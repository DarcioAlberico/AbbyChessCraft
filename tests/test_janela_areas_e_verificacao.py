"""O editor de áreas e a verificação de texto na janela, sem tela.

Mesma janela de `test_janela`: leitor sem a rede global, página sintética
"abc abc abc" / "cab bca", e as tarefas em segundo plano de verdade.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF

from core import lexico

from abbychess import zonas as zn
from abbychess.leitor import FONTE_MANUAL

from tests.test_janela import _esperar, app, janela  # noqa: F401  (fixtures)


def _ler_a_mao(app, janela):  # noqa: F811
    """Reconhece e dá aos glifos a leitura certa, como se a rede tivesse lido."""
    letras = list("abcabcabc" + "cabbca")
    janela.reconhecer()
    _esperar(app, janela)
    assert len(janela.boxes) == len(letras)
    for b, c in zip(janela.boxes, letras):
        b.char, b.source, b.confidence = c, "neural", 0.99
    janela._atualizar_tudo()


# ----------------------------------------------------------------------
# Editor de áreas
# ----------------------------------------------------------------------

def test_ferramentas_tem_o_editor_de_areas_e_a_verificacao(janela):  # noqa: F811
    textos = [a.text() for a in janela.menu_ferramentas.actions()]
    assert any("Editor de áreas" in t for t in textos)
    assert any("Verificação de texto" in t for t in textos)
    assert janela.acao_verificar.shortcut().toString() == "F7"


def test_editor_de_areas_e_modo_de_treino_se_excluem(janela):  # noqa: F811
    janela.acao_modo_treino.setChecked(True)
    janela._modo_treino(True)
    janela.acao_areas.setChecked(True)
    janela._modo_areas(True)
    assert janela.visor.modo_areas and not janela.visor.modo_treino
    assert not janela.acao_modo_treino.isChecked()

    janela.acao_modo_treino.setChecked(True)
    janela._modo_treino(True)
    assert janela.visor.modo_treino and not janela.visor.modo_areas
    assert not janela.acao_areas.isChecked()


def test_ligar_o_editor_numa_pagina_nova_acha_as_areas(app, janela):  # noqa: F811
    janela.acao_areas.setChecked(True)
    janela._modo_areas(True)
    _esperar(app, janela)
    assert janela.zonas and all(z.tipo == zn.TEXTO for z in janela.zonas)
    assert janela.projeto.carregar_zonas(0) == janela.zonas
    assert janela.boxes == []  # achar as áreas não reconhece a página


def test_desenhar_tipar_e_reconhecer_pelas_areas(app, janela):  # noqa: F811
    janela.acao_areas.setChecked(True)
    janela._modo_areas(True)
    _esperar(app, janela)
    largura, altura = janela.imagem.size
    # Arraste no visor fora de qualquer área: uma área nova na metade de baixo.
    janela.zonas = []
    janela._gravar_zonas()
    visor = janela.visor
    visor.apertar_no_editor_de_areas(QPointF(0, 0))
    visor.soltar_area(QPointF(0, 0), QPointF(largura - 1, altura - 1))
    assert len(janela.zonas) == 1 and janela.zonas[0].tipo == zn.TEXTO
    visor.apertar_no_editor_de_areas(QPointF(5, altura // 2 + 5))  # fora: nada escolhido
    visor.soltar_area(QPointF(5, 125), QPointF(largura - 5, altura - 5))
    assert len(janela.zonas) == 2 and janela.zona_atual == 1
    janela._zona_tipo(1, zn.IGNORAR)  # a tecla 4

    janela.reconhecer()
    _esperar(app, janela)
    assert len(janela.boxes) == 9  # só a primeira linha; a segunda está em "ignorar"
    assert janela.projeto.carregar_zonas(0)[1].tipo == zn.IGNORAR

    janela._zona_apagada(1)
    janela.reconhecer()
    _esperar(app, janela)
    assert len(janela.boxes) == 15


def test_arrastar_a_area_move_e_grava(app, janela):  # noqa: F811
    janela.acao_areas.setChecked(True)
    janela._modo_areas(True)
    _esperar(app, janela)
    antes = janela.zonas[0]
    janela.visor.apertar_no_editor_de_areas(QPointF((antes.x1 + antes.x2) / 2,
                                                    (antes.y1 + antes.y2) / 2))
    assert janela.zona_atual == 0
    janela.visor.soltar_arraste(QPointF((antes.x1 + antes.x2) / 2 + 10,
                                        (antes.y1 + antes.y2) / 2 + 5))
    depois = janela.projeto.carregar_zonas(0)[0]
    assert (depois.x1, depois.y1) == (antes.x1 + 10, antes.y1 + 5)


# ----------------------------------------------------------------------
# Verificação de texto
# ----------------------------------------------------------------------

def test_verificar_anda_pelas_desconhecidas_e_corrige(app, janela):  # noqa: F811
    _ler_a_mao(app, janela)
    janela.lexico = lexico.Lexico(palavras={"abc", "cab"})
    janela.verificar_texto()
    assert janela.abas.currentWidget() is janela.verificacao
    assert [d.palavra for d in janela.desconhecidas] == ["bca"]
    assert janela.verificacao.campo.text() == "bca"
    assert not janela.verificacao.recorte.pixmap().isNull()

    janela.verificacao.campo.setText("abc")
    janela.verificacao._corrigir()
    assert janela.desconhecidas == []
    assert "Nenhuma" in janela.verificacao.posicao.text()
    assert [b.char for b in janela.boxes[-3:]] == ["a", "b", "c"]
    assert janela.boxes[-3].source == FONTE_MANUAL
    assert janela.projeto.carregar_pagina(0)[-3].char == "a"


def test_corrigir_e_ensinar_grava_o_padrao(app, janela):  # noqa: F811
    _ler_a_mao(app, janela)
    janela.lexico = lexico.Lexico(palavras={"abc", "cab"})
    janela.verificar_texto()
    janela.verificacao.campo.setText("aca")
    janela.verificacao._ensinar()
    _esperar(app, janela)
    assert "a" in janela.leitor.padroes_por_caractere()


def test_letras_de_mais_nao_mexem_na_pagina(app, janela):  # noqa: F811
    _ler_a_mao(app, janela)
    janela.lexico = lexico.Lexico(palavras={"abc", "cab"})
    janela.verificar_texto()
    janela._corrigir_palavra("bcaa")
    assert "Divida ou junte" in janela.statusBar().currentMessage()
    assert [b.char for b in janela.boxes[-3:]] == ["b", "c", "a"]


def test_adicionar_e_ignorar_todas(app, janela):  # noqa: F811
    _ler_a_mao(app, janela)
    janela.lexico = lexico.Lexico(palavras={"abc", "cab"})
    janela.verificar_texto()
    janela._ignorar_todas()
    assert janela.desconhecidas == []
    janela.ignoradas = set()
    janela._recontar_desconhecidas(0)
    janela._adicionar_ao_lexico()
    assert janela.desconhecidas == []
    assert janela.projeto.arquivo_do_lexico.read_text(encoding="utf-8") == "bca\n"


def test_clique_no_glifo_abre_o_treino(app, janela):  # noqa: F811
    _ler_a_mao(app, janela)
    janela.lexico = lexico.Lexico(palavras={"abc", "cab"})
    janela.verificar_texto()
    palavra = janela.desconhecidas[0]
    _, x1, x2 = janela.verificacao._glifos[1]
    assert janela.verificacao.glifo_em((x1 + x2) / 2) == palavra.indices[1]
    janela.verificacao._clicar((x1 + x2) / 2, 0)
    assert janela.abas.currentWidget() is janela.treino
    assert janela.atual == palavra.indices[1]
