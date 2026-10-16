"""O modelo v2 (passo 1b): gid, decisões, reconciliação, estados, documento e procedência."""

from __future__ import annotations

import copy

import pytest
from core.box_model import BoxEntry

from abbychess import modelo, procedencia
from abbychess import texto as tx
from abbychess.modelo import (EM_REVISAO, GLIFOS_MARCADOS, NAO_RECONHECIDA, RECONHECIDA,
                              VERIFICADA, Box, Decisoes, Estilo, GlifoVirtual, Pagina, gid_de,
                              n_de, pid_de, proximo_estado, reconciliar)
from abbychess.zonas import Zona


def _e(x, char="a", y=10, largura=20):
    return BoxEntry(char, x, y, x + largura, y + 30, 0.9, "net")


def _pagina(*entries, pid=3) -> Pagina:
    return Pagina(pid=pid, indice=0, boxes=[Box(gid_de(pid, n), e) for n, e in enumerate(entries)],
                  estado=RECONHECIDA, proximo_n=len(entries))


# ----------------------------------------------------------------------
# gid
# ----------------------------------------------------------------------

def test_gid_junta_pid_e_n():
    g = gid_de(5, 123)
    assert (pid_de(g), n_de(g)) == (5, 123) and g == (5 << 20) | 123
    with pytest.raises(ValueError):
        gid_de(1, 1 << 20)


def test_alocar_nunca_reaproveita():
    p = _pagina(_e(0), _e(30))
    novos = [p.alocar() for _ in range(3)]
    assert novos == [gid_de(3, 2), gid_de(3, 3), gid_de(3, 4)] and p.proximo_n == 5


# ----------------------------------------------------------------------
# Decisões
# ----------------------------------------------------------------------

def test_reescrever_leva_antes_ao_primeiro_e_depois_ao_ultimo_sucessor():
    d = Decisoes(quebras=frozenset({1}), paragrafo_antes=frozenset({1}),
                 hifen_de_quebra=frozenset({1}), juncoes=frozenset({(1, 9)}),
                 virtuais=(GlifoVirtual(50, "x", 1),))
    novo, caidas = d.reescrever({1: [10, 11]})
    assert novo.quebras == {10} and novo.paragrafo_antes == {10}
    assert novo.hifen_de_quebra == {11}
    assert novo.juncoes == {(11, 9)}
    assert novo.virtuais[0].depois_de == 11 and caidas == []
    # O lado de chegada de uma junção vai ao primeiro sucessor.
    novo, _ = Decisoes(juncoes=frozenset({(8, 1)})).reescrever({1: [10, 11]})
    assert novo.juncoes == {(8, 10)}


def test_decisao_de_glifo_que_saiu_sem_sucessor_cai_e_e_dita():
    d = Decisoes(quebras=frozenset({1, 2}), juncoes=frozenset({(1, 2)}),
                 virtuais=(GlifoVirtual(50, "x", 1),))
    novo, caidas = d.reescrever({1: []})
    assert novo.quebras == {2} and novo.juncoes == frozenset()
    assert novo.virtuais[0].depois_de is None          # foi para o começo da linha
    assert len(caidas) == 3 and all("saiu" in c for c in caidas)


def test_juncao_que_vira_um_glifo_so_some():
    d = Decisoes(juncoes=frozenset({(1, 2)}))
    novo, _ = d.reescrever({1: [7], 2: [7]})               # os dois se juntaram
    assert novo.juncoes == frozenset()


def test_decisoes_e_box_vao_e_voltam_pelo_json():
    d = Decisoes(quebras=frozenset({1}), juncoes=frozenset({(2, 3)}),
                 paragrafo_antes=frozenset({4}), hifen_de_quebra=frozenset({5}),
                 virtuais=(GlifoVirtual(6, "é", 2, True, "z0"), GlifoVirtual(7, "x", None)))
    assert Decisoes.de_json(d.para_json()) == d
    b = Box(9, _e(0), "lower_a/p.png", Estilo(negrito=True), revisado=True)
    volta = Box.de_json(b.para_json())
    assert (volta.gid, volta.amostra, volta.estilo, volta.revisado) == (9, "lower_a/p.png",
                                                                        Estilo(True), True)
    assert volta.entry.as_state() == b.entry.as_state()


# ----------------------------------------------------------------------
# Estado (§4.4)
# ----------------------------------------------------------------------

