"""O banco de desempenho (SPEC §15.3): medidas em p95, gravadas num JSON por execução.

Roda só com `-m desempenho`. Cada teste mede uma meta de §2 e registra o número em
`medidas`; ao fim da sessão, `docs/medidas/AAAA-MM-DD-<rótulo>.json` recebe os números
e o ambiente (CPU, RAM, versões, threads do torch, commit). Na linha de base (passo 0)
os testes só reportam; os passos que perseguem uma meta acrescentam o portão
`alvo × 1,2`, que só reprova na máquina de `docs/medidas/maquina.json`.
"""

from __future__ import annotations

import datetime
import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ / "ferramentas"))
from comum import destino_da_medida, estado_do_git  # noqa: E402
MEDIDAS = RAIZ / "docs" / "medidas"
AQUECIMENTOS = 5
REPETICOES = 30

_coletadas: dict = {}


def percentil(valores, q: float) -> float:
    """O valor da posição `q` (0–1) na lista ordenada, pelo arredondamento do índice."""
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, int(round(q * (len(ordenados) - 1))))]


def p95(valores) -> float:
    return percentil(valores, 0.95)


def cronometrar(funcao, *, aquecimentos: int = AQUECIMENTOS, repeticoes: int = REPETICOES,
                antes=None) -> dict:
    """Roda `funcao` e devolve p50, p95 e máximo em milissegundos (aquecimentos descartados)."""
    tempos = []
    for i in range(aquecimentos + repeticoes):
        if antes is not None:
            antes(i)
        inicio = time.perf_counter_ns()
        funcao(i)
        decorrido = (time.perf_counter_ns() - inicio) / 1e6
        if i >= aquecimentos:
            tempos.append(decorrido)
    return {"p50_ms": round(statistics.median(tempos), 2), "p95_ms": round(p95(tempos), 2),
            "max_ms": round(max(tempos), 2), "n": len(tempos)}


@pytest.fixture(scope="session")
def medidas():
    return _coletadas


def na_maquina_cadastrada() -> bool:
    try:
        cadastro = json.loads((MEDIDAS / "maquina.json").read_text(encoding="utf-8"))
    except OSError:
        return False
    return cadastro.get("nome") == platform.node()


def _ambiente() -> dict:
    import fitz
    import PySide6
    try:
        import torch
        torch_versao, threads = torch.__version__, torch.get_num_threads()
    except ImportError:
        torch_versao, threads = None, None
    try:
        import psutil
        ram = round(psutil.virtual_memory().total / 2**30, 1)
    except ImportError:
        ram = None
    import gc

    git = estado_do_git()
    return {"objetos_congelados": gc.get_freeze_count(),
            "maquina": platform.node(), "maquina_cadastrada": na_maquina_cadastrada(),
            "cpu": platform.processor(), "ram_gb": ram, "python": sys.version.split()[0],
            "pyside6": PySide6.__version__, "pymupdf": fitz.VersionBind, "torch": torch_versao,
            "threads_do_torch": threads, **git}


#: As medidas de §2 que a linha de base tem de ter; sem alguma, o JSON é `-parcial`.
METAS = ("troca_de_pagina", "enter_ensinar", "releitura_de_um_glifo", "memoria_do_desfazer",
         "atraso_durante_o_lote", "memoria_total_com_o_lote")


def pytest_sessionfinish(session, exitstatus):
    """Grava o JSON da sessão, com o `exitstatus` dela.

    Sessão com falha vai com `-falhou` no nome, e sessão sem todas as `METAS` (um `-k`, ou
    o livro ausente, que pula os testes) com `-parcial`: nenhuma das duas fica com o nome
    que o README lê. Um JSON do mesmo dia e rótulo só é sobrescrito com
    `ABBY_SOBRESCREVER_MEDIDA=1`; sem ela, o novo ganha a hora no nome.
    """
    if not _coletadas:
        return
    rotulo = os.environ.get("ABBY_ROTULO_DA_MEDIDA", "medida")
    hoje = datetime.date.today().isoformat()
    MEDIDAS.mkdir(parents=True, exist_ok=True)
    faltam = [m for m in METAS if m not in _coletadas]
    if int(exitstatus) != 0:
        rotulo += "-falhou"
    elif faltam:
        rotulo += "-parcial"
    destino = destino_da_medida(hoje, rotulo, MEDIDAS)
    dados = {"data": hoje, "rotulo": rotulo, "exitstatus": int(exitstatus),
             "metas_ausentes": faltam,
             "ordem": "os testes do módulo dividem a janela e os padrões, em ordem fixa: o "
                      "Enter ensina antes do lote, e o lote lê com esses padrões",
             "ambiente": _ambiente(), "medidas": _coletadas}
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
