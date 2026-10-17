"""Substituir, sem Qt (SPEC §7.2, passo D2): os casos (Prosa, Notação, Ambos; o FEN nunca),
`\\1` e `\\g<nome>`, o que ainda não tem tradução, aplicar numa página (os glifos `manual`,
nada ensinado nem revisado) e o controlador: a página aberta direto, a prévia, aplicar no
livro numa transação só e o Ctrl+Z que volta todas (CA-7.2, CA-7.5)."""

from __future__ import annotations

import pytest

from abbychess import busca as bs
from abbychess import sessao as ss
from abbychess import substituir as sb
from abbychess.leitor import FONTE_MANUAL

from tests.test_busca import _esperar, livro_escrito  # noqa: F401 (fixture)
from tests.test_sessao import _pagina


def _casos(pagina, padrao, modelo, alvo=sb.PROSA, **opcoes):
    expressao, _dica = bs.compilar(bs.Opcoes(padrao, **opcoes))
    montada = ss.texto_e_unidades(pagina)
    indexada = bs.indexar_pagina(pagina, "pt", margens=(), montada=montada)
    return sb.casos_da_pagina(indexada, montada[1], expressao,
                              sb.substituto(modelo, opcoes.get("regex", False)), alvo)


def _depois(pagina, casos):
    copia = pagina.instantaneo()
    sb.aplicar_na_pagina(copia, casos)
    return copia, ss.texto_e_unidades(copia)[0]


def test_prosa_nunca_toca_notacao_e_notacao_nunca_toca_prosa():
    p = _pagina("joga Cf3 na casa")
    assert [c.antes for c in _casos(p, "c", "X")] == ["casa"]
    assert [c.antes for c in _casos(p, "c", "X", sb.NOTACAO)] == ["Cf3"]
    assert [c.antes for c in _casos(p, "c", "X", sb.AMBOS)] == ["Cf3", "casa"]
    assert _depois(p, _casos(p, "c", "X"))[1] == "joga Cf3 na Xasa"


def test_o_fen_nunca_e_substituido():
    p = _pagina("joga Cf3")
    p.diagramas = [type("D", (), {"lido": True, "fen": "8/8/8/8/8/5N2/8/8 w",
                                "caixa": (0, 500, 100, 600), "id": "d0"})()]
    expressao, _ = bs.compilar(bs.Opcoes("8"))
    montada = ss.texto_e_unidades(p)
    indexada = bs.indexar_pagina(p, "pt", margens=(), montada=montada)
    assert "8/8" in indexada.texto                       # pesquisável
    assert sb.casos_da_pagina(indexada, montada[1], expressao, sb.substituto("9", False),
                              sb.AMBOS) == []


def test_grupos_e_nomes_no_substituto():
    p = _pagina("joga bxc5 e dxe4")
    casos = _casos(p, r"(?P<col>[a-h])x([a-h][1-8])", r"\g<col>:\2", sb.NOTACAO, regex=True)
    assert [(c.antes, c.depois) for c in casos] == [("bxc5", "b:c5"), ("dxe4", "d:e4")]
    sem_regex = _casos(p, "bxc5", r"\1", sb.NOTACAO)
    assert [c.depois for c in sem_regex] == [r"\1"]      # sem a regex, o modelo como está


def test_o_substituto_com_grupo_que_nao_existe_e_invalido():
    expressao, _ = bs.compilar(bs.Opcoes(r"(a)(b)", regex=True))
    sb.validar(r"\2\g<1>", expressao, True)
    for ruim in (r"\3", r"\g<nome>", r"\g<1"):
        with pytest.raises(bs.PadraoInvalido):
            sb.validar(ruim, expressao, True)
    sb.validar(r"\3", expressao, False)                  # sem a regex, nada a validar


def test_o_que_e_do_passo_g_vem_desabilitado_com_o_motivo():
    p = _pagina("uma casa")
    [caso] = _casos(p, "m", "rn")                         # 1 glifo -> 2 letras: dividir
    assert not caso.aplicavel and "dividir" in caso.motivo
    [caso] = _casos(p, "as", "a")                         # tirar um glifo: tem tradução
    assert caso.aplicavel


def test_casamentos_na_mesma_palavra_sao_um_caso_so():
    p = _pagina("cassa velha")
    [caso] = _casos(p, "s", "z")
    assert (caso.antes, caso.depois, caso.casamentos) == ("cassa", "cazza", 2)


def test_aplicar_deixa_os_glifos_manual_sem_ensinar_nem_revisar():
    p = _pagina("uma casa velha")
    copia, texto = _depois(p, _casos(p, "casa", "cama"))
    assert texto == "uma cama velha"
    trocado = next(b for b in copia.boxes if b.entry.char == "m" and b.gid == p.boxes[5].gid)
    assert trocado.entry.source == FONTE_MANUAL and trocado.amostra is None
    assert not any(b.revisado for b in copia.boxes)


