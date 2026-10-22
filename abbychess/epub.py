"""O EPUB do AbbyChessCraft (SPEC §12.1, passo J): o escritor próprio, sem o do core.

Lê as mesmas `core.pagina.PaginaExtraida` que o DOCX (o Documento já estruturado pela
exportação) e escreve um EPUB 3 que a auditoria do EPUB do Aagaard pediu (roadmap, passo J):

- **Capítulos, não páginas.** Um XHTML por título de capítulo (`<h1>`), partido também
  quando passa de `LIMITE_DO_CAPITULO` caracteres; a página impressa fica como âncora
  (`epub:type="pagebreak"`), não como arquivo.
- **Navegação.** O sumário (`toc`) pelos títulos reais, em níveis (`<h1>` e `<h2>`); a
  lista das páginas (`page-list`); os marcos (`landmarks`: capa, sumário, começo do texto).
  Sem título nenhum, o sumário lista os capítulos pelas páginas que cobrem.
- **Mensagens no idioma do livro** (`MENSAGENS`): "Contents" num livro inglês, não
  "Sumário".
- **Metadados** (`Metadados`): título, autores, editora, data, assuntos, direitos,
  identificador (estável por título e autores quando não dado) e a capa.
- **Acessibilidade calculada**, não declarada: `alternativeText` e `accessModeSufficient`
  textual só quando todo diagrama traz o FEN; `accessibilityHazard` é `unknown`, porque
  ninguém verificou.
- **Diagramas**: o texto alternativo diz o FEN e o lado a jogar (e se foi assumido); o
  recorte diz que o diagrama não foi lido. Imagens iguais byte a byte são um recurso só.
- **Os mesmos bytes**: com o mesmo `SOURCE_DATE_EPOCH`, o mesmo arquivo (CA-12.6): a data
  do pacote e das entradas do zip vem de `core.exportar.instante`, e nada mais varia.

Do core só se usam funções públicas: a fonte dos símbolos (`fonte_dos_simbolos`) e o
instante reprodutível (`instante`, `agora`, `data_no_zip`). `conferir` lê o arquivo
escrito e acusa o que um leitor recusaria (o pacote, o manifesto, os links, o XML).
"""

from __future__ import annotations

import hashlib
import html
import logging
import os
import posixpath
import re
import tempfile
import uuid
import zipfile
from urllib.parse import unquote
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from xml.etree import ElementTree

from core.pagina import Figura, PaginaExtraida, Paragrafo

log = logging.getLogger(__name__)

#: Os caracteres que o XML 1.0 não aceita (os de controle, salvo tab e as quebras, e os
#: não caracteres): o OCR às vezes os traz, e um só tornaria o XHTML ilegível.
_FORA_DO_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff\ud800-\udfff]")


def limpo(texto: str) -> str:
    """O texto sem o que o XML 1.0 proíbe."""
    return _FORA_DO_XML.sub("", texto or "")


def _e(texto: str, aspas: bool = False) -> str:
    """Escapa para o XML, depois de tirar o que ele proíbe."""
    return html.escape(limpo(texto), quote=aspas)

#: Um capítulo passa disto (em caracteres de texto) e o seguinte começa na próxima página.
LIMITE_DO_CAPITULO = 120_000

