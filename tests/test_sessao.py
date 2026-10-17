"""A sessão de edição do Documento, sem Qt (SPEC §6.3, as linhas do passo D1; §6.4).

Cada linha D1 da tabela de §6.3 numa página sintética (as palavras montadas pelo core, como
na janela): o 1 → 1 (CA-6.2), o glifo que sai, a letra que faltou (no meio, no começo e a
palavra nova), o espaço inserido (CA-6.3) e o apagado, o colar de várias linhas; o que é do
passo G recusa sem mudar nada; e as figurinas (CA-6.7).
"""

from __future__ import annotations

import pytest
from core.box_model import BoxEntry

from abbychess import sessao as ss
from abbychess import texto as tx
from abbychess.leitor import FONTE_MANUAL
from abbychess.modelo import Box, Pagina, gid_de


def _pagina(*linhas: str) -> Pagina:
    """Cada letra um box de 18 px (passo de 22 na palavra, 30 a mais entre palavras)."""
    boxes, n = [], 0
    for k, linha in enumerate(linhas):
        x, y = 20, 20 + 60 * k
        for palavra in linha.split(" "):
            for letra in palavra:
                boxes.append(Box(gid_de(1, n), BoxEntry(letra, x, y, x + 18, y + 30, 0.9, "net")))
                n += 1
                x += 22
            x += 30
    return Pagina(pid=1, indice=0, boxes=boxes, estado="reconhecida", proximo_n=n)


def _texto(pagina) -> str:
    return ss.texto_e_unidades(pagina)[0]


def _editar(pagina, de: str, para: str) -> ss.Plano:
    """Troca a primeira ocorrência de `de` (palavras inteiras) por `para`, como a vista faz:
    a sessão é a menor sequência de palavras que cobre o trecho."""
    texto, unidades = ss.texto_e_unidades(pagina)
    inicio = texto.index(de)
    a, b = ss.palavras_em(unidades, inicio, inicio + len(de))
    novo = texto[a:inicio] + para + texto[inicio + len(de):b]
    return ss.editar(pagina, unidades[a:b], novo)


def test_ca_6_2_trocar_o_1_por_l_corrige_um_box_sem_virtual():
    p = _pagina("vou conc1uir hoje")
    gid = p.boxes[7].gid                                  # o "1"
    plano = _editar(p, "conc1uir", "concluir")
    assert plano.corrigir == {gid: "l"} and not plano.virtuais and not plano.sair
    assert p.box(gid).entry.char == "l" and p.box(gid).entry.source == FONTE_MANUAL
    assert _texto(p) == "vou concluir hoje"
    assert all(b.revisado for b in p.boxes[3:11]) and not p.boxes[0].revisado


def test_ca_6_3_o_espaco_inserido_e_uma_quebra_sem_mexer_em_box():
    p = _pagina("ganhartempos")
    caixas = [b.entry.as_state() for b in p.boxes]
    plano = _editar(p, "ganhartempos", "ganhar tempos")
    assert plano.quebrar == {p.boxes[6].gid} and not plano.corrigir
    assert _texto(p) == "ganhar tempos"
    assert [b.entry.as_state() for b in p.boxes] == caixas


def test_o_espaco_apagado_junta_as_palavras():
    p = _pagina("gan har")
    _editar(p, "gan har", "ganhar")
    assert _texto(p) == "ganhar" and p.decisoes.juncoes == {(p.boxes[2].gid, p.boxes[3].gid)}


def test_apagar_o_espaco_de_uma_quebra_tira_a_quebra():
    p = _pagina("ganhartempos")
    _editar(p, "ganhartempos", "ganhar tempos")
    _editar(p, "ganhar tempos", "ganhartempos")
    assert _texto(p) == "ganhartempos" and not p.decisoes.quebras and not p.decisoes.juncoes


def test_o_glifo_apagado_sai_da_pagina():
    p = _pagina("casxa")
    x = p.boxes[3].gid
    plano = _editar(p, "casxa", "casa")
    assert plano.sair == {x} and x not in p.vivos and _texto(p) == "casa"
    assert "1 glifo(s) tirado(s)" in plano.estrutural()


