"""O livro inteiro: reconhecer em lote e revisar de página em página.

No FineReader, depois de treinar os padrões em algumas páginas, o livro é lido
de uma vez e a revisão anda pelo documento todo, não por página. Aqui é igual:

- `reconhecer_paginas` lê um intervalo de páginas com os padrões do livro e
  grava cada uma no projeto assim que termina, para um cancelamento ou uma
  falha no meio não perder o que já foi lido. Página já lida só é lida de novo
  com `refazer`: a decisão é de quem chama, que pergunta ao usuário. A verificada
  é pulada sempre (CA-8.5), e a relida mantém os glifos `manual` e `revisado`
  (§4.6). É o lote da janela (`lote.CondutorDoLote`) rodado de uma vez, para as
  ferramentas e os testes.
- `proxima_com_pendentes` acha a próxima página gravada que ainda tem glifo
  para revisar, dando a volta no livro.

Sem Qt.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional

from core.box_model import BoxEntry

from abbychess import pagina as pg
from abbychess import servidor_de_leitura as sl
from abbychess.leitor import LeitorDoLivro, precisa_revisao
from abbychess.lote import ResultadoDoLote  # noqa: F401 (o resultado do lote mora lá)
from abbychess.projeto import Limiares, ProjetoDeLivro

log = logging.getLogger(__name__)

#: `progresso(feitas, total)` em páginas, e `ao_gravar(indice, resumo)` a cada
#: página gravada.
Progresso = Callable[[int, int], None]


#: O usuário cancelou o lote; as páginas já gravadas ficam (a do servidor e a daqui são a
#: mesma: o cancelamento chega pela leitura).
Cancelado = sl.Cancelado

CHAVE_DA_AMOSTRA = "paginas_da_amostra_guiada"
CHAVE_DOS_CANDIDATOS_DA_AMOSTRA = "candidatos_da_amostra_guiada"
CHAVE_DOS_PENDENTES_INICIAIS = "pendentes_iniciais_da_amostra"
CHAVE_DO_LIMIAR_DA_SAUDE = "limiar_de_pendentes_da_amostra"


@dataclass(frozen=True)
class SaudeDoLivro:
    paginas: tuple[int, ...]
    pendentes_antes: int
    pendentes_agora: int
    padroes: int
    limiar: int

    @property
    def pode_reconhecer_o_livro(self) -> bool:
        return bool(self.paginas) and self.pendentes_agora <= self.limiar


def saude(projeto: ProjetoDeLivro, padroes: int = 0) -> SaudeDoLivro:
    """O cartão Saúde derivado do projeto; não abre páginas, só lê ``livro.json``."""
    extras = projeto.dados.extras
    # Gravadas por `pid` (§12.4): `paginas` é a posição de agora de cada uma; os pendentes
    # iniciais são chaveados pelo valor gravado.
    gravadas = [g for g in extras.get(CHAVE_DA_AMOSTRA, ())
                if projeto.posicoes_das_gravadas([g])]
    paginas = tuple(projeto.posicoes_das_gravadas(gravadas))
    iniciais = extras.get(CHAVE_DOS_PENDENTES_INICIAIS, {}) or {}
    resumo = projeto.resumo_do_livro()
    antes = sum(int(iniciais.get(str(g), iniciais.get(g, 0)) or 0) for g in gravadas)
    agora = sum(int(resumo.get(i, {}).get("pendentes", 0) or 0) for i in paginas)
    limiar = int(extras.get(CHAVE_DO_LIMIAR_DA_SAUDE, max(3, round(antes * 0.1))) or 0)
    return SaudeDoLivro(paginas, antes, agora, int(padroes), limiar)


def interpretar_intervalo(texto: str, total: int) -> List[int]:
    """As páginas de "26-27, 30" como índices de zero, em ordem e sem repetir.

    Os números são os da página como o usuário os vê (de 1 a `total`). Vazio é
    o livro inteiro. Um intervalo aberto ("40-") vai até o fim.
    """
    texto = texto.strip()
    if not texto:
        return list(range(total))
    paginas = set()
    for parte in re.split(r"[,;\s]+", texto):
        if not parte:
            continue
        casou = re.fullmatch(r"(\d+)?\s*[-–]\s*(\d+)?|(\d+)", parte)
        if not casou:
            raise ValueError(f"Não entendi '{parte}'. Use, por exemplo, 26-27, 30.")
        if casou.group(3):
            inicio = fim = int(casou.group(3))
        else:
            inicio = int(casou.group(1) or 1)
            fim = int(casou.group(2) or total)
        if inicio > fim:
            inicio, fim = fim, inicio
        if inicio < 1 or fim > total:
            raise ValueError(f"As páginas vão de 1 a {total}; '{parte}' sai disso.")
        paginas.update(range(inicio - 1, fim))
    return sorted(paginas)


def paginas_da_amostra(indices: Iterable[int]) -> List[int]:
    """Três páginas representativas de um intervalo: 10%, 50% e 90%.

    `indices` são índices do PDF, já sem capa e sumário. Num intervalo de até
    três páginas, todas entram. O mesmo índice nunca entra duas vezes.
    """
    paginas = sorted(set(indices))
    if len(paginas) <= 3:
        return paginas
    ultima = len(paginas) - 1
    return [paginas[round(ultima * fracao)] for fracao in (0.1, 0.5, 0.9)]


def ja_lidas(projeto: ProjetoDeLivro, indices: Iterable[int]) -> List[int]:
    """Quais destas páginas já têm boxes gravados no projeto."""
    lidas = set(projeto.paginas_lidas())
    return [i for i in indices if i in lidas]


def reconhecer_paginas(projeto: ProjetoDeLivro, fonte: pg.FonteDePaginas,
                       leitor: LeitorDoLivro, indices: Iterable[int], *,
                       refazer: bool = False,
                       progresso: Optional[Progresso] = None,
                       cancelado: Callable[[], bool] = lambda: False,
                       ao_gravar: Optional[Callable[[int, pg.ResumoDaLeitura], None]] = None
                       ) -> ResultadoDoLote:
    """Segmenta, lê e grava cada página do intervalo, uma de cada vez, e espera a gravação.

    É o lote da janela (`lote.CondutorDoLote`, as mesmas regras: a verificada pulada, a
    já lida só com `refazer`, o §4.6, a cópia de antes do lote) com um controlador sem
    janela e o executor síncrono, lendo com `leitor` aqui mesmo. Os padrões do livro valem
    do jeito que estão: o lote não ensina nada. A página só é gravada inteira; se o
    cancelamento chega no meio dela, ela fica como estava antes do lote. Uma página que
    falha (não renderiza, por exemplo) vai para `falhas` e o lote segue.
    """
    from abbychess.controlador import ControladorDePagina
    from abbychess.lote import CondutorDoLote

    controlador = ControladorDePagina()
    controlador.ligar(projeto, fonte, leitor)
    fim: list = []

    def gravou(indice: int) -> None:
        if ao_gravar is not None:
            pagina = projeto.carregar_modelo(indice)
            resumo = pg.resumir(pagina.entries(), leitor)
            resumo.diagramas = sum(d.lido for d in pagina.diagramas)
            ao_gravar(indice, resumo)

    condutor = CondutorDoLote(
        controlador, list(indices), refazer, cancelado=cancelado, ao_gravar=gravou,
        ao_progresso=(lambda feitas, total, _estimativa: progresso(feitas, total))
        if progresso else None, ao_fim=fim.append)
    condutor.comecar()
    if not projeto.descarregar(60):
        log.warning("o lote leu, mas o gravador não gravou tudo: %s", projeto.paginas_sujas())
    return fim[0] if fim else condutor.resultado


# ----------------------------------------------------------------------
# A revisão do livro todo
# ----------------------------------------------------------------------

def pendentes_da_pagina(boxes: List[BoxEntry], limiares: Limiares) -> int:
    return sum(1 for b in boxes if precisa_revisao(b.char, b.source, b.confidence, limiares))


def pendentes_por_pagina(projeto: ProjetoDeLivro, limiares: Limiares) -> Dict[int, int]:
    """Quantos glifos faltam revisar em cada página gravada, só as que têm algum: pelo
    resumo de cada página no `livro.json` (o histograma das confianças dá os pendentes de
    qualquer limiar), sem abrir as páginas (§8.1, CA-8.3)."""
    from abbychess.projeto import pendentes_pelo_histograma

    contagem = {}
    for indice, resumo in projeto.resumo_do_livro().items():
        try:
            n = pendentes_pelo_histograma(resumo, limiares.revisao)
        except (KeyError, TypeError, ValueError):   # um resumo antigo, sem o histograma
            n = int(resumo.get("pendentes", 0) or 0)
        if n:
            contagem[indice] = n
    return contagem


def anterior_com_pendentes(projeto: ProjetoDeLivro, limiares: Limiares, antes_de: int
                           ) -> Optional[int]:
    """A página gravada com glifo a revisar antes de `antes_de` (dá a volta no livro)."""
    pendentes = sorted(pendentes_por_pagina(projeto, limiares))
    if not pendentes:
        return None
    ordem = ([i for i in reversed(pendentes) if i < antes_de]
             + [i for i in reversed(pendentes) if i > antes_de]
             + ([antes_de] if antes_de in pendentes else []))
    return ordem[0]


def proxima_com_pendentes(projeto: ProjetoDeLivro, limiares: Limiares, depois_de: int
                          ) -> Optional[int]:
    """A próxima página gravada com glifo a revisar, depois de `depois_de`.

    Dá a volta no livro: no fim, volta ao começo. A própria `depois_de` só
    entra por último, quando é a única que sobrou; quem chama já olhou a fila
    dela na memória, que pode estar mais nova do que o arquivo.
    """
    pendentes = pendentes_por_pagina(projeto, limiares)
    if not pendentes:
        return None
    depois = [i for i in sorted(pendentes) if i > depois_de]
    antes = [i for i in sorted(pendentes) if i < depois_de]
    ordem = depois + antes + ([depois_de] if depois_de in pendentes else [])
    return ordem[0]
