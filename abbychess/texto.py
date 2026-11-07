"""O documento da página e o texto dele (SPEC §4.2): `montar` e a normalização única.

**O documento é derivado.** `montar(pagina)` é função pura dos boxes, das áreas, das
decisões do usuário e dos diagramas: `Documento(blocos)`, cada `Bloco` com a área de onde
veio e a função dela, e linhas de palavras de gids. Nada do documento é gravado; quem
precisa do texto monta de novo.

- **Linhas e palavras** são as do core (`core.notacao.palavras_da_pagina`), que já são as do
  texto de hoje, com os acertos de `layout` (o espaço depois do "f", os vãos largos).
- **Lances colados** (`partir_lances_colados`): o negrito apertado do Mirkovic junta o lance
  ao número do seguinte ("♘f62.c4", "♗b44.e3", "e30—0", "♔c5♔a4"); a palavra parte depois da
  casa quando o que vem é um número de lance, um roque ou outra figurina. As decisões vêm
  depois: uma `juncao` do usuário junta de novo.
- **Decisões**: uma `quebra` parte a palavra antes do gid; uma `juncao` (a, b) junta a
  palavra que termina em `a` com a seguinte, que começa em `b`, na mesma linha; um glifo
  virtual entra depois de `depois_de` (na mesma palavra ou, com `palavra_nova`, numa nova),
  ou no começo da primeira linha; `paragrafo_antes` começa um bloco novo na linha do gid.
  O `hifen_de_quebra` é guardado para a exportação refluir o texto (passo J): a vista e a
  busca mostram as linhas como impressas.
- **Blocos**: linhas seguidas na mesma área de texto formam um bloco com a função da área;
  sem área, a função é `texto`. A ordem é a de leitura das linhas, salvo quando as áreas
  têm `ordem`: aí os blocos seguem a ordem delas.
- **Diagramas** entram como bloco próprio (`_lugar_do_diagrama`): no trecho (a coluna)
  deles, antes da primeira linha na altura deles ou abaixo. Quando essa linha fica ao lado
  do tabuleiro (o parágrafo que o contorna), só num fim de frase; sem fim de frase, no fim.

**O texto** (`texto`) tem dois modos: `impresso` (♘ como impresso; a vista, a busca, o DOCX
e o EPUB) e `san` (as figurinhas como letras, ♘ → N; o PGN, a validação e o texto de hoje,
que vinha do core já assim). Os dois passam por `core.notacao.normalizar_saida`.
"""

from __future__ import annotations

import copy
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Set, Tuple

import numpy as np

from abbychess import zonas as zn
from abbychess.layout import FIM_DE_FRASE, OrdemDeLeitura, lugares_da_pilha
from abbychess.modelo import Decisoes, Pagina

IMPRESSO = "impresso"
SAN = "san"
MODOS = (IMPRESSO, SAN)

#: Ligaduras tipográficas que ocupam um box, mas têm mais de uma letra no texto.
#: O Documento repete o gid do box para cada letra resultante.
LIGADURAS = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}



@dataclass(frozen=True)
class Palavra:
    gids: Tuple[int, ...]


@dataclass(frozen=True)
class Linha:
    palavras: Tuple[Palavra, ...]


@dataclass(frozen=True)
class Bloco:
    id: str
    zona_id: Optional[str]
    funcao: str
    linhas: Tuple[Linha, ...] = ()
    diagrama_id: Optional[str] = None
    #: Na legenda, o diagrama ao qual ela pertence.
    referencia_id: Optional[str] = None


@dataclass(frozen=True)
class Documento:
    blocos: Tuple[Bloco, ...]
    #: gid -> o caractere (os dos boxes como lidos, e os dos glifos virtuais).
    chars: Dict[int, str] = field(default_factory=dict)
    estilos: Dict[int, object] = field(default_factory=dict)

    def gids(self) -> List[int]:
        """Os gids do documento, na ordem dele (cada um uma vez)."""
        return [g for b in self.blocos for ln in b.linhas for p in ln.palavras for g in p.gids]


# ----------------------------------------------------------------------
# Montar
# ----------------------------------------------------------------------

#: Como o glifo que ninguém leu aparece no documento da vista (`com_os_nao_lidos`).
NAO_LIDO = "□"


