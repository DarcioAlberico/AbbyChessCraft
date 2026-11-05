"""D-4, CA-D4: a falha num trecho da camada mantém os outros, e Avisos diz qual."""

from __future__ import annotations

import pytest

from abbychess import exportar as ex
from abbychess import nativo
from abbychess.projeto import ProjetoDeLivro
from tests.ajudantes import _pdf_digital


@pytest.fixture
def projeto(tmp_path):
    p = ProjetoDeLivro.criar(tmp_path / "x", "Livro", _pdf_digital(tmp_path / "d.pdf", paginas=3))
    yield p
    p.fechar()


@pytest.fixture
def camada_falha_na_primeira(monkeypatch):
    from core import pdf_nativo

    original = pdf_nativo.extrair

    def extrair(caminho, paginas, **k):
        if 0 in paginas:
            raise RuntimeError("trecho ruim")
        return original(caminho, paginas, **k)

    monkeypatch.setattr(pdf_nativo, "extrair", extrair)


def test_ca_d4_a_falha_num_trecho_mantem_os_outros(projeto, camada_falha_na_primeira):
    relatorio = ex.Relatorio()
    nativas = ex.paginas_da_camada(projeto, [0, 2], relatorio=relatorio)
    assert set(nativas) == {2}
    assert [p for p, _ in relatorio.camada_falhou] == [0]
    assert "trecho ruim" in relatorio.camada_falhou[0][1]


def test_o_relatorio_diz_qual_pagina_e_o_resumo_avisa(projeto, camada_falha_na_primeira):
    relatorio = ex.Relatorio()
    ex.paginas_da_camada(projeto, [0, 2], relatorio=relatorio)
    assert "1 página(s) em que a camada de texto falhou" in relatorio.resumo()
    linha = next(t for t in relatorio.linhas() if t.startswith("página 1:"))
    assert "a camada de texto falhou" in linha and "trecho ruim" in linha


def test_a_pagina_importada_diz_que_saiu_sem_os_diagramas(projeto, camada_falha_na_primeira,
                                                          monkeypatch):
    monkeypatch.setattr(nativo, "paginas_importadas", lambda _p: [0])
    relatorio = ex.Relatorio()
    ex.paginas_da_camada(projeto, [0, 2], relatorio=relatorio)
    assert "sem os diagramas da camada" in relatorio.camada_falhou[0][1]


def test_paginas_importadas_vem_do_projeto(projeto):
    assert nativo.paginas_importadas(projeto) == []
    nativo.importar(projeto, [1])
    assert nativo.paginas_importadas(projeto) == [1]


def test_sem_falha_o_relatorio_nao_muda(projeto):
    relatorio = ex.Relatorio()
    assert set(ex.paginas_da_camada(projeto, [0, 2], relatorio=relatorio)) == {0, 2}
    assert relatorio.camada_falhou == []
    assert "camada de texto falhou" not in relatorio.resumo()
