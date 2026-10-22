"""O escritor próprio de EPUB (passo J): capítulos, sumário, páginas, marcos, metadados,
acessibilidade calculada, imagens sem repetição, os mesmos bytes e a conferência."""

from __future__ import annotations

import io
import json
import os
import zipfile
from types import SimpleNamespace

import pytest
from PIL import Image

from core.pagina import Figura, PaginaExtraida, Paragrafo

from abbychess import epub
from abbychess import exportar as ex

FEN = "r3k2r/pp3ppp/2n5/3q4/3P4/2N2N2/PP3PPP/R3K2R w - - 0 1"


def _png(cor: int = 0) -> bytes:
    dados = io.BytesIO()
    Image.new("L", (8, 8), cor).save(dados, format="PNG")
    return dados.getvalue()


def _livro():
    desenho = Figura(_png(0), 8, 8, fen=FEN, origem="render", lado_a_jogar="b",
                     lado_origem="usuario")
    igual = Figura(_png(0), 8, 8, fen=FEN, origem="render", lado_a_jogar="b",
                   lado_origem="usuario")
    recorte = Figura(_png(200), 8, 8, origem="recorte", aviso="posição não conferida")
    return [
        PaginaExtraida(numero=0, blocos=[Paragrafo("Chapter One", titulo=True, nivel=1),
                                         Paragrafo("Bold and italic text.",
                                                   negrito=[(0, 4)], italico=[(9, 15)])]),
        PaginaExtraida(numero=1, blocos=[Paragrafo("A section", titulo=True, nivel=2),
                                         desenho, Paragrafo("More text.")]),
        PaginaExtraida(numero=2, blocos=[Paragrafo("Chapter Two", titulo=True, nivel=1),
                                         igual, recorte]),
    ]


def _ler(caminho):
    with zipfile.ZipFile(caminho) as z:
        return {n: z.read(n) for n in z.namelist()}, z.infolist()


def test_o_epub_tem_capitulos_sumario_paginas_e_marcos(tmp_path):
    destino = tmp_path / "livro.epub"
    m = epub.Metadados("A Book", idioma="en", autores=("Jacob Aagaard",), editora="QC",
                       data="2012", assuntos=("Chess",), direitos="©", capa=_png(128))
    escrito = epub.escrever(_livro(), destino, m)
    assert epub.conferir(destino) == []
    assert (escrito.capitulos, escrito.paginas, escrito.titulos) == (2, 3, 3)
    assert escrito.imagens == 2 and escrito.reutilizadas == 1 and escrito.sem_fen == 1

    partes, infos = _ler(destino)
    assert infos[0].filename == "mimetype" and infos[0].compress_type == zipfile.ZIP_STORED
    nav = partes["OEBPS/nav.xhtml"].decode("utf-8")
    assert "<h1>Contents</h1>" in nav and "Sumário" not in nav
    # O h2 dentro do capítulo de antes; o segundo capítulo no primeiro nível.
    assert ('<li><a href="texto/capitulo-001.xhtml#t1">Chapter One</a><ol><li>'
            '<a href="texto/capitulo-001.xhtml#t2">A section</a></li></ol></li>') in nav
    assert '<a href="texto/capitulo-002.xhtml#t3">Chapter Two</a></li>' in nav
    assert nav.count('epub:type="page-list"') == 1 and ">3</a>" in nav
    assert 'epub:type="cover"' in nav and 'epub:type="bodymatter"' in nav

    opf = partes["OEBPS/content.opf"].decode("utf-8")
    for esperado in ("<dc:creator>Jacob Aagaard</dc:creator>", "<dc:publisher>QC</dc:publisher>",
                     "<dc:date>2012</dc:date>", "<dc:subject>Chess</dc:subject>",
                     'properties="cover-image"', "<dc:language>en</dc:language>",
                     "accessModeSufficient\">textual,visual<",
                     "accessibilityHazard\">unknown<"):
        assert esperado in opf
    assert "alternativeText" not in opf                 # há um recorte sem FEN

    capitulo = partes["OEBPS/texto/capitulo-001.xhtml"].decode("utf-8")
    assert "<strong>Bold</strong>" in capitulo and "<em>italic</em>" in capitulo
    assert 'epub:type="pagebreak"' in capitulo and 'id="pg2"' in capitulo
    assert f"Diagram: FEN {FEN} — Black to move (set in review)" in capitulo
    segundo = partes["OEBPS/texto/capitulo-002.xhtml"].decode("utf-8")
    assert "Diagram not read; image of the printed page\"" in segundo   # sem o aviso em pt


