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
from abbychess.diagramas import DiagramaLido
from abbychess.projeto import ProjetoDeLivro

from tests.ajudantes import _pagina_sintetica  # noqa: E402,F401,F811


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


def test_legenda_automatica_fica_ligada_ao_diagrama_mais_proximo_e_persiste():
    zonas = [
        zn.Zona(zn.TEXTO, 100, 420, 300, 450, id="z0", funcao="legenda", automatica=True),
        zn.Zona(zn.TEXTO, 500, 420, 700, 450, id="z1", funcao="legenda", automatica=True),
    ]
    diagramas = [DiagramaLido((100, 100, 300, 400), id="d0"),
                 DiagramaLido((500, 100, 700, 400), id="d1")]

    ligadas = zn.vincular_legendas(zonas, diagramas)
    restauradas = [zn.Zona.de_dict(z.como_dict()) for z in ligadas]

    assert [z.diagrama_id for z in restauradas] == ["d0", "d1"]


def test_vinculo_manual_de_legenda_nao_e_recalculado():
    manual = zn.Zona(zn.TEXTO, 100, 420, 300, 450, funcao="legenda",
                     automatica=False, diagrama_id="d1")
    diagramas = [DiagramaLido((100, 100, 300, 400), id="d0"),
                 DiagramaLido((500, 100, 700, 400), id="d1")]

    assert zn.vincular_legendas([manual], diagramas)[0].diagrama_id == "d1"


def test_funcao_de_margem_so_muda_zona_automatica_inteiramente_classificada():
    boxes = _boxes_de("CABECALHO", 100, 20) + _boxes_de("corpo", 100, 100)
    cabecalho = zn.Zona(zn.TEXTO, 90, 10, 190, 45, automatica=True)
    corpo = zn.Zona(zn.TEXTO, 90, 90, 190, 125, automatica=True)
    manual = zn.Zona(zn.TEXTO, 90, 10, 190, 45, automatica=False)
    funcoes = {i: "cabecalho" for i in range(len("CABECALHO"))}

    classificadas = zn.aplicar_funcoes_de_margem([cabecalho, corpo, manual], boxes, funcoes)

    assert [z.funcao for z in classificadas] == ["cabecalho", "texto", "texto"]


def test_titulo_centralizado_e_nota_menor_no_pe_sao_classificados():
    boxes = (_boxes_de("Um titulo", 360, 100)
             + _boxes_de("corpo normal bastante longo", 100, 300, altura=12)
             + _boxes_de("nota curta", 100, 850, altura=7))
    zonas = zn.automaticas(boxes, [], 800, 1000, escala=10)

    assert [z.funcao for z in zonas] == ["titulo", "texto", "nota"]


def test_recuo_da_primeira_linha_abre_outro_bloco():
    boxes = (_boxes_de("primeiro paragrafo", 100, 100)
             + _boxes_de("continua aqui", 100, 120)
             + _boxes_de("novo paragrafo", 120, 140))

    zonas = zn.automaticas(boxes, [], 800, 1000, escala=10)

    assert len(zonas) == 2


def test_modelo_de_areas_conserva_funcoes_e_recusa_outra_resolucao():
    original = zn.Zona(zn.TEXTO, 10, 20, 100, 80, id="z9", funcao="titulo", ordem=2)
    modelo = zn.ModeloDeAreas(800, 1000, (original,))

    [aplicada] = modelo.aplicar(800, 1000)

    assert aplicada.funcao == "titulo" and aplicada.ordem == 2 and aplicada.id == "z0"
    with pytest.raises(ValueError, match="resolução"):
        modelo.aplicar(801, 1000)


def test_ordenar_exige_todas_as_areas_uma_vez():
    zonas = [zn.Zona(zn.TEXTO, i * 20, 0, i * 20 + 10, 10) for i in range(4)]
    ordenadas = zn.ordenar(zonas, [3, 2, 1, 0])
    assert [z.ordem for z in ordenadas] == [3, 2, 1, 0]
    with pytest.raises(ValueError):
        zn.ordenar(zonas, [0, 1, 1, 3])


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
    assert projeto.resumo.paginas_lidas() == []
    assert projeto.carregar_pagina(0) is None
    assert projeto.resumo.estado_da_pagina(0) == "nao_reconhecida"
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


# ----------------------------------------------------------------------
# Fechamento do passo F: legendas lado a lado, a regra da legenda e a zona do usuário
# ----------------------------------------------------------------------

def _linha_de_boxes(texto, x, y, passo=12, altura=16):
    """Uma linha de boxes, um por letra, a partir de (x, y); o espaço é um vão de um passo."""
    from core.box_model import BoxEntry

    saida = []
    for c in texto:
        if c != " ":
            saida.append(BoxEntry(c, x, y, x + passo - 2, y + altura, 0.99, "neural"))
        x += passo
    return saida


