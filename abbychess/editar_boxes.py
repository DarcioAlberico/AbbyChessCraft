"""Editar os boxes da página: dividir, juntar, criar e mover as bordas, e os glifos marcados
à mão que reconhecer de novo não troca.

Sem interface, como a `pagina`, de onde vêm a página em tons de cinza (`cinza`) e a leitura
de um box (`_ler_um`): cada edição relê na hora os boxes que criou ou mudou (`_reler`).
"""

from __future__ import annotations

from dataclasses import replace
from typing import List, Optional

import numpy as np
from PIL import Image

from core import proporcao
from core.box_model import BoxEntry
from core.services.box_service import BoxService

from abbychess.leitor import LeitorDoLivro
from abbychess.pagina import Caixa, _contido, _ler_um, cinza


def _reler(imagem: Image.Image, boxes: List[BoxEntry], indices: List[int],
           leitor: Optional[LeitorDoLivro]) -> None:
    """Lê de novo só os boxes que uma edição criou ou mudou."""
    if leitor is None:
        return
    pagina = cinza(imagem)
    referencia = proporcao.altura_de_referencia(boxes) if boxes else None
    for i in indices:
        _ler_um(pagina, boxes[i], leitor, referencia)


def dividir(imagem: Image.Image, boxes: List[BoxEntry], indice: int,
            leitor: Optional[LeitorDoLivro] = None, *, x: Optional[int] = None) -> List[int]:
    """Divide em dois o box que juntou dois glifos, e relê as partes.

    Com `x`, a coluna da página onde cortar, o corte é vertical ali: é o ponto
    que o usuário escolheu no recorte ampliado. Sem `x`, quem decide é o
    `BoxService.split_box` do PyBoxEditor, que corta no vão mais fundo da tinta
    e escolhe o eixo sozinho.

    **Cada parte é aparada à própria tinta.** Num "rp" colado, o box vai da
    altura do x ao fim da perna do "p"; sem aparar, o "r" sairia com a altura
    do par, e a altura relativa que o padrão do livro grava ensinaria um "r"
    do tamanho de um "p".

    **O pingo do "i" não é um glifo.** Em "vi", "wi" e "xi" o vão horizontal sob o
    pingo é mais fundo que o vertical entre as letras, e o core corta ali (ele diz
    isso na própria `split_box`): saíam o pingo e o par sem pingo, um em cima do
    outro, e o pingo solto partia a linha. Quando a parte de cima é só um pingo, o
    corte vai para o vão vertical mais fundo do resto (`_corte_sob_o_pingo`).

    As partes entram no lugar do box, a da esquerda (ou de cima) primeiro, sem
    leitura e fora do manual. Com `leitor`, são relidas na hora. Devolve os
    índices das duas; os boxes depois de `indice` andam uma casa para a frente.
    """
    box = boxes[indice]
    matriz = np.asarray(imagem.convert("L"))
    tinta = BoxService._tinta_do_box(box, matriz)
    if x is None:
        partes = BoxService.split_box(box, matriz)
        coluna = _corte_sob_o_pingo(partes, box, tinta)
        if coluna is not None:
            partes = [replace(box, x2=coluna), replace(box, x1=coluna)]
    else:
        if not box.x1 < x < box.x2:
            raise ValueError(f"O corte em x={x} está fora do box ({box.x1}..{box.x2}).")
        partes = [replace(box, x2=x), replace(box, x1=x)]
    novas = []
    for parte in partes:
        parte = replace(parte, char="", source="", confidence=0.0,
                        angulo=box.angulo, negativo=box.negativo, moldura=box.moldura)
        aparada = _aparar(parte, box, tinta)
        if aparada is None:
            raise ValueError("Um dos lados do corte ficou sem tinta.")
        novas.append(aparada)
    boxes[indice:indice + 1] = novas
    _reler(imagem, boxes, [indice, indice + 1], leitor)
    return [indice, indice + 1]


#: O pingo: a parte de cima aparada com até esta fração da altura e da largura do box.
PINGO_ALTURA, PINGO_LARGURA = 0.3, 0.5


