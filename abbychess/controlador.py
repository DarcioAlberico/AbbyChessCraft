"""O controlador da página aberta (SPEC §14.1): os comandos da janela, sem Qt.

A janela só liga sinais a comandos e desenha o que os eventos dizem. Quem guarda a página
aberta, a fila de revisão, a seleção, o desfazer e decide o que cada comando faz é o
`ControladorDePagina`. Tudo é **por gid** (§4.1): a fila, os pulados, a seleção e o glifo
em revisão sobrevivem a dividir, juntar e marcar sem remapear índices, e a edição muda o
modelo (`abbychess.edicao`), que o gravador grava (`ProjetoDeLivro.agendar`).

**Eventos** (`Eventos`): `pagina_trocou`, `glifos_mudaram(gids)`, `atual_mudou`,
`selecao_mudou`, `padroes_mudaram`, `acoes_mudaram`, `mensagem(texto, ms)`,
`falha(titulo, texto)` e `aviso(titulo, texto)`; os outros controladores acrescentam os
deles.

**Todo comando que muda a página ou usa o leitor é uma tarefa** (`tarefa`), e as tarefas
rodam uma por vez, na ordem: a janela passa o executor do Qt, que as enfileira; os testes
passam o `ExecutorSincrono`. `preparar()` roda na thread da interface quando chega a vez
da tarefa: as edições (dividir, juntar, corrigir…) se fazem ali mesmo, e as leituras (ler,
ensinar, reconhecer) tiram o instantâneo do que precisam e devolvem `(trabalho, pronto)`;
`trabalho(progresso)` roda fora da interface sobre cópias, e `pronto(resultado)` põe o
resultado na página que a tarefa guardou. Assim o leitor nunca é usado por duas threads, e
nenhuma edição acontece no meio de uma leitura. O que o usuário pediu (os gids, o
caractere) é guardado na hora do comando: uma tarefa na fila não ensina outro glifo; e a
tarefa de outro projeto (aberto antes do atual) é descartada, pela `geracao`.

Enquanto o lote lê o livro (`lote_rodando`), editar a página é recusado com aviso: o lote
grava as páginas na thread dele.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np
from core.box_model import BoxEntry

from abbychess import diagramas as dg
from abbychess import edicao as ed
from abbychess import historico as hs
from abbychess import pagina as pg
from abbychess import procedencia
from abbychess import texto as tx
from abbychess import zonas as zn
from abbychess.leitor import FONTE_MANUAL, precisa_revisao
from abbychess.modelo import (LIDAS, NAO_RECONHECIDA, VERIFICADA, Diferenca, Pagina, proximo_estado,
                              reconciliar)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Antes:
    """A página e os padrões do livro quando uma edição começou (o "antes" da transação)."""

    pagina: Optional[Pagina]
    padroes: frozenset


class Eventos:
    """Os avisos dos controladores para quem desenha. Sem Qt: quem ouve é chamado na hora,
    na thread que emitiu (a da interface, para os comandos)."""

    def __init__(self):
        self._ouvintes: Dict[str, List[Callable]] = defaultdict(list)

    def ligar(self, nome: str, funcao: Callable) -> None:
        self._ouvintes[nome].append(funcao)

    def emitir(self, nome: str, *args) -> None:
        for funcao in list(self._ouvintes.get(nome, ())):
            funcao(*args)


class ExecutorSincrono:
    """O executor dos testes e das ferramentas: roda cada tarefa na hora, na mesma thread."""

    ocupado = False

    def so_leves(self) -> bool:
        return True                         # nada fica rodando: tudo pode na hora

    def __call__(self, titulo: str, preparar, falhou=None, progresso=None, leve=False) -> None:
        par = preparar()
        if par is None:
            return
        trabalho, pronto = par
        try:
            resultado = trabalho(progresso or (lambda *_: None))
        except Exception as erro:
            log.exception("a tarefa %r falhou", titulo)
            if falhou is None:
                raise
            falhou(str(erro))
            return
        pronto(resultado)


class ControladorDePagina:
    """A página aberta: o modelo dela, a fila, a seleção, o desfazer e os comandos."""

    def __init__(self, eventos: Optional[Eventos] = None, executar=None):
        self.eventos = eventos or Eventos()
        self.executar = executar or ExecutorSincrono()
        self.projeto = None
        self.fonte = None
        self.leitor = None
        self.indice = 0
        self.imagem = None
        self.matriz: Optional[np.ndarray] = None
        #: A página no modelo; `None` enquanto nada dela foi gravado (nasce na 1ª mudança).
        self.modelo: Optional[Pagina] = None
        #: O glifo em revisão, os pulados e a seleção do modo de treino, por gid.
        self.atual: Optional[int] = None
        self.pulados: set = set()
        #: A ordem da fila de glifos (§8.1): "confianca" (o menos confiável primeiro, os
        #: pulados no fim) ou "leitura" (a ordem da página).
        self.ordem_da_fila = "confianca"
        #: Na ordem de leitura: (página, posição na ordem da página) do último glifo mostrado,
        #: para a decisão seguir em frente mesmo quando o glifo sai (descartar, juntar).
        self._lugar_de_leitura = (-1, 0)
        #: (chave, gids) da última conta das margens corridas (`gids_de_margem`).
        self._margens: tuple = (None, frozenset())
        self.selecao: set = set()
        #: O desfazer do projeto (§14.2), da sessão.
        self.historico = hs.HistoricoDoProjeto()
        #: O lote está lendo o livro: editar a página espera.
        self.lote_rodando = False
        #: Muda a cada `ligar`: a tarefa pedida para outro projeto não roda nem aplica.
        self.geracao = 0
        #: O glifo em revisão foi escolhido pelo usuário (e não posto pela fila).
        self.escolhido = False

    # ------------------------------------------------------------------
    # O que a janela lê
    # ------------------------------------------------------------------
    @property
    def boxes(self) -> List[BoxEntry]:
        """Os glifos da página em ordem de leitura (os `BoxEntry`, para desenhar)."""
        return self.modelo.entries() if self.modelo is not None else []

    @property
    def gids(self) -> List[int]:
        return [b.gid for b in self.modelo.boxes] if self.modelo is not None else []

    def indice_de(self, gid: Optional[int]) -> Optional[int]:
        if gid is None or self.modelo is None:
            return None
        return next((i for i, b in enumerate(self.modelo.boxes) if b.gid == gid), None)

    def gid_em(self, indice: int) -> Optional[int]:
        if self.modelo is None or not 0 <= indice < len(self.modelo.boxes):
            return None
        return self.modelo.boxes[indice].gid

    def box(self, gid: int) -> BoxEntry:
        return self.modelo.box(gid).entry

    @property
    def reconhecida(self) -> bool:
        return self.modelo is not None and self.modelo.estado in LIDAS

    @property
    def estado(self) -> str:
        return self.modelo.estado if self.modelo is not None else NAO_RECONHECIDA

    @property
    def tabuleiros(self) -> list:
        return list(self.modelo.tabuleiros) if self.modelo is not None else []

    @property
    def diagramas(self) -> List[dg.DiagramaLido]:
        """Um diagrama por tabuleiro (os por ler também), em ordem."""
        if self.modelo is None:
            return []
        return dg.para_caixas(self.modelo.tabuleiros, self.modelo.diagramas)

    @property
    def zonas(self) -> list:
        return list(self.modelo.zonas) if self.modelo is not None else []

    @property
    def pronto(self) -> bool:
        """Há projeto, fonte e leitor: os comandos valem."""
        return self.projeto is not None and self.leitor is not None and self.fonte is not None

    def fila(self) -> List[int]:
        """Os gids a revisar: do menos confiável ao mais, com os pulados no fim; ou, na ordem
        de leitura (`ordem_da_fila`), na ordem da página."""
        if self.leitor is None or self.modelo is None:
            return []
        boxes = self.modelo.boxes
        indices = pg.fila_de_revisao(self.modelo.entries(), self.leitor)
        if self.ordem_da_fila == "leitura":
            return [boxes[i].gid for i in sorted(indices)]
        fila = [boxes[i].gid for i in indices]
        return [g for g in fila if g not in self.pulados] + [g for g in fila if g in self.pulados]

    def alvos(self) -> List[int]:
        """O que a decisão vale: a seleção inteira, ou só o glifo em revisão (por gid, na
        ordem de leitura)."""
        if self.atual is None:
            return []
        escolhidos = self.selecao | {self.atual}
        return [g for g in self.gids if g in escolhidos]

    def posicao_do_atual(self) -> str:
        """O que o Glifo diz da posição: nada, se o glifo está na fila (o contador do Inspetor
        a mostra); "fora da fila", se não."""
        if self.atual in self.fila():
            return ""
        return "Box fora da fila (já confirmado ou confiável)"

    def texto(self) -> str:
        """O texto da página (com as decisões e os diagramas), como no painel de baixo."""
        if self.modelo is None or not (self.modelo.boxes or self.modelo.tabuleiros):
            return ""
        pagina = self.modelo.instantaneo()
        pagina.diagramas = self.diagramas
        return tx.texto(tx.montar(pagina), pagina.diagramas, modo=tx.SAN)

    def documento(self):
        """O documento derivado da página (§4.2), para o painel Documento, com os glifos que
        ninguém leu (o realce os mostra); None sem página reconhecida."""
        if self.modelo is None or not (self.modelo.boxes or self.modelo.tabuleiros):
            return None
        pagina = self.modelo.instantaneo()
        pagina.diagramas = self.diagramas
        return tx.montar(pagina, com_os_nao_lidos=True)

    def gids_de_margem(self) -> frozenset:
        """Os glifos do cabeçalho e do rodapé corridos da página, pela regra da exportação
        (`exportar.margens_corridas`: a faixa, o vão e o número da página), até o layout do
        passo F dar a função às áreas."""
        if self.modelo is None or self.imagem is None:
            return frozenset()
        from abbychess import exportar as ex

        lidos = [b for b in self.modelo.boxes if b.entry.char]
        # A regra olha as linhas inteiras da página (~20 ms numa página cheia): o resultado
        # fica enquanto o que ela lê não muda (o texto, a posição de cada glifo lido e a
        # altura da página); montar a chave custa uma fração de milissegundo.
        chave = (self.indice, self.imagem.height,
                 tuple((b.gid, b.entry.char, b.entry.x1, b.entry.y1, b.entry.y2) for b in lidos))
        if self._margens[0] != chave:
            indices = ex.margens_corridas({0: ([b.entry for b in lidos], self.imagem.height)})[0]
            self._margens = (chave, frozenset(lidos[i].gid for i in indices if i < len(lidos)))
        return self._margens[1]

    def gids_virtuais(self) -> frozenset:
        """Os gids dos glifos virtuais (sem caixa) da página."""
        if self.modelo is None:
            return frozenset()
        return frozenset(v.gid for v in self.modelo.decisoes.virtuais)

    def padroes(self) -> frozenset:
        if self.leitor is None:
            return frozenset()
        return frozenset(c for v in self.leitor.padroes_por_caractere().values() for c in v)

    # ------------------------------------------------------------------
    # Projeto e páginas
    # ------------------------------------------------------------------
    def ligar(self, projeto, fonte, leitor) -> None:
        """O projeto aberto, a fonte das páginas e o leitor (os modelos já carregados)."""
        self.geracao += 1
        self.lote_rodando = False               # o lote do projeto anterior não vale aqui
        self.projeto, self.fonte, self.leitor = projeto, fonte, leitor
        #: As páginas renderizadas mais recentes e a pré-carga da seguinte (§14.1).
        self.cache = pg.CacheDePaginas(fonte) if fonte is not None else None
        #: As páginas visitadas, para Alt+← e Alt+→ (§3.3), e onde se está nelas.
        self.visitas: List[int] = []
        self._visita = -1
        self.historico = hs.HistoricoDoProjeto()
        self.modelo, self.atual, self.pulados, self.selecao = None, None, set(), set()
        self.imagem = self.matriz = None

    def desligar(self) -> None:
        self.ligar(None, None, None)

    def ir_para(self, indice: int, *, visita: bool = True) -> bool:
        """Abre a página `indice` (0 = a primeira). Falso se não deu (fora do livro, ou a
        fonte não renderizou; o motivo vai em `aviso`). `visita=False` é o Alt+← e o Alt+→,
        que andam no histórico de visitas sem mudá-lo."""
        if self.fonte is None or not 0 <= indice < self.fonte.total:
            return False
        try:
            imagem, matriz = self.cache.pagina(indice)
        except OSError as erro:
            self.eventos.emitir("aviso", "Página", str(erro))
            return False
        self.indice, self.imagem, self.matriz = indice, imagem, matriz
        if visita:
            self._registrar_visita(indice)
        self.modelo = self.projeto.carregar_modelo(indice)
        self.atual, self.pulados, self.selecao = None, set(), set()
        self.eventos.emitir("pagina_trocou")
        self.eventos.emitir("glifos_mudaram", None)
        if self.boxes:
            self.ir_ao_primeiro_pendente()
            if not self.reconhecida:
                self._avisar(f"Página com {len(self.boxes)} glifo(s) marcados à mão e ainda não "
                             "reconhecida. O F5 reconhece o resto e mantém os quadros.", 10000)
        else:
            self.eventos.emitir("atual_mudou")
        self.eventos.emitir("acoes_mudaram")
        return True

    def precarregar_seguinte(self) -> None:
        """Renderiza a página seguinte, a mais provável, noutra thread. A janela chama depois
        de pintar a atual: dentro do `ir_para`, a pré-carga disputava a CPU com a conversão e
        a pintura da página pedida, e a troca fora do cache ficava ~60 ms mais lenta."""
        if self.cache is not None and self.fonte is not None:
            self.cache.precarregar(self.indice + 1)

    # ------------------------------------------------------------------
    # Navegação (§3.3)
    # ------------------------------------------------------------------
    def _registrar_visita(self, indice: int) -> None:
        if 0 <= self._visita < len(self.visitas) and self.visitas[self._visita] == indice:
            return
        del self.visitas[self._visita + 1:]
        self.visitas.append(indice)
        self._visita = len(self.visitas) - 1

    @property
    def pode_voltar(self) -> bool:
        return self._visita > 0

    @property
    def pode_avancar(self) -> bool:
        return self._visita < len(self.visitas) - 1

    def voltar_visita(self) -> bool:
        """Alt+←: a página visitada antes desta."""
        if self._visita <= 0:
            return False
        if not self.ir_para(self.visitas[self._visita - 1], visita=False):
            return False
        self._visita -= 1
        self.eventos.emitir("acoes_mudaram")    # Alt+←/→ ligam e desligam pelo lugar novo
        return True

    def avancar_visita(self) -> bool:
        """Alt+→: a página visitada depois (depois de um Alt+←)."""
        if self._visita >= len(self.visitas) - 1:
            return False
        if not self.ir_para(self.visitas[self._visita + 1], visita=False):
            return False
        self._visita += 1
        self.eventos.emitir("acoes_mudaram")    # Alt+←/→ ligam e desligam pelo lugar novo
        return True

    def primeira(self) -> bool:
        return self.ir_para(0)

    def ultima(self) -> bool:
        return self.fonte is not None and self.ir_para(self.fonte.total - 1)

    def vizinha(self, passo: int) -> bool:
        """A página anterior (-1) ou a seguinte (+1), se houver."""
        return self.ir_para(self.indice + passo)

    def recarregar(self) -> None:
        """Mostra de novo a página aberta (o lote acabou de gravá-la)."""
        self.ir_para(self.indice)

    # ------------------------------------------------------------------
    # A fila de revisão
    # ------------------------------------------------------------------
    def mostrar(self, gid: Optional[int]) -> None:
        """Põe o glifo em revisão no painel de treino."""
        if gid is not None and self.indice_de(gid) is None:
            return
        self.atual = gid
        self._guardar_lugar()
        self.escolhido = False                  # `escolher` o liga depois, se foi o usuário
        self.eventos.emitir("atual_mudou")

    def _guardar_lugar(self) -> None:
        if self.atual is not None and self.ordem_da_fila == "leitura":
            gids = self.gids
            if self.atual in gids:
                self._lugar_de_leitura = (self.indice, gids.index(self.atual))

    def clicar(self, indice: int) -> None:
        """O box clicado no visor (pela posição na lista)."""
        self.escolher(self.gid_em(indice))

    def escolher(self, gid: Optional[int]) -> None:
        """O glifo que o usuário escolheu (clique, Tab): a propagação não o troca sozinha."""
        self.mostrar(gid)
        self.escolhido = self.atual is not None

    def ir_ao_primeiro_pendente(self) -> None:
        """O próximo a revisar depois de uma decisão: o primeiro da fila; na ordem de
        leitura, o primeiro pendente a partir do lugar do glifo decidido (e, no fim da
        página, o primeiro dela)."""
        fila = self.fila()
        if self.ordem_da_fila == "leitura" and fila:
            ordem = {g: n for n, g in enumerate(self.gids)}
            pagina, lugar = self._lugar_de_leitura
            lugar = ordem.get(self.atual, lugar if pagina == self.indice else 0)
            adiante = [g for g in fila if ordem[g] >= lugar]
            self.atual = adiante[0] if adiante else fila[0]
        else:
            self.atual = fila[0] if fila else None
        self._guardar_lugar()
        self.escolhido = False
        self.eventos.emitir("atual_mudou")

    def andar(self, passo: int) -> None:
        """Pula (passo > 0: o atual vai para o fim da fila) ou volta na fila. Na ordem de
        leitura, anda para o pendente seguinte (ou anterior) na página, sem pular."""
        fila = self.fila()
        if not fila:
            self.ir_ao_primeiro_pendente()
            return
        if self.ordem_da_fila == "leitura":
            ordem = {g: n for n, g in enumerate(self.gids)}
            aqui = ordem.get(self.atual, -1)
            if passo > 0:
                seguintes = [g for g in fila if ordem[g] > aqui]
                self.escolher(seguintes[0] if seguintes else fila[0])
            else:
                anteriores = [g for g in fila if ordem[g] < aqui]
                self.escolher(anteriores[-1] if anteriores else fila[-1])
            return
        if passo > 0 and self.atual in fila:
            self.pulados.add(self.atual)
            self.escolher(self.fila()[0])
            return
        posicao = fila.index(self.atual) if self.atual in fila else 0
        self.escolher(fila[(posicao + passo) % len(fila)])

    def verificar(self) -> None:
        """Ctrl+T: a página está verificada (§4.4), e a próxima página não verificada abre.
        Entra no desfazer; uma edição depois a devolve a `em_revisao`."""
        if self.modelo is None or self.modelo.estado not in LIDAS:
            self._avisar("Reconheça a página antes de marcá-la como verificada (F5).", 6000)
            return

        def corpo():
            antes = self._instantaneo()
            self._mudou(self.modelo, self.indice, "Página verificada", antes, evento="verificar")
            self.eventos.emitir("acoes_mudaram")
            proxima = self._proxima_nao_verificada()
            if proxima is None:
                self._avisar("Página verificada. As seguintes já estão todas verificadas.", 6000)
                return
            verificada = self.indice + 1
            self.ir_para(proxima)
            self._avisar(f"Página {verificada} verificada; abrindo a {proxima + 1}.", 6000)
        self._editar("Verificando a página", corpo, precisa_de_glifos=False)

    def _proxima_nao_verificada(self) -> Optional[int]:
        """A primeira página depois da aberta que não está verificada (a não reconhecida
        conta: está por revisar)."""
        resumo = self.projeto.resumo_do_livro()
        for i in range(self.indice + 1, self.fonte.total):
            if resumo.get(i, {}).get("estado") != VERIFICADA:
                return i
        return None

    def alternar_na_selecao(self, indice: int) -> None:
        """O Ctrl+clique do modo de treino: põe ou tira o glifo da seleção."""
        gid = self.gid_em(indice)
        if gid is None:
            return
        if gid in self.selecao or (gid == self.atual and not self.selecao):
            self.selecao.discard(gid)
            if gid == self.atual and self.selecao:
                self.mostrar(next(g for g in self.gids if g in self.selecao))
        else:
            if self.atual is not None:
                self.selecao.add(self.atual)
            self.selecao.add(gid)
            self.mostrar(gid)
        self.eventos.emitir("selecao_mudou")

    def limpar_selecao(self) -> None:
        self.selecao = set()
        self.eventos.emitir("selecao_mudou")

    # ------------------------------------------------------------------
    # As tarefas
    # ------------------------------------------------------------------
    def tarefa(self, titulo: str, preparar, falhou=None, progresso=None, *,
               leve: bool = False) -> None:
        """Põe `preparar` na fila do executor, presa ao projeto de agora: se outro projeto
        for aberto antes da vez dela (ou antes do fim do trabalho), ela não roda (ou o
        resultado não entra). `leve` é a propagação de um Enter, que lê com uma cópia dos
        padrões: com ela rodando, as edições não esperam (`_agora`)."""
        geracao = self.geracao

        def guardado():
            if self.geracao != geracao:
                return None
            par = preparar()
            if par is None:
                return None
            trabalho, pronto = par

            def pronto_guardado(resultado):
                if self.geracao != geracao:
                    log.info("o resultado de %r foi descartado: o projeto mudou", titulo)
                    return
                pronto(resultado)
            return trabalho, pronto_guardado

        self.executar(titulo, guardado, falhou=falhou, progresso=progresso, leve=leve)

    def _agora(self) -> bool:
        """Uma edição pode rodar na hora: nada roda, ou só a propagação de um Enter (que lê
        com uma cópia dos padrões e só entra nos glifos que não mudaram, §14.2)."""
        so_leves = getattr(self.executar, "so_leves", None)
        return so_leves() if so_leves is not None else not getattr(self.executar, "ocupado", False)

    def _editar(self, titulo: str, corpo, *, precisa_de_glifos: bool = True) -> None:
        """Uma edição: na hora, se nada prende o leitor (`_agora`); senão na fila, e `corpo()`
        roda na vez dela, se a página ainda é a mesma (se não é, avisa que a edição foi
        descartada). Durante o lote, é recusada na hora."""
        if self.lote_rodando:
            self._recusar_no_lote()
            return
        if self._agora():
            if self._pode_editar(precisa_de_glifos):
                corpo()
            return
        indice = self.indice

        def preparar():
            if self.indice != indice:
                self._avisar(f"{titulo}: descartado, porque a página mudou (era a {indice + 1}) "
                             "antes da vez dele na fila.", 8000)
            elif self._pode_editar(precisa_de_glifos):
                corpo()
            return None
        self.tarefa(titulo, preparar, falhou=self._falhou(titulo))

    # ------------------------------------------------------------------
    # Os comandos que leem (fora da thread da interface)
    # ------------------------------------------------------------------
    def reconhecer(self) -> None:
        """F5: segmenta pelas áreas, lê e acha os diagramas. Mantém os glifos marcados à mão
        de uma página ainda não reconhecida; numa já reconhecida, os glifos novos herdam o
        gid (e as decisões) de quem estava no mesmo lugar (`modelo.reconciliar`)."""
        if not self._pode_ler():
            return
        indice = self.indice
        self.tarefa("Reconhecendo a página", lambda: self._preparar_reconhecer(indice),
                    falhou=self._falhou("Reconhecer página"))

    def _preparar_reconhecer(self, indice: int):
        if indice != self.indice or not self._pode_ler(avisar=False):
            return None
        pagina = self._pagina_para_editar()
        imagem, leitor, zonas = self.imagem, self.leitor, list(pagina.zonas)
        antes = self._instantaneo()
        marcados = pg.a_manter_na_releitura(pagina.boxes, pagina.estado in LIDAS)   # §4.6

        def trabalho(progresso):
            segmentada = zn.segmentar(imagem, zonas, leitor)
            if marcados:
                segmentada.boxes = pg.manter_marcados(segmentada.boxes, marcados)
            pg.ler_boxes(imagem, segmentada.boxes, leitor, progresso=progresso)
            lidos = dg.ler_diagramas(imagem, segmentada.tabuleiros, escala=segmentada.escala,
                                     classificar=leitor.arbitro, boxes=segmentada.boxes)
            return segmentada, lidos

        def pronto(resultado):
            segmentada, lidos = resultado
            novos, dif = reconciliar(pagina.boxes, segmentada.boxes, pagina.alocar,
                                     procedencia.amostra_de)
            pagina.aplicar(dif, novos)
            pagina.tabuleiros = [tuple(int(v) for v in t) for t in segmentada.tabuleiros]
            # A conferência de antes vale mais que a releitura do mesmo tabuleiro.
            pagina.diagramas = dg.mesclar(lidos, dg.para_caixas(pagina.tabuleiros,
                                                                pagina.diagramas))
            if pagina is self.modelo:
                self.atual, self.pulados, self.selecao = None, set(), set()
            self._mudou(pagina, indice, "Reconhecer a página", antes, evento="reconhecer")
            if pagina is self.modelo:
                self.ir_ao_primeiro_pendente()
                resumo = pg.resumir(pagina.entries(), leitor)
                areas = f", pelas {len(zonas)} área(s) da página" if zonas else ""
                self._avisar(f"{resumo.boxes} boxes, {resumo.pendentes} a revisar, "
                             f"{len(pagina.tabuleiros)} diagrama(s){areas}.", 8000)

        return trabalho, pronto

    def reler_pendentes(self, tudo: bool = False) -> None:
        """Lê de novo os pendentes (ou todos os não manuais), com os padrões de agora."""
        if not self._pode_ler() or not self.boxes:
            return
        indice = self.indice
        self.tarefa("Relendo", lambda: self._preparar_reler(indice, tudo),
                    falhou=self._falhou("Reler"))

    def _preparar_reler(self, indice: int, tudo: bool, transacao: Optional[hs.Transacao] = None):
        """`transacao` é a do esquecer de padrões que pediu esta releitura: o que ela mudar
        emenda o `depois` dela, e um Ctrl+Z desfaz as duas coisas (o Ctrl+Z espera a
        releitura: ela não é leve)."""
        pagina = self.modelo
        if indice != self.indice or pagina is None or not pagina.boxes or self.leitor is None:
            return None                     # a página mudou antes da vez da releitura
        imagem = self.imagem
        leitor, limiares = self.leitor, self.leitor.limiares
        antes = tuple(pagina.boxes)
        if tudo:
            lidos = ed.copias_para_ler(antes, lambda e: e.source != FONTE_MANUAL)
        else:
            lidos = ed.copias_para_ler(antes, lambda e: precisa_revisao(
                e.char, e.source, e.confidence, limiares))

        def trabalho(progresso):
            return pg.ler_boxes(imagem, lidos, leitor, so_pendentes=not tudo, progresso=progresso)

        def pronto(resumo):
            foto = pagina.instantaneo()
            dif = ed.aplicar_leituras(pagina, antes, lidos)
            if not dif.vazia:
                if transacao is not None:
                    self._emendar(transacao, foto, pagina)
                else:                       # o Ctrl+R também se desfaz (§14.2)
                    self.historico.registrar(hs.Transacao(
                        "Reler pendentes", {pagina.pid: hs.mudanca(foto, pagina.instantaneo())}))
                    self.eventos.emitir("acoes_mudaram")
                self._gravar(pagina)
            if pagina is self.modelo:
                self.eventos.emitir("glifos_mudaram", dif.mudados)
                self.ir_ao_primeiro_pendente()
                self._avisar(f"Relida. {resumo.pendentes} a revisar.", 6000)

        return trabalho, pronto

    def ensinar(self, char: str) -> None:
        """Enter: ensina o glifo em revisão (ou a seleção inteira) como `char` neste livro e
        propaga o padrão pelos pendentes da página."""
        if self.atual is None or not self._pode_ler():
            return
        alvos = self.alvos()
        self.ensinar_gids({char: alvos}, f"Ensinar '{char}'", self._depois_de_ensinar(char, alvos))

    def _depois_de_ensinar(self, char: str, alvos: Sequence[int]):
        amostras = f" com {len(alvos)} amostras" if len(alvos) > 1 else ""

        def ensinou() -> None:                          # a parte síncrona: na hora
            self.pulados.difference_update(alvos)
            self.selecao = set()
            self.eventos.emitir("selecao_mudou")
            self.ir_ao_primeiro_pendente()
            self._avisar(f"Padrão '{char}' ensinado{amostras}; propagando pela página…", 5000)

        def propagou(resolvidos: int) -> None:          # depois da propagação
            if resolvidos:
                self._avisar(f"Padrão '{char}' ensinado{amostras} e resolveu mais "
                             f"{resolvidos} na página.", 5000)
            if self.atual is None or self.atual not in self.fila():
                # O glifo mostrado se resolveu: a janela avança (ou, se o usuário o escolheu,
                # mostra a leitura nova dele), a não ser que ele já esteja digitando
                # (`atual_resolvido`).
                self.eventos.emitir("atual_resolvido")
        return ensinou, propagou

    def ensinar_gids(self, por_char: Dict[str, Sequence[int]], descricao: str,
                     depois=None, *, juntar=None) -> None:
        """Ensina cada grupo de gids como o caractere dele (§14.2): a parte síncrona (o
        glifo vira manual, a amostra é gravada, a cor muda) roda na hora, se nada prende o
        leitor (`_agora`); a propagação pelos pendentes da página vai para a fila, com uma
        cópia dos padrões que já tem as amostras novas, e emenda a transação deste Enter.
        `depois` é `(ensinou, propagou(resolvidos))`, ou uma função só (chamada com o número
        de resolvidos no fim). `juntar` é a chave da transação que este emenda (a correção de
        uma palavra que também ensina: um Ctrl+Z desfaz as duas)."""
        indice = self.indice

        def agora():
            self._ensinar_agora(indice, por_char, descricao, depois, juntar)

        if self._agora():
            agora()
        else:
            self.tarefa("Ensinando", lambda: (agora(), None)[1], falhou=self._falhou("Ensinar"))

    def _ensinar_agora(self, indice, por_char, descricao, depois, juntar) -> None:
        pagina = self.modelo
        if indice != self.indice or pagina is None or self.leitor is None:
            return
        vivos = pagina.vivos
        por_char = {c: [g for g in gids if g in vivos] for c, gids in por_char.items()}
        por_char = {c: gids for c, gids in por_char.items() if gids}
        if not por_char:
            self._avisar("O glifo a ensinar saiu da página antes da vez dele.", 6000)
            return
        imagem, leitor, projeto = self.imagem, self.leitor, self.projeto
        antes_inst = self._instantaneo()
        antes = tuple(pagina.boxes)
        onde = {b.gid: i for i, b in enumerate(antes)}
        lidos = [b.entry for b in antes]
        try:
            for char, gids in por_char.items():
                for gid in gids:
                    i = onde[gid]
                    lidos[i] = ed.copia(antes[i].entry)
                    pg.ensinar(imagem, lidos, i, char, leitor, projeto, indice,
                               propagar=False, gid=gid)
        except Exception as erro:        # disco cheio, antivírus: nada do Enter fica
            for caminho in self.padroes() - antes_inst.padroes:
                try:
                    leitor.esquecer(caminho)
                except Exception:
                    log.exception("a amostra %s ficou sem o Enter dela", caminho)
            log.exception("o Enter falhou")
            self._falhou("Ensinar")(f"O padrão não foi ensinado: {erro}")
            return
        ed.aplicar_leituras(pagina, antes, lidos)
        transacao = self._mudou(pagina, indice, descricao, antes_inst, juntar=juntar)
        self.eventos.emitir("padroes_mudaram")
        ensinou, propagou = depois if isinstance(depois, tuple) else (None, depois)
        if ensinou is not None and pagina is self.modelo:
            ensinou()
        self._propagar(pagina, indice, transacao, propagou)

    def _propagar(self, pagina: Pagina, indice: int, transacao: hs.Transacao,
                  ao_fim: Optional[Callable[[int], None]]) -> None:
        """A propagação do Enter: os pendentes da página pelos padrões do livro de agora (uma
        cópia, que já tem as amostras do Enter), fora da interface. O que ela resolve emenda
        a `transacao`; desfeita antes do fim, o resultado é descartado."""
        foto_do_leitor = self.leitor.para_propagar()
        imagem = self.imagem

        def preparar():
            if transacao.invalidada:
                return None
            antes = tuple(pagina.boxes)
            limiares = foto_do_leitor.limiares
            lidos = ed.copias_para_ler(antes, lambda e: precisa_revisao(
                e.char, e.source, e.confidence, limiares))

            def trabalho(_progresso):
                return pg.propagar_padroes(imagem, lidos, foto_do_leitor)

            def pronto(resolvidos: int):
                if transacao.invalidada:
                    self._avisar("A propagação foi descartada: o Enter dela foi desfeito.",
                                 5000)
                    return
                foto = pagina.instantaneo()
                dif = ed.aplicar_leituras(pagina, antes, lidos)
                if not dif.vazia:
                    self._emendar(transacao, foto, pagina)
                    self._gravar(pagina)
                    if pagina is self.modelo:
                        self.eventos.emitir("glifos_mudaram", dif.mudados)
                    self.eventos.emitir("acoes_mudaram")
                if ao_fim is not None and pagina is self.modelo:
                    ao_fim(len(dif.mudados))
            return trabalho, pronto

        self.tarefa("Propagando o padrão", preparar, falhou=self._falhou("Propagar"), leve=True)

    def _emendar(self, transacao: hs.Transacao, antes: Pagina, pagina: Pagina) -> None:
        mais = hs.mudanca(antes, pagina.instantaneo())
        if pagina.pid in transacao.paginas:
            hs.emendar(transacao.paginas[pagina.pid], mais)
        else:
            transacao.paginas[pagina.pid] = mais
        self.historico.emendou(transacao)

    # ------------------------------------------------------------------
    # Os comandos que editam (na vez deles na fila: na hora, se nada está rodando)
    # ------------------------------------------------------------------
    def _vivos(self, gids) -> List[int]:
        vivos = set(self.gids)
        return [g for g in gids if g in vivos]

    def corrigir(self, char: str) -> None:
        """Shift+Enter: aceita `char` no glifo em revisão (ou na seleção) sem ensinar."""
        if self.atual is None:
            return
        pedidos = self.alvos()

        def corpo():
            alvos = self._vivos(pedidos)
            if not alvos:
                self._avisar("O glifo a corrigir saiu da página antes da vez dele.", 6000)
                return
            antes = self._instantaneo()
            for gid in alvos:
                ed.corrigir(self.modelo, gid, char)
            self.pulados.difference_update(alvos)
            self.selecao = set()
            self._mudou(self.modelo, self.indice, f"Corrigir para '{char}'", antes)
            self.eventos.emitir("selecao_mudou")
            self.ir_ao_primeiro_pendente()
        self._editar("Corrigindo", corpo)

    def descartar(self) -> None:
        """Del: tira o glifo da página (não é caractere)."""
        gid = self.atual
        if gid is None:
            return

        def corpo():
            if not self._vivos([gid]):
                return
            antes = self._instantaneo()
            dif = ed.descartar(self.modelo, gid)
            self._seguir(dif)
            self.selecao = set()
            self._mudou(self.modelo, self.indice, "Descartar box", antes)
            self.eventos.emitir("selecao_mudou")
            self.ir_ao_primeiro_pendente()
        self._editar("Descartando", corpo)

    def dividir(self, coluna: Optional[int] = None, gid: Optional[int] = None) -> None:
        """Ctrl+D: divide o glifo em dois (no ponto `coluna`, ou pela tinta) e mostra a
        primeira parte, já relida."""
        gid = self.atual if gid is None else gid
        if gid is None:
            return

        def corpo():
            if not self._vivos([gid]):
                return
            antes = self._instantaneo()
            try:
                dif = ed.dividir(self.modelo, self.imagem, gid, self.leitor, x=coluna)
            except ValueError as erro:
                self._avisar(f"Não dividiu: {erro}", 6000)
                return
            self._seguir(dif)
            self._depois_de_editar(dif.novos[0].gid, "Dividir box", antes,
                                   "Box dividido em dois; as partes foram relidas.")
        self._editar("Dividindo", corpo)

    def juntar(self, passo: int, gid: Optional[int] = None) -> None:
        """Ctrl+J: junta o glifo com o vizinho da mesma linha (passo +1 ou -1)."""
        gid = self.atual if gid is None else gid
        if gid is None:
            return

        def corpo():
            i = self.indice_de(gid)
            outro = pg.vizinho(self.boxes, i, passo) if i is not None else None
            if outro is None:
                lado = "seguinte" if passo > 0 else "anterior"
                self._avisar(f"Não há box {lado} nesta linha para juntar.", 6000)
                return
            antes = self._instantaneo()
            dif = ed.juntar(self.modelo, self.imagem, gid, self.gid_em(outro), self.leitor)
            self._seguir(dif)
            self._depois_de_editar(dif.novos[0].gid, "Juntar boxes", antes,
                                   "Boxes juntados; o box novo foi relido.")
        self._editar("Juntando", corpo)

    def dividir_em(self, indice: int, coluna: int) -> None:
        """O "Dividir aqui" do menu do visor (o box pela posição na lista)."""
        gid = self.gid_em(indice)
        if gid is not None:
            self.dividir(coluna, gid)

    def juntar_com(self, indice: int, passo: int) -> None:
        gid = self.gid_em(indice)
        if gid is not None:
            self.juntar(passo, gid)

    def ajustar(self, esquerda: int, cima: int, direita: int, baixo: int) -> None:
        """Alt+seta: move as bordas do glifo em revisão, em pixels da página."""
        gid = self.atual
        if gid is None:
            return

        def corpo():
            if not self._vivos([gid]):
                return
            antes = self._instantaneo()
            try:
                ed.ajustar(self.modelo, self.imagem, gid, self.leitor, esquerda=esquerda,
                           cima=cima, direita=direita, baixo=baixo)
            except ValueError as erro:
                self._avisar(f"Não ajustou: {erro}", 6000)
                return
            b = self.box(gid)
            # Os Alt+seta seguidos no mesmo box viram um passo só.
            self._depois_de_editar(gid, "Ajustar bordas", antes,
                                   f"Box em ({b.x1}, {b.y1})–({b.x2}, {b.y2}).",
                                   juntar=("ajustar", gid))
        self._editar("Ajustando", corpo)

    def marcar(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """O quadro desenhado no modo de treino vira glifo, lido, no lugar dos de dentro."""
        if self.imagem is None:
            return

        def corpo():
            antes = self._instantaneo()
            pagina = self._pagina_para_editar()
            try:
                dif = ed.marcar(pagina, self.imagem, (x1, y1, x2, y2), self.leitor)
            except ValueError as erro:
                self._avisar(f"Não marcou: {erro}", 6000)
                return
            self._seguir(dif)
            tirados = len(dif.removidos)
            extra = f", no lugar de {tirados} box(es) de dentro" if tirados else ""
            self._depois_de_editar(dif.novos[0].gid, "Marcar glifo", antes,
                                   f"Glifo marcado{extra}. Digite o caractere e Enter.",
                                   evento="marcar")
        self._editar("Marcando", corpo, precisa_de_glifos=False)

    def _depois_de_editar(self, mostrar: int, descricao: str, antes: hs.Instantaneo,
                          mensagem: str, *, juntar=None, evento: str = "editar") -> None:
        self.selecao = set()
        self._mudou(self.modelo, self.indice, descricao, antes, juntar=juntar, evento=evento)
        self.eventos.emitir("selecao_mudou")
        self.mostrar(mostrar)
        self._avisar(mensagem, 5000)

    # ------------------------------------------------------------------
    # Desfazer, padrões e limiares
    # ------------------------------------------------------------------
    def desfazer(self) -> None:
        """Ctrl+Z: desfaz a última transação do projeto (§14.2), na página dela; com só a
        propagação de um Enter rodando, na hora (e a propagação é descartada)."""
        self._desfazer_ou_refazer(refazer=False)

    def refazer(self) -> None:
        self._desfazer_ou_refazer(refazer=True)

    def _desfazer_ou_refazer(self, *, refazer: bool) -> None:
        if self.lote_rodando:
            self._recusar_no_lote()
            return
        if self._agora():
            self._voltar(refazer)
        else:
            self.tarefa("Refazendo" if refazer else "Desfazendo",
                        lambda: (self._voltar(refazer), None)[1],
                        falhou=self._falhou("Desfazer"))

    def _voltar(self, refazer: bool) -> None:
        h = self.historico
        transacao = h.proxima_a_refazer() if refazer else h.proxima_a_desfazer()
        if transacao is None or self.leitor is None or self.projeto is None:
            return
        paginas = {}
        try:
            for pid, m in transacao.paginas.items():
                pagina = (self.modelo if self.modelo is not None and self.modelo.pid == pid
                          else self.projeto.carregar_modelo(m.indice))
                if pagina is None or pagina.pid != pid:
                    raise hs.Recusa(f"a página {m.indice + 1} não é mais a da transação")
                hs.conferir(m, pagina, para_tras=not refazer)
                paginas[pid] = pagina
        except hs.Recusa as recusa:
            acao = "refazer" if refazer else "desfazer"
            self.eventos.emitir("recusa", refazer, f"Não dá para {acao} "
                                f"\u201c{transacao.descricao}\u201d: {recusa}. Nada foi mudado.")
            return
        for pid, m in transacao.paginas.items():
            hs.aplicar(m, paginas[pid], para_tras=not refazer)
        if not refazer:
            # A propagação dela, se ainda roda, não entra; e o refazer não a roda de novo
            # (refaz o que a transação guardou: o Ctrl+R relê os pendentes).
            transacao.invalidada = True
        for pagina in paginas.values():
            self._gravar(pagina)
        if refazer:
            for amostra in transacao.amostras_criadas:
                self.leitor.padroes.restaurar(amostra)
            for amostra in transacao.amostras_apagadas:
                if amostra.caminho.exists():
                    self.leitor.esquecer(amostra.caminho)
            h.refeita()
        else:
            for amostra in transacao.amostras_criadas:
                if amostra.caminho.exists():
                    self.leitor.esquecer(amostra.caminho)
            for amostra in transacao.amostras_apagadas:
                self.leitor.padroes.restaurar(amostra)
            h.desfeita()
        aberta = self.modelo is not None and self.modelo.pid in transacao.paginas
        if aberta or not transacao.indices or not self.ir_para(transacao.indices[0]):
            # A página aberta mudou (ou a da transação não abre): o glifo em revisão, os
            # pulados e a seleção podem citar glifos que saíram.
            self.atual, self.pulados, self.selecao = None, set(), set()
            self.eventos.emitir("glifos_mudaram", None)
            self.eventos.emitir("selecao_mudou")
            self.ir_ao_primeiro_pendente()
        repropagar = refazer and transacao.invalidada and transacao.amostras_criadas
        if repropagar and self.modelo is not None and self.modelo.pid in transacao.paginas:
            # Um Enter cuja propagação foi descartada quando ele foi desfeito: ela roda de
            # novo (na página dele, já aberta), com os padrões de agora, e emenda a transação.
            transacao.invalidada = False
            self._propagar(self.modelo, self.indice, transacao, None)
        self.eventos.emitir("padroes_mudaram")
        self.eventos.emitir("acoes_mudaram")
        acao = "Refeito" if refazer else "Desfeito"
        self._avisar(f"{acao}: {transacao.descricao}.", 6000)

    def tirar_do_desfazer(self, refazer: bool = False) -> None:
        """Tira a próxima ação do desfazer (ou do refazer) sem aplicá-la: depois de uma
        recusa, para chegar às anteriores."""
        if refazer:
            self.historico.descartar_refazer()
        else:
            self.historico.descartar_desfazer()
        self.eventos.emitir("acoes_mudaram")
        self._avisar("A ação saiu do desfazer; o Ctrl+Z segue com as anteriores.", 6000)

    def esquecer(self, caminhos: Sequence) -> None:
        """Apaga amostras dos padrões do livro e relê a página inteira sem elas (na fila: o
        leitor não muda no meio de uma leitura)."""
        if self.leitor is None:
            return
        if self.lote_rodando:                   # o lote lê com estes padrões
            self._recusar_no_lote()
            return
        caminhos = list(caminhos)

        def preparar():
            if self.leitor is None:
                return None
            antes = self._instantaneo()
            apagadas = [self.leitor.padroes.guardar(c) for c in caminhos]
            for caminho in caminhos:
                self.leitor.esquecer(caminho)
            self.eventos.emitir("padroes_mudaram")
            transacao = hs.Transacao(f"Esquecer {len(caminhos)} amostra(s)",
                                     amostras_apagadas=apagadas)
            if self.modelo is not None:
                novo = proximo_estado(self.modelo.estado, "esquecer_padrao")
                if novo != self.modelo.estado:
                    self.modelo.estado = novo
                    transacao.paginas[self.modelo.pid] = hs.mudanca(
                        antes.pagina, self.modelo.instantaneo())
                    self._gravar(self.modelo)
                    self._avisar("A página estava verificada e voltou à revisão: o padrão "
                                 "esquecido lia glifos dela.", 8000)
            self.historico.registrar(transacao)
            self.eventos.emitir("acoes_mudaram")
            if self.modelo is not None and self.modelo.boxes:
                indice = self.indice
                self.tarefa("Relendo", lambda: self._preparar_reler(indice, True, transacao),
                            falhou=self._falhou("Reler"))
            return None
        self.tarefa("Esquecendo padrões", preparar, falhou=self._falhou("Esquecer padrões"))

    def aplicar_limiares(self, limiares) -> None:
        """Os limiares do livro, gravados no projeto, e a fila refeita com eles (na fila: a
        fila de revisão não muda no meio de uma leitura). A mensagem vai para a barra; um
        problema ao gravar vai em `aviso`."""
        if self.lote_rodando:
            self._recusar_no_lote()
            return

        def preparar():
            if self.projeto is not None:
                self._aplicar_limiares(limiares)
            return None
        self.tarefa("Aplicando os limiares", preparar, falhou=self._falhou("Opções"))

    def _aplicar_limiares(self, limiares) -> None:
        projeto = self.projeto
        projeto.dados.limiares = limiares
        gravou = False
        if not projeto.somente_leitura:
            try:
                projeto.salvar()
            except OSError as erro:
                self.eventos.emitir("aviso", "Opções", "Os limiares valem nesta sessão, mas "
                                    f"não foram gravados no projeto:\n{erro}")
            else:
                gravou = True
                try:
                    projeto.reaplicar_limiar()
                except OSError as erro:
                    self.eventos.emitir("aviso", "Opções", "Os limiares foram gravados, mas o "
                                        "resumo do livro (livro.json) não; ele é refeito na "
                                        f"próxima gravação de página:\n{erro}")
        self.leitor.trocar_limiares(limiares)
        self.eventos.emitir("glifos_mudaram", None)
        if self.boxes:
            self.ir_ao_primeiro_pendente()
        if gravou:
            mensagem = "Limiares do livro gravados."
        elif projeto.somente_leitura:
            mensagem = "Limiares aplicados nesta sessão (o projeto é só para leitura)."
        else:
            mensagem = "Limiares aplicados nesta sessão (não foram gravados)."
        self._avisar(mensagem, 5000)

    # ------------------------------------------------------------------
    # Por dentro
    # ------------------------------------------------------------------
    def _avisar(self, texto: str, ms: int = 6000) -> None:
        self.eventos.emitir("mensagem", texto, ms)

    def _falhou(self, titulo: str):
        def falhou(mensagem: str) -> None:
            self.eventos.emitir("falha", titulo, mensagem)
        return falhou

    def _recusar_no_lote(self) -> None:
        self._avisar("O lote está lendo o livro: o comando foi recusado. Espere o lote acabar "
                     "ou cancele-o no menu Ferramentas.", 8000)

    def _pode_ler(self, avisar: bool = True) -> bool:
        if not self.pronto or self.imagem is None:
            return False
        if self.lote_rodando:
            if avisar:
                self._recusar_no_lote()
            return False
        return True

    def _pode_editar(self, precisa_de_glifos: bool = True) -> bool:
        if not self._pode_ler():
            return False
        return not precisa_de_glifos or bool(self.boxes)

    def box_atual(self) -> Optional[BoxEntry]:
        """O glifo em revisão, ou None se ele não está mais na página (o lote a releu)."""
        i = self.indice_de(self.atual)
        return self.modelo.boxes[i].entry if i is not None else None

    def _pagina_para_editar(self) -> Pagina:
        if self.modelo is None:
            self.modelo = self.projeto.pagina_para_editar(self.indice)
        return self.modelo

    def _instantaneo(self) -> Antes:
        """A página agora, com os padrões que o livro tem, para o desfazer."""
        pagina = self.modelo.instantaneo() if self.modelo is not None else None
        return Antes(pagina, self.padroes())

    def _seguir(self, dif: Diferenca) -> None:
        """O atual passa ao primeiro sucessor; pulados e seleção ficam só com os vivos."""
        if self.atual in dif.removidos:
            sucessores = dif.sucessores.get(self.atual) or []
            self.atual = sucessores[0] if sucessores else None
        self.pulados -= dif.removidos
        self.selecao -= dif.removidos
        if dif.caidas:
            self._avisar("Decisões que não puderam seguir os glifos: " + "; ".join(dif.caidas),
                         10000)

    def _mudou(self, pagina: Pagina, indice: int, descricao: str, antes: Antes, *,
               juntar=None, evento: Optional[str] = "editar") -> hs.Transacao:
        """Depois de uma edição: o estado (§4.4), o lado dos diagramas, o passo do desfazer,
        a gravação e o aviso.

        Ensinar, corrigir, dividir ou juntar um box da legenda muda o que ela diz: o lado
        dos diagramas não conferidos sai de novo dela aqui, sem reler os tabuleiros, e
        entra no mesmo passo do desfazer (`diagramas.rederivar_lados`). O F5 já leu tudo."""
        if evento is not None:              # mudar só as áreas não é editar a página (§4.4)
            pagina.estado = proximo_estado(pagina.estado, evento)
        if evento not in (None, "reconhecer") and pagina.diagramas and antes.pagina is not None:
            pagina.diagramas = dg.rederivar_lados(pagina.diagramas, antes.pagina.entries(),
                                                  pagina.entries())
        criados = []
        if self.leitor is not None:
            for caminho in sorted(self.padroes() - antes.padroes):
                criados.append(self.leitor.padroes.guardar(caminho))
        # Os ids das áreas e dos diagramas nascem antes de medir: o que a transação guarda é
        # o que vai para o disco (e o desfazer compara com o que a página tem).
        pagina.zonas = zn.com_ids(pagina.zonas)
        pagina.diagramas = dg.com_ids(pagina.diagramas)
        transacao = self.historico.registrar(hs.Transacao(
            descricao, {pagina.pid: hs.mudanca(antes.pagina, pagina.instantaneo())},
            amostras_criadas=criados, juntar=juntar))
        self._gravar(pagina)
        if pagina is self.modelo:
            m = transacao.paginas.get(pagina.pid)
            # Só a leitura de alguns glifos mudou (a lista e as caixas, não): a janela
            # repinta só eles; senão, tudo.
            so_leitura = (m is not None and m.ordem is None and not m.campos.keys() - {"estado"}
                          and all(a is not None and d is not None for a, d in
                                  zip(m.antes.values(), m.depois.values())))
            self.eventos.emitir("glifos_mudaram", set(m.antes) if so_leitura else None)
        self.eventos.emitir("acoes_mudaram")
        return transacao

    def _gravar(self, pagina: Pagina) -> None:
        if not self.projeto.agendar(pagina):
            self._avisar("Projeto aberto só para leitura: nada é gravado.", 6000)

