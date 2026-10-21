r"""As metas do servidor de leitura (SPEC §11, passo E), com o leitor real no filho.

    .venv\Scripts\python.exe -m pytest -q -m desempenho tests\desempenho

- CA-11.1 [desempenho]: o atraso de um `QTimer` de 16 ms durante um lote de 20 páginas;
- CA-11.6: a memória total (a interface mais o servidor) com o lote rodando;
- CA-11.7: a releitura de um glifo com o lote rodando (do Alt+seta ao glifo lido).

A janela usa o projeto como a abertura com servidor: o leitor da interface só com os padrões
do livro, e o filho com a rede e a base global (a fábrica de verdade). Sem o livro de
referência, pula (no portão, falha, pelo marcador `livro_real`).
"""

from __future__ import annotations

import os
import time

import pytest

from tests.desempenho.conftest import cronometrar, p95, percentil
from tests.livros import PASTA_DOS_PDFS

pytestmark = [pytest.mark.desempenho, pytest.mark.livro_real, pytest.mark.timeout(1800)]

_PDF = sorted(PASTA_DOS_PDFS.glob("Xadrez Vitorioso*/*.pdf"))
ABERTA = 20
LOTE = list(range(21, 41))          # 20 páginas para o atraso e a memória total (§15.3)
LOTE_DA_RELEITURA = list(range(41, 61))
#: As páginas lidas pelo lote com o servidor e depois sem ele, no mesmo projeto e com os
#: mesmos padrões (as do LOTE, já lidas uma vez: o "refazer").
LOTE_DA_COMPARACAO = list(range(21, 26))


def _ate(app, condicao, limite: float) -> None:
    fim = time.monotonic() + limite
    while not condicao() and time.monotonic() < fim:
        app.processEvents()
        time.sleep(0.002)
    app.processEvents()
    assert condicao(), "a condição não chegou no prazo"


@pytest.fixture(scope="module")
def ambiente(tmp_path_factory):
    if not _PDF:
        pytest.skip("o PDF do Xadrez Vitorioso não está nesta máquina")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    indice_paralelo = os.environ.get("ABBY_INDICE_PARALELO")
    os.environ["ABBY_INDICE_PARALELO"] = "1"            # o índice da busca como no programa
    from PySide6.QtWidgets import QApplication, QMessageBox

    from abbychess import pagina as pg
    from abbychess import servidor_de_leitura as sl
    from abbychess.app.janela import JanelaPrincipal
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro

    app = QApplication.instance() or QApplication([])
    pergunta_original = QMessageBox.question
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    projeto = ProjetoDeLivro.criar(tmp_path_factory.mktemp("livros"), "Servidor", _PDF[0])
    limiares = projeto.dados.limiares
    servidor = sl.ServidorDeLeitura(projeto.pasta_de_padroes, limiares,
                                    fabrica=sl.FABRICA_PADRAO)
    assert servidor.pronto.wait(300), "o servidor não carregou os modelos"
    janela = JanelaPrincipal()
    janela.resize(1600, 1000)
    janela.usar(projeto, pg.fonte_do_projeto(projeto),
                LeitorDoLivro(projeto.pasta_de_padroes, limiares=limiares, aguardar=True),
                servidor)
    janela.ir_para_pagina(ABERTA)
    janela.reconhecer()                                  # a página aberta, pelo servidor
    _ate(app, lambda: not janela.executor.ocupado, 120)
    yield app, janela
    janela.close()
    QMessageBox.question = pergunta_original
    if indice_paralelo is None:
        os.environ.pop("ABBY_INDICE_PARALELO", None)
    else:
        os.environ["ABBY_INDICE_PARALELO"] = indice_paralelo


def _rss_mb(processos) -> float:
    total = 0
    for processo in processos:
        try:
            total += processo.memory_info().rss
        except Exception:  # o filho saiu no meio da leitura: conta o que sobrou
            pass
    return total / 2**20


