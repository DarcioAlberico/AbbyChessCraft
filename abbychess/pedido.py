"""O pedido de uma exportação (§12.1): as opções do diálogo, as páginas que entram e o idioma do
livro, resolvidos uma vez para todos os formatos (SPEC-qualidade Q-E6). À parte de
`exportar.py` (CA-Q-A1)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Callable, Iterable, List, Optional, Tuple

from abbychess import idioma as idm
from abbychess import links_de_analise
from abbychess.projeto import ProjetoDeLivro


#: O idioma do arquivo exportado (`dc:language`, `xml:lang`) pelo do livro.
IDIOMAS_DO_ARQUIVO = {"pt": "pt-BR", "en": "en", "es": "es", "de": "de", "fr": "fr"}


Progresso = Callable[[int, int], None]


class NadaParaExportar(ValueError):
    """Nenhuma das páginas pedidas foi reconhecida."""


@dataclass(frozen=True)
class Opcoes:
    """As opções da exportação (§12.1). O padrão é o livro limpo: sem margens corridas,
    o texto refluído, os diagramas confiáveis desenhados."""

    #: Cabeçalhos, rodapés e números de página ficam no texto.
    manter_margens: bool = False
    #: Só as páginas verificadas (§4.4).
    so_verificadas: bool = False
    #: Os diagramas confiáveis redesenhados do FEN; falso, todos como recorte da página.
    desenhar_diagramas: bool = True
    #: No TXT, uma marca `[p. N]` no começo de cada página.
    marcas_de_pagina: bool = False
    #: As quebras de linha e os hífens do impresso ficam: cada linha impressa acaba numa
    #: quebra dentro do parágrafo (`\n` no texto; `<br/>` no EPUB, `w:br` no DOCX). Nas
    #: páginas do OCR, o parágrafo que a página partiu não se junta com o da seguinte; na
    #: camada nativa o core já o juntou ao ler, e ele fica junto, com a quebra no lugar.
    manter_quebras: bool = False
    #: No DOCX, os glifos de baixa confiança (os que a fila de revisão pede, §8) com o
    #: realce amarelo do Word, para quem revisa no editor de texto achar onde olhar.
    realcar_duvidosos: bool = False
    #: No EPUB, no DOCX e na prévia, o link que abre cada diagrama lido no tabuleiro de
    #: análise: `nenhum`, `lichess` ou `chesscom` (`links_de_analise.SITES`).
    links_de_analise: str = "nenhum"
    #: As páginas `(primeira, última)`, índices a partir de 0, as duas incluídas; `None`, o
    #: livro todo. Não é lembrada entre exportações.
    intervalo: Optional[Tuple[int, int]] = None
    #: As páginas escolhidas na gaveta, em índices (§3.1), que um intervalo não diz quando são
    #: salteadas; vazia, todas. Também não é lembrada.
    selecao: Tuple[int, ...] = ()

    def __post_init__(self) -> None:
        links_de_analise.validar(self.links_de_analise)
        if self.intervalo is not None:
            primeira, ultima = self.intervalo
            if not 0 <= primeira <= ultima:
                raise ValueError(f"intervalo inválido: {self.intervalo!r}")

    def indices(self, indices: Optional[Iterable[int]]) -> Optional[Iterable[int]]:
        """Os `indices` pedidos, cortados pelo `intervalo` e pela `selecao`."""
        if self.selecao:
            indices = self.selecao if indices is None else [i for i in indices if i in self.selecao]
        if self.intervalo is None:
            return indices
        dentro = range(self.intervalo[0], self.intervalo[1] + 1)
        return dentro if indices is None else [i for i in indices if i in dentro]


@dataclass(frozen=True)
class Pedido:
    """Uma exportação resolvida uma vez (SPEC-qualidade Q-E6): o projeto, as opções e os
    `indices` pedidos. Os formatos e as páginas leem daqui o que antes perguntavam cada um
    ao projeto: o idioma do livro pela camada do PDF, que abre o livro, sai uma vez só."""

    projeto: ProjetoDeLivro
    opcoes: Opcoes
    indices: Optional[Iterable[int]] = None

    @classmethod
    def de(cls, projeto: ProjetoDeLivro, indices: Optional[Iterable[int]] = None,
           opcoes: Optional[Opcoes] = None) -> "Pedido":
        """O pedido do diálogo: os `indices` cortados pelo `intervalo` das `opcoes`."""
        opcoes = opcoes or Opcoes()
        return cls(projeto, opcoes, opcoes.indices(indices))

    @cached_property
    def idioma(self) -> str:
        """O idioma do livro (`idioma_do_livro`), pedido na primeira vez que alguém o lê."""
        return idioma_do_livro(self.projeto)

    @property
    def idioma_do_arquivo(self) -> str:
        return idioma_do_arquivo(self.idioma)

    def alvo(self) -> List[int]:
        return _alvo(self.projeto, self.indices, self.opcoes)


def _alvo(projeto: ProjetoDeLivro, indices: Optional[Iterable[int]],
          opcoes: Optional[Opcoes]) -> List[int]:
    """As páginas que a exportação leva, em todo formato (SPEC-qualidade Q-E2): as
    reconhecidas de `indices` (ou todas) e, com `so_verificadas`, só as verificadas.
    Nenhuma: `NadaParaExportar`."""
    from abbychess.modelo import VERIFICADA

    lidas = set(projeto.resumo.paginas_lidas())
    alvo = sorted(lidas if indices is None else lidas.intersection(indices))
    so_verificadas = opcoes is not None and opcoes.so_verificadas
    if so_verificadas:
        estados = {i: r.get("estado") for i, r in projeto.resumo.do_livro().items()}
        alvo = [i for i in alvo if estados.get(i) == VERIFICADA]
    if not alvo:
        raise NadaParaExportar("Nenhuma página verificada para exportar." if so_verificadas
                               else "Nenhuma página reconhecida para exportar.")
    return alvo


def idioma_do_livro(projeto: ProjetoDeLivro) -> str:
    """
    O idioma do texto do livro: o que a camada de texto do PDF diz, ou o do projeto.

    O projeto nasce com "pt" quando ninguém escolhe, e o Odds & Ends, em inglês,
    saía com `dc:language` `pt-BR`. A camada responde pelas palavras comuns dela
    (`idioma.da_camada_do_pdf`); sem camada (a digitalização), vale o do projeto.
    """
    if projeto.origem.e_pdf:
        lido = idm.da_camada_do_pdf(projeto.fonte)
        if lido:
            return lido
    return projeto.dados.idioma or "pt"


def idioma_do_arquivo(idioma: str) -> str:
    """A etiqueta BCP 47 do arquivo exportado: `pt` é `pt-BR`, o resto como está."""
    return IDIOMAS_DO_ARQUIVO.get(idioma, idioma or "pt-BR")
