"""O editor Área do Inspetor (SPEC §3.1): função e ordem, e só aparece por ação explícita."""

from __future__ import annotations

from abbychess import zonas as zn

from tests.ajudantes import _ler_a_mao  # noqa: E402,F401,F811
from tests.fixturas_janela import janela  # noqa: E402,F401,F811


def _duas_areas(app, janela):  # noqa: F811
    _ler_a_mao(app, janela)
    largura, altura = janela.pagina.imagem.size
    janela.pagina.modelo.zonas = [
        zn.Zona(zn.TEXTO, 0, 0, largura, altura // 2, id="z0"),
        zn.Zona(zn.TEXTO, 0, altura // 2, largura, altura, id="z1"),
    ]
    janela.acao_areas.setChecked(True)
    janela.modo_areas(True)
    app.processEvents()


def _editor(janela):  # noqa: F811
    return janela.inspetor.editores["area"]


def _escolher_a_funcao(editor, funcao: str) -> None:
    indice = editor.campo.findData(funcao)
    editor.campo.setCurrentIndex(indice)
    editor.campo.activated.emit(indice)


def test_o_clique_na_area_abre_o_editor_com_a_funcao_e_o_numero(app, janela):  # noqa: F811
    _duas_areas(app, janela)
    assert janela.inspetor.atual() != "area"
    janela.visor.zona_escolhida.emit(1)
    editor = _editor(janela)
    assert janela.inspetor.atual() == "area" and janela.inspetor.editor() is editor
    assert editor.campo.currentData() == "texto" and not editor.formulario.isHidden()
    assert (editor.ordem.value(), editor.ordem.maximum()) == (2, 2)


def test_mudar_a_funcao_no_editor_muda_o_documento_e_se_desfaz(app, janela):  # noqa: F811
    _duas_areas(app, janela)
    janela.visor.zona_escolhida.emit(0)
    _escolher_a_funcao(_editor(janela), "titulo")
    assert janela.areas.zonas[0].funcao == "titulo"
    assert janela.pagina.documento().blocos[0].funcao == "titulo"
    janela.pagina.desfazedor.desfazer()
    assert janela.areas.zonas[0].funcao == "texto"


def test_mudar_o_numero_leva_a_area_na_ordem_e_se_desfaz(app, janela):  # noqa: F811
    _duas_areas(app, janela)
    janela.visor.zona_escolhida.emit(1)
    _editor(janela).ordem.setValue(1)
    assert [z.ordem for z in janela.areas.zonas] == [1, 0]
    assert [b.zona_id for b in janela.pagina.documento().blocos] == ["z1", "z0"]
    assert _editor(janela).ordem.value() == 1
    janela.pagina.desfazedor.desfazer()
    assert [z.ordem for z in janela.areas.zonas] == [None, None]


def test_trocar_a_funcao_pela_letra_atualiza_o_editor_aberto(app, janela):  # noqa: F811
    _duas_areas(app, janela)
    janela.visor.zona_escolhida.emit(0)
    janela.areas.trocar_funcao_atual("nota")
    assert _editor(janela).campo.currentData() == "nota"


def test_o_ordenar_nao_troca_de_editor(app, janela):  # noqa: F811
    """No Ordenar, o clique diz a ordem: o editor fica onde está."""
    _duas_areas(app, janela)
    janela.areas.iniciar_ordenacao()
    janela.visor.zona_escolhida.emit(0)
    assert janela.inspetor.atual() != "area"


def test_mudar_as_areas_sem_clicar_nao_troca_de_editor(app, janela):  # noqa: F811
    """§3.1: só por ação explícita, nunca por foco nem por uma mudança na página."""
    _duas_areas(app, janela)
    janela._layout_mudou()
    assert janela.inspetor.atual() != "area"


def test_sair_do_editor_de_areas_volta_ao_glifo(app, janela):  # noqa: F811
    _duas_areas(app, janela)
    janela.visor.zona_escolhida.emit(0)
    janela.acao_areas.setChecked(False)
    janela.modo_areas(False)
    assert janela.inspetor.atual() == "glifo"


def test_sem_area_escolhida_o_editor_diz_o_que_fazer(app, janela):  # noqa: F811
    _duas_areas(app, janela)
    janela.visor.zona_escolhida.emit(0)
    janela.areas.escolher(-1)
    editor = _editor(janela)
    assert editor.formulario.isHidden() and not editor.vazio.isHidden()
    assert "Ctrl+Shift+A" in editor.vazio.text()


def test_o_inspetor_tem_a_dica_do_editor(app, janela):  # noqa: F811
    _duas_areas(app, janela)
    janela.visor.zona_escolhida.emit(0)
    assert "Del" in janela.inspetor.dica.text()
