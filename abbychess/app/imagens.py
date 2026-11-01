"""Conversões de imagem para o Qt: página PIL e recorte numpy em QPixmap; e o desenho da
posição de um diagrama (no Documento e na aba Diagramas)."""

from __future__ import annotations

from typing import NamedTuple, Optional

import numpy as np
from PIL import Image
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QImage, QPainter, QPen, QPixmap

from abbychess.app import estilo

#: A fonte das figurinas (a do Documento, que a importa daqui).
FONTE = "Segoe UI Symbol"
#: A figurina de cada peça no desenho do diagrama.
FIGURINAS = {"K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
             "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟"}
LADO_DA_CASA = 22


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


def imagem_do_diagrama(diagrama, matriz: Optional[np.ndarray]) -> QImage:
    """A posição lida desenhada (casas e figurinas); sem leitura, o recorte da página."""
    if not diagrama.lido:
        if matriz is None:
            imagem = QImage(8 * LADO_DA_CASA, 8 * LADO_DA_CASA, QImage.Format.Format_RGB32)
            imagem.fill(estilo.FUNDO_SEM_IMAGEM)
            return imagem
        x1, y1, x2, y2 = (int(v) for v in diagrama.caixa)
        recorte = pixmap_de_cinza(matriz[max(0, y1):y2, max(0, x1):x2]).toImage()
        return recorte.scaledToHeight(8 * LADO_DA_CASA, Qt.TransformationMode.SmoothTransformation)
    lado = LADO_DA_CASA
    imagem = QImage(8 * lado + 2, 8 * lado + 2, QImage.Format.Format_RGB32)
    imagem.fill(estilo.PAPEL)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.setFont(QFont(FONTE, int(lado * 0.62)))
    for n, casa in enumerate(diagrama.casas[:64]):
        linha, coluna = divmod(n, 8)
        retangulo = QRectF(1 + coluna * lado, 1 + linha * lado, lado, lado)
        if (linha + coluna) % 2:
            pintor.fillRect(retangulo, estilo.CASA_ESCURA_DO_DOCUMENTO)
        if casa.simbolo:
            pintor.setPen(estilo.TINTA)
            pintor.drawText(retangulo, Qt.AlignmentFlag.AlignCenter, FIGURINAS.get(casa.simbolo, "?"))
    pintor.setPen(QPen(estilo.MOLDURA_DO_TABULEIRO))
    pintor.drawRect(QRectF(0.5, 0.5, 8 * lado + 1, 8 * lado + 1))
    pintor.end()
    return imagem
