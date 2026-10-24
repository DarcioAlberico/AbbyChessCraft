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

from abbychess import contexto
from abbychess import gravacao as gv
from abbychess import procedencia
from abbychess import sequencia as sq

from abbychess.leitor import FONTE_AGUARDANDO, FONTE_MANUAL, LeitorDoLivro, nome_de_origem
from abbychess.projeto import ARQUIVO_DE_INCLINACOES, EXTENSOES_DE_IMAGEM, ProjetoDeLivro

log = logging.getLogger(__name__)

Progresso = Callable[[int, int], None]


#: A maior inclinação que se procura, em graus. Página digitalizada passa de
#: um grau; acima de três a medida já estaria pegando outra coisa.
INCLINACAO_MAXIMA = 3.0
#: O passo da busca, em graus. A 300 dpi, 0,05° numa linha de 2.000 px é 1,7 px.
PASSO_DA_INCLINACAO = 0.05
#: Abaixo disto a página fica como está: girar custa uma interpolação.
INCLINACAO_MINIMA = 0.1



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
    """As páginas do livro em tons de cinza, pela sequência do livro (§12.4).

    Cada posição é uma `Entrada`: a página `pagina` da fonte dela (o PDF ou a imagem do
    livro, ou um arquivo em `inseridas/`), cortada pelo `quadro` e girada pelo `giro`. Sem a
    `sequencia` (as ferramentas e os testes que abrem um PDF solto), a posição `i` é a página
    `i` do arquivo.

    Com `endireitar`, cada página sai girada pela inclinação dela: o ângulo à mão da entrada,
    ou o medido (`medir_inclinacao`). Com `pasta`, a medida fica gravada lá
    (`inclinacoes.json`) e vale das próximas vezes: os boxes gravados da página estão nas
    coordenadas da página endireitada, e uma medida que mudasse depois os deixaria fora do
    lugar. A chave da medida é a da entrada (`_chave_da_inclinacao`).
    """

    def __init__(self, caminho: str | Path, *, endireitar: bool = False,
                 pasta: Optional[str | Path] = None, somente_leitura: bool = False,
                 sequencia: Optional[Callable[[], "sq.Sequencia"]] = None,
                 por_pid: bool = False):
        self.caminho = Path(caminho)
        self.endireitar = endireitar
        #: Projeto só para leitura: lê as inclinações gravadas, mas não grava as novas.
        self.somente_leitura = somente_leitura
        self.pasta = Path(pasta) if pasta else None
        #: A sequência do livro de agora (a do projeto, que as operações de página trocam).
        self._sequencia = sequencia
        #: As medidas por `pid` (o projeto da v3, com todo `pid` gravado); senão, a página do
        #: livro sem geometria segue pelo índice do PDF (`_chave_da_inclinacao`).
        self.por_pid = por_pid
        self._arquivo_das_inclinacoes = (self.pasta / ARQUIVO_DE_INCLINACOES
                                         if self.pasta else None)
        self._inclinacoes: dict = {}
        if self._arquivo_das_inclinacoes is not None and self._arquivo_das_inclinacoes.is_file():
            bruto = json.loads(self._arquivo_das_inclinacoes.read_text(encoding="utf-8"))
            self._inclinacoes = {(int(k) if k.isdigit() else k): float(v)
                                 for k, v in bruto.items()}
        #: Um render do fitz por vez: a janela, a pré-carga (`CacheDePaginas`) e o lote
        #: renderizam da mesma fonte, de threads diferentes, e o fitz não é seguro entre
        #: threads. Só o render fica na trava: medir a inclinação (~370 ms numa página nunca
        #: vista) e girar são do OpenCV, que solta o GIL, e correm fora dela; antes, o clique
        #: numa página esperava a medida inteira da página que a pré-carga estava fazendo.
        self._trava = threading.RLock()
        #: O dicionário das inclinações e o `inclinacoes.json`.
        self._trava_das_inclinacoes = threading.Lock()
        #: fonte da entrada -> o arquivo aberto (o do livro e os inseridos, na primeira vez).
        self._arquivos: Dict[str, "_ArquivoDePaginas"] = {
            sq.FONTE_DO_LIVRO: _ArquivoDePaginas(self.caminho)}

    @property
    def total(self) -> int:
        """Quantas páginas o livro tem (as da sequência; sem ela, as do arquivo)."""
        if self._sequencia is not None:
            return len(self._sequencia())
        return self._arquivos[sq.FONTE_DO_LIVRO].total

    def entrada(self, indice: int) -> "sq.Entrada":
        """A entrada da posição `indice` (IndexError fora do livro)."""
        if self._sequencia is not None:
            return self._sequencia().entrada_em(indice)
        if not 0 <= indice < self.total:
            raise IndexError(f"Página {indice + 1} fora de 1..{self.total}")
        return sq.Entrada(indice, sq.FONTE_DO_LIVRO, indice)

    def pagina(self, indice: int) -> Image.Image:
        """A página `indice`, endireitada quando a fonte foi aberta para isso."""
        return self.pagina_da_entrada(self.entrada(indice))

    def pagina_da_entrada(self, entrada: "sq.Entrada", renderizador=None) -> Image.Image:
        """A imagem da entrada (§12.4): a página da fonte endireitada inteira, depois o quadro
        e o giro (`abbychess.geometria`: assim cortar e girar são contas inteiras). Com o
        `renderizador` (`render.RenderEmProcesso`, o da pré-carga), a página do PDF é
        renderizada no processo dele, sem segurar o GIL desta."""
        imagem = self._da_fonte(entrada, renderizador)
        angulo = self.inclinacao_da_entrada(entrada, imagem)
        if abs(angulo) >= INCLINACAO_MINIMA:
            imagem = Image.fromarray(girar(np.asarray(imagem.convert("L")), angulo))
        return com_geometria(imagem, entrada.quadro, entrada.giro)

    def original(self, indice: int) -> Image.Image:
        """A página sem endireitar (a camada de texto do PDF e as ferramentas, só na página
        sem quadro nem giro: com eles, a imagem da entrada, que já é endireitada)."""
        return self.original_da_entrada(self.entrada(indice))

    def original_da_entrada(self, entrada: "sq.Entrada") -> Image.Image:
        if entrada.quadro is None and not entrada.giro:
            return self._da_fonte(entrada)
        return self.pagina_da_entrada(entrada)

    def _da_fonte(self, entrada: "sq.Entrada", renderizador=None) -> Image.Image:
        """A página da fonte da entrada, como está no arquivo. O `renderizador` só vale para
        o PDF, e fora da trava (o fitz daqui não é tocado); sem resposta dele, renderiza aqui."""
        arquivo = self._arquivo(entrada.fonte)
        if renderizador is not None and arquivo.e_pdf:
            imagem = renderizador.renderizar(arquivo.caminho, entrada.pagina)
            if imagem is not None:
                return imagem
        with self._trava:
            return arquivo.pagina(entrada.pagina)

    def tamanho_da_fonte(self, entrada: "sq.Entrada") -> Tuple[int, int]:
        """(largura, altura) da página da fonte renderizada, sem renderizá-la."""
        arquivo = self._arquivo(entrada.fonte)
        with self._trava:
            return arquivo.tamanho(entrada.pagina)

    def _arquivo(self, fonte: str) -> "_ArquivoDePaginas":
        with self._trava:
            arquivo = self._arquivos.get(fonte)
            if arquivo is None:
                if self.pasta is None:
                    raise OSError(f"A página inserida {fonte} precisa da pasta do projeto.")
                arquivo = self._arquivos[fonte] = _ArquivoDePaginas(self.pasta / fonte)
            return arquivo

    def inclinacao(self, indice: int, imagem: Optional[Image.Image] = None) -> float:
        return self.inclinacao_da_entrada(self.entrada(indice), imagem)

    def fixar_inclinacao(self, entrada: "sq.Entrada", angulo: float) -> None:
        """O ângulo da entrada é este (a página com boxes que muda de giro guarda o ângulo
        em que foi lida, §12.4: medir de novo moveria os boxes)."""
        self.fixar_inclinacoes([(entrada, angulo)])

    def fixar_inclinacoes(self, pares) -> None:
        """`fixar_inclinacao` de várias entradas, com uma gravação só do `inclinacoes.json`
        (dividir ou girar o livro inteiro)."""
        if not self.endireitar:
            return
        novas = {_chave_da_inclinacao(e, self.por_pid): float(angulo)
                 for e, angulo in pares if e.angulo is None}
        if not novas:
            return
        with self._trava_das_inclinacoes:
            self._inclinacoes.update(novas)
            if self._arquivo_das_inclinacoes is not None and not self.somente_leitura:
                gv.gravar_json(self._arquivo_das_inclinacoes, {
                    str(k): v for k, v in sorted(self._inclinacoes.items(),
                                                 key=_ordem_da_chave)})

    def inclinacao_guardada(self, entrada: "sq.Entrada") -> Optional[float]:
        """O ângulo medido e guardado da entrada, sem medir (None: ainda não foi medido)."""
        if not self.endireitar or entrada.angulo is not None:
            return None
        with self._trava_das_inclinacoes:
            angulo = self._inclinacoes.get(_chave_da_inclinacao(entrada, self.por_pid))
            if angulo is None and self.por_pid and entrada.do_livro_sem_geometria:
                angulo = self._inclinacoes.get(entrada.pagina)
        return angulo

    def inclinacao_da_entrada(self, entrada: "sq.Entrada",
                              imagem: Optional[Image.Image] = None) -> float:
        """O ângulo aplicado à página: o à mão da entrada, ou o gravado, ou medido agora e
        gravado. Duas threads que medem a mesma página ao mesmo tempo dão o mesmo número;
        vale o da primeira. O ângulo à mão vale mesmo na fonte que não endireita: é uma
        escolha do usuário na página, e não a medida automática."""
        if entrada.angulo is not None:
            return entrada.angulo if abs(entrada.angulo) >= INCLINACAO_MINIMA else 0.0
        if not self.endireitar:
            return 0.0
        chave = _chave_da_inclinacao(entrada, self.por_pid)
        with self._trava_das_inclinacoes:
            angulo = self._inclinacoes.get(chave)
            if angulo is None and self.por_pid and entrada.do_livro_sem_geometria:
                # A medida da v2, pelo índice do PDF: a migração a passa a `pid`, e uma queda
                # no meio dela não faz medir de novo (os boxes estão no ângulo medido).
                angulo = self._inclinacoes.get(entrada.pagina)
        if angulo is None:
            # Medida na página inteira da fonte, já girada (o texto deitado de uma página
            # escaneada de lado mede em pé); como girar de 90 e endireitar comutam em volta
            # do centro (a menos de um pixel na página não quadrada), o ângulo vale aplicado
            # à página da fonte.
            imagem = imagem if imagem is not None else self._da_fonte(entrada)
            medido = medir_inclinacao(np.asarray(
                com_geometria(imagem, None, entrada.giro).convert("L")))   # fora das travas
            with self._trava_das_inclinacoes:
                angulo = self._inclinacoes.get(chave)
                if angulo is None:
                    angulo = self._inclinacoes[chave] = medido
                    if self._arquivo_das_inclinacoes is not None and not self.somente_leitura:
                        gv.gravar_json(self._arquivo_das_inclinacoes, {
                            str(k): v for k, v in sorted(self._inclinacoes.items(),
                                                         key=_ordem_da_chave)})
        return angulo if abs(angulo) >= INCLINACAO_MINIMA else 0.0


