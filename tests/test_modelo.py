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

from tests.ajudantes import _lido


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


def test_bloco_de_legenda_carrega_a_referencia_do_diagrama():
    p = _pagina(*_linha("Diagrama 1"))
    p.zonas = [Zona("texto", 0, 0, 400, 45, id="z0", funcao="legenda",
                    diagrama_id="d0")]

    [bloco] = tx.montar(p).blocos

    assert bloco.funcao == "legenda" and bloco.referencia_id == "d0"


def test_paragrafo_e_estilos_sao_decisoes_persistidas_no_documento():
    from abbychess import edicao as ed

    p = _pagina(*_linha("casa velha"))
    primeiro = p.boxes[0].gid
    ed.paragrafo(p, primeiro)
    ed.estilizar(p, [primeiro], "negrito")
    doc = tx.montar(p)
    assert primeiro in p.decisoes.paragrafo_antes
    assert doc.estilos[primeiro].negrito
    ed.estilizar(p, [primeiro], "negrito")
    assert not p.box(primeiro).estilo.negrito


def test_modos_impresso_e_san():
    p = _pagina(_e(0, "♘"), _e(22, "e"), _e(44, "4"), _e(66, "✝"))
    doc = tx.montar(p)
    assert tx.texto(doc, modo=tx.IMPRESSO) == "♘e4+"
    assert tx.texto(doc, modo=tx.SAN) == "Ne4+"
    with pytest.raises(ValueError):
        tx.texto(doc, modo="outro")


def test_ligadura_do_box_sai_desfeita_nos_dois_modos():
    p = _pagina(_e(0, "ﬁ"), _e(22, "m"))
    doc = tx.montar(p)
    assert tx.texto(doc, modo=tx.IMPRESSO) == "fim"
    assert tx.texto(doc, modo=tx.SAN) == "fim"


def test_o_virtual_entra_logo_depois_da_ancora_dele():
    """D1: a âncora diz o lugar exato. O segundo depois do mesmo glifo entra logo depois
    dele (antes do primeiro: foi digitado ali); a sequência se encadeia um no outro."""
    p = _pagina(*_linha("abc"))
    a = p.boxes[0].gid
    x = p.alocar()
    p.decisoes = Decisoes(virtuais=(GlifoVirtual(x, "X", a), GlifoVirtual(p.alocar(), "Y", a),
                                    GlifoVirtual(p.alocar(), "Z", x),
                                    GlifoVirtual(p.alocar(), "1", None)))
    assert tx.texto(tx.montar(p)) == "1aYXZbc"


def test_apagar_o_virtual_passa_os_ancorados_nele_ao_lugar_dele():
    """Os virtuais ancorados no que sai (depois dele, ou antes dele e sem outra âncora)
    ficam no lugar dele, com a palavra nova dele; apagar um box como virtual é recusado."""
    from abbychess import edicao as ed

    p = _pagina(*_linha("abc"))
    a, b = p.boxes[0].gid, p.boxes[1].gid
    _, x = ed.virtual(p, "X", a, palavra_nova=True)
    _, y = ed.virtual(p, "Y", x)
    _, z = ed.virtual(p, "Z", None, antes_de=x)
    assert tx.texto(tx.montar(p)) == "abc ZXY"
    ed.apagar_virtual(p, x)
    assert tx.texto(tx.montar(p)) == "abc Z Y"
    assert {v.gid: (v.depois_de, v.antes_de, v.palavra_nova) for v in p.decisoes.virtuais} == {
        y: (a, None, True), z: (a, None, True)}
    with pytest.raises(ValueError, match="não é virtual"):
        ed.apagar_virtual(p, b)


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


