"""Os projetos abertos por último (U-4), no `QSettings`: o mais novo primeiro, sem repetir."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

CHAVE = "projetos_recentes"
MAXIMO = 8


def lista(config) -> List[str]:
    """As pastas, a mais nova primeira; um valor estragado vale lista vazia."""
    try:
        bruto = json.loads(config.value(CHAVE, "") or "[]")
    except (TypeError, ValueError):
        return []
    return [str(p) for p in bruto] if isinstance(bruto, list) else []


def lembrar(config, pasta) -> None:
    pasta = str(pasta)
    config.setValue(CHAVE, json.dumps(
        [pasta] + [p for p in lista(config) if p != pasta][:MAXIMO - 1], ensure_ascii=False))


def ultimo_que_existe(config):
    """A pasta mais nova que ainda é um projeto, ou None."""
    from abbychess.pasta_do_projeto import ARQUIVO_DO_PROJETO

    return next((p for p in lista(config) if (Path(p) / ARQUIVO_DO_PROJETO).is_file()), None)
