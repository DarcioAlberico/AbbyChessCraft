"""O visor novo do passo A1 (SPEC §3.3): o item dos boxes, o zoom, a rolagem e a navegação.

CA-3.4 (um item de boxes, repintura do retângulo do box), CA-3.6 (os limites do zoom na
barra), CA-3.8 (os atalhos de navegação por QTest, com a página e o foco esperados), e a
grade, o cache de páginas e o histórico de visitas sem janela. O CA-3.5 (a pintura e o
clique com 2.000 boxes) está em `tests/desempenho/test_visor.py`.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.box_model import BoxEntry  # noqa: E402
from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox  # noqa: E402

from abbychess import grade as gd  # noqa: E402
from abbychess import pagina as pg  # noqa: E402
from abbychess.app.item_dos_boxes import ItemDosBoxes  # noqa: E402
from abbychess.app.janela import JanelaPrincipal  # noqa: E402
from abbychess.leitor import FONTE_LIVRO, FONTE_MANUAL, FONTE_NENHUMA, LeitorDoLivro  # noqa: E402
from abbychess.projeto import ProjetoDeLivro  # noqa: E402

from tests.janela_util import boxes, mostrar  # noqa: E402
from tests.test_janela import _esperar  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ----------------------------------------------------------------------
# A grade e os estados, sem Qt
# ----------------------------------------------------------------------

def test_grade_acha_o_menor_box_no_ponto_e_os_do_retangulo():
    grade = gd.GradeDeCaixas([(0, 0, 100, 100), (10, 10, 20, 20), (200, 200, 210, 210)])
    assert grade.no_ponto(15, 15) == 1             # o de dentro, que é menor
    assert grade.no_ponto(50, 50) == 0
    assert grade.no_ponto(150, 150) is None
    assert grade.no_retangulo(190, 190, 300, 300) == {2}
    grade.mover(2, (400, 400, 410, 410))
    assert grade.no_ponto(205, 205) is None and grade.no_ponto(405, 405) == 2


def test_estados_dos_boxes():
    assert gd.estado(BoxEntry("a", 0, 0, 1, 1, 1.0, FONTE_MANUAL), True) == gd.MANUAL
    assert gd.estado(BoxEntry("", 0, 0, 1, 1), False) == gd.AGUARDANDO
    assert gd.estado(BoxEntry("", 0, 0, 1, 1, 0.0, FONTE_NENHUMA), True) == gd.SEM_LEITURA
    assert gd.estado(BoxEntry("a", 0, 0, 1, 1, 0.3, "net"), True) == gd.PENDENTE
    assert gd.estado(BoxEntry("a", 0, 0, 1, 1, 0.9, FONTE_LIVRO), False) == gd.LIVRO
    assert gd.estado(BoxEntry("a", 0, 0, 1, 1, 0.9, "net"), False) == gd.REDE


def test_cada_estado_tem_traco_distinto():
    from abbychess.app import estilo

    chamam = [estilo.TRACOS[e] for e in (gd.PENDENTE, gd.SEM_LEITURA, gd.AGUARDANDO)]
    assert len({t.estilo for t in chamam}) == 3 and all(t.largura >= 1.5 for t in chamam)
    origem = [estilo.TRACOS_DA_ORIGEM[e] for e in gd.ACEITOS]
    assert len({t.cor.name() for t in origem}) == 3


# ----------------------------------------------------------------------
# O cache de páginas e as visitas
# ----------------------------------------------------------------------

@pytest.fixture
def pdf_de_60_paginas(tmp_path):
    import fitz

    caminho = tmp_path / "sessenta.pdf"
    with fitz.open() as doc:
        for k in range(60):
            pagina = doc.new_page(width=200, height=300)
            pagina.insert_text((20, 40), f"Pagina {k + 1}", fontsize=14)
        doc.save(str(caminho))
    return caminho


def test_cache_guarda_as_ultimas_e_pre_carrega(pdf_de_60_paginas):
    fonte = pg.FonteDePaginas(pdf_de_60_paginas)
    cache = pg.CacheDePaginas(fonte, tamanho=3)
    primeira = cache.pagina(0)
    assert cache.pagina(0) is primeira               # do cache, o mesmo objeto
    for k in (1, 2, 3):
        cache.pagina(k)
    assert not cache.tem(0) and cache.tem(3)         # o mais antigo saiu
    cache.precarregar(10)
    cache.esperar()
    assert cache.tem(10)


def _janela(projeto):
    j = JanelaPrincipal()
    j.resize(1200, 900)
    j.usar(projeto, pg.FonteDePaginas(projeto.fonte),
           LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    return j


@pytest.fixture
def janela_de_60(app, tmp_path, pdf_de_60_paginas, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Sessenta", pdf_de_60_paginas)
    j = _janela(projeto)
    j.show()
    j.activateWindow()
    app.processEvents()
    yield j
    j.close()


def test_alt_seta_esquerda_depois_de_ctrl_g_50_volta(app, janela_de_60, monkeypatch):
    """CA-3.8: Alt+← depois de Ctrl+G 50 volta à página de antes; Alt+→ vai de novo."""
    j = janela_de_60
    monkeypatch.setattr(QInputDialog, "getInt", lambda *a, **k: (50, True))
    j.ir_para_pagina(6)
    j.visor.setFocus()
    QTest.keyClick(j.visor, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier)
    assert j.pagina.indice == 49
    QTest.keyClick(j.visor, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
    assert j.pagina.indice == 6
    QTest.keyClick(j.visor, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
    assert j.pagina.indice == 49


def test_alt_home_e_alt_end(app, janela_de_60):
    j = janela_de_60
    j.ir_para_pagina(20)
    j.visor.setFocus()
    QTest.keyClick(j.visor, Qt.Key.Key_End, Qt.KeyboardModifier.AltModifier)
    assert j.pagina.indice == 59
    QTest.keyClick(j.visor, Qt.Key.Key_Home, Qt.KeyboardModifier.AltModifier)
    assert j.pagina.indice == 0 and QApplication.focusWidget() is j.visor


def test_pgdn_no_fim_da_pagina_abre_a_seguinte_no_topo(app, janela_de_60):
    """CA-3.8: PgDn rola uma tela; no fim, abre a página seguinte, no topo."""
    j = janela_de_60
    j.ir_para_pagina(3)
    j.visor.definir_zoom(4.0)                        # a página maior que a vista
    j.visor.setFocus()
    barra = j.visor.verticalScrollBar()
    barra.setValue(barra.minimum())
    for _ in range(50):
        if j.pagina.indice != 3:
            break
        QTest.keyClick(j.visor, Qt.Key.Key_PageDown)
    assert j.pagina.indice == 4
    assert barra.value() == barra.minimum() and QApplication.focusWidget() is j.visor
    QTest.keyClick(j.visor, Qt.Key.Key_PageUp)      # no topo: a anterior, no fim
    assert j.pagina.indice == 3 and barra.value() == barra.maximum()


def test_zoom_tem_limites_e_a_barra_diz(app, janela_de_60):
    """CA-3.6: no limite do zoom a barra diz "zoom máximo" / "zoom mínimo"."""
    j = janela_de_60
    j.visor.setFocus()
    for _ in range(40):
        QTest.keyClick(j.visor, Qt.Key.Key_Plus, Qt.KeyboardModifier.ControlModifier)
    assert j.visor.escala() == pytest.approx(8.0)
    assert "zoom máximo" in j.statusBar().currentMessage()
    assert j.caixa_de_zoom.value() == 800
    for _ in range(60):
        QTest.keyClick(j.visor, Qt.Key.Key_Minus, Qt.KeyboardModifier.ControlModifier)
    assert j.visor.escala() == pytest.approx(0.05)
    assert "zoom mínimo" in j.statusBar().currentMessage()


def test_os_modos_de_zoom(app, janela_de_60):
    j = janela_de_60
    j.visor.setFocus()
    QTest.keyClick(j.visor, Qt.Key.Key_8, Qt.KeyboardModifier.ControlModifier)
    assert j.visor.escala() == pytest.approx(1.0) and j.visor.modo_zoom is None
    QTest.keyClick(j.visor, Qt.Key.Key_9, Qt.KeyboardModifier.ControlModifier)
    pagina = j.visor.scene().sceneRect().width()
    assert j.visor.modo_zoom == "largura"
    assert j.visor.escala() * pagina == pytest.approx(j.visor.viewport().width() - 4, abs=2)
    j.resize(900, 900)                              # na largura, o zoom segue a janela
    app.processEvents()
    assert j.visor.escala() * pagina == pytest.approx(j.visor.viewport().width() - 4, abs=2)
    QTest.keyClick(j.visor, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
    assert j.visor.modo_zoom == "pagina"
    assert j.caixa_de_zoom.focusPolicy() == Qt.FocusPolicy.ClickFocus


# ----------------------------------------------------------------------
# O item dos boxes na janela de verdade (a página sintética de `test_janela`)
# ----------------------------------------------------------------------

@pytest.fixture
def janela(app, tmp_path, monkeypatch):
    from tests.test_treino_por_livro import _pagina_sintetica

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Teste",
                                   _pagina_sintetica(tmp_path / "pagina.png"))
    j = _janela(projeto)
    j.reconhecer()
    _esperar(app, j)
    yield j
    j.close()


def test_a_cena_tem_um_item_de_boxes_e_a_mudanca_repinta_so_o_box(janela, monkeypatch):
    """CA-3.4: um item de boxes; mudar um box pede `update(QRectF)` ≤ 2× a caixa dele."""
    cena = janela.visor.scene()
    assert sum(isinstance(i, ItemDosBoxes) for i in cena.items()) == 1
    assert len(cena.items()) < 10                       # e não um item por box
    pedidos = []
    original = ItemDosBoxes.update

    def update(self, *args):
        pedidos.append(args)
        return original(self, *args)

    monkeypatch.setattr(ItemDosBoxes, "update", update)
    mostrar(janela, 2)
    janela.pagina.corrigir("q")
    b = boxes(janela)[2]
    retangulos = [a[0] for a in pedidos if a]
    assert retangulos and not [a for a in pedidos if not a]   # nada de repintar tudo
    for r in retangulos:
        assert r.width() * r.height() <= 2 * (b.x2 - b.x1) * (b.y2 - b.y1)


def test_v_liga_a_origem_das_leituras(app, janela):
    janela.show()
    janela.activateWindow()
    app.processEvents()
    janela.visor.setFocus()
    QTest.keyClick(janela.visor, Qt.Key.Key_V)
    assert janela.visor.item_dos_boxes.mostrar_origem and janela.acao_origem.isChecked()
    QTest.keyClick(janela.visor, Qt.Key.Key_V)
    assert not janela.visor.item_dos_boxes.mostrar_origem


def test_seguir_deixa_o_item_atual_a_120_px_da_borda(app, janela):
    """CA-3.8: com Seguir, o item atual fica a ≥ 120 px da borda depois de andar na fila."""
    janela.show()
    app.processEvents()
    janela.visor.definir_zoom(3.0)
    assert janela.acao_seguir.isChecked()
    for _ in range(4):
        janela.pagina.andar(+1)
        b = boxes(janela)[janela.pagina.indice_de(janela.pagina.atual)]
        topo = janela.visor.mapFromScene(b.x1, b.y1)
        fundo = janela.visor.mapFromScene(b.x2, b.y2)
        vista = janela.visor.viewport().rect()
        margem = min(topo.x(), topo.y(), vista.width() - fundo.x(), vista.height() - fundo.y())
        assert margem >= 120 - 4, margem                # a folga do traço do destaque


def test_f8_vai_ao_proximo_diagrama_por_conferir_do_livro(app, tmp_path, monkeypatch):
    from abbychess import diagramas as dg
    from tests.test_livro import pdf_sintetico

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Duas", pdf_sintetico(tmp_path))
    modelo = projeto.pagina_para_editar(2)
    modelo.tabuleiros = [(10, 10, 210, 210)]
    projeto.agendar(modelo)
    j = _janela(projeto)
    try:
        abertas = []
        j.eventos.ligar("conferir", abertas.append)
        monkeypatch.setattr(j, "_abrir_conferencia", lambda i: None)
        from core import diagrama_modelo as modelo

        vazias = [modelo.Casa(k // 8, k % 8, None, 1.0) for k in range(64)]
        monkeypatch.setattr(dg, "ler_diagramas", lambda _img, caixas, **_k: [
            dg.DiagramaLido(c, casas=list(vazias)) for c in caixas])
        j.ir_para_pagina(0)
        j.acao_diagramas.trigger()                       # F8
        _esperar(app, j)
        assert j.pagina.indice == 2 and abertas == [0]
    finally:
        j.close()


def test_botao_do_meio_e_espaco_arrastam_a_pagina_sem_marcar(app, janela):
    janela.show()
    app.processEvents()
    j = janela
    j.visor.definir_zoom(8.0)
    j.modo_treino(True)                              # mesmo no modo de treino
    antes_dos_boxes = list(j.pagina.modelo.boxes)
    porta = j.visor.viewport()
    barra = j.visor.verticalScrollBar()
    assert barra.maximum() >= 200
    barra.setValue(0)
    antes = barra.value()
    QTest.mousePress(porta, Qt.MouseButton.MiddleButton, pos=QPoint(300, 300))
    QTest.mouseMove(porta, QPoint(300, 200))
    QTest.mouseRelease(porta, Qt.MouseButton.MiddleButton, pos=QPoint(300, 200))
    assert barra.value() == antes + 100
    j.visor.setFocus()
    QTest.keyPress(j.visor, Qt.Key.Key_Space)
    QTest.mousePress(porta, Qt.MouseButton.LeftButton, pos=QPoint(300, 300))
    QTest.mouseMove(porta, QPoint(300, 350))
    QTest.mouseRelease(porta, Qt.MouseButton.LeftButton, pos=QPoint(300, 350))
    QTest.keyRelease(j.visor, Qt.Key.Key_Space)
    assert barra.value() == antes + 50
    assert j.pagina.modelo.boxes == antes_dos_boxes      # arrastou, não marcou quadro


def test_espaco_solto_fora_do_visor_nao_fica_preso(app, janela):
    janela.show()
    app.processEvents()
    janela.visor.setFocus()
    QTest.keyPress(janela.visor, Qt.Key.Key_Space)
    janela.treino.campo.setFocus()                   # o foco sai (Alt+Tab, um diálogo)
    app.processEvents()
    assert not janela.visor._espaco


def test_seguir_desligado_nao_move_a_vista(app, janela):
    janela.show()
    app.processEvents()
    janela.visor.definir_zoom(3.0)
    janela.acao_seguir.setChecked(False)
    barra_h, barra_v = janela.visor.horizontalScrollBar(), janela.visor.verticalScrollBar()
    barra_h.setValue(0)
    barra_v.setValue(0)
    for _ in range(4):
        janela.pagina.andar(+1)
    assert (barra_h.value(), barra_v.value()) == (0, 0)


def test_zoom_no_item_atual_e_shift_roda(app, janela):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QWheelEvent

    janela.show()
    app.processEvents()
    mostrar(janela, 0)
    janela.visor.zoom_item()
    b = boxes(janela)[0]
    centro = janela.visor.mapFromScene((b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2)
    vista = janela.visor.viewport().rect()
    assert janela.visor.escala() > 1 and vista.contains(centro)
    barra = janela.visor.horizontalScrollBar()
    barra.setValue(barra.maximum() // 2)
    antes = barra.value()
    evento = QWheelEvent(QPointF(100, 100), QPointF(100, 100), QPoint(0, 0), QPoint(0, -120),
                         Qt.MouseButton.NoButton, Qt.KeyboardModifier.ShiftModifier,
                         Qt.ScrollPhase.NoScrollPhase, False)
    janela.visor.wheelEvent(evento)
    assert barra.value() > antes


def test_pixmap_em_cache_vale_so_para_a_mesma_imagem(app, janela):
    from PIL import Image

    primeiro = janela._pixmap(0, janela.pagina.imagem)
    assert janela._pixmap(0, janela.pagina.imagem) is primeiro
    outra = Image.new("L", janela.pagina.imagem.size, 255)
    assert janela._pixmap(0, outra) is not primeiro


def test_pgdn_com_a_pagina_inteira_na_vista_vira_a_pagina(app, janela_de_60):
    j = janela_de_60
    j.ir_para_pagina(3)
    j.visor.zoom_pagina()                            # a página cabe: não há o que rolar
    j.visor.setFocus()
    QTest.keyClick(j.visor, Qt.Key.Key_PageDown)
    assert j.pagina.indice == 4
    QTest.keyClick(j.visor, Qt.Key.Key_PageUp)
    assert j.pagina.indice == 3


def test_f8_sem_diagrama_avisa_e_na_propria_pagina_abre_ela(app, janela, monkeypatch):
    janela.acao_diagramas.trigger()
    assert "Não há diagrama por conferir" in janela.statusBar().currentMessage()
    abertos = []
    monkeypatch.setattr(janela.conferencia, "conferir", lambda indice=None: abertos.append(1))
    janela.pagina.modelo.tabuleiros = [(10, 10, 210, 210)]
    janela.acao_diagramas.trigger()
    assert abertos == [1] and janela.pagina.indice == 0


# ----------------------------------------------------------------------
# O cache com duas threads, e as visitas
# ----------------------------------------------------------------------

def test_a_mesma_pagina_pedida_por_duas_threads_e_renderizada_uma_vez(pdf_de_60_paginas):
    import threading

    fonte = pg.FonteDePaginas(pdf_de_60_paginas)
    chamadas = []
    original = fonte._pagina
    dentro, solta = threading.Event(), threading.Event()

    def _pagina(indice):
        chamadas.append(indice)
        dentro.set()
        solta.wait(5)
        return original(indice)

    fonte._pagina = _pagina
    cache = pg.CacheDePaginas(fonte)
    cache.precarregar(5)                              # a pré-carga começa a renderizar
    assert dentro.wait(5)
    resultado = []
    leitor = threading.Thread(target=lambda: resultado.append(cache.pagina(5)))
    leitor.start()                                     # e o clique pede a mesma, no meio
    leitor.join(0.3)
    assert leitor.is_alive()                           # espera a pré-carga, não renderiza
    solta.set()
    leitor.join(5)
    cache.esperar()
    assert chamadas == [5] and resultado and resultado[0] is cache.pagina(5)


def test_visitas_cortam_o_que_vinha_depois_ao_navegar_no_meio(app, janela_de_60):
    p = janela_de_60.pagina
    for k in (3, 10, 20):
        p.ir_para(k)
    p.voltar_visita()
    p.voltar_visita()                                  # em 3, com 10 e 20 adiante
    p.ir_para(40)                                      # navegar corta o adiante
    assert not p.pode_avancar and p.visitas[-2:] == [3, 40]


def test_ligar_outro_projeto_troca_o_cache(app, janela_de_60, tmp_path):
    from tests.test_treino_por_livro import _pagina_sintetica

    antigo = janela_de_60.pagina.cache
    outro = ProjetoDeLivro.criar(tmp_path / "outros", "Outro",
                                 _pagina_sintetica(tmp_path / "outra.png"))
    janela_de_60.usar(outro, pg.FonteDePaginas(outro.fonte),
                      LeitorDoLivro(outro.pasta_de_padroes))
    assert janela_de_60.pagina.cache is not antigo
    assert janela_de_60.pagina.cache.fonte is janela_de_60.pagina.fonte


def test_paint_desenha_o_traco_do_box_logo_fora_do_retangulo_exposto(app):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter, QTransform
    from PySide6.QtWidgets import QStyleOptionGraphicsItem

    from abbychess.app.item_dos_boxes import ItemDosBoxes
    from core.box_model import BoxEntry

    item = ItemDosBoxes(400, 400)
    # O box começa em x = 101 da página, logo depois do retângulo exposto (que acaba em
    # 100,9); a 2×, o traço da borda esquerda dele cai no pixel 201, dentro do exposto.
    item.trocar([BoxEntry("a", 101, 50, 150, 90, 0.1, "net")], [gd.SEM_LEITURA])
    imagem = QImage(400, 400, QImage.Format.Format_ARGB32)
    imagem.fill(0)
    exposto = QRectF(0, 0, 100.9, 400)
    opcao = QStyleOptionGraphicsItem()
    opcao.exposedRect = exposto
    pintor = QPainter(imagem)
    pintor.setTransform(QTransform.fromScale(2, 2))
    pintor.setClipRect(exposto)                      # como a cena faz: só o exposto é pintado
    item.paint(pintor, opcao)
    pintor.end()
    assert any(imagem.pixelColor(201, y).alpha() for y in range(90, 190))


def test_enter_na_caixa_de_zoom_devolve_o_foco_e_clicar_noutro_campo_nao(app, janela):
    janela.show()
    app.processEvents()
    caixa = janela.caixa_de_zoom
    caixa.setFocus()
    caixa.lineEdit().selectAll()
    QTest.keyClicks(caixa.lineEdit(), "150")
    QTest.keyClick(caixa.lineEdit(), Qt.Key.Key_Return)
    app.processEvents()
    assert abs(janela.visor.escala() - 1.5) < 1e-6
    assert QApplication.focusWidget() is janela.visor
    caixa.setFocus(Qt.FocusReason.MouseFocusReason)
    app.processEvents()
    QTest.keyClicks(caixa.lineEdit(), "0")           # editando, sem Enter
    janela.treino.campo.setFocus(Qt.FocusReason.MouseFocusReason)   # e clica noutro campo
    app.processEvents()
    assert QApplication.focusWidget() is janela.treino.campo


def test_zoom_vale_com_o_foco_no_campo_do_treino_e_o_v_nao(app, janela):
    janela.show()
    app.processEvents()
    janela.treino.campo.setFocus()
    app.processEvents()
    QTest.keyClick(janela.treino.campo, Qt.Key.Key_8, Qt.KeyboardModifier.ControlModifier)
    assert abs(janela.visor.escala() - 1.0) < 1e-6           # Ctrl+8, 100%
    QTest.keyClick(janela.treino.campo, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
    assert janela.visor.modo_zoom == "pagina"                 # Ctrl+0
    QTest.keyClick(janela.treino.campo, Qt.Key.Key_V)
    assert not janela.acao_origem.isChecked()                 # no campo, V é uma letra
    assert "v" in janela.treino.campo.text().lower()


def test_a_seguinte_e_pre_carregada_depois_da_pintura(app, janela_de_60):
    j = janela_de_60
    j.ir_para_pagina(10)
    assert not j.pagina.cache.tem(11)                          # o ir_para não a dispara
    import time

    fim = time.monotonic() + 5                                  # o relógio da janela, sim
    while not j.pagina.cache.tem(11) and time.monotonic() < fim:
        app.processEvents()
        time.sleep(0.01)
    assert j.pagina.cache.tem(11)
