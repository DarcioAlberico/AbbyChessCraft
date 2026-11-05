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
from abbychess import perturbacoes as pt
from abbychess import texto as tx
from abbychess.leitor import FONTE_MANUAL

from tests.ajudantes import _lido  # noqa: E402,F401,F811
from tests.ajudantes import P25, TEXTO_P25  # noqa: E402,F401,F811

RAIZ = Path(__file__).resolve().parent.parent

#: Xadrez Vitorioso, p. 23 (Diagrama 4: sem o cavalo de b1) e p. 25 (Diagrama 5).
P23 = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/R1BQKBNR"
TEXTO_P23 = ("1.e4 e5 2.f4\nAs brancas mostram imediatamente que estão dispostas a entregar\n"
             "2...exf4 3.Cf3 f5?\nUm lance muito ruim. Seria melhor algo como 2...d5 (que")


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


def test_os_sinais_da_paleta_nao_separam_o_lance_da_resposta():
    for sinal in "⯹⇄⟳○⨀⨁⇔⇗⊞⟪⟫✕⊥⯺⯻⯼⯽":
        assert _sans(lc.primeira_linha(f"1.e4 {sinal} e5", "pt")) == ["e4", "e5"], sinal
    # O Δ anuncia outro lance, que não é a resposta das pretas.
    assert _sans(lc.primeira_linha("1.e4 Δ Cf3", "pt")) == ["e4"]


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

    from abbychess import montagem as mo

    figura = mo.figura_do_diagrama(Image.new("L", (800, 600), 255), _lido())
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
    a, b = pt.perturbacoes(posicoes, 30), pt.perturbacoes(posicoes, 30)
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


def test_numero_e_fileira_lidos_com_letras_pelo_ocr():
    """Mirkovic, *Chess School 1*: o `1` lido como `l` no número ("l.d6", "l9...") e na casa
    ("♔fl"), e o `0` como `o` ("l0.f3"). Sem isso a linha começava num lance de variante."""
    linha = lc.primeira_linha("l9...♘f2! 20.♔f2 ♕h4 2l.♔fl ♕h2", "en")
    assert [(lance.numero, lance.pretas) for lance in linha][:2] == [(19, True), (20, False)]
    assert _sans(linha) == ["Nf2", "Kf2", "Qh4", "Kf1", "Qh2"]
    assert _sans(lc.primeira_linha("l.d6! defeat would be l.♔b3?", "en")) == ["d6"]
    assert lc.primeira_linha("l0.f3 c5", "en")[0].numero == 10
    assert lc.primeira_linha("l...♔d7 2.♔e3", "en")[0].pretas


def test_letras_soltas_nao_viram_numero_nem_casa():
    """"lo." é palavra, "I." é inicial, e o "el" do espanhol não é e1 (só no lance de peça)."""
    assert _sans(lc.primeira_linha("eso lo. I. Ivanov jugó 1.e4", "es")) == ["e4"]
    assert lc.primeira_linha("el peón", "es") == []


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

def test_conferir_sem_tocar_no_lado_mantem_o_que_os_lances_dizem():
    """O lado que só o número do lance dizia (10...): o editor abre com ele, e conferir sem
    tocar no lado não o troca por "brancas, assumido" (o FEN, o texto e o PGN concordam)."""
    boxes = (_linha("Observe a posição seguinte:", 0) + _linha("10...Rf8 11.Dd5 Dd7 12.Dxd4", 520)
             + _linha("Agora as brancas atacam.", 560))
    pagina = tx.pagina_avulsa(boxes, [_lido(P25, caixa=(0, 60, 400, 460))])
    d = lc.validar_pagina(pagina, "pt")[0]
    tabuleiro = d.edicao()
    assert tabuleiro.lado == "b" and tabuleiro.fen().split()[1] == "b"
    pagina.diagramas = [d.conferir(tabuleiro)]
    conferido = lc.validar_pagina(pagina, "pt")[0]
    assert conferido.conferido and conferido.lado == "b"
    assert conferido.lado_origem == lc.LADO_DOS_LANCES and conferido.fen.split()[1] == "b"
    assert lc.pgn_do_diagrama(conferido).count(" b - - 0 10") == 1