def _corte_sob_o_pingo(partes: List[BoxEntry], box: BoxEntry, tinta) -> Optional[int]:
    """A coluna onde cortar quando o core cortou sob o pingo de um "i"; senão, `None`.

    O vão vertical é medido só na tinta de baixo do corte do core, sem o pingo, pela
    mesma régua do core (`_vale_mais_fundo`, com a margem dele)."""
    if tinta is None or len(partes) != 2 or (box.angulo or 0) % 180:
        return None                                  # girado, o corte em y é o certo
    de_cima = partes[0]
    if (de_cima.x1, de_cima.x2) != (box.x1, box.x2) or de_cima.y2 >= box.y2:
        return None                                  # o core cortou na coluna
    pingo = _aparar(de_cima, box, tinta)
    if pingo is None or (pingo.y2 - pingo.y1 > PINGO_ALTURA * box.height
                         or pingo.x2 - pingo.x1 > PINGO_LARGURA * box.width):
        return None
    vale = BoxService._vale_mais_fundo(tinta[de_cima.y2 - box.y1:].sum(axis=0),
                                       BoxService.MARGEM_DO_CORTE)
    return box.x1 + vale[0] if vale else None


def _aparar(parte: BoxEntry, inteiro: BoxEntry, tinta) -> Optional[BoxEntry]:
    """A parte encolhida até a tinta dela, medida na máscara do box inteiro."""
    if tinta is None:
        return parte
    pedaco = tinta[parte.y1 - inteiro.y1:parte.y2 - inteiro.y1,
                   parte.x1 - inteiro.x1:parte.x2 - inteiro.x1]
    linhas, colunas = np.nonzero(pedaco)
    if not linhas.size:
        return None
    return replace(parte, x1=parte.x1 + int(colunas.min()), x2=parte.x1 + int(colunas.max()) + 1,
                   y1=parte.y1 + int(linhas.min()), y2=parte.y1 + int(linhas.max()) + 1)


def criar_box(imagem: Image.Image, boxes: List[BoxEntry], area: Caixa,
              leitor: Optional[LeitorDoLivro] = None) -> int:
    """Cria o box do glifo dentro da área que o usuário desenhou, e o lê.

    É o quadro do treino de padrões do FineReader: o glifo que a segmentação
    perdeu, partiu ou juntou com o vizinho se marca à mão. A área é aparada à
    tinta, e os boxes que ficam dentro dela (o "m" quebrado em três) saem: o
    quadro novo os substitui. O box entra na ordem de leitura da página.

    Devolve o índice dele; os outros índices mudam, e quem guarda índices os
    remapeia pela identidade dos boxes.
    """
    largura, altura = imagem.size
    x1, y1, x2, y2 = area
    x1, x2 = sorted((x1, x2))
    y1, y2 = sorted((y1, y2))
    quadro = BoxService.clamp_box(BoxEntry("", x1, y1, x2, y2), largura, altura)
    if quadro.x2 - quadro.x1 < 1 or quadro.y2 - quadro.y1 < 1:
        raise ValueError("A área está fora da página.")
    tinta = BoxService._tinta_do_box(quadro, np.asarray(imagem.convert("L")))
    novo = _aparar(quadro, quadro, tinta) if tinta is not None and tinta.any() else None
    if novo is None:
        raise ValueError("Não há tinta na área marcada.")
    dentro = [b for b in boxes if _contido(b, (novo.x1, novo.y1, novo.x2, novo.y2))
              or _centro_dentro(b, novo)]
    restantes = [b for b in boxes if not any(b is d for d in dentro)]
    boxes[:] = BoxService.sort_boxes_reading_order(restantes + [novo])
    indice = next(i for i, b in enumerate(boxes) if b is novo)
    _reler(imagem, boxes, [indice], leitor)
    return indice


def a_manter_na_releitura(boxes, lida: bool) -> List[BoxEntry]:
    """Os glifos que reconhecer de novo não troca (§4.6), como cópias dos `BoxEntry`: numa
    página ainda não lida, os marcados à mão (todos os boxes dela); numa lida, os que o usuário
    decidiu (fonte `manual`) ou viu e aceitou (`revisado`). `boxes` são os `Box` do modelo.
    As decisões dos outros passam aos glifos novos pela sobreposição (`modelo.reconciliar`)."""
    from abbychess.edicao import copia
    from abbychess.leitor import FONTE_MANUAL

    return [copia(b.entry) for b in boxes
            if not lida or b.entry.source == FONTE_MANUAL or b.revisado]


