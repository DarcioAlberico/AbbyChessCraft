"""O livro inteiro: lote, fila de revisão entre páginas e exportação.

Como em `test_treino_por_livro`, o leitor roda sem a rede global (`ocr=None`):
o que ninguém leu fica vazio e vai para a revisão, e o que o livro ensinou sai
do padrão. O PDF é montado com páginas sintéticas a 300 dpi, a resolução em
que o projeto lê.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import fitz
import pytest
from PIL import Image

from abbychess import exportar as ex
from abbychess import livro
from abbychess import pagina as pg
from abbychess.leitor import FONTE_MANUAL, LeitorDoLivro
from abbychess.projeto import ProjetoDeLivro

from tests.test_treino_por_livro import _pagina_sintetica

PAGINAS = (("abc abc abc", "cab bca"), ("bca cab", "abc"), ("cba cba", "bac abc"))


def pdf_sintetico(pasta: Path, paginas=PAGINAS, *, camada_antiga: bool = False) -> Path:
    """Um PDF de imagens, uma página por grupo de linhas, como um livro digitalizado."""
    doc = fitz.open()
    for i, linhas in enumerate(paginas):
        caminho = _pagina_sintetica(pasta / f"p{i}.png", linhas)
        with Image.open(caminho) as imagem:
            largura, altura = imagem.size
        page = doc.new_page(width=largura * 72 / 300, height=altura * 72 / 300)
        page.insert_image(page.rect, filename=str(caminho))
        if camada_antiga:
            page.insert_text((5, 15), "hb7 lixo", fontsize=8, render_mode=3)
    destino = pasta / "livro.pdf"
    doc.save(destino)
    doc.close()
    return destino


@pytest.fixture
def projeto(tmp_path):
    return ProjetoDeLivro.criar(tmp_path / "livros", "Livro de Teste", pdf_sintetico(tmp_path))


@pytest.fixture
def leitor(projeto):
    return LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)


@pytest.fixture
def fonte(projeto):
    return pg.FonteDePaginas(projeto.fonte)


# ----------------------------------------------------------------------
# Intervalo
# ----------------------------------------------------------------------

def test_intervalo_em_numeros_de_pagina():
    assert livro.interpretar_intervalo("", 5) == [0, 1, 2, 3, 4]
    assert livro.interpretar_intervalo("2-3, 5", 5) == [1, 2, 4]
    assert livro.interpretar_intervalo("4-", 5) == [3, 4]
    assert livro.interpretar_intervalo("3-2 3", 5) == [1, 2]


@pytest.mark.parametrize("texto", ["0-2", "4-9", "a-b", "1..2"])
def test_intervalo_fora_do_livro_e_recusado(texto):
    with pytest.raises(ValueError):
        livro.interpretar_intervalo(texto, 5)


# ----------------------------------------------------------------------
# Lote
# ----------------------------------------------------------------------

def test_lote_grava_cada_pagina_com_progresso(projeto, fonte, leitor):
    progresso, gravadas = [], []
    resultado = livro.reconhecer_paginas(
        projeto, fonte, leitor, range(3), progresso=lambda f, t: progresso.append((f, t)),
        ao_gravar=lambda i, _r: gravadas.append(i))
    assert resultado.lidas == gravadas == [0, 1, 2]
    assert projeto.paginas_lidas() == [0, 1, 2]
    assert progresso == [(0, 3), (1, 3), (2, 3), (3, 3)]
    # Sem rede nem padrão, todo glifo fica para a revisão.
    assert resultado.pendentes[0] == len(projeto.carregar_pagina(0)) > 10


def test_lote_usa_os_padroes_do_livro(projeto, fonte, leitor):
    imagem = fonte.pagina(0)
    boxes = pg.segmentar(imagem)
    for indice, char in enumerate("abc"):
        pg.ensinar(imagem, boxes, indice, char, leitor, projeto, pagina=0, propagar=False)
    resultado = livro.reconhecer_paginas(projeto, fonte, leitor, [1, 2])
    texto = pg.texto(projeto.carregar_pagina(1))
    assert "bca cab" in texto
    assert resultado.total_de_pendentes == 0


def test_lote_pula_as_ja_lidas_sem_refazer(projeto, fonte, leitor):
    boxes = pg.segmentar(fonte.pagina(1))
    boxes[0].char, boxes[0].source, boxes[0].confidence = "b", FONTE_MANUAL, 1.0
    projeto.salvar_pagina(1, boxes)
    assert livro.ja_lidas(projeto, range(3)) == [1]

    resultado = livro.reconhecer_paginas(projeto, fonte, leitor, range(3))
    assert resultado.puladas == [1] and resultado.lidas == [0, 2]
    assert projeto.carregar_pagina(1)[0].source == FONTE_MANUAL

    refeito = livro.reconhecer_paginas(projeto, fonte, leitor, [1], refazer=True)
    assert refeito.lidas == [1]
    assert projeto.carregar_pagina(1)[0].source != FONTE_MANUAL


def test_cancelar_para_entre_paginas_e_guarda_as_feitas(projeto, fonte, leitor):
    gravadas = []
    resultado = livro.reconhecer_paginas(projeto, fonte, leitor, range(3),
                                         cancelado=lambda: len(gravadas) >= 1,
                                         ao_gravar=lambda i, _r: gravadas.append(i))
    assert resultado.cancelado
    assert projeto.paginas_lidas() == [0]


def test_cancelar_no_meio_da_pagina_nao_grava_ela_pela_metade(projeto, fonte, leitor):
    chamadas = []

    def cancelado():
        chamadas.append(1)
        return len(chamadas) > 3  # depois de segmentar, já dentro da leitura

    resultado = livro.reconhecer_paginas(projeto, fonte, leitor, [0], cancelado=cancelado)
    assert resultado.cancelado and resultado.lidas == []
    assert projeto.paginas_lidas() == []


def test_pagina_que_falha_nao_derruba_o_lote(projeto, fonte, leitor, monkeypatch):
    original = fonte.pagina

    def pagina(indice):
        if indice == 1:
            raise OSError("A página 2 não renderizou.")
        return original(indice)

    monkeypatch.setattr(fonte, "pagina", pagina)
    resultado = livro.reconhecer_paginas(projeto, fonte, leitor, range(3))
    assert resultado.lidas == [0, 2]
    assert "não renderizou" in resultado.falhas[1]


# ----------------------------------------------------------------------
# A fila do livro
# ----------------------------------------------------------------------

def test_proxima_pagina_com_pendentes_da_a_volta(projeto, fonte, leitor):
    livro.reconhecer_paginas(projeto, fonte, leitor, range(3))
    boxes = projeto.carregar_pagina(1)
    for b in boxes:
        b.char, b.source, b.confidence = "a", FONTE_MANUAL, 1.0
    projeto.salvar_pagina(1, boxes)
    limiares = projeto.dados.limiares

    assert set(livro.pendentes_por_pagina(projeto, limiares)) == {0, 2}
    assert livro.proxima_com_pendentes(projeto, limiares, 0) == 2
    assert livro.proxima_com_pendentes(projeto, limiares, 2) == 0
    assert livro.proxima_com_pendentes(projeto, limiares, 1) == 2


def test_sem_pendentes_no_livro_nao_ha_proxima(projeto, fonte, leitor):
    boxes = pg.segmentar(fonte.pagina(0))
    for b in boxes:
        b.char, b.source, b.confidence = "a", FONTE_MANUAL, 1.0
    projeto.salvar_pagina(0, boxes)
    assert livro.proxima_com_pendentes(projeto, projeto.dados.limiares, 0) is None


# ----------------------------------------------------------------------
# Exportar
# ----------------------------------------------------------------------

def _ensinar_e_ler(projeto, fonte, leitor):
    imagem = fonte.pagina(0)
    boxes = pg.segmentar(imagem)
    for indice, char in enumerate("abc"):
        pg.ensinar(imagem, boxes, indice, char, leitor, projeto, pagina=0, propagar=False)
    livro.reconhecer_paginas(projeto, fonte, leitor, range(3), refazer=True)


def test_paragrafos_cortam_no_vao_e_juntam_hifen():
    def linha(texto, y):
        return [pg.BoxEntry(c, 10 + 20 * i, y, 10 + 20 * i + 15, y + 20)
                for i, c in enumerate(texto) if c != " "]

    boxes = linha("abc-", 0) + linha("de fg", 40) + linha("jk", 80) + linha("hi", 200)
    blocos = ex.paragrafos(boxes)
    assert [p.texto for p in blocos] == ["abcde fg jk", "hi"]


def test_figurina_sai_como_impressa_e_nao_como_letra_do_san():
    boxes = [pg.BoxEntry(c, 10 + 20 * i, 0, 25 + 20 * i, 20) for i, c in enumerate("1.♘f3")]
    assert [p.texto for p in ex.paragrafos(boxes)] == ["1.♘f3"]


def test_docx_e_epub_tem_o_texto_das_paginas(projeto, fonte, leitor, tmp_path):
    _ensinar_e_ler(projeto, fonte, leitor)
    docx = tmp_path / "livro.docx"
    epub = tmp_path / "livro.epub"
    ex.exportar(projeto, docx)
    ex.exportar(projeto, epub, [1])

    from docx import Document

    texto_docx = "\n".join(p.text for p in Document(str(docx)).paragraphs)
    assert "abc abc abc" in texto_docx and "bca cab" in texto_docx
    with zipfile.ZipFile(epub) as z:
        assert z.namelist()[0] == "mimetype"
        xhtml = "".join(z.read(n).decode("utf-8") for n in z.namelist() if n.endswith(".xhtml"))
    assert "bca cab" in xhtml and "abc abc abc" not in xhtml


def test_diagrama_entra_como_recorte_na_altura_dele(projeto, fonte):
    imagem = fonte.pagina(0)
    boxes = pg.segmentar(imagem)
    for b in boxes:
        b.char = "a"
    meio = (boxes[0].y2 + max(b.y1 for b in boxes)) // 2
    pagina = ex.pagina_extraida(0, boxes, [(10, meio, 60, meio + 5)], imagem)
    tipos = [type(b).__name__ for b in pagina.blocos]
    assert tipos == ["Paragrafo", "Figura", "Paragrafo"]
    assert pagina.diagramas == 1
    figura = next(b for b in pagina.blocos if isinstance(b, ex.Figura))
    assert Image.open(io.BytesIO(figura.png)).size == (50, 5)


def test_pdf_pesquisavel_troca_a_camada_antiga(tmp_path):
    origem = pdf_sintetico(tmp_path, camada_antiga=True)
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Com Camada", origem)
    fonte = pg.FonteDePaginas(projeto.fonte)
    leitor = LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)
    _ensinar_e_ler(projeto, fonte, leitor)

    destino = tmp_path / "saida.pdf"
    resumo = ex.exportar_pdf_pesquisavel(projeto, destino, [0, 2])
    assert resumo.paginas == 2 and resumo.camadas_trocadas == 2 and resumo.caracteres > 20
    doc = fitz.open(destino)
    assert len(doc) == 2
    texto = doc[0].get_text()
    # Uma palavra por inserção: a extração devolve as palavras inteiras.
    assert "hb7" not in texto and "abc abc abc" in texto
    assert len(doc[0].search_for("abc")) == 3
    # A página não foi rasterizada: continua sendo a imagem original, e só ela.
    assert len(doc[0].get_images()) == 1
    doc.close()


def test_pdf_pesquisavel_de_imagem_solta(tmp_path):
    fonte_png = _pagina_sintetica(tmp_path / "solta.png")
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Solta", fonte_png)
    fonte = pg.FonteDePaginas(projeto.fonte)
    leitor = LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)
    _ensinar_e_ler(projeto, fonte, leitor)
    destino = tmp_path / "solta.pdf"
    ex.exportar(projeto, destino)
    with fitz.open(destino) as doc:
        assert "abc abc abc" in doc[0].get_text().replace("\n", " ") or "abc" in doc[0].get_text()


def test_sem_paginas_lidas_nao_exporta(projeto, tmp_path):
    with pytest.raises(ex.NadaParaExportar):
        ex.exportar(projeto, tmp_path / "x.epub")
    with pytest.raises(ValueError, match="não suportado"):
        ex.formato_do_caminho(tmp_path / "x.txt")
