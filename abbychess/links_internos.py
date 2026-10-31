"""Os links internos do livro exportado (SPEC §12.1, passo J): as referências do texto a uma
página impressa ("página 23"), a um diagrama numerado ("Diagrama 6") e a um capítulo
("capítulo 3"), que viram link quando o alvo está no livro.

O EPUB (`abbychess.epub`) e o DOCX (`abbychess.escritor_docx`) usam os mesmos:
`numerados` diz o que o livro numera, e `referencias_internas`, o que do texto vira link.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from core.pagina import Figura, PaginaExtraida, Paragrafo


#: As referências a uma página impressa, por idioma: "página 23", "on page 23", "p. 23".
#: O número é o grupo 1. Só viram link quando a página existe no livro exportado.
REFERENCIAS = {
    "pt": re.compile(r"\b(?:p[áa]gina|p[áa]g\.|p\.)\s*(\d{1,4})\b", re.IGNORECASE),
    "en": re.compile(r"\b(?:page|p\.)\s*(\d{1,4})\b", re.IGNORECASE),
    "es": re.compile(r"\b(?:p[áa]gina|p[áa]g\.|p\.)\s*(\d{1,4})\b", re.IGNORECASE),
    "de": re.compile(r"\b(?:Seite|S\.)\s*(\d{1,4})\b"),
    "fr": re.compile(r"\b(?:page|p\.)\s*(\d{1,4})\b", re.IGNORECASE),
}


def referencias(texto: str, idioma: str, alvos: Dict[int, str]) -> List[Tuple[int, int, str]]:
    """`(início, fim, href)` das referências do texto a páginas impressas que estão em
    `alvos` (número impresso -> href da âncora); as outras ficam como texto."""
    padrao = REFERENCIAS.get((idioma or "pt").split("-")[0].lower(), REFERENCIAS["en"])
    saida = []
    for achado in padrao.finditer(texto):
        if _citacao(texto, achado.start()):
            continue
        href = alvos.get(int(achado.group(1)))
        if href:
            saida.append((achado.start(), achado.end(), href))
    return saida


def _citacao(texto: str, inicio: int) -> bool:
    """A referência é a página de outra obra: "(Informator 45, p. 12)", "Fine, p. 3" —
    vem depois de uma vírgula, dentro de parênteses ainda abertos, ou logo depois de um
    nome com vírgula."""
    antes = texto[:inicio].rstrip()
    if not antes.endswith(","):
        return False
    return antes.count("(") > antes.count(")") or bool(re.search(r"[A-ZÀ-Ý][\w.'-]*,$", antes))


#: "Diagrama 6", "Diagram 6", "Diagramm 6", "diagramme 6", "diag. 6": a referência a um
#: diagrama numerado, em qualquer idioma (grupo 1). No começo de um parágrafo vizinho do
#: diagrama, é a legenda que o numera (`LEGENDA`).
#: "Diagrama 6.1" e "Diagrama 6,2" são outra numeração (por capítulo): não são o 6.
DIAGRAMA = re.compile(r"\b(?:diagram(?:a|me|m)?|diag\.)\s*(\d{1,4})\b(?![.,]\d)", re.IGNORECASE)
LEGENDA = re.compile(r"\s*(?:diagram(?:a|me|m)?|diag\.)\s*(\d{1,4})\b(?![.,]\d)", re.IGNORECASE)
#: "Capítulo 3", "Chapter III", "Kapitel 3", "chapitre 3": a referência a um capítulo
#: (grupo 1, arábico ou romano). No começo de um título de capítulo, é o número dele. O
#: romano só em maiúsculas ("in chapter i" não é o capítulo 1). O "I" pronome depois de
#: "chapter" ("the chapter I wrote") continua ambíguo: só vira link se houver capítulo I.
CAPITULO = re.compile(r"\b(?i:cap[íi]tulo|chapter|kapitel|chapitre)\s+(\d{1,3}|[IVXLC]{1,7})\b")
_ROMANOS = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def _numero_do_capitulo(texto: str) -> Optional[int]:
    """`3`, `III` -> 3; `None` para o romano malformado ("IIII", "VX")."""
    if texto.isdigit():
        return int(texto)
    letras = texto.upper()
    total = 0
    for i, letra in enumerate(letras):
        valor = _ROMANOS[letra]
        seguinte = _ROMANOS[letras[i + 1]] if i + 1 < len(letras) else 0
        total += -valor if valor < seguinte else valor
    canonico = ""
    resto = total
    for valor, simbolo in ((100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
                           (5, "V"), (4, "IV"), (1, "I")):
        while resto >= valor:
            canonico, resto = canonico + simbolo, resto - valor
    return total if total and canonico == letras else None


@dataclass
class Numerados:
    """O que o livro numera e o texto pode citar: `figuras` (id da `Figura` -> o número que a
    legenda dela imprime), `legendas` (id dos parágrafos que são essas legendas, onde a
    referência não vira link para si mesma) e `capitulos` (id do título -> o número dele).

    Número que se repete no livro (a numeração que recomeça a cada capítulo) não é alvo: o
    link iria para o diagrama errado."""
    figuras: Dict[int, int] = field(default_factory=dict)
    legendas: set = field(default_factory=set)
    capitulos: Dict[int, int] = field(default_factory=dict)


def numerados(paginas: Sequence[PaginaExtraida]) -> Numerados:
    """Os diagramas e os capítulos que o livro numera (`Numerados`).

    A legenda do diagrama é o parágrafo logo depois dele, ou logo antes: vale o lado que o
    livro mais usa, contado em todos os diagramas, porque o parágrafo de depois de um
    diagrama pode ser a legenda impressa acima do seguinte."""
    lados: Dict[str, Dict[int, Tuple[int, int]]] = {"depois": {}, "antes": {}}
    titulos: Dict[int, int] = {}
    for pagina in paginas:
        for k, bloco in enumerate(pagina.blocos):
            numero = _numero_do_titulo(bloco)
            if numero is not None:
                titulos[id(bloco)] = numero
            if isinstance(bloco, Figura):
                _legendas_vizinhas(pagina.blocos, k, lados)
    escolhido = _o_lado_mais_usado(lados)
    return Numerados(figuras=_unicos({f: n for f, (n, _) in escolhido.items()}),
                     legendas={p for _, p in escolhido.values()},
                     capitulos=_unicos(titulos))


def _numero_do_titulo(bloco) -> Optional[int]:
    """O número do título de capítulo (`<h1>`) que começa por "Capítulo 3", "Chapter III"."""
    if not (isinstance(bloco, Paragrafo) and bloco.titulo and bloco.nivel == 1):
        return None
    achado = CAPITULO.match(bloco.texto.strip())
    return _numero_do_capitulo(achado.group(1)) if achado else None


def _legendas_vizinhas(blocos: Sequence, k: int, lados: Dict[str, Dict[int, Tuple[int, int]]]
                       ) -> None:
    """A legenda que numera a figura `blocos[k]` no parágrafo logo depois e no logo antes:
    (número, id do parágrafo) em cada lado."""
    for lado, j in (("depois", k + 1), ("antes", k - 1)):
        if 0 <= j < len(blocos) and isinstance(blocos[j], Paragrafo):
            achado = LEGENDA.match(blocos[j].texto)
            if achado:
                lados[lado][id(blocos[k])] = (int(achado.group(1)), id(blocos[j]))


def _o_lado_mais_usado(lados: Dict[str, Dict[int, Tuple[int, int]]]) -> Dict[int, Tuple[int, int]]:
    return lados["depois"] if len(lados["depois"]) >= len(lados["antes"]) else lados["antes"]


def _unicos(numeros: Dict[int, int]) -> Dict[int, int]:
    """Só os de número que não se repete no livro."""
    from collections import Counter

    vezes = Counter(numeros.values())
    return {k: n for k, n in numeros.items() if vezes[n] == 1}


def referencias_internas(texto: str, idioma: str, paginas: Dict[int, str],
                         diagramas: Dict[int, str], capitulos: Dict[int, str]
                         ) -> List[Tuple[int, int, str]]:
    """As referências do texto que viram link: às páginas impressas (`referencias`), aos
    diagramas ("ver o Diagrama 6") e aos capítulos ("no capítulo 3") que estão nos alvos
    (número -> href). Sem sobrepor: "Diagrama 6, p. 23" são dois links."""
    achados = list(referencias(texto, idioma, paginas))
    for padrao, alvos, numero in ((DIAGRAMA, diagramas, int), (CAPITULO, capitulos,
                                                               _numero_do_capitulo)):
        if not alvos:
            continue
        for achado in padrao.finditer(texto):
            href = alvos.get(numero(achado.group(1)))
            if href:
                achados.append((achado.start(), achado.end(), href))
    saida: List[Tuple[int, int, str]] = []
    for inicio, fim, href in sorted(achados):
        if not saida or inicio >= saida[-1][1]:
            saida.append((inicio, fim, href))
    return saida