def test_legendas_lado_a_lado_viram_duas_zonas_ligadas_a_cada_diagrama():
    """Dois tabuleiros lado a lado, com "Diagrama 6…" e "Diagrama 7…" na mesma linha: duas
    legendas, uma para cada diagrama (CA-5.1, a ligação da legenda)."""
    from types import SimpleNamespace

    tabuleiros = [(50, 50, 330, 330), (420, 50, 700, 330)]
    # Como na p. 25 do Xadrez Vitorioso: cada legenda sob o seu tabuleiro, com um vão de
    # mais de 8 alturas de letra entre elas.
    boxes = (_linha_de_boxes("Diagrama 6. Jogam as brancas.", 60, 345, passo=8)
             + _linha_de_boxes("Diagrama 7. Jogam as brancas.", 430, 345, passo=8))
    zonas = zn.automaticas(boxes, tabuleiros, 760, 1000, escala=16)
    legendas = [z for z in zonas if z.funcao == "legenda"]
    assert len(legendas) == 2
    diagramas = [SimpleNamespace(id=f"d{k}", caixa=c) for k, c in enumerate(tabuleiros)]
    ligadas = zn.vincular_legendas(legendas, diagramas)
    assert sorted(z.diagrama_id for z in ligadas) == ["d0", "d1"]


def test_prosa_e_lances_abaixo_do_diagrama_nao_sao_legenda():
    tabuleiro = [(50, 50, 330, 330)]
    for texto in ("Black moves the knight to f6 and the game is equal again after all",
                  "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6"):
        zonas = zn.automaticas(_linha_de_boxes(texto, 55, 345, passo=5), tabuleiro, 760, 1000,
                               escala=16)
        assert not any(z.funcao == "legenda" for z in zonas), texto
    for texto in ("Diagrama 5. Jogam as pretas.", "White to play", "12"):
        zonas = zn.automaticas(_linha_de_boxes(texto, 60, 345), tabuleiro, 760, 1000, escala=16)
        assert any(z.funcao == "legenda" for z in zonas), texto


def test_a_zona_mexida_pelo_usuario_deixa_de_ser_automatica():
    zona = zn.Zona(zn.TEXTO, 0, 0, 100, 100, funcao="cabecalho", automatica=True, id="z0")
    for mexer in (lambda zs: zn.trocar_funcao(zs, 0, "texto"),
                  lambda zs: zn.trocar_tipo(zs, 0, zn.IGNORAR)):
        zonas = [zona]
        mexer(zonas)
        assert zonas[0].automatica is False
    assert zn.arrastar(zona, "d", 10, 0, 500, 500).automatica is False


def test_a_legenda_tolera_o_ocr_so_no_diagrama():
    """"Dia9rama", "iagrama" (o OCR) são legenda; a prosa curta que lembra "teste" ("These
    squares", "Tea time") não é: a tolerância vale só para a palavra longa."""
    for texto in ("Dia9rama 5. J09am as pretas.", "iagrama 3.", "Teste 1", "Diag ama 8."):
        assert zn._parece_legenda(texto), texto
    for texto in ("These squares", "Tea time", "Testing the plan", "Tesla moves", "Teen"):
        assert not zn._parece_legenda(texto), texto


def test_areas_antes_de_ler_saem_texto_e_o_f5_as_classifica():
    """O fluxo do FineReader: as áreas feitas antes de reconhecer (boxes sem leitura) não
    viram título pelo tamanho; depois de ler, as que continuam automáticas ganham a função
    pelo texto (a legenda, ligada ao diagrama), e a do usuário fica."""
    from core.box_model import BoxEntry

    tabuleiro = [(50, 50, 330, 330)]
    lidos = (_linha_de_boxes("Diagrama 5. Jogam as pretas.", 60, 345)
             + _linha_de_boxes("O corpo do texto segue aqui, com as letras de sempre.", 60, 500,
                               passo=10))
    sem_leitura = [BoxEntry("", b.x1, b.y1, b.x2, b.y2, 0.0, "aguardando") for b in lidos]
    antes = zn.automaticas(sem_leitura, tabuleiro, 760, 1000)
    assert all(z.funcao in ("texto", "diagrama") for z in antes)
    desenhada = zn.Zona(zn.TEXTO, 600, 900, 700, 960, funcao="nota", id="zu")
    depois = zn.reclassificar_automaticas(antes + [desenhada], lidos, 760, 1000)
    assert any(z.funcao == "legenda" for z in depois)
    assert depois[-1] == desenhada


def test_a_linha_de_lances_com_o_numero_mal_lido_nao_e_titulo():
    """No Xadrez Vitorioso o OCR leu "21.exf4" como "2lI.exf4": as casas ainda dizem lance."""
    assert zn._parece_lances("2lI.exf4 3.Cf3 f5?")
    assert zn._parece_lances("2lI.exf43.Cf3f5?")              # o texto da área, sem espaços
    assert not zn._parece_lances("Partidasde1972e1980")
    assert zn._parece_lances("exf4 Cf3 f5")
    assert zn._parece_lances("O-O e Txe8")
    assert not zn._parece_lances("TROCAR PEÇAS PARA TER UM FINAL VITORIOSO")
    assert not zn._parece_lances("Capítulo 1: a abertura")


