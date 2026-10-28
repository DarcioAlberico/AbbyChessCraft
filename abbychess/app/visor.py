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

**Desde o passo A1** (§3.3): os boxes são um item só (`ItemDosBoxes`), com os estados de
§13; o zoom vai de 5% a 800% (página inteira, largura, 100%, o item atual, e os passos de
Ctrl+roda e Ctrl++/−), e em "página inteira" e "largura" segue o redimensionamento; as
barras ficam sempre visíveis; o espaço e o botão do meio arrastam a página em qualquer
modo; PgUp e PgDn rolam uma tela e, no fim, pedem a página vizinha (`pagina_vizinha`).
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QContextMenuEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QGraphicsItem, QGraphicsLineItem, QGraphicsRectItem,
                               QGraphicsScene, QGraphicsView, QMenu)

from core.box_model import BoxEntry

from abbychess import grade as gd
from abbychess import zonas as zn
from abbychess.app import estilo
from abbychess.app.item_dos_boxes import ItemDosBoxes


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
    #: Editor de áreas: a área e a função semântica nova.
    zona_funcao = Signal(int, str)
    ordenacao_cancelada = Signal()
    #: O zoom mudou: a escala (1 = 100%) e o limite alcançado ("máximo", "mínimo" ou "").
    zoom_mudou = Signal(float, str)
    #: PgDn no fim da página (+1) ou PgUp no topo (-1): a página vizinha.
    pagina_vizinha = Signal(int)

    #: Os limites do zoom (§3.3).
    ESCALA_MINIMA = 0.05
    ESCALA_MAXIMA = 8.0
    #: O passo do Ctrl++ / Ctrl+− e o da roda.
    PASSO_DO_ZOOM = 1.25
    PASSO_DA_RODA = 1.15

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
        self.setBackgroundBrush(QBrush(estilo.FUNDO_DA_IMAGEM))
        #: O que a Imagem diz sem página (§13, estado vazio): sem livro aberto, a instrução.
        self.mensagem_vazia = ""
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        #: Os itens que não são boxes e saem a cada `mostrar_boxes` (os tabuleiros).
        self._itens: List[QGraphicsRectItem] = []
        #: O item único dos boxes (CA-3.4).
        self.item_dos_boxes: Optional[ItemDosBoxes] = None
        self._boxes: List[BoxEntry] = []
        #: "pagina", "largura" (o zoom segue o tamanho da janela) ou None (escala fixa).
        self.modo_zoom: Optional[str] = "pagina"
        #: O arraste da página com o espaço ou o botão do meio: o último ponto.
        self._panorama = None
        self._espaco = False
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
        #: O contorno da palavra sob o cursor do Documento (§6.2): outro item, para não
        #: apagar o da palavra em verificação.
        self._palavra_do_documento: Optional[QGraphicsRectItem] = None

    # ------------------------------------------------------------------
    def definir_vazio(self, mensagem: str) -> None:
        """Sem página na cena, a Imagem mostra `mensagem` (vazia: nada)."""
        self.mensagem_vazia = mensagem
        self.viewport().update()

    def drawForeground(self, pintor: QPainter, retangulo: QRectF) -> None:
        super().drawForeground(pintor, retangulo)
        if not self.mensagem_vazia:             # com página, sai aqui: nada de varrer a cena
            return
        pintor.save()
        pintor.resetTransform()                 # o texto na tela, não na página
        pintor.setPen(estilo.PAPEL)
        area = self.viewport().rect().adjusted(24, 24, -24, -24)
        pintor.drawText(area, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                        self.mensagem_vazia)
        pintor.restore()

    def mostrar_pagina(self, pixmap: QPixmap) -> None:
        self.mensagem_vazia = ""                # a página toma o lugar do estado vazio
        cena = self.scene()
        cena.clear()
        self._itens, self._boxes, self._selecionado, self._destaque = [], [], None, None
        self._corte = None
        self._marcados, self._marcados_indices, self._quadro = [], set(), None
        self._zonas, self._zona_sel, self._zonas_itens, self._arraste = [], None, [], None
        self._palavra = None
        self._palavra_do_documento = None
        cena.addPixmap(pixmap)
        cena.setSceneRect(QRectF(pixmap.rect()))
        self.item_dos_boxes = ItemDosBoxes(pixmap.width(), pixmap.height())
        self.item_dos_boxes.setZValue(1)
        cena.addItem(self.item_dos_boxes)
        # A escala passa de uma página à outra; nos modos, ela se refaz pela página nova. A
        # página nova começa no topo (o PgUp no topo pede o fim, e a janela o põe depois).
        if self.modo_zoom == "largura":
            self.verticalScrollBar().setValue(0)
        if self.modo_zoom is not None:
            self._aplicar_modo()
        else:
            self.zoom_mudou.emit(self.escala(), "")
        self.ir_ao_topo()

    def mostrar_boxes(self, boxes: List[BoxEntry], pendentes: set, tabuleiros=(),
                      cores_dos_tabuleiros=None) -> None:
        """`cores_dos_tabuleiros`, uma cor por tabuleiro, diz o estado da leitura."""
        cena = self.scene()
        for item in self._itens:
            cena.removeItem(item)
        if self._destaque is not None:
            cena.removeItem(self._destaque)
            self._destaque = None
        self._itens, self._boxes = [], boxes
        self._tabuleiros = [tuple(t) for t in tabuleiros]
        for i, (x1, y1, x2, y2) in enumerate(self._tabuleiros):
            caneta = QPen(cores_dos_tabuleiros[i] if cores_dos_tabuleiros else estilo.DIAGRAMA_POR_LER)
            caneta.setCosmetic(True)
            caneta.setWidthF(2.5)
            caneta.setStyle(Qt.PenStyle.DashLine)
            item = QGraphicsRectItem(x1, y1, x2 - x1, y2 - y1)
            item.setPen(caneta)
            cena.addItem(item)
            self._itens.append(item)
        if self.item_dos_boxes is not None:
            self.item_dos_boxes.trocar(boxes, [gd.estado(b, i in pendentes)
                                               for i, b in enumerate(boxes)])
        self.marcar_selecao(self._marcados_indices)
        if self._selecionado is not None and self._selecionado < len(boxes):
            self.selecionar(self._selecionado, centralizar=False)

    def repintar_boxes(self, boxes: List[BoxEntry], pendentes: set, indices) -> bool:
        """Repinta só os boxes `indices`, com a caixa e o estado de agora (a lista é a
        mesma: nenhum entrou nem saiu). Falso, sem mudar nada, se a lista não é a desenhada
        (aí é `mostrar_boxes`)."""
        item = self.item_dos_boxes
        if item is None or len(boxes) != len(item.grade.caixas):
            return False
        item.atualizar({i: gd.estado(boxes[i], i in pendentes) for i in indices}, boxes)
        self._boxes = boxes
        return True

    def definir_origem(self, sim: bool) -> None:
        """V: os aceitos na cor da origem da leitura (livro, rede, manual)."""
        if self.item_dos_boxes is not None:
            self.item_dos_boxes.definir_origem(sim)

    # ------------------------------------------------------------------
    # Zoom (§3.3)
    # ------------------------------------------------------------------
    def escala(self) -> float:
        return self.transform().m11()

    def _escalar(self, nova: float, modo: Optional[str] = None, *, avisar: bool = True) -> None:
        """`avisar`: o limite vai à barra ("zoom máximo"); o ajuste da página inteira ou da
        largura ao redimensionar não avisa."""
        limite = ""
        if nova >= self.ESCALA_MAXIMA:
            nova, limite = self.ESCALA_MAXIMA, "máximo"
        elif nova <= self.ESCALA_MINIMA:
            nova, limite = self.ESCALA_MINIMA, "mínimo"
        fator = nova / max(self.escala(), 1e-9)
        if abs(fator - 1) > 1e-6:
            self.scale(fator, fator)
        self.modo_zoom = modo
        self.zoom_mudou.emit(self.escala(), limite if avisar else "")

    def zoom_mais(self) -> None:
        self._escalar(self.escala() * self.PASSO_DO_ZOOM)

    def zoom_menos(self) -> None:
        self._escalar(self.escala() / self.PASSO_DO_ZOOM)

    def zoom_100(self) -> None:
        self._escalar(1.0)

    def definir_zoom(self, escala: float) -> None:
        self._escalar(escala)

    def zoom_pagina(self) -> None:
        self.modo_zoom = "pagina"
        self._aplicar_modo()

    def zoom_largura(self) -> None:
        self.modo_zoom = "largura"
        self._aplicar_modo()

    def zoom_item(self) -> None:
        """Ctrl+7: o item atual (o box em revisão) ocupa a vista, com folga em volta."""
        if self._selecionado is None or not 0 <= self._selecionado < len(self._boxes):
            return
        b = self._boxes[self._selecionado]
        lado = max(b.x2 - b.x1, b.y2 - b.y1, 8)
        alvo = QRectF(b.x1 - 3 * lado, b.y1 - 2 * lado, (b.x2 - b.x1) + 6 * lado,
                      (b.y2 - b.y1) + 4 * lado)
        vista = self.viewport().rect()
        self._escalar(min(vista.width() / alvo.width(), vista.height() / alvo.height()))
        self.centerOn(alvo.center())

    def enquadrar(self, caixa, folga: float = 0.12) -> None:
        """A caixa (da página) ocupa a vista, com `folga` em volta (o diagrama em conferência,
        §10). O zoom fica livre: Ctrl+roda, PgUp/PgDn e as barras continuam valendo."""
        x1, y1, x2, y2 = caixa
        largura, altura = max(x2 - x1, 8), max(y2 - y1, 8)
        alvo = QRectF(x1 - folga * largura, y1 - folga * altura,
                      largura * (1 + 2 * folga), altura * (1 + 2 * folga))
        vista = self.viewport().rect()
        if vista.width() >= 40 and vista.height() >= 40:
            self._escalar(min(vista.width() / alvo.width(), vista.height() / alvo.height()))
        self.centerOn(alvo.center())

    def _aplicar_modo(self) -> None:
        cena = self.scene().sceneRect()
        vista = self.viewport().rect()
        if cena.isEmpty() or vista.width() < 40 or vista.height() < 40:
            return                              # sem tamanho útil (a doca recolhida): nada
        if self.modo_zoom == "largura":
            nova = (vista.width() - 4) / cena.width()
        else:
            nova = min((vista.width() - 4) / cena.width(), (vista.height() - 4) / cena.height())
        modo = self.modo_zoom
        barra = self.verticalScrollBar()
        fracao = barra.value() / barra.maximum() if barra.maximum() > 0 else 0.0
        self._escalar(nova, modo, avisar=False)
        if modo == "largura":                   # a mesma altura da página, na escala nova
            barra.setValue(round(fracao * barra.maximum()))
        else:
            self.centerOn(cena.center())

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        if self.modo_zoom is not None:
            self._aplicar_modo()

    # ------------------------------------------------------------------
    # Rolagem (§3.3)
    # ------------------------------------------------------------------
    def rolar_tela(self, passo: int) -> None:
        """PgDn (+1) e PgUp (-1): uma tela; no fim (ou no topo), a página vizinha."""
        barra = self.verticalScrollBar()
        if passo > 0 and barra.value() >= barra.maximum():
            self.pagina_vizinha.emit(+1)
        elif passo < 0 and barra.value() <= barra.minimum():
            self.pagina_vizinha.emit(-1)
        else:
            barra.setValue(barra.value() + passo * barra.pageStep())

    def ir_ao_topo(self) -> None:
        self.verticalScrollBar().setValue(self.verticalScrollBar().minimum())

    def ir_ao_fim(self) -> None:
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

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
        retangulo = QRectF(b.x1 - margem, b.y1 - margem,
                           b.x2 - b.x1 + 2 * margem, b.y2 - b.y1 + 2 * margem)
        # Contorno duplo (§3.3): o escuro por fora, que aparece no papel e na ilustração,
        # e o amarelo por dentro; o de dentro é filho, e sai junto.
        fora = QPen(estilo.CONTORNO_DA_SELECAO)
        fora.setCosmetic(True)
        fora.setWidthF(5)
        self._destaque = cena.addRect(retangulo, fora)
        dentro = QPen(estilo.SELECIONADO)
        dentro.setCosmetic(True)
        dentro.setWidthF(2.5)
        QGraphicsRectItem(retangulo, self._destaque).setPen(dentro)
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
        caneta = QPen(estilo.MARCADO)
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
            cor = estilo.COR_DA_FUNCAO.get(z.funcao, estilo.COR_DA_ZONA[z.tipo])
            caneta = QPen(cor)
            caneta.setCosmetic(True)
            caneta.setWidthF(3.5 if i == self._zona_sel else 2)
            if i == self._zona_sel:
                caneta.setStyle(Qt.PenStyle.DashLine)
            fundo = QColor(cor)
            fundo.setAlpha(45 if i == self._zona_sel else 25)
            item = cena.addRect(z.x1, z.y1, z.x2 - z.x1, z.y2 - z.y1, caneta, QBrush(fundo))
            item.setZValue(5)
            numero = z.ordem + 1 if z.ordem is not None else i + 1
            rotulo = cena.addSimpleText(f"{numero} {zn.NOMES_DAS_FUNCOES[z.funcao]}")
            rotulo.setBrush(QBrush(cor))
            rotulo.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            rotulo.setPos(z.x1 + 2, z.y1 + 2)
            rotulo.setZValue(6)
            self._zonas_itens += [item, rotulo]

    def menu_da_zona(self, indice: int) -> QMenu:
        """A função da área e apagá-la, pelo botão direito."""
        menu = QMenu(self)
        teclas = {"texto": "T", "titulo": "H", "cabecalho": "C", "rodape": "R",
                  "numero_de_pagina": "P", "nota": "N", "legenda": "L", "diagrama": "D",
                  "figura": "I", "ignorar": "X"}
        for funcao in teclas:
            acao = menu.addAction(f"{zn.NOMES_DAS_FUNCOES[funcao]}\t{teclas[funcao]}")
            acao.setCheckable(True)
            acao.setChecked(self._zonas[indice].funcao == funcao)
            acao.triggered.connect(lambda _=False, f=funcao: self.zona_funcao.emit(indice, f))
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
        caneta = QPen(estilo.SELECIONADO)
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
        caneta = QPen(estilo.PALAVRA)
        caneta.setCosmetic(True)
        caneta.setWidthF(3)
        self._palavra = self.scene().addRect(x1 - 6, y1 - 6, x2 - x1 + 12, y2 - y1 + 12, caneta)
        self._palavra.setZValue(13)
        self.ensureVisible(self._palavra, 150, 150)

    def marcar_palavra_do_documento(self, caixa) -> None:
        """Contorna (tracejado) a palavra sob o cursor do Documento, sem rolar: quem rola é o
        Seguir (`mostrar_caixa`)."""
        if self._palavra_do_documento is not None:
            self.scene().removeItem(self._palavra_do_documento)
            self._palavra_do_documento = None
        if caixa is None:
            return
        x1, y1, x2, y2 = caixa
        caneta = QPen(estilo.AZUL)
        caneta.setCosmetic(True)
        caneta.setWidthF(2)
        caneta.setStyle(Qt.PenStyle.DashLine)
        self._palavra_do_documento = self.scene().addRect(x1 - 4, y1 - 4, x2 - x1 + 8,
                                                          y2 - y1 + 8, caneta)
        self._palavra_do_documento.setZValue(12)

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
        if self.item_dos_boxes is None:
            return None
        return self.item_dos_boxes.no_ponto(ponto.x(), ponto.y())

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
        botao = evento.button()
        if botao == Qt.MouseButton.MiddleButton or (
                self._espaco and botao == Qt.MouseButton.LeftButton):
            self._panorama = evento.position()      # arrasta a página, em qualquer modo
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            return
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
        if self._panorama is not None:
            delta = evento.position() - self._panorama
            self._panorama = evento.position()
            barra_h, barra_v = self.horizontalScrollBar(), self.verticalScrollBar()
            barra_h.setValue(barra_h.value() - int(delta.x()))
            barra_v.setValue(barra_v.value() - int(delta.y()))
            return
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
                caneta = QPen(estilo.COR_DA_ZONA[zn.TEXTO] if self.modo_areas else estilo.MARCADO)
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
        if self._panorama is not None:
            self._panorama = None
            self._cursor_do_modo()
            return
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
        tecla = evento.key()
        if tecla == Qt.Key.Key_Space and not evento.isAutoRepeat():
            self._espaco = True
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
            return
        if self.modo_areas and self._zona_sel is not None:
            tecla = evento.key()
            if tecla in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                self.zona_apagada.emit(self._zona_sel)
                return
            numeros = (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4)
            if tecla in numeros:
                self.zona_tipo.emit(self._zona_sel, zn.TIPOS[numeros.index(tecla)])
                return
            funcoes = {Qt.Key.Key_T: "texto", Qt.Key.Key_H: "titulo",
                       Qt.Key.Key_C: "cabecalho", Qt.Key.Key_R: "rodape",
                       Qt.Key.Key_P: "numero_de_pagina", Qt.Key.Key_N: "nota",
                       Qt.Key.Key_L: "legenda", Qt.Key.Key_D: "diagrama",
                       Qt.Key.Key_I: "figura", Qt.Key.Key_X: "ignorar"}
            if tecla in funcoes and evento.modifiers() == Qt.KeyboardModifier.NoModifier:
                self.zona_funcao.emit(self._zona_sel, funcoes[tecla])
                return
        if self.modo_areas and tecla == Qt.Key.Key_Escape:
            self.ordenacao_cancelada.emit()
            self.zona_escolhida.emit(-1)
            return
        super().keyPressEvent(evento)

    def focusOutEvent(self, evento):
        # O espaço solto fora do visor (Alt+Tab, um diálogo) não chega aqui: sem isto, o
        # próximo clique arrastaria a página em vez de escolher o box.
        self._espaco, self._panorama = False, None
        self._cursor_do_modo()
        super().focusOutEvent(evento)

    def keyReleaseEvent(self, evento):
        if evento.key() == Qt.Key.Key_Space and not evento.isAutoRepeat():
            self._espaco = False
            self._cursor_do_modo()
            return
        super().keyReleaseEvent(evento)

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
        if evento.reason() == QContextMenuEvent.Reason.Keyboard:
            self._menu_pelo_teclado()           # Shift+F10 e a tecla Menu (§3.2)
            return
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
            self.menu_da_vista().exec(evento.globalPos())
            return
        self.box_clicado.emit(indice)
        self.menu_do_box(indice, int(ponto.x())).exec(evento.globalPos())

    def _menu_pelo_teclado(self) -> None:
        """O menu do box em revisão, no meio dele; sem box, o da vista, no meio dela."""
        indice = self._selecionado
        if indice is not None and 0 <= indice < len(self._boxes) and not self.modo_areas:
            b = self._boxes[indice]
            centro = self.mapFromScene((b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2)
            self.menu_do_box(indice, (b.x1 + b.x2) // 2).exec(
                self.viewport().mapToGlobal(centro))
            return
        self.menu_da_vista().exec(self.viewport().mapToGlobal(self.viewport().rect().center()))

    #: As ações da janela (pelo id do YAML) que o menu da vista oferece.
    ACOES_DO_MENU = ("zoom_pagina", "zoom_largura", "zoom_100", "zoom_item", "zoom_mais",
                     "zoom_menos", "mostrar_origem")

    def mostrar_caixa(self, caixa) -> None:
        """Rola a vista até a caixa (da página), a 120 px da borda se couber (Seguir)."""
        x1, y1, x2, y2 = caixa
        self.ensureVisible(QRectF(x1, y1, x2 - x1, y2 - y1), 120, 120)

    def menu_da_vista(self) -> QMenu:
        """O zoom e a origem, das ações que a janela pôs no visor."""
        menu = QMenu(self)
        por_id = {a.objectName(): a for a in self.actions()}
        for id_ in self.ACOES_DO_MENU:
            if id_ in por_id:
                menu.addAction(por_id[id_])
        return menu

    def wheelEvent(self, evento):
        modificadores = evento.modifiers()
        if modificadores & Qt.KeyboardModifier.ControlModifier:
            fator = self.PASSO_DA_RODA if evento.angleDelta().y() > 0 else 1 / self.PASSO_DA_RODA
            self._escalar(self.escala() * fator)        # ancorado no cursor (a âncora da vista)
            return
        if modificadores & Qt.KeyboardModifier.ShiftModifier:
            barra = self.horizontalScrollBar()
            barra.setValue(barra.value() - evento.angleDelta().y())
            return
        super().wheelEvent(evento)
