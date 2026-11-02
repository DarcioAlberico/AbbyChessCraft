"""A camada de texto do PDF lida para a segunda opinião do F7 (`abbychess/camada.py`): as
palavras em pixels da imagem renderizada, e a página do livro que tem camada (SPEC-qualidade
§8: `camada.palavras` e `da_pagina` estavam quase sem cobertura)."""

from __future__ import annotations

import fitz
import pytest
from core.services.pdf_service import DPI_PADRAO

from abbychess import camada, pagina as pg, sequencia as sq
from abbychess.projeto import ProjetoDeLivro


def _pdf_com_texto(caminho, paginas=("rook and pawn", "the king")):
    with fitz.open() as doc:
        for texto in paginas:
            doc.new_page(width=300, height=200).insert_text((72, 100), texto, fontsize=12)
        doc.save(caminho)
    return caminho


def _palavras_do_fitz(caminho, pagina):
    with fitz.open(str(caminho)) as doc:
        return [(x0, y0, x1, y1, texto) for x0, y0, x1, y1, texto, *_ in doc[pagina].get_text("words")]


def test_as_palavras_da_camada_saem_em_pixels_da_imagem_renderizada(tmp_path):
    caminho = _pdf_com_texto(tmp_path / "livro.pdf")
    palavras = camada.palavras(caminho, 0, 2.0)
    assert [p.texto for p in palavras] == ["rook", "and", "pawn"]
    esperadas = [(x0 * 2, y0 * 2, x1 * 2, y1 * 2) for x0, y0, x1, y1, _t in _palavras_do_fitz(caminho, 0)]
    assert [p.caixa for p in palavras] == pytest.approx(esperadas)
    assert [p.texto for p in camada.palavras(caminho, 1, 1.0)] == ["the", "king"]


def test_a_camada_lida_de_novo_sai_igual_mesmo_depois_de_sair_da_memoria(tmp_path):
    caminho = _pdf_com_texto(tmp_path / "livro.pdf")
    primeira = camada.palavras(caminho, 0, 1.0)
    for k in range(1, 10):                    # mais escalas que as guardadas na memória
        camada.palavras(caminho, 0, 1.0 + k / 10)
    assert camada.palavras(caminho, 0, 1.0) == primeira
    assert camada.palavras(caminho, 0, 1.9) == camada.palavras(caminho, 0, 1.9)


def test_sem_camada_fora_do_livro_ou_com_o_arquivo_quebrado_a_camada_e_vazia(tmp_path):
    caminho = _pdf_com_texto(tmp_path / "livro.pdf", paginas=("",))
    assert camada.palavras(caminho, 0, 1.0) == []
    assert camada.palavras(caminho, 1, 1.0) == []
    assert camada.palavras(caminho, -1, 1.0) == []
    quebrado = tmp_path / "quebrado.pdf"
    quebrado.write_bytes(b"isto nao e um pdf")
    assert camada.palavras(quebrado, 0, 1.0) == []
    assert camada.palavras(tmp_path / "nao_existe.pdf", 0, 1.0) == []


def test_a_pagina_do_livro_tem_a_camada_na_escala_da_leitura(tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Camada", _pdf_com_texto(tmp_path / "livro.pdf"))
    fonte = pg.FonteDePaginas(projeto.fonte)
    assert camada.da_pagina(projeto, fonte, 1) == camada.palavras(projeto.fonte, 1, DPI_PADRAO / 72)
    assert [p.texto for p in camada.da_pagina(projeto, fonte, 1)] == ["the", "king"]
    assert camada.da_pagina(projeto, fonte, 2) == []     # fora do livro
    assert camada.da_pagina(projeto, None, 0) == []      # sem a fonte das páginas


def test_a_pagina_com_quadro_giro_ou_de_outro_arquivo_nao_tem_camada(tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Camada", _pdf_com_texto(tmp_path / "livro.pdf"))
    entradas = (sq.Entrada(0, pagina=0, giro=90), sq.Entrada(1, pagina=1, quadro=(0, 0, 100, 100)),
                sq.Entrada(2, fonte="inseridas/outra.pdf", pagina=0), sq.Entrada(3, pagina=1))
    fonte = pg.FonteDePaginas(projeto.fonte, sequencia=lambda: sq.Sequencia(entradas))
    assert [camada.da_pagina(projeto, fonte, k) for k in range(3)] == [[], [], []]
    assert [p.texto for p in camada.da_pagina(projeto, fonte, 3)] == ["the", "king"]


def test_o_livro_de_imagens_nao_tem_camada(tmp_path):
    from PIL import Image

    imagem = tmp_path / "pagina.png"
    Image.new("L", (60, 40), 255).save(imagem)
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Imagens", imagem)
    assert camada.da_pagina(projeto, pg.FonteDePaginas(projeto.fonte), 0) == []