#: As mensagens que o EPUB escreve, por idioma (o começo da etiqueta BCP 47).
MENSAGENS: Dict[str, Dict[str, str]] = {
    "pt": {"sumario": "Sumário", "paginas": "Páginas", "marcos": "Marcos", "capa": "Capa",
           "inicio": "Início do texto", "pagina": "Página", "diagrama": "Diagrama",
           "nao_lido": "Diagrama não lido; imagem da página impressa",
           "brancas": "brancas jogam", "pretas": "pretas jogam",
           "assumido": "lado a jogar não impresso (assumido)", "nao_revisado": "não revisado",
           "resumo": "Texto reconhecido de um livro de xadrez impresso. Os diagramas lidos "
                     "trazem a posição em FEN como texto alternativo."},
    "en": {"sumario": "Contents", "paginas": "Pages", "marcos": "Landmarks", "capa": "Cover",
           "inicio": "Start of text", "pagina": "Page", "diagrama": "Diagram",
           "nao_lido": "Diagram not read; image of the printed page",
           "brancas": "White to move", "pretas": "Black to move",
           "assumido": "side to move not printed (assumed)", "nao_revisado": "not reviewed",
           "resumo": "Recognized text of a printed chess book. Diagrams that were read carry "
                     "the position in FEN as alternative text."},
    "es": {"sumario": "Índice", "paginas": "Páginas", "marcos": "Puntos de referencia",
           "capa": "Cubierta", "inicio": "Inicio del texto", "pagina": "Página",
           "diagrama": "Diagrama", "nao_lido": "Diagrama no leído; imagen de la página impresa",
           "brancas": "juegan las blancas", "pretas": "juegan las negras",
           "assumido": "turno no impreso (supuesto)", "nao_revisado": "no revisado",
           "resumo": "Texto reconocido de un libro de ajedrez impreso. Los diagramas leídos "
                     "llevan la posición en FEN como texto alternativo."},
    "de": {"sumario": "Inhalt", "paginas": "Seiten", "marcos": "Orientierungspunkte",
           "capa": "Umschlag", "inicio": "Textanfang", "pagina": "Seite", "diagrama": "Diagramm",
           "nao_lido": "Diagramm nicht gelesen; Bild der gedruckten Seite",
           "brancas": "Weiß am Zug", "pretas": "Schwarz am Zug",
           "assumido": "Zugrecht nicht gedruckt (angenommen)", "nao_revisado": "nicht geprüft",
           "resumo": "Erkannter Text eines gedruckten Schachbuchs. Gelesene Diagramme tragen "
                     "die Stellung als FEN im Alternativtext."},
    "fr": {"sumario": "Table des matières", "paginas": "Pages", "marcos": "Repères",
           "capa": "Couverture", "inicio": "Début du texte", "pagina": "Page",
           "diagrama": "Diagramme", "nao_lido": "Diagramme non lu ; image de la page imprimée",
           "brancas": "les Blancs jouent", "pretas": "les Noirs jouent",
           "assumido": "trait non imprimé (supposé)", "nao_revisado": "non vérifié",
           "resumo": "Texte reconnu d'un livre d'échecs imprimé. Les diagrammes lus portent "
                     "la position en FEN comme texte alternatif."},
}

CSS = """\
body { margin: 0 1em; line-height: 1.45; }
h1 { font-size: 1.5em; margin: 1.6em 0 0.8em; break-after: avoid; }
h2 { font-size: 1.2em; margin: 1.2em 0 0.6em; break-after: avoid; }
p { margin: 0 0 0.6em; text-align: justify; hyphens: auto; }
figure.diagrama { margin: 1em auto; text-align: center; break-inside: avoid; }
figure.diagrama img { width: 16em; max-width: 100%; height: auto; }
figure.recorte img { width: 18em; max-width: 100%; height: auto; }
img.capa { display: block; max-width: 100%; max-height: 100vh; margin: 0 auto; }
"""

CSS_DOS_SIMBOLOS = """\
@font-face { font-family: "%(familia)s"; src: url("fontes/%(arquivo)s"); }
.s { font-family: "%(familia)s", serif; }
"""

TIPOS_DE_FONTE = {".ttf": "font/ttf", ".otf": "font/otf", ".woff": "font/woff",
                  ".woff2": "font/woff2"}

_CONTAINER = ('<?xml version="1.0" encoding="UTF-8"?>\n'
              '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
              '<rootfiles><rootfile full-path="OEBPS/content.opf" '
              'media-type="application/oebps-package+xml"/></rootfiles></container>\n')

_NS = {"opf": "http://www.idpf.org/2007/opf", "x": "http://www.w3.org/1999/xhtml",
       "epub": "http://www.idpf.org/2007/ops",
       "c": "urn:oasis:names:tc:opendocument:xmlns:container"}


@dataclass(frozen=True)
class Metadados:
    titulo: str
    idioma: str = "pt-BR"
    autores: Tuple[str, ...] = ()
    editora: str = ""
    #: `AAAA`, `AAAA-MM` ou `AAAA-MM-DD`.
    data: str = ""
    assuntos: Tuple[str, ...] = ()
    direitos: str = ""
    #: Vazio: uma URN estável por título e autores.
    identificador: str = ""
    #: A imagem da capa (PNG, JPEG, GIF ou WebP), ou nada.
    capa: Optional[bytes] = None
    #: A edição impressa (`dc:source`); vazio, o título.
    fonte: str = ""

    def identificador_do_livro(self) -> str:
        if self.identificador:
            return self.identificador
        semente = f"abbychesscraft:{'|'.join(self.autores)}|{self.titulo}"
        return "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, semente))


