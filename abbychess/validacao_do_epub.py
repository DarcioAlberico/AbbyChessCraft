"""A validação do EPUB escrito (SPEC §12.1, passo J): a conferência interna e os validadores
externos.

- `conferir` lê o arquivo e acusa o que um leitor recusaria (o pacote, o manifesto, os links,
  o XML). O escritor (`abbychess.epub`) a roda antes de trocar o arquivo anterior.
- `epubcheck`, `ace` e `calibre` rodam o EPUBCheck, o Ace by DAISY e o Calibre, quando
  configurados (`ABBY_EPUBCHECK`, `ABBY_ACE`, `ABBY_CALIBRE`); sem eles, `None`. Só rodam no
  portão.
"""

from __future__ import annotations

import html
import os
import posixpath
import re
import tempfile
import zipfile
from urllib.parse import unquote
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree


_NS = {"opf": "http://www.idpf.org/2007/opf", "x": "http://www.w3.org/1999/xhtml",
       "epub": "http://www.idpf.org/2007/ops",
       "c": "urn:oasis:names:tc:opendocument:xmlns:container"}


_URL_DO_CSS = re.compile(r"url\(\s*[\"']?([^\"')]+)[\"']?\s*\)")
_EPUB_TYPE = "{http://www.idpf.org/2007/ops}type"


def _resolver(base_do_arquivo: str, link: str) -> Tuple[str, str]:
    """(entrada do zip, fragmento) de um link relativo, já decodificado (`%20`)."""
    arquivo, _, fragmento = link.partition("#")
    arquivo = unquote(arquivo)
    alvo = posixpath.normpath(posixpath.join(base_do_arquivo, arquivo)) if arquivo else ""
    return alvo, unquote(fragmento)


def conferir(caminho: str | Path) -> List[str]:
    """Os problemas do EPUB que um leitor recusaria; lista vazia é arquivo são.

    Confere o pacote (`mimetype` primeiro e sem compressão, o `container.xml`), o OPF (XML
    legível, `dc:title`, `dc:language`, `dcterms:modified`, ids sem repetição, todo item
    existe, todo `itemref` está no manifesto, um `nav`, espinha não vazia), cada XHTML (XML
    legível, ids sem repetição, cada `href` e `src` — decodificados — apontando um item do
    manifesto e, com `#`, um id dele), o `url()` do CSS e o `nav` (`toc` e `page-list` com
    itens). Não substitui o EPUBCheck (`epubcheck`), que confere o esquema inteiro."""
    with zipfile.ZipFile(caminho) as z:
        nomes = set(z.namelist())
        problemas = _problemas_do_mimetype(z)
        opf_nome, opf, recusa = _opf_do_pacote(z, nomes)
        if opf is None:
            return problemas + [recusa]
        base = posixpath.dirname(opf_nome)
        problemas += _problemas_dos_metadados(opf.find("opf:metadata", _NS))
        itens, no_manifesto = _manifesto(opf, base, nomes, problemas)
        na_espinha = _espinha(opf, base, itens, problemas)
        navs = _navs(itens, problemas)
        arvores, ids = _xhtml_do_manifesto(z, nomes, no_manifesto, problemas)
        for nome, arvore in arvores.items():
            problemas += _problemas_dos_links(nome, arvore, no_manifesto, ids, na_espinha)
        problemas += _problemas_do_css(z, nomes, no_manifesto)
        problemas += _problemas_do_nav(navs, base, arvores)
    return problemas


def _problemas_do_mimetype(z: zipfile.ZipFile) -> List[str]:
    """O `mimetype` é a primeira entrada, sem compressão, e diz que o pacote é um EPUB."""
    infos = z.infolist()
    if not infos or infos[0].filename != "mimetype":
        return ["o mimetype não é a primeira entrada"]
    if infos[0].compress_type != zipfile.ZIP_STORED:
        return ["o mimetype está comprimido"]
    if z.read("mimetype") != b"application/epub+zip":
        return ["o mimetype não é application/epub+zip"]
    return []


