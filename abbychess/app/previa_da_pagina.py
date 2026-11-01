"""A página em miniatura nos diálogos de cortar e dividir (SPEC §12.4, a dívida do fechamento
do L): o retângulo do corte e a linha da divisão marcados sobre a imagem, com prévia, como no
FineReader.

O que vale continua sendo os números (as margens em porcentagem do que se vê, a divisão em
porcentagem da largura): a miniatura só mostra os campos do diálogo e os muda quando se
arrasta. O teclado segue pelos campos.
"""

from __future__ import annotations

from typing import Optional, Sequence

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPen, QPixmap
from PySide6.QtWidgets import QDoubleSpinBox, QSizePolicy, QWidget

from abbychess.app import estilo

#: O tamanho máximo da miniatura, em pixels de tela: a página dupla, deitada, ganha largura
#: (cabe na largura mínima dos diálogos, `dialogo_paginas.LARGURA_DOS_DIALOGOS`).
LARGURA_DA_PREVIA, ALTURA_DA_PREVIA = 400, 320

#: A distância, em pixels de tela, em que o clique pega uma borda (ou a linha) e não começa
#: um retângulo novo.
TOLERANCIA = 6

#: O que sobra da página, no mínimo, em porcentagem da largura e da altura: o corte que
#: deixaria a página vazia o controlador recusa, e o arraste para antes.
SOBRA_MINIMA = 5.0