def _ordem_da_chave(item) -> tuple:
    """Os índices do PDF em ordem numérica, como até o passo K; as chaves `p<pid>` depois."""
    chave = item[0]
    return (0, chave, "") if isinstance(chave, int) else (1, 0, chave)


def _chave_da_inclinacao(entrada: "sq.Entrada", por_pid: bool = False):
    """A chave da medida em `inclinacoes.json`: `p<pid>:inteira:<giro>` (§12.4), no projeto
    da v3: a medida é da página inteira (o quadro vem depois de endireitar) já girada. Num da
    v2 (só para leitura, ou uma fonte sem projeto), a página do livro sem quadro nem giro usa
    o índice dela no PDF, como até o passo K: lá o `pid` das páginas nunca editadas só existe
    na memória e muda de uma sessão para outra."""
    if not por_pid and entrada.do_livro_sem_geometria:
        return entrada.pagina
    return f"p{entrada.pid}:inteira:{entrada.giro}"


#: Quantos pixels o quadro pode passar da página (o arredondamento de um render).
FOLGA_DO_QUADRO = 2


class QuadroForaDaPagina(OSError):
    """O quadro da entrada não cabe na página da fonte (um `OSError`: abrir a página avisa,
    como a página que não renderiza)."""


#: O giro horário da entrada -> a transposição do PIL (que gira no sentido anti-horário).
_TRANSPOSICOES = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180,
                  270: Image.Transpose.ROTATE_90}


