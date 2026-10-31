"""Nenhum objeto-deus (SPEC-qualidade Q-A1, CA-Q-A1): nenhum arquivo de `abbychess/` com mais
de 1 000 linhas, nenhuma classe com mais de 40 métodos.

Os que ainda passam estão em `TETOS`, com o tamanho de hoje: o teto só desce. Crescer além
dele reprova; cair abaixo do limite e continuar na lista também (a exceção venceu e sai)."""

from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "abbychess"
LINHAS, METODOS = 1000, 40

#: O que ainda passa do limite, com o teto de hoje (Q7: os cortes 4 e 5 e o resto descem).
TETOS = {
    "abbychess/pagina.py": 1446,
    "abbychess/projeto.py:ProjetoDeLivro": 43,
    "abbychess/controlador.py:ControladorDePagina": 61,
    "abbychess/app/documento.py:VistaDoDocumento": 58,
    "abbychess/app/espaco.py:EspacoDeTrabalho": 53,
    "abbychess/app/visor.py:VisorDePagina": 55,
}


def medidas(raiz: Path):
    """{"pasta/arquivo.py": linhas} e {"pasta/arquivo.py:Classe": métodos}, de cada .py."""
    for arquivo in sorted(raiz.rglob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        nome = arquivo.relative_to(raiz.parent).as_posix()
        yield nome, len(texto.splitlines()), LINHAS
        for no in ast.walk(ast.parse(texto)):
            if isinstance(no, ast.ClassDef):
                n = sum(isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) for m in no.body)
                yield f"{nome}:{no.name}", n, METODOS


def violacoes(raiz: Path, tetos: dict) -> list:
    saida = []
    for nome, tamanho, limite in medidas(raiz):
        teto = tetos.get(nome)
        if teto is None and tamanho > limite:
            saida.append(f"{nome}: {tamanho} passa de {limite}")
        elif teto is not None and tamanho > teto:
            saida.append(f"{nome}: {tamanho} passa do teto {teto}")
        elif teto is not None and tamanho <= limite:
            saida.append(f"{nome}: {tamanho} já cabe em {limite}; tire-o de TETOS")
    return saida


def test_nenhum_arquivo_nem_classe_passa_do_limite_nem_do_teto():
    assert violacoes(RAIZ, TETOS) == []


def test_a_regra_pega_o_que_passa_e_a_excecao_que_venceu(tmp_path):
    pacote = tmp_path / "abbychess"
    pacote.mkdir()
    metodos = "".join(f"    def m{k}(self):\n        pass\n" for k in range(41))
    (pacote / "deus.py").write_text("class Deus:\n" + metodos, encoding="utf-8")
    (pacote / "longo.py").write_text("x = 1\n" * 1001, encoding="utf-8")
    (pacote / "curto.py").write_text("x = 1\n", encoding="utf-8")
    assert violacoes(pacote, {}) == ["abbychess/deus.py:Deus: 41 passa de 40",
                                     "abbychess/longo.py: 1001 passa de 1000"]
    tetos = {"abbychess/deus.py:Deus": 41, "abbychess/longo.py": 1000,
             "abbychess/curto.py": 5}
    assert violacoes(pacote, tetos) == ["abbychess/curto.py: 1 já cabe em 1000; tire-o de TETOS",
                                        "abbychess/longo.py: 1001 passa do teto 1000"]
