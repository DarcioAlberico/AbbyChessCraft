"""A mutação de um módulo (SPEC-qualidade §9, CA-Q-M1): cada mutante troca uma coisa só no
código (um operador, uma constante, uma condição), e um teste que reprova o mata.

    python ferramentas/mutador.py abbychess/modelo.py [--testes T ...] [--trabalhadores 4]
        [--tempo-por-mutante 120] [--ate-minutos 9] [--continuar] [--saida PASTA] [--raiz R]

- Os testes: os que importam o módulo (`--testes` os troca). Uma rodada com a cobertura por
  teste (`--cov-context=test`) diz quais passam por cada linha; cada mutante roda só esses,
  com `-x` (o primeiro que reprova basta).
- Cada trabalhador tem a sua cópia do projeto numa pasta temporária: a worktree nunca fica com
  um módulo mutado, e dois mutantes não se pisam. Sem bytecode gravado (`PYTHONDONTWRITEBYTECODE`),
  para o `.pyc` de um mutante não valer no outro. O teto da suíte rápida (`tests/conftest.py`)
  fica desligado: passar dele não é reprovar.
- O resultado de cada mutante: `morto` (um teste reprovou, ou o módulo nem importou), `tempo`
  (estourou `--tempo-por-mutante`: entrou em laço; conta como morto), `sobreviveu` (todos
  passaram) ou `sem_teste` (nenhum teste passa pela linha; conta como sobrevivente).
- Grava `<saida>/<módulo>-<commit>.json` a cada mutante: com `--continuar` a medida segue de
  onde parou (se o módulo não mudou), e `--ate-minutos` a para antes, para caber numa rodada.

Carga pesada: nada mais rodando, `--trabalhadores` no máximo 4.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tokenize
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

COMPARACOES = {ast.Lt: "<=", ast.LtE: "<", ast.Gt: ">=", ast.GtE: ">", ast.Eq: "!=",
               ast.NotEq: "==", ast.In: "not in", ast.NotIn: "in", ast.Is: "is not",
               ast.IsNot: "is"}
TEXTO_DA_COMPARACAO = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==",
                       ast.NotEq: "!=", ast.In: "in", ast.NotIn: "not in", ast.Is: "is",
                       ast.IsNot: "is not"}
ARITMETICOS = {ast.Add: ("+", "-"), ast.Sub: ("-", "+"), ast.Mult: ("*", "/"),
               ast.Div: ("/", "*"), ast.FloorDiv: ("//", "/"), ast.Mod: ("%", "//")}
IGNORAR_NA_COPIA = shutil.ignore_patterns(".git", "__pycache__", ".hypothesis", ".ruff_cache",
                                          ".pytest_cache", ".coverage*", "*.pyc")


@dataclass(frozen=True)
class Mutante:
    """Uma troca no texto do módulo: `fonte[inicio:fim]` vira `troca`."""

    linha: int
    fim_linha: int
    inicio: int
    fim: int
    tipo: str
    original: str
    troca: str

    def aplicar(self, fonte: str) -> str:
        return fonte[:self.inicio] + self.troca + fonte[self.fim:]


class _Texto:
    """As posições do módulo: o AST conta a coluna em bytes de UTF-8, o texto em caracteres."""

    def __init__(self, fonte: str):
        self.fonte = fonte
        # Só o \n parte a linha, como no Python (o str.splitlines parte também no U+2029).
        self.linhas = re.findall(r"[^\n]*\n|[^\n]+$", fonte)
        self.comeco = [0]
        for linha in self.linhas:
            self.comeco.append(self.comeco[-1] + len(linha))
        self.tokens = [(self.posicao_char(*t.start), self.posicao_char(*t.end), t.string)
                       for t in tokenize.generate_tokens(io.StringIO(fonte).readline)
                       if t.type in (tokenize.OP, tokenize.NAME)]

    def posicao_char(self, linha: int, coluna: int) -> int:
        return self.comeco[linha - 1] + coluna

    def posicao(self, linha: int, coluna_em_bytes: int) -> int:
        texto = self.linhas[linha - 1].encode("utf-8")[:coluna_em_bytes].decode("utf-8")
        return self.comeco[linha - 1] + len(texto)

    def inicio(self, no) -> int:
        return self.posicao(no.lineno, no.col_offset)

    def fim(self, no) -> int:
        return self.posicao(no.end_lineno, no.end_col_offset)

    def operador_entre(self, a: int, b: int, texto: str):
        """(início, fim) do operador `texto` (um ou dois tokens) entre as posições a e b."""
        dentro = [t for t in self.tokens if a <= t[0] and t[1] <= b and t[2] not in "()"]
        partes = texto.split()
        for k in range(len(dentro) - len(partes) + 1):
            if [t[2] for t in dentro[k:k + len(partes)]] == partes:
                return dentro[k][0], dentro[k + len(partes) - 1][1]
        return None

    def linha_de(self, posicao: int) -> int:
        return next(k for k in range(1, len(self.comeco)) if posicao < self.comeco[k])


def mutantes(fonte: str) -> List[Mutante]:
    """Os mutantes do módulo, na ordem do texto."""
    texto = _Texto(fonte)
    saida: List[Mutante] = []

    def trocar(inicio: int, fim: int, tipo: str, troca: str) -> None:
        saida.append(Mutante(texto.linha_de(inicio), texto.linha_de(max(inicio, fim - 1)),
                             inicio, fim, tipo, fonte[inicio:fim], troca))

    def operador(a, b, original: str, troca: str, tipo: str) -> None:
        lugar = texto.operador_entre(texto.fim(a), texto.inicio(b), original)
        if lugar is not None:
            trocar(*lugar, tipo, troca)

    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.Compare):
            for esquerda, op, direita in zip([no.left, *no.comparators], no.ops, no.comparators):
                operador(esquerda, direita, TEXTO_DA_COMPARACAO[type(op)],
                         COMPARACOES[type(op)], "comparação")
        elif isinstance(no, ast.BinOp) and type(no.op) in ARITMETICOS:
            original, troca = ARITMETICOS[type(no.op)]
            operador(no.left, no.right, original, troca, "aritmético")
        elif isinstance(no, ast.AugAssign) and type(no.op) in ARITMETICOS:
            original, troca = ARITMETICOS[type(no.op)]
            operador(no.target, no.value, original + "=", troca + "=", "atribuição")
        elif isinstance(no, ast.BoolOp):
            original, troca = ("and", "or") if isinstance(no.op, ast.And) else ("or", "and")
            for a, b in zip(no.values, no.values[1:]):
                operador(a, b, original, troca, "lógico")
        elif isinstance(no, ast.UnaryOp) and isinstance(no.op, ast.Not):
            depois_do_not = texto.operador_entre(texto.inicio(no), texto.fim(no), "not")[1]
            resto = fonte[depois_do_not:texto.fim(no)].lstrip()
            trocar(texto.inicio(no), texto.fim(no), "not tirado", resto)
        elif isinstance(no, (ast.If, ast.While)) and not (
                isinstance(no.test, ast.UnaryOp) and isinstance(no.test.op, ast.Not)):
            inicio, fim = texto.inicio(no.test), texto.fim(no.test)
            trocar(inicio, fim, "condição negada", f"not ({fonte[inicio:fim]})")
        elif isinstance(no, ast.Constant) and isinstance(no.value, bool):
            trocar(texto.inicio(no), texto.fim(no), "constante", str(not no.value))
        elif isinstance(no, ast.Constant) and type(no.value) is int:
            trocar(texto.inicio(no), texto.fim(no), "constante", str(no.value + 1))
        elif isinstance(no, (ast.Break, ast.Continue)):
            troca = "continue" if isinstance(no, ast.Break) else "break"
            trocar(texto.inicio(no), texto.fim(no), "laço", troca)
    return sorted(saida, key=lambda m: (m.inicio, m.fim, m.troca))


def classificar(codigo: Optional[int], estourou: bool, saida: str = "") -> str:
    """O resultado de um mutante pelo código de saída do pytest (e pela `saida` dele: o conftest
    que importa o módulo cai com o mutante que nem importa, e o pytest sai com 4, como num erro
    de uso; a rodada sem mutante já provou que o conftest carrega)."""
    if estourou:
        return "tempo"
    if codigo == 0:
        return "sobreviveu"
    if codigo in (1, 2, 3):                 # reprovou, a coleta caiu, ou o pytest caiu no mutante
        return "morto"
    if codigo == 4 and "ImportError while loading conftest" in saida:
        return "morto"
    raise RuntimeError(f"o pytest saiu com {codigo}: o erro é do mutador, não do mutante")


def testes_do_mutante(contextos: Dict[int, List[str]], m: Mutante, todos: List[str]) -> List[str]:
    """Os testes (o nodeid) que passam pelas linhas do mutante. A linha que só roda ao importar
    o módulo (a constante, o valor padrão da dataclass) tem o contexto vazio, porque o pytest
    importa na coleta, fora de teste nenhum: ela vale para `todos` os testes do módulo, também
    quando um teste o importa de novo e a linha roda dentro dele."""
    nomes = {c.split("|", 1)[0] for linha in range(m.linha, m.fim_linha + 1)
             for c in contextos.get(linha, ())}
    if "" in nomes:
        return list(todos)
    return sorted(n for n in nomes if n)


def resumo(resultados: List[str]) -> dict:
    """A contagem: o tempo conta como morto, o sem teste como sobrevivente."""
    mortos = sum(r in ("morto", "tempo") for r in resultados)
    total = len(resultados)
    return {"mutantes": total, "mortos": mortos,
            "sobreviventes": sum(r == "sobreviveu" for r in resultados),
            "sem_teste": sum(r == "sem_teste" for r in resultados),
            "percentual": round(100 * mortos / total, 1) if total else 0.0}


# ----------------------------------------------------------------------
# A medida: as cópias, a cobertura por teste e os mutantes
# ----------------------------------------------------------------------

def testes_que_importam(raiz: Path, modulo: Path) -> List[str]:
    """Os arquivos de teste que importam o módulo, em qualquer forma."""
    pacote, nome = ".".join(modulo.parent.parts), modulo.stem
    pontuado = f"{pacote}.{nome}" if pacote else nome
    saida = []
    for arquivo in sorted((raiz / "tests").glob("test_*.py")):
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if (isinstance(no, ast.ImportFrom) and (no.module == pontuado or (
                    no.module == pacote and any(a.name == nome for a in no.names)))) or (
                    isinstance(no, ast.Import) and any(a.name == pontuado for a in no.names)):
                saida.append(arquivo.relative_to(raiz).as_posix())
                break
    return saida


def _ambiente(copia: Path, **mais) -> dict:
    return dict(os.environ, PYTHONPATH=str(copia), PYTHONDONTWRITEBYTECODE="1",
                ABBY_TETO_DA_RAPIDA_S="1000000", **mais)


def argumentos_do_pytest(marcas: Optional[str]) -> List[str]:
    """Os argumentos das duas rodadas, a da cobertura e a de cada mutante: sem `marcas`, as
    camadas do `addopts` do pyproject (a suíte rápida); com elas, a expressão `-m` delas."""
    return ["-q", "-p", "no:cacheprovider", *(["-m", marcas] if marcas else [])]


def cobertura_por_teste(copia: Path, modulo: Path, testes: List[str], trabalhadores: int,
                        marcas: Optional[str] = None):
    """Linha -> os contextos (`nodeid|fase`) que passam por ela, de uma rodada sem mutante."""
    import coverage

    arquivo = copia / ".coverage.mutador"
    pontuado = ".".join(modulo.with_suffix("").parts)
    comando = [sys.executable, "-m", "pytest", *argumentos_do_pytest(marcas),
               f"--cov={pontuado}", "--cov-context=test", "--cov-report=",
               *(["-n", str(trabalhadores)] if trabalhadores > 1 else []), *testes]
    rodada = subprocess.run(comando, cwd=copia, capture_output=True,
                            env=_ambiente(copia, COVERAGE_FILE=str(arquivo)))
    if rodada.returncode != 0:
        raise SystemExit("os testes não passam sem mutante:\n"
                         + rodada.stdout.decode("utf-8", "replace")[-3000:])
    dados = coverage.CoverageData(basename=str(arquivo))
    dados.read()
    alvo = (copia / modulo).resolve()
    medido = next((f for f in dados.measured_files() if Path(f).resolve() == alvo), None)
    return {} if medido is None else dados.contexts_by_lineno(medido)


def _rodar_mutante(copia: Path, modulo: Path, fonte: str, m: Mutante, testes: List[str],
                   limite: float, marcas: Optional[str] = None) -> str:
    """Põe o mutante na cópia, roda os testes dele e devolve o módulo de volta."""
    caminho = copia / modulo
    argumentos = copia / ".testes-do-mutante.txt"
    argumentos.write_text("\n".join(testes) + "\n", encoding="utf-8")
    caminho.write_text(m.aplicar(fonte), encoding="utf-8", newline="")
    rodada = subprocess.Popen([sys.executable, "-m", "pytest", "-x", *argumentos_do_pytest(marcas),
                               f"@{argumentos.name}"], cwd=copia, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, env=_ambiente(copia))
    try:
        saida, _ = rodada.communicate(timeout=limite)
        return classificar(rodada.returncode, False, saida.decode("utf-8", "replace"))
    except subprocess.TimeoutExpired:
        _matar_a_arvore(rodada)
        return classificar(None, True)
    finally:
        caminho.write_text(fonte, encoding="utf-8", newline="")


def _matar_a_arvore(rodada: subprocess.Popen) -> None:
    """O pytest que estourou o tempo e os filhos dele: o teste que abre processos (o servidor,
    o pool do índice) deixa um neto que segura a saída aberta, e esperar por ela esperava o
    neto acabar (uma parte de 8,5 minutos chegou a 29)."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(rodada.pid)], capture_output=True)
    else:
        rodada.kill()
    try:
        rodada.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        pass