def com_geometria(imagem: Image.Image, quadro: Optional[Tuple[int, int, int, int]],
                  giro: int) -> Image.Image:
    """A imagem cortada pelo `quadro` (`[x0, y0, x1, y1)` em pixels dela) e girada `giro`
    graus no sentido horário, sem interpolar (§12.4: conta exata). Um quadro que passa da
    página mais que `FOLGA_DO_QUADRO` px (a página renderizada noutro tamanho, um
    `projeto.json` estragado) levanta `QuadroForaDaPagina`: cortar menos que o pedido em
    silêncio deixaria os boxes fora do lugar."""
    if quadro is not None:
        x0, y0, x1, y1 = quadro
        largura, altura = imagem.size
        if (x0 < -FOLGA_DO_QUADRO or y0 < -FOLGA_DO_QUADRO or x1 > largura + FOLGA_DO_QUADRO
                or y1 > altura + FOLGA_DO_QUADRO or x1 <= x0 or y1 <= y0):
            raise QuadroForaDaPagina(f"o quadro {list(quadro)} não cabe na página "
                                     f"({largura}×{altura} px)")
        imagem = imagem.crop((max(0, x0), max(0, y0), min(x1, largura), min(y1, altura)))
    if giro:
        imagem = imagem.transpose(_TRANSPOSICOES[giro])
    return imagem


