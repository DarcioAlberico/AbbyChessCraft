"""Perícia do erro de OCR: de cada erro nas linhas verificadas, que motor o fez e se a fila o viu.

    python perita_ocr.py <raiz-do-repo> <saida.json> <indices>   lê as páginas e grava os dados
"""
import json
import re
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(sys.argv[1])
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))

FIGURINAS = set("♔♕♖♗♘♙♚♛♜♝♞♟")
LANCE = re.compile(r"^[(\[]?(\d+\.{1,3}|\d+\.{0,3}[♔♕♖♗♘KQRBNDTCFRP]?[a-h]?[1-8]?x?[a-h][1-8].*|"
                   r"[♔♕♖♗♘KQRBNDTCFRP]?[a-h]?[1-8]?x?[a-h][1-8].*|O-O.*|0-0.*|[♔♕♖♗♘].*)$")


def classe_do_char(c: str) -> str:
    if c == " ":
        return "espaco"
    if c in FIGURINAS:
        return "figurina"
    if c.isdigit():
        return "digito"
    if c.isalpha():
        return "letra"
    if c in ".,;:!?-–—()[]'\"“”‘’":
        return "pontuacao"
    return "simbolo"


def tokens_de_lance(t: str) -> list:
    """Para cada posição de `t`, se ela está num token de lance."""
    marcas, pos = [False] * len(t), 0
    for m in re.finditer(r"\S+", t):
        if LANCE.match(m.group()):
            for k in range(m.start(), m.end()):
                marcas[k] = True
    return marcas


def alinhar(p: str, t: str) -> list:
    """Levenshtein com volta: uma lista de (op, i, j)."""
    n, m = len(p), len(t)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j - 1] + (p[i - 1] != t[j - 1]), d[i - 1][j] + 1,
                          d[i][j - 1] + 1)
    ops, i, j = [], n, m
    while i or j:
        if i and j and d[i][j] == d[i - 1][j - 1] + (p[i - 1] != t[j - 1]):
            ops.append(("ok" if p[i - 1] == t[j - 1] else "troca", i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            ops.append(("sobra", i - 1, None))
            i -= 1
        else:
            ops.append(("falta", None, j - 1))
            j -= 1
    return ops[::-1]


def box_de_cada_char(texto: str, indices: list, boxes: list) -> list:
    """Para cada posição do texto da linha, o índice do box que a deu (ou None)."""
    mapa, pos = [None] * len(texto), 0
    for k in indices:
        char = boxes[k].char or ""
        for _ in char:
            while pos < len(texto) and texto[pos] == " ":
                pos += 1
            if pos < len(texto):
                mapa[pos] = k
                pos += 1
    return mapa


def ler(indices, livro="xv"):
    from abbychess import contexto, livro as lv, montagem as mo, pagina as pg
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro
    from medir import _caixa_relativa, casar
    from rotular import VERDADE

    gab = {i: json.loads((VERDADE / livro / f"i{i:03d}.json").read_text(encoding="utf-8"))
           for i in indices}
    from comum import PASTA_DOS_PDFS
    pdf = next(Path(PASTA_DOS_PDFS).rglob(gab[indices[0]]["pdf"]))
    registros, linhas_saida = [], []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
        projeto = ProjetoDeLivro.criar(Path(pasta), f"perita-{livro}", pdf)
        leitor = LeitorDoLivro.com_modelos_globais(projeto.pasta_de_padroes,
                                                   limiares=projeto.dados.limiares)
        fonte = pg.fonte_do_projeto(projeto)
        lv.reconhecer_paginas(projeto, fonte, leitor, indices)
        limiares = projeto.dados.limiares
        for i in indices:
            boxes = [b for b in (projeto.carregar_pagina(i) or []) if b.char]
            pendentes = contexto.pendentes(boxes, limiares)
            largura, altura = fonte.pagina(i).width, fonte.pagina(i).height
            angulo = fonte.inclinacao(i)
            linhas = mo._linhas(boxes)
            caixas = [_caixa_relativa((min(boxes[k].x1 for k in ln.indices), ln.topo,
                                       max(boxes[k].x2 for k in ln.indices), ln.pe),
                                      angulo, largura, altura) for ln in linhas]
            corpo = gab[i]["linhas_corpo"]
            par = {jv: ip for ip, jv in casar(caixas, [c["caixa_rel"] for c in corpo])}
            for jv, verd in enumerate(corpo):
                if not verd.get("texto_verificado"):
                    continue
                t = verd["texto"]
                ln = linhas[par[jv]] if jv in par else None
                p = ln.texto if ln else ""
                mapa = box_de_cada_char(p, ln.indices, boxes) if ln else []
                lance = tokens_de_lance(t)
                linhas_saida.append({"pagina": i, "verdade": t, "lida": p})
                for op, a, b in alinhar(p, t):
                    k = mapa[a] if a is not None and a < len(mapa) else None
                    bx = boxes[k] if k is not None else None
                    registros.append({
                        "pag": i, "op": op,
                        "p": p[a] if a is not None else "", "t": t[b] if b is not None else "",
                        "lance": lance[b] if b is not None else None,
                        "fonte": bx.source if bx else None,
                        "conf": round(float(bx.confidence), 4) if bx else None,
                        "fila": bool(pendentes[k]) if k is not None else None,
                        "box": k})
    return registros, linhas_saida


if __name__ == "__main__":
    saida = Path(sys.argv[2])
    indices = [int(x) for x in sys.argv[3].split(",")]
    r, l = ler(indices)
    saida.write_text(json.dumps({"registros": r, "linhas": l}, ensure_ascii=False), encoding="utf-8")
    print("registros", len(r), "linhas", len(l))
