"""As perturbações do CA-10.1 (SPEC §10): versões de uma posição com uma peça trocada,
tirada ou movida, para medir a validação pelos lances (`ferramentas/medir.py`).

Saíram de `lances.py` no fechamento do passo H: lá fica o que o programa usa (ler a linha de
lances, validar, o PGN); aqui, o que só a medida usa. **Afetada** é a perturbada que toca uma
casa usada por um lance da linha: de onde sai, aonde chega, o caminho e a torre do roque.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

import chess

from abbychess.lances import _tabuleiro, roque_inferido



@dataclass(frozen=True)
class Perturbacao:
    #: A posição perturbada (só as peças), de onde veio e o que mudou.
    pecas: str
    origem: int
    tipo: str
    casas: Tuple[str, ...]


_TIPOS = ("trocada", "tirada", "movida")


def perturbar(pecas: str, vez: str, rng: random.Random, origem: int = 0,
              tentativas: int = 500) -> Optional[Perturbacao]:
    """Uma versão da posição com uma peça trocada, tirada ou movida, ainda legal com `vez`
    a jogar (sem roque). `None` se nenhuma tentativa der posição legal."""
    original = chess.Board(None)
    original.set_board_fen(pecas.split()[0])
    for _ in range(tentativas):
        board = original.copy()
        tipo = rng.choice(_TIPOS)
        ocupadas = sorted(board.piece_map())
        sem_rei = [c for c in ocupadas if board.piece_type_at(c) != chess.KING]
        vazias = [c for c in chess.SQUARES if c not in board.piece_map()]
        if tipo == "trocada" and sem_rei:
            casa = rng.choice(sem_rei)
            antiga = board.piece_at(casa)
            nova = chess.Piece(rng.choice([chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK,
                                           chess.QUEEN]), rng.choice([chess.WHITE, chess.BLACK]))
            if nova == antiga:
                continue
            board.set_piece_at(casa, nova)
            casas = (chess.square_name(casa),)
        elif tipo == "tirada" and sem_rei:
            casa = rng.choice(sem_rei)
            board.remove_piece_at(casa)
            casas = (chess.square_name(casa),)
        elif tipo == "movida" and vazias:
            de, para = rng.choice(ocupadas), rng.choice(vazias)
            board.set_piece_at(para, board.remove_piece_at(de))
            casas = (chess.square_name(de), chess.square_name(para))
        else:
            continue
        board.turn = vez != "b"
        if board.is_valid():
            return Perturbacao(board.board_fen(), origem, tipo, casas)
    return None


def perturbacoes(posicoes: Sequence[Tuple[str, str]], n: int = 100,
                 semente: int = 1234) -> List[Perturbacao]:
    """`n` perturbações das posições `(peças, vez)`, uma de cada por vez, com a semente."""
    rng = random.Random(semente)
    saida: List[Perturbacao] = []
    if not posicoes:
        return saida
    falhas = 0
    while len(saida) < n and falhas < 10 * n:
        origem = len(saida) % len(posicoes)
        pecas, vez = posicoes[origem]
        p = perturbar(pecas, vez, rng, origem)
        if p is None:
            falhas += 1
            continue
        saida.append(p)
    return saida


def casas_dos_lances(pecas: str, vez: str, sans: Sequence[str], numero: int = 1) -> List[set]:
    """As casas que cada lance usa, na posição verdadeira: de onde sai, aonde chega, o
    caminho, e a torre no roque. É o "lance afetado" do CA-10.1: uma perturbação que toca
    uma dessas casas afeta o lance."""
    board = _tabuleiro(pecas, vez, roque_inferido(pecas), numero)
    saida: List[set] = []
    for san in sans:
        movimento = board.parse_san(san)
        casas = {movimento.from_square, movimento.to_square}
        casas |= set(chess.SquareSet.between(movimento.from_square, movimento.to_square))
        if board.is_castling(movimento):
            torre = movimento.to_square if board.chess960 else (
                chess.H1 if movimento.to_square == chess.G1 else
                chess.A1 if movimento.to_square == chess.C1 else
                chess.H8 if movimento.to_square == chess.G8 else chess.A8)
            casas |= {torre} | set(chess.SquareSet.between(movimento.from_square, torre))
        if board.is_en_passant(movimento):
            casas.add(chess.square(chess.square_file(movimento.to_square),
                                   chess.square_rank(movimento.from_square)))
        saida.append({chess.square_name(c) for c in casas})
        board.push(movimento)
    return saida


def afetada(p: Perturbacao, casas: Iterable[set]) -> bool:
    """A perturbação toca alguma casa usada por um lance da linha."""
    tocadas = set(p.casas)
    return any(tocadas & c for c in casas)
