"""Reconhecer de novo sem perder decisões (SPEC §4.6, CA-4.8).

O F5 numa página já reconhecida mantém os glifos `manual` e `revisado`, passa as decisões
aos glifos novos pela sobreposição e é uma transação do desfazer. (O lote com "refazer" e o
"Voltar ao estado antes do lote" estão em `tests/test_servidor.py`.)
"""

from __future__ import annotations

from dataclasses import replace

from abbychess import zonas as zn
from abbychess.leitor import FONTE_MANUAL
from abbychess.modelo import GlifoVirtual

from tests.janela_util import boxes
from tests.test_janela import _esperar, app, janela  # noqa: F401


def test_ca_4_8_o_f5_mantem_correcoes_quebras_virtual_e_funcao_da_area(app, janela):  # noqa: F811
    p = janela.pagina
    janela.reconhecer()
    _esperar(app, janela)
    gids = list(p.gids)
    assert len(gids) >= 12
    corrigidos = gids[:10]
    for n, g in enumerate(corrigidos):                     # 10 correções manuais
        p.escolher(g)
        p.corrigir("ABCDEFGHIJ"[n])
        _esperar(app, janela)
    revisado = gids[11]
    p.modelo.boxes = [replace(b, revisado=True) if b.gid == revisado else b for b in p.modelo.boxes]
    virtual = GlifoVirtual(p.modelo.alocar(), "x", depois_de=gids[2])
    p.modelo.decisoes = replace(p.modelo.decisoes, quebras=frozenset({gids[4], gids[7]}),
                                virtuais=(virtual,))
    largura, altura = janela.pagina.imagem.size
    p.modelo.zonas = [zn.Zona("texto", 0, 0, largura, altura, id="z0", funcao="titulo")]
    antes = p.modelo.instantaneo()

    janela.reconhecer()                                    # o F5 de novo
    _esperar(app, janela)
    depois = {b.gid: b for b in p.modelo.boxes}
    for n, g in enumerate(corrigidos):
        assert depois[g].entry.char == "ABCDEFGHIJ"[n] and depois[g].entry.source == FONTE_MANUAL
    assert depois[revisado].revisado
    assert p.modelo.decisoes.quebras == {gids[4], gids[7]}
    assert p.modelo.decisoes.virtuais == (virtual,)
    assert [z.funcao for z in p.modelo.zonas] == ["titulo"]

    p.desfazer()                                           # o F5 é uma transação
    assert [b.entry.as_state() for b in p.modelo.boxes] == [b.entry.as_state() for b in antes.boxes]
    assert p.modelo.decisoes == antes.decisoes
    assert len(boxes(janela)) == len(antes.boxes)


def test_o_glifo_que_mudou_um_pouco_de_caixa_continua_o_mesmo_no_f5(app, janela):  # noqa: F811
    """§4.6: a releitura casa o glifo pela sobreposição (IoU ≥ 0,6), e não só pela caixa
    igual: a decisão dele fica no mesmo gid."""
    p = janela.pagina
    janela.reconhecer()
    _esperar(app, janela)
    alvo = next(b for b in p.modelo.boxes if b.entry.source != FONTE_MANUAL)
    torto = replace(alvo, entry=replace(alvo.entry, x2=alvo.entry.x2 + 2))   # 2 px a mais
    p.modelo.boxes = [torto if b.gid == alvo.gid else b for b in p.modelo.boxes]
    p.modelo.decisoes = replace(p.modelo.decisoes, quebras=frozenset({alvo.gid}))
    janela.reconhecer()
    _esperar(app, janela)
    assert alvo.gid in p.gids                            # o mesmo gid, com a caixa de agora
    assert p.box(alvo.gid).x2 == alvo.entry.x2
    assert p.modelo.decisoes.quebras == {alvo.gid}


def test_a_decisao_que_nao_segue_os_glifos_relidos_vai_para_resultados(app, janela):  # noqa: F811
    p = janela.pagina
    janela.reconhecer()
    _esperar(app, janela)
    alvo = p.modelo.boxes[0]
    p.modelo.decisoes = replace(p.modelo.decisoes, quebras=frozenset({alvo.gid}))
    largura, altura = janela.pagina.imagem.size
    e = alvo.entry                                       # uma área "ignorar" sobre o glifo
    p.modelo.zonas = [zn.Zona("texto", 0, 0, largura, altura, id="z0"),
                      zn.Zona("ignorar", e.x1 - 2, e.y1 - 2, e.x2 + 2, e.y2 + 2, id="z1")]
    resultados = []
    p.eventos.ligar("resultado", lambda titulo, texto: resultados.append(texto))
    janela.reconhecer()
    _esperar(app, janela)
    assert alvo.gid not in p.gids
    assert resultados and "decisões que não puderam seguir" in resultados[0]
    assert any("Reconhecer a página" == a.titulo for a in janela.avisos.itens)
