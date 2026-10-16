"""As tabelas do README (`ferramentas/resumo_medidas.py`) e a escolha da medida mais nova."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import comum  # noqa: E402
import resumo_medidas as rm  # noqa: E402


@pytest.fixture
def pastas(tmp_path, monkeypatch):
    medidas = tmp_path / "medidas"
    medidas.mkdir()
    monkeypatch.setattr(rm, "MEDIDAS", medidas)
    monkeypatch.setattr(rm, "README", tmp_path / "README.md")
    return medidas


def _gravar(pasta, nome, dados):
    (pasta / nome).write_text(json.dumps(dados), encoding="utf-8")


def _desempenho(p95):
    return {"ambiente": {"commit": "abc", "maquina_cadastrada": True},
            "medidas": {"troca_de_pagina": {"p95_ms": p95, "n": 30, "alvo_no_cache_ms": 150},
                        "memoria_do_desfazer": {"estimado_300x20_mb": 12.5, "acoes": 60,
                                                "alvo_mb": 50}}}


def test_ultima_medida_pela_data_e_hora_sem_falhou_nem_parcial(pastas):
    for nome in ("2026-10-15-linha-de-base.json", "2026-10-16-linha-de-base.json",
                 "2026-10-16-linha-de-base-101500.json", "2026-10-16-linha-de-base-falhou.json",
                 "2026-10-17-linha-de-base-parcial.json"):
        _gravar(pastas, nome, {})
    assert comum.ultima_medida("linha-de-base", pastas).name == "2026-10-16-linha-de-base-101500.json"
    assert comum.ultima_medida("qualidade-xv", pastas) is None


def test_destino_nao_sobrescreve_sem_a_variavel(pastas, monkeypatch):
    monkeypatch.delenv(comum.SOBRESCREVER, raising=False)
    assert comum.destino_da_medida("2026-10-16", "x", pastas).name == "2026-10-16-x.json"
    _gravar(pastas, "2026-10-16-x.json", {})
    outro = comum.destino_da_medida("2026-10-16", "x", pastas).name
    assert outro.startswith("2026-10-16-x-") and len(outro) == len("2026-10-16-x-000000.json")
    monkeypatch.setenv(comum.SOBRESCREVER, "1")
    assert comum.destino_da_medida("2026-10-16", "x", pastas).name == "2026-10-16-x.json"


def test_desempenho_usa_a_medida_mais_nova(pastas):
    _gravar(pastas, "2026-10-16-linha-de-base.json", _desempenho(300.0))
    _gravar(pastas, "2026-10-16-linha-de-base-120000.json", _desempenho(190.4))
    texto = rm.gerar()
    assert "p95 190 ms" in texto and "p95 300 ms" not in texto
    assert "~12,5 MB (estimado de 60 ações em 3 páginas, extrapolado)" in texto


def test_qualidade_mostra_pendente_com_o_provisorio(pastas):
    _gravar(pastas, "2026-10-16-qualidade-xv.json", {
        "indices": [0, 20], "nao_medido": {"validacao_pelos_lances": "passo H"},
        "resumo": {"margens_precisao": 0.875, "margens_revocacao": 1.0,
                   "diagramas_achados": "1/1", "diagramas_falsos": 0, "linhas_sem_par": 2,
                   "linhas_sem_par_negativas": 830, "paginas_negativas": 1,
                   "linhas_perdidas": 3, "fen_igual_a_leitura": "1/1",
                   "casas_erradas_por_diagrama": None, "casas_erradas_provisorio": 0.0,
                   "lado_certo": "0/0", "lado_certo_provisorio": "1/1",
                   "ordem_discordancia_media": 0.0, "cer_corpo": None,
                   "estado": "provisória: x"}})
    linha = next(ln for ln in rm.gerar().splitlines() if ln.startswith("| xv |"))
    assert "| 0,875 / 1 |" in linha and "| 830 (1 pág.) |" in linha
    assert "pendente (provisório: 0)" in linha and "pendente (provisório: 1/1)" in linha
    assert linha.endswith("| pendente | provisória: x |")
    assert "Ainda não medido: a validação do FEN pelos lances, no passo H." in rm.gerar()


def test_fatia_uma_linha_por_livro_e_passo_com_os_erros(pastas):
    base = {"paginas": {"i020": {"erros": {"texto": 5, "diagramas": 2}}}, "gestos": None,
            "gestos_diagramas": 4, "gestos_navegacao": 0, "estado": "pendente: y"}
    _gravar(pastas, "2026-10-16-fatia-xv-passo-0.json", dict(base, estado="velho"))
    _gravar(pastas, "2026-10-16-fatia-xv-passo-0-130000.json", base)
    _gravar(pastas, "2026-10-17-fatia-xv-passo-A3.json", dict(base, gestos=10,
                                                              gestos_sem_impossiveis=8))
    linhas = [ln for ln in rm.gerar().splitlines() if ln.startswith("| xv |")]
    assert len(linhas) == 2
    assert "| gestos pendentes | 4 | 0 | 2 (diagramas; texto pendente) | pendente: y |" in linhas[0]
    assert "10 gestos (8 sem os impossíveis) | 4 | 0 | 7 |" in linhas[1]


def test_main_troca_so_o_que_esta_entre_os_marcadores_e_mantem_o_crlf(pastas):
    _gravar(pastas, "2026-10-16-linha-de-base.json", _desempenho(190.0))
    rm.README.write_bytes(b"# T\r\nantes\r\n<!-- medidas:inicio -->\r\nvelho\r\n"
                          b"<!-- medidas:fim -->\r\ndepois\r\n")
    assert rm.main() == 0
    novo = rm.README.read_bytes()
    assert novo.startswith(b"# T\r\nantes\r\n<!-- medidas:inicio -->\r\nDesempenho")
    assert novo.endswith(b"<!-- medidas:fim -->\r\ndepois\r\n")
    assert b"velho" not in novo and b"\n" not in novo.replace(b"\r\n", b"")


def test_main_sem_marcadores_recusa(pastas):
    rm.README.write_text("# sem marcadores\n", encoding="utf-8")
    assert rm.main() == 1
    assert rm.README.read_text(encoding="utf-8") == "# sem marcadores\n"


def test_sem_medida_nenhuma(pastas):
    assert rm.gerar() == "Linha de base de desempenho: ainda não medida."


def test_desempenho_por_passo_ao_lado_da_linha_de_base(pastas):
    _gravar(pastas, "2026-10-16-linha-de-base.json", _desempenho(190.0))
    _gravar(pastas, "2026-10-17-passo-1a.json", _desempenho(205.5))
    _gravar(pastas, "2026-10-17-passo-1a-parcial.json", _desempenho(999.0))
    linha = next(ln for ln in rm.gerar().splitlines() if ln.startswith("| Troca de página, p95"))
    assert linha == "| Troca de página, p95 | 190 | 205,5 |"
