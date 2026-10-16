"""O Inspetor (SPEC §3.1): um editor só, o do item atual.

No cabeçalho, o seletor da fila (um `QToolButton` com menu, não um combo: o Alt+↓ é da
fila) e o contador; no meio, o editor (Glifo, o treino; Palavra, a verificação); no rodapé,
a dica das teclas do editor. O editor só troca por ação explícita (um clique num item, o
modo da fila), nunca pelo foco.
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMenu, QScrollArea, QStackedWidget,
                               QToolButton, QVBoxLayout, QWidget)

DICAS = {
    "glifo": "Enter ensina · Shift+Enter só esta · Del descarta · Alt+↓ próximo · "
             "Ctrl+D divide · Ctrl+J junta · Shift+seta bordas · F2 símbolos",
    "palavra": "Enter corrige · Ctrl+Enter corrige e ensina · Alt+↓ próxima · "
               "Ctrl+Shift+I ignora todas · Ctrl+Shift+D dicionário",
}


class PainelDoInspetor(QWidget):
    #: O modo da fila escolhido no seletor.
    modo_escolhido = Signal(str)

    def __init__(self, modos: Sequence[Tuple[str, str]], editores: Dict[str, QWidget],
                 parent=None):
        super().__init__(parent)
        self.seletor = QToolButton()
        self.seletor.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.seletor.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.seletor.setAccessibleName("Modo da fila de revisão (F7 cicla)")
        self.seletor.setToolTip("O que Alt+↓ e Alt+↑ percorrem (F7 cicla)")
        menu = QMenu(self.seletor)
        grupo = QActionGroup(menu)
        self._modos: Dict[str, QAction] = {}
        for modo, nome in modos:
            acao = menu.addAction(nome)
            acao.setCheckable(True)
            grupo.addAction(acao)
            acao.triggered.connect(lambda _=False, m=modo: self.modo_escolhido.emit(m))
            self._modos[modo] = acao
        self.seletor.setMenu(menu)
        self.contador = QLabel("")
        self.contador.setAccessibleName("Posição na fila")

        cabecalho = QHBoxLayout()
        cabecalho.addWidget(QLabel("Fila:"))
        cabecalho.addWidget(self.seletor, 1)
        cabecalho.addWidget(self.contador)

        self.editores = editores
        self.pilha = QStackedWidget()
        self._rolagens: Dict[str, QScrollArea] = {}
        for nome, editor in editores.items():
            rolagem = QScrollArea()
            rolagem.setWidgetResizable(True)
            rolagem.setFrameShape(QScrollArea.Shape.NoFrame)
            rolagem.setWidget(editor)
            self.pilha.addWidget(rolagem)
            self._rolagens[nome] = rolagem
        self.dica = QLabel("")
        self.dica.setWordWrap(True)
        self.dica.setStyleSheet("color: #555;")

        caixa = QVBoxLayout(self)
        caixa.setContentsMargins(4, 4, 4, 4)
        caixa.addLayout(cabecalho)
        caixa.addWidget(self.pilha, 1)
        caixa.addWidget(self.dica)
        self.mostrar(next(iter(editores)))

    # ------------------------------------------------------------------
    def mostrar(self, nome: str) -> None:
        """Mostra o editor `nome` ("glifo", "palavra")."""
        self.pilha.setCurrentWidget(self._rolagens[nome])
        self.dica.setText(DICAS.get(nome, ""))

    def atual(self) -> str:
        rolagem = self.pilha.currentWidget()
        return next(n for n, r in self._rolagens.items() if r is rolagem)

    def editor(self) -> QWidget:
        return self.editores[self.atual()]

    def mostrar_modo(self, modo: str, nome: str) -> None:
        self.seletor.setText(nome + "  ▾")
        self._modos[modo].setChecked(True)

    def mostrar_contador(self, texto: str) -> None:
        self.contador.setText(texto)

    def focar(self) -> None:
        """Alt+4: o campo do editor (o caractere, a palavra)."""
        campo = getattr(self.editor(), "campo", None)
        alvo = campo if campo is not None and campo.isEnabled() else self.seletor
        alvo.setFocus(Qt.FocusReason.ShortcutFocusReason)
