"""A sessão de edição do Documento, sem Qt (SPEC §6.3 e §6.4).

Cada linha D1 da tabela de §6.3 numa página sintética (as palavras montadas pelo core, como
na janela): o 1 → 1 (CA-6.2), o glifo que sai, a letra que faltou (no meio, no começo e a
palavra nova), o espaço inserido (CA-6.3) e o apagado, o colar de várias linhas; o que é do
as operações estruturais do passo G; e as figurinhas (CA-6.7).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from core.box_model import BoxEntry

from abbychess import sessao as ss
from abbychess import texto as tx
from abbychess.leitor import FONTE_MANUAL
from abbychess.modelo import Box, Pagina, gid_de
from tests.ajudantes import _editar, _pagina  # noqa: E402,F401,F811


def _texto(pagina) -> str:
    return ss.texto_e_unidades(pagina)[0]


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
    assert plano.estrutural() == "casxa → casa: 1 glifo tirado · Ctrl+Z desfaz"


@pytest.mark.parametrize("de, para", [("csa", "casa"), ("asa", "casa"), ("cas", "casa")])
def test_a_letra_que_faltou_vira_glifo_virtual(de, para):
    p = _pagina(f"a {de} b")
    plano = _editar(p, de, para)
    assert len(p.decisoes.virtuais) == 1 and _texto(p) == f"a {para} b"
    assert ": 1 glifo virtual · Ctrl+Z desfaz" in plano.estrutural()


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


@pytest.mark.parametrize(("de", "para", "boxes"), [("rnar", "mar", 3), ("mar", "rnar", 3)])
def test_ca_6_4_junta_ou_divide_os_boxes(de, para, boxes):
    p = _pagina(de)
    plano = _editar(p, de, para)
    assert _texto(p) == para and len(p.boxes) == boxes
    assert plano.juntar_boxes if len(de) > len(para) else plano.dividir_boxes
    estrutural = plano.estrutural()
    assert "glifos juntados" in estrutural if len(de) > len(para) else "dividido" in estrutural


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
    ("e8=D", "pt", "e8=D"), ("Te8=D", "pt", "♖e8=♕"), ("Casa", "pt", "Casa"), ("Rf1", "en", "♖f1"),
    ("Cf3⯹", "pt", "♘f3⯹"), ("Dxe5+⇄", "pt", "♕xe5+⇄"), ("Bb5⨀", "en", "♗b5⨀")])
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
    plano = _editar(p, "abc", "c")                        # sobra só o virtual na linha
    assert _texto(p) == "casa c\nfim"                     # (uma linha só existe com boxes)
    assert "a linha ficou sem glifos" in plano.estrutural()


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


def test_uma_letra_no_meio_da_ligadura_divide_ou_cria_caixa_multicaractere():
    p = _pagina("afb")
    p.boxes[1] = Box(p.boxes[1].gid, BoxEntry("fi", 42, 20, 60, 50, 0.9, "net"))
    plano = _editar(p, "afib", "afxib")
    assert _texto(p) == "afxib" and plano.dividir_boxes


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


@pytest.mark.parametrize("de, para, onde, letra", [
    ("ganhaxtempos", "ganhar tempos", 5, "r"), ("conc1uir", "concl uir", 4, "l"),
    ("casx", "casa ", 3, "a")])
def test_trocar_a_letra_e_partir_corrige_o_glifo_sem_tirar_o_box(de, para, onde, letra):
    p = _pagina(de)
    gid = p.boxes[onde].gid
    plano = _editar(p, de, para)
    assert plano.corrigir == {gid: letra} and not plano.sair and not p.decisoes.virtuais
    assert _texto(p) == para.strip()


def test_apagar_o_hifen_de_fim_de_linha_remove_o_box_e_mantem_a_linha_fisica():
    p = _pagina("exem-", "plo")
    hifen = p.boxes[4].gid
    plano = _editar(p, "exem-\nplo", "exemplo")
    assert hifen in plano.sair and hifen not in p.vivos
    assert _texto(p) == "exem\nplo"


def test_apagar_a_quebra_de_linha_avisa_que_ela_fica():
    p = _pagina("casa", "velha")
    plano = _editar(p, "casa\nvelha", "casavelha")
    assert _texto(p) == "casa\nvelha" and "a quebra de linha fica" in plano.estrutural()


def test_o_modo_como_o_livro_olha_as_figurinas_da_pagina():
    assert ss.modo_da_pagina("livro", "Cf3 e5") == "letras"
    assert ss.modo_da_pagina("livro", ["♘", "f", "3"]) == "figurinas"
    assert ss.modo_da_pagina("letras", "♘") == "letras"


def test_colar_a_pagina_inteira_alinha_pelos_trechos_iguais():
    """A revisão de produto do D1 (m7): sem fixos, um texto longo se ancora nos trechos
    longos iguais; só as letras trocadas viram trocas."""
    import random

    r = random.Random(1)
    original = " ".join("".join(r.choice("abcdefgh") for _ in range(r.randint(2, 8)))
                        for _ in range(150))
    novo = list(original)
    for k in r.sample([i for i, c in enumerate(original) if c != " "], 10):
        novo[k] = "x"
    novo = "".join(novo)
    pares = ss.alinhar(original, novo)
    trocas = [(i, j) for i, j in pares if i is not None and j is not None and original[i] != novo[j]]
    assert len(trocas) == 10 and all(i == j for i, j in pares)


# ----------------------------------------------------------------------
# Fechamento do passo G: juntar ou dividir boxes e mexer nas palavras numa edição só
# ----------------------------------------------------------------------

#: A fonte da página impressa: a Times New Roman do Windows.
FONTE_TIMES = Path("C:/Windows/Fonts/times.ttf")


def _pagina_impressa(texto):
    """Uma página com o texto impresso em Times (tinta de verdade), um box por letra."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    if not FONTE_TIMES.exists():
        # Outra fonte daria outra tinta e outros boxes: o teste pula, não muda.
        pytest.skip("a Times New Roman não está nesta máquina")
    imagem = Image.new("L", (600, 120), 255)
    desenho = ImageDraw.Draw(imagem)
    fonte = ImageFont.truetype(str(FONTE_TIMES), 50)
    x, boxes = 20, []
    for c in texto:
        if c == " ":
            x += 30
            continue
        solta = Image.new("L", (200, 120), 255)
        ImageDraw.Draw(solta).text((10, 10), c, font=fonte, fill=0)
        ys, xs = np.nonzero(np.asarray(solta) < 128)
        largura = int(xs.max() - xs.min() + 1)
        desenho.text((x - (int(xs.min()) - 10), 10), c, font=fonte, fill=0)
        boxes.append(Box(gid_de(1, len(boxes)),
                         BoxEntry(c, x, int(ys.min()), x + largura, int(ys.max()) + 1, 0.9, "net")))
        x += largura + 6
    return imagem.convert("RGB"), Pagina(1, 0, boxes, estado="reconhecida",
                                         proximo_n=len(boxes))


