"""O PDF pesquisável (§12.1): a página original como está, com a camada de texto invisível tirada
dos boxes do projeto (o que o livro ensinou e o que o usuário corrigiu), o FEN de cada diagrama
confiável sobre o tabuleiro, os marcadores pelos títulos e os rótulos pelos números impressos.
As peças vêm de `core.searchable_pdf`. À parte de `exportar.py` (SPEC-qualidade Q-E6,
CA-Q-A1)."""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from core.box_model import BoxEntry

from abbychess import gravacao as gv
from abbychess import pagina as pg
from abbychess import sequencia as sq
from abbychess.diagramas import DiagramaLido
from abbychess.margens import _funcoes_dos_candidatos, numeros_impressos
from abbychess.montagem import DPI_DA_LEITURA, Estrutura, palavras, titulos_das_paginas
from abbychess.pedido import NadaParaExportar, Progresso
from abbychess.projeto import ProjetoDeLivro

log = logging.getLogger(__name__)


#: Quando ler a página da camada de texto do PDF: "auto" (quando a régua do
#: `core.pdf_nativo` aceita a página) ou "nunca" (sempre dos boxes do projeto).
CAMADA = ("auto", "nunca")


@dataclass
class ResumoDoPdf:
    paginas: int = 0
    caracteres: int = 0
    #: Páginas em que a camada invisível que o PDF já trazia foi trocada pela nossa.
    camadas_trocadas: int = 0
    #: Páginas com texto visível próprio (PDF nascido digital): ficam sem a nossa
    #: camada, que duplicaria a busca.
    com_texto_proprio: List[int] = field(default_factory=list)
    sem_glifo: int = 0
    #: Diagramas com o FEN na camada de texto.
    fens: int = 0
    #: Os marcadores (o sumário do PDF) pelos títulos do Documento, e os que o PDF original
    #: já tinha e ficaram (o sumário do editor vale mais que o nosso).
    marcadores: int = 0
    marcadores_do_original: int = 0
    #: As páginas ganharam o número impresso como rótulo (o "23" que o leitor mostra).
    rotulos: bool = False


def _texto_visivel(page) -> bool:
    """A página tem texto que aparece, e não só uma camada de OCR invisível."""
    try:
        return any(traco.get("type") != 3 for traco in page.get_texttrace())
    except Exception as erro:  # PDF estranho: na dúvida, é texto de verdade
        log.debug("o rastro do texto não saiu (%s)", erro, exc_info=True)
        return bool(page.get_text("text").strip())


def _tirar_camada_invisivel(page) -> bool:
    """Apaga a camada de OCR que o PDF já trazia, sem tocar em imagem nem traço.

    Os PDFs digitalizados costumam vir com o OCR de fábrica, e no Darcy Lima é
    essa camada que lê "hb7" onde está impresso "♗b7". Somar a nossa a ela
    faria a busca achar as duas leituras.
    """
    import fitz

    if not page.get_text("text").strip():
        return False
    page.add_redact_annot(page.rect)
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                          graphics=fitz.PDF_REDACT_LINE_ART_NONE)
    return True


def _escrever_camada(page, boxes: Sequence[BoxEntry], escala: float, fontes, resumo) -> None:
    """A leitura do projeto como texto invisível, uma palavra por vez.

    **Por palavra, e não por caractere** como em `core.searchable_pdf`: com um
    caractere em cada posição, o vão entre os boxes de uma palavra vira espaço
    na extração, e no Darcy Lima a busca por "abertura" não achava nada ("abertu
    ra"). A palavra entra inteira no retângulo dos seus boxes, com o corpo que a
    faz ocupar essa largura. A palavra girada, ou com caractere que a fonte
    principal não desenha, cai para o caminho de lá, caractere a caractere.
    """
    from core.searchable_pdf import FONTE_OCR, FONTE_SIMBOLOS

    fonte, caminho, fonte_sym, caminho_sym = fontes
    page.insert_font(fontname=FONTE_OCR, fontfile=caminho)
    if fonte_sym is not None:
        page.insert_font(fontname=FONTE_SIMBOLOS, fontfile=caminho_sym)
    lidos = [b for b in boxes if b.char]
    for linha in palavras(lidos):
        for texto, indices in linha:
            grupo = [lidos[i] for i in indices]
            if (texto and all(not (b.angulo or 0) % 360 for b in grupo)
                    and all(fonte.has_glyph(ord(c)) for c in texto)):
                caixa = BoxEntry(texto, min(b.x1 for b in grupo), min(b.y1 for b in grupo),
                                 max(b.x2 for b in grupo), max(b.y2 for b in grupo))
                _escrever(page, caixa, texto, FONTE_OCR, fonte, escala)
                resumo.caracteres += len(texto)
                continue
            for b in grupo:
                _escrever_box(page, b, escala, fontes, resumo)


