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
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from PIL import Image

from core.box_model import BoxEntry
from core.pagina import Figura, PaginaExtraida, Paragrafo

from abbychess import gravacao as gv
from abbychess import links_de_analise
from abbychess import pagina as pg
from abbychess import sequencia as sq
from abbychess.diagramas import DiagramaLido, para_caixas
from abbychess.layout import OrdemDeLeitura
from abbychess.projeto import ProjetoDeLivro
from abbychess.metadados import metadados_do_projeto
from abbychess.montagem import (
    DPI_DA_LEITURA, Estrutura, FUNCOES_DE_MARGEM, _Linha, _juntar_entre_paginas, _linhas,
    _quebras_da_camada, pagina_extraida, palavras, titulos_das_paginas)

log = logging.getLogger(__name__)


FORMATOS = ("pdf", "docx", "epub", "txt", "pgn")

#: Quando ler a página da camada de texto do PDF: "auto" (quando a régua do
#: `core.pdf_nativo` aceita a página) ou "nunca" (sempre dos boxes do projeto).
CAMADA = ("auto", "nunca")

#: O idioma do arquivo exportado (`dc:language`, `xml:lang`) pelo do livro.
IDIOMAS_DO_ARQUIVO = {"pt": "pt-BR", "en": "en", "es": "es", "de": "de", "fr": "fr"}


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
    #: As quebras de linha e os hífens do impresso ficam: cada linha impressa acaba numa
    #: quebra dentro do parágrafo (`\n` no texto; `<br/>` no EPUB, `w:br` no DOCX). Nas
    #: páginas do OCR, o parágrafo que a página partiu não se junta com o da seguinte; na
    #: camada nativa o core já o juntou ao ler, e ele fica junto, com a quebra no lugar.
    manter_quebras: bool = False
    #: No DOCX, os glifos de baixa confiança (os que a fila de revisão pede, §8) com o
    #: realce amarelo do Word, para quem revisa no editor de texto achar onde olhar.
    realcar_duvidosos: bool = False
    #: No EPUB, no DOCX e na prévia, o link que abre cada diagrama lido no tabuleiro de
    #: análise: `nenhum`, `lichess` ou `chesscom` (`links_de_analise.SITES`).
    links_de_analise: str = "nenhum"
    #: As páginas `(primeira, última)`, índices a partir de 0, as duas incluídas; `None`, o
    #: livro todo. Não é lembrada entre exportações.
    intervalo: Optional[Tuple[int, int]] = None

    def __post_init__(self) -> None:
        links_de_analise.validar(self.links_de_analise)
        if self.intervalo is not None:
            primeira, ultima = self.intervalo
            if not 0 <= primeira <= ultima:
                raise ValueError(f"intervalo inválido: {self.intervalo!r}")

    def indices(self, indices: Optional[Iterable[int]]) -> Optional[Iterable[int]]:
        """Os `indices` pedidos, cortados pelo `intervalo`."""
        if self.intervalo is None:
            return indices
        dentro = range(self.intervalo[0], self.intervalo[1] + 1)
        return dentro if indices is None else [i for i in indices if i in dentro]


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
    #: Página -> as palavras sinalizadas (com glifo de baixa confiança, §8).
    sinalizadas: Dict[int, int] = field(default_factory=dict)
    #: No PGN: (página, número do diagrama, motivo) dos que ficaram de fora, e quantos entraram.
    fora_do_pgn: List[Tuple[int, int, str]] = field(default_factory=list)
    no_pgn: int = 0
    #: No PDF pesquisável, o resumo dele (o relatório por item é dos outros formatos).
    resumo_do_pdf: str = ""
    #: No EPUB: os capítulos, as figuras que reaproveitaram uma imagem igual e o que a
    #: conferência do arquivo escrito acusou (`epub.conferir`).
    capitulos: int = 0
    imagens_reutilizadas: int = 0
    #: No EPUB: os bytes que o PNG otimizado sem perda tirou das imagens.
    bytes_poupados: int = 0
    #: Índice da página -> o número impresso nela (`numeros_impressos`), quando se sabe.
    numeros_impressos: Dict[int, int] = field(default_factory=dict)
    #: No EPUB, as referências a página que viraram link; no PDF, os marcadores.
    links: int = 0
    marcadores: int = 0
    #: No EPUB e no DOCX, os diagramas com link de análise e o site dele (`Opcoes`).
    analises: int = 0
    site_de_analise: str = ""

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
        if self.sinalizadas:
            partes.append(f"{sum(self.sinalizadas.values())} palavra(s) sinalizada(s)")
        if self.capitulos:
            partes.append(f"{self.capitulos} capítulo(s)")
        if self.links:
            partes.append(f"{self.links} referência(s) a página, diagrama ou capítulo com link")
        if self.analises:
            partes.append(f"{self.analises} diagrama(s) com link para o {self.site_de_analise}")
        if self.numeros_impressos and self.formato == "epub":
            primeira = min(self.numeros_impressos)
            partes.append(f"página impressa {self.numeros_impressos[primeira]} na posição "
                          f"{primeira + 1} do PDF")
        if self.imagens_reutilizadas:
            partes.append(f"{self.imagens_reutilizadas} imagem(ns) reaproveitada(s)")
        if self.bytes_poupados >= 1024:
            partes.append(f"imagens {self.bytes_poupados // 1024} KB menores, sem perda")
        return "; ".join(partes) + "."

    def pagina(self, indice: int) -> str:
        """A página do item: "página 25" (a posição no PDF, que o duplo clique em Avisos
        abre), com o número impresso na frente quando difere ("p. 23, página 25")."""
        impresso = self.numeros_impressos.get(indice)
        if impresso is not None and impresso != indice + 1:
            return f"p. {impresso}, página {indice + 1}"
        return f"página {indice + 1}"

    def linhas(self) -> List[str]:
        """O resumo e uma linha por página com o que houve nela (os itens separados por
        ";"): em Avisos, cada linha é um aviso, e o duplo clique abre a página. Uma por
        página, e não por item, para o livro inteiro não lotar os Avisos."""
        itens: Dict[int, List[str]] = {}
        for pagina, titulo in self.titulos:
            itens.setdefault(pagina, []).append(f"título “{titulo}”")
        for pagina, textos in sorted(self.margens.items()):
            for t in textos:
                itens.setdefault(pagina, []).append(f"margem tirada “{t}”")
        for pagina, motivo in self.recortados:
            itens.setdefault(pagina, []).append(f"diagrama como recorte ({motivo})")
        for pagina, numero, motivo in self.fora_do_pgn:
            itens.setdefault(pagina, []).append(f"diagrama {numero} fora do PGN ({motivo})")
        for pagina, n in sorted(self.sinalizadas.items()):
            itens.setdefault(pagina, []).append(f"{n} palavra(s) sinalizada(s)")
        for pagina, n in sorted(self.pendentes.items()):
            if n:
                itens.setdefault(pagina, []).append(f"{n} glifo(s) pendente(s)")
        linhas = [self.resumo()]
        linhas += [f"{self.pagina(p)}: " + "; ".join(itens[p]) for p in sorted(itens)]
        if self.nao_verificadas:
            linhas.append("Páginas não verificadas: "
                          + ", ".join(str(i + 1) for i in self.nao_verificadas))
        return linhas

    def texto(self) -> str:
        """O relatório inteiro, uma linha por item, com a página (para Resultados)."""
        return "\n".join(self.linhas())


