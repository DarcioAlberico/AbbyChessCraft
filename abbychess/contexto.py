"""A leitura improvável pela palavra: o glifo lido com confiança que a palavra desmente.

A rede e a base global leem cada glifo sozinho, e num livro escaneado elas trocam com
confiança alta o `o` por `0`, o `l` por `1`, o `s` por `S`: "c0l0ca", "dific11ltar",
"anteS". Com a confiança acima do limiar de revisão, esses glifos não iam para a fila, e a
propagação dos padrões do livro nunca os relia; no replay da fatia eram 48 dos 217 glifos
ensinados (`docs/revisoes/ca-f1-investigacao.md`).

Aqui a palavra decide. Um glifo é improvável quando:

- é um algarismo (ou uma série deles) entre letras, no começo de uma palavra seguido de duas
  letras ou mais, ou no fim depois de duas letras ou mais ("c0l0ca", "1ibera", "muit0");
- é uma maiúscula logo depois de uma minúscula, numa palavra mais minúscula do que
  maiúscula ("anteS", "CavaIo");
- é uma minúscula entre maiúsculas ("VITORlOSO").

Nada disso vale na palavra que é um lance ("Tae1+", "Cxh2", "12.h3+"): ali algarismo e letra
se misturam de propósito. O glifo improvável vai para a revisão mesmo com confiança alta,
inclusive o lido por um padrão do livro (o padrão foi ensinado noutro contexto: um `1` de
"1.e4" lendo o `l` de uma palavra). Só o que o usuário confirmou (manual, revisado) e o texto
nativo do PDF não voltam.

O contrário também (Mirkovic, *Chess School 1*, onde o `1` e o `l` da fonte quase não
diferem): **a letra onde o lance ou o número pede algarismo** — "l.♗h7!", "♕el", "♖adl",
"l0.f3", "l6l9" — é improvável, e a sugestão é o algarismo. Só quando a troca faz da palavra
um lance com figurina ou algarismo de verdade, ou um número: o "el" do espanhol fica.

E a linha decide o que a palavra não vê (`_pela_linha`), pelo desenho igual em dois tamanhos
ou em duas alturas, e pela palavra seguinte (o "l" solto antes de "...d3" é o número):

- **a vírgula no alto da linha é apóstrofo** ("pawn,s", "couldn,t"), e o apóstrofo encostado
  na base é vírgula ("Linares' 2005"): na fonte do Mirkovic os dois são o mesmo glifo;
- **a minúscula do tamanho das maiúsculas é maiúscula** ("white moves", "oPPOSITIoN"), e o
  contrário, nas letras de mesmo desenho nas duas caixas (c, o, s, v, w, x, z).

A página decide a figurina larga demais (`_figurinas_largas`): as figurinas de um livro têm
todas a mesma largura, e a que passa disso engoliu a letra colada nela ("♘f4" lido "♘4" na
p. 88 do Mirkovic, com confiança alta). Ela não tem sugestão: a revisão a divide.

Cada improvável traz a sugestão quando há uma (`sugestoes`): o painel a põe no campo e o
Enter a ensina.
"""

from __future__ import annotations

import re
import threading
from types import MappingProxyType
from typing import Collection, Dict, FrozenSet, List, Optional, Sequence, Tuple

#: Um lance em SAN, com as letras das peças em inglês e em português (a figurina vira a letra
#: antes, `core.notacao.FIGURINAS`), o número do lance antes e a pontuação depois: a casa
#: ("Cxh2", "a8=D", "exd6e.p."), a troca entre peças ("NxN", "DxD+") ou o roque. Basta
#: reconhecer a palavra, não validar o lance.
_LANCE = re.compile(r"^[(\[]?(\d+\.+)?([KQRBNDTCP]?[a-h]?[1-8]?[x:]?[a-h][1-8](=?[KQRBNDTC])?"
                    r"(e\.p\.)?|[KQRBNDTCP][x:][KQRBNDTCP]|[O0][-–—][O0]([-–—][O0])?)"
                    r"[+#‡†]*[!?]*[)\],.;:]*$")


