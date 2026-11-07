"""Onde a próxima tecla cai (SPEC-pagina-perfeita U-1, CA-U1b): o painel com o foco ganha uma
borda em `destaque`, e a barra de status diz o nome dele e o que o Enter faz ali ("Documento ·
Enter confirma", "Inspetor · Enter confere").

Um objeto à parte, e não um mixin da janela (roadmap da página perfeita, T4): ele só olha o
foco (`QApplication.focusChanged`), a aba da vista, o editor do Inspetor e o modo da fila.
A borda é um widget por cima do painel, transparente ao mouse e sem foco, que muda de pai
quando o foco muda de painel.
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from shiboken6 import isValid

from abbychess.app import estilo, teclado

#: A espessura da borda do painel com o foco, em pixels.
ESPESSURA = 2

#: O que o Enter faz em cada aba da vista direita, pelo nome da aba. O da Galeria, dos
#: Padrões e dos Diagramas é o da própria lista (não é ação do YAML: a tecla não muda).
ENTER_DA_VISTA = {"Documento": "{confirmar_e_avancar} confirma",
                  "Galeria": "Enter ensina",
                  "Padrões": "Enter vai à origem",
                  "Diagramas": "Enter abre na conferência"}


class MolduraDoFoco(QWidget):
    """A borda por cima do painel: não pega o mouse, não pega o foco, não tem fundo."""

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName("A borda do painel com o foco")
        self.hide()

    def cor(self) -> QColor:
        """A cor da borda: o `destaque` do tema de agora (troca com o tema)."""
        return QColor(estilo.tema().destaque)

    def paintEvent(self, _evento):
        pintor = QPainter(self)
        caneta = QPen(self.cor())
        caneta.setWidth(ESPESSURA)
        pintor.setPen(caneta)
        metade = ESPESSURA // 2
        pintor.drawRect(self.rect().adjusted(metade, metade, -metade, -metade))
        pintor.end()


class IndicadorDoFoco(QObject):
    """A borda e o rótulo da barra de status da janela `janela`."""

    def __init__(self, janela):
        super().__init__(janela)
        self.janela = janela
        self.moldura = MolduraDoFoco()
        self.rotulo = QLabel("")
        self.rotulo.setAccessibleName("O painel com o foco e o que o Enter faz nele")
        janela.statusBar().insertPermanentWidget(0, self.rotulo)
        self._painel: Optional[QWidget] = None
        # Métodos, e não lambdas: o Qt desliga o sinal do receptor apagado com a janela (o
        # `focusChanged` é da aplicação, e sobrevive a ela).
        QApplication.instance().focusChanged.connect(self._mudou)
        janela.vista.currentChanged.connect(self._mudou)
        janela.inspetor.pilha.currentChanged.connect(self._mudou)
        janela.eventos.ligar("modo_da_fila_mudou", self._mudou)
        teclado.quando_mudar(self.atualizar)

    def _mudou(self, *_args) -> None:
        if isValid(self) and isValid(self.moldura) and isValid(self.janela):
            self.atualizar()

    def _paineis(self) -> Tuple[Tuple[str, QWidget, Callable[[], str]], ...]:
        """(nome, widget, o que o Enter faz) de cada painel, na ordem do Alt+N."""
        j = self.janela
        return (("Páginas", j.paginas, lambda: "Enter abre a página"),
                ("Imagem", j.visor, lambda: ""),
                (j.vista.tabText(j.vista.currentIndex()), j.vista, self._enter_da_vista),
                ("Linha", j.linha, lambda: ""),
                ("Inspetor", j.inspetor, self._enter_do_inspetor),
                ("Resultados", j.resultados, lambda: "Enter vai ao item"))

    def _enter_da_vista(self) -> str:
        j = self.janela
        return teclado.com_teclas(ENTER_DA_VISTA.get(j.vista.tabText(j.vista.currentIndex()), ""))

    def _enter_do_inspetor(self) -> str:
        j = self.janela
        editor = j.inspetor.atual()
        if editor == "glifo":
            return f"{teclado.tecla('ensinar', 'Enter')} ensina"
        if editor == "palavra":
            verbo = "confere" if j.fila.modo == "lances" else "corrige"
            return f"{teclado.tecla('corrigir_palavra', 'Enter')} {verbo}"
        if editor == "diagrama":
            return f"{teclado.tecla('conferir_diagrama', 'Ctrl+Enter')} confere"
        return ""

    def painel(self) -> Optional[Tuple[str, QWidget, Callable[[], str]]]:
        """O painel que tem o foco, ou None (a barra de status, um diálogo, nenhum)."""
        foco = QApplication.focusWidget()
        if foco is None:
            return None
        for painel in self._paineis():
            widget = painel[1]
            if foco is widget or widget.isAncestorOf(foco):
                return painel
        return None

    def atualizar(self) -> None:
        """A borda no painel com o foco e o rótulo da barra; sem painel, nenhum dos dois."""
        painel = self.painel()
        if painel is None:
            self._soltar()
            self.rotulo.setText("")
            return
        nome, widget, enter = painel
        self._prender(widget)
        acao = enter()
        self.rotulo.setText(f"{nome} · {acao}" if acao else nome)

    def _prender(self, widget: QWidget) -> None:
        if self._painel is not widget:
            self._soltar()
            self._painel = widget
            self.moldura.setParent(widget)
            widget.installEventFilter(self)
        self.moldura.setGeometry(widget.rect())
        self.moldura.raise_()
        self.moldura.show()

    def _soltar(self) -> None:
        if self._painel is not None and isValid(self._painel):
            self._painel.removeEventFilter(self)
        self._painel = None
        self.moldura.hide()

    def eventFilter(self, objeto, evento):
        if objeto is self._painel and evento.type() == QEvent.Type.Resize:
            self.moldura.setGeometry(objeto.rect())
        return False
