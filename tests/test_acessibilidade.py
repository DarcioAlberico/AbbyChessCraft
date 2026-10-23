"""A acessibilidade da janela (§13, passo K): CA-13.1 (todo botão sem texto legível tem
`accessibleName` e dica) e os estados vazios com instrução."""

from __future__ import annotations

import os
import unicodedata

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QAbstractButton, QApplication  # noqa: E402

from abbychess.app.janela import JanelaPrincipal  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app):
    j = JanelaPrincipal()
    yield j
    j.close()


def sem_texto_legivel(texto: str) -> bool:
    """O texto do botão não diz o que ele faz a quem não vê: vazio, ou só símbolos ("◀",
    "▶", "♘", "⚠", "▾")."""
    limpo = texto.replace("&", "").strip()
    return not any(unicodedata.category(c).startswith(("L", "N")) for c in limpo) \
        or len(limpo) == 1


def botoes_sem_nome(raiz) -> list:
    faltam = []
    for botao in raiz.findChildren(QAbstractButton):
        if not sem_texto_legivel(botao.text()):
            continue
        nome = botao.accessibleName() or (botao.defaultAction().text()
                                           if hasattr(botao, "defaultAction")
                                           and botao.defaultAction() else "")
        dica = botao.toolTip() or (botao.defaultAction().toolTip()
                                   if hasattr(botao, "defaultAction") and botao.defaultAction()
                                   else "")
        if not nome.strip() or not dica.strip():
            dono = botao.parent().__class__.__name__ if botao.parent() else "?"
            faltam.append((dono, botao.objectName() or repr(botao.text())))
    return faltam


def test_a_regra_reconhece_botao_sem_texto():
    assert sem_texto_legivel("") and sem_texto_legivel("◀") and sem_texto_legivel("♘")
    assert sem_texto_legivel("&X")                     # uma letra só não diz nada
    assert not sem_texto_legivel("Ensinar (Enter)")


def test_ca_13_1_todo_botao_sem_texto_tem_nome_e_dica(janela):
    assert botoes_sem_nome(janela) == []


def test_ca_13_1_dialogos_tambem(app, tmp_path):
    from abbychess import exportar as ex
    from abbychess.app.dialogo_exportacao import DialogoDeExportacao, JanelaDaPrevia
    from abbychess.app.opcoes import DialogoDeOpcoes
    from abbychess.projeto import Limiares

    for dialogo in (DialogoDeExportacao(None, "epub", ex.Opcoes(), {}, tmp_path, "T"),
                    JanelaDaPrevia(), DialogoDeOpcoes(Limiares())):
        assert botoes_sem_nome(dialogo) == [], type(dialogo).__name__


# ----------------------------------------------------------------------
# Os estados vazios (§13)
# ----------------------------------------------------------------------

def test_sem_livro_a_imagem_e_o_glifo_dizem_o_que_fazer(app, janela):
    from abbychess.app import vazios

    assert janela.visor.mensagem_vazia == vazios.sem_projeto()
    assert janela.treino.leitura.text() == vazios.sem_projeto()
    assert "Ctrl+N" in vazios.sem_projeto() and "Ctrl+O" in vazios.sem_projeto()
    from abbychess.app.visor import VisorDePagina

    visor = VisorDePagina()
    visor.resize(400, 300)
    visor.definir_vazio(vazios.sem_projeto())
    visor.show()
    app.processEvents()
    imagem = visor.viewport().grab().toImage()
    visor.close()
    fundo = imagem.pixelColor(2, 2)
    assert any(imagem.pixelColor(x, y) != fundo for x in range(0, imagem.width(), 2)
               for y in range(0, imagem.height(), 2))                # o texto apareceu


def test_abrir_uma_pagina_tira_o_estado_vazio_da_imagem(app):
    """Com página, o `drawForeground` sai logo (sem varrer a cena a cada pintura)."""
    from PySide6.QtGui import QPixmap

    from abbychess.app import vazios
    from abbychess.app.visor import VisorDePagina

    visor = VisorDePagina()
    visor.definir_vazio(vazios.sem_projeto())
    pixmap = QPixmap(50, 50)
    pixmap.fill()
    visor.mostrar_pagina(pixmap)
    assert visor.mensagem_vazia == ""


def test_pagina_nao_reconhecida_no_documento_tem_as_duas_teclas(app):
    from abbychess.app import vazios
    from abbychess.app.documento import VistaDoDocumento

    vista = VistaDoDocumento()
    vista.montar(None)
    assert vista.toPlainText() == vazios.pagina_nao_reconhecida()
    assert "F5" in vista.toPlainText() and "Ctrl+M" in vista.toPlainText()


def test_os_vazios_dizem_as_teclas_do_perfil():
    from abbychess.app import teclado, vazios

    try:
        teclado.definir("finereader")
        assert "Ctrl+F9 reconhece" in vazios.pagina_nao_reconhecida()
        teclado.definir("finereader", {"reconhecer_pagina": []})
        assert "Página › Reconhecer reconhece" in vazios.pagina_nao_reconhecida()
    finally:
        teclado.definir("padrao")
    assert "F5 reconhece" in vazios.pagina_nao_reconhecida()


def test_padroes_vazios_explicam_como_ensinar(app):
    from abbychess.app import vazios
    from abbychess.app.painel_padroes import PainelDePadroes

    painel = PainelDePadroes()
    painel.atualizar({})
    assert painel.resumo.text() == vazios.SEM_PADROES