def _lidos(pagina: Pagina, com_os_nao_lidos: bool):
    """Os boxes que entram no documento e o `BoxEntry` de cada um (o não lido como
    `NAO_LIDO`, numa cópia)."""
    lidos = [b for b in pagina.boxes if b.entry.char or com_os_nao_lidos]
    entries = []
    for b in lidos:
        if b.entry.char:
            entries.append(b.entry)
        else:
            vazio = copy.copy(b.entry)
            vazio.char = NAO_LIDO
            entries.append(vazio)
    return lidos, entries


def palavras_dos_gids(pagina: Pagina) -> List[List[int]]:
    """As palavras (gids) de todas as linhas da página, em ordem de leitura, como a vista do
    Documento as monta (com os não lidos e as decisões de palavra): a mesma chave das linhas
    guardadas, então depois do Documento elas não são refeitas. Os virtuais entram pelos
    gids deles (`pagina.decisoes.virtuais`)."""
    return [p for ln in linhas_dos_gids(pagina) for p in ln]


def linhas_dos_gids(pagina: Pagina, *, com_os_nao_lidos: bool = True) -> List[List[List[int]]]:
    """As linhas de `palavras_dos_gids`, cada uma com as palavras dela (gids). Sem os não
    lidos, as do texto e da exportação (`montar`): o glifo que ninguém leu não junta a
    palavra em volta do buraco dele."""
    lidos, entries = _lidos(pagina, com_os_nao_lidos)
    return _linhas_na_ordem(pagina, lidos, entries, chars_dos_gids(pagina, lidos, entries))[0]


def chars_dos_gids(pagina: Pagina, lidos, entries) -> Dict[int, str]:
    """O caractere de cada gid de `lidos` (o do `BoxEntry` de mesmo lugar em `entries`), os
    virtuais da página também."""
    chars = {b.gid: e.char for b, e in zip(lidos, entries)}
    chars.update({v.gid: v.char for v in pagina.decisoes.virtuais})
    return chars


#: O fim de um lance: a casa, a promoção e os sinais ("f6", "f1♕", "c8=Q+", "b4!?").
_FIM_DE_LANCE = re.compile(r"[a-h][1-8](?:=?[♔♕♖♗♘♚♛♜♝♞QRBN])?[+#‡†]*[!?]*$")
#: O que começa o lance seguinte colado: o número dele, o roque ou uma figurina com a casa.
_COMECO_DE_LANCE = re.compile(r"^(?:\d{1,3}\.|[0O][-–—][0O]|[♔♕♖♗♘♚♛♜♝♞][a-h]?[1-8]?[x:]?[a-h][1-8])")


def partir_lances_colados(linhas: List[List[List[int]]], chars: Dict[int, str]
                          ) -> List[List[List[int]]]:
    """Cada palavra partida entre um lance e o seguinte que o OCR colou nela (sem espaço
    entre eles): depois da casa (`_FIM_DE_LANCE`), quando o resto começa um lance
    (`_COMECO_DE_LANCE`). "♘f62.c4" vira "♘f6" e "2.c4"; "1.e4e5" e "a1-h8" ficam."""
    saida = []
    for linha in linhas:
        palavras = []
        for p in linha:
            palavras.extend(_lances_da_palavra(p, chars))
        saida.append(palavras)
    return saida


def _lances_da_palavra(p: List[int], chars: Dict[int, str]) -> List[List[int]]:
    """A palavra partida em cada lance colado nela; a que não pode ter um, inteira."""
    texto = [chars.get(g) or "" for g in p]
    if not _pode_ter_lance_colado(p, texto):
        return [p]
    partes: List[List[int]] = []
    atual = [p[0]]
    for k in range(1, len(p)):
        if (_FIM_DE_LANCE.search("".join(texto[k - len(atual):k]))
                and _COMECO_DE_LANCE.match("".join(texto[k:]))):
            partes.append(atual)
            atual = []
        atual.append(p[k])
    partes.append(atual)
    return partes


def _pode_ter_lance_colado(p: List[int], texto: List[str]) -> bool:
    """Dois lances colados têm ao menos 4 glifos e um número de lance."""
    return len(p) >= 4 and any(c[:1].isdigit() for c in texto)


