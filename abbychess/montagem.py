"""Das páginas gravadas no projeto ao intermediário do PyBoxEditor (`core.pagina`): as linhas e
as palavras pela ordem de leitura, a estrutura que o Documento (§4.2) dá a cada glifo, os
parágrafos pelo vão entre linhas e as figuras dos diagramas. Puro: nada aqui grava nem abre
arquivo. À parte de `exportar.py` (SPEC-qualidade Q-E6, CA-Q-A1)."""

from __future__ import annotations

import io
import re
import statistics
from dataclasses import dataclass, field
from typing import AbstractSet, Collection, Dict, List, Optional, Sequence, Tuple

from PIL import Image

from core.box_model import BoxEntry
from core.pagina import Figura, PaginaExtraida, Paragrafo

from abbychess.diagramas import DiagramaLido, em_ordem, para_caixas
from abbychess.layout import OrdemDeLeitura, lugares_da_pilha
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
#: O que vem antes da primeira letra de uma palavra: só ela sobe para maiúscula pela altura.
_ABRE_PALAVRA = frozenset("([{\"'“‘«¿¡")


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
    #: A ordem da área de texto de cada box, quando o usuário as ordenou (Ordenar).
    ordens: Dict[int, int] = field(default_factory=dict)
    #: As áreas da página, para a ordem da figura de cada tabuleiro.
    zonas: Sequence = ()
    #: Os boxes vistos e aceitos no Documento (§6.3): a caixa pela altura não os troca.
    revisados: set = field(default_factory=set)
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

        self.zonas = zonas
        areas = [z for z in zonas if z.tipo in (zn.TEXTO, zn.IGNORAR)]
        funcao_da, protege = _funcoes_das_areas(areas)
        for b in lidos:
            e = b.entry
            area = zn.zona_que_vale(areas, (e.x1 + e.x2) / 2, (e.y1 + e.y2) / 2)
            if area is None:
                continue
            self.funcoes[id(e)] = funcao_da[id(area)]
            if area.ordem is not None:
                self.ordens[id(e)] = area.ordem
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
            if b.revisado:
                self.revisados.add(chave)

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
    #: Da `Estrutura`: a ordem da área da linha (`None`: sem ordem).
    ordem: Optional[int] = None
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
            saida.append((chave, _palavras_da_linha(linha, trecho, boxes, documento,
                                                    normalizar_saida)))
    return saida


def _palavras_da_linha(linha, trecho, boxes: Sequence[BoxEntry], documento: Optional[Estrutura],
                       normalizar_saida) -> List[Tuple[str, List[int]]]:
    """As palavras de uma linha do trecho: as do Documento, quando ele as tem todas; senão,
    as da geometria. A letra de cada glifo já com a caixa pela altura."""
    indices = [trecho[s.indice] for p in linha for s in p.simbolos]
    caixa = _caixa_pela_altura(boxes, indices, _primeiras_letras(linha, trecho, boxes),
                               documento.revisados if documento is not None else ())

    def letra(i: int) -> str:
        return normalizar_saida(caixa.get(i, boxes[i].char))

    pelo_documento = (_pelo_documento(indices, boxes, documento, letra, normalizar_saida)
                      if documento is not None else None)
    if pelo_documento is not None:
        return pelo_documento
    return _pela_geometria(linha, trecho, letra)


def _pela_geometria(linha, trecho, letra) -> List[Tuple[str, List[int]]]:
    return [(_captura_minuscula("".join(letra(trecho[s.indice]) for s in p.simbolos)),
             [trecho[s.indice] for s in p.simbolos])
            for p in linha if p.simbolos]


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
    escolhidas = _com_as_so_de_virtuais(sorted({palavra_de[chave] for chave in indice_de}),
                                        palavras_do_documento)
    return [_palavra_do_documento(palavras_do_documento[k], indice_de, letra, normalizar)
            for k in escolhidas]


