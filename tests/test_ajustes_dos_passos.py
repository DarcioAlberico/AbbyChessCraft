"""Limitações registradas pelos passos que se resolvem em pouco: a aba Galeria no lugar da §3.1, o
item do começo do livro no sumário do EPUB e o editor de diagrama com as linhas de agora."""

from __future__ import annotations

import pytest

from abbychess import epub
from abbychess import lances as lc
from abbychess.app import editor_diagrama as dd
from tests.ajudantes import FEN, _lido
from tests.fixturas_janela import janela  # noqa: F401


def test_as_abas_na_ordem_da_spec(app, janela):  # noqa: F811
    assert [janela.vista.tabText(i) for i in range(janela.vista.count())] == [
        "Documento", "Galeria", "Padrões", "Diagramas"]


def _nav(*capitulos) -> str:
    return epub._nav(list(capitulos), epub.mensagens("pt"), "pt", False)


def test_as_paginas_antes_do_primeiro_titulo_tem_item_no_sumario():
    nav = _nav(epub._Capitulo("capitulo-001.xhtml", paginas=[(1, "pg1")]),
               epub._Capitulo("capitulo-002.xhtml", titulos=[(1, "t1", "Um")], paginas=[(2, "pg2")]))
    toc = nav[nav.index('epub:type="toc"'):nav.index('epub:type="page-list"')]
    assert toc.index('<a href="texto/capitulo-001.xhtml">Início do texto</a>') < toc.index("Um")


def test_o_livro_que_comeca_num_titulo_nao_ganha_item():
    nav = _nav(epub._Capitulo("capitulo-001.xhtml", titulos=[(1, "t1", "Um")], paginas=[(1, "pg1")]))
    toc = nav[nav.index('epub:type="toc"'):nav.index('epub:type="page-list"')]
    assert "Início do texto" not in toc


def test_o_livro_sem_titulo_segue_pelas_paginas():
    nav = _nav(epub._Capitulo("capitulo-001.xhtml", paginas=[(1, "pg1"), (2, "pg2")]))
    toc = nav[nav.index('epub:type="toc"'):nav.index('epub:type="page-list"')]
    assert "Início do texto" not in toc and "Páginas 1–2" in toc


@pytest.fixture
def editor(app):  # noqa: F811
    editor = dd.EditorDeDiagrama()
    diagrama = _lido()
    editor.abrir([diagrama], 0, [lc.primeira_linha("1.h3", "pt")])
    yield editor
    editor.deleteLater()


def test_sincronizar_com_as_linhas_de_agora_refaz_a_validacao(editor):
    assert FEN and editor.validacao().total == 1
    editor.sincronizar(editor.diagramas, [lc.primeira_linha("1.h3 h6 2.a3", "pt")])
    assert editor.validacao().total == 3


def test_sincronizar_sem_linhas_guarda_as_de_antes(editor):
    editor.sincronizar(editor.diagramas)
    assert editor.validacao().total == 1


def test_a_janela_passa_as_linhas_de_agora_ao_editor(app, janela, monkeypatch):  # noqa: F811
    recebido = []
    monkeypatch.setattr(type(janela.editor_diagrama), "aberto", property(lambda _: True))
    monkeypatch.setattr(janela.editor_diagrama, "sincronizar",
                        lambda diagramas, linhas=None: recebido.append(linhas) or True)
    monkeypatch.setattr(janela.pagina, "linhas_dos_diagramas", lambda: ["as de agora"])
    janela._sincronizar_conferencia()
    assert recebido == [["as de agora"]]
