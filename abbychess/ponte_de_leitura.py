"""O que vai ao leitor e ao servidor de leitura (§11) e volta, à parte do `ControladorDePagina`
(SPEC-qualidade Q-A1). O F5 e o Ctrl+Shift+R (`reconhecer`, `reconhecer_zona`: segmenta pelas
áreas, lê e acha os diagramas, mantendo o que o §4.6 manda manter), o Ctrl+R
(`reler_pendentes`), o Enter e o Ctrl+Enter (`ensinar`, `ensinar_gids`: a parte síncrona na
hora e a propagação pelos pendentes da página na fila, emendando a transação, §14.2), os
glifos aguardando leitura, que vão ao servidor só em recortes (`ler_os_aguardando`), o palpite
da rede para o glifo que ninguém leu (§9.2) e a troca que a palavra pede (`contexto`), e o
servidor: os padrões criados e apagados que vão a ele antes de cada pedido
(`sincronizar_padroes`) e o aviso de quando ele parou. A página aberta, a fila de revisão, as
edições e a gravação são do controlador (`self._p`)."""

from __future__ import annotations

import logging
from typing import Callable, Dict, Optional, Sequence, Tuple

from core.box_model import BoxEntry

from abbychess import arrumacao
from abbychess.avisos import AVISO_LONGO_MS
from abbychess import contexto
from abbychess import edicao as ed
from abbychess import historico as hs
from abbychess import pagina as pg
from abbychess import editar_boxes as eb
from abbychess import servidor_de_leitura as sl
from abbychess.leitor import FONTE_MANUAL
from abbychess.modelo import LIDAS, Pagina, pid_de

log = logging.getLogger(__name__)


