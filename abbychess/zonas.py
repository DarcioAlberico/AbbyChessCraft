"""As áreas da página, como as do FineReader: o que é texto, diagrama, imagem ou nada.

A segmentação automática erra o tipo das regiões de vez em quando: um diagrama
sem moldura vira texto, o cabeçalho corrido entra no meio da prosa, uma foto
enche a página de boxes. As áreas corrigem isso antes da leitura:

- **texto** é segmentado em glifos e lido, como sempre;
- **diagrama** vira tabuleiro (a lista `tabuleiros` de `segmentar_pagina`) e
  nenhum box de texto sai de dentro dele;
- **imagem** e **ignorar** não geram box nenhum. A diferença entre as duas é só
  o que a exportação fará com a região: a imagem é conservada, o resto não.

As áreas automáticas saem da segmentação atual: um bloco de texto por
parágrafo e um diagrama por tabuleiro, com a margem das coordenadas. O usuário
corrige o que estiver errado e reconhece de novo.

Com áreas gravadas, **só o que está dentro de uma área de texto vira box**,
como no FineReader. Áreas que se sobrepõem obedecem à mais restritiva: ignorar
e imagem vencem diagrama, que vence texto. Uma página sem áreas gravadas é lida
como antes, pela segmentação inteira.

Aqui não há Qt: o visor só desenha e devolve coordenadas, e a geometria de
criar, mover e esticar uma área está em funções puras, testadas sem tela.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from statistics import median
from typing import Iterable, List, Optional, Sequence, Tuple

from core.box_model import BoxEntry

from abbychess.layout import partes_pelo_vao
from abbychess.modelo import LETRAS_DAS_PECAS

TEXTO = "texto"
DIAGRAMA = "diagrama"
IMAGEM = "imagem"
IGNORAR = "ignorar"

#: Na ordem das teclas 1 a 4 do editor de áreas.
TIPOS = (TEXTO, DIAGRAMA, IMAGEM, IGNORAR)

NOMES = {TEXTO: "Texto", DIAGRAMA: "Diagrama", IMAGEM: "Imagem", IGNORAR: "Ignorar"}

#: A função da área no documento (SPEC §4.2). O tipo diz como a área é lida; a função,
#: o que o texto dela é. Uma área de texto pode ser corpo, título, cabeçalho corrido,
#: rodapé, número de página, nota ou legenda.
FUNCOES = ("texto", "titulo", "cabecalho", "rodape", "numero_de_pagina", "nota", "legenda",
           "diagrama", "figura", "tabela", "ignorar")
NOMES_DAS_FUNCOES = {
    "texto": "Texto", "titulo": "Título", "cabecalho": "Cabeçalho", "rodape": "Rodapé",
    "numero_de_pagina": "Nº de página", "nota": "Nota", "legenda": "Legenda",
    "diagrama": "Diagrama", "figura": "Imagem", "tabela": "Tabela", "ignorar": "Ignorar",
}
#: O tipo que cada função dá à área.
TIPO_DA_FUNCAO = {"texto": TEXTO, "titulo": TEXTO, "cabecalho": TEXTO, "rodape": TEXTO,
                  "numero_de_pagina": TEXTO, "nota": TEXTO, "legenda": TEXTO,
                  "diagrama": DIAGRAMA, "figura": IMAGEM, "tabela": IMAGEM, "ignorar": IGNORAR}
#: A função que escolher um tipo dá (até o passo F trazer a tabela como tipo próprio).
FUNCAO_DO_TIPO = {TEXTO: "texto", DIAGRAMA: "diagrama", IMAGEM: "figura", IGNORAR: "ignorar"}

#: Quem vence quando duas áreas cobrem o mesmo ponto: o maior.
PRIORIDADE = {TEXTO: 0, DIAGRAMA: 1, IMAGEM: 2, IGNORAR: 3}

#: Menor lado de uma área, em pixels da página. Menos que isso é um clique.
MENOR_LADO = 8

#: Folga em volta de um bloco de texto automático, em alturas de caractere.
FOLGA_DO_BLOCO = 0.4

#: Um vão maior que isto entre duas linhas, em alturas de linha, começa outro bloco.
VAO_ENTRE_BLOCOS = 1.2

#: Uma legenda fica encostada ao diagrama; a especificação admite acima ou abaixo.
DISTANCIA_DA_LEGENDA = 4.0
#: O corpo de um título é pelo menos 1,3 vez o corpo do texto (SPEC §5.1).
RAZAO_DO_TITULO = 1.3
RAZAO_DA_NOTA = 0.82
RECUO_DE_PARAGRAFO = 1.2

_INICIO_DA_LEGENDA = re.compile(r"^\s*(?:diagrama|diagram|teste|test|exerc[ií]cio|exercise)\b",
                                re.IGNORECASE)
_SO_O_NUMERO = re.compile(r"^\s*\d+\.?\s*$")
_TEXTO_DA_LEGENDA = re.compile(r"\b(?:jogam?|joga|to\s+play|white\s+to|black\s+to)\b",
                               re.IGNORECASE)
#: A legenda é curta (§5.1): um parágrafo de prosa abaixo do diagrama não é legenda.
TAMANHO_DA_LEGENDA = 80
#: A linha que continua a legenda (os jogadores, o lugar e o ano) é mais curta ainda.
TAMANHO_DA_CONTINUACAO = 50
#: O vão que parte uma linha em duas zonas (em alturas de glifo) e os glifos de cada lado.
VAO_QUE_PARTE, GLIFOS_DE_CADA_LADO = 8.0, 3
#: Um lance numerado ("1.e4", "10...Rf8"): a linha de lances não é título.
_LANCE = re.compile(r"\b\d{1,3}\s*\.{1,3}\s*\S")
#: Um lance pela casa de chegada ("exf4", "Cf3", "f5", "O-O"), também no texto da área,
#: que vem sem espaços: a linha de lances com o número mal lido ("2lI.exf4") ainda tem as
#: casas. E o que só lance tem: a peça (a letra de qualquer idioma, `modelo.LETRAS_DAS_PECAS`),
#: a captura ou o sinal colado na casa.
_CASA_DO_LANCE = re.compile(rf"[{LETRAS_DAS_PECAS}]?x?[a-h][1-8]|[O0]-[O0]")
_SO_DE_LANCE = re.compile(rf"[{LETRAS_DAS_PECAS}][a-h]?[1-8]?x?[a-h][1-8]|[a-h]x[a-h][1-8]"
                          r"|[a-h][1-8][+#?!]|[O0]-[O0]")


def _parece_lances(texto: str) -> bool:
    """A linha de lances: o número do lance, ou duas casas de chegada com uma peça, uma
    captura ou um sinal ("de 1972 e 1980" tem as casas e não é lance)."""
    return bool(_LANCE.search(texto)) or (len(_CASA_DO_LANCE.findall(texto)) >= 2
                                          and bool(_SO_DE_LANCE.search(texto)))
_NUMERO_DE_PAGINA = re.compile(r"^\s*(?:p(?:ág(?:ina)?|age)?\.?\s*)?\d+\s*$", re.IGNORECASE)

Caixa = Tuple[int, int, int, int]


@dataclass(frozen=True)
class ModeloDeAreas:
    """Zonas de uma página que podem ser reaplicadas somente na mesma resolução."""

    largura: int
    altura: int
    zonas: Tuple["Zona", ...]

    def aplicar(self, largura: int, altura: int) -> List["Zona"]:
        if (largura, altura) != (self.largura, self.altura):
            raise ValueError("A resolução da página é diferente da resolução do modelo.")
        # IDs pertencem à página de origem; a página de destino ganha os seus.
        return com_ids([replace(z, id="", diagrama_id=None) for z in self.zonas])


@dataclass(frozen=True)
class Zona:
    tipo: str
    x1: int
    y1: int
    x2: int
    y2: int
    #: Estável na página (`z0`, `z1`…): é a que o documento e as decisões citam.
    id: str = ""
    #: Vazia = a função padrão do tipo (`FUNCAO_DO_TIPO`).
    funcao: str = ""
    #: A posição da área na ordem de leitura do documento; `None` = pela posição na página.
    ordem: Optional[int] = None
    #: Veio das áreas automáticas (o layout pode dividi-la; a do usuário, não).
    automatica: bool = False
    #: O diagrama `dN` ao qual esta legenda pertence; vazio nas outras funções.
    diagrama_id: Optional[str] = None

    def __post_init__(self):
        if not self.funcao:
            object.__setattr__(self, "funcao", FUNCAO_DO_TIPO.get(self.tipo, "texto"))
        if self.funcao not in FUNCOES:
            raise ValueError(f"Função de área desconhecida: {self.funcao!r}")
        if TIPO_DA_FUNCAO[self.funcao] != self.tipo:
            raise ValueError(f"A função {self.funcao!r} não é de uma área do tipo {self.tipo!r}")
        if self.funcao != "legenda" and self.diagrama_id is not None:
            object.__setattr__(self, "diagrama_id", None)

    @property
    def caixa(self) -> Caixa:
        return self.x1, self.y1, self.x2, self.y2

    def contem(self, x: float, y: float) -> bool:
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2

    def contem_o_centro(self, caixa) -> bool:
        """O glifo (qualquer coisa com x1, y1, x2, y2) é da área quando o centro dele cai nela."""
        return self.contem((caixa.x1 + caixa.x2) / 2, (caixa.y1 + caixa.y2) / 2)

    def como_dict(self) -> dict:
        return {"id": self.id, "tipo": self.tipo, "funcao": self.funcao, "caixa": list(self.caixa),
                "ordem": self.ordem, "automatica": self.automatica,
                "diagrama_id": self.diagrama_id}

    @classmethod
    def de_dict(cls, dados: dict) -> "Zona":
        """Também lê o formato v1 (só `tipo` e `caixa`)."""
        tipo = dados.get("tipo", TEXTO)
        if tipo not in TIPOS:
            raise ValueError(f"Tipo de área desconhecido: {tipo!r}")
        x1, y1, x2, y2 = (int(v) for v in dados["caixa"])
        ordem = dados.get("ordem")
        return cls(tipo, x1, y1, x2, y2, id=str(dados.get("id") or ""),
                   funcao=str(dados.get("funcao") or ""),
                   ordem=None if ordem is None else int(ordem),
                   automatica=bool(dados.get("automatica", False)),
                   diagrama_id=str(dados.get("diagrama_id") or "") or None)


def ids_livres(itens: Sequence, prefixo: str) -> list:
    """Os itens (dataclasses com `id`) com `id` cada um: os que não têm ganham o próximo
    `<prefixo>N` livre. A regra das áreas (`zN`) e a dos diagramas (`dN`)."""
    usados = {i.id for i in itens if i.id}
    proximo, saida = 0, []
    for item in itens:
        if not item.id:
            while f"{prefixo}{proximo}" in usados:
                proximo += 1
            item = replace(item, id=f"{prefixo}{proximo}")
            usados.add(item.id)
        saida.append(item)
    return saida


def com_ids(zonas: Sequence[Zona]) -> List[Zona]:
    """As áreas com `id` cada uma: as que não têm ganham o próximo `zN` livre."""
    return ids_livres(zonas, "z")


def nova(tipo: str, caixa: Caixa, largura: int, altura: int) -> Zona:
    """A área com os cantos em ordem e dentro da página; erro se ficar pequena demais."""
    if tipo not in TIPOS:
        raise ValueError(f"Tipo de área desconhecido: {tipo!r}")
    x1, y1, x2, y2 = caixa
    x1, x2 = sorted((int(x1), int(x2)))
    y1, y2 = sorted((int(y1), int(y2)))
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(largura, x2), min(altura, y2)
    if x2 - x1 < MENOR_LADO or y2 - y1 < MENOR_LADO:
        raise ValueError("A área é pequena demais ou está fora da página.")
    return Zona(tipo, x1, y1, x2, y2)


# ----------------------------------------------------------------------
# Editar: achar, mover, esticar
# ----------------------------------------------------------------------

def zona_em(zonas: Sequence[Zona], x: float, y: float) -> Optional[int]:
    """A área sob o ponto; com várias, a menor, que é a que o usuário mira."""
    achadas = [((z.x2 - z.x1) * (z.y2 - z.y1), i) for i, z in enumerate(zonas) if z.contem(x, y)]
    return min(achadas)[1] if achadas else None


def zona_que_vale(zonas: Sequence[Zona], x: float, y: float) -> Optional[Zona]:
    """A área que vale no ponto quando mais de uma o cobre (§5): a desenhada ou mexida pelo
    usuário antes da automática, e entre elas a menor. A mesma regra no Documento, na
    exportação e na medida (antes, cada um ficava com uma: a primeira, a menor…)."""
    achadas = [z for z in zonas if z.contem(x, y)]
    if not achadas:
        return None
    return min(achadas, key=lambda z: (z.automatica, (z.x2 - z.x1) * (z.y2 - z.y1)))


def na_ordem_das_areas(itens: Sequence, ordem_de) -> list:
    """Os itens de área ordenada (`ordem_de(item)` não é `None`) seguem a ordem dela, nos lugares
    que já ocupavam; o resto fica onde está. A mesma regra no Documento e na exportação."""
    posicoes = [i for i, item in enumerate(itens) if ordem_de(item) is not None]
    ordenados = sorted((itens[i] for i in posicoes), key=ordem_de)
    saida = list(itens)
    for i, item in zip(posicoes, ordenados):
        saida[i] = item
    return saida


def area_do_tabuleiro(zonas: Sequence[Zona], caixa) -> Optional[Zona]:
    """A área de diagrama que vale no centro da caixa do tabuleiro."""
    return zona_que_vale([z for z in zonas if z.tipo == DIAGRAMA],
                         (caixa[0] + caixa[2]) / 2, (caixa[1] + caixa[3]) / 2)


def ordem_do_tabuleiro(zonas: Sequence[Zona], caixa) -> Optional[int]:
    """A ordem da área de diagrama do tabuleiro."""
    area = area_do_tabuleiro(zonas, caixa)
    return None if area is None else area.ordem


def zona_da_maioria(zonas: Sequence[Zona], boxes: Sequence[BoxEntry]) -> Optional[Zona]:
    """A área que vale para a maioria dos glifos de uma linha (pelo centro de cada um). O
    centro da linha inteira engana: uma linha que pega as coordenadas do tabuleiro (a-h)
    junto da legenda tem o centro dentro do diagrama."""
    votos: dict = {}
    for b in boxes:
        zona = zona_que_vale(zonas, (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2)
        if zona is not None:
            votos[id(zona)] = (votos.get(id(zona), (0, zona))[0] + 1, zona)
    return max(votos.values(), key=lambda v: v[0])[1] if votos else None


def bordas_em(zona: Zona, x: float, y: float, tolerancia: float) -> str:
    """Quais bordas da área estão sob o ponto: letras de "ecdb" (esquerda, cima,
    direita, baixo). Num canto vêm duas. Vazio é o miolo, que move a área."""
    if not (zona.x1 - tolerancia <= x <= zona.x2 + tolerancia
            and zona.y1 - tolerancia <= y <= zona.y2 + tolerancia):
        return ""
    bordas = ""
    if abs(x - zona.x1) <= tolerancia:
        bordas += "e"
    elif abs(x - zona.x2) <= tolerancia:
        bordas += "d"
    if abs(y - zona.y1) <= tolerancia:
        bordas += "c"
    elif abs(y - zona.y2) <= tolerancia:
        bordas += "b"
    return bordas


def arrastar(zona: Zona, bordas: str, dx: float, dy: float, largura: int, altura: int) -> Zona:
    """A área depois de um arraste: sem bordas, move inteira; com elas, estica só essas.

    Mover para no limite da página sem deformar a área; esticar não deixa um
    lado passar do outro.
    """
    dx, dy = int(round(dx)), int(round(dy))
    x1, y1, x2, y2 = zona.caixa
    if not bordas:
        dx = min(max(dx, -x1), largura - x2)
        dy = min(max(dy, -y1), altura - y2)
        return replace(zona, x1=x1 + dx, y1=y1 + dy, x2=x2 + dx, y2=y2 + dy, automatica=False)
    if "e" in bordas:
        x1 = min(max(0, x1 + dx), x2 - MENOR_LADO)
    if "d" in bordas:
        x2 = max(min(largura, x2 + dx), x1 + MENOR_LADO)
    if "c" in bordas:
        y1 = min(max(0, y1 + dy), y2 - MENOR_LADO)
    if "b" in bordas:
        y2 = max(min(altura, y2 + dy), y1 + MENOR_LADO)
    return replace(zona, x1=x1, y1=y1, x2=x2, y2=y2, automatica=False)


def trocar_tipo(zonas: List[Zona], indice: int, tipo: str) -> None:
    if tipo not in TIPOS:
        raise ValueError(f"Tipo de área desconhecido: {tipo!r}")
    # Mexida pelo usuário, a zona deixa de ser automática: a aprendizagem das margens e a
    # exportação não a reclassificam, e o endireitar a mantém (§5.1).
    zonas[indice] = replace(zonas[indice], tipo=tipo, funcao=FUNCAO_DO_TIPO[tipo],
                            diagrama_id=None, automatica=False)


def trocar_funcao(zonas: List[Zona], indice: int, funcao: str) -> None:
    """Troca a função e deriva dela o tipo da zona."""
    if funcao not in FUNCOES:
        raise ValueError(f"Função de área desconhecida: {funcao!r}")
    zonas[indice] = replace(zonas[indice], tipo=TIPO_DA_FUNCAO[funcao], funcao=funcao,
                            diagrama_id=(zonas[indice].diagrama_id
                                         if funcao == "legenda" else None),
                            automatica=False)


def ordenar(zonas: Sequence[Zona], indices: Sequence[int]) -> List[Zona]:
    """Grava a ordem escolhida; cada zona deve aparecer exatamente uma vez."""
    if sorted(indices) != list(range(len(zonas))):
        raise ValueError("A ordem deve conter cada área exatamente uma vez.")
    posicao = {indice: ordem for ordem, indice in enumerate(indices)}
    return [replace(zona, ordem=posicao[i]) for i, zona in enumerate(zonas)]


# ----------------------------------------------------------------------
# Áreas automáticas
# ----------------------------------------------------------------------

def automaticas(boxes: Sequence[BoxEntry], tabuleiros: Iterable[Caixa],
                largura: int, altura: int, escala: Optional[float] = None) -> List[Zona]:
    """As áreas que a segmentação atual sugere: blocos de texto e diagramas.

    Cada tabuleiro vira um diagrama com a margem das coordenadas a-h e 1-8, a
    mesma `MARGEM_DO_TABULEIRO` com que `segmentar_pagina` tira os boxes de
    dentro dele. O texto vira um bloco por grupo de linhas sem vão grande entre
    elas, que na prática é um por parágrafo, título ou número de página.
    """
    from abbychess.pagina import MARGEM_DO_TABULEIRO

    if escala is None:
        escala = median(b.y2 - b.y1 for b in boxes) if boxes else 20
    zonas: List[Zona] = []
    m = int(round(escala * MARGEM_DO_TABULEIRO))
    for x1, y1, x2, y2 in tabuleiros:
        zonas.append(nova(DIAGRAMA, (x1 - m, y1 - m, x2 + m, y2 + m), largura, altura))
    folga = max(2, int(round(escala * FOLGA_DO_BLOCO)))
    for bloco in _blocos(_linhas(boxes), escala):
        x1, y1, x2, y2 = bloco
        try:
            zonas.append(nova(TEXTO, (x1 - folga, y1 - folga, x2 + folga, y2 + folga),
                              largura, altura))
        except ValueError:
            continue
    zonas = com_ids([replace(z, automatica=True) for z in zonas])
    return classificar_funcoes(zonas, boxes, largura, altura, escala)


def classificar_funcoes(zonas: Sequence[Zona], boxes: Sequence[BoxEntry],
                        largura: int, altura: int, escala: float) -> List[Zona]:
    """Classifica as zonas automáticas sem alterar uma zona desenhada pelo usuário.

    Esta é a etapa local do pipeline de layout: legenda, número de página e título.
    Cabeçalhos corridos dependem de aprender repetições entre páginas e ficam na etapa
    do livro. Quando os boxes ainda não foram lidos, as regras que dependem de texto apenas
    não disparam.
    """
    classificacao = _Classificacao(zonas, boxes, largura, altura, escala)
    saida = [classificacao.zona(zona) if zona.automatica and zona.tipo == TEXTO else zona
             for zona in zonas]
    return _continuacoes_da_legenda(saida, boxes, escala)


class _Classificacao:
    """O que a página diz a `classificar_funcoes`: as zonas e os diagramas dela, o tamanho,
    a escala, o corpo do texto e o das maiúsculas."""

    def __init__(self, zonas: Sequence[Zona], boxes: Sequence[BoxEntry], largura: int,
                 altura: int, escala: float):
        self.zonas, self.boxes = zonas, boxes
        self.largura, self.altura, self.escala = largura, altura, escala
        self.diagramas = [z for z in zonas if z.funcao == "diagrama"]
        alturas = [b.y2 - b.y1 for b in boxes if b.char]
        self.corpo = median(alturas) if alturas else float(escala)
        # O corpo das maiúsculas e dos algarismos (o percentil 90): uma linha de lances, cheia
        # deles, tem a mediana alta sem ser de letra maior; o título tem as maiúsculas maiores.
        self.maiusculas = _percentil(alturas, 0.9) if alturas else float(escala)

    def zona(self, zona: Zona) -> Zona:
        """A zona automática de texto com a função que o texto dela diz."""
        dentro = [b for b in self.boxes if zona.contem_o_centro(b)]
        texto = _texto_dos_boxes(dentro)
        if not texto:
            return replace(zona, funcao="texto")
        if len(texto) <= 2 and not any(c.isalnum() for c in texto):
            # Poeira da digitalização (um ponto, um traço soltos): fica fora do texto.
            return replace(zona, tipo=IGNORAR, funcao="ignorar")
        return replace(zona, funcao=self.funcao(zona, dentro, texto))

    def funcao(self, zona: Zona, dentro: Sequence[BoxEntry], texto: str) -> str:
        """Número de página, legenda, título ou nota, nessa ordem; senão, texto."""
        if self._numero_de_pagina(zona, texto):
            return "numero_de_pagina"
        if self._legenda(zona, texto):
            return "legenda"
        if self._titulo(zona, dentro, texto):
            return "titulo"
        if self._nota(zona, dentro):
            return "nota"
        return "texto"

    def _numero_de_pagina(self, zona: Zona, texto: str) -> bool:
        """Só o número (ou "pág. N"), no alto ou no pé da página."""
        return bool(_NUMERO_DE_PAGINA.fullmatch(texto)) and (
            zona.y1 < 0.15 * self.altura or zona.y2 > 0.85 * self.altura)

    def _legenda(self, zona: Zona, texto: str) -> bool:
        return _parece_legenda(texto) and any(
            _vizinha_do_diagrama(zona, diagrama, self.escala) for diagrama in self.diagramas)

    def _titulo(self, zona: Zona, dentro: Sequence[BoxEntry], texto: str) -> bool:
        """Sem lances, com as maiúsculas maiores que as da página, ou curto, centrado, de
        uma linha só e sozinho."""
        if _parece_lances(texto):
            return False
        if _percentil([b.y2 - b.y1 for b in dentro], 0.9) >= RAZAO_DO_TITULO * self.maiusculas:
            return True
        return (len(texto) <= 80
                and abs((zona.x1 + zona.x2) / 2 - self.largura / 2) <= 0.1 * self.largura
                and zona.y2 - zona.y1 <= 2.2 * self.maiusculas       # uma linha só
                and _isolada(zona, self.zonas, self.escala))

    def _nota(self, zona: Zona, dentro: Sequence[BoxEntry]) -> bool:
        """No pé da página, com a letra menor que a do corpo, e sozinha."""
        return (zona.y1 >= 0.7 * self.altura
                and median(b.y2 - b.y1 for b in dentro) <= RAZAO_DA_NOTA * self.corpo
                and _isolada(zona, self.zonas, self.escala))


#: As funções que a classificação local dá (as da margem vêm das páginas lidas do livro).
FUNCOES_LOCAIS = frozenset({"texto", "titulo", "nota", "legenda", "ignorar"})


def reclassificar_automaticas(zonas: Sequence[Zona], boxes: Sequence[BoxEntry],
                              largura: int, altura: int) -> List[Zona]:
    """Depois do F5: as áreas que continuam automáticas (ninguém as mexeu) ganham a função
    pelo texto lido agora. As áreas feitas antes de reconhecer (o fluxo do FineReader) não
    tinham texto, e sem ele a função era só um palpite; a do usuário e a da margem
    aprendida pelo livro ficam como estão."""
    lidos = [b for b in boxes if b.char]
    marcadas = [z.automatica and z.funcao in FUNCOES_LOCAIS for z in zonas]
    if not lidos or not any(marcadas):
        return list(zonas)
    return _reclassificadas(zonas, marcadas, lidos, largura, altura)


def _reclassificadas(zonas: Sequence[Zona], marcadas: Sequence[bool], lidos: Sequence[BoxEntry],
                     largura: int, altura: int) -> List[Zona]:
    """As zonas `marcadas` de volta a texto e classificadas pelos glifos lidos; as outras
    como estão."""
    escala = median(b.y2 - b.y1 for b in lidos)
    candidatas = [replace(z, tipo=TEXTO, funcao="texto") if marcada else z
                  for z, marcada in zip(zonas, marcadas)]
    classificadas = classificar_funcoes(candidatas, lidos, largura, altura, escala)
    return [nova if marcada else velha
            for velha, nova, marcada in zip(zonas, classificadas, marcadas)]


def depois_de_ler(zonas: Sequence[Zona], boxes: Sequence[BoxEntry], tabuleiros: Iterable[Caixa],
                  diagramas: Sequence, largura: int, altura: int) -> List[Zona]:
    """As áreas da página depois de lê-la (o lote e o F5). Sem área nenhuma, as automáticas
    pela leitura, como o FineReader cria as dele ao reconhecer: o título, a legenda ligada
    ao diagrama e a nota chegam ao Documento e à exportação (o sumário) sem o usuário abrir
    o modo Áreas. Com áreas, as automáticas reclassificadas pelo texto lido; a do usuário
    fica como está."""
    if zonas:
        return reclassificar_automaticas(zonas, boxes, largura, altura)
    lidos = [b for b in boxes if b.char]
    if not lidos:
        return []
    return vincular_legendas(automaticas(lidos, tabuleiros, largura, altura), diagramas)


def _continuacoes_da_legenda(zonas: List[Zona], boxes: Sequence[BoxEntry],
                             escala: float) -> List[Zona]:
    """A zona de texto curta logo embaixo de uma legenda, sobrepondo-a na horizontal, é a
    continuação dela (os jogadores, o lugar e o ano: "Gormon-Silman / Memorial Ervin,
    1987"), que a regra da primeira linha não reconhece sozinha."""
    saida = list(zonas)
    mudou = True
    while mudou:
        mudou = False
        for k, zona in enumerate(saida):
            if _pode_continuar(zona, boxes) and any(
                    _embaixo_da_legenda(zona, legenda, escala) for legenda in saida):
                saida[k] = replace(zona, funcao="legenda")
                mudou = True
    return saida


def _pode_continuar(zona: Zona, boxes: Sequence[BoxEntry]) -> bool:
    """A zona automática de texto, ainda sem outra função, com `TAMANHO_DA_CONTINUACAO`
    caracteres ou menos."""
    return (zona.automatica and zona.tipo == TEXTO and zona.funcao == "texto"
            and len(_texto_dos_boxes([b for b in boxes if zona.contem_o_centro(b)]))
            <= TAMANHO_DA_CONTINUACAO)


def _embaixo_da_legenda(zona: Zona, legenda: Zona, escala: float) -> bool:
    """Se `legenda` é uma legenda logo acima da zona, sobrepondo-a na horizontal."""
    return (legenda.funcao == "legenda"
            and min(zona.x2, legenda.x2) - max(zona.x1, legenda.x1) > 0
            and -escala <= zona.y1 - legenda.y2 <= 1.5 * escala)


def _texto_dos_boxes(boxes: Sequence[BoxEntry]) -> str:
    """Texto suficiente para classificar uma zona, preservando espaços aproximados."""
    lidos = [b for b in boxes if b.char]
    if not lidos:
        return ""
    altura = median(b.y2 - b.y1 for b in lidos)
    linhas = sorted(_linhas_dos_lidos(lidos), key=lambda itens: min(b.y1 for b in itens))
    return " ".join(_texto_da_linha(linha, altura) for linha in linhas).strip()


def _linhas_dos_lidos(lidos: Sequence[BoxEntry]) -> List[List[BoxEntry]]:
    """Os glifos em linhas: cada um entra na linha cuja altura cobre o meio dele, ou cujo
    meio ele cobre, entre as três últimas."""
    linhas: List[List[BoxEntry]] = []
    for box in sorted(lidos, key=lambda b: (b.y1 + b.y2) / 2):
        meio = (box.y1 + box.y2) / 2
        for linha in reversed(linhas[-3:]):
            topo, pe = min(b.y1 for b in linha), max(b.y2 for b in linha)
            if topo <= meio <= pe or box.y1 <= (topo + pe) / 2 <= box.y2:
                linha.append(box)
                break
        else:
            linhas.append([box])
    return linhas


def _texto_da_linha(linha: Sequence[BoxEntry], altura: float) -> str:
    """Os caracteres da linha da esquerda para a direita, com um espaço onde o vão passa de
    0,6 altura."""
    partes = []
    anterior = None
    for box in sorted(linha, key=lambda b: b.x1):
        if anterior is not None and box.x1 - anterior.x2 > 0.6 * altura:
            partes.append(" ")
        partes.append(box.char)
        anterior = box
    return "".join(partes)


def _percentil(valores, q: float) -> float:
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, int(round(q * (len(ordenados) - 1))))]


