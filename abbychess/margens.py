"""As margens corridas e os números impressos (§12.1): o cabeçalho, o rodapé e o número de
página que se repetem entre páginas saem do texto exportado, e o número impresso de cada página
vira o rótulo dela. Puro: recebe as linhas da montagem (`montagem`). À parte de `exportar.py`
(SPEC-qualidade Q-E6, CA-Q-A1)."""

from __future__ import annotations

import difflib
import re
import statistics
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from core.box_model import BoxEntry

from abbychess.layout import OrdemDeLeitura
from abbychess.montagem import FUNCOES_DE_MARGEM, Estrutura, _Linha, _linhas


#: A faixa de cima e a de baixo da página, em frações da altura, onde moram o
#: cabeçalho e o rodapé corridos. No Xadrez Vitorioso o cabeçalho fica entre 5%
#: e 7% da altura, e a primeira linha do texto em 10%.
FAIXA_DA_MARGEM = 0.10
#: O vão que separa o cabeçalho do texto, em passos medianos entre linhas. Lá o
#: vão é de 2 a 3 passos; entre duas linhas do texto, 1.
VAO_DA_MARGEM = 1.5
#: Texto de cabeçalho é curto: um título corrido com o número da página.
TAMANHO_DA_MARGEM = 80
#: Quanto dois cabeçalhos precisam se parecer, só nas letras, para serem o mesmo
#: em páginas diferentes. Baixo de propósito: o OCR de uma página lê "SElRAWAN"
#: e o da outra "SElRA AN".
SEMELHANCA_DA_MARGEM = 0.6
#: A borda extrema da página, onde uma linha de um ou dois caracteres é poeira
#: da digitalização, não texto ("l" em y=1, "." em y=3.480).
FAIXA_DA_POEIRA = 0.03
#: O número da página sozinho entre o que não é letra nem dígito: "22", "- 22 -", "-22-".
_NUMERO_DE_PAGINA = re.compile(r"(?<![^\W\d_])(?<!\d)\d{1,4}(?!\d)(?![^\W\d_])")


@dataclass
class _Margem:
    """O que sai do texto exportado de uma página, e o candidato a título corrido."""

    poeira: List[int] = field(default_factory=list)
    #: `(linha, "cabecalho" | "rodape")` que passaram pela posição e pelo vão.
    candidatos: List[Tuple[_Linha, str]] = field(default_factory=list)


