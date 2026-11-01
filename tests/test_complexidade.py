"""Nenhuma função complexa demais fora da lista (SPEC-qualidade §8, CA-Q-X1), a parte que não
precisa da cobertura: uma função com cc >= 10 passa de CRAP 10 mesmo toda coberta, então ela
está em `ferramentas/crap_aceitos.txt` ou reprova aqui, na rápida.

A lista também não cita função que não existe (um corte que renomeia tira a linha) e não
cresce além de `TETO`, que só desce. A outra metade, as de cc < 10 com pouca cobertura e as da
lista que já caíram abaixo de 10, só a medida com a cobertura combinada vê (`qualidade.py`)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "ferramentas"))
import crapper  # noqa: E402

LISTA = RAIZ / "ferramentas" / "crap_aceitos.txt"
CC = 10

#: Quantas linhas a lista pode ter (Q8: 281 no começo); desce a cada função reduzida.
TETO = 81


def violacoes(pacote: Path, lista: set, teto: int) -> list:
    existentes, saida = set(), []
    for arquivo in sorted(pacote.rglob("*.py")):
        nome_do_arquivo = arquivo.relative_to(pacote.parent).as_posix()
        for nome, funcao in crapper.funcoes(ast.parse(arquivo.read_text(encoding="utf-8"))):
            existentes.add((nome_do_arquivo, nome))
            cc = crapper.complexidade(funcao)
            if cc >= CC and (nome_do_arquivo, nome) not in lista:
                saida.append(f"{nome_do_arquivo} {nome}: cc {cc}, fora da lista")
    saida += [f"{a} {n}: não existe; tire-a da lista" for a, n in sorted(lista - existentes)]
    if len(lista) > teto:
        saida.append(f"a lista tem {len(lista)} funções, o teto é {teto}")
    return saida


def test_toda_funcao_com_cc_de_10_ou_mais_esta_na_lista():
    assert violacoes(RAIZ / "abbychess", crapper.aceitas(LISTA), TETO) == []


def test_cada_linha_da_lista_tem_motivo():
    sem_motivo = [linha for linha in LISTA.read_text(encoding="utf-8").splitlines()
                  if linha.strip() and not linha.startswith("#")
                  and not linha.partition("#")[2].strip()]
    assert sem_motivo == []


def test_a_regra_pega_a_complexa_fora_da_lista_o_nome_velho_e_o_teto(tmp_path):
    pacote = tmp_path / "abbychess"
    pacote.mkdir()
    ramos = "".join(f"    if x == {k}:\n        return {k}\n" for k in range(9))
    (pacote / "mod.py").write_text(f"def complexa(x):\n{ramos}    return x\n\n\n"
                                   "def simples():\n    return 1\n", encoding="utf-8")
    assert violacoes(pacote, set(), 0) == ["abbychess/mod.py complexa: cc 10, fora da lista"]
    lista = {("abbychess/mod.py", "complexa"), ("abbychess/mod.py", "antiga")}
    assert violacoes(pacote, lista, 1) == ["abbychess/mod.py antiga: não existe; tire-a da lista",
                                           "a lista tem 2 funções, o teto é 1"]