def test_procedencia_aceita_o_callback_no_meio_de_registrar():
    """A coleta de lixo pode matar um `BoxEntry` registrado (e chamar o callback, que pega a
    trava) enquanto a mesma thread está dentro de `registrar`; com trava simples, travava."""
    import gc

    from core.box_model import BoxEntry

    morto = BoxEntry("a", 0, 0, 1, 1)
    procedencia.registrar(morto, "padroes/a.png")
    vivo = BoxEntry("b", 0, 0, 1, 1)
    with procedencia._trava:                  # como se registrar estivesse no meio
        del morto
        gc.collect()                          # o callback roda aqui, na mesma thread
        procedencia.registrar(vivo, "padroes/b.png")
    assert procedencia.amostra_de(vivo) == "padroes/b.png"


# ----------------------------------------------------------------------
# As regras que a mutação achou sem teste (Q9, CA-Q-M1)
# ----------------------------------------------------------------------

def _blocos_de(pagina) -> list:
    """O documento da página: o texto de cada bloco, e o id de cada diagrama."""
    doc = tx.montar(pagina)
    return [b.diagrama_id or tx.texto_do_bloco(doc, b) for b in doc.blocos]


def test_os_lances_colados_partem_ate_numa_palavra_de_quatro_glifos():
    """"e52." (a resposta e o número do lance seguinte, colados): quatro glifos já bastam."""
    assert tx.texto(tx.montar(_pagina(*_linha("1.e4 e52. Cf3")))) == "1.e4 e5 2. Cf3"


def test_os_diagramas_no_mesmo_lugar_vao_de_cima_para_baixo_e_da_esquerda_para_a_direita():
    direita, baixo, esquerda = (_lido(caixa=c) for c in ((220, 0, 420, 200), (0, 220, 150, 420),
                                                         (0, 0, 200, 200)))
    pagina = tx.pagina_avulsa(_linha("Embaixo", y=450), [direita, baixo, esquerda])  # d0, d1, d2
    assert _blocos_de(pagina) == ["d2", "d0", "d1", "Embaixo"]
    # Os que o documento não tem são numerados depois dos dele, na mesma ordem.
    sem_diagramas = tx.montar(_pagina(*_linha("nada")))
    assert tx.numeros_dos_diagramas(sem_diagramas, pagina.diagramas) == {"d2": 1, "d0": 2, "d1": 3}


def test_o_diagrama_entra_na_coluna_dele():
    linhas = []
    for k, y in enumerate((10, 50, 90, 210, 250, 290, 330)):
        linhas += _linha(f"esquerda longa {k}", y=y) + _linha(f"direita {k}", y=y, x0=700)
    pagina = tx.pagina_avulsa(linhas, [_lido(caixa=(100, 130, 300, 200)),
                                       _lido(caixa=(650, 130, 750, 200))])
    esquerda = [f"esquerda longa {k}" for k in range(7)]
    direita = [f"direita {k}" for k in range(7)]
    assert _blocos_de(pagina) == ["\n".join(esquerda[:3]), "d0",
                                  "\n".join(esquerda[3:] + direita[:3]), "d1",
                                  "\n".join(direita[3:])]


def test_a_linha_ate_uma_altura_de_glifo_acima_do_diagrama_vem_depois_dele():
    """A linha que começa até uma altura de glifo (30 px) acima do tabuleiro está na altura
    dele: o diagrama entra antes dela; um pixel mais acima, depois."""
    for topo, esperado in ((70, ["Antes.", "d0", "logo acima\ndepois"]),
                           (69, ["Antes.\nlogo acima", "d0", "depois"])):
        pagina = tx.pagina_avulsa(_linha("Antes.") + _linha("logo acima", y=topo)
                                  + _linha("depois", y=600), [_lido(caixa=(0, 100, 400, 500))])
        assert _blocos_de(pagina) == esperado


