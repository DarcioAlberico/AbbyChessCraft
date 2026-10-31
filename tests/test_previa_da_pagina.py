"""O corte e a divisão marcados sobre a página, com prévia (SPEC §12.4, a dívida do fechamento
do L): a miniatura e os campos de porcentagem andam juntos, nos dois sentidos."""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from abbychess.app import dialogo_paginas as dp  # noqa: E402
from abbychess.app import imagens  # noqa: E402
from abbychess.app import previa_da_pagina as pp  # noqa: E402

from tests.fixturas_paginas_na_janela import janela  # noqa: E402,F401,F811


def _pixmap(largura=400, altura=600):
    return imagens.pixmap_de_cinza(np.full((altura, largura), 255, dtype=np.uint8))


def _arrastar(widget, de, ate):
    """Aperta em `de`, arrasta até `ate` e solta (pixels da miniatura)."""
    botao, nenhum = Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton
    eventos = ((QEvent.Type.MouseButtonPress, de, botao, botao),
               (QEvent.Type.MouseMove, ate, nenhum, botao),
               (QEvent.Type.MouseButtonRelease, ate, botao, nenhum))
    for tipo, ponto, qual, apertados in eventos:
        p = QPointF(*ponto)
        QApplication.sendEvent(widget, QMouseEvent(tipo, p, widget.mapToGlobal(p), qual,
                                                   apertados, Qt.KeyboardModifier.NoModifier))


@pytest.fixture
def corte(app):  # noqa: F811
    margens = [dp.campo_de_porcentagem(0.0, 0.0, 95.0) for _ in range(4)]
    previa = pp.PreviaDoCorte(_pixmap(), margens, "A página 1")
    yield previa, margens
    previa.deleteLater()


def test_a_miniatura_cabe_e_guarda_a_proporcao(corte, app):  # noqa: F811
    previa, _ = corte
    assert (previa.width(), previa.height()) == (pp.ALTURA_DA_PREVIA * 2 // 3,
                                                 pp.ALTURA_DA_PREVIA)
    dupla = pp.PreviaDaDivisao(_pixmap(1000, 600), dp.campo_de_porcentagem(50, 5, 95), "")
    assert (dupla.width(), dupla.height()) == (pp.LARGURA_DA_PREVIA, 240)
    dupla.deleteLater()


def test_os_campos_mudam_o_retangulo(corte):
    previa, margens = corte
    margens[0].setValue(10.0)
    margens[3].setValue(25.0)
    r = previa.retangulo()
    assert r.left() == pytest.approx(0.10 * previa.width())
    assert r.bottom() == pytest.approx(0.75 * previa.height())
    assert r.top() == 0 and r.right() == previa.width()


def test_arrastar_a_borda_esquerda_muda_so_a_margem_esquerda(corte):
    previa, margens = corte
    meio_y = previa.height() / 2
    _arrastar(previa, (0, meio_y), (previa.width() * 0.2, meio_y))
    assert [m.value() for m in margens] == [pytest.approx(20.0, abs=0.1), 0, 0, 0]


def test_arrastar_o_canto_muda_duas_margens(corte):
    previa, margens = corte
    w, h = previa.width(), previa.height()
    _arrastar(previa, (w, h), (w * 0.9, h * 0.8))
    assert [m.value() for m in margens] == [0, 0, pytest.approx(10.0, abs=0.1),
                                             pytest.approx(20.0, abs=0.1)]


def test_a_borda_nao_passa_da_outra(corte):
    """O corte que deixaria a página vazia para antes: sobram 5% no mínimo."""
    previa, margens = corte
    margens[2].setValue(40.0)                     # a direita em 60%
    meio_y = previa.height() / 2
    _arrastar(previa, (0, meio_y), (previa.width(), meio_y))
    assert margens[0].value() == pytest.approx(60.0 - pp.SOBRA_MINIMA, abs=0.1)
    assert margens[2].value() == 40.0


