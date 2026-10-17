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
- **A edição** (§6.3, passo D1): a vista guarda, de cada caractere, a unidade dele
  (`sessao.Unidade`: o glifo, o espaço, a quebra de linha, o diagrama). Editar abre uma
  sessão: o texto de agora comparado com o da montagem dá a menor sequência de palavras
  tocada (`sessao.palavras_em`), e ela cresce sozinha com as edições seguintes. A sessão
  confirma ao sair dela (cursor, clique, foco), com Enter (e vai à próxima palavra
  duvidosa), Shift+Enter ou Ctrl+Enter (e ensina o glifo sob o cursor): a janela leva as
  unidades e o texto ao controlador (`sessao_confirmada`), e o bloco é montado de novo do
  modelo. Esc (ou Ctrl+Z) restaura a sessão, e Ctrl+Y a reaplica (até outra montagem ou o
  cursor sair dela). Enter numa palavra sem mudança a aceita. O desfazer do `QTextDocument`
  fica desligado. Tocar um diagrama confirma na hora: o diagrama não sai (CA-6.8). Com uma
  sessão aberta, uma montagem que vem de fora (a propagação, o relógio do texto) espera o
  fim dela. A vista sabe, de cada caractere de agora, de qual caractere da montagem ele veio
  (`_origem`, mantida pelo `contentsChange`): o que nenhuma edição tocou fica com o glifo
  dele (`sessao.alinhar`, os `fixos`), e apagar o segundo "s" de "cassa" tira o segundo. O
  colar entra só como texto.

Montar de novo (uma edição, a propagação) não perde o lugar: o cursor volta ao mesmo gid e a
rolagem fica onde estava (CA-6.5).
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Set

import numpy as np
from PySide6.QtCore import QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QGuiApplication, QImage, QPainter, QPen,
                           QTextBlockFormat, QTextBlockUserData, QTextCharFormat, QTextCursor,
                           QTextDocument, QTextImageFormat)
from PySide6.QtWidgets import QMenu, QTextEdit

