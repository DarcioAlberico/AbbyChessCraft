"""Das páginas gravadas no projeto ao intermediário do PyBoxEditor (`core.pagina`): as linhas e
as palavras pela ordem de leitura, a estrutura que o Documento (§4.2) dá a cada glifo, os
parágrafos pelo vão entre linhas e as figuras dos diagramas. Puro: nada aqui grava nem abre
arquivo. À parte de `exportar.py` (SPEC-qualidade Q-E6, CA-Q-A1)."""

from __future__ import annotations

import io
import re
import statistics
from dataclasses import dataclass, field
from typing import AbstractSet, Dict, List, Optional, Sequence, Tuple

from PIL import Image

from core.box_model import BoxEntry
from core.pagina import Figura, PaginaExtraida, Paragrafo

from abbychess.diagramas import DiagramaLido, para_caixas
from abbychess.layout import OrdemDeLeitura
from abbychess.projeto import ProjetoDeLivro


#: A resolução em que as páginas do PDF são lidas (`core.services.pdf_service`).
#: Os boxes gravados estão nesta escala.
DPI_DA_LEITURA = 300


#: Um passo entre linhas maior que isto, em passos medianos da página, abre
#: parágrafo. É o `core.pagina.SALTO_DE_PARAGRAFO` (0,6 além do passo).
SALTO_DE_PARAGRAFO = 1.6


#: Letras que só mudam de tamanho entre a minúscula e a maiúscula. O livro ensinado
#: pode ter o padrão com a caixa errada (um `o` ensinado como `O` lia o livro
#: inteiro com `abOut`), e a altura do glifo na linha decide.
LETRAS_DE_CAIXA_PELA_ALTURA = frozenset("cosvwxzCOSVWXZ")
#: Minúsculas sem haste nem perna: a altura delas é a altura-x da linha.
_ALTURA_X = frozenset("aemnru")
#: Maiúsculas e minúsculas com haste, de altura conhecida: a das maiúsculas. Sem o
#: `t`, que é mais baixo (21 px contra 31 do `h` no Odds & Ends), nem os números,
#: que no Garamond são de texto e sobem e descem.
_ALTURA_DE_MAIUSCULA = frozenset("ABDEFGHIJKLMNPRTUYbdfhkl")
#: Sem letra alta na linha, a letra ambígua até isto da altura-x é minúscula.
FOLGA_DA_ALTURA_X = 1.15
#: Entre a altura-x e a da maiúscula, onde a letra passa de uma caixa à outra.
CORTE_DA_CAIXA = 0.5


#: As funções de área que não são o texto do livro: saem da exportação, salvo com a opção
#: de manter cabeçalhos e rodapés (§12.1). `ignorar` sai sempre.
FUNCOES_DE_MARGEM = ("cabecalho", "rodape", "numero_de_pagina")
FORA_DA_EXPORTACAO = FUNCOES_DE_MARGEM + ("ignorar",)


