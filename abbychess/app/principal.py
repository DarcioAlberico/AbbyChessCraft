"""Entrada do aplicativo: `python -m abbychess [pasta-do-projeto]`."""

from __future__ import annotations

import logging
import sys
import threading

from abbychess import log_em_arquivo

log = logging.getLogger(__name__)


def registrar_os_erros_soltos() -> None:
    """O erro que ninguém pegou, num slot do Qt (`sys.excepthook`) ou numa thread
    (`threading.excepthook`), vai ao log com o rastro: o programa aberto pelo atalho não tem
    o stderr onde ele iria parar (SPEC-qualidade Q-C1)."""
    def na_interface(tipo, erro, rastro):
        log.critical("erro não tratado", exc_info=(tipo, erro, rastro))

    def na_thread(args):
        if args.exc_type is not SystemExit:
            log.critical("erro não tratado na thread %s",
                         args.thread.name if args.thread is not None else "?",
                         exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = na_interface
    threading.excepthook = na_thread


def traduzir_o_qt(app) -> None:
    """Os textos do próprio Qt (os botões padrão, os menus de contexto) em português, pela
    tradução que vem com o PySide6; sem ela, ficam em inglês."""
    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator

    tradutor = QTranslator(app)
    pasta = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if tradutor.load(QLocale(QLocale.Language.Portuguese, QLocale.Country.Brazil), "qtbase",
                     "_", pasta):
        app.installTranslator(tradutor)


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    log_em_arquivo.ligar("app")
    registrar_os_erros_soltos()

    # Importados aqui para `--help` e os testes não pagarem a carga do Qt.
    from PySide6.QtWidgets import QApplication

    from abbychess.app import estilo, opcoes, registro_de_eventos
    from abbychess.app.janela import JanelaPrincipal, configuracao

    app = QApplication(argv)
    app.setApplicationName("AbbyChessCraft")
    app.setOrganizationName("AbbyChessCraft")
    traduzir_o_qt(app)
    estilo.registrar_os_simbolos()
    # O tema do sistema (§13), e de novo quando ele muda, sem reiniciar (CA-13.3).
    estilo.aplicar(app)
    estilo.acompanhar_o_sistema(app)
    registro = registro_de_eventos.instalar(   # noqa: F841 (vive enquanto o app vive)
        app, str(log_em_arquivo.pasta_de_dados() / "eventos.jsonl")
        if opcoes.registro_ligado(configuracao()) else None)
    janela = JanelaPrincipal()
    janela.restaurar_a_geometria()
    janela.show()
    if len(argv) > 1:
        janela.abrir_caminho(argv[1])
    else:
        janela.reabrir_o_ultimo()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
