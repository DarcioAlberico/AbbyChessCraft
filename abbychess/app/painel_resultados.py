"""Resultados / Avisos (SPEC §3.1): o painel de baixo, que abre por busca, relatório ou ⚠.

Resultados mostra o que a busca (passo B) manda para ele: uma linha por ocorrência, com a
página, a linha e o trecho, o casamento em negrito (Enter ou duplo clique leva até ele), ou
os glifos da busca por glifo. A prévia da substituição (passo D2) põe uma caixa de marcar em
cada caso (antes → depois, prosa ou notação; os que ainda não têm tradução, desmarcados e
desabilitados, com o motivo na dica) e o botão "Aplicar N" (Enter); o duplo clique leva ao
caso. Avisos mostra o log persistente do projeto
(`abbychess.avisos`): os erros em vermelhão, os avisos em laranja, o mais novo embaixo. Esc
fecha o painel (`fechar_sobreposicao`).
"""

from __future__ import annotations

import html
from typing import Iterable, Sequence

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAbstractTextDocumentLayout, QPalette, QTextDocument
from PySide6.QtWidgets import (QApplication, QListWidget, QListWidgetItem, QMenu,
                               QPushButton, QStyle, QStyledItemDelegate, QStyleOptionViewItem,
                               QTabWidget, QVBoxLayout, QWidget)

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
    #: O aviso escolhido que cita uma página (e o ponto de um glifo): (página, x, y).
    aviso_escolhido = Signal(int, object, object)
    #: "Aplicar N" na prévia da substituição: página -> os casos marcados.
    aplicar_previa = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.resultados = _ListaDeResultados(self)
        self.resultados.setAccessibleName("Resultados")
        self.resultados.setItemDelegate(_DelegadoHtml(self.resultados))
        self.resultados.setUniformItemSizes(True)   # 2.000 linhas sem medir cada uma
        self.resultados.itemActivated.connect(self._ativado)
        self.resultados.itemChanged.connect(self._marcado)
        self.botao_aplicar = QPushButton("Aplicar")
        self.botao_aplicar.setAccessibleName("Aplicar a substituição dos casos marcados")
        self.botao_aplicar.clicked.connect(self._aplicar)
        self.botao_aplicar.hide()
        self._na_previa = False
        aba = QWidget()
        caixa = QVBoxLayout(aba)
        caixa.setContentsMargins(0, 0, 0, 0)
        caixa.setSpacing(2)
        caixa.addWidget(self.botao_aplicar)
        caixa.addWidget(self.resultados)
        self.avisos = QListWidget()
        self.avisos.setAccessibleName("Avisos e erros do projeto")
        self.avisos.setWordWrap(True)
        self.aba_de_resultados = aba
        self.addTab(aba, "Resultados")
        self.addTab(self.avisos, "Avisos")
        self.avisos.itemActivated.connect(self._aviso_ativado)
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

    def _limpar(self) -> None:
        self._na_previa = False
        self.botao_aplicar.hide()
        self.resultados.clear()

    def mostrar_previa(self, previas: Sequence, cabecalho: str) -> None:
        """A prévia da substituição: um caso por linha, marcado (os sem tradução,
        desmarcados e desabilitados), e o botão "Aplicar N"."""
        from abbychess import busca as bs

        self._limpar()
        self.resultados.blockSignals(True)
        self.resultados.addItem(cabecalho)
        linhas = 0
        for previa in previas:
            for caso in previa.casos:
                if linhas == LIMITE_DE_LINHAS:
                    break
                linhas += 1
                onde = "notação" if caso.etiqueta == bs.NOTACAO else "prosa"
                item = QListWidgetItem(f"p. {caso.pagina + 1}, l. {caso.linha} · {onde}: "
                                       f"{caso.antes} → {caso.depois}")
                item.setData(PAPEL_DO_ALVO, caso)
                if caso.aplicavel:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(Qt.CheckState.Checked)
                else:
                    item.setFlags((item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                                  & ~Qt.ItemFlag.ItemIsEnabled)
                    item.setCheckState(Qt.CheckState.Unchecked)
                    item.setToolTip(f"Sem tradução ainda: {caso.motivo}")
                self.resultados.addItem(item)
        total = sum(len(p.casos) for p in previas)
        if total > linhas:
            self.resultados.addItem(f"… e mais {total - linhas} (refine a busca; só os "
                                    "mostrados são aplicados)")
        self.resultados.blockSignals(False)
        self._na_previa = True
        self.botao_aplicar.show()
        self._marcado()
        self.setCurrentWidget(self.aba_de_resultados)

    def casos_marcados(self) -> dict:
        """Página -> os casos marcados na prévia."""
        marcados: dict = {}
        if not self._na_previa:
            return marcados
        for n in range(self.resultados.count()):
            item = self.resultados.item(n)
            caso = item.data(PAPEL_DO_ALVO)
            if caso is not None and item.checkState() == Qt.CheckState.Checked:
                marcados.setdefault(caso.pagina, []).append(caso)
        return marcados

    def _marcado(self, *_):
        if self._na_previa:
            n = sum(len(c) for c in self.casos_marcados().values())
            self.botao_aplicar.setText(f"Aplicar {n} (Enter)")
            self.botao_aplicar.setEnabled(n > 0)

    def _aplicar(self) -> None:
        marcados = self.casos_marcados()
        if marcados:
            self._limpar()
            self.aplicar_previa.emit(marcados)

    @property
    def na_previa(self) -> bool:
        return self._na_previa

    def mostrar_ocorrencias(self, ocorrencias: Sequence, cabecalho: str) -> None:
        """As ocorrências da busca, uma por linha: "p. 12, l. 3: …trecho…", o casamento em
        negrito; `cabecalho` em cima (a contagem, as páginas que ficaram fora)."""
        self._limpar()
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
        self.setCurrentWidget(self.aba_de_resultados)

    def _aviso_ativado(self, item: QListWidgetItem) -> None:
        from abbychess.app.busca_na_janela import lugar_do_aviso

        lugar = lugar_do_aviso(item.toolTip() or item.text())
        if lugar is not None:
            self.aviso_escolhido.emit(*lugar)

    def mostrar_glifos(self, glifos: Sequence, cabecalho: str, nomes=None) -> None:
        """Os glifos da busca por glifo (até a Galeria do passo C); `nomes`, o nome de cada
        grupo de fonte."""
        from abbychess import busca as bs

        self._limpar()
        self.resultados.addItem(cabecalho)
        for g in glifos[:LIMITE_DE_LINHAS]:
            grupo = bs.grupo_da_fonte(g.fonte)
            fonte = (nomes or {}).get(grupo, grupo)
            item = QListWidgetItem(f"p. {g.pagina + 1}: '{g.char or '□'}', {fonte.lower()}, "
                                   f"confiança {g.confianca:.2f}")
            item.setData(PAPEL_DO_ALVO, g)
            self.resultados.addItem(item)
        if len(glifos) > LIMITE_DE_LINHAS:
            self.resultados.addItem(f"… e mais {len(glifos) - LIMITE_DE_LINHAS}")
        self.setCurrentWidget(self.aba_de_resultados)

    def ir_aos_avisos(self) -> None:
        self.setCurrentWidget(self.avisos)

    def focar(self) -> None:
        alvo = self.resultados if self.currentWidget() is self.aba_de_resultados else self.avisos
        alvo.setFocus(Qt.FocusReason.ShortcutFocusReason)


class _ListaDeResultados(QListWidget):
    """A lista de Resultados: na prévia da substituição, Enter aplica (§7.2), e o duplo
    clique continua levando ao caso."""

    def __init__(self, painel: "PainelDeResultados"):
        super().__init__()
        self._painel = painel

    def keyPressEvent(self, evento):
        if (evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._painel.na_previa
                and self._painel.botao_aplicar.isEnabled()):
            self._painel._aplicar()
            return
        super().keyPressEvent(evento)
