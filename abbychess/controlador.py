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
from abbychess.modelo import (LIDAS, NAO_RECONHECIDA, Decisoes, Diferenca, Pagina,
                              proximo_estado, reconciliar)

log = logging.getLogger(__name__)


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

    def __call__(self, titulo: str, preparar, falhou=None, progresso=None) -> None:
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
        self.selecao: set = set()
        #: O desfazer de cada página desta sessão.
        self.historicos: Dict[int, hs.Historico] = {}
        #: O lote está lendo o livro: editar a página espera.
        self.lote_rodando = False
        #: Muda a cada `ligar`: a tarefa pedida para outro projeto não roda nem aplica.
        self.geracao = 0

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
        """Os gids a revisar, do menos confiável ao mais, com os pulados no fim."""
        if self.leitor is None or self.modelo is None:
            return []
        boxes = self.modelo.boxes
        fila = [boxes[i].gid for i in pg.fila_de_revisao(self.modelo.entries(), self.leitor)]
        return [g for g in fila if g not in self.pulados] + [g for g in fila if g in self.pulados]

    def alvos(self) -> List[int]:
        """O que a decisão vale: a seleção inteira, ou só o glifo em revisão (por gid, na
        ordem de leitura)."""
        if self.atual is None:
            return []
        escolhidos = self.selecao | {self.atual}
        return [g for g in self.gids if g in escolhidos]

    def posicao_do_atual(self) -> str:
        fila = self.fila()
        if self.atual in fila:
            return f"Pendente {fila.index(self.atual) + 1} de {len(fila)}"
        return "Box fora da fila (já confirmado ou confiável)"

    def texto(self) -> str:
        """O texto da página (com as decisões e os diagramas), como no painel de baixo."""
        if self.modelo is None or not (self.modelo.boxes or self.modelo.tabuleiros):
            return ""
        pagina = self.modelo.instantaneo()
        pagina.diagramas = self.diagramas
        return tx.texto(tx.montar(pagina), pagina.diagramas, modo=tx.SAN)

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
        self.projeto, self.fonte, self.leitor = projeto, fonte, leitor
        self.historicos = {}
        self.modelo, self.atual, self.pulados, self.selecao = None, None, set(), set()
        self.imagem = self.matriz = None

    def desligar(self) -> None:
        self.ligar(None, None, None)

    def ir_para(self, indice: int) -> bool:
        """Abre a página `indice` (0 = a primeira). Falso se não deu (fora do livro, ou a
        fonte não renderizou; o motivo vai em `aviso`)."""
        if self.fonte is None or not 0 <= indice < self.fonte.total:
            return False
        try:
            imagem = self.fonte.pagina(indice)
        except OSError as erro:
            self.eventos.emitir("aviso", "Página", str(erro))
            return False
        self.indice, self.imagem = indice, imagem
        self.matriz = np.asarray(imagem.convert("L"))
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
        self.eventos.emitir("atual_mudou")

    def clicar(self, indice: int) -> None:
        """O box clicado no visor (pela posição na lista)."""
        self.mostrar(self.gid_em(indice))

    def ir_ao_primeiro_pendente(self) -> None:
        fila = self.fila()
        self.atual = fila[0] if fila else None
        self.eventos.emitir("atual_mudou")

    def andar(self, passo: int) -> None:
        """Pula (passo > 0: o atual vai para o fim da fila) ou volta na fila."""
        fila = self.fila()
        if not fila:
            self.ir_ao_primeiro_pendente()
            return
        if passo > 0 and self.atual in fila:
            self.pulados.add(self.atual)
            self.mostrar(self.fila()[0])
            return
        posicao = fila.index(self.atual) if self.atual in fila else 0
        self.mostrar(fila[(posicao + passo) % len(fila)])

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
    def tarefa(self, titulo: str, preparar, falhou=None, progresso=None) -> None:
        """Põe `preparar` na fila do executor, presa ao projeto de agora: se outro projeto
        for aberto antes da vez dela (ou antes do fim do trabalho), ela não roda (ou o
        resultado não entra)."""
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

        self.executar(titulo, guardado, falhou=falhou, progresso=progresso)

    def _editar(self, titulo: str, corpo, *, precisa_de_glifos: bool = True) -> None:
        """Uma edição na fila: `corpo()` roda na vez dela, se a página ainda é a mesma."""
        indice = self.indice

        def preparar():
            if self.indice == indice and self._pode_editar(precisa_de_glifos):
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
        marcados = [] if pagina.estado in LIDAS else [ed.copia(b.entry) for b in pagina.boxes]

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

    def _preparar_reler(self, indice: int, tudo: bool):
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
            dif = ed.aplicar_leituras(pagina, antes, lidos)
            if not dif.vazia:
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
        def depois(resolvidos: int) -> None:
            self.pulados.difference_update(alvos)
            self.selecao = set()
            self.eventos.emitir("selecao_mudou")
            self.ir_ao_primeiro_pendente()
            amostras = f" com {len(alvos)} amostras" if len(alvos) > 1 else ""
            extra = f" e resolveu mais {resolvidos} na página" if resolvidos else ""
            self._avisar(f"Padrão '{char}' ensinado{amostras}{extra}.", 5000)
        return depois

    def ensinar_gids(self, por_char: Dict[str, Sequence[int]], descricao: str,
                     depois: Optional[Callable[[int], None]] = None, *, juntar=None) -> None:
        """Ensina cada grupo de gids como o caractere dele e propaga uma vez por grupo.
        `juntar` é a chave do passo do desfazer que este emenda (a correção de uma palavra
        que também ensina: um Ctrl+Z desfaz as duas)."""
        indice = self.indice
        self.tarefa("Ensinando", lambda: self._preparar_ensinar(indice, por_char, descricao,
                                                                depois, juntar),
                    falhou=self._falhou("Ensinar"))

    def _preparar_ensinar(self, indice, por_char, descricao, depois, juntar):
        pagina = self.modelo
        if indice != self.indice or pagina is None or self.leitor is None:
            return None
        vivos = pagina.vivos
        por_char = {c: [g for g in gids if g in vivos] for c, gids in por_char.items()}
        por_char = {c: gids for c, gids in por_char.items() if gids}
        if not por_char:
            self._avisar("O glifo a ensinar saiu da página antes da vez dele.", 6000)
            return None
        imagem, leitor, projeto = self.imagem, self.leitor, self.projeto
        antes_inst = self._instantaneo()
        antes = tuple(pagina.boxes)
        limiares = leitor.limiares
        onde = {b.gid: i for i, b in enumerate(antes)}
        alvos = {onde[g] for gids in por_char.values() for g in gids}
        lidos = ed.copias_para_ler(antes, lambda e: precisa_revisao(
            e.char, e.source, e.confidence, limiares))
        for i in alvos:
            if lidos[i] is antes[i].entry:
                lidos[i] = ed.copia(antes[i].entry)
        grupos = [(c, [onde[g] for g in gids]) for c, gids in por_char.items()]

        def trabalho(_progresso):
            return sum(pg.ensinar_varios(imagem, lidos, indices, char, leitor, projeto, indice,
                                         gids={i: antes[i].gid for i in indices})
                       for char, indices in grupos)

        def pronto(resolvidos: int):
            ed.aplicar_leituras(pagina, antes, lidos)
            self._mudou(pagina, indice, descricao, antes_inst, juntar=juntar)
            self.eventos.emitir("padroes_mudaram")
            if depois is not None and pagina is self.modelo:
                depois(resolvidos)

        return trabalho, pronto

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
    @property
    def historico(self) -> Optional[hs.Historico]:
        return self.historicos.get(self.indice)

    def desfazer(self) -> None:
        """Ctrl+Z; espera a tarefa em andamento (vai para a fila)."""
        indice = self.indice
        self.tarefa("Desfazendo", lambda: self._preparar_voltar(indice, refazer=False))

    def refazer(self) -> None:
        indice = self.indice
        self.tarefa("Refazendo", lambda: self._preparar_voltar(indice, refazer=True))

    def _preparar_voltar(self, indice: int, *, refazer: bool):
        historico = self.historicos.get(indice)
        if indice != self.indice or historico is None or self.leitor is None:
            return None
        if self.lote_rodando:
            self._recusar_no_lote()
            return None
        passo = historico.refazer() if refazer else historico.desfazer()
        if passo is None:
            return None
        if refazer:
            for amostra in passo.criados:
                self.leitor.padroes.restaurar(amostra)
        else:
            for amostra in passo.criados:
                if amostra.caminho.exists():
                    self.leitor.esquecer(amostra.caminho)
        self._voltar_para(passo.depois if refazer else passo.antes)
        acao = "Refeito" if refazer else "Desfeito"
        self._avisar(f"{acao}: {passo.descricao}.", 6000)
        return None                         # nada a fazer fora da interface

    def _voltar_para(self, estado: hs.Instantaneo) -> None:
        pagina = self._pagina_para_editar()
        salvo = estado.pagina
        pagina.boxes = list(salvo.boxes) if salvo is not None else []
        pagina.tabuleiros = list(salvo.tabuleiros) if salvo is not None else []
        pagina.diagramas = list(salvo.diagramas) if salvo is not None else []
        pagina.decisoes = salvo.decisoes if salvo is not None else Decisoes()
        pagina.estado = salvo.estado if salvo is not None else NAO_RECONHECIDA
        # `proximo_n` não volta: um gid nunca é reaproveitado.
        self.atual, self.pulados, self.selecao = None, set(), set()
        self._gravar(pagina)
        self.eventos.emitir("glifos_mudaram", None)
        self.eventos.emitir("padroes_mudaram")
        self.eventos.emitir("selecao_mudou")
        self.ir_ao_primeiro_pendente()
        self.eventos.emitir("acoes_mudaram")

    def esquecer(self, caminhos: Sequence) -> None:
        """Apaga amostras dos padrões do livro e relê a página inteira sem elas (na fila: o
        leitor não muda no meio de uma leitura)."""
        if self.leitor is None:
            return
        caminhos = list(caminhos)

        def preparar():
            if self.leitor is None:
                return None
            for caminho in caminhos:
                self.leitor.esquecer(caminho)
            self.eventos.emitir("padroes_mudaram")
            if self.modelo is not None:
                novo = proximo_estado(self.modelo.estado, "esquecer_padrao")
                if novo != self.modelo.estado:
                    self.modelo.estado = novo
                    self._gravar(self.modelo)
                    self._avisar("A página estava verificada e voltou à revisão: o padrão "
                                 "esquecido lia glifos dela.", 8000)
            self.reler_pendentes(tudo=True)
            return None
        self.tarefa("Esquecendo padrões", preparar, falhou=self._falhou("Esquecer padrões"))

    def aplicar_limiares(self, limiares) -> None:
        """Os limiares do livro, gravados no projeto, e a fila refeita com eles (na fila: a
        fila de revisão não muda no meio de uma leitura). A mensagem vai para a barra; um
        problema ao gravar vai em `aviso`."""
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
        self._avisar("O lote está lendo o livro: a edição espera ele acabar (ou cancele o "
                     "lote no menu Ferramentas).", 8000)

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

    def _instantaneo(self) -> hs.Instantaneo:
        """A página agora, com os padrões que o livro tem, para o desfazer."""
        pagina = self.modelo.instantaneo() if self.modelo is not None else None
        return hs.Instantaneo(pagina, self.padroes())

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

    def _mudou(self, pagina: Pagina, indice: int, descricao: str, antes: hs.Instantaneo, *,
               juntar=None, evento: str = "editar") -> None:
        """Depois de uma edição: o estado (§4.4), o passo do desfazer, a gravação e o aviso."""
        pagina.estado = proximo_estado(pagina.estado, evento)
        depois = hs.Instantaneo(pagina.instantaneo(), self.padroes())
        criados = []
        if self.leitor is not None:
            for caminho in sorted(depois.padroes - antes.padroes):
                criados.append(self.leitor.padroes.guardar(caminho))
        historico = self.historicos.setdefault(indice, hs.Historico())
        historico.registrar(hs.Passo(descricao, antes, depois, criados, juntar=juntar))
        self._gravar(pagina)
        if pagina is self.modelo:
            self.eventos.emitir("glifos_mudaram", None)
        self.eventos.emitir("acoes_mudaram")

    def _gravar(self, pagina: Pagina) -> None:
        if not self.projeto.agendar(pagina):
            self._avisar("Projeto aberto só para leitura: nada é gravado.", 6000)

