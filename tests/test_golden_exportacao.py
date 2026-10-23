"""O golden normalizado da exportação (CA-12.1) e a diferença declarada de cada opção (CA-12.3).

A forma normalizada: no DOCX, o `word/document.xml` em C14N sem os `w:rsid*`, uma linha por
parágrafo com o estilo e o texto (o negrito entre `**`, o itálico entre `_`, o realce entre
`[[ ]]`, a quebra dentro do parágrafo como `⏎`, a figura pelo texto alternativo); no EPUB,
cada XHTML da espinha em C14N e o OPF sem `dc:identifier` nem `dcterms:modified`, uma linha
por bloco; no TXT, as linhas não vazias. Os nomes das imagens (a soma do PNG) saem.

Os golden ficam em `tests/golden/exportacao/` (as 4 combinações cabeçalhos × quebras, em DOCX
e EPUB) e a diferença das opções em `tests/golden/opcoes.yaml`. Para regravar os golden depois
de uma mudança decidida: `pytest tests/test_golden_exportacao.py --atualizar-golden`. O
`opcoes.yaml` não é regravado: ele é a declaração, e se a diferença mudou, ele muda à mão.
"""

from __future__ import annotations

import difflib
import os
import re
import zipfile
from dataclasses import fields, replace
from pathlib import Path
from xml.etree import ElementTree

import pytest
import yaml
from PIL import Image

from core.box_model import BoxEntry

from abbychess import epub
from abbychess import escritor_docx as ed
from abbychess import exportar as ex
from abbychess import texto as tx
from abbychess.leitor import FONTE_MANUAL, Limiares
from abbychess.modelo import Decisoes, Estilo
from abbychess.zonas import Zona

from tests.test_diagramas import _lido

GOLDEN = Path(__file__).with_name("golden")
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
_DIAGRAMA = (300, 420, 700, 820)


def _linha(texto: str, y: int, x: int = 40, fonte: str = FONTE_MANUAL, confianca: float = 1.0):
    boxes, cursor = [], x
    for char in texto:
        if char != " ":
            boxes.append(BoxEntry(char, cursor, y, cursor + 10, y + 20, confianca, fonte))
        cursor += 14
    return boxes


def _pagina():
    """Cabeçalho, título, um parágrafo com negrito e o hífen de quebra, uma palavra duvidosa
    e um diagrama conferido com o parágrafo de depois."""
    linhas = [("XADREZ VITORIOSO 23", 10), ("Capitulo um", 100),
              ("O texto vai em negrito e o hi-", 200), ("Fen termina aqui.", 240)]
    entries = [b for texto, y in linhas for b in _linha(texto, y)]
    entries += _linha("Uma", 300) + _linha("duvida", 300, x=40 + 14 * 4, fonte="rede",
                                           confianca=0.2)
    entries += _linha("Depois do diagrama.", 900)
    zonas = [Zona("texto", 0, 0, 1000, 40, funcao="cabecalho"),
             Zona("texto", 0, 90, 1000, 130, funcao="titulo"),
             Zona("texto", 0, 190, 1000, 330), Zona("texto", 0, 890, 1000, 930)]
    diagrama = replace(_lido(caixa=_DIAGRAMA), conferido=True, lado="w", lado_origem="usuario",
                       id="d0")
    pagina = tx.pagina_avulsa(entries, [diagrama], zonas=zonas)
    pagina.tabuleiros = [_DIAGRAMA]
    linha200 = [b for b in pagina.boxes if b.entry.y1 == 200]
    alvo = {b.gid for b in linha200[len("Otextovaiem"):len("Otextovaiemnegrito")]}
    pagina.boxes = [replace(b, estilo=Estilo(negrito=True)) if b.gid in alvo else b
                    for b in pagina.boxes]
    pagina.decisoes = Decisoes(hifen_de_quebra=frozenset({linha200[-1].gid}))
    return pagina


def _extraida(opcoes: ex.Opcoes):
    pagina = _pagina()
    limiares = Limiares() if opcoes.realcar_duvidosos else None
    entries, estrutura = ex.Estrutura.da_pagina(pagina, limiares)
    return [ex.pagina_extraida(0, entries, pagina.tabuleiros, Image.new("L", (1000, 1400), 255),
                               pagina.diagramas, estrutura=estrutura,
                               manter_margens=opcoes.manter_margens,
                               desenhar_diagramas=opcoes.desenhar_diagramas,
                               manter_quebras=opcoes.manter_quebras)]


# ----------------------------------------------------------------------
# As formas normalizadas
# ----------------------------------------------------------------------