def _opf_do_pacote(z: zipfile.ZipFile, nomes: set
                   ) -> Tuple[str, Optional[ElementTree.Element], str]:
    """(o nome do OPF, a árvore dele, ""), pelo `container.xml`; sem ela, o problema que
    impede de conferir o resto."""
    try:
        container = ElementTree.fromstring(z.read("META-INF/container.xml"))
        opf_nome = container.find(".//c:rootfile", _NS).get("full-path")
    except (KeyError, ElementTree.ParseError, AttributeError):
        return "", None, "o META-INF/container.xml falta ou não aponta o OPF"
    if opf_nome not in nomes:
        return opf_nome, None, f"o OPF {opf_nome} não está no pacote"
    try:
        return opf_nome, ElementTree.fromstring(z.read(opf_nome)), ""
    except ElementTree.ParseError as erro:
        return opf_nome, None, f"o OPF não é XML legível ({erro})"


def _problemas_dos_metadados(metadados: Optional[ElementTree.Element]) -> List[str]:
    """O `dc:title`, o `dc:language` e o `dc:identifier` com texto, e o `dcterms:modified`."""
    problemas = []
    dc = "{http://purl.org/dc/elements/1.1/}"
    for campo in ("title", "language", "identifier"):
        achado = metadados.find(dc + campo) if metadados is not None else None
        if achado is None or not (achado.text or "").strip():
            problemas.append(f"o OPF não tem dc:{campo}")
    if not _tem_a_data_da_mudanca(metadados):
        problemas.append("o OPF não tem dcterms:modified")
    return problemas


def _tem_a_data_da_mudanca(metadados: Optional[ElementTree.Element]) -> bool:
    return metadados is not None and any(m.get("property") == "dcterms:modified"
                                         for m in metadados.findall("opf:meta", _NS))


def _manifesto(opf: ElementTree.Element, base: str, nomes: set, problemas: List[str]
               ) -> Tuple[Dict[str, ElementTree.Element], Dict[str, str]]:
    """Os itens do manifesto por id e o media-type de cada entrada do zip que ele cita;
    acusa o id repetido, o item sem `href` e o que não está no pacote."""
    itens: Dict[str, ElementTree.Element] = {}
    no_manifesto: Dict[str, str] = {}         # entrada do zip -> media-type
    for item in opf.findall(".//opf:manifest/opf:item", _NS):
        ident, href = item.get("id"), item.get("href")
        if ident in itens:
            problemas.append(f"o id {ident} se repete no manifesto")
        itens[ident] = item
        if not href:
            problemas.append(f"o item {ident} não tem href")
            continue
        alvo, _ = _resolver(base, href)
        no_manifesto[alvo] = item.get("media-type") or ""
        if alvo not in nomes:
            problemas.append(f"o item {href} do manifesto não está no pacote")
    return itens, no_manifesto


def _espinha(opf: ElementTree.Element, base: str, itens: Dict[str, ElementTree.Element],
             problemas: List[str]) -> set:
    """As entradas do zip na espinha; acusa a espinha vazia e o `itemref` fora do manifesto."""
    refs = opf.findall(".//opf:spine/opf:itemref", _NS)
    if not refs:
        problemas.append("a espinha está vazia")
    na_espinha = set()
    for ref in refs:
        if ref.get("idref") not in itens:
            problemas.append(f"o itemref {ref.get('idref')} não está no manifesto")
        else:
            na_espinha.add(_resolver(base, itens[ref.get("idref")].get("href") or "")[0])
    return na_espinha


def _navs(itens: Dict[str, ElementTree.Element], problemas: List[str]
          ) -> List[ElementTree.Element]:
    """Os itens do manifesto com `properties="nav"`; acusa se não for um só."""
    navs = [i for i in itens.values() if "nav" in (i.get("properties") or "").split()]
    if len(navs) != 1:
        problemas.append(f"o manifesto tem {len(navs)} nav (precisa de um)")
    return navs


