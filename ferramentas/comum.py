"""O que as ferramentas de medida e os testes `livro_real` dividem: onde estão os livros,
o estado do git e onde gravar uma medida.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

RAIZ = Path(__file__).resolve().parent.parent
MEDIDAS = RAIZ / "docs" / "medidas"
#: Onde estão os PDFs dos livros de referência (os do PyBoxEditor, por padrão).
PASTA_DOS_PDFS = Path(os.environ.get("ABBY_PASTA_DOS_PDFS",
                                     "C:/Python-Chess2/PyBoxEditor_Tkinter/PDF"))
#: Com "1", uma medida do mesmo dia e nome é sobrescrita; sem, a nova ganha a hora no nome.
SOBRESCREVER = "ABBY_SOBRESCREVER_MEDIDA"

_NOME = re.compile(r"(?P<data>\d{4}-\d{2}-\d{2})-(?P<base>.+?)(?:-(?P<hora>\d{6}))?\.json")


def estado_do_git() -> dict:
    """O commit e se a árvore tem mudança fora de `docs/medidas` e do README (as tabelas
    geradas), que não mudam o que é medido."""
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ,
                                capture_output=True, text=True, check=True).stdout.strip()
        sujo = bool(subprocess.run(["git", "status", "--porcelain", "--", ".",
                                    ":(exclude)docs/medidas", ":(exclude)README.md"], cwd=RAIZ,
                                   capture_output=True, text=True, check=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "arvore_suja": None}
    return {"commit": commit, "arvore_suja": sujo}


def destino_da_medida(data: str, base: str, pasta: Path = MEDIDAS) -> Path:
    """`AAAA-MM-DD-<base>.json`, ou com `-HHMMSS` se já existe e não é para sobrescrever."""
    destino = pasta / f"{data}-{base}.json"
    if destino.exists() and os.environ.get(SOBRESCREVER) != "1":
        destino = pasta / f"{data}-{base}-{time.strftime('%H%M%S')}.json"
    return destino


def ultima_medida(base: str, pasta: Path = MEDIDAS) -> Optional[Path]:
    """A medida mais nova com esse nome-base (pela data e pela hora no nome)."""
    candidatos = []
    for arquivo in pasta.glob(f"*-{base}*.json"):
        casou = _NOME.fullmatch(arquivo.name)
        if casou and casou["base"] == base:
            candidatos.append(((casou["data"], casou["hora"] or ""), arquivo))
    return max(candidatos)[1] if candidatos else None
