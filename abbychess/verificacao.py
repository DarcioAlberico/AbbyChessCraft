"""A verificação de texto do FineReader: andar pelas palavras que o léxico não conhece.

O léxico é o do core do PyBoxEditor (`core.lexico`), com as duas regras que
fazem dele uma ferramenta de revisão e não um corretor:

- **sinaliza, nunca corrige.** Palavra fora do dicionário é mostrada ao
  usuário, que lê o recorte e decide. Trocar pela palavra mais parecida
  entregaria prosa limpa e falsa (`Nimzowitsch` não está em lista nenhuma);
- **não toca em notação.** Quem separa lance de prosa é `core.notacao`, e só
  os pedaços tipados como prosa chegam ao dicionário
  (`lexico.suspeitas_da_pagina`). `Bxf6` e `exd5` nunca aparecem aqui.

A correção é por glifo: o texto novo da palavra é repartido pelos boxes dela,
e só os boxes que mudaram viram manuais. O glifo lido com duas letras (`♕f`)
pode ficar com uma (`♔`); fora disso, se o número de letras não bate com o de
glifos, o erro é de segmentação (dois glifos colados, um partido), e quem
resolve é dividir ou juntar no painel de treino, não a verificação. O espaço
digitado não é letra: é a palavra nova antes do glifo (`quebras`), a decisão
`edicao.quebrar` do modelo, e a contagem das palavras a respeita.

O português usa o pacote Hunspell do core (`pt.hunspell.gz` com `core.afixos`),
como o editor do PyBoxEditor (`core.editor.ortografia`), mais os nomes próprios
que o core empacota, porque livro de xadrez é cheio de Morphy e Capablanca. O
dicionário deste livro é o `lexico.txt` do projeto, e só o que o usuário manda
adicionar entra nele.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np

from core.box_model import BoxEntry

from abbychess.leitor import FONTE_MANUAL

Caixa = Tuple[int, int, int, int]

MOTIVOS = {
    "fora-do-dicionario": "fora do dicionário",
    "caixa-estranha": "maiúsculas no meio da palavra",
}


def caminho_do_lexico_do_idioma(idioma: str) -> Optional[str]:
    """A lista do idioma em `assets/lexico/` do PyBoxEditor, ou `None`."""
    from core import lexico

    pasta = os.path.dirname(lexico.CAMINHO_PADRAO)
    idioma = (idioma or "").split("-")[0].lower()
    for nome in (f"{idioma}.txt.gz", f"{idioma}.hunspell.gz"):
        caminho = os.path.join(pasta, nome)
        if idioma and os.path.exists(caminho):
            return caminho
    return None


def carregar_lexico(idioma: str = "pt", usuario: Optional[Path] = None,
                    extras: Iterable[Path] = ()):
    """O `core.lexico.Lexico` do idioma, com o dicionário do livro.

    `usuario` é o `lexico.txt` do projeto, que `adicionar` reescreve. `extras`
    são listas só de leitura, como o `.lexico.txt` que o PyBoxEditor guarda ao
    lado do PDF: as palavras delas valem, mas não são copiadas para o projeto.
    Um idioma sem lista dá o léxico vazio, que não sinaliza nada.
    """
    from core import lexico

    usuario_str = str(usuario) if usuario else None
    nenhum = os.path.join(os.path.dirname(lexico.CAMINHO_PADRAO), "nenhum")
    caminho = caminho_do_lexico_do_idioma(idioma)
    if caminho and caminho.endswith(".hunspell.gz"):
        from core import afixos

        flexoes = afixos.Afixos.carregar(caminho)
        lex = lexico.carregar(caminho=nenhum, caminho_usuario=usuario_str, idioma=idioma,
                              nomes=False)
        lex.palavras.update(flexoes.raizes)
        lex.flexoes = flexoes
    elif caminho:
        lex = lexico.carregar(caminho=caminho, caminho_usuario=usuario_str, idioma=idioma,
                              nomes=False)
    else:
        lex = lexico.carregar(caminho=nenhum, caminho_usuario=usuario_str, idioma=idioma,
                              nomes=False)
    if lex.palavras and os.path.exists(lexico.CAMINHO_NOMES):
        lex.palavras.update(lexico._ler(lexico.CAMINHO_NOMES))
    for extra in extras:
        if extra and Path(extra).is_file():
            lex.palavras.update(lexico._ler(str(extra)))
    return lex


@dataclass
class Desconhecida:
    """Uma palavra da página que o léxico não conhece, com os boxes dela."""

    palavra: str
    indices: List[int]
    motivo: str = "fora-do-dicionario"

    @property
    def explicacao(self) -> str:
        return MOTIVOS.get(self.motivo, self.motivo)


def desconhecidas(boxes: Sequence[BoxEntry], lex, ignoradas: Iterable[str] = (),
                  quebras: Iterable[int] = ()) -> List[Desconhecida]:
    """As palavras de prosa da página fora do léxico, na ordem de leitura.

    `ignoradas` são as do "Ignorar todas" desta sessão, comparadas sem caixa.
    `quebras` são os índices dos boxes que começam palavra por decisão do usuário
    (o espaço digitado aqui, `edicao.quebrar`): a palavra suspeita que tem um deles
    no meio é partida, e cada pedaço é perguntado ao léxico de novo.

    O glifo sem leitura no meio da palavra (o "ç" de "ameaçavam" que ninguém
    leu) entra nos índices dela: o núcleo do core só conta caracteres, e sem
    ele a palavra teria uma letra a menos que a correção a digitar. Tirar esse
    box da página antes de perguntar ao léxico seria pior: o vão que ele deixa
    parte a palavra em duas.
    """
    from core import lexico

    fora = {p.lower() for p in ignoradas}
    if not any(b.char for b in boxes):
        return []
    quebras = set(quebras)
    saida = []
    for s in _partidas(lexico.suspeitas_da_pagina(list(boxes), lex), boxes, lex, quebras):
        if s.palavra.lower() in fora or not s.indices:
            continue
        saida.append(Desconhecida(s.palavra, _com_os_vazios(boxes, s.indices), s.motivo))
    return saida


def _partidas(suspeitas, boxes: Sequence[BoxEntry], lex, quebras: set) -> list:
    """As suspeitas com as quebras do usuário aplicadas: os pedaços que o léxico conhece saem."""
    from core import lexico

    saida = []
    for s in suspeitas:
        if not quebras.intersection(s.indices[1:]):
            saida.append(s)
            continue
        pedacos = [[s.indices[0]]]
        for i in s.indices[1:]:
            if i in quebras:
                pedacos.append([])
            pedacos[-1].append(i)
        saida.extend(lexico.sinalizar([[(boxes[i].char, i) for i in p] for p in pedacos], lex))
    return saida


def _com_os_vazios(boxes: Sequence[BoxEntry], indices: Sequence[int]) -> List[int]:
    """Os índices da palavra mais os boxes sem leitura entre o primeiro e o último glifo."""
    x1, y1, x2, y2 = caixa_da_palavra(boxes, indices)
    vazios = [i for i in range(min(indices), max(indices) + 1)
              if not boxes[i].char and x1 <= (boxes[i].x1 + boxes[i].x2) / 2 <= x2
              and min(y2, boxes[i].y2) > max(y1, boxes[i].y1)]
    return sorted(set(indices) | set(vazios), key=lambda i: boxes[i].x1)


def caixa_da_palavra(boxes: Sequence[BoxEntry], indices: Sequence[int]) -> Caixa:
    escolhidos = [boxes[i] for i in indices]
    return (min(b.x1 for b in escolhidos), min(b.y1 for b in escolhidos),
            max(b.x2 for b in escolhidos), max(b.y2 for b in escolhidos))


def recorte_da_palavra(pagina: np.ndarray, boxes: Sequence[BoxEntry], indices: Sequence[int],
                       folga: Optional[int] = None) -> Tuple[np.ndarray, Tuple[int, int]]:
    """O recorte da página em volta da palavra e o canto dele (x, y) na página.

    A folga padrão é meia altura da palavra, para mostrar o vizinho de cada
    lado sem virar a linha inteira.
    """
    x1, y1, x2, y2 = caixa_da_palavra(boxes, indices)
    if folga is None:
        folga = max(4, (y2 - y1) // 2)
    altura, largura = pagina.shape[:2]
    x1, y1 = max(0, x1 - folga), max(0, y1 - folga)
    x2, y2 = min(largura, x2 + folga), min(altura, y2 + folga)
    return pagina[y1:y2, x1:x2], (x1, y1)


def repartir(boxes: Sequence[BoxEntry], indices: Sequence[int], novo: str) -> List[str]:
    """O texto novo repartido pelos glifos da palavra, um pedaço por box.

    Cada glifo fica com uma letra, ou com duas se já tinha duas (um box de
    ligadura como `fi` ou `f8`). O glifo de duas letras pode ficar com uma, nunca
    o contrário: `♔f8` sobre os glifos lidos `♕f` e `f8` dá `♔` e `f8`. Com mais
    de um jeito, vale o que muda menos glifos e, depois, menos letras; se ainda
    sobra empate, ou se não há jeito, é erro de segmentação, e o `ValueError` diz
    o que fazer. Os espaços não são letras: cada um é uma palavra nova
    (`quebras`).
    """
    return _repartir(boxes, indices, novo)[0]


def quebras(boxes: Sequence[BoxEntry], indices: Sequence[int], novo: str) -> List[int]:
    """As posições em `indices` dos glifos antes dos quais o texto novo tem espaço.

    "Next is" digitado sobre os seis glifos de "Nextis" dá `[4]`: o "i" começa
    uma palavra (o espaço que a leitura não viu, `edicao.quebrar`). O espaço que
    cai dentro de um box de ligadura é recusado, porque não há glifo onde partir.
    """
    return _repartir(boxes, indices, novo)[1]


def _repartir(boxes: Sequence[BoxEntry], indices: Sequence[int], novo: str
              ) -> Tuple[List[str], List[int]]:
    palavras = novo.split()
    letras = "".join(palavras)
    if not letras:
        raise ValueError("Digite a palavra.")
    pedacos = _pelos_glifos([boxes[i].char for i in indices], letras)
    if pedacos is None:
        raise ValueError(f"A palavra tem {len(indices)} glifo(s) e o texto novo "
                         f"{len(letras)} letra(s). Divida ou junte os glifos no painel "
                         "de treino.")
    if not pedacos:
        raise ValueError("Há mais de um jeito de pôr essas letras nos glifos. Clique no "
                         "glifo e corrija no painel de treino.")
    inicio, pos = {}, 0                   # letra em que cada glifo começa -> posição dele
    for k, pedaco in enumerate(pedacos):
        inicio.setdefault(pos, k)
        pos += len(pedaco)
    saida, pos = [], 0
    for palavra in palavras[:-1]:
        pos += len(palavra)
        if pos not in inicio:
            raise ValueError("O espaço cai dentro de um glifo de duas letras. Divida o "
                             "glifo no painel de treino.")
        saida.append(inicio[pos])
    return pedacos, saida


def _pelos_glifos(antigos: Sequence[str], letras: str) -> Optional[List[str]]:
    """As letras repartidas pelos glifos lidos `antigos` (ver `repartir`).

    Programação dinâmica por (glifos usados, letras usadas), com o custo (glifos
    mudados, letras editadas) e quantos caminhos dão esse custo. Devolve `None`
    sem jeito nenhum e `[]` quando o melhor jeito não é único.
    """
    n, m = len(antigos), len(letras)
    #: (i, j) -> (custo, caminhos, (j de antes, pedaço do glifo i - 1))
    melhor = {(0, 0): ((0, 0), 1, None)}
    for i, antigo in enumerate(antigos):
        for j in range(m):
            if (i, j) not in melhor:
                continue
            (mudados, editadas), caminhos, _ = melhor[(i, j)]
            for t in range(1, max(1, len(antigo)) + 1):
                if j + t > m:
                    break
                pedaco = letras[j:j + t]
                custo = (mudados + (pedaco != antigo), editadas + _distancia(antigo, pedaco))
                atual = melhor.get((i + 1, j + t))
                if atual is None or custo < atual[0]:
                    melhor[(i + 1, j + t)] = (custo, caminhos, (j, pedaco))
                elif custo == atual[0]:
                    melhor[(i + 1, j + t)] = (custo, atual[1] + caminhos, atual[2])
    fim = melhor.get((n, m))
    if fim is None:
        return None
    if fim[1] > 1:
        return []
    pedacos, i, j = [], n, m
    while i:
        j, pedaco = melhor[(i, j)][2]
        pedacos.append(pedaco)
        i -= 1
    return pedacos[::-1]


def _distancia(a: str, b: str) -> int:
    """A distância de edição (Levenshtein) entre dois textos curtos."""
    linha = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        anterior, linha[0] = linha[0], i
        for j, cb in enumerate(b, 1):
            anterior, linha[j] = linha[j], min(linha[j] + 1, linha[j - 1] + 1,
                                               anterior + (ca != cb))
    return linha[-1]


def corrigir(boxes: List[BoxEntry], indices: Sequence[int], novo: str) -> List[Tuple[int, str]]:
    """Grava o texto novo nos glifos da palavra e devolve os (box, letra) que mudaram.

    Só o glifo que mudou vira manual: os outros já estavam certos e continuam
    com a leitura e a origem que tinham.
    """
    mudados = []
    for i, pedaco in zip(indices, repartir(boxes, indices, novo)):
        if boxes[i].char != pedaco:
            boxes[i].char, boxes[i].source, boxes[i].confidence = pedaco, FONTE_MANUAL, 1.0
            mudados.append((i, pedaco))
    return mudados


#: Nome de jogador com iniciais: grupos de letras separados por ponto, com espaço
#: depois do ponto ou não ("L.Shamkovich", "L. Shamkovich", "J.R.Capablanca").
_COM_INICIAIS = re.compile(r"[^\W\d_]+(?:\.\s*[^\W\d_]+)+")


def formas_para_o_dicionario(texto: str) -> List[str]:
    """O que entra no dicionário do livro quando o usuário manda adicionar `texto`.

    Palavra comum entra sozinha. Nome com iniciais entra junto e sem espaço
    (`l.shamkovich`), que é como o núcleo do core lê "L.Shamkovich", e com o
    sobrenome à parte (`shamkovich`), porque em "L. Shamkovich" o espaço separa
    as palavras e o "L." sozinho é curto demais para ser perguntado.
    """
    from core import lexico

    nuc, _ = lexico.nucleo(texto.strip())
    if not _COM_INICIAIS.fullmatch(nuc):
        return [nuc]
    junto = re.sub(r"\s+", "", nuc)
    return [junto] + [p for p in junto.split(".") if len(p) >= lexico.MIN_PARTE]


def adicionar(lex, palavra: str, arquivo: Path) -> bool:
    """Põe a palavra no dicionário do livro e regrava o `lexico.txt`. Devolve se era nova.

    O formato é o de `core.lexico.salvar_do_usuario` (minúsculas, ordenadas, uma por
    linha), mas gravado por `abbychess.gravacao`, com `fsync` e novas tentativas.
    O nome com iniciais entra com o ponto (`formas_para_o_dicionario`), que o
    `acrescentar` do core recusa por não ser só letras; `conhece` o acha do mesmo jeito.
    """
    from abbychess import gravacao as gv

    nova = False
    for forma in formas_para_o_dicionario(palavra):
        if "." in forma:
            nova = forma.lower() not in lex.do_usuario or nova
            lex.do_usuario.add(forma.lower())
        else:
            nova = lex.acrescentar(forma) or nova
    if not nova:
        return False
    lista = sorted({p.strip().lower() for p in lex.do_usuario if p.strip()})
    gv.gravar_texto(arquivo, "\n".join(lista) + ("\n" if lista else ""))
    return True
