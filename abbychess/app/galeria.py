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
                               QMenu, QVBoxLayout, QWidget)

from abbychess.app.imagens import pixmap_de_cinza
from abbychess.app import estilo, teclado

#: O lado do recorte na grade, em pixels.
LADO = 56
ESCOPOS = (("pagina", "Página"), ("livro", "Livro"))
_QUADRO_VAZIO: List[QPixmap] = []
#: As teclas da grade, embaixo dela.
DICA = ("Digite um caractere: aplica à seleção · Enter ensina · Shift+Enter só corrige · "
        "Ctrl+A seleciona tudo · duplo clique vai ao glifo")
#: O estado vazio (§13): o que fazer para a Galeria mostrar algo; `{foco_vista}` é a tecla
#: do perfil que chega às abas da vista direita.
VAZIA = ("Galeria vazia: escolha um glifo na Imagem ou no Documento e abra esta aba "
         "({foco_vista} chega às abas; ou Editar › Galeria do caractere) para ver todos os "
         "glifos lidos como ele.")


def _vazio() -> QPixmap:
    """O quadro transparente do tamanho do recorte (um só, criado depois da QApplication)."""
    if not _QUADRO_VAZIO:
        quadro = QPixmap(LADO, LADO)
        quadro.fill(estilo.TRANSPARENTE)
        _QUADRO_VAZIO.append(quadro)
    return _QUADRO_VAZIO[0]


@dataclass
class Item:
    """Um glifo da Galeria."""

    pagina: int
    gid: int
    char: str
    confianca: float
    fonte: str = ""


def _dica_do_item(item: Item) -> str:
    """A dica da célula: a página, a leitura, a confiança e a fonte."""
    fonte = f", {item.fonte}" if item.fonte else ""
    return f"Página {item.pagina + 1} · '{item.char or '□'}' · confiança {item.confianca:.2f}{fonte}"


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

    def atualizar_leituras(self, leituras) -> None:
        """As leituras de agora ((página, gid) -> (char, confiança, fonte)), depois de um
        desfazer ou de um refazer; os glifos que sumiram da página saem da grade."""
        mudou = False
        for item in list(self.itens):
            chave = (item.pagina, item.gid)
            if chave not in leituras:
                continue
            leitura = leituras[chave]
            if leitura is None:
                mudou = True
                continue
            if (item.char, item.confianca, item.fonte) != leitura:
                item.char, item.confianca, item.fonte = leitura
                mudou = True
        if mudou:
            self.beginResetModel()
            self.itens = [i for i in self.itens if leituras.get((i.pagina, i.gid), ()) is not None]
            self.endResetModel()

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
            # Até o recorte chegar (numa thread), um quadro vazio do mesmo tamanho: a grade
            # mede a célula pelo primeiro item, e sem ele as células saíam cortadas.
            return self._figuras.get((item.pagina, item.gid), _vazio())
        if papel == Qt.ItemDataRole.SizeHintRole:
            return QSize(LADO + 12, LADO + 22)
        if papel == Qt.ItemDataRole.ToolTipRole:
            return _dica_do_item(item)
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
        self.titulo = QLabel(teclado.com_teclas(VAZIA))
        teclado.quando_mudar(self._refazer_o_vazio)     # o estado vazio cita a tecla do perfil
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
        self.vista.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.vista.customContextMenuRequested.connect(
            lambda ponto: self.menu_de_contexto().exec(self.vista.viewport().mapToGlobal(ponto)))
        self.dica = QLabel(DICA)
        self.dica.setWordWrap(True)
        estilo.papel(self.dica, "dica")
        # Quantos a próxima tecla vai mudar: o número da seleção, à frente da dica.
        self.vista.selectionModel().selectionChanged.connect(self._contar_selecao)
        self.modelo.modelReset.connect(self._contar_selecao)
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

    def _refazer_o_vazio(self) -> None:
        if not self.modelo.itens:
            self.titulo.setText(teclado.com_teclas(VAZIA))

    def selecionados(self) -> List[Item]:
        return [self.modelo.itens[i.row()] for i in self.vista.selectionModel().selectedIndexes()]

    def _contar_selecao(self, *_args) -> None:
        n = len(self.vista.selectionModel().selectedIndexes())
        self.dica.setText(f"{n} selecionado(s) · {DICA}" if n else DICA)

    def _escolhido(self, indice) -> None:
        if indice.isValid():
            self.escolhido.emit(self.modelo.itens[indice.row()])

    def menu_de_contexto(self) -> QMenu:
        """O que as teclas da grade fazem (§3.2), para o mouse: ir, ensinar, só corrigir, os
        símbolos, selecionar tudo e o outro escopo."""
        menu = QMenu(self)
        n = len(self.selecionados())
        ir = menu.addAction("Ir ao glifo")
        ir.setEnabled(self.vista.currentIndex().isValid())
        ir.triggered.connect(lambda: self._escolhido(self.vista.currentIndex()))
        menu.addSeparator()
        for texto, sinal in ((f"Ensinar as selecionadas ({n})", self.vista.ensinar),
                             (f"Só corrigir as selecionadas ({n})", self.vista.so_corrigir)):
            acao = menu.addAction(texto)
            acao.setEnabled(bool(n))
            acao.triggered.connect(sinal.emit)
        simbolos = menu.addAction("Símbolos…")
        simbolos.setEnabled(bool(n))
        simbolos.triggered.connect(lambda: self.abrir_paleta(self.vista.aplicar.emit))
        menu.addAction("Selecionar tudo", self.vista.selectAll)
        menu.addSeparator()
        no_livro = self.escopo.currentData() == "livro"
        outro = self.escopo.findData("pagina" if no_livro else "livro")
        menu.addAction("Ver só a página" if no_livro else "Ver o livro inteiro",
                       lambda: self.escopo.setCurrentIndex(outro))
        return menu

    def abrir_paleta(self, aplicar) -> None:
        """F2 na Galeria: o símbolo escolhido vale para a seleção."""
        from abbychess.app.painel_treino import menu_da_paleta

        self.menu_da_paleta = menu_da_paleta(self, aplicar)      # os testes escolhem sem abrir
        self.menu_da_paleta.popup(self.vista.mapToGlobal(self.vista.rect().center()))

    def focar(self) -> None:
        self.vista.setFocus(Qt.FocusReason.ShortcutFocusReason)
