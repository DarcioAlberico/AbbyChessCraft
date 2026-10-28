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
from tests.janela_util import atual, boxes, fila, mostrar, pulados, selecao  # noqa: E402,F401


def _ler_a_mao(app, janela):  # noqa: F811
    """Reconhece e dá aos glifos a leitura certa, como se a rede tivesse lido."""
    letras = list("abcabcabc" + "cabbca")
    janela.reconhecer()
    _esperar(app, janela)
    assert len(boxes(janela)) == len(letras)
    for b, c in zip(boxes(janela), letras):
        b.char, b.source, b.confidence = c, "neural", 0.99
    janela._glifos_mudaram()


# ----------------------------------------------------------------------
# Editor de áreas
# ----------------------------------------------------------------------

def test_ferramentas_tem_o_editor_de_areas_e_a_verificacao(janela):  # noqa: F811
    textos = [a.text() for a in janela.menu_ferramentas.actions()]
    assert any("Editor de áreas" in t for t in textos)
    assert any("Verificação de texto" in t for t in textos)
    assert janela.acao_ciclar_fila.shortcut().toString() == "F7"      # a fila de palavras é um modo


def test_editor_de_areas_e_modo_de_treino_se_excluem(janela):  # noqa: F811
    janela.acao_modo_treino.setChecked(True)
    janela.modo_treino(True)
    janela.acao_areas.setChecked(True)
    janela.modo_areas(True)
    assert janela.visor.modo_areas and not janela.visor.modo_treino
    assert not janela.acao_modo_treino.isChecked()

    janela.acao_modo_treino.setChecked(True)
    janela.modo_treino(True)
    assert janela.visor.modo_treino and not janela.visor.modo_areas
    assert not janela.acao_areas.isChecked()


def test_ligar_o_editor_numa_pagina_nova_acha_as_areas(app, janela):  # noqa: F811
    janela.acao_areas.setChecked(True)
    janela.modo_areas(True)
    _esperar(app, janela)
    assert janela.areas.zonas and all(z.tipo == zn.TEXTO for z in janela.areas.zonas)
    assert janela.projeto.carregar_zonas(0) == janela.areas.zonas
    assert boxes(janela) == []  # achar as áreas não reconhece a página