@dataclass
class Escrito:
    """O que o EPUB levou: para o relatório da exportação (§12.2)."""

    capitulos: int = 0
    paginas: int = 0
    titulos: int = 0
    imagens: int = 0
    #: Figuras que reaproveitaram uma imagem já no pacote (iguais byte a byte).
    reutilizadas: int = 0
    #: Diagramas sem FEN (recortes): sem alternativa textual suficiente.
    sem_fen: int = 0


def mensagens(idioma: str) -> Dict[str, str]:
    return MENSAGENS.get((idioma or "pt").split("-")[0].lower(), MENSAGENS["en"])


# ----------------------------------------------------------------------
# O texto de um parágrafo
# ----------------------------------------------------------------------

def _xhtml_do_texto(paragrafo: Paragrafo, simbolos: str) -> str:
    """O texto com `<strong>`, `<em>` e o `<span class="s">` dos símbolos, sem aninhar
    errado: a marcação abre e fecha por trecho de mesmo estilo."""
    texto = paragrafo.texto
    if not texto:
        return ""
    # Tirar caracteres mudaria os trechos de estilo: os proibidos viram espaço.
    texto = _FORA_DO_XML.sub(" ", texto)
    marcas = [[False, False, c in simbolos] for c in texto]
    for k, trechos in ((0, paragrafo.negrito), (1, paragrafo.italico)):
        for inicio, fim in trechos or ():
            for i in range(max(0, inicio), min(fim, len(texto))):
                marcas[i][k] = True
    saida, i = [], 0
    while i < len(texto):
        j = i
        while j < len(texto) and marcas[j] == marcas[i]:
            j += 1
        pedaco = html.escape(texto[i:j], quote=False)
        negrito, italico, simbolo = marcas[i]
        if simbolo:
            pedaco = f'<span class="s">{pedaco}</span>'
        if italico:
            pedaco = f"<em>{pedaco}</em>"
        if negrito:
            pedaco = f"<strong>{pedaco}</strong>"
        saida.append(pedaco)
        i = j
    return "".join(saida)


#: A procedência do lado a jogar nos idiomas sem a frase do core (`lado_a_jogar.marca`, que
#: é em português): legenda, conferência, número do lance; o resto é assumido.
PROCEDENCIAS = {
    "en": {"legenda": "from the caption", "usuario": "set in review",
           "lances": "from the move numbers", "": "assumed: not printed"},
    "es": {"legenda": "según la leyenda", "usuario": "indicado en la revisión",
           "lances": "según la numeración", "": "supuesto: no impreso"},
    "de": {"legenda": "laut Bildunterschrift", "usuario": "bei der Prüfung angegeben",
           "lances": "laut Zugnummer", "": "angenommen: nicht gedruckt"},
    "fr": {"legenda": "selon la légende", "usuario": "indiqué à la vérification",
           "lances": "selon la numérotation", "": "supposé : non imprimé"},
}


def marca_do_lado(figura: Figura, idioma: str) -> str:
    """"brancas a jogar (assumido: a página não diz)" e as outras: em português, a frase
    do core, a mesma do texto do Documento; nos outros idiomas, a tradução dela."""
    from core import lado_a_jogar

    lado = getattr(figura, "lado_a_jogar", None)
    origem = getattr(figura, "lado_origem", "") or ""
    origem = "" if origem == "convencao" or lado not in ("w", "b") else origem
    lingua = (idioma or "pt").split("-")[0].lower()
    if lingua == "pt":
        return lado_a_jogar.marca(lado if origem else None, origem)
    msg = mensagens(idioma)
    procedencias = PROCEDENCIAS.get(lingua, PROCEDENCIAS["en"])
    vez = msg["pretas"] if origem and lado == "b" else msg["brancas"]
    return f"{vez} ({procedencias.get(origem, procedencias[''])})"


