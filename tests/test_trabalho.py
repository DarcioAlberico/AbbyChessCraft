"""O executor da janela (`app.trabalho.Executor`): o aviso de uma thread depois que ele se foi."""

from __future__ import annotations

import logging
import os
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from abbychess.app.trabalho import Executor  # noqa: E402


def test_o_pronto_que_falha_vai_ao_log_e_ao_aviso_e_a_fila_segue(qtbot, caplog):
    """SPEC-qualidade CA-Q-C1: o `pronto` (na interface) que levanta no meio não some no laço
    do Qt: o rastro vai ao log, o `falhou` da tarefa avisa (a barra de status), e a tarefa
    seguinte da fila roda."""
    executor = Executor()
    avisos, depois = [], []

    def preparar():
        def pronto(_resultado):
            raise ValueError("o pronto quebrou no meio")
        return (lambda _progresso: 1), pronto

    with caplog.at_level(logging.ERROR, logger="abbychess.app.trabalho"):
        executor.rodar("Quebra", preparar, falhou=avisos.append)
        executor.rodar("Depois", lambda: ((lambda _progresso: 2), depois.append))
        qtbot.waitUntil(lambda: depois == [2], timeout=5000)
    assert len(avisos) == 1 and "o pronto quebrou no meio" in avisos[0]
    assert [r for r in caplog.records if r.exc_info and "Quebra" in r.getMessage()]


def test_o_aviso_de_uma_thread_depois_do_executor_apagado_e_descartado():
    """A janela fechou com o índice da busca montando: a thread dele avisava pelo executor
    apagado, e o "Signal source has been deleted" escapava na thread (o portão o mostrou)."""
    app = QApplication.instance() or QApplication([])
    executor = Executor()
    chamadas, erros = [], []
    executor.na_interface(lambda: chamadas.append("antes"))
    app.processEvents()
    assert chamadas == ["antes"]
    executor.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def avisar():
        try:
            executor.na_interface(lambda: chamadas.append("depois"))
        except Exception as erro:  # noqa: BLE001 — é o que o teste procura
            erros.append(erro)

    thread = threading.Thread(target=avisar)
    thread.start()
    thread.join(5)
    app.processEvents()
    assert erros == [] and chamadas == ["antes"]
