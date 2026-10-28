"""Os links de análise dos diagramas (SPEC §12.1): no EPUB, no DOCX e na prévia, cada
diagrama lido pode levar um link que abre a posição no tabuleiro de análise do Lichess ou
do Chess.com. Quem escolhe é a exportação (`Opcoes.links_de_analise`); o padrão é nenhum, e
aí o arquivo sai como antes, byte a byte.

Só o diagrama com FEN ganha link: o recorte não tem posição. O tabuleiro abre do lado em que
o livro imprimiu o diagrama (`Figura.orientacao`), e o FEN que o core deixou incompleto (só
a disposição, ou sem os campos do fim) é completado com o lado a jogar e o resto neutro,
porque os dois sites recusam o FEN pela metade.
"""

from __future__ import annotations

from typing import Dict, Optional
from urllib.parse import quote

#: As escolhas, na ordem do diálogo; `nenhum` é o padrão.
SITES = ("nenhum", "lichess", "chesscom")
#: O nome de cada uma, como o diálogo e o relatório mostram.
NOMES: Dict[str, str] = {"nenhum": "Nenhum", "lichess": "Lichess", "chesscom": "Chess.com"}
#: O texto do link, por idioma do livro (o começo da etiqueta BCP 47, como `epub.MENSAGENS`).
ROTULOS: Dict[str, str] = {"pt": "Analisar no {site}", "en": "Analyze on {site}",
                           "es": "Analizar en {site}", "de": "Auf {site} analysieren",
                           "fr": "Analyser sur {site}"}
#: Os campos que completam o FEN depois do lado a jogar: roque, en passant e os contadores.
_FIM_DO_FEN = ("-", "-", "0", "1")


def validar(site: str) -> str:
    """O `site` se ele for uma das escolhas; senão, `ValueError`."""
    if site not in SITES:
        raise ValueError(f"Link de análise desconhecido: {site!r}; use {', '.join(SITES)}.")
    return site


def fen_completo(fen: str, lado: Optional[str] = None) -> str:
    """O FEN com os seis campos: o que faltar vem do `lado` a jogar (`w` sem ele) e do fim
    neutro (sem roque, sem en passant, lance 1)."""
    campos = fen.split()
    if len(campos) == 1:
        campos.append(lado if lado in ("w", "b") else "w")
    campos.extend(_FIM_DO_FEN[len(campos) - 2:])
    return " ".join(campos[:6])


def link(fen: Optional[str], site: str, *, orientacao: str = "branca",
         lado: Optional[str] = None) -> Optional[str]:
    """O endereço que abre `fen` no tabuleiro de análise do `site`; `None` sem FEN ou com o
    site `nenhum`. `orientacao` `"preta"` abre o tabuleiro do lado das pretas."""
    validar(site)
    if site == "nenhum" or not fen or not fen.strip():
        return None
    completo = fen_completo(fen.strip(), lado)
    pretas = orientacao == "preta"
    if site == "lichess":
        return ("https://lichess.org/analysis/standard/"
                + quote(completo.replace(" ", "_"), safe="/_-")
                + ("?color=black" if pretas else ""))
    return ("https://www.chess.com/analysis?fen=" + quote(completo, safe="/")
            + ("&flip=true" if pretas else ""))


def link_da_figura(figura, site: str) -> Optional[str]:
    """O link de análise da `core.pagina.Figura` (o FEN, o lado a jogar e a orientação
    dela), ou `None` se ela não tiver posição ou o site for `nenhum`."""
    return link(getattr(figura, "fen", None), site,
                orientacao=getattr(figura, "orientacao", "branca") or "branca",
                lado=getattr(figura, "lado_a_jogar", None))


def rotulo(site: str, idioma: str) -> str:
    """O texto do link no idioma do livro: "Analisar no Lichess", "Analyze on Chess.com"."""
    lingua = (idioma or "pt").split("-")[0].lower()
    return ROTULOS.get(lingua, ROTULOS["en"]).format(site=NOMES[validar(site)])