class _ArquivoDePaginas:
    """Um PDF ou uma imagem solta, página por página (a trava é de quem chama)."""

    def __init__(self, caminho: Path):
        self.caminho = Path(caminho)
        self._pdf = None
        #: O documento do fitz aberto uma vez para os tamanhos (girar ou cortar muitas
        #: páginas de uma vez pergunta o de cada uma), e os já perguntados.
        self._documento = None
        self._tamanhos: Dict[int, Tuple[int, int]] = {}
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

    @property
    def e_pdf(self) -> bool:
        return self._pdf is not None

    def tamanho(self, indice: int) -> Tuple[int, int]:
        """(largura, altura) da página renderizada, sem renderizar (a do `get_pixmap` do
        core: o retângulo da página na escala do DPI, arredondado como ele arredonda)."""
        if not 0 <= indice < self.total:
            raise IndexError(f"Página {indice + 1} fora de 1..{self.total}")
        if self._pdf is None:
            with Image.open(self.caminho) as imagem:
                return imagem.size
        if indice not in self._tamanhos:
            import fitz
            from core.services.pdf_service import DPI_PADRAO

            if self._documento is None:
                self._documento = fitz.open(stream=self._pdf.pdf_bytes, filetype="pdf")
            escala = DPI_PADRAO / 72
            retangulo = (self._documento[indice].rect * fitz.Matrix(escala, escala)).irect
            self._tamanhos[indice] = (retangulo.width, retangulo.height)
        return self._tamanhos[indice]

    def pagina(self, indice: int) -> Image.Image:
        if not 0 <= indice < self.total:
            raise IndexError(f"Página {indice + 1} fora de 1..{self.total}")
        if self._pdf is not None:
            imagem = self._pdf.load_page(indice)
            if imagem is None:
                raise OSError(f"A página {indice + 1} não renderizou.")
            return imagem
        with Image.open(self.caminho) as imagem:
            return imagem.convert("L")


#: Quanto quem pede a página na hora espera a pré-carga dela no processo de render (uma página
#: nunca vista leva ~0,5 s com a medida da inclinação); passou disso, renderiza aqui.
ESPERA_PELA_PRE_CARGA_S = 1.0