@pytest.mark.parametrize("antes, depois", [
    ("rn b", "mb"), ("b rn", "bm"), ("b m b", "brn b"), ("b m b", "b rnb"), ("bm b", "brnb")])
def test_juntar_ou_dividir_e_mexer_na_palavra_numa_edicao_so(antes, depois):
    """Consertar o "rn" lido e o espaço sobrando de uma vez ("rn b" -> "mb"): a quebra e a
    junção de palavras citam os gids de antes, que juntar ou dividir aposentou (antes,
    ValueError e a edição inteira desfeita)."""
    imagem, pagina = _pagina_impressa(antes)
    _texto, unidades = ss.texto_e_unidades(pagina)
    ss.aplicar(pagina, ss.planejar(unidades, depois), imagem, None)
    assert ss.texto_e_unidades(pagina)[0] == depois


def test_m_impresso_vira_rn_com_tinta_pela_sessao():
    """CA-6.6 pela sessão: "m" -> "rn" num "m" impresso dá dois boxes com tinta e nenhum
    virtual."""
    imagem, pagina = _pagina_impressa("cama")
    _texto, unidades = ss.texto_e_unidades(pagina)
    ss.aplicar(pagina, ss.planejar(unidades, "carna"), imagem, None)
    assert ss.texto_e_unidades(pagina)[0] == "carna"
    assert [b.entry.char for b in pagina.boxes] == list("carna")
    assert not pagina.decisoes.virtuais