def manter_marcados(segmentados: List[BoxEntry], marcados: List[BoxEntry]) -> List[BoxEntry]:
    """Os boxes da segmentação com os glifos marcados à mão no lugar dos de baixo.

    É o F5 (ou o lote) numa página em que o usuário marcou glifos antes de
    reconhecer: o quadro dele vale mais que o box que a segmentação achou ali.
    Sai o box segmentado cujo centro cai dentro de um marcado, ou que tem mais
    da metade da área dentro dele. O resto fica, em ordem de leitura.
    """
    def coberto(b: BoxEntry) -> bool:
        area = max((b.x2 - b.x1) * (b.y2 - b.y1), 1)
        for m in marcados:
            largura = min(b.x2, m.x2) - max(b.x1, m.x1)
            altura = min(b.y2, m.y2) - max(b.y1, m.y1)
            if _centro_dentro(b, m) or (largura > 0 and altura > 0
                                        and largura * altura > 0.5 * area):
                return True
        return False

    return BoxService.sort_boxes_reading_order(
        [b for b in segmentados if not coberto(b)] + list(marcados))


def _centro_dentro(b: BoxEntry, quadro: BoxEntry) -> bool:
    cx, cy = (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2
    return quadro.x1 <= cx <= quadro.x2 and quadro.y1 <= cy <= quadro.y2


def vizinho(boxes: List[BoxEntry], indice: int, passo: int) -> Optional[int]:
    """O box ao lado na ordem de leitura, se ele estiver na mesma linha.

    Mesma linha é sobrepor na vertical: o fim de uma linha e o começo da
    seguinte são vizinhos na lista, mas juntá-los não é o que se quer.
    """
    outro = indice + passo
    if not 0 <= outro < len(boxes) or passo == 0:
        return None
    a, b = boxes[indice], boxes[outro]
    return outro if min(a.y2, b.y2) > max(a.y1, b.y1) else None


def juntar(imagem: Image.Image, boxes: List[BoxEntry], i: int, j: int,
           leitor: Optional[LeitorDoLivro] = None) -> int:
    """Junta dois boxes num só, o retângulo que cobre os dois, e o relê.

    É o contrário de `dividir`: para o glifo que a segmentação partiu, como um
    "m" quebrado em dois ou um acento solto da letra. O box novo fica no lugar
    do primeiro na ordem de leitura e herda o ângulo e a polaridade dele.
    Devolve o índice dele; os boxes depois do segundo andam uma casa para trás.
    """
    if i == j:
        raise ValueError("Não dá para juntar um box com ele mesmo.")
    i, j = sorted((i, j))
    a, b = boxes[i], boxes[j]
    boxes[i] = replace(a, char="", source="", confidence=0.0,
                       x1=min(a.x1, b.x1), y1=min(a.y1, b.y1),
                       x2=max(a.x2, b.x2), y2=max(a.y2, b.y2))
    del boxes[j]
    _reler(imagem, boxes, [i], leitor)
    return i


def ajustar(imagem: Image.Image, boxes: List[BoxEntry], indice: int,
            leitor: Optional[LeitorDoLivro] = None, *,
            esquerda: int = 0, cima: int = 0, direita: int = 0, baixo: int = 0) -> BoxEntry:
    """Move as bordas do box, em pixels da página, e o relê.

    Positivo move a borda para a direita ou para baixo, como as coordenadas.
    O box fica dentro da página (`BoxService.clamp_box`) e com pelo menos um
    pixel de cada lado; a leitura antiga, mesmo a manual, vale para o desenho
    antigo e sai.
    """
    box = boxes[indice]
    largura, altura = imagem.size
    novo = BoxService.clamp_box(replace(box, x1=box.x1 + esquerda, y1=box.y1 + cima,
                                        x2=box.x2 + direita, y2=box.y2 + baixo),
                                largura, altura)
    if novo.x2 - novo.x1 < 1 or novo.y2 - novo.y1 < 1:
        raise ValueError("O box ficaria vazio.")
    boxes[indice] = replace(box, char="", source="", confidence=0.0,
                            x1=novo.x1, y1=novo.y1, x2=novo.x2, y2=novo.y2)
    _reler(imagem, boxes, [indice], leitor)
    return boxes[indice]
