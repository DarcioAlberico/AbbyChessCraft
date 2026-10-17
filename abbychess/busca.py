"""Localizar (SPEC §7.1, §7.3, passo B): o índice das páginas e a busca, sem Qt.

- **O índice** (`PaginaIndexada`): de cada página reconhecida, o texto como o Documento o
  mostra (`sessao.texto_e_unidades`, uma linha impressa por linha, os não lidos como □), o
  gid de cada caractere, a etiqueta de cada palavra (prosa, notação, cabeçalho, FEN; a
  legenda ganha a dela no passo H) e os glifos (para a busca por glifo). O FEN de cada
  diagrama lido entra no fim, numa linha dele, sem gid. Montar o texto de uma página custa
  ~17 ms (o agrupamento em linhas do core); o livro inteiro é montado em paralelo, em
  processos (`construir`), em segundo plano ao abrir o projeto. Nada vai para o disco.
- **A busca** (`buscar`): o pacote `regex` (compatível com `re`), Unicode, `concurrent=True`
  (solta o GIL: a janela continua respondendo) e um tempo-limite por página; o primeiro que
  estoura aborta a busca inteira (`PadraoLento`). As classes de xadrez (`\\L` lance, `\\P`
  peça, `\\C` casa, `\\V` valoração) são expandidas antes de compilar (`expandir_classes`),
  e a expansão vira a dica do campo. **Figurina = letra**: no texto literal, a peça de um
  lance casa com a figurina e com as letras (do idioma do livro e do inglês): "Cf3" acha
  "♘f3" e "Nf3".
- **A busca por glifo** (`buscar_glifos`): caractere, fonte e faixa de confiança.
"""

from __future__ import annotations

import json
import os
import re as _re
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Tuple

import regex

from abbychess.modelo import FIGURINAS, Pagina

PROSA, NOTACAO, LEGENDA, CABECALHO, FEN = "prosa", "notacao", "legenda", "cabecalho", "fen"
ETIQUETAS = (PROSA, NOTACAO, FEN, LEGENDA, CABECALHO)
#: A etiqueta de cada caractere, num código de uma letra (o espaço e a quebra: " ").
_CODIGO = {PROSA: "p", NOTACAO: "n", LEGENDA: "l", CABECALHO: "c", FEN: "f"}
_ETIQUETA_DO_CODIGO = {c: e for e, c in _CODIGO.items()}

#: O tempo-limite de cada página (§7.1: 0,5 s); o primeiro que estoura aborta a busca.
TEMPO_LIMITE = 0.5

#: As letras das peças em cada idioma (as de `sessao.PECAS`), na ordem rei, dama, torre,
#: bispo, cavalo; as figurinas brancas e pretas na mesma ordem.
PECAS = {"pt": "RDTBC", "en": "KQRBN", "es": "RDTAC", "de": "KDTLS", "fr": "RDTFC"}
BRANCAS, PRETAS = "♔♕♖♗♘", "♚♛♜♝♞"


# ----------------------------------------------------------------------
# O índice
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class PaginaIndexada:
    """Uma página no índice. `etiquetas` tem um código por caractere de `texto`; `gids`, o
    gid de cada caractere (None no espaço, na quebra e no FEN); `glifos`, (gid, caractere,
    fonte, confiança) de cada box; `versao`, a do histórico quando foi indexada."""

    indice: int
    texto: str
    gids: Tuple[Optional[int], ...]
    etiquetas: str
    glifos: Tuple[Tuple[int, str, str, float], ...] = ()
    pid: Optional[int] = None
    versao: int = 0

    def etiqueta(self, posicao: int) -> str:
        return _ETIQUETA_DO_CODIGO.get(self.etiquetas[posicao], PROSA)


def e_lance(token: str, idioma: str) -> bool:
    """O token tem forma de lance, de número de lance ou de avaliação (a etiqueta "notação"):
    o classificador do core (letras do inglês e figurinas) ou o lance com as letras do
    idioma do livro."""
    from core.notacao import e_token_de_notacao

    from abbychess import sessao as ss

    if e_token_de_notacao(token):
        return True
    nucleo = token.strip(ss.PONTUACAO_DE_BORDA)
    return bool(nucleo) and ss._lance(idioma).match(nucleo) is not None


