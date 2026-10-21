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

**O PDF nascido digital não precisa de OCR para o DOCX e o EPUB.** Quando a
camada de texto de uma página é a tipografia do livro (`core.pdf_nativo`, a
régua por página), a página sai dela: as letras e as figurinas que o autor
escreveu, o negrito da linha principal, as colunas e o FEN exato dos diagramas
compostos em fonte. As outras páginas — digitalizadas, ou com a figurina em
imagem — saem dos boxes do projeto. O lado a jogar que o usuário conferiu na
revisão vale nos dois caminhos.

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

#: Quando ler a página da camada de texto do PDF: "auto" (quando a régua do
#: `core.pdf_nativo` aceita a página) ou "nunca" (sempre dos boxes do projeto).
CAMADA = ("auto", "nunca")

#: O idioma do arquivo exportado (`dc:language`, `xml:lang`) pelo do livro.
IDIOMAS_DO_ARQUIVO = {"pt": "pt-BR", "en": "en", "es": "es", "de": "de", "fr": "fr"}

#: Letras que só mudam de tamanho entre a minúscula e a maiúscula. O livro ensinado
#: pode ter o padrão com a caixa errada (um `o` ensinado como `O` lia o livro
#: inteiro com `abOut`), e a altura do glifo na linha decide.
LETRAS_DE_CAIXA_PELA_ALTURA = frozenset("cosvwxzCOSVWXZ")
#: Minúsculas sem haste nem perna: a altura delas é a altura-x da linha.
_ALTURA_X = frozenset("aemnru")
#: Maiúsculas e minúsculas com haste, de altura conhecida: a das maiúsculas. Sem o
#: `t`, que é mais baixo (21 px contra 31 do `h` no Odds & Ends), nem os números,
#: que no Garamond são de texto e sobem e descem.
_ALTURA_DE_MAIUSCULA = frozenset("ABDEFGHIJKLMNPRTUYbdfhkl")
#: Sem letra alta na linha, a letra ambígua até isto da altura-x é minúscula.
FOLGA_DA_ALTURA_X = 1.15
#: Entre a altura-x e a da maiúscula, onde a letra passa de uma caixa à outra.
CORTE_DA_CAIXA = 0.5

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
    #: O trecho de leitura (faixa, coluna) da linha; ver `_Leitura`.
    trecho: Tuple[int, int] = (0, 0)


def palavras(boxes: Sequence[BoxEntry]) -> List[List[Tuple[str, List[int]]]]:
    """As palavras de cada linha, `(texto, índices dos boxes)`, em ordem de leitura.

    O corte em linhas e palavras é o de `core.notacao.palavras_da_pagina`, mas
    o texto sai do próprio box: lá a figurina vira a letra do SAN (♘ -> N), e o
    livro exportado tem de mostrar o que estava impresso. Só o `✝` do xeque vira
    `+`, como em toda saída do PyBoxEditor (`notacao.normalizar_saida`).
    """
    return [linha for _trecho, linha in _palavras_por_trecho(boxes)]


def _palavras_por_trecho(boxes: Sequence[BoxEntry], leitura: Optional["_Leitura"] = None
                         ) -> List[Tuple[Tuple[int, int], List[Tuple[str, List[int]]]]]:
    """As linhas de `palavras`, cada uma com o trecho de leitura em que está."""
    from core.notacao import normalizar_saida, palavras_da_pagina

    leitura = leitura or _Leitura.da_pagina(boxes)
    saida = []
    for chave, trecho in leitura.trechos(boxes):
        parte = [boxes[i] for i in trecho]
        for linha in palavras_da_pagina(parte):
            indices = [trecho[s.indice] for p in linha for s in p.simbolos]
            caixa = _caixa_pela_altura(boxes, indices)
            saida.append((chave, [(_captura_minuscula("".join(
                normalizar_saida(caixa.get(trecho[s.indice], boxes[trecho[s.indice]].char))
                for s in p.simbolos)), [trecho[s.indice] for s in p.simbolos])
                for p in linha if p.simbolos]))
    return saida