def montar(pagina: Pagina, *, com_os_nao_lidos: bool = False) -> Documento:
    """O documento da página (função pura do que está gravado nela). O texto e a exportação
    só têm os glifos lidos; a vista do Documento (`com_os_nao_lidos`) mostra também os que
    ninguém leu, como `NAO_LIDO`, para o realce deles (§6.1)."""
    lidos, entries = _lidos(pagina, com_os_nao_lidos)
    chars = chars_dos_gids(pagina, lidos, entries)
    linhas, topos, trechos, ordem = _linhas_na_ordem(pagina, lidos, entries, chars)
    por_gid = {b.gid: e for b, e in zip(lidos, entries)}
    if ordem.coluna_da_pilha is None:
        antes_da_linha = _diagramas_antes_da_linha(pagina.diagramas, ordem, linhas, topos, trechos,
                                                   chars, por_gid, entries)
    else:
        antes_da_linha = _diagramas_da_pilha(pagina, ordem, linhas, topos, trechos, chars, entries)
    blocos = _blocos(linhas, _zonas_das_linhas(linhas, pagina.zonas, por_gid),
                     _paragrafos_novos(linhas, pagina.decisoes), antes_da_linha)
    return Documento(tuple(_na_ordem_das_zonas(blocos, pagina)), chars,
                     {b.gid: b.estilo for b in lidos})


def _linhas_na_ordem(pagina: Pagina, lidos, entries, chars: Dict[int, str]) -> tuple:
    """As linhas com as decisões da página, o topo e o trecho de cada uma, e a ordem de leitura;
    a legenda lida na coluna só de tabuleiros, junto do tabuleiro dela."""
    linhas, topos, trechos, ordem = _linhas_da_pagina(lidos, entries, _caixas_dos_diagramas(pagina))
    linhas = _aplicar_decisoes(partir_lances_colados(linhas, chars), pagina.decisoes)
    if ordem.coluna_da_pilha is None:
        return linhas, topos, trechos, ordem
    _, legendas = _lugares_da_pilha(pagina, ordem, linhas, topos, trechos, chars, entries)
    posicao = {lugar: j for j, lugar in reversed(list(enumerate(zip(trechos, topos))))}

    def chave(j: int) -> float:
        destino = legendas.get((trechos[j], topos[j]))
        return j if destino is None else posicao.get(destino, len(linhas)) - 0.5

    novos = sorted(range(len(linhas)), key=chave)
    return ([linhas[j] for j in novos], [topos[j] for j in novos], [trechos[j] for j in novos],
            ordem)


def _lugares_da_pilha(pagina: Pagina, ordem: OrdemDeLeitura, linhas, topos, trechos,
                      chars: Dict[int, str], entries) -> tuple:
    """`layout.lugares_da_pilha` com as linhas da página."""
    return lugares_da_pilha(ordem, _caixas_dos_diagramas(pagina),
                            list(zip(trechos, topos, _textos_das_linhas(linhas, chars))),
                            _altura_mediana(entries))


def _textos_das_linhas(linhas, chars: Dict[int, str]) -> List[str]:
    return [" ".join("".join(chars[g] for g in p) for p in ln) for ln in linhas]


def _altura_mediana(entries) -> float:
    return float(np.median([e.y2 - e.y1 for e in entries])) if entries else 0.0


def _caixas_dos_diagramas(pagina: Pagina) -> tuple:
    """As caixas dos tabuleiros da página: uma coluna só deles é da ordem de leitura."""
    return tuple(tuple(d.caixa) for d in pagina.diagramas)


def _zonas_das_linhas(linhas, zonas: Sequence, por_gid) -> list:
    """A área de texto de cada linha (None: fora delas)."""
    zonas_de_texto = [z for z in zonas if z.tipo == "texto"]
    return [_zona_da_linha(ln, por_gid, zonas_de_texto) for ln in linhas]


def _paragrafos_novos(linhas, decisoes: Decisoes) -> List[bool]:
    """Um parágrafo antes de qualquer glifo da linha começa o bloco nessa linha (o
    documento é feito de linhas inteiras; partir uma linha é do layout, passo F)."""
    return [any(g in decisoes.paragrafo_antes for p in ln for g in p) for ln in linhas]


