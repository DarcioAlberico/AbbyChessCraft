"""A barra de Localizar (SPEC §7.1, passo B), no topo da vista direita.

O texto; **Aa** (maiúsculas e minúsculas diferentes); **palavra inteira**; **.\\*** (regex,
com as classes de xadrez `\\L`, `\\P`, `\\C`, `\\V`, expandidas na dica do campo);
**♘=C** (figurina = letra); o **escopo** (livro, página, seleção, intervalo de páginas) e
**onde** (prosa, notação, FEN, legendas, cabeçalhos). Digitar busca de novo depois de um
instante (a anterior é cancelada); Enter e Shift+Enter vão à próxima e à anterior; Alt+Enter
manda todas para Resultados; Esc fecha. A barra só diz o que o usuário pediu
(`opcoes`): quem busca é a janela, pelo `ControladorDaBusca`.

Com Ctrl+H (§7.2, passo D2), a terceira linha: **substituir por** (com `\\1` e
`\\g<nome>` quando a regex está ligada), **Prosa | Notação | Ambos** e os botões
**Substituir** (Enter no campo) e **Todas** (Ctrl+Enter no campo).
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit, QMenu, QToolButton,
                               QVBoxLayout, QWidget)

from abbychess import busca as bs
from abbychess import substituir as sb
from abbychess.app import estilo, teclado

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
    #: Substituir a ocorrência atual; substituir todas (§7.2).
    substituir = Signal()
    substituir_todas = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("barra_de_busca")
        self.campo = QLineEdit()
        self.campo.setPlaceholderText("Localizar")
        self.campo.setAccessibleName("Texto a localizar")
        self.campo.setClearButtonEnabled(True)
        self.campo.setMinimumWidth(180)         # uma regex inteira cabe, também em 1366×768
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
        anterior = self._acao_simples("▲", "Ocorrência anterior ({ocorrencia_anterior})",
                                      self.anterior.emit)
        seguinte = self._acao_simples("▼", "Próxima ocorrência ({proxima_ocorrencia})",
                                      self.proxima.emit)
        fechar = self._acao_simples("✕", "Fechar a barra (Esc)", self.fechar.emit)
        self.substituto = QLineEdit()
        self.substituto.setPlaceholderText("Substituir por")
        self.substituto.setAccessibleName("Substituir por")
        self.substituto.setToolTip("Com a regex ligada, \\1 e \\g<nome> trazem os grupos. "
                                   "Enter: substituir · Ctrl+Enter: todas")
        self.substituto.setMinimumWidth(120)
        self.alvo = QComboBox()
        self.alvo.setAccessibleName("Substituir em: prosa, notação ou ambos")
        self.alvo.setToolTip("Prosa nunca toca a notação, e Notação nunca toca a prosa; o FEN "
                             "nunca é substituído")
        for valor, rotulo in sb.ALVOS:
            self.alvo.addItem(rotulo, valor)
        self.botao_substituir = self._acao_simples("Substituir", "Substituir a ocorrência "
                                                   "atual (Enter no campo)", self.substituir.emit)
        self.botao_todas = self._acao_simples("Todas", "Substituir todas (Ctrl+Enter no campo); "
                                              "fora da página, com a prévia em Resultados",
                                              self.substituir_todas.emit)
        self.linha_de_substituir = QWidget()
        linha = QHBoxLayout(self.linha_de_substituir)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(2)
        linha.addWidget(self.substituto, 1)
        for w in (self.alvo, self.botao_substituir, self.botao_todas):
            linha.addWidget(w)
        self.linha_de_substituir.hide()

        # Duas linhas: o campo, a contagem e as setas em cima; as opções embaixo (numa
        # vista direita estreita, uma linha só deixaria o campo com ~60 px).
        caixa = QVBoxLayout(self)
        caixa.setContentsMargins(4, 2, 4, 2)
        caixa.setSpacing(2)
        cima, baixo = QHBoxLayout(), QHBoxLayout()
        for linha in (cima, baixo):
            linha.setSpacing(2)
            caixa.addLayout(linha)
        cima.addWidget(self.campo, 1)
        for w in (self.contador, anterior, seguinte, fechar):
            cima.addWidget(w)
        for w in (self.maiusculas, self.palavra, self.regex, self.figurina, self.escopo,
                  self.intervalo, self.onde):
            baixo.addWidget(w)
        baixo.addStretch(1)
        caixa.addWidget(self.linha_de_substituir)

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
        """`dica` cita teclas por `{id}`: segue o perfil e as trocas (`teclado.texto_vivo`)."""
        botao = QToolButton()
        botao.setText(texto)
        teclado.texto_vivo(botao, "setToolTip", dica)
        teclado.texto_vivo(botao, "setAccessibleName", dica)
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

    def abrir_substituir(self, texto: Optional[str] = None) -> None:
        """Ctrl+H: a barra com a linha de substituir; o foco no substituto se já há o que
        localizar."""
        self.abrir(texto)
        self.linha_de_substituir.show()
        if self.campo.text():
            self.substituto.setFocus(Qt.FocusReason.ShortcutFocusReason)
            self.substituto.selectAll()

    def esconder_substituir(self) -> None:
        self.linha_de_substituir.hide()

    @property
    def substituindo(self) -> bool:
        return not self.linha_de_substituir.isHidden()

    def escolher_escopo(self, escopo: str) -> None:
        self.escopo.setCurrentIndex(max(0, self.escopo.findData(escopo)))

    def rotular_selecao(self, pagina: Optional[int]) -> None:
        """O escopo Seleção diz de que página é a seleção guardada ("Seleção (p. 3)")."""
        self.escopo.setItemText(self.escopo.findData(bs.SELECAO),
                                "Seleção" if pagina is None else f"Seleção (p. {pagina})")

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
        estilo.papel(self.contador, "")
        self.contador.setToolTip("")
        if total == 0:
            self.contador.setText("nada" if self.campo.text() else "")
        elif atual is None:
            self.contador.setText(str(total))
        else:
            self.contador.setText(f"{atual + 1} de {total}")

    def mostrar_erro(self, mensagem: str) -> None:
        self.contador.setText("erro")
        estilo.papel(self.contador, "erro")
        self.contador.setToolTip(mensagem)

    def mostrar_dica(self, dica: str) -> None:
        self.campo.setToolTip(dica)

    def keyPressEvent(self, evento):
        tecla, mods = evento.key(), evento.modifiers()
        if tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.substituto.hasFocus():
            if mods & Qt.KeyboardModifier.ControlModifier:
                self.substituir_todas.emit()
            else:
                self.substituir.emit()
            return
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