from abbychess import grade as gd
from abbychess import sessao as ss
from abbychess import texto as tx
from abbychess.app import estilo, teclado
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
#: A figurina branca e a preta de cada peça (o atalho repetido alterna, §6.4).
PRETA_DA_BRANCA = dict(zip("♔♕♖♗♘♙", "♚♛♜♝♞♟"))
BRANCA_DA_PRETA = {p: b for b, p in PRETA_DA_BRANCA.items()}


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
    #: A sessão confirmada: as unidades originais, o texto de agora, se avança à próxima
    #: duvidosa, o gid a ensinar (Ctrl+Enter, ou None), o último glifo da sessão e os pares
    #: (no original, no novo) que nenhuma edição tocou.
    sessao_confirmada = Signal(list, str, bool, object, object, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)                  # editável quando há página (montar)
        self.setUndoRedoEnabled(False)          # o desfazer é do projeto (§6.3)
        self.setAcceptRichText(False)           # colar e arrastar trazem só o texto
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
        #: As teclas que a vista entrega às ações (Enter, Shift+Enter, Ctrl+Z, Ctrl+Y): a
        #: exceção "redireciona" do YAML.
        self.teclas = teclado.AcoesDaTecla()
        #: A unidade de cada caractere do documento montado, e o texto dele.
        self._unidades: List[ss.Unidade] = []
        self._texto0 = ""
        #: A sessão aberta: o trecho [a, b) do texto da montagem que ela cobre.
        self._sessao: Optional[tuple] = None
        #: O número da sessão aberta: o confirmar agendado confere que ainda é ela.
        self._numero_da_sessao = 0
        #: De cada caractere do documento de agora, o índice dele no texto da montagem
        #: (None no que foi digitado); None se o `contentsChange` se perdeu.
        self._origem: Optional[List[Optional[int]]] = []
        self._montando = False
        self._pendente = None                   # a montagem que espera a sessão acabar
        #: (unidades, texto, fixos, a, b) do Esc, para o Ctrl+Y.
        self._restaurada: Optional[tuple] = None
        self._duvidosos: Set[int] = set()
        self._ultima_figurina: Optional[tuple] = None
        self.cursorPositionChanged.connect(self._cursor_mudou)

    # ------------------------------------------------------------------
    # Montar
    # ------------------------------------------------------------------
    def montar(self, documento: Optional[tx.Documento], diagramas: Sequence = (),
               estados: Optional[Dict[int, str]] = None, desconhecidos: Iterable[int] = (),
               virtuais: Iterable[int] = (), matriz: Optional[np.ndarray] = None,
               margens: Iterable[int] = (),
               aviso: str = "Página não reconhecida: F5 reconhece.") -> None:
        """O documento da página; sem documento (a página não reconhecida), o aviso.
        `margens`: os glifos do cabeçalho e do rodapé corridos, em cinza pequeno (a linha
        toda de margem; Ctrl+Shift+H a oculta), até as áreas terem função (passo F). Com
        uma sessão de edição aberta, a montagem espera o fim dela."""
        entrada = (documento, list(diagramas), dict(estados or {}), set(desconhecidos),
                   set(virtuais), matriz, set(margens), aviso)
        if self._sessao is not None:
            self._pendente = entrada
            return
        self._pendente = None
        self._restaurada = None                 # o Ctrl+Y vale só sobre a montagem do Esc
        self._entrada = entrada
        lugar = self._lugar()
        rolagem = self.verticalScrollBar().value()
        novo = QTextDocument(self)
        novo.setDefaultFont(QFont(FONTE, self.corpo))
        self._linha_do_gid, self._palavra_do_gid, self._diagramas = {}, {}, {}
        self._formatos = {}
        if documento is not None:
            self._preencher(novo, *self._entrada[:-1])
        else:
            formato = QTextCharFormat()
            formato.setForeground(estilo.CINZA)
            QTextCursor(novo).insertText(self._entrada[-1], formato)
        antigo = self.document()
        # O documento padrão do QTextEdit é do controle de texto, que o apaga no setDocument; o
        # nosso anterior (filho da vista) sai aqui, ou cada montagem o deixaria vivo.
        apagar = antigo is not novo and antigo.parent() is self
        self._movendo = self._montando = True
        try:
            self.setDocument(novo)
            self.setReadOnly(documento is None)
            self._guardar_as_unidades(virtuais)
            self._duvidosos = {g for g, e in (estados or {}).items()
                               if e in (gd.PENDENTE, gd.SEM_LEITURA, gd.AGUARDANDO)}
            self._duvidosos |= set(desconhecidos)
            self._voltar_ao_lugar(lugar)
            self.verticalScrollBar().setValue(rolagem)
            self.marcar_atual(self._gid_atual)
        finally:
            self._movendo = self._montando = False
        novo.contentsChange.connect(self._texto_mudou)
        if apagar:
            antigo.deleteLater()                # com as imagens dos diagramas e os formatos

    def _guardar_as_unidades(self, virtuais) -> None:
        """A unidade de cada caractere do documento montado (a sessão compara com ele)."""
        unidades: List[ss.Unidade] = []
        bloco = self.document().begin()
        primeiro = True
        while bloco.isValid():
            if not primeiro:
                unidades.append(ss.Unidade("\n", None, ss.LINHA))
            primeiro = False
            mapa = bloco.userData()
            texto = bloco.text()
            diagrama = isinstance(mapa, _MapaDoBloco) and mapa.diagrama_id is not None
            gids = mapa.gids if isinstance(mapa, _MapaDoBloco) else []
            for i, letra in enumerate(texto):
                gid = gids[i] if i < len(gids) else -1
                if diagrama or not isinstance(mapa, _MapaDoBloco):
                    unidades.append(ss.Unidade(letra, None, ss.OUTRO))
                elif gid >= 0:
                    unidades.append(ss.Unidade(letra, gid, ss.VIRTUAL if gid in virtuais
                                               else ss.GLIFO))
                else:
                    unidades.append(ss.Unidade(letra, None, ss.ESPACO))
            bloco = bloco.next()
        self._unidades = unidades
        self._texto0 = self.document().toPlainText()
        self._origem = list(range(len(self._texto0)))
        self._sessao = None

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
            if bloco.diagrama_id is not None:
                if not primeiro:
                    cursor.insertBlock()
                primeiro = False
                cursor.setBlockFormat(self._formato_do_bloco(bloco.funcao))
                self._por_diagrama(doc, cursor, self._diagramas.get(bloco.diagrama_id),
                                   numero.get(bloco.diagrama_id, 0), matriz)
                continue
            base = self._formato_do_caractere(bloco.funcao)
            de_margem = self._formato_do_caractere("cabecalho")
            escritas = 0
            for linha in bloco.linhas:
                gids = [g for p in linha.palavras for g in p.gids]
                margem = self._de_margem(gids, documento, margens, virtuais)
                if margem and not self.mostrar_margens:
                    for g in gids:                  # a Linha ainda acha a linha dela
                        self._linha_do_gid[g] = gids
                    continue
                # O parágrafo abre só aqui: um bloco todo de margem, oculto, não deixa um vazio.
                if not primeiro:
                    cursor.insertBlock(self._formato_do_bloco(bloco.funcao, continua=bool(escritas)))
                else:
                    cursor.setBlockFormat(self._formato_do_bloco(bloco.funcao))
                primeiro = False
                escritas += 1
                self._linha(cursor, linha, documento, de_margem if margem else base, normal,
                            estados, desconhecidos, virtuais)

    @staticmethod
    def _de_margem(gids, documento, margens, virtuais) -> bool:
        """A linha é de margem quando os glifos lidos dela (não o □ nem o virtual) estão todos
        nas margens corridas, e há pelo menos um."""
        lidos = [g for g in gids if g not in virtuais
                 and documento.chars.get(g, tx.NAO_LIDO) != tx.NAO_LIDO]
        return bool(lidos) and all(g in margens for g in lidos)

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
        linha = diagrama.linha_de_texto(numero, com_ressalva=False)
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
        if self._sessao is not None and not self._montando:
            if not self._dentro_da_sessao(self.textCursor().position()):
                self._confirmar_depois()        # saiu dela
            return                              # na sessão, os mapas estão velhos
        if self._movendo or self._clicando:     # o clique avisa uma vez, no release
            return
        if self._restaurada is not None:        # o cursor saiu da palavra do Esc
            _u, _t, _f, a, b = self._restaurada
            if not a <= self.textCursor().position() <= b:
                self._restaurada = None
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

    # ------------------------------------------------------------------
    # A edição (§6.3, passo D1)
    # ------------------------------------------------------------------
    @property
    def tem_sessao(self) -> bool:
        return self._sessao is not None

    @property
    def pode_reaplicar(self) -> bool:
        return self._restaurada is not None and self._sessao is None

    def _texto_mudou(self, posicao: int, removidos: int, inseridos: int) -> None:
        if self._montando:
            return
        atual = self.document().toPlainText()
        antes = self._texto0
        if self._origem is not None:
            self._origem[posicao:posicao + removidos] = [None] * inseridos
            if len(self._origem) != len(atual):
                self._origem = None             # o Qt contou diferente: sem os fixos
        if atual == antes:
            self._sessao = None
            self._origem = list(range(len(antes)))
            return
        inicio = 0
        limite = min(len(atual), len(antes))
        while inicio < limite and atual[inicio] == antes[inicio]:
            inicio += 1
        fim = 0
        while fim < limite - inicio and atual[-1 - fim] == antes[-1 - fim]:
            fim += 1
        a, b = ss.palavras_em(self._unidades, inicio, len(antes) - fim)
        if self._sessao is None:
            self._numero_da_sessao += 1
        self._sessao = (a, b)
        self._restaurada = None
        if any(u.tipo == ss.OUTRO for u in self._unidades[a:b]):
            # Um diagrama tocado: confirma já (o texto apagado sai, o diagrama volta).
            self._confirmar_depois()

    def _confirmar_depois(self) -> None:
        """Confirma a sessão aberta agora no próximo giro do laço de eventos, se ela ainda
        estiver aberta: nunca outra, nem a palavra sob o cursor (o aceitar do Enter)."""
        numero = self._numero_da_sessao

        def confirmar():
            if self._sessao is not None and self._numero_da_sessao == numero:
                self.confirmar(avancar=False)
        QTimer.singleShot(0, confirmar)

    def _fixos(self, a: int, b: int) -> List[tuple]:
        """Os pares (no original, no novo) da sessão [a, b) que nenhuma edição tocou."""
        if self._origem is None:
            return []
        atual = self.document().toPlainText()
        fim = b + len(atual) - len(self._texto0)
        return [(o - a, k - a) for k, o in enumerate(self._origem[a:fim], a)
                if o is not None and a <= o < b and self._texto0[o] == atual[k]]

    def _texto_da_sessao(self) -> str:
        a, b = self._sessao
        atual = self.document().toPlainText()
        return atual[a:b + len(atual) - len(self._texto0)]

    def _dentro_da_sessao(self, posicao: int) -> bool:
        a, b = self._sessao
        return a <= posicao <= b + len(self.document().toPlainText()) - len(self._texto0)

    def confirmar(self, avancar: bool = False, ensinar: bool = False) -> None:
        """Enter (`avancar`), Shift+Enter, Ctrl+Enter (`ensinar`), ou sair da sessão. Sem
        sessão, é aceitar a palavra sob o cursor (Enter numa palavra sem mudança)."""
        if self.document().isEmpty() or not self._unidades:
            return
        posicao = self.textCursor().position()
        if self._sessao is None:
            a, b = ss.palavras_em(self._unidades, posicao, posicao)
            if not any(u.glifo for u in self._unidades[a:b]):
                if avancar:
                    self.ir_a_proxima_duvidosa(posicao)
                return
            novo = self._texto0[a:b]
            fixos = [(k, k) for k in range(len(novo))]
        else:
            a, b = self._sessao
            novo = self._texto_da_sessao()
            fixos = self._fixos(a, b)
        unidades = self._unidades[a:b]
        alvo = ss.gid_no_cursor(unidades, novo, posicao - a, fixos) if ensinar else None
        ultimo = next((u.gid for u in reversed(unidades) if u.glifo), None)
        self._sessao, self._restaurada = None, None
        self.sessao_confirmada.emit(list(unidades), novo, avancar, alvo, ultimo, fixos)

    def restaurar(self) -> None:
        """Esc (ou Ctrl+Z na sessão): a palavra volta ao que era; Ctrl+Y a reaplica."""
        if self._sessao is None:
            return
        a, b = self._sessao
        restaurada = (list(self._unidades[a:b]), self._texto_da_sessao(), self._fixos(a, b), a, b)
        self._sessao = None
        entrada = self._pendente or self._entrada
        if entrada is not None:
            self.montar(*entrada)
        self._restaurada = restaurada

    def esquecer_a_restaurada(self) -> None:
        """O Ctrl+Z e o Ctrl+Y do projeto: o Ctrl+Y não reaplica mais a palavra do Esc."""
        self._restaurada = None

    def reaplicar(self) -> None:
        """Ctrl+Y depois do Esc: a sessão restaurada, confirmada como estava."""
        if not self.pode_reaplicar:
            return
        unidades, novo, fixos, _a, _b = self._restaurada
        self._restaurada = None
        ultimo = next((u.gid for u in reversed(unidades) if u.glifo), None)
        self.sessao_confirmada.emit(unidades, novo, False, None, ultimo, fixos)

    def ir_a_proxima_duvidosa(self, depois_de: int) -> bool:
        """O cursor no começo da próxima palavra com um glifo duvidoso (pendente, sem
        leitura, aguardando, fora do léxico), depois da posição `depois_de`."""
        unidades = self._unidades
        k = depois_de
        while k < len(unidades) and unidades[k].tipo not in (ss.ESPACO, ss.LINHA):
            k += 1                              # o fim da palavra de agora
        for i in range(k, len(unidades)):
            if unidades[i].glifo and unidades[i].gid in self._duvidosos:
                a, _b = ss.palavras_em(unidades, i, i)
                cursor = self.textCursor()
                cursor.setPosition(a)
                self.setTextCursor(cursor)
                self.ensureCursorVisible()
                return True
        return False

    def ir_ao_fim_do_gid(self, gid: Optional[int]) -> None:
        posicao = None if gid is None else self.posicao_do_gid(gid)
        if posicao is None:
            return
        fim = posicao + 1
        while fim < posicao + 8 and self._gid_no_caractere(fim) == gid:
            fim += 1
        cursor = self.textCursor()
        cursor.setPosition(fim)
        self.setTextCursor(cursor)

    def inserir_figurina(self, branca: str) -> None:
        """Ctrl+Shift+K/Q/R/B/N/P: a figurina no cursor; o mesmo atalho de novo alterna a cor
        da que acabou de entrar (§6.4)."""
        if self.isReadOnly():
            return
        cursor = self.textCursor()
        posicao = cursor.position()
        anterior = self.document().characterAt(posicao - 1) if posicao else ""
        if self._ultima_figurina == (posicao, branca) and anterior in (branca, PRETA_DA_BRANCA[branca]):
            cursor.deletePreviousChar()
            figura = PRETA_DA_BRANCA[branca] if anterior == branca else branca
        else:
            figura = branca
        cursor.insertText(figura)
        self.setTextCursor(cursor)
        self._ultima_figurina = (cursor.position(), branca)

    def abrir_paleta(self) -> None:
        """F2 no Documento: a paleta no cursor; o símbolo escolhido entra nele."""
        if self.isReadOnly():
            return
        from abbychess.app.painel_treino import FONTE_DE_SIMBOLOS, NOMES_DOS_SIMBOLOS, PALETA

        menu = QMenu(self)
        menu.setFont(QFont(FONTE_DE_SIMBOLOS, 12))
        for simbolo in PALETA:
            menu.addAction(f"{simbolo}   {NOMES_DOS_SIMBOLOS.get(simbolo, '')}",
                           lambda s=simbolo: self.textCursor().insertText(s))
        self.menu_da_paleta = menu              # os testes escolhem sem abrir
        menu.popup(self.viewport().mapToGlobal(self.cursorRect().bottomLeft()))

    def event(self, evento):
        teclas = self.__dict__.get('teclas')     # o Qt chama event() já no __init__
        if teclas is not None and teclas.sobrepor(evento):
            return True
        return super().event(evento)

    def keyPressEvent(self, evento):
        if self.teclas.disparar(evento):
            return
        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return                              # nunca um parágrafo novo no Documento
        super().keyPressEvent(evento)

    def focusOutEvent(self, evento):
        super().focusOutEvent(evento)
        if self._sessao is not None and evento.reason() != Qt.FocusReason.PopupFocusReason:
            self._confirmar_depois()            # o clique fora