def _diagramas_antes_da_linha(diagramas, ordem: OrdemDeLeitura, linhas, topos, trechos,
                              chars: Dict[int, str], por_gid, entries) -> Dict[int, List[str]]:
    """Onde cada diagrama entra: `{lugar: [ids]}`, antes da linha `lugar` (len(linhas) = no
    fim), de cima para baixo."""
    texto_das_linhas = _textos_das_linhas(linhas, chars)
    altura = _altura_mediana(entries)
    antes_da_linha: Dict[int, List[str]] = {}
    for d in sorted(diagramas, key=lambda d: (d.caixa[1], d.caixa[0])):
        lugar = _lugar_do_diagrama(d.caixa, ordem, linhas, topos, trechos, texto_das_linhas,
                                   por_gid, altura)
        antes_da_linha.setdefault(lugar, []).append(d.id)
    return antes_da_linha


def _diagramas_da_pilha(pagina: Pagina, ordem: OrdemDeLeitura, linhas, topos, trechos,
                        chars: Dict[int, str], entries) -> Dict[int, List[str]]:
    """`{lugar: [ids]}` da coluna só de tabuleiros (`layout.lugares_da_pilha`)."""
    lugares, _ = _lugares_da_pilha(pagina, ordem, linhas, topos, trechos, chars, entries)
    posicao = {lugar: j for j, lugar in reversed(list(enumerate(zip(trechos, topos))))}
    antes_da_linha: Dict[int, List[str]] = {}
    por_altura = sorted(pagina.diagramas, key=lambda d: (d.caixa[1], d.caixa[0]))
    for d, lugar in zip(por_altura, lugares):
        antes_da_linha.setdefault(posicao.get(lugar, len(linhas)), []).append(d.id)
    return antes_da_linha


def _blocos(linhas, zona_da_linha: list, novo_paragrafo: List[bool],
            antes_da_linha: Dict[int, List[str]]) -> List[Bloco]:
    """Os blocos do documento: as linhas seguidas na mesma área, sem parágrafo novo entre
    elas, e os diagramas no lugar deles."""
    blocos: List[Bloco] = []
    atual: List[Linha] = []
    atual_zona: Optional[object] = None

    def fechar():
        nonlocal atual
        if atual:
            zona = atual_zona
            blocos.append(Bloco(f"b{len(blocos)}", getattr(zona, "id", None) or None,
                                getattr(zona, "funcao", "texto"), tuple(atual),
                                referencia_id=getattr(zona, "diagrama_id", None)))
            atual = []

    for j, ln in enumerate(linhas):
        if j in antes_da_linha:
            fechar()
            _com_os_diagramas(blocos, antes_da_linha[j])
        if atual and (zona_da_linha[j] is not atual_zona or novo_paragrafo[j]):
            fechar()
        atual_zona = zona_da_linha[j]
        atual.append(Linha(tuple(Palavra(tuple(p)) for p in ln)))
    fechar()
    _com_os_diagramas(blocos, antes_da_linha.get(len(linhas), []))
    return blocos


def _com_os_diagramas(blocos: List[Bloco], dids: Sequence[str]) -> None:
    """Um bloco de diagrama para cada id, no fim dos blocos."""
    for did in dids:
        blocos.append(Bloco(f"b{len(blocos)}", None, "diagrama", diagrama_id=did))


def _lugar_do_diagrama(caixa, ordem: OrdemDeLeitura, linhas, topos, trechos,
                       texto_das_linhas, por_gid, altura: float) -> int:
    """Antes de qual linha o diagrama entra (len(linhas) = no fim).

    No trecho (a coluna) dele, antes da primeira linha na altura dele ou abaixo; sem linha
    assim no trecho, antes da primeira do trecho seguinte. Só a linha ao lado do tabuleiro,
    a do parágrafo que o contorna, pede um fim de frase antes: o parágrafo não é partido no
    meio. A linha de lances logo acima ("52.bxc7 ♔d7 … 54.♔xa5", sem ponto) não segura
    mais o diagrama, que caía depois do parágrafo de baixo (p. 54 do Aagaard).

    Só as linhas com lugar na página contam: a linha só de virtuais, na página sem glifo
    lido, não tem trecho nem topo, e o diagrama vai para o fim.
    """
    x1, y1, x2, y2 = caixa
    chave = ordem.chave((x1 + x2) / 2, y1)
    j = next((j for j in range(len(trechos)) if (trechos[j], topos[j]) >= (chave, y1 - altura)),
             len(linhas))
    if j == len(linhas) or trechos[j] != chave:
        return j
    if not _ao_lado(caixa, _caixas_da_linha(linhas[j], por_gid)):
        return j
    return _depois_do_fim_de_frase(j, texto_das_linhas)


