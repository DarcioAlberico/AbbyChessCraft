"""Conversões de imagem para o Qt: página PIL e recorte numpy em QPixmap."""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap


def pixmap_de_cinza(matriz: np.ndarray) -> QPixmap:
    """Um QPixmap de uma matriz uint8 em tons de cinza."""
    matriz = np.ascontiguousarray(matriz, dtype=np.uint8)
    if matriz.ndim == 3:
        matriz = np.ascontiguousarray(matriz.mean(axis=2).astype(np.uint8))
    altura, largura = matriz.shape
    imagem = QImage(matriz.data, largura, altura, largura, QImage.Format.Format_Grayscale8)
    return QPixmap.fromImage(imagem.copy())  # copy: o QImage não pode apontar para a matriz


def pixmap_da_pagina(imagem: Image.Image) -> QPixmap:
    return pixmap_de_cinza(np.asarray(imagem.convert("L")))


class PaginaPreparada(NamedTuple):
    """A `QImage` sem cópia e a matriz para onde ela aponta: só juntas. Guardar a `QImage`
    sem a matriz deixa um ponteiro solto quando a página sai do cache."""

    qimage: QImage
    matriz: np.ndarray


def qimage_da_pagina(matriz: np.ndarray) -> PaginaPreparada:
    """A `QImage` da matriz da página, sem cópia: feita na thread da pré-carga (a `QImage`,
    ao contrário do `QPixmap`, pode nascer fora da interface). O `QPixmap.fromImage` da
    interface copia."""
    matriz = np.ascontiguousarray(matriz, dtype=np.uint8)
    altura, largura = matriz.shape
    return PaginaPreparada(
        QImage(matriz.data, largura, altura, largura, QImage.Format.Format_Grayscale8), matriz)


def ampliado(pixmap: QPixmap, altura: int) -> QPixmap:
    """O recorte ampliado sem suavizar, para o glifo aparecer como foi impresso."""
    if pixmap.isNull() or pixmap.height() == 0:
        return pixmap
    return pixmap.scaledToHeight(altura, Qt.TransformationMode.FastTransformation)
