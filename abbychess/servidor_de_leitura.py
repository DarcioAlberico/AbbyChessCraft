"""O servidor de leitura (SPEC §11): os modelos globais num processo filho só.

**Por que um processo.** A base global do PyBoxEditor ocupa ~700 MB e a leitura de uma
página prende a CPU por segundos; na interface, o lote travava a janela (o passo E é o "o
lote não trava mais"). O filho é aberto com o projeto (`spawn`), importa só este módulo e o
que a leitura pede (sem PySide6), guarda os modelos e atende **toda** leitura global: o F5,
as releituras de glifo, a leitura e releitura dos diagramas, e o lote.

**A vez.** Os pedidos têm duas prioridades, interativo e lote. A página do lote roda numa
thread de trabalho do filho, e um pedido interativo (um F5, uma releitura) é atendido assim
que chega: a página do lote para antes do glifo seguinte até ele terminar (`_Laco`), mesmo
no meio da segmentação dela; um cancelamento do lote para a página no glifo seguinte.
Prioridade `BELOW_NORMAL` e `torch.set_num_threads(núcleos − 2)`.

**Os padrões.** O filho tem os padrões do livro lidos do disco ao começar. Depois, a
interface manda os **deltas** (as amostras criadas e as apagadas), que valem a partir do
pedido seguinte e do glifo seguinte do lote (`incluir`/`excluir`, sem gravar nada: quem grava
é a interface).

**O escritor único.** O servidor só lê e devolve (os boxes sem gid, a procedência de cada
leitura, os diagramas lidos); a interface aplica a regra de conflito, dá os gids, aplica o
§4.6 e grava pelo gravador.

**A fábrica de leitor** é importável por caminho (`"modulo:funcao"`, ou a variável de ambiente
`ABBY_FABRICA_DE_LEITOR`): os testes usam um leitor sem torch (`tests/leitor_falso.py`).

Do lado da interface, `ServidorDeLeitura` abre o filho, manda os pedidos e recebe as
respostas numa thread ouvinte, que chama o `ao_terminar` de cada pedido (quem usa leva o
resultado para a thread da interface). Se o filho morre, ele é aberto de novo uma vez e os
pedidos pendentes são reenviados; na segunda queda, os pedidos falham e `ao_avisar` diz.
"""

from __future__ import annotations

import importlib
import itertools
import logging
import multiprocessing as mp
import os
import queue
import sys
import threading
import time
import traceback
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)

FABRICA_PADRAO = "abbychess.servidor_de_leitura:leitor_global"
INTERATIVO, LOTE = 0, 1
#: O resultado de um pedido cancelado (ou abandonado ao fechar).
CANCELADO = "cancelado"


class Cancelado(Exception):
    """O pedido foi cancelado no meio (o lote, entre um glifo e outro)."""


class ErroDoServidor(RuntimeError):
    """O servidor não leu: a leitura falhou nele, ou ele caiu duas vezes."""


# ----------------------------------------------------------------------
# A leitura (as mesmas funções servem ao filho e ao caminho sem servidor dos testes)
# ----------------------------------------------------------------------

@dataclass
class PaginaLida:
    """O que o servidor devolve de uma página: os boxes lidos (sem gid), a procedência de
    cada leitura, os tabuleiros, a escala e os diagramas lidos."""

    boxes: list
    amostras: list
    tabuleiros: list
    escala: Optional[float]
    diagramas: list = field(default_factory=list)
    #: ``True``/``False`` quando o negrito foi medido; ``None`` quando faltou medida.
    negritos: list = field(default_factory=list)


def ler_pagina(imagem, zonas, marcados, leitor, *, progresso=None,
               cancelado: Callable[[], bool] = lambda: False) -> PaginaLida:
    """Segmenta pelas áreas, põe no lugar os glifos que ficam (§4.6), lê e acha os diagramas."""
    from abbychess import diagramas as dg
    from abbychess import pagina as pg
    from abbychess import procedencia
    from abbychess import zonas as zn

    segmentada = zn.segmentar(imagem, zonas, leitor)
    if marcados:
        segmentada.boxes = pg.manter_marcados(segmentada.boxes, marcados)
    pg.ler_boxes(imagem, segmentada.boxes, leitor, progresso=progresso, cancelado=cancelado)
    if cancelado():
        raise Cancelado
    lidos = dg.ler_diagramas(imagem, segmentada.tabuleiros, escala=segmentada.escala,
                             classificar=leitor.arbitro, boxes=segmentada.boxes)
    negritos = pg.efeitos_de_impressao(imagem, segmentada.boxes)
    return PaginaLida(segmentada.boxes, [procedencia.amostra_de(b) for b in segmentada.boxes],
                      list(segmentada.tabuleiros), segmentada.escala, lidos, negritos)


