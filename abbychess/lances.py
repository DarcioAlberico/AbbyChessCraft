"""Os lances do texto depois de cada diagrama (SPEC §10): validar, inferir o roque e o PGN.

Sem Qt. A ideia é a do chesspdf: os lances que o livro imprime depois de um diagrama
foram jogados **naquela** posição. Se o primeiro deles não é legal no FEN lido, a leitura
(ou o texto) está errada; se todos os da primeira linha são, a posição ganha o estado
**confiável pelos lances**.

## A primeira linha

O texto vai do diagrama até o próximo diagrama ou título (`texto_depois`), sem legenda,
cabeçalho, rodapé nem número de página. Nele, a linha começa no primeiro lance
**numerado** (`1.e4`, `10...Rf8`): um lance solto na prosa ("o peão de e4") não começa
nada. Depois, cada lance entra se tiver número ou se for a resposta das pretas logo depois
do lance das brancas; a prosa no meio não corta a linha, mas o lance seguinte precisa do
número. A linha acaba:

- num parêntese, colchete ou ponto e vírgula (a variante);
- num número que não é o esperado: o livro volta a um lance que já passou (`11...` depois
  do `14.`), o que também é variante.

**As letras são as do idioma do livro** (`modelo.PECAS`: `Cf3` em português é `Nf3`) e as
figurinas valem em qualquer idioma. Por isso o texto entra no modo impresso: no modo SAN o
`♖` já virou `R`, que em português seria o rei.

## O que conta como erro

O lance que `python-chess` não aceita (ilegal ou ambíguo) e, além dele, o lance que diz
mais do que faz: um `x` que não captura, um `+` que não dá xeque, um `#` que não dá mate.
A falta do sinal não conta (o OCR perde `x` e `+` mais do que inventa). O lado a jogar é o
do número (`1...` é das pretas); quando o diagrama diz outro lado, também é erro.

## O roque inferido

Rei e torre nas casas iniciais **sugerem** o roque (`roque_inferido`). A validação usa a
sugestão (senão o `O-O` do texto seria ilegal), mas o FEN do diagrama nunca a afirma sem
conferência (CA-10.3): só quem confere marca o roque. O PGN declara o roque conferido e o
que o próprio texto jogou (`O-O` na linha é prova do direito), nunca o inferido sozinho.
"""

from __future__ import annotations

import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import chess
import chess.pgn

CONFIAVEL = "confiavel_pelos_lances"
ILEGAL = "lance_ilegal"

#: A procedência do lado a jogar dito pelo número do primeiro lance (`1...` = pretas),
#: quando nem a legenda nem quem conferiu disseram.
LADO_DOS_LANCES = "lances"

#: Os estados como a interface os diz.
NOMES = {CONFIAVEL: "confiável pelos lances", ILEGAL: "lance do texto não é legal"}

#: As funções de bloco que não são o texto que segue o diagrama.
FORA_DO_TEXTO = frozenset({"legenda", "cabecalho", "rodape", "numero_de_pagina", "ignorar",
                           "imagem", "figura"})
#: As funções que encerram o texto de um diagrama (além do próximo diagrama).
FIM_DO_TEXTO = frozenset({"titulo"})

_INGLES = "KQRBN"
_PEOES = "♙♟"
_BORDA = ",:.\"'“”‘’"
#: `1.`, `1...`, `1…` e `1..` (as reticências que o OCR leu com um ponto a menos).
_NUMERO = re.compile(r"^(\d{1,3})(\.{2,}|…|\.)(.*)$")
#: O número como o OCR o lê num livro escaneado: o `1` como `l`, `I` ou `|` e o `0` como `O`
#: ou `o` ("l.d6", "l9...♘f2", "l0.f3", "2l.♔f1"; Mirkovic, *Chess School 1*, pp. 10–160).
#: Sem algarismo de verdade, só vale colado a um lance: "lo." no fim de uma frase é palavra.
_NUMERO_DO_OCR = re.compile(r"^([0-9lI|Oo]{1,3})(\.{2,}|…|\.)(.*)$")
_ALGARISMOS_DO_OCR = str.maketrans("lI|Oo", "11100")
#: O número separado das reticências da variante ("l ...d3", "1 ...♖e8"; Mirkovic, p. 88): o
#: lance das pretas sem número continuaria a linha principal. Não começa por O ou o: o
#: "o ...Cf6" do português é o artigo.
_NUMERO_SEPARADO = re.compile(r"(?<!\S)([(\[{]?[1-9lI|][0-9lI|Oo]{0,2})\s+"
                              r"(?=(?:\.{2,}|…)[^\s.…])")