@dataclass
class Estrutura:
    """O que o Documento (§4.2) sabe de cada box da página, para a exportação ler (§12.1).

    A montagem das linhas e dos parágrafos continua a desta exportação (a caixa pela
    altura, os trechos de coluna, as coordenadas), que tem casos medidos; a estrutura diz
    o que ela não tinha como saber: a função da área (título, margens, nota, legenda,
    ignorar), o negrito e o itálico do glifo, o parágrafo pedido e o hífen de quebra.
    Chaveada pelo `id` do `BoxEntry`, para sobreviver aos filtros da lista de boxes."""

    funcoes: Dict[int, str] = field(default_factory=dict)
    negrito: set = field(default_factory=set)
    italico: set = field(default_factory=set)
    paragrafo_antes: set = field(default_factory=set)
    hifen_de_quebra: set = field(default_factory=set)
    #: (id do último glifo de uma linha, id do primeiro da seguinte) que o Documento juntou
    #: numa palavra (o hífen de quebra apagado, §6.3): a linha seguinte entra sem espaço.
    juncoes: set = field(default_factory=set)
    #: Os boxes que a fila de revisão pede (`leitor.precisa_revisao` e `contexto`), quando a página foi
    #: lida com os limiares do livro: o realce do DOCX (`Opcoes.realcar_duvidosos`).
    duvidosos: set = field(default_factory=set)
    #: Os boxes numa área desenhada pelo usuário com função de texto (não de margem): a
    #: regra das margens corridas (`margens_corridas`) não os tira.
    protegidos: set = field(default_factory=set)
    #: Os `BoxEntry` da estrutura, vivos enquanto ela viver: as chaves são `id()`.
    vivos: list = field(default_factory=list)
    #: As palavras do texto do Documento em ordem de leitura (`texto.linhas_dos_gids` sem
    #: os não lidos, como `texto.montar`: as quebras, as junções, os lances colados partidos
    #: e os virtuais), cada uma como os `id()` dos glifos dela e, no lugar dos virtuais (sem
    #: box), o caractere (SPEC-qualidade Q-E1).
    palavras_do_documento: list = field(default_factory=list)
    #: O `id()` de cada glifo -> a posição da palavra dele em `palavras_do_documento`.
    palavra_de: Dict[int, int] = field(default_factory=dict)

    def funcao(self, b: BoxEntry) -> str:
        return self.funcoes.get(id(b), "texto")

    @classmethod
    def da_pagina(cls, pagina, limiares=None) -> Tuple[List[BoxEntry], "Estrutura"]:
        """Os boxes lidos da página do modelo (`modelo.Pagina`) e a estrutura deles; sem
        modelo, nada. Com os `limiares` do livro, também os duvidosos.

        Uma passada pelos glifos para cada coisa que a estrutura sabe deles (as áreas, os
        estilos e as decisões, os duvidosos), sem chamada a mais por glifo."""
        if pagina is None:
            return [], cls()
        lidos = [b for b in pagina.boxes if b.entry.char]
        estrutura = cls(vivos=[b.entry for b in lidos])
        estrutura._das_areas(pagina.zonas, lidos)
        estrutura._dos_estilos_e_decisoes(lidos, pagina.decisoes)
        if limiares is not None:
            estrutura._dos_duvidosos(pagina, lidos, limiares)
        entrada_do = {b.gid: b.entry for b in lidos}
        estrutura._das_juncoes(pagina.decisoes, entrada_do)
        estrutura._das_palavras(pagina, entrada_do)
        return list(estrutura.vivos), estrutura

    def _das_areas(self, zonas, lidos) -> None:
        """A função da área de cada glifo; protegido, o da área desenhada pelo usuário com
        função de texto."""
        from abbychess import zonas as zn

        areas = [z for z in zonas if z.tipo in (zn.TEXTO, zn.IGNORAR)]
        funcao_da, protege = _funcoes_das_areas(areas)
        for b in lidos:
            e = b.entry
            area = zn.zona_que_vale(areas, (e.x1 + e.x2) / 2, (e.y1 + e.y2) / 2)
            if area is None:
                continue
            self.funcoes[id(e)] = funcao_da[id(area)]
            if protege[id(area)]:
                self.protegidos.add(id(e))

    def _dos_estilos_e_decisoes(self, lidos, decisoes) -> None:
        for b in lidos:
            chave = id(b.entry)
            if b.estilo.negrito:
                self.negrito.add(chave)
            if b.estilo.italico:
                self.italico.add(chave)
            if b.gid in decisoes.paragrafo_antes:
                self.paragrafo_antes.add(chave)
            if b.gid in decisoes.hifen_de_quebra:
                self.hifen_de_quebra.add(chave)

    def _dos_duvidosos(self, pagina, lidos, limiares) -> None:
        """Os glifos que a fila de revisão pede: pela confiança, ou pelo contexto."""
        from abbychess import contexto
        from abbychess.leitor import precisa_revisao

        contra = contexto.improvaveis(pagina)
        for b in lidos:
            e = b.entry
            if (precisa_revisao(e.char, e.source, e.confidence, limiares)
                    or (b.gid in contra and contexto.volta_pelo_contexto(e.source))):
                self.duvidosos.add(id(e))

    def _das_juncoes(self, decisoes, entrada_do: dict) -> None:
        for ultimo, primeiro in decisoes.juncoes:
            if ultimo in entrada_do and primeiro in entrada_do:
                self.juncoes.add((id(entrada_do[ultimo]), id(entrada_do[primeiro])))

    def _das_palavras(self, pagina, entrada_do: dict) -> None:
        """As palavras do texto do Documento e a palavra de cada glifo (Q-E1)."""
        from abbychess import texto as tx

        virtuais = {v.gid: v.char for v in pagina.decisoes.virtuais}
        for linha in tx.linhas_dos_gids(pagina, com_os_nao_lidos=False):
            for p in linha:
                itens = _itens_da_palavra(p, entrada_do, virtuais)
                if itens:
                    self.palavra_de.update(
                        (item, len(self.palavras_do_documento))
                        for item in itens if not isinstance(item, str))
                    self.palavras_do_documento.append(itens)


def _funcoes_das_areas(areas) -> Tuple[Dict[int, str], Dict[int, bool]]:
    """A função de cada área (pelo `id`) e se ela protege os glifos dela da regra das
    margens (a desenhada pelo usuário, com função de texto)."""
    from abbychess import zonas as zn

    funcao_da, protege = {}, {}
    for area in areas:
        funcao = "ignorar" if area.tipo == zn.IGNORAR else area.funcao or "texto"
        funcao_da[id(area)] = funcao
        protege[id(area)] = not area.automatica and funcao not in FORA_DA_EXPORTACAO
    return funcao_da, protege


