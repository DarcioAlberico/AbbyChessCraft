"""O diálogo da exportação e o `metadados.json` (§12.1, passo J)."""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from abbychess import exportar as ex  # noqa: E402
from abbychess import gravacao as gv  # noqa: E402
from abbychess.app import dialogo_exportacao as de  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _projeto(pasta):
    return SimpleNamespace(pasta=pasta, dados=SimpleNamespace(nome="Xadrez Vitorioso"))


def test_normalizar_tira_vazios_parte_as_listas_e_recusa_data_ruim():
    assert ex.normalizar_metadados({"titulo": "  T ", "autores": "A; ;B", "editora": "",
                                    "assuntos": [None, "X"], "outro": "fica de fora"}) == {
        "titulo": "T", "autores": ["A", "B"], "assuntos": ["X"]}
    with pytest.raises(ValueError, match="AAAA"):
        ex.normalizar_metadados({"data": "maio de 2012"})


def test_gravar_metadados_copia_a_capa_para_o_projeto(tmp_path):
    pasta = tmp_path / "projeto"
    pasta.mkdir()
    capa = tmp_path / "foto.JPG"
    capa.write_bytes(b"\xff\xd8\xffcapa")
    gravado = ex.gravar_metadados(_projeto(pasta), {"autores": "A; B", "data": "2012"}, capa)
    assert gravado == {"autores": ["A", "B"], "data": "2012", "capa": "capa.jpg"}
    assert (pasta / "capa.jpg").read_bytes() == b"\xff\xd8\xffcapa"
    assert json.loads((pasta / ex.ARQUIVO_DE_METADADOS).read_text(encoding="utf-8")) == gravado
    assert ex.ler_metadados(_projeto(pasta)) == gravado
    m = ex.metadados_do_projeto(_projeto(pasta), "pt-BR")
    assert m.autores == ("A", "B") and m.capa == b"\xff\xd8\xffcapa"


def test_projeto_so_de_leitura_recusa_gravar(tmp_path):
    gv.proteger(tmp_path)
    try:
        with pytest.raises(gv.SomenteLeitura):
            ex.gravar_metadados(_projeto(tmp_path), {"autores": "A"})
    finally:
        gv.liberar(tmp_path)


def test_o_dialogo_traz_o_arquivo_e_devolve_o_formulario(app, tmp_path):
    metadados = {"titulo": "Livro", "autores": ["A", "B"], "capa": "capa.png"}
    d = de.DialogoDeExportacao(None, "epub", ex.Opcoes(manter_margens=True), metadados,
                               tmp_path, "Padrão")
    assert d.autores.text() == "A; B" and d.capa.text() == "capa.png"
    assert d.manter_margens.isChecked() and d.desenhar.isEnabled()
    assert not d.marcas.isEnabled()
    d.editora.setText("Ciência Moderna")
    d.desenhar.setChecked(False)
    escolha = d.escolha()
    assert escolha.opcoes == ex.Opcoes(manter_margens=True, desenhar_diagramas=False)
    assert escolha.metadados == {"titulo": "Livro", "autores": ["A", "B"],
                                 "editora": "Ciência Moderna", "capa": "capa.png"}
    d._tirar_capa()
    assert "capa" not in d.metadados()


@pytest.mark.parametrize("formato,metadados,marcas,margens", [
    ("txt", False, True, True), ("pgn", False, False, False), ("pdf", False, False, False),
    ("docx", True, False, True)])
def test_o_que_vale_em_cada_formato(app, tmp_path, formato, metadados, marcas, margens):
    d = de.DialogoDeExportacao(None, formato, ex.Opcoes(), {}, tmp_path, "T")
    assert d.caixa_metadados.isEnabled() is metadados
    assert d.marcas.isEnabled() is marcas
    assert d.manter_margens.isEnabled() is margens
    assert d.so_verificadas.isEnabled() is (formato != "pdf")


def test_as_opcoes_sao_lembradas(app, tmp_path):
    config = QSettings(str(tmp_path / "config.ini"), QSettings.Format.IniFormat)
    assert de.opcoes_lembradas(config) == ex.Opcoes()
    de.lembrar_opcoes(config, ex.Opcoes(so_verificadas=True, desenhar_diagramas=False))
    assert de.opcoes_lembradas(config) == ex.Opcoes(so_verificadas=True,
                                                    desenhar_diagramas=False)
    de.lembrar_opcoes(config, ex.Opcoes(desenhar_diagramas=False))
    assert de.opcoes_lembradas(config) == ex.Opcoes(desenhar_diagramas=False)


# ----------------------------------------------------------------------
# A revisão de código (rodada 1)
# ----------------------------------------------------------------------

def test_gravar_mantem_as_chaves_proprias_e_troca_o_autor_antigo(tmp_path):
    (tmp_path / ex.ARQUIVO_DE_METADADOS).write_text(json.dumps(
        {"colecao": "Clássicos", "autor": "Velho", "editora": "X"}), encoding="utf-8")
    gravado = ex.gravar_metadados(_projeto(tmp_path), {"autores": "Novo", "editora": ""})
    assert gravado == {"colecao": "Clássicos", "autores": ["Novo"]}


def test_a_capa_nova_tira_a_de_outra_extensao_e_a_mesma_nao_e_recopiada(tmp_path):
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 10
    (tmp_path / "capa.png").write_bytes(png)
    ex.gravar_metadados(_projeto(tmp_path), {}, tmp_path / "capa.png")    # a mesma
    assert (tmp_path / "capa.png").read_bytes() == png
    jpg = tmp_path / "nova.jpg"
    jpg.write_bytes(b"\xff\xd8\xff" + b"y" * 10)
    gravado = ex.gravar_metadados(_projeto(tmp_path), {}, jpg)
    assert gravado["capa"] == "capa.jpg" and not (tmp_path / "capa.png").exists()


def test_capa_que_nao_e_imagem_e_recusada(tmp_path):
    falsa = tmp_path / "capa.png"
    falsa.write_bytes(b"isto nao e imagem")
    with pytest.raises(ValueError, match="não é uma imagem"):
        ex.gravar_metadados(_projeto(tmp_path), {}, falsa)


def test_metadados_ruins_escritos_a_mao_nao_travam_os_outros_formatos(app, tmp_path):
    ruins = {"data": "c. 1990", "autores": 5}
    for formato in ("pdf", "txt", "pgn"):
        d = de.DialogoDeExportacao(None, formato, ex.Opcoes(), ruins, tmp_path, "T")
        assert d.escolha().metadados == {}
    d = de.DialogoDeExportacao(None, "epub", ex.Opcoes(), ruins, tmp_path, "T")
    assert d.autores.text() == "5"
    with pytest.raises(ValueError):
        d.metadados()                                 # no EPUB a data ruim é recusada
    assert ex.normalizar_metadados({"autores": 5}) == {"autores": ["5"]}


def test_escolher_capa_nova_mantem_a_antiga_no_formulario(app, tmp_path):
    d = de.DialogoDeExportacao(None, "epub", ex.Opcoes(), {"capa": "capa.png"}, tmp_path, "T")
    d.capa_escolhida = tmp_path / "nova.jpg"
    d.capa.setText(str(d.capa_escolhida))
    escolha = d.escolha()
    assert escolha.metadados == {"capa": "capa.png"} and escolha.capa == tmp_path / "nova.jpg"