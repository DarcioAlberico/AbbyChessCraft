"""A marcação que o EPUB, o DOCX e a prévia escrevem igual (SPEC-qualidade Q-E5): os trechos de
um parágrafo com o mesmo estilo, e a ressalva à vista do diagrama que ninguém conferiu. Cada
escritor só traduz para o formato dele (`<strong>`, `run.bold`)."""

from __future__ import annotations

from typing import List, NamedTuple, Sequence, Tuple


class Marca(NamedTuple):
    negrito: bool
    italico: bool
    #: O caractere está na fonte das figurinas (os `simbolos` do escritor).
    simbolo: bool
    #: O índice do link em `links`, ou -1.
    link: int
    duvidoso: bool


def trechos_marcados(texto: str, simbolos: str, negrito: Sequence[Tuple[int, int]],
                     italico: Sequence[Tuple[int, int]], duvidosos: Sequence[Tuple[int, int]],
                     links: Sequence[Tuple[int, int, str]]) -> List[Tuple[str, Marca]]:
    """Os pedaços seguidos de `texto` com a mesma `Marca`, em ordem. Os trechos são
    `(início, fim)` em `texto` (os de fora dele, cortados); os `links`, `(início, fim, alvo)`."""
    marcas = [[False, False, c in simbolos, -1, False] for c in texto]
    for k, trechos in ((0, negrito), (1, italico), (4, duvidosos)):
        for inicio, fim in trechos or ():
            for i in range(max(0, inicio), min(fim, len(texto))):
                marcas[i][k] = True
    for n, (inicio, fim, _alvo) in enumerate(links):
        for i in range(max(0, inicio), min(fim, len(texto))):
            marcas[i][3] = n
    saida, i = [], 0
    while i < len(texto):
        j = i
        while j < len(texto) and marcas[j] == marcas[i]:
            j += 1
        saida.append((texto[i:j], Marca(*marcas[i])))
        i = j
    return saida


def ressalva_do_diagrama(figura, idioma: str) -> str:
    """A ressalva à vista do diagrama que ninguém conferiu (PD-21): de quem é a vez, quando há
    posição, e "não revisado"; vazia sem revisão pendente. O EPUB e o DOCX a escrevem embaixo
    do diagrama; a prévia, no texto alternativo (`epub.alternativo`)."""
    from abbychess import epub

    if not getattr(figura, "revisao_pendente", False):
        return ""
    partes = [epub.marca_do_lado(figura, idioma)] if figura.fen else []
    return "; ".join(partes + [epub.mensagens(idioma)["nao_revisado"]])