def test_o_diagrama_ao_lado_do_paragrafo_espera_o_fim_da_frase():
    """O parágrafo que contorna o tabuleiro não é partido no meio: o diagrama entra depois da
    primeira linha ao lado dele que segue um fim de frase (nunca antes da primeira da
    página), colada a ele de um lado ou do outro; a linha que começa no pé dele não está ao
    lado."""
    from dataclasses import replace

    ao_lado = (_linha("que segue longe", y=100) + _linha("e acaba.", y=140)
               + _linha("Outra frase", y=180))
    contornado = ["Começo sem\nque segue longe\ne acaba.", "d0", "Outra frase"]
    d = _lido(caixa=(400, 100, 800, 500))
    assert _blocos_de(tx.pagina_avulsa(_linha("Começo sem") + ao_lado, [d])) == contornado
    assert _blocos_de(tx.pagina_avulsa(_linha("Título.") + ao_lado, [d])) == [
        "Título.", "d0", "que segue longe\ne acaba.\nOutra frase"]
    no_pe = _linha("no pé", y=500) + _linha("mais", y=540)
    assert _blocos_de(tx.pagina_avulsa(_linha("Começo sem") + no_pe, [d])) == [
        "Começo sem", "d0", "no pé\nmais"]
    x1 = max(e.x2 for e in ao_lado)
    colado = _lido(caixa=(x1, 100, x1 + 400, 500))
    assert _blocos_de(tx.pagina_avulsa(_linha("Começo sem") + ao_lado, [colado])) == contornado
    a_direita = [replace(e, x1=e.x1 + 290, x2=e.x2 + 290) for e in ao_lado]
    assert min(e.x1 for e in a_direita) == 300
    a_esquerda = _lido(caixa=(10, 100, 300, 500))
    assert _blocos_de(tx.pagina_avulsa(_linha("Começo sem") + a_direita, [a_esquerda])) == contornado


def test_o_virtual_ancorado_num_mais_novo_ou_num_ciclo():
    """A âncora virtual entra antes de quem se ancora nela, mesmo vindo depois na ordem das
    decisões (`ancorar` muda a âncora, não a ordem); com as duas âncoras, vale o depois_de;
    no ciclo, um vai para o começo da primeira linha e ninguém se perde; o sem âncora, com
    palavra nova, é uma palavra no começo."""
    from abbychess import edicao as ed

    p = _pagina(*_linha("abc"))
    a, c = p.boxes[0].gid, p.boxes[2].gid
    _, z = ed.virtual(p, "Z", a)
    _, x = ed.virtual(p, "X", a)
    ed.ancorar(p, {z: (None, x, False)})               # antes do X, que é mais novo
    assert tx.texto(tx.montar(p)) == "aZXbc"
    ed.ancorar(p, {z: (x, c, False)})                  # depois do X e antes do c
    assert tx.texto(tx.montar(p)) == "aXZbc"

    p = _pagina(*_linha("abc"))
    _, x = ed.virtual(p, "X", p.boxes[0].gid)
    _, y = ed.virtual(p, "Y", x)
    ed.ancorar(p, {x: (y, None, False)})               # X depois do Y, Y depois do X
    assert tx.texto(tx.montar(p)) == "YXabc"

    p = _pagina(*_linha("abc de"))
    ed.virtual(p, "Z", None, palavra_nova=True)
    assert tx.texto(tx.montar(p)) == "Z abc de"


def test_a_area_sem_ordem_fica_no_lugar():
    p = _pagina(*_linha("titulo"), *_linha("corpo", y=60), *_linha("resto", y=160))
    p.zonas = [Zona("texto", 0, 0, 400, 45, id="z0", funcao="titulo", ordem=1),
               Zona("texto", 0, 50, 400, 150, id="z1", ordem=0),
               Zona("texto", 0, 155, 400, 250, id="z2")]
    assert [(b.zona_id, b.funcao) for b in tx.montar(p).blocos] == [
        ("z1", "texto"), ("z0", "titulo"), ("z2", "texto")]