def test_atraso_e_memoria_durante_o_lote(ambiente, medidas):
    """Um QTimer de 16 ms durante um lote de 20 páginas pelo servidor: o atraso e o pico da
    memória somada (a interface e o filho)."""
    import psutil
    from PySide6.QtCore import QTimer

    app, janela = ambiente
    processos = [psutil.Process(), psutil.Process(janela.pagina.servidor.pid)]
    atrasos, instantes, rss = [], [], []
    ultimo = [time.perf_counter()]

    def tique():
        agora = time.perf_counter()
        atrasos.append((agora - ultimo[0]) * 1000 - 16)
        instantes.append(agora)
        ultimo[0] = agora
        rss.append(_rss_mb(processos))

    from abbychess import lote

    gravacoes, gravar_original = [], lote.CondutorDoLote._gravar

    def gravar(self, indice, lida):                      # quanto a janela gasta em cada página
        inicio_da_pagina = time.perf_counter()
        gravar_original(self, indice, lida)
        gravacoes.append((inicio_da_pagina, (time.perf_counter() - inicio_da_pagina) * 1000))

    temporizador = QTimer()
    temporizador.setInterval(16)
    temporizador.timeout.connect(tique)
    # CA-11.1 com a busca no roteiro (passo B): uma busca a cada 2 s durante o lote, alternando
    # dois textos (cada uma refaz no índice as páginas que o lote já gravou).
    buscas, textos = [], ["e", "casa"]

    def buscar():
        janela.localizar()
        janela.barra_de_busca.campo.setText(textos[len(buscas) % 2])
        janela.barra_de_busca.relogio.stop()
        janela._buscar()
        buscas.append(time.perf_counter())

    relogio_da_busca = QTimer()
    relogio_da_busca.setInterval(2000)
    relogio_da_busca.timeout.connect(buscar)
    lote.CondutorDoLote._gravar = gravar
    temporizador.start()
    relogio_da_busca.start()
    inicio = time.perf_counter()
    try:
        janela.livro.reconhecer(LOTE, refazer=True)      # o caminho do menu, sem o diálogo
        _ate(app, lambda: not janela.livro.lote_rodando, 1500)
    finally:
        fim = time.perf_counter()
        temporizador.stop()
        relogio_da_busca.stop()
        lote.CondutorDoLote._gravar = gravar_original
    k = max(range(len(atrasos)), key=atrasos.__getitem__)
    perto = min(gravacoes, key=lambda g: abs(g[0] - instantes[k]))
    tempos_de_gravar = [ms for _, ms in gravacoes]
    medidas["atraso_durante_o_lote"] = {
        "paginas": len(LOTE), "p99_ms": round(percentil(atrasos, 0.99), 1),
        "p95_ms": round(p95(atrasos), 1), "max_ms": round(max(atrasos), 1),
        "disparos": len(atrasos), "duracao_s": round(fim - inicio, 1),
        "alvo_p99_ms": 50,
        "acoes_durante_o_lote": "todas valem (passo E): o lote lê no servidor e grava na "
                                "interface entre um comando e outro; desde o B, uma busca a "
                                "cada 2 s (Localizar) durante o lote",
        "buscas_durante_o_lote": len(buscas),
        "maior_atraso": {"ms": round(atrasos[k], 1),
                         "segundos_da_gravacao_mais_perto": round(instantes[k] - perto[0], 3),
                         "gravacao_mais_perto_ms": round(perto[1], 1)},
        "como": "pelo servidor de leitura (desde o E): a leitura no filho, com a prioridade "
                "abaixo do normal; a interface reconcilia e entrega cada página ao gravador. "
                "Até o A3, o lote lia numa thread do processo da interface"}
    medidas["gravar_pagina_do_lote"] = {
        "p50_ms": round(percentil(tempos_de_gravar, 0.5), 1),
        "p95_ms": round(p95(tempos_de_gravar), 1), "max_ms": round(max(tempos_de_gravar), 1),
        "n": len(tempos_de_gravar),
        "como": "o que a janela faz com cada página que volta do servidor (a cópia de antes, "
                "reconciliar os gids, o resumo, entregar ao gravador), na thread da interface"}
    medidas["memoria_total_com_o_lote"] = {
        "rss_pico_mb": round(max(rss)) if rss else None, "alvo_mb": 2560,
        "interface_no_fim_mb": round(_rss_mb(processos[:1])),
        "servidor_no_fim_mb": round(_rss_mb(processos[1:])),
        "como": f"pico da soma do RSS da interface e do servidor durante um lote de "
                f"{len(LOTE)} páginas (desde o E, dois processos)"}


def test_releitura_de_um_glifo_com_o_lote_rodando(ambiente, medidas):
    """CA-11.7: do Alt+seta num glifo (a borda muda e a interface não o lê: os padrões do
    livro estão vazios) até a leitura do servidor chegar, com o lote lendo outras páginas."""
    from abbychess import pagina as pg

    app, janela = ambiente
    p = janela.pagina
    gid = next(b.gid for b in p.modelo.boxes if b.entry.x2 - b.entry.x1 >= 8)
    janela.livro.reconhecer(LOTE_DA_RELEITURA, refazer=True)
    _ate(app, lambda: janela.livro._condutor is not None
         and janela.livro._condutor.em_leitura is not None, 60)
    sentido = [1]

    def preparar(_i):
        p.escolher(gid)

    def reler(_i):
        sentido[0] = -sentido[0]
        p.ajustar(0, 0, sentido[0], 0)                   # a borda direita, ±1 px
        _ate(app, lambda: not pg.aguardando(p.box(gid)), 30)

    resultado = cronometrar(reler, antes=preparar)
    ainda_no_lote = janela.livro.lote_rodando
    janela.livro.cancelar()
    _ate(app, lambda: not janela.livro.lote_rodando, 600)
    medidas["releitura_com_o_lote"] = {
        **resultado, "alvo_p95_ms": 150, "lote_rodando_no_fim": ainda_no_lote,
        "como": "Alt+→/← alternados num glifo da página aberta: a interface o deixa "
                "aguardando e o servidor o lê entre um glifo e outro do lote (de outras "
                "páginas); do comando ao glifo lido, com o laço de eventos girando"}


