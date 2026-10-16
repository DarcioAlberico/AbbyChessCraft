"""O cabeçalho e o rodapé corridos fora da exportação, e a página só com quadros marcados.

As linhas sintéticas imitam a p. 22 do Xadrez Vitorioso: o cabeçalho a 5% da
altura com o número da página, um vão de dois a três passos, e o texto.
"""

from __future__ import annotations

import os

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QMessageBox  # noqa: E402

from core.box_model import BoxEntry  # noqa: E402

from abbychess import exportar as ex  # noqa: E402
from abbychess import livro  # noqa: E402
from abbychess import pagina as pg  # noqa: E402
from abbychess.leitor import FONTE_MANUAL, LeitorDoLivro  # noqa: E402
from abbychess.projeto import ProjetoDeLivro  # noqa: E402

from tests import test_janela  # noqa: E402
from tests.test_janela import _esperar  # noqa: E402
from tests.test_treino_por_livro import _pagina_sintetica  # noqa: E402
from tests.janela_util import atual, boxes, fila, mostrar, pulados, selecao  # noqa: E402,F401

app = test_janela.app
janela = test_janela.janela

ALTURA = 3500


def _linha(texto: str, y: int, x: int = 300, altura: int = 50):
    return [BoxEntry(c, x + 30 * i, y, x + 30 * i + 25, y + altura, 1.0, FONTE_MANUAL)
            for i, c in enumerate(texto) if c != " "]


#: Linhas de tamanhos diferentes: com o mesmo texto em todas, os espaços se
#: alinhariam e o core leria a página como várias colunas.
FRASES = ("as brancas jogam e ganham", "um lance muito ruim", "o plano consiste em atacar",
          "e a Dama sob ataque", "trocar peças num momento bom", "evitar golpes baratos")


def _corpo(y: int = 360, linhas: int = 6):
    return [b for k in range(linhas) for b in _linha(FRASES[k % len(FRASES)], y + 60 * k)]


def _tirados(boxes, tirar):
    return "".join(boxes[k].char for k in sorted(tirar))


# ----------------------------------------------------------------------
# Cabeçalho e rodapé
# ----------------------------------------------------------------------

def test_cabecalho_com_numero_sai_e_o_texto_fica():
    boxes = _linha("22 YASSER SEIRAWAN", 190) + _corpo()
    tirar = ex.margens_corridas({21: (boxes, ALTURA)})[21]
    assert _tirados(boxes, tirar) == "22YASSERSEIRAWAN"


def test_rodape_com_numero_sai():
    boxes = _corpo(2900) + _linha("- 22 -", 3350)
    tirar = ex.margens_corridas({21: (boxes, ALTURA)})[21]
    assert _tirados(boxes, tirar) == "-22-"


def test_titulo_que_se_repete_sai_mesmo_sem_numero():
    paginas = {i: (_linha("XADREZ VITORIOSO", 180) + _corpo(), ALTURA) for i in (20, 22)}
    tirar = ex.margens_corridas(paginas)
    assert all(_tirados(paginas[i][0], tirar[i]) == "XADREZVITORIOSO" for i in (20, 22))


def test_titulo_de_capitulo_sem_numero_nem_repeticao_fica():
    paginas = {20: (_linha("CAPITULO UM", 180) + _corpo(), ALTURA),
               21: (_linha("OUTRA COISA BEM DIFERENTE", 180) + _corpo(), ALTURA)}
    tirar = ex.margens_corridas(paginas)
    assert tirar == {20: set(), 21: set()}


def test_primeira_linha_colada_no_texto_fica():
    """Sem o vão maior que o das linhas, a primeira linha é texto, mesmo com número."""
    boxes = _linha("12 lances depois", 300) + _corpo(360)
    assert ex.margens_corridas({0: (boxes, ALTURA)}) == {0: set()}


def test_poeira_da_borda_sai():
    boxes = _linha("l", 1, x=2000, altura=33) + _corpo() + _linha(".", 3480, x=2000, altura=3)
    tirar = ex.margens_corridas({0: (boxes, ALTURA)})[0]
    assert _tirados(boxes, tirar) == "l."


