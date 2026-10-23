"""A sequência do livro (SPEC §12.4, passo L, rodada 1a): o tipo puro, o JSON, a montagem
a partir de um projeto da v2 e a seleção de páginas."""

from __future__ import annotations

import pytest

from abbychess import sequencia as sq
from abbychess.sequencia import Apagada, Entrada, Sequencia


def test_a_posicao_e_o_indice_na_sequencia():
    s = Sequencia.do_livro([7, 3, 9])
    assert len(s) == 3 and s.pids == [7, 3, 9]
    assert s.pid_em(1) == 3 and s.posicao_de(9) == 2 and s.posicao_de(42) is None
    assert s.entrada_de(3) == Entrada(3, "livro", 1)
    with pytest.raises(IndexError):
        s.pid_em(3)


def test_pid_repetido_e_recusado():
    with pytest.raises(ValueError, match="repetido"):
        Sequencia.do_livro([1, 1])
    with pytest.raises(ValueError, match="apagadas"):
        Sequencia((Entrada(1),), (Apagada(Entrada(1), 0),))


@pytest.mark.parametrize("campos, motivo", [
    ({"giro": 45}, "giro"),
    ({"metade": "meio"}, "metade"),
    ({"quadro": (10, 0, 10, 5)}, "quadro"),
    ({"fonte": "C:/outro.pdf"}, "fonte"),
    ({"fonte": "inseridas/../../segredo.pdf"}, "fonte"),     # nada fora da pasta do projeto
    ({"fonte": "inseridas/a/b.png"}, "fonte"),
    ({"fonte": "inseridas\\..\\x.png"}, "fonte"),
    ({"pagina": -1}, "negativos"),
])
def test_entrada_ruim_e_recusada(campos, motivo):
    with pytest.raises(ValueError, match=motivo):
        Entrada(1, **campos)


def test_o_json_vai_e_volta():
    s = Sequencia((Entrada(5, "livro", 0), Entrada(8, "inseridas/ab12.png", 0, giro=90),
                   Entrada(9, "livro", 2, quadro=(0, 0, 1200, 1700), metade="esquerda",
                           angulo=-0.4)),
                  (Apagada(Entrada(6, "livro", 1), 1),))
    bruto = s.para_json()
    assert bruto["entradas"][0] == {"pid": 5, "fonte": "livro", "pagina": 0}   # enxuto
    assert Sequencia.de_json(bruto) == s


def test_intacta_so_sem_quadro_giro_nem_angulo():
    assert Entrada(1).do_livro_intacta
    for campos in ({"giro": 180}, {"quadro": (0, 0, 5, 5)}, {"angulo": 0.3},
                   {"fonte": "inseridas/x.pdf"}):
        assert not Entrada(1, **campos).do_livro_intacta, campos
    assert Entrada(1, angulo=0.0).do_livro_intacta     # o ângulo à mão zero não gira


def test_com_entrada_troca_so_a_do_pid():
    s = Sequencia.do_livro([1, 2])
    girada = s.com_entrada(Entrada(2, "livro", 1, giro=270))
    assert girada.entradas[1].giro == 270 and s.entradas[1].giro == 0   # imutável
    with pytest.raises(KeyError):
        s.com_entrada(Entrada(9))


# ----------------------------------------------------------------------
# A montagem a partir da v2 (CA-12.7, a parte pura)
# ----------------------------------------------------------------------

def test_da_v2_mantem_os_pids_gravados_e_da_novos_acima_de_todos():
    s, proximo = sq.da_v2(6, {0: 0, 2: 5, 4: 1}, indices_v1=(), proximo_pid=6)
    assert s.pids == [0, 6, 5, 7, 1, 8] and proximo == 9
    assert [e.pagina for e in s.entradas] == list(range(6))
    assert all(e.fonte == "livro" for e in s.entradas)


def test_da_v2_a_pagina_v1_nao_migrada_fica_com_pid_igual_ao_indice():
    s, proximo = sq.da_v2(5, {1: 7}, indices_v1=(3,), proximo_pid=2)
    assert s.pids == [8, 7, 9, 3, 10]                      # os novos, acima do 7 gravado
    assert proximo == 11


def test_da_v2_o_contador_alto_vale():
    s, proximo = sq.da_v2(2, {}, indices_v1=(), proximo_pid=40)
    assert s.pids == [40, 41] and proximo == 42


def test_da_v2_recusa_pid_gravado_repetido():
    with pytest.raises(ValueError):
        sq.da_v2(3, {0: 4, 1: 4}, indices_v1=(), proximo_pid=0)


# ----------------------------------------------------------------------
# A seleção (CA-12.15, a parte pura)
# ----------------------------------------------------------------------

@pytest.mark.parametrize("texto, posicoes", [
    ("todas", [0, 1, 2, 3, 4, 5, 6]),
    ("ímpares", [0, 2, 4, 6]),                   # as páginas 1, 3, 5, 7
    ("Impares", [0, 2, 4, 6]),
    ("pares", [1, 3, 5]),
    ("3-5, 7", [2, 3, 4, 6]),
    ("7, 3–4, 3", [2, 3, 6]),                    # travessão, ordem e repetição
    ("2", [1]),
])
def test_a_selecao_da_posicoes_do_livro(texto, posicoes):
    assert sq.selecao(texto, 7) == posicoes


@pytest.mark.parametrize("texto, motivo", [
    ("", "quais"), ("5-3", "contrário"), ("0", "fora"), ("6-9", "fora"), ("a-b", "entendi"),
])
def test_a_selecao_ruim_diz_o_motivo(texto, motivo):
    with pytest.raises(ValueError, match=motivo):
        sq.selecao(texto, 7)


def test_a_selecao_segue_a_ordem_do_livro_depois_de_reordenar():
    reordenada = Sequencia.do_livro([10, 11, 12, 13])
    reordenada = Sequencia(tuple(reordenada.entradas[i] for i in (2, 0, 3, 1)))
    assert sq.pids_da_selecao(reordenada, sq.selecao("ímpares", 4)) == [12, 13]
