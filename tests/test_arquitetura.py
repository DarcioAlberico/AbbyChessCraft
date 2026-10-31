"""A arquitetura da janela (SPEC §14.1, CA-14.1), conferida no código-fonte.

- `app/janela.py` tem menos de 500 linhas.
- Dentro de `JanelaPrincipal`, toda função aninhada ou `lambda` só chama comandos de
  controlador (`self.pagina.…`, `self.areas.…`, `self.verificador.…`, `self.conferencia.…`,
  `self.livro.…`): a lógica não volta a crescer em closures da janela.
- A lógica (`abbychess/*.py`, fora de `app/`) não importa Qt.
- Nenhum `except` amplo engole o erro (SPEC-qualidade CA-Q-C4): o que pega `Exception` (ou
  `BaseException`, ou tudo) levanta de novo, vai ao log com o rastro (`log.exception`,
  `exc_info=`), ou leva o erro adiante como valor, numa das funções de `LEVAM_O_ERRO`.
"""

from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "abbychess"
JANELA = RAIZ / "app" / "janela.py"
CONTROLADORES = {"pagina", "areas", "verificador", "conferencia", "livro", "fila"}


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


def violacoes(fonte: str, classe_nome: str = "JanelaPrincipal"):
    arvore = ast.parse(fonte)
    classe = next(n for n in arvore.body if isinstance(n, ast.ClassDef)
                  and n.name == classe_nome)
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
    # O desenho é parte da janela (um mixin, desde o 2b): a mesma regra.
    desenho = (RAIZ / "app" / "desenho.py").read_text(encoding="utf-8")
    assert violacoes(desenho, "DesenhoDaJanela") == []
    # O espaço de trabalho (os painéis, os arranjos, o foco) também, desde o A2.
    espaco = (RAIZ / "app" / "espaco.py").read_text(encoding="utf-8")
    assert violacoes(espaco, "EspacoDeTrabalho") == []


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


def test_closures_da_janela_nao_tem_atribuicao_nem_controle_de_fluxo():
    arvore = ast.parse(JANELA.read_text(encoding="utf-8"))
    classe = next(n for n in arvore.body if isinstance(n, ast.ClassDef)
                  and n.name == "JanelaPrincipal")
    proibidos = (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.If, ast.For, ast.While,
                 ast.Try, ast.With, ast.IfExp)
    achados = [(f.lineno, type(no).__name__) for f in _aninhadas(classe)
               for no in ast.walk(f) if isinstance(no, proibidos)]
    assert achados == []


#: (arquivo, função) -> por que o `except` amplo dela não engole o erro: ele o leva adiante.
LEVAM_O_ERRO = {
    ("app/dialogos.py", "rodar"): "a thread guarda o erro, levantado de novo na interface",
    ("controlador_da_substituicao.py", "_trocar"):
        "a substituição que falha vai à lista de falhas, ao usuário",
    ("escritor_docx.py", "conferir"): "o que o python-docx não abre vira problema do relatório",
    ("lote.py", "rodar"): "a leitura que falhou volta ao lote como resultado, com o rastro",
    ("servidor_de_leitura.py", "_atender"): "a resposta leva o erro e o rastro à interface",
    ("servidor_de_leitura.py", "_principal"): "a queda do filho vai à interface com o rastro",
    ("render.py", "_matar"): "matar o processo que já morreu",
}


def _amplo(tipo) -> bool:
    if tipo is None:
        return True
    nomes = tipo.elts if isinstance(tipo, ast.Tuple) else [tipo]
    return any(isinstance(n, ast.Name) and n.id in ("Exception", "BaseException") for n in nomes)


def _registra_ou_levanta(handler: ast.ExceptHandler) -> bool:
    for no in ast.walk(handler):
        if isinstance(no, ast.Raise):
            return True
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute) and (
                no.func.attr == "exception" or any(k.arg == "exc_info" for k in no.keywords)):
            return True
    return False


def excepts_que_engolem(fonte: str):
    """(função, linha) de cada `except` amplo que nem levanta nem registra o rastro."""
    achados = []

    def visitar(no, funcao):
        for filho in ast.iter_child_nodes(no):
            if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visitar(filho, filho.name)
                continue
            if isinstance(filho, ast.ExceptHandler) and _amplo(filho.type) \
                    and not _registra_ou_levanta(filho):
                achados.append((funcao, filho.lineno))
            visitar(filho, funcao)

    visitar(ast.parse(fonte), "<módulo>")
    return achados


def test_nenhum_except_amplo_engole_o_erro():
    achados = []
    for arquivo in sorted(RAIZ.rglob("*.py")):
        relativo = arquivo.relative_to(RAIZ).as_posix()
        for funcao, linha in excepts_que_engolem(arquivo.read_text(encoding="utf-8")):
            if (relativo, funcao) not in LEVAM_O_ERRO:
                achados.append(f"{relativo}:{linha} ({funcao})")
    assert achados == []


def test_a_regra_dos_excepts_pega_o_que_engole_e_aceita_o_que_registra():
    fonte = '''
def engole():
    try:
        x()
    except Exception:
        pass

def registra():
    try:
        x()
    except Exception:
        log.exception("x falhou")

def avisa_com_o_rastro():
    try:
        x()
    except (OSError, Exception) as erro:
        log.warning("x falhou: %s", erro, exc_info=True)

def levanta():
    try:
        x()
    except BaseException:
        limpar()
        raise

def estreito():
    try:
        x()
    except ValueError:
        return None
'''
    assert excepts_que_engolem(fonte) == [("engole", 5)]


def test_lambdas_das_acoes_so_chamam_a_janela_ou_os_controladores():
    """`app/acoes.py` liga cada ação a um método da janela (`j`) ou a um comando de
    controlador (`p`, `livro`, `j.<controlador>`), sem lógica na lambda."""
    arvore = ast.parse((RAIZ / "app" / "acoes.py").read_text(encoding="utf-8"))
    ruins = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Lambda):
            continue
        for dentro in ast.walk(no.body):
            if isinstance(dentro, ast.Call):
                alvo = dentro.func
                while isinstance(alvo, ast.Attribute):
                    alvo = alvo.value
                if not (isinstance(alvo, ast.Name) and alvo.id in ("j", "p", "livro")):
                    ruins.append((dentro.lineno, ast.unparse(dentro.func)))
            elif isinstance(dentro, (ast.IfExp, ast.ListComp, ast.GeneratorExp)):
                ruins.append((dentro.lineno, type(dentro).__name__))
    assert ruins == []
