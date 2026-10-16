"""Caracterização: o comportamento de hoje, fixado antes dos passos 1 e 2 do roadmap.

Estes testes não dizem o que é certo; dizem o que o programa faz em 2026-10-15. Os
passos 1a, 1b e 2a trocam a persistência, o modelo (gid, documento) e o controlador
sem querer mudar o comportamento, e uma diferença aqui tem de ser **justificada** no
registro do passo (`docs/revisoes/passo-N.md`), nunca aceita em silêncio.

Os golden ficam em `tests/golden/caracterizacao/`. Para regravá-los depois de uma
mudança decidida: `pytest tests/test_caracterizacao.py --atualizar-golden`.

Rodam sem a rede global (`ocr=None`), como os outros testes do núcleo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.box_model import BoxEntry

from abbychess import diagramas as dg
from abbychess import exportar as ex
from abbychess import pagina as pg
from abbychess.leitor import FONTE_MANUAL, LeitorDoLivro
from abbychess.projeto import ProjetoDeLivro

from tests.test_treino_por_livro import _pagina_sintetica

GOLDEN = Path(__file__).with_name("golden") / "caracterizacao"


def _conferir(request, nome: str, valor) -> None:
    """Compara `valor` (texto ou JSON) com o golden; com --atualizar-golden, regrava."""
    caminho = GOLDEN / nome
    texto = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False, indent=1)
    if request.config.getoption("--atualizar-golden"):
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(texto + "\n", encoding="utf-8", newline="\n")
        return
    assert caminho.is_file(), f"golden ausente: rode com --atualizar-golden ({caminho.name})"
    assert texto + "\n" == caminho.read_text(encoding="utf-8"), f"mudou: {caminho.name}"


def _estado(boxes):
    # 2 casas: a confiança da rede varia na 3ª entre versões de OpenCV e NumPy.
    return [[b.char, b.x1, b.y1, b.x2, b.y2, b.source, round(b.confidence, 2)] for b in boxes]


@pytest.fixture
def projeto(tmp_path):
    fonte = _pagina_sintetica(tmp_path / "pagina.png", ("abc abc abc", "cab bca", "bac cba abc"))
    return ProjetoDeLivro.criar(tmp_path / "livros", "Caracterizacao", fonte)


@pytest.fixture
def leitor(projeto):
    return LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)


# ----------------------------------------------------------------------
# As operações do núcleo, em sequência fixa
# ----------------------------------------------------------------------

def test_roteiro_das_operacoes(request, projeto, leitor):
    """Segmentar, ler, ensinar, propagar, dividir, juntar, ajustar, marcar e descartar."""
    imagem = pg.fonte_do_projeto(projeto).pagina(0)
    boxes = pg.segmentar(imagem)
    passos = {"segmentar": _estado(boxes)}

    pg.ler_boxes(imagem, boxes, leitor)
    passos["ler"] = _estado(boxes)

    resolvidos = pg.ensinar(imagem, boxes, 0, "a", leitor, projeto, pagina=0)
    passos["ensinar_a"] = {"resolvidos": resolvidos, "boxes": _estado(boxes)}

    resolvidos = pg.ensinar_varios(imagem, boxes, [1, 4], "b", leitor, projeto, pagina=0)
    passos["ensinar_varios_b"] = {"resolvidos": resolvidos, "boxes": _estado(boxes)}

    pg.confirmar(boxes, 2, "c")
    passos["confirmar_c"] = _estado(boxes)

    pg.juntar(imagem, boxes, 0, 1, leitor)
    passos["juntar_0_1"] = _estado(boxes)

    pg.dividir(imagem, boxes, 0, leitor)
    passos["dividir_0"] = _estado(boxes)

    pg.ajustar(imagem, boxes, 3, leitor, esquerda=-2, direita=2)
    passos["ajustar_3"] = _estado(boxes)

    a = boxes[5]
    indice = pg.criar_box(imagem, boxes, (a.x1 - 3, a.y1 - 3, a.x2 + 3, a.y2 + 3), leitor)
    passos["criar_box"] = {"indice": indice, "boxes": _estado(boxes)}

    pg.descartar(boxes, len(boxes) - 1)
    passos["descartar_ultimo"] = _estado(boxes)

    passos["fila"] = pg.fila_de_revisao(boxes, leitor)
    passos["texto"] = pg.texto(boxes)
    _conferir(request, "roteiro.json", passos)


def test_manter_marcados(request):
    segmentados = [BoxEntry("", 0, 0, 10, 10), BoxEntry("", 20, 0, 30, 10),
                   BoxEntry("", 40, 0, 50, 10)]
    marcados = [BoxEntry("r", -1, -1, 11, 11, 1.0, FONTE_MANUAL),
                BoxEntry("p", 18, 0, 34, 10, 1.0, FONTE_MANUAL)]
    _conferir(request, "manter_marcados.json", _estado(pg.manter_marcados(segmentados, marcados)))


# ----------------------------------------------------------------------
# As três montagens do texto de hoje (que o passo 1b troca por uma só)
# ----------------------------------------------------------------------

def _linha(texto: str, y: int, x: int = 40, altura: int = 40):
    return [BoxEntry(c, x + 28 * i, y, x + 28 * i + 24, y + altura, 1.0, FONTE_MANUAL)
            for i, c in enumerate(texto) if c != " "]


def _pagina_mista():
    """Prosa com hífen de fim de linha, um lance com figurina e um parágrafo novo."""
    return (_linha("As brancas jogam 1.♘f3 e o pre-", 100)
            + _linha("to responde com 1...e5 logo.", 150)
            + _linha("Novo paragrafo depois do vao.", 320))


def test_tres_montagens_do_texto(request):
    boxes = _pagina_mista()
    diagrama = dg.DiagramaLido((40, 200, 300, 300))
    montagens = {
        "pagina.texto": pg.texto(boxes),
        "diagramas.texto_da_pagina": dg.texto_da_pagina(boxes, [diagrama]),
        "exportar.paragrafos": [p.texto for p in ex.paragrafos(boxes)],
        "exportar.paragrafos_com_corte": [p.texto for p in ex.paragrafos(boxes, [200])],
    }
    _conferir(request, "tres_montagens.json", montagens)


def test_margens_corridas(request):
    cabecalho = _linha("22 YASSER SEIRAWAN", 40)
    corpo = [b for k, frase in enumerate(("as brancas jogam e ganham", "um lance muito ruim",
                                          "o plano consiste em atacar", "e a Dama sob ataque"))
             for b in _linha(frase, 200 + 50 * k)]
    boxes = cabecalho + corpo
    tirar = ex.margens_corridas({21: (boxes, 1000)})[21]
    _conferir(request, "margens.json", sorted(tirar))
