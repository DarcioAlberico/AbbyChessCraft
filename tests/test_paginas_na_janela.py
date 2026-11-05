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

from tests.ajudantes import _ate, _buscar  # noqa: E402,F401,F811
from tests.fixturas_paginas_na_janela import janela  # noqa: E402,F401,F811


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


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
    assert d.lista.count() == 2 and "p. 3 do PDF" in d.lista.item(0).text()
    assert not d.botao_escolhidas.isEnabled()
    d.lista.item(1).setSelected(True)
    d.botao_escolhidas.click()
    assert d.escolha() == [6]
    d.deleteLater()


# ----------------------------------------------------------------------
# O menu Página e a gaveta
# ----------------------------------------------------------------------

def test_mover_pelo_menu_e_a_busca_acha_na_posicao_nova(app, janela, monkeypatch):  # noqa: F811
    projeto = janela.projeto
    _palavra(projeto, 1, "cavalo")
    janela.busca.abrir()
    _ate(janela.busca.pronto.is_set)
    pid = projeto.ordem.pid_em(1)
    monkeypatch.setattr(dp, "perguntar_paginas", lambda *_a, **_k: ([1], 9))
    janela.acao_mover_paginas.trigger()              # a página 2 depois da 10
    assert projeto.ordem.pid_em(9) == pid
    assert "Ctrl+Z" in janela.statusBar().currentMessage()
    _ate(janela.busca.pronto.is_set)
    _buscar(janela, "cavalo")
    assert [o.pagina for o in janela.busca.ultimo_resultado.ocorrencias] == [9]


def test_a_galeria_do_livro_traz_os_recortes_das_outras_paginas(app, janela):  # noqa: F811
    projeto = janela.projeto
    _palavra(projeto, 1, "cavalo")
    _palavra(projeto, 3, "casa")
    janela.busca.abrir()
    _ate(janela.busca.pronto.is_set)
    janela.ir_para_pagina(1)
    janela.abrir_galeria("a", "livro")
    g = janela.galeria
    _ate(lambda: g.modelo.rowCount() == 4)
    assert sorted({i.pagina for i in g.modelo.itens}) == [1, 3]
    _ate(lambda: len(g.modelo.recortes) == 4)            # a aberta e a do disco


def test_apagar_pelo_menu_muda_o_seletor_e_o_total(app, janela, monkeypatch):  # noqa: F811
    monkeypatch.setattr(dp, "perguntar_paginas", lambda *_a, **_k: ([2, 6], -1))
    janela.acao_apagar_paginas.trigger()
    assert janela.fonte.total == 58 and janela.seletor.maximum() == 58
    assert janela.total_de_paginas.text() == " de 58 "
    assert janela.acao_paginas_apagadas.isEnabled()


def test_inserir_pelo_menu(app, janela, monkeypatch, tmp_path):  # noqa: F811
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


def test_paginas_apagadas_pelo_menu_devolve(app, janela, monkeypatch):  # noqa: F811
    projeto = janela.projeto
    pids = projeto.sequencia.pids
    janela.pagina.operacoes.apagar_paginas([3])
    monkeypatch.setattr(dp, "perguntar_apagadas", lambda _j, apagadas: [apagadas[0].entrada.pid])
    janela.acao_paginas_apagadas.trigger()
    assert projeto.sequencia.pids == pids and not janela.acao_paginas_apagadas.isEnabled()


def test_a_gaveta_move_e_apaga_as_selecionadas(app, janela, monkeypatch):  # noqa: F811
    vistos = []
    monkeypatch.setattr(dp, "perguntar_paginas",
                        lambda _j, _t, _n, **k: vistos.append(k["selecao"]) or ([1, 2], 9))
    janela.mover_paginas([1, 2])                     # o que a gaveta emite
    assert vistos == ["2-3"]
    menu = janela.paginas.menu_de_contexto()
    textos = [a.text() for a in menu.actions()]
    assert any(t.startswith("Mover as selecionadas") for t in textos)
    assert any(t.startswith("Apagar as selecionadas") for t in textos)


def test_com_o_lote_rodando_as_operacoes_ficam_desligadas_com_o_motivo(app, janela):  # noqa: F811
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


def test_girar_cortar_e_dividir_pelo_menu(app, janela, monkeypatch):  # noqa: F811
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
    janela.pagina.desfazedor.desfazer()
    assert janela.fonte.total == 60
    monkeypatch.setattr(dp, "perguntar_com", lambda *_a, **_k: ([6], 1.25))
    janela.acao_endireitar_paginas.trigger()
    assert projeto.sequencia.entrada_em(6).angulo == 1.25


def test_o_angulo_medido_nao_e_arredondado_no_dialogo(app):
    """0,65° com uma casa viraria 0,7°, e dar OK sem mexer endireitaria a página."""
    campo = dp.campo_de_porcentagem(0.65, -20.0, 20.0, "°", decimais=2, passo=0.1)
    assert campo.value() == pytest.approx(0.65)
    campo.deleteLater()


def _acao(janela, comeco: str):  # noqa: F811
    return next(a for a in janela.paginas.menu_de_contexto().actions()
                if a.text().startswith(comeco))


def test_a_gaveta_exporta_as_selecionadas(app, janela, monkeypatch):  # noqa: F811
    """§3.1: as selecionadas vão ao diálogo, que não pergunta o intervalo."""
    from pathlib import Path

    from abbychess import exportar as ex
    from abbychess.app import dialogo_exportacao as de
    from abbychess.app import dialogos

    pedidos, exportados = [], []
    monkeypatch.setattr(dialogos, "destino_da_exportacao", lambda _j, _p: Path("x.txt"))
    monkeypatch.setattr(de, "perguntar", lambda _j, _p, _d, **k: pedidos.append(k["selecao"]) or de.Escolha(
        ex.Opcoes(selecao=tuple(k["selecao"])), {}, None))
    monkeypatch.setattr(janela.livro, "exportar", lambda _d, opcoes, _m, _c: exportados.append(opcoes))
    monkeypatch.setattr(janela.paginas, "selecionadas", lambda: [1, 4])
    _acao(janela, "Exportar as selecionadas (2)").trigger()
    assert pedidos == [[1, 4]] and exportados[0].selecao == (1, 4)


def test_a_gaveta_aplica_o_modelo_de_areas_nas_selecionadas(app, janela, monkeypatch):  # noqa: F811
    aplicados = []
    janela.areas.modelo = object()
    monkeypatch.setattr(janela.areas, "aplicar_modelo", aplicados.append)
    monkeypatch.setattr(janela.paginas, "selecionadas", lambda: [2, 5])
    _acao(janela, "Aplicar o modelo de áreas às selecionadas (2)").trigger()
    assert aplicados == [[2, 5]]


def test_sem_modelo_salvo_a_gaveta_diz_o_que_falta(app, janela, monkeypatch):  # noqa: F811
    aplicados = []
    janela.areas.modelo = None
    monkeypatch.setattr(janela.areas, "aplicar_modelo", aplicados.append)
    monkeypatch.setattr(janela.paginas, "selecionadas", lambda: [2])
    _acao(janela, "Aplicar o modelo de áreas às selecionadas (1)").trigger()
    assert not aplicados and "Salve um modelo" in janela.statusBar().currentMessage()
