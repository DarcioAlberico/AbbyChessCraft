"""Onde os testes `livro_real` acham os PDFs dos livros de referência.

A definição é a de `ferramentas/comum.py` (por padrão, a pasta `PDF` do PyBoxEditor;
`ABBY_PASTA_DOS_PDFS` aponta para outra), para testes e ferramentas não divergirem.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))

from comum import PASTA_DOS_PDFS  # noqa: E402,F401