def test_o_texto_tem_uma_linha_por_diagrama():
    pagina = tx.pagina_avulsa(_linha("Observe:") + _linha("1.e4 e5", y=520),
                              [_lido(caixa=(0, 100, 400, 500))])
    doc = tx.montar(pagina)
    assert tx.texto(doc, pagina.diagramas) == (
        "Observe:\n" + pagina.diagramas[0].linha_de_texto(1) + "\n1.e4 e5")
    assert tx.texto(doc) == "Observe:\n1.e4 e5"          # sem os diagramas, só as linhas


def test_as_palavras_da_vista_tem_o_glifo_nao_lido():
    """A vista do Documento (e a ordem da camada exportada) conta o glifo que ninguém leu."""
    p = _pagina(*_linha("ab"), _e(54, ""), *_linha("c", x0=76))
    assert tx.palavras_dos_gids(p) == [[b.gid for b in p.boxes]]


def _com_lacunas(*partes, y=3300):
    """Uma linha de boxes de largura 16 (a p. 15 do Aagaard): cada parte é `(texto, lacuna
    antes)`, e dentro da parte as letras ficam a 2 px umas das outras."""
    boxes, x = [], 200
    for texto, antes in partes:
        x += antes
        for c in texto:
            boxes.append(BoxEntry(c, x, y, x + 16, y + 25, 1.0, "manual"))
            x += 18
        x -= 2
    return boxes


def test_a_correcao_que_muda_as_palavras_do_core_monta_as_linhas_de_novo():
    """As linhas guardadas só valem para a correção que não muda as palavras do core: o
    algarismo que vira pontuação desfaz o número que o core remontou ("15" -> "1 §"), a
    letra que vira "f" ganha o espaço do gancho dele ("oithe" -> "of the"), e a vírgula
    depois do "f" que era "a," (as duas numa caixa só) também ("of," -> "of a,")."""
    from abbychess import edicao as ed

    p = _pagina(*_linha("Nota 1 5"))
    assert tx.texto(tx.montar(p)) == "Nota 15"
    ed.corrigir(p, p.boxes[-1].gid, "§")
    assert tx.texto(tx.montar(p)) == "Nota 1 §"

    # Três "f" com o gancho sobre a letra seguinte: o gancho do livro vale.
    gancho = (("af", 20), ("ter", -3), ("f", 20), ("or", -3), ("f", 20), ("ar", -3))
    p = tx.pagina_avulsa(_com_lacunas(("Depth", 0), ("oi", 20), ("the", 6), *gancho))
    assert tx.texto(tx.montar(p)) == "Depth oithe after for far"
    ed.corrigir(p, p.boxes[6].gid, "f")
    assert tx.texto(tx.montar(p)) == "Depth of the after for far"
    p = tx.pagina_avulsa(_com_lacunas(("Depth", 0), ("of", 20), (",", 6), *gancho))
    assert tx.texto(tx.montar(p)) == "Depth of, after for far"
    ed.corrigir(p, p.boxes[7].gid, "a,")
    assert tx.texto(tx.montar(p)) == "Depth of a, after for far"


def test_a_pagina_so_com_um_virtual_e_um_diagrama_monta():
    """Nenhum glifo lido, uma letra digitada sem âncora e um diagrama (achado na mutação do
    texto): a linha só de virtuais não tem lugar na página, e o diagrama vai para o fim, como
    sem linha nenhuma na altura dele. Levantava IndexError."""
    from abbychess import edicao as ed

    p = Pagina(pid=3, indice=0)
    ed.virtual(p, "Z", None)
    p.diagramas = [_lido(caixa=(0, 100, 400, 500))]
    documento = tx.montar(p)
    assert [b.funcao for b in documento.blocos] == ["texto", "diagrama"]
    assert tx.texto(documento).startswith("Z")


# As da mutação do modelo: o JSON, as decisões, a reconciliação e a sobreposição.

def _box(x1, y1, x2, y2, char="a"):
    return BoxEntry(char, x1, y1, x2, y2, 0.9, "net")


def test_o_n_fora_do_gid_diz_o_maior_que_cabe():
    with pytest.raises(ValueError, match=r"^n=1048576 fora de 0\.\.1048575$"):
        gid_de(1, 1 << 20)