@pytest.mark.parametrize("linha", [
    "Bb5 Bc4",          # português e inglês: B, o bispo
    "Ab5 Ac4",          # espanhol: A, o alfil
    "Sf3 Lb5",          # alemão: S, o Springer; L, o Läufer
    "Fb5 Fc4",          # francês: F, o fou
])
def test_a_linha_de_lances_de_qualquer_idioma_nao_e_titulo(linha):
    """Uma linha curta de lances, centrada e sozinha, é texto: as letras das peças de todos
    os idiomas de `modelo.PECAS` dizem lance, não só as do português e do inglês."""
    largura, passo = 1000, 12
    x = (largura - len(linha) * passo) // 2
    boxes = _linha_de_boxes(linha, x, 300, passo=passo)
    zona = zn.Zona(zn.TEXTO, x - 4, 296, x + len(linha) * passo + 4, 320, automatica=True)
    [classificada] = zn.classificar_funcoes([zona], boxes, largura, 1400, 16)
    assert classificada.funcao == "texto"


def test_a_pagina_lida_sem_areas_ganha_as_automaticas():
    """O lote e o F5: sem área nenhuma, as automáticas pela leitura (o título chega ao
    Documento e ao sumário); sem leitura, nada; com áreas, as do usuário ficam."""
    titulo = _linha_de_boxes("CAPITULO", 300, 100, passo=24, altura=32)
    corpo = [b for y in range(300, 700, 30) for b in _linha_de_boxes("texto corrido aqui", 100, y)]
    zonas = zn.depois_de_ler([], titulo + corpo, [], [], 1000, 1400)
    assert zonas and all(z.automatica for z in zonas)
    assert "titulo" in {z.funcao for z in zonas}
    sem_leitura = [BoxEntry("", b.x1, b.y1, b.x2, b.y2) for b in corpo]
    assert zn.depois_de_ler([], sem_leitura, [], [], 1000, 1400) == []
    do_usuario = [zn.Zona("texto", 0, 0, 1000, 1400)]
    assert zn.depois_de_ler(do_usuario, titulo + corpo, [], [], 1000, 1400) == do_usuario


def test_as_linhas_curtas_embaixo_da_legenda_a_continuam_e_a_prosa_nao():
    """"Gormon-Silman / Memorial Ervin, 1987" embaixo de "Diagrama 5…", cada uma na sua
    zona: as duas continuam a legenda; a linha longa de prosa logo depois, não."""
    tabuleiro = [(50, 50, 330, 330)]
    boxes = (_linha_de_boxes("Diagrama 5. Jogam as pretas.", 60, 345)
             + _linha_de_boxes("Gormon-Silman", 60, 381)
             + _linha_de_boxes("Memorial Ervin, 1987", 60, 417)
             + _linha_de_boxes("O corpo do texto segue aqui, com as letras de sempre.", 60, 453,
                               passo=10))
    zonas = zn.automaticas(boxes, tabuleiro, 760, 1000, escala=16)
    textos = sorted((z for z in zonas if z.tipo == zn.TEXTO), key=lambda z: z.y1)
    assert [z.funcao for z in textos] == ["legenda", "legenda", "legenda", "texto"]


def test_o_ponto_solto_da_digitalizacao_fica_fora_do_texto():
    boxes = _boxes_de("texto normal bastante longo", 100, 250) + _boxes_de(".", 400, 600)
    zonas = zn.automaticas(boxes, [], 800, 1000, escala=10)
    assert [(z.tipo, z.funcao) for z in sorted(zonas, key=lambda z: z.y1)] == [
        (zn.TEXTO, "texto"), (zn.IGNORAR, "ignorar")]


# ----------------------------------------------------------------------
# As regras que a mutação achou sem teste (Q9, CA-Q-M1)
# ----------------------------------------------------------------------

def _automatica(x1, y1, x2, y2, tipo=zn.TEXTO, **mais):
    """Uma área automática (a que a classificação pode mexer), com a caixa dada."""
    return zn.Zona(tipo, x1, y1, x2, y2, automatica=True, **mais)


def _funcoes(zonas, boxes, largura=2000, altura=1000, escala=10):
    """As funções das áreas classificadas, na ordem delas. A página larga não centra nada."""
    return [z.funcao for z in zn.classificar_funcoes(zonas, boxes, largura, altura, escala)]


def _linha_mista(texto, x, y):
    """Uma linha com as maiúsculas mais altas (14 px, 4 acima das minúsculas, de 10)."""
    return [BoxEntry(c, x + i * 8, y - 4 if c.isupper() else y, x + i * 8 + 6, y + 10)
            for i, c in enumerate(texto) if c != " "]


