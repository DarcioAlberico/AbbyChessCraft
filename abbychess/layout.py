"""Análise de layout compartilhada pelo Documento e pela exportação.

O primeiro estágio público é a ordem de leitura em colunas. Ele divide a página em trechos
independentes antes de formar linhas, para que o rodapé de uma coluna nunca se misture ao
topo da seguinte. Faixas que atravessam a calha, como títulos, ficam entre os trechos.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from core.box_model import BoxEntry

MARGEM_DA_CALHA = 0.25
# O Documento é refeito a cada edição e recebe páginas ainda incompletas. Exigimos mais
# evidência que a exportação legada: três filas curtas aparecem por acaso depois de dividir
# ou juntar boxes; seis mantêm esses rascunhos em uma coluna e ainda cobrem páginas reais.
FILAS_DE_COLUNA = 6
ChaveDeLeitura = Tuple[int, int]


def _coluna_de(x: float, colunas: Sequence[Tuple[int, int]]) -> int:
    """A coluna que contém ``x`` ou, na calha, a coluna mais próxima."""
    for i, (inicio, fim) in enumerate(colunas):
        if inicio <= x <= fim:
            return i
    return min(range(len(colunas)),
               key=lambda i: min(abs(x - colunas[i][0]), abs(x - colunas[i][1])))


@dataclass(frozen=True)
class OrdemDeLeitura:
    """Colunas e faixas transversais de uma página, numa interface sem detalhes do core."""

    colunas: Tuple[Tuple[int, int], ...] = ()
    faixas: Tuple[Tuple[float, float], ...] = ()
    #: A detecção do core sobre a página inteira; quando a página é um trecho só, o core a
    #: reaproveita (`deteccao_do_trecho`) em vez de refazê-la: ela é a parte mais cara de
    #: montar o texto, e o índice da busca monta o de todas as páginas.
    deteccao: object = field(default=None, compare=False, repr=False)

    @classmethod
    def da_pagina(cls, boxes: Sequence[BoxEntry]) -> "OrdemDeLeitura":
        from core.services.box_service import BoxService

        if len(boxes) < 2:
            return cls()
        deteccao = BoxService.detectar_colunas_e_transversais(list(boxes))
        colunas = deteccao[0]
        if len(colunas) < 2:
            return cls(deteccao=deteccao)
        altura = statistics.median(b.y2 - b.y1 for b in boxes)
        filas = [{round(((b.y1 + b.y2) / 2) / max(1.0, altura)) for b in boxes
                  if inicio <= (b.x1 + b.x2) / 2 <= fim} for inicio, fim in colunas]
        if min(len(fila) for fila in filas) < FILAS_DE_COLUNA:
            return cls(deteccao=deteccao)
        calhas = []
        for esquerda, direita in zip(colunas, colunas[1:]):
            largura = direita[0] - esquerda[1]
            calhas.append((esquerda[1] + MARGEM_DA_CALHA * largura,
                           direita[0] - MARGEM_DA_CALHA * largura,
                           (esquerda[1] + direita[0]) / 2))
        na_calha = sorted(
            (b for b in boxes if b.height >= 0.5 * altura and any(
                inicio < (b.x1 + b.x2) / 2 < fim or b.x1 < meio < b.x2
                for inicio, fim, meio in calhas)),
            key=lambda b: b.y1)
        grupos: List[List[BoxEntry]] = []
        for box in na_calha:
            if grupos and box.y1 <= max(outro.y2 for outro in grupos[-1]):
                grupos[-1].append(box)
            else:
                grupos.append([box])
        faixas = [(min(b.y1 for b in grupo), max(b.y2 for b in grupo)) for grupo in grupos
                  if len(grupo) >= 2 or max(b.height for b in grupo) >= 1.5 * altura]
        return cls(tuple(tuple(c) for c in colunas), tuple(faixas))

    def chave(self, x: float, y: float) -> ChaveDeLeitura:
        if not self.colunas:
            return 0, 0
        faixa = 2 * len(self.faixas)
        for k, (topo, pe) in enumerate(self.faixas):
            if topo <= y <= pe:
                faixa = 2 * k + 1
                break
            if y < topo:
                faixa = 2 * k
                break
        return faixa, 0 if faixa % 2 else _coluna_de(x, self.colunas)

    def trechos(self, boxes: Sequence[BoxEntry]) -> List[Tuple[ChaveDeLeitura, List[int]]]:
        """Índices agrupados por trecho, na ordem em que a página deve ser lida."""
        por_trecho: Dict[ChaveDeLeitura, List[int]] = {}
        for i, box in enumerate(boxes):
            chave = self.chave((box.x1 + box.x2) / 2, (box.y1 + box.y2) / 2)
            por_trecho.setdefault(chave, []).append(i)
        return [(chave, por_trecho[chave]) for chave in sorted(por_trecho)]

    def deteccao_do_trecho(self, indices: Sequence[int], boxes: Sequence[BoxEntry]):
        """A detecção para `palavras_da_pagina` do trecho: a da página, quando o trecho é a
        página inteira (os mesmos boxes, na mesma ordem); senão, None (o core a faz)."""
        return self.deteccao if len(indices) == len(boxes) else None
