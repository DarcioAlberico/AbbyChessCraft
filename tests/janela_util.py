"""A janela vista pelos testes: os glifos pela posição na lista, como o visor os mostra.

Desde o passo 2a o controlador guarda tudo por gid; os testes, escritos sobre a página
desenhada, falam de "o box 0", "o 3 foi pulado". Estas funções traduzem.
"""

from __future__ import annotations

from typing import List, Optional, Set


def boxes(janela) -> list:
    return janela.pagina.boxes


def atual(janela) -> Optional[int]:
    return janela.pagina.indice_de(janela.pagina.atual)


def fila(janela) -> List[int]:
    p = janela.pagina
    return [p.indice_de(g) for g in p.fila()]


def pulados(janela) -> Set[int]:
    p = janela.pagina
    return {p.indice_de(g) for g in p.pulados}


def selecao(janela) -> Set[int]:
    p = janela.pagina
    return {p.indice_de(g) for g in p.selecao}


def mostrar(janela, indice: int) -> None:
    janela.pagina.mostrar(janela.pagina.gid_em(indice))


def trocar_entries(janela, indice_da_pagina: int, mudar) -> None:
    """Muda os glifos de uma página como uma edição faria (cópias novas, a página trocada
    e agendada), para montar o cenário de um teste. `mudar(entry)` muda a cópia."""
    from dataclasses import replace

    projeto = janela.projeto
    pagina = projeto.carregar_modelo(indice_da_pagina)
    novos = []
    for b in pagina.boxes:
        e = replace(b.entry)
        mudar(e)
        novos.append(replace(b, entry=e))
    pagina.boxes = novos
    projeto.agendar(pagina)
    if indice_da_pagina == janela.pagina.indice:
        janela.pagina.eventos.emitir("glifos_mudaram", None)
