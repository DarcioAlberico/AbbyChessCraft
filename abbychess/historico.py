"""Desfazer e refazer o que muda a página: o Ctrl+Z do treino.

Cada passo guarda a página antes e depois e os padrões que ele gravou no livro, inteiros
(`padroes.Amostra`). Desfazer volta a página ao "antes" e apaga esses padrões; refazer
volta ao "depois" e os grava de novo.

A página guardada é o instantâneo do modelo (`Pagina.instantaneo`): desde o passo 2a nada
da página é mudado no lugar, e uma tupla dos `Box` basta, sem cópia de cada glifo. O
contador de gids (`proximo_n`) não volta com o desfazer: um gid nunca é reaproveitado.

O histórico é por página e vale na sessão: fechar o projeto o esquece. O desfazer do
projeto inteiro, com pré-condição por gid, é do passo 2b (§14.2). Sem Qt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import FrozenSet, List, Optional

from abbychess.modelo import Pagina
from abbychess.padroes import Amostra

#: Quantos passos cada página guarda. O mais antigo sai primeiro.
LIMITE = 100


@dataclass
class Instantaneo:
    """A página num momento: o que o desfazer devolve."""

    #: O instantâneo do modelo; `None` quando a página ainda não existia no projeto.
    pagina: Optional[Pagina]
    #: Os arquivos de padrão do livro naquele momento: a diferença entre o antes
    #: e o depois são os padrões que o passo gravou.
    padroes: FrozenSet[Path] = frozenset()

    @property
    def boxes(self):
        return [b.entry for b in self.pagina.boxes] if self.pagina is not None else []


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
