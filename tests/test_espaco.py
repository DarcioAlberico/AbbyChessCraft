"""O espaço de trabalho do passo A2 (SPEC §3.1, §3.2, §3.4, §8.1).

CA-3.1 (reabrir restaura o espaço), CA-3.2 (1366×768 e 1280×720, sem a cláusula do
tabuleiro; a da x-height está em `tests/livro_real`), CA-3.3 (os arranjos e o Alt+N, no
perfil padrão), CA-3.7 (a parte da janela: os atalhos registrados são os do YAML até o A2;
atalho citado no README ou na SPEC existe no YAML), CA-4.2 (a falha de gravação em Avisos;
o espaço gravado de forma atômica) e CA-8.2 (o Alt+↓ em cada painel; F7).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QAction, QContextMenuEvent, QShortcut  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from abbychess import atalhos  # noqa: E402
from abbychess import avisos as av  # noqa: E402
from abbychess import modelo as md  # noqa: E402
from abbychess import pagina as pg  # noqa: E402
from abbychess.app import espaco, teclado  # noqa: E402
from abbychess.app.janela import JanelaPrincipal  # noqa: E402
from abbychess.leitor import LeitorDoLivro  # noqa: E402
from abbychess.projeto import ProjetoDeLivro  # noqa: E402

from tests.janela_util import atual, boxes, fila  # noqa: E402
from tests.test_janela import _esperar  # noqa: E402
from tests.test_treino_por_livro import _pagina_sintetica  # noqa: E402
from tests.test_visor import pdf_de_60_paginas  # noqa: E402,F401

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _abrir(projeto, largura=1366, altura=768):
    j = JanelaPrincipal()
    j.resize(largura, altura)
    j.show()
    j.activateWindow()
    QApplication.processEvents()
    j.usar(projeto, pg.FonteDePaginas(projeto.fonte),
           LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    QApplication.processEvents()
    return j


@pytest.fixture
def sim(monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)


@pytest.fixture
def janela(app, tmp_path, sim):
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Teste",
                                   _pagina_sintetica(tmp_path / "pagina.png"))
    j = _abrir(projeto)
    yield j
    j.close()


@pytest.fixture
def lida(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    return janela


@pytest.fixture
def janela_de_60(app, tmp_path, pdf_de_60_paginas, sim):  # noqa: F811
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Sessenta", pdf_de_60_paginas)
    j = _abrir(projeto, 1920, 1080)
    yield j
    j.close()


# ----------------------------------------------------------------------
# CA-3.7, a parte da janela
# ----------------------------------------------------------------------

def _registrados(janela):
    reg = {}
    for q in janela.findChildren(QAction):
        if q.shortcuts():
            reg.setdefault(q.objectName(), set()).update(teclado.do_qt(s) for s in q.shortcuts())
    return reg


def test_os_atalhos_registrados_sao_exatamente_os_do_yaml_ate_o_passo(janela):
    esperado = {a.id: set(seqs) for a, seqs in teclado.tabela().ativas(teclado.PERFIL,
                                                                       teclado.PASSO)}
    assert _registrados(janela) == esperado
    assert janela.findChildren(QShortcut) == []           # nada fora do YAML


#: O que o README e a SPEC escrevem com cara de atalho e não é uma tecla: gestos e famílias.
_NAO_SAO_TECLAS = {"clique", "roda", "seta", "arraste", "arrastar", "N", "K/Q/R/B/N/P", "1…Ctrl+5",
                   "Shift+seta", "letra"}
_CITACAO = re.compile(r"(?<![\w+])((?:Ctrl|Alt|Shift)(?:\+(?:Ctrl|Alt|Shift))*\+[^\s,;:.)\]*`/|]+"
                      r"|F(?:[1-9]|1[0-2])\b)")


def _citados(texto):
    for bruto in _CITACAO.findall(texto):
        tecla = bruto.split("+")[-1] if not bruto.endswith("++") else "+"
        if tecla in _NAO_SAO_TECLAS or bruto.rstrip("+").split("+")[-1] in _NAO_SAO_TECLAS:
            continue
        try:
            yield atalhos.normalizar(bruto)
        except ValueError:
            continue                                     # "Ctrl+clique", "Alt+seta"…


def test_atalho_citado_no_readme_ou_na_spec_existe_no_yaml():
    tabela = teclado.tabela()
    conhecidos = {s for a in tabela.acoes for seqs in a.sequencias.values() for s in seqs}
    # As teclas que só são ligações nativas, citadas como tais (o widget as tem).
    conhecidos |= {s for n in tabela.nativos.values() for lista in n.values() for s in lista}
    # As do Qt e do Windows: o Tab anda pelo foco (§3.4, regra 2); Shift+F10 e Menu abrem o
    # menu de contexto (§3.2).
    conhecidos |= {"Tab", "Shift+Tab", "Shift+F10", "Menu"}
    faltam = {}
    for nome in ("README.md", "docs/SPEC.md"):
        texto = (RAIZ / nome).read_text(encoding="utf-8")
        for seq in _citados(texto):
            if seq not in conhecidos:
                faltam.setdefault(nome, set()).add(seq)
    assert faltam == {}


# ----------------------------------------------------------------------
# CA-3.3: os arranjos e o foco (perfil padrão)
# ----------------------------------------------------------------------

@pytest.mark.parametrize("acao, visor, vista, orientacao", [
    ("acao_so_imagem", True, False, Qt.Orientation.Horizontal),
    ("acao_lado_a_lado", True, True, Qt.Orientation.Horizontal),
    ("acao_empilhado", True, True, Qt.Orientation.Vertical),
    ("acao_so_vista", False, True, Qt.Orientation.Horizontal),
])
def test_cada_arranjo_mostra_os_paineis_da_tabela(janela, acao, visor, vista, orientacao):
    getattr(janela, acao).trigger()
    assert janela.visor.isVisible() is visor and janela.vista.isVisible() is vista
    assert janela.divisor.orientation() == orientacao
    assert janela.doca_inspetor.isVisible()                # o Inspetor fica


def _dentro(painel):
    foco = QApplication.focusWidget()
    return foco is not None and (foco is painel or painel.isAncestorOf(foco))


def test_alt_n_poe_o_foco_no_painel_certo(app, lida):
    j = lida
    paineis = {1: j.paginas, 2: j.visor, 3: j.vista, 4: j.inspetor, 5: j.resultados}
    for n, painel in paineis.items():
        QTest.keyClick(QApplication.focusWidget() or j, getattr(Qt.Key, f"Key_{n}"),
                       Qt.KeyboardModifier.AltModifier)
        app.processEvents()
        assert _dentro(painel), (n, QApplication.focusWidget())
    assert j.doca_paginas.isVisible() and j.doca_resultados.isVisible()   # abrem


def test_alt_3_de_novo_cicla_as_abas_da_vista(app, janela):
    janela.focar(3)
    assert janela.vista.currentWidget() is janela.texto
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_3, Qt.KeyboardModifier.AltModifier)
    assert janela.vista.currentWidget() is janela.padroes and _dentro(janela.vista)


# ----------------------------------------------------------------------
# CA-3.2: os tamanhos
# ----------------------------------------------------------------------

def test_tamanhos_padrao_cabem_em_1366(janela):
    paginas, imagem, vista, inspetor = espaco.TAMANHOS[1366]
    assert paginas + imagem + vista + inspetor + 3 * 4 <= 1366    # com as alças
    assert janela.minimumSizeHint().width() <= 1366
    assert janela.arranjo == "lado_a_lado" and not janela.doca_paginas.isVisible()


def test_em_1280_o_padrao_e_o_empilhado(app, tmp_path, sim):
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Estreito",
                                   _pagina_sintetica(tmp_path / "pagina.png"))
    j = _abrir(projeto, 1280, 720)
    try:
        assert j.arranjo == "empilhado"
        assert j.divisor.orientation() == Qt.Orientation.Vertical
        assert j.minimumSizeHint().width() <= 1280
    finally:
        j.close()


def test_projeto_novo_em_janela_larga_abre_a_gaveta(janela_de_60):
    j = janela_de_60
    assert j.doca_paginas.isVisible()
    assert j.paginas.lista.topLevelItemCount() == 60
    assert j.paginas.lista.topLevelItem(0).text(1) == "não reconhecida"


# ----------------------------------------------------------------------
# A gaveta de Páginas
# ----------------------------------------------------------------------

def test_enter_na_gaveta_abre_a_pagina_e_o_filtro_mostra_um_estado(app, janela_de_60):
    j = janela_de_60
    j.focar(1)
    lista = j.paginas.lista
    lista.setCurrentItem(lista.topLevelItem(7))
    QTest.keyClick(lista, Qt.Key.Key_Return)
    assert j.pagina.indice == 7
    j.paginas.filtro.setCurrentIndex(j.paginas.filtro.findData(md.VERIFICADA))
    assert all(lista.topLevelItem(n).isHidden() for n in range(lista.topLevelItemCount()))


def test_reconhecer_as_selecionadas_pede_o_lote_delas(janela_de_60, monkeypatch):
    j = janela_de_60
    pedidos = []
    monkeypatch.setattr(j.livro, "reconhecer", lambda indices, refazer: pedidos.append(indices))
    lista = j.paginas.lista
    lista.clearSelection()                                 # a página aberta vem escolhida
    for n in (3, 4, 9):
        lista.topLevelItem(n).setSelected(True)
    menu = j.paginas.menu_de_contexto()
    next(a for a in menu.actions() if a.text().startswith("Reconhecer")).trigger()
    assert pedidos == [[3, 4, 9]]


# ----------------------------------------------------------------------
# CA-8.2: a fila (Alt+↓ / Alt+↑, F7)
# ----------------------------------------------------------------------

def test_alt_baixo_anda_na_fila_com_o_foco_em_cada_painel_sem_mudar_texto(app, lida):
    j = lida
    j.doca_paginas.show()
    j.doca_resultados.show()
    leituras = [(b.char, b.source) for b in boxes(j)]
    texto_do_campo = None
    for widget in (j.paginas.lista, j.visor, j.texto, j.treino.campo, j.resultados.avisos):
        antes = atual(j)
        widget.setFocus()
        app.processEvents()
        texto_do_campo = j.treino.campo.text()
        QTest.keyClick(widget, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
        app.processEvents()
        assert atual(j) != antes, widget
        assert [(b.char, b.source) for b in boxes(j)] == leituras     # nunca muda texto
    assert texto_do_campo is not None
    QTest.keyClick(j.visor, Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier)
    assert [(b.char, b.source) for b in boxes(j)] == leituras


def test_f7_cicla_o_modo_e_o_editor_do_inspetor(app, lida, monkeypatch):
    j = lida
    monkeypatch.setattr(j.verificador, "verificar", lambda: False)    # sem carregar o léxico
    assert j.fila.modo == "confianca" and j.inspetor.atual() == "glifo"
    QTest.keyClick(j.visor, Qt.Key.Key_F7)
    assert j.fila.modo == "leitura" and j.pagina.ordem_da_fila == "leitura"
    assert fila(j) == sorted(fila(j), key=j.pagina.gids.index)       # na ordem da página
    QTest.keyClick(j.visor, Qt.Key.Key_F7)
    assert j.fila.modo == "palavras" and j.inspetor.atual() == "palavra"
    assert "Palavras" in j.inspetor.seletor.text()
    QTest.keyClick(j.visor, Qt.Key.Key_F7)
    QTest.keyClick(j.visor, Qt.Key.Key_F7)
    assert j.fila.modo == "confianca" and j.inspetor.atual() == "glifo"


def test_na_ordem_de_leitura_alt_baixo_vai_ao_pendente_seguinte_da_pagina(lida):
    j = lida
    j.fila.definir("leitura")
    pendentes = fila(j)
    j.pagina.escolher(pendentes[0])
    j.fila.andar(+1)
    assert j.pagina.atual == pendentes[1]
    j.fila.andar(-1)
    assert j.pagina.atual == pendentes[0]


# ----------------------------------------------------------------------
# Ctrl+T: a página verificada (§4.4)
# ----------------------------------------------------------------------

def test_ctrl_t_verifica_a_pagina_e_editar_a_devolve_a_revisao(app, lida):
    j = lida
    QTest.keyClick(j.visor, Qt.Key.Key_T, Qt.KeyboardModifier.ControlModifier)
    assert j.pagina.modelo.estado == md.VERIFICADA
    assert "verificada" in j.rotulo_da_pagina.text()
    j.pagina.desfazer()
    assert j.pagina.modelo.estado != md.VERIFICADA
    j.pagina.refazer()
    assert j.pagina.modelo.estado == md.VERIFICADA
    j.treino.campo.setText("x")
    j.treino.pedir_so_corrigir()
    _esperar(app, j)
    assert j.pagina.modelo.estado == md.EM_REVISAO


def test_ctrl_t_numa_pagina_nao_reconhecida_avisa(janela):
    janela.acao_verificada.setEnabled(True)
    janela.acao_verificada.trigger()
    assert janela.pagina.modelo is None or janela.pagina.modelo.estado == md.NAO_RECONHECIDA
    assert "Reconheça" in janela.statusBar().currentMessage()


# ----------------------------------------------------------------------
# O campo do caractere: a exceção 6 de §3.4
# ----------------------------------------------------------------------

def test_no_campo_delete_descarta_e_shift_seta_move_a_borda(app, lida):
    j = lida
    campo = j.treino.campo
    alvo = atual(j)
    caixa = next(b for b in boxes(j) if b.gid == alvo) if hasattr(boxes(j)[0], "gid") else None
    antes = len(boxes(j))
    campo.setFocus()
    x2 = j.pagina.box_atual().x2
    QTest.keyClick(campo, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    _esperar(app, j)
    assert j.pagina.box_atual().x2 == x2 + 1                    # Shift+→: a borda direita
    QTest.keyClick(campo, Qt.Key.Key_Delete)
    _esperar(app, j)
    assert len(boxes(j)) == antes - 1                            # Del: não é caractere
    assert caixa is None or caixa not in boxes(j)


def test_f2_abre_a_paleta_e_o_simbolo_entra_no_campo(app, lida):
    j = lida
    j.treino.campo.setText("")
    j.treino.campo.setFocus()
    QTest.keyClick(j.treino.campo, Qt.Key.Key_F2)
    menu = j.treino.menu_da_paleta
    next(a for a in menu.actions() if a.text().startswith("♘")).trigger()
    menu.close()
    assert j.treino.campo.text() == "♘"


# ----------------------------------------------------------------------
# Esc, os menus de contexto, os avisos
# ----------------------------------------------------------------------

def test_esc_fecha_resultados_e_depois_esvazia_a_selecao(app, lida):
    j = lida
    j.doca_resultados.show()
    j.pagina.selecao = {fila(j)[0], fila(j)[1]}
    QTest.keyClick(j.visor, Qt.Key.Key_Escape)
    assert not j.doca_resultados.isVisible() and j.pagina.selecao
    QTest.keyClick(j.visor, Qt.Key.Key_Escape)
    assert not j.pagina.selecao


def _menu_pelo_teclado(app, widget):
    """Um `QContextMenuEvent` de teclado (o que o Windows manda no Shift+F10 e na tecla
    Menu) no widget: devolve o menu que abriu, fechando-o."""
    abertos = []

    def fechar():
        menu = QApplication.activePopupWidget()
        abertos.append(menu)
        if menu is not None:
            menu.close()
    QTimer.singleShot(50, fechar)
    QApplication.sendEvent(widget, QContextMenuEvent(QContextMenuEvent.Reason.Keyboard,
                                                     QPoint(5, 5), widget.mapToGlobal(QPoint(5, 5))))
    fim = QTimer()
    fim.setSingleShot(True)
    fim.start(500)
    while fim.isActive() and not abertos:
        app.processEvents()
    return abertos[0] if abertos else None


def test_shift_f10_e_a_tecla_menu_abrem_o_menu_de_contexto_em_todo_painel(app, lida):
    j = lida
    j.doca_paginas.show()
    j.doca_resultados.show()
    app.processEvents()
    for widget in (j.paginas.lista, j.visor, j.texto, j.treino.campo, j.resultados.avisos):
        alvo = widget.viewport() if hasattr(widget, "viewport") and widget is not j.visor else widget
        assert _menu_pelo_teclado(app, alvo) is not None, widget


def test_a_falha_de_gravacao_aparece_em_avisos_e_fica_no_projeto(app, janela):
    janela.falha_de_gravacao.emit(0, OSError("disco cheio"))
    app.processEvents()
    assert janela.botao_avisos.text() == "⚠1"
    assert "disco cheio" in janela.resultados.avisos.item(0).text()
    janela.botao_avisos.click()
    assert janela.doca_resultados.isVisible() and janela.botao_avisos.text() == "⚠"
    registro = av.RegistroDeAvisos()
    registro.abrir(janela.projeto.pasta)
    assert registro.itens[-1].tipo == av.ERRO and "disco cheio" in registro.itens[-1].texto


def test_o_espaco_gravado_e_atomico(app, janela, monkeypatch):
    from abbychess import gravacao as gv

    janela.gravar_espaco()
    caminho = Path(janela.projeto.pasta) / espaco.ARQUIVO_DO_ESPACO
    antes = caminho.read_bytes()
    janela.arranjar("empilhado")

    def falhar(*_a):
        raise PermissionError("bloqueado")
    monkeypatch.setattr(gv, "_trocar", falhar)
    janela.gravar_espaco()
    assert caminho.read_bytes() == antes                      # o antigo, inteiro
    assert any("não foi gravado" in a.texto for a in janela.avisos.itens)


# ----------------------------------------------------------------------
# CA-3.1: reabrir o projeto restaura o espaço
# ----------------------------------------------------------------------

def test_reabrir_o_projeto_restaura_o_espaco(app, tmp_path, pdf_de_60_paginas, sim):  # noqa: F811
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Volta", pdf_de_60_paginas)
    j = _abrir(projeto, 1600, 1000)
    j.ir_para_pagina(12)
    j.arranjar("empilhado")
    j.divisor.setSizes([500, 300])
    j.doca_paginas.show()
    j.doca_resultados.show()
    j.visor.definir_zoom(2.0)
    j.vista.setCurrentWidget(j.padroes)
    j.focar(3)
    app.processEvents()
    tamanhos = j.divisor.sizes()
    j.close()

    outro = ProjetoDeLivro.abrir(projeto.pasta)
    k = _abrir(outro, 1600, 1000)
    try:
        app.processEvents()
        assert k.pagina.indice == 12
        assert k.arranjo == "empilhado"
        assert all(abs(a - b) <= 2 for a, b in zip(k.divisor.sizes(), tamanhos))
        assert k.doca_paginas.isVisible() and k.doca_resultados.isVisible()
        assert abs(k.visor.escala() - 2.0) < 1e-6
        assert k.vista.currentWidget() is k.padroes
        assert _dentro(k.vista)
    finally:
        k.close()


# ----------------------------------------------------------------------
# CA-3.2, a x-height no livro de referência
# ----------------------------------------------------------------------

def _x_height_do_gabarito(matriz, verdade) -> float:
    """A x-height mediana das linhas do corpo do gabarito, em pixels da página: em cada
    linha, a faixa de linhas de pixels com mais da metade da tinta da mais cheia."""
    import statistics

    h, w = matriz.shape
    alturas = []
    for linha in verdade["linhas_corpo"]:
        x1, y1, x2, y2 = linha["caixa_rel"]
        perfil = (matriz[int(y1 * h):int(y2 * h), int(x1 * w):int(x2 * w)] < 128).sum(axis=1)
        if perfil.max():
            alturas.append(int((perfil > perfil.max() / 2).sum()))
    return statistics.median(alturas)


@pytest.mark.livro_real
@pytest.mark.parametrize("largura, altura, arranjo", [(1366, 768, "lado_a_lado"),
                                                      (1280, 720, "empilhado")])
def test_x_height_na_imagem_no_zoom_largura(app, tmp_path, sim, largura, altura, arranjo):
    import json

    import numpy as np

    from tests.livros import PASTA_DOS_PDFS

    verdade = json.loads((RAIZ / "tests" / "verdade" / "xv" / "i025.json").read_text(encoding="utf-8"))
    pdf = next(PASTA_DOS_PDFS.rglob(verdade["pdf"]), None)
    if pdf is None:
        pytest.skip("o PDF do livro de referência não está na pasta dos PDFs")
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Xadrez Vitorioso", pdf)
    j = _abrir(projeto, largura, altura)
    try:
        assert j.arranjo == arranjo
        j.ir_para_pagina(verdade["indice_pdf"])
        j.visor.zoom_largura()
        app.processEvents()
        x_height = _x_height_do_gabarito(np.array(j.pagina.imagem.convert("L")), verdade)
        assert x_height * j.visor.escala() >= 6, (x_height, j.visor.escala())
    finally:
        j.close()
