"""A tabela final dos motores: Seirawan (linhas verificadas) e os livros com figurinas (referência
humana ou camada digital). Grava os números, sem texto de livro, em docs/medidas.

    python final_resumo.py <saida.json>
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

AQUI = Path(__file__).parent
sys.stdout.reconfigure(encoding="utf-8")
saida_json = Path(sys.argv[1])
sys.argv = ["x", str(AQUI / "motores2.json")]
f = (AQUI / "motores2_resumo.py").read_text(encoding="utf-8")
ns = {}
exec(f[:f.index("grupos = defaultdict")], ns)
ops, limpar, classe, marca, FIG = ns["ops"], ns["limpar"], ns["classe"], ns["marca"], ns["FIG"]

X = json.loads((AQUI / "motores-xv-p.json").read_text(encoding="utf-8"))
U = json.loads((AQUI / "motores3.json").read_text(encoding="utf-8"))
for x in X:
    x["livro"], x["tipo"] = "seirawan", "escaneado"
TODAS = X + U
SAN = re.compile(r"^(\d+\.{1,3})?([♔♕♖♗♘KQRBNDTCFP]?[a-h]?[1-8]?x?[a-h][1-8](=[♕♖♗♘QRBNDTCF])?|O-O(-O)?|0-0(-0)?)[+#]*[!?]*[.,;)]*$")


def consenso(p, outros):
    """Onde todos os outros concordam entre si e discordam do programa, vale o deles; figurina do
    programa e token com figurina não mudam (os outros não têm a classe)."""
    outros = [o for o in outros if o]
    if not p or len(outros) < 2:
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
    # posições em token com figurina ficam com o programa
    prot = [False] * len(p)
    for m in re.finditer(r"\S+", p):
        if any(c in FIG for c in m.group()):
            for k in range(m.start(), m.end()):
                prot[k] = True
    s = []
    for i in range(len(p) + 1):
        ii = [v[1].get(i, "") for v in votos]
        if ii[0] and all(x == ii[0] for x in ii) and not (i < len(p) and prot[i]):
            s.append(ii[0])
        if i == len(p):
            break
        vs = [v[0].get(i, p[i]) for v in votos]
        s.append(p[i] if prot[i] else (vs[0] if all(x == vs[0] for x in vs) else p[i]))
    return "".join(s)


def texto(u, m):
    if m == "consenso_ptd":
        return consenso(limpar(u["programa"]), [limpar(u["tesseract"]), limpar(u.get("paddle", ""))])
    if m == "consenso_pte":
        return consenso(limpar(u["programa"]), [limpar(u["tesseract"]), limpar(u["easyocr"])])
    return limpar(u.get(m, ""))


def medir(us, m):
    tot, err = Counter(), Counter()
    e = n = sob = el = tl = perf = tok = toke = tokf = 0
    for u in us:
        t, p = limpar(u["verdade"]), texto(u, m)
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
            sob += op == "sobra"
        n += len(t)
        lidos = p.split()
        for tk in t.split():
            if SAN.match(tk):
                tok += 1
                if tk not in lidos:
                    toke += 1
        # lido em forma de lance que não está na verdade: o erro que a forma não acusa
        vt = t.split()
        for tk in lidos:
            if SAN.match(tk) and tk not in vt:
                tokf += 1
    return {"cer": round(e / n, 4), "n": n, "erros": e, "sobras": sob,
            "cer_prosa": round((e - el - sob) / max(n - tl, 1), 4), "cer_lance": round(el / max(tl, 1), 4),
            "classes": {c: [err[c], tot[c]] for c in tot}, "unidades_perfeitas": perf,
            "tokens_lance": tok, "tokens_lance_errados": toke, "lidos_forma_de_lance_falsos": tokf}


def discordancia(us, outro):
    n = sel = er = peg = 0
    for u in us:
        p, t, o = limpar(u["programa"]), limpar(u["verdade"]), limpar(u.get(outro, ""))
        if not p or not o:
            continue
        # token com figurina não conta: os outros motores não têm a classe e sempre discordam
        prot = [False] * len(p)
        for m in re.finditer(r"\S+", p):
            if any(c in FIG for c in m.group()):
                for k in range(m.start(), m.end()):
                    prot[k] = True
        errado = {a for op, a, _ in ops(p, t) if op in ("troca", "sobra")}
        dif = {a for op, a, _ in ops(p, o) if op in ("troca", "sobra") and not prot[a]}
        n += len(p)
        sel += len(dif)
        er += len(errado)
        peg += len(errado & dif)
    return {"marca": sel, "de": n, "fracao": round(sel / max(n, 1), 4), "erros": er, "pegos": peg,
            "revocacao": round(peg / max(er, 1), 4), "precisao": round(peg / max(sel, 1), 4)}


grupos = defaultdict(list)
for u in TODAS:
    grupos[u["livro"]].append(u)
grupos["livros com figurinas"] = U
res = {}
for nome, us in grupos.items():
    res[nome] = {"motores": {m: medir(us, m) for m in ("programa", "tesseract", "easyocr", "paddle", "consenso_pte", "consenso_ptd")},
                 "discordancia": {o: discordancia(us, o) for o in ("tesseract", "easyocr", "paddle")},
                 "unidades": len(us), "tipo": us[0]["tipo"]}
    print(f"\n=== {nome} ({len(us)} unidades, {res[nome]['motores']['programa']['n']} chars)")
    for m, r in res[nome]["motores"].items():
        c = r["classes"]
        print(f"  {m:13s} CER {r['cer']:.4f} prosa {r['cer_prosa']:.4f} lance {r['cer_lance']:.4f} fig {c.get('figurina',[0,0])[0]}/{c.get('figurina',[0,0])[1]} símb {c.get('simbolo',[0,0])[0]}/{c.get('simbolo',[0,0])[1]} tok.lance err {r['tokens_lance_errados']}/{r['tokens_lance']} falso-forma {r['lidos_forma_de_lance_falsos']} perf {r['unidades_perfeitas']}")
    for o, r in res[nome]["discordancia"].items():
        print(f"  P×{o:10s} marca {r['fracao']:.1%} pega {r['revocacao']:.1%} precisão {r['precisao']:.1%}")
res["_nota"] = ("Sem padrões do livro nem treino; figurinas contra os outros motores protegidas. "
                "Escaneados com referência de página têm ordem e cabeçalhos do programa; "
                "o Dvoretsky usa a camada digital renderizada a 300 dpi.")
saida_json.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