def test_a_menor_area_tem_8_pixels_de_lado_e_o_canto_de_cima_para_no_zero():
    assert zn.nova(zn.TEXTO, (100, 100, 108, 108), 500, 500).caixa == (100, 100, 108, 108)
    for estreita in ((100, 100, 107, 200), (100, 100, 200, 107)):
        with pytest.raises(ValueError):
            zn.nova(zn.TEXTO, estreita, 500, 500)
    assert zn.nova(zn.TEXTO, (50, -30, 120, 60), 500, 500).caixa == (50, 0, 120, 60)


def test_a_imagem_sobre_o_diagrama_vence_e_o_tabuleiro_de_dentro_some():
    diagrama, imagem = zn.Zona(zn.DIAGRAMA, 0, 0, 400, 400), zn.Zona(zn.IMAGEM, 0, 0, 400, 400)
    assert zn.filtrar([], [(100, 100, 300, 300)], [diagrama, imagem]) == ([], [])


def test_o_glifo_com_o_centro_na_borda_da_area_e_dela():
    area = zn.Zona(zn.TEXTO, 100, 100, 200, 200)
    nas_bordas = [BoxEntry("a", 95, 145, 105, 155), BoxEntry("b", 195, 145, 205, 155),
                  BoxEntry("c", 145, 95, 155, 105), BoxEntry("d", 145, 195, 155, 205)]
    fora = BoxEntry("e", 196, 145, 206, 155)
    assert zn.filtrar(nas_bordas + [fora], [], [area])[0] == nas_bordas


def test_a_area_gravada_volta_igual_e_a_do_formato_v1_vem_do_usuario():
    legenda = zn.Zona(zn.TEXTO, 10, 20, 300, 60, id="z7", funcao="legenda", ordem=3,
                      automatica=True, diagrama_id="d2")
    assert zn.Zona.de_dict(legenda.como_dict()) == legenda
    v1 = zn.Zona.de_dict({"tipo": "imagem", "caixa": [1, 2, 300, 400]})
    assert (v1.id, v1.funcao, v1.ordem, v1.automatica, v1.diagrama_id) == (
        "", "figura", None, False, None)
    titulo = zn.Zona.de_dict({"tipo": "texto", "funcao": "titulo", "caixa": [0, 0, 100, 40],
                              "diagrama_id": "d0"})
    assert titulo.diagrama_id is None                  # só a legenda é de um diagrama


def test_a_area_estreita_na_borda_da_grande_e_a_que_o_clique_e_o_glifo_pegam():
    grande = zn.Zona(zn.TEXTO, 0, 0, 300, 300)
    coluna = zn.Zona(zn.IGNORAR, 250, 0, 300, 300)
    faixa = zn.Zona(zn.IGNORAR, 0, 250, 300, 300)
    assert zn.zona_em([grande, coluna], 275, 150) == 1
    assert zn.zona_em([grande, faixa], 150, 275) == 1
    assert zn.zona_que_vale([grande, coluna], 275, 150) is coluna
    assert zn.zona_que_vale([grande, faixa], 150, 275) is faixa


def test_a_linha_fica_com_a_area_da_maioria_dos_glifos():
    pagina = zn.Zona(zn.TEXTO, 0, 0, 1000, 1000)
    legenda = zn.Zona(zn.TEXTO, 90, 90, 130, 130, funcao="legenda")
    tabuleiro = zn.Zona(zn.DIAGRAMA, 500, 500, 700, 700)
    linha = _boxes_de("abc", 100, 100) + [BoxEntry("a", 600, 600, 606, 610)]
    assert zn.zona_da_maioria([pagina, legenda, tabuleiro], linha) is legenda


def test_a_borda_pega_ate_a_tolerancia_inclusive_dos_dois_lados():
    z = zn.Zona(zn.TEXTO, 100, 100, 200, 200)
    pontos = {(96, 150): "e", (104, 150): "e", (204, 150): "d", (196, 150): "d",
              (150, 96): "c", (150, 104): "c", (150, 204): "b", (150, 196): "b"}
    assert {p: zn.bordas_em(z, *p, 4) for p in pontos} == pontos
    assert zn.bordas_em(z, 100, 300, 4) == ""          # na coluna da borda, mas longe embaixo


def test_esticar_para_na_pagina_e_no_lado_oposto_e_mover_tira_a_automatica():
    z = zn.Zona(zn.TEXTO, 100, 100, 200, 200, automatica=True)
    assert zn.arrastar(z, "", 10, 0, 1000, 1000).automatica is False
    casos = {("e", -500, 0): (0, 100, 200, 200), ("c", 0, -500): (100, 0, 200, 200),
             ("d", -500, 0): (100, 100, 108, 200), ("b", 0, 50): (100, 100, 200, 250),
             ("b", 0, -500): (100, 100, 200, 108), ("b", 0, 5000): (100, 100, 200, 1000)}
    assert {c: zn.arrastar(z, *c, 1000, 1000).caixa for c in casos} == casos


