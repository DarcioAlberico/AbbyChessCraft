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
- **Links internos**: "página 23", "Diagrama 6" (pelo número da legenda) e "capítulo 3"
  (pelo número do título) viram link quando o alvo está no livro (`links_internos`).
- **Links de análise**, se pedidos: na legenda de cada diagrama lido, o link que abre a
  posição no Lichess ou no Chess.com (`links_de_analise`).
- **Os mesmos bytes**: com o mesmo `SOURCE_DATE_EPOCH`, o mesmo arquivo (CA-12.6): a data
  do pacote e das entradas do zip vem de `core.exportar.instante`, e nada mais varia.

Do core só se usam funções públicas: a fonte dos símbolos (`fonte_dos_simbolos`) e o
instante reprodutível (`instante`, `agora`, `data_no_zip`). A conferência do arquivo
escrito e os validadores externos estão em `abbychess.validacao_do_epub`.
"""

from __future__ import annotations

import hashlib
import html
import io
import logging
import os
import re
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from core.pagina import Figura, PaginaExtraida, Paragrafo

from abbychess import gravacao as gv
from abbychess import links_de_analise
from abbychess import marcacao
from abbychess.marcacao import trechos_marcados
from abbychess.validacao_do_epub import conferir
from abbychess.links_internos import Numerados, numerados, referencias_internas

log = logging.getLogger(__name__)

#: Os caracteres que o XML 1.0 não aceita (os de controle, salvo tab e as quebras, e os
#: não caracteres): o OCR às vezes os traz, e um só tornaria o XHTML ilegível.
_FORA_DO_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff\ud800-\udfff]")


def limpo(texto: str) -> str:
    """O texto sem o que o XML 1.0 proíbe."""
    return _FORA_DO_XML.sub("", texto or "")


def sem_proibidos(texto: str) -> str:
    """O texto com os caracteres que o XML proíbe trocados por espaço: o comprimento fica,
    e os trechos de estilo do parágrafo continuam valendo."""
    return _FORA_DO_XML.sub(" ", texto or "")


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
    #: As referências a página impressa que viraram link.
    links: int = 0
    #: Os diagramas com link de análise (`links_de_analise`).
    analises: int = 0
    #: Os bytes que o PNG otimizado sem perda tirou das imagens (`png_otimizado`).
    poupados: int = 0


def mensagens(idioma: str) -> Dict[str, str]:
    return MENSAGENS.get((idioma or "pt").split("-")[0].lower(), MENSAGENS["en"])


# ----------------------------------------------------------------------
# O texto de um parágrafo
# ----------------------------------------------------------------------

def xhtml_do_texto(paragrafo: Paragrafo, simbolos: str,
                   links: Sequence[Tuple[int, int, str]] = (), *,
                   quebras: bool = False, realce: bool = False) -> str:
    """O texto com `<strong>`, `<em>`, o `<span class="s">` dos símbolos e os `<a>` de
    `links` (`(início, fim, href)`), sem aninhar errado: a marcação abre e fecha por trecho
    de mesmo estilo, e o link fica por fora. Com `quebras`, a quebra de linha do texto (as
    linhas impressas mantidas, `Opcoes.manter_quebras`) vira `<br/>`; sem, é espaço. `realce`
    põe os trechos duvidosos do parágrafo (`exportar.ParagrafoExportado`) em `<mark>`: é a
    prévia do realce do DOCX."""
    texto = paragrafo.texto
    if not texto:
        return ""
    # Tirar caracteres mudaria os trechos de estilo: os proibidos viram espaço. As aspas
    # retas do OCR viram as curvas do impresso (PD-07), também uma por uma.
    texto = aspas_curvas(sem_proibidos(texto))
    duvidosos = getattr(paragrafo, "duvidosos", ()) if realce else ()
    saida = []
    for cru, (negrito, italico, simbolo, link, duvidoso) in trechos_marcados(
            texto, simbolos, paragrafo.negrito, paragrafo.italico, duvidosos, links):
        pedaco = html.escape(cru, quote=False)
        if quebras:
            pedaco = pedaco.replace("\n", "<br/>")
        if duvidoso:
            pedaco = f"<mark>{pedaco}</mark>"
        if simbolo:
            pedaco = f'<span class="s">{pedaco}</span>'
        if italico:
            pedaco = f"<em>{pedaco}</em>"
        if negrito:
            pedaco = f"<strong>{pedaco}</strong>"
        if link >= 0:
            pedaco = f'<a href="{html.escape(links[link][2], quote=True)}">{pedaco}</a>'
        saida.append(pedaco)
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
    #: As referências (a página, diagrama ou capítulo) que viraram link neste capítulo.
    links: int = 0
    #: Os diagramas com link de análise neste capítulo.
    analises: int = 0
    #: (número impresso, âncora) dos diagramas e dos capítulos numerados que caem aqui.
    diagramas: List[Tuple[int, str]] = field(default_factory=list)
    numerados: List[Tuple[int, str]] = field(default_factory=list)


def _capitulos(paginas: Sequence[PaginaExtraida], imagens: Dict[int, str], simbolos: str,
               msg: Dict[str, str], idioma: str, limite: int,
               rotulos: Optional[Dict[int, int]] = None,
               alvos: Optional[Dict[str, Dict[int, str]]] = None,
               numeros: Optional[Numerados] = None,
               quebras: bool = False, analise: str = "nenhum") -> List[_Capitulo]:
    """Os capítulos. `rotulos` dá o número impresso de cada página (índice -> número; sem
    ele, a posição no PDF); `alvos`, o href de cada página impressa, diagrama e capítulo
    numerado (`"paginas"`, `"diagramas"`, `"capitulos"`: número -> href), para as
    referências do texto virarem link; `numeros`, o que o livro numera (`numerados`);
    `analise`, o site do link de análise de cada diagrama lido (`links_de_analise`)."""
    alvos = alvos or {}
    escrita = _EscritaDosCapitulos(
        imagens, simbolos, msg, idioma, rotulos or {}, numeros or Numerados(),
        por_pagina=alvos.get("paginas", {}), por_diagrama=alvos.get("diagramas", {}),
        por_capitulo=alvos.get("capitulos", {}), quebras=quebras, analise=analise)
    for pagina in paginas:
        if escrita.atual.tamanho > limite:
            escrita.novo()
        escrita.pagina(pagina)
    return [c for c in escrita.capitulos if c.partes]


def _abre_capitulo(bloco) -> bool:
    """O título de capítulo (`<h1>`) com texto."""
    return isinstance(bloco, Paragrafo) and bloco.titulo and bloco.nivel == 1 \
        and bool(bloco.texto.strip())


def _tem_conteudo(bloco) -> bool:
    """A figura, ou o parágrafo com texto: o bloco que vai ao capítulo."""
    return isinstance(bloco, Figura) or (isinstance(bloco, Paragrafo)
                                         and bool(bloco.texto.strip()))


@dataclass
class _EscritaDosCapitulos:
    """O que `_capitulos` sabe enquanto passa pelos blocos: o que entra no texto (as imagens,
    os símbolos, as mensagens, os alvos dos links) e o que já escreveu (os capítulos, as
    âncoras de página postas e quantos títulos vieram)."""

    imagens: Dict[int, str]
    simbolos: str
    msg: Dict[str, str]
    idioma: str
    rotulos: Dict[int, int]
    numeros: Numerados
    por_pagina: Dict[int, str]
    por_diagrama: Dict[int, str]
    por_capitulo: Dict[int, str]
    quebras: bool = False
    analise: str = "nenhum"
    capitulos: List[_Capitulo] = field(
        default_factory=lambda: [_Capitulo("capitulo-001.xhtml")])
    vistas: set = field(default_factory=set)
    numero_do_titulo: int = 0

    @property
    def atual(self) -> _Capitulo:
        return self.capitulos[-1]

    def novo(self) -> None:
        self.capitulos.append(_Capitulo(f"capitulo-{len(self.capitulos) + 1:03d}.xhtml"))

    def pagina(self, pagina: PaginaExtraida) -> None:
        numero = pagina.numero + 1
        pendente = True
        for bloco in pagina.blocos:
            pendente = self.bloco(bloco, numero, pendente)
        if pendente:                            # página sem bloco: a âncora fica mesmo assim
            self.ancorar(numero)

    def bloco(self, bloco, numero: int, pendente: bool) -> bool:
        """O bloco no capítulo (num novo, se ele abre um capítulo), com a âncora da página
        antes do primeiro que tem conteúdo; devolve se ela ainda está pendente."""
        if _abre_capitulo(bloco) and self.atual.tamanho > 0:
            self.novo()
        if pendente and _tem_conteudo(bloco):
            self.ancorar(numero)
            pendente = False
        if isinstance(bloco, Figura):
            self.figura(bloco)
        elif isinstance(bloco, Paragrafo) and bloco.texto.strip():
            self.paragrafo(bloco)
        return pendente

    def ancorar(self, numero: int) -> None:
        """A âncora da página no capítulo em que o primeiro bloco dela cai; o rótulo é o
        número impresso, quando se sabe."""
        ancora = f"pg{numero}"
        if ancora in self.vistas:               # a mesma página duas vezes: uma âncora só
            return
        self.vistas.add(ancora)
        # Com a paginação conhecida, a página sem número impresso (as de rosto) não leva o
        # número da posição, que colidiria com um impresso: vai entre colchetes.
        rotulo = self.rotulos.get(numero - 1, f"[{numero}]" if self.rotulos else numero)
        self.atual.paginas.append((rotulo, ancora))
        self.atual.partes.append(f'<span epub:type="pagebreak" role="doc-pagebreak" '
                                 f'id="{ancora}" aria-label="{rotulo}"></span>')

    def figura(self, bloco: Figura) -> None:
        nome = self.imagens[id(bloco)]
        classe = "diagrama" if bloco.fen else "diagrama recorte"
        alt = _e(alternativo(bloco, self.msg, self.idioma), aspas=True)
        legenda = self.legenda(bloco)
        ident = ""
        if id(bloco) in self.numeros.figuras:
            ancora_do_diagrama = f"dg{self.numeros.figuras[id(bloco)]}"
            self.atual.diagramas.append((self.numeros.figuras[id(bloco)], ancora_do_diagrama))
            ident = f' id="{ancora_do_diagrama}"'
        self.atual.partes.append(f'<figure class="{classe}"{ident}><img src="../{nome}" '
                                 f'alt="{alt}"/>{legenda}</figure>')

    def legenda(self, bloco: Figura) -> str:
        """A ressalva do diagrama que ninguém conferiu fica à vista (PD-21), além do alt. E o
        link de análise, quando pedido, embaixo da ressalva."""
        na_legenda = []
        ressalva = marcacao.ressalva_do_diagrama(bloco, self.idioma)
        if ressalva:
            na_legenda.append(_e(ressalva))
        endereco = links_de_analise.link_da_figura(bloco, self.analise)
        if endereco:
            na_legenda.append(f'<a class="analise" href="{_e(endereco, aspas=True)}">'
                              f'{_e(links_de_analise.rotulo(self.analise, self.idioma))}</a>')
            self.atual.analises += 1
        return f"<figcaption>{'<br/>'.join(na_legenda)}</figcaption>" if na_legenda else ""

    def paragrafo(self, bloco: Paragrafo) -> None:
        links = ([] if bloco.titulo else referencias_internas(
            bloco.texto, self.idioma, self.por_pagina,
            {} if id(bloco) in self.numeros.legendas else self.por_diagrama, self.por_capitulo))
        self.atual.links += len(links)
        corpo = xhtml_do_texto(bloco, self.simbolos, links, quebras=self.quebras)
        if bloco.titulo:
            self.titulo(bloco, corpo)
        else:
            self.atual.partes.append(f"<p>{corpo}</p>")
        self.atual.tamanho += len(bloco.texto)

    def titulo(self, bloco: Paragrafo, corpo: str) -> None:
        self.numero_do_titulo += 1
        nivel = 1 if bloco.nivel == 1 else 2
        alvo = f"t{self.numero_do_titulo}"
        self.atual.partes.append(f'<h{nivel} id="{alvo}">{corpo}</h{nivel}>')
        self.atual.titulos.append((nivel, alvo, aspas_curvas(bloco.texto.strip())))
        if id(bloco) in self.numeros.capitulos:
            self.atual.numerados.append((self.numeros.capitulos[id(bloco)], alvo))


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

def aspas_curvas(texto: str) -> str:
    """As aspas retas trocadas pelas curvas, uma por uma (`core.exportar.aspas_curvas`,
    PD-07): o impresso tem `“`, `”` e `’`, e o OCR devolve as do teclado. Só nos arquivos
    formatados (EPUB, DOCX e a prévia); o TXT e o PGN saem como lidos."""
    from core.exportar import aspas_curvas as do_core

    return do_core(texto)


def png_otimizado(dados: bytes) -> bytes:
    """O mesmo PNG, menor quando dá, sem perder um pixel: em tons de cinza quando a imagem
    colorida não tem cor, em paleta quando tem até 256 cores, e com a compressão máxima.
    Cada candidato gravado é lido de volta e conferido pixel a pixel contra o original, e só
    fica o menor; o que não é PNG, não abre ou traz gestão de cor (perfil ICC, gama,
    cromaticidade, sRGB: o Pillow não a regrava inteira) volta como veio. Os mesmos bytes
    de entrada dão os mesmos de saída (CA-12.6)."""
    from PIL import Image

    if not dados.startswith(b"\x89PNG"):
        return dados
    try:
        with Image.open(io.BytesIO(dados)) as aberta:
            aberta.load()
            original = aberta.copy()
            info = {k: v for k, v in aberta.info.items() if k == "dpi"}
            de_cor = {"icc_profile", "gamma", "chromaticity", "srgb"} & set(aberta.info)
    except Exception:                          # PNG estragado: o escritor decide
        log.warning("o PNG não foi otimizado; vai como estava", exc_info=True)
        return dados
    if de_cor or original.mode not in ("1", "L", "LA", "P", "RGB", "RGBA"):
        return dados
    referencia = original.convert("RGBA").tobytes()
    candidatos = [original]
    if original.mode in ("RGB", "RGBA"):
        sem_alfa = original.mode == "RGB" or original.getextrema()[3] == (255, 255)
        candidatos.append(original.convert("L" if sem_alfa else "LA"))
        if original.getcolors(256) is not None:
            candidatos.append(original.convert("RGBA").quantize(colors=256, method=Image.Quantize.FASTOCTREE))
    melhor = dados
    for candidato in candidatos:
        saida = io.BytesIO()
        candidato.save(saida, format="PNG", optimize=True, **info)
        if len(saida.getvalue()) >= len(melhor):
            continue
        with Image.open(io.BytesIO(saida.getvalue())) as volta:
            if volta.convert("RGBA").tobytes() != referencia:
                continue                        # perderia algo: fica de fora
        melhor = saida.getvalue()
    return melhor


def tipo_da_imagem(dados: bytes) -> Tuple[str, str]:
    if dados[:3] == b"\xff\xd8\xff":
        return "image/jpeg", ".jpg"
    if dados[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif", ".gif"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return "image/png", ".png"


def escrever(paginas: Sequence[PaginaExtraida], caminho: str | Path, metadados: Metadados, *,
             limite_do_capitulo: int = LIMITE_DO_CAPITULO,
             numeros: Optional[Dict[int, int]] = None, quebras: bool = False,
             analise: str = "nenhum") -> Escrito:
    """Escreve o EPUB em `caminho` (ao lado e troca no fim: a falha não estraga o anterior).

    `numeros` é o número impresso de cada página (índice -> número): vira o rótulo da
    página na `page-list` e o alvo das referências do texto ("ver a página 23"). `quebras`
    escreve as quebras de linha dos parágrafos como `<br/>` (`Opcoes.manter_quebras`).
    `analise` põe na legenda de cada diagrama lido o link que abre a posição no Lichess ou
    no Chess.com (`Opcoes.links_de_analise`); `nenhum`, nenhum link."""
    links_de_analise.validar(analise)
    from core.exportar import agora, data_no_zip, instante

    idioma = metadados.idioma or "pt-BR"
    msg = mensagens(idioma)
    escrito = Escrito(paginas=len(paginas))
    pacote = _Pacote()
    imagens = _imagens(paginas, escrito, pacote)
    css, simbolos = _css_e_simbolos(paginas, pacote)
    pacote.manifesto.append('<item id="css" href="estilo.css" media-type="text/css"/>')
    pacote.manifesto.append('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
                            'properties="nav"/>')
    tem_capa = metadados.capa is not None
    if tem_capa:
        _capa(metadados.capa, msg, idioma, pacote)

    # Duas passadas: a primeira diz em que capítulo cai cada página, diagrama e capítulo
    # numerado, e a segunda escreve as referências já com o arquivo certo.
    numeros = numeros or {}
    contados = numerados(paginas)
    capitulos = _capitulos(paginas, imagens, simbolos, msg, idioma, limite_do_capitulo,
                           numeros, numeros=contados, quebras=quebras, analise=analise)
    alvos = _alvos(capitulos, numeros)
    if any(alvos.values()):
        capitulos = _capitulos(paginas, imagens, simbolos, msg, idioma, limite_do_capitulo,
                               numeros, alvos, contados, quebras, analise)
    if not capitulos:
        raise ValueError("Nada para escrever no EPUB: as páginas não têm texto nem diagrama.")
    _contar_os_capitulos(escrito, capitulos)
    _textos_dos_capitulos(capitulos, metadados.titulo, idioma, pacote)
    # O marco do sumário aponta o nav: fora da espinha, é RSC-011 no EPUBCheck. Fora da
    # leitura corrida (`linear="no"`), o leitor não o mostra entre a capa e o texto.
    pacote.espinha.append('<itemref idref="nav" linear="no"/>')

    momento = instante()
    opf = _opf(metadados, idioma, msg, pacote.manifesto, pacote.espinha, agora(momento),
               tem_figura=bool(imagens), todos_com_fen=escrito.sem_fen == 0,
               tem_titulos=escrito.titulos > 0, tem_capa=tem_capa)
    nav = _nav(capitulos, msg, idioma, tem_capa)
    _gravar_zip(Path(caminho), data_no_zip(momento),
                [("META-INF/container.xml", _CONTAINER.encode("utf-8")),
                 ("OEBPS/content.opf", opf.encode("utf-8")),
                 ("OEBPS/nav.xhtml", nav.encode("utf-8")),
                 ("OEBPS/estilo.css", css.encode("utf-8"))] + pacote.arquivos)
    return escrito


@dataclass
class _Pacote:
    """O que o EPUB leva além do OPF, do nav e do CSS (`arquivos`: entrada do zip, bytes),
    e as linhas do manifesto e da espinha, na ordem em que entram."""

    arquivos: List[Tuple[str, bytes]] = field(default_factory=list)
    manifesto: List[str] = field(default_factory=list)
    espinha: List[str] = field(default_factory=list)


def _imagens(paginas: Sequence[PaginaExtraida], escrito: Escrito, pacote: _Pacote
             ) -> Dict[int, str]:
    """A entrada do zip da imagem de cada figura (id da `Figura` -> nome), com o PNG
    otimizado; as iguais byte a byte são um recurso só."""
    por_hash: Dict[str, str] = {}
    imagens: Dict[int, str] = {}
    for pagina in paginas:
        for bloco in pagina.blocos:
            if not isinstance(bloco, Figura):
                continue
            if not bloco.fen:
                escrito.sem_fen += 1
            png = png_otimizado(bloco.png)
            soma = hashlib.sha256(png).hexdigest()
            if soma in por_hash:
                escrito.reutilizadas += 1
            else:
                tipo, extensao = tipo_da_imagem(png)
                nome = f"imagens/{soma[:20]}{extensao}"
                por_hash[soma] = nome
                pacote.arquivos.append((f"OEBPS/{nome}", png))
                escrito.poupados += len(bloco.png) - len(png)
                pacote.manifesto.append(f'<item id="i{len(por_hash)}" href="{nome}" '
                                        f'media-type="{tipo}"/>')
            imagens[id(bloco)] = por_hash[soma]
    escrito.imagens = len(por_hash)
    return imagens


def _css_e_simbolos(paginas: Sequence[PaginaExtraida], pacote: _Pacote) -> Tuple[str, str]:
    """(o CSS, os símbolos que a fonte cobre): com uma fonte de símbolos para o texto do
    livro, o CSS a declara e ela vai no pacote."""
    from core.exportar import fonte_dos_simbolos

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
            pacote.arquivos.append((f"OEBPS/fontes/{arquivo}", f.read()))
        tipo = TIPOS_DE_FONTE.get(os.path.splitext(arquivo)[1].lower(), "font/otf")
        pacote.manifesto.append(f'<item id="fonte" href="fontes/{_e(arquivo, aspas=True)}" '
                                f'media-type="{tipo}"/>')
    return css, simbolos


def _capa(capa: bytes, msg: Dict[str, str], idioma: str, pacote: _Pacote) -> None:
    """A imagem da capa e a página dela, primeira na espinha."""
    tipo, extensao = tipo_da_imagem(capa)
    pacote.arquivos.append((f"OEBPS/imagens/capa{extensao}", capa))
    pacote.manifesto.append(f'<item id="capa-imagem" href="imagens/capa{extensao}" '
                            f'media-type="{tipo}" properties="cover-image"/>')
    corpo = (f'<section epub:type="cover"><img class="capa" src="../imagens/capa{extensao}" '
             f'alt="{html.escape(msg["capa"], quote=True)}"/></section>')
    pacote.arquivos.append(("OEBPS/texto/capa.xhtml",
                            _xhtml(msg["capa"], idioma, corpo).encode("utf-8")))
    pacote.manifesto.append('<item id="capa" href="texto/capa.xhtml" '
                            'media-type="application/xhtml+xml"/>')
    pacote.espinha.append('<itemref idref="capa"/>')


def _alvos(capitulos: Sequence[_Capitulo], numeros: Dict[int, int]) -> Dict[str, Dict[int, str]]:
    """O href de cada página impressa (só com a paginação conhecida), diagrama e capítulo
    numerado, pelo capítulo em que caíram."""
    return {
        "paginas": ({rotulo: f"{c.nome}#{ancora}" for c in capitulos
                     for rotulo, ancora in c.paginas} if numeros else {}),
        "diagramas": {n: f"{c.nome}#{ancora}" for c in capitulos for n, ancora in c.diagramas},
        "capitulos": {n: f"{c.nome}#{ancora}" for c in capitulos for n, ancora in c.numerados},
    }


def _contar_os_capitulos(escrito: Escrito, capitulos: Sequence[_Capitulo]) -> None:
    escrito.links = sum(c.links for c in capitulos)
    escrito.analises = sum(c.analises for c in capitulos)
    escrito.capitulos = len(capitulos)
    escrito.titulos = sum(len(c.titulos) for c in capitulos)


def _textos_dos_capitulos(capitulos: Sequence[_Capitulo], titulo_do_livro: str, idioma: str,
                          pacote: _Pacote) -> None:
    """O XHTML de cada capítulo, com o título dele (ou o do livro), no manifesto e na
    espinha."""
    for n, c in enumerate(capitulos, start=1):
        titulo = c.titulos[0][2] if c.titulos else titulo_do_livro
        pacote.arquivos.append((f"OEBPS/texto/{c.nome}",
                                _xhtml(titulo, idioma, "".join(c.partes)).encode("utf-8")))
        pacote.manifesto.append(f'<item id="c{n}" href="texto/{c.nome}" '
                                'media-type="application/xhtml+xml"/>')
        pacote.espinha.append(f'<itemref idref="c{n}"/>')


def _opf(m: Metadados, idioma: str, msg: Dict[str, str], manifesto: List[str],
         espinha: List[str], modificado: str, *, tem_figura: bool, todos_com_fen: bool,
         tem_titulos: bool, tem_capa: bool) -> str:
    e = _e
    titulo = limpo(m.titulo).strip() or "Livro"
    dc = [f'<dc:identifier id="pub-id">{e(m.identificador_do_livro())}</dc:identifier>',
          f"<dc:title>{e(titulo)}</dc:title>", f"<dc:language>{e(idioma)}</dc:language>",
          # A edição impressa de onde vêm as páginas da `page-list` (EPUBCheck, OPF-066),
          # refinada como fonte da paginação (`source-of`), que é o que o Ace pede
          # (epub-pagesource). O `a11y:pageBreakSource` também satisfaz o Ace, mas o
          # EPUBCheck 5.4 o recusa (OPF-027): fica de fora.
          f'<dc:source id="pub-fonte">{e(m.fonte or titulo)}</dc:source>',
          '<meta refines="#pub-fonte" property="source-of">pagination</meta>']
    dc += _dc_do_livro(m)
    a11y = _acessibilidade(msg, tem_figura=tem_figura, todos_com_fen=todos_com_fen,
                           tem_titulos=tem_titulos, tem_capa=tem_capa)
    capa = '<meta name="cover" content="capa-imagem"/>' if tem_capa else ""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            # O idioma também no `<package>` (o Ace: epub-lang), além do `dc:language`.
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
            f'unique-identifier="pub-id" xml:lang="{e(idioma, aspas=True)}" '
            'prefix="schema: http://schema.org/">\n'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
            + "\n".join(dc) + "\n"
            f'<meta property="dcterms:modified">{modificado}</meta>\n'
            + "\n".join(a11y) + "\n" + capa
            + "</metadata>\n<manifest>\n" + "\n".join(manifesto) + "\n</manifest>\n"
            f'<spine>{"".join(espinha)}</spine>\n</package>\n')


def _dc_do_livro(m: Metadados) -> List[str]:
    """Os autores, a editora, a data, os assuntos e os direitos que os metadados trazem."""
    e = _e
    dc = [f"<dc:creator>{e(a)}</dc:creator>" for a in m.autores if a]
    if m.editora:
        dc.append(f"<dc:publisher>{e(m.editora)}</dc:publisher>")
    dc += _data(m)
    dc += [f"<dc:subject>{e(s)}</dc:subject>" for s in m.assuntos if s]
    if m.direitos:
        dc.append(f"<dc:rights>{e(m.direitos)}</dc:rights>")
    return dc


def _data(m: Metadados) -> List[str]:
    """O `dc:date`, se a data é AAAA, AAAA-MM ou AAAA-MM-DD; fora disso, fica de fora."""
    if m.data and re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", m.data.strip()):
        return [f"<dc:date>{_e(m.data.strip())}</dc:date>"]
    if m.data:
        log.warning("A data %r não é AAAA, AAAA-MM nem AAAA-MM-DD: fica fora do EPUB.", m.data)
    return []


def _acessibilidade(msg: Dict[str, str], *, tem_figura: bool, todos_com_fen: bool,
                    tem_titulos: bool, tem_capa: bool) -> List[str]:
    """A acessibilidade do que foi escrito, e só dele (EPUB Accessibility 1.1)."""
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
             f'<meta property="schema:accessibilitySummary">{_e(msg["resumo"])}</meta>']
    return a11y


def _gravar_zip(caminho: Path, data_hora, entradas: List[Tuple[str, bytes]]) -> None:
    """O EPUB ao lado, conferido (`conferir`) antes de trocar com o anterior
    (SPEC-qualidade Q-E3): o que não passa não é publicado, como no DOCX."""
    def escrever(temporario: Path) -> None:
        with zipfile.ZipFile(temporario, "w", zipfile.ZIP_DEFLATED) as z:
            _entrada(z, "mimetype", b"application/epub+zip", data_hora, zipfile.ZIP_STORED)
            for nome, dados in entradas:
                _entrada(z, nome, dados, data_hora, zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(temporario) as z:
            if z.testzip() is not None:
                raise zipfile.BadZipFile("EPUB temporário com entrada inválida")

    def recusar_o_estragado(temporario: Path) -> None:
        problemas = conferir(temporario)
        if problemas:
            raise ValueError("O EPUB não passou na conferência: " + "; ".join(problemas))

    gv.gravar_por(caminho, escrever, recusar_o_estragado)


def _entrada(z: zipfile.ZipFile, nome: str, dados: bytes, data_hora, compressao: int) -> None:
    info = zipfile.ZipInfo(nome, date_time=data_hora)
    info.compress_type = compressao
    info.create_system = 0                      # o mesmo no Windows e no Linux
    info.external_attr = 0o644 << 16
    z.writestr(info, dados)


