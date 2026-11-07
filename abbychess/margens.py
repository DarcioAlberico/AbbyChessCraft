"""As margens corridas e os números impressos (§12.1): o cabeçalho, o rodapé e o número de
página que se repetem entre páginas saem do texto exportado, e o número impresso de cada página
vira o rótulo dela. Puro: recebe as linhas da montagem (`montagem`). À parte de `exportar.py`
(SPEC-qualidade Q-E6, CA-Q-A1)."""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from core.box_model import BoxEntry

from abbychess.layout import OrdemDeLeitura
from abbychess.montagem import FUNCOES_DE_MARGEM, Estrutura, _Linha, _linhas, _passo_mediano


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
#: Quanto a linha colada no texto (sem o vão de `VAO_DA_MARGEM`) precisa se parecer com um
#: título corrido confirmado para sair como ele. Mais alto que o da repetição: sem o vão, a
#: posição diz menos, e "XADREZ BRASILEIRO" (0,69 contra "xadrezvitorioso") é outro título.
SEMELHANCA_DO_CONFIRMADO = 0.8
#: As funções de área que dizem título corrido; o número de página sozinho não tem letras.
LUGARES_CONFIRMAVEIS = ("cabecalho", "rodape")
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


@dataclass(frozen=True)
class Confirmado:
    """Um título corrido que o usuário confirmou (§5.1): as letras da área de cabeçalho ou de
    rodapé que ele desenhou ou cuja função trocou, e a paridade da página, porque o livro
    alterna o nome dos autores nas pares e o título nas ímpares."""

    paridade: int
    lugar: str
    letras: str


def confirmados_das_areas(paginas: Dict[int, Tuple[Sequence[BoxEntry], Sequence]]
                          ) -> List[Confirmado]:
    """Os títulos corridos confirmados do livro, de `{página: (boxes lidos, áreas)}`, sem
    repetição e na ordem das páginas. Vale a área de cabeçalho ou de rodapé que não é
    automática (a que a regra achou sozinha não confirma nada) e tem letras."""
    saida: List[Confirmado] = []
    for indice in sorted(paginas):
        boxes, areas = paginas[indice]
        for area in areas:
            confirmado = _confirmado_da_area(indice, boxes, area)
            if confirmado is not None and confirmado not in saida:
                saida.append(confirmado)
    return saida


def _confirmado_da_area(indice: int, boxes: Sequence[BoxEntry], area) -> Optional[Confirmado]:
    """O título corrido da área da página, se o usuário a marcou como cabeçalho ou rodapé e
    há letras nela; senão, None."""
    if area.automatica or area.funcao not in LUGARES_CONFIRMAVEIS:
        return None
    dentro = [b for b in boxes if b.char and area.contem_o_centro(b)]
    if not dentro:
        return None
    letras = _so_letras(" ".join(linha.texto for linha in _linhas(dentro, OrdemDeLeitura())))
    return Confirmado(indice % 2, area.funcao, letras) if letras else None


def _aprendidos(confirmados: Sequence[Confirmado], indice: int) -> Dict[str, List[str]]:
    """As letras dos confirmados da paridade da página, por lugar."""
    saida: Dict[str, List[str]] = {lugar: [] for lugar in LUGARES_CONFIRMAVEIS}
    for c in confirmados:
        if c.paridade == indice % 2:
            saida[c.lugar].append(c.letras)
    return saida


def _parece(letras: str, modelos: Sequence[str], limiar: float) -> bool:
    """As letras se parecem, ao menos `limiar`, com as de algum dos `modelos`."""
    return bool(letras) and any(
        difflib.SequenceMatcher(None, letras, modelo).ratio() >= limiar for modelo in modelos)


