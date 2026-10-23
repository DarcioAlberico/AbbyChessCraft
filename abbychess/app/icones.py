"""Os ícones da interface (SPEC §13 e §18.5): SVG do Lucide 0.460.0 (licença ISC, em
`icones/LICENSE`), sem marca nenhuma, pintados com a cor do texto do tema de agora.

O SVG do Lucide desenha com `currentColor`: aqui ele vira a cor do tema (a do texto; a
secundária no ícone desabilitado; a do texto sobre o destaque no selecionado) antes de
rasterizar, em vários tamanhos para a tela de alta densidade. O tema mudou, `aplicar` os faz
de novo. Só os SVG usados moram no pacote (o pacote do Lucide tem 1.500).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from abbychess.app import estilo

PASTA = Path(__file__).with_name("icones")
#: O atributo da ação na janela -> o nome do ícone no Lucide.
DA_JANELA: Dict[str, str] = {
    "acao_novo": "file-plus", "acao_abrir": "folder-open", "acao_exportar": "file-output",
    "acao_localizar": "search", "acao_substituir": "replace", "acao_opcoes": "settings",
    "acao_teclado": "keyboard", "acao_sair": "log-out",
    "acao_desfazer": "undo-2", "acao_refazer": "redo-2",
    "acao_anterior": "chevron-left", "acao_seguinte": "chevron-right",
    "acao_primeira": "chevrons-left", "acao_ultima": "chevrons-right",
    "acao_reconhecer": "scan-text", "acao_reler": "refresh-cw", "acao_lote": "book-open-check",
    "acao_ajustar": "maximize", "acao_zoom_mais": "zoom-in", "acao_zoom_menos": "zoom-out",
    "acao_modo_treino": "square-dashed-mouse-pointer", "acao_areas": "layout-dashboard",
    "acao_diagramas": "grid-3x3", "acao_realce": "highlighter", "acao_margens": "panel-top",
}
#: Os lados rasterizados: o Qt escolhe o mais perto do pedido vezes a densidade da tela.
LADOS = (16, 20, 24, 32, 40)


@lru_cache(maxsize=None)
def _svg(nome: str) -> bytes:
    return (PASTA / f"{nome}.svg").read_bytes()


def _pixmap(svg: bytes, lado: int) -> QPixmap:
    pixmap = QPixmap(lado, lado)
    pixmap.fill(estilo.TRANSPARENTE)
    pintor = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg)).render(pintor)
    pintor.end()
    return pixmap


def icone(nome: str) -> QIcon:
    """O ícone `nome` do Lucide nas cores do tema de agora."""
    tema = estilo.tema()
    resultado = QIcon()
    # O Active, sem pixmap próprio, usa o Normal.
    for modo, cor in ((QIcon.Mode.Normal, tema.texto), (QIcon.Mode.Disabled, tema.texto_secundario),
                      (QIcon.Mode.Selected, tema.texto_do_destaque)):
        svg = _svg(nome).replace(b"currentColor", cor.name().encode("ascii"))
        for lado in LADOS:
            resultado.addPixmap(_pixmap(svg, lado), modo)
    return resultado


def aplicar(janela) -> None:
    """Os ícones nas ações da janela, no tema de agora (de novo quando ele muda)."""
    feitos: Dict[str, QIcon] = {}
    for atributo, nome in DA_JANELA.items():
        acao = getattr(janela, atributo, None)
        if acao is not None:
            if nome not in feitos:
                feitos[nome] = icone(nome)
            acao.setIcon(feitos[nome])
