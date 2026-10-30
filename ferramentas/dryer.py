"""Pares de funções quase iguais pela forma (nomes e literais normalizados).

Uso: python dryer.py <raiz> [rank-minimo] [min-nos]
O rank é o ratio do difflib sobre a sequência de nós do AST de cada função.
"""
import ast
import sys
from difflib import SequenceMatcher
from pathlib import Path


def forma(func):
    seq = []
    for no in ast.walk(func):
        t = type(no).__name__
        if isinstance(no, (ast.BinOp, ast.BoolOp, ast.Compare, ast.UnaryOp)):
            op = getattr(no, "op", None) or (no.ops[0] if getattr(no, "ops", None) else None)
            t += type(op).__name__ if op is not None else ""
        elif isinstance(no, ast.Attribute):
            t += "." + no.attr  # atributos dizem muito do que o trecho faz
        seq.append(t)
    return seq


def main():
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    raiz = Path(sys.argv[1])
    minimo = float(sys.argv[2]) if len(sys.argv) > 2 else 0.8
    min_nos = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    fs = []
    for arq in sorted(raiz.rglob("*.py")):
        for no in ast.walk(ast.parse(arq.read_text(encoding="utf-8"))):
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                s = forma(no)
                if len(s) >= min_nos:
                    fs.append((f"{arq.as_posix()}:{no.lineno}", no.name, s,
                               no.end_lineno - no.lineno + 1, (arq, no.lineno, no.end_lineno)))
    fs.sort(key=lambda f: len(f[2]))
    pares = []
    for i, (a, na, sa, la, fa) in enumerate(fs):
        for b, nb, sb, lb, fb in fs[i + 1:]:
            if len(sb) > len(sa) * 1.25:
                break
            if fa[0] == fb[0] and (fa[1] <= fb[1] <= fa[2] or fb[1] <= fa[1] <= fb[2]):
                continue  # a aninhada contra a mãe dela
            m = SequenceMatcher(None, sa, sb, autojunk=False)
            if m.real_quick_ratio() < minimo or m.quick_ratio() < minimo:
                continue
            r = m.ratio()
            if r >= minimo:
                pares.append((r, la + lb, a, na, b, nb))
    pares.sort(key=lambda p: (-p[0], -p[1]))
    print(f"funções com >= {min_nos} nós: {len(fs)}; pares com rank >= {minimo}: {len(pares)}")
    for r, linhas, a, na, b, nb in pares:
        print(f"{r:.2f}  {linhas:4d} linhas  {a} {na}  <->  {b} {nb}")


if __name__ == "__main__":
    main()
