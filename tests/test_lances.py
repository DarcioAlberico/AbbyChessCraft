"""A validação pelos lances, o roque inferido e o PGN de cada diagrama (§10, passo H)."""

from __future__ import annotations

import io
import json
import sys
from dataclasses import replace
from pathlib import Path

import chess
import chess.pgn

from core.box_model import BoxEntry

from abbychess import diagramas as dg
from abbychess import lances as lc
from abbychess import texto as tx
from abbychess.leitor import FONTE_MANUAL

from tests.test_diagramas import _lido

RAIZ = Path(__file__).resolve().parent.parent

#: Xadrez Vitorioso, p. 23 (Diagrama 4: sem o cavalo de b1) e p. 25 (Diagrama 5).
P23 = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/R1BQKBNR"
P25 = "rnbqk2r/ppp3pp/3p1n2/8/2Bb1B2/5Q2/PPP3PP/4RR1K"
TEXTO_P23 = ("1.e4 e5 2.f4\nAs brancas mostram imediatamente que estão dispostas a entregar\n"
             "2...exf4 3.Cf3 f5?\nUm lance muito ruim. Seria melhor algo como 2...d5 (que")
TEXTO_P25 = ("10...Rf8 11.Dd5??\nAs brancas ameaçam o mate e esperam que as pretas se\n"
             "entusiasmem por 11...Cxd5 12.Bxd6+ + Rg8 13.Bxd5+ Be6 14.Bxe6 xeque-mate.\n"
             "11...Dd7 12.Dxd4 Cc6")


def _sans(linha):
    return [lance.san for lance in linha]


# ----------------------------------------------------------------------
# A primeira linha
# ----------------------------------------------------------------------

def test_linha_em_portugues_com_a_prosa_no_meio():
    linha = lc.primeira_linha(TEXTO_P23, "pt")
    assert _sans(linha) == ["e4", "e5", "f4", "exf4", "Nf3", "f5"]
    assert [lance.rotulo() for lance in linha[-2:]] == ["3.Cf3", "3...f5"]
    assert linha[-1].juizo == "?"


def test_a_linha_para_quando_o_numero_volta():
    # O 11... depois do 14. é variante: a linha para no mate.
    linha = lc.primeira_linha(TEXTO_P25, "pt")
    assert _sans(linha) == ["Kf8", "Qd5", "Nxd5", "Bxd6", "Kg8", "Bxd5", "Be6", "Bxe6"]
    assert linha[0].pretas and linha[0].numero == 10
    assert linha[3].marca == "+"


def test_figurinas_valem_em_qualquer_idioma_e_parentese_e_variante():
    linha = lc.primeira_linha("1.♘f3 ♞f6 2.♖g1 (2.g3 g6) 2...g6", "pt")
    assert _sans(linha) == ["Nf3", "Nf6", "Rg1"]
    assert linha[0].rotulo() == "1.♘f3"


def test_lance_solto_na_prosa_nao_comeca_linha():
    assert lc.primeira_linha("O peão de e4 domina d5 e f5.", "pt") == []
    assert _sans(lc.primeira_linha("O peão de e4 avança: 1.e5 Cd5", "pt")) == ["e5", "Nd5"]


def test_ingles_e_roque_com_zeros():
    linha = lc.primeira_linha("12.0-0 Qd7 13.Rfe1 O-O-O", "en")
    assert _sans(linha) == ["O-O", "Qd7", "Rfe1", "O-O-O"]


# ----------------------------------------------------------------------
# Validar
# ----------------------------------------------------------------------

def test_os_diagramas_do_livro_sao_confiaveis_pelos_lances():
    v23 = lc.validar(P23, lc.primeira_linha(TEXTO_P23, "pt"))
    v25 = lc.validar(P25, lc.primeira_linha(TEXTO_P25, "pt"), lado="b")
    assert v23.confiavel and v23.legais == 6 and v23.vez == "w"
    assert v25.confiavel and v25.numero == 10 and v25.lances[-1] == "Bxe6#"


def test_primeiro_lance_ilegal_diz_qual_e_onde():
    # O cavalo de g1 lido como bispo: 3.Cf3 não é legal.
    errada = P23.replace("KBNR", "KBBR")
    v = lc.validar(errada, lc.primeira_linha(TEXTO_P23, "pt"))
    assert v.estado == lc.ILEGAL and v.legais == 4
    assert v.aviso == "3.Cf3 do texto não é legal aqui"
    assert v.lances == ("e4", "e5", "f4", "exf4")


def test_lance_que_diz_mais_do_que_faz():
    linha = lc.primeira_linha("1.e4 e5 2.Cxf3", "pt")
    v = lc.validar(chess.STARTING_BOARD_FEN, linha)
    assert v.aviso == "2.Cxf3 do texto não captura nada aqui"
    v = lc.validar(chess.STARTING_BOARD_FEN, lc.primeira_linha("1.e4+", "pt"))
    assert v.aviso == "1.e4+ do texto não dá xeque aqui"