def test_o_estilo_do_json_antigo_e_nao_medido_e_o_de_agora_volta_inteiro():
    """O JSON de antes do passo I (nada, ou [0, 0, 0]) é "não medido"; o de agora guarda o
    reto medido no quarto item, e o itálico, o reto e o sublinhado voltam como foram."""
    assert Estilo.de_json(None) == Estilo.de_json([]) == Estilo.de_json([0, 0, 0]) == Estilo()
    for estilo in (Estilo(italico=True), Estilo(negrito=False, italico=False),
                   Estilo(negrito=True, italico=False), Estilo(sublinhado=True)):
        assert Estilo.de_json(estilo.para_json()) == estilo


def test_o_virtual_antes_de_um_glifo_volta_pelo_json():
    """O `antes_de` vai num sexto item, só quando há: o JSON de antes dele tem cinco."""
    d = Decisoes(virtuais=(GlifoVirtual(6, "x", None, antes_de=2), GlifoVirtual(7, "y", 2)))
    assert d.para_json()["virtuais"] == [[6, "x", None, 0, None, 2], [7, "y", 2, 0, None]]
    assert Decisoes.de_json(d.para_json()) == d


def test_o_virtual_antes_de_um_glifo_vai_ao_primeiro_sucessor_ou_cai_para_o_comeco():
    d = Decisoes(virtuais=(GlifoVirtual(50, "x", None, antes_de=1),))
    novo, caidas = d.reescrever({1: [10, 11]})
    assert novo.virtuais[0].antes_de == 10 and caidas == []
    novo, caidas = d.reescrever({1: []})
    assert novo.virtuais[0].antes_de is None
    assert caidas == ["glifo virtual 'x' antes do glifo 1 (o glifo saiu; o virtual foi para o "
                      "começo da página)"]


def test_so_descartar_ou_so_marcar_um_glifo_ja_e_mudanca():
    p = _pagina(_e(0), _e(30))
    _, dif = reconciliar(p.boxes, p.entries()[:1], p.alocar)
    assert dif.removidos == {p.boxes[1].gid} and not dif.vazia
    _, dif = reconciliar(p.boxes, p.entries() + [_e(60)], p.alocar)
    assert len(dif.novos) == 1 and not dif.vazia


def test_o_mesmo_objeto_e_o_mesmo_glifo_mesmo_com_outro_na_mesma_caixa():
    """Dois glifos na mesma caixa, trocados de lugar na lista: cada um fica com o seu gid
    (pelo objeto), e não com o do primeiro que tem a caixa."""
    p = _pagina(_e(0, "f"), _e(0, "i"))
    f, i = p.boxes
    novos, dif = reconciliar(p.boxes, [i.entry, f.entry], p.alocar)
    assert [(b.gid, b.entry.char) for b in novos] == [(i.gid, "i"), (f.gid, "f")] and dif.vazia


def test_a_copia_depois_do_mesmo_objeto_ainda_volta_pela_caixa():
    p = _pagina(_e(0), _e(30))
    depois = [p.boxes[0].entry, copy.deepcopy(p.boxes[1].entry)]
    novos, dif = reconciliar(p.boxes, depois, p.alocar)
    assert [b.gid for b in novos] == [b.gid for b in p.boxes] and dif.vazia


def test_o_estilo_medido_de_novo_vale_para_o_mesmo_glifo():
    p = _pagina(_e(0), _e(30))
    entries = p.entries()
    novos, dif = reconciliar(p.boxes, entries, p.alocar,
                             estilo_de=lambda e: Estilo(negrito=True) if e is entries[1] else None)
    assert [b.estilo for b in novos] == [Estilo(), Estilo(negrito=True)]
    assert dif.mudados == {p.boxes[1].gid}


