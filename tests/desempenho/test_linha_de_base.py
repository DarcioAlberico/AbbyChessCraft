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
    """De `ir_para_pagina` ao visor pintado numa QImage 1600×1000. Hoje não há cache."""
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
        **resultado, "alvo_no_cache_ms": 150, "alvo_fora_ms": 600,
        "como": "mesmo processo, alternando 2 páginas lidas; hoje não há cache, então este "
                "número vale para 'no cache'. 'Fora do cache' (processo novo) não foi medido "
                "pelo método e fica para o passo A1."}


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

    def ensinar(_i):
        QTest.keyClick(janela.treino.campo, Qt.Key.Key_Return)
        _esperar(app, janela, limite=120)

    resultado = cronometrar(ensinar, antes=preparar)
    medidas["enter_ensinar"] = {
        **resultado, "alvo_ms": 100,
        "padroes_no_livro": [antes, janela.leitor.total_de_padroes],
        "caracteres_novos": sum(novos[-resultado["n"]:]),
        "como": "QTest.keyClick(Enter) no campo, com o caractere lido do primeiro pendente "
                "(conferir a leitura), até o fim da propagação (a cor só muda no fim)"}


def test_releitura_de_um_glifo(ambiente, medidas):
    """Ajustar uma borda relê o glifo com a cadeia global, na thread da interface."""
    app, janela = ambiente
    janela.ir_para_pagina(PAGINAS[1])
    mostrar(janela, 0)
    lados = [(0, 0, 1, 0), (0, 0, -1, 0)]

    resultado = cronometrar(lambda i: janela.pagina.ajustar(*lados[i % 2]))
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
    e o que some ao esvaziar o histórico (`historicos.clear()`) é exatamente o que ele
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
    janela.pagina.historicos.clear()
    gc.collect()
    tracemalloc.start()
    try:
        rss_base = processo.memory_info().rss
        acoes = 0
        for indice in PAGINAS:
            janela.ir_para_pagina(indice)
            for k in range(20):
                mostrar(janela, k)
                janela.treino.campo.setText("y")
                janela.treino._so_corrigir()
                acoes += 1
        gc.collect()
        cheio, _ = tracemalloc.get_traced_memory()
        rss_cheio = processo.memory_info().rss
        janela.pagina.historicos.clear()
        gc.collect()
        vazio, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    preso = cheio - vazio
    por_acao = preso / acoes
    return {"acoes": acoes, "preso_pelo_historico_bytes": preso,
            "bytes_por_acao": round(por_acao),
            "estimado_300x20_mb": round(por_acao * 300 * 20 / 2**20, 1),
            "rss_delta_bytes_informativo": rss_cheio - rss_base,
            "como": f"tracemalloc ligado antes de {acoes} ações reais (3 páginas já visitadas "
                    "× 20): o que é liberado ao esvaziar o histórico, por ação, extrapolado "
                    "para 300 páginas × 20 ações"}


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
        ultimo[0] = agora
        rss.append(processo.memory_info().rss)

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
        "acoes_durante_o_lote": "editar é recusado com aviso; ler entra na fila (passo 2a)"}
    medidas["memoria_total_com_o_lote"] = {
        "rss_pico_mb": round(max(rss) / 2**20) if rss else None, "alvo_mb": 2560,
        "como": f"pico do RSS do processo único durante um lote de {len(LOTE)} páginas"}


def test_o_que_ainda_nao_existe(medidas):
    medidas["buscar_regex_no_livro"] = {"estado": "não existe", "alvo_p95_ms": 1000}
    medidas["montar_indice_da_busca"] = {"estado": "não existe", "alvo_p95_ms": 2000}
