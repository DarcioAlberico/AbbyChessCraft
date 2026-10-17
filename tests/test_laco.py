"""O laço do servidor de leitura numa thread, com filas comuns (SPEC §11; a suíte rápida).

O mesmo `_Laco` que roda no filho, sem abrir processo: a vez entre glifos, os deltas, o
cancelamento e o erro de uma operação. Os testes com o filho de verdade (`spawn`, a queda e o
fechamento) estão em `tests/test_servidor.py`, na camada `processo`.
"""

from __future__ import annotations

import queue
import threading
import time

import numpy as np
import pytest
from PIL import Image

from abbychess import servidor_de_leitura as sl
from abbychess.padroes import PadroesDoLivro
from abbychess.projeto import Limiares

from tests import leitor_falso
from tests.test_treino_por_livro import _pagina_sintetica


@pytest.fixture
def imagem(tmp_path):
    return Image.open(_pagina_sintetica(tmp_path / "pagina.png")).convert("L")


@pytest.fixture
def laco(tmp_path, monkeypatch):
    monkeypatch.setattr(sl, "_baixar_a_prioridade", lambda: None)   # não a do pytest
    monkeypatch.setenv("ABBY_FALSO_MS_POR_GLIFO", "5")
    entrada, saida = queue.Queue(), queue.Queue()
    laco = sl._Laco(entrada, saida, "tests.leitor_falso:criar", tmp_path / "padroes", Limiares())
    thread = threading.Thread(target=laco.rodar, daemon=True)
    thread.start()
    assert saida.get(timeout=10)[0] == "pronto"
    laco.pasta_de_teste = tmp_path / "padroes"
    yield laco
    entrada.put(("sair",))
    thread.join(5)


def _respostas(laco, quantas: int) -> dict:
    respostas = {}
    while len(respostas) < quantas:
        _, id_, ok, resultado = laco.saida.get(timeout=20)
        respostas[id_] = (ok, resultado)
    return respostas


def test_o_interativo_passa_na_frente_da_proxima_pagina_do_lote(laco, imagem):
    for id_ in (1, 2, 3):
        laco.entrada.put(("pedido", id_, sl.LOTE, "ler_pagina", (imagem, [], [])))
    time.sleep(0.03)                                      # o lote começou a página 1
    laco.entrada.put(("pedido", 9, sl.INTERATIVO, "ler_pagina", (imagem, [], [])))
    respostas = _respostas(laco, 4)
    assert all(ok for ok, _ in respostas.values())
    assert laco.ordem.index(9) < laco.ordem.index(2)
    # A vez entre glifos: o interativo termina dentro da página 1 do lote, e não depois dela.
    assert laco.ordem.index(1) < laco.ordem.index(9) and laco.fins.index(9) < laco.fins.index(1)
    lida = respostas[9][1]
    assert {b.char for b in lida.boxes} == {leitor_falso.LETRA}


def test_o_delta_vale_no_pedido_seguinte_e_o_apagado_sai(laco):
    padroes = PadroesDoLivro(laco.pasta_de_teste)
    recorte = np.full((30, 20), 0, np.uint8)
    caminho = padroes.ensinar(recorte, "a", 1.0, origem="o1")
    laco.entrada.put(("padroes", [(str(caminho), 1.0)], []))
    laco.entrada.put(("pedido", 1, sl.INTERATIVO, "ler_recortes", [(recorte, 30.0)]))
    [(ok, [leitura])] = _respostas(laco, 1).values()
    assert ok and (leitura.char, leitura.fonte) == ("a", "livro")
    laco.entrada.put(("padroes", [], [str(caminho)]))
    laco.entrada.put(("pedido", 2, sl.INTERATIVO, "padroes", None))
    assert _respostas(laco, 1)[2] == (True, 0)


