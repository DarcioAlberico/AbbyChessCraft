"""A paleta de símbolos: os de avaliação do core, o nome de cada um e o desenho na tela."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication, QToolButton

from core import nags

from abbychess.app import estilo
from abbychess.app.painel_treino import (FONTE_DE_SIMBOLOS, NOMES_DOS_SIMBOLOS, PALETA,
                                         PainelDeTreino, menu_da_paleta)

#: O que a tabela do core tem e a paleta não: o ⯾ não tem fonte (`nags.sem_glifo`), os outros
#: não são avaliação (as marcas de diagrama) ou se digitam (o comentário do Informator).
FORA_DA_PALETA = {"⯾", "⬒", "⬓", "<=", "==", "RR", "!!!", "!??"}


@pytest.fixture(scope="module")
def app():
    aplicativo = QApplication.instance() or QApplication([])
    estilo.registrar_os_simbolos()
    return aplicativo


def test_a_paleta_traz_todos_os_simbolos_do_core():
    do_core = {n.simbolo for n in nags.TABELA if n.simbolo} | {s for s, _ in nags.NAGS}
    assert do_core - set(PALETA) == FORA_DA_PALETA


def test_cada_simbolo_aparece_uma_vez_e_tem_nome():
    assert len(PALETA) == len(set(PALETA))
    assert set(PALETA) == set(NOMES_DOS_SIMBOLOS)
    assert len(set(NOMES_DOS_SIMBOLOS.values())) == len(PALETA)     # o leitor de tela os distingue


def test_o_que_o_core_nao_consegue_desenhar_nao_entra():
    assert not nags.sem_glifo(PALETA)


def test_todo_simbolo_tem_desenho_na_fonte_da_tela(app):
    for corpo, familia in ((14, FONTE_DE_SIMBOLOS), (9, estilo.FONTE_DA_INTERFACE)):
        metrica = QFontMetrics(QFont(familia, corpo))
        sem_desenho = {c for s in PALETA for c in s if not metrica.inFontUcs4(ord(c))}
        assert sem_desenho == set(), familia


@pytest.mark.parametrize("simbolo", ["⯹", "+-", "!!", "⨁"])
def test_o_botao_e_o_menu_inserem_o_simbolo_inteiro(app, simbolo):
    painel = PainelDeTreino()
    painel.habilitar(True)
    botao = next(b for b in painel.findChildren(QToolButton) if b.text() == simbolo)
    botao.click()
    assert painel.campo.text() == simbolo

    inseridos = []
    menu = menu_da_paleta(None, inseridos.append)
    next(a for a in menu.actions() if a.text().startswith(f"{simbolo}   ")).trigger()
    assert inseridos == [simbolo]


def test_a_grade_nao_alarga_o_painel_no_inspetor(app):
    """O Inspetor tem 296 px em 1366 (§3.1): a paleta cresce para baixo, a rolagem é dele."""
    assert PainelDeTreino().minimumSizeHint().width() <= 296 - 20
