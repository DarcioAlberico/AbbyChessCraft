"""O editor Diagrama do Inspetor (SPEC §10): a conferência de um diagrama, sem janela própria.

Era um diálogo modal com o recorte e a leitura lado a lado (o `ui/dialogo_diagrama.py` do
PyBoxEditor refeito em PySide6). Agora o recorte é a própria **Imagem**, que dá zoom no
diagrama (`VisorDePagina.enquadrar`) e continua navegável (CA-10.2): o zoom, a rolagem e o
resto da janela valem enquanto se confere. O estado da edição (casas, desfazer, lado, roque,
legalidade) é o `core.tabuleiro_edicao.TabuleiroEdicao`, e o desenho da posição é o
`core.render_diagrama.desenhar`; aqui só se desenha por cima e se despacham cliques e teclas.

- **Clicar seleciona; quem escreve é a tecla ou a paleta.** A letra da peça (maiúscula
  branca, minúscula preta) põe a peça na casa selecionada; Delete, Backspace ou espaço a
  esvaziam; as setas andam pelas casas. Com uma peça escolhida na paleta, o clique pinta; o
  botão direito esvazia.
- **O lado a jogar começa sem escolha** quando a página não diz. O FEN mostra `w`, porque o
  formato exige, e o aviso diz que é suposição até alguém escolher.
- **A validação pelos lances** (`abbychess.lances`) é refeita a cada casa corrigida: o
  editor diz se os lances do texto passam nesta posição.
- **Conferido** (Ctrl+Enter) grava este diagrama e passa ao próximo por conferir (o F8);
  PgUp e PgDn vão ao diagrama anterior ou seguinte **do livro**. Sair sem conferir não leva
  edição nenhuma.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton,
                               QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from core.tabuleiro_edicao import SIMBOLOS, TabuleiroEdicao

from abbychess import lances
from abbychess.diagramas import LADO_DA_LEGENDA, DiagramaLido, afirmar_lado
from abbychess.app import estilo

#: O lado de uma casa no Inspetor (o tabuleiro cabe nos 296 px de 1366, §3.1).
LADO_CASA = 30

#: Abaixo disto a peça lida é pintada de laranja (o `CONFIANCA_BAIXA` do PyBoxEditor).
CONFIANCA_BAIXA = 0.55

GLIFOS = {"K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
          "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟"}
NOMES = {"K": "rei", "Q": "dama", "R": "torre", "B": "bispo", "N": "cavalo", "P": "peão"}

CASA_CLARA, CASA_ESCURA = estilo.CASA_CLARA, estilo.CASA_ESCURA
COR_CORRIGIDA = estilo.CASA_CORRIGIDA      # verde: corrigida por você
COR_ARBITRADA = estilo.CASA_ARBITRADA      # vermelho: trocada pela legalidade
COR_DUVIDA = estilo.CASA_DUVIDOSA          # laranja: leitura duvidosa
COR_SELECAO = estilo.SELECIONADO           # amarelo: a casa selecionada


class TabuleiroConferivel(QWidget):
    """A posição lida, desenhada pela fonte de diagrama do PyBoxEditor e editável."""

    mudou = Signal()

    def __init__(self, tabuleiro: TabuleiroEdicao, orientacao: str = "branca", parent=None,
                 lado_casa: int = LADO_CASA):
        super().__init__(parent)
        self.tabuleiro = tabuleiro
        self.orientacao = orientacao
        self.lado = lado_casa
        self.selecionada: Optional[Tuple[int, int]] = None
        #: A peça escolhida na paleta: clique pinta com ela; "" pinta vazio.
        self.pincel: Optional[str] = None
        self._desenho: Optional[QPixmap] = None
        self._desenho_de: str = ""
        self.setFixedSize(8 * lado_casa, 8 * lado_casa)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Tabuleiro em conferência (letra da peça, Delete esvazia)")

    def trocar(self, tabuleiro: TabuleiroEdicao, orientacao: str) -> None:
        self.tabuleiro, self.orientacao, self.selecionada = tabuleiro, orientacao, None
        self._desenho_de = ""
        self.update()

    # -- geometria ---------------------------------------------------------
    def casa_em(self, x: float, y: float) -> Optional[Tuple[int, int]]:
        """A casa (linha 0 = 8ª fila, coluna 0 = a) sob o ponto do widget."""
        coluna, linha = int(x // self.lado), int(y // self.lado)
        if not (0 <= linha < 8 and 0 <= coluna < 8):
            return None
        return (7 - linha, 7 - coluna) if self.orientacao == "preta" else (linha, coluna)

    def retangulo(self, linha: int, coluna: int) -> QRect:
        if self.orientacao == "preta":
            linha, coluna = 7 - linha, 7 - coluna
        return QRect(coluna * self.lado, linha * self.lado, self.lado, self.lado)

    # -- desenho -----------------------------------------------------------
    def _posicao(self) -> Optional[QPixmap]:
        """O tabuleiro pela `render_diagrama.desenhar`, refeito só quando as peças mudam."""
        fen = self.tabuleiro.tabuleiro().board_fen()
        chave = f"{fen} {self.orientacao}"
        if self._desenho is None or self._desenho_de != chave:
            self._desenho = _desenhar_posicao(fen, self.orientacao, 8 * self.lado)
            self._desenho_de = chave
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
        fonte.setPixelSize(int(self.lado * 0.8))
        pintor.setFont(fonte)
        for casa in self.tabuleiro.casas:
            retangulo = self.retangulo(casa.linha, casa.coluna)
            pintor.fillRect(retangulo, CASA_CLARA if (casa.linha + casa.coluna) % 2 == 0
                            else CASA_ESCURA)
            if casa.simbolo:
                pintor.setPen(estilo.TINTA)
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


def _desenhar_posicao(fen_das_pecas: str, orientacao: str, lado_px: int) -> Optional[QPixmap]:
    try:
        from core import render_diagrama

        png, _largura, _altura = render_diagrama.desenhar(
            fen_das_pecas, lado_px=lado_px, moldura="sem", orientacao=orientacao, tons=0)
    except Exception:  # fonte de diagrama ausente ou ilegível: o widget cai nos glifos
        return None
    pixmap = QPixmap()
    return pixmap if pixmap.loadFromData(png, "PNG") else None


class EditorDeDiagrama(QWidget):
    """Confere os diagramas da página, um por vez, no Inspetor."""

    #: A caixa do diagrama, o tabuleiro conferido e se as 64 casas viram amostra; emitido
    #: depois de `aplicar` gravar.
    conferido = Signal(object, object, bool)
    #: A conferência terminou nesta página: o próximo por conferir é do livro (o F8).
    terminou = Signal()
    #: O diagrama mostrado: a caixa dele, para a Imagem enquadrar.
    diagrama_mostrado = Signal(object)
    #: PgUp (−1) ou PgDn (+1) na ponta da página: o diagrama vizinho é de outra página.
    fora_da_pagina = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.diagramas: List[DiagramaLido] = []
        #: A primeira linha de lances do texto depois de cada diagrama (§10).
        self.linhas: List[List[lances.Lance]] = []
        self.atual = 0
        #: Um tabuleiro por diagrama, criado na primeira visita: ir e voltar não perde edição.
        self.tabuleiros: Dict[int, TabuleiroEdicao] = {}
        #: Quem grava: `(caixa, tabuleiro, tudo) -> bool` (`ControladorDeDiagramas.aplicar`).
        #: Falso, e o editor não marca nada como conferido.
        self.aplicar = None
        self._montar()
        self._mostrar()

    # ------------------------------------------------------------------
    @property
    def aberto(self) -> bool:
        """Há diagramas em conferência."""
        return bool(self.diagramas)

    def abrir(self, diagramas: List[DiagramaLido], indice: int = 0,
              linhas: Optional[List[List[lances.Lance]]] = None) -> None:
        """Os diagramas da página, no `indice`. Os mesmos diagramas de antes (outro clique
        na mesma página, o F8, a aba) mantêm o que estava em edição; outros o descartam."""
        mesmos = self.aberto and _chaves(diagramas) == _chaves(self.diagramas)
        self.diagramas = list(diagramas)
        self.linhas = list(linhas or [])
        if not mesmos:
            self.tabuleiros = {}
        self.atual = max(0, min(indice, len(self.diagramas) - 1))
        self.check_inteiro.setChecked(False)
        if self.diagramas:
            self.posicao.trocar(self.tabuleiro(), self.diagrama.orientacao)
        self._mostrar()
        if self.diagramas:
            self.diagrama_mostrado.emit(self.diagrama.caixa)

    def sincronizar(self, diagramas: List[DiagramaLido]) -> bool:
        """A página mudou por baixo (um desfazer, o lado pela legenda, a releitura). Com os
        mesmos diagramas no mesmo lugar, o editor passa a mostrar os de agora (o tabuleiro
        sem edição é refeito); com outros, fecha. Devolve se continuou aberto."""
        if not self.aberto:
            return False
        if _chaves(diagramas) != _chaves(self.diagramas):
            self.fechar()
            return False
        for i, d in enumerate(diagramas):
            if d != self.diagramas[i] and not (i in self.tabuleiros
                                               and self.tabuleiros[i].pode_desfazer):
                self.tabuleiros.pop(i, None)
        self.diagramas = list(diagramas)
        self.posicao.trocar(self.tabuleiro(), self.diagrama.orientacao)
        self._mostrar()
        return True

    def fechar(self) -> None:
        """Sem diagramas (a página trocou): nada em edição."""
        self.diagramas, self.linhas, self.tabuleiros, self.atual = [], [], {}, 0
        self._mostrar()

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

        self.posicao = TabuleiroConferivel(TabuleiroEdicao.de_fen("8/8/8/8/8/8/8/8"))
        self.posicao.setToolTip("A posição lida; o impresso está na Imagem. Clique numa casa "
                                "e digite a peça.")
        self.posicao.mudou.connect(self._mostrar)

        self.fen = QLineEdit()
        self.fen.setReadOnly(True)
        self.fen.setFont(QFont("Consolas", 9))
        self.fen.setAccessibleName("FEN do diagrama")
        copiar = QPushButton("FEN")
        copiar.setToolTip("Copiar o FEN")
        copiar.clicked.connect(lambda: QApplication.clipboard().setText(self.fen.text()))
        copiar_pgn = QPushButton("PGN")
        copiar_pgn.setToolTip("Copiar o PGN: a posição e os lances do texto que passaram na "
                              "validação")
        copiar_pgn.clicked.connect(lambda: QApplication.clipboard().setText(self.pgn()))
        linha_fen = QHBoxLayout()
        linha_fen.addWidget(self.fen, 1)
        linha_fen.addWidget(copiar)
        linha_fen.addWidget(copiar_pgn)

        self.avisos = QLabel()
        self.avisos.setWordWrap(True)
        self.avisos.setTextFormat(Qt.TextFormat.PlainText)
        self.avisos.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        self.btn_anterior = QPushButton("◀")
        self.btn_anterior.setToolTip("O diagrama anterior do livro (PgUp)")
        self.btn_anterior.clicked.connect(lambda: self.ir(-1))
        self.btn_seguinte = QPushButton("▶")
        self.btn_seguinte.setToolTip("O diagrama seguinte do livro (PgDn)")
        self.btn_seguinte.clicked.connect(lambda: self.ir(+1))
        self.btn_desfazer = QPushButton("Desfazer")
        self.btn_desfazer.clicked.connect(self.desfazer)
        self.btn_refazer = QPushButton("Refazer")
        self.btn_refazer.clicked.connect(self.refazer)
        self.btn_conferido = QPushButton("Conferido")
        self.btn_conferido.setToolTip("Grava o diagrama e vai ao próximo por conferir "
                                      "(Ctrl+Enter)")
        self.btn_conferido.clicked.connect(self.confirmar)
        navegar = QHBoxLayout()
        for botao in (self.btn_anterior, self.btn_seguinte, self.btn_desfazer, self.btn_refazer):
            navegar.addWidget(botao)

        corpo = QVBoxLayout(self)
        corpo.setContentsMargins(0, 0, 0, 0)
        corpo.addWidget(self.cabecalho)
        corpo.addWidget(self.posicao, 0, Qt.AlignmentFlag.AlignHCenter)
        corpo.addLayout(navegar)
        corpo.addWidget(self.btn_conferido)
        corpo.addLayout(linha_fen)
        corpo.addWidget(self.avisos)
        corpo.addWidget(self._montar_controles())
        corpo.addStretch(1)

    def _montar_controles(self) -> QWidget:
        painel = QWidget()
        caixa = QVBoxLayout(painel)
        caixa.setContentsMargins(0, 0, 0, 0)

        paleta = QGroupBox("Pintar com")
        grade = QGridLayout(paleta)
        grade.setSpacing(2)
        self.botoes_paleta: Dict[str, QToolButton] = {}
        for coluna, simbolo in enumerate("KQRBNP"):
            for linha, s in enumerate((simbolo, simbolo.lower())):
                botao = QToolButton()
                botao.setText(GLIFOS[s])
                botao.setFont(QFont("Segoe UI Symbol", 13))
                botao.setCheckable(True)
                cor = "branco" if s.isupper() else "preto"
                botao.setToolTip(f"{NOMES[simbolo].capitalize()} {cor} (tecla {s})")
                botao.setAccessibleName(f"{NOMES[simbolo]} {cor}")
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
        grade_roque = QGridLayout(roque)
        self.checks_roque: Dict[str, QCheckBox] = {}
        for n, (letra, texto) in enumerate((("K", "O-O ♔"), ("Q", "O-O-O ♔"),
                                            ("k", "O-O ♚"), ("q", "O-O-O ♚"))):
            check = QCheckBox(texto)
            check.clicked.connect(lambda _=False, letra=letra: self._mudar_roque(letra))
            grade_roque.addWidget(check, n // 2, n % 2)
            self.checks_roque[letra] = check
        self.roque_inferido = QLabel()
        self.roque_inferido.setWordWrap(True)
        self.btn_roque_inferido = QPushButton("Usar o inferido")
        self.btn_roque_inferido.setToolTip("Marca o roque que rei e torre nas casas iniciais "
                                           "sugerem. Sem isto, o FEN sai sem roque.")
        self.btn_roque_inferido.clicked.connect(self._usar_roque_inferido)
        grade_roque.addWidget(self.roque_inferido, 2, 0, 1, 2)
        grade_roque.addWidget(self.btn_roque_inferido, 3, 0, 1, 2)
        caixa.addWidget(roque)

        self.check_inteiro = QCheckBox("Conferi as 64 casas: guardar todas como amostras")
        self.check_inteiro.setToolTip(
            "Sem isto, só as casas corrigidas viram amostra. As amostras ficam na pasta "
            "do projeto (diagramas/), nunca na base global do PyBoxEditor.")
        caixa.addWidget(self.check_inteiro)
        return painel

    # ------------------------------------------------------------------
    def _escolher(self, simbolo: str) -> None:
        self.posicao.pincel = None if self.posicao.pincel == simbolo else simbolo
        self._mostrar()
        self.posicao.setFocus()

    def _mudar_lado(self, lado: str) -> None:
        if self.aberto:
            afirmar_lado(self.tabuleiro(), lado)
        self._mostrar()

    def _mudar_roque(self, letra: str) -> None:
        if self.aberto:
            self.tabuleiro().alternar_roque(letra)
        self._mostrar()

    def _usar_roque_inferido(self) -> None:
        if self.aberto:
            tabuleiro = self.tabuleiro()
            tabuleiro.definir_roque(lances.roque_inferido(tabuleiro.fen()))
        self._mostrar()

    @property
    def pode_desfazer(self) -> bool:
        return self.aberto and self.tabuleiro().pode_desfazer

    @property
    def pode_refazer(self) -> bool:
        return self.aberto and self.tabuleiro().pode_refazer

    def desfazer(self) -> None:
        if self.pode_desfazer and self.tabuleiro().desfazer():
            self._mostrar()

    def refazer(self) -> None:
        if self.pode_refazer and self.tabuleiro().refazer():
            self._mostrar()

    def ir(self, passo: int) -> None:
        """PgUp (−1) e PgDn (+1): o diagrama vizinho; na ponta da página, o do livro."""
        if not self.aberto:
            return
        alvo = self.atual + passo
        if not 0 <= alvo < len(self.diagramas):
            self.fora_da_pagina.emit(passo)
            return
        self._ir_para(alvo)

    def _ir_para(self, indice: int) -> None:
        self.atual = indice
        self.posicao.trocar(self.tabuleiro(), self.diagrama.orientacao)
        self.check_inteiro.setChecked(False)
        self._mostrar()
        self.diagrama_mostrado.emit(self.diagrama.caixa)

    def confirmar(self) -> None:
        """Grava este diagrama como conferido e vai ao próximo por conferir."""
        if not self.aberto:
            return
        tabuleiro, tudo = self.tabuleiro(), self.check_inteiro.isChecked()
        if self.aplicar is not None and not self.aplicar(self.diagrama.caixa, tabuleiro, tudo):
            return                              # não gravou: o aviso já foi
        self.conferido.emit(self.diagrama.caixa, tabuleiro, tudo)
        self.diagramas[self.atual] = self.diagrama.conferir(tabuleiro)
        self.tabuleiros[self.atual] = self.diagramas[self.atual].edicao()
        faltam = [i for i in range(len(self.diagramas)) if not self.diagramas[i].conferido]
        if not faltam:
            self._mostrar()
            self.terminou.emit()
            return
        self._ir_para(next((i for i in faltam if i > self.atual), faltam[0]))

    # ------------------------------------------------------------------
    def validacao(self) -> Optional[lances.Validacao]:
        """A validação pelos lances da posição como está agora no editor (§10)."""
        if not self.aberto:
            return None
        linha = self.linhas[self.atual] if self.atual < len(self.linhas) else []
        tabuleiro = self.tabuleiro()
        lado = tabuleiro.lado if tabuleiro.lado_origem != "convencao" else None
        return lances.validar(tabuleiro.fen(), linha, lado=lado, roque=tabuleiro.roque)

    def pgn(self) -> str:
        """O PGN da posição do editor e dos lances validados (`lances.pgn_do_diagrama`)."""
        if not self.aberto:
            return ""
        d = self.diagrama.conferir(self.tabuleiro(), conferido=self.diagrama.conferido)
        return lances.pgn_do_diagrama(replace(d, validacao=self.validacao()))

    def _mostrar(self) -> None:
        aberto = self.aberto
        for w in (self.posicao, self.btn_conferido, self.btn_anterior, self.btn_seguinte,
                  self.check_inteiro, self.radio_brancas, self.radio_pretas,
                  self.btn_vazia, *self.botoes_paleta.values()):
            w.setEnabled(aberto)
        if not aberto:
            self.cabecalho.setText("Nenhum diagrama em conferência. Clique num diagrama da "
                                   "Imagem ou use F8.")
            self.fen.clear()
            self.avisos.clear()
            self.origem_do_lado.clear()
            self.roque_inferido.clear()
            self.btn_roque_inferido.setEnabled(False)
            self.btn_desfazer.setEnabled(False)
            self.btn_refazer.setEnabled(False)
            for check in self.checks_roque.values():
                check.setChecked(False)
                check.setEnabled(False)
            return
        d, tabuleiro = self.diagrama, self.tabuleiro()
        partes = [f"Diagrama {self.atual + 1} de {len(self.diagramas)}", tabuleiro.resumo()]
        if d.conferido:
            partes.append("conferido")
        self.cabecalho.setText("  —  ".join(partes))
        self.fen.setText(tabuleiro.fen())
        self.avisos.setText("\n".join(self.avisos_do_diagrama()))

        self.grupo_lado.setExclusive(False)
        self.radio_brancas.setChecked(tabuleiro.lado_origem != "convencao" and tabuleiro.lado == "w")
        self.radio_pretas.setChecked(tabuleiro.lado_origem != "convencao" and tabuleiro.lado == "b")
        self.grupo_lado.setExclusive(True)
        if tabuleiro.lado_origem == "convencao":
            vez = (self.validacao().vez if self.validacao() is not None else "")
            dica = (f" O texto começa com {'as pretas' if vez == 'b' else 'as brancas'}."
                    if vez else "")
            self.origem_do_lado.setText("A página não diz. Escolha: até lá o FEN sai com "
                                        f"'w' marcado como assumido.{dica}")
            estilo.papel(self.origem_do_lado, "erro")
        elif tabuleiro.lado_origem == LADO_DA_LEGENDA:
            trecho = f": “{d.lado_trecho}”" if d.lado_trecho else ""
            self.origem_do_lado.setText(f"Da legenda da página{trecho}. Confira.")
            estilo.papel(self.origem_do_lado, "aviso")
        else:
            self.origem_do_lado.setText("Informado por você.")
            estilo.papel(self.origem_do_lado, "")

        possiveis = tabuleiro.roques_possiveis()
        for letra, check in self.checks_roque.items():
            check.setChecked(letra in tabuleiro.roque)
            check.setEnabled(letra in possiveis)
        inferido = lances.roque_inferido(tabuleiro.fen())
        self.roque_inferido.setText(f"Inferido: {inferido} (rei e torre nas casas iniciais; "
                                    "não vai ao FEN sem você marcar)" if inferido
                                    else "Nenhum roque inferido.")
        self.btn_roque_inferido.setEnabled(bool(inferido) and inferido != tabuleiro.roque)
        for simbolo, botao in self.botoes_paleta.items():
            botao.setChecked(self.posicao.pincel == simbolo)
        self.btn_vazia.setChecked(self.posicao.pincel == "")
        self.btn_desfazer.setEnabled(tabuleiro.pode_desfazer)
        self.btn_refazer.setEnabled(tabuleiro.pode_refazer)
        self.posicao.update()

    def avisos_do_diagrama(self) -> List[str]:
        """O que a página deixou em aberto, o que o leitor desconfia, o que os lances do
        texto dizem e o que o FEN supõe."""
        if not self.aberto:
            return []
        d, tabuleiro = self.diagrama, self.tabuleiro()
        avisos = []
        if not d.orientacao_confirmada:
            avisos.append("Orientação não confirmada: não há coordenadas legíveis em volta do "
                          "tabuleiro, e a leitura supõe as brancas embaixo. Se o diagrama estiver "
                          "do lado das pretas, a posição sai girada 180°.")
        if d.motivo and not d.conferido:
            avisos.append(f"O leitor não confia nesta leitura: {d.motivo}. Confira casa a casa.")
        validacao = self.validacao()
        if validacao is not None and validacao.confiavel:
            avisos.append(f"Confiável pelos lances: os {validacao.total} lance(s) do texto "
                          "depois do diagrama são legais nesta posição.")
        elif validacao is not None:
            avisos.append(f"{validacao.aviso[:1].upper()}{validacao.aviso[1:]} "
                          f"({validacao.legais} de {validacao.total} lances passaram).")
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


def _chaves(diagramas) -> List[tuple]:
    """O lugar de cada diagrama: a mesma lista de caixas é a mesma página em edição."""
    return [tuple(d.caixa) for d in diagramas]