def reler_boxes(imagem, boxes, leitor, *, so_pendentes: bool, progresso=None):
    """Lê de novo os boxes (cópias) e devolve `(boxes, amostras, resumo)`."""
    from abbychess import pagina as pg
    from abbychess import procedencia

    resumo = pg.ler_boxes(imagem, boxes, leitor, so_pendentes=so_pendentes, progresso=progresso)
    return boxes, [procedencia.amostra_de(b) for b in boxes], resumo


def registrar_procedencia(boxes, amostras) -> None:
    """A procedência das leituras que voltaram do filho: o registro é por objeto e não
    atravessa a fila (§4.1), e a interface o refaz nos boxes que chegaram."""
    from abbychess import procedencia

    for box, amostra in zip(boxes, amostras):
        if amostra is not None:
            procedencia.registrar(box, amostra)


def ler_recortes(itens, leitor) -> list:
    """As leituras de recortes soltos: `[(recorte, altura_de_referencia)]` → `[Leitura]`."""
    return [leitor.ler(recorte, altura_de_referencia=altura) for recorte, altura in itens]


def ler_diagramas(imagem, caixas, boxes, leitor) -> list:
    from abbychess import diagramas as dg

    return dg.ler_diagramas(imagem, caixas, classificar=leitor.arbitro, boxes=boxes)


def automaticas(imagem, leitor) -> list:
    """As áreas que a segmentação sugere numa página ainda sem boxes (o árbitro dos glifos
    colados é o leitor global)."""
    from abbychess import pagina as pg
    from abbychess import zonas as zn

    largura, altura = imagem.size
    bruta = pg.segmentar_pagina(imagem, leitor)
    return zn.automaticas(bruta.boxes, bruta.tabuleiros, largura, altura)


def estado_do_leitor(leitor) -> dict:
    """O que a abertura diz dos modelos (a rede carregou? quantas referências globais?)."""
    base = getattr(leitor, "base", None)
    return {"rede": getattr(leitor, "rede", None) is not None,
            "base": getattr(base, "total", 0) if base is not None else 0}


def leitor_global(pasta_de_padroes, limiares):
    """A fábrica de verdade: o leitor com a rede e a base global do PyBoxEditor."""
    from abbychess.leitor import LeitorDoLivro

    return LeitorDoLivro.com_modelos_globais(pasta_de_padroes, limiares=limiares)


def _fabrica(caminho: str):
    modulo, nome = caminho.split(":", 1)
    return getattr(importlib.import_module(modulo), nome)


# ----------------------------------------------------------------------
# O filho
# ----------------------------------------------------------------------

def _baixar_a_prioridade() -> None:
    try:
        import psutil

        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 10)
    except Exception:  # sem psutil ou sem permissão: roda na prioridade normal
        log.debug("a prioridade do servidor não baixou", exc_info=True)
    if "torch" in sys.modules:
        sys.modules["torch"].set_num_threads(max(1, (os.cpu_count() or 2) - 2))