def alternativo(figura: Figura, msg: Dict[str, str], idioma: str) -> str:
    """O texto alternativo do diagrama: o FEN e o lado com a procedência, ou que ele não foi
    lido."""
    if figura.fen:
        texto = f"{msg['diagrama']}: FEN {figura.fen} — {marca_do_lado(figura, idioma)}"
        if getattr(figura, "revisao_pendente", False):
            texto += f"; {msg['nao_revisado']}"
        return texto
    texto = msg["nao_lido"]
    # O motivo do recorte é escrito em português pela exportação: só entra no livro em
    # português, para não pôr outro idioma no texto alternativo.
    if figura.aviso and idioma.lower().startswith("pt"):
        texto += f" ({figura.aviso})"
    return texto


# ----------------------------------------------------------------------
# Os capítulos
# ----------------------------------------------------------------------

@dataclass
class _Capitulo:
    nome: str
    partes: List[str] = field(default_factory=list)
    tamanho: int = 0
    #: (nível, âncora, texto) dos títulos do capítulo, para o sumário.
    titulos: List[Tuple[int, str, str]] = field(default_factory=list)
    #: (número impresso da página no arquivo, âncora) das páginas que começam aqui.
    paginas: List[Tuple[int, str]] = field(default_factory=list)


def _capitulos(paginas: Sequence[PaginaExtraida], imagens: Dict[int, str], simbolos: str,
               msg: Dict[str, str], idioma: str, limite: int) -> List[_Capitulo]:
    capitulos = [_Capitulo("capitulo-001.xhtml")]
    numero_do_titulo = 0

    def novo() -> _Capitulo:
        capitulos.append(_Capitulo(f"capitulo-{len(capitulos) + 1:03d}.xhtml"))
        return capitulos[-1]

    atual = capitulos[0]
    vistas: set = set()

    def ancorar(numero: int) -> None:
        """A âncora da página no capítulo em que o primeiro bloco dela cai."""
        ancora = f"pg{numero}"
        if ancora in vistas:                    # a mesma página duas vezes: uma âncora só
            return
        vistas.add(ancora)
        atual.paginas.append((numero, ancora))
        atual.partes.append(f'<span epub:type="pagebreak" role="doc-pagebreak" '
                            f'id="{ancora}" aria-label="{numero}"></span>')

    for pagina in paginas:
        if atual.tamanho > limite:
            atual = novo()
        numero = pagina.numero + 1
        pendente = True
        for bloco in pagina.blocos:
            if isinstance(bloco, Paragrafo) and bloco.titulo and bloco.nivel == 1 \
                    and bloco.texto.strip() and atual.tamanho > 0:
                atual = novo()
            if pendente and (isinstance(bloco, Figura) or (isinstance(bloco, Paragrafo)
                                                           and bloco.texto.strip())):
                ancorar(numero)
                pendente = False
            if isinstance(bloco, Figura):
                nome = imagens[id(bloco)]
                classe = "diagrama" if bloco.fen else "diagrama recorte"
                alt = _e(alternativo(bloco, msg, idioma), aspas=True)
                atual.partes.append(f'<figure class="{classe}"><img src="../{nome}" '
                                    f'alt="{alt}"/></figure>')
            elif isinstance(bloco, Paragrafo) and bloco.texto.strip():
                corpo = _xhtml_do_texto(bloco, simbolos)
                if bloco.titulo:
                    numero_do_titulo += 1
                    nivel = 1 if bloco.nivel == 1 else 2
                    alvo = f"t{numero_do_titulo}"
                    atual.partes.append(f'<h{nivel} id="{alvo}">{corpo}</h{nivel}>')
                    atual.titulos.append((nivel, alvo, bloco.texto.strip()))
                else:
                    atual.partes.append(f"<p>{corpo}</p>")
                atual.tamanho += len(bloco.texto)
        if pendente:                            # página sem bloco: a âncora fica mesmo assim
            ancorar(numero)
    return [c for c in capitulos if c.partes]


def _xhtml(titulo: str, idioma: str, corpo: str, css: bool = True) -> str:
    lang = html.escape(idioma, quote=True)
    folha = '<link rel="stylesheet" type="text/css" href="../estilo.css"/>' if css else ""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" '
            f'xmlns:epub="http://www.idpf.org/2007/ops" lang="{lang}" xml:lang="{lang}">'
            f"<head><meta charset=\"UTF-8\"/><title>{_e(titulo)}</title>{folha}</head>"
            f"<body>{corpo}</body></html>\n")