def test_desenhar_um_retangulo_novo_fora_do_corte(corte):
    previa, margens = corte
    for m, v in zip(margens, (30.0, 30.0, 30.0, 30.0)):
        m.setValue(v)
    w, h = previa.width(), previa.height()
    _arrastar(previa, (w * 0.05, h * 0.9), (w * 0.5, h * 0.75))   # de baixo para cima
    assert [m.value() for m in margens] == [pytest.approx(v, abs=0.2)
                                             for v in (5.0, 75.0, 50.0, 10.0)]


def test_um_clique_fora_nao_apaga_o_corte(corte):
    previa, margens = corte
    for m in margens:
        m.setValue(20.0)
    _arrastar(previa, (2, 2), (3, 3))
    assert [m.value() for m in margens] == [20.0] * 4


def test_arrastar_dentro_move_o_retangulo_sem_sair_da_pagina(corte):
    previa, margens = corte
    margens[0].setValue(10.0)
    margens[2].setValue(50.0)                     # de 10% a 50% da largura
    w, h = previa.width(), previa.height()
    _arrastar(previa, (w * 0.3, h * 0.5), (w * 0.9, h * 0.5))   # +60%, só cabem +50%
    assert margens[0].value() == pytest.approx(60.0, abs=0.1)
    assert margens[2].value() == pytest.approx(0.0, abs=0.1)


def test_o_arraste_avisa_a_previa_do_dialogo_uma_vez(corte):
    """As quatro margens mudam juntas, e a prévia ("1 página é cortada…") é refeita uma vez."""
    previa, margens = corte
    vezes = []
    margens[0].valueChanged.connect(lambda _v: vezes.append(1))
    w, h = previa.width(), previa.height()
    _arrastar(previa, (w * 0.1, h * 0.1), (w * 0.6, h * 0.6))
    assert len(vezes) == 1


def test_a_linha_da_divisao_segue_o_clique_e_o_campo(app):  # noqa: F811
    onde = dp.campo_de_porcentagem(50.0, 5.0, 95.0, " % da largura")
    previa = pp.PreviaDaDivisao(_pixmap(600, 400), onde, "A página 1")
    assert previa.x_da_linha() == pytest.approx(previa.width() / 2)
    _arrastar(previa, (previa.width() * 0.3, 10), (previa.width() * 0.42, 10))
    assert onde.value() == pytest.approx(42.0, abs=0.2)
    _arrastar(previa, (0, 10), (0, 10))           # na borda: o campo para em 5%
    assert onde.value() == 5.0
    onde.setValue(70.0)
    assert previa.x_da_linha() == pytest.approx(previa.width() * 0.7)
    previa.deleteLater()


def test_o_dialogo_mostra_a_miniatura(app):  # noqa: F811
    margens = [dp.campo_de_porcentagem(0.0, 0.0, 95.0) for _ in range(4)]
    previa = pp.PreviaDoCorte(_pixmap(), margens, "A página 3")
    d = dp.DialogoDasPaginas(None, "Cortar", 20, selecao="3", miniatura=previa,
                             linhas=list(zip("ecdb", margens)))
    assert previa.parent() is d and previa.accessibleName() == "A página 3"
    d.deleteLater()


def test_cortar_e_dividir_pela_janela_trazem_a_pagina_aberta(app, janela, monkeypatch):  # noqa: F811
    pedidos = []
    monkeypatch.setattr(dp, "perguntar_com",
                        lambda *_a, **k: pedidos.append(k) or None)
    janela.acao_cortar_paginas.trigger()
    janela.acao_dividir_paginas.trigger()
    corte, divisao = (k["miniatura"] for k in pedidos)
    assert isinstance(corte, pp.PreviaDoCorte) and isinstance(divisao, pp.PreviaDaDivisao)
    assert corte.accessibleName() == "A página 1"


def test_a_miniatura_de_outra_pagina_vem_do_cache(app, janela):  # noqa: F811
    pixmap, legenda = janela._miniatura([4, 7])
    assert not pixmap.isNull()
    assert legenda.startswith("A página 5 (")
