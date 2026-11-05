"""A entrada do aplicativo (`app.principal`): o erro que ninguém pegou vai ao log."""

from __future__ import annotations

import pytest

import logging
import sys
import threading


@pytest.mark.erro_esperado
def test_o_erro_que_ninguem_pegou_vai_ao_log_com_o_rastro(caplog, monkeypatch):
    """SPEC-qualidade CA-Q-C1: o erro que escapa de um slot do Qt (o `sys.excepthook`) ou de
    uma thread (o `threading.excepthook`) não vai só ao stderr, que a janela não tem."""
    from abbychess.app import principal

    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    principal.registrar_os_erros_soltos()

    def na_thread():
        raise RuntimeError("solto na thread")

    with caplog.at_level(logging.ERROR, logger="abbychess"):
        try:
            raise ValueError("solto na interface")
        except ValueError:
            sys.excepthook(*sys.exc_info())
        thread = threading.Thread(target=na_thread)
        thread.start()
        thread.join(5)
    soltos = {str(r.exc_info[1]) for r in caplog.records if r.exc_info}
    assert soltos == {"solto na interface", "solto na thread"}
