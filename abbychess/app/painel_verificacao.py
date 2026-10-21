"""O painel da verificação de texto: a palavra desconhecida, o recorte dela e o que fazer.

É a verificação do FineReader com o léxico do core, que sinaliza e nunca
corrige (ver `abbychess.verificacao`):

- **Enter** grava o texto do campo nos glifos da palavra, uma letra por glifo;
  só os que mudaram viram manuais. **Ctrl+Enter** faz o mesmo e ainda ensina
  cada glifo mudado como padrão deste livro.
- **Alt+↓** pula a palavra; **Alt+↑** volta (a fila no modo "palavras desconhecidas", F7).
- **Ctrl+Shift+I** ignora a palavra em toda a página nesta sessão.
- **Ctrl+Shift+D** põe a palavra no dicionário do livro (`lexico.txt`).
- O clique num glifo do recorte o abre no painel de treino, para dividir,
  juntar ou ajustar quando a palavra tem glifos de mais ou de menos.

Os atalhos são ações da janela (`app/teclado.py`); o painel oferece os comandos (`pedir_*`).
"""

from __future__ import annotations

from typing import List, Optional, Sequence

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPainter, QPen
from PySide6.QtWidgets import (QGridLayout, QLabel, QLineEdit, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from core.box_model import BoxEntry

from abbychess import verificacao as vf
from abbychess.app import cores, teclado
from abbychess.app.imagens import pixmap_de_cinza
from abbychess.app.painel_treino import FONTE_DE_SIMBOLOS

#: Altura do recorte da palavra no painel, em pixels de tela.
ALTURA_DO_RECORTE = 110


class _Campo(QLineEdit):
    """A palavra. Enter corrige e Ctrl+Enter corrige e ensina: as ações da janela ligadas em
    `teclas`, que o campo dispara (o Enter seria dele)."""

    def __init__(self):
        super().__init__()
        self.teclas = teclado.AcoesDaTecla()

    def event(self, evento):
        if self.teclas.sobrepor(evento):
            return True
        return super().event(evento)

    def keyPressEvent(self, evento):
        if self.teclas.disparar(evento):
            return
        super().keyPressEvent(evento)


class _Recorte(QLabel):
    """O recorte ampliado da palavra; o clique diz em que glifo caiu."""

    clicado = Signal(float, float)

    def mousePressEvent(self, evento):
        pixmap = self.pixmap()
        if (evento.button() == Qt.MouseButton.LeftButton and pixmap is not None
                and not pixmap.isNull()):
            esquerda = (self.width() - pixmap.width()) / 2
            topo = (self.height() - pixmap.height()) / 2
            self.clicado.emit(evento.position().x() - esquerda, evento.position().y() - topo)
        super().mousePressEvent(evento)


class PainelDeVerificacao(QWidget):
    corrigir = Signal(str)
    ensinar = Signal(str)
    pular = Signal()
    anterior = Signal()
    ignorar_todas = Signal()
    adicionar = Signal()
    #: O índice do box (na página) do glifo clicado no recorte.
    glifo_escolhido = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._glifos: List[tuple] = []  # (índice do box, x1, x2) no recorte ampliado
        self._ativo = False

        self.posicao = QLabel("")
        self.posicao.setWordWrap(True)
        self.recorte = _Recorte()
        self.recorte.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recorte.setMinimumSize(1, ALTURA_DO_RECORTE + 20)   # o pixmap não alarga o painel
        self.recorte.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.recorte.setStyleSheet("background: white; border: 1px solid #999;")
        self.recorte.setToolTip("Clique num glifo para abri-lo no Glifo.")
        self.recorte.clicado.connect(self._clicar)

        self.lido = QLabel("")
        self.lido.setFont(QFont(FONTE_DE_SIMBOLOS, 16))
        self.campo = _Campo()
        self.campo.setFont(QFont(FONTE_DE_SIMBOLOS, 18))

        # Em grade de duas colunas, com o rótulo curto e a tecla na dica: cabe no Inspetor de
        # 296 px (§3.1). Os botões não pegam o foco pelo Tab: o teclado é o do campo.
        self.botao_corrigir = self._botao("Corrigir", "Grava o texto nos glifos (Enter)",
                                          self.pedir_corrigir)
        self.botao_ensinar = self._botao("Corrigir e ensinar",
                                         "Grava e ensina os glifos mudados (Ctrl+Enter)",
                                         self.pedir_ensinar)
        self.botao_anterior = self._botao("◀ Anterior", "A palavra anterior (Alt+↑)",
                                          self.anterior.emit)
        self.botao_pular = self._botao("Pular ▶", "A próxima palavra, sem mudar esta (Alt+↓)",
                                       self.pular.emit)
        self.botao_todas = self._botao("Ignorar a palavra",
                                       "Ignora a palavra em toda a página, nesta sessão "
                                       "(Ctrl+Shift+I)", self.ignorar_todas.emit)
        self.botao_adicionar = self._botao("Ao dicionário",
                                           "Põe a palavra no dicionário do livro, lexico.txt "
                                           "(Ctrl+Shift+D)", self.adicionar.emit)
        grade = QGridLayout()
        grade.setSpacing(4)
        for n, botao in enumerate((self.botao_corrigir, self.botao_ensinar, self.botao_anterior,
                                   self.botao_pular, self.botao_todas, self.botao_adicionar)):
            grade.addWidget(botao, n // 2, n % 2)

        dica = QLabel("O léxico só aponta: nada é trocado sem você. Notação (Bxf6, exd5) "
                      "nunca aparece aqui. Um espaço separa a palavra em duas; com letras de "
                      "mais ou de menos, clique no glifo e divida ou junte no Glifo.")
        dica.setWordWrap(True)
        dica.setStyleSheet("color: #666;")

        caixa = QVBoxLayout(self)
        caixa.setContentsMargins(4, 4, 4, 4)
        caixa.addWidget(self.posicao)
        caixa.addWidget(self.recorte)
        caixa.addWidget(self.lido)
        caixa.addWidget(self.campo)
        caixa.addLayout(grade)
        caixa.addWidget(dica)
        caixa.addStretch(1)

        self.limpar("Escolha a fila de palavras desconhecidas (F7) para verificar o texto.")

    @staticmethod
    def _botao(texto: str, dica: str, funcao) -> QPushButton:
        botao = QPushButton(texto)
        botao.setToolTip(dica)
        botao.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        botao.clicked.connect(funcao)
        return botao

    def pedir_ignorar_todas(self) -> None:
        if self._ativo:
            self.ignorar_todas.emit()

    def pedir_adicionar(self) -> None:
        if self._ativo:
            self.adicionar.emit()

    # ------------------------------------------------------------------
    def mostrar(self, pagina: np.ndarray, boxes: Sequence[BoxEntry], palavra: vf.Desconhecida,
                posicao: int, total: int) -> None:
        """Mostra a palavra com os glifos contornados e põe o texto lido no campo."""
        self._ativo = True
        self.posicao.setText(f"Palavra {posicao + 1} de {total} — {palavra.explicacao}")
        recorte, (ox, oy) = vf.recorte_da_palavra(pagina, boxes, palavra.indices)
        pixmap = pixmap_de_cinza(recorte)
        fator = ALTURA_DO_RECORTE / max(pixmap.height(), 1)
        largura_util = max(self.recorte.width() - 10, 120)
        if pixmap.width() * fator > largura_util:
            fator = largura_util / max(pixmap.width(), 1)
        pixmap = pixmap.scaled(max(1, int(pixmap.width() * fator)),
                               max(1, int(pixmap.height() * fator)),
                               Qt.AspectRatioMode.IgnoreAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        pintor = QPainter(pixmap)
        self._glifos = []
        for i in palavra.indices:
            b = boxes[i]
            cor = cores.SEM_LEITURA if not b.char else cores.PALAVRA
            caneta = QPen(cor)
            caneta.setWidthF(1.5)
            pintor.setPen(caneta)
            x1, x2 = (b.x1 - ox) * fator, (b.x2 - ox) * fator
            pintor.drawRect(int(x1), int((b.y1 - oy) * fator), int(x2 - x1),
                            int((b.y2 - b.y1) * fator))
            self._glifos.append((i, x1, x2))
        pintor.end()
        self.recorte.setPixmap(pixmap)
        lidos = " ".join(boxes[i].char or "□" for i in palavra.indices)
        self.lido.setText(f"Glifos: {lidos}")
        # O glifo sem leitura não ganha letra inventada: falta digitá-la.
        texto = "".join(boxes[i].char for i in palavra.indices)
        self.campo.setText(texto)
        self.campo.selectAll()
        self.habilitar(True)
        self.campo.setFocus()

    def limpar(self, mensagem: str) -> None:
        self._ativo = False
        self._glifos = []
        self.posicao.setText(mensagem)
        self.recorte.clear()
        self.lido.setText("")
        self.campo.clear()
        self.habilitar(False)

    def habilitar(self, sim: bool) -> None:
        sim = sim and self._ativo
        for w in (self.campo, self.botao_corrigir, self.botao_ensinar, self.botao_anterior,
                  self.botao_pular, self.botao_todas, self.botao_adicionar):
            w.setEnabled(sim)

    # ------------------------------------------------------------------
    def glifo_em(self, x: float) -> Optional[int]:
        """O box do glifo na coluna `x` do recorte ampliado, ou o mais perto."""
        if not self._glifos:
            return None
        return min(self._glifos, key=lambda g: 0 if g[1] <= x <= g[2]
                   else min(abs(x - g[1]), abs(x - g[2])))[0]

    def _clicar(self, x: float, _y: float) -> None:
        indice = self.glifo_em(x)
        if indice is not None:
            self.glifo_escolhido.emit(indice)

    def _texto(self) -> Optional[str]:
        texto = self.campo.text().strip()
        return texto if self._ativo and texto else None

    def pedir_corrigir(self) -> None:
        texto = self._texto()
        if texto:
            self.corrigir.emit(texto)

    def pedir_ensinar(self) -> None:
        texto = self._texto()
        if texto:
            self.ensinar.emit(texto)