def indexar_pagina(pagina: Pagina, idioma: str = "pt", margens: Optional[Iterable[int]] = None,
                   versao: int = 0) -> PaginaIndexada:
    """A página no índice. `margens`: os gids do cabeçalho e do rodapé (sem eles, a regra
    barata das linhas montadas, `_margens_pelas_linhas`)."""
    from abbychess import sessao as ss

    texto, unidades = ss.texto_e_unidades(pagina)
    gids: List[Optional[int]] = [u.gid for u in unidades]
    margens = set(_margens_pelas_linhas(pagina, texto, gids) if margens is None else margens)
    codigos = [" "] * len(texto)
    for token in _re.finditer(r"\S+", texto):
        a, b = token.span()
        if any(gids[k] in margens for k in range(a, b)):
            codigo = _CODIGO[CABECALHO]
        elif e_lance(token.group(0), idioma):
            codigo = _CODIGO[NOTACAO]
        else:
            codigo = _CODIGO[PROSA]
        codigos[a:b] = [codigo] * (b - a)
    partes, etiquetas = [texto], ["".join(codigos)]
    for diagrama in pagina.diagramas:            # o FEN de cada diagrama lido, numa linha dele
        if getattr(diagrama, "lido", False) and getattr(diagrama, "fen", ""):
            linha = ("\n" if partes[0] or len(partes) > 1 else "") + diagrama.fen
            partes.append(linha)
            etiquetas.append(" " * (len(linha) - len(diagrama.fen)) + _CODIGO[FEN] * len(diagrama.fen))
            gids.extend([None] * len(linha))
    glifos = tuple((b.gid, b.entry.char, str(b.entry.source), float(b.entry.confidence))
                   for b in pagina.boxes)
    return PaginaIndexada(pagina.indice, "".join(partes), tuple(gids), "".join(etiquetas),
                          glifos, pagina.pid, versao)


#: A linha de margem (cabeçalho, rodapé, número de página) é curta e tem um número.
_LINHA_DE_MARGEM = _re.compile(r"\d")


