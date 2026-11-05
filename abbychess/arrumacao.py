"""O que a página ganha depois de mudar, num lugar só (SPEC-qualidade Q-A2): `arrumar`, o fim
de toda edição (os ids, as legendas, os lances validados), e `aplicar_lida`, o que uma leitura
deixa na página, a mesma para o F5 e para o lote. Funções puras sobre a `Pagina`: sem janela,
sem disco, sem histórico (quem chama grava e registra)."""

from __future__ import annotations

from typing import List, Optional, Tuple

from abbychess import diagramas as dg
from abbychess import lances as lc
from abbychess import montagem as mo
from abbychess import procedencia
from abbychess import zonas as zn
from abbychess.modelo import IOU_DA_RELEITURA, Pagina, descrever_caidas, proximo_estado, reconciliar


def arrumar(pagina: Pagina, idioma: str) -> None:
    """Os ids das áreas e dos diagramas (antes de medir: o que a transação guarda é o que vai
    para o disco), a legenda de cada diagrama e a validação dos lances."""
    pagina.zonas = zn.com_ids(list(pagina.zonas))
    pagina.diagramas = dg.com_ids(list(pagina.diagramas))
    pagina.zonas = zn.vincular_legendas(pagina.zonas, pagina.diagramas)
    pagina.diagramas = lc.validar_pagina(pagina, idioma)


def aplicar_lida(pagina: Pagina, lida, idioma: str, *,
                 tamanho: Optional[Tuple[int, int]] = None, zona=None) -> List[str]:
    """Põe na página o que o servidor leu (`servidor_de_leitura.PaginaLida`): os glifos
    reconciliados com os de antes (as decisões seguem os glifos, §4.6), os tabuleiros, os
    diagramas (a conferência de antes vale mais que a releitura do mesmo tabuleiro), as áreas
    automáticas e a função delas pelo texto (com o `tamanho` da imagem), o estado. Com `zona`,
    só o que está nela muda (Reconhecer a área). Devolve as decisões que não puderam seguir
    os glifos relidos, descritas."""
    de_antes = list(pagina.boxes)
    estilos = lida.estilos()
    if zona is None and lida.regua_do_negrito:   # a de uma área só não é a da página
        pagina.regua_do_negrito = dict(lida.regua_do_negrito)
    depois = list(lida.boxes)
    tabuleiros = [tuple(int(v) for v in t) for t in lida.tabuleiros]
    mo.corrigir_a_caixa_na_leitura(depois, tabuleiros)
    if zona is not None:
        depois, tabuleiros = _com_o_de_fora_da_zona(pagina, zona, depois, tabuleiros)
    novos, dif = reconciliar(pagina.boxes, depois, pagina.alocar, procedencia.amostra_de,
                             estilo_de=lambda entry: estilos.get(id(entry)),
                             iou_minimo=IOU_DA_RELEITURA)
    pagina.aplicar(dif, novos)
    pagina.tabuleiros = tabuleiros
    pagina.diagramas = dg.com_ids(dg.mesclar(lida.diagramas,
                                             dg.para_caixas(pagina.tabuleiros, pagina.diagramas)))
    if tamanho is not None:
        pagina.zonas = _zonas_depois_de_ler(pagina, lida, tamanho)
    arrumar(pagina, idioma)
    pagina.estado = proximo_estado(pagina.estado, "reconhecer")
    return descrever_caidas(dif.caidas, de_antes) if dif.caidas else []


def _zonas_depois_de_ler(pagina: Pagina, lida, tamanho: Tuple[int, int]) -> list:
    """A página de imagem (L-9) ganha uma área só, de figura: nenhum estado novo. A sem áreas ganha
    as automáticas; as automáticas feitas antes de ler (o modelo aplicado ao livro antes do lote),
    a função pelo texto lido."""
    if lida.imagem:
        return [zn.Zona(zn.IMAGEM, 0, 0, tamanho[0], tamanho[1], funcao="figura")]
    return zn.depois_de_ler(pagina.zonas, pagina.entries(), pagina.tabuleiros, pagina.diagramas,
                            *tamanho)


def _com_o_de_fora_da_zona(pagina: Pagina, zona, depois: list, tabuleiros: list) -> tuple:
    """Reconhecer a área: os boxes e os tabuleiros lidos nela, com os da página que estão fora
    dela (os boxes na ordem de leitura)."""
    from core.services.box_service import BoxService

    fora = [b.entry for b in pagina.boxes if not zona.contem_o_centro(b.entry)]
    depois = BoxService.sort_boxes_reading_order(fora + depois)
    tabuleiros = [t for t in pagina.tabuleiros
                  if not zona.contem((t[0] + t[2]) / 2, (t[1] + t[3]) / 2)] + tabuleiros
    return depois, tabuleiros