def test_o_roque_que_uma_casa_corrigida_impede_nao_vai_ao_fen():
    """Marcar o roque e depois tirar a torre: o FEN conferido sai sem o direito impossível
    (antes, um FEN inválido que caía do PGN)."""
    d = _lido("4k2r/8/8/8/8/8/8/4K2R")
    tabuleiro = d.edicao()
    tabuleiro.definir_roque("Kk")
    tabuleiro.limpar(7, 7)                              # a torre de h1
    conferido = d.conferir(tabuleiro)
    assert conferido.fen.split()[2] == "k"
    assert chess.Board(conferido.fen).is_valid()


# ----------------------------------------------------------------------
# As regras que a mutação achou sem teste (Q9, CA-Q-M1)
# ----------------------------------------------------------------------

def _jogo(diagrama):
    return chess.pgn.read_game(io.StringIO(lc.pgn_do_diagrama(diagrama)))


def test_palavras_que_parecem_numero_ou_casa_nao_entram_na_linha():
    """O "el" depois do lance não é e1; "lo." não é o lance 10; "2I." solto (uma referência)
    não é número, e colado ao lance ("2I.Cf3") é o 21 que o OCR leu."""
    assert _sans(lc.primeira_linha("1.e4 el peón", "es")) == ["e4"]
    assert lc.primeira_linha("y no lo. Cf3 Cc6", "es") == []
    assert lc.primeira_linha("Tabla 2I. Cf3 Cc6", "es") == []
    assert [(lance.numero, lance.pretas) for lance in lc.primeira_linha("2I.Cf3 Cc6", "es")] == [
        (21, False), (21, True)]


def test_a_variante_sem_numero_e_o_parentese_que_fecha_acabam_a_linha():
    assert _sans(lc.primeira_linha("1.e4 (d4) e5 2.Cf3", "pt")) == ["e4"]
    # O diagrama no meio de uma variante: a linha acaba no parêntese que a fecha.
    assert _sans(lc.primeira_linha("12.Te1 Cf6) 13.Dd2 Dd7", "pt")) == ["Re1", "Nf6"]


def test_o_lance_das_brancas_sem_numero_acaba_a_linha():
    assert _sans(lc.primeira_linha("1.e4 e5 Cf3 é o natural, mas 2.Bc4 Cf6", "pt")) == ["e4", "e5"]


def test_o_mate_do_texto_tem_de_ser_mate():
    v = lc.validar(chess.STARTING_BOARD_FEN, lc.primeira_linha("1.e4#", "pt"))
    assert v.aviso == "1.e4# do texto não dá mate aqui"
    v = lc.validar(chess.STARTING_BOARD_FEN, lc.primeira_linha("1.f3 e5 2.g4 Dh4#", "pt"))
    assert v.confiavel and v.lances[-1] == "Qh4#"


def test_a_posicao_que_nao_vale_nao_passa_lance_nenhum():
    assert lc.validar(P25, lc.primeira_linha(TEXTO_P25, "pt"), lado="w") == lc.Validacao(
        lc.ILEGAL, 8, 0, "10...Rf8 do texto diz que jogam as pretas, mas o diagrama diz as brancas",
        "b", 10)
    assert lc.validar("isto não é FEN", lc.primeira_linha("1.e4", "pt")) == lc.Validacao(
        lc.ILEGAL, 1, 0, "a posição lida não é legal com as brancas a jogar", "w", 1)
    # O lance 0 (que nenhum livro imprime) conta como o 1.
    assert lc.validar(chess.STARTING_BOARD_FEN, lc.primeira_linha("0.e4 e5", "pt")).numero == 1


def test_a_validacao_gravada_sem_os_campos_novos_volta_com_os_padroes():
    assert lc.Validacao.de_json({"estado": lc.CONFIAVEL, "lances": ["e4", "e5"]}) == lc.Validacao(
        lc.CONFIAVEL, 0, 0, "", "", 1, ("e4", "e5"), ("", ""))
    assert lc.Validacao.de_json({"estado": lc.ILEGAL, "numero": 0}).numero == 1


