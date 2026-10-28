"""Os links de análise dos diagramas: Lichess, Chess.com ou nenhum (§12.1)."""

from __future__ import annotations

import io
import os
import zipfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.pagina import Figura, PaginaExtraida, Paragrafo  # noqa: E402

from abbychess import epub  # noqa: E402
from abbychess import escritor_docx  # noqa: E402
from abbychess import exportar as ex  # noqa: E402
from abbychess import links_de_analise as la  # noqa: E402
from abbychess import previa as pv  # noqa: E402

FEN = "8/8/8/8/8/8/8/K6k w - - 0 1"


def _png() -> bytes:
    from PIL import Image

    dados = io.BytesIO()
    Image.new("L", (8, 8), 0).save(dados, format="PNG")
    return dados.getvalue()


def _paginas():
    """Um diagrama lido, do lado das pretas, e um recorte sem posição."""
    lido = Figura(_png(), 8, 8, fen=FEN, origem="render", orientacao="preta")
    recorte = Figura(_png(), 8, 8, origem="recorte")
    return [PaginaExtraida(numero=0, blocos=[Paragrafo("Texto antes."), lido,
                                             Paragrafo("Texto entre."), recorte])]


def _metadados():
    return epub.Metadados(titulo="Livro", idioma="pt-BR")


# ----------------------------------------------------------------------
# O endereço

def test_o_link_do_lichess_e_do_chess_com():
    assert la.link(FEN, "lichess") == \
        "https://lichess.org/analysis/standard/8/8/8/8/8/8/8/K6k_w_-_-_0_1"
    assert la.link(FEN, "chesscom") == \
        "https://www.chess.com/analysis?fen=8/8/8/8/8/8/8/K6k%20w%20-%20-%200%201"


def test_o_tabuleiro_abre_do_lado_impresso():
    assert la.link(FEN, "lichess", orientacao="preta").endswith("_0_1?color=black")
    assert la.link(FEN, "chesscom", orientacao="preta").endswith("&flip=true")


def test_nenhum_ou_sem_fen_nao_tem_link_e_o_site_desconhecido_e_recusado():
    assert la.link(FEN, "nenhum") is None
    assert la.link(None, "lichess") is None
    assert la.link("  ", "chesscom") is None
    with pytest.raises(ValueError, match="desconhecido"):
        la.link(FEN, "chess24")
    with pytest.raises(ValueError, match="desconhecido"):
        ex.Opcoes(links_de_analise="chess24")


def test_o_fen_pela_metade_e_completado_com_o_lado_a_jogar():
    assert la.fen_completo("8/8/8/8/8/8/8/K6k", "b") == "8/8/8/8/8/8/8/K6k b - - 0 1"
    assert la.fen_completo("8/8/8/8/8/8/8/K6k") == "8/8/8/8/8/8/8/K6k w - - 0 1"
    assert la.fen_completo("8/8/8/8/8/8/8/K6k b") == "8/8/8/8/8/8/8/K6k b - - 0 1"
    assert la.fen_completo("8/8/8/8/8/8/8/K6k w - - 3 40") == "8/8/8/8/8/8/8/K6k w - - 3 40"
    figura = Figura(_png(), 8, 8, fen="8/8/8/8/8/8/8/K6k", lado_a_jogar="b")
    assert la.link_da_figura(figura, "lichess").endswith("K6k_b_-_-_0_1")


def test_o_rotulo_no_idioma_do_livro():
    assert la.rotulo("lichess", "pt-BR") == "Analisar no Lichess"
    assert la.rotulo("chesscom", "en-US") == "Analyze on Chess.com"
    assert la.rotulo("lichess", "it") == "Analyze on Lichess"     # sem tradução: inglês


# ----------------------------------------------------------------------
# Os arquivos

def _xhtml_dos_capitulos(caminho) -> str:
    with zipfile.ZipFile(caminho) as z:
        return "".join(z.read(n).decode("utf-8") for n in z.namelist()
                       if "capitulo-" in n)


def test_o_epub_poe_o_link_so_no_diagrama_lido(tmp_path):
    caminho = tmp_path / "livro.epub"
    escrito = epub.escrever(_paginas(), caminho, _metadados(), analise="lichess")
    assert escrito.analises == 1
    corpo = _xhtml_dos_capitulos(caminho)
    assert corpo.count('class="analise"') == 1
    assert ('<a class="analise" href="https://lichess.org/analysis/standard/'
            '8/8/8/8/8/8/8/K6k_w_-_-_0_1?color=black">Analisar no Lichess</a>') in corpo
    assert epub.conferir(caminho) == []