def _itens_da_palavra(gids, entrada_do: dict, virtuais: dict) -> tuple:
    """Os `id()` dos glifos da palavra e, no lugar dos virtuais, o caractere."""
    return tuple(id(entrada_do[g]) if g in entrada_do else virtuais[g]
                 for g in gids if g in entrada_do or g in virtuais)


@dataclass
class _Linha:
    texto: str
    topo: int
    pe: int
    indices: List[int] = field(default_factory=list)
    #: O trecho de leitura (faixa, coluna) da linha; ver `layout.OrdemDeLeitura`.
    trecho: Tuple[int, int] = (0, 0)
    #: Da `Estrutura`: a função da área da linha, se ela pede parágrafo, se termina num
    #: hífen de quebra decidido, e os trechos `(início, fim)` em negrito e em itálico.
    funcao: str = "texto"
    paragrafo: bool = False
    hifen: bool = False
    #: Os ids do primeiro e do último glifo da linha (as junções entre linhas, §6.3).
    primeiro: int = 0
    ultimo: int = 0
    #: A junção da `Estrutura` com a linha anterior: entra sem espaço.
    juncoes: AbstractSet[Tuple[int, int]] = frozenset()
    negrito: List[Tuple[int, int]] = field(default_factory=list)
    italico: List[Tuple[int, int]] = field(default_factory=list)
    #: Os trechos dos glifos duvidosos (`Estrutura.duvidosos`).
    duvidosos: List[Tuple[int, int]] = field(default_factory=list)


def palavras(boxes: Sequence[BoxEntry]) -> List[List[Tuple[str, List[int]]]]:
    """As palavras de cada linha, `(texto, índices dos boxes)`, em ordem de leitura.

    O corte em linhas e palavras é o de `core.notacao.palavras_da_pagina`, mas
    o texto sai do próprio box: lá a figurina vira a letra do SAN (♘ -> N), e o
    livro exportado tem de mostrar o que estava impresso. Só o `✝` do xeque vira
    `+`, como em toda saída do PyBoxEditor (`notacao.normalizar_saida`), e a ligadura
    tipográfica (`ﬁ`) sai como as letras dela, como no Documento (`texto.normalizador`).
    """
    return [linha for _trecho, linha in _palavras_por_trecho(boxes)]


def _palavras_por_trecho(boxes: Sequence[BoxEntry], leitura: Optional[OrdemDeLeitura] = None,
                         estrutura: Optional[Estrutura] = None
                         ) -> List[Tuple[Tuple[int, int], List[Tuple[str, List[int]]]]]:
    """As linhas de `palavras`, cada uma com o trecho de leitura em que está. Com a
    `Estrutura`, as palavras de cada linha são as do Documento (`_pelo_documento`)."""
    from abbychess import texto as tx

    normalizar_saida = tx.normalizador(tx.IMPRESSO)   # sem as ligaduras, como o Documento
    leitura = leitura or OrdemDeLeitura.da_pagina(boxes)
    documento = estrutura if estrutura is not None and estrutura.palavras_do_documento else None
    saida = []
    for chave, trecho in leitura.trechos(boxes):
        for linha in leitura.linhas_do_trecho(trecho, boxes):
            indices = [trecho[s.indice] for p in linha for s in p.simbolos]
            caixa = _caixa_pela_altura(boxes, indices)

            def letra(i: int) -> str:
                return normalizar_saida(caixa.get(i, boxes[i].char))

            pelo_documento = (_pelo_documento(indices, boxes, documento, letra, normalizar_saida)
                              if documento is not None else None)
            saida.append((chave, pelo_documento if pelo_documento is not None else [
                (_captura_minuscula("".join(letra(trecho[s.indice]) for s in p.simbolos)),
                 [trecho[s.indice] for s in p.simbolos])
                for p in linha if p.simbolos]))
    return saida