def _sem_rsid(xml: bytes) -> str:
    raiz = ElementTree.fromstring(xml)
    for elemento in raiz.iter():
        for nome in [n for n in elemento.attrib if n.split("}")[-1].startswith("rsid")]:
            del elemento.attrib[nome]
    return ElementTree.canonicalize(ElementTree.tostring(raiz, encoding="unicode"))


def forma_do_docx(caminho: Path) -> str:
    with zipfile.ZipFile(caminho) as z:
        raiz = ElementTree.fromstring(_sem_rsid(z.read("word/document.xml")))
    linhas = []
    for p in raiz.iter(f"{{{_W}}}p"):
        estilo = p.find(f"{{{_W}}}pPr/{{{_W}}}pStyle")
        partes = []
        for r in p.iter(f"{{{_W}}}r"):
            texto = "".join("⏎" if f.tag == f"{{{_W}}}br" else (f.text or "")
                            for f in r if f.tag in (f"{{{_W}}}t", f"{{{_W}}}br"))
            propriedades = r.find(f"{{{_W}}}rPr")
            if texto and propriedades is not None:
                if propriedades.find(f"{{{_W}}}highlight") is not None:
                    texto = f"[[{texto}]]"
                if propriedades.find(f"{{{_W}}}i") is not None:
                    texto = f"_{texto}_"
                if propriedades.find(f"{{{_W}}}b") is not None:
                    texto = f"**{texto}**"
            partes.append(texto)
        for figura in p.iter(f"{{{_WP}}}docPr"):
            partes.append(f"[figura: {figura.get('descr')}]")
        if "".join(partes):
            nome = estilo.get(f"{{{_W}}}val") if estilo is not None else "Normal"
            linhas.append(f"{nome}: {''.join(partes)}")
    return "\n".join(linhas)


def _em_blocos(c14n: str) -> str:
    c14n = re.sub(r"imagens/[0-9a-f]{20}\.(png|jpg|gif|webp)", r"imagens/IMG.\1", c14n)
    return re.sub(r"(<(?:p|h1|h2|figure|li|section|nav|span epub:type|meta|dc:|item|itemref)\b)",
                  r"\n\1", c14n).strip()


