"""O estado de cada box para o desenho e a grade que acha boxes por ponto e por retângulo.

**Estados** (SPEC §13, os tokens de `app/estilo.py`): `PENDENTE` (vai para a revisão),
`SEM_LEITURA` (lido, e ninguém soube o que é), `AGUARDANDO` (ainda não lido: o box que a
segmentação achou e a leitura não alcançou, como no servidor do passo E), e os aceitos pela
origem: `MANUAL` (o usuário decidiu), `LIVRO` (um padrão deste livro), `REDE` (a rede ou a
base global, acima do limiar). Por padrão os aceitos saem discretos; com "mostrar origem"
(V) cada origem tem a sua cor.

**A grade** divide a página em células de `LADO` pixels e lembra, por célula, os boxes que
a tocam: o clique olha uma célula, e o desenho de um retângulo só os boxes das células dele,
em vez de varrer a página inteira (CA-3.5: 2.000 boxes, clique em ≤ 2 ms).

Sem Qt.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from core.box_model import BoxEntry

from abbychess.leitor import FONTE_LIVRO, FONTE_MANUAL

PENDENTE = "pendente"
SEM_LEITURA = "sem_leitura"
AGUARDANDO = "aguardando"
MANUAL = "manual"
LIVRO = "livro"
REDE = "rede"
ESTADOS = (PENDENTE, SEM_LEITURA, AGUARDANDO, MANUAL, LIVRO, REDE)
#: Os aceitos: discretos, a não ser com "mostrar origem".
ACEITOS = (MANUAL, LIVRO, REDE)

#: O lado da célula da grade, em pixels da página (um glifo a 300 dpi tem ~20–60).
LADO = 64


def estado(box: BoxEntry, pendente: bool) -> str:
    """O estado de desenho do box (`pendente` é o que a fila de revisão diz dele)."""
    if box.source == FONTE_MANUAL:
        return MANUAL
    if not box.char:
        return AGUARDANDO if not box.source else SEM_LEITURA
    if pendente:
        return PENDENTE
    return LIVRO if box.source == FONTE_LIVRO else REDE


class GradeDeCaixas:
    """As caixas da página numa grade de células, para achar por ponto e por retângulo."""

    def __init__(self, caixas: Sequence[Tuple[int, int, int, int]] = (), lado: int = LADO):
        self.lado = lado
        self.caixas: List[Tuple[int, int, int, int]] = []
        self._celulas: Dict[Tuple[int, int], List[int]] = defaultdict(list)
        self.trocar(caixas)

    def trocar(self, caixas: Sequence[Tuple[int, int, int, int]]) -> None:
        self.caixas = [tuple(int(v) for v in c) for c in caixas]
        self._celulas = defaultdict(list)
        for i, caixa in enumerate(self.caixas):
            for celula in self._celulas_de(caixa):
                self._celulas[celula].append(i)

    def mover(self, indice: int, caixa: Tuple[int, int, int, int]) -> None:
        """A caixa `indice` mudou (o Alt+seta): sai das células velhas, entra nas novas."""
        velha = self.caixas[indice]
        for celula in self._celulas_de(velha):
            lista = self._celulas.get(celula)
            if lista is not None and indice in lista:
                lista.remove(indice)
        self.caixas[indice] = tuple(int(v) for v in caixa)
        for celula in self._celulas_de(self.caixas[indice]):
            self._celulas[celula].append(indice)

    def _celulas_de(self, caixa) -> Iterable[Tuple[int, int]]:
        x1, y1, x2, y2 = caixa
        lado = self.lado
        for cx in range(int(x1) // lado, int(max(x1, x2 - 1)) // lado + 1):
            for cy in range(int(y1) // lado, int(max(y1, y2 - 1)) // lado + 1):
                yield cx, cy

    def no_ponto(self, x: float, y: float) -> Optional[int]:
        """O box que contém o ponto; se mais de um, o menor (o glifo dentro do outro)."""
        candidatos = self._celulas.get((int(x) // self.lado, int(y) // self.lado), ())
        melhor: Optional[Tuple[int, int]] = None
        for i in candidatos:
            x1, y1, x2, y2 = self.caixas[i]
            if x1 <= x <= x2 and y1 <= y <= y2:
                area = (x2 - x1) * (y2 - y1)
                if melhor is None or (area, i) < melhor:
                    melhor = (area, i)
        return melhor[1] if melhor is not None else None

    def no_retangulo(self, x1: float, y1: float, x2: float, y2: float) -> Set[int]:
        """Os boxes que tocam o retângulo (o que um `paint` precisa desenhar)."""
        achados: Set[int] = set()
        lado = self.lado
        for cx in range(int(x1) // lado, int(x2) // lado + 1):
            for cy in range(int(y1) // lado, int(y2) // lado + 1):
                for i in self._celulas.get((cx, cy), ()):
                    a1, b1, a2, b2 = self.caixas[i]
                    if a1 <= x2 and a2 >= x1 and b1 <= y2 and b2 >= y1:
                        achados.add(i)
        return achados
