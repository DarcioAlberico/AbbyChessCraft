"""Localizar (SPEC §7.1, §7.3, passo B): o índice das páginas e a busca, sem Qt.

- **O índice** (`PaginaIndexada`): de cada página reconhecida, o texto como o Documento o
  mostra (`sessao.texto_e_unidades`, uma linha impressa por linha, os não lidos como □), o
  gid de cada caractere, a etiqueta de cada palavra (prosa, notação, cabeçalho, FEN; a
  legenda ganha a dela no passo H) e os glifos (para a busca por glifo). O FEN de cada
  diagrama lido entra no fim, numa linha dele, sem gid. Montar o texto de uma página custa
  ~17 ms (o agrupamento em linhas do core); o livro inteiro é montado em paralelo, em
  processos abertos com o programa (`PoolDoIndice`, `construir`), em segundo plano ao abrir
  o projeto. Nada vai para o disco.
- **A busca** (`buscar`): o pacote `regex` (compatível com `re`), Unicode, `concurrent=True`
  (solta o GIL: a janela continua respondendo) e um tempo-limite por casamento; o primeiro
  que estoura aborta a busca inteira (`PadraoLento`). As classes de xadrez (`\\L` lance, `\\P`
  peça, `\\C` casa, `\\V` valoração) são expandidas antes de compilar (`expandir_classes`),
  e a expansão vira a dica do campo; elas não seguem o "ignorar maiúsculas" (B, o bispo,
  não é b, a coluna). **Figurina = letra**: no texto literal, a peça de um lance (a letra
  seguida de uma casa) casa com a figurina e com as letras do idioma do livro e do inglês:
  "Cf3" acha "♘f3" e "Nf3".
- **A busca por glifo** (`buscar_glifos`): caractere, fonte e faixa de confiança.
"""

from __future__ import annotations

import json
import os
import re as _re
import threading
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
    #: (gid, amostra) dos glifos lidos por um padrão do livro (a procedência, §8.3).
    amostras: Tuple[Tuple[int, str], ...] = ()

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
                   versao: int = 0, montada=None) -> PaginaIndexada:
    """A página no índice. `margens`: os gids do cabeçalho e do rodapé (sem eles, a regra
    barata das linhas montadas, `_margens_pelas_linhas`). `montada`: o (texto, unidades) de
    `sessao.texto_e_unidades`, se quem chama já o tem (montar a página é o caro)."""
    from abbychess import sessao as ss

    texto, unidades = montada if montada is not None else ss.texto_e_unidades(pagina)
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
    amostras = tuple((b.gid, b.amostra) for b in pagina.boxes if b.amostra)
    return PaginaIndexada(pagina.indice, "".join(partes), tuple(gids), "".join(etiquetas),
                          glifos, pagina.pid, versao, amostras)


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


def _indexar_tarefa(tarefa) -> Optional[PaginaIndexada]:
    """No processo do pool (ou na thread, sem pool): a página indexada. `tarefa` é (fonte,
    idioma, versão), a fonte a própria `Pagina` (a que está na memória, como instantâneo, e a
    v1, lida sem migrar), o caminho do JSON v2, ou (caminho, posição no livro, geometria e
    tamanho da entrada): o arquivo de uma página girada ou cortada pode estar na geometria de
    antes (§12.4, ela é levada à da entrada na leitura), e o `indice` gravado é o do PDF, e
    não a posição."""
    fonte, idioma, versao = tarefa
    if isinstance(fonte, Pagina):
        return indexar_pagina(fonte, idioma, versao=versao)
    from abbychess.modelo import reenquadrar
    from abbychess.projeto import _pagina_de_json

    caminho, posicao, geometria, tamanho = (fonte if isinstance(fonte, tuple)
                                            else (fonte, None, None, None))
    try:
        pagina = _pagina_de_json(json.loads(Path(caminho).read_text(encoding="utf-8")))
        if geometria is not None:
            reenquadrar(pagina, geometria, tamanho)
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if posicao is not None:
        pagina.indice = posicao
    return indexar_pagina(pagina, idioma, versao=versao)


def _aquecer(_n: int) -> int:
    """No processo novo do pool: os módulos da indexação já carregados (o core, ~0,4 s)."""
    from core import notacao  # noqa: F401

    from abbychess import projeto, sessao, texto  # noqa: F401
    return os.getpid()


