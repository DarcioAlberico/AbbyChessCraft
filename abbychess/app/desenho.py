"""O desenho da janela principal: o que cada evento dos controladores muda na tela.

É uma parte da `JanelaPrincipal` (`app/janela.py`), separada para a janela ficar com a
montagem e os comandos que perguntam antes (CA-14.1: `janela.py` < 500 linhas). Cada método
lê o estado dos controladores e desenha; nenhum decide nada.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QMessageBox

from abbychess import avisos as av
from abbychess import grade as gd
from abbychess import verificacao as vf
from abbychess.app import acoes, cores
from abbychess.app.imagens import pixmap_da_pagina


class DesenhoDaJanela:
    """Os métodos de desenho da `JanelaPrincipal` (um mixin: não é usado sozinho)."""

    def _pagina_trocou(self) -> None:
        p = self.pagina
        self.seletor.blockSignals(True)
        self.seletor.setMaximum(max(1, p.fonte.total))
        self.seletor.setValue(p.indice + 1)
        self.seletor.blockSignals(False)
        self.total_de_paginas.setText(f" de {p.fonte.total} ")
        self.visor.mostrar_pagina(self._pixmap(p.indice, p.imagem))
        self._pre_carga.start()                 # a seguinte, depois desta pintada
        self._pre_pixmap.start()                # e o pixmap dela, quando a pré-carga a tiver
        self.verificacao.limpar("Escolha a fila de palavras desconhecidas (F7) para verificar "
                                "o texto.")
        self._layout_mudou()
        if self.visor.modo_areas and not p.zonas:
            self.areas.automaticas()
        if self.fila.modo == "palavras":        # a página nova também é verificada
            self.verificar_texto()
        self.atualizar_barra()
        self.atualizar_paginas(seguir=True)

    def _pixmap(self, indice: int, imagem):
        """O QPixmap da página, das últimas 5 convertidas (a conversão leva dezenas de ms)."""
        guardado = self._pixmaps.get(indice)
        if guardado is not None and guardado[0] is imagem:
            self._pixmaps.move_to_end(indice)
            return guardado[1]
        pixmap = pixmap_da_pagina(imagem)
        self._pixmaps[indice] = (imagem, pixmap)
        while len(self._pixmaps) > 5:
            self._pixmaps.popitem(last=False)
        return pixmap

    def _pre_converter(self) -> None:
        """Converte a página seguinte, se a pré-carga já a renderizou (fora do clique)."""
        p = self.pagina
        if p.cache is not None and p.cache.tem(p.indice + 1):
            self._pixmap(p.indice + 1, p.cache.pagina(p.indice + 1)[0])

    def _zoom_mudou(self, escala: float, limite: str) -> None:
        self.caixa_de_zoom.blockSignals(True)
        self.caixa_de_zoom.setValue(round(escala * 100))
        self.caixa_de_zoom.blockSignals(False)
        if limite:
            self.statusBar().showMessage(f"zoom {limite}", 3000)

    def _glifos_mudaram(self, gids=None) -> None:
        """`gids`: só esses mudaram (a leitura, não a caixa nem a lista); None: tudo."""
        p = self.pagina
        na_fila = set(p.fila())
        todos = p.gids
        pendentes = {i for i, g in enumerate(todos) if g in na_fila}
        mudados = None if gids is None else [i for i, g in enumerate(todos) if g in gids]
        if mudados is None or not self.visor.repintar_boxes(p.boxes, pendentes, mudados):
            diagramas = p.diagramas
            self.visor.mostrar_boxes(p.boxes, pendentes, [d.caixa for d in diagramas],
                                     [cores.cor_do_diagrama(d) for d in diagramas])
        self._selecao_mudou()
        self.relogio_do_texto.start()
        self.relogio_das_paginas.start()        # o estado e os pendentes, na gaveta
        self.atualizar_barra()
        if p.leitor is not None:
            por_char = p.leitor.padroes_por_caractere()
            self.treino.mostrar_contagens(len(pendentes), len(p.boxes),
                                          sum(len(v) for v in por_char.values()), len(por_char))

    def _atual_mudou(self) -> None:
        p = self.pagina
        self.atualizar_fila()
        if p.box_atual() is None:
            self.visor.selecionar(None)
            self.treino.limpar("Esta página ainda não foi reconhecida. Aperte F5."
                               if not p.boxes else
                               "Nada a revisar nesta página. Clique num box para corrigi-lo, "
                               "ou vá para o próximo pendente do livro (F6).")
            return
        self.treino.mostrar(p.matriz, p.box_atual(), p.posicao_do_atual())
        # A fila e a Imagem levam o Documento e a Linha ao glifo (§6.2).
        self.texto.ir_ao_gid(p.atual, rolar=True)   # §6.2: o Documento rola até o glifo
        self.texto.marcar_atual(p.atual)            # e o marca, também sem o foco nele
        self.visor.marcar_palavra_do_documento(None)    # o contorno do cursor ficaria velho
        self._mostrar_a_linha()
        # Seguir (Ctrl+Shift+L): o item atual fica visível, a 120 px da borda (§3.3).
        self.visor.selecionar(p.indice_de(p.atual), centralizar=self.acao_seguir.isChecked())
        if not self.executor.so_leves():        # a propagação de um Enter não prende o painel
            self.treino.habilitar(False)

    def pintar_texto(self) -> None:
        """O Documento da página, com o realce de cada glifo (§6.1), sem perder o lugar."""
        self.relogio_do_texto.stop()
        p, v = self.pagina, self.verificador
        na_fila = set(p.fila())
        estados = {b.gid: gd.estado(b.entry, b.gid in na_fila) for b in p.modelo.boxes} \
            if p.modelo is not None else {}
        aviso = ("Nada reconhecido nesta página." if p.reconhecida
                 else "Página não reconhecida: F5 reconhece.")
        # A palavra fora do léxico que o usuário aceitou (Enter: revisada) não é mais duvidosa.
        revisados = {b.gid for b in p.modelo.boxes if b.revisado} if p.modelo is not None else set()
        self.texto.montar(p.documento(), p.diagramas, estados, v.gids_desconhecidos() - revisados,
                          p.gids_virtuais(), p.matriz, p.gids_de_margem(), aviso)
        self._mostrar_a_linha()

    def _selecao_mudou(self) -> None:
        p = self.pagina
        self.visor.marcar_selecao({p.indice_de(g) for g in p.selecao} - {None})
        self.treino.mostrar_selecao(len(p.alvos()) if p.selecao else 0)

    def _padroes_mudaram(self) -> None:
        if self.leitor is not None:
            self.padroes.atualizar(self.leitor.padroes_por_caractere())

    def _layout_mudou(self) -> None:
        self.visor.mostrar_zonas(self.areas.zonas, self.areas.atual)

    def _palavra_mudou(self) -> None:
        v, p = self.verificador, self.pagina
        palavra = v.atual()
        if palavra is None:
            self.visor.marcar_palavra(None)
            self.verificacao.limpar("Nenhuma palavra desconhecida nesta página.")
            return
        self.verificacao.mostrar(p.matriz, p.boxes, palavra, v.posicao, len(v.desconhecidas))
        self.visor.marcar_palavra(vf.caixa_da_palavra(p.boxes, palavra.indices))

    def _acoes_mudaram(self) -> None:
        acoes.atualizar(self)

    def _mensagem(self, texto: str, ms: int) -> None:
        if ms == 0 and self.executor.na_fila:   # o progresso não apaga a fila da barra
            texto += f" Na fila: {', '.join(self.executor.na_fila)}."
        self.statusBar().showMessage(texto, ms)

    def _falha(self, titulo: str, texto: str) -> None:
        self.statusBar().showMessage(f"{titulo}: falhou.")
        self.registrar_aviso(av.ERRO, titulo, texto)
        QMessageBox.critical(self, titulo, texto)

    def _aviso(self, titulo: str, texto: str) -> None:
        self.registrar_aviso(av.AVISO, titulo, texto)
        QMessageBox.warning(self, titulo, texto)

    def _gravacao_falhou(self, indice, erro) -> None:
        """CA-4.2 (A2): a falha de gravação vai para Avisos, além da barra."""
        pagina = f"A página {indice + 1}" if indice is not None else "Uma página"
        texto = (f"{pagina} não foi gravada ({erro}). Ela continua com as mudanças em memória "
                 "e o programa tenta de novo; não feche antes de liberar o disco.")
        self.statusBar().showMessage(texto)
        self.registrar_aviso(av.ERRO, "Gravação", texto)

    def _ocupado_mudou(self, ocupado: bool, titulo: str) -> None:
        self.progresso.setVisible(ocupado)
        self.progresso.setRange(0, 0)
        if ocupado and not self.executor.so_leves():
            self._mensagem_da_tarefa = f"{titulo}…"
            self.statusBar().showMessage(self._mensagem_da_tarefa)
            self.treino.habilitar(False)
        elif ocupado:
            pass                                # a propagação: o painel vale, e a mensagem
                                                # do Enter fica na barra
        else:
            self._limpar_a_mensagem_da_tarefa()
        if not ocupado and self.pagina.box_atual() is not None:
            self.treino.habilitar(True)
            foco = QApplication.focusWidget()
            # O próximo caractere vai para o campo, mas sem tirar o foco de quem o tem por
            # escolha (o seletor de página, por exemplo): só de ninguém ou do painel de texto.
            if (self.inspetor.atual() == "glifo" and self.isActiveWindow()
                    and (foco is None or foco is self.texto or self.treino.isAncestorOf(foco))):
                self.treino.campo.setFocus()
        acoes.atualizar(self)

    def _limpar_a_mensagem_da_tarefa(self) -> None:
        """A tarefa acabou: o "Carregando o léxico…" dela sai da barra (uma mensagem que
        veio depois, como o resultado, fica)."""
        mensagem = self._mensagem_da_tarefa
        if mensagem and self.statusBar().currentMessage().startswith(mensagem):
            self.statusBar().clearMessage()
        self._mensagem_da_tarefa = None

    def _fila_mudou(self, titulos: list) -> None:
        if self.executor.titulo:
            self._mensagem_da_tarefa = f"{self.executor.titulo}…"      # a tarefa que roda agora
            fila = f" Na fila: {', '.join(titulos)}." if titulos else ""
            self.statusBar().showMessage(f"{self.executor.titulo}…{fila}")

    def _progredir(self, feito: int, total: int) -> None:
        self.progresso.setRange(0, max(total, 1))
        self.progresso.setValue(feito)              # o rótulo do lote é de `_lote_progrediu`
