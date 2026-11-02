"""A borracha (SPEC §12.4, CA-12.17): pintar de branco, na página da fonte, as áreas apagadas
pelo usuário (as manchas do scanner). Cada área são os quatro cantos `(x1, y1, …, x4, y4)` de
um quadrilátero convexo em pixels da imagem (`geometria.borracha_na_fonte` os dá); quem as
guarda é a entrada da sequência, e quem as pinta, `pagina.FonteDePaginas`. Tudo é puro.
"""

from __future__ import annotations

import math
from typing import Tuple

import numpy as np
from PIL import Image


def com_borrachas(imagem: Image.Image, borrachas) -> Image.Image:
    """A imagem com as áreas das `borrachas` pintadas de branco. Sem borracha, a mesma
    imagem; com, uma cópia. Sai o pixel com o centro dentro da área: o retângulo `[x1, x2)`
    sem giro apaga exatamente `matriz[y1:y2, x1:x2]` (o polígono do PIL arredonda os cantos e
    pega a borda)."""
    if not borrachas:
        return imagem
    if imagem.mode not in ("1", "L", "RGB", "RGBA"):
        imagem = imagem.convert("RGB")
    matriz = np.array(imagem)
    for cantos in borrachas:
        caixa, dentro = _dentro_da_borracha(cantos, imagem.size)
        if caixa is not None:
            x0, y0, x1, y1 = caixa
            matriz[y0:y1, x0:x1][dentro] = 255
    return Image.fromarray(matriz)


def _dentro_da_borracha(cantos, tamanho: Tuple[int, int]):
    """(a caixa dos pixels que a área toca, na imagem, e a máscara deles com o centro dentro
    do quadrilátero convexo), ou (None, None) se ela fica fora da imagem."""
    xs, ys = cantos[::2], cantos[1::2]
    x0, y0 = max(0, math.floor(min(xs))), max(0, math.floor(min(ys)))
    x1, y1 = min(tamanho[0], math.ceil(max(xs))), min(tamanho[1], math.ceil(max(ys)))
    if x1 <= x0 or y1 <= y0:
        return None, None
    cx = np.arange(x0, x1) + 0.5
    cy = (np.arange(y0, y1) + 0.5)[:, None]
    lados = []
    for k in range(4):                  # de que lado de cada aresta o centro está
        ax, ay, bx, by = xs[k], ys[k], xs[(k + 1) % 4], ys[(k + 1) % 4]
        lados.append((bx - ax) * (cy - ay) - (by - ay) * (cx - ax))
    return (x0, y0, x1, y1), (np.all([lado >= 0 for lado in lados], axis=0)
                              | np.all([lado <= 0 for lado in lados], axis=0))
