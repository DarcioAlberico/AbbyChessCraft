"""A sequência do livro (SPEC §12.4, passo L): a ordem das páginas e de onde vem cada uma.

Até o passo K o índice da página no PDF era a identidade dela e a posição no livro. A
sequência separa as duas coisas: cada `Entrada` tem o `pid` da página (estável, §4.1) e diz
de onde vem a imagem dela (a fonte, a página da fonte, o `quadro` e o `giro`); a **posição
no livro é o índice na sequência**. As páginas apagadas saem para `apagadas`, com a posição
de onde saíram, e voltam com o mesmo `pid`.

Tudo aqui é puro (sem Qt, sem disco): o projeto guarda a sequência em `projeto.json` e a
monta, para um projeto da v2, com `da_v2`. `selecao` resolve "pares", "ímpares" e "3-7, 12"
em posições do livro.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

#: A fonte do livro (o PDF ou a imagem do projeto); as inseridas são "inseridas/<arquivo>".
FONTE_DO_LIVRO = "livro"
PASTA_DAS_INSERIDAS = "inseridas"
GIROS = (0, 90, 180, 270)
METADES = ("esquerda", "direita")

Quadro = Tuple[int, int, int, int]


def _dentro_das_inseridas(fonte: str) -> bool:
    """`inseridas/<arquivo>`, um nome só: sem `..`, sem barra invertida, sem caminho absoluto
    (um `projeto.json` de fora não abre arquivo nenhum fora da pasta do projeto)."""
    partes = fonte.split("/")
    return (len(partes) == 2 and partes[0] == PASTA_DAS_INSERIDAS and partes[1] not in ("", ".", "..")
            and "\\" not in fonte and ":" not in fonte)


@dataclass(frozen=True)
class Entrada:
    """Uma página do livro: o `pid` e a receita da imagem dela (§12.4). `quadro` é o
    retângulo `[x0, y0, x1, y1)` em pixels da página da fonte (nulo: a página inteira);
    `giro`, graus no sentido horário, depois do quadro; `metade`, só o rótulo de quem veio de
    uma divisão; `angulo`, o endireitar à mão (nulo: o medido)."""

    pid: int
    fonte: str = FONTE_DO_LIVRO
    pagina: int = 0
    quadro: Optional[Quadro] = None
    giro: int = 0
    metade: Optional[str] = None
    angulo: Optional[float] = None

    def __post_init__(self):
        if self.quadro is not None and not isinstance(self.quadro, tuple):
            object.__setattr__(self, "quadro", tuple(self.quadro))     # chave de cache: hashável
        if self.pid < 0 or self.pagina < 0:
            raise ValueError(f"pid e página não negativos: {self.pid}, {self.pagina}")
        if self.giro not in GIROS:
            raise ValueError(f"giro de {self.giro}° (só {GIROS})")
        if self.metade is not None and self.metade not in METADES:
            raise ValueError(f"metade desconhecida: {self.metade!r}")
        if self.quadro is not None:
            x0, y0, x1, y1 = self.quadro
            if not (0 <= x0 < x1 and 0 <= y0 < y1):
                raise ValueError(f"quadro vazio ou invertido: {self.quadro}")
        if self.fonte != FONTE_DO_LIVRO and not _dentro_das_inseridas(self.fonte):
            raise ValueError(f"fonte desconhecida: {self.fonte!r}")

    @property
    def do_livro_intacta(self) -> bool:
        """A página do PDF do livro como ele é (a camada de texto nativa vale nela, §12.1)."""
        return (self.fonte == FONTE_DO_LIVRO and self.quadro is None and self.giro == 0
                and not self.angulo)

    def para_json(self) -> dict:
        bruto: dict = {"pid": self.pid, "fonte": self.fonte, "pagina": self.pagina}
        if self.quadro is not None:
            bruto["quadro"] = list(self.quadro)
        if self.giro:
            bruto["giro"] = self.giro
        if self.metade is not None:
            bruto["metade"] = self.metade
        if self.angulo is not None:
            bruto["angulo"] = self.angulo
        return bruto

    @classmethod
    def de_json(cls, bruto: Mapping) -> "Entrada":
        quadro = bruto.get("quadro")
        angulo = bruto.get("angulo")
        return cls(pid=int(bruto["pid"]), fonte=str(bruto.get("fonte", FONTE_DO_LIVRO)),
                   pagina=int(bruto.get("pagina", 0)),
                   quadro=None if quadro is None else tuple(int(v) for v in quadro),
                   giro=int(bruto.get("giro", 0)), metade=bruto.get("metade"),
                   angulo=None if angulo is None else float(angulo))


@dataclass(frozen=True)
class Apagada:
    """Uma página tirada do livro: a entrada e a posição de onde saiu (para voltar ali)."""

    entrada: Entrada
    posicao: int
    #: O `pid` da página que vinha logo antes dela (apagada junto ou não; None: ela era a
    #: primeira). Restaurar a põe depois dessa página; a posição vale se ela sumiu.
    depois_de: Optional[int] = None

    def para_json(self) -> dict:
        bruto = {**self.entrada.para_json(), "posicao": self.posicao}
        if self.depois_de is not None:
            bruto["depois_de"] = self.depois_de
        return bruto

    @classmethod
    def de_json(cls, bruto: Mapping) -> "Apagada":
        depois_de = bruto.get("depois_de")
        return cls(Entrada.de_json(bruto), int(bruto.get("posicao", 0)),
                   None if depois_de is None else int(depois_de))


@dataclass(frozen=True)
class Sequencia:
    """A ordem do livro. Imutável: cada operação devolve outra (o desfazer guarda as duas)."""

    entradas: Tuple[Entrada, ...] = ()
    apagadas: Tuple[Apagada, ...] = ()
    _posicoes: Dict[int, int] = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self):
        posicoes: Dict[int, int] = {}
        for posicao, entrada in enumerate(self.entradas):
            if entrada.pid in posicoes:
                raise ValueError(f"pid {entrada.pid} repetido na sequência")
            posicoes[entrada.pid] = posicao
        for apagada in self.apagadas:
            if apagada.entrada.pid in posicoes:
                raise ValueError(f"pid {apagada.entrada.pid} na sequência e nas apagadas")
        object.__setattr__(self, "_posicoes", posicoes)

    def __len__(self) -> int:
        return len(self.entradas)

    @property
    def pids(self) -> List[int]:
        return [e.pid for e in self.entradas]

    def pid_em(self, posicao: int) -> int:
        """O `pid` da página na `posicao` do livro (0 = a primeira); IndexError fora."""
        if not 0 <= posicao < len(self.entradas):
            raise IndexError(f"Página {posicao + 1} fora de 1..{len(self.entradas)}")
        return self.entradas[posicao].pid

    def entrada_em(self, posicao: int) -> Entrada:
        return self.entradas[self._valida(posicao)]

    def posicao_de(self, pid: int) -> Optional[int]:
        """A posição da página no livro, ou None (apagada, ou de outro projeto)."""
        return self._posicoes.get(pid)

    def entrada_de(self, pid: int) -> Optional[Entrada]:
        posicao = self._posicoes.get(pid)
        return None if posicao is None else self.entradas[posicao]

    def apagada(self, pid: int) -> Optional[Apagada]:
        return next((a for a in self.apagadas if a.entrada.pid == pid), None)

    @property
    def todos_os_pids(self) -> List[int]:
        """Os do livro e os apagados: nenhum pid novo pode repetir um destes."""
        return self.pids + [a.entrada.pid for a in self.apagadas]

    def _valida(self, posicao: int) -> int:
        if not 0 <= posicao < len(self.entradas):
            raise IndexError(f"Página {posicao + 1} fora de 1..{len(self.entradas)}")
        return posicao

    def com_entrada(self, entrada: Entrada) -> "Sequencia":
        """A mesma sequência com a entrada do `pid` dela trocada (giro, quadro, ângulo)."""
        posicao = self._posicoes.get(entrada.pid)
        if posicao is None:
            raise KeyError(f"pid {entrada.pid} fora da sequência")
        entradas = list(self.entradas)
        entradas[posicao] = entrada
        return replace(self, entradas=tuple(entradas))

    # ------------------------------------------------------------------
    # As operações de página (§12.4, rodada 2): cada uma devolve a sequência nova
    # ------------------------------------------------------------------
    def mover(self, pids: Iterable[int], depois_da: int) -> "Sequencia":
        """As páginas `pids` (na ordem do livro) vão para depois da posição `depois_da` (-1:
        para o começo), contada na numeração de agora. A página de referência não pode ser
        uma das movidas."""
        movidas = self._do_livro(pids)
        if not -1 <= depois_da < len(self.entradas):
            raise ValueError(f"não há a página {depois_da + 1} para pôr as outras depois dela")
        if depois_da >= 0 and self.entradas[depois_da].pid in movidas:
            raise ValueError("a página de referência é uma das que se movem")
        ficam = [e for e in self.entradas if e.pid not in movidas]
        vao = [e for e in self.entradas if e.pid in movidas]
        lugar = 0 if depois_da < 0 else ficam.index(self.entradas[depois_da]) + 1
        return replace(self, entradas=tuple(ficam[:lugar] + vao + ficam[lugar:]))

    def apagar(self, pids: Iterable[int]) -> "Sequencia":
        """As páginas `pids` saem do livro para as apagadas, com a posição de onde saíram,
        contada entre as que ficaram (quantas páginas do livro vinham antes dela): restaurar
        só uma das apagadas juntas a põe no lugar certo. O livro não fica sem página nenhuma."""
        saem = self._do_livro(pids)
        if len(saem) >= len(self.entradas):
            raise ValueError("o livro não pode ficar sem páginas")
        apagadas, ficaram, anterior = [], 0, None
        for entrada in self.entradas:
            if entrada.pid in saem:
                apagadas.append(Apagada(entrada, ficaram, anterior))
            else:
                ficaram += 1
            anterior = entrada.pid
        apagadas = tuple(apagadas)
        return Sequencia(tuple(e for e in self.entradas if e.pid not in saem),
                         self.apagadas + apagadas)

    def restaurar(self, pids: Iterable[int]) -> "Sequencia":
        """As páginas apagadas `pids` voltam com o mesmo `pid`, logo depois da página que
        vinha antes delas (`Apagada.depois_de`; se ela também está apagada, a que vinha antes
        dela, e assim por diante). Sem essa página no livro, vale a posição gravada (ou o
        fim, se o livro ficou mais curto). Juntas ou uma de cada vez, voltam à mesma ordem."""
        pids = set(pids)
        voltam = sorted((a for a in self.apagadas if a.entrada.pid in pids),
                        key=lambda a: a.posicao)
        if len(voltam) != len(pids):
            faltam = pids - {a.entrada.pid for a in voltam}
            raise ValueError(f"página(s) que não estão entre as apagadas: {sorted(faltam)}")
        por_pid = {a.entrada.pid: a for a in self.apagadas}
        entradas = list(self.entradas)
        # Da apagada mais nova para a mais velha (as apagadas estão na ordem em que saíram):
        # cada uma volta ao livro como ele era quando ela saiu, como um desfazer em sequência.
        voltando = [a for a in reversed(self.apagadas) if a.entrada.pid in pids]
        while voltando:
            # Primeiro a que tem a âncora já no livro (as apagadas juntas voltam em cadeia).
            no_livro = {e.pid for e in entradas}
            for k, apagada in enumerate(voltando):
                ancora = _ancora(apagada, por_pid, no_livro, pids)
                if ancora is not _ESPERA:
                    break
            else:
                k, ancora = 0, None             # um ciclo (não acontece): a posição gravada
            apagada = voltando.pop(k)
            if ancora is _SEM_ANCORA or ancora is None:
                lugar = 0 if ancora is _SEM_ANCORA else min(apagada.posicao, len(entradas))
            else:
                lugar = next(i for i, e in enumerate(entradas) if e.pid == ancora) + 1
            entradas.insert(lugar, apagada.entrada)
        return Sequencia(tuple(entradas),
                         tuple(a for a in self.apagadas if a.entrada.pid not in pids))

    def inserir(self, novas: Sequence[Entrada], na_posicao: int) -> "Sequencia":
        """As entradas novas (com `pid` novos) entram a partir da posição `na_posicao` (0: antes
        da primeira; o tamanho do livro: no fim)."""
        if not 0 <= na_posicao <= len(self.entradas):
            raise ValueError(f"posição {na_posicao + 1} fora do livro")
        entradas = list(self.entradas)
        entradas[na_posicao:na_posicao] = list(novas)
        return replace(self, entradas=tuple(entradas))

    def _do_livro(self, pids: Iterable[int]) -> set:
        pids = set(pids)
        if not pids:
            raise ValueError("nenhuma página escolhida")
        fora = pids - set(self._posicoes)
        if fora:
            raise ValueError(f"página(s) fora do livro: {sorted(fora)}")
        return pids

    # ------------------------------------------------------------------
    def para_json(self) -> dict:
        return {"entradas": [e.para_json() for e in self.entradas],
                "apagadas": [a.para_json() for a in self.apagadas]}

    @classmethod
    def de_json(cls, bruto: Mapping) -> "Sequencia":
        """A sequência gravada; sem a lista `entradas` (outro formato), KeyError: uma sequência
        vazia por engano daria `pid` novos a todas as páginas."""
        entradas, apagadas = bruto["entradas"], bruto.get("apagadas", [])
        if not isinstance(entradas, list) or not isinstance(apagadas, list):
            raise TypeError("as entradas e as apagadas são listas")
        return cls(tuple(Entrada.de_json(e) for e in entradas),
                   tuple(Apagada.de_json(a) for a in apagadas))

    @classmethod
    def do_livro(cls, pids: Iterable[int]) -> "Sequencia":
        """A página `i` do PDF do livro na posição `i`, com o `pid` dado."""
        return cls(tuple(Entrada(pid, FONTE_DO_LIVRO, i) for i, pid in enumerate(pids)))


#: As respostas de `_ancora` que não são um pid: a página era a primeira do livro, ou a
#: âncora dela volta junto e ainda não entrou.
_SEM_ANCORA, _ESPERA = object(), object()


def _ancora(apagada: Apagada, por_pid: Mapping[int, Apagada], no_livro: set, voltam: set):
    """Depois de que página a apagada volta: o pid de uma página do livro, `_SEM_ANCORA` (a
    primeira), `_ESPERA` (a âncora volta junto e ainda não entrou) ou None (a âncora sumiu:
    vale a posição gravada)."""
    vistos = set()
    atual = apagada
    while True:
        alvo = atual.depois_de
        if alvo is None:
            return _SEM_ANCORA if atual.posicao == 0 else None
        if alvo in no_livro:
            return alvo
        if alvo in voltam and alvo in por_pid:
            return _ESPERA
        if alvo in vistos or alvo not in por_pid:
            return None
        vistos.add(alvo)
        atual = por_pid[alvo]                   # apagada antes e que fica: a âncora dela


def da_v2(total: int, pids_gravados: Mapping[int, int], indices_v1: Iterable[int],
          proximo_pid: int) -> Tuple[Sequencia, int]:
    """A sequência de um projeto da v2, de `total` páginas na ordem do PDF, e o próximo
    `pid` depois dela (§12.4, CA-12.7).

    - a página já gravada (`pids_gravados`: índice -> pid) mantém o `pid`;
    - a v1 ainda não migrada (`indices_v1`) fica com `pid` = índice, o que a migração da v1
      dá a ela (os `gid` e as amostras dela já usam esse número);
    - as outras ganham `pid` novos, acima do contador e de todo `pid` já usado.

    Um `pid` gravado que repete outro (dois arquivos do mesmo índice já foram resolvidos pelo
    `livro.json`; aqui seria um erro) levanta `ValueError`."""
    v1 = set(indices_v1)
    usados = set(pids_gravados.values()) | {i for i in v1 if i not in pids_gravados}
    if len(set(pids_gravados.values())) != len(pids_gravados):
        raise ValueError("dois índices com o mesmo pid gravado")
    proximo = max([proximo_pid, *(p + 1 for p in usados)], default=proximo_pid)
    pids: List[int] = []
    for indice in range(total):
        if indice in pids_gravados:
            pids.append(pids_gravados[indice])
        elif indice in v1:
            if indice in pids:
                raise ValueError(f"o pid {indice} da página v1 já foi dado a outra página")
            pids.append(indice)
        else:
            pids.append(proximo)
            proximo += 1
    return Sequencia.do_livro(pids), proximo


# ----------------------------------------------------------------------
# A seleção de páginas (§12.4, CA-12.15)
# ----------------------------------------------------------------------

_PARES = {"pares", "par"}
_IMPARES = {"impares", "ímpares", "impar", "ímpar"}
_TODAS = {"todas", "tudo"}
_PEDACO = re.compile(r"^\s*(\d+)\s*(?:[-–]\s*(\d+)\s*)?$")


def selecao(texto: str, total: int) -> List[int]:
    """As posições do livro (0 = a primeira), em ordem e sem repetir, que o texto pede:
    "todas", "pares", "ímpares" (pelo número da página no livro, que começa em 1), ou
    intervalos e números separados por vírgula ("3-7, 12"). Um pedaço fora de 1..`total`, ao
    contrário ou ilegível levanta `ValueError` com o motivo."""
    limpo = texto.strip().lower()
    if not limpo:
        raise ValueError("diga quais páginas: todas, pares, ímpares ou 3-7, 12")
    if limpo in _TODAS:
        return list(range(total))
    if limpo in _PARES:
        return list(range(1, total, 2))         # as páginas 2, 4, 6…
    if limpo in _IMPARES:
        return list(range(0, total, 2))         # as páginas 1, 3, 5…
    posicoes = set()
    for pedaco in limpo.split(","):
        casou = _PEDACO.match(pedaco)
        if casou is None:
            raise ValueError(f"não entendi {pedaco.strip()!r}: use 3-7, 12")
        de = int(casou.group(1))
        ate = int(casou.group(2) or de)
        if de > ate:
            raise ValueError(f"intervalo ao contrário: {de}-{ate}")
        if de < 1 or ate > total:
            raise ValueError(f"{pedaco.strip()} está fora das páginas 1 a {total}")
        posicoes.update(range(de - 1, ate))
    return sorted(posicoes)


def trechos_do_pdf(sequencia: Sequencia, posicoes: Iterable[int]) -> List[List[Tuple[int, int]]]:
    """As posições cujas páginas são do PDF do livro, intactas, em trechos de `(página do
    PDF, posição)` seguidos nos dois: no livro e no PDF. A camada de texto nativa junta o
    parágrafo de uma página com o da seguinte **do pedido**; pedir trecho a trecho faz essa
    junção só entre páginas vizinhas de verdade, e a de fora (`juntar_entre_paginas`) segue a
    ordem do livro."""
    trechos: List[List[Tuple[int, int]]] = []
    anterior: Optional[Tuple[int, int]] = None
    for posicao in sorted(set(posicoes)):
        entrada = sequencia.entrada_em(posicao)
        if not entrada.do_livro_intacta:
            anterior = None
            continue
        par = (entrada.pagina, posicao)
        if anterior is not None and par == (anterior[0] + 1, anterior[1] + 1):
            trechos[-1].append(par)
        else:
            trechos.append([par])
        anterior = par
    return trechos


def pids_da_selecao(sequencia: Sequencia, posicoes: Sequence[int]) -> List[int]:
    """Os `pid` das posições (a operação guarda os pids, que não mudam no meio dela)."""
    return [sequencia.pid_em(p) for p in posicoes]
