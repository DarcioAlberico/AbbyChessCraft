"""A janela inteira, sem tela: o fluxo de treino passa pelos sinais de verdade.

O leitor entra sem a rede global (`ocr=None`), como em `test_treino_por_livro`,
para o teste não depender do modelo do PyBoxEditor nem levar segundos para
carregá-lo. O resto, inclusive as tarefas em segundo plano, é o código real.
"""

from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from abbychess.app.janela import JanelaPrincipal  # noqa: E402
from abbychess.leitor import FONTE_LIVRO, FONTE_MANUAL, LeitorDoLivro  # noqa: E402
from abbychess import pagina as pg  # noqa: E402
from abbychess.projeto import ProjetoDeLivro  # noqa: E402

from tests.test_treino_por_livro import _pagina_sintetica  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app, tmp_path, monkeypatch):
    # Toda pergunta é respondida com "sim", para o teste não esperar clique.
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    fonte = _pagina_sintetica(tmp_path / "pagina.png")
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Teste", fonte)
    j = JanelaPrincipal()
    j.projeto = projeto
    j.fonte = pg.FonteDePaginas(projeto.fonte)
    j.leitor = LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)
    j.seletor.setMaximum(j.fonte.total)
    j.ir_para_pagina(0, salvar=False)
    yield j
    j.close()


def _esperar(app, janela, limite=20.0):
    fim = time.monotonic() + limite
    while janela.executor.ocupado and time.monotonic() < fim:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    assert not janela.executor.ocupado, "a tarefa não terminou no prazo"


def test_pagina_nova_pede_reconhecimento(janela):
    assert janela.boxes == []
    assert "F5" in janela.treino.leitura.text()