def test_apagar_o_hifen_de_fim_de_linha_junta_a_palavra_na_exportacao():
    """§6.3: apagar o hífen de quebra junta a palavra. O Documento mostra as linhas como
    impressas, e a exportação sai "exemplo" (antes, "exem plo": pior que sem tocar)."""
    from abbychess import montagem as mo
    from abbychess.modelo import Decisoes

    p = _pagina("exem-", "plo")
    p.decisoes = Decisoes(hifen_de_quebra=frozenset({p.boxes[4].gid}))
    _editar(p, "exem-\nplo", "exemplo")
    entries, estrutura = mo.Estrutura.da_pagina(p)
    blocos = mo.pagina_extraida(0, entries, estrutura=estrutura).blocos
    assert [b.texto for b in blocos if hasattr(b, "texto")] == ["exemplo"]


def test_apagar_um_travessao_solto_no_fim_da_linha_nao_junta_palavras():
    """Só o hífen colado à palavra a parte: o travessão solto ("velha -") que sai não junta
    "velha" com a palavra da linha seguinte."""
    p = _pagina("casa velha -", "plo longe")
    _editar(p, "casa velha -\nplo", "casa velha \nplo")
    assert not p.decisoes.juncoes


# ----------------------------------------------------------------------
# As regras que a mutação achou sem teste (Q9, CA-Q-M1)
# ----------------------------------------------------------------------

def _gids(pagina):
    return [b.gid for b in pagina.boxes]


@pytest.mark.parametrize("fixos", [
    [(0, 0), (1, 1), (1, 3), (2, 2), (4, 3)],             # um fora de ordem antes dos outros
    [(0, 0), (1, 1), (2, 2), (5, 3)],                     # o do original fora da faixa
    [(0, 0), (1, 1), (2, 2), (4, 4)]])                    # o do novo fora da faixa
def test_os_fixos_fora_de_ordem_ou_de_faixa_sao_ignorados(fixos):
    """Apagar o segundo "s" de "cassa" tira o segundo glifo mesmo com fixos que não servem:
    os de fora de ordem e de faixa são pulados, e os que vêm depois deles ainda valem."""
    p = _pagina("cassa")
    segundo = p.boxes[3].gid
    _texto_, unidades = ss.texto_e_unidades(p)
    ss.editar(p, unidades, "casa", fixos=fixos)
    assert _texto(p) == "casa" and segundo not in p.vivos and p.boxes[2].gid != segundo


def test_apagar_uma_palavra_repetida_tira_a_primeira():
    """Sem fixos, as lacunas ficam o mais à esquerda: "aa aa" -> "aa" tira os glifos da
    primeira palavra (o atalho das palavras iguais é só para o texto longo)."""
    p = _pagina("aa aa")
    primeira = set(_gids(p)[:2])
    plano = _editar(p, "aa aa", "aa")
    assert plano.sair == primeira and _texto(p) == "aa"


def test_colar_a_pagina_de_lances_repetidos_com_uma_palavra_a_mais_e_a_menos():
    """Colar por cima a página de lances que se repetem (mais de 200 palavras) com 14 lances
    novos no começo e 14 a menos no fim: as palavras iguais ancoram o alinhamento (também as
    que se repetem muito), e nenhuma letra é trocada; a faixa sozinha não cobre o deslocamento."""
    palavras = ["e4", "e5"] * 150
    p = _pagina(" ".join(palavras))
    _texto_, unidades = ss.texto_e_unidades(p)
    plano = ss.planejar(unidades, " ".join(["Cf3"] * 14 + palavras[:-14]))
    assert not plano.corrigir and plano.sair == set(_gids(p)[-28:])
    assert "".join(letras for letras, _ancora in plano.virtuais) == "Cf3" * 14


def test_colar_a_pagina_sem_nenhuma_palavra_igual_alinha_letra_a_letra():
    """Sem nenhuma palavra igual para ancorar, o texto longo se alinha na faixa em volta da
    diagonal: a primeira letra de cada palavra trocada é uma correção, nada sai nem entra."""
    import random

    r = random.Random(2)
    original = " ".join("".join(r.choice("abcdefgh") for _ in range(r.randint(3, 8)))
                        for _ in range(120))
    novo = "".join("x" if k == 0 or original[k - 1] == " " else c for k, c in enumerate(original))
    p = _pagina(original)
    _texto_, unidades = ss.texto_e_unidades(p)
    plano = ss.planejar(unidades, novo)
    assert len(plano.corrigir) == 120 and set(plano.corrigir.values()) == {"x"}
    assert not plano.sair and not plano.virtuais


