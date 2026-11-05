"""Contas da crítica 2, parte 2. Só contagens na saída."""
import json, math, random, re, sys, unicodedata
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")
import sys
S = sys.argv[1].rstrip("/\\") + "/"  # a pasta com motores3.json, motores-xv-p.json e perita-xv.json
src = open(__file__.replace("por_token_b", "por_token_a"), encoding="utf-8").read()
ns = {}
exec(src[:src.index('print("=== 1.')], ns)
ops, limpar, tokens, e_lance, FIG, TODAS, U, X = (ns[k] for k in ("ops", "limpar", "tokens", "e_lance", "FIG", "TODAS", "U", "X"))
src2 = src[src.index("def analisar"):src.index("def bloco")]
exec(src2, ns)
analisar = ns["analisar"]
M = json.load(open("docs/medidas/2026-11-05-motores.json", encoding="utf-8"))["motores"]
livros = ["seirawan", "aagaard-calculation", "nunn-rook-endings", "yusupov-evolution-1", "dvoretsky"]

print("=== A. Precisão e marcas por token, por classe (a classe do token lido vem do token da verdade alinhado)")
def tabela(us, rot):
    c = Counter()
    for u in us:
        sai, tp, marcas, p, t = analisar(u)
        cl_lido = {}
        err_lido = {}
        for r in sai:
            for k in r["lidos"]:
                # o token lido herda lance se qualquer token da verdade alinhado for lance
                cl_lido[k] = cl_lido.get(k, False) or r["lance"]
                err_lido[k] = err_lido.get(k, False) or (not r["ok"])
        c["lidos"] += len(tp)
        c["sem_par"] += sum(k not in cl_lido for k in range(len(tp)))
        c["lidos_lance"] += sum(bool(v) for v in cl_lido.values())
        c["lidos_fig"] += sum(any(ch in FIG for ch in x[2]) for x in tp)
        for o, mk in marcas.items():
            for k in mk:
                cl = "lance" if cl_lido.get(k) else ("sempar" if k not in cl_lido else "outro")
                c[f"{o}_marca_{cl}"] += 1
                if err_lido.get(k) or k not in cl_lido:
                    c[f"{o}_certa_{cl}"] += 1
    print(rot, dict(sorted(c.items())))
    for o in ("paddle", "tesseract"):
        for cl in ("lance", "outro"):
            a, b = c[f"{o}_certa_{cl}"], c[f"{o}_marca_{cl}"]
            print(f"   {o:10s} {cl:6s} marca {b} ({b/max(c['lidos_lance'] if cl=='lance' else c['lidos']-c['lidos_lance'],1):.1%} da classe) precisão {a}/{b} = {a/max(b,1):.1%}")
for l in livros:
    tabela([u for u in TODAS if u["livro"] == l], l)
tabela(U, "4 com figurinas")

print("\n=== B. Positivos para calibrar (erros por classe de caractere, programa, no que seria o ajuste)")
for l in livros:
    cl = M[l]["motores"]["programa"]["classes"]
    print(l, {k: v for k, v in cl.items() if k in ("simbolo", "figurina", "digito", "espaco", "pontuacao", "letra")})

print("\n=== C. Limites e poder")
def bin_cdf(k, n, p):
    # P(X<=k)
    s, t = 0.0, (1 - p) ** n
    for i in range(k + 1):
        s += t
        t = t * (n - i) / (i + 1) * p / (1 - p) if p < 1 else 0
    return s
def cp_sup(k, n, a=.05):
    lo, hi = k / n, 1.0
    for _ in range(80):
        m = (lo + hi) / 2
        if bin_cdf(k, n, m) > a:
            lo = m
        else:
            hi = m
    return hi
def cp_bi(k, n):
    def inf():
        if k == 0: return 0.0
        lo, hi = 0.0, k / n
        for _ in range(80):
            m = (lo + hi) / 2
            if 1 - bin_cdf(k - 1, n, m) < .025: lo = m
            else: hi = m
        return lo
    lo_ = inf()
    return lo_, cp_sup(k, n, .025)
print("P(zero erro em 600) por taxa real:", {p: round((1 - p) ** 600, 3) for p in (.0005, .001, .002, .003, .005, .01)})
print("N para limite unilateral 95% <= 0,5%, com c erros:")
for c in range(0, 6):
    n = c + 1
    while cp_sup(c, n) > .005:
        n += 1 if n < 200 else 5
    print("  c", c, "N", n, "P(passa) p=.1%%: %.2f  .2%%: %.2f  .3%%: %.2f  .5%%: %.2f" % tuple(bin_cdf(c, n, q) for q in (.001, .002, .003, .005)))
print("com N=2600 (40 páginas × 65):")
for c in range(0, 8):
    print("  c", c, "sup %.3f%%" % (100 * cp_sup(c, 2600)), "P(passa) p=.1%%: %.2f .2%%: %.2f .3%%: %.2f .5%%: %.2f" % tuple(bin_cdf(c, 2600, q) for q in (.001, .002, .003, .005)))
def beta_bin_passa(p, rho, paginas, m, c, B=20000, sem=3):
    rnd = random.Random(sem)
    if rho <= 0:
        return bin_cdf(c, paginas * m, p)
    th = (1 - rho) / rho
    a, b = p * th, (1 - p) * th
    ok = 0
    for _ in range(B):
        x = 0
        for _ in range(paginas):
            q = rnd.betavariate(a, b)
            # binomial rápida por Poisson para taxas raras
            lam = q * m
            L, k, t = math.exp(-lam), 0, 1.0
            while True:
                t *= rnd.random()
                if t <= L:
                    break
                k += 1
            x += k
            if x > c:
                break
        ok += x <= c
    return ok / B
