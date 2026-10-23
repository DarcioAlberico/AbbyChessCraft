"""As operações de página na janela (SPEC §12.4, passo L, rodada 2b): o menu Página, a gaveta,
os diálogos com a seleção e Páginas apagadas…; a janela segue a ordem nova (o seletor, a
gaveta, a busca)."""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.box_model import BoxEntry  # noqa: E402
from PIL import Image  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QFileDialog  # noqa: E402

from abbychess.app import acoes  # noqa: E402
from abbychess.app import dialogo_paginas as dp  # noqa: E402
from abbychess.projeto import ProjetoDeLivro  # noqa: E402

from tests.test_busca_janela import _ate, _buscar  # noqa: E402
from tests.test_espaco import sim  # noqa: E402,F401
from tests.test_visor import pdf_de_60_paginas  # noqa: E402,F401


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app, tmp_path, pdf_de_60_paginas, sim):  # noqa: F811
    """A janela como o programa a abre: a fonte pela sequência do projeto."""
    from abbychess import pagina as pg
    from abbychess.app.janela import JanelaPrincipal
    from abbychess.leitor import LeitorDoLivro

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Janela", pdf_de_60_paginas)
    j = JanelaPrincipal()
    j.resize(1366, 768)
    j.show()
    j.usar(projeto, pg.fonte_do_projeto(projeto),
           LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    QApplication.processEvents()
    yield j
    j.close()


def _palavra(projeto, posicao, palavra):
    boxes = [BoxEntry(char=c, x1=40 + 12 * k, y1=300, x2=50 + 12 * k, y2=320, source="manual",
                      confidence=1.0) for k, c in enumerate(palavra)]
    projeto.salvar_pagina(posicao, boxes)


# ----------------------------------------------------------------------
# Os diálogos
# ----------------------------------------------------------------------

def test_o_dialogo_so_aceita_a_selecao_valida_e_diz_quantas(app):
    d = dp.DialogoDasPaginas(None, "Mover", 20, selecao="3-5", lugar="Depois da página",
                             lugar_padrao=10, efeito="{N} página(s): {PAGINAS}.")
    ok = d.botoes.button(QDialogButtonBox.StandardButton.Ok)
    assert ok.isEnabled() and d.previa.text() == "3 página(s): 3-5."
    assert d.posicoes() == [2, 3, 4] and d.depois_da() == 9
    d.campo.setText("5-3")
    assert not ok.isEnabled() and "contrário" in d.previa.text()
    d.campo.setText("ímpares")
    assert ok.isEnabled() and d.previa.text().startswith("10 página(s)")
    d.lugar.setValue(0)
    assert d.depois_da() == -1 and d.lugar.text() == "o começo do livro"
    d.deleteLater()


def test_texto_da_selecao_junta_as_seguidas():
    assert dp.texto_da_selecao([1, 2, 3, 6, 9, 10]) == "2-4, 7, 10-11"


def test_o_dialogo_das_apagadas_restaura_as_escolhidas_ou_todas(app):
    from abbychess.sequencia import Sequencia

    s = Sequencia.do_livro(range(10)).apagar([2, 6])
    d = dp.DialogoDasApagadas(None, s.apagadas)
    assert d.lista.count() == 2 and "página 3 do PDF" in d.lista.item(0).text()
    assert not d.botao_escolhidas.isEnabled()
    d.lista.item(1).setSelected(True)
    d.botao_escolhidas.click()
    assert d.escolha() == [6]
    d.deleteLater()


# ----------------------------------------------------------------------
# O menu Página e a gaveta
# ----------------------------------------------------------------------

def test_mover_pelo_menu_e_a_busca_acha_na_posicao_nova(app, janela, monkeypatch):
    projeto = janela.projeto
    _palavra(projeto, 1, "cavalo")
    janela.busca.abrir()
    _ate(janela.busca.pronto.is_set)
    pid = projeto.pid_da_pagina(1)
    monkeypatch.setattr(dp, "perguntar_paginas", lambda *_a, **_k: ([1], 9))
    janela.acao_mover_paginas.trigger()              # a página 2 depois da 10
    assert projeto.pid_da_pagina(9) == pid
    assert "Ctrl+Z" in janela.statusBar().currentMessage()
    _ate(janela.busca.pronto.is_set)
    _buscar(janela, "cavalo")
    assert [o.pagina for o in janela.busca.ultimo_resultado.ocorrencias] == [9]


def test_apagar_pelo_menu_muda_o_seletor_e_o_total(app, janela, monkeypatch):
    monkeypatch.setattr(dp, "perguntar_paginas", lambda *_a, **_k: ([2, 6], -1))
    janela.acao_apagar_paginas.trigger()
    assert janela.fonte.total == 58 and janela.seletor.maximum() == 58
    assert janela.total_de_paginas.text() == " de 58 "
    assert janela.acao_paginas_apagadas.isEnabled()


def test_inserir_pelo_menu(app, janela, monkeypatch, tmp_path):
    imagem = tmp_path / "nova.png"
    Image.fromarray(np.full((300, 200), 255, np.uint8)).save(imagem)
    monkeypatch.setattr(QFileDialog, "getOpenFileNames",
                        staticmethod(lambda *_a, **_k: ([str(imagem)], "")))
    monkeypatch.setattr(dp, "perguntar_paginas", lambda *_a, **_k: ([], 4))
    janela.acao_inserir_paginas.trigger()            # depois da página 5
    assert janela.fonte.total == 61
    assert janela.projeto.sequencia.entrada_em(5).fonte.startswith("inseridas/")
    janela.ir_para_pagina(5)
    assert janela.pagina.indice == 5 and janela.pagina.imagem.size == (200, 300)


def test_paginas_apagadas_pelo_menu_devolve(app, janela, monkeypatch):
    projeto = janela.projeto
    pids = projeto.sequencia.pids
    janela.pagina.apagar_paginas([3])
    monkeypatch.setattr(dp, "perguntar_apagadas", lambda _j, apagadas: [apagadas[0].entrada.pid])
    janela.acao_paginas_apagadas.trigger()
    assert projeto.sequencia.pids == pids and not janela.acao_paginas_apagadas.isEnabled()


def test_a_gaveta_move_e_apaga_as_selecionadas(app, janela, monkeypatch):
    vistos = []
    monkeypatch.setattr(dp, "perguntar_paginas",
                        lambda _j, _t, _n, **k: vistos.append(k["selecao"]) or ([1, 2], 9))
    janela.mover_paginas([1, 2])                     # o que a gaveta emite
    assert vistos == ["2-3"]
    menu = janela.paginas.menu_de_contexto()
    textos = [a.text() for a in menu.actions()]
    assert any(t.startswith("Mover as selecionadas") for t in textos)
    assert any(t.startswith("Apagar as selecionadas") for t in textos)


def test_com_o_lote_rodando_as_operacoes_ficam_desligadas_com_o_motivo(app, janela):
    janela.pagina.lote_rodando = True
    acoes.atualizar(janela)
    for q in janela.acoes_de_paginas:
        assert not q.isEnabled() and "lote" in q.toolTip()
    assert not janela.paginas.paginas_mudam
    janela.pagina.lote_rodando = False
    acoes.atualizar(janela)
    assert janela.acao_mover_paginas.isEnabled()
    assert not janela.acao_paginas_apagadas.isEnabled()   # nenhuma apagada ainda


# ----------------------------------------------------------------------
# Girar, cortar e dividir pelo menu (rodada 3b)
# ----------------------------------------------------------------------

def test_os_dialogos_de_girar_cortar_e_dividir_leem_os_campos(app):
    sentido = dp.campo_do_sentido()
    sentido.setCurrentIndex(1)
    margens = [dp.campo_de_porcentagem(0.0, 0.0, 95.0) for _ in range(4)]
    margens[2].setValue(12.5)
    d = dp.DialogoDasPaginas(None, "Cortar", 20, selecao="2",
                             linhas=[("Girar", sentido), ("Margem direita", margens[2])])
    assert sentido.currentData() == 270 and margens[2].value() == 12.5
    assert sentido.accessibleName() == "Girar"
    d.deleteLater()


def test_girar_cortar_e_dividir_pelo_menu(app, janela, monkeypatch):
    projeto = janela.projeto
    monkeypatch.setattr(dp, "perguntar_com", lambda *_a, **_k: ([0, 2], 90))
    janela.acao_girar_paginas.trigger()
    assert [projeto.sequencia.entrada_em(i).giro for i in range(3)] == [90, 0, 90]
    monkeypatch.setattr(dp, "perguntar_com", lambda *_a, **_k: ([1], (0.1, 0, 0, 0)))
    janela.acao_cortar_paginas.trigger()
    assert projeto.sequencia.entrada_em(1).quadro is not None
    monkeypatch.setattr(dp, "perguntar_paginas", lambda *_a, **_k: ([1], -1))
    janela.acao_tirar_o_corte.trigger()
    assert projeto.sequencia.entrada_em(1).quadro is None
    monkeypatch.setattr(dp, "perguntar_com", lambda *_a, **_k: ([4], 0.5))
    janela.acao_dividir_paginas.trigger()
    assert janela.fonte.total == 61 and janela.seletor.maximum() == 61
    assert projeto.sequencia.entrada_em(5).metade == "direita"
    janela.pagina.desfazer()
    assert janela.fonte.total == 60
    monkeypatch.setattr(dp, "perguntar_com", lambda *_a, **_k: ([6], 1.25))
    janela.acao_endireitar_paginas.trigger()
    assert projeto.sequencia.entrada_em(6).angulo == 1.25


def test_o_angulo_medido_nao_e_arredondado_no_dialogo(app):
    """0,65° com uma casa viraria 0,7°, e dar OK sem mexer endireitaria a página."""
    campo = dp.campo_de_porcentagem(0.65, -20.0, 20.0, "°", decimais=2, passo=0.1)
    assert campo.value() == pytest.approx(0.65)
    campo.deleteLater()
