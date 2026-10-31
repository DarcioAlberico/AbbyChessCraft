"""No servidor, o leitor lê uma coisa por vez (SPEC-qualidade Q-C3): todo método dele que o
filho chama de duas threads (o glifo do lote e o pedido interativo) passa pela mesma trava,
e não só o `ler`."""
from __future__ import annotations

import queue
import threading

import pytest

from abbychess import servidor_de_leitura as sl

METODOS = ("ler", "ler_pelo_livro", "sugerir", "arbitro")


class _LeitorQueConta:
    """Registra quantos métodos rodam juntos; o primeiro espera `soltar`."""

    def __init__(self):
        self.dentro = 0
        self.maximo = 0
        self.primeiro_dentro = threading.Event()
        self.soltar = threading.Event()
        self._conta = threading.Lock()
        self._primeiro = True

    def _rodar(self):
        with self._conta:
            self.dentro += 1
            self.maximo = max(self.maximo, self.dentro)
            primeiro, self._primeiro = self._primeiro, False
        if primeiro:
            self.primeiro_dentro.set()
            assert self.soltar.wait(30)
        with self._conta:
            self.dentro -= 1
        return None

    def ler(self, recorte, **_k):
        return self._rodar()

    def ler_pelo_livro(self, recorte, *_a):
        return self._rodar()

    def sugerir(self, recorte, *_a):
        return self._rodar()

    def arbitro(self, recorte):
        return self._rodar()


@pytest.mark.parametrize("segundo", METODOS)
def test_o_segundo_metodo_espera_o_glifo_em_curso(segundo):
    laco = sl._Laco(queue.Queue(), queue.Queue(), "", None, None)
    laco.leitor = leitor = _LeitorQueConta()
    laco.dar_a_vez()
    primeiro = threading.Thread(target=leitor.ler, args=(None,))
    primeiro.start()
    assert leitor.primeiro_dentro.wait(30)

    entrou = threading.Event()
    outro = threading.Thread(target=lambda: (getattr(leitor, segundo)(None), entrou.set()))
    outro.start()
    esperou = not entrou.wait(0.3)          # com a trava, ele fica parado até o primeiro sair
    leitor.soltar.set()
    primeiro.join(30)
    outro.join(30)

    assert entrou.is_set() and esperou
    assert leitor.maximo == 1
