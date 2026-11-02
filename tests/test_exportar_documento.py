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
from abbychess import montagem as mo
from abbychess import lances as lc
from abbychess import texto as tx
from abbychess.leitor import FONTE_MANUAL
from abbychess.modelo import VERIFICADA, Decisoes, Estilo
from abbychess.zonas import Zona

from tests.ajudantes import _lido  # noqa: E402,F401,F811
from tests.ajudantes import P25, TEXTO_P25  # noqa: E402,F401,F811
from tests.ajudantes import _ensinar_e_ler  # noqa: E402,F401,F811


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
    entries, estrutura = mo.Estrutura.da_pagina(pagina)
    assert estrutura.funcao(entries[0]) == "cabecalho"
    paragrafos = _paragrafos(mo.pagina_extraida(0, entries, estrutura=estrutura))
    assert [p.texto for p in paragrafos] == [
        "Capitulo um", "O texto vai em negrito e o hiFen termina aqui.",
        "Outro paragrafo comeca."]
    titulo, corpo, outro = paragrafos
    assert titulo.titulo and titulo.nivel == 1
    assert not corpo.titulo and not outro.titulo
    assert corpo.negrito == [(inicio, inicio + len("negrito"))]
    assert corpo.texto[slice(*corpo.negrito[0])] == "negrito"


def test_ca_q_e1_a_exportacao_leva_as_decisoes_de_palavra_do_documento():
    """SPEC-qualidade CA-Q-E1 (§12.1: a exportação lê o Documento): a letra digitada à mão
    (o virtual, sem box), a palavra partida pelo usuário e os lances que o OCR colou saem no
    texto exportado como no Documento, e não como a geometria dos boxes os junta."""
    from abbychess.modelo import GlifoVirtual

    pagina = tx.pagina_avulsa(_linha("o cavlo vai a f6 maisum ♘f62.c4 fim", 10))
    gid_do = {b.entry.x1: b.gid for b in pagina.boxes}
    x_do_v = 40 + 14 * len("o cav") - 14              # o "v" de "cavlo"
    x_do_u = 40 + 14 * len("o cavlo vai a f6 mais")   # o "u" de "maisum"
    pagina.decisoes = Decisoes(
        quebras=frozenset({gid_do[x_do_u]}),
        virtuais=(GlifoVirtual(pagina.alocar(), "a", gid_do[x_do_v]),))
    documento = tx.texto(tx.montar(pagina))
    assert documento == "o cavalo vai a f6 mais um ♘f6 2.c4 fim"

    entries, estrutura = mo.Estrutura.da_pagina(pagina)
    extraida = mo.pagina_extraida(0, entries, estrutura=estrutura)
    assert [p.texto for p in _paragrafos(extraida)] == [documento]
    assert ex.texto_do_livro([extraida]) == documento + "\n"


def test_ca_q_e1_a_palavra_digitada_sozinha_sai_no_lugar_dela():
    """O virtual que abre palavra (sem glifo nenhum dela na linha) sai depois da palavra do
    Documento que vem antes dele, como no texto do Documento."""
    from abbychess.modelo import GlifoVirtual

    pagina = tx.pagina_avulsa(_linha("ab cd", 10))
    gid_do = {b.entry.char: b.gid for b in pagina.boxes}
    pagina.decisoes = Decisoes(virtuais=(GlifoVirtual(pagina.alocar(), "Z", gid_do["b"],
                                                      palavra_nova=True),))
    documento = tx.texto(tx.montar(pagina))
    assert documento == "ab Z cd"
    entries, estrutura = mo.Estrutura.da_pagina(pagina)
    assert [p.texto for p in _paragrafos(mo.pagina_extraida(0, entries, estrutura=estrutura))] \
        == [documento]


