"""O `projeto.json` como dados (§4.3), à parte do `ProjetoDeLivro` (SPEC-qualidade Q-A1): a
notação das peças (`Notacao`), os limiares da leitura (`Limiares`), os campos do arquivo
(`Projeto`) e o que a entrada confere antes de montá-los (`TIPOS_DO_PROJETO`,
`TIPOS_DOS_LIMIARES`, `VALORES_DO_PROJETO`, `_conferir_tipos`, `_conferir_valores`,
`_separar`, SPEC-qualidade Q-P6). Ler e gravar o arquivo é do projeto."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import StrEnum
from typing import Dict, Tuple

from abbychess.pasta_do_projeto import VERSAO


class Notacao(StrEnum):
    """Como o livro escreve as peças nos lances (`Projeto.notacao`, §6.4); a entrada do
    `projeto.json` recusa o resto (SPEC-qualidade Q-P9)."""

    LIVRO = "livro"
    FIGURINAS = "figurinas"
    LETRAS = "letras"


@dataclass
class Limiares:
    """Quando cada elo da leitura é aceito, e quando o box vai para a revisão.

    As confianças seguem as escalas do PyBoxEditor. A do k-NN é `1 - d/2000`
    (`core.learner.DISTANCIA_MAXIMA`).
    A rede usa 0,80, o `NEURAL_THRESHOLD` da janela do PyBoxEditor, e a base
    global 0,30, o `LEARNER_THRESHOLD_NEURAL`.

    O do livro é 0,25, distância 1.500, e não os 0,50 da faixa da base global:
    num livro digitalizado as repetições da mesma letra ficam entre 900 e 1.400
    de distância umas das outras, e 0,50 deixava metade delas de fora. A tabela
    está em `abbychess.padroes`; a trava de altura de lá é o que impede o
    limiar mais largo de trocar `o` por `O`.
    """

    livro: float = 0.25
    rede: float = 0.80
    base: float = 0.30
    revisao: float = 0.90
    #: A margem do aviso de conflito ao ensinar (§8.3), na escala das distâncias do k-NN
    #: do livro (`distância / 2000`): o glifo mais perto que isto de amostras de outro
    #: caractere é avisado.
    conflito: float = 0.10


@dataclass
class Projeto:
    """O `projeto.json` sem a sequência do livro e o próximo `pid`, que são da
    `SequenciaDoLivro` (`ProjetoDeLivro.ordem`, SPEC-qualidade Q-P9): a abertura os
    entrega a ela, e `salvar` os grava montados dela."""

    nome: str
    fonte: str
    criado: str
    limiares: Limiares = field(default_factory=Limiares)
    #: O idioma da prosa, que escolhe o léxico da verificação de texto e as letras das
    #: peças nos lances (pt: R D T B C; en: K Q R B N).
    idioma: str = "pt"
    #: Como o livro escreve as peças nos lances: "figurinas" (♘f3), "letras" (Cf3) ou
    #: "livro" (como o livro: figurinas se ele tem figurinas lidas). No modo figurinas, a
    #: letra digitada num lance vira figurina ao confirmar (§6.4).
    notacao: str = "livro"
    versao: int = VERSAO
    #: O SHA-256 dos primeiros 4 MB da fonte e o tamanho dela, que a reconhecem se ela for
    #: movida (o tamanho separa dois arquivos de começo igual e evita ler os outros).
    fonte_sha256: str = ""
    fonte_tamanho: int = 0
    #: Os campos de `projeto.json` que esta versão não conhece. Não se perdem: ficam aqui
    #: e são regravados em `extras` (os de `limiares` em `extras["limiares"]`), onde uma
    #: versão futura que os entenda vai buscá-los.
    extras: Dict[str, object] = field(default_factory=dict)
    #: Endireitar cada página antes de ler (`pagina.medir_inclinacao`). Projeto
    #: novo nasce com isto; o que foi criado antes fica sem, porque os boxes
    #: gravados dele estão nas coordenadas da página torta.
    endireitar: bool = False
    #: Os glifos que mudaram de página ao dividi-la (§12.4): gid velho -> gid novo (as chaves
    #: em texto, como no JSON). A amostra ensinada antes acha o glifo de origem por aqui.
    gids_movidos: Dict[str, int] = field(default_factory=dict)
    #: O maior `len(fields(BoxEntry))` que já gravou aqui (D-1): mais que o deste core, as
    #: páginas não se leem, e o projeto abre só para leitura, sem abrir nenhuma delas.
    campos_do_box: int = 0
    #: As letras das peças nos lances, na ordem rei, dama, torre, bispo, cavalo; vazio são as do
    #: idioma. Um livro em português com notação inglesa (`Rf1` é torre) precisa disto.
    letras_das_pecas: str = ""

    @property
    def chave_das_pecas(self) -> str:
        """O que `lances` e `sessao` recebem para saber as letras: elas, ou o idioma."""
        return self.letras_das_pecas or self.idioma


_NADA = type(None)
#: O tipo de cada campo conhecido do `projeto.json` e dos limiares (SPEC-qualidade Q-P6): a
#: entrada confere todos antes de montar o `Projeto` e antes de gravar qualquer coisa.
TIPOS_DO_PROJETO = {
    "nome": str, "fonte": str, "criado": str, "limiares": (dict, _NADA), "idioma": str,
    "notacao": str, "versao": int, "fonte_sha256": str, "fonte_tamanho": int,
    "proximo_pid": int, "extras": (dict, _NADA), "endireitar": bool, "sequencia": (dict, _NADA),
    "gids_movidos": dict, "campos_do_box": int, "letras_das_pecas": str,
}
TIPOS_DOS_LIMIARES = {f.name: (int, float) for f in fields(Limiares)}
#: Os campos de texto que só aceitam alguns valores.
VALORES_DO_PROJETO = {"notacao": tuple(Notacao)}
_NOMES_DOS_TIPOS = {str: "texto", int: "inteiro", float: "número", bool: "sim ou não",
                    dict: "objeto"}


def _conferir_tipos(valores: dict, tipos: dict, prefixo: str = "") -> None:
    """`ValueError` com o nome do primeiro campo de `valores` que não é do tipo de `tipos`
    (os que `tipos` não conhece passam: vão para `extras`). Um booleano não vale por número."""
    for nome, valor in valores.items():
        tipo = tipos.get(nome)
        if tipo is None:
            continue
        aceitos = tipo if isinstance(tipo, tuple) else (tipo,)
        if not isinstance(valor, aceitos) or (isinstance(valor, bool) and bool not in aceitos):
            esperado = " ou ".join(_NOMES_DOS_TIPOS[t] for t in aceitos if t is not _NADA)
            raise ValueError(f"o campo {prefixo}{nome} devia ser {esperado}, e é {valor!r}")


def _conferir_valores(valores: dict) -> None:
    """`ValueError` com o nome do campo de texto que só aceita alguns valores e tem outro."""
    for nome, aceitos in VALORES_DO_PROJETO.items():
        if nome in valores and valores[nome] not in set(aceitos):
            raise ValueError(f"o campo {nome} devia ser {', '.join(aceitos)}, e é "
                             f"{valores[nome]!r}")


def _separar(bruto: dict, classe) -> Tuple[dict, dict]:
    """Os campos que `classe` conhece e os outros."""
    nomes = {f.name for f in fields(classe)}
    return ({k: v for k, v in bruto.items() if k in nomes},
            {k: v for k, v in bruto.items() if k not in nomes})
