import re, sys, io, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
R = Path(r"C:\Python-Chess2\AbbyChessCraft-coordenadas")
rel = (R/"docs/pesquisa/checkup-2026-11.md").read_text(encoding="utf-8")
spec = (R/"docs/SPEC-pagina-perfeita.md").read_text(encoding="utf-8")
road = (R/"plans/roadmap-pagina-perfeita.md").read_text(encoding="utf-8")
docs = {"REL": rel, "SPEC": spec, "ROAD": road}

# 1. CAs definidos: "**CA-..." na spec
def_ca = set(re.findall(r"\*\*CA-([A-Z]\d*[a-z]?(?:\.\d+[ab]?)?)[\.:]?\*?\*?", spec))
def_lin = {}
for i, l in enumerate(spec.splitlines(), 1):
    for m in re.finditer(r"\*\*CA-([A-Z]\d*[a-z]?(?:\.\d+[ab]?)?)[\.:]", l):
        def_lin.setdefault(m.group(1), []).append(i)
print("CA definidos:", len(def_lin))
dup = {k: v for k, v in def_lin.items() if len(v) > 1}
print("CA definidos em duplicata:", dup)

# 2. CAs citados
cit = {}
for nome, t in docs.items():
    for i, l in enumerate(t.splitlines(), 1):
        for m in re.finditer(r"CA-([A-Z]\d*[a-z]?(?:\.\d+[ab]?)?(?:\.\*)?)", l):
            cit.setdefault(m.group(1), []).append((nome, i))
fant = {}
for c, onde in cit.items():
    if c.endswith(".*"):
        pre = c[:-1]
        if not any(k.startswith(pre) for k in def_lin):
            fant[c] = onde
    elif c not in def_lin:
        fant[c] = onde
print("CA citados sem definição nesta spec:", json.dumps(fant, ensure_ascii=False))

# 3. todo CA tem passo
ca_road = set()
for l in road.splitlines():
    pass
cit_road = [c for c, o in cit.items() if any(n == "ROAD" for n, _ in o)]
exp = set()
for c in cit_road:
    if c.endswith(".*"):
        exp |= {k for k in def_lin if k.startswith(c[:-1])}
    else:
        exp.add(c)
# faixas "CA-R1.1 a CA-R1.5"
for m in re.finditer(r"CA-([A-Z]\d*)\.(\d+) a CA-\1\.(\d+)", road):
    for n in range(int(m.group(2)), int(m.group(3)) + 1):
        exp.add(f"{m.group(1)}.{n}")
orf = sorted(set(def_lin) - exp)
print("CA da spec sem citação no roadmap:", orf)

# citados no roadmap em mais de um passo
sec = None
por_passo = {}
for l in road.splitlines():
    if l.startswith("## "):
        sec = l[3:]
    for m in re.finditer(r"CA-([A-Z]\d*[a-z]?(?:\.\d+[ab]?)?(?:\.\*)?)", l):
        por_passo.setdefault(m.group(1), set()).add(sec)
print("CA citados em >1 seção do roadmap:", {k: sorted(v) for k, v in por_passo.items() if len(v) > 1})

# 4. Ids R L F X D C E A U citados x definidos
defs = set()
for l in spec.splitlines():
    m = re.match(r"###\s+\d+\.\d+\s+([RLFX]-\d+[a-z]?)", l)
    if m: defs.add(m.group(1))
    m = re.match(r"\|\s*([LDCEAU]-\d+[a-z]?)\s*\|", l)
    if m: defs.add(m.group(1))
print("Ids definidos:", sorted(defs))
cits = {}
for nome, t in docs.items():
    for i, l in enumerate(t.splitlines(), 1):
        for m in re.finditer(r"(?<![A-Za-z0-9\-])([RLFXDCEAU])-(\d+)([a-z]?)(?![0-9])", l):
            cits.setdefault(m.group(1)+"-"+m.group(2)+m.group(3), []).append((nome, i))
print("Ids citados sem definição:", {k: v[:6] for k, v in cits.items() if k not in defs})
print("Ids definidos e sem menção no roadmap:", sorted(d for d in defs if not any(n == "ROAD" for n, _ in cits.get(d, []))))

# Dec
d_def = set(re.findall(r"\*\*Dec-(\d+)", spec))
print("Dec definidos (em negrito):", sorted(d_def))
print("Dec citados:", {k: sorted({n for n, _ in v}) for k, v in {m: [(n, 0) for n, t in docs.items() if f"Dec-{m}" in t] for m in "12345678 9".replace(" ", "")}.items() if v})

# PP citados x passos
passos = re.findall(r"^## Passo (\S+)", road, re.M)
print("Passos:", passos)
pp = {}
for nome, t in docs.items():
    for i, l in enumerate(t.splitlines(), 1):
        for m in re.finditer(r"\bPP\d+[a-z]?|\bPPL\b|\bPPT\b", l):
            pp.setdefault(m.group(0), []).append((nome, i))
print("PP citados sem passo:", {k: v for k, v in pp.items() if k not in passos})

# campos por passo
blocos = re.split(r"(?m)^## ", road)
campos = ["Contexto", "Fazer", "CA", "Risco", "Pronto quando", "Custo", "Carga"]
for b in blocos:
    if not b.startswith("Passo"):
        continue
    t = b.split("\n")[0]
    falta = [c for c in campos if not re.search(r"\*\*" + c, b)]
    print(t[:50], "| falta:", falta)

# títulos
print("Títulos spec:")
for l in spec.splitlines():
    if re.match(r"#{1,3} ", l): print("  ", l)
print("Títulos road:")
for l in road.splitlines():
    if re.match(r"#{1,3} ", l): print("  ", l)
print("Títulos rel:")
for l in rel.splitlines():
    if re.match(r"#{1,3} ", l): print("  ", l)

# frases a caçar
cacar = ["barata", "barato", "Tesseract padrão", "com evidência", "sem evidência", "hipoteses/", "servidor_de_opiniao", "marca fraca", "G2-d", "X-5", "L-7", "F7", "Alt+S", "medir_sincronia", "Validacao", "`Lance`", "fortes", "fila de hoje", "Fila de hoje", "98,4", "exploratório", "crítica", "critica", "quinto", "5 × 4", "2.000", "1.600", "Prova", "você", "Você", "L-6f", "U-12", "U-15", "CA-L8.2", "PP2 ", "conferido", "18 páginas", "60 min", "22 a 60", "L-7.1"]
for c in cacar:
    for nome, t in docs.items():
        hits = [i for i, l in enumerate(t.splitlines(), 1) if c in l]
        if hits:
            print(f"{c!r:22} {nome}: {hits[:30]}")
# palavras e tamanho
for nome, t in docs.items():
    print(nome, "palavras", len(t.split()))
