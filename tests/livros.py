"""Onde os testes `livro_real` acham os PDFs dos livros de referência.

Por padrão, a pasta `PDF` do PyBoxEditor; `ABBY_PASTA_DOS_PDFS` aponta para outra (a mesma
variável de `ferramentas/rotular.py`).
"""

from __future__ import annotations

import os
from pathlib import Path

PASTA_DOS_PDFS = Path(os.environ.get("ABBY_PASTA_DOS_PDFS",
                                     "C:/Python-Chess2/PyBoxEditor_Tkinter/PDF"))
