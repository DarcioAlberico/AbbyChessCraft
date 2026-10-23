"""A conta da geometria da página (SPEC §12.4, passo L, rodada 3): girar e cortar levam a caixa
aos mesmos pixels, sem arredondar."""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from abbychess import geometria as geo

TAMANHO = (70, 40)


@pytest.fixture
def imagem():
    return np.random.default_rng(7).integers(0, 255, (TAMANHO[1], TAMANHO[0]), dtype=np.uint8)


def _imagem_da(imagem, geometria):
    quadro, giro = geometria
    if quadro is not None:
        x0, y0, x1, y1 = quadro
        imagem = imagem[y0:y1, x0:x1]
    return np.rot90(imagem, k=-giro // 90)


def _recorte(imagem, caixa):
    x1, y1, x2, y2 = caixa
    return imagem[y1:y2, x1:x2]


GEOMETRIAS = [(q, g) for q, g in itertools.product(
    [None, (5, 3, 60, 37), (0, 0, 35, 40)], geo.GIROS)]


@pytest.mark.parametrize("geometria", GEOMETRIAS)
def test_a_caixa_cai_nos_mesmos_pixels(imagem, geometria):
    caixa_na_fonte = (12, 8, 30, 21)
    vista = _imagem_da(imagem, geometria)
    assert vista.shape[::-1] == geo.tamanho_da_imagem(geometria, TAMANHO)
    caixa = geo.da_fonte(caixa_na_fonte, geometria, TAMANHO)
    assert np.array_equal(_recorte(vista, caixa),
                          np.rot90(_recorte(imagem, caixa_na_fonte), k=-geometria[1] // 90))
    assert geo.para_a_fonte(caixa, geometria, TAMANHO) == caixa_na_fonte      # e volta


@pytest.mark.parametrize("de, para", itertools.product(GEOMETRIAS, GEOMETRIAS))
def test_de_uma_geometria_a_outra(imagem, de, para):
    caixa_na_fonte = (12, 8, 30, 21)
    caixa_de = geo.da_fonte(caixa_na_fonte, de, TAMANHO)
    na_fonte = geo.para_a_fonte(caixa_de, de, TAMANHO)
    assert geo.da_fonte(na_fonte, para, TAMANHO) == geo.da_fonte(caixa_na_fonte, para, TAMANHO)


def test_a_caixa_fora_do_quadro_nao_cabe_e_a_area_e_aparada():
    quadro = ((20, 10, 50, 30), 0)
    assert geo.da_fonte((5, 5, 15, 15), quadro, TAMANHO) is None
    assert geo.da_fonte((18, 12, 25, 20), quadro, TAMANHO) is None         # em parte fora
    assert geo.recortar((18, 12, 25, 20), quadro, TAMANHO) == (0, 2, 5, 10)
    assert geo.recortar((0, 0, 5, 5), quadro, TAMANHO) is None


def test_cortar_dentro_do_que_se_ve():
    girada = ((10, 0, 60, 40), 90)                                         # 50 × 40, girada
    assert geo.tamanho_da_imagem(girada, TAMANHO) == (40, 50)
    novo = geo.quadro_da_vista((0, 0, 40, 25), girada, TAMANHO)            # a metade de cima
    assert novo == (10, 0, 35, 40)


def test_normalizar():
    assert geo.normalizar(None) == geo.IDENTIDADE
    assert geo.normalizar([[1, 2, 3, 4], 450]) == ((1, 2, 3, 4), 90)
