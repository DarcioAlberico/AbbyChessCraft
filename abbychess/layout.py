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
        filas = [{round(((b.y1 + b.y2) / 2) / max(1.0, altura)) for b in boxes
                  if inicio <= (b.x1 + b.x2) / 2 <= fim} for inicio, fim in colunas]
        if min(len(fila) for fila in filas) < FILAS_DE_COLUNA:
            return cls(deteccao=deteccao)
        calhas = []
        for esquerda, direita in zip(colunas, colunas[1:]):
            largura = direita[0] - esquerda[1]
            calhas.append((esquerda[1] + MARGEM_DA_CALHA * largura,
                           direita[0] - MARGEM_DA_CALHA * largura,
                           (esquerda[1] + direita[0]) / 2))
        na_calha = sorted(
            (b for b in boxes if b.height >= 0.5 * altura and any(
                inicio < (b.x1 + b.x2) / 2 < fim or b.x1 < meio < b.x2
                for inicio, fim, meio in calhas)),
            key=lambda b: b.y1)
        grupos: List[List[BoxEntry]] = []
        for box in na_calha:
            if grupos and box.y1 <= max(outro.y2 for outro in grupos[-1]):
                grupos[-1].append(box)
            else:
                grupos.append([box])
        faixas = [(min(b.y1 for b in grupo), max(b.y2 for b in grupo)) for grupo in grupos
                  if len(grupo) >= 2 or max(b.height for b in grupo) >= 1.5 * altura]
        return cls(tuple(tuple(c) for c in colunas), tuple(faixas))

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
        return partir_nos_vaos(partir_depois_do_f(linhas, trecho), trecho)


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
    from core.notacao import LIMIAR_ESPACO, Palavra, _largura_mediana

    def depois_do_f(a, b) -> bool:
        return a.char == "f" and b.char[:1].isalpha()

    def lacuna(a, b) -> int:
        return trecho[b.indice].x1 - trecho[a.indice].x2

    def nada_no_meio(a, b) -> bool:
        """Nenhum box entre os dois (só para quem vai ser partido)."""
        esquerdo, direito = trecho[a.indice], trecho[b.indice]
        return not any(c.x1 < direito.x1 and c.x2 > esquerdo.x2
                       and c.y1 < esquerdo.y2 and c.y2 > esquerdo.y1
                       and c is not esquerdo and c is not direito for c in trecho)

    pares = [(a, b) for linha in linhas for p in linha for a, b in zip(p.simbolos, p.simbolos[1:])]
    comuns = [lacuna(a, b) for a, b in pares if not depois_do_f(a, b)]
    if not comuns:
        return linhas
    comum = statistics.median(comuns)
    dentro = [lacuna(a, b) for a, b in pares if depois_do_f(a, b) and lacuna(a, b) <= comum]
    gancho = comum - statistics.median(dentro) if len(dentro) >= AMOSTRAS_DO_GANCHO else 0
    if gancho <= 0:
        return linhas
    limiar = LIMIAR_ESPACO * _largura_mediana(trecho) - gancho

    saida = []
    for linha in linhas:
        palavras = []
        for palavra in linha:
            atual = []
            for s in palavra.simbolos:
                if (atual and depois_do_f(atual[-1], s) and lacuna(atual[-1], s) > limiar
                        and nada_no_meio(atual[-1], s)):
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


def partir_nos_vaos(linhas: list, trecho: Sequence[BoxEntry]) -> list:
    """Cada linha do core partida onde o vão entre duas palavras passa de `VAO_QUE_PARTE`
    alturas de glifo, com ao menos `PALAVRAS_DE_CADA_LADO` palavras em cada parte: o core
    junta numa linha o que está na mesma altura, e as legendas lado a lado viravam uma frase."""
    saida = []
    for linha in linhas:
        palavras = [p for p in linha if p.simbolos]
        if len(palavras) < 2 * PALAVRAS_DE_CADA_LADO:
            saida.append(linha)
            continue
        altura = statistics.median(trecho[s.indice].y2 - trecho[s.indice].y1
                                   for p in palavras for s in p.simbolos)
        partes, atual = [], [palavras[0]]
        for k, (p, q) in enumerate(zip(palavras, palavras[1:]), start=1):
            vao = (min(trecho[s.indice].x1 for s in q.simbolos)
                   - max(trecho[s.indice].x2 for s in p.simbolos))
            if (vao > VAO_QUE_PARTE * max(1, altura) and len(atual) >= PALAVRAS_DE_CADA_LADO
                    and len(palavras) - k >= PALAVRAS_DE_CADA_LADO):
                partes.append(atual)
                atual = []
            atual.append(q)
        partes.append(atual)
        saida.extend(partes if len(partes) > 1 else [linha])
    return saida