class CacheDePaginas:
    """As últimas páginas renderizadas e endireitadas, com a pré-carga da seguinte (§14.1).

    `pagina(i)` devolve `(imagem, matriz em cinza)`, do cache se ela está lá; `precarregar(i)`
    renderiza numa thread de fundo, uma por vez (o pedido mais novo vence). A chave é a
    `Entrada` da posição (o `pid` e a geometria): a página que muda de lugar continua no cache,
    e a que muda de quadro, giro ou ângulo sai dele. Sem Qt: o `preparar` (a janela dá o da
    `QImage`) roda com a matriz na thread que renderiza, e `preparada(i, imagem)` devolve o
    resultado.
    """

    TAMANHO = 5

    def __init__(self, fonte: FonteDePaginas, tamanho: int = TAMANHO,
                 preparar: Optional[Callable[[np.ndarray], object]] = None,
                 renderizador=None):
        self.fonte = fonte
        #: Onde a pré-carga renderiza o PDF (`render.RenderEmProcesso`): fora deste processo,
        #: sem parar a interface. A página pedida na hora renderiza aqui (é mais rápido, e a
        #: interface a espera de qualquer jeito).
        self.renderizador = renderizador
        self.tamanho = tamanho
        self.preparar = preparar
        self._paginas: "OrderedDict[sq.Entrada, Tuple[Image.Image, np.ndarray]]" = OrderedDict()
        #: entrada -> o `preparar` da matriz dela (sai do cache junto com a página).
        self._preparadas: Dict["sq.Entrada", object] = {}
        self._trava = threading.Lock()
        self._pedida: Optional["sq.Entrada"] = None
        self._thread: Optional[threading.Thread] = None
        #: entrada -> (o aviso de que a renderização em curso dela acabou, e se ela é no
        #: processo de render): quem pede a mesma página espera, em vez de renderizá-la de
        #: novo (a pré-carga e o clique juntos); a do processo, só `ESPERA_PELA_PRE_CARGA_S`.
        self._em_curso: Dict["sq.Entrada", Tuple[threading.Event, bool]] = {}

    @property
    def total(self) -> int:
        return self.fonte.total

    def tem(self, indice: int) -> bool:
        try:
            entrada = self.fonte.entrada(indice)
        except IndexError:
            return False
        with self._trava:
            return entrada in self._paginas

    def pagina(self, indice: int) -> Tuple[Image.Image, np.ndarray]:
        return self._da_entrada(self.fonte.entrada(indice))

    def _da_entrada(self, entrada: "sq.Entrada", renderizador=None
                    ) -> Tuple[Image.Image, np.ndarray]:
        while True:
            with self._trava:
                if entrada in self._paginas:
                    self._paginas.move_to_end(entrada)
                    return self._paginas[entrada]
                em_curso = self._em_curso.get(entrada)
                if em_curso is None:
                    aviso = threading.Event()
                    self._em_curso[entrada] = (aviso, renderizador is not None)
                    break                       # esta thread renderiza
                aviso, de_fora = em_curso
            if de_fora and renderizador is None:
                # A pré-carga está no processo de render: quem pede na hora (a interface) espera
                # o que um render daqui levaria, e não o limite do processo, se ele travou.
                if not aviso.wait(ESPERA_PELA_PRE_CARGA_S):
                    return self._renderizar(entrada, None)
                continue
            aviso.wait()                        # outra renderiza: espera e olha de novo
        try:
            return self._renderizar(entrada, renderizador)
        finally:
            with self._trava:
                del self._em_curso[entrada]
            aviso.set()

    def _renderizar(self, entrada: "sq.Entrada", renderizador) -> Tuple[Image.Image, np.ndarray]:
        """Renderiza a entrada (no processo do `renderizador`, se houver) e a guarda no cache."""
        imagem = (self.fonte.pagina_da_entrada(entrada) if renderizador is None
                  else self.fonte.pagina_da_entrada(entrada, renderizador))
        par = (imagem, np.asarray(imagem.convert("L")))
        preparada = None
        if self.preparar is not None:
            try:
                preparada = self.preparar(par[1])
            except Exception:                   # sem a preparada, a janela converte sozinha
                log.warning("preparar a página do pid %d falhou", entrada.pid, exc_info=True)
        with self._trava:
            self._paginas[entrada] = par
            self._paginas.move_to_end(entrada)
            if preparada is not None:
                self._preparadas[entrada] = preparada
            else:
                self._preparadas.pop(entrada, None)
            while len(self._paginas) > self.tamanho:
                velha, _ = self._paginas.popitem(last=False)
                self._preparadas.pop(velha, None)
        return par

    def esquecer(self, entrada: "sq.Entrada") -> None:
        """Tira a página do cache (o ângulo dela mudou, e a `Entrada` é a mesma)."""
        with self._trava:
            self._paginas.pop(entrada, None)
            self._preparadas.pop(entrada, None)

    def preparada(self, indice: int, imagem: Image.Image) -> Optional[object]:
        """O `preparar` da página `indice`, se ela está no cache e é esta `imagem`."""
        try:
            entrada = self.fonte.entrada(indice)
        except IndexError:
            return None
        with self._trava:
            par = self._paginas.get(entrada)
            if par is None or par[0] is not imagem:
                return None
            return self._preparadas.get(entrada)

    def precarregar(self, indice: int) -> None:
        """Renderiza a página `indice` em segundo plano, se ela ainda não está no cache."""
        try:
            entrada = self.fonte.entrada(indice)    # uma vez: a sequência pode mudar no meio
        except IndexError:
            return
        with self._trava:
            if entrada in self._paginas or entrada in self._em_curso:
                return
            self._pedida = entrada
            if self._thread is not None:
                return                          # a thread que roda pega o pedido novo
            self._thread = threading.Thread(target=self._pre_carga, daemon=True,
                                             name="pre-carga")
            self._thread.start()

    def _pre_carga(self) -> None:
        while True:
            with self._trava:
                entrada, self._pedida = self._pedida, None
                if entrada is None:             # decidido na trava: nenhum pedido se perde
                    self._thread = None
                    return
            try:
                self._da_entrada(entrada, self.renderizador)
            except Exception:                   # a página que não renderiza: avisa na vez dela
                log.warning("a pré-carga da página do pid %d falhou", entrada.pid,
                            exc_info=True)

    def esperar(self, limite: float = 10.0) -> None:
        """Espera a pré-carga em curso (os testes; fechar o projeto não precisa)."""
        thread = self._thread
        if thread is not None:
            thread.join(limite)


