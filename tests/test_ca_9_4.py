"""CA-9.4 (SPEC §9.1): com o servidor de leitura falso, do Ctrl+N ao primeiro Enter na fila,
no máximo 3 gestos além dos diálogos de arquivo, contados por um filtro de eventos.

O caminho é o de um livro escaneado (sem camada nativa): Ctrl+N, Enter no formulário (o
nome, o idioma e o intervalo já vêm preenchidos), e, quando a amostra fica pronta, o Enter
que ensina o primeiro glifo da fila (o foco já está no campo do Glifo). Os diálogos de
arquivo (o livro e a pasta) respondem sozinhos; o filtro conta as teclas soltas.
"""

from __future__ import annotations

import time

import pytest
from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog

from abbychess import nativo
from abbychess.app.janela import JanelaPrincipal

from tests.ajudantes import _esperar  # noqa: E402,F401,F811
from tests.ajudantes import pdf_sintetico  # noqa: E402,F401,F811

pytestmark = pytest.mark.processo


class ContadorDeGestos(QObject):
    """Conta os gestos do teclado: cada tecla apertada e solta conta uma vez, mesmo que o
    evento passe por vários objetos (a propagação ao pai, o atalho)."""

    def __init__(self):
        super().__init__()
        self.gestos, self._apertada = 0, False

    def eventFilter(self, _objeto, evento):
        tipo = evento.type()
        if tipo == QEvent.Type.KeyPress and not evento.isAutoRepeat():
            self._apertada = True
        elif tipo == QEvent.Type.KeyRelease and self._apertada and not evento.isAutoRepeat():
            self._apertada = False
            if evento.key() not in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt):
                self.gestos += 1
        return False


def _ate(app, condicao, limite=60.0):  # noqa: F811
    fim = time.monotonic() + limite
    while not condicao() and time.monotonic() < fim:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    assert condicao(), "a condição não chegou no prazo"


def test_ca_9_4_do_ctrl_n_ao_primeiro_enter_em_3_gestos(app, tmp_path, sem_dialogos,  # noqa: F811
                                                       monkeypatch):
    monkeypatch.setenv("ABBY_SERVIDOR", "1")
    monkeypatch.setenv("ABBY_FABRICA_DE_LEITOR", "tests.leitor_falso:criar")
    pdf = pdf_sintetico(tmp_path)
    pasta = tmp_path / "livros"
    pasta.mkdir()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(pdf), ""))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: str(pasta))
    monkeypatch.setattr(nativo, "oferta", lambda *_a, **_k: nativo.Oferta(0, 0))   # escaneado

    janela = JanelaPrincipal()
    janela.show()
    contador = ContadorDeGestos()
    app.installEventFilter(contador)
    try:
        terminou = []
        janela.eventos.ligar("amostra_terminou", terminou.append)

        def enter_no_formulario():
            formulario = QApplication.activeModalWidget()
            assert formulario is not None, "o formulário do Ctrl+N não abriu"
            QTest.keyClick(formulario, Qt.Key.Key_Return)
        QTimer.singleShot(100, enter_no_formulario)
        assert QTest.qWaitForWindowActive(janela, 5000)    # o atalho só vale na janela ativa
        alvo = QApplication.focusWidget() or janela.visor     # o atalho vale na janela
        QTest.keyClick(alvo, Qt.Key.Key_N, Qt.KeyboardModifier.ControlModifier)
        assert janela.projeto is not None, "o Ctrl+N não criou o projeto"

        _ate(app, lambda: terminou, limite=120)            # os modelos e a amostra no fundo
        _esperar(app, janela)
        p = janela.pagina
        assert p.atual is not None and p.atual in p.fila_da_pagina.fila()  # o primeiro glifo no Glifo
        antes = janela.leitor.arquivos_de_padrao()
        janela.activateWindow()                          # (o offscreen não devolve sozinho)
        assert QTest.qWaitForWindowActive(janela, 5000)
        foco = QApplication.focusWidget()
        assert foco is janela.treino.campo, foco         # o campo do Glifo, já com o foco
        QTest.keyClick(foco, Qt.Key.Key_Return)             # o primeiro Enter ensina
        _esperar(app, janela)
        _ate(app, lambda: janela.leitor.arquivos_de_padrao() == antes + 1)
        assert contador.gestos <= 3, contador.gestos
    finally:
        app.removeEventFilter(contador)
        janela.close()
