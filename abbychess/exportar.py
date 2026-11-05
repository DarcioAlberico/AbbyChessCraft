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

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

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
    DPI_DA_LEITURA, Estrutura, FUNCOES_DE_MARGEM, _juntar_entre_paginas, _linhas,
    _quebras_da_camada, pagina_extraida)
from abbychess.margens import _funcoes_das_margens, numeros_impressos
from abbychess.pedido import (
    NadaParaExportar, Opcoes, Pedido, Progresso, _alvo)
from abbychess.pdf_pesquisavel import CAMADA, exportar_pdf_pesquisavel

log = logging.getLogger(__name__)


FORMATOS = ("pdf", "docx", "epub", "txt", "pgn")


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
    #: conferência do arquivo escrito acusou (`validacao_do_epub.conferir`).
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
        return "; ".join(self._partes_do_texto() + self._partes_do_arquivo()) + "."

    def _partes_do_texto(self) -> List[str]:
        """O que entrou do livro e o que ficou de fora dele."""
        partes = [f"{len(self.paginas)} página(s), {self.caracteres} caracteres"]
        if self.titulos:
            partes.append(f"{len(self.titulos)} título(s)")
        partes.append(f"{self.desenhados} diagrama(s) desenhado(s) do FEN e "
                      f"{len(self.recortados)} como recorte")
        if self.da_camada:
            partes.append(f"{len(self.da_camada)} página(s) lida(s) da camada de texto do PDF "
                          "(as margens que o core tira delas não são listadas)")
        tiradas = sum(len(v) for v in self.margens.values())
        if tiradas:
            partes.append(f"{tiradas} linha(s) de cabeçalho/rodapé tirada(s)")
        if self.nao_verificadas:
            partes.append(f"{len(self.nao_verificadas)} página(s) não verificada(s)")
        if self.sinalizadas:
            partes.append(f"{sum(self.sinalizadas.values())} palavra(s) sinalizada(s)")
        return partes

    def _partes_do_arquivo(self) -> List[str]:
        """O que o arquivo escrito ganhou: capítulos, links, a paginação e as imagens."""
        partes = []
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
        return partes

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
        itens = self._itens_por_pagina()
        linhas = [self.resumo()]
        linhas += [f"{self.pagina(p)}: " + "; ".join(itens[p]) for p in sorted(itens)]
        if self.nao_verificadas:
            linhas.append("Páginas não verificadas: "
                          + ", ".join(str(i + 1) for i in self.nao_verificadas))
        return linhas

    def _itens_por_pagina(self) -> Dict[int, List[str]]:
        """Página -> os itens dela, na ordem: títulos, margens, recortes, os de fora do PGN,
        as palavras sinalizadas e os glifos pendentes."""
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
        return itens

    def texto(self) -> str:
        """O relatório inteiro, uma linha por item, com a página (para Resultados)."""
        return "\n".join(self.linhas())


# ----------------------------------------------------------------------
# Das páginas gravadas ao intermediário do PyBoxEditor
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
# Cabeçalho e rodapé corridos
# ----------------------------------------------------------------------


def paginas_do_projeto(projeto: ProjetoDeLivro, fonte: Optional[pg.FonteDePaginas],
                       indices: Optional[Iterable[int]] = None, *,
                       progresso: Optional[Progresso] = None,
                       camada: str = "auto", opcoes: Optional[Opcoes] = None,
                       relatorio: Optional[Relatorio] = None,
                       pedido: Optional[Pedido] = None) -> List[PaginaExtraida]:
    """
    As páginas reconhecidas do projeto, as de `indices` ou todas.

    Com `camada="auto"`, a página cuja camada de texto o `core.pdf_nativo` aceita
    sai dela, e as outras dos boxes, com a `Estrutura` do Documento de cada uma (§12.1:
    as funções das áreas, os estilos, o parágrafo e o hífen decididos). A regra das
    margens corridas só adivinha nas páginas cujas áreas não dizem cabeçalho nem
    rodapé. Depois, as duas passadas de livro, sobre as páginas dos dois caminhos: o
    parágrafo que a paginação partiu volta a ser um, e o diagrama sem lado lido ganha o
    do lance antes dele, conferido no tabuleiro e no lance seguinte. O `relatorio`, se
    vier, recebe o que saiu e o que ficou de fora (§12.2). O `pedido` da exportação traz as
    opções, as páginas e o idioma; sem ele, valem os `indices` e as `opcoes`.
    """
    pedido = pedido or Pedido(projeto, opcoes or Opcoes(), indices)
    opcoes = pedido.opcoes
    relatorio = relatorio if relatorio is not None else Relatorio()
    alvo, estados, nativas, pelos_boxes = _caminhos_das_paginas(projeto, pedido, camada)
    lidos, estruturas, tirar = _boxes_e_margens(projeto, pelos_boxes, alvo, opcoes, relatorio)
    paginas = []
    for feitas, indice in enumerate(alvo, start=1):
        if indice in nativas:
            paginas.append(nativas[indice])
        else:
            paginas.append(_pagina_pelos_boxes(projeto, fonte, indice, lidos[indice],
                                               estruturas[indice], tirar.get(indice, set()),
                                               opcoes, relatorio))
        if progresso:
            progresso(feitas, len(alvo))
    _passadas_do_livro(paginas, nativas, opcoes)
    _paginas_no_relatorio(relatorio, projeto, paginas, estados, nativas)
    return paginas


