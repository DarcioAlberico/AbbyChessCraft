"""Desfazer e refazer (Ctrl+Z, Ctrl+Y): a página e os padrões que o passo gravou."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from core.box_model import BoxEntry  # noqa: E402

from abbychess import historico as hs  # noqa: E402
from abbychess.leitor import FONTE_LIVRO, FONTE_MANUAL  # noqa: E402
from abbychess.padroes import PadroesDoLivro  # noqa: E402

from tests import test_janela  # noqa: E402
from tests.test_janela import _esperar  # noqa: E402

# As fixtures da janela de `test_janela`, com o mesmo nome aqui.
app = test_janela.app
janela = test_janela.janela


def _caixas(boxes):
    return [(b.char, b.x1, b.y1, b.x2, b.y2, b.source) for b in boxes]


# ----------------------------------------------------------------------
# O histórico, sem janela
# ----------------------------------------------------------------------

def _passo(n, juntar=None):
    return hs.Passo(f"passo {n}", hs.instantaneo([BoxEntry(str(n), 0, 0, 1, 1)]),
                    hs.instantaneo([BoxEntry(str(n + 1), 0, 0, 1, 1)]), juntar=juntar)


def test_desfazer_e_refazer_andam_nas_duas_pilhas():
    historico = hs.Historico()
    historico.registrar(_passo(1))
    historico.registrar(_passo(2))
    assert historico.desfazer().descricao == "passo 2"
    assert historico.proximo_a_refazer == "passo 2"
    assert historico.refazer().descricao == "passo 2"
    assert historico.refazer() is None


def test_passo_novo_apaga_o_refazer():
    historico = hs.Historico()
    historico.registrar(_passo(1))
    historico.desfazer()
    historico.registrar(_passo(5))
    assert historico.proximo_a_refazer is None
    assert historico.proximo_a_desfazer == "passo 5"


def test_passos_com_a_mesma_chave_viram_um():
    historico = hs.Historico()
    for n in range(3):
        historico.registrar(_passo(n, juntar=("ajustar", 7)))
    passo = historico.desfazer()
    assert passo.antes.boxes[0].char == "0" and passo.depois.boxes[0].char == "3"
    assert historico.desfazer() is None


def test_limite_tira_o_mais_antigo():
    historico = hs.Historico(limite=2)
    for n in range(4):
        historico.registrar(_passo(n))
    assert [historico.desfazer().descricao for _ in range(2)] == ["passo 3", "passo 2"]
    assert historico.desfazer() is None


def test_instantaneo_e_copia_e_nao_referencia():
    boxes = [BoxEntry("a", 0, 0, 1, 1)]
    estado = hs.instantaneo(boxes)
    boxes[0].char = "z"
    assert estado.boxes[0].char == "a"


def test_padrao_guardado_volta_inteiro(tmp_path):
    import numpy as np

    padroes = PadroesDoLivro(tmp_path / "padroes")
    recorte = np.full((20, 12), 255, np.uint8)
    recorte[4:16, 3:9] = 0
    caminho = padroes.ensinar(recorte, "a", altura_relativa=0.8, origem="p1")
    amostra = padroes.guardar(caminho)
    padroes.esquecer(caminho)
    assert padroes.total == 0

    padroes.restaurar(amostra)
    assert padroes.total == 1
    assert padroes.amostras_de("a") == [(caminho.resolve(), pytest.approx(0.8))]
    with pytest.raises(ValueError):
        padroes.restaurar(type(amostra)(tmp_path / "fora.png", amostra.png, {}))


# ----------------------------------------------------------------------
# Na janela
# ----------------------------------------------------------------------

def _reconhecida(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    return _caixas(janela.boxes)


def test_ctrl_z_desfaz_o_ensinar_e_apaga_o_padrao(app, janela):
    inicio = _reconhecida(app, janela)
    janela._mostrar_box(0)
    janela.treino.campo.setText("a")
    janela.treino._ensinar()
    _esperar(app, janela)
    assert sum(b.source == FONTE_LIVRO for b in janela.boxes) == 4
    assert janela.acao_desfazer.text() == "Desfazer: Ensinar 'a'"

    janela.show()
    janela.treino.campo.setFocus()
    app.processEvents()
    QTest.keyClick(janela.treino.campo, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    app.processEvents()

    assert _caixas(janela.boxes) == inicio
    assert janela.leitor.padroes_por_caractere() == {}
    assert _caixas(janela.projeto.carregar_pagina(0)) == inicio  # gravado já desfeito

    QTest.keyClick(janela.treino.campo, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    app.processEvents()
    assert len(janela.leitor.padroes_por_caractere()["a"]) == 1
    assert janela.boxes[0].source == FONTE_MANUAL
    assert sum(b.source == FONTE_LIVRO for b in janela.boxes) == 4


def test_desfazer_dividir_e_descartar(app, janela):
    inicio = _reconhecida(app, janela)
    janela._mostrar_box(0)
    janela.treino._juntar(+1)
    janela.treino._dividir()
    janela._mostrar_box(2)
    janela.treino._descartar()
    assert len(janela.boxes) == len(inicio) - 1

    janela.desfazer()                    # volta o descartado
    assert len(janela.boxes) == len(inicio)
    janela.desfazer()                    # desfaz a divisão: o par colado volta
    assert len(janela.boxes) == len(inicio) - 1
    janela.desfazer()                    # desfaz a junção
    assert _caixas(janela.boxes) == inicio
    # O que sobra é o próprio F5, que também se desfaz.
    assert janela.acao_desfazer.text() == "Desfazer: Reconhecer a página"


def test_alt_seta_seguidos_se_desfazem_de_uma_vez(app, janela):
    inicio = _reconhecida(app, janela)
    janela._mostrar_box(0)
    for _ in range(3):
        janela.treino._ajustar(0, 0, 1, 0)
    janela.desfazer()
    assert _caixas(janela.boxes) == inicio


def test_cada_pagina_tem_o_seu_historico(app, janela):
    _reconhecida(app, janela)
    janela._mostrar_box(0)
    janela.treino._descartar()
    assert janela.acao_desfazer.isEnabled()
    janela.historicos.pop(0)             # como se fosse outra página
    janela._atualizar_acoes()
    assert not janela.acao_desfazer.isEnabled()


def test_desfazer_o_reconhecimento_volta_a_pagina_de_antes(app, janela):
    _reconhecida(app, janela)
    janela._mostrar_box(0)
    janela.treino.campo.setText("Z")
    janela.treino._so_corrigir()
    corrigida = _caixas(janela.boxes)
    janela.reconhecer()                  # o F5 de novo apaga a correção
    _esperar(app, janela)
    assert janela.boxes[0].char != "Z"
    janela.desfazer()
    assert _caixas(janela.boxes) == corrigida
