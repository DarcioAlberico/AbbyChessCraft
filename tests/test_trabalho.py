"""O executor da janela (`app.trabalho.Executor`): o aviso de uma thread depois que ele se foi."""

from __future__ import annotations

import os
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from abbychess.app.trabalho import Executor  # noqa: E402


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
