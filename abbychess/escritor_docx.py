"""O DOCX do AbbyChessCraft (SPEC §12.1, passo J): o escritor próprio, sem o do core.

Lê as mesmas `core.pagina.PaginaExtraida` que o EPUB e escreve pelo python-docx:

- **Títulos** nos estilos "Heading 1" e "Heading 2" (o painel de navegação do Word e o
  sumário que ele monta saem deles); **negrito e itálico** pelos trechos do parágrafo; os
  **símbolos de xadrez** na fonte dos símbolos (`core.exportar.fonte_dos_simbolos`).
- **Diagramas** como imagem, com o texto alternativo do EPUB (o FEN e o lado com a
  procedência, ou que o diagrama não foi lido) no `descr` da figura; imagens iguais são uma
  parte só (o python-docx já guarda pela soma).
- **Páginas impressas**: cada página começa com um marcador (`pg23`), e as referências do
  texto ("página 23", `links_internos.referencias`) viram hiperlink interno para ele, quando a página
  está no arquivo. Os diagramas numerados pela legenda e os capítulos numerados pelo título
  (`links_internos.numerados`) têm marcador (`dg6`, `cap3`), e "ver o Diagrama 6" e "no capítulo 3"
  viram hiperlink para eles.
- **Links de análise**, se pedidos: embaixo de cada diagrama lido, o hiperlink externo que
  abre a posição no Lichess ou no Chess.com (`links_de_analise`).
- **Metadados** (`epub.Metadados`): título, autores, assuntos, idioma e identificador nas
  propriedades; o idioma também no estilo base (`w:lang`), senão o Word revisa um livro
  inglês em português.
- **Os mesmos bytes** com o mesmo `SOURCE_DATE_EPOCH` (CA-12.6): as datas das
  propriedades e das entradas do zip vêm de `core.exportar.instante`, e o zip é regravado
  na ordem e com os atributos fixos.

`conferir` relê o arquivo: o pacote abre, o XML do documento é legível, cada imagem citada
existe, cada hiperlink interno tem o seu marcador e os marcadores não se repetem.
"""

from __future__ import annotations

import datetime
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from xml.etree import ElementTree

from core.pagina import Figura, PaginaExtraida, Paragrafo

from abbychess import epub
from abbychess import links_internos
from abbychess import gravacao as gv
from abbychess import links_de_analise
from abbychess import marcacao

#: A largura do diagrama sem medida de casa e a máxima de qualquer figura, em centímetros.
LARGURA_DO_DIAGRAMA_CM = 6.5
LARGURA_MAXIMA_DO_RECORTE_CM = 9.0
#: O tamanho da casa do diagrama, em pontos: a largura vem de `Figura.casas_de_largura`.
CORPO_DA_CASA_PT = 16.0
#: O desenho da página, o do escritor do core (F111): Georgia 11, justificado, recuo de
#: primeira linha, margens de 2,2 cm.
FONTE_DO_TEXTO, CORPO_DO_TEXTO_PT, MARGEM_DA_PAGINA_CM = "Georgia", 11.0, 2.2
#: A cor do hiperlink interno (a do estilo "Hyperlink" do Word).
COR_DO_LINK = "0563C1"

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


@dataclass
class EscritoDocx:
    """O que o DOCX levou: para o relatório da exportação (§12.2)."""

    paginas: int = 0
    paragrafos: int = 0
    titulos: int = 0
    figuras: int = 0
    links: int = 0
    #: Os parágrafos com algum trecho realçado (`realce`).
    realcados: int = 0
    #: Os diagramas com link de análise (`analise`).
    analises: int = 0


# ----------------------------------------------------------------------
# Pedaços de OOXML
# ----------------------------------------------------------------------

def _desenho_da_pagina(doc) -> None:
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt

    normal = doc.styles["Normal"]
    normal.font.name = FONTE_DO_TEXTO
    normal.font.size = Pt(CORPO_DO_TEXTO_PT)
    formato = normal.paragraph_format
    formato.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    formato.first_line_indent = Pt(CORPO_DO_TEXTO_PT * 1.2)
    formato.space_after = Pt(CORPO_DO_TEXTO_PT * 0.35)
    for secao in doc.sections:
        secao.top_margin = secao.bottom_margin = Cm(MARGEM_DA_PAGINA_CM)
        secao.left_margin = secao.right_margin = Cm(MARGEM_DA_PAGINA_CM)


