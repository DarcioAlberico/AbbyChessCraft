"""Trabalho pesado fora da thread da interface: uma tarefa por vez, as outras na fila.

Ler uma página leva segundos e carregar os modelos também; feito na thread do Qt, a
janela congelaria. A tarefa roda num `QThreadPool` e devolve o resultado por sinal, que o
Qt entrega na thread da interface. Uma por vez porque o leitor do livro não é seguro para
duas threads ao mesmo tempo.

**Nada é ignorado** (passo 2a): a tarefa pedida com outra rodando entra na fila, e a fila
aparece na barra de status (`fila_mudou`). Cada tarefa é `preparar()`, chamado na thread
da interface quando chega a vez dela (tira o instantâneo do que a tarefa vai usar, e
devolve `(trabalho, pronto)`, ou None para não fazer nada), `trabalho(progresso)` fora da
interface e `pronto(resultado)` de novo na interface (`abbychess.controlador`).
"""

from __future__ import annotations

import logging
import traceback
from collections import deque
from typing import Any, Callable, List, Optional

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot

log = logging.getLogger(__name__)


class _Sinais(QObject):
    progresso = Signal(int, int)
    concluido = Signal(object)
    falhou = Signal(str)


class _Tarefa(QRunnable):
    def __init__(self, funcao: Callable[[Callable[[int, int], None]], Any]):
        super().__init__()
        self.funcao = funcao
        self.sinais = _Sinais()

    def run(self):
        try:
            resultado = self.funcao(self.sinais.progresso.emit)
        except Exception as erro:  # a interface precisa saber, e o log guarda o rastro
            log.exception("a tarefa falhou")
            self.sinais.falhou.emit(f"{erro}\n\n{traceback.format_exc(limit=3)}")
            return
        self.sinais.concluido.emit(resultado)


class Executor(QObject):
    """Roda uma tarefa por vez, enfileira as outras e avisa o que está rodando e esperando."""

    #: (ocupado, título da tarefa que roda)
    ocupado_mudou = Signal(bool, str)
    #: Os títulos das tarefas que esperam a vez.
    fila_mudou = Signal(list)
    #: (feito, total) da tarefa que roda.
    progresso = Signal(int, int)
    #: Uma função a chamar na thread da interface (`na_interface`).
    _chamar = Signal(object)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._fila: deque = deque()
        self._tarefa: Optional[_Tarefa] = None
        #: Dentro de `_proxima` ou de um `pronto`: a tarefa pedida ali só entra na fila.
        self._no_laco = False
        #: A tarefa que roda é leve.
        self._leve = False
        self.titulo = ""
        # Um método do executor (que mora na thread da interface), e não uma lambda: assim a
        # ligação é enfileirada quando o sinal vem de outra thread.
        self._chamar.connect(self._chamar_aqui, Qt.ConnectionType.QueuedConnection)

    def na_interface(self, funcao: Callable[[], None]) -> None:
        """Chama `funcao` na thread da interface (de qualquer thread: o sinal enfileira). O
        servidor de leitura avisa assim, da thread ouvinte dele (§11). Com o executor já
        apagado pelo Qt (a janela fechou com o índice da busca ou um recorte em curso), não
        há interface onde chamar: o aviso é descartado, sem derrubar a thread que avisava."""
        try:
            self._chamar.emit(funcao)
        except RuntimeError as erro:
            if "deleted" not in str(erro):
                raise
            log.debug("aviso descartado: a interface já fechou (%s)", erro)

    @Slot(object)
    def _chamar_aqui(self, funcao) -> None:
        try:
            funcao()
        except Exception:  # um aviso que falhou não derruba o laço do Qt
            log.exception("a chamada na interface falhou")

    @property
    def ocupado(self) -> bool:
        return self._tarefa is not None or bool(self._fila)

    @property
    def na_fila(self) -> List[str]:
        return [t[0] for t in self._fila]

    def __call__(self, titulo: str, preparar, falhou=None, progresso=None, leve=False) -> None:
        self.rodar(titulo, preparar, falhou, progresso, leve=leve)

    def so_leves(self) -> bool:
        """Nada roda nem espera, ou só tarefas leves (a propagação de um Enter, passo 2b):
        aí uma edição pode rodar na hora, e o painel de treino continua valendo."""
        return (self._tarefa is None or self._leve) and all(t[4] for t in self._fila)

    def rodar(self, titulo: str, preparar, falhou=None, progresso=None, *,
              leve: bool = False) -> None:
        """Agenda a tarefa: roda já se nada estiver rodando, senão entra na fila. Pedida de
        dentro de um `preparar` ou de um `pronto`, espera o laço de `_proxima`. `leve` é a
        que lê só com uma cópia dos padrões (não prende o leitor nem o painel)."""
        self._fila.append((titulo, preparar, falhou, progresso, leve))
        if self._tarefa is None and not self._no_laco:
            self._proxima()
        else:
            self.fila_mudou.emit(self.na_fila)

    def _proxima(self) -> None:
        while True:
            self._esvaziar_a_fila()
            # Quem ouve `ocupado_mudou(False)` pode ter pedido outra tarefa no laço.
            if self._tarefa is not None or not self._fila:
                return

    def _esvaziar_a_fila(self) -> None:
        self._no_laco = True
        try:
            while self._fila:
                titulo, preparar, falhou, progresso, leve = self._fila.popleft()
                try:
                    par = preparar()
                except Exception as erro:
                    log.exception("a preparação de %r falhou", titulo)
                    if falhou is not None:
                        falhou(f"{erro}\n\n{traceback.format_exc(limit=3)}")
                    continue
                if par is None:
                    continue                    # nada a fazer fora da interface
                trabalho, pronto = par
                tarefa = _Tarefa(trabalho)
                tarefa.sinais.progresso.connect(self.progresso.emit)
                if progresso is not None:
                    tarefa.sinais.progresso.connect(progresso)
                tarefa.sinais.concluido.connect(lambda r, f=pronto: self._fim(f, r))
                tarefa.sinais.falhou.connect(lambda m, f=falhou: self._fim(f, m))
                self._tarefa, self.titulo = tarefa, titulo   # mantém os sinais vivos até o fim
                self._leve = leve
                self.ocupado_mudou.emit(True, titulo)
                self.fila_mudou.emit(self.na_fila)
                self._pool.start(tarefa)
                return
            self._tarefa, self.titulo = None, ""
            self.ocupado_mudou.emit(False, "")
            self.fila_mudou.emit([])
        finally:
            self._no_laco = False

    def _fim(self, callback, valor) -> None:
        self._tarefa = None
        self._no_laco = True                    # o que o `pronto` pedir espera a vez
        try:
            if callback is not None:
                callback(valor)
        finally:
            self._no_laco = False
            self._proxima()                     # um erro no fim não para a fila

    def esvaziar(self) -> None:
        """Tira da fila o que ainda não começou (ao fechar)."""
        self._fila.clear()
        self.fila_mudou.emit([])

    def esperar(self, ms: int = 30000) -> bool:
        return self._pool.waitForDone(ms)
