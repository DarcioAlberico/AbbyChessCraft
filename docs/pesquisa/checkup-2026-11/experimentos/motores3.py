"""Mesma bateria do motores2, com o PP-OCRv6 junto (linhas do programa como recortes)."""
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
BENCH = Path(r"C:\Python-Chess2\PyBoxEditor_Tkinter\benchmarks")
DVORETSKY = "Dvoretsky - Dvoretsky's Endgame Manual 6*(2025).pdf"
PAG_DVORETSKY = [100, 101, 200, 201, 300, 400]


def main():
    from abbychess import livro as lv, montagem as mo, pagina as pg
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro
    from comum import PASTA_DOS_PDFS
    from medir import casar
    from paddleocr import TextRecognition
    import fitz

    sys.argv = ["x", str(RAIZ), "x"]
    fonte_m2 = (AQUI / "motores2.py").read_text(encoding="utf-8")
    ns = {"__name__": "m2", "__file__": str(AQUI / "motores2.py")}
    exec(fonte_m2[:fonte_m2.index("def ler_livro")], ns)
    linhas_nativas = ns["linhas_nativas"]

    U = json.loads((AQUI / "motores2.json").read_text(encoding="utf-8"))
    modelo = TextRecognition(model_name="PP-OCRv6_medium_rec")

    def ler(recorte):
        s = modelo.predict(input=np.array(recorte.convert("RGB")), batch_size=1)
        return s[0]["rec_text"] if s else ""

    def por_pdf(pdf, indices):
        saida = {}
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
            projeto = ProjetoDeLivro.criar(Path(pasta), "m3", pdf)
            leitor = LeitorDoLivro.com_modelos_globais(projeto.pasta_de_padroes,
                                                       limiares=projeto.dados.limiares)
            fonte = pg.fonte_do_projeto(projeto)
            lv.reconhecer_paginas(projeto, fonte, leitor, indices)
            for i in indices:
                boxes = [b for b in (projeto.carregar_pagina(i) or []) if b.char]
                imagem = fonte.pagina(i)
                linhas = mo._linhas(boxes)
                px = [(min(boxes[k].x1 for k in ln.indices), ln.topo,
                       max(boxes[k].x2 for k in ln.indices), ln.pe) for ln in linhas]
                textos = []
                for c in px:
                    textos.append(ler(imagem.crop((max(0, c[0] - 8), max(0, c[1] - 6),
                                                   min(imagem.width, c[2] + 8),
                                                   min(imagem.height, c[3] + 6)))))
                saida[i] = {"caixas": px, "programa": [ln.texto for ln in linhas], "paddle": textos}
        return saida

    corpus = json.loads((BENCH / "corpus_v2.json").read_text(encoding="utf-8"))
    t0 = time.time()
    k = 0
    for doc in corpus["documents"]:
        pdf = BENCH / doc["source"]
        n = fitz.open(pdf).page_count
        indices = [p["page_index"] - 1 if n > p["page_index"] - 1 and n > 1 else 0 for p in doc["pages"]]
        lidos = por_pdf(pdf, indices)
        for i in indices:
            # as unidades escaneadas são as 4 primeiras, na ordem do corpus
            assert U[k]["livro"] == doc["id"], (U[k]["livro"], doc["id"])
            assert U[k]["programa"] == "\n".join(lidos[i]["programa"]), "leitura mudou"
            U[k]["paddle"] = "\n".join(lidos[i]["paddle"])
            k += 1
    pdf_d = next(Path(PASTA_DOS_PDFS).rglob(DVORETSKY))
    lidos = por_pdf(pdf_d, PAG_DVORETSKY)
    for i in PAG_DVORETSKY:
        nat = linhas_nativas(pdf_d, i)
        par = {jv: ip for ip, jv in casar(lidos[i]["caixas"], [c for _, c in nat])}
        for jv, (t, _) in enumerate(nat):
            assert U[k]["verdade"] == t
            ip = par.get(jv)
            U[k]["paddle"] = lidos[i]["paddle"][ip] if ip is not None else ""
            k += 1
    print("segundos", time.time() - t0, "unidades", k, "de", len(U), flush=True)
    (AQUI / "motores3.json").write_text(json.dumps(U, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
