"""A pré-visualização da exportação (§12.2, passo J): CA-12.4 e CA-12.5."""

from __future__ import annotations

import html
import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from core.pagina import Figura, PaginaExtraida, Paragrafo  # noqa: E402

from abbychess import exportar as ex  # noqa: E402
from abbychess import previa as pv  # noqa: E402
from abbychess.app import dialogo_exportacao as de  # noqa: E402

from tests.test_livro import _ensinar_e_ler, fonte, leitor, projeto  # noqa: E402,F401


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _paragrafos_do_html(texto: str) -> list:
    """O texto de cada `<p>`/`<hN>` do livro na prévia (sem o relatório, as legendas dos
    diagramas, as marcas de página e o aviso do resto)."""
    corpo = texto.split('</div>', 1)[1]           # depois do relatório
    saida = []
    for _tag, atributos, conteudo in re.findall(r"<(p|h\d)([^>]*)>(.*?)</\1>", corpo, re.S):
        if "class=" in atributos or "<img" in conteudo:
            continue
        saida.append(html.unescape(re.sub(r"<[^>]+>", "", conteudo)).strip())
    return [s for s in saida if s]


def test_ca_12_4_previa_e_docx_tem_o_mesmo_texto_por_paragrafo(projeto, fonte, leitor,  # noqa: F811
                                                               tmp_path):
    from docx import Document

    _ensinar_e_ler(projeto, fonte, leitor)
    texto, _ = ex.previa(projeto, "docx")
    destino = tmp_path / "livro.docx"
    ex.exportar(projeto, destino)
    # A legenda do diagrama (estilo Caption) é a ressalva dele, como o alt na prévia.
    docx = [p.text.strip() for p in Document(str(destino)).paragraphs
            if p.text.strip() and p.style.name != "Caption"]
    previa = _paragrafos_do_html(texto)
    assert previa and previa == docx


def test_ca_12_5_o_relatorio_da_previa_e_o_da_exportacao(projeto, fonte, leitor,  # noqa: F811
                                                        tmp_path):
    _ensinar_e_ler(projeto, fonte, leitor)
    texto, relatorio_da_previa = ex.previa(projeto, "epub")
    _, relatorio = ex.exportar_com_relatorio(projeto, tmp_path / "livro.epub")
    assert relatorio_da_previa.texto().splitlines()[1:] == relatorio.texto().splitlines()[1:]
    for linha in relatorio.texto().splitlines()[1:]:
        assert html.escape(linha) in texto
    assert not (tmp_path / "livro.txt").exists()       # a prévia não grava nada


def test_previa_do_pgn_e_sem_previa_do_pdf(projeto, fonte, leitor):  # noqa: F811
    _ensinar_e_ler(projeto, fonte, leitor)
    texto, relatorio = ex.previa(projeto, "pgn")
    assert "<pre>" in texto and relatorio.formato == "pgn"
    with pytest.raises(ValueError, match="PDF"):
        ex.previa(projeto, "pdf")


def test_livro_grande_mostra_o_comeco_e_conta_o_resto():
    paginas = [PaginaExtraida(numero=i, blocos=[Paragrafo(f"Página {i}.")]) for i in range(35)]
    texto = pv.html_do_livro(paginas, ["resumo"], "T", limite=30)
    assert "Página 29." in texto and "Página 30." not in texto
    assert "e mais 5 página(s)" in texto


def test_diagrama_vai_dentro_do_html_com_o_texto_alternativo():
    import io

    from PIL import Image

    dados = io.BytesIO()
    Image.new("L", (8, 8), 0).save(dados, format="PNG")
    figura = Figura(dados.getvalue(), 8, 8, fen="8/8/8/8/8/8/8/K6k w - - 0 1", origem="render")
    texto = pv.html_do_livro([PaginaExtraida(numero=0, blocos=[figura])], ["r"], "T")
    assert 'src="data:image/png;base64,' in texto
    assert "Diagrama: FEN 8/8/8/8/8/8/8/K6k w - - 0 1" in texto


def test_o_botao_do_dialogo_pede_e_mostra_a_previa(app, tmp_path):
    pedidos = []
    d = de.DialogoDeExportacao(None, "epub", ex.Opcoes(), {"autores": ["A"]}, tmp_path, "T")
    d.ao_previsualizar = lambda *args: pedidos.append(args)
    d.previsualizar()
    assert pedidos == [("epub", ex.Opcoes(), {"autores": ["A"]})]
    assert not d.btn_previa.isEnabled()
    d.mostrar_previa("<p>o livro</p>")
    assert d.btn_previa.isEnabled() and d.janela_da_previa.isVisible()
    assert "o livro" in d.janela_da_previa.navegador.toPlainText()
    d.janela_da_previa.close()
    d.previa_falhou("erro")
    assert d.btn_previa.text() == "Pré-visualizar…"
    assert not de.DialogoDeExportacao(None, "pdf", ex.Opcoes(), {}, tmp_path, "T") \
        .btn_previa.isEnabled()


def test_previa_do_txt_e_o_txt(projeto, fonte, leitor):  # noqa: F811
    _ensinar_e_ler(projeto, fonte, leitor)
    sem, _ = ex.previa(projeto, "txt")
    com, _ = ex.previa(projeto, "txt", opcoes=ex.Opcoes(marcas_de_pagina=True))
    assert "<pre>" in sem and "[p. 1]" not in sem and "[p. 1]" in com