def _comeca_como(texto: str, palavras: Sequence[str], erros: int = 2) -> bool:
    """Se o começo do texto (sem espaços) é uma das `palavras` com até `erros` letras
    trocadas, faltando ou sobrando: o OCR lê "Dia9rama", "Dia rama", "iagrama"."""
    junto = re.sub(r"\s+", "", texto.lower())
    for palavra in palavras:
        n = len(palavra)
        for tamanho in range(max(1, n - erros), n + erros + 1):
            if _distancia(junto[:tamanho], palavra) <= erros:
                return True
    return False


def _distancia(a: str, b: str) -> int:
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        atual = [i]
        for j, cb in enumerate(b, start=1):
            atual.append(min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + (ca != cb)))
        anterior = atual
    return anterior[-1]


def _parece_legenda(texto: str) -> bool:
    """§5.1: linha curta perto do diagrama que diz "Diagrama N", "Teste N" ou só o número,
    ou de quem é a vez ("jogam as brancas", "White to play"). A prosa ("Black moves the
    knight…") e os lances ("1.e4 e5 2.Nf3") ficam no texto, que valida os lances."""
    from abbychess.diagramas import _VEZ_PELO_VERBO

    if len(texto) > TAMANHO_DA_LEGENDA:
        return False
    return bool(_INICIO_DA_LEGENDA.search(texto) or _SO_O_NUMERO.fullmatch(texto)
                or _TEXTO_DA_LEGENDA.search(texto) or _VEZ_PELO_VERBO.match(texto)
                # A tolerância do OCR só na palavra longa: "teste" com 2 erros casava
                # "These squares" e "Tea time" (o "Teste N" impresso já casa acima).
                or _comeca_como(texto, ("diagrama", "diagram")))


