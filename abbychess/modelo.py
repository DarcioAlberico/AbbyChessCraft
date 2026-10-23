"""O modelo da página, versão 2 (SPEC §4.1, §4.2, §4.4): identidade, decisões e estado.

Cada glifo da página é um `Box`, que **compõe** o `BoxEntry` do core (não o estende) com
o que o programa precisa guardar dele: o `gid`, a amostra de padrão que produziu a leitura
(procedência), o estilo e se o usuário já o revisou.

**Identidade.** A página tem um `pid` estável, que reordenar ou inserir páginas não muda,
e cada glifo um `gid = (pid << 20) | n`, com `n` tirado de `proximo_n` da página. Um gid
nunca é reaproveitado: o glifo dividido se aposenta e as partes nascem com gids novos, e
`Diferenca.sucessores` diz quem veio de quem.

**Decisões do usuário** (`Decisoes`) são chaveadas por gid: palavra nova antes de um glifo
(`quebras`), duas palavras juntas (`juncoes`), parágrafo antes (`paragrafo_antes`), glifos
virtuais (o caractere que falta, sem caixa) e hífen de quebra de linha. Quando uma edição
aposenta gids, `Decisoes.reescrever` as leva aos sucessores: "antes de g" vira "antes do
primeiro sucessor", e "depois de g", "depois do último". A decisão de um gid que saiu sem
sucessor (o box descartado) cai.

**Estado da página** (`proximo_estado`): a máquina de §4.4.

Sem Qt. As edições por gid estão em `abbychess.edicao`; o documento derivado (`montar`),
em `abbychess.texto`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

from core.box_model import BoxEntry

BITS_DO_N = 20
LIMITE_DO_N = 1 << BITS_DO_N


def gid_de(pid: int, n: int) -> int:
    if not 0 <= n < LIMITE_DO_N:
        raise ValueError(f"n={n} fora de 0..{LIMITE_DO_N - 1}")
    return (pid << BITS_DO_N) | n


def pid_de(gid: int) -> int:
    return gid >> BITS_DO_N


def n_de(gid: int) -> int:
    return gid & (LIMITE_DO_N - 1)


# ----------------------------------------------------------------------
# O glifo
# ----------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Estilo:
    negrito: bool = False
    italico: bool = False
    sublinhado: bool = False

    def para_json(self) -> list:
        return [int(self.negrito), int(self.italico), int(self.sublinhado)]

    @classmethod
    def de_json(cls, bruto) -> "Estilo":
        negrito, italico, sublinhado = (list(bruto or []) + [0, 0, 0])[:3]
        if not (negrito or italico or sublinhado):
            return SEM_ESTILO
        return cls(bool(negrito), bool(italico), bool(sublinhado))


#: O estilo de quase todo glifo, um objeto só: uma página tem milhares de glifos, e cada
#: objeto a mais pesa na coleta de lixo do Python (os picos do p95 da releitura no 1b).
SEM_ESTILO = Estilo()


@dataclass(frozen=True, eq=False, slots=True)
class Box:
    """Um glifo da página: o `BoxEntry` do core mais a identidade e a procedência dele."""

    gid: int
    entry: BoxEntry
    #: O arquivo do padrão do livro que deu a leitura (procedência, §8.3), relativo à pasta
    #: dos padrões; `None` quando a leitura não veio de um padrão do livro.
    amostra: Optional[str] = None
    estilo: Estilo = SEM_ESTILO
    #: O usuário viu e aceitou o glifo: sai da fila sem trocar a fonte da leitura.
    revisado: bool = False

    def para_json(self) -> list:
        return [self.gid, list(self.entry.as_state()), self.amostra, self.estilo.para_json(),
                int(self.revisado)]

    @classmethod
    def de_json(cls, bruto) -> "Box":
        gid, estado, amostra, estilo, revisado = bruto
        return cls(int(gid), BoxEntry.from_state(tuple(estado)), amostra,
                   Estilo.de_json(estilo), bool(revisado))


#: As figurinas que a leitura escreve (brancas e pretas): o modo das peças nos lances (§6.4).
FIGURINAS = frozenset("♔♕♖♗♘♙♚♛♜♝♞♟")


@dataclass(frozen=True, slots=True)
class GlifoVirtual:
    """O caractere que falta na página: não tem caixa, não ensina, não entra na leitura.

    Entra no documento logo depois do glifo `depois_de` (um box, ou outro virtual: as letras
    digitadas em sequência se encadeiam), ou logo antes do glifo `antes_de` (a letra que
    faltou no começo de uma palavra, D1), ou, sem os dois, no começo da primeira linha da
    página; na mesma palavra ou, com `palavra_nova`, numa palavra nova.
    """

    gid: int
    char: str
    depois_de: Optional[int]
    palavra_nova: bool = False
    zona_id: Optional[str] = None
    antes_de: Optional[int] = None

    def para_json(self) -> list:
        bruto = [self.gid, self.char, self.depois_de, int(self.palavra_nova), self.zona_id]
        return bruto + [self.antes_de] if self.antes_de is not None else bruto

    @classmethod
    def de_json(cls, bruto) -> "GlifoVirtual":
        gid, char, depois_de, palavra_nova, zona_id = bruto[:5]
        antes_de = bruto[5] if len(bruto) > 5 else None
        return cls(int(gid), str(char), None if depois_de is None else int(depois_de),
                   bool(palavra_nova), zona_id, None if antes_de is None else int(antes_de))


# ----------------------------------------------------------------------
# As decisões do usuário
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class Decisoes:
    quebras: FrozenSet[int] = frozenset()                  # palavra nova antes do gid
    juncoes: FrozenSet[Tuple[int, int]] = frozenset()      # (último da palavra, primeiro da seguinte)
    paragrafo_antes: FrozenSet[int] = frozenset()
    virtuais: Tuple[GlifoVirtual, ...] = ()
    hifen_de_quebra: FrozenSet[int] = frozenset()

    def gids(self) -> Set[int]:
        """Todo gid de box que alguma decisão referencia (os dos virtuais não são boxes)."""
        usados = set(self.quebras) | set(self.paragrafo_antes) | set(self.hifen_de_quebra)
        usados |= {g for par in self.juncoes for g in par}
        virtuais = {v.gid for v in self.virtuais}
        usados |= {v.depois_de for v in self.virtuais
                   if v.depois_de is not None and v.depois_de not in virtuais}
        usados |= {v.antes_de for v in self.virtuais
                   if v.antes_de is not None and v.antes_de not in virtuais}
        return usados

    def reescrever(self, sucessores: Dict[int, List[int]]) -> Tuple["Decisoes", List[str]]:
        """As decisões com os gids aposentados trocados pelos sucessores. Devolve também o
        que caiu (gid aposentado sem sucessor), em frases, para a interface avisar."""
        caidas: List[str] = []

        def primeiro(g: int) -> Optional[int]:
            if g not in sucessores:
                return g
            novos = sucessores[g]
            return novos[0] if novos else None

        def ultimo(g: int) -> Optional[int]:
            if g not in sucessores:
                return g
            novos = sucessores[g]
            return novos[-1] if novos else None

        def mapear(conjunto, onde, rotulo):
            saida = set()
            for g in conjunto:
                novo = onde(g)
                if novo is None:
                    caidas.append(f"{rotulo} do glifo {g} (o glifo saiu)")
                else:
                    saida.add(novo)
            return frozenset(saida)

        juncoes = set()
        for a, b in self.juncoes:
            na, nb = ultimo(a), primeiro(b)
            if na is None or nb is None:
                caidas.append(f"junção de palavras {a}+{b} (um dos glifos saiu)")
            elif na != nb:
                juncoes.add((na, nb))
        virtuais = []
        for v in self.virtuais:
            if v.antes_de is not None and v.antes_de in sucessores:
                novo = primeiro(v.antes_de)
                if novo is None:
                    caidas.append(f"glifo virtual '{v.char}' antes do glifo {v.antes_de} "
                                  "(o glifo saiu; o virtual foi para o começo da página)")
                v = replace(v, antes_de=novo)
            if v.depois_de is None or v.depois_de not in sucessores:
                virtuais.append(v)
                continue
            novo = ultimo(v.depois_de)
            if novo is None:
                caidas.append(f"glifo virtual '{v.char}' depois do glifo {v.depois_de} "
                              "(o glifo saiu; o virtual foi para o começo da página)")
            virtuais.append(replace(v, depois_de=novo))
        quebras = mapear(self.quebras, primeiro, "palavra nova antes")
        # Dois glifos fundidos podem levar uma quebra e uma junção à mesma fronteira (a
        # junção que terminava num e a quebra antes do outro). As duas não valem juntas:
        # fica a junção, que é sobre o glifo que já começava a fronteira, e a quebra cai.
        conflito = quebras & {b for _, b in juncoes}
        for g in sorted(conflito):
            caidas.append(f"palavra nova antes do glifo {g} (o glifo foi fundido no fim de "
                          "uma palavra juntada)")
        return Decisoes(
            quebras=quebras - conflito,
            juncoes=frozenset(juncoes),
            paragrafo_antes=mapear(self.paragrafo_antes, primeiro, "parágrafo antes"),
            virtuais=tuple(virtuais),
            hifen_de_quebra=mapear(self.hifen_de_quebra, ultimo, "hífen de quebra"),
        ), caidas

    def para_json(self) -> dict:
        return {"quebras": sorted(self.quebras), "juncoes": sorted([a, b] for a, b in self.juncoes),
                "paragrafo_antes": sorted(self.paragrafo_antes),
                "virtuais": [v.para_json() for v in self.virtuais],
                "hifen_de_quebra": sorted(self.hifen_de_quebra)}

    @classmethod
    def de_json(cls, bruto: Optional[dict]) -> "Decisoes":
        bruto = bruto or {}
        return cls(quebras=frozenset(map(int, bruto.get("quebras", []))),
                   juncoes=frozenset((int(a), int(b)) for a, b in bruto.get("juncoes", [])),
                   paragrafo_antes=frozenset(map(int, bruto.get("paragrafo_antes", []))),
                   virtuais=tuple(GlifoVirtual.de_json(v) for v in bruto.get("virtuais", [])),
                   hifen_de_quebra=frozenset(map(int, bruto.get("hifen_de_quebra", []))))


# ----------------------------------------------------------------------
# A mudança de uma edição
# ----------------------------------------------------------------------

@dataclass
class Diferenca:
    """O que uma edição fez na página, em gids (§4.1)."""

    removidos: Set[int] = field(default_factory=set)
    novos: List[Box] = field(default_factory=list)
    mudados: Set[int] = field(default_factory=set)
    #: gid aposentado -> os gids que nasceram dele, em ordem de leitura ([] = saiu sem sucessor).
    sucessores: Dict[int, List[int]] = field(default_factory=dict)
    #: As decisões que não puderam ir para os sucessores (preenchido por `aplicar`).
    caidas: List[str] = field(default_factory=list)

    @property
    def vazia(self) -> bool:
        return not (self.removidos or self.novos or self.mudados)


# ----------------------------------------------------------------------
# O estado da página (§4.4)
# ----------------------------------------------------------------------

NAO_RECONHECIDA = "nao_reconhecida"
GLIFOS_MARCADOS = "glifos_marcados"
RECONHECIDA = "reconhecida"
EM_REVISAO = "em_revisao"
VERIFICADA = "verificada"
ESTADOS = (NAO_RECONHECIDA, GLIFOS_MARCADOS, RECONHECIDA, EM_REVISAO, VERIFICADA)
#: Os estados de página que já passaram pelo F5 ou pelo lote (contam como lidas).
LIDAS = (RECONHECIDA, EM_REVISAO, VERIFICADA)

EVENTOS = ("marcar", "reconhecer", "editar", "verificar", "esquecer_padrao")

_TRANSICOES = {
    (NAO_RECONHECIDA, "marcar"): GLIFOS_MARCADOS,
    (NAO_RECONHECIDA, "reconhecer"): RECONHECIDA,
    (GLIFOS_MARCADOS, "marcar"): GLIFOS_MARCADOS,
    (GLIFOS_MARCADOS, "editar"): GLIFOS_MARCADOS,
    (GLIFOS_MARCADOS, "reconhecer"): RECONHECIDA,
    (RECONHECIDA, "reconhecer"): RECONHECIDA,
    (RECONHECIDA, "editar"): EM_REVISAO,
    (RECONHECIDA, "marcar"): EM_REVISAO,
    (RECONHECIDA, "verificar"): VERIFICADA,
    (EM_REVISAO, "editar"): EM_REVISAO,
    (EM_REVISAO, "marcar"): EM_REVISAO,
    (EM_REVISAO, "reconhecer"): EM_REVISAO,
    (EM_REVISAO, "verificar"): VERIFICADA,
    (VERIFICADA, "editar"): EM_REVISAO,
    (VERIFICADA, "marcar"): EM_REVISAO,
    (VERIFICADA, "reconhecer"): EM_REVISAO,
    (VERIFICADA, "esquecer_padrao"): EM_REVISAO,
    (VERIFICADA, "verificar"): VERIFICADA,
}


def proximo_estado(estado: str, evento: str) -> str:
    """O estado da página depois do evento; um evento que não se aplica não muda nada
    (editar uma página não reconhecida, esquecer padrão numa em revisão)."""
    if estado not in ESTADOS:
        raise ValueError(f"estado desconhecido {estado!r}")
    if evento not in EVENTOS:
        raise ValueError(f"evento desconhecido {evento!r}")
    return _TRANSICOES.get((estado, evento), estado)


# ----------------------------------------------------------------------
# A página
# ----------------------------------------------------------------------

@dataclass
class Pagina:
    """Uma página do livro no modelo v2: o que vai para `paginas/p<pid>.json`."""

    pid: int
    indice: int
    boxes: List[Box] = field(default_factory=list)
    tabuleiros: List[Tuple[int, int, int, int]] = field(default_factory=list)
    diagramas: list = field(default_factory=list)          # DiagramaLido
    zonas: list = field(default_factory=list)              # Zona
    decisoes: Decisoes = field(default_factory=Decisoes)
    estado: str = NAO_RECONHECIDA
    proximo_n: int = 0
    #: (quadro, giro) da imagem em que os boxes estão (§12.4): a da entrada quando a página
    #: foi lida ou gravada. Ao carregar, se a entrada tem outra, `reenquadrar` leva os boxes.
    geometria: tuple = (None, 0)
    #: (largura, altura) da página da fonte, para a conta (quando a geometria não é a inteira).
    tamanho: Optional[Tuple[int, int]] = None
    #: Os glifos que o quadro deixou de fora, guardados (o Ctrl+Z ou um quadro maior os
    #: devolvem, com o mesmo gid): (lugar na ordem de leitura, Box na página endireitada
    #: inteira).
    fora: tuple = ()
    #: As áreas, os tabuleiros e os diagramas que o quadro cortou ou deixou de fora:
    #: (tipo, lugar na lista, o objeto na página endireitada inteira, aparada). `tipo` é
    #: "zona", "tabuleiro" ou "diagrama"; `aparada` diz que a área está na página, cortada,
    #: e o objeto guardado é ela inteira (ela volta inteira se ninguém a mexer).
    areas_fora: tuple = ()

    def alocar(self) -> int:
        """Um gid novo desta página (nunca um já usado)."""
        gid = gid_de(self.pid, self.proximo_n)
        self.proximo_n += 1
        return gid

    @property
    def vivos(self) -> Set[int]:
        return {b.gid for b in self.boxes}

    @property
    def aposentados(self) -> Set[int]:
        """Os gids já alocados que não estão mais na página (nem são virtuais)."""
        virtuais = {v.gid for v in self.decisoes.virtuais}
        return {gid_de(self.pid, n) for n in range(self.proximo_n)} - self.vivos - virtuais

    def box(self, gid: int) -> Box:
        return next(b for b in self.boxes if b.gid == gid)

    def indice_de(self, gid: int) -> int:
        return next(i for i, b in enumerate(self.boxes) if b.gid == gid)

    def entries(self) -> List[BoxEntry]:
        return [b.entry for b in self.boxes]

    def instantaneo(self) -> "Pagina":
        """A página agora, para o gravador e o desfazer: uma cópia rasa, que vale porque
        nada da página é mudado no lugar (desde o 2a, uma edição troca as listas e os
        objetos). Custa uma tupla por lista, não uma cópia de cada glifo."""
        return Pagina(pid=self.pid, indice=self.indice, boxes=tuple(self.boxes),
                      tabuleiros=tuple(self.tabuleiros), diagramas=tuple(self.diagramas),
                      zonas=tuple(self.zonas), decisoes=self.decisoes, estado=self.estado,
                      proximo_n=self.proximo_n, geometria=self.geometria,
                      tamanho=self.tamanho, fora=tuple(self.fora),
                      areas_fora=tuple(self.areas_fora))

    def aplicar(self, diferenca: Diferenca, nova_ordem: Sequence[Box]) -> Diferenca:
        """Põe na página a lista de boxes depois da edição e leva as decisões aos sucessores.

        `nova_ordem` é a página inteira em ordem de leitura; a `diferenca` diz o que mudou.
        Só a thread da interface aplica (§4.1): aqui não há trava.
        """
        self.boxes = list(nova_ordem)
        if diferenca.sucessores:
            self.decisoes, caidas = self.decisoes.reescrever(diferenca.sucessores)
            diferenca.caidas.extend(caidas)
        return diferenca


#: Na releitura da página (o F5 e o lote, §4.6), o glifo que mudou um pouco de caixa
#: continua o mesmo (o gid e as decisões dele) se a interseção sobre a união das caixas,
#: a de antes e a de agora, for ao menos esta.
IOU_DA_RELEITURA = 0.6


def reconciliar(antes: Sequence[Box], depois: Sequence[BoxEntry], alocar,
                amostra_de=lambda entry: None,
                estados: Optional[Dict[int, int]] = None, *,
                estilo_de=lambda entry: None,
                iou_minimo: Optional[float] = None) -> Tuple[List[Box], Diferenca]:
    """Os `Box` da lista `depois` (os `BoxEntry` que a janela de hoje edita por índice),
    com os gids de `antes` onde dá e gids novos onde não dá, e a `Diferenca` entre as duas.

    É o que passa os gids (e as decisões) de uma página para a mesma página relida
    inteira (o F5 e o lote), e o que reconcilia as listas de `BoxEntry` de quem grava por
    `ProjetoDeLivro.salvar_pagina` (o lote, as ferramentas). A janela não reconcilia mais:
    desde o 2a ela edita o modelo (`abbychess.edicao`).

    1. O mesmo objeto `BoxEntry` é o mesmo glifo (mudado, se o estado mudou).
    2. Senão, a mesma caixa é o mesmo glifo (o desfazer de hoje devolve cópias).
    2½. Com `iou_minimo` (a releitura da página inteira, §4.6), o que sobra casa um a um
       com o que saiu, pela maior interseção sobre a união das caixas, se ela for ao menos
       `iou_minimo`: a segmentação de novo mexe um pixel aqui e ali, e o glifo é o mesmo.
    3. O que sobra de `depois` nasce com gid novo, e é sucessor de cada glifo de `antes`
       que saiu e com o qual ele se sobrepõe em mais da metade da área de um dos dois
       (dividir, juntar, marcar um quadro). Um glifo que saiu sem ninguém por cima saiu
       sem sucessor (descartar).

    `amostra_de(entry)` dá a procedência registrada da leitura (`abbychess.procedencia`);
    sem ela, um glifo que não mudou de leitura guarda a amostra que tinha. `estados` é a
    foto da última gravação, `foto(entry)` de cada gid: a janela muda o `BoxEntry` no
    lugar, e só a foto de antes diz se ele mudou (sem ela, vale o estado atual de `antes`).
    """
    por_objeto = {id(b.entry): b for b in antes}
    usados: Set[int] = set()
    saida: List[Optional[Box]] = [None] * len(depois)
    dif = Diferenca()
    estados = estados or {}
    agora = [foto(e) for e in depois]                       # uma vez por glifo

    def manter(i: int, velho: Box, entry: BoxEntry, estado_antes) -> None:
        usados.add(velho.gid)
        mudou = agora[i] != estado_antes
        registrada = amostra_de(entry)
        if registrada is None:              # ninguém leu este objeto desde a gravação
            amostra = None if mudou else velho.amostra
        else:
            amostra = registrada or None    # "" = lido, mas não por um padrão do livro
        estilo = estilo_de(entry)
        estilo = velho.estilo if estilo is None else estilo
        if entry is velho.entry and amostra == velho.amostra and estilo == velho.estilo:
            saida[i] = velho                # o caso comum: nada a copiar
        else:
            saida[i] = replace(velho, entry=entry, amostra=amostra, estilo=estilo)
        if mudou or estilo != velho.estilo:
            dif.mudados.add(velho.gid)

    for i, entry in enumerate(depois):                       # 1. o mesmo objeto
        velho = por_objeto.get(id(entry))
        if velho is not None and velho.entry is entry and velho.gid not in usados:
            manter(i, velho, entry, estados.get(velho.gid, agora[i]))
    if any(s is None for s in saida):                        # 2. a mesma caixa
        por_caixa: Dict[tuple, List[Box]] = {}
        for b in antes:
            if b.gid not in usados:
                por_caixa.setdefault(_caixa(b.entry), []).append(b)
        for i, entry in enumerate(depois):
            if saida[i] is not None:
                continue
            velho = next((b for b in por_caixa.get(_caixa(entry), []) if b.gid not in usados),
                         None)
            if velho is not None:
                manter(i, velho, entry, estados.get(velho.gid, foto(velho.entry)))
    if iou_minimo is not None and any(s is None for s in saida):   # 2½. pela sobreposição
        celulas: Dict[tuple, List[Box]] = {}       # só os vizinhos, não a página inteira
        for b in antes:
            if b.gid not in usados:
                for celula in _celulas(b.entry):
                    celulas.setdefault(celula, []).append(b)
        pares = []
        for i, entry in enumerate(depois):
            if saida[i] is None:
                vistos = {}
                for celula in _celulas(entry):
                    for velho in celulas.get(celula, ()):
                        vistos[velho.gid] = velho
                pares.extend((iou, i, velho) for velho in vistos.values()
                             if (iou := _iou(velho.entry, entry)) >= iou_minimo)
        pares.sort(key=lambda par: -par[0])
        for _iou_do_par, i, velho in pares:
            if saida[i] is None and velho.gid not in usados:
                manter(i, velho, depois[i], estados.get(velho.gid, foto(velho.entry)))
    saidos = [b for b in antes if b.gid not in usados]
    for i, entry in enumerate(depois):                       # 3. nascidos
        if saida[i] is not None:
            continue
        novo = Box(alocar(), entry, amostra_de(entry) or None,
                   estilo_de(entry) or SEM_ESTILO)
        saida[i] = novo
        dif.novos.append(novo)
    for velho in saidos:
        dif.removidos.add(velho.gid)
        dif.sucessores[velho.gid] = [n.gid for n in dif.novos if _sobrepoe(velho.entry, n.entry)]
    return list(saida), dif


def foto(entry: BoxEntry) -> int:
    """O estado do glifo num inteiro (o hash do `as_state()`), para comparar depois.

    Um inteiro, e não a tupla: a foto de cada página fica guardada entre uma gravação e a
    seguinte, e milhares de tuplas de vida longa disparavam a coleta de lixo completa do
    Python a cada poucas edições (os picos do p95 da releitura medidos no 1b). Um dict de
    inteiros não é rastreado pelo coletor.
    """
    return hash(tuple(entry.as_state()))


def _caixa(e: BoxEntry) -> tuple:
    return (e.x1, e.y1, e.x2, e.y2)


def descrever_caidas(caidas: Sequence[str], boxes: Sequence[Box]) -> List[str]:
    """As decisões que caíram, com o glifo dito como o usuário o vê (o caractere e a posição
    na página), e não pelo gid, que ele não vê em lugar nenhum."""
    import re

    por_gid = {b.gid: b.entry for b in boxes}

    def glifo(casou) -> str:
        e = por_gid.get(int(casou.group(0)))
        if e is None:
            return casou.group(0)
        return f"'{e.char or '?'}' em ({e.x1}, {e.y1})"

    # Só o número depois de "glifo " ou de "palavras " e o depois do "+" da junção: o
    # caractere de um glifo virtual também pode ser um dígito.
    return [re.sub(r"(?:(?<=glifo )|(?<=palavras )|(?<=\+))\d+", glifo, texto)
            for texto in caidas]


def _celulas(e: BoxEntry, lado: int = 64):
    for cx in range(e.x1 // lado, e.x2 // lado + 1):
        for cy in range(e.y1 // lado, e.y2 // lado + 1):
            yield cx, cy


def _iou(a: BoxEntry, b: BoxEntry) -> float:
    largura = min(a.x2, b.x2) - max(a.x1, b.x1)
    altura = min(a.y2, b.y2) - max(a.y1, b.y1)
    if largura <= 0 or altura <= 0:
        return 0.0
    inter = largura * altura
    uniao = (a.x2 - a.x1) * (a.y2 - a.y1) + (b.x2 - b.x1) * (b.y2 - b.y1) - inter
    return inter / max(uniao, 1)


def _sobrepoe(a: BoxEntry, b: BoxEntry) -> bool:
    largura = min(a.x2, b.x2) - max(a.x1, b.x1)
    altura = min(a.y2, b.y2) - max(a.y1, b.y1)
    if largura <= 0 or altura <= 0:
        return False
    inter = largura * altura
    area_a = max((a.x2 - a.x1) * (a.y2 - a.y1), 1)
    area_b = max((b.x2 - b.x1) * (b.y2 - b.y1), 1)
    return inter > 0.5 * min(area_a, area_b)


# ----------------------------------------------------------------------
# A geometria da página (§12.4, passo L)
# ----------------------------------------------------------------------

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
    # Na página inteira, o glifo tem o ângulo da fonte: girar a página de g graus no sentido
    # horário tira g do ângulo anti-horário do texto.
    inteira = [(b, geo.para_a_fonte(_caixa(b.entry), de, tamanho), b.entry.angulo + de[1])
               for b in pagina.boxes]
    for lugar, box in sorted(pagina.fora, key=lambda t: t[0]):
        inteira.insert(min(lugar, len(inteira)), (box, _caixa(box.entry), box.entry.angulo))
    dentro, fora = [], []
    for lugar, (box, caixa, angulo) in enumerate(inteira):
        nova = geo.da_fonte(caixa, para, tamanho)
        if nova is None:
            fora.append((lugar, _na_caixa(box, caixa, angulo)))
        else:
            dentro.append(_na_caixa(box, nova, angulo - para[1]))
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
    pagina.boxes, pagina.fora = dentro, tuple(fora)
    pagina.zonas, pagina.tabuleiros, pagina.diagramas = zonas, tabuleiros, diagramas
    pagina.areas_fora = areas_fora
    pagina.geometria, pagina.tamanho = para, tamanho
    return True


def _levar(itens, guardados, de, para, tamanho, *, caixa_de, com_caixa, chave, prefixo,
           aparar):
    """As áreas (ou tabuleiros, ou diagramas) `itens` da geometria `de` à `para`, com as
    `guardados` (`(lugar, objeto inteiro, aparada)`) de volta onde couberem. Devolve os que
    ficam na página e os que ficam guardados.

    A área aparada volta inteira só se ainda está como o corte a deixou (quem a mexeu ou a
    apagou decidiu por ela). A que tinha saído volta no lugar dela; se outra tomou o id dela
    nesse meio-tempo, ganha um id livre (`prefixo`), e o tabuleiro repetido não volta."""
    from abbychess import geometria as geo

    aparadas = {chave(obj): obj for _lugar, obj, aparada in guardados if aparada}
    inteira = []
    for item in itens:
        caixa = geo.para_a_fonte(caixa_de(item), de, tamanho)
        original = aparadas.get(chave(item)) if chave(item) else None
        if original is not None:
            vista = geo.recortar(caixa_de(original), de, tamanho)
            if vista is not None and geo.para_a_fonte(vista, de, tamanho) == caixa:
                caixa = caixa_de(original)
        inteira.append((item, caixa))
    usadas = {chave(item) for item in itens}
    usadas.update(chave(obj) for _lugar, obj, _aparada in guardados)
    for lugar, obj, _aparada in sorted((g for g in guardados if not g[2]), key=lambda g: g[0]):
        if chave(obj) in {chave(item) for item, _caixa in inteira}:
            if prefixo is None:
                continue
            n = 0
            while f"{prefixo}{n}" in usadas:
                n += 1
            obj = replace(obj, id=f"{prefixo}{n}")
            usadas.add(obj.id)
        inteira.insert(min(lugar, len(inteira)), (obj, caixa_de(obj)))
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
    from abbychess.zonas import MENOR_LADO

    de = geo.normalizar(pagina.geometria)
    metades = (geo.normalizar(esquerda), geo.normalizar(direita))
    largura, altura = geo.tamanho_da_imagem(de, tamanho)
    colunas = ((0, corte), (corte, largura))

    def lado(caixa) -> int:
        return 0 if caixa[0] + caixa[2] < 2 * corte else 1

    def na_metade(caixa, k: int):
        """A caixa na metade `k`, nos pixels dela, ou None. As duas metades são recortes do
        que se vê, com o mesmo giro: a conta é aparar na coluna do corte e, na direita,
        deslocar (sem passar pela página inteira, que custava 3 s no livro dividido)."""
        x1, y1, x2, y2 = caixa
        de_x, ate_x = colunas[k]
        x1, x2, y1, y2 = max(x1, de_x), min(x2, ate_x), max(y1, 0), min(y2, altura)
        if x2 <= x1 or y2 <= y1:
            return None
        return (x1 - de_x, y1, x2 - de_x, y2)

    def na_fonte(caixa):
        return geo.para_a_fonte(tuple(caixa), de, tamanho)

    direita_pg = Pagina(pid=pid_novo, indice=pagina.indice + 1, estado=pagina.estado,
                        geometria=metades[1], tamanho=tamanho)
    boxes: Tuple[list, list] = ([], [])
    fora, areas_fora = list(pagina.fora), list(pagina.areas_fora)
    movidos: Dict[int, int] = {}
    saidos = set()
    for lugar, box in enumerate(pagina.boxes):
        k = lado(_caixa(box.entry))
        caixa = na_metade(_caixa(box.entry), k)
        if caixa is None:                      # fora da página: guardado na esquerda
            fora.append((lugar, _na_caixa(box, na_fonte(_caixa(box.entry)),
                                          box.entry.angulo + de[1])))
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
    esquerda_d, direita_d = _dividir_decisoes(pagina.decisoes,
                                              {b.gid for b in pagina.boxes} - saidos,
                                              movidos, direita_pg)
    tabuleiros: Tuple[list, list] = ([], [])
    for lugar, tabuleiro in enumerate(pagina.tabuleiros):
        k = lado(tabuleiro)
        caixa = na_metade(tabuleiro, k)
        if caixa is None:
            areas_fora.append(("tabuleiro", lugar, na_fonte(tabuleiro), False))
        else:
            tabuleiros[k].append(tuple(caixa))
    diagramas: Tuple[list, list] = ([], [])
    for lugar, diagrama in enumerate(pagina.diagramas):
        k = lado(diagrama.caixa)
        caixa = na_metade(diagrama.caixa, k)
        if caixa is None:
            areas_fora.append(("diagrama", lugar,
                               replace(diagrama, caixa=na_fonte(diagrama.caixa)), False))
        else:
            diagramas[k].append(replace(diagrama, caixa=tuple(caixa)))
    zonas: Tuple[list, list] = ([], [])
    for zona in pagina.zonas:
        for k in (0, 1):
            caixa = na_metade(zona.caixa, k)
            if caixa is None or min(caixa[2] - caixa[0], caixa[3] - caixa[1]) < MENOR_LADO:
                continue
            ids = {d.id for d in diagramas[k]}
            zonas[k].append(replace(zona, x1=caixa[0], y1=caixa[1], x2=caixa[2], y2=caixa[3],
                                    diagrama_id=zona.diagrama_id
                                    if zona.diagrama_id in ids else None))
    esquerda_d, direita_d = (_virtuais_nas_zonas(d, z) for d, z in ((esquerda_d, zonas[0]),
                                                                   (direita_d, zonas[1])))
    esquerda_pg = Pagina(pid=pagina.pid, indice=pagina.indice, boxes=boxes[0],
                         tabuleiros=tabuleiros[0], diagramas=diagramas[0], zonas=zonas[0],
                         decisoes=esquerda_d, estado=pagina.estado,
                         proximo_n=pagina.proximo_n, geometria=metades[0], tamanho=tamanho,
                         fora=tuple(fora), areas_fora=tuple(areas_fora))
    direita_pg.boxes, direita_pg.decisoes = boxes[1], direita_d
    direita_pg.tabuleiros, direita_pg.diagramas = tabuleiros[1], diagramas[1]
    direita_pg.zonas = zonas[1]
    return esquerda_pg, direita_pg, movidos


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

        virtuais = []
        for v in d.virtuais:
            if not no_lado(v.gid):
                continue
            virtuais.append(replace(
                v, gid=f(v.gid),
                depois_de=f(v.depois_de) if v.depois_de is not None and no_lado(v.depois_de)
                else None,
                antes_de=f(v.antes_de) if v.antes_de is not None and no_lado(v.antes_de)
                else None))
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


def decisoes_dos_vivos(d: Decisoes, vivos: Set[int]) -> Decisoes:
    """As decisões sem as que citam um glifo que saiu (o virtual cuja âncora saiu também)."""
    if d.gids() <= vivos:
        return d
    ficam = tuple(d.virtuais)
    while True:
        gids = vivos | {v.gid for v in ficam}
        filtrados = tuple(v for v in ficam if (v.depois_de is None or v.depois_de in gids)
                          and (v.antes_de is None or v.antes_de in gids))
        if len(filtrados) == len(ficam):
            break
        ficam = filtrados
    return replace(d, quebras=d.quebras & vivos, paragrafo_antes=d.paragrafo_antes & vivos,
                   hifen_de_quebra=d.hifen_de_quebra & vivos,
                   juncoes=frozenset(j for j in d.juncoes if set(j) <= vivos), virtuais=ficam)


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

    def girada(caixa_da_vista):
        return _girada_no_centro(geo.para_a_fonte(tuple(caixa_da_vista), de, tamanho), delta,
                                 tamanho)

    # A ordem de leitura inteira, com os guardados no lugar deles (na página inteira, com o
    # ângulo da fonte), como em `reenquadrar`; só os marcados à mão seguem.
    inteira = [(b, geo.para_a_fonte(_caixa(b.entry), de, tamanho), b.entry.angulo + de[1])
               for b in pagina.boxes]
    for lugar, box in sorted(pagina.fora, key=lambda t: t[0]):
        inteira.insert(min(lugar, len(inteira)), (box, _caixa(box.entry), box.entry.angulo))
    boxes, fora = [], []
    for lugar, (box, fonte, angulo) in enumerate((b, f, a) for b, f, a in inteira
                                                 if manter(b)):
        fonte = _girada_no_centro(fonte, delta, tamanho)
        caixa = geo.da_fonte(fonte, de, tamanho)
        if caixa is None:
            fora.append((lugar, _na_caixa(box, fonte, angulo)))
        else:
            boxes.append(_na_caixa(box, caixa, angulo - de[1]))
    zonas = []
    for zona in pagina.zonas:
        if zona.automatica:
            continue
        caixa = geo.recortar(girada(zona.caixa), de, tamanho)
        if caixa is not None:
            zonas.append(replace(zona, x1=caixa[0], y1=caixa[1], x2=caixa[2], y2=caixa[3],
                                 diagrama_id=None))
    areas_fora = tuple(
        (tipo, lugar, replace(objeto, **dict(zip(("x1", "y1", "x2", "y2"), _girada_no_centro(
            objeto.caixa, delta, tamanho)))), aparada)
        for tipo, lugar, objeto, aparada in pagina.areas_fora
        if tipo == "zona" and not objeto.automatica)
    vivos = {b.gid for b in boxes} | {b.gid for _lugar, b in fora}
    return Pagina(pid=pagina.pid, indice=pagina.indice, boxes=boxes, zonas=zonas,
                  decisoes=decisoes_dos_vivos(pagina.decisoes, vivos),
                  estado=GLIFOS_MARCADOS if boxes else NAO_RECONHECIDA,
                  proximo_n=pagina.proximo_n, geometria=de, tamanho=tamanho,
                  fora=tuple(fora), areas_fora=areas_fora)