def test_reconhecer_poe_o_primeiro_pendente_no_painel(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    assert len(janela.boxes) >= 15
    assert janela.atual == janela._fila()[0]
    assert janela.treino.campo.isEnabled()
    assert janela.projeto.carregar_pagina(0) == janela.boxes


def test_enter_ensina_e_resolve_as_repeticoes(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    janela._mostrar_box(0)  # o primeiro "a" da página
    pendentes_antes = len(janela._fila())

    janela.treino.campo.setText("a")
    janela.treino._ensinar()
    _esperar(app, janela)

    assert janela.boxes[0].source == FONTE_MANUAL
    assert sum(b.source == FONTE_LIVRO for b in janela.boxes) == 4
    assert len(janela._fila()) == pendentes_antes - 5
    assert "a" in janela.padroes._padroes
    # A página gravada já tem a decisão: fechar agora não perde nada.
    assert janela.projeto.carregar_pagina(0)[0].source == FONTE_MANUAL


def test_shift_enter_corrige_sem_gravar_padrao(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    janela._mostrar_box(1)
    janela.treino.campo.setText("b")
    janela.treino._so_corrigir()
    assert (janela.boxes[1].char, janela.boxes[1].source) == ("b", FONTE_MANUAL)
    assert janela.leitor.padroes_por_caractere() == {}


def test_descartar_tira_o_box_e_mantem_os_pulados_coerentes(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    total = len(janela.boxes)
    janela._mostrar_box(3)
    janela._andar_na_fila(+1)            # pula o 3
    janela._mostrar_box(0)
    janela.treino._descartar()           # tira o 0: o pulado vira o 2
    assert len(janela.boxes) == total - 1
    assert janela.pulados == {2}


def test_pular_manda_o_box_para_o_fim_da_fila(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    primeiro = janela.atual
    janela._andar_na_fila(+1)
    assert janela.atual != primeiro
    assert janela._fila()[-1] == primeiro


def test_esquecer_rele_a_pagina_sem_o_padrao(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    janela._mostrar_box(0)
    janela.treino.campo.setText("a")
    janela.treino._ensinar()
    _esperar(app, janela)

    janela._esquecer([str(p) for p in janela.leitor.padroes_por_caractere()["a"]])
    _esperar(app, janela)

    assert janela.leitor.padroes_por_caractere() == {}
    assert not any(b.source == FONTE_LIVRO for b in janela.boxes)
    assert janela.boxes[0].source == FONTE_MANUAL  # a decisão do usuário fica


def _colar_os_dois_primeiros(app, janela):
    """Reconhece e junta o primeiro "a" com o "b": o box colado a dividir."""
    janela.reconhecer()
    _esperar(app, janela)
    a, b = janela.boxes[0], janela.boxes[1]
    janela._mostrar_box(0)
    janela.treino._juntar(+1)
    return a, b


def test_ctrl_j_junta_com_o_seguinte_e_remapeia_os_pulados(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    total = len(janela.boxes)
    janela._mostrar_box(5)
    janela._andar_na_fila(+1)            # pula o 5
    janela._mostrar_box(1)
    janela.treino._juntar(-1)            # junta o 1 com o 0: o pulado vira o 4
    assert len(janela.boxes) == total - 1
    assert janela.atual == 0
    assert janela.pulados == {4}
    assert len(janela.projeto.carregar_pagina(0)) == total - 1


def test_juntar_sem_vizinho_na_linha_nao_muda_nada(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    total = len(janela.boxes)
    janela._mostrar_box(0)
    janela.treino._juntar(-1)
    assert len(janela.boxes) == total
    assert "anterior" in janela.statusBar().currentMessage()


def test_dividir_no_ponto_clicado_do_recorte(app, janela):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    a, b = _colar_os_dois_primeiros(app, janela)
    total = len(janela.boxes)
    janela.show()
    app.processEvents()

    # Clica no meio do vão entre o "a" e o "b", no recorte ampliado.
    glifo, colado = janela.treino.glifo, janela.boxes[0]
    pixmap = glifo.pixmap()
    fracao = ((a.x2 + b.x1) / 2 - colado.x1) / (colado.x2 - colado.x1)
    x = (glifo.width() - pixmap.width()) / 2 + fracao * pixmap.width()
    QTest.mouseClick(glifo, Qt.MouseButton.LeftButton, pos=QPoint(round(x), glifo.height() // 2))
    assert a.x2 <= janela.treino.corte <= b.x1
    assert janela.visor._corte is not None  # a linha do corte também aparece na página

    janela.treino._dividir()

    assert len(janela.boxes) == total + 1
    assert (janela.boxes[0].x1, janela.boxes[0].x2) == (a.x1, a.x2)
    assert (janela.boxes[1].x1, janela.boxes[1].x2) == (b.x1, b.x2)
    assert janela.atual == 0
    # Sem padrões e sem rede ninguém lê as partes: as duas estão na fila.
    assert {0, 1} <= set(janela._fila())
    assert janela.treino.corte is None


def test_dividir_remapeia_os_pulados_e_ensina_cada_parte(app, janela):
    a, b = _colar_os_dois_primeiros(app, janela)
    janela._mostrar_box(4)
    janela._andar_na_fila(+1)            # pula o 4
    janela._mostrar_box(0)
    janela.treino._dividir()             # corte pela tinta; o pulado vira o 5
    assert janela.pulados == {5}

    janela.treino.campo.setText("a")
    janela.treino._ensinar()
    _esperar(app, janela)
    janela._mostrar_box(1)
    janela.treino.campo.setText("b")
    janela.treino._ensinar()
    _esperar(app, janela)
    assert set(janela.leitor.padroes_por_caractere()) == {"a", "b"}


def test_menu_do_visor_divide_no_ponto(app, janela):
    a, b = _colar_os_dois_primeiros(app, janela)
    total = len(janela.boxes)
    menu = janela.visor.menu_do_box(0, (a.x2 + b.x1) // 2)
    [dividir] = [acao for acao in menu.actions() if acao.text() == "Dividir aqui"]
    dividir.trigger()
    assert len(janela.boxes) == total + 1
    assert (janela.boxes[0].x2, janela.boxes[1].x1) == (a.x2, b.x1)


def test_alt_seta_move_as_bordas(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    janela._mostrar_box(0)
    x1, y1, x2, y2 = (janela.boxes[0].x1, janela.boxes[0].y1,
                      janela.boxes[0].x2, janela.boxes[0].y2)
    janela.treino._ajustar(0, 0, 1, 0)   # Alt+→: borda direita
    janela.treino._ajustar(-1, 0, 0, 0)  # Alt+Shift+←: borda esquerda
    janela.treino._ajustar(0, -1, 0, 0)  # Alt+Shift+↑: borda de cima
    b = janela.boxes[0]
    assert (b.x1, b.y1, b.x2, b.y2) == (x1 - 1, y1 - 1, x2 + 1, y2)
    assert janela.atual == 0
    assert janela.projeto.carregar_pagina(0)[0].x2 == x2 + 1


def _no_visor(janela, x, y):
    """O ponto da página (cena) em coordenadas do viewport do visor."""
    return janela.visor.mapFromScene(x, y)


def test_ferramentas_tem_o_modo_de_treino_e_as_opcoes(janela):
    textos = [a.text() for a in janela.menu_ferramentas.actions()]
    assert "Modo de treino (Ctrl+T)" in textos and "Opções…" in textos
    assert janela.acao_modo_treino.isCheckable()


def test_modo_treino_arraste_marca_um_glifo_e_enter_o_ensina(app, janela):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    janela.reconhecer()
    _esperar(app, janela)
    janela.show()
    janela.visor.resetTransform()        # 1 px de página = 1 px de tela
    app.processEvents()
    total = len(janela.boxes)
    a, b = janela.boxes[0], janela.boxes[1]

    janela.acao_modo_treino.trigger()
    assert janela.visor.modo_treino
    porta = janela.visor.viewport()
    inicio, fim = _no_visor(janela, a.x1 - 4, b.y1 - 4), _no_visor(janela, b.x2 + 1, a.y2 + 4)
    QTest.mousePress(porta, Qt.MouseButton.LeftButton, pos=inicio)
    QTest.mouseMove(porta, fim)
    QTest.mouseRelease(porta, Qt.MouseButton.LeftButton, pos=fim)

    assert len(janela.boxes) == total - 1  # o quadro substituiu o "a" e o "b"
    novo = janela.boxes[janela.atual]
    assert (novo.x1, novo.x2) == (a.x1, b.x2)

    janela.treino.campo.setText("ab")
    janela.treino._ensinar()
    _esperar(app, janela)
    assert "ab" in janela.leitor.padroes_por_caractere()


def test_ctrl_clique_seleciona_e_enter_ensina_todos(app, janela):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    janela.reconhecer()
    _esperar(app, janela)
    janela.show()
    janela.visor.resetTransform()
    app.processEvents()
    janela._mostrar_box(0)
    porta = janela.visor.viewport()
    for i in (3, 6):                     # os outros "a" da primeira linha
        b = janela.boxes[i]
        QTest.mouseClick(porta, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier,
                         _no_visor(janela, (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2))
    assert janela.selecao == {0, 3, 6}
    assert "3 glifos" in janela.treino.selecao.text()

    janela.treino.campo.setText("a")
    janela.treino._ensinar()
    _esperar(app, janela)

    assert len(janela.leitor.padroes_por_caractere()["a"]) == 3
    assert janela.selecao == set()
    assert sum(b.char == "a" and b.source == FONTE_LIVRO for b in janela.boxes) == 2


def test_ctrl_clique_de_novo_tira_da_selecao_e_esc_esvazia(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    janela._mostrar_box(0)
    janela._alternar_na_selecao(3)
    janela._alternar_na_selecao(6)
    janela._alternar_na_selecao(3)
    assert janela.selecao == {0, 6}
    janela.treino.limpar_selecao.emit()
    assert janela.selecao == set() and janela.treino.selecao.text() == ""


def test_opcoes_gravam_os_limiares_e_refazem_a_fila(app, janela):
    from abbychess.projeto import Limiares

    janela.reconhecer()
    _esperar(app, janela)
    janela._mostrar_box(0)
    janela.treino.campo.setText("a")
    janela.treino._ensinar()
    _esperar(app, janela)
    assert sum(b.source == FONTE_LIVRO for b in janela.boxes) == 4

    # Livro exigente demais: nenhum padrão aceito na próxima leitura.
    janela.aplicar_limiares(Limiares(livro=0.999))
    assert ProjetoDeLivro.abrir(janela.projeto.pasta).dados.limiares.livro == 0.999
    assert janela.leitor.padroes.distancia_maxima < 5
