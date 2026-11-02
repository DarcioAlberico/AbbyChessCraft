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
    palavras, depois_da_linha = _palavras_e_quebras(sequencia)
    linhas: List[Optional[int]] = [next((linha_original[g] for g in p if g in linha_original),
                                        None) for p in palavras]
    return list(zip(_linhas_das_novas(linhas, depois_da_linha), palavras))


def _palavras_e_quebras(sequencia) -> Tuple[List[List[int]], List[bool]]:
    """As palavras da sequência, em gids, e de cada uma se a quebra de linha impressa vem
    antes dela."""
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
    return palavras, depois_da_linha


def _linhas_das_novas(conhecidas: List[Optional[int]], depois_da_linha: List[bool]) -> List[int]:
    """A linha de cada palavra: a conhecida; a da palavra só de letras novas, a da anterior
    conhecida, ou a da seguinte se a quebra de linha vem antes dela (sem nenhuma, 0)."""
    linhas = list(conhecidas)
    for n in range(len(conhecidas)):
        if conhecidas[n] is None:
            linhas[n] = _linha_da_nova(conhecidas, n, depois_da_linha[n])
    return linhas


def _linha_da_nova(conhecidas: List[Optional[int]], n: int, depois_da_linha: bool) -> int:
    anterior = _primeira_conhecida(conhecidas, range(n - 1, -1, -1))
    seguinte = _primeira_conhecida(conhecidas, range(n + 1, len(conhecidas)))
    if depois_da_linha and seguinte is not None:
        return seguinte
    if anterior is not None:
        return anterior
    return seguinte if seguinte is not None else 0


def _primeira_conhecida(conhecidas: List[Optional[int]], indices) -> Optional[int]:
    """A primeira linha conhecida, na ordem de `indices`."""
    return next((conhecidas[k] for k in indices if conhecidas[k] is not None), None)


def ancorar(pagina: Pagina, sequencia, boxes_que_saem: Set[int],
             linha_original: Dict[int, int]) -> None:
    """Os virtuais como o usuário os deixou no texto novo. Em cada palavra, o virtual vem
    logo depois do glifo anterior dela; o primeiro, logo antes do primeiro box da palavra.
    Numa palavra só de virtuais, o primeiro abre uma palavra nova logo depois da palavra
    anterior da mesma linha impressa (ou antes do primeiro box da seguinte). E os virtuais
    de fora da sessão ancorados num box que sai (a palavra só de virtuais logo depois ou
    logo antes dela) passam ao vizinho que fica, na mesma linha."""
    ancoragem = _Ancoragem(pagina, sequencia, boxes_que_saem, linha_original)
    ancoragem.nas_palavras()                     # os virtuais das palavras da sessão
    ancoragem.os_de_fora()                       # os de fora ancorados num glifo dela
    if ancoragem.ancoras:
        ed.ancorar(pagina, ancoragem.ancoras)