def _idioma_no_estilo(doc, idioma: str) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    rpr = doc.styles["Normal"].element.get_or_add_rPr()
    for velho in rpr.findall(qn("w:lang")):
        rpr.remove(velho)
    lang = OxmlElement("w:lang")
    for atributo in ("w:val", "w:eastAsia", "w:bidi"):
        lang.set(qn(atributo), idioma)
    rpr.append(lang)


def _marcador(paragrafo, nome: str, ident: int) -> None:
    """Um marcador do Word (`w:bookmarkStart`/`End`) envolvendo o parágrafo."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    inicio = OxmlElement("w:bookmarkStart")
    inicio.set(qn("w:id"), str(ident))
    inicio.set(qn("w:name"), nome)
    fim = OxmlElement("w:bookmarkEnd")
    fim.set(qn("w:id"), str(ident))
    p = paragrafo._p
    ppr = p.pPr
    if ppr is not None:
        ppr.addnext(inicio)
    else:
        p.insert(0, inicio)
    p.append(fim)


def _texto_com_estilo(paragrafo, bloco: Paragrafo, simbolos: str, familia: str,
                      links: Sequence[Tuple[int, int, str]], quebras: bool = False,
                      realce: bool = False) -> None:
    """Os trechos do parágrafo como runs: negrito, itálico, fonte dos símbolos e o
    hiperlink interno por fora (o mesmo corte de `epub.xhtml_do_texto`)."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import RGBColor

    # Como no EPUB: o comprimento fica; a quebra de linha é espaço, como no XHTML, salvo com
    # `quebras` (as linhas impressas mantidas): aí ela fica, e o python-docx a escreve `w:br`.
    # As aspas retas do OCR viram as curvas do impresso (PD-07), uma por uma.
    texto = epub.aspas_curvas(epub.sem_proibidos(bloco.texto).replace("\r", " "))
    if not quebras:
        texto = texto.replace("\n", " ")
    duvidosos = getattr(bloco, "duvidosos", ()) if realce else ()
    hiperlink, do_hiperlink = None, -1
    for pedaco, marca in marcacao.trechos_marcados(
            texto, simbolos, bloco.negrito, bloco.italico, duvidosos, links,
            getattr(bloco, "sublinhado", ())):
        negrito, italico, simbolo, link, duvidoso, sublinhado = marca
        run = paragrafo.add_run(pedaco)
        run.underline = sublinhado or None
        _estilo_do_run(run, negrito, italico, duvidoso, simbolo, familia)
        if link >= 0:
            if hiperlink is None or do_hiperlink != link:
                hiperlink = OxmlElement("w:hyperlink")
                hiperlink.set(qn("w:anchor"), links[link][2])
                hiperlink.set(qn("w:history"), "1")
                paragrafo._p.append(hiperlink)
                do_hiperlink = link
            run.font.underline = True
            run.font.color.rgb = RGBColor.from_string(COR_DO_LINK)
            hiperlink.append(run._r)
        else:
            hiperlink, do_hiperlink = None, -1


def _estilo_do_run(run, negrito: bool, italico: bool, duvidoso: bool, simbolo: bool,
                   familia: str) -> None:
    """O negrito, o itálico, o realce do duvidoso e, no símbolo, a fonte dos símbolos
    (nos atributos que o Word lê para cada escrita). Os imports só no caso que os usa: isto roda
    por trecho."""
    run.bold = negrito or None
    run.italic = italico or None
    if duvidoso:
        from docx.enum.text import WD_COLOR_INDEX

        run.font.highlight_color = WD_COLOR_INDEX.YELLOW
    if simbolo and familia:
        from docx.oxml.ns import qn

        run.font.name = familia
        fontes = run._r.get_or_add_rPr().get_or_add_rFonts()
        fontes.set(qn("w:cs"), familia)
        fontes.set(qn("w:eastAsia"), familia)


