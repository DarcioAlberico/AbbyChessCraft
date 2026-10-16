"""A janela com o livro inteiro: lote em segundo plano, F6 entre páginas e exportação.

Como em `test_janela`, o leitor roda sem a rede global, e o resto é o código
real, com as tarefas no `Executor`. As perguntas e os diálogos de arquivo são
trocados por respostas fixas.
"""

from __future__ import annotations

import os
import zipfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (QApplication, QFileDialog, QInputDialog, QMenu,  # noqa: E402
                               QMessageBox)

from abbychess import pagina as pg  # noqa: E402
from abbychess.app.janela import JanelaPrincipal  # noqa: E402
from abbychess.leitor import FONTE_MANUAL, LeitorDoLivro  # noqa: E402
from abbychess.projeto import ProjetoDeLivro  # noqa: E402

from tests.test_janela import _esperar  # noqa: E402
from tests.test_livro import pdf_sintetico  # noqa: E402
from tests.janela_util import trocar_entries  # noqa: E402
from tests.janela_util import atual, boxes, fila, mostrar, pulados, selecao  # noqa: E402,F401

SIM = QMessageBox.StandardButton.Yes
NAO = QMessageBox.StandardButton.No


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def respostas(monkeypatch):
    """O que os diálogos respondem; o teste muda antes de agir."""
    estado = {"intervalo": "1-3", "pergunta": SIM, "perguntas": 0, "arquivo": ""}

    def pergunta(*_a, **_k):
        estado["perguntas"] += 1
        return estado["pergunta"]

    monkeypatch.setattr(QMessageBox, "question", pergunta)
    monkeypatch.setattr(QInputDialog, "getText",
                        lambda *a, **k: (estado["intervalo"], True))
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (estado["arquivo"], "EPUB (*.epub)"))
    return estado


@pytest.fixture
def janela(app, tmp_path, respostas):
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Livro", pdf_sintetico(tmp_path))
    j = JanelaPrincipal()
    j.usar(projeto, pg.FonteDePaginas(projeto.fonte),
          LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    yield j
    j.close()


def test_menu_ferramentas_tem_o_lote_e_o_projeto_a_exportacao(janela):
    ferramentas = [a.text() for a in janela.menu_ferramentas.actions()]
    pagina = next(m for m in janela.menuBar().findChildren(QMenu) if m.title() == "P&ágina")
    assert "Reconhecer o livro…" in ferramentas
    assert "Próxima página com pendentes" in [a.text() for a in pagina.actions()]
    projeto = next(m for m in janela.menuBar().findChildren(QMenu) if m.title() == "&Projeto")
    assert "Exportar…" in [a.text() for a in projeto.actions()]
    assert janela.acao_lote.isEnabled() and not janela.acao_cancelar_lote.isEnabled()


def test_lote_reconhece_o_intervalo_e_mostra_a_pagina_atual(app, janela, respostas):
    respostas["intervalo"] = "1-2"
    janela.reconhecer_livro()
    assert janela.acao_cancelar_lote.isEnabled()
    _esperar(app, janela)
    assert janela.projeto.paginas_lidas() == [0, 1]
    assert boxes(janela), "a página aberta foi lida no lote e recarregada"
    assert "Lote concluído" in janela.statusBar().currentMessage()
    assert not janela.acao_cancelar_lote.isEnabled()
    assert respostas["perguntas"] == 0  # nada lido antes: nada a perguntar


def test_lote_pergunta_e_pula_as_ja_lidas(app, janela, respostas):
    janela.reconhecer()
    _esperar(app, janela)
    mostrar(janela, 0)
    janela.treino.campo.setText("a")
    janela.treino.pedir_so_corrigir()

    respostas["pergunta"] = NAO
    janela.reconhecer_livro()
    _esperar(app, janela)
    assert respostas["perguntas"] == 1
    assert janela.projeto.paginas_lidas() == [0, 1, 2]
    assert janela.projeto.carregar_pagina(0)[0].source == FONTE_MANUAL


def test_cancelar_o_lote_guarda_o_que_ja_foi_lido(app, janela, respostas):
    janela.reconhecer_livro()
    janela.livro.cancelar()
    _esperar(app, janela)
    assert "Lote cancelado" in janela.statusBar().currentMessage()
    assert len(janela.projeto.paginas_lidas()) < 3


def test_f6_vai_para_a_proxima_pagina_com_pendentes(app, janela):
    janela.reconhecer_livro()
    _esperar(app, janela)
    # Resolve a página 1 inteira; a 2 também, e o F6 tem de achar a 3.
    def resolver(e):
        e.char, e.source, e.confidence = "a", FONTE_MANUAL, 1.0

    trocar_entries(janela, 0, resolver)
    trocar_entries(janela, 1, resolver)

    janela.livro.proximo_pendente()
    assert janela.pagina.indice == 2
    assert atual(janela) == fila(janela)[0]

    # Com pendentes na página aberta, F6 fica nela.
    janela.livro.proximo_pendente()
    assert janela.pagina.indice == 2


def test_exportar_epub_pela_janela(app, janela, respostas, tmp_path):
    janela.reconhecer_livro()
    _esperar(app, janela)
    respostas["arquivo"] = str(tmp_path / "saida")  # sem extensão: vale o filtro
    janela.exportar()
    _esperar(app, janela)
    destino = tmp_path / "saida.epub"
    assert destino.is_file()
    with zipfile.ZipFile(destino) as z:
        assert z.namelist()[0] == "mimetype"
    assert "Exportado em saida.epub" in janela.statusBar().currentMessage()