#: O `1` da casa lido como `l` ("♕el", "♖adl", "♔hl"): só no lance de peça ou de captura,
#: senão o "el" de um livro em espanhol viraria e1.
_FILEIRA_1_DO_OCR = re.compile(r"(?<=[a-h])[lI|](?=[+#!?‼⁇⁈⁉]*$)")
_LANCE = re.compile(r"^(?P<lance>O-O-O|O-O|[KQRBN]?[a-h]?[1-8]?[x:×]?[a-h][1-8](?:=?[QRBN])?)"
                    r"(?P<marca>[+#]*)(?P<juizo>[!?‼⁇⁈⁉]*)(?:e\.?p\.?)?$")
_SINAL = re.compile(r"^[+#!?‼⁇⁈⁉±∓⩱⩲=∞□■△▼→↑⇆–—-]+$")

#: Os sinais de juízo que viram NAG no PGN.
_NAGS = {"!": chess.pgn.NAG_GOOD_MOVE, "?": chess.pgn.NAG_MISTAKE,
         "!!": chess.pgn.NAG_BRILLIANT_MOVE, "‼": chess.pgn.NAG_BRILLIANT_MOVE,
         "??": chess.pgn.NAG_BLUNDER, "⁇": chess.pgn.NAG_BLUNDER,
         "!?": chess.pgn.NAG_SPECULATIVE_MOVE, "⁉": chess.pgn.NAG_SPECULATIVE_MOVE,
         "?!": chess.pgn.NAG_DUBIOUS_MOVE, "⁈": chess.pgn.NAG_DUBIOUS_MOVE}

#: Casas do rei e da torre de cada direito de roque.
_ROQUE = {"K": ("e1", "h1", "K", "R"), "Q": ("e1", "a1", "K", "R"),
          "k": ("e8", "h8", "k", "r"), "q": ("e8", "a8", "k", "r")}


@dataclass(frozen=True)
class Lance:
    """Um lance da linha: como está impresso e em SAN inglês."""

    impresso: str
    san: str
    numero: Optional[int] = None
    pretas: bool = False
    #: `+`, `#` ou vazio, como impresso.
    marca: str = ""
    #: `!`, `?!`… como impresso.
    juizo: str = ""

    def rotulo(self) -> str:
        """`1.♘f3`, `10...Rf8`: o número que o lance tem ou teria, e o lance impresso."""
        if self.numero is None:
            return self.impresso
        return f"{self.numero}{'...' if self.pretas else '.'}{self.impresso}"


@dataclass(frozen=True)
class Validacao:
    """O que os lances do texto disseram do diagrama."""

    estado: str
    #: Quantos lances da primeira linha o texto tem, e quantos passaram.
    total: int
    legais: int
    aviso: str = ""
    #: O lado a jogar pelo número do primeiro lance ("w"/"b"), ou vazio.
    vez: str = ""
    numero: int = 1
    #: Os lances que passaram, em SAN, com o juízo (para o PGN).
    lances: Tuple[str, ...] = ()
    juizos: Tuple[str, ...] = ()

    @property
    def confiavel(self) -> bool:
        return self.estado == CONFIAVEL

    def para_json(self) -> dict:
        return {"estado": self.estado, "total": self.total, "legais": self.legais,
                "aviso": self.aviso, "vez": self.vez, "numero": self.numero,
                "lances": list(self.lances), "juizos": list(self.juizos)}

    @classmethod
    def de_json(cls, bruto: Optional[dict]) -> Optional["Validacao"]:
        if not bruto or bruto.get("estado") not in (CONFIAVEL, ILEGAL):
            return None
        try:
            lances = tuple(str(s) for s in bruto.get("lances", ()))
            juizos = tuple(str(s) for s in bruto.get("juizos", ())) or ("",) * len(lances)
            return cls(bruto["estado"], int(bruto.get("total", 0)), int(bruto.get("legais", 0)),
                       str(bruto.get("aviso", "")), str(bruto.get("vez", "")),
                       int(bruto.get("numero", 1) or 1), lances, juizos)
        except (TypeError, ValueError):         # derivada: a próxima edição a refaz
            return None


