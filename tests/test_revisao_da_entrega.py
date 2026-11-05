"""Os defeitos que a revisão independente de M1 a M3 achou, cada um com o caso dele."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from core.box_model import BoxEntry

from abbychess import decodificador_de_lances as dl
from abbychess import evidencia as ev
from abbychess import pagina as pg
from abbychess.dados_do_projeto import Limiares
from abbychess.modelo import Decisoes, GlifoVirtual, Pagina
from abbychess.pasta_do_projeto import ARQUIVO_DO_PROJETO, PASTA_DE_PAGINAS
from abbychess.projeto import ProjetoDeLivro
from tests.ajudantes import ExecutorManual, _controlador, _pagina_sintetica

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
from medir_sincronia import _Diagrama, documento_de_linhas as _do_texto  # noqa: E402

INICIAL = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"


def _documento(*itens):
    return _do_texto(itens)


def _projeto_de_core_mais_novo(tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path, "Livro", _pagina_sintetica(tmp_path / "p.png"))
    projeto.salvar_pagina(0, [BoxEntry("a", 1, 2, 3, 4)])
    projeto.fechar()
    arquivo = next((projeto.pasta / PASTA_DE_PAGINAS).glob("p*.json"))
    bruto = json.loads(arquivo.read_text(encoding="utf-8"))
    bruto["boxes"][0][1].append("campo novo")
    arquivo.write_text(json.dumps(bruto), encoding="utf-8", newline="\n")
    return projeto.pasta


def test_a_pagina_de_core_mais_novo_nao_abre_mas_nao_quebra_a_navegacao(tmp_path):
    pasta = _projeto_de_core_mais_novo(tmp_path)
    arquivo_do_projeto = pasta / ARQUIVO_DO_PROJETO
    bruto = json.loads(arquivo_do_projeto.read_text(encoding="utf-8"))
    bruto["campos_do_box"] = bruto["campos_do_box"] + 1
    arquivo_do_projeto.write_text(json.dumps(bruto), encoding="utf-8", newline="\n")
    projeto = ProjetoDeLivro.abrir(pasta)
    try:
        from abbychess.controlador import ControladorDePagina
        from abbychess.leitor import LeitorDoLivro

        ctl = ControladorDePagina(executar=ExecutorManual())
        avisos = []
        ctl.eventos.ligar("aviso", lambda t, m: avisos.append(m))
        ctl.ligar(projeto, pg.FonteDePaginas(projeto.fonte),
                  LeitorDoLivro(projeto.pasta_de_padroes, limiares=Limiares()))
        assert ctl.ir_para(0) is False
        assert "versão mais nova" in avisos[0]
        assert ctl.modelo is None
    finally:
        projeto.fechar()


def test_o_resumo_refeito_nao_quebra_com_a_pagina_de_core_mais_novo(tmp_path):
    projeto = ProjetoDeLivro.abrir(_projeto_de_core_mais_novo(tmp_path))
    try:
        assert projeto.resumo.recalcular() is not None
    finally:
        projeto.fechar()


def test_a_letra_inserida_conta_como_conferida():
    documento, _d = _documento("Nf3")
    pagina = Pagina(0, 0, decisoes=Decisoes(virtuais=(GlifoVirtual(0, "N", None),)))
    assert 0 in ev.conferidos(pagina)
    assert dl.lances_por_conferir(documento, set(documento.chars), "KQRBN") == 0


def test_o_ilegal_com_sinal_nao_conta_duas_vezes(app, tmp_path):
    from abbychess import lances as lc
    from tests.ajudantes import _lido

    documento, _ = _documento(_Diagrama("d0", INICIAL), "1.Bf3!")
    diagrama = replace(_lido(INICIAL + " w - - 0 1"), id="d0",
                       validacao=lc.Validacao(lc.ILEGAL, 1, 0, "1.Bf3 do texto não é legal aqui", "w"))
    assert len(ev.rejeitados(documento, [diagrama], "KQRBN")) == 1


def test_a_chave_da_evidencia_ve_as_decisoes(tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path, "Livro", _pagina_sintetica(tmp_path / "p.png"))
    try:
        projeto.salvar_pagina(0, [BoxEntry("a", 1, 2, 3, 4, 0.9, "net")])
        ctl = _controlador(projeto, ExecutorManual())
        primeira = ctl.evidencia.agora()
        ctl.modelo.decisoes = Decisoes(quebras=frozenset({ctl.modelo.boxes[0].gid}))
        chamadas = []
        original = ev.da_pagina
        ev_da = lambda *a: (chamadas.append(1), original(*a))[1]  # noqa: E731
        ev.da_pagina = ev_da
        try:
            ctl.evidencia.agora()
        finally:
            ev.da_pagina = original
        assert chamadas and primeira is not None
    finally:
        projeto.fechar()


def test_as_letras_novas_refazem_a_validacao_da_pagina_aberta(tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path, "Livro", _pagina_sintetica(tmp_path / "p.png"))
    try:
        projeto.salvar_pagina(0, [BoxEntry("a", 1, 2, 3, 4, 0.9, "net")])
        ctl = _controlador(projeto, ExecutorManual())
        mudou = []
        ctl.eventos.ligar("glifos_mudaram", mudou.append)
        ctl.padroes_do_livro.definir_letras("KQRBN")
        assert projeto.dados.letras_das_pecas == "KQRBN" and mudou
        mudou.clear()
        ctl.padroes_do_livro.definir_letras("KQRBN")
        assert not mudou
    finally:
        projeto.fechar()


def test_o_resumo_leve_nao_monta_o_texto(tmp_path, monkeypatch):
    from abbychess import texto as tx

    projeto = ProjetoDeLivro.criar(tmp_path, "Livro", _pagina_sintetica(tmp_path / "p.png"))
    try:
        projeto.salvar_pagina(0, [BoxEntry("e", 1, 2, 3, 4, 0.9, "net"), BoxEntry("4", 4, 2, 6, 4, 0.9, "net")])
        modelo = projeto.carregar_modelo(0)
        guardado = projeto.resumo.do_livro()[0]["lances_por_conferir"]
        monkeypatch.setattr(tx, "montar", lambda *_a, **_k: pytest.fail("montou"))
        assert projeto.resumo.do_modelo(modelo, leve=True)["lances_por_conferir"] == guardado
    finally:
        projeto.fechar()


def test_o_resumo_leve_sem_gravacao_nao_afirma_a_contagem(tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path, "Livro", _pagina_sintetica(tmp_path / "p.png"))
    try:
        assert "lances_por_conferir" not in projeto.resumo.do_modelo(Pagina(9, 0), leve=True)
    finally:
        projeto.fechar()


def test_depois_de_um_diagrama_nao_lido_o_um_nao_e_a_posicao_inicial():
    documento, diagramas = _documento(_Diagrama("d", "", lido=False), "1.e4 e5 2.Qh8")
    saida = dl.decodificar(documento, diagramas, "KQRBN")
    assert [t.estado for t in saida.lances] == ["sem_posicao"] * 3


def test_a_paleta_apaga_o_filtro_e_o_digito_sem_uso_nao_esvazia(app):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtTest import QTest

    from abbychess.app import painel_treino as pt

    pt._USO_DA_PALETA.clear()
    menu = pt.menu_da_paleta(None, [].append)
    QTest.keyClicks(menu, "1")
    assert not menu.filtro and menu.acoes_dos_simbolos["♔"].isVisible()
    QTest.keyClicks(menu, "pre")                         # os pretos: mais de um resultado
    assert not menu.acoes_dos_simbolos["♔"].isVisible()
    for _ in "pre":     # direto: no teste, uma janela aberta tomaria a tecla como atalho dela
        menu.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Backspace,
                                     Qt.KeyboardModifier.NoModifier, "\b"))
    assert not menu.filtro and menu.acoes_dos_simbolos["♔"].isVisible()