def test_desenhar_tipar_e_reconhecer_pelas_areas(app, janela):  # noqa: F811
    janela.acao_areas.setChecked(True)
    janela.modo_areas(True)
    _esperar(app, janela)
    largura, altura = janela.pagina.imagem.size
    # Arraste no visor fora de qualquer área: uma área nova na metade de baixo.
    for _ in list(janela.areas.zonas):
        janela.areas.apagar(0)
    visor = janela.visor
    visor.apertar_no_editor_de_areas(QPointF(0, 0))
    visor.soltar_area(QPointF(0, 0), QPointF(largura - 1, altura - 1))
    assert len(janela.areas.zonas) == 1 and janela.areas.zonas[0].tipo == zn.TEXTO
    visor.apertar_no_editor_de_areas(QPointF(5, altura // 2 + 5))  # fora: nada escolhido
    visor.soltar_area(QPointF(5, 125), QPointF(largura - 5, altura - 5))
    assert len(janela.areas.zonas) == 2 and janela.areas.atual == 1
    janela.areas.trocar_tipo(1, zn.IGNORAR)  # a tecla 4

    janela.reconhecer()
    _esperar(app, janela)
    assert len(boxes(janela)) == 9  # só a primeira linha; a segunda está em "ignorar"
    assert janela.projeto.carregar_zonas(0)[1].tipo == zn.IGNORAR

    janela.areas.apagar(1)
    janela.reconhecer()
    _esperar(app, janela)
    assert len(boxes(janela)) == 15


def test_arrastar_a_area_move_e_grava(app, janela):  # noqa: F811
    janela.acao_areas.setChecked(True)
    janela.modo_areas(True)
    _esperar(app, janela)
    antes = janela.areas.zonas[0]
    janela.visor.apertar_no_editor_de_areas(QPointF((antes.x1 + antes.x2) / 2,
                                                    (antes.y1 + antes.y2) / 2))
    assert janela.areas.atual == 0
    janela.visor.soltar_arraste(QPointF((antes.x1 + antes.x2) / 2 + 10,
                                        (antes.y1 + antes.y2) / 2 + 5))
    depois = janela.projeto.carregar_zonas(0)[0]
    assert (depois.x1, depois.y1) == (antes.x1 + 10, antes.y1 + 5)


def test_o_menu_da_area_tem_imagem_e_ela_vira_imagem(app, janela):  # noqa: F811
    janela.acao_areas.setChecked(True)
    janela.modo_areas(True)
    _esperar(app, janela)
    acoes = {a.text().split("\t")[0]: a for a in janela.visor.menu_da_zona(0).actions()}
    assert acoes["Imagem"].text() == "Imagem\tI"
    acoes["Imagem"].trigger()
    z = janela.projeto.carregar_zonas(0)[0]
    assert (z.tipo, z.funcao) == (zn.IMAGEM, "figura")
    assert janela.acoes_das_funcoes[-2].shortcut().toString() == "I"


def test_funcao_e_ordem_das_areas_atualizam_o_documento_e_desfazem(app, janela):  # noqa: F811
    _ler_a_mao(app, janela)
    largura, altura = janela.pagina.imagem.size
    janela.pagina.modelo.zonas = [
        zn.Zona(zn.TEXTO, 0, 0, largura, altura // 2, id="z0"),
        zn.Zona(zn.TEXTO, 0, altura // 2, largura, altura, id="z1"),
    ]
    janela.areas.escolher(0)
    janela.areas.trocar_funcao_atual("titulo")
    assert janela.pagina.documento().blocos[0].funcao == "titulo"
    janela.pagina.desfazer()
    assert janela.areas.zonas[0].funcao == "texto"

    janela.areas.iniciar_ordenacao()
    janela.areas.escolher(1)
    janela.areas.escolher(0)
    assert [z.ordem for z in janela.areas.zonas] == [1, 0]
    assert [b.zona_id for b in janela.pagina.documento().blocos] == ["z1", "z0"]


def test_esc_cancela_a_ordenacao_sem_mudar_as_areas(app, janela):  # noqa: F811
    janela.acao_areas.setChecked(True)
    janela.modo_areas(True)
    _esperar(app, janela)
    antes = list(janela.areas.zonas)
    janela.areas.iniciar_ordenacao()
    janela.areas.escolher(0)
    janela.areas.cancelar_ordenacao()
    assert janela.areas.zonas == antes


def test_reconhecer_so_a_zona_preserva_boxes_de_fora(app, janela):  # noqa: F811
    _ler_a_mao(app, janela)
    pagina = janela.pagina
    primeira = min(b.y1 for b in pagina.boxes)
    alvo = zn.Zona(zn.TEXTO, 0, primeira - 5, pagina.imagem.width, primeira + 40, id="z0")
    fora = next(b for b in pagina.modelo.boxes if b.entry.y1 > alvo.y2)
    pagina.escolher(fora.gid)
    pagina.corrigir("Z")

    pagina.reconhecer_zona(alvo)
    _esperar(app, janela)

    assert pagina.modelo.box(fora.gid).entry.char == "Z"
    assert pagina.modelo.box(fora.gid).entry.source == FONTE_MANUAL


# ----------------------------------------------------------------------
# Verificação de texto
# ----------------------------------------------------------------------

def test_verificar_anda_pelas_desconhecidas_e_corrige(app, janela):  # noqa: F811
    _ler_a_mao(app, janela)
    janela.verificador.lexico = lexico.Lexico(palavras={"abc", "cab"})
    janela.verificar_texto()
    assert janela.inspetor.atual() == "palavra"
    assert [d.palavra for d in janela.verificador.desconhecidas] == ["bca"]
    assert janela.verificacao.campo.text() == "bca"
    assert not janela.verificacao.recorte.pixmap().isNull()

    janela.verificacao.campo.setText("abc")
    janela.verificacao.pedir_corrigir()
    assert janela.verificador.desconhecidas == []
    assert "Nenhuma" in janela.verificacao.posicao.text()
    assert [b.char for b in boxes(janela)[-3:]] == ["a", "b", "c"]
    assert boxes(janela)[-3].source == FONTE_MANUAL
    assert janela.projeto.carregar_pagina(0)[-3].char == "a"


def test_corrigir_e_ensinar_grava_o_padrao(app, janela):  # noqa: F811
    _ler_a_mao(app, janela)
    janela.verificador.lexico = lexico.Lexico(palavras={"abc", "cab"})
    janela.verificar_texto()
    janela.verificacao.campo.setText("aca")
    janela.verificacao.pedir_ensinar()
    _esperar(app, janela)
    assert "a" in janela.leitor.padroes_por_caractere()


def test_letras_de_mais_nao_mexem_na_pagina(app, janela):  # noqa: F811
    _ler_a_mao(app, janela)
    janela.verificador.lexico = lexico.Lexico(palavras={"abc", "cab"})
    janela.verificar_texto()
    janela.verificador.corrigir("bcaa")
    assert "Divida ou junte" in janela.statusBar().currentMessage()
    assert [b.char for b in boxes(janela)[-3:]] == ["b", "c", "a"]


def test_adicionar_e_ignorar_todas(app, janela):  # noqa: F811
    _ler_a_mao(app, janela)
    janela.verificador.lexico = lexico.Lexico(palavras={"abc", "cab"})
    janela.verificar_texto()
    janela.verificador.ignorar_todas()
    assert janela.verificador.desconhecidas == []
    janela.verificador.ignoradas = set()
    janela.verificador.recontar(0)
    janela._adicionar_palavra()
    assert janela.verificador.desconhecidas == []
    assert janela.projeto.arquivo_do_lexico.read_text(encoding="utf-8") == "bca\n"


def test_clique_no_glifo_abre_o_treino(app, janela):  # noqa: F811
    _ler_a_mao(app, janela)
    janela.verificador.lexico = lexico.Lexico(palavras={"abc", "cab"})
    janela.verificar_texto()
    palavra = janela.verificador.desconhecidas[0]
    _, x1, x2 = janela.verificacao._glifos[1]
    assert janela.verificacao.glifo_em((x1 + x2) / 2) == palavra.indices[1]
    janela.verificacao._clicar((x1 + x2) / 2, 0)
    assert janela.inspetor.atual() == "glifo"
    assert atual(janela) == palavra.indices[1]
