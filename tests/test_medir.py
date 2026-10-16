"""As funções puras de `ferramentas/medir.py`: casamento, FEN, linhas, ordem e o resumo."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import medir  # noqa: E402
from medir import DiagramaDaLeitura, Leitura  # noqa: E402

INICIAL = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR"


def test_casamento_corta_no_iou_minimo():
    verdade = [[0.0, 0.0, 1.0, 1.0]]
    # IoU de [0, 0, 1, x] com [0, 0, 1, 1] é x.
    assert medir.casar([[0.0, 0.0, 1.0, 0.51]], verdade) == [(0, 0)]
    assert medir.casar([[0.0, 0.0, 1.0, 0.49]], verdade) == []


def test_casamento_usa_cada_caixa_uma_vez_e_prefere_a_maior_sobreposicao():
    verdade = [[0, 0, 10, 10]]
    previstos = [[0, 0, 10, 8], [0, 0, 10, 10]]
    assert medir.casar(previstos, verdade) == [(1, 0)]


def test_fen_malformado_da_none():
    assert len(medir.casas(INICIAL)) == 64
    assert medir.casas(INICIAL + " w KQkq - 0 1") == medir.casas(INICIAL)
    assert medir.casas("8/8/8") is None
    assert medir.casas(INICIAL.replace("K", "X")) is None
    assert medir.casas("") is None


def test_dois_blocos_lado_a_lado_viram_uma_linha():
    unidas = medir.unir_por_linha([[0.6, 0.02, 0.9, 0.04], [0.1, 0.021, 0.4, 0.041],
                                   [0.1, 0.9, 0.2, 0.92]])
    assert unidas == [[0.1, 0.02, 0.9, 0.041], [0.1, 0.9, 0.2, 0.92]]


def test_discordancia():
    assert medir.discordancia([1, 2, 3], [1, 2, 3]) == 0.0
    assert medir.discordancia([1, 2, 3], [3, 2, 1]) == 1.0
    assert medir.discordancia([1, 2, 3], [1, 3, 2]) == pytest.approx(1 / 3)
    assert medir.discordancia([1], [1]) == 0.0


def _gabarito(**extra):
    g = {"estrutura_por": "Assistente", "revisado_por": "",
         "blocos": [
             {"id": "b0", "funcao": "cabecalho", "caixa_rel": [0.1, 0.02, 0.4, 0.04], "ordem": None},
             {"id": "b1", "funcao": "numero_de_pagina", "caixa_rel": [0.8, 0.02, 0.9, 0.04],
              "ordem": None},
             {"id": "b2", "funcao": "texto", "caixa_rel": [0.1, 0.1, 0.9, 0.2], "ordem": 1},
             {"id": "b3", "funcao": "texto", "caixa_rel": [0.1, 0.3, 0.9, 0.4], "ordem": 0},
             {"id": "b4", "funcao": "rodape", "caixa_rel": [0.1, 0.95, 0.9, 0.97], "ordem": None},
             {"id": "d0", "funcao": "diagrama", "caixa_rel": [0.2, 0.5, 0.6, 0.9], "ordem": 2}],
         "diagramas": [{"id": "d0", "fen": E4, "lado": "b", "fen_verificado": True,
                        "lado_verificado": True}],
         "linhas_corpo": [
             {"id": "l0", "bloco": "b2", "caixa_rel": [0.1, 0.1, 0.9, 0.2], "texto": "uma linha",
              "texto_verificado": True},
             {"id": "l1", "bloco": "b3", "caixa_rel": [0.1, 0.3, 0.9, 0.4], "texto": "outra",
              "texto_verificado": False}]}
    g.update(extra)
    return g


def test_comparar_pagina_margens_contam_rodape_e_numero():
    leitura = Leitura(linhas=[([0.1, 0.02, 0.9, 0.04], "Título 12")],
                      margens=[[0.1, 0.02, 0.9, 0.04], [0.1, 0.95, 0.9, 0.97]])
    m = medir.comparar_pagina(_gabarito(), leitura)["margens"]
    # O cabeçalho e o número, na mesma linha, viram um só; o rodapé é o outro.
    assert m == {"vp": 2, "fp": 0, "fn": 0}


def test_comparar_pagina_diagrama_casas_lado_e_falso():
    leitura = Leitura(diagramas=[DiagramaDaLeitura([0.2, 0.5, 0.6, 0.9], INICIAL, "w"),
                                 DiagramaDaLeitura([0.7, 0.5, 0.95, 0.9], INICIAL, "w")])
    d = medir.comparar_pagina(_gabarito(), leitura)["diagramas"]
    assert (d["verdade"], d["achados"], d["casados"]) == (1, 2, 1)
    assert d["detalhes"] == [{"id": "d0", "casas_erradas": 2, "fen_verificado": True,
                              "fen_igual_a_leitura": False, "lado_certo": False,
                              "lado_verificado": True, "confiavel": True}]


def test_comparar_pagina_ordem_pelo_bloco_e_cer_so_nas_verificadas():
    # Lidas na ordem da página (b2 em cima), mas o gabarito diz que b3 vem antes.
    leitura = Leitura(linhas=[([0.1, 0.1, 0.9, 0.2], "uma lirha"), ([0.1, 0.3, 0.9, 0.4], "xxx")])
    c = medir.comparar_pagina(_gabarito(), leitura)["corpo"]
    assert c["ordem_discordancia"] == 1.0
    assert (c["linhas_verificadas"], c["cer_erros"], c["cer_caracteres"]) == (1, 1, 9)


def test_linha_inventada_conta_como_sem_par():
    leitura = Leitura(linhas=[([0.1, 0.1, 0.9, 0.2], "uma linha"),
                              ([0.1, 0.02, 0.9, 0.04], "Título 12"),
                              ([0.3, 0.6, 0.5, 0.62], "poeira lida")])
    assert medir.comparar_pagina(_gabarito(), leitura)["linhas_sem_par"] == 1


def test_bloco_sem_ordem_vai_para_o_fim():
    g = _gabarito()
    g["blocos"][3]["ordem"] = None            # b3 sem ordem: vai depois de b2
    leitura = Leitura(linhas=[([0.1, 0.1, 0.9, 0.2], "a"), ([0.1, 0.3, 0.9, 0.4], "b")])
    assert medir.comparar_pagina(g, leitura)["corpo"]["ordem_discordancia"] == 0.0


def test_resumo_so_conta_fen_conferido_e_diz_o_que_falta():
    sem_conferir = _gabarito()
    sem_conferir["diagramas"][0]["fen_verificado"] = False
    sem_conferir["diagramas"][0]["lado_verificado"] = False
    leitura = Leitura(diagramas=[DiagramaDaLeitura([0.2, 0.5, 0.6, 0.9], INICIAL, "b")])
    paginas = {"i000": medir.comparar_pagina(_gabarito(), leitura),
               "i001": medir.comparar_pagina(sem_conferir, leitura)}
    r = medir.resumir(paginas)
    assert r["fen_verificados"] == "1/2"
    assert r["casas_erradas_por_diagrama"] == 2.0 and r["casas_erradas_provisorio"] == 2.0
    assert r["lado_certo"] == "1/1" and r["lado_certo_provisorio"] == "2/2"
    assert r["estado"].startswith("provisória: ")
    assert "estrutura revisada em 0/2" in r["estado"] and "FEN conferido em 1/2" in r["estado"]


def test_resumo_sem_fen_conferido_fica_sem_numero():
    g = _gabarito()
    g["diagramas"][0]["fen_verificado"] = False
    leitura = Leitura(diagramas=[DiagramaDaLeitura([0.2, 0.5, 0.6, 0.9], INICIAL, "b")])
    r = medir.resumir({"i000": medir.comparar_pagina(g, leitura)})
    assert r["casas_erradas_por_diagrama"] is None and r["casas_erradas_provisorio"] == 2.0


def _sem_pendencia():
    g = _gabarito(revisado_por="Usuário", verdade_versao=2,
                  conferencia_cega={"texto": {"aprovada": True, "verdade_versao": 2}})
    for ln in g["linhas_corpo"]:
        ln["texto_verificado"] = True
    g["diagramas"][0]["conferencia_cega"] = {"igual": True}
    return g


def test_resumo_valido_quando_nada_falta():
    g = _sem_pendencia()
    leitura = Leitura(diagramas=[DiagramaDaLeitura([0.2, 0.5, 0.6, 0.9], E4, "b")])
    r = medir.resumir({"i000": medir.comparar_pagina(g, leitura)})
    assert r["estado"] == "válida" and r["casas_erradas_por_diagrama"] == 0.0


def test_conferencia_cega_feita_numa_versao_velha_nao_vale():
    g = _sem_pendencia()
    g["verdade_versao"] = 3                  # o texto mudou depois da conferência
    leitura = Leitura(diagramas=[DiagramaDaLeitura([0.2, 0.5, 0.6, 0.9], E4, "b")])
    r = medir.resumir({"i000": medir.comparar_pagina(g, leitura)})
    assert r["estado"] == "provisória: sem conferência cega do texto aprovada e em dia"


def test_negativas_saem_a_parte_e_linhas_perdidas_contam():
    negativa = _gabarito(negativa=True)
    negativa["linhas_corpo"] = []
    lixo = Leitura(linhas=[([0.3, 0.6, 0.5, 0.62], "lixo"), ([0.3, 0.7, 0.5, 0.72], "lixo")])
    corpo = Leitura(linhas=[([0.1, 0.1, 0.9, 0.2], "uma linha"), ([0.3, 0.6, 0.5, 0.62], "x")])
    r = medir.resumir({"i000": medir.comparar_pagina(negativa, lixo),
                       "i001": medir.comparar_pagina(_gabarito(), corpo)})
    assert (r["linhas_sem_par_negativas"], r["paginas_negativas"]) == (2, 1)
    assert r["linhas_sem_par"] == 1          # só a da página de corpo
    assert r["linhas_perdidas"] == 1         # a l1 de i001 não foi lida
    assert r["fen_igual_a_leitura"] == "0/0"
