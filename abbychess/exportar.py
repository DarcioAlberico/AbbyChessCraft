"""Exportar o livro reconhecido: PDF pesquisável, DOCX e EPUB.

Os escritores são os do PyBoxEditor, e não cópias:

- **DOCX e EPUB** saem por `core.exportar.para_docx` e `para_epub`, que pedem a
  lista de `core.pagina.PaginaExtraida`. O que este módulo faz é montar essa
  lista a partir das páginas gravadas no projeto: as linhas pelo
  `core.notacao.palavras_da_pagina` (o mesmo que monta o texto do painel), os
  parágrafos pelo vão entre linhas. O diagrama lido e confiável (conferido, ou
  aprovado pelo porteiro do PyBoxEditor) é redesenhado do FEN por
  `core.render_diagrama`, com o FEN no texto alternativo; o resto sai como
  recorte da página, com o motivo no aviso.
- **O PDF pesquisável** usa as peças de `core.searchable_pdf`: as fontes, o
  corpo que preenche o box e a origem da linha de base. A função de lá,
  `gerar_pdf_pesquisavel`, segmenta e lê a página outra vez com a cadeia
  global; aqui a camada sai dos boxes do projeto, com o que o livro ensinou e
  o que o usuário corrigiu. A página original não é rasterizada. O FEN de cada
  diagrama confiável entra invisível sobre o tabuleiro, para a busca achá-lo.

Só entram as páginas já reconhecidas. Sem Qt: a janela chama isto numa thread.
"""

from __future__ import annotations

import difflib
import io
import logging
import os
import re
import statistics
import unicodedata
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from PIL import Image

from core.box_model import BoxEntry
from core.pagina import Figura, PaginaExtraida, Paragrafo

from abbychess import pagina as pg
from abbychess.diagramas import DiagramaLido, para_caixas
from abbychess.projeto import ProjetoDeLivro

log = logging.getLogger(__name__)

#: A resolução em que as páginas do PDF são lidas (`core.services.pdf_service`).
#: Os boxes gravados estão nesta escala.
DPI_DA_LEITURA = 300

#: Um passo entre linhas maior que isto, em passos medianos da página, abre
#: parágrafo. É o `core.pagina.SALTO_DE_PARAGRAFO` (0,6 além do passo).
SALTO_DE_PARAGRAFO = 1.6

FORMATOS = ("pdf", "docx", "epub")

#: A faixa de cima e a de baixo da página, em frações da altura, onde moram o
#: cabeçalho e o rodapé corridos. No Xadrez Vitorioso o cabeçalho fica entre 5%
#: e 7% da altura, e a primeira linha do texto em 10%.
FAIXA_DA_MARGEM = 0.10
#: O vão que separa o cabeçalho do texto, em passos medianos entre linhas. Lá o
#: vão é de 2 a 3 passos; entre duas linhas do texto, 1.
VAO_DA_MARGEM = 1.5
#: Texto de cabeçalho é curto: um título corrido com o número da página.
TAMANHO_DA_MARGEM = 80
#: Quanto dois cabeçalhos precisam se parecer, só nas letras, para serem o mesmo
#: em páginas diferentes. Baixo de propósito: o OCR de uma página lê "SElRAWAN"
#: e o da outra "SElRA AN".
SEMELHANCA_DA_MARGEM = 0.6
#: A borda extrema da página, onde uma linha de um ou dois caracteres é poeira
#: da digitalização, não texto ("l" em y=1, "." em y=3.480).
FAIXA_DA_POEIRA = 0.03
#: O número da página sozinho entre o que não é letra nem dígito: "22", "- 22 -", "-22-".
_NUMERO_DE_PAGINA = re.compile(r"(?<![^\W\d_])(?<!\d)\d{1,4}(?!\d)(?![^\W\d_])")

Progresso = Callable[[int, int], None]


class NadaParaExportar(ValueError):
    """Nenhuma das páginas pedidas foi reconhecida."""


# ----------------------------------------------------------------------
# Das páginas gravadas ao intermediário do PyBoxEditor
# ----------------------------------------------------------------------

@dataclass
class _Linha:
    texto: str
    topo: int
    pe: int
    indices: List[int] = field(default_factory=list)


