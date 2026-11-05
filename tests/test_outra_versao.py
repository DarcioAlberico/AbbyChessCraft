"""D-1: "não entendo" não é "corrompido". CA-D1: com `BoxEntry` de 12 campos num core de 11, nada
é movido, o projeto abre só para leitura, e `abrir()` não lê nenhum arquivo de `paginas/`."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest
from core.box_model import BoxEntry

from abbychess import pagina_em_json as pj
from abbychess.dados_do_projeto import Projeto
from abbychess.modelo import Box, PaginaDeOutraVersao, gid_de
from abbychess.pasta_do_projeto import ARQUIVO_DO_PROJETO, PASTA_DE_PAGINAS, VERSAO
from abbychess.projeto import ProjetoDeLivro
from tests.ajudantes import _pagina_sintetica

CAMPOS = len(fields(BoxEntry))


@pytest.fixture
def projeto_gravado(tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path, "Livro", _pagina_sintetica(tmp_path / "p.png"))
    projeto.salvar_pagina(0, [BoxEntry("a", 1, 2, 3, 4)])
    projeto.fechar()
    return projeto.pasta


def _editar_json(arquivo: Path, mudar) -> None:
    bruto = json.loads(arquivo.read_text(encoding="utf-8"))
    mudar(bruto)
    arquivo.write_text(json.dumps(bruto), encoding="utf-8", newline="\n")


def _pagina_do_futuro(pasta: Path) -> Path:
    """A página gravada por um core com um campo a mais em `BoxEntry`."""
    arquivo = next((pasta / PASTA_DE_PAGINAS).glob("p*.json"))
    _editar_json(arquivo, lambda bruto: bruto["boxes"][0][1].append("campo novo"))
    return arquivo


def test_o_projeto_grava_quantos_campos_tem_o_box(projeto_gravado):
    bruto = json.loads((projeto_gravado / ARQUIVO_DO_PROJETO).read_text(encoding="utf-8"))
    assert bruto["campos_do_box"] == CAMPOS


def test_ca_d1_o_projeto_de_core_mais_novo_abre_so_para_leitura_sem_ler_paginas(projeto_gravado,
                                                                               monkeypatch):
    arquivo = _pagina_do_futuro(projeto_gravado)
    _editar_json(projeto_gravado / ARQUIVO_DO_PROJETO,
                 lambda bruto: bruto.update(campos_do_box=CAMPOS + 1))
    lidos = []
    ler_bytes, ler_texto = Path.read_bytes, Path.read_text
    monkeypatch.setattr(Path, "read_bytes", lambda s: (lidos.append(s), ler_bytes(s))[1])
    monkeypatch.setattr(Path, "read_text", lambda s, *a, **k: (lidos.append(s), ler_texto(s, *a, **k))[1])
    projeto = ProjetoDeLivro.abrir(projeto_gravado)
    monkeypatch.undo()
    try:
        assert projeto.somente_leitura
        assert "mais nova" in projeto.motivo_so_leitura
        assert [p for p in lidos if p.parent.name == PASTA_DE_PAGINAS] == []
        assert arquivo.is_file()
        assert sorted(p.name for p in arquivo.parent.glob("*corrompido*")) == []
    finally:
        projeto.fechar()


def test_de_reserva_a_pagina_de_outra_versao_nao_e_isolada(projeto_gravado):
    """O `projeto.json` não disse (um projeto de antes de `campos_do_box`): ao ler a página, o
    erro sobe como `OSError`, e o arquivo fica onde está, em vez de virar "corrompido"."""
    arquivo = _pagina_do_futuro(projeto_gravado)
    projeto = ProjetoDeLivro.abrir(projeto_gravado)
    try:
        with pytest.raises(PaginaDeOutraVersao):
            projeto._gravada(0)
        assert arquivo.is_file() and not list(arquivo.parent.glob("*corrompido*"))
    finally:
        projeto.fechar()


def test_a_pagina_de_versao_mais_nova_tambem_nao_e_corrompida():
    with pytest.raises(PaginaDeOutraVersao):
        pj.pagina_de_json({"versao": pj.VERSAO_DA_PAGINA + 1, "pid": 0, "indice": 0})


def test_o_box_ilegivel_de_verdade_continua_ilegivel():
    with pytest.raises((TypeError, ValueError)):
        Box.de_json([gid_de(0, 0), ["a", 1], None, [], 0])


def test_a_versao_da_pagina_nao_sobe_sem_a_do_projeto():
    assert pj.VERSAO_DA_PAGINA <= VERSAO


def test_o_contrato_de_as_state():
    """`as_state` é a lista de todos os campos, na ordem do construtor, e `from_state` a desfaz:
    é o que `Box.para_json` grava. Um campo a mais no core muda este número: `campos_do_box`."""
    entrada = BoxEntry("a", 1, 2, 3, 4, 0.5, "neural")
    estado = entrada.as_state()
    assert len(estado) == CAMPOS
    assert list(estado[:7]) == ["a", 1, 2, 3, 4, 0.5, "neural"]
    assert BoxEntry.from_state(estado) == entrada


def test_o_campo_novo_nao_muda_a_versao_e_uma_versao_antiga_o_guarda_em_extras():
    from abbychess.projeto import _dados_do_projeto

    dados, regravar = _dados_do_projeto({"nome": "x", "fonte": "y", "criado": "z", "coisa_nova": 1})
    assert isinstance(dados, Projeto) and dados.extras == {"coisa_nova": 1} and regravar
    assert dados.versao == VERSAO
