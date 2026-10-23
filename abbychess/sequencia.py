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

    def para_json(self) -> dict:
        return {**self.entrada.para_json(), "posicao": self.posicao}

    @classmethod
    def de_json(cls, bruto: Mapping) -> "Apagada":
        return cls(Entrada.de_json(bruto), int(bruto.get("posicao", 0)))


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