# ----------------------------------------------------------------------
# Ler a linha
# ----------------------------------------------------------------------

def _tabela(idioma: str) -> Dict[str, str]:
    """Letra do idioma -> letra inglesa; as figurinas -> letra inglesa."""
    from core.notacao import FIGURINAS

    from abbychess.modelo import PECAS

    tabela = dict(zip(PECAS.get(idioma, _INGLES), _INGLES))
    tabela.update(FIGURINAS)
    tabela["✝"] = "+"
    return tabela


def _em_san(nucleo: str, tabela: Dict[str, str]) -> Optional[re.Match]:
    """O lance do token em SAN inglês, ou `None` se o token não for lance."""
    convertido = "".join(tabela.get(c, c) for c in nucleo if c not in _PEOES)
    convertido = convertido.replace("0-0-0", "O-O-O").replace("0-0", "O-O")
    achado = _LANCE.match(convertido)
    if achado is None and (convertido[:1] in _INGLES or "x" in convertido):
        achado = _LANCE.match(_FILEIRA_1_DO_OCR.sub("1", convertido))
    return achado


def _numero(nucleo: str) -> Optional[re.Match]:
    """O número do lance no começo do token (`_NUMERO`), ou o lido pelo OCR com letras no
    lugar dos algarismos (`_NUMERO_DO_OCR`); o grupo 1 sai sempre em algarismos."""
    casado = _NUMERO.match(nucleo)
    if casado is not None:
        return casado
    casado = _NUMERO_DO_OCR.match(nucleo)
    if casado is None:
        return None
    cru, resto = casado.group(1), casado.group(3)
    if not resto and (not any(c.isdigit() for c in cru) or "I" in cru):
        return None                             # "lo." é palavra; "I." a inicial de um nome
    return _NUMERO.match(cru.translate(_ALGARISMOS_DO_OCR) + casado.group(2) + resto)


def _tokens(texto: str, idioma: str):
    """(tipo, valor) do texto: "numero" (n, pretas), "lance" Lance, "sinal", "prosa",
    "variante" (abre ou fecha) e "fim" (ponto e vírgula)."""
    tabela = _tabela(idioma)
    for palavra in _NUMERO_SEPARADO.sub(r"\1", texto).split():
        abre = palavra[:1] in "([{"
        nucleo = palavra.lstrip("([{")
        fecha = nucleo.rstrip(_BORDA)[-1:] in (")", "]", "}") if nucleo else False
        fim = ";" in nucleo
        # O ponto final fica até o número ser visto: "1." e "1..." soltos são números.
        nucleo = nucleo.replace(";", "").lstrip(_BORDA).rstrip(",:\"'“”‘’)]}")
        if abre:
            yield "variante", None
        numero = _numero(nucleo)
        if numero:
            yield "numero", (int(numero.group(1)), numero.group(2) != ".")
            nucleo = numero.group(3)
        yield from _token_do_nucleo(nucleo.rstrip(_BORDA + ")]}"), tabela)
        if fecha:
            yield "variante", None
        if fim:
            yield "fim", None


def _token_do_nucleo(nucleo: str, tabela: Dict[str, str]):
    """O token do que sobra da palavra sem o número e a pontuação: "lance", "sinal" ou
    "prosa"; nada, se não sobrou nada."""
    if not nucleo:
        return
    achado = _em_san(nucleo, tabela)
    if achado:
        san = achado.group("lance").replace(":", "x").replace("×", "x")
        impresso = nucleo.rstrip("!?‼⁇⁈⁉")
        yield "lance", Lance(impresso, san, marca=achado.group("marca"),
                             juizo=achado.group("juizo"))
    elif _SINAL.match(nucleo):
        yield "sinal", nucleo
    else:
        yield "prosa", nucleo


def primeira_linha(texto: str, idioma: str = "pt") -> List[Lance]:
    """Os lances da primeira linha do texto (ver o docstring do módulo)."""
    linha = _Linha()
    for tipo, valor in _tokens(texto, idioma):
        if linha.lance(valor) if tipo == "lance" else linha.outro(tipo, valor):
            break
    return linha.lances


