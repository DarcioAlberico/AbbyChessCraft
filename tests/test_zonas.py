"""O editor de áreas: geometria, áreas automáticas, reconhecer pelas áreas e gravar.

A página sintética é a de `test_treino_por_livro`: "abc abc abc" na primeira
linha e "cab bca" na segunda, nove e seis glifos.
"""

from __future__ import annotations

import json

import pytest

from core.box_model import BoxEntry

from abbychess import pagina as pg
from abbychess import zonas as zn
from abbychess.projeto import ProjetoDeLivro

from tests.test_treino_por_livro import _pagina_sintetica


@pytest.fixture
def projeto(tmp_path):
    fonte = _pagina_sintetica(tmp_path / "pagina.png")
    return ProjetoDeLivro.criar(tmp_path / "livros", "Areas", fonte)


@pytest.fixture
def imagem(projeto):
    return pg.FonteDePaginas(projeto.fonte).pagina(0)


def _linha(boxes, b):
    return min(b.y2, boxes[0].y2) > max(b.y1, boxes[0].y1)


# ----------------------------------------------------------------------
# Geometria
# ----------------------------------------------------------------------

def test_nova_ordena_os_cantos_e_corta_na_pagina():
    z = zn.nova(zn.TEXTO, (300, 200, -20, 50), 250, 150)
    assert z.caixa == (0, 50, 250, 150)
    with pytest.raises(ValueError):
        zn.nova(zn.TEXTO, (10, 10, 12, 100), 250, 150)
    with pytest.raises(ValueError):
        zn.nova("tabela", (0, 0, 50, 50), 250, 150)


def test_zona_em_prefere_a_menor_e_bordas_em_acha_o_canto():
    grande = zn.Zona(zn.TEXTO, 0, 0, 500, 500)
    pequena = zn.Zona(zn.IGNORAR, 100, 100, 200, 200)
    assert zn.zona_em([grande, pequena], 150, 150) == 1
    assert zn.zona_em([grande, pequena], 50, 50) == 0
    assert zn.zona_em([grande, pequena], 600, 50) is None
    assert zn.bordas_em(pequena, 101, 199, 4) == "eb"
    assert zn.bordas_em(pequena, 150, 150, 4) == ""
    assert zn.bordas_em(pequena, 197, 150, 4) == "d"


def test_arrastar_move_sem_sair_da_pagina_e_estica_sem_inverter():
    z = zn.Zona(zn.TEXTO, 100, 100, 200, 200)
    assert zn.arrastar(z, "", 30, -20, 1000, 1000).caixa == (130, 80, 230, 180)
    assert zn.arrastar(z, "", 5000, 5000, 1000, 1000).caixa == (900, 900, 1000, 1000)
    assert zn.arrastar(z, "d", 50, 0, 1000, 1000).caixa == (100, 100, 250, 200)
    esticada = zn.arrastar(z, "ec", 500, 500, 1000, 1000)
    assert esticada.x1 == 200 - zn.MENOR_LADO and esticada.y1 == 200 - zn.MENOR_LADO


def test_o_tipo_mais_restritivo_vence():
    zonas = [zn.Zona(zn.TEXTO, 0, 0, 100, 100), zn.Zona(zn.DIAGRAMA, 0, 0, 60, 60),
             zn.Zona(zn.IGNORAR, 0, 0, 30, 30)]
    assert zn.tipo_no_ponto(zonas, 10, 10) == zn.IGNORAR
    assert zn.tipo_no_ponto(zonas, 50, 50) == zn.DIAGRAMA
    assert zn.tipo_no_ponto(zonas, 80, 80) == zn.TEXTO
    assert zn.tipo_no_ponto(zonas, 200, 200) is None


# ----------------------------------------------------------------------
# Áreas automáticas e reconhecer pelas áreas
# ----------------------------------------------------------------------

