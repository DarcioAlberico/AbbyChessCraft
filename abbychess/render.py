"""O render das páginas do PDF num processo à parte, para a pré-carga (§14.1, pendência do K).

O fitz segura o GIL enquanto renderiza: na thread da pré-carga, cada página nunca vista parava
a interface ~85 ms (medido no Xadrez Vitorioso). Num processo à parte a interface só espera os
bytes da página chegarem pelo cano: a maior parada caiu para ~7 ms, e o render leva ~17 ms a
mais por página. Só a pré-carga usa este caminho; a página pedida na hora, que a interface
espera de qualquer jeito, é renderizada no próprio processo, que é mais rápido.

O filho renderiza pelo mesmo `core.services.pdf_service.PDFService` do processo da interface:
os pixels são os mesmos. Ele é aberto (spawn) na primeira pré-carga e vive até o programa
sair; se ele cai ou não abre, `renderizar` devolve `None` e quem chama renderiza aqui, como
antes. `ABBY_RENDER_EM_PROCESSO=0` o desliga (a suíte rápida, como o servidor de leitura).
Este módulo não importa Qt: é o que o filho importa.
"""

from __future__ import annotations

import concurrent.futures as cf
import logging
import multiprocessing as mp
import os
import threading
from pathlib import Path
from typing import Optional

from PIL import Image

log = logging.getLogger(__name__)

#: Quanto esperar uma página (a primeira inclui abrir o processo e importar o fitz).
LIMITE_S = 60.0
#: Falhas seguidas depois das quais o processo não é aberto de novo nesta sessão.
FALHAS_ATE_DESISTIR = 3

#: No filho: o PDF aberto da última vez (o render seguinte é quase sempre do mesmo livro).
_PDF_DO_FILHO = None


def _renderizar_no_filho(caminho: str, indice: int):
    """No processo filho: `(modo, tamanho, bytes)` da página, ou `None` se ela não renderizou."""
    global _PDF_DO_FILHO
    from core.services.pdf_service import PDFService

    if _PDF_DO_FILHO is None or _PDF_DO_FILHO.pdf_path != caminho:
        pdf = PDFService()
        _total, erro = pdf.load_pdf(caminho)
        if erro:
            return None
        _PDF_DO_FILHO = pdf
    imagem = _PDF_DO_FILHO.load_page(indice)
    if imagem is None:
        return None
    return imagem.mode, imagem.size, imagem.tobytes()


class RenderEmProcesso:
    """Um processo que renderiza páginas de PDF, uma por vez."""

    def __init__(self):
        self._pool: Optional[cf.ProcessPoolExecutor] = None
        self._trava = threading.Lock()
        self._falhas = 0
        self._fechado = False

    @property
    def desistiu(self) -> bool:
        return self._fechado or self._falhas >= FALHAS_ATE_DESISTIR

    def renderizar(self, caminho: str | Path, indice: int) -> Optional[Image.Image]:
        """A página `indice` do PDF em `caminho`, renderizada no processo à parte; `None` se
        não deu (o processo não abriu, caiu, ou a página não renderizou lá): quem chama
        renderiza no próprio processo e dá o erro certo."""
        with self._trava:
            if self.desistiu:
                return None
            if self._pool is None:
                self._pool = cf.ProcessPoolExecutor(1, mp_context=mp.get_context("spawn"))
            pool = self._pool
        try:
            resultado = pool.submit(_renderizar_no_filho, str(caminho), indice).result(LIMITE_S)
        except Exception as erro:  # noqa: BLE001 — processo quebrado, tempo esgotado, pickle
            log.warning("o render em processo da página %d falhou: %s", indice + 1, erro)
            with self._trava:
                self._falhas += 1
                if self._pool is pool:
                    self._pool = None
            pool.shutdown(wait=False, cancel_futures=True)
            return None
        with self._trava:
            self._falhas = 0
        if resultado is None:
            return None
        modo, tamanho, dados = resultado
        return Image.frombytes(modo, tamanho, dados)

    def fechar(self) -> None:
        with self._trava:
            self._fechado = True
            pool, self._pool = self._pool, None
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)


_DO_PROGRAMA: Optional[RenderEmProcesso] = None
_TRAVA_DO_PROGRAMA = threading.Lock()


def do_programa() -> Optional[RenderEmProcesso]:
    """O processo de render do programa (um só, para todos os projetos abertos), ou `None`
    com `ABBY_RENDER_EM_PROCESSO=0`. O processo só abre no primeiro `renderizar`."""
    global _DO_PROGRAMA
    if os.environ.get("ABBY_RENDER_EM_PROCESSO", "1") == "0":
        return None
    with _TRAVA_DO_PROGRAMA:
        if _DO_PROGRAMA is None:
            _DO_PROGRAMA = RenderEmProcesso()
        return _DO_PROGRAMA
