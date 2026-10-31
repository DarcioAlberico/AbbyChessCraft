"""A sessão de edição do Documento (SPEC §6.3 e §6.4): sem Qt.

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
   quebras e junções; k glifos → 1 letra junta boxes e 1 glifo → k letras divide pela tinta
   ou conserva uma caixa multicaractere.
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
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Set, Tuple

from abbychess.modelo import FIGURINAS, PECAS, Pagina

GLIFO, VIRTUAL, ESPACO, LINHA, OUTRO = "glifo", "virtual", "espaco", "linha", "outro"
#: O que a vista põe no lugar da quebra de parágrafo; o colar de várias linhas também a traz
#: (e o tab colado, que é um espaço).
SEPARADORES = "\n \t"
#: O "gid" de uma letra digitada na sessão, que ainda não tem glifo (o Ctrl+Enter nela).
LETRA_NOVA = -1
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
    """A sessão não pode ser aplicada atomicamente: nada é alterado."""


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
        pares += _vao(original[i0:i], novo[j0:j], i0, j0)
        pares.append((i, j))
        i0, j0 = i + 1, j + 1
    pares += _vao(original[i0:], novo[j0:], i0, j0)
    return pares


def _vao(original: str, novo: str, i0: int, j0: int) -> List[Tuple[Optional[int], Optional[int]]]:
    """O alinhamento do vão entre dois fixos, nas posições do texto inteiro (o vão começa em
    `i0` no original e em `j0` no novo)."""
    return [(None if a is None else a + i0, None if b is None else b + j0)
            for a, b in _levenshtein(original, novo)]


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
    return _caminho(_custos(original, novo), original, novo)


def _custos(original: str, novo: str) -> List[Dict[int, int]]:
    """A tabela do Levenshtein (com o custo de `_troca`), linha a linha."""
    n, m = len(original), len(novo)
    infinito = n + m + 1
    faixa = abs(n - m) + FOLGA_DA_FAIXA if n * m > CELULAS_SEM_ANCORAS else None
    # Cada linha guarda só as colunas dela (a faixa inteira, ou só ela): fora, infinito.
    custo: List[Dict[int, int]] = [dict(enumerate(range(m + 1)))]
    for i in range(1, n + 1):
        if faixa is None:
            colunas = range(1, m + 1)
        else:
            centro = i * m // n
            colunas = range(max(1, centro - faixa), min(m, centro + faixa) + 1)
        anterior, linha = custo[i - 1], {0: i}
        for j in colunas:
            linha[j] = min(anterior.get(j - 1, infinito) + _troca(original[i - 1], novo[j - 1]),
                           anterior.get(j, infinito) + 1, linha.get(j - 1, infinito) + 1)
        custo.append(linha)
    return custo


def _caminho(custo: List[Dict[int, int]], original: str, novo: str
             ) -> List[Tuple[Optional[int], Optional[int]]]:
    """Os pares do alinhamento, do fim da tabela ao começo: no empate, a substituição antes
    de apagar, e apagar antes de inserir (as lacunas ficam o mais à esquerda)."""
    pares: List[Tuple[Optional[int], Optional[int]]] = []
    i, j = len(original), len(novo)
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
    #: Operações estruturais do passo G, na ordem em que aparecem no texto.
    juntar_boxes: List[Tuple[Tuple[int, ...], str]] = field(default_factory=list)
    dividir_boxes: List[Tuple[int, str]] = field(default_factory=list)
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
                                        or self.juntar or self.virtuais or self.juntar_boxes
                                        or self.dividir_boxes)

    def estrutural(self, *extras: str) -> str:
        """O aviso não modal da Linha para o que muda a estrutura (§6.3: "rn → m: 2 glifos
        juntados · Ctrl+Z desfaz"), ou "". `extras` entram antes do "Ctrl+Z desfaz"."""
        partes = self._tirados_e_virtuais() + self._juntados_e_divididos() + self._das_linhas()
        if not partes:
            return ""
        de, para = _curto(self.de), _curto(self.para)
        return f"{de} → {para}: " + " · ".join(partes + list(extras) + ["Ctrl+Z desfaz"])

    def _tirados_e_virtuais(self) -> List[str]:
        partes = []
        if self.sair:
            n = len(self.sair)
            partes.append(f"{n} glifo tirado" if n == 1 else f"{n} glifos tirados")
        letras = sum(len(t) for t, _a, _n in self.virtuais)
        if letras:
            partes.append(f"{letras} glifo virtual" if letras == 1 else f"{letras} glifos virtuais")
        return partes

    def _juntados_e_divididos(self) -> List[str]:
        partes = []
        if self.juntar_boxes:
            n = sum(len(gids) for gids, _char in self.juntar_boxes)
            partes.append(f"{n} glifos juntados")
        if self.dividir_boxes:
            n = sum(len(chars) for _gid, chars in self.dividir_boxes)
            partes.append(f"1 glifo dividido em {n}" if len(self.dividir_boxes) == 1
                          else f"{len(self.dividir_boxes)} glifos divididos")
        return partes

    def _das_linhas(self) -> List[str]:
        partes = []
        if self.linha_sem_boxes:
            partes.append("a linha ficou sem glifos: o resto dela foi para a vizinha")
        if self.linha_mantida:
            partes.append("a quebra de linha fica como impressa (o Documento mostra as "
                          "linhas do livro; a exportação junta o parágrafo)")
        return partes


def _curto(texto: str, limite: int = 30) -> str:
    return texto if len(texto) <= limite else texto[:limite - 1] + "…"


def _normalizar(novo: str) -> str:
    return "".join(" " if c in SEPARADORES else c for c in novo)


def gid_no_cursor(unidades: Sequence[Unidade], novo: str, onde: int,
                  fixos: Sequence[Tuple[int, int]] = ()) -> Optional[int]:
    """O glifo do original que ficou sob o cursor na posição `onde` do texto novo (o
    caractere antes dele; num espaço, o depois): o do Ctrl+Enter. `LETRA_NOVA` se ali há
    uma letra digitada agora; None se não há glifo."""
    original = _texto_original(unidades)
    novo = _normalizar(novo)
    por_novo = _por_novo(original, novo, fixos)
    for j in (onde - 1, onde):
        if not 0 <= j < len(novo) or novo[j] == " ":
            continue
        i = por_novo.get(j)
        if i is None:
            return LETRA_NOVA
        return unidades[i].gid if unidades[i].glifo else None
    return None


def _texto_original(unidades: Sequence[Unidade]) -> str:
    """O texto das unidades com a quebra de linha impressa como espaço (como o novo,
    normalizado)."""
    return "".join(u.texto if u.tipo != LINHA else " " for u in unidades)


def _por_novo(original: str, novo: str, fixos) -> Dict[int, int]:
    """j no novo -> i no original, dos caracteres alinhados."""
    return {j: i for i, j in alinhar(original, novo, fixos) if j is not None}


def planejar(unidades: Sequence[Unidade], novo: str,
             fixos: Sequence[Tuple[int, int]] = ()) -> Plano:
    """O plano da sessão: o que fica, o que sai, o que entra, e as fronteiras. `fixos`, os
    pares (no original, no novo) que nenhuma edição tocou (ver `alinhar`). O hífen de fim de
    linha que sai junta a palavra na aplicação (`_hifens_de_fim_de_linha`)."""
    novo = _normalizar(novo)
    original = _texto_original(unidades)
    pares = alinhar(original, novo, fixos)
    plano = Plano(linha=_linha_original(unidades), texto_mudou=original != novo,
                  de=" ".join(original.split()), para=" ".join(novo.split()))
    letras_do_gid = _itens_do_texto_novo(plano, unidades, novo, pares)
    _corrigir_e_tirar(plano, unidades, letras_do_gid)
    # A linha física continua no Documento; sem o box do hífen, a exportação poderá
    # refluir as duas metades da palavra sem reintroduzi-lo.
    plano.linha_mantida = _linha_apagada(unidades, novo, pares)
    _dividir_ligaduras_repetidas(plano, plano.itens, unidades, novo, pares)
    plano.revisar = {gid for item, gid in plano.itens if item == "glifo"}
    itens_do_original = _itens_do_original(plano)
    _fronteiras(unidades, itens_do_original, plano)
    _letras_novas(unidades, itens_do_original, plano)
    return plano


def _itens_do_texto_novo(plano: Plano, unidades, novo: str, pares) -> Dict[int, List[str]]:
    """Os itens do texto novo em `plano.itens`, na ordem dos pares (as operações estruturais
    no lugar do primeiro par delas); devolve as letras que cada glifo do original tem agora
    (vazio: saiu)."""
    estruturais, cobertos_i, cobertos_j = _operacoes_estruturais(unidades, novo, pares)
    primeiros = {min(posicoes): (tipo, dados) for tipo, dados, posicoes in estruturais}
    cobertos = _posicoes_cobertas(pares, cobertos_i, cobertos_j)
    letras_do_gid: Dict[int, List[str]] = {}
    for posicao, (i, j) in enumerate(pares):
        if posicao in primeiros:
            _item_estrutural(plano, *primeiros[posicao])
        if posicao not in cobertos:
            _item(plano.itens, letras_do_gid, unidades[i] if i is not None else None,
                  novo[j] if j is not None else None)
    return letras_do_gid


def _posicoes_cobertas(pares, cobertos_i: Set[int], cobertos_j: Set[int]) -> Set[int]:
    """Os pares que uma operação estrutural já cobre (de um lado ou do outro)."""
    return {p for p, (i, j) in enumerate(pares)
            if (i is not None and i in cobertos_i) or (j is not None and j in cobertos_j)}


def _item_estrutural(plano: Plano, tipo: str, dados) -> None:
    """A junção ou a divisão de boxes no plano, e o item dela no texto novo."""
    if tipo == "juntar":
        indice = len(plano.juntar_boxes)
        plano.juntar_boxes.append(dados)
    else:
        indice = len(plano.dividir_boxes)
        plano.dividir_boxes.append(dados)
    plano.itens.append((tipo, indice))


def _item(itens: list, letras_do_gid: Dict[int, List[str]], u: Optional[Unidade],
          c: Optional[str]) -> None:
    """O par (a unidade do original, o caractere do novo) nos itens: a letra no glifo que
    fica, ou o glifo que perdeu o caractere; e a letra nova, o espaço ou a quebra de linha."""
    if u is not None and u.glifo:
        if c is not None and c != " ":
            _letra_no_glifo(itens, letras_do_gid, u.gid, c)
            return
        letras_do_gid.setdefault(u.gid, [])     # o caractere saiu (talvez o glifo todo)
    if c is not None:
        itens.append(_item_novo(u, c))


def _letra_no_glifo(itens: list, letras_do_gid: Dict[int, List[str]], gid: int, c: str) -> None:
    letras_do_gid.setdefault(gid, []).append(c)
    if not itens or itens[-1] != ("glifo", gid):
        itens.append(("glifo", gid))


def _item_novo(u: Optional[Unidade], c: str) -> Tuple[str, Optional[str]]:
    """A letra sem glifo, ou o separador: a quebra de linha impressa que ficou, ou o espaço."""
    if c != " ":
        return ("letra", c)
    return ("linha", None) if u is not None and u.tipo == LINHA else ("espaco", None)


def _corrigir_e_tirar(plano: Plano, unidades, letras_do_gid: Dict[int, List[str]]) -> None:
    """O glifo sem letras sai; o que tem outras letras é corrigido."""
    texto_do_gid: Dict[int, str] = {}           # uma passada (a página inteira, no D2)
    for u in unidades:
        if u.glifo:
            texto_do_gid[u.gid] = texto_do_gid.get(u.gid, "") + u.texto
    for gid, letras in letras_do_gid.items():
        antes = texto_do_gid.get(gid, "")
        depois = "".join(letras)
        if not depois:
            plano.sair.add(gid)
        elif depois != antes:
            plano.corrigir[gid] = depois


def _linha_apagada(unidades, novo: str, pares) -> bool:
    """Alguma quebra de linha impressa saiu, ou virou outra coisa que não o espaço."""
    return any(unidades[i].tipo == LINHA and (j is None or novo[j] != " ")
               for i, j in pares if i is not None)


def _itens_do_original(plano: Plano) -> List[Tuple[str, object]]:
    """Os itens com cada operação estrutural no lugar do primeiro glifo do original dela."""
    itens_do_original = []
    for item, valor in plano.itens:
        if item == "juntar":
            itens_do_original.append(("glifo", plano.juntar_boxes[valor][0][0]))
        elif item == "dividir":
            itens_do_original.append(("glifo", plano.dividir_boxes[valor][0]))
        else:
            itens_do_original.append((item, valor))
    return itens_do_original


def _dividir_ligaduras_repetidas(plano, itens, unidades, novo, pares) -> None:
    """Uma inserção no meio de um box multicaractere transforma-o em ``1 -> k``."""
    vezes = Counter(v for t, v in itens if t == "glifo")      # uma passada: a página inteira
    repetidos = [gid for gid, n in vezes.items() if n > 1]
    for gid in repetidos:
        posicoes = [p for p, (i, _j) in enumerate(pares)
                    if i is not None and unidades[i].glifo and unidades[i].gid == gid]
        if not posicoes:
            continue
        js = [j for _i, j in pares[posicoes[0]:posicoes[-1] + 1]
              if j is not None and novo[j] != " "]
        chars = "".join(novo[j] for j in js)
        primeiro = next(k for k, x in enumerate(itens) if x == ("glifo", gid))
        ultimo = len(itens) - 1 - next(k for k, x in enumerate(reversed(itens))
                                      if x == ("glifo", gid))
        if chars and all(t in ("glifo", "letra") for t, _v in itens[primeiro:ultimo + 1]):
            indice = len(plano.dividir_boxes)
            plano.dividir_boxes.append((gid, chars))
            itens[primeiro:ultimo + 1] = [("dividir", indice)]


def _operacoes_estruturais(unidades, novo, pares):
    """Extrai os trechos desalinhados ``k -> 1`` e ``1 -> k`` entre âncoras iguais."""
    operacoes, cobertos_i, cobertos_j = [], set(), set()
    for posicoes in _trechos_desalinhados(unidades, novo, pares):
        operacao = _operacao_do_trecho([pares[p] for p in posicoes], unidades, novo)
        if operacao is None:
            continue
        tipo, dados, indices, js = operacao
        operacoes.append((tipo, dados, tuple(posicoes)))
        cobertos_i.update(indices)
        cobertos_j.update(js)
    return operacoes, cobertos_i, cobertos_j


def _trechos_desalinhados(unidades, novo: str, pares):
    """As posições de cada trecho de pares seguidos que não são o mesmo caractere."""
    trecho = []
    for p, (i, j) in enumerate(pares):
        if _mesmo_caractere(unidades, novo, i, j):
            if trecho:
                yield trecho
            trecho = []
        else:
            trecho.append(p)
    if trecho:
        yield trecho


def _mesmo_caractere(unidades, novo: str, i: Optional[int], j: Optional[int]) -> bool:
    """O par é o mesmo caractere dos dois lados (a quebra de linha impressa nunca é)."""
    return (i is not None and j is not None and unidades[i].texto == novo[j]
            and unidades[i].tipo != LINHA)


def _operacao_do_trecho(trecho, unidades, novo: str):
    """(tipo, dados, índices dos glifos, posições das letras) do trecho que é ``k -> 1``
    (juntar boxes) ou ``1 -> k`` (dividir um box); None se ele não é nenhum dos dois."""
    indices = _glifos_do_trecho(trecho, unidades)
    js = _letras_do_trecho(trecho, novo)
    gids = tuple(dict.fromkeys(unidades[i].gid for i in indices))
    letras = "".join(novo[j] for j in js)
    tipo = _tipo_estrutural(len(gids), len(letras))
    if tipo is None or not all(unidades[i].tipo == GLIFO for i in indices):
        return None
    dados = (gids, letras) if tipo == "juntar" else (gids[0], letras)
    return tipo, dados, indices, js


def _glifos_do_trecho(trecho, unidades) -> List[int]:
    return [i for i, _j in trecho if i is not None and unidades[i].glifo]


def _letras_do_trecho(trecho, novo: str) -> List[int]:
    return [j for _i, j in trecho if j is not None and novo[j] != " "]


def _tipo_estrutural(n_gids: int, n_letras: int) -> Optional[str]:
    """k glifos -> 1 letra junta; 1 glifo -> k letras divide."""
    if n_gids > 1 and n_letras == 1:
        return "juntar"
    if n_gids == 1 and n_letras > 1:
        return "dividir"
    return None


def _palavras_originais(unidades) -> Dict[int, int]:
    """gid -> o número da palavra dele no original."""
    return _contados(unidades, (ESPACO, LINHA))


def _linha_original(unidades) -> Dict[int, int]:
    """gid -> o número da linha impressa dele no original."""
    return _contados(unidades, (LINHA,))


def _contados(unidades, separadores) -> Dict[int, int]:
    """gid -> quantos `separadores` vêm antes do glifo dele."""
    numero_de, numero = {}, 0
    for u in unidades:
        if u.glifo:
            numero_de[u.gid] = numero
        elif u.tipo in separadores:
            numero += 1
    return numero_de


def _fronteiras(unidades, itens, plano: Plano) -> None:
    """Entre dois boxes que ficaram, seguidos no texto novo (os virtuais entre eles não
    contam: `_ancorar` os põe): juntos numa palavra agora e separados antes (espaço apagado:
    junção), ou o contrário (espaço inserido: quebra). As linhas impressas são da página:
    apagar a quebra de linha não junta."""
    palavra = _palavras_originais(unidades)
    tipo = {u.gid: u.tipo for u in unidades if u.glifo}
    anterior: Optional[int] = None
    separado = False
    for item, gid in itens:
        if item in ("espaco", "linha"):
            separado = True
            continue
        if item == "letra" or tipo[gid] != GLIFO:
            continue
        _fronteira(plano, palavra, anterior, gid, separado)
        anterior, separado = gid, False


def _fronteira(plano: Plano, palavra: Dict[int, int], anterior: Optional[int], gid: int,
               separado: bool) -> None:
    """A fronteira entre o box `anterior` e o `gid`, seguidos no texto novo (separados por
    espaço ou não): a quebra ou a junção, se ela mudou."""
    if anterior is None:
        return
    antes_separado = palavra[anterior] != palavra[gid]
    if separado and not antes_separado:
        plano.quebrar.add(gid)
    elif not separado and antes_separado and plano.linha[anterior] == plano.linha[gid]:
        plano.juntar.add((anterior, gid))


def _letras_novas(unidades, itens, plano: Plano) -> None:
    """Cada sequência de letras novas, como o aviso e a tinta sem box a descrevem: depois do
    glifo que fica antes dela na mesma palavra; sem ele, antes do glifo que vem depois; e a
    palavra toda nova, depois do último glifo antes dela (ou antes do primeiro depois, no
    começo de uma linha). O lugar de verdade é o de `_ancorar`."""
    linha = _linha_original(unidades)
    for k, fim in _sequencias_de_letras(itens):
        letras = "".join(c for _item, c in itens[k:fim])
        plano.virtuais.append((letras, *_ancora_das_letras(itens, k, fim, linha)))


def _sequencias_de_letras(itens):
    """(começo, fim) de cada sequência de itens "letra" seguidos."""
    k = 0
    while k < len(itens):
        if itens[k][0] != "letra":
            k += 1
            continue
        fim = k
        while fim < len(itens) and itens[fim][0] == "letra":
            fim += 1
        yield k, fim
        k = fim


def _ancora_das_letras(itens, k: int, fim: int, linha: Dict[int, int]):
    """(a âncora, a palavra é nova?) das letras `itens[k:fim]`: o glifo logo antes delas ou,
    sem ele, o logo depois; sem os dois, a de uma palavra nova inteira."""
    antes = itens[k - 1] if k else None
    depois = itens[fim] if fim < len(itens) else None
    if antes is not None and antes[0] == "glifo":
        return ("depois", antes[1]), False
    if depois is not None and depois[0] == "glifo":
        return ("antes", depois[1]), False
    return _ancora_da_palavra_nova(itens, k, fim, linha), True


def _ancora_da_palavra_nova(itens, k: int, fim: int, linha: Dict[int, int]):
    """Depois do último glifo antes dela, se ele está na linha do primeiro depois (ou se não
    há glifo depois); senão, antes do primeiro depois; sem glifo nenhum, no começo."""
    anterior, seguinte = _glifos_em_volta(itens, k, fim)
    if anterior is not None and (seguinte is None or linha.get(anterior) == linha.get(seguinte)):
        return ("depois", anterior)
    if seguinte is not None:
        return ("antes", seguinte)
    return ("depois", None)


def _glifos_em_volta(itens, k: int, fim: int) -> Tuple[Optional[int], Optional[int]]:
    """O último glifo antes de `itens[k:fim]` e o primeiro depois (None: não há)."""
    anterior = next((g for item, g in reversed(itens[:k]) if item == "glifo"), None)
    seguinte = next((g for item, g in itens[fim:] if item == "glifo"), None)
    return anterior, seguinte


# ----------------------------------------------------------------------
# A página como texto (as ferramentas, os testes e a máquina de estados)
# ----------------------------------------------------------------------

def texto_e_unidades(pagina: Pagina) -> Tuple[str, List[Unidade]]:
    """O texto da página como o Documento o mostra (uma linha impressa por parágrafo, os
    não lidos como □, sem os diagramas) e a unidade de cada caractere."""
    from abbychess import texto as tx

    documento = tx.montar(pagina, com_os_nao_lidos=True)
    normal = tx.normalizador(tx.IMPRESSO)
    virtuais = {v.gid for v in pagina.decisoes.virtuais}
    unidades: List[Unidade] = []

    def da_palavra(palavra) -> None:
        """Uma unidade por letra de cada glifo (a ligadura tem várias, o não lido é □)."""
        for g in palavra.gids:
            char = documento.chars.get(g, "")
            letras = tx.NAO_LIDO if char == tx.NAO_LIDO else (normal(char) or tx.NAO_LIDO)
            for letra in letras:
                unidades.append(Unidade(letra, g, VIRTUAL if g in virtuais else GLIFO))

    def da_linha(linha) -> None:
        for n, palavra in enumerate(linha.palavras):
            if n:
                unidades.append(Unidade(" ", None, ESPACO))
            da_palavra(palavra)

    for bloco in documento.blocos:
        for linha in bloco.linhas:
            if unidades:
                unidades.append(Unidade("\n", None, LINHA))
            da_linha(linha)
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
           fixos: Sequence[Tuple[int, int]] = ()) -> Plano:
    """Planeja e aplica."""
    plano = planejar(unidades, novo, fixos)
    aplicar(pagina, plano)
    return plano


