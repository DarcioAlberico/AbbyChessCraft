"""A exportação lê o Documento (§12.1, passo J): funções das áreas, estilos, parágrafo e
hífen decididos; o TXT, o PGN (CA-12.2), o relatório (§12.2) e os bytes iguais (CA-12.6)."""

from __future__ import annotations

import io
import zipfile
from dataclasses import replace

import chess.pgn
import pytest

from core.box_model import BoxEntry

from abbychess import exportar as ex
from abbychess import lances as lc
from abbychess import texto as tx
from abbychess.leitor import FONTE_MANUAL
from abbychess.modelo import Decisoes, Estilo
from abbychess.zonas import Zona

from tests.test_diagramas import _lido
from tests.test_lances import P25, TEXTO_P25
from tests.test_livro import _ensinar_e_ler, fonte, leitor, projeto  # noqa: F401 (fixtures)


def _linha(texto: str, y: int, x: int = 40):
    boxes, cursor = [], x
    for char in texto:
        if char != " ":
            boxes.append(BoxEntry(char, cursor, y, cursor + 10, y + 20, 1.0, FONTE_MANUAL))
        cursor += 14
    return boxes


def _pagina():
    """Cabeçalho, título, um parágrafo com negrito e hífen de quebra, outro pedido."""
    linhas = [("XADREZ VITORIOSO 23", 10), ("Capitulo um", 100),
              ("O texto vai em negrito e o hi-", 200), ("Fen termina aqui.", 240),
              ("Outro paragrafo comeca.", 280)]
    entries = [b for texto, y in linhas for b in _linha(texto, y)]
    zonas = [Zona("texto", 0, 0, 1000, 40, funcao="cabecalho"),
             Zona("texto", 0, 90, 1000, 130, funcao="titulo"),
             Zona("texto", 0, 190, 1000, 330)]
    pagina = tx.pagina_avulsa(entries, zonas=zonas)
    # "negrito": as 7 letras da palavra, na linha de y=200.
    inicio = len("O texto vai em ")
    linha200 = [b for b in pagina.boxes if b.entry.y1 == 200]
    alvo = {b.gid for b in linha200[len("Otextovaiem"):len("Otextovaiemnegrito")]}
    pagina.boxes = [replace(b, estilo=Estilo(negrito=True)) if b.gid in alvo else b
                    for b in pagina.boxes]
    hifen = linha200[-1].gid
    outro = next(b.gid for b in pagina.boxes if b.entry.y1 == 280)
    pagina.decisoes = Decisoes(hifen_de_quebra=frozenset({hifen}),
                               paragrafo_antes=frozenset({outro}))
    return pagina, inicio


def _paragrafos(pagina_extraida):
    return [b for b in pagina_extraida.blocos if isinstance(b, ex.Paragrafo)]


def test_a_exportacao_segue_as_areas_os_estilos_e_as_decisoes():
    pagina, inicio = _pagina()
    entries, estrutura = ex.Estrutura.da_pagina(pagina)
    assert estrutura.funcao(entries[0]) == "cabecalho"
    paragrafos = _paragrafos(ex.pagina_extraida(0, entries, estrutura=estrutura))
    assert [p.texto for p in paragrafos] == [
        "Capitulo um", "O texto vai em negrito e o hiFen termina aqui.",
        "Outro paragrafo comeca."]
    titulo, corpo, outro = paragrafos
    assert titulo.titulo and titulo.nivel == 1
    assert not corpo.titulo and not outro.titulo
    assert corpo.negrito == [(inicio, inicio + len("negrito"))]
    assert corpo.texto[slice(*corpo.negrito[0])] == "negrito"


def test_manter_margens_deixa_o_cabecalho_da_area():
    pagina, _ = _pagina()
    entries, estrutura = ex.Estrutura.da_pagina(pagina)
    textos = [p.texto for p in _paragrafos(ex.pagina_extraida(0, entries, estrutura=estrutura,
                                                              manter_margens=True))]
    assert textos[0] == "XADREZ VITORIOSO 23"


def test_sem_estrutura_a_pagina_sai_como_antes():
    pagina, _ = _pagina()
    entries = [b.entry for b in pagina.boxes]
    textos = [p.texto for p in _paragrafos(ex.pagina_extraida(0, entries))]
    assert "XADREZ VITORIOSO 23" in textos[0]
    assert not any(p.titulo for p in _paragrafos(ex.pagina_extraida(0, entries)))


