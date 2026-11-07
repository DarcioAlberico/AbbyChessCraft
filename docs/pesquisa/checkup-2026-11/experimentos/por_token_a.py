"""Contas da crítica 2. Saída só com contagens; o texto de livro não sai daqui."""
import json, math, random, re, sys
from collections import Counter, defaultdict
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
import sys
S = sys.argv[1].rstrip("/\\") + "/"  # a pasta com motores3.json, motores-xv-p.json e perita-xv.json
U = json.load(open(S + "motores3.json", encoding="utf-8"))
X = json.load(open(S + "motores-xv-p.json", encoding="utf-8"))
for x in X:
    x["livro"], x["tipo"] = "seirawan", "escaneado"
TODAS = X + U
PRETA = str.maketrans("♚♛♜♝♞♟", "♔♕♖♗♘♙")
FIG = set("♔♕♖♗♘♙")


def limpar(s):
    return re.sub(r"\s+", " ", (s or "").translate(PRETA)).strip()


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


# as três regras dos scripts
LANCE = re.compile(r"^[(\[]?(\d+\.{1,3}|\d+\.{0,3}[♔♕♖♗♘KQRBNDTCFRP]?[a-h]?[1-8]?x?[a-h][1-8].*|"
                   r"[♔♕♖♗♘KQRBNDTCFRP]?[a-h]?[1-8]?x?[a-h][1-8].*|O-O.*|0-0.*|[♔♕♖♗♘].*)$")
SAN = re.compile(r"^(\d+\.{1,3})?([♔♕♖♗♘KQRBNDTCFP]?[a-h]?[1-8]?x?[a-h][1-8](=[♕♖♗♘QRBNDTCF])?|O-O(-O)?|0-0(-0)?)[+#]*[!?]*[.,;)]*$")
MARCA = re.compile(r"(\d+\.{1,3}|[♔♕♖♗♘]|[a-h]x?[a-h]?[1-8]|O-O)")
# gramática de referência: tira a pontuação de fora, número, núcleo SAN, sufixos
G = re.compile(r"^[(\[{]*(\d+\s?\.{1,3}|\d+…)?(?P<nucleo>[♔♕♖♗♘KQRBNDTCFPSL]?[a-h]?[1-8]?[x:]?[-–]?[a-h][1-8](=?[♕♖♗♘♔QRBNDTCF])?(e\.?p\.?)?|[O0]-[O0](-[O0])?)[+#†‡]*[!?±∓⩲⩱=∞]*[)\]}.,;:]*$")


def e_lance(tk):
    return bool(G.match(tk))


def tokens(s):
    return [(m.start(), m.end(), m.group()) for m in re.finditer(r"\S+", s)]


print("=== 1. As regras de token, sobre a verdade (por livro)")
for livro in ("seirawan", "aagaard-calculation", "nunn-rook-endings", "yusupov-evolution-1", "dvoretsky"):
    c = Counter()
    for u in (u for u in TODAS if u["livro"] == livro):
        for _, _, tk in tokens(limpar(u["verdade"])):
            c["todos"] += 1
            a, b, d, g = bool(SAN.match(tk)), bool(MARCA.search(tk)), bool(LANCE.match(tk)), e_lance(tk)
            c["SAN"] += a; c["marca"] += b; c["LANCE"] += d; c["G"] += g
            f = any(x in FIG for x in tk)
            c["com_figurina"] += f
            c["fig_fora_de_SAN"] += f and not a
            c["G_fora_de_SAN"] += g and not a
            c["SAN_fora_de_G"] += a and not g
            c["marca_nao_G"] += b and not g
            c["LANCE_nao_G"] += d and not g
            c["G_com_fig"] += g and f
            c["so_numero"] += bool(re.fullmatch(r"[(\[]?\d+\.{1,3}", tk))
    print(livro, dict(c))


