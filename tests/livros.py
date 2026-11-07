"""Onde os testes acham os PDFs dos livros de referência, os gabaritos e as fatias.

A definição é a de `ferramentas/comum.py` (por padrão, a pasta `PDF` do PyBoxEditor;
`ABBY_PASTA_DOS_PDFS` aponta para outra), para testes e ferramentas não divergirem. Os
gabaritos (`ABBY_VERDADE`) e as fatias (`ABBY_FATIAS`) ficam fora do git, por direito
autoral; sem eles, o teste que precisa deles é pulado.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))

import pytest  # noqa: E402

from comum import FATIAS, PASTA_DOS_PDFS, VERDADE  # noqa: E402,F401


def gabarito(livro: str, indice: int) -> dict:
    """O gabarito da página, ou o teste é pulado se ele não está nesta máquina."""
    import json

    arquivo = VERDADE / livro / f"i{indice:03d}.json"
    if not arquivo.is_file():
        pytest.skip(f"o gabarito {livro}/{arquivo.name} não está em {VERDADE}")
    return json.loads(arquivo.read_text(encoding="utf-8"))


def gabaritos_do_livro(livro: str) -> list[Path]:
    """Os gabaritos do livro, ou o teste é pulado se não há nenhum nesta máquina."""
    arquivos = sorted((VERDADE / livro).glob("i*.json"))
    if not arquivos:
        pytest.skip(f"os gabaritos de {livro} não estão em {VERDADE}")
    return arquivos


def fatia(nome: str = "xv-i020-026-inicial.zip") -> Path:
    """O zip da fatia, ou o teste é pulado se ele não está nesta máquina."""
    arquivo = FATIAS / nome
    if not arquivo.is_file():
        pytest.skip(f"a fatia {nome} não está em {FATIAS}")
    return arquivo
