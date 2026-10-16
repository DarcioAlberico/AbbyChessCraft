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
e só os boxes que mudaram viram manuais. Se o número de letras não bate com o
de glifos, o erro é de segmentação (dois glifos colados, um partido), e quem
resolve é dividir ou juntar no painel de treino, não a verificação.

O português usa o pacote Hunspell do core (`pt.hunspell.gz` com `core.afixos`),
como o editor do PyBoxEditor (`core.editor.ortografia`), mais os nomes próprios
que o core empacota, porque livro de xadrez é cheio de Morphy e Capablanca. O
dicionário deste livro é o `lexico.txt` do projeto, e só o que o usuário manda
adicionar entra nele.
"""

from __future__ import annotations

import os
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


def desconhecidas(boxes: Sequence[BoxEntry], lex, ignoradas: Iterable[str] = ()
                  ) -> List[Desconhecida]:
    """As palavras de prosa da página fora do léxico, na ordem de leitura.

    `ignoradas` são as do "Ignorar todas" desta sessão, comparadas sem caixa.

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
    saida = []
    for s in lexico.suspeitas_da_pagina(list(boxes), lex):
        if s.palavra.lower() in fora or not s.indices:
            continue
        saida.append(Desconhecida(s.palavra, _com_os_vazios(boxes, s.indices), s.motivo))
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

    Com tantas letras quanto glifos, uma por glifo. Senão, se o texto antigo
    tinha o mesmo comprimento do novo (um box de ligadura como `fi` conta duas),
    cada box fica com o mesmo número de letras de antes. Fora disso é erro de
    segmentação, e o `ValueError` diz o que fazer.
    """
    novo = novo.strip()
    if not novo or any(c.isspace() for c in novo):
        raise ValueError("Digite a palavra sem espaços. Para separar ou juntar glifos, "
                         "use Dividir e Juntar no painel de treino.")
    if len(novo) == len(indices):
        return list(novo)
    tamanhos = [len(boxes[i].char) for i in indices]
    if sum(tamanhos) == len(novo):
        pedacos, pos = [], 0
        for t in tamanhos:
            pedacos.append(novo[pos:pos + t])
            pos += t
        return pedacos
    raise ValueError(f"A palavra tem {len(indices)} glifo(s) e o texto novo {len(novo)} "
                     "letra(s). Divida ou junte os glifos no painel de treino.")


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


def adicionar(lex, palavra: str, arquivo: Path) -> bool:
    """Põe a palavra no dicionário do livro e regrava o `lexico.txt`. Devolve se era nova."""
    from core import lexico

    if not lex.acrescentar(palavra):
        return False
    lexico.salvar_do_usuario(str(arquivo), lex.do_usuario)
    return True
