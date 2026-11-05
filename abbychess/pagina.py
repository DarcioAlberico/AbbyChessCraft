"""A página: abrir a imagem, segmentar em boxes, ler, revisar e ensinar.

Tudo aqui é sem interface, para a janela chamar numa thread de trabalho e os
testes chamarem direto. A segmentação é a do PyBoxEditor
(`BoxService.generate_boxes_opencv`), com o leitor do livro como árbitro do
separador de glifos colados: medido lá, separar sem árbitro tira 2,3 pontos de
F1 da página, e com árbitro devolve 0,3 acima de não separar.

O negrito e o itálico dos glifos estão em `efeitos`; dividir, juntar, criar e mover as
bordas dos boxes, em `editar_boxes`.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Collection, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from core import proporcao, vertical
from core.box_model import BoxEntry
from core.services.box_service import BoxService

from abbychess import contexto
from abbychess import gravacao as gv
from abbychess import procedencia
from abbychess import sequencia as sq
from abbychess.borracha import com_borrachas

from abbychess.leitor import (FONTE_AGUARDANDO, FONTE_MANUAL, FONTE_NENHUMA, LeitorDoLivro,
                              nome_de_origem, precisa_revisao)
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
        imagem = com_borrachas(imagem, entrada.borrachas)     # CA-12.17: medida sem a borracha
        if abs(angulo) >= INCLINACAO_MINIMA:
            imagem = Image.fromarray(girar(np.asarray(imagem.convert("L")), angulo))
        return com_geometria(imagem, entrada.quadro, entrada.giro)

    def original(self, indice: int) -> Image.Image:
        """A página sem endireitar (a camada de texto do PDF e as ferramentas, só na página
        sem quadro nem giro: com eles, a imagem da entrada, que já é endireitada)."""
        return self.original_da_entrada(self.entrada(indice))

    def original_da_entrada(self, entrada: "sq.Entrada") -> Image.Image:
        if entrada.quadro is None and not entrada.giro:
            return com_borrachas(self._da_fonte(entrada), entrada.borrachas)
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
            self._gravar_as_inclinacoes()

    def _gravar_as_inclinacoes(self) -> None:
        """Grava o `inclinacoes.json` (com a trava das inclinações tomada), se há onde e o
        projeto não é só leitura."""
        if self._arquivo_das_inclinacoes is not None and not self.somente_leitura:
            gv.gravar_json(self._arquivo_das_inclinacoes, {
                str(k): v for k, v in sorted(self._inclinacoes.items(), key=_ordem_da_chave)})

    def inclinacao_guardada(self, entrada: "sq.Entrada") -> Optional[float]:
        """O ângulo medido e guardado da entrada, sem medir (None: ainda não foi medido)."""
        if not self.endireitar or entrada.angulo is not None:
            return None
        with self._trava_das_inclinacoes:
            angulo = self._inclinacoes.get(_chave_da_inclinacao(entrada, self.por_pid))
            if angulo is None and self.por_pid and entrada.do_livro_sem_geometria:
                # A medida da v2, pelo índice do PDF: a migração a passa a `pid`, e uma queda
                # no meio dela não faz medir de novo (os boxes estão no ângulo medido).
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
        angulo = self.inclinacao_guardada(entrada)
        if angulo is None:
            angulo = self._medir_e_guardar(entrada, imagem)
        return angulo if abs(angulo) >= INCLINACAO_MINIMA else 0.0

    def _medir_e_guardar(self, entrada: "sq.Entrada", imagem: Optional[Image.Image]) -> float:
        """Mede a inclinação da entrada (fora das travas) e a grava; se outra thread gravou a
        dela antes, vale a primeira.

        Medida na página inteira da fonte, já girada (o texto deitado de uma página escaneada
        de lado mede em pé); como girar de 90 e endireitar comutam em volta do centro (a menos
        de um pixel na página não quadrada), o ângulo vale aplicado à página da fonte."""
        chave = _chave_da_inclinacao(entrada, self.por_pid)
        imagem = imagem if imagem is not None else self._da_fonte(entrada)
        medido = medir_inclinacao(np.asarray(
            com_geometria(imagem, None, entrada.giro).convert("L")))   # fora das travas
        with self._trava_das_inclinacoes:
            angulo = self._inclinacoes.get(chave)
            if angulo is None:
                angulo = self._inclinacoes[chave] = medido
                self._gravar_as_inclinacoes()
        return angulo


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
    nasceu assim. A sequência já foi montada ao abrir (`ordem.montar`), na thread de quem
    abre (o fitz que conta as páginas não roda junto com um render da pré-carga)."""
    return FonteDePaginas(projeto.fonte, endireitar=projeto.dados.endireitar,
                          pasta=projeto.pasta, somente_leitura=projeto.somente_leitura,
                          sequencia=lambda: projeto.sequencia,
                          por_pid=projeto.ordem.gravada)


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

    cinza = apagar_fios(imagem.convert("L"))
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
    todas = devolver_pingos(todas, binaria, escala)
    return SegmentacaoBruta(todas, tabuleiros, escala)


