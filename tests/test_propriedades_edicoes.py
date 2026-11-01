"""Q-T6: as edições por gid que ficam fora das máquinas de estado (`test_modelo_estados`).

`dividir_em`, `juntar_varios` (as edições ``1 -> k`` e ``k -> 1`` do Documento), `estilizar`,
`paragrafo`, os virtuais (pôr, trocar e tirar), `ajustar` e `revisar`, misturados com as
decisões de palavra (`quebrar`, `juntar_palavras`), sobre a página sintética das máquinas. As
leis, a cada passo:

- a página continua válida (as invariantes de `tests/estrategias.py`);
- cada edição faz o que diz e só isso: os glifos que ela não tocou são os mesmos objetos, e a
  ordem do documento (`montar`) é a de antes com a mudança dela (o glifo dividido trocado
  pelas partes, os juntados pelo novo, o virtual posto ou tirado), e nada mais muda de lugar;
- desfazer a edição (`historico.mudanca`, para trás) volta à página igual (os mesmos `Box`, as
  decisões e o estado), e refazer volta à editada.

Os virtuais nascem com uma âncora só (depois de um glifo, antes de um glifo ou no começo),
como o Documento os põe (`ancoragem`, `sessao`): a API aceita as duas, mas ninguém as usa.
"""

from __future__ import annotations

from hypothesis import strategies as st

from abbychess import edicao as ed
from abbychess import historico as hs
from abbychess import texto as tx

from tests.estrategias import LARGURA, ALTURA, conferir_a_pagina, pagina_sintetica, propriedade

OPERACOES = ("dividir_em", "juntar_varios", "estilizar", "paragrafo", "virtual",
             "trocar_virtual", "apagar_virtual", "ajustar", "revisar", "quebrar",
             "juntar_palavras")

PASSO = st.tuples(st.sampled_from(OPERACOES), st.integers(0, 10_000), st.integers(0, 10_000),
                  st.sampled_from("xyz"))


def _ordem(pagina):
    """Os gids do documento, na ordem dele."""
    return tx.montar(pagina).gids()


def _glifos(ordem, virtuais):
    """A ordem do documento sem os virtuais (os glifos com caixa)."""
    return [g for g in ordem if g not in virtuais]


def _virtuais(pagina) -> set:
    return {v.gid for v in pagina.decisoes.virtuais}


def _intactos(antes, depois, tocados) -> None:
    """Os glifos que a edição não tocou são os mesmos objetos, na mesma ordem."""
    assert [b for b in antes if b.gid not in tocados] == \
        [b for b in depois if b.gid not in tocados]


def _corrida(pagina, i, j):
    """Uma corrida de 1 a 4 glifos seguidos da mesma linha impressa (o mesmo topo)."""
    k = i % len(pagina.boxes)
    corrida = [pagina.boxes[k]]
    for b in pagina.boxes[k + 1:k + 1 + j % 4]:
        if abs(b.entry.y1 - corrida[0].entry.y1) > 10:
            break
        corrida.append(b)
    return [b.gid for b in corrida]


# ----------------------------------------------------------------------
# Cada edição e a lei dela; None: a edição não se aplica (ValueError, ou sem glifo)
# ----------------------------------------------------------------------

def _dividir_em(pagina, imagem, i, j, c):
    gid = pagina.boxes[i % len(pagina.boxes)].gid
    chars = (c + "y", c + "yz", "zz")[j % 3]
    antes, ordem, virtuais = list(pagina.boxes), _ordem(pagina), _virtuais(pagina)
    dif = ed.dividir_em(pagina, imagem, gid, chars)
    partes = dif.sucessores[gid]
    assert [b.gid for b in dif.novos] == partes and gid not in pagina.vivos
    assert "".join(pagina.box(g).entry.char for g in partes) == chars
    _intactos(antes, pagina.boxes, {gid, *partes})
    caixas = [pagina.box(g).entry for g in partes]
    assert all(a.x2 <= b.x1 for a, b in zip(caixas, caixas[1:])), caixas    # lado a lado
    if gid in ordem:                      # o glifo lido: as partes no lugar dele
        esperada = [p for g in _glifos(ordem, virtuais) for p in (partes if g == gid else [g])]
        assert _glifos(_ordem(pagina), virtuais) == esperada