# ----------------------------------------------------------------------
# Das páginas gravadas ao intermediário do PyBoxEditor
# ----------------------------------------------------------------------


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
    linhas = _linhas(boxes, OrdemDeLeitura())
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


def margens_da_pagina(boxes: Sequence[BoxEntry], altura: int) -> set:
    """Os índices de `margens_corridas` de uma página só, com os glifos sem leitura: o □ do
    cabeçalho corrido também é cabeçalho. A fila de revisão os manda para o fim (§8.1).

    A regra roda só nos lidos, como na exportação; contar o □ como glifo mudaria as linhas
    dela (um cisco sem leitura logo abaixo do título fecharia o vão que a regra pede). Depois,
    o sem leitura entra quando o centro dele cai na altura de um glifo de margem e na faixa
    dos glifos de margem dessa altura, com a folga de uma altura de cada lado. O sem leitura
    todo dentro da faixa da poeira (`FAIXA_DA_POEIRA`, em cima ou embaixo) também entra: é o
    cisco da borda da digitalização, que nenhuma linha do texto alcança."""
    lidos = [k for k, b in enumerate(boxes) if b.char]
    margem = {lidos[i] for i in margens_corridas({0: ([boxes[k] for k in lidos], altura)})[0]}
    de_margem = list(margem)
    for k, b in enumerate(boxes):
        if b.char:
            continue
        if b.y2 < FAIXA_DA_POEIRA * altura or b.y1 > (1 - FAIXA_DA_POEIRA) * altura:
            margem.add(k)
            continue
        x, y = (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2
        na_altura = [boxes[m] for m in de_margem if boxes[m].y1 <= y <= boxes[m].y2]
        if na_altura:
            folga = max(m.y2 - m.y1 for m in na_altura)
            if min(m.x1 for m in na_altura) - folga <= x <= max(m.x2 for m in na_altura) + folga:
                margem.add(k)
    return margem


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


def _alvo(projeto: ProjetoDeLivro, indices: Optional[Iterable[int]],
          opcoes: Optional[Opcoes]) -> List[int]:
    """As páginas que a exportação leva, em todo formato (SPEC-qualidade Q-E2): as
    reconhecidas de `indices` (ou todas) e, com `so_verificadas`, só as verificadas.
    Nenhuma: `NadaParaExportar`."""
    from abbychess.modelo import VERIFICADA

    lidas = set(projeto.resumo.paginas_lidas())
    alvo = sorted(lidas if indices is None else lidas.intersection(indices))
    so_verificadas = opcoes is not None and opcoes.so_verificadas
    if so_verificadas:
        estados = {i: r.get("estado") for i, r in projeto.resumo.do_livro().items()}
        alvo = [i for i in alvo if estados.get(i) == VERIFICADA]
    if not alvo:
        raise NadaParaExportar("Nenhuma página verificada para exportar." if so_verificadas
                               else "Nenhuma página reconhecida para exportar.")
    return alvo


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

    opcoes = opcoes or Opcoes()
    relatorio = relatorio if relatorio is not None else Relatorio()
    if camada not in CAMADA:
        raise ValueError(f"camada inválida: {camada!r} (use um de {CAMADA})")
    alvo = _alvo(projeto, indices, opcoes)
    estados = {i: r.get("estado") for i, r in projeto.resumo.do_livro().items()}
    nativas = paginas_da_camada(projeto, alvo) if camada == "auto" else {}
    pelos_boxes = [i for i in alvo if i not in nativas]
    lidos, estruturas = {}, {}
    limiares = projeto.dados.limiares         # os duvidosos: o realce e o relatório
    for i in pelos_boxes:
        lidos[i], estruturas[i] = Estrutura.da_pagina(projeto.carregar_modelo(i), limiares)
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
                                           desenhar_diagramas=opcoes.desenhar_diagramas,
                                           manter_quebras=opcoes.manter_quebras))
        if progresso:
            progresso(feitas, len(alvo))
    if opcoes.manter_quebras:
        # A camada nativa já vem refluída: a quebra volta onde cada linha impressa começa.
        for indice in nativas:
            _quebras_da_camada(nativas[indice])
    else:
        _juntar_entre_paginas(paginas)
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
        for linha in _linhas(margem, OrdemDeLeitura()) if margem else []:
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


