"""A confirmação na barra (SPEC §8.4, passo C): uma pergunta inline, sem diálogo modal.

"Aceitar 12 pendentes como estão? Enter aceita · Esc não marca". Ela pega o foco ao abrir;
Enter (ou o botão) aceita, Esc (ou o botão) fecha só a pergunta, e o foco volta a quem o
tinha. A janela a põe acima da faixa Linha e a fecha antes de qualquer outra camada no Esc
(`fechar_sobreposicao`): a barra de busca aberta fica.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton

from abbychess.app import estilo


class BarraDeConfirmacao(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("barra_de_confirmacao")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        cor = estilo.LARANJA
        self.setStyleSheet(f"#barra_de_confirmacao {{ background: rgba({cor.red()}, {cor.green()}, "
                           f"{cor.blue()}, 50); }}")
        self.pergunta = QLabel("")
        self.pergunta.setWordWrap(True)
        self.aceitar = QPushButton("Aceitar (Enter)")
        self.aceitar.setDefault(True)
        self.nao = QPushButton("Não (Esc)")
        caixa = QHBoxLayout(self)
        caixa.setContentsMargins(6, 2, 6, 2)
        caixa.addWidget(self.pergunta, 1)
        caixa.addWidget(self.aceitar)
        caixa.addWidget(self.nao)
        self.aceitar.clicked.connect(self._aceitar)
        self.nao.clicked.connect(self.recusar)
        self._ao_aceitar: Optional[Callable[[], None]] = None
        self._foco_antes = None
        self.hide()

    def perguntar(self, texto: str, ao_aceitar: Callable[[], None]) -> None:
        """Mostra a pergunta e guarda o que fazer se ela for aceita."""
        self._foco_antes = QApplication.focusWidget()
        self._ao_aceitar = ao_aceitar
        self.pergunta.setText(texto)
        self.setAccessibleName(texto)
        self.show()
        self.aceitar.setFocus(Qt.FocusReason.OtherFocusReason)

    @property
    def aberta(self) -> bool:
        return not self.isHidden()

    def _fechar(self) -> None:
        self.hide()
        antes, self._foco_antes = self._foco_antes, None
        if antes is not None and antes.isVisible():
            antes.setFocus(Qt.FocusReason.OtherFocusReason)

    def _aceitar(self) -> None:
        funcao, self._ao_aceitar = self._ao_aceitar, None
        self._fechar()
        if funcao is not None:
            funcao()

    def recusar(self) -> None:
        """Esc: só a pergunta fecha (nada é marcado)."""
        self._ao_aceitar = None
        self._fechar()

    def keyPressEvent(self, evento):
        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._aceitar()
            return
        if evento.key() == Qt.Key.Key_Escape:
            self.recusar()
            return
        super().keyPressEvent(evento)
