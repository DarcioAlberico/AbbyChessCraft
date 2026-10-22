"""A conferência dos diagramas pela janela, sem tela: clique, correção, lado e gravação.

Desde o passo H a conferência é o editor Diagrama do Inspetor (§10), não um diálogo."""

from __future__ import annotations

import json
import os
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRectF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from abbychess import diagramas as dg  # noqa: E402
from abbychess import pagina as pg  # noqa: E402
from abbychess.app import editor_diagrama as dd  # noqa: E402
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
    j.close()


def _reconhecida(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    return janela


def _clicar_no_diagrama(app, janela) -> dd.EditorDeDiagrama:
    x1, y1, x2, y2 = janela.pagina.diagramas[0].caixa
    janela.visor.diagrama_clicado.emit((x1 + x2) // 2, (y1 + y2) // 2)
    _esperar(app, janela)
    editor = janela.editor_diagrama
    assert editor.aberto and janela.inspetor.atual() == "diagrama"
    return editor


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


def _vista(janela):
    return janela.visor.mapToScene(janela.visor.viewport().rect()).boundingRect()


def test_clique_abre_o_editor_e_a_imagem_enquadra_o_impresso(app, janela):
    janela.resize(1366, 768)
    janela.show()
    _reconhecida(app, janela)
    janela.visor.zoom_pagina()
    escala_da_pagina = janela.visor.escala()
    dialogo = _clicar_no_diagrama(app, janela)
    lado = 8 * dd.LADO_CASA
    assert dialogo.posicao.size().toTuple() == (lado, lado)
    x1, y1, x2, y2 = janela.pagina.diagramas[0].caixa
    assert _vista(janela).contains(QRectF(x1, y1, x2 - x1, y2 - y1))
    assert janela.visor.escala() > escala_da_pagina
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

    assert dialogo.diagrama.conferido                    # era o único diagrama
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
    # Com o foco no editor, o Ctrl+Z (o desfazer da janela) é o do tabuleiro, não o da página.
    dialogo.posicao.setFocus()
    janela.acao_desfazer.trigger()
    assert dialogo.tabuleiro().casa(5, 0).simbolo == "n"


def test_fechar_sem_conferir_nao_leva_nada(app, janela):
    dialogo = _clicar_no_diagrama(app, _reconhecida(app, janela))
    _clicar_na_casa(dialogo, 4, 4)
    QTest.keyClicks(dialogo.posicao, "Q")
    dialogo.fechar()
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
    from abbychess import lances as lc
    from tests.test_diagramas import _lido

    linha = lc.primeira_linha("12.O-O-O Cxd4 13.Cxd4", "pt")
    dialogo = dd.EditorDeDiagrama()
    dialogo.abrir([_lido()], 0, [linha])
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

# ----------------------------------------------------------------------
# O editor no Inspetor e a aba Diagramas (passo H)
# ----------------------------------------------------------------------

def test_ca_10_2_com_a_conferencia_aberta_a_imagem_aceita_zoom_e_rolagem(app, janela):
    janela.resize(1366, 768)
    janela.show()
    editor = _clicar_no_diagrama(app, _reconhecida(app, janela))
    visor = janela.visor
    antes = visor.escala()
    visor.zoom_mais()
    assert visor.escala() > antes
    barra = visor.verticalScrollBar()
    if barra.maximum() > 0:
        valor = barra.value()
        visor.rolar_tela(+1 if valor < barra.maximum() else -1)
        assert barra.value() != valor
    # A conferência continua onde estava, sem gravar nada.
    assert editor.aberto and janela.inspetor.atual() == "diagrama"
    assert not janela.pagina.diagramas[0].conferido


def test_pgdn_na_ponta_do_livro_avisa_e_fica(app, janela):
    editor = _clicar_no_diagrama(app, _reconhecida(app, janela))
    editor.ir(+1)
    assert editor.aberto and editor.atual == 0
    assert "Não há diagrama depois deste no livro" in janela.statusBar().currentMessage()


def test_estado_e_filtros_da_aba():
    from abbychess import lances as lc
    from abbychess.app import painel_diagramas as pd
    from tests.test_diagramas import _lido

    lido, conferido = _lido(), replace(_lido(), conferido=True)
    duvidoso = replace(_lido(), motivo="casa duvidosa")
    ilegal = replace(_lido(), validacao=lc.Validacao(lc.ILEGAL, 2, 0, "1.Cd2 do texto não é "
                                                     "legal aqui"))
    pelos = replace(_lido(), validacao=lc.Validacao(lc.CONFIAVEL, 2, 2))
    por_ler = dg.DiagramaLido((0, 0, 10, 10))
    estados = [pd.estado(d) for d in (lido, conferido, duvidoso, ilegal, pelos, por_ler)]
    assert estados == [pd.CONFIAVEL, pd.CONFERIDO, pd.SEM_CONFIANCA, pd.LANCE_ILEGAL,
                       pd.PELOS_LANCES, pd.NAO_LIDO]
    todos = (lido, conferido, duvidoso, ilegal, pelos, por_ler)
    assert [pd.passa(d, "conferidos") for d in todos] == [False, True, False, False, False, False]
    assert [pd.passa(d, "sem_confianca") for d in todos] == [False, False, True, True, False, False]
    assert [pd.passa(d, "por_conferir") for d in todos] == [True, False, True, True, True, True]


def test_aba_diagramas_lista_o_livro_e_abre_no_editor(app, janela):
    _reconhecida(app, janela)
    janela.vista.setCurrentWidget(janela.painel_diagramas)
    _esperar(app, janela)
    painel = janela.painel_diagramas
    assert painel.itens() == [(0, 0)]                     # por conferir
    assert "1 de 1" in painel.contador.text()

    painel.definir_filtro("conferidos")
    assert painel.itens() == []
    painel.definir_filtro("todos")
    painel.grade.itemActivated.emit(painel.grade.item(0))
    _esperar(app, janela)
    assert janela.editor_diagrama.aberto and janela.inspetor.atual() == "diagrama"

    janela.editor_diagrama.radio_brancas.click()
    janela.editor_diagrama.confirmar()
    _esperar(app, janela)
    painel.definir_filtro("conferidos")
    assert painel.itens() == [(0, 0)]

def test_reabrir_na_mesma_pagina_mantem_o_que_estava_em_edicao(app, janela):
    editor = _clicar_no_diagrama(app, _reconhecida(app, janela))
    _clicar_na_casa(editor, 4, 4)
    QTest.keyClicks(editor.posicao, "Q")
    janela.conferencia.conferir(0)                     # outro clique, o F8, a aba
    _esperar(app, janela)
    assert editor.tabuleiro().casa(4, 4).simbolo == "Q"


def test_aplicar_num_diagrama_que_sumiu_nao_grava(app, janela):
    editor = _clicar_no_diagrama(app, _reconhecida(app, janela))
    assert janela.conferencia.aplicar((1, 1, 2, 2), editor.tabuleiro(), False) is False
    assert not janela.pagina.diagramas[0].conferido
    assert "reabra" in janela.statusBar().currentMessage()


def test_ctrl_z_sem_casa_editada_desfaz_a_conferencia_e_o_editor_acompanha(app, janela):
    editor = _clicar_no_diagrama(app, _reconhecida(app, janela))
    editor.radio_brancas.click()
    editor.confirmar()
    assert janela.pagina.diagramas[0].conferido and editor.diagrama.conferido
    editor.posicao.setFocus()
    janela.acao_desfazer.trigger()
    _esperar(app, janela)
    assert not janela.pagina.diagramas[0].conferido
    assert editor.aberto and not editor.diagrama.conferido     # sincronizado, não fechado