"""A régua do tamanho e do acoplamento (A-3, CA-A3, sobre o Q-A1 da SPEC-qualidade).

Os 40 métodos por classe e as 500 linhas da janela empurravam método para outro arquivo sem
reduzir nada: `JanelaPrincipal` tinha 237 métodos em dez classes, com `janela.py` parado em 498
linhas. No lugar deles, o que mede o objeto de verdade:

- **Total da MRO:** os métodos da classe somados aos das bases dela em `abbychess/`.
- **Acessos cruzados a privados:** `outro._x`, fora de `self` e `cls`.
- **Imports tardios:** `import` dentro de função, sinal de ciclo.
- **Maior ciclo:** o maior componente fortemente conexo do grafo de imports.

As 1.000 linhas por arquivo ficam como alarme. Cada teto tem a folga declarada do plano da
página perfeita (M1 a M3) e pode descer; subir pede motivo no commit. A régua de complexidade
(`crapper.py`) e a dos privados do core não mudam."""

from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "abbychess"
LINHAS, TOTAL_DA_MRO = 1000, 85

#: As classes acima de `TOTAL_DA_MRO`: 237 métodos em 05/11, com folga para M1 a M3.
TETOS_DA_MRO = {
    "abbychess/app/janela.py:JanelaPrincipal": 275,
}
TETO_DE_PRIVADOS = 300             # 05/11: 230, por `privados_entre_objetos`
TETO_DE_IMPORTS_TARDIOS = 360      # 05/11: 333, por `imports_tardios`
#: 05/11: 16 módulos. PPL +3: `evidencia`, `decodificador_de_lances` e `fila_de_lances` leem o
#: texto da página, e o resumo do livro e o controlador os chamam. Não cresce mais sem motivo.
TETO_DO_MAIOR_CICLO = 19


def _arquivos(raiz: Path):
    for arquivo in sorted(raiz.rglob("*.py")):
        yield arquivo.relative_to(raiz.parent).as_posix(), ast.parse(
            arquivo.read_text(encoding="utf-8"))


def _classes(raiz: Path) -> dict:
    """{"pasta/arquivo.py:Classe": o nó}, de cada classe do pacote."""
    return {f"{nome}:{no.name}": no for nome, arvore in _arquivos(raiz)
            for no in ast.walk(arvore) if isinstance(no, ast.ClassDef)}