@pytest.mark.parametrize("estado, evento, depois", [
    (NAO_RECONHECIDA, "marcar", GLIFOS_MARCADOS), (NAO_RECONHECIDA, "reconhecer", RECONHECIDA),
    (GLIFOS_MARCADOS, "reconhecer", RECONHECIDA), (RECONHECIDA, "editar", EM_REVISAO),
    (EM_REVISAO, "verificar", VERIFICADA), (VERIFICADA, "editar", EM_REVISAO),
    (VERIFICADA, "esquecer_padrao", EM_REVISAO), (EM_REVISAO, "reconhecer", EM_REVISAO),
    (VERIFICADA, "reconhecer", EM_REVISAO), (RECONHECIDA, "reconhecer", RECONHECIDA),
    (NAO_RECONHECIDA, "editar", NAO_RECONHECIDA), (EM_REVISAO, "esquecer_padrao", EM_REVISAO),
])
def test_maquina_de_estados(estado, evento, depois):
    assert proximo_estado(estado, evento) == depois


def test_estado_ou_evento_desconhecido_e_erro():
    with pytest.raises(ValueError):
        proximo_estado("perdida", "editar")
    with pytest.raises(ValueError):
        proximo_estado(RECONHECIDA, "apagar")


# ----------------------------------------------------------------------
# Reconciliar (o adaptador da janela)
# ----------------------------------------------------------------------

def test_reconciliar_mesmo_objeto_mantem_o_gid_e_ve_a_mudanca_pela_foto():
    p = _pagina(_e(0), _e(30))
    foto = {b.gid: modelo.foto(b.entry) for b in p.boxes}
    entries = p.entries()
    entries[1].char = "z"                                   # a janela muda no lugar
    novos, dif = reconciliar(p.boxes, entries, p.alocar, estados=foto)
    assert [b.gid for b in novos] == [b.gid for b in p.boxes]
    assert dif.mudados == {p.boxes[1].gid} and not dif.novos and not dif.removidos


def test_reconciliar_copia_do_desfazer_volta_pela_caixa():
    p = _pagina(_e(0), _e(30))
    copias = copy.deepcopy(p.entries())
    novos, dif = reconciliar(p.boxes, copias, p.alocar)
    assert [b.gid for b in novos] == [b.gid for b in p.boxes] and dif.vazia


def test_reconciliar_dividir_juntar_e_descartar_dao_os_sucessores():
    a, b, c = _e(0, largura=40), _e(60), _e(100)
    p = _pagina(a, b, c)
    ga, gb, gc = (x.gid for x in p.boxes)
    metade1, metade2 = _e(0), _e(20)                       # a dividido em dois
    junto = BoxEntry("", 60, 10, 120, 40)                   # b e c juntos
    novos, dif = reconciliar(p.boxes, [metade1, metade2, junto], p.alocar)
    n1, n2, nj = (x.gid for x in novos)
    assert dif.sucessores == {ga: [n1, n2], gb: [nj], gc: [nj]}
    novos, dif = reconciliar(novos, [metade1, metade2], p.alocar)
    assert dif.sucessores == {nj: []}                       # descartado: sem sucessor


def test_reconciliar_guarda_a_amostra_de_quem_nao_mudou_e_tira_a_de_quem_mudou():
    p = _pagina(_e(0), _e(30))
    p.boxes = [Box(b.gid, b.entry, "lower_a/x.png") for b in p.boxes]
    foto = {b.gid: modelo.foto(b.entry) for b in p.boxes}
    entries = p.entries()
    entries[1].char, entries[1].source = "q", "manual"
    novos, _ = reconciliar(p.boxes, entries, p.alocar, procedencia.amostra_de, foto)
    assert [b.amostra for b in novos] == ["lower_a/x.png", None]


def test_procedencia_vale_so_para_o_mesmo_objeto():
    e = _e(0)
    procedencia.registrar(e, "lower_a/y.png")
    assert procedencia.amostra_de(e) == "lower_a/y.png"
    assert procedencia.amostra_de(copy.deepcopy(e)) is None
    procedencia.registrar(e, None)
    assert procedencia.amostra_de(e) == procedencia.NENHUMA


# ----------------------------------------------------------------------
# montar() e o texto (§4.2)
# ----------------------------------------------------------------------

def _linha(texto: str, y: int = 10, x0: int = 10):
    """Um glifo por caractere, 20 px cada, com 14 px de vão nos espaços."""
    entries, x = [], x0
    for c in texto:
        if c == " ":
            x += 14
            continue
        entries.append(_e(x, c, y=y))
        x += 22
    return entries