def _com_as_so_de_virtuais(na_linha: List[int], palavras_do_documento: list) -> List[int]:
    """As palavras do Documento na linha e, depois de cada uma, as só de virtuais que a
    seguem."""
    escolhidas = []
    for k in na_linha:
        escolhidas.append(k)
        seguinte = k + 1
        while (seguinte < len(palavras_do_documento) and seguinte not in na_linha
               and all(isinstance(item, str) for item in palavras_do_documento[seguinte])):
            escolhidas.append(seguinte)
            seguinte += 1
    return escolhidas


def _palavra_do_documento(itens, indice_de: Dict[int, int], letra, normalizar
                          ) -> Tuple[str, List[int]]:
    """(o texto, os índices dos boxes) da palavra do Documento: a letra de cada glifo da
    linha e o caractere de cada virtual."""
    grupo = [indice_de[item] for item in itens if item in indice_de]
    texto = "".join(normalizar(item) if isinstance(item, str) else letra(indice_de[item])
                    for item in itens if isinstance(item, str) or item in indice_de)
    return _captura_minuscula(texto), grupo


#: O `X` de captura entre a peça (ou a coluna do peão) e a casa: `♖Xf2` é `♖xf2`.
_CAPTURA_MAIUSCULA = re.compile(r"(?<=[♔♕♖♗♘♚♛♜♝♞KQRBNa-h1-8])X(?=[a-h][1-8])")


def _captura_minuscula(palavra: str) -> str:
    """A captura sempre em minúscula: nenhum lance se escreve com `X`."""
    return _CAPTURA_MAIUSCULA.sub("x", palavra)


def _primeiras_letras(linha, trecho, boxes: Sequence[BoxEntry]) -> AbstractSet[int]:
    """O índice do primeiro glifo de cada palavra da linha, depois do que abre a palavra."""
    primeiras = set()
    for palavra in linha:
        for simbolo in palavra.simbolos:
            i = trecho[simbolo.indice]
            if boxes[i].char not in _ABRE_PALAVRA:
                primeiras.add(i)
                break
    return primeiras


def _caixa_pela_altura(boxes: Sequence[BoxEntry], indices: Sequence[int],
                       primeiras: AbstractSet[int], revisados: Collection[int]) -> Dict[int, str]:
    """
    `{índice: letra}` das letras de caixa ambígua cuja altura desmente a caixa lida.

    A régua é da própria linha: a altura-x é a mediana das minúsculas sem haste
    (`a e m n r u`), a da maiúscula, a das letras de altura conhecida. Sem as duas,
    ou com elas perto demais (um título em versal), nada muda. No Odds & Ends o `O`
    lido pelo padrão do livro tinha 19 px, a altura do `c` e do `s`, e o `C`
    maiúsculo 31.

    A letra só sobe nas `primeiras`: a caixa que engoliu tinta é alta sem a letra ser
    (`eVitar`), e no meio da palavra as subidas medidas erram todas. O que o usuário
    confirmou (manual, ou nos `revisados`) e o nativo ficam como estão, mas medem a régua.
    """
    baixas = _alturas(boxes, indices, _ALTURA_X)
    altas = _alturas(boxes, indices, _ALTURA_DE_MAIUSCULA)
    if not baixas:
        return {}
    x = statistics.median(baixas)
    maiuscula = statistics.median(altas) if altas else None
    if maiuscula is not None and maiuscula < 1.25 * x:
        return {}
    trocas = _trocas_de_caixa(boxes, _trocaveis(boxes, indices, revisados), x, maiuscula)
    return {i: certa for i, certa in trocas.items() if certa.islower() or i in primeiras}


def _trocaveis(boxes: Sequence[BoxEntry], indices: Sequence[int],
               revisados: Collection[int]) -> List[int]:
    """Os `indices` que a altura pode trocar: menos os `revisados`, o manual e o nativo."""
    from abbychess import contexto

    return [i for i in indices if id(boxes[i]) not in revisados
            and contexto.volta_pelo_contexto(boxes[i].source)]


def _alturas(boxes: Sequence[BoxEntry], indices: Sequence[int], letras) -> List[int]:
    """A altura de cada glifo da linha cuja letra está em `letras`."""
    return [boxes[i].y2 - boxes[i].y1 for i in indices if boxes[i].char in letras]


