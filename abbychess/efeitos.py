"""O negrito e o itálico dos glifos da página (§9.3): a espessura do traço, a régua do
negrito por palavra, a inclinação do itálico pela projeção, e o filtro do efeito na leitura.

Sem interface, como a `pagina`, de onde vêm a página em tons de cinza (`cinza`), o recorte
em pé (`recorte`) e a leitura no box (`por_leitura`).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import isnan
from typing import List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from core import proporcao, vertical
from core.box_model import BoxEntry

from abbychess import procedencia
from abbychess.leitor import LeitorDoLivro
from abbychess.pagina import cinza, por_leitura, recorte


def espessura_do_traco(recorte: np.ndarray) -> Optional[float]:
    """A meia largura do traço do glifo em alturas da tinta, como `core.negrito.espessura`,
    mas pela massa da tinta em tons de cinza: `massa ÷ perímetro`, e não pela transformada de
    distância da tinta binarizada. ``None`` se o recorte não tem o que medir.

    **O traço do corpo de texto tem uns 2 px a 300 dpi**, e a medida binária anda de pixel em
    pixel: o mesmo "t" redondo media 1,00 numa ocorrência e 1,18 na outra, conforme a fase do
    traço na grade. A massa em tons de cinza guarda a fração do pixel da borda. Medido no Odds
    & Ends (`ferramentas/medir_efeitos.py`, o negrito pela camada, com o negrito falso do
    ChessBase; as páginas de validação), a régua da página acha 84% das palavras em negrito na
    página limpa (79% com a medida do core) e 64% na escaneada (40%), e os falsos da limpa
    caem de 1,4% para 0,4%; com a régua do livro (`regua_do_negrito`), 99% e 91%.

    O fundo e a tinta são os do próprio recorte (os quantis 90 e 10), e a massa só conta perto
    da tinta: o ruído do papel não engorda o traço."""
    import cv2

    from core import negrito, preprocess

    if recorte.size == 0:
        return None
    tinta = preprocess.binarize(recorte, "otsu")
    ys, _xs = np.nonzero(tinta)
    if len(ys) < negrito.MINIMO_DE_TINTA or len(ys) == tinta.size:
        return None
    tons = recorte.astype(np.float32)
    fundo = _quantil_dos_tons(recorte, 0.90)
    escuro = _quantil_dos_tons(recorte[tinta > 0], 0.10)
    if fundo - escuro < CONTRASTE_MINIMO_DO_TRACO:
        return None
    perto = cv2.dilate(tinta, np.ones((3, 3), np.uint8)) > 0
    massa = float(np.clip((fundo - tons[perto]) / (fundo - escuro), 0.0, 1.0).sum())
    contornos, _ = cv2.findContours(tinta, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    perimetro = sum(cv2.arcLength(c, True) for c in contornos)
    if perimetro <= 0:
        return None
    altura = int(ys.max() - ys.min()) + 1
    # Num traço de largura w e comprimento L, a massa é wL e o perímetro, 2L: massa ÷
    # perímetro é a meia largura, a mesma grandeza da medida do core.
    return massa / perimetro / altura


#: A diferença de tom entre o papel e a tinta abaixo da qual o recorte não tem traço que se
#: meça (um borrão, um pedaço de fundo).
CONTRASTE_MINIMO_DO_TRACO = 30


def _quantil_dos_tons(tons: np.ndarray, q: float) -> float:
    """O quantil `q` de tons de 0 a 255, pelo histograma: o `np.percentile` ordena o recorte
    e custava 250 ms por página (duas vezes por glifo)."""
    acumulado = np.cumsum(np.bincount(np.asarray(tons, np.uint8).ravel(), minlength=256))
    return float(np.searchsorted(acumulado, q * (acumulado[-1] - 1), side="right"))


@dataclass
class Efeitos:
    """O negrito e o itálico de cada glifo de uma página (`medir_efeitos`), e a régua do
    negrito dela (`regua_do_negrito.regua_da_pagina`), que vai ao resumo do livro."""

    negritos: List[Optional[bool]]
    italicos: List[Optional[bool]]
    regua: dict


def medir_efeitos(imagem: Image.Image, boxes: Sequence[BoxEntry],
                  regua_do_livro: Optional[dict] = None) -> Efeitos:
    """O negrito e o itálico de cada glifo, medidos por palavra.

    ``None`` quando a palavra não basta para uma decisão, ``False``/``True`` quando o efeito
    é conhecido. O negrito é a régua do core sobre a espessura em tons de cinza
    (`decidir_negritos`), com a régua das outras páginas do livro quando ela é dada; o
    itálico, a inclinação das bordas das letras (`_italicos`), porque o core não tem régua do
    itálico."""
    from abbychess import regua_do_negrito as rn
    from core.notacao import palavras_da_pagina

    if not boxes:
        return Efeitos([], [], {})
    # A página em tons de cinza uma vez: convertê-la a cada glifo dobrava o tempo do lote.
    pagina = cinza(imagem)
    palavras = [[simbolo.indice for simbolo in palavra.simbolos]
                for linha in palavras_da_pagina(list(boxes)) for palavra in linha]
    medidas = espessuras_da_pagina(pagina, boxes)
    regua = rn.regua_da_pagina([box.char for box in boxes], medidas)
    return Efeitos(decidir_negritos(boxes, palavras, medidas, regua, regua_do_livro),
                   _italicos(pagina, boxes, palavras), regua)


def efeitos_da_pagina(imagem: Image.Image, boxes: Sequence[BoxEntry],
                      regua_do_livro: Optional[dict] = None
                      ) -> Tuple[List[Optional[bool]], List[Optional[bool]]]:
    """`(negritos, itálicos)` de `medir_efeitos`."""
    efeitos = medir_efeitos(imagem, boxes, regua_do_livro)
    return efeitos.negritos, efeitos.italicos


def espessuras_da_pagina(pagina: np.ndarray, boxes: Sequence[BoxEntry]
                         ) -> List[Optional[float]]:
    """A espessura do traço de cada glifo (`espessura_do_traco`) na página em tons de cinza."""
    return [espessura_do_traco(recorte(pagina, box)) for box in boxes]


def decidir_negritos(boxes: Sequence[BoxEntry], palavras: Sequence[List[int]],
                     medidas: Sequence[Optional[float]], regua_da_pagina: dict,
                     regua_do_livro: Optional[dict] = None) -> List[Optional[bool]]:
    """O negrito de cada glifo, decidido por palavra com a régua pública do core: a espessura
    de cada glifo contra a do mesmo caractere no peso redondo, e o peso da palavra contra o
    peso normal. Com a régua do livro (`regua_do_negrito.referencia_e_normal`), as duas vêm do
    livro com a página; sem ela, ou com o livro ainda curto, da página só."""
    from abbychess import regua_do_negrito as rn
    from core import negrito

    do_livro = rn.referencia_e_normal(regua_da_pagina, regua_do_livro)
    if do_livro is not None:
        referencia, normal = do_livro
    else:
        referencia, normal = negrito.referencia(_amostras_do_traco(boxes, medidas)), None
    medidos = [_medidos(boxes, medidas, indices) for indices in palavras]
    pesos = [negrito.relativo(glifos, referencia) if len(glifos) >= 2 else None
             for glifos in medidos]
    return _por_palavra(len(boxes), palavras, _negritos_dos_pesos(pesos, normal))


def _amostras_do_traco(boxes: Sequence[BoxEntry], medidas: Sequence[Optional[float]]) -> dict:
    """As espessuras medidas de cada caractere da página (a referência do peso redondo)."""
    amostras = defaultdict(list)
    for box, medida in zip(boxes, medidas):
        if box.char and medida is not None and not isnan(medida):
            amostras[box.char].append(medida)
    return amostras


def _medidos(boxes: Sequence[BoxEntry], medidas: Sequence[Optional[float]], indices
             ) -> List[Tuple[str, float]]:
    """`(caractere, espessura)` dos glifos da palavra que têm caractere e medida."""
    return [(boxes[i].char, medidas[i]) for i in indices
            if boxes[i].char and medidas[i] is not None and not isnan(medidas[i])]


def _negritos_dos_pesos(pesos: Sequence[Optional[float]], normal) -> List[Optional[bool]]:
    """O negrito de cada palavra pelo peso dela contra o normal (o da página, sem o do livro);
    None na palavra sem peso."""
    from core import negrito

    if normal is None:
        normal = negrito.escala([peso for peso in pesos if peso is not None])
    return [None if peso is None else negrito.e_negrito(peso, normal) for peso in pesos]


def _por_palavra(n: int, palavras: Sequence[List[int]], decididos: Sequence[Optional[bool]]
                 ) -> List[Optional[bool]]:
    """O efeito de cada um dos `n` glifos: o da palavra dele (None fora de palavra decidida)."""
    efeitos: List[Optional[bool]] = [None] * n
    for indices, decidido in zip(palavras, decididos):
        if decidido is None:
            continue
        for i in indices:
            efeitos[i] = decidido
    return efeitos


#: O itálico (`_italicos`): a palavra cujas letras pendem de `INCLINACAO_DO_ITALICO` a
#: `TETO_DO_ITALICO` graus além das retas da página, com a projeção da inclinação
#: `GANHO_DO_ITALICO` vezes mais afiada que a de pé, medida em `MINIMO_DE_LETRAS_DO_ITALICO`
#: letras ou mais. Ajustados no Odds & Ends (o itálico pela fonte do PDF, a página limpa e
#: degradada como escaneada, `ferramentas/medir_efeitos.py`): nas páginas que não entraram
#: no ajuste, 0 falsos em ~11.500 palavras retas e 99,8% das itálicas na página limpa, 98,9%
#: na escaneada, 99,1% na escaneada em preto e branco e 99,0% na ruim (a régua de antes, pelo
#: gradiente das bordas: 95,9%, 88,7%, 0% e 37,8%).
INCLINACAO_DO_ITALICO = 7.0
#: O itálico dos livros pende 10–20° (no Odds & Ends, o p99 das itálicas é 20°); as palavras
#: que passam de 22° são as de diagonais (v, w, y, A), que a projeção afia na diagonal.
TETO_DO_ITALICO = 22.0
GANHO_DO_ITALICO = 1.03
MINIMO_DE_LETRAS_DO_ITALICO = 3
#: Os ângulos que a projeção experimenta, em graus (positivo com o topo à direita).
ANGULOS_DO_ITALICO = np.arange(-20.0, 31.0, 1.0)
#: A inclinação até a qual a palavra conta como reta na referência da página (a página quase
#: toda em itálico não puxa a referência para o itálico).
RETA_ATE = 5.0


def _inclinacao_por_projecao(recorte: np.ndarray, mascara: np.ndarray
                             ) -> Optional[Tuple[float, float]]:
    """`(graus, ganho)`: o cisalhamento que deixa as letras mais de pé (positivo com o topo à
    direita) e quanto ele afia a projeção da tinta contra a de pé. ``None`` com tinta de
    menos.

    A tinta da palavra é cisalhada por cada ângulo de `ANGULOS_DO_ITALICO` e projetada nas
    colunas; as hastes e os lados das letras redondas se empilham na mesma coluna quando o
    cisalhamento desfaz a inclinação, e a soma dos quadrados da projeção chega ao pico. **Não
    depende da direção do gradiente**, que a régua de antes media: na página escaneada em
    preto e branco a borda inclinada vira uma escada de degraus verticais, e o itálico sumia
    (0% no Odds & Ends em 1 bit)."""
    from core import preprocess

    tinta = (preprocess.binarize(recorte.astype(np.uint8), "otsu") > 0) & mascara
    ys, xs = np.nonzero(tinta)
    if len(ys) < 30:
        return None
    ys = ys - ys.mean()
    deslocados = np.rint(xs[None, :] + ys[None, :] * np.tan(np.radians(ANGULOS_DO_ITALICO))[:, None]
                         ).astype(np.int64)
    deslocados -= deslocados.min(axis=1, keepdims=True)
    largura = int(deslocados.max()) + 1
    # Uma bincount só para todos os ângulos: cada ângulo na sua faixa de colunas.
    faixas = deslocados + (np.arange(len(ANGULOS_DO_ITALICO)) * largura)[:, None]
    projecoes = np.bincount(faixas.ravel(), minlength=largura * len(ANGULOS_DO_ITALICO))
    pontos = (projecoes.reshape(len(ANGULOS_DO_ITALICO), largura).astype(np.float64) ** 2).sum(1)
    k = int(np.argmax(pontos))
    desvio = 0.0
    if 0 < k < len(pontos) - 1:                 # o pico entre os ângulos, pela parábola
        a, b, c = pontos[k - 1], pontos[k], pontos[k + 1]
        if a - 2 * b + c != 0:
            desvio = float((a - c) / (2 * (a - 2 * b + c)))
    de_pe = pontos[int(np.argmin(np.abs(ANGULOS_DO_ITALICO)))]
    return float(ANGULOS_DO_ITALICO[k] + desvio), float(pontos[k] / max(de_pe, 1e-9))


def _italicos(pagina: np.ndarray, boxes: Sequence[BoxEntry], palavras: Sequence[List[int]]
              ) -> List[Optional[bool]]:
    """O itálico de cada glifo, pela inclinação das letras da palavra
    (`_inclinacao_por_projecao`) contra a das palavras retas da página (a página escaneada
    torta não vira itálico). Só as letras de pé contam: algarismos, figurinas e a barra do ½
    têm diagonais que não são itálico. A palavra inteira leva o resultado; sem letras que
    bastem, `None`."""
    altura, largura = pagina.shape[:2]
    medidas = [_inclinacao_da_palavra(pagina, altura, largura, _letras_de_pe(boxes, indices))
               for indices in palavras]
    normal = _inclinacao_das_retas(medidas)
    return _por_palavra(len(boxes), palavras, [_inclinada(m, normal) for m in medidas])


def _letras_de_pe(boxes: Sequence[BoxEntry], indices: List[int]) -> List[BoxEntry]:
    """As letras da palavra que contam para o itálico: sem algarismos, figurinas e a barra do
    ½ (as diagonais deles não são itálico), nem os glifos girados ou em negativo."""
    return [boxes[i] for i in indices
            if boxes[i].char.isalpha() and not boxes[i].angulo
            and not getattr(boxes[i], "negativo", False)]


def _inclinacao_da_palavra(pagina: np.ndarray, altura: int, largura: int,
                           letras: List[BoxEntry]) -> Optional[Tuple[float, float]]:
    """`(graus, ganho)` das letras da palavra na caixa delas (`_inclinacao_por_projecao`);
    None com letras de menos ou com a caixa estreita demais."""
    if len(letras) < MINIMO_DE_LETRAS_DO_ITALICO:
        return None
    x1, y1, x2, y2 = _caixa_das_letras(letras, altura, largura)
    if x2 - x1 <= 2 or y2 - y1 <= 2:
        return None
    return _inclinacao_por_projecao(pagina[y1:y2, x1:x2],
                                    _mascara_das_letras(letras, x1, y1, x2, y2))


def _caixa_das_letras(letras: List[BoxEntry], altura: int, largura: int
                      ) -> Tuple[int, int, int, int]:
    """A caixa que cobre as letras, dentro da página."""
    x1, y1 = max(0, min(b.x1 for b in letras)), max(0, min(b.y1 for b in letras))
    x2 = min(largura, max(b.x2 for b in letras))
    y2 = min(altura, max(b.y2 for b in letras))
    return x1, y1, x2, y2


def _mascara_das_letras(letras: List[BoxEntry], x1: int, y1: int, x2: int, y2: int
                        ) -> np.ndarray:
    """Os pixels da caixa que estão dentro de alguma letra (a tinta de fora não conta)."""
    mascara = np.zeros((y2 - y1, x2 - x1), bool)
    for b in letras:
        mascara[max(0, b.y1 - y1):max(0, b.y2 - y1),
                max(0, b.x1 - x1):max(0, b.x2 - x1)] = True
    return mascara


def _inclinacao_das_retas(medidas: Sequence[Optional[Tuple[float, float]]]) -> float:
    """A inclinação das palavras retas da página (a referência: a página escaneada torta não
    vira itálico); 0 sem nenhuma."""
    from statistics import median

    retas = [m[0] for m in medidas if m is not None and abs(m[0]) <= RETA_ATE]
    return median(retas) if retas else 0.0


def _inclinada(medida: Optional[Tuple[float, float]], normal: float) -> Optional[bool]:
    """A palavra é itálica: pende de `INCLINACAO_DO_ITALICO` a `TETO_DO_ITALICO` graus além
    da referência, com a projeção `GANHO_DO_ITALICO` vezes mais afiada; None sem medida."""
    if medida is None:
        return None
    return (INCLINACAO_DO_ITALICO <= medida[0] - normal <= TETO_DO_ITALICO
            and medida[1] >= GANHO_DO_ITALICO)


def reler_pelo_efeito(imagem: Image.Image, boxes: Sequence[BoxEntry], leitor: LeitorDoLivro,
                      negritos: Sequence[Optional[bool]], italicos: Sequence[Optional[bool]]
                      ) -> int:
    """O filtro do efeito (§9.3, CA-9.3) na leitura do lote e do F5: a página é lida antes de
    o efeito ser medido (a medida precisa das palavras lidas), e um glifo lido por uma
    amostra de efeito incompatível com o medido (uma legenda em negrito vizinha do corpo
    reto) é lido de novo com o efeito. Devolve quantos foram relidos."""
    alvos = _lidos_com_outro_efeito(boxes, leitor.padroes, negritos, italicos)
    if not alvos:
        return 0
    pagina = np.asarray(imagem.convert("L"))
    referencia = proporcao.altura_de_referencia(list(boxes))
    for i, efeito in alvos:
        box = boxes[i]
        por_leitura(box, leitor.ler(vertical.recorte_de_pe(pagina, box),
                                    altura_de_referencia=referencia, efeito=efeito))
    return len(alvos)


def _lidos_com_outro_efeito(boxes: Sequence[BoxEntry], padroes,
                            negritos: Sequence[Optional[bool]],
                            italicos: Sequence[Optional[bool]]) -> list:
    """`(índice, (negrito, itálico))` de cada glifo com o efeito medido que foi lido por uma
    amostra do livro de efeito incompatível com ele."""
    from abbychess.padroes import efeitos_compativeis

    alvos = []
    for i, box in enumerate(boxes):
        negrito = negritos[i] if i < len(negritos) else None
        italico = italicos[i] if i < len(italicos) else None
        if negrito is None and italico is None:
            continue
        amostra = procedencia.amostra_de(box)
        if not amostra or amostra == procedencia.NENHUMA:
            continue
        if not efeitos_compativeis(padroes.efeito_de(amostra), (negrito, italico)):
            alvos.append((i, (negrito, italico)))
    return alvos
