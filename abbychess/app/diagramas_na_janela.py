"""Os diagramas vistos da janela (SPEC §10, passo H): o editor Diagrama do Inspetor e a aba
Diagramas. Um mixin da `JanelaPrincipal`, como `EspacoDeTrabalho`: a conferência e a leitura
dos diagramas do livro são do `ControladorDeDiagramas`; aqui só se monta e se liga.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage

from abbychess.app import acoes
from abbychess.app.documento import imagem_do_diagrama
from abbychess.app.editor_diagrama import EditorDeDiagrama
from abbychess.app.painel_diagramas import PainelDeDiagramas


class DiagramasNaJanela:
    def _montar_diagramas(self) -> None:
        """O editor (no Inspetor) e a aba; o visor já existe."""
        c = self.conferencia
        self.editor_diagrama = EditorDeDiagrama()
        self.editor_diagrama.aplicar = c.aplicar     # grava antes de marcar (devolve se gravou)
        # Depois de gravar: a aba aberta relê o livro.
        self.editor_diagrama.conferido.connect(self._diagramas_mudaram)
        self.editor_diagrama.terminou.connect(c.proximo_do_livro)
        self.editor_diagrama.diagrama_mostrado.connect(self.visor.enquadrar)
        self.editor_diagrama.fora_da_pagina.connect(c.vizinho_do_livro)
        self.painel_diagramas = PainelDeDiagramas()
        self.painel_diagramas.abrir.connect(self.abrir_diagrama_do_livro)
        self.painel_diagramas.atualizar_pedido.connect(self.atualizar_diagramas)

    def _abrir_conferencia(self, indice: int) -> EditorDeDiagrama:
        """O editor Diagrama no Inspetor, no diagrama `indice` da página; a Imagem dá zoom
        nele e continua navegável (§10, CA-10.2)."""
        editor = self.editor_diagrama
        self.doca_inspetor.show()
        self.inspetor.mostrar("diagrama")
        editor.abrir(self.pagina.diagramas, indice, self.pagina.linhas_dos_diagramas())
        editor.posicao.setFocus(Qt.FocusReason.OtherFocusReason)
        acoes.atualizar(self)
        return editor

    def _sincronizar_conferencia(self, *_mudados) -> None:
        """A página mudou (desfazer, F5, áreas, a legenda): o editor acompanha, ou fecha se
        os diagramas não são mais os mesmos (nunca grava no diagrama errado)."""
        if self.editor_diagrama.aberto and not self.editor_diagrama.sincronizar(
                self.pagina.diagramas):
            self.statusBar().showMessage("A conferência fechou: os diagramas da página "
                                         "mudaram.", 6000)
            if self.inspetor.atual() == "diagrama":
                self.inspetor.mostrar("glifo")

    def _fechar_conferencia(self) -> None:
        """A página trocou: os diagramas em edição eram da outra (sem gravar nada)."""
        if self.editor_diagrama.aberto:
            self.editor_diagrama.fechar()
            if self.inspetor.atual() == "diagrama":
                self.inspetor.mostrar("glifo")

    # ------------------------------------------------------------------
    # A aba Diagramas
    # ------------------------------------------------------------------
    def atualizar_diagramas(self) -> None:
        """Relê os diagramas do livro (fora da interface) e os mostra na aba."""
        if self.projeto is not None:
            self.conferencia.do_livro(self._mostrar_diagramas)

    def _mostrar_diagramas(self, paginas) -> None:
        self.painel_diagramas.mostrar(paginas, self._recorte_na_memoria, _desenho)

    def _aba_mudou(self, _indice: int) -> None:
        if self.vista.currentWidget() is self.painel_diagramas:
            self.atualizar_diagramas()

    def _diagramas_mudaram(self, *_conferencia) -> None:
        if self.vista.currentWidget() is self.painel_diagramas:
            self.atualizar_diagramas()

    def _recorte_na_memoria(self, indice: int, caixa) -> Optional[QImage]:
        """O impresso do diagrama, se a página estiver entre as convertidas; senão None
        (converter todas as páginas do livro para a aba seria trabalho longo)."""
        guardado = self._pixmaps.get(indice)
        if guardado is None:
            return None
        x1, y1, x2, y2 = (int(v) for v in caixa)
        return guardado[1].copy(QRect(x1, y1, x2 - x1, y2 - y1)).toImage()

    def abrir_diagrama_do_livro(self, indice: int, diagrama: int) -> None:
        """Da aba: a página do diagrama e ele no editor Diagrama do Inspetor."""
        if indice != self.pagina.indice and not self.pagina.ir_para(indice):
            return
        self.conferencia.conferir(diagrama)


def _desenho(diagrama) -> QImage:
    return imagem_do_diagrama(diagrama, None)
