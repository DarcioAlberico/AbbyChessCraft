"""A leitura improvável pela palavra: o glifo lido com confiança que a palavra desmente.

A rede e a base global leem cada glifo sozinho, e num livro escaneado elas trocam com
confiança alta o `o` por `0`, o `l` por `1`, o `s` por `S`: "c0l0ca", "dific11ltar",
"anteS". Com a confiança acima do limiar de revisão, esses glifos não iam para a fila, e a
propagação dos padrões do livro nunca os relia; no replay da fatia eram 48 dos 217 glifos
ensinados (`docs/revisoes/ca-f1-investigacao.md`).

Aqui a palavra decide. Um glifo é improvável quando:

- é um algarismo (ou uma série deles) entre letras, no começo de uma palavra seguido de duas
  letras ou mais, ou no fim depois de duas letras ou mais ("c0l0ca", "1ibera", "muit0");
- é uma maiúscula logo depois de uma minúscula, numa palavra mais minúscula do que
  maiúscula ("anteS", "CavaIo");
- é uma minúscula entre maiúsculas ("VITORlOSO").

Nada disso vale na palavra que é um lance ("Tae1+", "Cxh2", "12.h3+"): ali algarismo e letra
se misturam de propósito. O glifo improvável vai para a revisão mesmo com confiança alta,
inclusive o lido por um padrão do livro (o padrão foi ensinado noutro contexto: um `1` de
"1.e4" lendo o `l` de uma palavra). Só o que o usuário confirmou (manual, revisado) e o texto
nativo do PDF não voltam.
"""

from __future__ import annotations

import re
import threading
from typing import FrozenSet, List, Optional, Sequence, Tuple

#: Um lance em SAN, com as letras das peças em inglês e em português (a figurina vira a letra
#: antes, `core.notacao.FIGURINAS`), o número do lance antes e a pontuação depois: a casa
#: ("Cxh2", "a8=D", "exd6e.p."), a troca entre peças ("NxN", "DxD+") ou o roque. Basta
#: reconhecer a palavra, não validar o lance.
_LANCE = re.compile(r"^[(\[]?(\d+\.+)?([KQRBNDTCP]?[a-h]?[1-8]?[x:]?[a-h][1-8](=?[KQRBNDTC])?"
                    r"(e\.p\.)?|[KQRBNDTCP][x:][KQRBNDTCP]|[O0]-[O0](-[O0])?)"
                    r"[+#‡†]*[!?]*[)\],.;:]*$")


def _e_lance(chars: Sequence[str]) -> bool:
    from core.notacao import FIGURINAS

    return bool(_LANCE.match("".join(FIGURINAS.get(c, c) for c in chars)))


def _tipo(c: str) -> str:
    """'d' algarismo, 'M' maiúscula, 'm' minúscula, 'o' o resto (pontuação, vazio, símbolo)."""
    if c and c.isdigit():
        return "d"
    if c and c.isalpha():
        if c.isupper():
            return "M"
        if c.islower():
            return "m"
    return "o"


def _letras_seguidas(tipos: Sequence[str], inicio: int, passo: int) -> int:
    n, k = 0, inicio
    while 0 <= k < len(tipos) and tipos[k] in "Mm":
        n, k = n + 1, k + passo
    return n


def improvaveis_na_palavra(chars: Sequence[str]) -> List[bool]:
    """Para cada glifo da palavra (o caractere de cada box, em ordem), se ele é improvável."""
    saida = [False] * len(chars)
    if _e_lance(chars):
        return saida
    tipos = [_tipo(c) for c in chars]
    k = 0
    while k < len(tipos):
        if tipos[k] != "d":
            k += 1
            continue
        fim = k
        while fim + 1 < len(tipos) and tipos[fim + 1] == "d":
            fim += 1
        antes = _letras_seguidas(tipos, k - 1, -1)
        depois = _letras_seguidas(tipos, fim + 1, 1)
        if (antes and depois) or (k == 0 and depois >= 2) or (fim == len(tipos) - 1 and antes >= 2):
            saida[k:fim + 1] = [True] * (fim + 1 - k)
        k = fim + 1
    minuscula = tipos.count("m") > tipos.count("M")     # "anteS", e não "VITORlOSO"
    for k in range(1, len(tipos)):
        if minuscula and tipos[k] == "M" and tipos[k - 1] == "m":
            saida[k] = True
        elif (tipos[k] == "m" and tipos[k - 1] == "M" and k + 1 < len(tipos)
              and tipos[k + 1] == "M"):
            saida[k] = True
    return saida


