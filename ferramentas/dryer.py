"""Pares de funções quase iguais pela forma (nomes e literais normalizados).

Uso: python dryer.py <raiz> [rank-minimo] [min-nos] [--aceitos <arquivo>]
O rank é o ratio do difflib sobre a sequência de nós do AST de cada função.

Com `--aceitos`, os pares da lista (uma linha `arq.py funcao <-> arq.py funcao  # motivo`,
os arquivos a partir da pasta que contém a raiz) não contam; sai 1 se há par fora da lista
ou par da lista que não existe mais (a lista fica do tamanho do que se aceitou de fato).
"""
import ast
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

_ACEITO = re.compile(r"^\s*(\S+)\s+(\S+)\s+<->\s+(\S+)\s+(\S+)")


def aceitos(caminho):
    """Os pares aceitos do arquivo, cada um como o conjunto das duas (arquivo, função)."""
    pares = set()
    for linha in Path(caminho).read_text(encoding="utf-8").splitlines():
        achado = _ACEITO.match(linha.split("#", 1)[0])
        if achado:
            a, na, b, nb = achado.groups()
            pares.add(frozenset({(a, na), (b, nb)}))
    return pares


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
    argumentos = sys.argv[1:]
    lista = None
    if "--aceitos" in argumentos:
        i = argumentos.index("--aceitos")
        lista = aceitos(argumentos[i + 1])
        del argumentos[i:i + 2]
    raiz = Path(argumentos[0])
    minimo = float(argumentos[1]) if len(argumentos) > 1 else 0.8
    min_nos = int(argumentos[2]) if len(argumentos) > 2 else 60
    base = raiz.resolve().parent
    fs = []
    for arq in sorted(raiz.rglob("*.py")):
        nome = arq.resolve().relative_to(base).as_posix()
        for no in ast.walk(ast.parse(arq.read_text(encoding="utf-8"))):
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                s = forma(no)
                if len(s) >= min_nos:
                    fs.append((f"{nome}:{no.lineno}", no.name, s,
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
    if lista is None:
        return 0
    achados = {frozenset({(a.rsplit(":", 1)[0], na), (b.rsplit(":", 1)[0], nb)})
               for _r, _l, a, na, b, nb in pares}
    novos, sumidos = achados - lista, lista - achados
    print(f"fora da lista de aceitos: {len(novos)}; aceitos que não existem mais: {len(sumidos)}")
    for par in sorted(map(sorted, novos | sumidos)):
        print(("novo     " if frozenset(par) in novos else "sumiu    ")
              + "  <->  ".join(f"{arq} {func}" for arq, func in par))
    return 1 if novos or sumidos else 0


if __name__ == "__main__":
    sys.exit(main())