def _so_letras(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", sem_acento.lower())


def _margem_da_pagina(boxes: Sequence[BoxEntry], altura: int) -> _Margem:
    margem = _Margem()
    # De cima para baixo, sem os trechos de coluna: o cabeçalho `Games 7`, com o
    # título numa coluna e o número na outra, é uma linha só, a primeira.
    linhas = _linhas(boxes, OrdemDeLeitura())
    if not linhas or not altura:
        return margem
    poeira = [linha for linha in linhas if len(linha.texto.replace(" ", "")) <= 2 and (
        linha.pe < FAIXA_DA_POEIRA * altura or linha.topo > (1 - FAIXA_DA_POEIRA) * altura)]
    for linha in poeira:
        margem.poeira.extend(linha.indices)
    linhas = [linha for linha in linhas if linha not in poeira]
    if len(linhas) < 3:
        return margem
    passos = [b.topo - a.topo for a, b in zip(linhas, linhas[1:]) if b.topo > a.topo]
    passo = statistics.median(passos) if passos else 0
    if not passo:
        return margem
    primeira, segunda = linhas[0], linhas[1]
    if (primeira.pe < FAIXA_DA_MARGEM * altura and len(primeira.texto) <= TAMANHO_DA_MARGEM
            and segunda.topo - primeira.topo > VAO_DA_MARGEM * passo):
        margem.candidatos.append((primeira, "cabecalho"))
    penultima, ultima = linhas[-2], linhas[-1]
    if (ultima.topo > (1 - FAIXA_DA_MARGEM) * altura and len(ultima.texto) <= TAMANHO_DA_MARGEM
            and ultima.topo - penultima.topo > VAO_DA_MARGEM * passo):
        margem.candidatos.append((ultima, "rodape"))
    return margem


def margens_corridas(paginas: Dict[int, Tuple[Sequence[BoxEntry], int]]) -> Dict[int, set]:
    """Os boxes de cabeçalho, rodapé e poeira de cada página, para sair do texto.

    `paginas` é `{índice: (boxes lidos, altura da página)}`. Uma linha é título
    corrido quando está na faixa de cima (ou de baixo), separada do texto por um
    vão maior que o das linhas, é curta e, além disso, ou tem o número da página
    ou se repete, só nas letras, no mesmo lugar de outra página: o livro alterna
    o nome dos autores nas pares e o título nas ímpares. A primeira linha de um
    capítulo novo não tem número nem se repete, e fica.
    """
    funcoes, margens = _funcoes_das_margens(paginas)
    return {i: set(margens[i].poeira) | set(funcoes[i]) for i in paginas}


def margens_da_pagina(boxes: Sequence[BoxEntry], altura: int) -> set:
    """Os índices de `margens_corridas` de uma página só, com os glifos sem leitura: o □ do
    cabeçalho corrido também é cabeçalho. A fila de revisão os manda para o fim (§8.1).

    A regra roda só nos lidos, como na exportação; contar o □ como glifo mudaria as linhas
    dela (um cisco sem leitura logo abaixo do título fecharia o vão que a regra pede). Depois,
    o sem leitura entra quando o centro dele cai na altura de um glifo de margem e na faixa
    dos glifos de margem dessa altura, com a folga de uma altura de cada lado. O sem leitura
    todo dentro da faixa da poeira (`FAIXA_DA_POEIRA`, em cima ou embaixo) também entra: é o
    cisco da borda da digitalização, que nenhuma linha do texto alcança."""
    lidos = [k for k, b in enumerate(boxes) if b.char]
    margem = {lidos[i] for i in margens_corridas({0: ([boxes[k] for k in lidos], altura)})[0]}
    de_margem = list(margem)
    for k, b in enumerate(boxes):
        if b.char:
            continue
        if b.y2 < FAIXA_DA_POEIRA * altura or b.y1 > (1 - FAIXA_DA_POEIRA) * altura:
            margem.add(k)
            continue
        x, y = (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2
        na_altura = [boxes[m] for m in de_margem if boxes[m].y1 <= y <= boxes[m].y2]
        if na_altura:
            folga = max(m.y2 - m.y1 for m in na_altura)
            if min(m.x1 for m in na_altura) - folga <= x <= max(m.x2 for m in na_altura) + folga:
                margem.add(k)
    return margem


def funcoes_das_margens(paginas: Dict[int, Tuple[Sequence[BoxEntry], int]]) -> Dict[int, dict]:
    """`{página: {indice_do_box: função}}` aprendido no conjunto do livro.

    Ao contrário de :func:`margens_corridas`, poeira não aparece: ela não é cabeçalho
    nem rodapé e requer uma zona `ignorar`, de outro tipo.
    """
    funcoes, _margens = _funcoes_das_margens(paginas)
    return funcoes


def _funcoes_das_margens(paginas: Dict[int, Tuple[Sequence[BoxEntry], int]]
                          ) -> Tuple[Dict[int, dict], Dict[int, _Margem]]:
    margens = {i: _margem_da_pagina(boxes, altura) for i, (boxes, altura) in paginas.items()}
    saida = {i: {} for i in paginas}
    from core import lado_a_jogar

    for i, margem in margens.items():
        for linha, lugar in margem.candidatos:
            # "13.♕b3 0–0–0" no pé da coluna tem o "13" de um número de página,
            # e saía do livro como rodapé.
            if lado_a_jogar.tem_lance(linha.texto):
                continue
            letras = _so_letras(linha.texto)
            numero = bool(_NUMERO_DE_PAGINA.search(linha.texto))
            repete = any(
                lugar == outro_lugar and difflib.SequenceMatcher(
                    None, letras, _so_letras(outra.texto)).ratio() >= SEMELHANCA_DA_MARGEM
                for j, outra_margem in margens.items() if j != i
                for outra, outro_lugar in outra_margem.candidatos)
            if numero or (repete and letras):
                texto = linha.texto.strip()
                funcao = ("numero_de_pagina" if re.fullmatch(r"\D*\d{1,4}\D*", texto)
                          and not letras else lugar)
                saida[i].update({indice: funcao for indice in linha.indices})
    return saida, margens


#: Quantas páginas precisam concordar no deslocamento para o número impresso valer.
CONCORDANCIA_DOS_NUMEROS = 2


def numeros_impressos(paginas: Dict[int, Tuple[Sequence[BoxEntry], "Estrutura"]],
                      funcoes: Dict[int, dict],
                      todas: Optional[Iterable[int]] = None) -> Dict[int, int]:
    """`{índice da página: número impresso}`, pelos números das margens.

    Os candidatos são os números nas linhas de margem: as que a regra das margens achou
    (`funcoes`, índice do box -> função) e as das áreas de cabeçalho, rodapé e número de
    página da `Estrutura`. Cada número dá um **deslocamento** (número − índice); cada página
    fica com o seu deslocamento mais votado no livro (o OCR erra números, "2l", e um
    cabeçalho tem outros, "Problema 41"). A paginação vale **por trechos**: páginas
    seguidas com o mesmo deslocamento, ao menos `CONCORDANCIA_DOS_NUMEROS`, formam um
    trecho, e cada página das pedidas (`todas`, ou as de `paginas`) recebe o do último
    trecho que começa nela ou antes (o encarte de fotos que o livro não numera muda o
    deslocamento dali em diante). Número ≤ 0 não sai. Sem trecho, `{}`."""
    from collections import Counter

    por_pagina: Dict[int, set] = {}
    for indice, (boxes, estrutura) in paginas.items():
        das_margens = funcoes.get(indice, {})
        margem = [b for k, b in enumerate(boxes) if k in das_margens
                  or estrutura.funcao(b) in FUNCOES_DE_MARGEM]
        vistos = set()
        for linha in _linhas(margem, OrdemDeLeitura()) if margem else []:
            for numero in _NUMERO_DE_PAGINA.findall(linha.texto):
                vistos.add(int(numero) - indice)
        if vistos:
            por_pagina[indice] = vistos
    votos: Counter = Counter(d for vistos in por_pagina.values() for d in vistos)
    escolhido = {i: max(sorted(v), key=lambda d: votos[d]) for i, v in por_pagina.items()}
    trechos: List[Tuple[int, int]] = []           # (primeira página, deslocamento)
    corrida: List[int] = []

    def fechar() -> None:
        if len(corrida) >= CONCORDANCIA_DOS_NUMEROS:
            trechos.append((corrida[0], escolhido[corrida[0]]))

    for i in sorted(escolhido):
        if corrida and escolhido[i] != escolhido[corrida[-1]]:
            fechar()
            corrida = []
        corrida.append(i)
    fechar()
    if not trechos:
        return {}
    saida = {}
    for i in sorted(todas if todas is not None else paginas):
        deslocamento = trechos[0][1]
        for comeco, d in trechos:
            if comeco <= i:
                deslocamento = d
        if i + deslocamento >= 1:
            saida[i] = i + deslocamento
    return saida


def _funcoes_dos_candidatos(paginas: Dict[int, Tuple[Sequence[BoxEntry], int]]) -> Dict[int, dict]:
    """As linhas candidatas a margem de cada página (posição, vão e tamanho), sem a
    comparação entre páginas de `_funcoes_das_margens`: para achar o número impresso basta
    o número delas, e a comparação custa n² no livro."""
    saida = {}
    for i, (boxes, altura) in paginas.items():
        margem = _margem_da_pagina(boxes, altura)
        saida[i] = {k: lugar for linha, lugar in margem.candidatos for k in linha.indices}
    return saida
