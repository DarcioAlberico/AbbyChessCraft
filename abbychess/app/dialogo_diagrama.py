"""A conferência de um diagrama: o recorte impresso e a posição lida, lado a lado.

É o `ui/dialogo_diagrama.py` do PyBoxEditor refeito em PySide6, com a mesma
regra: o recorte e a leitura **na mesma escala**, para a conferência custar
segundos, e a correção casa a casa. O estado da edição (casas, desfazer, lado,
roque, legalidade) é o `core.tabuleiro_edicao.TabuleiroEdicao`, e o desenho da
posição é o `core.render_diagrama.desenhar`; aqui só se desenha por cima e se
despacham cliques e teclas.

- **Clicar seleciona; quem escreve é a tecla ou a paleta.** A letra da peça
  (maiúscula branca, minúscula preta) põe a peça na casa selecionada; Delete,
  Backspace ou espaço a esvaziam; as setas andam pelas casas. Com uma peça
  escolhida na paleta, o clique pinta; o botão direito esvazia.
- **O lado a jogar começa sem escolha** quando a página não diz. O FEN mostra
  `w`, porque o formato exige, e o aviso diz que é suposição até alguém
  escolher.
- **Conferido** (Ctrl+Enter) grava este diagrama e passa ao próximo por
  conferir. Fechar sem conferir não leva edição nenhuma.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QDialog, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QRadioButton, QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from core.tabuleiro_edicao import SIMBOLOS, TabuleiroEdicao

from abbychess.app.imagens import pixmap_de_cinza
from abbychess.diagramas import LADO_DA_LEGENDA, DiagramaLido, afirmar_lado

#: O lado de uma casa na tela; recorte e posição usam o mesmo.
LADO_CASA = 56

#: Abaixo disto a peça lida é pintada de laranja (o `CONFIANCA_BAIXA` do PyBoxEditor).
CONFIANCA_BAIXA = 0.55

GLIFOS = {"K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
          "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟"}
NOMES = {"K": "rei", "Q": "dama", "R": "torre", "B": "bispo", "N": "cavalo", "P": "peão"}

CASA_CLARA, CASA_ESCURA = QColor("#F0D9B5"), QColor("#B58863")
COR_CORRIGIDA = QColor(39, 174, 96, 90)    # verde: corrigida por você
COR_ARBITRADA = QColor(192, 57, 43, 90)    # vermelho: trocada pela legalidade
COR_DUVIDA = QColor(230, 126, 34, 90)      # laranja: leitura duvidosa
COR_SELECAO = QColor(241, 196, 15)         # amarelo: a casa selecionada


class TabuleiroConferivel(QWidget):
    """A posição lida, desenhada pela fonte de diagrama do PyBoxEditor e editável."""

    mudou = Signal()

    def __init__(self, tabuleiro: TabuleiroEdicao, orientacao: str = "branca", parent=None):
        super().__init__(parent)
        self.tabuleiro = tabuleiro
        self.orientacao = orientacao
        self.selecionada: Optional[Tuple[int, int]] = None
        #: A peça escolhida na paleta: clique pinta com ela; "" pinta vazio.
        self.pincel: Optional[str] = None
        self._desenho: Optional[QPixmap] = None
        self._desenho_de: str = ""
        self.setFixedSize(8 * LADO_CASA, 8 * LADO_CASA)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def trocar(self, tabuleiro: TabuleiroEdicao, orientacao: str) -> None:
        self.tabuleiro, self.orientacao, self.selecionada = tabuleiro, orientacao, None
        self._desenho_de = ""
        self.update()

    # -- geometria ---------------------------------------------------------
    def casa_em(self, x: float, y: float) -> Optional[Tuple[int, int]]:
        """A casa (linha 0 = 8ª fila, coluna 0 = a) sob o ponto do widget."""
        coluna, linha = int(x // LADO_CASA), int(y // LADO_CASA)
        if not (0 <= linha < 8 and 0 <= coluna < 8):
            return None
        return (7 - linha, 7 - coluna) if self.orientacao == "preta" else (linha, coluna)

    def retangulo(self, linha: int, coluna: int) -> QRect:
        if self.orientacao == "preta":
            linha, coluna = 7 - linha, 7 - coluna
        return QRect(coluna * LADO_CASA, linha * LADO_CASA, LADO_CASA, LADO_CASA)

    # -- desenho -----------------------------------------------------------
    def _posicao(self) -> QPixmap:
        """O tabuleiro pela `render_diagrama.desenhar`, refeito só quando as peças mudam."""
        fen = self.tabuleiro.tabuleiro().board_fen()
        chave = f"{fen} {self.orientacao}"
        if self._desenho is None or self._desenho_de != chave:
            self._desenho, self._desenho_de = _desenhar_posicao(fen, self.orientacao), chave
        return self._desenho

    def paintEvent(self, _evento):
        pintor = QPainter(self)
        desenho = self._posicao()
        if desenho is not None:
            pintor.drawPixmap(self.rect(), desenho)
        else:
            self._pintar_com_glifos(pintor)
        for casa in self.tabuleiro.casas:
            cor = None
            if casa.corrigida:
                cor = COR_CORRIGIDA
            elif casa.arbitrada:
                cor = COR_ARBITRADA
            elif casa.simbolo and casa.confianca < CONFIANCA_BAIXA:
                cor = COR_DUVIDA
            if cor is not None:
                pintor.fillRect(self.retangulo(casa.linha, casa.coluna), cor)
        if self.selecionada is not None:
            caneta = QPen(COR_SELECAO)
            caneta.setWidth(3)
            pintor.setPen(caneta)
            pintor.drawRect(self.retangulo(*self.selecionada).adjusted(1, 1, -2, -2))
        pintor.end()

    def _pintar_com_glifos(self, pintor: QPainter) -> None:
        """Sem a fonte de diagrama, casas lisas e as figurinas Unicode."""
        fonte = QFont()
        fonte.setPixelSize(int(LADO_CASA * 0.8))
        pintor.setFont(fonte)
        for casa in self.tabuleiro.casas:
            retangulo = self.retangulo(casa.linha, casa.coluna)
            pintor.fillRect(retangulo, CASA_CLARA if (casa.linha + casa.coluna) % 2 == 0
                            else CASA_ESCURA)
            if casa.simbolo:
                pintor.setPen(Qt.GlobalColor.black)
                pintor.drawText(QRectF(retangulo), Qt.AlignmentFlag.AlignCenter,
                                GLIFOS[casa.simbolo])

    # -- edição ------------------------------------------------------------
    def mousePressEvent(self, evento):
        casa = self.casa_em(evento.position().x(), evento.position().y())
        if casa is None:
            return
        self.setFocus()
        self.selecionada = casa
        if evento.button() == Qt.MouseButton.RightButton:
            self.tabuleiro.limpar(*casa)
            self.mudou.emit()
        elif self.pincel is not None:
            atual = self.tabuleiro.casa(*casa).simbolo
            # Clicar de novo com a mesma peça alterna entre ela e a casa vazia.
            self.tabuleiro.colocar(*casa, None if atual == self.pincel or not self.pincel
                                   else self.pincel)
            self.mudou.emit()
        self.update()

    def keyPressEvent(self, evento):
        if evento.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            super().keyPressEvent(evento)
            return
        tecla, texto = evento.key(), evento.text()
        setas = {Qt.Key.Key_Left: (0, -1), Qt.Key.Key_Right: (0, 1),
                 Qt.Key.Key_Up: (-1, 0), Qt.Key.Key_Down: (1, 0)}
        if tecla in setas:
            linha, coluna = self.selecionada or (0, 0)
            dl, dc = setas[tecla]
            if self.orientacao == "preta":
                dl, dc = -dl, -dc
            self.selecionada = (min(7, max(0, linha + dl)), min(7, max(0, coluna + dc)))
            self.update()
            return
        if self.selecionada is None:
            super().keyPressEvent(evento)
            return
        if texto and texto in SIMBOLOS:
            self.tabuleiro.colocar(*self.selecionada, texto)
        elif tecla in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace, Qt.Key.Key_Space):
            self.tabuleiro.limpar(*self.selecionada)
        else:
            super().keyPressEvent(evento)
            return
        self.mudou.emit()
        self.update()


def _desenhar_posicao(fen_das_pecas: str, orientacao: str) -> Optional[QPixmap]:
    try:
        from core import render_diagrama

        png, _largura, _altura = render_diagrama.desenhar(
            fen_das_pecas, lado_px=8 * LADO_CASA, moldura="sem", orientacao=orientacao, tons=0)
    except Exception:  # fonte de diagrama ausente ou ilegível: o widget cai nos glifos
        return None
    pixmap = QPixmap()
    return pixmap if pixmap.loadFromData(png, "PNG") else None


def recorte_do_diagrama(matriz: np.ndarray, caixa) -> QPixmap:
    """O tabuleiro impresso no mesmo tamanho da posição desenhada ao lado."""
    x1, y1, x2, y2 = caixa
    pedaco = matriz[max(0, y1):y2, max(0, x1):x2]
    if not pedaco.size:
        return QPixmap()
    return pixmap_de_cinza(pedaco).scaled(
        8 * LADO_CASA, 8 * LADO_CASA, Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation)


class DialogoDeDiagrama(QDialog):
    """Confere os diagramas da página, um por vez. Emite cada conferência."""

    #: O índice do diagrama, o tabuleiro conferido e se as 64 casas viram amostra.
    conferido = Signal(int, object, bool)

    def __init__(self, matriz: np.ndarray, diagramas: List[DiagramaLido], indice: int = 0,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Conferir diagrama")
        self.matriz = matriz
        self.diagramas = list(diagramas)
        self.atual = indice
        #: Um tabuleiro por diagrama, criado na primeira visita: ir e voltar não perde edição.
        self.tabuleiros: Dict[int, TabuleiroEdicao] = {}
        self._montar()
        self._mostrar()

    # ------------------------------------------------------------------
    def tabuleiro(self, indice: Optional[int] = None) -> TabuleiroEdicao:
        indice = self.atual if indice is None else indice
        if indice not in self.tabuleiros:
            self.tabuleiros[indice] = self.diagramas[indice].edicao()
        return self.tabuleiros[indice]

    @property
    def diagrama(self) -> DiagramaLido:
        return self.diagramas[self.atual]

    def _montar(self) -> None:
        self.cabecalho = QLabel()
        self.cabecalho.setWordWrap(True)
        fonte = self.cabecalho.font()
        fonte.setBold(True)
        self.cabecalho.setFont(fonte)

        self.recorte = QLabel()
        self.recorte.setFixedSize(8 * LADO_CASA, 8 * LADO_CASA)
        self.recorte.setToolTip("O diagrama como está impresso na página")
        self.posicao = TabuleiroConferivel(self.tabuleiro(), self.diagrama.orientacao)
        self.posicao.setToolTip("A posição lida. Clique numa casa e digite a peça.")
        self.posicao.mudou.connect(self._mostrar)

        lado_a_lado = QHBoxLayout()
        lado_a_lado.addWidget(_com_titulo("Impresso", self.recorte))
        lado_a_lado.addWidget(_com_titulo("Lido", self.posicao))
        lado_a_lado.addWidget(self._montar_controles())

        self.fen = QLineEdit()
        self.fen.setReadOnly(True)
        self.fen.setFont(QFont("Consolas", 10))
        copiar = QPushButton("Copiar FEN")
        copiar.clicked.connect(lambda: QApplication.clipboard().setText(self.fen.text()))
        linha_fen = QHBoxLayout()
        linha_fen.addWidget(QLabel("FEN:"))
        linha_fen.addWidget(self.fen, 1)
        linha_fen.addWidget(copiar)

        self.avisos = QLabel()
        self.avisos.setWordWrap(True)
        self.avisos.setTextFormat(Qt.TextFormat.PlainText)
        self.avisos.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        self.btn_anterior = QPushButton("◀ Anterior")
        self.btn_anterior.clicked.connect(lambda: self._ir(-1))
        self.btn_seguinte = QPushButton("Seguinte ▶")
        self.btn_seguinte.clicked.connect(lambda: self._ir(+1))
        self.btn_desfazer = QPushButton("Desfazer")
        self.btn_desfazer.clicked.connect(self._desfazer)
        self.btn_refazer = QPushButton("Refazer")
        self.btn_refazer.clicked.connect(self._refazer)
        self.btn_conferido = QPushButton("Conferido (Ctrl+Enter)")
        self.btn_conferido.clicked.connect(self.confirmar)
        self.btn_conferido.setDefault(True)
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.reject)
        botoes = QHBoxLayout()
        for botao in (self.btn_anterior, self.btn_seguinte, self.btn_desfazer, self.btn_refazer):
            botoes.addWidget(botao)
        botoes.addStretch(1)
        botoes.addWidget(self.btn_conferido)
        botoes.addWidget(fechar)

        corpo = QVBoxLayout(self)
        corpo.addWidget(self.cabecalho)
        corpo.addLayout(lado_a_lado)
        corpo.addLayout(linha_fen)
        corpo.addWidget(self.avisos)
        corpo.addLayout(botoes)

        for atalho, funcao in (("Ctrl+Return", self.confirmar), ("Ctrl+Enter", self.confirmar),
                               ("Ctrl+Z", self._desfazer), ("Ctrl+Y", self._refazer),
                               ("Ctrl+Shift+Z", self._refazer), ("PgDown", lambda: self._ir(+1)),
                               ("PgUp", lambda: self._ir(-1))):
            QShortcut(QKeySequence(atalho), self, activated=funcao)

    def _montar_controles(self) -> QWidget:
        painel = QWidget()
        caixa = QVBoxLayout(painel)
        caixa.setContentsMargins(0, 0, 0, 0)

        paleta = QGroupBox("Pintar com")
        grade = QGridLayout(paleta)
        self.botoes_paleta: Dict[str, QToolButton] = {}
        for coluna, simbolo in enumerate("KQRBNP"):
            for linha, s in enumerate((simbolo, simbolo.lower())):
                botao = QToolButton()
                botao.setText(GLIFOS[s])
                botao.setFont(QFont("Segoe UI Symbol", 16))
                botao.setCheckable(True)
                cor = "branco" if s.isupper() else "preto"
                botao.setToolTip(f"{NOMES[simbolo].capitalize()} {cor} (tecla {s})")
                botao.clicked.connect(lambda _=False, s=s: self._escolher(s))
                grade.addWidget(botao, linha, coluna)
                self.botoes_paleta[s] = botao
        self.btn_vazia = QToolButton()
        self.btn_vazia.setText("vazia")
        self.btn_vazia.setCheckable(True)
        self.btn_vazia.setToolTip("Clique esvazia a casa (Delete faz o mesmo)")
        self.btn_vazia.clicked.connect(lambda: self._escolher(""))
        grade.addWidget(self.btn_vazia, 2, 0, 1, 6)
        caixa.addWidget(paleta)

        lado = QGroupBox("Lado a jogar")
        coluna_lado = QVBoxLayout(lado)
        self.grupo_lado = QButtonGroup(self)
        self.radio_brancas = QRadioButton("Brancas jogam")
        self.radio_pretas = QRadioButton("Pretas jogam")
        for valor, radio in (("w", self.radio_brancas), ("b", self.radio_pretas)):
            self.grupo_lado.addButton(radio)
            radio.clicked.connect(lambda _=False, v=valor: self._mudar_lado(v))
            coluna_lado.addWidget(radio)
        self.origem_do_lado = QLabel()
        self.origem_do_lado.setWordWrap(True)
        coluna_lado.addWidget(self.origem_do_lado)
        caixa.addWidget(lado)

        roque = QGroupBox("Roque")
        linha_roque = QHBoxLayout(roque)
        self.checks_roque: Dict[str, QCheckBox] = {}
        for letra, texto in (("K", "O-O ♔"), ("Q", "O-O-O ♔"), ("k", "O-O ♚"), ("q", "O-O-O ♚")):
            check = QCheckBox(texto)
            check.clicked.connect(lambda _=False, letra=letra: self._mudar_roque(letra))
            linha_roque.addWidget(check)
            self.checks_roque[letra] = check
        caixa.addWidget(roque)

        self.check_inteiro = QCheckBox("Conferi as 64 casas: guardar todas como\namostras do livro")
        self.check_inteiro.setToolTip(
            "Sem isto, só as casas corrigidas viram amostra. As amostras ficam na pasta "
            "do projeto (diagramas/), nunca na base global do PyBoxEditor.")
        caixa.addWidget(self.check_inteiro)
        caixa.addStretch(1)
        return painel

    # ------------------------------------------------------------------
    def _escolher(self, simbolo: str) -> None:
        self.posicao.pincel = None if self.posicao.pincel == simbolo else simbolo
        self._mostrar()
        self.posicao.setFocus()

    def _mudar_lado(self, lado: str) -> None:
        afirmar_lado(self.tabuleiro(), lado)
        self._mostrar()

    def _mudar_roque(self, letra: str) -> None:
        self.tabuleiro().alternar_roque(letra)
        self._mostrar()

    def _desfazer(self) -> None:
        if self.tabuleiro().desfazer():
            self._mostrar()

    def _refazer(self) -> None:
        if self.tabuleiro().refazer():
            self._mostrar()

    def _ir(self, passo: int) -> None:
        if len(self.diagramas) < 2:
            return
        self.atual = (self.atual + passo) % len(self.diagramas)
        self.posicao.trocar(self.tabuleiro(), self.diagrama.orientacao)
        self.check_inteiro.setChecked(False)
        self._mostrar()

    def confirmar(self) -> None:
        """Grava este diagrama como conferido e vai ao próximo por conferir."""
        tabuleiro = self.tabuleiro()
        self.conferido.emit(self.atual, tabuleiro, self.check_inteiro.isChecked())
        self.diagramas[self.atual] = self.diagrama.conferir(tabuleiro)
        self.tabuleiros[self.atual] = self.diagramas[self.atual].edicao()
        faltam = [i for i in range(len(self.diagramas)) if not self.diagramas[i].conferido]
        if not faltam:
            self.accept()
            return
        seguinte = next((i for i in faltam if i > self.atual), faltam[0])
        self._ir(seguinte - self.atual)

    # ------------------------------------------------------------------
    def _mostrar(self) -> None:
        d, tabuleiro = self.diagrama, self.tabuleiro()
        partes = [f"Diagrama {self.atual + 1} de {len(self.diagramas)}", tabuleiro.resumo()]
        if d.conferido:
            partes.append("conferido")
        self.cabecalho.setText("  —  ".join(partes))
        self.recorte.setPixmap(recorte_do_diagrama(self.matriz, d.caixa))
        self.fen.setText(tabuleiro.fen())
        self.avisos.setText("\n".join(self.avisos_do_diagrama()))

        self.grupo_lado.setExclusive(False)
        self.radio_brancas.setChecked(tabuleiro.lado_origem != "convencao" and tabuleiro.lado == "w")
        self.radio_pretas.setChecked(tabuleiro.lado_origem != "convencao" and tabuleiro.lado == "b")
        self.grupo_lado.setExclusive(True)
        if tabuleiro.lado_origem == "convencao":
            self.origem_do_lado.setText("A página não diz. Escolha: até lá o FEN sai com "
                                        "'w' marcado como assumido.")
            self.origem_do_lado.setStyleSheet("color: #c0392b;")
        elif tabuleiro.lado_origem == LADO_DA_LEGENDA:
            trecho = f": “{d.lado_trecho}”" if d.lado_trecho else ""
            self.origem_do_lado.setText(f"Da legenda da página{trecho}. Confira.")
            self.origem_do_lado.setStyleSheet("color: #e67e22;")
        else:
            self.origem_do_lado.setText("Informado por você.")
            self.origem_do_lado.setStyleSheet("")

        possiveis = tabuleiro.roques_possiveis()
        for letra, check in self.checks_roque.items():
            check.setChecked(letra in tabuleiro.roque)
            check.setEnabled(letra in possiveis)
        for simbolo, botao in self.botoes_paleta.items():
            botao.setChecked(self.posicao.pincel == simbolo)
        self.btn_vazia.setChecked(self.posicao.pincel == "")
        self.btn_desfazer.setEnabled(tabuleiro.pode_desfazer)
        self.btn_refazer.setEnabled(tabuleiro.pode_refazer)
        self.btn_anterior.setEnabled(len(self.diagramas) > 1)
        self.btn_seguinte.setEnabled(len(self.diagramas) > 1)
        self.posicao.update()

    def avisos_do_diagrama(self) -> List[str]:
        """O que a página deixou em aberto, o que o leitor desconfia e o que o FEN supõe."""
        d, tabuleiro = self.diagrama, self.tabuleiro()
        avisos = []
        if not d.orientacao_confirmada:
            avisos.append("Orientação não confirmada: não há coordenadas legíveis em volta do "
                          "tabuleiro, e a leitura supõe as brancas embaixo. Se o diagrama estiver "
                          "do lado das pretas, a posição sai girada 180°.")
        if d.motivo and not d.conferido:
            avisos.append(f"O leitor não confia nesta leitura: {d.motivo}. Confira casa a casa.")
        avisos.extend(tabuleiro.avisos())
        legenda = []
        if any(c.corrigida for c in tabuleiro.casas):
            legenda.append("verde: corrigida por você")
        if any(c.arbitrada and not c.corrigida for c in tabuleiro.casas):
            legenda.append("vermelho: trocada pela legalidade")
        if any(c.simbolo and not c.corrigida and c.confianca < CONFIANCA_BAIXA
               for c in tabuleiro.casas):
            legenda.append("laranja: leitura duvidosa")
        if legenda:
            avisos.append("   ".join(legenda))
        return avisos


def _com_titulo(titulo: str, widget: QWidget) -> QWidget:
    caixa = QWidget()
    coluna = QVBoxLayout(caixa)
    coluna.setContentsMargins(0, 0, 0, 0)
    coluna.addWidget(QLabel(titulo))
    coluna.addWidget(widget)
    coluna.addStretch(1)
    return caixa
