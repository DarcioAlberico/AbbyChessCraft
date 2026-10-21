"""A Galeria vista da janela (SPEC §8.2, passo C): abrir a Galeria do caractere do glifo
atual (da página ou do livro) ou de uma busca por glifo, tirar os recortes das páginas numa
thread e aplicar o que o usuário pediu nela pelo controlador da página
(`corrigir_no_livro`: várias páginas, um passo do desfazer). Um mixin da `JanelaPrincipal`.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict

from abbychess import pagina as pg
from abbychess.app.galeria import Item, PainelDaGaleria

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
        self._galeria_pendente = None
        self.eventos.ligar("galeria_aplicada", self._galeria_aplicada)

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
        self.vista.setCurrentWidget(self.galeria)
        nome = f"'{char}'" if char else "os glifos sem leitura"
        if escopo == "pagina":
            itens = [Item(p.indice, b.gid, b.entry.char, float(b.entry.confidence),
                          str(b.entry.source)) for b in p.modelo.boxes if b.entry.char == char]
            self._mostrar_na_galeria(f"Galeria de {nome} na página {p.indice + 1}", itens, escopo)
            return
        self.statusBar().showMessage(f"Juntando os glifos de {nome} do livro…", 0)

        def chegou(achados):
            self.statusBar().clearMessage()
            itens = [Item(a.pagina, a.gid, a.char, a.confianca, a.fonte) for a in achados
                     if a.char == char]
            self._mostrar_na_galeria(f"Galeria de {nome} no livro", itens, escopo)
        self.busca.glifos(char, ao_terminar=chegou)

    def mostrar_glifos_na_galeria(self, achados, titulo: str) -> None:
        """A busca por glifo (§7.1) abre na Galeria."""
        itens = [Item(a.pagina, a.gid, a.char, a.confianca, a.fonte) for a in achados]
        self._char_da_galeria = ""
        self.vista.setCurrentWidget(self.galeria)
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
        projeto, fonte = p.projeto, p.fonte
        aberta = (p.indice, p.imagem, p.modelo.instantaneo() if p.modelo is not None else None)
        por_pagina = defaultdict(list)
        for item in itens:
            por_pagina[item.pagina].append(item.gid)

        def rodar():
            for indice, gids in sorted(por_pagina.items(), key=lambda kv: kv[0] != aberta[0]):
                if carga != self._carga_da_galeria:
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
                    recortes = [(indice, g, pg.recorte(imagem, entradas[g]))
                                for g in gids if g in entradas]
                except Exception:
                    log.exception("os recortes da página %d para a Galeria falharam", indice + 1)
                    continue
                p.executar.na_interface(lambda r=recortes: self._recortes_chegaram(carga, r))

        threading.Thread(target=rodar, name="recortes-da-galeria", daemon=True).start()

    def _recortes_chegaram(self, carga: int, recortes) -> None:
        if carga != self._carga_da_galeria:
            return
        for indice, gid, recorte in recortes:
            self.galeria.modelo.mostrar_recorte(indice, gid, recorte)

    # ------------------------------------------------------------------
    def _galeria_aplicar(self, char: str) -> None:
        """Digitar um caractere na Galeria: ele vale para a seleção (sem ensinar)."""
        itens = self.galeria.selecionados()
        if not itens:
            return
        self._galeria_pendente = ([(i.pagina, i.gid) for i in itens], char)
        self.pagina.corrigir_no_livro(_por_pagina(itens), char)

    def _galeria_confirmar(self, ensinar: bool) -> None:
        """Enter (ensina) e Shift+Enter (só corrige): cada glifo com a leitura dele."""
        itens = [i for i in self.galeria.selecionados() if i.char]
        if not itens:
            return
        recortes = self.galeria.modelo.recortes
        por_char = defaultdict(list)
        for item in itens:
            por_char[item.char].append(item)
        faltam = [i for i in itens if (i.pagina, i.gid) not in recortes]
        if ensinar and faltam:
            self.statusBar().showMessage(f"{len(faltam)} recorte(s) ainda carregando: tente "
                                         "de novo em um instante.", 6000)
            return
        for char, grupo in por_char.items():
            self._galeria_pendente = ([(i.pagina, i.gid) for i in grupo], char)
            self.pagina.corrigir_no_livro(
                _por_pagina(grupo), char,
                recortes={(i.pagina, i.gid): recortes[(i.pagina, i.gid)] for i in grupo}
                if ensinar else None)

    def _galeria_aplicada(self, feitos: int, paginas: int, ensinou: bool) -> None:
        pendente, self._galeria_pendente = self._galeria_pendente, None
        if pendente is not None:
            self.galeria.modelo.trocar_leitura(*pendente)
        acao = "ensinado(s)" if ensinou else "corrigido(s)"
        self.statusBar().showMessage(f"Galeria: {feitos} glifo(s) {acao} em {paginas} "
                                     "página(s) · Ctrl+Z desfaz.", 8000)

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