def palavras(boxes: Sequence[BoxEntry]) -> List[List[Tuple[str, List[int]]]]:
    """As palavras de cada linha, `(texto, índices dos boxes)`, em ordem de leitura.

    O corte em linhas e palavras é o de `core.notacao.palavras_da_pagina`, mas
    o texto sai do próprio box: lá a figurina vira a letra do SAN (♘ -> N), e o
    livro exportado tem de mostrar o que estava impresso. Só o `✝` do xeque vira
    `+`, como em toda saída do PyBoxEditor (`notacao.normalizar_saida`).
    """
    from core.notacao import normalizar_saida, palavras_da_pagina

    saida = []
    for linha in palavras_da_pagina(boxes):
        saida.append([("".join(normalizar_saida(boxes[s.indice].char) for s in p.simbolos),
                       [s.indice for s in p.simbolos]) for p in linha if p.simbolos])
    return saida


def _linhas(boxes: Sequence[BoxEntry]) -> List[_Linha]:
    linhas = []
    for linha in palavras(boxes):
        indices = [i for _, grupo in linha for i in grupo]
        texto = " ".join(t for t, _ in linha if t).strip()
        if not texto or not indices:
            continue
        linhas.append(_Linha(texto, min(boxes[i].y1 for i in indices),
                             max(boxes[i].y2 for i in indices), indices))
    return linhas


# ----------------------------------------------------------------------
# Cabeçalho e rodapé corridos
# ----------------------------------------------------------------------

@dataclass
class _Margem:
    """O que sai do texto exportado de uma página, e o candidato a título corrido."""

    poeira: List[int] = field(default_factory=list)
    #: `(linha, "cabecalho" | "rodape")` que passaram pela posição e pelo vão.
    candidatos: List[Tuple[_Linha, str]] = field(default_factory=list)


