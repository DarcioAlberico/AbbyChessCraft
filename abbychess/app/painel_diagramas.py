"""A aba Diagramas da vista direita (SPEC §10): os diagramas do livro numa grade.

Cada item tem o recorte impresso (quando a página está na memória da janela), a posição lida
desenhada e o estado. Os filtros são os da spec (por conferir, lidos sem confiança,
conferidos) e o dos confiáveis pelos lances. Enter ou duplo clique abre o diagrama no editor
Diagrama do Inspetor, com a Imagem enquadrando o impresso.

Os diagramas vêm do disco, fora da interface (`ControladorDeDiagramas.do_livro`); a aba só
desenha e filtra (`estado`, `passa` são puros, testados sem Qt).
"""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Tuple

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QListView, QListWidget,
                               QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

#: Os estados de um diagrama na aba, com o nome que ela mostra.
NAO_LIDO, CONFERIDO, LANCE_ILEGAL = "nao_lido", "conferido", "lance_ilegal"
PELOS_LANCES, SEM_CONFIANCA, CONFIAVEL = "pelos_lances", "sem_confianca", "confiavel"
NOMES = {NAO_LIDO: "não lido", CONFERIDO: "conferido", LANCE_ILEGAL: "lance do texto ilegal",
         PELOS_LANCES: "confiável pelos lances", SEM_CONFIANCA: "lido sem confiança",
         CONFIAVEL: "lido, confiável"}

#: (filtro, nome no seletor), na ordem do seletor.
FILTROS = (("todos", "Todos"), ("por_conferir", "Por conferir"),
           ("sem_confianca", "Lidos sem confiança"), ("pelos_lances", "Confiáveis pelos lances"),
           ("conferidos", "Conferidos"))

#: O lado de cada metade da miniatura (o recorte e o desenho).
LADO_DA_MINIATURA = 96


def estado(d) -> str:
    """O estado do diagrama na aba (um de `NOMES`)."""
    if not d.lido:
        return NAO_LIDO
    if d.conferido:
        return CONFERIDO
    validacao = getattr(d, "validacao", None)
    if validacao is not None and not validacao.confiavel:
        return LANCE_ILEGAL
    if not d.confiavel:
        return SEM_CONFIANCA
    if validacao is not None:
        return PELOS_LANCES
    return CONFIAVEL


def passa(d, filtro: str) -> bool:
    """O diagrama entra no filtro."""
    e = estado(d)
    if filtro == "por_conferir":
        return e != CONFERIDO
    if filtro == "sem_confianca":
        return e in (SEM_CONFIANCA, LANCE_ILEGAL)
    if filtro == "pelos_lances":
        return e == PELOS_LANCES
    if filtro == "conferidos":
        return e == CONFERIDO
    return True


