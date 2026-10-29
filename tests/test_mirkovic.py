"""O que o *Chess School 1* do Mirkovic (PDF ClearScan, 2013) mostrou que faltava.

As medidas são das pp. 10, 18, 19, 89 e 160 do livro, lidas no projeto do usuário: os lances
colados pelo negrito apertado, a numeração dos diagramas em duas colunas, a linha que
atravessa a calha, o fio embaixo do cabeçalho corrido e o idioma do projeto.
"""

from __future__ import annotations

from core.box_model import BoxEntry

from abbychess import texto as tx
from abbychess.diagramas import DiagramaLido


def _palavras(texto: str) -> list:
    chars = {i: c for i, c in enumerate(texto)}
    linhas = tx.partir_lances_colados([[list(range(len(texto)))]], chars)
    return ["".join(chars[g] for g in p) for p in linhas[0]]


def test_lances_colados_partem_depois_da_casa():
    assert _palavras("♘f62.c4") == ["♘f6", "2.c4"]
    assert _palavras("♗b44.e30—0") == ["♗b4", "4.e3", "0—0"]
    assert _palavras("3.♔c5♔a44.♔c4♔a35.♔c3") == ["3.♔c5", "♔a4", "4.♔c4", "♔a3", "5.♔c3"]
    assert _palavras("g1♕6.f7") == ["g1♕", "6.f7"]


def test_o_que_nao_e_lance_colado_fica():
    for palavra in ("1.e4e5", "a1-h8", "1997.", "E48-1.d4", "♔c6andnow", "Fig.12", "h2-h4"):
        assert _palavras(palavra) == [palavra]


def _boxes_da_linha(texto: str, x: int, y: int) -> list:
    boxes = []
    for c in texto:
        if c != " ":
            boxes.append(BoxEntry(c, x, y, x + 10, y + 20, 0.99, "neural"))
        x += 11
    return boxes


def test_os_lances_partidos_chegam_ao_documento_e_a_juncao_os_junta():
    pagina = tx.pagina_avulsa(_boxes_da_linha("E48-1.d4 ♘f62.c4 e6", 40, 100))
    assert tx.texto(tx.montar(pagina)) == "E48-1.d4 ♘f6 2.c4 e6"
    gids = [b.gid for b in pagina.boxes]
    pagina.decisoes = type(pagina.decisoes)(juncoes=frozenset({(gids[10], gids[11])}))
    assert tx.texto(tx.montar(pagina)) == "E48-1.d4 ♘f62.c4 e6"


def _diagrama(did: str, caixa) -> DiagramaLido:
    return DiagramaLido(caixa=caixa, id=did)


def test_os_diagramas_sao_numerados_na_ordem_do_documento():
    """p. 18: Moravec e Pogosianc 1976 na coluna da esquerda, Reti e Pogosianc 1984 na da
    direita; pela altura, o Reti (mais alto que o Pogosianc de 1976) era o 2."""
    diagramas = [_diagrama("d0", (1050, 369, 1576, 899)), _diagrama("d1", (248, 375, 764, 902)),
                 _diagrama("d2", (252, 1543, 769, 2070)), _diagrama("d3", (1056, 1596, 1581, 2126))]
    documento = tx.Documento(tuple(tx.Bloco(f"b{k}", None, "diagrama", diagrama_id=did)
                                   for k, did in enumerate(["d1", "d2", "d0"])), {}, {})
    assert tx.numeros_dos_diagramas(documento, diagramas) == {"d1": 1, "d2": 2, "d0": 3, "d3": 4}


def _linha_larga(texto: str, x: int, y: int) -> list:
    """Uma linha com a geometria da p. 160 do Mirkovic: glifos de 20 px, 1 px entre eles."""
    boxes = []
    for c in texto:
        if c != " ":
            boxes.append(BoxEntry(c, x, y, x + 20, y + 32, 0.99, "neural"))
        x += 21
    return boxes