@pytest.mark.parametrize("de, para", [("csa", "casa"), ("asa", "casa"), ("cas", "casa")])
def test_a_letra_que_faltou_vira_glifo_virtual(de, para):
    p = _pagina(f"a {de} b")
    plano = _editar(p, de, para)
    assert len(p.decisoes.virtuais) == 1 and _texto(p) == f"a {para} b"
    assert "1 glifo(s) virtual(is)" in plano.estrutural()


def test_varias_letras_seguidas_e_a_palavra_nova():
    p = _pagina("a casa")
    _editar(p, "a casa", "a bela casa")
    assert _texto(p) == "a bela casa" and len(p.decisoes.virtuais) == 4
    p = _pagina("casa", "longe")
    _editar(p, "longe", "muito longe")                    # no começo da linha
    assert _texto(p) == "casa\nmuito longe"


def test_trocar_e_apagar_letras_virtuais():
    p = _pagina("a csa")
    _editar(p, "csa", "casa")
    _editar(p, "casa", "cosa")                            # troca a letra virtual
    assert _texto(p) == "a cosa" and p.decisoes.virtuais[0].char == "o"
    _editar(p, "cosa", "csa")                             # e a apaga
    assert _texto(p) == "a csa" and not p.decisoes.virtuais


def test_colar_varias_linhas_vira_espacos():
    p = _pagina("ganhartempos")
    _editar(p, "ganhartempos", "ganhar\ntempos")
    assert _texto(p) == "ganhar tempos"


@pytest.mark.parametrize("de, para", [("rnar", "mar"), ("mar", "rnar")])
def test_o_que_e_do_passo_g_recusa_sem_mudar_nada(de, para):
    p = _pagina(de)
    antes = p.instantaneo()
    with pytest.raises(ss.Recusa, match="próxima versão"):
        _editar(p, de, para)
    assert [b.entry.as_state() for b in p.boxes] == [b.entry.as_state() for b in antes.boxes]
    assert p.decisoes == antes.decisoes


def test_sem_mudanca_so_revisa():
    p = _pagina("casa")
    plano = _editar(p, "casa", "casa")
    assert not plano.muda and all(b.revisado for b in p.boxes)
    assert all(b.entry.source == "net" for b in p.boxes)   # a fonte não muda (CA-6.9)


def test_o_glifo_nao_lido_recebe_a_letra():
    p = _pagina("ca?a")
    p.boxes[2] = Box(p.boxes[2].gid, BoxEntry("", 64, 20, 82, 50, 0.0, "none"))
    assert _texto(p) == f"ca{tx.NAO_LIDO}a"
    _editar(p, f"ca{tx.NAO_LIDO}a", "casa")
    assert _texto(p) == "casa" and p.boxes[2].entry.source == FONTE_MANUAL


@pytest.mark.parametrize("token, idioma, figurinha", [
    ("Cf3", "pt", "♘f3"), ("Nf3", "en", "♘f3"), ("14.Dxe5+", "pt", "14.♕xe5+"),
    ("e8=D", "pt", "e8=D"), ("Te8=D", "pt", "♖e8=♕"), ("Casa", "pt", "Casa"), ("Rf1", "en", "♖f1")])
def test_ca_6_7_figurinas_no_token_de_lance(token, idioma, figurinha):
    assert ss.figurinas(token, idioma) == figurinha


def test_ca_6_7_so_os_tokens_mudados_e_so_no_modo_figurinas():
    assert ss.com_figurinas("Cf3 Cf6", "Cf6 Cf8", "pt", "figurinas") == "♘f3 Cf6"
    assert ss.com_figurinas("Cf3", "Cf8", "pt", "letras") == "Cf3"


def test_alinhar_prefere_a_substituicao_e_a_esquerda():
    assert ss.alinhar("ab", "xb") == [(0, 0), (1, 1)]
    assert ss.alinhar("aa", "aaa") == [(None, 0), (0, 1), (1, 2)]


# ----------------------------------------------------------------------
# Os virtuais ficam onde o usuário os digitou (a revisão de código do D1)
# ----------------------------------------------------------------------