def _metodos(no: ast.ClassDef) -> set:
    return {m.name for m in no.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _bases(no: ast.ClassDef) -> list:
    return [b.attr if isinstance(b, ast.Attribute) else b.id for b in no.bases
            if isinstance(b, (ast.Attribute, ast.Name))]


def total_da_mro(raiz: Path) -> dict:
    """{classe: quantos métodos, somando as bases do pacote}. Uma base que é de fora (o Qt) não
    conta; nomes iguais em classes diferentes contam uma vez."""
    classes = _classes(raiz)
    por_nome = {chave.split(":")[1]: no for chave, no in classes.items()}

    def metodos(no, vistos) -> set:
        saida = set(_metodos(no))
        for base in _bases(no):
            if base in por_nome and base not in vistos:
                saida |= metodos(por_nome[base], vistos | {base})
        return saida

    return {chave: len(metodos(no, {no.name})) for chave, no in classes.items()}


def privados_entre_objetos(raiz: Path) -> int:
    """Quantos `outro._x`: o atributo privado lido de quem não é `self` nem `cls`."""
    total = 0
    for _nome, arvore in _arquivos(raiz):
        for no in ast.walk(arvore):
            if (isinstance(no, ast.Attribute) and no.attr.startswith("_")
                    and not no.attr.startswith("__")
                    and not (isinstance(no.value, ast.Name) and no.value.id in ("self", "cls"))):
                total += 1
    return total


def imports_tardios(raiz: Path) -> int:
    """Quantos `import` estão dentro de uma função."""
    tardios = set()
    for _nome, arvore in _arquivos(raiz):
        for funcao in ast.walk(arvore):
            if isinstance(funcao, (ast.FunctionDef, ast.AsyncFunctionDef)):
                tardios |= {no for no in ast.walk(funcao)
                            if isinstance(no, (ast.Import, ast.ImportFrom))}
    return len(tardios)


def _modulo(nome: str, pacote: str) -> str:
    return nome[:-3].replace("/", ".").replace(f"{pacote}.__init__", pacote)


def _imports_do_arquivo(arvore, pacote: str, modulos: set) -> set:
    saida = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            saida |= {a.name for a in no.names}
        elif isinstance(no, ast.ImportFrom) and no.module:
            saida.add(no.module)
            saida |= {f"{no.module}.{a.name}" for a in no.names}
    return {m for m in saida if m in modulos}


def maior_ciclo(raiz: Path) -> int:
    """O tamanho do maior componente fortemente conexo dos imports do pacote, mesmo os tardios
    (Tarjan, sem recursão por módulo além da profundidade do pacote)."""
    pacote = raiz.name
    arvores = {_modulo(nome, pacote): arvore for nome, arvore in _arquivos(raiz)}
    modulos = set(arvores)
    grafo = {m: _imports_do_arquivo(a, pacote, modulos) for m, a in arvores.items()}
    indice, baixo, pilha, na_pilha, maior = {}, {}, [], set(), [1]

    def visitar(v):
        indice[v] = baixo[v] = len(indice)
        pilha.append(v)
        na_pilha.add(v)
        for w in grafo[v]:
            if w not in indice:
                visitar(w)
                baixo[v] = min(baixo[v], baixo[w])
            elif w in na_pilha:
                baixo[v] = min(baixo[v], indice[w])
        if baixo[v] == indice[v]:
            componente = []
            while True:
                w = pilha.pop()
                na_pilha.discard(w)
                componente.append(w)
                if w == v:
                    break
            maior[0] = max(maior[0], len(componente))

    for modulo in sorted(grafo):
        if modulo not in indice:
            visitar(modulo)
    return maior[0]


def violacoes(raiz: Path, tetos: dict) -> list:
    """O que passa das 1.000 linhas ou do total da MRO; e a exceção que venceu."""
    saida = []
    for arquivo in sorted(raiz.rglob("*.py")):
        linhas = len(arquivo.read_text(encoding="utf-8").splitlines())
        if linhas > LINHAS:
            saida.append(f"{arquivo.relative_to(raiz.parent).as_posix()}: {linhas} passa de {LINHAS}")
    totais = total_da_mro(raiz)
    for chave, total in sorted(totais.items()):
        teto = tetos.get(chave)
        if teto is None and total > TOTAL_DA_MRO:
            saida.append(f"{chave}: {total} métodos na MRO passa de {TOTAL_DA_MRO}")
        elif teto is not None and total > teto:
            saida.append(f"{chave}: {total} métodos na MRO passa do teto {teto}")
        elif teto is not None and total <= TOTAL_DA_MRO:
            saida.append(f"{chave}: {total} métodos na MRO já cabe em {TOTAL_DA_MRO}; tire-a dos tetos")
    return saida


def test_nenhum_arquivo_nem_classe_passa_do_limite_nem_do_teto():
    assert violacoes(RAIZ, TETOS_DA_MRO) == []


def test_os_acessos_a_privados_nao_passam_do_teto():
    assert privados_entre_objetos(RAIZ) <= TETO_DE_PRIVADOS


def test_os_imports_tardios_nao_passam_do_teto():
    assert imports_tardios(RAIZ) <= TETO_DE_IMPORTS_TARDIOS


def test_o_maior_ciclo_nao_passa_do_teto():
    assert maior_ciclo(RAIZ) <= TETO_DO_MAIOR_CICLO


def _pacote(tmp_path) -> Path:
    pacote = tmp_path / "abbychess"
    pacote.mkdir()
    (pacote / "__init__.py").write_text("", encoding="utf-8")
    return pacote


def test_a_regra_pega_o_que_passa_e_a_excecao_que_venceu(tmp_path):
    pacote = _pacote(tmp_path)
    metodos = "".join(f"    def m{k}(self):\n        pass\n" for k in range(50))
    outros = "".join(f"    def n{k}(self):\n        pass\n" for k in range(40))
    (pacote / "base.py").write_text("class Base:\n" + metodos, encoding="utf-8")
    (pacote / "deus.py").write_text("from abbychess.base import Base\n\nclass Deus(Base):\n" + outros,
                                    encoding="utf-8")
    (pacote / "longo.py").write_text("x = 1\n" * 1001, encoding="utf-8")
    assert violacoes(pacote, {}) == ["abbychess/longo.py: 1001 passa de 1000",
                                     "abbychess/deus.py:Deus: 90 métodos na MRO passa de 85"]
    assert violacoes(pacote, {"abbychess/deus.py:Deus": 89,
                              "abbychess/base.py:Base": 60}) == [
        "abbychess/longo.py: 1001 passa de 1000",
        "abbychess/base.py:Base: 50 métodos na MRO já cabe em 85; tire-a dos tetos",
        "abbychess/deus.py:Deus: 90 métodos na MRO passa do teto 89"]


def test_a_regua_dos_privados_conta_so_entre_objetos(tmp_path):
    pacote = _pacote(tmp_path)
    (pacote / "a.py").write_text(
        "class A:\n    def f(self, b):\n        self._x = b._y\n        return b.__class__, cls._z\n",
        encoding="utf-8")
    assert privados_entre_objetos(pacote) == 1


def test_a_regua_dos_imports_tardios_nao_conta_os_do_modulo(tmp_path):
    pacote = _pacote(tmp_path)
    (pacote / "a.py").write_text("import os\n\ndef f():\n    import sys\n    from os import path\n",
                                 encoding="utf-8")
    assert imports_tardios(pacote) == 2


def test_a_regua_do_ciclo_acha_o_maior_componente(tmp_path):
    pacote = _pacote(tmp_path)
    (pacote / "a.py").write_text("from abbychess import b\n", encoding="utf-8")
    (pacote / "b.py").write_text("def f():\n    import abbychess.c\n", encoding="utf-8")
    (pacote / "c.py").write_text("from abbychess.a import x\n", encoding="utf-8")
    (pacote / "d.py").write_text("from abbychess import a\n", encoding="utf-8")
    assert maior_ciclo(pacote) == 3
