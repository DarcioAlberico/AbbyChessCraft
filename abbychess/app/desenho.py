"""O desenho da janela principal: o que cada evento dos controladores muda na tela.

É uma parte da `JanelaPrincipal` (`app/janela.py`), separada para a janela ficar com a
montagem e os comandos que perguntam antes (CA-14.1: `janela.py` < 500 linhas). Cada método
lê o estado dos controladores e desenha; nenhum decide nada.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QMessageBox

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
        self.visor.mostrar_pagina(pixmap_da_pagina(p.imagem))
        self.verificacao.limpar("Aperte F7 para verificar o texto da página.")
        self._layout_mudou()
        if self.visor.modo_areas and not p.zonas:
            self.areas.automaticas()

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
        if p.leitor is not None:
            por_char = p.leitor.padroes_por_caractere()
            self.treino.mostrar_contagens(len(pendentes), len(p.boxes),
                                          sum(len(v) for v in por_char.values()), len(por_char))

    def _atual_mudou(self) -> None:
        p = self.pagina
        if p.box_atual() is None:
            self.visor.selecionar(None)
            self.treino.limpar("Esta página ainda não foi reconhecida. Aperte F5."
                               if not p.boxes else
                               "Nada a revisar nesta página. Clique num box para corrigi-lo, "
                               "ou vá para o próximo pendente do livro (F6).")
            return
        self.treino.mostrar(p.matriz, p.box_atual(), p.posicao_do_atual())
        self.visor.selecionar(p.indice_de(p.atual))
        if not self.executor.so_leves():        # a propagação de um Enter não prende o painel
            self.treino.habilitar(False)

    def pintar_texto(self) -> None:
        self.relogio_do_texto.stop()
        self.texto.setPlainText(self.pagina.texto())

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
        QMessageBox.critical(self, titulo, texto)

    def _aviso(self, titulo: str, texto: str) -> None:
        QMessageBox.warning(self, titulo, texto)

    def _gravacao_falhou(self, indice, erro) -> None:
        pagina = f"A página {indice + 1}" if indice is not None else "Uma página"
        self.statusBar().showMessage(
            f"{pagina} não foi gravada ({erro}). Ela continua com as mudanças em memória e o "
            "programa tenta de novo; não feche antes de liberar o disco.")

    def _ocupado_mudou(self, ocupado: bool, titulo: str) -> None:
        self.progresso.setVisible(ocupado)
        self.progresso.setRange(0, 0)
        if ocupado and not self.executor.so_leves():
            self.statusBar().showMessage(f"{titulo}…")
            self.treino.habilitar(False)
        elif ocupado:
            pass                                # a propagação: o painel vale, e a mensagem
                                                # do Enter fica na barra
        elif self.pagina.box_atual() is not None:
            self.treino.habilitar(True)
            foco = QApplication.focusWidget()
            # O próximo caractere vai para o campo, mas sem tirar o foco de quem o tem por
            # escolha (o seletor de página, por exemplo): só de ninguém ou do painel de texto.
            if (self.abas.currentWidget() is self.treino and self.isActiveWindow()
                    and (foco is None or foco is self.texto or self.treino.isAncestorOf(foco))):
                self.treino.campo.setFocus()
        acoes.atualizar(self)

    def _fila_mudou(self, titulos: list) -> None:
        if self.executor.titulo:
            fila = f" Na fila: {', '.join(titulos)}." if titulos else ""
            self.statusBar().showMessage(f"{self.executor.titulo}…{fila}")

    def _progredir(self, feito: int, total: int) -> None:
        self.progresso.setRange(0, max(total, 1))
        self.progresso.setValue(feito)
