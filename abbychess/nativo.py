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

import difflib
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
#: Abaixo disto, a página não vai por cima da camada: as palavras já não são as mesmas.
SIMILARIDADE_MINIMA = 0.9


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
    # Por `pid` (§12.4), como as outras listas de páginas do projeto.
    projeto.dados.extras[CHAVE_DAS_PAGINAS] = sorted(set(
        projeto.dados.extras.get(CHAVE_DAS_PAGINAS, ())) | set(
        projeto.ordem.paginas_para_gravar(importadas)))
    projeto.salvar()
    return Resultado(tuple(importadas), tuple(recusadas))


def _lugares_da_extraida(extraida) -> list[tuple]:
    """A palavra de cada lugar da página da camada, na ordem de `_boxes`: (texto, bloco, célula ou
    None, início, fim)."""
    from core.pagina import Paragrafo, Tabela

    lugares = []
    for bloco in extraida.blocos:
        if isinstance(bloco, Paragrafo):
            lugares += [(m.group(), bloco, None, m.start(), m.end())
                        for m in re.finditer(r"\S+", bloco.texto)]
        elif isinstance(bloco, Tabela):
            for i, linha in enumerate(bloco.linhas):
                for j, celula in enumerate(linha):
                    lugares += [(m.group(), bloco, (i, j), m.start(), m.end())
                                for m in re.finditer(r"\S+", celula)]
    return lugares


def _decisoes_que_nao_cabem(pagina: Pagina) -> list[str]:
    """O que a camada não sabe fazer: a quebra, a junção e o parágrafo decididos, a letra virtual."""
    d = pagina.decisoes
    nomes = (("quebra", d.quebras), ("junção", d.juncoes), ("parágrafo", d.paragrafo_antes),
             ("letra inserida", d.virtuais))
    return [f"{len(v)} {nome}(s) decidida(s) não se aplica(m) à camada" for nome, v in nomes if v]


def remendar(extraida, pagina: Pagina) -> list[str]:
    """As edições da página importada por cima da página da camada (D-3): sair dos boxes apagaria
    os diagramas e embaralharia as colunas, porque o x deles é fictício. Compara as palavras da
    camada com as dos glifos (cada glifo importado é uma palavra) e aplica a troca, o apagar e o
    inserir; as figuras, as colunas e as tabelas ficam. Devolve o que não se aplicou, para o
    relatório. Abaixo de `SIMILARIDADE_MINIMA`, nada se aplica."""
    avisos = _decisoes_que_nao_cabem(pagina)
    lugares = _lugares_da_extraida(extraida)
    base = [lugar[0] for lugar in lugares]
    atual = [b.entry.char for b in pagina.boxes]
    if base == atual:
        return avisos
    casador = difflib.SequenceMatcher(None, base, atual, autojunk=False)
    if casador.ratio() < SIMILARIDADE_MINIMA:
        return avisos + [f"a página mudou demais para ir por cima da camada "
                         f"({casador.ratio():.0%} igual): saiu como a camada"]
    for operacao, i1, i2, j1, j2 in reversed(casador.get_opcodes()):
        if operacao != "equal":
            avisos += _aplicar_o_trecho(lugares, i1, i2, " ".join(atual[j1:j2]))
    return avisos


def _aplicar_o_trecho(lugares, i1: int, i2: int, novo: str) -> list[str]:
    """O trecho [i1, i2) da camada vira `novo`; um trecho que cruza blocos não se aplica."""
    if i1 == i2:                                # inserir: logo depois da palavra anterior
        if not lugares or i1 == 0:
            return [f"“{novo}” não se aplicou: não há palavra antes dela"]
        _, bloco, celula, _inicio, fim = lugares[i1 - 1]
        _trocar(bloco, celula, fim, fim, " " + novo)
        return []
    primeiro, ultimo = lugares[i1], lugares[i2 - 1]
    if primeiro[1] is not ultimo[1] or primeiro[2] != ultimo[2]:
        return [f"“{novo}” não se aplicou: o trecho cruza parágrafos ou células"]
    _, bloco, celula, inicio, _ = primeiro
    fim = ultimo[4]
    if not novo:                                # apagar: com um espaço em volta
        inicio, fim = _com_um_espaco(_texto_do_lugar(bloco, celula), inicio, fim)
    _trocar(bloco, celula, inicio, fim, novo)
    return []


def _texto_do_lugar(bloco, celula) -> str:
    return bloco.texto if celula is None else bloco.linhas[celula[0]][celula[1]]


def _com_um_espaco(texto: str, inicio: int, fim: int) -> tuple[int, int]:
    if fim < len(texto) and texto[fim] == " ":
        return inicio, fim + 1
    return (inicio - 1, fim) if inicio and texto[inicio - 1] == " " else (inicio, fim)


def _trocar(bloco, celula, inicio: int, fim: int, novo: str) -> None:
    if celula is not None:
        i, j = celula
        texto = bloco.linhas[i][j]
        bloco.linhas[i][j] = texto[:inicio] + novo + texto[fim:]
        return
    bloco.texto = bloco.texto[:inicio] + novo + bloco.texto[fim:]
    delta = len(novo) - (fim - inicio)
    if not delta:
        return
    bloco.negrito = _deslocar_os_trechos(bloco.negrito, inicio, fim, delta)
    bloco.italico = _deslocar_os_trechos(bloco.italico, inicio, fim, delta)
    bloco.inicios = [i + delta if i >= fim else i for i in bloco.inicios]
    bloco.pesos, bloco.lacunas = None, None     # por caractere: não valem mais neste parágrafo


def _deslocar_os_trechos(trechos, inicio: int, fim: int, delta: int) -> list:
    saida = []
    for a, b in trechos:
        a2 = a + delta if a >= fim else a
        b2 = b + delta if b >= fim else max(a2, min(b, inicio) if b > inicio else b)
        if b2 > a2:
            saida.append((a2, b2))
    return saida


def paginas_importadas(projeto: ProjetoDeLivro) -> list[int]:
    """As posições no livro das páginas que `importar` criou da camada."""
    return projeto.ordem.posicoes_das_gravadas(projeto.dados.extras.get(CHAVE_DAS_PAGINAS, ()))


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
