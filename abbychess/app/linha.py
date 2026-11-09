"""A faixa Linha (SPEC §3.1, Ctrl+F5): a linha atual ampliada, a imagem em cima e o texto
embaixo, alinhados por glifo (o Zoom do FineReader).

A escala é a maior em que a linha cabe na faixa (a altura da imagem e a largura da faixa);
cada caractere fica centrado embaixo do glifo dele, e o glifo atual é contornado. Com a
página em 1366×768, a x-height do texto impresso fica em ≥ 12 px na faixa (CA-3.2).
"""

from __future__ import annotations

from typing import List, Optional, Sequence

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSizePolicy, QWidget

from abbychess.app.imagens import pixmap_de_cinza
from abbychess.app import estilo, teclado

FONTE = "Segoe UI Symbol"
#: A altura da parte do texto, embaixo da imagem.
ALTURA_DO_TEXTO = 24
MARGEM = 4
#: A faixa do aviso, em cima da imagem, quando há aviso.
ALTURA_DO_AVISO = 20
#: O corpo das letras embaixo da imagem, e quantos pixels de largura cada ponto de corpo pede.
CORPO_MAXIMO, CORPO_MINIMO = 12, 7
LARGURA_POR_PONTO = 0.75


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
        self._sublinhados = frozenset()
        self._fortes = frozenset()
        self.escala = 0.0
        #: O aviso não modal de uma edição que mudou a estrutura (§6.3), por alguns segundos.
        self.aviso = ""
        self._relogio_do_aviso = QTimer(self)
        self._relogio_do_aviso.setSingleShot(True)
        self._relogio_do_aviso.timeout.connect(lambda: self.avisar(""))
        #: As ações da janela que o menu de contexto também mostra (o Ctrl+F5 da Linha).
        self.acoes_do_menu: List = []

    @property
    def glifos(self) -> List:
        """Os glifos que a faixa mostra (BoxEntry, na ordem da linha); vazia, nenhum."""
        return list(self._boxes)

    def avisar(self, texto: str, ms: int = 6000) -> None:
        """"2 glifo(s) tirado(s) · Ctrl+Z desfaz", no canto da faixa; vazio apaga."""
        self.aviso = texto
        self.setToolTip(texto)
        if texto:
            self._relogio_do_aviso.start(ms)
        self.update()

    def mostrar(self, matriz: Optional[np.ndarray], boxes: Sequence, atual: Optional[int], *,
                sublinhados=frozenset(), fortes=frozenset()) -> None:
        """Os `boxes` da linha (BoxEntry, na ordem dela) e o índice do atual entre eles; na fila
        Lances, os índices dos tokens de lance (`sublinhados`) e os do ilegal (`fortes`)."""
        self._sublinhados, self._fortes = frozenset(sublinhados), frozenset(fortes)
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

    def texto(self) -> str:
        """As letras da linha como a faixa as mostra (□ no glifo sem leitura)."""
        return "".join(b.char or "□" for b in self._boxes)

    def menu_de_contexto(self) -> QMenu:
        """Copiar o texto da linha e as ações da janela (§3.2)."""
        menu = QMenu(self)
        copiar = menu.addAction("Copiar o texto da linha")
        copiar.setEnabled(bool(self._boxes))
        copiar.triggered.connect(lambda: QApplication.clipboard().setText(self.texto()))
        if self.acoes_do_menu:
            menu.addSeparator()
            menu.addActions(self.acoes_do_menu)
        return menu

    def contextMenuEvent(self, evento):
        self.menu_de_contexto().exec(evento.globalPos())

    def limpar(self) -> None:
        self._recorte, self._boxes, self._atual, self.escala = None, [], None, 0.0
        self.update()

    def corpo_do_texto(self) -> int:
        """O corpo das letras embaixo da imagem: 12, ou menos numa linha longa, para letra não
        cair sobre letra (70 caracteres a 1366 px); nunca menos que `CORPO_MINIMO`."""
        if not self._boxes or not self.escala:
            return CORPO_MAXIMO
        larguras = sorted((b.x2 - b.x1) * self.escala for b in self._boxes)
        mediana = larguras[len(larguras) // 2]
        return max(CORPO_MINIMO, min(CORPO_MAXIMO, int(mediana / LARGURA_POR_PONTO)))

    def paintEvent(self, _evento):
        pintor = QPainter(self)
        pintor.fillRect(self.rect(), estilo.PAPEL)
        if self._recorte is None or self._recorte.isNull():
            pintor.setPen(estilo.TINTA_SECUNDARIA)
            pintor.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                            teclado.com_teclas("A linha do glifo atual aparece aqui "
                                               "({mostrar_linha} esconde)."))
            pintor.end()
            return
        # O aviso tem uma faixa própria em cima: por cima da imagem, ele cobria as letras.
        topo = MARGEM + (ALTURA_DO_AVISO if self.aviso else 0)
        altura_util = self.height() - ALTURA_DO_TEXTO - MARGEM - topo
        largura_util = self.width() - 2 * MARGEM
        self.escala = min(altura_util / max(self._recorte.height(), 1),
                          largura_util / max(self._recorte.width(), 1))
        largura = self._recorte.width() * self.escala
        esquerda = MARGEM + (largura_util - largura) / 2
        alvo = QRectF(esquerda, topo, largura, self._recorte.height() * self.escala)
        pintor.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        pintor.drawPixmap(alvo, self._recorte, QRectF(self._recorte.rect()))
        ox, oy = self._origem
        pintor.setFont(QFont(FONTE, self.corpo_do_texto()))
        base = alvo.bottom() + 2
        for n, b in enumerate(self._boxes):
            gx1 = esquerda + (b.x1 - ox) * self.escala
            gx2 = esquerda + (b.x2 - ox) * self.escala
            if n == self._atual:                # o contorno duplo (CA-U7)
                retangulo = QRectF(gx1 - 1, topo + (b.y1 - oy) * self.escala - 1,
                                   gx2 - gx1 + 2, (b.y2 - b.y1) * self.escala + 2)
                for caneta in estilo.canetas_da_selecao(2):
                    pintor.setPen(caneta)
                    pintor.drawRect(retangulo)
            self._pintar_a_letra(pintor, n, b, gx1, gx2, base)
        self._pintar_o_aviso(pintor)
        pintor.end()

    def _pintar_a_letra(self, pintor, n: int, b, gx1: float, gx2: float, base: float) -> None:
        """A letra embaixo do glifo, com o traço do lance (azul) e o do ilegal (forte)."""
        forte = n in self._fortes
        pintor.setPen(estilo.TINTA if b.char and not forte else estilo.VERMELHAO)
        pintor.drawText(QRectF(gx1 - 8, base, gx2 - gx1 + 16, ALTURA_DO_TEXTO),
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, b.char or "□")
        if n in self._sublinhados or forte:
            caneta = QPen(estilo.VERMELHAO if forte else estilo.AZUL)
            caneta.setWidthF(2.5 if forte else 1)
            pintor.setPen(caneta)
            pintor.drawLine(QPointF(gx1, base + ALTURA_DO_TEXTO - 3),
                            QPointF(gx2, base + ALTURA_DO_TEXTO - 3))

    def _pintar_o_aviso(self, pintor) -> None:
        if not self.aviso:
            return
        pintor.setFont(QFont(FONTE, 9))
        metricas = pintor.fontMetrics()
        texto = metricas.elidedText(self.aviso, Qt.TextElideMode.ElideRight,
                                    self.width() - 2 * MARGEM - 12)
        largura = metricas.horizontalAdvance(texto) + 12
        caixa = QRectF(self.width() - largura - MARGEM, MARGEM / 2, largura, ALTURA_DO_AVISO - 2)
        pintor.fillRect(caixa, estilo.FUNDO_DO_GLIFO_DA_LINHA)
        pintor.setPen(estilo.TINTA_DO_GLIFO_DA_LINHA)
        pintor.drawText(caixa, Qt.AlignmentFlag.AlignCenter, texto)