#: O fio horizontal (`apagar_fios`): ao menos esta fração da largura da página, no máximo esta
#: da altura, e com a tinta enchendo ao menos esta fração da caixa dele.
FIO_LARGURA, FIO_ALTURA, FIO_CHEIO = 0.25, 0.012, 0.6


def apagar_fios(cinza: Image.Image) -> Image.Image:
    """A página em tons de cinza sem os fios horizontais soltos: o traço embaixo do cabeçalho
    corrido, o de cima do rodapé.

    **O fio levava o cabeçalho junto.** No *Chess School 1* do Mirkovic o cabeçalho corrido
    fica de 4 a 11 px acima de um fio da largura do texto: "CHESS SCHOOL" (p. 18) saía sem
    box nenhum, e o da p. 89 em dez pedaços lidos como "bi i i h i h ifi ♘", no meio do texto.
    Sem o fio, saem os 11 e os 36 glifos, e os tabuleiros são os mesmos.

    O fio é um componente de tinta sozinho, longo (`FIO_LARGURA`), fino (`FIO_ALTURA`) e
    cheio (`FIO_CHEIO`). A moldura do tabuleiro tem os lados no mesmo componente e não é
    fio; o sublinhado encostado nas letras também não (as letras esvaziam a caixa)."""
    import cv2

    matriz = np.asarray(cinza)
    altura, largura = matriz.shape[:2]
    tinta = (matriz < 128).astype(np.uint8)
    total, rotulos, medidas, _c = cv2.connectedComponentsWithStats(tinta, connectivity=8)
    larguras, alturas, areas = (medidas[:, k] for k in (cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT,
                                                         cv2.CC_STAT_AREA))
    fios = np.nonzero((larguras >= FIO_LARGURA * largura) & (alturas <= FIO_ALTURA * altura)
                      & (areas >= FIO_CHEIO * larguras * alturas))[0]
    fios = fios[fios != 0]                               # o fundo
    if not len(fios):
        return cinza
    limpa = matriz.copy()
    limpa[np.isin(rotulos, fios)] = 255
    return Image.fromarray(limpa)


#: O pingo perdido: até esta fração da escala de texto nos dois eixos, e com pelo menos
#: esta outra de área (abaixo é poeira, não pingo).
PINGO_PERDIDO_MAXIMO, PINGO_PERDIDO_AREA_MINIMA = 0.6, 0.02


def devolver_pingos(boxes: List[BoxEntry], binaria: np.ndarray, escala: float
                    ) -> List[BoxEntry]:
    """Devolve ao glifo de baixo o pingo que a segmentação deixou sem box.

    **O "i" em negrito perdia o pingo.** O merge do core cola o pingo na haste, mas o
    par (pingo, vão de 1–2 px, haste) passa de 1,6 escalas de altura, e o
    `dividir_linhas_coladas` o toma por duas linhas grudadas: corta no vão e joga fora
    o pingo, mais curto que um caractere (`PECA_MINIMA_DE_LINHA`). A rede via só a
    haste, que em negrito tem a serifa do "1", e lia "1" com 0,98 ("exerc1se",
    "analys1s" na p. 15 do Aagaard, "A Matter of Endgame Technique").

    O pingo devolvido é um componente de tinta **inteiro sem box** (a cauda de um "p"
    cortada pelo mesmo passo é parte de um componente que tem box, e fica de fora),
    pequeno nos dois eixos, com o centro sobre o box de baixo e a até
    `FOLGA_DE_DIACRITICO` da altura dele: a régua com que o core cola o pingo.
    """
    if not boxes or binaria is None or escala <= 0:
        return boxes
    import cv2

    # A tinta sem box (quase nada numa página): a binária com os boxes apagados. O componente
    # dela que encosta em tinta coberta é pedaço de um glifo que tem box.
    orfa = _sem_os_boxes(binaria, boxes)
    total, rotulos, medidas, _c = cv2.connectedComponentsWithStats(orfa, connectivity=8)
    saida = list(boxes)
    crescidos = set()
    for rotulo, x, y, w, h in _orfaos_pequenos(medidas, escala):
        if _encosta_em_tinta_coberta(rotulos, rotulo, binaria, orfa, x, y, w, h):
            continue
        k = _glifo_de_baixo(saida, crescidos, x, y, w, h)
        if k is None:
            continue
        b = saida[k]
        saida[k] = replace(b, x1=min(b.x1, x), y1=y, x2=max(b.x2, x + w))
        crescidos.add(k)
    return saida