# ----------------------------------------------------------------------
# Aplicar
# ----------------------------------------------------------------------

def _hifens_de_fim_de_linha(pagina: Pagina, saem, onde) -> List[Tuple[int, int]]:
    """(a letra antes do hífen, a primeira da linha seguinte) de cada hífen que sai e era o
    último glifo da linha dele: a palavra partida pela quebra se junta (§6.3, "junta a
    palavra e remove `hifen_de_quebra`"; antes, a exportação saía "exem plo")."""
    if not saem or not onde:
        return []
    por_linha = _gids_por_linha(onde)
    ordem = {gid: i for i, gid in enumerate(onde)}
    saida = []
    for gid in saem:
        if not _hifen_que_sai(pagina, gid, onde):
            continue
        juncao = _juncao_do_hifen(gid, onde, por_linha, ordem)
        if juncao is not None:
            saida.append(juncao)
    return saida


def _gids_por_linha(onde) -> Dict[Tuple[int, int], List[int]]:
    """(bloco, linha) -> os gids dela."""
    por_linha: Dict[Tuple[int, int], List[int]] = {}
    for gid, (b, n, _k) in onde.items():
        por_linha.setdefault((b, n), []).append(gid)
    return por_linha


def _hifen_que_sai(pagina: Pagina, gid: int, onde) -> bool:
    """O glifo que sai é um hífen (ou o hífen discricionário) da página montada."""
    box = pagina.box(gid) if gid in pagina.vivos else None
    return box is not None and box.entry.char in ("-", "\u00ad") and gid in onde


