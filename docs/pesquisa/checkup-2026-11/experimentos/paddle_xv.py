"""PP-OCRv6 (reconhecedor local, já baixado) nas mesmas linhas do Seirawan, pelos recortes do programa."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
RAIZ = Path(sys.argv[1])
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))
AQUI = Path(__file__).parent
sys.stdout.reconfigure(encoding="utf-8")


def main():
    import psutil
    from abbychess import pagina as pg
    from abbychess.projeto import ProjetoDeLivro
    from comum import PASTA_DOS_PDFS
    from paddleocr import TextRecognition

    L = json.loads((AQUI / "motores-xv.json").read_text(encoding="utf-8"))
    pdf = next(Path(PASTA_DOS_PDFS).rglob("Xadrez Vitorioso - Estrategias*.pdf"))
    modelo = TextRecognition(model_name="PP-OCRv6_medium_rec")
    print("RAM do processo MB", psutil.Process().memory_info().rss // 2**20, flush=True)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
        projeto = ProjetoDeLivro.criar(Path(pasta), "paddle", pdf)
        fonte = pg.fonte_do_projeto(projeto)
        t0, n = time.time(), 0
        for x in L:
            c = x.get("caixa")
            if not c:
                x["paddle"] = ""
                continue
            img = fonte.pagina(x["pagina"])
            r = img.crop((max(0, c[0] - 8), max(0, c[1] - 6), min(img.width, c[2] + 8),
                          min(img.height, c[3] + 6))).convert("RGB")
            saida = modelo.predict(input=np.array(r), batch_size=1)
            x["paddle"] = saida[0]["rec_text"] if saida else ""
            x["paddle_conf"] = float(saida[0]["rec_score"]) if saida else 0.0
            n += 1
        print("paddle s/linha", (time.time() - t0) / max(n, 1), "RAM MB",
              psutil.Process().memory_info().rss // 2**20, flush=True)
    (AQUI / "motores-xv-p.json").write_text(json.dumps(L, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
