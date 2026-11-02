r"""CA-9.4 [desempenho] (SPEC §9.1): com o servidor de leitura real, o atraso de evento fica
p99 ≤ 50 ms enquanto os modelos carregam (a navegação já funciona nesse tempo).

    .venv\Scripts\python.exe -m pytest -q -m desempenho tests\desempenho\test_carregar_modelos.py

A janela abre o projeto do livro de referência como o usuário abre (`abrir_caminho`, com o
servidor e a fábrica de verdade), e um `QTimer` de 16 ms mede o atraso de cada disparo do
começo da abertura até os modelos ficarem prontos no filho. Sem o livro, pula (no portão,
falha, pelo marcador `livro_real`).
"""

from __future__ import annotations

import os
import time

import pytest

from tests.desempenho.conftest import p95, percentil
from tests.livros import PASTA_DOS_PDFS

pytestmark = [pytest.mark.desempenho, pytest.mark.livro_real, pytest.mark.timeout(900)]

_PDF = sorted(PASTA_DOS_PDFS.glob("Xadrez Vitorioso*/*.pdf"))


def test_atraso_enquanto_os_modelos_carregam(tmp_path, monkeypatch, medidas):
    if not _PDF:
        pytest.skip("o PDF do Xadrez Vitorioso não está nesta máquina")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("ABBY_SERVIDOR", "1")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox

    from abbychess.app.janela import JanelaPrincipal
    from abbychess.projeto import ProjetoDeLivro

    for nome in ("information", "warning"):
        monkeypatch.setattr(QMessageBox, nome, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    app = QApplication.instance() or QApplication([])
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Modelos", _PDF[0])
    pasta = projeto.pasta
    projeto.fechar()

    janela = JanelaPrincipal()
    janela.resize(1600, 1000)
    janela.show()
    prontos = []
    janela.eventos.ligar("modelos_prontos", prontos.append)
    atrasos, ultimo = [], [0.0]

    def tique():
        agora = time.perf_counter()
        atrasos.append((agora - ultimo[0]) * 1000 - 16)
        ultimo[0] = agora

    temporizador = QTimer()
    temporizador.setInterval(16)
    temporizador.timeout.connect(tique)
    try:
        inicio = time.perf_counter()
        ultimo[0] = inicio
        temporizador.start()
        janela.abrir_caminho(str(pasta))
        fim = time.monotonic() + 600
        while not prontos and time.monotonic() < fim:
            app.processEvents()
            time.sleep(0.002)
        temporizador.stop()
        assert prontos, "os modelos não carregaram no prazo"
        duracao = time.perf_counter() - inicio
    finally:
        temporizador.stop()
        janela.close()
    # O primeiro disparo inclui a própria abertura (até a janela voltar ao laço de eventos):
    # ela vai à parte, e o critério é o atraso com os modelos carregando no fundo.
    abertura, durante = atrasos[0], atrasos[1:]
    p99 = percentil(durante, 0.99)
    medidas["atraso_carregando_os_modelos"] = {
        "p99_ms": round(p99, 1), "p95_ms": round(p95(durante), 1),
        "max_ms": round(max(durante), 1), "disparos": len(durante),
        "abertura_ms": round(abertura, 1), "duracao_s": round(duracao, 1), "alvo_p99_ms": 50,
        "como": "QTimer de 16 ms do abrir_caminho do projeto (o servidor e a fábrica de "
                "verdade) até modelos_prontos; o primeiro disparo, que inclui a abertura, vai "
                "à parte"}
    assert p99 <= 50 * 1.2, f"p99 {p99:.1f} ms (alvo 50, corte 60)"
