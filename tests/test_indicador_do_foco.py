"""CA-U1b (SPEC-pagina-perfeita, U-1; T1, bloco 3): o painel com o foco tem a borda em
`destaque`, o nome dele aparece na barra de status, e a barra diz o que o Enter faz ali:
`Enter ensina`, `Enter confirma`, `Enter confere`.

O foco invisível era a queixa: com seis painéis, não se via onde a próxima tecla cai, e o
mesmo Enter ensina no Glifo, confirma no Documento e confere na fila Lances.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from abbychess.app import estilo  # noqa: E402

from tests.fixturas_espaco import janela  # noqa: E402,F401,F811


def _focar(j, painel: int):
    j.focar(painel)
    QApplication.processEvents()
    return j.indicador_do_foco


def _barra(j) -> str:
    return j.indicador_do_foco.rotulo.text()


def test_cada_painel_com_o_foco_tem_a_borda_e_o_nome_na_barra(janela):  # noqa: F811
    j = janela
    esperados = {1: (j.paginas, "Páginas"), 2: (j.visor, "Imagem"), 3: (j.vista, "Documento"),
                 4: (j.inspetor, "Inspetor"), 5: (j.resultados, "Resultados")}
    for painel, (widget, nome) in esperados.items():
        indicador = _focar(j, painel)
        moldura = indicador.moldura
        assert moldura.parentWidget() is widget, nome
        assert moldura.isVisible() and moldura.geometry() == widget.rect(), nome
        assert moldura.cor() == estilo.tema().destaque, nome
        assert _barra(j).startswith(nome), (nome, _barra(j))


def test_a_vista_diz_a_aba_e_o_enter_dela(janela):  # noqa: F811
    j = janela
    _focar(j, 3)
    assert _barra(j) == "Documento · Enter confirma"
    j.vista.setCurrentWidget(j.galeria)
    j.galeria.focar()
    QApplication.processEvents()
    assert _barra(j) == "Galeria · Enter ensina"


def test_o_inspetor_diz_o_enter_do_editor_e_da_fila(janela):  # noqa: F811
    j = janela
    j.fila.definir("confianca")
    _focar(j, 4)
    assert _barra(j) == "Inspetor · Enter ensina"           # o Glifo
    j.fila.definir("palavras")
    QApplication.processEvents()
    assert _barra(j) == "Inspetor · Enter corrige"           # a Palavra
    j.fila.definir("lances")
    QApplication.processEvents()
    assert _barra(j) == "Inspetor · Enter confere"           # a Palavra, na fila Lances


def test_o_enter_segue_a_tecla_do_perfil(janela, monkeypatch):  # noqa: F811
    from abbychess.app import indicador_do_foco as ind

    j = janela
    j.fila.definir("confianca")
    monkeypatch.setattr(ind.teclado, "tecla", lambda id_, sem="": "F12" if id_ == "ensinar"
                        else "Enter")
    _focar(j, 4)
    j.indicador_do_foco.atualizar()
    assert _barra(j) == "Inspetor · F12 ensina"


def test_sem_painel_com_o_foco_a_borda_some(janela):  # noqa: F811
    j = janela
    indicador = _focar(j, 2)
    assert indicador.moldura.isVisible()
    j.caixa_de_zoom.setFocus()                       # a barra de status não é painel
    QApplication.processEvents()
    assert not indicador.moldura.isVisible() and _barra(j) == ""


def test_a_moldura_acompanha_o_tamanho_do_painel_e_nao_pega_o_mouse(janela):  # noqa: F811
    from PySide6.QtCore import Qt

    j = janela
    indicador = _focar(j, 2)
    j.resize(j.width() - 120, j.height())
    QApplication.processEvents()
    assert indicador.moldura.geometry() == j.visor.rect()
    assert indicador.moldura.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert indicador.moldura.focusPolicy() == Qt.FocusPolicy.NoFocus