class _Laco:
    """O laço do filho: recebe e atende, com a página do lote numa thread de trabalho.

    **A vez.** A thread principal recebe as mensagens e atende os pedidos interativos na
    hora, mesmo com uma página do lote em curso: enquanto um interativo roda, a página do lote
    para antes do glifo seguinte (`_livre`), e o leitor lê um glifo por vez (`_trava`). Assim
    a segmentação da página do lote, que não tem glifos no meio (~0,5 s numa página cheia),
    também dá a vez, e a releitura de um glifo não espera por ela. Os deltas dos padrões e
    os limiares entram assim que chegam, entre um glifo e outro (sob a mesma trava).

    Durante um interativo longo (um F5), a thread principal não recebe nada: o "cancelar"
    do lote, os deltas e o "sair" esperam o fim dele (a página do lote fica parada em
    `_livre`; fechar o projeto no meio de um F5 depende do `terminate` de `fechar`).
    """

    def __init__(self, entrada, saida, fabrica: str, pasta_de_padroes, limiares):
        self.entrada, self.saida = entrada, saida
        self.fabrica, self.pasta, self.limiares = fabrica, pasta_de_padroes, limiares
        self.interativos: deque = deque()
        self.lotes: deque = deque()
        self.cancelados: set = set()
        self.sair = False
        self.interativo: Optional[int] = None      # o id do interativo em curso
        self.no_lote: Optional[int] = None         # o id da página do lote em curso
        #: A ordem em que os pedidos começaram e a em que terminaram (os testes as pedem:
        #: CA-11.8 e a vez entre glifos).
        self.ordem: List[int] = []
        self.fins: List[int] = []
        self._trava = threading.Lock()             # o leitor: um glifo por vez
        self._livre = threading.Event()            # nenhum interativo rodando
        self._livre.set()
        self._acordar = threading.Event()          # a página do lote terminou
        self._trabalhador: Optional[threading.Thread] = None

    def rodar(self) -> None:
        self.leitor = _fabrica(self.fabrica)(self.pasta, self.limiares)
        _baixar_a_prioridade()
        ler_original = self.leitor.ler
        self.leitor.ler = lambda recorte, **k: self._ler_com_vez(ler_original, recorte, **k)
        self.saida.put(("pronto", os.getpid(), estado_do_leitor(self.leitor)))
        while not self.sair:
            self._receber(bloquear=not (self.interativos or (self.lotes and not self._no_lote())))
            if self.interativos:
                self._atender_interativo(self.interativos.popleft())
            elif self.lotes and not self._no_lote():
                self._comecar_lote(self.lotes.popleft())
        if self._trabalhador is not None:          # o "sair" para a página no glifo seguinte
            self._trabalhador.join(5)

    def _no_lote(self) -> bool:
        # O `no_lote`, que o trabalhador zera antes de acordar o laço, e não o `is_alive()`:
        # a thread ainda viva logo depois do `_acordar.set()` deixaria a página seguinte
        # parada na fila (o acordar consumido e o laço bloqueado esperando mensagem).
        return self.no_lote is not None

    def _receber(self, bloquear: bool) -> None:
        while True:
            try:
                mensagem = self.entrada.get(timeout=0.2) if bloquear else self.entrada.get_nowait()
            except queue.Empty:
                if bloquear and not self._acordar.is_set():
                    continue
                self._acordar.clear()
                return
            bloquear = False
            tipo = mensagem[0]
            if tipo == "pedido":
                (self.interativos if mensagem[2] == INTERATIVO else self.lotes).append(mensagem)
            elif tipo == "padroes":
                _, criados, apagados = mensagem
                with self._trava:                  # não no meio do glifo do lote
                    for caminho in apagados:
                        self.leitor.padroes.excluir(caminho)
                    for criado in criados:
                        caminho, altura, *resto = criado
                        self.leitor.padroes.incluir(caminho, altura,
                                                    resto[0] if resto else None)
            elif tipo == "limiares":
                with self._trava:
                    self.leitor.trocar_limiares(mensagem[1])
            elif tipo == "cancelar":
                # O que espera na fila continua nela e, na vez dele, responde "cancelado"
                # (`_atender`): quem pediu sempre recebe resposta. O que já terminou não guarda
                # nada (o cancelamento chegou tarde).
                id_ = mensagem[1]
                na_fila = any(m[1] == id_ for m in (*self.interativos, *self.lotes))
                if na_fila or id_ in (self.interativo, self.no_lote):
                    self.cancelados.add(id_)
            elif tipo == "sair":
                self.sair = True
                return

    def _ler_com_vez(self, ler, recorte, **k):
        """Um glifo. O do lote espera os interativos em curso e para se foi cancelado (ou se
        o servidor vai sair); o interativo só espera o glifo do lote que está sendo lido."""
        if threading.current_thread() is self._trabalhador:
            while not self._livre.wait(0.1) and not self.sair:
                pass
            if self.no_lote in self.cancelados or self.sair:
                raise Cancelado
        with self._trava:
            return ler(recorte, **k)

    def _atender_interativo(self, mensagem) -> None:
        self.interativo = mensagem[1]
        self._livre.clear()
        try:
            self._atender(mensagem)
        finally:
            self._livre.set()
            self.interativo = None

    def _comecar_lote(self, mensagem) -> None:
        self.no_lote = mensagem[1]

        def rodar():
            try:
                self._atender(mensagem)
            finally:
                self.no_lote = None
                self.cancelados.discard(mensagem[1])   # um cancelar que chegou no fim
                self._acordar.set()                # o laço começa a página seguinte

        self._trabalhador = threading.Thread(target=rodar, name="pagina-do-lote", daemon=True)
        self._trabalhador.start()

    def _atender(self, mensagem) -> None:
        _, id_, _prioridade, operacao, argumentos = mensagem
        if id_ in self.cancelados or self.sair:
            self.cancelados.discard(id_)
            self.saida.put(("resposta", id_, False, CANCELADO))
            return
        self.ordem.append(id_)
        try:
            resultado = self._operar(operacao, argumentos)
        except Cancelado:
            self.saida.put(("resposta", id_, False, CANCELADO))
        except Exception as erro:  # a interface decide: o log do filho guarda o rastro
            self.saida.put(("resposta", id_, False,
                            f"{erro}\n\n{traceback.format_exc(limit=4)}"))
        else:
            self.saida.put(("resposta", id_, True, resultado))
        finally:
            self.fins.append(id_)
            self.cancelados.discard(id_)

    def _operar(self, operacao: str, argumentos):
        leitor = self.leitor
        if operacao == "ler_pagina":
            imagem, zonas, marcados = argumentos
            return ler_pagina(imagem, zonas, marcados, leitor)
        if operacao == "reler_boxes":
            imagem, boxes, so_pendentes = argumentos
            return reler_boxes(imagem, boxes, leitor, so_pendentes=so_pendentes)
        if operacao == "ler_recortes":
            return ler_recortes(argumentos, leitor)
        if operacao == "ler_diagramas":
            imagem, caixas, boxes = argumentos
            return ler_diagramas(imagem, caixas, boxes, leitor)
        if operacao == "automaticas":
            return automaticas(argumentos, leitor)
        if operacao == "ordem":
            return list(self.ordem)
        if operacao == "fins":
            return list(self.fins)
        if operacao == "padroes":                  # os testes conferem os deltas
            return leitor.padroes.total
        if operacao == "pid":
            return os.getpid()
        if operacao == "modulos":                  # os testes: o filho não carrega o Qt
            return sorted(m for m in ("PySide6", "torch") if m in sys.modules)
        raise ValueError(f"operação desconhecida {operacao!r}")


