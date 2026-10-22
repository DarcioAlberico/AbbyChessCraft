"""A conferência dos diagramas pela janela, sem tela: clique, correção, lado e gravação."""

from __future__ import annotations

import json
import os
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from abbychess import diagramas as dg  # noqa: E402
from abbychess import pagina as pg  # noqa: E402
from abbychess.app import dialogo_diagrama as dd  # noqa: E402
from abbychess.app.janela import JanelaPrincipal  # noqa: E402
from abbychess.leitor import LeitorDoLivro  # noqa: E402
from abbychess.projeto import ProjetoDeLivro  # noqa: E402

from tests.test_diagramas import FEN, pagina_com_diagrama, sem_modelo  # noqa: E402
from tests.test_janela import _esperar  # noqa: E402
from tests.janela_util import atual, boxes, fila, mostrar, pulados, selecao  # noqa: E402,F401

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
    j.usar(projeto, pg.FonteDePaginas(projeto.fonte),
          LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    yield j
    if j.dialogo_diagrama is not None:
        j.dialogo_diagrama.close()
    j.close()


def _reconhecida(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    return janela


def _clicar_no_diagrama(app, janela) -> dd.DialogoDeDiagrama:
    x1, y1, x2, y2 = janela.pagina.diagramas[0].caixa
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
    assert len(janela.pagina.diagramas) == 1
    d = janela.pagina.diagramas[0]
    assert d.fen == FEN + " w - - 0 1"
    assert d.lado is None
    texto = _texto(janela)
    assert f"[Diagrama 1: {FEN} w - - 0 1 — brancas a jogar (assumido: a página não diz)" in texto
    janela.projeto.descarregar()
    gravado = json.loads(janela.projeto._arquivo_da_pagina(0).read_text(encoding="utf-8"))
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
    d = janela.pagina.diagramas[0]
    assert d.conferido and d.fen == esperado
    assert "pretas a jogar (informado na revisão)" in _texto(janela)
    assert "não revisado" not in _texto(janela)
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
    assert not janela.pagina.diagramas[0].conferido
    assert janela.pagina.diagramas[0].fen == FEN + " w - - 0 1"


def test_conferencia_sobrevive_a_reabrir_e_a_reconhecer(app, janela):
    dialogo = _clicar_no_diagrama(app, _reconhecida(app, janela))
    dialogo.radio_brancas.click()
    dialogo.confirmar()
    conferido = janela.pagina.diagramas[0].fen

    janela.ir_para_pagina(0)
    assert janela.pagina.diagramas[0].conferido and janela.pagina.diagramas[0].fen == conferido
    janela.reconhecer()
    _esperar(app, janela)
    assert janela.pagina.diagramas[0].conferido and janela.pagina.diagramas[0].lado == "w"
    assert "brancas a jogar (informado na revisão)" in _texto(janela)


def test_pagina_antiga_le_o_diagrama_no_primeiro_clique(app, janela):
    """Página gravada antes da leitura: só as caixas; o clique lê e abre."""
    imagem = janela.pagina.imagem
    segmentada = pg.segmentar_pagina(imagem)
    arquivo = janela.projeto.pasta / "paginas" / "0001.json"
    arquivo.write_text(json.dumps({"pagina": 1, "boxes": [],
                                   "tabuleiros": [list(t) for t in segmentada.tabuleiros]}),
                       encoding="utf-8")
    janela.ir_para_pagina(0)
    assert len(janela.pagina.tabuleiros) == 1 and not janela.pagina.diagramas[0].lido
    assert "[Diagrama 1: ainda não lido]" in _texto(janela)

    dialogo = _clicar_no_diagrama(app, janela)
    assert dialogo.fen.text() == FEN + " w - - 0 1"
    assert janela.pagina.diagramas[0].lido


def test_lote_le_o_diagrama_e_a_pagina_nao_fica_por_ler(app, janela, monkeypatch):
    """O lote (Ctrl+Shift+F5) lê o diagrama como o F5: a página volta com o FEN."""
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("1", True))
    janela.reconhecer_livro()
    _esperar(app, janela)
    assert janela.projeto.paginas_lidas() == [0]
    [d] = janela.pagina.diagramas
    assert d.lido and d.fen == FEN + " w - - 0 1" and d.lado is None
    texto = _texto(janela)
    assert "ainda não lido" not in texto
    assert f"[Diagrama 1: {FEN} w - - 0 1 — brancas a jogar (assumido: a página não diz)" in texto


@pytest.fixture
def janela_com_legenda(app, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    fonte = pagina_com_diagrama(tmp_path / "pagina.png", legenda="pretas jogam")
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Legenda", fonte)
    j = JanelaPrincipal()
    j.usar(projeto, pg.FonteDePaginas(projeto.fonte),
          LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    yield j
    j.close()


def _corrigir(app, janela, gid: int, char: str) -> None:
    janela.pagina.mostrar(gid)
    janela.treino.campo.setText(char)
    janela.treino.pedir_so_corrigir()
    _esperar(app, janela)


def test_corrigir_a_legenda_muda_o_lado_sem_f5_e_desfaz_junto(app, janela_com_legenda):
    """O "g" corrigido em "pretas jo9am" faz o lado sair da legenda na hora, e o Ctrl+Z
    da correção o leva de volta a assumido."""
    janela = _reconhecida(app, janela_com_legenda)
    p = janela.pagina
    caixa = p.diagramas[0].caixa
    legenda = sorted((b for b in p.modelo.boxes if caixa[3] < b.entry.y1 < caixa[3] + 120),
                     key=lambda b: b.entry.x1)
    assert len(legenda) == len("pretasjogam")
    for b, c in zip(legenda, "pretasjo9am"):
        _corrigir(app, janela, b.gid, c)
    casas = p.diagramas[0].casas
    assert p.diagramas[0].lado is None

    _corrigir(app, janela, legenda[8].gid, "g")

    d = p.diagramas[0]
    assert (d.lado, d.lado_origem, d.titulo) == ("b", dg.LADO_DA_LEGENDA, "pretas jogam")
    assert d.casas == casas and d.fen == FEN + " b - - 0 1"
    assert "pretas a jogar (da legenda)" in _texto(janela)

    p.desfazer()
    _esperar(app, janela)
    assert p.diagramas[0].lado is None
    assert "(assumido: a página não diz)" in _texto(janela)
    p.refazer()
    _esperar(app, janela)
    assert p.diagramas[0].lado == "b"


def test_lado_informado_na_conferencia_nao_muda_com_a_legenda(app, janela_com_legenda):
    janela = _reconhecida(app, janela_com_legenda)
    p = janela.pagina
    caixa = p.diagramas[0].caixa
    legenda = sorted((b for b in p.modelo.boxes if caixa[3] < b.entry.y1 < caixa[3] + 120),
                     key=lambda b: b.entry.x1)
    p.modelo.diagramas = [replace(p.modelo.diagramas[0], lado="w",
                                  lado_origem=dg.LADO_DO_USUARIO)]
    for b, c in zip(legenda, "pretasjogam"):
        _corrigir(app, janela, b.gid, c)
    assert (p.diagramas[0].lado, p.diagramas[0].lado_origem) == ("w", dg.LADO_DO_USUARIO)


def _texto(janela) -> str:
    """O painel de texto, sem esperar o relógio que o refaz depois da última mudança."""
    janela.pintar_texto()
    return janela.texto.toPlainText()


def test_a_conferencia_valida_pelos_lances_e_oferece_o_roque_inferido(app):
    import numpy as np

    from abbychess import lances as lc
    from tests.test_diagramas import _lido

    linha = lc.primeira_linha("12.O-O-O Cxd4 13.Cxd4", "pt")
    dialogo = dd.DialogoDeDiagrama(np.full((600, 800), 255, np.uint8), [_lido()], 0,
                                   linhas=[linha])
    try:
        assert any(a.startswith("Confiável pelos lances") for a in dialogo.avisos_do_diagrama())
        assert "KQkq" in dialogo.roque_inferido.text()
        assert dialogo.fen.text().split()[2] == "-"           # inferido não é afirmado
        assert "[SetUp \"1\"]" in dialogo.pgn() and "12. O-O-O Nxd4" in dialogo.pgn()

        dialogo.btn_roque_inferido.click()
        assert dialogo.fen.text().split()[2] == "KQkq"
        assert not dialogo.btn_roque_inferido.isEnabled()

        _clicar_na_casa(dialogo, 7, 0, Qt.MouseButton.RightButton)      # tira a torre de a1
        assert any("12.O-O-O do texto não é legal aqui" in a
                   for a in dialogo.avisos_do_diagrama())
    finally:
        dialogo.close()