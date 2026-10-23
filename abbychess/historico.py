"""O desfazer do projeto (SPEC §14.2): transações por gid, com pré-condição.

Um `HistoricoDoProjeto` guarda as `Transacao`es do projeto inteiro, da mais antiga à mais
nova, até `LIMITE_DE_MEMORIA` (as mais antigas saem). Cada transação diz, por página
(`MudancaDaPagina`), **só o que mudou**: o `Box` de antes e o de depois de cada gid tocado
(`None` = não existia), as vizinhanças para recolocar um glifo que volta no lugar dele na
ordem de leitura, e os campos da página que mudaram (decisões, áreas, tabuleiros,
diagramas, estado). Junto, as amostras de padrão que ela criou e as que apagou.

**Pré-condição por gid.** Desfazer só aplica se cada gid tocado está hoje igual ao que a
transação o deixou (`igual`: o mesmo objeto, ou o mesmo gid, leitura, caixa, amostra,
estilo e revisão, como o de uma página relida do disco); senão recusa, inteira, e diz
por quê. Uma mudança feita por fora em **outros** gids não impede. A versão
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

from abbychess.leitor import FONTE_MANUAL
from abbychess.modelo import Box, Decisoes, Pagina

#: O que o desfazer do projeto guarda, no máximo (estimado); as mais antigas saem.
LIMITE_DE_MEMORIA = 50 * 2**20
#: Quantos vizinhos de antes guardar para recolocar um glifo que volta.
VIZINHOS = 3
#: Os campos da página que uma transação pode mudar, além dos glifos.
CAMPOS = ("decisoes", "zonas", "tabuleiros", "diagramas", "estado")
#: Estimativa do custo de um glifo guardado (o `Box` e o `BoxEntry`, em bytes).
BYTES_POR_GLIFO = 600
#: E de uma área ou um diagrama guardado (um diagrama lido tem 64 casas).
BYTES_POR_ITEM = 4000


@dataclass
class MudancaDaPagina:
    """O que uma transação mudou numa página."""

    pid: int
    #: A posição da página quando a transação foi feita: só para os avisos (o desfazer acha a
    #: página pelo `pid`, que não muda quando ela troca de lugar, §12.4).
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
    #: (ordem antes, ordem depois) dos gids, só quando a edição reordenou os que ficaram
    #: (marcar um quadro refaz a ordem de leitura da página inteira).
    ordem: Optional[Tuple[Tuple[int, ...], Tuple[int, ...]]] = None

    def bytes(self) -> int:
        tamanho = len(self.antes) * 2 * BYTES_POR_GLIFO
        tamanho += (len(self.vizinhos_antes) + len(self.vizinhos_depois)) * (VIZINHOS + 2) * 32
        if self.ordem is not None:
            tamanho += (len(self.ordem[0]) + len(self.ordem[1])) * 36
        for antes, depois in self.campos.values():
            for valor in (antes, depois):
                itens = len(valor) if isinstance(valor, tuple) else 1
                tamanho += sys.getsizeof(valor) + itens * BYTES_POR_ITEM
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
    #: (antes, depois) da sequência do livro, nas operações de página (§12.4): desfazer só
    #: aplica se a sequência de agora é a de depois.
    sequencia: Optional[tuple] = None

    def bytes(self) -> int:
        ordem = 0 if self.sequencia is None else sum(
            (len(s.entradas) + len(s.apagadas)) * 96 for s in self.sequencia)
        return (sum(m.bytes() for m in self.paginas.values()) + ordem
                + sum(len(a.png) for a in self.amostras_criadas + self.amostras_apagadas))


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
    ficaram = set(ordem_antes) & set(ordem_depois)
    if [g for g in ordem_antes if g in ficaram] != [g for g in ordem_depois if g in ficaram]:
        m.ordem = (tuple(ordem_antes), tuple(ordem_depois))
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
        if gid in mais.vizinhos_antes and gid not in m.vizinhos_antes \
                and m.antes[gid] is not None:     # mexido em `m`, removido em `mais`
            m.vizinhos_antes[gid] = mais.vizinhos_antes[gid]
        m.depois[gid] = mais.depois[gid]
        if gid in mais.vizinhos_depois:
            m.vizinhos_depois[gid] = mais.vizinhos_depois[gid]
    for gid in [g for g in m.antes if m.antes[g] is m.depois[g]]:
        del m.antes[gid], m.depois[gid]              # voltou ao que era: não mudou
    if mais.ordem is not None:
        m.ordem = ((m.ordem or mais.ordem)[0], mais.ordem[1])
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


def igual(a: Optional[Box], b: Optional[Box]) -> bool:
    """O mesmo glifo, no mesmo estado: o mesmo objeto, ou um igual campo a campo (a página
    que saiu da memória e foi relida do disco tem objetos novos)."""
    if a is b:
        return True
    if a is None or b is None:
        return False
    return (a.gid == b.gid and a.amostra == b.amostra and a.estilo == b.estilo
            and a.revisado == b.revisado and a.entry.as_state() == b.entry.as_state())


def lido_depois(atual: Optional[Box], esperado: Optional[Box]) -> bool:
    """O glifo esperado estava "aguardando leitura" (§11) e o atual é ele mesmo, só que lido
    pelo servidor depois: a leitura que chega não é uma decisão, e não impede o desfazer."""
    if atual is None or esperado is None or atual.gid != esperado.gid:
        return False
    e, a = esperado.entry, atual.entry
    return (not e.char and not e.source and a.source != FONTE_MANUAL
            and (a.x1, a.y1, a.x2, a.y2) == (e.x1, e.y1, e.x2, e.y2)
            and atual.estilo == esperado.estilo and atual.revisado == esperado.revisado)


def conferir(m: MudancaDaPagina, pagina: Optional[Pagina], *, para_tras: bool) -> None:
    """Levanta `Recusa` se a página não está como a transação a deixou (nos gids dela). O
    glifo que estava aguardando leitura e foi lido depois conta como igual."""
    esperado = m.depois if para_tras else m.antes
    atuais = {b.gid: b for b in pagina.boxes} if pagina is not None else {}
    mudados = [gid for gid, box in esperado.items()
               if not igual(atuais.get(gid), box) and not lido_depois(atuais.get(gid), box)]
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
    if m.ordem is not None:
        ordem = _na_ordem(ordem, m.ordem[0] if para_tras else m.ordem[1])
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
            virtuais=_virtuais_ancorados(d.virtuais, vivos))


def _virtuais_ancorados(virtuais, vivos) -> tuple:
    """Os virtuais cujas âncoras ainda estão na página (um box vivo ou um virtual que fica)."""
    ficam = tuple(virtuais)
    while True:
        gids = vivos | {v.gid for v in ficam}
        filtrados = tuple(v for v in ficam if (v.depois_de is None or v.depois_de in gids)
                          and (v.antes_de is None or v.antes_de in gids))
        if len(filtrados) == len(ficam):
            return filtrados
        ficam = filtrados


def _na_ordem(ordem: List[int], alvo: Sequence[int]) -> List[int]:
    """Os gids de `ordem` na ordem de `alvo`; os que `alvo` não tem (de uma edição feita
    depois) ficam logo depois de quem vinha antes deles em `ordem`."""
    posicao = {g: i for i, g in enumerate(alvo)}
    saida = sorted((g for g in ordem if g in posicao), key=posicao.__getitem__)
    for i, gid in enumerate(ordem):
        if gid in posicao:
            continue
        anterior = next((ordem[k] for k in range(i - 1, -1, -1) if ordem[k] in saida), None)
        saida.insert(0 if anterior is None else saida.index(anterior) + 1, gid)
    return saida


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
        #: transação -> a estimativa dela, calculada uma vez (o total anda junto).
        self._tamanho: Dict[int, int] = {}
        self._total = 0
        #: pid -> quantas vezes uma ação do usuário mudou a página (registrar, emendar,
        #: desfazer, refazer): o lote compara antes e depois de ler (§11).
        self._versoes: Dict[int, int] = {}

    def versao(self, pid: Optional[int]) -> int:
        return self._versoes.get(pid, 0) if pid is not None else 0

    def tocar(self, pid: int) -> None:
        """A página mudou por fora do desfazer, por um comando do usuário (voltar ao estado
        antes do lote): o lote que a lê agora não grava por cima."""
        self._versoes[pid] = self._versoes.get(pid, 0) + 1

    def _mudou(self, transacao: Transacao) -> None:
        for pid in transacao.paginas:
            self._versoes[pid] = self._versoes.get(pid, 0) + 1

    def _medir(self, transacao: Transacao) -> None:
        self._total -= self._tamanho.get(id(transacao), 0)
        self._tamanho[id(transacao)] = transacao.bytes()
        self._total += self._tamanho[id(transacao)]

    def _esquecer(self, transacao: Transacao) -> None:
        self._total -= self._tamanho.pop(id(transacao), 0)

    def registrar(self, transacao: Transacao) -> Transacao:
        """Uma transação nova, que apaga o que havia para refazer. Uma com a mesma chave
        `juntar` da última se junta a ela (e é a última que volta)."""
        self._mudou(transacao)
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
            self._medir(ultima)
            return ultima
        self._desfazer.append(transacao)
        for velha in self._refazer:
            self._esquecer(velha)
        self._refazer.clear()
        self._medir(transacao)
        while self._total > self.limite and len(self._desfazer) > 1:
            self._esquecer(self._desfazer.pop(0))
        return transacao

    def emendou(self, transacao: Transacao) -> None:
        """A transação cresceu (a propagação a emendou): a estimativa é refeita."""
        self._mudou(transacao)
        if id(transacao) in self._tamanho:
            self._medir(transacao)
            while self._total > self.limite and len(self._desfazer) > 1:
                self._esquecer(self._desfazer.pop(0))

    @property
    def bytes(self) -> int:
        return self._total

    @property
    def passos(self) -> int:
        """Quantas transações o Ctrl+Z ainda alcança."""
        return len(self._desfazer)

    def toca(self, pid: int) -> bool:
        """Alguma transação do desfazer ou do refazer muda a página `pid` (o lote não a
        sobrescreve: o Ctrl+Z dela seria recusado, §11)."""
        return any(pid in t.paginas for t in (*self._desfazer, *self._refazer))

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
        self._mudou(self._refazer[-1])

    def refeita(self) -> None:
        self._desfazer.append(self._refazer.pop())
        self._mudou(self._desfazer[-1])

    def descartar_desfazer(self) -> None:
        """Tira a próxima a desfazer sem aplicá-la (a que foi recusada)."""
        if self._desfazer:
            self._esquecer(self._desfazer.pop())

    def descartar_refazer(self) -> None:
        if self._refazer:
            self._esquecer(self._refazer.pop())

    def limpar(self) -> None:
        self._desfazer.clear()
        self._refazer.clear()
        self._tamanho.clear()
        self._total = 0