def test_o_glifo_novo_guarda_a_amostra_que_o_leu():
    p = _pagina(_e(0))
    nova = _e(30)
    procedencia.registrar(nova, "lower_b/p.png")
    novos, dif = reconciliar(p.boxes, [p.boxes[0].entry, nova], p.alocar, procedencia.amostra_de)
    assert [b.amostra for b in novos] == [None, "lower_b/p.png"] and dif.novos == [novos[1]]


def _relida(antes, depois):
    """A releitura da página inteira (o F5, §4.6): os gids de antes, os de depois e os que
    saíram."""
    p = _pagina(*antes)
    novos, dif = reconciliar(p.boxes, depois, p.alocar, iou_minimo=modelo.IOU_DA_RELEITURA)
    return [b.gid for b in p.boxes], [b.gid for b in novos], dif.removidos


def test_na_releitura_o_glifo_continua_com_ao_menos_0_6_de_intersecao_sobre_a_uniao():
    [g], [novo], saidos = _relida([_box(100, 100, 110, 110)], [_box(100, 100, 110, 106)])
    assert novo == g and not saidos                              # 60 / 100
    [g], [novo], saidos = _relida([_box(100, 100, 110, 110)], [_box(100, 100, 110, 105)])
    assert novo != g and saidos == {g}                           # 50 / 100


def test_na_releitura_o_traco_de_um_pixel_continua_o_mesmo():
    for antes, depois in ((_box(100, 100, 120, 101, "-"), _box(100, 100, 121, 101, "-")),
                          (_box(100, 100, 101, 130, "|"), _box(100, 100, 101, 131, "|"))):
        [g], [novo], _ = _relida([antes], [depois])
        assert novo == g


def test_na_releitura_o_glifo_vai_so_para_a_caixa_mais_parecida():
    """Duas caixas novas sobre um glifo (IoU 0,9 e 0,7): ele fica com a de 0,9, em qualquer
    ordem, e a outra nasce."""
    parecida, menos = _box(100, 100, 110, 109), _box(100, 100, 110, 107, "b")
    [g], gids, saidos = _relida([_box(100, 100, 110, 110)], [parecida, menos])
    assert gids[0] == g and gids[1] != g and not saidos
    [g], gids, _ = _relida([_box(100, 100, 110, 110)], [menos, parecida])
    assert gids[1] == g and gids[0] != g


def _sucessores(antes, depois) -> dict:
    """Os sucessores de cada glifo que saiu, pelo caractere."""
    p = _pagina(*antes)
    novos, dif = reconciliar(p.boxes, depois, p.alocar)
    char = {b.gid: b.entry.char for b in [*p.boxes, *novos]}
    return {char[g]: [char[n] for n in ns] for g, ns in dif.sucessores.items()}


def test_o_sucessor_cobre_mais_da_metade_da_area_de_um_dos_dois():
    largo, estreito = _box(0, 10, 40, 40, "v"), _box(0, 10, 20, 40, "v")
    assert _sucessores([largo], [_box(29, 10, 49, 40, "n")]) == {"v": ["n"]}     # 11/20 do novo
    assert _sucessores([largo], [_box(30, 10, 50, 40, "n")]) == {"v": []}        # a metade não
    assert _sucessores([estreito], [_box(9, 10, 49, 40, "n")]) == {"v": ["n"]}   # 11/20 do velho
    assert _sucessores([_box(0, 10, 20, 40, "v")], [_box(0, 100, 20, 130, "n")]) == {"v": []}


def test_o_pedaco_de_um_pixel_tambem_e_sucessor():
    """O traço, a barra e o pingo de um pixel que saem de um glifo, e o pingo que entra
    num."""
    for fino in (_box(0, 39, 20, 40, "_"), _box(19, 10, 20, 40, "|"), _box(5, 20, 6, 21, ".")):
        assert _sucessores([_box(0, 10, 20, 40, "v")], [fino]) == {"v": [fino.char]}
    assert _sucessores([_box(5, 20, 6, 21, ".")], [_box(0, 10, 20, 40, "v")]) == {".": ["v"]}
