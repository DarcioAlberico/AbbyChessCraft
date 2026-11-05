"""O efeito do consenso caractere a caractere: quantos erros tira, quantos cria, e o custo em tempo."""
import json
import sys
from pathlib import Path

AQUI = Path(__file__).parent
sys.stdout.reconfigure(encoding="utf-8")
sys.argv = ["x", str(AQUI / "saida-descartada.json")]
f = (AQUI / "final_resumo.py").read_text(encoding="utf-8")
ns = {"__file__": str(AQUI / "final_resumo.py")}
exec(f[:f.rindex("grupos = defaultdict")], ns)
ops, limpar, consenso, TODAS = ns["ops"], ns["limpar"], ns["consenso"], ns["TODAS"]

por_livro = {}
for u in TODAS:
    p, t = limpar(u["programa"]), limpar(u["verdade"])
    c = consenso(p, [limpar(u["tesseract"]), limpar(u.get("paddle", ""))])
    if c == p:
        continue
    # as posições do programa certas e erradas, e o que o consenso fez em cada uma
    certo = {a for op, a, _ in ops(p, t) if op == "ok"}
    r = por_livro.setdefault(u["livro"], {"mudou": 0, "tirou": 0, "criou": 0})
    e_antes = sum(op != "ok" for op, _, _ in ops(p, t))
    e_depois = sum(op != "ok" for op, _, _ in ops(c, t))
    mud = [(op, a, b) for op, a, b in ops(p, c) if op != "ok"]
    r["mudou"] += len(mud)
    for op, a, b in mud:
        if a is not None and a in certo:
            r["criou"] += 1
    r["tirou"] += e_antes - e_depois + 0
    r.setdefault("erros_antes", 0)
    r.setdefault("erros_depois", 0)
    r["erros_antes"] += e_antes
    r["erros_depois"] += e_depois
print(json.dumps(por_livro, ensure_ascii=False, indent=1))
(AQUI / "consenso-efeito.json").write_text(json.dumps(por_livro, ensure_ascii=False, indent=1), encoding="utf-8")
