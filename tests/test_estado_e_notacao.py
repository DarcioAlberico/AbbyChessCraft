"""O estado da página e a notação validados na entrada (SPEC-qualidade Q-P9): um valor que
o programa não conhece não passa calado por "reconhecida" nem por "letras"."""
from __future__ import annotations

import json

import pytest
from core.box_model import BoxEntry

from abbychess.modelo import NAO_RECONHECIDA
from abbychess.projeto import ProjetoDeLivro, ProjetoInvalido


def test_a_notacao_desconhecida_nao_abre_e_diz_o_campo(projeto):
    arquivo = projeto.pasta / "projeto.json"
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    dados["notacao"] = "figurina"                       # a digitação errada de "figurinas"
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    antes = arquivo.read_bytes()

    with pytest.raises(ProjetoInvalido, match="notacao"):
        ProjetoDeLivro.abrir(projeto.pasta)

    assert arquivo.read_bytes() == antes


def test_o_estado_desconhecido_faz_a_pagina_ilegivel_e_ela_fica_guardada(projeto):
    projeto.salvar_pagina(0, [BoxEntry(char="a", x1=10, y1=10, x2=30, y2=40, source="net",
                                       confidence=0.5)], reconhecida=True)
    assert projeto.fechar()
    arquivo = projeto.pasta / "paginas" / f"p{projeto.pid_da_pagina(0)}.json"
    bruto = json.loads(arquivo.read_text(encoding="utf-8"))
    bruto["estado"] = "reconhecido"                     # não é estado nenhum
    arquivo.write_text(json.dumps(bruto), encoding="utf-8")

    aberto = ProjetoDeLivro.abrir(projeto.pasta)
    try:
        assert aberto.carregar_modelo(0) is None
        assert aberto.resumo.estado_da_pagina(0) == NAO_RECONHECIDA
        [guardado] = sorted((projeto.pasta / "paginas").glob("p*.corrompido*.json"))
        assert json.loads(guardado.read_text(encoding="utf-8"))["estado"] == "reconhecido"
    finally:
        aberto.fechar()
