"""Resultados / Avisos (SPEC §3.1): o painel de baixo, que abre por busca, relatório ou ⚠.

Resultados mostra o que a busca (passo B) manda para ele: uma linha por ocorrência, com a
página, a linha e o trecho, o casamento em negrito (Enter ou duplo clique leva até ele), ou
os glifos da busca por glifo. A prévia da substituição (passo D2) mostra todos os casos,
cada um com a caixa de marcar (antes → depois, prosa ou notação; os que ainda não têm
tradução, desmarcados e desabilitados, com o motivo na dica): Espaço marca ou desmarca os
selecionados (Shift e Ctrl+A selecionam vários), Enter ou "Aplicar N" aplica os marcados, e
Shift+Enter ou o duplo clique leva ao caso. Avisos mostra o log persistente do projeto
(`abbychess.avisos`): os erros em vermelhão, os avisos em laranja, o mais novo embaixo. Esc
fecha o painel (`fechar_sobreposicao`).
"""

from __future__ import annotations

import html
from typing import Iterable, Sequence

from PySide6.QtCore import QAbstractListModel, QModelIndex, QSize, Qt, Signal
from PySide6.QtGui import QAbstractTextDocumentLayout, QPalette, QTextDocument
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QLabel, QListView,
                               QListWidget, QListWidgetItem, QMenu, QPushButton, QStyle,
                               QStyledItemDelegate, QStyleOptionViewItem, QTabWidget,
                               QVBoxLayout, QWidget)

from abbychess import avisos as av
from abbychess.app import estilo


#: O papel do HTML de cada linha de Resultados (o texto simples fica no papel de exibição,
#: para copiar e para o leitor de tela).
PAPEL_DO_HTML = Qt.ItemDataRole.UserRole + 1
#: O papel do que a linha leva (uma ocorrência ou um glifo achado).
PAPEL_DO_ALVO = Qt.ItemDataRole.UserRole + 2
#: Quantas linhas Resultados mostra de uma busca (o resto fica na contagem).
LIMITE_DE_LINHAS = 2000



#: O tipo do aviso no item da lista (para repintar quando o tema muda).
PAPEL_DO_TIPO = Qt.ItemDataRole.UserRole + 20


