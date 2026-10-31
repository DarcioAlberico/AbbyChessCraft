"""A entrada do `projeto.json` (SPEC-qualidade Q-P6): um campo do tipo errado não abre o
projeto, o erro diz qual campo, e nada na pasta muda."""
from __future__ import annotations

import json

import pytest

from abbychess.projeto import ProjetoDeLivro, ProjetoInvalido

#: (campo, valor do tipo errado). Os de `limiares` vão como "limiares.<nome>".
ERRADOS = [
    ("nome", 5), ("fonte", ["a"]), ("criado", 5), ("idioma", 5), ("notacao", 5),
    ("versao", "3"), ("versao", True), ("fonte_sha256", 5), ("fonte_tamanho", "12"),
    ("proximo_pid", "12"), ("proximo_pid", 1.5), ("extras", 5), ("endireitar", "sim"),
    ("sequencia", 5), ("gids_movidos", [1]), ("limiares", 5),
    ("limiares.livro", "x"), ("limiares.rede", None), ("limiares.base", True),
    ("limiares.revisao", "0.9"), ("limiares.conflito", []),
]


def _fotografia(pasta):
    """Cada arquivo e cada pasta do projeto, com os bytes."""
    return {p.relative_to(pasta).as_posix(): (p.read_bytes() if p.is_file() else None)
            for p in sorted(pasta.rglob("*"))}


@pytest.mark.parametrize("campo, valor", ERRADOS, ids=[f"{c}={v!r}" for c, v in ERRADOS])
def test_um_campo_do_tipo_errado_nao_abre_e_nada_e_gravado(projeto, campo, valor):
    arquivo = projeto.pasta / "projeto.json"
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    if campo.startswith("limiares."):
        dados["limiares"][campo.split(".", 1)[1]] = valor
    else:
        dados[campo] = valor
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    antes = _fotografia(projeto.pasta)

    with pytest.raises(ProjetoInvalido, match=campo.replace(".", r"\.")):
        ProjetoDeLivro.abrir(projeto.pasta)

    assert _fotografia(projeto.pasta) == antes


def test_os_tipos_certos_abrem_como_antes(projeto):
    aberto = ProjetoDeLivro.abrir(projeto.pasta)
    try:
        assert aberto.dados == projeto.dados
    finally:
        aberto.fechar()