class PonteDeLeitura:
    def __init__(self, p) -> None:
        self._p = p
        self.zerar()

    def zerar(self, leitor=None, servidor: Optional[sl.ServidorDeLeitura] = None) -> None:
        """Outro projeto (o `ligar`): o servidor dele começa com os padrões do `leitor`, e
        nada está sendo lido nem sugerido."""
        #: Os padrões que o servidor já tem (os deltas vão a partir deles).
        self._enviados: frozenset = (self._p.padroes_de(leitor) if servidor is not None
                                     else frozenset())
        #: Os gids aguardando cuja leitura já foi pedida ao servidor.
        self._em_leitura: set = set()
        #: Os pids das páginas com um F5 (ou Ctrl+Shift+R) entre o preparar e o pronto.
        self.lendo_no_f5: set = set()
        #: O palpite da rede para os glifos que ninguém leu (§9.2): gid -> (o `BoxEntry`
        #: de quando foi pedido, `(char, confiança)` ou None). Vale enquanto o glifo é o mesmo
        #: objeto; os pedidos em curso ficam em `_sugerindo`.
        self._sugestoes: Dict[int, Tuple[BoxEntry, Optional[Tuple[str, float]]]] = {}
        self._sugerindo: set = set()

    @property
    def lendo(self) -> bool:
        """Há glifos aguardando cuja leitura foi pedida ao servidor e ainda não chegou."""
        return bool(self._em_leitura)

    # ------------------------------------------------------------------
    # Os comandos que leem (fora da thread da interface)
    # ------------------------------------------------------------------
    def reconhecer(self) -> None:
        """F5: segmenta pelas áreas, lê e acha os diagramas. Mantém os glifos marcados à mão
        de uma página ainda não reconhecida; numa já reconhecida, os glifos novos herdam o
        gid (e as decisões) de quem estava no mesmo lugar (`modelo.reconciliar`)."""
        self._reconhecer(None)

    def reconhecer_zona(self, zona) -> None:
        """Ctrl+Shift+R: reconhece somente uma zona e conserva o restante da página."""
        self._reconhecer(zona)

    def _reconhecer(self, zona) -> None:
        if not self._p._pode_ler() or self.servidor_parado():
            return
        indice = self._p.indice
        pid = self._p.projeto.ordem.pid_em(indice)
        titulo, falha = (("Reconhecendo a página", "Reconhecer página") if zona is None
                         else ("Reconhecendo a área", "Reconhecer área"))
        avisar = self._p._falhou(falha)

        def falhou(mensagem: str) -> None:      # a página sai de `lendo_no_f5` também aqui
            self.lendo_no_f5.discard(pid)
            avisar(mensagem)

        self._p.tarefa(titulo, lambda: self._preparar_reconhecer(indice, zona), falhou=falhou)

    def _preparar_reconhecer(self, indice: int, zona=None):
        if indice != self._p.indice or not self._p._pode_ler():
            return None
        pagina = self._p._pagina_para_editar()
        # Do preparar ao pronto, o lote deixa a página para reler depois (CA-Q-C2): com o
        # servidor ele grava fora do executor, e o pronto passaria por cima da leitura dele.
        self.lendo_no_f5.add(pagina.pid)
        imagem, leitor = self._p.imagem, self._p.leitor
        zonas = [zona] if zona is not None else list(pagina.zonas)
        antes = self._p._instantaneo()
        marcados = eb.a_manter_na_releitura(pagina.boxes, pagina.estado in LIDAS)   # §4.6
        if zona is not None:
            marcados = [b for b in marcados if zona.contem_o_centro(b)]
        servidor = self.servidor_para_pedir()
        regua = self._p.projeto.resumo.regua_do_negrito(sem_o_pid=pagina.pid)

        def trabalho(progresso):
            if servidor is None:
                return sl.ler_pagina(imagem, zonas, marcados, leitor, regua_do_livro=regua,
                                     progresso=progresso)
            try:
                lida = servidor.chamar("ler_pagina", (imagem, zonas, marcados, regua),
                                       timeout=sl.TEMPO_DO_PEDIDO)
            except sl.Cancelado:                # o projeto fechou: nada a pôr
                return None
            sl.registrar_procedencia(lida.boxes, lida.amostras)
            return lida

        def pronto(lida: Optional[sl.PaginaLida]):
            self.lendo_no_f5.discard(pagina.pid)
            if lida is None:
                return
            caidas = arrumacao.aplicar_lida(pagina, lida, self._p.projeto.dados.chave_das_pecas, zona=zona,
                                            tamanho=None if imagem is None else imagem.size)
            if caidas:                          # §4.6: o que não pôde seguir os glifos novos
                self._p.eventos.emitir("resultado", "Reconhecer a página", (
                    f"Página {indice + 1}: decisões que não puderam seguir os glifos relidos: "
                    + "; ".join(caidas)))
            if pagina is self._p.modelo:
                self._p.atual, self._p.pulados, self._p.selecao = None, set(), set()
            descricao = "Reconhecer a área" if zona is not None else "Reconhecer a página"
            # O estado já é o do reconhecer (`aplicar_lida`).
            self._p._mudou(pagina, indice, descricao, antes, evento=None)
            self._p.eventos.emitir("pagina_reconhecida", indice)
            self._mostrar_o_reconhecido(pagina, leitor, zonas)

        return trabalho, pronto

    def _mostrar_o_reconhecido(self, pagina: Pagina, leitor, zonas) -> None:
        """A página reconhecida, se é a aberta: os rótulos das áreas reclassificadas, a fila no
        primeiro pendente e o resumo da leitura."""
        if pagina is not self._p.modelo:
            return
        if pagina.zonas:
            self._p.eventos.emitir("layout_mudou")
        self._p.fila_da_pagina.ir_ao_primeiro_pendente()
        resumo = pg.resumir(pagina.entries(), leitor)
        areas = f", pelas {len(zonas)} área(s) da página" if zonas else ""
        self._p._avisar(f"{resumo.boxes} boxes, {resumo.pendentes} a revisar, "
                        f"{len(pagina.tabuleiros)} diagrama(s){areas}.", AVISO_LONGO_MS)

    def reler_pendentes(self, tudo: bool = False) -> None:
        """Lê de novo os pendentes (ou todos os não manuais), com os padrões de agora."""
        if not self._p._pode_ler() or not self._p.boxes or self.servidor_parado():
            return
        indice = self._p.indice
        self._p.tarefa("Relendo", lambda: self._preparar_reler(indice, tudo),
                       falhou=self._p._falhou("Reler"))

    def _preparar_reler(self, indice: int, tudo: bool, transacao: Optional[hs.Transacao] = None):
        """`transacao` é a do esquecer de padrões que pediu esta releitura: o que ela mudar
        emenda o `depois` dela, e um Ctrl+Z desfaz as duas coisas (o Ctrl+Z espera a
        releitura: ela não é leve)."""
        pagina = self._p.modelo
        if indice != self._p.indice or pagina is None or not pagina.boxes or self._p.leitor is None:
            return None                     # a página mudou antes da vez da releitura
        imagem = self._p.imagem
        leitor, limiares = self._p.leitor, self._p.leitor.limiares
        antes = tuple(pagina.boxes)
        lidos, pendentes, nao_ler = _quem_reler(pagina, antes, limiares, tudo)
        servidor = self.servidor_para_pedir()

        def trabalho(progresso):
            if servidor is None:
                resumo = pg.ler_boxes(imagem, lidos, leitor, so_pendentes=not tudo,
                                      progresso=progresso, pendentes=pendentes, nao_ler=nao_ler)
                return lidos, resumo
            try:
                relidos, amostras, resumo = servidor.chamar(
                    "reler_boxes", (imagem, lidos, not tudo, nao_ler),
                    timeout=sl.TEMPO_DO_PEDIDO)
            except sl.Cancelado:                # o projeto fechou: nada a pôr
                return None
            sl.registrar_procedencia(relidos, amostras)
            return relidos, resumo

        def pronto(resultado):
            if resultado is None:
                return
            relidos, resumo = resultado
            foto = pagina.instantaneo()
            dif = ed.aplicar_leituras(pagina, antes, relidos)
            if not dif.vazia:
                if transacao is not None:
                    self.emendar(transacao, foto, pagina)
                else:                       # o Ctrl+R também se desfaz (§14.2)
                    self._p.historico.registrar(hs.Transacao(
                        "Reler pendentes", {pagina.pid: hs.mudanca(foto, pagina.instantaneo())}))
                    self._p.eventos.emitir("acoes_mudaram")
                self._p._gravar(pagina)
            if pagina is self._p.modelo:
                self._p.eventos.emitir("glifos_mudaram", dif.mudados)
                self._p.fila_da_pagina.ir_ao_primeiro_pendente()
                self._p._avisar(f"Relida. {resumo.pendentes} a revisar.", 6000)

        return trabalho, pronto

    def ensinar(self, char: str, em_lote: bool = False) -> None:
        """Enter: ensina o glifo em revisão (ou a seleção inteira) como `char` neste livro e
        propaga o padrão pelos pendentes da página. Ctrl+Enter (`em_lote`): no mesmo passo do
        desfazer, corrige sem ensinar os outros glifos da página com a mesma leitura que a
        palavra desmente (`contexto.lote`: o "0" de "c0l0ca" vira "o" em toda a página)."""
        if self._p.atual is None or not self._p._pode_ler():
            return
        alvos = self._p.alvos()
        lote = None
        if em_lote:
            lote = ({self._p.box(g).char for g in alvos} - {char}, char)
        self.ensinar_gids({char: alvos}, f"Ensinar '{char}'" + (" em lote" if em_lote else ""),
                          self.depois_de_ensinar(char, alvos), lote=lote)

    def ensinar_em_lote(self, char: str) -> None:
        """Ctrl+Enter no Glifo: `ensinar` com o lote."""
        self.ensinar(char, em_lote=True)

    def depois_de_ensinar(self, char: str, alvos: Sequence[int]):
        amostras = f" com {len(alvos)} amostras" if len(alvos) > 1 else ""

        def ensinou() -> None:                          # a parte síncrona: na hora
            self._p.pulados.difference_update(alvos)
            self._p.selecao = set()
            self._p.eventos.emitir("selecao_mudou")
            self._p.fila_da_pagina.ir_ao_primeiro_pendente()
            self._p._avisar(f"Padrão '{char}' ensinado{amostras}; propagando pela página…", 5000)

        def propagou(resolvidos: int) -> None:          # depois da propagação
            if resolvidos:
                self._p._avisar(f"Padrão '{char}' ensinado{amostras} e resolveu mais "
                                f"{resolvidos} na página.", 5000)
            if self._p.atual is None or self._p.atual not in self._p.fila_da_pagina.fila():
                # O glifo mostrado se resolveu: a janela avança (ou, se o usuário o escolheu,
                # mostra a leitura nova dele), a não ser que ele já esteja digitando
                # (`atual_resolvido`).
                self._p.eventos.emitir("atual_resolvido")
        return ensinou, propagou

    def ensinar_gids(self, por_char: Dict[str, Sequence[int]], descricao: str,
                     depois=None, *, juntar=None, lote=None) -> None:
        """Ensina cada grupo de gids como o caractere dele (§14.2): a parte síncrona (o
        glifo vira manual, a amostra é gravada, a cor muda) roda na hora, se nada prende o
        leitor (`_agora`); a propagação pelos pendentes da página vai para a fila, com uma
        cópia dos padrões que já tem as amostras novas, e emenda a transação deste Enter.
        `depois` é `(ensinou, propagou(resolvidos))`, ou uma função só (chamada com o número
        de resolvidos no fim). `juntar` é a chave da transação que este emenda (a correção de
        uma palavra que também ensina: um Ctrl+Z desfaz as duas). `lote` é `(leituras,
        caractere)`: os glifos de `contexto.lote` com essas leituras viram o caractere, sem
        ensinar, na parte síncrona."""
        indice = self._p.indice

        def agora():
            self._ensinar_agora(indice, por_char, descricao, depois, juntar, lote)

        if self._p._agora():
            agora()
        else:
            self._p.tarefa("Ensinando", lambda: (agora(), None)[1], falhou=self._p._falhou("Ensinar"))

    def _ensinar_agora(self, indice, por_char, descricao, depois, juntar, lote=None) -> None:
        pagina = self._p.modelo
        if indice != self._p.indice or pagina is None or self._p.leitor is None:
            return
        por_char = _os_vivos(por_char, pagina.vivos)
        if not por_char:
            self._p._avisar("O glifo a ensinar saiu da página antes da vez dele.", 6000)
            return
        feito = self._ensinar_e_corrigir(pagina, indice, por_char, lote)
        if feito is None:
            return
        antes_inst, corrigidos = feito
        transacao = self._p._mudou(pagina, indice, descricao, antes_inst, juntar=juntar)
        self._p.eventos.emitir("padroes_mudaram")
        propagou = self._depois_do_enter(pagina, depois, lote, corrigidos)
        self.propagar(pagina, indice, transacao, propagou)

    def _ensinar_e_corrigir(self, pagina: Pagina, indice: int, por_char, lote):
        """A parte síncrona do Enter na página: as amostras ensinadas (`_ensinar_as_amostras`),
        os glifos do lote corrigidos sem ensinar e as leituras na página. Devolve `(o
        instantâneo de antes, os gids corrigidos em lote)`, ou None se o ensino falhou."""
        imagem = self._p._cinza()
        antes_inst = self._p._instantaneo()
        antes = tuple(pagina.boxes)
        onde = {b.gid: i for i, b in enumerate(antes)}
        lidos = self._ensinar_as_amostras(imagem, indice, por_char, antes, onde, antes_inst)
        if lidos is None:
            return None
        corrigidos = (_corrigir_em_lote(pagina, lote, por_char, antes, onde, lidos)
                      if lote is not None else [])
        ed.aplicar_leituras(pagina, antes, lidos)
        for char, gids in por_char.items():
            self._p._tirar_a_letra_que_faltava(pagina, gids, char)
        return antes_inst, corrigidos

    def _ensinar_as_amostras(self, imagem, indice: int, por_char, antes, onde, antes_inst):
        """Ensina cada glifo como o caractere dele (uma amostra por glifo, nas cópias que
        devolve). Se uma falha (disco cheio, antivírus), nada do Enter fica: as amostras dele
        são esquecidas, o erro vai ao usuário e devolve None."""
        leitor, projeto = self._p.leitor, self._p.projeto
        lidos = [b.entry for b in antes]
        try:
            for char, gids in por_char.items():
                for gid in gids:
                    i = onde[gid]
                    lidos[i] = ed.copia(antes[i].entry)
                    pg.ensinar(imagem, lidos, i, char, leitor, projeto, indice,
                               propagar=False, gid=gid, efeito=antes[i].estilo)
        except Exception as erro:        # disco cheio, antivírus: nada do Enter fica
            for caminho in self._p.padroes() - antes_inst.padroes:
                try:
                    leitor.esquecer(caminho)
                except Exception:
                    log.exception("a amostra %s ficou sem o Enter dela", caminho)
            log.exception("o Enter falhou")
            self._p._falhou("Ensinar")(f"O padrão não foi ensinado: {erro}")
            return None
        return lidos

    def _depois_do_enter(self, pagina: Pagina, depois, lote, corrigidos):
        """Na página aberta: o `ensinou` de `depois` e o aviso do lote. Devolve o `propagou`."""
        ensinou, propagou = depois if isinstance(depois, tuple) else (None, depois)
        if ensinou is not None and pagina is self._p.modelo:
            ensinou()
        if lote is not None and pagina is self._p.modelo:
            self._p.pulados.difference_update(corrigidos)
            self._p._avisar(f"Padrão '{lote[1]}' ensinado e {len(corrigidos)} glifo(s) corrigido(s) "
                            "em lote na página; propagando…" if corrigidos else
                            "Nenhum outro glifo da página tem essa leitura numa palavra que a "
                            "desminta: só este foi ensinado.", 6000)
        return propagou

    def propagar(self, pagina: Pagina, indice: int, transacao: hs.Transacao,
                 ao_fim: Optional[Callable[[int], None]]) -> None:
        """A propagação do Enter: os pendentes da página pelos padrões do livro de agora (uma
        cópia, que já tem as amostras do Enter), fora da interface. O que ela resolve emenda
        a `transacao`; desfeita antes do fim, o resultado é descartado."""
        foto_do_leitor = self._p.leitor.para_propagar()
        imagem = self._p._cinza()

        def preparar():
            if transacao.invalidada:
                return None
            antes = tuple(pagina.boxes)
            pendentes = contexto.pendentes_da_pagina(pagina, foto_do_leitor.limiares)
            copiar = {id(b.entry) for b, p in zip(antes, pendentes) if p}
            lidos = ed.copias_para_ler(antes, lambda e: id(e) in copiar)

            def trabalho(_progresso):
                return pg.propagar_padroes(imagem, lidos, foto_do_leitor,
                                           efeitos=[b.estilo for b in antes],
                                           pendentes=pendentes)

            def pronto(resolvidos: int):
                if transacao.invalidada:
                    self._p._avisar("A propagação foi descartada: o Enter dela foi desfeito.",
                                    5000)
                    return
                foto = pagina.instantaneo()
                dif = ed.aplicar_leituras(pagina, antes, lidos)
                if not dif.vazia:
                    self.emendar(transacao, foto, pagina)
                    self._p._gravar(pagina)
                    if pagina is self._p.modelo:
                        self._p.eventos.emitir("glifos_mudaram", dif.mudados)
                    self._p.eventos.emitir("acoes_mudaram")
                if ao_fim is not None and pagina is self._p.modelo:
                    ao_fim(len(dif.mudados))
            return trabalho, pronto

        self._p.tarefa("Propagando o padrão", preparar, falhou=self._p._falhou("Propagar"), leve=True)

    def ler_os_aguardando(self) -> None:
        """Os glifos aguardando da página aberta (os modelos ficaram prontos, ou a página
        abriu): lidos fora do desfazer."""
        if self._p.modelo is not None:
            self.ler_os_aguardando_de(self._p.modelo, self._p.indice, None)

    def ler_os_aguardando_de(self, pagina: Pagina, indice: int,
                             transacao: Optional[hs.Transacao]) -> None:
        """§11: os glifos que a interface não leu (o leitor dela só tem os padrões do livro)
        vão ao servidor, só os recortes, sem passar pela fila de tarefas (a releitura não
        espera um F5 nem o lote). A resposta entra nos glifos que não mudaram desde o pedido
        e emenda a `transacao` da edição que os criou, para o refazer os trazer já lidos.
        Sem ela (a página abriu, os modelos ficaram prontos, um desfazer os trouxe de volta),
        a leitura entra fora do desfazer: ela não é decisão de ninguém, e a pré-condição do
        desfazer a aceita (`historico.lido_depois`). Com o servidor carregando (ou reabrindo
        depois de uma queda), o pedido espera na fila do filho; parado, os glifos ficam
        aguardando."""
        servidor = self._p.servidor
        if not _pode_pedir_a_leitura(servidor, self._p, pagina, indice):
            return
        antes = tuple(pagina.boxes)
        indices = _aguardando_sem_pedido(antes, self._em_leitura)
        if not indices:
            return
        entradas = [b.entry for b in antes]
        gids = {antes[i].gid for i in indices}
        self._em_leitura |= gids
        geracao = self._p.geracao
        recortes = pg.recortes_para_ler(self._p.imagem, entradas, indices)
        self.sincronizar_padroes()

        def chegou(pedido: sl.Pedido) -> None:
            if self._p.geracao != geracao:
                return                          # outro projeto
            self._em_leitura -= gids
            if not pedido.ok:
                if not pedido.cancelado:
                    log.warning("a leitura dos glifos aguardando falhou: %s", pedido.resultado)
                return
            lidos = _com_as_leituras(entradas, indices, pedido.resultado)
            foto = pagina.instantaneo()
            dif = ed.aplicar_leituras(pagina, antes, lidos)
            if dif.vazia:
                return
            if transacao is not None and not transacao.invalidada:
                self.emendar(transacao, foto, pagina)
            self._p._gravar(pagina)
            self._mostrar_os_lidos(pagina, dif)
            self._p.eventos.emitir("acoes_mudaram")

        servidor.pedir("ler_recortes", recortes,
                       ao_terminar=lambda pedido: self._p.executar.na_interface(
                           lambda: chegou(pedido)))

    def _mostrar_os_lidos(self, pagina: Pagina, dif) -> None:
        """Os glifos lidos, se a página é a aberta; sem glifo em revisão, a fila vai ao
        primeiro pendente."""
        if pagina is self._p.modelo:
            self._p.eventos.emitir("glifos_mudaram", dif.mudados)
            if self._p.atual is None:
                self._p.fila_da_pagina.ir_ao_primeiro_pendente()

    # ------------------------------------------------------------------
    # O palpite da rede para o glifo que ninguém leu (§9.2)
    # ------------------------------------------------------------------
    def sugestao_do_atual(self) -> Optional[Tuple[str, float]]:
        """O palpite da rede para o glifo em revisão, se ninguém o leu e o palpite já chegou."""
        guardada = self._sugestao_guardada(self._p.indice_de(self._p.atual))
        return guardada[1] if guardada is not None else None

    def sugestao_do_contexto(self) -> Optional[Tuple[str, bool]]:
        """(a troca que a palavra ou a linha pede, se os dois têm o mesmo desenho) para o glifo
        em revisão (`contexto.sugestoes`); None sem troca, ou se ele já foi revisado."""
        i = self._p.indice_de(self._p.atual)
        if i is None or self._p.modelo is None:
            return None
        box = self._p.modelo.boxes[i]
        if box.revisado or not box.entry.char or not contexto.volta_pelo_contexto(box.entry.source):
            return None
        sugestao = contexto.sugestoes(self._p.modelo).get(box.gid)
        if not sugestao:
            return None
        return sugestao, contexto.mesmo_desenho(box.entry.char, sugestao)

    def _sugestao_guardada(self, i: Optional[int]):
        if i is None or self._p.modelo is None:
            return None
        box = self._p.modelo.boxes[i]
        guardada = self._sugestoes.get(box.gid)
        return guardada if guardada is not None and guardada[0] is box.entry else None

    def sugerir_ao_atual(self) -> None:
        """O glifo mostrado não tem leitura: pede o palpite da rede, que vai ao painel
        (`caractere_sugerido`, com a confiança) quando chega. Com o servidor, o pedido leva os
        glifos sem leitura da página toda, e os seguintes da fila já o têm quando chegam; sem
        ele, lê-se aqui só o atual, para não pesar na interface. Uma falha fica no log: o
        palpite é ajuda, e o resto do `atual_mudou` (o painel, a seleção) tem de rodar."""
        try:
            self._pedir_palpite()
        except Exception:                  # o palpite não pode prender a navegação
            log.exception("o palpite da rede para o glifo sem leitura falhou")

    def _pedir_palpite(self) -> None:
        i = self._p.indice_de(self._p.atual)
        if not self._precisa_de_palpite(i):
            return
        servidor, geracao = self._p.servidor, self._p.geracao
        if not _ha_quem_sugira(servidor, self._p.leitor):
            return
        antes = tuple(self._p.modelo.boxes)
        # Guarda-se só o da página aberta (os gids levam a página, e os outros não voltam a
        # valer sem um novo pedido).
        self._sugestoes = _so_os_da_pagina(self._sugestoes, pid_de(antes[i].gid))
        indices = self._a_sugerir(antes, i, servidor)
        recortes = pg.recortes_para_ler(self._p._cinza(), [b.entry for b in antes], indices)
        gids = {antes[k].gid for k in indices}

        def chegou(sugestoes) -> None:
            for k, sugestao in zip(indices, sugestoes):
                self._sugestoes[antes[k].gid] = (antes[k].entry, sugestao)
            if (sugestao := self.sugestao_do_atual()) is not None:
                self._p.eventos.emitir("caractere_sugerido", *sugestao)

        if servidor is None:
            chegou([self._p.leitor.sugerir(recorte, altura) for recorte, altura in recortes])
            return
        self._sugerindo |= gids

        def terminou(pedido: sl.Pedido) -> None:
            if self._p.geracao != geracao:
                return                          # outro projeto
            self._sugerindo -= gids
            if pedido.ok:
                chegou(pedido.resultado)
            elif not pedido.cancelado:
                log.warning("o palpite da rede para os glifos sem leitura falhou: %s",
                            pedido.resultado)

        servidor.pedir("sugerir_recortes", recortes,
                       ao_terminar=lambda pedido: self._p.executar.na_interface(
                           lambda: terminou(pedido)))

    def _precisa_de_palpite(self, i: Optional[int]) -> bool:
        """O glifo `i` da página aberta não tem leitura, nem palpite guardado ou pedido."""
        return not (i is None or self._p.imagem is None
                    or not pg.sem_leitura(self._p.modelo.boxes[i].entry)
                    or self._sugestao_guardada(i) is not None or self._p.atual in self._sugerindo)

    def _a_sugerir(self, antes, i: int, servidor) -> list:
        """Os glifos do pedido: sem o servidor, só o atual; com ele, os da página toda sem
        leitura, sem palpite guardado nem pedido."""
        if servidor is None:
            return [i]
        return [k for k, b in enumerate(antes) if pg.sem_leitura(b.entry)
                and b.gid not in self._sugerindo and self._sugestao_guardada(k) is None]

    def servidor_parado(self) -> bool:
        """O servidor desistiu (caiu duas vezes): o comando que lê avisa e não roda."""
        if self._p.servidor is None or not self._p.servidor.parado:
            return False
        self._p._avisar("O servidor de leitura parou. Reabra o projeto (Projeto › Abrir) para "
                        "voltar a ler as páginas.", AVISO_LONGO_MS)
        return True

    def servidor_para_pedir(self) -> Optional[sl.ServidorDeLeitura]:
        """O servidor, com os padrões de agora já mandados (os deltas valem a partir do
        pedido seguinte, §11); None sem servidor."""
        self.sincronizar_padroes()
        return self._p.servidor

    def sincronizar_padroes(self) -> None:
        """Manda ao servidor as amostras criadas e apagadas desde a última vez."""
        if self._p.servidor is None or self._p.leitor is None:
            return
        agora = self._p.padroes()
        criados, apagados = agora - self._enviados, self._enviados - agora
        if criados or apagados:
            padroes = self._p.leitor.padroes
            self._p.servidor.enviar_padroes([(c, padroes.altura_de(c), padroes.efeito_de(c))
                                             for c in sorted(criados)],
                                            sorted(apagados))
            self._enviados = agora

    def emendar(self, transacao: hs.Transacao, antes: Pagina, pagina: Pagina) -> None:
        mais = hs.mudanca(antes, pagina.instantaneo())
        if pagina.pid in transacao.paginas:
            hs.emendar(transacao.paginas[pagina.pid], mais)
        else:
            transacao.paginas[pagina.pid] = mais
        self._p.historico.emendou(transacao)


