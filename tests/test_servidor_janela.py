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
    gid = p.atual
    _ate(app, lambda: not pg.aguardando(p.box(gid)))           # volta pelo laço de eventos
    marcado = p.box(gid)
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
    # A busca também (passo B): as páginas que o lote já leu entram nela.
    j.localizar()
    j.barra_de_busca.campo.setText("x")
    j.barra_de_busca.relogio.stop()
    j._buscar()
    _ate(app, lambda: j.busca.ultimo_resultado is not None, 30)
    assert j.busca.ultimo_resultado.ocorrencias and j.livro.lote_rodando
    _ate(app, lambda: not j.livro.lote_rodando, 180)
    [resultado] = j.fins
    assert len(resultado.lidas) + len(resultado.puladas) == 50 and not resultado.falhas
    ultima = p.projeto.carregar_modelo(50)
    # CA-11.2: as páginas começadas depois do Enter leem o "a" pelo padrão do livro.
    assert feitas_ao_ensinar < 49
    assert any(b.entry.char == "a" and b.entry.source == "livro" for b in ultima.boxes)
    # CA-4.4: o livro.json é o recalculado, com as páginas que vieram do servidor.
    assert p.projeto.descarregar(10)
    gravado = json.loads((p.projeto.pasta / "livro.json").read_text(encoding="utf-8"))
    assert gravado == p.projeto.recalcular_livro()


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


def test_o_lote_para_quando_o_servidor_desiste(app, janela_do_livro, monkeypatch):  # noqa: F811
    """Na segunda queda o servidor desiste: o lote para (as páginas seguintes falhariam todas)
    e o que faltou fica para retomar depois de reabrir o projeto."""
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    j = janela_do_livro
    p = j.pagina
    servidor = p.servidor
    j.livro.reconhecer(list(range(51)), refazer=False)
    _ate(app, lambda: len(p.projeto.paginas_lidas()) >= 1)
    servidor.processo.kill()
    _ate(app, lambda: servidor.reinicios == 1 and servidor.pronto.is_set())
    _ate(app, lambda: len(p.projeto.paginas_lidas()) >= 3)        # o lote seguiu no reaberto
    servidor.processo.kill()
    _ate(app, lambda: not j.livro.lote_rodando, 60)
    resultado = j.fins[-1]
    assert servidor.desistiu and resultado.servidor_parou and not resultado.falhas
    assert j.livro.restante is not None and len(resultado.lidas) < 51
    assert not j.livro.pode_retomar                    # “Não”: o servidor está parado


def test_a_procedencia_do_padrao_volta_do_filho_no_f5(app, janela):  # noqa: F811
    p = janela.pagina
    janela.reconhecer()
    _esperar(app, janela)
    p.escolher(p.gids[0])
    p.ensinar("a")                                       # o primeiro glifo é um "a"
    _esperar(app, janela)
    janela.reconhecer()                                  # os outros "a", pelo padrão, no filho
    _esperar(app, janela)
    pelo_livro = [b for b in p.modelo.boxes if b.entry.source == "livro"]
    assert pelo_livro and all(b.amostra for b in pelo_livro)


def test_ca_11_7_sem_servidor_pronto_o_glifo_fica_aguardando_sem_prender_a_fila(
        app, projeto_lido, sem_dialogos, monkeypatch):  # noqa: F811
    monkeypatch.setenv("ABBY_SERVIDOR", "1")
    monkeypatch.setenv("ABBY_FABRICA_DE_LEITOR", "tests.leitor_falso:criar")
    monkeypatch.setenv("ABBY_FALSO_ATRASO_AO_ABRIR", "4")
    janela = JanelaPrincipal()
    try:
        janela.abrir_caminho(str(projeto_lido.pasta))
        _esperar(app, janela)
        p = janela.pagina
        assert not p.servidor.pronto.is_set()            # os "modelos" ainda carregam
        b = p.box(p.gids[0])
        p.marcar(b.x1 - 1, b.y1 - 1, b.x2 + 1, b.y2 + 1)
        gid = p.atual
        assert pg.aguardando(p.box(gid)) and not janela.executor.ocupado
        p.escolher(p.gids[1])
        p.ensinar("b")                                   # o Enter não espera os modelos
        assert p.box(p.gids[1]).char == "b"
        _esperar(app, janela)                            # a propagação, com o "b" só
        assert pg.aguardando(p.box(gid)) and not p.servidor.pronto.is_set()
        _ate(app, p.servidor.pronto.is_set)
        _ate(app, lambda: not pg.aguardando(p.box(gid)))
        assert p.box(gid).char == leitor_falso.LETRA
    finally:
        janela.close()



def test_f3_atravessa_as_paginas_e_o_documento_vai_a_ocorrencia(app, janela_do_livro):  # noqa: F811
    """A revisão de produto do passo B (M2): a ocorrência de outra página abre no Documento já
    montado, com o cursor nela."""
    j = janela_do_livro
    j.livro.reconhecer([0, 1, 2], refazer=False)        # o leitor falso lê tudo como "x"
    _ate(app, lambda: not j.livro.lote_rodando, 60)
    j.localizar()
    j.barra_de_busca.campo.setText("x")
    j.barra_de_busca.relogio.stop()
    j._buscar()
    _ate(app, lambda: j.busca.ultimo_resultado is not None, 30)
    parado = lambda: not j.busca.buscando and not j.barra_de_busca.relogio.isActive()  # noqa: E731
    _ate(app, parado, 30)                                # (o lote rearma a busca ao gravar)
    ocorrencias = j.busca.ultimo_resultado.ocorrencias
    primeira_da_seguinte = next(o for o in ocorrencias if o.pagina != j.pagina.indice)
    for _ in range(ocorrencias.index(primeira_da_seguinte) + 1):
        j.proxima_ocorrencia()
        _ate(app, parado, 30)
    assert j.pagina.indice == primeira_da_seguinte.pagina
    assert j.texto.gid_no_cursor() == primeira_da_seguinte.gids[0]