print("P(zero erro) com aglomeração por página, 40 pág × 65, taxa real .2%: rho 0, .05, .2:",
      [round(beta_bin_passa(.002, r, 40, 65, 0), 3) for r in (0, .05, .2)])
print("zero erros, N 600, limite com DEFF:")
for deff in (1, 2, 4, 5, 15):
    print("  DEFF", deff, "Nef", 600 / deff, "limite %.2f%%" % (100 * (1 - .05 ** (1 / (600 / deff)))))
print("395 sem erro, IID: %.2f%%" % (100 * (1 - .05 ** (1 / 395))))
print("olhadas sem efeito, alfa 5%:", {k: round(1 - .95 ** k, 2) for k in (5, 10, 15, 20, 30)})
print("Consenso: certo→errado: IC por livro")
for nome, k, n in (("seirawan", 5, 298), ("nunn", 14, 56), ("todos", 22, 819), ("todos liquido", 31, 819), ("yusupov", 3, 182), ("aagaard", 0, 205), ("dvoretsky", 0, 78)):
    print("  ", nome, k, n, "%.1f%%" % (100 * k / n), "IC95 [%.1f, %.1f]" % tuple(100 * x for x in cp_bi(k, n)))
print("  sem o Nunn", 8, 763, "%.1f%%" % (100 * 8 / 763), "IC95 [%.1f, %.1f]" % tuple(100 * x for x in cp_bi(8, 763)))
print("N de edições p/ 0,5% com zero:", math.ceil(math.log(.05) / math.log(.995)))
print("Lance Seirawan silente por token, IC CP: fila 8/137, T 9/137, PP 12/137, união 3/137:", [tuple(round(100 * x, 1) for x in cp_bi(k, 137)) for k in (8, 9, 12, 3)])
print("2/64 linhas", tuple(round(100 * x, 1) for x in cp_bi(2, 64)))
print("lado 2/5", tuple(round(100 * x, 1) for x in cp_bi(2, 5)), "FEN 7/7", tuple(round(100 * x, 1) for x in cp_bi(7, 7)))
print("fig 9/498", tuple(round(100 * x, 1) for x in cp_bi(9, 498)))
print("cobertura: 20/199 marcados", )
print("isotônica: conservar: recall em eval: 25 erros, 80%:", tuple(round(100 * x, 1) for x in cp_bi(20, 25)))
print("injeção: 16/20", tuple(round(100 * x, 1) for x in cp_bi(16, 20)), "8/10", tuple(round(100 * x, 1) for x in cp_bi(8, 10)), "38/40 ", tuple(round(100 * x, 1) for x in cp_bi(38, 40)))

print("\n=== D. Tipografia: quantos caracteres de cada família na verdade, e o efeito da dobra no CER")
FAM = {"hifen-": "-", "en–": "–", "em—": "—", "menos−": "−", "aspas'": "'", "aspas’": "’", "aspas\"": '"', "aspas“": "“", "aspas”": "”", "…": "…", "zero": "0", "O": "O"}
for l in livros:
    c = Counter()
    nfd = 0
    for u in (u for u in TODAS if u["livro"] == l):
        t = u["verdade"]
        nfd += unicodedata.normalize("NFC", t) != t
        for k, v in FAM.items():
            if k in ("zero", "O"):
                continue
            c[k] += t.count(v)
        c["..."] += t.count("...")
        c["O-O"] += t.count("O-O")
        c["0-0"] += t.count("0-0")
        c["+-"] += t.count("+-") + t.count("+−")
        c["±"] += t.count("±")
    print(l, "linhas não NFC", nfd, dict(c))
def dobra(s):
    s = unicodedata.normalize("NFKC", s)
    for a, b in (("–", "-"), ("—", "-"), ("−", "-"), ("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("…", "...")):
        s = s.replace(a, b)
    return s
for l in livros:
    us = [u for u in TODAS if u["livro"] == l]
    r = {}
    for m in ("programa", "paddle", "tesseract"):
        e0 = e1 = n = 0
        for u in us:
            t, p = limpar(u["verdade"]), limpar(u.get(m, ""))
            e0 += sum(a != "ok" for a, _, _ in ops(p, t))
            t2, p2 = dobra(t), dobra(p)
            e1 += sum(a != "ok" for a, _, _ in ops(p2, t2))
            n += len(t)
        r[m] = (round(100 * e0 / n, 2), round(100 * e1 / n, 2))
    print(l, "CER cru → dobrado", r)

print("\n=== E. Ordem: erro de token por sequência × por saco (página como unidade)")
for u in (u for u in U if u["tipo"] == "escaneado"):
    t = limpar(u["verdade"]).split()
    row = {}
    for m in ("programa", "paddle", "tesseract"):
        o = dict(u); o["programa"] = u[m]
        sai, *_ = analisar(o, outros=())
        seq = sum(not r["ok"] for r in sai)
        bag = sum((Counter(t) - Counter(limpar(u[m]).split())).values())
        extra = sum((Counter(limpar(u[m]).split()) - Counter(t)).values())
        row[m] = (seq, bag, extra)
    print(u["livro"], u["pagina"], "tokens", len(t), "(seq, saco-falta, saco-sobra)", row)

print("\n=== F. Candidatos: lance?")
for ln in open(S + "c2_candidatos.txt", encoding="utf-8"):
    c = eval(ln)
    print(c[0], "lance" if e_lance(c[1]) else "outro", "pos", c[2], repr(c[3]), "->", repr(c[4]), "token:", len(c[1]), "chars")
