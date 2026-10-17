"""O livro inteiro: reconhecer em lote e revisar de página em página.

No FineReader, depois de treinar os padrões em algumas páginas, o livro é lido
de uma vez e a revisão anda pelo documento todo, não por página. Aqui é igual:

- `reconhecer_paginas` lê um intervalo de páginas com os padrões do livro e
  grava cada uma no projeto assim que termina, para um cancelamento ou uma
  falha no meio não perder o que já foi lido. Página já lida só é lida de novo
  com `refazer`: a decisão é de quem chama, que pergunta ao usuário. A verificada
  é pulada sempre (CA-8.5), e a relida mantém os glifos `manual` e `revisado`
  (§4.6). É o caminho síncrono, das ferramentas e dos testes; a janela lê o lote
  pelo `lote.CondutorDoLote`, que grava na thread da interface.
- `proxima_com_pendentes` acha a próxima página gravada que ainda tem glifo
  para revisar, dando a volta no livro.

Sem Qt.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional

from core.box_model import BoxEntry

from abbychess import diagramas as dg
from abbychess import pagina as pg
from abbychess import servidor_de_leitura as sl
from abbychess.leitor import LeitorDoLivro, precisa_revisao
from abbychess.modelo import LIDAS, VERIFICADA
from abbychess.projeto import Limiares, ProjetoDeLivro

log = logging.getLogger(__name__)

#: `progresso(feitas, total)` em páginas, e `ao_gravar(indice, resumo)` a cada
#: página gravada.
Progresso = Callable[[int, int], None]


#: O usuário cancelou o lote; as páginas já gravadas ficam (a do servidor e a daqui são a
#: mesma: o cancelamento chega pela leitura).
Cancelado = sl.Cancelado


@dataclass
class ResultadoDoLote:
    #: As páginas lidas e gravadas neste lote, em ordem.
    lidas: List[int] = field(default_factory=list)
    #: As que já estavam lidas e ficaram como estavam.
    puladas: List[int] = field(default_factory=list)
    #: As verificadas, puladas mesmo com "refazer" (CA-8.5).
    verificadas: List[int] = field(default_factory=list)
    #: As abertas e com mudança na janela, que o lote não sobrescreveu (CA-11.4).
    reler_depois: List[int] = field(default_factory=list)
    #: Página -> motivo, para a que não abriu ou não segmentou.
    falhas: Dict[int, str] = field(default_factory=dict)
    #: Página -> quantos glifos ficaram para revisar.
    pendentes: Dict[int, int] = field(default_factory=dict)
    #: Página -> quantos diagramas foram lidos em FEN.
    diagramas: Dict[int, int] = field(default_factory=dict)
    cancelado: bool = False

    @property
    def total_de_pendentes(self) -> int:
        return sum(self.pendentes.values())


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
    """Segmenta, lê e grava cada página do intervalo, uma de cada vez.

    Os padrões do livro valem do jeito que estão: o lote não ensina nada. A
    página só é gravada inteira; se o cancelamento chega no meio dela, ela fica
    como estava antes do lote. Uma página que falha (não renderiza, por
    exemplo) vai para `falhas` e o lote segue.
    """
    indices = list(indices)
    resultado = ResultadoDoLote()
    total = len(indices)
    if progresso:
        progresso(0, total)
    for feitas, indice in enumerate(indices, start=1):
        if cancelado():
            resultado.cancelado = True
            break
        estado = projeto.estado_da_pagina(indice)
        if estado == VERIFICADA:
            resultado.verificadas.append(indice)
        elif estado in LIDAS and not refazer:
            resultado.puladas.append(indice)
        else:
            try:
                resumo = _reconhecer_uma(projeto, fonte, leitor, indice, cancelado)
            except Cancelado:
                resultado.cancelado = True
                break
            except (OSError, ValueError, IndexError) as erro:
                log.warning("a página %d não foi reconhecida: %s", indice + 1, erro)
                resultado.falhas[indice] = str(erro)
            else:
                resultado.lidas.append(indice)
                resultado.pendentes[indice] = resumo.pendentes
                resultado.diagramas[indice] = resumo.diagramas
                if ao_gravar:
                    ao_gravar(indice, resumo)
        if progresso:
            progresso(feitas, total)
    return resultado


def _reconhecer_uma(projeto, fonte, leitor, indice, cancelado) -> pg.ResumoDaLeitura:
    """Uma página do lote, com os diagramas lidos em FEN como no F5 da janela.

    A conferência feita antes vale mais que a releitura (`diagramas.mesclar`):
    refazer o livro não desfaz o tabuleiro corrigido à mão.
    """
    imagem = fonte.pagina(indice)
    modelo = projeto.carregar_modelo(indice)
    # Com áreas gravadas (editor de áreas), só o texto delas vira box; e ficam os glifos
    # marcados à mão da página ainda não lida, ou os manuais e revisados da já lida (§4.6).
    marcados = (pg.a_manter_na_releitura(modelo.boxes, modelo.estado in LIDAS)
                if modelo is not None else [])
    lida = sl.ler_pagina(imagem, projeto.carregar_zonas(indice), marcados, leitor,
                         cancelado=cancelado)
    if cancelado():
        raise Cancelado
    diagramas = dg.mesclar(lida.diagramas, projeto.carregar_diagramas(indice))
    projeto.salvar_pagina(indice, lida.boxes, lida.tabuleiros, diagramas, reconheceu=True)
    resumo = pg.resumir(lida.boxes, leitor)
    resumo.diagramas = sum(d.lido for d in diagramas)
    return resumo


# ----------------------------------------------------------------------
# A revisão do livro todo
# ----------------------------------------------------------------------

def pendentes_da_pagina(boxes: List[BoxEntry], limiares: Limiares) -> int:
    return sum(1 for b in boxes if precisa_revisao(b.char, b.source, b.confidence, limiares))


def pendentes_por_pagina(projeto: ProjetoDeLivro, limiares: Limiares) -> Dict[int, int]:
    """Quantos glifos faltam revisar em cada página gravada, só as que têm algum."""
    contagem = {}
    for indice in projeto.paginas_lidas():
        try:
            boxes = projeto.carregar_pagina(indice) or []
        except (OSError, ValueError, json.JSONDecodeError) as erro:
            log.warning("a página %d gravada não abriu: %s", indice + 1, erro)
            continue
        n = pendentes_da_pagina(boxes, limiares)
        if n:
            contagem[indice] = n
    return contagem


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