def test_exportacao_tira_o_cabecalho(tmp_path):
    imagem = tmp_path / "pagina.png"
    Image.new("L", (2480, ALTURA), 255).save(imagem)
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Margens", imagem)
    projeto.salvar_pagina(0, _linha("22 YASSER SEIRAWAN", 190) + _corpo())
    [pagina] = ex.paginas_do_projeto(projeto, None)
    textos = [b.texto for b in pagina.blocos]
    assert textos and not any("YASSER" in t for t in textos)
    assert textos[0].startswith("as brancas jogam")


# ----------------------------------------------------------------------
# A página só com quadros marcados
# ----------------------------------------------------------------------

def test_pagina_so_marcada_nao_conta_como_lida(tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Marcas",
                                   _pagina_sintetica(tmp_path / "p.png"))
    projeto.salvar_pagina(0, [BoxEntry("a", 1, 1, 5, 5)], reconhecida=False)
    assert projeto.paginas_lidas() == [] and not projeto.pagina_reconhecida(0)
    assert projeto.carregar_pagina(0)[0].char == "a"
    projeto.salvar_pagina(0, [BoxEntry("a", 1, 1, 5, 5)])
    assert projeto.paginas_lidas() == [0] and projeto.pagina_reconhecida(0)


def test_manter_marcados_tira_o_box_de_baixo():
    segmentados = [BoxEntry("", 0, 0, 10, 10), BoxEntry("", 20, 0, 30, 10)]
    marcado = BoxEntry("r", -1, -1, 11, 11, 1.0, FONTE_MANUAL)
    saida = pg.manter_marcados(segmentados, [marcado])
    assert saida == [marcado, segmentados[1]]


def test_lote_mantem_o_glifo_marcado(tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Marcas",
                                   _pagina_sintetica(tmp_path / "p.png"))
    leitor = LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)
    fonte = pg.fonte_do_projeto(projeto)
    a = pg.segmentar(fonte.pagina(0))[0]
    marcado = BoxEntry("α", a.x1, a.y1, a.x2, a.y2, 1.0, FONTE_MANUAL)
    projeto.salvar_pagina(0, [marcado], reconhecida=False)

    resultado = livro.reconhecer_paginas(projeto, fonte, leitor, [0])

    assert resultado.lidas == [0] and projeto.pagina_reconhecida(0)
    boxes = projeto.carregar_pagina(0)
    assert boxes[0].char == "α" and len(boxes) == len(pg.segmentar(fonte.pagina(0)))


def test_f5_numa_pagina_marcada_nao_pergunta_e_mantem_os_quadros(app, janela, monkeypatch):
    a = pg.segmentar(janela.pagina.imagem)[0]
    janela.pagina.marcar(a.x1 - 3, a.y1 - 3, a.x2 + 3, a.y2 + 3)
    janela.treino.campo.setText("a")
    janela.treino._so_corrigir()
    assert not janela.projeto.pagina_reconhecida(0) and janela.projeto.carregar_pagina(0)

    def nao_pergunte(*_a, **_k):
        raise AssertionError("o F5 perguntou numa página só com quadros marcados")

    monkeypatch.setattr(QMessageBox, "question", nao_pergunte)
    janela.reconhecer()
    _esperar(app, janela)

    assert janela.pagina.reconhecida and janela.projeto.pagina_reconhecida(0)
    assert (boxes(janela)[0].char, boxes(janela)[0].source) == ("a", FONTE_MANUAL)
    assert sum(b.x1 == a.x1 and b.y1 == a.y1 for b in boxes(janela)) == 1


@pytest.mark.parametrize("reconhecida", [True, False])
def test_desfazer_o_f5_devolve_a_marca_da_pagina(app, janela, reconhecida):
    if reconhecida:
        janela.reconhecer()
        _esperar(app, janela)
    a = pg.segmentar(janela.pagina.imagem)[0]
    janela.pagina.marcar(a.x1 - 3, a.y1 - 3, a.x2 + 3, a.y2 + 3)
    janela.reconhecer()
    _esperar(app, janela)
    janela.pagina.desfazer()
    assert janela.pagina.reconhecida == reconhecida
    assert janela.projeto.pagina_reconhecida(0) == reconhecida
