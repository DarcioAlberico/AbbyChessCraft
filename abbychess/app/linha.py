"""A faixa Linha (SPEC §3.1, Ctrl+F5): a linha atual ampliada, a imagem em cima e o texto
embaixo, alinhados por glifo (o Zoom do FineReader).

A escala é a maior em que a linha cabe na faixa (a altura da imagem e a largura da faixa);
cada caractere fica centrado embaixo do glifo dele, e o glifo atual é contornado. Com a
página em 1366×768, a x-height do texto impresso fica em ≥ 12 px na faixa (CA-3.2).
"""

from __future__ import annotations

from typing import List, Optional, Sequence

import numpy as np
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from abbychess.app import cores
from abbychess.app.imagens import pixmap_de_cinza

FONTE = "Segoe UI Symbol"
#: A altura da parte do texto, embaixo da imagem.
ALTURA_DO_TEXTO = 24
MARGEM = 4


class FaixaDaLinha(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName("Linha: a linha atual ampliada, imagem sobre texto")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(80)
        self._recorte: Optional[QPixmap] = None
        self._origem = (0, 0)
        self._boxes: List = []
        self._atual: Optional[int] = None
        self.escala = 0.0
        #: O aviso não modal de uma edição que mudou a estrutura (§6.3), por alguns segundos.
        self.aviso = ""
        self._relogio_do_aviso = QTimer(self)
        self._relogio_do_aviso.setSingleShot(True)
        self._relogio_do_aviso.timeout.connect(lambda: self.avisar(""))

    def avisar(self, texto: str, ms: int = 6000) -> None:
        """"2 glifo(s) tirado(s) · Ctrl+Z desfaz", no canto da faixa; vazio apaga."""
        self.aviso = texto
        self.setToolTip(texto)
        if texto:
            self._relogio_do_aviso.start(ms)
        self.update()

    def mostrar(self, matriz: Optional[np.ndarray], boxes: Sequence, atual: Optional[int]) -> None:
        """Os `boxes` da linha (BoxEntry, na ordem dela) e o índice do atual entre eles."""
        if matriz is None or not boxes:
            self.limpar()
            return
        x1 = max(0, min(b.x1 for b in boxes) - 6)
        y1 = max(0, min(b.y1 for b in boxes) - 4)
        x2 = min(matriz.shape[1], max(b.x2 for b in boxes) + 6)
        y2 = min(matriz.shape[0], max(b.y2 for b in boxes) + 4)
        if x2 <= x1 or y2 <= y1:                # a caixa fora da página: nada a mostrar
            self.limpar()
            return
        self._recorte = pixmap_de_cinza(matriz[y1:y2, x1:x2])
        self._origem = (x1, y1)
        self._boxes = list(boxes)
        self._atual = atual
        self.update()

    def limpar(self) -> None:
        self._recorte, self._boxes, self._atual, self.escala = None, [], None, 0.0
        self.update()

    def paintEvent(self, _evento):
        pintor = QPainter(self)
        pintor.fillRect(self.rect(), QColor(255, 255, 255))
        if self._recorte is None or self._recorte.isNull():
            pintor.setPen(QColor(120, 120, 120))
            pintor.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                            "A linha do glifo atual aparece aqui (Ctrl+F5 esconde).")
            pintor.end()
            return
        altura_util = self.height() - ALTURA_DO_TEXTO - 2 * MARGEM
        largura_util = self.width() - 2 * MARGEM
        self.escala = min(altura_util / max(self._recorte.height(), 1),
                          largura_util / max(self._recorte.width(), 1))
        largura = self._recorte.width() * self.escala
        esquerda = MARGEM + (largura_util - largura) / 2
        alvo = QRectF(esquerda, MARGEM, largura, self._recorte.height() * self.escala)
        pintor.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        pintor.drawPixmap(alvo, self._recorte, QRectF(self._recorte.rect()))
        ox, oy = self._origem
        pintor.setFont(QFont(FONTE, 12))
        base = alvo.bottom() + 2
        for n, b in enumerate(self._boxes):
            gx1 = esquerda + (b.x1 - ox) * self.escala
            gx2 = esquerda + (b.x2 - ox) * self.escala
            if n == self._atual:
                caneta = QPen(cores.SELECIONADO)
                caneta.setWidthF(2)
                pintor.setPen(caneta)
                pintor.drawRect(QRectF(gx1 - 1, MARGEM + (b.y1 - oy) * self.escala - 1,
                                       gx2 - gx1 + 2, (b.y2 - b.y1) * self.escala + 2))
            pintor.setPen(QColor(0, 0, 0) if b.char else QColor(200, 0, 0))
            pintor.drawText(QRectF(gx1 - 8, base, gx2 - gx1 + 16, ALTURA_DO_TEXTO),
                            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                            b.char or "□")
        self._pintar_o_aviso(pintor)
        pintor.end()

    def _pintar_o_aviso(self, pintor) -> None:
        if not self.aviso:
            return
        pintor.setFont(QFont(FONTE, 9))
        largura = pintor.fontMetrics().horizontalAdvance(self.aviso) + 12
        caixa = QRectF(self.width() - largura - MARGEM, MARGEM, largura, 18)
        pintor.fillRect(caixa, QColor(255, 248, 220))
        pintor.setPen(QColor(90, 70, 0))
        pintor.drawText(caixa, Qt.AlignmentFlag.AlignCenter, self.aviso)