def _xhtml_do_manifesto(z: zipfile.ZipFile, nomes: set, no_manifesto: Dict[str, str],
                        problemas: List[str]
                        ) -> Tuple[Dict[str, ElementTree.Element], Dict[str, set]]:
    """A árvore e os ids de cada XHTML do manifesto que está no pacote; acusa o que não é XML
    legível e o id repetido."""
    arvores: Dict[str, ElementTree.Element] = {}
    ids: Dict[str, set] = {}
    for nome, tipo in sorted(no_manifesto.items()):
        if tipo != "application/xhtml+xml" or nome not in nomes:
            continue
        try:
            arvore = ElementTree.fromstring(z.read(nome))
        except ElementTree.ParseError as erro:
            problemas.append(f"{nome}: XML inválido ({erro})")
            continue
        arvores[nome] = arvore
        ids[nome] = _ids_do_xhtml(nome, arvore, problemas)
    return arvores, ids


def _ids_do_xhtml(nome: str, arvore: ElementTree.Element, problemas: List[str]) -> set:
    vistos: set = set()
    for el in arvore.iter():
        ident = el.get("id")
        if ident is None:
            continue
        if ident in vistos:
            problemas.append(f"{nome}: o id {ident} se repete")
        vistos.add(ident)
    return vistos


def _problemas_dos_links(nome: str, arvore: ElementTree.Element, no_manifesto: Dict[str, str],
                         ids: Dict[str, set], na_espinha: set) -> List[str]:
    """Cada `href` e `src` relativo do XHTML aponta um item do manifesto (e, com `#`, um id
    dele); o `<a>` para um XHTML, um da espinha."""
    problemas = []
    pasta = posixpath.dirname(nome)
    for el in arvore.iter():
        for atributo in ("href", "src"):
            link = el.get(atributo)
            if not link or re.match(r"^[a-z][a-z0-9+.-]*:", link, re.I):
                continue                # http:, mailto:, data:
            alvo, fragmento = _resolver(pasta, link)
            problema = _problema_do_link(el.tag, alvo or nome, fragmento, no_manifesto, ids,
                                         na_espinha)
            if problema:
                problemas.append(f"{nome}: {problema} {link}")
    return problemas


def _problema_do_link(tag: str, alvo: str, fragmento: str, no_manifesto: Dict[str, str],
                      ids: Dict[str, set], na_espinha: set) -> str:
    if alvo not in no_manifesto:
        return "link quebrado"
    if fragmento and alvo in ids and fragmento not in ids[alvo]:
        return "âncora inexistente"
    if (tag == "{http://www.w3.org/1999/xhtml}a" and no_manifesto[alvo] == "application/xhtml+xml"
            and alvo not in na_espinha):
        return "link para fora da espinha"          # o que o EPUBCheck chama RSC-011
    return ""


def _problemas_do_css(z: zipfile.ZipFile, nomes: set, no_manifesto: Dict[str, str]) -> List[str]:
    """Cada `url()` dos CSS do manifesto aponta um item dele."""
    problemas = []
    for nome, tipo in sorted(no_manifesto.items()):
        if tipo == "text/css" and nome in nomes:
            for link in _URL_DO_CSS.findall(z.read(nome).decode("utf-8", "replace")):
                alvo, _ = _resolver(posixpath.dirname(nome), link)
                if alvo not in no_manifesto:
                    problemas.append(f"{nome}: url() quebrada {link}")
    return problemas


def _problemas_do_nav(navs: List[ElementTree.Element], base: str,
                      arvores: Dict[str, ElementTree.Element]) -> List[str]:
    """O `nav` (o primeiro, se há mais de um) tem `toc` e `page-list`, cada um com itens."""
    if not navs:
        return []
    nav = arvores.get(_resolver(base, navs[0].get("href") or "")[0])
    problemas = []
    for tipo in ("toc", "page-list"):
        el = _nav_do_tipo(nav, tipo)
        if el is None:
            problemas.append(f"o nav não tem {tipo}")
        elif el.find(".//x:li", _NS) is None:
            problemas.append(f"o {tipo} do nav está vazio")
    return problemas