class _Ancoragem:
    """O que `ancorar` vai decidindo: as palavras da sessão, os glifos dela, os virtuais da
    página e a âncora nova de cada virtual."""

    def __init__(self, pagina: Pagina, sequencia, boxes_que_saem: Set[int],
                 linha_original: Dict[int, int]):
        self.pagina, self.boxes_que_saem = pagina, boxes_que_saem
        self.linha_original = linha_original
        self.virtuais = {v.gid: v for v in pagina.decisoes.virtuais}
        self.palavras = palavras_da_sequencia(sequencia, linha_original)
        self.na_sessao = {g for _linha, p in self.palavras for g in p} | set(linha_original)
        self.ancoras: Dict[int, Tuple[Optional[int], Optional[int], bool]] = {}

    def fica_fora(self, gid: int) -> bool:
        """O glifo de fora cujo lugar não depende da sessão: a cadeia das âncoras dele não
        entra nela (senão, ancorar a sessão nele fecharia um ciclo)."""
        vistos = set()
        while gid in self.virtuais:
            if gid in self.na_sessao or gid in vistos:
                return False
            vistos.add(gid)
            v = self.virtuais[gid]
            gid = v.depois_de if v.depois_de is not None else v.antes_de
            if gid is None:
                return True
            if gid in self.boxes_que_saem or gid in self.na_sessao:
                return False
        return True

    def de_fora(self, linha: int) -> Tuple[Optional[int], Optional[int]]:
        return vizinhos_de_fora(self.pagina, self.linha_original, linha, self.na_sessao,
                                self.fica_fora)

    def nas_palavras(self) -> None:
        for n, (linha, palavra) in enumerate(self.palavras):
            self._na_palavra(n, linha, palavra)

    def _na_palavra(self, n: int, linha: int, palavra: List[int]) -> None:
        """O virtual logo depois do glifo anterior da palavra; o primeiro, logo antes do
        primeiro box dela, ou numa palavra nova (`palavra_nova`) se ela é só de virtuais."""
        caixas = [g for g in palavra if g not in self.virtuais]
        for k, gid in enumerate(palavra):
            if gid not in self.virtuais:
                continue
            if k:
                self.ancoras[gid] = (palavra[k - 1], None, False)
            elif caixas:
                self.ancoras[gid] = (None, caixas[0], False)
            else:
                self.ancoras[gid] = palavra_nova(self.palavras, n, linha, self.virtuais,
                                                 self.de_fora)

    def os_de_fora(self) -> None:
        """Os virtuais de fora da sessão ancorados num glifo dela."""
        if not self.palavras:
            return
        for v in self.virtuais.values():
            if v.gid in self.na_sessao:
                continue
            ancora = v.depois_de if v.depois_de is not None else v.antes_de
            if ancora in self.na_sessao:
                self.ancoras[v.gid] = self._ao_lado_da_sessao(v, ancora)

    def _ao_lado_da_sessao(self, v, ancora: int) -> Tuple[Optional[int], Optional[int], bool]:
        """A palavra só de virtuais logo depois (ou antes) da sessão, ancorada num glifo
        dela: fica logo depois da última palavra da sessão nesta linha (ou antes da
        primeira), como a sessão a deixou."""
        apos = v.depois_de is not None
        linha = self.linha_original.get(ancora, 0)
        mesma = [p for lp, p in self.palavras if lp == linha]
        if mesma:
            return ((mesma[-1][-1], None, v.palavra_nova) if apos
                    else (None, mesma[0][0], v.palavra_nova))
        antes, depois = self.de_fora(linha)          # a sessão saiu toda desta linha
        return (antes, None, True) if antes is not None else (None, depois, True)


def vizinhos_de_fora(pagina: Pagina, linha_original: Dict[int, int], linha: int,
                      na_sessao: Set[int], fica_fora) -> Tuple[Optional[int], Optional[int]]:
    """Na página montada agora: o último glifo de fora da sessão antes dela e o primeiro
    depois dela, na linha impressa `linha` da sessão; se a linha não tem nenhum (a sessão
    era a linha toda, e uma linha só existe com boxes), os mais perto nas outras linhas. Só
    os glifos que `fica_fora` aceita."""
    alvo = {g for g, lp in linha_original.items() if lp == linha}
    palavras = _palavras_montadas(pagina)
    dentro = [k for k, (_ln, p) in enumerate(palavras) if any(g in alvo for g in p)]
    if not dentro:
        return None, None
    a, b = dentro[0], dentro[-1]
    fora = _de_fora_da_sessao(palavras, na_sessao, fica_fora)
    return _vizinhos(fora, a, b, palavras[a][0])


def _palavras_montadas(pagina: Pagina) -> List[Tuple[int, List[int]]]:
    """(a linha, os gids) de cada palavra da página montada agora, em ordem; a linha é o id
    dela no Documento (todas vivas enquanto a lista se monta)."""
    from abbychess import texto as tx

    return [(id(ln), list(p.gids)) for bloco in tx.montar(pagina, com_os_nao_lidos=True).blocos
            for ln in bloco.linhas for p in ln.palavras]