def test_areas_automaticas_cobrem_o_texto_e_cercam_o_tabuleiro(imagem):
    boxes = pg.segmentar(imagem)
    largura, altura = imagem.size
    tabuleiro = (600, 20, 700, 120)
    zonas = zn.automaticas(boxes, [tabuleiro], largura, altura)
    textos = [z for z in zonas if z.tipo == zn.TEXTO]
    diagramas = [z for z in zonas if z.tipo == zn.DIAGRAMA]
    # Linha dupla: o vão é maior que uma altura de letra, e cada linha vira um bloco.
    assert len(textos) == 2
    assert all(any(t.contem((b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2) for t in textos)
               for b in boxes)
    d = diagramas[0]
    assert d.x1 < 600 and d.y1 < 20 and d.x2 > 700 and d.y2 > 120  # a margem das coordenadas


def test_areas_automaticas_reconhecem_a_mesma_coisa(imagem):
    """Reconhecer pelas áreas automáticas dá os mesmos boxes da segmentação inteira."""
    segmentada = pg.segmentar_pagina(imagem)
    largura, altura = imagem.size
    zonas = zn.automaticas(segmentada.boxes, segmentada.tabuleiros, largura, altura)
    pelas_areas = zn.segmentar_com_zonas(imagem, zonas)
    assert pelas_areas.boxes == segmentada.boxes


def _boxes_de(texto, x, y, altura=10, passo=8):
    return [BoxEntry(c, x + i * passo, y, x + i * passo + 6, y + altura)
            for i, c in enumerate(texto) if c != " "]


def test_areas_automaticas_dividem_as_funcoes_de_legenda_numero_e_titulo():
    boxes = (_boxes_de("CAPITULO", 320, 100, altura=20, passo=12)
             + _boxes_de("texto normal bastante longo", 100, 250)
             + _boxes_de("Diagrama 7 jogam pretas", 220, 630)
             + _boxes_de("42", 390, 960))
    zonas = zn.automaticas(boxes, [(200, 400, 600, 600)], 800, 1000, escala=10)

    funcoes = {z.funcao for z in zonas}
    assert {"titulo", "texto", "legenda", "numero_de_pagina", "diagrama"} <= funcoes


def test_classificacao_nao_altera_area_desenhada_pelo_usuario():
    boxes = _boxes_de("Diagrama 7", 100, 120)
    manual = zn.Zona(zn.TEXTO, 90, 110, 220, 140, funcao="texto", automatica=False)
    diagrama = zn.Zona(zn.DIAGRAMA, 90, 150, 250, 350, automatica=True)

    classificadas = zn.classificar_funcoes([manual, diagrama], boxes, 500, 500, 10)

    assert classificadas[0].funcao == "texto"


def test_ignorar_e_imagem_nao_geram_boxes(imagem):
    boxes = pg.segmentar(imagem)
    largura, altura = imagem.size
    primeira = [b for b in boxes if _linha(boxes, b)]
    meio = (max(b.y2 for b in primeira) + min(b.y1 for b in boxes if not _linha(boxes, b))) // 2
    tudo = zn.Zona(zn.TEXTO, 0, 0, largura, altura)
    for tipo in (zn.IGNORAR, zn.IMAGEM):
        embaixo = zn.Zona(tipo, 0, meio, largura, altura)
        segmentada = zn.segmentar_com_zonas(imagem, [tudo, embaixo])
        assert len(segmentada.boxes) == len(primeira) == 9
        assert segmentada.tabuleiros == []


def test_fora_das_areas_de_texto_nada_e_lido(imagem):
    boxes = pg.segmentar(imagem)
    primeira = [b for b in boxes if _linha(boxes, b)]
    so_a_primeira = zn.Zona(zn.TEXTO, 0, 0, imagem.size[0], max(b.y2 for b in primeira) + 5)
    assert len(zn.segmentar_com_zonas(imagem, [so_a_primeira]).boxes) == 9
    assert zn.segmentar(imagem, []).boxes == pg.segmentar_pagina(imagem).boxes


def test_diagrama_vira_tabuleiro_e_tira_o_texto_de_dentro(imagem):
    boxes = pg.segmentar(imagem)
    largura, altura = imagem.size
    tudo = zn.Zona(zn.TEXTO, 0, 0, largura, altura)
    a_direita = zn.Zona(zn.DIAGRAMA, 200, 0, largura, altura)
    segmentada = zn.segmentar_com_zonas(imagem, [tudo, a_direita])
    assert segmentada.tabuleiros == [a_direita.caixa]
    assert all((b.x1 + b.x2) / 2 < 200 for b in segmentada.boxes)
    assert 0 < len(segmentada.boxes) < len(boxes)


def test_tabuleiro_achado_dentro_do_diagrama_e_o_que_vale():
    boxes, tabuleiros = [], [(100, 100, 300, 300), (600, 600, 800, 800)]
    zonas = [zn.Zona(zn.DIAGRAMA, 80, 80, 320, 320), zn.Zona(zn.TEXTO, 500, 500, 900, 900)]
    texto, saida = zn.filtrar(boxes, tabuleiros, zonas)
    # O primeiro fica, justo; o segundo caiu numa área que o usuário disse ser texto.
    assert saida == [(100, 100, 300, 300)]


# ----------------------------------------------------------------------
# Gravar no projeto
# ----------------------------------------------------------------------

def test_areas_gravadas_voltam_iguais_e_nao_contam_como_pagina_lida(projeto):
    zonas = [zn.Zona(zn.TEXTO, 0, 0, 100, 100), zn.Zona(zn.IGNORAR, 10, 10, 50, 50)]
    projeto.salvar_zonas(0, zonas)
    gravadas = projeto.carregar_zonas(0)
    assert [(z.tipo, z.caixa) for z in gravadas] == [(z.tipo, z.caixa) for z in zonas]
    assert [z.id for z in gravadas] == ["z0", "z1"]           # cada área ganha um id (v2)
    assert projeto.carregar_zonas(1) == []
    assert projeto.paginas_lidas() == []
    assert projeto.carregar_pagina(0) is None
    assert projeto.estado_da_pagina(0) == "nao_reconhecida"
    projeto.salvar_zonas(0, [])
    assert projeto.carregar_zonas(0) == []


def test_projeto_antigo_abre_sem_areas_e_em_portugues(projeto):
    arquivo = projeto.pasta / "projeto.json"
    bruto = json.loads(arquivo.read_text(encoding="utf-8"))
    del bruto["idioma"]
    arquivo.write_text(json.dumps(bruto), encoding="utf-8")
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    assert reaberto.dados.idioma == "pt"
    assert reaberto.carregar_zonas(0) == []
    assert not (reaberto.pasta / "zonas").exists()
