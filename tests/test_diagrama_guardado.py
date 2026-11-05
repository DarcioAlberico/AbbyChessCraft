"""D-2, CA-D2: a edição do diagrama sobrevive à troca de página; fechar com alteração pergunta."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox

from abbychess import pagina as pg
from abbychess.app.editor_diagrama import EditorDeDiagrama
from abbychess.app.janela import JanelaPrincipal
from abbychess.leitor import LeitorDoLivro
from abbychess.projeto import ProjetoDeLivro
from tests.ajudantes import _lido, _pagina_sintetica


@pytest.fixture
def editor(app):
    e = EditorDeDiagrama()
    yield e
    e.deleteLater()


def _alterar(editor) -> None:
    editor.tabuleiro().colocar(4, 4, "Q")


def _casa(editor) -> str:
    casa = editor.tabuleiro().casa(4, 4)
    return casa.simbolo


def test_ca_d2_sair_e_voltar_mantem_a_casa(editor):
    d = _lido()
    editor.abrir([d], pid=7)
    _alterar(editor)
    assert "alterado" in editor.cabecalho.text() or editor.tabuleiro().pode_desfazer
    editor.fechar()                                       # PgDn: a página trocou
    assert not editor.aberto
    editor.abrir([d], pid=7)                              # voltou
    assert _casa(editor) == "Q" and editor.tabuleiro().pode_desfazer


def test_abrir_outra_pagina_guarda_a_de_antes(editor):
    d = _lido()
    editor.abrir([d], pid=7)
    _alterar(editor)
    editor.abrir([_lido(caixa=(1, 2, 3, 4))], pid=8)
    assert editor.tabuleiro().casa(4, 4).simbolo != "Q"
    editor.abrir([d], pid=7)
    assert _casa(editor) == "Q"


def test_o_mesmo_lugar_em_outra_pagina_nao_herda(editor):
    d = _lido()
    editor.abrir([d], pid=7)
    _alterar(editor)
    editor.fechar()
    editor.abrir([d], pid=8)
    assert editor.tabuleiro().casa(4, 4).simbolo != "Q"


def test_a_leitura_que_mudou_descarta_e_avisa(editor):
    d = _lido()
    editor.abrir([d], pid=7)
    _alterar(editor)
    editor.fechar()
    avisos = []
    editor.edicao_descartada.connect(lambda: avisos.append(1))
    editor.abrir([_lido("8/8/8/8/8/8/8/K6k")], pid=7)
    assert avisos == [1]
    assert not editor.tabuleiro().pode_desfazer


def test_sem_alteracao_nada_fica_guardado(editor):
    editor.abrir([_lido()], pid=7)
    editor.tabuleiro()
    editor.fechar()
    assert editor.alterados() == 0


def test_alterados_conta_os_guardados_e_os_abertos_e_esquecer_os_tira(editor):
    d = _lido()
    editor.abrir([d], pid=7)
    _alterar(editor)
    assert editor.alterados() == 1
    editor.fechar()
    assert editor.alterados() == 1
    editor.esquecer()
    assert editor.alterados() == 0


def test_o_cabecalho_diz_alterado(editor):
    editor.abrir([_lido()], pid=7)
    _alterar(editor)
    editor._mostrar()
    assert "alterado" in editor.cabecalho.text()


@pytest.fixture
def janela(app, tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path, "Livro", _pagina_sintetica(tmp_path / "p.png"))
    j = JanelaPrincipal()
    j.usar(projeto, pg.FonteDePaginas(projeto.fonte),
           LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    yield j
    j.close()


def test_ca_d2_fechar_com_alteracao_pergunta_e_nao_fecha_se_negar(janela, monkeypatch):
    janela.editor_diagrama.abrir([_lido()], pid=0)
    _alterar(janela.editor_diagrama)
    perguntas = []

    def nao(_j, _t, texto, *a):
        perguntas.append(texto)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", nao)
    assert janela._fechar_projeto() is False
    assert "1 diagrama(s)" in perguntas[0]
    assert janela.editor_diagrama.alterados() == 1
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    assert janela._edicoes_resolvidas() is True
    assert janela.editor_diagrama.alterados() == 0


def test_fechar_sem_alteracao_nao_pergunta(janela, monkeypatch):
    def nao_pergunte(*_a):
        raise AssertionError("não devia perguntar")

    monkeypatch.setattr(QMessageBox, "question", nao_pergunte)
    assert janela._edicoes_resolvidas() is True