def fonte_do_projeto(projeto: ProjetoDeLivro) -> FonteDePaginas:
    """As páginas do livro como o projeto as lê: pela sequência dele, endireitadas se ele
    nasceu assim. A sequência é montada aqui, na thread de quem abre (o fitz que conta as
    páginas não roda junto com um render da pré-carga)."""
    projeto.sequencia
    return FonteDePaginas(projeto.fonte, endireitar=projeto.dados.endireitar,
                          pasta=projeto.pasta, somente_leitura=projeto.somente_leitura,
                          sequencia=lambda: projeto.sequencia,
                          por_pid=projeto.sequencia_gravada)


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


def cinza(imagem) -> np.ndarray:
    """A página em tons de cinza: a imagem PIL convertida, ou a matriz que já é (a do cache
    de páginas, `CacheDePaginas`). Converter custa ~7 ms numa página do livro: quem recorta
    muitos glifos converte uma vez, e a janela passa a matriz que já tem."""
    return np.asarray(imagem.convert("L")) if isinstance(imagem, Image.Image) else imagem


def recorte(imagem, box: BoxEntry) -> np.ndarray:
    """O recorte do box em pé e positivo, como o classificador o quer."""
    return vertical.recorte_de_pe(cinza(imagem), box)


def efeitos_de_impressao(imagem: Image.Image, boxes: Sequence[BoxEntry]) -> List[Optional[bool]]:
    """O negrito de cada glifo (`efeitos_da_pagina`, sem o itálico)."""
    return efeitos_da_pagina(imagem, boxes)[0]


def efeitos_da_pagina(imagem: Image.Image, boxes: Sequence[BoxEntry]
                      ) -> Tuple[List[Optional[bool]], List[Optional[bool]]]:
    """O negrito e o itálico de cada glifo, medidos por palavra.

    ``None`` quando a palavra não basta para uma decisão, ``False``/``True`` quando o efeito
    é conhecido. O negrito é a régua pública do core (`_negritos`); o itálico, a inclinação
    das bordas das letras (`_italicos`), porque o core não tem régua do itálico."""
    from core.notacao import palavras_da_pagina

    if not boxes:
        return [], []
    # A página em tons de cinza uma vez: convertê-la a cada glifo dobrava o tempo do lote.
    pagina = cinza(imagem)
    palavras = [[simbolo.indice for simbolo in palavra.simbolos]
                for linha in palavras_da_pagina(list(boxes)) for palavra in linha]
    return _negritos(pagina, boxes, palavras), _italicos(pagina, boxes, palavras)


def _negritos(pagina: np.ndarray, boxes: Sequence[BoxEntry], palavras: Sequence[List[int]]
              ) -> List[Optional[bool]]:
    """O negrito de cada glifo, medido por palavra com a régua pública do core. A referência
    é a página inteira: a régua compara a espessura de cada caractere com as outras
    ocorrências dele, como :mod:`core.negrito` exige."""
    from collections import defaultdict
    from math import isnan

    from core import negrito

    medidas = [negrito.espessura(recorte(pagina, box)) for box in boxes]
    amostras = defaultdict(list)
    for box, medida in zip(boxes, medidas):
        if box.char and medida is not None and not isnan(medida):
            amostras[box.char].append(medida)
    referencia = negrito.referencia(amostras)

    pesos = []
    for indices in palavras:
        glifos = [(boxes[i].char, medidas[i]) for i in indices
                  if boxes[i].char and medidas[i] is not None and not isnan(medidas[i])]
        pesos.append(negrito.relativo(glifos, referencia) if len(glifos) >= 2 else None)
    normal = negrito.escala([peso for peso in pesos if peso is not None])
    efeitos: List[Optional[bool]] = [None] * len(boxes)
    for indices, peso in zip(palavras, pesos):
        if peso is None:
            continue
        forte = negrito.e_negrito(peso, normal)
        for i in indices:
            efeitos[i] = forte
    return efeitos