def _e_lance(chars: Sequence[str]) -> bool:
    from core.notacao import FIGURINAS

    return bool(_LANCE.match("".join(FIGURINAS.get(c, c) for c in chars)))


def _tipo(c: str) -> str:
    """'d' algarismo, 'M' maiúscula, 'm' minúscula, 'o' o resto (pontuação, vazio, símbolo)."""
    if c and c.isdigit():
        return "d"
    if c and c.isalpha():
        if c.isupper():
            return "M"
        if c.islower():
            return "m"
    return "o"


def _letras_seguidas(tipos: Sequence[str], inicio: int, passo: int) -> int:
    n, k = 0, inicio
    while 0 <= k < len(tipos) and tipos[k] in "Mm":
        n, k = n + 1, k + passo
    return n


#: A letra que um algarismo parece, para a sugestão do algarismo entre letras ("c0l0ca").
_LETRA_DO_ALGARISMO = {"0": "o", "1": "l", "5": "s"}
#: O algarismo que cada letra parece, para a letra onde o lance ou o número pede algarismo.
_ALGARISMO_DA_LETRA = {"l": "1", "I": "1", "|": "1", "O": "0", "o": "0"}
#: Um número solto: o ano ("1997", "1619"), o número do lance ("10."), entre parênteses.
_NUMERO = re.compile(r"^[(\[]?\d{1,4}[.,;:)\]]*$")


def _algarismos_pedidos(chars: Sequence[str]) -> List[Optional[str]]:
    """Para cada glifo, o algarismo que a palavra pede no lugar da letra lida, ou None: só
    quando trocar as letras-algarismo faz da palavra um lance com figurina ou algarismo de
    verdade ("l.♗h7!", "♕el", "l0.f3") ou um número com algarismo de verdade ("l997")."""
    from core.notacao import FIGURINAS

    trocas = [_ALGARISMO_DA_LETRA.get(c) for c in chars]
    nada = [None] * len(chars)
    if not any(trocas) or _e_lance(chars):
        return nada
    trocada = [t or c for t, c in zip(trocas, chars)]
    com_algarismo = any(c and c.isdigit() for c in chars)
    com_figurina = any(c in FIGURINAS for c in chars)
    if _e_lance(trocada) and (com_algarismo or com_figurina):
        return trocas
    if com_algarismo and _NUMERO.match("".join(trocada)):
        return trocas
    return nada


def _na_outra_caixa(c: str, maiuscula: bool) -> str:
    """A letra trocada de caixa, com o I e o l que se confundem pelo desenho."""
    if maiuscula:
        return "I" if c == "l" else c.upper()
    return "l" if c == "I" else c.lower()


def julgar_palavra(chars: Sequence[str]) -> List[Optional[str]]:
    """Para cada glifo da palavra: None se ele é provável; senão a sugestão ("" sem uma)."""
    saida: List[Optional[str]] = [None] * len(chars)
    algarismos = _algarismos_pedidos(chars)
    if any(algarismos):
        return algarismos
    if _e_lance(chars):
        return saida
    tipos = [_tipo(c) for c in chars]
    maiuscula = tipos.count("M") > tipos.count("m")
    k = 0
    while k < len(tipos):
        if tipos[k] != "d":
            k += 1
            continue
        fim = k
        while fim + 1 < len(tipos) and tipos[fim + 1] == "d":
            fim += 1
        antes = _letras_seguidas(tipos, k - 1, -1)
        depois = _letras_seguidas(tipos, fim + 1, 1)
        if (antes and depois) or (k == 0 and depois >= 2) or (fim == len(tipos) - 1 and antes >= 2):
            for j in range(k, fim + 1):
                letra = _LETRA_DO_ALGARISMO.get(chars[j], "")
                saida[j] = _na_outra_caixa(letra, True) if letra and maiuscula else letra
        k = fim + 1
    minuscula = tipos.count("m") > tipos.count("M")     # "anteS", e não "VITORlOSO"
    for k in range(1, len(tipos)):
        if minuscula and tipos[k] == "M" and tipos[k - 1] == "m":
            saida[k] = _na_outra_caixa(chars[k], False)
        elif (tipos[k] == "m" and tipos[k - 1] == "M" and k + 1 < len(tipos)
              and tipos[k + 1] == "M"):
            saida[k] = _na_outra_caixa(chars[k], True)
    return saida


