r"""A linha de base das metas de §2 da spec, medida na interface de hoje (passo 0).

    $env:ABBY_ROTULO_DA_MEDIDA = "linha-de-base"
    .venv\Scripts\python.exe -m pytest -q -m desempenho tests\desempenho

Só reporta: a interface de hoje não cumpre as metas, e o número dela é o que os passos
seguintes têm de bater. Usa o livro de referência (Xadrez Vitorioso) e os modelos
globais; sem eles, pula (no portão, falha, pelo marcador `livro_real`). O método é o de
§15.3: 5 aquecimentos, 30 repetições, p95.
"""

from __future__ import annotations

import gc
import os
import time

import pytest

from tests.desempenho.conftest import cronometrar, p95, percentil
from tests.livros import PASTA_DOS_PDFS
from tests.test_janela import _esperar
from tests.janela_util import atual, boxes, fila, mostrar

pytestmark = [pytest.mark.desempenho, pytest.mark.livro_real, pytest.mark.timeout(1800)]

_PDF = sorted(PASTA_DOS_PDFS.glob("Xadrez Vitorioso*/*.pdf"))
PAGINAS = [20, 21, 22]
#: As ações da medida da memória do desfazer em cada página.
ACOES_POR_PAGINA = 100
LOTE = list(range(20, 40))          # 20 páginas para a memória total (§15.3)


@pytest.fixture(scope="module")
def ambiente(tmp_path_factory):
    if not _PDF:
        pytest.skip("o PDF do Xadrez Vitorioso não está nesta máquina")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    from abbychess import livro
    from abbychess import pagina as pg
    from abbychess.app.janela import JanelaPrincipal
    from abbychess import leitor as leitor_mod
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro

    app = QApplication.instance() or QApplication([])
    pergunta_original = QMessageBox.question
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    projeto = ProjetoDeLivro.criar(tmp_path_factory.mktemp("livros"), "Linha de base", _PDF[0])
    leitor = LeitorDoLivro.com_modelos_globais(projeto.pasta_de_padroes,
                                               limiares=projeto.dados.limiares)
    fonte = pg.fonte_do_projeto(projeto)
    # Como a janela faz ao abrir (desde o 1b): logo depois de carregar os modelos, com o
    # projeto e a fonte abertos e nenhuma página lida ainda.
    congelar = getattr(leitor_mod, "congelar_para_a_coleta_de_lixo", None)
    if congelar is not None:
        congelar()
    livro.reconhecer_paginas(projeto, fonte, leitor, PAGINAS)
    janela = JanelaPrincipal()
    janela.resize(1600, 1000)
    janela.usar(projeto, fonte, leitor)
    janela.ir_para_pagina(PAGINAS[0])
    yield app, janela
    janela.close()
    QMessageBox.question = pergunta_original


def test_troca_de_pagina(ambiente, medidas):
    """De `ir_para_pagina` ao visor pintado numa QImage 1600×1000, alternando 2 páginas lidas:
    desde o A1 as duas estão no cache (a página renderizada e o pixmap)."""
    from PySide6.QtGui import QImage, QPainter

    app, janela = ambiente
    imagem = QImage(1600, 1000, QImage.Format.Format_ARGB32)

    def trocar(i):
        janela.ir_para_pagina(PAGINAS[i % 2])
        pintor = QPainter(imagem)
        janela.visor.render(pintor)
        pintor.end()

    resultado = cronometrar(trocar)
    medidas["troca_de_pagina"] = {
        **resultado, "alvo_no_cache_ms": 150,
        "como": "mesmo processo, alternando 2 páginas lidas, as duas no cache (desde o A1)"}


def test_troca_de_pagina_fora_do_cache(ambiente, medidas):
    """A mesma troca com o cache esvaziado antes de cada uma: renderizar e endireitar a
    página, convertê-la para o visor e desenhar os boxes (§2: ≤ 600 ms)."""
    from PySide6.QtGui import QImage, QPainter

    app, janela = ambiente
    imagem = QImage(1600, 1000, QImage.Format.Format_ARGB32)

    def esvaziar(_i):
        janela.pagina.cache.esperar()
        with janela.pagina.cache._trava:
            janela.pagina.cache._paginas.clear()
        janela._pixmaps.clear()

    def trocar(i):
        janela.ir_para_pagina(PAGINAS[i % 2])
        pintor = QPainter(imagem)
        janela.visor.render(pintor)
        pintor.end()

    resultado = cronometrar(trocar, antes=esvaziar, aquecimentos=2, repeticoes=12)
    medidas["troca_fora_do_cache"] = {
        **resultado, "alvo_ms": 600,
        "como": "mesmo processo, o cache de páginas e o de pixmaps esvaziados antes de cada "
                "troca (o processo novo, com a primeira carga do PDF, não está nesta medida)"}


