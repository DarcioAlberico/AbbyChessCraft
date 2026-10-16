r"""Escreve no README as tabelas das medidas, a partir dos JSON de `docs/medidas/`.

    .venv\Scripts\python.exe ferramentas\resumo_medidas.py

Nenhum número das medidas é digitado à mão no README (SPEC §15.3): este script troca o
que estiver entre `<!-- medidas:inicio -->` e `<!-- medidas:fim -->` pela tabela gerada da
medida mais recente de cada tipo (linha de base de desempenho, qualidade por livro, fatia
por livro e passo). "Mais recente" é pela data e pela hora do nome do arquivo
(`comum.ultima_medida`); os `-falhou` e `-parcial` nunca entram. O estado de cada medida
vem do próprio JSON.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "ferramentas"))

from comum import ultima_medida  # noqa: E402

MEDIDAS = RAIZ / "docs" / "medidas"
README = RAIZ / "README.md"
INICIO, FIM = "<!-- medidas:inicio -->", "<!-- medidas:fim -->"
LIVROS = ("xv", "yusupov", "darcy")
_FATIA = re.compile(r"\d{4}-\d{2}-\d{2}-fatia-(?P<livro>[^-]+)-passo-(?P<passo>[^-]+)"
                    r"(?:-(?P<hora>\d{6}))?\.json")
_NOMES = {"ligacao_da_legenda": "a ligação da legenda ao diagrama",
          "precisao_e_revocacao_por_funcao": "precisão e revocação por função de bloco",
          "validacao_pelos_lances": "a validação do FEN pelos lances"}


def _ultimo(base: str):
    arquivo = ultima_medida(base, MEDIDAS)
    if arquivo is None:
        return None, None
    return arquivo, json.loads(arquivo.read_text(encoding="utf-8"))


def _ms(valor) -> str:
    return "—" if valor is None else f"{round(valor):d} ms"


def _num(valor) -> str:
    """Número com vírgula decimal; ausente (nada a medir) vira travessão."""
    if valor is None:
        return "—"
    return f"{valor:g}".replace(".", ",") if isinstance(valor, float) else str(valor)


def _desempenho() -> list:
    arquivo, dados = _ultimo("linha-de-base")
    if dados is None:
        return ["Linha de base de desempenho: ainda não medida."]
    m = dados["medidas"]
    troca, enter = m.get("troca_de_pagina", {}), m.get("enter_ensinar", {})
    releitura, memoria = m.get("releitura_de_um_glifo", {}), m.get("memoria_do_desfazer", {})
    lote, total = m.get("atraso_durante_o_lote", {}), m.get("memoria_total_com_o_lote", {})
    padroes = enter.get("padroes_no_livro") or ["?", "?"]
    novos = enter.get("caracteres_novos")
    novos = (f"; {novos} das {enter.get('n')} repetições ensinaram caractere novo"
             if novos is not None else "")
    acoes = memoria.get("acoes")
    estimativa = f"estimado de {acoes} ações em 3 páginas" if acoes else "estimado"
    return [
        f"Desempenho, de `docs/medidas/{arquivo.name}` (commit {dados['ambiente'].get('commit')}; "
        f"máquina cadastrada: {'sim' if dados['ambiente'].get('maquina_cadastrada') else 'não'}; "
        f"p95 de {troca.get('n', '?')} repetições):",
        "",
        "| Meta (spec §2) | Hoje | Alvo |",
        "|---|---|---|",
        f"| Trocar de página (não há cache) | p95 {_ms(troca.get('p95_ms'))} | "
        f"{troca.get('alvo_no_cache_ms')} ms no cache; fora do cache ainda não medido pelo método |",
        f"| Enter até a cor do box mudar | p95 {_ms(enter.get('p95_ms'))} "
        f"({padroes[0]} → {padroes[1]} padrões no livro{novos}) | {enter.get('alvo_ms')} ms |",
        f"| Releitura de um glifo | p95 {_ms(releitura.get('p95_ms'))}; impossível com o lote | "
        f"{releitura.get('alvo_ms')} ms com o lote |",
        f"| Memória do desfazer, 300 páginas × 20 ações | ~{_num(memoria.get('estimado_300x20_mb'))} MB "
        f"({estimativa}, extrapolado) | {memoria.get('alvo_mb')} MB |",
        f"| Atraso da interface durante o lote ({lote.get('paginas')} páginas) | p99 "
        f"{_num(lote.get('p99_ms'))} ms, com as ações desabilitadas | {lote.get('alvo_p99_ms')} ms, "
        "com as ações |",
        f"| Memória com o lote | {total.get('rss_pico_mb')} MB num processo | "
        f"{total.get('alvo_mb')} MB |",
        *[f"| {rotulo} | {m[chave].get('estado', '—')} | {_ms(m[chave].get('alvo_p95_ms'))} |"
          for chave, rotulo in (("buscar_regex_no_livro", "Buscar regex no livro"),
                                ("montar_indice_da_busca", "Montar o índice da busca"))
          if chave in m],
    ]


def _provisorio(valor_ok, valor_todos) -> str:
    """O número conferido, ou 'pendente' com o provisório entre parênteses."""
    if valor_ok not in (None, "0/0"):
        return _num(valor_ok)
    if valor_todos in (None, "0/0"):
        return "—"
    return f"pendente (provisório: {_num(valor_todos)})"


_LEGENDA = (
    "Qualidade contra os gabaritos (`ferramentas\\medir.py`). **Margens corridas**: cabeçalho, "
    "número de página e rodapé tirados do texto. **Sem par**: linhas lidas que não casam com "
    "nenhuma linha do gabarito (inventadas); as das páginas negativas (capa, sumário) vão à "
    "parte. **Perdidas**: linhas do gabarito que a leitura não achou. **Casas** e **lado** só "
    "contam nos diagramas que você conferiu; o provisório, entre parênteses, é contra o FEN "
    "rotulado pelo assistente (casa a casa, contra o recorte), ainda não conferido por você, e "
    "a coluna **FEN = leitura** diz em quantos ele é igual ao que o programa leu. **Ordem**: "
    "pares de linhas casadas fora da ordem de leitura do gabarito (não vê onde o diagrama cai "
    "no texto). \"—\" é nada a medir.")


def _nas_negativas(r: dict) -> str:
    n = r.get("linhas_perdidas_negativas")
    return f" (+{n} nas negativas)" if n else ""


def _qualidade() -> list:
    cabeca = ["", _LEGENDA, "",
              "| Livro | Páginas | Margens corridas P / R | Diagramas achados (falsos) | "
              "Sem par | Sem par nas negativas | Perdidas | FEN = leitura | Casas erradas por "
              "diagrama | Lado certo | Ordem | CER do corpo | Estado |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    linhas, fora = [], {}
    for livro in LIVROS:
        _, dados = _ultimo(f"qualidade-{livro}")
        if dados is None:
            continue
        r = dados["resumo"]
        fora.update(dados.get("nao_medido") or {})
        cer = ("pendente" if r.get("cer_corpo") is None
               else f"{r['cer_corpo']:.2%}".replace(".", ","))
        negativas = (f"{r.get('linhas_sem_par_negativas')} ({r.get('paginas_negativas')} pág.)"
                     if r.get("paginas_negativas") else "—")
        linhas.append(
            f"| {livro} | {len(dados['indices'])} | {_num(r.get('margens_precisao'))} / "
            f"{_num(r.get('margens_revocacao'))} | {r.get('diagramas_achados')} "
            f"({r.get('diagramas_falsos')}) | {r.get('linhas_sem_par')} | {negativas} | "
            f"{r.get('linhas_perdidas')}{_nas_negativas(r)} | {r.get('fen_igual_a_leitura')} | "
            f"{_provisorio(r.get('casas_erradas_por_diagrama'), r.get('casas_erradas_provisorio'))} | "
            f"{_provisorio(r.get('lado_certo'), r.get('lado_certo_provisorio'))} | "
            f"{_num(r.get('ordem_discordancia_media'))} | {cer} | {r.get('estado')} |")
    if not linhas:
        return []
    saida = cabeca + linhas
    if fora:
        saida += ["", "Ainda não medido: " + "; ".join(
            f"{_NOMES.get(k, k)}, no {v}" for k, v in fora.items()) + "."]
    return saida


def _fatia() -> list:
    """A medida mais recente de cada (livro, passo), com o estado que o JSON dá."""
    mais_recente = {}
    for arquivo in MEDIDAS.glob("*-fatia-*-passo-*.json"):
        casou = _FATIA.fullmatch(arquivo.name)
        if casou:
            chave = (casou["livro"], casou["passo"])
            ordem = (arquivo.name[:10], casou["hora"] or "")
            if chave not in mais_recente or ordem > mais_recente[chave][0]:
                mais_recente[chave] = (ordem, arquivo)
    linhas = []
    for (livro, passo), (_, arquivo) in sorted(mais_recente.items()):
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        paginas = ", ".join(sorted(dados.get("paginas", {})))
        if dados.get("gestos") is None:
            total = "gestos pendentes"
        else:
            total = (f"{dados['gestos']} gestos ({dados['gestos_sem_impossiveis']} sem os "
                     "impossíveis)")
        erros_texto = sum((p.get("erros") or {}).get("texto", 0)
                          for p in dados.get("paginas", {}).values())
        erros_diagramas = sum((p.get("erros") or {}).get("diagramas", 0)
                              for p in dados.get("paginas", {}).values())
        erros = (f"{erros_texto + erros_diagramas}" if dados.get("gestos") is not None
                 else f"{erros_diagramas} (diagramas; texto pendente)")
        linhas.append(f"| {livro} | {passo} | {paginas} | {total} | "
                      f"{dados.get('gestos_diagramas')} | {dados.get('gestos_navegacao', '—')} | "
                      f"{erros} | {dados.get('estado')} | `{arquivo.name}` |")
    if not linhas:
        return []
    return ["", "Fatia (`ferramentas\\replay_fatia.py`; **erros** são as diferenças do snapshot "
            "contra o gabarito, o N da medida humana):", "",
            "| Livro | Passo | Páginas | Total | Gestos dos diagramas | Navegação | Erros | "
            "Estado | JSON |", "|---|---|---|---|---|---|---|---|---|", *linhas]


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