def _figura(doc, figura: Figura, alt: str, numero: int) -> None:
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt

    from core.exportar import largura_em_pt

    em_pt = largura_em_pt(figura, CORPO_DA_CASA_PT)
    if em_pt:
        largura = min(Pt(em_pt), Cm(LARGURA_MAXIMA_DO_RECORTE_CM))
    elif figura.fen:
        largura = Cm(LARGURA_DO_DIAGRAMA_CM)
    else:
        proporcao = (figura.largura / figura.altura) if figura.altura else 1.0
        largura = Cm(min(LARGURA_MAXIMA_DO_RECORTE_CM,
                         LARGURA_DO_DIAGRAMA_CM * max(proporcao, 0.5)))
    doc.add_picture(io.BytesIO(epub.png_otimizado(figura.png)), width=largura)
    paragrafo = doc.paragraphs[-1]
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for propriedades in paragrafo._p.xpath(".//wp:docPr"):
        propriedades.set("descr", epub.limpo(alt))
        propriedades.set("name", f"Diagrama {numero}")


def _ressalva(doc, figura: Figura, idioma: str) -> bool:
    """A legenda visível do diagrama cuja posição ninguém conferiu (PD-21): de quem é a vez
    e "não revisado". Fica no `descr` também, mas quem vê a página precisa ver isto."""
    ressalva = marcacao.ressalva_do_diagrama(figura, idioma)
    if not ressalva:
        return False
    paragrafo = doc.add_paragraph(epub.limpo(ressalva))
    _como_legenda(doc, paragrafo)
    return True


def _como_legenda(doc, paragrafo) -> None:
    try:
        paragrafo.style = doc.styles["Caption"]
    except KeyError:                            # o modelo sem o estilo: fica no Normal
        pass


def _link_de_analise(doc, figura: Figura, site: str, idioma: str) -> bool:
    """O hiperlink externo, embaixo do diagrama lido, que abre a posição no tabuleiro de
    análise do `site` (`links_de_analise`); nada sem FEN ou com o site `nenhum`."""
    endereco = links_de_analise.link_da_figura(figura, site)
    if not endereco:
        return False
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.opc.constants import RELATIONSHIP_TYPE
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import RGBColor

    paragrafo = doc.add_paragraph()
    _como_legenda(doc, paragrafo)
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    hiperlink = OxmlElement("w:hyperlink")
    hiperlink.set(qn("r:id"), doc.part.relate_to(endereco, RELATIONSHIP_TYPE.HYPERLINK,
                                                 is_external=True))
    hiperlink.set(qn("w:history"), "1")
    run = paragrafo.add_run(epub.limpo(links_de_analise.rotulo(site, idioma)))
    run.font.underline = True
    run.font.color.rgb = RGBColor.from_string(COR_DO_LINK)
    hiperlink.append(run._r)
    paragrafo._p.append(hiperlink)
    return True


# ----------------------------------------------------------------------
# Escrever
# ----------------------------------------------------------------------

def escrever(paginas: Sequence[PaginaExtraida], caminho: str | Path, metadados: epub.Metadados,
             *, numeros: Optional[Dict[int, int]] = None, quebras: bool = False,
             realce: bool = False, analise: str = "nenhum") -> EscritoDocx:
    """Escreve o DOCX em `caminho` (ao lado e troca no fim: a falha não estraga o anterior).

    `numeros` é o número impresso de cada página (índice -> número): as referências do
    texto a ele viram hiperlink para o marcador da página. `analise` põe embaixo de cada
    diagrama lido o link que abre a posição no Lichess ou no Chess.com
    (`Opcoes.links_de_analise`); `nenhum`, nenhum link."""
    links_de_analise.validar(analise)
    from docx import Document

    from core.exportar import data_no_zip, instante

    # Só as páginas que têm o que escrever ganham marcador; só elas são alvo de link.
    com_conteudo = _com_conteudo(paginas)
    if not com_conteudo:
        raise ValueError("Nada para escrever no DOCX: as páginas não têm texto nem diagrama.")
    idioma = metadados.idioma or "pt-BR"
    msg = epub.mensagens(idioma)
    escrito = EscritoDocx(paginas=len(paginas))
    idioma = epub.limpo(idioma)
    doc = Document()
    _desenho_da_pagina(doc)
    _idioma_no_estilo(doc, idioma)

    recurso = _fonte_dos_simbolos(paginas)
    familia, simbolos = (recurso[0], recurso[2]) if recurso else ("", "")
    # Os diagramas e os capítulos numerados ganham marcador (`dg6`, `cap3`) e são alvo de
    # "ver o Diagrama 6" e "no capítulo 3", como no EPUB.
    escrita = _EscritaDoDocx(doc, escrito, idioma, msg, simbolos, familia,
                             _alvos_das_paginas(com_conteudo, numeros),
                             links_internos.numerados(com_conteudo), quebras, realce, analise)
    for numero_da_pagina, pagina in enumerate(com_conteudo):
        escrita.pagina(numero_da_pagina, pagina)

    momento = instante()
    _propriedades(doc, metadados, idioma, momento)
    bruto = io.BytesIO()
    doc.save(bruto)
    partes = _partes_finais(bruto.getvalue(), recurso)
    _gravar_reprodutivel(Path(caminho), partes, data_no_zip(momento))
    return escrito


