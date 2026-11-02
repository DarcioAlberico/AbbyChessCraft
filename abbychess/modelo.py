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
from enum import StrEnum
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
    """O negrito e o itálico (`None`: não medido, o efeito desconhecido que o k-NN compara com
    todas as amostras; `False`: medido e reto) e o sublinhado, que é só do usuário (§9.3)."""

    negrito: Optional[bool] = None
    italico: Optional[bool] = None
    sublinhado: bool = False

    def para_json(self) -> list:
        """[negrito, itálico, sublinhado], e um quarto item com o que foi medido como reto
        (1: o negrito, 2: o itálico) quando há: o JSON de antes do fechamento do passo I não
        o tem, e lá o 0 é "não medido"."""
        retos = (self.negrito is False) | (self.italico is False) << 1
        base = [int(bool(self.negrito)), int(bool(self.italico)), int(self.sublinhado)]
        return base + [retos] if retos else base

    @classmethod
    def de_json(cls, bruto) -> "Estilo":
        negrito, italico, sublinhado, retos = (list(bruto or []) + [0, 0, 0, 0])[:4]
        negrito = True if negrito else (False if retos & 1 else None)
        italico = True if italico else (False if retos & 2 else None)
        if negrito is None and italico is None and not sublinhado:
            return SEM_ESTILO
        return cls(negrito, italico, bool(sublinhado))


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
#: As letras das peças em cada idioma, na ordem rei, dama, torre, bispo, cavalo: as do lance
#: na prosa do livro (a sessão, a busca, o PGN). Uma definição só (SPEC-qualidade Q-E5).
PECAS = {"pt": "RDTBC", "en": "KQRBN", "es": "RDTAC", "de": "KDTLS", "fr": "RDTFC"}
#: As letras das peças de todos os idiomas: as que dizem lance sem saber o idioma do livro.
LETRAS_DAS_PECAS = "".join(sorted(set("".join(PECAS.values()))))


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
        return usados | self._ancoras_dos_virtuais()

    def _ancoras_dos_virtuais(self) -> Set[int]:
        """Os boxes a que os virtuais se prendem (a âncora que é outro virtual não conta)."""
        virtuais = {v.gid for v in self.virtuais}
        return {g for v in self.virtuais for g in (v.depois_de, v.antes_de)
                if g is not None and g not in virtuais}

    def reescrever(self, sucessores: Dict[int, List[int]]) -> Tuple["Decisoes", List[str]]:
        """As decisões com os gids aposentados trocados pelos sucessores. Devolve também o
        que caiu (gid aposentado sem sucessor), em frases, para a interface avisar."""
        r = _Reescrita(sucessores)
        juncoes = r.juncoes(self.juncoes)
        virtuais = [r.virtual(v) for v in self.virtuais]
        quebras = r.conjunto(self.quebras, r.primeiro, "palavra nova antes")
        # Dois glifos fundidos podem levar uma quebra e uma junção à mesma fronteira (a
        # junção que terminava num e a quebra antes do outro). As duas não valem juntas:
        # fica a junção, que é sobre o glifo que já começava a fronteira, e a quebra cai.
        conflito = quebras & {b for _, b in juncoes}
        for g in sorted(conflito):
            r.caidas.append(f"palavra nova antes do glifo {g} (o glifo foi fundido no fim de "
                            "uma palavra juntada)")
        return Decisoes(
            quebras=quebras - conflito,
            juncoes=frozenset(juncoes),
            paragrafo_antes=r.conjunto(self.paragrafo_antes, r.primeiro, "parágrafo antes"),
            virtuais=tuple(virtuais),
            hifen_de_quebra=r.conjunto(self.hifen_de_quebra, r.ultimo, "hífen de quebra"),
        ), r.caidas

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