def _vizinha_do_diagrama(zona: Zona, diagrama, escala: float) -> bool:
    """Embaixo ou em cima do diagrama (sobrepondo na horizontal), ou ao lado dele
    (sobrepondo na vertical), a até `DISTANCIA_DA_LEGENDA` alturas de letra."""
    return _distancia_ao_diagrama(zona, _caixa(diagrama)) <= DISTANCIA_DA_LEGENDA * escala


def _caixa(coisa) -> Caixa:
    return tuple(coisa.caixa) if hasattr(coisa, "caixa") else (coisa.x1, coisa.y1, coisa.x2, coisa.y2)


def _distancia_ao_diagrama(zona: Zona, caixa: Caixa) -> float:
    """A distância da zona ao diagrama pelo lado em que eles se encaram; infinita se não se
    encaram (nem na horizontal nem na vertical)."""
    x1, y1, x2, y2 = caixa
    if min(zona.x2, x2) - max(zona.x1, x1) > 0:
        return max(y1 - zona.y2, zona.y1 - y2, 0)
    if min(zona.y2, y2) - max(zona.y1, y1) > 0:
        return max(x1 - zona.x2, zona.x1 - x2, 0)
    return float("inf")


def _isolada(zona: Zona, zonas: Sequence[Zona], escala: float) -> bool:
    outras = [z for z in zonas if z is not zona and z.tipo == TEXTO]
    distancia = min((max(z.y1 - zona.y2, zona.y1 - z.y2, 0) for z in outras), default=float("inf"))
    return distancia >= 1.5 * escala


