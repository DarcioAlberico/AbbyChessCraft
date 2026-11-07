"""CA-R1.6: a tabela de 60 tokens rotulados à mão; `lances._tokens` confere sobre a mesma tabela,
e `Projeto.letras_das_pecas` muda quem é cada letra. A normalização e o alinhamento únicos."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from abbychess import lances as lc
from abbychess import tokens as tk

TABELA = yaml.safe_load((Path(__file__).parent / "dados" / "tokens_rotulados.yaml")
                        .read_text(encoding="utf-8"))["tokens"]
_ALFABETOS = ("RDTBC", "KQRBN")


def _casos():
    for linha in TABELA:
        for letras in ([linha["letras"]] if "letras" in linha else _ALFABETOS):
            yield str(linha["token"]), letras, linha["classe"], linha.get("peca")


def test_a_tabela_tem_60_linhas():
    assert len(TABELA) >= 60


@pytest.mark.parametrize("token, letras, classe, peca", list(_casos()))
def test_cada_token_na_classe_certa(token, letras, classe, peca):
    achado = tk.classificar_token(token, letras)
    assert achado.classe == classe, achado
    if peca is not None:
        assert achado.peca == peca, achado


@pytest.mark.parametrize("token, letras, classe, _peca", list(_casos()))
def test_lances_tokens_concorda_com_a_tabela(token, letras, classe, _peca):
    tipos = {t for t, _ in lc._tokens(token, letras)}
    assert ("lance" in tipos) == (classe == tk.LANCE), (token, tipos)


def test_os_subtokens():
    t = tk.classificar_token("(12.♘xf3+!)", "RDTBC")
    assert (t.abre, t.numero, t.nucleo, t.xeque, t.sinal, t.fecha) == (
        "(", "12.", "♘xf3", "+", "!", ")")
    assert t.san == "Nxf3"


def test_o_igual_colado_a_casa_com_peca_e_promocao():
    t = tk.classificar_token("a8=D", "RDTBC")
    assert t.classe == tk.LANCE and t.nucleo == "a8=D" and t.sinal == ""
    assert tk.classificar_token("a8=", "RDTBC").sinal == "="


def test_o_xeque_faz_parte_do_lance():
    assert tk.classificar_token("♖e1#", "RDTBC").xeque == "#"
    assert tk.classificar_token("♖e1†", "RDTBC").xeque == "†"


def test_o_lance_longo_e_prosa_mas_e_contado():
    t = tk.classificar_token("e2-e4", "RDTBC")
    assert t.classe == tk.PROSA and t.forma_longa
    assert not tk.classificar_token("de", "RDTBC").forma_longa


def test_o_idioma_tambem_da_as_letras():
    assert tk.classificar_token("Tf1", "pt").peca == "R"
    assert tk.classificar_token("Rf1", "en").peca == "R"


# ------------------------------------------------------------------
# Normalização
# ------------------------------------------------------------------
def test_a_literal_e_nfc_e_espacos():
    assert tk.normalizar("a  b\n c") == "a b c"
    assert tk.normalizar("é") == "é"
    assert tk.normalizar("♘f3 –", tk.LITERAL) == "♘f3 –"


@pytest.mark.parametrize("entrada, saida", [
    ("♘f3", "Cf3"), ("♞f6", "Cf6"), ("♙e4", "e4"), ("0-0", "O-O"), ("0-0-0", "O-O-O"),
    ("1–0", "1-0"), ("a—b", "a-b"), ("“aspas”", '"aspas"'), ("12…♘f6", "12...Cf6"),
])
def test_a_semantica(entrada, saida):
    assert tk.normalizar(entrada, tk.SEMANTICA, "RDTBC") == saida


def test_mais_menos_e_o_sinal_seguem_diferentes():
    assert tk.normalizar("+-", tk.SEMANTICA) != tk.normalizar("±", tk.SEMANTICA)


# ------------------------------------------------------------------
# Alinhamento
# ------------------------------------------------------------------
def test_alinhar_igual():
    assert tk.alinhar("abc", "abc") == [(0, 0), (1, 1), (2, 2)]


def test_alinhar_troca_antes_de_falta_e_sobra():
    assert tk.alinhar("ab", "ax") == [(0, 0), (1, 1)]


def test_alinhar_falta_e_sobra():
    assert tk.alinhar("abc", "ac") == [(0, 0), (1, None), (2, 1)]
    assert tk.alinhar("ac", "abc") == [(0, 0), (None, 1), (1, 2)]


def test_alinhar_vazios():
    assert tk.alinhar("", "") == []
    assert tk.alinhar("a", "") == [(0, None)]
    assert tk.alinhar("", "a") == [(None, 0)]


# ------------------------------------------------------------------
# Avaliar
# ------------------------------------------------------------------
def _erros(verdade, lida):
    return [(a.token.texto, a.erro) for a in tk.avaliar_a_linha(verdade, lida, "RDTBC")]


def test_token_certo():
    assert _erros("1.e4 e5 Cf3", "1.e4 e5 Cf3") == [("1.e4", ""), ("e5", ""), ("Cf3", "")]


def test_a_figurina_e_a_letra_sao_iguais_na_semantica():
    assert _erros("Cf3", "♘f3") == [("Cf3", "")]


def test_os_tipos_de_erro():
    assert _erros("Cf3 Td1", "Cf8 Td1") == [("Cf3", "troca"), ("Td1", "")]
    assert _erros("Cf3 e5", "Cf e5") == [("Cf3", "falta"), ("e5", "")]
    assert _erros("Cf3 e5", "e5") == [("Cf3", "sumiu"), ("e5", "")]


def test_dois_tokens_colados_e_erro_de_espaco_nos_dois():
    assert _erros("a b", "ab") == [("a", "espaco"), ("b", "espaco")]


def test_um_token_partido_e_erro_de_espaco():
    assert _erros("abcd", "ab cd") == [("abcd", "espaco")]