class _Previa(QWidget):
    """A miniatura da página (`pixmap`, já do tamanho da tela), com a moldura em volta."""

    def __init__(self, pixmap: QPixmap, legenda: str):
        super().__init__()
        self.pixmap = pixmap.scaled(QSize(LARGURA_DA_PREVIA, ALTURA_DA_PREVIA),
                                    Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
        self.setFixedSize(self.pixmap.size())
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setAccessibleName(legenda)
        self.setToolTip(legenda)

    def _fracao(self, ponto: QPointF) -> QPointF:
        """O ponto em porcentagem da imagem (de 0 a 100), preso dentro dela."""
        return QPointF(min(max(ponto.x() / self.width(), 0.0), 1.0) * 100,
                       min(max(ponto.y() / self.height(), 0.0), 1.0) * 100)

    def paintEvent(self, _evento) -> None:
        pintor = QPainter(self)
        pintor.drawPixmap(0, 0, self.pixmap)
        self.pintar(pintor)
        pintor.end()

    def pintar(self, pintor: QPainter) -> None:
        raise NotImplementedError


class PreviaDoCorte(_Previa):
    """O retângulo do corte sobre a página: arrastar uma borda ou um canto a move; arrastar
    dentro move o retângulo inteiro; arrastar fora dele marca um retângulo novo. `margens`
    são os quatro campos do diálogo (esquerda, cima, direita, baixo), em porcentagem."""

    def __init__(self, pixmap: QPixmap, margens: Sequence[QDoubleSpinBox], legenda: str):
        super().__init__(pixmap, legenda)
        self.margens = list(margens)
        for campo in self.margens:
            campo.valueChanged.connect(self.update)
        #: O arraste em curso: as bordas que ele move ("e", "c", "d", "b"), "mover" ou
        #: "novo", com o ponto e o retângulo de onde ele começou.
        self._arraste: Optional[tuple] = None

    def retangulo(self) -> QRectF:
        """O que fica da página, em pixels da miniatura."""
        esquerda, cima, direita, baixo = (m.value() / 100 for m in self.margens)
        return QRectF(QPointF(esquerda * self.width(), cima * self.height()),
                      QPointF((1 - direita) * self.width(), (1 - baixo) * self.height()))

    def _bordas_em(self, ponto: QPointF) -> str:
        """As bordas do retângulo perto do ponto ("" se nenhuma): "ec" é o canto de cima à
        esquerda."""
        r = self.retangulo()
        dentro_x = r.left() - TOLERANCIA <= ponto.x() <= r.right() + TOLERANCIA
        dentro_y = r.top() - TOLERANCIA <= ponto.y() <= r.bottom() + TOLERANCIA
        bordas = ""
        if dentro_y and abs(ponto.x() - r.left()) <= TOLERANCIA:
            bordas += "e"
        elif dentro_y and abs(ponto.x() - r.right()) <= TOLERANCIA:
            bordas += "d"
        if dentro_x and abs(ponto.y() - r.top()) <= TOLERANCIA:
            bordas += "c"
        elif dentro_x and abs(ponto.y() - r.bottom()) <= TOLERANCIA:
            bordas += "b"
        return bordas

    def _cursor_para(self, ponto: QPointF) -> Qt.CursorShape:
        bordas = self._bordas_em(ponto)
        if bordas in ("ec", "db"):
            return Qt.CursorShape.SizeFDiagCursor
        if bordas in ("dc", "eb"):
            return Qt.CursorShape.SizeBDiagCursor
        if bordas in ("e", "d"):
            return Qt.CursorShape.SizeHorCursor
        if bordas in ("c", "b"):
            return Qt.CursorShape.SizeVerCursor
        if self.retangulo().contains(ponto):
            return Qt.CursorShape.SizeAllCursor
        return Qt.CursorShape.CrossCursor

    def _por(self, esquerda: float, cima: float, direita: float, baixo: float) -> None:
        """Os campos pelas bordas do que fica (em porcentagem da imagem, de 0 a 100)."""
        valores = (esquerda, cima, 100 - direita, 100 - baixo)
        for campo, valor in zip(self.margens, valores):
            campo.blockSignals(True)
            campo.setValue(min(max(valor, campo.minimum()), campo.maximum()))
            campo.blockSignals(False)
        # Um sinal só no fim: a prévia do diálogo e a miniatura leem as quatro de uma vez.
        self.margens[0].valueChanged.emit(self.margens[0].value())

    def _bordas_atuais(self):
        esquerda, cima, direita, baixo = (m.value() for m in self.margens)
        return esquerda, cima, 100 - direita, 100 - baixo

    def mousePressEvent(self, evento) -> None:
        if evento.button() != Qt.MouseButton.LeftButton:
            return
        ponto = evento.position()
        bordas = self._bordas_em(ponto)
        if bordas:
            modo = bordas
        elif self.retangulo().contains(ponto):
            modo = "mover"
        else:
            modo = "novo"
        self._arraste = (modo, self._fracao(ponto), self._bordas_atuais())

    def mouseMoveEvent(self, evento) -> None:
        ponto = evento.position()
        if self._arraste is None:
            self.setCursor(self._cursor_para(ponto))
            return
        modo, inicio, bordas = self._arraste
        novas = _bordas_arrastadas(modo, inicio, self._fracao(ponto), bordas)
        if novas is not None:
            self._por(*novas)

    def mouseReleaseEvent(self, _evento) -> None:
        self._arraste = None

    def pintar(self, pintor: QPainter) -> None:
        r = self.retangulo()
        fora = QRectF(self.rect())
        pintor.save()
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(estilo.FORA_DO_CORTE)
        # As quatro faixas fora do corte, sem se sobrepor (a sombra fica igual nos cantos).
        pintor.drawRect(QRectF(0, 0, fora.width(), r.top()))
        pintor.drawRect(QRectF(0, r.bottom(), fora.width(), fora.height() - r.bottom()))
        pintor.drawRect(QRectF(0, r.top(), r.left(), r.height()))
        pintor.drawRect(QRectF(r.right(), r.top(), fora.width() - r.right(), r.height()))
        pintor.setBrush(Qt.BrushStyle.NoBrush)
        pintor.setPen(QPen(estilo.SELECIONADO, 2))
        pintor.drawRect(r)
        pintor.setPen(QPen(estilo.CONTORNO_DA_SELECAO, 1))
        pintor.setBrush(estilo.SELECIONADO)
        for canto in (r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()):
            pintor.drawRect(QRectF(canto.x() - 3, canto.y() - 3, 6, 6))
        pintor.restore()


def _bordas_arrastadas(modo: str, inicio: QPointF, agora: QPointF, bordas):
    """As bordas do corte (esquerda, cima, direita, baixo, em porcentagem) com o arraste de
    `inicio` a `agora`: um retângulo novo ("novo"), o mesmo movido ("mover") ou as bordas de
    `modo` esticadas ("e", "dc"...). None se o novo ainda é um clique sem arraste."""
    if modo == "novo":
        return _corte_novo(inicio, agora)
    if modo == "mover":
        return _corte_movido(inicio, agora, bordas)
    return _corte_esticado(modo, agora, bordas)


def _corte_novo(inicio: QPointF, agora: QPointF):
    e, d = sorted((inicio.x(), agora.x()))
    c, b = sorted((inicio.y(), agora.y()))
    if d - e < SOBRA_MINIMA or b - c < SOBRA_MINIMA:
        return None                             # um clique sem arraste não apaga o corte
    return e, c, d, b


def _corte_movido(inicio: QPointF, agora: QPointF, bordas):
    """O corte inteiro levado junto, sem sair da página."""
    e, c, d, b = bordas
    dx = min(max(agora.x() - inicio.x(), -e), 100 - d)
    dy = min(max(agora.y() - inicio.y(), -c), 100 - b)
    return e + dx, c + dy, d + dx, b + dy


def _corte_esticado(modo: str, agora: QPointF, bordas):
    """As bordas de `modo` no ponto, sem passar da sobra mínima diante da borda oposta."""
    e, c, d, b = bordas
    if "e" in modo:
        e = min(agora.x(), d - SOBRA_MINIMA)
    if "d" in modo:
        d = max(agora.x(), e + SOBRA_MINIMA)
    if "c" in modo:
        c = min(agora.y(), b - SOBRA_MINIMA)
    if "b" in modo:
        b = max(agora.y(), c + SOBRA_MINIMA)
    return e, c, d, b


class PreviaDaDivisao(_Previa):
    """A linha da divisão sobre a página: clicar ou arrastar a põe no lugar. `campo` é o do
    diálogo, em porcentagem da largura."""

    def __init__(self, pixmap: QPixmap, campo: QDoubleSpinBox, legenda: str):
        super().__init__(pixmap, legenda)
        self.campo = campo
        campo.valueChanged.connect(self.update)
        self.setCursor(Qt.CursorShape.SplitHCursor)
        self._arrastando = False

    def x_da_linha(self) -> float:
        return self.campo.value() / 100 * self.width()

    def _por(self, ponto: QPointF) -> None:
        valor = self._fracao(ponto).x()
        self.campo.setValue(min(max(valor, self.campo.minimum()), self.campo.maximum()))

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton:
            self._arrastando = True
            self._por(evento.position())

    def mouseMoveEvent(self, evento) -> None:
        if self._arrastando:
            self._por(evento.position())

    def mouseReleaseEvent(self, _evento) -> None:
        self._arrastando = False

    def pintar(self, pintor: QPainter) -> None:
        x = self.x_da_linha()
        pintor.save()
        pintor.fillRect(QRectF(x, 0, self.width() - x, self.height()),
                        estilo.METADE_DA_DIREITA)
        pintor.setPen(QPen(estilo.CONTORNO_DA_SELECAO, 4))
        pintor.drawLine(QPointF(x, 0), QPointF(x, self.height()))
        pintor.setPen(QPen(estilo.SELECIONADO, 2))
        pintor.drawLine(QPointF(x, 0), QPointF(x, self.height()))
        pintor.restore()
