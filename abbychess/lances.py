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

**As letras são as do idioma do livro** (`sessao.PECAS`: `Cf3` em português é `Nf3`) e as
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

import random
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

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

    from abbychess.sessao import PECAS

    tabela = dict(zip(PECAS.get(idioma, _INGLES), _INGLES))
    tabela.update(FIGURINAS)
    tabela["✝"] = "+"
    return tabela


def _em_san(nucleo: str, tabela: Dict[str, str]) -> Optional[re.Match]:
    """O lance do token em SAN inglês, ou `None` se o token não for lance."""
    convertido = "".join(tabela.get(c, c) for c in nucleo if c not in _PEOES)
    convertido = convertido.replace("0-0-0", "O-O-O").replace("0-0", "O-O")
    return _LANCE.match(convertido)


def _tokens(texto: str, idioma: str):
    """(tipo, valor) do texto: "numero" (n, pretas), "lance" Lance, "sinal", "prosa",
    "variante" (abre ou fecha) e "fim" (ponto e vírgula)."""
    tabela = _tabela(idioma)
    for palavra in texto.split():
        abre = palavra[:1] in "([{"
        nucleo = palavra.lstrip("([{")
        fecha = nucleo.rstrip(_BORDA)[-1:] in (")", "]", "}") if nucleo else False
        fim = ";" in nucleo
        # O ponto final fica até o número ser visto: "1." e "1..." soltos são números.
        nucleo = nucleo.replace(";", "").lstrip(_BORDA).rstrip(",:\"'“”‘’)]}")
        if abre:
            yield "variante", None
        numero = _NUMERO.match(nucleo)
        if numero:
            yield "numero", (int(numero.group(1)), numero.group(2) != ".")
            nucleo = numero.group(3)
        nucleo = nucleo.rstrip(_BORDA + ")]}")
        if nucleo:
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
        if fecha:
            yield "variante", None
        if fim:
            yield "fim", None