def vincular_legendas(zonas: Sequence[Zona], diagramas: Sequence) -> List[Zona]:
    """Liga cada legenda ao diagrama `dN` geometricamente mais próximo.

    O vínculo usa os diagramas lidos, cuja caixa é a do tabuleiro, e por isso sobrevive
    à reordenação das listas. Uma ligação existente a um diagrama da página é autoridade e
    fica; a legenda marcada à mão (L) sem ligação também ganha a do vizinho.
    """
    ids = {d.id for d in diagramas if getattr(d, "id", "")}
    saida = []
    for zona in zonas:
        if zona.funcao != "legenda":
            saida.append(replace(zona, diagrama_id=None) if zona.diagrama_id else zona)
        elif zona.diagrama_id in ids:
            saida.append(zona)
        else:
            saida.append(replace(zona, diagrama_id=_diagrama_mais_perto(zona, diagramas)))
    return saida


def _diagrama_mais_perto(zona: Zona, diagramas: Sequence) -> Optional[str]:
    """O id do diagrama com id que encara a legenda mais de perto; na mesma distância, o de
    cima ou de baixo vence o do lado. None se nenhum a encara."""
    candidatos = []
    for diagrama in diagramas:
        if not getattr(diagrama, "id", ""):
            continue
        distancia = _distancia_ao_diagrama(zona, tuple(diagrama.caixa))
        if distancia == float("inf"):
            continue
        x1, y1, x2, y2 = diagrama.caixa
        embaixo = min(zona.x2, x2) - max(zona.x1, x1) > 0   # a de baixo vence a do lado
        candidatos.append((distancia, not embaixo, diagrama.id))
    return min(candidatos)[2] if candidatos else None