def _os_vivos(por_char: Dict[str, Sequence[int]], vivos) -> Dict[str, list]:
    """Os gids de cada caractere que ainda estão na página; sem os caracteres que ficaram sem
    nenhum."""
    por_char = {c: [g for g in gids if g in vivos] for c, gids in por_char.items()}
    return {c: gids for c, gids in por_char.items() if gids}


def _corrigir_em_lote(pagina: Pagina, lote, por_char, antes, onde, lidos) -> list:
    """O Ctrl+Enter: os glifos da página com as leituras do `lote` que a palavra desmente
    (`contexto.lote`) viram o caractere dele nas cópias `lidos`, sem ensinar; devolve os gids."""
    lidas, novo = lote
    ensinados = {g for gids in por_char.values() for g in gids}
    corrigidos = []
    for gid in contexto.lote(pagina, lidas, novo, ensinados):
        i = onde[gid]
        lidos[i] = ed.copia(antes[i].entry)
        pg.confirmar(lidos, i, novo)
        corrigidos.append(gid)
    return corrigidos


def _ha_quem_sugira(servidor, leitor) -> bool:
    """O palpite tem quem o dê: o servidor de pé, ou, sem ele, a rede do leitor."""
    if servidor is None:
        return getattr(leitor, "rede", None) is not None
    return not servidor.parado


