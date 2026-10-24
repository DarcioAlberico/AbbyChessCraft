"""A gaveta de Páginas (SPEC §3.1): o livro inteiro numa lista, lida de `livro.json`.

Cada linha tem o número, o estado (§4.4, um símbolo com cor, o nome na dica), os glifos a
revisar e os diagramas por conferir, em 150 px;
as páginas que nunca foram reconhecidas aparecem como "não reconhecida". Enter ou duplo
clique abre a página; a seleção múltipla (Shift, Ctrl) vai para "Reconhecer as
selecionadas" no menu de contexto. O filtro mostra só um estado.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QGroupBox, QHeaderView, QLabel,
                               QMenu, QProgressBar, QPushButton, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from abbychess import modelo as md
from abbychess.livro import SaudeDoLivro
from abbychess.app import estilo

#: O símbolo e a cor de cada estado na coluna estreita (a cor não carrega o sentido sozinha).
SIMBOLOS_DOS_ESTADOS = {
    md.NAO_RECONHECIDA: ("·", estilo.CINZA),
    md.GLIFOS_MARCADOS: ("✎", estilo.ROXO_AVERMELHADO),
    md.RECONHECIDA: ("○", estilo.LARANJA),
    md.EM_REVISAO: ("◐", estilo.VERMELHAO),
    md.VERIFICADA: ("✓", estilo.VERDE_AZULADO),
}

NOMES_DOS_ESTADOS = {
    md.NAO_RECONHECIDA: "não reconhecida",
    md.GLIFOS_MARCADOS: "glifos marcados",
    md.RECONHECIDA: "reconhecida",
    md.EM_REVISAO: "em revisão",
    md.VERIFICADA: "verificada",
}


#: As operações de página do menu de contexto (o texto, o método da janela que pergunta).
OPERACOES_DA_GAVETA = (
    ("Girar à direita", "girar_a_direita"), ("Girar à esquerda", "girar_a_esquerda"),
    ("Girar…", "girar_paginas"), ("Cortar…", "cortar_paginas"),
    ("Tirar o corte…", "tirar_o_corte"), ("Dividir…", "dividir_paginas"),
    ("Endireitar…", "endireitar_paginas"))


class PainelDePaginas(QWidget):
    #: O índice da página a abrir (Enter, duplo clique, "Abrir").
    abrir = Signal(int)
    #: Os índices a reconhecer em lote ("Reconhecer as selecionadas").
    reconhecer = Signal(list)
    #: O livro inteiro, a partir do cartão Saúde do livro.
    reconhecer_livro = Signal()
    #: As operações de página nas selecionadas (§12.4): mover (pergunta o lugar) e apagar.
    mover = Signal(list)
    apagar = Signal(list)
    #: (o método da janela, as posições escolhidas): girar, cortar, dividir, endireitar.
    operacao = Signal(str, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        #: As operações de página valem agora (a janela liga e desliga, como as do menu).
        self.paginas_mudam = True
        self.filtro = QComboBox()
        self.filtro.setAccessibleName("Filtrar as páginas pelo estado")
        self.filtro.addItem("Todas as páginas", None)
        for estado, nome in NOMES_DOS_ESTADOS.items():
            self.filtro.addItem(nome.capitalize(), estado)
        self.filtro.currentIndexChanged.connect(self._filtrar)
        # A largura pelo começo do texto, não pelo item mais longo: a gaveta tem 150 px (§3.1).
        self.filtro.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.filtro.setMinimumContentsLength(8)

        self.lista = QTreeWidget()
        self.lista.setAccessibleName("Páginas do livro")
        self.lista.setRootIsDecorated(False)
        self.lista.setUniformRowHeights(True)
        self.lista.setHeaderLabels(["Pág.", "Est.", "Rev.", "Diag.", "Ach."])
        self.lista.headerItem().setToolTip(1, "O estado da página (passe o mouse no símbolo)")
        self.lista.headerItem().setToolTip(2, "Glifos a revisar")
        self.lista.headerItem().setToolTip(3, "Diagramas por conferir")
        self.lista.headerItem().setToolTip(4, "Ocorrências da busca (Ctrl+F)")
        self.lista.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lista.itemActivated.connect(self._abrir_item)
        self.lista.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lista.customContextMenuRequested.connect(self._menu)
        # As colunas cabem nos 144 px da lista mesmo com a barra vertical (~17 px no Windows):
        # a Pág. fica com o que sobra, e a lista nunca rola na horizontal.
        cabecalho = self.lista.header()
        cabecalho.setStretchLastSection(False)
        cabecalho.setMinimumSectionSize(16)
        cabecalho.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for coluna, largura in enumerate((22, 24, 26, 24), start=1):
            cabecalho.setSectionResizeMode(coluna, QHeaderView.ResizeMode.Fixed)
            self.lista.setColumnWidth(coluna, largura)
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lista.headerItem().setToolTip(0, "A página do livro")
        self.lista.setColumnHidden(4, True)     # só com uma busca (§7.1)
        self._contagem = None

        self.saude = QGroupBox("Saúde do livro")
        caixa_da_saude = QVBoxLayout(self.saude)
        caixa_da_saude.setContentsMargins(6, 6, 6, 6)
        self.amostra_da_saude = QLabel()
        self.pendentes_da_saude = QLabel()
        self.padroes_da_saude = QLabel()
        self.botao_reconhecer_livro = QPushButton("Reconhecer o livro")
        self.botao_reconhecer_livro.clicked.connect(self.reconhecer_livro)
        for widget in (self.amostra_da_saude, self.pendentes_da_saude,
                       self.padroes_da_saude, self.botao_reconhecer_livro):
            caixa_da_saude.addWidget(widget)
        self.saude.hide()

        #: O progresso do lote (passo E): as páginas feitas, e o tempo estimado na dica.
        self.lote = QProgressBar()
        self.lote.setAccessibleName("Progresso do lote")
        self.lote.setTextVisible(True)
        self.lote.setFormat("%v de %m")
        self.lote.hide()

        caixa = QVBoxLayout(self)
        caixa.setContentsMargins(2, 2, 2, 2)
        caixa.addWidget(self.saude)
        caixa.addWidget(self.filtro)
        caixa.addWidget(self.lote)
        caixa.addWidget(self.lista, 1)

    def mostrar_lote(self, feitas: int, total: int, texto: str) -> None:
        self.lote.setRange(0, max(1, total))
        self.lote.setValue(feitas)
        self.lote.setToolTip(texto)
        self.lote.show()

    def esconder_lote(self) -> None:
        self.lote.hide()

    def mostrar_saude(self, saude: SaudeDoLivro) -> None:
        """Mostra o progresso da amostra e destaca quando já vale reconhecer o livro."""
        if not saude.paginas:
            self.saude.hide()
            return
        n = len(saude.paginas)
        self.amostra_da_saude.setText(f"Amostra: {n} página{'s' if n != 1 else ''}")
        self.pendentes_da_saude.setText(
            f"Pendentes: {saude.pendentes_antes} → {saude.pendentes_agora}")
        self.padroes_da_saude.setText(f"Padrões ensinados: {saude.padroes}")
        pronto = saude.pode_reconhecer_o_livro
        self.botao_reconhecer_livro.setDefault(pronto)
        self.botao_reconhecer_livro.setProperty("pronto", pronto)
        self.botao_reconhecer_livro.setToolTip(
            "A amostra atingiu o limiar; reconheça o livro inteiro."
            if pronto else
            f"Revise a amostra até restarem no máximo {saude.limiar} pendentes.")
        self.botao_reconhecer_livro.style().unpolish(self.botao_reconhecer_livro)
        self.botao_reconhecer_livro.style().polish(self.botao_reconhecer_livro)
        self.saude.show()

    # ------------------------------------------------------------------
    def mostrar(self, total: int, resumo: Dict[int, dict], atual: Optional[int]) -> None:
        """As `total` páginas do livro, com o resumo das que estão em `livro.json`. Com o
        mesmo número de páginas, atualiza as linhas no lugar (a seleção e a rolagem ficam);
        `atual` (a página aberta mudou) escolhe a linha dela."""
        self.lista.setUpdatesEnabled(False)
        if self.lista.topLevelItemCount() != total:
            self.lista.clear()
            itens = []
            for i in range(total):
                item = QTreeWidgetItem()
                item.setData(0, Qt.ItemDataRole.UserRole, i)
                for coluna in (0, 2, 3):
                    item.setTextAlignment(coluna, Qt.AlignmentFlag.AlignRight)
                itens.append(item)
            self.lista.addTopLevelItems(itens)
        for i in range(total):
            r = resumo.get(i, {})
            estado = r.get("estado", md.NAO_RECONHECIDA)
            pendentes = r.get("pendentes")
            diagramas = r.get("diagramas_por_conferir", 0)
            item = self.lista.topLevelItem(i)
            simbolo, cor = SIMBOLOS_DOS_ESTADOS.get(estado, ("?", estilo.CINZA))
            cor = estilo.na_interface(cor)
            for coluna, texto in enumerate((str(i + 1), simbolo,
                                            "" if pendentes is None else str(pendentes),
                                            str(diagramas) if diagramas else "")):
                if item.text(coluna) != texto:
                    item.setText(coluna, texto)
            if item.data(1, Qt.ItemDataRole.UserRole) != estado:
                item.setData(1, Qt.ItemDataRole.UserRole, estado)
                item.setToolTip(1, NOMES_DOS_ESTADOS.get(estado, estado))
                item.setForeground(1, cor)
                apagada = estado == md.NAO_RECONHECIDA      # o que ainda não foi lido, atenuado
                if apagada:
                    item.setForeground(0, estilo.cor("texto_secundario"))
                else:                                   # a cor da paleta, que segue o tema
                    item.setData(0, Qt.ItemDataRole.ForegroundRole, None)
        self._pintar_contagem()
        self._filtrar()
        if atual is not None:
            self.marcar_atual(atual)
        self.lista.setUpdatesEnabled(True)

    def esquecer_as_cores(self) -> None:
        """O tema mudou: a próxima atualização pinta de novo a coluna de estado e o número."""
        for i in range(self.lista.topLevelItemCount()):
            self.lista.topLevelItem(i).setData(1, Qt.ItemDataRole.UserRole, None)

    def mostrar_ocorrencias(self, contagem) -> None:
        """A contagem da busca por página (§7.1), na coluna "Ach."; None a esconde."""
        self._contagem = contagem
        self.lista.setColumnHidden(4, contagem is None)
        self._pintar_contagem()

    def _pintar_contagem(self) -> None:
        for i in range(self.lista.topLevelItemCount()):
            item = self.lista.topLevelItem(i)
            n = (self._contagem or {}).get(i, 0)
            if item.text(4) != (str(n) if n else ""):
                item.setText(4, str(n) if n else "")
                item.setTextAlignment(4, Qt.AlignmentFlag.AlignRight)

    def marcar_atual(self, indice: int) -> None:
        """A página aberta fica escolhida (sem abrir de novo)."""
        if 0 <= indice < self.lista.topLevelItemCount():
            item = self.lista.topLevelItem(indice)
            self.lista.setCurrentItem(item)
            self.lista.scrollToItem(item)

    def selecionadas(self) -> List[int]:
        return sorted(i.data(0, Qt.ItemDataRole.UserRole) for i in self.lista.selectedItems())

    def focar(self) -> None:
        self.lista.setFocus(Qt.FocusReason.ShortcutFocusReason)

    # ------------------------------------------------------------------
    def _filtrar(self, *_):
        estado = self.filtro.currentData()
        for n in range(self.lista.topLevelItemCount()):
            item = self.lista.topLevelItem(n)
            item.setHidden(estado is not None and item.data(1, Qt.ItemDataRole.UserRole) != estado)

    def _abrir_item(self, item, _coluna=0) -> None:
        if item is not None:
            self.abrir.emit(item.data(0, Qt.ItemDataRole.UserRole))

    def _menu(self, ponto) -> None:
        menu = self.menu_de_contexto()
        menu.exec(self.lista.viewport().mapToGlobal(ponto))

    def menu_de_contexto(self) -> QMenu:
        menu = QMenu(self)
        item = self.lista.currentItem()
        abrir = menu.addAction("Abrir a página")
        abrir.setEnabled(item is not None)
        abrir.triggered.connect(lambda: self._abrir_item(self.lista.currentItem()))
        selecionadas = self.selecionadas()
        lote = menu.addAction(f"Reconhecer as selecionadas ({len(selecionadas)})")
        lote.setEnabled(bool(selecionadas))
        lote.triggered.connect(lambda: self.reconhecer.emit(self.selecionadas()))
        menu.addSeparator()
        mover = menu.addAction(f"Mover as selecionadas ({len(selecionadas)})…")
        mover.setEnabled(bool(selecionadas) and self.paginas_mudam)
        mover.triggered.connect(lambda: self.mover.emit(self.selecionadas()))
        apagar = menu.addAction(f"Apagar as selecionadas ({len(selecionadas)})…")
        apagar.setEnabled(bool(selecionadas) and self.paginas_mudam)
        apagar.triggered.connect(lambda: self.apagar.emit(self.selecionadas()))
        menu.addSeparator()
        for texto, metodo in OPERACOES_DA_GAVETA:
            acao = menu.addAction(texto)
            acao.setEnabled(bool(selecionadas) and self.paginas_mudam)
            acao.triggered.connect(
                lambda _=False, m=metodo: self.operacao.emit(m, self.selecionadas()))
        return menu
