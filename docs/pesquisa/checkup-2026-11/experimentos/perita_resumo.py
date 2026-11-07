"""Resumo da perícia: CER por classe, por motor, erro silencioso, calibração e curva da fila."""
import json
import sys
import importlib.util
from collections import Counter, defaultdict
from pathlib import Path

ALVO = Path(sys.argv[1])
dados = json.loads(ALVO.read_text(encoding="utf-8"))
R = dados["registros"]
FIG = set("♔♕♖♗♘♙♚♛♜♝♞♟")


def classe(c):
    if c == " ":
        return "espaco"
    if c in FIG:
        return "figurina"
    if c.isdigit():
        return "digito"
    if c.isalpha():
        return "letra"
    if c in ".,;:!?-–—()[]'\"“”‘’":
        return "pontuacao"
    return "simbolo"


erros = [r for r in R if r["op"] != "ok"]
base = sum(1 for r in R if r["op"] != "sobra")
print(f"linhas {len(dados['linhas'])}  chars verdade {base}  erros {len(erros)}  CER {len(erros)/base:.4f}")
print("ops", Counter(r["op"] for r in erros))
print("linhas perfeitas", sum(l["lida"] == l["verdade"] for l in dados["linhas"]), "de", len(dados["linhas"]))
print("linhas não achadas", sum(not l["lida"] for l in dados["linhas"]))

print("\n-- por classe do caractere da verdade (troca+falta / total)")
tot, err = Counter(), Counter()
for r in R:
    if r["t"]:
        tot[classe(r["t"])] += 1
        if r["op"] != "ok":
            err[classe(r["t"])] += 1
for c in tot:
    print(f"  {c:10s} {tot[c]:6d} erros {err[c]:5d}  {err[c]/tot[c]:.4f}")
print("  sobras (char inventado):", Counter(classe(r["p"]) for r in R if r["op"] == "sobra"))

print("\n-- lance x prosa")
t2, e2 = Counter(), Counter()
for r in R:
    if r["t"]:
        k = "lance" if r["lance"] else "prosa"
        t2[k] += 1
        e2[k] += r["op"] != "ok"
for k in t2:
    print(f"  {k}: {t2[k]} erros {e2[k]} CER {e2[k]/t2[k]:.4f}")

print("\n-- por motor (box lido alinhado)")
pm = defaultdict(lambda: [0, 0])
for r in R:
    if r["op"] in ("ok", "troca", "sobra") and r["p"].strip():
        f = r["fonte"] or "sem-box"
        pm[f][0] += 1
        pm[f][1] += r["op"] != "ok"
for f, (n, e) in sorted(pm.items(), key=lambda x: -x[1][0]):
    print(f"  {f:16s} chars {n:6d} erros {e:5d}  {e/n:.4f}  fatia dos erros {e/max(1,sum(v[1] for v in pm.values())):.2%}")

print("\n-- erro silencioso (char lido errado cujo box a fila NÃO pediu)")
vis = [r for r in R if r["op"] in ("troca", "sobra") and r["p"].strip() and r["fila"] is not None]
print(f"  lidos errados com box: {len(vis)}  na fila: {sum(r['fila'] for r in vis)}  silenciosos: {sum(not r['fila'] for r in vis)}")
ml = [r for r in vis if r["lance"]]
print(f"  em lance: {len(ml)}  silenciosos {sum(not r['fila'] for r in ml)}")
falta = [r for r in R if r["op"] == "falta" and r["t"].strip()]
print(f"  faltas (char não lido; a fila não tem como ver): {len(falta)}  em lance {sum(1 for r in falta if r['lance'])}")
print(f"  espaços errados: {sum(1 for r in erros if (r['t']==' ' or r['p']==' '))}")

caixas = {}
for r in R:
    if r["box"] is not None:
        chave = (r["pag"], r["box"])
        c = caixas.setdefault(chave, {"fila": r["fila"], "erro": False, "fonte": r["fonte"], "conf": r["conf"]})
        c["erro"] = c["erro"] or r["op"] != "ok"
n = len(caixas)
f = sum(c["fila"] for c in caixas.values())
e = sum(c["erro"] for c in caixas.values())
fe = sum(c["fila"] and c["erro"] for c in caixas.values())
print(f"\n-- fila: boxes {n}  na fila {f} ({f/n:.1%})  com erro {e} ({e/n:.2%})  fila&erro {fe}")
print(f"  precisão da fila {fe/max(f,1):.2%}  revocação {fe/max(e,1):.2%}")

print("\n-- calibração por motor (conf → acerto)")
bins = [0, .5, .7, .8, .9, .95, .99, 1.0001]
for fonte in sorted({c["fonte"] for c in caixas.values() if c["fonte"]}):
    cs = [c for c in caixas.values() if c["fonte"] == fonte and c["conf"] is not None]
    linha, ece = [], 0.0
    for a, b in zip(bins, bins[1:]):
        x = [c for c in cs if a <= c["conf"] < b]
        if x:
            ac = 1 - sum(c["erro"] for c in x) / len(x)
            med = sum(c["conf"] for c in x) / len(x)
            ece += len(x) / len(cs) * abs(ac - med)
            linha.append(f"[{a:.2f},{b:.2f}) n={len(x)} conf={med:.2f} acerto={ac:.3f}")
    print(f"  {fonte} (n={len(cs)}, ECE={ece:.3f})")
    for s in linha:
        print("     ", s)

print("\n-- curva: fila só por confiança < x (boxes), o que pegaria")
cs = [c for c in caixas.values() if c["conf"] is not None]
for x in (.3, .5, .7, .8, .9, .95, .99, .999):
    sel = [c for c in cs if c["conf"] < x]
    ee = sum(c["erro"] for c in sel)
    print(f"  x={x:<5} fila {len(sel):6d} ({len(sel)/len(cs):.1%})  erros pegos {ee}/{sum(c['erro'] for c in cs)} ({ee/max(1,sum(c['erro'] for c in cs)):.1%})")

print("\n-- confusões mais frequentes (lido → verdade)")
conf = Counter((r["p"], r["t"]) for r in erros if r["op"] == "troca")
print("  ", [f"{a}→{b}:{n}" for (a, b), n in conf.most_common(30)])
print("  faltas:", [f"{a!r}:{n}" for a, n in Counter(r["t"] for r in erros if r["op"] == "falta").most_common(15)])
print("  sobras:", [f"{a!r}:{n}" for a, n in Counter(r["p"] for r in erros if r["op"] == "sobra").most_common(15)])

print("\n-- exemplos de linhas de lance com erro")
vistos = 0
for l in dados["linhas"]:
    if l["lida"] != l["verdade"] and any(ch.isdigit() for ch in l["verdade"]):
        print("  V:", l["verdade"][:100])
        print("  L:", l["lida"][:100])
        vistos += 1
        if vistos >= 12:
            break
