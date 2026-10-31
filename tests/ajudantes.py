"""O que os testes dividem e não é fixture (SPEC-qualidade Q-T2, Q-T5).

`esperar` é a espera única da suíte rápida: ela espera uma condição, e não um tempo; o
`time.sleep` dos testes rápidos é só o dela (o teste de `tests/test_suite.py` confere).
"""

from __future__ import annotations

import time
from typing import Callable, Optional


def esperar(condicao: Callable[[], object], limite: float = 20.0, *,
            a_cada: Optional[Callable[[], None]] = None) -> bool:
    """Espera `condicao()` valer, até `limite` segundos; devolve se valeu (o teste afirma).
    A cada volta, os eventos do Qt (se há uma aplicação) e `a_cada` (a fila da interface de
    um controlador sem janela, por exemplo)."""
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
    except ImportError:                                  # sem o Qt: só a condição
        app = None
    fim = time.monotonic() + limite
    while True:
        if a_cada is not None:
            a_cada()
        if app is not None:
            app.processEvents()
        if condicao():
            return True
        if time.monotonic() >= fim:
            return False
        time.sleep(0.005)
