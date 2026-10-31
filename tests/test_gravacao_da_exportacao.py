"""A gravação dos arquivos exportados (SPEC-qualidade CA-Q-E3 e CA-Q-E4), pela porta de
entrada da exportação: cada formato grava ao lado, troca com as novas tentativas da gravação
do projeto, não deixa temporário, e o EPUB que não passa na conferência não troca o
anterior."""

from __future__ import annotations

import pytest

from abbychess import epub
from abbychess import exportar as ex
from abbychess import gravacao as gv

from tests.test_livro import _ensinar_e_ler, fonte, leitor, projeto  # noqa: F401 (fixtures)

FORMATOS = ("txt", "docx", "epub", "pdf")


@pytest.fixture
def lido(projeto, fonte, leitor, monkeypatch):  # noqa: F811
    monkeypatch.setattr(gv, "ESPERA", 0.0)
    _ensinar_e_ler(projeto, fonte, leitor)
    return projeto


@pytest.fixture
def saida(tmp_path):
    """Uma pasta só das saídas (o PDF de origem do projeto mora em `tmp_path`)."""
    pasta = tmp_path / "saida"
    pasta.mkdir()
    return pasta


def test_ca_q_e3_o_epub_que_nao_passa_na_conferencia_nao_troca_o_anterior(lido, saida,
                                                                          monkeypatch):
    destino = saida / "livro.epub"
    ex.exportar_com_relatorio(lido, destino)
    anterior = destino.read_bytes()
    monkeypatch.setattr(epub, "conferir", lambda caminho: ["o sumário aponta para o nada"])
    with pytest.raises(ValueError, match="sumário"):
        ex.exportar_com_relatorio(lido, destino)
    assert destino.read_bytes() == anterior
    assert sorted(p.name for p in saida.iterdir()) == ["livro.epub"]


@pytest.mark.parametrize("formato", FORMATOS)
def test_ca_q_e4_a_troca_presa_tenta_de_novo(lido, saida, monkeypatch, formato):
    """O Word ou o leitor de PDF com o arquivo anterior aberto: a troca falha com
    `PermissionError` duas vezes e passa na terceira, como a gravação do projeto."""
    trocar, tentativas = gv._trocar, []
    destino = saida / f"livro.{formato}"

    def preso(temporario, caminho):             # só o arquivo exportado está aberto
        if caminho == destino:
            tentativas.append(caminho)
            if len(tentativas) <= 2:
                raise PermissionError("o arquivo está aberto em outro programa")
        trocar(temporario, caminho)

    monkeypatch.setattr(gv, "_trocar", preso)
    ex.exportar_com_relatorio(lido, destino)
    assert destino.stat().st_size > 0 and len(tentativas) == 3
    assert sorted(p.name for p in saida.iterdir()) == [destino.name]


@pytest.mark.parametrize("formato", FORMATOS)
def test_ca_q_e4_a_falha_nao_deixa_temporario_nem_troca_o_anterior(lido, saida,
                                                                   monkeypatch, formato):
    destino = saida / f"livro.{formato}"
    destino.write_bytes(b"o anterior")
    trocar = gv._trocar

    def preso(temporario, caminho):             # só o arquivo exportado está aberto
        if caminho == destino:
            raise PermissionError("o arquivo está aberto em outro programa")
        trocar(temporario, caminho)

    monkeypatch.setattr(gv, "_trocar", preso)
    with pytest.raises(PermissionError):
        ex.exportar_com_relatorio(lido, destino)
    assert destino.read_bytes() == b"o anterior"
    assert sorted(p.name for p in saida.iterdir()) == [destino.name]
