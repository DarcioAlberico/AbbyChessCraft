"""A arquitetura da janela (SPEC §14.1, CA-14.1), conferida no código-fonte.

- `app/janela.py` tem menos de 500 linhas.
- Dentro de `JanelaPrincipal`, toda função aninhada ou `lambda` só chama comandos de
  controlador (`self.pagina.…`, `self.areas.…`, `self.verificador.…`, `self.conferencia.…`,
  `self.livro.…`): a lógica não volta a crescer em closures da janela.
- A lógica (`abbychess/*.py`, fora de `app/`) não importa Qt.
"""

from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "abbychess"
JANELA = RAIZ / "app" / "janela.py"
CONTROLADORES = {"pagina", "areas", "verificador", "conferencia", "livro"}


def _chamada_de_controlador(chamada: ast.Call) -> bool:
    """`self.<controlador>.<comando>(…)`, com qualquer profundidade depois do controlador."""
    alvo = chamada.func
    cadeia = []
    while isinstance(alvo, ast.Attribute):
        cadeia.append(alvo.attr)
        alvo = alvo.value
    cadeia.reverse()
    return (isinstance(alvo, ast.Name) and alvo.id == "self" and len(cadeia) >= 2
            and cadeia[0] in CONTROLADORES)


def _aninhadas(classe: ast.ClassDef):
    """As funções aninhadas e lambdas dentro dos métodos da classe (e as lambdas do corpo)."""
    for no in classe.body:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dentro in ast.walk(no):
                if dentro is not no and isinstance(dentro, (ast.FunctionDef,
                                                            ast.AsyncFunctionDef, ast.Lambda)):
                    yield dentro
        else:
            for dentro in ast.walk(no):
                if isinstance(dentro, ast.Lambda):
                    yield dentro


def violacoes(fonte: str):
    arvore = ast.parse(fonte)
    classe = next(n for n in arvore.body if isinstance(n, ast.ClassDef)
                  and n.name == "JanelaPrincipal")
    saida = []
    for funcao in _aninhadas(classe):
        for no in ast.walk(funcao):
            if isinstance(no, ast.Call) and not _chamada_de_controlador(no):
                saida.append((funcao.lineno, ast.unparse(no.func)))
    return saida


def test_janela_tem_menos_de_500_linhas():
    linhas = JANELA.read_text(encoding="utf-8").count("\n")
    assert linhas < 500, linhas


def test_closures_da_janela_so_chamam_comandos_de_controlador():
    assert violacoes(JANELA.read_text(encoding="utf-8")) == []


def test_a_regra_pega_uma_closure_com_logica():
    fonte = '''
class JanelaPrincipal:
    def __init__(self):
        self.botao.clicked.connect(lambda: self.pagina.andar(+1))
        def pronto(r):
            self.boxes = sorted(r)
        self.x.connect(pronto)
'''
    assert violacoes(fonte) == [(5, "sorted")]


def test_a_logica_nao_importa_qt():
    for arquivo in sorted(RAIZ.glob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            nomes = []
            if isinstance(no, ast.Import):
                nomes = [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom) and no.module:
                nomes = [no.module]
            assert not any(n.split(".")[0] in ("PySide6", "PyQt5", "PyQt6") for n in nomes), \
                arquivo.name