def test_so_apagar_a_quebra_de_linha_e_uma_edicao():
    """A quebra de linha apagada não tira nem põe glifo, mas o texto digitado mudou: o
    desfazer diz "Editar", não "Aceitar"."""
    p = _pagina("casa", "velha")
    assert _editar(p, "casa\nvelha", "casavelha").muda


def test_trocar_a_letra_depois_da_quebra_de_linha_nao_avisa_da_quebra():
    p = _pagina("casa", "velha")
    plano = _editar(p, "casa\nvelha", "casa\nvelho")
    assert _texto(p) == "casa\nvelho" and plano.estrutural() == ""


@pytest.mark.parametrize("de, para, aviso", [
    ("mar", "rnar", "mar → rnar: 1 glifo dividido em 2 · Ctrl+Z desfaz"),
    ("m m", "rn rn", "m m → rn rn: 2 glifos divididos · Ctrl+Z desfaz"),
    ("carn", "cam", "carn → cam: 2 glifos juntados · Ctrl+Z desfaz"),          # no fim
    ("cxsa rnar", "casa mar", "cxsa rnar → casa mar: 2 glifos juntados · Ctrl+Z desfaz")])
def test_o_aviso_das_operacoes_estruturais(de, para, aviso):
    """Um glifo dividido diz em quantos; dois, quantos glifos. A junção no fim da sessão e a
    que vem depois de uma troca simples também são achadas."""
    p = _pagina(de)
    plano = _editar(p, de, para)
    assert _texto(p) == para and plano.estrutural() == aviso


def test_o_aviso_encurta_a_palavra_de_mais_de_30_letras():
    longa = "abcdefghij" * 3
    p = _pagina(longa + "x")
    plano = _editar(p, longa + "x", longa)
    assert plano.estrutural() == f"{longa[:29]}… → {longa}: 1 glifo tirado · Ctrl+Z desfaz"


def test_gid_no_cursor_logo_depois_do_espaco_e_no_fim():
    """Logo depois do espaço, o glifo do Ctrl+Enter é o que vem depois dele; no fim, depois de
    um espaço digitado, não há glifo."""
    p = _pagina("ab cd")
    _texto_, unidades = ss.texto_e_unidades(p)
    assert ss.gid_no_cursor(unidades, "ab cd", 3) == p.boxes[2].gid
    assert ss.gid_no_cursor(unidades, "ab cd ", 6) is None


def test_a_ligadura_dividida_no_meio_de_uma_palavra_revisa_as_vizinhas():
    """A letra no meio da ligadura "fi" a divide; as letras em volta dela, na mesma palavra e
    na seguinte, ficam com o glifo delas e revisadas, e a letra nova logo depois dela entra
    depois dos boxes da divisão."""
    for pagina, de, para in [("afb", "afib", "afxib"), ("af b", "afi b", "afxi b"),
                             ("afb", "afib", "afxiyb")]:
        p = _pagina(pagina)
        p.boxes[1] = Box(p.boxes[1].gid, BoxEntry("fi", 42, 20, 60, 50, 0.9, "net"))
        a, b = p.boxes[0].gid, p.boxes[2].gid
        plano = _editar(p, de, para)
        assert _texto(p) == para and len(plano.dividir_boxes) == 1
        assert a in p.vivos and b in p.vivos and p.box(a).revisado and p.box(b).revisado


@pytest.mark.parametrize("linhas, de, para, letras, lado, ancora", [
    (("a csa b",), "csa", "casa", "a", "depois", 1),     # depois do glifo antes dela
    (("x asa",), "x asa", "x casa", "c", "antes", 1),    # no começo da palavra, depois de outra
    (("o sol",), "o sol", "o bem sol", "bem", "depois", 0),   # palavra nova entre duas
    (("um sol",), "sol", "sol bem", "bem", "depois", 4),      # palavra nova no fim
    (("casa", "longe"), "longe", "muito longe", "muito", "antes", 4),   # no começo da linha
    (("casa", "longe"), "casa\nlonge", "casa\nmuito longe", "muito", "antes", 4)])
