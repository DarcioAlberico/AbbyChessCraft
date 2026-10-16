"""A página com os boxes coloridos pela origem da leitura.

O botão direito sobre um box abre o menu de edição: dividir na coluna clicada
e juntar com o vizinho da linha, os mesmos comandos do painel de treino.

No **modo de treino** o arraste desenha o quadro de um glifo, em vez de mover a
página: é como se marca o que a segmentação perdeu, partiu ou colou. Em
qualquer modo, Ctrl+clique põe o box na seleção (ou o tira dela), para
ensinar várias ocorrências do mesmo glifo de uma vez.

No **editor de áreas** o arraste desenha uma área, o arraste dentro de uma área
a move e o das bordas a estica; Del apaga a selecionada e as teclas 1 a 4
trocam o tipo (texto, diagrama, imagem, ignorar). É outro modo, separado do de
treino: os dois usam o arraste, e um liga só com o outro desligado. A
geometria está em `abbychess.zonas`; aqui só se desenha e se emite.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QGraphicsItem, QGraphicsLineItem, QGraphicsRectItem,
                               QGraphicsScene, QGraphicsView, QMenu)

from core.box_model import BoxEntry

from abbychess import zonas as zn
from abbychess.app import cores


class VisorDePagina(QGraphicsView):
    """Mostra a página e os boxes. Clique escolhe um box; Ctrl+roda aproxima."""

    box_clicado = Signal(int)
    #: O box e a coluna da página onde dividi-lo.
    dividir_em = Signal(int, int)
    #: O box e o lado do vizinho com que juntá-lo: +1 o seguinte, -1 o anterior.
    juntar_com = Signal(int, int)
    #: O quadro desenhado no modo de treino: x1, y1, x2, y2 da página.
    area_desenhada = Signal(int, int, int, int)
    #: Ctrl+clique num box: entra na seleção, ou sai se já estava.
    box_alternado = Signal(int)
    #: Clique num diagrama, fora dos boxes: x, y da página (a janela acha qual é).
    diagrama_clicado = Signal(int, int)
    #: Editor de áreas: área nova desenhada (x1, y1, x2, y2 da página).
    zona_desenhada = Signal(int, int, int, int)
    #: Editor de áreas: a área escolhida, ou -1 para nenhuma.
    zona_escolhida = Signal(int)
    #: Editor de áreas: a área, as bordas arrastadas ("" move inteira) e o deslocamento.
    zona_arrastada = Signal(int, str, int, int)
    #: Editor de áreas: apagar a área.
    zona_apagada = Signal(int)
    #: Editor de áreas: a área e o tipo novo.
    zona_tipo = Signal(int, str)

    #: Menor lado, em pixels da página, para o arraste contar como quadro.
    MENOR_QUADRO = 3
    #: Distância da borda de uma área, em pixels de tela, que pega a borda.
    PEGA_DA_BORDA = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor(90, 90, 90)))
        self._itens: List[QGraphicsRectItem] = []
        #: O item de cada box, na ordem de `_boxes` (para repintar só alguns).
        self._itens_dos_boxes: List[QGraphicsRectItem] = []
        self._boxes: List[BoxEntry] = []
        self._selecionado: Optional[int] = None
        self._destaque: Optional[QGraphicsRectItem] = None
        self._corte: Optional[QGraphicsLineItem] = None
        self._marcados: List[QGraphicsRectItem] = []
        self._marcados_indices: set = set()
        self.modo_treino = False
        self._inicio = None
        self._quadro: Optional[QGraphicsRectItem] = None
        self.modo_areas = False
        self._zonas: List[zn.Zona] = []
        self._zona_sel: Optional[int] = None
        self._zonas_itens: list = []
        #: O arraste de uma área em curso: (índice, bordas, ponto inicial).
        self._arraste = None
        self._palavra: Optional[QGraphicsRectItem] = None

    # ------------------------------------------------------------------
    def mostrar_pagina(self, pixmap: QPixmap) -> None:
        cena = self.scene()
        cena.clear()
        self._itens, self._boxes, self._selecionado, self._destaque = [], [], None, None
        self._corte = None
        self._marcados, self._marcados_indices, self._quadro = [], set(), None
        self._zonas, self._zona_sel, self._zonas_itens, self._arraste = [], None, [], None
        self._palavra = None
        cena.addPixmap(pixmap)
        cena.setSceneRect(QRectF(pixmap.rect()))
        self.resetTransform()
        self.fitInView(cena.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def mostrar_boxes(self, boxes: List[BoxEntry], pendentes: set, tabuleiros=(),
                      cores_dos_tabuleiros=None) -> None:
        """`cores_dos_tabuleiros`, uma cor por tabuleiro, diz o estado da leitura."""
        cena = self.scene()
        for item in self._itens:
            cena.removeItem(item)
        if self._destaque is not None:
            cena.removeItem(self._destaque)
            self._destaque = None
        self._itens, self._boxes, self._itens_dos_boxes = [], boxes, []
        self._tabuleiros = [tuple(t) for t in tabuleiros]
        for i, (x1, y1, x2, y2) in enumerate(self._tabuleiros):
            caneta = QPen(cores_dos_tabuleiros[i] if cores_dos_tabuleiros else cores.DIAGRAMA)
            caneta.setCosmetic(True)
            caneta.setWidthF(2.5)
            caneta.setStyle(Qt.PenStyle.DashLine)
            item = QGraphicsRectItem(x1, y1, x2 - x1, y2 - y1)
            item.setPen(caneta)
            cena.addItem(item)
            self._itens.append(item)
        for i, b in enumerate(boxes):
            item = QGraphicsRectItem(b.x1, b.y1, b.x2 - b.x1, b.y2 - b.y1)
            self._pintar(item, b, i in pendentes)
            cena.addItem(item)
            self._itens.append(item)
            self._itens_dos_boxes.append(item)
        self.marcar_selecao(self._marcados_indices)
        if self._selecionado is not None and self._selecionado < len(boxes):
            self.selecionar(self._selecionado, centralizar=False)

    @staticmethod
    def _pintar(item: QGraphicsRectItem, b: BoxEntry, pendente: bool) -> None:
        cor = cores.cor_do_box(b.char, b.source, pendente)
        caneta = QPen(cor)
        caneta.setCosmetic(True)
        caneta.setWidthF(1.2)
        item.setPen(caneta)
        preenchimento = QColor(cor)
        preenchimento.setAlpha(40 if pendente or not b.char else 0)
        item.setBrush(QBrush(preenchimento))

    def repintar_boxes(self, boxes: List[BoxEntry], pendentes: set, indices) -> bool:
        """Repinta só os boxes `indices` (a leitura ou a cor mudou, a caixa não). Falso, sem
        mudar nada, se a lista não é a desenhada (aí é `mostrar_boxes`)."""
        if len(boxes) != len(self._itens_dos_boxes):
            return False
        for i in indices:
            b, item = boxes[i], self._itens_dos_boxes[i]
            if item.rect().toRect().getCoords()[:2] != (b.x1, b.y1):
                return False                # a caixa mudou: desenhar tudo
            self._pintar(item, b, i in pendentes)
        self._boxes = boxes
        return True

    def selecionar(self, indice: Optional[int], centralizar: bool = True) -> None:
        cena = self.scene()
        if self._destaque is not None:
            cena.removeItem(self._destaque)
            self._destaque = None
        self.marcar_corte(None)
        self._selecionado = indice
        if indice is None or not 0 <= indice < len(self._boxes):
            return
        b = self._boxes[indice]
        margem = 3
        caneta = QPen(cores.SELECIONADO)
        caneta.setCosmetic(True)
        caneta.setWidthF(3)
        self._destaque = cena.addRect(b.x1 - margem, b.y1 - margem,
                                      b.x2 - b.x1 + 2 * margem, b.y2 - b.y1 + 2 * margem, caneta)
        self._destaque.setZValue(10)
        if centralizar:
            self.ensureVisible(self._destaque, 120, 120)

    def marcar_selecao(self, indices) -> None:
        """Contorna em ciano os boxes da seleção do modo de treino."""
        cena = self.scene()
        for item in self._marcados:
            cena.removeItem(item)
        self._marcados = []
        self._marcados_indices = {i for i in indices if 0 <= i < len(self._boxes)}
        caneta = QPen(cores.MARCADO)
        caneta.setCosmetic(True)
        caneta.setWidthF(2.5)
        for i in sorted(self._marcados_indices):
            b = self._boxes[i]
            item = cena.addRect(b.x1 - 2, b.y1 - 2, b.x2 - b.x1 + 4, b.y2 - b.y1 + 4, caneta)
            item.setZValue(9)
            self._marcados.append(item)

    def definir_modo_treino(self, sim: bool) -> None:
        """No modo de treino o arraste desenha o quadro de um glifo."""
        if sim and self.modo_areas:
            self.definir_modo_areas(False)
        self.modo_treino = sim
        self._cursor_do_modo()

    def definir_modo_areas(self, sim: bool) -> None:
        """No editor de áreas o arraste desenha, move e estica as áreas da página."""
        self.modo_areas = sim
        if sim:
            self.modo_treino = False
        self._arraste, self._inicio = None, None
        self.viewport().setMouseTracking(sim)
        self._cursor_do_modo()
        self.mostrar_zonas(self._zonas, self._zona_sel)

    def _cursor_do_modo(self) -> None:
        livre = not (self.modo_treino or self.modo_areas)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if livre
                         else QGraphicsView.DragMode.NoDrag)
        self.viewport().setCursor(Qt.CursorShape.OpenHandCursor if livre
                                  else Qt.CursorShape.CrossCursor)

    def mostrar_zonas(self, zonas, selecionada: Optional[int] = None) -> None:
        """Desenha as áreas, com o número e o tipo no canto. Só no editor de áreas."""
        cena = self.scene()
        for item in self._zonas_itens:
            cena.removeItem(item)
        self._zonas_itens = []
        self._zonas = list(zonas)
        valida = selecionada is not None and 0 <= selecionada < len(self._zonas)
        self._zona_sel = selecionada if valida else None
        if not self.modo_areas:
            return
        for i, z in enumerate(self._zonas):
            cor = cores.COR_DA_ZONA[z.tipo]
            caneta = QPen(cor)
            caneta.setCosmetic(True)
            caneta.setWidthF(3.5 if i == self._zona_sel else 2)
            if i == self._zona_sel:
                caneta.setStyle(Qt.PenStyle.DashLine)
            fundo = QColor(cor)
            fundo.setAlpha(45 if i == self._zona_sel else 25)
            item = cena.addRect(z.x1, z.y1, z.x2 - z.x1, z.y2 - z.y1, caneta, QBrush(fundo))
            item.setZValue(5)
            rotulo = cena.addSimpleText(f"{i + 1} {zn.NOMES[z.tipo]}")
            rotulo.setBrush(QBrush(cor))
            rotulo.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            rotulo.setPos(z.x1 + 2, z.y1 + 2)
            rotulo.setZValue(6)
            self._zonas_itens += [item, rotulo]

    def menu_da_zona(self, indice: int) -> QMenu:
        """O tipo da área e apagá-la, pelo botão direito."""
        menu = QMenu(self)
        for numero, tipo in enumerate(zn.TIPOS, start=1):
            acao = menu.addAction(f"{zn.NOMES[tipo]}\t{numero}")
            acao.setCheckable(True)
            acao.setChecked(self._zonas[indice].tipo == tipo)
            acao.triggered.connect(lambda _=False, t=tipo: self.zona_tipo.emit(indice, t))
        menu.addSeparator()
        menu.addAction("Apagar área\tDel").triggered.connect(
            lambda: self.zona_apagada.emit(indice))
        return menu

    def marcar_corte(self, coluna: Optional[int]) -> None:
        """A linha onde o box selecionado vai ser dividido, ou nenhuma."""
        if self._corte is not None:
            self.scene().removeItem(self._corte)
            self._corte = None
        indice = self._selecionado
        if coluna is None or indice is None or not 0 <= indice < len(self._boxes):
            return
        b = self._boxes[indice]
        caneta = QPen(cores.SELECIONADO)
        caneta.setCosmetic(True)
        caneta.setWidthF(2)
        self._corte = self.scene().addLine(coluna, b.y1 - 4, coluna, b.y2 + 4, caneta)
        self._corte.setZValue(11)

    def marcar_palavra(self, caixa) -> None:
        """Contorna a palavra em verificação e a traz para a vista, ou apaga o contorno."""
        if self._palavra is not None:
            self.scene().removeItem(self._palavra)
            self._palavra = None
        if caixa is None:
            return
        x1, y1, x2, y2 = caixa
        caneta = QPen(cores.PALAVRA)
        caneta.setCosmetic(True)
        caneta.setWidthF(3)
        self._palavra = self.scene().addRect(x1 - 6, y1 - 6, x2 - x1 + 12, y2 - y1 + 12, caneta)
        self._palavra.setZValue(13)
        self.ensureVisible(self._palavra, 150, 150)

    def menu_do_box(self, indice: int, coluna: int) -> QMenu:
        """O menu de edição do box, com a coluna onde o botão direito caiu."""
        menu = QMenu(self)
        dividir = menu.addAction("Dividir aqui")
        dividir.triggered.connect(lambda: self.dividir_em.emit(indice, coluna))
        b = self._boxes[indice]
        dividir.setEnabled(b.x1 < coluna < b.x2)
        menu.addAction("Juntar com o anterior").triggered.connect(
            lambda: self.juntar_com.emit(indice, -1))
        menu.addAction("Juntar com o seguinte").triggered.connect(
            lambda: self.juntar_com.emit(indice, +1))
        return menu

    # ------------------------------------------------------------------
    def _box_em(self, ponto) -> Optional[int]:
        x, y = ponto.x(), ponto.y()
        achados = [(b.width * b.height, i) for i, b in enumerate(self._boxes)
                   if b.x1 <= x <= b.x2 and b.y1 <= y <= b.y2]
        return min(achados)[1] if achados else None

    def _pega(self) -> float:
        """A tolerância das bordas em pixels da página, na escala atual."""
        return self.PEGA_DA_BORDA / max(self.transform().m11(), 1e-6)

    def _tamanho_da_pagina(self):
        retangulo = self.scene().sceneRect()
        return int(retangulo.width()), int(retangulo.height())

    def apertar_no_editor_de_areas(self, ponto) -> None:
        """Na borda da área escolhida, estica; dentro de uma área, escolhe e move;
        fora de todas, começa uma área nova."""
        x, y = ponto.x(), ponto.y()
        sel = self._zona_sel
        if sel is not None:
            bordas = zn.bordas_em(self._zonas[sel], x, y, self._pega())
            if bordas:
                self._arraste = (sel, bordas, ponto)
                return
        indice = zn.zona_em(self._zonas, x, y)
        if indice is not None:
            if indice != sel:
                self.zona_escolhida.emit(indice)
            self._arraste = (indice, "", ponto)
            return
        if sel is not None:
            self.zona_escolhida.emit(-1)
        self._inicio = ponto

    def _cursor_das_bordas(self, ponto) -> None:
        sel = self._zona_sel
        bordas = (zn.bordas_em(self._zonas[sel], ponto.x(), ponto.y(), self._pega())
                  if sel is not None else "")
        if bordas in ("ec", "db"):
            forma = Qt.CursorShape.SizeFDiagCursor
        elif bordas in ("dc", "eb"):
            forma = Qt.CursorShape.SizeBDiagCursor
        elif bordas in ("e", "d"):
            forma = Qt.CursorShape.SizeHorCursor
        elif bordas in ("c", "b"):
            forma = Qt.CursorShape.SizeVerCursor
        elif zn.zona_em(self._zonas, ponto.x(), ponto.y()) is not None:
            forma = Qt.CursorShape.SizeAllCursor
        else:
            forma = Qt.CursorShape.CrossCursor
        self.viewport().setCursor(forma)

    def mousePressEvent(self, evento):
        if self.modo_areas:
            if evento.button() == Qt.MouseButton.LeftButton:
                self.apertar_no_editor_de_areas(self.mapToScene(evento.position().toPoint()))
                self.setFocus()
            return
        if evento.button() == Qt.MouseButton.LeftButton:
            ponto = self.mapToScene(evento.position().toPoint())
            indice = self._box_em(ponto)
            if evento.modifiers() & Qt.KeyboardModifier.ControlModifier:
                if indice is not None:
                    self.box_alternado.emit(indice)
                return
            if self.modo_treino:
                # Clique escolhe o box; arraste desenha o quadro (ver mouseRelease).
                self._inicio = ponto
                return
            if indice is not None:
                self.box_clicado.emit(indice)
            elif self._no_tabuleiro(ponto):
                self.diagrama_clicado.emit(int(ponto.x()), int(ponto.y()))
                return
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento):
        if self.modo_areas and self._arraste is not None:
            self.previa_do_arraste(self.mapToScene(evento.position().toPoint()))
            return
        if self.modo_areas and self._inicio is None:
            self._cursor_das_bordas(self.mapToScene(evento.position().toPoint()))
            return
        if self._inicio is not None:
            ponto = self.mapToScene(evento.position().toPoint())
            retangulo = QRectF(self._inicio, ponto).normalized()
            if self._quadro is None:
                caneta = QPen(cores.COR_DA_ZONA[zn.TEXTO] if self.modo_areas else cores.MARCADO)
                caneta.setCosmetic(True)
                caneta.setWidthF(1.5)
                caneta.setStyle(Qt.PenStyle.DashLine)
                self._quadro = self.scene().addRect(retangulo, caneta)
                self._quadro.setZValue(12)
            else:
                self._quadro.setRect(retangulo)
            return
        super().mouseMoveEvent(evento)

    def previa_do_arraste(self, ponto) -> None:
        """A área em arraste desenhada onde vai ficar, antes de soltar."""
        indice, bordas, inicio = self._arraste
        largura, altura = self._tamanho_da_pagina()
        z = zn.arrastar(self._zonas[indice], bordas, ponto.x() - inicio.x(),
                        ponto.y() - inicio.y(), largura, altura)
        if 2 * indice + 1 < len(self._zonas_itens):
            self._zonas_itens[2 * indice].setRect(z.x1, z.y1, z.x2 - z.x1, z.y2 - z.y1)
            self._zonas_itens[2 * indice + 1].setPos(z.x1 + 2, z.y1 + 2)

    def soltar_arraste(self, fim) -> None:
        """O fim do arraste de uma área: emite o deslocamento, se houve."""
        (indice, bordas, inicio), self._arraste = self._arraste, None
        dx, dy = int(round(fim.x() - inicio.x())), int(round(fim.y() - inicio.y()))
        if dx or dy:
            self.zona_arrastada.emit(indice, bordas, dx, dy)

    def mouseReleaseEvent(self, evento):
        if evento.button() == Qt.MouseButton.LeftButton and self._arraste is not None:
            self.soltar_arraste(self.mapToScene(evento.position().toPoint()))
            return
        if self._inicio is not None and evento.button() == Qt.MouseButton.LeftButton:
            inicio, self._inicio = self._inicio, None
            if self._quadro is not None:
                self.scene().removeItem(self._quadro)
                self._quadro = None
            fim = self.mapToScene(evento.position().toPoint())
            if self.modo_areas:
                self.soltar_area(inicio, fim)
            else:
                self.soltar_quadro(inicio, fim)
            return
        super().mouseReleaseEvent(evento)

    def soltar_area(self, inicio, fim) -> None:
        """O fim do arraste fora das áreas, no editor de áreas: uma área nova."""
        retangulo = QRectF(inicio, fim).normalized()
        if min(retangulo.width(), retangulo.height()) >= zn.MENOR_LADO:
            self.zona_desenhada.emit(int(retangulo.left()), int(retangulo.top()),
                                     int(retangulo.right()) + 1, int(retangulo.bottom()) + 1)

    def keyPressEvent(self, evento):
        if self.modo_areas and self._zona_sel is not None:
            tecla = evento.key()
            if tecla in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                self.zona_apagada.emit(self._zona_sel)
                return
            numeros = (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4)
            if tecla in numeros:
                self.zona_tipo.emit(self._zona_sel, zn.TIPOS[numeros.index(tecla)])
                return
            if tecla == Qt.Key.Key_Escape:
                self.zona_escolhida.emit(-1)
                return
        super().keyPressEvent(evento)

    def soltar_quadro(self, inicio, fim) -> None:
        """O fim do arraste no modo de treino: quadro novo, ou clique num box."""
        retangulo = QRectF(inicio, fim).normalized()
        if min(retangulo.width(), retangulo.height()) >= self.MENOR_QUADRO:
            self.area_desenhada.emit(int(retangulo.left()), int(retangulo.top()),
                                     int(retangulo.right()) + 1, int(retangulo.bottom()) + 1)
            return
        indice = self._box_em(fim)
        if indice is not None:
            self.box_clicado.emit(indice)
        elif self._no_tabuleiro(fim):
            self.diagrama_clicado.emit(int(fim.x()), int(fim.y()))

    def _no_tabuleiro(self, ponto) -> bool:
        return any(x1 <= ponto.x() <= x2 and y1 <= ponto.y() <= y2
                   for x1, y1, x2, y2 in getattr(self, "_tabuleiros", ()))

    def contextMenuEvent(self, evento):
        ponto = self.mapToScene(evento.pos())
        if self.modo_areas:
            indice = zn.zona_em(self._zonas, ponto.x(), ponto.y())
            if indice is not None:
                if indice != self._zona_sel:
                    self.zona_escolhida.emit(indice)
                self.menu_da_zona(indice).exec(evento.globalPos())
            return
        indice = self._box_em(ponto)
        if indice is None:
            return
        self.box_clicado.emit(indice)
        self.menu_do_box(indice, int(ponto.x())).exec(evento.globalPos())

    def wheelEvent(self, evento):
        if evento.modifiers() & Qt.KeyboardModifier.ControlModifier:
            fator = 1.15 if evento.angleDelta().y() > 0 else 1 / 1.15
            self.scale(fator, fator)
            return
        super().wheelEvent(evento)

    def ajustar(self) -> None:
        self.resetTransform()
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
