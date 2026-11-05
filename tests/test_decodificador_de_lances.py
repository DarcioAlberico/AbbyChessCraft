"""X-1 sem rebobinar: CA-X1.2, CA-X1.4 e a primeira metade de CA-X1.5. A linha da fila Lances."""

from __future__ import annotations

from dataclasses import dataclass

from abbychess import decodificador_de_lances as dl
from abbychess import texto as tx


@dataclass
class _Diagrama:
    id: str
    fen: str
    lido: bool = True


def _documento(*itens, funcao="texto"):
    """O documento de `itens`: str é uma linha; `_Diagrama`, o bloco dele; ("titulo", str), um
    título. Cada caractere vira um gid."""
    gid = 0
    chars = {}
    blocos = []
    diagramas = []
    for n, item in enumerate(itens):
        if isinstance(item, _Diagrama):
            diagramas.append(item)
            blocos.append(tx.Bloco(f"b{n}", None, "diagrama", (), item.id))
            continue
        qual, texto = item if isinstance(item, tuple) else (funcao, item)
        palavras = []
        for palavra in texto.split():
            gids = []
            for c in palavra:
                chars[gid] = c
                gids.append(gid)
                gid += 1
            palavras.append(tx.Palavra(tuple(gids)))
        blocos.append(tx.Bloco(f"b{n}", None, qual, (tx.Linha(tuple(palavras)),)))
    return tx.Documento(tuple(blocos), chars), diagramas


def _estados(*itens, chave="KQRBN", semente=None):
    documento, diagramas = _documento(*itens)
    saida = dl.decodificar(documento, diagramas, chave, semente)
    return [(t.impresso, t.estado) for t in saida.lances]


INICIAL = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"


def test_a_posicao_do_diagrama_anda_pelos_numeros():
    d = _Diagrama("d", INICIAL + " w - - 0 1")
    assert _estados(d, "1.e4 e5 2.Nf3 Nc6") == [("e4", "legal"), ("e5", "legal"), ("Nf3", "legal"),
                                               ("Nc6", "legal")]


def test_ca_x1_2_o_lance_impresso_errado_fica_com_marca_e_os_seguintes_sem_posicao():
    d = _Diagrama("d", INICIAL + " w - - 0 1")
    documento, diagramas = _documento(d, "1.e4 e5 2.Bf3 Nc6 3.d4")
    saida = dl.decodificar(documento, diagramas, "KQRBN")
    assert [(t.impresso, t.estado) for t in saida.lances] == [
        ("e4", "legal"), ("e5", "legal"), ("Bf3", "ilegal"), ("Nc6", "sem_posicao"),
        ("d4", "sem_posicao")]
    assert "não se joga aqui" in saida.ilegais[0].motivo
    assert documento.chars[saida.ilegais[0].gids[0]] == "B"


def test_o_numero_nao_entra_nos_gids_do_lance():
    documento, diagramas = _documento(_Diagrama("d", INICIAL), "12.e4")
    saida = dl.decodificar(documento, diagramas, "KQRBN")
    [lance] = saida.lances
    assert [documento.chars[g] for g in lance.gids] == ["e", "4"]
    assert [documento.chars[g] for g in lance.gids_do_numero] == ["1", "2", "."]


def test_ca_x1_4_variante_aninhada_nao_gera_marca_falsa():
    d = _Diagrama("d", INICIAL)
    estados = _estados(d, "1.e4 e5 (1...c5 2.Qh8 (2.Nf3)) 2.Nf3 Qh4")
    assert [e for _i, e in estados if e == "ilegal"] == []


def test_ca_x1_4_a_pagina_que_comeca_no_meio_da_partida_nao_gera_marca():
    assert all(e == "sem_posicao" for _i, e in _estados("14.Qh8 Kf7 15.Rxa8"))


def test_ca_x1_5_as_alternativas_com_ponto_e_virgula_nao_geram_marca_falsa():
    d = _Diagrama("d", "r1bqkb1r/1ppppppp/2n2n2/8/4P3/2N5/PPPP1PPP/R1BQKBNR")
    estados = _estados(d, "12...Ra6; 12...Ra7; 12...Nb6 13.Qc2")
    assert [e for _i, e in estados if e == "ilegal"] == []


def test_o_numero_que_volta_perde_a_posicao():
    d = _Diagrama("d", INICIAL)
    assert _estados(d, "1.e4 e5 2.Nf3 1...c5 2.Qh8") == [
        ("e4", "legal"), ("e5", "legal"), ("Nf3", "legal"), ("c5", "sem_posicao"),
        ("Qh8", "sem_posicao")]


def test_o_lance_solto_na_prosa_nao_conta_nem_perde_a_posicao():
    d = _Diagrama("d", INICIAL)
    assert _estados(d, "1.e4 o peão de d5 é forte 1...e5") == [
        ("e4", "legal"), ("d5", "sem_posicao"), ("e5", "legal")]


