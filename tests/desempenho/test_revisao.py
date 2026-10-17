r"""As metas da revisão (SPEC §8, passo C), num livro sintético de 230 páginas.

    .venv\Scripts\python.exe -m pytest -q -m desempenho tests\desempenho\test_revisao.py

- CA-8.3 [desempenho]: do `abrir()` do projeto ao painel de Páginas com 230 linhas, p95 ≤
  300 ms (a gaveta já aberta); e mudar os limiares recalcula os pendentes de todas as páginas
  sem reler JSON.

O portão (`alvo × 1,2`) só reprova na máquina de `docs/medidas/maquina.json`.
"""

from __future__ import annotations

import time

import pytest

from tests.desempenho.conftest import na_maquina_cadastrada, percentil
from tests.desempenho.test_busca import PAGINAS
from tests.desempenho.test_substituir import _livro_de_230

pytestmark = [pytest.mark.desempenho, pytest.mark.timeout(900)]


def _portao(valor: float, alvo: float) -> None:
    if na_maquina_cadastrada():
        assert valor <= alvo * 1.2, f"{valor} > {alvo} × 1,2"


def test_ca_8_3_do_abrir_ao_painel_de_paginas(tmp_path, medidas, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox

    from abbychess.app.janela import JanelaPrincipal
    from abbychess.projeto import ProjetoDeLivro

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    app = QApplication.instance() or QApplication([])
    pasta = _livro_de_230(tmp_path)
    pasta.fechar()
    pasta = pasta.pasta
    janela = JanelaPrincipal()
    tempos = []
    try:
        janela.show()
        lista = janela.paginas.lista
        for rodada in range(11):
            if janela.projeto is not None:
                janela._fechar_projeto()
                lista.clear()
                app.processEvents()
            projeto = ProjetoDeLivro.abrir(pasta)
            inicio = time.perf_counter()
            janela.abrir(projeto)
            fim = time.monotonic() + 60
            if not rodada:                               # a primeira aquece e abre a gaveta,
                while not janela.pagina.pronto and time.monotonic() < fim:    # que o espaço
                    app.processEvents()                  # do projeto grava ao fechar
                    time.sleep(0.01)
                janela.abrir_gaveta()
            while lista.topLevelItemCount() < PAGINAS and time.monotonic() < fim:
                app.processEvents()
                time.sleep(0.001)
            assert lista.topLevelItemCount() >= PAGINAS
            if rodada:                                   # a primeira aquece
                tempos.append((time.perf_counter() - inicio) * 1000)
        assert sum(1 for i in range(PAGINAS)
                   if lista.topLevelItem(i).text(2)) > 0      # os pendentes, pelo resumo
        # Mudar os limiares: os pendentes de todas as páginas, sem abrir nenhuma.
        p = janela.pagina
        fim = time.monotonic() + 120
        while not p.pronto and time.monotonic() < fim:   # o leitor da interface carregado
            app.processEvents()
            time.sleep(0.01)
        abertas = []
        original = p.projeto.carregar_modelo
        monkeypatch.setattr(p.projeto, "carregar_modelo",
                            lambda i: (abertas.append(i), original(i))[1])
        limiares = type(p.leitor.limiares)(**{**vars(p.leitor.limiares), "revisao": 0.5})
        inicio = time.perf_counter()
        p.aplicar_limiares(limiares)
        while janela.executor.ocupado:
            app.processEvents()
        t_limiares = (time.perf_counter() - inicio) * 1000
        assert set(abertas) <= {p.indice}                # só a aberta, que já está na memória
    finally:
        janela.close()
        app.processEvents()
    p95 = round(percentil(tempos, 0.95), 1)
    medidas["abrir_ao_painel_de_paginas"] = {
        "ms": [round(t) for t in tempos],
        "p50_ms": round(percentil(tempos, 0.5), 1), "p95_ms": p95, "max_ms": round(max(tempos), 1),
        "n": len(tempos), "paginas": PAGINAS, "alvo_p95_ms": 300,
        "limiares_ms": round(t_limiares, 1),
        "como": "JanelaPrincipal com a gaveta aberta; do janela.abrir(projeto) às 230 linhas no "
                "painel de Páginas (o leitor da interface carregando), 10 vezes depois de uma "
                "que aquece; e mudar o limiar de revisão (sem abrir as páginas)"}
    _portao(p95, 300)
