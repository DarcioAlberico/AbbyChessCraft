r"""O itálico do OCR (`pagina.efeitos_da_pagina`) contra o itálico da fonte de um PDF nascido
digital, e o que ele marca num livro escaneado (pendência do passo I).

    .venv\Scripts\python.exe ferramentas\medir_italico.py --pdf "<Odds & Ends.pdf>"
        [--ajuste 5-20,74-85,...] [--validacao 21-40,241,...]
        [--fatia tests\dados\fatia\xv-i020-026-inicial.zip --folha italicos-da-fatia.png]

No PDF nascido digital, cada glifo segmentado da página renderizada ganha o caractere e o
rótulo do glifo da camada que contém o centro dele: itálico pela bandeira da fonte ou pelo
nome (a regra de `core.pdf_nativo`). Contam as palavras com o itálico medido e o rótulo todo
igual. As páginas de `--ajuste` foram as usadas para escolher os limiares de
`pagina._italicos`; as de `--validacao`, não.

Na fatia (o livro escaneado, sem rótulo), conta as palavras marcadas por página e, com
`--folha`, monta uma imagem com o recorte de cada uma, para ver a olho.

Grava `docs/medidas/AAAA-MM-DD-italico.json`.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
import tempfile
import time
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))

from comum import destino_da_medida, estado_do_git  # noqa: E402

AJUSTE = "5-20,74-85,264,281,586,588,601,642,643,669"
VALIDACAO = ("21-40,241,242,256,258,259,266,282,286,287,306,312,329,335,340,347,360,456,461,"
             "469,475,490,492,497,498,501,593,595,597,598,599,606,608,612,614,617,647,649,652,"
             "670,679")
#: A regra do itálico pela fonte (`core.pdf_nativo._e_italico`, que é privado).
_ITALICO_NO_NOME = re.compile(r"(italic|oblique|kursiv|[-_,](bold|semibold|medium)?it(mt)?$)")
_SUBCONJUNTO = re.compile(r"^[A-Z]{6}\+")


def paginas(texto: str) -> list:
    """`5-7,9` → [5, 6, 7, 9] (índices do PDF, a partir de 0)."""
    saida = []
    for parte in texto.split(","):
        a, _, b = parte.strip().partition("-")
        saida += list(range(int(a), int(b or a) + 1))
    return saida


def _glifos_da_camada(page) -> list:
    """`(x1, y1, x2, y2, char, italico)` dos glifos horizontais da camada, em pontos."""
    saida = []
    for bloco in page.get_text("rawdict")["blocks"]:
        for linha in bloco.get("lines", []):
            if tuple(linha["dir"]) != (1.0, 0.0):
                continue
            for span in linha["spans"]:
                nome = _SUBCONJUNTO.sub("", span["font"]).lower()
                italico = bool(span["flags"] & 2) or bool(_ITALICO_NO_NOME.search(nome))
                for c in span["chars"]:
                    if c["c"].strip():
                        saida.append((*c["bbox"], c["c"], italico))
    return saida


def medir_pdf(pdf: Path, indices: list) -> dict:
    import fitz

    from abbychess import pagina as pg
    from core.notacao import palavras_da_pagina

    fonte = pg.FonteDePaginas(pdf)
    doc = fitz.open(pdf)
    vp = fp = fn = vn = sem_medida = 0
    tempos, falsos = [], []
    for indice in indices:
        imagem = fonte.pagina(indice)
        page = doc[indice]
        escala = imagem.width / page.rect.width
        glifos = _glifos_da_camada(page)
        boxes = pg.segmentar(imagem)
        rotulos = []
        for b in boxes:
            cx, cy = (b.x1 + b.x2) / 2 / escala, (b.y1 + b.y2) / 2 / escala
            achado = next((g for g in glifos if g[0] <= cx <= g[2] and g[1] <= cy <= g[3]), None)
            b.char = achado[4] if achado else ""
            rotulos.append(achado[5] if achado else None)
        t0 = time.perf_counter()
        _negritos, italicos = pg.efeitos_da_pagina(imagem, boxes)
        tempos.append((time.perf_counter() - t0) * 1000)
        for linha in palavras_da_pagina(boxes):
            for palavra in linha:
                indices_da_palavra = [s.indice for s in palavra.simbolos]
                letras = [i for i in indices_da_palavra if boxes[i].char.isalpha()]
                verdade = {rotulos[i] for i in letras if rotulos[i] is not None}
                if len(letras) < 3 or len(verdade) != 1:
                    continue
                medido = italicos[letras[0]]
                if medido is None:
                    sem_medida += 1
                    continue
                certo = verdade.pop()
                texto = "".join(boxes[i].char for i in indices_da_palavra)
                if medido and certo:
                    vp += 1
                elif medido:
                    fp += 1
                    falsos.append(f"p{indice + 1} {texto}")
                elif certo:
                    fn += 1
                else:
                    vn += 1
    tempos.sort()
    return {"paginas": [i + 1 for i in indices], "italicas": vp + fn, "retas": fp + vn,
            "verdadeiros": vp, "falsos": fp, "perdidas": fn, "sem_medida": sem_medida,
            "revocacao": round(vp / max(1, vp + fn), 4),
            "precisao": round(vp / max(1, vp + fp), 4) if vp + fp else None,
            "falsos_exemplos": falsos[:20],
            "ms_por_pagina_p50": round(tempos[len(tempos) // 2], 1) if tempos else None}


def medir_fatia(zip_: Path, folha: Path | None) -> dict:
    import numpy as np
    from PIL import Image

    from abbychess import pagina as pg
    from abbychess.projeto import ProjetoDeLivro
    from core.notacao import palavras_da_pagina

    pasta = Path(tempfile.mkdtemp())
    with zipfile.ZipFile(zip_) as z:
        z.extractall(pasta)
    projeto = ProjetoDeLivro.abrir(next(p.parent for p in pasta.rglob("projeto.json")))
    por_pagina, recortes = {}, []
    try:
        fonte = pg.fonte_do_projeto(projeto)
        for indice in projeto.paginas_lidas():
            modelo = projeto.carregar_modelo(indice)
            boxes = [b.entry for b in modelo.boxes]
            imagem = fonte.pagina(indice)
            _negritos, italicos = pg.efeitos_da_pagina(imagem, boxes)
            cinza = pg.cinza(imagem)
            medidas = marcadas = 0
            palavras = []
            for linha in palavras_da_pagina(boxes):
                for palavra in linha:
                    indices = [s.indice for s in palavra.simbolos]
                    if italicos[indices[0]] is None:
                        continue
                    medidas += 1
                    if italicos[indices[0]]:
                        marcadas += 1
                        texto = "".join(boxes[i].char for i in indices)
                        palavras.append(texto)
                        x1, y1 = min(boxes[i].x1 for i in indices), min(boxes[i].y1 for i in indices)
                        x2, y2 = max(boxes[i].x2 for i in indices), max(boxes[i].y2 for i in indices)
                        recortes.append(cinza[max(0, y1 - 4):y2 + 4, max(0, x1 - 4):x2 + 4])
            por_pagina[indice + 1] = {"palavras_medidas": medidas, "italicas": marcadas,
                                      "quais": palavras}
    finally:
        projeto.fechar()
    if folha is not None and recortes:
        largura = max(r.shape[1] for r in recortes)
        altura = sum(r.shape[0] + 6 for r in recortes)
        tela = np.full((altura, largura), 255, np.uint8)
        y = 0
        for r in recortes:
            tela[y:y + r.shape[0], :r.shape[1]] = r
            y += r.shape[0] + 6
        Image.fromarray(tela).save(folha)
    return {"projeto": str(zip_.relative_to(RAIZ)) if zip_.is_relative_to(RAIZ) else str(zip_),
            "paginas": por_pagina}


def main(argv=None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--pdf", type=Path, required=True,
                            help="o PDF nascido digital com itálico na camada (Odds & Ends)")
    analisador.add_argument("--ajuste", default=AJUSTE)
    analisador.add_argument("--validacao", default=VALIDACAO)
    analisador.add_argument("--fatia", type=Path,
                            default=RAIZ / "tests" / "dados" / "fatia" / "xv-i020-026-inicial.zip")
    analisador.add_argument("--folha", type=Path, help="a imagem com as palavras marcadas na fatia")
    args = analisador.parse_args(argv)

    from abbychess import pagina as pg

    resultado = {
        "data": datetime.date.today().isoformat(), "git": estado_do_git(),
        "pdf": args.pdf.name,
        "regra": {"inclinacao_graus": pg.INCLINACAO_DO_ITALICO, "forca": pg.FORCA_DO_ITALICO,
                  "minimo_de_letras": pg.MINIMO_DE_LETRAS_DO_ITALICO,
                  "janela_graus": pg.JANELA_DO_ITALICO, "reta_ate_graus": pg.RETA_ATE},
        "ajuste": medir_pdf(args.pdf, paginas(args.ajuste)),
        "validacao": medir_pdf(args.pdf, paginas(args.validacao)),
    }
    if args.fatia:
        resultado["fatia"] = medir_fatia(args.fatia, args.folha)
    destino = destino_da_medida(resultado["data"], "italico")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
    for nome in ("ajuste", "validacao"):
        r = resultado[nome]
        print(f"{nome}: {r['italicas']} itálicas, {r['retas']} retas; revocação {r['revocacao']}, "
              f"precisão {r['precisao']}, falsos {r['falsos']}; {r['ms_por_pagina_p50']} ms/página")
    if "fatia" in resultado:
        for pagina, r in resultado["fatia"]["paginas"].items():
            print(f"fatia p{pagina}: {r['italicas']} de {r['palavras_medidas']} {r['quais'][:12]}")
    print(destino)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
