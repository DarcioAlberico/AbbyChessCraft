"""A medida da qualidade (SPEC-qualidade §1, roadmap Q0): a cobertura combinada da suíte
rápida e da camada `processo`, rodadas em série, e sobre ela o CRAP (`crapper.py`) e a
duplicação (`dryer.py`).

    python ferramentas/qualidade.py                      # roda as duas camadas e mede
    python ferramentas/qualidade.py --cobertura X.json   # mede sobre uma cobertura pronta

Grava em `docs/medidas/qualidade/`: `crap-<commit>.txt`, `duplicacao-<commit>.txt` e
`AAAA-MM-DD-qualidade.json` (o resumo, com o estado do git). A cobertura bruta (~1 MB) e o
`.coverage` ficam numa pasta temporária, fora do git. É carga pesada: nada mais rodando.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum  # noqa: E402

PASTA = comum.MEDIDAS / "qualidade"
FERRAMENTAS = Path(__file__).resolve().parent
# As duas camadas que entram na cobertura: a rápida em paralelo (no máximo 4 workers) e a
# `processo` em série, que abre o servidor de leitura e o render (os filhos são medidos pelo
# `pytest-cov.pth` de quem os abre). Com a cobertura em cada filho, a matança do gravador (50
# filhos, 36 s sem ela) passa do teto de 60 s do pyproject: o teto sobe só aqui, na medida.
CAMADAS = {
    "rapida": ["-n", "4"],
    "processo": ["-m", "processo", "--timeout=600"],
}


def rodar_as_camadas(cobertura: Path) -> dict:
    """Roda as camadas em série com a cobertura somada; o código de saída de cada uma."""
    ambiente = dict(os.environ, PYTHONPATH=str(comum.RAIZ),
                    COVERAGE_FILE=str(cobertura.with_name(".coverage")))
    codigos = {}
    for i, (nome, args) in enumerate(CAMADAS.items()):
        relatorio = [f"--cov-report=json:{cobertura}"] if i == len(CAMADAS) - 1 else ["--cov-report="]
        comando = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                   "--cov=abbychess", *(["--cov-append"] if i else []), *relatorio, *args]
        print(f"[{nome}] {' '.join(comando[1:])}", flush=True)
        inicio = time.perf_counter()
        codigos[nome] = subprocess.run(comando, cwd=comum.RAIZ, env=ambiente).returncode
        print(f"[{nome}] saída {codigos[nome]} em {time.perf_counter() - inicio:.0f} s", flush=True)
    return codigos


def _ferramenta(nome: str, *args) -> str:
    saida = subprocess.run([sys.executable, "-I", str(FERRAMENTAS / nome), *map(str, args)],
                           cwd=comum.RAIZ, capture_output=True, check=True)
    return saida.stdout.decode("utf-8")


def resumo(cobertura: dict, crap: str, duplicacao: str, git: dict, codigos: dict) -> dict:
    """O resumo da medida, dos três relatórios (a primeira linha de cada ferramenta)."""
    totais = cobertura["totals"]
    funcoes, acima = map(int, re.match(r"funções: (\d+); CRAP >= \S+: (\d+)", crap).groups())
    pares = int(re.match(r"funções com >= \d+ nós: \d+; pares com rank >= \S+: (\d+)",
                         duplicacao).group(1))
    return {
        "ambiente": {**git, "data": time.strftime("%Y-%m-%d")},
        "camadas": codigos,
        "cobertura": {"linhas": totais["num_statements"], "faltando": totais["missing_lines"],
                      "percentual": round(totais["percent_covered"], 1)},
        "crap": {"funcoes": funcoes, "acima_de_10": acima},
        "duplicacao": {"pares_acima_de_0_8": pares},
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    partes = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    partes.add_argument("--cobertura", type=Path, help="um coverage.json já gerado")
    args = partes.parse_args()
    git = comum.estado_do_git()
    with tempfile.TemporaryDirectory(prefix="abby-qualidade-") as pasta:
        cobertura = args.cobertura or Path(pasta) / "cobertura.json"
        codigos = {} if args.cobertura else rodar_as_camadas(cobertura)
        if any(codigos.values()):
            print(f"uma camada falhou ({codigos}): a medida não vale sobre uma suíte vermelha")
            return 1
        crap = _ferramenta("crapper.py", "abbychess", cobertura, 10)
        duplicacao = _ferramenta("dryer.py", "abbychess", 0.8, 60)
        dados = resumo(json.loads(cobertura.read_text(encoding="utf-8")), crap, duplicacao, git,
                       codigos)
    PASTA.mkdir(parents=True, exist_ok=True)
    commit = git["commit"] or "sem-git"
    (PASTA / f"crap-{commit}.txt").write_text(crap, encoding="utf-8", newline="\n")
    (PASTA / f"duplicacao-{commit}.txt").write_text(duplicacao, encoding="utf-8", newline="\n")
    destino = comum.destino_da_medida(dados["ambiente"]["data"], "qualidade", PASTA)
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                       newline="\n")
    print(json.dumps(dados, ensure_ascii=False, indent=2))
    print(f"gravado: {destino.relative_to(comum.RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