def _so_os_da_pagina(sugestoes: dict, pid: int) -> dict:
    """Os palpites guardados dos glifos da página `pid`."""
    return {g: v for g, v in sugestoes.items() if pid_de(g) == pid}


def _quem_reler(pagina, antes, limiares, tudo: bool) -> tuple:
    """(as cópias a ler, os pendentes, ou None com `tudo`, as posições a não ler). O revisado não
    é relido, nem com `tudo`: decidido não volta (D-5)."""
    nao_ler = [i for i, b in enumerate(antes) if b.revisado]
    if tudo:
        fora = {id(antes[i].entry) for i in nao_ler}
        return (ed.copias_para_ler(antes, lambda e: e.source != FONTE_MANUAL
                                   and id(e) not in fora), None, nao_ler)
    pendentes = contexto.pendentes_da_pagina(pagina, limiares)
    copiar = {id(b.entry) for b, p in zip(antes, pendentes) if p}
    return ed.copias_para_ler(antes, lambda e: id(e) in copiar), pendentes, nao_ler


def _pode_pedir_a_leitura(servidor, p, pagina: Pagina, indice: int) -> bool:
    """O servidor de pé e a página ainda aberta: os aguardando podem ir a ele."""
    return not (servidor is None or servidor.parado
                or pagina is not p.modelo or indice != p.indice)


def _aguardando_sem_pedido(antes, em_leitura: set) -> list:
    """Os glifos aguardando leitura cujo pedido ainda não foi feito."""
    return [i for i, b in enumerate(antes)
            if pg.aguardando(b.entry) and b.gid not in em_leitura]


def _com_as_leituras(entradas, indices, leituras) -> list:
    """As entradas com cópias lidas nos `indices` (as outras, as mesmas)."""
    lidos = list(entradas)
    for i, leitura in zip(indices, leituras):
        lidos[i] = ed.copia(entradas[i])
        pg.por_leitura(lidos[i], leitura)
    return lidos
