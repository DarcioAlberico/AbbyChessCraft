"""Análise de layout compartilhada pelo Documento e pela exportação.

O primeiro estágio público é a ordem de leitura em colunas. Ele divide a página em trechos
independentes antes de formar linhas, para que o rodapé de uma coluna nunca se misture ao
topo da seguinte. Faixas que atravessam a calha, como títulos, ficam entre os trechos.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from core.box_model import BoxEntry

#: Quanto da calha, de cada lado, não conta para um box atravessar: o `9` que abre a coluna
#: da direita encosta na calha sem atravessá-la.
MARGEM_DA_CALHA = 0.25
#: Filas de texto que cada coluna precisa ter para a página ser lida em colunas. Com três (a
#: exportação até 2026-10-23), filas curtas apareciam por acaso depois de dividir ou juntar
#: boxes, e páginas de diagramas viravam colunas que cortavam os tabuleiros (3 de 160
#: páginas de 8 livros, `docs/revisoes/pendencias.md`); com seis, nenhuma página real perde
#: as colunas que tem. O Documento e a exportação usam a mesma, e leem a página igual.
FILAS_DE_COLUNA = 6
#: A linha que atravessa a calha (`_linhas_que_atravessam`): o vão dela na calha, em larguras
#: da calha. No Mirkovic (calha de 48 px), as linhas de largura total têm de -10 a 21 px ali
#: e o título centrado 13; entre as duas colunas o vão é a calha inteira ou mais.
VAO_DA_LINHA_NA_CALHA = 0.6
ChaveDeLeitura = Tuple[int, int]


def _coluna_de(x: float, colunas: Sequence[Tuple[int, int]]) -> int:
    """A coluna que contém ``x`` ou, na calha, a coluna mais próxima."""
    for i, (inicio, fim) in enumerate(colunas):
        if inicio <= x <= fim:
            return i
    return min(range(len(colunas)),
               key=lambda i: min(abs(x - colunas[i][0]), abs(x - colunas[i][1])))


@dataclass(frozen=True)
class OrdemDeLeitura:
    """Colunas e faixas transversais de uma página, numa interface sem detalhes do core: a
    ordem de leitura em trechos de uma coluna só, `(faixa, coluna)`, do Documento e da
    exportação.

    **As linhas se montam dentro de cada trecho.** O `core.notacao` monta a linha pela
    altura, na ordem de leitura do `BoxService`; quando ela passa do pé de uma coluna para o
    alto da seguinte, o caractere de cima "não está abaixo" da linha corrente e entra nela
    (no Odds & Ends, `isfantastic:16...d3`, a linha de uma coluna colada à da outra).

    O que atravessa a calha (o título centrado sobre as duas colunas) é uma faixa sozinha,
    na altura dele; entre duas dessas, as colunas da esquerda para a direita. Página de uma
    coluna é um trecho só. A mesma chave ordena as figuras da exportação (`chave` de um
    ponto): o diagrama da coluna da esquerda fica entre os parágrafos dela."""

    colunas: Tuple[Tuple[int, int], ...] = ()
    faixas: Tuple[Tuple[float, float], ...] = ()
    #: A detecção do core sobre a página inteira; quando a página é um trecho só, o core a
    #: reaproveita (`deteccao_do_trecho`) em vez de refazê-la: ela é a parte mais cara de
    #: montar o texto, e o índice da busca monta o de todas as páginas.
    deteccao: object = field(default=None, compare=False, repr=False)

    @classmethod
    def da_pagina(cls, boxes: Sequence[BoxEntry]) -> "OrdemDeLeitura":
        from core.services.box_service import BoxService

        if len(boxes) < 2:
            return cls()
        deteccao = BoxService.detectar_colunas_e_transversais(list(boxes))
        colunas = deteccao[0]
        if len(colunas) < 2:
            return cls(deteccao=deteccao)
        altura = statistics.median(b.y2 - b.y1 for b in boxes)
        if _filas_de_cada_coluna(boxes, colunas, altura) < FILAS_DE_COLUNA:
            return cls(deteccao=deteccao)
        grupos = _grupos_pela_altura(_na_calha(boxes, _calhas(colunas), altura))
        faixas = _faixas_dos_grupos(grupos, altura)
        faixas += _linhas_que_atravessam(boxes, colunas, altura)
        return cls(tuple(tuple(c) for c in colunas), _unidas(faixas))

    def chave(self, x: float, y: float) -> ChaveDeLeitura:
        if not self.colunas:
            return 0, 0
        faixa = 2 * len(self.faixas)
        for k, (topo, pe) in enumerate(self.faixas):
            if topo <= y <= pe:
                faixa = 2 * k + 1
                break
            if y < topo:
                faixa = 2 * k
                break
        return faixa, 0 if faixa % 2 else _coluna_de(x, self.colunas)

    def trechos(self, boxes: Sequence[BoxEntry]) -> List[Tuple[ChaveDeLeitura, List[int]]]:
        """Índices agrupados por trecho, na ordem em que a página deve ser lida."""
        por_trecho: Dict[ChaveDeLeitura, List[int]] = {}
        for i, box in enumerate(boxes):
            chave = self.chave((box.x1 + box.x2) / 2, (box.y1 + box.y2) / 2)
            por_trecho.setdefault(chave, []).append(i)
        return [(chave, por_trecho[chave]) for chave in sorted(por_trecho)]

    def deteccao_do_trecho(self, indices: Sequence[int], boxes: Sequence[BoxEntry]):
        """A detecção para `palavras_da_pagina` do trecho: a da página, quando o trecho é a
        página inteira (os mesmos boxes, na mesma ordem); senão, None (o core a faz)."""
        return self.deteccao if len(indices) == len(boxes) else None

    def linhas_do_trecho(self, indices: Sequence[int], boxes: Sequence[BoxEntry]) -> list:
        """As linhas de palavras do trecho (`palavras_da_pagina` do core, com os índices dos
        símbolos relativos ao trecho), partidas depois do gancho do "f" (`partir_depois_do_f`)
        e nos vãos largos demais (`partir_nos_vaos`)."""
        from core.notacao import palavras_da_pagina

        trecho = [boxes[i] for i in indices]
        linhas = palavras_da_pagina(trecho, self.deteccao_do_trecho(indices, boxes))
        if len(indices) < len(boxes):
            linhas = partir_pela_pagina(linhas, trecho, boxes)
        return partir_nos_vaos(partir_depois_do_f(linhas, trecho), trecho)


def _filas_de_cada_coluna(boxes: Sequence[BoxEntry], colunas, altura: float) -> int:
    """Quantas filas de texto (alturas de glifo) tem a coluna que tem menos."""
    filas = [{round(((b.y1 + b.y2) / 2) / max(1.0, altura)) for b in boxes
              if inicio <= (b.x1 + b.x2) / 2 <= fim} for inicio, fim in colunas]
    return min(len(fila) for fila in filas)


def _calhas(colunas) -> List[Tuple[float, float, float]]:
    """(início, fim, meio) de cada calha, sem `MARGEM_DA_CALHA` de cada lado."""
    calhas = []
    for esquerda, direita in zip(colunas, colunas[1:]):
        largura = direita[0] - esquerda[1]
        calhas.append((esquerda[1] + MARGEM_DA_CALHA * largura,
                       direita[0] - MARGEM_DA_CALHA * largura,
                       (esquerda[1] + direita[0]) / 2))
    return calhas


def _na_calha(boxes: Sequence[BoxEntry], calhas, altura: float) -> List[BoxEntry]:
    """Os glifos de meia altura ou mais com o centro numa calha, ou por cima do meio dela,
    de cima para baixo."""
    return sorted(
        (b for b in boxes if b.height >= 0.5 * altura and any(
            inicio < (b.x1 + b.x2) / 2 < fim or b.x1 < meio < b.x2
            for inicio, fim, meio in calhas)),
        key=lambda b: b.y1)


def _grupos_pela_altura(na_calha: Sequence[BoxEntry]) -> List[List[BoxEntry]]:
    """Os glifos (de cima para baixo) em grupos: o que começa antes do pé do grupo de cima
    entra nele."""
    grupos: List[List[BoxEntry]] = []
    for box in na_calha:
        if grupos and box.y1 <= max(outro.y2 for outro in grupos[-1]):
            grupos[-1].append(box)
        else:
            grupos.append([box])
    return grupos


def _faixas_dos_grupos(grupos: Sequence[List[BoxEntry]], altura: float
                       ) -> List[Tuple[float, float]]:
    """A faixa de cada grupo da calha com dois glifos ou mais, ou com um de 1,5 altura."""
    return [(min(b.y1 for b in grupo), max(b.y2 for b in grupo)) for grupo in grupos
            if len(grupo) >= 2 or max(b.height for b in grupo) >= 1.5 * altura]


def _linhas_que_atravessam(boxes: Sequence[BoxEntry], colunas, altura: float
                           ) -> List[Tuple[float, float]]:
    """As faixas das linhas que passam de uma coluna à outra sem o vão da calha.

    O parágrafo de largura total no alto de uma página de duas colunas (Mirkovic, p. 160:
    "…where bish|op is sacrificed…") tem um box só, ou nenhum, no meio da calha; como faixa
    pelos boxes da calha ele não entrava, e cada linha virava metade de uma coluna e metade
    da outra. Aqui vale a linha: perto da calha, com texto dos dois lados, e o vão nela menor
    que `VAO_DA_LINHA_NA_CALHA` da largura da calha. O título centrado com o espaço bem na
    calha ("NO PAIN | NO GAIN", p. 10) também."""
    faixas = []
    for esquerda, direita in zip(colunas, colunas[1:]):
        largura = direita[0] - esquerda[1]
        if largura <= 0:
            continue
        meio = (esquerda[1] + direita[0]) / 2
        perto = sorted((b for b in boxes if b.x2 >= esquerda[1] - 3 * altura
                        and b.x1 <= direita[0] + 3 * altura and b.height > 0),
                       key=lambda b: (b.y1 + b.y2) / 2)
        filas: List[List[BoxEntry]] = []
        for box in perto:
            centro = (box.y1 + box.y2) / 2
            if filas and min(b.y1 for b in filas[-1]) <= centro <= max(b.y2 for b in filas[-1]):
                filas[-1].append(box)
            else:
                filas.append([box])
        for fila in filas:
            antes = [b for b in fila if (b.x1 + b.x2) / 2 < meio]
            depois = [b for b in fila if (b.x1 + b.x2) / 2 >= meio]
            if not antes or not depois:
                continue
            vao = min(b.x1 for b in depois) - max(b.x2 for b in antes)
            if vao < VAO_DA_LINHA_NA_CALHA * largura:
                topo, pe = min(f.y1 for f in fila), max(f.y2 for f in fila)     # uma vez por fila
                linha = [b for b in boxes if topo <= (b.y1 + b.y2) / 2 <= pe]
                faixas.append((min(b.y1 for b in linha), max(b.y2 for b in linha)))
    return faixas


def _unidas(faixas: Sequence[Tuple[float, float]]) -> Tuple[Tuple[float, float], ...]:
    """As faixas em ordem, as que se sobrepõem juntas numa só."""
    saida: List[Tuple[float, float]] = []
    for topo, pe in sorted(faixas):
        if saida and topo <= saida[-1][1]:
            saida[-1] = (saida[-1][0], max(saida[-1][1], pe))
        else:
            saida.append((topo, pe))
    return tuple(saida)


#: O trecho cujos glifos são, na mediana, mais largos que isto vezes os da página mede o espaço
#: pela página (`partir_pela_pagina`).
LARGURA_DO_TRECHO_ISOLADO = 1.25


def partir_pela_pagina(linhas: list, trecho: Sequence[BoxEntry], pagina: Sequence[BoxEntry]
                       ) -> list:
    """As palavras do trecho partidas pelo limiar de espaço da página quando o trecho só tem
    glifos largos: o core mede o espaço pela largura mediana do trecho, e o cabeçalho ou o
    título que viram um trecho sozinho (a faixa que atravessa a calha) perdiam os espaços
    ("GMNIK0LAsEDLAK", Mirkovic p. 10: letras a 1–3 px, palavras a 11–13, o limiar do trecho
    15 e o da página 9)."""
    from core.notacao import LIMIAR_ESPACO, Palavra

    da_pagina = largura_mediana(pagina)
    if largura_mediana(trecho) <= LARGURA_DO_TRECHO_ISOLADO * da_pagina:
        return linhas
    limiar = LIMIAR_ESPACO * da_pagina
    saida = []
    for linha in linhas:
        palavras = []
        for palavra in linha:
            atual = []
            for s in palavra.simbolos:
                if atual and trecho[s.indice].x1 - trecho[atual[-1].indice].x2 > limiar:
                    palavras.append(Palavra(atual))
                    atual = []
                atual.append(s)
            palavras.append(Palavra(atual))
        saida.append(palavras)
    return saida


#: Quantas lacunas depois do "f", dentro da palavra, o trecho precisa ter para o gancho valer.
AMOSTRAS_DO_GANCHO = 3


def partir_depois_do_f(linhas: list, trecho: Sequence[BoxEntry]) -> list:
    """Cada palavra do core partida entre um "f" e a letra seguinte quando a lacuna, somada ao
    gancho do "f", passa do limiar de espaço do core (`notacao.LIMIAR_ESPACO`).

    **O gancho do "f" passa da haste para a direita**, e o box acaba alguns pixels depois da
    tinta do corpo: a lacuna até a palavra seguinte sai menor, e o espaço depois de "of"
    sumia. Na p. 15 do Aagaard ("A Matter of Endgame Technique", largura 16, limiar 8), a
    lacuna depois do "f" é de -4 a -3 dentro da palavra ("after", "for") e de 5 a 8 entre
    palavras: "ofthe", "ofexercises", "yourselfa".

    O gancho é medido no trecho: a lacuna comum dentro da palavra menos a mediana das lacunas
    depois do "f" que não passam dela, com ao menos `AMOSTRAS_DO_GANCHO` delas. Sem gancho (a
    fonte sem ele, o texto espaçado) ou sem amostras, o limiar é o do core e nada muda: na p.
    1045 do Yusupov uma amostra só (-4) dava um gancho de 7 px, e "fr" ("for" com o "o"
    perdido) saía partido.

    **Com um box sem leitura entre o "f" e a letra** ("fo|llowed" sem o "o"), a palavra fica
    como o core a fez: ele não faz símbolo do box, mas mede a lacuna por ele."""
    from core.notacao import LIMIAR_ESPACO

    gancho = _gancho_do_f(linhas, trecho)
    if gancho <= 0:
        return linhas
    return _partidas_depois_do_f(linhas, trecho, LIMIAR_ESPACO * largura_mediana(trecho) - gancho)


def _depois_do_f(a, b) -> bool:
    return a.char == "f" and b.char[:1].isalpha()


def _lacuna(trecho: Sequence[BoxEntry], a, b) -> int:
    return trecho[b.indice].x1 - trecho[a.indice].x2


def _nada_no_meio(trecho: Sequence[BoxEntry], a, b) -> bool:
    """Nenhum box entre os dois (só para quem vai ser partido)."""
    esquerdo, direito = trecho[a.indice], trecho[b.indice]
    return not any(c.x1 < direito.x1 and c.x2 > esquerdo.x2
                   and c.y1 < esquerdo.y2 and c.y2 > esquerdo.y1
                   and c is not esquerdo and c is not direito for c in trecho)


def _gancho_do_f(linhas: list, trecho: Sequence[BoxEntry]) -> float:
    """O gancho do "f" no trecho: a lacuna comum dentro da palavra menos a mediana das
    lacunas depois do "f" que não passam dela; 0 sem lacuna comum ou com menos de
    `AMOSTRAS_DO_GANCHO` amostras."""
    comuns, do_f = _lacunas_dentro_da_palavra(linhas, trecho)
    if not comuns:
        return 0
    comum = statistics.median(comuns)
    dentro = [lacuna for lacuna in do_f if lacuna <= comum]
    return comum - statistics.median(dentro) if len(dentro) >= AMOSTRAS_DO_GANCHO else 0


def _lacunas_dentro_da_palavra(linhas: list, trecho: Sequence[BoxEntry]
                               ) -> Tuple[List[int], List[int]]:
    """As lacunas entre letras vizinhas de cada palavra, em ordem: as comuns e as depois do
    "f"."""
    comuns: List[int] = []
    do_f: List[int] = []
    for linha in linhas:
        for p in linha:
            for a, b in zip(p.simbolos, p.simbolos[1:]):
                (do_f if _depois_do_f(a, b) else comuns).append(_lacuna(trecho, a, b))
    return comuns, do_f


def _partidas_depois_do_f(linhas: list, trecho: Sequence[BoxEntry], limiar: float) -> list:
    """Cada palavra partida entre o "f" e a letra seguinte com a lacuna acima do `limiar` e
    nenhum box entre os dois."""
    from core.notacao import Palavra

    saida = []
    for linha in linhas:
        palavras = []
        for palavra in linha:
            atual = []
            for s in palavra.simbolos:
                if (atual and _depois_do_f(atual[-1], s) and _lacuna(trecho, atual[-1], s) > limiar
                        and _nada_no_meio(trecho, atual[-1], s)):
                    palavras.append(Palavra(atual))
                    atual = []
                atual.append(s)
            palavras.append(Palavra(atual))
        saida.append(palavras)
    return saida


#: O vão entre palavras que parte uma linha, em alturas de glifo (a mediana da linha), e as
#: palavras que cada parte precisa ter. Nas p. 21–27 do Xadrez Vitorioso, as legendas de dois
#: diagramas lado a lado saíam numa linha só, com 10,5 alturas entre elas (entre palavras, ~0,6).
#: Em 135 páginas de 9 livros, só passam dos dois as legendas lado a lado, as colunas de um
#: índice e títulos com ornamentos, que também são linhas à parte; a tabela de lances (o
#: número de um lado, o lance do outro) fica em 6,3, e por isso o limiar é 8.
VAO_QUE_PARTE, PALAVRAS_DE_CADA_LADO = 8.0, 3


def largura_mediana(boxes: Sequence[BoxEntry]) -> float:
    """A largura mediana dos glifos lidos (a régua de espaço do core, que a deixa privada:
    `core.notacao._largura_mediana`, refeita aqui pelo contrato)."""
    larguras = sorted(b.x2 - b.x1 for b in boxes if b.char)
    return float(larguras[len(larguras) // 2]) or 1.0 if larguras else 1.0


def partir_nos_vaos(linhas: list, trecho: Sequence[BoxEntry]) -> list:
    """Cada linha do core partida onde o vão entre duas palavras passa de `VAO_QUE_PARTE`
    alturas de glifo, com ao menos `PALAVRAS_DE_CADA_LADO` palavras em cada parte: o core
    junta numa linha o que está na mesma altura, e as legendas lado a lado viravam uma frase."""
    saida = []
    for linha in linhas:
        saida.extend(_linha_partida_nos_vaos(linha, trecho))
    return saida


def _linha_partida_nos_vaos(linha: list, trecho: Sequence[BoxEntry]) -> list:
    """As partes da linha (a linha inteira, se ela não parte)."""
    palavras = [p for p in linha if p.simbolos]
    if len(palavras) < 2 * PALAVRAS_DE_CADA_LADO:
        return [linha]
    altura = statistics.median(trecho[s.indice].y2 - trecho[s.indice].y1
                               for p in palavras for s in p.simbolos)

    def vao(atual: list, q) -> float:
        """Da última palavra da parte até a palavra `q`."""
        return (min(trecho[s.indice].x1 for s in q.simbolos)
                - max(trecho[s.indice].x2 for s in atual[-1].simbolos))

    partes = partes_pelo_vao(palavras, vao, VAO_QUE_PARTE * max(1, altura), PALAVRAS_DE_CADA_LADO)
    return partes if len(partes) > 1 else [linha]


def partes_pelo_vao(itens: Sequence, vao, limite: float, de_cada_lado: int) -> List[list]:
    """Os itens, em ordem, partidos antes de cada um cujo `vao(parte, item)` até a parte
    corrente passa de `limite`, com `de_cada_lado` itens ou mais de cada lado do corte. A
    regra das linhas do Documento (`partir_nos_vaos`, entre palavras) e da linha das zonas
    automáticas (`zonas._partir_no_vao`, entre glifos)."""
    partes, atual = [], [itens[0]]
    for k, item in enumerate(itens[1:], start=1):
        if (vao(atual, item) > limite and len(atual) >= de_cada_lado
                and len(itens) - k >= de_cada_lado):
            partes.append(atual)
            atual = []
        atual.append(item)
    partes.append(atual)
    return partes
