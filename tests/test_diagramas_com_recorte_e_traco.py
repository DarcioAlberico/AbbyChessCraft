"""CA-U5c (SPEC-pagina-perfeita, U-5c; T1, bloco 4): a grade da aba Diagramas tem o impresso de
todos os diagramas, e não só os das páginas na memória; na Imagem, cada estado do tabuleiro tem
o seu traço, e não só a cor, com a legenda de quatro linhas.

Antes, as páginas fora da memória mostravam "recorte na Imagem", e os quatro estados usavam o
mesmo tracejado, só com cores diferentes.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QLabel  # noqa: E402

from core.box_model import BoxEntry  # noqa: E402

from abbychess.app import estilo  # noqa: E402
from abbychess.app.painel_diagramas import PainelDeDiagramas  # noqa: E402
from abbychess.app.painel_treino import PainelDeTreino  # noqa: E402
from abbychess.app.visor import VisorDePagina  # noqa: E402

from tests.ajudantes import _lido, esperar  # noqa: E402
from tests.fixturas_paginas_na_janela import janela  # noqa: E402,F401,F811


def _estados():
    """Um diagrama de cada estado: por ler, a conferir, confiável, conferido."""
    return (SimpleNamespace(lido=False, conferido=False, confiavel=False),
            SimpleNamespace(lido=True, conferido=False, confiavel=False),
            SimpleNamespace(lido=True, conferido=False, confiavel=True),
            SimpleNamespace(lido=True, conferido=True, confiavel=True))


def test_cada_estado_do_tabuleiro_tem_o_seu_traco():
    tracos = [estilo.traco_do_diagrama(d) for d in _estados()]
    assert len({t.estilo for t in tracos}) == 4                  # o traço, e não só a cor
    assert [t.cor for t in tracos] == [estilo.cor_do_diagrama(d) for d in _estados()]


def test_a_imagem_desenha_o_traco_do_estado(app):
    visor = VisorDePagina()
    caixas = [(10 + 60 * k, 10, 60 + 60 * k, 60) for k in range(4)]
    tracos = [estilo.traco_do_diagrama(d) for d in _estados()]
    visor.mostrar_boxes([BoxEntry("a", 5, 5, 8, 8, 1.0, "manual")], set(), caixas, tracos)
    assert [item.pen().style() for item in visor._itens] == [t.estilo for t in tracos]
    visor.deleteLater()


def test_a_legenda_do_glifo_tem_os_quatro_estados_do_diagrama(app):
    painel = PainelDeTreino()
    textos = {r.text() for r in painel.findChildren(QLabel)}
    for nome in ("Diagrama por ler", "Diagrama a conferir", "Diagrama confiável",
                 "Diagrama conferido"):
        assert nome in textos, nome
    painel.deleteLater()


def test_o_recorte_que_chega_depois_entra_na_grade(app):
    painel = PainelDeDiagramas()
    painel.mostrar([(7, [_lido()])], recorte=lambda *_a: None)
    assert not painel.tem_recorte(7, 0)
    antes = painel.grade.item(0).icon().pixmap(64, 32).toImage()
    impresso = QImage(40, 40, QImage.Format.Format_Grayscale8)
    impresso.fill(Qt.GlobalColor.black)
    painel.mostrar_recorte(7, 0, impresso)
    assert painel.tem_recorte(7, 0)
    assert painel.grade.item(0).icon().pixmap(64, 32).toImage() != antes
    painel.mostrar_recorte(99, 0, impresso)                      # de outra carga: nada
    painel.deleteLater()


def test_a_janela_traz_o_recorte_da_pagina_fora_da_memoria(app, janela, monkeypatch):  # noqa: F811
    j = janela
    fora = 40                                     # longe das páginas que a janela guarda
    assert fora not in j._pixmaps
    monkeypatch.setattr(j.conferencia, "do_livro",
                        lambda pronto: pronto([(fora, [_lido(caixa=(10, 10, 110, 110))])]))
    j.vista.setCurrentWidget(j.painel_diagramas)
    j.painel_diagramas.definir_filtro("todos")
    j.atualizar_diagramas()
    assert esperar(lambda: j.painel_diagramas.tem_recorte(fora, 0), 20)
