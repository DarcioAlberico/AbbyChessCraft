"""O mutador (`ferramentas/mutador.py`, SPEC-qualidade §9, CA-Q-M1) sobre um pacote de
brinquedo: os mutantes que ele gera, como classifica cada rodada e, na camada `processo`, a
medida inteira (a cobertura por teste, os mutantes mortos, os sobreviventes, os sem teste e o
que entra em laço)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

FERRAMENTAS = Path(__file__).resolve().parent.parent / "ferramentas"
sys.path.insert(0, str(FERRAMENTAS))
import mutador  # noqa: E402

#: O "é" antes do operador na mesma linha: o AST conta a coluna em bytes, o texto em caracteres.
BRINQUEDO = '''\
def f(a, b):
    """O docstring não muta."""
    if "é" < b and b != 0:  # é
        return a + 1
    return not a
'''


def _linhas_mutadas(fonte):
    originais = fonte.split("\n")                # as linhas do Python: só o \n as parte
    saida = set()
    for m in mutador.mutantes(fonte):
        novas = m.aplicar(fonte).split("\n")
        assert len(novas) == len(originais), m
        [k] = [k for k, (a, b) in enumerate(zip(originais, novas)) if a != b]
        assert k + 1 == m.linha, m
        saida.add((m.linha, novas[k]))
    return saida


def test_os_mutantes_trocam_operadores_constantes_e_condicoes_no_lugar_certo():
    assert _linhas_mutadas(BRINQUEDO) == {
        (3, '    if not ("é" < b and b != 0):  # é'),       # a condição negada
        (3, '    if "é" <= b and b != 0:  # é'),
        (3, '    if "é" < b or b != 0:  # é'),
        (3, '    if "é" < b and b == 0:  # é'),
        (3, '    if "é" < b and b != 1:  # é'),
        (4, "        return a - 1"),
        (4, "        return a + 2"),
        (5, "    return a"),                                 # o not tirado
    }


def test_os_mutantes_de_atribuicao_comparacao_de_identidade_e_laco():
    fonte = ("def g(xs, n):\n"
             "    while n > 0:\n"
             "        n -= 1\n"
             "        if xs is None or n in xs:\n"
             "            break\n"
             "    return True\n")
    assert _linhas_mutadas(fonte) == {
        (2, "    while not (n > 0):"), (2, "    while n >= 0:"), (2, "    while n > 1:"),
        (3, "        n += 1"), (3, "        n -= 2"),
        (4, "        if not (xs is None or n in xs):"),
        (4, "        if xs is not None or n in xs:"),
        (4, "        if xs is None and n in xs:"),
        (4, "        if xs is None or n not in xs:"),
        (5, "            continue"),
        (6, "    return False"),
    }


def test_o_separador_de_paragrafo_numa_string_nao_parte_a_linha():
    """O U+2029 (o parágrafo do Qt, escrito como está numa string do `sessao`) é fim de linha
    para o `str.splitlines`, mas não para o tokenizador nem para o AST."""
    fonte = 'SEP = " "\n\n\ndef h(a):\n    return a + 1\n'
    assert _linhas_mutadas(fonte) == {(5, "    return a - 1"), (5, "    return a + 2")}


def test_a_rodada_de_cada_mutante_vira_morto_sobreviveu_ou_tempo():
    assert mutador.classificar(0, False) == "sobreviveu"
    assert mutador.classificar(1, False) == "morto"          # um teste reprovou
    assert mutador.classificar(2, False) == "morto"          # o mutante nem importa
    assert mutador.classificar(None, True) == "tempo"        # entrou em laço
    for codigo in (4, 5):                                    # o erro é do mutador, não do mutante
        with pytest.raises(RuntimeError):
            mutador.classificar(codigo, False)


def test_os_testes_de_um_mutante_sao_os_que_cobrem_a_linha_dele():
    contextos = {3: ["tests/t.py::test_b|run", "", "tests/t.py::test_a|setup",
                     "tests/t.py::test_a|run"],
                 4: ["tests/t.py::test_c|run"]}
    todos = ["tests/t.py", "tests/u.py"]
    [m] = [m for m in mutador.mutantes(BRINQUEDO) if m.linha == 3 and m.troca == "<="]
    assert mutador.testes_do_mutante(contextos, m, todos) == ["tests/t.py::test_a",
                                                             "tests/t.py::test_b"]
    [m] = [m for m in mutador.mutantes(BRINQUEDO) if m.linha == 5]
    assert mutador.testes_do_mutante(contextos, m, todos) == []


def test_a_linha_que_roda_ao_importar_o_modulo_vale_para_todos_os_testes_dele():
    """A constante do módulo e o valor padrão de uma dataclass rodam na importação, que o
    pytest faz na coleta, fora de teste nenhum: a cobertura os marca com o contexto vazio."""
    fonte = "LIMITE = 3\n\n\ndef f(x):\n    return x < LIMITE\n"
    [m] = [m for m in mutador.mutantes(fonte) if m.linha == 1]
    todos = ["tests/t.py", "tests/u.py"]
    assert mutador.testes_do_mutante({1: [""], 5: ["tests/t.py::test_f|run"]}, m, todos) == todos
    # Também quando um teste importa o módulo de novo (e a linha roda nele): a importação
    # da coleta vale para todos, não só para ele.
    assert mutador.testes_do_mutante({1: ["", "tests/t.py::test_recarrega|run"]}, m,
                                     todos) == todos


def test_o_resumo_conta_o_tempo_como_morto_e_o_sem_teste_como_sobrevivente():
    resultados = ["morto", "morto", "tempo", "sobreviveu", "sem_teste"]
    assert mutador.resumo(resultados) == {"mutantes": 5, "mortos": 3, "sobreviventes": 1,
                                          "sem_teste": 1, "percentual": 60.0}


PROJETO = {
    "pacote/__init__.py": "",
    "pacote/mod.py": ('def f(a, b):\n'
                      '    if a < b and b != 0:\n'
                      '        return a + 1\n'
                      '    return not a\n'
                      '\n'
                      '\n'
                      'def contar(n):\n'
                      '    while n > 0:\n'
                      '        n -= 1\n'
                      '    return n\n'
                      '\n'
                      '\n'
                      'def sem_teste(x):\n'
                      '    return x * 2\n'),
    "tests/__init__.py": "",
    "tests/test_mod.py": ("from pacote.mod import contar, f\n\n\n"
                          "def test_f():\n    assert f(1, 2) == 2\n\n\n"
                          "def test_contar():\n    assert contar(3) == 0\n"),
}


@pytest.mark.processo
def test_a_medida_inteira_no_brinquedo(tmp_path):
    raiz = tmp_path / "projeto"
    for nome, texto in PROJETO.items():
        (raiz / nome).parent.mkdir(parents=True, exist_ok=True)
        (raiz / nome).write_text(texto, encoding="utf-8")
    saida = tmp_path / "saida"
    rodada = subprocess.run(
        [sys.executable, str(FERRAMENTAS / "mutador.py"), "pacote/mod.py", "--raiz", str(raiz),
         "--testes", "tests/test_mod.py", "--trabalhadores", "2", "--saida", str(saida),
         "--tempo-por-mutante", "8"], capture_output=True, timeout=600)
    texto = rodada.stdout.decode("utf-8")
    assert rodada.returncode == 0, texto + rodada.stderr.decode("utf-8", "replace")
    [arquivo] = saida.glob("mod-*.json")
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    por = {(m["linha"], m["troca"]): m["resultado"] for m in dados["mutantes"]}
    assert por[(3, "-")] == "morto"                  # f(1, 2) daria 0
    assert por[(2, "<=")] == "sobreviveu"            # 1 <= 2 também
    assert por[(9, "+=")] == "tempo"                 # contar nunca acaba
    assert por[(14, "/")] == "sem_teste"             # nenhum teste chama sem_teste
    assert dados["resumo"]["mutantes"] == len(dados["mutantes"])
    assert "sobreviventes" in texto and "mod.py:2" in texto
