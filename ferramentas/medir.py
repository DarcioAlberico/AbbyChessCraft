r"""O roteiro de medição contra os gabaritos (SPEC §15.2, §15.3).

    .venv\Scripts\python.exe ferramentas\medir.py --livro xv --indices 0,7,20-26
    .venv\Scripts\python.exe ferramentas\medir.py --livro yusupov --indices 6,12,33
    .venv\Scripts\python.exe ferramentas\medir.py --livro darcy --indices 25,26

Reconhece as páginas num projeto temporário (modelos globais, padrões vazios), como o
programa faz, e compara com `tests/verdade/<livro>/`:

- **margens corridas**: precisão e revocação das linhas tiradas como título corrido,
  número de página ou rodapé (o que a exportação faz hoje) contra os blocos `cabecalho`,
  `numero_de_pagina` e `rodape`;
- **diagramas**: tabuleiros achados (IoU ≥ 0,5) e falsos; casas erradas no FEN e lado a
  jogar **só nos diagramas com `fen_verificado` / `lado_verificado`** (os outros dão o
  número provisório, contra o FEN do rascunho, à parte);
- **linhas sem par**: linhas lidas que não casam com nenhuma linha do gabarito, à parte
  nas páginas `negativa` (capa, sumário: a medida de "nada inventado") e no resto; e
  **linhas perdidas**: linhas do gabarito que a leitura não achou (a revocação de linhas);
- **ordem**: distância de Kendall (normalizada) entre a ordem lida e a do gabarito, nas
  linhas de corpo casadas;
- **CER do corpo**: só sobre as linhas com `texto_verificado: true` (o texto do gabarito é
  do usuário; enquanto ele não verifica, a medida fica "pendente").

O que a spec pede e ainda não é medido fica em `nao_medido`, com o passo que o traz.
Grava `docs/medidas/AAAA-MM-DD-qualidade-<livro>.json`. O README cita esse JSON, e nenhum
número é digitado à mão.

A comparação é `comparar_pagina` (pura: gabarito × leitura), e `resumir` soma as páginas;
`tests/test_medir.py` as testa sem PDF.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))

from comum import destino_da_medida, estado_do_git  # noqa: E402
from rotular import (PASTA_DOS_PDFS, VERDADE, _caixa_relativa, _indices,  # noqa: E402
                     levenshtein, problemas_do_fen, sha256_do_arquivo)

MEDIDAS = RAIZ / "docs" / "medidas"
IOU_MINIMO = 0.5
FUNCOES_DE_MARGEM = ("cabecalho", "numero_de_pagina", "rodape")
NAO_MEDIDO = {
    "ligacao_da_legenda": "passo H (a leitura de hoje não liga legenda a diagrama)",
    "precisao_e_revocacao_por_funcao": "passo F (a leitura de hoje não classifica blocos)",
    "validacao_pelos_lances": "passo H",
}


def iou(a, b) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    uniao = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / uniao if uniao > 0 else 0.0


def casar(previstos, verdade):
    """Casamento guloso por IoU: [(i_previsto, j_verdade)], cada um usado uma vez."""
    pares = sorted(((iou(p, v), i, j) for i, p in enumerate(previstos)
                    for j, v in enumerate(verdade)), reverse=True)
    usados_p, usados_v, saida = set(), set(), []
    for valor, i, j in pares:
        if valor < IOU_MINIMO:
            break
        if i not in usados_p and j not in usados_v:
            usados_p.add(i)
            usados_v.add(j)
            saida.append((i, j))
    return saida


def casas(fen: str) -> Optional[list]:
    """As 64 casas da parte das peças do FEN ('.' = vazia), ou `None` se ele for malformado
    (pela mesma regra de `rotular.problemas_do_fen`)."""
    pecas = (fen or "").split(" ")[0]
    if problemas_do_fen(pecas):
        return None
    return [c for fileira in pecas.split("/")
            for ch in fileira for c in (["."] * int(ch) if ch in "12345678" else [ch])]


def unir_por_linha(caixas):
    """Junta as caixas que dividem a mesma linha (sobreposição vertical ≥ 50% da menor).

    Um título corrido rotulado em dois blocos lado a lado é uma linha só da leitura; sem
    juntar, a linha casaria com um bloco e o outro viraria falso negativo.
    """
    unidas = []
    for caixa in sorted(caixas, key=lambda c: (c[1], c[0])):
        for k, outra in enumerate(unidas):
            sobra = min(caixa[3], outra[3]) - max(caixa[1], outra[1])
            menor = min(caixa[3] - caixa[1], outra[3] - outra[1])
            if menor > 0 and sobra >= 0.5 * menor:
                unidas[k] = [min(caixa[0], outra[0]), min(caixa[1], outra[1]),
                             max(caixa[2], outra[2]), max(caixa[3], outra[3])]
                break
        else:
            unidas.append(list(caixa))
    return unidas


def discordancia(ordem_a, ordem_b) -> float:
    """Fração de pares discordantes entre duas ordens dos mesmos itens (0 = iguais, 1 = invertida).

    É a distância de Kendall normalizada, e não o tau.
    """
    n = len(ordem_a)
    if n < 2:
        return 0.0
    pos_b = {item: k for k, item in enumerate(ordem_b)}
    discordantes = sum(1 for i in range(n) for j in range(i + 1, n)
                       if pos_b[ordem_a[i]] > pos_b[ordem_a[j]])
    return discordantes / (n * (n - 1) / 2)


# ----------------------------------------------------------------------
# A comparação de uma página, sem PDF
# ----------------------------------------------------------------------

@dataclass
class DiagramaDaLeitura:
    caixa_rel: list
    fen: str
    lado: str
    confiavel: bool = True


@dataclass
class Leitura:
    """O que o programa leu numa página, nas coordenadas relativas do gabarito."""
    #: Cada linha lida: caixa relativa e texto, na ordem da leitura.
    linhas: List[tuple] = field(default_factory=list)
    #: As caixas das linhas tiradas como margem corrida (sem a poeira da borda).
    margens: List[list] = field(default_factory=list)
    diagramas: List[DiagramaDaLeitura] = field(default_factory=list)


def comparar_pagina(gabarito: dict, leitura: Leitura) -> dict:
    """As medidas de uma página: margens, diagramas, linhas sem par, ordem e CER."""
    caixas_linhas = [c for c, _ in leitura.linhas]

    verd_margem = unir_por_linha([b["caixa_rel"] for b in gabarito["blocos"]
                                  if b["funcao"] in FUNCOES_DE_MARGEM])
    casados_m = casar(leitura.margens, verd_margem)
    margens = {"vp": len(casados_m), "fp": len(leitura.margens) - len(casados_m),
               "fn": len(verd_margem) - len(casados_m)}

    blocos_d = [b for b in gabarito["blocos"] if b["funcao"] == "diagrama"]
    verdade_d = {d["id"]: d for d in gabarito["diagramas"]}
    casados_d = casar([d.caixa_rel for d in leitura.diagramas],
                      [b["caixa_rel"] for b in blocos_d])
    detalhes = []
    for ip, jv in sorted(casados_d, key=lambda par: par[1]):
        verdade, lido = verdade_d[blocos_d[jv]["id"]], leitura.diagramas[ip]
        certo, previsto = casas(verdade["fen"]), casas(lido.fen)
        erradas = (sum(a != b for a, b in zip(certo, previsto)) if certo and previsto
                   else 64 if certo else None)
        lado_dito = verdade.get("lado") in ("w", "b")
        detalhes.append({
            "id": verdade["id"], "casas_erradas": erradas,
            "fen_verificado": bool(verdade.get("fen_verificado")),
            "fen_igual_a_leitura": verdade["fen"] == verdade.get("fen_lido"),
            "lado_certo": (lido.lado == verdade["lado"]) if lado_dito else None,
            "lado_verificado": bool(verdade.get("lado_verificado")) and lado_dito,
            "confiavel": lido.confiavel})

    corpo = gabarito["linhas_corpo"]
    casados_c = casar(caixas_linhas, [ln["caixa_rel"] for ln in corpo])
    com_par = ({ip for ip, _ in casados_c}
               | {ip for ip, _ in casar(caixas_linhas, verd_margem)})
    sem_par = len(caixas_linhas) - len(com_par)

    por_verdade = {jv: ip for ip, jv in casados_c}
    ordem_do_bloco = {b["id"]: b.get("ordem") for b in gabarito["blocos"]}
    chave = {jv: (ordem_do_bloco.get(corpo[jv].get("bloco")), jv) for _, jv in casados_c}
    ordem_lida = [jv for ip, jv in sorted(casados_c)]
    ordem_certa = sorted(ordem_lida, key=lambda jv: (chave[jv][0] is None, chave[jv]))
    erros = caracteres = verificadas = 0
    for jv, linha in enumerate(corpo):
        if not linha.get("texto_verificado"):
            continue
        verificadas += 1
        previsto = leitura.linhas[por_verdade[jv]][1] if jv in por_verdade else ""
        erros += levenshtein(previsto, linha["texto"])
        caracteres += len(linha["texto"])
    return {
        "pagina_impressa": gabarito.get("pagina_impressa"),
        "estrutura": bool(gabarito.get("estrutura_por")),
        "estrutura_revisada": bool(gabarito.get("revisado_por")),
        "margens": margens,
        "diagramas": {"verdade": len(blocos_d), "achados": len(leitura.diagramas),
                      "casados": len(casados_d), "detalhes": detalhes},
        "negativa": bool(gabarito.get("negativa")),
        "linhas_sem_par": sem_par,
        "linhas_perdidas": len(corpo) - len(casados_c),
        "conferencia_cega_texto": _conferencia_em_dia(gabarito),
        "conferencia_cega_fen": any(fen_conferido_as_cegas(d) for d in gabarito["diagramas"]),
        "corpo": {"linhas": len(corpo), "casadas": len(casados_c),
                  "ordem_discordancia": round(discordancia(ordem_lida, ordem_certa), 4),
                  "linhas_verificadas": verificadas, "cer_erros": erros,
                  "cer_caracteres": caracteres,
                  "cer": round(erros / caracteres, 4) if caracteres else None}}


def fen_conferido_as_cegas(diagrama: dict) -> bool:
    """A conferência cega deu igual **ao FEN de hoje** (um FEN mudado depois não vale)."""
    cega = diagrama.get("conferencia_cega") or {}
    return bool(cega.get("igual")) and cega.get("fen", diagrama.get("fen")) == diagrama.get("fen")


def _conferencia_em_dia(gabarito: dict) -> bool:
    """A conferência cega do texto aprovada e feita sobre a versão atual do gabarito."""
    texto = gabarito.get("conferencia_cega", {}).get("texto", {})
    return bool(texto.get("aprovada")) and texto.get("verdade_versao") == gabarito.get(
        "verdade_versao")


def _razao(a, b):
    return round(a / b, 4) if b else None


def resumir(paginas: dict) -> dict:
    """A soma das páginas de `comparar_pagina`, com o estado da medida."""
    soma = lambda f: sum(f(p) for p in paginas.values())  # noqa: E731
    vp, fp, fn = (soma(lambda p, k=k: p["margens"][k]) for k in ("vp", "fp", "fn"))
    detalhes = [d for p in paginas.values() for d in p["diagramas"]["detalhes"]]
    fen_ok = [d for d in detalhes if d["fen_verificado"] and d["casas_erradas"] is not None]
    fen_todos = [d for d in detalhes if d["casas_erradas"] is not None]
    lado_ok = [d for d in detalhes if d["lado_verificado"]]
    lado_todos = [d for d in detalhes if d["lado_certo"] is not None]
    verdade_d = soma(lambda p: p["diagramas"]["verdade"])
    casados_d = soma(lambda p: p["diagramas"]["casados"])
    erros, caracteres = soma(lambda p: p["corpo"]["cer_erros"]), soma(
        lambda p: p["corpo"]["cer_caracteres"])
    revisadas = sum(1 for p in paginas.values() if p["estrutura_revisada"])
    verificadas = soma(lambda p: p["corpo"]["linhas_verificadas"])
    linhas = soma(lambda p: p["corpo"]["linhas"])
    pendencias = []
    if revisadas < len(paginas):
        pendencias.append(f"estrutura revisada em {revisadas}/{len(paginas)} páginas")
    if len(fen_ok) < len(fen_todos):
        pendencias.append(f"FEN conferido em {len(fen_ok)}/{len(fen_todos)} diagramas")
    if verificadas < linhas:
        pendencias.append(f"texto verificado em {verificadas}/{linhas} linhas")
    if not any(p["conferencia_cega_texto"] for p in paginas.values()):
        pendencias.append("sem conferência cega do texto aprovada e em dia")
    if fen_todos and not any(p["conferencia_cega_fen"] for p in paginas.values()):
        pendencias.append("sem conferência cega de FEN igual")
    return {
        "margens_precisao": _razao(vp, vp + fp),
        "margens_revocacao": _razao(vp, vp + fn),
        "diagramas_achados": f"{casados_d}/{verdade_d}",
        "diagramas_falsos": soma(lambda p: p["diagramas"]["achados"] - p["diagramas"]["casados"]),
        "linhas_sem_par": soma(lambda p: 0 if p["negativa"] else p["linhas_sem_par"]),
        "linhas_sem_par_negativas": soma(lambda p: p["linhas_sem_par"] if p["negativa"] else 0),
        "paginas_negativas": sum(1 for p in paginas.values() if p["negativa"]),
        "linhas_perdidas": soma(lambda p: 0 if p["negativa"] else p["linhas_perdidas"]),
        "linhas_perdidas_negativas": soma(lambda p: p["linhas_perdidas"] if p["negativa"] else 0),
        "fen_igual_a_leitura": f"{sum(d['fen_igual_a_leitura'] for d in detalhes)}/{len(detalhes)}",
        "fen_verificados": f"{len(fen_ok)}/{len(fen_todos)}",
        "casas_erradas_por_diagrama": _razao(sum(d["casas_erradas"] for d in fen_ok), len(fen_ok)),
        "casas_erradas_provisorio": _razao(sum(d["casas_erradas"] for d in fen_todos),
                                           len(fen_todos)),
        "lado_certo": f"{sum(d['lado_certo'] for d in lado_ok)}/{len(lado_ok)}",
        "lado_certo_provisorio": f"{sum(d['lado_certo'] for d in lado_todos)}/{len(lado_todos)}",
        "ordem_discordancia_media": round(
            soma(lambda p: p["corpo"]["ordem_discordancia"]) / max(len(paginas), 1), 4),
        "cer_corpo": _razao(erros, caracteres),
        "linhas_com_texto_verificado": f"{verificadas}/{linhas}",
        "estado": "válida" if not pendencias else "provisória: " + "; ".join(pendencias),
    }


# ----------------------------------------------------------------------
# A leitura das páginas
# ----------------------------------------------------------------------

def medir(livro: str, pdf: Path, indices) -> dict:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
        return _medir(livro, pdf, indices, Path(pasta))


def _medir(livro: str, pdf: Path, indices, pasta: Path) -> dict:
    from abbychess import exportar as ex
    from abbychess import livro as lv
    from abbychess import pagina as pg
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro

    gabaritos = {i: json.loads((VERDADE / livro / f"i{i:03d}.json").read_text(encoding="utf-8"))
                 for i in indices}
    sha = sha256_do_arquivo(pdf)
    for i, g in gabaritos.items():
        if g["pdf_sha256"] != sha:
            raise SystemExit(f"i{i:03d}: o PDF não é o do gabarito (pdf_sha256)")

    projeto = ProjetoDeLivro.criar(pasta, f"medir-{livro}", pdf)
    leitor = LeitorDoLivro.com_modelos_globais(projeto.pasta_de_padroes,
                                               limiares=projeto.dados.limiares)
    fonte = pg.fonte_do_projeto(projeto)
    inicio = time.perf_counter()
    lote = lv.reconhecer_paginas(projeto, fonte, leitor, indices)
    duracao = time.perf_counter() - inicio

    boxes = {i: [b for b in (projeto.carregar_pagina(i) or []) if b.char] for i in indices}
    alturas = {i: fonte.pagina(i).height for i in indices}
    larguras = {i: fonte.pagina(i).width for i in indices}
    tirados = ex.margens_corridas({i: (boxes[i], alturas[i]) for i in indices})

    paginas = {}
    for i in indices:
        angulo = fonte.inclinacao(i)
        rel = lambda caixa: _caixa_relativa(caixa, angulo, larguras[i], alturas[i])  # noqa: E731
        linhas = ex._linhas(boxes[i])
        caixas = [rel((min(boxes[i][k].x1 for k in ln.indices), ln.topo,
                       max(boxes[i][k].x2 for k in ln.indices), ln.pe)) for ln in linhas]
        # A poeira da borda, que a mesma regra tira, não conta: ela é `ignorar` no
        # gabarito e não é margem de ninguém.
        poeira = set(ex._margem_da_pagina(boxes[i], alturas[i]).poeira)
        margens = [c for c, ln in zip(caixas, linhas)
                   if set(ln.indices) & tirados[i] and not set(ln.indices) <= poeira]
        diagramas = [DiagramaDaLeitura(rel(d.caixa), d.fen or "", d.lado, d.confiavel)
                     for d in projeto.carregar_diagramas(i)]
        leitura = Leitura([(c, ln.texto) for c, ln in zip(caixas, linhas)], margens, diagramas)
        paginas[f"i{i:03d}"] = {**comparar_pagina(gabaritos[i], leitura),
                                "pendentes": lote.pendentes.get(i)}

    resumo = {**resumir(paginas), "lote_s": round(duracao, 1),
              "pendentes": sum(v for v in lote.pendentes.values())}
    return {"livro": livro, "indices": list(indices), "pdf_sha256": sha,
            "gabaritos": {f"i{i:03d}": {"verdade_versao": g.get("verdade_versao"),
                                         "sha256": _sha_do_gabarito(livro, i)}
                          for i, g in gabaritos.items()},
            "gabaritos_revisados": f"{sum(1 for p in paginas.values() if p['estrutura_revisada'])}"
                                   f"/{len(paginas)}",
            "nao_medido": NAO_MEDIDO, "resumo": resumo, "paginas": paginas}


def _sha_do_gabarito(livro: str, indice: int) -> str:
    return sha256_do_arquivo(VERDADE / livro / f"i{indice:03d}.json")


def main(argv=None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--livro", required=True)
    grupo = analisador.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--indices", help="índices do PDF, ex.: 20-26")
    grupo.add_argument("--paginas", help="páginas impressas, ex.: 21-27 (pelo gabarito)")
    analisador.add_argument("--pdf", type=Path, help="o PDF; por padrão, o do gabarito")
    args = analisador.parse_args(argv)

    disponiveis = {}
    for arquivo in sorted((VERDADE / args.livro).glob("i*.json")):
        g = json.loads(arquivo.read_text(encoding="utf-8"))
        disponiveis[g["indice_pdf"]] = g
    if args.indices:
        indices = _indices(args.indices)
        faltam = [i for i in indices if i not in disponiveis]
        if faltam:
            raise SystemExit(f"sem gabarito para os índices {faltam}")
    else:
        impressas = set(_indices(args.paginas))
        indices = sorted(i for i, g in disponiveis.items() if g.get("pagina_impressa") in impressas)
        if not indices:
            raise SystemExit("nenhum gabarito com essas páginas impressas (pagina_impressa vazio?)")
    pdf = args.pdf or next(PASTA_DOS_PDFS.rglob(disponiveis[indices[0]]["pdf"]), None)
    if pdf is None:
        raise SystemExit(f"o PDF {disponiveis[indices[0]]['pdf']!r} não está em "
                         f"{PASTA_DOS_PDFS}; passe --pdf ou defina ABBY_PASTA_DOS_PDFS")
    resultado = medir(args.livro, pdf, indices)
    resultado["data"] = datetime.date.today().isoformat()
    resultado.update(estado_do_git())
    MEDIDAS.mkdir(parents=True, exist_ok=True)
    destino = destino_da_medida(resultado["data"], f"qualidade-{args.livro}")
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
    print(json.dumps(resultado["resumo"], ensure_ascii=False, indent=1))
    print(destino.relative_to(RAIZ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
