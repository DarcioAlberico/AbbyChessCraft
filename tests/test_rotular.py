"""A ida e volta do texto dos gabaritos (`ferramentas/rotular.py`), com dados sintéticos."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import rotular  # noqa: E402


@pytest.fixture
def pastas(tmp_path, monkeypatch):
    verdade, faixas = tmp_path / "verdade", tmp_path / "faixas"
    (verdade / "sint").mkdir(parents=True)
    monkeypatch.setattr(rotular, "VERDADE", verdade)
    monkeypatch.setattr(rotular, "FAIXAS", faixas)
    gabarito = {
        "verdade_versao": 1, "rotulado_por": "",
        "blocos": [{"id": "b1", "funcao": "texto", "caixa_rel": [0.1, 0.1, 0.9, 0.2],
                    "texto_impresso": "lido um\nlido dois"}],
        "linhas_corpo": [
            {"id": "l1", "bloco": "b1", "caixa_rel": [0.1, 0.1, 0.9, 0.15], "texto": "lido um",
             "texto_verificado": False},
            {"id": "l2", "bloco": "b1", "caixa_rel": [0.1, 0.15, 0.9, 0.2], "texto": "lido dois",
             "texto_verificado": False}]}
    (verdade / "sint" / "i000.json").write_text(json.dumps(gabarito), encoding="utf-8")
    return verdade, faixas


def test_ida_e_volta_junta_as_linhas_do_bloco_e_assina(pastas):
    verdade, faixas = pastas
    [txt] = rotular.texto_exportar("sint")
    linhas = txt.read_text(encoding="utf-8").splitlines()
    assert linhas[1] == "!l1\tlido um" and linhas[2] == "!l2\tlido dois"
    txt.write_text("\n".join([linhas[0], "l1\tcerto um", "!l2\tlido dois"]) + "\n",
                   encoding="utf-8")

    assert rotular.texto_importar("sint", "Usuário") == {"i000": 1}
    g = json.loads((verdade / "sint" / "i000.json").read_text(encoding="utf-8"))
    assert [ln["texto_verificado"] for ln in g["linhas_corpo"]] == [True, False]
    assert g["blocos"][0]["texto_impresso"] == "certo um\nlido dois"
    assert g["verdade_versao"] == 2 and g["rotulado_por"] == "Usuário"


def test_importar_sem_mudanca_nao_sobe_a_versao(pastas):
    verdade, _ = pastas
    rotular.texto_exportar("sint")
    rotular.texto_importar("sint", "Usuário")
    g = json.loads((verdade / "sint" / "i000.json").read_text(encoding="utf-8"))
    assert g["verdade_versao"] == 1 and g["rotulado_por"] == ""


def test_importar_exige_quem_verificou(pastas):
    rotular.texto_exportar("sint")
    with pytest.raises(SystemExit, match="--por"):
        rotular.texto_importar("sint", " ")


def test_exportar_nao_sobrescreve_trabalho_nao_importado(pastas):
    verdade, _ = pastas
    [txt] = rotular.texto_exportar("sint")
    futuro = time.time() + 60
    os.utime(txt, (futuro, futuro))
    with pytest.raises(SystemExit, match="mais novo"):
        rotular.texto_exportar("sint")
    assert rotular.texto_exportar("sint", forcar=True) == [txt]


def test_id_desconhecido_e_recusado(pastas):
    [txt] = rotular.texto_exportar("sint")
    txt.write_text("l9\tnão existe\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="desconhecido"):
        rotular.texto_importar("sint", "Usuário")


def test_concordancia_e_validacao():
    a = {"linhas_corpo": [{"texto": "abcdefghij"}]}
    b = {"linhas_corpo": [{"texto": "abcdefghiX"}]}
    assert rotular.concordancia(a, a) == 1.0
    assert rotular.concordancia(a, b) == pytest.approx(0.9)
    problemas = rotular.validar({"blocos": [{"id": "x", "funcao": "outra", "caixa_rel": [0, 0, 2, 1]}]})
    assert any("função desconhecida" in p for p in problemas)
    assert any("dentro de 0–1" in p for p in problemas)


def _valido():
    return {"livro": "sint", "pdf_sha256": "x", "indice_pdf": 0, "verdade_versao": 1,
            "rotulado_por": "", "revisado_por": "", "papel": 250,
            "blocos": [{"id": "b0", "funcao": "texto", "caixa_rel": [0.1, 0.1, 0.9, 0.2], "ordem": 0},
                       {"id": "b1", "funcao": "legenda", "caixa_rel": [0.1, 0.6, 0.5, 0.65],
                        "ordem": 2},
                       {"id": "d0", "funcao": "diagrama", "caixa_rel": [0.1, 0.3, 0.5, 0.6],
                        "ordem": 1}],
            "diagramas": [{"id": "d0", "fen": "8/8/8/8/8/8/8/K6k", "lado": "?", "legenda": "b1"}],
            "linhas_corpo": [{"id": "l0", "bloco": "b0", "caixa_rel": [0.1, 0.1, 0.9, 0.2],
                              "texto": "x"}]}


def test_gabarito_valido_nao_tem_problema():
    assert rotular.validar(_valido()) == []


@pytest.mark.parametrize("estragar, trecho", [
    (lambda g: g["diagramas"][0].update(fen="8/8/8/8/8/8/8/K6"), "a fileira 1 tem 7 casas"),
    (lambda g: g["diagramas"][0].update(fen="8/8/8/8/8/8/K6k"), "7 fileira(s)"),
    (lambda g: g["diagramas"][0].update(fen="8/8/8/8/8/8/8/K6x"), "caractere 'x'"),
    (lambda g: g["diagramas"][0].update(lado="brancas"), "não é w, b ou ?"),
    (lambda g: g["diagramas"][0].update(legenda="b0"), "não é um bloco de legenda"),
    (lambda g: g["diagramas"][0].update(id="d9"), "falta o bloco de função diagrama"),
    (lambda g: g["linhas_corpo"][0].update(bloco="b7"), "não existe"),
    (lambda g: g["linhas_corpo"][0].update(caixa_rel=[0.1, 0.1, 0.9]), "caixa_rel"),
    (lambda g: g["blocos"][1].update(ordem=0), "ordem repetida"),
    (lambda g: g["blocos"][1].update(id="b0"), "id repetido"),
])
def test_validar_reprova(estragar, trecho):
    g = _valido()
    estragar(g)
    problemas = rotular.validar(g)
    assert any(trecho in p for p in problemas), problemas


def test_rascunho_nao_apaga_gabarito_com_trabalho(pastas, tmp_path):
    verdade, _ = pastas
    arquivo = verdade / "sint" / "i000.json"
    with pytest.raises(SystemExit, match="já tem trabalho"):
        rotular._recusar_sobrescrever(verdade / "sint", [0], forcar=False)
    rotular._recusar_sobrescrever(verdade / "sint", [0], forcar=True)
    assert (verdade / "sint" / "i000.json.bak").read_bytes() == arquivo.read_bytes()
    # Rascunho puro (versão 0, ninguém assinou) pode ser refeito sem --forcar.
    g = json.loads(arquivo.read_text(encoding="utf-8"))
    g["verdade_versao"] = 0
    arquivo.write_text(json.dumps(g), encoding="utf-8")
    rotular._recusar_sobrescrever(verdade / "sint", [0], forcar=False)


def test_linha_sem_tab_e_recusada_e_u2028_fica_no_texto(pastas):
    [txt] = rotular.texto_exportar("sint")
    txt.write_text("l1\tum\u2028dois\r\nl2 sem tab\n", encoding="utf-8", newline="")
    with pytest.raises(SystemExit, match="linha 2: falta o TAB"):
        rotular.texto_importar("sint", "Usuário")
    txt.write_text("l1\tum\u2028dois\r\n", encoding="utf-8", newline="")
    assert rotular.ler_txt(txt) == [("l1", "um\u2028dois", True)]


def test_importar_confere_todas_as_paginas_antes_de_gravar(pastas):
    verdade, faixas = pastas
    segunda = json.loads((verdade / "sint" / "i000.json").read_text(encoding="utf-8"))
    (verdade / "sint" / "i001.json").write_text(json.dumps(segunda), encoding="utf-8")
    rotular.texto_exportar("sint")
    (faixas / "sint" / "i000.txt").write_text("l1\tnovo\n", encoding="utf-8")
    (faixas / "sint" / "i001.txt").write_text("l9\tnão existe\n", encoding="utf-8")
    antes = (verdade / "sint" / "i000.json").read_bytes()
    with pytest.raises(SystemExit, match="desconhecido"):
        rotular.texto_importar("sint", "Usuário")
    assert (verdade / "sint" / "i000.json").read_bytes() == antes


def test_conferencia_cega_do_texto_grava_o_resultado(pastas, tmp_path):
    verdade, _ = pastas
    modelo = rotular.cego_modelo("sint", "i000")
    assert modelo.read_text(encoding="utf-8").splitlines()[1:] == ["l1\t", "l2\t"]
    with pytest.raises(SystemExit, match="já existe"):
        rotular.cego_modelo("sint", "i000")
    modelo.write_text("l1\tlido um\nl2\tlido dois\n", encoding="utf-8")
    assert rotular.cego_texto("sint", "i000", modelo, "Outra pessoa") == 1.0
    g = json.loads((verdade / "sint" / "i000.json").read_text(encoding="utf-8"))
    assert g["conferencia_cega"]["texto"]["aprovada"] is True
    assert g["conferencia_cega"]["texto"]["por"] == "Outra pessoa"
    modelo.write_text("l1\tlido um\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="faltam"):
        rotular.cego_texto("sint", "i000", modelo, "Outra pessoa")


def test_conferencia_cega_do_fen_e_revisao(pastas):
    verdade, _ = pastas
    arquivo = verdade / "sint" / "i000.json"
    g = json.loads(arquivo.read_text(encoding="utf-8"))
    g["diagramas"] = [{"id": "d0", "fen": "8/8/8/8/8/8/8/K6k", "fen_verificado": False,
                       "lado_verificado": False}]
    arquivo.write_text(json.dumps(g), encoding="utf-8")
    assert rotular.cego_fen("sint", "i000", "d0", "8/8/8/8/8/8/8/K5k1 w - - 0 1", "P") is False
    assert json.loads(arquivo.read_text(encoding="utf-8"))["diagramas"][0]["fen_verificado"] is False
    assert rotular.cego_fen("sint", "i000", "d0", "8/8/8/8/8/8/8/K6k", "P") is True
    assert json.loads(arquivo.read_text(encoding="utf-8"))["diagramas"][0]["fen_verificado"] is True
    with pytest.raises(SystemExit, match="FEN inválido"):
        rotular.cego_fen("sint", "i000", "d0", "8/8", "P")

    with pytest.raises(SystemExit, match=r"\['d7'\]"):
        rotular.revisar("sint", "i000", "Revisor", lado=["d7"])
    g = rotular.revisar("sint", "i000", "Revisor", lado=["d0"])
    assert g["revisado_por"] == "Revisor" and g["diagramas"][0]["lado_verificado"] is True