class _Linha:
    """A primeira linha enquanto os tokens chegam: os lances aceitos, o número que o próximo
    lance teria e o que o livro imprimiu logo antes dele."""

    def __init__(self):
        self.lances: List[Lance] = []
        self.esperado: Optional[Tuple[int, bool]] = None
        self.numero: Optional[Tuple[int, bool]] = None
        self.colado = False              # o token anterior foi um lance aceito

    def outro(self, tipo: str, valor) -> bool:
        """O token que não é lance; True: ele acaba a linha."""
        if tipo == "sinal":
            return False
        if self._corta(tipo, valor):
            return True
        self.numero, self.colado = (valor if tipo == "numero" else None), False
        return False

    def _corta(self, tipo: str, valor) -> bool:
        """A variante, o ponto e vírgula e o número que não é o esperado acabam a linha
        começada (o livro volta a um lance que já passou)."""
        if not self.lances:
            return False
        if tipo == "numero":
            return valor != self.esperado
        return tipo in ("variante", "fim")

    def lance(self, valor: Lance) -> bool:
        """Põe o lance na linha, se ele tem número ou é a resposta das pretas logo depois do
        lance das brancas; True: ele acaba a linha."""
        if self.numero is not None:
            n, pretas = self.numero
        elif not (self.lances and self.colado):
            return False                        # lance solto na prosa
        elif self.esperado is not None and self.esperado[1]:
            n, pretas = self.esperado
        else:
            return True                         # lance das brancas sem número: outra coisa
        self.lances.append(Lance(valor.impresso, valor.san, n, pretas, valor.marca, valor.juizo))
        self.esperado = (n, True) if not pretas else (n + 1, False)
        self.numero, self.colado = None, True
        return False


# ----------------------------------------------------------------------
# Validar
# ----------------------------------------------------------------------

def roque_inferido(pecas: str) -> str:
    """Os direitos de roque que rei e torre nas casas iniciais sugerem ("KQkq", "Kq", "")."""
    board = chess.Board(None)
    board.set_board_fen(pecas.split()[0])
    saida = ""
    for letra, (casa_rei, casa_torre, rei, torre) in _ROQUE.items():
        p_rei = board.piece_at(chess.parse_square(casa_rei))
        p_torre = board.piece_at(chess.parse_square(casa_torre))
        if p_rei and p_torre and p_rei.symbol() == rei and p_torre.symbol() == torre:
            saida += letra
    return saida


def _tabuleiro(pecas: str, vez: str, roque: str, numero: int) -> chess.Board:
    board = chess.Board(None)
    board.set_board_fen(pecas.split()[0])
    board.turn = vez != "b"
    board.set_castling_fen(roque or "-")
    board.fullmove_number = max(1, numero)
    return board


def _contradiz(board: chess.Board, movimento: chess.Move, lance: Lance) -> str:
    """O que o lance diz e não faz aqui: vazio quando nada."""
    if "x" in lance.san and not board.is_capture(movimento):
        return "não captura nada aqui"
    if "#" in lance.marca or "+" in lance.marca:
        board.push(movimento)
        try:
            if "#" in lance.marca and not board.is_checkmate():
                return "não dá mate aqui"
            if "+" in lance.marca and not board.is_check():
                return "não dá xeque aqui"
        finally:
            board.pop()
    return ""


def validar(fen: str, linha: Sequence[Lance], *, lado: Optional[str] = None,
            roque: str = "", roque_informado: bool = False) -> Optional[Validacao]:
    """A validação de `linha` a partir do FEN (só as peças contam). `lado` é o que o
    diagrama diz ("w"/"b") ou `None`; `roque`, o conferido, e `roque_informado`, se quem
    conferiu o disse (vazio dito é "sem roque", não "o inferido"). Sem lances, `None`."""
    pecas = _pecas(fen)
    if not linha or not pecas:
        return None
    primeiro = linha[0]
    vez = "b" if primeiro.pretas else "w"
    numero = primeiro.numero or 1
    total = len(linha)
    if _lado_contrario(lado, vez):
        return Validacao(ILEGAL, total, 0, f"{primeiro.rotulo()} do texto diz que jogam "
                         f"{_QUEM[vez]}, mas o diagrama diz {_QUEM[lado]}", vez, numero)
    board = _tabuleiro_valido(pecas, vez, roque, roque_informado, numero)
    if board is None:
        return Validacao(ILEGAL, total, 0, "a posição lida não é legal com "
                         f"{_QUEM[vez]} a jogar", vez, numero)
    return _validar_os_lances(board, linha, vez, numero)


