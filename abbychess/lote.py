"""O lote (SPEC §11, §4.6): ler o livro sem travar a janela, com a janela como escritor único.

O `CondutorDoLote` mora na thread de quem chama (a da interface) e anda página a página:

1. **Decide** se a página entra: a verificada é pulada sempre (CA-8.5); a já lida, sem
   "refazer"; e a **página aberta e suja** (com passos da sessão no desfazer) não é
   sobrescrita: fica em "reler depois" (CA-11.4).
2. **Prepara** o que fica (§4.6: os glifos `manual` e `revisado` da página já lida, os
   marcados à mão da que ainda não foi), as áreas e a versão da página no desfazer.
3. **Lê** fora da interface: com o servidor, uma thread renderiza a página e a pede com a
   prioridade do lote (um F5 passa na frente entre um glifo e outro, CA-11.8); sem servidor
   (os testes, as ferramentas), uma tarefa do executor lê com o leitor da interface.
4. **Grava** na thread da interface: a página que foi verificada enquanto era lida é pulada;
   a que o usuário mudou desde o pedido (aberta ou não: a versão dela no desfazer andou) vai
   para "reler depois"; senão, a página de antes vai para `paginas/.antes-do-lote/` (no
   "refazer"), os gids se reconciliam como no F5 e a página vai ao gravador. O lote não
   entra no desfazer (§4.6).

Cancelar para a página em leitura no glifo seguinte (ela fica como estava); o que faltou
fica em `restante`, para retomar sem ler nenhuma página duas vezes (CA-11.5).

Sem Qt. Com o executor síncrono (as ferramentas, `livro.reconhecer_paginas`), cada página
termina dentro da chamada que a pediu; o laço de `_seguinte` não se aninha, para um livro
de centenas de páginas não estourar a pilha.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

from abbychess import diagramas as dg
from abbychess import lances as lc
from abbychess import pagina as pg
from abbychess import procedencia
from abbychess import servidor_de_leitura as sl
from abbychess.controlador import TEMPO_DO_PEDIDO
from abbychess.modelo import (IOU_DA_RELEITURA, LIDAS, VERIFICADA, descrever_caidas,
                              proximo_estado, reconciliar)

log = logging.getLogger(__name__)

#: Por que uma página não foi lida.
JA_LIDA, VERIFICADA_PULADA, RELER_DEPOIS = "ja_lida", "verificada", "reler_depois"
#: De quanto em quanto tempo a thread do lote olha se o lote foi cancelado enquanto espera o
#: servidor, e quanto ela espera a resposta de um cancelamento antes de desistir da página.
VOLTA_DA_ESPERA, PRAZO_DO_CANCELAMENTO = 0.5, 30.0


@dataclass
class ResultadoDoLote:
    #: As páginas lidas e gravadas neste lote, em ordem.
    lidas: List[int] = field(default_factory=list)
    #: As que já estavam lidas e ficaram como estavam.
    puladas: List[int] = field(default_factory=list)
    #: As verificadas, puladas mesmo com "refazer" (CA-8.5).
    verificadas: List[int] = field(default_factory=list)
    #: As que o usuário mudou nesta sessão, que o lote não sobrescreveu (CA-11.4).
    reler_depois: List[int] = field(default_factory=list)
    #: Página -> motivo, para a que não abriu ou não segmentou.
    falhas: Dict[int, str] = field(default_factory=dict)
    #: Página -> quantos glifos ficaram para revisar.
    pendentes: Dict[int, int] = field(default_factory=dict)
    #: Página -> quantos diagramas foram lidos em FEN.
    diagramas: Dict[int, int] = field(default_factory=dict)
    #: Página -> as decisões que não puderam seguir os glifos relidos (§4.6).
    caidas: Dict[int, List[str]] = field(default_factory=dict)
    cancelado: bool = False
    #: O lote parou porque o servidor de leitura desistiu (a página em curso fica para
    #: retomar, e não conta como falha).
    servidor_parou: bool = False

    @property
    def total_de_pendentes(self) -> int:
        return sum(self.pendentes.values())


@dataclass
class _Pedida:
    """O que o lote guardou de uma página ao pedir a leitura dela."""

    indice: int
    pid: Optional[int]
    versao: int
    inicio: float


class CondutorDoLote:
    """Um lote: `comecar()`, `cancelar()`; ao fim, `ao_fim(resultado)`.

    `pagina` é o `ControladorDePagina` (o projeto, a fonte, o leitor, o servidor, o executor
    e a página aberta). `ao_progresso(feitas, total, segundos_restantes)` vem a cada página;
    `cancelado()` é um pedido de parar vindo de fora (as ferramentas), além de `cancelar`.
    """

    def __init__(self, pagina, indices: Sequence[int], refazer: bool, *,
                 ao_progresso: Optional[Callable[[int, int, Optional[float]], None]] = None,
                 ao_gravar: Optional[Callable[[int], None]] = None,
                 ao_fim: Optional[Callable[[ResultadoDoLote], None]] = None,
                 cancelado: Callable[[], bool] = lambda: False,
                 forcar: Sequence[int] = ()):
        self.p = pagina
        self.indices = list(indices)
        self.restante = deque(self.indices)
        self.refazer = refazer
        #: As páginas que o usuário mandou ler de novo de qualquer jeito (as que ficaram para
        #: reler depois, confirmadas no Retomar): lidas mesmo já lidas, e mesmo abertas com
        #: passos no desfazer (a confirmação disse que o Ctrl+Z delas deixa de valer).
        self.forcar = set(forcar)
        self.ao_progresso = ao_progresso or (lambda *_: None)
        self.ao_gravar = ao_gravar or (lambda _indice: None)
        self.ao_fim = ao_fim or (lambda _resultado: None)
        self._de_fora = cancelado
        self.resultado = ResultadoDoLote()
        self._cancelar = threading.Event()
        self._pedido: Optional[sl.Pedido] = None
        self._geracao = pagina.geracao
        self._feitas = 0
        #: Segundos de leitura das páginas lidas (o tempo estimado vem da média).
        self._tempos: List[float] = []
        self.terminou = False
        self.em_leitura: Optional[int] = None
        self._no_laco = False
        self._de_novo = False

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
        return self._cancelar.is_set() or self._de_fora()

    # ------------------------------------------------------------------
    def _valendo(self) -> bool:
        """O projeto ainda é o do lote (trocar de projeto o encerra sem gravar nada)."""
        return self.p.geracao == self._geracao and not self.terminou

    def _seguinte(self) -> None:
        """A próxima página. Chamado de dentro de uma página que terminou na hora (o executor
        síncrono), só marca que há mais: o laço de fora continua, sem aninhar."""
        if self._no_laco:
            self._de_novo = True
            return
        self._no_laco = True
        try:
            self._de_novo = True
            while self._de_novo:
                self._de_novo = False
                self._um_passo()
        finally:
            self._no_laco = False

    def _um_passo(self) -> None:
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
            self._pular(indice, motivo)

    def _pular(self, indice: int, motivo: str) -> None:
        self.restante.popleft()
        {JA_LIDA: self.resultado.puladas, VERIFICADA_PULADA: self.resultado.verificadas,
         RELER_DEPOIS: self.resultado.reler_depois}[motivo].append(indice)
        self._avancar()

    def _fica_de_fora(self, indice: int) -> Optional[str]:
        estado = self.p.projeto.estado_da_pagina(indice)
        if estado == VERIFICADA:
            return VERIFICADA_PULADA
        forcada = indice in self.forcar
        if estado in LIDAS and not (self.refazer or forcada):
            return JA_LIDA
        if not forcada and self._aberta_e_suja(indice):
            return RELER_DEPOIS
        return None

    def _aberta_e_suja(self, indice: int) -> bool:
        """Antes de ler: a página aberta com mudança do usuário nesta sessão, um passo dela no
        desfazer ou no refazer (toda edição, F5 ou desfazer entra lá; sobrescrevê-la faria o
        Ctrl+Z dela ser recusado). A gravação pendente sozinha não conta: pode ser a do
        próprio lote. As fechadas com passos assim são lidas (§11 só protege a aberta); o que
        protege qualquer página é `_mudou_durante`: a mudança enquanto ela era lida."""
        p = self.p
        modelo = p.modelo
        return modelo is not None and p.indice == indice and p.historico.toca(modelo.pid)

    def _ler(self, indice: int) -> None:
        p = self.p
        projeto, fonte, leitor, servidor = p.projeto, p.fonte, p.leitor, p._servidor_para_pedir()
        # Na janela, só o pid e a versão (sem ler o JSON da página: isso, e o que o §4.6
        # mantém, vão para a thread da leitura). Uma mudança do usuário depois daqui sobe a
        # versão, e `_mudou_durante` a pega.
        pid = projeto.pid_da_pagina(indice)
        pedida = _Pedida(indice, pid, p.historico.versao(pid), time.perf_counter())
        self.em_leitura = indice

        def ler(cancelado) -> sl.PaginaLida:
            modelo = projeto.carregar_modelo(indice)
            zonas = list(modelo.zonas) if modelo is not None else projeto.carregar_zonas(indice)
            marcados = (pg.a_manter_na_releitura(modelo.boxes, modelo.estado in LIDAS)
                        if modelo is not None else [])                     # §4.6
            imagem = fonte.pagina(indice)
            if servidor is None:
                return sl.ler_pagina(imagem, zonas, marcados, leitor, cancelado=cancelado)
            return self._ler_no_servidor(servidor, (imagem, zonas, marcados), cancelado)

        def voltou(resultado) -> None:
            self._pedido = None
            if not self._valendo():
                return
            self._voltou(pedida, resultado)
            # Com o servidor, a página seguinte começa num passo à parte do laço de eventos: a
            # janela responde entre gravar esta e preparar aquela. Sem ele, a leitura é uma
            # tarefa da fila, que já dá a vez.
            agendar = getattr(self.p.executar, "na_interface", None)
            if agendar is None or servidor is None:
                self._seguinte()
            else:
                agendar(self._seguinte)

        if servidor is None:
            self._ler_na_fila(indice, ler, voltou)
        else:
            self._ler_numa_thread(ler, voltou)

    def _ler_no_servidor(self, servidor, argumentos, cancelado) -> sl.PaginaLida:
        """Na thread do lote: pede a página e espera, olhando o cancelamento; um pedido
        cancelado sempre responde, mas, se a resposta não vier no prazo, a página é dada
        por cancelada (ela fica como estava)."""
        if cancelado():
            raise sl.Cancelado
        pedido = self._pedido = servidor.pedir("ler_pagina", argumentos, prioridade=sl.LOTE)
        cancelou_em, pedido_em = None, time.monotonic()
        while not pedido.feito.wait(VOLTA_DA_ESPERA):
            if cancelado() and cancelou_em is None:
                servidor.cancelar(pedido)
                cancelou_em = time.monotonic()
            if cancelou_em is not None and time.monotonic() - cancelou_em > PRAZO_DO_CANCELAMENTO:
                raise sl.Cancelado
            if time.monotonic() - pedido_em > TEMPO_DO_PEDIDO:     # um filho travado
                servidor.cancelar(pedido)
                raise TimeoutError(f"o servidor não leu a página em {TEMPO_DO_PEDIDO:.0f} s")
        lida = servidor.esperar(pedido, 0)
        sl.registrar_procedencia(lida.boxes, lida.amostras)
        return lida

    def _voltou(self, pedida: _Pedida, resultado) -> None:
        indice = pedida.indice
        self._tempos.append(time.perf_counter() - pedida.inicio)
        self.em_leitura = None
        p = self.p
        if isinstance(resultado, sl.Cancelado):
            self.resultado.cancelado = True
            self._terminar()
            return
        if isinstance(resultado, sl.ErroDoServidor) and p.servidor is not None \
                and p.servidor.desistiu:
            # As outras páginas falhariam do mesmo jeito: o lote para, e o que faltou (esta
            # página também) fica para retomar depois de reabrir o projeto.
            self.resultado.servidor_parou = True
            self.resultado.cancelado = True
            self._terminar()
            return
        if isinstance(resultado, Exception):
            log.warning("a página %d não foi reconhecida: %s", indice + 1, resultado)
            self.restante.popleft()
            self.resultado.falhas[indice] = str(resultado)
            self._avancar()
            return
        motivo = self._mudou_durante(pedida)
        if motivo is not None:
            self._pular(indice, motivo)
            return
        self.restante.popleft()
        self._gravar(indice, resultado)
        self._avancar()

    def _mudou_durante(self, pedida: _Pedida) -> Optional[str]:
        """A página verificada, ou mudada pelo usuário, enquanto era lida (aberta ou não)."""
        p = self.p
        if p.projeto.estado_da_pagina(pedida.indice) == VERIFICADA:
            return VERIFICADA_PULADA
        modelo = p.projeto.carregar_modelo(pedida.indice)
        pid = modelo.pid if modelo is not None else None
        if pid != pedida.pid or p.historico.versao(pid) != pedida.versao:
            return RELER_DEPOIS
        return None

    def _ler_numa_thread(self, ler, voltou) -> None:
        def rodar():
            try:
                resultado = ler(lambda: self.cancelado)
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
                    return ler(lambda: self.cancelado)
                except (sl.Cancelado, OSError, ValueError, IndexError) as erro:
                    return erro
            return trabalho, voltou

        self.p.executar(f"Lote: página {indice + 1}", preparar,
                        falhou=lambda mensagem: voltou(RuntimeError(mensagem)))

    def _gravar(self, indice: int, lida: sl.PaginaLida) -> None:
        """O escritor único: a cópia de antes, os gids e o gravador."""
        p = self.p
        projeto = p.projeto
        pagina = projeto.pagina_para_editar(indice)
        if (self.refazer or indice in self.forcar) and pagina.estado in LIDAS \
                and not projeto.somente_leitura:
            projeto.guardar_antes_do_lote(pagina)                         # §4.6
        de_antes = list(pagina.boxes)
        from abbychess.modelo import Estilo

        estilos = {id(entry): Estilo(negrito=negrito)
                   for entry, negrito in zip(lida.boxes, lida.negritos)
                   if negrito is not None}
        novos, dif = reconciliar(pagina.boxes, lida.boxes, pagina.alocar, procedencia.amostra_de,
                                 estilo_de=lambda entry: estilos.get(id(entry)),
                                 iou_minimo=IOU_DA_RELEITURA)
        pagina.aplicar(dif, novos)
        if dif.caidas:
            self.resultado.caidas[indice] = descrever_caidas(dif.caidas, de_antes)
        pagina.tabuleiros = [tuple(int(v) for v in t) for t in lida.tabuleiros]
        pagina.diagramas = dg.com_ids(dg.mesclar(lida.diagramas, dg.para_caixas(pagina.tabuleiros,
                                                                     pagina.diagramas)))
        pagina.diagramas = lc.validar_pagina(pagina, projeto.dados.idioma)
        pagina.estado = proximo_estado(pagina.estado, "reconhecer")
        p._gravar(pagina)
        self.resultado.lidas.append(indice)
        self.resultado.pendentes[indice] = pg.resumir(
            [b.entry for b in pagina.boxes if not b.revisado], p.leitor).pendentes
        self.resultado.diagramas[indice] = sum(d.lido for d in pagina.diagramas)
        if indice == p.indice and p.modelo is None and p.imagem is not None:
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


def _paginas(indices) -> str:
    """As páginas como o usuário as vê, com as seguidas em faixa: "2–51, 60"."""
    faixas, numeros = [], sorted({int(i) + 1 for i in indices})
    for n in numeros:
        if faixas and n == faixas[-1][1] + 1:
            faixas[-1][1] = n
        else:
            faixas.append([n, n])
    return ", ".join(f"{a}–{b}" if b > a else str(a) for a, b in faixas)


def tem_detalhe(resultado: ResultadoDoLote) -> bool:
    """O fim do lote tem algo a conferir (vai aos Avisos); o lote limpo não."""
    return bool(resultado.cancelado or resultado.reler_depois or resultado.falhas
                or resultado.caidas)


def resumo_do_fim(resultado: ResultadoDoLote) -> str:
    """A mensagem curta do fim do lote, para a barra (o detalhe vai aos Avisos)."""
    if resultado.servidor_parou:
        inicio = "Lote interrompido (o servidor de leitura parou)"
    elif resultado.cancelado:
        inicio = "Lote cancelado"
    else:
        inicio = "Lote concluído"
    partes = [f"{len(resultado.lidas)} lida(s)", f"{resultado.total_de_pendentes} a revisar"]
    if resultado.reler_depois:
        partes.append(f"{len(resultado.reler_depois)} para reler depois")
    if resultado.falhas:
        partes.append(f"{len(resultado.falhas)} falharam")
    return f"{inicio}: " + ", ".join(partes) + "."


def detalhe_do_fim(resultado: ResultadoDoLote) -> str:
    """O que os Avisos guardam do fim do lote: as páginas de cada caso."""
    linhas = [resumo_do_fim(resultado),
              f"Lidas: {_paginas(resultado.lidas) or 'nenhuma'}; "
              f"{sum(resultado.diagramas.values())} diagrama(s) lido(s) em FEN."]
    if resultado.puladas:
        linhas.append(f"Já lidas, puladas: {_paginas(resultado.puladas)}.")
    if resultado.verificadas:
        linhas.append(f"Verificadas, puladas: {_paginas(resultado.verificadas)}.")
    if resultado.reler_depois:
        linhas.append("Para reler depois (mudadas por você nesta sessão, ou enquanto o lote "
                      f"as lia): {_paginas(resultado.reler_depois)}.")
    if resultado.falhas:
        linhas.append("Falharam: " + "; ".join(
            f"{i + 1} ({(motivo.splitlines() or ['sem motivo'])[0]})"
            for i, motivo in resultado.falhas.items()) + ".")
    for indice, caidas in resultado.caidas.items():
        linhas.append(f"Página {indice + 1}, decisões que não seguiram os glifos relidos: "
                      + "; ".join(caidas) + ".")
    return "\n".join(linhas)