def _depois_do_fim_de_frase(j: int, texto_das_linhas: Sequence[str]) -> int:
    """A primeira linha de `j` em diante (nunca a primeira da página) que vem depois de um
    fim de frase; sem fim de frase, o fim."""
    return next((k for k in range(max(j, 1), len(texto_das_linhas))
                 if FIM_DE_FRASE.search(texto_das_linhas[k - 1])), len(texto_das_linhas))


def _caixas_da_linha(linha, por_gid) -> list:
    """Os `BoxEntry` dos glifos da linha (os virtuais não têm)."""
    return [por_gid[g] for p in linha for g in p if g in por_gid]


def _ao_lado(caixa, caixas) -> bool:
    """A linha começa acima do pé do tabuleiro e fica toda à esquerda ou à direita dele."""
    if not caixas:
        return False
    x1, _, x2, y2 = caixa
    return (min(e.y1 for e in caixas) < y2
            and (max(e.x2 for e in caixas) <= x1 or min(e.x1 for e in caixas) >= x2))


#: As linhas de palavras das últimas páginas montadas, pela chave do que elas usam
#: (`_chave_das_linhas`): `{chave: (linhas, topos)}`, do mais velho ao mais novo.
_LINHAS_VISTAS: "OrderedDict[tuple, tuple]" = OrderedDict()
_TRAVA_DAS_LINHAS = threading.Lock()
#: Quantas páginas a cache guarda (o texto e a vista do Documento de cada uma, a do lote e as
#: vizinhas).
LINHAS_GUARDADAS = 16


@lru_cache(maxsize=4096)
def _o_que_as_palavras_leem(char: str) -> Optional[str]:
    """O caractere, se as palavras do core dependem dele; `None` se não. As linhas e as
    colunas são só da geometria; das palavras, o caractere só pesa quando some na
    normalização (o box vazio ocupa espaço, mas não é símbolo), nos números que o core
    remonta (a palavra só de algarismos, a que começa por algarismo ou ponto) e no "f", que
    tem limiar de espaço próprio (`layout.partir_depois_do_f`). Depois do "f", se a letra
    seguinte é letra ou não, também decide; a chave a guarda como "letra"."""
    from core.notacao import FIGURINAS, normalizar_saida

    simbolo = FIGURINAS.get(char, normalizar_saida(char))
    if not simbolo or simbolo == "f" or any(c.isdigit() or c == "." for c in simbolo):
        return simbolo
    return "letra" if simbolo[:1].isalpha() else None


def _chave_das_linhas(lidos, entries) -> Optional[tuple]:
    """O que as linhas de palavras usam: o gid, a caixa, o ângulo e a moldura de cada glifo
    lido, na ordem da página, e o caractere só onde as palavras o leem
    (`_o_que_as_palavras_leem`). Trocar uma letra por outra (a correção mais comum) não muda
    a chave. `None` se algo não for comparável (aí as linhas são montadas sempre)."""
    try:
        chave = tuple((b.gid, e.x1, e.y1, e.x2, e.y2, e.angulo, getattr(e, "moldura", False),
                       _o_que_as_palavras_leem(e.char))
                      for b, e in zip(lidos, entries))
        hash(chave)
    except TypeError:
        return None
    return chave


def _linhas_da_pagina(lidos, entries, tabuleiros: tuple = ()
                      ) -> Tuple[List[List[List[int]]], List[int], List[tuple], OrdemDeLeitura]:
    """As palavras (gids) de cada linha na ordem de leitura, o topo e o trecho de cada linha,
    e a ordem de leitura (os diagramas entram no trecho deles). A ordem de leitura e as
    linhas são ~85% do `montar` (~15–20 ms numa página do livro): guardadas pela chave,
    corrigir um caractere não as refaz."""
    chave = _chave_das_linhas(lidos, entries)
    chave = None if chave is None else (tabuleiros, chave)
    vistas = _linhas_guardadas(chave)
    if vistas is not None:
        return vistas
    linhas, topos, trechos, ordem = _linhas_novas(lidos, entries, tabuleiros)
    _guardar_as_linhas(chave, linhas, topos, trechos, ordem)
    return linhas, topos, trechos, ordem