def _juncao_do_hifen(gid: int, onde, por_linha, ordem) -> Optional[Tuple[int, int]]:
    """(a letra antes do hífen, a primeira da linha seguinte), se o hífen é o último glifo da
    linha, colado na palavra, e há uma linha depois; senão None."""
    b, n, k = onde[gid]
    linha = sorted(por_linha[(b, n)], key=ordem.__getitem__)
    seguinte = sorted(por_linha.get((b, n + 1), []), key=ordem.__getitem__)
    if linha[-1] != gid or len(linha) < 2 or not seguinte:
        return None
    if onde.get(linha[-2], (None, None, None))[2] != k:
        return None                             # um travessão solto ("velha -") não parte palavra
    return (linha[-2], seguinte[0])


def aplicar(pagina: Pagina, plano: Plano, imagem=None, leitor=None) -> None:
    """O plano na página: as letras, as fronteiras, as letras novas (virtuais), os virtuais
    que saem, as âncoras de todos como ficaram no texto, e só então os boxes que saem (já
    não são âncora de ninguém)."""
    # Aqui, e não no topo: `edicao` traz o core de segmentação (cv2, numpy), que o índice da
    # busca, num processo à parte, não precisa (§7.3).
    from abbychess import ancoragem as ag
    from abbychess import edicao as ed

    sucessores_estruturais, sucessor = _aplicar_estruturais(pagina, plano, imagem, leitor)

    def primeiro(gid: int) -> int:
        return sucessor.get(gid, (gid, gid))[0]

    def ultimo_de(gid: int) -> int:
        return sucessor.get(gid, (gid, gid))[1]

    virtuais = {v.gid for v in pagina.decisoes.virtuais}
    _corrigir(pagina, plano.corrigir, virtuais)
    for gid in sorted(plano.quebrar):
        ed.quebrar(pagina, primeiro(gid))
    _juntar_as_palavras(pagina, [(ultimo_de(a), primeiro(b)) for a, b in sorted(plano.juntar)])
    sequencia = _sequencia_digitada(pagina, plano.itens, sucessores_estruturais)
    for gid in plano.sair & virtuais:
        ed.apagar_virtual(pagina, gid)
    boxes_que_saem = plano.sair - virtuais
    plano.linha_sem_boxes = _linha_sem_boxes(pagina, sequencia, plano.linha, virtuais,
                                             boxes_que_saem)
    ag.ancorar(pagina, sequencia, boxes_que_saem, plano.linha)
    _tirar_os_boxes(pagina, sequencia, boxes_que_saem, plano.linha)
    lidos = {b.gid for b in pagina.boxes if b.entry.char}
    ed.revisar(pagina, plano.revisar & lidos)   # o □ e o aguardando ficam na fila


