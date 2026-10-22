"""A janela com o livro inteiro: lote em segundo plano, F6 entre páginas e exportação.

Como em `test_janela`, o leitor roda sem a rede global, e o resto é o código
real, com as tarefas no `Executor`. As perguntas e os diálogos de arquivo são
trocados por respostas fixas.
"""

from __future__ import annotations

import os
import json
import zipfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (QApplication, QFileDialog, QInputDialog, QMenu,  # noqa: E402
                               QMessageBox)

from abbychess import livro as lv  # noqa: E402
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

    def pergunta(*a, **_k):
        estado["perguntas"] += 1
        estado["texto"] = a[2] if len(a) > 2 else ""
        return estado["pergunta"]

    monkeypatch.setattr(QMessageBox, "question", pergunta)
    monkeypatch.setattr(QInputDialog, "getText",
                        lambda *a, **k: (estado["intervalo"], True))
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (estado["arquivo"], "EPUB (*.epub)"))

    # O diálogo da exportação: `estado["exportacao"]` preenche o formulário, e ele aceita.
    from PySide6.QtWidgets import QDialog

    from abbychess.app.dialogo_exportacao import DialogoDeExportacao

    def exec_(dialogo):
        estado["dialogo"] = dialogo
        preencher = estado.get("exportacao")
        if preencher is not None:
            preencher(dialogo)
        dialogo.done(QDialog.DialogCode.Accepted)        # como o exec de verdade termina
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DialogoDeExportacao, "exec", exec_)
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


def test_cartao_de_saude_mostra_a_evolucao_e_oferece_o_lote(janela):
    chamadas = []
    janela.paginas.reconhecer_livro.disconnect()
    janela.paginas.reconhecer_livro.connect(lambda: chamadas.append(True))

    janela.paginas.mostrar_saude(lv.SaudeDoLivro((0, 1, 2), 40, 3, 12, 4))

    assert janela.paginas.saude.isHidden() is False
    assert janela.paginas.amostra_da_saude.text() == "Amostra: 3 páginas"
    assert janela.paginas.pendentes_da_saude.text() == "Pendentes: 40 → 3"
    assert janela.paginas.padroes_da_saude.text() == "Padrões ensinados: 12"
    assert janela.paginas.botao_reconhecer_livro.isDefault()
    janela.paginas.botao_reconhecer_livro.click()
    assert chamadas == [True]


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

    def preencher(dialogo):
        dialogo.autores.setText("Yasser Seirawan; Jeremy Silman")
        dialogo.data.setText("2012-05")
    respostas["exportacao"] = preencher
    janela.exportar()
    _esperar(app, janela)
    destino = tmp_path / "saida.epub"
    assert destino.is_file()
    with zipfile.ZipFile(destino) as z:
        assert z.namelist()[0] == "mimetype"
        opf = z.read("OEBPS/content.opf").decode("utf-8")
    assert "<dc:creator>Jeremy Silman</dc:creator>" in opf and "<dc:date>2012-05</dc:date>" in opf
    assert "Exportado em saida.epub" in janela.statusBar().currentMessage()
    # O formulário ficou no projeto: a próxima exportação já o traz preenchido.
    gravado = json.loads((janela.projeto.pasta / "metadados.json").read_text(encoding="utf-8"))
    assert gravado == {"autores": ["Yasser Seirawan", "Jeremy Silman"], "data": "2012-05"}
    respostas["exportacao"] = None
    janela.exportar()
    _esperar(app, janela)
    assert respostas["dialogo"].autores.text() == "Yasser Seirawan; Jeremy Silman"
    assert respostas["dialogo"].marcas.isEnabled() is False      # é do TXT


def test_a_pergunta_do_lote_diz_que_as_correcoes_ficam_e_conta_as_verificadas_a_parte(
        app, janela, respostas):
    from abbychess.modelo import VERIFICADA

    respostas["intervalo"] = "1-3"
    janela.reconhecer_livro()
    _esperar(app, janela)
    janela.projeto.descarregar(10)
    pagina = janela.projeto.carregar_modelo(2)
    pagina.estado = VERIFICADA
    janela.projeto.salvar_modelo(pagina)
    respostas["perguntas"], respostas["pergunta"] = 0, NAO
    janela.reconhecer_livro()
    _esperar(app, janela)
    texto = respostas["texto"]
    assert "2 das 3" in texto and "1 verificada" in texto
    assert "mantendo as correções manuais" in texto and "Voltar ao estado antes do lote" in texto


def test_a_previa_que_chega_depois_de_fechar_o_dialogo_nao_abre_janela(app, janela, respostas,
                                                                       tmp_path):
    janela.reconhecer_livro()
    _esperar(app, janela)
    respostas["arquivo"] = str(tmp_path / "saida.epub")
    respostas["exportacao"] = lambda dialogo: dialogo.previsualizar()
    janela.exportar()                       # pede a prévia e fecha com Exportar
    _esperar(app, janela)                   # a prévia chega, depois a exportação
    dialogo = respostas["dialogo"]
    assert dialogo.vivo is False and dialogo.janela_da_previa is None
    assert (tmp_path / "saida.epub").is_file()


def test_previa_pelo_controlador_chega_ao_dialogo(app, janela, tmp_path):
    from abbychess import exportar as ex
    from abbychess.app.dialogo_exportacao import DialogoDeExportacao

    janela.reconhecer_livro()
    _esperar(app, janela)
    dialogo = DialogoDeExportacao(janela, "epub", ex.Opcoes(), {}, tmp_path, "Livro")
    dialogo.ao_previsualizar = lambda f, o, m: janela.livro.previa(
        f, o, m, dialogo.mostrar_previa, dialogo.previa_falhou)
    dialogo.previsualizar()
    assert not dialogo.btn_exportar.isEnabled()   # Exportar espera a prévia
    _esperar(app, janela)
    texto = dialogo.janela_da_previa.navegador.toPlainText()
    # As páginas desta fixture não têm caracteres ensinados: a prévia mostra as marcas delas.
    assert "Pré-visualização" in texto and "Relatório" in texto and "Página 3" in texto
    assert dialogo.btn_exportar.isEnabled()
    dialogo.reject()
    assert not dialogo.janela_da_previa.isVisible()   # fechar o diálogo fecha a prévia
