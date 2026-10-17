"""O Documento e a sincronia do passo A3 (SPEC §6.1, §6.2; CA-6.1, CA-6.5, a Linha do CA-3.2).

A vista sozinha (`VistaDoDocumento` com documentos montados à mão: o mapa, os diagramas, o
realce, as margens, o corpo) e na janela (o clique numa palavra destaca os glifos na Imagem;
a Imagem e a fila levam o cursor ao glifo; montar de novo não perde o lugar; a faixa Linha).
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QTextCharFormat  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from abbychess import texto as tx  # noqa: E402
from abbychess.app.documento import VistaDoDocumento  # noqa: E402

from tests.janela_util import atual, boxes, fila  # noqa: E402
from tests.test_espaco import _abrir, _dentro, janela, lida, sim  # noqa: E402,F401
from tests.test_janela import _esperar  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _doc(*blocos, chars=None):
    return tx.Documento(tuple(blocos), chars or {})


def _bloco(id_, funcao, *linhas):
    return tx.Bloco(id_, None, funcao, tuple(tx.Linha(tuple(tx.Palavra(tuple(p)) for p in ln))
                                             for ln in linhas))


CHARS = {1: "a", 2: "b", 3: "c", 4: "d", 5: "e", 9: "C", 10: "a", 11: "p"}


def _vista(app, documento=None, **k):
    v = VistaDoDocumento()
    v.resize(500, 300)
    v.montar(documento or _doc(_bloco("b0", "cabecalho", [[9, 10, 11]]),
                               _bloco("b1", "texto", [[1, 2], [3]], [[4, 5]]), chars=CHARS), **k)
    return v


# ----------------------------------------------------------------------
# A vista sozinha
# ----------------------------------------------------------------------

def test_o_mapa_leva_cada_posicao_ao_gid_e_volta(app):
    v = _vista(app)
    assert v.toPlainText() == "Cap\nab c\nde"            # uma linha impressa por parágrafo
    for gid in (9, 1, 2, 3, 4, 5):
        posicao = v.posicao_do_gid(gid)
        assert v.gid_na_posicao(posicao) == gid           # o caractere à direita do cursor
    assert v.palavra_de(2) == [1, 2] and v.linha_de(3) == [1, 2, 3]
    assert v.gid_na_posicao(v.posicao_do_gid(2) + 1) == 2   # no espaço depois: o anterior


def test_montar_de_novo_nao_deixa_documentos_vivos(app):
    """Cada montagem é um QTextDocument novo; o anterior (com as imagens dos diagramas e a
    coleção de formatos) tem de sair, ou a memória cresce a cada mudança da página."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtGui import QTextDocument

    v = _vista(app)
    for _ in range(20):
        v.remontar()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert len(v.findChildren(QTextDocument)) <= 2         # o de agora (e o padrão do Qt)


def test_ctrl_shift_h_oculta_as_margens_e_o_realce_desliga(app):
    v = _vista(app, estados={1: "pendente"})
    v.alternar_margens()
    assert "Cap" not in v.toPlainText()
    v.alternar_margens()
    assert v.toPlainText().startswith("Cap")

    def fundo(gid):
        cursor = v.textCursor()
        cursor.setPosition(v.posicao_do_gid(gid) + 1)
        return cursor.charFormat().background().style()
    assert fundo(1) != Qt.BrushStyle.NoBrush and fundo(2) == Qt.BrushStyle.NoBrush
    v.definir_realce(False)
    assert fundo(1) == Qt.BrushStyle.NoBrush


def test_o_desconhecido_tem_ondulado_e_o_virtual_pontilhado(app):
    v = _vista(app, desconhecidos={4}, virtuais={5})

    def sublinhado(gid):
        cursor = v.textCursor()
        cursor.setPosition(v.posicao_do_gid(gid) + 1)
        return cursor.charFormat().underlineStyle()
    assert sublinhado(4) == QTextCharFormat.UnderlineStyle.WaveUnderline
    assert sublinhado(5) == QTextCharFormat.UnderlineStyle.DotLine
    assert sublinhado(1) == QTextCharFormat.UnderlineStyle.NoUnderline