def processos_para_indexar() -> int:
    """Quantos processos montam o índice: os núcleos menos dois (a janela e o servidor de
    leitura), no máximo 6 (cada um carrega o core; mais que os núcleos físicos não ganha)."""
    return max(1, min(6, (os.cpu_count() or 2) - 2))


#: Segundos que os processos aquecidos esperam um projeto antes de fechar sozinhos.
OCIOSO = 300.0


class PoolDoIndice:
    """Os processos que montam o índice, abertos com o programa (`aquecer`, numa thread: abrir
    e importar custa ~0,75 s, que assim não fica no caminho de abrir o projeto) e fechados
    quando o último índice que os usa termina (`obter` e `devolver` contam os usos: parados,
    eles ocupariam ~300 MB à toa), ou depois de `OCIOSO` s sem projeto aberto; o próximo
    projeto aberto os abre de novo (o alvo de 2 s do índice vale para o primeiro projeto)."""

    def __init__(self):
        self._pool: Optional[ProcessPoolExecutor] = None
        self._trava = threading.Lock()
        self._pronto = threading.Event()
        self._usos = 0

    def aquecer(self, ocioso: float = None) -> None:
        """Abre os processos e carrega os módulos neles, numa thread (volta na hora)."""
        threading.Thread(target=self._abrir, name="pool-do-indice", daemon=True).start()
        relogio = threading.Timer(OCIOSO if ocioso is None else ocioso, self._fechar_se_ocioso)
        relogio.daemon = True
        relogio.start()

    def _fechar_se_ocioso(self) -> None:
        with self._trava:
            ocioso = self._usos == 0
        if ocioso:
            self.liberar()

    def _abrir(self) -> Optional[ProcessPoolExecutor]:
        import multiprocessing

        with self._trava:
            if self._pool is None:
                n = processos_para_indexar()
                self._pool = ProcessPoolExecutor(n, mp_context=multiprocessing.get_context("spawn"))
                try:
                    list(self._pool.map(_aquecer, range(n)))
                except Exception:               # o pool quebrado: o índice monta sem ele
                    self._pool.shutdown(wait=False, cancel_futures=True)
                    self._pool = None
            self._pronto.set()
            return self._pool

    def obter(self) -> Optional[ProcessPoolExecutor]:
        """O pool aberto (abre agora, se não foi aquecido), contado como um uso até
        `devolver`."""
        with self._trava:
            self._usos += 1
        return self._abrir()

    def devolver(self) -> None:
        """O fim de um uso; o último fecha os processos (as tarefas de outro uso nunca são
        canceladas por este)."""
        with self._trava:                       # o último tira o pool na mesma trava: um
            self._usos = max(0, self._usos - 1)  # obter() que vem depois abre outro
            pool = None
            if self._usos == 0:
                pool, self._pool = self._pool, None
                self._pronto.clear()
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)

    def liberar(self) -> None:
        """Fecha os processos agora."""
        with self._trava:
            pool, self._pool = self._pool, None
            self._pronto.clear()
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)


def construir(fontes: Mapping[int, Tuple[object, int]], idioma: str = "pt", *,
              paralelo: bool = True, cancelado: Callable[[], bool] = lambda: False,
              ao_indexar: Optional[Callable[[PaginaIndexada], None]] = None,
              pool: Optional[PoolDoIndice] = None) -> Dict[int, PaginaIndexada]:
    """O índice das páginas: `fontes` é índice -> (o JSON v2 da página, ou a `Pagina`; a
    versão dela no histórico). Com `paralelo`, num pool de processos (`pool`, o aquecido
    com o programa; sem ele, um aberto só para isso): montar o texto de 230 páginas leva
    ~5,5 s num processo e ~1,2 s em 6 já abertos."""
    saida: Dict[int, PaginaIndexada] = {}
    tarefas = [(fonte, idioma, versao) for _i, (fonte, versao) in sorted(fontes.items())]
    if not tarefas:
        return saida
    usado = None
    if not paralelo or len(tarefas) < 8:
        resultados: Iterable = map(_indexar_tarefa, tarefas)
    else:
        usado = pool if pool is not None else PoolDoIndice()
        executor = usado.obter()
        resultados = (executor.map(_indexar_tarefa, tarefas, chunksize=4) if executor is not None
                      else map(_indexar_tarefa, tarefas))
    try:
        for indexada in resultados:
            if cancelado():
                break
            if indexada is not None:
                saida[indexada.indice] = indexada
                if ao_indexar is not None:
                    ao_indexar(indexada)
    finally:
        fechar = getattr(resultados, "close", None)
        if fechar is not None:                  # cancela as tarefas deste índice que faltam
            fechar()
        if usado is not None:
            usado.devolver()
    return saida


