"""A Galeria vista da janela (SPEC §8.2, passo C): abrir a Galeria do caractere do glifo
atual (da página ou do livro) ou de uma busca por glifo, tirar os recortes das páginas numa
thread e aplicar o que o usuário pediu nela pelo controlador da página
(`corrigir_no_livro`: várias páginas, um passo do desfazer). Também o resto da revisão vista
da janela: o Ctrl+T com a pergunta na barra (§8.4) e o esquecer da aba Padrões (§8.3). Um
mixin da `JanelaPrincipal`.
"""

from __future__ import annotations

import functools
import logging
import threading
from collections import defaultdict

import numpy as np

from abbychess import pagina as pg
from abbychess.app.galeria import Item, PainelDaGaleria
from abbychess.controlador import AVISO_LONGO_MS

log = logging.getLogger(__name__)


class GaleriaNaJanela:
    def _montar_galeria(self) -> None:
        self.galeria = PainelDaGaleria()
        self.vista.addTab(self.galeria, "Galeria")
        g = self.galeria
        g.vista.aplicar.connect(self._galeria_aplicar)
        g.vista.ensinar.connect(lambda: self._galeria_confirmar(ensinar=True))
        g.vista.so_corrigir.connect(lambda: self._galeria_confirmar(ensinar=False))
        g.escopo_mudou.connect(lambda escopo: self.abrir_galeria(self._char_da_galeria, escopo))
        g.escolhido.connect(self._galeria_escolhido)
        self._char_da_galeria = ""
        self._carga_da_galeria = 0
        self._pedido_da_galeria = 0
        self._mostrando_na_galeria = False
        self.eventos.ligar("galeria_aplicada", self._galeria_aplicada)
        self.eventos.ligar("sequencia_mudou", self._galeria_sem_ordem)
        self.eventos.ligar("historico_aplicado", self._galeria_depois_do_historico)
        self.vista.currentChanged.connect(self._aba_da_galeria)

    def _aba_da_galeria(self, _indice) -> None:
        """Abrir a aba vazia (Alt+3, o clique) mostra a Galeria do caractere do glifo atual."""
        p = self.pagina
        if (self.vista.currentWidget() is self.galeria and not self._mostrando_na_galeria
                and not self.galeria.modelo.itens and p.modelo is not None
                and p.atual is not None):
            self.abrir_galeria()

    def _ir_a_galeria(self) -> None:
        """A aba da Galeria à frente, sem o preenchimento pelo glifo atual (quem chama já vai
        mostrar outra coisa nela)."""
        self._mostrando_na_galeria = True
        try:
            self.vista.setCurrentWidget(self.galeria)
        finally:
            self._mostrando_na_galeria = False

    def _galeria_depois_do_historico(self, pids) -> None:
        """O Ctrl+Z ou o Ctrl+Y mudou páginas da Galeria: as leituras dos glifos dela voltam
        a ser as das páginas (antes, a grade ficava com a correção desfeita)."""
        p = self.pagina
        if not self.galeria.modelo.itens or p.projeto is None:
            return
        posicoes = {p.projeto.posicao_do_pid(pid) for pid in pids} - {None}
        afetadas = {i.pagina for i in self.galeria.modelo.itens} & posicoes
        leituras = {}
        for posicao in afetadas:
            pagina = p.modelo if posicao == p.indice and p.modelo is not None \
                else p.projeto.carregar_modelo(posicao)
            vivos = set(pagina.vivos)
            for item in self.galeria.modelo.itens:
                if item.pagina == posicao:
                    if item.gid not in vivos:
                        leituras[(posicao, item.gid)] = None
                        continue
                    e = pagina.box(item.gid).entry
                    leituras[(posicao, item.gid)] = (e.char, float(e.confidence), str(e.source))
        if leituras:
            self.galeria.modelo.atualizar_leituras(leituras)

    def _galeria_sem_ordem(self) -> None:
        """A ordem do livro mudou (§12.4): os glifos da Galeria citam posições de antes, e
        corrigi-los editaria a página que agora está ali. A Galeria se esvazia."""
        self._carga_da_galeria += 1              # os recortes em curso não entram
        self._pedido_da_galeria += 1             # nem a Galeria do livro que ainda junta
        if self.galeria.modelo.itens:
            self.galeria.mostrar("A ordem do livro mudou: abra a Galeria de novo", [], None)

    # ------------------------------------------------------------------
    def verificar_pagina(self) -> None:
        """Ctrl+T: com glifos a revisar, pergunta na barra (§8.4: Enter aceita, Esc não
        marca e fecha só a pergunta) antes de marcar a página como verificada."""
        pendentes = len(self.pagina.fila_da_pagina.fila()) if self.pagina.modelo is not None else 0
        if pendentes:
            indice = self.pagina.indice           # só a página da pergunta (§8.4)
            self.confirmacao.perguntar(
                f"Aceitar {pendentes} pendente(s) da página {indice + 1} como estão e marcá-la "
                "como verificada? Enter aceita · Esc não marca",
                functools.partial(self.pagina.verificar, indice))
            return
        self.pagina.verificar()

    def esquecer(self, caminhos: list) -> None:
        if self.leitor is not None:              # sem pergunta: o Ctrl+Z desfaz (§8.3)
            self.pagina.padroes_do_livro.esquecer(caminhos)

    # ------------------------------------------------------------------
    def abrir_galeria(self, char=None, escopo=None) -> None:
        """A Galeria do caractere (o do glifo atual, sem `char`), da página ou do livro."""
        p = self.pagina
        if p.modelo is None or p.projeto is None:
            return
        if char is None:
            i = p.indice_de(p.atual)
            char = p.modelo.boxes[i].entry.char if i is not None else ""
        escopo = escopo or self.galeria.escopo.currentData()
        self._char_da_galeria = char
        self._ir_a_galeria()
        nome = f"de '{char}'" if char else "dos glifos sem leitura"
        if escopo == "pagina":
            itens = [Item(p.indice, b.gid, b.entry.char, float(b.entry.confidence),
                          str(b.entry.source)) for b in p.modelo.boxes if b.entry.char == char]
            self._mostrar_na_galeria(f"Galeria {nome} na página {p.indice + 1}", itens, escopo)
            return
        quais = f"lidos como '{char}'" if char else "sem leitura"
        self.statusBar().showMessage(f"Juntando do livro os glifos {quais}…", 0)
        self._pedido_da_galeria += 1
        pedido, versao = self._pedido_da_galeria, p.operacoes.mudancas_da_sequencia
        # Com o índice ainda montando, a Galeria do livro vê só as páginas já indexadas.
        montando = "" if self.busca.pronto.is_set() else " (o índice ainda está sendo montado)"

        def chegou(achados):
            # Uma resposta velha (outro pedido depois, ou a ordem do livro mudou) não entra.
            if pedido != self._pedido_da_galeria or versao != p.operacoes.mudancas_da_sequencia:
                return
            self.statusBar().clearMessage()
            itens = [Item(a.pagina, a.gid, a.char, a.confianca, a.fonte) for a in achados
                     if a.char == char]
            self._mostrar_na_galeria(f"Galeria {nome} no livro{montando}", itens, escopo)
        self.busca.glifos(char, ao_terminar=chegou)

    def mostrar_glifos_na_galeria(self, achados, titulo: str) -> None:
        """A busca por glifo (§7.1) abre na Galeria."""
        itens = [Item(a.pagina, a.gid, a.char, a.confianca, a.fonte) for a in achados]
        self._char_da_galeria = ""
        self._ir_a_galeria()
        self._mostrar_na_galeria(titulo, itens, None)

    def _mostrar_na_galeria(self, titulo: str, itens, escopo) -> None:
        self.galeria.mostrar(titulo, itens, escopo)
        self.galeria.focar()
        self._carregar_recortes(list(self.galeria.modelo.itens))

    def _carregar_recortes(self, itens) -> None:
        """Os recortes, numa thread: a página aberta pela imagem dela, as outras pela fonte
        e pelo JSON (sem o cache, `ler_sem_migrar`); chegam pela fila da interface."""
        self._carga_da_galeria += 1
        carga, p = self._carga_da_galeria, self.pagina
        projeto, fonte, geracao = p.projeto, p.fonte, p.geracao
        vale = lambda: carga == self._carga_da_galeria and geracao == p.geracao   # noqa: E731
        aberta = (p.indice, p.imagem, p.modelo.instantaneo() if p.modelo is not None else None)
        por_pagina = defaultdict(list)
        for item in itens:
            por_pagina[item.pagina].append(item.gid)

        def rodar():
            for indice, gids in sorted(por_pagina.items(), key=lambda kv: kv[0] != aberta[0]):
                if not vale():                  # outra carga, ou outro projeto
                    return
                try:
                    if indice == aberta[0] and aberta[1] is not None and aberta[2] is not None:
                        imagem, modelo = aberta[1], aberta[2]
                    else:
                        modelo = projeto.ler_sem_migrar(indice)
                        imagem = fonte.pagina(indice) if modelo is not None else None
                    if modelo is None or imagem is None:
                        continue
                    entradas = {b.gid: b.entry for b in modelo.boxes}
                    cinza = np.asarray(imagem.convert("L"))
                    recortes = [(indice, g, pg.recorte(cinza, entradas[g]))
                                for g in gids if g in entradas]
                except Exception:
                    log.exception("os recortes da página %d para a Galeria falharam", indice + 1)
                    continue
                p.executar.na_interface(lambda r=recortes: self._recortes_chegaram(vale, r))

        threading.Thread(target=rodar, name="recortes-da-galeria", daemon=True).start()

    def _recortes_chegaram(self, vale, recortes) -> None:
        if not vale():
            return
        for indice, gid, recorte in recortes:
            self.galeria.modelo.mostrar_recorte(indice, gid, recorte)

    # ------------------------------------------------------------------
    def _galeria_aplicar(self, char: str) -> None:
        """Digitar um caractere na Galeria: ele vale para a seleção (sem ensinar)."""
        itens = self.galeria.selecionados()
        if not itens:
            return
        self.pagina.corrigir_no_livro(_por_pagina(itens), char)

    def _galeria_confirmar(self, ensinar: bool) -> None:
        """Enter (ensina) e Shift+Enter (só corrige): cada glifo com a leitura dele."""
        itens = [i for i in self.galeria.selecionados() if i.char]
        if not itens:
            return
        recortes = self.galeria.modelo.recortes
        faltam = [i for i in itens if (i.pagina, i.gid) not in recortes]
        if ensinar and faltam:
            self.statusBar().showMessage(f"{len(faltam)} recorte(s) ainda carregando: tente "
                                         "de novo em um instante.", 6000)
            return
        leituras = {(i.pagina, i.gid): i.char for i in itens}   # cada um com a dele
        self.pagina.corrigir_no_livro(
            _por_pagina(itens), leituras,
            recortes={chave: recortes[chave] for chave in leituras} if ensinar else None)

    def _galeria_aplicada(self, feitos: int, paginas: int, ensinou: bool,
                          aplicadas: dict) -> None:
        for char in set(aplicadas.values()):
            self.galeria.modelo.trocar_leitura(
                [chave for chave, c in aplicadas.items() if c == char], char)
        acao = "ensinado(s)" if ensinou else "corrigido(s)"
        self.statusBar().showMessage(f"Galeria: {feitos} glifo(s) {acao} em {paginas} "
                                     "página(s) · Ctrl+Z desfaz.", AVISO_LONGO_MS)

    def _galeria_escolhido(self, item) -> None:
        if item.pagina != self.pagina.indice:
            self.ir_para_pagina(item.pagina)
            self.pintar_texto()
        if item.gid in set(self.pagina.gids):
            self.pagina.escolher(item.gid)


def _por_pagina(itens) -> dict:
    alvos = defaultdict(list)
    for item in itens:
        alvos[item.pagina].append(item.gid)
    return dict(alvos)
