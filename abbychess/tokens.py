"""A unidade da medida e da fila Lances (SPEC da página perfeita, §1): o token, a classe dele, as
duas normalizações e o alinhamento. Sem Qt, e uma regra só: `classificar_token` usa as mesmas
funções de `lances`, para a fila, o F-3 e a medida nunca discordarem do que é um lance.

**Classes:** `LANCE`, `NUMERO`, `SINAL`, `FIGURINA` (figurina sem casa) e `PROSA`. O token é
partido em subtokens: abre, numero, nucleo, xeque, sinal e fecha.

**Normalização:** a literal (NFC e espaços colapsados) é a da página perfeita; a semântica, a
literal mais a figurina de qualquer cor como a letra da peça, os traços como `-`, as aspas retas,
`…` como `...` e `0-0` como `O-O`. `+-` e `±` seguem diferentes.

**Alinhamento:** `alinhar` é um só. No empate: troca, depois falta, depois sobra.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from abbychess import lances as lc
from abbychess.modelo import letras_das_pecas

LANCE, NUMERO, SINAL, FIGURINA, PROSA = "lance", "numero", "sinal", "figurina", "prosa"
LITERAL, SEMANTICA = "literal", "semantica"
_ABRE = "([{\"'“‘"
_FECHA = ")]},;:.\"'”’"
_BRANCAS = "♔♕♖♗♘♙"
_PRETAS = "♚♛♜♝♞♟"
_FIGURINAS = _BRANCAS + _PRETAS
_ORDEM_DAS_LETRAS = "KQRBN"
_TRACO_ENTRE = re.compile(r"(?<=[\w])[–—−](?=[\w])")
_ROQUE_COM_ZERO = re.compile(r"\b0-0(-0)?\b")
_ASPAS = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})
_FIGURINA_NA_LETRA = {f: p for f, p in zip(_BRANCAS + _PRETAS, "KQRBNPKQRBNP")}
#: O lance longo (`e2-e4`), hoje não aceito por `lances`: só contado (CA-X1.7).
_LANCE_LONGO = re.compile(r"^[a-h][1-8][-–—x:×][a-h][1-8]")


@dataclass(frozen=True)
class Token:
    """Um token classificado; os subtokens como impressos."""

    texto: str
    classe: str
    abre: str = ""
    numero: str = ""
    nucleo: str = ""
    xeque: str = ""
    sinal: str = ""
    fecha: str = ""
    #: A peça do lance, em inglês ("K", "Q", "R", "B", "N"; vazio: peão ou roque).
    peca: str = ""
    #: O lance em SAN inglês, sem xeque; vazio se não é lance.
    san: str = ""

    @property
    def forma_longa(self) -> bool:
        return bool(_LANCE_LONGO.match(self.texto.lstrip(_ABRE)))


def classificar_token(token: str, letras: str = "pt") -> Token:
    """A classe do token, por `lances._tabela(letras)`: as letras das peças (5, na ordem rei,
    dama, torre, bispo, cavalo) ou o idioma que as dá."""
    miolo = token.strip()
    abre = miolo[:len(miolo) - len(miolo.lstrip(_ABRE))]
    resto = miolo[len(abre):]
    corpo = resto.rstrip(_FECHA + "…") if not lc._numero(resto.rstrip(",;:\"'”’)]}")) else (
        resto.rstrip(",;:\"'”’)]}"))
    fecha = resto[len(corpo):]
    numero = lc._numero(corpo)
    if numero is not None:
        cru = corpo[:len(corpo) - len(numero.group(3))]
        nucleo = numero.group(3).rstrip(lc._BORDA + ")]}")
        fecha = numero.group(3)[len(nucleo):] + fecha
        if not nucleo:
            return Token(miolo, NUMERO, abre=abre, numero=cru, fecha=fecha)
    else:
        cru, nucleo = "", corpo
    return _do_nucleo(miolo, abre, cru, nucleo.lstrip(lc._BORDA), fecha, letras)


def _sem_lance(miolo, abre, numero, nucleo, fecha) -> Token:
    """O token sem forma de lance: sinal, figurina sem casa ou prosa."""
    if nucleo and lc._SINAL.match(nucleo):
        return Token(miolo, SINAL, abre=abre, numero=numero, sinal=nucleo, fecha=fecha)
    if nucleo and all(c in _FIGURINAS for c in nucleo):
        return Token(miolo, FIGURINA, abre=abre, numero=numero, nucleo=nucleo, fecha=fecha)
    if not nucleo and not numero:
        return Token(miolo, PROSA)
    return Token(miolo, PROSA, abre=abre, numero=numero, nucleo=nucleo, fecha=fecha)


def _do_nucleo(miolo, abre, numero, nucleo, fecha, letras) -> Token:
    achado = lc._em_san(nucleo, lc._tabela(letras)) if nucleo else None
    if achado is None:
        return _sem_lance(miolo, abre, numero, nucleo, fecha)
    san = achado.group("lance").replace(":", "x").replace("×", "x")
    sinal = achado.group("juizo") + achado.group("avaliacao")
    sem_sinal = nucleo[:len(nucleo) - len(sinal)] if sinal else nucleo
    marca = sem_sinal[len(sem_sinal.rstrip("+#†‡✝")):]
    return Token(miolo, LANCE, abre=abre, numero=numero, nucleo=sem_sinal[:len(sem_sinal) - len(marca)],
                 xeque=marca, sinal=sinal, fecha=fecha, san=san,
                 peca=san[0] if san[0] in _ORDEM_DAS_LETRAS else "")


def normalizar(texto: str, modo: str = LITERAL, letras: str = "pt") -> str:
    """O texto em uma das duas leituras (o módulo diz quais)."""
    saida = " ".join(unicodedata.normalize("NFC", texto).split())
    if modo == LITERAL:
        return saida
    pecas = letras_das_pecas(letras)
    saida = "".join(_letra_da_figurina(c, pecas) for c in saida)
    saida = _TRACO_ENTRE.sub("-", saida).translate(_ASPAS).replace("…", "...")
    return _ROQUE_COM_ZERO.sub(lambda m: "O-O-O" if m.group(1) else "O-O", saida)


def _letra_da_figurina(c: str, pecas: str) -> str:
    peca = _FIGURINA_NA_LETRA.get(c)
    if peca is None:
        return c
    return "" if peca == "P" else pecas[_ORDEM_DAS_LETRAS.index(peca)]


def alinhar(verdade: Sequence, lida: Sequence) -> List[Tuple[Optional[int], Optional[int]]]:
    """O alinhamento de edição mínima: pares `(i, j)`, `(i, None)` (falta na lida) e `(None, j)`
    (sobra na lida), na ordem. No empate: troca, depois falta, depois sobra."""
    n, m = len(verdade), len(lida)
    custos = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        custos[i][0] = i
    for j in range(m + 1):
        custos[0][j] = j
    for i in range(1, n + 1):
        linha, acima = custos[i], custos[i - 1]
        for j in range(1, m + 1):
            linha[j] = min(acima[j - 1] + (verdade[i - 1] != lida[j - 1]), acima[j] + 1, linha[j - 1] + 1)
    return _caminho(custos, verdade, lida)


def _caminho(custos, verdade, lida) -> List[Tuple[Optional[int], Optional[int]]]:
    i, j, pares = len(verdade), len(lida), []
    while i or j:
        if i and j and custos[i][j] == custos[i - 1][j - 1] + (verdade[i - 1] != lida[j - 1]):
            i, j = i - 1, j - 1
            pares.append((i, j))
        elif i and custos[i][j] == custos[i - 1][j] + 1:
            i -= 1
            pares.append((i, None))
        else:
            j -= 1
            pares.append((None, j))
    pares.reverse()
    return pares


@dataclass(frozen=True)
class Avaliado:
    """Um token da verdade contra a leitura (SPEC, §1): certo, ou o tipo do erro."""

    token: Token
    #: "" (certo), "troca", "falta", "espaco" ou "sumiu".
    erro: str = ""
    #: O texto lido alinhado a ele, e os índices dele na leitura normalizada.
    lido: str = ""
    indices_lidos: Tuple[int, ...] = ()

    @property
    def certo(self) -> bool:
        return not self.erro


def avaliar_a_linha(verdade: str, lida: str, letras: str = "pt", modo: str = SEMANTICA
                    ) -> List[Avaliado]:
    """Cada token da verdade, depois de normalizar, contra a linha lida. Token certo: todos os
    caracteres alinhados são iguais, e ele corresponde a exatamente um token lido."""
    verdade, lida = normalizar(verdade, modo, letras), normalizar(lida, modo, letras)
    donos_v, donos_l = _donos(verdade), _donos(lida)
    saida = []
    pares = alinhar(verdade, lida)
    for n, palavra in enumerate(verdade.split()):
        alinhados = [(i, j) for i, j in pares if i is not None and donos_v[i] == n]
        erro, texto = _erro_do_token(alinhados, verdade, lida, donos_l, pares, donos_v)
        saida.append(Avaliado(classificar_token(palavra, letras), erro, texto,
                              tuple(j for _i, j in alinhados if j is not None)))
    return saida


def _donos(texto: str) -> List[Optional[int]]:
    """De cada caractere, o índice do token dele; None nos espaços."""
    donos: List[Optional[int]] = []
    n = -1
    fora = True
    for c in texto:
        if c == " ":
            donos.append(None)
            fora = True
        else:
            n += fora
            fora = False
            donos.append(n)
    return donos


def _erro_do_token(alinhados, verdade, lida, donos_l, pares, donos_v) -> Tuple[str, str]:
    lidos = [j for _i, j in alinhados if j is not None]
    if not lidos:
        return "sumiu", ""
    texto = "".join(lida[j] for j in lidos)
    if _erro_de_espaco(lidos, donos_l, pares, donos_v):
        return "espaco", texto
    return _erro_nos_caracteres(alinhados, verdade, lida, lidos, donos_l), texto


def _erro_nos_caracteres(alinhados, verdade, lida, lidos, donos_l) -> str:
    """"falta", "troca" (um caractere diferente, ou o token lido com caractere a mais), ou certo."""
    if any(j is None for _i, j in alinhados):
        return "falta"
    if any(verdade[i] != lida[j] for i, j in alinhados):
        return "troca"
    return "troca" if donos_l.count(donos_l[lidos[0]]) != len(lidos) else ""


def _erro_de_espaco(lidos, donos_l, pares, donos_v) -> bool:
    """O token caiu em mais de um lido (partido), ou outro da verdade caiu no mesmo (colados)."""
    tokens_lidos = {donos_l[j] for j in lidos}
    if None in tokens_lidos or len(tokens_lidos) > 1:
        return True
    dono = next(iter(tokens_lidos))
    colados = {donos_v[i] for i, j in pares
               if i is not None and j is not None and donos_l[j] == dono}
    return len(colados - {None}) > 1
