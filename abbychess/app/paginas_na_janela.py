"""As operações de página vistas da janela (SPEC §12.4, passo L): os diálogos do menu Página e
da gaveta, que perguntam e chamam os comandos do controlador (`mover_paginas`,
`apagar_paginas`, `inserir_paginas`, `restaurar_paginas`, `girar_paginas`, `cortar_paginas`,
`tirar_o_corte`, `dividir_paginas`, `endireitar_paginas`). Um mixin da `JanelaPrincipal`,
como `EspacoDeTrabalho`.
"""

from __future__ import annotations

from typing import Optional, Sequence

from PySide6.QtWidgets import QCheckBox, QFileDialog

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

    def _total(self) -> int:
        return self.pagina.fonte.total if self.pagina.fonte else 0

    def girar_paginas(self, selecionadas: Optional[Sequence[int]] = None) -> None:
        sentido = dp.campo_do_sentido()
        escolha = dp.perguntar_com(
            self, "Girar páginas", self._total(), [("Girar", sentido)], sentido.currentData,
            selecao=self._selecao_de_agora(selecionadas),
            efeito="{N} página(s) giram: {PAGINAS}.",
            explicacao="A imagem gira, e os glifos, as áreas e os diagramas lidos vão junto. "
                       "Ctrl+Z desfaz.")
        if escolha is not None:
            self.pagina.girar_paginas(*escolha)

    def cortar_paginas(self, selecionadas: Optional[Sequence[int]] = None) -> None:
        margens = [dp.campo_de_porcentagem(0.0, 0.0, 95.0) for _ in range(4)]
        escolha = dp.perguntar_com(
            self, "Cortar páginas", self._total(),
            list(zip(("Margem esquerda", "Margem de cima", "Margem direita", "Margem de baixo"),
                     margens)),
            lambda: tuple(m.value() / 100 for m in margens),
            selecao=self._selecao_de_agora(selecionadas),
            efeito="{N} página(s) são cortadas: {PAGINAS}.",
            explicacao="Cada margem é a parte da imagem que se vê agora que sai, em "
                       "porcentagem da largura ou da altura. Os glifos que ficam de fora "
                       "são guardados: Ctrl+Z, ou Tirar o corte…, os devolvem.")
        if escolha is not None:
            self.pagina.cortar_paginas(*escolha)

    def tirar_o_corte(self, selecionadas: Optional[Sequence[int]] = None) -> None:
        escolha = dp.perguntar_paginas(
            self, "Tirar o corte", self._total(), selecao=self._selecao_de_agora(selecionadas),
            efeito="{N} página(s) voltam inteiras: {PAGINAS}.",
            explicacao="A página volta inteira (o giro fica), com os glifos que o corte "
                       "guardou. A metade de uma página dividida não: o Ctrl+Z da divisão "
                       "junta as metades.")
        if escolha is not None:
            self.pagina.tirar_o_corte(escolha[0])

    def dividir_paginas(self, selecionadas: Optional[Sequence[int]] = None) -> None:
        onde = dp.campo_de_porcentagem(50.0, 5.0, 95.0, " % da largura")
        escolha = dp.perguntar_com(
            self, "Dividir páginas", self._total(), [("Dividir em", onde)],
            lambda: onde.value() / 100, selecao=self._selecao_de_agora(selecionadas),
            efeito="{N} página(s) espelhada(s) viram duas cada: {PAGINAS}.",
            explicacao="A página de duas colunas de livro (a espelhada) vira duas: a metade "
                       "esquerda fica no lugar e a direita entra logo depois, cada uma com "
                       "os glifos dela. Ctrl+Z junta de novo.")
        if escolha is not None:
            self.pagina.dividir_paginas(*escolha)

    def endireitar_paginas(self, selecionadas: Optional[Sequence[int]] = None) -> None:
        limite = self.pagina.ENDIREITAR_NO_MAXIMO
        try:
            agora = self.pagina.fonte.inclinacao(self.pagina.indice) if self.pagina.fonte else 0
        except (OSError, IndexError):
            agora = 0.0
        angulo = dp.campo_de_porcentagem(agora, -limite, limite, "°", decimais=2, passo=0.1)
        medido = QCheckBox("Usar o ângulo medido")
        medido.toggled.connect(lambda sim: angulo.setEnabled(not sim))
        escolha = dp.perguntar_com(
            self, "Endireitar páginas", self._total(),
            [("Ângulo", angulo), ("", medido)],
            lambda: None if medido.isChecked() else angulo.value(),
            selecao=self._selecao_de_agora(selecionadas),
            efeito="{N} página(s) são endireitadas: {PAGINAS}.",
            explicacao="O ângulo positivo gira a página no sentido anti-horário. A leitura "
                       "das páginas se desfaz: ficam só os glifos marcados à mão (a leitura "
                       "digitada ou aceita na revisão), girados com a página, e as áreas que "
                       "você desenhou; o F5 lê de novo. Ctrl+Z desfaz.")
        if escolha is not None:
            self.pagina.endireitar_paginas(*escolha)

    def paginas_apagadas(self) -> None:
        apagadas = self.projeto.sequencia.apagadas if self.projeto is not None else ()
        if not apagadas:
            self.statusBar().showMessage("Nenhuma página apagada.", 5000)
            return
        pids = dp.perguntar_apagadas(self, apagadas)
        if pids:
            self.pagina.restaurar_paginas(pids)
