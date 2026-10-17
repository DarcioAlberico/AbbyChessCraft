"""A edição no Documento, na janela (SPEC §6.3, §6.4, passo D1).

A página é montada no modelo com o texto que cada teste pede (um box por letra, como em
`tests/test_sessao.py`), e o teste edita pelo teclado do `VistaDoDocumento`: Backspace,
letras, colar, IME, Enter, Shift+Enter, Ctrl+Enter, Esc, Ctrl+Z e Ctrl+Y. CA-6.2, CA-6.3,
CA-6.4 (as linhas D1, cada uma desfeita com um Ctrl+Z), CA-6.7, CA-6.8 e CA-6.9.
"""

from __future__ import annotations

import pytest
from core.box_model import BoxEntry
from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QInputMethodEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from abbychess import diagramas as dg
from abbychess.leitor import FONTE_MANUAL
from abbychess.modelo import Box

from tests.test_documento import app  # noqa: F401 (fixture)


def _escrever(j, *linhas, estados=None):
    """A página aberta com estas linhas, cada letra um box (0,9 de confiança, "net")."""
    p = j.pagina
    pagina = p._pagina_para_editar()
    boxes = []
    for k, linha in enumerate(linhas):
        x, y = 20, 20 + 60 * k
        for palavra in linha.split(" "):
            for letra in palavra:
                boxes.append(Box(pagina.alocar(), BoxEntry(letra, x, y, x + 18, y + 30, 0.9, "net")))
                x += 22
            x += 30
    pagina.boxes = boxes
    pagina.decisoes = type(pagina.decisoes)()
    pagina.tabuleiros, pagina.diagramas = [], []
    pagina.estado = "reconhecida"
    p.ir_para(0)
    j.pintar_texto()
    j.texto.setFocus()
    QApplication.processEvents()
    return pagina


def _por_o_cursor(j, posicao: int, ate: int = None):
    cursor = j.texto.textCursor()
    cursor.setPosition(posicao)
    if ate is not None:
        from PySide6.QtGui import QTextCursor

        cursor.setPosition(ate, QTextCursor.MoveMode.KeepAnchor)
    j.texto.setTextCursor(cursor)


def _tecla(j, tecla, modificadores=Qt.KeyboardModifier.NoModifier):
    QTest.keyClick(j.texto, tecla, modificadores)
    QApplication.processEvents()


def _texto(j) -> str:
    return j.texto.toPlainText()


@pytest.fixture(scope="module")
def _janela_do_modulo(app, tmp_path_factory):  # noqa: F811
    """Uma janela para o módulo (abrir uma por teste custava ~2,5 s da suíte rápida)."""
    from PySide6.QtWidgets import QMessageBox

    from abbychess.projeto import ProjetoDeLivro
    from tests.test_espaco import _abrir
    from tests.test_treino_por_livro import _pagina_sintetica

    remendo = pytest.MonkeyPatch()
    remendo.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    pasta = tmp_path_factory.mktemp("edicao")
    janela = _abrir(ProjetoDeLivro.criar(pasta / "livros", "Edição",
                                         _pagina_sintetica(pasta / "pagina.png")))
    yield janela
    janela.close()
    remendo.undo()


@pytest.fixture
def j(_janela_do_modulo):
    """A janela do módulo com o desfazer, a sessão e o modo do livro de volta ao começo."""
    from abbychess import historico as hs

    janela = _janela_do_modulo
    if janela.texto.tem_sessao:
        janela.texto.restaurar()
    janela.texto._restaurada = None
    janela.pagina.historico = hs.HistoricoDoProjeto()
    janela.projeto.dados.idioma, janela.projeto.dados.notacao = "pt", "figurinas"
    janela.linha.avisar("")
    return janela


