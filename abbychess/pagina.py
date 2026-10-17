"""A página: abrir a imagem, segmentar em boxes, ler, revisar e ensinar.

Tudo aqui é sem interface, para a janela chamar numa thread de trabalho e os
testes chamarem direto. A segmentação é a do PyBoxEditor
(`BoxService.generate_boxes_opencv`), com o leitor do livro como árbitro do
separador de glifos colados: medido lá, separar sem árbitro tira 2,3 pontos de
F1 da página, e com árbitro devolve 0,3 acima de não separar.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from core import proporcao, vertical
from core.box_model import BoxEntry
from core.services.box_service import BoxService

from abbychess import gravacao as gv
from abbychess import procedencia

from abbychess.leitor import (FONTE_AGUARDANDO, FONTE_MANUAL, LeitorDoLivro, nome_de_origem,
                              precisa_revisao)
from abbychess.projeto import EXTENSOES_DE_IMAGEM, ProjetoDeLivro

log = logging.getLogger(__name__)

Progresso = Callable[[int, int], None]


#: A maior inclinação que se procura, em graus. Página digitalizada passa de
#: um grau; acima de três a medida já estaria pegando outra coisa.
INCLINACAO_MAXIMA = 3.0
#: O passo da busca, em graus. A 300 dpi, 0,05° numa linha de 2.000 px é 1,7 px.
PASSO_DA_INCLINACAO = 0.05
#: Abaixo disto a página fica como está: girar custa uma interpolação.
INCLINACAO_MINIMA = 0.1

#: O arquivo, na pasta do projeto, com o ângulo medido de cada página.
ARQUIVO_DE_INCLINACOES = "inclinacoes.json"


def medir_inclinacao(cinza: np.ndarray, limite: float = INCLINACAO_MAXIMA,
                     passo: float = PASSO_DA_INCLINACAO) -> float:
    """Quantos graus girar a página para as linhas de texto ficarem retas.

    Pelo perfil de projeção: gira a tinta em cada ângulo da busca e fica com o
    que dá as linhas mais nítidas (a maior variância da soma por linha). O
    `core.preprocess.deskew` mede pelo retângulo mínimo de toda a tinta, e numa
    página com diagramas ele mede o diagrama: na p. 26 do Xadrez Vitorioso deu
    2,19° onde as linhas descem 0,6°, e girar por ele entortaria a página.

    Positivo é anti-horário, como em `cv2.getRotationMatrix2D`. A busca é em
    meia resolução, que basta para o passo de 0,05°.
    """
    import cv2

    from core import preprocess

    tinta = (preprocess.binarize(cinza, "otsu") > 0).astype(np.uint8)
    pequena = cv2.resize(tinta, (max(1, tinta.shape[1] // 2), max(1, tinta.shape[0] // 2)),
                         interpolation=cv2.INTER_AREA)
    altura, largura = pequena.shape
    if not pequena.any():
        return 0.0
    melhor_nota, melhor = -1.0, 0.0
    for angulo in np.arange(-limite, limite + passo / 2, passo):
        giro = cv2.getRotationMatrix2D((largura / 2, altura / 2), float(angulo), 1.0)
        girada = cv2.warpAffine(pequena, giro, (largura, altura), flags=cv2.INTER_NEAREST)
        nota = float(np.var(girada.sum(axis=1).astype(np.float64)))
        # Em empate fica o ângulo mais perto de zero: não girar sem motivo.
        if nota > melhor_nota or (nota == melhor_nota and abs(angulo) < abs(melhor)):
            melhor_nota, melhor = nota, float(angulo)
    return round(melhor, 2)


def girar(cinza: np.ndarray, angulo: float) -> np.ndarray:
    """A página girada em `angulo` graus em volta do centro, com fundo branco."""
    import cv2

    altura, largura = cinza.shape[:2]
    giro = cv2.getRotationMatrix2D((largura / 2, altura / 2), angulo, 1.0)
    return cv2.warpAffine(cinza, giro, (largura, altura), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=255)


def ponto_original(x: float, y: float, angulo: float, largura: int, altura: int
                   ) -> Tuple[float, float]:
    """Onde o ponto da página endireitada estava na página original."""
    import cv2

    giro = cv2.getRotationMatrix2D((largura / 2, altura / 2), angulo, 1.0)
    volta = cv2.invertAffineTransform(giro)
    return (float(volta[0, 0] * x + volta[0, 1] * y + volta[0, 2]),
            float(volta[1, 0] * x + volta[1, 1] * y + volta[1, 2]))


class FonteDePaginas:
    """As páginas de um PDF ou de uma imagem solta, em tons de cinza.

    Com `endireitar`, cada página sai girada pela inclinação medida dela
    (`medir_inclinacao`). Com `pasta`, a medida fica gravada lá
    (`inclinacoes.json`) e vale das próximas vezes: os boxes gravados da página
    estão nas coordenadas da página endireitada, e uma medida que mudasse
    depois os deixaria fora do lugar.
    """

    def __init__(self, caminho: str | Path, *, endireitar: bool = False,
                 pasta: Optional[str | Path] = None, somente_leitura: bool = False):
        self.caminho = Path(caminho)
        self.endireitar = endireitar
        #: Projeto só para leitura: lê as inclinações gravadas, mas não grava as novas.
        self.somente_leitura = somente_leitura
        self._arquivo_das_inclinacoes = Path(pasta) / ARQUIVO_DE_INCLINACOES if pasta else None
        self._inclinacoes: dict = {}
        if self._arquivo_das_inclinacoes is not None and self._arquivo_das_inclinacoes.is_file():
            bruto = json.loads(self._arquivo_das_inclinacoes.read_text(encoding="utf-8"))
            self._inclinacoes = {int(k): float(v) for k, v in bruto.items()}
        self._pdf = None
        #: Uma página por vez: a janela, a pré-carga (`CacheDePaginas`) e o lote renderizam
        #: da mesma fonte, de threads diferentes. Com o lote rodando, abrir uma página fora do
        #: cache espera a página que o lote está renderizando (antes, os dois disputavam o
        #: fitz sem trava, o que não é seguro).
        self._trava = threading.RLock()
        self.total = 1
        sufixo = self.caminho.suffix.lower()
        if sufixo == ".pdf":
            from core.services.pdf_service import PDFService

            self._pdf = PDFService()
            total, erro = self._pdf.load_pdf(str(self.caminho))
            if erro:
                raise OSError(erro)
            self.total = total
        elif sufixo not in EXTENSOES_DE_IMAGEM:
            raise OSError(f"Formato não suportado: {sufixo}")

    def pagina(self, indice: int) -> Image.Image:
        """A página `indice`, endireitada quando a fonte foi aberta para isso."""
        with self._trava:
            return self._pagina(indice)

    def _pagina(self, indice: int) -> Image.Image:
        imagem = self.original(indice)
        if not self.endireitar:
            return imagem
        angulo = self.inclinacao(indice, imagem)
        if abs(angulo) < INCLINACAO_MINIMA:
            return imagem
        return Image.fromarray(girar(np.asarray(imagem.convert("L")), angulo))

    def original(self, indice: int) -> Image.Image:
        """A página como está no arquivo, sem endireitar."""
        if not 0 <= indice < self.total:
            raise IndexError(f"Página {indice + 1} fora de 1..{self.total}")
        if self._pdf is not None:
            imagem = self._pdf.load_page(indice)
            if imagem is None:
                raise OSError(f"A página {indice + 1} não renderizou.")
            return imagem
        with Image.open(self.caminho) as imagem:
            return imagem.convert("L")

    def inclinacao(self, indice: int, imagem: Optional[Image.Image] = None) -> float:
        """O ângulo aplicado à página: o gravado, ou medido agora e gravado."""
        with self._trava:
            return self._inclinacao(indice, imagem)

    def _inclinacao(self, indice: int, imagem: Optional[Image.Image] = None) -> float:
        if not self.endireitar:
            return 0.0
        if indice not in self._inclinacoes:
            imagem = imagem if imagem is not None else self.original(indice)
            self._inclinacoes[indice] = medir_inclinacao(np.asarray(imagem.convert("L")))
            if self._arquivo_das_inclinacoes is not None and not self.somente_leitura:
                gv.gravar_json(self._arquivo_das_inclinacoes,
                               {str(k): v for k, v in sorted(self._inclinacoes.items())})
        angulo = self._inclinacoes[indice]
        return angulo if abs(angulo) >= INCLINACAO_MINIMA else 0.0


class CacheDePaginas:
    """As últimas páginas renderizadas e endireitadas, com a pré-carga da seguinte (§14.1).

    `pagina(i)` devolve `(imagem, matriz em cinza)`, do cache se ela está lá; `precarregar(i)`
    renderiza numa thread de fundo, uma por vez (o pedido mais novo vence). Sem Qt.
    """

    TAMANHO = 5

    def __init__(self, fonte: FonteDePaginas, tamanho: int = TAMANHO):
        self.fonte = fonte
        self.tamanho = tamanho
        self._paginas: "OrderedDict[int, Tuple[Image.Image, np.ndarray]]" = OrderedDict()
        self._trava = threading.Lock()
        self._pedida: Optional[int] = None
        self._thread: Optional[threading.Thread] = None
        #: índice -> o aviso de que a renderização em curso dele acabou: quem pede a mesma
        #: página espera, em vez de renderizá-la de novo (a pré-carga e o clique juntos).
        self._em_curso: Dict[int, threading.Event] = {}

    @property
    def total(self) -> int:
        return self.fonte.total

    def tem(self, indice: int) -> bool:
        with self._trava:
            return indice in self._paginas

    def pagina(self, indice: int) -> Tuple[Image.Image, np.ndarray]:
        while True:
            with self._trava:
                if indice in self._paginas:
                    self._paginas.move_to_end(indice)
                    return self._paginas[indice]
                aviso = self._em_curso.get(indice)
                if aviso is None:
                    aviso = self._em_curso[indice] = threading.Event()
                    break                       # esta thread renderiza
            aviso.wait()                        # outra renderiza: espera e olha de novo
        try:
            imagem = self.fonte.pagina(indice)
            par = (imagem, np.asarray(imagem.convert("L")))
            with self._trava:
                self._paginas[indice] = par
                self._paginas.move_to_end(indice)
                while len(self._paginas) > self.tamanho:
                    self._paginas.popitem(last=False)
            return par
        finally:
            with self._trava:
                del self._em_curso[indice]
            aviso.set()

    def precarregar(self, indice: int) -> None:
        """Renderiza a página `indice` em segundo plano, se ela ainda não está no cache."""
        if not 0 <= indice < self.total or self.tem(indice):
            return
        with self._trava:
            self._pedida = indice
            if self._thread is not None:
                return                          # a thread que roda pega o pedido novo
            self._thread = threading.Thread(target=self._pre_carga, daemon=True,
                                             name="pre-carga")
            self._thread.start()

    def _pre_carga(self) -> None:
        while True:
            with self._trava:
                indice, self._pedida = self._pedida, None
                if indice is None:              # decidido na trava: nenhum pedido se perde
                    self._thread = None
                    return
            try:
                self.pagina(indice)
            except Exception:                   # a página que não renderiza: avisa na vez dela
                log.warning("a pré-carga da página %d falhou", indice + 1, exc_info=True)

    def esperar(self, limite: float = 10.0) -> None:
        """Espera a pré-carga em curso (os testes; fechar o projeto não precisa)."""
        thread = self._thread
        if thread is not None:
            thread.join(limite)


def fonte_do_projeto(projeto: ProjetoDeLivro) -> FonteDePaginas:
    """As páginas do livro como o projeto as lê: endireitadas, se ele nasceu assim."""
    return FonteDePaginas(projeto.fonte, endireitar=projeto.dados.endireitar,
                          pasta=projeto.pasta, somente_leitura=projeto.somente_leitura)


@dataclass
class ResumoDaLeitura:
    boxes: int
    pendentes: int
    por_fonte: dict
    #: Quantos diagramas da página saíram lidos em FEN; só o lote preenche.
    diagramas: int = 0


Caixa = Tuple[int, int, int, int]

#: Folga em volta do tabuleiro, em alturas de caractere, dentro da qual um box é
#: do diagrama e não do texto. É a `MARGEM_DIAGRAMA` do leitor de produção do
#: PyBoxEditor (`core.livro`), que leva junto as coordenadas a-h e 1-8.
MARGEM_DO_TABULEIRO = 1.4


@dataclass
class PaginaSegmentada:
    boxes: List[BoxEntry]
    tabuleiros: List[Caixa] = field(default_factory=list)
    #: A altura de caractere da página, que a leitura dos diagramas usa para
    #: achar os rótulos e a legenda em volta do tabuleiro.
    escala: float = 0.0


def segmentar_pagina(imagem: Image.Image, leitor: Optional[LeitorDoLivro] = None
                     ) -> PaginaSegmentada:
    """Os boxes de texto em ordem de leitura e os tabuleiros, separados.

    Sem isto, as peças e as casas hachuradas de um diagrama sem moldura viram
    boxes de texto e enchem a fila de revisão de lixo. Os tabuleiros saem como
    no leitor de produção do PyBoxEditor (`core.livro`): pelos contornos antes
    do descarte de não texto, com a segunda passada que acha o tabuleiro dentro
    de um painel. Refazer essas etapas de outro jeito foi tentado lá e achou
    seis tabuleiros onde havia dois.
    """
    bruta = segmentar_tudo(imagem, leitor)
    forma = (imagem.size[1], imagem.size[0])
    exclusoes = [_com_margem(t, bruta.escala * MARGEM_DO_TABULEIRO, forma)
                 for t in bruta.tabuleiros]
    boxes = [b for b in bruta.boxes if not any(_contido(b, e) for e in exclusoes)]
    return PaginaSegmentada(BoxService.sort_boxes_reading_order(boxes), bruta.tabuleiros,
                            float(bruta.escala))


@dataclass
class SegmentacaoBruta:
    """Todos os boxes da página, sem tirar os diagramas, os tabuleiros e a escala."""

    boxes: List[BoxEntry]
    tabuleiros: List[Caixa]
    escala: float


def segmentar_tudo(imagem: Image.Image, leitor: Optional[LeitorDoLivro] = None
                   ) -> SegmentacaoBruta:
    """A segmentação e os tabuleiros, antes de decidir o que é texto.

    `segmentar_pagina` tira daqui os boxes de dentro dos tabuleiros; o editor
    de áreas (`abbychess.zonas`) tira os que as áreas mandam tirar.
    """
    from core import diagrama

    cinza = imagem.convert("L")
    matriz = np.asarray(cinza)
    binaria = BoxService.binaria_para_segmentacao(
        matriz, max_contornos=BoxService.MAX_CONTORNOS_DE_TEXTO)
    antes, th, escala, _ = BoxService.boxes_antes_do_descarte(
        cinza, max_contornos=BoxService.MAX_CONTORNOS_DE_TEXTO, binaria_inicial=binaria)
    escala = escala or 1
    tabuleiros = (list(diagrama.localizar(antes, escala=escala, imagem=matriz, binaria=th))
                  if antes else [])

    arbitro = leitor.arbitro if leitor is not None else None
    todas = BoxService.generate_boxes_opencv(cinza, arbitro=arbitro, binaria=binaria)
    return SegmentacaoBruta(todas, tabuleiros, escala)


def segmentar(imagem: Image.Image, leitor: Optional[LeitorDoLivro] = None) -> List[BoxEntry]:
    """Só os boxes de texto da página, em ordem de leitura."""
    return segmentar_pagina(imagem, leitor).boxes


def _com_margem(caixa: Caixa, margem: float, forma) -> Caixa:
    altura, largura = forma[:2]
    m = int(round(margem))
    x1, y1, x2, y2 = caixa
    return max(0, x1 - m), max(0, y1 - m), min(largura, x2 + m), min(altura, y2 + m)


def _contido(b: BoxEntry, caixa: Caixa) -> bool:
    return caixa[0] <= b.x1 and b.x2 <= caixa[2] and caixa[1] <= b.y1 and b.y2 <= caixa[3]


def recorte(imagem, box: BoxEntry) -> np.ndarray:
    """O recorte do box em pé e positivo, como o classificador o quer."""
    return vertical.recorte_de_pe(np.asarray(imagem.convert("L")
                                             if isinstance(imagem, Image.Image) else imagem), box)


def ler_boxes(imagem: Image.Image, boxes: List[BoxEntry], leitor: LeitorDoLivro, *,
              so_pendentes: bool = False, progresso: Optional[Progresso] = None,
              cancelado: Callable[[], bool] = lambda: False) -> ResumoDaLeitura:
    """Lê os boxes no lugar. Com `so_pendentes`, não toca no que já foi confirmado.

    Box manual nunca é relido: a correção do usuário tem precedência até ele
    pedir outra coisa (invariante 2 do PyBoxEditor).
    """
    pagina = np.asarray(imagem.convert("L"))
    referencia = proporcao.altura_de_referencia(boxes) if boxes else None
    alvos = [b for b in boxes if b.source != FONTE_MANUAL and (
        not so_pendentes or precisa_revisao(b.char, b.source, b.confidence, leitor.limiares))]
    for i, box in enumerate(alvos):
        if cancelado():
            break
        _ler_um(pagina, box, leitor, referencia)
        if progresso and (i % 10 == 0 or i == len(alvos) - 1):
            progresso(i + 1, len(alvos))
    return resumir(boxes, leitor)


def _ler_um(pagina: np.ndarray, box: BoxEntry, leitor: LeitorDoLivro,
            referencia: Optional[float]) -> None:
    por_leitura(box, leitor.ler(vertical.recorte_de_pe(pagina, box),
                                altura_de_referencia=referencia))


def por_leitura(box: BoxEntry, leitura) -> None:
    """Põe a leitura (`leitor.Leitura`) no box e registra de que amostra ela veio."""
    box.char, box.source, box.confidence = leitura.char, leitura.fonte, leitura.confianca
    procedencia.registrar(box, leitura.amostra)


def aguardando(box: BoxEntry) -> bool:
    """O box ainda não lido (§11): a interface não o leu e espera o servidor."""
    return not box.char and box.source == FONTE_AGUARDANDO


def recortes_para_ler(imagem: Image.Image, boxes: List[BoxEntry], indices: Sequence[int]
                      ) -> List[Tuple[np.ndarray, Optional[float]]]:
    """Os recortes em pé dos boxes `indices`, com a altura de referência da página: o pedido
    de leitura de glifos ao servidor (§11), sem mandar a página inteira pela fila."""
    pagina = np.asarray(imagem.convert("L"))
    referencia = proporcao.altura_de_referencia(boxes) if boxes else None
    return [(vertical.recorte_de_pe(pagina, boxes[i]), referencia) for i in indices]


def _reler(imagem: Image.Image, boxes: List[BoxEntry], indices: List[int],
           leitor: Optional[LeitorDoLivro]) -> None:
    """Lê de novo só os boxes que uma edição criou ou mudou."""
    if leitor is None:
        return
    pagina = np.asarray(imagem.convert("L"))
    referencia = proporcao.altura_de_referencia(boxes) if boxes else None
    for i in indices:
        _ler_um(pagina, boxes[i], leitor, referencia)


def resumir(boxes: List[BoxEntry], leitor: LeitorDoLivro) -> ResumoDaLeitura:
    por_fonte: dict = {}
    for b in boxes:
        por_fonte[b.source or "vazio"] = por_fonte.get(b.source or "vazio", 0) + 1
    return ResumoDaLeitura(len(boxes), len(fila_de_revisao(boxes, leitor)), por_fonte)


def fila_de_revisao(boxes: List[BoxEntry], leitor: LeitorDoLivro) -> List[int]:
    """Índices dos boxes a revisar, do menos confiável ao mais.

    Em empate de confiança fica a ordem de leitura, para o usuário andar pela
    página e não pular de um canto para outro.
    """
    pendentes = [i for i, b in enumerate(boxes)
                 if precisa_revisao(b.char, b.source, b.confidence, leitor.limiares)]
    return sorted(pendentes, key=lambda i: (round(boxes[i].confidence, 2), i))


def ensinar(imagem: Image.Image, boxes: List[BoxEntry], indice: int, char: str,
            leitor: LeitorDoLivro, projeto: ProjetoDeLivro, pagina: int, *,
            propagar: bool = True, gid: Optional[int] = None) -> int:
    """Ensina o box como `char` neste livro e propaga o padrão pela página.

    O box ensinado vira manual. Com `propagar`, os boxes ainda pendentes são
    comparados com os padrões do livro, e os que forem o mesmo glifo passam a
    sair dele: é assim que uma correção resolve as repetições da página inteira.
    Devolve quantos pendentes deixaram de ser pendentes.

    `gid` é o do glifo, que vai para o nome do padrão; a janela o dá (ela trabalha com
    gids). Sem ele, quem trabalha com a lista (ferramentas, testes) o pede ao projeto.
    Os boxes da lista são mudados no lugar: quem chama da janela passa cópias
    (`edicao.copias_para_ler`).
    """
    box = boxes[indice]
    referencia = proporcao.altura_de_referencia(boxes) if boxes else None
    if gid is None:
        gid = projeto.gid_do_box(pagina, boxes, indice)
    leitor.ensinar(recorte(imagem, box), char, altura_de_referencia=referencia,
                   origem=nome_de_origem(projeto.dados.nome, pagina, indice, gid))
    box.char, box.source, box.confidence = char, FONTE_MANUAL, 1.0
    procedencia.registrar(box, procedencia.NENHUMA)     # é a origem do padrão, não cópia
    return propagar_padroes(imagem, boxes, leitor) if propagar else 0


def ensinar_varios(imagem: Image.Image, boxes: List[BoxEntry], indices: List[int], char: str,
                   leitor: LeitorDoLivro, projeto: ProjetoDeLivro, pagina: int, *,
                   gids: Optional[dict] = None) -> int:
    """Ensina vários boxes como o mesmo `char` e propaga uma vez só no fim.

    É a seleção do modo de treino: o usuário marca as ocorrências que a leitura
    errou de jeitos diferentes (borrada, cortada, mais grossa) e as ensina num
    Enter. Cada uma vira uma amostra, o que o k-NN do livro aproveita melhor do
    que uma amostra só. Devolve quantos pendentes a propagação resolveu.
    """
    for indice in sorted(set(indices)):
        ensinar(imagem, boxes, indice, char, leitor, projeto, pagina, propagar=False,
                gid=None if gids is None else gids[indice])
    return propagar_padroes(imagem, boxes, leitor)


def propagar_padroes(imagem: Image.Image, boxes: List[BoxEntry], leitor: LeitorDoLivro) -> int:
    """Aplica os padrões do livro aos boxes pendentes, sem a cadeia global.

    Um padrão novo só muda o que o k-NN do livro responde; a rede e a base
    global dariam a mesma leitura de antes. Por isso basta consultar o livro,
    o que custa milissegundos, em vez de reler a página inteira, que custava
    oito segundos no Darcy Lima. Devolve quantos pendentes foram resolvidos.
    """
    pagina = np.asarray(imagem.convert("L"))
    referencia = proporcao.altura_de_referencia(boxes) if boxes else None
    resolvidos = 0
    for box in boxes:
        if not precisa_revisao(box.char, box.source, box.confidence, leitor.limiares):
            continue
        leitura = leitor.ler_pelo_livro(vertical.recorte_de_pe(pagina, box), referencia)
        if leitura.char:
            box.char, box.source, box.confidence = leitura.char, leitura.fonte, leitura.confianca
            procedencia.registrar(box, leitura.amostra)
            resolvidos += 1
    return resolvidos


def confirmar(boxes: List[BoxEntry], indice: int, char: str) -> None:
    """Aceita a leitura do box sem gravar padrão: corrige só esta ocorrência."""
    box = boxes[indice]
    box.char, box.source, box.confidence = char, FONTE_MANUAL, 1.0
    procedencia.registrar(box, procedencia.NENHUMA)


def descartar(boxes: List[BoxEntry], indice: int) -> BoxEntry:
    """Tira da página um box que não é caractere (sujeira, pedaço de diagrama)."""
    return boxes.pop(indice)


def texto(boxes: List[BoxEntry]) -> str:
    """O texto da página na ordem de leitura, pelas linhas e palavras do core.

    É o documento de `abbychess.texto.montar`, no modo `san` (as figurinhas como letras),
    que é como o texto sempre saiu daqui.
    """
    from abbychess import texto as tx

    return tx.texto(tx.montar(tx.pagina_avulsa(boxes)), modo=tx.SAN)


# ----------------------------------------------------------------------
# Editar os boxes: dividir, juntar e mover as bordas
# ----------------------------------------------------------------------

def dividir(imagem: Image.Image, boxes: List[BoxEntry], indice: int,
            leitor: Optional[LeitorDoLivro] = None, *, x: Optional[int] = None) -> List[int]:
    """Divide em dois o box que juntou dois glifos, e relê as partes.

    Com `x`, a coluna da página onde cortar, o corte é vertical ali: é o ponto
    que o usuário escolheu no recorte ampliado. Sem `x`, quem decide é o
    `BoxService.split_box` do PyBoxEditor, que corta no vão mais fundo da tinta
    e escolhe o eixo sozinho.

    **Cada parte é aparada à própria tinta.** Num "rp" colado, o box vai da
    altura do x ao fim da perna do "p"; sem aparar, o "r" sairia com a altura
    do par, e a altura relativa que o padrão do livro grava ensinaria um "r"
    do tamanho de um "p".

    As partes entram no lugar do box, a da esquerda (ou de cima) primeiro, sem
    leitura e fora do manual. Com `leitor`, são relidas na hora. Devolve os
    índices das duas; os boxes depois de `indice` andam uma casa para a frente.
    """
    box = boxes[indice]
    matriz = np.asarray(imagem.convert("L"))
    if x is None:
        partes = BoxService.split_box(box, matriz)
    else:
        if not box.x1 < x < box.x2:
            raise ValueError(f"O corte em x={x} está fora do box ({box.x1}..{box.x2}).")
        partes = [replace(box, x2=x), replace(box, x1=x)]
    tinta = BoxService._tinta_do_box(box, matriz)
    novas = []
    for parte in partes:
        parte = replace(parte, char="", source="", confidence=0.0,
                        angulo=box.angulo, negativo=box.negativo, moldura=box.moldura)
        aparada = _aparar(parte, box, tinta)
        if aparada is None:
            raise ValueError("Um dos lados do corte ficou sem tinta.")
        novas.append(aparada)
    boxes[indice:indice + 1] = novas
    _reler(imagem, boxes, [indice, indice + 1], leitor)
    return [indice, indice + 1]


def _aparar(parte: BoxEntry, inteiro: BoxEntry, tinta) -> Optional[BoxEntry]:
    """A parte encolhida até a tinta dela, medida na máscara do box inteiro."""
    if tinta is None:
        return parte
    pedaco = tinta[parte.y1 - inteiro.y1:parte.y2 - inteiro.y1,
                   parte.x1 - inteiro.x1:parte.x2 - inteiro.x1]
    linhas, colunas = np.nonzero(pedaco)
    if not linhas.size:
        return None
    return replace(parte, x1=parte.x1 + int(colunas.min()), x2=parte.x1 + int(colunas.max()) + 1,
                   y1=parte.y1 + int(linhas.min()), y2=parte.y1 + int(linhas.max()) + 1)


def criar_box(imagem: Image.Image, boxes: List[BoxEntry], area: Caixa,
              leitor: Optional[LeitorDoLivro] = None) -> int:
    """Cria o box do glifo dentro da área que o usuário desenhou, e o lê.

    É o quadro do treino de padrões do FineReader: o glifo que a segmentação
    perdeu, partiu ou juntou com o vizinho se marca à mão. A área é aparada à
    tinta, e os boxes que ficam dentro dela (o "m" quebrado em três) saem: o
    quadro novo os substitui. O box entra na ordem de leitura da página.

    Devolve o índice dele; os outros índices mudam, e quem guarda índices os
    remapeia pela identidade dos boxes.
    """
    largura, altura = imagem.size
    x1, y1, x2, y2 = area
    x1, x2 = sorted((x1, x2))
    y1, y2 = sorted((y1, y2))
    quadro = BoxService.clamp_box(BoxEntry("", x1, y1, x2, y2), largura, altura)
    if quadro.x2 - quadro.x1 < 1 or quadro.y2 - quadro.y1 < 1:
        raise ValueError("A área está fora da página.")
    tinta = BoxService._tinta_do_box(quadro, np.asarray(imagem.convert("L")))
    novo = _aparar(quadro, quadro, tinta) if tinta is not None and tinta.any() else None
    if novo is None:
        raise ValueError("Não há tinta na área marcada.")
    dentro = [b for b in boxes if _contido(b, (novo.x1, novo.y1, novo.x2, novo.y2))
              or _centro_dentro(b, novo)]
    restantes = [b for b in boxes if not any(b is d for d in dentro)]
    boxes[:] = BoxService.sort_boxes_reading_order(restantes + [novo])
    indice = next(i for i, b in enumerate(boxes) if b is novo)
    _reler(imagem, boxes, [indice], leitor)
    return indice


def a_manter_na_releitura(boxes, lida: bool) -> List[BoxEntry]:
    """Os glifos que reconhecer de novo não troca (§4.6), como cópias dos `BoxEntry`: numa
    página ainda não lida, os marcados à mão (todos os boxes dela); numa lida, os que o usuário
    decidiu (fonte `manual`) ou viu e aceitou (`revisado`). `boxes` são os `Box` do modelo.
    As decisões dos outros passam aos glifos novos pela sobreposição (`modelo.reconciliar`)."""
    from abbychess.edicao import copia
    from abbychess.leitor import FONTE_MANUAL

    return [copia(b.entry) for b in boxes
            if not lida or b.entry.source == FONTE_MANUAL or b.revisado]


def manter_marcados(segmentados: List[BoxEntry], marcados: List[BoxEntry]) -> List[BoxEntry]:
    """Os boxes da segmentação com os glifos marcados à mão no lugar dos de baixo.

    É o F5 (ou o lote) numa página em que o usuário marcou glifos antes de
    reconhecer: o quadro dele vale mais que o box que a segmentação achou ali.
    Sai o box segmentado cujo centro cai dentro de um marcado, ou que tem mais
    da metade da área dentro dele. O resto fica, em ordem de leitura.
    """
    def coberto(b: BoxEntry) -> bool:
        area = max((b.x2 - b.x1) * (b.y2 - b.y1), 1)
        for m in marcados:
            largura = min(b.x2, m.x2) - max(b.x1, m.x1)
            altura = min(b.y2, m.y2) - max(b.y1, m.y1)
            if _centro_dentro(b, m) or (largura > 0 and altura > 0
                                        and largura * altura > 0.5 * area):
                return True
        return False

    return BoxService.sort_boxes_reading_order(
        [b for b in segmentados if not coberto(b)] + list(marcados))


def _centro_dentro(b: BoxEntry, quadro: BoxEntry) -> bool:
    cx, cy = (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2
    return quadro.x1 <= cx <= quadro.x2 and quadro.y1 <= cy <= quadro.y2


def vizinho(boxes: List[BoxEntry], indice: int, passo: int) -> Optional[int]:
    """O box ao lado na ordem de leitura, se ele estiver na mesma linha.

    Mesma linha é sobrepor na vertical: o fim de uma linha e o começo da
    seguinte são vizinhos na lista, mas juntá-los não é o que se quer.
    """
    outro = indice + passo
    if not 0 <= outro < len(boxes) or passo == 0:
        return None
    a, b = boxes[indice], boxes[outro]
    return outro if min(a.y2, b.y2) > max(a.y1, b.y1) else None


def juntar(imagem: Image.Image, boxes: List[BoxEntry], i: int, j: int,
           leitor: Optional[LeitorDoLivro] = None) -> int:
    """Junta dois boxes num só, o retângulo que cobre os dois, e o relê.

    É o contrário de `dividir`: para o glifo que a segmentação partiu, como um
    "m" quebrado em dois ou um acento solto da letra. O box novo fica no lugar
    do primeiro na ordem de leitura e herda o ângulo e a polaridade dele.
    Devolve o índice dele; os boxes depois do segundo andam uma casa para trás.
    """
    if i == j:
        raise ValueError("Não dá para juntar um box com ele mesmo.")
    i, j = sorted((i, j))
    a, b = boxes[i], boxes[j]
    boxes[i] = replace(a, char="", source="", confidence=0.0,
                       x1=min(a.x1, b.x1), y1=min(a.y1, b.y1),
                       x2=max(a.x2, b.x2), y2=max(a.y2, b.y2))
    del boxes[j]
    _reler(imagem, boxes, [i], leitor)
    return i


def ajustar(imagem: Image.Image, boxes: List[BoxEntry], indice: int,
            leitor: Optional[LeitorDoLivro] = None, *,
            esquerda: int = 0, cima: int = 0, direita: int = 0, baixo: int = 0) -> BoxEntry:
    """Move as bordas do box, em pixels da página, e o relê.

    Positivo move a borda para a direita ou para baixo, como as coordenadas.
    O box fica dentro da página (`BoxService.clamp_box`) e com pelo menos um
    pixel de cada lado; a leitura antiga, mesmo a manual, vale para o desenho
    antigo e sai.
    """
    box = boxes[indice]
    largura, altura = imagem.size
    novo = BoxService.clamp_box(replace(box, x1=box.x1 + esquerda, y1=box.y1 + cima,
                                        x2=box.x2 + direita, y2=box.y2 + baixo),
                                largura, altura)
    if novo.x2 - novo.x1 < 1 or novo.y2 - novo.y1 < 1:
        raise ValueError("O box ficaria vazio.")
    boxes[indice] = replace(box, char="", source="", confidence=0.0,
                            x1=novo.x1, y1=novo.y1, x2=novo.x2, y2=novo.y2)
    _reler(imagem, boxes, [indice], leitor)
    return boxes[indice]