class PainelDeDiagramas(QWidget):
    #: O diagrama escolhido: o índice da página e o do diagrama nela.
    abrir = Signal(int, int)
    #: O botão Atualizar (ou a aba aberta): a janela relê os diagramas do livro.
    atualizar_pedido = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.filtro = QComboBox()
        for chave, nome in FILTROS:
            self.filtro.addItem(nome, chave)
        self.filtro.setCurrentIndex(1)              # por conferir
        self.filtro.setAccessibleName("Filtro dos diagramas")
        self.filtro.currentIndexChanged.connect(lambda _i: self._preencher())
        atualizar = QPushButton("Atualizar")
        atualizar.setToolTip("Relê os diagramas do livro")
        atualizar.clicked.connect(self.atualizar_pedido.emit)
        self.contador = QLabel("")
        topo = QHBoxLayout()
        topo.addWidget(QLabel("Mostrar:"))
        topo.addWidget(self.filtro, 1)
        topo.addWidget(atualizar)

        self.grade = QListWidget()
        self.grade.setViewMode(QListView.ViewMode.IconMode)
        self.grade.setResizeMode(QListView.ResizeMode.Adjust)
        self.grade.setMovement(QListView.Movement.Static)
        self.grade.setIconSize(QSize(2 * LADO_DA_MINIATURA + 4, LADO_DA_MINIATURA))
        self.grade.setSpacing(6)
        self.grade.setWordWrap(True)
        self.grade.setAccessibleName("Diagramas do livro (Enter abre na conferência)")
        self.grade.itemActivated.connect(self._ativado)

        caixa = QVBoxLayout(self)
        caixa.setContentsMargins(4, 4, 4, 4)
        caixa.addLayout(topo)
        caixa.addWidget(self.contador)
        caixa.addWidget(self.grade, 1)

        self._paginas: List[Tuple[int, list]] = []
        self._recorte: Optional[Callable] = None
        self._desenho: Optional[Callable] = None

    # ------------------------------------------------------------------
    def mostrar(self, paginas: Sequence[Tuple[int, list]], recorte: Optional[Callable] = None,
                desenho: Optional[Callable] = None) -> None:
        """[(índice da página, [DiagramaLido])]. `recorte(indice, caixa)` dá a `QImage` do
        impresso ou `None` (a página não está na memória); `desenho(d)`, a da posição."""
        self._paginas = [(i, list(ds)) for i, ds in paginas]
        self._recorte, self._desenho = recorte, desenho
        self._preencher()

    def filtro_atual(self) -> str:
        return self.filtro.currentData()

    def definir_filtro(self, filtro: str) -> None:
        self.filtro.setCurrentIndex(next(k for k, (c, _n) in enumerate(FILTROS) if c == filtro))

    def itens(self) -> List[Tuple[int, int]]:
        """(página, diagrama) dos itens na grade, em ordem."""
        return [self.grade.item(k).data(Qt.ItemDataRole.UserRole)
                for k in range(self.grade.count())]

    def _preencher(self) -> None:
        self.grade.clear()
        filtro = self.filtro_atual()
        total = mostrados = 0
        for pagina, diagramas in self._paginas:
            for k, d in enumerate(diagramas):
                total += 1
                if not passa(d, filtro):
                    continue
                mostrados += 1
                e = estado(d)
                texto = f"p. {pagina + 1} · {k + 1}\n{NOMES[e]}"
                item = QListWidgetItem(self._icone(pagina, d), texto)
                item.setData(Qt.ItemDataRole.UserRole, (pagina, k))
                dica = d.validacao.aviso if e == LANCE_ILEGAL else (d.motivo or NOMES[e])
                item.setToolTip(f"Página {pagina + 1}, diagrama {k + 1}: {dica}")
                self.grade.addItem(item)
        self.contador.setText(f"{mostrados} de {total} diagrama(s)" if total
                              else "Nenhum diagrama lido no livro.")

    def _icone(self, pagina: int, d) -> QIcon:
        lado = LADO_DA_MINIATURA
        tela = QPixmap(2 * lado + 4, lado)
        tela.fill(QColor(255, 255, 255))
        pintor = QPainter(tela)
        recorte = self._recorte(pagina, d.caixa) if self._recorte is not None else None
        if recorte is not None and not recorte.isNull():
            pintor.drawImage(0, 0, recorte.scaled(lado, lado, Qt.AspectRatioMode.KeepAspectRatio,
                                                  Qt.TransformationMode.SmoothTransformation))
        else:
            pintor.fillRect(0, 0, lado, lado, QColor(235, 235, 235))
            pintor.drawText(0, 0, lado, lado, Qt.AlignmentFlag.AlignCenter, "recorte\nna Imagem")
        desenho: Optional[QImage] = self._desenho(d) if self._desenho is not None else None
        if desenho is not None and not desenho.isNull():
            pintor.drawImage(lado + 4, 0, desenho.scaled(
                lado, lado, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        pintor.end()
        return QIcon(tela)

    def _ativado(self, item: QListWidgetItem) -> None:
        pagina, indice = item.data(Qt.ItemDataRole.UserRole)
        self.abrir.emit(pagina, indice)