def test_o_epub_sem_link_sai_igual_ao_de_antes(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    padrao, nenhum = tmp_path / "padrao.epub", tmp_path / "nenhum.epub"
    epub.escrever(_paginas(), padrao, _metadados())
    escrito = epub.escrever(_paginas(), nenhum, _metadados(), analise="nenhum")
    assert escrito.analises == 0
    assert padrao.read_bytes() == nenhum.read_bytes()
    assert "analise" not in _xhtml_dos_capitulos(nenhum)


def test_o_docx_poe_o_hiperlink_externo(tmp_path):
    caminho = tmp_path / "livro.docx"
    escrito = escritor_docx.escrever(_paginas(), caminho, _metadados(), analise="chesscom")
    assert escrito.analises == 1
    with zipfile.ZipFile(caminho) as z:
        relacoes = z.read("word/_rels/document.xml.rels").decode("utf-8")
        documento = z.read("word/document.xml").decode("utf-8")
    assert ('Target="https://www.chess.com/analysis?fen=8/8/8/8/8/8/8/K6k%20w%20-%20-%20'
            '0%201&amp;flip=true" TargetMode="External"') in relacoes
    assert documento.count("Analisar no Chess.com") == 1
    assert escritor_docx.conferir(caminho) == []


def test_o_conferir_do_docx_acusa_o_hiperlink_externo_sem_endereco(tmp_path):
    caminho = tmp_path / "livro.docx"
    escritor_docx.escrever(_paginas(), caminho, _metadados(), analise="lichess")
    quebrado = tmp_path / "quebrado.docx"
    with zipfile.ZipFile(caminho) as z, zipfile.ZipFile(quebrado, "w") as saida:
        for info in z.infolist():
            dados = z.read(info)
            if info.filename == "word/_rels/document.xml.rels":
                dados = dados.replace(b' TargetMode="External"', b"")
            saida.writestr(info, dados)
    assert any("endereço externo" in p for p in escritor_docx.conferir(quebrado))


def test_a_previa_mostra_o_link_como_o_arquivo(tmp_path):
    html = pv.html_do_livro(_paginas(), ["Relatório"], "Livro", analise="lichess")
    assert html.count("Analisar no Lichess") == 1
    assert "https://lichess.org/analysis/standard/" in html
    assert "Analisar no" not in pv.html_do_livro(_paginas(), ["Relatório"], "Livro")


def test_o_relatorio_conta_os_links(tmp_path):
    relatorio = ex.Relatorio(formato="epub")
    ex.exportar_epub(_paginas(), tmp_path / "livro.epub", titulo="Livro",
                     relatorio=relatorio, analise="chesscom")
    assert relatorio.analises == 1
    assert "1 diagrama(s) com link para o Chess.com" in relatorio.resumo()
    relatorio = ex.Relatorio(formato="docx")
    ex.exportar_docx(_paginas(), tmp_path / "livro.docx", titulo="Livro", relatorio=relatorio)
    assert relatorio.analises == 0 and "link para o" not in relatorio.resumo()


# ----------------------------------------------------------------------
# O diálogo

@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_o_dialogo_escolhe_o_site(app, tmp_path):
    from abbychess.app import dialogo_exportacao as de

    d = de.DialogoDeExportacao(None, "epub", ex.Opcoes(links_de_analise="chesscom"), {},
                               tmp_path, "T")
    assert [d.analise.itemText(i) for i in range(d.analise.count())] == \
        ["Nenhum", "Lichess", "Chess.com"]
    assert d.analise.currentData() == "chesscom" and d.analise.isEnabled()
    d.analise.setCurrentIndex(1)
    assert d.opcoes() == ex.Opcoes(links_de_analise="lichess")
    for formato in ("txt", "pgn", "pdf"):
        assert not de.DialogoDeExportacao(None, formato, ex.Opcoes(), {}, tmp_path,
                                          "T").analise.isEnabled()


def test_o_site_escolhido_e_lembrado(app, tmp_path):
    from PySide6.QtCore import QSettings

    from abbychess.app import dialogo_exportacao as de

    config = QSettings(str(tmp_path / "config.ini"), QSettings.Format.IniFormat)
    de.lembrar_opcoes(config, ex.Opcoes(so_verificadas=True, links_de_analise="lichess"))
    assert de.opcoes_lembradas(config) == ex.Opcoes(so_verificadas=True,
                                                    links_de_analise="lichess")
    # O que gravou a versão de antes (sem a escolha) e o valor que não vale mais: nenhum.
    config.setValue(de.CHAVE, "so_verificadas,desenhar_diagramas")
    assert de.opcoes_lembradas(config).links_de_analise == "nenhum"
    config.setValue(de.CHAVE, "links_de_analise=chess24")
    assert de.opcoes_lembradas(config) == ex.Opcoes(desenhar_diagramas=False)