def improvaveis_na_palavra(chars: Sequence[str]) -> List[bool]:
    """Para cada glifo da palavra (o caractere de cada box, em ordem), se ele é improvável."""
    return [s is not None for s in julgar_palavra(chars)]


# ----------------------------------------------------------------------
# A linha: o mesmo desenho em dois tamanhos ou em duas alturas
# ----------------------------------------------------------------------

#: As letras de mesmo desenho nas duas caixas: só o tamanho diz qual é.
CAIXA_PELO_TAMANHO = frozenset("cosvwxzCOSVWXZ")
#: As letras cuja minúscula não tem haste: o tamanho delas diz a caixa, mesmo quando o
#: desenho também diria (a sugestão da palavra não troca a caixa que a altura confirma).
_CAIXA_NA_ALTURA = frozenset("acemnorsuvwxzACEMNORSUVWXZ")
#: As referências da altura das maiúsculas (sem as de desenho igual, que podem estar trocadas,
#: e sem as que descem) e a da altura do x (as minúsculas sem haste nem cauda).
_ALTAS = frozenset("ABDEFGHIKLMNPRTUYbdhkl")
_BAIXAS = frozenset("aemnru")
_QUE_DESCEM = frozenset("gjpqyQJ,;()[]{}")
#: Quantas linhas da página precisam medir as duas alturas para a razão entre elas valer.
LINHAS_DA_RAZAO = 3
#: Abaixo disto (maiúscula / x), a linha não separa as caixas pelo tamanho.
RAZAO_QUE_SEPARA = 1.2
_APOSTROFOS = frozenset("'’‘")


def _medidas(entries) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """(altura das maiúsculas, altura do x, linha de base) da linha, pelas letras dela."""
    from statistics import median

    altas = [e.y2 - e.y1 for e in entries if e.char in _ALTAS]
    baixas = [e.y2 - e.y1 for e in entries if e.char in _BAIXAS]
    base = [e.y2 for e in entries if e.char and e.char[:1].isalnum()
            and e.char not in _QUE_DESCEM]
    return (median(altas) if len(altas) >= 2 else None,
            median(baixas) if len(baixas) >= 2 else None,
            median(base) if len(base) >= 2 else None)


