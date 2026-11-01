"""A segunda opinião da camada de texto do PDF na verificação de texto (F7).

O PDF ClearScan (o "Paper Capture" do Acrobat, comum nos livros de xadrez digitalizados) traz
uma camada de texto do OCR da Adobe. Para a importação ela não serve (`nativo` a recusa: as
figurinas viram lixo, `'it'd8` no lugar de `♔d8`), mas a **prosa** dela é boa, e os erros dela
não são os nossos. No *Chess School 1* do Mirkovic, p. 19, ela tem "distance between",
"squares", "maneuver" e "pawn's" onde o OCR leu "distancebetween", "spuares", "rwneuver" e
"pawn,s"; e erra onde ele acerta ("Oposition", "pa;ition", "Qose").

Por isso ela só **opina**, e só com o léxico do livro de juiz:

- na palavra que o léxico já marcou, a da camada no mesmo lugar vira a sugestão do campo, se o
  léxico a conhece ("distancebetween" → "distance between": o espaço digitado parte a palavra);
- a palavra que o léxico aceita mas a camada lê outra, conhecida também ("am" → "and"), entra
  na verificação com o motivo `camada`.

Nada é trocado sozinho, e lance nenhum é comparado (as figurinas da camada são lixo). Só vale
a página do livro inteira (sem quadro nem giro): a camada está nas coordenadas do PDF.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple

from core.box_model import BoxEntry

Caixa = Tuple[float, float, float, float]

#: O motivo das palavras que só a camada pôs na verificação.
MOTIVO = "camada"
#: A pontuação de borda que não conta na comparação.
_BORDA = ".,;:!?\"“”‘’'()[]"
#: Glifos de lance: a palavra do OCR com algum deles não é prosa.
_DE_LANCE = set("♔♕♖♗♘♙♚♛♜♝♞♟0123456789")


@dataclass(frozen=True)
class PalavraDaCamada:
    caixa: Caixa
    texto: str


_VISTAS: "OrderedDict[tuple, List[PalavraDaCamada]]" = OrderedDict()
_TRAVA = threading.Lock()
_GUARDADAS = 8


def palavras(caminho: str | Path, pagina: int, escala: float) -> List[PalavraDaCamada]:
    """As palavras da camada de texto da página do PDF (índice de zero), em pixels da imagem
    renderizada com `escala` (dpi / 72); vazia sem camada."""
    chave = (str(caminho), pagina, escala)
    with _TRAVA:
        if chave in _VISTAS:
            _VISTAS.move_to_end(chave)
            return _VISTAS[chave]
    import fitz

    try:
        with fitz.open(str(caminho)) as documento:
            if not 0 <= pagina < documento.page_count:
                return []
            brutas = documento[pagina].get_text("words")
    except (RuntimeError, ValueError, OSError):
        return []
    saida = [PalavraDaCamada((x0 * escala, y0 * escala, x1 * escala, y1 * escala), texto)
             for x0, y0, x1, y1, texto, *_ in brutas if texto.strip()]
    with _TRAVA:
        _VISTAS[chave] = saida
        while len(_VISTAS) > _GUARDADAS:
            _VISTAS.popitem(last=False)
    return saida


def da_pagina(projeto, fonte, indice: int) -> List[PalavraDaCamada]:
    """As palavras da camada da posição `indice` do livro, ou vazia: sem PDF, na página de
    outro arquivo, ou na página com quadro ou giro."""
    from core.services.pdf_service import DPI_PADRAO

    from abbychess import sequencia as sq

    caminho = Path(projeto.fonte)
    if caminho.suffix.lower() != ".pdf" or fonte is None:
        return []
    try:
        entrada = fonte.entrada(indice)
    except IndexError:
        return []
    if entrada.fonte != sq.FONTE_DO_LIVRO or entrada.quadro is not None or entrada.giro:
        return []
    return palavras(caminho, entrada.pagina, DPI_PADRAO / 72)


def _limpa(texto: str) -> str:
    return texto.strip(_BORDA).replace("’", "'")


def _na_caixa(camada: Sequence[PalavraDaCamada], caixa: Caixa) -> List[PalavraDaCamada]:
    """As palavras da camada com o centro dentro da caixa (com a folga de um terço da altura),
    da esquerda para a direita."""
    x1, y1, x2, y2 = caixa
    folga = (y2 - y1) / 3
    dentro = [p for p in camada
              if x1 - folga <= (p.caixa[0] + p.caixa[2]) / 2 <= x2 + folga
              and y1 - folga <= (p.caixa[1] + p.caixa[3]) / 2 <= y2 + folga]
    return sorted(dentro, key=lambda p: p.caixa[0])


def _conhecida(lex, texto: str) -> bool:
    """Se o léxico conhece a palavra de prosa (`verificacao.conhecida_pelas_partes`)."""
    from abbychess import verificacao as vf

    limpa = _limpa(texto)
    return bool(limpa) and vf.conhecida_pelas_partes(lex, limpa)


def sugestao(camada: Sequence[PalavraDaCamada], caixa: Caixa, lido: str, lex) -> str:
    """A leitura da camada no lugar da palavra `lido` (as palavras dela juntas por espaço),
    quando difere e o léxico conhece cada uma; senão vazia."""
    achadas = _na_caixa(camada, caixa)
    if not achadas or not all(_conhecida(lex, p.texto) for p in achadas):
        return ""
    texto = " ".join(_limpa(p.texto) for p in achadas)
    return texto if texto != _limpa(lido) else ""


def discordancias(camada: Sequence[PalavraDaCamada], boxes: Sequence[BoxEntry], lex,
                  ja_vistos: set) -> List[Tuple[str, List[int], str]]:
    """(lido, índices dos boxes, leitura da camada) das palavras de prosa que o léxico aceita
    mas a camada, com outra palavra que ele também conhece, lê diferente ("am" → "and").
    `ja_vistos`: os índices que a verificação já mostra."""
    saida = []
    lidos, cx, cy = _centros_lidos(boxes)
    for palavra in camada:
        indices = _indices_na_caixa(palavra.caixa, boxes, lidos, cx, cy)
        if (not indices or not _conhecida(lex, palavra.texto)
                or ja_vistos.intersection(indices)):
            continue
        lido = "".join(boxes[i].char for i in indices)
        leitura = _outra_conhecida(lex, lido, palavra.texto)
        if leitura is not None:
            saida.append((lido, indices, leitura))
    return saida


def _centros_lidos(boxes: Sequence[BoxEntry]) -> tuple:
    """Os boxes lidos e os centros de todos, como vetores."""
    import numpy as np

    return (np.array([bool(b.char) for b in boxes]),
            np.array([(b.x1 + b.x2) / 2 for b in boxes], dtype=float),
            np.array([(b.y1 + b.y2) / 2 for b in boxes], dtype=float))


def _indices_na_caixa(caixa, boxes: Sequence[BoxEntry], lidos, cx, cy) -> List[int]:
    """Os índices dos boxes lidos com o centro na caixa da palavra, da esquerda à direita."""
    x1, y1, x2, y2 = caixa
    dentro = (lidos & (cx >= x1) & (cx <= x2) & (cy >= y1) & (cy <= y2)).nonzero()[0]
    return sorted((int(i) for i in dentro), key=lambda i: boxes[i].x1)


def _outra_conhecida(lex, lido: str, texto: str):
    """A leitura da camada (limpa), se o lido é outra palavra que o léxico conhece; None se é
    a mesma, se o lido tem caractere de lance ou se o léxico não o conhece."""
    if any(c in _DE_LANCE for c in lido):
        return None
    limpo = _limpa(lido)
    if limpo and limpo != _limpa(texto) and limpo.lower() != _limpa(texto).lower():
        if _conhecida(lex, limpo):
            return _limpa(texto)
    return None


def opinioes(desconhecidas, boxes: Sequence[BoxEntry], camada: Sequence[PalavraDaCamada], lex):
    """As desconhecidas da verificação com a sugestão da camada, mais as discordâncias dela
    (`MOTIVO`), na ordem de leitura."""
    from abbychess import verificacao as vf

    if not camada:
        return list(desconhecidas)
    saida = []
    vistos = set()
    for d in desconhecidas:
        vistos.update(d.indices)
        lidos = [i for i in d.indices if boxes[i].char]
        sugerida = sugestao(camada, vf.caixa_da_palavra(boxes, lidos or d.indices), d.palavra, lex)
        saida.append(vf.Desconhecida(d.palavra, d.indices, d.motivo, sugerida))
    for lido, indices, da_camada in discordancias(camada, boxes, lex, vistos):
        saida.append(vf.Desconhecida(lido, indices, MOTIVO, da_camada))
    ordem = {i: k for k, i in enumerate(_ordem_de_leitura(boxes))}
    return sorted(saida, key=lambda d: min(ordem.get(i, len(ordem)) for i in d.indices))


def _ordem_de_leitura(boxes: Sequence[BoxEntry]) -> List[int]:
    """Os índices dos boxes na ordem em que a página os lê (a das linhas do Documento)."""
    from abbychess import texto as tx

    pagina = tx.pagina_avulsa(list(boxes))
    posicao = {b.gid: k for k, b in enumerate(pagina.boxes)}
    return [posicao[g] for p in tx.palavras_dos_gids(pagina) for g in p if g in posicao]