def _nav(capitulos: Sequence[_Capitulo], msg: Dict[str, str], idioma: str,
         tem_capa: bool) -> str:
    titulos = [(c.nome, n, a, t) for c in capitulos for n, a, t in c.titulos]
    if titulos:
        lista = lista_do_sumario(titulos)
    else:
        itens = []
        for c in capitulos:
            primeira, ultima = c.paginas[0][0], c.paginas[-1][0]
            faixa = f"{primeira}" if primeira == ultima else f"{primeira}–{ultima}"
            itens.append(f'<li><a href="texto/{c.nome}">{msg["paginas"]} {faixa}</a></li>')
        lista = "".join(itens)
    paginas = "".join(f'<li><a href="texto/{c.nome}#{a}">{n}</a></li>'
                      for c in capitulos for n, a in c.paginas)
    marcos = []
    if tem_capa:
        marcos.append(f'<li><a epub:type="cover" href="texto/capa.xhtml">{msg["capa"]}</a></li>')
    marcos.append(f'<li><a epub:type="toc" href="nav.xhtml#toc">{msg["sumario"]}</a></li>')
    if capitulos:
        marcos.append(f'<li><a epub:type="bodymatter" href="texto/{capitulos[0].nome}">'
                      f'{msg["inicio"]}</a></li>')
    lang = html.escape(idioma, quote=True)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" '
            f'xmlns:epub="http://www.idpf.org/2007/ops" lang="{lang}" xml:lang="{lang}">'
            f'<head><meta charset="UTF-8"/><title>{html.escape(msg["sumario"])}</title></head><body>'
            f'<nav epub:type="toc" id="toc" role="doc-toc"><h1>{html.escape(msg["sumario"])}</h1>'
            f"<ol>{lista}</ol></nav>"
            f'<nav epub:type="page-list" id="paginas" hidden="hidden"><h1>'
            f'{html.escape(msg["paginas"])}</h1><ol>{paginas}</ol></nav>'
            f'<nav epub:type="landmarks" id="marcos" hidden="hidden"><h1>'
            f'{html.escape(msg["marcos"])}</h1><ol>{"".join(marcos)}</ol></nav>'
            "</body></html>\n")


def lista_do_sumario(titulos: Sequence[Tuple[str, int, str, str]]) -> str:
    """Os itens do `<ol>` do sumário: cada `<h1>` com um `<ol>` dos `<h2>` que o seguem; um
    `<h2>` antes de qualquer `<h1>` fica no primeiro nível. `titulos` é (arquivo, nível,
    âncora, texto)."""
    partes: List[str] = []
    filhos: List[str] = []
    aberto = False

    def fechar() -> None:
        if aberto:
            partes.append((f"<ol>{''.join(filhos)}</ol>" if filhos else "") + "</li>")

    for nome, nivel, alvo, texto in titulos:
        link = f'<a href="texto/{nome}#{alvo}">{_e(texto)}</a>'
        if nivel == 1:
            fechar()
            partes.append(f"<li>{link}")
            aberto, filhos = True, []
        elif aberto:
            filhos.append(f"<li>{link}</li>")
        else:
            partes.append(f"<li>{link}</li>")
    fechar()
    return "".join(partes)


# ----------------------------------------------------------------------
# Escrever
# ----------------------------------------------------------------------