class _Reescrita:
    """Os gids aposentados levados aos sucessores (`Decisoes.reescrever`), com as frases do
    que caiu, na ordem em que caiu."""

    def __init__(self, sucessores: Dict[int, List[int]]):
        self.sucessores = sucessores
        self.caidas: List[str] = []

    def primeiro(self, g: int) -> Optional[int]:
        if g not in self.sucessores:
            return g
        novos = self.sucessores[g]
        return novos[0] if novos else None

    def ultimo(self, g: int) -> Optional[int]:
        if g not in self.sucessores:
            return g
        novos = self.sucessores[g]
        return novos[-1] if novos else None

    def conjunto(self, conjunto, onde, rotulo: str) -> FrozenSet[int]:
        saida = set()
        for g in conjunto:
            novo = onde(g)
            if novo is None:
                self.caidas.append(f"{rotulo} do glifo {g} (o glifo saiu)")
            else:
                saida.add(novo)
        return frozenset(saida)

    def juncoes(self, juncoes) -> Set[Tuple[int, int]]:
        """A junção vai do último sucessor de um ao primeiro do outro; a dos dois glifos
        fundidos num só some."""
        saida = set()
        for a, b in juncoes:
            na, nb = self.ultimo(a), self.primeiro(b)
            if na is None or nb is None:
                self.caidas.append(f"junção de palavras {a}+{b} (um dos glifos saiu)")
            elif na != nb:
                saida.add((na, nb))
        return saida

    def virtual(self, v: GlifoVirtual) -> GlifoVirtual:
        """O virtual antes do primeiro sucessor do `antes_de` e depois do último do
        `depois_de`; a âncora que saiu vira None (o começo da página)."""
        if v.antes_de is not None and v.antes_de in self.sucessores:
            novo = self.primeiro(v.antes_de)
            if novo is None:
                self.caidas.append(f"glifo virtual '{v.char}' antes do glifo {v.antes_de} "
                                   "(o glifo saiu; o virtual foi para o começo da página)")
            v = replace(v, antes_de=novo)
        if v.depois_de is None or v.depois_de not in self.sucessores:
            return v
        novo = self.ultimo(v.depois_de)
        if novo is None:
            self.caidas.append(f"glifo virtual '{v.char}' depois do glifo {v.depois_de} "
                               "(o glifo saiu; o virtual foi para o começo da página)")
        return replace(v, depois_de=novo)


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

class Estado(StrEnum):
    """O estado da página. É texto (o JSON e as comparações não mudam), e `Estado(texto)`
    recusa o que não é estado: a entrada do disco o valida (SPEC-qualidade Q-P9)."""

    NAO_RECONHECIDA = "nao_reconhecida"
    GLIFOS_MARCADOS = "glifos_marcados"
    RECONHECIDA = "reconhecida"
    EM_REVISAO = "em_revisao"
    VERIFICADA = "verificada"


NAO_RECONHECIDA = Estado.NAO_RECONHECIDA
GLIFOS_MARCADOS = Estado.GLIFOS_MARCADOS
RECONHECIDA = Estado.RECONHECIDA
EM_REVISAO = Estado.EM_REVISAO
VERIFICADA = Estado.VERIFICADA
ESTADOS = tuple(Estado)
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
    #: A régua do negrito da página (`regua_do_negrito.regua_da_pagina`), da última leitura
    #: dela: vai ao resumo do livro, de onde sai a régua do livro para ler as outras.
    regua_do_negrito: dict = field(default_factory=dict)

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
                      areas_fora=tuple(self.areas_fora), regua_do_negrito=self.regua_do_negrito)

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
    r = _Reconciliacao(antes, depois, amostra_de, estados or {}, estilo_de)
    r.pelo_objeto()                                          # 1. o mesmo objeto
    if r.faltam():                                           # 2. a mesma caixa
        r.pela_caixa()
    if iou_minimo is not None and r.faltam():                # 2½. pela sobreposição
        r.pela_sobreposicao(iou_minimo)
    saidos = [b for b in antes if b.gid not in r.usados]
    r.nascidos(alocar)                                       # 3. nascidos
    r.sucessores(saidos)
    return list(r.saida), r.dif