def _trocas_de_caixa(boxes: Sequence[BoxEntry], indices: Sequence[int], x: float,
                     maiuscula: Optional[float]) -> Dict[int, str]:
    """A letra de caixa ambígua cuja altura, na régua da linha (a altura-x `x` e a da
    `maiuscula`), desmente a caixa lida."""
    trocas = {}
    for i in indices:
        letra = boxes[i].char
        if letra not in LETRAS_DE_CAIXA_PELA_ALTURA:
            continue
        altura = boxes[i].y2 - boxes[i].y1
        if maiuscula is None:
            # Só a minúscula se prova sem régua de maiúscula.
            certa = letra.lower() if altura <= FOLGA_DA_ALTURA_X * x else letra
        else:
            corte = x + CORTE_DA_CAIXA * (maiuscula - x)
            certa = letra.lower() if altura < corte else letra.upper()
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
        linhas.append(_linha_nova(texto, indices, trecho, linha, boxes, estrutura))
    return linhas


def _linha_nova(texto: str, indices: List[int], trecho, palavras_da_linha,
                boxes: Sequence[BoxEntry], estrutura: Optional[Estrutura]) -> _Linha:
    nova = _Linha(texto, min(boxes[i].y1 for i in indices),
                  max(boxes[i].y2 for i in indices), indices, trecho)
    if estrutura is not None:
        _com_a_estrutura(nova, palavras_da_linha, boxes, estrutura)
    return nova


def _com_a_estrutura(linha: _Linha, palavras_da_linha, boxes: Sequence[BoxEntry],
                     estrutura: Estrutura) -> None:
    """A função, o parágrafo, o hífen e os estilos da linha, pela `Estrutura`."""
    entradas = [boxes[i] for i in linha.indices]
    funcoes = [estrutura.funcao(b) for b in entradas]
    linha.funcao = max(dict.fromkeys(funcoes), key=funcoes.count)   # o empate: a primeira
    ordens = [estrutura.ordens.get(id(b)) for b in entradas]
    linha.ordem = max(dict.fromkeys(ordens), key=ordens.count)
    linha.paragrafo = id(entradas[0]) in estrutura.paragrafo_antes
    linha.hifen = id(entradas[-1]) in estrutura.hifen_de_quebra and linha.texto.endswith("-")
    linha.primeiro, linha.ultimo = id(entradas[0]), id(entradas[-1])
    linha.juncoes = estrutura.juncoes
    for nome, marcados in (("negrito", estrutura.negrito), ("italico", estrutura.italico),
                           ("duvidosos", estrutura.duvidosos)):
        # O estilo cobre o glifo de vários caracteres só se todos o têm; a dúvida, se um
        # só a tem (a palavra inteira é onde olhar).
        trechos = _trechos_da_linha(palavras_da_linha, boxes, marcados, nome == "duvidosos")
        setattr(linha, nome, _unir_trechos(trechos, linha.texto))


def _trechos_da_linha(palavras_da_linha, boxes: Sequence[BoxEntry], marcados: set,
                      basta_um: bool) -> List[Tuple[int, int]]:
    """Os trechos `(início, fim)` da linha com os glifos `marcados`: letra a letra quando a
    palavra tem um caractere por glifo; senão, a palavra inteira."""
    trechos: List[Tuple[int, int]] = []
    posicao = 0
    for texto, grupo in palavras_da_linha:
        if not texto:
            continue
        if len(texto) == len(grupo):            # um caractere por glifo: letra a letra
            trechos += _letra_a_letra(grupo, posicao, boxes, marcados)
        elif (any if basta_um else all)(id(boxes[i]) in marcados for i in grupo):
            trechos.append((posicao, posicao + len(texto)))
        posicao += len(texto) + 1
    return trechos


