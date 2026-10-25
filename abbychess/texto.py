"""O documento da página e o texto dele (SPEC §4.2): `montar` e a normalização única.

**O documento é derivado.** `montar(pagina)` é função pura dos boxes, das áreas, das
decisões do usuário e dos diagramas: `Documento(blocos)`, cada `Bloco` com a área de onde
veio e a função dela, e linhas de palavras de gids. Nada do documento é gravado; quem
precisa do texto monta de novo.

- **Linhas e palavras** são as do core (`core.notacao.palavras_da_pagina`), que já são as do
  texto de hoje, com os acertos de `layout` (o espaço depois do "f", os vãos largos).
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

from abbychess.layout import OrdemDeLeitura
from abbychess.modelo import Decisoes, Pagina

IMPRESSO = "impresso"
SAN = "san"
MODOS = (IMPRESSO, SAN)

#: Ligaduras tipográficas que ocupam um box, mas têm mais de uma letra no texto.
#: O Documento repete o gid do box para cada letra resultante.
LIGADURAS = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}

_FIM_DE_FRASE = re.compile(r"[.:!?]\s*$")


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
    linhas = _linhas_da_pagina(*_lidos(pagina, True))[0]
    return [p for ln in _aplicar_decisoes(linhas, pagina.decisoes) for p in ln]


def montar(pagina: Pagina, *, com_os_nao_lidos: bool = False) -> Documento:
    """O documento da página (função pura do que está gravado nela). O texto e a exportação
    só têm os glifos lidos; a vista do Documento (`com_os_nao_lidos`) mostra também os que
    ninguém leu, como `NAO_LIDO`, para o realce deles (§6.1)."""
    lidos, entries = _lidos(pagina, com_os_nao_lidos)
    chars = {b.gid: e.char for b, e in zip(lidos, entries)}
    chars.update({v.gid: v.char for v in pagina.decisoes.virtuais})
    linhas, topos, trechos, ordem = _linhas_da_pagina(lidos, entries)
    linhas = _aplicar_decisoes(linhas, pagina.decisoes)
    texto_das_linhas = [" ".join("".join(chars[g] for g in p) for p in ln) for ln in linhas]

    por_gid = {b.gid: e for b, e in zip(lidos, entries)}
    zonas_de_texto = [z for z in pagina.zonas if z.tipo == "texto"]
    zona_da_linha = [_zona_da_linha(ln, por_gid, zonas_de_texto) for ln in linhas]
    # Um parágrafo antes de qualquer glifo da linha começa o bloco nessa linha (o
    # documento é feito de linhas inteiras; partir uma linha é do layout, passo F).
    novo_paragrafo = [any(g in pagina.decisoes.paragrafo_antes for p in ln for g in p)
                      for ln in linhas]

    # Onde cada diagrama entra: antes da linha `lugar` (len(linhas) = no fim).
    altura = float(np.median([e.y2 - e.y1 for e in entries])) if entries else 0.0
    antes_da_linha: Dict[int, List[str]] = {}
    diagramas = sorted(pagina.diagramas, key=lambda d: (d.caixa[1], d.caixa[0]))
    for d in diagramas:
        lugar = _lugar_do_diagrama(d.caixa, ordem, linhas, topos, trechos, texto_das_linhas,
                                   por_gid, altura)
        antes_da_linha.setdefault(lugar, []).append(d.id)

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
            for did in antes_da_linha[j]:
                blocos.append(Bloco(f"b{len(blocos)}", None, "diagrama", diagrama_id=did))
        if atual and (zona_da_linha[j] is not atual_zona or novo_paragrafo[j]):
            fechar()
        atual_zona = zona_da_linha[j]
        atual.append(Linha(tuple(Palavra(tuple(p)) for p in ln)))
    fechar()
    for did in antes_da_linha.get(len(linhas), []):
        blocos.append(Bloco(f"b{len(blocos)}", None, "diagrama", diagrama_id=did))
    return Documento(tuple(_na_ordem_das_zonas(blocos, pagina.zonas)), chars,
                     {b.gid: b.estilo for b in lidos})


def _lugar_do_diagrama(caixa, ordem: OrdemDeLeitura, linhas, topos, trechos,
                       texto_das_linhas, por_gid, altura: float) -> int:
    """Antes de qual linha o diagrama entra (len(linhas) = no fim).

    No trecho (a coluna) dele, antes da primeira linha na altura dele ou abaixo; sem linha
    assim no trecho, antes da primeira do trecho seguinte. Só a linha ao lado do tabuleiro,
    a do parágrafo que o contorna, pede um fim de frase antes: o parágrafo não é partido no
    meio. A linha de lances logo acima ("52.bxc7 ♔d7 … 54.♔xa5", sem ponto) não segura
    mais o diagrama, que caía depois do parágrafo de baixo (p. 54 do Aagaard).
    """
    x1, y1, x2, y2 = caixa
    chave = ordem.chave((x1 + x2) / 2, y1)
    j = next((j for j in range(len(linhas)) if (trechos[j], topos[j]) >= (chave, y1 - altura)),
             len(linhas))
    if j == len(linhas) or trechos[j] != chave:
        return j
    caixas = [por_gid[g] for p in linhas[j] for g in p if g in por_gid]
    ao_lado = bool(caixas) and (min(e.y1 for e in caixas) < y2
                                and (max(e.x2 for e in caixas) <= x1 or min(e.x1 for e in caixas) >= x2))
    if not ao_lado:
        return j
    return next((k for k in range(max(j, 1), len(linhas))
                 if _FIM_DE_FRASE.search(texto_das_linhas[k - 1])), len(linhas))


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


def _linhas_da_pagina(lidos, entries) -> Tuple[List[List[List[int]]], List[int],
                                               List[tuple], OrdemDeLeitura]:
    """As palavras (gids) de cada linha na ordem de leitura, o topo e o trecho de cada linha,
    e a ordem de leitura (os diagramas entram no trecho deles). A ordem de leitura e as
    linhas são ~85% do `montar` (~15–20 ms numa página do livro): guardadas pela chave,
    corrigir um caractere não as refaz."""
    chave = _chave_das_linhas(lidos, entries)
    if chave is not None:
        with _TRAVA_DAS_LINHAS:
            vistas = _LINHAS_VISTAS.get(chave)
            if vistas is not None:
                _LINHAS_VISTAS.move_to_end(chave)
        if vistas is not None:
            linhas, topos, trechos, ordem = vistas
            return [[list(p) for p in ln] for ln in linhas], list(topos), list(trechos), ordem
    linhas: List[List[List[int]]] = []
    topos: List[int] = []
    trechos: List[tuple] = []
    ordem = OrdemDeLeitura.da_pagina(entries)
    for chave_do_trecho, indices in ordem.trechos(entries):
        trecho = [entries[i] for i in indices]
        for linha in ordem.linhas_do_trecho(indices, entries):
            palavras = [[lidos[indices[s.indice]].gid for s in p.simbolos] for p in linha]
            palavras = [p for p in palavras if p]
            if palavras:
                linhas.append(palavras)
                topos.append(min(trecho[s.indice].y1 for p in linha for s in p.simbolos))
                trechos.append(chave_do_trecho)
    if chave is not None:
        with _TRAVA_DAS_LINHAS:
            _LINHAS_VISTAS[chave] = (tuple(tuple(tuple(p) for p in ln) for ln in linhas),
                                     tuple(topos), tuple(trechos), ordem)
            while len(_LINHAS_VISTAS) > LINHAS_GUARDADAS:
                _LINHAS_VISTAS.popitem(last=False)
    return linhas, topos, trechos, ordem


def _aplicar_decisoes(linhas: List[List[List[int]]], decisoes: Decisoes) -> List[List[List[int]]]:
    """As quebras, as junções e os virtuais aplicados às palavras de cada linha."""
    saida = []
    for linha in linhas:
        palavras: List[List[int]] = []
        for p in linha:                                       # quebras
            atual = [p[0]]
            for g in p[1:]:
                if g in decisoes.quebras:
                    palavras.append(atual)
                    atual = [g]
                else:
                    atual.append(g)
            palavras.append(atual)
        juntas: List[List[int]] = []
        for p in palavras:                                    # junções
            if juntas and (juntas[-1][-1], p[0]) in decisoes.juncoes:
                juntas[-1] = juntas[-1] + p
            else:
                juntas.append(list(p))
        saida.append(juntas)
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
    return saida


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
    """A área de texto que contém o meio da linha (a primeira, se mais de uma)."""
    entries = [por_gid[g] for p in linha for g in p if g in por_gid]
    if not entries or not zonas:
        return None
    cx = (min(e.x1 for e in entries) + max(e.x2 for e in entries)) / 2
    cy = (min(e.y1 for e in entries) + max(e.y2 for e in entries)) / 2
    return next((z for z in zonas if z.contem(cx, cy)), None)


def _na_ordem_das_zonas(blocos: List[Bloco], zonas: Sequence) -> List[Bloco]:
    """Com `ordem` nas áreas, os blocos delas seguem essa ordem; o resto fica no lugar."""
    ordem = {z.id: z.ordem for z in zonas if z.id and z.ordem is not None}
    if not ordem:
        return blocos
    posicoes = [i for i, b in enumerate(blocos) if b.zona_id in ordem]
    ordenados = sorted((blocos[i] for i in posicoes), key=lambda b: ordem[b.zona_id])
    saida = list(blocos)
    for i, b in zip(posicoes, ordenados):
        saida[i] = b
    return saida


# ----------------------------------------------------------------------
# O texto
# ----------------------------------------------------------------------

def normalizar(char: str, modo: str) -> str:
    """O caractere como sai do programa no modo (§4.2)."""
    return _normalizador(modo)(char)


def _normalizador(modo: str):
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
    normal = _normalizador(modo)
    por_id = {d.id: d for d in diagramas}
    numero = {d.id: k for k, d in enumerate(sorted(diagramas, key=lambda d: (d.caixa[1], d.caixa[0])),
                                            start=1)}
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


def texto_do_bloco(documento: Documento, bloco: Bloco, modo: str = IMPRESSO) -> str:
    """O texto de um bloco de texto: uma linha impressa por linha."""
    normal = _normalizador(modo)
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
