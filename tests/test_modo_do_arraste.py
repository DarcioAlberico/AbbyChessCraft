"""CA-U2 (SPEC-pagina-perfeita, U-2; T1, bloco 3): os três modos do arraste da Imagem (marcar
glifo, editor de áreas, borracha) mostram um rótulo fixo enquanto ligados, cada um com o seu
cursor, e o Esc sai do modo.

Antes, o aviso de cada modo sumia da barra em alguns segundos, os três tinham a mesma cruz, e
o Esc não desligava nenhum: não se via que o arraste ia apagar a imagem em vez de rolar.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tests.fixturas_espaco import janela  # noqa: E402,F401,F811


def _modos(j):
    return (("Marcar glifo", j.acao_modo_treino), ("Editor de áreas", j.acao_areas),
            ("Borracha", j.acao_borracha))


def _cursor(j):
    return j.visor.viewport().cursor()


def test_cada_modo_mostra_o_rotulo_fixo_e_sai_com_esc(janela):  # noqa: F811
    j = janela
    rotulo = j.modo_do_arraste.rotulo
    assert not rotulo.isVisible()
    for nome, acao in _modos(j):
        acao.trigger()
        QApplication.processEvents()
        assert acao.isChecked() and rotulo.isVisible(), nome
        assert rotulo.text() == f"{nome} · Esc sai", rotulo.text()
        j.statusBar().showMessage("outra coisa", 10)         # a mensagem passa; o rótulo fica
        QApplication.processEvents()
        assert rotulo.isVisible()
        j.fechar_sobreposicao()                               # o Esc
        QApplication.processEvents()
        assert not acao.isChecked() and not rotulo.isVisible(), nome
        assert _cursor(j).shape() == Qt.CursorShape.OpenHandCursor, nome


def test_cada_modo_tem_o_seu_cursor(janela):  # noqa: F811
    j = janela
    vistos = []
    for nome, acao in _modos(j):
        acao.trigger()
        QApplication.processEvents()
        cursor = _cursor(j)
        assert cursor.shape() == Qt.CursorShape.BitmapCursor, nome
        vistos.append(cursor.pixmap().toImage())
        acao.trigger()                                        # desliga
    assert vistos[0] != vistos[1] != vistos[2] != vistos[0]


def test_trocar_de_modo_troca_o_rotulo(janela):  # noqa: F811
    j = janela
    j.acao_modo_treino.trigger()
    j.acao_borracha.trigger()                                 # um modo só: o outro sai
    QApplication.processEvents()
    assert not j.acao_modo_treino.isChecked()
    assert j.modo_do_arraste.rotulo.text() == "Borracha · Esc sai"


def test_o_esc_fecha_antes_a_selecao_e_depois_o_modo(janela):  # noqa: F811
    """A ordem da §3.4 (regra 4): o que está mais por cima sai primeiro."""
    j = janela
    j.acao_modo_treino.trigger()
    j.pagina.selecao = {0}
    j.fechar_sobreposicao()
    assert not j.pagina.selecao and j.acao_modo_treino.isChecked()
    j.fechar_sobreposicao()
    assert not j.acao_modo_treino.isChecked()


def test_o_rotulo_segue_a_tecla_do_perfil(janela, monkeypatch):  # noqa: F811
    from abbychess.app import modo_do_arraste as md

    j = janela
    monkeypatch.setattr(md.teclado, "tecla", lambda id_, sem="": "F12")
    j.acao_borracha.trigger()
    QApplication.processEvents()
    assert j.modo_do_arraste.rotulo.text() == "Borracha · F12 sai"
