r"""Gera `docs/ATALHOS.md` de `docs/atalhos.yaml` e mostra os problemas da tabela.

    .venv\Scripts\python.exe ferramentas\atalhos.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from abbychess import atalhos  # noqa: E402

DESTINO = Path(__file__).resolve().parent.parent / "docs" / "ATALHOS.md"


def main() -> int:
    tabela = atalhos.carregar()
    problemas = atalhos.verificar(tabela)
    for problema in problemas:
        print(problema)
    DESTINO.write_text(atalhos.markdown(tabela) + "\n", encoding="utf-8", newline="\n")
    print(f"{DESTINO.name}: {len(tabela.acoes)} ações; {len(problemas)} problema(s)")
    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())
