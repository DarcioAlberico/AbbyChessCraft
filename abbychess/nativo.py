"""Texto tipográfico de PDFs nascidos digitais, sem passar pelo OCR.

Este módulo é a seam entre a extração pública de ``core.pdf_nativo`` e o modelo do
AbbyChessCraft. Quem chama só precisa perguntar se há uma oferta e, se o usuário aceitar,
importar: avaliação, extração, geometria aproximada e persistência ficam escondidas aqui.

A camada nativa não tem boxes físicos por caractere. Para continuar usando um único modelo
e um único ``Documento``, cada palavra vira um ``Box`` confirmado na linha de onde veio. A
caixa horizontal é proporcional à posição da palavra; a vertical vem de ``topo``/``pe`` do
parágrafo. Ela serve à navegação e ao realce, mas não é amostra de treino.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

from core.box_model import BoxEntry

from abbychess import sequencia as sq
from abbychess.leitor import FONTE_NATIVA
from abbychess.modelo import Box, Estilo, Pagina, RECONHECIDA
from abbychess.projeto import ProjetoDeLivro

CHAVE_DAS_PAGINAS = "paginas_da_camada_nativa"


@dataclass(frozen=True)
class Oferta:
    aceitas: int
    amostradas: int

    @property
    def disponivel(self) -> bool:
        return self.aceitas > 0


@dataclass(frozen=True)
class Resultado:
    importadas: tuple[int, ...]
    recusadas: tuple[int, ...]


def oferta(caminho: str | Path, *, paginas: int = 12) -> Oferta:
    """A oferta para um PDF, pela régua conservadora do core."""
    caminho = Path(caminho)
    if caminho.suffix.lower() != ".pdf":
        return Oferta(0, 0)
    from core import pdf_nativo

    aceitas, amostradas = pdf_nativo.amostrar(str(caminho), paginas=paginas)
    return Oferta(aceitas, amostradas)


def importar(projeto: ProjetoDeLivro, indices: Optional[Sequence[int]] = None, *,
             idioma: Optional[str] = None, progresso=None) -> Resultado:
    """Cria no projeto as páginas cuja camada o core aceita, sem chamar leitor ou servidor.
    `indices` são posições do livro; a camada vale só na página do livro intacta (sem
    quadro, giro nem ângulo à mão, §12.4), e é pedida pela página do PDF dela."""
    from core import pdf_nativo

    sequencia = projeto.sequencia
    posicoes = range(len(sequencia)) if indices is None else indices
    importadas, recusadas = [], []
    # Em trechos seguidos no livro e no PDF (`sequencia.trechos_do_pdf`): o core junta o
    # parágrafo de uma página com o da seguinte do pedido.
    for trecho in sq.trechos_do_pdf(sequencia, posicoes):
        do_pdf = dict(trecho)                   # página do PDF -> posição no livro
        extracao = pdf_nativo.extrair(str(projeto.fonte), sorted(do_pdf), idioma=idioma,
                                      progress_callback=progresso)
        for extraida in extracao.paginas:
            posicao = do_pdf.get(extraida.numero)
            if posicao is None:
                continue
            pagina = projeto.pagina_para_editar(posicao)
            pagina.boxes = _boxes(pagina, extraida)
            pagina.estado = RECONHECIDA
            projeto.salvar_modelo(pagina)
            importadas.append(posicao)
        recusadas += [do_pdf[v.numero] for v in extracao.recusadas if v.numero in do_pdf]
    importadas.sort()
    recusadas.sort()
    projeto.dados.extras[CHAVE_DAS_PAGINAS] = sorted(set(
        projeto.dados.extras.get(CHAVE_DAS_PAGINAS, ())) | set(importadas))
    projeto.salvar()
    return Resultado(tuple(importadas), tuple(recusadas))


def _boxes(pagina: Pagina, extraida) -> list[Box]:
    from core.pagina import Paragrafo, Tabela

    saida = []
    linha_global = 0
    for bloco in extraida.blocos:
        if isinstance(bloco, Paragrafo):
            linhas = _linhas(bloco.texto, bloco.inicios)
            topo = bloco.topo if bloco.topo is not None else 30 + linha_global * 36
            pe = bloco.pe if bloco.pe is not None else topo + max(1, len(linhas)) * 30
            for numero, (inicio, texto) in enumerate(linhas):
                y1 = round(topo + numero * (pe - topo) / max(1, len(linhas)))
                y2 = round(topo + (numero + 1) * (pe - topo) / max(1, len(linhas)))
                saida.extend(_boxes_da_linha(pagina, texto, inicio, y1, max(y1 + 1, y2),
                                             extraida.largura, bloco.negrito, bloco.italico))
                linha_global += 1
        elif isinstance(bloco, Tabela):
            for linha in bloco.linhas:
                texto = "  ".join(linha)
                y1 = 30 + linha_global * 36
                saida.extend(_boxes_da_linha(pagina, texto, 0, y1, y1 + 28,
                                             extraida.largura, (), ()))
                linha_global += 1
    return saida


def _linhas(texto: str, inicios: Iterable[int]) -> list[tuple[int, str]]:
    pontos = sorted(set(int(i) for i in inicios if 0 <= int(i) < len(texto))) or [0]
    pontos.append(len(texto))
    return [(a, texto[a:b].strip()) for a, b in zip(pontos, pontos[1:]) if texto[a:b].strip()]


def _boxes_da_linha(pagina: Pagina, texto: str, deslocamento: int, y1: int, y2: int,
                    largura: int, negritos, italicos) -> list[Box]:
    palavras = list(re.finditer(r"\S+", texto))
    altura = max(1, y2 - y1)
    escala = max(4.0, altura * 0.42)
    espaco = max(12.0, altura * 0.75)
    cursor = 40.0
    saida = []
    for palavra in palavras:
        inicio, fim = deslocamento + palavra.start(), deslocamento + palavra.end()
        estilo = Estilo(negrito=_sobrepoe(inicio, fim, negritos),
                        italico=_sobrepoe(inicio, fim, italicos))
        x1 = round(cursor)
        x2 = max(x1 + 1, round(cursor + len(palavra.group()) * escala))
        cursor = x2 + espaco
        entry = BoxEntry(palavra.group(), x1, y1, x2, y2, 1.0, FONTE_NATIVA)
        saida.append(Box(pagina.alocar(), entry, estilo=estilo, revisado=True))
    return saida


def _sobrepoe(inicio: int, fim: int, trechos) -> bool:
    return any(max(inicio, int(a)) < min(fim, int(b)) for a, b in trechos)
