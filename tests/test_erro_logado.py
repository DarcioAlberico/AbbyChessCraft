"""CA-C5: um teste que loga ERROR sem a marca `erro_esperado` reprova."""

from __future__ import annotations

import logging
import threading

import pytest

from tests.conftest import reprovar_os_erros_logados

log = logging.getLogger(__name__)


def test_sem_erro_nada_acontece():
    reprovar_os_erros_logados([], None)


def test_com_erro_e_sem_a_marca_reprova():
    registro = logging.LogRecord("abbychess.x", logging.ERROR, "x.py", 1, "quebrou", (), None)
    with pytest.raises(pytest.fail.Exception, match="abbychess.x: quebrou"):
        reprovar_os_erros_logados([registro], None)


def test_a_marca_libera():
    registro = logging.LogRecord("abbychess.x", logging.ERROR, "x.py", 1, "quebrou", (), None)
    reprovar_os_erros_logados([registro], object())


@pytest.mark.erro_esperado
def test_a_guarda_ve_o_erro_de_outra_thread(sem_erro_logado):
    thread = threading.Thread(target=lambda: log.error("noutra thread"))
    thread.start()
    thread.join()
    assert [r.getMessage() for r in sem_erro_logado.erros] == ["noutra thread"]


def test_warning_nao_conta(sem_erro_logado):
    log.warning("só um aviso")
    assert sem_erro_logado.erros == []
