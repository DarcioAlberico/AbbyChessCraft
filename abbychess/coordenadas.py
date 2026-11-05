"""As coordenadas impressas em volta dos diagramas (SPEC §10, CA-10.4): achá-las na imagem da
página, para a operação de página as tirar com a borracha (`operacoes_de_pagina`). Sem Qt.

**Coordenada é geometria, não leitura.** Quem imprime `a`–`h` e `1`–`8` põe uma marca por casa,
centrada nela, numa só linha colada ao tabuleiro. A legenda e a prosa da coluna vizinha também
caem na faixa, mas com várias marcas por casa: o lado que não é assim fica como está, e quem
pediu vê que nada mudou (melhor que apagar uma letra do texto).

Sai um retângulo por lado, e não um por marca: são dois por diagrama no `projeto.json`, e não
dezesseis, num livro com centenas deles.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np

from abbychess.geometria import cinza as _cinza
from abbychess.montagem import ALCANCE_DAS_COORDENADAS

Caixa = Tuple[int, int, int, int]

#: Os lados em que um livro imprime coordenadas.
LADOS = ("esquerda", "direita", "acima", "abaixo")

#: Quantas casas precisam da marca delas: a que falta é a que o scanner apagou, e abaixo disto
#: não é coordenada (a mesma régua de `core.diagrama.RAIAS_DE_ROTULO`).
CASAS_COM_MARCA = 7

#: A marca, em casas: a maior dimensão dela. Abaixo do piso é pedaço de letra ou sujeira, que só
#: não conta como marca; acima do teto é moldura, outro tabuleiro ou tarja.
MARCA_MINIMA, MARCA_MAXIMA = 0.15, 0.8

#: Quanto, em casas, o centro da marca pode fugir do centro da casa dela.
FORA_DO_CENTRO = 0.3

#: Quanto, em casas, o centro de uma marca pode fugir da linha das outras (o `g` desce, o `b`
#: sobe).
FORA_DA_LINHA = 0.25

#: Marcas a mais toleradas na linha: a letra que o limiar partiu em duas.
MARCAS_A_MAIS = 2

#: Abaixo desta amplitude de tom a faixa é papel: o Otsu dividiria o ruído do scan ao meio (a
#: guarda de `core.diagrama.AMPLITUDE_DE_TINTA`).
AMPLITUDE_DE_TINTA = 40

#: A folga do retângulo em volta das marcas, em casas (o cinza da borda da letra).
FOLGA = 0.05

#: A faixa onde se procura, em casas: passa do alcance para a letra que começa dentro dele não
#: sair cortada.
FAIXA = ALCANCE_DAS_COORDENADAS + 0.5


class _Faixa:
    """A faixa de um lado do tabuleiro, com as contas de "ao longo do lado" e "para fora dele"
    que valem igual nos quatro lados. Um componente é `(x1, y1, x2, y2)` na página."""

    def __init__(self, tabuleiro: Caixa, lado: str, tamanho: Tuple[int, int]):
        self.tabuleiro, self.lado = tabuleiro, lado
        x1, y1, x2, y2 = tabuleiro
        self.deitada = lado in ("acima", "abaixo")           # as marcas correm na horizontal
        self.inicio, fim = (x1, x2) if self.deitada else (y1, y2)
        self.casa = max(1.0, (fim - self.inicio) / 8)
        alcance = int(round(self.casa * FAIXA))
        largura, altura = tamanho
        self.caixa = {"esquerda": (max(0, x1 - alcance), y1, x1, y2),
                      "direita": (x2, y1, min(largura, x2 + alcance), y2),
                      "acima": (x1, max(0, y1 - alcance), x2, y1),
                      "abaixo": (x1, y2, x2, min(altura, y2 + alcance))}[lado]

    def tamanho(self, c: Caixa) -> float:
        """A maior dimensão do componente, em casas."""
        return max(c[2] - c[0], c[3] - c[1]) / self.casa

    def ao_longo(self, c: Caixa) -> float:
        """O centro do componente ao longo do lado."""
        return (c[0] + c[2]) / 2 if self.deitada else (c[1] + c[3]) / 2

    def para_fora(self, c: Caixa) -> Tuple[int, int]:
        """(começo, fim) do componente na direção para fora do tabuleiro, medidos da borda."""
        x1, y1, x2, y2 = self.tabuleiro
        return {"esquerda": (x1 - c[2], x1 - c[0]), "direita": (c[0] - x2, c[2] - x2),
                "acima": (y1 - c[3], y1 - c[1]), "abaixo": (c[1] - y2, c[3] - y2)}[self.lado]

    def retangulo(self, marcas: Sequence[Caixa]) -> Caixa:
        """O retângulo das marcas com a folga, sem encostar no tabuleiro nem sair da faixa."""
        folga = max(2, int(round(self.casa * FOLGA)))
        x1, y1, x2, y2 = self.caixa
        return (max(x1, min(c[0] for c in marcas) - folga),
                max(y1, min(c[1] for c in marcas) - folga),
                min(x2, max(c[2] for c in marcas) + folga),
                min(y2, max(c[3] for c in marcas) + folga))


def caixas_das_coordenadas(imagem, tabuleiro: Caixa) -> List[Caixa]:
    """Os retângulos das coordenadas impressas em volta do `tabuleiro`, um por lado que as tem
    (nenhum, se ele não as tem). `imagem` é a página, PIL ou matriz."""
    arr = _cinza(imagem)
    altura, largura = arr.shape[:2]
    saida = []
    for lado in LADOS:
        retangulo = _do_lado(arr, _Faixa(tuple(int(v) for v in tabuleiro), lado, (largura, altura)))
        if retangulo is not None:
            saida.append(retangulo)
    return saida


def _do_lado(arr: np.ndarray, faixa: _Faixa) -> Optional[Caixa]:
    """O retângulo das coordenadas neste lado, ou None se o que há nele não é coordenada."""
    componentes = _componentes(arr, faixa.caixa)
    linha = _linha_das_marcas([c for c in componentes
                               if MARCA_MINIMA <= faixa.tamanho(c) <= MARCA_MAXIMA], faixa)
    if linha is None:
        return None
    na_linha = [c for c in componentes if _toca(c, linha, faixa)]
    return faixa.retangulo(na_linha) if _so_marcas(na_linha, faixa) else None


def _so_marcas(na_linha: Sequence[Caixa], faixa: _Faixa) -> bool:
    """Na linha só há as marcas e os pedaços delas: a prosa tem várias por casa, e o que é grande
    demais (a moldura de outra coisa) não sai junto."""
    tamanhos = [faixa.tamanho(c) for c in na_linha]
    return (max(tamanhos) <= MARCA_MAXIMA
            and sum(t >= MARCA_MINIMA for t in tamanhos) <= 8 + MARCAS_A_MAIS)


def _linha_das_marcas(marcas: Sequence[Caixa], faixa: _Faixa) -> Optional[Tuple[int, int]]:
    """(começo, fim), medidos da borda do tabuleiro, da linha das marcas. None sem marcas
    bastantes, ou sem elas alinhadas."""
    medidas = [faixa.para_fora(c) for c in _a_primeira_de_cada_casa(marcas, faixa)]
    if len(medidas) < CASAS_COM_MARCA:
        return None
    meio = float(np.median([(a + b) / 2 for a, b in medidas]))
    alinhadas = [(a, b) for a, b in medidas
                 if abs((a + b) / 2 - meio) <= faixa.casa * FORA_DA_LINHA]
    if len(alinhadas) < CASAS_COM_MARCA:
        return None
    return min(a for a, _ in alinhadas), max(b for _, b in alinhadas)


def _a_primeira_de_cada_casa(marcas: Sequence[Caixa], faixa: _Faixa) -> List[Caixa]:
    """A marca mais perto do tabuleiro em cada casa, entre as centradas nela e que começam ao
    alcance dele."""
    primeira: dict = {}
    for c in marcas:
        posicao = (faixa.ao_longo(c) - faixa.inicio) / faixa.casa
        casa = int(posicao)
        comeco = faixa.para_fora(c)[0]
        if (0 <= casa < 8 and abs(posicao - casa - 0.5) <= FORA_DO_CENTRO
                and comeco <= faixa.casa * ALCANCE_DAS_COORDENADAS
                and (casa not in primeira or comeco < faixa.para_fora(primeira[casa])[0])):
            primeira[casa] = c
    return list(primeira.values())


def _toca(c: Caixa, linha: Tuple[int, int], faixa: _Faixa) -> bool:
    """O componente entra na linha das marcas."""
    comeco, fim = faixa.para_fora(c)
    return comeco < linha[1] and linha[0] < fim


def _componentes(arr: np.ndarray, caixa: Caixa) -> List[Caixa]:
    """Os componentes conexos de tinta na `caixa`, em coordenadas da página."""
    x1, y1, x2, y2 = caixa
    recorte = arr[y1:y2, x1:x2]
    if recorte.size == 0 or int(recorte.max()) - int(recorte.min()) < AMPLITUDE_DE_TINTA:
        return []
    _limiar, binaria = cv2.threshold(recorte, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    quantos, _rotulos, medidas, _centros = cv2.connectedComponentsWithStats(binaria, 8)
    return [(x1 + int(x), y1 + int(y), x1 + int(x + largura), y1 + int(y + a))
            for x, y, largura, a, _area in medidas[1:quantos]]