def test_marcar_de_novo_como_legenda_nao_desfaz_a_ligacao_ao_diagrama():
    zonas = [zn.Zona(zn.TEXTO, 0, 400, 200, 430, funcao="legenda", diagrama_id="d1")]
    zn.trocar_funcao(zonas, 0, "legenda")
    assert zonas[0].diagrama_id == "d1"


def test_a_margem_do_diagrama_e_a_folga_do_bloco_em_pixels():
    """A margem das coordenadas: 1,4 altura de letra (sem glifo nenhum, 20 px: 28); a folga
    do bloco: 0,4 altura e ao menos 2 px. A poeira pequena demais para área não para as
    outras."""
    [sem_texto] = zn.automaticas([], [(100, 100, 300, 300)], 1000, 1000)
    assert sem_texto.caixa == (72, 72, 328, 328)
    [diagrama] = zn.automaticas([], [(100, 100, 300, 300)], 1000, 1000, escala=10)
    assert diagrama.caixa == (86, 86, 314, 314)
    poeira = [BoxEntry(".", 500, 10, 502, 12)]
    zonas = zn.automaticas(poeira + _boxes_de("texto corrido", 100, 100), [], 1000, 1000,
                           escala=3)
    assert [z.caixa for z in zonas] == [(98, 98, 204, 112)]


def test_a_legenda_sem_diagrama_na_pagina_e_texto():
    zonas = zn.automaticas(_boxes_de("Diagrama 5. Jogam as pretas.", 20, 300), [], 2000, 1000,
                           escala=10)
    assert [z.funcao for z in zonas] == ["texto"]


def _diagrama_e_legenda(legenda, continuacao=""):
    """As funções das áreas de texto, de cima para baixo, com a legenda logo embaixo do
    diagrama e a continuação logo embaixo dela."""
    boxes = _boxes_de(legenda, 20, 410) + _boxes_de(continuacao, 20, 440)
    zonas = zn.automaticas(boxes, [(20, 100, 700, 400)], 2000, 1000, escala=10)
    return [z.funcao for z in sorted(zonas, key=lambda z: z.y1) if z.tipo == zn.TEXTO]


def test_a_legenda_tem_ate_80_letras_e_a_linha_que_a_continua_ate_50():
    assert _diagrama_e_legenda("Diagrama 5. " + "a" * 68) == ["legenda"]          # 80
    assert _diagrama_e_legenda("Diagrama 5. " + "a" * 69) == ["texto"]            # 81
    jogadores = "Memorial Ervin, " * 4
    assert _diagrama_e_legenda("Diagrama 5.", jogadores[:50]) == ["legenda", "legenda"]
    assert _diagrama_e_legenda("Diagrama 5.", jogadores[:51]) == ["legenda", "texto"]


def test_as_legendas_so_de_numero_lado_a_lado_sao_duas():
    """"12." e "13." sob dois tabuleiros lado a lado, três glifos de cada lado do vão."""
    tabuleiros = [(50, 50, 330, 330), (420, 50, 700, 330)]
    boxes = _boxes_de("12.", 60, 345) + _boxes_de("13.", 430, 345)
    zonas = zn.automaticas(boxes, tabuleiros, 760, 1000, escala=10)
    assert [z.funcao for z in zonas if z.tipo == zn.TEXTO] == ["legenda", "legenda"]


def test_o_ponto_pequeno_no_pe_da_linha_e_da_legenda():
    """"12." com o ponto do tamanho dele, na linha de base ou com o meio nela: uma área só,
    a legenda. Sob o tabuleiro da esquerda e sob o da direita."""
    for x in (60, 430):
        for y1, y2 in ((353, 355), (352, 358)):
            boxes = [BoxEntry("1", x, 345, x + 6, 355), BoxEntry("2", x + 8, 345, x + 14, 355),
                     BoxEntry(".", x + 16, y1, x + 18, y2)]
            zonas = zn.automaticas(boxes, [(x - 10, 50, x + 270, 330)], 760, 1000, escala=10)
            assert [(z.tipo, z.funcao) for z in zonas] == [(zn.DIAGRAMA, "diagrama"),
                                                           (zn.TEXTO, "legenda")], (x, y1)


def test_a_linha_que_abre_com_aspas_e_uma_area_so():
    """As aspas no alto, menores que as letras, começam a linha (o centro delas é o mais
    alto); o "D" entra porque cobre o meio dela."""
    boxes = [BoxEntry("“", 100, 96, 104, 101)] + _linha_mista("Diagrama 5.", 106, 100)
    zonas = zn.automaticas(boxes, [(100, 50, 400, 70)], 2000, 1000, escala=10)
    assert [(z.tipo, z.funcao) for z in zonas] == [(zn.DIAGRAMA, "diagrama"),
                                                   (zn.TEXTO, "legenda")]


