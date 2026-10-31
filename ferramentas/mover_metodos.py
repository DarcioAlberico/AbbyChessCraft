"""Move métodos de uma classe para uma classe colaboradora nova (o corte 3 do Q7).

    python ferramentas/mover_metodos.py ORIGEM CLASSE DESTINO NOVA ATRIBUTO --metodos a,b,c
        [--estado _x,_y] [--renomear _a:a,_b:b] [--aplicar]

- ORIGEM: o arquivo da classe (`abbychess/controlador.py`); CLASSE: o nome dela.
- DESTINO: o módulo novo; NOVA: a classe nova; ATRIBUTO: o nome do colaborador na de origem
  (`self.ATRIBUTO = NOVA(self)`, posto à mão no `__init__`).
- `--metodos`: os que mudam de casa; `--estado`: os atributos que mudam junto (o colaborador
  passa a ser o dono deles); `--renomear`: privados que ficam públicos porque a origem os chama.

No código movido, `self.X` vira `self._p.X` quando X fica na origem; na origem, `self.X` vira
`self.ATRIBUTO.X` quando X muda. O `self` sozinho (passado como argumento) é listado para a
mão. Sem `--aplicar`, só mostra o plano.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys

_SELF = re.compile(r"\bself\.(\w+)")
_SELF_SOLTO = re.compile(r"\bself\b(?!\.)")


def _blocos(fonte: str, classe: str, nomes: set[str]):
    """(início, fim) em linhas (base 0, fim exclusivo) de cada método, com os decoradores e os
    comentários colados acima."""
    linhas = fonte.splitlines(keepends=True)
    arvore = ast.parse(fonte)
    cls = next(n for n in arvore.body if isinstance(n, ast.ClassDef) and n.name == classe)
    blocos = []
    for m in cls.body:
        if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name in nomes:
            inicio = min([m.lineno] + [d.lineno for d in m.decorator_list]) - 1
            while inicio > 0 and linhas[inicio - 1].strip().startswith("#"):
                inicio -= 1
            blocos.append((inicio, m.end_lineno, m.name))
    achados = {b[2] for b in blocos}
    faltam = nomes - achados
    if faltam:
        sys.exit(f"não achei: {sorted(faltam)}")
    return linhas, sorted(blocos)


def _trocar(texto: str, troca) -> str:
    return _SELF.sub(lambda m: troca(m.group(1)) or m.group(0), texto)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("origem")
    ap.add_argument("classe")
    ap.add_argument("destino")
    ap.add_argument("nova")
    ap.add_argument("atributo")
    ap.add_argument("--metodos", required=True)
    ap.add_argument("--estado", default="")
    ap.add_argument("--renomear", default="")
    ap.add_argument("--cabecalho", default="", help="arquivo com o docstring e os imports")
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args(argv)
    metodos = {n for n in a.metodos.split(",") if n}
    estado = {n for n in a.estado.split(",") if n}
    renomear = dict(par.split(":") for par in a.renomear.split(",") if par)
    origem = pathlib.Path(a.origem)
    fonte = origem.read_text(encoding="utf-8")
    linhas, blocos = _blocos(fonte, a.classe, metodos)
    movidos = metodos | estado

    def no_movido(nome):
        if nome in movidos:
            return f"self.{renomear.get(nome, nome)}"
        return f"self._p.{nome}"

    def na_origem(nome):
        if nome in movidos:
            return f"self.{a.atributo}.{renomear.get(nome, nome)}"
        return None

    corpo, soltos = [], []
    tirar = set()
    for inicio, fim, nome in blocos:
        trecho = "".join(linhas[inicio:fim])
        for k, linha in enumerate(linhas[inicio:fim]):
            if _SELF_SOLTO.search(linha.split("#")[0]) and not linha.lstrip().startswith("def "):
                soltos.append(f"{origem}:{inicio + k + 1}: {linha.strip()}")
        trecho = _trocar(trecho, no_movido)
        if nome in renomear:
            trecho = re.sub(rf"\bdef {re.escape(nome)}\b", f"def {renomear[nome]}", trecho, count=1)
        corpo.append(trecho)
        tirar.update(range(inicio, fim))
    resto = [linha for k, linha in enumerate(linhas) if k not in tirar]
    resto_txt = _trocar("".join(resto), na_origem)
    resto_txt = re.sub(r"\n{4,}", "\n\n\n", resto_txt)
    cabecalho = pathlib.Path(a.cabecalho).read_text(encoding="utf-8") if a.cabecalho else ""
    novo = (cabecalho + f"\n\nclass {a.nova}:\n    def __init__(self, p) -> None:\n"
            f"        self._p = p\n\n" + "\n".join(corpo))
    print(f"{len(blocos)} métodos, {sum(f - i for i, f, _ in blocos)} linhas; "
          f"origem {len(linhas)} -> {resto_txt.count(chr(10))} linhas")
    for s in soltos:
        print("self solto:", s)
    if a.aplicar:
        origem.write_text(resto_txt, encoding="utf-8", newline="\n")
        pathlib.Path(a.destino).write_text(novo, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