def test_em_portugues_o_alt_tem_a_marca_do_documento_e_o_motivo(tmp_path):
    destino = tmp_path / "livro.epub"
    epub.escrever(_livro(), destino, epub.Metadados("Livro"))
    partes, _ = _ler(destino)
    texto = "".join(v.decode("utf-8") for n, v in partes.items() if n.endswith(".xhtml"))
    assert "pretas a jogar (informado na revisão)" in texto
    assert "Diagrama não lido; imagem da página impressa (posição não conferida)" in texto
    assert "<h1>Sumário</h1>" in partes["OEBPS/nav.xhtml"].decode("utf-8")


def test_todos_com_fen_declara_o_texto_alternativo(tmp_path):
    paginas = [PaginaExtraida(numero=0, blocos=[Figura(_png(), 8, 8, fen=FEN, origem="render")])]
    destino = tmp_path / "a.epub"
    epub.escrever(paginas, destino, epub.Metadados("L"))
    opf = _ler(destino)[0]["OEBPS/content.opf"].decode("utf-8")
    assert "alternativeText" in opf and "accessModeSufficient\">textual<" in opf


def test_sem_titulo_o_sumario_lista_as_paginas_e_o_capitulo_parte_pelo_tamanho(tmp_path):
    paginas = [PaginaExtraida(numero=i, blocos=[Paragrafo("x" * 60)]) for i in range(5)]
    destino = tmp_path / "a.epub"
    escrito = epub.escrever(paginas, destino, epub.Metadados("L"), limite_do_capitulo=100)
    assert escrito.capitulos == 3                     # 2 páginas por capítulo
    nav = _ler(destino)[0]["OEBPS/nav.xhtml"].decode("utf-8")
    assert "Páginas 1–2" in nav and "Páginas 5</a>" in nav
    assert epub.conferir(destino) == []