def _pelo_documento(indices: Sequence[int], boxes: Sequence[BoxEntry], estrutura: Estrutura,
                    letra, normalizar) -> Optional[List[Tuple[str, List[int]]]]:
    """As palavras da linha (os `indices` dos boxes dela) partidas como o Documento as parte
    (SPEC-qualidade Q-E1), na ordem dele: a quebra e os lances colados partidos, a junção
    sem espaço, e o virtual (a letra digitada, sem box) no lugar dele. O virtual entra com a
    palavra que tem um glifo nesta linha; a palavra só de virtuais, depois da palavra do
    Documento que vem antes dela. None se algum glifo da linha não está no Documento (a
    linha sai pela geometria, como antes)."""
    palavras_do_documento, palavra_de = estrutura.palavras_do_documento, estrutura.palavra_de
    indice_de = {id(boxes[i]): i for i in indices}
    if any(chave not in palavra_de for chave in indice_de):
        return None
    na_linha = sorted({palavra_de[chave] for chave in indice_de})
    escolhidas = []
    for k in na_linha:
        escolhidas.append(k)
        seguinte = k + 1
        while (seguinte < len(palavras_do_documento) and seguinte not in na_linha
               and all(isinstance(item, str) for item in palavras_do_documento[seguinte])):
            escolhidas.append(seguinte)
            seguinte += 1
    saida = []
    for k in escolhidas:
        grupo = [indice_de[item] for item in palavras_do_documento[k] if item in indice_de]
        texto = "".join(normalizar(item) if isinstance(item, str) else letra(indice_de[item])
                        for item in palavras_do_documento[k]
                        if isinstance(item, str) or item in indice_de)
        saida.append((_captura_minuscula(texto), grupo))
    return saida


#: O `X` de captura entre a peça (ou a coluna do peão) e a casa: `♖Xf2` é `♖xf2`.
_CAPTURA_MAIUSCULA = re.compile(r"(?<=[♔♕♖♗♘♚♛♜♝♞KQRBNa-h1-8])X(?=[a-h][1-8])")


def _captura_minuscula(palavra: str) -> str:
    """A captura sempre em minúscula: nenhum lance se escreve com `X`."""
    return _CAPTURA_MAIUSCULA.sub("x", palavra)


def _caixa_pela_altura(boxes: Sequence[BoxEntry], indices: Sequence[int]) -> Dict[int, str]:
    """
    `{índice: letra}` das letras de caixa ambígua cuja altura desmente a caixa lida.

    A régua é da própria linha: a altura-x é a mediana das minúsculas sem haste
    (`a e m n r u`), a da maiúscula, a das letras de altura conhecida. Sem as duas,
    ou com elas perto demais (um título em versal), nada muda. No Odds & Ends o `O`
    lido pelo padrão do livro tinha 19 px, a altura do `c` e do `s`, e o `C`
    maiúsculo 31.
    """
    def altura(i: int) -> int:
        return boxes[i].y2 - boxes[i].y1

    baixas = [altura(i) for i in indices if boxes[i].char in _ALTURA_X]
    altas = [altura(i) for i in indices if boxes[i].char in _ALTURA_DE_MAIUSCULA]
    if not baixas:
        return {}
    x = statistics.median(baixas)
    maiuscula = statistics.median(altas) if altas else None
    if maiuscula is not None and maiuscula < 1.25 * x:
        return {}
    trocas = {}
    for i in indices:
        letra = boxes[i].char
        if letra not in LETRAS_DE_CAIXA_PELA_ALTURA:
            continue
        if maiuscula is None:
            # Só a minúscula se prova sem régua de maiúscula.
            certa = letra.lower() if altura(i) <= FOLGA_DA_ALTURA_X * x else letra
        else:
            corte = x + CORTE_DA_CAIXA * (maiuscula - x)
            certa = letra.lower() if altura(i) < corte else letra.upper()
        if certa != letra:
            trocas[i] = certa
    return trocas


def _linhas(boxes: Sequence[BoxEntry], leitura: Optional[OrdemDeLeitura] = None,
            estrutura: Optional[Estrutura] = None) -> List[_Linha]:
    linhas = []
    for trecho, linha in _palavras_por_trecho(boxes, leitura, estrutura):
        indices = [i for _, grupo in linha for i in grupo]
        texto = " ".join(t for t, _ in linha if t).strip()
        if not texto or not indices:
            continue
        nova = _Linha(texto, min(boxes[i].y1 for i in indices),
                      max(boxes[i].y2 for i in indices), indices, trecho)
        if estrutura is not None:
            _com_a_estrutura(nova, linha, boxes, estrutura)
        linhas.append(nova)
    return linhas


