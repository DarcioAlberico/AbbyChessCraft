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

from tests import fixturas_janela  # noqa: E402
janela = fixturas_janela.janela  # a fixture do apoio, com o nome que os testes pedem
from tests.ajudantes import _esperar  # noqa: E402,F401,F811
from tests.janela_util import atual, boxes, fila, mostrar, pulados, selecao  # noqa: E402,F401



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


def test_emendar_a_propagacao_que_descarta_reordena_e_muda_o_estado():
    """A propagação descarta o glifo do Enter, reordena a página e muda o estado: desfazer a
    transação emendada volta à página de antes do Enter, e refazer, à de depois de tudo."""
    from abbychess import edicao as ed
    from abbychess.modelo import NAO_RECONHECIDA, RECONHECIDA

    p = _pagina("abcd")
    inicial = list(p.boxes)
    t = _transacao(p, lambda pg: ed.corrigir(pg, pg.boxes[0].gid, "z"))
    foto = p.instantaneo()
    ed.descartar(p, p.boxes[0].gid)                    # o glifo do Enter sai
    p.boxes = [p.boxes[1], p.boxes[0], p.boxes[2]]     # e a ordem muda
    p.estado = RECONHECIDA
    hs.emendar(t.paginas[1], hs.mudanca(foto, p.instantaneo()))
    m = t.paginas[1]
    hs.conferir(m, p, para_tras=True)
    hs.aplicar(m, p, para_tras=True)
    assert p.boxes == inicial and p.estado == NAO_RECONHECIDA
    hs.conferir(m, p, para_tras=False)
    hs.aplicar(m, p, para_tras=False)
    assert [b.entry.char for b in p.boxes] == ["c", "b", "d"] and p.estado == RECONHECIDA


def test_emendar_esquece_o_que_a_propagacao_desfez_e_guarda_o_que_ela_criou():
    """O glifo que o Enter criou e a propagação descartou, e o estado que ela voltou, saem da
    transação; o glifo que a propagação criou entra, e desfazer o tira."""
    from abbychess.modelo import NAO_RECONHECIDA, RECONHECIDA

    p = _pagina("abc")
    inicial = list(p.boxes)
    criado = Box((1 << 20) | 9, BoxEntry("x", 40, 0, 48, 9))

    def enter(pg):
        pg.boxes = pg.boxes + [criado]
        pg.estado = RECONHECIDA

    t = _transacao(p, enter)
    foto = p.instantaneo()
    da_propagacao = Box((1 << 20) | 10, BoxEntry("y", 50, 0, 58, 9))
    p.boxes = inicial[:2] + [da_propagacao] + inicial[2:]
    p.estado = NAO_RECONHECIDA
    hs.emendar(t.paginas[1], hs.mudanca(foto, p.instantaneo()))
    m = t.paginas[1]
    assert set(m.antes) == {da_propagacao.gid} and m.campos == {}
    hs.conferir(m, p, para_tras=True)
    hs.aplicar(m, p, para_tras=True)
    assert p.boxes == inicial
    hs.aplicar(m, p, para_tras=False)
    assert [b.entry.char for b in p.boxes] == ["a", "b", "y", "c"]


def test_padrao_guardado_volta_inteiro(tmp_path):
    import numpy as np

    padroes = PadroesDoLivro(tmp_path / "padroes")
    recorte = np.full((20, 12), 255, np.uint8)
    recorte[4:16, 3:9] = 0
    caminho = padroes.ensinar(recorte, "a", altura_relativa=0.8, origem="p1")
    amostra = padroes.guardar(caminho)
    padroes.esquecer(caminho)
    assert padroes.total == 0

    padroes.restaurar_varios([amostra])
    assert padroes.total == 1
    assert padroes.amostras_de("a") == [(caminho.resolve(), pytest.approx(0.8))]
    with pytest.raises(ValueError):
        padroes.restaurar_varios([type(amostra)(tmp_path / "fora.png", amostra.png, {})])


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


