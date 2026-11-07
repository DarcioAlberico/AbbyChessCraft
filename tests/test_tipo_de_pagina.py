"""L-9: CA-L9.1 a CA-L9.4. A página de imagem não é segmentada, não inventa linhas, sai inteira na
exportação, e nunca em silêncio. Os cortes são conferidos nos gabaritos, no portão (CA-L9.2)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pytest
from core.box_model import BoxEntry
from PIL import Image, ImageDraw

from abbychess import arrumacao
from abbychess import exportar as ex
from abbychess import lote as lt
from abbychess import pagina as pg
from abbychess import servidor_de_leitura as sl
from abbychess import tipo_de_pagina as tp
from abbychess import zonas as zn
from abbychess.app import vazios
from abbychess.app.desenho import _aviso_do_documento
from abbychess.app.janela import JanelaPrincipal
from abbychess.leitor import LeitorDoLivro
from abbychess.modelo import Box, Pagina
from abbychess.projeto import ProjetoDeLivro
from tests.ajudantes import _esperar

VERDADE = Path(__file__).parent / "verdade"


def _capa(largura=800, altura=1100) -> Image.Image:
    """Muita tinta, em manchas e em poeira: uma capa."""
    rng = np.random.default_rng(3)
    matriz = (rng.random((altura, largura)) > 0.55).astype(np.uint8) * 255
    imagem = Image.fromarray(matriz, "L")
    ImageDraw.Draw(imagem).rectangle((100, 100, 700, 700), fill=0)
    return imagem


def _texto(largura=800, altura=1100) -> Image.Image:
    imagem = Image.new("L", (largura, altura), 255)
    pintor = ImageDraw.Draw(imagem)
    for y in range(60, altura - 60, 26):
        for x in range(60, largura - 60, 14):
            pintor.rectangle((x, y, x + 8, y + 14), fill=0)
    return imagem


def test_a_capa_e_imagem_e_o_texto_nao():
    assert tp.e_imagem(_capa())
    assert not tp.e_imagem(_texto())


def test_a_pagina_branca_nao_e_imagem():
    assert not tp.e_imagem(Image.new("L", (400, 600), 255))


def test_as_medidas_da_pagina_preta_nao_quebram():
    assert tp.medidas(Image.new("L", (10, 10), 0))["tinta"] >= 0


class _LeitorQueNaoDeveLer:
    arbitro = None
    limiares = None

    def __getattr__(self, nome):
        raise AssertionError(f"não devia ler: {nome}")


def test_a_pagina_de_imagem_nao_passa_pela_leitura():
    lida = sl.ler_pagina(_capa(), [], [], _LeitorQueNaoDeveLer())
    assert lida.imagem and lida.boxes == [] and lida.tabuleiros == []


def test_com_area_ou_glifo_marcado_o_classificador_nao_entra(monkeypatch, tmp_path):
    chamadas = []
    monkeypatch.setattr(tp, "e_imagem", lambda _i: chamadas.append(1) or True)
    zona = zn.Zona(zn.IMAGEM, 0, 0, 10, 10, funcao="figura")
    lida = sl.ler_pagina(Image.new("L", (20, 20), 255), [zona], [], LeitorDoLivro(tmp_path))
    assert not lida.imagem and not chamadas


def test_a_area_so_de_figura_nao_segmenta():
    zona = zn.Zona(zn.IMAGEM, 0, 0, 800, 1100, funcao="figura")
    segmentada = zn.segmentar_com_zonas(_capa(), [zona], _LeitorQueNaoDeveLer())
    assert segmentada.boxes == [] and segmentada.tabuleiros == []


def test_aplicar_a_lida_poe_a_area_da_pagina_inteira():
    pagina = Pagina(0, 0)
    lida = sl.PaginaLida([], [], [], None, imagem=True)
    arrumacao.aplicar_lida(pagina, lida, "pt", tamanho=(800, 1100))
    [zona] = pagina.zonas
    assert (zona.funcao, zona.x1, zona.y1, zona.x2, zona.y2) == ("figura", 0, 0, 800, 1100)
    assert pagina.estado == "reconhecida" and tp.tratada_como_imagem(pagina)


def test_a_pagina_com_glifos_nao_e_tratada_como_imagem():
    pagina = Pagina(0, 0, boxes=[Box(0, BoxEntry("a", 0, 0, 1, 1))],
                    zonas=[zn.Zona(zn.IMAGEM, 0, 0, 10, 10, funcao="figura")])
    assert not tp.tratada_como_imagem(pagina)
    assert not tp.tratada_como_imagem(Pagina(0, 0))


def test_o_fim_do_lote_diz_quantas():
    r = lt.ResultadoDoLote(lidas=[0, 1, 2], como_imagem=[0])
    assert "1 tratada(s) como imagem" in lt.resumo_do_fim(r)
    assert "Tratadas como imagem" in lt.detalhe_do_fim(r)


@pytest.fixture
def projeto_de_capa(tmp_path):
    caminho = tmp_path / "capa.png"
    _capa().save(caminho)
    projeto = ProjetoDeLivro.criar(tmp_path / "x", "Livro", caminho)
    yield projeto
    projeto.fechar()


def _gravar_como_imagem(projeto):
    pagina = projeto.pagina_para_editar(0)
    arrumacao.aplicar_lida(pagina, sl.PaginaLida([], [], [], None, imagem=True), "pt",
                           tamanho=(800, 1100))
    projeto.salvar_modelo(pagina)
    return pagina


def test_ca_l9_3_a_exportacao_poe_a_pagina_inteira_e_o_relatorio_lista(projeto_de_capa):
    _gravar_como_imagem(projeto_de_capa)
    relatorio = ex.Relatorio()
    paginas = ex.paginas_do_projeto(projeto_de_capa, pg.fonte_do_projeto(projeto_de_capa),
                                    relatorio=relatorio)
    [figura] = paginas[0].blocos
    assert figura.largura > 0 and figura.origem == "recorte"
    assert relatorio.recortados == [(0, "página tratada como imagem")]


def test_o_resumo_marca_so_a_tratada_como_imagem(projeto_de_capa):
    pagina = _gravar_como_imagem(projeto_de_capa)
    assert projeto_de_capa.resumo.do_modelo(pagina)["imagem"] is True
    assert "imagem" not in projeto_de_capa.resumo.do_modelo(Pagina(1, 1))


@pytest.fixture
def janela(app, projeto_de_capa):
    j = JanelaPrincipal()
    j.usar(projeto_de_capa, pg.FonteDePaginas(projeto_de_capa.fonte),
           LeitorDoLivro(projeto_de_capa.pasta_de_padroes, limiares=projeto_de_capa.dados.limiares))
    j.show()
    yield j
    j.close()


def test_o_documento_diz_que_e_imagem_com_a_tecla(app, janela, monkeypatch):
    _gravar_como_imagem(janela.projeto)
    janela.pagina.ir_para(0)
    aviso = _aviso_do_documento(janela.pagina)
    assert aviso == vazios.tratada_como_imagem()
    assert "tratada como imagem" in aviso and "Ctrl+Shift+T" in aviso


def test_ca_l9_4_a_tecla_le_como_texto_e_ctrl_z_volta(app, janela, monkeypatch):
    p = janela.pagina
    p.ir_para(0)
    _esperar(app, janela)
    janela.reconhecer()
    _esperar(app, janela)
    assert p.modelo.zonas and tp.tratada_como_imagem(p.modelo), p.modelo.estado
    monkeypatch.setattr(sl, "ler_pagina", lambda img, zonas, *a, **k: sl.PaginaLida(
        [BoxEntry("a", 10, 10, 30, 30, 0.9, "net")], [None], [], None))
    janela.acao_ler_como_texto.trigger()
    _esperar(app, janela)
    assert not tp.tratada_como_imagem(p.modelo) and len(p.modelo.boxes) == 1
    assert p.modelo.zonas[0].funcao == "texto"
    janela.acao_desfazer.trigger()
    _esperar(app, janela)
    assert tp.tratada_como_imagem(p.modelo)


def test_ca_l9_4_a_lista_e_o_filtro_trazem_a_capa(app, janela):
    _gravar_como_imagem(janela.projeto)
    janela.listar_as_tratadas_como_imagem()
    lista = janela.resultados.resultados
    assert any("p. 1" in lista.item(k).text() for k in range(1, lista.count()))
    janela.abrir_gaveta()
    janela.atualizar_paginas()
    gaveta = janela.paginas
    gaveta.filtro.setCurrentIndex(gaveta.filtro.findData("imagem"))
    assert not gaveta.lista.topLevelItem(0).isHidden()


def test_a_tecla_fora_da_pagina_de_imagem_avisa(app, janela):
    avisos = []
    janela.pagina.eventos.ligar("mensagem", lambda t, _ms: avisos.append(t))
    janela.pagina.leitura.ler_como_texto()
    assert "não está tratada como imagem" in avisos[-1]


@pytest.mark.livro_real
@pytest.mark.timeout(600)
def test_ca_l9_2_nenhuma_pagina_com_gabarito_de_texto_cai_nele():
    from tests.livros import PASTA_DOS_PDFS

    import fitz

    caidas = []
    for livro in ("xv", "darcy", "yusupov"):
        for arquivo in sorted((VERDADE / livro).glob("i*.json")):
            g = json.loads(arquivo.read_text(encoding="utf-8"))
            if not any(ln.get("texto") for ln in g.get("linhas_corpo", [])):
                continue
            pdf = next(PASTA_DOS_PDFS.rglob(g["pdf"]), None)
            if pdf is None:
                pytest.skip(f"o PDF de {livro} não está nesta máquina")
            with fitz.open(pdf) as doc:
                pix = doc[g["indice_pdf"]].get_pixmap(dpi=g.get("dpi_de_leitura", 300),
                                                      colorspace=fitz.csGRAY)
            matriz = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w)
            if tp.e_imagem(matriz):
                caidas.append(f"{livro}/{arquivo.stem}")
    assert caidas == []


@pytest.mark.livro_real
@pytest.mark.timeout(600)
def test_ca_l9_1_a_capa_do_seirawan_em_menos_de_5_s_tambem_no_segundo_f5(tmp_path):
    from tests.livros import PASTA_DOS_PDFS

    pdf = sorted(PASTA_DOS_PDFS.glob("Xadrez Vitorioso*/*.pdf"))
    if not pdf:
        pytest.skip("o PDF do Xadrez Vitorioso não está nesta máquina")
    projeto = ProjetoDeLivro.criar(tmp_path, "Capa", pdf[0])
    try:
        imagem = pg.fonte_do_projeto(projeto).pagina(0)
        leitor = sl.leitor_global(projeto.pasta_de_padroes, projeto.dados.limiares)
        inicio = time.perf_counter()
        lida = sl.ler_pagina(imagem, [], [], leitor)
        assert lida.imagem and time.perf_counter() - inicio < 5
        pagina = projeto.pagina_para_editar(0)
        arrumacao.aplicar_lida(pagina, lida, "pt", tamanho=imagem.size)
        inicio = time.perf_counter()
        segunda = sl.ler_pagina(imagem, list(pagina.zonas), [], leitor)
        assert segunda.boxes == [] and time.perf_counter() - inicio < 5
    finally:
        projeto.fechar()
