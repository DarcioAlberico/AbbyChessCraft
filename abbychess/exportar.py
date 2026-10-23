"""Exportar o livro reconhecido: PDF pesquisável, DOCX, EPUB, TXT e PGN.

O que vem do PyBoxEditor e o que é desta aplicação:

- **DOCX** e **EPUB** saem pelos escritores próprios (`abbychess.escritor_docx` e
  `abbychess.epub`, desde o passo J; os do core deixaram de ser usados); os dois pedem a lista de
  `core.pagina.PaginaExtraida`. O que este módulo faz é montar essa
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
from abbychess import sequencia as sq
from abbychess.diagramas import DiagramaLido, para_caixas
from abbychess.layout import _coluna_de
from abbychess.projeto import ProjetoDeLivro

log = logging.getLogger(__name__)

#: A resolução em que as páginas do PDF são lidas (`core.services.pdf_service`).
#: Os boxes gravados estão nesta escala.
DPI_DA_LEITURA = 300

#: Um passo entre linhas maior que isto, em passos medianos da página, abre
#: parágrafo. É o `core.pagina.SALTO_DE_PARAGRAFO` (0,6 além do passo).
SALTO_DE_PARAGRAFO = 1.6

FORMATOS = ("pdf", "docx", "epub", "txt", "pgn")

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


@dataclass(frozen=True)
class Opcoes:
    """As opções da exportação (§12.1). O padrão é o livro limpo: sem margens corridas,
    o texto refluído, os diagramas confiáveis desenhados."""

    #: Cabeçalhos, rodapés e números de página ficam no texto.
    manter_margens: bool = False
    #: Só as páginas verificadas (§4.4).
    so_verificadas: bool = False
    #: Os diagramas confiáveis redesenhados do FEN; falso, todos como recorte da página.
    desenhar_diagramas: bool = True
    #: No TXT, uma marca `[p. N]` no começo de cada página.
    marcas_de_pagina: bool = False


@dataclass
class Relatorio:
    """O que a exportação fez e deixou de fora (§12.2), com a página de cada item."""

    formato: str = ""
    paginas: List[int] = field(default_factory=list)
    da_camada: List[int] = field(default_factory=list)
    caracteres: int = 0
    titulos: List[Tuple[int, str]] = field(default_factory=list)
    #: Página -> os textos de cabeçalho, rodapé e número de página tirados.
    margens: Dict[int, List[str]] = field(default_factory=dict)
    desenhados: int = 0
    #: (página, motivo) de cada diagrama que saiu como recorte.
    recortados: List[Tuple[int, str]] = field(default_factory=list)
    nao_verificadas: List[int] = field(default_factory=list)
    #: Página -> glifos pendentes de revisão.
    pendentes: Dict[int, int] = field(default_factory=dict)
    #: No PGN: (página, número do diagrama, motivo) dos que ficaram de fora, e quantos entraram.
    fora_do_pgn: List[Tuple[int, int, str]] = field(default_factory=list)
    no_pgn: int = 0
    #: No PDF pesquisável, o resumo dele (o relatório por item é dos outros formatos).
    resumo_do_pdf: str = ""
    #: No EPUB: os capítulos, as figuras que reaproveitaram uma imagem igual e o que a
    #: conferência do arquivo escrito acusou (`epub.conferir`).
    capitulos: int = 0
    imagens_reutilizadas: int = 0
    problemas_do_arquivo: List[str] = field(default_factory=list)
    #: Índice da página -> o número impresso nela (`numeros_impressos`), quando se sabe.
    numeros_impressos: Dict[int, int] = field(default_factory=dict)
    #: No EPUB, as referências a página que viraram link; no PDF, os marcadores.
    links: int = 0
    marcadores: int = 0

    def resumo(self) -> str:
        """Uma linha, para a barra de status."""
        if self.formato == "pdf":
            return self.resumo_do_pdf
        if self.formato == "pgn":
            partes = [f"{self.no_pgn} diagrama(s) com a posição e os lances"]
            if self.fora_do_pgn:
                partes.append(f"{len(self.fora_do_pgn)} de fora (ver Resultados)")
            return "; ".join(partes) + "."
        partes = [f"{len(self.paginas)} página(s), {self.caracteres} caracteres"]
        if self.titulos:
            partes.append(f"{len(self.titulos)} título(s)")
        partes.append(f"{self.desenhados} diagrama(s) desenhado(s) do FEN e "
                      f"{len(self.recortados)} como recorte")
        if self.da_camada:
            partes.append(f"{len(self.da_camada)} página(s) lida(s) da camada de texto do PDF")
        tiradas = sum(len(v) for v in self.margens.values())
        if tiradas:
            partes.append(f"{tiradas} linha(s) de cabeçalho/rodapé tirada(s)")
        if self.nao_verificadas:
            partes.append(f"{len(self.nao_verificadas)} página(s) não verificada(s)")
        if self.capitulos:
            partes.append(f"{self.capitulos} capítulo(s)")
        if self.links:
            partes.append(f"{self.links} referência(s) a página, diagrama ou capítulo com link")
        if self.numeros_impressos and self.formato == "epub":
            primeira = min(self.numeros_impressos)
            partes.append(f"página impressa {self.numeros_impressos[primeira]} na posição "
                          f"{primeira + 1} do PDF")
        if self.imagens_reutilizadas:
            partes.append(f"{self.imagens_reutilizadas} imagem(ns) reaproveitada(s)")
        if self.problemas_do_arquivo:
            partes.append(f"{len(self.problemas_do_arquivo)} problema(s) no arquivo "
                          "(ver Resultados)")
        return "; ".join(partes) + "."

    def texto(self) -> str:
        """O relatório inteiro, uma linha por item, com a página (para Resultados)."""
        linhas = [self.resumo()]
        for pagina, titulo in self.titulos:
            linhas.append(f"p. {pagina + 1}: título “{titulo}”")
        for pagina, textos in sorted(self.margens.items()):
            for t in textos:
                linhas.append(f"p. {pagina + 1}: margem tirada “{t}”")
        for pagina, motivo in self.recortados:
            linhas.append(f"p. {pagina + 1}: diagrama como recorte ({motivo})")
        for pagina, numero, motivo in self.fora_do_pgn:
            linhas.append(f"p. {pagina + 1}: diagrama {numero} fora do PGN ({motivo})")
        if self.nao_verificadas:
            linhas.append("Páginas não verificadas: "
                          + ", ".join(str(i + 1) for i in self.nao_verificadas))
        for problema in self.problemas_do_arquivo:
            linhas.append(f"arquivo: {problema}")
        com_pendentes = {i: n for i, n in sorted(self.pendentes.items()) if n}
        if com_pendentes:
            linhas.append("Glifos pendentes: " + ", ".join(
                f"p. {i + 1} ({n})" for i, n in com_pendentes.items()))
        return "\n".join(linhas)


# ----------------------------------------------------------------------
# Das páginas gravadas ao intermediário do PyBoxEditor
# ----------------------------------------------------------------------

#: As funções de área que não são o texto do livro: saem da exportação, salvo com a opção
#: de manter cabeçalhos e rodapés (§12.1). `ignorar` sai sempre.
FUNCOES_DE_MARGEM = ("cabecalho", "rodape", "numero_de_pagina")
FORA_DA_EXPORTACAO = FUNCOES_DE_MARGEM + ("ignorar",)


@dataclass
class Estrutura:
    """O que o Documento (§4.2) sabe de cada box da página, para a exportação ler (§12.1).

    A montagem das linhas e dos parágrafos continua a desta exportação (a caixa pela
    altura, os trechos de coluna, as coordenadas), que tem casos medidos; a estrutura diz
    o que ela não tinha como saber: a função da área (título, margens, nota, legenda,
    ignorar), o negrito e o itálico do glifo, o parágrafo pedido e o hífen de quebra.
    Chaveada pelo `id` do `BoxEntry`, para sobreviver aos filtros da lista de boxes."""

    funcoes: Dict[int, str] = field(default_factory=dict)
    negrito: set = field(default_factory=set)
    italico: set = field(default_factory=set)
    paragrafo_antes: set = field(default_factory=set)
    hifen_de_quebra: set = field(default_factory=set)
    #: Os boxes numa área desenhada pelo usuário com função de texto (não de margem): a
    #: regra das margens corridas (`margens_corridas`) não os tira.
    protegidos: set = field(default_factory=set)
    #: Os `BoxEntry` da estrutura, vivos enquanto ela viver: as chaves são `id()`.
    vivos: list = field(default_factory=list)

    def funcao(self, b: BoxEntry) -> str:
        return self.funcoes.get(id(b), "texto")

    @classmethod
    def da_pagina(cls, pagina) -> Tuple[List[BoxEntry], "Estrutura"]:
        """Os boxes lidos da página do modelo (`modelo.Pagina`) e a estrutura deles; sem
        modelo, nada."""
        from abbychess import zonas as zn

        if pagina is None:
            return [], cls()
        lidos = [b for b in pagina.boxes if b.entry.char]
        areas = [z for z in pagina.zonas if z.tipo in (zn.TEXTO, zn.IGNORAR)]
        estrutura = cls(vivos=[b.entry for b in lidos])
        decisoes = pagina.decisoes
        for b in lidos:
            e = b.entry
            cx, cy = (e.x1 + e.x2) / 2, (e.y1 + e.y2) / 2
            area = next((z for z in areas if z.contem(cx, cy)), None)
            if area is not None:
                funcao = "ignorar" if area.tipo == zn.IGNORAR else area.funcao or "texto"
                estrutura.funcoes[id(e)] = funcao
                if not area.automatica and funcao not in FORA_DA_EXPORTACAO:
                    estrutura.protegidos.add(id(e))
            if b.estilo.negrito:
                estrutura.negrito.add(id(e))
            if b.estilo.italico:
                estrutura.italico.add(id(e))
            if b.gid in decisoes.paragrafo_antes:
                estrutura.paragrafo_antes.add(id(e))
            if b.gid in decisoes.hifen_de_quebra:
                estrutura.hifen_de_quebra.add(id(e))
        return list(estrutura.vivos), estrutura


@dataclass
class _Linha:
    texto: str
    topo: int
    pe: int
    indices: List[int] = field(default_factory=list)
    #: O trecho de leitura (faixa, coluna) da linha; ver `_Leitura`.
    trecho: Tuple[int, int] = (0, 0)
    #: Da `Estrutura`: a função da área da linha, se ela pede parágrafo, se termina num
    #: hífen de quebra decidido, e os trechos `(início, fim)` em negrito e em itálico.
    funcao: str = "texto"
    paragrafo: bool = False
    hifen: bool = False
    negrito: List[Tuple[int, int]] = field(default_factory=list)
    italico: List[Tuple[int, int]] = field(default_factory=list)


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
        for linha in palavras_da_pagina(
                parte, leitura.deteccao if len(trecho) == len(boxes) else None):
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
    #: A detecção do core sobre a página inteira, que o core reaproveita quando a página é
    #: um trecho só (como em `layout.OrdemDeLeitura`).
    deteccao: object = field(default=None, compare=False, repr=False)

    @classmethod
    def da_pagina(cls, boxes: Sequence[BoxEntry]) -> "_Leitura":
        from core.services.box_service import BoxService

        if len(boxes) < 2:
            return cls()
        deteccao = BoxService.detectar_colunas_e_transversais(list(boxes))
        colunas = deteccao[0]
        if len(colunas) < 2:
            return cls(deteccao=deteccao)
        altura = statistics.median(b.y2 - b.y1 for b in boxes)
        # Uma coluna tem filas de texto: com uma linha só, o vão entre duas palavras
        # passaria por calha e partiria a linha.
        filas = [{round(((b.y1 + b.y2) / 2) / max(1.0, altura)) for b in boxes
                  if a <= (b.x1 + b.x2) / 2 <= z} for a, z in colunas]
        if min(len(f) for f in filas) < FILAS_DE_COLUNA:
            return cls(deteccao=deteccao)
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


def _linhas(boxes: Sequence[BoxEntry], leitura: Optional[_Leitura] = None,
            estrutura: Optional[Estrutura] = None) -> List[_Linha]:
    linhas = []
    for trecho, linha in _palavras_por_trecho(boxes, leitura):
        indices = [i for _, grupo in linha for i in grupo]
        texto = " ".join(t for t, _ in linha if t).strip()
        if not texto or not indices:
            continue
        nova = _Linha(texto, min(boxes[i].y1 for i in indices),
                      max(boxes[i].y2 for i in indices), indices, trecho)
        if estrutura is not None:
            _com_a_estrutura(nova, linha, boxes, estrutura)
        linhas.append(nova)
    return linhas


def _com_a_estrutura(linha: _Linha, palavras_da_linha, boxes: Sequence[BoxEntry],
                     estrutura: Estrutura) -> None:
    """A função, o parágrafo, o hífen e os estilos da linha, pela `Estrutura`."""
    entradas = [boxes[i] for i in linha.indices]
    funcoes = [estrutura.funcao(b) for b in entradas]
    linha.funcao = max(set(funcoes), key=funcoes.count)
    linha.paragrafo = id(entradas[0]) in estrutura.paragrafo_antes
    linha.hifen = id(entradas[-1]) in estrutura.hifen_de_quebra and linha.texto.endswith("-")
    for nome, marcados in (("negrito", estrutura.negrito), ("italico", estrutura.italico)):
        trechos: List[Tuple[int, int]] = []
        posicao = 0
        for texto, grupo in palavras_da_linha:
            if not texto:
                continue
            if len(texto) == len(grupo):            # um caractere por glifo: letra a letra
                for k, i in enumerate(grupo):
                    if id(boxes[i]) in marcados:
                        trechos.append((posicao + k, posicao + k + 1))
            elif all(id(boxes[i]) in marcados for i in grupo):
                trechos.append((posicao, posicao + len(texto)))
            posicao += len(texto) + 1
        setattr(linha, nome, _unir_trechos(trechos, linha.texto))


def _unir_trechos(trechos: Sequence[Tuple[int, int]], texto: str = "") -> List[Tuple[int, int]]:
    """Os trechos ordenados, com os encostados (ou separados só por um espaço de `texto`)
    num só. Uma letra não marcada entre dois trechos continua de fora."""
    saida: List[Tuple[int, int]] = []
    for inicio, fim in sorted(trechos):
        if saida and (inicio <= saida[-1][1] or (
                inicio == saida[-1][1] + 1 and texto[saida[-1][1]:inicio] == " ")):
            saida[-1] = (saida[-1][0], max(saida[-1][1], fim))
        else:
            saida.append((inicio, fim))
    return saida


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
    funcoes, margens = _funcoes_das_margens(paginas)
    return {i: set(margens[i].poeira) | set(funcoes[i]) for i in paginas}


def funcoes_das_margens(paginas: Dict[int, Tuple[Sequence[BoxEntry], int]]) -> Dict[int, dict]:
    """`{página: {indice_do_box: função}}` aprendido no conjunto do livro.

    Ao contrário de :func:`margens_corridas`, poeira não aparece: ela não é cabeçalho
    nem rodapé e requer uma zona `ignorar`, de outro tipo.
    """
    funcoes, _margens = _funcoes_das_margens(paginas)
    return funcoes


def _funcoes_das_margens(paginas: Dict[int, Tuple[Sequence[BoxEntry], int]]
                          ) -> Tuple[Dict[int, dict], Dict[int, _Margem]]:
    margens = {i: _margem_da_pagina(boxes, altura) for i, (boxes, altura) in paginas.items()}
    saida = {i: {} for i in paginas}
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
                texto = linha.texto.strip()
                funcao = ("numero_de_pagina" if re.fullmatch(r"\D*\d{1,4}\D*", texto)
                          and not letras else lugar)
                saida[i].update({indice: funcao for indice in linha.indices})
    return saida, margens


def _juntar_linhas(textos: Sequence[str]) -> str:
    """As linhas de um parágrafo num texto só, desfazendo a hifenização."""
    saida = ""
    for texto in textos:
        if saida.endswith("-") and len(saida) > 1 and saida[-2].isalpha() and texto[:1].islower():
            saida = saida[:-1] + texto
        else:
            saida = f"{saida} {texto}" if saida else texto
    return saida


def _juntar(linhas: Sequence[_Linha]) -> Tuple[str, List[Tuple[int, int]], List[Tuple[int, int]]]:
    """O texto do parágrafo e os trechos em negrito e em itálico, já no texto juntado.

    O hífen de quebra decidido no Documento (§6.3) sai sempre; o não decidido sai pela
    regra de `_juntar_linhas` (letra antes, minúscula depois)."""
    texto, negrito, italico = "", [], []
    anterior: Optional[_Linha] = None
    for linha in linhas:
        if anterior is None:
            base = 0
        elif anterior.hifen or (texto.endswith("-") and len(texto) > 1 and texto[-2].isalpha()
                                and linha.texto[:1].islower()):
            texto = texto[:-1]
            base = len(texto)
            # O trecho que acabava no hífen não pode cobrir a letra da linha seguinte.
            negrito = [(a, min(b, base)) for a, b in negrito if a < base]
            italico = [(a, min(b, base)) for a, b in italico if a < base]
        else:
            texto += " "
            base = len(texto)
        texto += linha.texto
        negrito += [(base + a, base + b) for a, b in linha.negrito]
        italico += [(base + a, base + b) for a, b in linha.italico]
        anterior = linha

    def cortados(trechos):
        return _unir_trechos([(a, min(b, len(texto))) for a, b in trechos if a < len(texto)],
                             texto)
    return texto, cortados(negrito), cortados(italico)


def paragrafos(boxes: Sequence[BoxEntry], cortes: Sequence[int] = ()) -> List[Paragrafo]:
    """Os parágrafos da página: linhas seguidas, cortadas onde o vão cresce.

    `cortes` são alturas da página (o topo de cada diagrama) que também
    separam parágrafos: o texto de cima e o de baixo de um diagrama não se
    juntam mesmo com passo normal.
    """
    return [p for _trecho, p in _paragrafos_por_trecho(boxes, cortes)]


def _paragrafos_por_trecho(boxes: Sequence[BoxEntry], cortes: Sequence[int] = (),
                           leitura: Optional[_Leitura] = None,
                           estrutura: Optional[Estrutura] = None
                           ) -> List[Tuple[Tuple[int, int], Paragrafo]]:
    """Os parágrafos de `paragrafos`, cada um com o trecho de leitura em que começa.

    Com a `Estrutura`, também abre parágrafo onde a função da área muda (o título, a
    nota, a legenda) e onde o Documento pediu (`paragrafo_antes`); a linha de área
    `titulo` sai como título de capítulo (o `<h1>` do sumário)."""
    linhas = _linhas(boxes, leitura, estrutura)
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
                or any(anterior.pe <= y < linha.topo for y in cortes)
                or linha.funcao != anterior.funcao or linha.paragrafo):
            grupos.append([linha])
        else:
            grupos[-1].append(linha)
    saida = []
    for g in grupos:
        texto, negrito, italico = _juntar(g)
        titulo = g[0].funcao == "titulo"
        saida.append((g[0].trecho, Paragrafo(texto, titulo=titulo, nivel=1 if titulo else 2,
                                             negrito=negrito, italico=italico,
                                             topo=g[0].topo, pe=g[-1].pe)))
    return saida


def _figura(imagem: Image.Image, caixa: Tuple[int, int, int, int],
            aviso: str = "diagrama não lido: recorte da página") -> Figura:
    recorte = imagem.convert("L").crop(caixa)
    dados = io.BytesIO()
    recorte.save(dados, format="PNG")
    return Figura(png=dados.getvalue(), largura=recorte.width, altura=recorte.height,
                  origem="recorte", caixa=tuple(caixa), casas_de_largura=8.0, aviso=aviso)


#: O aviso do diagrama recortado porque as opções pediram recortes (§12.1).
RECORTE_PEDIDO = "recorte pedido nas opções da exportação"


def _aviso_do_recorte(diagrama: DiagramaLido) -> str:
    if not diagrama.lido:
        return f"diagrama não lido: {diagrama.erro or 'recorte da página'}"
    if diagrama.validacao is not None and not diagrama.validacao.confiavel:
        return f"posição não conferida: {diagrama.validacao.aviso}"
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
                    diagramas: Sequence[DiagramaLido] = (),
                    estrutura: Optional[Estrutura] = None,
                    manter_margens: bool = False,
                    desenhar_diagramas: bool = True) -> PaginaExtraida:
    """A página gravada no formato que os escritores do PyBoxEditor pedem.

    Os diagramas entram na altura em que estão, quando há a imagem: os lidos
    com confiança, redesenhados do FEN; os outros, como recorte da página. Com a
    `Estrutura` do Documento, as áreas de margem e as de ignorar saem (as de margem
    ficam com `manter_margens`), e títulos, estilos e parágrafos seguem o Documento.
    """
    cortes = [t[1] for t in tabuleiros] if imagem is not None else []
    texto = _sem_coordenadas([b for b in boxes if b.char], tabuleiros)
    if estrutura is not None:
        fora = ("ignorar",) if manter_margens else FORA_DA_EXPORTACAO
        texto = [b for b in texto if estrutura.funcao(b) not in fora]
    leitura = _Leitura.da_pagina(texto)
    com_trecho = _paragrafos_por_trecho(texto, cortes, leitura, estrutura)
    blocos: list = [p for _trecho, p in com_trecho]
    figuras = []
    if imagem is not None:
        # Cada figura no trecho da coluna dela, e na altura dela dentro do trecho:
        # só pela altura, o diagrama da esquerda caía entre os parágrafos da direita.
        figuras = [(leitura.chave((d.caixa[0] + d.caixa[2]) / 2, d.caixa[1]), d.caixa[1],
                    figura_do_diagrama(imagem, d) if desenhar_diagramas
                    else _figura(imagem, d.caixa, RECORTE_PEDIDO))
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
                       camada: str = "auto", opcoes: Optional[Opcoes] = None,
                       relatorio: Optional[Relatorio] = None) -> List[PaginaExtraida]:
    """
    As páginas reconhecidas do projeto, as de `indices` ou todas.

    Com `camada="auto"`, a página cuja camada de texto o `core.pdf_nativo` aceita
    sai dela, e as outras dos boxes, com a `Estrutura` do Documento de cada uma (§12.1:
    as funções das áreas, os estilos, o parágrafo e o hífen decididos). A regra das
    margens corridas só adivinha nas páginas cujas áreas não dizem cabeçalho nem
    rodapé. Depois, as duas passadas de livro, sobre as páginas dos dois caminhos: o
    parágrafo que a paginação partiu volta a ser um, e o diagrama sem lado lido ganha o
    do lance antes dele, conferido no tabuleiro e no lance seguinte. O `relatorio`, se
    vier, recebe o que saiu e o que ficou de fora (§12.2).
    """
    from core import pdf_nativo

    from abbychess.modelo import VERIFICADA

    opcoes = opcoes or Opcoes()
    relatorio = relatorio if relatorio is not None else Relatorio()
    if camada not in CAMADA:
        raise ValueError(f"camada inválida: {camada!r} (use um de {CAMADA})")
    lidas = set(projeto.paginas_lidas())
    alvo = sorted(lidas if indices is None else lidas.intersection(indices))
    estados = {i: r.get("estado") for i, r in projeto.resumo_do_livro().items()}
    if opcoes.so_verificadas:
        alvo = [i for i in alvo if estados.get(i) == VERIFICADA]
    if not alvo:
        raise NadaParaExportar("Nenhuma página reconhecida para exportar."
                               if not opcoes.so_verificadas else
                               "Nenhuma página verificada para exportar.")
    nativas = paginas_da_camada(projeto, alvo) if camada == "auto" else {}
    pelos_boxes = [i for i in alvo if i not in nativas]
    lidos, estruturas = {}, {}
    for i in pelos_boxes:
        lidos[i], estruturas[i] = Estrutura.da_pagina(projeto.carregar_modelo(i))
    # A regra das margens corridas olha o livro inteiro, como sempre (o título corrido das
    # pares casa com o das ímpares); só não tira o que o usuário marcou como texto. As
    # mesmas margens dão o número impresso de cada página (os rótulos e os links do EPUB).
    funcoes, margens = _funcoes_das_margens(
        {i: (lidos[i], _altura_da_pagina(projeto, i)) for i in pelos_boxes})
    tirar = {} if opcoes.manter_margens else {
        i: set(margens[i].poeira) | set(funcoes[i]) for i in pelos_boxes}
    relatorio.numeros_impressos = numeros_impressos(
        {i: (lidos[i], estruturas[i]) for i in pelos_boxes}, funcoes, alvo)
    paginas = []
    for feitas, indice in enumerate(alvo, start=1):
        if indice in nativas:
            paginas.append(nativas[indice])
        else:
            tabuleiros = projeto.carregar_tabuleiros(indice)
            imagem = fonte.pagina(indice) if fonte is not None and tabuleiros else None
            fora = {k for k in tirar.get(indice, set())
                    if id(lidos[indice][k]) not in estruturas[indice].protegidos}
            texto = [b for k, b in enumerate(lidos[indice]) if k not in fora]
            _margens_no_relatorio(relatorio, indice, lidos[indice], fora, estruturas[indice],
                                  opcoes.manter_margens)
            paginas.append(pagina_extraida(indice, texto, tabuleiros, imagem,
                                           projeto.carregar_diagramas(indice),
                                           estrutura=estruturas[indice],
                                           manter_margens=opcoes.manter_margens,
                                           desenhar_diagramas=opcoes.desenhar_diagramas))
        if progresso:
            progresso(feitas, len(alvo))
    pdf_nativo.juntar_entre_paginas(paginas)
    pdf_nativo.lados_pelos_lances(paginas)
    _paginas_no_relatorio(relatorio, projeto, paginas, estados, nativas)
    return paginas


#: Quantas páginas precisam concordar no deslocamento para o número impresso valer.
CONCORDANCIA_DOS_NUMEROS = 2


def numeros_impressos(paginas: Dict[int, Tuple[Sequence[BoxEntry], "Estrutura"]],
                      funcoes: Dict[int, dict],
                      todas: Optional[Iterable[int]] = None) -> Dict[int, int]:
    """`{índice da página: número impresso}`, pelos números das margens.

    Os candidatos são os números nas linhas de margem: as que a regra das margens achou
    (`funcoes`, índice do box -> função) e as das áreas de cabeçalho, rodapé e número de
    página da `Estrutura`. Cada número dá um **deslocamento** (número − índice); cada página
    fica com o seu deslocamento mais votado no livro (o OCR erra números, "2l", e um
    cabeçalho tem outros, "Problema 41"). A paginação vale **por trechos**: páginas
    seguidas com o mesmo deslocamento, ao menos `CONCORDANCIA_DOS_NUMEROS`, formam um
    trecho, e cada página das pedidas (`todas`, ou as de `paginas`) recebe o do último
    trecho que começa nela ou antes (o encarte de fotos que o livro não numera muda o
    deslocamento dali em diante). Número ≤ 0 não sai. Sem trecho, `{}`."""
    from collections import Counter

    por_pagina: Dict[int, set] = {}
    for indice, (boxes, estrutura) in paginas.items():
        das_margens = funcoes.get(indice, {})
        margem = [b for k, b in enumerate(boxes) if k in das_margens
                  or estrutura.funcao(b) in FUNCOES_DE_MARGEM]
        vistos = set()
        for linha in _linhas(margem, _Leitura()) if margem else []:
            for numero in _NUMERO_DE_PAGINA.findall(linha.texto):
                vistos.add(int(numero) - indice)
        if vistos:
            por_pagina[indice] = vistos
    votos: Counter = Counter(d for vistos in por_pagina.values() for d in vistos)
    escolhido = {i: max(sorted(v), key=lambda d: votos[d]) for i, v in por_pagina.items()}
    trechos: List[Tuple[int, int]] = []           # (primeira página, deslocamento)
    corrida: List[int] = []

    def fechar() -> None:
        if len(corrida) >= CONCORDANCIA_DOS_NUMEROS:
            trechos.append((corrida[0], escolhido[corrida[0]]))

    for i in sorted(escolhido):
        if corrida and escolhido[i] != escolhido[corrida[-1]]:
            fechar()
            corrida = []
        corrida.append(i)
    fechar()
    if not trechos:
        return {}
    saida = {}
    for i in sorted(todas if todas is not None else paginas):
        deslocamento = trechos[0][1]
        for comeco, d in trechos:
            if comeco <= i:
                deslocamento = d
        if i + deslocamento >= 1:
            saida[i] = i + deslocamento
    return saida


def _funcoes_dos_candidatos(paginas: Dict[int, Tuple[Sequence[BoxEntry], int]]) -> Dict[int, dict]:
    """As linhas candidatas a margem de cada página (posição, vão e tamanho), sem a
    comparação entre páginas de `_funcoes_das_margens`: para achar o número impresso basta
    o número delas, e a comparação custa n² no livro."""
    saida = {}
    for i, (boxes, altura) in paginas.items():
        margem = _margem_da_pagina(boxes, altura)
        saida[i] = {k: lugar for linha, lugar in margem.candidatos for k in linha.indices}
    return saida


def titulos_das_paginas(projeto: ProjetoDeLivro, indices: Sequence[int],
                        estruturas: Optional[dict] = None) -> List[Tuple[int, str]]:
    """`[(índice da página, título)]` das áreas de título do Documento, na ordem do livro:
    os marcadores do PDF pesquisável (§12.1). `estruturas` (índice -> `Estrutura.da_pagina`)
    poupa carregar os modelos de novo."""
    saida = []
    for indice in indices:
        entries, estrutura = (estruturas[indice] if estruturas is not None
                              else Estrutura.da_pagina(projeto.carregar_modelo(indice)))
        do_titulo = [b for b in entries if estrutura.funcao(b) == "titulo"]
        if not do_titulo:
            continue
        for _trecho, paragrafo in _paragrafos_por_trecho(do_titulo, (), _Leitura(), estrutura):
            if paragrafo.titulo and paragrafo.texto.strip():
                saida.append((indice, paragrafo.texto.strip()))
    return saida


def _margens_no_relatorio(relatorio: Relatorio, indice: int, boxes: Sequence[BoxEntry],
                          adivinhados: set, estrutura: Estrutura, manter: bool) -> None:
    """As linhas de margem que saíram da página: as adivinhadas e as das áreas."""
    if manter:
        return
    tirados = [b for k, b in enumerate(boxes)
               if k in adivinhados or estrutura.funcao(b) in FUNCOES_DE_MARGEM]
    if tirados:
        textos = [ln.texto for ln in _linhas(tirados, _Leitura())]
        relatorio.margens.setdefault(indice, []).extend(textos)


def _paginas_no_relatorio(relatorio: Relatorio, projeto: ProjetoDeLivro,
                          paginas: Sequence[PaginaExtraida], estados: dict,
                          nativas: dict) -> None:
    from abbychess.modelo import VERIFICADA

    resumo = projeto.resumo_do_livro()
    for pagina in paginas:
        i = pagina.numero
        relatorio.paginas.append(i)
        relatorio.caracteres += pagina.caracteres
        if i in nativas:
            relatorio.da_camada.append(i)
        if estados.get(i) != VERIFICADA:
            relatorio.nao_verificadas.append(i)
        pendentes = resumo.get(i, {}).get("pendentes")
        if pendentes:
            relatorio.pendentes[i] = int(pendentes)
        for bloco in pagina.blocos:
            if isinstance(bloco, Paragrafo) and bloco.titulo and bloco.nivel == 1:
                relatorio.titulos.append((i, bloco.texto))
            elif isinstance(bloco, Figura):
                if bloco.origem == "render":
                    relatorio.desenhados += 1
                else:
                    relatorio.recortados.append((i, bloco.aviso or "recorte da página"))


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

    # A posição no livro -> a página do PDF (§12.4): a camada só vale na página do livro sem
    # quadro, giro nem ângulo à mão (as inseridas, cortadas e giradas saem dos boxes), e é
    # pedida em trechos seguidos no livro e no PDF (`sequencia.trechos_do_pdf`): o core junta
    # o parágrafo de uma página com o da seguinte do pedido.
    trechos = sq.trechos_do_pdf(projeto.sequencia, indices)
    if not trechos:
        return {}
    idioma = idioma_do_livro(projeto)
    paginas = {}
    for trecho in trechos:
        do_pdf = dict(trecho)
        try:
            extracao = pdf_nativo.extrair(str(projeto.fonte), sorted(do_pdf), idioma=idioma)
        except Exception as erro:  # noqa: BLE001 — o livro sai dos boxes, e não falha
            log.warning("A camada de texto do PDF não foi lida (%s: %s); as páginas saem dos "
                        "boxes.", type(erro).__name__, erro)
            return {}
        for pagina in extracao.paginas:
            posicao = do_pdf.get(pagina.numero)
            if posicao is None:
                continue
            pagina.numero = posicao         # o número que a exportação mostra é o do livro
            _lado_da_revisao(pagina, projeto.carregar_diagramas(posicao))
            paginas[posicao] = pagina
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
    """A altura da página lida, em pixels a 300 dpi, sem renderizá-la: a do PDF da entrada,
    na página do livro sem geometria (§12.4); a do quadro girado, nas outras (o tamanho da
    fonte gravado na entrada, ou o da página inserida)."""
    entrada = projeto.sequencia.entrada_em(indice)
    if not entrada.do_livro_sem_geometria:
        from abbychess import geometria as geo

        tamanho = entrada.tamanho or pg.fonte_do_projeto(projeto).tamanho_da_fonte(entrada)
        return geo.tamanho_da_imagem(entrada.geometria, tamanho)[1]
    if projeto.fonte_e_pdf:
        import fitz

        with fitz.open(projeto.fonte) as doc:
            return round(doc[entrada.pagina].rect.height * DPI_DA_LEITURA / 72)
    with Image.open(projeto.fonte) as imagem:
        return imagem.height


def exportar_docx(paginas: Sequence[PaginaExtraida], caminho: str | Path, *,
                  titulo: str, autor: str = "", idioma: str = "pt-BR",
                  metadados=None, relatorio: Optional["Relatorio"] = None) -> Path:
    """O DOCX pelo escritor próprio (`abbychess.escritor_docx`): títulos nos estilos de
    título, estilos, diagramas com o texto alternativo, marcadores de página e hiperlinks
    internos, metadados. Depois de gravar, `escritor_docx.conferir` lê o arquivo; o que
    ele acusar vai ao `relatorio`."""
    from abbychess import epub
    from abbychess import escritor_docx

    metadados = metadados or epub.Metadados(titulo=titulo, idioma=idioma,
                                            autores=(autor,) if autor else ())
    numeros = relatorio.numeros_impressos if relatorio is not None else None
    escrito = escritor_docx.escrever(paginas, caminho, metadados, numeros=numeros)
    problemas = escritor_docx.conferir(caminho)
    for problema in problemas:
        log.warning("DOCX %s: %s", caminho, problema)
    if relatorio is not None:
        relatorio.links = escrito.links
        relatorio.problemas_do_arquivo = problemas
    return Path(caminho)


def exportar_epub(paginas: Sequence[PaginaExtraida], caminho: str | Path, *,
                  titulo: str, autor: str = "", idioma: str = "pt-BR",
                  metadados=None, relatorio: Optional["Relatorio"] = None) -> Path:
    """O EPUB pelo escritor próprio (`abbychess.epub`): capítulos, sumário pelos títulos,
    lista de páginas, marcos, metadados e a acessibilidade do que foi escrito. Depois de
    gravar, `epub.conferir` lê o arquivo; o que ele acusar vai ao `relatorio`."""
    from abbychess import epub

    metadados = metadados or epub.Metadados(titulo=titulo, idioma=idioma,
                                            autores=(autor,) if autor else ())
    numeros = relatorio.numeros_impressos if relatorio is not None else None
    escrito = epub.escrever(paginas, caminho, metadados, numeros=numeros)
    problemas = epub.conferir(caminho)
    for problema in problemas:
        log.warning("EPUB %s: %s", caminho, problema)
    if relatorio is not None:
        relatorio.capitulos = escrito.capitulos
        relatorio.imagens_reutilizadas = escrito.reutilizadas
        relatorio.problemas_do_arquivo = problemas
        relatorio.links = escrito.links
    return Path(caminho)


#: O arquivo, na pasta do projeto, com os metadados do livro exportado (§12.1).
ARQUIVO_DE_METADADOS = "metadados.json"


#: Os campos de `metadados.json`, na ordem do formulário (§12.1).
CAMPOS_DE_METADADOS = ("titulo", "autores", "editora", "data", "assuntos", "direitos",
                       "identificador", "fonte", "capa")
#: Os campos que são listas.
LISTAS_DE_METADADOS = ("autores", "assuntos")
#: A data que o EPUB aceita (`dc:date`).
DATA_DOS_METADADOS = re.compile(r"\d{4}(-\d{2}(-\d{2})?)?")
#: O nome da capa copiada para a pasta do projeto (a extensão é a da origem).
NOME_DA_CAPA = "capa"


def ler_metadados(projeto: ProjetoDeLivro) -> dict:
    """O `metadados.json` do projeto como está, ou `{}` (sem arquivo, ou ilegível: aviso no
    log, e a exportação segue só com o título)."""
    import json

    arquivo = Path(projeto.pasta) / ARQUIVO_DE_METADADOS
    if not arquivo.is_file():
        return {}
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        log.warning("%s ilegível (%s): o EPUB sai só com o título.", arquivo, erro)
        return {}
    return dados if isinstance(dados, dict) else {}


def normalizar_metadados(dados: dict) -> dict:
    """Os campos conhecidos, sem espaços nas pontas, as listas como listas (um texto com
    `;` vira lista) e sem os vazios. Levanta `ValueError` com a data fora de AAAA-MM-DD."""
    saida: dict = {}
    for campo in CAMPOS_DE_METADADOS:
        valor = dados.get(campo)
        if valor is None:
            continue
        if campo in LISTAS_DE_METADADOS:
            if isinstance(valor, str):
                itens = valor.split(";")
            elif isinstance(valor, (list, tuple)):
                itens = list(valor)
            else:                               # um número, um objeto: vira um item
                itens = [valor]
            lista = [str(v).strip() for v in itens if v is not None and str(v).strip()]
            if lista:
                saida[campo] = lista
        elif str(valor).strip():
            saida[campo] = str(valor).strip()
    if "data" in saida and not DATA_DOS_METADADOS.fullmatch(saida["data"]):
        raise ValueError(f"A data {saida['data']!r} deve ser AAAA, AAAA-MM ou AAAA-MM-DD.")
    return saida


def gravar_metadados(projeto: ProjetoDeLivro, dados: dict,
                     capa: Optional[Path] = None) -> dict:
    """Grava o `metadados.json` (atômico, como todo arquivo do projeto) e devolve o que foi
    gravado. `capa` é uma imagem escolhida fora do projeto: é copiada para a pasta dele
    (`capa.<ext>`) e o campo passa a apontá-la. Recusa (`SomenteLeitura`) em projeto só
    de leitura."""
    from abbychess import gravacao as gv

    novos = normalizar_metadados(dados)
    pasta = Path(projeto.pasta)
    # As chaves que o formulário não conhece (escritas à mão) ficam; as dele valem o que ele
    # disse, e a vazia sai. O `autor` singular de antes dá lugar a `autores`.
    gravado = {k: v for k, v in ler_metadados(projeto).items()
               if k not in CAMPOS_DE_METADADOS and k != "autor"}
    gravado.update(novos)
    if capa is not None:
        capa = Path(capa)
        conteudo = capa.read_bytes()
        _conferir_capa(conteudo)
        extensao = capa.suffix.lower() if capa.suffix.lower() in EXTENSOES_DA_CAPA else ".png"
        nome = f"{NOME_DA_CAPA}{extensao}"
        destino = pasta / nome
        if not destino.exists() or destino.resolve() != capa.resolve():
            gv.gravar_bytes(destino, conteudo)
        for velha in EXTENSOES_DA_CAPA:          # a capa de outra extensão não fica órfã
            if velha != extensao and (pasta / f"{NOME_DA_CAPA}{velha}").is_file():
                gv.apagar(pasta / f"{NOME_DA_CAPA}{velha}")
        gravado["capa"] = nome
    gv.gravar_json(pasta / ARQUIVO_DE_METADADOS, gravado)
    return gravado


#: As extensões de capa que o EPUB leva, e o tamanho máximo (a cópia é na hora de exportar).
EXTENSOES_DA_CAPA = (".png", ".jpg", ".jpeg", ".gif", ".webp")
TAMANHO_MAXIMO_DA_CAPA = 20 * 1024 * 1024


def _conferir_capa(conteudo: bytes) -> None:
    """Levanta `ValueError` se a capa não for PNG, JPEG, GIF ou WebP, ou passar do limite."""
    if len(conteudo) > TAMANHO_MAXIMO_DA_CAPA:
        raise ValueError(f"A capa tem {len(conteudo) // (1024 * 1024)} MB; o limite é "
                         f"{TAMANHO_MAXIMO_DA_CAPA // (1024 * 1024)} MB.")
    assinaturas = (conteudo[:8] == b"\x89PNG\r\n\x1a\n", conteudo[:3] == b"\xff\xd8\xff",
                   conteudo[:6] in (b"GIF87a", b"GIF89a"),
                   conteudo[:4] == b"RIFF" and conteudo[8:12] == b"WEBP")
    if not any(assinaturas):
        raise ValueError("A capa não é uma imagem PNG, JPEG, GIF ou WebP.")


def metadados_do_projeto(projeto: ProjetoDeLivro, idioma: str, dados: Optional[dict] = None):
    """Os metadados do EPUB: o título e o idioma do projeto e o que `metadados.json` disser
    (`titulo`, `autores`, `editora`, `data`, `assuntos`, `direitos`, `identificador`,
    `fonte` e `capa`, o caminho de uma imagem relativo à pasta do projeto). `dados` troca o
    arquivo (o formulário de um projeto só de leitura). Sem nada, só o título e o idioma."""
    from abbychess import epub

    dados = ler_metadados(projeto) if dados is None else dados
    if not isinstance(dados, dict):
        dados = {}

    def texto(chave: str) -> str:
        valor = dados.get(chave)
        return str(valor).strip() if valor is not None else ""

    def lista(valor) -> Tuple[str, ...]:
        if isinstance(valor, str):
            return (valor.strip(),) if valor.strip() else ()
        if not isinstance(valor, (list, tuple)):
            return ()
        return tuple(str(v).strip() for v in valor if v is not None and str(v).strip())

    capa = None
    if texto("capa"):
        pasta = Path(projeto.pasta).resolve()
        arquivo_da_capa = (pasta / texto("capa")).resolve()
        if pasta != arquivo_da_capa and pasta not in arquivo_da_capa.parents:
            log.warning("A capa %s está fora da pasta do projeto: fica de fora.", texto("capa"))
        else:
            try:
                capa = arquivo_da_capa.read_bytes()
            except OSError as erro:
                log.warning("A capa %s não foi lida (%s).", texto("capa"), erro)
    return epub.Metadados(
        titulo=texto("titulo") or projeto.dados.nome, idioma=idioma,
        autores=lista(dados.get("autores") or dados.get("autor")),
        editora=texto("editora"), data=texto("data"), assuntos=lista(dados.get("assuntos")),
        direitos=texto("direitos"), identificador=texto("identificador"),
        fonte=texto("fonte"), capa=capa)


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

    lidas = set(projeto.paginas_lidas())
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
               if not projeto.fonte_e_pdf or not e.do_livro_sem_geometria}
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
            log.warning("os marcadores e os rótulos do PDF não saíram (%s)", erro)
        try:
            doc.subset_fonts()
        except Exception as erro:  # sem subset o arquivo só fica maior
            log.info("as fontes do PDF não foram reduzidas (%s)", erro)
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
        if projeto.fonte_e_pdf:
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
    temporario = caminho.with_name(caminho.name + ".tmp")
    doc.save(str(temporario), garbage=3, deflate=True)
    temporario.replace(caminho)


# ----------------------------------------------------------------------
# Uma porta só
# ----------------------------------------------------------------------

def _gravar_texto(caminho: Path, texto: str) -> Path:
    """Grava ao lado e troca no fim: uma exportação que falha não estraga a anterior."""
    import tempfile

    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(prefix=f".{caminho.stem}-", suffix=".tmp",
                                      dir=caminho.parent)
    try:
        arquivo = os.fdopen(fd, "w", encoding="utf-8", newline="\n")
    except BaseException:
        os.close(fd)
        Path(temporario).unlink(missing_ok=True)
        raise
    try:
        with arquivo:
            arquivo.write(texto)
        os.chmod(temporario, 0o644)             # o mkstemp nasce 0600
        os.replace(temporario, caminho)
    except BaseException:
        Path(temporario).unlink(missing_ok=True)
        raise
    return caminho


def _linha_do_diagrama(figura: Figura) -> str:
    """O diagrama no texto puro: o FEN e o lado dito, ou o recorte e o motivo."""
    from core import lado_a_jogar

    if figura.fen:
        lado = lado_a_jogar.marca(figura.lado_a_jogar, figura.lado_origem or "")
        pendente = f"; {lado_a_jogar.NAO_REVISADO}" if figura.revisao_pendente else ""
        return f"[Diagrama: {figura.fen} — {lado}{pendente}]"
    return f"[Diagrama: {figura.aviso or 'recorte da página'}]"


def texto_do_livro(paginas: Sequence[PaginaExtraida], *, marcas_de_pagina: bool = False) -> str:
    """O TXT (§12.1): um parágrafo por bloco, linha em branco entre eles, o título como
    está, o diagrama numa linha com o FEN. Cabeçalho corrido nunca entra por acidente: o
    texto é o mesmo das páginas exportadas, que já saíram sem as margens."""
    blocos = []
    for pagina in paginas:
        if marcas_de_pagina:
            blocos.append(f"[p. {pagina.numero + 1}]")
        for bloco in pagina.blocos:
            if isinstance(bloco, Figura):
                blocos.append(_linha_do_diagrama(bloco))
            elif isinstance(bloco, Paragrafo) and bloco.texto.strip():
                blocos.append(bloco.texto.strip())
    return "\n\n".join(blocos) + ("\n" if blocos else "")


def pgn_do_livro(projeto: ProjetoDeLivro, indices: Optional[Iterable[int]] = None,
                 relatorio: Optional[Relatorio] = None,
                 opcoes: Optional[Opcoes] = None) -> str:
    """O PGN (§10, §12.1): uma partida por diagrama, da posição dele (`SetUp`/`FEN`) e com
    os lances do texto que passaram na validação, com a página e o número do diagrama.

    Entram os diagramas conferidos (a posição é a de quem conferiu; os lances, só os que
    passaram) e os confiáveis pelos lances, sempre com a posição legal; os outros vão ao
    `relatorio` com o motivo, para serem conferidos e exportados de novo."""
    from abbychess import lances as lc
    from abbychess.diagramas import em_ordem
    from abbychess.modelo import VERIFICADA

    relatorio = relatorio if relatorio is not None else Relatorio()
    lidas = set(projeto.paginas_lidas())
    alvo = sorted(lidas if indices is None else lidas.intersection(indices))
    if opcoes is not None and opcoes.so_verificadas:
        estados = {i: r.get("estado") for i, r in projeto.resumo_do_livro().items()}
        alvo = [i for i in alvo if estados.get(i) == VERIFICADA]
    if not alvo:
        raise NadaParaExportar("Nenhuma página reconhecida para exportar.")
    partidas = []
    for i in alvo:
        modelo = projeto.carregar_modelo(i)
        if modelo is None or not modelo.tabuleiros:
            continue
        relatorio.paginas.append(i)
        diagramas = para_caixas(em_ordem(modelo.tabuleiros), modelo.diagramas)
        for numero, d in enumerate(diagramas, start=1):
            motivo = _fora_do_pgn(d)
            if motivo:
                relatorio.fora_do_pgn.append((i, numero, motivo))
                continue
            try:
                partidas.append(lc.pgn_do_diagrama(d, {
                    "Event": projeto.dados.nome, "Site": "?", "Round": "?",
                    "Annotator": "AbbyChessCraft",
                    "Page": str(i + 1), "Diagram": str(numero)}))
            except ValueError as erro:          # uma posição que o python-chess recusa
                relatorio.fora_do_pgn.append((i, numero, f"o PGN não saiu ({erro})"))
                continue
            relatorio.no_pgn += 1
    return "\n\n".join(partidas) + ("\n" if partidas else "")


def _fora_do_pgn(d: DiagramaLido) -> str:
    """Por que o diagrama não entra no PGN; vazio se entra."""
    import chess

    if not d.lido:
        return d.erro or "não lido"
    try:
        legal = chess.Board(d.fen).is_valid()
    except ValueError:
        legal = False
    if not legal:
        return "a posição não é legal"
    if d.conferido:
        return ""
    if d.validacao is not None and not d.validacao.confiavel:
        return d.validacao.aviso
    if d.validacao is not None and d.validacao.confiavel:
        return ""
    return "nem conferido nem confiável pelos lances"


def _mesmo_arquivo(a: Path, b: Path) -> bool:
    """Os dois caminhos são o mesmo arquivo (maiúsculas, nomes 8.3, links e hardlinks)."""
    try:
        return a.exists() and b.exists() and os.path.samefile(a, b)
    except OSError:
        return False


def formato_do_caminho(caminho: str | Path) -> str:
    formato = Path(caminho).suffix.lower().lstrip(".")
    if formato not in FORMATOS:
        raise ValueError(f"Formato {formato or '(sem extensão)'} não suportado; "
                         f"use {', '.join(FORMATOS)}.")
    return formato


def previa(projeto: ProjetoDeLivro, formato: str, indices: Optional[Iterable[int]] = None, *,
           opcoes: Optional[Opcoes] = None, metadados: Optional[dict] = None,
           progresso: Optional[Progresso] = None) -> Tuple[str, Relatorio]:
    """A pré-visualização (§12.2): `(html, relatório)` do que a exportação em `formato`
    escreveria, pelo mesmo caminho e com as mesmas opções, sem gravar nada. O PDF
    pesquisável não tem prévia: ele guarda as páginas como são."""
    from abbychess import previa as pv

    if formato not in FORMATOS or formato == "pdf":
        raise ValueError(f"Sem pré-visualização para {formato.upper()}.")
    opcoes = opcoes or Opcoes()
    relatorio = Relatorio(formato=formato)
    idioma = idioma_do_arquivo(idioma_do_livro(projeto))
    titulo = metadados_do_projeto(projeto, idioma, metadados).titulo
    if formato == "pgn":
        texto = pgn_do_livro(projeto, indices, relatorio, opcoes)
        return pv.html_do_texto(texto, relatorio.texto().splitlines(), titulo, idioma), relatorio
    fonte = pg.fonte_do_projeto(projeto)
    paginas = paginas_do_projeto(projeto, fonte, indices, progresso=progresso, opcoes=opcoes,
                                 relatorio=relatorio)
    linhas = relatorio.texto().splitlines()
    if formato == "txt":                        # o TXT como ele sai, não o livro formatado
        texto = texto_do_livro(paginas[:pv.LIMITE], marcas_de_pagina=opcoes.marcas_de_pagina)
        if len(paginas) > pv.LIMITE:
            texto += f"\n… e mais {len(paginas) - pv.LIMITE} página(s), que a exportação inclui.\n"
        return pv.html_do_texto(texto, linhas, titulo, idioma), relatorio
    return pv.html_do_livro(paginas, linhas, titulo, idioma), relatorio


def exportar(projeto: ProjetoDeLivro, caminho: str | Path,
             indices: Optional[Iterable[int]] = None, *,
             progresso: Optional[Progresso] = None, opcoes: Optional[Opcoes] = None) -> str:
    """Exporta no formato da extensão de `caminho` e devolve o resumo para a tela."""
    return exportar_com_relatorio(projeto, caminho, indices, progresso=progresso,
                                  opcoes=opcoes)[0]


def exportar_com_relatorio(projeto: ProjetoDeLivro, caminho: str | Path,
                           indices: Optional[Iterable[int]] = None, *,
                           progresso: Optional[Progresso] = None,
                           opcoes: Optional[Opcoes] = None,
                           metadados: Optional[dict] = None) -> Tuple[str, Relatorio]:
    """Exporta e devolve `(resumo, relatório)`: o resumo vai à barra, o relatório aos
    Resultados (§12.2). `metadados` troca o `metadados.json` (o formulário não gravado)."""
    formato = formato_do_caminho(caminho)
    caminho = Path(caminho)
    if _mesmo_arquivo(caminho, Path(projeto.fonte)):
        raise ValueError("O destino é o próprio arquivo de origem do livro: escolha outro nome.")
    opcoes = opcoes or Opcoes()
    relatorio = Relatorio(formato=formato)
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
        if resumo.marcadores:
            partes.append(f"{resumo.marcadores} marcador(es) pelos títulos")
        if resumo.marcadores_do_original:
            partes.append(f"o sumário do PDF original ficou ({resumo.marcadores_do_original} "
                          "marcadores)")
        if resumo.rotulos:
            partes.append("páginas com o número impresso como rótulo")
        relatorio.marcadores = resumo.marcadores
        relatorio.resumo_do_pdf = "; ".join(partes) + "."
        return relatorio.resumo_do_pdf, relatorio
    if formato == "pgn":
        _gravar_texto(caminho, pgn_do_livro(projeto, indices, relatorio, opcoes))
        return relatorio.resumo(), relatorio
    fonte = pg.fonte_do_projeto(projeto)
    paginas = paginas_do_projeto(projeto, fonte, indices, progresso=progresso,
                                 opcoes=opcoes, relatorio=relatorio)
    idioma = idioma_do_arquivo(idioma_do_livro(projeto))
    if formato == "txt":
        _gravar_texto(caminho, texto_do_livro(paginas, marcas_de_pagina=opcoes.marcas_de_pagina))
        return relatorio.resumo(), relatorio
    meta = metadados_do_projeto(projeto, idioma, metadados)
    if formato == "docx":
        exportar_docx(paginas, caminho, titulo=meta.titulo, idioma=idioma, metadados=meta,
                      relatorio=relatorio)
    else:
        exportar_epub(paginas, caminho, titulo=meta.titulo, idioma=idioma, metadados=meta,
                      relatorio=relatorio)
    return relatorio.resumo(), relatorio