# ----------------------------------------------------------------------
# As classes de xadrez
# ----------------------------------------------------------------------

def _classe_de_pecas(idioma: str) -> str:
    return "".join(sorted(FIGURINAS)) + PECAS.get(idioma, PECAS["en"])


def classes(idioma: str) -> Dict[str, str]:
    """A expansão de cada classe de xadrez (§7.1), para o idioma do livro. Cada uma fica
    fora do "ignorar maiúsculas" (`(?-i:...)`: B, o bispo, não é b, a coluna), e o lance e a
    casa não começam nem terminam no meio de uma palavra ("the5", "a43"; a casa depois da
    coluna ou da linha que desambigua vale: Nbd7, Rae1, R1e2, exd5)."""
    pecas = regex.escape(_classe_de_pecas(idioma))
    lance = (rf"(?-i:(?<!\w)(?:[{pecas}]?[a-h]?[1-8]?[-x]?[a-h][1-8](?:=[{pecas}])?"
             r"|O-O(?:-O)?|0-0(?:-0)?)[+#]?(?![\w+#]))")
    casa = r"(?-i:(?<![a-wyz][a-wyz])(?<![i-wyz09])[a-h][1-8](?![0-9]))"
    valoracao = (r"(?-i:(?:\+-|-\+|\+=|=\+|!!|\?\?|!\?|\?!|‼|⁇|⁉|⁈|[±∓⩲⩱∞□!?]"
                 r"|(?<!\w)=(?!\w)))")
    return {"L": lance, "P": f"(?-i:[{pecas}])", "C": casa, "V": valoracao}


DESCRICOES = {"L": "lance (Cf3, exd5, O-O, e8=D+)", "P": "peça (figurinas e letras do idioma)",
              "C": "casa (a1 a h8)",
              "V": "valoração (± ∓ ⩲ ⩱ +- -+ += =+ = ∞ ! ? !! ?? !? ?! □)"}


class PadraoInvalido(ValueError):
    """A regex não compila (a mensagem vai para a barra)."""


class PadraoLento(Exception):
    """Uma página estourou o tempo-limite: a busca inteira foi abortada."""


def expandir_classes(padrao: str, idioma: str) -> Tuple[str, str]:
    """O padrão com `\\L`, `\\P`, `\\C` e `\\V` expandidos (fora de `[...]`; dentro, `\\P`
    vira as peças e `\\C`, `a-h1-8`), e a dica com a expansão das que apareceram. `\\P{...}`
    (a propriedade Unicode do `regex`) fica como está."""
    expansao = classes(idioma)
    saida: List[str] = []
    usadas: List[str] = []
    dentro, k = False, 0
    while k < len(padrao):
        c = padrao[k]
        if c == "\\" and k + 1 < len(padrao):
            proximo = padrao[k + 1]
            propriedade = proximo == "P" and padrao[k + 2:k + 3] == "{"
            if proximo in expansao and not propriedade:
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
            saida.append(c)
            k += 1
            if padrao[k:k + 1] == "^":         # "[^" e o "]" logo depois são literais
                saida.append("^")
                k += 1
            if padrao[k:k + 1] == "]":
                saida.append("]")
                k += 1
            continue
        if c == "]" and dentro:
            dentro = False
        saida.append(c)
        k += 1
    dica = "; ".join(f"\\{c} = {DESCRICOES[c]}: {expansao[c]}" for c in usadas)
    return "".join(saida), dica


#: A peça de um lance no texto literal: a letra seguida de uma casa (com a desambiguação
#: e a captura: "Cf3", "C1e2", "Cbd7", "Cxe5").
_DEPOIS_DA_PECA = _re.compile(r"[a-h]?[1-8]?x?[a-h][1-8]")


