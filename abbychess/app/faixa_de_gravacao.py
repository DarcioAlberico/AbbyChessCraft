"""A faixa da gravação que falhou (SPEC-pagina-perfeita U-6, CA-U6): enquanto alguma página não
grava (o disco cheio, o arquivo bloqueado), uma faixa fixa, na cor de erro, fica acima da
página e diz qual, por quê, e que o programa tenta de novo. Ela sai sozinha quando o gravador
consegue; o botão abre Avisos.

Antes, a falha era uma linha na barra de status, que a mensagem seguinte apagava: quem
fechasse o programa ali perdia a edição. O gravador tenta de novo na thread dele; a faixa só
pergunta, a cada meio segundo enquanto está à vista, se ainda há página falhando
(`falhando`, uma função sem argumentos).
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from abbychess.app import estilo

#: De quanto em quanto tempo a faixa à vista pergunta se a página já gravou, em ms.
INTERVALO_MS = 500


class FaixaDeGravacao(QFrame):
    """A faixa: o texto da falha e o botão que abre Avisos."""

    #: O botão "Ver os avisos".
    ver_os_avisos = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName("A gravação que falhou")
        self.texto = QLabel("")
        self.texto.setWordWrap(True)
        estilo.papel(self.texto, "erro")
        self.botao = QPushButton("Ver os avisos")
        self.botao.clicked.connect(self.ver_os_avisos.emit)
        caixa = QHBoxLayout(self)
        caixa.setContentsMargins(6, 2, 6, 2)
        caixa.addWidget(self.texto, 1)
        caixa.addWidget(self.botao)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._falhando: Optional[Callable[[], object]] = None
        self._relogio = QTimer(self)
        self._relogio.setInterval(INTERVALO_MS)
        self._relogio.timeout.connect(self._conferir)
        self.hide()

    def mostrar(self, indice: Optional[int], erro, falhando: Callable[[], object]) -> None:
        """A página `indice` (posição; None se não se sabe) não gravou por `erro`. A faixa fica
        até `falhando()` dar vazio."""
        pagina = f"A página {indice + 1}" if indice is not None else "Uma página"
        self.texto.setText(f"{pagina} não foi gravada ({erro}). O programa tenta de novo; não "
                           "feche antes de liberar o disco.")
        self._falhando = falhando
        self.show()
        self._relogio.start()

    def _conferir(self) -> None:
        if self._falhando is None or not self._falhando():
            self.esconder()

    def esconder(self) -> None:
        self._relogio.stop()
        self._falhando = None
        self.hide()
