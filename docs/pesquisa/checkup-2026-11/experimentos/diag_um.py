"""De onde vem o `1` no lugar de h, m, l, n: fonte, confiança e forma do box, em Aagaard e Seirawan."""
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

RAIZ = Path(sys.argv[1])
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))
sys.stdout.reconfigure(encoding="utf-8")
AQUI = Path(__file__).parent
BENCH = Path(r"C:\Python-Chess2\PyBoxEditor_Tkinter\benchmarks")


def main():
    from abbychess import contexto, livro as lv, montagem as mo, pagina as pg
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro
    from comum import PASTA_DOS_PDFS
    from PIL import Image, ImageDraw

    casos = [("aagaard", BENCH / "corpus_v2/source/aagaard.pdf", 29),
             ("xv", next(Path(PASTA_DOS_PDFS).rglob("Xadrez Vitorioso - Estrategias*.pdf")), 22)]
    for nome, pdf, i in casos:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
            projeto = ProjetoDeLivro.criar(Path(pasta), "diag", pdf)
            leitor = LeitorDoLivro.com_modelos_globais(projeto.pasta_de_padroes,
                                                       limiares=projeto.dados.limiares)
            fonte = pg.fonte_do_projeto(projeto)
            lv.reconhecer_paginas(projeto, fonte, leitor, [i])
            boxes = [b for b in (projeto.carregar_pagina(i) or [])]
            imagem = fonte.pagina(i).convert("L")
            print("==", nome, "boxes", len(boxes), "vazios", sum(not b.char for b in boxes))
            print(" fontes", Counter(b.source for b in boxes).most_common())
            alturas = sorted(b.y2 - b.y1 for b in boxes if b.char)
            mediana = alturas[len(alturas) // 2]
            print(" mediana da altura", mediana)
            pend = contexto.pendentes([b for b in boxes if b.char], projeto.dados.limiares)
            lidos = [b for b in boxes if b.char]
            linhas = mo._linhas(lidos)
            digitos_em_palavra = []
            for ln in linhas:
                for tok in ln.texto.split():
                    limpo = tok.strip(".,;:!?()")
                    if any(c.isalpha() for c in limpo) and any(c in "019" for c in limpo) and len(limpo) > 3:
                        digitos_em_palavra.append(tok)
            print(" palavras com dígito:", len(digitos_em_palavra), digitos_em_palavra[:40])
            uns = [(b, p) for b, p in zip(lidos, pend) if b.char == "1"]
            print(" boxes '1':", len(uns), "fontes", Counter(b.source for b, _ in uns).most_common(),
                  "na fila", sum(p for _, p in uns))
            print(" conf dos '1':", sorted(round(float(b.confidence), 2) for b, _ in uns)[:30])
            print(" w×h dos '1':", Counter((b.x2 - b.x1, b.y2 - b.y1) for b, _ in uns).most_common(12))
            # folha com os recortes dos '1' e do texto de uma linha
            folha = Image.new("L", (900, 200), 255)
            x = 5
            for b, _ in uns[:40]:
                c = imagem.crop((b.x1, b.y1, b.x2, b.y2))
                folha.paste(c, (x, 5))
                x += c.width + 6
            d = ImageDraw.Draw(folha)
            folha.save(AQUI / f"uns-{nome}.png")
            for ln in linhas[6:14]:
                print("  |", ln.texto[:95])
            leitor_rede = leitor.rede
            del leitor_rede


if __name__ == "__main__":
    main()
