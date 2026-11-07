"""A posição ao longo da página, sem rebobinar (X-1, SPEC da página perfeita §6.1): quais tokens de
lance têm posição conhecida, e qual é o primeiro ilegal de cada sequência. Sem Qt.

**Sementes.** O FEN do diagrama lido, quando a linha o segue. Sem diagrama, `1.` abre a posição
inicial **como hipótese**: vale se os dois primeiros lances são legais nela. A `semente` de quem
chama (o estado do fim da página anterior, na passada de livro) também vale.

**Sincronia, sem rebobinar (M2).** A posição só anda enquanto o número for o esperado. Número que
volta, `(`, `;`, ou lance das brancas sem número: a posição se perde, e tudo fica sem posição, sem
marca, até o próximo diagrama. **Nunca se marca lance sem posição,** e só o primeiro ilegal de cada
sequência é marcado. PP7 troca essa perda pela rebobinada.

**Saída.** Nada é trocado: `decodificar` só diz o estado de cada token. A regra do que é lance é a
de `tokens.classificar_token`, a mesma da fila e da medida.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import chess

from abbychess import lances as lc
from abbychess import texto as tx
from abbychess import tokens as tk

LEGAL, ILEGAL, SEM_POSICAO = "legal", "ilegal", "sem_posicao"
DIAGRAMA, INICIAL, ANTERIOR = "diagrama", "inicial", "anterior"
#: Quantos lances legais confirmam a hipótese da posição inicial.
LANCES_DA_HIPOTESE = 2
#: CA-F4.11: em 05/11, 6 dos 107 tokens de lance errados (5,6 %) ficavam em linha fora da fila,
#: acima dos 5 %: a fila inclui a linha vizinha. Exploratório; o ponto de parada de M2 revê.
COM_AS_VIZINHAS = True
_XEQUE_MARCA = str.maketrans({"†": "+", "‡": "+", "✝": "+"})


@dataclass(frozen=True)
class LanceLido:
    """Um token de lance da página e o que a posição diz dele."""

    gids: Tuple[int, ...]
    gids_do_numero: Tuple[int, ...]
    impresso: str
    san: str
    estado: str
    motivo: str = ""
    #: De onde veio a posição: `DIAGRAMA`, `INICIAL`, `ANTERIOR`; vazio sem posição.
    semente: str = ""


@dataclass
class Decodificada:
    lances: List[LanceLido] = field(default_factory=list)
    #: A posição e o número esperado no fim da página, para a passada de livro; None sem posição.
    final: Optional[Tuple[str, Tuple[int, bool]]] = None

    @property
    def ilegais(self) -> List[LanceLido]:
        return [t for t in self.lances if t.estado == ILEGAL]

    @property
    def com_posicao(self) -> int:
        return sum(t.estado != SEM_POSICAO for t in self.lances)

    def por_semente(self) -> Dict[str, int]:
        saida: Dict[str, int] = {}
        for t in self.lances:
            if t.semente and t.estado != SEM_POSICAO:
                saida[t.semente] = saida.get(t.semente, 0) + 1
        return saida


@dataclass(frozen=True)
class PalavraLida:
    """Uma palavra de texto da página: os gids dela e o token classificado."""

    gids: Tuple[int, ...]
    token: tk.Token

    @property
    def inicio_do_miolo(self) -> int:
        return len(self.token.abre) + len(self.token.numero)

    @property
    def miolo(self) -> str:
        return self.token.nucleo + self.token.xeque + self.token.sinal


def palavras_de_texto(documento, chave: str):
    """(bloco, linha, as `PalavraLida` da linha) do texto corrido: sem cabeçalho, rodapé, legenda
    nem número de página. Cada caractere leva ao gid dele (o glifo pode ter mais de um)."""
    normal = tx.normalizador(tx.IMPRESSO)
    for bloco in documento.blocos:
        if bloco.diagrama_id is not None or bloco.funcao in lc.FORA_DO_TEXTO:
            continue
        for linha in bloco.linhas:
            yield bloco, linha, [_palavra_lida(p, documento, normal, chave) for p in linha.palavras]


def _palavra_lida(palavra, documento, normal, chave: str) -> PalavraLida:
    gids: List[int] = []
    letras: List[str] = []
    for g in palavra.gids:
        char = documento.chars.get(g, "")
        texto = tx.NAO_LIDO if char == tx.NAO_LIDO else (normal(char) or tx.NAO_LIDO)
        letras.append(texto)
        gids.extend([g] * len(texto))
    return PalavraLida(tuple(gids), tk.classificar_token("".join(letras), chave))


class _Posicao:
    """A posição enquanto os tokens chegam."""

    def __init__(self, semente: Optional[Tuple[str, Tuple[int, bool]]]):
        self.board: Optional[chess.Board] = None
        self.esperado: Optional[Tuple[int, bool]] = None
        self.origem = ""
        self.numero: Optional[Tuple[int, bool]] = None
        self.colado = False
        self.fen_do_diagrama: Optional[str] = None
        #: Os lances legais da hipótese, ainda por confirmar (índices em `lances`).
        self.hipotese: Optional[List[int]] = None
        #: O primeiro lance depois do diagrama: só ele pode ser en passant sem o lance anterior.
        self.recem_do_diagrama = False
        #: Veio um diagrama, lido ou não: a posição é dele, e não a inicial por hipótese.
        self.sem_hipotese = False
        if semente is not None:
            self.board = chess.Board(semente[0])
            self.esperado, self.origem = semente[1], ANTERIOR

    def perder(self) -> None:
        self.board, self.esperado, self.numero, self.colado = None, None, None, False
        self.origem, self.fen_do_diagrama = "", None


def decodificar(documento, diagramas: Sequence, chave: str = "pt",
                semente: Optional[Tuple[str, Tuple[int, bool]]] = None) -> Decodificada:
    """O estado de cada token de lance da página (o módulo diz as regras)."""
    por_id = {d.id: d for d in diagramas}
    saida = Decodificada()
    estado = _Posicao(semente)
    for bloco in documento.blocos:
        if bloco.diagrama_id is not None:
            _no_diagrama(estado, saida, por_id.get(bloco.diagrama_id))
        elif bloco.funcao in lc.FIM_DO_TEXTO:
            _desfazer_a_hipotese(estado, saida)
            estado.perder()
        elif bloco.funcao not in lc.FORA_DO_TEXTO:
            _no_bloco(estado, saida, bloco, documento, chave)
    _desfazer_a_hipotese(estado, saida)
    if estado.board is not None and estado.esperado is not None:
        saida.final = (estado.board.fen(), estado.esperado)
    return saida


def _no_diagrama(estado: _Posicao, saida: Decodificada, diagrama) -> None:
    _desfazer_a_hipotese(estado, saida)
    estado.perder()
    estado.sem_hipotese = True                  # depois de um diagrama, `1.` não é o início do jogo
    if diagrama is not None and getattr(diagrama, "lido", False) and diagrama.fen:
        estado.fen_do_diagrama = diagrama.fen.split()[0]


def _no_bloco(estado: _Posicao, saida: Decodificada, bloco, documento, chave: str) -> None:
    normal = tx.normalizador(tx.IMPRESSO)
    for linha in bloco.linhas:
        for palavra in linha.palavras:
            _na_palavra(estado, saida, _palavra_lida(palavra, documento, normal, chave))


def _na_palavra(estado: _Posicao, saida: Decodificada, p: PalavraLida) -> None:
    token = p.token
    if "(" in token.abre or "[" in token.abre or "{" in token.abre:
        _desfazer_a_hipotese(estado, saida)
        estado.perder()
    if token.numero:
        _no_numero(estado, saida, token.numero)
    if token.classe == tk.LANCE:
        _no_lance(estado, saida, p)
    elif token.classe == tk.PROSA:
        estado.numero, estado.colado = None, False
    if any(c in token.fecha for c in ")]};"):
        _desfazer_a_hipotese(estado, saida)
        estado.perder()


def _no_numero(estado: _Posicao, saida: Decodificada, numero: str) -> None:
    casado = lc._numero(numero)
    if casado is None:
        return
    visto = (int(casado.group(1)), casado.group(2) != ".")
    if estado.board is None:
        _semear(estado, visto)
    elif visto != estado.esperado:
        _desfazer_a_hipotese(estado, saida)
        estado.perder()
        return
    estado.numero = visto


def _semear(estado: _Posicao, visto: Tuple[int, bool]) -> None:
    """O número sem posição: abre a do diagrama que veio antes, ou a hipótese da inicial."""
    if estado.fen_do_diagrama is not None:
        estado.board = _do_diagrama(estado.fen_do_diagrama, visto)
        achou = estado.board is not None
        estado.origem = DIAGRAMA if achou else ""
        estado.recem_do_diagrama = achou
        estado.esperado = visto if achou else None
        estado.fen_do_diagrama = estado.fen_do_diagrama if achou else None
    elif visto == (1, False) and not estado.sem_hipotese:
        estado.board, estado.esperado = chess.Board(), visto
        estado.origem, estado.hipotese = INICIAL, []


def _do_diagrama(pecas: str, visto: Tuple[int, bool]) -> Optional[chess.Board]:
    vez = "b" if visto[1] else "w"
    return lc._tabuleiro_valido(pecas, vez, "", False, visto[0])


def _no_lance(estado: _Posicao, saida: Decodificada, p: PalavraLida) -> None:
    if estado.board is None or estado.esperado is None:
        _anotar(saida, p, SEM_POSICAO)
        return
    if estado.numero is None:
        if not estado.colado:                       # o lance solto na prosa: não é a linha
            _anotar(saida, p, SEM_POSICAO)
            return
        if not estado.esperado[1]:                  # o lance das brancas sem número: outra coisa
            _anotar(saida, p, SEM_POSICAO)
            _desfazer_a_hipotese(estado, saida)
            estado.perder()
            return
    _jogar(estado, saida, p)


def _jogar(estado: _Posicao, saida: Decodificada, p: PalavraLida) -> None:
    token = p.token
    n, pretas = estado.esperado
    lance = lc.Lance(token.nucleo, token.san, n, pretas, token.xeque.translate(_XEQUE_MARCA))
    if estado.recem_do_diagrama:
        lc._com_en_passant(estado.board, token.san)
        estado.recem_do_diagrama = False
    motivo = _motivo(estado.board, lance)
    if motivo:
        if estado.hipotese is not None:
            _anotar(saida, p, SEM_POSICAO)
            _desfazer_a_hipotese(estado, saida, confirmada=False)
            estado.perder()
            return
        _anotar(saida, p, ILEGAL, f"{token.nucleo} {motivo}", estado.origem)
        estado.perder()                             # os seguintes ficam sem posição
        return
    estado.board.push_san(token.san)
    _anotar(saida, p, LEGAL, semente=estado.origem)
    if estado.hipotese is not None:
        estado.hipotese.append(len(saida.lances) - 1)
        if len(estado.hipotese) >= LANCES_DA_HIPOTESE:
            estado.hipotese = None                  # confirmada
    estado.esperado = (n, True) if not pretas else (n + 1, False)
    estado.numero, estado.colado = None, True


def _motivo(board: chess.Board, lance: lc.Lance) -> str:
    """Por que o lance não vale aqui; vazio se vale (a regra de `lances._validar_os_lances`)."""
    try:
        return lc._contradiz(board, board.parse_san(lance.san), lance)
    except chess.AmbiguousMoveError:
        return "é ambíguo aqui"
    except ValueError:
        return "não se joga aqui"


def _desfazer_a_hipotese(estado: _Posicao, saida: Decodificada, confirmada: bool = False) -> None:
    """A hipótese da posição inicial que não se confirmou: os lances dela ficam sem posição."""
    if estado.hipotese is None or confirmada:
        return
    for k in estado.hipotese:
        t = saida.lances[k]
        saida.lances[k] = LanceLido(t.gids, t.gids_do_numero, t.impresso, t.san, SEM_POSICAO)
    estado.hipotese = None
    estado.perder()


def _anotar(saida: Decodificada, p: PalavraLida, estado: str, motivo: str = "",
            semente: str = "") -> None:
    token, inicio = p.token, p.inicio_do_miolo
    fim = inicio + len(p.miolo)
    saida.lances.append(LanceLido(_unicos(p.gids[inicio:fim]),
                                  _unicos(p.gids[len(token.abre):inicio]), token.nucleo, token.san,
                                  estado, motivo, semente))


def _unicos(gids: Sequence[int]) -> Tuple[int, ...]:
    return tuple(dict.fromkeys(gids))


@dataclass(frozen=True)
class LinhaDeLance:
    """Uma linha da fila Lances: os gids dela e os de número, lance, xeque e sinal."""

    gids: Tuple[int, ...]
    gids_de_lance: Tuple[int, ...]
    texto: str
    tem_lance: bool


def linhas_da_fila(documento, chave: str = "pt") -> List[LinhaDeLance]:
    """As linhas com forma de lance na leitura, as que estão entre duas assim (F-4) e, com
    `COM_AS_VIZINHAS`, as vizinhas delas."""
    linhas = [_linha_de_lance(linha, palavras)
              for _bloco, linha, palavras in palavras_de_texto(documento, chave)]
    fila = _indices_da_fila([ln.tem_lance for ln in linhas])
    return [ln for k, ln in enumerate(linhas) if k in fila]


def _indices_da_fila(tem_lance: Sequence[bool]) -> set:
    """Quais linhas entram: as com lance, a entre duas assim e, se ligado, as vizinhas."""
    com = [k for k, tem in enumerate(tem_lance) if tem]
    entre = {a + 1 for a, b in zip(com, com[1:]) if b - a == 2}
    vizinhas = {v for k in com for v in (k - 1, k + 1)} if COM_AS_VIZINHAS else set()
    return set(com) | entre | vizinhas


def _linha_de_lance(linha, palavras: Sequence[PalavraLida]) -> LinhaDeLance:
    return LinhaDeLance(tuple(g for p in linha.palavras for g in p.gids),
                        tuple(g for p in palavras for g in _gids_de_lance(p)),
                        " ".join(p.token.texto for p in palavras),
                        any(p.token.classe == tk.LANCE for p in palavras))


def _gids_de_lance(p: PalavraLida) -> Tuple[int, ...]:
    """O que a conferência marca na palavra: número, lance, xeque e sinal; a prosa fica."""
    token = p.token
    if token.classe not in (tk.LANCE, tk.NUMERO, tk.SINAL):
        return ()
    inicio = len(token.abre)
    return _unicos(p.gids[inicio:inicio + len(token.numero) + len(p.miolo)])


def lances_por_conferir(documento, revisados_ou_confirmados, chave: str = "pt") -> int:
    """Quantos tokens de lance têm algum glifo por conferir (nem `manual`, `revisado`, `nativa`)."""
    total = 0
    for _bloco, _linha, palavras in palavras_de_texto(documento, chave):
        for p in palavras:
            if p.token.classe == tk.LANCE and not all(
                    g in revisados_ou_confirmados for g in _gids_de_lance(p)):
                total += 1
    return total
