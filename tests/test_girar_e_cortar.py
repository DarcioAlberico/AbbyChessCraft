"""Girar e cortar páginas (SPEC §12.4, passo L, rodada 3a): CA-12.11 e CA-12.12. Os boxes
seguem a imagem com conta exata, a operação grava só a sequência (cada página é levada à
geometria nova quando é lida) e o Ctrl+Z volta tudo; o glifo cortado fica guardado."""

from __future__ import annotations

import json

import numpy as np
import pytest
from core.box_model import BoxEntry

from abbychess import pagina as pg
from abbychess.controlador import ControladorDePagina
from abbychess.leitor import LeitorDoLivro
from abbychess.projeto import ProjetoDeLivro

from tests.test_visor import pdf_de_60_paginas  # noqa: F401


@pytest.fixture
def sem_endireitar(monkeypatch):
    """O ângulo zero: a imagem girada é exatamente `np.rot90` da de antes."""
    monkeypatch.setattr(pg, "medir_inclinacao", lambda *_a, **_k: 0.0)


@pytest.fixture
def projeto(tmp_path, pdf_de_60_paginas, sem_endireitar):  # noqa: F811
    return ProjetoDeLivro.criar(tmp_path / "livros", "Girar", pdf_de_60_paginas)


def _ligar(projeto):
    controlador = ControladorDePagina()
    controlador.ligar(projeto, pg.fonte_do_projeto(projeto),
                      LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    controlador.ir_para(0)
    return controlador


@pytest.fixture
def ctl(projeto):
    return _ligar(projeto)


CAIXAS = [(30, 40, 52, 70), (120, 300, 160, 330), (500, 900, 540, 950)]


def _gravar(projeto, posicao):
    projeto.salvar_pagina(posicao, [BoxEntry(char="abc"[k], x1=a, y1=b, x2=c, y2=d,
                                             source="manual", confidence=1.0)
                                    for k, (a, b, c, d) in enumerate(CAIXAS)])


def _imagem(ctl, posicao):
    return np.asarray(ctl.fonte.pagina(posicao).convert("L"))


def _recortes(ctl, projeto, posicao):
    imagem = _imagem(ctl, posicao)
    return {b.gid: imagem[b.entry.y1:b.entry.y2, b.entry.x1:b.entry.x2]
            for b in projeto.carregar_modelo(posicao).boxes}


# ----------------------------------------------------------------------
# CA-12.11: girar
# ----------------------------------------------------------------------

def test_ca_12_11_girar_as_impares_leva_imagem_e_boxes(projeto, ctl):
    for i in range(10):
        _gravar(projeto, i)
    antes = {i: (_imagem(ctl, i), _recortes(ctl, projeto, i)) for i in range(10)}
    arquivos = {p.name: p.read_bytes() for p in (projeto.pasta / "paginas").glob("p*.json")}
    assert ctl.girar_paginas([0, 2, 4, 6, 8], 90)
    for i in range(10):
        imagem, recortes = antes[i]
        k = -1 if i % 2 == 0 else 0
        assert np.array_equal(_imagem(ctl, i), np.rot90(imagem, k=k)), i
        depois = _recortes(ctl, projeto, i)
        assert depois.keys() == recortes.keys()                       # os mesmos gids
        for gid, recorte in recortes.items():
            assert np.array_equal(depois[gid], np.rot90(recorte, k=k)), (i, gid)
    # só a sequência foi gravada: os arquivos das páginas são os de antes
    assert {p.name: p.read_bytes() for p in (projeto.pasta / "paginas").glob("p*.json")} \
        == arquivos


def test_ca_12_11_noventa_duas_vezes_e_cento_e_oitenta_e_o_ctrl_z_volta(projeto, ctl):
    _gravar(projeto, 3)
    imagem, recortes = _imagem(ctl, 3), _recortes(ctl, projeto, 3)
    ctl.girar_paginas([3], 90)
    ctl.girar_paginas([3], 90)
    assert projeto.sequencia.entrada_em(3).giro == 180
    assert np.array_equal(_imagem(ctl, 3), np.rot90(imagem, k=2))
    ctl.desfazer()
    ctl.desfazer()
    assert projeto.sequencia.entrada_em(3).giro == 0
    assert np.array_equal(_imagem(ctl, 3), imagem)
    assert {g: r.tobytes() for g, r in _recortes(ctl, projeto, 3).items()} == \
        {g: r.tobytes() for g, r in recortes.items()}


def test_ca_12_11_reabrir_sem_gravar_as_paginas_os_boxes_estao_no_lugar(projeto, ctl):
    """A queda depois de gravar a sequência e antes dos arquivos das páginas: a página é
    levada à geometria nova quando é lida (o arquivo dela diz a geometria de antes)."""
    _gravar(projeto, 1)
    recortes = _recortes(ctl, projeto, 1)
    ctl.girar_paginas([1], 270)
    projeto.fechar()
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    outro = _ligar(reaberto)
    depois = _recortes(outro, reaberto, 1)
    assert {g: np.rot90(r, k=1).tobytes() for g, r in recortes.items()} == \
        {g: r.tobytes() for g, r in depois.items()}
    bruto = json.loads((projeto.pasta / "paginas" / f"p{projeto.pid_da_pagina(1)}.json")
                       .read_text(encoding="utf-8"))
    assert bruto["geometria"] == [None, 0]               # o arquivo ainda na de antes


def test_a_pagina_com_boxes_guarda_o_angulo_em_que_foi_lida(tmp_path, pdf_de_60_paginas,  # noqa: F811
                                                         monkeypatch):
    medidas = iter([0.6, 9.9])                           # a segunda medida não pode acontecer
    monkeypatch.setattr(pg, "medir_inclinacao", lambda *_a, **_k: next(medidas))
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Angulo", pdf_de_60_paginas)
    ctl = _ligar(projeto)                                # mede a página 1: 0,6
    _gravar(projeto, 0)
    ctl.girar_paginas([0], 90)
    assert ctl.fonte.inclinacao(0) == 0.6
    gravado = json.loads((projeto.pasta / "inclinacoes.json").read_text(encoding="utf-8"))
    assert gravado[f"p{projeto.pid_da_pagina(0)}:inteira:90"] == 0.6


# ----------------------------------------------------------------------
# CA-12.12: cortar
# ----------------------------------------------------------------------

def test_ca_12_12_cortar_e_o_recorte_exato_e_o_glifo_de_fora_fica_guardado(projeto, ctl):
    _gravar(projeto, 2)
    imagem, recortes = _imagem(ctl, 2), _recortes(ctl, projeto, 2)
    altura, largura = imagem.shape
    gids = [b.gid for b in projeto.carregar_modelo(2).boxes]
    assert ctl.cortar_paginas([2], (0.03, 0.03, 0.5, 0.5))
    x0, y0 = round(0.03 * largura), round(0.03 * altura)
    x1, y1 = largura - round(0.5 * largura), altura - round(0.5 * altura)
    assert np.array_equal(_imagem(ctl, 2), imagem[y0:y1, x0:x1])
    modelo = projeto.carregar_modelo(2)
    dentro = {b.gid for b in modelo.boxes}
    assert dentro == set(gids[:2])                       # o terceiro saiu do quadro
    assert [b.gid for _lugar, b in modelo.fora] == [gids[2]]
    depois = _recortes(ctl, projeto, 2)
    for gid in dentro:
        assert np.array_equal(depois[gid], recortes[gid])  # os mesmos pixels
    ctl.desfazer()
    assert [b.gid for b in projeto.carregar_modelo(2).boxes] == gids   # na ordem de antes


def test_o_glifo_de_fora_volta_ao_tirar_o_corte_depois_de_gravar_e_reabrir(projeto, ctl):
    _gravar(projeto, 4)
    gids = [b.gid for b in projeto.carregar_modelo(4).boxes]
    ctl.cortar_paginas([4], (0, 0, 0.5, 0.5))
    projeto.salvar_pagina(4, projeto.carregar_pagina(4))   # gravada no quadro (o 3º fora)
    bruto = json.loads((projeto.pasta / "paginas" / f"p{projeto.pid_da_pagina(4)}.json")
                       .read_text(encoding="utf-8"))
    assert len(bruto["boxes"]) == 2 and len(bruto["fora"]) == 1
    projeto.fechar()
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    outro = _ligar(reaberto)
    assert outro.tirar_o_corte([4])
    assert [b.gid for b in reaberto.carregar_modelo(4).boxes] == gids


def test_cortar_uma_pagina_girada_corta_o_que_se_ve(projeto, ctl):
    ctl.girar_paginas([5], 90)
    vista = _imagem(ctl, 5)
    altura, largura = vista.shape
    ctl.cortar_paginas([5], (0, 0, 0.5, 0))              # a metade esquerda do que se vê
    assert np.array_equal(_imagem(ctl, 5), vista[:, :largura - round(0.5 * largura)])


def test_margens_que_esvaziam_a_pagina_sao_recusadas(projeto, ctl):
    assert not ctl.cortar_paginas([0], (0.6, 0, 0.5, 0))
    assert projeto.sequencia.entrada_em(0).quadro is None


def test_a_pagina_girada_ou_cortada_nao_usa_a_camada_nativa(projeto, ctl):
    ctl.girar_paginas([0], 180)
    assert not projeto.sequencia.entrada_em(0).do_livro_intacta


# ----------------------------------------------------------------------
# A revisão da rodada 3a
# ----------------------------------------------------------------------

def _pagina_com_areas():
    from abbychess.diagramas import DiagramaLido
    from abbychess.modelo import Pagina
    from abbychess.zonas import Zona

    return Pagina(pid=1, indice=0, tamanho=(600, 400),
                  zonas=[Zona("texto", 0, 0, 600, 100, id="z0"),
                         Zona("texto", 400, 200, 580, 380, id="z1")],
                  tabuleiros=[(350, 150, 550, 350)],
                  diagramas=[DiagramaLido(caixa=(350, 150, 550, 350), id="d0", conferido=True,
                                          titulo="Brancas jogam")])


def test_cortar_e_voltar_devolve_areas_tabuleiros_e_diagramas():
    from abbychess.modelo import reenquadrar

    pagina = _pagina_com_areas()
    antes = (list(pagina.zonas), list(pagina.tabuleiros), list(pagina.diagramas))
    reenquadrar(pagina, ((0, 0, 300, 400), 0), None)
    assert [(z.id, z.caixa) for z in pagina.zonas] == [("z0", (0, 0, 300, 100))]
    assert pagina.tabuleiros == [] and pagina.diagramas == []
    reenquadrar(pagina, (None, 0), None)
    assert (list(pagina.zonas), list(pagina.tabuleiros), list(pagina.diagramas)) == antes
    assert pagina.areas_fora == ()


def test_a_area_aparada_e_mexida_fica_como_o_usuario_a_deixou():
    from dataclasses import replace

    from abbychess.modelo import reenquadrar

    pagina = _pagina_com_areas()
    reenquadrar(pagina, ((0, 0, 300, 400), 0), None)
    pagina.zonas = [replace(pagina.zonas[0], y2=90)]          # o usuário a encolheu
    reenquadrar(pagina, (None, 0), None)
    assert [(z.id, z.caixa) for z in pagina.zonas][0] == ("z0", (0, 0, 300, 90))


def test_o_diagrama_que_volta_com_o_id_tomado_ganha_outro():
    from dataclasses import replace

    from abbychess.modelo import reenquadrar

    pagina = _pagina_com_areas()
    reenquadrar(pagina, ((0, 0, 300, 400), 0), None)
    novo = replace(_pagina_com_areas().diagramas[0], caixa=(10, 150, 200, 340), id="d0",
                   conferido=False)
    pagina.diagramas = [novo]                                  # um diagrama novo tomou o d0
    reenquadrar(pagina, (None, 0), None)
    # o de volta entra no lugar dele na lista (o primeiro), com outro id
    assert [(d.id, d.conferido) for d in pagina.diagramas] == [("d1", True), ("d0", False)]


def test_as_areas_fora_sobrevivem_a_gravar_e_reabrir(projeto, ctl):
    from abbychess.zonas import Zona

    _gravar(projeto, 6)
    projeto.salvar_zonas(6, [Zona("texto", 500, 850, 560, 960, id="z0")])
    ctl.cortar_paginas([6], (0, 0, 0.5, 0.5))
    projeto.salvar_pagina(6, projeto.carregar_pagina(6))
    projeto.fechar()
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    assert reaberto.carregar_modelo(6).zonas == []
    assert _ligar(reaberto).tirar_o_corte([6])
    assert [z.caixa for z in reaberto.carregar_modelo(6).zonas] == [(500, 850, 560, 960)]


@pytest.mark.parametrize("graus, angulo, esperado", [
    (90, 90, 0), (90, 0, 270), (270, 270, 0), (180, 90, 270)])
def test_girar_leva_o_angulo_do_texto(graus, angulo, esperado):
    """O texto que sobe (90) fica de pé quando a página gira 90° à direita."""
    from abbychess.modelo import Box, Pagina, reenquadrar

    entry = BoxEntry(char="a", x1=10, y1=10, x2=20, y2=40, angulo=angulo)
    pagina = Pagina(pid=1, indice=0, tamanho=(100, 200), boxes=[Box(gid=1, entry=entry)])
    reenquadrar(pagina, (None, graus), None)
    assert pagina.boxes[0].entry.angulo == esperado
    reenquadrar(pagina, (None, 0), None)
    assert pagina.boxes[0].entry.angulo == angulo


def test_a_posicao_repetida_gira_uma_vez_so(projeto, ctl):
    assert ctl.girar_paginas([3, 3], 90)
    assert projeto.sequencia.entrada_em(3).giro == 90


def test_tirar_o_corte_sem_corte_nao_muda_nada(projeto, ctl):
    assert not ctl.tirar_o_corte([0])