def _escrever_fens(page, diagramas: Sequence[DiagramaLido], escala: float, fontes,
                   resumo) -> None:
    """O FEN dos diagramas confiáveis, invisível no alto do tabuleiro, e o lado a jogar.

    O FEN fica sozinho na faixa de cima, para a busca achá-lo inteiro; na faixa
    de baixo dela vai a marca do lado, como no texto alternativo do DOCX e do
    EPUB: o `w` que ninguém disse sai "assumido", e o diagrama que ninguém
    conferiu, "não revisado".
    """
    from core import lado_a_jogar
    from core.searchable_pdf import FONTE_OCR

    fonte = fontes[0]
    for d in diagramas:
        if not d.confiavel:
            continue
        x1, y1, x2, y2 = d.caixa
        altura = max(10, (y2 - y1) // 8)
        faixa = BoxEntry(d.fen, x1, y1, x2, y1 + altura)
        _escrever(page, faixa, d.fen, FONTE_OCR, fonte, escala)
        marca = d.marca_do_lado() + ("" if d.conferido else f"; {lado_a_jogar.NAO_REVISADO}")
        _escrever(page, BoxEntry(marca, x1, y1 + altura, x2, y1 + 2 * altura), marca,
                  FONTE_OCR, fonte, escala)
        resumo.fens += 1


def _escrever_box(page, b: BoxEntry, escala: float, fontes, resumo) -> None:
    from core.searchable_pdf import FONTE_OCR, FONTE_SIMBOLOS

    from abbychess import texto as tx

    fonte, _, fonte_sym, _ = fontes
    char = tx.normalizar(b.char, tx.IMPRESSO)          # a ligadura sai "fi": a busca acha
    if not char:
        return
    if all(fonte.has_glyph(ord(c)) for c in char):
        nome, metrica = FONTE_OCR, fonte
    elif fonte_sym is not None and all(fonte_sym.has_glyph(ord(c)) for c in char):
        nome, metrica = FONTE_SIMBOLOS, fonte_sym
    else:
        resumo.sem_glifo += 1
        return
    _escrever(page, b, char, nome, metrica, escala)
    resumo.caracteres += len(char)


def _origem_do_texto(angulo: int, x1: float, y1: float, x2: float, y2: float):
    """Onde a linha de base começa, para cada ângulo do box: a 90° o texto sobe da base,
    a 270° desce do topo. A regra de `core.searchable_pdf`, aqui para não depender de um
    privado do core."""
    import fitz

    if angulo % 360 == 90:
        return fitz.Point(x2, y2)
    if angulo % 360 == 270:
        return fitz.Point(x1, y1)
    return fitz.Point(x1, y2)


def _corpo_que_preenche(fonte, texto: str, largura_alvo: float, altura_alvo: float) -> float:
    """O corpo que faz o texto ocupar a largura do box (a seleção no leitor de PDF cai
    sobre o caractere certo). A regra de `core.searchable_pdf`, aqui para não depender de
    um privado do core."""
    corpo = max(altura_alvo, 1.0)
    largura = fonte.text_length(texto, fontsize=corpo)
    if largura > 0 and largura_alvo > 0:
        corpo *= largura_alvo / largura
    return max(1.0, min(corpo, altura_alvo * 3.0))


def _escrever(page, b: BoxEntry, texto: str, nome: str, metrica, escala: float) -> None:

    x1, y1, x2, y2 = b.x1 * escala, b.y1 * escala, b.x2 * escala, b.y2 * escala
    angulo = (b.angulo or 0) % 360
    if angulo in (90, 270):
        corpo = _corpo_que_preenche(metrica, texto, y2 - y1, x2 - x1)
    else:
        corpo = _corpo_que_preenche(metrica, texto, x2 - x1, y2 - y1)
    page.insert_text(_origem_do_texto(angulo, x1, y1, x2, y2), texto, fontname=nome,
                     fontsize=corpo, render_mode=3, rotate=angulo)


def _fontes():
    import fitz

    from core.chess_pdf_processor import FONTES_DE_SIMBOLO, resolve_chess_font

    caminho = resolve_chess_font()
    caminho_sym = next((p for p in FONTES_DE_SIMBOLO if os.path.exists(p)), "")
    return (fitz.Font(fontfile=caminho), caminho,
            fitz.Font(fontfile=caminho_sym) if caminho_sym else None, caminho_sym)


def _na_original(caixa, angulo: float, largura: int, altura: int):
    """O box da página endireitada levado ao lugar dele na página do PDF original.

    Só translada, sem girar o box: a inclinação é de no máximo três graus, e a
    camada invisível precisa estar onde a palavra está, para a seleção e a
    busca acertarem. `caixa` é um `BoxEntry` ou uma tupla x1, y1, x2, y2.
    """
    x1, y1, x2, y2 = ((caixa.x1, caixa.y1, caixa.x2, caixa.y2) if isinstance(caixa, BoxEntry)
                      else caixa)
    cx, cy = pg.ponto_original((x1 + x2) / 2, (y1 + y2) / 2, angulo, largura, altura)
    dx, dy = round(cx - (x1 + x2) / 2), round(cy - (y1 + y2) / 2)
    movida = (x1 + dx, y1 + dy, x2 + dx, y2 + dy)
    if isinstance(caixa, BoxEntry):
        return replace(caixa, x1=movida[0], y1=movida[1], x2=movida[2], y2=movida[3])
    return movida


def exportar_pdf_pesquisavel(projeto: ProjetoDeLivro, caminho: str | Path,
                             indices: Optional[Iterable[int]] = None, *,
                             progresso: Optional[Progresso] = None) -> ResumoDoPdf:
    """O PDF com as páginas reconhecidas e a leitura do projeto como texto invisível.

    A página do PDF do livro sem quadro nem giro sai do original, sem rasterizar; as outras
    (as inseridas, as cortadas e as giradas, §12.4 CA-12.16, e toda página de fonte em
    imagem) viram uma página de PDF com a imagem da entrada a 300 dpi, a que se vê no
    programa, e a camada casa com ela sem conta nenhuma.

    O projeto que endireita as páginas tem os boxes nas coordenadas da página
    endireitada; no PDF original eles voltam ao lugar da página torta.
    """
    import fitz

    lidas = set(projeto.resumo.paginas_lidas())
    alvo = sorted(lidas if indices is None else lidas.intersection(indices))
    if not alvo:
        raise NadaParaExportar("Nenhuma página reconhecida para exportar.")
    resumo = ResumoDoPdf()
    fontes = _fontes()
    tinha_rotulos = False
    fonte = pg.fonte_do_projeto(projeto)
    # A posição no livro -> a página do PDF (§12.4); a que não sai do original, a imagem.
    entradas = [projeto.sequencia.entrada_em(i) for i in alvo]
    imagens = {i for i, e in zip(alvo, entradas)
               if not projeto.origem.e_pdf or not e.do_livro_sem_geometria}
    paginas_do_pdf = [e.pagina for e in entradas]
    #: O livro na ordem do PDF: o sumário e os rótulos do original ainda servem. Reordenado,
    #: eles saem e são refeitos pelos títulos e pelos números impressos do Documento.
    na_ordem = paginas_do_pdf == sorted(paginas_do_pdf)
    if not imagens:
        doc = fitz.open(projeto.fonte)
        # O `select` apaga os rótulos de página do original: o que ele tinha é lido antes.
        tinha_rotulos = na_ordem and bool(doc.get_page_labels())
        doc.select(paginas_do_pdf)                  # o `select` aceita qualquer ordem
        if not na_ordem:
            doc.set_toc([])                         # o sumário do original, fora de ordem
    else:
        doc = _pdf_com_imagens(projeto, fonte, alvo, entradas, imagens)
    escala = 72.0 / DPI_DA_LEITURA
    try:
        for feitas, (page, indice) in enumerate(zip(doc, alvo), start=1):
            if indice not in imagens and _texto_visivel(page):
                resumo.com_texto_proprio.append(indice)
            else:
                if indice not in imagens and _tirar_camada_invisivel(page):
                    resumo.camadas_trocadas += 1
                boxes = projeto.carregar_pagina(indice) or []
                diagramas = projeto.carregar_diagramas(indice)
                # A imagem da entrada já é a endireitada; a página do original, não.
                angulo = 0.0 if indice in imagens else fonte.inclinacao(indice)
                if angulo:
                    largura = round(page.rect.width / escala)
                    altura = round(page.rect.height / escala)
                    boxes = [_na_original(b, angulo, largura, altura) for b in boxes]
                    diagramas = [replace(d, caixa=_na_original(d.caixa, angulo, largura, altura))
                                 for d in diagramas]
                _escrever_camada(page, boxes, escala, fontes, resumo)
                _escrever_fens(page, diagramas, escala, fontes, resumo)
            resumo.paginas += 1
            if progresso:
                progresso(feitas, len(alvo))
        try:
            _marcar_o_pdf(doc, projeto, alvo, resumo, tinha_rotulos)
        except Exception as erro:  # noqa: BLE001 — sem marcadores o PDF continua bom
            log.warning("os marcadores e os rótulos do PDF não saíram (%s)", erro, exc_info=True)
        try:
            doc.subset_fonts()
        except Exception as erro:  # sem subset o arquivo só fica maior
            log.info("as fontes do PDF não foram reduzidas (%s)", erro, exc_info=True)
        _gravar_pdf(doc, Path(caminho))
    finally:
        doc.close()
    return resumo


def _pdf_com_imagens(projeto: ProjetoDeLivro, fonte: pg.FonteDePaginas, alvo: Sequence[int],
                     entradas: Sequence[sq.Entrada], imagens: set):
    """O PDF novo, página a página: a do original (`insert_pdf`, sem rasterizar) ou a imagem
    da entrada (as posições de `imagens`). O sumário do original não vem: os marcadores saem
    dos títulos do Documento."""
    import fitz

    doc = fitz.open()
    original = None
    escala = 72.0 / DPI_DA_LEITURA
    try:
        if projeto.origem.e_pdf:
            original = fitz.open(projeto.fonte)
        for indice, entrada in zip(alvo, entradas):
            if indice not in imagens:
                doc.insert_pdf(original, from_page=entrada.pagina, to_page=entrada.pagina,
                               links=False, annots=False)
                continue
            imagem = fonte.pagina(indice)
            dados = io.BytesIO()
            imagem.save(dados, format="PNG", optimize=True)
            pagina = doc.new_page(width=imagem.width * escala, height=imagem.height * escala)
            pagina.insert_image(pagina.rect, stream=dados.getvalue())
        doc.set_toc([])
    except BaseException:
        doc.close()
        raise
    finally:
        if original is not None:
            original.close()
    return doc


def _marcar_o_pdf(doc, projeto: ProjetoDeLivro, alvo: Sequence[int], resumo: ResumoDoPdf,
                  tinha_rotulos: bool = False) -> None:
    """Os marcadores pelos títulos do Documento e os rótulos pelo número impresso.

    O sumário e os rótulos que o PDF original já trazia ficam: são do editor, e um
    sumário refeito pelo OCR seria pior. Sem título nenhum, o PDF sai sem marcadores. Os
    modelos são carregados uma vez só para as duas coisas."""
    posicao = {indice: k for k, indice in enumerate(alvo)}
    lidos = {indice: Estrutura.da_pagina(projeto.carregar_modelo(indice)) for indice in alvo}
    # Depois do `select`, os marcadores das páginas que ficaram de fora já saíram.
    original = [m for m in doc.get_toc() if m[2] > 0]
    if original:
        resumo.marcadores_do_original = len(original)
    else:
        titulos = titulos_das_paginas(projeto, alvo, lidos)
        if titulos:
            doc.set_toc([[1, titulo, posicao[indice] + 1] for indice, titulo in titulos])
            resumo.marcadores = len(titulos)
    if tinha_rotulos:
        return
    # A altura de cada página sai do próprio PDF aberto (a 300 dpi, como os boxes).
    funcoes = _funcoes_dos_candidatos(
        {i: (lidos[i][0], round(doc[posicao[i]].rect.height * DPI_DA_LEITURA / 72))
         for i in alvo})
    numeros = numeros_impressos(lidos, funcoes, alvo)
    if not numeros:
        return
    regras: List[dict] = []
    anterior: Optional[int] = None
    for indice in alvo:
        numero = numeros.get(indice)
        if numero is None:
            # Sem número (as páginas de rosto, antes do 1): romanos, a partir do i. A
            # primeira regra tem de estar na página 0, ou o rótulo do PDF fica inválido.
            if anterior is not None or not regras:
                regras.append({"startpage": posicao[indice], "prefix": "", "style": "r",
                               "firstpagenum": 1})
            anterior = None
            continue
        if anterior is None or numero != anterior + 1:
            regras.append({"startpage": posicao[indice], "prefix": "", "style": "D",
                           "firstpagenum": numero})
        anterior = numero
    doc.set_page_labels(regras)
    resumo.rotulos = True


def _gravar_pdf(doc, caminho: Path) -> None:
    """Grava ao lado e troca no fim. Com `SOURCE_DATE_EPOCH`, os mesmos bytes (CA-12.6): as
    datas do arquivo são a dela, e o identificador do original fica (o PyMuPDF sorteia a
    segunda metade do `/ID` a cada gravação)."""
    epoca = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    if epoca.isdigit():
        quando = datetime.fromtimestamp(int(epoca), timezone.utc).strftime("D:%Y%m%d%H%M%S+00'00'")
        doc.set_metadata({**(doc.metadata or {}), "creationDate": quando, "modDate": quando})

    def escrever(temporario: Path) -> None:
        if epoca.isdigit():
            doc.save(str(temporario), garbage=3, deflate=True, no_new_id=True)
        else:
            doc.save(str(temporario), garbage=3, deflate=True)

    gv.gravar_por(caminho, escrever)