def _com_a_estrutura(linha: _Linha, palavras_da_linha, boxes: Sequence[BoxEntry],
                     estrutura: Estrutura) -> None:
    """A função, o parágrafo, o hífen e os estilos da linha, pela `Estrutura`."""
    entradas = [boxes[i] for i in linha.indices]
    funcoes = [estrutura.funcao(b) for b in entradas]
    linha.funcao = max(dict.fromkeys(funcoes), key=funcoes.count)   # o empate: a primeira
    linha.paragrafo = id(entradas[0]) in estrutura.paragrafo_antes
    linha.hifen = id(entradas[-1]) in estrutura.hifen_de_quebra and linha.texto.endswith("-")
    linha.primeiro, linha.ultimo = id(entradas[0]), id(entradas[-1])
    linha.juncoes = estrutura.juncoes
    for nome, marcados in (("negrito", estrutura.negrito), ("italico", estrutura.italico),
                           ("duvidosos", estrutura.duvidosos)):
        # O estilo cobre o glifo de vários caracteres só se todos o têm; a dúvida, se um
        # só a tem (a palavra inteira é onde olhar).
        basta_um = nome == "duvidosos"
        trechos: List[Tuple[int, int]] = []
        posicao = 0
        for texto, grupo in palavras_da_linha:
            if not texto:
                continue
            if len(texto) == len(grupo):            # um caractere por glifo: letra a letra
                for k, i in enumerate(grupo):
                    if id(boxes[i]) in marcados:
                        trechos.append((posicao + k, posicao + k + 1))
            elif (any if basta_um else all)(id(boxes[i]) in marcados for i in grupo):
                trechos.append((posicao, posicao + len(texto)))
            posicao += len(texto) + 1
        setattr(linha, nome, _unir_trechos(trechos, linha.texto))


def _unir_trechos(trechos: Sequence[Tuple[int, int]], texto: str = "") -> List[Tuple[int, int]]:
    """Os trechos ordenados, com os encostados (ou separados só por um espaço de `texto`)
    num só. Uma letra não marcada entre dois trechos continua de fora."""
    saida: List[Tuple[int, int]] = []
    for inicio, fim in sorted(trechos):
        if saida and (inicio <= saida[-1][1] or (
                inicio == saida[-1][1] + 1 and texto[saida[-1][1]:inicio] == " ")):
            saida[-1] = (saida[-1][0], max(saida[-1][1], fim))
        else:
            saida.append((inicio, fim))
    return saida


def _juntar(linhas: Sequence[_Linha], manter_quebras: bool = False
            ) -> Tuple[str, List[Tuple[int, int]], List[Tuple[int, int]],
                       List[Tuple[int, int]]]:
    """O texto do parágrafo e os trechos em negrito, em itálico e duvidosos, já no texto
    juntado.

    O hífen de quebra decidido no Documento (§6.3) sai sempre; o não decidido sai pela
    regra da letra antes e da minúscula depois. Com `manter_quebras`, as
    linhas se juntam por `\\n` e todo hífen fica, como impresso."""
    texto, negrito, italico, duvidosos = "", [], [], []
    anterior: Optional[_Linha] = None
    for linha in linhas:
        if anterior is None:
            base = 0
        elif manter_quebras:
            texto += "\n"
            base = len(texto)
        elif (anterior.ultimo, linha.primeiro) in linha.juncoes:
            base = len(texto)                   # a palavra que o hífen apagado partia
        elif anterior.hifen or (texto.endswith("-") and len(texto) > 1 and texto[-2].isalpha()
                                and linha.texto[:1].islower()):
            texto = texto[:-1]
            base = len(texto)
            # O trecho que acabava no hífen não pode cobrir a letra da linha seguinte.
            negrito = [(a, min(b, base)) for a, b in negrito if a < base]
            italico = [(a, min(b, base)) for a, b in italico if a < base]
            duvidosos = [(a, min(b, base)) for a, b in duvidosos if a < base]
        else:
            texto += " "
            base = len(texto)
        texto += linha.texto
        negrito += [(base + a, base + b) for a, b in linha.negrito]
        italico += [(base + a, base + b) for a, b in linha.italico]
        duvidosos += [(base + a, base + b) for a, b in linha.duvidosos]
        anterior = linha

    def cortados(trechos):
        return _unir_trechos([(a, min(b, len(texto))) for a, b in trechos if a < len(texto)],
                             texto)
    return texto, cortados(negrito), cortados(italico), cortados(duvidosos)


@dataclass
class ParagrafoExportado(Paragrafo):
    """O `Paragrafo` do core com o que só esta exportação sabe: os trechos `(início, fim)`
    dos glifos duvidosos, para o realce do DOCX (`Opcoes.realcar_duvidosos`)."""

    duvidosos: List[Tuple[int, int]] = field(default_factory=list)


def _juntar_entre_paginas(paginas: Sequence[PaginaExtraida]) -> None:
    """`core.pdf_nativo.juntar_entre_paginas`, levando os duvidosos do parágrafo que
    volta para a página de antes (o core leva só o negrito e o itálico)."""
    from core import pdf_nativo

    primeiros = [p.blocos[0] if p.blocos else None for p in paginas]
    pdf_nativo.juntar_entre_paginas(paginas)
    for atual, seguinte, primeiro in zip(paginas, paginas[1:], primeiros[1:]):
        if primeiro is None or (seguinte.blocos and seguinte.blocos[0] is primeiro):
            continue
        antes = atual.blocos[-1]
        trechos = getattr(primeiro, "duvidosos", None)
        if trechos and isinstance(antes, ParagrafoExportado):
            # O core escreve `fim + " " + começo`: o texto de depois acaba no fim do novo.
            deslocamento = len(antes.texto) - len(primeiro.texto)
            antes.duvidosos = list(antes.duvidosos) + [
                (a + deslocamento, z + deslocamento) for a, z in trechos
                if a + deslocamento >= 0]