def _linhas_guardadas(chave: Optional[tuple]):
    """As linhas, os topos, os trechos e a ordem guardados pela chave, em listas novas (quem
    as recebe pode mudá-las); None se não estão guardados."""
    if chave is None:
        return None
    with _TRAVA_DAS_LINHAS:
        vistas = _LINHAS_VISTAS.get(chave)
        if vistas is not None:
            _LINHAS_VISTAS.move_to_end(chave)
    if vistas is None:
        return None
    linhas, topos, trechos, ordem = vistas
    return [[list(p) for p in ln] for ln in linhas], list(topos), list(trechos), ordem


def _linhas_novas(lidos, entries, tabuleiros: tuple = ()):
    """As linhas de palavras (gids) montadas pela ordem de leitura, trecho a trecho, com o
    topo e o trecho de cada uma, e a ordem."""
    linhas: List[List[List[int]]] = []
    topos: List[int] = []
    trechos: List[tuple] = []
    ordem = OrdemDeLeitura.da_pagina(entries, tabuleiros)
    for chave_do_trecho, indices in ordem.trechos(entries):
        trecho = [entries[i] for i in indices]
        for linha in ordem.linhas_do_trecho(indices, entries):
            palavras = _gids_das_palavras(linha, indices, lidos)
            if palavras:
                linhas.append(palavras)
                topos.append(min(trecho[s.indice].y1 for p in linha for s in p.simbolos))
                trechos.append(chave_do_trecho)
    return linhas, topos, trechos, ordem


def _gids_das_palavras(linha, indices, lidos) -> List[List[int]]:
    """As palavras da linha do core como gids, sem as vazias."""
    palavras = [[lidos[indices[s.indice]].gid for s in p.simbolos] for p in linha]
    return [p for p in palavras if p]


def _guardar_as_linhas(chave: Optional[tuple], linhas, topos, trechos, ordem) -> None:
    """Guarda as linhas pela chave (em tuplas), e esquece as mais velhas além do limite."""
    if chave is None:
        return
    with _TRAVA_DAS_LINHAS:
        _LINHAS_VISTAS[chave] = (tuple(tuple(tuple(p) for p in ln) for ln in linhas),
                                 tuple(topos), tuple(trechos), ordem)
        while len(_LINHAS_VISTAS) > LINHAS_GUARDADAS:
            _LINHAS_VISTAS.popitem(last=False)


def _aplicar_decisoes(linhas: List[List[List[int]]], decisoes: Decisoes) -> List[List[List[int]]]:
    """As quebras, as junções e os virtuais aplicados às palavras de cada linha."""
    saida = [_com_as_juncoes(_com_as_quebras(linha, decisoes.quebras), decisoes.juncoes)
             for linha in linhas]
    _com_os_virtuais(saida, decisoes)
    return saida


def _com_as_quebras(linha: List[List[int]], quebras) -> List[List[int]]:
    """As palavras da linha partidas antes de cada gid de quebra."""
    palavras: List[List[int]] = []
    for p in linha:
        atual = [p[0]]
        for g in p[1:]:
            if g in quebras:
                palavras.append(atual)
                atual = [g]
            else:
                atual.append(g)
        palavras.append(atual)
    return palavras


def _com_as_juncoes(palavras: List[List[int]], juncoes) -> List[List[int]]:
    """Cada palavra junta à anterior quando (o fim da anterior, o começo dela) é uma junção."""
    juntas: List[List[int]] = []
    for p in palavras:
        if juntas and (juntas[-1][-1], p[0]) in juncoes:
            juntas[-1] = juntas[-1] + p
        else:
            juntas.append(list(p))
    return juntas


