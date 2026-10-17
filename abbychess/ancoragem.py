"""Onde os glifos virtuais da sessão do Documento ficam na página (SPEC §6.3, passo D1).

A página monta as palavras dos boxes (o core) e põe cada virtual logo depois (ou logo antes)
da âncora dele (`texto._aplicar_decisoes`). Depois de uma sessão, `ancorar` dá a cada virtual
a âncora que o põe onde o usuário o digitou:

- **Numa palavra com box**: o virtual vem logo depois do glifo anterior da palavra; o
  primeiro, logo antes do primeiro box dela.
- **Numa palavra só de virtuais** (`palavra_nova`): uma palavra nova logo depois da palavra
  anterior da mesma linha impressa da sessão; sem ela, antes do primeiro box de uma seguinte
  da mesma linha; sem as duas, ao lado da palavra de fora da sessão na mesma linha
  (`vizinhos_de_fora`, só um glifo cuja cadeia de âncoras não entra na sessão, ou o ciclo
  fecharia); sem ela, a vizinha mais perto em outra linha (uma linha só existe com boxes).
- **Os virtuais de fora da sessão ancorados num glifo dela** (a palavra só de virtuais logo
  depois ou logo antes da sessão): ficam logo depois da última palavra da sessão na linha
  deles (ou antes da primeira).

E `como_digitado`: tirar um box deixa um vão (ou fecha um) e o core pode partir ou juntar
palavras ali; as junções e quebras voltam a palavra ao que o usuário digitou.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from abbychess import edicao as ed
from abbychess.modelo import Pagina


def palavras_da_sequencia(sequencia, linha_original: Dict[int, int]
                           ) -> List[Tuple[int, List[int]]]:
    """As palavras do texto novo, em gids, e a linha impressa de cada uma: a do primeiro
    glifo dela que já existia; a palavra só de letras novas fica na linha da palavra
    anterior, ou na da seguinte se a quebra de linha impressa vem antes dela."""
    palavras: List[List[int]] = []
    depois_da_linha: List[bool] = []
    atual: List[int] = []
    quebra = False
    for item, gid in list(sequencia) + [("espaco", None)]:
        if item == "glifo":
            atual.append(gid)
            continue
        if atual:
            palavras.append(atual)
            depois_da_linha.append(quebra)
            atual, quebra = [], False
        if item == "linha":
            quebra = True
    linhas: List[Optional[int]] = [next((linha_original[g] for g in p if g in linha_original),
                                        None) for p in palavras]
    conhecidas = list(linhas)
    for n in range(len(palavras)):
        if linhas[n] is not None:
            continue
        anterior = next((conhecidas[k] for k in range(n - 1, -1, -1)
                         if conhecidas[k] is not None), None)
        seguinte = next((conhecidas[k] for k in range(n + 1, len(palavras))
                         if conhecidas[k] is not None), None)
        if depois_da_linha[n] and seguinte is not None:
            linhas[n] = seguinte
        elif anterior is not None:
            linhas[n] = anterior
        else:
            linhas[n] = seguinte if seguinte is not None else 0
    return list(zip(linhas, palavras))


def ancorar(pagina: Pagina, sequencia, boxes_que_saem: Set[int],
             linha_original: Dict[int, int]) -> None:
    """Os virtuais como o usuário os deixou no texto novo. Em cada palavra, o virtual vem
    logo depois do glifo anterior dela; o primeiro, logo antes do primeiro box da palavra.
    Numa palavra só de virtuais, o primeiro abre uma palavra nova logo depois da palavra
    anterior da mesma linha impressa (ou antes do primeiro box da seguinte). E os virtuais
    de fora da sessão ancorados num box que sai (a palavra só de virtuais logo depois ou
    logo antes dela) passam ao vizinho que fica, na mesma linha."""
    virtuais = {v.gid: v for v in pagina.decisoes.virtuais}
    palavras = palavras_da_sequencia(sequencia, linha_original)
    na_sessao = {g for _linha, p in palavras for g in p} | set(linha_original)
    ancoras: Dict[int, Tuple[Optional[int], Optional[int], bool]] = {}

    def fica_fora(gid: int) -> bool:
        """O glifo de fora cujo lugar não depende da sessão: a cadeia das âncoras dele não
        entra nela (senão, ancorar a sessão nele fecharia um ciclo)."""
        vistos = set()
        while gid in virtuais:
            if gid in na_sessao or gid in vistos:
                return False
            vistos.add(gid)
            v = virtuais[gid]
            gid = v.depois_de if v.depois_de is not None else v.antes_de
            if gid is None:
                return True
            if gid in boxes_que_saem or gid in na_sessao:
                return False
        return True

    def de_fora(linha: int) -> Tuple[Optional[int], Optional[int]]:
        return vizinhos_de_fora(pagina, linha_original, linha, na_sessao, fica_fora)

    for n, (linha, palavra) in enumerate(palavras):
        caixas = [g for g in palavra if g not in virtuais]
        for k, gid in enumerate(palavra):
            if gid not in virtuais:
                continue
            if k:
                ancoras[gid] = (palavra[k - 1], None, False)
            elif caixas:
                ancoras[gid] = (None, caixas[0], False)
            else:
                ancoras[gid] = palavra_nova(palavras, n, linha, virtuais, de_fora)
    for v in virtuais.values():
        if v.gid in na_sessao or not palavras:
            continue
        apos = v.depois_de is not None
        ancora = v.depois_de if apos else v.antes_de
        if ancora not in na_sessao:
            continue
        # A palavra só de virtuais logo depois (ou antes) da sessão, ancorada num glifo
        # dela: fica logo depois da última palavra da sessão nesta linha (ou antes da
        # primeira), como a sessão a deixou.
        linha = linha_original.get(ancora, 0)
        mesma = [p for lp, p in palavras if lp == linha]
        if mesma:
            ancoras[v.gid] = ((mesma[-1][-1], None, v.palavra_nova) if apos
                              else (None, mesma[0][0], v.palavra_nova))
            continue
        antes, depois = de_fora(linha)          # a sessão saiu toda desta linha
        ancoras[v.gid] = (antes, None, True) if antes is not None else (None, depois, True)
    if ancoras:
        ed.ancorar(pagina, ancoras)


def vizinhos_de_fora(pagina: Pagina, linha_original: Dict[int, int], linha: int,
                      na_sessao: Set[int], fica_fora) -> Tuple[Optional[int], Optional[int]]:
    """Na página montada agora: o último glifo de fora da sessão antes dela e o primeiro
    depois dela, na linha impressa `linha` da sessão; se a linha não tem nenhum (a sessão
    era a linha toda, e uma linha só existe com boxes), os mais perto nas outras linhas. Só
    os glifos que `fica_fora` aceita."""
    from abbychess import texto as tx

    alvo = {g for g, lp in linha_original.items() if lp == linha}
    palavras = [(id(ln), list(p.gids)) for bloco in tx.montar(pagina, com_os_nao_lidos=True).blocos
                for ln in bloco.linhas for p in ln.palavras]
    dentro = [k for k, (_ln, p) in enumerate(palavras) if any(g in alvo for g in p)]
    if not dentro:
        return None, None
    a, b = dentro[0], dentro[-1]
    fora = [(ln, [g for g in p if g not in na_sessao and fica_fora(g)]) for ln, p in palavras]
    mesma = palavras[a][0]
    antes = next((p[-1] for ln, p in reversed(fora[:a]) if p and ln == mesma), None)
    depois = next((p[0] for ln, p in fora[b + 1:] if p and ln == mesma), None)
    if antes is None and depois is None:
        antes = next((p[-1] for _ln, p in reversed(fora[:a]) if p), None)
        depois = next((p[0] for _ln, p in fora[b + 1:] if p), None)
    return antes, depois


def palavra_nova(palavras, n: int, linha: int, virtuais, de_fora
                  ) -> Tuple[Optional[int], Optional[int], bool]:
    """A âncora da palavra `n`, só de virtuais: depois da palavra anterior da mesma linha;
    sem ela, antes do primeiro box de uma seguinte da mesma linha; sem as duas, depois (ou
    antes) da palavra de fora da sessão na mesma linha (`de_fora`); sem elas, a vizinha mais
    perto em outra linha."""
    anterior = next((p for lp, p in reversed(palavras[:n]) if lp == linha), None)
    if anterior is not None:
        return anterior[-1], None, True
    seguinte = next((g for lp, p in palavras[n + 1:] if lp == linha for g in p
                     if g not in virtuais), None)
    if seguinte is not None:
        return None, seguinte, True
    antes, depois = de_fora(linha)
    if antes is not None:
        return antes, None, True
    if depois is not None:
        return None, depois, True
    if n:
        return palavras[n - 1][1][-1], None, True
    seguinte = next((g for _lp, p in palavras[n + 1:] for g in p if g not in virtuais), None)
    return None, seguinte, True


def pagina_montada(pagina: Pagina):
    """A página montada agora: gid -> (bloco, linha, palavra), e os gids de cada palavra."""
    from abbychess import texto as tx

    onde: Dict[int, Tuple[int, int, int]] = {}
    montadas: Dict[Tuple[int, int, int], List[int]] = {}
    for b, bloco in enumerate(tx.montar(pagina, com_os_nao_lidos=True).blocos):
        for n, linha in enumerate(bloco.linhas):
            for k, palavra in enumerate(linha.palavras):
                montadas[(b, n, k)] = list(palavra.gids)
                for g in palavra.gids:
                    onde[g] = (b, n, k)
    return onde, montadas


def como_digitado(pagina: Pagina, sequencia, na_sessao: Set[int],
                  antes: Dict[int, Tuple[int, int, int]]) -> None:
    """Tirar um box deixa um vão (ou fecha um) na página, e a montagem do core pode partir
    ou juntar palavras ali (o vão entre palavras é medido na linha). Onde ela partiu uma
    palavra que o usuário digitou inteira, os boxes são juntados de novo (na mesma linha
    impressa); onde ela juntou duas que ele digitou separadas, ou uma da sessão com a vizinha
    de fora, a palavra nova é marcada; e as palavras de fora da sessão voltam a ser as de
    `antes` (a página montada antes de o box sair)."""
    onde, montadas = pagina_montada(pagina)
    boxes = pagina.vivos
    linhas: Dict[Tuple[int, int], List[int]] = {}
    for (b, n, _k), gids in sorted(montadas.items()):  # os boxes de cada linha, em ordem
        linhas.setdefault((b, n), []).extend(g for g in gids if g in boxes)
    for linha in linhas.values():               # as palavras de fora, como eram
        for a, b in zip(linha, linha[1:]):
            if a in na_sessao or b in na_sessao or a not in antes or b not in antes:
                continue
            if antes[a] == antes[b] and onde[a] != onde[b]:
                ed.juntar_palavras(pagina, a, b)
            elif antes[a] != antes[b] and onde[a] == onde[b]:
                ed.quebrar(pagina, b)
    digitadas = [[g for g in p if g in boxes and g in onde]
                 for _linha, p in palavras_da_sequencia(sequencia, {})]
    digitadas = [p for p in digitadas if p]
    if not digitadas:
        return
    for palavra in digitadas:
        for a, b in zip(palavra, palavra[1:]):
            if onde[a][:2] == onde[b][:2] and onde[a] != onde[b]:
                ed.juntar_palavras(pagina, a, b)
    for anterior, seguinte in zip(digitadas, digitadas[1:]):
        if onde[anterior[-1]] == onde[seguinte[0]]:
            ed.quebrar(pagina, seguinte[0])
    primeiro, ultimo = digitadas[0][0], digitadas[-1][-1]
    palavra = montadas[onde[primeiro]]
    if any(g not in na_sessao for g in palavra[:palavra.index(primeiro)]):
        ed.quebrar(pagina, primeiro)
    palavra = montadas[onde[ultimo]]
    de_fora = [g for g in palavra[palavra.index(ultimo) + 1:] if g not in na_sessao]
    if de_fora and de_fora[0] in boxes:
        ed.quebrar(pagina, de_fora[0])