def _com_conteudo(paginas: Sequence[PaginaExtraida]) -> List[PaginaExtraida]:
    """As páginas com uma figura ou um parágrafo com texto."""
    return [p for p in paginas if any(
        isinstance(b, Figura) or (isinstance(b, Paragrafo) and b.texto.strip())
        for b in p.blocos)]


def _fonte_dos_simbolos(paginas: Sequence[PaginaExtraida]):
    """(família, arquivo, símbolos) da fonte que cobre os símbolos do texto, ou nada."""
    from core.exportar import fonte_dos_simbolos

    return fonte_dos_simbolos("".join(b.texto for p in paginas for b in p.blocos
                                      if isinstance(b, Paragrafo)))


def _alvos_das_paginas(com_conteudo: Sequence[PaginaExtraida],
                       numeros: Optional[Dict[int, int]]) -> Dict[int, str]:
    """O marcador de cada página pelo número impresso dela, quando se sabe."""
    alvos = {}
    for pagina in com_conteudo:
        if numeros and pagina.numero in numeros:
            alvos[numeros[pagina.numero]] = f"pg{pagina.numero + 1}"
    return alvos


@dataclass
class _EscritaDoDocx:
    """O que `escrever` sabe enquanto passa pelos blocos: o documento, o que entra no texto e
    o último id de marcador; `pendente` é o marcador da página que ainda não caiu num
    parágrafo, e `quebrar`, se ela começa numa página nova."""

    doc: object
    escrito: EscritoDocx
    idioma: str
    msg: Dict[str, str]
    simbolos: str
    familia: str
    alvos: Dict[int, str]
    contados: links_internos.Numerados
    quebras: bool
    realce: bool
    analise: str
    ident: int = 0
    pendente: str = ""
    quebrar: bool = False

    def __post_init__(self) -> None:
        self.por_diagrama = {n: f"dg{n}" for n in self.contados.figuras.values()}
        self.por_capitulo = {n: f"cap{n}" for n in self.contados.capitulos.values()}

    def marcar(self, paragrafo, nome: str) -> None:
        self.ident += 1
        _marcador(paragrafo, nome, self.ident)

    def pagina(self, numero_da_pagina: int, pagina: PaginaExtraida) -> None:
        self.pendente = f"pg{pagina.numero + 1}"
        self.quebrar = bool(numero_da_pagina)
        for bloco in pagina.blocos:
            if isinstance(bloco, Figura):
                self.figura(bloco)
            elif isinstance(bloco, Paragrafo) and bloco.texto.strip():
                self.paragrafo(bloco)

    def comecar_a_pagina(self, paragrafo) -> None:
        """O primeiro parágrafo da página leva o marcador dela. A página impressa começa numa
        página nova, como no livro (o DOCX é o formato de editar o livro, e o número dela
        fica no marcador)."""
        if not self.pendente:
            return
        if self.quebrar:
            paragrafo.paragraph_format.page_break_before = True
        self.marcar(paragrafo, self.pendente)
        self.pendente = ""

    def figura(self, bloco: Figura) -> None:
        self.escrito.figuras += 1
        _figura(self.doc, bloco, epub.alternativo(bloco, self.msg, self.idioma),
                self.escrito.figuras)
        paragrafo = self.doc.paragraphs[-1]
        self.comecar_a_pagina(paragrafo)
        if id(bloco) in self.contados.figuras:
            self.marcar(paragrafo, f"dg{self.contados.figuras[id(bloco)]}")
        _ressalva(self.doc, bloco, self.idioma)
        if _link_de_analise(self.doc, bloco, self.analise, self.idioma):
            self.escrito.analises += 1

    def paragrafo(self, bloco: Paragrafo) -> None:
        if bloco.titulo:
            estilo = "Heading 1" if bloco.nivel == 1 else "Heading 2"
            self.escrito.titulos += 1
            links: list = []
        else:
            estilo = None
            links = links_internos.referencias_internas(
                bloco.texto, self.idioma, self.alvos,
                {} if id(bloco) in self.contados.legendas else self.por_diagrama,
                self.por_capitulo)
            self.escrito.links += len(links)
        paragrafo = self.doc.add_paragraph(style=estilo)
        _texto_com_estilo(paragrafo, bloco, self.simbolos, self.familia, links, self.quebras,
                          self.realce)
        if self.realce and getattr(bloco, "duvidosos", None):
            self.escrito.realcados += 1
        self.escrito.paragrafos += 1
        if id(bloco) in self.contados.capitulos:
            self.marcar(paragrafo, f"cap{self.contados.capitulos[id(bloco)]}")
        self.comecar_a_pagina(paragrafo)


