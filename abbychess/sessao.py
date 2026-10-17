"""A sessão de edição do Documento (SPEC §6.3, as linhas do passo D1; §6.4): sem Qt.

A vista guarda, de cada caractere da página montada, a `Unidade` dele: o glifo (box ou
virtual), o espaço entre palavras, a quebra de linha impressa ou outra coisa (o diagrama).
Uma sessão é a menor sequência de palavras inteiras que as edições tocaram: as unidades
dela e o texto que ela tem agora. Confirmar a sessão é:

1. **Realinhar** o texto de agora contra o original (`alinhar`: Levenshtein; no empate, a
   substituição antes de inserir e apagar, e o alinhamento à esquerda). Teclas, IME, colar,
   arrastar e autocompletar dão o mesmo resultado, porque só o texto final conta.
2. **Planejar** (`planejar`): cada glifo do original fica (com o caractere novo, se mudou)
   ou sai; as letras novas viram glifos virtuais, ancorados no glifo vizinho; as fronteiras
   entre palavras viram quebras e junções. O que é do passo G (k glifos → 1 letra, que é
   juntar; 1 glifo → k letras, que é dividir) recusa a sessão inteira (`Recusa`).
3. **Aplicar** (`aplicar`): as operações em `abbychess.edicao`, numa ordem que mantém as
   âncoras vivas, e todos os glifos da sessão `revisado` (confirmar é revisar).

As figurinas (§6.4): num token de lance que o usuário editou, a letra da peça vira figurina
quando o livro é de figurinas (`figurinas`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Set, Tuple

from abbychess import edicao as ed
from abbychess.modelo import Pagina

GLIFO, VIRTUAL, ESPACO, LINHA, OUTRO = "glifo", "virtual", "espaco", "linha", "outro"
#: O que a vista põe no lugar da quebra de parágrafo; o colar de várias linhas também a traz.
SEPARADORES = "\n "
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

def alinhar(original: str, novo: str) -> List[Tuple[Optional[int], Optional[int]]]:
    """Os pares (i no original, j no novo) do alinhamento de menor custo; `None` de um lado
    é inserção ou remoção. No empate, a substituição antes de inserir e apagar, e as
    lacunas o mais à esquerda possível."""
    n, m = len(original), len(novo)
    custo = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        custo[i][0] = i
    for j in range(1, m + 1):
        custo[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            custo[i][j] = min(custo[i - 1][j - 1] + (original[i - 1] != novo[j - 1]),
                              custo[i - 1][j] + 1, custo[i][j - 1] + 1)
    pares: List[Tuple[Optional[int], Optional[int]]] = []
    i, j = n, m
    while i or j:
        if i and j and custo[i][j] == custo[i - 1][j - 1] + (original[i - 1] != novo[j - 1]):
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
    #: Os glifos da sessão que ficam: todos `revisado` ao confirmar.
    revisar: Set[int] = field(default_factory=set)
    #: As palavras como o usuário as digitou, em gids dos glifos que ficam: tirar um glifo
    #: do meio deixa um vão na página, e o core partiria a palavra ali (`aplicar` junta).
    palavras: List[List[int]] = field(default_factory=list)

    @property
    def muda(self) -> bool:
        return bool(self.corrigir or self.sair or self.quebrar or self.juntar or self.virtuais)

    def estrutural(self) -> str:
        """O aviso não modal da Linha para o que muda a estrutura (§6.3), ou ""."""
        partes = []
        if self.sair:
            partes.append(f"{len(self.sair)} glifo(s) tirado(s)")
        letras = sum(len(t) for t, _a, _n in self.virtuais)
        if letras:
            partes.append(f"{letras} glifo(s) virtual(is)")
        return " · ".join(partes + ["Ctrl+Z desfaz"]) if partes else ""


def _normalizar(novo: str) -> str:
    return "".join(" " if c in SEPARADORES else c for c in novo)


def planejar(unidades: Sequence[Unidade], novo: str) -> Plano:
    """O plano da sessão: o que fica, o que sai, o que entra, e as fronteiras."""
    novo = _normalizar(novo)
    original = "".join(u.texto if u.tipo != LINHA else " " for u in unidades)
    pares = alinhar(original, novo)
    _recusar_o_que_e_do_passo_g(unidades, novo, pares)

    plano = Plano()
    # O texto novo, item a item: o glifo do original que ficou ali (com a letra nova), a
    # letra nova sem glifo (None) ou o espaço.
    itens: List[Tuple[str, Optional[int]]] = []     # ("glifo", gid) / ("letra", None) / ("espaco", None)
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
        itens.append(("espaco", None) if c == " " else ("letra", c))

    for gid, letras in letras_do_gid.items():
        antes = "".join(u.texto for u in unidades if u.gid == gid)
        depois = "".join(letras)
        if not depois:
            plano.sair.add(gid)
        elif depois != antes:
            plano.corrigir[gid] = depois
    vivos = [gid for kind, gid in itens if kind == "glifo"]
    plano.revisar = {g for g in vivos if g is not None}
    palavra: List[int] = []
    for kind, gid in itens + [("espaco", None)]:
        if kind == "glifo" and gid not in plano.sair:
            palavra.append(gid)
        elif kind == "espaco" and palavra:
            plano.palavras.append(palavra)
            palavra = []

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
    """Entre dois glifos que ficaram, seguidos no texto novo: juntos numa palavra agora e
    separados antes (espaço apagado: junção), ou o contrário (espaço inserido: quebra)."""
    palavra, linha = _palavras_originais(unidades), _linha_original(unidades)
    tipo = {u.gid: u.tipo for u in unidades if u.glifo}
    anterior: Optional[int] = None
    separado = False
    for kind, gid in itens:
        if kind == "espaco":
            separado = True
            continue
        if kind == "letra":
            continue
        if anterior is not None:
            antes_separado = palavra[anterior] != palavra[gid]
            if separado and not antes_separado:
                if tipo[gid] != GLIFO:
                    raise Recusa(f"{PROXIMA_VERSAO} (separar antes de um glifo virtual)")
                plano.quebrar.add(gid)
            elif not separado and antes_separado:
                if linha[anterior] != linha[gid]:
                    pass                        # as linhas impressas são da página
                elif tipo[anterior] != GLIFO or tipo[gid] != GLIFO:
                    raise Recusa(f"{PROXIMA_VERSAO} (juntar com um glifo virtual)")
                else:
                    plano.juntar.add((anterior, gid))
        anterior, separado = gid, False


def _letras_novas(unidades, itens, plano: Plano) -> None:
    """Cada sequência de letras novas numa palavra do texto novo vira glifos virtuais,
    ancorados no glifo que fica antes dela na mesma palavra; sem ele, antes do glifo que
    vem depois; e a palavra toda nova, depois do último glifo antes dela (ou antes do
    primeiro depois, no começo de uma linha)."""
    linha = _linha_original(unidades)
    k = 0
    while k < len(itens):
        if itens[k][0] != "letra":
            k += 1
            continue
        fim = k
        while fim < len(itens) and itens[fim][0] == "letra":
            fim += 1
        letras = "".join(c for _kind, c in itens[k:fim])
        antes = itens[k - 1] if k else None
        depois = itens[fim] if fim < len(itens) else None
        if antes is not None and antes[0] == "glifo":
            plano.virtuais.append((letras, ("depois", antes[1]), False))
        elif depois is not None and depois[0] == "glifo":
            plano.virtuais.append((letras, ("antes", depois[1]), False))
        else:                                   # uma palavra nova inteira
            anterior = next((g for kind, g in reversed(itens[:k]) if kind == "glifo"), None)
            seguinte = next((g for kind, g in itens[fim:] if kind == "glifo"), None)
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


def editar(pagina: Pagina, unidades: Sequence[Unidade], novo: str) -> Plano:
    """Planeja e aplica (levanta `Recusa` sem mudar nada)."""
    plano = planejar(unidades, novo)
    aplicar(pagina, plano)
    return plano


# ----------------------------------------------------------------------
# Aplicar
# ----------------------------------------------------------------------

def aplicar(pagina: Pagina, plano: Plano) -> None:
    """O plano na página, numa ordem que mantém as âncoras vivas: as letras, as fronteiras,
    as letras novas (ancoradas em glifos que ficam), e só então o que sai."""
    virtuais = {v.gid for v in pagina.decisoes.virtuais}
    for gid, char in plano.corrigir.items():
        if gid in virtuais:
            ed.trocar_virtual(pagina, gid, char)
        else:
            ed.corrigir(pagina, gid, char)
    for gid in sorted(plano.quebrar):
        ed.quebrar(pagina, gid)
    for ultimo, primeiro in sorted(plano.juntar):
        if primeiro in pagina.decisoes.quebras:     # o espaço era uma quebra: ela sai
            pagina.decisoes = replace(pagina.decisoes, quebras=pagina.decisoes.quebras - {primeiro})
        else:
            ed.juntar_palavras(pagina, ultimo, primeiro)
    for letras, (lado, ancora), nova in plano.virtuais:
        anterior: Optional[int] = None
        for n, letra in enumerate(letras):
            if n:
                _d, anterior = ed.virtual(pagina, letra, anterior)
            elif lado == "antes":
                _d, anterior = ed.virtual(pagina, letra, None, palavra_nova=nova, antes_de=ancora)
            else:
                _d, anterior = ed.virtual(pagina, letra, ancora, palavra_nova=nova)
    for gid in plano.sair:
        if gid in virtuais:
            ed.apagar_virtual(pagina, gid)
    for gid in plano.sair:
        if gid not in virtuais:
            ed.descartar(pagina, gid)
    _como_digitado(pagina, plano)
    ed.revisar(pagina, plano.revisar - virtuais)


def _como_digitado(pagina: Pagina, plano: Plano) -> None:
    """Onde a página montada partiu uma palavra que o usuário digitou inteira (o vão do
    glifo tirado), ela é juntada de novo (na mesma linha impressa)."""
    from abbychess import texto as tx

    documento = tx.montar(pagina, com_os_nao_lidos=True)
    onde: Dict[int, Tuple[int, int]] = {}
    for b, bloco in enumerate(documento.blocos):
        for n, linha in enumerate(bloco.linhas):
            for k, palavra in enumerate(linha.palavras):
                for g in palavra.gids:
                    onde[g] = ((b, n), k)
    boxes = pagina.vivos
    for palavra in plano.palavras:
        for a, b in zip(palavra, palavra[1:]):
            if a in boxes and b in boxes and a in onde and b in onde \
                    and onde[a][0] == onde[b][0] and onde[a][1] != onde[b][1]:
                ed.juntar_palavras(pagina, a, b)


# ----------------------------------------------------------------------
# As figurinas (§6.4)
# ----------------------------------------------------------------------

#: As letras das peças em cada idioma, na ordem rei, dama, torre, bispo, cavalo.
PECAS = {"pt": "RDTBC", "en": "KQRBN", "es": "RDTAC", "de": "KDTLS", "fr": "RDTFC"}
FIGURINAS_BRANCAS = "♔♕♖♗♘"


def _lance(idioma: str):
    pecas = PECAS.get(idioma, PECAS["en"])
    return re.compile(rf"^(\d{{1,3}}\.(?:\.\.)?)?([{pecas}])([a-h]?[1-8]?x?[a-h][1-8])"
                      rf"(=[{pecas}])?([+#]?[!?]{{0,2}}[±∓⩱⩲=∞]?)$")


def figurinas(token: str, idioma: str) -> str:
    """O token de lance com a letra da peça (e a da promoção) como figurina; os outros
    tokens como vieram."""
    pecas = PECAS.get(idioma, PECAS["en"])
    casou = _lance(idioma).match(token)
    if casou is None:
        return token
    numero, peca, resto, promocao, sinais = casou.groups()
    figura = FIGURINAS_BRANCAS[pecas.index(peca)]
    if promocao:
        promocao = "=" + FIGURINAS_BRANCAS[pecas.index(promocao[1])]
    return f"{numero or ''}{figura}{resto}{promocao or ''}{sinais}"


def com_figurinas(novo: str, original: str, idioma: str, modo: str) -> str:
    """O texto da sessão com as figurinas nos tokens de lance que mudaram (§6.4), se o
    livro é de figurinas; no modo letras, como foi digitado."""
    if modo != "figurinas":
        return novo
    ja_estavam = set(_normalizar(original).split())
    return re.sub(r"\S+", lambda t: t.group(0) if t.group(0) in ja_estavam
                  else figurinas(t.group(0), idioma), novo)
