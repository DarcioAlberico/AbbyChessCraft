"""O idioma da prosa de um livro, pelas palavras mais comuns dele.

O idioma do projeto escolhe o léxico da verificação de texto (F7) e as letras das peças nos
lances. Escolhido errado, a verificação não serve: no *Chess School 1* do Mirkovic, em inglês
num projeto em português, o léxico do português marcou 178 palavras da p. 19, quase todas
certas, e as erradas ("Oppesition", "spuares") se perdiam entre elas; com o do inglês foram
32, todas erros de leitura.

As palavras comuns (artigos, preposições, pronomes) são poucas, curtas e muito frequentes:
umas 15 numa página bastam, e o OCR as lê bem. O idioma é o que tem mais delas, desde que
tenha o dobro do segundo; senão, nenhum (`None`).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, Optional

#: Os idiomas do projeto: o rótulo e o código (o do léxico, `verificacao.carregar_lexico`).
IDIOMAS = (("Português", "pt"), ("English", "en"), ("Español", "es"),
           ("Deutsch", "de"), ("Français", "fr"))
#: O nome de cada idioma numa frase ("o texto parece em inglês").
NOMES = {"pt": "português", "en": "inglês", "es": "espanhol", "de": "alemão",
         "fr": "francês"}

#: As palavras mais comuns de cada idioma, sem as que dois deles dividem ("a", "de", "que",
#: "para", "das", "un", "an", "in", "on", "as", "do", "no"…): só as que dizem o idioma.
COMUNS = {
    "pt": {"o", "os", "um", "uma", "da", "dos", "na", "nos", "nas", "não", "com", "ao", "à",
           "é", "são", "ou", "mas", "mais", "foi", "pelo", "pela", "seu", "sua", "pretas",
           "brancas", "lance", "então", "também"},
    "en": {"the", "of", "and", "to", "is", "that", "with", "for", "it", "this", "which", "be",
           "are", "was", "by", "from", "black", "white", "move", "moves", "his", "after",
           "would", "can", "not", "has", "have", "at", "or"},
    "es": {"el", "los", "las", "del", "y", "con", "es", "una", "lo", "al", "su", "pero", "más",
           "negras", "blancas", "jugada", "también", "porque"},
    "de": {"der", "und", "den", "ist", "mit", "nicht", "ein", "eine", "zu", "auf", "dem",
           "sich", "von", "auch", "wird", "weiß", "schwarz", "zug", "nach", "aber"},
    "fr": {"le", "les", "et", "des", "du", "est", "une", "pour", "pas", "avec", "dans", "par",
           "sur", "au", "aux", "qui", "ce", "noirs", "blancs", "coup", "mais"},
}

#: Quantas palavras comuns o texto precisa ter para o idioma dele valer.
MINIMO = 15
#: Quantas vezes as do primeiro idioma precisam ser as do segundo.
VANTAGEM = 2.0

_PALAVRA = re.compile(r"[^\W\d_]+", re.UNICODE)


def contar(texto: str) -> Counter:
    """Quantas palavras comuns de cada idioma o texto tem."""
    contagem: Counter = Counter()
    for palavra in _PALAVRA.findall(texto.lower()):
        for codigo, comuns in COMUNS.items():
            if palavra in comuns:
                contagem[codigo] += 1
    return contagem


def provavel(textos: Iterable[str] | str) -> Optional[str]:
    """O código do idioma do texto, ou `None` quando ele não diz (pouco texto, ou dois
    idiomas perto um do outro)."""
    texto = textos if isinstance(textos, str) else "\n".join(textos)
    contagem = contar(texto).most_common(2)
    if not contagem or contagem[0][1] < MINIMO:
        return None
    if len(contagem) > 1 and contagem[0][1] < VANTAGEM * contagem[1][1]:
        return None
    return contagem[0][0]


def da_camada_do_pdf(caminho, paginas: int = 8) -> Optional[str]:
    """O idioma pela camada de texto do PDF (a do ClearScan, a nativa), lida em `paginas`
    páginas espalhadas pelo miolo do livro; `None` sem camada ou sem idioma claro."""
    import fitz

    try:
        with fitz.open(str(caminho)) as documento:
            total = documento.page_count
            if total == 0:
                return None
            passo = max(1, total // (paginas + 1))
            indices = sorted({min(total - 1, passo * (k + 1)) for k in range(paginas)})
            return provavel(documento[i].get_text() for i in indices)
    except (RuntimeError, ValueError, OSError):
        return None
