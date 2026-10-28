"""A fábrica de leitor falso do servidor de leitura (SPEC §11, para os testes; sem torch).

`criar(pasta, limiares)` dá um `LeitorDoLivro` com os padrões do livro de verdade e, no
lugar da cadeia global, uma leitura fixa ("x", fonte `neural`, confiança 0,5) depois de um
atraso por glifo (`ABBY_FALSO_MS_POR_GLIFO`, 10 ms por padrão: 15 glifos, ~150 ms por
página sintética). Assim o teste sabe que a leitura veio do servidor e o lote tem duração.
O palpite do glifo que ninguém leu (§9.2) é fixo ("y", 0,4, `RedeFalsa`); o leitor
falso não tem rede, e o estado dos modelos continua "sem rede".
`ABBY_FALSO_ATRASO_AO_ABRIR` faz o filho demorar a ficar pronto, como os modelos de verdade.
"""

from __future__ import annotations

import os
import time

from abbychess.leitor import Leitura, LeitorDoLivro

LETRA = "x"
FONTE = "neural"
CONFIANCA = 0.5

#: O palpite da rede falsa para o glifo que ninguém leu (§9.2).
PALPITE = "y"
CONFIANCA_DO_PALPITE = 0.4


class RedeFalsa:
    """A rede de glifos no lugar da do PyBoxEditor: o mesmo palpite para todo recorte."""

    def predict(self, _recorte):
        return PALPITE, CONFIANCA_DO_PALPITE

    def predict_topk(self, _recorte, k=5):
        return [(PALPITE, CONFIANCA_DO_PALPITE)]


class LeitorFalso(LeitorDoLivro):
    def _ler_global(self, recorte, altura_de_referencia) -> Leitura:
        time.sleep(float(os.environ.get("ABBY_FALSO_MS_POR_GLIFO", "10")) / 1000)
        return Leitura(LETRA, FONTE, CONFIANCA)

    def sugerir(self, recorte, altura_de_referencia=None):
        # O palpite da rede falsa sem a rede: o estado dos modelos continua "sem rede".
        return RedeFalsa().predict(recorte)


def criar(pasta_de_padroes, limiares):
    # `ABBY_FALSO_ATRASO_AO_ABRIR` segundos "carregando os modelos" (o servidor não pronto).
    time.sleep(float(os.environ.get("ABBY_FALSO_ATRASO_AO_ABRIR", "0")))
    return LeitorFalso(pasta_de_padroes, limiares=limiares)
