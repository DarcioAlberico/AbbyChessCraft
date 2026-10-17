"""As opções do livro: os limiares da leitura e da revisão, e como ele escreve as peças.

Ficam no `projeto.json` do livro, e não no aplicativo: um livro bem impresso
aguenta uma revisão mais frouxa, uma fotocópia gasta pede outra.
"""

from __future__ import annotations

from dataclasses import fields

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QLabel)

from abbychess.projeto import Limiares

#: O rótulo e a dica de cada limiar, na ordem do diálogo.
ROTULOS = {
    "revisao": ("Revisar abaixo de", "Confiança abaixo da qual o box vai para a fila."),
    "livro": ("Padrão do livro aceito acima de", "Mais baixo aceita padrões mais distantes. "
              "A trava de altura continua valendo."),
    "rede": ("Rede global aceita acima de", "O NEURAL_THRESHOLD do PyBoxEditor."),
    "base": ("Base global aceita acima de", "O LEARNER_THRESHOLD_NEURAL do PyBoxEditor."),
}


#: Como o livro escreve as peças nos lances (§6.4): o valor e o rótulo.
NOTACOES = (("figurinas", "Figurinas (♘f3)"), ("letras", "Letras (Cf3)"))


class DialogoDeOpcoes(QDialog):
    def __init__(self, limiares: Limiares, parent=None, notacao: str = "figurinas"):
        super().__init__(parent)
        self.setWindowTitle("Opções do livro")
        formulario = QFormLayout(self)
        formulario.addRow(QLabel("Limiares deste livro. Valem na hora, sem reconhecer de novo."))
        self.campos = {}
        for nome, (rotulo, dica) in ROTULOS.items():
            campo = QDoubleSpinBox()
            campo.setRange(0.0, 1.0)
            campo.setSingleStep(0.05)
            campo.setDecimals(2)
            campo.setValue(getattr(limiares, nome))
            campo.setToolTip(dica)
            formulario.addRow(rotulo, campo)
            self.campos[nome] = campo
        self.campo_notacao = QComboBox()
        for valor, rotulo in NOTACOES:
            self.campo_notacao.addItem(rotulo, valor)
        self.campo_notacao.setCurrentIndex(max(0, self.campo_notacao.findData(notacao)))
        self.campo_notacao.setToolTip("No modo figurinas, a letra da peça digitada num lance vira "
                                      "figurina ao confirmar a palavra no Documento.")
        formulario.addRow("Peças nos lances", self.campo_notacao)
        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                  | QDialogButtonBox.StandardButton.Cancel)
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        formulario.addRow(botoes)

    def notacao(self) -> str:
        return self.campo_notacao.currentData()

    def limiares(self) -> Limiares:
        return Limiares(**{c.name: round(self.campos[c.name].value(), 2)
                           for c in fields(Limiares)})
