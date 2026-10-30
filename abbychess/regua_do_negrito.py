"""A régua do negrito do livro: a espessura do traço de cada caractere no peso redondo, juntada
das páginas lidas, para a página que se lê agora (§9.2).

**A régua da página sozinha não basta num livro de xadrez.** O `core.negrito` compara a
espessura de cada glifo com a das outras ocorrências do mesmo caractere (o quantil 25, o peso
redondo) e decide o negrito pelo peso da palavra contra o peso normal da página. Numa página
de partida quase todo algarismo, "x" e letra de casa está num lance da linha principal, em
negrito: o "redondo" deles sai negrito, o peso normal da página também, e o negrito some. O
core mede com o livro inteiro por isso (`core.negrito.marcar`: 90,2% com a página por
referência, 96,7% com 40 páginas, no Dvoretsky).

Cada página guarda a régua dela (`regua_da_pagina`: por caractere, a contagem, o quantil 25 e
a mediana), que vai ao resumo do livro (`livro.json`) com as outras contas da página; o
projeto junta as das outras páginas (`juntar`) e a manda com o pedido de leitura. A página
apagada sai da régua com o resumo dela, e a página relida troca a régua dela.
"""

from __future__ import annotations

from collections import defaultdict
from math import isnan
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

#: Por caractere: `[contagem, quantil 25, mediana]` das espessuras (`pagina.espessura_do_traco`).
Regua = Dict[str, List[float]]

#: Quantos glifos medidos o livro precisa ter para a régua dele valer (umas duas páginas de
#: texto): abaixo disso, a página decide sozinha, como antes.
MINIMO_DO_LIVRO = 3000

#: Quantas ocorrências um caractere precisa para entrar na conta do peso normal.
MINIMO_DO_CARACTERE = 5

CASAS = 5


def regua_da_pagina(caracteres: Sequence[str], espessuras: Sequence[Optional[float]]) -> Regua:
    """A régua dos glifos medidos de uma página (os de caractere lido)."""
    amostras: Dict[str, List[float]] = defaultdict(list)
    for char, medida in zip(caracteres, espessuras):
        if char and medida is not None and not isnan(medida):
            amostras[char].append(medida)
    return {char: [len(v), round(float(np.percentile(v, 25)), CASAS),
                   round(float(np.median(v)), CASAS)]
            for char, v in sorted(amostras.items())}


def _mediana_ponderada(valores: Sequence[float], pesos: Sequence[float]) -> float:
    ordem = np.argsort(valores)
    acumulado = np.cumsum(np.asarray(pesos, dtype=float)[ordem])
    return float(np.asarray(valores)[ordem][np.searchsorted(acumulado, acumulado[-1] / 2)])


def juntar(reguas: Iterable[Mapping[str, Sequence[float]]]) -> Regua:
    """A régua de várias páginas: por caractere, a contagem somada e a mediana dos quantis de
    cada página, pesada pela contagem (o quantil do conjunto, aproximado sem as amostras)."""
    por_char: Dict[str, List[Tuple[float, float, float]]] = defaultdict(list)
    for regua in reguas:
        for char, valores in (regua or {}).items():
            try:
                n, p25, p50 = (float(v) for v in valores[:3])
            except (TypeError, ValueError):
                continue                        # o resumo ilegível não estraga a régua
            if n > 0 and p25 > 0 and p50 > 0:
                por_char[char].append((n, p25, p50))
    saida: Regua = {}
    for char, itens in sorted(por_char.items()):
        pesos = [n for n, _, _ in itens]
        saida[char] = [sum(pesos), round(_mediana_ponderada([p for _, p, _ in itens], pesos), CASAS),
                       round(_mediana_ponderada([m for _, _, m in itens], pesos), CASAS)]
    return saida


def tamanho(regua: Optional[Regua]) -> int:
    """Quantos glifos a régua mediu."""
    return int(sum(v[0] for v in (regua or {}).values()))


def referencia_e_normal(pagina: Regua, livro: Optional[Regua]
                        ) -> Optional[Tuple[Dict[str, float], float]]:
    """`(referência, peso normal)` pela régua do livro com a da página, ou None se o livro
    ainda não mediu o bastante (`MINIMO_DO_LIVRO`): a página decide sozinha.

    A referência de cada caractere é o quantil 25 do livro e da página juntos. O peso normal
    é o das palavras redondas: a razão mediana ÷ quantil 25 dos caracteres, na mediana pesada
    pela contagem (os caracteres de prosa, que são a maioria, puxam para o redondo; os
    algarismos, quase todos em lances negritos, pesam pouco)."""
    if tamanho(livro) < MINIMO_DO_LIVRO:
        return None
    juntos = juntar([livro, pagina])
    referencia = {char: v[1] for char, v in juntos.items()}
    razoes, pesos = [], []
    for n, p25, p50 in juntos.values():
        if n >= MINIMO_DO_CARACTERE:
            razoes.append(p50 / p25)
            pesos.append(n)
    normal = _mediana_ponderada(razoes, pesos) if razoes else 1.0
    return referencia, normal