def test_o_desfazer_que_falha_nos_padroes_ja_moveu_o_historico(app, janela, monkeypatch):
    """SPEC-qualidade Q-C5: as páginas voltam e o histórico anda junto com elas; um padrão
    que não sai do disco é avisado, e não deixa a transação para trás, já aplicada."""
    inicio = _reconhecida(app, janela)
    mostrar(janela, 0)
    janela.treino.campo.setText("a")
    janela.treino.pedir_ensinar()
    _esperar(app, janela)
    avisos = []
    janela.pagina.eventos.ligar("aviso", lambda titulo, texto: avisos.append(texto))

    def disco_cheio(caminhos):
        raise OSError("disco cheio")
    monkeypatch.setattr(janela.leitor, "esquecer_varios", disco_cheio)
    janela.pagina.desfazedor.desfazer()
    _esperar(app, janela)

    assert _caixas(boxes(janela)) == inicio
    assert janela.pagina.historico.proxima_a_refazer().descricao == "Ensinar 'a'"
    assert any("disco cheio" in texto for texto in avisos)


def test_desfazer_dividir_e_descartar(app, janela):
    inicio = _reconhecida(app, janela)
    mostrar(janela, 0)
    janela.treino.pedir_juntar(+1)
    janela.treino.pedir_dividir()
    mostrar(janela, 2)
    janela.treino.pedir_descartar()
    assert len(boxes(janela)) == len(inicio) - 1

    janela.pagina.desfazedor.desfazer()                    # volta o descartado
    assert len(boxes(janela)) == len(inicio)
    janela.pagina.desfazedor.desfazer()                    # desfaz a divisão: o par colado volta
    assert len(boxes(janela)) == len(inicio) - 1
    janela.pagina.desfazedor.desfazer()                    # desfaz a junção
    assert _caixas(boxes(janela)) == inicio
    # O que sobra é o próprio F5, que também se desfaz.
    assert janela.acao_desfazer.text() == "Desfazer: Reconhecer a página"


def test_alt_seta_seguidos_se_desfazem_de_uma_vez(app, janela):
    inicio = _reconhecida(app, janela)
    mostrar(janela, 0)
    for _ in range(3):
        janela.treino.pedir_ajustar(0, 0, 1, 0)
    janela.pagina.desfazedor.desfazer()
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
    janela.pagina.desfazedor.desfazer()
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
    from tests.ajudantes import pdf_sintetico  # noqa: E402,F401,F811

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
        j.pagina.desfazedor.desfazer()                           # na página 1, desfaz a da página 0
        assert j.pagina.indice == 0 and boxes(j)[0].char != "Z"
        j.pagina.desfazedor.refazer()
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
    janela.pagina.desfazedor.desfazer()
    assert avisos and "Não dá para desfazer" in avisos[0] and "Nada foi mudado" in avisos[0]
    assert modelo.boxes == antes and janela.acao_desfazer.text() == "Desfazer: Corrigir para 'Z'"
    ed.corrigir(modelo, modelo.boxes[0].gid, "Z")      # outro objeto, igual ao "depois"
    janela.pagina.desfazedor.desfazer()
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
    janela.pagina.desfazedor.desfazer()
    assert _caixas(boxes(janela)) == inicio and janela.leitor.padroes_por_caractere() == {}


def test_desfazer_com_a_propagacao_rodando_descarta_o_resultado_dela(app, janela, monkeypatch):
    inicio = _reconhecida(app, janela)
    solto = _propagacao_presa(monkeypatch)
    mostrar(janela, 0)
    janela.treino.campo.setText("a")
    janela.treino.pedir_ensinar()
    assert boxes(janela)[0].source == FONTE_MANUAL       # a parte síncrona, na hora
    assert janela.executor.ocupado                        # a propagação, presa
    janela.pagina.desfazedor.desfazer()                              # roda na hora, com ela presa
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
    janela.pagina.desfazedor.desfazer()                              # o "b" e a propagação dele
    janela.pagina.desfazedor.desfazer()                              # o "a" e a propagação dele
    assert janela.leitor.padroes_por_caractere() == {}
    assert _caixas(boxes(janela)) == inicio               # e a página volta inteira