#: Quem joga, pelo lado ("w"/"b"), como os avisos o dizem.
_QUEM = {"w": "as brancas", "b": "as pretas"}


def _pecas(fen: Optional[str]) -> str:
    """O campo das peças do FEN (vazio sem FEN)."""
    return (fen or "").split()[0] if (fen or "").strip() else ""


def _lado_contrario(lado: Optional[str], vez: str) -> bool:
    """O diagrama diz um lado ("w"/"b") e o número do primeiro lance, o outro."""
    return lado in ("w", "b") and lado != vez


def _tabuleiro_valido(pecas: str, vez: str, roque: str, roque_informado: bool,
                      numero: int) -> Optional[chess.Board]:
    """O tabuleiro da posição lida, com o roque que vale; None se o FEN é malformado ou a
    posição não é legal."""
    # O roque marcado só vale onde rei e torre ainda estão (o editor pode guardar um que a
    # correção de uma casa desfez); sem ninguém dizer, vale o inferido.
    try:
        possiveis = roque_inferido(pecas)
        dito = roque if roque_informado or roque else possiveis
        roque = "".join(letra for letra in dito if letra in possiveis)
        board = _tabuleiro(pecas, vez, roque, numero)
    except ValueError:                          # FEN malformado
        return None
    return board if board.is_valid() else None


def _validar_os_lances(board: chess.Board, linha: Sequence[Lance], vez: str,
                       numero: int) -> Validacao:
    """Joga a linha no tabuleiro até o primeiro lance que não é legal ou diz o que não faz."""
    total = len(linha)
    sans, juizos = [], []
    for lance in linha:
        try:
            movimento = board.parse_san(lance.san)
            motivo = _contradiz(board, movimento, lance)
        except chess.AmbiguousMoveError:
            motivo = "é ambíguo aqui"
        except ValueError:
            motivo = "não é legal aqui"
        if motivo:
            return Validacao(ILEGAL, total, len(sans), f"{lance.rotulo()} do texto {motivo}",
                             vez, numero, tuple(sans), tuple(juizos))
        sans.append(board.san(movimento))
        juizos.append(lance.juizo)
        board.push(movimento)
    return Validacao(CONFIAVEL, total, total, "", vez, numero, tuple(sans), tuple(juizos))


# ----------------------------------------------------------------------
# A página
# ----------------------------------------------------------------------

def textos_depois(documento, modo: str = "impresso") -> Dict[str, str]:
    """O texto que segue cada diagrama do documento, até o próximo diagrama ou título."""
    from abbychess import texto as tx

    saida: Dict[str, str] = {}
    atual: Optional[str] = None
    partes: List[str] = []
    for bloco in documento.blocos:
        if bloco.diagrama_id is not None or bloco.funcao in FIM_DO_TEXTO:
            if atual is not None:
                saida[atual] = "\n".join(partes)
            atual, partes = bloco.diagrama_id, []
            continue
        if atual is None or bloco.funcao in FORA_DO_TEXTO:
            continue
        partes.append(tx.texto_do_bloco(documento, bloco, modo))
    if atual is not None:
        saida[atual] = "\n".join(partes)
    return saida


#: O texto depois dos diagramas das últimas páginas validadas, pela chave do que ele usa
#: (`_chave_do_texto`): `{chave: textos}`, do mais velho ao mais novo.
_TEXTOS_VISTOS: "OrderedDict[tuple, Dict[str, str]]" = OrderedDict()
_TRAVA_DOS_TEXTOS = threading.Lock()
#: Quantas páginas a cache guarda (a aberta, a do lote e as vizinhas).
TEXTOS_GUARDADOS = 8


