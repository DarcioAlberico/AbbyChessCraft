"""O servidor de leitura (SPEC §11): o filho, a vez, os deltas, a queda e o fechamento.

Com o leitor falso (`tests/leitor_falso.py`): sem torch, uma leitura fixa depois de um atraso
por glifo. Cada teste abre o seu filho (`spawn`, ~1 s).
"""

from __future__ import annotations

import time

import numpy as np
import pytest
from PIL import Image

from abbychess import servidor_de_leitura as sl
from abbychess.padroes import PadroesDoLivro
from abbychess.projeto import Limiares

from tests import leitor_falso
from tests.test_treino_por_livro import _pagina_sintetica

FABRICA = "tests.leitor_falso:criar"

#: Cada teste abre um processo filho (`spawn`, ~1 s): a camada `processo`, fora da suíte
#: rápida (`pytest -m processo`).
pytestmark = pytest.mark.processo


@pytest.fixture
def pasta(tmp_path):
    return tmp_path / "padroes"


@pytest.fixture
def servidor(pasta):
    avisos = []
    s = sl.ServidorDeLeitura(pasta, Limiares(), fabrica=FABRICA,
                             ao_avisar=lambda titulo, texto, desistiu: avisos.append(texto))
    s.avisos = avisos
    assert s.pronto.wait(60), "o filho não ficou pronto"
    yield s
    s.fechar()


@pytest.fixture
def imagem(tmp_path):
    return Image.open(_pagina_sintetica(tmp_path / "pagina.png")).convert("L")


def test_o_filho_le_a_pagina_e_devolve_os_boxes_e_a_procedencia(servidor, imagem):
    lida = servidor.chamar("ler_pagina", (imagem, [], []), timeout=30)
    assert len(lida.boxes) == 15 and len(lida.amostras) == 15
    assert {b.char for b in lida.boxes} == {leitor_falso.LETRA}
    assert {b.source for b in lida.boxes} == {leitor_falso.FONTE}


def test_os_deltas_dos_padroes_valem_no_pedido_seguinte(servidor, pasta, imagem):
    padroes = PadroesDoLivro(pasta)
    recorte = np.full((30, 20), 0, np.uint8)
    caminho = padroes.ensinar(recorte, "a", 1.0, origem="o1")   # a interface grava
    assert servidor.chamar("padroes", timeout=10) == 0
    servidor.enviar_padroes([(caminho, 1.0)], [])
    assert servidor.chamar("padroes", timeout=10) == 1
    leitura = servidor.chamar("ler_recortes", [(recorte, 30.0)], timeout=10)[0]
    assert (leitura.char, leitura.fonte) == ("a", "livro")
    servidor.enviar_padroes([], [caminho])
    assert servidor.chamar("padroes", timeout=10) == 0


def test_o_palpite_da_rede_vem_do_filho(servidor):
    """§9.2: o glifo que ninguém leu recebe o palpite da rede, que só o servidor tem."""
    recorte = np.full((30, 20), 0, np.uint8)
    palpites = servidor.chamar("sugerir_recortes", [(recorte, 30.0)], timeout=10)
    assert palpites == [(leitor_falso.PALPITE, leitor_falso.CONFIANCA_DO_PALPITE)]


def test_ca_11_8_o_pedido_interativo_passa_na_frente_da_pagina_seguinte_do_lote(servidor, imagem,
                                                                                monkeypatch):
    lote = [servidor.pedir("ler_pagina", (imagem, [], []), prioridade=sl.LOTE) for _ in range(3)]
    time.sleep(0.05)                                       # o lote começou a primeira página
    f5 = servidor.pedir("ler_pagina", (imagem, [], []))
    for pedido in (*lote, f5):
        servidor.esperar(pedido, 30)
    ordem = servidor.chamar("ordem", timeout=10)
    assert ordem.index(f5.id) < ordem.index(lote[1].id)      # antes da próxima página do lote


def test_cancelar_para_a_pagina_do_lote_no_glifo_seguinte(servidor, imagem):
    pedido = servidor.pedir("ler_pagina", (imagem, [], []), prioridade=sl.LOTE)
    time.sleep(0.05)
    servidor.cancelar(pedido)
    with pytest.raises(sl.Cancelado):
        servidor.esperar(pedido, 30)


def test_o_filho_que_morre_volta_uma_vez_e_na_segunda_desiste(servidor, imagem):
    primeiro = servidor.pid
    servidor.processo.kill()
    pedido = servidor.pedir("pid")
    assert servidor.esperar(pedido, 60) != primeiro          # reaberto, e o pedido reenviado
    assert servidor.reinicios == 1 and servidor.avisos
    servidor.processo.kill()
    pedido = servidor.pedir("pid")
    with pytest.raises(sl.ErroDoServidor):
        servidor.esperar(pedido, 60)
    assert servidor.desistiu and len(servidor.avisos) == 2


def test_fechar_termina_o_filho_sem_deixar_orfao(pasta):
    import psutil

    s = sl.ServidorDeLeitura(pasta, Limiares(), fabrica=FABRICA)
    assert s.pronto.wait(60)
    pid = s.pid
    inicio = time.perf_counter()
    s.fechar()
    assert time.perf_counter() - inicio <= 6
    assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE


def test_a_interface_nao_importa_torch_para_ler_pelo_servidor():
    """§11: o processo da interface não importa torch (o filho, sim, com o leitor real)."""
    import subprocess
    import sys

    codigo = ("import sys; from abbychess import servidor_de_leitura, controlador, controladores;"
              "from abbychess.app import janela; print('torch' in sys.modules)")
    saida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True,
                           env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"},
                           timeout=120)
    assert saida.stdout.strip() == "False", saida.stderr


def test_o_filho_de_um_pai_com_qt_nao_carrega_o_qt(tmp_path):
    """§11: o filho importa só o servidor e o leitor (o pai, como a janela, tem o Qt)."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1]
    saida = subprocess.run([sys.executable, "-m", "tests.app_falso", str(tmp_path / "padroes")],
                           capture_output=True, text=True, timeout=120, cwd=raiz,
                           env={**os.environ, "PYTHONPATH": str(raiz)})
    assert saida.stdout.strip() == "[]", saida.stderr


def test_cancelar_antes_de_o_filho_ficar_pronto_responde_cancelado(pasta, imagem):
    """O ✕ do lote com os modelos ainda carregando: o pedido que não começou responde
    "cancelado" na vez dele (antes, saía da fila sem resposta, e o lote ficava preso)."""
    s = sl.ServidorDeLeitura(pasta, Limiares(), fabrica=FABRICA)
    try:
        pedido = s.pedir("ler_pagina", (imagem, [], []), prioridade=sl.LOTE)
        s.cancelar(pedido)
        with pytest.raises(sl.Cancelado):
            s.esperar(pedido, 30)
        assert not s._pendentes
    finally:
        s.fechar()

