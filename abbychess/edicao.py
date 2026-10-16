"""As edições da página por gid (SPEC §4.1, §4.2): cada uma devolve a `Diferenca`.

As operações de caixa (dividir, juntar, marcar um quadro, descartar) usam as funções de
`abbychess.pagina`, que trabalham sobre a lista de `BoxEntry`, e dizem os sucessores
explicitamente: aqui não há adivinhação por sobreposição (essa é do adaptador da janela,
`modelo.reconciliar`). As decisões (quebrar e juntar palavras, o glifo virtual, o parágrafo)
não mexem nos boxes. Toda edição passa por `Pagina.aplicar`, que leva as decisões aos
sucessores.

Só a thread da interface edita a página (§4.1). Sem Qt.
"""

from __future__ import annotations

from dataclasses import replace
from typing import List, Optional, Tuple

from abbychess import pagina as pg
from abbychess import procedencia
from abbychess.modelo import Box, Decisoes, Diferenca, GlifoVirtual, Pagina


def _novos(pagina: Pagina, entries, de: int, ate: int) -> List[Box]:
    return [Box(pagina.alocar(), e, procedencia.amostra_de(e) or None) for e in entries[de:ate]]


def dividir(pagina: Pagina, imagem, gid: int, leitor=None, *, x: Optional[int] = None) -> Diferenca:
    """O glifo `gid` em dois (ver `pagina.dividir`); as partes são os sucessores dele."""
    i = pagina.indice_de(gid)
    entries = pagina.entries()
    pg.dividir(imagem, entries, i, leitor, x=x)
    partes = _novos(pagina, entries, i, i + 2)
    dif = Diferenca(removidos={gid}, novos=partes, sucessores={gid: [b.gid for b in partes]})
    return pagina.aplicar(dif, pagina.boxes[:i] + partes + pagina.boxes[i + 1:])


def juntar(pagina: Pagina, imagem, gid_a: int, gid_b: int, leitor=None) -> Diferenca:
    """Os dois glifos num só (ver `pagina.juntar`), sucessor dos dois."""
    i, j = sorted((pagina.indice_de(gid_a), pagina.indice_de(gid_b)))
    velhos = (pagina.boxes[i].gid, pagina.boxes[j].gid)
    entries = pagina.entries()
    pg.juntar(imagem, entries, i, j, leitor)
    [novo] = _novos(pagina, entries, i, i + 1)
    boxes = list(pagina.boxes)
    boxes[i] = novo
    del boxes[j]
    dif = Diferenca(removidos=set(velhos), novos=[novo],
                    sucessores={g: [novo.gid] for g in velhos})
    return pagina.aplicar(dif, boxes)


def marcar(pagina: Pagina, imagem, area, leitor=None) -> Diferenca:
    """O quadro desenhado vira um glifo (ver `pagina.criar_box`); os que ficaram dentro
    dele saem, e o glifo novo é o sucessor de cada um."""
    entries = pagina.entries()
    por_objeto = {id(b.entry): b for b in pagina.boxes}
    k = pg.criar_box(imagem, entries, area, leitor)
    ficaram = {id(e) for e in entries}
    [novo] = _novos(pagina, entries, k, k + 1)
    sairam = [b.gid for b in pagina.boxes if id(b.entry) not in ficaram]
    boxes = [novo if i == k else por_objeto[id(e)] for i, e in enumerate(entries)]
    dif = Diferenca(removidos=set(sairam), novos=[novo],
                    sucessores={g: [novo.gid] for g in sairam})
    return pagina.aplicar(dif, boxes)


def descartar(pagina: Pagina, gid: int) -> Diferenca:
    """Tira o glifo da página (não é caractere): sai sem sucessor."""
    i = pagina.indice_de(gid)
    dif = Diferenca(removidos={gid}, sucessores={gid: []})
    return pagina.aplicar(dif, pagina.boxes[:i] + pagina.boxes[i + 1:])


def corrigir(pagina: Pagina, gid: int, char: str) -> Diferenca:
    """Aceita o caractere do glifo sem ensinar (ver `pagina.confirmar`)."""
    i = pagina.indice_de(gid)
    entries = pagina.entries()
    pg.confirmar(entries, i, char)
    pagina.boxes[i] = replace(pagina.boxes[i], amostra=None)
    return pagina.aplicar(Diferenca(mudados={gid}), pagina.boxes)


# ----------------------------------------------------------------------
# As decisões (§4.2): não mexem nos boxes
# ----------------------------------------------------------------------

def _decidir(pagina: Pagina, decisoes: Decisoes, mudados=()) -> Diferenca:
    pagina.decisoes = decisoes
    return Diferenca(mudados=set(mudados))


def quebrar(pagina: Pagina, gid: int) -> Diferenca:
    """Palavra nova antes do glifo (o espaço que a leitura não viu)."""
    _vivo(pagina, gid)
    d = pagina.decisoes
    return _decidir(pagina, replace(d, quebras=d.quebras | {gid}), [gid])


def juntar_palavras(pagina: Pagina, ultimo: int, primeiro: int) -> Diferenca:
    """A palavra que termina em `ultimo` e a que começa em `primeiro`, numa só (o espaço
    que a leitura viu e não existe)."""
    _vivo(pagina, ultimo)
    _vivo(pagina, primeiro)
    if ultimo == primeiro:
        raise ValueError("Uma palavra não se junta com ela mesma.")
    d = pagina.decisoes
    return _decidir(pagina, replace(d, juncoes=d.juncoes | {(ultimo, primeiro)},
                                    quebras=d.quebras - {primeiro}), [ultimo, primeiro])


def paragrafo(pagina: Pagina, gid: int) -> Diferenca:
    _vivo(pagina, gid)
    d = pagina.decisoes
    return _decidir(pagina, replace(d, paragrafo_antes=d.paragrafo_antes | {gid}), [gid])


def virtual(pagina: Pagina, char: str, depois_de: Optional[int], *,
            palavra_nova: bool = False) -> Tuple[Diferenca, int]:
    """O caractere que falta, depois do glifo `depois_de` (ou no começo, com `None`).
    Ganha um gid da página, como os boxes, mas não tem caixa. Devolve o gid dele."""
    if not char:
        raise ValueError("O glifo virtual precisa de um caractere.")
    if depois_de is not None:
        _vivo(pagina, depois_de)
    gid = pagina.alocar()
    d = pagina.decisoes
    novo = GlifoVirtual(gid, char, depois_de, palavra_nova)
    return _decidir(pagina, replace(d, virtuais=d.virtuais + (novo,))), gid


def _vivo(pagina: Pagina, gid: int) -> None:
    if gid not in pagina.vivos:
        raise ValueError(f"O glifo {gid} não está na página.")
