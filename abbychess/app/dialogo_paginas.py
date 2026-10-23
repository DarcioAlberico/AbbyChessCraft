"""Os diálogos das operações de página (SPEC §12.4, passo L): mover, apagar, inserir, girar,
cortar e dividir páginas, e Páginas apagadas….

As páginas se escolhem como texto, pela seleção do livro (`sequencia.selecao`: "3-7, 12",
"ímpares", "pares", "todas"), com o número de agora; o diálogo mostra, enquanto se digita,
quantas páginas o texto escolhe ou o que está errado nele, e só aceita o texto válido. O
lugar ("depois da página N") é um número de 0 a N, em que 0 é o começo do livro.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Tuple, Union

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFormLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from abbychess import sequencia as sq
from abbychess.app import estilo


def texto_da_selecao(posicoes: Sequence[int]) -> str:
    """As posições como o usuário as escreve: "2-4, 7" (os números da página, de 1)."""
    numeros, faixas = sorted({p + 1 for p in posicoes}), []
    for n in numeros:
        if faixas and n == faixas[-1][1] + 1:
            faixas[-1][1] = n
        else:
            faixas.append([n, n])
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in faixas)


def efeito(um: str, varios: str) -> Callable[[List[int]], str]:
    """A prévia no número certo: `um` para uma página, `varios` para mais (com `{N}`, quantas,
    e `{PAGINAS}`, o texto da seleção)."""
    def texto(posicoes: List[int]) -> str:
        modelo = um if len(posicoes) == 1 else varios
        return modelo.format(N=len(posicoes), PAGINAS=texto_da_selecao(posicoes))
    return texto


#: A largura mínima dos diálogos: a explicação e a prévia cabem em poucas linhas.
LARGURA_DOS_DIALOGOS = 440


class DialogoDasPaginas(QDialog):
    """Escolhe as páginas e, para mover e inserir, o lugar. `com_selecao=False` (inserir) só
    pergunta o lugar; `linhas` (rótulo, widget) são as perguntas da operação (girar, cortar,
    dividir), depois das páginas. `efeito` é a prévia: um modelo com `{N}` e `{PAGINAS}`, ou
    uma função das posições; `validar(posições, depois_da)` diz por que a escolha não vale
    (o OK fica desligado), ou None; `ok`, o texto do botão que confirma."""

    def __init__(self, parent, titulo: str, total: int, *, selecao: str = "",
                 com_selecao: bool = True, lugar: Optional[str] = None, lugar_padrao: int = 0,
                 explicacao: str = "",
                 efeito: Union[str, Callable[[List[int]], str]] = "{N} página(s)",
                 linhas: Sequence[Tuple[str, QWidget]] = (),
                 validar: Optional[Callable[[List[int], int], Optional[str]]] = None,
                 ok: str = ""):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setMinimumWidth(LARGURA_DOS_DIALOGOS)
        self.validar = validar
        self.total = total
        self.efeito = efeito
        self.campo = QLineEdit(selecao)
        self.campo.setPlaceholderText("3-7, 12 · ímpares · pares · todas")
        self.campo.setAccessibleName("As páginas")
        self.campo.setToolTip("Os números das páginas como estão no livro agora; "
                              "\"ímpares\", \"pares\" e \"todas\" também valem")
        self.previa = QLabel("")
        self.previa.setWordWrap(True)
        self.lugar: Optional[QSpinBox] = None
        formulario = QFormLayout()
        if com_selecao:
            formulario.addRow("Páginas", self.campo)
            formulario.addRow("", self.previa)
        else:
            self.campo.hide()
            self.previa.hide()
        if lugar is not None:
            self.lugar = QSpinBox()
            self.lugar.setRange(0, total)
            self.lugar.setValue(max(0, min(lugar_padrao, total)))
            self.lugar.setSpecialValueText("o começo do livro")
            self.lugar.setAccessibleName(lugar)
            self.lugar.valueChanged.connect(self._conferir)
            formulario.addRow(lugar, self.lugar)
        for rotulo, widget in linhas:
            widget.setAccessibleName(rotulo)
            formulario.addRow(rotulo, widget)
        self.botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                       QDialogButtonBox.StandardButton.Cancel)
        if ok:
            self.botoes.button(QDialogButtonBox.StandardButton.Ok).setText(ok)
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        corpo = QVBoxLayout(self)
        if explicacao:
            nota = QLabel(explicacao)
            nota.setWordWrap(True)
            estilo.papel(nota, "dica")
            corpo.addWidget(nota)
        corpo.addLayout(formulario)
        corpo.addWidget(self.botoes)
        self.com_selecao = com_selecao
        self.campo.textChanged.connect(self._conferir)
        self._conferir()

    def posicoes(self) -> List[int]:
        """As posições escolhidas (ValueError se o texto não vale)."""
        return sq.selecao(self.campo.text(), self.total) if self.com_selecao else []

    def depois_da(self) -> int:
        """A posição depois da qual as páginas vão (-1: o começo do livro)."""
        return (self.lugar.value() - 1) if self.lugar is not None else -1

    def _conferir(self, *_args) -> None:
        ok = self.botoes.button(QDialogButtonBox.StandardButton.Ok)
        if not self.com_selecao:
            ok.setEnabled(True)
            return
        try:
            posicoes = self.posicoes()
        except ValueError as erro:
            self.previa.setText(str(erro))
            estilo.papel(self.previa, "erro")
            ok.setEnabled(False)
            return
        erro = self.validar(posicoes, self.depois_da()) if self.validar else None
        if erro:
            self.previa.setText(erro)
            estilo.papel(self.previa, "erro")
            ok.setEnabled(False)
            return
        self.previa.setText(self.efeito(posicoes) if callable(self.efeito) else
                            self.efeito.format(N=len(posicoes),
                                               PAGINAS=texto_da_selecao(posicoes)))
        estilo.papel(self.previa, "dica")
        ok.setEnabled(True)


def perguntar_paginas(janela, titulo: str, total: int, **opcoes
                      ) -> Optional[Tuple[List[int], int]]:
    """(posições, depois_da) do diálogo aceito, ou None."""
    dialogo = DialogoDasPaginas(janela, titulo, total, **opcoes)
    try:
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialogo.posicoes(), dialogo.depois_da()
    finally:
        dialogo.deleteLater()


def perguntar_com(janela, titulo: str, total: int, linhas: Sequence[Tuple[str, QWidget]],
                  ler: Callable[[], object], **opcoes) -> Optional[Tuple[List[int], object]]:
    """(posições, o que `ler()` diz das `linhas`) do diálogo aceito, ou None. `ler` roda com
    o diálogo ainda vivo."""
    dialogo = DialogoDasPaginas(janela, titulo, total, linhas=linhas, **opcoes)
    try:
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialogo.posicoes(), ler()
    finally:
        dialogo.deleteLater()


#: Os sentidos de girar, como o diálogo os oferece: (texto, graus no sentido horário).
SENTIDOS = (("90° à direita", 90), ("90° à esquerda", 270), ("180°", 180))


def campo_do_sentido() -> QComboBox:
    campo = QComboBox()
    for texto, graus in SENTIDOS:
        campo.addItem(texto, graus)
    return campo


def campo_de_porcentagem(valor: float, minimo: float, maximo: float, sufixo: str = " %", *,
                         decimais: int = 1, passo: float = 1.0) -> QDoubleSpinBox:
    """O campo de número; as casas antes do valor (o Qt arredonda o valor às casas de agora:
    o ângulo medido de 0,65° viraria 0,7°, e dar OK sem mexer endireitaria a página)."""
    campo = QDoubleSpinBox()
    campo.setDecimals(decimais)
    campo.setRange(minimo, maximo)
    campo.setSingleStep(passo)
    campo.setSuffix(sufixo)
    campo.setValue(valor)
    return campo


# ----------------------------------------------------------------------
# Páginas apagadas…
# ----------------------------------------------------------------------

def descrever_apagada(apagada: "sq.Apagada") -> str:
    """Como a página apagada aparece na lista: de onde ela vem e onde ela estava."""
    e = apagada.entrada
    if e.fonte == sq.FONTE_DO_LIVRO:
        origem = f"p. {e.pagina + 1} do PDF"
        if e.metade is not None:
            origem += f" (metade {e.metade})"
    else:
        origem = f"inserida (p. {e.pagina + 1} de {e.fonte.split('/', 1)[1][:8]}…)"
    return f"{origem} · estava depois da p. {apagada.posicao}" \
        if apagada.posicao else f"{origem} · estava no começo do livro"


class DialogoDasApagadas(QDialog):
    """As páginas apagadas, para restaurar as escolhidas ou todas."""

    def __init__(self, parent, apagadas: Sequence["sq.Apagada"]):
        super().__init__(parent)
        self.setWindowTitle("Páginas apagadas")
        self.resize(560, 360)
        self.lista = QListWidget()
        self.lista.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lista.setAccessibleName("Páginas apagadas")
        for apagada in apagadas:
            item = QListWidgetItem(descrever_apagada(apagada))
            item.setData(Qt.ItemDataRole.UserRole, apagada.entrada.pid)
            self.lista.addItem(item)
        nota = QLabel("Os glifos, as correções e os padrões ensinados nelas ficaram guardados: "
                      "a página volta como estava, no lugar de onde saiu.")
        nota.setWordWrap(True)
        estilo.papel(nota, "dica")
        self.botao_escolhidas = QPushButton("Restaurar as escolhidas")
        self.botao_todas = QPushButton("Restaurar todas")
        fechar = QPushButton("Fechar")
        self._escolha: List[int] = []
        self.botao_escolhidas.clicked.connect(lambda: self._restaurar(self._selecionadas()))
        self.botao_todas.clicked.connect(lambda: self._restaurar(self._todas()))
        fechar.clicked.connect(self.reject)
        self.lista.itemSelectionChanged.connect(self._ligar)
        self.botao_todas.setEnabled(bool(apagadas))
        botoes = QDialogButtonBox()
        for botao, papel in ((self.botao_escolhidas, QDialogButtonBox.ButtonRole.AcceptRole),
                             (self.botao_todas, QDialogButtonBox.ButtonRole.AcceptRole),
                             (fechar, QDialogButtonBox.ButtonRole.RejectRole)):
            botoes.addButton(botao, papel)
        corpo = QVBoxLayout(self)
        corpo.addWidget(nota)
        corpo.addWidget(self.lista, 1)
        corpo.addWidget(botoes)
        self._ligar()

    def _selecionadas(self) -> List[int]:
        return [i.data(Qt.ItemDataRole.UserRole) for i in self.lista.selectedItems()]

    def _todas(self) -> List[int]:
        return [self.lista.item(k).data(Qt.ItemDataRole.UserRole)
                for k in range(self.lista.count())]

    def _ligar(self) -> None:
        self.botao_escolhidas.setEnabled(bool(self.lista.selectedItems()))

    def _restaurar(self, pids: List[int]) -> None:
        if pids:
            self._escolha = pids
            self.accept()

    def escolha(self) -> List[int]:
        return list(self._escolha)


def perguntar_apagadas(janela, apagadas: Sequence["sq.Apagada"]) -> Optional[List[int]]:
    """Os `pid` a restaurar, ou None."""
    dialogo = DialogoDasApagadas(janela, apagadas)
    try:
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialogo.escolha() or None
    finally:
        dialogo.deleteLater()