def test_lote_com_e_sem_servidor(ambiente, medidas):
    """As mesmas páginas, o mesmo projeto e os mesmos padrões: o tempo de cada página pelo
    lote com o servidor, e lida na própria janela (o `sl.ler_pagina` com o leitor real
    carregado aqui; o último teste do módulo, porque os modelos ficam no processo)."""
    from abbychess import lote
    from abbychess import servidor_de_leitura as sl

    app, janela = ambiente
    p = janela.pagina
    tempos = []
    original = lote.CondutorDoLote._voltou

    def voltou(self, pedida, resultado):
        tempos.append(time.perf_counter() - pedida.inicio)
        original(self, pedida, resultado)

    lote.CondutorDoLote._voltou = voltou
    try:
        janela.livro.reconhecer(LOTE_DA_COMPARACAO, refazer=True)
        _ate(app, lambda: not janela.livro.lote_rodando, 900)
    finally:
        lote.CondutorDoLote._voltou = original
    leitor = sl.leitor_global(p.projeto.pasta_de_padroes, p.projeto.dados.limiares)
    sem = []
    for indice in LOTE_DA_COMPARACAO:
        inicio = time.perf_counter()
        sl.ler_pagina(p.fonte.pagina(indice), [], [], leitor)
        sem.append(time.perf_counter() - inicio)
    medidas["lote_com_e_sem_servidor"] = {
        "paginas": LOTE_DA_COMPARACAO, "padroes_no_livro": leitor.total_de_padroes,
        "com_servidor_s_por_pagina": round(sum(tempos) / len(tempos), 2),
        "sem_servidor_s_por_pagina": round(sum(sem) / len(sem), 2),
        "como": "o lote com o servidor (do pedido à resposta, com a página renderizada) e "
                "`ler_pagina` na própria janela com o leitor real, nas mesmas páginas"}


def test_atraso_durante_o_lote_com_o_leitor_falso(tmp_path, medidas):
    """CA-11.1 [desempenho], primeiro com o falso: 50 páginas sintéticas (~200 ms cada)."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from abbychess import pagina as pg
    from abbychess import servidor_de_leitura as sl
    from abbychess.app.janela import JanelaPrincipal
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro
    from tests.test_livro import PAGINAS, pdf_sintetico

    app = QApplication.instance() or QApplication([])
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Falso", pdf_sintetico(tmp_path,
                                                                                PAGINAS * 17))
    limiares = projeto.dados.limiares
    servidor = sl.ServidorDeLeitura(projeto.pasta_de_padroes, limiares,
                                    fabrica="tests.leitor_falso:criar")
    assert servidor.pronto.wait(60)
    janela = JanelaPrincipal()
    janela.usar(projeto, pg.FonteDePaginas(projeto.fonte),
                LeitorDoLivro(projeto.pasta_de_padroes, limiares=limiares, aguardar=True),
                servidor)
    atrasos, ultimo = [], [time.perf_counter()]

    def tique():
        agora = time.perf_counter()
        atrasos.append((agora - ultimo[0]) * 1000 - 16)
        ultimo[0] = agora

    temporizador = QTimer()
    temporizador.setInterval(16)
    temporizador.timeout.connect(tique)
    buscas = []                                         # desde o B, como no real

    def buscar():
        janela.localizar()
        janela.barra_de_busca.campo.setText(("e", "casa")[len(buscas) % 2])
        janela.barra_de_busca.relogio.stop()
        janela._buscar()
        buscas.append(time.perf_counter())

    relogio_da_busca = QTimer()
    relogio_da_busca.setInterval(2000)
    relogio_da_busca.timeout.connect(buscar)
    temporizador.start()
    relogio_da_busca.start()
    inicio = time.perf_counter()
    try:
        janela.livro.reconhecer(list(range(51)), refazer=False)
        _ate(app, lambda: not janela.livro.lote_rodando, 600)
    finally:
        temporizador.stop()
        relogio_da_busca.stop()
        duracao = time.perf_counter() - inicio
        janela.close()
    medidas["atraso_durante_o_lote_falso"] = {
        "paginas": 51, "p99_ms": round(percentil(atrasos, 0.99), 1),
        "p95_ms": round(p95(atrasos), 1), "max_ms": round(max(atrasos), 1),
        "disparos": len(atrasos), "duracao_s": round(duracao, 1), "alvo_p99_ms": 50,
        "buscas_durante_o_lote": len(buscas),
        "como": "o lote de 51 páginas sintéticas pelo servidor com o leitor falso (10 ms por "
                "glifo, ~200 ms por página): a janela grava uma página a cada ~200 ms; desde o "
                "B, uma busca a cada 2 s (Localizar) durante o lote"}

