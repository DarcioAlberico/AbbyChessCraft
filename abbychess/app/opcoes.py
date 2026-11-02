"""As opções do livro: os limiares da leitura e da revisão, como ele escreve as peças e o
idioma da prosa (o dicionário da verificação de texto).

Ficam no `projeto.json` do livro, e não no aplicativo: um livro bem impresso
aguenta uma revisão mais frouxa, uma fotocópia gasta pede outra.
"""

from __future__ import annotations

from dataclasses import fields

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QLabel)

from abbychess.idioma import IDIOMAS
from abbychess.projeto import Limiares

#: O rótulo e a dica de cada limiar, na ordem do diálogo.
ROTULOS = {
    "revisao": ("Revisar abaixo de", "Confiança abaixo da qual o box vai para a fila."),
    "livro": ("Padrão do livro aceito acima de", "Mais baixo aceita padrões mais distantes. "
              "A trava de altura continua valendo."),
    "rede": ("Rede global aceita acima de", "O NEURAL_THRESHOLD do PyBoxEditor."),
    "base": ("Base global aceita acima de", "O LEARNER_THRESHOLD_NEURAL do PyBoxEditor."),
    "conflito": ("Avisar conflito a menos de", "Ao ensinar, o Inspetor avisa quando o glifo "
                 "está mais perto que isto (a distância do k-NN / 2000) de amostras de outro "
                 "caractere."),
}


#: Como o livro escreve as peças nos lances (§6.4): o valor e o rótulo.
NOTACOES = (("livro", "Como o livro (figurinas se ele tem)"), ("figurinas", "Figurinas (♘f3)"),
            ("letras", "Letras (Cf3)"))


class DialogoDeOpcoes(QDialog):
    def __init__(self, limiares: Limiares, parent=None, notacao: str = "livro",
                 idioma: str = "pt"):
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
        self.campo_idioma = QComboBox()
        for rotulo, codigo in IDIOMAS:
            self.campo_idioma.addItem(rotulo, codigo)
        self.campo_idioma.setCurrentIndex(max(0, self.campo_idioma.findData(idioma)))
        self.campo_idioma.setToolTip("O idioma da prosa: o dicionário da verificação de texto "
                                     "(F7) e as letras das peças nos lances.")
        formulario.addRow("Idioma do livro", self.campo_idioma)
        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                  | QDialogButtonBox.StandardButton.Cancel)
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        formulario.addRow(botoes)

    def notacao(self) -> str:
        return self.campo_notacao.currentData()

    def idioma(self) -> str:
        return self.campo_idioma.currentData()

    def limiares(self) -> Limiares:
        return Limiares(**{c.name: round(self.campos[c.name].value(), 2)
                           for c in fields(Limiares)})
