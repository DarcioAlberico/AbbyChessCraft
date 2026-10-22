"""Dividir, juntar e ajustar boxes, como no treino de padrões do FineReader.

A página sintética é a de `test_treino_por_livro`: "abc abc abc" e "cab bca".
Juntar o "a" e o "b" do começo dá o box colado que a segmentação às vezes
entrega, como o "rp" da p. 27 do Darcy Lima; dividi-lo tem de devolver os dois.
"""

from __future__ import annotations

import pytest

from abbychess import pagina as pg
from abbychess import edicao as ed
from abbychess.leitor import FONTE_LIVRO, FONTE_MANUAL, LeitorDoLivro
from abbychess.projeto import ProjetoDeLivro
from abbychess.modelo import Box, Pagina

from tests.test_treino_por_livro import _pagina_sintetica


@pytest.fixture
def projeto(tmp_path):
    fonte = _pagina_sintetica(tmp_path / "pagina.png")
    return ProjetoDeLivro.criar(tmp_path / "livros", "Colados", fonte)


@pytest.fixture
def leitor(projeto):
    return LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)


@pytest.fixture
def imagem(projeto):
    return pg.FonteDePaginas(projeto.fonte).pagina(0)


def _caixa(b):
    return b.x1, b.y1, b.x2, b.y2


def _colar_ab(imagem, leitor):
    """Os boxes da página com o primeiro "a" e "b" num box só, e os dois originais."""
    boxes = pg.segmentar(imagem)
    a, b = boxes[0], boxes[1]
    pg.juntar(imagem, boxes, 0, 1, leitor)
    return boxes, a, b


def test_juntar_cobre_os_dois_e_tira_o_segundo(imagem, leitor):
    boxes = pg.segmentar(imagem)
    total, a, b, c = len(boxes), boxes[0], boxes[1], boxes[2]

    novo = pg.juntar(imagem, boxes, 1, 0, leitor)  # a ordem dos índices não importa

    assert novo == 0 and len(boxes) == total - 1
    assert _caixa(boxes[0]) == (a.x1, min(a.y1, b.y1), b.x2, max(a.y2, b.y2))
    assert boxes[1] is c
    assert boxes[0].source != FONTE_MANUAL  # relido, não herda a decisão antiga


