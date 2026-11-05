"""A geometria de uma página do livro (SPEC §12.4, passo L, rodada 3): o quadro e o giro, e a
conta exata que leva uma caixa de uma geometria a outra.

A imagem de uma entrada da sequência é a página da fonte **endireitada** (o ângulo medido na
página inteira), depois cortada pelo `quadro` e girada pelo `giro` (graus no sentido
horário). Endireitar vem antes: cortar e girar de 90 em 90 graus são operações inteiras
sobre a página endireitada, e uma caixa passa de uma geometria a outra sem arredondar nada.

As caixas são `(x1, y1, x2, y2)` meio abertas (`matriz[y1:y2, x1:x2]`), em pixels. "A fonte"
aqui é a página endireitada inteira, de `tamanho = (largura, altura)`. Tudo é puro.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy as np

Caixa = Tuple[int, int, int, int]
Quadro = Tuple[int, int, int, int]
#: (quadro ou None = a página inteira, giro em graus no sentido horário).
Geometria = Tuple[Optional[Quadro], int]
IDENTIDADE: Geometria = (None, 0)
GIROS = (0, 90, 180, 270)


def cinza(imagem) -> np.ndarray:
    """A imagem PIL ou a matriz, em tons de cinza (matriz `uint8` de duas dimensões)."""
    if hasattr(imagem, "convert"):
        return np.asarray(imagem.convert("L"))
    arr = np.asarray(imagem)
    return arr if arr.ndim == 2 else arr.mean(axis=2).astype(np.uint8)


def normalizar(geometria) -> Geometria:
    """A geometria como tupla comparável (o JSON traz listas; None vale a identidade)."""
    if geometria is None:
        return IDENTIDADE
    quadro, giro = geometria
    return (None if quadro is None else tuple(int(v) for v in quadro), int(giro) % 360)


def _quadro(geometria: Geometria, tamanho: Tuple[int, int]) -> Quadro:
    quadro, _ = geometria
    return quadro if quadro is not None else (0, 0, tamanho[0], tamanho[1])


def tamanho_da_imagem(geometria: Geometria, tamanho: Tuple[int, int]) -> Tuple[int, int]:
    """(largura, altura) da imagem da entrada: o quadro, girado."""
    x0, y0, x1, y1 = _quadro(geometria, tamanho)
    largura, altura = x1 - x0, y1 - y0
    return (altura, largura) if geometria[1] in (90, 270) else (largura, altura)


def girar_caixa(caixa: Caixa, giro: int, largura: int, altura: int) -> Caixa:
    """A caixa numa imagem `largura` × `altura` depois de girá-la `giro` graus no sentido
    horário (o `np.rot90(k=-giro // 90)` dos pixels dela)."""
    x1, y1, x2, y2 = caixa
    giro %= 360
    if giro == 0:
        return caixa
    if giro == 90:
        return (altura - y2, x1, altura - y1, x2)
    if giro == 180:
        return (largura - x2, altura - y2, largura - x1, altura - y1)
    if giro == 270:
        return (y1, largura - x2, y2, largura - x1)
    raise ValueError(f"giro de {giro}°")


def para_a_fonte(caixa: Caixa, geometria: Geometria, tamanho: Tuple[int, int]) -> Caixa:
    """A caixa da imagem da entrada levada à página endireitada inteira."""
    x0, y0, x1, y1 = _quadro(geometria, tamanho)
    giro = geometria[1]
    largura, altura = tamanho_da_imagem(geometria, tamanho)
    a, b, c, d = girar_caixa(caixa, (360 - giro) % 360, largura, altura)
    return (a + x0, b + y0, c + x0, d + y0)


def da_fonte(caixa: Caixa, geometria: Geometria, tamanho: Tuple[int, int]) -> Optional[Caixa]:
    """A caixa da página endireitada inteira levada à imagem da entrada; None se ela não cabe
    inteira no quadro (o glifo cortado fora sai da página, guardado, §12.4)."""
    x0, y0, x1, y1 = _quadro(geometria, tamanho)
    a, b, c, d = caixa
    if a < x0 or b < y0 or c > x1 or d > y1:
        return None
    return girar_caixa((a - x0, b - y0, c - x0, d - y0), geometria[1], x1 - x0, y1 - y0)


def recortar(caixa: Caixa, geometria: Geometria, tamanho: Tuple[int, int]) -> Optional[Caixa]:
    """Como `da_fonte`, mas a caixa que sai em parte do quadro é aparada nele (as áreas da
    página); None se nada dela fica dentro."""
    x0, y0, x1, y1 = _quadro(geometria, tamanho)
    a, b, c, d = caixa
    a, b, c, d = max(a, x0), max(b, y0), min(c, x1), min(d, y1)
    if c <= a or d <= b:
        return None
    return da_fonte((a, b, c, d), geometria, tamanho)


def quadro_da_vista(caixa: Caixa, geometria: Geometria, tamanho: Tuple[int, int]) -> Quadro:
    """O quadro novo (na página endireitada) de um retângulo marcado na imagem que se vê agora:
    cortar de novo uma página já cortada e girada corta dentro do que se vê."""
    return para_a_fonte(caixa, geometria, tamanho)


def borracha_na_fonte(caixa: Caixa, geometria: Geometria, tamanho: Tuple[int, int],
                      angulo: float) -> Tuple[float, ...]:
    """O retângulo marcado na imagem que se vê agora, levado à página da fonte **antes** de
    endireitar (a borracha, CA-12.17): os quatro cantos `(x1, y1, …, x4, y4)`, no sentido
    horário a partir do de cima à esquerda. Endireitar `angulo` graus (anti-horário, em volta
    do centro, como `cv2.getRotationMatrix2D`) é desfeito canto a canto: guardada assim, a
    área segue a mancha se o ângulo da página mudar depois."""
    a, b, c, d = para_a_fonte(caixa, geometria, tamanho)
    cx, cy = tamanho[0] / 2, tamanho[1] / 2
    cosseno, seno = math.cos(math.radians(angulo)), math.sin(math.radians(angulo))
    cantos = []
    for x, y in ((a, b), (c, b), (c, d), (a, d)):
        cantos += [round(cosseno * (x - cx) - seno * (y - cy) + cx, 2),
                   round(seno * (x - cx) + cosseno * (y - cy) + cy, 2)]
    return tuple(cantos)
