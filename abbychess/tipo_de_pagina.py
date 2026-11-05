"""A página que não é texto (L-9, SPEC da página perfeita §4.9). Sem Qt.

A capa do Seirawan inventava 1.442 linhas e 5.429 pendentes, e custava uns 6 minutos. O classificador
olha a tinta antes de segmentar: numa página de texto, ela está em componentes do tamanho de letra;
numa capa, em manchas e em poeira. Medido em 05/11: a capa tem 42 % de tinta e 1,4 % dela em letras;
as 13 páginas com gabarito de texto de três livros têm de 52,7 % a 98,6 % em letras. O corte fica longe
das duas pontas, porque o erro caro é esconder página de texto (CA-L9.2).

**Nunca em silêncio:** o fim do lote lista, a gaveta filtra, o Documento diz, e Ctrl+Shift+T lê como
texto. Nenhum estado novo nem formato novo: a página de imagem é a página com uma área `figura` só.
"""

from __future__ import annotations

import cv2
import numpy as np

from abbychess.geometria import cinza

#: Abaixo desta fração de tinta na página, ela é branca ou quase, e a leitura é barata.
TINTA_MINIMA = 0.15
#: Acima desta fração da tinta em letras, é texto.
LETRAS_NA_TINTA = 0.15
#: Com tantos componentes do tamanho de letra, é texto, seja o que for o resto.
LETRAS_DE_TEXTO = 400


def medidas(imagem) -> dict:
    """A tinta da página, quantos componentes têm tamanho de letra, e a parte da tinta neles."""
    pagina = cinza(imagem)
    altura = pagina.shape[0]
    _limiar, binaria = cv2.threshold(pagina, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    n, _rotulos, comps, _centros = cv2.connectedComponentsWithStats(binaria, 8)
    comps = comps[1:n]
    if not len(comps):
        return {"tinta": 0.0, "letras": 0, "letras_na_tinta": 0.0}
    alturas, larguras, areas = comps[:, cv2.CC_STAT_HEIGHT], comps[:, cv2.CC_STAT_WIDTH], comps[:, cv2.CC_STAT_AREA]
    de_letra = (alturas > altura * 0.004) & (alturas < altura * 0.03) & (larguras < altura * 0.04)
    return {"tinta": float(areas.sum()) / pagina.size, "letras": int(np.count_nonzero(de_letra)),
            "letras_na_tinta": float(areas[de_letra].sum()) / float(areas.sum())}


def e_imagem(imagem) -> bool:
    """A página é imagem, e não texto: muita tinta, e quase nada dela em letras."""
    m = medidas(imagem)
    return (m["tinta"] >= TINTA_MINIMA and m["letras_na_tinta"] < LETRAS_NA_TINTA
            and m["letras"] < LETRAS_DE_TEXTO)


def tratada_como_imagem(pagina) -> bool:
    """A página sem glifos, com uma área só, de figura: a marca do L-9 no modelo."""
    return (not pagina.boxes and len(pagina.zonas) == 1 and pagina.zonas[0].funcao == "figura"
            and pagina.zonas[0].x1 == 0 and pagina.zonas[0].y1 == 0)