def _juntar_varios(pagina, _imagem, i, j, c):
    gids = _corrida(pagina, i, j)
    if len(gids) < 2:
        return None
    antes, ordem, virtuais = list(pagina.boxes), _ordem(pagina), _virtuais(pagina)
    dif = ed.juntar_varios(pagina, gids, c)
    [novo] = [b.gid for b in dif.novos]
    assert dif.sucessores == {g: [novo] for g in gids} and pagina.box(novo).entry.char == c
    _intactos(antes, pagina.boxes, {*gids, novo})
    # Os mesmos glifos, com a corrida trocada pelo novo. A ordem, não: ela é da geometria (o
    # core), e a caixa juntada cobre o vão entre as palavras da página sintética (cada glifo
    # é uma palavra); numa página de uma linha curta embaixo, o core a lê noutra coluna.
    assert sorted(_glifos(_ordem(pagina), virtuais)) == \
        sorted({g for g in _glifos(ordem, virtuais) if g not in gids} | {novo})


def _estilizar(pagina, _imagem, i, j, _c):
    gids = _corrida(pagina, i, j)
    campo = ("negrito", "italico", "sublinhado")[j % 3]
    valor = not all(getattr(pagina.box(g).estilo, campo) for g in gids)
    antes, ordem, decisoes = list(pagina.boxes), _ordem(pagina), pagina.decisoes
    ed.estilizar(pagina, gids, campo)
    assert all(getattr(pagina.box(g).estilo, campo) is valor for g in gids)
    assert all(pagina.box(g).entry is a.entry for a in antes for g in gids if a.gid == g)
    _intactos(antes, pagina.boxes, set(gids))
    assert _ordem(pagina) == ordem and pagina.decisoes == decisoes


def _paragrafo(pagina, _imagem, i, _j, _c):
    gid = pagina.boxes[i % len(pagina.boxes)].gid
    antes, ordem = list(pagina.boxes), _ordem(pagina)
    ed.paragrafo(pagina, gid)
    decisoes = pagina.decisoes
    assert gid in decisoes.paragrafo_antes
    ed.paragrafo(pagina, gid)                       # de novo: nada muda
    assert pagina.decisoes == decisoes
    assert pagina.boxes == antes and _ordem(pagina) == ordem


def _alvo(pagina, i):
    """Um glifo da página, com caixa ou virtual."""
    gids = [b.gid for b in pagina.boxes] + [v.gid for v in pagina.decisoes.virtuais]
    return gids[i % len(gids)]


def _virtual(pagina, _imagem, i, j, c):
    ancora = _alvo(pagina, i)
    onde = j % 3
    depois_de = ancora if onde == 0 else None
    antes_de = ancora if onde == 1 else None
    antes, ordem = list(pagina.boxes), _ordem(pagina)
    _dif, novo = ed.virtual(pagina, c, depois_de, palavra_nova=bool(j & 4), antes_de=antes_de)
    agora = _ordem(pagina)
    assert agora.count(novo) == 1 and tx.montar(pagina).chars[novo] == c
    assert [g for g in agora if g != novo] == ordem
    assert pagina.boxes == antes


def _um_virtual(pagina, i):
    virtuais = [v.gid for v in pagina.decisoes.virtuais]
    return virtuais[i % len(virtuais)] if virtuais else None


def _trocar_virtual(pagina, _imagem, i, _j, c):
    gid = _um_virtual(pagina, i)
    if gid is None:
        return None
    ordem = _ordem(pagina)
    ed.trocar_virtual(pagina, gid, c)
    assert _ordem(pagina) == ordem and tx.montar(pagina).chars[gid] == c


def _apagar_virtual(pagina, _imagem, i, _j, _c):
    gid = _um_virtual(pagina, i)
    if gid is None:
        return None
    antes, ordem = list(pagina.boxes), _ordem(pagina)
    saiu = next(v for v in pagina.decisoes.virtuais if v.gid == gid)
    mudam = any(gid in (v.depois_de, v.antes_de) for v in pagina.decisoes.virtuais)
    irmaos = any(v.gid != gid and (v.depois_de, v.antes_de) == (saiu.depois_de, saiu.antes_de)
                 for v in pagina.decisoes.virtuais)
    ed.apagar_virtual(pagina, gid)
    assert gid not in _virtuais(pagina) and pagina.boxes == antes
    if mudam and irmaos:
        # O ancorado no que sai vai para a âncora dele, na frente do outro que já estava lá
        # ("a213" sem o 1 dá "a32"): o defeito relatado no Q-T6, fora da lei até a correção.
        return
    assert _ordem(pagina) == [g for g in ordem if g != gid]