def analisar(u, outros=("paddle", "tesseract")):
    """Por token da verdade: certo?, classe; por token lido: marcado por cada motor."""
    p, t = limpar(u["programa"]), limpar(u["verdade"])
    a = ops(p, t)
    t2p = {}
    sobras = set()
    faltas = set()
    for op, i, j in a:
        if j is not None and i is not None:
            t2p[j] = (i, op)
        elif j is not None:
            faltas.add(j)
        else:
            sobras.add(i)
    tp = tokens(p)
    idx = [None] * len(p)
    for k, (s, e, _) in enumerate(tp):
        for q in range(s, e):
            idx[q] = k
    marcas = {}
    for o in outros:
        ot = limpar(u.get(o, ""))
        mk = set()
        if ot and p:
            pos = 0
            for op, i, j in ops(p, ot):
                if i is not None:
                    pos = i
                if op in ("troca", "sobra") and idx[i] is not None:
                    mk.add(idx[i])
                elif op == "falta":
                    # inserção: marca o token em volta, se houver
                    q = pos if pos < len(p) else len(p) - 1
                    if q >= 0 and idx[q] is not None:
                        mk.add(idx[q])
        mk = {k for k in mk if not any(c in FIG for c in tp[k][2])}
        marcas[o] = mk
    saida = []
    for s, e, tk in tokens(t):
        lidos = set()
        ok = True
        for j in range(s, e):
            if j in t2p:
                i, op = t2p[j]
                if idx[i] is not None:
                    lidos.add(idx[i])
                if op != "ok":
                    ok = False
            else:
                ok = False
        if ok and len(lidos) != 1:
            ok = False
        if ok:
            k = next(iter(lidos))
            ok = tp[k][2] == tk
        saida.append({"tk": tk, "ok": ok, "lidos": lidos, "lance": e_lance(tk), "fig": any(c in FIG for c in tk)})
    return saida, tp, marcas, p, t


def bloco(us, rot):
    c = Counter()
    for u in us:
        sai, tp, marcas, p, t = analisar(u)
        c["lidos"] += len(tp)
        for o, mk in marcas.items():
            c["marc_" + o] += len(mk)
        for r in sai:
            cl = "lance" if r["lance"] else "outro"
            c[cl] += 1
            if r["fig"]:
                c[cl + "_fig"] += 1
            if not r["ok"]:
                c[cl + "_err"] += 1
                if r["fig"]:
                    c[cl + "_err_fig"] += 1
                if not r["lidos"]:
                    c[cl + "_err_sumiu"] += 1
                for o, mk in marcas.items():
                    if r["lidos"] & mk:
                        c[cl + "_peg_" + o] += 1
    print(rot, dict(sorted(c.items())))
    return c


print("\n=== 2. Discordância por token, por livro (figurina protegida, como na spec)")
tot = Counter()
for livro in ("seirawan", "aagaard-calculation", "nunn-rook-endings", "yusupov-evolution-1", "dvoretsky"):
    bloco([u for u in TODAS if u["livro"] == livro], livro)
bloco(U, "4 livros com figurinas")

print("\n=== 3. Fila × discordância por token, Seirawan (perita-xv)")
Pv = json.load(open(S + "perita-xv.json", encoding="utf-8"))


def alinhar_puro(p, t):
    n, m = len(p), len(t)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j - 1] + (p[i - 1] != t[j - 1]), d[i - 1][j] + 1, d[i][j - 1] + 1)
    i, j, k = n, m, 0
    while i or j:
        k += 1
        if i and j and d[i][j] == d[i - 1][j - 1] + (p[i - 1] != t[j - 1]):
            i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            i -= 1
        else:
            j -= 1
    return k


