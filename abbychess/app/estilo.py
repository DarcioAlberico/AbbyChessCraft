"""Os tokens da aparência (SPEC §13): por enquanto, os estados dos boxes na página.

Cada estado tem cor (da paleta Okabe-Ito, legível para quem não distingue vermelho e
verde) e traço distintos: a cor sozinha não carrega o sentido. Os traços são cosméticos (a
largura é da tela, não da página) e de pelo menos 1,5 px, a não ser o dos aceitos, que é
discreto de propósito (1 px a 25%): o que chama o olho é o que falta revisar.

O resto da folha de estilo (espaçamentos, tipografia, tema escuro) é do passo K.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from abbychess import grade as gd

# A paleta Okabe-Ito.
LARANJA = QColor(230, 159, 0)
VERMELHAO = QColor(213, 94, 0)
AZUL = QColor(0, 114, 178)
VERDE_AZULADO = QColor(0, 158, 115)
ROXO_AVERMELHADO = QColor(204, 121, 167)
CINZA = QColor(110, 110, 110)
PRETO = QColor(0, 0, 0)


@dataclass(frozen=True)
class Traco:
    cor: QColor
    largura: float
    estilo: Qt.PenStyle
    #: Opacidade do preenchimento (0 = sem preenchimento), para o estado que chama o olho.
    preenchimento: int = 0


#: O desenho de cada estado, com os aceitos discretos (sem "mostrar origem").
TRACOS: Dict[str, Traco] = {
    gd.PENDENTE: Traco(LARANJA, 1.8, Qt.PenStyle.DashLine, 40),
    gd.SEM_LEITURA: Traco(VERMELHAO, 2.6, Qt.PenStyle.DotLine, 40),
    gd.AGUARDANDO: Traco(CINZA, 1.5, Qt.PenStyle.DashDotLine),
    gd.MANUAL: Traco(QColor(0, 0, 0, 64), 1.0, Qt.PenStyle.SolidLine),
    gd.LIVRO: Traco(QColor(0, 0, 0, 64), 1.0, Qt.PenStyle.SolidLine),
    gd.REDE: Traco(QColor(0, 0, 0, 64), 1.0, Qt.PenStyle.SolidLine),
}

#: Com "mostrar origem" (V): cada aceito na cor da origem dele.
TRACOS_DA_ORIGEM: Dict[str, Traco] = {
    gd.MANUAL: Traco(ROXO_AVERMELHADO, 1.5, Qt.PenStyle.SolidLine),
    gd.LIVRO: Traco(VERDE_AZULADO, 1.5, Qt.PenStyle.SolidLine),
    gd.REDE: Traco(AZUL, 1.5, Qt.PenStyle.SolidLine),
}


def traco(estado: str, mostrar_origem: bool) -> Traco:
    if mostrar_origem and estado in TRACOS_DA_ORIGEM:
        return TRACOS_DA_ORIGEM[estado]
    return TRACOS[estado]
