"""A fábrica de leitor falso do servidor de leitura (SPEC §11, para os testes; sem torch).

`criar(pasta, limiares)` dá um `LeitorDoLivro` com os padrões do livro de verdade e, no
lugar da cadeia global, uma leitura fixa ("x", fonte `neural`, confiança 0,5) depois de um
atraso por glifo (`ABBY_FALSO_MS_POR_GLIFO`, 10 ms por padrão: 15 glifos, ~150 ms por
página sintética). Assim o teste sabe que a leitura veio do servidor e o lote tem duração.
"""

from __future__ import annotations

import os
import time

from abbychess.leitor import Leitura, LeitorDoLivro

LETRA = "x"
FONTE = "neural"
CONFIANCA = 0.5


class LeitorFalso(LeitorDoLivro):
    def _ler_global(self, recorte, altura_de_referencia) -> Leitura:
        time.sleep(float(os.environ.get("ABBY_FALSO_MS_POR_GLIFO", "10")) / 1000)
        return Leitura(LETRA, FONTE, CONFIANCA)


def criar(pasta_de_padroes, limiares):
    return LeitorFalso(pasta_de_padroes, limiares=limiares)