def _quebras_da_camada(pagina: PaginaExtraida) -> None:
    """`manter_quebras` na página da camada nativa: a quebra volta onde cada linha impressa
    começa (`Paragrafo.inicios`). O espaço antes dela vira `\\n`, sem mudar o comprimento;
    depois do hífen que a camada guardou colado (`inter-essante`), o `\\n` entra. Sem espaço
    nem hífen, o core tirou o hífen da palavra partida (o dicionário disse que era quebra, ou
    era o hífen brando: `core.pdf_nativo._juntar`): o hífen volta com a quebra (`intere-\\n
    ssante`, como impresso). Os trechos de estilo e os inícios seguintes andam o que entrou; o
    hífen que volta fica no trecho da letra antes dele."""
    from core.lexico import HIFENS

    for bloco in pagina.blocos:
        if not isinstance(bloco, Paragrafo) or bloco.titulo or not bloco.inicios:
            continue
        letras = list(bloco.texto)
        inseridas: List[Tuple[int, str]] = []    # (posição no texto de antes, o que entra)
        for inicio in bloco.inicios:
            if not 0 < inicio <= len(letras):
                continue
            if letras[inicio - 1] == " ":
                letras[inicio - 1] = "\n"
            elif letras[inicio - 1] in HIFENS:
                inseridas.append((inicio, "\n"))
            elif (inicio < len(letras) and letras[inicio - 1].isalnum()
                  and letras[inicio].isalnum()):
                inseridas.append((inicio, "-\n"))
        for inicio, texto in sorted(inseridas, reverse=True):
            letras[inicio:inicio] = list(texto)
        if inseridas:
            def andar(p: int) -> int:
                return p + sum(len(t) for i, t in inseridas if i <= p)

            def andar_fim(p: int) -> int:           # o fim exclusivo não leva o `\n` dele,
                return p + sum(len(t) if i < p else len(t) - 1     # mas leva o hífen que
                               for i, t in inseridas if i <= p)    # volta

            for nome in ("negrito", "italico", "duvidosos"):
                trechos = getattr(bloco, nome, None)
                if trechos:
                    setattr(bloco, nome, [(andar(a), andar_fim(z)) for a, z in trechos])
            bloco.inicios = [andar(i) for i in bloco.inicios]
            bloco.pesos = bloco.lacunas = None    # uma medida por caractere: não bate mais
        bloco.texto = "".join(letras)


def paragrafos(boxes: Sequence[BoxEntry], cortes: Sequence[int] = ()) -> List[Paragrafo]:
    """Os parágrafos da página: linhas seguidas, cortadas onde o vão cresce.

    `cortes` são alturas da página (o topo de cada diagrama) que também
    separam parágrafos: o texto de cima e o de baixo de um diagrama não se
    juntam mesmo com passo normal.
    """
    return [p for _trecho, p in _paragrafos_por_trecho(boxes, cortes)]


def _paragrafos_por_trecho(boxes: Sequence[BoxEntry], cortes: Sequence[int] = (),
                           leitura: Optional[OrdemDeLeitura] = None,
                           estrutura: Optional[Estrutura] = None,
                           manter_quebras: bool = False
                           ) -> List[Tuple[Tuple[int, int], Paragrafo]]:
    """Os parágrafos de `paragrafos`, cada um com o trecho de leitura em que começa.

    Com a `Estrutura`, também abre parágrafo onde a função da área muda (o título, a
    nota, a legenda) e onde o Documento pediu (`paragrafo_antes`); a linha de área
    `titulo` sai como título de capítulo (o `<h1>` do sumário)."""
    linhas = _linhas(boxes, leitura, estrutura)
    if not linhas:
        return []
    passos = [b.topo - a.topo for a, b in zip(linhas, linhas[1:])
              if b.topo > a.topo and a.trecho == b.trecho]
    passo = statistics.median(passos) if passos else 0
    grupos: List[List[_Linha]] = [[linhas[0]]]
    for anterior, linha in zip(linhas, linhas[1:]):
        salto = linha.topo - anterior.topo
        # Outro trecho (a coluna seguinte, a faixa que atravessa) também abre
        # parágrafo, como voltar para cima.
        if (salto <= 0 or linha.trecho != anterior.trecho
                or (passo and salto > SALTO_DE_PARAGRAFO * passo)
                or any(anterior.pe <= y < linha.topo for y in cortes)
                or linha.funcao != anterior.funcao or linha.paragrafo):
            grupos.append([linha])
        else:
            grupos[-1].append(linha)
    saida = []
    for g in grupos:
        texto, negrito, italico, duvidosos = _juntar(g, manter_quebras)
        titulo = g[0].funcao == "titulo"
        saida.append((g[0].trecho, ParagrafoExportado(
            texto, titulo=titulo, nivel=1 if titulo else 2, negrito=negrito, italico=italico,
            topo=g[0].topo, pe=g[-1].pe, duvidosos=duvidosos)))
    return saida