def test_ca_12_6_os_mesmos_bytes(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    a, b = tmp_path / "a.epub", tmp_path / "b.epub"
    m = epub.Metadados("L", autores=("A",), capa=_png(5))
    epub.escrever(_livro(), a, m)
    epub.escrever(_livro(), b, m)
    assert a.read_bytes() == b.read_bytes()


def test_o_identificador_e_estavel_e_configuravel():
    a = epub.Metadados("L", autores=("A",)).identificador_do_livro()
    assert a == epub.Metadados("L", autores=("A",)).identificador_do_livro()
    assert a != epub.Metadados("L", autores=("B",)).identificador_do_livro()
    assert epub.Metadados("L", identificador="isbn:123").identificador_do_livro() == "isbn:123"


def test_conferir_acusa_link_quebrado_e_mimetype_fora_do_lugar(tmp_path):
    destino = tmp_path / "ruim.epub"
    epub.escrever(_livro(), destino, epub.Metadados("L"))
    partes, _ = _ler(destino)
    capitulo = partes["OEBPS/texto/capitulo-001.xhtml"].decode("utf-8")
    partes["OEBPS/texto/capitulo-001.xhtml"] = capitulo.replace(
        "</body>", '<p><a href="capitulo-009.xhtml#x">x</a><a href="#nada">y</a></p></body>'
    ).encode("utf-8")
    ruim = tmp_path / "ruim2.epub"
    with zipfile.ZipFile(ruim, "w", zipfile.ZIP_DEFLATED) as z:
        for nome in sorted(partes):                       # META-INF/ antes do mimetype
            z.writestr(nome, partes[nome])
    problemas = epub.conferir(ruim)
    assert "o mimetype não é a primeira entrada" in problemas
    assert any("link quebrado capitulo-009.xhtml#x" in p for p in problemas)
    assert any("âncora inexistente #nada" in p for p in problemas)


def test_metadados_do_projeto_pelo_arquivo(tmp_path):
    (tmp_path / "capa.png").write_bytes(_png(9))
    (tmp_path / ex.ARQUIVO_DE_METADADOS).write_text(json.dumps({
        "autores": ["Jacob Aagaard"], "editora": "Quality Chess", "data": "2012",
        "assuntos": "Chess", "capa": "capa.png"}), encoding="utf-8")
    projeto = SimpleNamespace(pasta=tmp_path, dados=SimpleNamespace(nome="Endgame"))
    m = ex.metadados_do_projeto(projeto, "en")
    assert (m.titulo, m.idioma, m.autores, m.editora, m.assuntos) == (
        "Endgame", "en", ("Jacob Aagaard",), "Quality Chess", ("Chess",))
    assert m.capa == _png(9)
    vazio = ex.metadados_do_projeto(SimpleNamespace(pasta=tmp_path / "x",
                                                    dados=SimpleNamespace(nome="T")), "pt-BR")
    assert vazio.titulo == "T" and vazio.capa is None


def test_epubcheck_sem_configuracao_e_none(tmp_path, monkeypatch):
    monkeypatch.delenv("ABBY_EPUBCHECK", raising=False)
    assert epub.epubcheck(tmp_path / "x.epub") is None


@pytest.mark.parametrize("idioma,titulo", [("es", "Índice"), ("de", "Inhalt"),
                                           ("fr", "Table des matières"), ("xx", "Contents")])
def test_mensagens_por_idioma(idioma, titulo):
    assert epub.mensagens(idioma)["sumario"] == titulo


# ----------------------------------------------------------------------
# A revisão de código (rodada 1)
# ----------------------------------------------------------------------

def test_a_fonte_dos_simbolos_e_achada_pelo_css(tmp_path):
    paginas = [PaginaExtraida(numero=0, blocos=[Paragrafo("1.♘f3 ♞f6 2.♖g1")])]
    destino = tmp_path / "a.epub"
    epub.escrever(paginas, destino, epub.Metadados("L"))
    partes, _ = _ler(destino)
    css = partes["OEBPS/estilo.css"].decode("utf-8")
    if "@font-face" in css:                           # há fonte de símbolos nesta máquina
        assert 'url("fontes/' in css
        assert '<span class="s">' in partes["OEBPS/texto/capitulo-001.xhtml"].decode("utf-8")
    assert epub.conferir(destino) == []


def test_caracteres_de_controle_do_ocr_nao_quebram_o_xml(tmp_path):
    paginas = [PaginaExtraida(numero=0, blocos=[Paragrafo("Tí\x0ctulo", titulo=True, nivel=1),
                                                Paragrafo("um\x00 texto", negrito=[(0, 2)])])]
    destino = tmp_path / "a.epub"
    epub.escrever(paginas, destino, epub.Metadados("Livro\x0c"))
    assert epub.conferir(destino) == []


def test_livro_vazio_nao_vira_pacote_invalido(tmp_path):
    with pytest.raises(ValueError, match="Nada para escrever"):
        epub.escrever([], tmp_path / "a.epub", epub.Metadados("L"))


def test_a_ancora_da_pagina_cai_no_capitulo_do_titulo_dela(tmp_path):
    paginas = [PaginaExtraida(numero=0, blocos=[Paragrafo("Antes.")]),
               PaginaExtraida(numero=1, blocos=[Paragrafo("Capítulo", titulo=True, nivel=1),
                                                Paragrafo("Depois.")])]
    destino = tmp_path / "a.epub"
    epub.escrever(paginas, destino, epub.Metadados("L"))
    partes, _ = _ler(destino)
    assert 'id="pg2"' not in partes["OEBPS/texto/capitulo-001.xhtml"].decode("utf-8")
    assert 'id="pg2"' in partes["OEBPS/texto/capitulo-002.xhtml"].decode("utf-8")
    assert 'href="texto/capitulo-002.xhtml#pg2"' in partes["OEBPS/nav.xhtml"].decode("utf-8")


def test_o_opf_tem_a_fonte_impressa_e_recusa_data_fora_do_formato(tmp_path):
    destino = tmp_path / "a.epub"
    epub.escrever(_livro(), destino, epub.Metadados("L", data="maio de 2012"))
    opf = _ler(destino)[0]["OEBPS/content.opf"].decode("utf-8")
    assert "<dc:source>L</dc:source>" in opf and "<dc:date>" not in opf


def test_conferir_acusa_id_repetido_e_toc_vazio(tmp_path):
    destino = tmp_path / "a.epub"
    epub.escrever(_livro(), destino, epub.Metadados("L"))
    partes, _ = _ler(destino)
    capitulo = partes["OEBPS/texto/capitulo-001.xhtml"].decode("utf-8")
    partes["OEBPS/texto/capitulo-001.xhtml"] = capitulo.replace(
        "</body>", '<p id="t1">repetido</p></body>').encode("utf-8")
    nav = partes["OEBPS/nav.xhtml"].decode("utf-8")
    inicio = nav.index('<nav epub:type="toc"')
    fim = nav.index("</nav>", inicio)
    partes["OEBPS/nav.xhtml"] = (nav[:inicio] + '<nav epub:type="toc" id="toc"><ol></ol>'
                                 + nav[fim:]).encode("utf-8")
    ruim = tmp_path / "ruim.epub"
    with zipfile.ZipFile(ruim, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), partes.pop("mimetype"))
        for nome in sorted(partes):
            z.writestr(nome, partes[nome], zipfile.ZIP_DEFLATED)
    problemas = epub.conferir(ruim)
    assert "OEBPS/texto/capitulo-001.xhtml: o id t1 se repete" in problemas
    assert "o toc do nav está vazio" in problemas


