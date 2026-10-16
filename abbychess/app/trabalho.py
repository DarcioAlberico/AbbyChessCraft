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

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

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

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._fila: deque = deque()
        self._tarefa: Optional[_Tarefa] = None
        #: Dentro de `_proxima` ou de um `pronto`: a tarefa pedida ali só entra na fila.
        self._no_laco = False
        self.titulo = ""

    @property
    def ocupado(self) -> bool:
        return self._tarefa is not None or bool(self._fila)

    @property
    def na_fila(self) -> List[str]:
        return [t[0] for t in self._fila]

    def __call__(self, titulo: str, preparar, falhou=None, progresso=None) -> None:
        self.rodar(titulo, preparar, falhou, progresso)

    def rodar(self, titulo: str, preparar, falhou=None, progresso=None) -> None:
        """Agenda a tarefa: roda já se nada estiver rodando, senão entra na fila. Pedida de
        dentro de um `preparar` ou de um `pronto`, espera o laço de `_proxima`."""
        self._fila.append((titulo, preparar, falhou, progresso))
        if self._tarefa is None and not self._no_laco:
            self._proxima()
        else:
            self.fila_mudou.emit(self.na_fila)

    def _proxima(self) -> None:
        self._no_laco = True
        try:
            while self._fila:
                titulo, preparar, falhou, progresso = self._fila.popleft()
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
