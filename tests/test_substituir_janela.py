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
    jb._limpar_previa()                                  # a do teste anterior
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
    _ate(lambda: jb.resultados.na_previa)
    assert _texto(jb) == "casa velha casa"               # nada sem a prévia (CA-7.5)
    modelo, vista = jb.resultados.modelo_da_previa, jb.resultados.previa
    assert modelo.rowCount() == 2 and "Aplicar 2" in jb.resultados.botao_aplicar.text()
    vista.setCurrentIndex(modelo.index(1))
    QTest.keyClick(vista, Qt.Key.Key_Space)               # desmarcar um caso
    assert "Aplicar 1" in jb.resultados.botao_aplicar.text()
    QTest.keyClick(vista, Qt.Key.Key_Return)              # Enter aplica
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


def test_o_caso_estrutural_vem_habilitado_na_previa(jb):  # noqa: F811
    _pagina_lida(jb, "uma casa")
    _buscar(jb, "m")
    _substituir_por(jb, "rn")
    jb.substituir_todas()
    _ate(lambda: jb.resultados.na_previa)
    modelo = jb.resultados.modelo_da_previa
    indice = modelo.index(0)
    assert modelo.flags(indice) & Qt.ItemFlag.ItemIsEnabled
    assert not modelo.data(indice, Qt.ItemDataRole.ToolTipRole)
    assert jb.resultados.botao_aplicar.isEnabled()


# ----------------------------------------------------------------------
# As revisões do passo D2
# ----------------------------------------------------------------------

def test_a_previa_mostra_e_aplica_todos_os_casos_mesmo_alem_de_2000(jb):  # noqa: F811
    from abbychess.app import painel_resultados as pr

    linhas = [" ".join(["a"] * 75) for _ in range(30)]   # 2.250 casos
    _pagina_lida(jb, *linhas)
    _buscar(jb, "a")
    _substituir_por(jb, "o")
    jb.substituir_todas()
    _ate(lambda: jb.resultados.na_previa, 30)
    assert jb.resultados.modelo_da_previa.rowCount() == 2250 > pr.LIMITE_DE_LINHAS
    assert "Aplicar 2250" in jb.resultados.botao_aplicar.text()
    QTest.keyClick(jb.resultados.previa, Qt.Key.Key_Return)
    _ate(lambda: "a" not in _texto(jb), 30)
    jb.desfazer()                                         # um Ctrl+Z volta todos
    _ate(lambda: "o" not in _texto(jb), 30)


def test_shift_enter_e_o_duplo_clique_vao_ao_caso(jb, monkeypatch):  # noqa: F811
    _pagina_lida(jb, "casa velha casa")
    _buscar(jb, "casa")
    _substituir_por(jb, "lata")
    jb.substituir_todas()
    _ate(lambda: jb.resultados.na_previa)
    idas, gids = [], []
    monkeypatch.setattr(jb, "_ir_a_pagina_ja_montada", idas.append)
    monkeypatch.setattr(jb.texto, "ir_ao_gid", gids.append)
    modelo, vista = jb.resultados.modelo_da_previa, jb.resultados.previa
    vista.setCurrentIndex(modelo.index(1))
    QTest.keyClick(vista, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    caso = modelo.caso(1)
    assert idas == [caso.pagina] and gids == [caso.gids[0]]
    assert _texto(jb) == "casa velha casa"                # foi, sem aplicar
    vista.doubleClicked.emit(modelo.index(0))
    assert gids[-1] == modelo.caso(0).gids[0]


def test_substituir_pula_o_que_ja_esta_como_o_substituto(jb):  # noqa: F811
    _pagina_lida(jb, "casa velha")
    _buscar(jb, "casa")
    _substituir_por(jb, "Casa")
    jb.substituir_atual()
    _ate(lambda: jb._posicao == 0)
    jb.substituir_atual()
    _ate(lambda: _texto(jb) == "Casa velha")
    _ate(lambda: not jb.busca.buscando and not jb.barra_de_busca.relogio.isActive())
    jb.substituir_atual()                                 # "Casa" já é o substituto
    assert "erro" not in jb.barra_de_busca.contador.text()
    assert "Nada mais a substituir" in jb.statusBar().currentMessage()


def test_outra_substituicao_tira_a_previa_velha(jb):  # noqa: F811
    from abbychess import busca as bs

    _pagina_lida(jb, "casa velha casa")
    _buscar(jb, "casa")
    _substituir_por(jb, "casas")
    jb.substituir_todas()
    _ate(lambda: jb.resultados.na_previa)
    jb.barra_de_busca.escolher_escopo(bs.PAGINA)
    jb.substituir_todas()                                 # Todas na página, por fora
    _ate(lambda: _texto(jb) == "casas velha casas")
    _ate(lambda: not jb.resultados.na_previa)
    assert "A prévia saiu" in jb.resultados.resultados.item(0).text()


def test_substituir_pula_o_ja_trocado_tambem_noutra_pagina(jb, monkeypatch):  # noqa: F811
    from dataclasses import replace

    _pagina_lida(jb, "Casa velha")
    _buscar(jb, "casa")
    _substituir_por(jb, "Casa")
    _ate(lambda: not jb.busca.buscando and not jb.barra_de_busca.relogio.isActive())
    noutra = replace(jb._ocorrencias[0], pagina=5)       # uma "Casa" na página 6
    jb._ocorrencias, jb._posicao = [jb._ocorrencias[0], noutra], 0
    idas = []
    monkeypatch.setattr(jb, "_ir_a_ocorrencia", idas.append)
    jb.substituir_atual()
    assert idas == [] and "Nada mais a substituir" in jb.statusBar().currentMessage()
