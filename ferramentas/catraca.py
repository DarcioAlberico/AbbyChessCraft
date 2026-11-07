r"""A catraca do portão (R-3, SPEC da página perfeita §3.3): as 7 páginas de texto do Seirawan,
com a rede carregada, contra a referência em `docs/medidas/catraca-xv.json`. É regressão: não
aprova nada, e por isso não pede auditoria do gabarito.

    python ferramentas\catraca.py                # mede e compara com a referência
    python ferramentas\catraca.py --gravar       # mede e grava a referência (na primeira vez)
    python ferramentas\catraca.py --remedir      # a chave mudou: ver `remedir`

A referência vale para uma **chave**: o SHA dos gabaritos, o do modelo, o commit do core e a
versão da normalização. Mudou a chave, comparar não vale: `--remedir` mede de novo o commit da
referência sobre a chave nova, numa worktree temporária, e compara só essas duas (CA-R3.3).
Passar da tolerância pede registro no commit, com o ganho que o justifica. Carga: ~70 s por
medida, uma por vez. O JSON não leva texto de livro.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))

REFERENCIA = RAIZ / "docs" / "medidas" / "catraca-xv.json"
LIVRO = "xv"
INDICES = tuple(range(20, 27))
#: Sobe quando `normalizar` muda (PPL, `abbychess/tokens.py`).
VERSAO_DA_NORMALIZACAO = 1
#: Quantos erros a mais no corpo a medida tolera; em casas e em linhas perdidas, nenhum.
TOLERANCIA_DE_ERROS = 2


def numeros(resultado: dict) -> dict:
    """O que a catraca vigia, do JSON de `medir.medir`. O tempo fica de fora: CA-R3.5."""
    paginas = resultado["paginas"].values()
    detalhes = [d for p in paginas for d in p["diagramas"]["detalhes"]
                if d["casas_erradas"] is not None]
    return {
        "cer_erros": sum(p["corpo"]["cer_erros"] for p in paginas),
        "cer_caracteres": sum(p["corpo"]["cer_caracteres"] for p in paginas),
        "cer_corpo": resultado["resumo"]["cer_corpo"],
        "casas_erradas": sum(d["casas_erradas"] for d in detalhes),
        "diagramas_casados": sum(p["diagramas"]["casados"] for p in paginas),
        "diagramas_falsos": resultado["resumo"]["diagramas_falsos"],
        "linhas_perdidas": resultado["resumo"]["linhas_perdidas"],
        "linhas_sem_par": resultado["resumo"]["linhas_sem_par"],
        "pendentes": resultado["resumo"]["pendentes"],
    }


def violacoes(referencia: dict, medida: dict) -> List[str]:
    """O que piorou além da tolerância; vazio passa."""
    saida = []
    if medida["cer_erros"] > referencia["cer_erros"] + TOLERANCIA_DE_ERROS:
        saida.append(f"o corpo tem {medida['cer_erros']} erros; a referência tem "
                     f"{referencia['cer_erros']}, com tolerância de {TOLERANCIA_DE_ERROS}")
    if medida["casas_erradas"] > referencia["casas_erradas"]:
        saida.append(f"{medida['casas_erradas']} casas erradas; a referência tem "
                     f"{referencia['casas_erradas']}")
    if medida["linhas_perdidas"] > referencia["linhas_perdidas"]:
        saida.append(f"{medida['linhas_perdidas']} linhas perdidas; a referência tem "
                     f"{referencia['linhas_perdidas']}")
    if medida["diagramas_casados"] < referencia["diagramas_casados"]:
        saida.append(f"{medida['diagramas_casados']} diagramas achados; a referência tem "
                     f"{referencia['diagramas_casados']}")
    return saida


def falta_o_modelo(estado_do_leitor: dict) -> Optional[str]:
    """CA-R3.1: sem a rede ou sem a base global, a medida não vale, e o portão reprova."""
    if not estado_do_leitor.get("rede"):
        return "a rede não carregou (falta o custom_model.pth)"
    if not estado_do_leitor.get("base"):
        return "a base global não carregou (falta training_data)"
    return None


def _sha(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for pedaco in iter(lambda: arquivo.read(1 << 20), b""):
            resumo.update(pedaco)
    return resumo.hexdigest()


def _raiz_do_core() -> Path:
    import core

    return Path(core.__file__).resolve().parent.parent


def chave(raiz_da_verdade: Path = RAIZ / "tests" / "verdade") -> dict:
    """O que torna duas medidas comparáveis."""
    gabaritos = hashlib.sha256()
    for indice in INDICES:
        gabaritos.update(_sha(raiz_da_verdade / LIVRO / f"i{indice:03d}.json").encode())
    core = _raiz_do_core()
    modelo = core / "custom_model.pth"
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=core, capture_output=True,
                            text=True).stdout.strip()
    return {"gabaritos": gabaritos.hexdigest(),
            "modelo": _sha(modelo) if modelo.is_file() else None,
            "core": commit or None, "normalizacao": VERSAO_DA_NORMALIZACAO}


def estado_do_leitor_global() -> dict:
    from abbychess import servidor_de_leitura as sl
    from abbychess.dados_do_projeto import Limiares

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
        return sl.estado_do_leitor(sl.leitor_global(Path(pasta), Limiares()))


def medir_agora() -> dict:
    """Mede as 7 páginas, e devolve os números e a chave."""
    from medir import medir
    from rotular import PASTA_DOS_PDFS, VERDADE

    gabarito = json.loads((VERDADE / LIVRO / f"i{INDICES[0]:03d}.json").read_text(encoding="utf-8"))
    pdf = next(PASTA_DOS_PDFS.rglob(gabarito["pdf"]), None)
    if pdf is None:
        raise SystemExit(f"o PDF {gabarito['pdf']!r} não está em {PASTA_DOS_PDFS}")
    resultado = medir(LIVRO, pdf, list(INDICES))
    return {"chave": chave(VERDADE), "numeros": numeros(resultado)}


def gravar(referencia: dict, destino: Path = REFERENCIA, commit: Optional[str] = None) -> None:
    from comum import estado_do_git

    corpo = {**referencia, "indices": list(INDICES),
             "commit": commit or estado_do_git()["commit"]}
    destino.write_text(json.dumps(corpo, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")


def remedir(referencia: dict) -> dict:
    """O commit da referência medido sobre a chave de agora (os gabaritos de agora, o core e o
    modelo são os instalados): numa worktree temporária, que sai no fim."""
    pasta = Path(tempfile.mkdtemp(prefix="catraca-"))
    arvore = pasta / "arvore"
    subprocess.run(["git", "worktree", "add", "--detach", str(arvore), referencia["commit"]],
                   cwd=RAIZ, check=True, capture_output=True)
    try:
        shutil.copytree(RAIZ / "tests" / "verdade", arvore / "tests" / "verdade",
                        dirs_exist_ok=True)
        shutil.copy2(Path(__file__), arvore / "ferramentas" / "catraca.py")
        saida = pasta / "medida.json"
        ambiente = dict(os.environ, PYTHONPATH=str(arvore), PYTHONIOENCODING="utf-8")
        subprocess.run([sys.executable, str(arvore / "ferramentas" / "catraca.py"),
                        "--medir-para", str(saida)], cwd=arvore, env=ambiente, check=True)
        return json.loads(saida.read_text(encoding="utf-8"))
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(arvore)], cwd=RAIZ,
                       capture_output=True)
        shutil.rmtree(pasta, ignore_errors=True)


def main(argv=None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--gravar", action="store_true")
    analisador.add_argument("--remedir", action="store_true")
    analisador.add_argument("--medir-para", type=Path, help=argparse.SUPPRESS)
    args = analisador.parse_args(argv)

    if args.medir_para:
        args.medir_para.write_text(json.dumps(medir_agora(), ensure_ascii=False), encoding="utf-8")
        return 0
    falta = falta_o_modelo(estado_do_leitor_global())
    if falta:
        print(f"catraca: {falta}")
        return 1
    if args.remedir:
        antiga = json.loads(REFERENCIA.read_text(encoding="utf-8"))
        referencia = remedir(antiga)
        agora = medir_agora()
        ruins = violacoes(referencia["numeros"], agora["numeros"])
        print(json.dumps({"referencia": referencia, "agora": agora, "violacoes": ruins},
                         ensure_ascii=False, indent=1))
        if not ruins:
            gravar(agora)
        return 1 if ruins else 0
    agora = medir_agora()
    if args.gravar:
        gravar(agora)
        print(json.dumps(agora, ensure_ascii=False, indent=1))
        return 0
    referencia = json.loads(REFERENCIA.read_text(encoding="utf-8"))
    if referencia["chave"] != agora["chave"]:
        print("catraca: a chave mudou: rode --remedir")
        return 1
    ruins = violacoes(referencia["numeros"], agora["numeros"])
    print(json.dumps({"agora": agora["numeros"], "violacoes": ruins}, ensure_ascii=False, indent=1))
    return 1 if ruins else 0


if __name__ == "__main__":
    sys.exit(main())
