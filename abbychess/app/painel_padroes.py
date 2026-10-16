"""Os padrões ensinados para este livro, por caractere, com a opção de esquecer.

Ensinar errado acontece: um `l` ensinado como `1` passa a ler errado todas as
repetições dele. Aqui se vê cada amostra de cada caractere e se apaga a ruim.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QPushButton, QSplitter, QVBoxLayout, QWidget)

from abbychess.app.painel_treino import FONTE_DE_SIMBOLOS


class PainelDePadroes(QWidget):
    esquecer = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._padroes: Dict[str, List[Path]] = {}

        self.caracteres = QListWidget()
        self.caracteres.setFont(QFont(FONTE_DE_SIMBOLOS, 12))
        self.caracteres.currentTextChanged.connect(self._mostrar_amostras)

        self.amostras = QListWidget()
        self.amostras.setViewMode(QListWidget.ViewMode.IconMode)
        self.amostras.setIconSize(QSize(48, 48))
        self.amostras.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.amostras.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

        self.botao_esquecer = QPushButton("Esquecer amostras selecionadas")
        self.botao_esquecer.clicked.connect(self._esquecer)
        self.resumo = QLabel("")

        direita = QWidget()
        caixa_direita = QVBoxLayout(direita)
        caixa_direita.setContentsMargins(0, 0, 0, 0)
        caixa_direita.addWidget(self.amostras)
        botoes = QHBoxLayout()
        botoes.addWidget(self.resumo, 1)
        botoes.addWidget(self.botao_esquecer)
        caixa_direita.addLayout(botoes)

        divisor = QSplitter(Qt.Orientation.Horizontal)
        divisor.addWidget(self.caracteres)
        divisor.addWidget(direita)
        divisor.setSizes([140, 400])

        caixa = QVBoxLayout(self)
        caixa.addWidget(divisor)

    def atualizar(self, padroes: Dict[str, List[Path]]) -> None:
        atual = self.caracteres.currentItem()
        escolhido = atual.data(Qt.ItemDataRole.UserRole) if atual else None
        self._padroes = padroes
        self.caracteres.blockSignals(True)
        self.caracteres.clear()
        for char, arquivos in sorted(padroes.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            item = QListWidgetItem(f"{char}    {len(arquivos)}")
            item.setData(Qt.ItemDataRole.UserRole, char)
            self.caracteres.addItem(item)
            if char == escolhido:
                self.caracteres.setCurrentItem(item)
        self.caracteres.blockSignals(False)
        total = sum(len(v) for v in padroes.values())
        self.resumo.setText(f"{total} amostras em {len(padroes)} caracteres")
        self._mostrar_amostras()

    def _mostrar_amostras(self, *_args) -> None:
        self.amostras.clear()
        atual = self.caracteres.currentItem()
        if atual is None:
            return
        for arquivo in self._padroes.get(atual.data(Qt.ItemDataRole.UserRole), []):
            item = QListWidgetItem(QIcon(QPixmap(str(arquivo))), "")
            item.setData(Qt.ItemDataRole.UserRole, str(arquivo))
            item.setToolTip(arquivo.stem)
            self.amostras.addItem(item)

    def _esquecer(self) -> None:
        caminhos = [i.data(Qt.ItemDataRole.UserRole) for i in self.amostras.selectedItems()]
        if caminhos:
            self.esquecer.emit(caminhos)