def _margens_no_relatorio(relatorio: Relatorio, indice: int, boxes: Sequence[BoxEntry],
                          adivinhados: set, estrutura: Estrutura, manter: bool) -> None:
    """As linhas de margem que saíram da página: as adivinhadas e as das áreas."""
    if manter:
        return
    tirados = [b for k, b in enumerate(boxes)
               if k in adivinhados or estrutura.funcao(b) in FUNCOES_DE_MARGEM]
    if tirados:
        textos = [ln.texto for ln in _linhas(tirados, OrdemDeLeitura())]
        relatorio.margens.setdefault(indice, []).extend(textos)


def _paginas_no_relatorio(relatorio: Relatorio, projeto: ProjetoDeLivro,
                          paginas: Sequence[PaginaExtraida], estados: dict,
                          nativas: dict) -> None:
    from abbychess.modelo import VERIFICADA

    resumo = projeto.resumo.do_livro()
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
        # As palavras, não os trechos (`_unir_trechos` junta as vizinhas num trecho só).
        sinalizadas = sum(len(b.texto[a:z].split()) for b in pagina.blocos
                          for a, z in getattr(b, "duvidosos", ()))
        if sinalizadas:
            relatorio.sinalizadas[i] = sinalizadas
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
    if not projeto.origem.e_pdf or not indices:
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
                        "boxes.", type(erro).__name__, erro, exc_info=True)
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
    if projeto.origem.e_pdf:
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
    if projeto.origem.e_pdf:
        import fitz

        with fitz.open(projeto.fonte) as doc:
            return round(doc[entrada.pagina].rect.height * DPI_DA_LEITURA / 72)
    with Image.open(projeto.fonte) as imagem:
        return imagem.height


