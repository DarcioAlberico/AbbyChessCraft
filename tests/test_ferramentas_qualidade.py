"""O crapper e o dryer (`ferramentas/crapper.py`, `ferramentas/dryer.py`) sobre um pacote de
brinquedo, chamados como na linha de comando (SPEC-qualidade §1, §7, §8)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

FERRAMENTAS = Path(__file__).resolve().parent.parent / "ferramentas"

# A complexidade de cada função, contada à mão: 1, mais um por if, laço, except, compreensão
# (e o if dela) e operando a mais de um `and`/`or`; a aninhada conta sozinha.
BRINQUEDO = '''\
def simples():
    return 1


def ramos(x, ys):
    if x and x > 1:
        x = 0
    for y in ys:
        x += y
    z = [y for y in ys if y]
    try:
        x = int(x)
    except ValueError:
        x = 0
    return x, z


class Caixa:
    def metodo(self, a):
        return 1 if a else 2


def mae(a):
    def filha(b):
        while b:
            b -= 1
        return b
    if a:
        return filha(a)
    return 0
'''
ESPERADO = {"simples": 1, "ramos": 7, "Caixa.metodo": 2, "mae": 2, "mae.filha": 2}


def _rodar(ferramenta, *args):
    saida = subprocess.run([sys.executable, "-I", str(FERRAMENTAS / ferramenta), *map(str, args)],
                           capture_output=True, check=True)
    return saida.stdout.decode("utf-8")


def _crapper(tmp_path, executadas, faltando, limite=0):
    pacote = tmp_path / "pacote"
    pacote.mkdir()
    (pacote / "mod.py").write_text(BRINQUEDO, encoding="utf-8")
    cobertura = tmp_path / "coverage.json"
    cobertura.write_text(json.dumps({"files": {"pacote/mod.py": {
        "executed_lines": executadas, "missing_lines": faltando}}}), encoding="utf-8")
    texto = _rodar("crapper.py", pacote, cobertura, limite)
    return texto, {m["nome"]: (float(m["crap"]), int(m["cc"]))
                   for m in re.finditer(r"(?P<crap>[\d.]+)\s+cc=\s*(?P<cc>\d+)\s+cob=\s*\d+%\s+\S+\s+"
                                        r"(?P<nome>\S+)", texto)}


def _linhas_de(nome):
    """As linhas da função `nome` (a última parte) no brinquedo, da `def` ao fim do corpo."""
    linhas = BRINQUEDO.splitlines()
    inicio = next(i for i, t in enumerate(linhas) if t.strip().startswith(f"def {nome}("))
    recuo = len(linhas[inicio]) - len(linhas[inicio].lstrip())
    fim = inicio + 1
    while fim < len(linhas) and (not linhas[fim].strip()
                                 or len(linhas[fim]) - len(linhas[fim].lstrip()) > recuo):
        fim += 1
    return list(range(inicio + 1, fim + 1))


def test_o_crapper_conta_a_complexidade_de_funcoes_metodos_e_aninhadas(tmp_path):
    todas = sorted({n for f in ESPERADO for n in _linhas_de(f.split(".")[-1])})
    texto, achadas = _crapper(tmp_path, todas, [])
    assert {nome: cc for nome, (_crap, cc) in achadas.items()} == ESPERADO
    assert texto.startswith("funções: 5;")
    # Toda coberta: o CRAP é a própria complexidade.
    assert all(crap == cc for crap, cc in achadas.values())


def test_o_crapper_pesa_a_falta_de_cobertura_e_filtra_pelo_limite(tmp_path):
    ramos = _linhas_de("ramos")
    outras = sorted({n for f in ESPERADO if f != "ramos" for n in _linhas_de(f.split(".")[-1])})
    texto, achadas = _crapper(tmp_path, outras, ramos, limite=10)
    # cc² × (1 − 0)³ + cc = 49 + 7; as outras ficam abaixo de 10 e saem.
    assert achadas == {"ramos": (56.0, 7)}
    assert texto.startswith("funções: 5; CRAP >= 10: 1")


def _par(nome, a, b):
    return f'''\
def {nome}(itens, prefixo):
    usados = {{i.id for i in itens if i.id}}
    proximo, saida = {a}, []
    for i in itens:
        if not i.id:
            while f"{{prefixo}}{{proximo}}" in usados:
                proximo += {b}
            usados.add(i.id)
        saida.append(i)
    return saida
'''


def test_o_resumo_da_qualidade_le_a_primeira_linha_de_cada_relatorio(tmp_path):
    sys.path.insert(0, str(FERRAMENTAS))
    import qualidade

    cobertura = {"totals": {"num_statements": 200, "missing_lines": 20, "percent_covered": 90.04}}
    crap, _achadas = _crapper(tmp_path, [], _linhas_de("ramos"), limite=10)   # grava o pacote
    git = {"commit": "abc1234", "arvore_suja": False, "arquivos_sujos": []}
    dados = qualidade.resumo(cobertura, crap, _rodar("dryer.py", tmp_path / "pacote", 0.8, 20),
                             git, {"rapida": 0, "processo": 0})
    assert dados["ambiente"]["commit"] == "abc1234"
    assert dados["cobertura"] == {"linhas": 200, "faltando": 20, "percentual": 90.0}
    assert dados["crap"] == {"funcoes": 5, "acima_de_10": 1}
    assert dados["duplicacao"] == {"pares_acima_de_0_8": 0}
    assert dados["camadas"] == {"rapida": 0, "processo": 0}


def test_o_resumo_da_qualidade_conta_os_pares_fora_da_lista_de_aceitos():
    sys.path.insert(0, str(FERRAMENTAS))
    import qualidade

    cobertura = {"totals": {"num_statements": 1, "missing_lines": 0, "percent_covered": 100.0}}
    duplicacao = ("funções com >= 60 nós: 9; pares com rank >= 0.8: 2\n"
                  "0.90    30 linhas  a.py:1 f  <->  b.py:1 g\n"
                  "fora da lista de aceitos: 1; aceitos que não existem mais: 0\n")
    dados = qualidade.resumo(cobertura, "funções: 1; CRAP >= 10: 0\n", duplicacao, {}, {})
    assert dados["duplicacao"] == {"pares_acima_de_0_8": 2, "fora_da_lista": 1,
                                   "aceitos_sumidos": 0}


def _pares_do_dryer(pacote):
    texto = _rodar("dryer.py", pacote, 0.8, 20)
    return [linha for linha in texto.splitlines()[1:] if linha.strip()]


def test_o_dryer_acha_as_iguais_pela_forma_com_outros_nomes_e_literais(tmp_path):
    pacote = tmp_path / "pacote"
    pacote.mkdir()
    (pacote / "um.py").write_text(_par("com_ids", 0, 1), encoding="utf-8")
    (pacote / "dois.py").write_text(
        _par("outros_ids", 5, 2)
        + "\n\ndef diferente(texto, n):\n"
        + "    partes = sorted(set(texto.split()), key=len)[::-1]\n"
        + "    return {p: len(p) * n for p in partes if p.isalpha()}\n",
        encoding="utf-8")
    pares = _pares_do_dryer(pacote)
    assert len(pares) == 1, pares
    assert pares[0].startswith("1.00") and "com_ids" in pares[0] and "outros_ids" in pares[0]


def test_o_dryer_falha_com_par_fora_da_lista_de_aceitos_e_com_aceito_que_sumiu(tmp_path):
    pacote = tmp_path / "pacote"
    pacote.mkdir()
    (pacote / "um.py").write_text(_par("com_ids", 0, 1), encoding="utf-8")
    (pacote / "dois.py").write_text(_par("outros_ids", 5, 2), encoding="utf-8")
    lista = tmp_path / "aceitos.txt"

    def dryer(texto):
        lista.write_text(texto, encoding="utf-8")
        saida = subprocess.run([sys.executable, "-I", str(FERRAMENTAS / "dryer.py"), str(pacote),
                                "0.8", "20", "--aceitos", str(lista)], capture_output=True)
        return saida.returncode, saida.stdout.decode("utf-8")

    aceito = "pacote/dois.py outros_ids <-> pacote/um.py com_ids  # o motivo\n"
    assert dryer(aceito)[0] == 0
    codigo, texto = dryer("# nenhum aceito\n")
    assert codigo == 1 and "novo" in texto and "com_ids" in texto
    codigo, texto = dryer(aceito + "pacote/um.py velha <-> pacote/dois.py antiga\n")
    assert codigo == 1 and "sumiu" in texto and "velha" in texto


def test_o_dryer_nao_casa_a_aninhada_com_a_mae_que_a_contem(tmp_path):
    pacote = tmp_path / "pacote"
    pacote.mkdir()
    filha = "\n".join("    " + t for t in _par("filha", 0, 1).splitlines())
    (pacote / "mod.py").write_text(f"def mae(itens):\n{filha}\n    return filha(itens, 'z')\n",
                                   encoding="utf-8")
    assert _pares_do_dryer(pacote) == []
