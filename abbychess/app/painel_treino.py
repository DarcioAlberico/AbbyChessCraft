"""O painel de treino: o glifo em revisão, a linha em volta e o que fazer com ele.

É o diálogo de treino de padrões do FineReader, adaptado a livros de xadrez:

- **Enter** ensina o glifo como padrão deste livro e relê a página. As outras
  ocorrências do mesmo desenho deixam a fila sozinhas.
- **Shift+Enter** corrige só esta ocorrência, sem gravar padrão. Serve para o
  glifo borrado que não deve ensinar nada.
- **Del** tira o box da página: sujeira, pedaço de moldura, traço de diagrama.
- **Tab** pula para o próximo da fila sem decidir.
- **Ctrl+D** divide o box em dois glifos, no ponto clicado no recorte ampliado
  ou, sem clique, no vão da tinta. **Ctrl+J** junta com o box seguinte da
  linha e **Ctrl+Shift+J** com o anterior. **Alt+seta** move a borda direita
  ou a de baixo; **Alt+Shift+seta**, a esquerda ou a de cima.

No modo de treino (Ctrl+T) o arraste na página desenha o quadro de um glifo, e
Ctrl+clique junta boxes numa seleção: Enter ensina todos com o mesmo caractere.
Esc esvazia a seleção.

A paleta insere figurinas e símbolos de avaliação, que o teclado não tem.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QFont, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from core.box_model import BoxEntry

from abbychess.app import cores
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


class _CampoDoCaractere(QLineEdit):
    """Enter ensina, Shift+Enter só corrige; o resto é edição normal."""

    ensinar = Signal()
    so_corrigir = Signal()

    def event(self, evento):
        # O Ctrl+Z e o Ctrl+Y são da janela (desfazer a página), não do campo: sem
        # isto o QLineEdit os toma para desfazer o que se digitou nele.
        if evento.type() == QEvent.Type.ShortcutOverride and (
                evento.matches(QKeySequence.StandardKey.Undo)
                or evento.matches(QKeySequence.StandardKey.Redo)):
            evento.ignore()
            return True
        return super().event(evento)

    def keyPressEvent(self, evento):
        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if evento.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.so_corrigir.emit()
            else:
                self.ensinar.emit()
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
        self.campo.ensinar.connect(self._ensinar)
        self.campo.so_corrigir.connect(self._so_corrigir)

        botao_ensinar = QPushButton("Ensinar padrão  (Enter)")
        botao_ensinar.setDefault(True)
        botao_ensinar.clicked.connect(self._ensinar)
        botao_corrigir = QPushButton("Só esta ocorrência  (Shift+Enter)")
        botao_corrigir.clicked.connect(self._so_corrigir)
        botao_descartar = QPushButton("Não é caractere  (Del)")
        botao_descartar.clicked.connect(self._descartar)
        botao_anterior = QPushButton("◀ Anterior")
        botao_anterior.clicked.connect(self.anterior.emit)
        botao_pular = QPushButton("Pular ▶  (Tab)")
        botao_pular.clicked.connect(self.pular.emit)
        botao_dividir = QPushButton("Dividir  (Ctrl+D)")
        botao_dividir.setToolTip("Divide o box em dois glifos, na linha vermelha do recorte "
                                 "ou, sem ela, no vão da tinta.")
        botao_dividir.clicked.connect(self._dividir)
        botao_juntar_antes = QPushButton("◀ Juntar")
        botao_juntar_antes.setToolTip("Junta com o box anterior da linha (Ctrl+Shift+J).")
        botao_juntar_antes.clicked.connect(lambda: self._juntar(-1))
        botao_juntar_depois = QPushButton("Juntar ▶")
        botao_juntar_depois.setToolTip("Junta com o box seguinte da linha (Ctrl+J).")
        botao_juntar_depois.clicked.connect(lambda: self._juntar(+1))
        self._botoes = [botao_ensinar, botao_corrigir, botao_descartar, botao_anterior, botao_pular,
                        botao_dividir, botao_juntar_antes, botao_juntar_depois]

        editar = QHBoxLayout()
        editar.addWidget(botao_juntar_antes)
        editar.addWidget(botao_dividir)
        editar.addWidget(botao_juntar_depois)
        dica_das_bordas = QLabel("Bordas: Alt+seta move a direita ou a de baixo; "
                                 "Alt+Shift+seta, a esquerda ou a de cima.")
        dica_das_bordas.setWordWrap(True)
        dica_das_bordas.setStyleSheet("color: #555;")

        navegar = QHBoxLayout()
        navegar.addWidget(botao_anterior)
        navegar.addWidget(botao_pular)

        paleta = QGroupBox("Símbolos")
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

        legenda = QGroupBox("Cores dos boxes")
        caixa_legenda = QVBoxLayout(legenda)
        for cor, texto in cores.LEGENDA:
            linha = QLabel(f'<span style="color:{cor.name()}">■</span> {texto}')
            caixa_legenda.addWidget(linha)

        caixa = QVBoxLayout(self)
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

        for tecla, acao in ((QKeySequence.StandardKey.Delete, self._descartar),
                            (QKeySequence("Tab"), self.pular.emit),
                            (QKeySequence("Shift+Tab"), self.anterior.emit),
                            (QKeySequence("Ctrl+D"), self._dividir),
                            (QKeySequence("Esc"), self.limpar_selecao.emit),
                            (QKeySequence("Ctrl+J"), lambda: self._juntar(+1)),
                            (QKeySequence("Ctrl+Shift+J"), lambda: self._juntar(-1)),
                            *self._atalhos_das_bordas()):
            atalho = QShortcut(tecla, self)
            atalho.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            atalho.activated.connect(acao)

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

    def _atalhos_das_bordas(self):
        """Alt+seta move a borda direita ou a de baixo; com Shift, a oposta."""
        for tecla, (dx, dy) in (("Left", (-1, 0)), ("Right", (1, 0)),
                                ("Up", (0, -1)), ("Down", (0, 1))):
            yield (QKeySequence(f"Alt+{tecla}"),
                   lambda dx=dx, dy=dy: self._ajustar(0, 0, dx, dy))
            yield (QKeySequence(f"Alt+Shift+{tecla}"),
                   lambda dx=dx, dy=dy: self._ajustar(dx, dy, 0, 0))

    def _dividir(self) -> None:
        if self._ativo:
            self.dividir.emit(self.corte)

    def _juntar(self, passo: int) -> None:
        if self._ativo:
            self.juntar.emit(passo)

    def _ajustar(self, esquerda: int, cima: int, direita: int, baixo: int) -> None:
        if self._ativo:
            self.ajustar.emit(esquerda, cima, direita, baixo)

    def _inserir(self, simbolo: str) -> None:
        self.campo.insert(simbolo)
        self.campo.setFocus()

    def _texto(self) -> Optional[str]:
        texto = self.campo.text()
        return texto if texto.strip() else None

    def _ensinar(self) -> None:
        if self._ativo and (texto := self._texto()):
            self.ensinar.emit(texto)

    def _so_corrigir(self) -> None:
        if self._ativo and (texto := self._texto()):
            self.so_corrigir.emit(texto)

    def _descartar(self) -> None:
        if self._ativo:
            self.descartar.emit()
