"""CRAP por função: cc² × (1 − cobertura)³ + cc, com a cobertura do coverage.json.

Uso: python crapper.py <raiz-do-pacote> <coverage.json> [limite]
"""
import ast
import json
import sys
from pathlib import Path

DECISOES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler,
            ast.match_case, ast.comprehension, ast.Assert)


def complexidade(func):
    cc = 1
    pilha = list(ast.iter_child_nodes(func))
    while pilha:
        no = pilha.pop()
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue  # a aninhada conta sozinha
        if isinstance(no, DECISOES):
            cc += 1
            if isinstance(no, ast.comprehension):
                cc += len(no.ifs)
        elif isinstance(no, ast.BoolOp):
            cc += len(no.values) - 1
        pilha.extend(ast.iter_child_nodes(no))
    return cc


def funcoes(arvore):
    def visitar(no, prefixo):
        for filho in ast.iter_child_nodes(no):
            if isinstance(filho, ast.ClassDef):
                yield from visitar(filho, f"{prefixo}{filho.name}.")
            elif isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield f"{prefixo}{filho.name}", filho
                yield from visitar(filho, f"{prefixo}{filho.name}.")
            else:
                yield from visitar(filho, prefixo)
    yield from visitar(arvore, "")


def main():
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    raiz, cobertura = Path(sys.argv[1]), sys.argv[2]
    limite = float(sys.argv[3] if len(sys.argv) > 3 else 10)
    dados = json.loads(Path(cobertura).read_text(encoding="utf-8"))["files"]
    por_arquivo = {Path(k).as_posix(): v for k, v in dados.items()}
    linhas = []
    for arq in sorted(raiz.rglob("*.py")):
        rel = arq.as_posix()
        cob = next((v for k, v in por_arquivo.items() if rel.endswith(k) or k.endswith(rel)), None)
        exec_ = set(cob["executed_lines"]) if cob else set()
        falta = set(cob["missing_lines"]) if cob else set()
        arvore = ast.parse(arq.read_text(encoding="utf-8"))
        for nome, f in funcoes(arvore):
            faixa = range(f.lineno, f.end_lineno + 1)
            e = sum(1 for n in faixa if n in exec_)
            m = sum(1 for n in faixa if n in falta)
            frac = e / (e + m) if e + m else 0.0
            cc = complexidade(f)
            crap = cc * cc * (1 - frac) ** 3 + cc
            linhas.append((crap, cc, frac, f"{rel}:{f.lineno}", nome))
    linhas.sort(reverse=True)
    acima = [linha for linha in linhas if linha[0] >= limite]
    print(f"funções: {len(linhas)}; CRAP >= {limite:g}: {len(acima)}")
    for crap, cc, frac, onde, nome in acima:
        print(f"{crap:8.1f}  cc={cc:3d}  cob={frac:5.0%}  {onde}  {nome}")


if __name__ == "__main__":
    main()
