"""A conferência dos diagramas pela janela, sem tela: clique, correção, lado e gravação."""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from abbychess import pagina as pg  # noqa: E402
from abbychess.app import dialogo_diagrama as dd  # noqa: E402
from abbychess.app.janela import JanelaPrincipal  # noqa: E402
from abbychess.leitor import LeitorDoLivro  # noqa: E402
from abbychess.projeto import ProjetoDeLivro  # noqa: E402

from tests.test_diagramas import FEN, pagina_com_diagrama, sem_modelo  # noqa: E402
from tests.test_janela import _esperar  # noqa: E402

pytestmark = sem_modelo


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    fonte = pagina_com_diagrama(tmp_path / "pagina.png")
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Diagramas", fonte)
    j = JanelaPrincipal()
    j.projeto = projeto
    j.fonte = pg.FonteDePaginas(projeto.fonte)
    j.leitor = LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)
    j.seletor.setMaximum(j.fonte.total)
    j.ir_para_pagina(0, salvar=False)
    yield j
    if j.dialogo_diagrama is not None:
        j.dialogo_diagrama.close()
    j.close()


def _reconhecida(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    return janela


def _clicar_no_diagrama(app, janela) -> dd.DialogoDeDiagrama:
    x1, y1, x2, y2 = janela.diagramas[0].caixa
    janela.visor.diagrama_clicado.emit((x1 + x2) // 2, (y1 + y2) // 2)
    _esperar(app, janela)
    dialogo = janela.dialogo_diagrama
    assert dialogo is not None and dialogo.isVisible()
    return dialogo


def _clicar_na_casa(dialogo, linha: int, coluna: int, botao=Qt.MouseButton.LeftButton):
    centro = dialogo.posicao.retangulo(linha, coluna).center()
    QTest.mouseClick(dialogo.posicao, botao, Qt.KeyboardModifier.NoModifier, QPoint(centro))


def test_reconhecer_le_o_diagrama_e_poe_o_fen_no_texto(app, janela):
    _reconhecida(app, janela)
    assert len(janela.diagramas) == 1
    d = janela.diagramas[0]
    assert d.fen == FEN + " w - - 0 1"
    assert d.lado is None
    texto = janela.texto.toPlainText()
    assert f"[Diagrama 1: {FEN} w - - 0 1 — brancas a jogar (assumido: a página não diz)" in texto
    gravado = json.loads((janela.projeto.pasta / "paginas" / "0001.json").read_text(encoding="utf-8"))
    assert gravado["diagramas"][0]["fen"] == d.fen


def test_clique_abre_o_recorte_e_a_posicao_na_mesma_escala(app, janela):
    dialogo = _clicar_no_diagrama(app, _reconhecida(app, janela))
    lado = 8 * dd.LADO_CASA
    assert dialogo.recorte.pixmap().size().toTuple() == (lado, lado)
    assert dialogo.posicao.size().toTuple() == (lado, lado)
    assert dialogo.fen.text() == FEN + " w - - 0 1"
    # Sem legenda, nenhum lado vem escolhido e o aviso diz que o 'w' é suposição.
    assert not dialogo.radio_brancas.isChecked() and not dialogo.radio_pretas.isChecked()
    assert "não diz" in dialogo.origem_do_lado.text()
    assert any("Orientação não confirmada" in a for a in dialogo.avisos_do_diagrama())


def test_corrigir_casa_a_casa_escolher_o_lado_e_conferir(app, janela):
    dialogo = _clicar_no_diagrama(app, _reconhecida(app, janela))

    _clicar_na_casa(dialogo, 4, 4)                       # e4
    QTest.keyClicks(dialogo.posicao, "Q")                # dama branca
    _clicar_na_casa(dialogo, 0, 0, Qt.MouseButton.RightButton)   # esvazia a8
    dialogo.radio_pretas.click()
    dialogo.checks_roque["k"].click()
    esperado = "4k2r/pp3ppp/2n5/3q4/3PQ3/2N2N2/PP3PPP/R3K2R b k - 0 1"
    assert dialogo.fen.text() == esperado
    assert dialogo.btn_desfazer.isEnabled()

    dialogo.confirmar()

    assert not dialogo.isVisible()                       # era o único diagrama
    d = janela.diagramas[0]
    assert d.conferido and d.fen == esperado
    assert "pretas a jogar (informado na revisão)" in janela.texto.toPlainText()
    assert "não revisado" not in janela.texto.toPlainText()
    assert [x.fen for x in janela.projeto.carregar_diagramas(0)] == [esperado]
    # As duas casas corrigidas viram amostra, só na pasta do projeto.
    assert (janela.projeto.pasta / "diagramas" / "pecas" / "branca" / "Q").is_dir()


def test_paleta_pinta_e_desfazer_volta(app, janela):
    dialogo = _clicar_no_diagrama(app, _reconhecida(app, janela))
    dialogo.botoes_paleta["n"].click()
    _clicar_na_casa(dialogo, 5, 0)                       # a3
    assert dialogo.tabuleiro().casa(5, 0).simbolo == "n"
    _clicar_na_casa(dialogo, 5, 0)                       # de novo: alterna para vazia
    assert dialogo.tabuleiro().casa(5, 0).simbolo is None
    QTest.keyClick(dialogo, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert dialogo.tabuleiro().casa(5, 0).simbolo == "n"


def test_fechar_sem_conferir_nao_leva_nada(app, janela):
    dialogo = _clicar_no_diagrama(app, _reconhecida(app, janela))
    _clicar_na_casa(dialogo, 4, 4)
    QTest.keyClicks(dialogo.posicao, "Q")
    dialogo.reject()
    assert not janela.diagramas[0].conferido
    assert janela.diagramas[0].fen == FEN + " w - - 0 1"


def test_conferencia_sobrevive_a_reabrir_e_a_reconhecer(app, janela):
    dialogo = _clicar_no_diagrama(app, _reconhecida(app, janela))
    dialogo.radio_brancas.click()
    dialogo.confirmar()
    conferido = janela.diagramas[0].fen

    janela.ir_para_pagina(0)
    assert janela.diagramas[0].conferido and janela.diagramas[0].fen == conferido
    janela.reconhecer()
    _esperar(app, janela)
    assert janela.diagramas[0].conferido and janela.diagramas[0].lado == "w"
    assert "brancas a jogar (informado na revisão)" in janela.texto.toPlainText()


def test_pagina_antiga_le_o_diagrama_no_primeiro_clique(app, janela):
    """Página gravada antes da leitura: só as caixas; o clique lê e abre."""
    imagem = janela.imagem
    segmentada = pg.segmentar_pagina(imagem)
    arquivo = janela.projeto.pasta / "paginas" / "0001.json"
    arquivo.write_text(json.dumps({"pagina": 1, "boxes": [],
                                   "tabuleiros": [list(t) for t in segmentada.tabuleiros]}),
                       encoding="utf-8")
    janela.ir_para_pagina(0, salvar=False)
    assert len(janela.tabuleiros) == 1 and not janela.diagramas[0].lido
    assert "[Diagrama 1: ainda não lido]" in janela.texto.toPlainText()

    dialogo = _clicar_no_diagrama(app, janela)
    assert dialogo.fen.text() == FEN + " w - - 0 1"
    assert janela.diagramas[0].lido