def test_area_ignorar_sai_sempre():
    entries = _linha("Texto que fica.", 10) + _linha("respingo", 300)
    pagina = tx.pagina_avulsa(entries, zonas=[Zona("ignorar", 0, 290, 1000, 330)])
    entries, estrutura = ex.Estrutura.da_pagina(pagina)
    for manter in (False, True):
        textos = [p.texto for p in _paragrafos(ex.pagina_extraida(
            0, entries, estrutura=estrutura, manter_margens=manter))]
        assert textos == ["Texto que fica."]


# ----------------------------------------------------------------------
# TXT
# ----------------------------------------------------------------------

def test_txt_tem_um_paragrafo_por_bloco_e_as_marcas_de_pagina():
    pagina, _ = _pagina()
    entries, estrutura = ex.Estrutura.da_pagina(pagina)
    extraida = ex.pagina_extraida(4, entries, estrutura=estrutura)
    assert ex.texto_do_livro([extraida]) == (
        "Capitulo um\n\nO texto vai em negrito e o hiFen termina aqui.\n\n"
        "Outro paragrafo comeca.\n")
    assert ex.texto_do_livro([extraida], marcas_de_pagina=True).startswith(
        "[p. 5]\n\nCapitulo um")


def test_txt_do_projeto_com_relatorio(projeto, fonte, leitor, tmp_path):  # noqa: F811
    _ensinar_e_ler(projeto, fonte, leitor)
    destino = tmp_path / "livro.txt"
    resumo, relatorio = ex.exportar_com_relatorio(projeto, destino)
    texto = destino.read_text(encoding="utf-8")
    assert "abc abc abc" in texto and texto.endswith("\n")
    assert relatorio.paginas and resumo.startswith(f"{len(relatorio.paginas)} página(s)")
    # Nenhuma página foi verificada: todas vão ao relatório.
    assert relatorio.nao_verificadas == relatorio.paginas
    assert "Páginas não verificadas" in relatorio.texto()


def test_so_verificadas_sem_nenhuma_nao_exporta(projeto, fonte, leitor, tmp_path):  # noqa: F811
    _ensinar_e_ler(projeto, fonte, leitor)
    with pytest.raises(ex.NadaParaExportar, match="verificada"):
        ex.exportar(projeto, tmp_path / "x.txt", opcoes=ex.Opcoes(so_verificadas=True))


# ----------------------------------------------------------------------
# PGN (CA-12.2)
# ----------------------------------------------------------------------

class _Dados:
    nome = "Xadrez Vitorioso"


class _ProjetoFalso:
    """O que `pgn_do_livro` lê do projeto: as páginas lidas e o modelo de cada uma."""

    dados = _Dados()

    def __init__(self, modelos):
        self.modelos = modelos

    def paginas_lidas(self):
        return sorted(self.modelos)

    def carregar_modelo(self, i):
        return self.modelos.get(i)


def _com_validacao(d, texto, lado=None):
    linha = lc.primeira_linha(texto, "pt")
    return replace(d, validacao=lc.validar(d.fen, linha, lado=lado))


def test_ca_12_2_o_pgn_do_diagrama_conferido_com_lances():
    conferido = replace(_lido(P25, caixa=(0, 0, 400, 400)), conferido=True, lado="b",
                        lado_origem="usuario")
    conferido = _com_validacao(conferido, TEXTO_P25, lado="b")
    sem_conferir = _lido(caixa=(0, 500, 400, 900))
    pagina = tx.pagina_avulsa([], [conferido, sem_conferir])
    pagina.tabuleiros = [(0, 0, 400, 400), (0, 500, 400, 900)]
    relatorio = ex.Relatorio(formato="pgn")
    texto = ex.pgn_do_livro(_ProjetoFalso({24: pagina}), relatorio=relatorio)

    jogo = chess.pgn.read_game(io.StringIO(texto))
    assert jogo.errors == []
    assert jogo.headers["SetUp"] == "1"
    assert jogo.headers["FEN"] == conferido.fen.replace(" - - 0 1", " - - 0 10")
    assert jogo.headers["Page"] == "25" and jogo.headers["Diagram"] == "1"
    assert jogo.headers["Event"] == "Xadrez Vitorioso"
    assert [m.uci() for m in jogo.mainline_moves()][:2] == ["e8f8", "f3d5"]   # Rf8 Dd5
    assert chess.pgn.NAG_BLUNDER in jogo.next().next().nags        # 11.Dd5??
    assert relatorio.no_pgn == 1
    assert relatorio.fora_do_pgn == [(24, 2, "nem conferido nem confiável pelos lances")]
    assert "p. 25: diagrama 2 fora do PGN" in relatorio.texto()


