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
import subprocess
import sys
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent.parent
MEDIDAS = RAIZ / "docs" / "medidas"
AQUECIMENTOS = 5
REPETICOES = 30

_coletadas: dict = {}


def p95(valores) -> float:
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, int(round(0.95 * (len(ordenados) - 1))))]


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
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ,
                                capture_output=True, text=True, check=True).stdout.strip()
        sujo = bool(subprocess.run(["git", "status", "--porcelain", "--", ".",
                                    ":(exclude)docs/medidas"], cwd=RAIZ,
                                   capture_output=True, text=True, check=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        commit, sujo = None, None
    return {"maquina": platform.node(), "maquina_cadastrada": na_maquina_cadastrada(),
            "cpu": platform.processor(), "ram_gb": ram, "python": sys.version.split()[0],
            "pyside6": PySide6.__version__, "pymupdf": fitz.VersionBind, "torch": torch_versao,
            "threads_do_torch": threads, "commit": commit, "arvore_suja": sujo}


def pytest_sessionfinish(session, exitstatus):
    """Grava o JSON da sessão, com o `exitstatus` dela.

    Sessão com falha não grava por cima de nada: o JSON vai com `-falhou` no nome. E um
    JSON do mesmo dia e rótulo só é sobrescrito com `ABBY_SOBRESCREVER_MEDIDA=1`, para uma
    rodada parcial (um `-k`) não apagar a medida inteira.
    """
    if not _coletadas:
        return
    rotulo = os.environ.get("ABBY_ROTULO_DA_MEDIDA", "medida")
    hoje = datetime.date.today().isoformat()
    MEDIDAS.mkdir(parents=True, exist_ok=True)
    sufixo = "" if int(exitstatus) == 0 else "-falhou"
    destino = MEDIDAS / f"{hoje}-{rotulo}{sufixo}.json"
    if destino.exists() and not sufixo and os.environ.get("ABBY_SOBRESCREVER_MEDIDA") != "1":
        destino = MEDIDAS / f"{hoje}-{rotulo}-{time.strftime('%H%M%S')}.json"
    dados = {"data": hoje, "rotulo": rotulo, "exitstatus": int(exitstatus),
             "ambiente": _ambiente(), "medidas": _coletadas}
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
