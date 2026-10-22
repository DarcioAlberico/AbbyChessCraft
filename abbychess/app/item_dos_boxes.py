"""O item que desenha todos os boxes da página (SPEC §3.3, CA-3.4 e CA-3.5).

Um item só na cena, e não um por box: 2.000 itens custavam a montagem da cena a cada
mudança e o percurso deles a cada pintura. O item guarda as caixas numa grade
(`abbychess.grade`) e, ao pintar, desenha só os boxes do retângulo exposto; ao mudar um box,
pede a repintura só do retângulo dele (`update(QRectF)`), com uma folga para o traço.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from PySide6.QtCore import QRectF
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem

from core.box_model import BoxEntry

from abbychess import grade as gd
from abbychess.app import estilo


class ItemDosBoxes(QGraphicsItem):
    """Os boxes da página, num item, com o estado de cada um."""

    #: A folha em volta da caixa repintada, em pixels da página: o traço cosmético passa
    #: um pouco da caixa, e a folga não pode passar de ~20% do lado (CA-3.4: o retângulo
    #: pedido fica em até 2× a caixa).
    FOLGA_MAXIMA = 3.0

    def __init__(self, largura: float, altura: float):
        super().__init__()
        self._limites = QRectF(0, 0, largura, altura)
        self.grade = gd.GradeDeCaixas()
        self.estados: List[str] = []
        self.mostrar_origem = False
        self._canetas: Dict[Tuple[str, bool], Tuple[QPen, Optional[QBrush]]] = {}
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption)

    # ------------------------------------------------------------------
    def boundingRect(self) -> QRectF:
        return self._limites

    def trocar(self, boxes: Sequence[BoxEntry], estados: Sequence[str]) -> None:
        """Todos os boxes de novo (a página mudou, um box entrou ou saiu)."""
        self.grade.trocar([(b.x1, b.y1, b.x2, b.y2) for b in boxes])
        self.estados = list(estados)
        self.update()

    def atualizar(self, estados: Dict[int, str], boxes: Sequence[BoxEntry]) -> None:
        """Só os boxes de `estados` (índice -> estado novo) mudaram: a leitura ou a caixa;
        a lista é a mesma."""
        for i, estado_novo in estados.items():
            velha = self.grade.caixas[i]
            b = boxes[i]
            nova = (b.x1, b.y1, b.x2, b.y2)
            if nova != velha:
                self.update(self._retangulo(velha))
                self.grade.mover(i, nova)
            self.estados[i] = estado_novo
            self.update(self._retangulo(nova))

    def definir_origem(self, sim: bool) -> None:
        if sim != self.mostrar_origem:
            self.mostrar_origem = sim
            self.update()

    def no_ponto(self, x: float, y: float) -> Optional[int]:
        return self.grade.no_ponto(x, y)

    # ------------------------------------------------------------------
    def _retangulo(self, caixa) -> QRectF:
        x1, y1, x2, y2 = caixa
        folga = min(self.FOLGA_MAXIMA, 0.2 * max(1, min(x2 - x1, y2 - y1)))
        return QRectF(x1 - folga, y1 - folga, x2 - x1 + 2 * folga, y2 - y1 + 2 * folga)

    def _caneta(self, estado: str) -> Tuple[QPen, Optional[QBrush]]:
        chave = (estado, self.mostrar_origem)
        if chave not in self._canetas:
            t = estilo.traco(estado, self.mostrar_origem)
            caneta = QPen(t.cor)
            caneta.setCosmetic(True)
            caneta.setWidthF(t.largura)
            caneta.setStyle(t.estilo)
            if t.padrao:
                caneta.setDashPattern(list(t.padrao))
            pincel = None
            if t.preenchimento:
                cor = QColor(t.cor)
                cor.setAlpha(t.preenchimento)
                pincel = QBrush(cor)
            self._canetas[chave] = (caneta, pincel)
        return self._canetas[chave]

    #: Metade do traço mais largo (o "sem leitura", 2,6 px) e 1 px, em pixels da tela: um box
    #: fora do retângulo exposto por menos que isso ainda pinta dentro dele.
    ALCANCE_DO_TRACO = 2.3

    def paint(self, pintor: QPainter, opcao: QStyleOptionGraphicsItem, widget=None) -> None:
        exposto = opcao.exposedRect if opcao is not None else self._limites
        escala = max(abs(pintor.worldTransform().m11()), 1e-6)
        alcance = self.ALCANCE_DO_TRACO / escala          # em pixels da página
        indices = self.grade.no_retangulo(exposto.left() - alcance, exposto.top() - alcance,
                                          exposto.right() + alcance, exposto.bottom() + alcance)
        por_estado: Dict[str, List[int]] = {}
        for i in indices:
            por_estado.setdefault(self.estados[i], []).append(i)
        caixas = self.grade.caixas
        # Em zoom baixo o preenchimento cobriria a letra (revisão do A2): só o contorno.
        sem_preenchimento = escala < estilo.ZOOM_SEM_PREENCHIMENTO
        for estado, lista in por_estado.items():
            caneta, pincel = self._caneta(estado)
            if sem_preenchimento:
                pincel = None
            pintor.setPen(caneta)
            pintor.setBrush(pincel if pincel is not None else QBrush())
            pintor.drawRects([QRectF(c[0], c[1], c[2] - c[0], c[3] - c[1])
                              for c in (caixas[i] for i in lista)])
