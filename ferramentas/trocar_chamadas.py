"""Troca chamadas nos arquivos por uma tabela de regex (o corte 3 do Q7: quem chamava o
`ControladorDePagina` passa a chamar o colaborador).

    python ferramentas/trocar_chamadas.py TABELA [--aplicar]

TABELA: um arquivo de linhas `arquivo<TAB>regex<TAB>troca<TAB>quantas` (`quantas` é quantas
trocas se esperam naquele arquivo; outra contagem para tudo, sem gravar nada). Linhas vazias e
as que começam com `#` são puladas."""

from __future__ import annotations

import pathlib
import re
import sys


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    tabela = pathlib.Path(argv[0]).read_text(encoding="utf-8").splitlines()
    aplicar = "--aplicar" in argv
    textos, erros = {}, []
    for linha in tabela:
        if not linha.strip() or linha.startswith("#"):
            continue
        arquivo, regex, troca, quantas = linha.split("\t")
        caminho = pathlib.Path(arquivo)
        texto = textos.get(caminho)
        if texto is None:
            texto = caminho.read_text(encoding="utf-8")
        texto, n = re.subn(regex, troca, texto)
        if n != int(quantas):
            erros.append(f"{arquivo}: {regex!r} trocou {n}, esperava {quantas}")
        textos[caminho] = texto
    for erro in erros:
        print(erro)
    if erros:
        return 1
    for caminho, texto in textos.items():
        print(f"{caminho}: trocado")
        if aplicar:
            caminho.write_text(texto, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
