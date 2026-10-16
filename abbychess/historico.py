"""Desfazer e refazer o que muda a página: o Ctrl+Z do treino.

Cada passo guarda a página antes e depois (boxes e diagramas, copiados) e os
padrões que ele gravou no livro, inteiros (`padroes.Amostra`). Desfazer volta a
página ao "antes" e apaga esses padrões; refazer volta ao "depois" e os grava
de novo. Copiar a página inteira é mais simples que guardar cada operação ao
contrário, e uma página de 2.000 boxes custa milissegundos para copiar.

O histórico é por página e vale na sessão: fechar o projeto o esquece. Sem Qt.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import FrozenSet, List, Optional, Sequence

from core.box_model import BoxEntry

from abbychess.padroes import Amostra

#: Quantos passos cada página guarda. O mais antigo sai primeiro.
LIMITE = 100


@dataclass
class Instantaneo:
    """A página num momento: o que o desfazer devolve."""

    boxes: List[BoxEntry]
    diagramas: list
    #: Os arquivos de padrão do livro naquele momento: a diferença entre o antes
    #: e o depois são os padrões que o passo gravou.
    padroes: FrozenSet[Path] = frozenset()
    #: A página já tinha passado pelo F5 (ver `ProjetoDeLivro.salvar_pagina`).
    reconhecida: bool = True


def instantaneo(boxes: Sequence[BoxEntry], diagramas: Sequence = ()) -> Instantaneo:
    return Instantaneo(copy.deepcopy(list(boxes)), copy.deepcopy(list(diagramas)))


@dataclass
class Passo:
    descricao: str
    antes: Instantaneo
    depois: Instantaneo
    #: Os padrões que o passo gravou no livro (ensinar).
    criados: List[Amostra] = field(default_factory=list)
    #: Uma chave que junta passos seguidos do mesmo tipo num só: cada Alt+seta
    #: num box é um passo, e desfazer pixel a pixel não serve a ninguém.
    juntar: Optional[tuple] = None


class Historico:
    """As pilhas de desfazer e refazer de uma página."""

    def __init__(self, limite: int = LIMITE):
        self.limite = limite
        self._desfazer: List[Passo] = []
        self._refazer: List[Passo] = []

    def registrar(self, passo: Passo) -> None:
        """Um passo novo. Ele apaga o que havia para refazer, como em todo editor."""
        ultimo = self._desfazer[-1] if self._desfazer else None
        if (passo.juntar is not None and ultimo is not None and ultimo.juntar == passo.juntar
                and not self._refazer):
            ultimo.depois = passo.depois
            ultimo.criados.extend(passo.criados)
            return
        self._desfazer.append(passo)
        self._refazer.clear()
        del self._desfazer[:-self.limite]

    def desfazer(self) -> Optional[Passo]:
        if not self._desfazer:
            return None
        passo = self._desfazer.pop()
        self._refazer.append(passo)
        return passo

    def refazer(self) -> Optional[Passo]:
        if not self._refazer:
            return None
        passo = self._refazer.pop()
        self._desfazer.append(passo)
        return passo

    @property
    def proximo_a_desfazer(self) -> Optional[str]:
        return self._desfazer[-1].descricao if self._desfazer else None

    @property
    def proximo_a_refazer(self) -> Optional[str]:
        return self._refazer[-1].descricao if self._refazer else None
