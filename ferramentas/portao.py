"""O portão (`livro_real` e `desempenho`), arquivo por arquivo, cada um num processo, sob o
vigia da RAM livre (roadmap da página perfeita, contrato, item 0; carga pesada trava a máquina).

    python ferramentas/portao.py                  # os arquivos com teste de portão
    python ferramentas/portao.py --arquivos a b   # só estes
    python ferramentas/portao.py --saida X.txt    # o resumo; os logs ficam ao lado

Antes de cada arquivo, espera até 5 min por RAM livre; durante, abaixo do piso, mata a árvore
e diz que interrompeu. A saída é 0 só se todos passarem sem interrupção. Carga pesada: nada
mais rodando (~17 min). O resumo vai a uma pasta temporária, fora do git, se não houver `--saida`.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil

RAIZ = Path(__file__).resolve().parent.parent
PISO = 800 * 1024 * 1024
PARA_COMECAR = 2.2 * 1024 ** 3
ESPERA_MAXIMA = 300
ARQUIVOS = (
    "tests/test_coluna_de_tabuleiros.py", "tests/test_diagramas.py", "tests/test_documento.py",
    "tests/test_espaco.py", "tests/test_servidor_livro_real.py",
    "tests/test_treino_por_livro.py", "tests/test_visor.py", "tests/test_catraca_do_livro.py",
    "tests/test_tipo_de_pagina.py",
    "tests/desempenho/test_busca.py", "tests/desempenho/test_carregar_modelos.py",
    "tests/desempenho/test_linha_de_base.py", "tests/desempenho/test_paginas.py",
    "tests/desempenho/test_revisao.py", "tests/desempenho/test_servidor.py",
    "tests/desempenho/test_sessao.py", "tests/desempenho/test_substituir.py",
    "tests/desempenho/test_visor.py",
)


def _matar(pid: int) -> None:
    pai = psutil.Process(pid)
    for filho in pai.children(recursive=True):
        filho.kill()
    pai.kill()


def _vigiar(processo: subprocess.Popen, minimo: int) -> tuple:
    """Espera o processo; mata-o se a RAM livre cair abaixo do piso. (interrompido, mínimo)."""
    while processo.poll() is None:
        time.sleep(3)
        livre = psutil.virtual_memory().available
        minimo = min(minimo, livre)
        if livre < PISO:
            _matar(processo.pid)
            processo.wait()
            return True, minimo
    return False, minimo


def rodar(arquivo: str, saida: Path) -> dict:
    """Um arquivo do portão num processo; o que aconteceu."""
    registro = saida.with_name(f"{saida.stem}-{Path(arquivo).stem}.log")
    espera = time.time()
    while (psutil.virtual_memory().available < PARA_COMECAR
           and time.time() - espera < ESPERA_MAXIMA):
        time.sleep(10)
    ambiente = dict(os.environ, ABBY_PORTAO="1", PYTHONPATH=str(RAIZ), PYTHONIOENCODING="utf-8")
    inicio = time.time()
    with registro.open("w", encoding="utf-8") as log:
        processo = subprocess.Popen(
            [sys.executable, "-m", "pytest", arquivo, "-q", "-p", "no:cacheprovider",
             "--no-header", "-n0", "--tb=short", "-m", "livro_real or desempenho"],
            cwd=RAIZ, env=ambiente, stdout=log, stderr=subprocess.STDOUT)
        interrompido, minimo = _vigiar(processo, psutil.virtual_memory().available)
    texto = registro.read_text(encoding="utf-8", errors="replace")
    fim = re.findall(r"^=* ?.*(?:passed|failed|no tests ran|deselected).*$", texto, re.M)
    return {"arquivo": arquivo, "saida": processo.returncode, "interrompido": interrompido,
            "menor_ram_gb": round(minimo / 2 ** 30, 2), "segundos": round(time.time() - inicio),
            "fim": fim[-1].strip("= ")[:80] if fim else "",
            "falhas": re.findall(r"^FAILED (\S+)", texto, re.M)}


def aprovou(resultado: dict) -> bool:
    """Passou: saída 0, ou nenhum teste selecionado (5), e sem o vigia ter interrompido."""
    return resultado["saida"] in (0, 5) and not resultado["interrompido"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arquivos", nargs="+", default=list(ARQUIVOS))
    parser.add_argument("--saida", type=Path)
    args = parser.parse_args()
    saida = args.saida or Path(tempfile.mkdtemp(prefix="portao-")) / "portao.txt"
    resultados = []
    with saida.open("w", encoding="utf-8") as resumo:
        for arquivo in args.arquivos:
            resultado = rodar(arquivo, saida)
            resultados.append(resultado)
            print(resultado, file=resumo, flush=True)
            print(resultado, flush=True)
    reprovados = [r["arquivo"] for r in resultados if not aprovou(r)]
    print(f"portão: {len(resultados) - len(reprovados)} de {len(resultados)} arquivos; "
          f"resumo em {saida}")
    if reprovados:
        print("reprovados:", *reprovados)
    return 1 if reprovados else 0


if __name__ == "__main__":
    sys.exit(main())