def test_a_tolerancia_da_legenda_e_de_duas_letras_como_o_ocr_erra():
    """Dois sinais lidos antes ("-.Diagrama 5"), o "Di" lido "l" ("lagrama 5."), o "g" lido
    "9" sem o "r" ("Dia9ama 5.") ou lido "99" ("Dia99rama 5.") são legenda; a prosa que
    começa por "Diagonal" ou "Diagnóstico" (três letras de diferença) não é."""
    for texto in ("-.Diagrama 5", "lagrama 5.", "Dia9ama 5.", "Dia99rama 5."):
        assert _diagrama_e_legenda(texto) == ["legenda"], texto
    for texto in ("Diagonal longa das brancas", "Diagnóstico da posição"):
        assert _diagrama_e_legenda(texto) == ["texto"], texto


def test_a_poeira_tem_ate_dois_sinais_e_tres_ja_sao_texto():
    corpo = _boxes_de("texto normal bastante longo", 100, 250)
    for sinais, esperado in (("--", (zn.IGNORAR, "ignorar")), ("...", (zn.TEXTO, "texto"))):
        zonas = zn.automaticas(corpo + _boxes_de(sinais, 100, 600), [], 800, 1000, escala=10)
        assert [(z.tipo, z.funcao) for z in sorted(zonas, key=lambda z: z.y1)][-1] == esperado


def _numero(y1, y2, vao=2):
    """A função de "42" numa área de y1 a y2, com `vao` pixels entre os algarismos."""
    boxes = [BoxEntry("4", 50, y1 + 3, 56, y1 + 13),
             BoxEntry("2", 56 + vao, y1 + 3, 62 + vao, y1 + 13)]
    return _funcoes([_automatica(40, y1, 80, y2)], boxes, 800, 1000)[0]


def test_o_numero_de_pagina_fica_acima_de_15_ou_abaixo_de_85_por_cento_da_altura():
    assert _numero(149, 169) == "numero_de_pagina"
    assert _numero(150, 170) == "texto"
    assert _numero(830, 850) == "texto"
    assert _numero(831, 851) == "numero_de_pagina"
    # Os algarismos a 0,6 altura um do outro ainda são uma palavra só.
    assert _numero(831, 851, vao=6) == "numero_de_pagina"


def test_o_titulo_pelo_tamanho_comeca_em_1_3_vez_as_maiusculas_da_pagina():
    titulo = _boxes_de("CAPITULO", 100, 100, altura=26, passo=12)
    corpo = [b for y in range(200, 320, 30)
             for b in _boxes_de("texto corrido da pagina", 100, y, altura=20, passo=12)]
    zonas = zn.automaticas(titulo + corpo, [], 2000, 1000, escala=20)
    assert [z.funcao for z in sorted(zonas, key=lambda z: z.y1)] == ["titulo", "texto"]


def test_o_numero_grande_do_capitulo_e_titulo_mesmo_com_o_ponto_pequeno():
    """"3." à esquerda, o algarismo de 30 px e o ponto de 6: o tamanho é o do algarismo."""
    capitulo = [BoxEntry("3", 100, 100, 118, 130), BoxEntry(".", 120, 124, 126, 130)]
    corpo = [b for y in range(200, 320, 30)
             for b in _boxes_de("texto corrido da pagina", 100, y, altura=20, passo=12)]
    zonas = zn.automaticas(capitulo + corpo, [], 2000, 1000, escala=20)
    assert [z.funcao for z in sorted(zonas, key=lambda z: z.y1)] == ["titulo", "texto"]


def _centrado(texto, centro=1000, altura=18, vizinha_a=None):
    """A função de uma linha de `texto` numa área centrada em `centro` (a página tem 2000 de
    largura), com a `altura` dada e, se pedida, outra área de texto `vizinha_a` px embaixo."""
    largura = 8 * len(texto) + 6
    x1 = centro - largura // 2
    zonas = [_automatica(x1, 296, x1 + largura, 296 + altura)]
    if vizinha_a is not None:
        y = 296 + altura + vizinha_a
        zonas.append(zn.Zona(zn.TEXTO, 0, y, 2000, y + 100))
    return _funcoes(zonas, _boxes_de(texto, x1 + 4, 300))[0]


def test_o_titulo_centrado_tem_ate_80_letras_uma_linha_e_15_pixels_de_vao():
    comprido = "Um titulo comprido " * 5
    assert _centrado(comprido[:80]) == "titulo"
    assert _centrado(comprido[:81]) == "texto"
    assert _centrado("Um titulo", centro=1200) == "titulo"          # 10 % da largura
    assert _centrado("Um titulo", centro=1201) == "texto"
    assert _centrado("Um titulo", altura=22) == "titulo"            # 2,2 maiúsculas
    assert _centrado("Um titulo", altura=23) == "texto"
    assert _centrado("Um titulo", vizinha_a=15) == "titulo"         # 1,5 linha
    assert _centrado("Um titulo", vizinha_a=14) == "texto"