def _contextos(destino: Path, chave: dict, continuar: bool, medir) -> Dict[int, List[str]]:
    """Os contextos por linha: os guardados ao lado da medida, se ela continua com o mesmo
    módulo, os mesmos testes e as mesmas marcas; senão os de uma rodada nova (`medir`), que
    ficam guardados. Cada parte de uma medida longa não refaz a cobertura."""
    guardados = destino.with_suffix(".contextos")
    if continuar and guardados.is_file():
        bruto = json.loads(guardados.read_text(encoding="utf-8"))
        if bruto.get("chave") == chave:
            return {int(k): v for k, v in bruto["contextos"].items()}
    contextos = medir()
    guardados.write_text(json.dumps({"chave": chave, "contextos": contextos}, ensure_ascii=False),
                         encoding="utf-8", newline="\n")
    return contextos


def _commit(raiz: Path) -> str:
    rodada = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=raiz, capture_output=True)
    return rodada.stdout.decode().strip() if rodada.returncode == 0 else "sem-git"


def _gravar(destino: Path, dados: dict, resultados: Dict[int, dict]) -> None:
    lista = [resultados[n] for n in sorted(resultados)]
    dados = dict(dados, mutantes=lista, resumo=resumo([r["resultado"] for r in lista]))
    temporario = destino.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8", newline="\n")
    os.replace(temporario, destino)


