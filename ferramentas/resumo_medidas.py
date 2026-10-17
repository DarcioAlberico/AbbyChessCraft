r"""Escreve no README as tabelas das medidas, a partir dos JSON de `docs/medidas/`.

    .venv\Scripts\python.exe ferramentas\resumo_medidas.py

Nenhum número das medidas é digitado à mão no README (SPEC §15.3): este script troca o
que estiver entre `<!-- medidas:inicio -->` e `<!-- medidas:fim -->` pela tabela gerada da
medida mais recente de cada tipo (linha de base de desempenho, qualidade por livro, fatia
por livro e passo). "Mais recente" é pela data e pela hora do nome do arquivo
(`comum.ultima_medida`); os `-falhou` e `-parcial` nunca entram nessas tabelas (as rodadas
repetidas só do lote, que são `-parcial`, aparecem só na tabela delas, marcadas). O estado
de cada medida vem do próprio JSON.
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
#: Os passos na ordem do roadmap (as tabelas seguem esta ordem, não a alfabética).
ORDEM_DOS_PASSOS = ("0", "1a", "1b", "2a", "2b", "a1", "a2", "a3", "e", "d1", "b", "d2", "c", "i",
                    "f", "g", "h", "j", "k", "l")


def _na_ordem(passo: str):
    """A chave de ordenação de um passo ("D1", "d1", "passo-d1"...): a do roadmap."""
    nome = str(passo).lower().removeprefix("passo-").removeprefix("passo ")
    return (ORDEM_DOS_PASSOS.index(nome) if nome in ORDEM_DOS_PASSOS else len(ORDEM_DOS_PASSOS),
            nome)
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
              "| Livro | Commit | Páginas | Margens corridas P / R | Diagramas achados (falsos) | "
              "Sem par | Sem par nas negativas | Perdidas | FEN = leitura | Casas erradas por "
              "diagrama | Lado certo | Ordem | CER do corpo | Estado |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
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
            f"| {livro} | {dados.get('commit')} | {len(dados['indices'])} | "
            f"{_num(r.get('margens_precisao'))} / "
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
    for (livro, passo), (_, arquivo) in sorted(mais_recente.items(),
                                               key=lambda i: (i[0][0], _na_ordem(i[0][1]))):
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


_PASSO = re.compile(r"\d{4}-\d{2}-\d{2}-passo-(?P<passo>[^-]+)(?:-\d{6})?\.json")


def _por_passo() -> list:
    """O desempenho de cada passo do roadmap (`ABBY_ROTULO_DA_MEDIDA=passo-<passo>`), ao lado
    da linha de base: as mesmas metas, a medida mais nova de cada passo."""
    _, base = _ultimo("linha-de-base")
    passos = sorted({c["passo"] for a in MEDIDAS.glob("*-passo-*.json")
                     if (c := _PASSO.fullmatch(a.name))}, key=_na_ordem)
    if base is None or not passos:
        return []
    metas = (("troca_de_pagina", "p95_ms", "Troca de página, p95"),
             ("troca_fora_do_cache", "p95_ms", "Troca fora do cache, p95"),
             ("enter_ensinar", "p95_ms", "Enter, p95"),
             ("releitura_de_um_glifo", "p95_ms", "Releitura, p95"),
             ("memoria_do_desfazer", "estimado_300x20_mb", "Desfazer (MB)"),
             ("atraso_durante_o_lote", "p99_ms", "Atraso no lote, p99"),
             ("memoria_total_com_o_lote", "rss_pico_mb", "Memória com o lote (MB)"),
             ("releitura_com_o_lote", "p95_ms", "Releitura com o lote, p95"),
             ("atraso_durante_o_lote_falso", "p99_ms", "Atraso no lote falso (51 p.), p99"),
             ("gravar_pagina_do_lote", "p95_ms", "Gravar uma página do lote, p95"),
             ("lote_com_e_sem_servidor", "com_servidor_s_por_pagina", "Lote com servidor (s/p.)"),
             ("lote_com_e_sem_servidor", "sem_servidor_s_por_pagina", "Lote sem servidor (s/p.)"),
             ("pintura_dos_boxes", "p95_ms", "Pintura de 2.000 boxes, p95"),
             ("texto_da_pagina", "p95_ms", "Montar o Documento, p95"),
             ("clique_no_documento", "p95_ms", "Clique no Documento, p95"),
             ("clique_no_box", "p95_ms", "Clique acha o box, p95"))
    colunas = [("linha de base", base)]
    for passo in passos:
        arquivo, dados = _ultimo(f"passo-{passo}")
        if dados is not None:
            colunas.append((f"{passo} (`{arquivo.name}`)", dados))
    linhas = ["", "Desempenho por passo, em ms ou MB (uma rodada cada, a do portão, que roda "
              "no mesmo processo depois dos testes `livro_real` e por isso não é a condição "
              "das rodadas repetidas; quanto o mesmo código varia, e o que se conclui, está "
              "nelas, abaixo):", "",
              "| Meta | " + " | ".join(nome for nome, _ in colunas) + " |",
              "|---|" + "---|" * len(colunas)]
    for chave, campo, rotulo in metas:
        valores = [_num(dados["medidas"].get(chave, {}).get(campo)) for _, dados in colunas]
        linhas.append(f"| {rotulo} | " + " | ".join(valores) + " |")
    return linhas


_REPETICAO = re.compile(r"(?P<data>\d{4}-\d{2}-\d{2})-repeticao-(?P<passo>[^-]+)"
                        r"(?P<parcial>-parcial)?(?:-(?P<hora>\d{6}))?\.json")
_METAS_REPETIDAS = (("troca_de_pagina", "p50_ms", "Troca, p50"),
                    ("troca_de_pagina", "p95_ms", "Troca, p95"),
                    ("troca_fora_do_cache", "p50_ms", "Fora do cache, p50"),
                    ("enter_ensinar", "p50_ms", "Enter, p50"),
                    ("enter_ensinar", "p95_ms", "Enter, p95"),
                    ("releitura_de_um_glifo", "p50_ms", "Releitura, p50"),
                    ("releitura_de_um_glifo", "p95_ms", "Releitura, p95"),
                    ("atraso_durante_o_lote", "p99_ms", "Atraso no lote, p99"),
                    ("releitura_com_o_lote", "p95_ms", "Releitura com o lote, p95"))


def _repeticoes() -> list:
    """As rodadas repetidas (`ABBY_ROTULO_DA_MEDIDA=repeticao-<passo>`), para separar o efeito
    de um passo da variação entre rodadas do mesmo código. A rodada **completa** roda o
    módulo inteiro, na ordem da linha de base (o lote lê com os padrões que o Enter
    ensinou); a **só do lote** (`-k atraso`, `-parcial`) lê sem eles e é outra carga."""
    grupos = {}
    for arquivo in MEDIDAS.glob("*-repeticao-*.json"):
        casou = _REPETICAO.fullmatch(arquivo.name)
        if casou:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
            condicao = "só do lote, sem os padrões" if casou["parcial"] else "completa"
            ordem = (casou["data"], casou["hora"] or "")
            grupos.setdefault((casou["passo"], condicao), []).append((ordem, dados))
    if not grupos:
        return []
    linhas = ["", "Rodadas repetidas, em ms (cada valor é uma rodada, na ordem em que rodou). Sem o "
              "congelamento dos modelos para a coleta de lixo (até o 1a, e no 1b com "
              "`ABBY_SEM_CONGELAR=1`), o p95 do Enter do passo 0 ao 1b tem duas faixas no mesmo "
              "código (perto de 110–130 e de 180–235; no 2a, uma só, perto de 90); o atraso no "
              "lote tem duas faixas sempre (perto de 8–10 e de 21). Desde o 2b o congelamento é "
              "desligado (`ABBY_CONGELAR=1` liga): as duas linhas do 2b rodam o mesmo programa (o "
              "rótulo `sem_congelar` é do roteiro de medida), e a coluna do Enter mede até a "
              "cor mudar (até o 2a, até o fim da propagação). Desde o A1 a troca é no cache de páginas "
              "(a vizinha já pré-carregada); a de fora do cache tem coluna própria. "
              "Compare pela mediana (p50), que varia bem menos (mas uma rodada solta pode sair "
              "alta):", "",
              "| Código | Commit | Rodada | " + " | ".join(r for _, _, r in _METAS_REPETIDAS) + " |",
              "|---|---|---|" + "---|" * len(_METAS_REPETIDAS)]
    for (passo, condicao), rodadas in sorted(grupos.items(),
                                             key=lambda i: (_na_ordem(i[0][0]), i[0][1])):
        rodadas.sort(key=lambda r: r[0])
        commits = sorted({d["ambiente"].get("commit") for _, d in rodadas})
        valores = []
        for chave, campo, _ in _METAS_REPETIDAS:
            serie = [d["medidas"].get(chave, {}).get(campo) for _, d in rodadas]
            valores.append("; ".join(_num(v) for v in serie) if any(v is not None for v in serie)
                           else "—")
        linhas.append(f"| passo {passo.replace('_', ' ')} | {', '.join(commits)} | {condicao} | "
                      + " | ".join(valores) + " |")
    return linhas


def _historico_da_qualidade() -> list:
    """Todas as medidas de qualidade, por livro e na ordem: o que um passo mudou aparece."""
    linhas = []
    for livro in LIVROS:
        medidas = []
        for arquivo in MEDIDAS.glob(f"*-qualidade-{livro}*.json"):
            casou = re.fullmatch(rf"(\d{{4}}-\d{{2}}-\d{{2}})-qualidade-{livro}(?:-(\d{{6}}))?\.json",
                                 arquivo.name)
            if casou:
                medidas.append(((casou[1], casou[2] or ""), arquivo))
        for _, arquivo in sorted(medidas):
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
            r = dados["resumo"]
            linhas.append(
                f"| {livro} | {dados.get('commit')} | {_num(r.get('margens_precisao'))} / "
                f"{_num(r.get('margens_revocacao'))} | {r.get('diagramas_achados')} "
                f"({r.get('diagramas_falsos')}) | {r.get('linhas_sem_par')} | "
                f"{r.get('linhas_perdidas')} | {_num(r.get('casas_erradas_provisorio'))} | "
                f"{r.get('lado_certo_provisorio')} | {_num(r.get('lote_s'))} s |")
    if not linhas:
        return []
    return ["", "Histórico da qualidade (todas as medidas; casas e lado provisórios):", "",
            "| Livro | Commit | Margens P / R | Diagramas (falsos) | Sem par | Perdidas | Casas | "
            "Lado | Lote |", "|---|---|---|---|---|---|---|---|---|", *linhas]


def gerar() -> str:
    return "\n".join(_desempenho() + _por_passo() + _repeticoes() + _qualidade()
                     + _historico_da_qualidade() + _fatia())


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
