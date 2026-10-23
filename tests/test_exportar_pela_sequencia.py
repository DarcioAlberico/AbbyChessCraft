"""A origem das amostras e as exportações pela sequência do livro (SPEC §12.4, passo L,
rodada 1d). Ainda não há operação que reordene (rodada 2): a sequência é trocada na memória,
como a operação vai trocá-la."""

from __future__ import annotations

import pytest
from core.box_model import BoxEntry

from abbychess import exportar as ex
from abbychess import pagina as pg
from abbychess.leitor import nome_de_origem
from abbychess.modelo import gid_de
from abbychess.projeto import ProjetoDeLivro
from abbychess.sequencia import Apagada, Entrada, Sequencia

from tests.test_visor import pdf_de_60_paginas  # noqa: F401


def _box(char, x=10):
    return BoxEntry(char=char, x1=x, y1=10, x2=x + 8, y2=22, source="manual", confidence=1.0)


@pytest.fixture
def projeto(tmp_path, pdf_de_60_paginas):  # noqa: F811
    return ProjetoDeLivro.criar(tmp_path / "livros", "Exportar", pdf_de_60_paginas)


def _reordenar(projeto, ordem, apagar=()):
    s = projeto.sequencia
    entradas = tuple(s.entradas[i] for i in ordem)
    apagadas = tuple(Apagada(s.entradas[i], i) for i in apagar)
    projeto._trocar_sequencia(Sequencia(entradas, apagadas))


# ----------------------------------------------------------------------
# A origem das amostras
# ----------------------------------------------------------------------

def test_a_amostra_acha_a_pagina_pelo_gid_depois_de_reordenar(projeto):
    projeto.salvar_pagina(4, [_box("a")])
    gid = projeto.carregar_modelo(4).boxes[0].gid
    origem = nome_de_origem("livro", 4, 0, gid)                   # "…_p0005_b0_g…"
    assert projeto.origem_da_amostra(origem) == (4, gid)
    _reordenar(projeto, [4, *range(4), *range(5, 60)])            # a página 5 vai à frente
    assert projeto.origem_da_amostra(origem) == (0, gid)


def test_a_amostra_cuja_pagina_saiu_do_livro_diz_que_saiu(projeto):
    projeto.salvar_pagina(4, [_box("a")])
    gid = projeto.carregar_modelo(4).boxes[0].gid
    _reordenar(projeto, [i for i in range(60) if i != 4], apagar=[4])
    assert projeto.origem_da_amostra(nome_de_origem("livro", 4, 0, gid)) == (None, gid)


def test_a_amostra_antiga_sem_gid_vai_a_pagina_do_pdf_do_nome(projeto):
    _reordenar(projeto, [9, *range(9), *range(10, 60)])
    assert projeto.origem_da_amostra("livro_p0010_b3") == (0, None)
    assert projeto.origem_da_amostra("sem o padrão de nome") is None


def test_a_origem_vem_do_gid_e_nao_do_numero_da_pagina_no_nome(projeto):
    """O nome diz a página 13 (a de quando foi ensinada); o gid diz a página do pid 30."""
    origem = nome_de_origem("livro", 12, 3, gid_de(30, 3))
    _reordenar(projeto, [*range(30, 60), *range(30)])            # o pid 30 vai à posição 1
    assert projeto.origem_da_amostra(origem) == (0, gid_de(30, 3))


def test_o_sinal_ir_para_leva_o_none_da_pagina_que_saiu():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from abbychess.app.painel_padroes import PainelDePadroes

    QApplication.instance() or QApplication([])
    painel, recebidos = PainelDePadroes(), []
    painel.ir_para.connect(lambda pagina, gid: recebidos.append((pagina, gid)))
    painel.ir_para.emit(None, 5)
    assert recebidos == [(None, 5)]                 # e não (0, 5): a página 1


# ----------------------------------------------------------------------
# Os trechos da camada de texto (a junção entre páginas segue o livro)
# ----------------------------------------------------------------------

def test_os_trechos_sao_seguidos_no_livro_e_no_pdf():
    from abbychess import sequencia as sq

    s = Sequencia((Entrada(0, "livro", 0), Entrada(1, "livro", 1), Entrada(5, "livro", 5),
                   Entrada(6, "livro", 6, giro=90), Entrada(7, "livro", 7),
                   Entrada(8, "livro", 8), Entrada(2, "livro", 2)))
    assert sq.trechos_do_pdf(s, range(7)) == [[(0, 0), (1, 1)], [(5, 2)], [(7, 4), (8, 5)],
                                              [(2, 6)]]
    assert sq.trechos_do_pdf(s, [0, 5]) == [[(0, 0)], [(8, 5)]]


def test_a_importacao_da_camada_segue_a_ordem_do_livro(tmp_path):
    from abbychess import nativo
    from abbychess import texto as tx

    from tests.test_exportar_preciso import _pdf_digital

    pdf = _pdf_digital(tmp_path / "digital.pdf", paginas=3)
    projeto = ProjetoDeLivro.criar(tmp_path / "projetos", "Digital", pdf)
    _reordenar(projeto, [2, 0, 1])
    resultado = nativo.importar(projeto)
    assert resultado.importadas == (0, 1, 2)
    assert "Chapter 3" in tx.texto(tx.montar(projeto.carregar_modelo(0)))
    assert "Chapter 1" in tx.texto(tx.montar(projeto.carregar_modelo(1)))


# ----------------------------------------------------------------------
# As exportações
# ----------------------------------------------------------------------