def _com_os_virtuais(saida: List[List[List[int]]], decisoes: Decisoes) -> None:
    """Os glifos virtuais postos nas linhas."""
    # Os virtuais, na ordem das decisões: cada um logo depois (ou logo antes) da âncora dele,
    # que é um box ou outro virtual; a âncora virtual entra antes dele (uma pilha, não a
    # recursão: a cadeia pode ser longa). Dois na mesma âncora: o mais novo fica junto dela
    # (foi digitado ali). Um virtual sem âncora na página, ou num ciclo, vai para o começo
    # da primeira linha.
    por_gid = {v.gid: v for v in decisoes.virtuais}
    postos: Set[int] = set()

    def ancora_de(v) -> Optional[int]:
        return v.antes_de if v.antes_de is not None and v.depois_de is None else v.depois_de

    def por(v, sem_ancora: bool = False) -> None:
        postos.add(v.gid)
        if sem_ancora:
            _inserir_virtual(saida, v, None)
        elif v.antes_de is not None and v.depois_de is None:
            _inserir_antes(saida, v)
        else:
            _inserir_virtual(saida, v, v.depois_de)

    for primeiro in decisoes.virtuais:
        pilha, na_pilha = [primeiro], {primeiro.gid}
        while pilha:
            v = pilha[-1]
            if v.gid in postos:
                pilha.pop()
                continue
            ancora = ancora_de(v)
            if ancora in por_gid and ancora not in postos:
                if ancora in na_pilha:          # um ciclo: este fica sem âncora
                    por(pilha.pop(), sem_ancora=True)
                    continue
                pilha.append(por_gid[ancora])
                na_pilha.add(ancora)
                continue
            por(pilha.pop())


def _inserir_antes(linhas: List[List[List[int]]], v) -> None:
    """O virtual antes do glifo `antes_de` (um box ou outro virtual): na palavra dele ou,
    com `palavra_nova`, numa palavra nova logo antes dela; sem ele, no começo da primeira
    linha."""
    for linha in linhas:
        for k, p in enumerate(linha):
            if v.antes_de in p:
                if v.palavra_nova:
                    linha.insert(k, [v.gid])
                else:
                    p.insert(p.index(v.antes_de), v.gid)
                return
    _inserir_virtual(linhas, v, None)


def _inserir_virtual(linhas: List[List[List[int]]], v, depois: Optional[int]) -> None:
    """O virtual `v` logo depois do glifo `depois` (um box ou outro virtual), ou no começo
    da primeira linha."""
    if depois is not None:
        for linha in linhas:
            for k, p in enumerate(linha):
                if depois in p:
                    if v.palavra_nova:
                        linha.insert(k + 1, [v.gid])
                    else:
                        p.insert(p.index(depois) + 1, v.gid)
                    return
    if not linhas:
        linhas.append([[v.gid]])
    elif v.palavra_nova or not linhas[0]:
        linhas[0].insert(0, [v.gid])
    else:
        linhas[0][0].insert(0, v.gid)


def _zona_da_linha(linha, por_gid, zonas):
    """A área de texto que contém o meio da linha (a que vale, se mais de uma)."""
    entries = _caixas_da_linha(linha, por_gid)
    if not entries or not zonas:
        return None
    return zn.zona_da_maioria(zonas, entries)


def _na_ordem_das_zonas(blocos: List[Bloco], pagina: Pagina) -> List[Bloco]:
    """Com `ordem` nas áreas, os blocos delas seguem essa ordem, o diagrama pela área de
    diagrama dele; o resto fica no lugar."""
    ordem = {z.id: z.ordem for z in pagina.zonas if z.id and z.ordem is not None}
    if not ordem:
        return blocos
    do_diagrama = {d.id: zn.ordem_do_tabuleiro(pagina.zonas, d.caixa) for d in pagina.diagramas}
    return zn.na_ordem_das_areas(blocos, lambda b: (ordem.get(b.zona_id)
                                                    if b.diagrama_id is None
                                                    else do_diagrama.get(b.diagrama_id)))


