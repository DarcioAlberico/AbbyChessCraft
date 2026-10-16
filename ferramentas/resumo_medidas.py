r"""Escreve no README as tabelas das medidas, a partir dos JSON de `docs/medidas/`.

    .venv\Scripts\python.exe ferramentas\resumo_medidas.py

Nenhum número das medidas é digitado à mão no README (SPEC §15.3): este script troca o
que estiver entre `<!-- medidas:inicio -->` e `<!-- medidas:fim -->` pela tabela gerada da
medida mais recente de cada tipo (linha de base de desempenho, qualidade por livro, fatia).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MEDIDAS = RAIZ / "docs" / "medidas"
README = RAIZ / "README.md"
INICIO, FIM = "<!-- medidas:inicio -->", "<!-- medidas:fim -->"


def _ultimo(padrao: str):
    arquivos = sorted(MEDIDAS.glob(padrao))
    if not arquivos:
        return None, None
    return arquivos[-1], json.loads(arquivos[-1].read_text(encoding="utf-8"))


def _ms(valor) -> str:
    return "—" if valor is None else f"{round(valor):d} ms"


def _num(valor) -> str:
    """Número com vírgula decimal; ausente (nada a medir) vira travessão."""
    if valor is None:
        return "—"
    return f"{valor:g}".replace(".", ",") if isinstance(valor, float) else str(valor)


def _desempenho() -> list:
    arquivo, dados = _ultimo("*-linha-de-base.json")
    if dados is None:
        return ["Linha de base de desempenho: ainda não medida."]
    m = dados["medidas"]
    troca, enter = m.get("troca_de_pagina", {}), m.get("enter_ensinar", {})
    releitura, memoria = m.get("releitura_de_um_glifo", {}), m.get("memoria_do_desfazer", {})
    lote, total = m.get("atraso_durante_o_lote", {}), m.get("memoria_total_com_o_lote", {})
    padroes = enter.get("padroes_no_livro") or ["?", "?"]
    linhas = [
        f"Desempenho, de `docs/medidas/{arquivo.name}` (máquina cadastrada: "
        f"{'sim' if dados['ambiente'].get('maquina_cadastrada') else 'não'}; p95 de "
        f"{troca.get('n', '?')} repetições):",
        "",
        "| Meta (spec §2) | Hoje | Alvo |",
        "|---|---|---|",
        f"| Trocar de página (não há cache) | p95 {_ms(troca.get('p95_ms'))} | "
        f"{troca.get('alvo_no_cache_ms')} ms no cache; fora do cache ainda não medido pelo método |",
        f"| Enter até a cor do box mudar | p95 {_ms(enter.get('p95_ms'))} "
        f"({padroes[0]} → {padroes[1]} padrões no livro) | {enter.get('alvo_ms')} ms |",
        f"| Releitura de um glifo | p95 {_ms(releitura.get('p95_ms'))}; impossível com o lote | "
        f"{releitura.get('alvo_ms')} ms com o lote |",
        f"| Memória do desfazer, 300 páginas × 20 ações | ~{_num(memoria.get('estimado_300x20_mb'))} MB "
        f"(estimado) | {memoria.get('alvo_mb')} MB |",
        f"| Atraso da interface durante o lote ({lote.get('paginas')} páginas) | p99 "
        f"{_num(lote.get('p99_ms'))} ms, com as ações desabilitadas | {lote.get('alvo_p99_ms')} ms, "
        "com as ações |",
        f"| Memória com o lote | {total.get('rss_pico_mb')} MB num processo | "
        f"{total.get('alvo_mb')} MB |",
    ]
    return linhas


def _provisorio(valor_ok, valor_todos) -> str:
    """O número conferido, ou 'pendente' com o provisório entre parênteses."""
    if valor_ok not in (None, "0/0"):
        return _num(valor_ok)
    if valor_todos in (None, "0/0"):
        return "—"
    return f"pendente (provisório: {_num(valor_todos)})"


def _qualidade() -> list:
    linhas = ["", "Qualidade contra os gabaritos (`ferramentas\\medir.py`). Casas e lado só "
              "contam nos diagramas conferidos; o provisório (contra o FEN do rascunho, ainda "
              "não conferido) vai entre parênteses. \"Margens corridas\" são cabeçalho, número "
              "de página e rodapé; \"—\" é nada a medir (nenhuma linha tirada, nenhum "
              "diagrama).", "",
              "| Livro | Páginas | Margens corridas P / R | Diagramas achados (falsos) | "
              "Linhas sem par | Casas erradas por diagrama | Lado certo | Ordem "
              "(discordância) | CER do corpo | Estado |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    achou = False
    for livro in ("xv", "yusupov", "darcy"):
        arquivo, dados = _ultimo(f"*-qualidade-{livro}.json")
        if dados is None:
            continue
        achou = True
        r = dados["resumo"]
        cer = ("pendente" if r.get("cer_corpo") is None
               else f"{r['cer_corpo']:.2%}".replace(".", ","))
        linhas.append(
            f"| {livro} | {len(dados['indices'])} | {_num(r.get('margens_precisao'))} / "
            f"{_num(r.get('margens_revocacao'))} | {r.get('diagramas_achados')} "
            f"({r.get('diagramas_falsos')}) | {r.get('linhas_sem_par')} | "
            f"{_provisorio(r.get('casas_erradas_por_diagrama'), r.get('casas_erradas_provisorio'))} | "
            f"{_provisorio(r.get('lado_certo'), r.get('lado_certo_provisorio'))} | "
            f"{_num(r.get('ordem_discordancia_media'))} | {cer} | {r.get('estado')} |")
    if achou:
        _, algum = _ultimo("*-qualidade-xv.json")
        fora = (algum or {}).get("nao_medido") or {}
        if fora:
            linhas += ["", "Ainda não medido: " + "; ".join(
                f"{k.replace('_', ' ')} ({v})" for k, v in fora.items()) + "."]
    return linhas if achou else []


_FATIA = re.compile(r"\d{4}-\d{2}-\d{2}-fatia-(?P<livro>[^-]+)-passo-(?P<passo>.+)\.json")


def _fatia() -> list:
    """A medida mais recente de cada (livro, passo), com o estado que o JSON dá."""
    mais_recente = {}
    for arquivo in sorted(MEDIDAS.glob("*-fatia-*-passo-*.json")):
        casou = _FATIA.fullmatch(arquivo.name)
        if casou:
            mais_recente[(casou["livro"], casou["passo"])] = arquivo
    linhas = []
    for (livro, passo), arquivo in sorted(mais_recente.items()):
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        paginas = ", ".join(sorted(dados.get("paginas", {})))
        if dados.get("gestos") is None:
            total = "gestos pendentes"
        else:
            total = (f"{dados['gestos']} gestos ({dados['gestos_sem_impossiveis']} sem os "
                     "impossíveis)")
        linhas.append(f"| {livro} | {passo} | {paginas} | {total} | "
                      f"{dados.get('gestos_diagramas')} | {dados.get('gestos_navegacao', '—')} | "
                      f"{dados.get('estado')} | `{arquivo.name}` |")
    if not linhas:
        return []
    return ["", "Fatia (`ferramentas\\replay_fatia.py`):", "",
            "| Livro | Passo | Páginas | Total | Gestos dos diagramas | Navegação | Estado | "
            "JSON |", "|---|---|---|---|---|---|---|---|", *linhas]


def gerar() -> str:
    return "\n".join(_desempenho() + _qualidade() + _fatia())


def main() -> int:
    # `newline=""` lê e grava os fins de linha como estão: o README não muda de CRLF para LF.
    with open(README, encoding="utf-8", newline="") as arquivo:
        texto = arquivo.read()
    if INICIO not in texto or FIM not in texto:
        print(f"o README não tem os marcadores {INICIO} / {FIM}", file=sys.stderr)
        return 1
    fim_de_linha = "\r\n" if "\r\n" in texto else "\n"
    gerado = gerar().replace("\n", fim_de_linha)
    novo = re.sub(re.escape(INICIO) + r".*?" + re.escape(FIM),
                  lambda _m: f"{INICIO}{fim_de_linha}{gerado}{fim_de_linha}{FIM}", texto,
                  flags=re.S)
    with open(README, "w", encoding="utf-8", newline="") as arquivo:
        arquivo.write(novo)
    print("README: tabelas das medidas atualizadas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
