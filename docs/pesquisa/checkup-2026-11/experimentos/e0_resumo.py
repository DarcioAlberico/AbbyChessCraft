"""E0 por página: troca + falta sobre a verdade, sem contar sobras (o core traz linhas não verificadas)."""
import json
import re
import sys
from pathlib import Path

import importlib.util

AQUI = Path(__file__).parent
sys.stdout.reconfigure(encoding="utf-8")
sys.argv = ["x", str(AQUI / "motores2.json")]
fonte = (AQUI / "motores2_resumo.py").read_text(encoding="utf-8")
ns = {}
exec(fonte[:fonte.index("grupos = defaultdict")], ns)
ops = ns["ops"]


def norm(s):
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"(\w)[-—–] (\w)", r"\1\2", s)
    return s.strip()


def medir(p, t):
    e = {"troca": 0, "falta": 0, "sobra": 0, "ok": 0}
    for op, _, _ in ops(p, t):
        e[op] += 1
    return e


E0 = json.loads((AQUI / "e0.json").read_text(encoding="utf-8"))
X = json.loads((AQUI / "motores-xv.json").read_text(encoding="utf-8"))
tot = {m: {"troca": 0, "falta": 0, "sobra": 0, "ok": 0, "n": 0} for m in ("core", "programa", "tesseract", "easyocr")}
for pg in E0:
    i = pg["pagina"]
    linhas = [x for x in X if x["pagina"] == i]
    verdade = norm(" ".join(pg["verdade"]))
    textos = {"core": pg["core"]}
    for m in ("programa", "tesseract", "easyocr"):
        textos[m] = " ".join(x[m] for x in linhas)
    for m, t in textos.items():
        r = medir(norm(t), verdade)
        for k in r:
            tot[m][k] += r[k]
        tot[m]["n"] += len(verdade)
    print(i, "core s", pg["segundos"], "len core", len(pg["core"]), "len verdade", len(verdade))
for m, r in tot.items():
    print(f"{m:10s} troca {r['troca']:4d} falta {r['falta']:4d} sobra {r['sobra']:4d} | (troca+falta)/n = {(r['troca']+r['falta'])/r['n']:.4f}")
print(E0[1]["core"][:400])