def _propriedades(doc, metadados: epub.Metadados, idioma: str, momento) -> None:
    """As propriedades do documento, com a data do `instante` (os mesmos bytes, CA-12.6)."""
    data = datetime.datetime.fromtimestamp(momento, datetime.timezone.utc).replace(tzinfo=None)
    propriedades = doc.core_properties
    propriedades.title = epub.limpo(metadados.titulo)
    propriedades.author = epub.limpo("; ".join(metadados.autores))
    propriedades.subject = epub.limpo("; ".join(metadados.assuntos))
    propriedades.keywords = epub.limpo("; ".join(metadados.assuntos))
    propriedades.language = idioma
    propriedades.identifier = epub.limpo(metadados.identificador_do_livro())
    propriedades.last_modified_by = "AbbyChessCraft"
    propriedades.comments = ""
    propriedades.revision = 1
    propriedades.created = data
    propriedades.modified = data


def _partes_finais(dados: bytes, recurso) -> Dict[str, bytes]:
    """As partes do pacote como vão para o disco: sem a miniatura e as sobras do modelo
    do python-docx (a página em branco, a data de impressão), e com a fonte dos símbolos
    embutida do jeito que o Word espera (ECMA-376 §15.2.13: ofuscada, o `.odttf` no
    `[Content_Types]`, a fonte no `fontTable` com o relacionamento, e o
    `w:embedTrueTypeFonts` nas configurações, logo depois do `w:zoom`)."""
    import re

    from core.exportar import GUID_DA_FONTE, REL_DE_FONTE, TIPO_OFUSCADO, ofuscar

    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        partes = {info.filename: z.read(info) for info in z.infolist()}
    miniatura = "docProps/thumbnail.jpeg"
    if miniatura in partes:
        del partes[miniatura]
        partes["_rels/.rels"] = re.sub(rb'<Relationship [^>]*Target="docProps/thumbnail\.jpeg"/>',
                                       b"", partes["_rels/.rels"])
        partes["[Content_Types].xml"] = re.sub(
            rb'<Override PartName="/docProps/thumbnail\.jpeg"[^>]*/>', b"",
            partes["[Content_Types].xml"])
    if "docProps/core.xml" in partes:
        partes["docProps/core.xml"] = re.sub(rb"<cp:lastPrinted>.*?</cp:lastPrinted>", b"",
                                             partes["docProps/core.xml"])
    if not recurso:
        return partes
    familia, origem = recurso[0], recurso[1]
    with open(origem, "rb") as f:
        partes["word/fonts/fonte1.odttf"] = ofuscar(f.read())
    tipos = partes["[Content_Types].xml"].decode("utf-8")
    if "odttf" not in tipos:
        abertura = tipos.index(">", tipos.index("<Types")) + 1
        tipos = (tipos[:abertura] + f'<Default Extension="odttf" ContentType="{TIPO_OFUSCADO}"/>'
                 + tipos[abertura:])
        partes["[Content_Types].xml"] = tipos.encode("utf-8")
    nome = familia.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    tabela = partes["word/fontTable.xml"].decode("utf-8")
    corte = tabela.index("</w:fonts>")
    tabela = (tabela[:corte] + f'<w:font w:name="{nome}"><w:embedRegular r:id="rIdFonte1" '
              f'w:fontKey="{GUID_DA_FONTE}"/></w:font>' + tabela[corte:])
    if "xmlns:r=" not in tabela[:tabela.index(">", tabela.index("<w:fonts"))]:
        tabela = tabela.replace("<w:fonts ", f'<w:fonts xmlns:r="{_R}" ', 1)
    partes["word/fontTable.xml"] = tabela.encode("utf-8")
    partes["word/_rels/fontTable.xml.rels"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rIdFonte1" Type="{REL_DE_FONTE}" Target="fonts/fonte1.odttf"/>'
        "</Relationships>").encode("utf-8")
    ajustes = partes["word/settings.xml"].decode("utf-8")
    if "embedTrueTypeFonts" not in ajustes:
        if "<w:zoom" in ajustes:
            corte = ajustes.index("/>", ajustes.index("<w:zoom")) + 2
        else:
            corte = ajustes.index(">", ajustes.index("<w:settings")) + 1
        ajustes = ajustes[:corte] + "<w:embedTrueTypeFonts/>" + ajustes[corte:]
        partes["word/settings.xml"] = ajustes.encode("utf-8")
    return partes