def test_lado_do_texto_contra_o_da_legenda():
    v = lc.validar(P25, lc.primeira_linha(TEXTO_P25, "pt"), lado="w")
    assert v.estado == lc.ILEGAL
    assert "jogam as pretas, mas o diagrama diz as brancas" in v.aviso


def test_sem_lances_nao_ha_validacao():
    assert lc.validar(P23, []) is None


def test_o_roque_do_texto_usa_o_inferido():
    pecas = "r3k2r/pppq1ppp/2n2n2/3pp3/3PP3/2N2N2/PPPQ1PPP/R3K2R"
    v = lc.validar(pecas, lc.primeira_linha("10.0-0-0 0-0", "pt"))
    assert v.confiavel and v.lances == ("O-O-O", "O-O")


def test_desmarcar_todos_os_roques_nao_volta_ao_inferido(tmp_path):
    pecas = "r3k2r/pppq1ppp/2n2n2/3pp3/3PP3/2N2N2/PPPQ1PPP/R3K2R"
    linha = lc.primeira_linha("10.0-0-0 0-0", "pt")
    assert not lc.validar(pecas, linha, roque="", roque_informado=True).confiavel

    # No diagrama: conferir com os roques todos desmarcados é dizer "sem roque".
    d = _lido(pecas + " w - - 0 1")
    tabuleiro = d.edicao()
    tabuleiro.definir_roque("KQkq")
    tabuleiro.definir_roque("")
    conferido = d.conferir(tabuleiro)
    assert conferido.roque == "" and conferido.roque_informado
    volta = dg.DiagramaLido.de_json(json.loads(json.dumps(conferido.para_json())))
    assert volta.roque_informado and volta.edicao().roque_informado
    # O gravado antes do campo, sem roque, ainda deixa o inferido valer.
    bruto = conferido.para_json()
    del bruto["roque_informado"]
    assert not dg.DiagramaLido.de_json(bruto).roque_informado


# ----------------------------------------------------------------------
# O roque inferido nunca vai ao FEN sem conferência (CA-10.3)
# ----------------------------------------------------------------------

def test_roque_inferido_nao_vai_ao_fen():
    d = _lido()                                     # r3k2r ... R3K2R: os quatro roques
    assert d.roque_inferido == "KQkq"
    assert d.fen.split()[2] == "-"
    assert "KQkq" not in d.linha_de_texto(1)


def test_roque_conferido_vai_ao_fen():
    d = _lido()
    tabuleiro = d.edicao()
    tabuleiro.definir_roque(d.roque_inferido)
    assert d.conferir(tabuleiro).fen.split()[2] == "KQkq"


def test_exportar_o_fen_do_diagrama_sem_conferir_nao_tem_roque():
    from PIL import Image

    from abbychess import exportar as ex

    figura = ex.figura_do_diagrama(Image.new("L", (800, 600), 255), _lido())
    assert figura.fen and figura.fen.split()[2] == "-"


# ----------------------------------------------------------------------
# PGN
# ----------------------------------------------------------------------

def _diagrama_validado(pecas, texto, lado=None):
    d = _lido(pecas)
    d = dg.DiagramaLido(d.caixa, casas=d.casas, lado=lado, lado_origem="legenda" if lado else "")
    linha = lc.primeira_linha(texto, "pt")
    return replace(d, validacao=lc.validar(d.fen, linha, lado=lado))


def test_pgn_do_diagrama_parte_da_posicao():
    d = _diagrama_validado(P25, TEXTO_P25, lado="b")
    pgn = lc.pgn_do_diagrama(d, {"Event": "Xadrez Vitorioso, p. 25"})
    jogo = chess.pgn.read_game(io.StringIO(pgn))
    assert jogo.headers["SetUp"] == "1"
    assert jogo.headers["FEN"] == P25 + " b - - 0 10"
    assert jogo.headers["Event"] == "Xadrez Vitorioso, p. 25"
    assert "10... Kf8 11. Qd5 $4 Nxd5" in pgn          # ?? vira o NAG 4
    assert jogo.end().board().is_checkmate()


def test_pgn_so_declara_o_roque_que_o_texto_jogou():
    pecas = "r3k2r/pppq1ppp/2n2n2/3pp3/3PP3/2N2N2/PPPQ1PPP/R3K2R"
    d = _diagrama_validado(pecas, "10.O-O-O h6")
    jogo = chess.pgn.read_game(io.StringIO(lc.pgn_do_diagrama(d)))
    assert jogo.headers["FEN"].split()[2] == "Q"
    assert [m.uci() for m in jogo.mainline_moves()] == ["e1c1", "h7h6"]