def _relatorio(modulo: Path, dados: dict) -> str:
    r = dados["resumo"]
    linhas = [f"{modulo.as_posix()}: mutantes: {r['mutantes']}; mortos: {r['mortos']} "
              f"({r['percentual']:g} %); sobreviventes: {r['sobreviventes']}; "
              f"sem teste: {r['sem_teste']}" + ("; PARCIAL" if dados["parcial"] else "")]
    vivos = [m for m in dados["mutantes"] if m["resultado"] in ("sobreviveu", "sem_teste")]
    if vivos:
        linhas.append("sobreviventes:")
        linhas += [f"  {modulo.as_posix()}:{m['linha']}  {m['tipo']}  {m['original']!r} -> "
                   f"{m['troca']!r}  ({m['resultado']})" for m in vivos]
    return "\n".join(linhas)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    partes = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    partes.add_argument("modulo", type=Path, help="o módulo, a partir da raiz")
    partes.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parent.parent)
    partes.add_argument("--testes", nargs="+")
    partes.add_argument("--trabalhadores", type=int, default=4)
    partes.add_argument("--tempo-por-mutante", type=float, default=120.0)
    partes.add_argument("--ate-minutos", type=float)
    partes.add_argument("--continuar", action="store_true")
    partes.add_argument("--saida", type=Path)
    partes.add_argument("--marcas", help="a expressão -m do pytest (sem ela: a suíte rápida)")
    args = partes.parse_args()
    raiz = args.raiz.resolve()
    trabalhadores = max(1, min(4, args.trabalhadores))
    fonte = (raiz / args.modulo).read_text(encoding="utf-8")
    lista = mutantes(fonte)
    testes = args.testes or testes_que_importam(raiz, args.modulo)
    saida = args.saida or raiz / "docs" / "medidas" / "mutacao"
    saida.mkdir(parents=True, exist_ok=True)
    destino = saida / f"{args.modulo.stem}-{_commit(raiz)}.json"
    sha = hashlib.sha256(fonte.encode("utf-8")).hexdigest()
    dados = {"modulo": args.modulo.as_posix(), "commit": _commit(raiz), "sha": sha,
             "testes": testes, "marcas": args.marcas, "parcial": True}
    resultados: Dict[int, dict] = {}
    if args.continuar and destino.is_file():
        anterior = json.loads(destino.read_text(encoding="utf-8"))
        if anterior.get("sha") == sha:
            resultados = {m["n"]: m for m in anterior["mutantes"]}
    prazo = time.monotonic() + 60 * args.ate_minutos if args.ate_minutos else None
    trava = threading.Lock()
    with tempfile.TemporaryDirectory(prefix="abby-mutador-") as pasta:
        copias = [Path(pasta) / f"c{k}" for k in range(trabalhadores)]
        for copia in copias:
            shutil.copytree(raiz, copia, ignore=IGNORAR_NA_COPIA)
        contextos = _contextos(destino, {"sha": sha, "testes": testes, "marcas": args.marcas},
                               args.continuar,
                               lambda: cobertura_por_teste(copias[0], args.modulo, testes,
                                                           trabalhadores, args.marcas))
        livres: "queue.Queue[Path]" = queue.Queue()
        for copia in copias:
            livres.put(copia)

        def fazer(n: int, m: Mutante) -> None:
            if prazo is not None and time.monotonic() > prazo:
                return
            dele = testes_do_mutante(contextos, m, testes)
            if dele:
                copia = livres.get()
                try:
                    resultado = _rodar_mutante(copia, args.modulo, fonte, m, dele,
                                               args.tempo_por_mutante, args.marcas)
                finally:
                    livres.put(copia)
            else:
                resultado = "sem_teste"
            with trava:
                resultados[n] = dict(asdict(m), n=n, resultado=resultado, testes=len(dele))
                _gravar(destino, dados, resultados)
                if len(resultados) % 25 == 0:
                    print(f"{len(resultados)}/{len(lista)}", flush=True)

        with ThreadPoolExecutor(trabalhadores) as executor:
            for falha in [executor.submit(fazer, n, m) for n, m in enumerate(lista)
                          if n not in resultados]:
                falha.result()
    dados["parcial"] = len(resultados) < len(lista)
    _gravar(destino, dados, resultados)
    final = json.loads(destino.read_text(encoding="utf-8"))
    print(_relatorio(args.modulo, final))
    print(f"gravado: {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