def test_ca_q_e1_o_glifo_nao_lido_no_meio_da_palavra_fica_como_no_texto_do_documento():
    """O glifo que ninguém leu (sem caractere) não entra no texto nem na exportação: a
    palavra fica partida no buraco dele, como no `texto.montar` (a vista do Documento, que o
    mostra, não é a referência). Na fatia do xv, "ca o", "princ pio" e "Dia rama" saíam
    juntos ("cao") quando as palavras vinham da vista."""
    entries = _linha("nesse caso fica", 10)
    x_do_s = 40 + 14 * len("nesse ca")
    for b in entries:
        if b.x1 == x_do_s:
            b.char = ""                                  # o "s" que ninguém leu
    pagina = tx.pagina_avulsa(entries)
    documento = tx.texto(tx.montar(pagina))
    entries, estrutura = mo.Estrutura.da_pagina(pagina)
    assert [p.texto for p in _paragrafos(mo.pagina_extraida(0, entries, estrutura=estrutura))] \
        == [documento]


def test_manter_margens_deixa_o_cabecalho_da_area():
    pagina, _ = _pagina()
    entries, estrutura = mo.Estrutura.da_pagina(pagina)
    textos = [p.texto for p in _paragrafos(mo.pagina_extraida(0, entries, estrutura=estrutura,
                                                              manter_margens=True))]
    assert textos[0] == "XADREZ VITORIOSO 23"


def test_sem_estrutura_a_pagina_sai_como_antes():
    pagina, _ = _pagina()
    entries = [b.entry for b in pagina.boxes]
    textos = [p.texto for p in _paragrafos(mo.pagina_extraida(0, entries))]
    assert "XADREZ VITORIOSO 23" in textos[0]
    assert not any(p.titulo for p in _paragrafos(mo.pagina_extraida(0, entries)))


def test_area_ignorar_sai_sempre():
    entries = _linha("Texto que fica.", 10) + _linha("respingo", 300)
    pagina = tx.pagina_avulsa(entries, zonas=[Zona("ignorar", 0, 290, 1000, 330)])
    entries, estrutura = mo.Estrutura.da_pagina(pagina)
    for manter in (False, True):
        textos = [p.texto for p in _paragrafos(mo.pagina_extraida(
            0, entries, estrutura=estrutura, manter_margens=manter))]
        assert textos == ["Texto que fica."]


# ----------------------------------------------------------------------
# TXT
# ----------------------------------------------------------------------

def test_txt_tem_um_paragrafo_por_bloco_e_as_marcas_de_pagina():
    pagina, _ = _pagina()
    entries, estrutura = mo.Estrutura.da_pagina(pagina)
    extraida = mo.pagina_extraida(4, entries, estrutura=estrutura)
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


def test_so_verificadas_leva_so_a_verificada(projeto, fonte, leitor, tmp_path):  # noqa: F811
    _ensinar_e_ler(projeto, fonte, leitor)
    pagina = projeto.carregar_modelo(1)
    pagina.estado = VERIFICADA
    projeto.salvar_modelo(pagina)
    _, todas = ex.exportar_com_relatorio(projeto, tmp_path / "todas.txt")
    _, so = ex.exportar_com_relatorio(projeto, tmp_path / "so.txt",
                                      opcoes=ex.Opcoes(so_verificadas=True))
    assert todas.paginas == [0, 1, 2]
    assert so.paginas == [1] and so.nao_verificadas == []
    assert "Páginas não verificadas" not in so.texto()


def test_ca_q_e2_o_pdf_pesquisavel_tambem_leva_so_as_verificadas(projeto, fonte, leitor,  # noqa: F811
                                                                 tmp_path):
    """SPEC-qualidade CA-Q-E2: "só as páginas verificadas" vale no PDF pesquisável como nos
    outros formatos; sem nenhuma verificada, ele também não exporta."""
    import fitz

    _ensinar_e_ler(projeto, fonte, leitor)
    so = ex.Opcoes(so_verificadas=True)
    with pytest.raises(ex.NadaParaExportar, match="verificada"):
        ex.exportar_com_relatorio(projeto, tmp_path / "nenhuma.pdf", opcoes=so)
    pagina = projeto.carregar_modelo(1)
    pagina.estado = VERIFICADA
    projeto.salvar_modelo(pagina)
    ex.exportar_com_relatorio(projeto, tmp_path / "so.pdf", opcoes=so)
    with fitz.open(tmp_path / "so.pdf") as doc:
        assert len(doc) == 1


