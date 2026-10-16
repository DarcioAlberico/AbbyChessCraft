"""O painel de treino: o glifo em revisão, a linha em volta e o que fazer com ele.

É o diálogo de treino de padrões do FineReader, adaptado a livros de xadrez:

- **Enter** ensina o glifo como padrão deste livro e relê a página. As outras
  ocorrências do mesmo desenho deixam a fila sozinhas.
- **Shift+Enter** corrige só esta ocorrência, sem gravar padrão. Serve para o
  glifo borrado que não deve ensinar nada.
- **Del** tira o box da página: sujeira, pedaço de moldura, traço de diagrama.
- **Alt+↓** passa ao próximo da fila sem decidir; **Alt+↑** volta (em qualquer painel).
- **Ctrl+D** divide o box em dois glifos, no ponto clicado no recorte ampliado
  ou, sem clique, no vão da tinta. **Ctrl+J** junta com o box seguinte da
  linha e **Ctrl+Shift+J** com o anterior. **Shift+seta** move a borda direita
  ou a de baixo; **Ctrl+Shift+seta**, a esquerda ou a de cima.

No modo de marcar (Ctrl+M) o arraste na página desenha o quadro de um glifo, e
Ctrl+clique junta boxes numa seleção: Enter ensina todos com o mesmo caractere.
Esc esvazia a seleção.

A paleta (F2) insere figurinas e símbolos de avaliação, que o teclado não tem.

As teclas são as ações da janela (`app/teclado.py`, de `docs/atalhos.yaml`): o painel só
oferece os comandos (`pedir_*`). No campo do caractere, Enter, Shift+Enter, Delete e as
setas das bordas ficam com o campo (a exceção 6 de §3.4), que dispara a ação delas.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMenu,
                               QPushButton, QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from core.box_model import BoxEntry

from abbychess.app import cores, estilo, teclado
from abbychess.app.imagens import ampliado, pixmap_de_cinza

#: Figurinas e símbolos que os livros de xadrez imprimem e o teclado não tem.
PALETA = [
    "♔", "♕", "♖", "♗", "♘", "♙",
    "♚", "♛", "♜", "♝", "♞", "♟",
    "+", "#", "!", "?", "±", "∓",
    "⩲", "⩱", "=", "∞", "□", "–",
]

#: O nome de cada símbolo, na dica do botão: ⩲ e ⩱ se parecem com ± e ∓ em
#: várias fontes, e a dica tira a dúvida antes de ensinar o padrão errado.
NOMES_DOS_SIMBOLOS = {
    "♔": "rei branco", "♕": "dama branca", "♖": "torre branca", "♗": "bispo branco",
    "♘": "cavalo branco", "♙": "peão branco", "♚": "rei preto", "♛": "dama preta",
    "♜": "torre preta", "♝": "bispo preto", "♞": "cavalo preto", "♟": "peão preto",
    "+": "xeque", "#": "mate", "!": "bom lance", "?": "lance ruim",
    "±": "brancas estão melhor (U+00B1)", "∓": "negras estão melhor (U+2213)",
    "⩲": "brancas um pouco melhor (U+2A72)", "⩱": "negras um pouco melhor (U+2A71)",
    "=": "igualdade", "∞": "posição obscura", "□": "lance único", "–": "travessão",
}

FONTE_DE_SIMBOLOS = "Segoe UI Symbol"

NOMES_DAS_FONTES = {
    "manual": "confirmado por você",
    "livro": "padrão deste livro",
    "livro?": "padrão deste livro (fraco)",
    "neural": "rede global",
    "learner": "base global",
    "easyocr": "EasyOCR",
    "none": "ninguém leu",
}


def _amostra_do_traco(traco) -> QPixmap:
    """Um retângulo pequeno com o traço e o preenchimento do estado, para a legenda."""
    pixmap = QPixmap(30, 16)
    pixmap.fill(QColor(255, 255, 255))
    pintor = QPainter(pixmap)
    caneta = QPen(traco.cor)
    caneta.setWidthF(traco.largura)
    caneta.setStyle(traco.estilo)
    pintor.setPen(caneta)
    if traco.preenchimento:
        cor = QColor(traco.cor)
        cor.setAlpha(traco.preenchimento)
        pintor.setBrush(cor)
    pintor.drawRect(3, 3, 24, 10)
    pintor.end()
    return pixmap


class _CampoDoCaractere(QLineEdit):
    """O caractere do glifo. Enter, Shift+Enter, Delete e as setas das bordas disparam as
    ações ligadas em `teclas`; o resto é edição normal."""

    def __init__(self):
        super().__init__()
        self.teclas = teclado.AcoesDaTecla()

    def event(self, evento):
        # O Ctrl+Z e o Ctrl+Y são da janela (desfazer a página), não do campo: sem
        # isto o QLineEdit os toma para desfazer o que se digitou nele.
        if evento.type() == QEvent.Type.ShortcutOverride and (
                evento.matches(QKeySequence.StandardKey.Undo)
                or evento.matches(QKeySequence.StandardKey.Redo)):
            evento.ignore()
            return True
        if self.teclas.sobrepor(evento):
            return True
        return super().event(evento)

    def keyPressEvent(self, evento):
        if self.teclas.disparar(evento):
            return
        super().keyPressEvent(evento)


class _GlifoAmpliado(QLabel):
    """O recorte ampliado; o clique escolhe a coluna onde dividir o box."""

    clicado = Signal(float)

    def mousePressEvent(self, evento):
        pixmap = self.pixmap()
        if (evento.button() == Qt.MouseButton.LeftButton and pixmap is not None
                and not pixmap.isNull()):
            # O pixmap fica centrado no rótulo (AlignCenter).
            esquerda = (self.width() - pixmap.width()) / 2
            self.clicado.emit((evento.position().x() - esquerda) / max(pixmap.width(), 1))
        super().mousePressEvent(evento)


#: Altura do recorte ampliado no painel, em pixels de tela.
ALTURA_DO_GLIFO = 140


class PainelDeTreino(QWidget):
    ensinar = Signal(str)
    so_corrigir = Signal(str)
    descartar = Signal()
    pular = Signal()
    anterior = Signal()
    #: A coluna da página onde cortar, ou `None` para o corte no vão da tinta.
    dividir = Signal(object)
    #: +1 junta com o box seguinte da linha, -1 com o anterior.
    juntar = Signal(int)
    #: Quanto mover cada borda: esquerda, cima, direita, baixo.
    ajustar = Signal(int, int, int, int)
    #: A coluna do corte escolhida no recorte, para o visor marcá-la.
    corte_mudou = Signal(object)
    #: Esc: esvaziar a seleção do modo de treino.
    limpar_selecao = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ativo = False
        self._pagina: Optional[np.ndarray] = None
        self._box: Optional[BoxEntry] = None
        self.corte: Optional[int] = None

        self.glifo = _GlifoAmpliado()
        self.glifo.setToolTip("Clique onde dividir o box e aperte Ctrl+D.")
        self.glifo.clicado.connect(self._clicar_no_glifo)
        self.glifo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.glifo.setMinimumHeight(150)
        self.glifo.setStyleSheet("background: white; border: 1px solid #999;")

        self.contexto = QLabel()
        self.contexto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.contexto.setMinimumHeight(70)
        self.contexto.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.contexto.setStyleSheet("background: white; border: 1px solid #999;")

        self.leitura = QLabel("Abra um projeto e reconheça uma página.")
        self.leitura.setWordWrap(True)

        self.campo = _CampoDoCaractere()
        fonte = QFont(FONTE_DE_SIMBOLOS, 22)
        self.campo.setFont(fonte)
        self.campo.setPlaceholderText("caractere")
        self.campo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        botao_ensinar = QPushButton("Ensinar (Enter)")
        botao_ensinar.setToolTip("Ensina o glifo como padrão deste livro e relê a página")
        botao_ensinar.setDefault(True)
        botao_ensinar.clicked.connect(self.pedir_ensinar)
        botao_corrigir = QPushButton("Só esta (Shift+Enter)")
        botao_corrigir.setToolTip("Corrige só esta ocorrência, sem gravar padrão")
        botao_corrigir.clicked.connect(self.pedir_so_corrigir)
        botao_descartar = QPushButton("Não é caractere (Del)")
        botao_descartar.clicked.connect(self.pedir_descartar)
        botao_anterior = QPushButton("◀ Anterior")
        botao_anterior.setToolTip("O anterior da fila (Alt+↑)")
        botao_anterior.clicked.connect(self.anterior.emit)
        botao_pular = QPushButton("Pular ▶")
        botao_pular.setToolTip("O próximo da fila, sem decidir (Alt+↓)")
        botao_pular.clicked.connect(self.pular.emit)
        botao_dividir = QPushButton("Dividir")
        botao_dividir.setToolTip("Divide o box em dois glifos, na linha vermelha do recorte "
                                 "ou, sem ela, no vão da tinta (Ctrl+D).")
        botao_dividir.clicked.connect(self.pedir_dividir)
        botao_juntar_antes = QPushButton("◀ Juntar")
        botao_juntar_antes.setToolTip("Junta com o box anterior da linha (Ctrl+Shift+J).")
        botao_juntar_antes.clicked.connect(lambda: self.pedir_juntar(-1))
        botao_juntar_depois = QPushButton("Juntar ▶")
        botao_juntar_depois.setToolTip("Junta com o box seguinte da linha (Ctrl+J).")
        botao_juntar_depois.clicked.connect(lambda: self.pedir_juntar(+1))
        self._botoes = [botao_ensinar, botao_corrigir, botao_descartar, botao_anterior, botao_pular,
                        botao_dividir, botao_juntar_antes, botao_juntar_depois]

        editar = QHBoxLayout()
        editar.addWidget(botao_juntar_antes)
        editar.addWidget(botao_dividir)
        editar.addWidget(botao_juntar_depois)
        dica_das_bordas = QLabel("Bordas: Shift+seta move a direita ou a de baixo; "
                                 "Ctrl+Shift+seta, a esquerda ou a de cima.")
        dica_das_bordas.setWordWrap(True)
        dica_das_bordas.setStyleSheet("color: #555;")

        navegar = QHBoxLayout()
        navegar.addWidget(botao_anterior)
        navegar.addWidget(botao_pular)

        paleta = QGroupBox("Símbolos  (F2)")
        grade = QGridLayout(paleta)
        grade.setSpacing(2)
        for i, simbolo in enumerate(PALETA):
            botao = QToolButton()
            botao.setText(simbolo)
            botao.setToolTip(f"{simbolo}  {NOMES_DOS_SIMBOLOS.get(simbolo, '')}")
            botao.setFont(QFont(FONTE_DE_SIMBOLOS, 14))
            botao.setFixedSize(34, 34)
            botao.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            botao.clicked.connect(lambda _=False, s=simbolo: self._inserir(s))
            grade.addWidget(botao, i // 6, i % 6)
            self._botoes.append(botao)

        self.selecao = QLabel("")
        self.selecao.setWordWrap(True)
        self.fila = QLabel("")
        self.padroes = QLabel("")

        legenda = QGroupBox("Os boxes na página")
        caixa_legenda = QVBoxLayout(legenda)
        amostras = [(estilo.traco(estado, origem), texto)
                    for estado, origem, texto in estilo.LEGENDA]
        amostras += [(estilo.Traco(cores.DIAGRAMA, 2.5, Qt.PenStyle.DashLine),
                      "Diagrama (fora do texto)"),
                     (estilo.Traco(cores.MARCADO, 2.5, Qt.PenStyle.SolidLine),
                      "Na seleção (Ctrl+clique)")]
        for traco, texto in amostras:
            linha = QHBoxLayout()
            amostra = QLabel()
            amostra.setPixmap(_amostra_do_traco(traco))
            linha.addWidget(amostra)
            linha.addWidget(QLabel(texto), 1)
            caixa_legenda.addLayout(linha)

        caixa = QVBoxLayout(self)
        caixa.setContentsMargins(4, 4, 4, 4)    # cabe no Inspetor de 296 px (§3.1)
        caixa.addWidget(QLabel("<b>Glifo</b>"))
        caixa.addWidget(self.glifo)
        caixa.addWidget(QLabel("<b>Na linha</b>"))
        caixa.addWidget(self.contexto)
        caixa.addWidget(self.leitura)
        caixa.addWidget(self.selecao)
        caixa.addWidget(self.campo)
        caixa.addWidget(botao_ensinar)
        caixa.addWidget(botao_corrigir)
        caixa.addWidget(botao_descartar)
        caixa.addLayout(navegar)
        caixa.addLayout(editar)
        caixa.addWidget(dica_das_bordas)
        caixa.addWidget(paleta)
        caixa.addWidget(self.fila)
        caixa.addWidget(self.padroes)
        caixa.addWidget(legenda)
        caixa.addStretch(1)

        self.habilitar(False)

    # ------------------------------------------------------------------
    def mostrar(self, pagina: np.ndarray, box: BoxEntry, posicao: str) -> None:
        """Mostra o box em revisão e põe a leitura atual no campo, selecionada."""
        self._pagina, self._box = pagina, box
        self._definir_corte(None)
        self.contexto.setPixmap(self._contexto(pagina, box))
        fonte = NOMES_DAS_FONTES.get(box.source, box.source or "sem leitura")
        lido = box.char if box.char else "—"
        self.leitura.setText(f"{posicao}<br>Leitura: <b style='font-size:16pt'>{lido}</b> "
                             f"&nbsp;({fonte}, confiança {box.confidence:.2f})")
        self.campo.setText(box.char)
        self.campo.selectAll()
        self.habilitar(True)                    # antes do foco: num campo desligado o Qt o
        self.campo.setFocus()                   # ignora, e a próxima tecla iria para outro lugar

    def limpar(self, mensagem: str) -> None:
        self._pagina, self._box = None, None
        self._definir_corte(None)
        self.glifo.clear()
        self.contexto.clear()
        self.campo.clear()
        self.leitura.setText(mensagem)
        self.habilitar(False)

    def habilitar(self, sim: bool) -> None:
        self._ativo = sim
        self.campo.setEnabled(sim)
        for botao in self._botoes:
            botao.setEnabled(sim)

    def mostrar_selecao(self, quantos: int) -> None:
        """Quantos boxes a seleção tem; com mais de um, Enter ensina todos."""
        self.selecao.setText(
            f"<b style='color:{cores.MARCADO.name()}'>Seleção: {quantos} glifos.</b> Enter "
            "ensina todos com o mesmo caractere; Esc esvazia." if quantos > 1 else "")

    def mostrar_contagens(self, pendentes: int, total: int, padroes: int, caracteres: int) -> None:
        self.fila.setText(f"<b>A revisar nesta página:</b> {pendentes} de {total} boxes")
        self.padroes.setText(f"<b>Padrões deste livro:</b> {padroes} amostras em "
                             f"{caracteres} caracteres")

    # ------------------------------------------------------------------
    def _contexto(self, pagina: np.ndarray, box: BoxEntry):
        """A faixa da linha em volta do box, com ele marcado."""
        altura = max(box.y2 - box.y1, 1)
        y1 = max(0, box.y1 - altura)
        y2 = min(pagina.shape[0], box.y2 + altura)
        x1 = max(0, box.x1 - 18 * altura)
        x2 = min(pagina.shape[1], box.x2 + 18 * altura)
        pixmap = pixmap_de_cinza(pagina[y1:y2, x1:x2]).copy()
        pintor = QPainter(pixmap)
        caneta = QPen(cores.SELECIONADO)
        caneta.setWidth(2)
        pintor.setPen(caneta)
        pintor.drawRect(box.x1 - x1 - 2, box.y1 - y1 - 2, box.x2 - box.x1 + 3, box.y2 - box.y1 + 3)
        pintor.end()
        largura = max(self.contexto.width() - 8, 200)
        return pixmap.scaled(largura, 90, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)

    def _desenhar_glifo(self) -> None:
        box = self._box
        recorte = self._pagina[box.y1:box.y2, box.x1:box.x2]
        pixmap = ampliado(pixmap_de_cinza(recorte), ALTURA_DO_GLIFO)
        if self.corte is not None and not pixmap.isNull():
            pixmap = pixmap.copy()
            coluna = (self.corte - box.x1) * pixmap.width() / max(box.x2 - box.x1, 1)
            pintor = QPainter(pixmap)
            caneta = QPen(cores.SELECIONADO)
            caneta.setWidth(2)
            pintor.setPen(caneta)
            pintor.drawLine(round(coluna), 0, round(coluna), pixmap.height())
            pintor.end()
        self.glifo.setPixmap(pixmap)

    def _definir_corte(self, coluna: Optional[int]) -> None:
        """Marca a coluna da página onde dividir; `None` volta ao corte pela tinta."""
        box = self._box
        if box is None or coluna is None or not box.x1 < coluna < box.x2:
            coluna = None
        self.corte = coluna
        if box is not None:
            self._desenhar_glifo()
        self.corte_mudou.emit(coluna)

    def _clicar_no_glifo(self, fracao: float) -> None:
        if self._ativo and self._box is not None:
            box = self._box
            self._definir_corte(box.x1 + round(fracao * (box.x2 - box.x1)))
            self.campo.setFocus()

    # ------------------------------------------------------------------
    # Os comandos que as ações da janela (e os botões) pedem; valem com um glifo mostrado.
    # ------------------------------------------------------------------
    def pedir_dividir(self) -> None:
        if self._ativo:
            self.dividir.emit(self.corte)

    def pedir_juntar(self, passo: int) -> None:
        if self._ativo:
            self.juntar.emit(passo)

    def pedir_ajustar(self, esquerda: int, cima: int, direita: int, baixo: int) -> None:
        if self._ativo:
            self.ajustar.emit(esquerda, cima, direita, baixo)

    def pedir_ensinar(self) -> None:
        if self._ativo and (texto := self._texto()):
            self.ensinar.emit(texto)

    def pedir_so_corrigir(self) -> None:
        if self._ativo and (texto := self._texto()):
            self.so_corrigir.emit(texto)

    def pedir_descartar(self) -> None:
        if self._ativo:
            self.descartar.emit()

    def abrir_paleta(self) -> None:
        """F2: a paleta como menu, no campo; o símbolo escolhido entra no cursor."""
        if not self._ativo:
            return
        menu = QMenu(self)
        menu.setFont(QFont(FONTE_DE_SIMBOLOS, 12))
        for simbolo in PALETA:
            menu.addAction(f"{simbolo}   {NOMES_DOS_SIMBOLOS.get(simbolo, '')}",
                           lambda s=simbolo: self._inserir(s))
        self.menu_da_paleta = menu              # os testes escolhem sem abrir
        menu.popup(self.campo.mapToGlobal(self.campo.rect().bottomLeft()))

    def _inserir(self, simbolo: str) -> None:
        self.campo.insert(simbolo)
        self.campo.setFocus()

    def _texto(self) -> Optional[str]:
        texto = self.campo.text()
        return texto if texto.strip() else None