def test_desfazer_e_refazer_uma_area(app, janela):
    janela.areas.desenhar(10, 10, 300, 120)
    criada = janela.areas.zonas
    assert len(criada) == 1 and criada[0].id            # o id nasceu com ela
    janela.pagina.desfazedor.desfazer()
    assert janela.areas.zonas == []
    janela.pagina.desfazedor.refazer()
    assert janela.areas.zonas == criada
    janela.projeto.paginas_em_memoria.descarregar(5)
    assert janela.projeto.carregar_zonas(0) == criada


def test_desfazer_depois_de_a_pagina_sair_da_memoria(app, tmp_path, monkeypatch):
    """A página relida do disco tem objetos novos: a pré-condição compara por valor."""
    from PySide6.QtWidgets import QMessageBox

    from abbychess import pagina as pg
    from abbychess.app.janela import JanelaPrincipal
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro
    from tests.ajudantes import pdf_sintetico  # noqa: E402,F401,F811

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
        projeto.paginas_em_memoria.descarregar(5)
        projeto.paginas_em_memoria._modelos.pop(0)     # como se 16 páginas tivessem passado
        j.pagina.desfazedor.desfazer()
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
    janela.pagina.desfazedor.desfazer()                            # recusa, e "sim": tira a ação
    assert janela.acao_desfazer.text() == "Desfazer: Corrigir para 'Q'"
    janela.pagina.desfazedor.desfazer()                            # e a anterior volta
    assert boxes(janela)[1].char != "Q" and boxes(janela)[0].char == "W"


def test_reler_pendentes_entra_no_desfazer(app, janela):
    inicio = _reconhecida(app, janela)
    mostrar(janela, 0)
    janela.treino.campo.setText("a")
    janela.treino.pedir_ensinar()
    _esperar(app, janela)
    janela.pagina.desfazedor.desfazer()                            # o Enter e a propagação saem
    janela.leitor.padroes.restaurar_varios(janela.pagina.historico.proxima_a_refazer()
                                           .amostras_criadas[:1])  # o padrão volta por fora
    janela.pagina.leitura.reler_pendentes()
    _esperar(app, janela)
    assert janela.acao_desfazer.text() == "Desfazer: Reler pendentes"
    janela.pagina.desfazedor.desfazer()
    assert _caixas(boxes(janela)) == inicio


def test_refazer_um_enter_desfeito_na_propagacao_propaga_de_novo(app, janela, monkeypatch):
    _reconhecida(app, janela)
    solto = _propagacao_presa(monkeypatch)
    mostrar(janela, 0)
    janela.treino.campo.setText("a")
    janela.treino.pedir_ensinar()
    janela.pagina.desfazedor.desfazer()                            # com a propagação presa
    solto.set()
    _esperar(app, janela)
    janela.pagina.desfazedor.refazer()                             # refaz e propaga de novo
    _esperar(app, janela)
    assert sum(b.source == FONTE_LIVRO for b in boxes(janela)) == 4
    janela.pagina.desfazedor.desfazer()                            # e o desfazer leva as duas coisas
    assert not any(b.source in (FONTE_LIVRO, FONTE_MANUAL) for b in boxes(janela))


