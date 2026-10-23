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
