"""Entrada do aplicativo: `python -m abbychess [pasta-do-projeto]`."""

from __future__ import annotations

import logging
import sys


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    # Importados aqui para `--help` e os testes não pagarem a carga do Qt.
    from PySide6.QtWidgets import QApplication

    from abbychess.app import estilo, registro_de_eventos
    from abbychess.app.janela import JanelaPrincipal

    app = QApplication(argv)
    app.setApplicationName("AbbyChessCraft")
    app.setOrganizationName("AbbyChessCraft")
    # O tema do sistema (§13), e de novo quando ele muda, sem reiniciar (CA-13.3).
    estilo.aplicar(app)
    estilo.acompanhar_o_sistema(app)
    registro = registro_de_eventos.instalar(app)    # noqa: F841 (vive enquanto o app vive)
    janela = JanelaPrincipal()
    janela.show()
    if len(argv) > 1:
        janela.abrir_caminho(argv[1])
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
