"""As operações de página vistas da janela (SPEC §12.4, passo L): os diálogos do menu Página e
da gaveta, que perguntam e chamam os comandos do controlador (`mover_paginas`,
`apagar_paginas`, `inserir_paginas`, `restaurar_paginas`, `girar_paginas`, `cortar_paginas`,
`tirar_o_corte`, `tirar_as_borrachas`, `tirar_as_coordenadas`, `dividir_paginas`,
`endireitar_paginas`), e o modo da borracha (CA-12.17), com os outros modos do arraste que ela
exclui. Um mixin da `JanelaPrincipal`, como `EspacoDeTrabalho`.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QFileDialog, QLabel

from abbychess import sequencia as sq
from abbychess.app import dialogo_paginas as dp
from abbychess.app import imagens
from abbychess.app import previa_da_pagina as pp
from abbychess.app import teclado
from abbychess.avisos import AVISO_LONGO_MS


class PaginasNaJanela:
    def _miniatura(self, posicoes: Sequence[int]):
        """(pixmap, legenda) da página que a miniatura do corte e da divisão mostra: a aberta,
        se ela está entre as escolhidas; senão a primeira delas. None se não há imagem (a
        miniatura sai, e os números continuam)."""
        if not posicoes or self.pagina.fonte is None:
            return None
        aberta = self.pagina.indice
        posicao = aberta if aberta in posicoes else min(posicoes)
        try:
            if posicao == aberta and self.pagina.matriz is not None:
                matriz = self.pagina.matriz
            else:
                matriz = self.pagina.cache.pagina(posicao)[1]
        except (OSError, IndexError, AttributeError):
            return None
        legenda = f"A página {posicao + 1}"
        if len(posicoes) > 1:
            legenda += " (as outras escolhidas seguem os mesmos números)"
        return imagens.pixmap_de_cinza(matriz), legenda

    def _posicoes_de_agora(self, selecionadas: Optional[Sequence[int]]) -> list:
        """As pedidas (a gaveta, pelo menu de contexto); senão as escolhidas na gaveta, se ela
        tem mais de uma (o menu Página vale para elas); senão a página aberta."""
        if selecionadas:
            return list(selecionadas)
        da_gaveta = self.paginas.selecionadas() if self.doca_paginas.isVisible() else []
        return list(da_gaveta) if len(da_gaveta) > 1 else [self.pagina.indice]

    def _selecao_de_agora(self, selecionadas: Optional[Sequence[int]]) -> str:
        return dp.texto_da_selecao(self._posicoes_de_agora(selecionadas))

    def operacao_da_gaveta(self, metodo: str, posicoes: Sequence[int]) -> None:
        """O menu de contexto da gaveta (`painel_paginas.OPERACOES_DA_GAVETA`): a operação nas
        páginas escolhidas."""
        operacoes = {"girar_a_direita": self.girar_a_direita,
                     "girar_a_esquerda": self.girar_a_esquerda,
                     "girar_paginas": self.girar_paginas, "cortar_paginas": self.cortar_paginas,
                     "tirar_o_corte": self.tirar_o_corte,
                     "tirar_as_borrachas": self.tirar_as_borrachas,
                     "tirar_as_coordenadas": self.tirar_as_coordenadas,
                     "dividir_paginas": self.dividir_paginas,
                     "endireitar_paginas": self.endireitar_paginas}
        operacoes[metodo](posicoes)

    def _so_um_modo(self, ligada) -> None:
        """Os modos do arraste (marcar glifo, áreas, borracha) se excluem: os outros saem."""
        for q in (self.acao_modo_treino, self.acao_areas, self.acao_borracha):
            if q is not ligada and q.isChecked():
                q.setChecked(False)
                if q is self.acao_areas:
                    self.modo_areas(False)
                else:
                    self.visor.definir_modo_do_quadro(None)

    def modo_borracha(self, sim: bool) -> None:
        """A borracha (CA-12.17): o arraste apaga a área da imagem (a mancha do scanner)."""
        if sim:
            self._so_um_modo(self.acao_borracha)
        self.visor.definir_modo_do_quadro("borracha" if sim else None)
        self.statusBar().showMessage(teclado.com_teclas(
            "Borracha: arraste em volta da mancha para apagá-la da imagem; {desfazer} a "
            "devolve.") if sim else "Borracha: desligada.", AVISO_LONGO_MS)

    def _apagar_mancha(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """A área da borracha apagada na página aberta; a vista fica onde estava (a página
        apagada é mostrada de novo, e começaria no topo)."""
        barras = (self.visor.horizontalScrollBar(), self.visor.verticalScrollBar())
        lugar = [b.value() for b in barras]
        if self.pagina.operacoes.apagar_manchas(self.pagina.indice, [(x1, y1, x2, y2)]):
            for barra, valor in zip(barras, lugar):
                barra.setValue(valor)

    def girar_a_direita(self, selecionadas: Optional[Sequence[int]] = None) -> None:
        """Um gesto (o menu, a gaveta): 90° à direita, sem diálogo."""
        self.pagina.operacoes.girar_paginas(self._posicoes_de_agora(selecionadas), 90)

    def girar_a_esquerda(self, selecionadas: Optional[Sequence[int]] = None) -> None:
        self.pagina.operacoes.girar_paginas(self._posicoes_de_agora(selecionadas), 270)

    def exportar_as_selecionadas(self, selecionadas: Sequence[int]) -> None:
        """A exportação só das páginas selecionadas na gaveta (§3.1)."""
        from abbychess.app import dialogo_exportacao, dialogos

        destino = dialogos.destino_da_exportacao(self, self.projeto)
        escolha = (dialogo_exportacao.perguntar(self, self.projeto, destino, selecao=selecionadas)
                   if destino else None)
        if escolha is not None:
            meta = escolha.metadados if destino.suffix.lower() in (".epub", ".docx") else None
            self.livro.exportar(destino, escolha.opcoes, meta, escolha.capa)

    def modelo_nas_selecionadas(self, selecionadas: Sequence[int]) -> None:
        """O modelo de áreas salvo nas páginas selecionadas na gaveta (§3.1)."""
        if self.areas.modelo is None:
            self.statusBar().showMessage(
                "Salve um modelo de áreas antes, numa página com as áreas certas.", 6000)
            return
        self.areas.aplicar_modelo(list(selecionadas))

    def mover_paginas(self, selecionadas: Optional[Sequence[int]] = None) -> None:
        escolha = self._perguntar_pela_selecao(
            "Mover páginas", selecionadas, ("1 página muda de lugar: {PAGINAS}.",
                                            "{N} páginas mudam de lugar: {PAGINAS}."),
            "Mover", "As páginas saem de onde estão e entram, na mesma ordem, depois da "
                     "página escolhida (contada como está agora). {desfazer} desfaz.",
            lugar="Depois da página", lugar_padrao=self.pagina.indice, validar=_mover_vale)
        if escolha is not None:
            posicoes, depois_da = escolha
            self.pagina.operacoes.mover_paginas(posicoes, depois_da)

    def apagar_paginas(self, selecionadas: Optional[Sequence[int]] = None) -> None:
        escolha = self._perguntar_pela_selecao(
            "Apagar páginas", selecionadas, ("1 página sai do livro: {PAGINAS}.",
                                             "{N} páginas saem do livro: {PAGINAS}."),
            "Apagar", "As páginas saem do livro, da busca e das exportações, mas ficam "
                      "guardadas no projeto, com os glifos e as correções: {desfazer}, ou "
                      "Página › Páginas apagadas…, as devolvem.")
        if escolha is not None:
            self.pagina.operacoes.apagar_paginas(escolha[0])

    def _perguntar_pela_selecao(self, titulo: str, selecionadas, efeito: Tuple[str, str],
                                ok: str, explicacao: str, **mais):
        """O diálogo das páginas a partir da seleção de agora; `efeito` é a frase de uma
        página e a de várias. A escolha, ou None se cancelou."""
        return dp.perguntar_paginas(
            self, titulo, self._total(), selecao=self._selecao_de_agora(selecionadas),
            efeito=dp.efeito(*efeito), ok=ok, explicacao=explicacao, **mais)

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
            ok="Inserir",
            explicacao=("1 arquivo. Cada página dele vira uma página do livro; ele é copiado "
                        "para o projeto (o original pode sair do lugar). {desfazer} desfaz."
                        if len(caminhos) == 1 else
                        f"{len(caminhos)} arquivos. Cada página deles vira uma página do livro; "
                        "eles são copiados para o projeto (os originais podem sair do lugar). "
                        "{desfazer} desfaz."))
        if escolha is not None:
            self.pagina.operacoes.inserir_paginas(caminhos, escolha[1] + 1)

    def _total(self) -> int:
        return self.pagina.fonte.total if self.pagina.fonte else 0

    def girar_paginas(self, selecionadas: Optional[Sequence[int]] = None) -> None:
        sentido = dp.campo_do_sentido()
        escolha = dp.perguntar_com(
            self, "Girar páginas", self._total(), [("Girar", sentido)], sentido.currentData,
            selecao=self._selecao_de_agora(selecionadas),
            efeito=dp.efeito("1 página gira: {PAGINAS}.", "{N} páginas giram: {PAGINAS}."),
            ok="Girar",
            explicacao="A imagem gira, e os glifos, as áreas e os diagramas lidos vão junto. "
                       "{desfazer} desfaz.")
        if escolha is not None:
            self.pagina.operacoes.girar_paginas(*escolha)

    def cortar_paginas(self, selecionadas: Optional[Sequence[int]] = None) -> None:
        margens = [dp.campo_de_porcentagem(0.0, 0.0, 95.0) for _ in range(4)]
        posicoes = self._posicoes_de_agora(selecionadas)
        miniatura = self._miniatura(posicoes)
        if miniatura is not None:
            miniatura = pp.PreviaDoCorte(miniatura[0], margens, miniatura[1])
        escolha = dp.perguntar_com(
            self, "Cortar páginas", self._total(),
            list(zip(("Margem esquerda", "Margem de cima", "Margem direita", "Margem de baixo"),
                     margens)),
            lambda: tuple(m.value() / 100 for m in margens),
            selecao=dp.texto_da_selecao(posicoes), miniatura=miniatura,
            efeito=dp.efeito("1 página é cortada: {PAGINAS}.",
                             "{N} páginas são cortadas: {PAGINAS}."), ok="Cortar",
            explicacao="Marque na página o que fica: arraste as bordas ou os cantos, ou "
                       "desenhe outro retângulo. Cada margem é a parte da imagem que se vê "
                       "agora que sai, em porcentagem da largura ou da altura. Os glifos que "
                       "ficam de fora são guardados: {desfazer}, ou Tirar o corte…, os "
                       "devolvem.")
        if escolha is not None:
            self.pagina.operacoes.cortar_paginas(*escolha)

    def tirar_o_corte(self, selecionadas: Optional[Sequence[int]] = None) -> None:
        escolha = self._perguntar_pela_selecao(
            "Tirar o corte", selecionadas, ("1 página volta inteira: {PAGINAS}.",
                                            "{N} páginas voltam inteiras: {PAGINAS}."),
            "Tirar o corte", "A página volta inteira (o giro fica), com os glifos que o corte "
                             "guardou. A metade de uma página dividida não: o {desfazer} da "
                             "divisão junta as metades.")
        if escolha is not None:
            self.pagina.operacoes.tirar_o_corte(escolha[0])

    def tirar_as_borrachas(self, selecionadas: Optional[Sequence[int]] = None) -> None:
        escolha = self._perguntar_pela_selecao(
            "Tirar a borracha", selecionadas,
            ("1 página volta como era na fonte: {PAGINAS}.",
             "{N} páginas voltam como eram na fonte: {PAGINAS}."),
            "Tirar a borracha", "As áreas que a borracha apagou voltam à imagem; o corte, o "
                                "giro e a leitura ficam. {desfazer} desfaz.")
        if escolha is not None:
            self.pagina.operacoes.tirar_as_borrachas(escolha[0])

    def tirar_as_coordenadas(self, selecionadas: Optional[Sequence[int]] = None) -> None:
        escolha = self._perguntar_pela_selecao(
            "Tirar as coordenadas", selecionadas,
            ("1 página fica sem as coordenadas dos diagramas: {PAGINAS}.",
             "{N} páginas ficam sem as coordenadas dos diagramas: {PAGINAS}."),
            "Tirar as coordenadas",
            "As letras e os números impressos em volta dos diagramas lidos saem da imagem e das "
            "exportações; a legenda e o texto em volta ficam, e o diagrama segue na orientação "
            "em que foi lido. {desfazer} desfaz, e Tirar a borracha… as devolve.")
        if escolha is not None:
            self.pagina.operacoes.tirar_as_coordenadas(escolha[0])

    def dividir_paginas(self, selecionadas: Optional[Sequence[int]] = None) -> None:
        onde = dp.campo_de_porcentagem(50.0, 5.0, 95.0, " % da largura")
        posicoes = self._posicoes_de_agora(selecionadas)
        miniatura = self._miniatura(posicoes)
        if miniatura is not None:
            miniatura = pp.PreviaDaDivisao(miniatura[0], onde, miniatura[1])
        lidas = set(self.projeto.resumo.paginas_lidas()) if self.projeto is not None else set()
        contagem = dp.efeito("1 página dupla vira duas: {PAGINAS}.",
                             "{N} páginas duplas viram duas cada: {PAGINAS}.")

        def efeito(posicoes):
            texto = contagem(posicoes)
            ja_lidas = len(lidas.intersection(posicoes))
            if ja_lidas > 20:
                # As duas metades de cada página lida são gravadas: uns segundos no livro.
                texto += (f" {ja_lidas} já foram lidas: leva alguns segundos (dividir antes "
                          "de ler é instantâneo).")
            return texto

        escolha = dp.perguntar_com(
            self, "Dividir páginas", self._total(), [("Dividir em", onde)],
            lambda: onde.value() / 100, selecao=dp.texto_da_selecao(posicoes),
            miniatura=miniatura, efeito=efeito, ok="Dividir",
            explicacao="A imagem com duas páginas do livro lado a lado (a página dupla) vira "
                       "duas, na linha que se marca na página (clique ou arraste): a metade "
                       "esquerda fica no lugar e a direita entra logo depois, "
                       "cada uma com os glifos dela. A que já é metade de uma divisão fica "
                       "como está. {desfazer} junta de novo.")
        if escolha is not None:
            with _ocupado(self, "Dividindo as páginas…"):
                self.pagina.operacoes.dividir_paginas(*escolha)

    def endireitar_paginas(self, selecionadas: Optional[Sequence[int]] = None) -> None:
        limite = self.pagina.ENDIREITAR_NO_MAXIMO
        try:
            agora = self.pagina.fonte.inclinacao(self.pagina.indice) if self.pagina.fonte else 0
        except (OSError, IndexError):
            agora = 0.0
        angulo = dp.campo_de_porcentagem(agora, -limite, limite, "°", decimais=2, passo=0.1)
        # Começa no medido: dar OK sem mexer não muda nada (com várias páginas, o ângulo de
        # uma valeria para todas, e a leitura delas se desfaria).
        medido = QCheckBox("Usar o ângulo medido de cada página")
        medido.toggled.connect(lambda sim: angulo.setEnabled(not sim))
        medido.setChecked(True)
        nota = QLabel(f"Medido nesta página: {agora:.2f}°".replace(".", ","))
        lidas = set(self.projeto.resumo.paginas_lidas()) if self.projeto is not None else set()
        # As com ângulo à mão: só elas mudam quando o pedido é o medido.
        a_mao = ({i for i, e in enumerate(self.projeto.sequencia.entradas)
                  if e.angulo is not None} if self.projeto is not None else set())

        def efeito(posicoes):
            if medido.isChecked():
                voltam = a_mao.intersection(posicoes)
                texto = (f"{sq.quantas_paginas(len(voltam))} "
                         f"{'volta' if len(voltam) == 1 else 'voltam'} ao ângulo medido; as "
                         "outras ficam como estão.")
                perdem = len(lidas.intersection(voltam))
                rotulo = "Voltar ao ângulo medido"
            else:
                graus = f"{angulo.value():.2f}".replace(".", ",")
                texto = (f"{sq.quantas_paginas(len(posicoes))} "
                         f"{'é endireitada' if len(posicoes) == 1 else 'são endireitadas'} "
                         f"em {graus}°: {dp.texto_da_selecao(posicoes)}.")
                perdem = len(lidas.intersection(posicoes))
                rotulo = "Endireitar e desfazer a leitura" if perdem else "Endireitar"
            if perdem:
                texto += (f" A leitura de {sq.quantas_paginas(perdem)} se desfaz (ficam os "
                          "glifos marcados à mão).")
            return texto, rotulo

        def validar(posicoes, _depois_da):
            if medido.isChecked() and not a_mao.intersection(posicoes):
                return ("Nenhuma das escolhidas tem ângulo à mão: com o medido, nada muda. "
                        "Desmarque a caixa para dar um ângulo.")
            return None

        escolha = dp.perguntar_com(
            self, "Endireitar páginas", self._total(),
            [("Ângulo", angulo), ("", nota), ("", medido)],
            lambda: None if medido.isChecked() else angulo.value(),
            selecao=self._selecao_de_agora(selecionadas), efeito=efeito, validar=validar,
            sinais=(medido.toggled, angulo.valueChanged),
            explicacao="O ângulo positivo gira a página no sentido anti-horário. Na página "
                       "lida, a leitura se desfaz: ficam só os glifos marcados à mão (a "
                       "leitura digitada ou aceita na revisão), girados com a página, e as "
                       "áreas que você desenhou; o F5 lê de novo. {desfazer} desfaz.")
        if escolha is not None:
            with _ocupado(self, "Endireitando as páginas…"):
                self.pagina.operacoes.endireitar_paginas(*escolha)

    def paginas_apagadas(self) -> None:
        apagadas = self.projeto.sequencia.apagadas if self.projeto is not None else ()
        if not apagadas:
            self.statusBar().showMessage("Nenhuma página apagada.", 5000)
            return
        pids = dp.perguntar_apagadas(self, apagadas)
        if pids:
            self.pagina.operacoes.restaurar_paginas(pids)


def _mover_vale(posicoes, depois_da: int):
    """Por que mover não vale (na linha da prévia, antes do OK), ou None."""
    if depois_da in posicoes:
        return "a página de referência é uma das que se movem: escolha outra"
    if sorted(posicoes) == list(range(depois_da + 1, depois_da + 1 + len(posicoes))):
        return "as páginas já estão aí: escolha outro lugar"
    return None


class _ocupado:
    """O cursor de espera e o aviso na barra durante uma operação longa na interface (dividir
    ou endireitar o livro inteiro leva uns segundos)."""

    def __init__(self, janela, aviso: str):
        self.janela, self.aviso = janela, aviso

    def __enter__(self):
        self.janela.statusBar().showMessage(self.aviso)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        # Desligada antes de pintar o aviso: um clique no meio não dispara outra operação.
        self.janela.setEnabled(False)
        QApplication.processEvents()
        return self

    def __exit__(self, *_erro):
        self.janela.setEnabled(True)
        QApplication.restoreOverrideCursor()
        return False