def test_aplicar_recusa_se_a_pagina_mudou_desde_a_previa():
    p = _pagina("uma casa velha")
    casos = _casos(p, "casa", "cama")
    outra = _pagina("uma rosa velha")
    with pytest.raises(ss.Recusa):
        sb.aplicar_na_pagina(outra, casos)


# ----------------------------------------------------------------------
# O controlador
# ----------------------------------------------------------------------

@pytest.fixture
def sub(livro_escrito):  # noqa: F811
    from abbychess.controladores import ControladorDaSubstituicao

    projeto, ctl, busca, escrever, eventos = livro_escrito
    s = ControladorDaSubstituicao(ctl, busca)
    eventos.update(previas=[], feitas=[], erros=[])
    ctl.eventos.ligar("previa_pronta", eventos["previas"].append)
    ctl.eventos.ligar("substituicao_feita", lambda *a: eventos["feitas"].append(a))
    ctl.eventos.ligar("substituicao_falhou", eventos["erros"].append)
    return projeto, ctl, s, escrever, eventos


def _textos(projeto):
    return [ss.texto_e_unidades(projeto.carregar_modelo(i))[0] for i in projeto.paginas_lidas()]


def test_ca_7_5_fora_da_pagina_so_aplica_depois_da_previa(sub):
    projeto, ctl, s, escrever, eventos = sub
    assert s.previa(bs.Opcoes("casa", escopo=bs.LIVRO), "lata", sb.PROSA)
    _esperar(lambda: eventos["previas"])
    previas = eventos["previas"][-1]
    assert [p.indice for p in previas] == [0, 1]
    assert _textos(projeto) == ["casa velha", "outra casa", "fim"]   # nada aplicado ainda
    s.aplicar({p.indice: p.casos for p in previas}, "Substituir 2 ocorrências")
    ctl.executar.tudo()
    assert _textos(projeto) == ["lata velha", "outra lata", "fim"]
    assert eventos["feitas"][-1][:2] == (2, 2)


def test_ca_7_2_um_ctrl_z_volta_todas_as_paginas(sub):
    projeto, ctl, s, escrever, eventos = sub
    s.previa(bs.Opcoes("a", escopo=bs.LIVRO), "o", sb.PROSA)
    _esperar(lambda: eventos["previas"])
    s.aplicar({p.indice: p.casos for p in eventos["previas"][-1]}, "Substituir")
    ctl.executar.tudo()
    assert _textos(projeto) == ["coso velho", "outro coso", "fim"]
    ctl.desfazer()
    ctl.executar.tudo()
    assert _textos(projeto) == ["casa velha", "outra casa", "fim"]
    ctl.refazer()
    ctl.executar.tudo()
    assert _textos(projeto) == ["coso velho", "outro coso", "fim"]


def test_na_pagina_aberta_aplica_direto_um_caso_ou_todos(sub):
    projeto, ctl, s, escrever, eventos = sub
    escrever(0, "casa e casa")
    ctl.ir_para(0)
    s.na_pagina(bs.Opcoes("casa", escopo=bs.PAGINA), "lata", sb.PROSA, posicao=7)
    ctl.executar.tudo()
    assert _textos(projeto)[0] == "casa e lata"
    s.na_pagina(bs.Opcoes("casa", escopo=bs.PAGINA), "lata", sb.PROSA)
    ctl.executar.tudo()
    assert _textos(projeto)[0] == "lata e lata"


def test_a_pagina_editada_depois_da_previa_aplica_na_de_agora_ou_fica_de_fora(sub):
    projeto, ctl, s, escrever, eventos = sub
    s.previa(bs.Opcoes("casa", escopo=bs.LIVRO), "lata", sb.PROSA)
    _esperar(lambda: eventos["previas"])
    escrever(1, "nada aqui")                             # a página 2 mudou
    s.aplicar({p.indice: p.casos for p in eventos["previas"][-1]}, "Substituir")
    ctl.executar.tudo()
    assert _textos(projeto) == ["lata velha", "nada aqui", "fim"]
    casos, paginas, falhas, _sem = eventos["feitas"][-1]
    assert (casos, paginas) == (1, 1) and 1 in falhas


def test_o_substituto_invalido_nao_monta_a_previa(sub):
    projeto, ctl, s, escrever, eventos = sub
    assert not s.previa(bs.Opcoes("(c)asa", regex=True), r"\2", sb.PROSA)
    assert "não existe" in eventos["erros"][-1]
