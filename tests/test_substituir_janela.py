"""Substituir na janela (SPEC §7.2, passo D2): Ctrl+H, Substituir e a próxima, Todas na
página (direto) e no livro (sempre a prévia em Resultados, e Enter aplica), o caso sem
tradução desabilitado e o Ctrl+Z que volta tudo."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from abbychess import busca as bs
from abbychess import sessao as ss

from tests.test_busca_janela import _ate, _buscar, _pagina_lida, jb  # noqa: F401 (fixture)
from tests.test_documento import app  # noqa: F401 (fixture)
from tests.test_documento_edicao import _janela_do_modulo, j  # noqa: F401 (fixtures)


def _texto(jb):  # noqa: F811
    return ss.texto_e_unidades(jb.pagina.modelo)[0]


def _substituir_por(jb, texto):  # noqa: F811
    b = jb.barra_de_busca
    jb.substituir()
    b.substituto.setText(texto)


def test_ctrl_h_mostra_a_linha_de_substituir_e_ctrl_f_a_esconde(jb):  # noqa: F811
    _pagina_lida(jb, "casa velha")
    _buscar(jb, "casa")
    jb.substituir()
    b = jb.barra_de_busca
    assert b.substituindo
    jb.localizar()
    assert not b.substituindo


def test_substituir_troca_a_atual_e_vai_a_proxima(jb):  # noqa: F811
    _pagina_lida(jb, "casa velha casa")
    _buscar(jb, "casa")
    _substituir_por(jb, "lata")
    jb.substituir_atual()                                 # a primeira ocorrência (o Ctrl+H
    _ate(lambda: jb._posicao == 0)                        # buscou de novo: espera ela)
    jb.substituir_atual()                                 # troca ela
    _ate(lambda: _texto(jb) == "lata velha casa")
    _ate(lambda: jb.barra_de_busca.contador.text() == "1 de 1")   # e foi à próxima
    jb.desfazer()
    _ate(lambda: _texto(jb) == "casa velha casa")


def test_todas_no_livro_so_aplica_pela_previa(jb):  # noqa: F811
    _pagina_lida(jb, "casa velha casa")
    _buscar(jb, "casa")
    _substituir_por(jb, "lata")
    jb.substituir_todas()
    lista = jb.resultados.resultados
    _ate(lambda: jb.resultados.na_previa)
    assert _texto(jb) == "casa velha casa"               # nada sem a prévia (CA-7.5)
    marcados = [lista.item(n) for n in range(lista.count())
                if lista.item(n).checkState() == Qt.CheckState.Checked]
    assert len(marcados) == 2 and "Aplicar 2" in jb.resultados.botao_aplicar.text()
    marcados[1].setCheckState(Qt.CheckState.Unchecked)   # desmarcar um caso
    QTest.keyClick(lista, Qt.Key.Key_Return)              # Enter aplica
    _ate(lambda: _texto(jb) == "lata velha casa")
    jb.desfazer()
    _ate(lambda: _texto(jb) == "casa velha casa")


def test_todas_na_pagina_aplica_direto(jb):  # noqa: F811
    _pagina_lida(jb, "casa velha casa")
    _buscar(jb, "casa")
    jb.barra_de_busca.escolher_escopo(bs.PAGINA)
    _substituir_por(jb, "lata")
    jb.substituir_todas()
    _ate(lambda: _texto(jb) == "lata velha lata")
    assert not jb.resultados.na_previa


def test_o_caso_sem_traducao_vem_desabilitado_na_previa(jb):  # noqa: F811
    _pagina_lida(jb, "uma casa")
    _buscar(jb, "m")
    _substituir_por(jb, "rn")
    jb.substituir_todas()
    _ate(lambda: jb.resultados.na_previa)
    lista = jb.resultados.resultados
    item = lista.item(1)
    assert not item.flags() & Qt.ItemFlag.ItemIsEnabled and "dividir" in item.toolTip()
    assert not jb.resultados.botao_aplicar.isEnabled()
