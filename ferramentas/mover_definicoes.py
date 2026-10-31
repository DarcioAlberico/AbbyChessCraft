"""Move definições de topo de um módulo para um módulo novo (o corte 5 do Q7).

    python ferramentas/mover_definicoes.py ORIGEM DESTINO --nomes a,b,c --cabecalho FILE
        [--chamadores abbychess,tests,ferramentas --alias mt] [--aplicar]

- ORIGEM: o módulo de onde saem (`abbychess/exportar.py`); DESTINO: o módulo novo, que começa
  pelo `--cabecalho` (o docstring e os imports) e recebe as definições na ordem em que estavam.
- `--nomes`: funções, classes e atribuições de topo; cada uma sai com os decoradores e os
  comentários colados acima (o `#:` de uma constante).
- Na ORIGEM, os nomes movidos que ela ainda usa entram num `from abbychess.<destino> import`,
  depois do último `from abbychess`.
- `--chamadores`: nas pastas dadas, `<apelido da origem>.NOME` de um nome movido vira
  `<alias>.NOME`, e o `from abbychess import <destino> as <alias>` entra logo abaixo da linha que
  importa a origem, com o mesmo recuo.

Sem `--aplicar`, só mostra o plano.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys


def _blocos(fonte: str, nomes: set[str]):
    """(início, fim, nome) em linhas (base 0, fim exclusivo) de cada definição."""
    linhas = fonte.splitlines(keepends=True)
    blocos = []
    for no in ast.parse(fonte).body:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            achados = {no.name}
        elif isinstance(no, ast.Assign):
            achados = {t.id for t in no.targets if isinstance(t, ast.Name)}
        elif isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name):
            achados = {no.target.id}
        else:
            continue
        if not achados & nomes:
            continue
        if not achados <= nomes:
            sys.exit(f"atribuição com nomes a mais: {sorted(achados)}")
        inicio = min([no.lineno] + [d.lineno for d in getattr(no, "decorator_list", [])]) - 1
        while inicio > 0 and linhas[inicio - 1].strip().startswith("#"):
            inicio -= 1
        blocos.append((inicio, no.end_lineno, sorted(achados)[0]))
    faltam = nomes - {n for b in blocos for n in [b[2]]} - _nomes_de_atribuicoes(fonte, nomes)
    if faltam:
        sys.exit(f"não achei: {sorted(faltam)}")
    return linhas, sorted(blocos)


def _nomes_de_atribuicoes(fonte: str, nomes: set[str]) -> set[str]:
    achados = set()
    for no in ast.parse(fonte).body:
        if isinstance(no, ast.Assign):
            achados |= {t.id for t in no.targets if isinstance(t, ast.Name)} & nomes
    return achados


def _usados(fonte: str, nomes: set[str]) -> list[str]:
    usados = {n.id for n in ast.walk(ast.parse(fonte)) if isinstance(n, ast.Name)}
    return sorted(usados & nomes)


def _com_import(texto: str, linha_nova: str) -> str:
    linhas = texto.splitlines(keepends=True)
    ultimo = max(k for k, linha in enumerate(linhas) if linha.startswith("from abbychess"))
    while linhas[ultimo].rstrip().endswith(("(", ",")):     # o import partido em linhas
        ultimo += 1
    linhas.insert(ultimo + 1, linha_nova)
    return "".join(linhas)


def _import_partido(modulo: str, nomes: list[str]) -> str:
    cabeca = f"from abbychess.{modulo} import "
    if len(cabeca) + len(", ".join(nomes)) <= 100:
        return cabeca + ", ".join(nomes) + "\n"
    linhas, atual = [], "    "
    for nome in nomes:
        if len(atual) + len(nome) + 2 > 100:
            linhas.append(atual.rstrip() + "\n")
            atual = "    "
        atual += nome + ", "
    linhas.append(atual.rstrip().rstrip(",") + ")\n")
    return cabeca + "(\n" + "".join(linhas)


def _chamadores(pastas: list[str], origem: str, destino: str, alias: str, nomes: set[str],
                aplicar: bool) -> None:
    importa = re.compile(rf"^([ \t]*)from abbychess import {origem}(?: as (\w+))?\b.*$", re.M)
    for pasta in pastas:
        for arquivo in sorted(pathlib.Path(pasta).rglob("*.py")):
            texto = arquivo.read_text(encoding="utf-8")
            achado = importa.search(texto)
            if achado is None:
                continue
            apelido = achado.group(2) or origem
            uso = re.compile(rf"\b{re.escape(apelido)}\.({'|'.join(map(re.escape, nomes))})\b")
            trocas = len(uso.findall(texto))
            if not trocas:
                continue
            novo = uso.sub(lambda m: f"{alias}.{m.group(1)}", texto)
            for m in reversed(list(importa.finditer(novo))):
                recuo = m.group(1)
                linha = f"{recuo}from abbychess import {destino} as {alias}"
                if linha.strip() not in novo:
                    novo = novo[:m.end()] + "\n" + linha + novo[m.end():]
                else:
                    break
            print(f"{arquivo}: {trocas} chamada(s)")
            if aplicar:
                arquivo.write_text(novo, encoding="utf-8", newline="\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("origem")
    ap.add_argument("destino")
    ap.add_argument("--nomes", required=True)
    ap.add_argument("--cabecalho", required=True, help="arquivo com o docstring e os imports")
    ap.add_argument("--chamadores", default="")
    ap.add_argument("--alias", default="")
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args(argv)
    nomes = {n for n in a.nomes.split(",") if n}
    origem = pathlib.Path(a.origem)
    destino = pathlib.Path(a.destino)
    if destino.exists():
        sys.exit(f"{destino} já existe")
    fonte = origem.read_text(encoding="utf-8")
    linhas, blocos = _blocos(fonte, nomes)
    tirar = {k for inicio, fim, _ in blocos for k in range(inicio, fim)}
    corpo, fim_de_antes = "", None
    for inicio, fim, _ in blocos:          # os vizinhos na origem continuam colados
        trecho = "".join(linhas[inicio:fim])
        corpo += trecho if inicio == fim_de_antes else "\n\n" + trecho
        fim_de_antes = fim
    resto = re.sub(r"\n{4,}", "\n\n\n",
                   "".join(linha for k, linha in enumerate(linhas) if k not in tirar))
    usados = _usados(resto, nomes)
    if usados:
        resto = _com_import(resto, _import_partido(destino.stem, usados))
    cabecalho = pathlib.Path(a.cabecalho).read_text(encoding="utf-8").rstrip("\n")
    novo = re.sub(r"\n{4,}", "\n\n\n", cabecalho + "\n" + corpo)
    print(f"{len(blocos)} definições, {len(tirar)} linhas; origem {len(linhas)} -> "
          f"{resto.count(chr(10))} linhas; a origem ainda usa {len(usados)}: {usados}")
    if a.chamadores:
        _chamadores(a.chamadores.split(","), origem.stem, destino.stem, a.alias or destino.stem,
                    nomes, a.aplicar)
    if a.aplicar:
        origem.write_text(resto, encoding="utf-8", newline="\n")
        destino.write_text(novo, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