#: O itálico (`_italicos`): a palavra cujas bordas quase verticais pendem
#: `INCLINACAO_DO_ITALICO` graus além das da página, com o pico `FORCA_DO_ITALICO` vezes o da
#: vertical, medida em `MINIMO_DE_LETRAS_DO_ITALICO` letras ou mais. Ajustados no Odds & Ends
#: (o itálico pela fonte do PDF): 0 falsos em 17.950 palavras retas e 95,8% das itálicas nas
#: páginas que não entraram no ajuste (`ferramentas/medir_italico.py`).
INCLINACAO_DO_ITALICO = 7.0
FORCA_DO_ITALICO = 2.0
MINIMO_DE_LETRAS_DO_ITALICO = 3
#: Até quantos graus da vertical uma borda conta: o itálico dos livros pende ~10–17°; a
#: diagonal do Z (~34°) e a da perna do y (~22°, fraca) ficam de fora ou não vencem.
JANELA_DO_ITALICO = 25
#: A inclinação até a qual a palavra conta como reta na referência da página (a página quase
#: toda em itálico não puxa a referência para o itálico).
RETA_ATE = 5.0


def _inclinacao_das_bordas(recorte: np.ndarray, mascara: np.ndarray
                           ) -> Optional[Tuple[float, float]]:
    """`(graus, força)`: a inclinação mais comum das bordas quase verticais da tinta (positiva
    com o topo à direita) e quantas vezes o pico pesa o que pesa a vertical. As hastes e os
    lados das letras redondas fazem o pico; as diagonais (v, w, y) se espalham dos dois lados.
    `None` com borda de menos."""
    import cv2

    tons = recorte.astype(np.float32)
    gx = cv2.Sobel(tons, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(tons, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = np.hypot(gx, gy)
    if not magnitude.size or magnitude.max() <= 0:
        return None
    usar = mascara & (magnitude > 0.25 * magnitude.max()) & (np.abs(gx) > 1e-3)
    if usar.sum() < 30:
        return None
    # A borda que pende α da vertical tem o gradiente em α da horizontal: tan α = gy/gx.
    angulo = np.degrees(np.arctan(gy[usar] / gx[usar]))
    dentro = np.abs(angulo) <= JANELA_DO_ITALICO
    if dentro.sum() < 20:
        return None
    janela = JANELA_DO_ITALICO
    h = np.bincount(np.round(angulo[dentro]).astype(int) + janela,
                    weights=magnitude[usar][dentro], minlength=2 * janela + 1)
    h = np.convolve(h, np.exp(-0.5 * (np.arange(-6, 7) / 2.0) ** 2), mode="same")
    pico = int(np.argmax(h))
    return float(pico - janela), float(h[pico] / max(h[janela], 1e-9))


def _italicos(pagina: np.ndarray, boxes: Sequence[BoxEntry], palavras: Sequence[List[int]]
              ) -> List[Optional[bool]]:
    """O itálico de cada glifo, pela inclinação das letras da palavra (`_inclinacao_das_bordas`)
    contra a das palavras retas da página (a página escaneada torta não vira itálico). Só as
    letras de pé contam: algarismos, figurinas e a barra do ½ têm diagonais que não são
    itálico. A palavra inteira leva o resultado; sem letras que bastem, `None`."""
    from statistics import median

    altura, largura = pagina.shape[:2]
    medidas = []
    for indices in palavras:
        letras = [boxes[i] for i in indices
                  if boxes[i].char.isalpha() and not boxes[i].angulo
                  and not getattr(boxes[i], "negativo", False)]
        medida = None
        if len(letras) >= MINIMO_DE_LETRAS_DO_ITALICO:
            x1, y1 = max(0, min(b.x1 for b in letras)), max(0, min(b.y1 for b in letras))
            x2 = min(largura, max(b.x2 for b in letras))
            y2 = min(altura, max(b.y2 for b in letras))
            if x2 - x1 > 2 and y2 - y1 > 2:
                mascara = np.zeros((y2 - y1, x2 - x1), bool)
                for b in letras:
                    mascara[max(0, b.y1 - y1):max(0, b.y2 - y1),
                            max(0, b.x1 - x1):max(0, b.x2 - x1)] = True
                medida = _inclinacao_das_bordas(pagina[y1:y2, x1:x2], mascara)
        medidas.append(medida)
    retas = [m[0] for m in medidas if m is not None and abs(m[0]) <= RETA_ATE]
    normal = median(retas) if retas else 0.0
    efeitos: List[Optional[bool]] = [None] * len(boxes)
    for indices, medida in zip(palavras, medidas):
        if medida is None:
            continue
        inclinada = (medida[0] - normal >= INCLINACAO_DO_ITALICO
                     and medida[1] >= FORCA_DO_ITALICO)
        for i in indices:
            efeitos[i] = inclinada
    return efeitos


def ler_boxes(imagem: Image.Image, boxes: List[BoxEntry], leitor: LeitorDoLivro, *,
              so_pendentes: bool = False, progresso: Optional[Progresso] = None,
              cancelado: Callable[[], bool] = lambda: False,
              pendentes: Optional[Sequence[bool]] = None) -> ResumoDaLeitura:
    """Lê os boxes no lugar. Com `so_pendentes`, não toca no que já foi confirmado.

    Box manual nunca é relido: a correção do usuário tem precedência até ele
    pedir outra coisa (invariante 2 do PyBoxEditor). Os pendentes são os de
    `contexto.pendentes`, ou os `pendentes` de quem lê cópias (`propagar_padroes`).
    """
    pagina = cinza(imagem)
    referencia = proporcao.altura_de_referencia(boxes) if boxes else None
    if so_pendentes and pendentes is None:
        pendentes = contexto.pendentes(boxes, leitor.limiares)
    alvos = [b for i, b in enumerate(boxes) if b.source != FONTE_MANUAL and (
        not so_pendentes or pendentes[i])]
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
    pagina = cinza(imagem)
    referencia = proporcao.altura_de_referencia(boxes) if boxes else None
    return [(vertical.recorte_de_pe(pagina, boxes[i]), referencia) for i in indices]


def _reler(imagem: Image.Image, boxes: List[BoxEntry], indices: List[int],
           leitor: Optional[LeitorDoLivro]) -> None:
    """Lê de novo só os boxes que uma edição criou ou mudou."""
    if leitor is None:
        return
    pagina = cinza(imagem)
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
    página e não pular de um canto para outro. O glifo que a palavra desmente
    (`contexto`) entra mesmo com a confiança alta.
    """
    pendentes = [i for i, p in enumerate(contexto.pendentes(boxes, leitor.limiares)) if p]
    return sorted(pendentes, key=lambda i: (round(boxes[i].confidence, 2), i))


def ensinar(imagem: Image.Image, boxes: List[BoxEntry], indice: int, char: str,
            leitor: LeitorDoLivro, projeto: ProjetoDeLivro, pagina: int, *,
            propagar: bool = True, gid: Optional[int] = None, efeito=None) -> int:
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
                   origem=nome_de_origem(projeto.dados.nome, pagina, indice, gid), efeito=efeito)
    box.char, box.source, box.confidence = char, FONTE_MANUAL, 1.0
    procedencia.registrar(box, procedencia.NENHUMA)     # é a origem do padrão, não cópia
    return propagar_padroes(imagem, boxes, leitor) if propagar else 0


def ensinar_varios(imagem: Image.Image, boxes: List[BoxEntry], indices: List[int], char: str,
                   leitor: LeitorDoLivro, projeto: ProjetoDeLivro, pagina: int, *,
                   gids: Optional[dict] = None, efeitos: Optional[Sequence] = None) -> int:
    """Ensina vários boxes como o mesmo `char` e propaga uma vez só no fim.

    É a seleção do modo de treino: o usuário marca as ocorrências que a leitura
    errou de jeitos diferentes (borrada, cortada, mais grossa) e as ensina num
    Enter. Cada uma vira uma amostra, o que o k-NN do livro aproveita melhor do
    que uma amostra só. Devolve quantos pendentes a propagação resolveu.
    """
    for indice in sorted(set(indices)):
        ensinar(imagem, boxes, indice, char, leitor, projeto, pagina, propagar=False,
                gid=None if gids is None else gids[indice],
                efeito=None if efeitos is None else efeitos[indice])
    return propagar_padroes(imagem, boxes, leitor, efeitos=efeitos)


def propagar_padroes(imagem: Image.Image, boxes: List[BoxEntry], leitor: LeitorDoLivro, *,
                     efeitos: Optional[Sequence] = None,
                     pendentes: Optional[Sequence[bool]] = None) -> int:
    """Aplica os padrões do livro aos boxes pendentes, sem a cadeia global.

    Um padrão novo só muda o que o k-NN do livro responde; a rede e a base
    global dariam a mesma leitura de antes. Por isso basta consultar o livro,
    o que custa milissegundos, em vez de reler a página inteira, que custava
    oito segundos no Darcy Lima. Devolve quantos pendentes foram resolvidos.

    Os pendentes são os de `contexto.pendentes`; quem lê cópias fora da interface passa
    `pendentes`, os mesmos com que escolheu o que copiar.
    """
    pagina = cinza(imagem)
    referencia = proporcao.altura_de_referencia(boxes) if boxes else None
    if pendentes is None:
        pendentes = contexto.pendentes(boxes, leitor.limiares)
    resolvidos = 0
    for i, box in enumerate(boxes):
        if not pendentes[i]:
            continue
        efeito = None if efeitos is None else efeitos[i]
        leitura = leitor.ler_pelo_livro(vertical.recorte_de_pe(pagina, box), referencia, efeito)
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
