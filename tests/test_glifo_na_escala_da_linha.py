"""CA-U9 (SPEC-pagina-perfeita, U-9; T1, bloco 4): o recorte do Glifo usa a escala da linha
dele, e não estica cada glifo a 140 px; um traço marca a linha de base.

Antes, a vírgula e o apóstrofo, o `o` e o `O`, saíam todos com 140 px de altura: perdiam o
tamanho e a linha de base, justo nos pares que o glifo isolado não resolve.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.box_model import BoxEntry  # noqa: E402

from abbychess.app import estilo  # noqa: E402
from abbychess.app.painel_treino import ALTURA_DO_GLIFO, PainelDeTreino, faixa_da_linha  # noqa: E402

#: (char, y1, y2): o "O" alto, o "o" de x-height, a vírgula que desce da linha de base.
GLIFOS = (("O", 100, 140), ("o", 115, 140), (",", 134, 148), ("d", 98, 140))


def _pagina():
    matriz = np.full((300, 400), 255, np.uint8)
    boxes = []
    for k, (char, y1, y2) in enumerate(GLIFOS):
        x = 40 + 40 * k
        matriz[y1:y2, x:x + 20] = 0
        boxes.append(BoxEntry(char, x, y1, x + 20, y2, 0.9, "net"))
    return matriz, boxes


def _linhas_com_tinta(painel) -> int:
    """Quantas linhas do pixmap têm tinta preta (a do glifo; o traço da base é cinza)."""
    imagem = painel.glifo.pixmap().toImage()
    return sum(1 for y in range(imagem.height())
               if any(imagem.pixelColor(x, y).value() < 30 for x in range(imagem.width())))


@pytest.fixture
def painel(app):
    painel = PainelDeTreino()
    yield painel
    painel.deleteLater()


def test_a_faixa_da_linha_e_o_topo_a_base_e_o_pe():
    _matriz, boxes = _pagina()
    assert faixa_da_linha(boxes) == (98, 140, 148)       # a base: a mediana dos pés


def test_dois_glifos_de_alturas_diferentes_mantem_a_razao(painel):
    matriz, boxes = _pagina()
    alturas = {}
    for box in boxes:
        painel.mostrar(matriz, box, "", tomar_o_foco=False, linha=boxes)
        assert painel.glifo.pixmap().height() == ALTURA_DO_GLIFO      # a linha inteira: 140 px
        alturas[box.char] = _linhas_com_tinta(painel)
    assert alturas["O"] / alturas["o"] == pytest.approx(40 / 25, rel=0.08)
    assert alturas[","] < alturas["o"] < alturas["O"]


def test_o_traco_da_linha_de_base_fica_na_altura_da_base(painel):
    matriz, boxes = _pagina()
    painel.mostrar(matriz, boxes[1], "", tomar_o_foco=False, linha=boxes)
    imagem = painel.glifo.pixmap().toImage()
    escala = ALTURA_DO_GLIFO / (148 - 98)
    y = round((140 - 98) * escala)
    linhas = [yy for yy in range(imagem.height())
              if imagem.pixelColor(0, yy) == estilo.TINTA_SECUNDARIA]     # na borda, sem tinta
    assert linhas and min(abs(yy - y) for yy in linhas) <= 1


def test_sem_a_linha_o_glifo_ocupa_a_altura_toda_como_antes(painel):
    matriz, boxes = _pagina()
    painel.mostrar(matriz, boxes[2], "", tomar_o_foco=False)
    assert painel.glifo.pixmap().height() == ALTURA_DO_GLIFO
    assert _linhas_com_tinta(painel) == ALTURA_DO_GLIFO


def test_o_corte_continua_na_coluna_clicada(painel):
    """A largura do recorte é a do glifo: o clique que escolhe a coluna do Ctrl+D não muda."""
    matriz, boxes = _pagina()
    box = boxes[0]
    painel.mostrar(matriz, box, "", tomar_o_foco=False, linha=boxes)
    painel._clicar_no_glifo(0.5)
    assert painel.corte == box.x1 + 10


def test_a_janela_passa_a_linha_do_glifo_atual(app, tmp_path, sim):
    """O Glifo da janela recebe a linha do glifo atual: a faixa vai do topo ao pé dela."""
    from abbychess.projeto import ProjetoDeLivro
    from tests.ajudantes import _abrir, _ler_a_mao, _pagina_sintetica

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Linha",
                                   _pagina_sintetica(tmp_path / "pagina.png"))
    j = _abrir(projeto)
    try:
        _ler_a_mao(app, j)
        p = j.pagina
        j._atual_mudou()
        linha = j.boxes_da_linha(p.atual)
        assert len(linha) > 1 and p.box_atual() in linha
        assert j.treino._faixa == faixa_da_linha(linha)
    finally:
        j.close()