def _caminhos_das_paginas(projeto: ProjetoDeLivro, pedido: Pedido, camada: str
                          ) -> Tuple[List[int], dict, Dict[int, PaginaExtraida], List[int]]:
    """(as páginas do pedido, o estado de cada uma, as que saem da camada de texto, as que
    saem dos boxes)."""
    if camada not in CAMADA:
        raise ValueError(f"camada inválida: {camada!r} (use um de {CAMADA})")
    alvo = pedido.alvo()
    estados = {i: r.get("estado") for i, r in projeto.resumo.do_livro().items()}
    nativas = paginas_da_camada(projeto, alvo, pedido) if camada == "auto" else {}
    return alvo, estados, nativas, [i for i in alvo if i not in nativas]


def _boxes_e_margens(projeto: ProjetoDeLivro, pelos_boxes: Sequence[int], alvo: Sequence[int],
                     opcoes: Opcoes, relatorio: Relatorio):
    """(os boxes e a `Estrutura` de cada página, o que sai dela pela regra das margens);
    o número impresso de cada página vai ao `relatorio`."""
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
    return lidos, estruturas, tirar


def _pagina_pelos_boxes(projeto: ProjetoDeLivro, fonte: Optional[pg.FonteDePaginas],
                        indice: int, boxes: Sequence[BoxEntry], estrutura: Estrutura,
                        tirar: set, opcoes: Opcoes, relatorio: Relatorio) -> PaginaExtraida:
    """A página pelos boxes, sem as margens que a regra tirou (salvo as que o usuário marcou
    como texto), com os diagramas dela."""
    tabuleiros = projeto.carregar_tabuleiros(indice)
    imagem = fonte.pagina(indice) if fonte is not None and tabuleiros else None
    fora = {k for k in tirar if id(boxes[k]) not in estrutura.protegidos}
    texto = [b for k, b in enumerate(boxes) if k not in fora]
    _margens_no_relatorio(relatorio, indice, boxes, fora, estrutura, opcoes.manter_margens)
    return pagina_extraida(indice, texto, tabuleiros, imagem, projeto.carregar_diagramas(indice),
                           estrutura=estrutura, manter_margens=opcoes.manter_margens,
                           desenhar_diagramas=opcoes.desenhar_diagramas,
                           manter_quebras=opcoes.manter_quebras)


def _passadas_do_livro(paginas: List[PaginaExtraida], nativas: Dict[int, PaginaExtraida],
                       opcoes: Opcoes) -> None:
    """O parágrafo que a paginação partiu volta a ser um (ou, com as quebras mantidas, a
    quebra volta à camada nativa), e o diagrama sem lado lido ganha o do lance antes dele."""
    from core import pdf_nativo

    if opcoes.manter_quebras:
        # A camada nativa já vem refluída: a quebra volta onde cada linha impressa começa.
        for indice in nativas:
            _quebras_da_camada(nativas[indice])
    else:
        _juntar_entre_paginas(paginas)
    pdf_nativo.lados_pelos_lances(paginas)


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
    resumo = projeto.resumo.do_livro()
    for pagina in paginas:
        _pagina_no_relatorio(relatorio, pagina, resumo, estados, nativas)
        _blocos_no_relatorio(relatorio, pagina.numero, pagina.blocos)


def _pagina_no_relatorio(relatorio: Relatorio, pagina: PaginaExtraida, resumo: dict,
                         estados: dict, nativas: dict) -> None:
    """A página, os caracteres, a camada, a verificação, os pendentes e as sinalizadas."""
    from abbychess.modelo import VERIFICADA

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


