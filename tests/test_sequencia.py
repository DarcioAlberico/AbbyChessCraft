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
    s, proximo = sq.da_v2(6, {0: 0, 2: 5, 4: 1}, proximo_pid=6)
    assert s.pids == [0, 6, 5, 7, 1, 8] and proximo == 9
    assert [e.pagina for e in s.entradas] == list(range(6))
    assert all(e.fonte == "livro" for e in s.entradas)


def test_da_v2_o_contador_alto_vale():
    s, proximo = sq.da_v2(2, {}, proximo_pid=40)
    assert s.pids == [40, 41] and proximo == 42


def test_da_v2_recusa_pid_gravado_repetido():
    with pytest.raises(ValueError):
        sq.da_v2(3, {0: 4, 1: 4}, proximo_pid=0)


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


def test_mover_para_o_comeco_e_para_o_fim():
    s = Sequencia.do_livro(range(5))
    assert s.mover([3], -1).pids == [3, 0, 1, 2, 4]
    assert s.mover([0, 1], 4).pids == [2, 3, 4, 0, 1]
    assert s.mover([0, 1, 2, 3], 4).pids == [4, 0, 1, 2, 3]   # todas menos uma
    with pytest.raises(ValueError, match="referência"):
        s.mover([1, 2], 2)
    with pytest.raises(ValueError):
        s.mover([1], 5)


def test_restaurar_uma_das_apagadas_juntas_volta_ao_lugar_certo():
    s = Sequencia.do_livro(range(10)).apagar([2, 6])
    assert s.restaurar([6]).pids == [0, 1, 3, 4, 5, 6, 7, 8, 9]
    assert s.restaurar([2]).pids == [0, 1, 2, 3, 4, 5, 7, 8, 9]
    assert s.restaurar([2]).restaurar([6]).pids == list(range(10))


@pytest.mark.parametrize("semente", range(5))
def test_restaurar_tudo_ou_da_mais_nova_para_a_mais_velha_volta_a_ordem(semente):
    """Apagadas em várias vezes: restaurar todas juntas, ou cada vez da mais nova para a mais
    velha (como um desfazer), devolve a ordem exata."""
    import random

    sorteio = random.Random(semente)
    for _ in range(200):
        n = sorteio.randint(3, 12)
        t, lotes = Sequencia.do_livro(range(n)), []
        for _ in range(sorteio.randint(2, 4)):
            if len(t) < 2:
                break
            parte = sorteio.sample(t.pids, sorteio.randint(1, len(t) - 1))
            t, lotes = t.apagar(parte), lotes + [parte]
        assert t.restaurar([p for lote in lotes for p in lote]).pids == list(range(n))
        volta = t
        for lote in reversed(lotes):
            volta = volta.restaurar(lote)
        assert volta.pids == list(range(n))


def test_a_ancora_vai_e_volta_no_json():
    s = Sequencia.do_livro(range(4)).apagar([2])
    assert s.apagadas[0].depois_de == 1
    assert Sequencia.de_json(s.para_json()) == s


def test_restaurar_com_o_livro_mais_curto_vai_ao_fim():
    s = Sequencia.do_livro(range(6)).apagar([5]).apagar([2, 3, 4])
    assert s.restaurar([5]).pids == [0, 1, 5]
    with pytest.raises(ValueError, match="apagadas"):
        s.restaurar([0])


def test_inserir_fora_do_livro_e_recusado():
    s = Sequencia.do_livro(range(3))
    nova = Entrada(9, "inseridas/a.png", 0)
    assert s.inserir([nova], 3).pids == [0, 1, 2, 9] and s.inserir([nova], 0).pid_em(0) == 9
    with pytest.raises(ValueError):
        s.inserir([nova], 4)


def test_a_selecao_segue_a_ordem_do_livro_depois_de_reordenar():
    reordenada = Sequencia.do_livro([10, 11, 12, 13])
    reordenada = Sequencia(tuple(reordenada.entradas[i] for i in (2, 0, 3, 1)))
    assert sq.pids_da_selecao(reordenada, sq.selecao("ímpares", 4)) == [12, 13]


# ----------------------------------------------------------------------
# As regras que a mutação achou sem teste (Q9, CA-Q-M1)
# ----------------------------------------------------------------------

@pytest.mark.parametrize("fonte", ["inseridas/a\\b.png", "inseridas/C:x.png"])
def test_a_inserida_com_um_caminho_do_windows_no_nome_e_recusada(fonte):
    with pytest.raises(ValueError, match="fonte"):
        Entrada(1, fonte=fonte)