def _nav_do_tipo(nav: Optional[ElementTree.Element], tipo: str) -> Optional[ElementTree.Element]:
    return None if nav is None else next(
        (n for n in nav.iter("{http://www.w3.org/1999/xhtml}nav") if n.get(_EPUB_TYPE) == tipo),
        None)


def ace(caminho: str | Path) -> Optional[List[str]]:
    """As violações de acessibilidade que o Ace by DAISY acha, se ele estiver configurado
    (`ABBY_ACE`: o caminho do executável `ace`, ou `ace.cmd` no Windows); `None` sem ele.

    Cada violação vem como "[impacto] arquivo: regra — descrição". O Ace roda num Chrome
    sem janela (Puppeteer) e leva alguns segundos; o relatório dele vai a uma pasta
    temporária, que some depois."""
    import json
    import subprocess

    executavel = os.environ.get("ABBY_ACE")
    if not executavel or not Path(executavel).is_file():
        return None
    with tempfile.TemporaryDirectory(prefix="ace-") as pasta:
        subprocess.run([executavel, "--force", "--silent", "-o", pasta, str(caminho)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=600, check=False)
        relatorio = Path(pasta) / "report.json"
        if not relatorio.is_file():
            return ["o Ace não produziu relatório"]
        dados = json.loads(relatorio.read_text(encoding="utf-8"))
    violacoes = []
    for documento in dados.get("assertions", []):
        alvo = documento.get("earl:testSubject", {}).get("url", "")
        for teste in documento.get("assertions", []):
            resultado = teste.get("earl:result", {})
            if resultado.get("earl:outcome") == "pass":
                continue
            regra = teste.get("earl:test", {})
            violacoes.append(f"[{regra.get('earl:impact', '?')}] {alvo}: "
                             f"{regra.get('dct:title', '?')} — {resultado.get('dct:description', '')}")
    return violacoes


def calibre(caminho: str | Path) -> Optional[List[str]]:
    """Os problemas do EPUB aberto num leitor de verdade, o Calibre, se ele estiver
    configurado (`ABBY_CALIBRE`: o caminho do `ebook-convert`); `None` sem ele.

    O Calibre converte o EPUB em PDF pelo motor dele (o mesmo Chromium do leitor): a conversão
    tem de acabar sem erro, e cada link interno do texto (os do `nav` à parte) tem de sair como
    link para uma página do PDF. É o que dá para conferir sem olhar; o resto (a figura, a
    fonte dos símbolos) se vê no PDF."""
    executavel = os.environ.get("ABBY_CALIBRE")
    if not executavel or not Path(executavel).is_file():
        return None
    return _no_calibre(executavel, caminho)


def _no_calibre(executavel: str, caminho: str | Path) -> List[str]:
    """Converte o EPUB em PDF pelo `executavel` e confere a conversão e os links."""
    do_texto = _links_do_texto(caminho)
    with tempfile.TemporaryDirectory(prefix="calibre-") as pasta:
        pdf = Path(pasta) / "livro.pdf"
        codigo, texto_da_saida = _converter(executavel, caminho, pdf)
        if codigo is None:
            return ["o Calibre não converteu o EPUB em 600 s"]
        if codigo != 0 or not pdf.is_file():
            ultimas = texto_da_saida.strip().splitlines()[-3:]
            return [f"o Calibre não converteu o EPUB (código {codigo}): " + " | ".join(ultimas)]
        problemas = _avisos_do_calibre(texto_da_saida)
        no_pdf, fora = _links_do_pdf(pdf)
    problemas += _links_que_faltam(do_texto, no_pdf)
    if fora:
        problemas.append(f"{fora} link(s) do PDF do Calibre levam para fora do livro")
    return problemas


def _converter(executavel: str, caminho: str | Path, pdf: Path) -> Tuple[Optional[int], str]:
    """(o código de saída, o que o `ebook-convert` imprimiu); `None` no código se ele passou
    de 600 s (e foi morto)."""
    import subprocess

    processo = subprocess.Popen([executavel, str(caminho), str(pdf)], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                errors="replace")
    try:
        texto_da_saida, _ = processo.communicate(timeout=600)
    except subprocess.TimeoutExpired:
        _matar_a_arvore(processo)
        return None, ""
    return processo.returncode, texto_da_saida


def _matar_a_arvore(processo) -> None:
    """O `ebook-convert` abre filhos (`calibre-parallel`): a árvore inteira sai."""
    import subprocess

    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(processo.pid)],
                       capture_output=True, check=False)
    processo.kill()
    processo.communicate()


