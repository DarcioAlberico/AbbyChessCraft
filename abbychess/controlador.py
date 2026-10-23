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

O lote (`lote.CondutorDoLote`, `lote_rodando`) não prende a janela: lê pelo servidor e
grava cada página aqui, na thread da interface, entre um comando e outro; as edições, o F5 e
o desfazer valem durante ele.

**O servidor de leitura** (§11, `servidor`): com ele, a interface não tem os modelos globais;
o leitor dela só tem os padrões do livro (a propagação, a fila), e o que eles não leem fica
"aguardando leitura". O F5, o reler, os diagramas e os glifos aguardando vão ao servidor, e a
resposta entra como a da propagação: nos glifos que não mudaram, emendando a transação da
edição. Antes de cada pedido, os padrões criados e apagados desde o último vão ao servidor
(`_sincronizar_padroes`). Sem servidor (os testes, as ferramentas), lê-se aqui mesmo.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from core.box_model import BoxEntry

from abbychess import ancoragem as ag
from abbychess import diagramas as dg
from abbychess import edicao as ed
from abbychess import historico as hs
from abbychess import lances as lc
from abbychess import modelo as md
from abbychess import pagina as pg
from abbychess import procedencia
from abbychess import servidor_de_leitura as sl
from abbychess import sessao as ss
from abbychess import texto as tx
from abbychess import zonas as zn
from abbychess.leitor import FONTE_MANUAL, FONTE_NENHUMA, precisa_revisao
from abbychess.modelo import (IOU_DA_RELEITURA, LIDAS, NAO_RECONHECIDA, VERIFICADA, Diferenca,
                              Pagina, descrever_caidas, proximo_estado, reconciliar)

log = logging.getLogger(__name__)

