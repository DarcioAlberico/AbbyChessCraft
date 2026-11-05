"""A caixa pela altura na leitura, para o Documento (SPEC-qualidade §13.9): só nas palavras sem
número nem figurina. No lance, a medida achou o "W" que era a dama mal lida (Aagaard, 9 de 9): ele
fica como foi lido, na fila de revisão."""

from __future__ import annotations

from core.box_model import BoxEntry

from abbychess import arrumacao
from abbychess import montagem as mo
from abbychess import texto as tx
from abbychess.leitor import FONTE_LIVRO, FONTE_MANUAL
from abbychess.modelo import Pagina
from abbychess.servidor_de_leitura import PaginaLida

#: A altura de cada letra: a altura-x 20, as maiúsculas 31.
ALTURAS = {**{c: 20 for c in "aemnrucosvwxz"}, **{c: 31 for c in "ABDEFGHIJKLMNPRTUYbdfhklit"},
           **{c: 20 for c in "OSVWCXZ"}}


def _linha(texto: str, y: int = 100, alturas=None, fonte: str = FONTE_LIVRO) -> list:
    saida = []
    for k, c in enumerate(texto):
        if c == " ":
            continue
        altura = (alturas or ALTURAS).get(c, 31)
        saida.append(BoxEntry(c, 300 + 24 * k, y + 31 - altura, 322 + 24 * k, y + 31, 0.9, fonte))
    return saida


def _texto(boxes) -> str:
    return "".join(b.char for b in boxes)


def test_a_palavra_sem_numero_nem_figurina_desce():
    boxes = _linha("hOnestly abOut LOndOn")
    mo.corrigir_a_caixa_na_leitura(boxes)
    assert _texto(boxes) == "honestlyaboutLondon"


def test_a_inicial_alta_sobe():
    boxes = _linha("white Hand and", alturas={**ALTURAS, "w": 31})
    mo.corrigir_a_caixa_na_leitura(boxes)
    assert _texto(boxes) == "WhiteHandand"


def test_o_lance_com_numero_fica_como_foi_lido():
    boxes = _linha("15.We2 hOnestly Rh3 Wh3-h6, abOut")
    mo.corrigir_a_caixa_na_leitura(boxes)
    assert _texto(boxes) == "15.We2honestlyRh3Wh3-h6,about"


def test_a_palavra_com_figurina_fica_como_foi_lida():
    boxes = _linha("♕cO hOnestly abOut")
    mo.corrigir_a_caixa_na_leitura(boxes)
    assert _texto(boxes) == "♕cOhonestlyabout"


def test_o_confirmado_fica():
    boxes = _linha("hOnestly abOut", fonte=FONTE_MANUAL)
    mo.corrigir_a_caixa_na_leitura(boxes)
    assert _texto(boxes) == "hOnestlyabOut"


def test_o_glifo_sem_leitura_nao_atrapalha():
    boxes = _linha("hOnestly abOut") + [BoxEntry("", 900, 100, 920, 130, 0.0, "neural")]
    mo.corrigir_a_caixa_na_leitura(boxes)
    assert _texto(boxes) == "honestlyabout"


def _lida(boxes) -> PaginaLida:
    return PaginaLida(boxes, [None] * len(boxes), [], None)


def test_a_pagina_lida_chega_ao_documento_com_a_caixa_certa():
    pagina = Pagina(pid=1, indice=0)
    arrumacao.aplicar_lida(pagina, _lida(_linha("hOnestly abOut 15.We2")), "en")
    assert tx.texto(tx.montar(pagina)) == "honestly about 15.We2"


def test_a_exportacao_nao_troca_de_novo_o_que_a_leitura_corrigiu():
    boxes = _linha("hOnestly abOut LOndOn")
    mo.corrigir_a_caixa_na_leitura(boxes)
    assert mo._caixa_pela_altura(boxes, range(len(boxes)), {0, 8, 13}, ()) == {}