def test_montar_sem_decisoes_e_o_texto_de_hoje():
    p = _pagina(*_linha("abc de"), *_linha("fg", y=60))
    assert tx.texto(tx.montar(p), modo=tx.SAN) == "abc de\nfg"


def test_quebra_juncao_e_virtuais():
    p = _pagina(*_linha("abc de"))
    g = [b.gid for b in p.boxes]
    p.decisoes = Decisoes(quebras=frozenset({g[1]}), juncoes=frozenset({(g[2], g[3])}),
                          virtuais=(GlifoVirtual(p.alocar(), "X", g[4]),
                                    GlifoVirtual(p.alocar(), "Y", g[0], palavra_nova=True),
                                    GlifoVirtual(p.alocar(), "Z", None)))
    assert tx.texto(tx.montar(p)) == "Za Y bcdeX"


def test_paragrafo_antes_e_areas_fazem_blocos_com_funcao_e_ordem():
    p = _pagina(*_linha("titulo"), *_linha("corpo", y=60), *_linha("mais", y=110))
    p.zonas = [Zona("texto", 0, 0, 400, 45, id="z0", funcao="titulo", ordem=1),
               Zona("texto", 0, 50, 400, 150, id="z1", ordem=0)]
    doc = tx.montar(p)
    assert [(b.zona_id, b.funcao) for b in doc.blocos] == [("z1", "texto"), ("z0", "titulo")]
    terceira = next(b.gid for b in p.boxes if b.entry.y1 == 110)
    p.zonas = []
    p.decisoes = Decisoes(paragrafo_antes=frozenset({terceira}))
    assert [len(b.linhas) for b in tx.montar(p).blocos] == [2, 1]


def test_modos_impresso_e_san():
    p = _pagina(_e(0, "♘"), _e(22, "e"), _e(44, "4"), _e(66, "✝"))
    doc = tx.montar(p)
    assert tx.texto(doc, modo=tx.IMPRESSO) == "♘e4+"
    assert tx.texto(doc, modo=tx.SAN) == "Ne4+"
    with pytest.raises(ValueError):
        tx.texto(doc, modo="outro")


def test_virtuais_no_mesmo_glifo_ficam_na_ordem_em_que_foram_digitados():
    p = _pagina(*_linha("abc"))
    a = p.boxes[0].gid
    p.decisoes = Decisoes(virtuais=(GlifoVirtual(p.alocar(), "X", a), GlifoVirtual(p.alocar(), "Y", a),
                                    GlifoVirtual(p.alocar(), "1", None),
                                    GlifoVirtual(p.alocar(), "2", None)))
    assert tx.texto(tx.montar(p)) == "12aXYbc"


def test_quebrar_desfaz_a_juncao_que_termina_no_glifo():
    from abbychess import edicao as ed

    p = _pagina(*_linha("ab cd"))
    g = [b.gid for b in p.boxes]
    ed.juntar_palavras(p, g[1], g[2])
    assert tx.texto(tx.montar(p)) == "abcd"
    ed.quebrar(p, g[2])
    assert tx.texto(tx.montar(p)) == "ab cd"
    assert not (p.decisoes.quebras & {b for _, b in p.decisoes.juncoes})


def test_fundir_glifos_nao_deixa_quebra_e_juncao_na_mesma_fronteira():
    """juntar_palavras(b, c), quebrar(d) e depois juntar os glifos c e d num só."""
    from abbychess import edicao as ed

    p = _pagina(*_linha("ab cd ef"))
    a, b, c, d = (x.gid for x in p.boxes[:4])
    ed.juntar_palavras(p, b, c)
    ed.quebrar(p, d)
    assert tx.texto(tx.montar(p)) == "abc d ef"
    novo, caidas = p.decisoes.reescrever({c: [99], d: [99]})
    assert not (novo.quebras & {y for _, y in novo.juncoes})
    assert (b, 99) in novo.juncoes and 99 not in novo.quebras
    assert any("fundido" in x for x in caidas)


def test_paragrafo_antes_de_um_glifo_do_meio_da_linha_vale_para_a_linha():
    p = _pagina(*_linha("um"), *_linha("dois tres", y=60))
    meio = next(b.gid for b in p.boxes if b.entry.char == "t")
    p.decisoes = Decisoes(paragrafo_antes=frozenset({meio}))
    assert [len(b.linhas) for b in tx.montar(p).blocos] == [1, 1]
