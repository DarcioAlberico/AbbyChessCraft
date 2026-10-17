"""A sessão de edição do Documento (SPEC §6.3, as linhas do passo D1; §6.4): sem Qt.

A vista guarda, de cada caractere da página montada, a `Unidade` dele: o glifo (box ou
virtual), o espaço entre palavras, a quebra de linha impressa ou outra coisa (o diagrama).
Uma sessão é a menor sequência de palavras inteiras que as edições tocaram: as unidades
dela e o texto que ela tem agora. Confirmar a sessão é:

1. **Realinhar** o texto de agora contra o original (`alinhar`: Levenshtein; no empate, a
   substituição antes de inserir e apagar, e o alinhamento à esquerda). Teclas, IME, colar,
   arrastar e autocompletar dão o mesmo resultado, porque só o texto final conta. Os
   caracteres que a vista sabe que nenhuma edição tocou (`fixos`) ficam com o glifo deles:
   apagar o segundo "s" de "cassa" tira o segundo glifo.
2. **Planejar** (`planejar`): cada glifo do original fica (com o caractere novo, se mudou)
   ou sai; as letras novas viram glifos virtuais; as fronteiras entre palavras viram
   quebras e junções entre os boxes. O que é do passo G (k glifos → 1 letra, que é juntar;
   1 glifo → k letras, que é dividir) recusa a sessão inteira (`Recusa`).
3. **Aplicar** (`aplicar`): as operações em `abbychess.edicao`; os virtuais da sessão são
   ancorados de novo como o usuário os deixou (`_ancorar`), antes de sair qualquer box; e os
   glifos da sessão que têm leitura ficam `revisado` (confirmar é revisar). O texto da
   página depois de confirmar é o digitado.

As figurinas (§6.4): num token de lance que o usuário editou, a letra da peça vira figurina
quando o livro é de figurinas (`figurinas`).
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Set, Tuple

from abbychess import ancoragem as ag
from abbychess import edicao as ed
from abbychess.modelo import Pagina

GLIFO, VIRTUAL, ESPACO, LINHA, OUTRO = "glifo", "virtual", "espaco", "linha", "outro"
#: O que a vista põe no lugar da quebra de parágrafo; o colar de várias linhas também a traz
#: (e o tab colado, que é um espaço).
SEPARADORES = "\n \t"
#: O "gid" de uma letra digitada na sessão, que ainda não tem glifo (o Ctrl+Enter nela).
LETRA_NOVA = -1
#: A mensagem do que é do passo G.
PROXIMA_VERSAO = "este tipo de edição chega numa próxima versão"


@dataclass(frozen=True)
class Unidade:
    """Um caractere da página montada: `gid` é o do glifo (None no espaço, na quebra de
    linha e no diagrama)."""

    texto: str
    gid: Optional[int]
    tipo: str

    @property
    def glifo(self) -> bool:
        return self.tipo in (GLIFO, VIRTUAL)


class Recusa(Exception):
    """A sessão tem uma edição sem tradução ainda (passo G): nada é aplicado."""


# ----------------------------------------------------------------------
# Alinhar
# ----------------------------------------------------------------------

def alinhar(original: str, novo: str, fixos: Sequence[Tuple[int, int]] = ()
            ) -> List[Tuple[Optional[int], Optional[int]]]:
    """Os pares (i no original, j no novo) do alinhamento de menor custo; `None` de um lado
    é inserção ou remoção. No empate, a substituição antes de inserir e apagar, e as
    lacunas o mais à esquerda possível. `fixos`: pares que já se sabe que são o mesmo
    caractere (o que nenhuma edição tocou); o alinhamento passa por eles, e só os vãos entre
    eles são alinhados (os fixos fora de ordem ou de faixa são ignorados)."""
    if not fixos and len(original) * len(novo) > CELULAS_SEM_ANCORAS:
        fixos = _trechos_longos_iguais(original, novo)
    pares: List[Tuple[Optional[int], Optional[int]]] = []
    i0 = j0 = 0
    for i, j in sorted(fixos):
        if not (i0 <= i < len(original) and j0 <= j < len(novo)):
            continue
        pares += [(None if a is None else a + i0, None if b is None else b + j0)
                  for a, b in _levenshtein(original[i0:i], novo[j0:j])]
        pares.append((i, j))
        i0, j0 = i + 1, j + 1
    pares += [(None if a is None else a + i0, None if b is None else b + j0)
              for a, b in _levenshtein(original[i0:], novo[j0:])]
    return pares


#: Acima disto (caracteres do original × do novo), sem fixos, o alinhamento se ancora nas
#: palavras iguais, e um vão ainda maior se alinha numa faixa em volta da diagonal: colar a
#: página inteira por cima custaria segundos no Levenshtein completo.
CELULAS_SEM_ANCORAS = 250_000
#: A folga da faixa, além da diferença de tamanho dos dois lados.
FOLGA_DA_FAIXA = 32


def _trechos_longos_iguais(original: str, novo: str) -> List[Tuple[int, int]]:
    """Os pares de caracteres das palavras iguais nos dois lados, na ordem (um difflib sobre
    as listas de palavras, que são curtas: o de caracteres fica quadrático em texto
    repetitivo)."""
    de = list(re.finditer(r"\S+", original))
    para = list(re.finditer(r"\S+", novo))
    blocos = difflib.SequenceMatcher(None, [t.group(0) for t in de], [t.group(0) for t in para],
                                     autojunk=False).get_matching_blocks()
    pares: List[Tuple[int, int]] = []
    for bloco in blocos:
        for k in range(bloco.size):
            x, y = de[bloco.a + k], para[bloco.b + k]
            pares += [(x.start() + c, y.start() + c) for c in range(len(x.group(0)))]
    return pares


def _troca(a: str, b: str) -> int:
    """O custo de alinhar `a` com `b`: 0 iguais, 1 duas letras; 2 uma letra com o espaço
    (nunca menos que apagar e inserir): trocar o x de "ganhaxtempos" por "r " corrige o
    glifo e insere o espaço, não tira o box para pôr um virtual."""
    if a == b:
        return 0
    return 2 if (a == " ") != (b == " ") else 1


def _levenshtein(original: str, novo: str) -> List[Tuple[Optional[int], Optional[int]]]:
    """O alinhamento de menor custo; grande demais, só numa faixa em volta da diagonal."""
    n, m = len(original), len(novo)
    infinito = n + m + 1
    custo = [[infinito] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        custo[i][0] = i
    for j in range(m + 1):
        custo[0][j] = j
    faixa = abs(n - m) + FOLGA_DA_FAIXA if n * m > CELULAS_SEM_ANCORAS else None
    for i in range(1, n + 1):
        if faixa is None:
            colunas = range(1, m + 1)
        else:
            centro = i * m // n
            colunas = range(max(1, centro - faixa), min(m, centro + faixa) + 1)
        for j in colunas:
            custo[i][j] = min(custo[i - 1][j - 1] + _troca(original[i - 1], novo[j - 1]),
                              custo[i - 1][j] + 1, custo[i][j - 1] + 1)
    pares: List[Tuple[Optional[int], Optional[int]]] = []
    i, j = n, m
    while i or j:
        if i and j and custo[i][j] == custo[i - 1][j - 1] + _troca(original[i - 1], novo[j - 1]):
            pares.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i and custo[i][j] == custo[i - 1][j] + 1:
            pares.append((i - 1, None))
            i -= 1
        else:
            pares.append((None, j - 1))
            j -= 1
    pares.reverse()
    return pares


# ----------------------------------------------------------------------
# Planejar
# ----------------------------------------------------------------------

@dataclass
class Plano:
    """O que a sessão faz na página, em gids."""

    #: gid de box ou virtual -> o caractere novo dele.
    corrigir: Dict[int, str] = field(default_factory=dict)
    #: Os glifos que saem (box: descartado; virtual: apagado).
    sair: Set[int] = field(default_factory=set)
    #: Palavra nova antes destes boxes (o espaço inserido).
    quebrar: Set[int] = field(default_factory=set)
    #: (último, primeiro): as palavras juntadas (o espaço apagado).
    juntar: Set[Tuple[int, int]] = field(default_factory=set)
    #: As letras que faltaram: (letras, âncora, a palavra é nova?), a âncora como
    #: ("depois", gid) ou ("antes", gid).
    virtuais: List[Tuple[str, Tuple[str, Optional[int]], bool]] = field(default_factory=list)
    #: Os glifos da sessão que ficam: `revisado` ao confirmar (os que têm leitura).
    revisar: Set[int] = field(default_factory=set)
    #: O texto novo, item a item: ("glifo", gid) do original que ficou, ("letra", c) sem
    #: glifo ainda, ("espaco", None) e ("linha", None), a quebra de linha impressa que ficou.
    itens: List[Tuple[str, object]] = field(default_factory=list)
    #: gid -> a linha impressa dele no original (0 é a primeira da sessão).
    linha: Dict[int, int] = field(default_factory=dict)
    #: O texto digitado é outro (também quando só um virtual muda de palavra).
    texto_mudou: bool = False
    #: `aplicar` deixou uma linha impressa só com virtuais: ela some (as linhas vêm dos
    #: boxes), e eles vão para a linha vizinha.
    linha_sem_boxes: bool = False
    #: Uma quebra de linha impressa foi apagada: ela fica (as linhas são da página).
    linha_mantida: bool = False
    #: As palavras antes e depois da sessão, para o aviso ("casas → casa: ...").
    de: str = ""
    para: str = ""

    @property
    def muda(self) -> bool:
        return self.texto_mudou or bool(self.corrigir or self.sair or self.quebrar
                                        or self.juntar or self.virtuais)

    def estrutural(self, *extras: str) -> str:
        """O aviso não modal da Linha para o que muda a estrutura (§6.3: "rn → m: 2 glifos
        juntados · Ctrl+Z desfaz"), ou "". `extras` entram antes do "Ctrl+Z desfaz"."""
        partes = []
        if self.sair:
            n = len(self.sair)
            partes.append(f"{n} glifo tirado" if n == 1 else f"{n} glifos tirados")
        letras = sum(len(t) for t, _a, _n in self.virtuais)
        if letras:
            partes.append(f"{letras} glifo virtual" if letras == 1 else f"{letras} glifos virtuais")
        if self.linha_sem_boxes:
            partes.append("a linha ficou sem glifos: o resto dela foi para a vizinha")
        if self.linha_mantida:
            partes.append("a quebra de linha fica (juntar linhas chega numa próxima versão)")
        if not partes:
            return ""
        de, para = _curto(self.de), _curto(self.para)
        return f"{de} → {para}: " + " · ".join(partes + list(extras) + ["Ctrl+Z desfaz"])


def _curto(texto: str, limite: int = 30) -> str:
    return texto if len(texto) <= limite else texto[:limite - 1] + "…"


def _normalizar(novo: str) -> str:
    return "".join(" " if c in SEPARADORES else c for c in novo)


def gid_no_cursor(unidades: Sequence[Unidade], novo: str, onde: int,
                  fixos: Sequence[Tuple[int, int]] = ()) -> Optional[int]:
    """O glifo do original que ficou sob o cursor na posição `onde` do texto novo (o
    caractere antes dele; num espaço, o depois): o do Ctrl+Enter. `LETRA_NOVA` se ali há
    uma letra digitada agora; None se não há glifo."""
    original = "".join(u.texto if u.tipo != LINHA else " " for u in unidades)
    novo = _normalizar(novo)
    por_novo = {j: i for i, j in alinhar(original, novo, fixos) if j is not None}
    for j in (onde - 1, onde):
        if not 0 <= j < len(novo) or novo[j] == " ":
            continue
        i = por_novo.get(j)
        if i is None:
            return LETRA_NOVA
        return unidades[i].gid if unidades[i].glifo else None
    return None


def planejar(unidades: Sequence[Unidade], novo: str,
             fixos: Sequence[Tuple[int, int]] = (), fim_de_linha: bool = False) -> Plano:
    """O plano da sessão: o que fica, o que sai, o que entra, e as fronteiras. `fixos`, os
    pares (no original, no novo) que nenhuma edição tocou (ver `alinhar`); `fim_de_linha`,
    a sessão termina numa quebra de linha impressa (o hífen dela parte uma palavra)."""
    novo = _normalizar(novo)
    original = "".join(u.texto if u.tipo != LINHA else " " for u in unidades)
    pares = alinhar(original, novo, fixos)
    _recusar_o_que_e_do_passo_g(unidades, novo, pares)

    plano = Plano(linha=_linha_original(unidades), texto_mudou=original != novo,
                  de=" ".join(original.split()), para=" ".join(novo.split()))
    itens = plano.itens
    letras_do_gid: Dict[int, List[str]] = {}
    for i, j in pares:
        u = unidades[i] if i is not None else None
        c = novo[j] if j is not None else None
        if u is not None and u.glifo and c is not None and c != " ":
            letras_do_gid.setdefault(u.gid, []).append(c)
            if not itens or itens[-1] != ("glifo", u.gid):
                itens.append(("glifo", u.gid))
            continue
        if u is not None and u.glifo:
            letras_do_gid.setdefault(u.gid, [])     # o caractere saiu (talvez o glifo todo)
        if c is None:
            continue
        if c != " ":
            itens.append(("letra", c))
        else:
            itens.append(("linha", None) if u is not None and u.tipo == LINHA else ("espaco", None))

    for gid, letras in letras_do_gid.items():
        antes = "".join(u.texto for u in unidades if u.gid == gid)
        depois = "".join(letras)
        if not depois:
            plano.sair.add(gid)
        elif depois != antes:
            plano.corrigir[gid] = depois
    _recusar_o_hifen_de_fim_de_linha(unidades, plano.sair, fim_de_linha)
    plano.linha_mantida = any(unidades[i].tipo == LINHA and (j is None or novo[j] != " ")
                              for i, j in pares if i is not None)
    ficam = [gid for item, gid in itens if item == "glifo"]
    if len(ficam) != len(set(ficam)):           # uma letra no meio de "fi": dividir o glifo
        raise Recusa(f"{PROXIMA_VERSAO} (dividir um glifo)")
    plano.revisar = set(ficam)
    _fronteiras(unidades, itens, plano)
    _letras_novas(unidades, itens, plano)
    return plano


def _recusar_o_que_e_do_passo_g(unidades, novo, pares) -> None:
    """Um trecho sem coincidência em que k glifos dão 1 letra (juntar) ou 1 glifo dá k
    letras (dividir): isso é do passo G."""
    def checar(trecho):
        glifos = [i for i, _j in trecho if i is not None and unidades[i].glifo]
        letras = [j for _i, j in trecho if j is not None and novo[j] != " "]
        troca = any(i is not None and j is not None and unidades[i].glifo and novo[j] != " "
                    for i, j in trecho)
        k, n = len({unidades[i].gid for i in glifos}), len(letras)
        if troca and k != n and min(k, n) == 1:
            o_que = "juntar glifos" if k > 1 else "dividir um glifo"
            raise Recusa(f"{PROXIMA_VERSAO} ({o_que})")

    trecho = []
    for i, j in pares:
        igual = (i is not None and j is not None and unidades[i].texto == novo[j]
                 and unidades[i].tipo != LINHA)
        if igual:
            if trecho:
                checar(trecho)
            trecho = []
        else:
            trecho.append((i, j))
    if trecho:
        checar(trecho)


#: Os hífens que partem uma palavra no fim da linha impressa.
HIFENS = "-‐‑"


def _recusar_o_hifen_de_fim_de_linha(unidades, sair, fim_de_linha: bool) -> None:
    """Apagar o hífen do fim de uma linha impressa é juntar as duas metades da palavra
    (§6.3, "hífen de fim de linha apagado"): isso é do passo G, e sem ele o box do hífen sairia
    e a palavra continuaria partida."""
    for k, u in enumerate(unidades):
        no_fim = (unidades[k + 1].tipo == LINHA if k + 1 < len(unidades) else fim_de_linha)
        if u.glifo and u.gid in sair and u.texto in HIFENS and no_fim:
            raise Recusa(f"{PROXIMA_VERSAO} (juntar a palavra partida pelo hífen)")


def _palavras_originais(unidades) -> Dict[int, int]:
    """gid -> o número da palavra dele no original; e a linha impressa de cada palavra."""
    palavra, numero = {}, 0
    for u in unidades:
        if u.glifo:
            palavra[u.gid] = numero
        elif u.tipo in (ESPACO, LINHA):
            numero += 1
    return palavra


def _linha_original(unidades) -> Dict[int, int]:
    linha, numero = {}, 0
    for u in unidades:
        if u.glifo:
            linha[u.gid] = numero
        elif u.tipo == LINHA:
            numero += 1
    return linha


def _fronteiras(unidades, itens, plano: Plano) -> None:
    """Entre dois boxes que ficaram, seguidos no texto novo (os virtuais entre eles não
    contam: `_ancorar` os põe): juntos numa palavra agora e separados antes (espaço apagado:
    junção), ou o contrário (espaço inserido: quebra). As linhas impressas são da página:
    apagar a quebra de linha não junta."""
    palavra, linha = _palavras_originais(unidades), plano.linha
    tipo = {u.gid: u.tipo for u in unidades if u.glifo}
    anterior: Optional[int] = None
    separado = False
    for item, gid in itens:
        if item in ("espaco", "linha"):
            separado = True
            continue
        if item == "letra" or tipo[gid] != GLIFO:
            continue
        if anterior is not None:
            antes_separado = palavra[anterior] != palavra[gid]
            if separado and not antes_separado:
                plano.quebrar.add(gid)
            elif not separado and antes_separado and linha[anterior] == linha[gid]:
                plano.juntar.add((anterior, gid))
        anterior, separado = gid, False


def _letras_novas(unidades, itens, plano: Plano) -> None:
    """Cada sequência de letras novas, como o aviso e a tinta sem box a descrevem: depois do
    glifo que fica antes dela na mesma palavra; sem ele, antes do glifo que vem depois; e a
    palavra toda nova, depois do último glifo antes dela (ou antes do primeiro depois, no
    começo de uma linha). O lugar de verdade é o de `_ancorar`."""
    linha = _linha_original(unidades)
    k = 0
    while k < len(itens):
        if itens[k][0] != "letra":
            k += 1
            continue
        fim = k
        while fim < len(itens) and itens[fim][0] == "letra":
            fim += 1
        letras = "".join(c for _item, c in itens[k:fim])
        antes = itens[k - 1] if k else None
        depois = itens[fim] if fim < len(itens) else None
        if antes is not None and antes[0] == "glifo":
            plano.virtuais.append((letras, ("depois", antes[1]), False))
        elif depois is not None and depois[0] == "glifo":
            plano.virtuais.append((letras, ("antes", depois[1]), False))
        else:                                   # uma palavra nova inteira
            anterior = next((g for item, g in reversed(itens[:k]) if item == "glifo"), None)
            seguinte = next((g for item, g in itens[fim:] if item == "glifo"), None)
            if anterior is not None and (seguinte is None or linha.get(anterior) == linha.get(seguinte)):
                plano.virtuais.append((letras, ("depois", anterior), True))
            elif seguinte is not None:
                plano.virtuais.append((letras, ("antes", seguinte), True))
            else:
                plano.virtuais.append((letras, ("depois", None), True))
        k = fim


# ----------------------------------------------------------------------
# A página como texto (as ferramentas, os testes e a máquina de estados)
# ----------------------------------------------------------------------

def texto_e_unidades(pagina: Pagina) -> Tuple[str, List[Unidade]]:
    """O texto da página como o Documento o mostra (uma linha impressa por parágrafo, os
    não lidos como □, sem os diagramas) e a unidade de cada caractere."""
    from abbychess import texto as tx

    documento = tx.montar(pagina, com_os_nao_lidos=True)
    normal = tx._normalizador(tx.IMPRESSO)
    virtuais = {v.gid for v in pagina.decisoes.virtuais}
    unidades: List[Unidade] = []
    for bloco in documento.blocos:
        for linha in bloco.linhas:
            if unidades:
                unidades.append(Unidade("\n", None, LINHA))
            for n, palavra in enumerate(linha.palavras):
                if n:
                    unidades.append(Unidade(" ", None, ESPACO))
                for g in palavra.gids:
                    char = documento.chars.get(g, "")
                    letras = tx.NAO_LIDO if char == tx.NAO_LIDO else (normal(char) or tx.NAO_LIDO)
                    for letra in letras:
                        unidades.append(Unidade(letra, g, VIRTUAL if g in virtuais else GLIFO))
    return "".join(u.texto for u in unidades), unidades


def palavras_em(unidades: Sequence[Unidade], inicio: int, fim: int) -> Tuple[int, int]:
    """A menor sequência de palavras inteiras que cobre [inicio, fim): estende até o espaço
    (ou a quebra de linha) de cada lado."""
    a, b = max(0, inicio), min(len(unidades), max(fim, inicio))
    while a > 0 and unidades[a - 1].tipo not in (ESPACO, LINHA):
        a -= 1
    while b < len(unidades) and unidades[b].tipo not in (ESPACO, LINHA):
        b += 1
    return a, b


def editar(pagina: Pagina, unidades: Sequence[Unidade], novo: str,
           fixos: Sequence[Tuple[int, int]] = (), fim_de_linha: bool = False) -> Plano:
    """Planeja e aplica (levanta `Recusa` sem mudar nada)."""
    plano = planejar(unidades, novo, fixos, fim_de_linha)
    aplicar(pagina, plano)
    return plano


# ----------------------------------------------------------------------
# Aplicar
# ----------------------------------------------------------------------

def aplicar(pagina: Pagina, plano: Plano) -> None:
    """O plano na página: as letras, as fronteiras, as letras novas (virtuais), os virtuais
    que saem, as âncoras de todos como ficaram no texto, e só então os boxes que saem (já
    não são âncora de ninguém)."""
    virtuais = {v.gid for v in pagina.decisoes.virtuais}
    for gid, char in plano.corrigir.items():
        if gid in virtuais:
            ed.trocar_virtual(pagina, gid, char)
        else:
            ed.corrigir(pagina, gid, char)
    for gid in sorted(plano.quebrar):
        ed.quebrar(pagina, gid)
    sem_quebra = []
    for ultimo, primeiro in sorted(plano.juntar):
        if primeiro in pagina.decisoes.quebras:     # o espaço era uma quebra: ela sai
            pagina.decisoes = replace(pagina.decisoes, quebras=pagina.decisoes.quebras - {primeiro})
            sem_quebra.append((ultimo, primeiro))
        else:
            ed.juntar_palavras(pagina, ultimo, primeiro)
    if sem_quebra:                              # o core também separava ali: junção
        onde, _palavras = ag.pagina_montada(pagina)
        for ultimo, primeiro in sem_quebra:
            if onde.get(ultimo) != onde.get(primeiro):
                ed.juntar_palavras(pagina, ultimo, primeiro)
    sequencia: List[Tuple[str, Optional[int]]] = []
    for item, valor in plano.itens:
        if item == "letra":                     # o lugar dela vem de `_ancorar`
            _d, gid = ed.virtual(pagina, str(valor), None, palavra_nova=True)
            sequencia.append(("glifo", gid))
        else:
            sequencia.append((item, valor))
    for gid in plano.sair & virtuais:
        ed.apagar_virtual(pagina, gid)
    boxes_que_saem = plano.sair - virtuais
    com_box = {lp for lp, p in ag.palavras_da_sequencia(sequencia, plano.linha)
               if any(g not in virtuais and g in pagina.vivos and g not in boxes_que_saem
                      for g in p)}
    plano.linha_sem_boxes = any(lp not in com_box
                                for lp, _p in ag.palavras_da_sequencia(sequencia, plano.linha))
    ag.ancorar(pagina, sequencia, boxes_que_saem, plano.linha)
    antes = ag.pagina_montada(pagina)[0] if boxes_que_saem else {}
    for gid in boxes_que_saem:
        ed.descartar(pagina, gid)
    if boxes_que_saem:                          # só o box tirado deixa um vão na página
        ag.como_digitado(pagina, sequencia, {g for _i, g in sequencia} | set(plano.linha), antes)
    lidos = {b.gid for b in pagina.boxes if b.entry.char}
    ed.revisar(pagina, plano.revisar & lidos)   # o □ e o aguardando ficam na fila


# ----------------------------------------------------------------------
# As figurinas (§6.4)
# ----------------------------------------------------------------------

#: As letras das peças em cada idioma, na ordem rei, dama, torre, bispo, cavalo. O lance
#: estrito do core (`core.notacao.RE_LANCE_ESTRITO`) só conhece as letras do inglês; aqui a
#: forma é a mesma, com as letras do idioma do livro.
PECAS = {"pt": "RDTBC", "en": "KQRBN", "es": "RDTAC", "de": "KDTLS", "fr": "RDTFC"}
FIGURINAS_BRANCAS = "♔♕♖♗♘"
#: A pontuação colada ao lance na prosa: "(Cf3)", "Cf3,", "Cf3." (a de `core.notacao`).
PONTUACAO_DE_BORDA = ",;:.)(\"'“”‘’[]"


def _lance(idioma: str):
    pecas = PECAS.get(idioma, PECAS["en"])
    return re.compile(rf"^(\d{{1,3}}\.(?:\.\.)?)?([{pecas}])([a-h]?[1-8]?x?[a-h][1-8])"
                      rf"(=[{pecas}])?([+#]?[!?]{{0,2}}[±∓⩱⩲=∞]?)$")


def figurinas(token: str, idioma: str) -> str:
    """O token de lance com a letra da peça (e a da promoção) como figurina; os outros
    tokens como vieram. A pontuação de borda fica onde estava."""
    pecas = PECAS.get(idioma, PECAS["en"])
    nucleo = token.lstrip(PONTUACAO_DE_BORDA)
    antes = token[:len(token) - len(nucleo)]
    nucleo = nucleo.rstrip(PONTUACAO_DE_BORDA)
    depois = token[len(antes) + len(nucleo):]
    casou = _lance(idioma).match(nucleo)
    if casou is None:
        return token
    numero, peca, resto, promocao, sinais = casou.groups()
    figura = FIGURINAS_BRANCAS[pecas.index(peca)]
    if promocao:
        promocao = "=" + FIGURINAS_BRANCAS[pecas.index(promocao[1])]
    return f"{antes}{numero or ''}{figura}{resto}{promocao or ''}{sinais}{depois}"


#: As figurinas que a leitura escreve (brancas e pretas).
TODAS_AS_FIGURINAS = frozenset("♔♕♖♗♘♙♚♛♜♝♞♟")


def modo_da_pagina(modo: str, chars) -> str:
    """O modo do livro (§6.4) para a página: "livro" vira "figurinas" se algum glifo dela foi
    lido como figurina, e "letras" se nenhum; os outros modos ficam."""
    if modo != "livro":
        return modo
    return "figurinas" if any(c in TODAS_AS_FIGURINAS for c in chars) else "letras"


def com_figurinas(novo: str, original: str, idioma: str, modo: str) -> str:
    """O texto da sessão com as figurinas nos tokens de lance que o usuário mudou ou
    digitou (§6.4), se o livro é de figurinas; no modo letras, como foi digitado. Os tokens
    que ficaram iguais e no mesmo lugar não mudam (o "Cf3" que o livro imprime assim)."""
    if modo != "figurinas":
        return novo
    tokens = list(re.finditer(r"\S+", novo))
    iguais = set()
    blocos = difflib.SequenceMatcher(None, _normalizar(original).split(),
                                     [t.group(0) for t in tokens], autojunk=False)
    for bloco in blocos.get_matching_blocks():
        iguais.update(range(bloco.b, bloco.b + bloco.size))
    partes, fim = [], 0
    for k, t in enumerate(tokens):
        partes.append(novo[fim:t.start()])
        partes.append(t.group(0) if k in iguais else figurinas(t.group(0), idioma))
        fim = t.end()
    partes.append(novo[fim:])
    return "".join(partes)
