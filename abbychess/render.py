"""O render das páginas do PDF num processo à parte, para a pré-carga (§14.1, pendência do K).

O fitz segura o GIL enquanto renderiza: na thread da pré-carga, cada página nunca vista parava
a interface ~85 ms (medido no Xadrez Vitorioso). Num processo à parte a interface só espera os
bytes da página chegarem pelo cano: a maior parada caiu para ~13 ms, e o render leva ~20–30 ms
a mais por página. Só a pré-carga usa este caminho; a página pedida na hora, que a interface
espera de qualquer jeito, é renderizada no próprio processo, que é mais rápido.

O filho renderiza pelo mesmo `core.services.pdf_service.PDFService` do processo da interface:
os pixels são os mesmos. Ele guarda o PDF aberto pelo caminho, o tamanho e a data do arquivo (o
PDF trocado no mesmo lugar é lido de novo). Ele abre (spawn) na primeira pré-carga, fecha
depois de `OCIOSO_S` sem pedido e morre com o processo que o abriu. Se ele não responde em
`LIMITE_S`, cai ou não abre, `renderizar` devolve `None` (quem chama renderiza aqui, como antes),
e o filho travado é morto; depois de `FALHAS_ATE_DESISTIR` falhas seguidas, ele não é aberto de
novo na sessão. `ABBY_RENDER_EM_PROCESSO=0` o desliga (a suíte rápida, como o servidor de
leitura). Este módulo não importa Qt: é o que o filho importa.
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

#: Quanto esperar uma página: a primeira inclui abrir o processo e importar o fitz (~0,3–2 s);
#: as outras levam ~0,1 s.
LIMITE_S = 15.0
#: Falhas seguidas depois das quais o processo não é aberto de novo nesta sessão.
FALHAS_ATE_DESISTIR = 3
#: Sem pedido por este tempo, o filho fecha (e solta o PDF que guardava); o próximo o reabre.
OCIOSO_S = 120.0

#: No filho: o PDF aberto da última vez, e de que arquivo (caminho, tamanho, data).
_PDF_DO_FILHO = None
_ARQUIVO_DO_FILHO = None


def vigiar_o_pai() -> None:
    """No filho (o `initializer` de um pool `spawn`): sai quando o processo que o abriu morre,
    mesmo morto à força (sem o `atexit` dele, o filho ficava órfão). O pool do índice
    (`busca.PoolDoIndice`) também o usa."""
    pai = mp.parent_process()
    if pai is None:
        return

    def vigiar():
        from multiprocessing.connection import wait

        wait([pai.sentinel])
        os._exit(0)

    threading.Thread(target=vigiar, daemon=True, name="vigia-do-pai").start()


def _renderizar_no_filho(caminho: str, arquivo: tuple, indice: int):
    """No processo filho: `(modo, tamanho, bytes)` da página, ou `None` se ela não renderizou.
    `arquivo` é `(caminho, tamanho, data)` do PDF como o pai o vê."""
    global _PDF_DO_FILHO, _ARQUIVO_DO_FILHO
    from core.services.pdf_service import PDFService

    if _PDF_DO_FILHO is None or _ARQUIVO_DO_FILHO != arquivo:
        pdf = PDFService()
        _total, erro = pdf.load_pdf(caminho)
        if erro:
            return None
        _PDF_DO_FILHO, _ARQUIVO_DO_FILHO = pdf, arquivo
    imagem = _PDF_DO_FILHO.load_page(indice)
    if imagem is None:
        return None
    return imagem.mode, imagem.size, imagem.tobytes()


def _matar(pool: cf.ProcessPoolExecutor) -> None:
    """Fecha o pool e mata o filho, travado ou não: o `shutdown(wait=False)` sozinho deixa o
    filho travado vivo, e o `atexit` do `concurrent.futures` o espera ao sair (o programa não
    fechava). `_processes` é interno do pool, mas é o único caminho até o processo."""
    for processo in list((getattr(pool, "_processes", None) or {}).values()):
        try:
            processo.kill()
        except Exception:  # noqa: BLE001 — já morto
            pass
    pool.shutdown(wait=False, cancel_futures=True)


class RenderEmProcesso:
    """Um processo que renderiza páginas de PDF, uma por vez."""

    def __init__(self, limite_s: float = LIMITE_S, ocioso_s: float = OCIOSO_S):
        self.limite_s, self.ocioso_s = limite_s, ocioso_s
        self._pool: Optional[cf.ProcessPoolExecutor] = None
        self._trava = threading.Lock()
        self._falhas = 0
        self._fechado = False
        self._relogio: Optional[threading.Timer] = None

    @property
    def desistiu(self) -> bool:
        return self._fechado or self._falhas >= FALHAS_ATE_DESISTIR

    @property
    def aberto(self) -> bool:
        """Se o processo filho está aberto agora."""
        return self._pool is not None

    def renderizar(self, caminho: str | Path, indice: int) -> Optional[Image.Image]:
        """A página `indice` do PDF em `caminho`, renderizada no processo à parte; `None` se
        não deu (o processo não abriu, caiu, travou, ou a página não renderizou lá): quem
        chama renderiza no próprio processo e dá o erro certo."""
        try:
            estado = os.stat(caminho)
        except OSError:
            return None
        arquivo = (str(caminho), estado.st_size, estado.st_mtime_ns)
        with self._trava:
            if self.desistiu:
                return None
            if self._relogio is not None:
                self._relogio.cancel()
                self._relogio = None
            if self._pool is None:
                self._pool = cf.ProcessPoolExecutor(1, mp_context=mp.get_context("spawn"),
                                                    initializer=vigiar_o_pai)
            pool = self._pool
        try:
            resultado = pool.submit(_renderizar_no_filho, str(caminho), arquivo,
                                    indice).result(self.limite_s)
        except Exception as erro:  # noqa: BLE001 — processo quebrado, tempo esgotado, pickle
            log.warning("o render em processo da página %d falhou: %r", indice + 1, erro)
            with self._trava:
                self._falhas += 1
                if self._pool is pool:
                    self._pool = None
            _matar(pool)
            return None
        with self._trava:
            self._falhas = 0
            if self._pool is pool and not self._fechado:
                self._relogio = threading.Timer(self.ocioso_s, self._fechar_ocioso, (pool,))
                self._relogio.daemon = True
                self._relogio.start()
        if resultado is None:
            return None
        modo, tamanho, dados = resultado
        return Image.frombytes(modo, tamanho, dados)

    def _fechar_ocioso(self, pool: cf.ProcessPoolExecutor) -> None:
        with self._trava:
            if self._pool is not pool:
                return                          # um pedido novo chegou, ou já fechou
            self._pool, self._relogio = None, None
        pool.shutdown(wait=False)

    def fechar(self) -> None:
        with self._trava:
            self._fechado = True
            pool, self._pool = self._pool, None
            if self._relogio is not None:
                self._relogio.cancel()
                self._relogio = None
        if pool is not None:
            _matar(pool)


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
