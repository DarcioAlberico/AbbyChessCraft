"""O FEN dos diagramas no reconhecimento em lote e na exportação.

O F5 da janela já lia os diagramas; o lote e a exportação ainda não. Aqui o
lote lê e grava o FEN sem desfazer o que foi conferido, e a exportação desenha
do FEN o diagrama que merece confiança, com o FEN no texto alternativo e na
camada pesquisável do PDF.
"""

from __future__ import annotations

import zipfile

import fitz
import pytest

from abbychess import exportar as ex
from abbychess import livro
from abbychess import pagina as pg
from abbychess.leitor import LeitorDoLivro
from abbychess.projeto import ProjetoDeLivro

from tests.test_diagramas import FEN, _lido, pagina_com_diagrama, sem_modelo


@pytest.fixture
def projeto(tmp_path):
    return ProjetoDeLivro.criar(tmp_path / "livros", "Com diagrama",
                                pagina_com_diagrama(tmp_path / "pagina.png"))


@pytest.fixture
def leitor(projeto):
    return LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)


@pytest.fixture
def fonte(projeto):
    return pg.FonteDePaginas(projeto.fonte)


def _gravar_com(projeto, fonte, diagrama):
    """A página gravada com o texto lido e um diagrama na caixa do tabuleiro."""
    boxes = pg.segmentar(fonte.pagina(0))
    for b in boxes:
        b.char = "a"
    projeto.salvar_pagina(0, boxes, [diagrama.caixa], [diagrama])


# ----------------------------------------------------------------------
# O lote
# ----------------------------------------------------------------------

@sem_modelo
def test_lote_le_o_diagrama_em_fen(projeto, fonte, leitor):
    resultado = livro.reconhecer_paginas(projeto, fonte, leitor, [0])
    [diagrama] = projeto.carregar_diagramas(0)
    assert diagrama.fen.split()[0] == FEN
    assert resultado.diagramas == {0: 1}


def test_lote_refeito_nao_desfaz_a_conferencia(projeto, fonte, leitor):
    outro = "4k3/8/8/8/8/8/8/4K3"
    conferido = _lido(outro, conferido=True, lado="b", lado_origem="usuario")
    _gravar_com(projeto, fonte, conferido)
    tabuleiros = pg.segmentar_pagina(fonte.pagina(0)).tabuleiros
    if not tabuleiros:
        pytest.skip("a segmentação não achou o tabuleiro desta página")
    conferido.caixa = tabuleiros[0]
    _gravar_com(projeto, fonte, conferido)

    livro.reconhecer_paginas(projeto, fonte, leitor, [0], refazer=True)

    [diagrama] = projeto.carregar_diagramas(0)
    assert diagrama.conferido and diagrama.fen.startswith(f"{outro} b ")


# ----------------------------------------------------------------------
# A exportação
# ----------------------------------------------------------------------

def test_diagrama_conferido_sai_desenhado_do_fen(fonte):
    imagem = fonte.pagina(0)
    diagrama = _lido(conferido=True, lado="b", lado_origem="usuario")
    pagina = ex.pagina_extraida(0, [], [diagrama.caixa], imagem, [diagrama])
    [figura] = [b for b in pagina.blocos if isinstance(b, ex.Figura)]
    assert figura.origem == "render"
    assert figura.fen == diagrama.fen and figura.fen.split()[1] == "b"
    assert figura.lado_a_jogar == "b" and figura.revisao_pendente is False
    assert figura.linhas  # o modo de fonte de xadrez do DOCX e do EPUB


def test_diagrama_sem_confianca_sai_como_recorte_com_o_motivo(fonte):
    imagem = fonte.pagina(0)
    duvidoso = _lido(motivo="duas damas brancas a mais")
    por_ler = _lido(caixa=(10, 10, 60, 60))
    por_ler.casas = []
    pagina = ex.pagina_extraida(0, [], [duvidoso.caixa, por_ler.caixa], imagem,
                                [duvidoso, por_ler])
    figuras = [b for b in pagina.blocos if isinstance(b, ex.Figura)]
    assert [f.origem for f in figuras] == ["recorte", "recorte"]
    assert any("duas damas" in f.aviso for f in figuras)
    assert any("não lido" in f.aviso for f in figuras)
    assert not any(f.fen for f in figuras)


def test_epub_tem_o_fen_no_texto_alternativo(projeto, fonte, tmp_path):
    _gravar_com(projeto, fonte, _lido(conferido=True))
    destino = tmp_path / "livro.epub"
    mensagem = ex.exportar(projeto, destino)
    assert "1 diagrama(s) desenhado(s) do FEN" in mensagem
    with zipfile.ZipFile(destino) as z:
        xhtml = "".join(z.read(n).decode("utf-8") for n in z.namelist() if n.endswith(".xhtml"))
    assert FEN in xhtml


def test_docx_sai_com_o_diagrama_desenhado(projeto, fonte, tmp_path):
    _gravar_com(projeto, fonte, _lido(conferido=True))
    destino = tmp_path / "livro.docx"
    assert "1 diagrama(s) desenhado(s) do FEN" in ex.exportar(projeto, destino)
    with zipfile.ZipFile(destino) as z:
        assert FEN in z.read("word/document.xml").decode("utf-8")


def test_pdf_pesquisavel_acha_o_fen(projeto, fonte, tmp_path):
    _gravar_com(projeto, fonte, _lido(conferido=True))
    destino = tmp_path / "livro.pdf"
    assert "1 diagrama(s) com o FEN pesquisável" in ex.exportar(projeto, destino)
    with fitz.open(destino) as doc:
        assert FEN in doc[0].get_text("text").replace("\n", "")


def test_pdf_sem_fen_do_diagrama_duvidoso(projeto, fonte, tmp_path):
    _gravar_com(projeto, fonte, _lido(motivo="peças demais"))
    destino = tmp_path / "livro.pdf"
    ex.exportar(projeto, destino)
    with fitz.open(destino) as doc:
        assert FEN not in doc[0].get_text("text")
