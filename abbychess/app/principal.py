"""Entrada do aplicativo: `python -m abbychess [pasta-do-projeto]`."""

from __future__ import annotations

import logging
import sys


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    # Importados aqui para `--help` e os testes não pagarem a carga do Qt.
    from PySide6.QtWidgets import QApplication

    from abbychess.app.janela import JanelaPrincipal

    app = QApplication(argv)
    app.setApplicationName("AbbyChessCraft")
    app.setOrganizationName("AbbyChessCraft")
    janela = JanelaPrincipal()
    janela.show()
    if len(argv) > 1:
        janela.abrir_caminho(argv[1])
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