def test_a_ancora_das_letras_novas_no_plano(linhas, de, para, letras, lado, ancora):
    """A âncora de cada letra nova no plano (a da tinta sem box, §6.3): depois do glifo antes
    dela na palavra; sem ele, antes do seguinte; a palavra nova, depois do último glifo antes
    dela se ele está na linha do primeiro depois (ou se não há glifo depois), senão antes do
    primeiro depois (a palavra no começo de uma linha)."""
    p = _pagina(*linhas)
    gids = _gids(p)
    plano = _editar(p, de, para)
    assert plano.virtuais == [(letras, (lado, gids[ancora]))]


@pytest.mark.parametrize("linhas, de, para, juncao", [
    (("e-", "plo"), "e-\nplo", "e\nplo", (0, 2)),         # a linha de duas letras
    (("a b-", "plo"), "b-\nplo", "b\nplo", (1, 3)),       # a palavra antes da partida
    (("exem-", "plo"), "exem-\nplo", "eem\nplo", (3, 5))])   # outra letra sai antes do hífen
def test_o_hifen_de_fim_de_linha_que_sai_junta_a_palavra(linhas, de, para, juncao):
    p = _pagina(*linhas)
    gids = _gids(p)
    _editar(p, de, para)
    assert _texto(p) == "\n".join(linhas).replace(de, para)
    assert (gids[juncao[0]], gids[juncao[1]]) in p.decisoes.juncoes


@pytest.mark.parametrize("linhas, de, para", [
    (("casa velha-",), "velha-", "velha"),                # o hífen da última linha
    (("-bem", "fim"), "-bem", "bem"),                     # o hífen que abre a linha
    (("casa", "velha"), "casa", "cas")])                  # a última letra da linha não é hífen
def test_o_que_sai_no_fim_ou_no_comeco_da_linha_e_nao_parte_palavra_nao_junta(linhas, de, para):
    p = _pagina(*linhas)
    _editar(p, de, para)
    assert _texto(p) == "\n".join(linhas).replace(de, para) and not p.decisoes.juncoes


def test_apagar_a_quebra_gravada_onde_a_tinta_tambem_separa_junta():
    """A quebra gravada entre duas palavras que a tinta também separa (o box mexido depois
    dela): apagar o espaço tira a quebra e junta as palavras."""
    from abbychess.modelo import Decisoes

    p = _pagina("ab cd")
    p.decisoes = Decisoes(quebras=frozenset({p.boxes[2].gid}))
    _editar(p, "ab cd", "abcd")
    assert _texto(p) == "abcd" and not p.decisoes.quebras


def test_figurinas_com_o_espaco_digitado_antes_e_na_pagina_longa_de_lances():
    """O espaço digitado antes do lance fica; na página longa de lances que se repetem (mais
    de 200), só o lance mudado vira figurina."""
    assert ss.com_figurinas(" Cf3 e5", "Cf3 e5", "pt", "figurinas") == " Cf3 e5"
    original = " ".join(["Cf3", "e5"] * 120)
    novo = "Cf6" + original[3:]                           # o primeiro lance mudado
    assert ss.com_figurinas(novo, original, "pt", "figurinas") == "♘f6" + original[3:]


# ----------------------------------------------------------------------
# Os defeitos que a mutação achou (Q9)
# ----------------------------------------------------------------------

def _exportado(pagina):
    """Os parágrafos da página como a exportação os escreve."""
    from abbychess import montagem as mo

    entries, estrutura = mo.Estrutura.da_pagina(pagina)
    return [b.texto for b in mo.pagina_extraida(0, entries, estrutura=estrutura).blocos
            if hasattr(b, "texto")]


@pytest.mark.parametrize("para, documento", [
    ("exeplo", "exe\nplo"),                               # a letra antes do hífen também sai
    ("exemlo", "exem\nlo"),                               # a primeira da linha seguinte também
    ("exelo", "exe\nlo")])                                # as duas
