"""O render da pré-carga num processo à parte (`abbychess.render`, pendência do passo K)."""

from __future__ import annotations

import pytest
from PIL import Image

from abbychess import pagina as pg
from abbychess import render

from tests.test_livro import pdf_sintetico


class _RenderFalso:
    """Guarda os pedidos; devolve a página que o processo daria, ou nada (`quebrado`)."""

    def __init__(self, fonte, quebrado=False):
        self.fonte, self.quebrado, self.pedidos = fonte, quebrado, []

    def renderizar(self, caminho, indice):
        self.pedidos.append(indice)
        if self.quebrado:
            return None
        return self.fonte._arquivo("livro").pagina(indice).copy()


@pytest.fixture
def fonte(tmp_path):
    return pg.FonteDePaginas(pdf_sintetico(tmp_path))


def test_so_a_pre_carga_renderiza_no_processo(fonte):
    falso = _RenderFalso(fonte)
    cache = pg.CacheDePaginas(fonte, renderizador=falso)
    cache.pagina(0)                                   # a pedida na hora: aqui
    assert falso.pedidos == []
    cache.precarregar(1)
    cache.esperar()
    assert falso.pedidos == [1] and cache.tem(1)
    assert cache.pagina(1)[0].tobytes() == fonte.pagina(1).tobytes()


def test_sem_resposta_do_processo_a_pre_carga_renderiza_aqui(fonte):
    falso = _RenderFalso(fonte, quebrado=True)
    cache = pg.CacheDePaginas(fonte, renderizador=falso)
    cache.precarregar(2)
    cache.esperar()
    assert falso.pedidos == [2] and cache.tem(2)


def test_a_pagina_pedida_nao_espera_a_pre_carga_travada_no_processo(fonte, monkeypatch):
    """O processo de render que trava não prende a interface: quem pede a página que a
    pré-carga renderiza lá espera `ESPERA_PELA_PRE_CARGA_S` e renderiza aqui."""
    import threading
    import time

    monkeypatch.setattr(pg, "ESPERA_PELA_PRE_CARGA_S", 0.2)
    solta = threading.Event()

    class _Travado(_RenderFalso):
        def renderizar(self, caminho, indice):
            solta.wait(10)
            return super().renderizar(caminho, indice)

    cache = pg.CacheDePaginas(fonte, renderizador=_Travado(fonte))
    cache.precarregar(1)
    time.sleep(0.05)                                  # a pré-carga já está no processo
    inicio = time.perf_counter()
    imagem, _ = cache.pagina(1)
    assert time.perf_counter() - inicio < 2.0
    assert imagem.tobytes() == fonte.pagina(1).tobytes()
    solta.set()
    cache.esperar()
    assert cache.tem(1)


def test_desligado_pelo_ambiente(monkeypatch):
    monkeypatch.setenv("ABBY_RENDER_EM_PROCESSO", "0")
    assert render.do_programa() is None
    monkeypatch.setenv("ABBY_RENDER_EM_PROCESSO", "1")
    assert render.do_programa() is render.do_programa()


@pytest.mark.processo
def test_o_processo_da_os_mesmos_pixels_e_desiste_quando_fecha(tmp_path):
    caminho = pdf_sintetico(tmp_path)
    renderizador = render.RenderEmProcesso()
    try:
        de_la = renderizador.renderizar(caminho, 1)
        aqui = pg.FonteDePaginas(caminho).pagina(1)
        assert isinstance(de_la, Image.Image)
        assert (de_la.mode, de_la.size, de_la.tobytes()) == (aqui.mode, aqui.size, aqui.tobytes())
        assert renderizador.renderizar(caminho, 99) is None      # fora do PDF: quem chama erra
    finally:
        renderizador.fechar()
    assert renderizador.desistiu and renderizador.renderizar(caminho, 0) is None


def _filhos_vivos(limite: float = 10.0) -> list:
    import multiprocessing as mp
    import time

    fim = time.monotonic() + limite
    while mp.active_children() and time.monotonic() < fim:
        time.sleep(0.05)
    return mp.active_children()