# ----------------------------------------------------------------------
# Os mesmos bytes (CA-12.6)
# ----------------------------------------------------------------------

def test_ca_12_6_duas_exportacoes_iguais_byte_a_byte(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    pagina, _ = _pagina()
    entries, estrutura = ex.Estrutura.da_pagina(pagina)
    paginas = [ex.pagina_extraida(0, entries, estrutura=estrutura)]
    a, b = tmp_path / "a.epub", tmp_path / "b.epub"
    ex.exportar_epub(paginas, a, titulo="T")
    ex.exportar_epub(paginas, b, titulo="T")
    assert a.read_bytes() == b.read_bytes()
    with zipfile.ZipFile(a) as z:
        nav = z.read("OEBPS/nav.xhtml").decode("utf-8")
    assert "Capitulo um" in nav                        # o título da área vira o sumário
    c, d = tmp_path / "c.docx", tmp_path / "d.docx"
    ex.exportar_docx(paginas, c, titulo="T")
    ex.exportar_docx(paginas, d, titulo="T")
    assert c.read_bytes() == d.read_bytes()
    assert ex.texto_do_livro(paginas) == ex.texto_do_livro(paginas)


# ----------------------------------------------------------------------
# A revisão de código (rodada 1)
# ----------------------------------------------------------------------

def test_o_negrito_que_acaba_no_hifen_nao_cobre_a_linha_seguinte():
    a = ex._Linha("inter-", 0, 10, hifen=True, negrito=[(0, 6)])
    b = ex._Linha("essante fim", 20, 30)
    assert ex._juntar([a, b]) == ("interessante fim", [(0, 5)], [], [])


def test_a_juncao_dos_trechos_so_atravessa_espaco():
    assert ex._unir_trechos([(0, 1), (2, 3)], "abc") == [(0, 1), (2, 3)]
    assert ex._unir_trechos([(0, 2), (3, 5)], "ab cd") == [(0, 5)]


def test_pagina_sem_modelo_nao_derruba():
    entries, estrutura = ex.Estrutura.da_pagina(None)
    assert entries == [] and estrutura.funcoes == {}


def test_area_de_texto_do_usuario_protege_da_regra_das_margens():
    entries = _linha("Linha marcada pelo usuario", 10)
    pagina = tx.pagina_avulsa(entries, zonas=[Zona("texto", 0, 0, 1000, 40)])
    lidos, estrutura = ex.Estrutura.da_pagina(pagina)
    assert all(id(b) in estrutura.protegidos for b in lidos)
    automatica = tx.pagina_avulsa(entries, zonas=[Zona("texto", 0, 0, 1000, 40,
                                                       automatica=True)])
    lidos, estrutura = ex.Estrutura.da_pagina(automatica)
    assert not estrutura.protegidos


def test_relatorio_do_pdf_e_o_resumo_dele():
    r = ex.Relatorio(formato="pdf", resumo_do_pdf="2 página(s), 40 caracteres na camada.")
    assert r.resumo() == r.texto() == "2 página(s), 40 caracteres na camada."


def test_pgn_recusa_posicao_ilegal_mesmo_conferida():
    sem_rei = replace(_lido("8/8/8/8/8/8/8/8", caixa=(0, 0, 400, 400)), conferido=True)
    pagina = tx.pagina_avulsa([], [sem_rei])
    pagina.tabuleiros = [(0, 0, 400, 400)]
    relatorio = ex.Relatorio(formato="pgn")
    assert ex.pgn_do_livro(_ProjetoFalso({0: pagina}), relatorio=relatorio) == ""
    assert relatorio.fora_do_pgn == [(0, 1, "a posição não é legal")]