def _so_letras(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", sem_acento.lower())


def _margem_da_pagina(boxes: Sequence[BoxEntry], altura: int,
                      aprendidos: Optional[Dict[str, List[str]]] = None) -> _Margem:
    margem = _Margem()
    # De cima para baixo, sem os trechos de coluna: o cabeçalho `Games 7`, com o
    # título numa coluna e o número na outra, é uma linha só, a primeira.
    linhas = _linhas(boxes, OrdemDeLeitura())
    if not linhas or not altura:
        return margem
    linhas = _sem_a_poeira(linhas, altura, margem)
    if len(linhas) < 3:
        return margem
    passo = _passo_mediano(linhas)
    if not passo:
        return margem
    margem.candidatos += _candidatos_da_margem(linhas, altura, passo, aprendidos or {})
    return margem


def _sem_a_poeira(linhas: List[_Linha], altura: int, margem: _Margem) -> List[_Linha]:
    """As linhas sem a poeira da borda, que vai à `margem`."""
    poeira = [linha for linha in linhas if _e_poeira(linha, altura)]
    for linha in poeira:
        margem.poeira.extend(linha.indices)
    return [linha for linha in linhas if linha not in poeira]


def _e_poeira(linha: _Linha, altura: int) -> bool:
    """Um ou dois caracteres na borda extrema da página (`FAIXA_DA_POEIRA`)."""
    return len(linha.texto.replace(" ", "")) <= 2 and (
        linha.pe < FAIXA_DA_POEIRA * altura or linha.topo > (1 - FAIXA_DA_POEIRA) * altura)


def _candidatos_da_margem(linhas: List[_Linha], altura: int, passo: float,
                          aprendidos: Dict[str, List[str]]) -> List[Tuple[_Linha, str]]:
    """A primeira linha na faixa de cima e a última na de baixo, curtas e separadas do texto
    por um vão maior que o das linhas; sem o vão, a que se parece muito com um título corrido
    confirmado do mesmo lugar (`aprendidos`, §5.1)."""
    candidatos = []
    primeira, segunda = linhas[0], linhas[1]
    if (primeira.pe < FAIXA_DA_MARGEM * altura and len(primeira.texto) <= TAMANHO_DA_MARGEM
            and _separada(primeira, segunda.topo - primeira.topo, passo,
                          aprendidos.get("cabecalho", ()))):
        candidatos.append((primeira, "cabecalho"))
    penultima, ultima = linhas[-2], linhas[-1]
    if (ultima.topo > (1 - FAIXA_DA_MARGEM) * altura and len(ultima.texto) <= TAMANHO_DA_MARGEM
            and _separada(ultima, ultima.topo - penultima.topo, passo,
                          aprendidos.get("rodape", ()))):
        candidatos.append((ultima, "rodape"))
    return candidatos


def _separada(linha: _Linha, vao: float, passo: float, confirmados: Sequence[str]) -> bool:
    """A linha tem o vão das margens, ou é um título corrido confirmado colado no texto."""
    return vao > VAO_DA_MARGEM * passo or _parece(_so_letras(linha.texto), confirmados,
                                                  SEMELHANCA_DO_CONFIRMADO)


def margens_corridas(paginas: Dict[int, Tuple[Sequence[BoxEntry], int]],
                     confirmados: Sequence[Confirmado] = ()) -> Dict[int, set]:
    """Os boxes de cabeçalho, rodapé e poeira de cada página, para sair do texto.

    `paginas` é `{índice: (boxes lidos, altura da página)}`. Uma linha é título
    corrido quando está na faixa de cima (ou de baixo), separada do texto por um
    vão maior que o das linhas, é curta e, além disso, ou tem o número da página
    ou se repete, só nas letras, no mesmo lugar de outra página: o livro alterna
    o nome dos autores nas pares e o título nas ímpares. A primeira linha de um
    capítulo novo não tem número nem se repete, e fica. Os `confirmados` (§5.1) valem como
    repetição na paridade deles, e também sem o vão quando a linha se parece muito com um.
    """
    funcoes, margens = _funcoes_das_margens(paginas, confirmados)
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
        if _na_poeira(b, altura) or _na_faixa_da_margem(b, boxes, de_margem):
            margem.add(k)
    return margem


def _na_poeira(b: BoxEntry, altura: int) -> bool:
    """O box todo dentro da faixa da poeira, em cima ou embaixo."""
    return b.y2 < FAIXA_DA_POEIRA * altura or b.y1 > (1 - FAIXA_DA_POEIRA) * altura


def _na_faixa_da_margem(b: BoxEntry, boxes: Sequence[BoxEntry], de_margem: List[int]) -> bool:
    """O centro do box na altura de um glifo de margem e na faixa dos glifos de margem dessa
    altura, com a folga de uma altura de cada lado."""
    x, y = (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2
    na_altura = [boxes[m] for m in de_margem if boxes[m].y1 <= y <= boxes[m].y2]
    if not na_altura:
        return False
    folga = max(m.y2 - m.y1 for m in na_altura)
    return min(m.x1 for m in na_altura) - folga <= x <= max(m.x2 for m in na_altura) + folga


def funcoes_das_margens(paginas: Dict[int, Tuple[Sequence[BoxEntry], int]],
                        confirmados: Sequence[Confirmado] = ()) -> Dict[int, dict]:
    """`{página: {indice_do_box: função}}` aprendido no conjunto do livro e nos títulos
    corridos `confirmados`.

    Ao contrário de :func:`margens_corridas`, poeira não aparece: ela não é cabeçalho
    nem rodapé e requer uma zona `ignorar`, de outro tipo.
    """
    funcoes, _margens = _funcoes_das_margens(paginas, confirmados)
    return funcoes


def _funcoes_das_margens(paginas: Dict[int, Tuple[Sequence[BoxEntry], int]],
                         confirmados: Sequence[Confirmado] = ()
                         ) -> Tuple[Dict[int, dict], Dict[int, _Margem]]:
    aprendidos = {i: _aprendidos(confirmados, i) for i in paginas}
    margens = {i: _margem_da_pagina(boxes, altura, aprendidos[i])
               for i, (boxes, altura) in paginas.items()}
    saida = {i: {} for i in paginas}
    for i, margem in margens.items():
        for linha, lugar in margem.candidatos:
            funcao = _funcao_da_margem(i, linha, lugar, margens, aprendidos[i])
            if funcao:
                saida[i].update({indice: funcao for indice in linha.indices})
    return saida, margens


def _funcao_da_margem(i: int, linha: _Linha, lugar: str, margens: Dict[int, _Margem],
                      aprendidos: Optional[Dict[str, List[str]]] = None) -> str:
    """A função da linha candidata da página `i`: o número de página, o cabeçalho ou o rodapé
    (o `lugar`), se ela tem o número da página, se repete noutra ou se parece com um título
    corrido confirmado do mesmo lugar (`aprendidos`); vazia se fica no texto."""
    from core import lado_a_jogar

    # "13.♕b3 0–0–0" no pé da coluna tem o "13" de um número de página,
    # e saía do livro como rodapé.
    if lado_a_jogar.tem_lance(linha.texto):
        return ""
    letras = _so_letras(linha.texto)
    numero = bool(_NUMERO_DE_PAGINA.search(linha.texto))
    repete = (_repete(i, letras, lugar, margens)
              or _parece(letras, (aprendidos or {}).get(lugar, ()), SEMELHANCA_DA_MARGEM))
    if not (numero or (repete and letras)):
        return ""
    texto = linha.texto.strip()
    return "numero_de_pagina" if re.fullmatch(r"\D*\d{1,4}\D*", texto) and not letras else lugar


def _repete(i: int, letras: str, lugar: str, margens: Dict[int, _Margem]) -> bool:
    """As letras se parecem com as de uma candidata do mesmo lugar noutra página."""
    return any(
        lugar == outro_lugar and difflib.SequenceMatcher(
            None, letras, _so_letras(outra.texto)).ratio() >= SEMELHANCA_DA_MARGEM
        for j, outra_margem in margens.items() if j != i
        for outra, outro_lugar in outra_margem.candidatos)


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
    por_pagina: Dict[int, set] = {}
    for indice, (boxes, estrutura) in paginas.items():
        vistos = _deslocamentos(indice, boxes, estrutura, funcoes.get(indice, {}))
        if vistos:
            por_pagina[indice] = vistos
    trechos = _trechos(_mais_votados(por_pagina))
    if not trechos:
        return {}
    return _numeros_pelos_trechos(trechos, sorted(todas if todas is not None else paginas))


def _deslocamentos(indice: int, boxes: Sequence[BoxEntry], estrutura: "Estrutura",
                   das_margens: dict) -> set:
    """Os deslocamentos (número − índice) dos números nas linhas de margem da página."""
    margem = [b for k, b in enumerate(boxes) if k in das_margens
              or estrutura.funcao(b) in FUNCOES_DE_MARGEM]
    vistos = set()
    for linha in _linhas(margem, OrdemDeLeitura()) if margem else []:
        for numero in _NUMERO_DE_PAGINA.findall(linha.texto):
            vistos.add(int(numero) - indice)
    return vistos


def _mais_votados(por_pagina: Dict[int, set]) -> Dict[int, int]:
    """O deslocamento de cada página: o dela mais votado no livro (no empate, o menor)."""
    from collections import Counter

    votos: Counter = Counter(d for vistos in por_pagina.values() for d in vistos)
    return {i: max(sorted(v), key=lambda d: votos[d]) for i, v in por_pagina.items()}


def _trechos(escolhido: Dict[int, int]) -> List[Tuple[int, int]]:
    """(primeira página, deslocamento) de cada corrida de páginas seguidas com o mesmo
    deslocamento, de ao menos `CONCORDANCIA_DOS_NUMEROS` páginas."""
    trechos: List[Tuple[int, int]] = []
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
    return trechos


def _numeros_pelos_trechos(trechos: List[Tuple[int, int]], indices: Iterable[int]
                           ) -> Dict[int, int]:
    """O número de cada página pelo último trecho que começa nela ou antes; ≤ 0 não sai."""
    saida = {}
    for i in indices:
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