def test_a_linha_que_atravessa_a_calha_e_lida_inteira():
    """p. 160: o parágrafo de largura total no alto tem um box só, ou nenhum, no meio da calha
    de 48 px; não era faixa, e cada linha virava metade de uma coluna e metade da outra."""
    boxes = _linha_larga("Among the oldest combin where bishop is", 100, 40)
    palavras = ["ab", "cdef", "ghi", "jklmno", "pq", "rstu", "vwxyz", "abc"]
    for k in range(20):
        # Os vãos entre palavras mudam de linha para linha, como na prosa justificada.
        resto = " ".join(palavras[(k + j) % 8] for j in range(4))[:16]
        boxes += _linha_larga(f"e{k:02d} {resto}", 100, 120 + 45 * k)
        boxes += _linha_larga(f"d{k:02d} {resto}", 568, 120 + 45 * k)
    texto = tx.texto(tx.montar(tx.pagina_avulsa(boxes))).splitlines()
    assert texto[0] == "Among the oldest combin where bishop is"
    assert texto[1].startswith("e00 ") and texto[21].startswith("d00 ")


def test_o_cabecalho_isolado_mede_o_espaco_pela_pagina():
    """p. 10: "GM NIKOLA SEDLAK" sozinho num trecho, de letras largas: o espaço do core pela
    largura mediana do trecho sumia ("GMNIKOLASEDLAK")."""
    from abbychess.layout import partir_pela_pagina
    from core.notacao import palavras_da_pagina

    cabecalho, x = [], 600
    for palavra in ("GM", "NIKOLA", "SEDLAK"):
        for c in palavra:
            cabecalho.append(BoxEntry(c, x, 10, x + 30, 40, 0.99, "neural"))
            x += 32
        x += 12
    pagina = cabecalho + [b for k in range(8) for b in _boxes_da_linha(
        f"e{k} abcde fghij klmno pqrst", 100, 120 + 40 * k)]
    linhas = partir_pela_pagina(palavras_da_pagina(cabecalho), cabecalho, pagina)
    assert ["".join(cabecalho[s.indice].char for s in p.simbolos) for p in linhas[0]] == [
        "GM", "NIKOLA", "SEDLAK"]


def test_o_idioma_pelas_palavras_comuns():
    from abbychess import idioma

    ingles = ("Opposition is when distance between the kings is odd number of squares. "
              "Opposition has big practical importance in pawn's endings, and basically "
              "represent maneuver fight, with cause of gaining the material advantage or "
              "engaging the better position for king. The side which steps in the opposition "
              "has the advantage in most of the cases, and we say that side is in opposition.")
    portugues = ("As brancas jogam e ganham. O rei das pretas não pode voltar, e o peão "
                 "passa. Com o lance do texto, a posição é de vitória, mas só se o rei for "
                 "pelo caminho mais curto; senão as pretas empatam. É uma regra que vale "
                 "também nos finais com mais peões, e o livro a mostra nos diagramas seguintes "
                 "com o rei na frente do peão, pela casa da coroação, e com a oposição.")
    espanhol = ("Las blancas juegan y ganan. El rey de las negras no puede volver, y el peón "
                "pasa. Con la jugada del texto la posición es ganadora, pero solo si el rey va "
                "por el camino más corto; si no, las negras hacen tablas. Es una regla que "
                "vale también en los finales con más peones, y el libro lo muestra en los "
                "diagramas siguientes con el rey delante del peón.")
    assert (idioma.provavel(ingles), idioma.provavel(portugues),
            idioma.provavel(espanhol)) == ("en", "pt", "es")
    assert idioma.provavel("1.e4 e5 2.♘f3 ♘c6 3.♗b5 a6") is None       # só lances


def test_o_fio_do_cabecalho_sai_e_a_moldura_do_tabuleiro_fica():
    """pp. 18 e 89: o fio embaixo do cabeçalho corrido levava as letras dele na segmentação."""
    import numpy as np
    from PIL import Image

    from abbychess.pagina import apagar_fios

    matriz = np.full((2666, 1820), 255, np.uint8)
    matriz[170:179, 130:1690] = 0                      # o fio, 9 px
    matriz[130:162, 140:160] = 0                       # uma letra do cabeçalho
    matriz[400:406, 200:720] = 0                       # a moldura de um tabuleiro
    matriz[914:920, 200:720] = 0
    matriz[400:920, 200:206] = 0
    matriz[400:920, 714:720] = 0
    matriz[1200:1230, 200:1600:40] = 0                 # um sublinhado de traços não é fio
    limpa = np.asarray(apagar_fios(Image.fromarray(matriz)))
    assert (limpa[170:179, 130:1690] == 255).all()
    assert (limpa[130:162, 140:160] == 0).all()
    assert (limpa[400:406, 200:720] == 0).all() and (limpa[914:920, 200:720] == 0).all()
    assert (limpa[1200:1230, 200:1600:40] == 0).all()