def test_o_pgn_sem_diagrama_nao_troca_o_anterior(projeto, fonte, leitor, tmp_path):  # noqa: F811
    _ensinar_e_ler(projeto, fonte, leitor)
    destino = tmp_path / "livro.pgn"
    destino.write_text("o PGN bom de antes\n", encoding="utf-8")
    with pytest.raises(ex.NadaParaExportar, match="Nenhum diagrama"):
        ex.exportar_com_relatorio(projeto, destino)
    assert destino.read_text(encoding="utf-8") == "o PGN bom de antes\n"
    # Com um diagrama conferido, o PGN troca o anterior.
    modelo = projeto.carregar_modelo(1)
    modelo.tabuleiros = [(0, 0, 400, 400)]
    modelo.diagramas = [replace(_lido(P25, caixa=(0, 0, 400, 400)), conferido=True, lado="b",
                                lado_origem="usuario")]
    projeto.salvar_modelo(modelo)
    resumo, relatorio = ex.exportar_com_relatorio(projeto, destino)
    assert resumo == "1 diagrama(s) com a posição e os lances."
    assert relatorio.no_pgn == 1 and '[Page "2"]' in destino.read_text(encoding="utf-8")


def test_a_funcao_da_linha_empatada_nao_depende_do_processo():
    """O empate entre duas funções sai pela primeira, igual em todo processo (CA-12.6)."""
    import os
    import subprocess
    import sys
    codigo = ("from tests.test_exportar_documento import _funcao_empatada; "
              "print(_funcao_empatada())")
    saidas = set()
    for semente in ("1", "2", "3", "4", "5", "6"):
        ambiente = dict(os.environ, PYTHONHASHSEED=semente)
        saidas.add(subprocess.run([sys.executable, "-c", codigo], env=ambiente, check=True,
                                  capture_output=True, text=True).stdout.strip())
    assert saidas == {"titulo"}


def _funcao_empatada() -> str:
    """Uma linha com metade das letras numa área de título e metade numa de texto."""
    entries = _linha("abcd efgh", 100)
    zonas = [Zona("texto", 0, 90, 90, 130, funcao="titulo"),
             Zona("texto", 90, 90, 1000, 130)]
    pagina = tx.pagina_avulsa(entries, zonas=zonas)
    lidos, estrutura = mo.Estrutura.da_pagina(pagina)
    return mo._linhas(lidos, ex.OrdemDeLeitura(), estrutura)[0].funcao


# ----------------------------------------------------------------------
# PGN (CA-12.2)
# ----------------------------------------------------------------------

class _Dados:
    nome = "Xadrez Vitorioso"


class _ProjetoFalso:
    """O que `pgn_do_livro` lê do projeto: as páginas lidas e o modelo de cada uma (o
    resumo do livro é o próprio falso)."""

    dados = _Dados()

    def __init__(self, modelos):
        self.modelos = modelos
        self.resumo = self

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
    assert "página 25: diagrama 2 fora do PGN" in relatorio.texto()


class _ProjetoComEstados(_ProjetoFalso):
    def __init__(self, modelos, verificadas):
        super().__init__(modelos)
        self.verificadas = verificadas

    def do_livro(self):
        return {i: {"estado": VERIFICADA if i in self.verificadas else "reconhecida"}
                for i in self.modelos}


def test_so_verificadas_no_pgn_leva_so_o_diagrama_da_verificada():
    def pagina():
        conferido = replace(_lido(P25, caixa=(0, 0, 400, 400)), conferido=True, lado="b",
                            lado_origem="usuario")
        p = tx.pagina_avulsa([], [conferido])
        p.tabuleiros = [(0, 0, 400, 400)]
        return p
    projeto_falso = _ProjetoComEstados({24: pagina(), 30: pagina()}, verificadas={24})
    relatorio = ex.Relatorio(formato="pgn")
    texto = ex.pgn_do_livro(projeto_falso, relatorio=relatorio,
                            opcoes=ex.Opcoes(so_verificadas=True))
    assert texto.count("[Page ") == 1 and '[Page "25"]' in texto
    assert relatorio.no_pgn == 1
    assert ex.pgn_do_livro(projeto_falso, relatorio=ex.Relatorio(formato="pgn")).count(
        "[Page ") == 2



# ----------------------------------------------------------------------
# Os mesmos bytes (CA-12.6)
# ----------------------------------------------------------------------

