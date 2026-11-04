"""Nenhum privado do PyBoxEditor fora da lista (SPEC-qualidade Q-E7, CA-Q-E7): o programa usa o
core pela API dele. O que ainda passa por um `_nome` está em `EXCECOES`, cada um com o pedido
em `docs/pedidos-ao-pyboxeditor.md` e o teste de contrato que fixa o comportamento usado; a
lista só encolhe (o nome que sai do código sai daqui, ou o teste reprova).

O acesso é achado pelo AST, sem saber os tipos: pelo nome importado do core (o módulo, a
classe: `BoxService._tinta_do_box`), ou por uma variável da função criada por uma classe do core
(`servico = LearningService(...)`) ou anotada com ela (`tabuleiro: TabuleiroEdicao`)."""

from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PEDIDOS = RAIZ / "docs" / "pedidos-ao-pyboxeditor.md"
CONTRATOS = RAIZ / "tests" / "test_contrato_do_core.py"

#: (arquivo, "Dono._nome") -> o teste de contrato (em `CONTRATOS`) que fixa o uso.
EXCECOES = {
    ("abbychess/diagramas.py", "TabuleiroEdicao._estado"): "test_contrato_do_historico_do_tabuleiro",
    ("abbychess/diagramas.py", "TabuleiroEdicao._historico"): "test_contrato_do_historico_do_tabuleiro",
    ("abbychess/diagramas.py", "TabuleiroEdicao._indice"): "test_contrato_do_historico_do_tabuleiro",
    ("abbychess/diagramas.py", "TabuleiroEdicao._registrar"): "test_contrato_do_historico_do_tabuleiro",
    ("abbychess/editar_boxes.py", "BoxService._tinta_do_box"): "test_contrato_da_tinta_do_box",
    ("abbychess/editar_boxes.py", "BoxService._vale_mais_fundo"): "test_contrato_do_vale_mais_fundo",
    ("abbychess/leitor.py", "LearningService._get_learner"): "test_contrato_do_servico_de_aprendizado",
    ("abbychess/leitor.py", "LearningService._predictor"): "test_contrato_do_servico_de_aprendizado",
    ("abbychess/verificacao.py", "lexico._ler"): "test_contrato_da_lista_de_palavras",
}


def _do_core(arvore) -> dict:
    """Nome local -> nome no core, de cada import do pacote `core` (em qualquer lugar do arquivo)."""
    nomes = {}
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and (no.module or "").split(".")[0] == "core":
            nomes.update({a.asname or a.name: a.name for a in no.names})
        elif isinstance(no, ast.Import):
            nomes.update({(a.asname or a.name).split(".")[0]: a.name.split(".")[-1]
                          for a in no.names if a.name.split(".")[0] == "core"})
    return nomes


def _tipo(anotacao, do_core: dict):
    if isinstance(anotacao, ast.Name):
        return do_core.get(anotacao.id)
    if isinstance(anotacao, ast.Constant) and isinstance(anotacao.value, str):
        return do_core.get(anotacao.value.split("[")[0].strip())
    return None


def _locais(funcao, do_core: dict) -> dict:
    """As variáveis da função ligadas a uma classe do core: o parâmetro anotado com ela e o
    nome que recebe uma chamada a ela."""
    locais = {}
    argumentos = funcao.args
    for arg in [*argumentos.posonlyargs, *argumentos.args, *argumentos.kwonlyargs]:
        tipo = _tipo(arg.annotation, do_core)
        if tipo:
            locais[arg.arg] = tipo
    for no in ast.walk(funcao):
        if (isinstance(no, ast.Assign) and isinstance(no.value, ast.Call)
                and isinstance(no.value.func, ast.Name) and no.value.func.id in do_core):
            locais.update({alvo.id: do_core[no.value.func.id] for alvo in no.targets
                           if isinstance(alvo, ast.Name)})
    return locais


def privados_do_core(fonte: str) -> set:
    """Os "Dono._nome" de cada acesso a um privado do core no texto do módulo."""
    arvore = ast.parse(fonte)
    do_core = _do_core(arvore)
    achados = set()
    escopos = [(arvore, {})] + [(f, _locais(f, do_core)) for f in ast.walk(arvore)
                                if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for escopo, locais in escopos:
        for no in ast.walk(escopo):
            if (isinstance(no, ast.Attribute) and no.attr.startswith("_")
                    and not no.attr.startswith("__") and isinstance(no.value, ast.Name)):
                dono = locais.get(no.value.id) or do_core.get(no.value.id)
                if dono:
                    achados.add(f"{dono}.{no.attr}")
    return achados


def acessos(raiz: Path) -> set:
    """(arquivo, "Dono._nome") de `abbychess/` inteiro."""
    return {(arquivo.relative_to(raiz).as_posix(), nome)
            for arquivo in sorted((raiz / "abbychess").rglob("*.py"))
            for nome in privados_do_core(arquivo.read_text(encoding="utf-8"))}


def test_os_privados_do_core_sao_so_os_da_lista():
    assert acessos(RAIZ) == set(EXCECOES)


def test_cada_excecao_tem_o_pedido_e_o_teste_de_contrato():
    pedidos = PEDIDOS.read_text(encoding="utf-8") if PEDIDOS.is_file() else ""
    contratos = (ast.parse(CONTRATOS.read_text(encoding="utf-8")) if CONTRATOS.is_file()
                 else ast.Module(body=[], type_ignores=[]))
    testes = {no.name for no in contratos.body if isinstance(no, ast.FunctionDef)}
    sem_pedido = sorted(nome for _a, nome in EXCECOES if f"`{nome}`" not in pedidos)
    sem_contrato = sorted(t for t in EXCECOES.values() if t not in testes)
    assert sem_pedido == [] and sem_contrato == []


def test_a_regra_pega_o_nome_do_core_o_parametro_anotado_e_o_objeto_criado():
    fonte = '''
from core.servicos import Classe
from core import modulo
from abbychess import nosso


def anotado(c: Classe, d: "Classe"):
    return c._a, d._b


def criado():
    o = Classe()
    return o._c, Classe._d, modulo._e, nosso._f, o.publico, o.__dict__
'''
    assert privados_do_core(fonte) == {"Classe._a", "Classe._b", "Classe._c", "Classe._d",
                                       "modulo._e"}
