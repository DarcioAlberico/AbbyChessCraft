"""O que os testes dividem (SPEC-qualidade Q-T5): as fixtures de mais de um módulo."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox
from abbychess import pagina as pg
from abbychess.leitor import LeitorDoLivro
from abbychess.modelo import Box
from abbychess.projeto import ProjetoDeLivro
from tests.ajudantes import _ate_valer
from tests.ajudantes import _esperar
from tests.ajudantes import pdf_sintetico
from tests.ajudantes import _pagina
from tests.ajudantes import _pagina_sintetica


@pytest.fixture
def livro_escrito(tmp_path):
    """Um projeto de 3 páginas com o texto escrito à mão (sem reconhecer), o controlador da
    página e o da busca (sem processos)."""
    from abbychess.controladores import ControladorDaBusca
    from abbychess.modelo import gid_de
    from abbychess.projeto import ProjetoDeLivro
    from tests.ajudantes import ExecutorManual, _controlador  # noqa: E402,F401,F811
    from tests.ajudantes import pdf_sintetico  # noqa: E402,F401,F811

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Três", pdf_sintetico(tmp_path))
    executor = ExecutorManual()
    ctl = _controlador(projeto, executor)

    def escrever(indice, texto):
        pagina = projeto.pagina_para_editar(indice)
        modelo = _pagina(texto)
        pagina.boxes = [Box(gid_de(pagina.pid, n), b.entry) for n, b in enumerate(modelo.boxes)]
        pagina.proximo_n = len(pagina.boxes)
        pagina.estado = "reconhecida"
        projeto.salvar_modelo(pagina)
        return pagina

    for i, texto in enumerate(("casa velha", "outra casa", "fim")):
        escrever(i, texto)
    busca = ControladorDaBusca(ctl, paralelo=False)
    eventos = {"fins": [], "falhas": [], "avisos": []}
    ctl.eventos.ligar("busca_terminou", eventos["fins"].append)
    ctl.eventos.ligar("busca_falhou", eventos["falhas"].append)
    ctl.eventos.ligar("aviso", lambda titulo, texto: eventos["avisos"].append(texto))
    busca.abrir()
    _ate_valer(busca.pronto.is_set)
    yield projeto, ctl, busca, escrever, eventos
    projeto.fechar()


@pytest.fixture
def jb(j):  # noqa: F811
    """A janela do módulo com a barra de busca fechada e as opções no padrão."""
    from abbychess import busca as bs

    b = j.barra_de_busca
    j.fechar_busca()
    b.escolher_escopo(bs.LIVRO)
    b.intervalo.clear()
    for botao in (b.maiusculas, b.palavra, b.regex, b.figurina):
        botao.setChecked(False)
    j._selecao_congelada = None
    b.relogio.stop()
    return j


@pytest.fixture(scope="module")
def _janela_do_modulo(app, tmp_path_factory):  # noqa: F811
    """Uma janela para o módulo (abrir uma por teste custava ~2,5 s da suíte rápida)."""
    from PySide6.QtWidgets import QMessageBox

    from abbychess.projeto import ProjetoDeLivro
    from tests.ajudantes import _abrir  # noqa: E402,F401,F811
    from tests.ajudantes import _pagina_sintetica  # noqa: E402,F401,F811

    remendo = pytest.MonkeyPatch()
    remendo.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    pasta = tmp_path_factory.mktemp("edicao")
    janela = _abrir(ProjetoDeLivro.criar(pasta / "livros", "Edição",
                                         _pagina_sintetica(pasta / "pagina.png")))
    yield janela
    janela.close()
    remendo.undo()


@pytest.fixture
def j(_janela_do_modulo):
    """A janela do módulo com o desfazer, a sessão e o modo do livro de volta ao começo."""
    from abbychess import historico as hs

    janela = _janela_do_modulo
    if janela.texto.tem_sessao:
        janela.texto.restaurar()
    janela.texto._restaurada = None
    janela.pagina.historico = hs.HistoricoDoProjeto()
    janela.projeto.dados.idioma, janela.projeto.dados.notacao = "pt", "figurinas"
    janela.linha.avisar("")
    return janela


@pytest.fixture
def sim(monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)


@pytest.fixture
def lida(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    return janela


@pytest.fixture
def sem_dialogos(monkeypatch):
    """Registra os avisos em vez de abrir caixas de diálogo."""
    avisos = []
    for nome in ("information", "warning"):
        monkeypatch.setattr(QMessageBox, nome,
                            lambda _pai, titulo, texto, *a, **k: avisos.append(texto))
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    return avisos                   # sem os modelos globais: o conftest (CA-Q-T1)


@pytest.fixture
def projeto_lido(tmp_path, app):  # noqa: F811
    from abbychess import livro, pagina as pg

    fonte = _pagina_sintetica(tmp_path / "pagina.png")
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Janela", fonte)
    leitor = LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)
    livro.reconhecer_paginas(projeto, pg.fonte_do_projeto(projeto), leitor, [0])
    return projeto


@pytest.fixture
def projeto(tmp_path):
    return ProjetoDeLivro.criar(tmp_path / "livros", "Livro de Teste", pdf_sintetico(tmp_path))


@pytest.fixture
def leitor(projeto):
    return LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)


@pytest.fixture
def fonte(projeto):
    return pg.FonteDePaginas(projeto.fonte)


@pytest.fixture
def pdf_de_60_paginas(tmp_path):
    import fitz

    caminho = tmp_path / "sessenta.pdf"
    with fitz.open() as doc:
        for k in range(60):
            pagina = doc.new_page(width=200, height=300)
            pagina.insert_text((20, 40), f"Pagina {k + 1}", fontsize=14)
        doc.save(str(caminho))
    return caminho
