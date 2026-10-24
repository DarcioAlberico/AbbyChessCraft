"""Dividir páginas espelhadas (SPEC §12.4, passo L, rodada 3b): CA-12.13 e CA-4.6 depois da
divisão. A esquerda fica com o `pid`, a direita ganha um novo, e os glifos dela gids novos
(`gids_movidos`); as páginas são gravadas inteiras com a sequência, e o Ctrl+Z as junta."""

from __future__ import annotations

import json

import numpy as np
import pytest
from core.box_model import BoxEntry

from abbychess import pagina as pg
from abbychess.controlador import ControladorDePagina
from abbychess.leitor import LeitorDoLivro, nome_de_origem
from abbychess.modelo import Box, Decisoes, GlifoVirtual, Pagina, dividir, pid_de
from abbychess.projeto import ProjetoDeLivro

from tests.test_visor import pdf_de_60_paginas  # noqa: F401


@pytest.fixture
def projeto(tmp_path, pdf_de_60_paginas, monkeypatch):  # noqa: F811
    monkeypatch.setattr(pg, "medir_inclinacao", lambda *_a, **_k: 0.0)
    return ProjetoDeLivro.criar(tmp_path / "livros", "Dividir", pdf_de_60_paginas)


def _ligar(projeto):
    controlador = ControladorDePagina()
    controlador.ligar(projeto, pg.fonte_do_projeto(projeto),
                      LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    controlador.ir_para(0)
    return controlador


@pytest.fixture
def ctl(projeto):
    return _ligar(projeto)


def _imagem(ctl, posicao):
    return np.asarray(ctl.fonte.pagina(posicao).convert("L"))


def _gravar(projeto, ctl, posicao):
    """Três glifos na metade esquerda e dois na direita da página."""
    largura = _imagem(ctl, posicao).shape[1]
    meio = largura // 2
    caixas = [(30, 40, 52, 70), (60, 40, 80, 70), (100, 300, 140, 330),
              (meio + 20, 40, meio + 44, 70), (meio + 60, 40, meio + 80, 70)]
    projeto.salvar_pagina(posicao, [BoxEntry(char="abcde"[k], x1=a, y1=b, x2=c, y2=d,
                                             source="manual", confidence=1.0)
                                    for k, (a, b, c, d) in enumerate(caixas)])
    return meio


def _recortes(ctl, projeto, posicao):
    imagem = _imagem(ctl, posicao)
    return {b.gid: imagem[b.entry.y1:b.entry.y2, b.entry.x1:b.entry.x2].tobytes()
            for b in projeto.carregar_modelo(posicao).boxes}


# ----------------------------------------------------------------------
# CA-12.13
# ----------------------------------------------------------------------

def test_ca_12_13_dividir_da_duas_paginas_com_metade_dos_pixels(projeto, ctl):
    meio = _gravar(projeto, ctl, 2)
    imagem = _imagem(ctl, 2)
    recortes = _recortes(ctl, projeto, 2)
    gids = [b.gid for b in projeto.carregar_modelo(2).boxes]
    pid = projeto.pid_da_pagina(2)
    assert ctl.dividir_paginas([2])
    assert len(projeto.sequencia) == 61
    esquerda, direita = projeto.sequencia.entrada_em(2), projeto.sequencia.entrada_em(3)
    assert (esquerda.pid, esquerda.metade, direita.metade) == (pid, "esquerda", "direita")
    assert direita.pid not in range(60) and projeto.sequencia.entrada_em(4).pagina == 3
    assert np.array_equal(_imagem(ctl, 2), imagem[:, :meio])
    assert np.array_equal(_imagem(ctl, 3), imagem[:, meio:])
    assert [b.gid for b in projeto.carregar_modelo(2).boxes] == gids[:3]
    novos = [b.gid for b in projeto.carregar_modelo(3).boxes]
    assert [pid_de(g) for g in novos] == [direita.pid] * 2
    assert projeto.dados.gids_movidos == {str(v): n for v, n in zip(gids[3:], novos)}
    depois = {**_recortes(ctl, projeto, 2), **_recortes(ctl, projeto, 3)}
    for velho, novo in zip(gids, gids[:3] + novos):
        assert depois[novo] == recortes[velho]                  # os mesmos pixels


def test_ca_12_13_a_amostra_de_um_glifo_da_direita_acha_a_origem(projeto, ctl):
    _gravar(projeto, ctl, 5)
    gid = projeto.carregar_modelo(5).boxes[4].gid
    origem = nome_de_origem("Dividir", 5, 4, gid)
    ctl.dividir_paginas([5])
    novo = projeto.dados.gids_movidos[str(gid)]
    assert projeto.origem_da_amostra(origem) == (6, novo)
    assert projeto.carregar_modelo(6).boxes[1].gid == novo
    # a amostra antiga, sem gid, vai à metade esquerda
    assert projeto.origem_da_amostra(nome_de_origem("Dividir", 5, 4)) == (5, None)


def test_ca_12_13_dividir_uma_metade_e_recusado(projeto, ctl):
    ctl.dividir_paginas([1])
    antes = projeto.sequencia
    assert not ctl.dividir_paginas([1])
    assert not ctl.dividir_paginas([2])
    assert projeto.sequencia == antes
    assert not ctl.tirar_o_corte([2])


def test_ca_12_13_o_ctrl_z_junta_e_aposenta_o_pid_novo(projeto, ctl):
    _gravar(projeto, ctl, 2)
    antes = projeto.sequencia
    gids = [b.gid for b in projeto.carregar_modelo(2).boxes]
    recortes = _recortes(ctl, projeto, 2)
    ctl.dividir_paginas([2])
    pid_novo = projeto.sequencia.entrada_em(3).pid
    assert (projeto.pasta / "paginas" / f"p{pid_novo}.json").is_file()
    ctl.desfazer()
    assert projeto.sequencia == antes
    assert projeto.dados.gids_movidos == {}
    assert not (projeto.pasta / "paginas" / f"p{pid_novo}.json").exists()
    assert [b.gid for b in projeto.carregar_modelo(2).boxes] == gids
    assert _recortes(ctl, projeto, 2) == recortes
    assert projeto.novo_pid() > pid_novo                         # aposentado
    livro = json.loads((projeto.pasta / "livro.json").read_text(encoding="utf-8"))
    assert str(pid_novo) not in livro["paginas"]
    ctl.refazer()
    assert projeto.sequencia.entrada_em(3).pid == pid_novo
    assert len(projeto.carregar_modelo(3).boxes) == 2


def test_o_ctrl_z_recusa_se_a_metade_mudou_depois(projeto, ctl):
    _gravar(projeto, ctl, 2)
    ctl.dividir_paginas([2])
    pagina = projeto.carregar_modelo(3)
    projeto.salvar_pagina(3, [b.entry for b in pagina.boxes[:1]])   # por fora do desfazer
    sequencia = projeto.sequencia
    ctl.desfazer()
    assert projeto.sequencia == sequencia


def test_dividir_pagina_sem_glifos_so_muda_a_sequencia(projeto, ctl):
    assert ctl.dividir_paginas([7, 9])
    assert [projeto.sequencia.entrada_em(i).metade for i in (7, 8, 10, 11)] == \
        ["esquerda", "direita", "esquerda", "direita"]
    assert not list((projeto.pasta / "paginas").glob("p*.json"))
    ctl.desfazer()
    assert len(projeto.sequencia) == 60


def test_a_divisao_sobrevive_a_reabrir(projeto, ctl):
    _gravar(projeto, ctl, 0)
    ctl.dividir_paginas([0])
    recortes = {**_recortes(ctl, projeto, 0), **_recortes(ctl, projeto, 1)}
    projeto.fechar()
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    outro = _ligar(reaberto)
    assert {**_recortes(outro, reaberto, 0), **_recortes(outro, reaberto, 1)} == recortes
    assert reaberto.dados.gids_movidos == projeto.dados.gids_movidos


def test_dividir_uma_pagina_girada_divide_o_que_se_ve(projeto, ctl):
    _gravar(projeto, ctl, 4)
    ctl.girar_paginas([4], 90)
    vista = _imagem(ctl, 4)
    recortes = _recortes(ctl, projeto, 4)
    gids = [b.gid for b in projeto.carregar_modelo(4).boxes]
    largura = vista.shape[1]
    ctl.dividir_paginas([4], 0.4)
    corte = round(0.4 * largura)
    assert np.array_equal(_imagem(ctl, 4), vista[:, :corte])
    assert np.array_equal(_imagem(ctl, 5), vista[:, corte:])
    depois = {**_recortes(ctl, projeto, 4), **_recortes(ctl, projeto, 5)}
    movidos = {int(v): n for v, n in projeto.dados.gids_movidos.items()}
    for gid in gids:                                     # os mesmos pixels, girados ou não
        assert depois[movidos.get(gid, gid)] == recortes[gid]


def test_ca_4_6_nenhum_gid_se_repete_depois_de_dividir(projeto, ctl):
    for posicao in (0, 3):
        _gravar(projeto, ctl, posicao)
    ctl.dividir_paginas([0, 3])
    vistos = []
    for posicao in range(len(projeto.sequencia)):
        modelo = projeto.carregar_modelo(posicao)
        if modelo is not None:
            assert all(pid_de(b.gid) == modelo.pid for b in modelo.boxes)
            vistos += [b.gid for b in modelo.boxes]
    assert len(vistos) == len(set(vistos)) == 10


# ----------------------------------------------------------------------
# modelo.dividir: as decisões, as áreas, os diagramas
# ----------------------------------------------------------------------

def _box(gid, x):
    return Box(gid=gid, entry=BoxEntry(char="x", x1=x, y1=10, x2=x + 10, y2=30))


def test_as_decisoes_vao_com_os_glifos():
    pagina = Pagina(pid=1, indice=0, tamanho=(200, 100), proximo_n=10,
                    boxes=[_box(1 << 20 | n, x) for n, x in ((0, 10), (1, 50), (2, 120),
                                                              (3, 160))])
    g = [b.gid for b in pagina.boxes]
    pagina.decisoes = Decisoes(
        quebras=frozenset({g[1], g[3]}), juncoes=frozenset({(g[1], g[2]), (g[2], g[3])}),
        virtuais=(GlifoVirtual(1 << 20 | 4, "é", g[2]),
                  GlifoVirtual(1 << 20 | 5, "s", 1 << 20 | 4),
                  GlifoVirtual(1 << 20 | 6, "a", None)))
    esquerda, direita, movidos = dividir(pagina, 100, ((0, 0, 100, 100), 0),
                                         ((100, 0, 200, 100), 0), (200, 100), 7)
    assert movidos == {g[2]: 7 << 20, g[3]: 7 << 20 | 1}
    assert esquerda.decisoes.quebras == {g[1]}
    assert esquerda.decisoes.juncoes == frozenset()                  # a junção das metades
    assert direita.decisoes.quebras == {7 << 20 | 1}
    assert direita.decisoes.juncoes == {(7 << 20, 7 << 20 | 1)}
    assert [(v.char, v.gid, v.depois_de) for v in direita.decisoes.virtuais] == \
        [("é", 7 << 20 | 2, 7 << 20), ("s", 7 << 20 | 3, 7 << 20 | 2)]
    assert [v.char for v in esquerda.decisoes.virtuais] == ["a"]
    assert direita.proximo_n == 4 and esquerda.proximo_n == 10
    assert [b.entry.x1 for b in direita.boxes] == [20, 60]


def test_as_areas_sao_cortadas_e_os_diagramas_vao_pelo_centro():
    from abbychess.diagramas import DiagramaLido
    from abbychess.zonas import Zona

    pagina = Pagina(pid=1, indice=0, tamanho=(200, 100),
                    zonas=[Zona("texto", 10, 0, 190, 50, id="z0"),
                           Zona("texto", 10, 60, 104, 90, id="z1"),
                           Zona("texto", 120, 60, 180, 90, id="z2", funcao="legenda",
                                diagrama_id="d0")],
                    tabuleiros=[(110, 10, 190, 50)],
                    diagramas=[DiagramaLido(caixa=(110, 10, 190, 50), id="d0")])
    esquerda, direita, _ = dividir(pagina, 100, ((0, 0, 100, 100), 0),
                                   ((100, 0, 200, 100), 0), (200, 100), 7)
    assert [(z.id, z.caixa) for z in esquerda.zonas] == [("z0", (10, 0, 100, 50)),
                                                         ("z1", (10, 60, 100, 90))]
    assert [(z.id, z.caixa, z.diagrama_id) for z in direita.zonas] == [
        ("z0", (0, 0, 90, 50), None), ("z2", (20, 60, 80, 90), "d0")]
    assert esquerda.tabuleiros == [] and direita.tabuleiros == [(10, 10, 90, 50)]
    assert [d.caixa for d in direita.diagramas] == [(10, 10, 90, 50)]


# ----------------------------------------------------------------------
# A revisão da rodada 3b
# ----------------------------------------------------------------------

def test_refazer_a_divisao_nao_reaproveita_um_gid_da_direita(projeto, ctl):
    _gravar(projeto, ctl, 2)
    ctl.dividir_paginas([2])
    direita = projeto.carregar_modelo(3)
    direita.alocar()                                 # uma edição na direita, desfeita
    contador = direita.proximo_n
    ctl.desfazer()
    ctl.refazer()
    assert projeto.carregar_modelo(3).proximo_n >= contador


def test_o_glifo_fora_da_pagina_fica_guardado_na_esquerda(projeto, ctl):
    projeto.salvar_pagina(2, [BoxEntry(char="a", x1=30, y1=40, x2=50, y2=70, source="manual",
                                       confidence=1.0)])
    pagina = projeto.carregar_modelo(2)
    perdido = Box(gid=pagina.alocar(), entry=BoxEntry(char="z", x1=-30, y1=40, x2=-5, y2=70))
    pagina.boxes = [*pagina.boxes, perdido]
    projeto.salvar_modelo(pagina)
    assert ctl.dividir_paginas([2])
    esquerda = projeto.carregar_modelo(2)
    assert [b.entry.char for b in esquerda.boxes] == ["a"]
    assert [b.gid for _lugar, b in esquerda.fora] == [perdido.gid]


def test_falhar_ao_gravar_o_projeto_nao_deixa_o_arquivo_da_direita(projeto, ctl, monkeypatch):
    _gravar(projeto, ctl, 2)
    antes = projeto.sequencia

    def falhar():
        raise OSError("disco cheio")

    monkeypatch.setattr(projeto, "salvar", falhar)
    assert not ctl.dividir_paginas([2])
    assert projeto.sequencia == antes and projeto.dados.gids_movidos == {}
    assert [p.name for p in (projeto.pasta / "paginas").glob("p*.json")] == \
        [f"p{projeto.pid_da_pagina(2)}.json"]


def test_com_leitura_do_servidor_pendente_as_operacoes_esperam(projeto, ctl):
    ctl._em_leitura = {123}
    assert "servidor" in ctl.motivo_para_nao_mudar_as_paginas()
    assert not ctl.dividir_paginas([2])


def test_a_pagina_vazia_na_memoria_nao_impede_o_desfazer(projeto, ctl):
    ctl.dividir_paginas([7])
    projeto.pagina_para_editar(8)                    # nasce vazia na memória, sem arquivo
    ctl.desfazer()
    assert len(projeto.sequencia) == 60


def test_a_amostra_antiga_vai_a_esquerda_mesmo_com_a_direita_antes(projeto, ctl):
    ctl.dividir_paginas([5])
    ctl.mover_paginas([6], -1)                       # a direita vai para o começo
    assert projeto.sequencia.entrada_em(0).metade == "direita"
    assert projeto.origem_da_amostra(nome_de_origem("Dividir", 5, 0)) == (6, None)