#: O máximo que um pedido da janela espera o servidor (o F5 com os modelos ainda carregando
#: cabe com folga): um servidor travado sem morrer não prende a fila de tarefas para sempre.
TEMPO_DO_PEDIDO = 600.0


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

    def na_interface(self, funcao) -> None:
        funcao()                            # não há outra thread de interface

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
        #: O servidor de leitura do projeto (§11), ou None: lê-se na interface.
        self.servidor: Optional[sl.ServidorDeLeitura] = None
        #: Os padrões que o servidor já tem (os deltas vão a partir deles).
        self._enviados: frozenset = frozenset()
        #: Os gids aguardando cuja leitura já foi pedida ao servidor.
        self._em_leitura: set = set()
        self.indice = 0
        self.imagem = None
        self.matriz: Optional[np.ndarray] = None
        #: A página no modelo; `None` enquanto nada dela foi gravado (nasce na 1ª mudança).
        self.modelo: Optional[Pagina] = None
        #: O glifo em revisão, os pulados e a seleção do modo de treino, por gid.
        self.atual: Optional[int] = None
        self.pulados: set = set()
        #: Conta as sessões do Documento confirmadas: a chave do passo do desfazer de cada
        #: uma, que o ensinar do Ctrl+Enter emenda.
        self._numero_da_sessao = 0
        #: Chamado antes de sair da página aberta (outra página, o Ctrl+T): a janela confirma
        #: ali a sessão aberta do Documento (§6.3), que não pode ficar para depois.
        self.antes_de_sair_da_pagina: Optional[Callable[[], None]] = None
        #: Feito com a matriz da página na thread que a renderiza (a da pré-carga, quase
        #: sempre): a janela põe aqui a `QImage` dela, e a conversão sai da interface.
        self.preparar_imagem: Optional[Callable[[np.ndarray], object]] = None
        #: +1 ou -1: o sentido do último passo entre páginas, o da pré-carga.
        self._sentido = 1
        #: O livro tem figurinas lidas (o modo "livro" das peças, §6.4): o "sim" fica guardado
        #: até outro projeto; sem ele (None), o resumo das páginas é consultado de novo.
        self._livro_tem_figurinas: Optional[bool] = None
        #: (box, virtual, letra): o box marcado ao lado da letra virtual. Se o usuário o
        #: confirma com essa letra (Enter ou Shift+Enter), o virtual sai no mesmo passo.
        self._letra_que_faltava: Optional[Tuple[int, int, str]] = None
        #: As sessões do Documento confirmadas que esperam a vez na fila, como [corpo, já
        #: rodou?] (o Ctrl+T espera; fechar o projeto as aplica na hora).
        self._sessoes_na_fila: List[list] = []
        #: A ordem da fila de glifos (§8.1): "confianca" (o menos confiável primeiro, os
        #: pulados no fim) ou "leitura" (a ordem da página).
        self.ordem_da_fila = "confianca"
        #: gid -> (o que decide, se ele vai para a fila): a fila julga de novo só os glifos
        #: que mudaram (a leitura, a fonte, a confiança ou o revisado), e todos quando o
        #: limiar muda.
        self._pendencia: dict = {}
        self._limiar_da_pendencia = None
        #: Na ordem de leitura: (página, posição na ordem da página) do último glifo mostrado,
        #: para a decisão seguir em frente mesmo quando o glifo sai (descartar, juntar).
        self._lugar_de_leitura = (-1, 0)
        #: (chave, gids) da última conta das margens corridas (`gids_de_margem`).
        self._margens: tuple = (None, frozenset())
        self.selecao: set = set()
        #: O desfazer do projeto (§14.2), da sessão.
        self.historico = hs.HistoricoDoProjeto()
        #: O lote está lendo o livro (a janela mostra o progresso e o ✕; nada é recusado).
        self.lote_rodando = False
        #: Muda a cada `ligar`: a tarefa pedida para outro projeto não roda nem aplica.
        self.geracao = 0
        #: O glifo em revisão foi escolhido pelo usuário (e não posto pela fila).
        self.escolhido = False
        self.eventos.ligar("padroes_mudaram", self._sincronizar_padroes)

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
        """Os gids a revisar (§8.1): do menos confiável ao mais, com os pulados no fim; na
        ordem de leitura (`ordem_da_fila`), na ordem da página; por caractere, agrupados pela
        leitura (os sem leitura no fim) e, em cada grupo, do menos confiável ao mais. O glifo
        `revisado` (visto e aceito no Documento, §6.3) não volta."""
        if self.leitor is None or self.modelo is None:
            return []
        boxes = self.modelo.boxes
        indices = self._pendentes()
        if self.ordem_da_fila == "leitura":
            return [boxes[i].gid for i in indices]
        if self.ordem_da_fila == "caractere":
            indices = sorted(indices, key=lambda i: (boxes[i].entry.char or "\uffff",
                                                     round(boxes[i].entry.confidence, 2), i))
        else:
            indices = sorted(indices, key=lambda i: (round(boxes[i].entry.confidence, 2), i))
        fila = [boxes[i].gid for i in indices]
        return [g for g in fila if g not in self.pulados] + [g for g in fila if g in self.pulados]

    def _pendentes(self) -> List[int]:
        """Os índices dos glifos que vão para a fila, na ordem da página. Só os glifos que
        mudaram são julgados de novo (§8.1: a fila recalculada só para os gids tocados)."""
        limiares = self.leitor.limiares
        chave = limiares.revisao                 # o único limiar que decide a fila
        anterior = self._pendencia if chave == self._limiar_da_pendencia else {}
        nova, indices = {}, []
        for i, box in enumerate(self.modelo.boxes):
            e = box.entry
            estado = (e.char, e.source, e.confidence, box.revisado)
            visto = anterior.get(box.gid)
            if visto is not None and visto[0] == estado:
                pendente = visto[1]
            else:
                pendente = not box.revisado and precisa_revisao(e.char, e.source, e.confidence,
                                                                limiares)
            nova[box.gid] = (estado, pendente)
            if pendente:
                indices.append(i)
        self._pendencia, self._limiar_da_pendencia = nova, chave
        return indices

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

    def linhas_dos_diagramas(self) -> List[List[lc.Lance]]:
        """A primeira linha de lances do texto que segue cada diagrama (§10), na ordem de
        `diagramas`, para a conferência validar a posição enquanto ela é corrigida."""
        if self.modelo is None or not self.modelo.tabuleiros:
            return []
        pagina = self.modelo.instantaneo()
        pagina.diagramas = dg.com_ids(self.diagramas)
        idioma = self.projeto.dados.idioma if self.projeto is not None else "pt"
        textos = lc.textos_depois(tx.montar(pagina))
        return [lc.primeira_linha(textos.get(d.id, ""), idioma) for d in pagina.diagramas]

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
        return self.padroes_de(self.leitor)

    @staticmethod
    def padroes_de(leitor) -> frozenset:
        if leitor is None:
            return frozenset()
        return frozenset(c for v in leitor.padroes_por_caractere().values() for c in v)

    # ------------------------------------------------------------------
    # Projeto e páginas
    # ------------------------------------------------------------------
    def ligar(self, projeto, fonte, leitor, servidor: Optional[sl.ServidorDeLeitura] = None
              ) -> None:
        """O projeto aberto, a fonte das páginas e o leitor (os modelos já carregados; ou,
        com o `servidor`, só os padrões do livro). O servidor do projeto anterior fecha."""
        self._livro_tem_figurinas = None
        self._sessoes_na_fila = []              # a fila do projeto anterior foi esvaziada
        self._letra_que_faltava = None
        if self.servidor is not None and self.servidor is not servidor:
            self.servidor.fechar()
        self.servidor = servidor
        self._enviados = self.padroes_de(leitor) if servidor is not None else frozenset()
        self._em_leitura = set()
        self.geracao += 1
        self.lote_rodando = False               # o lote do projeto anterior não vale aqui
        self.projeto, self.fonte, self.leitor = projeto, fonte, leitor
        #: As páginas renderizadas mais recentes e a pré-carga da seguinte (§14.1).
        self.cache = (pg.CacheDePaginas(fonte, preparar=self.preparar_imagem)
                      if fonte is not None else None)
        self._sentido = 1
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
        if indice != self.indice and self.antes_de_sair_da_pagina is not None:
            self.antes_de_sair_da_pagina()
        try:
            imagem, matriz = self.cache.pagina(indice)
        except OSError as erro:
            self.eventos.emitir("aviso", "Página", str(erro))
            return False
        if indice != self.indice:
            self._sentido = 1 if indice > self.indice else -1
        self.indice, self.imagem, self.matriz = indice, imagem, matriz
        self._letra_que_faltava = None
        if visita:
            self._registrar_visita(indice)
        self.modelo = self.projeto.carregar_modelo(indice)
        self.atual, self.pulados, self.selecao = None, set(), set()
        self.eventos.emitir("pagina_trocou")
        self.eventos.emitir("glifos_mudaram", None)
        if self.boxes:
            self.ir_ao_primeiro_pendente()
            self._ler_os_aguardando(self.modelo, indice, None)
            if not self.reconhecida:
                self._avisar(f"Página com {len(self.boxes)} glifo(s) marcados à mão e ainda não "
                             "reconhecida. O {reconhecer_pagina} reconhece o resto e mantém "
                             "os quadros.", 10000)
        else:
            self.eventos.emitir("atual_mudou")
        self.eventos.emitir("acoes_mudaram")
        return True

    def precarregar_seguinte(self) -> None:
        """Renderiza a próxima página no sentido em que se anda (a seguinte, ou a anterior
        depois de um PgUp), a mais provável, noutra thread. A janela chama depois de pintar a
        atual: dentro do `ir_para`, a pré-carga disputava a CPU com a conversão e a pintura
        da página pedida, e a troca fora do cache ficava ~60 ms mais lenta."""
        if self.cache is not None and self.fonte is not None:
            self.cache.precarregar(self.proxima_provavel)

    @property
    def proxima_provavel(self) -> int:
        """A página que a pré-carga prepara: a vizinha no sentido do último passo; na ponta do
        livro (o Home deixa o sentido para trás na primeira), a do outro lado."""
        alvo = self.indice + self._sentido
        total = self.fonte.total if self.fonte is not None else 0
        return alvo if 0 <= alvo < total else self.indice - self._sentido

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
        if self.antes_de_sair_da_pagina is not None:   # a sessão aberta entra antes
            self.antes_de_sair_da_pagina()
        if self._sessoes_na_fila:
            self._avisar("A edição do texto ainda espera a vez dela na fila: marque a página "
                         "como verificada depois que ela entrar.", 8000)
            return
        if self.modelo is None or self.modelo.estado not in LIDAS:
            self._avisar("Reconheça a página antes de marcá-la como verificada "
                         "({reconhecer_pagina}).", 6000)
            return

        def corpo():
            antes = self._instantaneo()
            self._mudou(self.modelo, self.indice, "Página verificada", antes, evento="verificar")
            self.eventos.emitir("pagina_verificada", self.indice)
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

        def falhou_guardado(mensagem: str) -> None:
            if self.geracao == geracao and falhou is not None:
                falhou(mensagem)

        self.executar(titulo, guardado, falhou=falhou_guardado if falhou else None,
                      progresso=progresso, leve=leve)

    def _agora(self) -> bool:
        """Uma edição pode rodar na hora: nada roda, ou só a propagação de um Enter (que lê
        com uma cópia dos padrões e só entra nos glifos que não mudaram, §14.2)."""
        so_leves = getattr(self.executar, "so_leves", None)
        return so_leves() if so_leves is not None else not getattr(self.executar, "ocupado", False)

    def _editar(self, titulo: str, corpo, *, precisa_de_glifos: bool = True,
                nao_rodou=None, so_nesta_pagina: bool = True) -> None:
        """Uma edição: na hora, se nada prende o leitor (`_agora`); senão na fila, e `corpo()`
        roda na vez dela, se a página ainda é a mesma (se não é, avisa que a edição foi
        descartada; com `so_nesta_pagina=False`, roda assim mesmo: o corpo sabe a página
        dele). `nao_rodou()`, se o corpo não rodou."""
        if self._agora():
            if self._pode_editar(precisa_de_glifos):
                corpo()
            elif nao_rodou is not None:
                nao_rodou()
            return
        indice = self.indice

        def preparar():
            if self.indice != indice and not so_nesta_pagina:
                if self.pronto:
                    corpo()
                    return None
            elif self.indice != indice:
                self._avisar(f"{titulo}: descartado, porque a página mudou (era a {indice + 1}) "
                             "antes da vez dele na fila.", 8000)
            elif self._pode_editar(precisa_de_glifos):
                corpo()
                return None
            if nao_rodou is not None:
                nao_rodou()
            return None
        self.tarefa(titulo, preparar, falhou=self._falhou(titulo))

    # ------------------------------------------------------------------
    # Os comandos que leem (fora da thread da interface)
    # ------------------------------------------------------------------
    def reconhecer(self) -> None:
        """F5: segmenta pelas áreas, lê e acha os diagramas. Mantém os glifos marcados à mão
        de uma página ainda não reconhecida; numa já reconhecida, os glifos novos herdam o
        gid (e as decisões) de quem estava no mesmo lugar (`modelo.reconciliar`)."""
        if not self._pode_ler() or self.servidor_parado():
            return
        indice = self.indice
        self.tarefa("Reconhecendo a página", lambda: self._preparar_reconhecer(indice),
                    falhou=self._falhou("Reconhecer página"))

    def reconhecer_zona(self, zona) -> None:
        """Ctrl+Shift+R: reconhece somente uma zona e conserva o restante da página."""
        if not self._pode_ler() or self.servidor_parado():
            return
        indice = self.indice
        self.tarefa("Reconhecendo a área",
                    lambda: self._preparar_reconhecer(indice, zona),
                    falhou=self._falhou("Reconhecer área"))

    def _preparar_reconhecer(self, indice: int, zona=None):
        if indice != self.indice or not self._pode_ler(avisar=False):
            return None
        pagina = self._pagina_para_editar()
        imagem, leitor = self.imagem, self.leitor
        zonas = [zona] if zona is not None else list(pagina.zonas)
        antes = self._instantaneo()
        marcados = pg.a_manter_na_releitura(pagina.boxes, pagina.estado in LIDAS)   # §4.6
        if zona is not None:
            marcados = [b for b in marcados
                        if zona.contem((b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2)]
        servidor = self._servidor_para_pedir()

        def trabalho(progresso):
            if servidor is None:
                return sl.ler_pagina(imagem, zonas, marcados, leitor, progresso=progresso)
            try:
                lida = servidor.chamar("ler_pagina", (imagem, zonas, marcados),
                                       timeout=TEMPO_DO_PEDIDO)
            except sl.Cancelado:                # o projeto fechou: nada a pôr
                return None
            sl.registrar_procedencia(lida.boxes, lida.amostras)
            return lida

        def pronto(lida: Optional[sl.PaginaLida]):
            if lida is None:
                return
            lidos = lida.diagramas
            de_antes = list(pagina.boxes)
            estilos = {id(entry): md.Estilo(negrito=negrito)
                       for entry, negrito in zip(lida.boxes, lida.negritos)
                       if negrito is not None}
            depois = list(lida.boxes)
            if zona is not None:
                from core.services.box_service import BoxService

                fora = [b.entry for b in pagina.boxes
                        if not zona.contem((b.entry.x1 + b.entry.x2) / 2,
                                          (b.entry.y1 + b.entry.y2) / 2)]
                depois = BoxService.sort_boxes_reading_order(fora + depois)
            novos, dif = reconciliar(pagina.boxes, depois, pagina.alocar,
                                     procedencia.amostra_de,
                                     estilo_de=lambda entry: estilos.get(id(entry)),
                                     iou_minimo=IOU_DA_RELEITURA)
            pagina.aplicar(dif, novos)
            if dif.caidas:                      # §4.6: o que não pôde seguir os glifos novos
                self.eventos.emitir("resultado", "Reconhecer a página", (
                    f"Página {indice + 1}: decisões que não puderam seguir os glifos relidos: "
                    + "; ".join(descrever_caidas(dif.caidas, de_antes))))
            tabuleiros = [tuple(int(v) for v in t) for t in lida.tabuleiros]
            if zona is not None:
                tabuleiros = [t for t in pagina.tabuleiros
                              if not zona.contem((t[0] + t[2]) / 2, (t[1] + t[3]) / 2)] + tabuleiros
            pagina.tabuleiros = tabuleiros
            # A conferência de antes vale mais que a releitura do mesmo tabuleiro.
            pagina.diagramas = dg.mesclar(lidos, dg.para_caixas(pagina.tabuleiros,
                                                                pagina.diagramas))
            if pagina is self.modelo:
                self.atual, self.pulados, self.selecao = None, set(), set()
            descricao = "Reconhecer a área" if zona is not None else "Reconhecer a página"
            self._mudou(pagina, indice, descricao, antes, evento="reconhecer")
            self.eventos.emitir("pagina_reconhecida", indice)
            if pagina is self.modelo:
                self.ir_ao_primeiro_pendente()
                resumo = pg.resumir(pagina.entries(), leitor)
                areas = f", pelas {len(zonas)} área(s) da página" if zonas else ""
                self._avisar(f"{resumo.boxes} boxes, {resumo.pendentes} a revisar, "
                             f"{len(pagina.tabuleiros)} diagrama(s){areas}.", 8000)

        return trabalho, pronto

    def reler_pendentes(self, tudo: bool = False) -> None:
        """Lê de novo os pendentes (ou todos os não manuais), com os padrões de agora."""
        if not self._pode_ler() or not self.boxes or self.servidor_parado():
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

        servidor = self._servidor_para_pedir()

        def trabalho(progresso):
            if servidor is None:
                resumo = pg.ler_boxes(imagem, lidos, leitor, so_pendentes=not tudo,
                                      progresso=progresso)
                return lidos, resumo
            try:
                relidos, amostras, resumo = servidor.chamar(
                    "reler_boxes", (imagem, lidos, not tudo), timeout=TEMPO_DO_PEDIDO)
            except sl.Cancelado:                # o projeto fechou: nada a pôr
                return None
            sl.registrar_procedencia(relidos, amostras)
            return relidos, resumo

        def pronto(resultado):
            if resultado is None:
                return
            relidos, resumo = resultado
            foto = pagina.instantaneo()
            dif = ed.aplicar_leituras(pagina, antes, relidos)
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
                               propagar=False, gid=gid, efeito=antes[i].estilo)
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
        for char, gids in por_char.items():
            self._tirar_a_letra_que_faltava(pagina, gids, char)
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
                return pg.propagar_padroes(imagem, lidos, foto_do_leitor,
                                           efeitos=[b.estilo for b in antes])

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

    def ler_os_aguardando(self) -> None:
        """Os glifos aguardando da página aberta (os modelos ficaram prontos, ou a página
        abriu): lidos fora do desfazer."""
        if self.modelo is not None:
            self._ler_os_aguardando(self.modelo, self.indice, None)

    def _ler_os_aguardando(self, pagina: Pagina, indice: int,
                           transacao: Optional[hs.Transacao]) -> None:
        """§11: os glifos que a interface não leu (o leitor dela só tem os padrões do livro)
        vão ao servidor, só os recortes, sem passar pela fila de tarefas (a releitura não
        espera um F5 nem o lote). A resposta entra nos glifos que não mudaram desde o pedido
        e emenda a `transacao` da edição que os criou, para o refazer os trazer já lidos.
        Sem ela (a página abriu, os modelos ficaram prontos, um desfazer os trouxe de volta),
        a leitura entra fora do desfazer: ela não é decisão de ninguém, e a pré-condição do
        desfazer a aceita (`historico.lido_depois`). Com o servidor carregando (ou reabrindo
        depois de uma queda), o pedido espera na fila do filho; parado, os glifos ficam
        aguardando."""
        servidor = self.servidor
        if servidor is None or servidor.parado \
                or pagina is not self.modelo or indice != self.indice:
            return
        antes = tuple(pagina.boxes)
        indices = [i for i, b in enumerate(antes)
                   if pg.aguardando(b.entry) and b.gid not in self._em_leitura]
        if not indices:
            return
        entradas = [b.entry for b in antes]
        gids = {antes[i].gid for i in indices}
        self._em_leitura |= gids
        geracao = self.geracao
        recortes = pg.recortes_para_ler(self.imagem, entradas, indices)
        self._sincronizar_padroes()

        def chegou(pedido: sl.Pedido) -> None:
            if self.geracao != geracao:
                return                          # outro projeto
            self._em_leitura -= gids
            if not pedido.ok:
                if not pedido.cancelado:
                    log.warning("a leitura dos glifos aguardando falhou: %s", pedido.resultado)
                return
            lidos = list(entradas)
            for i, leitura in zip(indices, pedido.resultado):
                lidos[i] = ed.copia(entradas[i])
                pg.por_leitura(lidos[i], leitura)
            foto = pagina.instantaneo()
            dif = ed.aplicar_leituras(pagina, antes, lidos)
            if dif.vazia:
                return
            if transacao is not None and not transacao.invalidada:
                self._emendar(transacao, foto, pagina)
            self._gravar(pagina)
            if pagina is self.modelo:
                self.eventos.emitir("glifos_mudaram", dif.mudados)
                if self.atual is None:
                    self.ir_ao_primeiro_pendente()
            self.eventos.emitir("acoes_mudaram")

        servidor.pedir("ler_recortes", recortes,
                       ao_terminar=lambda pedido: self.executar.na_interface(
                           lambda: chegou(pedido)))

    def servidor_parado(self) -> bool:
        """O servidor desistiu (caiu duas vezes): o comando que lê avisa e não roda."""
        if self.servidor is None or not self.servidor.parado:
            return False
        self._avisar("O servidor de leitura parou. Reabra o projeto (Projeto › Abrir) para "
                     "voltar a ler as páginas.", 8000)
        return True

    def _servidor_para_pedir(self) -> Optional[sl.ServidorDeLeitura]:
        """O servidor, com os padrões de agora já mandados (os deltas valem a partir do
        pedido seguinte, §11); None sem servidor."""
        self._sincronizar_padroes()
        return self.servidor

    def _sincronizar_padroes(self) -> None:
        """Manda ao servidor as amostras criadas e apagadas desde a última vez."""
        if self.servidor is None or self.leitor is None:
            return
        agora = self.padroes()
        criados, apagados = agora - self._enviados, self._enviados - agora
        if criados or apagados:
            padroes = self.leitor.padroes
            self.servidor.enviar_padroes([(c, padroes.altura_de(c), padroes.efeito_de(c))
                                          for c in sorted(criados)],
                                         sorted(apagados))
            self._enviados = agora

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
            self._tirar_a_letra_que_faltava(self.modelo, alvos, char)
            self.pulados.difference_update(alvos)
            self.selecao = set()
            self._mudou(self.modelo, self.indice, f"Corrigir para '{char}'", antes)
            self.eventos.emitir("selecao_mudou")
            self.ir_ao_primeiro_pendente()
        self._editar("Corrigindo", corpo)

    def corrigir_no_livro(self, alvos, char: str, recortes=None) -> None:
        """A Galeria (§8.2): `char` nos glifos `alvos` (página -> gids), em quantas páginas
        forem, num passo do desfazer e sem ensinar (digitar, Shift+Enter). Com `recortes`
        ((página, gid) -> o recorte do glifo), cada um também é ensinado: uma amostra por
        glifo (Enter). Os glifos ficam `manual`; a página editada sai de verificada."""
        from core import proporcao

        from abbychess.leitor import nome_de_origem

        alvos = {int(i): list(g) for i, g in alvos.items() if g}
        if not alvos or not char:
            return

        def corpo():
            n = sum(len(g) for g in alvos.values())
            acao = "Ensinar" if recortes else "Corrigir para"
            transacao = hs.Transacao(f"{acao} '{char}' ({n} glifo(s), Galeria)")
            aberta, feitos = False, 0
            for indice, gids in sorted(alvos.items()):
                if self.modelo is not None and indice == self.indice:
                    pagina, aberta = self.modelo, True
                else:
                    pagina = self.projeto.pagina_para_editar(indice)
                vivos = set(pagina.vivos)
                gids = [g for g in gids if g in vivos]
                if not gids:
                    continue
                antes = pagina.instantaneo()
                referencia = (proporcao.altura_de_referencia(pagina.entries())
                              if recortes else None)
                for gid in gids:
                    recorte = (recortes or {}).get((indice, gid))
                    if recorte is not None and self.leitor is not None:
                        caminho = self.leitor.ensinar(
                            recorte, char, altura_de_referencia=referencia,
                            origem=nome_de_origem(self.projeto.dados.nome, indice,
                                                  pagina.indice_de(gid), gid))
                        transacao.amostras_criadas.append(self.leitor.padroes.guardar(caminho))
                    ed.corrigir(pagina, gid, char)
                    feitos += 1
                pagina.estado = proximo_estado(pagina.estado, "editar")
                transacao.paginas[pagina.pid] = hs.mudanca(antes, pagina.instantaneo())
                self._gravar(pagina)
            if not transacao.paginas:
                self._avisar("Os glifos escolhidos na Galeria saíram das páginas.", 6000)
                return
            self.historico.registrar(transacao)
            if transacao.amostras_criadas:
                self.eventos.emitir("padroes_mudaram")
            if aberta:
                self.selecao = set()
                self.eventos.emitir("glifos_mudaram", None)
                self.eventos.emitir("selecao_mudou")
            self.eventos.emitir("acoes_mudaram")
            self.eventos.emitir("galeria_aplicada", feitos, len(transacao.paginas),
                                bool(transacao.amostras_criadas))
        self._editar("Galeria", corpo, so_nesta_pagina=False, precisa_de_glifos=False)

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
            novo = dif.novos[0].gid
            vizinho = ag.virtual_vizinho(pagina, novo)
            self._letra_que_faltava = None if vizinho is None else (novo, *vizinho)
            if vizinho is not None:             # a letra que faltava, digitada no Documento
                mensagem = (f"Glifo marcado{extra}. Se é o '{vizinho[1]}' que faltava ali, Enter "
                            "o confirma, e a letra virtual sai.")
            else:
                mensagem = f"Glifo marcado{extra}. Digite o caractere e Enter."
            self._depois_de_editar(novo, "Marcar glifo", antes, mensagem, evento="marcar")
            if vizinho is not None:
                self.eventos.emitir("caractere_sugerido", vizinho[1])
        self._editar("Marcando", corpo, precisa_de_glifos=False)

    def confirmar_sessao(self, unidades, novo: str, *, ensinar_gid: Optional[int] = None,
                         original: Optional[str] = None, fixos=(), depois=None,
                         fim_de_linha: bool = False, agora: bool = False) -> None:
        """§6.3: a sessão do Documento confirmada (Enter, Shift+Enter, Ctrl+Enter, sair dela):
        as unidades originais dela e o texto de agora viram as operações da tabela, num passo
        do desfazer, e os glifos dela com leitura ficam `revisado`. Sem mudança, é aceitar a
        palavra. O que é do passo G recusa tudo (`sessao_recusada`, com a mensagem); o que
        muda a estrutura avisa (`estrutural`). `ensinar_gid` (Ctrl+Enter) ensina o glifo sob o
        cursor no mesmo passo do desfazer (`ss.LETRA_NOVA`: uma letra digitada agora, que não
        ensina). `fixos`: os pares que nenhuma edição tocou (`sessao.alinhar`). `depois()`
        roda quando a edição entrou na página (na hora, ou na vez dela na fila).
        `fim_de_linha`: a sessão termina numa quebra de linha impressa. `agora`: aplica já,
        sem a fila (fechar o projeto, que esvazia a fila)."""
        unidades = list(unidades)
        original = original if original is not None else "".join(u.texto for u in unidades)
        dados = self.projeto.dados if self.projeto is not None else None
        indice, pagina = self.indice, self.modelo
        if dados is not None:
            novo = ss.com_figurinas(novo, original, dados.idioma,
                                    self._modo_das_pecas(dados.notacao, pagina))

        def corpo():
            # A página da sessão, mesmo que o usuário já tenha ido a outra (a sessão confirma
            # ao sair da página, e a edição pode esperar a vez dela na fila).
            aberta = pagina is self.modelo
            virtuais = {v.gid for v in pagina.decisoes.virtuais}
            if not aberta and self.projeto.modelo_em_memoria(indice) is not pagina:
                # A página saiu da memória e foi lida de novo (o lote, por exemplo): a
                # edição no objeto velho seria gravada por cima da nova.
                self.eventos.emitir("sessao_recusada", "a página mudou antes da confirmação")
                return
            if any(u.glifo and u.gid not in pagina.vivos | virtuais for u in unidades):
                self.eventos.emitir("sessao_recusada", "a página mudou antes da confirmação")
                return
            try:
                plano = ss.planejar(unidades, novo, fixos, fim_de_linha)
            except ss.Recusa as recusa:
                self.eventos.emitir("sessao_recusada", str(recusa))
                return
            antes = Antes(pagina.instantaneo(), self.padroes())
            vivos_antes = set(pagina.vivos)
            try:
                ss.aplicar(pagina, plano, self.imagem if aberta else None, self.leitor)
            except Exception:
                # Nada da sessão fica pela metade: a página volta ao instantâneo (os gids já
                # alocados não voltam: um gid nunca se repete).
                pagina.boxes, pagina.decisoes = list(antes.pagina.boxes), antes.pagina.decisoes
                log.exception("a sessão do Documento falhou ao aplicar")
                self.eventos.emitir("sessao_recusada", "a edição falhou e foi desfeita")
                return
            saiu = vivos_antes - pagina.vivos
            if aberta:
                self.pulados -= saiu
                self.selecao -= saiu
                if self.atual in saiu:
                    self.atual = None
            palavra = " ".join(novo.split())
            descricao = (f"Editar '{palavra[:40]}'" if plano.muda
                         else f"Aceitar '{' '.join(original.split())[:40]}'")
            self._numero_da_sessao += 1
            chave = ("sessao", self._numero_da_sessao)   # o Ctrl+Enter emenda nesta
            self._mudou(pagina, indice, descricao, antes, juntar=chave)
            tinta = aberta and bool(plano.virtuais) and self._tinta_sem_box(pagina, plano)
            aviso = plano.estrutural(*(["há tinta sem box aqui: Ctrl+M marca o quadro"]
                                       if tinta else []))
            if aviso:
                self.eventos.emitir("estrutural", aviso)
            if aberta and ensinar_gid is not None:
                self._ensinar_do_documento(ensinar_gid, chave)
            if aberta and depois is not None:
                depois()
        # A edição que não rodou (a página sem imagem, ou outra na vez dela): o Documento
        # volta ao modelo.
        if pagina is None:
            self.eventos.emitir("sessao_recusada", "a página não pode ser editada agora")
            return
        if agora:                               # fechar o projeto: a fila vai ser esvaziada
            corpo()
            return
        if self._agora():
            self._editar("Editando o texto", corpo, so_nesta_pagina=False,
                         nao_rodou=lambda: self.eventos.emitir(
                             "sessao_recusada", "a página não pode ser editada agora"))
            return
        espera = [corpo, False]
        self._sessoes_na_fila.append(espera)

        def rodar(funcao):
            def rodando():
                if espera[1]:                   # já aplicada (fechar o projeto)
                    return
                espera[1] = True
                self._sessoes_na_fila.remove(espera)
                funcao()
            return rodando
        self._editar("Editando o texto", rodar(corpo), so_nesta_pagina=False,
                     nao_rodou=rodar(lambda: self.eventos.emitir(
                         "sessao_recusada", "a página não pode ser editada agora")))

    def novo_paragrafo(self, gid: Optional[int]) -> None:
        """Começa um parágrafo antes do glifo indicado, num passo do desfazer."""
        if gid is None or self.modelo is None:
            return

        def corpo():
            antes = Antes(self.modelo.instantaneo(), self.padroes())
            ed.paragrafo(self.modelo, gid)
            self._mudou(self.modelo, self.indice, "Novo parágrafo", antes)
        self._editar("Criando parágrafo", corpo)

    def alternar_estilo(self, gids: Sequence[int], campo: str) -> None:
        """Alterna negrito, itálico ou sublinhado na seleção do Documento."""
        gids = [g for g in dict.fromkeys(gids)
                if self.modelo is not None and g in self.modelo.vivos]
        if not gids or self.modelo is None:
            return

        def corpo():
            antes = Antes(self.modelo.instantaneo(), self.padroes())
            ed.estilizar(self.modelo, gids, campo)
            self._mudou(self.modelo, self.indice, f"Alternar {campo}", antes)
        self._editar(f"Aplicando {campo}", corpo)

    def aplicar_as_sessoes_na_fila(self) -> None:
        """Fechar o projeto (a fila vai ser esvaziada): as sessões do Documento que esperavam
        a vez entram agora, em vez de se perder."""
        for espera in list(self._sessoes_na_fila):
            if not espera[1]:
                espera[1] = True
                self._sessoes_na_fila.remove(espera)
                espera[0]()

    def _tirar_a_letra_que_faltava(self, pagina: Pagina, gids, char: str) -> None:
        """O box marcado ao lado da letra virtual foi confirmado com a letra dela: ele é a
        letra que faltava, e o virtual sai (no passo do desfazer da confirmação)."""
        pendente, self._letra_que_faltava = self._letra_que_faltava, None
        if pendente is None:
            return
        box, virtual, letra = pendente
        if (box in gids and char == letra and pagina is self.modelo
                and virtual in {v.gid for v in pagina.decisoes.virtuais}):
            ed.apagar_virtual(pagina, virtual)

    def _modo_das_pecas(self, notacao: str, pagina: Optional[Pagina]) -> str:
        """O modo das peças nos lances (§6.4). "livro": figurinas se o livro tem figurinas
        lidas (a página aberta ou, uma vez por projeto, as outras páginas lidas), senão
        letras; uma página de prosa num livro de figurinas segue o livro."""
        if notacao != "livro":
            return notacao
        if not self._livro_tem_figurinas and pagina is not None:
            if ss.modo_da_pagina("livro", (b.entry.char for b in pagina.boxes)) == "figurinas":
                self._livro_tem_figurinas = True
        if not self._livro_tem_figurinas:       # o "não" não fica guardado: o lote lê mais
            self._livro_tem_figurinas = self._figurinas_nas_paginas_lidas() or None
        return "figurinas" if self._livro_tem_figurinas else "letras"

    def _figurinas_nas_paginas_lidas(self) -> bool:
        """Pelo resumo das páginas no `livro.json` (sem abrir nenhuma; uma página gravada
        antes do D1 não tem o campo e conta quando for gravada de novo)."""
        if self.projeto is None:
            return False
        return any(r.get("figurinas") for r in self.projeto.resumo_do_livro().values())

    def _tinta_sem_box(self, pagina: Pagina, plano) -> bool:
        """Há tinta sem box onde uma letra que faltou entrou (a letra que a segmentação não
        viu): a faixa ao lado do glifo âncora, do tamanho das letras, até o vizinho da linha."""
        if self.matriz is None:
            return False
        caixas = {b.gid: b.entry for b in pagina.boxes}
        for letras, (lado, ancora), _nova in plano.virtuais:
            e = caixas.get(ancora)
            if e is None:
                continue
            largura = max(4, (e.x2 - e.x1)) * len(letras)
            mesma_linha = [b for b in caixas.values() if b is not e and b.y1 < e.y2 and b.y2 > e.y1]
            if lado == "depois":
                x1 = e.x2 + 1
                x2 = min([x1 + largura] + [b.x1 for b in mesma_linha if b.x1 >= e.x2])
            else:
                x2 = e.x1 - 1
                x1 = max([x2 - largura] + [b.x2 for b in mesma_linha if b.x2 <= e.x1])
            recorte = self.matriz[max(0, e.y1):e.y2, max(0, x1):max(0, x2)]
            if recorte.size and int((recorte < 128).sum()) >= 12:
                return True
        return False

    def _ensinar_do_documento(self, gid: int, chave) -> None:
        """Ctrl+Enter: o glifo sob o cursor, ensinado com o caractere dele, no passo do
        desfazer da edição (`chave`)."""
        virtuais = {v.gid for v in self.modelo.decisoes.virtuais} if self.modelo else set()
        if gid == ss.LETRA_NOVA or gid in virtuais:
            self._avisar("Glifo sem tinta não ensina.", 6000)
            return
        if self.modelo is None or gid not in self.modelo.vivos or not self._pode_ler():
            return
        char = self.box(gid).char
        if not char:
            return
        self.escolher(gid)
        self.limpar_selecao()
        self.ensinar_gids({char: [gid]}, f"Ensinar '{char}'",
                          self._depois_de_ensinar(char, [gid]), juntar=chave)

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
                # Pelo pid (§12.4): a página pode ter mudado de posição desde a transação.
                posicao = self.projeto.posicao_do_pid(pid)
                if posicao is None:
                    raise hs.Recusa(f"a página {m.indice + 1} saiu do livro")
                pagina = (self.modelo if self.modelo is not None and self.modelo.pid == pid
                          else self.projeto.carregar_modelo(posicao))
                if pagina is None or pagina.pid != pid:
                    raise hs.Recusa(f"a página {posicao + 1} não é mais a da transação")
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
        posicoes = sorted(p for p in map(self.projeto.posicao_do_pid, transacao.paginas)
                          if p is not None)
        if aberta or not posicoes or not self.ir_para(posicoes[0]):
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
        self.ler_os_aguardando()                # o que voltou ainda sem leitura
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
        """Apaga amostras dos padrões do livro (§8.3), num passo do desfazer, e devolve à
        fila os glifos que elas leram: na página aberta, na hora; nas outras, pelo índice da
        busca, em segundo plano (`lidos_pelas_amostras`), emendando a mesma transação. O
        glifo devolvido fica com a leitura e perde a fonte (o padrão que a dava sumiu: ele
        volta à fila); a página verificada atingida volta a `em_revisao`, com aviso. Desfazer
        o esquecer devolve as amostras e tira os glifos da fila de novo. Na fila de
        tarefas: o leitor não muda no meio de uma leitura."""
        if self.leitor is None:
            return
        caminhos = list(caminhos)

        def preparar():
            if self.leitor is None:
                return None
            nomes = {self._nome_da_amostra(c) for c in caminhos}
            apagadas = [self.leitor.padroes.guardar(c) for c in caminhos]
            for caminho in caminhos:
                self.leitor.esquecer(caminho)
            self.eventos.emitir("padroes_mudaram")
            transacao = hs.Transacao(f"Esquecer {len(caminhos)} amostra(s)",
                                     amostras_apagadas=apagadas)
            self.historico.registrar(transacao)
            devolvidos = {}
            if self.modelo is not None:
                n = self._devolver_a_fila(self.modelo, nomes, None, transacao)
                if n:
                    devolvidos[self.indice] = n
            self.eventos.emitir("acoes_mudaram")
            procurar = self.lidos_pelas_amostras
            if procurar is None:
                self._avisar_os_devolvidos(len(caminhos), devolvidos, completo=True)
                return None
            self._avisar(f"Esquecida(s) {len(caminhos)} amostra(s); procurando no livro os "
                         "glifos que ela(s) leram…", 0)
            procurar(nomes, lambda achados: self._devolver_no_livro(
                nomes, achados, transacao, devolvidos, len(caminhos)))
            return None
        self.tarefa("Esquecendo padrões", preparar, falhou=self._falhou("Esquecer padrões"))

    #: Quem acha, no livro, os glifos lidos por umas amostras (o índice da busca):
    #: `lidos_pelas_amostras(nomes, ao_terminar)`, com `ao_terminar({página: [gids]})`.
    lidos_pelas_amostras = None

    def aviso_de_ensino(self, char: str) -> Tuple[str, str]:
        """§8.3, ao digitar o caractere do glifo atual: o efeito ("Enter ensina 'l' · 23
        iguais nesta página": os glifos da página com a mesma leitura dele) e o conflito
        ("este glifo está a 0,08 de 14 amostras de '1'", ou "")."""
        if not char or self.modelo is None or self.atual is None or self.leitor is None:
            return "", ""
        i = self.indice_de(self.atual)
        if i is None:
            return "", ""
        entradas = self.modelo.entries()
        lida = entradas[i].char
        iguais = sum(1 for k, e in enumerate(entradas) if k != i and lida and e.char == lida)
        efeito = f"Enter ensina '{char}'" + (f" · {iguais} iguais nesta página" if iguais else "")
        conflito = ""
        if self.imagem is not None:
            from core import proporcao
            from abbychess.leitor import altura_relativa

            recorte = pg.recorte(self.imagem, entradas[i])
            referencia = proporcao.altura_de_referencia(entradas)
            achado = self.leitor.padroes.conflito(recorte, char,
                                                  altura_relativa(recorte, referencia),
                                                  self.leitor.limiares.conflito)
            if achado is not None:
                outro, n, distancia = achado
                conflito = (f"este glifo está a {distancia:.2f} de {n} amostra(s) de "
                            f"'{outro}'".replace(".", ","))
        return efeito, conflito

    def _nome_da_amostra(self, caminho) -> str:
        """O nome da amostra como o `Box.amostra` o guarda (relativo à pasta dos padrões)."""
        caminho = Path(caminho)
        try:
            return caminho.resolve().relative_to(
                Path(self.projeto.pasta_de_padroes).resolve()).as_posix()
        except ValueError:
            return caminho.name

    def _devolver_a_fila(self, pagina: Pagina, nomes: set, gids, transacao) -> int:
        """Os glifos da página lidos pelas amostras `nomes` (só os de `gids`, se vier)
        voltam à fila; a verificada volta a `em_revisao`. Emenda a `transacao` e grava.
        Devolve quantos voltaram."""
        alvo = None if gids is None else set(gids)
        antes = pagina.instantaneo()
        boxes, n = list(pagina.boxes), 0
        for k, box in enumerate(boxes):
            if box.amostra in nomes and (alvo is None or box.gid in alvo):
                entry = ed.copia(box.entry)
                entry.source = FONTE_NENHUMA
                procedencia.registrar(entry, procedencia.NENHUMA)
                boxes[k] = replace(box, entry=entry, amostra=None, revisado=False)
                n += 1
        if not n:
            return 0
        pagina.boxes = boxes
        estado = proximo_estado(pagina.estado, "esquecer_padrao")
        if estado != pagina.estado:
            pagina.estado = estado
            self.eventos.emitir("aviso", "Esquecer padrões",
                                f"Página {pagina.indice + 1}: estava verificada e voltou à "
                                "revisão (o padrão esquecido lia glifos dela).")
        self._emendar(transacao, antes, pagina)
        self._gravar(pagina)
        if pagina is self.modelo:
            if self.atual is None:
                self.ir_ao_primeiro_pendente()
            self.eventos.emitir("glifos_mudaram", None)
        return n

    def _devolver_no_livro(self, nomes, achados, transacao, devolvidos, quantas) -> None:
        """O resultado da procura no livro: as outras páginas, na mesma transação (se ela
        não foi desfeita no meio)."""
        if transacao.invalidada or self.projeto is None:
            return
        for indice, gids in sorted(achados.items()):
            if self.modelo is not None and indice == self.indice:
                pagina = self.modelo
            else:
                pagina = self.projeto.pagina_para_editar(indice)
            n = self._devolver_a_fila(pagina, nomes, gids, transacao)
            if n:
                devolvidos[indice] = devolvidos.get(indice, 0) + n
        self.eventos.emitir("acoes_mudaram")
        self._avisar_os_devolvidos(quantas, devolvidos, completo=True)

    def _avisar_os_devolvidos(self, quantas: int, devolvidos: dict, completo: bool) -> None:
        total = sum(devolvidos.values())
        if total:
            self._avisar(f"Esquecida(s) {quantas} amostra(s): {total} glifo(s) voltaram à fila "
                         f"em {len(devolvidos)} página(s) · Ctrl+Z desfaz.", 10000)
        else:
            self._avisar(f"Esquecida(s) {quantas} amostra(s); nenhum glifo lido por ela(s) · "
                         "Ctrl+Z desfaz.", 8000)

    def aplicar_limiares(self, limiares) -> None:
        """Os limiares do livro, gravados no projeto, e a fila refeita com eles (na fila: a
        fila de revisão não muda no meio de uma leitura). A mensagem vai para a barra; um
        problema ao gravar vai em `aviso`."""

        def preparar():
            if self.projeto is not None:
                self._aplicar_limiares(limiares)
            return None
        self.tarefa("Aplicando os limiares", preparar, falhou=self._falhou("Opções"))

    def definir_notacao(self, notacao: str) -> None:
        """Como o livro escreve as peças nos lances (§6.4), no projeto (gravado junto com os
        limiares, que vêm logo depois)."""
        if self.projeto is not None:
            self.projeto.dados.notacao = notacao

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
        if self.servidor is not None:
            self.servidor.trocar_limiares(limiares)
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

    def _pode_ler(self, avisar: bool = True) -> bool:
        return self.pronto and self.imagem is not None

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
        pagina.zonas = zn.vincular_legendas(pagina.zonas, pagina.diagramas)
        pagina.diagramas = lc.validar_pagina(pagina, self.projeto.dados.idioma)
        transacao = self.historico.registrar(hs.Transacao(
            descricao, {pagina.pid: hs.mudanca(antes.pagina, pagina.instantaneo())},
            amostras_criadas=criados, juntar=juntar))
        self._gravar(pagina)
        self._ler_os_aguardando(pagina, indice, transacao)
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