def test_cancelar_para_a_pagina_do_lote_e_a_que_nao_comecou_tambem_responde(laco, imagem):
    laco.entrada.put(("pedido", 1, sl.LOTE, "ler_pagina", (imagem, [], [])))
    laco.entrada.put(("pedido", 2, sl.LOTE, "ler_pagina", (imagem, [], [])))
    time.sleep(0.03)
    laco.entrada.put(("cancelar", 1))
    laco.entrada.put(("cancelar", 2))
    respostas = _respostas(laco, 2)                       # quem pediu sempre recebe resposta
    assert respostas == {1: (False, sl.CANCELADO), 2: (False, sl.CANCELADO)}
    assert 2 not in laco.ordem and not laco.cancelados


def test_o_cancelamento_que_chega_depois_do_fim_nao_fica_guardado(laco):
    laco.entrada.put(("pedido", 1, sl.INTERATIVO, "pid", None))
    _respostas(laco, 1)
    laco.entrada.put(("cancelar", 1))
    laco.entrada.put(("pedido", 2, sl.INTERATIVO, "pid", None))
    _respostas(laco, 1)
    assert not laco.cancelados


def test_a_operacao_que_falha_volta_como_erro_e_o_laco_segue(laco):
    laco.entrada.put(("pedido", 1, sl.INTERATIVO, "nao_existe", None))
    laco.entrada.put(("pedido", 2, sl.INTERATIVO, "pid", None))
    respostas = _respostas(laco, 2)
    assert not respostas[1][0] and "nao_existe" in respostas[1][1]
    assert respostas[2][0]


def test_o_modulo_principal_guardado_nao_abre_a_janela_no_filho():
    """O filho do `spawn` importa `abbychess.__main__` como `__mp_main__`: nada do Qt."""
    import subprocess
    import sys

    codigo = ("import runpy, sys; runpy.run_module('abbychess.__main__', run_name='__mp_main__');"
              "print('PySide6' in sys.modules)")
    saida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True,
                           timeout=60)
    assert saida.stdout.strip() == "False", saida.stderr


def test_o_interativo_nao_espera_a_segmentacao_da_pagina_do_lote(laco, imagem, monkeypatch):
    """A segmentação não tem glifos no meio (~0,5 s numa página cheia): a página do lote roda
    numa thread, e a releitura de um glifo é respondida durante ela."""
    from abbychess import zonas as zn

    original = zn.segmentar
    monkeypatch.setattr(zn, "segmentar", lambda *a, **k: (time.sleep(0.6), original(*a, **k))[1])
    laco.entrada.put(("pedido", 1, sl.LOTE, "ler_pagina", (imagem, [], [])))
    time.sleep(0.1)                                       # o lote está segmentando
    inicio = time.perf_counter()
    laco.entrada.put(("pedido", 9, sl.INTERATIVO, "ler_recortes",
                      [(np.full((30, 20), 0, np.uint8), 30.0)]))
    respostas = _respostas(laco, 1)
    assert 9 in respostas and time.perf_counter() - inicio < 0.3
    assert _respostas(laco, 1)[1][0]                      # e a página do lote termina


def test_cancelar_e_sair_no_meio_da_segmentacao_param_a_pagina_do_lote(laco, imagem,
                                                                       monkeypatch):
    from abbychess import zonas as zn

    original = zn.segmentar
    monkeypatch.setattr(zn, "segmentar", lambda *a, **k: (time.sleep(0.3), original(*a, **k))[1])
    laco.entrada.put(("pedido", 1, sl.LOTE, "ler_pagina", (imagem, [], [])))
    laco.entrada.put(("pedido", 2, sl.LOTE, "ler_pagina", (imagem, [], [])))
    time.sleep(0.1)                                       # a 1 está segmentando
    laco.entrada.put(("cancelar", 1))
    assert _respostas(laco, 1) == {1: (False, sl.CANCELADO)}    # no glifo seguinte
    assert _respostas(laco, 1)[2][0]                      # a 2 começa e termina
    laco.entrada.put(("pedido", 3, sl.LOTE, "ler_pagina", (imagem, [], [])))
    time.sleep(0.1)
    laco.entrada.put(("sair",))
    assert _respostas(laco, 1) == {3: (False, sl.CANCELADO)}
    laco._trabalhador.join(5)
    assert not laco._trabalhador.is_alive() and not laco.cancelados