def _aplicar_estruturais(pagina: Pagina, plano: Plano, imagem, leitor):
    """Junta e divide os boxes do plano. Devolve os gids novos de cada operação e, de cada gid
    aposentado, (o primeiro sucessor, o último): a quebra e a junção de palavras do mesmo
    plano citam os gids de antes ("rn b" -> "mb" junta os boxes e a palavra)."""
    from abbychess import edicao as ed

    sucessores_estruturais = {}
    sucessor: Dict[int, Tuple[int, int]] = {}
    for indice, (gids, char) in enumerate(plano.juntar_boxes):
        dif = ed.juntar_varios(pagina, gids, char)
        sucessores_estruturais[("juntar", indice)] = [dif.novos[0].gid]
        for gid in gids:
            sucessor[gid] = (dif.novos[0].gid, dif.novos[0].gid)
    for indice, (gid, chars) in enumerate(plano.dividir_boxes):
        dif = ed.dividir_em(pagina, imagem, gid, chars, leitor)
        sucessores_estruturais[("dividir", indice)] = [b.gid for b in dif.novos]
        sucessor[gid] = (dif.novos[0].gid, dif.novos[-1].gid)
    return sucessores_estruturais, sucessor


def _corrigir(pagina: Pagina, corrigir: Dict[int, str], virtuais: Set[int]) -> None:
    from abbychess import edicao as ed

    for gid, char in corrigir.items():
        if gid in virtuais:
            ed.trocar_virtual(pagina, gid, char)
        else:
            ed.corrigir(pagina, gid, char)