def aplicar_funcoes_de_margem(zonas: Sequence[Zona], boxes: Sequence[BoxEntry],
                              funcoes: dict) -> List[Zona]:
    """Aplica cabeçalho/rodapé/número aprendidos pelo livro às zonas automáticas."""
    return [_com_a_funcao_da_margem(zona, boxes, funcoes) for zona in zonas]


def _com_a_funcao_da_margem(zona: Zona, boxes: Sequence[BoxEntry], funcoes: dict) -> Zona:
    """A zona automática de texto (ou de uma função da margem) com a função que todos os
    glifos dela têm em `funcoes`; as outras como estão."""
    if not zona.automatica or zona.tipo != TEXTO or zona.funcao not in (
            "texto", "titulo", "cabecalho", "rodape", "numero_de_pagina"):
        return zona
    funcao = _funcao_de_todos([i for i, box in enumerate(boxes) if zona.contem_o_centro(box)],
                              funcoes)
    return replace(zona, funcao=funcao) if funcao else zona


def _funcao_de_todos(indices: Sequence[int], funcoes: dict) -> Optional[str]:
    """A função que todos os glifos de `indices` têm em `funcoes`; None se não há glifo, se
    algum não tem função ou se elas diferem."""
    votos = [funcoes[i] for i in indices if i in funcoes]
    return votos[0] if indices and len(votos) == len(indices) and len(set(votos)) == 1 else None


