"""A ordem das áreas (Ordenar, CA-5.5) vale para o diagrama e para a exportação, e não só para os
blocos de texto do Documento (limitação do passo F)."""

from __future__ import annotations

from core.box_model import BoxEntry
from PIL import Image

from abbychess import montagem as mo
from abbychess import texto as tx
from abbychess import zonas as zn
from tests.ajudantes import _lido

CAIXA = (100, 200, 500, 600)


def _linha(texto: str, y: int) -> list:
    return [BoxEntry(c, 100 + 22 * k, y, 120 + 22 * k, y + 30, 0.9, "net")
            for k, c in enumerate(texto) if c != " "]


def _pagina(alto=None, diagrama=None, baixo=None, *, com_diagrama=True):
    entries = _linha("alto", 100) + _linha("baixo", 700)
    zonas = [zn.Zona(zn.TEXTO, 0, 0, 800, 190, id="alto", ordem=alto),
             zn.Zona(zn.DIAGRAMA, 90, 190, 510, 610, id="tabuleiro", ordem=diagrama),
             zn.Zona(zn.TEXTO, 0, 620, 800, 900, id="baixo", ordem=baixo)]
    return tx.pagina_avulsa(entries, [_lido(caixa=CAIXA)] if com_diagrama else [], zonas)


def _documento(pagina) -> list:
    doc = tx.montar(pagina)
    return [b.diagrama_id or tx.texto_do_bloco(doc, b) for b in doc.blocos]


def _exportada(pagina) -> list:
    entries, estrutura = mo.Estrutura.da_pagina(pagina)
    extraida = mo.pagina_extraida(0, entries, [CAIXA], Image.new("RGB", (800, 1000)),
                                  pagina.diagramas, estrutura, desenhar_diagramas=False)
    return ["figura" if isinstance(b, mo.Figura) else b.texto for b in extraida.blocos]


def test_sem_ordem_tudo_fica_pela_leitura():
    pagina = _pagina()
    assert _documento(pagina) == ["alto", "d0", "baixo"]
    assert _exportada(pagina) == ["alto", "figura", "baixo"]


def test_o_diagrama_segue_o_ordenar_no_documento():
    assert _documento(_pagina(alto=2, diagrama=1, baixo=0)) == ["baixo", "d0", "alto"]
    assert _documento(_pagina(alto=1, diagrama=0, baixo=2)) == ["d0", "alto", "baixo"]


def test_a_exportacao_segue_o_ordenar():
    assert _exportada(_pagina(alto=2, diagrama=1, baixo=0)) == ["baixo", "figura", "alto"]
    assert _exportada(_pagina(alto=1, diagrama=0, baixo=2)) == ["figura", "alto", "baixo"]


def test_a_exportacao_e_o_documento_leem_a_mesma_ordem():
    for ordem in ((0, 1, 2), (2, 1, 0), (1, 2, 0), (2, 0, 1)):
        pagina = _pagina(*ordem)
        lidos = ["figura" if x == "d0" else x for x in _documento(pagina)]
        assert _exportada(pagina) == lidos


def test_duas_areas_de_texto_juntas_nao_viram_um_paragrafo_so_quando_ordenadas():
    """Linhas seguidas, sem vão: sem ordem, um parágrafo; com ordem, cada área no lugar dela."""
    entries = _linha("primeira", 100) + _linha("segunda", 140)
    def com_ordem(a, b):
        return tx.pagina_avulsa(entries, [], [zn.Zona(zn.TEXTO, 0, 90, 800, 135, id="a", ordem=a),
                                              zn.Zona(zn.TEXTO, 0, 136, 800, 300, id="b", ordem=b)])

    def exportada(pagina):
        entradas, estrutura = mo.Estrutura.da_pagina(pagina)
        return [p.texto for p in mo.pagina_extraida(0, entradas, estrutura=estrutura).blocos]

    assert exportada(com_ordem(None, None)) == ["primeira segunda"]
    assert exportada(com_ordem(1, 0)) == ["segunda", "primeira"]


def test_o_que_nao_tem_area_ordenada_fica_no_lugar():
    """Só o diagrama e o alto têm ordem: trocam entre si, e o de baixo não se mexe."""
    assert _documento(_pagina(alto=1, diagrama=0)) == ["d0", "alto", "baixo"]
    assert _exportada(_pagina(alto=1, diagrama=0)) == ["figura", "alto", "baixo"]


def test_a_area_de_diagrama_sem_tabuleiro_nao_atrapalha():
    assert _documento(_pagina(alto=1, diagrama=2, baixo=0, com_diagrama=False)) == ["baixo", "alto"]