def _juntar_as_palavras(pagina: Pagina, juntas: List[Tuple[int, int]]) -> None:
    """As junções (último, primeiro), já nos gids de agora. O espaço que era uma quebra só
    tira a quebra; onde o core também separava, entra a junção."""
    from abbychess import ancoragem as ag
    from abbychess import edicao as ed

    sem_quebra = []
    for ultimo, comeco in juntas:
        if comeco in pagina.decisoes.quebras:       # o espaço era uma quebra: ela sai
            pagina.decisoes = replace(pagina.decisoes, quebras=pagina.decisoes.quebras - {comeco})
            sem_quebra.append((ultimo, comeco))
        else:
            ed.juntar_palavras(pagina, ultimo, comeco)
    if sem_quebra:                              # o core também separava ali: junção
        onde, _palavras = ag.pagina_montada(pagina)
        for ultimo, comeco in sem_quebra:
            if onde.get(ultimo) != onde.get(comeco):
                ed.juntar_palavras(pagina, ultimo, comeco)


def _sequencia_digitada(pagina: Pagina, itens, sucessores_estruturais
                        ) -> List[Tuple[str, Optional[int]]]:
    """Os itens do texto novo em gids de agora: cada letra nova vira um virtual (o lugar dele
    vem de `_ancorar`), e cada operação estrutural, os boxes que ela criou."""
    from abbychess import edicao as ed

    sequencia: List[Tuple[str, Optional[int]]] = []
    for item, valor in itens:
        if item == "letra":                     # o lugar dela vem de `_ancorar`
            _d, gid = ed.virtual(pagina, str(valor), None, palavra_nova=True)
            sequencia.append(("glifo", gid))
        elif item in ("juntar", "dividir"):
            sequencia.extend(("glifo", gid) for gid in sucessores_estruturais[(item, valor)])
        else:
            sequencia.append((item, valor))
    return sequencia


