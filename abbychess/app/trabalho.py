"""Trabalho pesado fora da thread da interface, uma tarefa por vez.

Ler uma página leva segundos e carregar os modelos também; feito na thread do Qt,
a janela congelaria. A tarefa roda num `QThreadPool` e devolve o resultado por
sinal, que o Qt entrega na thread da interface. Uma tarefa por vez porque o
leitor do livro não é seguro para duas threads ao mesmo tempo.
"""

from __future__ import annotations

import logging
import traceback
from typing import Any, Callable, Optional

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
    """Roda uma tarefa por vez e avisa quando está ocupado."""

    ocupado_mudou = Signal(bool, str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._ocupado = False
        self._tarefa: Optional[_Tarefa] = None

    @property
    def ocupado(self) -> bool:
        return self._ocupado

    def rodar(self, titulo: str, funcao, ao_concluir=None, ao_falhar=None, ao_progredir=None) -> bool:
        """Agenda `funcao(progresso)`. Devolve False se já há uma tarefa rodando."""
        if self._ocupado:
            return False
        tarefa = _Tarefa(funcao)
        if ao_progredir:
            tarefa.sinais.progresso.connect(ao_progredir)
        tarefa.sinais.concluido.connect(lambda r: self._fim(ao_concluir, r))
        tarefa.sinais.falhou.connect(lambda m: self._fim(ao_falhar, m))
        self._tarefa = tarefa  # mantém os sinais vivos até o fim
        self._ocupado = True
        self.ocupado_mudou.emit(True, titulo)
        self._pool.start(tarefa)
        return True

    def _fim(self, callback, valor):
        self._ocupado = False
        self._tarefa = None
        self.ocupado_mudou.emit(False, "")
        if callback:
            callback(valor)

    def esperar(self, ms: int = 30000) -> bool:
        return self._pool.waitForDone(ms)
