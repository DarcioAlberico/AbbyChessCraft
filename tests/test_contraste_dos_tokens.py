"""CA-U7 (SPEC-pagina-perfeita, U-7; T1, bloco 4): o teste calcula as razões dos tokens.

- A borda de campos e botões pede 3:1 (WCAG 1.4.11) contra a janela, a base e o botão, nos dois
  temas; era 1,63:1 no claro.
- O amarelo da seleção (1,66:1 no papel) nunca fica sozinho: contorno duplo, o escuro por fora,
  como no visor. Valia na Linha, no corte do Glifo, no corte da Imagem e na casa do Diagrama.
- No editor Diagrama, a casa corrigida (verde) e a duvidosa (laranja) têm a mesma luminância:
  cada estado ganha um canto próprio, com contorno escuro, e não só a cor.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint  # noqa: E402

from core.box_model import BoxEntry  # noqa: E402
from core.tabuleiro_edicao import TabuleiroEdicao  # noqa: E402

from abbychess.app import editor_diagrama as dd  # noqa: E402
from abbychess.app import estilo  # noqa: E402
from abbychess.app.linha import ALTURA_DO_TEXTO, FaixaDaLinha  # noqa: E402
from abbychess.app.painel_treino import PainelDeTreino  # noqa: E402

TRES_PARA_UM = 3.0
#: Os glifos do teste em cinza: o preto do desenho é só o do contorno.
CINZA = 128


@pytest.mark.parametrize("tema", [estilo.CLARO, estilo.ESCURO], ids=lambda t: t.nome)
def test_a_borda_tem_3_para_1_contra_a_janela_a_base_e_o_botao(tema):
    for fundo in (tema.janela, tema.base, tema.botao):
        assert estilo.contraste(tema.borda, fundo) >= TRES_PARA_UM, (tema.nome, fundo.name())


def test_as_canetas_da_selecao_sao_o_escuro_por_fora_e_o_amarelo_por_dentro():
    fora, dentro = estilo.canetas_da_selecao(2)
    assert dentro.color() == estilo.SELECIONADO and fora.widthF() > dentro.widthF()
    for papel in (estilo.PAPEL, estilo.PAPEL_ESCURO):
        assert estilo.contraste(fora.color(), papel) >= TRES_PARA_UM
    assert estilo.contraste(fora.color(), estilo.SELECIONADO) >= TRES_PARA_UM


def _tem(imagem, cor, x0=0, y0=0, x1=None, y1=None) -> bool:
    x1 = imagem.width() if x1 is None else x1
    y1 = imagem.height() if y1 is None else y1
    return any(imagem.pixelColor(x, y).rgb() == cor.rgb()
               for x in range(x0, x1) for y in range(y0, y1))


def _pagina():
    matriz = np.full((100, 300), 255, np.uint8)
    boxes = []
    for k, char in enumerate("abc"):
        x = 40 + 40 * k
        matriz[40:60, x:x + 15] = CINZA
        boxes.append(BoxEntry(char, x, 40, x + 15, 60, 0.9, "net"))
    return matriz, boxes


def test_o_atual_da_linha_tem_o_contorno_duplo(app):
    faixa = FaixaDaLinha()
    faixa.resize(600, 80)
    matriz, boxes = _pagina()
    faixa.mostrar(matriz, boxes, 1)
    imagem = faixa.grab().toImage()
    ate = imagem.height() - ALTURA_DO_TEXTO               # só a imagem, sem as letras
    assert _tem(imagem, estilo.SELECIONADO, y1=ate)
    assert _tem(imagem, estilo.CONTORNO_DA_SELECAO, y1=ate)
    faixa.deleteLater()


def test_o_corte_do_glifo_tem_o_contorno_duplo(app):
    painel = PainelDeTreino()
    matriz, boxes = _pagina()
    painel.mostrar(matriz, boxes[0], "", tomar_o_foco=False)
    painel._definir_corte(boxes[0].x1 + 7)
    imagem = painel.glifo.pixmap().toImage()
    assert _tem(imagem, estilo.SELECIONADO) and _tem(imagem, estilo.CONTORNO_DA_SELECAO)
    painel.deleteLater()


def test_a_casa_selecionada_do_diagrama_tem_o_contorno_duplo(app):
    tabuleiro = dd.TabuleiroConferivel(TabuleiroEdicao.de_fen("4k3/8/8/8/8/8/8/4K3"))
    tabuleiro.selecionada = (4, 2)
    imagem = tabuleiro.grab().toImage()
    r = tabuleiro.retangulo(4, 2)
    caixa = (r.left(), r.top(), r.right() + 1, r.bottom() + 1)
    assert _tem(imagem, estilo.SELECIONADO, *caixa)
    assert _tem(imagem, estilo.CONTORNO_DA_SELECAO, *caixa)
    tabuleiro.deleteLater()


def test_cada_estado_da_casa_tem_o_seu_canto(app):
    assert len(set(dd.CANTO_DO_ESTADO.values())) == len(dd.CANTO_DO_ESTADO) == 3
    for casa in (estilo.CASA_CLARA, estilo.CASA_ESCURA):
        assert estilo.contraste(dd.CONTORNO_DO_CANTO, casa) >= TRES_PARA_UM
    tabuleiro = dd.TabuleiroConferivel(TabuleiroEdicao.de_fen("4k3/8/8/8/8/8/8/4K3"))
    vazias = [c for c in tabuleiro.tabuleiro.casas      # longe da moldura do tabuleiro
              if not c.simbolo and 1 <= c.linha <= 6 and 1 <= c.coluna <= 6]
    corrigida, arbitrada, duvidosa = vazias[0], vazias[9], vazias[18]
    corrigida.corrigida = True
    arbitrada.arbitrada = True
    duvidosa.simbolo, duvidosa.confianca = "N", 0.1
    imagem = tabuleiro.grab().toImage()
    for casa, estado in ((corrigida, "corrigida"), (arbitrada, "arbitrada"),
                         (duvidosa, "duvida")):
        r = tabuleiro.retangulo(casa.linha, casa.coluna)
        marcados = {canto for canto, ponto in _cantos(r).items()
                    if _tem(imagem, dd.CONTORNO_DO_CANTO, ponto.x() - 2, ponto.y() - 2,
                            ponto.x() + 3, ponto.y() + 3)}
        assert marcados == {dd.CANTO_DO_ESTADO[estado]}, (estado, marcados)
    tabuleiro.deleteLater()


def _cantos(r):
    """O ponto a 4 px de cada canto, por dentro da casa."""
    return {"topo_esquerdo": QPoint(r.left() + 4, r.top() + 4),
            "topo_direito": QPoint(r.right() - 4, r.top() + 4),
            "baixo_esquerdo": QPoint(r.left() + 4, r.bottom() - 4),
            "baixo_direito": QPoint(r.right() - 4, r.bottom() - 4)}
