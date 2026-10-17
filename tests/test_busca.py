"""Localizar, sem Qt (SPEC §7.1, §7.3, passo B): o índice, a busca, as classes de xadrez
(CA-7.4), figurina = letra (CA-7.6), o padrão inválido e o lento (CA-7.3), o escopo, o
"onde" e a busca por glifo."""

from __future__ import annotations

import re

import pytest
from core.box_model import BoxEntry

from abbychess import busca as bs
from abbychess import sessao as ss
from abbychess.modelo import Box

from tests.test_sessao import _pagina


def _indice(*linhas, idioma="pt", indice=0):
    p = _pagina(*linhas)
    p.indice = indice
    return bs.indexar_pagina(p, idioma, margens=())


def _achados(paginas, texto, **opcoes):
    if isinstance(paginas, bs.PaginaIndexada):
        paginas = {paginas.indice: paginas}
    resultado = bs.buscar(paginas, bs.Opcoes(texto, **opcoes))
    return [paginas[o.pagina].texto[o.inicio:o.fim] for o in resultado.ocorrencias]


def test_o_indice_tem_o_texto_do_documento_e_o_gid_de_cada_caractere():
    p = _pagina("joga Cf3")
    indexada = bs.indexar_pagina(p, "pt", margens=())
    assert indexada.texto == ss.texto_e_unidades(p)[0] == "joga Cf3"
    assert indexada.gids[5] == p.boxes[4].gid and indexada.gids[4] is None
    assert indexada.etiqueta(0) == bs.PROSA and indexada.etiqueta(5) == bs.NOTACAO


def test_cada_resultado_leva_ao_gid_certo():
    indexada = _indice("vou conc1uir hoje")
    [o] = bs.buscar({0: indexada}, bs.Opcoes(r"(?<=\w)1(?=\w)", regex=True)).ocorrencias
    assert o.gids == (indexada.gids[8],) and o.linha == 1 and o.trecho[o.coluna] == "1"


@pytest.mark.parametrize("idioma, positivos, negativos", [
    ("pt", ["Cf3", "exd5", "O-O", "Te8=D+", "Dxe5#", "♘f3"], ["casa", "x9", "Zf3"]),
    ("en", ["Nf3", "exd5", "O-O-O", "Re8=Q+", "♘f3"], ["house", "Zf3"])])
def test_ca_7_4_a_classe_de_lance(idioma, positivos, negativos):
    for token in positivos:
        assert _achados(_indice(token, idioma=idioma), r"^\L$", regex=True, idioma=idioma), token
    for token in negativos:
        assert not _achados(_indice(token, idioma=idioma), r"^\L$", regex=True,
                            idioma=idioma), token


@pytest.mark.parametrize("classe, idioma, positivos, negativos", [
    (r"\P", "pt", ["C", "D", "♘", "♛"], ["N", "x", "a"]),
    (r"\P", "en", ["N", "Q", "♘"], ["C", "D", "x"]),
    (r"\C", "pt", ["e4", "h8", "a1"], ["i9", "e9", "z1"]),
    (r"\V", "pt", ["±", "∓", "⩲", "!?", "?!", "+-", "!", "∞"], ["a", "*"])])
def test_ca_7_4_as_classes_de_peca_casa_e_valoracao(classe, idioma, positivos, negativos):
    for token in positivos:
        assert _achados(_indice(token, idioma=idioma), rf"^{classe}$", regex=True,
                        maiusculas=True, idioma=idioma), (classe, token)
    for token in negativos:
        assert not _achados(_indice(token, idioma=idioma), rf"^{classe}$", regex=True,
                            maiusculas=True, idioma=idioma), (classe, token)


def test_a_classe_dentro_de_colchetes_e_a_dica():
    padrao, dica = bs.expandir_classes(r"[\P]x\C", "pt")
    assert re.fullmatch(padrao, "Cxe4") and re.fullmatch(padrao, "♘xe4")
    assert dica.startswith(r"\P = peça") and r"\C = casa" in dica
    with pytest.raises(bs.PadraoInvalido):
        bs.expandir_classes(r"[\L]", "pt")


def test_ca_7_6_figurina_igual_a_letra():
    indexada = _indice("joga Cf3 ou ♘f3 ou Nf3 Casa")
    assert _achados(indexada, "Cf3", maiusculas=True, figurina_letra=True) == ["Cf3", "♘f3", "Nf3"]
    assert _achados(indexada, "Cf3", maiusculas=True) == ["Cf3"]
    assert _achados(indexada, "Casa", maiusculas=True, figurina_letra=True) == ["Casa"]


def test_ca_7_3_regex_invalida_e_padrao_lento():
    with pytest.raises(bs.PadraoInvalido):
        bs.buscar({0: _indice("casa")}, bs.Opcoes("(casa", regex=True))
    longo = _indice("a" * 400 + "!")
    with pytest.raises(bs.PadraoLento, match="lento"):
        bs.buscar({0: longo}, bs.Opcoes(r"(\w+)+$", regex=True), tempo_limite=0.02)