def _sem_os_boxes(binaria: np.ndarray, boxes: List[BoxEntry]) -> np.ndarray:
    """A binária com a tinta dos boxes apagada: a tinta sem box."""
    orfa = binaria.copy()
    for b in boxes:
        orfa[b.y1:b.y2, b.x1:b.x2] = 0
    return orfa


def _orfaos_pequenos(medidas: np.ndarray, escala: float):
    """`(rótulo, x, y, w, h)` de cada componente da tinta sem box com tamanho de pingo: até
    `PINGO_PERDIDO_MAXIMO` escalas nos dois eixos e com a área mínima (abaixo é poeira)."""
    import cv2

    maximo, area_minima = PINGO_PERDIDO_MAXIMO * escala, PINGO_PERDIDO_AREA_MINIMA * escala ** 2
    larguras, alturas, areas = (medidas[:, k] for k in (cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT,
                                                         cv2.CC_STAT_AREA))
    pequenos = (larguras <= maximo) & (alturas <= maximo) & (areas >= area_minima)
    for rotulo in np.nonzero(pequenos)[0]:
        if rotulo == 0:                                  # o fundo
            continue
        x, y, w, h = (int(v) for v in medidas[rotulo][:4])
        yield rotulo, x, y, w, h


def _encosta_em_tinta_coberta(rotulos: np.ndarray, rotulo, binaria: np.ndarray,
                              orfa: np.ndarray, x: int, y: int, w: int, h: int) -> bool:
    """O componente encosta em tinta que tem box: é pedaço de um glifo (a cauda de um "p"
    cortada), e não um pingo inteiro."""
    import cv2

    y0, x0 = max(0, y - 1), max(0, x - 1)
    janela = np.s_[y0:y + h + 1, x0:x + w + 1]
    vizinhanca = cv2.dilate((rotulos[janela] == rotulo).astype(np.uint8),
                            np.ones((3, 3), np.uint8)) > 0
    return bool((vizinhanca & (binaria[janela] > 0) & (orfa[janela] == 0)).any())


def _glifo_de_baixo(saida: List[BoxEntry], crescidos: set, x: int, y: int, w: int, h: int
                    ) -> Optional[int]:
    """O box em pé, ainda sem pingo devolvido, com o centro do pingo sobre ele e logo abaixo
    (até `FOLGA_DE_DIACRITICO` da altura dele); o mais perto, ou None."""
    centro = x + w / 2
    candidatos = [k for k, b in enumerate(saida)
                  if k not in crescidos and not (b.angulo or 0) % 180
                  and b.x1 <= centro <= b.x2 and w <= b.width + 1
                  and 0 <= b.y1 - (y + h) <= BoxService.FOLGA_DE_DIACRITICO * b.height]
    if not candidatos:
        return None
    return min(candidatos, key=lambda k: saida[k].y1 - (y + h))


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


def ler_boxes(imagem: Image.Image, boxes: List[BoxEntry], leitor: LeitorDoLivro, *,
              so_pendentes: bool = False, progresso: Optional[Progresso] = None,
              cancelado: Callable[[], bool] = lambda: False,
              pendentes: Optional[Sequence[bool]] = None,
              nao_ler: Collection[int] = ()) -> ResumoDaLeitura:
    """Lê os boxes no lugar. Com `so_pendentes`, não toca no que já foi confirmado.

    Box manual nunca é relido (invariante 2 do PyBoxEditor), nem as posições de `nao_ler`, os
    revisados da página (D-5). Os pendentes são os de `contexto.pendentes`, ou os `pendentes`
    de quem lê cópias (`propagar_padroes`).
    """
    pagina = cinza(imagem)
    referencia = proporcao.altura_de_referencia(boxes) if boxes else None
    if so_pendentes and pendentes is None:
        pendentes = contexto.pendentes(boxes, leitor.limiares)
    _ler_os_alvos(pagina, _alvos_da_leitura(boxes, so_pendentes, pendentes, nao_ler), leitor,
                  referencia, progresso, cancelado)
    return resumir(boxes, leitor)