def test_refazer_noutra_pagina_abre_a_do_enter_e_propaga(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from abbychess import pagina as pg
    from abbychess.app.janela import JanelaPrincipal
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro
    from tests.ajudantes import pdf_sintetico  # noqa: E402,F401,F811

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
        j.pagina.desfazedor.desfazer()                             # com a propagação presa
        solto.set()
        _esperar(app, j)
        j.ir_para_pagina(1)
        j.pagina.desfazedor.refazer()                              # da página 1
        _esperar(app, j)
        assert j.pagina.indice == 0
        assert sum(b.source == FONTE_LIVRO for b in boxes(j)) >= 1   # propagou de novo
    finally:
        j.close()


# ----------------------------------------------------------------------
# As regras que a mutação achou sem teste (Q9, CA-Q-M1)
# ----------------------------------------------------------------------

def _registrada(transacao, limite=hs.LIMITE_DE_MEMORIA):
    h = hs.HistoricoDoProjeto(limite)
    h.registrar(transacao)
    return h


def _desfazer(m, pagina):
    hs.conferir(m, pagina, para_tras=True)
    hs.aplicar(m, pagina, para_tras=True)


def test_o_desfazer_guarda_ate_50_mb():
    """SPEC §14.2: o desfazer do projeto vai até 50 MB."""
    assert hs.HistoricoDoProjeto().limite == 50 * 2**20


def test_a_estimativa_de_memoria_de_cada_parte_da_transacao():
    """O limite conta a estimativa do histórico (`bytes`): 600 bytes por glifo guardado, no
    antes e no depois; 5 × 32 pelos vizinhos de cada um que sai ou nasce; 36 por gid de uma
    ordem refeita; o valor e 4000 por item de um campo; 96 por página da sequência; 600 por
    glifo e 4000 por página trocada inteira; 64 por gid movido; e o PNG das amostras."""
    import sys
    from pathlib import Path

    from abbychess import edicao as ed
    from abbychess.modelo import RECONHECIDA
    from abbychess.padroes import Amostra
    from abbychess.sequencia import Sequencia

    p = _pagina("abcd")
    corrigidos = _transacao(p, lambda pg: [ed.corrigir(pg, b.gid, "z") for b in pg.boxes[:2]])
    assert _registrada(corrigidos).bytes == 2 * 2 * 600
    apagado = _transacao(p, lambda pg: ed.descartar(pg, pg.boxes[1].gid))
    assert _registrada(apagado).bytes == 2 * 600 + 5 * 32
    novo = Box((1 << 20) | 9, BoxEntry("x", 50, 0, 58, 9))
    nascido = _transacao(p, lambda pg: setattr(pg, "boxes", pg.boxes + [novo]))
    assert _registrada(nascido).bytes == 2 * 600 + 5 * 32
    # z c d x -> c z x: o "d" sai e a ordem muda (4 gids antes, 3 depois).
    reordenado = _transacao(p, lambda pg: setattr(pg, "boxes", [pg.boxes[1], pg.boxes[0],
                                                                pg.boxes[3]]))
    assert _registrada(reordenado).bytes == 2 * 600 + 5 * 32 + (4 + 3) * 36
    estado = p.estado
    reconhecida = _transacao(p, lambda pg: setattr(pg, "estado", RECONHECIDA))
    assert _registrada(reconhecida).bytes == sum(sys.getsizeof(v) + 4000
                                                 for v in (estado, RECONHECIDA))

    livro = Sequencia.do_livro([1, 2, 3])
    apagar = hs.Transacao("Apagar a página 2", sequencia=(livro, livro.apagar([2])))
    assert _registrada(apagar).bytes == (3 + 0 + 2 + 1) * 96
    dividir = hs.Transacao("Dividir a página", inteiras={2: (None, _pagina("abc", pid=2))},
                           movidos=({"1": 5}, {"1": 5, "2": 6}))
    assert _registrada(dividir).bytes == 3 * 600 + 4000 + (1 + 2) * 64
    ensinar = hs.Transacao("Ensinar", amostras_criadas=[Amostra(Path("a.png"), b"a" * 100, {})],
                           amostras_apagadas=[Amostra(Path("b.png"), b"b" * 30, {})])
    assert _registrada(ensinar).bytes == 130


def test_a_transacao_que_cresce_e_medida_de_novo_sem_contar_duas_vezes():
    """A propagação emendada e os Alt+seta juntados refazem a estimativa da transação (não
    a somam à de antes); a propagação que chega depois de a transação sair não conta."""
    from abbychess import edicao as ed

    p = _pagina()
    h = hs.HistoricoDoProjeto()
    t = h.registrar(_transacao(p, lambda pg: ed.corrigir(pg, pg.boxes[0].gid, "z")))
    foto = p.instantaneo()
    ed.corrigir(p, p.boxes[1].gid, "y")                # o que a propagação resolveu
    hs.emendar(t.paginas[1], hs.mudanca(foto, p.instantaneo()))
    h.emendou(t)
    assert h.bytes == 2 * 2 * 600
    for c in "xw":
        h.registrar(_transacao(p, lambda pg, c=c: ed.corrigir(pg, pg.boxes[2].gid, c),
                               juntar=("ajustar", 3)))
    assert h.passos == 2 and h.bytes == 2 * 2 * 600 + 2 * 600
    h.descartar_desfazer()
    h.descartar_desfazer()
    h.emendou(t)                                       # já fora do desfazer
    assert h.bytes == 0


def test_a_ultima_transacao_fica_mesmo_maior_que_o_limite():
    from abbychess import edicao as ed

    p = _pagina()
    h = hs.HistoricoDoProjeto(limite=1)
    for c in "zy":
        h.registrar(_transacao(p, lambda pg, c=c: ed.corrigir(pg, pg.boxes[0].gid, c),
                               f"Corrigir para '{c}'"))
    assert h.passos == 1 and h.proximo_a_desfazer == "Corrigir para 'y'"


def test_o_lote_ve_as_paginas_que_o_desfazer_ou_o_refazer_mudam():
    """O lote não grava por cima de uma página que o Ctrl+Z ou o Ctrl+Y mudariam (§11); a
    ação tirada do refazer e o histórico limpo não a seguram mais."""
    from abbychess import edicao as ed

    p = _pagina()
    h = hs.HistoricoDoProjeto()
    assert not h.toca(1)
    h.registrar(_transacao(p, lambda pg: ed.corrigir(pg, pg.boxes[0].gid, "z")))
    assert h.toca(1) and not h.toca(2)
    h.desfeita()
    assert h.toca(1)                                   # no refazer
    h.descartar_refazer()
    assert not h.toca(1) and h.proximo_a_refazer is None and h.bytes == 0
    h.descartar_refazer()                              # sem nada para tirar
    h.registrar(_transacao(p, lambda pg: ed.corrigir(pg, pg.boxes[1].gid, "y")))
    h.limpar()
    assert h.passos == 0 and h.bytes == 0 and not h.toca(1)


def test_a_versao_da_pagina_nunca_volta_a_um_valor_que_ja_teve():
    """O lote compara a versão da página antes e depois de ler (§11): cada mudança, por
    dentro ou por fora do desfazer, dá uma versão que a página nunca teve; a das outras
    páginas não muda."""
    from abbychess import edicao as ed

    p = _pagina()
    h = hs.HistoricoDoProjeto()
    vistas, outra = [h.versao(1)], h.versao(2)
    h.tocar(1)
    vistas.append(h.versao(1))
    t = h.registrar(_transacao(p, lambda pg: ed.corrigir(pg, pg.boxes[0].gid, "z")))
    vistas.append(h.versao(1))
    for mudar in (lambda: h.tocar(1), h.desfeita, h.refeita, lambda: h.emendou(t)):
        mudar()
        vistas.append(h.versao(1))
    assert len(set(vistas)) == len(vistas) == 7 and h.versao(2) == outra


def test_o_glifo_que_a_transacao_criou_ou_apagou_e_mudou_por_fora_recusa():
    from abbychess import edicao as ed

    p = _pagina(pid=2)                                 # a página 2 do livro
    novo = Box((2 << 20) | 9, BoxEntry("x", 40, 0, 48, 9))
    m = _transacao(p, lambda pg: setattr(pg, "boxes", pg.boxes + [novo])).paginas[2]
    p.boxes = p.boxes[:-1]                             # o glifo novo saiu por fora
    with pytest.raises(hs.Recusa) as recusa:
        hs.conferir(m, p, para_tras=True)
    assert str(recusa.value) == ("1 glifo(s) da página 2 mudaram depois (por outra ação, que "
                                 "não passou por este desfazer)")
    apagado = p.boxes[0]
    m = _transacao(p, lambda pg: ed.descartar(pg, apagado.gid)).paginas[2]
    p.boxes = [apagado] + p.boxes                      # e o apagado voltou por fora
    with pytest.raises(hs.Recusa):
        hs.conferir(m, p, para_tras=True)


def test_a_leitura_que_chega_depois_nao_impede_o_desfazer():
    """§11: o glifo novo fica aguardando leitura, e o servidor o lê depois, fora do desfazer.
    A leitura não é decisão de ninguém: o Ctrl+Z ainda tira o glifo. A leitura manual, a que
    mexeu na caixa e a releitura de um glifo que já estava lido são outra ação: recusam."""
    from abbychess import edicao as ed

    casos = [("", dict(char="x", source=FONTE_LIVRO), True),
             ("", dict(char="x", source=FONTE_MANUAL), False),
             ("", dict(char="x", source=FONTE_LIVRO, x2=49), False),
             ("x", dict(char="y", source=FONTE_LIVRO), False)]
    for char, leitura, aceita in casos:
        p = _pagina()
        inicial = list(p.boxes)
        novo = Box((1 << 20) | 9, BoxEntry(char, 40, 0, 48, 9, 1.0, FONTE_LIVRO if char else ""))
        m = _transacao(p, lambda pg: setattr(pg, "boxes", pg.boxes + [novo])).paginas[1]
        lido = ed.copia(novo.entry)
        for campo, valor in leitura.items():
            setattr(lido, campo, valor)
        antes = tuple(p.boxes)
        ed.aplicar_leituras(p, antes, [lido if b is novo else b.entry for b in antes])
        assert p.boxes[-1].entry.char == leitura["char"]
        if aceita:
            _desfazer(m, p)
            assert p.boxes == inicial
        else:
            with pytest.raises(hs.Recusa):
                hs.conferir(m, p, para_tras=True)


def test_emendar_guarda_o_lugar_do_glifo_do_enter_que_a_propagacao_descartou():
    """O Enter corrige o "b", e a propagação o descarta e corrige o "c": desfazer devolve o
    "b" no lugar dele (não no começo da página) e o "c" como era."""
    from abbychess import edicao as ed

    p = _pagina("abcd")
    inicial = list(p.boxes)
    t = _transacao(p, lambda pg: ed.corrigir(pg, pg.boxes[1].gid, "z"))
    foto = p.instantaneo()
    ed.descartar(p, p.boxes[1].gid)
    ed.corrigir(p, p.boxes[1].gid, "y")                # agora o "c"
    hs.emendar(t.paginas[1], hs.mudanca(foto, p.instantaneo()))
    m = t.paginas[1]
    _desfazer(m, p)
    assert p.boxes == inicial
    hs.conferir(m, p, para_tras=False)
    hs.aplicar(m, p, para_tras=False)
    assert [b.entry.char for b in p.boxes] == ["a", "y", "d"]


def test_desfazer_a_ordem_refeita_guarda_os_glifos_de_uma_edicao_feita_depois():
    """Marcar um quadro refaz a ordem da página; desfazer a devolve, e os glifos que outra
    ação pôs depois ficam: o do meio logo depois de quem vinha antes dele, o do começo no
    começo."""
    p = _pagina("abcd")
    novo = Box((1 << 20) | 9, BoxEntry("x", 0, 50, 8, 59))
    m = _transacao(p, lambda pg: setattr(pg, "boxes", [pg.boxes[2], pg.boxes[0], novo,
                                                       pg.boxes[3]])).paginas[1]
    c, a, x, d = p.boxes
    w, z = (Box((1 << 20) | k, BoxEntry(char, 0, 70, 8, 79)) for k, char in ((10, "w"), (11, "Z")))
    p.boxes = [w, c, a, z, x, d]                       # por fora
    _desfazer(m, p)
    assert [b.entry.char for b in p.boxes] == ["w", "a", "b", "Z", "c", "d"]


def test_desfazer_devolve_na_ordem_os_glifos_que_o_enter_e_a_propagacao_descartaram():
    """O Enter descarta o "e", e a propagação, os três antes dele: desfazer devolve cada um
    depois do vizinho dele, a começar do mais perto do "a" (o "e" guardou só os três
    vizinhos, e nenhum deles estaria na página se ele voltasse primeiro)."""
    from abbychess import edicao as ed

    p = _pagina("abcdef")
    inicial = list(p.boxes)
    t = _transacao(p, lambda pg: ed.descartar(pg, pg.boxes[4].gid))
    foto = p.instantaneo()
    for gid in [b.gid for b in p.boxes[1:4]]:
        ed.descartar(p, gid)
    hs.emendar(t.paginas[1], hs.mudanca(foto, p.instantaneo()))
    _desfazer(t.paginas[1], p)
    assert p.boxes == inicial
