"""A fábrica de leitor falso do servidor de leitura (SPEC §11, para os testes; sem torch).

`criar(pasta, limiares)` dá um `LeitorDoLivro` com os padrões do livro de verdade e, no
lugar da cadeia global, uma leitura fixa ("x", fonte `neural`, confiança 0,5) depois de um
atraso por glifo (`ABBY_FALSO_MS_POR_GLIFO`, 10 ms por padrão: 15 glifos, ~150 ms por
página sintética). Assim o teste sabe que a leitura veio do servidor e o lote tem duração.
O palpite do glifo que ninguém leu (§9.2) é fixo ("y", 0,4, `RedeFalsa`); o leitor
falso não tem rede, e o estado dos modelos continua "sem rede".
`ABBY_FALSO_ATRASO_AO_ABRIR` faz o filho demorar a ficar pronto, como os modelos de verdade.

Os dois defeitos do filho que o vigia trata (CA-C3, CA-C4), contados desde que o filho abriu:
`ABBY_FALSO_DORME_NO_GLIFO=N` dorme para sempre no N-ésimo glifo (o filho travado, mas vivo), e
`ABBY_FALSO_CAI_NO_GLIFO=N` derruba o processo nele (a página que derruba o filho). Reaberto, o
filho conta de novo: a mesma página dorme ou cai outra vez.
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
    glifos_lidos = 0

    def _ler_global(self, recorte, altura_de_referencia) -> Leitura:
        LeitorFalso.glifos_lidos += 1
        _defeito_no_glifo(LeitorFalso.glifos_lidos)
        time.sleep(float(os.environ.get("ABBY_FALSO_MS_POR_GLIFO", "10")) / 1000)
        return Leitura(LETRA, FONTE, CONFIANCA)

    def sugerir(self, recorte, altura_de_referencia=None):
        # O palpite da rede falsa sem a rede: o estado dos modelos continua "sem rede".
        return RedeFalsa().predict(recorte)


def _defeito_no_glifo(n: int) -> None:
    if n == int(os.environ.get("ABBY_FALSO_CAI_NO_GLIFO", "0")):
        os._exit(3)                                 # a queda: sem resposta, sem "caiu"
    if n == int(os.environ.get("ABBY_FALSO_DORME_NO_GLIFO", "0")):
        while True:                                 # travado, mas vivo
            time.sleep(1)


def criar(pasta_de_padroes, limiares):
    # `ABBY_FALSO_ATRASO_AO_ABRIR` segundos "carregando os modelos" (o servidor não pronto).
    time.sleep(float(os.environ.get("ABBY_FALSO_ATRASO_AO_ABRIR", "0")))
    return LeitorFalso(pasta_de_padroes, limiares=limiares)
