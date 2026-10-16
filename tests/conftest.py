"""Configuração comum dos testes: o Qt sem tela (`offscreen`) e o portão das camadas lentas.

As fixtures da janela (`app`, `janela`) e a página sintética ainda moram em
`tests/test_janela.py` e `tests/test_treino_por_livro.py`, importadas pelos outros
módulos; elas vêm para cá no passo 2a, quando a janela passa a ser montada pelo
controlador e as fixtures mudam de qualquer jeito.

O portão (SPEC §15.1): com `ABBY_PORTAO=1`, um teste `livro_real` que pularia por
falta do PDF ou do modelo **falha** (na preparação, numa fixture ou na chamada; um xfail
continua xfail). O portão só vale com as camadas selecionadas:
`ABBY_PORTAO=1 pytest -q -m "livro_real or desempenho"`; sem o `-m`, o `addopts` as tira.
Fora do portão, pular é aceito, para a suíte rodar numa máquina sem os livros.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    resultado = yield
    relatorio = resultado.get_result()
    if (os.environ.get("ABBY_PORTAO") == "1" and relatorio.skipped
            and not hasattr(relatorio, "wasxfail")
            and item.get_closest_marker("livro_real") is not None):
        relatorio.outcome = "failed"
        relatorio.longrepr = (f"[portão] {item.nodeid} pulou, mas no portão o livro real é "
                              f"obrigatório: {relatorio.longrepr}")


def pytest_addoption(parser):
    parser.addoption("--atualizar-golden", action="store_true", default=False,
                     help="regrava os arquivos de referência (golden) em vez de comparar")
