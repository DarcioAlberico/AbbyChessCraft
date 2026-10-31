"""As corridas menores (SPEC-qualidade Q-C5), cada uma encenada no ponto em que outra thread
entraria."""
from __future__ import annotations

import threading

from abbychess import busca as bs


class _PoolFalso:
    def __init__(self):
        self.fechado = False

    def shutdown(self, wait=True, cancel_futures=False):
        self.fechado = True


class _TravaComIntervalo:
    """Uma trava que, na primeira vez que é solta, deixa outra "thread" (`no_intervalo`)
    entrar antes de quem a soltou seguir: o pior momento para um `obter`."""

    def __init__(self, no_intervalo):
        self._trava = threading.Lock()
        self._no_intervalo = no_intervalo

    def __enter__(self):
        self._trava.acquire()

    def __exit__(self, *_):
        self._trava.release()
        intervalo, self._no_intervalo = self._no_intervalo, None
        if intervalo is not None:
            intervalo()


def test_fechar_o_pool_ocioso_nao_fecha_o_que_um_obter_acabou_de_pegar():
    pool = bs.PoolDoIndice()
    aberto = pool._pool = _PoolFalso()
    pool._pronto.set()
    recebidos = []

    def obter_de_outra_thread():                # o `obter` sem o `_abrir`: só pega o pool
        with pool._trava:
            pool._usos += 1
            recebidos.append(pool._pool)

    pool._trava = _TravaComIntervalo(obter_de_outra_thread)
    pool._fechar_se_ocioso()

    assert recebidos, "o obter de outra thread não rodou"
    assert not any(p is not None and p.fechado for p in recebidos)
    assert aberto.fechado == (recebidos[0] is None)
