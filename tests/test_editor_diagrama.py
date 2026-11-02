"""O tabuleiro do editor Diagrama (`abbychess/app/editor_diagrama.py`, SPEC §10) pelo teclado e
sem a fonte de diagrama: as setas andam pelas casas, a letra põe a peça, Delete esvazia, e o
FEN do editor acompanha. Sem os modelos de diagrama (o tabuleiro lido é montado do FEN)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from core.tabuleiro_edicao import TabuleiroEdicao  # noqa: E402

from abbychess.app import editor_diagrama as dd  # noqa: E402
from abbychess.app import estilo  # noqa: E402

from tests.ajudantes import FEN, _lido  # noqa: E402

Tecla = Qt.Key


@pytest.fixture
def editor(app):
    editor = dd.EditorDeDiagrama()
    editor.abrir([_lido()], 0)
    editor.show()
    editor.posicao.setFocus()
    yield editor
    editor.close()


def _pecas(editor) -> str:
    """As peças do FEN que o editor mostra."""
    return editor.fen.text().split()[0]


def _teclas(widget, *teclas) -> None:
    for tecla in teclas:
        if isinstance(tecla, str):
            QTest.keyClicks(widget, tecla)
        else:
            QTest.keyClick(widget, tecla)


def test_as_setas_comecam_em_a8_e_a_letra_poe_a_peca_na_casa(editor):
    assert _pecas(editor) == FEN
    _teclas(editor.posicao, Tecla.Key_Right, "Q")          # de a8 a b8: dama branca
    assert _pecas(editor) == "rQ2k2r/pp3ppp/2n5/3q4/3P4/2N2N2/PP3PPP/R3K2R"
    _teclas(editor.posicao, Tecla.Key_Down, Tecla.Key_Down, Tecla.Key_Left, "n")   # a6
    assert _pecas(editor) == "rQ2k2r/pp3ppp/n1n5/3q4/3P4/2N2N2/PP3PPP/R3K2R"
    assert editor.tabuleiro().casa(2, 0).corrigida


def test_as_setas_param_na_borda_do_tabuleiro(editor):
    _teclas(editor.posicao, Tecla.Key_Up, Tecla.Key_Left)           # já em a8: fica
    _teclas(editor.posicao, Tecla.Key_Delete)
    assert _pecas(editor).startswith("4k2r/")                        # a torre de a8 saiu
    _teclas(editor.posicao, *[Tecla.Key_Down] * 9, *[Tecla.Key_Right] * 9)   # até h1, e para
    _teclas(editor.posicao, Tecla.Key_Backspace)
    assert _pecas(editor).endswith("/R3K3")                          # a torre de h1 saiu


def test_espaco_esvazia_e_a_tecla_que_nao_e_peca_nao_muda_nada(editor):
    _teclas(editor.posicao, Tecla.Key_Right, Tecla.Key_Right, Tecla.Key_Right, Tecla.Key_Right)
    _teclas(editor.posicao, "x", "1", Tecla.Key_Return)              # e8: nada disso é peça
    assert _pecas(editor) == FEN
    QTest.keyClick(editor.posicao, Tecla.Key_Q, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(editor.posicao, Tecla.Key_N, Qt.KeyboardModifier.AltModifier)
    assert _pecas(editor) == FEN                                     # o atalho não é peça
    _teclas(editor.posicao, Tecla.Key_Space)
    assert _pecas(editor) == "r6r/pp3ppp/2n5/3q4/3P4/2N2N2/PP3PPP/R3K2R"   # o rei saiu


def test_sem_casa_escolhida_a_letra_nao_poe_peca(editor):
    _teclas(editor.posicao, "Q", Tecla.Key_Delete)
    assert _pecas(editor) == FEN


def test_com_as_pretas_embaixo_as_setas_andam_como_se_ve(app):
    """Virado (as pretas embaixo), a8 fica no canto de baixo à direita: a seta para a
    esquerda vai a b8, e a para cima, a b7."""
    tabuleiro = dd.TabuleiroConferivel(TabuleiroEdicao.de_fen(FEN), "preta")
    tabuleiro.show()
    try:
        _teclas(tabuleiro, Tecla.Key_Left, "N", Tecla.Key_Up, Tecla.Key_Up, "B")
        assert tabuleiro.tabuleiro.casa(0, 1).simbolo == "N"          # b8
        assert tabuleiro.tabuleiro.casa(2, 1).simbolo == "B"          # b6
        _teclas(tabuleiro, Tecla.Key_Right, "p")                      # a6
        _teclas(tabuleiro, Tecla.Key_Down, Tecla.Key_Delete)             # a7 esvazia
        assert (tabuleiro.tabuleiro.tabuleiro().board_fen()
                == "rN2k2r/1p3ppp/pBn5/3q4/3P4/2N2N2/PP3PPP/R3K2R")
    finally:
        tabuleiro.close()


def test_sem_a_fonte_de_diagrama_o_tabuleiro_sai_com_as_figurinas(app, monkeypatch):
    """Sem a fonte de diagrama do PyBoxEditor (o desenho falha), as casas lisas e as peças em
    figurinas Unicode."""
    from core import render_diagrama

    def sem_a_fonte(*_a, **_k):
        raise OSError("a fonte de diagrama não está nesta máquina")

    monkeypatch.setattr(render_diagrama, "desenhar", sem_a_fonte)
    tabuleiro = dd.TabuleiroConferivel(TabuleiroEdicao.de_fen("4k3/8/8/8/8/8/8/4K3"))
    imagem = tabuleiro.grab().toImage()

    def cores(linha, coluna):
        r = tabuleiro.retangulo(linha, coluna)
        return {imagem.pixelColor(x, y).name() for x in range(r.left(), r.right() + 1)
                for y in range(r.top(), r.bottom() + 1)}

    assert cores(0, 0) == {dd.CASA_CLARA.name()}                      # a8, vazia e clara
    assert cores(0, 1) == {dd.CASA_ESCURA.name()}                     # b8, vazia e escura
    rei = cores(0, 4)                                                 # e8: o ♚ por cima
    assert dd.CASA_CLARA.name() in rei and estilo.TINTA.name() in rei
    assert estilo.TINTA.name() in cores(7, 4)                         # e1: o ♔