#: O `X` de captura entre a peça (ou a coluna do peão) e a casa: `♖Xf2` é `♖xf2`.
_CAPTURA_MAIUSCULA = re.compile(r"(?<=[♔♕♖♗♘♚♛♜♝♞KQRBNa-h1-8])X(?=[a-h][1-8])")


def _captura_minuscula(palavra: str) -> str:
    """A captura sempre em minúscula: nenhum lance se escreve com `X`."""
    return _CAPTURA_MAIUSCULA.sub("x", palavra)


#: Quanto da calha, de cada lado, não conta para um box atravessar: o `9` que
#: abre a coluna da direita encosta na calha sem atravessá-la.
MARGEM_DA_CALHA = 0.25

#: Filas de texto que cada coluna precisa ter para a página ser lida em colunas.
FILAS_DE_COLUNA = 3


@dataclass
class _Leitura:
    """
    A ordem de leitura da página em trechos de uma coluna só: (faixa, coluna).

    **As linhas se montam dentro de cada trecho.** O `core.notacao` monta a linha
    pela altura, na ordem de leitura do `BoxService`; quando ela passa do pé de uma
    coluna para o alto da seguinte, o caractere de cima "não está abaixo" da linha
    corrente e entra nela — no Odds & Ends, `isfantastic:16...d3` e
    `♖hf820...♖df8`, a linha de uma coluna colada à da outra.

    O que atravessa a calha (o título `Games` centrado sobre as duas colunas) é uma
    faixa sozinha, na altura dele; entre duas dessas, as colunas da esquerda para a
    direita. Página de uma coluna é um trecho só. A mesma chave ordena as figuras
    (`chave` de um ponto), e é isso que põe o diagrama da coluna da esquerda entre
    os parágrafos dela, e não entre os da direita da mesma altura.
    """

    colunas: List[Tuple[int, int]] = field(default_factory=list)
    #: As faixas que atravessam, `[topo, pé]` em pixels, de cima para baixo.
    faixas: List[List[float]] = field(default_factory=list)

    @classmethod
    def da_pagina(cls, boxes: Sequence[BoxEntry]) -> "_Leitura":
        from core.services.box_service import BoxService

        if len(boxes) < 2:
            return cls()
        colunas = BoxService.detectar_colunas(list(boxes))
        if len(colunas) < 2:
            return cls()
        altura = statistics.median(b.y2 - b.y1 for b in boxes)
        # Uma coluna tem filas de texto: com uma linha só, o vão entre duas palavras
        # passaria por calha e partiria a linha.
        filas = [{round(((b.y1 + b.y2) / 2) / max(1.0, altura)) for b in boxes
                  if a <= (b.x1 + b.x2) / 2 <= z} for a, z in colunas]
        if min(len(f) for f in filas) < FILAS_DE_COLUNA:
            return cls()
        calhas = []
        for a, b in zip(colunas, colunas[1:]):
            largura = b[0] - a[1]
            calhas.append((a[1] + MARGEM_DA_CALHA * largura, b[0] - MARGEM_DA_CALHA * largura,
                           (a[1] + b[0]) / 2))
        na_calha = sorted(
            (b for b in boxes if b.y2 - b.y1 >= 0.5 * altura and any(
                a < (b.x1 + b.x2) / 2 < z or b.x1 < meio < b.x2 for a, z, meio in calhas)),
            key=lambda b: b.y1)
        grupos: List[List[BoxEntry]] = []
        for b in na_calha:
            if grupos and b.y1 <= max(o.y2 for o in grupos[-1]):
                grupos[-1].append(b)
            else:
                grupos.append([b])
        # Um box sozinho na calha é ruído (um filete, um respingo) — a não ser que
        # seja letra de título, bem maior que o texto.
        unidas = [[min(o.y1 for o in g), max(o.y2 for o in g)] for g in grupos
                  if len(g) >= 2 or max(o.y2 - o.y1 for o in g) >= 1.5 * altura]
        return cls(list(colunas), unidas)

    def chave(self, x: float, y: float) -> Tuple[int, int]:
        """A faixa (2k+1 a k-ésima que atravessa; 2k o que fica antes dela) e a coluna."""
        from core.pagina import _coluna_de

        if not self.colunas:
            return (0, 0)
        faixa = 2 * len(self.faixas)
        for k, (topo, pe) in enumerate(self.faixas):
            if topo <= y <= pe:
                faixa = 2 * k + 1
                break
            if y < topo:
                faixa = 2 * k
                break
        return (faixa, 0 if faixa % 2 else _coluna_de(x, self.colunas))

    def trechos(self, boxes: Sequence[BoxEntry]) -> List[Tuple[Tuple[int, int], List[int]]]:
        """Os índices dos boxes por trecho, na ordem de leitura dos trechos."""
        por_trecho: Dict[Tuple[int, int], List[int]] = {}
        for i, b in enumerate(boxes):
            por_trecho.setdefault(self.chave((b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2),
                                  []).append(i)
        return [(chave, por_trecho[chave]) for chave in sorted(por_trecho)]


def _caixa_pela_altura(boxes: Sequence[BoxEntry], indices: Sequence[int]) -> Dict[int, str]:
    """
    `{índice: letra}` das letras de caixa ambígua cuja altura desmente a caixa lida.

    A régua é da própria linha: a altura-x é a mediana das minúsculas sem haste
    (`a e m n r u`), a da maiúscula, a das letras de altura conhecida. Sem as duas,
    ou com elas perto demais (um título em versal), nada muda. No Odds & Ends o `O`
    lido pelo padrão do livro tinha 19 px, a altura do `c` e do `s`, e o `C`
    maiúsculo 31.
    """
    def altura(i: int) -> int:
        return boxes[i].y2 - boxes[i].y1

    baixas = [altura(i) for i in indices if boxes[i].char in _ALTURA_X]
    altas = [altura(i) for i in indices if boxes[i].char in _ALTURA_DE_MAIUSCULA]
    if not baixas:
        return {}
    x = statistics.median(baixas)
    maiuscula = statistics.median(altas) if altas else None
    if maiuscula is not None and maiuscula < 1.25 * x:
        return {}
    trocas = {}
    for i in indices:
        letra = boxes[i].char
        if letra not in LETRAS_DE_CAIXA_PELA_ALTURA:
            continue
        if maiuscula is None:
            # Só a minúscula se prova sem régua de maiúscula.
            certa = letra.lower() if altura(i) <= FOLGA_DA_ALTURA_X * x else letra
        else:
            corte = x + CORTE_DA_CAIXA * (maiuscula - x)
            certa = letra.lower() if altura(i) < corte else letra.upper()
        if certa != letra:
            trocas[i] = certa
    return trocas


def _linhas(boxes: Sequence[BoxEntry], leitura: Optional[_Leitura] = None) -> List[_Linha]:
    linhas = []
    for trecho, linha in _palavras_por_trecho(boxes, leitura):
        indices = [i for _, grupo in linha for i in grupo]
        texto = " ".join(t for t, _ in linha if t).strip()
        if not texto or not indices:
            continue
        linhas.append(_Linha(texto, min(boxes[i].y1 for i in indices),
                             max(boxes[i].y2 for i in indices), indices, trecho))
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
    # De cima para baixo, sem os trechos de coluna: o cabeçalho `Games 7`, com o
    # título numa coluna e o número na outra, é uma linha só, a primeira.
    linhas = _linhas(boxes, _Leitura())
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
    from core import lado_a_jogar

    for i, margem in margens.items():
        for linha, lugar in margem.candidatos:
            # "13.♕b3 0–0–0" no pé da coluna tem o "13" de um número de página,
            # e saía do livro como rodapé.
            if lado_a_jogar.tem_lance(linha.texto):
                continue
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
    return [p for _trecho, p in _paragrafos_por_trecho(boxes, cortes)]


def _paragrafos_por_trecho(boxes: Sequence[BoxEntry], cortes: Sequence[int] = (),
                           leitura: Optional[_Leitura] = None
                           ) -> List[Tuple[Tuple[int, int], Paragrafo]]:
    """Os parágrafos de `paragrafos`, cada um com o trecho de leitura em que começa."""
    linhas = _linhas(boxes, leitura)
    if not linhas:
        return []
    passos = [b.topo - a.topo for a, b in zip(linhas, linhas[1:])
              if b.topo > a.topo and a.trecho == b.trecho]
    passo = statistics.median(passos) if passos else 0
    grupos: List[List[_Linha]] = [[linhas[0]]]
    for anterior, linha in zip(linhas, linhas[1:]):
        salto = linha.topo - anterior.topo
        # Outro trecho (a coluna seguinte, a faixa que atravessa) também abre
        # parágrafo, como voltar para cima.
        if (salto <= 0 or linha.trecho != anterior.trecho
                or (passo and salto > SALTO_DE_PARAGRAFO * passo)
                or any(anterior.pe <= y < linha.topo for y in cortes)):
            grupos.append([linha])
        else:
            grupos[-1].append(linha)
    return [(g[0].trecho, Paragrafo(_juntar_linhas([linha.texto for linha in g]),
                                    topo=g[0].topo, pe=g[-1].pe))
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


#: Até onde, em casas, as coordenadas impressas ficam do tabuleiro: os números à
#: esquerda e as letras embaixo.
ALCANCE_DAS_COORDENADAS = 0.9


def _sem_coordenadas(boxes: Sequence[BoxEntry],
                     tabuleiros: Sequence[Tuple[int, int, int, int]]) -> List[BoxEntry]:
    """
    Os boxes de texto, sem o que está dentro do tabuleiro nem as coordenadas dele.

    No Odds & Ends os números de `8` a `1` à esquerda e o `a b c d e f g h` embaixo
    saíam no texto (`476542 a b c d e f g h10...♗h3?!`). Coordenada é **um
    caractere sozinho**: o número à esquerda, na altura de uma fila, e a letra
    embaixo, sob uma coluna — sem vizinho a menos de meia casa. A legenda logo
    abaixo do tabuleiro (`Branco joga`, `1-40`) tem as letras coladas e fica; o
    lance impresso logo acima (`9.e4 ♕h5 10.♘xc4`) também.
    """
    if not tabuleiros:
        return list(boxes)

    def centro(b: BoxEntry) -> Tuple[float, float]:
        return (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2

    def sozinho(b: BoxEntry, casa: float) -> bool:
        cx, cy = centro(b)
        return not any(o is not b and abs(centro(o)[0] - cx) < 0.5 * casa
                       and abs(centro(o)[1] - cy) < 0.5 * (b.y2 - b.y1 + o.y2 - o.y1)
                       for o in boxes)

    def fora(b: BoxEntry) -> bool:
        cx, cy = centro(b)
        for x1, y1, x2, y2 in tabuleiros:
            casa = max(1.0, (x2 - x1) / 8)
            folga = ALCANCE_DAS_COORDENADAS * casa
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                return True
            if (b.char in "12345678" and x1 - folga <= cx < x1 and y1 <= cy <= y2
                    and sozinho(b, casa)):
                return True
            if (b.char in "abcdefgh" and x1 <= cx <= x2 and y2 < cy <= y2 + folga
                    and sozinho(b, casa)):
                return True
        return False

    return [b for b in boxes if not fora(b)]


def pagina_extraida(indice: int, boxes: Sequence[BoxEntry],
                    tabuleiros: Sequence[Tuple[int, int, int, int]] = (),
                    imagem: Optional[Image.Image] = None,
                    diagramas: Sequence[DiagramaLido] = ()) -> PaginaExtraida:
    """A página gravada no formato que os escritores do PyBoxEditor pedem.

    Os diagramas entram na altura em que estão, quando há a imagem: os lidos
    com confiança, redesenhados do FEN; os outros, como recorte da página.
    """
    cortes = [t[1] for t in tabuleiros] if imagem is not None else []
    texto = _sem_coordenadas([b for b in boxes if b.char], tabuleiros)
    leitura = _Leitura.da_pagina(texto)
    com_trecho = _paragrafos_por_trecho(texto, cortes, leitura)
    blocos: list = [p for _trecho, p in com_trecho]
    figuras = []
    if imagem is not None:
        # Cada figura no trecho da coluna dela, e na altura dela dentro do trecho:
        # só pela altura, o diagrama da esquerda caía entre os parágrafos da direita.
        figuras = [(leitura.chave((d.caixa[0] + d.caixa[2]) / 2, d.caixa[1]), d.caixa[1],
                    figura_do_diagrama(imagem, d))
                   for d in para_caixas(tabuleiros, diagramas)]
        ordem = [(trecho, p.topo or 0, p) for trecho, p in com_trecho] + figuras
        blocos = [b for _t, _y, b in sorted(ordem, key=lambda item: (item[0], item[1]))]
    largura, altura = imagem.size if imagem is not None else (0, 0)
    return PaginaExtraida(numero=indice, blocos=blocos,
                          caracteres=sum(len(b.char) for b in boxes if b.char),
                          diagramas=len(figuras), altura=altura, largura=largura,
                          dpi=DPI_DA_LEITURA)


def paginas_do_projeto(projeto: ProjetoDeLivro, fonte: Optional[pg.FonteDePaginas],
                       indices: Optional[Iterable[int]] = None, *,
                       progresso: Optional[Progresso] = None,
                       camada: str = "auto") -> List[PaginaExtraida]:
    """
    As páginas reconhecidas do projeto, as de `indices` ou todas.

    Com `camada="auto"`, a página cuja camada de texto o `core.pdf_nativo` aceita
    sai dela, e as outras dos boxes. Depois, as duas passadas de livro, sobre as
    páginas dos dois caminhos: o parágrafo que a paginação partiu volta a ser um, e
    o diagrama sem lado lido ganha o do lance antes dele, conferido no tabuleiro e
    no lance seguinte.
    """
    from core import pdf_nativo

    if camada not in CAMADA:
        raise ValueError(f"camada inválida: {camada!r} (use um de {CAMADA})")
    lidas = set(projeto.paginas_lidas())
    alvo = sorted(lidas if indices is None else lidas.intersection(indices))
    if not alvo:
        raise NadaParaExportar("Nenhuma página reconhecida para exportar.")
    nativas = paginas_da_camada(projeto, alvo) if camada == "auto" else {}
    pelos_boxes = [i for i in alvo if i not in nativas]
    lidos = {i: [b for b in (projeto.carregar_pagina(i) or []) if b.char] for i in pelos_boxes}
    tirar = margens_corridas({i: (lidos[i], _altura_da_pagina(projeto, i)) for i in pelos_boxes})
    paginas = []
    for feitas, indice in enumerate(alvo, start=1):
        if indice in nativas:
            paginas.append(nativas[indice])
        else:
            tabuleiros = projeto.carregar_tabuleiros(indice)
            imagem = fonte.pagina(indice) if fonte is not None and tabuleiros else None
            texto = [b for k, b in enumerate(lidos[indice]) if k not in tirar[indice]]
            paginas.append(pagina_extraida(indice, texto, tabuleiros, imagem,
                                           projeto.carregar_diagramas(indice)))
        if progresso:
            progresso(feitas, len(alvo))
    pdf_nativo.juntar_entre_paginas(paginas)
    pdf_nativo.lados_pelos_lances(paginas)
    return paginas


def paginas_da_camada(projeto: ProjetoDeLivro, indices: Sequence[int]) -> Dict[int, PaginaExtraida]:
    """
    `{índice: página}` das páginas que saem da camada de texto do PDF.

    Só as que a régua do `core.pdf_nativo` aceita: a camada tem de ser a tipografia
    do livro, e não um OCR de fábrica nem uma página com a figurina em imagem. O
    lado a jogar que o usuário conferiu num diagrama do projeto passa para o
    diagrama da camada no mesmo lugar. Um PDF que não abre, ou uma página que a
    leitura não monta, fica com os boxes — o log diz por quê.
    """
    if not projeto.fonte_e_pdf or not indices:
        return {}
    from core import pdf_nativo

    try:
        extracao = pdf_nativo.extrair(str(projeto.fonte), list(indices),
                                      idioma=idioma_do_livro(projeto))
    except Exception as erro:  # noqa: BLE001 — o livro sai dos boxes, e não falha
        log.warning("A camada de texto do PDF não foi lida (%s: %s); as páginas saem dos boxes.",
                    type(erro).__name__, erro)
        return {}
    paginas = {p.numero: p for p in extracao.paginas}
    for indice, pagina in paginas.items():
        _lado_da_revisao(pagina, projeto.carregar_diagramas(indice))
    return paginas


def _lado_da_revisao(pagina: PaginaExtraida, diagramas: Sequence[DiagramaLido]) -> None:
    """O lado conferido na revisão vale sobre o da camada, no diagrama do mesmo lugar."""
    from core import pdf_nativo

    for figura in pagina.blocos:
        if not (isinstance(figura, Figura) and figura.fen and figura.caixa):
            continue
        [revisado] = para_caixas([tuple(figura.caixa)], diagramas)
        if revisado.conferido and revisado.lado in ("w", "b"):
            pdf_nativo.trocar_lado(figura, revisado.lado, _lado_do_desenho(),
                                   _moldura_padrao(), _cantos_padrao(),
                                   origem=revisado.lado_origem or "usuario")


def _lado_do_desenho() -> int:
    from core import render_diagrama
    return render_diagrama.LADO_PADRAO


def _moldura_padrao():
    from core import render_diagrama
    return render_diagrama.MOLDURA_PADRAO


def _cantos_padrao() -> str:
    from core import render_diagrama
    return render_diagrama.CANTO_PADRAO


def idioma_do_livro(projeto: ProjetoDeLivro) -> str:
    """
    O idioma do texto do livro: o que a camada de texto do PDF diz, ou o do projeto.

    O projeto nasce com "pt" quando ninguém escolhe, e o Odds & Ends, em inglês,
    saía com `dc:language` `pt-BR`. A camada responde por centenas de palavras
    (`pdf_nativo.idioma_do_pdf`); sem camada (a digitalização), vale o do projeto.
    """
    if projeto.fonte_e_pdf:
        from core import pdf_nativo

        try:
            lido = pdf_nativo.idioma_do_pdf(str(projeto.fonte))
        except (OSError, RuntimeError, ValueError):
            lido = None
        if lido:
            return lido
    return projeto.dados.idioma or "pt"


def idioma_do_arquivo(idioma: str) -> str:
    """A etiqueta BCP 47 do arquivo exportado: `pt` é `pt-BR`, o resto como está."""
    return IDIOMAS_DO_ARQUIVO.get(idioma, idioma or "pt-BR")


def _altura_da_pagina(projeto: ProjetoDeLivro, indice: int) -> int:
    """A altura da página lida, em pixels a 300 dpi, sem renderizá-la."""
    if projeto.fonte_e_pdf:
        import fitz

        with fitz.open(projeto.fonte) as doc:
            return round(doc[indice].rect.height * DPI_DA_LEITURA / 72)
    with Image.open(projeto.fonte) as imagem:
        return imagem.height


def exportar_docx(paginas: Sequence[PaginaExtraida], caminho: str | Path, *,
                  titulo: str, autor: str = "", idioma: str = "pt-BR") -> Path:
    from core.exportar import para_docx

    return Path(para_docx(paginas, str(caminho), titulo=titulo, autor=autor, idioma=idioma))


def exportar_epub(paginas: Sequence[PaginaExtraida], caminho: str | Path, *,
                  titulo: str, autor: str = "", idioma: str = "pt-BR") -> Path:
    from core.exportar import para_epub

    return Path(para_epub(paginas, str(caminho), titulo=titulo, autor=autor, idioma=idioma))


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
    escrever(paginas, caminho, titulo=projeto.dados.nome,
             idioma=idioma_do_arquivo(idioma_do_livro(projeto)))
    figuras = [b for p in paginas for b in p.blocos if isinstance(b, Figura)]
    desenhados = sum(f.origem == "render" for f in figuras)
    da_camada = sum(getattr(p, "leitura", "") == "camada" for p in paginas)
    resumo = (f"{len(paginas)} página(s), {sum(p.caracteres for p in paginas)} caracteres, "
              f"{desenhados} diagrama(s) desenhado(s) do FEN e "
              f"{len(figuras) - desenhados} como recorte")
    if da_camada:
        resumo += f"; {da_camada} página(s) lida(s) da camada de texto do PDF"
    return resumo + "."
