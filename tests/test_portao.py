"""O portão das camadas lentas: no portão, livro real ausente é falha, não pulo."""

from __future__ import annotations

from pathlib import Path

pytest_plugins = ["pytester"]

TESTE = '''
import pytest

@pytest.mark.livro_real
def test_precisa_do_livro():
    pytest.skip("o PDF não está nesta máquina")
'''


def _rodar(pytester, monkeypatch, portao: str | None):
    conftest = Path(__file__).with_name("conftest.py").read_text(encoding="utf-8")
    pytester.makeconftest(conftest)
    pytester.makeini("[pytest]\nmarkers =\n    livro_real: livro real\n")
    pytester.makepyfile(TESTE)
    if portao is None:
        monkeypatch.delenv("ABBY_PORTAO", raising=False)
    else:
        monkeypatch.setenv("ABBY_PORTAO", portao)
    return pytester.runpytest("-p", "no:cacheprovider")


def test_fora_do_portao_pular_e_aceito(pytester, monkeypatch):
    _rodar(pytester, monkeypatch, None).assert_outcomes(skipped=1)


def test_no_portao_pular_vira_falha(pytester, monkeypatch):
    resultado = _rodar(pytester, monkeypatch, "1")
    resultado.assert_outcomes(failed=1)
    resultado.stdout.fnmatch_lines(["*portão*"])


TESTE_SKIPIF = """
import pytest

@pytest.mark.livro_real
@pytest.mark.skipif(True, reason="o PDF não está nesta máquina")
def test_pula_na_preparacao():
    pass

@pytest.fixture
def livro():
    pytest.skip("o modelo não carregou")

@pytest.mark.livro_real
def test_pula_na_fixture(livro):
    pass

@pytest.mark.livro_real
@pytest.mark.xfail(reason="defeito conhecido")
def test_xfail_continua_xfail():
    assert False
"""


def test_no_portao_skipif_e_fixture_tambem_falham_e_xfail_nao(pytester, monkeypatch):
    conftest = Path(__file__).with_name("conftest.py").read_text(encoding="utf-8")
    pytester.makeconftest(conftest)
    pytester.makeini("[pytest]\nmarkers =\n    livro_real: livro real\n")
    pytester.makepyfile(TESTE_SKIPIF)
    monkeypatch.setenv("ABBY_PORTAO", "1")
    resultado = pytester.runpytest("-p", "no:cacheprovider")
    resultado.assert_outcomes(errors=2, xfailed=1)   # pular na preparação vira erro
