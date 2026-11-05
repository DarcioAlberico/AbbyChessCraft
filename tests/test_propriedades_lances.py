"""Q-T6: a ida e volta dos lances e do FEN dos diagramas (§10).

- **PGN → lances → PGN.** Uma posição legal (lances ao acaso desde a inicial) e uma linha que a
  segue, impressas como um livro as imprime (`1.e4 e5 2.♘f3`, `12...Tf8`), com as letras do
  idioma (`modelo.PECAS`) ou as figurinas: `primeira_linha` lê os mesmos lances, `validar` os
  aceita todos (o diagrama fica confiável pelos lances) com os mesmos SAN, e o PGN do diagrama
  tem a posição e a linha. Lido de volta (o texto dos lances do PGN, em inglês), dá o mesmo
  PGN.
- **FEN → posição → FEN.** Qualquer arranjo de peças, com o lado e o roque ditos: o diagrama
  (`DiagramaLido`) dá o mesmo FEN; gravado e relido (`para_json`), e passado pelo editor de
  posição (`edicao`, `conferir`), também.

O lance da linha que só vale com a casa de *en passant* não entra: o diagrama não diz qual
foi o último lance, e a posição dele não tem a casa, salvo no primeiro lance
(`tests/test_lances.py`).
"""

from __future__ import annotations

import io

import chess
import chess.pgn
from hypothesis import assume
from hypothesis import strategies as st

from abbychess import diagramas as dg
from abbychess import lances as lc
from abbychess.modelo import PECAS

from tests.ajudantes import _lido
from tests.estrategias import propriedade

FIGURINAS = dict(zip("KQRBN", "♔♕♖♗♘"))
#: O modo de impressão das peças: as letras de um idioma, ou as figurinas.
MODOS = sorted(PECAS) + ["figurinas"]


def _jogar(board: chess.Board, escolhas) -> list:
    """Os lances de `escolhas` (cada um, o índice entre os legais), até acabarem os legais."""
    jogados = []
    for k in escolhas:
        legais = list(board.legal_moves)
        if not legais:
            break
        movimento = legais[k % len(legais)]
        jogados.append(movimento)
        board.push(movimento)
    return jogados


def _impresso(san: str, modo: str) -> str:
    """O SAN inglês como o livro o imprime: as letras das peças do idioma, ou as figurinas
    (o O do roque não é peça)."""
    tabela = FIGURINAS if modo == "figurinas" else dict(zip("KQRBN", PECAS[modo]))
    return "".join(tabela.get(c, c) for c in san)


def _linha_impressa(board: chess.Board, movimentos, modo: str) -> tuple:
    """O texto da linha (`5.e4 e5 6.♘f3`, `5...e5 6.♘f3`) e os SAN, a partir de `board`."""
    board = board.copy()
    partes, sans = [], []
    for k, movimento in enumerate(movimentos):
        san = board.san(movimento)
        impresso = _impresso(san, modo)
        if board.turn == chess.WHITE:
            partes.append(f"{board.fullmove_number}.{impresso}")
        else:
            partes.append(f"{board.fullmove_number}...{impresso}" if k == 0 else impresso)
        sans.append(san)
        board.push(movimento)
    return " ".join(partes), sans


def _validado(board, linha):
    """O diagrama da posição (só as peças: o lado e o roque, ninguém disse) validado pela linha."""
    pecas = board.board_fen()
    validacao = lc.validar(f"{pecas} w - - 0 1", linha)
    return _lido(pecas, validacao=validacao), validacao


def lei_dos_lances(abertura, seguinte, modo):
    """A linha impressa é lida, validada e vai ao PGN com os mesmos lances; o PGN relido dá o
    mesmo PGN."""
    board = chess.Board()
    _jogar(board, abertura)
    inicio = board.copy()
    movimentos = _jogar(board, seguinte)
    assume(movimentos and not inicio.is_en_passant(movimentos[0]))
    texto, sans = _linha_impressa(inicio, movimentos, modo)
    linha = lc.primeira_linha(texto, modo if modo in PECAS else "pt")
    assert [lance.san for lance in linha] == [s.rstrip("+#") for s in sans], texto
    diagrama, validacao = _validado(inicio, linha)
    assert validacao.estado == lc.CONFIAVEL, (texto, validacao.aviso)
    assert list(validacao.lances) == sans and validacao.legais == len(sans)
    assert validacao.vez == ("w" if inicio.turn else "b")
    assert validacao.numero == inicio.fullmove_number
    pgn = lc.pgn_do_diagrama(diagrama)
    jogo = chess.pgn.read_game(io.StringIO(pgn))
    assert jogo.board().board_fen() == inicio.board_fen()
    assert jogo.board().turn == inicio.turn
    assert [n.san() for n in jogo.mainline()] == sans
    # PGN -> lances -> PGN: o texto dos lances do PGN (em inglês) dá o mesmo PGN.
    lances_do_pgn = jogo.accept(chess.pgn.StringExporter(headers=False, comments=False))
    de_novo, _ = _validado(inicio, lc.primeira_linha(lances_do_pgn, "en"))
    assert lc.pgn_do_diagrama(de_novo) == pgn


ESCOLHAS = st.lists(st.integers(0, 200), max_size=40)

test_os_lances_vao_do_texto_ao_pgn_e_voltam, \
    test_os_lances_vao_do_texto_ao_pgn_e_voltam_noturna = propriedade(
        lei_dos_lances, rapida=30,
        abertura=ESCOLHAS, seguinte=st.lists(st.integers(0, 200), min_size=1, max_size=8),
        modo=st.sampled_from(MODOS))


# ----------------------------------------------------------------------
# FEN -> posição -> FEN
# ----------------------------------------------------------------------

CASA = st.one_of(st.just(None), st.just(None), st.sampled_from("PNBRQKpnbrqk"))


def _pecas(casas) -> str:
    """O campo das peças do FEN das 64 casas (de a8 a h1)."""
    board = chess.Board(None)
    for k, simbolo in enumerate(casas):
        if simbolo:
            board.set_piece_at(chess.square(k % 8, 7 - k // 8), chess.Piece.from_symbol(simbolo))
    return board.board_fen()


def lei_do_fen(casas, lado, roque):
    """O FEN do diagrama é o das peças, do lado e do roque ditos (o roque que rei e torre não
    permitem cai); gravado e relido, e passado pelo editor de posição, é o mesmo."""
    pecas = _pecas(casas)
    diagrama = _lido(pecas, lado=lado, lado_origem=dg.LADO_DO_USUARIO, roque=roque,
                     roque_informado=True)
    possivel = "".join(c for c in roque if c in lc.roque_inferido(pecas))
    assert diagrama.fen == f"{pecas} {lado} {possivel or '-'} - 0 1"
    assert dg.DiagramaLido.de_json(diagrama.para_json()).fen == diagrama.fen
    assert diagrama.conferir(diagrama.edicao()).fen == diagrama.fen


test_o_fen_do_diagrama_vai_e_volta, test_o_fen_do_diagrama_vai_e_volta_noturna = propriedade(
    lei_do_fen, rapida=20,
    casas=st.lists(CASA, min_size=64, max_size=64), lado=st.sampled_from("wb"),
    roque=st.sampled_from(["", "K", "Qk", "KQkq", "kq"]))
