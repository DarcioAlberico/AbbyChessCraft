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


class _ProjetoQueNaoEDaBusca:
    """O projeto que a janela abriu depois do pedido da busca: ninguém deve lê-lo por ela."""

    def __init__(self, resto):
        self.lidas, self._resto = [], resto

    def ler_sem_migrar(self, indice):
        self.lidas.append(indice)
        return None

    def __getattr__(self, nome):                # o resto, que o fim da busca consulta
        return getattr(self._resto, nome)


def test_a_busca_le_as_paginas_do_projeto_de_quando_foi_pedida(livro_escrito, monkeypatch):
    projeto, ctl, busca, escrever, eventos = livro_escrito
    escrever(2, "fim novo")
    busca.marcar_velha(2)                                 # para ler do disco, na thread
    monkeypatch.setattr(projeto, "modelo_em_memoria", lambda i: None)
    adiadas, Thread = [], threading.Thread

    def thread_adiada(*args, name=None, target=None, **k):   # a da busca não começa já
        if name == "busca":
            adiadas.append(target)
            return type("Parada", (), {"start": lambda self: None})()
        return Thread(*args, name=name, target=target, **k)

    monkeypatch.setattr(threading, "Thread", thread_adiada)
    busca.buscar(bs.Opcoes("novo"))
    outro = _ProjetoQueNaoEDaBusca(projeto)
    monkeypatch.setattr(ctl, "projeto", outro)            # a janela troca de projeto
    monkeypatch.setattr(threading, "Thread", Thread)
    [rodar] = adiadas
    rodar()                                               # e só então a thread lê

    assert outro.lidas == []


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
