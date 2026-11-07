"""E0: a cadeia do core (`core.livro`, CNN + Tesseract) contra o programa, nas páginas verificadas.

Compara por página, com o espaço normalizado e a hifenização de fim de linha desfeita nos dois
lados: o core junta parágrafos, e a comparação linha a linha não cabe.
    python e0_core_livro.py <raiz> <saida.json> <indices>
"""
import json
import re
import sys
import time
from pathlib import Path

RAIZ = Path(sys.argv[1])
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))
sys.stdout.reconfigure(encoding="utf-8")


def texto_dos_blocos(pagina):
    partes = []
    for b in pagina.blocos:
        t = getattr(b, "texto", None)
        if t:
            partes.append(t)
    return " ".join(partes)


def main():
    import fitz
    from core import livro
    from core.services.learning_service import LearningService
    from core.services.ocr_service import OCRService
    from comum import PASTA_DOS_PDFS
    from rotular import VERDADE

    indices = [int(x) for x in sys.argv[3].split(",")]
    gab = {i: json.loads((VERDADE / "xv" / f"i{i:03d}.json").read_text(encoding="utf-8")) for i in indices}
    pdf = next(Path(PASTA_DOS_PDFS).rglob(gab[indices[0]]["pdf"]))
    aprendizado = LearningService()
    if not aprendizado.load_predictor():
        raise SystemExit(aprendizado.motivo_do_modelo())
    classificar = aprendizado.leitor_de_texto("pt")
    ocr = OCRService()

    def ler_pagina(imagem):
        return ocr.tesseract_pagina_detalhada_conf(imagem, "pt")

    def ler_faixa(faixa):
        return ocr.tesseract_faixa_detalhada_conf(faixa, "pt")

    doc = fitz.open(pdf)
    saida = []
    for i in indices:
        t0 = time.time()
        pag = livro.extrair_pagina(doc[i], classificar, numero=i, ler_pagina=ler_pagina,
                                   ler_faixa=ler_faixa, idioma_ocr="pt")
        verdade = [c["texto"] for c in gab[i]["linhas_corpo"] if c.get("texto_verificado")]
        saida.append({"pagina": i, "segundos": round(time.time() - t0, 1), "verdade": verdade,
                      "core": texto_dos_blocos(pag)})
        print(i, "s", saida[-1]["segundos"], flush=True)
    doc.close()
    Path(sys.argv[2]).write_text(json.dumps(saida, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
