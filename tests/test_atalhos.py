"""CA-3.7, a parte de dados: `docs/atalhos.yaml` passa nas próprias regras desde o passo 0.

Cada regra tem um caso negativo montado à mão, para o verificador não passar por ser
frouxo. A parte da janela (os atalhos registrados são os do YAML) entra no passo A2.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from abbychess import atalhos

RAIZ = Path(__file__).resolve().parent.parent


def test_a_tabela_do_programa_nao_tem_problemas():
    assert atalhos.verificar(atalhos.carregar()) == []


def test_atalhos_md_esta_em_dia():
    gerado = atalhos.markdown(atalhos.carregar()) + "\n"
    assert (RAIZ / "docs" / "ATALHOS.md").read_text(encoding="utf-8") == gerado, \
        "rode ferramentas/atalhos.py"


@pytest.mark.parametrize("bruto, esperado", [
    ("ctrl+shift+pgdown", "Ctrl+Shift+PgDn"),
    ("Shift+Ctrl+Z", "Ctrl+Shift+Z"),
    ("Ctrl++", "Ctrl++"),
    ("Ctrl+,", "Ctrl+,"),
    ("alt+return", "Alt+Enter"),
    ("v", "V"),
    ("Escape", "Esc"),
    ("ctrl+f5", "Ctrl+F5"),
    ("shift+F12", "Shift+F12"),
    ("Ins", "Insert"),
])
def test_normalizar(bruto, esperado):
    assert atalhos.normalizar(bruto) == esperado


@pytest.mark.parametrize("bruto", ["Ctrl+", "Ctrl+Foo", "Hyper+A", "F25", "", "Ctrl+Ctrl+A"])
def test_normalizar_recusa_o_que_nao_e_tecla(bruto):
    with pytest.raises(ValueError):
        atalhos.normalizar(bruto)


# ----------------------------------------------------------------------
# Cada regra, com uma tabela que a quebra
# ----------------------------------------------------------------------

BASE = """
versao: 1
perfis: [padrao, finereader]
passos: ["0", A2]
escopos:
  global:   {widgets: [], editavel: false}
  imagem:   {widgets: [graphicsview], editavel: false}
  areas:    {dentro_de: imagem, widgets: [graphicsview], editavel: false}
  documento: {widgets: [textedit], editavel: true}
widgets_da_janela: [textedit, graphicsview, tabwidget]
nativos:
  textedit: {vence: [Ctrl+Home, Ctrl+Z]}
  graphicsview: {perde: [PgDn]}
  tabwidget: {perde: [Ctrl+Tab]}
"""


def _problemas(tmp_path, acoes: str, base: str = BASE):
    """Cada parâmetro é um bloco YAML de ações (começa por quebra de linha)."""
    arquivo = tmp_path / "atalhos.yaml"
    arquivo.write_text(base + "acoes:\n" + textwrap.indent(textwrap.dedent(acoes), "  "),
                       encoding="utf-8")
    return atalhos.verificar(atalhos.carregar(arquivo))


def test_tabela_minima_valida(tmp_path):
    assert _problemas(tmp_path, """
        - {id: a, descricao: A, escopo: [global], padrao: F5, desde_passo: A2}
        - {id: b, descricao: B, escopo: [areas], padrao: T, desde_passo: A2}
    """) == []


@pytest.mark.parametrize("acoes, trecho", [
    ("""
        - {id: a, descricao: A, escopo: [global], padrao: F5, desde_passo: A2}
        - {id: b, descricao: B, escopo: [documento], padrao: F5, desde_passo: A2}
     """, "colide"),
    ("""
        - {id: a, descricao: A, escopo: [imagem], padrao: Ctrl+K, desde_passo: A2}
        - {id: b, descricao: B, escopo: [areas], padrao: Ctrl+K, desde_passo: A2}
     """, "colide"),
    ("""
        - {id: a, descricao: A, escopo: [global], padrao: F5, finereader: F6, desde_passo: A2}
        - {id: b, descricao: B, escopo: [global], padrao: F7, finereader: F6, desde_passo: A2}
     """, "[finereader] F6"),
    ("\n- {id: a, descricao: A, escopo: [documento], padrao: H, desde_passo: A2}\n", "seria digitado"),
    ("\n- {id: a, descricao: A, escopo: [documento], padrao: '5', desde_passo: A2}\n", "seria digitado"),
    ("\n- {id: a, descricao: A, escopo: [documento], padrao: '-', desde_passo: A2}\n", "seria digitado"),
    ("\n- {id: a, descricao: A, escopo: [global], padrao: V, desde_passo: A2}\n", "seria digitado"),
    ("\n- {id: a, descricao: A, escopo: [global], padrao: Ctrl+Alt+0, desde_passo: A2}\n", "AltGr"),
    ("\n- {id: a, descricao: A, escopo: [global], padrao: Alt+P, desde_passo: A2}\n", "menus"),
    ("\n- {id: a, descricao: A, escopo: [global], padrao: Tab, desde_passo: A2}\n", "Tab nunca"),
    ("\n- {id: a, descricao: A, escopo: [global], padrao: Shift+F10, desde_passo: A2}\n", "contexto"),
    ("\n- {id: a, descricao: A, escopo: [global], padrao: F10, desde_passo: A2}\n", "barra de menus"),
    ("\n- {id: a, descricao: A, escopo: [global], padrao: Alt+F4, desde_passo: A2}\n", "fecha a janela"),
    ("\n- {id: a, descricao: A, escopo: [documento], padrao: Ctrl+Home, desde_passo: A2}\n", "não dispara"),
    ("\n- {id: a, descricao: A, escopo: [global], padrao: Ctrl+Tab, desde_passo: A2}\n", "apaga a ligação"),
    ("\n- {id: a, descricao: A, escopo: [imagem], padrao: PgDn, desde_passo: A2}\n", "apaga a ligação"),
    ("\n- {id: a, descricao: A, escopo: [global], sem_atalho: [padrao], desde_passo: A2}\n",
     "perfil finereader"),
    ("\n- {id: a, descricao: A, escopo: [global], padrao: F5, sem_atalho: [padrao], desde_passo: A2}\n",
     "em `sem_atalho` e com sequência"),
    ("\n- {id: a, descricao: A, escopo: [global], padrao: F5, sem_atalho: [outro], desde_passo: A2}\n",
     "perfil desconhecido"),
    ("\n- {id: a, descricao: A, escopo: [global], padrao: F5, desde_passo: Z9}\n", "não é passo"),
    ("""
        - id: a
          descricao: A
          escopo: [global]
          padrao: Ctrl+Z
          desde_passo: A2
          excecoes: [{tecla: Ctrl+Z, widget: textedit, tipo: redireciona, motivo: " "}]
     """, "sem motivo"),
    ("""
        - id: a
          descricao: A
          escopo: [global]
          padrao: F5
          desde_passo: A2
          excecoes: [{tecla: Ctrl+Z, widget: textedit, tipo: redireciona, motivo: velha}]
     """, "não é sequência da ação"),
    ("""
        - id: a
          descricao: A
          escopo: [global]
          padrao: Ctrl+Z
          desde_passo: A2
          excecoes: [{tecla: Ctrl+Z, widget: textedit, tipo: substitui, motivo: lado errado}]
     """, "não corresponde"),
    ("""
        - id: a
          descricao: A
          escopo: [imagem]
          padrao: Ctrl+Z
          desde_passo: A2
          excecoes: [{tecla: Ctrl+Z, widget: textedit, tipo: redireciona, motivo: fora}]
     """, "fora do escopo"),
    ("""
        - id: a
          descricao: A
          escopo: [global]
          padrao: Ctrl+Z
          desde_passo: A2
          excecoes: [{tecla: Ctrl+Z, widget: textedit, tipo: outro, motivo: tipo errado}]
     """, "sem tipo válido"),
    ("""
        - {id: a, descricao: A, escopo: [global], padrao: F5, desde_passo: A2}
        - {id: a, descricao: B, escopo: [global], padrao: F6, desde_passo: A2}
     """, "id repetido"),
    ("""
        - id: a
          descricao: A
          escopo: [global]
          padrao: Ctrl+Z
          desde_passo: A2
          excecoes: [{tecla: Ctrl+Z, widget: textedit}]
     """, "exceção sem tipo, motivo"),
    ("""