def _so_letras(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", sem_acento.lower())


def _margem_da_pagina(boxes: Sequence[BoxEntry], altura: int) -> _Margem:
    margem = _Margem()
    linhas = _linhas(boxes)
    if not linhas or not altura:
        return margem
    poeira = [linha for linha in linhas if len(linha.texto.replace(" ", "")) <= 2 and (
        linha.pe < FAIXA_DA_POEIRA * altura or linha.topo > (1 - FAIXA_DA_POEIRA) * altura)]
    for linha in poeira:
        margem.poeira.extend(linha.indices)
    linhas = [linha for linha in linhas if linha not in poeira]
    if len(linhas) < 3:
        return margem
    passos = [b.topo - a.topo for a, b in zip(linhas, linhas[1:]) if b.topo > a.topo]
    passo = statistics.median(passos) if passos else 0
    if not passo:
        return margem
    primeira, segunda = linhas[0], linhas[1]
    if (primeira.pe < FAIXA_DA_MARGEM * altura and len(primeira.texto) <= TAMANHO_DA_MARGEM
            and segunda.topo - primeira.topo > VAO_DA_MARGEM * passo):
        margem.candidatos.append((primeira, "cabecalho"))
    penultima, ultima = linhas[-2], linhas[-1]
    if (ultima.topo > (1 - FAIXA_DA_MARGEM) * altura and len(ultima.texto) <= TAMANHO_DA_MARGEM
            and ultima.topo - penultima.topo > VAO_DA_MARGEM * passo):
        margem.candidatos.append((ultima, "rodape"))
    return margem


def margens_corridas(paginas: Dict[int, Tuple[Sequence[BoxEntry], int]]) -> Dict[int, set]:
    """Os boxes de cabeçalho, rodapé e poeira de cada página, para sair do texto.

    `paginas` é `{índice: (boxes lidos, altura da página)}`. Uma linha é título
    corrido quando está na faixa de cima (ou de baixo), separada do texto por um
    vão maior que o das linhas, é curta e, além disso, ou tem o número da página
    ou se repete, só nas letras, no mesmo lugar de outra página: o livro alterna
    o nome dos autores nas pares e o título nas ímpares. A primeira linha de um
    capítulo novo não tem número nem se repete, e fica.
    """
    margens = {i: _margem_da_pagina(boxes, altura) for i, (boxes, altura) in paginas.items()}
    saida = {i: set(m.poeira) for i, m in margens.items()}
    for i, margem in margens.items():
        for linha, lugar in margem.candidatos:
            letras = _so_letras(linha.texto)
            numero = bool(_NUMERO_DE_PAGINA.search(linha.texto))
            repete = any(
                lugar == outro_lugar and difflib.SequenceMatcher(
                    None, letras, _so_letras(outra.texto)).ratio() >= SEMELHANCA_DA_MARGEM
                for j, outra_margem in margens.items() if j != i
                for outra, outro_lugar in outra_margem.candidatos)
            if numero or (repete and letras):
                saida[i].update(linha.indices)
    return saida


def _juntar_linhas(textos: Sequence[str]) -> str:
    """As linhas de um parágrafo num texto só, desfazendo a hifenização."""
    saida = ""
    for texto in textos:
        if saida.endswith("-") and len(saida) > 1 and saida[-2].isalpha() and texto[:1].islower():
            saida = saida[:-1] + texto
        else:
            saida = f"{saida} {texto}" if saida else texto
    return saida


def paragrafos(boxes: Sequence[BoxEntry], cortes: Sequence[int] = ()) -> List[Paragrafo]:
    """Os parágrafos da página: linhas seguidas, cortadas onde o vão cresce.

    `cortes` são alturas da página (o topo de cada diagrama) que também
    separam parágrafos: o texto de cima e o de baixo de um diagrama não se
    juntam mesmo com passo normal.
    """
    linhas = _linhas(boxes)
    if not linhas:
        return []
    passos = [b.topo - a.topo for a, b in zip(linhas, linhas[1:]) if b.topo > a.topo]
    passo = statistics.median(passos) if passos else 0
    grupos: List[List[_Linha]] = [[linhas[0]]]
    for anterior, linha in zip(linhas, linhas[1:]):
        salto = linha.topo - anterior.topo
        # Voltar para cima é a coluna seguinte: também abre parágrafo.
        if (salto <= 0 or (passo and salto > SALTO_DE_PARAGRAFO * passo)
                or any(anterior.pe <= y < linha.topo for y in cortes)):
            grupos.append([linha])
        else:
            grupos[-1].append(linha)
    return [Paragrafo(_juntar_linhas([linha.texto for linha in g]), topo=g[0].topo, pe=g[-1].pe)
            for g in grupos]


def _figura(imagem: Image.Image, caixa: Tuple[int, int, int, int],
            aviso: str = "diagrama não lido: recorte da página") -> Figura:
    recorte = imagem.convert("L").crop(caixa)
    dados = io.BytesIO()
    recorte.save(dados, format="PNG")
    return Figura(png=dados.getvalue(), largura=recorte.width, altura=recorte.height,
                  origem="recorte", caixa=tuple(caixa), casas_de_largura=8.0, aviso=aviso)


def _aviso_do_recorte(diagrama: DiagramaLido) -> str:
    if not diagrama.lido:
        return f"diagrama não lido: {diagrama.erro or 'recorte da página'}"
    return f"posição não conferida e sem a confiança do porteiro: {diagrama.motivo}"


def _figura_desenhada(diagrama: DiagramaLido) -> Figura:
    """O diagrama redesenhado do FEN, como o `core.livro` faz no modo "render".

    O indicador de quem joga só é desenhado quando o lado foi dito (pela
    legenda ou na conferência); sem isso o FEN leva `w` por exigência do
    formato, e o texto alternativo carimba que foi assumido.
    """
    from core import render_diagrama as rd

    lado = diagrama.lado if diagrama.lado_origem else None
    fen = diagrama.fen
    png, largura, altura = rd.desenhar(fen, orientacao=diagrama.orientacao, lado_a_jogar=lado)
    linhas, emolduradas = rd.linhas_do_diagrama(fen, rd.carregar(rd.FONTE_PADRAO),
                                                diagrama.orientacao)
    return Figura(png, largura, altura, fen=fen, origem="render", linhas=linhas,
                  linhas_emolduradas=emolduradas, fonte=rd.FONTE_PADRAO,
                  orientacao=diagrama.orientacao,
                  casas_de_largura=largura * 8.0 / rd.lado_efetivo(rd.LADO_PADRAO),
                  caixa=tuple(diagrama.caixa), lado_a_jogar=lado,
                  lado_origem=diagrama.lado_origem or "convencao",
                  revisao_pendente=not diagrama.conferido)


def figura_do_diagrama(imagem: Image.Image, diagrama: DiagramaLido) -> Figura:
    """Desenhado do FEN se a leitura merece confiança; senão, o recorte."""
    if diagrama.confiavel:
        from core import render_diagrama as rd

        try:
            return _figura_desenhada(diagrama)
        except (rd.FonteDesconhecida, rd.FonteIncompleta) as erro:
            # Sem a fonte de xadrez, o livro sai com o recorte e diz por quê.
            return _figura(imagem, diagrama.caixa, f"não deu para desenhar: {erro}")
    return _figura(imagem, diagrama.caixa, _aviso_do_recorte(diagrama))


def pagina_extraida(indice: int, boxes: Sequence[BoxEntry],
                    tabuleiros: Sequence[Tuple[int, int, int, int]] = (),
                    imagem: Optional[Image.Image] = None,
                    diagramas: Sequence[DiagramaLido] = ()) -> PaginaExtraida:
    """A página gravada no formato que os escritores do PyBoxEditor pedem.

    Os diagramas entram na altura em que estão, quando há a imagem: os lidos
    com confiança, redesenhados do FEN; os outros, como recorte da página.
    """
    cortes = [t[1] for t in tabuleiros] if imagem is not None else []
    blocos: list = list(paragrafos([b for b in boxes if b.char], cortes))
    figuras = []
    if imagem is not None:
        figuras = [(d.caixa[1], figura_do_diagrama(imagem, d))
                   for d in para_caixas(tabuleiros, diagramas)]
        ordem = [(p.topo or 0, p) for p in blocos] + figuras
        blocos = [b for _, b in sorted(ordem, key=lambda par: par[0])]
    largura, altura = imagem.size if imagem is not None else (0, 0)
    return PaginaExtraida(numero=indice, blocos=blocos,
                          caracteres=sum(len(b.char) for b in boxes if b.char),
                          diagramas=len(figuras), altura=altura, largura=largura,
                          dpi=DPI_DA_LEITURA)


def paginas_do_projeto(projeto: ProjetoDeLivro, fonte: Optional[pg.FonteDePaginas],
                       indices: Optional[Iterable[int]] = None, *,
                       progresso: Optional[Progresso] = None) -> List[PaginaExtraida]:
    """As páginas reconhecidas do projeto, as de `indices` ou todas."""
    lidas = set(projeto.paginas_lidas())
    alvo = sorted(lidas if indices is None else lidas.intersection(indices))
    if not alvo:
        raise NadaParaExportar("Nenhuma página reconhecida para exportar.")
    lidos = {i: [b for b in (projeto.carregar_pagina(i) or []) if b.char] for i in alvo}
    tirar = margens_corridas({i: (lidos[i], _altura_da_pagina(projeto, i)) for i in alvo})
    paginas = []
    for feitas, indice in enumerate(alvo, start=1):
        tabuleiros = projeto.carregar_tabuleiros(indice)
        imagem = fonte.pagina(indice) if fonte is not None and tabuleiros else None
        texto = [b for k, b in enumerate(lidos[indice]) if k not in tirar[indice]]
        paginas.append(pagina_extraida(indice, texto, tabuleiros, imagem,
                                       projeto.carregar_diagramas(indice)))
        if progresso:
            progresso(feitas, len(alvo))
    return paginas


def _altura_da_pagina(projeto: ProjetoDeLivro, indice: int) -> int:
    """A altura da página lida, em pixels a 300 dpi, sem renderizá-la."""
    if projeto.fonte_e_pdf:
        import fitz

        with fitz.open(projeto.fonte) as doc:
            return round(doc[indice].rect.height * DPI_DA_LEITURA / 72)
    with Image.open(projeto.fonte) as imagem:
        return imagem.height


def exportar_docx(paginas: Sequence[PaginaExtraida], caminho: str | Path, *,
                  titulo: str, autor: str = "") -> Path:
    from core.exportar import para_docx

    return Path(para_docx(paginas, str(caminho), titulo=titulo, autor=autor, idioma="pt-BR"))


def exportar_epub(paginas: Sequence[PaginaExtraida], caminho: str | Path, *,
                  titulo: str, autor: str = "") -> Path:
    from core.exportar import para_epub

    return Path(para_epub(paginas, str(caminho), titulo=titulo, autor=autor, idioma="pt-BR"))


# ----------------------------------------------------------------------
# PDF pesquisável
# ----------------------------------------------------------------------

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


def _texto_visivel(page) -> bool:
    """A página tem texto que aparece, e não só uma camada de OCR invisível."""
    try:
        return any(traco.get("type") != 3 for traco in page.get_texttrace())
    except Exception as erro:  # PDF estranho: na dúvida, é texto de verdade
        log.debug("o rastro do texto não saiu (%s)", erro)
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
    from core import notacao
    from core.searchable_pdf import FONTE_OCR, FONTE_SIMBOLOS

    fonte, _, fonte_sym, _ = fontes
    char = notacao.normalizar_saida(b.char)
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


def _escrever(page, b: BoxEntry, texto: str, nome: str, metrica, escala: float) -> None:
    from core.searchable_pdf import _corpo_que_preenche, _origem_do_texto

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

    Com fonte em PDF, as páginas são as do original, sem rasterizar; com fonte
    em imagem, cada página vira uma página de PDF com a imagem a 300 dpi.

    O projeto que endireita as páginas tem os boxes nas coordenadas da página
    endireitada; no PDF original eles voltam ao lugar da página torta.
    """
    import fitz

    lidas = set(projeto.paginas_lidas())
    alvo = sorted(lidas if indices is None else lidas.intersection(indices))
    if not alvo:
        raise NadaParaExportar("Nenhuma página reconhecida para exportar.")
    resumo = ResumoDoPdf()
    fontes = _fontes()
    if projeto.fonte_e_pdf:
        doc = fitz.open(projeto.fonte)
        doc.select(alvo)
    else:
        doc = fitz.open()
        # Com fonte em imagem, a página do PDF é a endireitada: a camada casa
        # com ela sem girar nada.
        imagem = pg.fonte_do_projeto(projeto).pagina(0)
        dados = io.BytesIO()
        imagem.save(dados, format="PNG")
        escala_img = 72.0 / DPI_DA_LEITURA
        pagina = doc.new_page(width=imagem.width * escala_img, height=imagem.height * escala_img)
        pagina.insert_image(pagina.rect, stream=dados.getvalue())
    escala = 72.0 / DPI_DA_LEITURA
    fonte = pg.fonte_do_projeto(projeto) if projeto.fonte_e_pdf else None
    try:
        for feitas, (page, indice) in enumerate(zip(doc, alvo), start=1):
            if _texto_visivel(page):
                resumo.com_texto_proprio.append(indice)
            else:
                if _tirar_camada_invisivel(page):
                    resumo.camadas_trocadas += 1
                boxes = projeto.carregar_pagina(indice) or []
                diagramas = projeto.carregar_diagramas(indice)
                angulo = fonte.inclinacao(indice) if fonte is not None else 0.0
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
            doc.subset_fonts()
        except Exception as erro:  # sem subset o arquivo só fica maior
            log.info("as fontes do PDF não foram reduzidas (%s)", erro)
        _gravar_pdf(doc, Path(caminho))
    finally:
        doc.close()
    return resumo


def _gravar_pdf(doc, caminho: Path) -> None:
    temporario = caminho.with_name(caminho.name + ".tmp")
    doc.save(str(temporario), garbage=3, deflate=True)
    temporario.replace(caminho)


# ----------------------------------------------------------------------
# Uma porta só
# ----------------------------------------------------------------------

def formato_do_caminho(caminho: str | Path) -> str:
    formato = Path(caminho).suffix.lower().lstrip(".")
    if formato not in FORMATOS:
        raise ValueError(f"Formato {formato or '(sem extensão)'} não suportado; "
                         f"use {', '.join(FORMATOS)}.")
    return formato


def exportar(projeto: ProjetoDeLivro, caminho: str | Path,
             indices: Optional[Iterable[int]] = None, *,
             progresso: Optional[Progresso] = None) -> str:
    """Exporta no formato da extensão de `caminho` e devolve o resumo para a tela."""
    formato = formato_do_caminho(caminho)
    caminho = Path(caminho)
    if formato == "pdf":
        resumo = exportar_pdf_pesquisavel(projeto, caminho, indices, progresso=progresso)
        partes = [f"{resumo.paginas} página(s), {resumo.caracteres} caracteres na camada"]
        if resumo.camadas_trocadas:
            partes.append(f"camada antiga trocada em {resumo.camadas_trocadas}")
        if resumo.com_texto_proprio:
            partes.append(f"{len(resumo.com_texto_proprio)} com texto próprio ficaram sem camada")
        if resumo.fens:
            partes.append(f"{resumo.fens} diagrama(s) com o FEN pesquisável")
        if resumo.sem_glifo:
            partes.append(f"{resumo.sem_glifo} sem glifo na fonte")
        return "; ".join(partes) + "."
    fonte = pg.fonte_do_projeto(projeto)
    paginas = paginas_do_projeto(projeto, fonte, indices, progresso=progresso)
    escrever = exportar_docx if formato == "docx" else exportar_epub
    escrever(paginas, caminho, titulo=projeto.dados.nome)
    figuras = [b for p in paginas for b in p.blocos if isinstance(b, Figura)]
    desenhados = sum(f.origem == "render" for f in figuras)
    return (f"{len(paginas)} página(s), {sum(p.caracteres for p in paginas)} caracteres, "
            f"{desenhados} diagrama(s) desenhado(s) do FEN e "
            f"{len(figuras) - desenhados} como recorte.")
