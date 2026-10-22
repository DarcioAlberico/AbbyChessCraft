"""As cores da interface que ainda não passaram para `app/estilo.py` (os boxes já passaram,
no A1): os diagramas, as áreas, a seleção e a palavra da verificação. O passo K leva o resto
para os tokens."""

from PySide6.QtGui import QColor

MANUAL = QColor(142, 68, 173)       # roxo: o diagrama conferido por você
CONFIAVEL = QColor(41, 128, 185)    # azul: o diagrama lido com confiança
PENDENTE = QColor(230, 126, 34)     # laranja: vai para a revisão
SEM_LEITURA = QColor(192, 57, 43)   # vermelho: ninguém leu
SELECIONADO = QColor(241, 196, 15)  # amarelo: o box em revisão
DIAGRAMA = QColor(127, 140, 141)    # cinza tracejado: tabuleiro, fora do texto
MARCADO = QColor(0, 188, 212)       # ciano: na seleção do modo de treino
PALAVRA = QColor(233, 30, 99)       # rosa: a palavra na verificação de texto

#: As áreas do editor de áreas, como as do FineReader: cada tipo com a sua cor.
COR_DA_ZONA = {
    "texto": QColor(46, 134, 222),
    "diagrama": QColor(39, 174, 96),
    "imagem": QColor(211, 84, 0),
    "ignorar": QColor(127, 140, 141),
}

COR_DA_FUNCAO = {
    "texto": QColor(46, 134, 222), "titulo": QColor(52, 73, 94),
    "cabecalho": QColor(142, 68, 173), "rodape": QColor(125, 60, 152),
    "numero_de_pagina": QColor(91, 44, 111), "nota": QColor(22, 160, 133),
    "legenda": QColor(243, 156, 18), "diagrama": QColor(39, 174, 96),
    "figura": QColor(211, 84, 0), "tabela": QColor(192, 57, 43),
    "ignorar": QColor(127, 140, 141),
}


def cor_do_diagrama(diagrama) -> QColor:
    """Tracejado do tabuleiro: cinza por ler, laranja a conferir, azul confiável, roxo conferido."""
    if diagrama.conferido:
        return MANUAL
    if not diagrama.lido:
        return DIAGRAMA
    return CONFIAVEL if diagrama.confiavel else PENDENTE