def _cor_do_aviso(tipo: str):
    return estilo.cor("erro") if tipo == av.ERRO else estilo.cor("aviso")

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
        self.resultados = QListWidget()
        self.resultados.setAccessibleName("Resultados")
        self.resultados.setItemDelegate(_DelegadoHtml(self.resultados))
        self.resultados.setUniformItemSizes(True)   # 2.000 linhas sem medir cada uma
        self.resultados.itemActivated.connect(self._ativado)
        # A prévia da substituição: todos os casos (um modelo, sem limite de linhas).
        self.cabecalho_da_previa = QLabel()
        self.cabecalho_da_previa.setWordWrap(True)
        self.botao_aplicar = QPushButton("Aplicar")
        self.botao_aplicar.setAccessibleName("Aplicar a substituição dos casos marcados")
        self.botao_aplicar.clicked.connect(self._aplicar)
        self.modelo_da_previa = ModeloDaPrevia(self)
        self.modelo_da_previa.marcas_mudaram.connect(self._marcado)
        self.previa = _VistaDaPrevia(self)
        self.previa.setModel(self.modelo_da_previa)
        aba = QWidget()
        caixa = QVBoxLayout(aba)
        caixa.setContentsMargins(0, 0, 0, 0)
        caixa.setSpacing(2)
        for w in (self.cabecalho_da_previa, self.botao_aplicar, self.previa, self.resultados):
            caixa.addWidget(w)
        self._mostrar_a_previa(False)
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
        item.setData(PAPEL_DO_TIPO, aviso.tipo)
        item.setForeground(_cor_do_aviso(aviso.tipo))
        item.setToolTip(aviso.texto)
        self.avisos.addItem(item)
        self.avisos.scrollToBottom()

    def repintar(self) -> None:
        """O tema mudou: os avisos na cor do tema novo."""
        for i in range(self.avisos.count()):
            item = self.avisos.item(i)
            item.setForeground(_cor_do_aviso(item.data(PAPEL_DO_TIPO)))

    def _ativado(self, item: QListWidgetItem) -> None:
        alvo = item.data(PAPEL_DO_ALVO)
        if alvo is not None:
            self.escolhido.emit(alvo)

    def _mostrar_a_previa(self, sim: bool) -> None:
        for w in (self.cabecalho_da_previa, self.botao_aplicar, self.previa):
            w.setVisible(sim)
        self.resultados.setVisible(not sim)

    def _limpar(self) -> None:
        self.modelo_da_previa.mostrar([])
        self._mostrar_a_previa(False)
        self.resultados.clear()

    def limpar_previa(self, aviso: str = "") -> None:
        """A prévia sai (outra substituição mudou as páginas); `aviso` fica em Resultados."""
        if self.na_previa:
            self._limpar()
            if aviso:
                self.resultados.addItem(aviso)

    def mostrar_previa(self, previas: Sequence, cabecalho: str) -> None:
        """A prévia da substituição: todos os casos, um por linha, marcados (os sem
        tradução, desmarcados e desabilitados), e o botão "Aplicar N"."""
        self.resultados.clear()
        self.cabecalho_da_previa.setText(cabecalho)
        self.modelo_da_previa.mostrar([c for p in previas for c in p.casos])
        self._mostrar_a_previa(True)
        self._marcado()
        self.setCurrentWidget(self.aba_de_resultados)

    def casos_marcados(self) -> dict:
        """Página -> os casos marcados na prévia (todos, também os fora da tela)."""
        marcados: dict = {}
        for caso in self.modelo_da_previa.marcados():
            marcados.setdefault(caso.pagina, []).append(caso)
        return marcados

    def _marcado(self, *_):
        if self.na_previa:
            n = self.modelo_da_previa.quantos_marcados()
            self.botao_aplicar.setText(f"Aplicar {n} (Enter)")
            self.botao_aplicar.setEnabled(n > 0)

    def _aplicar(self) -> None:
        marcados = self.casos_marcados()
        if marcados:
            self._limpar()
            self.aplicar_previa.emit(marcados)

    def _ir_ao_caso(self, indice: QModelIndex) -> None:
        caso = self.modelo_da_previa.caso(indice.row()) if indice.isValid() else None
        if caso is not None:
            self.escolhido.emit(caso)

    @property
    def na_previa(self) -> bool:
        return self.modelo_da_previa.rowCount() > 0 and not self.previa.isHidden()

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
            secundario = estilo.hex_de("texto_secundario")
            item.setData(PAPEL_DO_HTML, f"<span style='color:{secundario}'>{local}:</span> "
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
        if self.currentWidget() is not self.aba_de_resultados:
            alvo = self.avisos
        else:
            alvo = self.previa if self.na_previa else self.resultados
        alvo.setFocus(Qt.FocusReason.ShortcutFocusReason)


class ModeloDaPrevia(QAbstractListModel):
    """Os casos da prévia e a marca de cada um (sem um item Qt por caso: 28 mil casos
    mostram na hora)."""

    marcas_mudaram = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._casos: list = []
        self._marcas = bytearray()

    def mostrar(self, casos) -> None:
        self.beginResetModel()
        self._casos = list(casos)
        self._marcas = bytearray(1 if c.aplicavel else 0 for c in self._casos)
        self.endResetModel()

    def caso(self, linha: int):
        return self._casos[linha] if 0 <= linha < len(self._casos) else None

    def marcados(self):
        return [c for c, m in zip(self._casos, self._marcas) if m]

    def quantos_marcados(self) -> int:
        return sum(self._marcas)

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._casos)

    def data(self, indice, papel=Qt.ItemDataRole.DisplayRole):
        from abbychess import busca as bs

        caso = self.caso(indice.row())
        if caso is None:
            return None
        if papel == Qt.ItemDataRole.DisplayRole:
            onde = "notação" if caso.etiqueta == bs.NOTACAO else "prosa"
            return (f"p. {caso.pagina + 1}, l. {caso.linha} · {onde}: "
                    f"{caso.antes} → {caso.depois}")
        if papel == Qt.ItemDataRole.CheckStateRole:
            return (Qt.CheckState.Checked if self._marcas[indice.row()]
                    else Qt.CheckState.Unchecked)
        if papel == Qt.ItemDataRole.ToolTipRole and not caso.aplicavel:
            return f"Sem tradução ainda: {caso.motivo}"
        if papel == PAPEL_DO_ALVO:
            return caso
        return None

    def flags(self, indice):
        caso = self.caso(indice.row())
        if caso is None:
            return Qt.ItemFlag.NoItemFlags
        if not caso.aplicavel:
            return Qt.ItemFlag.ItemIsSelectable    # à vista, sem marcar
        return (Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable)

    def setData(self, indice, valor, papel=Qt.ItemDataRole.EditRole) -> bool:
        if papel != Qt.ItemDataRole.CheckStateRole:
            return False
        marcado = Qt.CheckState(valor) == Qt.CheckState.Checked
        return self.marcar([indice.row()], marcado)

    def marcar(self, linhas, marcado: bool) -> bool:
        mudou = False
        for linha in linhas:
            caso = self.caso(linha)
            if caso is not None and caso.aplicavel and bool(self._marcas[linha]) != marcado:
                self._marcas[linha] = 1 if marcado else 0
                mudou = True
        if mudou:
            linhas = sorted(linhas)
            self.dataChanged.emit(self.index(linhas[0]), self.index(linhas[-1]),
                                  [Qt.ItemDataRole.CheckStateRole])
            self.marcas_mudaram.emit()
        return mudou


class _VistaDaPrevia(QListView):
    """A lista da prévia: Espaço marca ou desmarca os selecionados, Enter aplica, Shift+Enter
    (e o duplo clique) leva ao caso."""

    def __init__(self, painel: "PainelDeResultados"):
        super().__init__()
        self._painel = painel
        self.setAccessibleName("Prévia da substituição")
        self.setUniformItemSizes(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.doubleClicked.connect(painel._ir_ao_caso)

    def keyPressEvent(self, evento):
        tecla, mods = evento.key(), evento.modifiers()
        if tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if mods & Qt.KeyboardModifier.ShiftModifier:
                self._painel._ir_ao_caso(self.currentIndex())
            elif self._painel.botao_aplicar.isEnabled():
                self._painel._aplicar()
            return
        if tecla == Qt.Key.Key_Space:
            linhas = sorted({i.row() for i in self.selectedIndexes()}
                            or ({self.currentIndex().row()} if self.currentIndex().isValid()
                                else set()))
            modelo = self._painel.modelo_da_previa
            marcados = [modelo._marcas[k] for k in linhas if modelo.caso(k).aplicavel]
            modelo.marcar(linhas, not all(marcados) if marcados else True)
            return
        super().keyPressEvent(evento)