def test_enter_ensinar(ambiente, medidas):
    """Do Enter (QTest.keyClick) até a cor do box mudar: hoje, o fim da propagação.

    Cada repetição pega o primeiro pendente da fila que tem leitura e aperta Enter com o
    caractere lido no campo: é o Enter de quem confere que a leitura está certa, o caso
    mais comum, e não ensina rótulo errado. A fila anda, então cada repetição é um glifo
    diferente, e os padrões do livro crescem como numa sessão de verdade.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    app, janela = ambiente
    janela.ir_para_pagina(PAGINAS[0])
    antes = janela.leitor.total_de_padroes
    novos: list = []

    def preparar(_i):
        pendentes = [k for k in fila(janela) if boxes(janela)[k].char]
        if not pendentes:
            janela.ir_para_pagina(PAGINAS[(PAGINAS.index(janela.pagina.indice) + 1)
                                          % len(PAGINAS)])
            pendentes = [k for k in fila(janela) if boxes(janela)[k].char]
        mostrar(janela, pendentes[0])
        char = boxes(janela)[atual(janela)].char
        novos.append(char not in janela.leitor.padroes_por_caractere())
        janela.treino.campo.setText(char)

    sincronos: list = []
    totais: list = []

    def ensinar(_i):
        inicio = time.perf_counter_ns()
        QTest.keyClick(janela.treino.campo, Qt.Key.Key_Return)   # volta com a cor mudada
        sincronos.append((time.perf_counter_ns() - inicio) / 1e6)
        _esperar(app, janela, limite=120)                       # e a propagação, na fila
        totais.append((time.perf_counter_ns() - inicio) / 1e6)

    cronometrar(ensinar, antes=preparar)
    from tests.desempenho.conftest import AQUECIMENTOS

    def resumo(tempos):
        tempos = tempos[AQUECIMENTOS:]
        import statistics

        return {"p50_ms": round(statistics.median(tempos), 2), "p95_ms": round(p95(tempos), 2),
                "max_ms": round(max(tempos), 2), "n": len(tempos)}

    resultado = resumo(sincronos)
    medidas["enter_ensinar"] = {
        **resultado, "alvo_ms": 100,
        "padroes_no_livro": [antes, janela.leitor.total_de_padroes],
        "caracteres_novos": sum(novos[-resultado["n"]:]),
        "como": "desde o 2b: QTest.keyClick(Enter) no campo, com o caractere lido do primeiro "
                "pendente (conferir a leitura), até a cor mudar (a parte síncrona: o glifo "
                "manual, a amostra gravada); a propagação vai para a fila e não entra. Até o "
                "2a, era até o fim da propagação (ver enter_ate_o_fim_da_propagacao)"}
    medidas["enter_ate_o_fim_da_propagacao"] = {
        **resumo(totais),
        "como": "o mesmo Enter, até a propagação acabar (o que o 2a media como Enter)"}


def test_enter_com_uma_propagacao_lenta_em_curso(ambiente, medidas):
    """CA-14.3 [desempenho]: com uma propagação lenta em curso (1 s injetado), a cor do
    segundo Enter muda dentro da meta (a parte síncrona não espera a propagação)."""
    import threading

    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from abbychess import pagina as pg

    app, janela = ambiente
    janela.ir_para_pagina(PAGINAS[2])
    original = pg.propagar_padroes
    solto = threading.Event()
    pg.propagar_padroes = lambda *a, **k: (solto.wait(1.0), original(*a, **k))[1]
    tempos = []
    try:
        for _ in range(10):
            pendentes = [k for k in fila(janela) if boxes(janela)[k].char]
            if len(pendentes) < 2:
                break
            mostrar(janela, pendentes[0])
            janela.treino.campo.setText(boxes(janela)[pendentes[0]].char)
            QTest.keyClick(janela.treino.campo, Qt.Key.Key_Return)   # a primeira, presa
            mostrar(janela, pendentes[1])
            janela.treino.campo.setText(boxes(janela)[pendentes[1]].char)
            inicio = time.perf_counter_ns()
            QTest.keyClick(janela.treino.campo, Qt.Key.Key_Return)   # o segundo Enter
            tempos.append((time.perf_counter_ns() - inicio) / 1e6)
            solto.set()
            _esperar(app, janela, limite=120)
            solto.clear()
    finally:
        pg.propagar_padroes = original
        solto.set()
        _esperar(app, janela, limite=120)
    medidas["enter_com_propagacao_lenta"] = {
        "p50_ms": round(percentil(tempos, 0.5), 2) if tempos else None,
        "p95_ms": round(p95(tempos), 2) if tempos else None, "n": len(tempos),
        "alvo_ms": 100,
        "como": "o segundo Enter, com a propagação do primeiro presa (1 s), até a cor mudar"}


def test_releitura_de_um_glifo(ambiente, medidas):
    """Ajustar uma borda relê o glifo com a cadeia global, na thread da interface."""
    app, janela = ambiente
    janela.ir_para_pagina(PAGINAS[1])
    mostrar(janela, 0)
    lados = [(0, 0, 1, 0), (0, 0, -1, 0)]

    resultado = cronometrar(lambda i: janela.pagina.ajustar(*lados[i % 2]))
    # O texto da página é refeito um instante depois da última mudança (desde o 2b), fora do
    # tempo acima: o que ele custa na interface, à parte.
    medidas["texto_da_pagina"] = {
        **cronometrar(lambda i: janela.pintar_texto()),
        "como": "refazer o painel de texto da página (montar o documento e pôr no painel), "
                "que desde o 2b roda 150 ms depois da última mudança, e não dentro do Enter "
                "nem da releitura"}
    medidas["releitura_de_um_glifo"] = {**resultado, "alvo_ms": 150,
                                        "com_o_lote": "impossível hoje: o lote ocupa o executor"}


def test_memoria_do_desfazer(ambiente, medidas):
    """A memória que o histórico prende (tracemalloc), por ação, extrapolada para 300 × 20."""
    app, janela = ambiente
    medidas["memoria_do_desfazer"] = {
        "boxes_por_pagina": round(sum(len(janela.projeto.carregar_pagina(i)) for i in PAGINAS)
                                  / len(PAGINAS)),
        "alvo_mb": 50, **_memoria_do_historico(app, janela)}


def _memoria_do_historico(app, janela) -> dict:
    """O que o histórico prende: a memória que volta quando ele é esvaziado.

    O `tracemalloc` liga **antes** da base, então tudo o que as ações alocam é rastreado,
    e o que some ao esvaziar o histórico (`historico.limpar()`) é exatamente o que ele
    prendia. O RSS não serve para isso: o alocador do Windows não devolve a memória ao
    sistema, e na rodada de 2026-10-16 ele não caiu nada ao esvaziar. As 3 páginas são
    visitadas antes da base, para o cache delas não entrar na conta. O RSS vai junto, só
    como informação.
    """
    import tracemalloc

    import psutil

    processo = psutil.Process()
    for indice in PAGINAS:
        janela.ir_para_pagina(indice)
    janela.pagina.historico.limpar()
    gc.collect()
    tracemalloc.start()
    try:
        rss_base = processo.memory_info().rss
        acoes = 0
        for indice in PAGINAS:
            janela.ir_para_pagina(indice)
            for k in range(ACOES_POR_PAGINA):
                mostrar(janela, k)
                janela.treino.campo.setText("y")
                janela.treino.pedir_so_corrigir()
                acoes += 1
        # O gravador (outra thread, que o `tracemalloc` também vê) termina antes de cada
        # leitura: sem isso, o que ele aloca e solta entre as duas era maior que o que o
        # histórico prende (rodadas do 2b com −9,6 e 0,2 MB).
        janela.projeto.descarregar(10)
        gc.collect()
        cheio, _ = tracemalloc.get_traced_memory()
        rss_cheio = processo.memory_info().rss
        estimativa = janela.pagina.historico.bytes
        janela.pagina.historico.limpar()
        janela.projeto.descarregar(10)
        gc.collect()
        vazio, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    preso = cheio - vazio
    por_acao = preso / acoes
    return {"acoes": acoes, "preso_pelo_historico_bytes": preso,
            "bytes_por_acao": round(por_acao),
            "estimado_300x20_mb": round(por_acao * 300 * 20 / 2**20, 1),
            "estimativa_do_historico_300x20_mb": round(estimativa / acoes * 300 * 20 / 2**20, 1),
            "rss_delta_bytes_informativo": rss_cheio - rss_base,
            "como": f"tracemalloc ligado antes de {acoes} ações reais (3 páginas já visitadas "
                    f"× {ACOES_POR_PAGINA}): o que é liberado ao esvaziar o histórico, por "
                    "ação, extrapolado para 300 páginas × 20 ações; e a estimativa que o "
                    "próprio histórico faz (`HistoricoDoProjeto.bytes`, a que o limite de 50 MB "
                    "usa). Desde o 2b, 100 ações por página: com 20, o histórico prendia menos "
                    "que o ruído do coletor de lixo"}


def test_atraso_e_memoria_durante_o_lote(ambiente, medidas):
    """Um QTimer de 16 ms durante um lote de 20 páginas: o atraso e o pico de RSS."""
    import psutil
    from PySide6.QtCore import QTimer

    app, janela = ambiente
    atrasos, rss = [], []
    ultimo = [time.perf_counter()]
    processo = psutil.Process()

    def tique():
        agora = time.perf_counter()
        atrasos.append((agora - ultimo[0]) * 1000 - 16)
        instantes.append(agora)
        ultimo[0] = agora
        rss.append(processo.memory_info().rss)

    instantes, fim_do_lote = [], []

    def lote_mudou():
        if not janela.livro.lote_rodando:
            fim_do_lote.append(time.perf_counter())

    janela.eventos.ligar("lote_mudou", lote_mudou)
    temporizador = QTimer()
    temporizador.setInterval(16)
    temporizador.timeout.connect(tique)
    temporizador.start()
    inicio = time.perf_counter()
    janela.livro.reconhecer(LOTE, refazer=True)      # o caminho do menu, sem o diálogo
    _esperar(app, janela, limite=1500)
    temporizador.stop()
    medidas["atraso_durante_o_lote"] = {
        "paginas": len(LOTE), "p99_ms": round(percentil(atrasos, 0.99), 1),
        "p95_ms": round(p95(atrasos), 1), "max_ms": round(max(atrasos), 1),
        "disparos": len(atrasos), "duracao_s": round(time.perf_counter() - inicio, 1),
        "alvo_p99_ms": 50,
        "acoes_durante_o_lote": "editar, desfazer, esquecer e os limiares são recusados com "
                                "aviso; F5 e Ctrl+R ficam desligados (passo 2a)",
        "como": "pelo controlador do livro (desde o 2a): inclui gravar o pendente antes do "
                "lote e recarregar a página aberta no fim; até o 1b, o lote rodava direto no "
                "executor, sem as duas coisas",
        "maior_atraso_no_fim_do_lote": _maior_no_fim(atrasos, instantes, fim_do_lote)}
    medidas["memoria_total_com_o_lote"] = {
        "rss_pico_mb": round(max(rss) / 2**20) if rss else None, "alvo_mb": 2560,
        "como": f"pico do RSS do processo único durante um lote de {len(LOTE)} páginas"}


def _maior_no_fim(atrasos, instantes, fim_do_lote) -> dict:
    """Onde caiu o maior atraso: no fim do lote (até 1 s depois do aviso de fim, quando a
    página aberta é recarregada) ou no meio dele."""
    if not atrasos or not fim_do_lote:
        return {}
    k = max(range(len(atrasos)), key=atrasos.__getitem__)
    distancia = instantes[k] - fim_do_lote[0]
    return {"ms": round(atrasos[k], 1), "segundos_depois_do_fim": round(distancia, 2),
            "no_fim": -0.05 <= distancia <= 1.0,
            "maior_antes_do_fim_ms": round(max((a for a, t in zip(atrasos, instantes)
                                                if t < fim_do_lote[0]), default=0), 1)}


def test_o_que_ainda_nao_existe(medidas):
    medidas["buscar_regex_no_livro"] = {"estado": "não existe", "alvo_p95_ms": 1000}
    medidas["montar_indice_da_busca"] = {"estado": "não existe", "alvo_p95_ms": 2000}