def _linhas(boxes: Sequence[BoxEntry]) -> List[List[int]]:
    """As linhas de texto, como caixas [x1, y1, x2, y2], de cima para baixo.

    Um box entra na linha cujo meio da altura ele cobre. Basta para agrupar em
    blocos; a ordem de leitura de verdade é a do `BoxService`.
    """
    linhas: List[List[int]] = []
    membros: List[List[BoxEntry]] = []
    for b in sorted(boxes, key=lambda b: (b.y1 + b.y2) / 2):
        meio = (b.y1 + b.y2) / 2
        for linha, dela in zip(reversed(linhas[-3:]), reversed(membros[-3:])):
            if linha[1] <= meio <= linha[3] or b.y1 <= (linha[1] + linha[3]) / 2 <= b.y2:
                linha[0], linha[1] = min(linha[0], b.x1), min(linha[1], b.y1)
                linha[2], linha[3] = max(linha[2], b.x2), max(linha[3], b.y2)
                dela.append(b)
                break
        else:
            linhas.append([b.x1, b.y1, b.x2, b.y2])
            membros.append([b])
    saida: List[List[int]] = []
    for dela in membros:
        saida.extend(_partir_no_vao(dela))
    return saida


def _partir_no_vao(boxes: Sequence[BoxEntry]) -> List[List[int]]:
    """A linha partida onde o vão entre dois glifos passa de `VAO_QUE_PARTE` alturas, com
    ao menos `GLIFOS_DE_CADA_LADO` glifos de cada lado: as legendas de dois diagramas lado a
    lado ("Diagrama 6…   Diagrama 7…") ficam numa linha só da mesma altura, e viravam uma
    zona só ligada a um diagrama só (a mesma regra da `layout.partir_nos_vaos`)."""
    ordem = sorted(boxes, key=lambda b: b.x1)
    altura = max(1, median(b.y2 - b.y1 for b in ordem))
    partes = partes_pelo_vao(ordem, lambda atual, b: b.x1 - max(x.x2 for x in atual),
                             VAO_QUE_PARTE * altura, GLIFOS_DE_CADA_LADO)
    return [[min(x.x1 for x in p), min(x.y1 for x in p), max(x.x2 for x in p), max(x.y2 for x in p)]
            for p in partes]