def _figurina_igual_a_letra(texto: str, idioma: str) -> str:
    """O texto literal como regex, com a peça de cada lance (a letra seguida de casa, ou a
    figurina) trocada pela classe das formas dela: a figurina branca e a preta, a letra do
    idioma e a do inglês (menos quando a do inglês é outra peça no idioma: em português, o R
    do inglês é a torre e o R do livro é o rei)."""
    pecas, ingles = PECAS.get(idioma, PECAS["en"]), PECAS["en"]
    saida: List[str] = []
    for k, c in enumerate(texto):
        papel = None
        if c in BRANCAS:
            papel = BRANCAS.index(c)
        elif c in PRETAS:
            papel = PRETAS.index(c)
        elif _DEPOIS_DA_PECA.match(texto, k + 1):
            if c in pecas:
                papel = pecas.index(c)
            elif c in ingles:
                papel = ingles.index(c)
        if papel is None:
            saida.append(regex.escape(c))
            continue
        formas = {BRANCAS[papel], PRETAS[papel], pecas[papel]}
        letra_inglesa = ingles[papel]
        if letra_inglesa not in pecas or pecas.index(letra_inglesa) == papel:
            formas.add(letra_inglesa)
        saida.append("(?-i:[" + "".join(regex.escape(f) for f in sorted(formas)) + "])")
    return "".join(saida)


# ----------------------------------------------------------------------
# A busca
# ----------------------------------------------------------------------

LIVRO, PAGINA, INTERVALO, SELECAO = "livro", "pagina", "intervalo", "selecao"


@dataclass(frozen=True)
class Opcoes:
    """O que a barra pede. `selecao` é (página, gid do primeiro glifo, gid do último): a
    posição no texto sai do índice da página na hora da busca, que pode tê-la refeito;
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
    # MULTILINE: `^` e `$` em cada linha impressa da página.
    bandeiras = (regex.UNICODE | regex.VERSION0 | regex.MULTILINE
                 | (0 if opcoes.maiusculas else regex.IGNORECASE))
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
           tempo_limite: float = TEMPO_LIMITE, expressao=None) -> Resultado:
    """As ocorrências, em ordem de página e posição. `PadraoInvalido` se a regex não
    compila; `PadraoLento` no primeiro tempo-limite estourado, que conta cada casamento (um
    `search` por vez: o trabalho de anotar as ocorrências e a espera pelo GIL ficam fora).
    `cancelado()` é consultado entre as páginas (digitar de novo cancela a busca anterior).
    `expressao`: a já compilada (`compilar`)."""
    if not opcoes.texto:
        return Resultado()
    if expressao is None:
        expressao, _dica = compilar(opcoes)
    resultado = Resultado()
    for indice in _paginas_do_escopo(paginas, opcoes):
        if cancelado():
            resultado.cancelada = True
            break
        pagina = paginas[indice]
        resultado.paginas_buscadas += 1
        inicio, fim = 0, len(pagina.texto)
        if opcoes.escopo == SELECAO:
            trecho = _trecho_da_selecao(pagina, opcoes.selecao)
            if trecho is None:
                continue
            inicio, fim = trecho
        for casado in casamentos(pagina, expressao, inicio, fim, tempo_limite, indice):
            ocorrencia = _ocorrencia(pagina, casado.start(), casado.end())
            if ocorrencia is not None and ocorrencia.etiqueta in opcoes.onde:
                resultado.ocorrencias.append(ocorrencia)
    return resultado


def casamentos(pagina: PaginaIndexada, expressao, inicio: int, fim: int,
               tempo_limite: float = TEMPO_LIMITE, indice: int = 0):
    """Os casamentos não vazios em `pagina.texto[inicio:fim]`, um `search` por vez (o
    tempo-limite conta cada um; `PadraoLento` no primeiro estourado)."""
    posicao = inicio
    while posicao <= fim:
        try:
            casado = expressao.search(pagina.texto, posicao, fim, concurrent=True,
                                      timeout=tempo_limite)
        except TimeoutError as erro:
            raise PadraoLento(f"padrão lento demais (página {indice + 1})") from erro
        if casado is None:
            return
        if casado.end() == casado.start():      # o casamento vazio: adiante, sem ocorrência
            posicao = casado.end() + 1
            continue
        yield casado
        posicao = casado.end()


def _trecho_da_selecao(pagina: PaginaIndexada, selecao) -> Optional[Tuple[int, int]]:
    """(início, fim) no texto da página da seleção (página, gid do primeiro, gid do último)."""
    if selecao is None:
        return None
    _pagina, primeiro, ultimo = selecao
    if primeiro not in pagina.gids or ultimo not in pagina.gids:
        return None
    inicio = pagina.gids.index(primeiro)
    fim = len(pagina.gids) - pagina.gids[::-1].index(ultimo)
    return (inicio, fim) if inicio < fim else None


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
