r"""O tempo de uma sessão de correção, pelo registro de eventos (SPEC §15.4, CA-F.2).

    $env:ABBY_REGISTRO_DE_EVENTOS = "sessao.jsonl"; .venv\Scripts\python.exe -m abbychess <projeto>
    .venv\Scripts\python.exe ferramentas\tempo_da_fatia.py sessao.jsonl --erros 87 --por <nome>
        --passo 0 --bloco i020-i022

Soma o tempo do primeiro ao último gesto, sem os intervalos ociosos de mais de 60 s, e
divide pelo número de erros do bloco (as diferenças do snapshot contra o gabarito: a soma
de `erros` das páginas do bloco no JSON da fatia). O registro acrescenta ao arquivo, e o
relógio monotônico recomeça a cada vez que o computador liga: cada `inicio` abre uma
sessão nova, e um intervalo entre duas sessões nunca entra na soma. Uma linha cortada (o
programa fechado no meio da escrita) é ignorada.

Grava `docs/medidas/AAAA-MM-DD-fatia-humana.json` (acrescenta a sessão às que já estiverem
lá). É informativo: não reprova passo nenhum.
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MEDIDAS = RAIZ / "docs" / "medidas"
OCIOSO_S = 60.0
GESTOS = {"clique", "tecla", "atalho"}


def _sessoes(linhas):
    """Os instantes dos gestos, uma lista por sessão (cada `inicio` abre uma)."""
    sessoes = [[]]
    for linha in linhas:
        try:
            dados = json.loads(linha)
        except ValueError:
            continue
        if not isinstance(dados, dict):
            continue
        if dados.get("evento") == "inicio":
            if sessoes[-1]:
                sessoes.append([])
        elif dados.get("evento") in GESTOS and isinstance(dados.get("t"), (int, float)):
            sessoes[-1].append(float(dados["t"]))
    return [s for s in sessoes if s]


def tempo_ativo(linhas) -> dict:
    """Segundos ativos e gestos das sessões do registro, sem pausa longa nem salto de relógio."""
    gestos = ativo = pausas = 0
    sessoes = _sessoes(linhas)
    for instantes in sessoes:
        gestos += len(instantes)
        for a, b in zip(instantes, instantes[1:]):
            if 0 <= b - a <= OCIOSO_S:
                ativo += b - a
            else:
                pausas += 1
    return {"gestos": gestos, "segundos_ativos": round(ativo, 1),
            "pausas_descontadas": pausas, "sessoes": len(sessoes)}


def main(argv=None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("registro", type=Path)
    analisador.add_argument("--erros", type=int, required=True,
                            help="as diferenças do bloco contra o gabarito")
    analisador.add_argument("--por", required=True, help="quem fez a sessão")
    analisador.add_argument("--passo", required=True, help="o passo do programa usado")
    analisador.add_argument("--bloco", required=True, help="as páginas, ex.: i020-i022")
    args = analisador.parse_args(argv)
    sessao = tempo_ativo(args.registro.read_text(encoding="utf-8").splitlines())
    sessao.update({"por": args.por, "passo": args.passo, "bloco": args.bloco,
                   "erros": args.erros,
                   "segundos_por_erro": round(sessao["segundos_ativos"] / args.erros, 2)
                   if args.erros else None})
    hoje = datetime.date.today().isoformat()
    destino = MEDIDAS / f"{hoje}-fatia-humana.json"
    dados = (json.loads(destino.read_text(encoding="utf-8")) if destino.is_file()
             else {"data": hoje, "sessoes": []})
    dados["sessoes"].append(sessao)
    MEDIDAS.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                       newline="\n")
    print(json.dumps(sessao, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
