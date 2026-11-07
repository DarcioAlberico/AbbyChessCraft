"""O portão arquivo por arquivo, cada um num processo, sob o vigia da RAM livre."""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import psutil

PASTA = Path(sys.argv[1])
SAIDA = Path(sys.argv[2])
PISO = 800 * 1024 * 1024
PARA_COMECAR = 2.2 * 1024 ** 3
ARQUIVOS = ["tests/test_coluna_de_tabuleiros.py", "tests/test_diagramas.py", "tests/test_documento.py", "tests/test_espaco.py", "tests/test_servidor_livro_real.py", "tests/test_treino_por_livro.py", "tests/desempenho/test_paginas.py", "tests/desempenho/test_servidor.py"]
_TODOS = ["tests/test_diagramas.py", "tests/test_documento.py",
            "tests/test_espaco.py", "tests/test_servidor_livro_real.py", "tests/test_treino_por_livro.py",
            "tests/test_visor.py", "tests/desempenho/test_busca.py", "tests/desempenho/test_carregar_modelos.py",
            "tests/desempenho/test_linha_de_base.py", "tests/desempenho/test_paginas.py",
            "tests/desempenho/test_revisao.py", "tests/desempenho/test_servidor.py",
            "tests/desempenho/test_sessao.py", "tests/desempenho/test_substituir.py",
            "tests/desempenho/test_visor.py"]
ambiente = dict(os.environ, ABBY_PORTAO="1", PYTHONPATH=str(PASTA), PYTHONIOENCODING="utf-8")


def rodar(arquivo: str):
    registro = SAIDA.with_name(SAIDA.stem + "-" + Path(arquivo).stem + ".log")
    espera = time.time()
    while psutil.virtual_memory().available < PARA_COMECAR and time.time() - espera < 300:
        time.sleep(10)
    minimo = psutil.virtual_memory().available
    inicio = time.time()
    with registro.open("w", encoding="utf-8") as saida:
        p = subprocess.Popen([sys.executable, "-m", "pytest", arquivo, "-q", "-p", "no:cacheprovider",
                              "--no-header", "-n0", "--tb=short", "-m", "livro_real or desempenho"],
                             cwd=PASTA, env=ambiente, stdout=saida, stderr=subprocess.STDOUT)
        interrompido = False
        while p.poll() is None:
            time.sleep(3)
            livre = psutil.virtual_memory().available
            minimo = min(minimo, livre)
            if livre < PISO:
                interrompido = True
                pai = psutil.Process(p.pid)
                for filho in pai.children(recursive=True):
                    filho.kill()
                pai.kill()
                break
        p.wait()
    texto = registro.read_text(encoding="utf-8", errors="replace")
    fim = re.findall(r"^\d+ (?:passed|failed|deselected|skipped).*$|^=* ?.*(?:passed|failed|no tests ran).*$",
                     texto, re.M)
    falhas = re.findall(r"^FAILED (\S+)", texto, re.M)
    return (arquivo, p.returncode, interrompido, f"{minimo / 2**30:.2f} GB",
            f"{time.time() - inicio:.0f} s", fim[-1][:80] if fim else "", falhas)


with SAIDA.open("w", encoding="utf-8") as resumo:
    for arquivo in ARQUIVOS:
        linha = rodar(arquivo)
        print(linha, file=resumo, flush=True)
print(SAIDA.read_text(encoding="utf-8"))
