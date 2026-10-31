r"""A exportação medida (SPEC §12, passo J): o tempo, os mesmos bytes e os validadores.

    .venv\Scripts\python.exe ferramentas\medir_exportacao.py [--livro xv]

Lê as páginas da fatia (as p. 21–27 do Xadrez Vitorioso, as do protocolo da fatia) num
projeto novo, com os modelos globais (o que um usuário novo tem), e exporta em cada formato:

- **o tempo** pelo método da §15.3 (5 aquecimentos, 30 repetições, p50 e p95);
- **os mesmos bytes** (CA-12.6): duas exportações com o mesmo `SOURCE_DATE_EPOCH`;
- **o EPUB nos validadores**: o EPUBCheck (`ABBY_EPUBCHECK`), o Ace by DAISY (`ABBY_ACE`) e o
  Calibre (`ABBY_CALIBRE`); o que não estiver configurado sai `null`, não aprovado;
- **o relatório** de cada formato (o resumo, os capítulos e os títulos do sumário).

Grava `docs/medidas/AAAA-MM-DD-exportacao-<livro>.json`. O projeto fica numa pasta
temporária, que sai no fim; nada é gravado na base global do PyBoxEditor.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))

from comum import MEDIDAS, PASTA_DOS_PDFS, destino_da_medida, estado_do_git  # noqa: E402

FORMATOS = ("epub", "docx", "txt", "pgn", "pdf")
AQUECIMENTOS = 5
REPETICOES = 30
EPOCA = "1700000000"


#: As páginas da fatia (o protocolo, docs/medidas/protocolo-fatia.md): índices a partir de 0.
FATIA = {"xv": range(20, 27)}


def _indices_e_pdf(livro: str):
    gabarito = RAIZ / "tests" / "verdade" / livro / f"i{FATIA[livro][0]:03d}.json"
    nome = json.loads(gabarito.read_text(encoding="utf-8"))["pdf"]
    pdf = next(PASTA_DOS_PDFS.rglob(nome), None)
    if pdf is None:
        raise SystemExit(f"PDF não encontrado em {PASTA_DOS_PDFS}: {nome}")
    return list(FATIA[livro]), pdf


def _percentil(valores, q: float) -> float:
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, int(round(q * (len(ordenados) - 1))))]


def _sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def medir(livro: str) -> dict:
    from abbychess import exportar as ex
    from abbychess import epub
    from abbychess import livro as lv
    from abbychess import pagina as pg
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro

    indices, pdf = _indices_e_pdf(livro)
    os.environ["SOURCE_DATE_EPOCH"] = EPOCA
    with tempfile.TemporaryDirectory(prefix="abby-exportacao-", ignore_cleanup_errors=True) as p:
        pasta = Path(p)
        projeto = ProjetoDeLivro.criar(pasta / "livros", f"Exportação {livro}", pdf)
        leitor = LeitorDoLivro.com_modelos_globais(projeto.pasta_de_padroes,
                                                   limiares=projeto.dados.limiares)
        inicio = time.perf_counter()
        lv.reconhecer_paginas(projeto, pg.fonte_do_projeto(projeto), leitor, indices)
        leitura_s = round(time.perf_counter() - inicio, 1)
        formatos = {}
        for formato in FORMATOS:
            destino = pasta / f"livro.{formato}"
            tempos = []
            resumo = relatorio = None
            for i in range(AQUECIMENTOS + REPETICOES):
                inicio = time.perf_counter_ns()
                resumo, relatorio = ex.exportar_com_relatorio(projeto, destino)
                if i >= AQUECIMENTOS:
                    tempos.append((time.perf_counter_ns() - inicio) / 1e6)
            primeira = _sha(destino)
            ex.exportar_com_relatorio(projeto, pasta / f"outra.{formato}")
            dados = {
                "tempo": {"p50_ms": round(_percentil(tempos, 0.5), 1),
                          "p95_ms": round(_percentil(tempos, 0.95), 1),
                          "max_ms": round(max(tempos), 1), "n": len(tempos),
                          "aquecimentos": AQUECIMENTOS},
                "bytes": destino.stat().st_size,
                "mesmos_bytes": primeira == _sha(pasta / f"outra.{formato}"),
                "resumo": resumo,
                "capitulos": relatorio.capitulos,
                "titulos": len(relatorio.titulos),
                "desenhados": relatorio.desenhados,
                "recortados": len(relatorio.recortados),
                "no_pgn": relatorio.no_pgn,
                "palavras_sinalizadas": sum(relatorio.sinalizadas.values()),
                # O EPUB que não passa nela nem é gravado (SPEC-qualidade Q-E3): aqui, [].
                "problemas_do_arquivo": epub.conferir(destino) if formato == "epub" else [],
            }
            if formato == "epub":
                dados["epubcheck"] = epub.epubcheck(destino)
                dados["ace"] = epub.ace(destino)
                dados["calibre"] = epub.calibre(destino)
            formatos[formato] = dados
            print(formato, dados["tempo"], "mesmos bytes:", dados["mesmos_bytes"], flush=True)
        projeto.paginas_em_memoria.descarregar(30)
    validadores = {nome: formatos["epub"][nome] for nome in ("epubcheck", "ace", "calibre")}
    return {
        "livro": livro, "paginas": [i + 1 for i in indices], "pdf": pdf.name,
        "leitura_da_fatia_s": leitura_s, "modelos": "globais (projeto novo, sem padrões)",
        "metodo": f"§15.3: {AQUECIMENTOS} aquecimentos, {REPETICOES} repetições; os mesmos "
                  f"bytes com SOURCE_DATE_EPOCH={EPOCA}",
        "formatos": formatos,
        "epub_aprovado": all(v == [] for v in validadores.values()),
        "validadores_ausentes": [n for n, v in validadores.items() if v is None],
        "todos_com_os_mesmos_bytes": all(d["mesmos_bytes"] for d in formatos.values()),
    }


def main(argv=None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--livro", default="xv", choices=sorted(FATIA))
    args = analisador.parse_args(argv)
    resultado = {"data": datetime.date.today().isoformat(), **estado_do_git(),
                 **medir(args.livro)}
    MEDIDAS.mkdir(parents=True, exist_ok=True)
    destino = destino_da_medida(resultado["data"], f"exportacao-{args.livro}")
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
    print(destino)
    print(json.dumps({k: resultado[k] for k in ("epub_aprovado", "validadores_ausentes",
                                                "todos_com_os_mesmos_bytes")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
