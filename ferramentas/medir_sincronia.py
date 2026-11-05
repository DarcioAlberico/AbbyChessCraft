r"""A primeira pergunta sobre lance (PPL, item 4; SPEC da página perfeita, CA-X1.3, CA-F4.10, CA-F4.11).

    python ferramentas\medir_sincronia.py                  # as 7 páginas do Seirawan e as 4 do corpus_v2
    python ferramentas\medir_sincronia.py --so-gabarito    # sem ler: só o teto de cobertura
    python ferramentas\medir_sincronia.py --projeto X --livro seirawan   # CA-F4.10: depois da fila

Por livro:

- **Teto de cobertura, sem rebobinar:** no texto do gabarito, que fração dos tokens de lance tem
  posição conhecida, por página e por seguimento (a posição passa de uma página à seguinte). No
  `corpus_v2`, a referência não diz onde estão os diagramas: o teto ali é um piso, só com `1.`.
- **Sinal da legalidade,** na leitura do programa: a fração dos tokens de lance errados que dá
  ilegal, e a dos certos (o **alarme**). Sem rebobinar, é só linha principal.
- **Fora da fila (CA-F4.11):** os tokens de lance da verdade em linha fora da fila, e os errados.

**Exploratório:** o Seirawan já foi visto e o `corpus_v2` não foi auditado. Dimensiona o ponto de
parada do passo PPL, e não aprova alvo. O JSON não leva texto de livro. Carga: uma leitura.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))

from comum import destino_da_medida, estado_do_git  # noqa: E402

from abbychess import decodificador_de_lances as dl  # noqa: E402
from abbychess import texto as tx  # noqa: E402
from abbychess import tokens as tk  # noqa: E402

VERDADE = RAIZ / "tests" / "verdade"
CORPUS = {"aagaard": (("aagaard_calculation_p030",), "KQRBN"),
          "nunn": (("nunn_rook_endings_p237",), "KQRBN"),
          "yusupov": (("yusupov_evolution_1_p034", "yusupov_evolution_1_p047"), "KQRBN")}
INDICES_DO_SEIRAWAN = tuple(range(20, 27))
LETRAS_DO_SEIRAWAN = "pt"
METAS = {"teto": 0.30, "alarme": 0.05}


@dataclass(frozen=True)
class _Diagrama:
    id: str
    fen: str
    lido: bool = True


@dataclass
class PaginaDaVerdade:
    nome: str
    documento: tx.Documento
    diagramas: List[_Diagrama]
    linhas: List[str]


def documento_de_linhas(itens: Sequence) -> Tuple[tx.Documento, List[_Diagrama]]:
    """O `Documento` de uma lista: `str` é uma linha de texto; `_Diagrama`, o bloco dele."""
    gid, chars, blocos, diagramas = 0, {}, [], []
    for n, item in enumerate(itens):
        if isinstance(item, _Diagrama):
            diagramas.append(item)
            blocos.append(tx.Bloco(f"b{n}", None, "diagrama", (), item.id))
            continue
        palavras = []
        for palavra in item.split():
            gids = []
            for c in palavra:
                chars[gid] = c
                gids.append(gid)
                gid += 1
            palavras.append(tx.Palavra(tuple(gids)))
        blocos.append(tx.Bloco(f"b{n}", None, "texto", (tx.Linha(tuple(palavras)),)))
    return tx.Documento(tuple(blocos), chars), diagramas


def pagina_do_gabarito(g: dict, nome: str) -> PaginaDaVerdade:
    """A página de um gabarito de `tests/verdade`: as linhas de corpo e os diagramas, na ordem."""
    linhas_do_bloco: Dict[str, List[str]] = {}
    for linha in g.get("linhas_corpo", []):
        linhas_do_bloco.setdefault(linha["bloco"], []).append(linha["texto"])
    fens = {d["id"]: d.get("fen") for d in g.get("diagramas", [])}
    itens: List = []
    for bloco in sorted(g["blocos"], key=lambda b: b["ordem"]):
        if bloco["funcao"] == "diagrama" and fens.get(bloco["id"]):
            itens.append(_Diagrama(bloco["id"], fens[bloco["id"]]))
        elif bloco["funcao"] == "texto":
            itens.extend(linhas_do_bloco.get(bloco["id"], []))
    documento, diagramas = documento_de_linhas(itens)
    return PaginaDaVerdade(nome, documento, diagramas, [i for i in itens if isinstance(i, str)])


def pagina_de_referencia(texto: str, nome: str) -> PaginaDaVerdade:
    linhas = [ln for ln in texto.splitlines() if ln.strip()]
    documento, diagramas = documento_de_linhas(linhas)
    return PaginaDaVerdade(nome, documento, diagramas, linhas)


def teto_de_cobertura(paginas: Sequence[PaginaDaVerdade], letras: str) -> dict:
    """Os tokens com posição, por página e, com a posição passando à seguinte, por seguimento."""
    total = por_pagina = por_seguimento = 0
    longos = 0
    semente = None
    for pagina in paginas:
        sozinha = dl.decodificar(pagina.documento, pagina.diagramas, letras)
        seguida = dl.decodificar(pagina.documento, pagina.diagramas, letras, semente)
        semente = seguida.final
        total += len(sozinha.lances)
        por_pagina += sozinha.com_posicao
        por_seguimento += seguida.com_posicao
        longos += sum(tk.classificar_token(p, letras).forma_longa for ln in pagina.linhas
                      for p in ln.split())
    return {"tokens_de_lance": total, "com_posicao_por_pagina": por_pagina,
            "com_posicao_por_seguimento": por_seguimento,
            "cobertura_por_pagina": _razao(por_pagina, total),
            "cobertura_por_seguimento": _razao(por_seguimento, total),
            "lances_longos": longos}


def _razao(a: int, b: int) -> Optional[float]:
    return round(a / b, 4) if b else None


def _texto_da_linha(linha, documento, normal) -> str:
    return " ".join("".join(normal(documento.chars.get(g, "")) or tx.NAO_LIDO for g in p.gids)
                    for p in linha.palavras)


def linhas_lidas(documento) -> List[Tuple[str, Tuple[int, ...]]]:
    """(o texto, os gids) de cada linha de texto corrido do documento lido."""
    normal = tx.normalizador(tx.IMPRESSO)
    saida = []
    for _bloco, linha, _palavras in dl.palavras_de_texto(documento, "en"):
        saida.append((_texto_da_linha(linha, documento, normal),
                      tuple(g for p in linha.palavras for g in p.gids)))
    return saida


def sinal_na_leitura(verdade: Sequence[str], documento, diagramas, letras: str) -> dict:
    """Os tokens de lance da verdade contra a leitura, alinhados na página inteira (exploratório,
    SPEC §1): as quebras de linha da referência nem sempre são as do livro, e o alinhamento por
    linha contaria como erro o que só mudou de linha. Errados, marcados e fora da fila."""
    decodificada = dl.decodificar(documento, diagramas, letras)
    lidas = [(tk.normalizar(t, tk.SEMANTICA, letras), gids) for t, gids in linhas_lidas(documento)]
    lidas = [(t, gids) for t, gids in lidas if t]
    dono = [k for k, (t, _g) in enumerate(lidas) for _c in t + " "]
    na_fila = {g for ln in dl.linhas_da_fila(documento, letras) for g in ln.gids}
    conta = dict.fromkeys(("lances", "errados", "errados_de_forma_valida", "certos_marcados",
                           "errados_marcados", "fora_da_fila", "errados_fora_da_fila"), 0)
    for a in tk.avaliar_a_linha(" ".join(verdade), " ".join(t for t, _g in lidas), letras):
        if a.token.classe == tk.LANCE:
            gids = {g for j in a.indices_lidos for g in lidas[dono[j]][1]}
            marcados = {tk.normalizar(t.impresso, tk.SEMANTICA, letras)
                        for t in decodificada.ilegais if set(t.gids) & gids}
            lido = tk.classificar_token(a.lido, letras).nucleo
            _somar(conta, a, lido in marcados, not gids & na_fila, letras)
    conta.update(cobertura_da_leitura=_razao(decodificada.com_posicao, len(decodificada.lances)),
                 tokens_lidos=len(decodificada.lances), ilegais_lidos=len(decodificada.ilegais),
                 por_semente=decodificada.por_semente())
    return conta


def _somar(conta: dict, a, marcada: bool, fora: bool, letras: str) -> None:
    conta["lances"] += 1
    conta["fora_da_fila"] += fora
    if a.certo:
        conta["certos_marcados"] += marcada
        return
    conta["errados"] += 1
    conta["errados_marcados"] += marcada
    conta["errados_fora_da_fila"] += fora
    conta["errados_de_forma_valida"] += tk.classificar_token(a.lido, letras).classe == tk.LANCE


def ponto_de_parada(por_livro: Dict[str, dict]) -> dict:
    """O ponto de parada do passo PPL, item 4. Sem leitura, o alarme fica `None`."""
    teto = [max(v["teto"]["cobertura_por_pagina"] or 0, v["teto"]["cobertura_por_seguimento"] or 0)
            for v in por_livro.values() if v["teto"]["tokens_de_lance"]]
    lidos = [v["leitura"] for v in por_livro.values() if v.get("leitura")]
    certos = sum(v["lances"] - v["errados"] for v in lidos)
    marcados = sum(v["certos_marcados"] for v in lidos)
    alarme = _razao(marcados, certos) if lidos else None
    return {"teto_maximo": max(teto, default=None), "alarme": alarme, "metas": METAS,
            "x1_liberado": bool(teto) and max(teto) >= METAS["teto"]
            and (alarme is None or alarme < METAS["alarme"])}


def _ler_paginas(fonte: Path, indices: Sequence[int], letras: str) -> List[Tuple[tx.Documento, list]]:
    from abbychess import diagramas as dg
    from abbychess import livro as lv
    from abbychess import pagina as pg
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
        projeto = ProjetoDeLivro.criar(pasta, "sincronia", fonte)
        projeto.dados.letras_das_pecas = letras if len(letras) == 5 else ""
        leitor = LeitorDoLivro.com_modelos_globais(projeto.pasta_de_padroes,
                                                   limiares=projeto.dados.limiares)
        lv.reconhecer_paginas(projeto, pg.fonte_do_projeto(projeto), leitor, indices)
        saida = []
        for i in indices:
            modelo = projeto.carregar_modelo(i)
            saida.append((tx.montar(modelo), dg.com_ids(list(modelo.diagramas))))
        projeto.fechar()
    return saida


def _seirawan(ler: bool) -> dict:
    from rotular import PASTA_DOS_PDFS

    gabaritos = {i: json.loads((VERDADE / "xv" / f"i{i:03d}.json").read_text(encoding="utf-8"))
                 for i in INDICES_DO_SEIRAWAN}
    paginas = [pagina_do_gabarito(g, f"i{i:03d}") for i, g in gabaritos.items()]
    livro = {"paginas": len(paginas), "gabarito_auditado": False,
             "teto": teto_de_cobertura(paginas, LETRAS_DO_SEIRAWAN)}
    if ler:
        pdf = next(PASTA_DOS_PDFS.rglob(gabaritos[INDICES_DO_SEIRAWAN[0]]["pdf"]))
        lidas = _ler_paginas(pdf, INDICES_DO_SEIRAWAN, LETRAS_DO_SEIRAWAN)
        livro["leitura"] = _somar_os_sinais(
            sinal_na_leitura(p.linhas, doc, dgs, LETRAS_DO_SEIRAWAN)
            for p, (doc, dgs) in zip(paginas, lidas))
    return livro


def _corpus(pasta: Path, livro: str, nomes: Sequence[str], letras: str, ler: bool) -> dict:
    paginas = [pagina_de_referencia((pasta / "references" / f"{n}.txt").read_text(encoding="utf-8"), n)
               for n in nomes]
    saida = {"paginas": len(paginas), "gabarito_auditado": False,
             "teto": teto_de_cobertura(paginas, letras),
             "teto_e_piso": "a referência não traz os diagramas"}
    if ler:
        sinais = []
        for pagina in paginas:
            [(doc, dgs)] = _ler_paginas(pasta / "images" / f"{pagina.nome}.png", [0], letras)
            sinais.append(sinal_na_leitura(pagina.linhas, doc, dgs, letras))
        saida["leitura"] = _somar_os_sinais(sinais)
    return saida


def _somar_os_sinais(sinais) -> dict:
    total: dict = {}
    sementes: Dict[str, int] = {}
    com_posicao = lidos = 0
    for s in sinais:
        for chave, valor in s.items():
            if isinstance(valor, int) and not isinstance(valor, bool):
                total[chave] = total.get(chave, 0) + valor
        for chave, valor in s["por_semente"].items():
            sementes[chave] = sementes.get(chave, 0) + valor
        lidos += s["tokens_lidos"]
        com_posicao += round((s["cobertura_da_leitura"] or 0) * s["tokens_lidos"])
    total["por_semente"] = sementes
    total["cobertura_da_leitura"] = _razao(com_posicao, lidos)
    return total


def do_projeto(pasta: Path, livro: str, corpus: Path) -> dict:
    """CA-F4.10: os tokens errados de um projeto já revisado, contra o gabarito: as páginas do
    Seirawan pelo índice do PDF, as do `corpus_v2` na ordem da referência. Só leitura."""
    from abbychess import diagramas as dg
    from abbychess.projeto import ProjetoDeLivro

    if livro == "seirawan":
        paginas = [pagina_do_gabarito(json.loads((VERDADE / "xv" / f"i{i:03d}.json").read_text(
            encoding="utf-8")), f"i{i:03d}") for i in INDICES_DO_SEIRAWAN]
        indices, letras = list(INDICES_DO_SEIRAWAN), LETRAS_DO_SEIRAWAN
    else:
        nomes, letras = CORPUS[livro]
        paginas = [pagina_de_referencia((corpus / "references" / f"{n}.txt").read_text(
            encoding="utf-8"), n) for n in nomes]
        indices = list(range(len(nomes)))
    projeto = ProjetoDeLivro.abrir(pasta)
    try:
        sinais = []
        for pagina, i in zip(paginas, indices):
            modelo = projeto.ler_sem_migrar(i)
            sinais.append(sinal_na_leitura(pagina.linhas, tx.montar(modelo),
                                           dg.com_ids(list(modelo.diagramas)), letras))
    finally:
        projeto.fechar()
    return _somar_os_sinais(sinais)


def main(argv=None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--so-gabarito", action="store_true")
    analisador.add_argument("--projeto", type=Path, help="CA-F4.10: um projeto já revisado")
    analisador.add_argument("--livro", choices=["seirawan", *CORPUS], default="seirawan")
    args = analisador.parse_args(argv)
    ler = not args.so_gabarito
    import core

    corpus = Path(core.__file__).resolve().parent.parent / "benchmarks" / "corpus_v2"
    if args.projeto:
        print(json.dumps(do_projeto(args.projeto, args.livro, corpus), ensure_ascii=False, indent=1))
        return 0
    por_livro = {"seirawan": _seirawan(ler)}
    for livro, (nomes, letras) in CORPUS.items():
        por_livro[livro] = _corpus(corpus, livro, nomes, letras, ler)
    resultado = {"por_livro": por_livro, "ponto_de_parada": ponto_de_parada(por_livro),
                 "data": datetime.date.today().isoformat(), **estado_do_git(),
                 "exploratorio": "Seirawan já visto; corpus_v2 sem auditoria: não aprova alvo"}
    destino = destino_da_medida(resultado["data"], "sincronia")
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
    print(json.dumps(resultado["ponto_de_parada"], ensure_ascii=False, indent=1))
    print(destino.relative_to(RAIZ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