def test_ca_12_6_duas_exportacoes_iguais_byte_a_byte(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    pagina, _ = _pagina()
    entries, estrutura = mo.Estrutura.da_pagina(pagina)
    paginas = [mo.pagina_extraida(0, entries, estrutura=estrutura)]
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
    a = mo._Linha("inter-", 0, 10, hifen=True, negrito=[(0, 6)])
    b = mo._Linha("essante fim", 20, 30)
    assert mo._juntar([a, b]) == ("interessante fim", [(0, 5)], [], [])


def test_a_juncao_dos_trechos_so_atravessa_espaco():
    assert mo._unir_trechos([(0, 1), (2, 3)], "abc") == [(0, 1), (2, 3)]
    assert mo._unir_trechos([(0, 2), (3, 5)], "ab cd") == [(0, 5)]


def test_pagina_sem_modelo_nao_derruba():
    entries, estrutura = mo.Estrutura.da_pagina(None)
    assert entries == [] and estrutura.funcoes == {}


def test_area_de_texto_do_usuario_protege_da_regra_das_margens():
    entries = _linha("Linha marcada pelo usuario", 10)
    pagina = tx.pagina_avulsa(entries, zonas=[Zona("texto", 0, 0, 1000, 40)])
    lidos, estrutura = mo.Estrutura.da_pagina(pagina)
    assert all(id(b) in estrutura.protegidos for b in lidos)
    automatica = tx.pagina_avulsa(entries, zonas=[Zona("texto", 0, 0, 1000, 40,
                                                       automatica=True)])
    lidos, estrutura = mo.Estrutura.da_pagina(automatica)
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


def test_o_pgn_diz_por_que_cada_diagrama_ficou_de_fora():
    """Entra o confiável pelos lances, sem conferir; ficam de fora, com o motivo, o que os
    lances desmentem, o não lido (com o erro da leitura, ou sem ele) e o de FEN que o
    python-chess recusa (o lado estragado no arquivo)."""
    caixas = [(0, 500 * k, 400, 500 * k + 400) for k in range(5)]
    pelos_lances = _com_validacao(_lido(P25, caixa=caixas[0], lado="b"), TEXTO_P25, lado="b")
    desmentido = _com_validacao(_lido(P25, caixa=caixas[1], lado="b"), "10...Txf8 11.Dxh7",
                                lado="b")
    sem_modelo = ex.DiagramaLido(caixas[2], erro="o modelo de diagramas não carregou")
    nao_lido = ex.DiagramaLido(caixas[3])
    lado_estragado = replace(_lido(P25, caixa=caixas[4]), conferido=True, lado="x")
    pagina = tx.pagina_avulsa([], [pelos_lances, desmentido, sem_modelo, nao_lido,
                                   lado_estragado])
    pagina.tabuleiros = caixas
    relatorio = ex.Relatorio(formato="pgn")
    texto = ex.pgn_do_livro(_ProjetoFalso({0: pagina}), relatorio=relatorio)
    assert texto.count("[Page ") == 1 and '[Diagram "1"]' in texto
    assert relatorio.fora_do_pgn == [(0, 2, "10...Txf8 do texto não é legal aqui"),
                                     (0, 3, "o modelo de diagramas não carregou"),
                                     (0, 4, "não lido"), (0, 5, "a posição não é legal")]

# ----------------------------------------------------------------------
# A revisão de produto do fechamento (rodada 1)
# ----------------------------------------------------------------------

def test_o_intervalo_leva_so_as_paginas_dele(projeto, fonte, leitor, tmp_path):  # noqa: F811
    _ensinar_e_ler(projeto, fonte, leitor)
    _, relatorio = ex.exportar_com_relatorio(projeto, tmp_path / "meio.txt",
                                             opcoes=ex.Opcoes(intervalo=(1, 2)))
    assert relatorio.paginas == [1, 2]
    _, previa = ex.previa(projeto, "epub", opcoes=ex.Opcoes(intervalo=(2, 2)))
    assert previa.paginas == [2]
    with pytest.raises(ValueError):
        ex.Opcoes(intervalo=(3, 1))


def test_o_dialogo_devolve_o_intervalo():
    import os
    from pathlib import Path

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from abbychess.app.dialogo_exportacao import DialogoDeExportacao, lembrar_opcoes

    QApplication.instance() or QApplication([])
    dialogo = DialogoDeExportacao(None, "epub", ex.Opcoes(), {}, Path("."), "T", 300)
    assert dialogo.opcoes().intervalo is None               # todas, de saída
    dialogo.primeira.setValue(30)                           # mexer no número escolhe "Da página"
    dialogo.ultima.setValue(12)
    assert dialogo.de_ate.isChecked()
    assert dialogo.opcoes().intervalo == (11, 29)           # a ordem trocada se acerta

    class _Config(dict):
        def setValue(self, chave, valor):
            self[chave] = valor
    config = _Config()
    lembrar_opcoes(config, dialogo.opcoes())
    assert "intervalo" not in next(iter(config.values()))   # não se lembra
    sem_total = DialogoDeExportacao(None, "epub", ex.Opcoes(), {}, Path("."), "T")
    assert sem_total.caixa_paginas.isHidden() and sem_total.opcoes().intervalo is None
    dialogo.deleteLater()
    sem_total.deleteLater()


def test_cada_item_do_relatorio_leva_a_pagina_dele():
    """Critério 7: cada página com o que houve nela (o número impresso quando difere), uma
    linha por página, e o duplo clique em Avisos acha a página pelo texto da linha."""
    from abbychess.app.busca_na_janela import lugar_do_aviso

    r = ex.Relatorio(formato="epub", recortados=[(24, "não lido"), (30, "não lido")],
                     sinalizadas={24: 3}, pendentes={30: 2}, numeros_impressos={24: 23})
    linhas = r.linhas()
    assert linhas[1:] == [
        "p. 23, página 25: diagrama como recorte (não lido); 3 palavra(s) sinalizada(s)",
        "página 31: diagrama como recorte (não lido); 2 glifo(s) pendente(s)"]
    assert "3 palavra(s) sinalizada(s)" in r.resumo()
    assert [lugar_do_aviso(linha)[0] for linha in linhas[1:]] == [24, 30]


def test_as_palavras_sinalizadas_contam_sem_o_realce(projeto, fonte, leitor, tmp_path):  # noqa: F811
    _ensinar_e_ler(projeto, fonte, leitor)
    _, relatorio = ex.exportar_com_relatorio(projeto, tmp_path / "livro.txt")
    _, com_realce = ex.exportar_com_relatorio(projeto, tmp_path / "livro.docx",
                                              opcoes=ex.Opcoes(realcar_duvidosos=True))
    assert relatorio.sinalizadas == com_realce.sinalizadas


def test_ca_12_6_o_pdf_pesquisavel_sai_igual(projeto, fonte, leitor, tmp_path,  # noqa: F811
                                            monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    _ensinar_e_ler(projeto, fonte, leitor)
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    ex.exportar_com_relatorio(projeto, a)
    ex.exportar_com_relatorio(projeto, b)
    assert a.read_bytes() == b.read_bytes()


def test_o_intervalo_do_dialogo_vai_ate_a_ultima_pagina_do_livro(tmp_path, monkeypatch):
    """O livro com páginas inseridas é maior que o PDF: o intervalo vai até a última da
    sequência (as posições que `Opcoes.intervalo` usa), não até a última do PDF."""
    import os
    from types import SimpleNamespace

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from abbychess.app import dialogo_exportacao as de

    QApplication.instance() or QApplication([])
    maximos = []
    monkeypatch.setattr(de.DialogoDeExportacao, "exec",
                        lambda d: maximos.append(d.ultima.maximum()) or 0)

    class _Config(dict):
        def value(self, chave, padrao=None):
            return self.get(chave, padrao)
    falso = SimpleNamespace(sequencia=list(range(61)), pasta=tmp_path,
                            dados=SimpleNamespace(nome="Livro"),
                            total_de_paginas=lambda: 60)
    from PySide6.QtWidgets import QWidget

    janela = QWidget()                                  # o pai do diálogo
    janela.config, janela.livro = _Config(), None
    assert de.perguntar(janela, falso, tmp_path / "livro.epub") is None
    assert maximos == [61]
