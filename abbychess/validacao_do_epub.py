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
    problemas: List[str] = []
    with zipfile.ZipFile(caminho) as z:
        nomes = set(z.namelist())
        infos = z.infolist()
        if not infos or infos[0].filename != "mimetype":
            problemas.append("o mimetype não é a primeira entrada")
        elif infos[0].compress_type != zipfile.ZIP_STORED:
            problemas.append("o mimetype está comprimido")
        elif z.read("mimetype") != b"application/epub+zip":
            problemas.append("o mimetype não é application/epub+zip")
        try:
            container = ElementTree.fromstring(z.read("META-INF/container.xml"))
            opf_nome = container.find(".//c:rootfile", _NS).get("full-path")
        except (KeyError, ElementTree.ParseError, AttributeError):
            return problemas + ["o META-INF/container.xml falta ou não aponta o OPF"]
        if opf_nome not in nomes:
            return problemas + [f"o OPF {opf_nome} não está no pacote"]
        try:
            opf = ElementTree.fromstring(z.read(opf_nome))
        except ElementTree.ParseError as erro:
            return problemas + [f"o OPF não é XML legível ({erro})"]
        base = posixpath.dirname(opf_nome)
        metadados = opf.find("opf:metadata", _NS)
        dc = "{http://purl.org/dc/elements/1.1/}"
        for campo in ("title", "language", "identifier"):
            achado = metadados.find(dc + campo) if metadados is not None else None
            if achado is None or not (achado.text or "").strip():
                problemas.append(f"o OPF não tem dc:{campo}")
        if metadados is None or not any(m.get("property") == "dcterms:modified"
                                        for m in metadados.findall("opf:meta", _NS)):
            problemas.append("o OPF não tem dcterms:modified")
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
        refs = opf.findall(".//opf:spine/opf:itemref", _NS)
        if not refs:
            problemas.append("a espinha está vazia")
        na_espinha = set()
        for ref in refs:
            if ref.get("idref") not in itens:
                problemas.append(f"o itemref {ref.get('idref')} não está no manifesto")
            else:
                na_espinha.add(_resolver(base, itens[ref.get("idref")].get("href") or "")[0])
        navs = [i for i in itens.values() if "nav" in (i.get("properties") or "").split()]
        if len(navs) != 1:
            problemas.append(f"o manifesto tem {len(navs)} nav (precisa de um)")

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
            vistos: set = set()
            for el in arvore.iter():
                ident = el.get("id")
                if ident is None:
                    continue
                if ident in vistos:
                    problemas.append(f"{nome}: o id {ident} se repete")
                vistos.add(ident)
            ids[nome] = vistos
        for nome, arvore in arvores.items():
            pasta = posixpath.dirname(nome)
            for el in arvore.iter():
                for atributo in ("href", "src"):
                    link = el.get(atributo)
                    if not link or re.match(r"^[a-z][a-z0-9+.-]*:", link, re.I):
                        continue                # http:, mailto:, data:
                    alvo, fragmento = _resolver(pasta, link)
                    alvo = alvo or nome
                    if alvo not in no_manifesto:
                        problemas.append(f"{nome}: link quebrado {link}")
                    elif fragmento and alvo in ids and fragmento not in ids[alvo]:
                        problemas.append(f"{nome}: âncora inexistente {link}")
                    elif (el.tag == "{http://www.w3.org/1999/xhtml}a"
                          and no_manifesto[alvo] == "application/xhtml+xml"
                          and alvo not in na_espinha):
                        # O que o EPUBCheck chama RSC-011.
                        problemas.append(f"{nome}: link para fora da espinha {link}")
        for nome, tipo in sorted(no_manifesto.items()):
            if tipo == "text/css" and nome in nomes:
                for link in _URL_DO_CSS.findall(z.read(nome).decode("utf-8", "replace")):
                    alvo, _ = _resolver(posixpath.dirname(nome), link)
                    if alvo not in no_manifesto:
                        problemas.append(f"{nome}: url() quebrada {link}")
        if navs:
            nav_nome, _ = _resolver(base, navs[0].get("href") or "")
            nav = arvores.get(nav_nome)
            for tipo in ("toc", "page-list"):
                el = None if nav is None else next(
                    (n for n in nav.iter("{http://www.w3.org/1999/xhtml}nav")
                     if n.get(_EPUB_TYPE) == tipo), None)
                if el is None:
                    problemas.append(f"o nav não tem {tipo}")
                elif el.find(".//x:li", _NS) is None:
                    problemas.append(f"o {tipo} do nav está vazio")
    return problemas


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
    import subprocess

    import fitz

    executavel = os.environ.get("ABBY_CALIBRE")
    if not executavel or not Path(executavel).is_file():
        return None
    problemas: List[str] = []
    do_texto: List[str] = []                    # o texto de cada link interno, fora do nav
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
    with tempfile.TemporaryDirectory(prefix="calibre-") as pasta:
        pdf = Path(pasta) / "livro.pdf"
        processo = subprocess.Popen([executavel, str(caminho), str(pdf)], stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                    errors="replace")
        try:
            texto_da_saida, _ = processo.communicate(timeout=600)
        except subprocess.TimeoutExpired:
            # O `ebook-convert` abre filhos (`calibre-parallel`): a árvore inteira sai.
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(processo.pid)],
                               capture_output=True, check=False)
            processo.kill()
            processo.communicate()
            return ["o Calibre não converteu o EPUB em 600 s"]
        if processo.returncode != 0 or not pdf.is_file():
            ultimas = texto_da_saida.strip().splitlines()[-3:]
            return [f"o Calibre não converteu o EPUB (código {processo.returncode}): "
                    + " | ".join(ultimas)]
        problemas += [f"o Calibre avisou: {linha.strip()}"
                      for linha in texto_da_saida.splitlines()
                      if re.search(r"Traceback|Failed to|Could not|not found|Unknown link",
                                   linha)]
        with fitz.open(pdf) as doc:
            no_pdf, fora = [], 0
            for pagina in doc:
                for link in pagina.get_links():
                    if link.get("kind") != fitz.LINK_GOTO:
                        continue
                    if not 0 <= link.get("page", -1) < doc.page_count:
                        fora += 1
                    no_pdf.append(" ".join(pagina.get_textbox(link["from"]).split()))
    # Cada link do texto casa com um do PDF de texto igual, ou, sem ele, com o mais curto que
    # contém o texto dele (a caixa do PDF pode levar a pontuação vizinha; "Diagrama 1" não
    # gasta o "Diagrama 12" de outro link). Os do sumário sobram, e tudo bem.
    for texto in do_texto:
        iguais = [k for k, t in enumerate(no_pdf) if t == texto]
        contem = sorted((len(t), k) for k, t in enumerate(no_pdf) if texto in t)
        achado = iguais[0] if iguais else (contem[0][1] if contem else None)
        if achado is None:
            problemas.append(f"o link \"{texto}\" não saiu como link no PDF do Calibre")
        else:
            del no_pdf[achado]
    if fora:
        problemas.append(f"{fora} link(s) do PDF do Calibre levam para fora do livro")
    return problemas


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
