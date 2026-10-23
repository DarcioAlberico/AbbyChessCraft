"""Endireitar à mão (SPEC §12.4, passo L, rodada 4): CA-12.14. O ângulo à mão vence o medido e
fica na entrada da sequência (por `pid`); a leitura da página se desfaz, menos os glifos
marcados à mão, que giram em volta do centro; o Ctrl+Z devolve o ângulo e a página."""

from __future__ import annotations

import numpy as np
import pytest
from core.box_model import BoxEntry
from PIL import Image

from abbychess import pagina as pg
from abbychess.controlador import ControladorDePagina
from abbychess.diagramas import DiagramaLido
from abbychess.leitor import LeitorDoLivro
from abbychess.modelo import (GLIFOS_MARCADOS, Box, Decisoes, Pagina, endireitar)
from abbychess.projeto import ProjetoDeLivro
from abbychess.zonas import Zona

from tests.test_visor import pdf_de_60_paginas  # noqa: F401

QUADRADO = (400, 100, 440, 140)


@pytest.fixture
def projeto(tmp_path, pdf_de_60_paginas, monkeypatch):  # noqa: F811
    monkeypatch.setattr(pg, "medir_inclinacao", lambda *_a, **_k: 0.0)
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Endireitar", pdf_de_60_paginas)
    matriz = np.full((800, 600), 255, np.uint8)
    x1, y1, x2, y2 = QUADRADO
    matriz[y1:y2, x1:x2] = 0
    imagem = tmp_path / "quadrado.png"
    Image.fromarray(matriz).save(imagem)
    projeto.gravar_sequencia(projeto.sequencia.inserir(projeto.inserir_arquivo(imagem), 0))
    return projeto


@pytest.fixture
def ctl(projeto):
    controlador = ControladorDePagina()
    controlador.ligar(projeto, pg.fonte_do_projeto(projeto),
                      LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    controlador.ir_para(0)
    return controlador


def _gravar(projeto):
    x1, y1, x2, y2 = QUADRADO
    projeto.salvar_pagina(0, [
        BoxEntry(char="q", x1=x1, y1=y1, x2=x2, y2=y2, source="manual", confidence=1.0),
        BoxEntry(char="z", x1=40, y1=600, x2=60, y2=630, source="livro", confidence=0.9)])


def _centro_da_tinta(ctl):
    matriz = np.asarray(ctl.fonte.pagina(0).convert("L"))
    ys, xs = np.nonzero(matriz < 128)
    return xs.mean(), ys.mean()


def test_ca_12_14_o_angulo_a_mao_vence_o_medido_e_o_glifo_marcado_gira(projeto, ctl):
    _gravar(projeto)
    pid = projeto.pid_da_pagina(0)
    assert ctl.endireitar_paginas([0], 5.0)
    assert projeto.sequencia.entrada_de(pid).angulo == 5.0
    assert ctl.fonte.inclinacao(0) == 5.0
    modelo = projeto.carregar_modelo(0)
    assert modelo.estado == GLIFOS_MARCADOS
    assert [b.entry.char for b in modelo.boxes] == ["q"]        # o lido pelo livro saiu
    b = modelo.boxes[0].entry
    cx, cy = _centro_da_tinta(ctl)
    assert abs((b.x1 + b.x2) / 2 - cx) <= 1.5 and abs((b.y1 + b.y2) / 2 - cy) <= 1.5
    assert (b.x2 - b.x1, b.y2 - b.y1) == (40, 40)


def test_ca_12_14_o_ctrl_z_devolve_o_angulo_e_os_boxes(projeto, ctl):
    _gravar(projeto)
    antes = [(b.gid, b.entry.char, b.entry.x1, b.entry.y1)
             for b in projeto.carregar_modelo(0).boxes]
    ctl.endireitar_paginas([0], -3.5)
    ctl.desfazer()
    assert projeto.sequencia.entrada_em(0).angulo is None
    assert [(b.gid, b.entry.char, b.entry.x1, b.entry.y1)
            for b in projeto.carregar_modelo(0).boxes] == antes
    ctl.refazer()
    assert projeto.sequencia.entrada_em(0).angulo == -3.5


def test_o_angulo_a_mao_fica_depois_de_reabrir(projeto, ctl):
    _gravar(projeto)
    ctl.endireitar_paginas([0], 2.0)
    projeto.fechar()
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    assert reaberto.sequencia.entrada_em(0).angulo == 2.0
    assert [b.entry.char for b in reaberto.carregar_modelo(0).boxes] == ["q"]


def test_voltar_ao_medido_e_o_limite(projeto, ctl):
    ctl.endireitar_paginas([3], 1.0)
    assert not ctl.endireitar_paginas([3], 25.0)
    assert ctl.endireitar_paginas([3], None)
    assert projeto.sequencia.entrada_em(3).angulo is None
    assert not ctl.endireitar_paginas([3], None)                # nada muda


def test_a_pagina_sem_glifos_so_muda_o_angulo(projeto, ctl):
    assert ctl.endireitar_paginas([5, 6], 1.5)
    assert projeto.carregar_modelo(5) is None


def test_endireitar_tira_o_que_nao_foi_marcado_a_mao():
    revisado = Box(gid=1 << 20 | 1, entry=BoxEntry(char="r", x1=100, y1=100, x2=110, y2=120,
                                                   source="livro"), revisado=True)
    manual = Box(gid=1 << 20, entry=BoxEntry(char="m", x1=50, y1=50, x2=60, y2=70,
                                             source="manual"))
    lido = Box(gid=1 << 20 | 2, entry=BoxEntry(char="l", x1=150, y1=50, x2=160, y2=70,
                                               source="livro"))
    pagina = Pagina(pid=1, indice=0, tamanho=(200, 200), proximo_n=3,
                    boxes=[manual, revisado, lido],
                    zonas=[Zona("texto", 10, 10, 190, 90, id="z0"),
                           Zona("texto", 10, 100, 190, 190, id="z1", automatica=True)],
                    tabuleiros=[(20, 120, 80, 180)],
                    diagramas=[DiagramaLido(caixa=(20, 120, 80, 180), id="d0")],
                    decisoes=Decisoes(quebras=frozenset({lido.gid, revisado.gid})))
    nova = endireitar(pagina, 0.0, (200, 200), lambda b: b.entry.source == "manual"
                      or b.revisado)
    assert [b.gid for b in nova.boxes] == [manual.gid, revisado.gid]
    assert [z.id for z in nova.zonas] == ["z0"]
    assert nova.tabuleiros == [] and nova.diagramas == []
    assert nova.decisoes.quebras == {revisado.gid}
    assert nova.proximo_n == 3 and pagina.boxes[2] is lido     # a de entrada não mudou