def _blocos(linhas: List[List[int]], escala: float) -> List[Caixa]:
    """Junta linhas seguidas que se sobrepõem na horizontal e não têm vão grande."""
    blocos: List[List[int]] = []
    for linha in sorted(linhas, key=lambda c: c[1]):
        alvo = None
        for bloco in blocos:
            vao = linha[1] - bloco[3]
            recuo = linha[0] - bloco[0]
            if (vao <= escala * VAO_ENTRE_BLOCOS and recuo < escala * RECUO_DE_PARAGRAFO
                    and min(linha[2], bloco[2]) > max(linha[0], bloco[0])):
                alvo = bloco
        if alvo is None:
            blocos.append(list(linha))
        else:
            alvo[0], alvo[1] = min(alvo[0], linha[0]), min(alvo[1], linha[1])
            alvo[2], alvo[3] = max(alvo[2], linha[2]), max(alvo[3], linha[3])
    return [tuple(b) for b in blocos]


# ----------------------------------------------------------------------
# Reconhecer com as áreas
# ----------------------------------------------------------------------

def tipo_no_ponto(zonas: Sequence[Zona], x: float, y: float) -> Optional[str]:
    """O tipo que vale no ponto: o mais restritivo das áreas que o cobrem, ou `None`."""
    tipos = [z.tipo for z in zonas if z.contem(x, y)]
    return max(tipos, key=PRIORIDADE.__getitem__) if tipos else None


