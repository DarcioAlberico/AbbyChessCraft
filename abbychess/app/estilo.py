"""Os tokens da aparência (SPEC §13): as cores, os traços, os espaços, a tipografia e o tema.

**Nenhuma cor literal fora daqui** em `app/` (CA-13.3, conferido por AST em
`tests/test_estilo.py`). Há dois tipos de token:

- **Os do papel**, que nunca invertem: a página na Imagem, a faixa Linha, o Documento (é o
  livro), os tabuleiros e as miniaturas. Os estados dos boxes, a seleção, as áreas e os
  destaques são desenhados sobre papel nos dois temas, e o contraste deles é medido contra o
  **papel de referência** (CA-13.2: o fundo do índice 25 do livro de referência no gabarito,
  255) e também contra um papel mais escuro (`PAPEL_ESCURO`, 230: a digitalização amarelada),
  ≥ 3:1 nos dois.
- **Os da interface**, que seguem o tema do sistema (`Tema`: `CLARO` e `ESCURO`): a paleta
  Qt e a folha de estilo saem deles (`aplicar`), e mudar o tema do sistema troca os dois sem
  reiniciar (`acompanhar_o_sistema`). Os rótulos de dica, aviso, erro e acerto não têm cor
  própria: têm um **papel** (`papel(widget, "dica")`), que a folha de estilo pinta no tema de
  agora.

Cada estado de box tem cor (a paleta Okabe-Ito, escurecida até o contraste de 3:1, legível
para quem não distingue vermelho e verde) **e** traço distintos: a cor sozinha não carrega o
sentido. Os traços são cosméticos (a largura é da tela, não da página) e de pelo menos 1,5 px,
a não ser o dos aceitos, discreto de propósito (1 px a 25%): o que chama o olho é o que falta
revisar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QPalette

from abbychess import grade as gd

# ----------------------------------------------------------------------
# A paleta Okabe-Ito, escurecida até 3:1 contra o papel (CA-13.2)
# ----------------------------------------------------------------------
#
# As originais (laranja 230,159,0; vermelhão 213,94,0; verde-azulado 0,158,115; roxo
# 204,121,167) davam 1,8:1, 3,1:1, 2,7:1 e 2,5:1 contra o cinza 230 (revisão do A1). Mesma
# matiz, mais escuras; o azul e o cinza já passavam.
LARANJA = QColor(176, 96, 0)
VERMELHAO = QColor(200, 70, 0)
AZUL = QColor(0, 114, 178)
VERDE_AZULADO = QColor(0, 120, 85)
ROXO_AVERMELHADO = QColor(150, 60, 120)
CINZA = QColor(110, 110, 110)
PRETO = QColor(0, 0, 0)
BRANCO = QColor(255, 255, 255)
TRANSPARENTE = QColor(0, 0, 0, 0)             # o fundo dos ícones rasterizados

#: O papel de referência (o gabarito do Xadrez Vitorioso, índice 25) e um papel mais escuro.
PAPEL = QColor(255, 255, 255)
PAPEL_ESCURO = QColor(230, 230, 230)
#: A tinta sobre o papel (o Documento, a Linha, o tabuleiro) e a secundária.
TINTA = QColor(0, 0, 0)
TINTA_SECUNDARIA = QColor(110, 110, 110)


@dataclass(frozen=True)
class Traco:
    cor: QColor
    largura: float
    estilo: Qt.PenStyle
    #: Opacidade do preenchimento (0 = sem preenchimento), para o estado que chama o olho.
    preenchimento: int = 0
    #: O padrão do traço quando o estilo é `CustomDashLine` (traço, vão… em larguras).
    padrao: Tuple[float, ...] = ()


#: O desenho de cada estado, com os aceitos discretos (sem "mostrar origem").
TRACOS: Dict[str, Traco] = {
    gd.PENDENTE: Traco(LARANJA, 1.8, Qt.PenStyle.DashLine, 40),
    gd.SEM_LEITURA: Traco(VERMELHAO, 2.6, Qt.PenStyle.DotLine, 40),
    gd.AGUARDANDO: Traco(CINZA, 1.5, Qt.PenStyle.DashDotLine),
    gd.MANUAL: Traco(QColor(0, 0, 0, 64), 1.0, Qt.PenStyle.SolidLine),
    gd.LIVRO: Traco(QColor(0, 0, 0, 64), 1.0, Qt.PenStyle.SolidLine),
    gd.REDE: Traco(QColor(0, 0, 0, 64), 1.0, Qt.PenStyle.SolidLine),
}

#: Com "mostrar origem" (V): cada aceito na cor da origem dele, com traço próprio.
TRACOS_DA_ORIGEM: Dict[str, Traco] = {
    gd.MANUAL: Traco(ROXO_AVERMELHADO, 1.5, Qt.PenStyle.SolidLine),
    gd.LIVRO: Traco(VERDE_AZULADO, 1.5, Qt.PenStyle.DashDotDotLine),
    gd.REDE: Traco(AZUL, 1.5, Qt.PenStyle.CustomDashLine, padrao=(6, 2, 1, 2)),
}

#: Abaixo deste zoom, o preenchimento dos boxes pendentes cobriria a letra (revisão de
#: produto do A2, a 22%): só o contorno.
ZOOM_SEM_PREENCHIMENTO = 0.4

#: A legenda do painel de treino: o estado, se ele precisa do V, e o texto.
LEGENDA = [
    (gd.PENDENTE, False, "A revisar"),
    (gd.SEM_LEITURA, False, "Sem leitura"),
    (gd.AGUARDANDO, False, "Aguardando leitura"),
    (gd.MANUAL, False, "Aceito (discreto; V mostra a origem)"),
    (gd.MANUAL, True, "Confirmado por você (com V)"),
    (gd.LIVRO, True, "Padrão deste livro (com V)"),
    (gd.REDE, True, "Rede ou base global (com V)"),
]


def traco(estado: str, mostrar_origem: bool) -> Traco:
    if mostrar_origem and estado in TRACOS_DA_ORIGEM:
        return TRACOS_DA_ORIGEM[estado]
    return TRACOS[estado]


# ----------------------------------------------------------------------
# Os outros tokens do papel
# ----------------------------------------------------------------------

#: A seleção (§3.3: contorno duplo): o amarelo por dentro e o escuro por fora, que se vê em
#: papel branco e em ilustração escura.
SELECIONADO = QColor(241, 196, 15)
CONTORNO_DA_SELECAO = QColor(0, 0, 0)
MARCADO = QColor(0, 128, 140)               # ciano: na seleção do modo de treino
PALAVRA = QColor(194, 24, 91)               # rosa: a palavra na verificação de texto
#: Em volta da página na Imagem.
FUNDO_DA_IMAGEM = QColor(90, 90, 90)

#: O tracejado do tabuleiro na Imagem, pelo estado do diagrama.
DIAGRAMA_POR_LER = CINZA
DIAGRAMA_A_CONFERIR = LARANJA
DIAGRAMA_CONFIAVEL = AZUL
DIAGRAMA_CONFERIDO = ROXO_AVERMELHADO

#: As áreas do editor de áreas, como as do FineReader: cada tipo e cada função com a sua cor.
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

#: O Documento é papel nos dois temas: os fundos dos destaques são deste papel.
FUNDO_DE_BAIXA_CONFIANCA = QColor(255, 226, 184)
#: O glifo atual (revisão de produto do A3: o azul-claro de antes sumia sobre um □).
FUNDO_DO_ATUAL = QColor(150, 200, 255)
FUNDO_DA_SESSAO = QColor(255, 246, 200)
FUNDO_DA_BUSCA = QColor(255, 232, 130)
FUNDO_DA_OCORRENCIA = QColor(255, 170, 70)

#: A faixa Linha: o glifo atual em destaque e a tinta dele.
FUNDO_DO_GLIFO_DA_LINHA = QColor(255, 248, 220)
TINTA_DO_GLIFO_DA_LINHA = QColor(90, 70, 0)

#: O tabuleiro desenhado (editor Diagrama, Documento, miniaturas).
CASA_CLARA = QColor(240, 217, 181)
CASA_ESCURA = QColor(181, 136, 99)
CASA_ESCURA_DO_DOCUMENTO = QColor(181, 196, 166)
MOLDURA_DO_TABULEIRO = QColor(90, 90, 90)
#: A borda dos quadros de papel na interface (o glifo ampliado, o recorte da palavra).
BORDA_DO_PAPEL = QColor(153, 153, 153)
FUNDO_SEM_IMAGEM = QColor(240, 240, 240)
#: As marcas do editor Diagrama sobre as casas (com transparência: a peça aparece).
CASA_CORRIGIDA = QColor(39, 174, 96, 90)
CASA_ARBITRADA = QColor(192, 57, 43, 90)
CASA_DUVIDOSA = QColor(230, 126, 34, 90)


def cor_do_diagrama(diagrama) -> QColor:
    """Tracejado do tabuleiro: cinza por ler, laranja a conferir, azul confiável, roxo conferido."""
    if diagrama.conferido:
        return DIAGRAMA_CONFERIDO
    if not diagrama.lido:
        return DIAGRAMA_POR_LER
    return DIAGRAMA_CONFIAVEL if diagrama.confiavel else DIAGRAMA_A_CONFERIR


# ----------------------------------------------------------------------
# Espaços, raios e tipografia
# ----------------------------------------------------------------------

ESPACOS = (4, 8, 12, 16, 24)
RAIO = 4
FONTE_DA_INTERFACE = "Segoe UI"
CORPO_DA_INTERFACE = 9
FONTE_DOS_SIMBOLOS = "Segoe UI Symbol"
#: O menor alvo de clique (§13: ≥ 24 px).
ALVO_MINIMO = 24


# ----------------------------------------------------------------------
# O tema da interface
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class Tema:
    nome: str
    janela: QColor
    base: QColor
    base_alternada: QColor
    texto: QColor
    texto_secundario: QColor
    botao: QColor
    borda: QColor
    destaque: QColor
    texto_do_destaque: QColor
    dica_fundo: QColor
    erro: QColor
    aviso: QColor
    acerto: QColor
    link: QColor


CLARO = Tema("claro", janela=QColor(240, 240, 240), base=QColor(255, 255, 255),
             base_alternada=QColor(246, 246, 246), texto=QColor(20, 20, 20),
             texto_secundario=QColor(85, 85, 85), botao=QColor(240, 240, 240),
             borda=QColor(190, 190, 190), destaque=QColor(0, 114, 178),
             texto_do_destaque=QColor(255, 255, 255), dica_fundo=QColor(255, 255, 225),
             erro=QColor(176, 40, 30), aviso=QColor(160, 85, 0), acerto=QColor(0, 110, 70),
             link=QColor(0, 90, 160))
ESCURO = Tema("escuro", janela=QColor(37, 37, 38), base=QColor(30, 30, 30),
              base_alternada=QColor(45, 45, 48), texto=QColor(230, 230, 230),
              texto_secundario=QColor(170, 170, 170), botao=QColor(55, 55, 58),
              borda=QColor(80, 80, 85), destaque=QColor(86, 156, 214),
              texto_do_destaque=QColor(0, 0, 0), dica_fundo=QColor(60, 60, 64),
              erro=QColor(255, 120, 110), aviso=QColor(240, 175, 80),
              acerto=QColor(110, 210, 150), link=QColor(120, 180, 255))
TEMAS = {CLARO.nome: CLARO, ESCURO.nome: ESCURO}

#: Os papéis de rótulo que a folha de estilo pinta, e o campo do tema de cada um.
PAPEIS = {"dica": "texto_secundario", "erro": "erro", "aviso": "aviso", "acerto": "acerto"}

_atual = CLARO


def tema() -> Tema:
    """O tema aplicado agora."""
    return _atual


def tema_do_sistema() -> str:
    """"escuro" se o sistema pede o esquema escuro; "claro" no resto (e sem resposta)."""
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    if app is None:
        return CLARO.nome
    try:
        esquema = app.styleHints().colorScheme()
    except AttributeError:                      # Qt sem o esquema de cores (< 6.5)
        return CLARO.nome
    return ESCURO.nome if esquema == Qt.ColorScheme.Dark else CLARO.nome


def paleta(t: Tema) -> QPalette:
    p = QPalette()
    papeis = {QPalette.ColorRole.Window: t.janela, QPalette.ColorRole.WindowText: t.texto,
              QPalette.ColorRole.Base: t.base, QPalette.ColorRole.AlternateBase: t.base_alternada,
              QPalette.ColorRole.Text: t.texto, QPalette.ColorRole.Button: t.botao,
              QPalette.ColorRole.ButtonText: t.texto, QPalette.ColorRole.Highlight: t.destaque,
              QPalette.ColorRole.HighlightedText: t.texto_do_destaque,
              QPalette.ColorRole.ToolTipBase: t.dica_fundo, QPalette.ColorRole.ToolTipText: t.texto,
              QPalette.ColorRole.PlaceholderText: t.texto_secundario,
              QPalette.ColorRole.Link: t.link, QPalette.ColorRole.Mid: t.borda}
    for papel_, cor in papeis.items():
        p.setColor(papel_, cor)
    for papel_ in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                   QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, papel_, t.texto_secundario)
    return p


def folha_de_estilo(t: Tema) -> str:
    """A folha de estilo do tema: os papéis dos rótulos, o foco visível e as dicas."""
    linhas = [f'QLabel[papel="{nome}"] {{ color: {getattr(t, campo).name()}; }}'
              for nome, campo in PAPEIS.items()]
    linhas.append(f"QToolTip {{ color: {t.texto.name()}; background: {t.dica_fundo.name()}; "
                  f"border: 1px solid {t.borda.name()}; padding: {ESPACOS[0]}px; }}")
    return "\n".join(linhas) + "\n"


class _Avisos(QObject):
    """Avisa quem guardou cor da interface (um pincel de item de lista, um HTML) que o tema
    mudou: a paleta e a folha de estilo se refazem sozinhas, o que foi guardado não."""

    tema_mudou = Signal(str)


_avisos = None


def avisos() -> _Avisos:
    global _avisos
    if _avisos is None:
        _avisos = _Avisos()
    return _avisos


def na_interface(cor_do_papel: QColor) -> QColor:
    """Uma cor de estado (feita para o papel) para usar sobre a interface: no tema claro,
    ela mesma; no escuro, clareada até o contraste de leitura (4,5:1) contra a base."""
    if _atual is CLARO:
        return QColor(cor_do_papel)
    cor_ = QColor(cor_do_papel)
    for _ in range(12):
        if contraste(cor_, _atual.base) >= 4.5:
            break
        cor_ = cor_.lighter(118)
    return cor_


def cor(nome: str) -> QColor:
    """Uma cor do tema de agora pelo nome do campo ("texto_secundario", "erro"…)."""
    return getattr(_atual, nome)


def hex_de(nome: str) -> str:
    """A cor do tema de agora em `#rrggbb`, para o texto rico (HTML) dos painéis."""
    return cor(nome).name()


def papel(widget, nome: str) -> None:
    """Dá ao rótulo um papel ("dica", "erro", "aviso", "acerto", ou "" para nenhum): a folha
    de estilo o pinta no tema de agora, e de novo quando o tema muda."""
    if nome and nome not in PAPEIS:
        raise ValueError(f"papel desconhecido: {nome!r}")
    if (widget.property("papel") or "") == nome:
        return                                  # o mesmo: sem repolir (é caro)
    widget.setProperty("papel", nome)
    estilo_qt = widget.style()
    estilo_qt.unpolish(widget)
    estilo_qt.polish(widget)


def aplicar(app, nome: str = "") -> Tema:
    """Aplica o tema `nome` ("claro", "escuro"; vazio: o do sistema): paleta e folha de
    estilo. Devolve o tema aplicado."""
    global _atual
    _atual = TEMAS.get(nome or tema_do_sistema(), CLARO)
    app.setPalette(paleta(_atual))
    app.setStyleSheet(folha_de_estilo(_atual))
    avisos().tema_mudou.emit(_atual.nome)
    return _atual


def acompanhar_o_sistema(app) -> None:
    """Muda o tema quando o do sistema muda (CA-13.3), sem reiniciar."""
    try:
        app.styleHints().colorSchemeChanged.connect(lambda _esquema: aplicar(app))
    except AttributeError:                      # Qt sem o sinal: fica o tema da abertura
        pass


def papel_de_papel(widget) -> None:
    """O widget que mostra o livro (o Documento) é papel nos dois temas: fundo branco e
    tinta preta, como a página."""
    p = widget.palette()
    p.setColor(QPalette.ColorRole.Base, PAPEL)
    p.setColor(QPalette.ColorRole.Text, TINTA)
    widget.setPalette(p)


def contraste(a: QColor, b: QColor) -> float:
    """O contraste WCAG entre duas cores opacas (a transparência se compõe sobre `b`)."""
    def linear(c: float) -> float:
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    def luminancia(c: QColor) -> float:
        return 0.2126 * linear(c.red()) + 0.7152 * linear(c.green()) + 0.0722 * linear(c.blue())

    alfa = a.alpha() / 255.0
    composta = QColor(round(a.red() * alfa + b.red() * (1 - alfa)),
                      round(a.green() * alfa + b.green() * (1 - alfa)),
                      round(a.blue() * alfa + b.blue() * (1 - alfa)))
    claro, escuro = sorted((luminancia(composta), luminancia(b)), reverse=True)
    return (claro + 0.05) / (escuro + 0.05)

