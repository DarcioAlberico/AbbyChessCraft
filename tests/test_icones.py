"""Os ícones (SPEC §13 e §18.5, passo K): os SVG do Lucide no pacote, com a licença; pintados
pelo tema, de novo quando ele muda; os botões da barra com alvo de 24 px."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QToolBar, QToolButton  # noqa: E402

from abbychess.app import estilo, icones  # noqa: E402
from abbychess.app.janela import JanelaPrincipal  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tema_claro(app):
    paleta, folha = app.palette(), app.styleSheet()
    estilo.aplicar(app, "claro")
    yield app
    estilo.aplicar(app, "claro")
    app.setPalette(paleta)
    app.setStyleSheet(folha)


@pytest.fixture
def janela(tema_claro):
    j = JanelaPrincipal()
    yield j
    j.close()


def _cor_do_traco(icone, lado=24, modo=None):
    """A cor mais opaca do ícone rasterizado (o traço)."""
    from PySide6.QtGui import QIcon

    imagem = icone.pixmap(lado, lado, modo or QIcon.Mode.Normal).toImage()
    pixels = [imagem.pixelColor(x, y) for x in range(imagem.width())
              for y in range(imagem.height())]
    return max(pixels, key=lambda c: c.alpha()).name()


def test_os_svg_usados_estao_no_pacote_com_a_licenca():
    usados = set(icones.DA_JANELA.values())
    no_pacote = {p.stem for p in icones.PASTA.glob("*.svg")}
    assert usados == no_pacote                     # nenhum faltando, nenhum sobrando
    licenca = (icones.PASTA / "LICENSE").read_text(encoding="utf-8")
    assert licenca.startswith("ISC License") and "Lucide Contributors" in licenca
    for nome in usados:                            # todos pintáveis pelo tema
        assert b"currentColor" in (icones.PASTA / f"{nome}.svg").read_bytes(), nome


def test_o_icone_tem_a_cor_do_texto_do_tema(tema_claro):
    from PySide6.QtGui import QIcon

    assert _cor_do_traco(icones.icone("scan-text")) == estilo.CLARO.texto.name()
    assert _cor_do_traco(icones.icone("scan-text"), modo=QIcon.Mode.Disabled) \
        == estilo.CLARO.texto_secundario.name()
    estilo.aplicar(tema_claro, "escuro")
    assert _cor_do_traco(icones.icone("scan-text")) == estilo.ESCURO.texto.name()


def test_o_icone_e_rasterizado_uma_vez_por_tema(tema_claro, monkeypatch):
    """Rasterizar os 25 ícones era metade do custo de abrir uma janela (~40 de 78 ms)."""
    icones._icone.cache_clear()
    feitos = []
    original = icones._pixmap
    monkeypatch.setattr(icones, "_pixmap", lambda svg, lado: feitos.append(lado) or original(svg, lado))
    primeiro = icones.icone("scan-text")
    assert len(feitos) == 3 * len(icones.LADOS)
    assert icones.icone("scan-text").cacheKey() == primeiro.cacheKey() and len(feitos) == 15
    estilo.aplicar(tema_claro, "escuro")                 # outro tema, outras cores: de novo
    assert _cor_do_traco(icones.icone("scan-text")) == estilo.ESCURO.texto.name()
    assert len(feitos) == 30


def test_toda_acao_do_mapa_existe_e_tem_icone(janela):
    for atributo in icones.DA_JANELA:
        acao = getattr(janela, atributo)          # um nome errado no mapa reprova aqui
        assert not acao.icon().isNull(), atributo


def test_trocar_o_tema_repinta_os_icones_da_janela(janela, tema_claro):
    antes = _cor_do_traco(janela.acao_reconhecer.icon())
    estilo.aplicar(tema_claro, "escuro")
    depois = _cor_do_traco(janela.acao_reconhecer.icon())
    assert (antes, depois) == (estilo.CLARO.texto.name(), estilo.ESCURO.texto.name())


def test_os_botoes_da_barra_tem_alvo_de_24_px(janela):
    janela.show()
    QApplication.processEvents()
    barra = janela.findChild(QToolBar, "barra_principal")
    botoes = [b for b in barra.findChildren(QToolButton) if b.isVisible() and b.defaultAction()]
    assert botoes
    for botao in botoes:
        assert min(botao.width(), botao.height()) >= estilo.ALVO_MINIMO, botao.defaultAction().text()
    # Os dois comandos principais mostram o nome ao lado do ícone.
    assert barra.widgetForAction(janela.acao_reconhecer).toolButtonStyle() \
        == barra.widgetForAction(janela.acao_reler).toolButtonStyle() \
        != barra.widgetForAction(janela.acao_anterior).toolButtonStyle()
