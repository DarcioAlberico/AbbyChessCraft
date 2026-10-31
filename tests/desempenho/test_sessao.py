r"""O plano da sessão do Documento sobre a página inteira (SPEC §5, passo D2): cada confirmação
planeja a página toda, então o `planejar` tem de crescer linear nos glifos.

    .venv\Scripts\python.exe -m pytest -q -m desempenho tests\desempenho\test_sessao.py

Achado no Q8: `_dividir_ligaduras_repetidas` contava, para cada glifo, quantas vezes ele
aparece percorrendo todos os itens; numa página de 2 500 glifos, ~0,5 s de cada confirmação.
"""

from __future__ import annotations

import time

import pytest

from abbychess import sessao as ss

pytestmark = pytest.mark.desempenho


def _pagina(glifos: int):
    """Palavras de cinco glifos separadas por espaço, como uma página de prosa."""
    unidades, gid = [], 0
    while gid < glifos:
        if unidades:
            unidades.append(ss.Unidade(" ", None, ss.ESPACO))
        for _ in range(5):
            unidades.append(ss.Unidade("abcde"[gid % 5], gid, ss.GLIFO))
            gid += 1
    return unidades


def _planejar(glifos: int) -> float:
    unidades = _pagina(glifos)
    original = "".join(u.texto for u in unidades)
    novo = "z" + original[1:]                           # só o primeiro glifo foi tocado
    fixos = [(k, k) for k in range(1, len(original))]
    melhor = float("inf")
    for _ in range(3):
        inicio = time.perf_counter()
        ss.planejar(unidades, novo, fixos)
        melhor = min(melhor, time.perf_counter() - inicio)
    return melhor


def test_planejar_a_pagina_inteira_cresce_linear_nos_glifos():
    menor, maior = _planejar(1250), _planejar(2500)
    # Linear: o dobro dos glifos, ~o dobro do tempo; quadrático, ~4x.
    assert maior < 2.8 * menor, f"{menor * 1000:.0f} ms -> {maior * 1000:.0f} ms"
