"""O servidor de leitura ligado à janela (SPEC §11): a abertura, o F5, os glifos aguardando,
os deltas dos padrões, a queda, o fechamento e o lote (CA-11.1 a CA-11.4).

A janela abre o projeto como pela linha de comando, com o servidor ligado
(`ABBY_SERVIDOR=1`) e o leitor falso no filho (`tests/leitor_falso.py`: tudo o que ele lê
sai "x", fonte `neural`). Assim o teste sabe que a leitura veio do servidor.
"""

from __future__ import annotations

import json
import time

import pytest

from abbychess import pagina as pg
from abbychess.app.janela import JanelaPrincipal

from tests import leitor_falso
from tests.janela_util import boxes
from tests.test_janela import _esperar, app  # noqa: F401 (fixture)
from tests.test_janela_persistencia import projeto_lido, sem_dialogos  # noqa: F401 (fixtures)
from tests.test_livro import PAGINAS, pdf_sintetico

pytestmark = pytest.mark.processo


def _ate(app, condicao, limite=60.0):  # noqa: F811
    fim = time.monotonic() + limite
    while not condicao() and time.monotonic() < fim:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    assert condicao(), "a condição não chegou no prazo"


@pytest.fixture
def janela(app, projeto_lido, sem_dialogos, monkeypatch):  # noqa: F811
    monkeypatch.setenv("ABBY_SERVIDOR", "1")
    monkeypatch.setenv("ABBY_FABRICA_DE_LEITOR", "tests.leitor_falso:criar")
    janela = JanelaPrincipal()
    janela.prontos = []
    janela.eventos.ligar("modelos_prontos", janela.prontos.append)
    janela.abrir_caminho(str(projeto_lido.pasta))
    _esperar(app, janela)
    _ate(app, lambda: janela.prontos)
    yield janela
    janela.close()


def test_a_abertura_liga_o_servidor_e_o_f5_le_por_ele(app, janela):  # noqa: F811
    p = janela.pagina
    assert p.servidor is not None and p.servidor.pronto.is_set()
    assert p.leitor.ocr is None and p.leitor.aguardar          # a interface não tem modelos
    assert janela.prontos == [{"rede": False, "base": 0}]       # o falso não tem rede
    janela.reconhecer()
    _esperar(app, janela)
    assert boxes(janela)
    assert {(b.char, b.source) for b in boxes(janela)} == {(leitor_falso.LETRA, leitor_falso.FONTE)}


def test_o_glifo_marcado_fica_aguardando_e_recebe_a_leitura_do_servidor(app, janela):  # noqa: F811
    p = janela.pagina
    janela.reconhecer()
    _esperar(app, janela)
    antes = len(boxes(janela))
    b = boxes(janela)[0]
    vistos = []
    janela.eventos.ligar("glifos_mudaram", lambda gids: vistos.append(
        [pg.aguardando(x) for x in p.boxes]))
    p.marcar(b.x1 - 1, b.y1 - 1, b.x2 + 1, b.y2 + 1)
    assert any(any(v) for v in vistos)                         # desenhado como aguardando
    _esperar(app, janela)
    marcado = p.box(p.atual)
    assert (marcado.char, marcado.source) == (leitor_falso.LETRA, leitor_falso.FONTE)
    assert not any(pg.aguardando(x) for x in p.boxes)
    p.desfazer()                                               # o quadro e a leitura: um passo
    assert len(boxes(janela)) == antes and p.historico.proxima_a_desfazer().descricao \
        == "Reconhecer a página"


def test_o_padrao_ensinado_vai_ao_servidor_antes_do_pedido_seguinte(app, janela):  # noqa: F811
    p = janela.pagina
    janela.reconhecer()
    _esperar(app, janela)
    p.escolher(p.gids[0])
    p.ensinar("a")
    _esperar(app, janela)
    assert len(p.padroes()) == 1
    assert p.servidor.chamar("padroes", timeout=10) == 1        # CA-11.2: o delta chegou
    p.desfazer()                                               # o desfazer apaga a amostra
    _esperar(app, janela)
    assert p.servidor.chamar("padroes", timeout=10) == 0


def test_a_primeira_queda_vai_aos_avisos_e_a_segunda_oferece_reabrir(app, janela,  # noqa: F811
                                                                    sem_dialogos):  # noqa: F811
    p = janela.pagina
    primeiro = p.servidor
    primeiro.processo.kill()
    _ate(app, lambda: any(a.titulo == "Servidor de leitura" for a in janela.avisos.itens))
    assert primeiro.reinicios == 1 and not primeiro.desistiu
    _ate(app, lambda: primeiro.pronto.is_set())
    janela.reconhecer()                                        # o reaberto lê
    _esperar(app, janela)
    assert {b.char for b in boxes(janela)} == {leitor_falso.LETRA}

    janela.prontos.clear()
    primeiro.processo.kill()                                   # a segunda: desiste
    _ate(app, lambda: p.servidor is not primeiro and p.servidor is not None)
    _ate(app, lambda: janela.prontos)                          # "Sim" reabriu o projeto
    assert primeiro.desistiu and not p.servidor.desistiu


