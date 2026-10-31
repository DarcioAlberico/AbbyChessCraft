"""As regras da própria suíte (SPEC §15.1, SPEC-qualidade Q-T1): o que a suíte rápida não
carrega, e o que as camadas lentas continuam tendo."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from abbychess.leitor import LeitorDoLivro

TESTES = Path(__file__).resolve().parent
#: As camadas lentas (SPEC §15.1): o relógio e a espera de verdade são delas.
CAMADAS_LENTAS = {"livro_real", "desempenho", "processo", "noturno"}
#: Os falsos que simulam trabalho lento (o leitor, o servidor, o processo do gravador), e a
#: espera única (`ajudantes.esperar`).
PODEM_DORMIR = {"ajudantes.py", "leitor_falso.py", "servidor_falso.py", "filho_do_gravador.py"}
RELOGIOS = {"perf_counter", "perf_counter_ns", "monotonic", "monotonic_ns", "time"}


def _marcas(no) -> set:
    """As marcas `pytest.mark.<nome>` de um decorador ou de um `pytestmark`."""
    return {n.attr for n in ast.walk(no) if isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Attribute) and n.value.attr == "mark"}


def relogio_na_suite_rapida(fonte: str):
    """(função, linha, o quê) de cada `time.sleep` e de cada `assert` sobre o relógio fora
    das camadas lentas (SPEC-qualidade CA-Q-T2)."""
    arvore = ast.parse(fonte)
    do_modulo = set()
    for no in arvore.body:
        if isinstance(no, ast.Assign) and any(isinstance(a, ast.Name) and a.id == "pytestmark"
                                              for a in no.targets):
            do_modulo |= _marcas(no.value)
    if do_modulo & CAMADAS_LENTAS:
        return []
    achados = []
    for funcao in (n for n in ast.walk(arvore)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
        if set().union(*map(_marcas, funcao.decorator_list)) & CAMADAS_LENTAS:
            continue
        for no in ast.walk(funcao):
            if isinstance(no, ast.Call) and getattr(no.func, "attr", getattr(no.func, "id", "")) \
                    == "sleep":
                achados.append((funcao.name, no.lineno, "sleep"))
            if isinstance(no, ast.Assert) and any(
                    isinstance(c, ast.Call) and getattr(c.func, "attr", None) in RELOGIOS
                    for c in ast.walk(no.test)):
                achados.append((funcao.name, no.lineno, "relógio no assert"))
    return sorted(set(achados), key=lambda a: a[1])


def test_ca_q_t2_a_suite_rapida_nao_dorme_nem_mede_o_relogio():
    """CA-Q-T2: sob -n 4, uma pausa do sistema derruba o teste que espera um `sleep` ou que
    afirma um tempo; a suíte rápida espera a condição (`ajudantes.esperar`, o
    `qtbot.waitUntil`, um `threading.Event` do falso), e o tempo é das camadas lentas.
    (`ajudantes.esperar` é a espera única; o falso que simula trabalho lento pode dormir.)"""
    achados = [f"{arquivo.relative_to(TESTES).as_posix()}:{linha} ({funcao}: {oque})"
               for arquivo in sorted(TESTES.rglob("*.py"))
               if arquivo.name not in PODEM_DORMIR and "desempenho" not in arquivo.parts
               for funcao, linha, oque in relogio_na_suite_rapida(
                   arquivo.read_text(encoding="utf-8"))]
    assert achados == []


def test_a_regra_do_relogio_pega_o_sleep_e_o_assert_e_poupa_as_camadas_lentas():
    fonte = '''
import time
import pytest

def test_espera():
    time.sleep(0.1)

def test_mede():
    inicio = time.perf_counter()
    assert time.perf_counter() - inicio < 0.2

@pytest.mark.processo
def test_lento():
    time.sleep(1)

def test_sem_relogio():
    assert 1 < 2
'''
    assert relogio_na_suite_rapida(fonte) == [("test_espera", 6, "sleep"),
                                               ("test_mede", 10, "relógio no assert")]
    assert relogio_na_suite_rapida("import pytest\npytestmark = pytest.mark.processo\n"
                                   "def test_x():\n    time.sleep(1)\n") == []


def test_a_suite_rapida_nao_carrega_os_modelos_globais(tmp_path):
    """CA-Q-T1: a rede e a base global do PyBoxEditor levam segundos e gigabytes por worker;
    na suíte rápida, quem as pede (a janela que abre um projeto) recebe o leitor só com os
    padrões do livro, e o teste da janela não estoura o prazo com -n 4."""
    leitor = LeitorDoLivro.com_modelos_globais(tmp_path / "padroes")
    assert leitor.rede is None and leitor.base is None and leitor.ocr is None


@pytest.mark.livro_real
def test_a_camada_do_livro_real_carrega_os_modelos_globais(tmp_path):
    leitor = LeitorDoLivro.com_modelos_globais(tmp_path / "padroes")
    assert leitor.base is not None and leitor.ocr is not None
