"""A fonte das páginas pela sequência do livro (SPEC §12.4, passo L, rodada 1c): renderizar
pela entrada (fonte, página, quadro, giro, ângulo), o cache chaveado pela entrada, a chave da
inclinação e o lote que resolve as páginas em `pid`."""

from __future__ import annotations

import json

import numpy as np
import pytest
from PIL import Image

from abbychess import pagina as pg
from abbychess import sequencia as sq
from abbychess.sequencia import Apagada, Entrada, Sequencia

from tests.test_visor import pdf_de_60_paginas  # noqa: F401


def _matriz(imagem):
    return np.asarray(imagem.convert("L"))


# ----------------------------------------------------------------------
# A geometria (conta exata, sem interpolar)
# ----------------------------------------------------------------------

@pytest.fixture
def ruido():
    sorteio = np.random.default_rng(3)
    return Image.fromarray(sorteio.integers(0, 255, (40, 70), dtype=np.uint8))


@pytest.mark.parametrize("giro, k", [(90, -1), (180, 2), (270, 1)])
def test_o_giro_e_o_rot90_horario(ruido, giro, k):
    assert np.array_equal(_matriz(pg.com_geometria(ruido, None, giro)),
                          np.rot90(_matriz(ruido), k=k))


def test_o_quadro_e_o_recorte_exato_e_vem_antes_do_giro(ruido):
    cortada = pg.com_geometria(ruido, (10, 5, 40, 25), 90)
    assert np.array_equal(_matriz(cortada), np.rot90(_matriz(ruido)[5:25, 10:40], k=-1))


@pytest.mark.parametrize("quadro", [(100, 0, 120, 10), (0, 0, 75, 40), (0, -5, 70, 40)])
def test_quadro_que_nao_cabe_e_recusado_sem_cortar_menos_em_silencio(ruido, quadro):
    with pytest.raises(pg.QuadroForaDaPagina, match="não cabe"):
        pg.com_geometria(ruido, quadro, 0)


def test_quadro_na_folga_do_arredondamento_vale(ruido):
    assert pg.com_geometria(ruido, (0, 0, 71, 41), 0).size == (70, 40)


