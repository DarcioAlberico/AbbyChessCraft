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
from tests.janela_util import atual, boxes, fila, mostrar, pulados, selecao  # noqa: E402,F401


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
    j.usar(projeto, pg.FonteDePaginas(projeto.fonte),
          LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
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
    assert boxes(janela) == []
    assert "F5" in janela.treino.leitura.text()


def test_reconhecer_poe_o_primeiro_pendente_no_painel(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    assert len(boxes(janela)) >= 15
    assert atual(janela) == fila(janela)[0]
    assert janela.treino.campo.isEnabled()
    assert janela.projeto.carregar_pagina(0) == boxes(janela)


def test_enter_ensina_e_resolve_as_repeticoes(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    mostrar(janela, 0)  # o primeiro "a" da página
    pendentes_antes = len(fila(janela))

    janela.treino.campo.setText("a")
    janela.treino._ensinar()
    _esperar(app, janela)

    assert boxes(janela)[0].source == FONTE_MANUAL
    assert sum(b.source == FONTE_LIVRO for b in boxes(janela)) == 4
    assert len(fila(janela)) == pendentes_antes - 5
    assert "a" in janela.padroes._padroes
    # A página gravada já tem a decisão: fechar agora não perde nada.
    assert janela.projeto.carregar_pagina(0)[0].source == FONTE_MANUAL


def test_shift_enter_corrige_sem_gravar_padrao(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    mostrar(janela, 1)
    janela.treino.campo.setText("b")
    janela.treino._so_corrigir()
    assert (boxes(janela)[1].char, boxes(janela)[1].source) == ("b", FONTE_MANUAL)
    assert janela.leitor.padroes_por_caractere() == {}


def test_descartar_tira_o_box_e_mantem_os_pulados_coerentes(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    total = len(boxes(janela))
    mostrar(janela, 3)
    janela.pagina.andar(+1)            # pula o 3
    mostrar(janela, 0)
    janela.treino._descartar()           # tira o 0: o pulado vira o 2
    assert len(boxes(janela)) == total - 1
    assert pulados(janela) == {2}


def test_pular_manda_o_box_para_o_fim_da_fila(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    primeiro = atual(janela)
    janela.pagina.andar(+1)
    assert atual(janela) != primeiro
    assert fila(janela)[-1] == primeiro


def test_esquecer_rele_a_pagina_sem_o_padrao(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    mostrar(janela, 0)
    janela.treino.campo.setText("a")
    janela.treino._ensinar()
    _esperar(app, janela)

    janela.pagina.esquecer([str(p) for p in janela.leitor.padroes_por_caractere()["a"]])
    _esperar(app, janela)

    assert janela.leitor.padroes_por_caractere() == {}
    assert not any(b.source == FONTE_LIVRO for b in boxes(janela))
    assert boxes(janela)[0].source == FONTE_MANUAL  # a decisão do usuário fica


def _colar_os_dois_primeiros(app, janela):
    """Reconhece e junta o primeiro "a" com o "b": o box colado a dividir."""
    janela.reconhecer()
    _esperar(app, janela)
    a, b = boxes(janela)[0], boxes(janela)[1]
    mostrar(janela, 0)
    janela.treino._juntar(+1)
    return a, b


def test_ctrl_j_junta_com_o_seguinte_e_remapeia_os_pulados(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    total = len(boxes(janela))
    mostrar(janela, 5)
    janela.pagina.andar(+1)            # pula o 5
    mostrar(janela, 1)
    janela.treino._juntar(-1)            # junta o 1 com o 0: o pulado vira o 4
    assert len(boxes(janela)) == total - 1
    assert atual(janela) == 0
    assert pulados(janela) == {4}
    assert len(janela.projeto.carregar_pagina(0)) == total - 1


def test_juntar_sem_vizinho_na_linha_nao_muda_nada(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    total = len(boxes(janela))
    mostrar(janela, 0)
    janela.treino._juntar(-1)
    assert len(boxes(janela)) == total
    assert "anterior" in janela.statusBar().currentMessage()


def test_dividir_no_ponto_clicado_do_recorte(app, janela):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    a, b = _colar_os_dois_primeiros(app, janela)
    total = len(boxes(janela))
    janela.show()
    app.processEvents()

    # Clica no meio do vão entre o "a" e o "b", no recorte ampliado.
    glifo, colado = janela.treino.glifo, boxes(janela)[0]
    pixmap = glifo.pixmap()
    fracao = ((a.x2 + b.x1) / 2 - colado.x1) / (colado.x2 - colado.x1)
    x = (glifo.width() - pixmap.width()) / 2 + fracao * pixmap.width()
    QTest.mouseClick(glifo, Qt.MouseButton.LeftButton, pos=QPoint(round(x), glifo.height() // 2))
    assert a.x2 <= janela.treino.corte <= b.x1
    assert janela.visor._corte is not None  # a linha do corte também aparece na página

    janela.treino._dividir()

    assert len(boxes(janela)) == total + 1
    assert (boxes(janela)[0].x1, boxes(janela)[0].x2) == (a.x1, a.x2)
    assert (boxes(janela)[1].x1, boxes(janela)[1].x2) == (b.x1, b.x2)
    assert atual(janela) == 0
    # Sem padrões e sem rede ninguém lê as partes: as duas estão na fila.
    assert {0, 1} <= set(fila(janela))
    assert janela.treino.corte is None


def test_dividir_remapeia_os_pulados_e_ensina_cada_parte(app, janela):
    a, b = _colar_os_dois_primeiros(app, janela)
    mostrar(janela, 4)
    janela.pagina.andar(+1)            # pula o 4
    mostrar(janela, 0)
    janela.treino._dividir()             # corte pela tinta; o pulado vira o 5
    assert pulados(janela) == {5}

    janela.treino.campo.setText("a")
    janela.treino._ensinar()
    _esperar(app, janela)
    mostrar(janela, 1)
    janela.treino.campo.setText("b")
    janela.treino._ensinar()
    _esperar(app, janela)
    assert set(janela.leitor.padroes_por_caractere()) == {"a", "b"}


def test_menu_do_visor_divide_no_ponto(app, janela):
    a, b = _colar_os_dois_primeiros(app, janela)
    total = len(boxes(janela))
    menu = janela.visor.menu_do_box(0, (a.x2 + b.x1) // 2)
    [dividir] = [acao for acao in menu.actions() if acao.text() == "Dividir aqui"]
    dividir.trigger()
    assert len(boxes(janela)) == total + 1
    assert (boxes(janela)[0].x2, boxes(janela)[1].x1) == (a.x2, b.x1)


def test_alt_seta_move_as_bordas(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    mostrar(janela, 0)
    x1, y1, x2, y2 = (boxes(janela)[0].x1, boxes(janela)[0].y1,
                      boxes(janela)[0].x2, boxes(janela)[0].y2)
    janela.treino._ajustar(0, 0, 1, 0)   # Alt+→: borda direita
    janela.treino._ajustar(-1, 0, 0, 0)  # Alt+Shift+←: borda esquerda
    janela.treino._ajustar(0, -1, 0, 0)  # Alt+Shift+↑: borda de cima
    b = boxes(janela)[0]
    assert (b.x1, b.y1, b.x2, b.y2) == (x1 - 1, y1 - 1, x2 + 1, y2)
    assert atual(janela) == 0
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
    total = len(boxes(janela))
    a, b = boxes(janela)[0], boxes(janela)[1]

    janela.acao_modo_treino.trigger()
    assert janela.visor.modo_treino
    porta = janela.visor.viewport()
    inicio, fim = _no_visor(janela, a.x1 - 4, b.y1 - 4), _no_visor(janela, b.x2 + 1, a.y2 + 4)
    QTest.mousePress(porta, Qt.MouseButton.LeftButton, pos=inicio)
    QTest.mouseMove(porta, fim)
    QTest.mouseRelease(porta, Qt.MouseButton.LeftButton, pos=fim)

    assert len(boxes(janela)) == total - 1  # o quadro substituiu o "a" e o "b"
    novo = boxes(janela)[atual(janela)]
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
    mostrar(janela, 0)
    porta = janela.visor.viewport()
    for i in (3, 6):                     # os outros "a" da primeira linha
        b = boxes(janela)[i]
        QTest.mouseClick(porta, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier,
                         _no_visor(janela, (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2))
    assert selecao(janela) == {0, 3, 6}
    assert "3 glifos" in janela.treino.selecao.text()

    janela.treino.campo.setText("a")
    janela.treino._ensinar()
    _esperar(app, janela)

    assert len(janela.leitor.padroes_por_caractere()["a"]) == 3
    assert selecao(janela) == set()
    assert sum(b.char == "a" and b.source == FONTE_LIVRO for b in boxes(janela)) == 2


def test_ctrl_clique_de_novo_tira_da_selecao_e_esc_esvazia(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    mostrar(janela, 0)
    janela.pagina.alternar_na_selecao(3)
    janela.pagina.alternar_na_selecao(6)
    janela.pagina.alternar_na_selecao(3)
    assert selecao(janela) == {0, 6}
    janela.treino.limpar_selecao.emit()
    assert selecao(janela) == set() and janela.treino.selecao.text() == ""


def test_opcoes_gravam_os_limiares_e_refazem_a_fila(app, janela):
    from abbychess.projeto import Limiares

    janela.reconhecer()
    _esperar(app, janela)
    mostrar(janela, 0)
    janela.treino.campo.setText("a")
    janela.treino._ensinar()
    _esperar(app, janela)
    assert sum(b.source == FONTE_LIVRO for b in boxes(janela)) == 4

    # Livro exigente demais: nenhum padrão aceito na próxima leitura.
    janela.pagina.aplicar_limiares(Limiares(livro=0.999))
    assert ProjetoDeLivro.abrir(janela.projeto.pasta).dados.limiares.livro == 0.999
    assert janela.leitor.padroes.distancia_maxima < 5


def test_opcoes_refazem_os_pendentes_do_livro_json(app, janela):
    import json

    from abbychess.projeto import ARQUIVO_DO_LIVRO, Limiares

    janela.reconhecer()
    _esperar(app, janela)
    for revisao in (0.5, 1.0, 0.0):
        janela.pagina.aplicar_limiares(Limiares(revisao=revisao))
        gravado = json.loads((janela.projeto.pasta / ARQUIVO_DO_LIVRO).read_text(encoding="utf-8"))
        assert gravado == janela.projeto.recalcular_livro(), revisao


# ----------------------------------------------------------------------
# Passo 2a: a fila visível e o gravador
# ----------------------------------------------------------------------

def test_comando_com_tarefa_rodando_entra_na_fila_e_aparece(app, janela):
    import threading

    trava = threading.Event()
    janela.executor.rodar("Tarefa lenta", lambda: ((lambda _p: trava.wait(10)), lambda _r: None))
    janela.reconhecer()                       # não é ignorado: espera a vez
    assert "Na fila: Reconhecendo a página" in janela.statusBar().currentMessage()
    trava.set()
    _esperar(app, janela)
    assert len(boxes(janela)) >= 15           # e rodou depois


def test_editar_nao_grava_na_hora_e_fechar_grava(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    mostrar(janela, 1)
    janela.treino.campo.setText("q")
    janela.treino._so_corrigir()
    projeto = janela.projeto
    assert projeto.sujas                      # entregue ao gravador, ainda não gravado
    janela.close()
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    try:
        assert reaberto.carregar_pagina(0)[1].char == "q"
    finally:
        reaberto.fechar()


def test_falha_de_gravacao_aparece_na_barra(app, janela, monkeypatch):
    from abbychess import gravacao as gv

    janela.reconhecer()
    _esperar(app, janela)

    def falhar(*_a, **_k):
        raise PermissionError("disco cheio")

    monkeypatch.setattr(gv, "gravar_json", falhar)
    try:
        mostrar(janela, 1)
        janela.treino.campo.setText("q")
        janela.treino._so_corrigir()
        janela.projeto.descarregar(5)
        fim = time.monotonic() + 5
        while ("não foi gravada" not in janela.statusBar().currentMessage()
               and time.monotonic() < fim):
            app.processEvents()
            time.sleep(0.01)
        print(repr(janela.statusBar().currentMessage()))
        assert "A página 1 não foi gravada (disco cheio)" in janela.statusBar().currentMessage()
        assert janela.projeto.sujas
    finally:
        monkeypatch.undo()                   # o fechar da fixture grava (e não pergunta)
