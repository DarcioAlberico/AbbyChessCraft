"""As cores da interface num lugar só: a cor de cada box diz de onde veio a leitura."""

from PySide6.QtGui import QColor

from abbychess.leitor import FONTE_LIVRO, FONTE_MANUAL

MANUAL = QColor(142, 68, 173)       # roxo: o usuário decidiu
LIVRO = QColor(39, 174, 96)         # verde: padrão deste livro
CONFIAVEL = QColor(41, 128, 185)    # azul: rede ou base global, acima do limiar
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

LEGENDA = [
    (MANUAL, "Confirmado por você"),
    (LIVRO, "Padrão deste livro"),
    (CONFIAVEL, "Rede ou base global"),
    (PENDENTE, "A revisar"),
    (SEM_LEITURA, "Sem leitura"),
    (DIAGRAMA, "Diagrama (fora do texto)"),
    (MARCADO, "Na seleção (Ctrl+clique)"),
]


def cor_do_diagrama(diagrama) -> QColor:
    """Tracejado do tabuleiro: cinza por ler, laranja a conferir, azul confiável, roxo conferido."""
    if diagrama.conferido:
        return MANUAL
    if not diagrama.lido:
        return DIAGRAMA
    return CONFIAVEL if diagrama.confiavel else PENDENTE


def cor_do_box(char: str, fonte: str, pendente: bool) -> QColor:
    if fonte == FONTE_MANUAL:
        return MANUAL
    if not char:
        return SEM_LEITURA
    if pendente:
        return PENDENTE
    if fonte == FONTE_LIVRO:
        return LIVRO
    return CONFIAVEL