def test_o_corpo_muda_com_limites_e_volta_ao_padrao(app):
    v = _vista(app)
    v.mudar_corpo(+3)
    assert v.corpo == 14
    for _ in range(40):
        v.mudar_corpo(+1)
    assert v.corpo == 28
    v.mudar_corpo(0)
    assert v.corpo == 11


def test_e_somente_leitura(app):
    v = _vista(app)
    v.setFocus()
    QTest.keyClicks(v, "zzz")
    assert v.toPlainText() == "Cap\nab c\nde"


def test_o_diagrama_entra_com_o_desenho_a_linha_o_estado_e_copiar_fen(app):
    """O diagrama no lugar dele (a atomicidade numa seleção que o cruza é do D1, com a
    edição: o Documento é só leitura até lá)."""
    from core.diagrama_modelo import Casa

    from abbychess.diagramas import DiagramaLido

    casas = [Casa(n // 8, n % 8, "K" if n == 60 else ("k" if n == 4 else "")) for n in range(64)]
    d = DiagramaLido((0, 0, 100, 100), casas, lado="w", id="d0")
    documento = _doc(_bloco("b0", "texto", [[1, 2]]),
                     tx.Bloco("b1", None, "diagrama", diagrama_id="d0"), chars=CHARS)
    v = _vista(app, documento, diagramas=[d])
    assert v.ids_dos_diagramas() == {"d0"}
    assert "[Diagrama 1: " + d.fen in v.toPlainText()
    assert "lido, não conferido" in v.toPlainText() and "Copiar FEN" in v.toPlainText()
    v.copiar_fen("d0")
    assert QApplication.clipboard().text() == d.fen


# ----------------------------------------------------------------------
# Na janela: a sincronia (§6.2) e o lugar (CA-6.5)
# ----------------------------------------------------------------------

@pytest.fixture
def lida_a_mao(app, janela):  # noqa: F811
    from tests.test_janela_areas_e_verificacao import _ler_a_mao

    _ler_a_mao(app, janela)
    janela.pintar_texto()
    return janela


def _clicar_no_gid(app, j, gid):
    texto = j.texto
    cursor = texto.textCursor()
    cursor.setPosition(texto.posicao_do_gid(gid) + 1)
    ponto = texto.cursorRect(cursor).center() - QPoint(2, 0)
    QTest.mouseClick(texto.viewport(), Qt.MouseButton.LeftButton, pos=ponto)
    app.processEvents()


def test_ca_6_1_clicar_numa_palavra_destaca_os_glifos_dela_na_imagem(app, lida_a_mao):
    j = lida_a_mao
    alvo = j.pagina.gids[4]
    palavra = j.texto.palavra_de(alvo)
    _clicar_no_gid(app, j, alvo)
    destaque = j.visor._palavra_do_documento               # o destaque gravado no item
    escolhidos = [boxes(j)[j.pagina.indice_de(g)] for g in palavra]
    esperado = (min(b.x1 for b in escolhidos), min(b.y1 for b in escolhidos),
                max(b.x2 for b in escolhidos), max(b.y2 for b in escolhidos))
    r = destaque.rect()
    assert abs(r.left() - esperado[0]) <= 8 and abs(r.right() - esperado[2]) <= 8   # a margem
    assert atual(j) == alvo and j.inspetor.atual() == "glifo"


def test_a_imagem_e_a_fila_levam_o_cursor_do_documento_ao_glifo(app, lida):  # noqa: F811
    j = lida
    j.pintar_texto()
    j.visor.box_clicado.emit(7)                            # o clique na Imagem
    assert j.texto.gid_no_cursor() == j.pagina.gids[7]
    j.pagina.escolher(j.pagina.gids[2])
    j.fila.andar(+1)                                       # Alt+↓
    assert j.texto.gid_no_cursor() == atual(j)


def test_ca_6_5_montar_de_novo_mantem_o_cursor_e_a_rolagem(app, lida_a_mao):
    j = lida_a_mao
    j.texto.resize(200, 60)                                # para haver o que rolar
    j.texto.corpo = 26
    j.texto.remontar()
    alvo = j.pagina.gids[9]
    j.texto.ir_ao_gid(alvo)
    barra = j.texto.verticalScrollBar()
    rolagem = barra.value()
    # Outra ação muda a página (corrigir um glifo pelo Glifo): o documento é montado de novo.
    j.pagina.escolher(j.pagina.gids[0])
    j.treino.campo.setText("z")
    j.treino.pedir_so_corrigir()
    _esperar(app, j)
    j.texto.ir_ao_gid(alvo, rolar=False)                   # o cursor seguiu a fila: volto
    barra.setValue(rolagem)
    j.pintar_texto()
    assert j.texto.gid_no_cursor() == alvo and barra.value() == rolagem


def _caixa_de(j, gids):
    escolhidos = [boxes(j)[j.pagina.indice_de(g)] for g in gids]
    return (min(b.x1 for b in escolhidos), min(b.y1 for b in escolhidos),
            max(b.x2 for b in escolhidos), max(b.y2 for b in escolhidos))


def test_o_cursor_no_documento_destaca_a_palavra_certa_e_mostra_a_linha(app, lida_a_mao):
    j = lida_a_mao
    j.texto.setFocus()
    j.texto.ir_ao_gid(j.pagina.gids[0], rolar=False)
    QTest.keyClick(j.texto, Qt.Key.Key_Down)               # a linha seguinte
    app.processEvents()
    gid = j.texto.gid_no_cursor()
    x1, y1, x2, y2 = _caixa_de(j, j.texto.palavra_de(gid))
    r = j.visor._palavra_do_documento.rect()
    assert abs(r.left() - (x1 - 4)) < 1 and abs(r.right() - (x2 + 4)) < 1
    linha = [j.pagina.gids[j.pagina.boxes.index(b)] for b in j.linha._boxes]
    assert gid in linha and linha == j.texto.linha_de(gid)


def test_o_cursor_do_documento_nao_apaga_a_palavra_em_verificacao(app, lida_a_mao):
    from core import lexico

    j = lida_a_mao
    j.verificador.lexico = lexico.Lexico(palavras={"abc"})
    j.fila.definir("palavras")
    contorno = j.visor._palavra
    assert contorno is not None
    j.texto.setFocus()
    j.texto.ir_ao_gid(j.pagina.gids[0], rolar=False)
    QTest.keyClick(j.texto, Qt.Key.Key_Down)
    app.processEvents()
    assert j.visor._palavra is contorno and j.visor._palavra_do_documento is not None


def test_sem_seguir_o_cursor_do_documento_nao_rola_a_imagem(app, lida_a_mao):
    j = lida_a_mao
    j.visor.definir_zoom(4.0)                              # a página maior que a vista
    barra = j.visor.verticalScrollBar()
    for seguir, deve_rolar in ((False, False), (True, True)):
        j.acao_seguir.setChecked(seguir)
        barra.setValue(0)
        j.texto.setFocus()
        j.texto.ir_ao_gid(j.pagina.gids[0], rolar=False)
        QTest.keyClick(j.texto, Qt.Key.Key_Down)           # para a última linha, lá embaixo
        app.processEvents()
        assert (barra.value() > 0) is deve_rolar, seguir


def test_o_clique_no_branco_depois_da_linha_nao_escolhe_glifo(app, lida_a_mao):
    j = lida_a_mao
    j.texto.resize(600, 300)
    antes = atual(j)
    fim = j.texto.posicao_do_gid(j.texto.linha_de(j.pagina.gids[0])[-1]) + 1
    cursor = j.texto.textCursor()
    cursor.setPosition(fim)
    ponto = j.texto.cursorRect(cursor).center() + QPoint(200, 0)
    QTest.mouseClick(j.texto.viewport(), Qt.MouseButton.LeftButton, pos=ponto)
    app.processEvents()
    assert atual(j) == antes


def test_a_linha_sem_o_mapa_do_documento_vem_da_geometria(app, lida):  # noqa: F811
    j = lida
    j.texto._linha_do_gid = {}                             # o instante antes de montar
    j._mostrar_a_linha()
    linha = [j.pagina.gids[j.pagina.boxes.index(b)] for b in j.linha._boxes]
    assert atual(j) in linha and len(linha) > 1


def test_montar_de_novo_mantem_a_selecao(app, lida_a_mao):
    j = lida_a_mao
    cursor = j.texto.textCursor()
    inicio = j.texto.posicao_do_gid(j.pagina.gids[1])
    cursor.setPosition(inicio)
    cursor.setPosition(inicio + 5, cursor.MoveMode.KeepAnchor)
    j.texto.setTextCursor(cursor)
    selecionado = j.texto.textCursor().selectedText()
    j.pintar_texto()
    assert j.texto.textCursor().selectedText() == selecionado


def test_ctrl_f5_esconde_e_mostra_a_linha(app, lida):  # noqa: F811
    j = lida
    assert j.linha.isVisible()
    QTest.keyClick(j.visor, Qt.Key.Key_F5, Qt.KeyboardModifier.ControlModifier)
    assert not j.linha.isVisible() and not j.acao_linha.isChecked()
    QTest.keyClick(j.visor, Qt.Key.Key_F5, Qt.KeyboardModifier.ControlModifier)
    assert j.linha.isVisible()


def test_a_linha_mostra_a_linha_do_glifo_atual(app, lida):  # noqa: F811
    j = lida
    j.pintar_texto()
    assert j.linha._boxes and atual(j) in [j.pagina.gids[j.pagina.boxes.index(b)]
                                         for b in j.linha._boxes]
    assert j.linha.escala > 0


def test_o_zoom_no_documento_muda_o_corpo_e_nao_a_imagem(app, lida_a_mao):
    j = lida_a_mao
    escala = j.visor.escala()
    j.vista.setCurrentWidget(j.painel_do_documento)
    j.texto.setFocus()
    app.processEvents()
    padrao = j.texto.corpo_padrao                         # 10 em 1366, 11 de 1600 em diante
    QTest.keyClick(j.texto, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
    assert j.texto.corpo == padrao + 1 and abs(j.visor.escala() - escala) < 1e-9
    QTest.keyClick(j.texto, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
    assert j.texto.corpo == padrao


def test_ctrl_shift_h_na_janela(app, lida_a_mao):
    j = lida_a_mao
    j.texto.setFocus()
    QTest.keyClick(j.texto, Qt.Key.Key_H,
                   Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    assert not j.texto.mostrar_margens and not j.acao_margens.isChecked()


def test_andar_na_fila_nao_muda_o_texto_do_documento(app, lida):  # noqa: F811
    """A fila muda o realce e o cursor, não o texto."""
    j = lida
    j.pintar_texto()
    antes = j.texto.toPlainText()
    j.fila.andar(+1)
    j.pintar_texto()
    assert j.texto.toPlainText() == antes and fila(j)


# ----------------------------------------------------------------------
# CA-3.2, a Linha no livro de referência
# ----------------------------------------------------------------------

@pytest.mark.livro_real
@pytest.mark.parametrize("largura, altura", [(1366, 768), (1280, 720)])
def test_x_height_na_linha(app, tmp_path, sim, largura, altura):  # noqa: F811
    import json
    from pathlib import Path

    import numpy as np

    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro
    from tests.livros import PASTA_DOS_PDFS
    from tests.test_espaco import _x_height_do_gabarito

    raiz = Path(__file__).resolve().parent.parent
    verdade = json.loads((raiz / "tests" / "verdade" / "xv" / "i025.json").read_text(encoding="utf-8"))
    pdf = next(PASTA_DOS_PDFS.rglob(verdade["pdf"]), None)
    if pdf is None:
        pytest.skip("o PDF do livro de referência não está na pasta dos PDFs")
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Xadrez Vitorioso", pdf)
    j = _abrir(projeto, largura, altura)
    try:
        j.ir_para_pagina(verdade["indice_pdf"])
        j.pagina.leitor = LeitorDoLivro(projeto.pasta_de_padroes)
        j.reconhecer()
        _esperar(app, j, 120)
        meio = len(j.pagina.boxes) // 2                     # um glifo do corpo da página
        j.pagina.escolher(j.pagina.gids[meio])
        j.pintar_texto()
        j.linha.repaint()
        app.processEvents()
        x_height = _x_height_do_gabarito(np.array(j.pagina.imagem.convert("L")), verdade)
        assert x_height * j.linha.escala >= 12, (x_height, j.linha.escala)
    finally:
        j.close()


def test_o_ultimo_glifo_de_uma_linha_visual_quebrada_e_clicavel(app):
    """Uma palavra longa sem espaço quebra no meio: o glifo do fim de cada linha visual também
    se acha pelo clique."""
    gids = list(range(100, 220))
    chars = {g: "m" for g in gids}
    v = _vista(app, _doc(_bloco("b0", "texto", [gids]), chars=chars))
    v.resize(260, 400)
    v.show()
    app.processEvents()
    fins = []
    for g in gids:
        cursor = v.textCursor()
        cursor.setPosition(v.posicao_do_gid(g))
        depois = v.textCursor()
        depois.setPosition(v.posicao_do_gid(g) + 1)
        if v.cursorRect(depois).y() != v.cursorRect(cursor).y():
            fins.append(g)
    assert fins                                            # a palavra quebrou
    for g in fins:
        cursor = v.textCursor()
        cursor.setPosition(v.posicao_do_gid(g))
        ponto = v.cursorRect(cursor).center() + QPoint(3, 0)
        assert v.gid_no_ponto(ponto) == g
    v.close()


def test_o_cabecalho_corrido_sai_em_cinza_e_ctrl_shift_h_o_oculta(app):
    """Até o passo F, as margens vêm da regra da exportação (`gids_de_margem`)."""
    v = _vista(app, _doc(_bloco("b0", "texto", [[9, 10, 11]], [[1, 2], [3]]), chars=CHARS),
               margens={9, 10, 11})
    cursor = v.textCursor()
    cursor.setPosition(v.posicao_do_gid(10) + 1)
    assert cursor.charFormat().foreground().color().name() == "#6e6e6e"   # o cinza
    v.alternar_margens(False)
    assert v.toPlainText() == "ab c" and v.linha_de(10) == [9, 10, 11]


def test_o_glifo_atual_fica_marcado_no_documento_sem_o_foco(app, lida):  # noqa: F811
    j = lida
    j.pintar_texto()
    j.inspetor.focar()                                     # o foco no Inspetor, como na fila
    j.fila.andar(+1)
    selecoes = j.texto.extraSelections()
    assert len(selecoes) == 1
    assert j.texto.gid_na_posicao(selecoes[0].cursor.selectionStart()) == atual(j)


def test_a_pagina_nao_reconhecida_diz_no_documento(app, janela):  # noqa: F811
    janela.pintar_texto()
    assert "não reconhecida" in janela.texto.toPlainText()
    assert not janela.acao_realce.isEnabled()


def test_um_bloco_so_de_margem_oculto_nao_deixa_paragrafo_vazio(app):
    documento = _doc(_bloco("b0", "texto", [[9, 10, 11]]), _bloco("b1", "texto", [[1, 2]]),
                     _bloco("b2", "texto", [[4, 5]]), chars=CHARS)
    v = _vista(app, documento, margens={9, 10, 11})
    v.alternar_margens(False)
    assert v.toPlainText() == "ab\nde"


def test_a_linha_de_margem_com_um_glifo_nao_lido_continua_margem(app):
    chars = {**CHARS, 12: tx.NAO_LIDO}
    v = _vista(app, _doc(_bloco("b0", "texto", [[9, 12, 11]], [[1, 2]]), chars=chars),
               margens={9, 11})
    v.alternar_margens(False)
    assert v.toPlainText() == "ab"


def test_a_linha_do_clique_e_a_do_glifo_clicado(app, lida_a_mao):
    j = lida_a_mao
    alvo = j.pagina.gids[5]                                # o meio de uma palavra
    _clicar_no_gid(app, j, alvo)
    marcado = [n for n in range(len(j.linha._boxes)) if n == j.linha._atual]
    assert marcado and j.pagina.boxes.index(j.linha._boxes[marcado[0]]) == 5


def test_o_documento_mostra_o_estado_e_a_exportacao_o_nao_revisado(app):
    from core.diagrama_modelo import Casa
    from core.lado_a_jogar import NAO_REVISADO

    from abbychess.diagramas import DiagramaLido

    casas = [Casa(n // 8, n % 8, "K" if n == 60 else ("k" if n == 4 else "")) for n in range(64)]
    d = DiagramaLido((0, 0, 100, 100), casas, lado="w", id="d0")
    assert NAO_REVISADO in d.linha_de_texto(1)
    assert NAO_REVISADO not in d.linha_de_texto(1, com_ressalva=False)
