"""A catraca de qualidade no portão (R-3): CA-R3.1, CA-R3.2, CA-R3.3 sem a parte por classe e
CA-R3.5. As regras rodam na rápida, sobre números fabricados; a medida, no portão."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import catraca  # noqa: E402

BASE = {"cer_erros": 100, "cer_caracteres": 9000, "cer_corpo": 0.0111, "casas_erradas": 0,
        "diagramas_casados": 7, "diagramas_falsos": 1, "linhas_perdidas": 1, "linhas_sem_par": 5,
        "pendentes": 400}


def test_o_mesmo_resultado_passa():
    assert catraca.violacoes(BASE, dict(BASE)) == []


def test_ate_a_tolerancia_passa_e_alem_dela_reprova():
    assert catraca.violacoes(BASE, {**BASE, "cer_erros": 102}) == []
    assert "103 erros" in catraca.violacoes(BASE, {**BASE, "cer_erros": 103})[0]


@pytest.mark.parametrize("campo, valor", [("casas_erradas", 1), ("linhas_perdidas", 2),
                                          ("diagramas_casados", 6)])
def test_casa_linha_e_diagrama_nao_tem_tolerancia(campo, valor):
    assert len(catraca.violacoes(BASE, {**BASE, campo: valor})) == 1


def test_melhorar_nao_reprova():
    assert catraca.violacoes(BASE, {**BASE, "cer_erros": 50, "linhas_perdidas": 0}) == []


def test_sem_o_modelo_a_medida_nao_vale():
    assert "rede" in catraca.falta_o_modelo({"rede": False, "base": 500000})
    assert "base" in catraca.falta_o_modelo({"rede": True, "base": 0})
    assert catraca.falta_o_modelo({"rede": True, "base": 500000}) is None


def test_os_numeros_saem_do_json_da_medida():
    pagina = {"corpo": {"cer_erros": 3, "cer_caracteres": 100},
              "diagramas": {"casados": 1, "detalhes": [{"casas_erradas": 2},
                                                       {"casas_erradas": None}]}}
    resultado = {"paginas": {"i020": pagina, "i021": pagina},
                 "resumo": {"cer_corpo": 0.03, "diagramas_falsos": 0, "linhas_perdidas": 4,
                            "linhas_sem_par": 1, "pendentes": 9, "lote_s": 70.0}}
    assert catraca.numeros(resultado) == {
        "cer_erros": 6, "cer_caracteres": 200, "cer_corpo": 0.03, "casas_erradas": 4,
        "diagramas_casados": 2, "diagramas_falsos": 0, "linhas_perdidas": 4, "linhas_sem_par": 1,
        "pendentes": 9}


def test_a_chave_muda_com_o_gabarito(tmp_path, monkeypatch):
    monkeypatch.setattr(catraca, "_raiz_do_core", lambda: tmp_path)
    (tmp_path / catraca.LIVRO).mkdir()
    for indice in catraca.INDICES:
        (tmp_path / catraca.LIVRO / f"i{indice:03d}.json").write_text("{}", encoding="utf-8")
    antes = catraca.chave(tmp_path)
    (tmp_path / catraca.LIVRO / "i020.json").write_text('{"x": 1}', encoding="utf-8")
    assert catraca.chave(tmp_path)["gabaritos"] != antes["gabaritos"]
    assert antes["normalizacao"] == catraca.VERSAO_DA_NORMALIZACAO


@pytest.mark.livro_real
@pytest.mark.timeout(900)
def test_as_sete_paginas_nao_pioram_e_duas_rodadas_dao_o_mesmo():
    from tests.livros import PASTA_DOS_PDFS

    if not sorted(PASTA_DOS_PDFS.glob("Xadrez Vitorioso*/*.pdf")):
        pytest.skip("o PDF do Xadrez Vitorioso não está nesta máquina")
    falta = catraca.falta_o_modelo(catraca.estado_do_leitor_global())
    assert falta is None, falta
    referencia = json.loads(catraca.REFERENCIA.read_text(encoding="utf-8"))
    primeira = catraca.medir_agora()
    assert primeira["chave"] == referencia["chave"], "a chave mudou: ferramentas/catraca.py --remedir"
    assert catraca.violacoes(referencia["numeros"], primeira["numeros"]) == []
    assert catraca.medir_agora() == primeira, "CA-R3.5: duas rodadas no mesmo commit diferem"
