"""Resultados / Avisos (SPEC §3.1): o painel de baixo, que abre por busca, relatório ou ⚠.

Resultados mostra o que a busca (passo B) manda para ele: uma linha por ocorrência, com a
página, a linha e o trecho, o casamento em negrito (Enter ou duplo clique leva até ele), ou
os glifos da busca por glifo. Avisos mostra o log persistente do projeto
(`abbychess.avisos`): os erros em vermelhão, os avisos em laranja, o mais novo embaixo. Esc
fecha o painel (`fechar_sobreposicao`).
"""

from __future__ import annotations

import html
from typing import Iterable, Sequence

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAbstractTextDocumentLayout, QPalette, QTextDocument
from PySide6.QtWidgets import (QApplication, QListWidget, QListWidgetItem, QMenu, QStyle,
                               QStyledItemDelegate, QStyleOptionViewItem, QTabWidget)

from abbychess import avisos as av
from abbychess.app import estilo


#: O papel do HTML de cada linha de Resultados (o texto simples fica no papel de exibição,
#: para copiar e para o leitor de tela).
PAPEL_DO_HTML = Qt.ItemDataRole.UserRole + 1
#: O papel do que a linha leva (uma ocorrência ou um glifo achado).
PAPEL_DO_ALVO = Qt.ItemDataRole.UserRole + 2
#: Quantas linhas Resultados mostra de uma busca (o resto fica na contagem).
LIMITE_DE_LINHAS = 2000


class _DelegadoHtml(QStyledItemDelegate):
    """Desenha a linha pelo HTML dela (o casamento em negrito)."""

    def _documento(self, option, index) -> QTextDocument:
        documento = QTextDocument()
        documento.setDefaultFont(option.font)
        documento.setHtml(index.data(PAPEL_DO_HTML) or html.escape(index.data() or ""))
        return documento

    def paint(self, painter, option, index):
        if not index.data(PAPEL_DO_HTML):
            super().paint(painter, option, index)
            return
        opcao = QStyleOptionViewItem(option)
        self.initStyleOption(opcao, index)
        documento = self._documento(opcao, index)
        opcao.text = ""
        estilo_ = opcao.widget.style() if opcao.widget else QApplication.style()
        estilo_.drawControl(QStyle.ControlElement.CE_ItemViewItem, opcao, painter, opcao.widget)
        contexto = QAbstractTextDocumentLayout.PaintContext()
        if opcao.state & QStyle.StateFlag.State_Selected:
            contexto.palette.setColor(QPalette.ColorRole.Text,
                                      opcao.palette.color(QPalette.ColorRole.HighlightedText))
        painter.save()
        painter.translate(opcao.rect.topLeft())
        painter.setClipRect(opcao.rect.translated(-opcao.rect.topLeft()))
        documento.documentLayout().draw(painter, contexto)
        painter.restore()

    def sizeHint(self, option, index):
        if not index.data(PAPEL_DO_HTML):
            return super().sizeHint(option, index)
        documento = self._documento(option, index)
        return QSize(int(documento.idealWidth()), int(documento.size().height()))


class PainelDeResultados(QTabWidget):
    #: A linha escolhida (Enter, duplo clique): a ocorrência ou o glifo achado dela.
    escolhido = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.resultados = QListWidget()
        self.resultados.setAccessibleName("Resultados")
        self.resultados.setItemDelegate(_DelegadoHtml(self.resultados))
        self.resultados.itemActivated.connect(self._ativado)
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

    def _ativado(self, item: QListWidgetItem) -> None:
        alvo = item.data(PAPEL_DO_ALVO)
        if alvo is not None:
            self.escolhido.emit(alvo)

    def mostrar_ocorrencias(self, ocorrencias: Sequence, cabecalho: str) -> None:
        """As ocorrências da busca, uma por linha: "p. 12, l. 3: …trecho…", o casamento em
        negrito; `cabecalho` em cima (a contagem, as páginas que ficaram fora)."""
        self.resultados.clear()
        self.resultados.addItem(cabecalho)
        for o in ocorrencias[:LIMITE_DE_LINHAS]:
            tamanho = o.fim - o.inicio
            antes = o.trecho[max(0, o.coluna - 60):o.coluna]
            casado = o.trecho[o.coluna:o.coluna + tamanho]
            depois = o.trecho[o.coluna + tamanho:o.coluna + tamanho + 60]
            local = f"p. {o.pagina + 1}, l. {o.linha}"
            item = QListWidgetItem(f"{local}: {antes}{casado}{depois}")
            item.setData(PAPEL_DO_HTML, f"<span style='color:gray'>{local}:</span> "
                                        f"{html.escape(antes)}<b>{html.escape(casado)}</b>"
                                        f"{html.escape(depois)}")
            item.setData(PAPEL_DO_ALVO, o)
            self.resultados.addItem(item)
        if len(ocorrencias) > LIMITE_DE_LINHAS:
            self.resultados.addItem(f"… e mais {len(ocorrencias) - LIMITE_DE_LINHAS} "
                                    "(refine a busca)")
        self.setCurrentWidget(self.resultados)

    def mostrar_glifos(self, glifos: Sequence, cabecalho: str) -> None:
        """Os glifos da busca por glifo (até a Galeria do passo C)."""
        self.resultados.clear()
        self.resultados.addItem(cabecalho)
        for g in glifos[:LIMITE_DE_LINHAS]:
            item = QListWidgetItem(f"p. {g.pagina + 1}: '{g.char or '□'}', fonte {g.fonte or 'aguardando'}, "
                                   f"confiança {g.confianca:.2f} (glifo {g.gid & 0xFFFFF})")
            item.setData(PAPEL_DO_ALVO, g)
            self.resultados.addItem(item)
        if len(glifos) > LIMITE_DE_LINHAS:
            self.resultados.addItem(f"… e mais {len(glifos) - LIMITE_DE_LINHAS}")
        self.setCurrentWidget(self.resultados)

    def ir_aos_avisos(self) -> None:
        self.setCurrentWidget(self.avisos)

    def focar(self) -> None:
        self.currentWidget().setFocus(Qt.FocusReason.ShortcutFocusReason)