def _linha_sem_boxes(pagina: Pagina, sequencia, linha, virtuais: Set[int],
                     boxes_que_saem: Set[int]) -> bool:
    """Alguma linha impressa do texto novo fica só com virtuais (sem box que fica)."""
    from abbychess import ancoragem as ag

    vivos = pagina.vivos
    com_box = {lp for lp, p in ag.palavras_da_sequencia(sequencia, linha)
               if any(g not in virtuais and g in vivos and g not in boxes_que_saem
                      for g in p)}
    return any(lp not in com_box for lp, _p in ag.palavras_da_sequencia(sequencia, linha))


def _tirar_os_boxes(pagina: Pagina, sequencia, boxes_que_saem: Set[int], linha) -> None:
    """Descarta os boxes que saem (já não são âncora de ninguém), junta a palavra partida pelo
    hífen de fim de linha que saiu e fecha o vão que o box tirado deixa."""
    from abbychess import ancoragem as ag
    from abbychess import edicao as ed

    antes = ag.pagina_montada(pagina)[0] if boxes_que_saem else {}
    juntar_a_palavra = _hifens_de_fim_de_linha(pagina, boxes_que_saem, antes)
    for gid in boxes_que_saem:
        ed.descartar(pagina, gid)
    _juntar_os_hifens(pagina, juntar_a_palavra)
    if boxes_que_saem:                          # só o box tirado deixa um vão na página
        ag.como_digitado(pagina, sequencia, {g for _i, g in sequencia} | set(linha), antes)


def _juntar_os_hifens(pagina: Pagina, juntar_a_palavra: List[Tuple[int, int]]) -> None:
    from abbychess import edicao as ed

    for ultimo, primeiro in juntar_a_palavra:     # §6.3: apagar o hífen junta a palavra
        if ultimo in pagina.vivos and primeiro in pagina.vivos:
            ed.juntar_palavras(pagina, ultimo, primeiro)


# ----------------------------------------------------------------------
# As figurinas (§6.4)
# ----------------------------------------------------------------------

#: O lance estrito do core (`core.notacao.RE_LANCE_ESTRITO`) só conhece as letras do inglês;
#: aqui a forma é a mesma, com as letras do idioma do livro (`modelo.PECAS`).
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


def modo_da_pagina(modo: str, chars) -> str:
    """O modo do livro (§6.4) para a página: "livro" vira "figurinas" se algum glifo dela foi
    lido como figurina, e "letras" se nenhum; os outros modos ficam."""
    if modo != "livro":
        return modo
    return "figurinas" if any(c in FIGURINAS for c in chars) else "letras"


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