def test_apagar_a_letra_e_o_hifen_de_fim_de_linha_juntos_junta_a_palavra(para, documento):
    """§6.3: apagar o hífen de quebra junta a palavra, também quando uma letra em volta dele
    sai na mesma edição ("exem-" / "plo" -> "exeplo"; antes, a exportação saía "exe plo")."""
    from abbychess.modelo import Decisoes

    p = _pagina("exem-", "plo")
    p.decisoes = Decisoes(hifen_de_quebra=frozenset({p.boxes[4].gid}))
    _editar(p, "exem-\nplo", para)
    assert _texto(p) == documento and _exportado(p) == [para]


@pytest.mark.parametrize("para", [
    "casa\nmuito longe",                                  # no começo da segunda linha
    "casa muito\nlonge"])                                 # no fim da primeira
def test_a_palavra_nova_junto_da_quebra_de_linha_fica_na_linha_digitada(para):
    """Na sessão que pega as duas linhas impressas, a palavra digitada logo depois da quebra
    de linha fica no começo da segunda linha, e a digitada logo antes, no fim da primeira
    (antes, as duas iam para o fim da primeira: "casa muito\\nlonge")."""
    p = _pagina("casa", "longe")
    _editar(p, "casa\nlonge", para)
    assert _texto(p) == para


def _com_a_ligadura_fi(tinta_sem_corte: bool = False):
    """A página "afib" impressa em Times, com o "f" e o "i" num box só, a ligadura "fi";
    `tinta_sem_corte`: no box, só um fio de tinta, que não se corta em duas letras (todo
    corte deixa um lado sem tinta)."""
    from PIL import ImageDraw

    imagem, impressa = _pagina_impressa("afib")
    a, f, i, b = impressa.boxes
    fi = BoxEntry("fi", f.entry.x1, min(f.entry.y1, i.entry.y1), i.entry.x2,
                  max(f.entry.y2, i.entry.y2), 0.9, "net")
    if tinta_sem_corte:
        desenho = ImageDraw.Draw(imagem)
        desenho.rectangle([fi.x1, fi.y1, fi.x2, fi.y2], fill=(255, 255, 255))
        desenho.rectangle([fi.x1, fi.y1, fi.x1 + 1, fi.y2 - 1], fill=(0, 0, 0))
    return imagem, Pagina(1, 0, [a, Box(f.gid, fi), b], estado="reconhecida",
                          proximo_n=impressa.proximo_n)


def test_o_espaco_digitado_dentro_da_ligadura_parte_a_palavra_ali():
    """O espaço digitado no meio da ligadura "fi" ("afib" -> "af ib") divide o box pela tinta
    e parte a palavra entre os pedaços (antes, a quebra entrava antes da ligadura inteira, e
    a página ficava "a fib")."""
    imagem, pagina = _com_a_ligadura_fi()
    _texto_, unidades = ss.texto_e_unidades(pagina)
    ss.aplicar(pagina, ss.planejar(unidades, "af ib"), imagem, None)
    assert _texto(pagina) == "af ib"
    assert [b.entry.char for b in pagina.boxes] == ["a", "f", "i", "b"]


@pytest.mark.parametrize("sem_imagem", [True, False])
def test_o_espaco_dentro_da_ligadura_sem_tinta_para_cortar_e_recusado(sem_imagem):
    """Sem a tinta para cortar a ligadura (a página sem imagem, ou uma tinta que não se corta
    em duas letras), o espaço não tem onde ficar: a sessão é recusada, com o motivo, e a
    página fica como estava; o usuário divide o glifo antes (Ctrl+D)."""
    imagem, pagina = _com_a_ligadura_fi(tinta_sem_corte=not sem_imagem)
    antes = ([(b.gid, b.entry.as_state()) for b in pagina.boxes], pagina.decisoes)
    _texto_, unidades = ss.texto_e_unidades(pagina)
    plano = ss.planejar(unidades, "af ib")
    with pytest.raises(ss.Recusa, match="não dá para pôr um espaço dentro do glifo “fi”"):
        ss.aplicar(pagina, plano, None if sem_imagem else imagem, None)
    assert ([(b.gid, b.entry.as_state()) for b in pagina.boxes], pagina.decisoes) == antes
    assert _texto(pagina) == "afib"
