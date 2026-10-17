"""Localizar na janela (SPEC §7.1, passo B): Ctrl+F, a barra, F3 e Shift+F3, o destaque no
Documento, Alt+Enter e os Resultados, a contagem na gaveta, a regex inválida, o Esc e a
busca por glifo."""

from __future__ import annotations

import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from abbychess.app.documento import FUNDO_DA_BUSCA, FUNDO_DA_OCORRENCIA

from tests.test_documento import app  # noqa: F401 (fixture)
from tests.test_documento_edicao import _escrever, _janela_do_modulo, j  # noqa: F401 (fixtures)


@pytest.fixture
def jb(j):  # noqa: F811
    return j


def _ate(condicao, limite=10.0):
    fim = time.monotonic() + limite
    while not condicao() and time.monotonic() < fim:
        QApplication.processEvents()
        time.sleep(0.005)
    assert condicao()


def _pagina_lida(jb, *linhas):
    """A página escrita, gravada e no índice da busca."""
    pagina = _escrever(jb, *linhas)
    jb.projeto.salvar_modelo(pagina)
    jb.busca.abrir()
    _ate(jb.busca.pronto.is_set)
    return pagina


def _buscar(jb, texto, **marcas):
    b = jb.barra_de_busca
    jb.localizar()
    for nome, valor in marcas.items():
        getattr(b, nome).setChecked(valor)
    b.campo.setText(texto)
    b.contador.setText("")
    antes = jb.busca.ultimo_resultado
    b.relogio.stop()
    jb._buscar()
    _ate(lambda: jb.busca.ultimo_resultado is not antes or "erro" in b.contador.text())


def _cores(jb):
    return [s.format.background().color() for s in jb.texto.extraSelections()]


def test_ctrl_f_busca_f3_anda_e_o_documento_destaca(jb):
    pagina = _pagina_lida(jb, "casa velha casa")
    _buscar(jb, "casa")
    assert jb.barra_de_busca.isVisible() and jb.barra_de_busca.contador.text() == "2"
    assert _cores(jb).count(FUNDO_DA_BUSCA) == 2
    QTest.keyClick(jb, Qt.Key.Key_F3)
    QApplication.processEvents()
    assert jb.barra_de_busca.contador.text() == "1 de 2"
    assert FUNDO_DA_OCORRENCIA in _cores(jb)
    assert jb.texto.gid_no_cursor() == pagina.boxes[0].gid
    jb.proxima_ocorrencia()
    assert jb.barra_de_busca.contador.text() == "2 de 2"
    jb.ocorrencia_anterior()
    assert jb.barra_de_busca.contador.text() == "1 de 2"
    jb.paginas.mostrar(jb.pagina.fonte.total, {}, None)      # a gaveta (fechada no teste)
    assert jb.paginas.lista.isColumnHidden(4) is False
    assert jb.paginas.lista.topLevelItem(0).text(4) == "2"


def test_alt_enter_manda_todas_para_resultados_e_a_linha_leva_ate_ela(jb):
    _pagina_lida(jb, "joga Cf3 e ♘f3")
    _buscar(jb, "Cf3", figurina=True, maiusculas=True)
    jb.todas_em_resultados()
    lista = jb.resultados.resultados
    assert jb.doca_resultados.isVisible() and "2 ocorrência" in lista.item(0).text()
    assert lista.item(1).text().startswith("p. 1, l. 1:")
    lista.itemActivated.emit(lista.item(2))
    assert jb.barra_de_busca.contador.text() == "2 de 2"


def test_a_regex_invalida_aparece_na_barra(jb):
    _pagina_lida(jb, "casa")
    _buscar(jb, "(casa", regex=True)
    assert jb.barra_de_busca.contador.text() == "erro"
    assert "inválida" in jb.barra_de_busca.contador.toolTip()


def test_nada_encontrado_e_o_esc_fecha_a_barra(jb):
    _pagina_lida(jb, "casa")
    _buscar(jb, "zzz")
    assert jb.barra_de_busca.contador.text() == "nada"
    assert "Nada encontrado" in jb.statusBar().currentMessage()
    jb.barra_de_busca.campo.setFocus()
    QApplication.processEvents()
    jb.fechar_sobreposicao()                               # Esc
    assert not jb.barra_de_busca.isVisible() and jb.paginas.lista.isColumnHidden(4)
    assert FUNDO_DA_BUSCA not in _cores(jb)


def test_a_pagina_editada_entra_na_busca_seguinte(jb):
    _pagina_lida(jb, "casa velha")
    _buscar(jb, "casas")
    assert jb.barra_de_busca.contador.text() == "nada"
    jb.fechar_busca()
    texto = jb.texto
    cursor = texto.textCursor()
    cursor.setPosition(4)
    texto.setTextCursor(cursor)
    QTest.keyClicks(texto, "s")
    QTest.keyClick(texto, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    QApplication.processEvents()
    _buscar(jb, "casas")
    assert jb.barra_de_busca.contador.text() == "1"


def test_a_busca_por_glifo_vai_para_resultados(jb, monkeypatch):
    from abbychess.app import busca_na_janela as bj

    pagina = _pagina_lida(jb, "casa")
    monkeypatch.setattr(bj.DialogoDaBuscaPorGlifo, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(bj.DialogoDaBuscaPorGlifo, "pedido", lambda self: ("a", None, 0.0, 1.0))
    jb.buscar_glifo()
    lista = jb.resultados.resultados
    assert "Glifos 'a'" in lista.item(0).text() and lista.count() == 3
    lista.itemActivated.emit(lista.item(2))
    assert jb.pagina.atual == pagina.boxes[3].gid