def _letra_a_letra(grupo: List[int], posicao: int, boxes: Sequence[BoxEntry],
                   marcados: set) -> List[Tuple[int, int]]:
    return [(posicao + k, posicao + k + 1) for k, i in enumerate(grupo)
            if id(boxes[i]) in marcados]


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
    texto = ""
    trechos: Tuple[list, list, list] = ([], [], [])          # o negrito, o itálico, a dúvida
    anterior: Optional[_Linha] = None
    for linha in linhas:
        texto, base, cortou = _emenda(texto, anterior, linha, manter_quebras)
        if cortou:
            # O trecho que acabava no hífen não pode cobrir a letra da linha seguinte.
            trechos = tuple([(a, min(b, base)) for a, b in t if a < base] for t in trechos)
        texto += linha.texto
        for juntos, da_linha in zip(trechos, (linha.negrito, linha.italico, linha.duvidosos)):
            juntos += [(base + a, base + b) for a, b in da_linha]
        anterior = linha

    def cortados(trechos):
        return _unir_trechos([(a, min(b, len(texto))) for a, b in trechos if a < len(texto)],
                             texto)
    negrito, italico, duvidosos = trechos
    return texto, cortados(negrito), cortados(italico), cortados(duvidosos)


def _emenda(texto: str, anterior: Optional[_Linha], linha: _Linha, manter_quebras: bool
            ) -> Tuple[str, int, bool]:
    """(o texto pronto para receber a linha, onde ela começa nele, se o hífen de quebra
    saiu): a quebra mantida, a junção sem espaço, o hífen tirado ou o espaço."""
    if anterior is None:
        return texto, 0, False
    if manter_quebras:
        return texto + "\n", len(texto) + 1, False
    if (anterior.ultimo, linha.primeiro) in linha.juncoes:
        return texto, len(texto), False         # a palavra que o hífen apagado partia
    if _hifen_de_quebra(texto, anterior, linha):
        return texto[:-1], len(texto) - 1, True
    return texto + " ", len(texto) + 1, False


def _hifen_de_quebra(texto: str, anterior: _Linha, linha: _Linha) -> bool:
    """O hífen decidido no Documento, ou o da regra: a letra antes e a minúscula depois."""
    return anterior.hifen or (texto.endswith("-") and len(texto) > 1 and texto[-2].isalpha()
                              and linha.texto[:1].islower())


@dataclass
class ParagrafoExportado(Paragrafo):
    """O `Paragrafo` do core com o que só esta exportação sabe: os trechos `(início, fim)`
    dos glifos duvidosos, para o realce do DOCX (`Opcoes.realcar_duvidosos`)."""

    duvidosos: List[Tuple[int, int]] = field(default_factory=list)
    #: A ordem da área de onde ele veio, quando o usuário as ordenou.
    ordem_da_area: Optional[int] = None


def _juntar_entre_paginas(paginas: Sequence[PaginaExtraida]) -> None:
    """`core.pdf_nativo.juntar_entre_paginas`, levando os duvidosos do parágrafo que
    volta para a página de antes (o core leva só o negrito e o itálico)."""
    from core import pdf_nativo

    primeiros = [p.blocos[0] if p.blocos else None for p in paginas]
    pdf_nativo.juntar_entre_paginas(paginas)
    for atual, seguinte, primeiro in zip(paginas, paginas[1:], primeiros[1:]):
        if primeiro is None or (seguinte.blocos and seguinte.blocos[0] is primeiro):
            continue
        _levar_os_duvidosos(atual.blocos[-1], primeiro)


def _levar_os_duvidosos(antes, primeiro) -> None:
    """Os duvidosos do parágrafo `primeiro`, que voltou para o fim de `antes`."""
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
        if isinstance(bloco, Paragrafo) and not bloco.titulo and bloco.inicios:
            _quebras_do_paragrafo(bloco, HIFENS)


def _quebras_do_paragrafo(bloco: Paragrafo, hifens) -> None:
    letras = list(bloco.texto)
    inseridas = _o_que_entra(letras, bloco.inicios, hifens)
    for inicio, texto in sorted(inseridas, reverse=True):
        letras[inicio:inicio] = list(texto)
    if inseridas:
        _andar_os_trechos(bloco, inseridas)
    bloco.texto = "".join(letras)


