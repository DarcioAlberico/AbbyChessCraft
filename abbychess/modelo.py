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


@dataclass(frozen=True, slots=True)
class GlifoVirtual:
    """O caractere que falta na página: não tem caixa, não ensina, não entra na leitura.

    Entra no documento depois do glifo `depois_de` (ou no começo da linha, com `None`),
    na mesma palavra ou, com `palavra_nova`, numa palavra nova.
    """

    gid: int
    char: str
    depois_de: Optional[int]
    palavra_nova: bool = False
    zona_id: Optional[str] = None

    def para_json(self) -> list:
        return [self.gid, self.char, self.depois_de, int(self.palavra_nova), self.zona_id]

    @classmethod
    def de_json(cls, bruto) -> "GlifoVirtual":
        gid, char, depois_de, palavra_nova, zona_id = bruto
        return cls(int(gid), str(char), None if depois_de is None else int(depois_de),
                   bool(palavra_nova), zona_id)


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
        usados |= {v.depois_de for v in self.virtuais if v.depois_de is not None}
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
            if v.depois_de is None or v.depois_de not in sucessores:
                virtuais.append(v)
                continue
            novo = ultimo(v.depois_de)
            if novo is None:
                caidas.append(f"glifo virtual '{v.char}' depois do glifo {v.depois_de} "
                              "(o glifo saiu; o virtual foi para o começo da linha)")
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
                      proximo_n=self.proximo_n)

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
        if entry is velho.entry and amostra == velho.amostra:
            saida[i] = velho                # o caso comum: nada a copiar
        else:
            saida[i] = replace(velho, entry=entry, amostra=amostra)
        if mudou:
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
        novo = Box(alocar(), entry, amostra_de(entry) or None)
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

    return [re.sub(r"\d+", glifo, texto) for texto in caidas]


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