def _alvos_da_leitura(boxes: List[BoxEntry], so_pendentes: bool,
                      pendentes: Optional[Sequence[bool]],
                      nao_ler: Collection[int] = ()) -> List[BoxEntry]:
    """Os boxes a ler: nunca os manuais nem os de `nao_ler`; com `so_pendentes`, só os
    pendentes."""
    fora = set(nao_ler)
    return [b for i, b in enumerate(boxes) if b.source != FONTE_MANUAL and i not in fora and (
        not so_pendentes or pendentes[i])]


def _ler_os_alvos(pagina: np.ndarray, alvos: List[BoxEntry], leitor: LeitorDoLivro,
                  referencia: Optional[float], progresso: Optional[Progresso],
                  cancelado: Callable[[], bool]) -> None:
    """Lê os boxes no lugar, um por um, até o `cancelado`; o `progresso` a cada 10 e no fim."""
    for i, box in enumerate(alvos):
        if cancelado():
            break
        _ler_um(pagina, box, leitor, referencia)
        if progresso and (i % 10 == 0 or i == len(alvos) - 1):
            progresso(i + 1, len(alvos))


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


def sem_leitura(box: BoxEntry) -> bool:
    """O box que a cadeia toda leu e ninguém reconheceu (o painel pode sugerir o palpite da
    rede, §9.2)."""
    return not box.char and box.source == FONTE_NENHUMA


def recortes_para_ler(imagem: Image.Image, boxes: List[BoxEntry], indices: Sequence[int]
                      ) -> List[Tuple[np.ndarray, Optional[float]]]:
    """Os recortes em pé dos boxes `indices`, com a altura de referência da página: o pedido
    de leitura de glifos ao servidor (§11), sem mandar a página inteira pela fila."""
    pagina = cinza(imagem)
    referencia = proporcao.altura_de_referencia(boxes) if boxes else None
    return [(vertical.recorte_de_pe(pagina, boxes[i]), referencia) for i in indices]


def resumir(boxes: List[BoxEntry], leitor: LeitorDoLivro) -> ResumoDaLeitura:
    por_fonte: dict = {}
    for b in boxes:
        por_fonte[b.source or "vazio"] = por_fonte.get(b.source or "vazio", 0) + 1
    return ResumoDaLeitura(len(boxes), len(fila_de_revisao(boxes, leitor)), por_fonte)


def fila_de_revisao(boxes: List[BoxEntry], leitor: LeitorDoLivro,
                    no_fim: Collection[int] = ()) -> List[int]:
    """Índices dos boxes a revisar, do menos confiável ao mais.

    Em empate de confiança fica a ordem de leitura, para o usuário andar pela
    página e não pular de um canto para outro. O glifo que a palavra desmente
    (`contexto`) entra mesmo com a confiança alta. Os de `no_fim` (as margens que a
    exportação tira, `margens.margens_da_pagina`) vêm depois de todos os outros.
    """
    pendentes = [i for i, p in enumerate(contexto.pendentes(boxes, leitor.limiares)) if p]
    no_fim = set(no_fim)
    return sorted(pendentes, key=lambda i: (i in no_fim, round(boxes[i].confidence, 2), i))


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

    Um padrão novo só muda o que o k-NN do livro responde: basta o livro, em milissegundos.
    Devolve quantos pendentes foram resolvidos. Os pendentes são os de `contexto.pendentes`;
    quem lê cópias fora da interface passa `pendentes`, os com que escolheu o que copiar.
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
            # O improvável que o livro lê igual continua pendente (a palavra ainda o
            # desmente): resolvido é o que muda de caractere ou saía pela confiança.
            if leitura.char != box.char or precisa_revisao(box.char, box.source,
                                                           box.confidence, leitor.limiares):
                resolvidos += 1
            box.char, box.source, box.confidence = leitura.char, leitura.fonte, leitura.confianca
            procedencia.registrar(box, leitura.amostra)
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