def _blocos_no_relatorio(relatorio: Relatorio, i: int, blocos: Sequence) -> None:
    """Os títulos de capítulo, os diagramas desenhados e os recortes, com o motivo."""
    for bloco in blocos:
        if isinstance(bloco, Paragrafo) and bloco.titulo and bloco.nivel == 1:
            relatorio.titulos.append((i, bloco.texto))
        elif isinstance(bloco, Figura):
            if bloco.origem == "render":
                relatorio.desenhados += 1
            else:
                relatorio.recortados.append((i, bloco.aviso or "recorte da página"))


def paginas_da_camada(projeto: ProjetoDeLivro, indices: Sequence[int],
                      pedido: Optional[Pedido] = None) -> Dict[int, PaginaExtraida]:
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
    idioma = (pedido or Pedido(projeto, Opcoes())).idioma
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
    escritor confere o arquivo (`validacao_do_epub.conferir`) antes de trocar o anterior, e
    recusa o que não passa (SPEC-qualidade Q-E3), como o DOCX."""
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
    if not d.lido:
        return d.erro or "não lido"
    if not _posicao_legal(d.fen):
        return "a posição não é legal"
    if d.conferido:
        return ""
    if d.validacao is not None:
        return "" if d.validacao.confiavel else d.validacao.aviso
    return "nem conferido nem confiável pelos lances"


def _posicao_legal(fen: str) -> bool:
    """O python-chess aceita o FEN, e a posição é legal."""
    import chess

    try:
        return chess.Board(fen).is_valid()
    except ValueError:
        return False


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
    pedido = Pedido.de(projeto, indices, opcoes)
    opcoes, indices = pedido.opcoes, pedido.indices
    relatorio = Relatorio(formato=formato)
    idioma = pedido.idioma_do_arquivo
    titulo = metadados_do_projeto(projeto, idioma, metadados).titulo
    if formato == "pgn":
        texto = pgn_do_livro(projeto, indices, relatorio, opcoes)
        return pv.html_do_texto(texto, relatorio.texto().splitlines(), titulo, idioma), relatorio
    fonte = pg.fonte_do_projeto(projeto)
    paginas = paginas_do_projeto(projeto, fonte, indices, progresso=progresso, opcoes=opcoes,
                                 relatorio=relatorio, pedido=pedido)
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
    pedido = Pedido.de(projeto, indices, opcoes)
    opcoes, indices = pedido.opcoes, pedido.indices
    relatorio = Relatorio(formato=formato)
    if formato == "pdf":
        resumo = exportar_pdf_pesquisavel(projeto, caminho, pedido.alvo(), progresso=progresso)
        relatorio.marcadores = resumo.marcadores
        relatorio.resumo_do_pdf = resumo.resumo()
        return relatorio.resumo_do_pdf, relatorio
    if formato == "pgn":
        texto = pgn_do_livro(projeto, indices, relatorio, opcoes)
        if not texto:
            raise NadaParaExportar("Nenhum diagrama entrou no PGN.\n\n" + relatorio.texto())
        _gravar_texto(caminho, texto)
        return relatorio.resumo(), relatorio
    _exportar_as_paginas(projeto, caminho, formato, pedido, relatorio, progresso, metadados)
    return relatorio.resumo(), relatorio


def _exportar_as_paginas(projeto: ProjetoDeLivro, caminho: Path, formato: str, pedido: Pedido,
                         relatorio: Relatorio, progresso: Optional[Progresso],
                         metadados: Optional[dict]) -> None:
    """O TXT, o DOCX e o EPUB: das páginas do projeto, pelas opções do pedido."""
    opcoes = pedido.opcoes
    fonte = pg.fonte_do_projeto(projeto)
    paginas = paginas_do_projeto(projeto, fonte, pedido.indices, progresso=progresso,
                                 opcoes=opcoes, relatorio=relatorio, pedido=pedido)
    idioma = pedido.idioma_do_arquivo
    if formato == "txt":
        _gravar_texto(caminho, texto_do_livro(paginas, marcas_de_pagina=opcoes.marcas_de_pagina))
        return
    meta = metadados_do_projeto(projeto, idioma, metadados)
    if formato == "docx":
        exportar_docx(paginas, caminho, titulo=meta.titulo, idioma=idioma, metadados=meta,
                      relatorio=relatorio, quebras=opcoes.manter_quebras,
                      realce=opcoes.realcar_duvidosos, analise=opcoes.links_de_analise)
    else:
        exportar_epub(paginas, caminho, titulo=meta.titulo, idioma=idioma, metadados=meta,
                      relatorio=relatorio, quebras=opcoes.manter_quebras,
                      analise=opcoes.links_de_analise)