def _ler(projeto, paginas):
    for i, letra in paginas:
        projeto.salvar_pagina(i, [_box(letra), _box(letra, x=20)])


def test_o_txt_segue_a_ordem_do_livro(projeto):
    _ler(projeto, [(0, "a"), (1, "b"), (2, "c")])
    _reordenar(projeto, [2, 0, 1, *range(3, 60)])
    # Uma linha só no alto da página é cabeçalho corrido: as margens ficam, para o texto sair.
    paginas = ex.paginas_do_projeto(projeto, pg.fonte_do_projeto(projeto), camada="nunca",
                                    opcoes=ex.Opcoes(manter_margens=True))
    assert [p.numero for p in paginas] == [0, 1, 2]
    texto = ex.texto_do_livro(paginas)
    assert texto.index("cc") < texto.index("aa") < texto.index("bb")


def test_o_pdf_pesquisavel_sai_na_ordem_do_livro(projeto, tmp_path):
    import fitz

    _ler(projeto, [(0, "a"), (1, "b"), (2, "c")])
    _reordenar(projeto, [2, 0, 1, *range(3, 60)])
    saida = tmp_path / "pesquisavel.pdf"
    ex.exportar_pdf_pesquisavel(projeto, saida)
    with fitz.open(str(saida)) as doc:
        impressas = [doc[k].get_text().split("Pagina")[1].split()[0] for k in range(3)]
    assert impressas == ["3", "1", "2"]                  # o texto impresso do PDF de cada uma


def test_ca_12_16_o_pdf_pesquisavel_usa_as_imagens_transformadas(projeto, tmp_path):
    """A página girada e a inserida saem com a imagem da entrada, e a camada de texto em cima
    do que se vê; a do original sem quadro nem giro continua do original."""
    import fitz
    import numpy as np
    from PIL import Image

    _ler(projeto, [(0, "a"), (1, "b")])
    fonte = pg.fonte_do_projeto(projeto)
    e = projeto.sequencia.entrada_em(0)
    largura, altura = fonte.tamanho_da_fonte(e)
    projeto._trocar_sequencia(projeto.sequencia.com_entrada(
        Entrada(e.pid, "livro", e.pagina, giro=90, tamanho=(largura, altura))))
    caixa = projeto.carregar_pagina(0)[0]                  # o "a" na página girada
    imagem = tmp_path / "solta.png"
    Image.fromarray(np.full((400, 300), 255, np.uint8)).save(imagem)
    inseridas = projeto.inserir_arquivo(imagem)
    projeto.gravar_sequencia(projeto.sequencia.inserir(inseridas, 2))
    projeto.salvar_pagina(2, [_box("c"), _box("c", x=20)])
    saida = tmp_path / "pesquisavel.pdf"
    ex.exportar_pdf_pesquisavel(projeto, saida)
    escala = 72.0 / ex.DPI_DA_LEITURA
    with fitz.open(str(saida)) as doc:
        assert len(doc) == 3
        girada, original, inserida = doc[0], doc[1], doc[2]
        assert girada.rect.width == pytest.approx(altura * escala)
        assert girada.rect.height == pytest.approx(largura * escala)
        assert girada.get_images() and inserida.get_images()
        palavra = next(w for w in girada.get_text("words") if w[4] == "aa")
        assert palavra[0] == pytest.approx(caixa.x1 * escala, abs=1)
        assert palavra[1] == pytest.approx(caixa.y1 * escala, abs=2)
        assert "Pagina" in original.get_text()              # o texto do original, vetorial
        assert inserida.rect.width == pytest.approx(300 * escala)
        assert "cc" in inserida.get_text()


def test_a_altura_vem_da_pagina_do_pdf_da_entrada(tmp_path):
    import fitz

    pdf = tmp_path / "alturas.pdf"
    with fitz.open() as doc:
        for altura in (300, 400, 500):
            doc.new_page(width=200, height=altura)
        doc.save(str(pdf))
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Alturas", pdf)
    _reordenar(projeto, [2, 0, 1])
    assert [ex._altura_da_pagina(projeto, i) for i in range(3)] == [
        round(a * ex.DPI_DA_LEITURA / 72) for a in (500, 300, 400)]
    e = projeto.sequencia.entrada_em(0)                          # girada: renderiza
    projeto._trocar_sequencia(projeto.sequencia.com_entrada(
        Entrada(e.pid, "livro", e.pagina, giro=90,
                tamanho=pg.fonte_do_projeto(projeto).tamanho_da_fonte(e))))
    assert ex._altura_da_pagina(projeto, 0) == pg.fonte_do_projeto(projeto).original(0).height


def test_o_sumario_do_original_fora_de_ordem_nao_vai_para_o_pdf(projeto, tmp_path):
    import fitz

    _ler(projeto, [(0, "a"), (1, "b"), (2, "c")])
    with fitz.open(str(projeto.fonte)) as doc:                   # o original com sumário
        doc.set_toc([[1, "Um", 1], [1, "Dois", 2], [1, "Tres", 3]])
        doc.save(str(tmp_path / "com_sumario.pdf"))
    projeto.fonte.write_bytes((tmp_path / "com_sumario.pdf").read_bytes())
    _reordenar(projeto, [2, 0, 1, *range(3, 60)])
    saida = tmp_path / "pesquisavel.pdf"
    ex.exportar_pdf_pesquisavel(projeto, saida)
    with fitz.open(str(saida)) as doc:
        paginas = [m[2] for m in doc.get_toc()]
    assert paginas == sorted(paginas)                            # nenhum destino para trás