def test_digitar_abre_uma_sessao_e_o_modelo_so_muda_ao_confirmar(j):
    pagina = _escrever(j, "vou conc1uir hoje")
    _por_o_cursor(j, 9)                                   # depois do "1"
    _tecla(j, Qt.Key.Key_Backspace)
    QTest.keyClicks(j.texto, "l")
    assert j.texto.tem_sessao and pagina.boxes[7].entry.char == "1"
    _tecla(j, Qt.Key.Key_Return)                          # confirma (CA-6.2)
    assert not j.texto.tem_sessao
    assert pagina.boxes[7].entry.char == "l" and pagina.boxes[7].entry.source == FONTE_MANUAL
    assert not pagina.decisoes.virtuais and _texto(j) == "vou concluir hoje"
    assert pagina.boxes[7].gid not in j.pagina.fila()


def test_ca_6_3_o_espaco_digitado_parte_a_palavra(j):
    pagina = _escrever(j, "ganhartempos")
    _por_o_cursor(j, 6)
    QTest.keyClicks(j.texto, " ")
    _tecla(j, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert _texto(j) == "ganhar tempos" and pagina.decisoes.quebras == {pagina.boxes[6].gid}


def test_ca_6_9_esc_restaura_e_ctrl_y_reaplica(j):
    pagina = _escrever(j, "casa velha")
    _por_o_cursor(j, 4)
    QTest.keyClicks(j.texto, "s")
    assert _texto(j) == "casas velha"
    j.fechar_sobreposicao()                               # Esc
    assert _texto(j) == "casa velha" and not pagina.decisoes.virtuais
    j.refazer()                                           # Ctrl+Y
    assert _texto(j) == "casas velha" and len(pagina.decisoes.virtuais) == 1


def test_ca_6_9_enter_numa_palavra_sem_mudanca_a_tira_da_fila(j):
    pagina = _escrever(j, "casa velha")
    for b in pagina.boxes:
        b.entry.confidence = 0.1                          # todas na fila
    j.pintar_texto()
    _por_o_cursor(j, 2)
    _tecla(j, Qt.Key.Key_Return)
    casa = {b.gid for b in pagina.boxes[:4]}
    assert casa.isdisjoint(j.pagina.fila()) and all(b.revisado for b in pagina.boxes[:4])
    assert {b.entry.source for b in pagina.boxes[:4]} == {"net"}   # a fonte não muda
    assert j.texto.textCursor().position() == 5           # a próxima duvidosa: "velha"


@pytest.mark.parametrize("como", ["teclas", "colar", "ime"])
def test_ca_6_4_cada_linha_d1_se_desfaz_com_um_ctrl_z(j, como):
    casos = [("conc1uir", 4, 5, "l", "concluir"),          # 1 → 1
             ("casxa", 3, 4, "", "casa"),                  # k → 0
             ("csa", 1, 1, "a", "casa"),                    # 0 → k (o virtual)
             ("ganhartempos", 6, 6, " ", "ganhar tempos"),  # o espaço inserido
             ("gan har", 3, 4, "", "ganhar")]               # o espaço apagado
    for original, de, ate, novo, esperado in casos:
        pagina = _escrever(j, original)
        antes = pagina.instantaneo()
        _por_o_cursor(j, de, ate)
        if como == "teclas":
            if de != ate:
                _tecla(j, Qt.Key.Key_Delete)
            if novo:
                QTest.keyClicks(j.texto, novo)
        elif como == "colar":
            if not novo:                                  # cola a letra de antes por cima
                _por_o_cursor(j, de - 1, ate)
                novo = original[de - 1]
            dados = QMimeData()
            dados.setText(novo)
            j.texto.insertFromMimeData(dados)
        elif novo:
            evento = QInputMethodEvent()
            evento.setCommitString(novo)
            j.texto.inputMethodEvent(evento)
        else:                                             # o IME apaga pelo trecho de troca
            _por_o_cursor(j, ate)
            evento = QInputMethodEvent()
            evento.setCommitString("", de - ate, ate - de)
            j.texto.inputMethodEvent(evento)
        _tecla(j, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        assert _texto(j) == esperado, (como, original)
        j.desfazer()                                      # um Ctrl+Z
        j.pintar_texto()                                  # o relógio do texto (150 ms)
        assert [b.entry.as_state() for b in pagina.boxes] == \
            [b.entry.as_state() for b in antes.boxes], (como, original)
        assert pagina.decisoes == antes.decisoes and _texto(j) == original, (como, original)


def test_ca_6_4_colar_varias_linhas(j):
    pagina = _escrever(j, "ganhartempos")
    _por_o_cursor(j, 0, 12)
    dados = QMimeData()
    dados.setText("ganhar\ntempos")
    j.texto.insertFromMimeData(dados)
    _tecla(j, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert _texto(j) == "ganhar tempos" and pagina.decisoes.quebras


def test_o_que_e_do_passo_g_recusa_e_restaura(j):
    pagina = _escrever(j, "rnar")
    _por_o_cursor(j, 0, 2)
    QTest.keyClicks(j.texto, "m")
    _tecla(j, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert _texto(j) == "rnar" and [b.entry.char for b in pagina.boxes] == list("rnar")
    assert "próxima versão" in j.linha.aviso


def test_o_aviso_estrutural_vai_para_a_linha(j):
    _escrever(j, "casxa")
    _por_o_cursor(j, 3, 4)
    _tecla(j, Qt.Key.Key_Delete)
    _tecla(j, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert "1 glifo(s) tirado(s) · Ctrl+Z desfaz" == j.linha.aviso


def test_sair_da_sessao_confirma(j):
    pagina = _escrever(j, "conc1uir hoje")
    _por_o_cursor(j, 4, 5)
    QTest.keyClicks(j.texto, "l")
    _por_o_cursor(j, 12)                                  # o cursor sai da palavra
    QApplication.processEvents()
    assert pagina.boxes[4].entry.char == "l" and not j.texto.tem_sessao


def test_a_montagem_de_fora_espera_a_sessao(j):
    _escrever(j, "casa velha")
    _por_o_cursor(j, 4)
    QTest.keyClicks(j.texto, "s")
    j.pintar_texto()                                      # o relógio do texto, por exemplo
    assert _texto(j) == "casas velha" and j.texto.tem_sessao


def test_ca_6_7_cf3_vira_figurina_no_modo_figurinas(j):
    pagina = _escrever(j, "joga Cf6")
    j.projeto.dados.idioma, j.projeto.dados.notacao = "pt", "figurinas"
    _por_o_cursor(j, 7, 8)
    QTest.keyClicks(j.texto, "3")
    _tecla(j, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert _texto(j) == "joga ♘f3" and pagina.boxes[4].entry.char == "♘"
    pagina = _escrever(j, "joga Cf6")
    j.projeto.dados.notacao = "letras"
    _por_o_cursor(j, 7, 8)
    QTest.keyClicks(j.texto, "3")
    _tecla(j, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert _texto(j) == "joga Cf3"


def test_ctrl_shift_n_insere_a_figurina_e_repetir_alterna_a_cor(j):
    _escrever(j, "joga f3")
    _por_o_cursor(j, 5)
    j.inserir_figurina("♘")
    assert _texto(j) == "joga ♘f3"
    j.inserir_figurina("♘")
    assert _texto(j) == "joga ♞f3"
    j.inserir_figurina("♘")
    assert _texto(j) == "joga ♘f3"


def test_f2_no_documento_insere_o_simbolo_no_cursor(j):
    _escrever(j, "joga f3")
    _por_o_cursor(j, 5)
    j.texto.abrir_paleta()
    acao = next(a for a in j.texto.menu_da_paleta.actions() if a.text().startswith("♗"))
    acao.trigger()
    assert _texto(j) == "joga ♗f3"


def test_ctrl_enter_ensina_o_glifo_sob_o_cursor(j):
    pagina = _escrever(j, "conc1uir")
    _por_o_cursor(j, 4, 5)
    QTest.keyClicks(j.texto, "l")
    j.confirmar_no_documento(ensinar=True)
    QApplication.processEvents()
    assert "l" in j.leitor.padroes_por_caractere()
    assert pagina.boxes[4].entry.char == "l"


def test_ca_6_8_apagar_uma_selecao_que_cruza_um_diagrama_mantem_o_diagrama(j):
    pagina = _escrever(j, "antes do", "depois")
    pagina.tabuleiros = [(100, 80, 300, 120)]             # entre as duas linhas
    pagina.diagramas = dg.para_caixas(pagina.tabuleiros, [])
    j.pintar_texto()
    texto = _texto(j)
    assert "￼" in texto
    _por_o_cursor(j, texto.index("do"), texto.index("depois") + 3)
    _tecla(j, Qt.Key.Key_Delete)
    QApplication.processEvents()
    QApplication.processEvents()
    assert "￼" in _texto(j) and len(pagina.tabuleiros) == 1
    assert "do" not in _texto(j).split()


def test_a_pagina_sem_texto_deixa_o_documento_so_para_leitura(j):
    _escrever(j)
    assert j.texto.isReadOnly()                           # o aviso não se edita
    _escrever(j, "casa")
    assert not j.texto.isReadOnly()


def test_o_modo_das_pecas_fica_nas_opcoes_do_livro(j):
    import json

    from abbychess.app.opcoes import DialogoDeOpcoes

    dialogo = DialogoDeOpcoes(j.projeto.dados.limiares, j, notacao="letras")
    assert dialogo.notacao() == "letras"
    j.pagina.definir_notacao("letras")
    j.pagina._aplicar_limiares(j.projeto.dados.limiares)  # grava o projeto
    bruto = json.loads((j.projeto.pasta / "projeto.json").read_text(encoding="utf-8"))
    assert bruto["notacao"] == "letras"


def test_a_letra_que_faltou_sobre_tinta_sem_box_oferece_o_ctrl_m(j):
    import numpy as np

    pagina = _escrever(j, "csa")
    matriz = np.full((300, 900), 255, np.uint8)
    matriz[20:50, 40:60] = 0                              # tinta logo depois do "c", sem box
    j.pagina.matriz = matriz
    _por_o_cursor(j, 1)
    QTest.keyClicks(j.texto, "a")
    _tecla(j, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert len(pagina.decisoes.virtuais) == 1
    assert "Ctrl+M marca o quadro" in j.linha.aviso



# ----------------------------------------------------------------------
# A revisão de código do D1
# ----------------------------------------------------------------------

def test_apagar_o_segundo_de_dois_iguais_tira_o_segundo_glifo(j):
    pagina = _escrever(j, "cassa ab ab")
    s1, s2 = pagina.boxes[2].gid, pagina.boxes[3].gid
    _por_o_cursor(j, 4)                                   # depois do segundo "s"
    _tecla(j, Qt.Key.Key_Backspace)
    _tecla(j, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert _texto(j) == "casa ab ab" and s1 in pagina.vivos and s2 not in pagina.vivos
    primeiro, segundo = {b.gid for b in pagina.boxes[4:6]}, {b.gid for b in pagina.boxes[6:8]}
    _por_o_cursor(j, 7, 10)                               # " ab", o segundo
    _tecla(j, Qt.Key.Key_Delete)
    _tecla(j, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert _texto(j) == "casa ab" and primeiro <= pagina.vivos and not segundo & pagina.vivos


def test_o_confirmar_agendado_nao_aceita_outra_palavra(j):
    pagina = _escrever(j, "ab de")
    emitidas = []
    j.texto.sessao_confirmada.connect(lambda *a: emitidas.append(a[1]))
    try:
        _por_o_cursor(j, 1)
        QTest.keyClicks(j.texto, "x")                     # "axb de"
        _por_o_cursor(j, 5)                               # sai da sessão (agenda o confirmar)
        _por_o_cursor(j, 6)                               # e anda de novo antes do laço girar
        QApplication.processEvents()
        QApplication.processEvents()
    finally:
        j.texto.sessao_confirmada.disconnect()
        j.texto.sessao_confirmada.connect(j._sessao_do_documento)
    assert emitidas == ["axb"]
    assert not any(b.revisado for b in pagina.boxes if b.entry.char in "de")


def test_enter_numa_palavra_com_um_nao_lido_nao_o_revisa(j):
    pagina = _escrever(j, "casa velha")
    pagina.boxes[1].entry.char = ""                       # □
    j.pintar_texto()
    _por_o_cursor(j, 2)
    _tecla(j, Qt.Key.Key_Return)
    assert not pagina.boxes[1].revisado and pagina.boxes[0].revisado


def test_o_ctrl_y_depois_do_desfazer_do_projeto_refaz_o_projeto(j):
    _escrever(j, "casa velha")
    _por_o_cursor(j, 4)
    QTest.keyClicks(j.texto, "s")
    _tecla(j, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)    # "casas"
    _por_o_cursor(j, 11)
    QTest.keyClicks(j.texto, "x")                         # "velhax", na sessão
    j.fechar_sobreposicao()                               # Esc: "velha" volta
    j.desfazer()                                          # o Ctrl+Z do projeto: "casa"
    j.pintar_texto()
    j.refazer()                                           # refaz o projeto, não o "velhax"
    j.pintar_texto()
    assert _texto(j) == "casas velha"


def test_ctrl_enter_e_um_passo_do_desfazer_e_a_letra_nova_nao_ensina(j):
    pagina = _escrever(j, "conc1uir")
    antes = [b.entry.as_state() for b in pagina.boxes]
    _por_o_cursor(j, 4, 5)
    QTest.keyClicks(j.texto, "l")
    j.confirmar_no_documento(ensinar=True)
    QApplication.processEvents()
    assert pagina.boxes[4].entry.char == "l" and len(j.pagina.historico._desfazer) == 1
    j.desfazer()
    j.pintar_texto()
    assert [b.entry.as_state() for b in pagina.boxes] == antes and _texto(j) == "conc1uir"
    _escrever(j, "csa")
    _por_o_cursor(j, 1)
    QTest.keyClicks(j.texto, "a")
    j.confirmar_no_documento(ensinar=True)
    QApplication.processEvents()
    assert "não ensina" in j.statusBar().currentMessage()


def test_colar_html_entra_como_texto_e_o_tab_e_um_espaco(j):
    pagina = _escrever(j, "ganhartempos")
    _por_o_cursor(j, 0, 12)
    dados = QMimeData()
    dados.setHtml("<b>ganhar</b>\ttempos")
    dados.setText("ganhar\ttempos")
    j.texto.insertFromMimeData(dados)
    _tecla(j, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert _texto(j) == "ganhar tempos" and pagina.decisoes.quebras
    assert not pagina.decisoes.virtuais


def test_o_ime_com_composicao_so_conta_o_que_foi_confirmado(j):
    pagina = _escrever(j, "csa")
    _por_o_cursor(j, 1)
    composicao = QInputMethodEvent("a", [])               # o preedit, ainda sem commit
    j.texto.inputMethodEvent(composicao)
    QApplication.processEvents()
    final = QInputMethodEvent()
    final.setCommitString("a")
    j.texto.inputMethodEvent(final)
    _tecla(j, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert _texto(j) == "casa" and len(pagina.decisoes.virtuais) == 1


def test_desfazer_a_edicao_tira_o_revisado(j):
    pagina = _escrever(j, "conc1uir")
    _por_o_cursor(j, 4, 5)
    QTest.keyClicks(j.texto, "l")
    _tecla(j, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert all(b.revisado for b in pagina.boxes)
    j.desfazer()
    assert not any(b.revisado for b in pagina.boxes)