def _gravar_reprodutivel(caminho: Path, partes: Dict[str, bytes], data_hora) -> None:
    """As partes num zip com a mesma data e os mesmos atributos em toda entrada (o
    python-docx carimba a hora de agora), ao lado; conferido antes de trocar com o
    anterior: um DOCX que não passa em `conferir` não é publicado."""
    def escrever(temporario: Path) -> None:
        with zipfile.ZipFile(temporario, "w", zipfile.ZIP_DEFLATED) as destino:
            for nome, dados in partes.items():
                info = zipfile.ZipInfo(nome, date_time=data_hora)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0o644 << 16
                destino.writestr(info, dados)

    def recusar_o_estragado(temporario: Path) -> None:
        problemas = conferir(temporario)
        if problemas:
            raise ValueError("O DOCX não passou na conferência: " + "; ".join(problemas))

    gv.gravar_por(caminho, escrever, recusar_o_estragado)


# ----------------------------------------------------------------------
# Conferir
# ----------------------------------------------------------------------

def conferir(caminho: str | Path) -> List[str]:
    """Os problemas do DOCX que o Word recusaria ou mostraria quebrado; lista vazia é
    arquivo são."""
    try:
        z = zipfile.ZipFile(caminho)
    except (zipfile.BadZipFile, OSError) as erro:
        return [f"o DOCX não abre como zip ({erro})"]
    with z:
        problemas, seguir = _problemas_do_pacote(z)
    if not seguir:
        return problemas
    try:
        from docx import Document

        Document(str(caminho))
    except Exception as erro:  # noqa: BLE001 — o que o python-docx não abre, o Word também não
        problemas.append(f"o python-docx não abre o arquivo ({erro})")
    return problemas


