"""Endireitar a página torta antes de ler.

Na p. 26 do Xadrez Vitorioso, com 0,6° de inclinação, a vírgula e o ponto do
fim de cada linha (que ficam baixos) caíam na linha de baixo: o texto saía
"uma Dama" / ", mas agora". A página endireitada lê a linha inteira.
"""

from __future__ import annotations

import json

import fitz
import numpy as np
import pytest
from PIL import Image

from abbychess import exportar as ex
from abbychess import livro
from abbychess import pagina as pg
from abbychess.leitor import LeitorDoLivro
from abbychess.projeto import ARQUIVO_DO_PROJETO, ProjetoDeLivro

from tests.test_treino_por_livro import _pagina_sintetica

LINHAS = ("abc abc abc abc abc", "cab bca cab bca", "abc cab bca abc")


def _torta(caminho, angulo):
    """A página sintética girada `angulo` graus, como saiu do scanner."""
    reta = _pagina_sintetica(caminho, LINHAS)
    cinza = np.asarray(Image.open(reta).convert("L"))
    Image.fromarray(pg.girar(cinza, angulo)).save(caminho)
    return caminho


def test_mede_a_inclinacao_de_uma_pagina_girada(tmp_path):
    cinza = np.asarray(Image.open(_torta(tmp_path / "p.png", -1.2)).convert("L"))
    assert pg.medir_inclinacao(cinza) == pytest.approx(1.2, abs=0.1)


def test_pagina_reta_nao_gira(tmp_path):
    cinza = np.asarray(Image.open(_pagina_sintetica(tmp_path / "p.png", LINHAS)).convert("L"))
    assert abs(pg.medir_inclinacao(cinza)) < pg.INCLINACAO_MINIMA


def test_a_medida_fica_gravada_no_projeto(tmp_path, monkeypatch):
    caminho = _torta(tmp_path / "p.png", -1.0)
    fonte = pg.FonteDePaginas(caminho, endireitar=True, pasta=tmp_path)
    angulo = fonte.inclinacao(0)
    gravado = json.loads((tmp_path / pg.ARQUIVO_DE_INCLINACOES).read_text(encoding="utf-8"))
    assert gravado == {"0": angulo}

    def medir_de_novo(*_a, **_k):
        raise AssertionError("a inclinação gravada foi medida de novo")

    monkeypatch.setattr(pg, "medir_inclinacao", medir_de_novo)
    outra = pg.FonteDePaginas(caminho, endireitar=True, pasta=tmp_path)
    assert outra.inclinacao(0) == angulo
    assert outra.pagina(0).size == outra.original(0).size


def test_ponto_volta_ao_lugar_da_pagina_original():
    original = np.full((400, 600), 255, np.uint8)
    original[100:104, 450:454] = 0                    # um ponto de tinta
    girada = pg.girar(original, 2.0)
    ys, xs = np.nonzero(girada < 128)
    x, y = pg.ponto_original(xs.mean(), ys.mean(), 2.0, 600, 400)
    assert (x, y) == (pytest.approx(451.5, abs=1), pytest.approx(101.5, abs=1))


def test_projeto_novo_endireita_e_o_antigo_nao(tmp_path):
    fonte = _pagina_sintetica(tmp_path / "p.png")
    novo = ProjetoDeLivro.criar(tmp_path / "livros", "Novo", fonte)
    assert novo.dados.endireitar

    antigo = ProjetoDeLivro.criar(tmp_path / "livros", "Antigo", fonte)
    arquivo = antigo.pasta / ARQUIVO_DO_PROJETO
    bruto = json.loads(arquivo.read_text(encoding="utf-8"))
    del bruto["endireitar"]                           # como gravava a versão anterior
    arquivo.write_text(json.dumps(bruto), encoding="utf-8")
    assert not ProjetoDeLivro.abrir(antigo.pasta).dados.endireitar
    assert not pg.fonte_do_projeto(ProjetoDeLivro.abrir(antigo.pasta)).endireitar


def test_pagina_torta_le_as_linhas_inteiras(tmp_path):
    """Ensinadas as três letras, cada linha da página torta sai inteira e na ordem."""
    caminho = _torta(tmp_path / "p.png", -1.5)
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Torto", caminho)
    leitor = LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)
    fonte = pg.fonte_do_projeto(projeto)
    imagem = fonte.pagina(0)
    boxes = pg.segmentar(imagem)
    for indice, char in enumerate("abc"):
        pg.ensinar(imagem, boxes, indice, char, leitor, projeto, pagina=0, propagar=False)
    pg.ler_boxes(imagem, boxes, leitor)
    assert pg.texto(boxes).splitlines() == list(LINHAS)


def _pdf_de(imagem_png, destino):
    with Image.open(imagem_png) as imagem:
        largura, altura = imagem.size
    doc = fitz.open()
    page = doc.new_page(width=largura * 72 / 300, height=altura * 72 / 300)
    page.insert_image(page.rect, filename=str(imagem_png))
    doc.save(destino)
    doc.close()
    return destino


def test_camada_do_pdf_fica_sobre_a_palavra_da_pagina_torta(tmp_path):
    angulo = -2.0
    png = _torta(tmp_path / "p.png", angulo)
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "PDF torto", _pdf_de(png, tmp_path / "l.pdf"))
    leitor = LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)
    fonte = pg.fonte_do_projeto(projeto)
    imagem = fonte.pagina(0)
    boxes = pg.segmentar(imagem)
    for indice, char in enumerate("abc"):
        pg.ensinar(imagem, boxes, indice, char, leitor, projeto, pagina=0, propagar=False)
    livro.reconhecer_paginas(projeto, fonte, leitor, [0])
    destino = tmp_path / "pesquisavel.pdf"
    ex.exportar(projeto, destino)

    # A primeira e a última palavra da primeira linha: onde a tinta delas está no
    # original torto tem de cair dentro do retângulo da palavra na camada.
    reta = np.asarray(fonte.pagina(0).convert("L"))
    lidos = [b for b in projeto.carregar_pagina(0) if b.char]
    linha = [b for b in lidos if b.y1 < lidos[0].y2]
    with fitz.open(destino) as doc:
        palavras = [[v * 300 / 72 for v in p[:4]] for p in doc[0].get_text("words")
                    if p[4] == "abc"]
    for glifo in (min(linha, key=lambda b: b.x1), max(linha, key=lambda b: b.x2)):
        x, y = pg.ponto_original((glifo.x1 + glifo.x2) / 2, (glifo.y1 + glifo.y2) / 2,
                                 fonte.inclinacao(0), reta.shape[1], reta.shape[0])
        assert any(x1 <= x <= x2 and y1 <= y <= y2 for x1, y1, x2, y2 in palavras)


def test_box_endireitado_volta_para_cima_da_tinta_original():
    original = np.full((400, 600), 255, np.uint8)
    original[100:110, 500:510] = 0                    # um glifo perto do canto
    girada = pg.girar(original, 2.0)
    ys, xs = np.nonzero(girada < 128)
    box = pg.BoxEntry("x", int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    movido = ex._na_original(box, 2.0, 600, 400)
    assert abs(movido.x1 - 500) <= 1 and abs(movido.y1 - 100) <= 1
    assert movido.x2 - movido.x1 == box.x2 - box.x1   # translada, sem deformar
    assert ex._na_original((box.x1, box.y1, box.x2, box.y2), 2.0, 600, 400) == (
        movido.x1, movido.y1, movido.x2, movido.y2)