def test_abrir_a_pagina_de_quadro_ruim_avisa_e_nao_derruba(tmp_path, pdf_de_60_paginas):  # noqa: F811
    from abbychess.controlador import ControladorDePagina
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Quadro", pdf_de_60_paginas)
    controlador = ControladorDePagina()
    avisos = []
    controlador.eventos.ligar("aviso", lambda titulo, texto: avisos.append(texto))
    controlador.ligar(projeto, pg.fonte_do_projeto(projeto),
                      LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    entrada = projeto.sequencia.entrada_em(3)
    projeto._trocar_sequencia(projeto.sequencia.com_entrada(
        Entrada(entrada.pid, "livro", 3, quadro=(0, 0, 99999, 50))))
    assert controlador.ir_para(3) is False and avisos and "não cabe" in avisos[0]


# ----------------------------------------------------------------------
# Renderizar pela entrada
# ----------------------------------------------------------------------

def _fonte(pdf, sequencia, tmp_path, **opcoes):
    return pg.FonteDePaginas(pdf, pasta=tmp_path, sequencia=lambda: sequencia, **opcoes)


def test_a_posicao_renderiza_a_pagina_da_entrada(pdf_de_60_paginas, tmp_path):  # noqa: F811
    solta = pg.FonteDePaginas(pdf_de_60_paginas)
    s = Sequencia((Entrada(7, "livro", 12), Entrada(3, "livro", 0)))
    fonte = _fonte(pdf_de_60_paginas, s, tmp_path)
    assert fonte.total == 2
    assert np.array_equal(_matriz(fonte.pagina(0)), _matriz(solta.pagina(12)))
    assert np.array_equal(_matriz(fonte.pagina(1)), _matriz(solta.pagina(0)))
    with pytest.raises(IndexError):
        fonte.pagina(2)


def test_a_pagina_inserida_vem_da_pasta_do_projeto(pdf_de_60_paginas, tmp_path, ruido):  # noqa: F811
    (tmp_path / sq.PASTA_DAS_INSERIDAS).mkdir()
    ruido.save(tmp_path / sq.PASTA_DAS_INSERIDAS / "ab12.png")
    s = Sequencia((Entrada(0), Entrada(9, "inseridas/ab12.png", 0, giro=180)))
    fonte = _fonte(pdf_de_60_paginas, s, tmp_path)
    assert np.array_equal(_matriz(fonte.pagina(1)), np.rot90(_matriz(ruido), k=2))


def test_o_angulo_a_mao_vence_o_medido(pdf_de_60_paginas, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(pg, "medir_inclinacao", lambda *_a, **_k: pytest.fail("mediu"))
    s = Sequencia((Entrada(0, angulo=1.5),))
    fonte = _fonte(pdf_de_60_paginas, s, tmp_path, endireitar=True)
    assert fonte.inclinacao(0) == 1.5
    assert not (tmp_path / pg.ARQUIVO_DE_INCLINACOES).exists()     # nada medido nem gravado


def test_a_chave_da_inclinacao(pdf_de_60_paginas, tmp_path):  # noqa: F811
    """A página do livro sem geometria usa o índice do PDF (o `inclinacoes.json` de antes
    continua valendo); a girada, o `pid` e a geometria."""
    (tmp_path / pg.ARQUIVO_DE_INCLINACOES).write_text(json.dumps({"4": 0.7}), encoding="utf-8")
    s = Sequencia((Entrada(30, "livro", 4), Entrada(31, "livro", 5, giro=90)))
    fonte = _fonte(pdf_de_60_paginas, s, tmp_path, endireitar=True)
    assert fonte.inclinacao(0) == 0.7                       # a medida antiga, pela página 5
    fonte.inclinacao(1)
    gravado = json.loads((tmp_path / pg.ARQUIVO_DE_INCLINACOES).read_text(encoding="utf-8"))
    assert set(gravado) == {"4", "p31:inteira:90"}
    reaberta = _fonte(pdf_de_60_paginas, s, tmp_path, endireitar=True)
    assert reaberta._inclinacoes == {4: 0.7, "p31:inteira:90": gravado["p31:inteira:90"]}


# ----------------------------------------------------------------------
# O cache chaveado pela entrada
# ----------------------------------------------------------------------

def test_o_cache_segue_a_pagina_que_muda_de_lugar(pdf_de_60_paginas, tmp_path):  # noqa: F811
    estado = {"s": Sequencia.do_livro(range(5))}
    fonte = pg.FonteDePaginas(pdf_de_60_paginas, sequencia=lambda: estado["s"])
    cache = pg.CacheDePaginas(fonte)
    imagem, _ = cache.pagina(2)
    entradas = estado["s"].entradas
    estado["s"] = Sequencia((entradas[2], *entradas[:2], *entradas[3:]))   # a 3 vai à 1
    assert cache.tem(0) and cache.pagina(0)[0] is imagem                  # sem renderizar
    estado["s"] = estado["s"].com_entrada(Entrada(2, "livro", 2, giro=90))
    assert not cache.tem(0)                                               # outra geometria


# ----------------------------------------------------------------------
# O lote por pid
# ----------------------------------------------------------------------

def test_o_lote_pula_a_pagina_que_saiu_do_livro_e_segue_a_que_mudou_de_lugar(
        tmp_path, pdf_de_60_paginas):  # noqa: F811
    from abbychess.controlador import ControladorDePagina
    from abbychess.leitor import LeitorDoLivro
    from abbychess.lote import CondutorDoLote
    from abbychess.projeto import ProjetoDeLivro

    origem = tmp_path / "curto.pdf"
    import fitz

    with fitz.open(str(pdf_de_60_paginas)) as doc:
        doc.select([0, 1, 2])
        doc.save(str(origem))
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Lote", origem)
    controlador = ControladorDePagina()
    controlador.ligar(projeto, pg.fonte_do_projeto(projeto),
                      LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    pids = projeto.sequencia.pids
    gravadas = []
    condutor = CondutorDoLote(controlador, [0, 1, 2], refazer=False,
                              ao_gravar=gravadas.append)
    entradas = projeto.sequencia.entradas
    # Antes de começar: a página 2 sai do livro e a 3 vai para a frente.
    projeto._trocar_sequencia(Sequencia((entradas[2], entradas[0]),
                                        (Apagada(entradas[1], 1),)))
    assert condutor.posicoes_restantes() == [1, 0]
    condutor.comecar()
    projeto.descarregar(30)
    assert condutor.resultado.fora_do_livro == [pids[1]]
    assert sorted(condutor.resultado.lidas) == [0, 1]
    assert projeto.carregar_modelo(0).pid == pids[2] and projeto.carregar_modelo(1).pid == pids[0]
    assert not (projeto.pasta / "paginas" / f"p{pids[1]}.json").exists()
    from abbychess import lote

    assert lote.tem_detalhe(condutor.resultado)
    assert "1 saíram do livro" in lote.resumo_do_fim(condutor.resultado)


def _controlador_de_3_paginas(tmp_path, pdf):
    import fitz

    from abbychess.controlador import ControladorDePagina
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro

    origem = tmp_path / "curto.pdf"
    with fitz.open(str(pdf)) as doc:
        doc.select([0, 1, 2])
        doc.save(str(origem))
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Lote", origem)
    controlador = ControladorDePagina()
    controlador.ligar(projeto, pg.fonte_do_projeto(projeto),
                      LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    return projeto, controlador


def test_a_pagina_que_muda_de_lugar_durante_a_leitura_e_gravada_no_lugar_novo(
        tmp_path, pdf_de_60_paginas):  # noqa: F811
    from abbychess.lote import CondutorDoLote

    projeto, controlador = _controlador_de_3_paginas(tmp_path, pdf_de_60_paginas)
    pids = projeto.sequencia.pids
    renderizar = controlador.fonte.pagina_da_entrada
    vistos = []

    def no_meio_da_leitura(entrada):
        vistos.append(entrada.pid)
        if entrada.pid == pids[0]:              # a primeira vai para o fim enquanto é lida
            e = projeto.sequencia.entradas
            projeto._trocar_sequencia(Sequencia((e[1], e[2], e[0])))
        return renderizar(entrada)

    controlador.fonte.pagina_da_entrada = no_meio_da_leitura
    condutor = CondutorDoLote(controlador, [0], refazer=False)
    condutor.comecar()
    projeto.descarregar(30)
    assert vistos == [pids[0]]                  # a imagem é a da página pedida
    assert condutor.resultado.lidas == [2] and not condutor.resultado.reler_depois
    assert projeto.carregar_modelo(2).pid == pids[0] and projeto.carregar_modelo(2).boxes


def test_o_progresso_chega_ao_total_com_posicoes_fora_do_livro(tmp_path, pdf_de_60_paginas):  # noqa: F811
    from abbychess.lote import CondutorDoLote

    projeto, controlador = _controlador_de_3_paginas(tmp_path, pdf_de_60_paginas)
    progresso = []
    condutor = CondutorDoLote(controlador, [0, 7], refazer=False,
                              ao_progresso=lambda feitas, total, _e: progresso.append(
                                  (feitas, total)))
    condutor.comecar()
    projeto.descarregar(30)
    assert progresso[-1] == (2, 2) and 7 in condutor.resultado.falhas
