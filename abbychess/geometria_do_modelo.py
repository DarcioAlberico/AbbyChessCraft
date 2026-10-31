"""O modelo da página levado entre geometrias (SPEC §12.4, passo L): os glifos, as áreas, os
diagramas e as decisões quando a página ganha quadro ou giro (`reenquadrar`), quando se
divide em duas (`dividir`) e quando o usuário a endireita à mão (`endireitar`).

Saiu de `abbychess.modelo` no Q8 (o arquivo passou de 1 000 linhas ao partir as funções);
o modelo não depende daqui. Sem Qt.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, Optional, Set, Tuple

from core.box_model import BoxEntry

from abbychess.modelo import GLIFOS_MARCADOS, NAO_RECONHECIDA, Box, Decisoes, GlifoVirtual, Pagina


def _caixa(entry: BoxEntry) -> Tuple[int, int, int, int]:
    return (entry.x1, entry.y1, entry.x2, entry.y2)


def _na_caixa(box: Box, caixa, angulo: int) -> Box:
    x1, y1, x2, y2 = caixa
    return replace(box, entry=replace(box.entry, x1=x1, y1=y1, x2=x2, y2=y2,
                                      angulo=angulo % 360))


def reenquadrar(pagina: Pagina, para, tamanho: Optional[Tuple[int, int]]) -> bool:
    """Leva os boxes, as áreas, os tabuleiros e os diagramas da geometria da página à `para`
    (`(quadro, giro)`), com conta exata (`abbychess.geometria`). O glifo que não cabe no
    quadro novo vai para `pagina.fora`, com o gid e o lugar dele na ordem de leitura; o que
    estava fora e cabe volta ao lugar. O `angulo` do glifo (o do texto impresso, anti-horário)
    acompanha o giro. As áreas são aparadas no quadro; o tabuleiro e o diagrama que não cabem
    saem; tudo isso fica em `pagina.areas_fora` e volta como os glifos. Devolve se algo
    mudou. Sem `tamanho` (a página da fonte), levanta `ValueError`."""
    from abbychess import geometria as geo

    de, para = geo.normalizar(pagina.geometria), geo.normalizar(para)
    tamanho = tamanho or pagina.tamanho
    if de == para:
        return False
    if tamanho is None:
        raise ValueError("sem o tamanho da página da fonte, a geometria não muda")
    dentro, fora = _glifos_na_geometria(_na_pagina_inteira(pagina, de, tamanho), para, tamanho)
    zonas, tabuleiros, diagramas, areas_fora = _areas_na_geometria(pagina, de, para, tamanho)
    pagina.boxes, pagina.fora = dentro, tuple(fora)
    pagina.zonas, pagina.tabuleiros, pagina.diagramas = zonas, tabuleiros, diagramas
    pagina.areas_fora = areas_fora
    pagina.geometria, pagina.tamanho = para, tamanho
    return True


def _na_pagina_inteira(pagina: Pagina, de, tamanho: Tuple[int, int]) -> list:
    """(box, caixa na página inteira, ângulo da fonte) de cada glifo, na ordem de leitura,
    com os guardados fora do quadro de volta no lugar deles."""
    from abbychess import geometria as geo

    # Na página inteira, o glifo tem o ângulo da fonte: girar a página de g graus no sentido
    # horário tira g do ângulo anti-horário do texto.
    inteira = [(b, geo.para_a_fonte(_caixa(b.entry), de, tamanho), b.entry.angulo + de[1])
               for b in pagina.boxes]
    for lugar, box in sorted(pagina.fora, key=lambda t: t[0]):
        inteira.insert(min(lugar, len(inteira)), (box, _caixa(box.entry), box.entry.angulo))
    return inteira


def _glifos_na_geometria(inteira: list, para, tamanho: Tuple[int, int]) -> Tuple[list, list]:
    """Os glifos que cabem no quadro `para` e os que ficam fora, com o lugar deles."""
    from abbychess import geometria as geo

    dentro, fora = [], []
    for lugar, (box, caixa, angulo) in enumerate(inteira):
        nova = geo.da_fonte(caixa, para, tamanho)
        if nova is None:
            fora.append((lugar, _na_caixa(box, caixa, angulo)))
        else:
            dentro.append(_na_caixa(box, nova, angulo - para[1]))
    return dentro, fora


def _areas_na_geometria(pagina: Pagina, de, para, tamanho: Tuple[int, int]):
    """As áreas, os tabuleiros e os diagramas levados à `para`, e o que fica guardado."""
    guardadas = {}
    for tipo, lugar, objeto, aparada in pagina.areas_fora:
        guardadas.setdefault(tipo, []).append((lugar, objeto, aparada))

    def caixa_da_zona(z):
        return z.caixa

    def zona_com(z, c):
        return replace(z, x1=c[0], y1=c[1], x2=c[2], y2=c[3])

    zonas, fora_z = _levar(pagina.zonas, guardadas.get("zona", ()), de, para, tamanho,
                           caixa_de=caixa_da_zona, com_caixa=zona_com,
                           chave=lambda z: z.id, prefixo="z", aparar=True)
    tabuleiros, fora_t = _levar(pagina.tabuleiros, guardadas.get("tabuleiro", ()), de, para,
                                tamanho, caixa_de=tuple, com_caixa=lambda _t, c: tuple(c),
                                chave=tuple, prefixo=None, aparar=False)
    diagramas, fora_d = _levar(pagina.diagramas, guardadas.get("diagrama", ()), de, para,
                               tamanho, caixa_de=lambda d: tuple(d.caixa),
                               com_caixa=lambda d, c: replace(d, caixa=tuple(c)),
                               chave=lambda d: d.id, prefixo="d", aparar=False)
    areas_fora = tuple((tipo, lugar, objeto, aparada)
                       for tipo, lista in (("zona", fora_z), ("tabuleiro", fora_t),
                                           ("diagrama", fora_d))
                       for lugar, objeto, aparada in lista)
    return zonas, tabuleiros, diagramas, areas_fora


def _levar(itens, guardados, de, para, tamanho, *, caixa_de, com_caixa, chave, prefixo,
           aparar):
    """As áreas (ou tabuleiros, ou diagramas) `itens` da geometria `de` à `para`, com as
    `guardados` (`(lugar, objeto inteiro, aparada)`) de volta onde couberem. Devolve os que
    ficam na página e os que ficam guardados.

    A área aparada volta inteira só se ainda está como o corte a deixou (quem a mexeu ou a
    apagou decidiu por ela). A que tinha saído volta no lugar dela; se outra tomou o id dela
    nesse meio-tempo, ganha um id livre (`prefixo`), e o tabuleiro repetido não volta."""
    aparadas = {chave(obj): obj for _lugar, obj, aparada in guardados if aparada}
    inteira = [(item, _na_fonte_inteira(item, aparadas, de, tamanho, caixa_de, chave))
               for item in itens]
    _com_as_que_sairam(inteira, itens, guardados, caixa_de, chave, prefixo)
    return _na_geometria_nova(inteira, para, tamanho, com_caixa, chave, aparar)


def _na_fonte_inteira(item, aparadas, de, tamanho, caixa_de, chave):
    """A caixa do item na página inteira: a de antes do corte, se ele foi aparado e ainda
    está como o corte o deixou."""
    from abbychess import geometria as geo

    caixa = geo.para_a_fonte(caixa_de(item), de, tamanho)
    original = aparadas.get(chave(item)) if chave(item) else None
    if original is None:
        return caixa
    vista = geo.recortar(caixa_de(original), de, tamanho)
    if vista is not None and geo.para_a_fonte(vista, de, tamanho) == caixa:
        return caixa_de(original)
    return caixa


def _com_as_que_sairam(inteira: list, itens, guardados, caixa_de, chave, prefixo) -> None:
    """Põe em `inteira` as que tinham saído inteiras, no lugar delas; a de id tomado ganha um
    id livre (sem `prefixo`, não volta)."""
    usadas = _chaves_usadas(itens, guardados, chave)
    for lugar, obj, _aparada in sorted((g for g in guardados if not g[2]), key=lambda g: g[0]):
        if chave(obj) in {chave(item) for item, _caixa in inteira}:
            if prefixo is None:
                continue
            obj = replace(obj, id=_id_livre(prefixo, usadas))
            usadas.add(obj.id)
        inteira.insert(min(lugar, len(inteira)), (obj, caixa_de(obj)))


def _chaves_usadas(itens, guardados, chave) -> set:
    """As chaves (os ids) dos itens da página e dos guardados."""
    usadas = {chave(item) for item in itens}
    usadas.update(chave(obj) for _lugar, obj, _aparada in guardados)
    return usadas


def _id_livre(prefixo: str, usadas: set) -> str:
    n = 0
    while f"{prefixo}{n}" in usadas:
        n += 1
    return f"{prefixo}{n}"


def _na_geometria_nova(inteira: list, para, tamanho, com_caixa, chave, aparar: bool):
    """Os itens que ficam na página, levados à `para` (aparados, se `aparar`), e os que
    ficam guardados: os que não cabem e, inteiros, os aparados."""
    from abbychess import geometria as geo

    dentro, fora = [], []
    for lugar, (item, caixa) in enumerate(inteira):
        if aparar:
            vista = geo.recortar(caixa, para, tamanho)
        else:
            vista = geo.da_fonte(caixa, para, tamanho)
        if vista is None:
            fora.append((lugar, com_caixa(item, caixa), False))
            continue
        dentro.append(com_caixa(item, vista))
        if chave(item) and geo.para_a_fonte(vista, para, tamanho) != tuple(caixa):
            fora.append((lugar, com_caixa(item, caixa), True))
    return dentro, fora


def viva(pagina: Pagina) -> Pagina:
    """A página de um instantâneo (`Pagina.instantaneo`, com tuplas) como a que o cache e a
    interface editam (com listas)."""
    return replace(pagina, boxes=list(pagina.boxes), tabuleiros=list(pagina.tabuleiros),
                   diagramas=list(pagina.diagramas), zonas=list(pagina.zonas))


def dividir(pagina: Pagina, corte: int, esquerda, direita, tamanho: Tuple[int, int],
            pid_novo: int) -> Tuple[Pagina, Pagina, Dict[int, int]]:
    """Divide a página espelhada (§12.4) no `x = corte` da imagem que se vê (a da geometria
    dela): devolve a página da esquerda (o mesmo `pid`, na geometria `esquerda`), a da
    direita (`pid_novo`, na geometria `direita`) e os gids que mudaram de página (velho ->
    novo).

    Cada glifo vai para a metade do centro dele (aparado nela, se passa da divisão), e os da
    direita ganham gids do `pid_novo`, na ordem de leitura. As áreas são cortadas pela
    divisão (a lasca menor que `zonas.MENOR_LADO` some); o tabuleiro e o diagrama vão pela
    metade do centro. As decisões vão com os glifos delas (a junção de duas metades se
    desfaz), e o glifo virtual, com o glifo a que ele se prende. O que estava guardado fora do
    quadro (`fora`, `areas_fora`) fica na esquerda, e o que não cabe em metade nenhuma (uma
    caixa fora da página) vai para lá. A página não muda."""
    from abbychess import geometria as geo

    de = geo.normalizar(pagina.geometria)
    metades = (geo.normalizar(esquerda), geo.normalizar(direita))
    divisao = _Divisao(de, tamanho, corte)
    direita_pg = Pagina(pid=pid_novo, indice=pagina.indice + 1, estado=pagina.estado,
                        geometria=metades[1], tamanho=tamanho)
    boxes, fora, movidos, saidos = _dividir_glifos(pagina, divisao, direita_pg)
    esquerda_d, direita_d = _dividir_decisoes(pagina.decisoes,
                                              {b.gid for b in pagina.boxes} - saidos,
                                              movidos, direita_pg)
    areas_fora = list(pagina.areas_fora)
    tabuleiros = _dividir_tabuleiros(pagina.tabuleiros, divisao, areas_fora)
    diagramas = _dividir_diagramas(pagina.diagramas, divisao, areas_fora)
    zonas = _dividir_zonas(pagina.zonas, divisao, diagramas)
    esquerda_d = _virtuais_nas_zonas(esquerda_d, zonas[0])
    direita_d = _virtuais_nas_zonas(direita_d, zonas[1])
    esquerda_pg = Pagina(pid=pagina.pid, indice=pagina.indice, boxes=boxes[0],
                         tabuleiros=tabuleiros[0], diagramas=diagramas[0], zonas=zonas[0],
                         decisoes=esquerda_d, estado=pagina.estado,
                         proximo_n=pagina.proximo_n, geometria=metades[0], tamanho=tamanho,
                         fora=tuple(fora), areas_fora=tuple(areas_fora))
    direita_pg.boxes, direita_pg.decisoes = boxes[1], direita_d
    direita_pg.tabuleiros, direita_pg.diagramas = tabuleiros[1], diagramas[1]
    direita_pg.zonas = zonas[1]
    return esquerda_pg, direita_pg, movidos


class _Divisao:
    """O corte da imagem que se vê (a da geometria `de`) no `x = corte`, em duas metades."""

    def __init__(self, de, tamanho: Tuple[int, int], corte: int):
        from abbychess import geometria as geo

        self.de, self.tamanho, self.corte = de, tamanho, corte
        largura, self.altura = geo.tamanho_da_imagem(de, tamanho)
        self.colunas = ((0, corte), (corte, largura))

    def lado(self, caixa) -> int:
        return 0 if caixa[0] + caixa[2] < 2 * self.corte else 1

    def na_metade(self, caixa, k: int):
        """A caixa na metade `k`, nos pixels dela, ou None. As duas metades são recortes do
        que se vê, com o mesmo giro: a conta é aparar na coluna do corte e, na direita,
        deslocar (sem passar pela página inteira, que custava 3 s no livro dividido)."""
        x1, y1, x2, y2 = caixa
        de_x, ate_x = self.colunas[k]
        x1, x2, y1, y2 = max(x1, de_x), min(x2, ate_x), max(y1, 0), min(y2, self.altura)
        if x2 <= x1 or y2 <= y1:
            return None
        return (x1 - de_x, y1, x2 - de_x, y2)

    def na_fonte(self, caixa):
        from abbychess import geometria as geo

        return geo.para_a_fonte(tuple(caixa), self.de, self.tamanho)


def _dividir_glifos(pagina: Pagina, divisao: _Divisao, direita_pg: Pagina):
    """Os glifos de cada metade (os da direita com gids dela, na ordem de leitura), os
    guardados fora (os de antes e os que não cabem em metade nenhuma), os gids que mudaram de
    página e os que saíram."""
    boxes: Tuple[list, list] = ([], [])
    fora = list(pagina.fora)
    movidos: Dict[int, int] = {}
    saidos = set()
    for lugar, box in enumerate(pagina.boxes):
        k = divisao.lado(_caixa(box.entry))
        caixa = divisao.na_metade(_caixa(box.entry), k)
        if caixa is None:                      # fora da página: guardado na esquerda
            fora.append((lugar, _na_caixa(box, divisao.na_fonte(_caixa(box.entry)),
                                          box.entry.angulo + divisao.de[1])))
            saidos.add(box.gid)
            continue
        if k == 1:
            movidos[box.gid] = direita_pg.alocar()
            x1, y1, x2, y2 = caixa
            box = replace(box, gid=movidos[box.gid],
                          entry=replace(box.entry, x1=x1, y1=y1, x2=x2, y2=y2))
        elif caixa != _caixa(box.entry):     # a esquerda começa na origem: só a aparada
            box = _na_caixa(box, caixa, box.entry.angulo)
        boxes[k].append(box)
    return boxes, fora, movidos, saidos


def _dividir_tabuleiros(tabuleiros, divisao: _Divisao, areas_fora: list) -> Tuple[list, list]:
    """Os tabuleiros de cada metade, pelo centro; o que não cabe vai para `areas_fora`."""
    return _dividir_pelo_centro(tabuleiros, "tabuleiro", divisao, areas_fora,
                                caixa_de=lambda t: t, com_caixa=lambda _t, caixa: caixa)


def _dividir_diagramas(diagramas, divisao: _Divisao, areas_fora: list) -> Tuple[list, list]:
    """Os diagramas de cada metade, pelo centro; o que não cabe vai para `areas_fora`."""
    return _dividir_pelo_centro(diagramas, "diagrama", divisao, areas_fora,
                                caixa_de=lambda d: d.caixa,
                                com_caixa=lambda d, caixa: replace(d, caixa=caixa))


def _dividir_pelo_centro(itens, tipo: str, divisao: _Divisao, areas_fora: list, *, caixa_de,
                         com_caixa) -> Tuple[list, list]:
    """Cada item vai à metade do centro da caixa dele (`caixa_de`), com a caixa dela
    (`com_caixa`); o que não cabe vai para `areas_fora` com a caixa na fonte."""
    metades: Tuple[list, list] = ([], [])
    for lugar, item in enumerate(itens):
        k = divisao.lado(caixa_de(item))
        caixa = divisao.na_metade(caixa_de(item), k)
        if caixa is None:
            areas_fora.append((tipo, lugar, com_caixa(item, divisao.na_fonte(caixa_de(item))), False))
        else:
            metades[k].append(com_caixa(item, tuple(caixa)))
    return metades


def _dividir_zonas(zonas, divisao: _Divisao, diagramas: Tuple[list, list]) -> Tuple[list, list]:
    """As áreas cortadas pela divisão (a lasca menor que `zonas.MENOR_LADO` some); a legenda
    só cita o diagrama que ficou na metade dela."""
    from abbychess.zonas import MENOR_LADO

    metades: Tuple[list, list] = ([], [])
    for zona in zonas:
        for k in (0, 1):
            caixa = divisao.na_metade(zona.caixa, k)
            if caixa is None or min(caixa[2] - caixa[0], caixa[3] - caixa[1]) < MENOR_LADO:
                continue
            ids = {d.id for d in diagramas[k]}
            metades[k].append(replace(zona, x1=caixa[0], y1=caixa[1], x2=caixa[2], y2=caixa[3],
                                      diagrama_id=zona.diagrama_id
                                      if zona.diagrama_id in ids else None))
    return metades


def _virtuais_nas_zonas(d: Decisoes, zonas) -> Decisoes:
    """O virtual que cita uma área que não ficou nesta metade passa a não citar nenhuma."""
    ids = {z.id for z in zonas}
    virtuais = tuple(v if v.zona_id is None or v.zona_id in ids else replace(v, zona_id=None)
                     for v in d.virtuais)
    return d if virtuais == d.virtuais else replace(d, virtuais=virtuais)


def _dividir_decisoes(d: Decisoes, gids: Set[int], movidos: Dict[int, int],
                      direita: Pagina) -> Tuple[Decisoes, Decisoes]:
    """As decisões da esquerda e as da direita (com os gids novos). O virtual vai com o box a
    que a cadeia dele se prende (`depois_de`, senão `antes_de`); sem box, fica na esquerda.
    Os virtuais da direita ganham gids da página dela."""
    por_gid = {v.gid: v for v in d.virtuais}

    def ancora(v: GlifoVirtual) -> Optional[int]:
        vistos = set()
        alvo = v.depois_de if v.depois_de is not None else v.antes_de
        while alvo in por_gid and alvo not in vistos:
            vistos.add(alvo)
            de_la = por_gid[alvo]
            alvo = de_la.depois_de if de_la.depois_de is not None else de_la.antes_de
        return alvo if alvo in gids else None

    virtuais_d = [v for v in d.virtuais if ancora(v) in movidos]
    mapa = dict(movidos)
    for v in virtuais_d:
        mapa[v.gid] = direita.alocar()

    def metade(no_lado, f) -> Decisoes:
        def um(conjunto):
            return frozenset(f(g) for g in conjunto if no_lado(g))

        virtuais = [_virtual_na_metade(v, no_lado, f) for v in d.virtuais if no_lado(v.gid)]
        return Decisoes(quebras=um(d.quebras), paragrafo_antes=um(d.paragrafo_antes),
                        hifen_de_quebra=um(d.hifen_de_quebra),
                        juncoes=frozenset((f(a), f(b)) for a, b in d.juncoes
                                          if no_lado(a) and no_lado(b)),
                        virtuais=tuple(virtuais))

    def na_direita(g: int) -> bool:
        return g in mapa

    def na_esquerda(g: int) -> bool:
        return g not in mapa

    return metade(na_esquerda, lambda g: g), metade(na_direita, mapa.__getitem__)


def _virtual_na_metade(v: GlifoVirtual, no_lado, f) -> GlifoVirtual:
    """O virtual com os gids da metade (`f`); a âncora que ficou na outra vira None."""
    return replace(
        v, gid=f(v.gid),
        depois_de=f(v.depois_de) if v.depois_de is not None and no_lado(v.depois_de) else None,
        antes_de=f(v.antes_de) if v.antes_de is not None and no_lado(v.antes_de) else None)


def decisoes_dos_vivos(d: Decisoes, vivos: Set[int]) -> Decisoes:
    """As decisões sem as que citam um glifo que saiu (o virtual cuja âncora saiu também)."""
    if d.gids() <= vivos:
        return d
    ficam = _virtuais_ancorados(d.virtuais, vivos)
    return replace(d, quebras=d.quebras & vivos, paragrafo_antes=d.paragrafo_antes & vivos,
                   hifen_de_quebra=d.hifen_de_quebra & vivos,
                   juncoes=frozenset(j for j in d.juncoes if set(j) <= vivos), virtuais=ficam)


def _virtuais_ancorados(virtuais, vivos: Set[int]) -> Tuple[GlifoVirtual, ...]:
    """Os virtuais cujas âncoras estão vivas ou são virtuais que ficam, até nada mais cair
    (o que se prendia a um virtual que caiu cai também)."""
    ficam = tuple(virtuais)
    while True:
        gids = vivos | {v.gid for v in ficam}
        filtrados = tuple(v for v in ficam if _ancorado(v, gids))
        if len(filtrados) == len(ficam):
            return ficam
        ficam = filtrados


def _ancorado(v: GlifoVirtual, gids: Set[int]) -> bool:
    return ((v.depois_de is None or v.depois_de in gids)
            and (v.antes_de is None or v.antes_de in gids))


def _girada_no_centro(caixa, delta: float, tamanho: Tuple[int, int]):
    """A caixa da página endireitada inteira levada a outro ângulo de endireitar (`delta`
    graus a mais, anti-horário, em volta do centro da página, como `pagina.girar`): o centro
    dela gira, e o tamanho fica (a inclinação é pequena)."""
    import math

    x1, y1, x2, y2 = caixa
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    ox, oy = tamanho[0] / 2, tamanho[1] / 2
    cosseno, seno = math.cos(math.radians(delta)), math.sin(math.radians(delta))
    nx = cosseno * (cx - ox) + seno * (cy - oy) + ox
    ny = -seno * (cx - ox) + cosseno * (cy - oy) + oy
    dx, dy = round(nx - cx), round(ny - cy)
    return (x1 + dx, y1 + dy, x2 + dx, y2 + dy)


def endireitar(pagina: Pagina, delta: float, tamanho: Tuple[int, int], manter) -> Pagina:
    """A página depois de endireitá-la à mão `delta` graus a mais (§12.4): a leitura dela se
    desfaz. Ficam os glifos que `manter(box)` diz (os marcados à mão), com o centro girado em
    volta do centro da página, e as áreas do usuário, do mesmo jeito; os outros glifos, as
    áreas automáticas, os tabuleiros e os diagramas saem, com as decisões que os citavam. O
    estado vai a `glifos_marcados` (ou a `nao_reconhecida`, sem glifo). O glifo que o giro
    tira do quadro fica guardado (`fora`). Devolve uma página nova; a de entrada não muda."""
    from abbychess import geometria as geo

    de = geo.normalizar(pagina.geometria)
    # A ordem de leitura inteira, com os guardados no lugar deles (na página inteira, com o
    # ângulo da fonte), como em `reenquadrar`; só os marcados à mão seguem.
    marcados = [(b, f, a) for b, f, a in _na_pagina_inteira(pagina, de, tamanho) if manter(b)]
    boxes, fora = _glifos_girados(marcados, delta, de, tamanho)
    zonas = _zonas_do_usuario_giradas(pagina.zonas, delta, de, tamanho)
    areas_fora = _guardadas_do_usuario_giradas(pagina.areas_fora, delta, tamanho)
    vivos = {b.gid for b in boxes} | {b.gid for _lugar, b in fora}
    return Pagina(pid=pagina.pid, indice=pagina.indice, boxes=boxes, zonas=zonas,
                  decisoes=decisoes_dos_vivos(pagina.decisoes, vivos),
                  estado=GLIFOS_MARCADOS if boxes else NAO_RECONHECIDA,
                  proximo_n=pagina.proximo_n, geometria=de, tamanho=tamanho,
                  fora=tuple(fora), areas_fora=areas_fora)


def _glifos_girados(marcados: list, delta: float, de, tamanho: Tuple[int, int]):
    """Os glifos com o centro girado `delta` graus em volta do centro da página: os que
    ficam no quadro e os que o giro tira dele, com o lugar deles."""
    girados = [(box, _girada_no_centro(fonte, delta, tamanho), angulo)
               for box, fonte, angulo in marcados]
    return _glifos_na_geometria(girados, de, tamanho)


def _zonas_do_usuario_giradas(zonas, delta: float, de, tamanho: Tuple[int, int]) -> list:
    """As áreas do usuário giradas como os glifos e aparadas no quadro (sem diagrama: os
    diagramas saem); as automáticas saem."""
    from abbychess import geometria as geo

    giradas = []
    for zona in zonas:
        if zona.automatica:
            continue
        fonte = _girada_no_centro(geo.para_a_fonte(tuple(zona.caixa), de, tamanho), delta,
                                  tamanho)
        caixa = geo.recortar(fonte, de, tamanho)
        if caixa is not None:
            giradas.append(replace(zona, x1=caixa[0], y1=caixa[1], x2=caixa[2], y2=caixa[3],
                                   diagrama_id=None))
    return giradas


def _guardadas_do_usuario_giradas(areas_fora, delta: float, tamanho: Tuple[int, int]) -> tuple:
    """As áreas do usuário guardadas fora do quadro, giradas na página inteira; o resto do
    que estava guardado sai."""
    return tuple(
        (tipo, lugar, replace(objeto, **dict(zip(("x1", "y1", "x2", "y2"), _girada_no_centro(
            objeto.caixa, delta, tamanho)))), aparada)
        for tipo, lugar, objeto, aparada in areas_fora
        if tipo == "zona" and not objeto.automatica)