def primeira_linha(texto: str, idioma: str = "pt") -> List[Lance]:
    """Os lances da primeira linha do texto (ver o docstring do módulo)."""
    linha: List[Lance] = []
    esperado: Optional[Tuple[int, bool]] = None
    numero: Optional[Tuple[int, bool]] = None
    colado = False                   # o token anterior foi um lance aceito
    for tipo, valor in _tokens(texto, idioma):
        if tipo in ("variante", "fim"):
            if linha:
                break
            numero, colado = None, False
        elif tipo == "sinal":
            continue
        elif tipo == "prosa":
            numero, colado = None, False
        elif tipo == "numero":
            if linha and valor != esperado:
                break
            numero, colado = valor, False
        else:                                   # lance
            if numero is not None:
                n, pretas = numero
            elif linha and colado and esperado is not None and esperado[1]:
                n, pretas = esperado
            elif linha and colado:
                break                           # lance das brancas sem número: outra coisa
            else:
                continue                        # lance solto na prosa
            linha.append(Lance(valor.impresso, valor.san, n, pretas, valor.marca, valor.juizo))
            esperado = (n, True) if not pretas else (n + 1, False)
            numero, colado = None, True
    return linha


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
    pecas = (fen or "").split()[0] if (fen or "").strip() else ""
    if not linha or not pecas:
        return None
    primeiro = linha[0]
    vez = "b" if primeiro.pretas else "w"
    numero = primeiro.numero or 1
    total = len(linha)
    if lado in ("w", "b") and lado != vez:
        quem = {"w": "as brancas", "b": "as pretas"}
        return Validacao(ILEGAL, total, 0, f"{primeiro.rotulo()} do texto diz que jogam "
                         f"{quem[vez]}, mas o diagrama diz {quem[lado]}", vez, numero)
    # O roque marcado só vale onde rei e torre ainda estão (o editor pode guardar um que a
    # correção de uma casa desfez); sem ninguém dizer, vale o inferido.
    try:
        possiveis = roque_inferido(pecas)
        dito = roque if roque_informado or roque else possiveis
        roque = "".join(letra for letra in dito if letra in possiveis)
        board = _tabuleiro(pecas, vez, roque, numero)
    except ValueError:                          # FEN malformado
        board = None
    if board is None or not board.is_valid():
        return Validacao(ILEGAL, total, 0, "a posição lida não é legal com "
                         f"{'as pretas' if vez == 'b' else 'as brancas'} a jogar", vez, numero)
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
    """O que o texto da página usa para ser montado (`texto.montar`): o caractere, a caixa e
    o ângulo de cada glifo, as áreas, as decisões e os diagramas. A confiança e a fonte da
    leitura não entram: confirmar uma leitura (o Enter mais comum) não muda o texto. `None`
    se algo não for comparável (aí o texto é montado sempre)."""
    try:
        chave = (tuple((b.gid, b.entry.char, b.entry.x1, b.entry.y1, b.entry.x2, b.entry.y2,
                        b.entry.angulo) for b in pagina.boxes),
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
    from dataclasses import replace

    from abbychess import diagramas as dg

    if not any(d.lido and d.id for d in pagina.diagramas):
        return [d if d.validacao is None and d.lado_origem != LADO_DOS_LANCES
                else _sem_lado_dos_lances(replace(d, validacao=None)) for d in pagina.diagramas]
    # O documento com todos os tabuleiros, os por ler também: o texto que segue um
    # diagrama ainda não lido não pode cair no anterior.
    copia = copy.copy(pagina)
    if pagina.tabuleiros:
        copia.diagramas = dg.com_ids(dg.para_caixas(pagina.tabuleiros, pagina.diagramas))
    textos = _textos_da_pagina(copia)
    saida = []
    for d in pagina.diagramas:
        linha = primeira_linha(textos.get(d.id, ""), idioma) if d.lido and d.id else []
        dito = d.lado if d.lado_origem != LADO_DOS_LANCES else None
        validacao = (validar(d.fen, linha, lado=dito, roque=d.roque,
                             roque_informado=d.roque_informado) if linha else None)
        novo = d if d.validacao == validacao else replace(d, validacao=validacao)
        if not novo.conferido and dito is None:
            # O número do primeiro lance (`1...`) diz de quem é a vez quando ninguém disse.
            if validacao is not None and validacao.vez:
                novo = replace(novo, lado=validacao.vez, lado_origem=LADO_DOS_LANCES,
                               lado_trecho=linha[0].rotulo())
            else:
                novo = _sem_lado_dos_lances(novo)
        saida.append(novo)
    return saida


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
    vez = (validacao.vez if validacao else "") or diagrama.lado or "w"
    numero = validacao.numero if validacao else 1
    sans = list(validacao.lances) if validacao else []
    conferido = set(diagrama.roque) & set(roque_inferido(pecas))
    roque = "".join(sorted(conferido | set(_roque_usado(pecas, vez, numero, sans)),
                           key="KQkq".index))
    board = _tabuleiro(pecas, vez, roque, numero)
    jogo = chess.pgn.Game()
    for chave in ("Event", "Site", "Round", "White", "Black"):
        jogo.headers[chave] = "?"
    jogo.headers["Date"] = "????.??.??"
    jogo.headers["Result"] = "*"
    jogo.headers.update({k: v for k, v in (cabecalhos or {}).items() if v})
    jogo.setup(board)
    no = jogo
    for san, juizo in zip(sans, validacao.juizos if validacao else ()):
        try:
            no = no.add_variation(no.board().parse_san(san))
        except ValueError:                      # validação de outra posição: pára aqui
            break
        if juizo in _NAGS:
            no.nags.add(_NAGS[juizo])
    if validacao is not None and not validacao.confiavel:
        no.comment = f"[{validacao.aviso}]"
    if not diagrama.conferido:
        jogo.comment = ("posição lida, não conferida; " + NOMES[CONFIAVEL]
                        if validacao and validacao.confiavel else "posição lida, não conferida")
    return str(jogo)


# ----------------------------------------------------------------------
# As perturbações (CA-10.1)
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class Perturbacao:
    #: A posição perturbada (só as peças), de onde veio e o que mudou.
    pecas: str
    origem: int
    tipo: str
    casas: Tuple[str, ...]


_TIPOS = ("trocada", "tirada", "movida")


def perturbar(pecas: str, vez: str, rng: random.Random, origem: int = 0,
              tentativas: int = 500) -> Optional[Perturbacao]:
    """Uma versão da posição com uma peça trocada, tirada ou movida, ainda legal com `vez`
    a jogar (sem roque). `None` se nenhuma tentativa der posição legal."""
    original = chess.Board(None)
    original.set_board_fen(pecas.split()[0])
    for _ in range(tentativas):
        board = original.copy()
        tipo = rng.choice(_TIPOS)
        ocupadas = sorted(board.piece_map())
        sem_rei = [c for c in ocupadas if board.piece_type_at(c) != chess.KING]
        vazias = [c for c in chess.SQUARES if c not in board.piece_map()]
        if tipo == "trocada" and sem_rei:
            casa = rng.choice(sem_rei)
            antiga = board.piece_at(casa)
            nova = chess.Piece(rng.choice([chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK,
                                           chess.QUEEN]), rng.choice([chess.WHITE, chess.BLACK]))
            if nova == antiga:
                continue
            board.set_piece_at(casa, nova)
            casas = (chess.square_name(casa),)
        elif tipo == "tirada" and sem_rei:
            casa = rng.choice(sem_rei)
            board.remove_piece_at(casa)
            casas = (chess.square_name(casa),)
        elif tipo == "movida" and vazias:
            de, para = rng.choice(ocupadas), rng.choice(vazias)
            board.set_piece_at(para, board.remove_piece_at(de))
            casas = (chess.square_name(de), chess.square_name(para))
        else:
            continue
        board.turn = vez != "b"
        if board.is_valid():
            return Perturbacao(board.board_fen(), origem, tipo, casas)
    return None


def perturbacoes(posicoes: Sequence[Tuple[str, str]], n: int = 100,
                 semente: int = 1234) -> List[Perturbacao]:
    """`n` perturbações das posições `(peças, vez)`, uma de cada por vez, com a semente."""
    rng = random.Random(semente)
    saida: List[Perturbacao] = []
    if not posicoes:
        return saida
    falhas = 0
    while len(saida) < n and falhas < 10 * n:
        origem = len(saida) % len(posicoes)
        pecas, vez = posicoes[origem]
        p = perturbar(pecas, vez, rng, origem)
        if p is None:
            falhas += 1
            continue
        saida.append(p)
    return saida


def casas_dos_lances(pecas: str, vez: str, sans: Sequence[str], numero: int = 1) -> List[set]:
    """As casas que cada lance usa, na posição verdadeira: de onde sai, aonde chega, o
    caminho, e a torre no roque. É o "lance afetado" do CA-10.1: uma perturbação que toca
    uma dessas casas afeta o lance."""
    board = _tabuleiro(pecas, vez, roque_inferido(pecas), numero)
    saida: List[set] = []
    for san in sans:
        movimento = board.parse_san(san)
        casas = {movimento.from_square, movimento.to_square}
        casas |= set(chess.SquareSet.between(movimento.from_square, movimento.to_square))
        if board.is_castling(movimento):
            torre = movimento.to_square if board.chess960 else (
                chess.H1 if movimento.to_square == chess.G1 else
                chess.A1 if movimento.to_square == chess.C1 else
                chess.H8 if movimento.to_square == chess.G8 else chess.A8)
            casas |= {torre} | set(chess.SquareSet.between(movimento.from_square, torre))
        if board.is_en_passant(movimento):
            casas.add(chess.square(chess.square_file(movimento.to_square),
                                   chess.square_rank(movimento.from_square)))
        saida.append({chess.square_name(c) for c in casas})
        board.push(movimento)
    return saida


def afetada(p: Perturbacao, casas: Iterable[set]) -> bool:
    """A perturbação toca alguma casa usada por um lance da linha."""
    tocadas = set(p.casas)
    return any(tocadas & c for c in casas)