def _tipo_da_imagem(dados: bytes) -> Tuple[str, str]:
    if dados[:3] == b"\xff\xd8\xff":
        return "image/jpeg", ".jpg"
    if dados[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif", ".gif"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return "image/png", ".png"


def escrever(paginas: Sequence[PaginaExtraida], caminho: str | Path, metadados: Metadados, *,
             limite_do_capitulo: int = LIMITE_DO_CAPITULO) -> Escrito:
    """Escreve o EPUB em `caminho` (ao lado e troca no fim: a falha não estraga o anterior)."""
    from core.exportar import agora, data_no_zip, fonte_dos_simbolos, instante

    idioma = metadados.idioma or "pt-BR"
    msg = mensagens(idioma)
    escrito = Escrito(paginas=len(paginas))

    arquivos: List[Tuple[str, bytes]] = []
    manifesto: List[str] = []
    por_hash: Dict[str, str] = {}
    imagens: Dict[int, str] = {}
    for pagina in paginas:
        for bloco in pagina.blocos:
            if not isinstance(bloco, Figura):
                continue
            if not bloco.fen:
                escrito.sem_fen += 1
            soma = hashlib.sha256(bloco.png).hexdigest()
            if soma in por_hash:
                escrito.reutilizadas += 1
            else:
                tipo, extensao = _tipo_da_imagem(bloco.png)
                nome = f"imagens/{soma[:20]}{extensao}"
                por_hash[soma] = nome
                arquivos.append((f"OEBPS/{nome}", bloco.png))
                manifesto.append(f'<item id="i{len(por_hash)}" href="{nome}" '
                                 f'media-type="{tipo}"/>')
            imagens[id(bloco)] = por_hash[soma]
    escrito.imagens = len(por_hash)

    css = CSS
    recurso = fonte_dos_simbolos("".join(b.texto for p in paginas for b in p.blocos
                                         if isinstance(b, Paragrafo)))
    simbolos = ""
    if recurso:
        familia, origem, simbolos = recurso
        arquivo = os.path.basename(origem)
        css += CSS_DOS_SIMBOLOS % {"familia": familia.replace('"', ""),
                                   "arquivo": arquivo.replace('"', "%22")}
        with open(origem, "rb") as f:
            arquivos.append((f"OEBPS/fontes/{arquivo}", f.read()))
        tipo = TIPOS_DE_FONTE.get(os.path.splitext(arquivo)[1].lower(), "font/otf")
        manifesto.append(f'<item id="fonte" href="fontes/{_e(arquivo, aspas=True)}" '
                         f'media-type="{tipo}"/>')
    manifesto.append('<item id="css" href="estilo.css" media-type="text/css"/>')
    manifesto.append('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
                     'properties="nav"/>')

    espinha = []
    tem_capa = metadados.capa is not None
    if tem_capa:
        tipo, extensao = _tipo_da_imagem(metadados.capa)
        arquivos.append((f"OEBPS/imagens/capa{extensao}", metadados.capa))
        manifesto.append(f'<item id="capa-imagem" href="imagens/capa{extensao}" '
                         f'media-type="{tipo}" properties="cover-image"/>')
        corpo = (f'<section epub:type="cover"><img class="capa" src="../imagens/capa{extensao}" '
                 f'alt="{html.escape(msg["capa"], quote=True)}"/></section>')
        arquivos.append(("OEBPS/texto/capa.xhtml",
                         _xhtml(msg["capa"], idioma, corpo).encode("utf-8")))
        manifesto.append('<item id="capa" href="texto/capa.xhtml" '
                         'media-type="application/xhtml+xml"/>')
        espinha.append('<itemref idref="capa"/>')

    capitulos = _capitulos(paginas, imagens, simbolos, msg, idioma, limite_do_capitulo)
    if not capitulos:
        raise ValueError("Nada para escrever no EPUB: as páginas não têm texto nem diagrama.")
    escrito.capitulos = len(capitulos)
    escrito.titulos = sum(len(c.titulos) for c in capitulos)
    for n, c in enumerate(capitulos, start=1):
        titulo = c.titulos[0][2] if c.titulos else metadados.titulo
        arquivos.append((f"OEBPS/texto/{c.nome}",
                         _xhtml(titulo, idioma, "".join(c.partes)).encode("utf-8")))
        manifesto.append(f'<item id="c{n}" href="texto/{c.nome}" '
                         'media-type="application/xhtml+xml"/>')
        espinha.append(f'<itemref idref="c{n}"/>')

    momento = instante()
    opf = _opf(metadados, idioma, msg, manifesto, espinha, agora(momento),
               tem_figura=bool(imagens), todos_com_fen=escrito.sem_fen == 0,
               tem_titulos=escrito.titulos > 0, tem_capa=tem_capa)
    nav = _nav(capitulos, msg, idioma, tem_capa)
    _gravar_zip(Path(caminho), data_no_zip(momento),
                [("META-INF/container.xml", _CONTAINER.encode("utf-8")),
                 ("OEBPS/content.opf", opf.encode("utf-8")),
                 ("OEBPS/nav.xhtml", nav.encode("utf-8")),
                 ("OEBPS/estilo.css", css.encode("utf-8"))] + arquivos)
    return escrito


def _opf(m: Metadados, idioma: str, msg: Dict[str, str], manifesto: List[str],
         espinha: List[str], modificado: str, *, tem_figura: bool, todos_com_fen: bool,
         tem_titulos: bool, tem_capa: bool) -> str:
    e = _e
    titulo = limpo(m.titulo).strip() or "Livro"
    dc = [f'<dc:identifier id="pub-id">{e(m.identificador_do_livro())}</dc:identifier>',
          f"<dc:title>{e(titulo)}</dc:title>", f"<dc:language>{e(idioma)}</dc:language>",
          # A edição impressa de onde vêm as páginas da `page-list` (EPUBCheck, OPF-066).
          f"<dc:source>{e(m.fonte or titulo)}</dc:source>"]
    dc += [f"<dc:creator>{e(a)}</dc:creator>" for a in m.autores if a]
    if m.editora:
        dc.append(f"<dc:publisher>{e(m.editora)}</dc:publisher>")
    if m.data and re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", m.data.strip()):
        dc.append(f"<dc:date>{e(m.data.strip())}</dc:date>")
    elif m.data:
        log.warning("A data %r não é AAAA, AAAA-MM nem AAAA-MM-DD: fica fora do EPUB.", m.data)
    dc += [f"<dc:subject>{e(s)}</dc:subject>" for s in m.assuntos if s]
    if m.direitos:
        dc.append(f"<dc:rights>{e(m.direitos)}</dc:rights>")
    # A acessibilidade do que foi escrito, e só dele (EPUB Accessibility 1.1).
    a11y = ['<meta property="schema:accessMode">textual</meta>']
    if tem_figura or tem_capa:
        a11y.append('<meta property="schema:accessMode">visual</meta>')
    a11y.append('<meta property="schema:accessModeSufficient">textual</meta>'
                if not tem_figura or todos_com_fen else
                '<meta property="schema:accessModeSufficient">textual,visual</meta>')
    if tem_figura and todos_com_fen:
        a11y.append('<meta property="schema:accessibilityFeature">alternativeText</meta>')
    if tem_titulos:
        a11y.append('<meta property="schema:accessibilityFeature">structuralNavigation</meta>')
    a11y += ['<meta property="schema:accessibilityFeature">pageNavigation</meta>',
             '<meta property="schema:accessibilityFeature">readingOrder</meta>',
             '<meta property="schema:accessibilityHazard">unknown</meta>',
             f'<meta property="schema:accessibilitySummary">{e(msg["resumo"])}</meta>']
    capa = '<meta name="cover" content="capa-imagem"/>' if tem_capa else ""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
            'unique-identifier="pub-id" prefix="schema: http://schema.org/">\n'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
            + "\n".join(dc) + "\n"
            f'<meta property="dcterms:modified">{modificado}</meta>\n'
            + "\n".join(a11y) + "\n" + capa
            + "</metadata>\n<manifest>\n" + "\n".join(manifesto) + "\n</manifest>\n"
            f'<spine>{"".join(espinha)}</spine>\n</package>\n')