def _pela_linha(linhas: Sequence[Sequence[Sequence[int]]], por_gid) -> Tuple[dict, dict]:
    """({gid: sugestão}, {gid: maiúscula pela altura}): os glifos que a linha desmente (a
    vírgula no alto e o apóstrofo na base, a letra de `CAIXA_PELO_TAMANHO` do tamanho da outra
    caixa) e, para as letras de `_CAIXA_NA_ALTURA`, a caixa que a altura delas diz."""
    medidas = []
    for linha in linhas:
        pares = [(g, por_gid[g]) for p in linha for g in p if g in por_gid]
        medidas.append((pares, _medidas([e for _g, e in pares])))
    # A razão da página completa a linha que só mede uma das alturas ("oPPOSITIoN", sem
    # minúscula de referência), e só com `LINHAS_DA_RAZAO` linhas que medem as duas.
    razoes = sorted(x / m for _p, (m, x, _b) in medidas if m and x)
    razao = razoes[len(razoes) // 2] if len(razoes) >= LINHAS_DA_RAZAO else None
    saida, alturas = {}, {}
    for pares, (maiuscula, x, base) in medidas:
        if (maiuscula is None or x is None) and (razao is None or (maiuscula, x) == (None, None)):
            continue
        maiuscula = maiuscula or x / razao
        x = x or maiuscula * razao
        if base is not None and x:
            for g, e in pares:
                if e.char == "," and e.y2 < base - 0.5 * x:
                    saida[g] = "'"
                elif e.char in _APOSTROFOS and e.y2 > base - 0.25 * x:
                    saida[g] = ","
        if maiuscula < RAZAO_QUE_SEPARA * x:
            continue
        for g, e in pares:
            if e.char not in _CAIXA_NA_ALTURA:
                continue
            altura = e.y2 - e.y1
            if altura >= x + 0.6 * (maiuscula - x):
                alturas[g] = True
            elif altura <= x + 0.4 * (maiuscula - x):
                alturas[g] = False
            if e.char not in CAIXA_PELO_TAMANHO or alturas.get(g) is None:
                continue
            if e.char.islower() and alturas[g]:
                saida[g] = e.char.upper()
            elif e.char.isupper() and not alturas[g]:
                saida[g] = e.char.lower()
    return saida, alturas


def _numeros_soltos(linhas: Sequence[Sequence[Sequence[int]]], char) -> Dict[int, str]:
    """{gid: algarismo} da letra solta que é o número do lance das pretas logo depois,
    separado das reticências ("l ...d3", `lances._NUMERO_SEPARADO`)."""
    saida = {}
    for linha in linhas:
        for palavra, seguinte in zip(linha, linha[1:]):
            chars = [char[g] for g in palavra]
            numero = "".join(_ALGARISMO_DA_LETRA.get(c, c) for c in chars)
            if not numero.isdigit() or numero.startswith("0"):    # "o ...Cf6" é o artigo
                continue
            depois = "".join(char[g] for g in seguinte)
            lance = depois.lstrip(".…")
            if len(depois) - len(lance) >= 2 or depois.startswith("…"):
                if lance and _e_lance(list(lance)):
                    saida.update((g, _ALGARISMO_DA_LETRA[c]) for g, c in zip(palavra, chars)
                                 if c in _ALGARISMO_DA_LETRA)
    return saida


#: Quanto a figurina pode passar da largura das outras iguais da página, em frações da altura
#: dela: as do Mirkovic variam 2 px em 36, e uma letra colada acrescenta pelo menos um "l".
FOLGA_DA_FIGURINA = 0.2
#: Quantas figurinas iguais a página precisa ter para a mediana delas medir a largura; com
#: menos, a medida é a de todas as figurinas da página.
FIGURINAS_DA_MEDIDA = 3


def _figurinas_largas(pagina) -> FrozenSet[int]:
    """Os gids das figurinas mais largas que as outras da página (`FOLGA_DA_FIGURINA`)."""
    from statistics import median

    from core.notacao import FIGURINAS

    figurinas = [b for b in pagina.boxes if b.entry.char and b.entry.char in FIGURINAS]
    if len(figurinas) < FIGURINAS_DA_MEDIDA:
        return frozenset()
    larguras: Dict[str, List[int]] = {}
    for b in figurinas:
        larguras.setdefault(b.entry.char, []).append(b.entry.x2 - b.entry.x1)
    todas = median(w for ws in larguras.values() for w in ws)
    saida = set()
    for b in figurinas:
        e = b.entry
        iguais = larguras[e.char]
        medida = median(iguais) if len(iguais) >= FIGURINAS_DA_MEDIDA else todas
        if e.x2 - e.x1 > medida + FOLGA_DA_FIGURINA * (e.y2 - e.y1):
            saida.add(b.gid)
    return frozenset(saida)


#: As últimas páginas julgadas: chave -> {gid: sugestão}, a mais recente no fim. A fila da
#: janela pergunta várias vezes por ação (~2–3 ms cada numa página do livro); a chave custa
#: uma fração disso. Mais de uma: o resumo da página gravada (`improvaveis_da_lista`, com os
#: gids provisórios) julgava no meio, e a fila seguinte refazia a conta.
_JULGADAS: dict = {}
_GUARDADAS = 4
_TRAVA = threading.Lock()


def _chave(pagina) -> tuple:
    """O que a regra lê: o caractere e a caixa de cada glifo, e as decisões de palavra."""
    return (tuple((b.gid, b.entry.char, b.entry.x1, b.entry.y1, b.entry.x2, b.entry.y2,
                   getattr(b.entry, "angulo", 0)) for b in pagina.boxes), pagina.decisoes)


def julgar(pagina) -> Dict[int, str]:
    """{gid: sugestão} dos glifos improváveis da página (`modelo.Pagina`), pelas palavras e
    pelas linhas do Documento (`texto.linhas_dos_gids`); a sugestão é "" quando não há uma."""
    from abbychess import texto as tx

    chave = _chave(pagina)
    with _TRAVA:
        if (julgada := _JULGADAS.pop(chave, None)) is not None:
            _JULGADAS[chave] = julgada
            return julgada
    char = {b.gid: b.entry.char for b in pagina.boxes}
    char.update({v.gid: v.char for v in pagina.decisoes.virtuais})
    linhas = tx.linhas_dos_gids(pagina)
    saida, alturas = _pela_linha(linhas, {b.gid: b.entry for b in pagina.boxes
                                          if b.entry.char})
    for palavra in (p for ln in linhas for p in ln):
        for gid, sugestao in zip(palavra, julgar_palavra([char[g] for g in palavra])):
            if sugestao is None or (gid in saida and not sugestao):
                continue
            atual = char[gid]
            if (sugestao and sugestao.lower() == atual.lower() and sugestao != atual
                    and alturas.get(gid) == atual.isupper()):
                # "whereWhite": o W tem a altura de maiúscula; o que falta é o espaço.
                sugestao = ""
            saida[gid] = sugestao
    saida.update(_numeros_soltos(linhas, char))
    saida.update((g, "") for g in _figurinas_largas(pagina) if g not in saida)
    julgada = MappingProxyType(saida)
    with _TRAVA:
        _JULGADAS[chave] = julgada
        while len(_JULGADAS) > _GUARDADAS:
            del _JULGADAS[next(iter(_JULGADAS))]
    return julgada


def improvaveis(pagina) -> FrozenSet[int]:
    """Os gids dos glifos improváveis da página (`julgar`)."""
    return frozenset(julgar(pagina))


def sugestoes(pagina) -> Dict[int, str]:
    """{gid: o caractere que o contexto sugere} dos improváveis que têm sugestão."""
    return {g: s for g, s in julgar(pagina).items() if s}


_DESENHOS_IGUAIS = ({",", "'", "’", "‘"}, {"l", "I", "|", "1"})


def mesmo_desenho(lido: str, sugestao: str) -> bool:
    """Se o caractere lido e o sugerido têm o mesmo desenho (a vírgula e o apóstrofo, as duas
    caixas de `CAIXA_PELO_TAMANHO`, o l e o 1): ensinar o padrão faria o livro ler
    todos os outros como a sugestão, e a troca é "só esta"."""
    if lido in CAIXA_PELO_TAMANHO and sugestao == lido.swapcase():
        return True
    return any(lido in grupo and sugestao in grupo for grupo in _DESENHOS_IGUAIS)


def volta_pelo_contexto(fonte: str) -> bool:
    """Se um glifo improvável dessa fonte vai para a revisão: tudo menos o confirmado pelo
    usuário e o texto nativo."""
    from abbychess.leitor import FONTE_MANUAL, FONTE_NATIVA

    return fonte not in (FONTE_MANUAL, FONTE_NATIVA)


def improvaveis_da_lista(boxes) -> List[bool]:
    """Para cada `BoxEntry` da lista (a página inteira), se a palavra o desmente e ele volta
    à revisão por isso (`volta_pelo_contexto`)."""
    from abbychess import texto as tx

    pagina = tx.pagina_avulsa(list(boxes))
    contra = improvaveis(pagina)
    return [b.gid in contra and volta_pelo_contexto(b.entry.source) for b in pagina.boxes]


def _pendentes(pagina, limiares, revisados: Sequence[bool]) -> List[bool]:
    from abbychess.leitor import precisa_revisao

    contra = improvaveis(pagina)
    return [not revisado and (precisa_revisao(b.entry.char, b.entry.source, b.entry.confidence,
                                              limiares)
                              or (b.gid in contra and volta_pelo_contexto(b.entry.source)))
            for b, revisado in zip(pagina.boxes, revisados)]


def pendentes(boxes, limiares, revisados: Optional[Sequence[bool]] = None) -> List[bool]:
    """Para cada `BoxEntry` da lista, se ele vai para a revisão: `precisa_revisao` ou
    improvável pela palavra. A lista é a página inteira (as palavras saem dela)."""
    from abbychess import texto as tx

    return _pendentes(tx.pagina_avulsa(list(boxes)), limiares,
                      revisados or [False] * len(boxes))


def pendentes_da_pagina(pagina, limiares, *, com_os_revisados: bool = False) -> List[bool]:
    """`pendentes` para os `Box` da página do modelo, pelos gids dela (as linhas guardadas
    do Documento servem). Com `com_os_revisados`, o revisado também conta, como na leitura
    dos pendentes, que relê pela confiança sem olhar a revisão; sem, ele sai, como na fila."""
    revisados = [False if com_os_revisados else b.revisado for b in pagina.boxes]
    return _pendentes(pagina, limiares, revisados)


def _do_lote(pagina, lidas: Collection[str], novo: str, fora: Collection[int]) -> List[bool]:
    from abbychess import texto as tx

    julgados = julgar(pagina)
    contra = {g for g, sugestao in julgados.items() if not sugestao or sugestao == novo}
    candidatos = {b.gid for b in pagina.boxes
                  if b.gid in contra and b.gid not in fora and b.entry.char
                  and b.entry.char in lidas and not b.revisado
                  and volta_pelo_contexto(b.entry.source)}
    if not candidatos:
        return [False] * len(pagina.boxes)
    # A troca tem de deixar o glifo provável na palavra: o "0" de "C0L0CA" não vira "o".
    char = {b.gid: b.entry.char for b in pagina.boxes}
    char.update({v.gid: v.char for v in pagina.decisoes.virtuais})
    provaveis = set()
    for palavra in tx.palavras_dos_gids(pagina):
        trocados = [g for g in palavra if g in candidatos]
        if trocados:
            na_palavra = improvaveis_na_palavra([novo if g in candidatos else char[g]
                                                 for g in palavra])
            provaveis.update(g for g, improvavel in zip(palavra, na_palavra)
                             if g in candidatos and not improvavel)
    return [b.gid in provaveis for b in pagina.boxes]


def lote(pagina, lidas: Collection[str], novo: str, fora: Collection[int] = ()) -> List[int]:
    """A confusão do livro corrigida em lote (Ctrl+Enter no Glifo): os gids da página lidos
    como um dos caracteres de `lidas` que a palavra desmente e que, trocados por `novo`,
    deixam de ser improváveis; menos os de `fora` (os ensinados). Ficam de fora o que o
    usuário confirmou (manual, revisado) e o nativo: o "0" de "c0l0ca" entra; o de "1.e4",
    o de "10" e o de "C0L0CA" (com `novo` "o"), não."""
    return [b.gid for b, sim in zip(pagina.boxes, _do_lote(pagina, lidas, novo, set(fora)))
            if sim]


def lote_da_lista(boxes, lidas: Collection[str], novo: str,
                  fora: Collection[int] = ()) -> List[int]:
    """`lote` para a lista de `BoxEntry` da página inteira: os índices, e `fora` também."""
    from abbychess import texto as tx

    pagina = tx.pagina_avulsa(list(boxes))
    fora = {pagina.boxes[i].gid for i in fora}
    return [i for i, sim in enumerate(_do_lote(pagina, lidas, novo, fora)) if sim]
