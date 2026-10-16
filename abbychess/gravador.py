"""O gravador das páginas (SPEC §4.3): uma thread só, que serializa e grava.

A interface não grava. Ela entrega ao gravador um **instantâneo imutável** da página
(`Pagina.instantaneo`, tuplas dos objetos, que desde o 2a ninguém muda no lugar) e segue.
O gravador junta as entregas da mesma página: a primeira marca a página como suja e
agenda a gravação para dali a `ATRASO` segundos, e as seguintes só trocam o instantâneo
(coalescência). Cem edições em 400 ms são uma gravação.

Uma gravação que falha não perde a página: ela continua suja, a falha é avisada por
`ao_falhar(pid, erro)` uma vez por sequência de falhas, e o gravador tenta de novo com
espera crescente (até `ESPERA_MAXIMA`), ou na hora quando chega um instantâneo novo dela.
`descarregar` grava tudo agora e espera; fechar o projeto descarrega e para a thread.

Sem Qt. `ao_falhar` e `ao_gravar` são chamados da thread do gravador.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, Optional

log = logging.getLogger(__name__)

#: A coalescência: quanto o gravador espera, depois da primeira mudança, para gravar.
ATRASO = 0.5
#: A espera mais longa entre duas tentativas de uma página que não grava.
ESPERA_MAXIMA = 30.0


class Gravador:
    """Grava instantâneos de página numa thread própria, com coalescência por página."""

    def __init__(self, gravar: Callable[[object], None], *, atraso: float = ATRASO,
                 ao_falhar: Optional[Callable[[int, BaseException], None]] = None,
                 ao_gravar: Optional[Callable[[int], None]] = None,
                 relogio: Callable[[], float] = time.monotonic, nome: str = "gravador"):
        self._gravar = gravar
        self.atraso = atraso
        self.ao_falhar = ao_falhar
        self.ao_gravar = ao_gravar
        self._relogio = relogio
        self._cond = threading.Condition()
        #: pid -> o instantâneo mais novo ainda não gravado.
        self._pendentes: Dict[int, object] = {}
        #: pid -> quando gravar.
        self._prazos: Dict[int, float] = {}
        #: pid -> quantas falhas seguidas (a espera cresce com elas).
        self._falhas: Dict[int, int] = {}
        #: pid -> quantas tentativas já houve (o `descarregar` sabe quem já tentou).
        self._tentativas: Dict[int, int] = {}
        self._gravando: Optional[int] = None
        self._parar = False
        #: Quantas gravações deram certo (os testes de coalescência contam por aqui).
        self.gravacoes = 0
        self._thread = threading.Thread(target=self._rodar, name=nome, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    # O lado da interface
    # ------------------------------------------------------------------
    def agendar(self, pid: int, instantaneo) -> None:
        """A página `pid` mudou: grava `instantaneo` dentro de `atraso` segundos."""
        with self._cond:
            if self._parar:
                raise RuntimeError("o gravador já foi fechado")
            self._pendentes[pid] = instantaneo
            if pid in self._falhas:             # estava falhando: tenta logo com o novo
                self._prazos[pid] = self._relogio()
            else:
                self._prazos.setdefault(pid, self._relogio() + self.atraso)
            self._cond.notify_all()

    def pendente(self, pid: int) -> bool:
        with self._cond:
            return pid in self._pendentes or self._gravando == pid

    @property
    def sujas(self) -> set:
        """As páginas com mudança ainda não gravada (inclusive as que falharam)."""
        with self._cond:
            sujas = set(self._pendentes)
            if self._gravando is not None:
                sujas.add(self._gravando)
            return sujas

    @property
    def falhando(self) -> set:
        with self._cond:
            return set(self._falhas)

    def descarregar(self, limite: Optional[float] = None) -> bool:
        """Grava agora tudo o que está pendente e espera. Devolve se ficou tudo gravado
        (falso se alguma página falhou de novo ou o `limite`, em segundos, venceu)."""
        fim = None if limite is None else time.monotonic() + limite
        with self._cond:
            agora = self._relogio()
            for pid in self._pendentes:
                self._prazos[pid] = agora
            inicio = dict(self._tentativas)
            self._cond.notify_all()
            while True:
                restantes = set(self._pendentes)
                if self._gravando is not None:
                    restantes.add(self._gravando)
                if not restantes:
                    return True
                if self._gravando is None and all(
                        p in self._falhas and self._tentativas.get(p, 0) > inicio.get(p, 0)
                        for p in restantes):
                    return False                # cada uma que sobrou já falhou de novo
                espera = 0.05 if fim is None else min(0.05, fim - time.monotonic())
                if espera <= 0:
                    return False
                self._cond.wait(espera)

    def fechar(self, limite: Optional[float] = 30.0) -> bool:
        """Descarrega e para a thread. Devolve se ficou tudo gravado."""
        gravou = self.descarregar(limite)
        with self._cond:
            self._parar = True
            self._cond.notify_all()
        self._thread.join(limite)
        return gravou

    # ------------------------------------------------------------------
    # A thread
    # ------------------------------------------------------------------
    def _proximo(self) -> Optional[int]:
        """O pid a gravar agora; espera dentro da condição até haver um (None: parar)."""
        while True:
            if self._parar:
                return None
            agora = self._relogio()
            prontos = [p for p in self._pendentes if self._prazos.get(p, agora) <= agora]
            if prontos:
                return min(prontos, key=lambda p: self._prazos.get(p, agora))
            futuros = [self._prazos[p] for p in self._pendentes if p in self._prazos]
            # O relógio pode ser falso nos testes: a espera tem teto, para ele andar.
            self._cond.wait(None if not self._pendentes
                            else min(0.05, max(0.0, min(futuros, default=agora) - agora)))

    def _rodar(self) -> None:
        while True:
            with self._cond:
                pid = self._proximo()
                if pid is None:
                    return
                instantaneo = self._pendentes.pop(pid)
                self._prazos.pop(pid, None)
                self._gravando = pid
            erro: Optional[BaseException] = None
            try:
                self._gravar(instantaneo)
            except Exception as falha:           # disco cheio, sem permissão, antivírus
                erro = falha
                log.exception("a página p%d não foi gravada", pid)
            with self._cond:
                self._gravando = None
                self._tentativas[pid] = self._tentativas.get(pid, 0) + 1
                seguidas = 0
                if erro is None:
                    self.gravacoes += 1
                    self._falhas.pop(pid, None)
                else:
                    seguidas = self._falhas.get(pid, 0) + 1
                    self._falhas[pid] = seguidas
                    if pid not in self._pendentes:    # nada mais novo: tenta o mesmo depois
                        self._pendentes[pid] = instantaneo
                        self._prazos[pid] = self._relogio() + min(
                            ESPERA_MAXIMA, self.atraso * 2 ** seguidas)
                self._cond.notify_all()
            if erro is None:
                if self.ao_gravar is not None:
                    self.ao_gravar(pid)
            elif seguidas == 1 and self.ao_falhar is not None:
                self.ao_falhar(pid, erro)