pos = 0
por_pagina = defaultdict(Counter)
c = Counter()
filas_tot = 0
for ln, u in zip(Pv["linhas"], X):
    p, t = ln["lida"], ln["verdade"]
    k = alinhar_puro(p, t)
    regs = Pv["registros"][pos:pos + k]
    pos += k
    fila_p, q = [None] * len(p), 0
    for r in regs:
        if r["op"] != "falta":
            fila_p[q] = r["fila"]
            q += 1
    assert q == len(p)
    # tokens lidos com fila, no texto cru
    tp = tokens(p)
    tk_fila = set()
    for n, (s, e, _) in enumerate(tp):
        if any(fila_p[z] for z in range(s, e)):
            tk_fila.add(n)
    a = dict(u)
    a["programa"] = p
    a["verdade"] = t
    sai, tp2, marcas, p2, t2 = analisar(a)
    if p2 != p:
        # limpar mudou o espaço: refaz o índice por token
        tk_fila = set()
        q = 0
        for n, (s, e, tk) in enumerate(tp2):
            z = p.find(tk, q)
            if z >= 0 and any(fila_p[y] for y in range(z, z + len(tk))):
                tk_fila.add(n)
            q = max(q, z + len(tk)) if z >= 0 else q
    c["lidos"] += len(tp2)
    c["m_fila"] += len(tk_fila)
    c["m_pp"] += len(marcas["paddle"])
    c["m_t"] += len(marcas["tesseract"])
    c["m_uniao_pp_t"] += len(marcas["paddle"] | marcas["tesseract"])
    por_pagina[u["pagina"]]["lidos"] += len(tp2)
    for r in sai:
        cl = "lance" if r["lance"] else "outro"
        pg = por_pagina[u["pagina"]]
        c[cl] += 1
        pg[cl] += 1
        if not r["ok"]:
            c[cl + "_err"] += 1
            pg[cl + "_err"] += 1
            f = bool(r["lidos"] & tk_fila)
            d = bool(r["lidos"] & marcas["paddle"])
            e = bool(r["lidos"] & marcas["tesseract"])
            c[cl + "_fila"] += f
            c[cl + "_pp"] += d
            c[cl + "_t"] += e
            c[cl + "_fila_ou_pp"] += f or d
            c[cl + "_fila_ou_t"] += f or e
            c[cl + "_nada_fila_t"] += not (f or e)
            c[cl + "_sumiu"] += not r["lidos"]
            pg[cl + "_silente_fila"] += not f
            pg[cl + "_silente_t"] += not e
print(dict(sorted(c.items())))
print("por página (lance, erro, silente pela fila, silente pelo T):")
for k, v in sorted(por_pagina.items()):
    print(k, v["lance"], v["lance_err"], v["lance_silente_fila"], v["lance_silente_t"], "| outro", v["outro"], v["outro_err"], v["outro_silente_fila"], v["outro_silente_t"])
assert pos == len(Pv["registros"])


print("\n=== 4. Erro por página e efeito de desenho")
def por_pag(us, motor):
    out = defaultdict(Counter)
    for u in us:
        o = dict(u); o["programa"] = u.get(motor, "")
        sai, *_ = analisar(o, outros=())
        pg = (u["livro"], u["pagina"])
        p, t = limpar(o["programa"]), limpar(u["verdade"])
        e = sum(a != "ok" for a, _, _ in ops(p, t))
        out[pg]["cerr"] += e
        out[pg]["cn"] += len(t)
        for r in sai:
            if r["lance"]:
                out[pg]["ln"] += 1
                out[pg]["lerr"] += not r["ok"]
            else:
                out[pg]["on"] += 1
                out[pg]["oerr"] += not r["ok"]
    return out


def icc(grupos):
    """Estimador ANOVA do ICC para binários: [(erros, n)]."""
    k = len(grupos)
    N = sum(n for _, n in grupos)
    E = sum(e for e, _ in grupos)
    if k < 2 or N == k:
        return float("nan"), N / max(k, 1)
    m0 = (N - sum(n * n for _, n in grupos) / N) / (k - 1)
    msb = sum(e * e / n for e, n in grupos if n) - E * E / N
    msb /= (k - 1)
    msw = (E - sum(e * e / n for e, n in grupos if n)) / (N - k)
    return (msb - msw) / (msb + (m0 - 1) * msw), m0


