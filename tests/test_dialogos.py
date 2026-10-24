"""O fluxo compacto de criação do livro (§9.1)."""

from types import SimpleNamespace

import pytest

from abbychess.app import dialogos
from abbychess.projeto import ProjetoDeLivro
from tests.test_livro import pdf_sintetico


@pytest.mark.parametrize(("texto", "total", "esperado"), [
    ("", 12, (0, 11)),
    ("5-10", 20, (4, 9)),
    ("7", 20, (6, 6)),
])
def test_intervalo_do_corpo(texto, total, esperado):
    assert dialogos.intervalo_do_corpo(texto, total) == esperado


def test_intervalo_do_corpo_recusa_paginas_descontinuas():
    with pytest.raises(ValueError, match="contínuo"):
        dialogos.intervalo_do_corpo("2-4, 8", 10)


@pytest.mark.parametrize(("paridade", "esperado"), [
    ("Todas", [1, 2, 3, 4, 5]),
    ("Páginas ímpares", [2, 4]),
    ("Páginas pares", [1, 3, 5]),
])
def test_modelo_de_areas_filtra_intervalo_por_numero_visivel(monkeypatch, paridade, esperado):
    monkeypatch.setattr(dialogos.QInputDialog, "getText",
                        lambda *_a, **_k: ("2-6", True))
    monkeypatch.setattr(dialogos.QInputDialog, "getItem",
                        lambda *_a, **_k: (paridade, True))

    assert dialogos.paginas_do_modelo_de_areas(None, 10) == esperado


def test_novo_projeto_guarda_idioma_e_intervalo_no_mesmo_fluxo(tmp_path, monkeypatch):
    fonte = pdf_sintetico(tmp_path)
    destino = tmp_path / "projetos"
    valores = {}

    class Config:
        def value(self, chave, padrao):
            return padrao

        def setValue(self, chave, valor):
            valores[chave] = valor

    janela = SimpleNamespace(config=Config(), statusBar=lambda: SimpleNamespace(showMessage=lambda *_: None))
    monkeypatch.setattr(dialogos.QFileDialog, "getOpenFileName",
                        lambda *_a, **_k: (str(fonte), ""))
    monkeypatch.setattr(dialogos.QFileDialog, "getExistingDirectory",
                        lambda *_a, **_k: str(destino))
    monkeypatch.setattr(dialogos.DialogoDeNovoProjeto, "obter",
                        lambda *_a, **_k: dialogos.OpcoesDoNovoProjeto("Meu livro", "en", (1, 2)))
    monkeypatch.setattr(dialogos.nativo, "oferta", lambda *_a, **_k: dialogos.nativo.Oferta(0, 0))

    projeto = dialogos.novo_projeto(janela)
    try:
        assert projeto.dados.idioma == "en"
        assert projeto.dados.extras["intervalo_do_corpo"] == [1, 2]
        assert projeto.dados.extras["amostra_guiada_pendente"] is True
        assert projeto.dados.extras[dialogos.livro.CHAVE_DOS_CANDIDATOS_DA_AMOSTRA] == [1, 2]
        reaberto = ProjetoDeLivro.abrir(projeto.pasta)
        try:
            assert reaberto.dados.idioma == "en"
            assert reaberto.dados.extras["intervalo_do_corpo"] == [1, 2]
        finally:
            reaberto.fechar()
    finally:
        projeto.fechar()
    assert valores["ultima_fonte"] == str(fonte.parent)


def test_texto_nativo_parcial_deixa_so_as_recusadas_para_a_amostra(tmp_path, monkeypatch):
    fonte = pdf_sintetico(tmp_path)
    janela = SimpleNamespace(
        config=SimpleNamespace(value=lambda _chave, padrao: padrao, setValue=lambda *_: None),
        statusBar=lambda: SimpleNamespace(showMessage=lambda *_: None))
    monkeypatch.setattr(dialogos.QFileDialog, "getOpenFileName",
                        lambda *_a, **_k: (str(fonte), ""))
    monkeypatch.setattr(dialogos.QFileDialog, "getExistingDirectory",
                        lambda *_a, **_k: str(tmp_path / "projetos"))
    monkeypatch.setattr(dialogos.DialogoDeNovoProjeto, "obter",
                        lambda *_a, **_k: dialogos.OpcoesDoNovoProjeto("Parcial", "pt", (0, 2)))
    monkeypatch.setattr(dialogos.nativo, "oferta", lambda *_a, **_k: dialogos.nativo.Oferta(2, 3))
    monkeypatch.setattr(dialogos.QMessageBox, "question",
                        lambda *_a, **_k: dialogos.QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(dialogos.nativo, "importar",
                        lambda *_a, **_k: dialogos.nativo.Resultado((0, 2), (1,)))

    projeto = dialogos.novo_projeto(janela)
    try:
        assert projeto.dados.extras["amostra_guiada_pendente"] is True
        assert projeto.dados.extras[dialogos.livro.CHAVE_DOS_CANDIDATOS_DA_AMOSTRA] == [1]
    finally:
        projeto.fechar()