def test_o_lance_das_brancas_sem_numero_perde_a_posicao():
    d = _Diagrama("d", INICIAL)
    assert _estados(d, "1.e4 e5 Nf3 Qh8") == [("e4", "legal"), ("e5", "legal"), ("Nf3", "sem_posicao"),
                                              ("Qh8", "sem_posicao")]


def test_a_hipotese_da_posicao_inicial_vale_com_dois_lances_legais():
    documento, diagramas = _documento("1.e4 e5 2.Nf3")
    saida = dl.decodificar(documento, diagramas, "KQRBN")
    assert [t.estado for t in saida.lances] == ["legal"] * 3
    assert saida.por_semente() == {"inicial": 3}


def test_a_hipotese_que_falha_nao_marca_nada():
    assert _estados("1.Qh8 Kf7 2.Rxa8") == [("Qh8", "sem_posicao"), ("Kf7", "sem_posicao"),
                                            ("Rxa8", "sem_posicao")]
    assert all(e == "sem_posicao" for _i, e in _estados("1.e4 Qh2 2.Rxa8"))


def test_a_hipotese_de_um_lance_so_nao_conta():
    assert _estados("1.e4") == [("e4", "sem_posicao")]


def test_o_titulo_perde_a_posicao():
    d = _Diagrama("d", INICIAL)
    assert _estados(d, "1.e4", ("titulo", "Capítulo"), "2.Qh8") == [("e4", "legal"),
                                                                    ("Qh8", "sem_posicao")]


def test_o_cabecalho_nao_conta():
    d = _Diagrama("d", INICIAL)
    assert _estados(d, "1.e4", ("cabecalho", "h8 d3"), "1...e5") == [("e4", "legal"), ("e5", "legal")]


def test_a_semente_da_pagina_anterior():
    documento, diagramas = _documento("1.e4 e5 2.Nf3")
    final = dl.decodificar(documento, diagramas, "KQRBN").final
    assert final[1] == (2, True)
    seguinte, _d = _documento("2...Nc6 3.Bb5")
    saida = dl.decodificar(seguinte, [], "KQRBN", semente=final)
    assert [t.estado for t in saida.lances] == ["legal", "legal"]
    assert saida.por_semente() == {"anterior": 2}


def test_o_diagrama_nao_lido_nao_e_semente():
    d = _Diagrama("d", "", lido=False)
    assert _estados(d, "12.Qh8") == [("Qh8", "sem_posicao")]


def test_a_posicao_ilegal_do_diagrama_nao_e_semente():
    d = _Diagrama("d", "8/8/8/8/8/8/8/8")
    assert _estados(d, "1.e4") == [("e4", "sem_posicao")]


def test_o_xeque_que_nao_e_xeque_e_ilegal():
    d = _Diagrama("d", INICIAL)
    documento, diagramas = _documento(d, "1.e4+")
    assert "xeque" in dl.decodificar(documento, diagramas, "KQRBN").ilegais[0].motivo


def test_com_as_letras_em_portugues():
    d = _Diagrama("d", INICIAL)
    assert _estados(d, "1.e4 e5 2.Cf3 Cc6", chave="RDTBC")[-1] == ("Cc6", "legal")


# ------------------------------------------------------------------
# As linhas da fila
# ------------------------------------------------------------------
def test_a_fila_tem_as_linhas_com_lance_as_entre_duas_e_as_vizinhas(monkeypatch):
    documento, _d = _documento("longe", "prosa só aqui", "1.e4 e5", "uma frase no meio", "2.Nf3 Nc6",
                               "fim da prosa", "longe")
    linhas = dl.linhas_da_fila(documento, "KQRBN")
    assert [ln.texto for ln in linhas] == ["prosa só aqui", "1.e4 e5", "uma frase no meio",
                                           "2.Nf3 Nc6", "fim da prosa"]
    monkeypatch.setattr(dl, "COM_AS_VIZINHAS", False)
    linhas = dl.linhas_da_fila(documento, "KQRBN")
    assert [ln.texto for ln in linhas] == ["1.e4 e5", "uma frase no meio", "2.Nf3 Nc6"]


def test_sem_lance_a_fila_e_vazia():
    documento, _d = _documento("prosa", "mais prosa")
    assert dl.linhas_da_fila(documento, "KQRBN") == []


def test_o_cabecalho_nao_entra_na_fila():
    documento, _d = _documento(("cabecalho", "1.e4"), "prosa")
    assert dl.linhas_da_fila(documento, "KQRBN") == []


def test_a_linha_separa_o_que_e_lance_da_prosa():
    documento, _d = _documento("depois de 1.e4+! ±")
    [linha] = dl.linhas_da_fila(documento, "KQRBN")
    assert "".join(documento.chars[g] for g in linha.gids_de_lance) == "1.e4+!±"


def test_lances_por_conferir():
    documento, _d = _documento("1.e4 e5")
    confirmados = {g for g, c in documento.chars.items() if g < 4}
    assert dl.lances_por_conferir(documento, set(), "KQRBN") == 2
    assert dl.lances_por_conferir(documento, confirmados, "KQRBN") == 1
    assert dl.lances_por_conferir(documento, set(documento.chars), "KQRBN") == 0