def _o_que_entra(letras: List[str], inicios: Sequence[int], hifens
                 ) -> List[Tuple[int, str]]:
    """(posição no texto de antes, o que entra) em cada início de linha impressa; o espaço
    antes dele vira `\\n` em `letras`, sem mudar o comprimento."""
    inseridas: List[Tuple[int, str]] = []
    for inicio in inicios:
        if not 0 < inicio <= len(letras):
            continue
        if letras[inicio - 1] == " ":
            letras[inicio - 1] = "\n"
        elif letras[inicio - 1] in hifens:
            inseridas.append((inicio, "\n"))
        elif (inicio < len(letras) and letras[inicio - 1].isalnum()
              and letras[inicio].isalnum()):
            inseridas.append((inicio, "-\n"))
    return inseridas


def _andar_os_trechos(bloco: Paragrafo, inseridas: List[Tuple[int, str]]) -> None:
    """Os trechos de estilo e os inícios andam o que entrou antes deles."""
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
    passo = _passo_mediano(linhas, no_trecho=True)
    grupos: List[List[_Linha]] = [[linhas[0]]]
    for anterior, linha in zip(linhas, linhas[1:]):
        if _abre_paragrafo(anterior, linha, passo, cortes):
            grupos.append([linha])
        else:
            grupos[-1].append(linha)
    return [_paragrafo_do_grupo(g, manter_quebras) for g in grupos]


def _passo_mediano(linhas: List[_Linha], *, no_trecho: bool = False) -> float:
    """O passo mediano entre linhas seguidas que descem; com `no_trecho`, só entre as do
    mesmo trecho (as margens olham a página inteira, `margens._margem_da_pagina`)."""
    passos = [b.topo - a.topo for a, b in zip(linhas, linhas[1:])
              if b.topo > a.topo and (not no_trecho or a.trecho == b.trecho)]
    return statistics.median(passos) if passos else 0


def _abre_paragrafo(anterior: _Linha, linha: _Linha, passo: float, cortes: Sequence[int]) -> bool:
    """O vão cresce, a linha volta para cima, muda de trecho (a coluna seguinte, a faixa que
    atravessa) ou de função, passa por um corte, ou o Documento pediu."""
    salto = linha.topo - anterior.topo
    return (salto <= 0 or linha.trecho != anterior.trecho
            or (passo and salto > SALTO_DE_PARAGRAFO * passo)
            or any(anterior.pe <= y < linha.topo for y in cortes)
            or linha.funcao != anterior.funcao or linha.paragrafo or linha.ordem != anterior.ordem)


def _paragrafo_do_grupo(g: List[_Linha], manter_quebras: bool
                        ) -> Tuple[Tuple[int, int], Paragrafo]:
    texto, negrito, italico, duvidosos = _juntar(g, manter_quebras)
    titulo = g[0].funcao == "titulo"
    return (g[0].trecho, ParagrafoExportado(
        texto, titulo=titulo, nivel=1 if titulo else 2, negrito=negrito, italico=italico,
        topo=g[0].topo, pe=g[-1].pe, duvidosos=duvidosos, ordem_da_area=g[0].ordem))


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
    texto = _texto_da_pagina(boxes, tabuleiros, estrutura, manter_margens)
    leitura = OrdemDeLeitura.da_pagina(texto, tabuleiros)
    com_trecho = _paragrafos_por_trecho(texto, cortes, leitura, estrutura, manter_quebras)
    blocos: list = [p for _trecho, p in com_trecho]
    figuras = []
    if imagem is not None:
        figuras = _figuras_da_pagina(imagem, leitura, tabuleiros, diagramas, desenhar_diagramas)
        figuras, com_trecho_e_topo = _com_a_pilha(texto, leitura, estrutura, tabuleiros, figuras,
                                                  com_trecho)
        blocos = _na_ordem_de_leitura(com_trecho_e_topo, figuras)
    blocos = _na_ordem_das_areas(blocos, figuras, tabuleiros, estrutura)
    largura, altura = imagem.size if imagem is not None else (0, 0)
    return PaginaExtraida(numero=indice, blocos=blocos,
                          caracteres=sum(len(b.char) for b in boxes if b.char),
                          diagramas=len(figuras), altura=altura, largura=largura,
                          dpi=DPI_DA_LEITURA)


