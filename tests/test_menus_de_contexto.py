"""O menu de contexto nos painéis que não tinham (SPEC §3.2: "Shift+F10 e a tecla Menu abrem o
menu de contexto em todo painel"): a Galeria, os Padrões, os Diagramas e a Linha.

Cada menu repete o que o painel já faz pelo teclado ou por um botão, para quem usa o mouse;
nenhum faz algo que o painel não fazia. O Shift+F10 na janela inteira está em
`tests/test_espaco.py`.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QAction, QContextMenuEvent, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from core.box_model import BoxEntry  # noqa: E402

from abbychess.app.galeria import Item, PainelDaGaleria  # noqa: E402
from abbychess.app.linha import FaixaDaLinha  # noqa: E402
from abbychess.app.painel_diagramas import PainelDeDiagramas  # noqa: E402
from abbychess.app.painel_padroes import PainelDePadroes  # noqa: E402


def _acao(menu, comeco: str):
    """A ação do menu cujo texto começa por `comeco`."""
    return next(a for a in menu.actions() if a.text().startswith(comeco))


def _textos(menu):
    return [a.text() for a in menu.actions() if not a.isSeparator()]


def _abre_pelo_teclado(app, widget) -> bool:
    """O `QContextMenuEvent` de teclado (Shift+F10, a tecla Menu) abre um menu no widget."""
    abertos = []

    def fechar():
        menu = QApplication.activePopupWidget()
        abertos.append(menu)
        if menu is not None:
            menu.close()
    QTimer.singleShot(50, fechar)
    QApplication.sendEvent(widget, QContextMenuEvent(QContextMenuEvent.Reason.Keyboard,
                                                     QPoint(5, 5), widget.mapToGlobal(QPoint(5, 5))))
    fim = QTimer()
    fim.setSingleShot(True)
    fim.start(500)
    while fim.isActive() and not abertos:
        app.processEvents()
    return bool(abertos and abertos[0] is not None)


# ----------------------------------------------------------------------
# A Galeria
# ----------------------------------------------------------------------
@pytest.fixture
def galeria(app):
    painel = PainelDaGaleria()
    painel.resize(400, 300)
    painel.show()
    painel.mostrar("'e'", [Item(0, 1, "e", 0.4), Item(0, 2, "e", 0.6), Item(3, 7, "c", 0.5)],
                   escopo="pagina")
    yield painel
    painel.close()
    painel.deleteLater()


def test_o_menu_da_galeria_sem_selecao_so_seleciona_e_troca_o_escopo(galeria):
    menu = galeria.menu_de_contexto()
    assert _textos(menu) == ["Ir ao glifo", "Ensinar as selecionadas (0)",
                             "Só corrigir as selecionadas (0)", "Símbolos…", "Selecionar tudo",
                             "Ver o livro inteiro"]
    assert not _acao(menu, "Ir ao glifo").isEnabled()
    assert not _acao(menu, "Ensinar").isEnabled() and not _acao(menu, "Só corrigir").isEnabled()
    assert not _acao(menu, "Símbolos").isEnabled()
    _acao(menu, "Selecionar tudo").trigger()
    assert len(galeria.selecionados()) == 3


def test_o_menu_da_galeria_faz_o_que_o_teclado_faz(galeria):
    galeria.vista.setCurrentIndex(galeria.modelo.index(1))
    galeria.vista.selectionModel().select(galeria.modelo.index(0),
                                          galeria.vista.selectionModel().SelectionFlag.Select)
    ensinou, corrigiu, foi, escopos = [], [], [], []
    galeria.vista.ensinar.connect(lambda: ensinou.append(1))
    galeria.vista.so_corrigir.connect(lambda: corrigiu.append(1))
    galeria.escolhido.connect(foi.append)
    galeria.escopo_mudou.connect(escopos.append)
    menu = galeria.menu_de_contexto()
    assert "Ensinar as selecionadas (2)" in _textos(menu)
    _acao(menu, "Ensinar").trigger()
    _acao(menu, "Só corrigir").trigger()
    _acao(menu, "Ir ao glifo").trigger()
    assert ensinou == [1] and corrigiu == [1]
    assert [(i.pagina, i.gid) for i in foi] == [(3, 7)]    # o do cursor, na ordem da confiança
    _acao(menu, "Ver o livro inteiro").trigger()
    assert escopos == ["livro"]
    assert "Ver só a página" in _textos(galeria.menu_de_contexto())


def test_os_simbolos_do_menu_da_galeria_aplicam_a_selecao(galeria):
    galeria.vista.selectAll()
    aplicados = []
    galeria.vista.aplicar.connect(aplicados.append)
    _acao(galeria.menu_de_contexto(), "Símbolos").trigger()
    paleta = galeria.menu_da_paleta
    paleta.escolher("♘")
    paleta.close()
    assert aplicados == ["♘"]


# ----------------------------------------------------------------------
# Os Padrões
# ----------------------------------------------------------------------
@pytest.fixture
def padroes(app, tmp_path):
    arquivos = []
    for nome in ("um", "dois", "tres"):
        caminho = tmp_path / f"{nome}.png"
        QPixmap(8, 8).save(str(caminho))
        arquivos.append(caminho)
    painel = PainelDePadroes()
    painel.atualizar({"1": arquivos[:2], "l": arquivos[2:]},
                     {str(arquivos[0]): {"origem": (20, 0x1a), "lidos": 3},
                      str(arquivos[1]): {"origem": None, "lidos": 0},
                      str(arquivos[2]): {"origem": (4, 2), "lidos": 1}})
    painel.caracteres.setCurrentRow(0)                        # o "1", com duas amostras
    yield painel, arquivos
    painel.deleteLater()


def test_o_menu_das_amostras_vai_a_origem_e_esquece(padroes):
    painel, arquivos = padroes
    idas, esquecidas = [], []
    painel.ir_para.connect(lambda pagina, gid: idas.append((pagina, gid)))
    painel.esquecer.connect(esquecidas.append)
    menu = painel.menu_das_amostras()
    assert _textos(menu) == ["Ir à origem", "Esquecer as selecionadas (0)"]
    assert not any(a.isEnabled() for a in menu.actions())
    painel.amostras.item(0).setSelected(True)
    painel.amostras.setCurrentItem(painel.amostras.item(0))
    menu = painel.menu_das_amostras()
    _acao(menu, "Ir à origem").trigger()
    _acao(menu, "Esquecer").trigger()
    assert idas == [(20, 0x1a)] and esquecidas == [[str(arquivos[0])]]
    painel.amostras.item(0).setSelected(False)
    painel.amostras.item(1).setSelected(True)                 # a amostra sem origem
    painel.amostras.setCurrentItem(painel.amostras.item(1))
    assert not _acao(painel.menu_das_amostras(), "Ir à origem").isEnabled()


def test_o_menu_dos_caracteres_esquece_todas_as_amostras_do_caractere(padroes):
    painel, arquivos = padroes
    esquecidas = []
    painel.esquecer.connect(esquecidas.append)
    menu = painel.menu_dos_caracteres()
    assert _textos(menu) == ["Esquecer as 2 amostras de '1'"]
    _acao(menu, "Esquecer").trigger()
    assert esquecidas == [[str(arquivos[0]), str(arquivos[1])]]
    painel.caracteres.setCurrentItem(None)
    assert not _acao(painel.menu_dos_caracteres(), "Esquecer").isEnabled()


# ----------------------------------------------------------------------
# Os Diagramas
# ----------------------------------------------------------------------
def _diagrama(**campos):
    base = dict(lido=True, conferido=False, validacao=None, confiavel=True, lado="w",
                motivo="", caixa=(0, 0, 10, 10))
    base.update(campos)
    return SimpleNamespace(**base)


@pytest.fixture
def diagramas(app):
    painel = PainelDeDiagramas()
    painel.mostrar([(2, [_diagrama(), _diagrama(conferido=True)])])
    yield painel
    painel.deleteLater()


def test_o_menu_dos_diagramas_abre_atualiza_e_filtra(diagramas):
    abertos, pedidos = [], []
    diagramas.abrir.connect(lambda pagina, k: abertos.append((pagina, k)))
    diagramas.atualizar_pedido.connect(lambda: pedidos.append(1))
    menu = diagramas.menu_de_contexto()
    assert not _acao(menu, "Abrir na conferência").isEnabled()
    diagramas.grade.setCurrentRow(0)
    menu = diagramas.menu_de_contexto()
    _acao(menu, "Abrir na conferência").trigger()
    _acao(menu, "Atualizar").trigger()
    assert abertos == [(2, 0)] and pedidos == [1]
    filtros = _acao(menu, "Mostrar").menu()
    marcados = [a.text() for a in filtros.actions() if a.isChecked()]
    assert marcados == ["Por conferir"]
    next(a for a in filtros.actions() if a.text() == "Conferidos").trigger()
    assert diagramas.filtro_atual() == "conferidos" and diagramas.itens() == [(2, 1)]


# ----------------------------------------------------------------------
# A Linha
# ----------------------------------------------------------------------
def test_o_menu_da_linha_copia_o_texto_e_traz_as_acoes_da_janela(app):
    faixa = FaixaDaLinha()
    esconder = QAction("Linha", faixa)
    esconder.setCheckable(True)
    faixa.acoes_do_menu.append(esconder)
    menu = faixa.menu_de_contexto()
    assert _textos(menu) == ["Copiar o texto da linha", "Linha"]
    assert not _acao(menu, "Copiar").isEnabled()
    matriz = np.full((100, 200), 255, np.uint8)
    boxes = [BoxEntry(c, 20 + 20 * k, 40, 32 + 20 * k, 60, 0.9, "net")
             for k, c in enumerate(("N", "f", "3"))]
    boxes.append(BoxEntry("", 100, 40, 112, 60, 0.0, ""))      # o glifo sem leitura
    faixa.mostrar(matriz, boxes, 0)
    _acao(faixa.menu_de_contexto(), "Copiar").trigger()
    assert QApplication.clipboard().text() == "Nf3□"
    faixa.deleteLater()


# ----------------------------------------------------------------------
# Shift+F10 em cada um, fora da janela
# ----------------------------------------------------------------------
def test_shift_f10_abre_o_menu_nos_quatro_paineis(app, galeria, padroes, diagramas):
    painel, _arquivos = padroes
    faixa = FaixaDaLinha()
    faixa.resize(300, 80)
    for widget in (galeria.vista.viewport(), painel.amostras.viewport(),
                   painel.caracteres.viewport(), diagramas.grade.viewport(), faixa):
        assert _abre_pelo_teclado(app, widget), widget
    faixa.deleteLater()