def test_pgn_do_lance_ilegal_para_nele_com_o_aviso():
    d = _diagrama_validado(P23.replace("KBNR", "KBBR"), TEXTO_P23)
    pgn = lc.pgn_do_diagrama(d)
    assert "3.Cf3 do texto não é legal aqui" in pgn
    assert len(list(chess.pgn.read_game(io.StringIO(pgn)).mainline_moves())) == 4


# ----------------------------------------------------------------------
# A página
# ----------------------------------------------------------------------

def _linha(texto: str, y: int, x: int = 0):
    boxes, cursor = [], x
    for char in texto:
        if char != " ":
            boxes.append(BoxEntry(char, cursor, y, cursor + 10, y + 20, 1.0, FONTE_MANUAL))
        cursor += 14
    return boxes


def test_validar_pagina_usa_o_texto_depois_do_diagrama():
    # As linhas sem vão alinhado: a ordem de leitura do core não vê colunas.
    boxes = (_linha("Observe a posição seguinte:", 0) + _linha("1.e4 e5 2.f4 exf4 3.Cf3 f5", 520)
             + _linha("Agora as brancas atacam.", 560))
    pagina = tx.pagina_avulsa(boxes, [_lido(P23, caixa=(0, 60, 400, 460))])
    diagramas = lc.validar_pagina(pagina, "pt")
    assert diagramas[0].validacao.confiavel
    assert diagramas[0].confiavel


def test_confirmar_uma_leitura_nao_monta_o_texto_de_novo(monkeypatch):
    """A validação é refeita em toda edição; o Enter que confirma a leitura muda só a fonte e
    a confiança do glifo, e o texto depois do diagrama é o mesmo: não é montado de novo
    (custava ~25 ms por Enter). Mudar um caractere monta, e o resultado é o de sem a cache."""
    boxes = (_linha("Observe a posição seguinte:", 0) + _linha("1.e4 e5 2.f4 exf4 3.Cf3 f5", 520)
             + _linha("Agora as brancas atacam.", 560))
    pagina = tx.pagina_avulsa(boxes, [_lido(P23, caixa=(0, 60, 400, 460))])
    montagens = []
    original = tx.montar
    monkeypatch.setattr(tx, "montar", lambda p, **k: montagens.append(1) or original(p, **k))
    lc._TEXTOS_VISTOS.clear()
    primeira = lc.validar_pagina(pagina, "pt")
    lance = next(b for b in pagina.boxes if b.entry.y1 == 520 and b.entry.char == "C")
    lance.entry.confidence, lance.entry.source = 0.3, "rede"
    assert lc.validar_pagina(pagina, "pt") == primeira and len(montagens) == 1
    # A moldura muda a ordem de leitura do core: entra na chave.
    sem_moldura = lc._chave_do_texto(pagina)
    lance.entry.moldura = True
    assert lc._chave_do_texto(pagina) != sem_moldura
    lance.entry.moldura = False
    lance.entry.char = "D"                                   # 3.Df3: outro lance, outro texto
    com_a_cache = lc.validar_pagina(pagina, "pt")
    assert len(montagens) == 2
    lc._TEXTOS_VISTOS.clear()
    assert lc.validar_pagina(pagina, "pt") == com_a_cache
    assert lc.textos_depois(original(pagina))["d0"].startswith("1.e4 e5 2.f4 exf4 3.Df3")


def test_o_texto_do_diagrama_vai_ate_o_proximo():
    boxes = (_linha("Primeiro:", 0) + _linha("1.e4 e5", 470) + _linha("Segundo:", 520)
             + _linha("1.d4 d5", 990))
    d0, d1 = _lido(P23, caixa=(0, 40, 400, 440)), _lido(P23, caixa=(0, 560, 400, 960))
    documento = tx.montar(tx.pagina_avulsa(boxes, [d0, d1]))
    textos = lc.textos_depois(documento)
    assert textos["d0"].startswith("1.e4 e5") and "1.d4" not in textos["d0"]
    assert textos["d1"] == "1.d4 d5"


def test_lance_ilegal_tira_a_confianca_do_porteiro():
    boxes = (_linha("Observe a posição seguinte:", 0) + _linha("1.Cd2 e5 2.e4 Cf6", 520)
             + _linha("Agora as brancas atacam.", 560))
    pagina = tx.pagina_avulsa(boxes, [_lido(P23, caixa=(0, 60, 400, 460))])
    d = lc.validar_pagina(pagina, "pt")[0]
    assert d.validacao.aviso == "1.Cd2 do texto não é legal aqui"
    assert not d.confiavel


def test_validacao_vai_e_volta_no_json():
    d = _diagrama_validado(P25, TEXTO_P25, lado="b")
    volta = dg.DiagramaLido.de_json(json.loads(json.dumps(d.para_json())))
    assert volta.validacao == d.validacao
    assert dg.DiagramaLido.de_json(_lido().para_json()).validacao is None


