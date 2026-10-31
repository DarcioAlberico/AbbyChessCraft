"""As alavancas dos cortes 3 e 5 do Q7 (`ferramentas/mover_metodos.py`,
`ferramentas/trocar_chamadas.py`, `ferramentas/mover_definicoes.py`) sobre módulos de
brinquedo, chamadas como na linha de comando (SPEC-qualidade Q-A1)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FERRAMENTAS = Path(__file__).resolve().parent.parent / "ferramentas"

BRINQUEDO = '''\
class Dono:
    def __init__(self):
        self.base = 10
        self.col = None

    def fica(self):
        return self.col.dobro() + 1

    def dobro(self):
        return self.base * self._vezes

    def _vezes_mais(self):
        self._vezes += 1
'''


def _rodar(*args, cwd):
    return subprocess.run([sys.executable, *map(str, args)], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8")


def test_mover_metodos_leva_o_metodo_e_o_estado_e_a_origem_chama_o_colaborador(tmp_path):
    origem = tmp_path / "dono.py"
    origem.write_text(BRINQUEDO, encoding="utf-8")
    saida = _rodar(FERRAMENTAS / "mover_metodos.py", origem, "Dono", tmp_path / "col.py",
                   "Colaborador", "col", "--metodos", "dobro,_vezes_mais", "--estado", "_vezes",
                   "--renomear", "_vezes_mais:vezes_mais", "--aplicar", cwd=tmp_path)
    assert saida.returncode == 0, saida.stderr
    espaco: dict = {}
    exec((tmp_path / "col.py").read_text(encoding="utf-8"), espaco)
    exec(origem.read_text(encoding="utf-8"), espaco)
    dono = espaco["Dono"]()
    dono.col = espaco["Colaborador"](dono)
    dono.col._vezes = 2
    dono.col.vezes_mais()                       # o estado é do colaborador
    assert dono.fica() == 31                    # 10 (da origem) × 3 + 1
    assert not hasattr(dono, "dobro")


def test_trocar_chamadas_com_a_contagem_errada_nao_grava_nada(tmp_path):
    alvo = tmp_path / "a.py"
    alvo.write_text("p.um()\np.um()\n", encoding="utf-8")
    tabela = tmp_path / "t.tsv"
    tabela.write_text("a.py\t\\bp\\.um\\b\tp.col.um\t1\n", encoding="utf-8")
    saida = _rodar(FERRAMENTAS / "trocar_chamadas.py", tabela, "--aplicar", cwd=tmp_path)
    assert saida.returncode == 1 and "trocou 2, esperava 1" in saida.stdout
    assert alvo.read_text(encoding="utf-8") == "p.um()\np.um()\n"
    tabela.write_text("a.py\t\\bp\\.um\\b\tp.col.um\t2\n", encoding="utf-8")
    assert _rodar(FERRAMENTAS / "trocar_chamadas.py", tabela, "--aplicar",
                  cwd=tmp_path).returncode == 0
    assert alvo.read_text(encoding="utf-8") == "p.col.um()\np.col.um()\n"


GRANDE = '''\
"""Grande."""

from abbychess import base


#: O que o dobro dobra.
LIMITE = 3


def fica():
    return dobro(LIMITE) + 1


def dobro(x):
    return x * 2
'''

USO = '''\
from abbychess import grande as gr


def usar():
    return gr.dobro(2) + gr.fica()
'''


def test_mover_definicoes_leva_a_constante_e_a_funcao_e_os_chamadores_seguem(tmp_path):
    pacote = tmp_path / "abbychess"
    pacote.mkdir()
    (pacote / "__init__.py").write_text("", encoding="utf-8")
    (pacote / "base.py").write_text("", encoding="utf-8")
    (pacote / "grande.py").write_text(GRANDE, encoding="utf-8")
    (tmp_path / "chamador").mkdir()
    (tmp_path / "chamador" / "uso.py").write_text(USO, encoding="utf-8")
    cabecalho = tmp_path / "cabecalho.txt"
    cabecalho.write_text('"""Miúdo."""\n', encoding="utf-8")
    saida = _rodar(FERRAMENTAS / "mover_definicoes.py", pacote / "grande.py", pacote / "miudo.py",
                   "--nomes", "LIMITE,dobro", "--cabecalho", cabecalho,
                   "--chamadores", "chamador", "--alias", "mi", "--aplicar", cwd=tmp_path)
    assert saida.returncode == 0, saida.stderr
    miudo = (pacote / "miudo.py").read_text(encoding="utf-8")
    assert "#: O que o dobro dobra.\nLIMITE = 3" in miudo     # o comentário vai junto
    assert "def dobro" not in (pacote / "grande.py").read_text(encoding="utf-8")
    assert "mi.dobro(2)" in (tmp_path / "chamador" / "uso.py").read_text(encoding="utf-8")
    rodar = _rodar("-c", "from chamador.uso import usar; print(usar())", cwd=tmp_path)
    assert rodar.stdout.strip() == "11", rodar.stderr      # 4 + (6 + 1)
