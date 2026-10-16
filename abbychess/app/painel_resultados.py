"""Resultados / Avisos (SPEC §3.1): o painel de baixo, que abre por busca, relatório ou ⚠.

Até o passo B, Resultados só mostra o que outros comandos escrevem nele; Avisos mostra o log
persistente do projeto (`abbychess.avisos`): os erros em vermelhão, os avisos em laranja,
o mais novo embaixo. Esc fecha o painel (`fechar_sobreposicao`).
"""

from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QTabWidget

from abbychess import avisos as av
from abbychess.app import estilo


class PainelDeResultados(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.resultados = QListWidget()
        self.resultados.setAccessibleName("Resultados")
        self.avisos = QListWidget()
        self.avisos.setAccessibleName("Avisos e erros do projeto")
        self.avisos.setWordWrap(True)
        self.addTab(self.resultados, "Resultados")
        self.addTab(self.avisos, "Avisos")

    def mostrar_avisos(self, itens: Iterable[av.Aviso]) -> None:
        self.avisos.clear()
        for aviso in itens:
            self.acrescentar(aviso)

    def acrescentar(self, aviso: av.Aviso) -> None:
        item = QListWidgetItem(("⛔ " if aviso.tipo == av.ERRO else "⚠ ") + aviso.linha())
        item.setForeground(estilo.VERMELHAO if aviso.tipo == av.ERRO else estilo.LARANJA.darker(140))
        item.setToolTip(aviso.texto)
        self.avisos.addItem(item)
        self.avisos.scrollToBottom()

    def ir_aos_avisos(self) -> None:
        self.setCurrentWidget(self.avisos)

    def focar(self) -> None:
        self.currentWidget().setFocus(Qt.FocusReason.ShortcutFocusReason)