def _no_pe(y1, altura_da_letra):
    """A função de "nota curta" com a letra da altura dada, numa área que começa em y1 (a
    página tem 1000 de altura e o corpo, de letra 50, fica no alto)."""
    corpo = zn.Zona(zn.TEXTO, 50, 90, 1950, 170)               # a do usuário: fica como está
    nota = _automatica(90, y1, 400, y1 + altura_da_letra + 8)
    boxes = (_boxes_de("o corpo do texto da pagina segue", 100, 100, altura=50)
             + _boxes_de("nota curta", 100, y1 + 4, altura=altura_da_letra))
    return _funcoes([corpo, nota], boxes)[1]


def test_a_nota_comeca_a_70_por_cento_da_altura_com_a_letra_ate_0_82_do_corpo():
    assert _no_pe(700, 41) == "nota"
    assert _no_pe(699, 41) == "texto"
    assert _no_pe(400, 41) == "texto"
    assert _no_pe(750, 42) == "texto"
    assert _no_pe(750, 50) == "texto"                  # o corpo no pé da página não é nota


def test_o_f5_sem_leitura_nao_mexe_e_reclassifica_pela_altura_das_letras_lidas():
    diagrama = _automatica(20, 100, 700, 400, tipo=zn.DIAGRAMA)
    perto = _automatica(16, 406, 120, 424)
    longe = _automatica(16, 496, 120, 514)             # 96 px abaixo: mais de 4 letras
    lidos = _boxes_de("Diagrama 5.", 20, 410) + _boxes_de("Diagrama 6.", 20, 500)
    sem_leitura = [BoxEntry("", b.x1, b.y1, b.x2, b.y2) for b in lidos]
    zonas = [diagrama, perto, longe]
    assert zn.depois_de_ler(zonas, sem_leitura, [], [], 2000, 1000) == zonas
    assert [z.funcao for z in zn.depois_de_ler(zonas, lidos, [], [], 2000, 1000)] == [
        "diagrama", "legenda", "texto"]


def test_a_continuacao_da_continuacao_vale_tambem_fora_de_ordem():
    diagrama = _automatica(20, 100, 400, 400, tipo=zn.DIAGRAMA)
    legenda = _automatica(20, 406, 200, 424)
    jogadores = _automatica(20, 436, 200, 454)
    lugar = _automatica(20, 466, 250, 484)
    boxes = (_boxes_de("Diagrama 5.", 24, 410) + _boxes_de("Gormon-Silman", 24, 440)
             + _boxes_de("Memorial Ervin, 1987", 24, 470))
    assert _funcoes([lugar, jogadores, legenda, diagrama], boxes) == ["legenda"] * 3 + [
        "diagrama"]


def _continua(x1, y1, x2=400):
    """A função de "Gormon-Silman" numa área de x1 a x2 que começa em y1, sob a legenda que
    vai de (20, 406) a (200, 424). As letras ficam à direita da legenda."""
    diagrama = _automatica(20, 100, 400, 400, tipo=zn.DIAGRAMA)
    legenda = _automatica(20, 406, 200, 424)
    linha = _automatica(x1, y1, x2, y1 + 18)
    boxes = (_boxes_de("Diagrama 5.", 24, 410)
             + _boxes_de("Gormon-Silman", max(x1, 210) + 4, y1 + 4))
    return _funcoes([diagrama, legenda, linha], boxes)[2]


def test_a_continuacao_da_legenda_fica_embaixo_dela_e_sobrepoe_na_horizontal():
    assert _continua(150, 436) == "legenda"
    assert _continua(210, 436) == "texto"              # ao lado, sem sobrepor
    assert _continua(200, 436) == "texto"              # só encosta
    assert _continua(199, 436) == "legenda"            # um pixel em comum
    assert _continua(150, 414) == "legenda"            # sobe uma letra sobre a legenda
    assert _continua(150, 439) == "legenda"            # a 1,5 letra
    assert _continua(150, 440) == "texto"


def _ao_lado(x1, y1):
    """A função de "Diagrama 5." numa área de 120 × 18 com o canto em (x1, y1), perto do
    diagrama de (300, 100) a (600, 400)."""
    diagrama = _automatica(300, 100, 600, 400, tipo=zn.DIAGRAMA)
    legenda = _automatica(x1, y1, x1 + 120, y1 + 18)
    return _funcoes([diagrama, legenda], _boxes_de("Diagrama 5.", x1 + 4, y1 + 4))[1]


