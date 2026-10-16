"""As opções do livro: os limiares da leitura e da revisão.

Ficam no `projeto.json` do livro, e não no aplicativo: um livro bem impresso
aguenta uma revisão mais frouxa, uma fotocópia gasta pede outra.
"""

from __future__ import annotations

from dataclasses import fields

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel

from abbychess.projeto import Limiares

#: O rótulo e a dica de cada limiar, na ordem do diálogo.
ROTULOS = {
    "revisao": ("Revisar abaixo de", "Confiança abaixo da qual o box vai para a fila."),
    "livro": ("Padrão do livro aceito acima de", "Mais baixo aceita padrões mais distantes. "
              "A trava de altura continua valendo."),
    "rede": ("Rede global aceita acima de", "O NEURAL_THRESHOLD do PyBoxEditor."),
    "base": ("Base global aceita acima de", "O LEARNER_THRESHOLD_NEURAL do PyBoxEditor."),
}


class DialogoDeOpcoes(QDialog):
    def __init__(self, limiares: Limiares, parent=None):
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
        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                  | QDialogButtonBox.StandardButton.Cancel)
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        formulario.addRow(botoes)

    def limiares(self) -> Limiares:
        return Limiares(**{c.name: round(self.campos[c.name].value(), 2)
                           for c in fields(Limiares)})
