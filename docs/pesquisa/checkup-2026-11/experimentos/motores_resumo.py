"""Comparação dos motores, oráculo e fusões simples sobre as linhas verificadas."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

L = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
MOTORES = [m for m in ("programa", "tesseract", "easyocr", "paddle") if any(x.get(m) for x in L)]
LANCE = re.compile(r"^[(\[]?(\d+\.{1,3}.*|[KQRBNDTCFP]?[a-h]?[1-8]?x?[a-h][1-8][+#!?]*[.,;)]*|O-O.*|0-0.*)$")
SAN = re.compile(r"^(\d+\.{1,3})?([KQRBNDTCFRP]?[a-h]?[1-8]?x?[a-h][1-8](=[QRBNDTCF])?|O-O(-O)?|0-0(-0)?)[+#]*[!?]*[.,;)]*$")


def lev_ops(p, t):
    n, m = len(p), len(t)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j - 1] + (p[i - 1] != t[j - 1]), d[i - 1][j] + 1, d[i][j - 1] + 1)
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


def lev(p, t):
    return sum(o != "ok" for o, _, _ in lev_ops(p, t))


def marca_lance(t):
    m = [False] * len(t)
    for x in re.finditer(r"\S+", t):
        if LANCE.match(x.group()):
            for k in range(x.start(), x.end()):
                m[k] = True
    return m


def normal(s):
    return (s.replace("—", "-").replace("–", "-").replace("’", "'").replace("‘", "'")
            .replace("“", '"').replace("”", '"'))


def medir(chave_ou_f, nome):
    f = chave_ou_f if callable(chave_ou_f) else (lambda x: x[chave_ou_f])
    tot = {"e": 0, "n": 0, "ln": 0, "le": 0, "perf": 0, "tl": 0, "tle": 0, "tls": 0, "en": 0}
    for x in L:
        p, t = f(x), x["verdade"]
        ops, lance = lev_ops(p, t), marca_lance(t)
        for o, a, b in ops:
            if o != "ok":
                tot["e"] += 1
                if b is not None and lance[b]:
                    tot["le"] += 1
            if b is not None and lance[b]:
                tot["ln"] += 1
        tot["n"] += len(t)
        tot["en"] += lev(normal(p), normal(t))
        tot["perf"] += p == t
        tp = p.split()
        for tok in t.split():
            if LANCE.match(tok):
                tot["tl"] += 1
                if tok not in tp:
                    tot["tle"] += 1
                    # o token errado parece um lance bem formado? (o erro que a forma não pega)
    print(f"{nome:26s} CER {tot['e']/tot['n']:.4f}  CER-tipogr {tot['en']/tot['n']:.4f}  "
          f"prosa {(tot['e']-tot['le'])/(tot['n']-tot['ln']):.4f}  lance {tot['le']/tot['ln']:.4f}  "
          f"linhas perfeitas {tot['perf']}/{len(L)}  tokens de lance errados {tot['tle']}/{tot['tl']}")
    return tot


print("linhas", len(L), "motores", MOTORES)
for m in MOTORES:
    medir(m, m)


def oraculo(ms):
    return lambda x: min((x[m] for m in ms), key=lambda p: lev(p, x["verdade"]))


for r in (2, 3, 4):
    if r <= len(MOTORES):
        medir(oraculo(MOTORES[:r]), "oráculo de linha " + "+".join(m[0] for m in MOTORES[:r]))


# --- fusão 1: a palavra com dígito, fora dos lances, vai à letra se a língua a conhece
try:
    from wordfreq import zipf_frequency
except ImportError:
    zipf_frequency = None
TROCAS = {"1": "li", "0": "oO", "9": "g", "5": "S", "8": "B", "4": "A", "3": "e", "7": "T"}


def conhece(palavra):
    return zipf_frequency(palavra.lower(), "pt") >= 1.5


def sem_digito(tok):
    nucleo = tok.strip(".,;:!?()\"'“”-—")
    if not nucleo or not any(c.isdigit() for c in nucleo) or not any(c.isalpha() for c in nucleo):
        return tok
    if SAN.match(tok) or LANCE.match(tok):
        return tok
    cands = [""]
    for c in nucleo:
        op = TROCAS.get(c, c) if c.isdigit() else c
        cands = [a + o for a in cands for o in op][:64]
    bons = [c for c in cands if conhece(c)]
    if not bons:
        return tok
    melhor = max(bons, key=lambda c: zipf_frequency(c.lower(), "pt"))
    return tok.replace(nucleo, melhor)


def f_lexico(x):
    return " ".join(sem_digito(t) for t in x["programa"].split(" "))


print()
medir(f_lexico, "programa + léxico díg→letra")
muda = [(x["programa"], f_lexico(x), x["verdade"]) for x in L if f_lexico(x) != x["programa"]]
piora = sum(lev(a, v) < lev(b, v) for a, b, v in muda)
print(f"   linhas mudadas {len(muda)}, pioradas {piora}")


# --- fusão 2: votação na espinha do programa
def votar(x, outros):
    p = x["programa"]
    if not p:
        return max((x[o] for o in outros), key=len) if outros else ""
    subs = {}
    insere = {}
    for o in outros:
        for op, a, b in lev_ops(p, x[o]):
            if op == "troca":
                subs.setdefault(a, []).append(x[o][b])
            elif op == "sobra":
                subs.setdefault(a, []).append("")
            elif op == "falta":
                chave = next((a2 for op2, a2, _ in lev_ops(p, x[o]) if False), None)
    return subs


def fusao_consenso(x):
    """Onde todos os outros motores concordam entre si e discordam do programa, vale o deles."""
    p = x["programa"]
    outros = [m for m in MOTORES if m != "programa" and x[m]]
    if not p or len(outros) < 2:
        return p
    votos = []
    for o in outros:
        mapa, pos = {}, 0
        ins = {}
        for op, a, b in lev_ops(p, x[o]):
            if op in ("ok", "troca"):
                mapa[a] = x[o][b]
                pos = a + 1
            elif op == "sobra":
                mapa[a] = ""
                pos = a + 1
            else:
                ins[pos] = ins.get(pos, "") + x[o][b]
        votos.append((mapa, ins))
    saida = []
    for i in range(len(p) + 1):
        ii = [v[1].get(i, "") for v in votos]
        if ii[0] and all(s == ii[0] for s in ii):
            saida.append(ii[0])
        if i == len(p):
            break
        vs = [v[0].get(i, p[i]) for v in votos]
        saida.append(vs[0] if all(s == vs[0] for s in vs) else p[i])
    return "".join(saida)


if len(MOTORES) >= 3:
    medir(fusao_consenso, "consenso sobre a espinha")
    medir(lambda x: " ".join(sem_digito(t) for t in fusao_consenso(x).split(" ")), "consenso + léxico")


# --- discordância como fila
print("\n-- discordância como sinal de revisão (por caractere do programa)")
for outros in ([m] for m in MOTORES[1:]):
    outro = outros[0]
    n = sel = err = pegos = 0
    for x in L:
        p, t = x["programa"], x["verdade"]
        if not p or not x[outro]:
            continue
        errado = {a for o, a, _ in lev_ops(p, t) if o in ("troca", "sobra")}
        gaps_v = sum(1 for o, a, _ in lev_ops(p, t) if o == "falta")
        dif = {a for o, a, _ in lev_ops(p, x[outro]) if o in ("troca", "sobra")}
        n += len(p)
        sel += len(dif)
        err += len(errado)
        pegos += len(errado & dif)
    print(f"  {outro}: marca {sel}/{n} ({sel/n:.1%}); erros pegos {pegos}/{err} ({pegos/max(err,1):.1%}); precisão {pegos/max(sel,1):.1%}")

# linhas onde a linha inteira discorda: fila por linha
for outro in MOTORES[1:]:
    conc = [x for x in L if x["programa"] and x["programa"] == x[outro]]
    if conc:
        print(f"  {outro}: linhas idênticas ao programa {len(conc)}/{len(L)}; dessas, erradas: {sum(c['programa']!=c['verdade'] for c in conc)}")
    conc = [x for x in L if x["programa"] and normal(x["programa"]) == normal(x[outro])]
    print(f"  {outro} (tipografia à parte): idênticas {len(conc)}/{len(L)}; erradas {sum(normal(c['programa'])!=normal(c['verdade']) for c in conc)}")

print("\n-- confusões por motor")
for m in MOTORES:
    c = Counter()
    for x in L:
        for o, a, b in lev_ops(x[m], x["verdade"]):
            if o == "troca":
                c[(x[m][a], x["verdade"][b])] += 1
    print(" ", m, [f"{a}→{b}:{n}" for (a, b), n in c.most_common(14)])

print("\n-- amostra de lances: V / P / T / E")
vistos = 0
for x in L:
    if re.search(r"\d\.", x["verdade"]) and x["programa"] != x["verdade"]:
        print("  V", x["verdade"][:90])
        for m in MOTORES:
            print("  ", m[0].upper(), x[m][:90])
        vistos += 1
        if vistos == 6:
            break
print("\nvazios nas linhas:", sum(x.get("vazios", 0) for x in L))