@pytest.mark.processo
def test_o_filho_que_nao_responde_no_prazo_e_morto(tmp_path):
    """Sem o `kill`, o filho travado ficava vivo e o programa não fechava (o `atexit` do
    `concurrent.futures` o esperava). Aqui o prazo é menor que abrir o processo."""
    caminho = pdf_sintetico(tmp_path)
    renderizador = render.RenderEmProcesso(limite_s=0.001)
    assert renderizador.renderizar(caminho, 0) is None and not renderizador.aberto
    assert _filhos_vivos() == []
    renderizador.limite_s = render.LIMITE_S                  # de novo: abre outro e responde
    try:
        assert renderizador.renderizar(caminho, 0) is not None
    finally:
        renderizador.fechar()


@pytest.mark.processo
def test_matar_o_pool_mata_o_filho_travado():
    import concurrent.futures as cf
    import multiprocessing as mp
    import time

    pool = cf.ProcessPoolExecutor(1, mp_context=mp.get_context("spawn"))
    trabalho = pool.submit(time.sleep, 30)
    fim = time.monotonic() + 30
    while not trabalho.running() and time.monotonic() < fim:
        time.sleep(0.05)
    assert trabalho.running()
    render._matar(pool)
    assert _filhos_vivos(limite=5) == []                    # sem o kill, 30 s dormindo


def _vivo(pid: int) -> bool:
    """Se o processo `pid` ainda roda (Windows: `os.kill(pid, 0)` o mataria)."""
    import ctypes
    import os

    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    k32 = ctypes.windll.kernel32
    alca = k32.OpenProcess(0x1000, False, pid)      # PROCESS_QUERY_LIMITED_INFORMATION
    if not alca:
        return False
    try:
        codigo = ctypes.c_ulong()
        k32.GetExitCodeProcess(alca, ctypes.byref(codigo))
        return codigo.value == 259                  # STILL_ACTIVE
    finally:
        k32.CloseHandle(alca)


@pytest.mark.processo
def test_os_filhos_do_pool_do_indice_morrem_com_o_programa_morto_a_forca(tmp_path):
    """Os filhos do `PoolDoIndice` ficavam órfãos quando o programa morria sem fechar o pool
    (12 achados parados desde a manhã): o vigia do pai os faz sair."""
    import subprocess
    import sys
    import time
    from pathlib import Path

    import os

    roteiro = tmp_path / "pai.py"
    roteiro.write_text(
        "import os\n"
        "from abbychess import busca\n"
        "from tests.test_render import _pid_do_filho\n"
        "if __name__ == '__main__':\n"
        "    pool = busca.PoolDoIndice().obter()\n"
        "    print(' '.join(str(p) for p in set(pool.map(_pid_do_filho, range(16)))), flush=True)\n"
        "    os._exit(0)\n", encoding="utf-8")
    raiz = str(Path(__file__).resolve().parents[1])
    saida = subprocess.run([sys.executable, str(roteiro)], capture_output=True, text=True,
                           timeout=120, cwd=raiz, env={**os.environ, "PYTHONPATH": raiz})
    pids = [int(p) for p in saida.stdout.split()]
    assert pids, saida.stderr
    fim = time.monotonic() + 10
    while any(_vivo(p) for p in pids) and time.monotonic() < fim:
        time.sleep(0.1)
    assert [p for p in pids if _vivo(p)] == []


def _pid_do_filho(_n: int) -> int:
    import os

    return os.getpid()


@pytest.mark.processo
def test_o_pdf_trocado_no_mesmo_lugar_e_lido_de_novo_e_o_ocioso_fecha(tmp_path):
    import time

    pasta = tmp_path / "a"
    pasta.mkdir()
    caminho = pdf_sintetico(pasta)
    renderizador = render.RenderEmProcesso(ocioso_s=0.3)
    try:
        renderizador.renderizar(caminho, 0)
        outro = pdf_sintetico(tmp_path, [("zzz zzz zzz",), ("yyy",), ("xxx",)])
        caminho.write_bytes(outro.read_bytes())
        de_la = renderizador.renderizar(caminho, 0)
        assert de_la.tobytes() == pg.FonteDePaginas(caminho).pagina(0).tobytes()
        time.sleep(1.0)
        assert not renderizador.aberto and _filhos_vivos() == []
        assert renderizador.renderizar(caminho, 1) is not None   # reabre no próximo pedido
    finally:
        renderizador.fechar()