def test_a_legenda_encara_o_diagrama_por_um_lado_a_ate_4_letras():
    assert _ao_lado(630, 200) == "legenda"             # à direita, a 30
    assert _ao_lado(700, 200) == "texto"               # à direita, a 100
    assert _ao_lado(300, 440) == "legenda"             # embaixo, a 40
    assert _ao_lado(300, 441) == "texto"
    assert _ao_lado(630, 410) == "texto"               # na diagonal: não encara
    assert _ao_lado(600, 410) == "texto"               # encosta na coluna dele, sem entrar
    assert _ao_lado(599, 410) == "legenda"             # um pixel na coluna: embaixo, a 10
    assert _ao_lado(630, 400) == "texto"               # encosta na linha dele, sem entrar
    assert _ao_lado(630, 399) == "legenda"             # um pixel na linha: ao lado, a 30


def test_na_mesma_distancia_o_diagrama_de_cima_vence_o_do_lado():
    legenda = zn.Zona(zn.TEXTO, 100, 420, 300, 450, funcao="legenda", automatica=True)
    de_cima = DiagramaLido((299, 0, 580, 420), id="d1")       # um pixel sobre a legenda
    do_lado = DiagramaLido((0, 300, 100, 600), id="d0")       # encostado à esquerda
    assert zn.vincular_legendas([legenda], [do_lado, de_cima])[0].diagrama_id == "d1"
    a_um_pixel = DiagramaLido((299, 0, 580, 419), id="d1")
    assert zn.vincular_legendas([legenda], [do_lado, a_um_pixel])[0].diagrama_id == "d0"
    sem_id = DiagramaLido((100, 100, 300, 410))
    assert zn.vincular_legendas([legenda], [sem_id, do_lado])[0].diagrama_id == "d0"


def test_a_funcao_da_margem_vale_com_todos_os_glifos_iguais_e_nao_tira_a_nota():
    boxes = (_boxes_de("7", 100, 20) + _boxes_de("CABECALHO", 300, 20)
             + _boxes_de("nota", 100, 900))
    numero = _automatica(90, 10, 120, 45)
    cabecalho = _automatica(290, 10, 390, 45)
    nota = _automatica(90, 890, 150, 925, funcao="nota")
    aprendidas = {0: "numero_de_pagina", **{i: "cabecalho" for i in range(1, 5)},
                  **{i: "rodape" for i in range(10, 14)}}
    zonas = [numero, cabecalho, nota]
    assert [z.funcao for z in zn.aplicar_funcoes_de_margem(zonas, boxes, aprendidas)] == [
        "numero_de_pagina", "texto", "nota"]
    aprendidas.update({i: "cabecalho" for i in range(5, 10)})
    assert zn.aplicar_funcoes_de_margem(zonas, boxes, aprendidas)[1].funcao == "cabecalho"


def test_cada_area_de_diagrama_da_o_tabuleiro_de_dentro_ou_a_si_mesma():
    """A área de diagrama sem tabuleiro achado é o tabuleiro, se o diagrama vence no centro
    dela (as de ignorar cobrem as bordas); com um achado (o centro dele nela, onde o diagrama
    vence), é ele, e não serve à outra área."""
    sem_achado = zn.Zona(zn.DIAGRAMA, 300, 300, 600, 600)
    com_achado = zn.Zona(zn.DIAGRAMA, 1000, 400, 1400, 800)
    ignorar = [zn.Zona(zn.IGNORAR, 0, 0, 350, 1000), zn.Zona(zn.IGNORAR, 0, 0, 1000, 350)]
    achado = (1020, 410, 1380, 770)
    _, tabuleiros = zn.filtrar([], [achado], [sem_achado, com_achado] + ignorar)
    assert tabuleiros == [sem_achado.caixa, achado]


def test_o_paragrafo_junta_linhas_a_ate_1_2_letra_e_o_recuo_de_1_2_abre_outro():
    """A primeira linha recuada, a segunda mais longa, a terceira 10 px à direita: um bloco,
    com a caixa de todas; a quarta, recuada 12 px, abre outro. Cada vão é de 12 px. No alto
    à direita e no pé à esquerda da página."""
    for dx, dy in ((0, 0), (-280, 700)):
        boxes = (_linha_mista("a Torre ataca", 320 + dx, 100 + dy)
                 + _linha_mista("o Bispo defende a casa", 300 + dx, 126 + dy)
                 + _linha_mista("e o Rei", 310 + dx, 152 + dy)
                 + _linha_mista("Novo paragrafo", 312 + dx, 178 + dy))
        zonas = zn.automaticas(boxes, [], 2000, 1000, escala=10)
        assert [z.caixa for z in zonas] == [(296 + dx, 92 + dy, 478 + dx, 166 + dy),
                                            (308 + dx, 170 + dy, 426 + dx, 192 + dy)]


def test_as_linhas_que_so_se_encostam_na_horizontal_sao_dois_blocos():
    de_cima = _boxes_de("abcdefghij", 300, 100)
    assert len(zn.automaticas(de_cima + _boxes_de("klmno", 262, 115), [], 2000, 1000,
                              escala=10)) == 2
    assert len(zn.automaticas(de_cima + _boxes_de("klmno", 263, 115), [], 2000, 1000,
                              escala=10)) == 1