def _principal(entrada, saida, fabrica, pasta_de_padroes, limiares) -> None:
    """A entrada do filho (`spawn`)."""
    logging.basicConfig(level=logging.WARNING)
    try:
        _Laco(entrada, saida, fabrica, pasta_de_padroes, limiares).rodar()
    except Exception:  # a queda vira resposta: a interface reabre ou desiste
        saida.put(("caiu", traceback.format_exc(limit=6)))


# ----------------------------------------------------------------------
# A interface
# ----------------------------------------------------------------------

@dataclass
class Pedido:
    id: int
    operacao: str
    prioridade: int
    mensagem: tuple
    ao_terminar: Optional[Callable[["Pedido"], None]] = None
    feito: threading.Event = field(default_factory=threading.Event)
    ok: bool = False
    resultado: Any = None
    enviado_em: float = field(default_factory=time.perf_counter)

    @property
    def cancelado(self) -> bool:
        return not self.ok and self.resultado == CANCELADO


class ServidorDeLeitura:
    """O filho, visto da interface: pedir, esperar, cancelar, mandar os deltas, fechar."""

    def __init__(self, pasta_de_padroes, limiares, *, fabrica: Optional[str] = None,
                 ao_avisar: Optional[Callable[[str, str, bool], None]] = None,
                 ao_ficar_pronto: Optional[Callable[[dict], None]] = None):
        self.pasta, self.limiares = pasta_de_padroes, limiares
        self.fabrica = fabrica or os.environ.get("ABBY_FABRICA_DE_LEITOR") or FABRICA_PADRAO
        #: `ao_avisar(titulo, texto, desistiu)`, na thread ouvinte, com o `desistiu` da hora
        #: do aviso (duas quedas seguidas não chegam as duas como a segunda).
        self.ao_avisar = ao_avisar or (lambda titulo, texto, _desistiu: log.warning(
            "%s: %s", titulo, texto))
        self._contexto = mp.get_context("spawn")
        self._ids = itertools.count(1)
        self._pendentes: Dict[int, Pedido] = {}
        self._trava = threading.RLock()
        self.pronto = threading.Event()
        #: O estado dos modelos do filho (`estado_do_leitor`), quando ele fica pronto; e
        #: `ao_ficar_pronto(estado)`, chamado na thread ouvinte (só na primeira vez).
        self.estado: Optional[dict] = None
        self.ao_ficar_pronto = ao_ficar_pronto
        self.reinicios = 0
        self.desistiu = False
        self._fechando = False
        self._abrir()
        self._ouvinte = threading.Thread(target=self._ouvir, name="ouvinte-da-leitura", daemon=True)
        self._ouvinte.start()

    # ------------------------------------------------------------------
    def _abrir(self) -> None:
        self.pronto.clear()
        # As filas do filho que caiu: sem o `cancel_join_thread`, a thread que alimenta a
        # entrada velha (com pedidos no buffer, que ninguém mais lê) prende a saída do
        # programa no `join` do multiprocessing.
        for fila in (getattr(self, "_entrada", None), getattr(self, "_saida", None)):
            if fila is not None:
                try:
                    fila.close()
                    fila.cancel_join_thread()
                except (OSError, ValueError):
                    pass
        self._entrada = self._contexto.Queue()
        self._saida = self._contexto.Queue()
        self.processo = self._contexto.Process(
            target=_principal, name="abbychess-servidor-de-leitura", daemon=True,
            args=(self._entrada, self._saida, self.fabrica, self.pasta, self.limiares))
        self.processo.start()

    @property
    def pid(self) -> Optional[int]:
        return self.processo.pid if self.processo is not None else None

    def pedir(self, operacao: str, argumentos=None, *, prioridade: int = INTERATIVO,
              ao_terminar: Optional[Callable[[Pedido], None]] = None) -> Pedido:
        """Manda um pedido; `ao_terminar(pedido)` roda na thread ouvinte quando ele volta."""
        id_ = next(self._ids)
        mensagem = ("pedido", id_, prioridade, operacao, argumentos)
        pedido = Pedido(id_, operacao, prioridade, mensagem, ao_terminar)
        with self._trava:
            if self.desistiu:
                self._concluir(pedido, False, "o servidor de leitura caiu duas vezes")
                return pedido
            self._pendentes[id_] = pedido
            self._entrada.put(mensagem)
        return pedido

    @property
    def parado(self) -> bool:
        """Desistiu depois da segunda queda, ou fechou: não lê mais."""
        return self.desistiu or self._fechando

    def esperar(self, pedido: Pedido, timeout: Optional[float] = None):
        """O resultado do pedido (numa thread que pode esperar: nunca na da interface)."""
        if not pedido.feito.wait(timeout):
            raise TimeoutError(f"o servidor não respondeu ao pedido {pedido.operacao!r}")
        if not pedido.ok:
            if pedido.cancelado:
                raise Cancelado
            raise ErroDoServidor(str(pedido.resultado))
        return pedido.resultado

    def chamar(self, operacao: str, argumentos=None, *, prioridade: int = INTERATIVO,
               timeout: Optional[float] = None):
        return self.esperar(self.pedir(operacao, argumentos, prioridade=prioridade), timeout)

    def cancelar(self, pedido: Pedido) -> None:
        """Para o pedido (o do lote para no glifo seguinte; um que não começou nem começa, e
        responde "cancelado" na vez dele)."""
        with self._trava:
            if not pedido.feito.is_set() and not self._fechando:
                self._entrada.put(("cancelar", pedido.id))

    def abandonar_pendentes(self) -> None:
        """Ao fechar: quem espera um pedido recebe "cancelado" já (a tarefa em curso termina
        sem esperar a leitura), e o filho é avisado para não começar o que falta."""
        with self._trava:
            pendentes, self._pendentes = list(self._pendentes.values()), {}
            if not self._fechando:
                for pedido in pendentes:
                    self._entrada.put(("cancelar", pedido.id))
        for pedido in pendentes:
            self._concluir(pedido, False, CANCELADO)

    def enviar_padroes(self, criados, apagados) -> None:
        """Deltas: `criados` tem `(caminho, altura[, efeito])`; `apagados`, caminhos."""
        if criados or apagados:
            with self._trava:
                self._entrada.put(("padroes", [(str(item[0]), *item[1:]) for item in criados],
                                   [str(c) for c in apagados]))

    def trocar_limiares(self, limiares) -> None:
        self.limiares = limiares
        with self._trava:
            self._entrada.put(("limiares", limiares))

    # ------------------------------------------------------------------
    def _ouvir(self) -> None:
        while not self._fechando:
            try:
                mensagem = self._saida.get(timeout=0.3)
            except queue.Empty:
                if not self._fechando and not self.processo.is_alive():
                    self._caiu("o processo terminou")
                continue
            except (EOFError, OSError):
                if not self._fechando:
                    self._caiu("a fila do processo fechou")
                continue
            tipo = mensagem[0]
            if tipo == "pronto":
                primeira = self.estado is None
                self.estado = mensagem[2]
                self.pronto.set()
                if primeira and self.ao_ficar_pronto is not None:
                    try:
                        self.ao_ficar_pronto(self.estado)
                    except Exception:  # quem ouve falhou: o ouvinte continua
                        log.exception("o aviso de servidor pronto falhou")
            elif tipo == "resposta":
                _, id_, ok, resultado = mensagem
                with self._trava:
                    pedido = self._pendentes.pop(id_, None)
                if pedido is not None:
                    self._concluir(pedido, ok, resultado)
            elif tipo == "caiu":
                log.error("o servidor de leitura caiu:\n%s", mensagem[1])
                self._caiu(mensagem[1].strip().splitlines()[-1] if mensagem[1].strip() else "")

    def _concluir(self, pedido: Pedido, ok: bool, resultado) -> None:
        pedido.ok, pedido.resultado = ok, resultado
        pedido.feito.set()
        if pedido.ao_terminar is not None:
            try:
                pedido.ao_terminar(pedido)
            except Exception:  # quem pediu falhou ao receber: o ouvinte continua
                log.exception("o fim do pedido %r falhou", pedido.operacao)

    def _caiu(self, motivo: str) -> None:
        """Reabre uma vez e reenvia os pendentes; na segunda queda, desiste."""
        with self._trava:
            if self._fechando or self.desistiu:
                return
            try:
                self.processo.join(0.1)
            except Exception:
                pass
            if self.reinicios >= 1:
                self.desistiu = True
                pendentes, self._pendentes = list(self._pendentes.values()), {}
            else:
                self.reinicios += 1
                pendentes = None
                self._abrir()
                for pedido in self._pendentes.values():
                    self._entrada.put(pedido.mensagem)
        if pendentes is None:
            self._avisar(f"O servidor de leitura parou ({motivo}) e foi aberto de novo; os "
                         "pedidos em curso foram reenviados.", False)
            return
        for pedido in pendentes:
            self._concluir(pedido, False, "o servidor de leitura caiu duas vezes")
        self._avisar(f"O servidor de leitura parou de novo ({motivo}). Reabra o projeto para "
                     "voltar a ler as páginas.", True)

    def _avisar(self, texto: str, desistiu: bool) -> None:
        try:
            self.ao_avisar("Servidor de leitura", texto, desistiu)
        except Exception:  # quem ouve falhou: o ouvinte continua (e o rastro fica no log)
            log.exception("o aviso do servidor de leitura falhou")

    def fechar(self, espera: float = 5.0) -> None:
        """Termina o filho: pede para sair, espera `espera` s e, se preciso, o encerra."""
        with self._trava:                       # uma queda agora não reabre o filho
            if self._fechando:
                return
            self._fechando = True
            try:
                self._entrada.put(("sair",))
            except (OSError, ValueError):
                pass
        self.processo.join(espera)
        if self.processo.is_alive():
            self.processo.terminate()
            self.processo.join(1)
        with self._trava:
            pendentes, self._pendentes = list(self._pendentes.values()), {}
        for pedido in pendentes:
            self._concluir(pedido, False, CANCELADO)
        for fila in (self._entrada, self._saida):
            try:
                fila.close()
                fila.cancel_join_thread()
            except (OSError, ValueError):
                pass
        self._ouvinte.join(1)