def forma_do_epub(caminho: Path) -> str:
    with zipfile.ZipFile(caminho) as z:
        opf_bruto = z.read("OEBPS/content.opf")
        opf = ElementTree.fromstring(opf_bruto)
        ns = {"opf": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/"}
        metadados = opf.find("opf:metadata", ns)
        for filho in list(metadados):
            if filho.tag == f"{{{ns['dc']}}}identifier" or filho.get("property") == "dcterms:modified":
                metadados.remove(filho)
        manifesto = {i.get("id"): i.get("href") for i in opf.iter(f"{{{ns['opf']}}}item")}
        partes = ["== content.opf ==",
                  _em_blocos(ElementTree.canonicalize(ElementTree.tostring(opf, encoding="unicode")))]
        for item in opf.iter(f"{{{ns['opf']}}}itemref"):
            href = manifesto[item.get("idref")]
            partes += [f"== {href} ==",
                       _em_blocos(ElementTree.canonicalize(z.read(f"OEBPS/{href}").decode("utf-8")))]
    return "\n".join(partes)


def forma_do_txt(caminho: Path) -> str:
    return "\n".join(linha for linha in caminho.read_text(encoding="utf-8").splitlines() if linha)


def _formas(tmp_path: Path, opcoes: ex.Opcoes) -> dict:
    paginas = _extraida(opcoes)
    docx, livro, txt = tmp_path / "a.docx", tmp_path / "a.epub", tmp_path / "a.txt"
    metadados = epub.Metadados("Golden", autores=("A. Autor",), data="2026")
    ed.escrever(paginas, docx, metadados, quebras=opcoes.manter_quebras,
                realce=opcoes.realcar_duvidosos)
    epub.escrever(paginas, livro, metadados, quebras=opcoes.manter_quebras)
    txt.write_text(ex.texto_do_livro(paginas, marcas_de_pagina=opcoes.marcas_de_pagina),
                   encoding="utf-8")
    assert ed.conferir(docx) == [] and epub.conferir(livro) == []
    if os.environ.get("ABBY_EPUBCHECK"):
        assert epub.epubcheck(livro) == []
    return {"docx": forma_do_docx(docx), "epub": forma_do_epub(livro), "txt": forma_do_txt(txt)}


@pytest.fixture(autouse=True)
def _data_fixa(monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")


# ----------------------------------------------------------------------
# CA-12.1: as 4 combinações cabeçalhos × quebras
# ----------------------------------------------------------------------

@pytest.mark.parametrize("margens", [False, True], ids=["sem-cabecalho", "com-cabecalho"])
@pytest.mark.parametrize("quebras", [False, True], ids=["refluido", "com-quebras"])
def test_ca_12_1_golden_normalizado(request, tmp_path, margens, quebras):
    formas = _formas(tmp_path, ex.Opcoes(manter_margens=margens, manter_quebras=quebras))
    sufixo = f"{'com' if margens else 'sem'}-cabecalho-{'com-quebras' if quebras else 'refluido'}"
    for formato in ("docx", "epub"):
        caminho = GOLDEN / "exportacao" / f"{formato}-{sufixo}.txt"
        if request.config.getoption("--atualizar-golden"):
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_text(formas[formato] + "\n", encoding="utf-8", newline="\n")
            continue
        assert caminho.is_file(), f"golden ausente: rode com --atualizar-golden ({caminho.name})"
        assert formas[formato] + "\n" == caminho.read_text(encoding="utf-8"), \
            f"mudou: {caminho.name}"


def test_a_forma_normalizada_tira_o_que_muda_entre_exportacoes(tmp_path, monkeypatch):
    """Outro instante e outro identificador dão a mesma forma: ela compara o conteúdo."""
    a = _formas(tmp_path, ex.Opcoes())
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1800000000")
    b = _formas(tmp_path, ex.Opcoes())
    assert a == b
    assert "rsid" not in a["docx"] and "dcterms:modified" not in a["epub"]
    assert "Heading1: Capitulo um" in a["docx"].replace("Heading 1", "Heading1")


# ----------------------------------------------------------------------
# CA-12.3: cada opção, exatamente a diferença declarada
# ----------------------------------------------------------------------

def _declaracao() -> dict:
    return yaml.safe_load((GOLDEN / "opcoes.yaml").read_text(encoding="utf-8"))


def test_toda_opcao_esta_declarada():
    declaradas = set(_declaracao())
    assert declaradas == {f.name for f in fields(ex.Opcoes)}


@pytest.mark.parametrize("nome", sorted(_declaracao()))
def test_ca_12_3_a_opcao_produz_so_a_diferenca_declarada(tmp_path, nome):
    declarada = _declaracao()[nome]
    if declarada.get("escopo") == "livro":
        # A opção escolhe páginas do projeto, não muda a página: os testes que ela cita.
        import tests.test_exportar_documento as documento

        for teste in declarada["testes"]:
            assert hasattr(documento, teste), teste
        return
    padrao = getattr(ex.Opcoes(), nome)
    ligada = declarada.get("valor", not padrao)
    for pasta in ("padrao", "ligada"):
        (tmp_path / pasta).mkdir()
    antes = _formas(tmp_path / "padrao", ex.Opcoes())
    depois = _formas(tmp_path / "ligada", replace(ex.Opcoes(), **{nome: ligada}))
    for formato in ("docx", "epub", "txt"):
        esperado = declarada.get(formato) or {}
        diferenca = list(difflib.ndiff(antes[formato].splitlines(), depois[formato].splitlines()))
        removidas = [linha[2:] for linha in diferenca if linha.startswith("- ")]
        acrescentadas = [linha[2:] for linha in diferenca if linha.startswith("+ ")]
        for tipo, linhas in (("remove", removidas), ("acrescenta", acrescentadas)):
            padroes = [re.compile(p) for p in esperado.get(tipo, [])]
            for linha in linhas:
                assert any(p.search(linha) for p in padroes), \
                    f"{nome}/{formato}: linha que a declaração não prevê ({tipo}): {linha!r}"
            for p in padroes:
                assert any(p.search(linha) for linha in linhas), \
                    f"{nome}/{formato}: a declaração prevê ({tipo}) {p.pattern!r} e não veio"


# ----------------------------------------------------------------------
# As opções novas, por si
# ----------------------------------------------------------------------

def test_manter_quebras_fica_com_as_linhas_e_o_hifen():
    textos = [b.texto for b in _extraida(ex.Opcoes(manter_quebras=True))[0].blocos
              if isinstance(b, ex.Paragrafo)]
    assert "O texto vai em negrito e o hi-\nFen termina aqui.\nUma duvida" in textos


def test_manter_quebras_na_camada_nativa_volta_pelos_inicios():
    paragrafo = ex.Paragrafo("uma linha outra linha", inicios=[0, 10])
    pagina = ex.PaginaExtraida(numero=0, blocos=[paragrafo])
    ex._quebras_da_camada(pagina)
    assert paragrafo.texto == "uma linha\noutra linha"
    # A camada guarda o hífen colado (`inter-essante`): o `\n` entra depois dele, e o
    # negrito de "essante" e o da linha de antes seguem nas letras deles.
    partida = ex.Paragrafo("o inter-essante fim", inicios=[0, 8], negrito=[(2, 8), (8, 15)])
    ex._quebras_da_camada(ex.PaginaExtraida(numero=0, blocos=[partida]))
    assert partida.texto == "o inter-\nessante fim"
    assert [partida.texto[a:z] for a, z in partida.negrito] == ["inter-", "essante"]
    assert partida.inicios == [0, 9] and partida.pesos is None


def test_manter_quebras_na_camada_nativa_devolve_o_hifen_que_o_core_tirou():
    """O core tira o hífen da palavra partida quando o dicionário diz que era quebra, e o
    hífen brando: sem espaço nem hífen no início da linha, a quebra volta com o hífen, como
    impressa, e o hífen fica no negrito da sílaba de antes."""
    partida = ex.Paragrafo("o interessante fim e mais", inicios=[0, 7, 19],
                           negrito=[(2, 14)], italico=[(15, 18)])
    ex._quebras_da_camada(ex.PaginaExtraida(numero=0, blocos=[partida]))
    assert partida.texto == "o inter-\nessante fim\ne mais"
    assert [partida.texto[a:z] for a, z in partida.negrito] == ["inter-\nessante"]
    assert [partida.texto[a:z] for a, z in partida.italico] == ["fim"]
    assert partida.inicios == [0, 9, 21]
    # Sem letra dos dois lados, não é palavra partida: nada entra.
    numero = ex.Paragrafo("lance 12.e4", inicios=[0, 8])
    ex._quebras_da_camada(ex.PaginaExtraida(numero=0, blocos=[numero]))
    assert numero.texto == "lance 12.e4"


@pytest.mark.parametrize("com_dicionario", [False, True])
def test_manter_quebras_com_a_camada_de_um_pdf_que_parte_palavras(tmp_path, com_dicionario):
    """Pela camada de verdade (`core.pdf_nativo`): a palavra partida volta partida, com o
    dicionário que tira o hífen ou sem ele (o hífen fica colado), e as outras quebras viram
    `\\n`."""
    import fitz

    from core import lexico, pdf_nativo

    caminho = tmp_path / "partido.pdf"
    doc = fitz.open()
    pagina = doc.new_page(width=300, height=200)
    for k, linha in enumerate(["Then came a very beauti-", "ful combination in the game and",
                               "it ends here."]):
        pagina.insert_text((20, 40 + 14 * k), linha, fontsize=11)
    doc.save(caminho)
    doc.close()
    lex = lexico.Lexico(palavras={"beautiful"}) if com_dicionario else None
    extraida = pdf_nativo.extrair(str(caminho), [0], idioma="en", lex=lex).paginas[0]
    textos = [b.texto for b in extraida.blocos if isinstance(b, ex.Paragrafo)]
    assert any(("beautiful" if com_dicionario else "beauti-ful") in t for t in textos), textos
    ex._quebras_da_camada(extraida)
    textos = [b.texto for b in extraida.blocos if isinstance(b, ex.Paragrafo)]
    assert "Then came a very beauti-\nful combination in the game and\nit ends here." in textos


def test_o_realce_marca_so_a_palavra_duvidosa_e_atravessa_a_pagina():
    corpo = next(b for b in _extraida(ex.Opcoes(realcar_duvidosos=True))[0].blocos
                 if isinstance(b, ex.Paragrafo) and "duvida" in b.texto)
    assert [corpo.texto[a:z] for a, z in corpo.duvidosos] == ["duvida"]
    # O parágrafo que a paginação partiu volta com os duvidosos dele no lugar certo.
    antes = ex.ParagrafoExportado("fim da pagina sem ponto")
    depois = ex.ParagrafoExportado("e segue duvida", duvidosos=[(8, 14)])
    paginas = [ex.PaginaExtraida(numero=0, blocos=[antes]),
               ex.PaginaExtraida(numero=1, blocos=[depois])]
    ex._juntar_entre_paginas(paginas)
    assert [antes.texto[a:z] for a, z in antes.duvidosos] == ["duvida"]


def test_o_dialogo_oferece_as_opcoes_novas_so_onde_valem():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from abbychess.app.dialogo_exportacao import DialogoDeExportacao

    QApplication.instance() or QApplication([])
    for formato, quebras, realce in (("docx", True, True), ("epub", True, False),
                                     ("txt", True, False), ("pgn", False, False)):
        dialogo = DialogoDeExportacao(None, formato, ex.Opcoes(), {}, Path("."), "T")
        assert dialogo.manter_quebras.isEnabled() is quebras
        assert dialogo.realcar.isEnabled() is realce
        dialogo.manter_quebras.setChecked(True)
        dialogo.realcar.setChecked(True)
        opcoes = dialogo.opcoes()
        assert opcoes.manter_quebras and opcoes.realcar_duvidosos
        dialogo.deleteLater()