def _gravar_zip(caminho: Path, data_hora, entradas: List[Tuple[str, bytes]]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(prefix=".epub-", suffix=".tmp", dir=caminho.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporario, "w", zipfile.ZIP_DEFLATED) as z:
            _entrada(z, "mimetype", b"application/epub+zip", data_hora, zipfile.ZIP_STORED)
            for nome, dados in entradas:
                _entrada(z, nome, dados, data_hora, zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(temporario) as z:
            if z.testzip() is not None:
                raise zipfile.BadZipFile("EPUB temporário com entrada inválida")
        os.chmod(temporario, 0o644)             # o mkstemp nasce 0600
        os.replace(temporario, caminho)
    except BaseException:
        Path(temporario).unlink(missing_ok=True)
        raise


def _entrada(z: zipfile.ZipFile, nome: str, dados: bytes, data_hora, compressao: int) -> None:
    info = zipfile.ZipInfo(nome, date_time=data_hora)
    info.compress_type = compressao
    info.create_system = 0                      # o mesmo no Windows e no Linux
    info.external_attr = 0o644 << 16
    z.writestr(info, dados)


# ----------------------------------------------------------------------
# Conferir
# ----------------------------------------------------------------------

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
        for ref in refs:
            if ref.get("idref") not in itens:
                problemas.append(f"o itemref {ref.get('idref')} não está no manifesto")
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