- {id: a, descricao: A, escopo: [global], padrao: F5, finerader: F6, desde_passo: A2}
""",
     "chave desconhecida 'finerader'"),
    ("""
- {id: a, descricao: A, escopo: [], padrao: F5, desde_passo: A2}
""", "`escopo` vazio"),
    ("""
- {descricao: A, escopo: [global], padrao: F5, desde_passo: A2}
""", "falta `id`"),
    ("""
- {id: a, descricao: A, escopo: [documento], padrao: Space, desde_passo: A2}
""",
     "tecla de edição"),
    ("""
- {id: a, descricao: A, escopo: [documento], padrao: Shift+Backspace, desde_passo: A2}
""",
     "tecla de edição"),
])
def test_cada_regra_reprova(tmp_path, acoes, trecho):
    """Cada caso quebra uma regra só: todo problema achado tem de ser o dela."""
    problemas = _problemas(tmp_path, acoes)
    assert problemas and all(trecho in p for p in problemas), problemas


def test_sem_atalho_tira_a_acao_do_perfil(tmp_path):
    """Sem a chave `finereader`, a sequência do padrão valeria lá; `sem_atalho` a tira."""
    assert _problemas(tmp_path, """
        - {id: a, descricao: A, escopo: [global], padrao: F5, sem_atalho: [finereader], desde_passo: A2}
        - {id: b, descricao: B, escopo: [global], sem_atalho: [padrao], finereader: F5, desde_passo: A2}
    """) == []


def test_ciclo_em_dentro_de_e_problema(tmp_path):
    base = BASE.replace("areas:    {dentro_de: imagem,", "areas:    {dentro_de: areas,")
    problemas = _problemas(tmp_path, "\n- {id: a, descricao: A, escopo: [global], padrao: F5, "
                                     "desde_passo: A2}\n", base)
    assert any("ciclo" in p for p in problemas), problemas


def test_dentro_de_que_aponta_para_escopo_que_nao_existe_e_problema(tmp_path):
    base = BASE.replace("areas:    {dentro_de: imagem,", "areas:    {dentro_de: nenhum,")
    problemas = _problemas(tmp_path, """
        - {id: a, descricao: A, escopo: [global], padrao: F5, desde_passo: A2}
    """, base)
    assert problemas == ["escopo areas: `dentro_de` aponta para 'nenhum', que não existe"]


def test_excecao_declarada_libera_o_nativo(tmp_path):
    assert _problemas(tmp_path, """
        - id: a
          descricao: A
          escopo: [global]
          padrao: Ctrl+Z
          desde_passo: A2
          excecoes: [{tecla: Ctrl+Z, widget: textedit, tipo: redireciona, motivo: desfazer da página}]
    """) == []


def test_ativas_respeita_desde_passo():
    tabela = atalhos.carregar()
    no_a1 = {a.id for a, _ in tabela.ativas("padrao", "A1")}
    assert "ir_para_pagina" in no_a1 and "substituir" not in no_a1


def test_acao_que_nao_existe_e_erro_claro():
    with pytest.raises(KeyError, match="não há ação 'nenhuma'"):
        atalhos.carregar().da_acao("nenhuma")
