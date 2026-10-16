"""O desfazer do projeto (SPEC §14.2): transações por gid, com pré-condição.

Um `HistoricoDoProjeto` guarda as `Transacao`es do projeto inteiro, da mais antiga à mais
nova, até `LIMITE_DE_MEMORIA` (as mais antigas saem). Cada transação diz, por página
(`MudancaDaPagina`), **só o que mudou**: o `Box` de antes e o de depois de cada gid tocado
(`None` = não existia), as vizinhanças para recolocar um glifo que volta no lugar dele na
ordem de leitura, e os campos da página que mudaram (decisões, áreas, tabuleiros,
diagramas, estado). Junto, as amostras de padrão que ela criou e as que apagou.

**Pré-condição por gid.** Desfazer só aplica se cada gid tocado está hoje exatamente como a
transação o deixou (o mesmo objeto `Box`: nada é mudado no lugar desde o 2a); senão recusa,
inteira, e diz por quê. Uma mudança feita por fora em **outros** gids não impede. A versão
da página não entra. Os campos da página voltam se ainda estão como a transação os deixou;
se outra coisa os mudou, ficam (e as decisões que citarem um glifo que saiu caem).

**A propagação emenda.** O Enter grava a parte síncrona (o glifo ensinado) numa transação, e
a propagação, que roda depois, emenda o que resolveu no `depois` dela (`emendar`). Desfazer
a transação com a propagação ainda rodando a invalida (`invalidada`), e o resultado dela é
descartado.

O contador de gids (`proximo_n`) nunca volta: um gid não é reaproveitado. Sem Qt.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Tuple

from abbychess.modelo import Box, Decisoes, Pagina

#: O que o desfazer do projeto guarda, no máximo (estimado); as mais antigas saem.
LIMITE_DE_MEMORIA = 50 * 2**20
#: Quantos vizinhos de antes guardar para recolocar um glifo que volta.
VIZINHOS = 3
#: Os campos da página que uma transação pode mudar, além dos glifos.
CAMPOS = ("decisoes", "zonas", "tabuleiros", "diagramas", "estado")
#: Estimativa do custo de um glifo guardado (o `Box` e o `BoxEntry`, em bytes).
BYTES_POR_GLIFO = 600


@dataclass
class MudancaDaPagina:
    """O que uma transação mudou numa página."""

    pid: int
    indice: int
    #: gid -> o Box antes e depois (None: não existia).
    antes: Dict[int, Optional[Box]] = field(default_factory=dict)
    depois: Dict[int, Optional[Box]] = field(default_factory=dict)
    #: gid -> os gids que vinham antes dele na ordem de leitura (o mais perto primeiro),
    #: para os que saíram (desfazer os põe de volta) e para os que nasceram (refazer).
    vizinhos_antes: Dict[int, Tuple[int, ...]] = field(default_factory=dict)
    vizinhos_depois: Dict[int, Tuple[int, ...]] = field(default_factory=dict)
    #: campo -> (valor antes, valor depois), só os que mudaram.
    campos: Dict[str, tuple] = field(default_factory=dict)

    @property
    def vazia(self) -> bool:
        return not self.antes and not self.campos

    def bytes(self) -> int:
        tamanho = len(self.antes) * 2 * BYTES_POR_GLIFO
        for antes, depois in self.campos.values():
            tamanho += sys.getsizeof(antes) + sys.getsizeof(depois)
        return tamanho


@dataclass(eq=False)
class Transacao:
    descricao: str
    paginas: Dict[int, MudancaDaPagina] = field(default_factory=dict)       # por pid
    #: Os padrões que ela gravou (desfazer os apaga) e os que apagou (desfazer os devolve),
    #: inteiros (`padroes.Amostra`).
    amostras_criadas: list = field(default_factory=list)
    amostras_apagadas: list = field(default_factory=list)
    #: Uma chave que junta transações seguidas do mesmo tipo (os Alt+seta num glifo).
    juntar: Optional[tuple] = None
    #: Desfeita com a propagação dela ainda rodando: o resultado da propagação não entra.
    invalidada: bool = False

    def bytes(self) -> int:
        return (sum(m.bytes() for m in self.paginas.values())
                + sum(len(a.png) for a in self.amostras_criadas + self.amostras_apagadas))

    @property
    def indices(self) -> List[int]:
        return sorted(m.indice for m in self.paginas.values())


# ----------------------------------------------------------------------
# Medir a mudança entre dois instantâneos
# ----------------------------------------------------------------------

def mudanca(antes: Optional[Pagina], depois: Pagina) -> MudancaDaPagina:
    """O que mudou de `antes` (instantâneo; None = a página não existia) a `depois`."""
    m = MudancaDaPagina(depois.pid, depois.indice)
    velhos = {b.gid: b for b in (antes.boxes if antes is not None else ())}
    novos = {b.gid: b for b in depois.boxes}
    for gid, box in velhos.items():
        if novos.get(gid) is not box:
            m.antes[gid], m.depois[gid] = box, novos.get(gid)
    for gid, box in novos.items():
        if gid not in velhos:
            m.antes[gid], m.depois[gid] = None, box
    ordem_antes = [b.gid for b in antes.boxes] if antes is not None else []
    ordem_depois = [b.gid for b in depois.boxes]
    m.vizinhos_antes = _vizinhos(ordem_antes, {g for g in m.antes if m.depois[g] is None})
    m.vizinhos_depois = _vizinhos(ordem_depois, {g for g in m.antes if m.antes[g] is None})
    for campo in CAMPOS:
        valor_antes = getattr(antes, campo) if antes is not None else _vazio(campo)
        valor_depois = getattr(depois, campo)
        if _congelar(valor_antes) != _congelar(valor_depois):
            m.campos[campo] = (_congelar(valor_antes), _congelar(valor_depois))
    return m


def emendar(m: MudancaDaPagina, mais: MudancaDaPagina) -> None:
    """Acrescenta a `m` o que `mais` mudou depois (a propagação de um Enter): o `antes` de
    um gid fica o de `m`, o `depois` passa a ser o de `mais`."""
    for gid in mais.antes:
        if gid not in m.antes:
            m.antes[gid] = mais.antes[gid]
            if gid in mais.vizinhos_antes:
                m.vizinhos_antes[gid] = mais.vizinhos_antes[gid]
        m.depois[gid] = mais.depois[gid]
        if gid in mais.vizinhos_depois:
            m.vizinhos_depois[gid] = mais.vizinhos_depois[gid]
    for gid in [g for g in m.antes if m.antes[g] is m.depois[g]]:
        del m.antes[gid], m.depois[gid]              # voltou ao que era: não mudou
    for campo, (_antes, depois) in mais.campos.items():
        antes = m.campos.get(campo, (_antes, None))[0]
        if antes == depois:
            m.campos.pop(campo, None)
        else:
            m.campos[campo] = (antes, depois)


def _vizinhos(ordem: Sequence[int], quais: set) -> Dict[int, Tuple[int, ...]]:
    saida = {}
    for i, gid in enumerate(ordem):
        if gid in quais:
            saida[gid] = tuple(reversed(ordem[max(0, i - VIZINHOS):i]))
    return saida


def _vazio(campo: str):
    return {"decisoes": Decisoes(), "estado": "nao_reconhecida"}.get(campo, ())


def _congelar(valor):
    return tuple(valor) if isinstance(valor, list) else valor


# ----------------------------------------------------------------------
# Aplicar uma mudança (desfazer: para trás; refazer: para a frente)
# ----------------------------------------------------------------------

class Recusa(Exception):
    """A pré-condição não vale: algum gid da transação mudou por fora."""


def conferir(m: MudancaDaPagina, pagina: Optional[Pagina], *, para_tras: bool) -> None:
    """Levanta `Recusa` se a página não está como a transação a deixou (nos gids dela)."""
    esperado = m.depois if para_tras else m.antes
    atuais = {b.gid: b for b in pagina.boxes} if pagina is not None else {}
    mudados = [gid for gid, box in esperado.items() if atuais.get(gid) is not box]
    if mudados:
        raise Recusa(f"{len(mudados)} glifo(s) da página {m.indice + 1} mudaram depois "
                     "(por outra ação, que não passou por este desfazer)")


def aplicar(m: MudancaDaPagina, pagina: Pagina, *, para_tras: bool) -> None:
    """Põe a página no `antes` (para trás) ou no `depois` da mudança, nos gids dela e nos
    campos que ainda estão como a mudança os deixou. Chame `conferir` antes."""
    alvo = m.antes if para_tras else m.depois
    vizinhos = m.vizinhos_antes if para_tras else m.vizinhos_depois
    atuais = {b.gid: b for b in pagina.boxes}
    ordem = [b.gid for b in pagina.boxes]
    sair = {gid for gid, box in alvo.items() if box is None}
    ordem = [g for g in ordem if g not in sair]
    voltar = [gid for gid, box in alvo.items() if box is not None and gid not in atuais]
    # Na ordem de antes, para o vizinho de um que volta já estar no lugar quando ele vier.
    for gid in sorted(voltar, key=lambda g: _posicao(g, vizinhos)):
        lugar = 0
        for vizinho in vizinhos.get(gid, ()):
            if vizinho in ordem:
                lugar = ordem.index(vizinho) + 1
                break
        ordem.insert(lugar, gid)
    caixas = {**atuais, **{g: b for g, b in alvo.items() if b is not None}}
    pagina.boxes = [caixas[g] for g in ordem]
    for campo, (antes, depois) in m.campos.items():
        hoje, de_la, para = (_congelar(getattr(pagina, campo)), *(
            (depois, antes) if para_tras else (antes, depois)))
        if hoje == de_la:
            setattr(pagina, campo, list(para) if isinstance(para, tuple) else para)
    vivos = pagina.vivos
    d = pagina.decisoes
    if not d.gids() <= vivos:                       # o que cita um glifo que saiu cai
        pagina.decisoes = replace(
            d, quebras=d.quebras & vivos, paragrafo_antes=d.paragrafo_antes & vivos,
            hifen_de_quebra=d.hifen_de_quebra & vivos,
            juncoes=frozenset(j for j in d.juncoes if set(j) <= vivos),
            virtuais=tuple(v for v in d.virtuais
                           if v.depois_de is None or v.depois_de in vivos))


def _posicao(gid: int, vizinhos: Dict[int, Tuple[int, ...]]) -> int:
    """Quantos dos que voltam vêm antes dele (pela cadeia de vizinhos)."""
    profundidade, atual, vistos = 0, gid, set()
    while atual in vizinhos and vizinhos[atual] and atual not in vistos:
        vistos.add(atual)
        atual = vizinhos[atual][0]
        profundidade += 1
    return profundidade


# ----------------------------------------------------------------------
# O histórico
# ----------------------------------------------------------------------

class HistoricoDoProjeto:
    """As pilhas de desfazer e refazer do projeto inteiro, com limite de memória."""

    def __init__(self, limite: int = LIMITE_DE_MEMORIA):
        self.limite = limite
        self._desfazer: List[Transacao] = []
        self._refazer: List[Transacao] = []

    def registrar(self, transacao: Transacao) -> Transacao:
        """Uma transação nova, que apaga o que havia para refazer. Uma com a mesma chave
        `juntar` da última se junta a ela (e é a última que volta)."""
        ultima = self._desfazer[-1] if self._desfazer else None
        if (transacao.juntar is not None and ultima is not None and not self._refazer
                and ultima.juntar == transacao.juntar and not ultima.invalidada):
            for pid, m in transacao.paginas.items():
                if pid in ultima.paginas:
                    emendar(ultima.paginas[pid], m)
                else:
                    ultima.paginas[pid] = m
            ultima.amostras_criadas.extend(transacao.amostras_criadas)
            ultima.amostras_apagadas.extend(transacao.amostras_apagadas)
            return ultima
        self._desfazer.append(transacao)
        self._refazer.clear()
        self._caber()
        return transacao

    def _caber(self) -> None:
        total = sum(t.bytes() for t in self._desfazer)
        while total > self.limite and len(self._desfazer) > 1:
            total -= self._desfazer.pop(0).bytes()

    @property
    def bytes(self) -> int:
        return sum(t.bytes() for t in self._desfazer + self._refazer)

    def proxima_a_desfazer(self) -> Optional[Transacao]:
        return self._desfazer[-1] if self._desfazer else None

    def proxima_a_refazer(self) -> Optional[Transacao]:
        return self._refazer[-1] if self._refazer else None

    @property
    def proximo_a_desfazer(self) -> Optional[str]:
        t = self.proxima_a_desfazer()
        return t.descricao if t else None

    @property
    def proximo_a_refazer(self) -> Optional[str]:
        t = self.proxima_a_refazer()
        return t.descricao if t else None

    def desfeita(self) -> None:
        """A última foi desfeita (com sucesso): vai para o refazer."""
        self._refazer.append(self._desfazer.pop())

    def refeita(self) -> None:
        self._desfazer.append(self._refazer.pop())

    def limpar(self) -> None:
        self._desfazer.clear()
        self._refazer.clear()
