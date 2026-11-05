"""T1, bloco 1 (M1): CA-U4 (reabrir volta tamanho, divisores e projeto), CA-U5a (F8 chega ao fim),
CA-U8 (Ctrl+Shift+N na Galeria troca a seleção) e CA-U1a (Alt+3 e digitar escreve no Documento;
clique e fim de tarefa não movem o foco dele)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from abbychess import pagina as pg
from abbychess.app import recentes
from abbychess.app.galeria import Item
from abbychess.app.janela import JanelaPrincipal, configuracao
from abbychess.controlador_de_diagramas import ControladorDeDiagramas
from abbychess.leitor import LeitorDoLivro
from abbychess.projeto import ProjetoDeLivro
from tests.ajudantes import (ExecutorManual, _controlador, _escrever, _lido, _pagina_sintetica,
                             _pdf_digital)


@pytest.fixture
def configuracao_limpa(app):
    config = configuracao()
    config.clear()
    yield config
    config.clear()


def _janela_com(projeto) -> JanelaPrincipal:
    j = JanelaPrincipal()
    j.usar(projeto, pg.FonteDePaginas(projeto.fonte),
           LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    return j


@pytest.fixture
def janela(app, tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path, "Livro", _pagina_sintetica(tmp_path / "p.png"))
    j = _janela_com(projeto)
    j.resize(1366, 768)
    j.show()
    j.activateWindow()
    app.processEvents()
    yield j
    j.close()


# ------------------------------------------------------------------
# U-4
# ------------------------------------------------------------------
def test_ca_u4_a_geometria_gravada_volta(app, configuracao_limpa):
    primeira = JanelaPrincipal()
    primeira.resize(760, 610)
    primeira.show()
    app.processEvents()
    primeira.close()
    segunda = JanelaPrincipal()
    segunda.restaurar_a_geometria()
    assert (segunda.width(), segunda.height()) == (760, 610)
    segunda.close()


def test_a_geometria_estragada_nao_impede_de_abrir(app, configuracao_limpa):
    configuracao_limpa.setValue("geometria", "isto não é geometria")
    j = JanelaPrincipal()
    j.restaurar_a_geometria()
    assert j.width() > 0
    j.close()


def test_os_recentes_guardam_a_ordem_sem_repetir(configuracao_limpa, tmp_path):
    for nome in ("a", "b", "a", "c"):
        recentes.lembrar(configuracao_limpa, tmp_path / nome)
    assert recentes.lista(configuracao_limpa) == [str(tmp_path / n) for n in "cab"]


def test_os_recentes_tem_um_teto(configuracao_limpa, tmp_path):
    for k in range(recentes.MAXIMO + 3):
        recentes.lembrar(configuracao_limpa, tmp_path / str(k))
    assert len(recentes.lista(configuracao_limpa)) == recentes.MAXIMO


def test_o_valor_estragado_nos_recentes_vira_lista_vazia(configuracao_limpa):
    configuracao_limpa.setValue(recentes.CHAVE, "{não é json")
    assert recentes.lista(configuracao_limpa) == []


def test_ca_u4_abrir_lembra_e_reabrir_volta_ao_ultimo(app, tmp_path, configuracao_limpa):
    projeto = ProjetoDeLivro.criar(tmp_path, "Livro", _pagina_sintetica(tmp_path / "p.png"))
    pasta = projeto.pasta
    primeira = JanelaPrincipal()
    primeira.abrir(projeto)
    assert recentes.lista(configuracao_limpa)[0] == str(pasta)
    primeira.close()
    segunda = JanelaPrincipal()
    assert segunda.reabrir_o_ultimo() is True
    assert segunda.projeto is not None and segunda.projeto.pasta == pasta
    segunda.close()


def test_reabrir_sem_a_pasta_nao_faz_nada(app, tmp_path, configuracao_limpa):
    recentes.lembrar(configuracao_limpa, tmp_path / "sumiu")
    j = JanelaPrincipal()
    assert j.reabrir_o_ultimo() is False
    assert j.projeto is None
    j.close()


def test_o_menu_recentes_lista_as_pastas(app, tmp_path, configuracao_limpa):
    recentes.lembrar(configuracao_limpa, tmp_path / "um")
    j = JanelaPrincipal()
    j.encher_os_recentes()
    assert [q.text() for q in j.menu_recentes.actions()] == [str(tmp_path / "um")]
    j.close()


def test_o_menu_sem_recentes_diz_que_nao_ha(app, configuracao_limpa):
    j = JanelaPrincipal()
    j.encher_os_recentes()
    [acao] = j.menu_recentes.actions()
    assert not acao.isEnabled()
    j.close()


def test_a_divisao_da_janela_volta_com_o_projeto(app, tmp_path, configuracao_limpa):
    projeto = ProjetoDeLivro.criar(tmp_path, "Livro", _pagina_sintetica(tmp_path / "p.png"))
    pasta = projeto.pasta
    j = _janela_com(projeto)
    j.resize(1366, 768)
    j.show()
    app.processEvents()
    j.divisor.setSizes([300, 900])
    app.processEvents()
    antes = j.divisor.sizes()
    j.close()
    segunda = JanelaPrincipal()
    segunda.resize(1366, 768)
    segunda.show()
    app.processEvents()
    aberto = ProjetoDeLivro.abrir(pasta)
    segunda.usar(aberto, pg.FonteDePaginas(aberto.fonte),
                 LeitorDoLivro(aberto.pasta_de_padroes, limiares=aberto.dados.limiares))
    app.processEvents()
    assert abs(segunda.divisor.sizes()[0] - antes[0]) <= 8
    segunda.close()


# ------------------------------------------------------------------
# U-5a
# ------------------------------------------------------------------
def test_ca_u5a_o_diagrama_que_falhou_nao_prende_o_f8(tmp_path):
    from dataclasses import replace

    projeto = ProjetoDeLivro.criar(tmp_path / "x", "Duas", _pdf_digital(tmp_path / "d.pdf", 3))
    try:
        for indice, diagrama in ((0, replace(_lido(), erro="sem leitura", casas=[])), (2, _lido())):
            modelo = projeto.pagina_para_editar(indice)
            modelo.tabuleiros = [tuple(diagrama.caixa)]
            modelo.diagramas = [diagrama]
            projeto.salvar_modelo(modelo)
        executor = ExecutorManual()
        ctl = _controlador(projeto, executor)
        executor.tudo()
        abertas = []
        ctl.eventos.ligar("conferir", abertas.append)
        conferencia = ControladorDeDiagramas(ctl)
        conferencia.proximo_do_livro()                    # a 1 só tem o que falhou: passa dela
        executor.tudo()
        assert ctl.indice == 2 and abertas == [0]
    finally:
        projeto.fechar()


def test_o_diagrama_que_falhou_nao_conta_por_conferir(tmp_path):
    from dataclasses import replace

    projeto = ProjetoDeLivro.criar(tmp_path / "x", "Uma", _pagina_sintetica(tmp_path / "p.png"))
    try:
        modelo = projeto.pagina_para_editar(0)
        modelo.tabuleiros = [(1, 1, 50, 50)]
        modelo.diagramas = [replace(_lido(caixa=(1, 1, 50, 50)), erro="sem leitura", casas=[])]
        assert projeto.resumo.do_modelo(modelo)["diagramas_por_conferir"] == 0
    finally:
        projeto.fechar()


# ------------------------------------------------------------------
# U-8
# ------------------------------------------------------------------
def test_ca_u8_a_figurina_na_galeria_troca_a_selecao(app, janela):
    pagina = _escrever(janela, "abc")
    gid = pagina.boxes[0].gid
    janela.vista.setCurrentWidget(janela.galeria)
    janela.galeria.mostrar("Galeria", [Item(0, gid, "a", 0.5)], "pagina")
    janela.galeria.focar()
    janela.galeria.vista.selectAll()
    app.processEvents()
    assert janela.galeria.isAncestorOf(QApplication.focusWidget())
    janela.inserir_figurina("♘")
    app.processEvents()
    assert janela.pagina.modelo.boxes[0].entry.char == "♘"


def test_as_figurinas_e_a_paleta_valem_na_galeria(janela):
    assert janela.galeria in janela.acoes_das_figurinas[0].associatedObjects()
    assert janela.galeria in janela.acao_paleta.associatedObjects()


def test_a_galeria_tem_tecla_propria(janela):
    assert janela.acao_galeria.shortcuts() != []


# ------------------------------------------------------------------
# U-1
# ------------------------------------------------------------------
def test_ca_u1a_alt_3_e_digitar_escreve_no_documento(app, janela):
    _escrever(janela, "abc")
    janela.visor.setFocus()
    app.processEvents()
    janela.focar(3)
    app.processEvents()
    assert QApplication.focusWidget() is janela.texto


def test_ca_u1a_o_clique_nao_tira_o_foco_do_documento(app, janela):
    _escrever(janela, "abc def")
    janela.texto.setFocus()
    app.processEvents()
    assert QApplication.focusWidget() is janela.texto
    posicao = janela.texto.cursorRect().center() + QPoint(4, 2)
    QTest.mouseClick(janela.texto.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, posicao)
    app.processEvents()
    assert QApplication.focusWidget() is janela.texto


def test_ca_u1a_o_fim_de_uma_tarefa_nao_tira_o_foco_do_documento(app, janela):
    _escrever(janela, "abc def")
    janela.texto.setFocus()
    app.processEvents()
    janela._devolver_o_painel()
    app.processEvents()
    assert QApplication.focusWidget() is janela.texto


def test_sem_foco_no_documento_o_glifo_continua_pegando_o_foco(app, janela):
    pagina = _escrever(janela, "abc")
    janela.visor.setFocus()
    janela.inspetor.mostrar("glifo")
    janela.pagina.escolher(pagina.boxes[0].gid)
    app.processEvents()
    assert QApplication.focusWidget() is janela.treino.campo