def test_dividir_na_coluna_devolve_os_dois_glifos_aparados(imagem, leitor):
    boxes, a, b = _colar_ab(imagem, leitor)
    total = len(boxes)

    novos = pg.dividir(imagem, boxes, 0, leitor, x=(a.x2 + b.x1) // 2)

    assert novos == [0, 1] and len(boxes) == total + 1
    # Aparadas à tinta: o "a" volta à altura do x, sem a haste do "b".
    assert _caixa(boxes[0]) == _caixa(a)
    assert _caixa(boxes[1]) == _caixa(b)


def test_dividir_sem_coluna_corta_no_vao_da_tinta(imagem, leitor):
    boxes, a, b = _colar_ab(imagem, leitor)
    pg.dividir(imagem, boxes, 0, leitor)
    assert _caixa(boxes[0]) == _caixa(a)
    assert _caixa(boxes[1]) == _caixa(b)


def test_divisao_do_documento_usa_os_vaos_e_grava_letras_manuais(imagem, leitor):
    boxes, a, b = _colar_ab(imagem, leitor)
    pagina = Pagina(1, 0, [Box((1 << 20) + i, entry) for i, entry in enumerate(boxes)],
                    proximo_n=len(boxes))
    gid = pagina.boxes[0].gid
    dif = ed.dividir_em(pagina, imagem, gid, "ab", leitor)
    assert [box.entry.char for box in dif.novos] == ["a", "b"]
    assert [_caixa(box.entry) for box in dif.novos] == [_caixa(a), _caixa(b)]


def test_dividir_fora_do_box_ou_no_branco_e_recusado(imagem, leitor):
    boxes, a, b = _colar_ab(imagem, leitor)
    antes = list(boxes)
    with pytest.raises(ValueError, match="fora do box"):
        pg.dividir(imagem, boxes, 0, leitor, x=b.x2 + 5)
    assert boxes == antes

    # O "c" com folga em branco à direita, até o meio do espaço: o corte na folga
    # deixa um lado vazio.
    pg.ajustar(imagem, boxes, 1, leitor, direita=12)
    antes = list(boxes)
    with pytest.raises(ValueError, match="sem tinta"):
        pg.dividir(imagem, boxes, 1, leitor, x=boxes[1].x2 - 4)
    assert boxes == antes


def test_cada_parte_dividida_ensina_a_sua_letra(projeto, imagem, leitor):
    """O caso do "rp": dividido, cada letra vira um padrão, e não o par."""
    boxes, a, b = _colar_ab(imagem, leitor)
    pg.ler_boxes(imagem, boxes, leitor)
    pg.dividir(imagem, boxes, 0, leitor, x=(a.x2 + b.x1) // 2)

    pg.ensinar(imagem, boxes, 0, "a", leitor, projeto, pagina=0)
    pg.ensinar(imagem, boxes, 1, "b", leitor, projeto, pagina=0)

    assert set(leitor.padroes_por_caractere()) == {"a", "b"}
    # Os outros quatro "a" e quatro "b" da página saem dos padrões das partes.
    assert sum(x.char == "a" and x.source == FONTE_LIVRO for x in boxes) == 4
    assert sum(x.char == "b" and x.source == FONTE_LIVRO for x in boxes) == 4


def test_vizinho_so_na_mesma_linha(imagem):
    boxes = pg.segmentar(imagem)
    fim_da_linha = max(i for i, b in enumerate(boxes) if b.y1 < boxes[0].y2)
    assert pg.vizinho(boxes, 0, +1) == 1
    assert pg.vizinho(boxes, 0, -1) is None
    assert pg.vizinho(boxes, fim_da_linha, +1) is None  # o próximo é da linha de baixo
    assert pg.vizinho(boxes, len(boxes) - 1, +1) is None


def test_ajustar_move_as_bordas_dentro_da_pagina(imagem, leitor):
    boxes = pg.segmentar(imagem)
    pg.confirmar(boxes, 0, "a")
    x1, y1, x2, y2 = _caixa(boxes[0])

    pg.ajustar(imagem, boxes, 0, leitor, esquerda=-2, cima=1, direita=3, baixo=-1)
    assert _caixa(boxes[0]) == (x1 - 2, y1 + 1, x2 + 3, y2 - 1)
    assert boxes[0].source != FONTE_MANUAL  # a leitura era do desenho antigo

    pg.ajustar(imagem, boxes, 0, leitor, esquerda=-10_000, cima=-10_000)
    assert (boxes[0].x1, boxes[0].y1) == (0, 0)  # BoxService.clamp_box


def test_ajustar_nao_deixa_o_box_vazio(imagem, leitor):
    boxes = pg.segmentar(imagem)
    antes = _caixa(boxes[0])
    with pytest.raises(ValueError, match="vazio"):
        pg.ajustar(imagem, boxes, 0, leitor, direita=-(boxes[0].x2 - boxes[0].x1))
    assert _caixa(boxes[0]) == antes


def test_quadro_desenhado_vira_box_aparado_e_tira_os_de_dentro(imagem, leitor):
    boxes = pg.segmentar(imagem)
    total, a, b, c = len(boxes), boxes[0], boxes[1], boxes[2]

    # Folga em volta do "a" e do "b": o quadro sai aparado à tinta dos dois.
    indice = pg.criar_box(imagem, boxes, (b.x2 + 3, a.y2 + 9, a.x1 - 6, b.y1 - 4), leitor)

    assert indice == 0 and len(boxes) == total - 1
    assert _caixa(boxes[0]) == (a.x1, b.y1, b.x2, a.y2)
    assert boxes[1] is c  # a ordem de leitura continua


def test_quadro_sem_tinta_e_recusado(imagem, leitor):
    boxes = pg.segmentar(imagem)
    antes = list(boxes)
    with pytest.raises(ValueError, match="tinta"):
        pg.criar_box(imagem, boxes, (800, 5, 880, 30), leitor)
    with pytest.raises(ValueError, match="fora"):
        pg.criar_box(imagem, boxes, (5000, 5000, 5100, 5100), leitor)
    assert boxes == antes


def test_quadro_numa_pagina_sem_reconhecer(projeto, imagem, leitor):
    """Dá para treinar antes do F5: marcar o glifo, ensinar, e a leitura já o usa."""
    a = pg.segmentar(imagem)[0]
    boxes = []
    indice = pg.criar_box(imagem, boxes, (a.x1 - 3, a.y1 - 3, a.x2 + 3, a.y2 + 3), leitor)
    pg.ensinar(imagem, boxes, indice, "a", leitor, projeto, pagina=0)

    lidos = pg.segmentar(imagem)
    pg.ler_boxes(imagem, lidos, leitor)
    assert sum(x.char == "a" and x.source == FONTE_LIVRO for x in lidos) == 5


def test_ensinar_varios_grava_uma_amostra_por_box(projeto, imagem, leitor):
    boxes = pg.segmentar(imagem)
    pg.ler_boxes(imagem, boxes, leitor)
    resolvidos = pg.ensinar_varios(imagem, boxes, [0, 3], "a", leitor, projeto, pagina=0)
    assert len(leitor.padroes_por_caractere()["a"]) == 2
    assert boxes[0].source == boxes[3].source == FONTE_MANUAL
    assert resolvidos == 3  # os outros três "a"