def _links_do_texto(caminho: str | Path) -> List[str]:
    """O texto visível de cada link interno dos XHTML do EPUB, fora do `nav`."""
    do_texto: List[str] = []
    with zipfile.ZipFile(caminho) as z:
        for nome in z.namelist():
            if nome.endswith(".xhtml") and not nome.endswith("nav.xhtml"):
                xhtml = z.read(nome).decode("utf-8")
                for href, texto in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', xhtml,
                                              re.S):
                    # O `<br/>` do `manter_quebras` é um espaço no texto do PDF; o link só de
                    # imagem (sem texto) não tem o que casar.
                    visivel = html.unescape(re.sub(r"<[^>]+>", "",
                                                   re.sub(r"<br\s*/?>", " ", texto)))
                    visivel = " ".join(visivel.split())
                    if visivel and not re.match(r"[a-z][a-z0-9+.-]*:", href):
                        do_texto.append(visivel)
    return do_texto


def _avisos_do_calibre(texto_da_saida: str) -> List[str]:
    """As linhas da saída do `ebook-convert` que dizem que algo falhou ou não foi achado."""
    return [f"o Calibre avisou: {linha.strip()}"
            for linha in texto_da_saida.splitlines()
            if re.search(r"Traceback|Failed to|Could not|not found|Unknown link", linha)]


def _links_do_pdf(pdf: Path) -> Tuple[List[str], int]:
    """O texto sob cada link interno do PDF e quantos deles levam para fora das páginas."""
    import fitz

    with fitz.open(pdf) as doc:
        no_pdf, fora = [], 0
        for pagina in doc:
            for link in pagina.get_links():
                if link.get("kind") != fitz.LINK_GOTO:
                    continue
                if not 0 <= link.get("page", -1) < doc.page_count:
                    fora += 1
                no_pdf.append(" ".join(pagina.get_textbox(link["from"]).split()))
    return no_pdf, fora


def _links_que_faltam(do_texto: List[str], no_pdf: List[str]) -> List[str]:
    """Cada link do texto gasta um do PDF (`_o_que_casa`); os do sumário sobram, e tudo bem."""
    problemas = []
    for texto in do_texto:
        achado = _o_que_casa(texto, no_pdf)
        if achado is None:
            problemas.append(f"o link \"{texto}\" não saiu como link no PDF do Calibre")
        else:
            del no_pdf[achado]
    return problemas


def _o_que_casa(texto: str, no_pdf: List[str]) -> Optional[int]:
    """O link do PDF de texto igual, ou, sem ele, o mais curto que contém o texto (a caixa do
    PDF pode levar a pontuação vizinha; "Diagrama 1" não gasta o "Diagrama 12" de outro link)."""
    iguais = [k for k, t in enumerate(no_pdf) if t == texto]
    contem = sorted((len(t), k) for k, t in enumerate(no_pdf) if texto in t)
    return iguais[0] if iguais else (contem[0][1] if contem else None)


def epubcheck(caminho: str | Path) -> Optional[List[str]]:
    """Os erros do EPUBCheck, se ele estiver configurado (`ABBY_EPUBCHECK`: o caminho do
    `epubcheck.jar`); `None` sem ele."""
    import subprocess

    jar = os.environ.get("ABBY_EPUBCHECK")
    if not jar or not Path(jar).is_file():
        return None
    saida = subprocess.run(["java", "-jar", jar, str(caminho)], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=600)
    return [linha for linha in (saida.stdout + saida.stderr).splitlines()
            if linha.startswith(("ERROR", "FATAL"))]
