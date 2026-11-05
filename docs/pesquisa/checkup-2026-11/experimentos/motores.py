"""Os motores lado a lado nas mesmas linhas verificadas do Seirawan: programa, Tesseract, EasyOCR.

    python motores.py <raiz-do-repo> <saida.json> <indices>
"""
import json
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(sys.argv[1])
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))


def main():
    import numpy as np
    from abbychess import livro as lv, montagem as mo, pagina as pg
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro
    from comum import PASTA_DOS_PDFS
    from medir import _caixa_relativa, casar
    from rotular import VERDADE

    saida = Path(sys.argv[2])
    indices = [int(x) for x in sys.argv[3].split(",")]
    gab = {i: json.loads((VERDADE / "xv" / f"i{i:03d}.json").read_text(encoding="utf-8"))
           for i in indices}
    pdf = next(Path(PASTA_DOS_PDFS).rglob(gab[indices[0]]["pdf"]))
    linhas_saida, recortes = [], []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
        projeto = ProjetoDeLivro.criar(Path(pasta), "motores", pdf)
        leitor = LeitorDoLivro.com_modelos_globais(projeto.pasta_de_padroes,
                                                   limiares=projeto.dados.limiares)
        fonte = pg.fonte_do_projeto(projeto)
        t0 = time.time()
        lv.reconhecer_paginas(projeto, fonte, leitor, indices)
        print("programa s/pág", (time.time() - t0) / len(indices), flush=True)
        for i in indices:
            todos = projeto.carregar_pagina(i) or []
            boxes = [b for b in todos if b.char]
            vazios = [b for b in todos if not b.char]
            imagem = fonte.pagina(i)
            largura, altura = imagem.width, imagem.height
            angulo = fonte.inclinacao(i)
            linhas = mo._linhas(boxes)
            px = [(min(boxes[k].x1 for k in ln.indices), ln.topo,
                   max(boxes[k].x2 for k in ln.indices), ln.pe) for ln in linhas]
            caixas = [_caixa_relativa(c, angulo, largura, altura) for c in px]
            corpo = gab[i]["linhas_corpo"]
            par = {jv: ip for ip, jv in casar(caixas, [c["caixa_rel"] for c in corpo])}
            for jv, verd in enumerate(corpo):
                if not verd.get("texto_verificado") or jv not in par:
                    if verd.get("texto_verificado"):
                        linhas_saida.append({"pagina": i, "verdade": verd["texto"], "programa": "",
                                             "tesseract": "", "easyocr": "", "vazios": 0})
                    continue
                ln, c = linhas[par[jv]], px[par[jv]]
                n_vazios = sum(1 for b in vazios if c[0] <= (b.x1 + b.x2) / 2 <= c[2]
                               and c[1] <= (b.y1 + b.y2) / 2 <= c[3])
                x1, y1 = max(0, c[0] - 8), max(0, c[1] - 6)
                x2, y2 = min(largura, c[2] + 8), min(altura, c[3] + 6)
                recortes.append((len(linhas_saida), imagem.crop((x1, y1, x2, y2)).convert("L")))
                linhas_saida.append({"pagina": i, "verdade": verd["texto"], "programa": ln.texto,
                                     "tesseract": "", "easyocr": "", "vazios": n_vazios,
                                     "caixa": list(map(int, c))})
    del projeto, leitor, fonte

    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    t0 = time.time()
    for k, img in recortes:
        linhas_saida[k]["tesseract"] = pytesseract.image_to_string(
            img, lang="por", config="--psm 7").strip()
    print("tesseract s/linha", (time.time() - t0) / len(recortes), flush=True)
    saida.write_text(json.dumps(linhas_saida, ensure_ascii=False), encoding="utf-8")

    try:
        import easyocr
        leitor_e = easyocr.Reader(["pt"], gpu=False, download_enabled=False, verbose=False)
        t0 = time.time()
        for k, img in recortes:
            texto = leitor_e.recognize(np.array(img), detail=0, paragraph=False, batch_size=1)
            linhas_saida[k]["easyocr"] = " ".join(texto).strip()
        print("easyocr s/linha", (time.time() - t0) / len(recortes), flush=True)
    except Exception as erro:
        print("easyocr indisponível:", repr(erro)[:300], flush=True)
    saida.write_text(json.dumps(linhas_saida, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