def test_fechar_a_janela_termina_o_filho_sem_deixar_orfao(app, projeto_lido,  # noqa: F811
                                                         sem_dialogos, monkeypatch):  # noqa: F811
    import psutil

    monkeypatch.setenv("ABBY_SERVIDOR", "1")
    monkeypatch.setenv("ABBY_FABRICA_DE_LEITOR", "tests.leitor_falso:criar")
    janela = JanelaPrincipal()
    janela.abrir_caminho(str(projeto_lido.pasta))
    _esperar(app, janela)
    servidor = janela.pagina.servidor
    _ate(app, servidor.pronto.is_set)
    pid = servidor.pid
    inicio = time.perf_counter()
    janela.close()
    assert time.perf_counter() - inicio <= 6
    assert janela.pagina.servidor is None
    assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE


# ----------------------------------------------------------------------
# O lote pelo servidor
# ----------------------------------------------------------------------

@pytest.fixture
def janela_do_livro(app, tmp_path, sem_dialogos, monkeypatch):  # noqa: F811
    """Um livro de 51 páginas sintéticas (~200 ms por página com o leitor falso)."""
    from abbychess.projeto import ProjetoDeLivro

    monkeypatch.setenv("ABBY_SERVIDOR", "1")
    monkeypatch.setenv("ABBY_FABRICA_DE_LEITOR", "tests.leitor_falso:criar")
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Lote",
                                   pdf_sintetico(tmp_path, PAGINAS * 17))
    pasta = projeto.pasta
    projeto.fechar()
    janela = JanelaPrincipal()
    janela.fins = []
    janela.eventos.ligar("lote_terminou", lambda mensagem, resultado: janela.fins.append(resultado))
    janela.abrir_caminho(str(pasta))
    _esperar(app, janela)
    _ate(app, janela.pagina.servidor.pronto.is_set)
    yield janela
    janela.close()


def test_ca_11_1_e_11_2_durante_o_lote_navegar_e_ensinar_valem_na_hora(app, janela_do_livro):  # noqa: F811
    j = janela_do_livro
    p = j.pagina
    j.reconhecer()                                       # a página 1, pelo servidor
    _esperar(app, j)
    j.livro.reconhecer(list(range(1, 51)), refazer=False)
    _ate(app, lambda: len(p.projeto.paginas_lidas()) >= 3)
    assert j.livro.lote_rodando and not j.executor.ocupado    # o lote não prende a fila
    p.escolher(p.gids[0])
    p.ensinar("a")                                       # o primeiro glifo é um "a"
    assert p.box(p.gids[0]).char == "a"                  # na hora, sem esperar o lote
    assert j.pagina.ir_para(1) and p.indice == 1         # navegar também
    feitas_ao_ensinar = len(p.projeto.paginas_lidas())
    _ate(app, lambda: not j.livro.lote_rodando, 180)
    [resultado] = j.fins
    assert len(resultado.lidas) + len(resultado.puladas) == 50 and not resultado.falhas
    ultima = p.projeto.carregar_modelo(50)
    # CA-11.2: as páginas começadas depois do Enter leem o "a" pelo padrão do livro.
    assert feitas_ao_ensinar < 49
    assert any(b.entry.char == "a" and b.entry.source == "livro" for b in ultima.boxes)


def test_ca_11_4_a_aberta_editada_durante_a_leitura_fica_para_reler_depois(
        app, janela_do_livro):  # noqa: F811
    j = janela_do_livro
    p = j.pagina
    j.livro.reconhecer([0], refazer=False)               # lida pelo lote: nada no desfazer
    _ate(app, lambda: not j.livro.lote_rodando, 60)
    assert j.fins[-1].lidas == [0] and boxes(j)          # a aberta aparece lida
    j.livro.reconhecer([0], refazer=True)
    assert j.livro._condutor.em_leitura == 0             # passou da conferência de antes
    p.escolher(p.gids[0])
    p.corrigir("Q")                                      # na hora: o lote está no servidor
    assert p.box(p.gids[0]).char == "Q"
    _ate(app, lambda: not j.livro.lote_rodando, 60)
    assert j.fins[-1].reler_depois == [0] and j.fins[-1].lidas == []
    assert p.box(p.gids[0]).char == "Q"
    assert any(a.titulo == "Reconhecer o livro" for a in j.avisos.itens)


def test_ca_11_3_fechar_com_o_lote_ativo_termina_o_filho_e_as_paginas_carregam(app,  # noqa: F811
                                                                             janela_do_livro):
    import psutil

    from abbychess.projeto import ProjetoDeLivro

    j = janela_do_livro
    p = j.pagina
    pasta, pid = p.projeto.pasta, p.servidor.pid
    j.livro.reconhecer(list(range(51)), refazer=False)
    _ate(app, lambda: len(p.projeto.paginas_lidas()) >= 2)
    inicio = time.perf_counter()
    j.close()
    assert time.perf_counter() - inicio <= 6
    assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    for arquivo in (pasta / "paginas").glob("p*.json"):
        json.loads(arquivo.read_text(encoding="utf-8"))  # toda página gravada carrega
    reaberto = ProjetoDeLivro.abrir(pasta)
    try:
        assert len(reaberto.paginas_lidas()) >= 2
    finally:
        reaberto.fechar()

