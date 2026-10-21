"""A Galeria por caractere (SPEC §8.2, passo C): a grade dos recortes de todos os glifos
lidos como um caractere (ou de uma busca por glifo), da página ou do livro, do menos
confiável ao mais, com a leitura embaixo e a página e a confiança na dica.

Pelo teclado: as setas, Shift e Ctrl+A selecionam; **digitar um caractere** o aplica à
seleção (um passo do desfazer, sem ensinar); **Enter** ensina a seleção (uma amostra por
glifo, com a leitura dele); **Shift+Enter** só corrige (a leitura de cada um fica, `manual`,
sem padrão novo). O duplo clique leva ao glifo. Quem edita é a janela (`galeria_na_janela`),
pelo controlador da página; aqui, só o que o usuário pediu.

Os recortes chegam aos poucos (`mostrar_recorte`): a janela os tira das páginas numa thread.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QAbstractListModel, QModelIndex, QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QListView,
                               QVBoxLayout, QWidget)

from abbychess.app.imagens import pixmap_de_cinza

#: O lado do recorte na grade, em pixels.
LADO = 56
ESCOPOS = (("pagina", "Página"), ("livro", "Livro"))


@dataclass
class Item:
    """Um glifo da Galeria."""

    pagina: int
    gid: int
    char: str
    confianca: float
    fonte: str = ""


class ModeloDaGaleria(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.itens: List[Item] = []
        self._figuras: Dict[Tuple[int, int], QPixmap] = {}
        self.recortes: Dict[Tuple[int, int], np.ndarray] = {}

    def mostrar(self, itens) -> None:
        self.beginResetModel()
        self.itens = sorted(itens, key=lambda i: (round(i.confianca, 4), i.pagina, i.gid))
        self._figuras, self.recortes = {}, {}
        self.endResetModel()

    def mostrar_recorte(self, pagina: int, gid: int, recorte: np.ndarray) -> None:
        chave = (pagina, gid)
        self.recortes[chave] = recorte
        figura = pixmap_de_cinza(recorte)
        self._figuras[chave] = figura.scaled(LADO, LADO, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation)
        for linha, item in enumerate(self.itens):
            if (item.pagina, item.gid) == chave:
                indice = self.index(linha)
                self.dataChanged.emit(indice, indice, [Qt.ItemDataRole.DecorationRole])
                break

    def trocar_leitura(self, chaves, char: str) -> None:
        """A leitura nova dos glifos corrigidos (eles ficam na grade, com ela)."""
        chaves = set(chaves)
        for linha, item in enumerate(self.itens):
            if (item.pagina, item.gid) in chaves:
                item.char, item.confianca, item.fonte = char, 1.0, "manual"
                indice = self.index(linha)
                self.dataChanged.emit(indice, indice)

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.itens)

    def data(self, indice, papel=Qt.ItemDataRole.DisplayRole):
        if not indice.isValid() or not 0 <= indice.row() < len(self.itens):
            return None
        item = self.itens[indice.row()]
        if papel == Qt.ItemDataRole.DisplayRole:
            return item.char or "□"
        if papel == Qt.ItemDataRole.DecorationRole:
            return self._figuras.get((item.pagina, item.gid))
        if papel == Qt.ItemDataRole.ToolTipRole:
            fonte = f", {item.fonte}" if item.fonte else ""
            return (f"Página {item.pagina + 1} · '{item.char or '□'}' · "
                    f"confiança {item.confianca:.2f}{fonte}")
        if papel == Qt.ItemDataRole.UserRole:
            return item
        return None


class VistaDaGaleria(QListView):
    """A grade: digitar aplica, Enter ensina, Shift+Enter só corrige, duplo clique vai."""

    aplicar = Signal(str)
    ensinar = Signal()
    so_corrigir = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setIconSize(QSize(LADO, LADO))
        self.setGridSize(QSize(LADO + 16, LADO + 26))
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAccessibleName("Galeria por caractere")

    def keyPressEvent(self, evento):
        tecla, mods, texto = evento.key(), evento.modifiers(), evento.text()
        if tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if mods & Qt.KeyboardModifier.ShiftModifier:
                self.so_corrigir.emit()
            else:
                self.ensinar.emit()
            return
        sem_atalho = not mods & (Qt.KeyboardModifier.ControlModifier
                                 | Qt.KeyboardModifier.AltModifier)
        if sem_atalho and len(texto) == 1 and texto.isprintable() and not texto.isspace():
            self.aplicar.emit(texto)
            return
        super().keyPressEvent(evento)


class PainelDaGaleria(QWidget):
    """O cabeçalho (o caractere, o escopo, a contagem e as teclas) e a grade."""

    #: O escopo escolhido ("pagina" ou "livro").
    escopo_mudou = Signal(str)
    #: O glifo escolhido (duplo clique): o `Item`.
    escolhido = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titulo = QLabel("Galeria: escolha um glifo e abra a Galeria do caractere dele.")
        self.titulo.setWordWrap(True)
        self.escopo = QComboBox()
        self.escopo.setAccessibleName("Galeria: a página ou o livro")
        for valor, rotulo in ESCOPOS:
            self.escopo.addItem(rotulo, valor)
        self.escopo.currentIndexChanged.connect(
            lambda _i: self.escopo_mudou.emit(self.escopo.currentData()))
        self.modelo = ModeloDaGaleria(self)
        self.vista = VistaDaGaleria()
        self.vista.setModel(self.modelo)
        self.vista.doubleClicked.connect(self._escolhido)
        self.dica = QLabel("Digite um caractere: aplica à seleção · Enter ensina · Shift+Enter "
                           "só corrige · Ctrl+A seleciona tudo · duplo clique vai ao glifo")
        self.dica.setWordWrap(True)
        self.dica.setStyleSheet("color: #555;")
        cima = QHBoxLayout()
        cima.addWidget(self.titulo, 1)
        cima.addWidget(self.escopo)
        caixa = QVBoxLayout(self)
        caixa.setContentsMargins(2, 2, 2, 2)
        caixa.addLayout(cima)
        caixa.addWidget(self.vista, 1)
        caixa.addWidget(self.dica)

    def mostrar(self, titulo: str, itens, escopo: Optional[str] = None) -> None:
        if escopo is not None:
            self.escopo.blockSignals(True)
            self.escopo.setCurrentIndex(max(0, self.escopo.findData(escopo)))
            self.escopo.blockSignals(False)
        self.modelo.mostrar(itens)
        self.titulo.setText(f"{titulo}: {len(self.modelo.itens)} glifo(s), do menos confiável "
                            "ao mais")

    def selecionados(self) -> List[Item]:
        return [self.modelo.itens[i.row()] for i in self.vista.selectionModel().selectedIndexes()]

    def _escolhido(self, indice) -> None:
        if indice.isValid():
            self.escolhido.emit(self.modelo.itens[indice.row()])

    def focar(self) -> None:
        self.vista.setFocus(Qt.FocusReason.ShortcutFocusReason)