def _margens_pelas_linhas(pagina: Pagina, texto: str, gids: Sequence[Optional[int]]) -> set:
    """Os gids do cabeçalho e do rodapé, pelas linhas já montadas (barato: a regra da
    exportação, `exportar.margens_corridas`, monta as linhas de novo e custa ~15 ms por
    página): a primeira e a última linha, curtas (até 60 caracteres), com um número, e
    separadas do texto por um vão maior que 1,5 vez o vão mediano entre as linhas."""
    caixa = {b.gid: b.entry for b in pagina.boxes}
    linhas, inicio = [], 0
    for parte in texto.split("\n"):
        fim = inicio + len(parte)
        meus = {g for g in gids[inicio:fim] if g is not None and g in caixa}
        if meus:
            linhas.append((parte, meus, min(caixa[g].y1 for g in meus),
                           max(caixa[g].y2 for g in meus)))
        inicio = fim + 1
    if len(linhas) < 3:
        return set()
    vaos = sorted(max(0, b[2] - a[3]) for a, b in zip(linhas, linhas[1:]))
    mediano = vaos[len(vaos) // 2]
    saida: set = set()
    for k, vizinho in ((0, 1), (len(linhas) - 1, len(linhas) - 2)):
        parte, meus, topo, base = linhas[k]
        _p, _m, topo_v, base_v = linhas[vizinho]
        vao = topo_v - base if k == 0 else topo - base_v
        if len(parte.strip()) <= 60 and _LINHA_DE_MARGEM.search(parte) and vao > 1.5 * max(1, mediano):
            saida |= meus
    return saida


def _indexar_arquivo(argumentos) -> Optional[PaginaIndexada]:
    """No processo do pool: a página gravada (o JSON v2), indexada."""
    caminho, idioma, versao = argumentos
    from abbychess.projeto import _pagina_de_json

    try:
        pagina = _pagina_de_json(json.loads(Path(caminho).read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return indexar_pagina(pagina, idioma, versao=versao)


def processos_para_indexar() -> int:
    """Quantos processos montam o índice: os núcleos menos dois (a janela e o servidor de
    leitura), no máximo 6 (cada um carrega o core; mais que os núcleos físicos não ganha)."""
    return max(1, min(6, (os.cpu_count() or 2) - 2))


def construir(arquivos: Mapping[int, Tuple[str, int]], idioma: str = "pt", *,
              paralelo: bool = True, cancelado: Callable[[], bool] = lambda: False,
              ao_indexar: Optional[Callable[[PaginaIndexada], None]] = None
              ) -> Dict[int, PaginaIndexada]:
    """O índice das páginas gravadas: `arquivos` é índice -> (o JSON da página, a versão
    dela no histórico). Com `paralelo`, num pool de processos aberto só para isso (montar o
    texto de 230 páginas leva ~5,5 s num processo e ~1,4 s em 6)."""
    saida: Dict[int, PaginaIndexada] = {}
    tarefas = [(caminho, idioma, versao) for _i, (caminho, versao) in sorted(arquivos.items())]
    if not tarefas:
        return saida
    if not paralelo or len(tarefas) < 8:
        resultados: Iterable = map(_indexar_arquivo, tarefas)
        pool = None
    else:
        import multiprocessing

        pool = ProcessPoolExecutor(min(processos_para_indexar(), len(tarefas) // 4 or 1),
                                   mp_context=multiprocessing.get_context("spawn"))
        resultados = pool.map(_indexar_arquivo, tarefas, chunksize=4)
    try:
        for indexada in resultados:
            if cancelado():
                break
            if indexada is not None:
                saida[indexada.indice] = indexada
                if ao_indexar is not None:
                    ao_indexar(indexada)
    finally:
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)
    return saida


# ----------------------------------------------------------------------
# As classes de xadrez
# ----------------------------------------------------------------------

def _classe_de_pecas(idioma: str) -> str:
    return "".join(sorted(FIGURINAS)) + PECAS.get(idioma, PECAS["en"])


def classes(idioma: str) -> Dict[str, str]:
    """A expansão de cada classe de xadrez (§7.1), para o idioma do livro."""
    pecas = regex.escape(_classe_de_pecas(idioma))
    lance = (rf"(?:[{pecas}]?[a-h]?[1-8]?[-x]?[a-h][1-8](?:=[{pecas}])?|O-O(?:-O)?|0-0(?:-0)?)"
             r"[+#]?")
    valoracao = r"(?:\+-|-\+|!!|\?\?|!\?|\?!|[±∓⩲⩱=∞!?])"
    return {"L": lance, "P": f"[{pecas}]", "C": "[a-h][1-8]", "V": valoracao}


DESCRICOES = {"L": "lance (Cf3, exd5, O-O, e8=D+)", "P": "peça (figurinas e letras do idioma)",
              "C": "casa (a1 a h8)", "V": "valoração (± ∓ ⩲ ⩱ += -+ ! ? !? ?!)"}


class PadraoInvalido(ValueError):
    """A regex não compila (a mensagem vai para a barra)."""


class PadraoLento(Exception):
    """Uma página estourou o tempo-limite: a busca inteira foi abortada."""


def expandir_classes(padrao: str, idioma: str) -> Tuple[str, str]:
    """O padrão com `\\L`, `\\P`, `\\C` e `\\V` expandidos (fora de `[...]`; dentro, `\\P`
    vira as peças e `\\C`, `a-h1-8`), e a dica com a expansão das que apareceram."""
    expansao = classes(idioma)
    saida: List[str] = []
    usadas: List[str] = []
    dentro, k = False, 0
    while k < len(padrao):
        c = padrao[k]
        if c == "\\" and k + 1 < len(padrao):
            proximo = padrao[k + 1]
            if proximo in expansao:
                if dentro:
                    if proximo == "P":
                        saida.append(regex.escape(_classe_de_pecas(idioma)))
                    elif proximo == "C":
                        saida.append("a-h1-8")
                    else:
                        raise PadraoInvalido(f"\\{proximo} não cabe dentro de [ ]")
                else:
                    saida.append(expansao[proximo])
                if proximo not in usadas:
                    usadas.append(proximo)
            else:
                saida.append(c + proximo)
            k += 2
            continue
        if c == "[" and not dentro:
            dentro = True
        elif c == "]" and dentro and saida and saida[-1] != "[":
            dentro = False
        saida.append(c)
        k += 1
    dica = "; ".join(f"\\{c} = {DESCRICOES[c]}: {expansao[c]}" for c in usadas)
    return "".join(saida), dica


def _figurina_igual_a_letra(texto: str, idioma: str) -> str:
    """O texto literal como regex, com a peça de cada lance (a letra seguida de casa, ou a
    figurina) trocada pela classe das formas dela: a figurina branca e a preta, a letra do
    idioma e a do inglês."""
    pecas, ingles = PECAS.get(idioma, PECAS["en"]), PECAS["en"]
    saida: List[str] = []
    for k, c in enumerate(texto):
        seguinte = texto[k + 1:k + 2]
        papel = None
        if c in BRANCAS:
            papel = BRANCAS.index(c)
        elif c in PRETAS:
            papel = PRETAS.index(c)
        elif c in pecas and (seguinte in "abcdefghx" and seguinte != ""):
            papel = pecas.index(c)
        elif c in ingles and (seguinte in "abcdefghx" and seguinte != ""):
            papel = ingles.index(c)
        if papel is None:
            saida.append(regex.escape(c))
        else:
            formas = {BRANCAS[papel], PRETAS[papel], pecas[papel], ingles[papel]}
            saida.append("[" + "".join(regex.escape(f) for f in sorted(formas)) + "]")
    return "".join(saida)


# ----------------------------------------------------------------------
# A busca
# ----------------------------------------------------------------------

LIVRO, PAGINA, INTERVALO, SELECAO = "livro", "pagina", "intervalo", "selecao"


@dataclass(frozen=True)
class Opcoes:
    """O que a barra pede. `selecao` é (página, início, fim) no texto do índice;
    `intervalo`, (primeira, última) inclusive, em índices de página."""

    texto: str
    maiusculas: bool = False
    palavra_inteira: bool = False
    regex: bool = False
    figurina_letra: bool = False
    escopo: str = LIVRO
    pagina_atual: int = 0
    intervalo: Optional[Tuple[int, int]] = None
    selecao: Optional[Tuple[int, int, int]] = None
    onde: FrozenSet[str] = frozenset(ETIQUETAS)
    idioma: str = "pt"


@dataclass(frozen=True)
class Ocorrencia:
    pagina: int
    inicio: int
    fim: int
    linha: int                  # 1 é a primeira da página
    trecho: str                 # a linha inteira
    coluna: int                 # o casamento em trecho[coluna:coluna + (fim - inicio)]
    gids: Tuple[int, ...]
    etiqueta: str = PROSA


@dataclass
class Resultado:
    ocorrencias: List[Ocorrencia] = field(default_factory=list)
    paginas_buscadas: int = 0
    cancelada: bool = False

    def por_pagina(self) -> Dict[int, int]:
        contagem: Dict[int, int] = {}
        for o in self.ocorrencias:
            contagem[o.pagina] = contagem.get(o.pagina, 0) + 1
        return contagem


def compilar(opcoes: Opcoes):
    """A regex compilada, e a dica (a expansão das classes). `PadraoInvalido` se não compila."""
    dica = ""
    if opcoes.regex:
        padrao, dica = expandir_classes(opcoes.texto, opcoes.idioma)
    elif opcoes.figurina_letra:
        padrao = _figurina_igual_a_letra(opcoes.texto, opcoes.idioma)
    else:
        padrao = regex.escape(opcoes.texto)
    if opcoes.palavra_inteira:
        padrao = rf"(?<!\w)(?:{padrao})(?!\w)"
    bandeiras = regex.UNICODE | regex.VERSION0 | (0 if opcoes.maiusculas else regex.IGNORECASE)
    try:
        return regex.compile(padrao, bandeiras), dica
    except regex.error as erro:
        raise PadraoInvalido(str(erro)) from erro


def _paginas_do_escopo(paginas: Mapping[int, PaginaIndexada], opcoes: Opcoes) -> List[int]:
    if opcoes.escopo in (PAGINA, SELECAO):
        alvo = opcoes.selecao[0] if opcoes.escopo == SELECAO and opcoes.selecao else opcoes.pagina_atual
        return [alvo] if alvo in paginas else []
    if opcoes.escopo == INTERVALO and opcoes.intervalo is not None:
        a, b = sorted(opcoes.intervalo)
        return [i for i in sorted(paginas) if a <= i <= b]
    return sorted(paginas)


def buscar(paginas: Mapping[int, PaginaIndexada], opcoes: Opcoes,
           cancelado: Callable[[], bool] = lambda: False,
           tempo_limite: float = TEMPO_LIMITE) -> Resultado:
    """As ocorrências, em ordem de página e posição. `PadraoInvalido` se a regex não
    compila; `PadraoLento` no primeiro tempo-limite estourado. `cancelado()` é consultado
    entre as páginas (digitar de novo cancela a busca anterior)."""
    if not opcoes.texto:
        return Resultado()
    expressao, _dica = compilar(opcoes)
    resultado = Resultado()
    for indice in _paginas_do_escopo(paginas, opcoes):
        if cancelado():
            resultado.cancelada = True
            break
        pagina = paginas[indice]
        resultado.paginas_buscadas += 1
        inicio, fim = 0, len(pagina.texto)
        if opcoes.escopo == SELECAO and opcoes.selecao is not None:
            inicio, fim = opcoes.selecao[1], opcoes.selecao[2]
        try:
            for casado in expressao.finditer(pagina.texto, inicio, fim, concurrent=True,
                                             timeout=tempo_limite):
                ocorrencia = _ocorrencia(pagina, casado.start(), casado.end())
                if ocorrencia is not None and ocorrencia.etiqueta in opcoes.onde:
                    resultado.ocorrencias.append(ocorrencia)
        except TimeoutError as erro:
            raise PadraoLento(f"padrão lento demais (página {indice + 1})") from erro
    return resultado


def _ocorrencia(pagina: PaginaIndexada, inicio: int, fim: int) -> Optional[Ocorrencia]:
    if fim <= inicio:                           # o casamento vazio não é ocorrência
        return None
    texto = pagina.texto
    comeco_da_linha = texto.rfind("\n", 0, inicio) + 1
    fim_da_linha = texto.find("\n", inicio)
    fim_da_linha = len(texto) if fim_da_linha < 0 else fim_da_linha
    primeiro = next((k for k in range(inicio, fim) if not texto[k].isspace()), inicio)
    gids: List[int] = []
    for k in range(inicio, fim):
        g = pagina.gids[k]
        if g is not None and (not gids or gids[-1] != g):
            gids.append(g)
    return Ocorrencia(pagina.indice, inicio, fim, texto.count("\n", 0, inicio) + 1,
                      texto[comeco_da_linha:fim_da_linha], inicio - comeco_da_linha,
                      tuple(gids), pagina.etiqueta(primeiro))


# ----------------------------------------------------------------------
# A busca por glifo
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class GlifoAchado:
    pagina: int
    gid: int
    char: str
    fonte: str
    confianca: float


REDE, BASE, LIVRO_, MANUAL, SEM_LEITURA = "rede", "base", "livro", "manual", "sem leitura"


def grupo_da_fonte(fonte: str) -> str:
    """A fonte da leitura no grupo da busca por glifo (§7.1): manual, livro (os padrões do
    livro), base (a base global do PyBoxEditor), rede (a rede e as cadeias do core) ou sem
    leitura."""
    if fonte == "manual":
        return MANUAL
    if fonte.startswith("livro"):
        return LIVRO_
    if fonte in ("", "none"):
        return SEM_LEITURA
    if "learner" in fonte or fonte.startswith("base"):
        return BASE
    return REDE


def buscar_glifos(paginas: Mapping[int, PaginaIndexada], char: str,
                  fontes: Optional[Sequence[str]] = None, confianca_minima: float = 0.0,
                  confianca_maxima: float = 1.0) -> List[GlifoAchado]:
    """Os glifos lidos como `char` (vazio: qualquer um), dos grupos de `fontes` (None:
    todos; ver `grupo_da_fonte`), com a confiança na faixa (§7.1); em ordem de página."""
    saida = []
    for indice in sorted(paginas):
        for gid, c, fonte, confianca in paginas[indice].glifos:
            if char and c != char:
                continue
            if fontes is not None and grupo_da_fonte(fonte) not in fontes:
                continue
            if confianca_minima <= confianca <= confianca_maxima:
                saida.append(GlifoAchado(indice, gid, c, fonte, confianca))
    return saida
