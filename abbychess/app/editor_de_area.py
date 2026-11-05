"""O editor Área do Inspetor (SPEC §3.1): a função e o número da ordem da área escolhida. A letra e
o botão direito continuam valendo; aqui se vê o que a área é e se muda a ordem de uma só, sem o
Ordenar, que pede o clique em todas."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QSpinBox, QVBoxLayout, QWidget

from abbychess import zonas as zn
from abbychess.app import estilo, teclado

#: As funções do editor, na ordem do menu da área (a `tabela` é da fase das tabelas, §5.1).
FUNCOES = ("texto", "titulo", "cabecalho", "rodape", "numero_de_pagina", "nota", "legenda",
           "diagrama", "figura", "ignorar")


class EditorDeArea(QWidget):
    #: A função escolhida para a área mostrada.
    funcao_escolhida = Signal(str)
    #: O número novo da área mostrada na ordem de leitura.
    ordem_escolhida = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.vazio = QLabel()
        self.vazio.setWordWrap(True)
        estilo.papel(self.vazio, "dica")
        teclado.texto_vivo(self.vazio, "setText",
                           "Clique numa área, no editor de áreas ({modo_areas}).")
        self.campo = QComboBox()
        self.campo.setAccessibleName("Função da área")
        for funcao in FUNCOES:
            self.campo.addItem(zn.NOMES_DAS_FUNCOES[funcao], funcao)
        self.campo.activated.connect(lambda i: self.funcao_escolhida.emit(self.campo.itemData(i)))
        self.ordem = QSpinBox()
        self.ordem.setAccessibleName("Número da área na ordem de leitura")
        self.ordem.setKeyboardTracking(False)   # "12" digitado não passa pelo 1
        self.ordem.valueChanged.connect(self.ordem_escolhida)
        self.formulario = QWidget()
        campos = QFormLayout(self.formulario)
        campos.setContentsMargins(0, 0, 0, 0)
        campos.addRow("Função:", self.campo)
        campos.addRow("Ordem:", self.ordem)
        caixa = QVBoxLayout(self)
        caixa.setContentsMargins(4, 4, 4, 4)
        caixa.addWidget(self.vazio)
        caixa.addWidget(self.formulario)
        caixa.addStretch(1)
        caixa.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.mostrar(None, 0, "")

    def mostrar(self, numero: Optional[int], total: int, funcao: str) -> None:
        """A área de número `numero` entre `total`; `None`: nenhuma escolhida."""
        vazio = numero is None
        self.vazio.setHidden(not vazio)
        self.formulario.setHidden(vazio)
        if vazio:
            return
        indice = self.campo.findData(funcao)
        self.campo.setCurrentIndex(indice)      # -1, a função fora da lista: nada marcado
        self.ordem.blockSignals(True)
        self.ordem.setRange(1, max(1, total))
        self.ordem.setValue(numero)
        self.ordem.blockSignals(False)
