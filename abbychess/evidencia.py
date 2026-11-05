"""O que a página diz contra a leitura, à parte de `contexto.pendentes` (SPEC da página perfeita,
F-1, F-3, X-1). `pendentes` é o que a leitura pode reler; a evidência não relê nada, e um glifo
marcado aqui nunca é trocado sozinho. Sem Qt.

**Marca forte:** o glifo sem leitura (□), a palavra que desmente a leitura e o lance ilegal. PP5
acrescenta os escores. O lance conferido (todos os glifos `manual`, `revisado` ou `nativa`) que a
validação rejeita é **aceito como impresso**: calculado de novo, sem marca e sem nada gravado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Tuple

from abbychess import contexto
from abbychess import decodificador_de_lances as dl
from abbychess import lances as lc
from abbychess.leitor import FONTE_MANUAL, FONTE_NATIVA

#: Ligado pelo ponto de parada do passo PPL, item 4 (`docs/revisoes/pp-l.md`): sem ele, só F-3.
X1_LIGADO = True
NINGUEM_LEU = "Ninguém leu"
A_PALAVRA_DESMENTE = "A palavra desmente"


def motivo_do_ilegal(impresso: str, motivo: str = "não se joga aqui") -> str:
    """O texto do F-3: diz os dois lados da dúvida, o lance e o diagrama (CA-F3.2)."""
    return f"{impresso} {motivo}. Erro de leitura, de impressão ou do diagrama?"


@dataclass(frozen=True)
class EvidenciaDaPagina:
    #: gid -> (o motivo, a sugestão), das marcas fortes.
    motivos: Dict[int, Tuple[str, str]] = field(default_factory=dict)
    #: Os gids dos lances ilegais; todos estão em `motivos`.
    ilegais: FrozenSet[int] = frozenset()

    @property
    def fortes(self) -> FrozenSet[int]:
        return frozenset(self.motivos)


def conferidos(pagina) -> FrozenSet[int]:
    """Os gids decididos: `revisado`, `manual` ou `nativa`."""
    return frozenset(b.gid for b in pagina.boxes
                     if b.revisado or b.entry.source in (FONTE_MANUAL, FONTE_NATIVA))


def rejeitados(documento, diagramas, chave: str) -> List[Tuple[Tuple[int, ...], str]]:
    """(gids, motivo) de cada lance que a posição desmente: o de F-3, da validação do diagrama, e
    os de X-1, da posição que anda pela página."""
    saida: List[Tuple[Tuple[int, ...], str]] = []
    vistos = set()
    for d in diagramas:
        gids = lc.gids_do_rejeitado(documento, d, chave)
        if gids:
            vistos.add(gids)
            saida.append((gids, motivo_do_ilegal(_impresso(documento, gids),
                                                  _sem_rotulo(d.validacao.aviso))))
    if X1_LIGADO:
        for t in dl.decodificar(documento, diagramas, chave).ilegais:
            if t.gids not in vistos:
                vistos.add(t.gids)
                motivo = t.motivo[len(t.impresso) + 1:] if t.motivo.startswith(t.impresso) else ""
                saida.append((t.gids, motivo_do_ilegal(t.impresso, motivo or "não se joga aqui")))
    return saida


def _impresso(documento, gids) -> str:
    return "".join(documento.chars.get(g, "") for g in gids)


def _sem_rotulo(aviso: str) -> str:
    """O motivo de um aviso da validação (`1.Bf3 do texto não é legal aqui`), sem o lance."""
    return aviso.split(" do texto ", 1)[1] if " do texto " in aviso else "não se joga aqui"


def _dos_glifos(pagina, feitos) -> Dict[int, Tuple[str, str]]:
    """O □ e a palavra que desmente a leitura, nos glifos por decidir."""
    motivos: Dict[int, Tuple[str, str]] = {}
    sugestoes = contexto.julgar(pagina)
    for b in pagina.boxes:
        if b.gid in feitos:
            continue
        if not b.entry.char:
            motivos[b.gid] = (NINGUEM_LEU, "")
        elif b.gid in sugestoes and contexto.volta_pelo_contexto(b.entry.source):
            motivos[b.gid] = (A_PALAVRA_DESMENTE, sugestoes[b.gid] or "")
    return motivos


def da_pagina(pagina, documento, diagramas, chave: str) -> EvidenciaDaPagina:
    """A evidência da página aberta. `documento`, o `tx.montar` com os glifos não lidos."""
    feitos = conferidos(pagina)
    motivos = _dos_glifos(pagina, feitos)
    ilegais = set()
    for gids, motivo in rejeitados(documento, diagramas, chave):
        if not all(g in feitos for g in gids):
            ilegais.update(gids)
            for g in gids:
                motivos[g] = (motivo, "")
    return EvidenciaDaPagina(motivos, frozenset(ilegais))


def contagens_dos_lances(pagina, documento, diagramas, chave: str) -> Dict[str, int]:
    """As quatro contagens do relatório de lances (F-4), da página: `ilegais` (por conferir),
    `aceitos` como impressos, `sem_posicao` e `nao_conferidos`."""
    feitos = conferidos(pagina)
    decodificada = dl.decodificar(documento, diagramas, chave) if X1_LIGADO else dl.Decodificada()
    rejeitos = rejeitados(documento, diagramas, chave)
    ilegais = sum(not all(g in feitos for g in gids) for gids, _m in rejeitos)
    return {"ilegais": ilegais, "aceitos": len(rejeitos) - ilegais,
            "sem_posicao": sum(t.estado == dl.SEM_POSICAO and not all(g in feitos for g in t.gids)
                               for t in decodificada.lances),
            "nao_conferidos": dl.lances_por_conferir(documento, feitos, chave)}


@dataclass(frozen=True)
class ItemDeLance:
    """Um lance do relatório: a página, os gids, o tipo e o texto da linha em Resultados."""

    pagina: int
    gids: Tuple[int, ...]
    tipo: str
    texto: str


def itens_da_pagina(indice: int, pagina, documento, diagramas, chave: str) -> List[ItemDeLance]:
    """Os lances da página para o relatório: ilegais, aceitos como impressos, e não conferidos."""
    feitos = conferidos(pagina)
    itens: List[ItemDeLance] = []
    rejeitos = {gids: motivo for gids, motivo in rejeitados(documento, diagramas, chave)}
    for gids, motivo in rejeitos.items():
        tipo = "aceito como impresso" if all(g in feitos for g in gids) else "ilegal"
        itens.append(ItemDeLance(indice, gids, tipo, f"p. {indice + 1}: {tipo}: {motivo}"))
    return itens + _os_nao_conferidos(indice, documento, diagramas, chave, rejeitos, feitos)


def _os_nao_conferidos(indice, documento, diagramas, chave, rejeitos, feitos) -> List[ItemDeLance]:
    if not X1_LIGADO:
        return []
    itens = []
    for t in dl.decodificar(documento, diagramas, chave).lances:
        if t.gids not in rejeitos and not all(g in feitos for g in t.gids):
            tipo = "sem posição" if t.estado == dl.SEM_POSICAO else "não conferido"
            itens.append(ItemDeLance(indice, t.gids, tipo, f"p. {indice + 1}: {tipo}: {t.impresso}"))
    return itens
