"""As operações de página vistas da janela (SPEC §12.4, passo L): os diálogos do menu Página e
da gaveta, que perguntam e chamam os comandos do controlador (`mover_paginas`,
`apagar_paginas`, `inserir_paginas`, `restaurar_paginas`). Um mixin da `JanelaPrincipal`,
como `EspacoDeTrabalho`.
"""

from __future__ import annotations

from typing import Optional, Sequence

from PySide6.QtWidgets import QFileDialog

from abbychess.app import dialogo_paginas as dp


class PaginasNaJanela:
    def _selecao_de_agora(self, selecionadas: Optional[Sequence[int]]) -> str:
        """As da gaveta, se ela tem várias escolhidas; senão a página aberta."""
        if selecionadas:
            return dp.texto_da_selecao(selecionadas)
        return str(self.pagina.indice + 1)

    def mover_paginas(self, selecionadas: Optional[Sequence[int]] = None) -> None:
        total = self.pagina.fonte.total if self.pagina.fonte else 0
        escolha = dp.perguntar_paginas(
            self, "Mover páginas", total, selecao=self._selecao_de_agora(selecionadas),
            lugar="Depois da página", lugar_padrao=self.pagina.indice,
            efeito="{N} página(s) mudam de lugar: {PAGINAS}.",
            explicacao="As páginas saem de onde estão e entram, na mesma ordem, depois da "
                       "página escolhida (contada como está agora). Ctrl+Z desfaz.")
        if escolha is not None:
            posicoes, depois_da = escolha
            self.pagina.mover_paginas(posicoes, depois_da)

    def apagar_paginas(self, selecionadas: Optional[Sequence[int]] = None) -> None:
        total = self.pagina.fonte.total if self.pagina.fonte else 0
        escolha = dp.perguntar_paginas(
            self, "Apagar páginas", total, selecao=self._selecao_de_agora(selecionadas),
            efeito="{N} página(s) saem do livro: {PAGINAS}.",
            explicacao="As páginas saem do livro, da busca e das exportações, mas ficam "
                       "guardadas no projeto, com os glifos e as correções: Ctrl+Z, ou "
                       "Página › Páginas apagadas…, as devolvem.")
        if escolha is not None:
            self.pagina.apagar_paginas(escolha[0])

    def inserir_paginas(self) -> None:
        caminhos, _ = QFileDialog.getOpenFileNames(
            self, "Inserir páginas de um PDF ou de imagens", "",
            "PDF e imagens (*.pdf *.png *.jpg *.jpeg *.tif *.tiff *.bmp)")
        if not caminhos:
            return
        total = self.pagina.fonte.total if self.pagina.fonte else 0
        escolha = dp.perguntar_paginas(
            self, "Inserir páginas", total, com_selecao=False,
            lugar="Depois da página", lugar_padrao=self.pagina.indice + 1,
            explicacao=f"{len(caminhos)} arquivo(s). Cada página deles vira uma página do "
                       "livro; os arquivos são copiados para o projeto (o original pode "
                       "sair do lugar). Ctrl+Z desfaz.")
        if escolha is not None:
            self.pagina.inserir_paginas(caminhos, escolha[1] + 1)

    def paginas_apagadas(self) -> None:
        apagadas = self.projeto.sequencia.apagadas if self.projeto is not None else ()
        if not apagadas:
            self.statusBar().showMessage("Nenhuma página apagada.", 5000)
            return
        pids = dp.perguntar_apagadas(self, apagadas)
        if pids:
            self.pagina.restaurar_paginas(pids)