def test_o_texto_do_diagrama_nao_tem_a_legenda():
    from abbychess.zonas import Zona

    boxes = _linha("Observe:", 0) + _linha("Brancas jogam", 470) + _linha("1.e4 e5", 520)
    legenda = Zona("texto", 0, 465, 400, 495, id="z1", funcao="legenda")
    pagina = tx.pagina_avulsa(boxes, [_lido(P23, caixa=(0, 40, 400, 440))], [legenda])
    assert lc.textos_depois(tx.montar(pagina)) == {"d0": "1.e4 e5"}


def test_o_diagrama_que_deixou_de_estar_lido_perde_a_validacao_e_o_lado_dos_lances():
    validado = _diagrama_validado(P25, TEXTO_P25, lado="b")
    outra = (0, 500, 400, 900)
    por_ler = [dg.DiagramaLido(validado.caixa, id="d0", validacao=validado.validacao, lado="b",
                               lado_origem="legenda"),
               dg.DiagramaLido(outra, id="d1", lado="b", lado_origem=lc.LADO_DOS_LANCES,
                               lado_trecho="10...Rf8")]
    pagina = tx.pagina_avulsa(_linha("1.e4 e5", 950), por_ler)
    assert lc.validar_pagina(pagina, "pt") == [
        dg.DiagramaLido(validado.caixa, id="d0", lado="b", lado_origem="legenda"),
        dg.DiagramaLido(outra, id="d1")]


def test_o_pgn_comeca_no_lance_do_texto_com_o_lado_dele():
    """Sem lances, o lance 1 das brancas; com eles, o número e o lado do texto, mesmo contra
    a legenda; sem eles, o lado do diagrama."""
    assert _jogo(_lido(P23)).headers["FEN"] == P23 + " w - - 0 1"
    assert _jogo(_diagrama_validado(P23, "1.e4 e5")).headers["FEN"] == P23 + " w - - 0 1"
    assert _jogo(_diagrama_validado(P25, TEXTO_P25, lado="w")).headers["FEN"] == P25 + " b - - 0 10"
    d = _lido(P25)
    pela_legenda = dg.DiagramaLido(d.caixa, casas=d.casas, lado="b", lado_origem="legenda")
    assert _jogo(pela_legenda).headers["FEN"] == P25 + " b - - 0 1"


def test_o_pgn_da_validacao_de_outra_posicao_para_no_lance_que_nao_cabe():
    """A validação gravada é de outra posição (a casa corrigida depois): o PGN não joga nem
    declara o roque dos lances que vêm depois do primeiro que não cabe."""
    pecas = "r3k2r/8/8/8/8/8/8/R3K2R"
    gravada = lc.Validacao.de_json({"estado": lc.CONFIAVEL, "total": 3, "legais": 3, "vez": "w",
                                    "numero": 1, "lances": ["Qd5", "O-O", "Ra2"]})
    jogo = _jogo(replace(_lido(pecas), validacao=gravada))
    assert jogo.headers["FEN"] == pecas + " w - - 0 1"
    assert list(jogo.mainline_moves()) == []


def test_o_comentario_do_pgn_diz_se_a_posicao_foi_conferida():
    assert _jogo(_diagrama_validado(P23, TEXTO_P23)).comment == (
        "posição lida, não conferida; confiável pelos lances")
    assert _jogo(_diagrama_validado(P23.replace("KBNR", "KBBR"), TEXTO_P23)).comment == (
        "posição lida, não conferida")
    assert _jogo(_lido(P23)).comment == "posição lida, não conferida"
    d = _diagrama_validado(P23, TEXTO_P23)
    assert _jogo(d.conferir(d.edicao())).comment == ""


def test_o_aviso_do_primeiro_lance_ilegal_fica_no_pgn_da_posicao_nao_conferida():
    """Nenhum lance passa (o primeiro já é ilegal): o aviso e a posição não conferida vão os
    dois para o comentário do jogo, e um não apaga o outro."""
    d = _diagrama_validado(P23, "1.Cd2 e5 2.e4")
    jogo = _jogo(d)
    assert list(jogo.mainline_moves()) == []
    assert jogo.comment == "posição lida, não conferida; [1.Cd2 do texto não é legal aqui]"
    assert _jogo(d.conferir(d.edicao())).comment == "[1.Cd2 do texto não é legal aqui]"
