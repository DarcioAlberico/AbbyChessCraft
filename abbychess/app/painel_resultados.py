"""Resultados / Avisos (SPEC §3.1): o painel de baixo, que abre por busca, relatório ou ⚠.

Até o passo B, Resultados só mostra o que outros comandos escrevem nele; Avisos mostra o log
persistente do projeto (`abbychess.avisos`): os erros em vermelhão, os avisos em laranja,
o mais novo embaixo. Esc fecha o painel (`fechar_sobreposicao`).
"""

from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QListWidget, QListWidgetItem, QMenu, QTabWidget

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
        for lista in (self.resultados, self.avisos):
            lista.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            lista.customContextMenuRequested.connect(
                lambda ponto, lista=lista: self.menu_de_contexto(lista).exec(
                    lista.viewport().mapToGlobal(ponto)))

    def menu_de_contexto(self, lista: QListWidget) -> QMenu:
        """Copiar a linha (ou todas) e limpar a lista da tela (o log no disco fica)."""
        menu = QMenu(self)
        item = lista.currentItem()
        copiar = menu.addAction("Copiar")
        copiar.setEnabled(item is not None)
        copiar.triggered.connect(lambda: QApplication.clipboard().setText(item.text()))
        todas = menu.addAction("Copiar tudo")
        todas.triggered.connect(lambda: QApplication.clipboard().setText(
            "\n".join(lista.item(n).text() for n in range(lista.count()))))
        limpar = menu.addAction("Limpar a lista")
        limpar.triggered.connect(lista.clear)
        return menu

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