def test_metadados_nulos_e_capa_fora_da_pasta(tmp_path):
    projeto_dir = tmp_path / "projeto"
    projeto_dir.mkdir()
    (tmp_path / "fora.png").write_bytes(_png(1))
    (projeto_dir / ex.ARQUIVO_DE_METADADOS).write_text(json.dumps({
        "editora": None, "autores": [None, "A"], "capa": "../fora.png"}), encoding="utf-8")
    m = ex.metadados_do_projeto(SimpleNamespace(pasta=projeto_dir,
                                                dados=SimpleNamespace(nome="T")), "pt-BR")
    assert m.editora == "" and m.autores == ("A",) and m.capa is None

@pytest.mark.skipif(not os.environ.get("ABBY_EPUBCHECK"),
                    reason="o EPUBCheck não está configurado (ABBY_EPUBCHECK)")
def test_o_epubcheck_aprova_o_livro_com_capa_fonte_e_recortes(tmp_path):
    jpeg = io.BytesIO()
    Image.new("RGB", (30, 45), (40, 80, 120)).save(jpeg, format="JPEG")
    for idioma, capa in (("en", jpeg.getvalue()), ("pt-BR", _png(90))):
        destino = tmp_path / f"livro-{idioma}.epub"
        epub.escrever(_livro(), destino, epub.Metadados(
            "A Book & <More>", idioma=idioma, autores=("A",), data="2012-05", capa=capa))
        assert epub.conferir(destino) == []
        assert epub.epubcheck(destino) == []