def test_o_virtual_cuja_ancora_sai_fica_no_lugar():
    p = _pagina("x ab", "cd")
    _editar(p, "ab", "abz")                               # o z depois do b
    _editar(p, "abz", "az")                               # e o b sai
    assert _texto(p) == "x az\ncd"
    p = _pagina("q bc")
    _editar(p, "bc", "abc")                               # o a antes do b
    _editar(p, "abc", "ac")
    assert _texto(p) == "q ac"


def test_inserir_antes_de_um_virtual_da_mesma_ancora():
    p = _pagina("ab")
    _editar(p, "ab", "axb")
    _editar(p, "axb", "ayxb")
    assert _texto(p) == "ayxb"
    p = _pagina("ab")
    _editar(p, "ab", "axyb")
    _editar(p, "axyb", "axzyb")
    assert _texto(p) == "axzyb"


def test_uma_letra_antes_do_virtual_que_comeca_a_palavra():
    p = _pagina("q bc")
    _editar(p, "bc", "abc")
    _editar(p, "q abc", "Q xabc")
    assert _texto(p) == "Q xabc"


def test_a_palavra_virtual_fica_quando_a_vizinha_sai():
    p = _pagina("a c")
    _editar(p, "a c", "a b c")                            # "b" é uma palavra virtual
    _editar(p, "a b", "b")
    assert _texto(p) == "b c"
    p = _pagina("casa", "ab", "fim")
    _editar(p, "ab", "abc")
    _editar(p, "abc", "c")                                # sobra só o virtual na linha
    assert _texto(p) == "casa c\nfim"                     # (uma linha só existe com boxes)


@pytest.mark.parametrize("pagina, com_virtual, para", [
    ("ab cd", "abx cd", "abxcd"),                         # juntar depois do virtual
    ("ab", "abx", "ab x"),                                # o virtual vira palavra
    ("ab", "axb", "ax b"),                                # partir depois do virtual
    ("a b", "a xb", "ax b")])                             # partir antes dele
def test_o_espaco_junto_de_um_virtual(pagina, com_virtual, para):
    p = _pagina(pagina)
    _editar(p, pagina, com_virtual)
    assert len(p.decisoes.virtuais) == 1
    _editar(p, com_virtual, para)
    assert _texto(p) == para


def test_uma_letra_no_meio_da_ligadura_e_do_passo_g():
    p = _pagina("afb")
    p.boxes[1] = Box(p.boxes[1].gid, BoxEntry("fi", 42, 20, 60, 50, 0.9, "net"))
    with pytest.raises(ss.Recusa, match="dividir um glifo"):
        _editar(p, "afib", "afxib")


def test_o_que_ninguem_tocou_fica_com_o_glifo_dele():
    p = _pagina("cassa")
    texto, unidades = ss.texto_e_unidades(p)
    segundo = p.boxes[3].gid
    ss.editar(p, unidades, "casa", fixos=[(0, 0), (1, 1), (2, 2), (4, 3)])   # o 2º s apagado
    assert _texto(p) == "casa" and segundo not in p.vivos and p.boxes[2].gid != segundo


def test_enter_nao_revisa_o_nao_lido():
    p = _pagina("ca?a")
    p.boxes[2] = Box(p.boxes[2].gid, BoxEntry("", 64, 20, 82, 50, 0.0, "none"))
    _editar(p, f"ca{tx.NAO_LIDO}a", f"ca{tx.NAO_LIDO}a")
    assert not p.boxes[2].revisado and p.boxes[0].revisado


def test_figurinas_com_pontuacao_e_o_token_igual_que_mudou_de_lugar():
    assert ss.figurinas("(Cf3)", "pt") == "(♘f3)" and ss.figurinas("Cf3,", "pt") == "♘f3,"
    assert ss.com_figurinas("Cf3 joga Cf3", "Cf3 joga xx", "pt", "figurinas") == "Cf3 joga ♘f3"


def test_gid_no_cursor_da_letra_nova():
    p = _pagina("csa")
    _texto_, unidades = ss.texto_e_unidades(p)
    assert ss.gid_no_cursor(unidades, "casa", 2) == ss.LETRA_NOVA
    assert ss.gid_no_cursor(unidades, "casa", 1) == p.boxes[0].gid