def _chave_do_texto(pagina) -> Optional[tuple]:
    """O que o texto da página usa para ser montado (`texto.montar`): o caractere, a caixa, o
    ângulo e a moldura de cada glifo, as áreas, as decisões e os diagramas. A confiança e a fonte da
    leitura não entram: confirmar uma leitura (o Enter mais comum) não muda o texto. `None`
    se algo não for comparável (aí o texto é montado sempre)."""
    try:
        # `moldura`: o core faz da tabela emoldurada uma faixa só na ordem de leitura.
        chave = (tuple((b.gid, b.entry.char, b.entry.x1, b.entry.y1, b.entry.x2, b.entry.y2,
                        b.entry.angulo, getattr(b.entry, "moldura", False))
                       for b in pagina.boxes),
                 tuple(pagina.zonas), pagina.decisoes,
                 tuple((tuple(d.caixa), d.id) for d in pagina.diagramas))
        hash(chave)
    except TypeError:
        return None
    return chave


def _textos_da_pagina(pagina) -> Dict[str, str]:
    """`textos_depois(texto.montar(pagina))`, guardado pela chave do que ele usa: montar o
    texto da página custava ~25 ms em cada Enter (a validação é refeita em toda edição)."""
    from abbychess import texto as tx

    chave = _chave_do_texto(pagina)
    if chave is not None:
        with _TRAVA_DOS_TEXTOS:
            if chave in _TEXTOS_VISTOS:
                _TEXTOS_VISTOS.move_to_end(chave)
                return _TEXTOS_VISTOS[chave]
    textos = textos_depois(tx.montar(pagina))
    if chave is not None:
        with _TRAVA_DOS_TEXTOS:
            _TEXTOS_VISTOS[chave] = textos
            while len(_TEXTOS_VISTOS) > TEXTOS_GUARDADOS:
                _TEXTOS_VISTOS.popitem(last=False)
    return textos


def validar_pagina(pagina, idioma: str = "pt") -> list:
    """Os diagramas da página com a validação pelos lances do texto que segue cada um.

    É derivada, como o lado pela legenda: refeita depois de cada edição (`_mudou`) e
    gravada no diagrama para a fila, a aba Diagramas e o resumo do livro."""
    import copy

    from abbychess import diagramas as dg

    if not any(d.lido and d.id for d in pagina.diagramas):
        return _sem_validacao(pagina.diagramas)
    # O documento com todos os tabuleiros, os por ler também: o texto que segue um
    # diagrama ainda não lido não pode cair no anterior.
    copia = copy.copy(pagina)
    if pagina.tabuleiros:
        copia.diagramas = dg.com_ids(dg.para_caixas(pagina.tabuleiros, pagina.diagramas))
    textos = _textos_da_pagina(copia)
    return [_validado(d, textos, idioma) for d in pagina.diagramas]


def _sem_validacao(diagramas) -> list:
    """Os diagramas sem a validação nem o lado dos lances (a página não tem diagrama lido)."""
    from dataclasses import replace

    return [d if d.validacao is None and d.lado_origem != LADO_DOS_LANCES
            else _sem_lado_dos_lances(replace(d, validacao=None)) for d in diagramas]


def _validado(d, textos: Dict[str, str], idioma: str):
    """O diagrama com a validação pelos lances do texto que o segue."""
    from dataclasses import replace

    linha = primeira_linha(textos.get(d.id, ""), idioma) if d.lido and d.id else []
    dito = d.lado if d.lado_origem != LADO_DOS_LANCES else None
    validacao = (validar(d.fen, linha, lado=dito, roque=d.roque,
                         roque_informado=d.roque_informado) if linha else None)
    novo = d if d.validacao == validacao else replace(d, validacao=validacao)
    return novo if dito is not None else _lado_pelos_lances(novo, validacao, linha)


def _lado_pelos_lances(d, validacao: Optional[Validacao], linha: Sequence[Lance]):
    """O número do primeiro lance (`1...`) diz de quem é a vez quando ninguém disse: nem a
    legenda nem quem conferiu (conferir sem tocar no lado não o apaga)."""
    from dataclasses import replace

    if validacao is not None and validacao.vez:
        return replace(d, lado=validacao.vez, lado_origem=LADO_DOS_LANCES,
                       lado_trecho=linha[0].rotulo())
    return _sem_lado_dos_lances(d)


