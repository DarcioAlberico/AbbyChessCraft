"""Os motores por livro, com figurinas: CER por classe, consenso e discordância."""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
U = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
M = ["programa", "tesseract", "easyocr"]
PRETA = str.maketrans("♚♛♜♝♞♟", "♔♕♖♗♘♙")
FIG = set("♔♕♖♗♘♙")
SIMB = set("±∓⩲⩱=+#!?∞⨁⨀△□◯→↑⇆⟫")


def limpar(s):
    return re.sub(r"\s+", " ", s.translate(PRETA)).strip()


def ops(p, t):
    n, m = len(p), len(t)
    d = np.zeros((n + 1, m + 1), dtype=np.int32)
    d[0, :] = np.arange(m + 1)
    tt = np.frombuffer(t.encode("utf-32-le"), dtype=np.uint32) if m else np.array([], dtype=np.uint32)
    for i in range(1, n + 1):
        c = ord(p[i - 1])
        sub = d[i - 1, :-1] + (tt != c)
        ini = np.minimum(d[i - 1, 1:] + 1, sub)
        linha = np.empty(m + 1, dtype=np.int32)
        linha[0] = i
        linha[1:] = ini
        # inserções: varredura com acumulado
        linha = np.minimum.accumulate(linha - np.arange(m + 1)) + np.arange(m + 1)
        d[i] = linha
    saida, i, j = [], n, m
    while i or j:
        if i and j and d[i, j] == d[i - 1, j - 1] + (p[i - 1] != t[j - 1]):
            saida.append(("ok" if p[i - 1] == t[j - 1] else "troca", i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i and d[i, j] == d[i - 1, j] + 1:
            saida.append(("sobra", i - 1, None))
            i -= 1
        else:
            saida.append(("falta", None, j - 1))
            j -= 1
    return saida[::-1]


def classe(c):
    if c == " ":
        return "espaco"
    if c in FIG:
        return "figurina"
    if c in SIMB:
        return "simbolo"
    if c.isdigit():
        return "digito"
    if c.isalpha():
        return "letra"
    return "pontuacao"


TOKEN_LANCE = re.compile(r"(\d+\.{1,3}|[♔♕♖♗♘]|[a-h]x?[a-h]?[1-8]|O-O)")


def marca(t):
    m = [False] * len(t)
    for x in re.finditer(r"\S+", t):
        if TOKEN_LANCE.search(x.group()):
            for k in range(x.start(), x.end()):
                m[k] = True
    return m


def consenso(p, outros):
    if not p or any(not o for o in outros):
        return p
    votos = []
    for o in outros:
        mapa, ins, pos = {}, {}, 0
        for op, a, b in ops(p, o):
            if op in ("ok", "troca"):
                mapa[a] = o[b]
                pos = a + 1
            elif op == "sobra":
                mapa[a] = ""
                pos = a + 1
            else:
                ins[pos] = ins.get(pos, "") + o[b]
        votos.append((mapa, ins))
    s = []
    for i in range(len(p) + 1):
        ii = [v[1].get(i, "") for v in votos]
        if ii[0] and all(x == ii[0] for x in ii):
            s.append(ii[0])
        if i == len(p):
            break
        vs = [v[0].get(i, p[i]) for v in votos]
        # figurina do programa nunca é trocada: os outros não têm a classe
        s.append(p[i] if p[i] in FIG else (vs[0] if all(x == vs[0] for x in vs) else p[i]))
    return "".join(s)


grupos = defaultdict(list)
for u in U:
    grupos[u["livro"] + (" (" + u["tipo"] + ")")].append(u)
grupos["TODOS"] = U

for nome, us in grupos.items():
    print(f"\n=== {nome}: {len(us)} unidades, {sum(len(limpar(u['verdade'])) for u in us)} chars")
    for m in M + ["consenso"]:
        tot, err, tl, el = Counter(), Counter(), 0, 0
        e = n = sob = 0
        perf = 0
        for u in us:
            t = limpar(u["verdade"])
            p = (consenso(limpar(u["programa"]), [limpar(u["tesseract"]), limpar(u["easyocr"])])
                 if m == "consenso" else limpar(u[m]))
            perf += p == t
            mk = marca(t)
            for op, a, b in ops(p, t):
                if b is not None:
                    tot[classe(t[b])] += 1
                    tl += mk[b]
                    if op != "ok":
                        err[classe(t[b])] += 1
                        el += mk[b]
                if op != "ok":
                    e += 1
                if op == "sobra":
                    sob += 1
            n += len(t)
        cl = " ".join(f"{c}={err[c]}/{tot[c]}" for c in ("letra", "digito", "figurina", "simbolo", "pontuacao", "espaco") if tot[c])
        print(f"  {m:10s} CER {e/n:.4f} sobras {sob} | prosa {(e-el-sob)/max(n-tl,1):.4f} lance {el/max(tl,1):.4f} | {cl} | perfeitas {perf}")
    # discordância
    n = sel = er = peg = 0
    for u in us:
        p, t, o = limpar(u["programa"]), limpar(u["verdade"]), limpar(u["tesseract"])
        if not p or not o:
            continue
        errado = {a for op, a, _ in ops(p, t) if op in ("troca", "sobra")}
        dif = {a for op, a, _ in ops(p, o) if op in ("troca", "sobra")}
        n += len(p)
        sel += len(dif)
        er += len(errado)
        peg += len(errado & dif)
    print(f"  discordância P×T: marca {sel}/{n} ({sel/max(n,1):.1%}); erros pegos {peg}/{er} ({peg/max(er,1):.1%}); precisão {peg/max(sel,1):.1%}")
    n = sel = er = peg = 0
    for u in us:
        p, t, o = limpar(u["programa"]), limpar(u["verdade"]), limpar(u["easyocr"])
        if not p or not o:
            continue
        errado = {a for op, a, _ in ops(p, t) if op in ("troca", "sobra")}
        dif = {a for op, a, _ in ops(p, o) if op in ("troca", "sobra")}
        n += len(p)
        sel += len(dif)
        er += len(errado)
        peg += len(errado & dif)
    print(f"  discordância P×E: marca {sel}/{n} ({sel/max(n,1):.1%}); erros pegos {peg}/{er} ({peg/max(er,1):.1%}); precisão {peg/max(sel,1):.1%}")

for m in M:
    c = Counter()
    for u in U:
        p, t = limpar(u[m]), limpar(u["verdade"])
        for op, a, b in ops(p, t):
            if op == "troca":
                c[(p[a], t[b])] += 1
    print(m, [f"{a}→{b}:{n}" for (a, b), n in c.most_common(18)])
print("\namostras do programa em linhas de lance:")
for u in U:
    if u["tipo"] == "digital" and "♖" in u["verdade"] and limpar(u["programa"]) != limpar(u["verdade"]):
        print(" V", u["verdade"][:80])
        print(" P", u["programa"][:80])
        print(" T", u["tesseract"][:80])
        print(" E", u["easyocr"][:80])
        break