def numeros_das_areas(pagina: Pagina) -> Dict[str, int]:
    """O número de cada área (§5.2), pelo id: a ordem em que o Documento a lê; depois, a que não
    lê nada, pela ordem dela e pela lista. Nenhum número se repete."""
    do_diagrama = {d.id: zn.area_do_tabuleiro(pagina.zonas, d.caixa) for d in pagina.diagramas}
    numeros: Dict[str, int] = {}
    lidas = [_id_da_area(bloco, do_diagrama) for bloco in montar(pagina).blocos]
    # `sorted` é estável: sem ordem, fica a da lista.
    resto = [z.id for z in sorted(pagina.zonas, key=lambda z: (z.ordem is None, z.ordem or 0))]
    for zona_id in lidas + resto:
        if zona_id and zona_id not in numeros:
            numeros[zona_id] = len(numeros) + 1
    return numeros


def _id_da_area(bloco: Bloco, do_diagrama: dict) -> Optional[str]:
    """O id da área do bloco: a do tabuleiro, no bloco de diagrama."""
    if bloco.diagrama_id is None:
        return bloco.zona_id
    area = do_diagrama.get(bloco.diagrama_id)
    return area.id if area is not None else None


# ----------------------------------------------------------------------
# O texto
# ----------------------------------------------------------------------

def normalizar(char: str, modo: str) -> str:
    """O caractere como sai do programa no modo (§4.2)."""
    return normalizador(modo)(char)


def normalizador(modo: str):
    """A função que leva o caractere lido ao que sai no modo (§4.2), sem as ligaduras: o
    mesmo caminho no Documento, na edição e na exportação."""
    from core.notacao import FIGURINAS, normalizar_saida

    def sem_ligadura(char: str) -> str:
        return "".join(LIGADURAS.get(c, c) for c in char)

    if modo == SAN:
        return lambda c: FIGURINAS.get(c) or normalizar_saida(sem_ligadura(c))
    if modo == IMPRESSO:
        return lambda c: normalizar_saida(sem_ligadura(c))
    raise ValueError(f"modo desconhecido {modo!r}")


def texto(documento: Documento, diagramas: Sequence = (), modo: str = IMPRESSO) -> str:
    """O texto do documento: uma linha impressa por linha, e uma linha por diagrama."""
    normal = normalizador(modo)
    por_id = {d.id: d for d in diagramas}
    numero = numeros_dos_diagramas(documento, diagramas)
    saida = []
    for bloco in documento.blocos:
        if bloco.diagrama_id is not None:
            d = por_id.get(bloco.diagrama_id)
            if d is not None:
                saida.append(d.linha_de_texto(numero[bloco.diagrama_id]))
            continue
        for linha in bloco.linhas:
            saida.append(" ".join("".join(normal(documento.chars[g]) for g in p.gids)
                                  for p in linha.palavras))
    return "\n".join(saida)


def numeros_dos_diagramas(documento: Documento, diagramas: Sequence) -> Dict[str, int]:
    """O número de cada diagrama ("Diagrama 1"): a ordem em que o documento os lê (a coluna da
    esquerda antes da da direita; no Mirkovic, p. 18, a altura dava 2, 3, 1, 4), e os que o
    documento não tem depois, de cima para baixo."""
    ordem = [b.diagrama_id for b in documento.blocos if b.diagrama_id is not None]
    vistos = set(ordem)
    ordem += [d.id for d in sorted(diagramas, key=lambda d: (d.caixa[1], d.caixa[0]))
              if d.id not in vistos]
    return {did: k for k, did in enumerate(dict.fromkeys(ordem), start=1)}


def texto_do_bloco(documento: Documento, bloco: Bloco, modo: str = IMPRESSO) -> str:
    """O texto de um bloco de texto: uma linha impressa por linha."""
    normal = normalizador(modo)
    return "\n".join(" ".join("".join(normal(documento.chars[g]) for g in p.gids)
                              for p in linha.palavras) for linha in bloco.linhas)


def pagina_avulsa(entries, diagramas=(), zonas=()) -> Pagina:
    """Uma `Pagina` com gids provisórios, para montar o texto de uma lista de `BoxEntry`
    (o adaptador do passo 1b: a janela e a exportação ainda trabalham com listas)."""
    from abbychess.modelo import Box, gid_de

    diagramas = list(diagramas)
    if any(not d.id for d in diagramas):
        from abbychess.diagramas import com_ids

        diagramas = com_ids(diagramas)
    return Pagina(pid=0, indice=0, boxes=[Box(gid_de(0, i), e) for i, e in enumerate(entries)],
                  diagramas=diagramas, zonas=list(zonas), proximo_n=len(entries))