def exportar_docx(paginas: Sequence[PaginaExtraida], caminho: str | Path, *,
                  titulo: str, autor: str = "", idioma: str = "pt-BR",
                  metadados=None, relatorio: Optional["Relatorio"] = None,
                  quebras: bool = False, realce: bool = False,
                  analise: str = "nenhum") -> Path:
    """O DOCX pelo escritor próprio (`abbychess.escritor_docx`): títulos nos estilos de
    título, estilos, diagramas com o texto alternativo, marcadores de página e hiperlinks
    internos, metadados; com `analise`, o link de análise de cada diagrama lido
    (`Opcoes.links_de_analise`). O escritor confere o arquivo (`escritor_docx.conferir`)
    antes de trocar o anterior, e recusa o que não passa."""
    from abbychess import escritor_docx

    _escrever_formatado(escritor_docx.escrever, paginas, caminho, titulo, autor, idioma,
                        metadados, relatorio, analise, quebras=quebras, realce=realce)
    return Path(caminho)


def _escrever_formatado(escrever, paginas, caminho, titulo: str, autor: str, idioma: str,
                        metadados, relatorio: Optional["Relatorio"], analise: str, **opcoes):
    """Os dois escritores formatados (o DOCX e o EPUB) por um caminho só: os metadados
    (os dados, ou os de padrão pelo título), os números impressos e, no relatório, os links
    e as análises. Devolve o que o escritor contou."""
    from abbychess import epub

    metadados = metadados or epub.Metadados(titulo=titulo, idioma=idioma,
                                            autores=(autor,) if autor else ())
    numeros = relatorio.numeros_impressos if relatorio is not None else None
    escrito = escrever(paginas, caminho, metadados, numeros=numeros, analise=analise, **opcoes)
    if relatorio is not None:
        relatorio.links = escrito.links
        relatorio.analises = escrito.analises
        relatorio.site_de_analise = links_de_analise.NOMES[analise] if escrito.analises else ""
    return escrito


def exportar_epub(paginas: Sequence[PaginaExtraida], caminho: str | Path, *,
                  titulo: str, autor: str = "", idioma: str = "pt-BR",
                  metadados=None, relatorio: Optional["Relatorio"] = None,
                  quebras: bool = False, analise: str = "nenhum") -> Path:
    """O EPUB pelo escritor próprio (`abbychess.epub`): capítulos, sumário pelos títulos,
    lista de páginas, marcos, metadados e a acessibilidade do que foi escrito; com
    `analise`, o link de análise de cada diagrama lido (`Opcoes.links_de_analise`). O
    escritor confere o arquivo (`epub.conferir`) antes de trocar o anterior, e recusa o que
    não passa (SPEC-qualidade Q-E3), como o DOCX."""
    from abbychess import epub

    escrito = _escrever_formatado(epub.escrever, paginas, caminho, titulo, autor, idioma,
                                  metadados, relatorio, analise, quebras=quebras)
    if relatorio is not None:
        relatorio.capitulos = escrito.capitulos
        relatorio.imagens_reutilizadas = escrito.reutilizadas
        relatorio.bytes_poupados = escrito.poupados
    return Path(caminho)


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


# ----------------------------------------------------------------------
# Uma porta só
# ----------------------------------------------------------------------

def _gravar_texto(caminho: Path, texto: str) -> Path:
    """Grava ao lado e troca no fim: uma exportação que falha não estraga a anterior."""
    caminho = Path(caminho)
    gv.gravar_por(caminho, lambda temporario: temporario.write_text(
        texto, encoding="utf-8", newline="\n"))
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

    relatorio = relatorio if relatorio is not None else Relatorio()
    alvo = _alvo(projeto, indices, opcoes)
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
    indices = opcoes.indices(indices)
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
    return (pv.html_do_livro(paginas, linhas, titulo, idioma, quebras=opcoes.manter_quebras,
                             realce=formato == "docx" and opcoes.realcar_duvidosos,
                             analise=opcoes.links_de_analise),
            relatorio)


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
    indices = opcoes.indices(indices)
    relatorio = Relatorio(formato=formato)
    if formato == "pdf":
        resumo = exportar_pdf_pesquisavel(projeto, caminho, _alvo(projeto, indices, opcoes),
                                          progresso=progresso)
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
        texto = pgn_do_livro(projeto, indices, relatorio, opcoes)
        if not texto:
            raise NadaParaExportar("Nenhum diagrama entrou no PGN.\n\n" + relatorio.texto())
        _gravar_texto(caminho, texto)
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
                      relatorio=relatorio, quebras=opcoes.manter_quebras,
                      realce=opcoes.realcar_duvidosos, analise=opcoes.links_de_analise)
    else:
        exportar_epub(paginas, caminho, titulo=meta.titulo, idioma=idioma, metadados=meta,
                      relatorio=relatorio, quebras=opcoes.manter_quebras,
                      analise=opcoes.links_de_analise)
    return relatorio.resumo(), relatorio