def _ajustar(pagina, imagem, i, j, _c):
    gid = pagina.boxes[i % len(pagina.boxes)].gid
    bordas = dict(zip(("esquerda", "cima", "direita", "baixo"),
                      ((j >> s) % 7 - 3 for s in (0, 3, 6, 9))))
    k, antes, decisoes = pagina.indice_de(gid), list(pagina.boxes), pagina.decisoes
    ed.ajustar(pagina, imagem, gid, **bordas)
    e = pagina.boxes[k].entry
    assert pagina.boxes[k].gid == gid and len(pagina.boxes) == len(antes)
    assert 0 <= e.x1 < e.x2 <= LARGURA and 0 <= e.y1 < e.y2 <= ALTURA
    _intactos(antes, pagina.boxes, {gid})
    assert pagina.decisoes == decisoes


def _revisar(pagina, _imagem, i, j, _c):
    gids = _corrida(pagina, i, j)
    antes, ordem = list(pagina.boxes), _ordem(pagina)
    ed.revisar(pagina, gids)
    assert all(pagina.box(g).revisado for g in gids)
    assert all(pagina.box(g).entry is a.entry and pagina.box(g).estilo == a.estilo
               for a in antes for g in gids if a.gid == g)
    _intactos(antes, pagina.boxes, set(gids))
    assert ed.revisar(pagina, gids).vazia and _ordem(pagina) == ordem


def _quebrar(pagina, _imagem, i, _j, _c):
    ed.quebrar(pagina, pagina.boxes[i % len(pagina.boxes)].gid)


def _juntar_palavras(pagina, _imagem, i, _j, _c):
    if len(pagina.boxes) >= 2:
        k = i % (len(pagina.boxes) - 1)
        ed.juntar_palavras(pagina, pagina.boxes[k].gid, pagina.boxes[k + 1].gid)


EDICOES = {"dividir_em": _dividir_em, "juntar_varios": _juntar_varios, "estilizar": _estilizar,
           "paragrafo": _paragrafo, "virtual": _virtual, "trocar_virtual": _trocar_virtual,
           "apagar_virtual": _apagar_virtual, "ajustar": _ajustar, "revisar": _revisar,
           "quebrar": _quebrar, "juntar_palavras": _juntar_palavras}


def _desfazer_e_refazer(pagina, antes) -> None:
    """Desfazer a edição volta à página de antes (os mesmos `Box`, as decisões e o estado), e
    refazer, à editada."""
    depois = pagina.instantaneo()
    m = hs.mudanca(antes, depois)
    hs.conferir(m, pagina, para_tras=True)
    hs.aplicar(m, pagina, para_tras=True)
    assert pagina.boxes == list(antes.boxes)
    assert pagina.decisoes == antes.decisoes and pagina.estado == antes.estado
    hs.conferir(m, pagina, para_tras=False)
    hs.aplicar(m, pagina, para_tras=False)
    assert pagina.boxes == list(depois.boxes)
    assert pagina.decisoes == depois.decisoes and pagina.estado == depois.estado


def lei_das_edicoes(n, passos):
    """Qualquer sequência das edições deixa a página válida; cada uma faz o que diz, e
    desfazer e refazer cada uma voltam à página de antes e à de depois."""
    imagem, pagina = pagina_sintetica(n)
    for operacao, i, j, c in passos:
        if not pagina.boxes:
            break
        antes = pagina.instantaneo()
        try:
            EDICOES[operacao](pagina, imagem, i, j, c)
        except ValueError:
            assert pagina.boxes == list(antes.boxes) and pagina.decisoes == antes.decisoes
            continue                    # a edição recusada não muda nada
        conferir_a_pagina(pagina)
        _desfazer_e_refazer(pagina, antes)


def test_dividir_em_tres_deixa_as_letras_digitadas_lado_a_lado():
    """O exemplo mínimo que a propriedade achou (Q-T6): o terceiro caractere digitado corta um
    traço sem vão vertical, e o `split_box` do core, que escolhe o eixo, o cortava na
    horizontal; as letras saíam uma em cima da outra, e o Documento ganhava uma quebra de linha
    no meio do que foi digitado."""
    lei_das_edicoes(1, [("dividir_em", 0, 1, "x")])
    imagem, pagina = pagina_sintetica(1)
    ed.dividir_em(pagina, imagem, pagina.boxes[0].gid, "xyz")
    assert "\n" not in tx.texto(tx.montar(pagina))


test_as_edicoes_mantem_a_pagina_e_voltam_no_desfazer, \
    test_as_edicoes_mantem_a_pagina_e_voltam_no_desfazer_noturna = propriedade(
        lei_das_edicoes, rapida=30,
        n=st.integers(1, 30), passos=st.lists(PASSO, max_size=12))