def filtrar(boxes: Sequence[BoxEntry], tabuleiros: Sequence[Caixa],
            zonas: Sequence[Zona]) -> Tuple[List[BoxEntry], List[Caixa]]:
    """Os boxes de texto e os tabuleiros que as áreas deixam passar.

    Um box fica se o centro dele cai numa área cujo tipo vencedor é texto. Cada
    área de diagrama dá um tabuleiro: o achado pela segmentação dentro dela,
    que é a caixa justa das 64 casas, ou a própria área, se não achou nenhum.
    A ordem dos boxes é mantida.
    """
    texto = [b for b in boxes
             if tipo_no_ponto(zonas, (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2) == TEXTO]
    return texto, _tabuleiros_das_areas(tabuleiros, zonas)


def _tabuleiros_das_areas(tabuleiros: Sequence[Caixa], zonas: Sequence[Zona]) -> List[Caixa]:
    """Cada área de diagrama dá os tabuleiros achados dentro dela, onde o diagrama vence, ou
    a própria área, se não achou nenhum e o diagrama vence no centro dela; sem repetir."""
    saida: List[Caixa] = []
    for z in zonas:
        if z.tipo != DIAGRAMA:
            continue
        dentro = _tabuleiros_dentro(z, tabuleiros, zonas)
        saida.extend(tuple(t) for t in dentro if tuple(t) not in saida)
        if not dentro and tipo_no_ponto(zonas, (z.x1 + z.x2) / 2, (z.y1 + z.y2) / 2) == DIAGRAMA:
            saida.append(z.caixa)
    return saida


def _tabuleiros_dentro(zona: Zona, tabuleiros: Sequence[Caixa], zonas: Sequence[Zona]) -> list:
    """Os tabuleiros com o centro na área e onde o diagrama vence."""
    return [t for t in tabuleiros if zona.contem((t[0] + t[2]) / 2, (t[1] + t[3]) / 2)
            and tipo_no_ponto(zonas, (t[0] + t[2]) / 2, (t[1] + t[3]) / 2) == DIAGRAMA]


def segmentar(imagem, zonas: Sequence[Zona], leitor=None):
    """A segmentação da página: pelas áreas, se houver, ou a automática inteira."""
    if zonas:
        return segmentar_com_zonas(imagem, zonas, leitor)
    from abbychess.pagina import segmentar_pagina

    return segmentar_pagina(imagem, leitor)


def segmentar_com_zonas(imagem, zonas: Sequence[Zona], leitor=None):
    """A `PaginaSegmentada` que as áreas pedem: texto só das áreas de texto.

    A segmentação roda na página inteira, sem tirar os diagramas que ela acha,
    porque é o usuário quem decide agora o que é diagrama: um tabuleiro achado
    numa área que ele marcou como texto é lido como texto.
    """
    from core.services.box_service import BoxService

    from abbychess.pagina import PaginaSegmentada, segmentar_tudo

    if not any(z.tipo in (TEXTO, DIAGRAMA) for z in zonas):     # só figura e ignorar: nada a ler
        return PaginaSegmentada([], [])
    bruta = segmentar_tudo(imagem, leitor)
    boxes, tabuleiros = filtrar(bruta.boxes, bruta.tabuleiros, zonas)
    return PaginaSegmentada(BoxService.sort_boxes_reading_order(boxes), tabuleiros)