def _problemas_do_pacote(z: zipfile.ZipFile) -> Tuple[List[str], bool]:
    """(os problemas, se vale abrir pelo python-docx): sem as partes obrigatórias ou com o
    XML ilegível, o resto nem se confere."""
    nomes = set(z.namelist())
    faltam = [f"falta {obrigatorio}" for obrigatorio in (
        "[Content_Types].xml", "word/document.xml", "word/_rels/document.xml.rels")
        if obrigatorio not in nomes]
    if faltam:
        return faltam, False
    try:
        documento = ElementTree.fromstring(z.read("word/document.xml"))
        relacoes = ElementTree.fromstring(z.read("word/_rels/document.xml.rels"))
    except ElementTree.ParseError as erro:
        return [f"XML ilegível ({erro})"], False
    problemas = _problemas_das_imagens(documento, relacoes, nomes)
    marcadores = _marcadores(documento, problemas)
    problemas += _problemas_dos_hiperlinks(documento, relacoes, marcadores)
    problemas += _figuras_repetidas(documento)
    problemas += _problemas_da_fonte(z, nomes)
    return problemas, True


def _problemas_das_imagens(documento: ElementTree.Element, relacoes: ElementTree.Element,
                           nomes: set) -> List[str]:
    """Cada imagem citada aponta uma parte do pacote."""
    alvos = {r.get("Id"): r.get("Target") for r in relacoes}
    problemas = []
    for blip in documento.iter(f"{{{_A}}}blip"):
        ident = blip.get(f"{{{_R}}}embed")
        alvo = alvos.get(ident)
        if alvo is None or f"word/{alvo}" not in nomes:
            problemas.append(f"a imagem {ident} não está no pacote")
    return problemas


def _marcadores(documento: ElementTree.Element, problemas: List[str]) -> set:
    """Os nomes dos marcadores; acusa o nome e o id repetidos e o marcador que não fecha."""
    marcadores, ids = set(), set()
    for marca in documento.iter(f"{{{_W}}}bookmarkStart"):
        nome, ident = marca.get(f"{{{_W}}}name"), marca.get(f"{{{_W}}}id")
        if nome in marcadores:
            problemas.append(f"o marcador {nome} se repete")
        if ident in ids:
            problemas.append(f"o id de marcador {ident} se repete")
        marcadores.add(nome)
        ids.add(ident)
    fechados = {m.get(f"{{{_W}}}id") for m in documento.iter(f"{{{_W}}}bookmarkEnd")}
    for ident in ids - fechados:
        problemas.append(f"o marcador de id {ident} não fecha")
    return marcadores


def _problemas_dos_hiperlinks(documento: ElementTree.Element, relacoes: ElementTree.Element,
                              marcadores: set) -> List[str]:
    """O hiperlink interno vai a um marcador; o externo, a um endereço."""
    externos = {r.get("Id"): r.get("Target") for r in relacoes
                if r.get("TargetMode") == "External"}
    problemas = []
    for link in documento.iter(f"{{{_W}}}hyperlink"):
        problema = _problema_do_hiperlink(link, marcadores, externos)
        if problema:
            problemas.append(problema)
    return problemas


def _problema_do_hiperlink(link: ElementTree.Element, marcadores: set,
                           externos: Dict[str, str]) -> str:
    ancora = link.get(f"{{{_W}}}anchor")
    if ancora is None and link.get(f"{{{_R}}}id") is None:
        return "hiperlink sem destino"
    if ancora is not None and ancora not in marcadores:
        return f"o hiperlink para {ancora} não tem marcador"
    if ancora is None and not externos.get(link.get(f"{{{_R}}}id")):
        return f"o hiperlink {link.get(f'{{{_R}}}id')} não tem endereço externo"
    return ""


def _figuras_repetidas(documento: ElementTree.Element) -> List[str]:
    figuras = [d.get("id") for d in documento.iter(
        "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr")]
    return ["ids de figura repetidos"] if len(figuras) != len(set(figuras)) else []


def _problemas_da_fonte(z: zipfile.ZipFile, nomes: set) -> List[str]:
    """A fonte embutida tem relacionamento, e o arquivo dela está no pacote."""
    if "word/fontTable.xml" not in nomes or b"embedRegular" not in z.read("word/fontTable.xml"):
        return []
    rels = "word/_rels/fontTable.xml.rels"
    if rels not in nomes:
        return ["a fonte embutida não tem relacionamento"]
    return [f"a fonte {rel.get('Target')} não está no pacote"
            for rel in ElementTree.fromstring(z.read(rels))
            if f"word/{rel.get('Target')}" not in nomes]