def _de_fora_da_sessao(palavras: List[Tuple[int, List[int]]], na_sessao: Set[int],
                       fica_fora) -> List[Tuple[int, List[int]]]:
    """Cada palavra só com os glifos de fora da sessão que `fica_fora` aceita."""
    return [(ln, [g for g in p if g not in na_sessao and fica_fora(g)]) for ln, p in palavras]


def _vizinhos(fora: List[Tuple[int, List[int]]], a: int, b: int,
              mesma: int) -> Tuple[Optional[int], Optional[int]]:
    """O último glifo de `fora` antes da palavra `a` e o primeiro depois da `b`, na linha
    `mesma`; sem nenhum dos dois nela, os mais perto em qualquer linha."""
    antes_dela, depois_dela = list(reversed(fora[:a])), fora[b + 1:]
    antes = _na_ponta(antes_dela, -1, mesma)
    depois = _na_ponta(depois_dela, 0, mesma)
    if antes is None and depois is None:
        antes, depois = _na_ponta(antes_dela, -1), _na_ponta(depois_dela, 0)
    return antes, depois


def _na_ponta(palavras: List[Tuple[int, List[int]]], ponta: int,
              linha: Optional[int] = None) -> Optional[int]:
    """O glifo da `ponta` (0 ou -1) da primeira palavra não vazia, só das da `linha` se ela
    é dada."""
    return next((p[ponta] for ln, p in palavras if p and (linha is None or ln == linha)), None)


def palavra_nova(palavras, n: int, linha: int, virtuais, de_fora
                  ) -> Tuple[Optional[int], Optional[int], bool]:
    """A âncora da palavra `n`, só de virtuais: depois da palavra anterior da mesma linha;
    sem ela, antes do primeiro box de uma seguinte da mesma linha; sem as duas, depois (ou
    antes) da palavra de fora da sessão na mesma linha (`de_fora`); sem elas, a vizinha mais
    perto em outra linha."""
    anterior = next((p for lp, p in reversed(palavras[:n]) if lp == linha), None)
    if anterior is not None:
        return anterior[-1], None, True
    seguinte = _primeiro_box(palavras[n + 1:], virtuais, linha)
    if seguinte is not None:
        return None, seguinte, True
    return _fora_da_linha(palavras, n, virtuais, de_fora(linha))


def _fora_da_linha(palavras, n: int, virtuais, vizinhos: Tuple[Optional[int], Optional[int]]
                   ) -> Tuple[Optional[int], Optional[int], bool]:
    """Sem palavra da sessão na linha: depois (ou antes) do glifo de fora dela na mesma
    linha (`vizinhos`); sem eles, a palavra vizinha mais perto em outra linha."""
    antes, depois = vizinhos
    if antes is not None:
        return antes, None, True
    if depois is not None:
        return None, depois, True
    if n:
        return palavras[n - 1][1][-1], None, True
    return None, _primeiro_box(palavras[n + 1:], virtuais), True


def _primeiro_box(palavras, virtuais, linha: Optional[int] = None) -> Optional[int]:
    """O primeiro glifo que não é virtual das palavras, só das da `linha` se ela é dada."""
    return next((g for lp, p in palavras if linha is None or lp == linha for g in p
                 if g not in virtuais), None)


def virtual_vizinho(pagina: Pagina, gid: int) -> Optional[Tuple[int, str]]:
    """O glifo virtual colado no box `gid` na palavra montada (o da esquerda; senão, o da
    direita), como (gid, letra), ou None. O box recém-marcado sobre a tinta de uma letra que
    faltava pode ser ela, ou outra coisa (a vírgula ao lado): quem decide é o usuário."""
    virtuais = {v.gid: v for v in pagina.decisoes.virtuais}
    onde, montadas = pagina_montada(pagina)
    if gid not in onde or not virtuais:
        return None
    palavra = montadas[onde[gid]]
    k = palavra.index(gid)
    vizinho = next((g for g in (palavra[k - 1] if k else None,
                                palavra[k + 1] if k + 1 < len(palavra) else None)
                    if g in virtuais), None)
    return None if vizinho is None else (vizinho, virtuais[vizinho].char)


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
    como = _ComoDigitado(pagina, na_sessao)
    como.as_de_fora(antes)                       # as palavras de fora, como eram
    digitadas = como.digitadas(sequencia)
    if digitadas:
        como.as_digitadas(digitadas)             # as da sessão, como foram digitadas
        como.as_pontas(digitadas)                # e separadas das de fora


