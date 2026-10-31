"""O que fica de uma página lida (SPEC-qualidade Q-A2, CA-Q-A2 parte 2): o F5 e o lote, com a
mesma leitura sobre a mesma página, deixam a mesma página."""
from __future__ import annotations

from core.box_model import BoxEntry

from abbychess import pagina as pg
from abbychess import projeto as pj
from abbychess import servidor_de_leitura as sl
from abbychess.controlador import ControladorDePagina
from abbychess.leitor import LeitorDoLivro
from abbychess.lote import CondutorDoLote
from abbychess.projeto import ProjetoDeLivro
from tests.ajudantes import ExecutorManual, pdf_sintetico

#: Duas linhas de texto (uma com lance) e um tabuleiro: o bastante para as áreas automáticas,
#: a legenda e o diagrama.
TEXTO = [("1.", 40, 10), ("e4", 70, 10), ("e5", 100, 10), ("D", 300, 232), ("i", 320, 232),
         ("a", 330, 232), ("g", 340, 232), ("r", 350, 232), ("a", 360, 232)]
TABULEIRO = (300, 20, 500, 220)          # a página sintética tem 900 × 260


def _lida() -> sl.PaginaLida:
    from abbychess.diagramas import DiagramaLido

    boxes = [BoxEntry(c, x, y, x + 9 * len(c), y + 14, source="net", confidence=0.95)
             for c, x, y in TEXTO]
    return sl.PaginaLida(boxes, [None] * len(boxes), [TABULEIRO], None,
                         [DiagramaLido(TABULEIRO)], negritos=[False] * len(boxes))


def _controlador(tmp_path, nome):
    projeto = ProjetoDeLivro.criar(tmp_path / nome, "Livro", pdf_sintetico(tmp_path / nome))
    executor = ExecutorManual()
    ctl = ControladorDePagina(executar=executor)
    ctl.ligar(projeto, pg.fonte_do_projeto(projeto),
              LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    ctl.ir_para(0)
    while executor.fila:                        # a imagem da página aberta
        fim = executor.comecar()
        if fim is not None:
            fim()
    return projeto, ctl


def test_o_f5_e_o_lote_deixam_a_mesma_pagina(tmp_path):
    (tmp_path / "f5").mkdir()
    (tmp_path / "lote").mkdir()
    projeto_f5, f5 = _controlador(tmp_path, "f5")
    projeto_lote, ctl_lote = _controlador(tmp_path, "lote")
    assert f5.imagem is not None

    trabalho, pronto = f5.leitura._preparar_reconhecer(0)
    pronto(_lida())
    CondutorDoLote(ctl_lote, [0], refazer=False)._gravar(0, _lida())

    pela_f5, pelo_lote = projeto_f5.carregar_modelo(0), projeto_lote.carregar_modelo(0)
    assert pela_f5.zonas and pela_f5.diagramas         # o caso cobre as áreas e o diagrama
    assert pj._comparavel(pela_f5) == pj._comparavel(pelo_lote)
