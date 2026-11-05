"""O sublinhado (Ctrl+U) sai na exportação, como o negrito e o itálico (limitação do passo G)."""

from __future__ import annotations

from dataclasses import replace

from core.box_model import BoxEntry

from abbychess import epub, escritor_docx, marcacao
from abbychess import montagem as mo
from abbychess import texto as tx
from abbychess.modelo import Estilo


def _pagina(palavra_sublinhada: bool = True):
    """"um dois", com "dois" sublinhado."""
    entries = [BoxEntry(c, 10 + 22 * k, 10, 30 + 22 * k, 40, 0.9, "net")
               for k, c in enumerate("um dois") if c != " "]
    pagina = tx.pagina_avulsa(entries)
    if palavra_sublinhada:
        pagina.boxes = [replace(b, estilo=Estilo(sublinhado=True)) if k >= 2 else b
                        for k, b in enumerate(pagina.boxes)]
    return pagina


def _paragrafo(pagina):
    entries, estrutura = mo.Estrutura.da_pagina(pagina)
    return mo.pagina_extraida(0, entries, estrutura=estrutura).blocos[0]


def test_o_paragrafo_exportado_sabe_o_trecho_sublinhado():
    paragrafo = _paragrafo(_pagina())
    assert paragrafo.texto == "um dois"
    assert paragrafo.sublinhado == [(3, 7)]
    assert _paragrafo(_pagina(False)).sublinhado == []


def test_os_trechos_marcados_separam_o_sublinhado():
    pedacos = marcacao.trechos_marcados("um dois", "", (), (), (), (), sublinhado=[(3, 7)])
    assert [(t, m.sublinhado) for t, m in pedacos] == [("um ", False), ("dois", True)]


def test_o_epub_escreve_o_sublinhado():
    assert epub._com_estilo("x", False, False, False, False, True) == "<u>x</u>"
    assert epub._com_estilo("x", True, False, False, False, True) == "<strong><u>x</u></strong>"
    assert epub._com_estilo("x", False, False, False, False) == "x"


def test_o_docx_escreve_o_sublinhado():
    import docx

    documento = docx.Document()
    saida = documento.add_paragraph()
    escritor_docx._texto_com_estilo(saida, _paragrafo(_pagina()), "", "", [])
    assert [(r.text, r.underline) for r in saida.runs] == [("um ", None), ("dois", True)]


def test_o_sublinhado_acompanha_o_paragrafo_que_volta_para_a_pagina_anterior():
    antes = mo.ParagrafoExportado("fim de um começo", sublinhado=[(0, 3)])
    primeiro = mo.ParagrafoExportado("começo", sublinhado=[(0, 6)])
    mo._levar_os_trechos(antes, primeiro)
    assert antes.sublinhado == [(0, 3), (10, 16)]
