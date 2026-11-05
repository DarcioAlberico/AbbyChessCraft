"""Substituir (SPEC §7.2, passo D2): sem Qt.

Os casos saem do índice da busca (`busca.PaginaIndexada`: o texto do Documento, o gid e a
etiqueta de cada caractere) e das unidades da página (`sessao.texto_e_unidades`). Cada caso
é a menor sequência de palavras inteiras que um ou mais casamentos tocam, com o texto de
antes e o de depois (o substituto com `\\1` e `\\g<nome>`, quando a regex está ligada). O
caso que a sessão de edição recusaria (o que é do passo G: juntar ou dividir glifos, o
hífen de fim de linha) vem com o motivo: a prévia o mostra desabilitado.

"Onde" é Prosa (a prosa, as legendas e os cabeçalhos), Notação ou Ambos: um casamento que
toca uma palavra de fora não vira caso. O FEN é pesquisável, nunca substituível.

Aplicar numa página é uma sessão só, da página inteira (`aplicar_na_pagina`): o texto com
os casos aceitos, alinhado ao original passando pelos caracteres que nenhum caso tocou; as
operações são as do §6.3 (`sessao.aplicar`), os glifos corrigidos ficam `manual` e nada é
ensinado nem marcado como revisado.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Dict, FrozenSet, List, Optional, Sequence, Tuple

import regex

from abbychess import busca as bs
from abbychess import sessao as ss
from abbychess.modelo import Pagina

PROSA, NOTACAO, AMBOS = "prosa", "notacao", "ambos"
ALVOS = ((PROSA, "Prosa"), (NOTACAO, "Notação"), (AMBOS, "Ambos"))
#: As etiquetas do índice que cada "onde" pode tocar (o FEN, nenhum).
ETIQUETAS_DO_ALVO: Dict[str, FrozenSet[str]] = {
    PROSA: frozenset({bs.PROSA, bs.LEGENDA, bs.CABECALHO}),
    NOTACAO: frozenset({bs.NOTACAO}),
    AMBOS: frozenset({bs.PROSA, bs.LEGENDA, bs.CABECALHO, bs.NOTACAO}),
}


@dataclass(frozen=True)
class Caso:
    """Uma substituição: as palavras [inicio, fim) do texto da página, de `antes` para
    `depois`. `motivo` diz por que ela ainda não tem tradução (a prévia a desabilita)."""

    pagina: int
    inicio: int
    fim: int
    antes: str
    depois: str
    etiqueta: str
    linha: int
    gids: Tuple[int, ...]
    casamentos: int = 1
    motivo: str = ""

    @property
    def aplicavel(self) -> bool:
        return not self.motivo


@dataclass
class Previa:
    """Os casos de uma página, com o texto dela quando foram calculados. `lida` é a página
    como a prévia a leu (aplicar edita uma cópia dela e confere que a página não mudou desde
    então), `carimbo`, o arquivo dela na leitura (`projeto.carimbo`), `geracao`, o projeto;
    `fora`, os casamentos que ficaram fora porque tocam palavras de outro "onde"."""

    indice: int
    texto: str
    casos: List[Caso]
    lida: Optional[Pagina] = None
    carimbo: Optional[tuple] = None
    geracao: Optional[int] = None
    fora: int = field(default=0)


def substituto(modelo: str, regex_ligada: bool) -> Callable[[object], str]:
    """O texto que entra no lugar de cada casamento: com a regex, `\\1`, `\\g<nome>` e os
    escapes de `re`; sem ela, o modelo como está."""
    if not regex_ligada:
        return lambda _casado: modelo

    def expandir(casado) -> str:
        try:
            return casado.expand(modelo)
        except (regex.error, IndexError) as erro:
            raise bs.PadraoInvalido(f"substituto inválido: {erro}") from erro
    return expandir


def validar(modelo: str, expressao, regex_ligada: bool) -> None:
    """`PadraoInvalido` se o substituto cita um grupo que a regex não tem (antes de buscar)."""
    if not regex_ligada:
        return
    k = 0
    while k < len(modelo):
        if modelo[k] != "\\" or k + 1 == len(modelo):
            k += 1
        elif modelo[k + 1].isdigit():
            k = _depois_do_grupo_numerado(modelo, k, expressao)
        elif modelo[k + 1:k + 3] == "g<":
            k = _depois_do_grupo_nomeado(modelo, k, expressao)
        else:
            k += 2


def _depois_do_grupo_numerado(modelo: str, k: int, expressao) -> int:
    """Onde termina o `\\N` que começa em `k` (até dois dígitos); `PadraoInvalido` se a regex
    não tem o grupo."""
    fim = k + 1
    while fim < len(modelo) and modelo[fim].isdigit() and fim - k <= 2:
        fim += 1
    numero = int(modelo[k + 1:fim])
    if numero > expressao.groups:
        raise bs.PadraoInvalido(f"substituto inválido: o grupo \\{numero} não existe")
    return fim


def _depois_do_grupo_nomeado(modelo: str, k: int, expressao) -> int:
    """Onde termina o `\\g<nome>` que começa em `k`; `PadraoInvalido` sem o `>` ou sem o
    grupo."""
    fecha = modelo.find(">", k + 3)
    if fecha < 0:
        raise bs.PadraoInvalido("substituto inválido: falta o > de \\g<nome>")
    nome = modelo[k + 3:fecha]
    existe = (int(nome) <= expressao.groups if nome.isdigit()
              else nome in expressao.groupindex)
    if not existe:
        raise bs.PadraoInvalido(f"substituto inválido: o grupo {nome} não existe")
    return fecha + 1


def casos_da_pagina(indexada: bs.PaginaIndexada, unidades: Sequence[ss.Unidade], expressao,
                    trocar: Callable[[object], str], alvo: str = PROSA,
                    onde: FrozenSet[str] = frozenset(bs.ETIQUETAS),
                    trecho: Optional[Tuple[int, int]] = None,
                    tempo_limite: Optional[float] = None,
                    fora: Optional[List[int]] = None) -> List[Caso]:
    """Os casos da página: os casamentos em palavras de `alvo` (e de `onde`, o filtro da
    busca), juntados quando tocam as mesmas palavras. `trecho`: só dentro dele (a
    seleção). `PadraoLento` se um casamento passa do tempo-limite (`busca.TEMPO_LIMITE`, se
    não vier). `fora`, se vier, ganha quantos casamentos ficaram fora por tocar palavras de
    outro "onde" (a notação, com Prosa; a prosa, com Notação)."""
    texto = "".join(u.texto for u in unidades)
    if not indexada.texto.startswith(texto):
        raise ValueError("o índice da página não é o das unidades dela")
    inicio, fim = trecho if trecho is not None else (0, len(texto))
    casamentos = bs.casamentos(indexada, expressao, inicio, min(fim, len(texto)),
                               bs.TEMPO_LIMITE if tempo_limite is None else tempo_limite,
                               indice=indexada.indice)
    trocas = _trocas(indexada, texto, casamentos, trocar, ETIQUETAS_DO_ALVO[alvo] & onde,
                     ETIQUETAS_DO_ALVO[AMBOS] & onde, fora if fora is not None else [0])
    return _juntar_em_casos(indexada, unidades, texto, trocas)


def _trocas(indexada, texto: str, casamentos, trocar, permitidas, substituiveis,
            fora: List[int]) -> List[Tuple[int, int, str]]:
    """(início, fim, novo) de cada casamento só em palavras `permitidas` que muda o texto;
    `fora` conta os que tocam as outras `substituiveis`."""
    trocas: List[Tuple[int, int, str]] = []
    for casado in casamentos:
        a, b = casado.start(), casado.end()
        etiquetas = {indexada.etiqueta(k) for k in range(a, b) if not texto[k].isspace()}
        if etiquetas and etiquetas <= permitidas:
            novo = trocar(casado)
            if novo != texto[a:b]:
                trocas.append((a, b, novo))
        elif etiquetas and etiquetas <= substituiveis:
            fora[0] += 1
    return trocas


def _juntar_em_casos(indexada, unidades, texto: str, trocas) -> List[Caso]:
    faixas, grupos = _nas_mesmas_palavras(unidades, trocas)
    return [_caso(indexada, unidades, texto, de, ate, grupo)
            for (de, ate), grupo in zip(faixas, grupos)]


def _nas_mesmas_palavras(unidades, trocas) -> Tuple[List[Tuple[int, int]],
                                                     List[List[Tuple[int, int, str]]]]:
    """As faixas de palavras das trocas e as trocas de cada uma: as que tocam as mesmas
    palavras são um caso só."""
    grupos: List[List[Tuple[int, int, str]]] = []
    faixas: List[Tuple[int, int]] = []
    for a, b, novo in trocas:
        de, ate = ss.palavras_em(unidades, a, b)
        if faixas and de < faixas[-1][1]:       # as mesmas palavras: um caso só
            faixas[-1] = (faixas[-1][0], max(ate, faixas[-1][1]))
            grupos[-1].append((a, b, novo))
        else:
            faixas.append((de, ate))
            grupos.append([(a, b, novo)])
    return faixas, grupos


def _caso(indexada, unidades, texto: str, de: int, ate: int, grupo) -> Caso:
    depois = _trocado(texto, de, ate, grupo)
    gids = tuple(dict.fromkeys(u.gid for u in unidades[de:ate] if u.glifo))
    primeiro = next((k for k in range(grupo[0][0], grupo[0][1]) if not texto[k].isspace()),
                    grupo[0][0])
    return Caso(indexada.indice, de, ate, texto[de:ate], depois,
                bs.NOTACAO if indexada.etiqueta(primeiro) == bs.NOTACAO else bs.PROSA,
                texto.count("\n", 0, de) + 1, gids, len(grupo))


def _texto_com_os_casos(texto: str, unidades, casos: Sequence[Caso]
                        ) -> Tuple[str, List[Tuple[int, int]]]:
    """O texto da página com os casos trocados, e as posições que não mudam (de antes ->
    de depois); `sessao.Recusa` se um caso não é mais o da página."""
    partes: List[str] = []
    fixos: List[Tuple[int, int]] = []
    posicao = j = 0
    for caso in sorted(casos, key=lambda c: c.inicio):
        # As mesmas palavras inteiras: "casas" começa com "casa", mas não é o caso "casa".
        if (caso.inicio < posicao or texto[caso.inicio:caso.fim] != caso.antes
                or ss.palavras_em(unidades, caso.inicio, caso.fim) != (caso.inicio, caso.fim)):
            raise ss.Recusa("a página mudou desde a prévia")
        for i in range(posicao, caso.inicio):
            fixos.append((i, j + i - posicao))
        j += caso.inicio - posicao
        partes += [texto[posicao:caso.inicio], caso.depois]
        j += len(caso.depois)
        posicao = caso.fim
    for i in range(posicao, len(texto)):
        fixos.append((i, j + i - posicao))
    partes.append(texto[posicao:])
    return "".join(partes), fixos


def _trocado(texto: str, de: int, ate: int, grupo) -> str:
    partes, posicao = [], de
    for a, b, novo in grupo:
        partes += [texto[posicao:a], novo]
        posicao = b
    partes.append(texto[posicao:ate])
    return "".join(partes)


def aplicar_na_pagina(pagina: Pagina, casos: Sequence[Caso], imagem_de=lambda: None) -> ss.Plano:
    """Os casos aceitos na página, numa sessão só (ver o docstring do módulo). Levanta
    `sessao.Recusa` sem mudar nada se o conjunto não tem tradução. `imagem_de()` dá a imagem
    da página, pedida só quando um caso divide um glifo pela tinta (m → rn, §6.3)."""
    texto, unidades = ss.texto_e_unidades(pagina)
    novo, fixos = _texto_com_os_casos(texto, unidades, casos)
    plano = ss.planejar(unidades, novo, fixos)
    plano.revisar = set()                       # substituir não revisa nem ensina (§7.2)
    # A cópia da página (`instantaneo`) guarda os boxes numa tupla, e juntar ou dividir
    # monta a lista nova somando pedaços dela (antes, TypeError em todo caso estrutural).
    pagina.boxes = list(pagina.boxes)
    antes = {b.gid for b in pagina.boxes}
    ss.aplicar(pagina, plano, imagem_de() if plano.dividir_boxes else None)
    # Os boxes que nascem de juntar ou dividir também ficam por revisar (o substituir não
    # revisa nada; a edição pelo Documento é que os marca revisados).
    pagina.boxes = [replace(b, revisado=False) if b.gid not in antes and b.revisado else b
                    for b in pagina.boxes]
    return plano
