"""Ler a sequência não grava (SPEC-qualidade Q-P8): quem monta e conserta a sequência é
`ordem.montar`, chamada ao criar e ao abrir; a propriedade só lê."""
from __future__ import annotations

import json
from dataclasses import replace

from abbychess.projeto import ARQUIVO_DO_LIVRO, ProjetoDeLivro


def _fotografia(pasta):
    return {p.relative_to(pasta).as_posix(): (p.read_bytes() if p.is_file() else None)
            for p in sorted(pasta.rglob("*"))}


def _sem_a_sequencia_gravada(projeto):
    arquivo = projeto.pasta / "projeto.json"
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    dados["sequencia"] = None
    arquivo.write_text(json.dumps(dados), encoding="utf-8")


def test_ler_a_sequencia_nao_muda_nenhum_arquivo(projeto):
    projeto.salvar_pagina(1, [])
    _sem_a_sequencia_gravada(projeto)
    (projeto.pasta / ARQUIVO_DO_LIVRO).unlink()          # a página 2 some do livro.json
    novo = ProjetoDeLivro(projeto.pasta, replace(projeto.dados, sequencia=None))
    antes = _fotografia(projeto.pasta)

    assert len(novo.sequencia) == len(projeto.sequencia)
    novo.resumo.paginas_lidas()

    assert _fotografia(projeto.pasta) == antes


def test_abrir_monta_e_grava_a_sequencia_que_faltava(projeto):
    _sem_a_sequencia_gravada(projeto)

    aberto = ProjetoDeLivro.abrir(projeto.pasta)
    try:
        gravado = json.loads((projeto.pasta / "projeto.json").read_text(encoding="utf-8"))
        assert gravado["sequencia"] == aberto.sequencia.para_json()
        assert len(aberto.sequencia) == len(projeto.sequencia)
    finally:
        aberto.fechar()
