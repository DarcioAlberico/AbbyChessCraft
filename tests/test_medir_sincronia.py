"""`ferramentas/medir_sincronia.py` sobre gabaritos e leituras fabricados (CA-X1.3, CA-X1.7, CA-F4.11)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import medir_sincronia as ms  # noqa: E402

INICIAL = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"


def _pagina(*itens):
    documento, diagramas = ms.documento_de_linhas(itens)
    return ms.PaginaDaVerdade("p", documento, diagramas, [i for i in itens if isinstance(i, str)])


def test_o_teto_por_pagina_e_por_seguimento():
    p1 = _pagina(ms._Diagrama("d", INICIAL), "1.e4 e5 2.Nf3")
    p2 = _pagina("2...Nc6 3.Bb5")
    teto = ms.teto_de_cobertura([p1, p2], "KQRBN")
    assert teto["tokens_de_lance"] == 5
    assert teto["com_posicao_por_pagina"] == 3 and teto["cobertura_por_pagina"] == 0.6
    assert teto["com_posicao_por_seguimento"] == 5 and teto["cobertura_por_seguimento"] == 1.0


def test_ca_x1_7_o_lance_longo_e_contado():
    assert ms.teto_de_cobertura([_pagina("depois e2-e4 e d7-d5")], "KQRBN")["lances_longos"] == 2


def test_o_gabarito_vira_pagina_com_o_diagrama_na_ordem():
    g = {"blocos": [{"id": "b1", "funcao": "texto", "ordem": 2},
                    {"id": "d0", "funcao": "diagrama", "ordem": 1},
                    {"id": "x", "funcao": "cabecalho", "ordem": 0}],
         "linhas_corpo": [{"bloco": "b1", "texto": "1.e4 e5"}],
         "diagramas": [{"id": "d0", "fen": INICIAL}]}
    pagina = ms.pagina_do_gabarito(g, "i001")
    assert pagina.linhas == ["1.e4 e5"]
    assert [b.diagrama_id for b in pagina.documento.blocos] == ["d0", None]


def test_a_referencia_sem_as_linhas_vazias():
    assert ms.pagina_de_referencia("a\n\nb\n", "n").linhas == ["a", "b"]


def _ler(*itens):
    documento, diagramas = ms.documento_de_linhas(itens)
    return documento, diagramas


def test_o_sinal_na_leitura_conta_errado_e_marcado():
    verdade = ["1.e4 e5 2.Nf3 Nc6"]
    documento, diagramas = _ler(ms._Diagrama("d", INICIAL), "1.e4 e5 2.Bf3 Nc6")
    s = ms.sinal_na_leitura(verdade, documento, diagramas, "KQRBN")
    assert s["lances"] == 4 and s["errados"] == 1 and s["errados_de_forma_valida"] == 1
    assert s["errados_marcados"] == 1 and s["certos_marcados"] == 0
    assert s["ilegais_lidos"] == 1


def test_sem_erro_o_alarme_nao_toca():
    verdade = ["1.e4 e5"]
    documento, diagramas = _ler(ms._Diagrama("d", INICIAL), "1.e4 e5")
    s = ms.sinal_na_leitura(verdade, documento, diagramas, "KQRBN")
    assert s["certos_marcados"] == 0 and s["errados"] == 0


def test_ca_f4_11_a_linha_fora_da_fila_e_contada():
    verdade = ["1.e4 e5", "prosa sem nada"]
    documento, diagramas = _ler("prosa sem nada")
    s = ms.sinal_na_leitura(verdade, documento, diagramas, "KQRBN")
    assert s["fora_da_fila"] == 2 and s["errados_fora_da_fila"] == 2


def test_o_ponto_de_parada():
    livro = {"teto": {"tokens_de_lance": 10, "cobertura_por_pagina": 0.2,
                      "cobertura_por_seguimento": 0.4},
             "leitura": {"lances": 100, "errados": 0, "certos_marcados": 1}}
    assert ms.ponto_de_parada({"a": livro})["x1_liberado"] is True
    alto = {**livro, "leitura": {"lances": 100, "errados": 0, "certos_marcados": 9}}
    assert ms.ponto_de_parada({"a": alto})["x1_liberado"] is False
    baixo = {"teto": {"tokens_de_lance": 10, "cobertura_por_pagina": 0.1,
                      "cobertura_por_seguimento": 0.1}}
    assert ms.ponto_de_parada({"a": baixo})["x1_liberado"] is False


def test_o_json_nao_leva_texto_de_livro():
    verdade = ["PalavraDoLivro 1.e4"]
    documento, diagramas = _ler("PalavraDoLivro 1.e4")
    s = ms.sinal_na_leitura(verdade, documento, diagramas, "KQRBN")
    assert "PalavraDoLivro" not in repr(s)