def _figura(imagem: Image.Image, caixa: Tuple[int, int, int, int],
            aviso: str = "diagrama não lido: recorte da página") -> Figura:
    recorte = imagem.convert("L").crop(caixa)
    dados = io.BytesIO()
    recorte.save(dados, format="PNG")
    return Figura(png=dados.getvalue(), largura=recorte.width, altura=recorte.height,
                  origem="recorte", caixa=tuple(caixa), casas_de_largura=8.0, aviso=aviso)


#: O aviso do diagrama recortado porque as opções pediram recortes (§12.1).
RECORTE_PEDIDO = "recorte pedido nas opções da exportação"


def _aviso_do_recorte(diagrama: DiagramaLido) -> str:
    if not diagrama.lido:
        return f"diagrama não lido: {diagrama.erro or 'recorte da página'}"
    if diagrama.validacao is not None and not diagrama.validacao.confiavel:
        return f"posição não conferida: {diagrama.validacao.aviso}"
    return f"posição não conferida e sem a confiança do porteiro: {diagrama.motivo}"


def _figura_desenhada(diagrama: DiagramaLido) -> Figura:
    """O diagrama redesenhado do FEN, como o `core.livro` faz no modo "render".

    O indicador de quem joga só é desenhado quando o lado foi dito (pela
    legenda ou na conferência); sem isso o FEN leva `w` por exigência do
    formato, e o texto alternativo carimba que foi assumido.
    """
    from core import render_diagrama as rd

    lado = diagrama.lado if diagrama.lado_origem else None
    fen = diagrama.fen
    png, largura, altura = rd.desenhar(fen, orientacao=diagrama.orientacao, lado_a_jogar=lado)
    linhas, emolduradas = rd.linhas_do_diagrama(fen, rd.carregar(rd.FONTE_PADRAO),
                                                diagrama.orientacao)
    return Figura(png, largura, altura, fen=fen, origem="render", linhas=linhas,
                  linhas_emolduradas=emolduradas, fonte=rd.FONTE_PADRAO,
                  orientacao=diagrama.orientacao,
                  casas_de_largura=largura * 8.0 / rd.lado_efetivo(rd.LADO_PADRAO),
                  caixa=tuple(diagrama.caixa), lado_a_jogar=lado,
                  lado_origem=diagrama.lado_origem or "convencao",
                  revisao_pendente=not diagrama.conferido)


def figura_do_diagrama(imagem: Image.Image, diagrama: DiagramaLido) -> Figura:
    """Desenhado do FEN se a leitura merece confiança; senão, o recorte."""
    if diagrama.confiavel:
        from core import render_diagrama as rd

        try:
            return _figura_desenhada(diagrama)
        except (rd.FonteDesconhecida, rd.FonteIncompleta) as erro:
            # Sem a fonte de xadrez, o livro sai com o recorte e diz por quê.
            return _figura(imagem, diagrama.caixa, f"não deu para desenhar: {erro}")
    return _figura(imagem, diagrama.caixa, _aviso_do_recorte(diagrama))


#: Até onde, em casas, as coordenadas impressas ficam do tabuleiro: os números à
#: esquerda e as letras embaixo.
ALCANCE_DAS_COORDENADAS = 0.9


