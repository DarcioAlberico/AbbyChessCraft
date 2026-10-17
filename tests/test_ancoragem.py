"""Onde os glifos virtuais da sessão ficam (`abbychess.ancoragem`): um caso por ramo de
`palavra_nova` e de `vizinhos_de_fora`."""

from __future__ import annotations

import pytest

from abbychess import ancoragem as ag
from tests.test_sessao import _pagina

V1, V2, V3 = 101, 102, 103                                # os virtuais dos casos
VIRTUAIS = {V1, V2, V3}


@pytest.mark.parametrize("palavras, n, de_fora, esperado", [
    # a palavra anterior da mesma linha
    ([(0, [1, 2]), (0, [V1])], 1, (None, None), (2, None, True)),
    # sem ela, o primeiro box de uma seguinte da mesma linha (pulando outra só de virtuais)
    ([(0, [V1]), (0, [V2]), (0, [V3, 5])], 0, (None, None), (None, 5, True)),
    # sem as duas, a palavra de fora da sessão antes dela na linha
    ([(0, [V1])], 0, (7, 8), (7, None, True)),
    # ou a de fora depois dela
    ([(0, [V1])], 0, (None, 8), (None, 8, True)),
    # sem nada na linha, a palavra anterior em outra linha
    ([(0, [1, 2]), (1, [V1])], 1, (None, None), (2, None, True)),
    # e, no começo, o primeiro box de uma palavra seguinte em outra linha
    ([(0, [V1]), (1, [V2, 6])], 0, (None, None), (None, 6, True)),
])
def test_palavra_nova(palavras, n, de_fora, esperado):
    assert ag.palavra_nova(palavras, n, palavras[n][0], VIRTUAIS, lambda _linha: de_fora) == esperado


def _gids(p):
    return [b.gid for b in p.boxes]


@pytest.mark.parametrize("linhas, sessao, dependentes, esperado", [
    # a palavra de fora antes e a depois, na mesma linha
    (("aa bb cc",), [2, 3], None, (1, 4)),
    # a sessão no começo da linha: só a de depois
    (("aa bb",), [0, 1], None, (None, 2)),
    # a sessão é a linha toda: os vizinhos nas outras linhas
    (("aa", "bb", "cc"), [2, 3], None, (1, 4)),
    # um glifo de fora que depende da sessão não serve: o anterior a ele
    (("aa bb cc",), [2, 3], {1}, (0, 4)),
])
def test_vizinhos_de_fora(linhas, sessao, dependentes, esperado):
    p = _pagina(*linhas)
    g = _gids(p)
    na_sessao = {g[k] for k in sessao}
    linha_original = {gid: 0 for gid in na_sessao}
    recusados = {g[k] for k in dependentes or ()}
    antes, depois = ag.vizinhos_de_fora(p, linha_original, 0, na_sessao,
                                        lambda gid: gid not in recusados)
    assert (antes, depois) == tuple(None if k is None else g[k] for k in esperado)
