"""Configuração comum dos testes: o Qt sem tela (`offscreen`) e o portão das camadas lentas.

As fixtures da janela (`app`, `janela`) e a página sintética ainda moram em
`tests/test_janela.py` e `tests/test_treino_por_livro.py`, importadas pelos outros
módulos; elas vêm para cá no passo 2a, quando a janela passa a ser montada pelo
controlador e as fixtures mudam de qualquer jeito.

O portão (SPEC §15.1): com `ABBY_PORTAO=1`, um teste `livro_real` que pularia por
falta do PDF ou do modelo **falha** (na preparação, numa fixture ou na chamada; um xfail
continua xfail). O portão só vale com as camadas selecionadas:
`ABBY_PORTAO=1 pytest -q -m "livro_real or desempenho"`; sem o `-m`, o `addopts` as tira.
Fora do portão, pular é aceito, para a suíte rodar numa máquina sem os livros.
"""

from __future__ import annotations

import os
import weakref

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# A suíte rápida abre os projetos sem o servidor de leitura (um processo por abertura): os
# testes do servidor (`-m processo`) o ligam com `ABBY_SERVIDOR=1` e o leitor falso.
os.environ.setdefault("ABBY_SERVIDOR", "0")
# O índice da busca sem o pool de processos (cada janela aberta nos testes abriria 6).
os.environ.setdefault("ABBY_INDICE_PARALELO", "0")
# A pré-carga renderiza aqui, e não no processo de render do programa (`abbychess.render`):
# cada janela da suíte abriria um. Os testes dele o ligam; as medidas de desempenho também.
os.environ.setdefault("ABBY_RENDER_EM_PROCESSO", "0")
# O offscreen não acha as fontes do sistema: sem elas o texto sai em quadrados largos, e as
# medidas de largura dos painéis (CA-3.2, o Inspetor de 296 px) não valem como no programa.
if os.name == "nt":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"),
                                                         "Fonts"))


def pytest_configure(config):
    """O `QSettings` dos testes num INI temporário, e não no registro do usuário: um teste que
    troca o perfil de teclado, a pasta de exportação ou as opções lembradas não deixa nada
    no programa de quem roda a suíte (e não herda o que essa pessoa escolheu). Vale para o
    `janela.configuracao()`, que segue o formato padrão."""
    import tempfile

    from PySide6.QtCore import QSettings

    pasta = tempfile.mkdtemp(prefix="abby-qsettings-")
    config._abby_qsettings = pasta
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, pasta)
    _anotar_os_gravadores()


#: Os gravadores de página criados (fracos): `gravadores_descarregados` os descarrega no fim de
#: cada teste.
_GRAVADORES: list = []


def _anotar_os_gravadores() -> None:
    from abbychess import gravador as gr

    original = gr.Gravador.__init__

    def __init__(self, *args, **kwargs):
        original(self, *args, **kwargs)
        _GRAVADORES.append(weakref.ref(self))

    gr.Gravador.__init__ = __init__


@pytest.fixture(autouse=True)
def gravadores_descarregados():
    """O que o gravador de um projeto do teste tem pendente é gravado no fim dele, e não no
    meio do teste seguinte (um teste que troca as funções de `gravacao` a veria passar)."""
    inicio = len(_GRAVADORES)
    yield
    novos = _GRAVADORES[inicio:]
    del _GRAVADORES[inicio:]
    for referencia in novos:
        gravador = referencia()
        if gravador is not None:
            try:
                gravador.descarregar(2.0)
            except Exception:  # noqa: BLE001 — o gravador de um teste que o quebrou de propósito
                pass


@pytest.fixture(autouse=True, scope="module")
def janelas_apagadas_no_fim_do_modulo():
    """As janelas e os diálogos que os testes do módulo deixaram vivos (fechados, mas ainda
    no Qt) são apagados no fim dele. Sem isto eles se acumulavam pela suíte inteira, e cada
    troca de tema (`estilo.aplicar`, a folha de estilo da aplicação) refazia o estilo de
    todos: os testes do tema levavam ~15 s cada, e a suíte, 310 s em vez de ~60 (§15.1).
    Por ser autouse e de módulo, ela abre antes e fecha depois das fixtures do módulo."""
    yield
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    for widget in app.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def pytest_unconfigure(config):
    import shutil

    pasta = getattr(config, "_abby_qsettings", None)
    if pasta:
        shutil.rmtree(pasta, ignore_errors=True)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    resultado = yield
    relatorio = resultado.get_result()
    if (os.environ.get("ABBY_PORTAO") == "1" and relatorio.skipped
            and not hasattr(relatorio, "wasxfail")
            and item.get_closest_marker("livro_real") is not None):
        relatorio.outcome = "failed"
        relatorio.longrepr = (f"[portão] {item.nodeid} pulou, mas no portão o livro real é "
                              f"obrigatório: {relatorio.longrepr}")


def pytest_addoption(parser):
    parser.addoption("--atualizar-golden", action="store_true", default=False,
                     help="regrava os arquivos de referência (golden) em vez de comparar")