class _Reconciliacao:
    """O que `reconciliar` vai decidindo: os gids de `antes` já usados, o `Box` de cada
    `BoxEntry` de `depois` (None: ainda nenhum) e a `Diferenca`."""

    def __init__(self, antes: Sequence[Box], depois: Sequence[BoxEntry], amostra_de,
                 estados: Dict[int, int], estilo_de):
        self.antes, self.depois = antes, depois
        self.amostra_de, self.estilo_de = amostra_de, estilo_de
        self.estados = estados
        self.usados: Set[int] = set()
        self.saida: List[Optional[Box]] = [None] * len(depois)
        self.dif = Diferenca()
        self.agora = [foto(e) for e in depois]              # uma vez por glifo

    def faltam(self) -> bool:
        return any(s is None for s in self.saida)

    def manter(self, i: int, velho: Box, entry: BoxEntry, estado_antes) -> None:
        """O glifo `velho` continua, com o `BoxEntry` de agora no índice `i`."""
        self.usados.add(velho.gid)
        mudou = self.agora[i] != estado_antes
        amostra = self._amostra(velho, entry, mudou)
        estilo = self._estilo(velho, entry)
        if entry is velho.entry and amostra == velho.amostra and estilo == velho.estilo:
            self.saida[i] = velho                # o caso comum: nada a copiar
        else:
            self.saida[i] = replace(velho, entry=entry, amostra=amostra, estilo=estilo)
        if mudou or estilo != velho.estilo:
            self.dif.mudados.add(velho.gid)

    def _amostra(self, velho: Box, entry: BoxEntry, mudou: bool) -> Optional[str]:
        registrada = self.amostra_de(entry)
        if registrada is None:              # ninguém leu este objeto desde a gravação
            return None if mudou else velho.amostra
        return registrada or None           # "" = lido, mas não por um padrão do livro

    def _estilo(self, velho: Box, entry: BoxEntry) -> Estilo:
        estilo = self.estilo_de(entry)
        if estilo is None:
            return velho.estilo
        if velho.estilo.sublinhado != estilo.sublinhado:
            # A medida diz o negrito e o itálico; o sublinhado é do usuário (Ctrl+U) e fica.
            return replace(estilo, sublinhado=velho.estilo.sublinhado)
        return estilo

    def pelo_objeto(self) -> None:
        por_objeto = {id(b.entry): b for b in self.antes}
        for i, entry in enumerate(self.depois):
            velho = por_objeto.get(id(entry))
            if velho is not None and velho.entry is entry and velho.gid not in self.usados:
                self.manter(i, velho, entry, self.estados.get(velho.gid, self.agora[i]))

    def pela_caixa(self) -> None:
        por_caixa = self._por_caixa()
        for i, entry in enumerate(self.depois):
            if self.saida[i] is not None:
                continue
            velho = next((b for b in por_caixa.get(_caixa(entry), [])
                          if b.gid not in self.usados), None)
            if velho is not None:
                self.manter(i, velho, entry, self.estados.get(velho.gid, foto(velho.entry)))

    def _por_caixa(self) -> Dict[tuple, List[Box]]:
        return self._dos_que_sobram(lambda entry: (_caixa(entry),))

    def _dos_que_sobram(self, chaves) -> Dict[tuple, List[Box]]:
        """Os glifos de `antes` ainda não usados, sob cada chave que `chaves(entry)` dá."""
        indice: Dict[tuple, List[Box]] = {}
        for b in self.antes:
            if b.gid not in self.usados:
                for chave in chaves(b.entry):
                    indice.setdefault(chave, []).append(b)
        return indice

    def pela_sobreposicao(self, iou_minimo: float) -> None:
        """Os que sobram casam um a um, da maior IoU para a menor."""
        for _iou_do_par, i, velho in self._pares(iou_minimo):
            if self.saida[i] is None and velho.gid not in self.usados:
                self.manter(i, velho, self.depois[i],
                            self.estados.get(velho.gid, foto(velho.entry)))

    def _pares(self, iou_minimo: float) -> list:
        """(IoU, índice em `depois`, glifo de `antes`) dos que sobram dos dois lados e se
        sobrepõem ao menos `iou_minimo`, da maior IoU para a menor."""
        celulas = self._celulas_dos_que_sobram()
        pares = []
        for i, entry in enumerate(self.depois):
            if self.saida[i] is None:
                vistos = {}
                for celula in _celulas(entry):
                    for velho in celulas.get(celula, ()):
                        vistos[velho.gid] = velho
                pares.extend((iou, i, velho) for velho in vistos.values()
                             if (iou := _iou(velho.entry, entry)) >= iou_minimo)
        pares.sort(key=lambda par: -par[0])
        return pares

    def _celulas_dos_que_sobram(self) -> Dict[tuple, List[Box]]:
        return self._dos_que_sobram(_celulas)       # só os vizinhos, não a página inteira

    def nascidos(self, alocar) -> None:
        """O que sobra de `depois` nasce com gid novo."""
        for i, entry in enumerate(self.depois):
            if self.saida[i] is not None:
                continue
            novo = Box(alocar(), entry, self.amostra_de(entry) or None,
                       self.estilo_de(entry) or SEM_ESTILO)
            self.saida[i] = novo
            self.dif.novos.append(novo)

    def sucessores(self, saidos: Sequence[Box]) -> None:
        """Cada glifo que saiu tem por sucessores os nascidos que se sobrepõem a ele."""
        for velho in saidos:
            self.dif.removidos.add(velho.gid)
            self.dif.sucessores[velho.gid] = [n.gid for n in self.dif.novos
                                              if _sobrepoe(velho.entry, n.entry)]


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

