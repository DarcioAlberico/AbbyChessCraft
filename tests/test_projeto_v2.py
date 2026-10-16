"""O projeto no modelo v2 pelo caminho da janela de hoje (o adaptador do passo 1b).

A janela ainda edita listas de `BoxEntry` com `abbychess.pagina`; a gravação reconcilia
com o modelo. Aqui: o gid sobrevive às gravações e às edições, a procedência da leitura
chega ao `Box`, o padrão ensinado leva o gid do glifo de origem no nome, e o estado da
página segue §4.4.
"""

from __future__ import annotations

import json

import pytest

from abbychess import livro, pagina as pg
from abbychess.leitor import FONTE_LIVRO, LeitorDoLivro
from abbychess.modelo import EM_REVISAO, GLIFOS_MARCADOS, RECONHECIDA, pid_de
from abbychess.projeto import ARQUIVO_DO_LIVRO, ProjetoDeLivro

from tests.test_treino_por_livro import _pagina_sintetica


@pytest.fixture
def lido(tmp_path):
    fonte = _pagina_sintetica(tmp_path / "pagina.png")
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Modelo v2", fonte)
    leitor = LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)
    imagem = pg.fonte_do_projeto(projeto).pagina(0)
    livro.reconhecer_paginas(projeto, pg.fonte_do_projeto(projeto), leitor, [0])
    return projeto, leitor, imagem


def test_pagina_nova_ganha_pid_estavel_e_gids_dela(lido):
    projeto, _, _ = lido
    modelo = projeto.carregar_modelo(0)
    assert modelo.pid == 0 and projeto.dados.proximo_pid == 1
    assert {pid_de(b.gid) for b in modelo.boxes} == {0}
    assert projeto._arquivo_da_pagina(0).name == "p0.json"
    assert projeto.resumo_do_livro()[0]["pid"] == 0
    gids = [b.gid for b in modelo.boxes]
    projeto.salvar_pagina(0, projeto.carregar_pagina(0))
    assert [b.gid for b in ProjetoDeLivro.abrir(projeto.pasta).carregar_modelo(0).boxes] == gids


def test_dividir_pela_janela_aposenta_o_gid_e_da_gids_novos(lido):
    projeto, leitor, imagem = lido
    boxes = projeto.carregar_pagina(0)
    antes = [b.gid for b in projeto.carregar_modelo(0).boxes]
    pg.juntar(imagem, boxes, 0, 1, leitor)
    projeto.salvar_pagina(0, boxes)
    depois = projeto.carregar_modelo(0)
    assert antes[0] not in depois.vivos and antes[1] not in depois.vivos
    assert depois.boxes[0].gid not in antes and depois.boxes[0].gid in depois.vivos
    assert not (depois.vivos & depois.aposentados)


def test_estados_pela_gravacao(lido, tmp_path):
    projeto, leitor, imagem = lido
    assert projeto.estado_da_pagina(0) == RECONHECIDA
    projeto.salvar_pagina(0, projeto.carregar_pagina(0))               # nada mudou
    assert projeto.estado_da_pagina(0) == RECONHECIDA
    boxes = projeto.carregar_pagina(0)
    pg.confirmar(boxes, 0, "z")
    projeto.salvar_pagina(0, boxes)                                    # primeira edição
    assert projeto.estado_da_pagina(0) == EM_REVISAO
    livro.reconhecer_paginas(projeto, pg.fonte_do_projeto(projeto), leitor, [0], refazer=True)
    assert projeto.estado_da_pagina(0) == EM_REVISAO                  # F5 não volta atrás
    marcados = pg.segmentar(imagem)[:2]
    projeto.salvar_pagina(1, marcados, reconhecida=False)
    assert projeto.estado_da_pagina(1) == GLIFOS_MARCADOS and projeto.paginas_lidas() == [0]


def test_procedencia_e_gid_no_padrao(lido):
    projeto, leitor, imagem = lido
    boxes = projeto.carregar_pagina(0)
    gid_ensinado = projeto.gid_do_box(0, boxes, 0)
    pg.ensinar(imagem, boxes, 0, "a", leitor, projeto, 0)              # propaga pela página
    projeto.salvar_pagina(0, boxes)
    padroes = [p.name for p in projeto.pasta_de_padroes.rglob("*.png")]
    assert len(padroes) == 1 and f"_g{gid_ensinado:x}" in padroes[0]
    modelo = projeto.carregar_modelo(0)
    do_livro = [b for b in modelo.boxes if b.entry.source == FONTE_LIVRO]
    assert do_livro and all(b.amostra and b.amostra.endswith(".png") for b in do_livro)
    assert modelo.box(gid_ensinado).amostra is None                   # é a origem, não cópia
    # A procedência vai para o disco e volta.
    bruto = json.loads(projeto._arquivo_da_pagina(0).read_text(encoding="utf-8"))
    assert any(b[2] for b in bruto["boxes"])
    reaberto = ProjetoDeLivro.abrir(projeto.pasta).carregar_modelo(0)
    assert [b.amostra for b in reaberto.boxes] == [b.amostra for b in modelo.boxes]


def test_livro_json_tem_o_pid_e_e_igual_ao_recalculado(lido):
    projeto, leitor, imagem = lido
    projeto.salvar_zonas(4, [])                                          # nada a gravar
    assert 4 not in projeto.resumo_do_livro()
    projeto.salvar_pagina(2, pg.segmentar(imagem)[:1], reconhecida=False)
    gravado = json.loads((projeto.pasta / ARQUIVO_DO_LIVRO).read_text(encoding="utf-8"))
    assert gravado == projeto.recalcular_livro()
    assert {r["pid"] for r in projeto.resumo_do_livro().values()} == {0, 1}