# ----------------------------------------------------------------------
# As perturbações e a medida (CA-10.1)
# ----------------------------------------------------------------------

def test_perturbacoes_sao_legais_reprodutiveis_e_diferentes():
    posicoes = [(P23, "w"), (P25, "b")]
    a, b = lc.perturbacoes(posicoes, 30), lc.perturbacoes(posicoes, 30)
    assert a == b and len(a) == 30
    assert {p.tipo for p in a} == {"trocada", "tirada", "movida"}
    for p in a:
        original = posicoes[p.origem][0]
        assert p.pecas != original
        board = chess.Board(None)
        board.set_board_fen(p.pecas)
        board.turn = posicoes[p.origem][1] == "w"
        assert board.is_valid()


def test_ca_10_1_no_gabarito_do_xadrez_vitorioso():
    sys.path.insert(0, str(RAIZ / "ferramentas"))
    import medir

    gabaritos = {f.stem: json.loads(f.read_text(encoding="utf-8"))
                 for f in (RAIZ / "tests" / "verdade" / "xv").glob("i*.json")}
    r = medir.validacao_pelos_lances(gabaritos)
    assert r["verdadeiros"] >= 2 and r["verdadeiros_confiaveis"] == r["verdadeiros"]
    assert r["perturbadas"] == 100 and r["afetadas"] > 0
    assert r["deteccao"] >= 0.6
    assert r["confiaveis_afetadas"] == 0


# ----------------------------------------------------------------------
# A revisão de código (rodada 1)
# ----------------------------------------------------------------------

def test_numero_separado_do_lance_e_reticencias_curtas():
    assert _sans(lc.primeira_linha("1. e4 e5 2. Cf3 Cc6 3.Bb5", "pt")) == [
        "e4", "e5", "Nf3", "Nc6", "Bb5"]
    linha = lc.primeira_linha("1..e5 2.Cf3", "pt")
    assert linha[0].pretas and _sans(linha) == ["e5", "Nf3"]


def test_linha_legal_nao_anula_a_duvida_do_porteiro():
    boxes = (_linha("Observe a posição seguinte:", 0) + _linha("1.e4 e5 2.f4 exf4 3.Cf3 f5", 520)
             + _linha("Agora as brancas atacam.", 560))
    pagina = tx.pagina_avulsa(boxes, [_lido(P23, caixa=(0, 60, 400, 460), motivo="casa duvidosa")])
    d = lc.validar_pagina(pagina, "pt")[0]
    assert d.validacao.confiavel and not d.confiavel


def test_o_numero_do_lance_diz_o_lado_quando_ninguem_disse():
    boxes = (_linha("Observe a posição seguinte:", 0) + _linha("10...Rf8 11.Dd5 Dd7 12.Dxd4", 520)
             + _linha("Agora as brancas atacam.", 560))
    pagina = tx.pagina_avulsa(boxes, [_lido(P25, caixa=(0, 60, 400, 460))])
    d = lc.validar_pagina(pagina, "pt")[0]
    assert d.validacao.confiavel and d.lado == "b" and d.lado_origem == lc.LADO_DOS_LANCES
    assert d.fen.split()[1] == "b"
    assert "pretas a jogar (pelo número do lance do texto, 10...Rf8)" in d.linha_de_texto(1)
    assert lc.pgn_do_diagrama(d).count(" b - - 0 10") == 1
    # O texto mudou e não diz mais: o lado volta a não dito.
    pagina = tx.pagina_avulsa(_linha("Observe a posição seguinte:", 0), [d])
    assert lc.validar_pagina(pagina, "pt")[0].lado is None


def test_texto_do_diagrama_por_ler_nao_cai_no_anterior():
    boxes = (_linha("Primeiro:", 0) + _linha("Nada aqui.", 470) + _linha("Segundo:", 520)
             + _linha("1.d4 d5", 990))
    d0 = replace(_lido(P23, caixa=(0, 40, 400, 440)), id="d0")
    pagina = tx.pagina_avulsa(boxes, [d0])
    pagina.tabuleiros = [(0, 40, 400, 440), (0, 560, 400, 960)]   # o segundo, por ler
    assert lc.validar_pagina(pagina, "pt")[0].validacao is None


def test_entradas_estranhas_nao_derrubam():
    assert lc.validar("", lc.primeira_linha("1.e4", "pt")) is None
    assert lc.validar("isto não é FEN", lc.primeira_linha("1.e4", "pt")).estado == lc.ILEGAL
    assert lc.pgn_do_diagrama(dg.DiagramaLido((0, 0, 10, 10))) == ""
    assert lc.Validacao.de_json({"estado": lc.CONFIAVEL, "total": "x"}) is None