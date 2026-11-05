"""As partes do desenho do Documento que não precisam da classe da vista: as linhas de um bloco
de texto e o formato do realce de um glifo (A-3: `app/documento.py` estava no limite)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QFont, QTextCharFormat

from abbychess import grade as gd
from abbychess.app import estilo


def escrever_as_linhas(vista, cursor, bloco, primeiro: bool, documento,
                       normal, estados, desconhecidos, virtuais, margens) -> bool:
    """As linhas de um bloco de texto, um parágrafo cada; a de margem, oculta, só no mapa da
    Linha. Devolve se ainda não houve parágrafo (o `primeiro` de `_preencher`)."""
    base = vista._formato_do_caractere(bloco.funcao)
    de_margem = vista._formato_do_caractere("cabecalho")
    escritas = 0
    for linha in bloco.linhas:
        gids = [g for p in linha.palavras for g in p.gids]
        margem = vista._de_margem(gids, documento, margens, virtuais)
        if margem and not vista.mostrar_margens:
            vista._linha_do_gid.update(dict.fromkeys(gids, gids))  # a Linha ainda a acha
            continue
        # O parágrafo abre só aqui: um bloco todo de margem, oculto, não deixa um vazio.
        if not primeiro:
            cursor.insertBlock(vista._formato_do_bloco(bloco.funcao, continua=bool(escritas)))
        else:
            cursor.setBlockFormat(vista._formato_do_bloco(bloco.funcao))
        primeiro = False
        escritas += 1
        vista._linha(cursor, linha, gids, documento, de_margem if margem else base, normal,
                     estados, desconhecidos, virtuais)
    return primeiro


def formato_novo(base: QTextCharFormat, estado: Optional[str], desconhecido: bool,
                 virtual: bool, estilo_do_glifo) -> QTextCharFormat:
    """O realce sobre o `base`: o negrito, o itálico e o sublinhado do glifo (None: sem
    estilo), o fundo da baixa confiança, o cinza do aguardando, o ondulado e o pontilhado."""
    formato = QTextCharFormat(base)
    if estilo_do_glifo is not None:
        formato.setFontWeight(QFont.Weight.Bold if estilo_do_glifo.negrito
                              else QFont.Weight.Normal)
        formato.setFontItalic(bool(estilo_do_glifo.italico))   # None: não medido
        formato.setFontUnderline(estilo_do_glifo.sublinhado)
    if estado == gd.FORTE:                      # o estado não depende só da cor: há traço (CA-F2.2)
        formato.setBackground(estilo.FUNDO_FORTE)
        formato.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
        formato.setUnderlineColor(estilo.TINTA)
        return formato
    if estado in (gd.PENDENTE, gd.SEM_LEITURA):
        formato.setBackground(estilo.FUNDO_DE_BAIXA_CONFIANCA)
    elif estado == gd.AGUARDANDO:
        formato.setForeground(estilo.CINZA)
    if desconhecido:
        formato.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
        formato.setUnderlineColor(estilo.VERMELHAO)
    elif virtual:
        formato.setUnderlineStyle(QTextCharFormat.UnderlineStyle.DotLine)
        formato.setUnderlineColor(estilo.AZUL)
    return formato