def _sem_lado_dos_lances(d):
    """O diagrama sem o lado que só os lances diziam (o texto mudou)."""
    from dataclasses import replace

    if d.lado_origem != LADO_DOS_LANCES:
        return d
    return replace(d, lado=None, lado_origem="", lado_trecho="")


# ----------------------------------------------------------------------
# PGN
# ----------------------------------------------------------------------

def _roque_usado(pecas: str, vez: str, numero: int, sans: Sequence[str]) -> str:
    """Os direitos de roque que a própria linha exerceu (o `O-O` do texto é prova)."""
    board = _tabuleiro(pecas, vez, roque_inferido(pecas), numero)
    usados = ""
    for san in sans:
        try:
            movimento = board.parse_san(san)
        except ValueError:                      # gravado com outra posição: pára aqui
            break
        if board.is_castling(movimento):
            ala = "K" if board.is_kingside_castling(movimento) else "Q"
            usados += ala if board.turn == chess.WHITE else ala.lower()
        board.push(movimento)
    return usados


def pgn_do_diagrama(diagrama, cabecalhos: Optional[Dict[str, str]] = None) -> str:
    """O PGN da posição do diagrama e dos lances validados que a seguem (SetUp/FEN).

    O FEN do PGN usa o lado do texto e o roque conferido mais o que a linha jogou; o
    inferido sozinho nunca entra (CA-10.3). Sem validação, só a posição; sem leitura, vazio."""
    if not diagrama.lido:
        return ""
    validacao = diagrama.validacao
    pecas = diagrama.fen.split()[0]
    vez_dos_lances, numero, sans, juizos = _do_texto(validacao)
    vez = vez_dos_lances or diagrama.lado or "w"
    conferido = set(diagrama.roque) & set(roque_inferido(pecas))
    roque = "".join(sorted(conferido | set(_roque_usado(pecas, vez, numero, sans)),
                           key="KQkq".index))
    board = _tabuleiro(pecas, vez, roque, numero)
    jogo = _jogo_vazio(cabecalhos)
    jogo.setup(board)
    no = _com_os_lances(jogo, sans, juizos)
    _comentar(jogo, no, validacao, diagrama.conferido)
    return str(jogo)


def _do_texto(validacao: Optional[Validacao]) -> Tuple[str, int, List[str], Sequence[str]]:
    """O lado, o número do primeiro lance, os lances e os juízos validados (sem validação: os
    de uma posição sem lances)."""
    if validacao is None:
        return "", 1, [], ()
    return validacao.vez, validacao.numero, list(validacao.lances), validacao.juizos


def _jogo_vazio(cabecalhos: Optional[Dict[str, str]]) -> chess.pgn.Game:
    """O jogo com os cabeçalhos obrigatórios do PGN e os dados que não são vazios."""
    jogo = chess.pgn.Game()
    for chave in ("Event", "Site", "Round", "White", "Black"):
        jogo.headers[chave] = "?"
    jogo.headers["Date"] = "????.??.??"
    jogo.headers["Result"] = "*"
    jogo.headers.update({k: v for k, v in (cabecalhos or {}).items() if v})
    return jogo


def _com_os_lances(jogo: chess.pgn.Game, sans: Sequence[str], juizos: Sequence[str]):
    """Os lances na linha principal do jogo, com o juízo em NAG; devolve o último nó."""
    no = jogo
    for san, juizo in zip(sans, juizos):
        try:
            no = no.add_variation(no.board().parse_san(san))
        except ValueError:                      # validação de outra posição: pára aqui
            break
        if juizo in _NAGS:
            no.nags.add(_NAGS[juizo])
    return no


def _comentar(jogo: chess.pgn.Game, no, validacao: Optional[Validacao], conferido: bool):
    """O aviso do lance que não passou, no último nó, e a posição não conferida, no jogo. Sem
    lance nenhum, o último nó é o jogo: os dois vão nele, a posição antes."""
    aviso = f"[{validacao.aviso}]" if validacao is not None and not validacao.confiavel else ""
    if not conferido:
        jogo.comment = ("posição lida, não conferida; " + NOMES[CONFIAVEL]
                        if validacao and validacao.confiavel else "posição lida, não conferida")
    if aviso:
        no.comment = "; ".join(c for c in (no.comment, aviso) if c)
