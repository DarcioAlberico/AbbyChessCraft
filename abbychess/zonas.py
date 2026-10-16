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

from dataclasses import dataclass, replace
from statistics import median
from typing import Iterable, List, Optional, Sequence, Tuple

from core.box_model import BoxEntry

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

Caixa = Tuple[int, int, int, int]


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

    def __post_init__(self):
        if not self.funcao:
            object.__setattr__(self, "funcao", FUNCAO_DO_TIPO.get(self.tipo, "texto"))
        if self.funcao not in FUNCOES:
            raise ValueError(f"Função de área desconhecida: {self.funcao!r}")
        if TIPO_DA_FUNCAO[self.funcao] != self.tipo:
            raise ValueError(f"A função {self.funcao!r} não é de uma área do tipo {self.tipo!r}")

    @property
    def caixa(self) -> Caixa:
        return self.x1, self.y1, self.x2, self.y2

    def contem(self, x: float, y: float) -> bool:
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2

    def como_dict(self) -> dict:
        return {"id": self.id, "tipo": self.tipo, "funcao": self.funcao, "caixa": list(self.caixa),
                "ordem": self.ordem, "automatica": self.automatica}

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
                   automatica=bool(dados.get("automatica", False)))


def com_ids(zonas: Sequence[Zona]) -> List[Zona]:
    """As áreas com `id` cada uma: as que não têm ganham o próximo `zN` livre."""
    usados = {z.id for z in zonas if z.id}
    proximo, saida = 0, []
    for z in zonas:
        if not z.id:
            while f"z{proximo}" in usados:
                proximo += 1
            z = replace(z, id=f"z{proximo}")
            usados.add(z.id)
        saida.append(z)
    return saida


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
        return replace(zona, x1=x1 + dx, y1=y1 + dy, x2=x2 + dx, y2=y2 + dy)
    if "e" in bordas:
        x1 = min(max(0, x1 + dx), x2 - MENOR_LADO)
    if "d" in bordas:
        x2 = max(min(largura, x2 + dx), x1 + MENOR_LADO)
    if "c" in bordas:
        y1 = min(max(0, y1 + dy), y2 - MENOR_LADO)
    if "b" in bordas:
        y2 = max(min(altura, y2 + dy), y1 + MENOR_LADO)
    return replace(zona, x1=x1, y1=y1, x2=x2, y2=y2)


def trocar_tipo(zonas: List[Zona], indice: int, tipo: str) -> None:
    if tipo not in TIPOS:
        raise ValueError(f"Tipo de área desconhecido: {tipo!r}")
    zonas[indice] = replace(zonas[indice], tipo=tipo, funcao=FUNCAO_DO_TIPO[tipo])


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
    return com_ids([replace(z, automatica=True) for z in zonas])


def _linhas(boxes: Sequence[BoxEntry]) -> List[List[int]]:
    """As linhas de texto, como caixas [x1, y1, x2, y2], de cima para baixo.

    Um box entra na linha cujo meio da altura ele cobre. Basta para agrupar em
    blocos; a ordem de leitura de verdade é a do `BoxService`.
    """
    linhas: List[List[int]] = []
    for b in sorted(boxes, key=lambda b: (b.y1 + b.y2) / 2):
        meio = (b.y1 + b.y2) / 2
        for linha in reversed(linhas[-3:]):
            if linha[1] <= meio <= linha[3] or b.y1 <= (linha[1] + linha[3]) / 2 <= b.y2:
                linha[0], linha[1] = min(linha[0], b.x1), min(linha[1], b.y1)
                linha[2], linha[3] = max(linha[2], b.x2), max(linha[3], b.y2)
                break
        else:
            linhas.append([b.x1, b.y1, b.x2, b.y2])
    return linhas


def _blocos(linhas: List[List[int]], escala: float) -> List[Caixa]:
    """Junta linhas seguidas que se sobrepõem na horizontal e não têm vão grande."""
    blocos: List[List[int]] = []
    for linha in sorted(linhas, key=lambda c: c[1]):
        alvo = None
        for bloco in blocos:
            vao = linha[1] - bloco[3]
            if vao <= escala * VAO_ENTRE_BLOCOS and min(linha[2], bloco[2]) > max(linha[0], bloco[0]):
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
    saida: List[Caixa] = []
    for z in zonas:
        if z.tipo != DIAGRAMA:
            continue
        dentro = [t for t in tabuleiros if z.contem((t[0] + t[2]) / 2, (t[1] + t[3]) / 2)
                  and tipo_no_ponto(zonas, (t[0] + t[2]) / 2, (t[1] + t[3]) / 2) == DIAGRAMA]
        saida.extend(tuple(t) for t in dentro if tuple(t) not in saida)
        if not dentro and tipo_no_ponto(zonas, (z.x1 + z.x2) / 2, (z.y1 + z.y2) / 2) == DIAGRAMA:
            saida.append(z.caixa)
    return texto, saida


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

    bruta = segmentar_tudo(imagem, leitor)
    boxes, tabuleiros = filtrar(bruta.boxes, bruta.tabuleiros, zonas)
    return PaginaSegmentada(BoxService.sort_boxes_reading_order(boxes), tabuleiros)
