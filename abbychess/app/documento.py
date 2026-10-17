"""O Documento (SPEC §6.1, §6.2): a página reconhecida, montada num `QTextDocument`.

- **De onde vem**: do documento derivado (`abbychess.texto.montar`, com os glifos que
  ninguém leu como □), no modo `impresso` (♘ como impresso). Cada linha impressa é um
  parágrafo: refluir as linhas em parágrafos pede os parágrafos do layout (passo F); sem
  eles, o título e o corpo da mesma área se juntariam. Os títulos em título; cabeçalho,
  rodapé e número de página em cinza pequeno (Ctrl+Shift+H os oculta); as notas em corpo
  menor.
- **O mapa posição → gid** fica no `QTextBlockUserData` de cada parágrafo (uma lista com o
  gid de cada caractere, -1 nos espaços), não num `QTextCharFormat` por glifo: a coleção de
  formatos do documento não libera e vazaria a cada montagem (§6.2).
- **Os diagramas** entram inline e atômicos: o desenho da posição lida (ou o recorte da
  página, se não lida), a linha dele em monoespaçado, o estado e "Copiar FEN".
- **O realce** (liga e desliga): baixa confiança com fundo laranja-claro, fora do léxico com
  ondulado, glifo virtual com pontilhado, aguardando leitura em cinza; manual e revisado sem
  realce.
- **Somente leitura** até o passo D1, que traz a edição.

Montar de novo (uma edição, a propagação) não perde o lugar: o cursor volta ao mesmo gid e a
rolagem fica onde estava (CA-6.5).
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Set

import numpy as np
from PySide6.QtCore import QRectF, Qt, QUrl, Signal
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QGuiApplication, QImage, QPainter, QPen,
                           QTextBlockFormat, QTextBlockUserData, QTextCharFormat, QTextCursor,
                           QTextDocument, QTextImageFormat)
from PySide6.QtWidgets import QTextEdit

from core.lado_a_jogar import NAO_REVISADO

from abbychess import grade as gd
from abbychess import texto as tx
from abbychess.app import estilo
from abbychess.app.imagens import pixmap_de_cinza

FONTE = "Segoe UI Symbol"
MONO = "Consolas"
CORPO_PADRAO = 11
CORPO_MINIMO, CORPO_MAXIMO = 7, 28
#: As funções em cinza pequeno, que Ctrl+Shift+H oculta.
MARGENS = {"cabecalho", "rodape", "numero_de_pagina"}
FUNDO_DE_BAIXA_CONFIANCA = QColor(255, 226, 184)
FUNDO_DO_ATUAL = QColor(190, 220, 255)
#: A figurina de cada peça no desenho do diagrama.
FIGURINAS = {"K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
             "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟"}
LADO_DA_CASA = 22


class _MapaDoBloco(QTextBlockUserData):
    """O gid de cada caractere do parágrafo (-1 onde não há glifo) e, se o parágrafo é um
    diagrama, o id dele."""

    def __init__(self, gids: List[int], diagrama_id: Optional[str] = None):
        super().__init__()
        self.gids = gids
        self.diagrama_id = diagrama_id


def imagem_do_diagrama(diagrama, matriz: Optional[np.ndarray]) -> QImage:
    """A posição lida desenhada (casas e figurinas); sem leitura, o recorte da página."""
    if not diagrama.lido:
        if matriz is None:
            imagem = QImage(8 * LADO_DA_CASA, 8 * LADO_DA_CASA, QImage.Format.Format_RGB32)
            imagem.fill(QColor(240, 240, 240))
            return imagem
        x1, y1, x2, y2 = (int(v) for v in diagrama.caixa)
        recorte = pixmap_de_cinza(matriz[max(0, y1):y2, max(0, x1):x2]).toImage()
        return recorte.scaledToHeight(8 * LADO_DA_CASA, Qt.TransformationMode.SmoothTransformation)
    lado = LADO_DA_CASA
    imagem = QImage(8 * lado + 2, 8 * lado + 2, QImage.Format.Format_RGB32)
    imagem.fill(QColor(255, 255, 255))
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.setFont(QFont(FONTE, int(lado * 0.62)))
    for n, casa in enumerate(diagrama.casas[:64]):
        linha, coluna = divmod(n, 8)
        retangulo = QRectF(1 + coluna * lado, 1 + linha * lado, lado, lado)
        if (linha + coluna) % 2:
            pintor.fillRect(retangulo, QColor(181, 196, 166))
        if casa.simbolo:
            pintor.setPen(QColor(0, 0, 0))
            pintor.drawText(retangulo, Qt.AlignmentFlag.AlignCenter, FIGURINAS.get(casa.simbolo, "?"))
    pintor.setPen(QPen(QColor(90, 90, 90)))
    pintor.drawRect(QRectF(0.5, 0.5, 8 * lado + 1, 8 * lado + 1))
    pintor.end()
    return imagem


def estado_do_diagrama(diagrama) -> str:
    if diagrama.conferido:
        return "conferido"
    if diagrama.lido:
        return "lido, não conferido"
    return "não lido"


class VistaDoDocumento(QTextEdit):
    #: O clique num glifo: o gid dele e os gids da palavra.
    glifo_clicado = Signal(int, list)
    #: O cursor andou (teclado ou clique) para a palavra destes gids.
    cursor_na_palavra = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)                  # a edição é do passo D1
        self.setUndoRedoEnabled(False)
        self.setTabChangesFocus(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse
                                     | Qt.TextInteractionFlag.TextSelectableByKeyboard
                                     | Qt.TextInteractionFlag.LinksAccessibleByMouse
                                     | Qt.TextInteractionFlag.LinksAccessibleByKeyboard)
        self.setAccessibleName("Documento: o texto reconhecido da página")
        self.realce = True
        self.mostrar_margens = True
        self.corpo = CORPO_PADRAO
        self._diagramas: Dict[str, object] = {}
        self._linha_do_gid: Dict[int, List[int]] = {}
        self._palavra_do_gid: Dict[int, List[int]] = {}
        self._movendo = False                   # o cursor posto pelo programa não avisa
        self._clicando = False                  # o cursor do press: o release avisa
        self._entrada = None                     # o que a última montagem recebeu
        self._formatos: Dict[tuple, QTextCharFormat] = {}   # os do realce, por montagem
        self._gid_atual: Optional[int] = None
        self.corpo_padrao = CORPO_PADRAO
        self.cursorPositionChanged.connect(self._cursor_mudou)

    # ------------------------------------------------------------------
    # Montar
    # ------------------------------------------------------------------
    def montar(self, documento: Optional[tx.Documento], diagramas: Sequence = (),
               estados: Optional[Dict[int, str]] = None, desconhecidos: Iterable[int] = (),
               virtuais: Iterable[int] = (), matriz: Optional[np.ndarray] = None,
               margens: Iterable[int] = ()) -> None:
        """O documento da página; sem documento (a página não reconhecida), o aviso.
        `margens`: os glifos do cabeçalho e do rodapé corridos, em cinza pequeno (a linha
        toda de margem; Ctrl+Shift+H a oculta), até as áreas terem função (passo F)."""
        self._entrada = (documento, list(diagramas), dict(estados or {}), set(desconhecidos),
                         set(virtuais), matriz, set(margens))
        lugar = self._lugar()
        rolagem = self.verticalScrollBar().value()
        novo = QTextDocument(self)
        novo.setDefaultFont(QFont(FONTE, self.corpo))
        self._linha_do_gid, self._palavra_do_gid, self._diagramas = {}, {}, {}
        self._formatos = {}
        if documento is not None:
            self._preencher(novo, *self._entrada)
        else:
            aviso = QTextCharFormat()
            aviso.setForeground(estilo.CINZA)
            QTextCursor(novo).insertText("Página não reconhecida: F5 reconhece.", aviso)
        antigo = self.document()
        # O documento padrão do QTextEdit é do controle de texto, que o apaga no setDocument; o
        # nosso anterior (filho da vista) sai aqui, ou cada montagem o deixaria vivo.
        apagar = antigo is not novo and antigo.parent() is self
        self._movendo = True
        try:
            self.setDocument(novo)
            self._voltar_ao_lugar(lugar)
            self.verticalScrollBar().setValue(rolagem)
            self.marcar_atual(self._gid_atual)
        finally:
            self._movendo = False
        if apagar:
            antigo.deleteLater()                # com as imagens dos diagramas e os formatos

    def _lugar(self):
        """O cursor e a âncora da seleção, como (gid, deslocamento no glifo) cada."""
        cursor = self.textCursor()
        return (self._gid_e_deslocamento(cursor.anchor()),
                self._gid_e_deslocamento(cursor.position()))

    def _gid_e_deslocamento(self, posicao: int):
        if self.document().isEmpty():
            return None
        bloco = self.document().findBlock(posicao)
        mapa = bloco.userData() if bloco.isValid() else None
        if not isinstance(mapa, _MapaDoBloco):
            return None
        i = posicao - bloco.position()
        if 0 <= i < len(mapa.gids) and mapa.gids[i] >= 0:
            gid = mapa.gids[i]
            return gid, i - mapa.gids.index(gid)
        if 0 < i <= len(mapa.gids) and mapa.gids[i - 1] >= 0:   # o fim de um glifo
            gid = mapa.gids[i - 1]
            return gid, i - mapa.gids.index(gid)
        return None

    def _voltar_ao_lugar(self, lugar) -> None:
        ancora, posicao = lugar
        destino = self._posicao_de(posicao)
        if destino is None:
            return
        cursor = self.textCursor()
        inicio = self._posicao_de(ancora)
        if inicio is not None and inicio != destino:
            cursor.setPosition(inicio)
            cursor.setPosition(destino, QTextCursor.MoveMode.KeepAnchor)
        else:
            cursor.setPosition(destino)
        self.setTextCursor(cursor)

    def _posicao_de(self, gid_e_deslocamento) -> Optional[int]:
        if gid_e_deslocamento is None:
            return None
        gid, deslocamento = gid_e_deslocamento
        inicio = self.posicao_do_gid(gid)
        return None if inicio is None else inicio + deslocamento

    def remontar(self) -> None:
        """A mesma página, com o realce, as margens ou o corpo de agora."""
        if self._entrada is not None:
            self.montar(*self._entrada)

    def _preencher(self, doc, documento, diagramas, estados, desconhecidos, virtuais, matriz,
                   margens=frozenset()):
        normal = tx._normalizador(tx.IMPRESSO)
        self._diagramas = {d.id: d for d in diagramas}
        numero = {d.id: k for k, d in enumerate(sorted(diagramas, key=lambda d: (d.caixa[1], d.caixa[0])),
                                                start=1)}
        cursor = QTextCursor(doc)
        primeiro = True
        for bloco in documento.blocos:
            if bloco.funcao in MARGENS and not self.mostrar_margens:
                continue
            if not primeiro:
                cursor.insertBlock()
            primeiro = False
            cursor.setBlockFormat(self._formato_do_bloco(bloco.funcao))
            if bloco.diagrama_id is not None:
                self._por_diagrama(doc, cursor, self._diagramas.get(bloco.diagrama_id),
                                   numero.get(bloco.diagrama_id, 0), matriz)
                continue
            base = self._formato_do_caractere(bloco.funcao)
            de_margem = self._formato_do_caractere("cabecalho")
            escritas = 0
            for linha in bloco.linhas:
                gids = [g for p in linha.palavras for g in p.gids]
                margem = bool(gids) and all(g in margens for g in gids)
                if margem and not self.mostrar_margens:
                    for g in gids:                  # a Linha ainda acha a linha dela
                        self._linha_do_gid[g] = gids
                    continue
                if escritas:
                    cursor.insertBlock(self._formato_do_bloco(bloco.funcao, continua=True))
                escritas += 1
                self._linha(cursor, linha, documento, de_margem if margem else base, normal,
                            estados, desconhecidos, virtuais)

    def _linha(self, cursor, linha, documento, base, normal, estados, desconhecidos,
               virtuais) -> None:
        """Uma linha impressa num parágrafo, com o mapa dos gids dele. O texto entra em
        corridas do mesmo formato (uma inserção por corrida, não por glifo)."""
        gids: List[int] = []
        corrida: List[str] = []
        formato_da_corrida = None

        def escrever():
            if corrida:
                cursor.insertText("".join(corrida), formato_da_corrida)
                corrida.clear()

        gids_da_linha = [g for p in linha.palavras for g in p.gids]
        for n_palavra, palavra in enumerate(linha.palavras):
            if n_palavra:
                if formato_da_corrida is not base:
                    escrever()
                    formato_da_corrida = base
                corrida.append(" ")
                gids.append(-1)
            for g in palavra.gids:
                self._linha_do_gid[g] = gids_da_linha
                self._palavra_do_gid[g] = list(palavra.gids)
                char = documento.chars.get(g, "")
                letras = tx.NAO_LIDO if char == tx.NAO_LIDO else (normal(char) or tx.NAO_LIDO)
                formato = self._formato_do_glifo(base, estados.get(g), g in desconhecidos,
                                                 g in virtuais)
                if formato is not formato_da_corrida:
                    escrever()
                    formato_da_corrida = formato
                corrida.append(letras)
                gids.extend([g] * len(letras))
        escrever()
        cursor.block().setUserData(_MapaDoBloco(gids))

    def _por_diagrama(self, doc, cursor, diagrama, numero: int, matriz) -> None:
        if diagrama is None:
            cursor.block().setUserData(_MapaDoBloco([]))
            return
        nome = f"diagrama:{diagrama.id}"
        doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl(nome),
                        imagem_do_diagrama(diagrama, matriz))
        formato = QTextImageFormat()
        formato.setName(nome)
        cursor.insertImage(formato)
        mono = QTextCharFormat()
        mono.setFont(QFont(MONO, max(CORPO_MINIMO, self.corpo - 2)))
        # No Documento, só o estado de §6.1, embaixo: o "não revisado" é da exportação.
        linha = diagrama.linha_de_texto(numero).replace(f"; {NAO_REVISADO}", "")
        cursor.insertText(" " + linha, mono)
        estado = QTextCharFormat()
        estado.setForeground(estilo.CINZA)
        cursor.insertText(f" {estado_do_diagrama(diagrama)}", estado)
        if diagrama.lido:
            ligacao = QTextCharFormat()
            ligacao.setAnchor(True)
            ligacao.setAnchorHref(f"copiar-fen:{diagrama.id}")
            ligacao.setForeground(estilo.AZUL)
            ligacao.setFontUnderline(True)
            cursor.insertText(" · ", estado)
            cursor.insertText("Copiar FEN", ligacao)
        texto = cursor.block().text()
        cursor.block().setUserData(_MapaDoBloco([-1] * len(texto), diagrama.id))

    def _formato_do_bloco(self, funcao: str, continua: bool = False) -> QTextBlockFormat:
        """O parágrafo de uma linha: o espaço maior fica entre os blocos (`continua`: a linha
        seguinte do mesmo bloco, junto da anterior)."""
        formato = QTextBlockFormat()
        if not continua:
            formato.setTopMargin(self.corpo * (0.9 if funcao == "titulo" else 0.5))
        return formato

    def _formato_do_caractere(self, funcao: str) -> QTextCharFormat:
        formato = QTextCharFormat()
        if funcao == "titulo":
            formato.setFontWeight(QFont.Weight.Bold)
            formato.setFontPointSize(self.corpo * 1.3)
        elif funcao in MARGENS:
            formato.setForeground(estilo.CINZA)
            formato.setFontPointSize(max(CORPO_MINIMO, self.corpo * 0.8))
        elif funcao == "nota":
            formato.setFontPointSize(max(CORPO_MINIMO, self.corpo * 0.85))
        return formato

    def _formato_do_glifo(self, base: QTextCharFormat, estado: Optional[str], desconhecido: bool,
                          virtual: bool) -> QTextCharFormat:
        """O formato do glifo pelo realce; o `base` (o mesmo objeto) quando não há realce, para
        as corridas de texto seguido ficarem numa inserção só."""
        if not self.realce or not (desconhecido or virtual
                                   or estado in (gd.PENDENTE, gd.SEM_LEITURA, gd.AGUARDANDO)):
            return base
        chave = (id(base), estado, desconhecido, virtual)   # o base é o do bloco, vivo até o fim
        if chave in self._formatos:
            return self._formatos[chave]
        formato = QTextCharFormat(base)
        if estado in (gd.PENDENTE, gd.SEM_LEITURA):
            formato.setBackground(FUNDO_DE_BAIXA_CONFIANCA)
        elif estado == gd.AGUARDANDO:
            formato.setForeground(estilo.CINZA)
        if desconhecido:
            formato.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
            formato.setUnderlineColor(estilo.VERMELHAO)
        elif virtual:
            formato.setUnderlineStyle(QTextCharFormat.UnderlineStyle.DotLine)
            formato.setUnderlineColor(estilo.AZUL)
        self._formatos[chave] = formato
        return formato

    # ------------------------------------------------------------------
    # O mapa
    # ------------------------------------------------------------------
    def gid_na_posicao(self, posicao: int) -> Optional[int]:
        bloco = self.document().findBlock(posicao)
        mapa = bloco.userData() if bloco.isValid() else None
        if not isinstance(mapa, _MapaDoBloco):
            return None
        i = posicao - bloco.position()
        for k in (i, i - 1):                    # o cursor fica entre dois caracteres
            if 0 <= k < len(mapa.gids) and mapa.gids[k] >= 0:
                return mapa.gids[k]
        return None

    def gid_no_ponto(self, ponto) -> Optional[int]:
        """O glifo sob o ponto do clique: o cursor cai entre dois caracteres, e o lado do
        ponto diz qual (à esquerda da posição do cursor, o de antes). Um ponto fora do
        caractere (o branco depois do fim da linha) não é glifo."""
        cursor = self.cursorForPosition(ponto)
        posicao = cursor.position()
        if ponto.x() < self.cursorRect(cursor).x() and posicao > 0:
            posicao -= 1
        bloco = self.document().findBlock(posicao)
        mapa = bloco.userData() if bloco.isValid() else None
        i = posicao - bloco.position()
        if not isinstance(mapa, _MapaDoBloco) or not 0 <= i < len(mapa.gids) or mapa.gids[i] < 0:
            return None
        antes, depois = QTextCursor(self.document()), QTextCursor(self.document())
        antes.setPosition(posicao)
        depois.setPosition(posicao + 1)
        esquerda, direita = self.cursorRect(antes), self.cursorRect(depois)
        fim = direita.x()
        if direita.y() != esquerda.y():
            # O caractere termina a linha visual: a posição seguinte já está na de baixo, e a
            # borda direita dele vem da largura do próprio caractere.
            letra = bloco.text()[i:i + 1]
            fim = esquerda.x() + QFontMetrics(depois.charFormat().font()).horizontalAdvance(letra)
        if not esquerda.x() - 2 <= ponto.x() <= fim + 2:
            return None
        return mapa.gids[i]

    def gid_no_cursor(self) -> Optional[int]:
        if self.document().isEmpty():
            return None
        return self.gid_na_posicao(self.textCursor().position())

    def posicao_do_gid(self, gid: int) -> Optional[int]:
        bloco = self.document().begin()
        while bloco.isValid():
            mapa = bloco.userData()
            if isinstance(mapa, _MapaDoBloco) and gid in mapa.gids:
                return bloco.position() + mapa.gids.index(gid)
            bloco = bloco.next()
        return None

    def palavra_de(self, gid: int) -> List[int]:
        return list(self._palavra_do_gid.get(gid, []))

    def linha_de(self, gid: int) -> List[int]:
        """Os gids da linha impressa do glifo (para a faixa Linha)."""
        return list(self._linha_do_gid.get(gid, []))

    def ir_ao_gid(self, gid: Optional[int], rolar: bool = True) -> None:
        """Põe o cursor no glifo (sem avisar: foi o programa) e, com `rolar`, o mostra."""
        posicao = None if gid is None else self.posicao_do_gid(gid)
        if posicao is None:
            return
        anterior, self._movendo = self._movendo, True
        try:
            cursor = self.textCursor()
            cursor.setPosition(posicao)
            self.setTextCursor(cursor)
            if rolar:
                self.ensureCursorVisible()
        finally:
            self._movendo = anterior

    # ------------------------------------------------------------------
    # Realce, margens, corpo
    # ------------------------------------------------------------------
    def definir_realce(self, sim: bool) -> None:
        self.realce = bool(sim)
        self.remontar()

    def definir_corpo_padrao(self, corpo: int) -> None:
        """O corpo padrão da janela de agora; o corpo muda junto se o usuário não o mudou."""
        if self.corpo == self.corpo_padrao and corpo != self.corpo:
            self.corpo = corpo
            self.remontar()
        self.corpo_padrao = corpo

    def alternar_margens(self, mostrar: Optional[bool] = None) -> None:
        """Ctrl+Shift+H: mostra ou oculta cabeçalhos, rodapés e números de página (`mostrar`,
        o estado da ação marcável; sem ele, o contrário do de agora)."""
        self.mostrar_margens = (not self.mostrar_margens) if mostrar is None else bool(mostrar)
        self.remontar()

    def mudar_corpo(self, passo: int) -> None:
        """O zoom do Documento: o corpo do texto (passo 0 volta ao padrão)."""
        corpo = self.corpo_padrao if passo == 0 else self.corpo + passo
        corpo = max(CORPO_MINIMO, min(CORPO_MAXIMO, corpo))
        if corpo != self.corpo:
            self.corpo = corpo
            self.remontar()

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------
    def _cursor_mudou(self) -> None:
        if self._movendo or self._clicando:     # o clique avisa uma vez, no release
            return
        gid = self.gid_no_cursor()
        if gid is not None:
            self.cursor_na_palavra.emit(self.palavra_de(gid))

    def mousePressEvent(self, evento):
        self._clicando = evento.button() == Qt.MouseButton.LeftButton
        super().mousePressEvent(evento)

    def mouseReleaseEvent(self, evento):
        clicando, self._clicando = self._clicando, False
        super().mouseReleaseEvent(evento)
        if evento.button() != Qt.MouseButton.LeftButton:
            return
        if clicando and self.textCursor().hasSelection():
            self._cursor_mudou()                # um arraste que selecionou: o cursor avisa
        ancora = self.anchorAt(evento.position().toPoint())
        if ancora.startswith("copiar-fen:"):
            self.copiar_fen(ancora.split(":", 1)[1])
            return
        if self.textCursor().hasSelection():
            return
        gid = self.gid_no_ponto(evento.position().toPoint())
        if gid is not None:
            self.glifo_clicado.emit(gid, self.palavra_de(gid))

    def copiar_fen(self, diagrama_id: str) -> None:
        diagrama = self._diagramas.get(diagrama_id)
        if diagrama is not None and diagrama.lido:
            QGuiApplication.clipboard().setText(diagrama.fen)

    def marcar_atual(self, gid: Optional[int]) -> None:
        """O glifo atual da fila (§6.2: destacado nos dois), com fundo próprio que vale sem
        o foco no Documento (o cursor de texto só aparece com ele)."""
        self._gid_atual = gid
        posicao = None if gid is None else self.posicao_do_gid(gid)
        if posicao is None:
            self.setExtraSelections([])
            return
        fim = posicao + 1
        while fim < posicao + 8 and self._gid_no_caractere(fim) == gid:
            fim += 1                            # um glifo de mais de um caractere
        destaque = QTextEdit.ExtraSelection()
        destaque.format.setBackground(FUNDO_DO_ATUAL)
        destaque.format.setFontUnderline(True)
        destaque.format.setUnderlineColor(estilo.AZUL)
        cursor = QTextCursor(self.document())
        cursor.setPosition(posicao)
        cursor.setPosition(fim, QTextCursor.MoveMode.KeepAnchor)
        destaque.cursor = cursor
        self.setExtraSelections([destaque])

    def _gid_no_caractere(self, posicao: int) -> Optional[int]:
        bloco = self.document().findBlock(posicao)
        mapa = bloco.userData() if bloco.isValid() else None
        i = posicao - bloco.position()
        if isinstance(mapa, _MapaDoBloco) and 0 <= i < len(mapa.gids) and mapa.gids[i] >= 0:
            return mapa.gids[i]
        return None

    def ids_dos_diagramas(self) -> Set[str]:
        ids, bloco = set(), self.document().begin()
        while bloco.isValid():
            mapa = bloco.userData()
            if isinstance(mapa, _MapaDoBloco) and mapa.diagrama_id:
                ids.add(mapa.diagrama_id)
            bloco = bloco.next()
        return ids