#: A última página julgada: (chave, gids improváveis). A fila da janela pergunta várias vezes
#: por ação (~2–3 ms cada numa página do livro); a chave custa uma fração disso.
_ULTIMA: Tuple[Optional[tuple], FrozenSet[int]] = (None, frozenset())
_TRAVA = threading.Lock()


def _chave(pagina) -> tuple:
    """O que a regra lê: o caractere e a caixa de cada glifo, e as decisões de palavra."""
    return (tuple((b.gid, b.entry.char, b.entry.x1, b.entry.y1, b.entry.x2, b.entry.y2,
                   getattr(b.entry, "angulo", 0)) for b in pagina.boxes), pagina.decisoes)


def improvaveis(pagina) -> FrozenSet[int]:
    """Os gids dos glifos improváveis da página (`modelo.Pagina`), pelas palavras do
    Documento (`texto.palavras_dos_gids`)."""
    global _ULTIMA
    from abbychess import texto as tx

    chave = _chave(pagina)
    with _TRAVA:
        if _ULTIMA[0] == chave:
            return _ULTIMA[1]
    char = {b.gid: b.entry.char for b in pagina.boxes}
    char.update({v.gid: v.char for v in pagina.decisoes.virtuais})
    saida = set()
    for palavra in tx.palavras_dos_gids(pagina):
        for gid, improvavel in zip(palavra, improvaveis_na_palavra([char[g] for g in palavra])):
            if improvavel:
                saida.add(gid)
    with _TRAVA:
        _ULTIMA = (chave, frozenset(saida))
        return _ULTIMA[1]


def volta_pelo_contexto(fonte: str) -> bool:
    """Se um glifo improvável dessa fonte vai para a revisão: tudo menos o confirmado pelo
    usuário e o texto nativo."""
    from abbychess.leitor import FONTE_MANUAL, FONTE_NATIVA

    return fonte not in (FONTE_MANUAL, FONTE_NATIVA)


def improvaveis_da_lista(boxes) -> List[bool]:
    """Para cada `BoxEntry` da lista (a página inteira), se a palavra o desmente e ele volta
    à revisão por isso (`volta_pelo_contexto`)."""
    from abbychess import texto as tx

    pagina = tx.pagina_avulsa(list(boxes))
    contra = improvaveis(pagina)
    return [b.gid in contra and volta_pelo_contexto(b.entry.source) for b in pagina.boxes]


def _pendentes(pagina, limiares, revisados: Sequence[bool]) -> List[bool]:
    from abbychess.leitor import precisa_revisao

    contra = improvaveis(pagina)
    return [not revisado and (precisa_revisao(b.entry.char, b.entry.source, b.entry.confidence,
                                              limiares)
                              or (b.gid in contra and volta_pelo_contexto(b.entry.source)))
            for b, revisado in zip(pagina.boxes, revisados)]


def pendentes(boxes, limiares, revisados: Optional[Sequence[bool]] = None) -> List[bool]:
    """Para cada `BoxEntry` da lista, se ele vai para a revisão: `precisa_revisao` ou
    improvável pela palavra. A lista é a página inteira (as palavras saem dela)."""
    from abbychess import texto as tx

    return _pendentes(tx.pagina_avulsa(list(boxes)), limiares,
                      revisados or [False] * len(boxes))


def pendentes_da_pagina(pagina, limiares, *, com_os_revisados: bool = False) -> List[bool]:
    """`pendentes` para os `Box` da página do modelo, pelos gids dela (as linhas guardadas
    do Documento servem). Com `com_os_revisados`, o revisado também conta, como na leitura
    dos pendentes, que relê pela confiança sem olhar a revisão; sem, ele sai, como na fila."""
    revisados = [False if com_os_revisados else b.revisado for b in pagina.boxes]
    return _pendentes(pagina, limiares, revisados)
