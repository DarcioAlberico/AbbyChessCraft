"""CA-U6 (SPEC-pagina-perfeita, U-6; T1, bloco 3): com o disco falhando, a faixa da gravação
fica à vista até a página gravar; o ⚠ da barra fica na cor de erro enquanto houver erro não
visto; o botão da faixa abre Avisos.

Antes, a falha de gravação pesava igual a um aviso: uma linha na barra, que a próxima
mensagem apagava, e o ⚠ igual ao de um aviso qualquer. Fechar o programa ali perdia a edição.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from abbychess import avisos as av  # noqa: E402
from abbychess import gravacao as gv  # noqa: E402

from tests.ajudantes import _ler_a_mao, esperar  # noqa: E402
from tests.fixturas_espaco import janela  # noqa: E402,F401,F811


def _visivel(widget) -> bool:
    QApplication.processEvents()
    return widget.isVisible()


def test_a_faixa_fica_ate_a_pagina_gravar(app, janela, monkeypatch):  # noqa: F811
    j = janela
    _ler_a_mao(app, j)
    assert j.projeto.paginas_em_memoria.descarregar(10)       # a leitura gravada antes
    faixa = j.faixa_de_gravacao
    assert not faixa.isVisible()
    original = gv._trocar

    def falhar(*_a):
        raise PermissionError("disco bloqueado")
    monkeypatch.setattr(gv, "_trocar", falhar)
    j.pagina.modelo.boxes[0].entry.char = "x"
    j._glifos_mudaram()                                       # agenda a gravação
    assert esperar(lambda: _visivel(faixa), 10)
    assert "não foi gravada" in faixa.texto.text() and "disco bloqueado" in faixa.texto.text()
    j.statusBar().showMessage("outra coisa")                  # a barra muda; a faixa fica
    for _ in range(5):
        QApplication.processEvents()
    assert faixa.isVisible()
    monkeypatch.setattr(gv, "_trocar", original)              # o disco volta
    assert esperar(lambda: not _visivel(faixa), 10)
    assert not j.projeto.paginas_em_memoria.falhando


def test_o_botao_da_faixa_abre_os_avisos(app, janela):  # noqa: F811
    j = janela
    j.falha_de_gravacao.emit(0, OSError("disco cheio"))
    QApplication.processEvents()
    j.faixa_de_gravacao.botao.click()
    QApplication.processEvents()
    assert j.doca_resultados.isVisible()
    assert j.resultados.currentWidget() is j.resultados.avisos


def test_o_aviso_de_erro_pinta_o_botao_na_cor_de_erro(app, janela):  # noqa: F811
    j = janela
    assert (j.botao_avisos.property("papel") or "") == ""
    j.registrar_aviso(av.AVISO, "Teste", "um aviso qualquer")
    assert (j.botao_avisos.property("papel") or "") == "aviso"
    j.falha_de_gravacao.emit(0, OSError("disco cheio"))
    QApplication.processEvents()
    assert j.botao_avisos.property("papel") == "erro"
    j.abrir_avisos()                                          # visto: volta ao normal
    assert (j.botao_avisos.property("papel") or "") == ""