tabs = {m: por_pag(TODAS, m) for m in ("programa", "paddle", "tesseract")}
for livro in ("seirawan", "dvoretsky"):
    t = tabs["programa"]
    gr = [(v["lerr"], v["ln"]) for (l, _), v in t.items() if l == livro and v["ln"]]
    r, m0 = icc(gr)
    print(livro, "lance por página (erro,n)", gr, "ICC %.3f m0 %.1f DEFF %.2f" % (r, m0, 1 + (m0 - 1) * max(r, 0)))
    gr = [(v["oerr"], v["on"]) for (l, _), v in t.items() if l == livro]
    r, m0 = icc(gr)
    print(livro, "resto por página", gr, "ICC %.3f m0 %.1f DEFF %.2f" % (r, m0, 1 + (m0 - 1) * max(r, 0)))
    gr = [(v["cerr"], v["cn"]) for (l, _), v in t.items() if l == livro]
    r, m0 = icc(gr)
    print(livro, "caractere por página", gr, "ICC %.4f m0 %.1f DEFF %.2f" % (r, m0, 1 + (m0 - 1) * max(r, 0)))
# entre livros, tokens de lance
t = tabs["programa"]
pl = defaultdict(lambda: [0, 0])
for (l, _), v in t.items():
    pl[l][0] += v["lerr"]; pl[l][1] += v["ln"]
print("lance por livro (erro,n):", dict(pl))
r, m0 = icc([tuple(v) for v in pl.values()])
print("ICC entre livros %.3f m0 %.1f DEFF %.2f" % (r, m0, 1 + (m0 - 1) * max(r, 0)))
pl2 = {k: v for k, v in t.items()}
gr = [(v["lerr"], v["ln"]) for v in t.values() if v["ln"]]
r, m0 = icc(gr)
print("ICC entre páginas, tudo junto %.3f m0 %.1f DEFF %.2f; páginas %d" % (r, m0, 1 + (m0 - 1) * max(r, 0), len(gr)))


print("\n=== 5. Comparação pareada por página")
def boot(pages, a, b, chave_e, chave_n, B=4000, semente=7):
    rnd = random.Random(semente)
    d = []
    for _ in range(B):
        s = [rnd.choice(pages) for _ in pages]
        na = sum(a[x][chave_n] for x in s)
        ea = sum(a[x][chave_e] for x in s)
        nb = sum(b[x][chave_n] for x in s)
        eb = sum(b[x][chave_e] for x in s)
        d.append(100 * (ea / max(na, 1) - eb / max(nb, 1)))
    d.sort()
    return d[int(.025 * B)], d[int(.975 * B)]


def sinal(pages, a, b, chave_e, chave_n):
    dif = [a[x][chave_e] / max(a[x][chave_n], 1) - b[x][chave_e] / max(b[x][chave_n], 1) for x in pages]
    dif = [x for x in dif if x]
    n = len(dif)
    obs = abs(sum(dif))
    tot = cnt = 0
    for mask in range(2 ** n):
        s = sum((1 if mask >> i & 1 else -1) * dif[i] for i in range(n))
        tot += 1
        cnt += abs(s) >= obs - 1e-12
    return cnt / tot, sum(x > 0 for x in dif), n


P = tabs["programa"]; D = tabs["paddle"]; T = tabs["tesseract"]
paginas = {"seirawan": [k for k in P if k[0] == "seirawan"], "dvoretsky": [k for k in P if k[0] == "dvoretsky"],
           "4 esc. c/ fig": [k for k in P if k[0] not in ("seirawan", "dvoretsky")], "tudo": list(P)}
for nome, pgs in paginas.items():
    for rot, a, b in (("prog-PP", P, D), ("T-PP", T, D), ("prog-T", P, T)):
        for ch, chn in (("cerr", "cn"), ("lerr", "ln"), ("oerr", "on")):
            ea, na = sum(a[x][ch] for x in pgs), sum(a[x][chn] for x in pgs)
            eb, nb = sum(b[x][ch] for x in pgs), sum(b[x][chn] for x in pgs)
            lo, hi = boot(pgs, a, b, ch, chn)
            ps, npos, nn = sinal(pgs, a, b, ch, chn) if len(pgs) <= 17 else (float("nan"), 0, 0)
            print(f"{nome:14s} {rot:8s} {ch:4s} {ea}/{na} vs {eb}/{nb} dif {100*(ea/max(na,1)-eb/max(nb,1)):+.2f} pp  IC95boot [{lo:+.2f},{hi:+.2f}]  flip p={ps:.3f} ({npos}/{nn} pág. a>b)")

