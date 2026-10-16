"""CA-F.1: o custo declarado dos comandos do passo 0 é o que a interface de hoje pede.

Cada comando de `ferramentas/replay/comandos.yaml` com `passo: "0"` é executado na
janela com eventos reais (QTest), e um filtro de eventos conta os gestos: cada
`KeyPress` e `MouseButtonPress` espontâneo (o que sobe para o widget pai chega como não
espontâneo e não conta de novo), mais cada `Shortcut` disparado (a tecla de um atalho não
chega como `KeyPress`); a tecla modificadora sozinha não conta, porque um acorde é um
gesto. A regra é `registro_de_eventos.tipo_do_gesto`, a mesma que mede a pessoa na CA-F.2.
O total tem de ser o `custo` do catálogo, e o efeito
tem de ser o que o comando promete.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from abbychess.app.registro_de_eventos import tipo_do_gesto
from abbychess.leitor import FONTE_MANUAL

from tests import test_janela, test_janela_diagramas
from tests.test_janela import _esperar

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import replay_fatia as rf  # noqa: E402
from tests.janela_util import atual, boxes, fila, mostrar, pulados, selecao  # noqa: E402,F401

app = test_janela.app
janela = test_janela.janela
CUSTO = {c["id"]: c["custo"] for c in rf.carregar_catalogo()["comandos"] if str(c["passo"]) == "0"}


class _Contador(QObject):
    """Conta os gestos pela mesma regra do registro da CA-F.2 (`tipo_do_gesto`)."""

    def __init__(self):
        super().__init__()
        self.gestos = 0

    def eventFilter(self, _objeto, evento):
        if tipo_do_gesto(evento) is not None:
            self.gestos += 1
        return False


@pytest.fixture
def contador(app):
    c = _Contador()
    QApplication.instance().installEventFilter(c)
    yield c
    QApplication.instance().removeEventFilter(c)


def _pronta(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    janela.show()
    janela.activateWindow()
    janela.visor.resetTransform()
    app.processEvents()
    return janela


def _no_visor(janela, x, y):
    return janela.visor.mapFromScene(x, y)


def _centro(b):
    return (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2


def test_o_catalogo_do_passo_0_e_o_que_este_teste_cobre():
    assert set(CUSTO) == {"pagina_seguinte", "reler_pendentes", "ensinar_da_fila", "ensinar_glifo",
                          "descartar_box",
                          "marcar_glifo",
                          "dividir_glifo", "juntar_glifos", "abrir_diagrama", "corrigir_casa",
                          "corrigir_lado", "fechar_diagrama"}


def test_premissa_evento_que_sobe_para_o_pai_nao_e_espontaneo(app, contador):
    """O contador só conta eventos espontâneos: o Enter que o campo ignora e sobe para o pai
    chega lá como não espontâneo, e o gesto conta uma vez."""
    from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

    pai = QWidget()
    campo = QLineEdit(pai)
    QVBoxLayout(pai).addWidget(campo)
    pai.show()
    app.processEvents()
    contador.gestos = 0
    QTest.keyClick(campo, Qt.Key.Key_Return)      # o QLineEdit ignora, o pai recebe
    assert contador.gestos == 1
    pai.close()


@pytest.fixture
def janela_de_duas_paginas(app, tmp_path, monkeypatch):
    """A janela com um PDF de verdade de duas páginas (a página sintética duas vezes)."""
    import fitz
    from PySide6.QtWidgets import QMessageBox

    from abbychess import pagina as pg
    from abbychess.app.janela import JanelaPrincipal
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro
    from tests.test_treino_por_livro import _pagina_sintetica

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    png = _pagina_sintetica(tmp_path / "pagina.png")
    pdf = tmp_path / "duas.pdf"
    with fitz.open() as doc:
        for _ in range(2):
            pagina = doc.new_page(width=216, height=62)     # 900×260 px a 300 dpi
            pagina.insert_image(pagina.rect, filename=str(png))
        doc.save(str(pdf))
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Duas", pdf)
    j = JanelaPrincipal()
    j.usar(projeto, pg.FonteDePaginas(projeto.fonte),
           LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    yield j
    j.close()


def test_pagina_seguinte(app, janela_de_duas_paginas, contador):
    janela_d = _pronta(app, janela_de_duas_paginas)
    assert janela_d.fonte.total == 2 and janela_d.pagina.indice == 0
    contador.gestos = 0
    QTest.keyClick(janela_d.treino.campo, Qt.Key.Key_PageDown, Qt.KeyboardModifier.ControlModifier)
    assert contador.gestos == CUSTO["pagina_seguinte"]
    assert janela_d.pagina.indice == 1 and janela_d.seletor.value() == 2


def test_reler_pendentes(app, janela, contador):
    """Ctrl+R relê os pendentes: o padrão ensinado resolve um 'a' que estava pendente."""
    _pronta(app, janela)
    mostrar(janela, 0)
    janela.treino.campo.setText("a")
    janela.treino.pedir_ensinar()
    _esperar(app, janela)
    outro = next(i for i, b in enumerate(boxes(janela)) if b.char == "a" and i != 0)
    boxes(janela)[outro].char, boxes(janela)[outro].source = "", "none"   # volta a pendente
    assert outro in fila(janela)
    contador.gestos = 0
    QTest.keyClick(janela.treino.campo, Qt.Key.Key_R, Qt.KeyboardModifier.ControlModifier)
    _esperar(app, janela)
    assert contador.gestos == CUSTO["reler_pendentes"]
    assert boxes(janela)[outro].char == "a" and outro not in fila(janela)


def test_dividir_e_juntar(app, janela, contador):
    _pronta(app, janela)
    total, b = len(boxes(janela)), boxes(janela)[0]
    contador.gestos = 0
    QTest.mouseClick(janela.visor.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, _no_visor(janela, *_centro(b)))
    QTest.keyClick(janela.treino.campo, Qt.Key.Key_J, Qt.KeyboardModifier.ControlModifier)
    assert contador.gestos == CUSTO["juntar_glifos"]
    assert len(boxes(janela)) == total - 1

    contador.gestos = 0
    QTest.mouseClick(janela.visor.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, _no_visor(janela, *_centro(boxes(janela)[0])))
    QTest.keyClick(janela.treino.campo, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
    assert contador.gestos == CUSTO["dividir_glifo"]
    assert len(boxes(janela)) == total


def test_ensinar_glifo(app, janela, contador):
    _pronta(app, janela)
    b = boxes(janela)[0]
    contador.gestos = 0
    QTest.mouseClick(janela.visor.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, _no_visor(janela, *_centro(b)))
    QTest.keyClicks(janela.treino.campo, "a")
    QTest.keyClick(janela.treino.campo, Qt.Key.Key_Return)
    _esperar(app, janela)
    assert contador.gestos == CUSTO["ensinar_glifo"]
    assert (boxes(janela)[0].char, boxes(janela)[0].source) == ("a", FONTE_MANUAL)
    assert "a" in janela.leitor.padroes_por_caractere()


def test_ensinar_da_fila(app, janela, contador):
    """O glifo que a janela já mostra (o primeiro da fila): digitar e Enter, sem clique."""
    _pronta(app, janela)
    primeiro = fila(janela)[0]
    # O campo vem selecionado (e com o foco, que o offscreen não garante dar à janela).
    assert atual(janela) == primeiro and janela.treino.campo.selectedText() == janela.treino.campo.text()
    contador.gestos = 0
    QTest.keyClicks(janela.treino.campo, "a")
    QTest.keyClick(janela.treino.campo, Qt.Key.Key_Return)
    _esperar(app, janela)
    assert contador.gestos == CUSTO["ensinar_da_fila"]
    assert (boxes(janela)[primeiro].char, boxes(janela)[primeiro].source) == ("a", FONTE_MANUAL)
    assert atual(janela) != primeiro             # a janela foi sozinha ao próximo da fila


def test_descartar_box(app, janela, contador):
    _pronta(app, janela)
    total, b = len(boxes(janela)), boxes(janela)[1]
    botao = next(w for w in janela.treino.findChildren(QPushButton)
                 if w.text().startswith("Não é caractere"))
    contador.gestos = 0
    QTest.mouseClick(janela.visor.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, _no_visor(janela, *_centro(b)))
    QTest.mouseClick(botao, Qt.MouseButton.LeftButton)
    assert contador.gestos == CUSTO["descartar_box"]
    assert len(boxes(janela)) == total - 1


def test_marcar_glifo(app, janela, contador):
    _pronta(app, janela)
    a, b = boxes(janela)[0], boxes(janela)[1]
    porta = janela.visor.viewport()
    contador.gestos = 0
    QTest.keyClick(janela.treino.campo, Qt.Key.Key_M, Qt.KeyboardModifier.ControlModifier)
    inicio, fim = _no_visor(janela, a.x1 - 4, b.y1 - 4), _no_visor(janela, b.x2 + 1, a.y2 + 4)
    QTest.mousePress(porta, Qt.MouseButton.LeftButton, pos=inicio)
    QTest.mouseMove(porta, fim)
    QTest.mouseRelease(porta, Qt.MouseButton.LeftButton, pos=fim)
    QTest.keyClicks(janela.treino.campo, "x")
    QTest.keyClick(janela.treino.campo, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert contador.gestos == CUSTO["marcar_glifo"]
    # O Shift+Enter já avança a fila; o box marcado é o que cobre o "a" e o "b".
    novo = next(x for x in boxes(janela) if x.x1 <= a.x1 + 1 and x.x2 >= b.x2 - 1)
    assert (novo.char, novo.source) == ("x", FONTE_MANUAL)


@pytest.fixture
def janela_com_diagrama(app, tmp_path, monkeypatch):
    """A janela de `test_janela_diagramas`, montada aqui (fixture não se chama direto)."""
    from PySide6.QtWidgets import QMessageBox

    from abbychess import pagina as pg
    from abbychess.app.janela import JanelaPrincipal
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro
    from tests.test_diagramas import pagina_com_diagrama

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Diagramas",
                                   pagina_com_diagrama(tmp_path / "pagina.png"))
    j = JanelaPrincipal()
    j.usar(projeto, pg.FonteDePaginas(projeto.fonte),
           LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    yield j
    if j.dialogo_diagrama is not None:
        j.dialogo_diagrama.close()
    j.close()


@test_janela_diagramas.sem_modelo
def test_conferir_um_diagrama(app, janela_com_diagrama, contador):
    """Abrir com um clique no diagrama, corrigir uma casa, conferir com Ctrl+Enter."""
    from abbychess.app import dialogo_diagrama as dd

    janela_d = _pronta(app, janela_com_diagrama)
    x1, y1, x2, y2 = janela_d.pagina.diagramas[0].caixa
    contador.gestos = 0
    QTest.mouseClick(janela_d.visor.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, _no_visor(janela_d, (x1 + x2) / 2, (y1 + y2) / 2))
    _esperar(app, janela_d)
    dialogo = janela_d.dialogo_diagrama
    assert isinstance(dialogo, dd.DialogoDeDiagrama)
    assert contador.gestos == CUSTO["abrir_diagrama"]

    contador.gestos = 0
    centro = dialogo.posicao.retangulo(4, 4).center()
    QTest.mouseClick(dialogo.posicao, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     QPoint(centro))
    QTest.keyClicks(dialogo.posicao, "Q")
    assert contador.gestos == CUSTO["corrigir_casa"]
    assert dialogo.posicao.tabuleiro.casa(4, 4).simbolo == "Q"

    contador.gestos = 0
    # Sobre o indicador: o centro de um QRadioButton largo cai fora da área clicável.
    QTest.mouseClick(dialogo.radio_pretas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     QPoint(8, dialogo.radio_pretas.height() // 2))
    assert contador.gestos == CUSTO["corrigir_lado"]
    assert dialogo.tabuleiro().lado == "b"

    contador.gestos = 0
    QTest.keyClick(dialogo.posicao, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    _esperar(app, janela_d)
    assert contador.gestos == CUSTO["fechar_diagrama"]
    assert janela_d.pagina.diagramas[0].conferido
