"""Os motores em livros com figurinas: 4 páginas escaneadas revisadas (corpus_v2) e 6 digitais.

    python motores2.py <raiz-do-repo> <saida.json>
"""
import json
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(sys.argv[1])
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))
AQUI = Path(__file__).parent
BENCH = Path(r"C:\Python-Chess2\PyBoxEditor_Tkinter\benchmarks")
DVORETSKY = "Dvoretsky - Dvoretsky's Endgame Manual 6*(2025).pdf"
PAG_DVORETSKY = [100, 101, 200, 201, 300, 400]
FIG = {"K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘"}


def linhas_nativas(pdf, i):
    import fitz
    doc = fitz.open(pdf)
    saida = []
    for b in doc[i].get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            spans = l["spans"]
            if any("Merida" in s["font"] or s["font"] == "ArialMT" for s in spans):
                continue
            t = "".join("".join(FIG.get(c, c) for c in s["text"]) if "SemFig" in s["font"]
                        else s["text"] for s in spans).strip()
            if t:
                saida.append((t, [v * 300 / 72 for v in l["bbox"]]))
    doc.close()
    return saida


def ler_livro(pdf, indices, lote_de_linhas):
    from abbychess import livro as lv, montagem as mo, pagina as pg
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
        projeto = ProjetoDeLivro.criar(Path(pasta), "motores", pdf)
        leitor = LeitorDoLivro.com_modelos_globais(projeto.pasta_de_padroes,
                                                   limiares=projeto.dados.limiares)
        fonte = pg.fonte_do_projeto(projeto)
        t0 = time.time()
        lv.reconhecer_paginas(projeto, fonte, leitor, indices)
        print(pdf.name[:30], "s/pág", round((time.time() - t0) / len(indices), 1), flush=True)
        for i in indices:
            boxes = [b for b in (projeto.carregar_pagina(i) or []) if b.char]
            imagem = fonte.pagina(i)
            largura, altura = imagem.width, imagem.height
            linhas = mo._linhas(boxes)
            px = [(min(boxes[k].x1 for k in ln.indices), ln.topo,
                   max(boxes[k].x2 for k in ln.indices), ln.pe) for ln in linhas]
            recortes = [imagem.crop((max(0, c[0] - 8), max(0, c[1] - 6), min(largura, c[2] + 8),
                                     min(altura, c[3] + 6))).convert("L") for c in px]
            lote_de_linhas[(pdf.name, i)] = {"textos": [ln.texto for ln in linhas], "caixas": px,
                                             "recortes": recortes}


def main():
    import numpy as np
    from comum import PASTA_DOS_PDFS
    from medir import casar

    saida = Path(sys.argv[2])
    pasta_crops = AQUI / "crops"
    pasta_crops.mkdir(exist_ok=True)
    corpus = json.loads((BENCH / "corpus_v2.json").read_text(encoding="utf-8"))
    leituras, unidades = {}, []
    tarefas = []
    for doc in corpus["documents"]:
        pdf = BENCH / doc["source"]
        import fitz
        n = fitz.open(pdf).page_count
        for p in doc["pages"]:
            i = p["page_index"] - 1 if n > p["page_index"] - 1 and n > 1 else 0
            tarefas.append((doc["id"], pdf, i, BENCH / p["reference"]))
    por_pdf = {}
    for t in tarefas:
        por_pdf.setdefault(t[1], []).append(t[2])
    for pdf, indices in por_pdf.items():
        ler_livro(pdf, indices, leituras)
    pdf_d = next(Path(PASTA_DOS_PDFS).rglob(DVORETSKY))
    ler_livro(pdf_d, PAG_DVORETSKY, leituras)

    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    import easyocr
    leitor_e = easyocr.Reader(["en"], gpu=False, download_enabled=False, verbose=False)
    t0, n_l = time.time(), 0
    for chave, d in leituras.items():
        d["tesseract"], d["easyocr"] = [], []
        for k, img in enumerate(d["recortes"]):
            img.save(pasta_crops / f"{abs(hash(chave[0])) % 10000}_{chave[1]}_{k}.png")
            d["tesseract"].append(pytesseract.image_to_string(img, lang="eng", config="--psm 7").strip())
            d["easyocr"].append(" ".join(leitor_e.recognize(np.array(img), detail=0, paragraph=False,
                                                            batch_size=1)).strip())
            n_l += 1
    print("t+e s/linha", (time.time() - t0) / max(n_l, 1), flush=True)

    # as páginas escaneadas: a unidade é a página, com o texto na ordem do programa
    for ident, pdf, i, ref in tarefas:
        d = leituras[(pdf.name, i)]
        unidades.append({"livro": ident, "tipo": "escaneado", "pagina": i,
                         "verdade": ref.read_text(encoding="utf-8"),
                         "programa": "\n".join(d["textos"]), "tesseract": "\n".join(d["tesseract"]),
                         "easyocr": "\n".join(d["easyocr"])})
    # o digital: a unidade é a linha, casada pela caixa
    for i in PAG_DVORETSKY:
        d = leituras[(pdf_d.name, i)]
        nat = linhas_nativas(pdf_d, i)
        par = {jv: ip for ip, jv in casar(d["caixas"], [c for _, c in nat])}
        for jv, (t, _) in enumerate(nat):
            ip = par.get(jv)
            unidades.append({"livro": "dvoretsky", "tipo": "digital", "pagina": i, "verdade": t,
                             "programa": d["textos"][ip] if ip is not None else "",
                             "tesseract": d["tesseract"][ip] if ip is not None else "",
                             "easyocr": d["easyocr"][ip] if ip is not None else ""})
    saida.write_text(json.dumps(unidades, ensure_ascii=False), encoding="utf-8")
    print("unidades", len(unidades))


if __name__ == "__main__":
    main()
