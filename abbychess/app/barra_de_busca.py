"""A barra de Localizar (SPEC §7.1, passo B), no topo da vista direita.

O texto; **Aa** (maiúsculas e minúsculas diferentes); **palavra inteira**; **.\\*** (regex,
com as classes de xadrez `\\L`, `\\P`, `\\C`, `\\V`, expandidas na dica do campo);
**♘=C** (figurina = letra); o **escopo** (livro, página, seleção, intervalo de páginas) e
**onde** (prosa, notação, FEN, legendas, cabeçalhos). Digitar busca de novo depois de um
instante (a anterior é cancelada); Enter e Shift+Enter vão à próxima e à anterior; Alt+Enter
manda todas para Resultados; Esc fecha. A barra só diz o que o usuário pediu
(`opcoes`): quem busca é a janela, pelo `ControladorDaBusca`.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit, QMenu, QToolButton,
                               QWidget)

from abbychess import busca as bs
from abbychess.app import estilo

ESCOPOS = ((bs.LIVRO, "Livro"), (bs.PAGINA, "Página"), (bs.SELECAO, "Seleção"),
           (bs.INTERVALO, "Intervalo"))
ONDE = ((bs.PROSA, "Prosa"), (bs.NOTACAO, "Notação"), (bs.FEN, "FEN"),
        (bs.LEGENDA, "Legendas"), (bs.CABECALHO, "Cabeçalhos e rodapés"))
#: Quanto esperar depois da última tecla antes de buscar.
ESPERA_MS = 250


class BarraDeBusca(QWidget):
    #: As opções mudaram (depois da espera): buscar de novo.
    mudou = Signal()
    proxima = Signal()
    anterior = Signal()
    todas = Signal()
    fechar = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("barra_de_busca")
        self.campo = QLineEdit()
        self.campo.setPlaceholderText("Localizar")
        self.campo.setAccessibleName("Texto a localizar")
        self.campo.setClearButtonEnabled(True)
        self.maiusculas = self._botao("Aa", "Maiúsculas e minúsculas diferentes")
        self.palavra = self._botao("ab|", "Palavra inteira")
        self.regex = self._botao(".*", "Expressão regular (com \\L lance, \\P peça, \\C casa, "
                                 "\\V valoração)")
        self.figurina = self._botao("♘=C", "Figurina = letra: ♘f3 casa Cf3 e Nf3")
        self.escopo = QComboBox()
        self.escopo.setAccessibleName("Onde buscar: livro, página, seleção ou intervalo")
        for valor, rotulo in ESCOPOS:
            self.escopo.addItem(rotulo, valor)
        self.intervalo = QLineEdit()
        self.intervalo.setPlaceholderText("3-10")
        self.intervalo.setAccessibleName("Intervalo de páginas")
        self.intervalo.setMaximumWidth(64)
        self.intervalo.hide()
        self.onde = QToolButton()
        self.onde.setText("Onde")
        self.onde.setToolTip("Prosa, notação, FEN, legendas, cabeçalhos")
        self.onde.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.onde)
        self.acoes_do_onde = {}
        for valor, rotulo in ONDE:
            q = menu.addAction(rotulo)
            q.setCheckable(True)
            q.setChecked(True)
            q.toggled.connect(self._agendar)
            self.acoes_do_onde[valor] = q
        self.onde.setMenu(menu)
        self.contador = QLabel("")
        self.contador.setAccessibleName("Ocorrências")
        self.contador.setMinimumWidth(60)
        anterior = self._acao_simples("▲", "Ocorrência anterior (Shift+F3)", self.anterior.emit)
        seguinte = self._acao_simples("▼", "Próxima ocorrência (F3)", self.proxima.emit)
        fechar = self._acao_simples("✕", "Fechar a barra (Esc)", self.fechar.emit)

        caixa = QHBoxLayout(self)
        caixa.setContentsMargins(4, 2, 4, 2)
        caixa.setSpacing(2)
        caixa.addWidget(self.campo, 1)
        for w in (self.maiusculas, self.palavra, self.regex, self.figurina, self.escopo,
                  self.intervalo, self.onde, self.contador, anterior, seguinte, fechar):
            caixa.addWidget(w)

        self.relogio = QTimer(self)
        self.relogio.setSingleShot(True)
        self.relogio.setInterval(ESPERA_MS)
        self.relogio.timeout.connect(self.mudou.emit)
        self.campo.textChanged.connect(self._agendar)
        self.intervalo.textChanged.connect(self._agendar)
        self.escopo.currentIndexChanged.connect(self._escopo_mudou)
        self.hide()

    def _botao(self, texto: str, dica: str) -> QToolButton:
        botao = QToolButton()
        botao.setText(texto)
        botao.setToolTip(dica)
        botao.setAccessibleName(dica)
        botao.setCheckable(True)
        botao.toggled.connect(self._agendar)
        return botao

    def _acao_simples(self, texto: str, dica: str, funcao) -> QToolButton:
        botao = QToolButton()
        botao.setText(texto)
        botao.setToolTip(dica)
        botao.setAccessibleName(dica)
        botao.setAutoRaise(True)
        botao.clicked.connect(funcao)
        return botao

    def _escopo_mudou(self, *_):
        self.intervalo.setVisible(self.escopo.currentData() == bs.INTERVALO)
        self._agendar()

    def _agendar(self, *_):
        self.relogio.start()

    # ------------------------------------------------------------------
    def abrir(self, texto: Optional[str] = None) -> None:
        """Mostra a barra com o foco no campo (e o texto, se veio a seleção)."""
        self.show()
        if texto:
            self.campo.setText(texto)
        self.campo.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.campo.selectAll()

    def opcoes(self, **contexto) -> bs.Opcoes:
        """As opções da barra, com o `contexto` da janela (a página aberta, a seleção, o
        idioma)."""
        return bs.Opcoes(
            self.campo.text(), maiusculas=self.maiusculas.isChecked(),
            palavra_inteira=self.palavra.isChecked(), regex=self.regex.isChecked(),
            figurina_letra=self.figurina.isChecked(), escopo=self.escopo.currentData(),
            intervalo=self.intervalo_de_paginas(),
            onde=frozenset(v for v, q in self.acoes_do_onde.items() if q.isChecked()),
            **contexto)

    def intervalo_de_paginas(self) -> Optional[Tuple[int, int]]:
        """O intervalo digitado ("3-10" ou "7"), em índices (0 = a primeira), ou None."""
        casado = re.fullmatch(r"\s*(\d+)\s*(?:[-–]\s*(\d+))?\s*", self.intervalo.text())
        if casado is None:
            return None
        a = int(casado.group(1))
        b = int(casado.group(2) or a)
        return (max(0, min(a, b) - 1), max(0, max(a, b) - 1))

    def mostrar_contagem(self, atual: Optional[int], total: int) -> None:
        self.contador.setStyleSheet("")
        if total == 0:
            self.contador.setText("nada" if self.campo.text() else "")
        elif atual is None:
            self.contador.setText(str(total))
        else:
            self.contador.setText(f"{atual + 1} de {total}")

    def mostrar_erro(self, mensagem: str) -> None:
        self.contador.setText("erro")
        self.contador.setStyleSheet(f"color: {estilo.VERMELHAO.name()}")
        self.contador.setToolTip(mensagem)

    def mostrar_dica(self, dica: str) -> None:
        self.campo.setToolTip(dica)

    def keyPressEvent(self, evento):
        tecla, mods = evento.key(), evento.modifiers()
        if tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if mods & Qt.KeyboardModifier.AltModifier:
                self.todas.emit()
            elif mods & Qt.KeyboardModifier.ShiftModifier:
                self.anterior.emit()
            else:
                self.proxima.emit()
            return
        if tecla == Qt.Key.Key_Escape:
            self.fechar.emit()
            return
        super().keyPressEvent(evento)
