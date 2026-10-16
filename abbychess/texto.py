"""O documento da página e o texto dele (SPEC §4.2): `montar` e a normalização única.

**O documento é derivado.** `montar(pagina)` é função pura dos boxes, das áreas, das
decisões do usuário e dos diagramas: `Documento(blocos)`, cada `Bloco` com a área de onde
veio e a função dela, e linhas de palavras de gids. Nada do documento é gravado; quem
precisa do texto monta de novo.

- **Linhas e palavras** são as do core (`core.notacao.palavras_da_pagina`), que já são as do
  texto de hoje.
- **Decisões**: uma `quebra` parte a palavra antes do gid; uma `juncao` (a, b) junta a
  palavra que termina em `a` com a seguinte, que começa em `b`, na mesma linha; um glifo
  virtual entra depois de `depois_de` (na mesma palavra ou, com `palavra_nova`, numa nova),
  ou no começo da primeira linha; `paragrafo_antes` começa um bloco novo na linha do gid.
  O `hifen_de_quebra` é guardado para a exportação refluir o texto (passo J): a vista e a
  busca mostram as linhas como impressas.
- **Blocos**: linhas seguidas na mesma área de texto formam um bloco com a função da área;
  sem área, a função é `texto`. A ordem é a de leitura das linhas, salvo quando as áreas
  têm `ordem`: aí os blocos seguem a ordem delas.
- **Diagramas** entram como bloco próprio, no lugar de hoje
  (`diagramas.texto_da_pagina`): antes da primeira linha na altura deles ou abaixo, mas só
  num fim de frase; sem fim de frase, no fim.

**O texto** (`texto`) tem dois modos: `impresso` (♘ como impresso; a vista, a busca, o DOCX
e o EPUB) e `san` (as figurinhas como letras, ♘ → N; o PGN, a validação e o texto de hoje,
que vinha do core já assim). Os dois passam por `core.notacao.normalizar_saida`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from abbychess.modelo import Decisoes, Pagina

IMPRESSO = "impresso"
SAN = "san"
MODOS = (IMPRESSO, SAN)

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


@dataclass(frozen=True)
class Documento:
    blocos: Tuple[Bloco, ...]
    #: gid -> o caractere (os dos boxes como lidos, e os dos glifos virtuais).
    chars: Dict[int, str] = field(default_factory=dict)

    def gids(self) -> List[int]:
        """Os gids do documento, na ordem dele (cada um uma vez)."""
        return [g for b in self.blocos for ln in b.linhas for p in ln.palavras for g in p.gids]


# ----------------------------------------------------------------------
# Montar
# ----------------------------------------------------------------------

def montar(pagina: Pagina) -> Documento:
    """O documento da página (função pura do que está gravado nela)."""
    from core.notacao import palavras_da_pagina

    lidos = [b for b in pagina.boxes if b.entry.char]
    chars = {b.gid: b.entry.char for b in lidos}
    chars.update({v.gid: v.char for v in pagina.decisoes.virtuais})
    entries = [b.entry for b in lidos]
    linhas: List[List[List[int]]] = []
    topos: List[int] = []
    for linha in (palavras_da_pagina(entries) if entries else []):
        palavras = [[lidos[s.indice].gid for s in p.simbolos] for p in linha]
        palavras = [p for p in palavras if p]
        if palavras:
            linhas.append(palavras)
            topos.append(min(lidos[s.indice].entry.y1 for p in linha for s in p.simbolos))
    linhas = _aplicar_decisoes(linhas, pagina.decisoes)
    texto_das_linhas = [" ".join("".join(chars[g] for g in p) for p in ln) for ln in linhas]

    por_gid = {b.gid: b.entry for b in lidos}
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
        lugar = len(linhas)
        for j in range(1, len(linhas)):
            if topos[j] >= d.caixa[1] - altura and _FIM_DE_FRASE.search(texto_das_linhas[j - 1]):
                lugar = j
                break
        antes_da_linha.setdefault(lugar, []).append(d.id)

    blocos: List[Bloco] = []
    atual: List[Linha] = []
    atual_zona: Optional[object] = None

    def fechar():
        nonlocal atual
        if atual:
            zona = atual_zona
            blocos.append(Bloco(f"b{len(blocos)}", getattr(zona, "id", None) or None,
                                getattr(zona, "funcao", "texto"), tuple(atual)))
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
    return Documento(tuple(_na_ordem_das_zonas(blocos, pagina.zonas)), chars)


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
    ultimo: Dict[Optional[int], int] = {}                     # virtuais, na ordem em que
    for v in decisoes.virtuais:                               # foram digitados: o segundo
        depois = ultimo.get(v.depois_de, v.depois_de)         # depois do mesmo glifo vem
        _inserir_virtual(saida, v, depois)                    # depois do primeiro
        ultimo[v.depois_de] = v.gid
    return saida


def _inserir_virtual(linhas: List[List[List[int]]], v, depois: Optional[int]) -> None:
    """O virtual `v` depois do glifo `depois` (o âncora dele, ou o último virtual já posto
    nesse âncora), ou no começo da primeira linha."""
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

    if modo == SAN:
        return lambda c: FIGURINAS.get(c) or normalizar_saida(c)
    if modo == IMPRESSO:
        return normalizar_saida
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