def _sem_coordenadas(boxes: Sequence[BoxEntry],
                     tabuleiros: Sequence[Tuple[int, int, int, int]]) -> List[BoxEntry]:
    """
    Os boxes de texto, sem o que está dentro do tabuleiro nem as coordenadas dele.

    No Odds & Ends os números de `8` a `1` à esquerda e o `a b c d e f g h` embaixo
    saíam no texto (`476542 a b c d e f g h10...♗h3?!`). Coordenada é **um
    caractere sozinho**: o número à esquerda, na altura de uma fila, e a letra
    embaixo, sob uma coluna — sem vizinho a menos de meia casa. A legenda logo
    abaixo do tabuleiro (`Branco joga`, `1-40`) tem as letras coladas e fica; o
    lance impresso logo acima (`9.e4 ♕h5 10.♘xc4`) também.
    """
    if not tabuleiros:
        return list(boxes)

    def centro(b: BoxEntry) -> Tuple[float, float]:
        return (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2

    def sozinho(b: BoxEntry, casa: float) -> bool:
        cx, cy = centro(b)
        return not any(o is not b and abs(centro(o)[0] - cx) < 0.5 * casa
                       and abs(centro(o)[1] - cy) < 0.5 * (b.y2 - b.y1 + o.y2 - o.y1)
                       for o in boxes)

    def fora(b: BoxEntry) -> bool:
        cx, cy = centro(b)
        for x1, y1, x2, y2 in tabuleiros:
            casa = max(1.0, (x2 - x1) / 8)
            folga = ALCANCE_DAS_COORDENADAS * casa
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                return True
            if (b.char in "12345678" and x1 - folga <= cx < x1 and y1 <= cy <= y2
                    and sozinho(b, casa)):
                return True
            if (b.char in "abcdefgh" and x1 <= cx <= x2 and y2 < cy <= y2 + folga
                    and sozinho(b, casa)):
                return True
        return False

    return [b for b in boxes if not fora(b)]


def pagina_extraida(indice: int, boxes: Sequence[BoxEntry],
                    tabuleiros: Sequence[Tuple[int, int, int, int]] = (),
                    imagem: Optional[Image.Image] = None,
                    diagramas: Sequence[DiagramaLido] = (),
                    estrutura: Optional[Estrutura] = None,
                    manter_margens: bool = False,
                    desenhar_diagramas: bool = True,
                    manter_quebras: bool = False) -> PaginaExtraida:
    """A página gravada no formato que os escritores do PyBoxEditor pedem.

    Os diagramas entram na altura em que estão, quando há a imagem: os lidos
    com confiança, redesenhados do FEN; os outros, como recorte da página. Com a
    `Estrutura` do Documento, as áreas de margem e as de ignorar saem (as de margem
    ficam com `manter_margens`), e títulos, estilos e parágrafos seguem o Documento.
    """
    cortes = [t[1] for t in tabuleiros] if imagem is not None else []
    texto = _sem_coordenadas([b for b in boxes if b.char], tabuleiros)
    if estrutura is not None:
        fora = ("ignorar",) if manter_margens else FORA_DA_EXPORTACAO
        texto = [b for b in texto if estrutura.funcao(b) not in fora]
    leitura = OrdemDeLeitura.da_pagina(texto)
    com_trecho = _paragrafos_por_trecho(texto, cortes, leitura, estrutura, manter_quebras)
    blocos: list = [p for _trecho, p in com_trecho]
    figuras = []
    if imagem is not None:
        # Cada figura no trecho da coluna dela, e na altura dela dentro do trecho:
        # só pela altura, o diagrama da esquerda caía entre os parágrafos da direita.
        figuras = [(leitura.chave((d.caixa[0] + d.caixa[2]) / 2, d.caixa[1]), d.caixa[1],
                    figura_do_diagrama(imagem, d) if desenhar_diagramas
                    else _figura(imagem, d.caixa, RECORTE_PEDIDO))
                   for d in para_caixas(tabuleiros, diagramas)]
        ordem = [(trecho, p.topo or 0, p) for trecho, p in com_trecho] + figuras
        blocos = [b for _t, _y, b in sorted(ordem, key=lambda item: (item[0], item[1]))]
    largura, altura = imagem.size if imagem is not None else (0, 0)
    return PaginaExtraida(numero=indice, blocos=blocos,
                          caracteres=sum(len(b.char) for b in boxes if b.char),
                          diagramas=len(figuras), altura=altura, largura=largura,
                          dpi=DPI_DA_LEITURA)


def titulos_das_paginas(projeto: ProjetoDeLivro, indices: Sequence[int],
                        estruturas: Optional[dict] = None) -> List[Tuple[int, str]]:
    """`[(índice da página, título)]` das áreas de título do Documento, na ordem do livro:
    os marcadores do PDF pesquisável (§12.1). `estruturas` (índice -> `Estrutura.da_pagina`)
    poupa carregar os modelos de novo."""
    saida = []
    for indice in indices:
        entries, estrutura = (estruturas[indice] if estruturas is not None
                              else Estrutura.da_pagina(projeto.carregar_modelo(indice)))
        do_titulo = [b for b in entries if estrutura.funcao(b) == "titulo"]
        if not do_titulo:
            continue
        for _trecho, paragrafo in _paragrafos_por_trecho(do_titulo, (), OrdemDeLeitura(), estrutura):
            if paragrafo.titulo and paragrafo.texto.strip():
                saida.append((indice, paragrafo.texto.strip()))
    return saida