def _na_ordem_das_areas(blocos: list, figuras: list, tabuleiros, estrutura: Optional[Estrutura]
                        ) -> list:
    """Os blocos pela ordem das áreas (`zonas.na_ordem_das_areas`), como no Documento."""
    if estrutura is None or not any(z.ordem is not None for z in estrutura.zonas):
        return blocos
    from abbychess import zonas as zn

    da_figura = {id(figura[2]): zn.ordem_do_tabuleiro(estrutura.zonas, caixa)
                 for figura, caixa in zip(figuras, em_ordem(tabuleiros))}
    return zn.na_ordem_das_areas(blocos, lambda b: da_figura.get(id(b),
                                                                 getattr(b, "ordem_da_area", None)))


def _texto_da_pagina(boxes: Sequence[BoxEntry], tabuleiros, estrutura: Optional[Estrutura],
                     manter_margens: bool) -> List[BoxEntry]:
    """Os boxes do texto: sem os do tabuleiro e as coordenadas dele e, com a `Estrutura`,
    sem as áreas de margem (salvo `manter_margens`) e as de ignorar."""
    texto = _sem_coordenadas([b for b in boxes if b.char], tabuleiros)
    if estrutura is None:
        return texto
    fora = ("ignorar",) if manter_margens else FORA_DA_EXPORTACAO
    return [b for b in texto if estrutura.funcao(b) not in fora]


def _figuras_da_pagina(imagem: Image.Image, leitura: OrdemDeLeitura, tabuleiros,
                       diagramas: Sequence[DiagramaLido], desenhar_diagramas: bool) -> list:
    """(trecho, altura, figura) de cada diagrama: cada figura no trecho da coluna dela, e na
    altura dela dentro do trecho (só pela altura, o diagrama da esquerda caía entre os
    parágrafos da direita)."""
    return [(leitura.chave((d.caixa[0] + d.caixa[2]) / 2, d.caixa[1]), d.caixa[1],
             figura_do_diagrama(imagem, d) if desenhar_diagramas
             else _figura(imagem, d.caixa, RECORTE_PEDIDO))
            for d in para_caixas(tabuleiros, diagramas)]


def _com_a_pilha(texto: Sequence[BoxEntry], leitura: OrdemDeLeitura, estrutura, tabuleiros,
                 figuras: list, com_trecho: list) -> Tuple[list, list]:
    """As figuras e os parágrafos como (trecho, topo, bloco) para ordenar: na coluna só de
    tabuleiros, cada figura e a legenda dela antes do comentário (`layout.lugares_da_pilha`)."""
    paragrafos = [(trecho, p.topo or 0, p) for trecho, p in com_trecho]
    if leitura.coluna_da_pilha is None:
        return figuras, paragrafos
    altura = statistics.median(b.y2 - b.y1 for b in texto)
    linhas = [(ln.trecho, ln.topo, ln.texto) for ln in _linhas(texto, leitura, estrutura)]
    lugares, legendas = lugares_da_pilha(leitura, tabuleiros, linhas, altura)
    novas = [(lugar[0], lugar[1] - 0.5, figura[2]) for lugar, figura in zip(lugares, figuras)]
    return novas, [_no_lugar(item, legendas) for item in paragrafos]


def _no_lugar(item: tuple, legendas: dict) -> tuple:
    """(trecho, topo, parágrafo), com o parágrafo da legenda antes da figura dela."""
    destino = legendas.get(item[:2])
    return item if destino is None else (destino[0], destino[1] - 0.6, item[2])


def _na_ordem_de_leitura(paragrafos, figuras) -> list:
    ordem = list(paragrafos) + figuras
    return [b for _t, _y, b in sorted(ordem, key=lambda item: (item[0], item[1]))]


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
