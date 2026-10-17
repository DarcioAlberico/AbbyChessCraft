"""O lote pelo servidor de leitura (SPEC §11, §4.6): ler o livro sem travar a janela.

O `CondutorDoLote` mora na thread da interface e anda página a página:

1. **Decide** se a página entra: a verificada é pulada sempre (CA-8.5); a já lida, sem
   "refazer"; e a **página aberta e suja** (com passos da sessão no desfazer) não é
   sobrescrita: fica em "reler depois" (CA-11.4).
2. **Prepara** o que fica (§4.6: os glifos `manual` e `revisado` da página já lida, os
   marcados à mão da que ainda não foi) e as áreas.
3. **Lê** fora da interface: com o servidor, uma thread renderiza a página e a pede com a
   prioridade do lote (um F5 passa na frente entre um glifo e outro, CA-11.8); sem servidor
   (os testes, as ferramentas), uma tarefa do executor lê com o leitor da interface.
4. **Grava** na thread da interface (o escritor único): confere o conflito de novo (a
   página pode ter sido aberta e editada enquanto era lida), copia a página de antes para
   `paginas/.antes-do-lote/` (no "refazer"), reconcilia os gids como o F5 e entrega ao
   gravador. O lote não entra no desfazer (§4.6).

Cancelar para a página em leitura no glifo seguinte (ela fica como estava); o que faltou
fica em `restante`, para retomar sem ler nenhuma página duas vezes (CA-11.5). As edições não
esperam o lote: ele só escreve entre uma página e outra, na thread delas.

Sem Qt: a thread da interface é a de quem chama, e o que volta da thread de leitura chega
por `executar.na_interface`.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Callable, List, Optional, Sequence

from abbychess import diagramas as dg
from abbychess import pagina as pg
from abbychess import procedencia
from abbychess import servidor_de_leitura as sl
from abbychess.livro import ResultadoDoLote
from abbychess.modelo import LIDAS, VERIFICADA, proximo_estado, reconciliar

log = logging.getLogger(__name__)

#: Por que uma página não foi lida.
JA_LIDA, VERIFICADA_PULADA, RELER_DEPOIS = "ja_lida", "verificada", "reler_depois"


class CondutorDoLote:
    """Um lote: `comecar()`, `cancelar()`; ao fim, `ao_fim(resultado)`.

    `pagina` é o `ControladorDePagina` (o projeto, a fonte, o leitor, o servidor, o executor
    e a página aberta). `ao_progresso(feitas, total, segundos_restantes)` vem a cada página.
    """

    def __init__(self, pagina, indices: Sequence[int], refazer: bool, *,
                 ao_progresso: Optional[Callable[[int, int, Optional[float]], None]] = None,
                 ao_gravar: Optional[Callable[[int], None]] = None,
                 ao_fim: Optional[Callable[[ResultadoDoLote], None]] = None):
        self.p = pagina
        self.indices = list(indices)
        self.restante = deque(self.indices)
        self.refazer = refazer
        self.ao_progresso = ao_progresso or (lambda *_: None)
        self.ao_gravar = ao_gravar or (lambda _indice: None)
        self.ao_fim = ao_fim or (lambda _resultado: None)
        self.resultado = ResultadoDoLote()
        self._cancelar = threading.Event()
        self._pedido: Optional[sl.Pedido] = None
        self._geracao = pagina.geracao
        self._feitas = 0
        #: Segundos de leitura das páginas lidas (o tempo estimado vem da média).
        self._tempos: List[float] = []
        self.terminou = False
        self.em_leitura: Optional[int] = None

    @property
    def total(self) -> int:
        return len(self.indices)

    def comecar(self) -> None:
        self.ao_progresso(0, self.total, None)
        self._seguinte()

    def cancelar(self) -> None:
        """A página em leitura para no glifo seguinte e fica como estava."""
        self._cancelar.set()
        pedido = self._pedido
        if pedido is not None and self.p.servidor is not None:
            self.p.servidor.cancelar(pedido)

    @property
    def cancelado(self) -> bool:
        return self._cancelar.is_set()

    # ------------------------------------------------------------------
    def _valendo(self) -> bool:
        """O projeto ainda é o do lote (trocar de projeto o encerra sem gravar nada)."""
        return self.p.geracao == self._geracao and not self.terminou

    def _seguinte(self) -> None:
        while self._valendo():
            if self.cancelado:
                self.resultado.cancelado = True
                self._terminar()
                return
            if not self.restante:
                self._terminar()
                return
            indice = self.restante[0]
            motivo = self._fica_de_fora(indice)
            if motivo is None:
                self._ler(indice)
                return
            self.restante.popleft()
            {JA_LIDA: self.resultado.puladas, VERIFICADA_PULADA: self.resultado.verificadas,
             RELER_DEPOIS: self.resultado.reler_depois}[motivo].append(indice)
            self._avancar()

    def _fica_de_fora(self, indice: int) -> Optional[str]:
        projeto = self.p.projeto
        estado = projeto.estado_da_pagina(indice)
        if estado == VERIFICADA:
            return VERIFICADA_PULADA
        if estado in LIDAS and not self.refazer:
            return JA_LIDA
        if self._aberta_e_suja(indice):
            return RELER_DEPOIS
        return None

    def _aberta_e_suja(self, indice: int) -> bool:
        """A página aberta com mudança do usuário nesta sessão: um passo dela no desfazer ou
        no refazer (toda edição, F5 ou desfazer entra lá; sobrescrevê-la faria o Ctrl+Z dela
        ser recusado). A gravação pendente sozinha não conta: pode ser a do próprio lote."""
        p = self.p
        modelo = p.modelo
        return modelo is not None and p.indice == indice and p.historico.toca(modelo.pid)

    def _ler(self, indice: int) -> None:
        p = self.p
        projeto, fonte, leitor, servidor = p.projeto, p.fonte, p.leitor, p._servidor_para_pedir()
        modelo = projeto.carregar_modelo(indice)
        zonas = list(modelo.zonas) if modelo is not None else projeto.carregar_zonas(indice)
        marcados = (pg.a_manter_na_releitura(modelo.boxes, modelo.estado in LIDAS)
                    if modelo is not None else [])                         # §4.6
        self.em_leitura = indice
        inicio = time.perf_counter()

        def ler(cancelado) -> sl.PaginaLida:
            imagem = fonte.pagina(indice)
            if servidor is None:
                return sl.ler_pagina(imagem, zonas, marcados, leitor, cancelado=cancelado)
            if cancelado():
                raise sl.Cancelado
            self._pedido = servidor.pedir("ler_pagina", (imagem, zonas, marcados),
                                          prioridade=sl.LOTE)
            if cancelado():                     # cancelado entre renderizar e pedir
                servidor.cancelar(self._pedido)
            lida = servidor.esperar(self._pedido)
            _registrar(lida)
            return lida

        def voltou(resultado) -> None:
            self._pedido = None
            if not self._valendo():
                return
            self._tempos.append(time.perf_counter() - inicio)
            self.em_leitura = None
            if isinstance(resultado, sl.Cancelado):
                self.resultado.cancelado = True
                self._terminar()
                return
            servidor_caiu = (isinstance(resultado, sl.ErroDoServidor)
                             and p.servidor is not None and p.servidor.desistiu)
            if servidor_caiu:                   # as outras páginas falhariam do mesmo jeito
                self.resultado.falhas[indice] = str(resultado)
                self.resultado.cancelado = True
                self._terminar()
                return
            self.restante.popleft()
            if isinstance(resultado, Exception):
                log.warning("a página %d não foi reconhecida: %s", indice + 1, resultado)
                self.resultado.falhas[indice] = str(resultado)
            else:
                self._gravar(indice, resultado)
            self._avancar()
            self._seguinte()

        if servidor is None:
            self._ler_na_fila(indice, ler, voltou)
        else:
            self._ler_numa_thread(ler, voltou)

    def _ler_numa_thread(self, ler, voltou) -> None:
        def rodar():
            try:
                resultado = ler(self._cancelar.is_set)
            except Exception as erro:  # a leitura que falhou volta como resultado
                resultado = erro
            try:
                self.p.executar.na_interface(lambda: voltou(resultado))
            except RuntimeError:  # a janela fechou no meio da página: nada a gravar
                log.info("o lote terminou com a janela já fechada")

        threading.Thread(target=rodar, name="lote", daemon=True).start()

    def _ler_na_fila(self, indice: int, ler, voltou) -> None:
        """Sem servidor: uma tarefa do executor por página (o leitor da interface é de uma
        thread por vez); uma edição pedida no meio roda entre uma página e outra."""
        def preparar():
            def trabalho(_progresso):
                try:
                    return ler(self._cancelar.is_set)
                except (sl.Cancelado, OSError, ValueError, IndexError) as erro:
                    return erro
            return trabalho, voltou

        self.p.executar(f"Lote: página {indice + 1}", preparar, falhou=lambda m: voltou(
            RuntimeError(m)))

    def _gravar(self, indice: int, lida: sl.PaginaLida) -> None:
        """O escritor único: a regra de conflito, a cópia de antes, os gids e o gravador."""
        p = self.p
        if self._aberta_e_suja(indice):          # editada enquanto o servidor a lia
            self.resultado.reler_depois.append(indice)
            return
        projeto = p.projeto
        pagina = projeto.pagina_para_editar(indice)
        if pagina.estado in LIDAS and not projeto.somente_leitura:
            projeto.guardar_antes_do_lote(pagina)                         # §4.6
        novos, dif = reconciliar(pagina.boxes, lida.boxes, pagina.alocar, procedencia.amostra_de)
        pagina.aplicar(dif, novos)
        pagina.tabuleiros = [tuple(int(v) for v in t) for t in lida.tabuleiros]
        pagina.diagramas = dg.mesclar(lida.diagramas, dg.para_caixas(pagina.tabuleiros,
                                                                     pagina.diagramas))
        pagina.estado = proximo_estado(pagina.estado, "reconhecer")
        p._gravar(pagina)
        self.resultado.lidas.append(indice)
        self.resultado.pendentes[indice] = pg.resumir(pagina.entries(), p.leitor).pendentes
        self.resultado.diagramas[indice] = sum(d.lido for d in pagina.diagramas)
        if indice == p.indice and p.modelo is None:
            p.modelo = pagina                   # a página aberta nasceu agora, no lote
        if pagina is p.modelo:
            p.atual, p.pulados, p.selecao = None, set(), set()
            p.eventos.emitir("glifos_mudaram", None)
            p.eventos.emitir("selecao_mudou")
            p.ir_ao_primeiro_pendente()
        self.ao_gravar(indice)

    def _avancar(self) -> None:
        self._feitas += 1
        restantes = len(self.restante)
        estimativa = (sum(self._tempos) / len(self._tempos) * restantes
                      if self._tempos else None)
        self.ao_progresso(self._feitas, self.total, estimativa)

    def _terminar(self) -> None:
        if self.terminou:
            return
        self.terminou = True
        self.em_leitura = None
        self.ao_fim(self.resultado)


def _registrar(lida: sl.PaginaLida) -> None:
    for box, amostra in zip(lida.boxes, lida.amostras):
        if amostra is not None:
            procedencia.registrar(box, amostra)


def resumo_do_fim(resultado: ResultadoDoLote) -> str:
    """A mensagem do fim do lote, para a barra e os Avisos."""
    partes = [f"{len(resultado.lidas)} página(s) reconhecida(s)",
              f"{resultado.total_de_pendentes} glifo(s) a revisar",
              f"{sum(resultado.diagramas.values())} diagrama(s) lido(s) em FEN"]
    if resultado.puladas:
        partes.append(f"{len(resultado.puladas)} já lida(s) pulada(s)")
    if resultado.verificadas:
        partes.append(f"{len(resultado.verificadas)} verificada(s) pulada(s)")
    if resultado.reler_depois:
        partes.append("para reler depois (abertas com mudanças): "
                      + ", ".join(str(i + 1) for i in resultado.reler_depois))
    if resultado.falhas:
        partes.append("falharam: " + ", ".join(str(i + 1) for i in resultado.falhas))
    inicio = "Lote cancelado: " if resultado.cancelado else "Lote concluído: "
    return inicio + "; ".join(partes) + "."