class _ComoDigitado:
    """A página montada antes das junções e quebras de `como_digitado` (elas não a
    remontam), os boxes vivos e os glifos da sessão."""

    def __init__(self, pagina: Pagina, na_sessao: Set[int]):
        self.pagina, self.na_sessao = pagina, na_sessao
        self.onde, self.montadas = pagina_montada(pagina)
        self.boxes = pagina.vivos

    def as_de_fora(self, antes: Dict[int, Tuple[int, int, int]]) -> None:
        """As palavras de fora da sessão voltam às de `antes`, só nas linhas da sessão (as
        que tinham um glifo dela antes): as outras não mudaram."""
        linhas = self._linhas()
        da_sessao = {antes[g][:2] for g in self.na_sessao if g in antes}
        for linha in linhas:
            if any(antes.get(g, (None, None))[:2] in da_sessao for g in linha):
                self._como_antes(linha, antes)

    def _linhas(self):
        """Os boxes de cada linha montada, em ordem."""
        linhas: Dict[Tuple[int, int], List[int]] = {}
        for (b, n, _k), gids in sorted(self.montadas.items()):
            linhas.setdefault((b, n), []).extend(g for g in gids if g in self.boxes)
        return linhas.values()

    def _como_antes(self, linha: List[int], antes: Dict[int, Tuple[int, int, int]]) -> None:
        """Dois boxes vizinhos de fora da sessão juntos na mesma palavra se estavam numa
        só em `antes`, e partidos se estavam em duas."""
        for a, b in zip(linha, linha[1:]):
            if a in self.na_sessao or b in self.na_sessao or a not in antes or b not in antes:
                continue
            juntos_antes, juntos_agora = antes[a] == antes[b], self.onde[a] == self.onde[b]
            if juntos_antes != juntos_agora:
                if juntos_antes:
                    ed.juntar_palavras(self.pagina, a, b)
                else:
                    ed.quebrar(self.pagina, b)

    def digitadas(self, sequencia) -> List[List[int]]:
        """Os boxes montados de cada palavra digitada, sem as que não têm nenhum."""
        digitadas = [[g for g in p if g in self.boxes and g in self.onde]
                     for _linha, p in palavras_da_sequencia(sequencia, {})]
        return [p for p in digitadas if p]

    def as_digitadas(self, digitadas: List[List[int]]) -> None:
        """A palavra digitada que a montagem partiu na mesma linha impressa é juntada, e
        duas digitadas que ela juntou são partidas."""
        onde = self.onde
        for palavra in digitadas:
            for a, b in zip(palavra, palavra[1:]):
                if onde[a][:2] == onde[b][:2] and onde[a] != onde[b]:
                    ed.juntar_palavras(self.pagina, a, b)
        for anterior, seguinte in zip(digitadas, digitadas[1:]):
            if onde[anterior[-1]] == onde[seguinte[0]]:
                ed.quebrar(self.pagina, seguinte[0])

    def as_pontas(self, digitadas: List[List[int]]) -> None:
        """A primeira e a última palavra da sessão partidas da de fora que a montagem juntou
        a elas."""
        primeiro, ultimo = digitadas[0][0], digitadas[-1][-1]
        palavra = self.montadas[self.onde[primeiro]]
        if any(g not in self.na_sessao for g in palavra[:palavra.index(primeiro)]):
            ed.quebrar(self.pagina, primeiro)
        palavra = self.montadas[self.onde[ultimo]]
        de_fora = [g for g in palavra[palavra.index(ultimo) + 1:] if g not in self.na_sessao]
        if de_fora and de_fora[0] in self.boxes:
            ed.quebrar(self.pagina, de_fora[0])
