"""A verificação de texto: o léxico do core aponta, o usuário corrige os glifos.

A página sintética tem prosa e notação ("abc Bxf6 bca"). Os glifos recebem a
leitura certa à mão, para o teste não depender do modelo global, e um léxico
pequeno conhece só "abc": "bca" é desconhecida, e "Bxf6", que é lance, não pode
aparecer nunca.
"""

from __future__ import annotations

import pytest

from core import lexico

from abbychess import pagina as pg
from abbychess import verificacao as vf
from abbychess.leitor import FONTE_MANUAL

from tests.test_treino_por_livro import _pagina_sintetica

LINHAS = ("abc Bxf6 bca", "cab abc")


def _ler_a_mao(boxes, linhas=LINHAS):
    letras = [c for linha in linhas for c in linha if not c.isspace()]
    assert len(boxes) == len(letras), "a segmentação devia dar um box por letra"
    for b, c in zip(boxes, letras):
        b.char, b.source, b.confidence = c, "neural", 0.99
    return boxes


@pytest.fixture
def imagem(tmp_path):
    return pg.FonteDePaginas(_pagina_sintetica(tmp_path / "p.png", LINHAS)).pagina(0)


@pytest.fixture
def boxes(imagem):
    return _ler_a_mao(pg.segmentar(imagem))


@pytest.fixture
def lex():
    return lexico.Lexico(palavras={"abc", "cab"})


def test_so_a_prosa_desconhecida_aparece_e_a_notacao_nunca(boxes, lex):
    achadas = vf.desconhecidas(boxes, lex)
    assert [d.palavra for d in achadas] == ["bca"]
    assert "".join(boxes[i].char for i in achadas[0].indices) == "bca"
    assert achadas[0].explicacao == "fora do dicionário"


def test_ignoradas_saem_da_lista(boxes, lex):
    assert vf.desconhecidas(boxes, lex, ignoradas={"BCA"}) == []


def test_glifo_sem_leitura_fica_na_palavra(boxes, lex):
    palavra = vf.desconhecidas(boxes, lex)[0]
    meio = palavra.indices[1]
    boxes[meio].char = ""
    sem_o_c = vf.desconhecidas(boxes, lex)
    assert [d.palavra for d in sem_o_c] == ["ba"]
    assert sem_o_c[0].indices == palavra.indices  # os três glifos, com o vazio no meio
    vf.corrigir(boxes, sem_o_c[0].indices, "abc")
    assert vf.desconhecidas(boxes, lex) == []


def test_corrigir_troca_so_os_glifos_que_mudaram(boxes, lex):
    palavra = vf.desconhecidas(boxes, lex)[0]
    mudados = vf.corrigir(boxes, palavra.indices, "aca")
    b, c, a = (boxes[i] for i in palavra.indices)
    assert mudados == [(palavra.indices[0], "a")]
    assert b.char == "a" and b.source == FONTE_MANUAL
    assert c.source == "neural" and a.source == "neural"


def test_letras_de_mais_ou_de_menos_pedem_dividir_ou_juntar(boxes, lex):
    palavra = vf.desconhecidas(boxes, lex)[0]
    with pytest.raises(ValueError, match="Divida ou junte"):
        vf.corrigir(boxes, palavra.indices, "bcaa")
    with pytest.raises(ValueError, match="sem espaços"):
        vf.corrigir(boxes, palavra.indices, "b ca")
    assert "".join(boxes[i].char for i in palavra.indices) == "bca"


def test_ligadura_reparte_pelo_tamanho_de_antes(boxes):
    i, j = 0, 1
    boxes[i].char, boxes[j].char = "fi", "x"
    assert vf.repartir(boxes, [i, j], "flx") == ["fl", "x"]


def test_adicionar_grava_o_dicionario_do_livro(boxes, lex, tmp_path):
    arquivo = tmp_path / "lexico.txt"
    assert vf.adicionar(lex, "Bca", arquivo)
    assert arquivo.read_text(encoding="utf-8") == "bca\n"
    assert vf.desconhecidas(boxes, lex) == []
    assert not vf.adicionar(lex, "bca", arquivo)  # já estava
    relido = vf.carregar_lexico("xx", arquivo)
    assert relido.conhece("bca") and not relido.sinaliza  # idioma sem lista não acusa nada


def test_recorte_da_palavra_tem_a_palavra_e_folga(imagem, boxes, lex):
    import numpy as np

    palavra = vf.desconhecidas(boxes, lex)[0]
    x1, y1, x2, y2 = vf.caixa_da_palavra(boxes, palavra.indices)
    recorte, (ox, oy) = vf.recorte_da_palavra(np.asarray(imagem), boxes, palavra.indices)
    assert ox < x1 and oy < y1
    assert recorte.shape[1] > x2 - x1 and recorte.shape[0] > y2 - y1


def test_lexico_portugues_do_core():
    pt = vf.carregar_lexico("pt")
    assert pt.sinaliza
    assert pt.conhece("estratégia") and pt.conhece("desenvolvimento")
    assert pt.conhece("Morphy")  # os nomes próprios do core entram junto
    assert not pt.conhece("desenvover")
