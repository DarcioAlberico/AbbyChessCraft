"""Roda o portão em série e o interrompe se a RAM livre cair abaixo do piso. Registra o mínimo."""
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

PASTA = Path(sys.argv[1])
SAIDA = Path(sys.argv[2])
PISO = 800 * 1024 * 1024

ambiente = dict(os.environ, ABBY_PORTAO="1", PYTHONPATH=str(PASTA), PYTHONIOENCODING="utf-8")
with SAIDA.open("w", encoding="utf-8") as saida:
    processo = subprocess.Popen(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header", "-n0",
         "-m", "livro_real or desempenho"],
        cwd=PASTA, env=ambiente, stdout=saida, stderr=subprocess.STDOUT)
    minimo = psutil.virtual_memory().available
    interrompido = False
    while processo.poll() is None:
        time.sleep(5)
        livre = psutil.virtual_memory().available
        minimo = min(minimo, livre)
        if livre < PISO:
            interrompido = True
            pai = psutil.Process(processo.pid)
            for filho in pai.children(recursive=True):
                filho.kill()
            pai.kill()
            break
    processo.wait()
    print(f"\nVIGIA: saída {processo.returncode}, interrompido={interrompido}, "
          f"menor RAM livre {minimo / 2**30:.2f} GB", file=saida)
print(f"saída {processo.returncode}, interrompido={interrompido}, "
      f"menor RAM livre {minimo / 2**30:.2f} GB")
