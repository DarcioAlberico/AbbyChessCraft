"""A faixa Linha (`abbychess/app/linha.py`, SPEC §3.1): a linha do glifo atual ampliada, ou
a faixa vazia com a instrução quando não há linha a mostrar."""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.box_model import BoxEntry  # noqa: E402

from abbychess.app.linha import FaixaDaLinha  # noqa: E402


def _pagina():
    """Uma página branca com três glifos pretos numa linha."""
    matriz = np.full((200, 400), 255, np.uint8)
    boxes = []
    for k in range(3):
        x = 40 + 40 * k
        matriz[90:110, x:x + 15] = 0
        boxes.append(BoxEntry("abc"[k], x, 90, x + 15, 110, 0.9, "net"))
    return matriz, boxes


@pytest.fixture
def faixa(app):
    faixa = FaixaDaLinha()
    faixa.resize(600, 80)
    yield faixa
    faixa.deleteLater()


def _imagem(faixa):
    return faixa.grab().toImage()


def _tem_tinta(imagem) -> bool:
    """Algum pixel quase preto: os glifos da linha (a instrução é cinza)."""
    return any(imagem.pixelColor(x, y).value() < 40
               for x in range(0, imagem.width(), 2) for y in range(imagem.height()))


def test_a_linha_aparece_ampliada_e_some_sem_pagina_sem_glifos_ou_fora_da_pagina(faixa):
    matriz, boxes = _pagina()
    vazia = _imagem(faixa)
    assert not _tem_tinta(vazia)                          # a instrução, sem linha

    faixa.mostrar(matriz, boxes, 1)
    mostrada = _imagem(faixa)
    assert _tem_tinta(mostrada) and faixa.escala > 1      # a linha, maior que na página

    faixa.mostrar(None, boxes, 1)                         # sem a imagem da página
    assert _imagem(faixa) == vazia and faixa.escala == 0

    faixa.mostrar(matriz, boxes, 1)
    faixa.mostrar(matriz, [], None)                       # a linha sem glifos
    assert _imagem(faixa) == vazia

    faixa.mostrar(matriz, boxes, 1)
    fora = [BoxEntry("x", 500, 300, 520, 330, 0.9, "net")]   # além da página (400 × 200)
    faixa.mostrar(matriz, fora, 0)
    assert _imagem(faixa) == vazia and faixa.escala == 0
