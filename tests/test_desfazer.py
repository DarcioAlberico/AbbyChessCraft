"""Desfazer e refazer (Ctrl+Z, Ctrl+Y): a página e os padrões que o passo gravou."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from core.box_model import BoxEntry  # noqa: E402

from abbychess import historico as hs  # noqa: E402
from abbychess.modelo import Box, Pagina  # noqa: E402
from abbychess.leitor import FONTE_LIVRO, FONTE_MANUAL  # noqa: E402
from abbychess.padroes import PadroesDoLivro  # noqa: E402

from tests import test_janela  # noqa: E402
from tests.test_janela import _esperar  # noqa: E402
from tests.janela_util import atual, boxes, fila, mostrar, pulados, selecao  # noqa: E402,F401

# As fixtures da janela de `test_janela`, com o mesmo nome aqui.
app = test_janela.app
janela = test_janela.janela


def _caixas(boxes):
    return [(b.char, b.x1, b.y1, b.x2, b.y2, b.source) for b in boxes]


# ----------------------------------------------------------------------
# O histórico do projeto, sem janela
# ----------------------------------------------------------------------

def _pagina(chars="abc", pid=1):
    return Pagina(pid=pid, indice=pid - 1, proximo_n=len(chars),
                  boxes=[Box((pid << 20) | k, BoxEntry(c, 10 * k, 0, 10 * k + 8, 9))
                         for k, c in enumerate(chars)])


def _transacao(pagina, editar, descricao="passo", juntar=None):
    antes = pagina.instantaneo()
    editar(pagina)
    return hs.Transacao(descricao, {pagina.pid: hs.mudanca(antes, pagina.instantaneo())},
                        juntar=juntar)


def test_desfazer_e_refazer_andam_nas_duas_pilhas():
    from abbychess import edicao as ed

    p = _pagina()
    h = hs.HistoricoDoProjeto()
    for n, gid in enumerate(g.gid for g in list(p.boxes)[:2]):
        h.registrar(_transacao(p, lambda pg, g=gid: ed.corrigir(pg, g, "z"), f"passo {n}"))
    assert h.proximo_a_desfazer == "passo 1"
    t = h.proxima_a_desfazer()
    hs.conferir(t.paginas[1], p, para_tras=True)
    hs.aplicar(t.paginas[1], p, para_tras=True)
    h.desfeita()
    assert [b.entry.char for b in p.boxes] == ["z", "b", "c"]
    assert h.proximo_a_refazer == "passo 1"
    h.registrar(_transacao(p, lambda pg: ed.corrigir(pg, pg.boxes[2].gid, "y"), "novo"))
    assert h.proximo_a_refazer is None and h.proximo_a_desfazer == "novo"


def test_dividir_e_descartar_voltam_no_lugar_da_ordem_de_leitura():
    from abbychess import edicao as ed

    p = _pagina("abcd")
    inicial = list(p.boxes)
    meio = p.boxes[1].gid
    m1 = _transacao(p, lambda pg: ed.descartar(pg, meio)).paginas[1]
    m2 = _transacao(p, lambda pg: ed.descartar(pg, pg.boxes[0].gid)).paginas[1]
    for m in (m2, m1):
        hs.conferir(m, p, para_tras=True)
        hs.aplicar(m, p, para_tras=True)
    assert p.boxes == inicial                          # os mesmos objetos, na mesma ordem
    hs.aplicar(m1, p, para_tras=False)
    assert [b.entry.char for b in p.boxes] == ["a", "c", "d"]


def test_mudanca_por_fora_num_gid_da_transacao_recusa():
    from abbychess import edicao as ed

    p = _pagina()
    m = _transacao(p, lambda pg: ed.corrigir(pg, pg.boxes[0].gid, "z")).paginas[1]
    ed.corrigir(p, p.boxes[1].gid, "q")                # em outro gid: não impede
    hs.conferir(m, p, para_tras=True)
    ed.corrigir(p, p.boxes[0].gid, "w")                # no gid dela: recusa
    with pytest.raises(hs.Recusa):
        hs.conferir(m, p, para_tras=True)


def test_transacoes_com_a_mesma_chave_viram_uma():
    from abbychess import edicao as ed

    p = _pagina()
    h = hs.HistoricoDoProjeto()
    for c in "xyz":
        h.registrar(_transacao(p, lambda pg, c=c: ed.corrigir(pg, pg.boxes[0].gid, c),
                               juntar=("ajustar", 7)))
    t = h.proxima_a_desfazer()
    m = t.paginas[1]
    gid = p.boxes[0].gid
    assert m.antes[gid].entry.char == "a" and m.depois[gid].entry.char == "z"
    h.desfeita()
    assert h.proxima_a_desfazer() is None


def test_limite_de_memoria_tira_as_mais_antigas():
    from abbychess import edicao as ed

    p = _pagina("a" * 50)
    h = hs.HistoricoDoProjeto(limite=50 * 2 * hs.BYTES_POR_GLIFO * 3)   # cabem ~3 de 50 glifos
    for n in range(6):
        h.registrar(_transacao(p, lambda pg, n=n: [ed.corrigir(pg, b.gid, str(n))
                                                   for b in list(pg.boxes)], f"t{n}"))
    descricoes = []
    while h.proxima_a_desfazer() is not None:
        descricoes.append(h.proximo_a_desfazer)
        h.desfeita()
    assert descricoes == ["t5", "t4", "t3"] and h.bytes <= h.limite


def test_emendar_junta_a_propagacao_no_depois():
    from abbychess import edicao as ed

    p = _pagina()
    t = _transacao(p, lambda pg: ed.corrigir(pg, pg.boxes[0].gid, "z"))
    foto = p.instantaneo()
    ed.corrigir(p, p.boxes[1].gid, "y")                # o que a propagação resolveu
    hs.emendar(t.paginas[1], hs.mudanca(foto, p.instantaneo()))
    hs.aplicar(t.paginas[1], p, para_tras=True)
    assert [b.entry.char for b in p.boxes] == ["a", "b", "c"]


def test_padrao_guardado_volta_inteiro(tmp_path):
    import numpy as np

    padroes = PadroesDoLivro(tmp_path / "padroes")
    recorte = np.full((20, 12), 255, np.uint8)
    recorte[4:16, 3:9] = 0
    caminho = padroes.ensinar(recorte, "a", altura_relativa=0.8, origem="p1")
    amostra = padroes.guardar(caminho)
    padroes.esquecer(caminho)
    assert padroes.total == 0

    padroes.restaurar(amostra)
    assert padroes.total == 1
    assert padroes.amostras_de("a") == [(caminho.resolve(), pytest.approx(0.8))]
    with pytest.raises(ValueError):
        padroes.restaurar(type(amostra)(tmp_path / "fora.png", amostra.png, {}))


# ----------------------------------------------------------------------
# Na janela
# ----------------------------------------------------------------------

def _reconhecida(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    return _caixas(boxes(janela))


def test_ctrl_z_desfaz_o_ensinar_e_apaga_o_padrao(app, janela):
    inicio = _reconhecida(app, janela)
    mostrar(janela, 0)
    janela.treino.campo.setText("a")
    janela.treino.pedir_ensinar()
    _esperar(app, janela)
    assert sum(b.source == FONTE_LIVRO for b in boxes(janela)) == 4
    assert janela.acao_desfazer.text() == "Desfazer: Ensinar 'a'"

    janela.show()
    janela.treino.campo.setFocus()
    app.processEvents()
    QTest.keyClick(janela.treino.campo, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    app.processEvents()

    assert _caixas(boxes(janela)) == inicio
    assert janela.leitor.padroes_por_caractere() == {}
    assert _caixas(janela.projeto.carregar_pagina(0)) == inicio  # gravado já desfeito

    QTest.keyClick(janela.treino.campo, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    app.processEvents()
    assert len(janela.leitor.padroes_por_caractere()["a"]) == 1
    assert boxes(janela)[0].source == FONTE_MANUAL
    assert sum(b.source == FONTE_LIVRO for b in boxes(janela)) == 4


def test_desfazer_dividir_e_descartar(app, janela):
    inicio = _reconhecida(app, janela)
    mostrar(janela, 0)
    janela.treino.pedir_juntar(+1)
    janela.treino.pedir_dividir()
    mostrar(janela, 2)
    janela.treino.pedir_descartar()
    assert len(boxes(janela)) == len(inicio) - 1

    janela.pagina.desfazer()                    # volta o descartado
    assert len(boxes(janela)) == len(inicio)
    janela.pagina.desfazer()                    # desfaz a divisão: o par colado volta
    assert len(boxes(janela)) == len(inicio) - 1
    janela.pagina.desfazer()                    # desfaz a junção
    assert _caixas(boxes(janela)) == inicio
    # O que sobra é o próprio F5, que também se desfaz.
    assert janela.acao_desfazer.text() == "Desfazer: Reconhecer a página"


def test_alt_seta_seguidos_se_desfazem_de_uma_vez(app, janela):
    inicio = _reconhecida(app, janela)
    mostrar(janela, 0)
    for _ in range(3):
        janela.treino.pedir_ajustar(0, 0, 1, 0)
    janela.pagina.desfazer()
    assert _caixas(boxes(janela)) == inicio




def test_desfazer_o_reconhecimento_volta_a_pagina_de_antes(app, janela):
    _reconhecida(app, janela)
    mostrar(janela, 0)
    janela.treino.campo.setText("Z")
    janela.treino.pedir_so_corrigir()
    corrigida = _caixas(boxes(janela))
    janela.reconhecer()                  # o F5 de novo mantém a correção manual (§4.6)
    _esperar(app, janela)
    assert boxes(janela)[0].char == "Z"
    assert janela.pagina.historico.proximo_a_desfazer == "Reconhecer a página"
    janela.pagina.desfazer()
    assert _caixas(boxes(janela)) == corrigida


# ----------------------------------------------------------------------
# O desfazer do projeto (§14.2): CA-14.2 e CA-14.3
# ----------------------------------------------------------------------

def test_desfazer_e_do_projeto_e_mostra_a_pagina_que_volta(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from abbychess import pagina as pg
    from abbychess.app.janela import JanelaPrincipal
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro
    from tests.test_livro import pdf_sintetico

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Duas", pdf_sintetico(tmp_path))
    j = JanelaPrincipal()
    j.usar(projeto, pg.FonteDePaginas(projeto.fonte),
           LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    try:
        j.reconhecer()
        _esperar(app, j)
        mostrar(j, 0)
        j.pagina.corrigir("Z")
        j.ir_para_pagina(1)
        assert j.acao_desfazer.text() == "Desfazer: Corrigir para 'Z'"
        j.pagina.desfazer()                           # na página 1, desfaz a da página 0
        assert j.pagina.indice == 0 and boxes(j)[0].char != "Z"
        j.pagina.refazer()
        assert boxes(j)[0].char == "Z"
    finally:
        j.close()


def test_mudanca_por_fora_nos_gids_recusa_o_desfazer_e_em_outros_nao(app, janela, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from abbychess import edicao as ed

    avisos = []
    # A recusa pergunta se tira a ação do desfazer: aqui, "não".
    monkeypatch.setattr(QMessageBox, "question",
                        lambda _p, _t, texto, *a, **k: (avisos.append(texto),
                                                        QMessageBox.StandardButton.No)[1])
    _reconhecida(app, janela)
    mostrar(janela, 0)
    janela.pagina.corrigir("Z")
    modelo = janela.pagina.modelo
    ed.corrigir(modelo, modelo.boxes[1].gid, "q")      # por fora, noutro glifo: não impede
    ed.corrigir(modelo, modelo.boxes[0].gid, "W")      # por fora, no glifo da transação
    antes = list(modelo.boxes)
    janela.pagina.desfazer()
    assert avisos and "Não dá para desfazer" in avisos[0] and "Nada foi mudado" in avisos[0]
    assert modelo.boxes == antes and janela.acao_desfazer.text() == "Desfazer: Corrigir para 'Z'"
    ed.corrigir(modelo, modelo.boxes[0].gid, "Z")      # outro objeto, igual ao "depois"
    janela.pagina.desfazer()
    assert len(avisos) == 1 and boxes(janela)[0].char != "Z"   # igual por valor: desfaz


def _propagacao_presa(monkeypatch):
    """A propagação espera o evento antes de ler (a propagação lenta do CA-14.3)."""
    import threading

    from abbychess import pagina as pg

    solto = threading.Event()
    original = pg.propagar_padroes
    monkeypatch.setattr(pg, "propagar_padroes",
                        lambda *a, **k: (solto.wait(10), original(*a, **k))[1])
    return solto


def test_desfazer_depois_da_propagacao_volta_a_pagina_toda(app, janela):
    inicio = _reconhecida(app, janela)
    mostrar(janela, 0)
    janela.treino.campo.setText("a")
    janela.treino.pedir_ensinar()
    _esperar(app, janela)
    assert sum(b.source == FONTE_LIVRO for b in boxes(janela)) == 4   # a propagação resolveu
    janela.pagina.desfazer()
    assert _caixas(boxes(janela)) == inicio and janela.leitor.padroes_por_caractere() == {}


def test_desfazer_com_a_propagacao_rodando_descarta_o_resultado_dela(app, janela, monkeypatch):
    inicio = _reconhecida(app, janela)
    solto = _propagacao_presa(monkeypatch)
    mostrar(janela, 0)
    janela.treino.campo.setText("a")
    janela.treino.pedir_ensinar()
    assert boxes(janela)[0].source == FONTE_MANUAL       # a parte síncrona, na hora
    assert janela.executor.ocupado                        # a propagação, presa
    janela.pagina.desfazer()                              # roda na hora, com ela presa
    assert _caixas(boxes(janela)) == inicio
    solto.set()
    _esperar(app, janela)
    assert _caixas(boxes(janela)) == inicio               # o resultado dela não entrou
    assert "descartada" in janela.statusBar().currentMessage()


def test_enter_durante_uma_propagacao_nao_perde_nem_duplica_leitura(app, janela, monkeypatch):
    inicio = _reconhecida(app, janela)
    solto = _propagacao_presa(monkeypatch)
    mostrar(janela, 0)                                    # o primeiro "a"
    janela.treino.campo.setText("a")
    janela.treino.pedir_ensinar()
    assert janela.treino.campo.isEnabled()                # o painel vale durante ela
    mostrar(janela, 1)                                    # o "b", com a primeira presa
    janela.treino.campo.setText("b")
    janela.treino.pedir_ensinar()
    assert (boxes(janela)[1].char, boxes(janela)[1].source) == ("b", FONTE_MANUAL)
    solto.set()
    _esperar(app, janela)
    assert (boxes(janela)[0].source, boxes(janela)[1].source) == (FONTE_MANUAL, FONTE_MANUAL)
    assert sum(b.source == FONTE_LIVRO and b.char == "a" for b in boxes(janela)) == 4
    por_char = janela.leitor.padroes_por_caractere()
    assert len(por_char["a"]) == 1 and len(por_char["b"]) == 1     # uma amostra de cada
    janela.pagina.desfazer()                              # o "b" e a propagação dele
    janela.pagina.desfazer()                              # o "a" e a propagação dele
    assert janela.leitor.padroes_por_caractere() == {}
    assert _caixas(boxes(janela)) == inicio               # e a página volta inteira


def test_desfazer_e_refazer_uma_area(app, janela):
    janela.areas.desenhar(10, 10, 300, 120)
    criada = janela.areas.zonas
    assert len(criada) == 1 and criada[0].id            # o id nasceu com ela
    janela.pagina.desfazer()
    assert janela.areas.zonas == []
    janela.pagina.refazer()
    assert janela.areas.zonas == criada
    janela.projeto.descarregar(5)
    assert janela.projeto.carregar_zonas(0) == criada


def test_desfazer_depois_de_a_pagina_sair_da_memoria(app, tmp_path, monkeypatch):
    """A página relida do disco tem objetos novos: a pré-condição compara por valor."""
    from PySide6.QtWidgets import QMessageBox

    from abbychess import pagina as pg
    from abbychess.app.janela import JanelaPrincipal
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro
    from tests.test_livro import pdf_sintetico

    avisos = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _p, _t, texto, *a: avisos.append(texto))
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Duas", pdf_sintetico(tmp_path))
    j = JanelaPrincipal()
    j.usar(projeto, pg.FonteDePaginas(projeto.fonte),
           LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    try:
        j.reconhecer()
        _esperar(app, j)
        mostrar(j, 0)
        j.pagina.corrigir("Z")
        j.ir_para_pagina(1)
        projeto.descarregar(5)
        projeto._modelos.pop(0)                         # como se 16 páginas tivessem passado
        j.pagina.desfazer()
        assert avisos == [] and j.pagina.indice == 0 and boxes(j)[0].char != "Z"
    finally:
        j.close()


def test_enter_que_nao_grava_a_amostra_nao_deixa_nada(app, janela, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    falhas = []
    monkeypatch.setattr(QMessageBox, "critical", lambda _p, _t, texto, *a: falhas.append(texto))
    inicio = _reconhecida(app, janela)
    mostrar(janela, 0)
    janela.pagina.alternar_na_selecao(3)                # dois glifos: o segundo falha
    original = janela.leitor.padroes.ensinar
    chamadas = []

    def ensinar(*a, **k):
        chamadas.append(1)
        if len(chamadas) == 2:
            raise PermissionError("disco cheio")
        return original(*a, **k)

    monkeypatch.setattr(janela.leitor.padroes, "ensinar", ensinar)
    janela.treino.campo.setText("a")
    janela.treino.pedir_ensinar()
    _esperar(app, janela)
    assert falhas and "disco cheio" in falhas[0]
    assert _caixas(boxes(janela)) == inicio               # a página não mudou
    assert janela.leitor.padroes_por_caractere() == {}    # e a amostra gravada saiu
    assert janela.pagina.historico.proximo_a_desfazer == "Reconhecer a página"


def test_edicao_que_reordena_a_pagina_volta_na_ordem_de_antes():
    """Marcar um quadro refaz a ordem de leitura da página inteira: a transação guarda a
    ordem, e desfazer a devolve (o caso que a máquina do controlador achou)."""
    p = _pagina("abcd")
    inicial = list(p.boxes)
    novo = Box((1 << 20) | 9, BoxEntry("x", 0, 50, 8, 59))
    t = _transacao(p, lambda pg: setattr(pg, "boxes", [pg.boxes[2], pg.boxes[0], novo,
                                                       pg.boxes[3]]))
    m = t.paginas[1]
    assert m.ordem is not None
    hs.conferir(m, p, para_tras=True)
    hs.aplicar(m, p, para_tras=True)
    assert p.boxes == inicial
    hs.aplicar(m, p, para_tras=False)
    assert [b.entry.char for b in p.boxes] == ["c", "a", "x", "d"]


def test_recusa_pode_tirar_a_acao_e_seguir_com_as_anteriores(app, janela, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from abbychess import edicao as ed

    _reconhecida(app, janela)
    mostrar(janela, 1)
    janela.pagina.corrigir("Q")                         # a anterior
    mostrar(janela, 0)
    janela.pagina.corrigir("Z")                         # a recusada
    modelo = janela.pagina.modelo
    ed.corrigir(modelo, modelo.boxes[0].gid, "W")       # por fora
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    janela.pagina.desfazer()                            # recusa, e "sim": tira a ação
    assert janela.acao_desfazer.text() == "Desfazer: Corrigir para 'Q'"
    janela.pagina.desfazer()                            # e a anterior volta
    assert boxes(janela)[1].char != "Q" and boxes(janela)[0].char == "W"


def test_reler_pendentes_entra_no_desfazer(app, janela):
    inicio = _reconhecida(app, janela)
    mostrar(janela, 0)
    janela.treino.campo.setText("a")
    janela.treino.pedir_ensinar()
    _esperar(app, janela)
    janela.pagina.desfazer()                            # o Enter e a propagação saem
    janela.leitor.padroes.restaurar(janela.pagina.historico.proxima_a_refazer()
                                    .amostras_criadas[0])      # o padrão volta por fora
    janela.pagina.reler_pendentes()
    _esperar(app, janela)
    assert janela.acao_desfazer.text() == "Desfazer: Reler pendentes"
    janela.pagina.desfazer()
    assert _caixas(boxes(janela)) == inicio


def test_refazer_um_enter_desfeito_na_propagacao_propaga_de_novo(app, janela, monkeypatch):
    _reconhecida(app, janela)
    solto = _propagacao_presa(monkeypatch)
    mostrar(janela, 0)
    janela.treino.campo.setText("a")
    janela.treino.pedir_ensinar()
    janela.pagina.desfazer()                            # com a propagação presa
    solto.set()
    _esperar(app, janela)
    janela.pagina.refazer()                             # refaz e propaga de novo
    _esperar(app, janela)
    assert sum(b.source == FONTE_LIVRO for b in boxes(janela)) == 4
    janela.pagina.desfazer()                            # e o desfazer leva as duas coisas
    assert not any(b.source in (FONTE_LIVRO, FONTE_MANUAL) for b in boxes(janela))


def test_refazer_noutra_pagina_abre_a_do_enter_e_propaga(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from abbychess import pagina as pg
    from abbychess.app.janela import JanelaPrincipal
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro
    from tests.test_livro import pdf_sintetico

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Duas", pdf_sintetico(tmp_path))
    j = JanelaPrincipal()
    j.usar(projeto, pg.FonteDePaginas(projeto.fonte),
           LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    try:
        j.reconhecer()
        _esperar(app, j)
        solto = _propagacao_presa(monkeypatch)
        mostrar(j, 0)
        j.treino.campo.setText("a")
        j.treino.pedir_ensinar()
        j.pagina.desfazer()                             # com a propagação presa
        solto.set()
        _esperar(app, j)
        j.ir_para_pagina(1)
        j.pagina.refazer()                              # da página 1
        _esperar(app, j)
        assert j.pagina.indice == 0
        assert sum(b.source == FONTE_LIVRO for b in boxes(j)) >= 1   # propagou de novo
    finally:
        j.close()