def test_maiusculas_palavra_inteira_e_o_escopo():
    paginas = {i: _indice(f"Casa casa casamento {i}", indice=i) for i in range(4)}
    assert len(_achados(paginas, "casa")) == 12
    assert len(_achados(paginas, "casa", maiusculas=True)) == 8
    assert len(_achados(paginas, "casa", palavra_inteira=True)) == 8
    assert len(_achados(paginas, "casa", escopo=bs.PAGINA, pagina_atual=2)) == 3
    assert len(_achados(paginas, "casa", escopo=bs.INTERVALO, intervalo=(1, 2))) == 6
    assert _achados(paginas, "casa", escopo=bs.SELECAO, selecao=(3, 5, 9)) == ["casa"]


def test_onde_separa_prosa_notacao_e_fen():
    p = _pagina("joga Cf3 casa")
    p.diagramas = [type("D", (), {"lido": True, "fen": "8/8/8/8/8/5N2/8/8 w",
                                "caixa": (0, 500, 100, 600), "id": "d0"})()]
    indexada = bs.indexar_pagina(p, "pt", margens=())
    assert indexada.texto.endswith("\n8/8/8/8/8/5N2/8/8 w")
    assert _achados(indexada, "a", onde=frozenset({bs.PROSA})) == ["a", "a", "a"]
    assert _achados(indexada, "f3", onde=frozenset({bs.NOTACAO})) == ["f3"]
    assert _achados(indexada, "5N2", onde=frozenset({bs.FEN})) == ["5N2"]
    assert not _achados(indexada, "5N2", onde=frozenset({bs.PROSA, bs.NOTACAO}))


def test_a_busca_cancelada_para_entre_as_paginas():
    paginas = {i: _indice("casa", indice=i) for i in range(5)}
    vistas = []
    resultado = bs.buscar(paginas, bs.Opcoes("casa"),
                          cancelado=lambda: (vistas.append(1), len(vistas) > 2)[1])
    assert resultado.cancelada and resultado.paginas_buscadas == 2


def test_a_busca_por_glifo():
    p = _pagina("casa")
    p.boxes[1] = Box(p.boxes[1].gid, BoxEntry("a", 42, 20, 60, 50, 0.3, "manual"))
    indexada = bs.indexar_pagina(p, "pt", margens=())
    assert [g.gid for g in bs.buscar_glifos({0: indexada}, "a")] == [p.boxes[1].gid, p.boxes[3].gid]
    assert [g.gid for g in bs.buscar_glifos({0: indexada}, "a", fontes=["manual"])] == [p.boxes[1].gid]
    assert [g.gid for g in bs.buscar_glifos({0: indexada}, "", confianca_maxima=0.5)] == [p.boxes[1].gid]


def test_construir_sem_processos_pelos_arquivos(tmp_path):
    import json

    from abbychess.projeto import _pagina_para_json

    arquivos = {}
    for i in range(3):
        p = _pagina(f"pagina {i}")
        p.indice = i
        caminho = tmp_path / f"p{i}.json"
        caminho.write_text(json.dumps(_pagina_para_json(p)), encoding="utf-8")
        arquivos[i] = (str(caminho), 7)
    indice = bs.construir(arquivos, "pt", paralelo=False)
    assert sorted(indice) == [0, 1, 2] and indice[2].texto == "pagina 2" and indice[1].versao == 7


# ----------------------------------------------------------------------
# O controlador (o índice em segundo plano, a busca numa thread)
# ----------------------------------------------------------------------

def _esperar(condicao, limite=20.0):
    import time

    fim = time.monotonic() + limite
    while not condicao() and time.monotonic() < fim:
        time.sleep(0.01)
    assert condicao()


def test_o_controlador_monta_o_indice_busca_e_refaz_a_pagina_editada(tmp_path):
    from abbychess.controladores import ControladorDaBusca
    from abbychess.projeto import ProjetoDeLivro
    from tests.test_controlador import ExecutorManual, _controlador
    from tests.test_livro import pdf_sintetico

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Duas", pdf_sintetico(tmp_path))
    try:
        executor = ExecutorManual()
        ctl = _controlador(projeto, executor)
        ctl.reconhecer()
        executor.tudo()
        busca = ControladorDaBusca(ctl, paralelo=False)
        fins, falhas = [], []
        ctl.eventos.ligar("busca_terminou", fins.append)
        ctl.eventos.ligar("busca_falhou", falhas.append)
        busca.abrir()
        busca.buscar(bs.Opcoes("zzqq"))                  # pedida antes do índice: espera
        _esperar(lambda: busca.pronto.is_set() and fins)
        assert sorted(busca.indice) == projeto.paginas_lidas() and not fins[-1].ocorrencias
        texto, unidades = ss.texto_e_unidades(ctl.modelo)
        inicio, fim = ss.palavras_em(unidades, 0, 0)
        ctl.confirmar_sessao(unidades[inicio:fim], "zzqq" + texto[inicio:fim])   # uma edição
        executor.tudo()
        busca.buscar(bs.Opcoes("zzqq"))
        _esperar(lambda: len(fins) == 2)
        [o] = fins[-1].ocorrencias
        assert o.pagina == ctl.indice and len(o.gids) == 4
        busca.buscar(bs.Opcoes("(zz", regex=True))
        assert falhas and "inválida" in falhas[-1]
    finally:
        projeto.fechar()