print("\n=== 6. Entre livros: razão de CER (t com K-1 gl)")
M = json.load(open("docs/medidas/2026-11-05-motores.json", encoding="utf-8"))["motores"]
livros = ["seirawan", "aagaard-calculation", "nunn-rook-endings", "yusupov-evolution-1", "dvoretsky"]
T975 = {2: 4.303, 3: 3.182, 4: 2.776}
for a, b, campo in (("paddle", "programa", "cer"), ("paddle", "tesseract", "cer"), ("paddle", "programa", "cer_prosa"), ("consenso_ptd", "programa", "cer")):
    r = [math.log(M[l]["motores"][a][campo] / M[l]["motores"][b][campo]) for l in livros]
    m = sum(r) / 5
    s = (sum((x - m) ** 2 for x in r) / 4) ** .5
    print(a, "/", b, campo, "razões", [round(math.exp(x), 2) for x in r], "média geom %.2f IC95 [%.2f, %.2f], dp(log) %.2f" % (math.exp(m), math.exp(m - 2.776 * s / 5 ** .5), math.exp(m + 2.776 * s / 5 ** .5), s))
    # quantos livros para IC95 da razão excluir 1, se a razão verdadeira for a média observada
    if m:
        for K in (5, 10, 20, 30, 50):
            tk = {5: 2.776, 10: 2.262, 20: 2.093, 30: 2.045, 50: 2.01}[K]
            print("   K", K, "semi-largura em razão x%.2f" % math.exp(tk * s / K ** .5), end="")
        print()
print("Limite 95%% da fração de livros que falham, com zero falha em K livros:", {K: round(1 - .05 ** (1 / K), 3) for K in (1, 3, 4, 5, 10, 20, 30, 59)})

print("\n=== 7. P(erro | discordância) por livro: a transferência")
for o in ("tesseract", "paddle"):
    print(o)
    for l in livros + ["livros com figurinas"]:
        d = M[l]["discordancia"][o]
        a, b = d["pegos"] / max(d["marca"], 1), (d["erros"] - d["pegos"]) / max(d["de"] - d["marca"], 1)
        print(f"  {l:24s} P(e|disc)={a:.3f} ({d['pegos']}/{d['marca']}) P(e|concorda)={b:.4f} ({d['erros']-d['pegos']}/{d['de']-d['marca']}) marca {d['fracao']:.3f} base {d['erros']/d['de']:.3f}")

print("\n=== 8. Auditoria do gabarito: programa = gabarito, e os dois motores concordam entre si contra ele (Seirawan)")
cand = []
tp_tot = 0
for u in X:
    p, t = limpar(u["programa"]), limpar(u["verdade"])
    d, e = limpar(u.get("paddle", "")), limpar(u.get("tesseract", ""))
    tt, dd, ee, pp = t.split(), d.split(), e.split(), p.split()
    tp_tot += len(tt)
    # por token, alinhado por sequência de tokens
    for tk in tt:
        pass
    a = ops(d, t) if d else []
    if not d or not e:
        continue
    # posição a posição: onde P=gabarito, e D e E têm o mesmo char diferente
    def mapa(x):
        m = {}
        for op, i, j in ops(x, t):
            if j is not None:
                m[j] = x[i] if i is not None else ""
        return m
    mp, md, me = mapa(p), mapa(d), mapa(e)
    for j, ch in enumerate(t):
        if ch == " ":
            continue
        if mp.get(j) == ch and md.get(j) != ch and md.get(j) == me.get(j):
            s = t.rfind(" ", 0, j) + 1
            f = t.find(" ", j)
            f = len(t) if f < 0 else f
            cand.append((u["pagina"], t[s:f], j - s, ch, md.get(j)))
print("candidatos a erro de gabarito ou a engano comum dos motores:", len(cand), "em", tp_tot, "tokens")
print("por gênero (gabarito->motores):", Counter((c[3], c[4]) for c in cand).most_common(12))
with open(S + "c2_candidatos.txt", "w", encoding="utf-8") as f:
    for c in cand:
        f.write(repr(c) + "\n")