def test_o_quadro_sem_altura_e_recusado():
    with pytest.raises(ValueError, match="quadro"):
        Entrada(1, quadro=(0, 10, 5, 10))


def test_o_quadro_e_o_tamanho_em_lista_viram_tupla_e_a_entrada_serve_de_chave():
    """O JSON traz listas; a entrada é chave do cache das imagens."""
    e = Entrada(1, quadro=[0, 0, 5, 5], tamanho=[100, 200])
    assert e.quadro == (0, 0, 5, 5) and e.tamanho == (100, 200)
    assert {e: "a"}[Entrada(1, quadro=(0, 0, 5, 5), tamanho=(100, 200))] == "a"


def test_a_entrada_so_com_o_pid_e_a_primeira_pagina_do_livro():
    assert Entrada(4) == Entrada(4, "livro", 0) == Entrada.de_json({"pid": 4})
    assert Entrada(4).pagina == 0
    assert Apagada.de_json({"pid": 4}) == Apagada(Entrada(4), 0, None)


def test_a_sequencia_e_a_apagada_nao_mudam_no_lugar():
    """Imutáveis: o desfazer guarda a de antes e a de depois, e uma não pode mudar a outra."""
    from dataclasses import FrozenInstanceError

    s = Sequencia.do_livro([1, 2]).apagar([2])
    with pytest.raises(FrozenInstanceError):
        s.entradas = ()
    with pytest.raises(FrozenInstanceError):
        s.apagadas[0].posicao = 5


def test_a_pagina_fora_do_livro_diz_o_numero_que_o_usuario_ve():
    s = Sequencia.do_livro([7, 3, 9])
    for chamar in (s.pid_em, s.entrada_em):
        with pytest.raises(IndexError, match=r"^Página 4 fora de 1\.\.3$"):
            chamar(3)
        with pytest.raises(IndexError, match=r"^Página 0 fora de 1\.\.3$"):
            chamar(-1)
    with pytest.raises(ValueError, match=r"^posição 5 fora do livro$"):
        s.inserir([Entrada(20)], 4)
    with pytest.raises(ValueError, match="não há a página 4 "):
        s.mover([7], 3)
    with pytest.raises(ValueError, match="não há a página -1 "):
        s.mover([7], -2)


def test_a_primeira_pagina_nao_serve_de_referencia_se_ela_mesma_se_move():
    with pytest.raises(ValueError, match="referência"):
        Sequencia.do_livro([7, 3, 9]).mover([7, 9], 0)


def test_as_apagadas_fora_de_uma_lista_sao_recusadas():
    with pytest.raises(TypeError):
        Sequencia.de_json({"entradas": [], "apagadas": {}})


def test_a_pagina_restaurada_volta_ao_comeco_quando_a_ancora_dela_era_a_primeira():
    """A 2 saiu depois da 1; a 1 saiu depois, sendo a primeira. Só a 2 volta: a âncora dela
    (a 1) está apagada e era a primeira, então a 2 vai para o começo, antes da 3."""
    s = Sequencia.do_livro([1, 2, 3]).apagar([2]).apagar([1])
    assert s.restaurar([2]).pids == [2, 3]


def test_a_ancora_que_nao_existe_volta_pela_posicao_gravada():
    """Um `projeto.json` de fora com a âncora num pid que não há: vale a posição gravada."""
    s = Sequencia.de_json({"entradas": [{"pid": 1}, {"pid": 2}],
                           "apagadas": [{"pid": 5, "posicao": 1, "depois_de": 99}]})
    assert s.restaurar([5]).pids == [1, 5, 2]


def test_as_ancoras_em_ciclo_nao_travam_o_restaurar():
    """Duas apagadas que se ancoram uma na outra (não acontece, só num JSON estragado): a mais
    nova volta pela posição gravada, e a outra logo depois dela."""
    s = Sequencia.de_json({"entradas": [{"pid": 1}],
                           "apagadas": [{"pid": 5, "posicao": 0, "depois_de": 6},
                                        {"pid": 6, "posicao": 0, "depois_de": 5}]})
    assert s.restaurar([5, 6]).pids == [6, 5, 1]


def test_as_paginas_novas_da_v2_ganham_pid_acima_dos_gravados():
    s, proximo = sq.da_v2(4, {0: 10, 2: 11}, proximo_pid=3)
    assert s.pids == [10, 12, 11, 13] and proximo == 14
