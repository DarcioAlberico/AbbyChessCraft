"""A janela principal do AbbyChessCraft: o fluxo de treino por livro.

O caminho de uso é o do FineReader com treino de padrões:

1. **Novo projeto** liga um PDF ou imagem a uma pasta de projeto do livro.
2. **Reconhecer página** (F5) segmenta e lê, com os padrões do livro na frente.
3. A fila mostra os glifos duvidosos, do menos confiável ao mais. Para cada um,
   Enter ensina o padrão e relê a página; as repetições somem da fila sozinhas.
   No modo de treino (Ctrl+T) o arraste desenha o quadro de um glifo que a
   segmentação perdeu, e Ctrl+clique junta ocorrências para ensinar de uma vez.
4. O box que juntou dois glifos se divide (Ctrl+D) e cada parte entra na fila;
   o que a segmentação partiu se junta (Ctrl+J), e as bordas se ajustam.
5. Na página seguinte o livro já lê com o que foi ensinado.
6. **Reconhecer o livro** lê um intervalo de páginas em segundo plano, e F6 anda
   pela revisão do livro todo, de página em página. **Exportar** escreve o PDF
   pesquisável, o DOCX ou o EPUB das páginas reconhecidas.
7. O **editor de áreas** (Ctrl+Shift+A) corrige o que a página tem de texto,
   diagrama, imagem e o que ignorar, antes do F5. A **verificação de texto** (F7)
   anda pelas palavras que o léxico do core não conhece.

A janela só compõe e despacha. O que lê, ensina e grava está em
`abbychess.pagina`, `abbychess.leitor`, `abbychess.projeto`, `abbychess.livro`,
`abbychess.exportar`, `abbychess.zonas` e `abbychess.verificacao`, sem Qt.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (QDockWidget, QFileDialog, QInputDialog, QLabel, QMainWindow,
                               QMessageBox, QPlainTextEdit, QProgressBar, QSpinBox, QTabWidget,
                               QToolBar)

from core.box_model import BoxEntry

from abbychess import diagramas as dg
from abbychess import exportar as ex
from abbychess import livro
from abbychess import historico as hs
from abbychess import pagina as pg
from abbychess import verificacao as vf
from abbychess import zonas as zn
from abbychess.app import cores
from abbychess.app.dialogo_diagrama import DialogoDeDiagrama
from abbychess.app.imagens import pixmap_da_pagina
from abbychess.app.opcoes import DialogoDeOpcoes
from abbychess.app.painel_padroes import PainelDePadroes
from abbychess.app.painel_treino import FONTE_DE_SIMBOLOS, PainelDeTreino
from abbychess.app.painel_verificacao import PainelDeVerificacao
from abbychess.app.trabalho import Executor
from abbychess.app.visor import VisorDePagina
from abbychess.leitor import LeitorDoLivro
from abbychess.projeto import ProjetoDeLivro, ProjetoInvalido

log = logging.getLogger(__name__)

TITULO = "AbbyChessCraft"


class JanelaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(TITULO)
        self.resize(1500, 950)
        self.config = QSettings("AbbyChessCraft", "AbbyChessCraft")

        self.projeto: Optional[ProjetoDeLivro] = None
        self.fonte: Optional[pg.FonteDePaginas] = None
        self.leitor: Optional[LeitorDoLivro] = None
        self.indice_pagina = 0
        self.imagem = None
        self.matriz: Optional[np.ndarray] = None
        self.boxes: List[BoxEntry] = []
        self.tabuleiros: list = []
        #: A leitura de cada tabuleiro (`abbychess.diagramas`), de cima para baixo.
        self.diagramas: List[dg.DiagramaLido] = []
        #: O desfazer de cada página desta sessão (`abbychess.historico`).
        self.historicos: Dict[int, hs.Historico] = {}
        #: A página passou pelo F5 ou pelo lote; falso enquanto só tem quadros marcados.
        self.reconhecida = False
        self.dialogo_diagrama: Optional[DialogoDeDiagrama] = None
        self.atual: Optional[int] = None
        self.pulados: set = set()
        #: A seleção do modo de treino, que um Enter ensina inteira.
        self.selecao: set = set()
        #: O pedido de cancelar o lote em andamento, ou None sem lote.
        self._cancelar_lote: Optional[threading.Event] = None
        #: As áreas da página (editor de áreas) e a escolhida.
        self.zonas: List[zn.Zona] = []
        self.zona_atual: Optional[int] = None
        #: A verificação de texto: o léxico do livro, as palavras e onde se está.
        self.lexico = None
        self.ignoradas: set = set()
        self.desconhecidas: List[vf.Desconhecida] = []
        self.pos_verificacao = 0

        self.executor = Executor(self)
        self.executor.ocupado_mudou.connect(self._ocupado_mudou)

        self.visor = VisorDePagina()
        self.visor.box_clicado.connect(self._box_clicado)
        self.visor.dividir_em.connect(self._dividir_box)
        self.visor.juntar_com.connect(self._juntar_box)
        self.visor.area_desenhada.connect(self._criar_box)
        self.visor.box_alternado.connect(self._alternar_na_selecao)
        self.visor.diagrama_clicado.connect(self._diagrama_clicado)
        self.visor.zona_desenhada.connect(self._zona_desenhada)
        self.visor.zona_escolhida.connect(self._zona_escolhida)
        self.visor.zona_arrastada.connect(self._zona_arrastada)
        self.visor.zona_apagada.connect(self._zona_apagada)
        self.visor.zona_tipo.connect(self._zona_tipo)
        self.setCentralWidget(self.visor)

        self.treino = PainelDeTreino()
        self.treino.ensinar.connect(self._ensinar)
        self.treino.so_corrigir.connect(self._so_corrigir)
        self.treino.descartar.connect(self._descartar)
        self.treino.pular.connect(lambda: self._andar_na_fila(+1))
        self.treino.anterior.connect(lambda: self._andar_na_fila(-1))
        self.treino.dividir.connect(self._dividir)
        self.treino.juntar.connect(self._juntar)
        self.treino.ajustar.connect(self._ajustar)
        self.treino.corte_mudou.connect(self.visor.marcar_corte)
        self.treino.limpar_selecao.connect(self._limpar_selecao)

        self.padroes = PainelDePadroes()
        self.padroes.esquecer.connect(self._esquecer)

        self.verificacao = PainelDeVerificacao()
        self.verificacao.corrigir.connect(self._corrigir_palavra)
        self.verificacao.ensinar.connect(lambda t: self._corrigir_palavra(t, ensinar=True))
        self.verificacao.pular.connect(lambda: self._andar_na_verificacao(+1))
        self.verificacao.anterior.connect(lambda: self._andar_na_verificacao(-1))
        self.verificacao.ignorar_todas.connect(self._ignorar_todas)
        self.verificacao.adicionar.connect(self._adicionar_ao_lexico)
        self.verificacao.glifo_escolhido.connect(self._glifo_da_palavra)

        self.abas = abas = QTabWidget()
        abas.addTab(self.treino, "Treino")
        abas.addTab(self.padroes, "Padrões do livro")
        abas.addTab(self.verificacao, "Verificação")
        abas.currentChanged.connect(self._aba_mudou)
        doca = QDockWidget("Treino de padrões", self)
        doca.setObjectName("doca_treino")
        doca.setWidget(abas)
        doca.setMinimumWidth(420)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, doca)

        self.texto = QPlainTextEdit()
        self.texto.setReadOnly(True)
        self.texto.setFont(QFont(FONTE_DE_SIMBOLOS, 11))
        doca_texto = QDockWidget("Texto reconhecido", self)
        doca_texto.setObjectName("doca_texto")
        doca_texto.setWidget(self.texto)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, doca_texto)

        self._montar_acoes()
        self.progresso = QProgressBar()
        self.progresso.setMaximumWidth(260)
        self.progresso.hide()
        self.statusBar().addPermanentWidget(self.progresso)
        self.treino.limpar("Crie um projeto (Ctrl+N) ou abra um existente (Ctrl+O).")
        self._atualizar_acoes()

    # ------------------------------------------------------------------
    # Ações e barra
    # ------------------------------------------------------------------
    def _acao(self, texto, atalho, funcao, barra=None) -> QAction:
        acao = QAction(texto, self)
        if atalho:
            acao.setShortcut(QKeySequence(atalho))
        acao.triggered.connect(funcao)
        if barra is not None:
            barra.addAction(acao)
        return acao

    def _montar_acoes(self) -> None:
        barra = QToolBar("Principal")
        barra.setObjectName("barra_principal")
        barra.setMovable(False)
        self.addToolBar(barra)

        self.acao_novo = self._acao("Novo projeto…", "Ctrl+N", self.novo_projeto, barra)
        self.acao_abrir = self._acao("Abrir projeto…", "Ctrl+O", self.abrir_projeto, barra)
        barra.addSeparator()
        self.acao_anterior = self._acao("◀", "Ctrl+PgUp",
                                        lambda: self.ir_para_pagina(self.indice_pagina - 1), barra)
        self.seletor = QSpinBox()
        self.seletor.setMinimum(1)
        self.seletor.setKeyboardTracking(False)
        self.seletor.valueChanged.connect(lambda v: self.ir_para_pagina(v - 1))
        barra.addWidget(self.seletor)
        self.total_de_paginas = QLabel(" de 0 ")
        barra.addWidget(self.total_de_paginas)
        self.acao_seguinte = self._acao("▶", "Ctrl+PgDown",
                                        lambda: self.ir_para_pagina(self.indice_pagina + 1), barra)
        barra.addSeparator()
        self.acao_reconhecer = self._acao("Reconhecer página (F5)", "F5", self.reconhecer, barra)
        self.acao_reler = self._acao("Reler pendentes", "Ctrl+R", self.reler_pendentes, barra)
        self.acao_desfazer = self._acao("Desfazer", "Ctrl+Z", self.desfazer)
        self.acao_refazer = self._acao("Refazer", "Ctrl+Y", self.refazer)
        self.acao_refazer.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        barra.addSeparator()
        self.acao_ajustar = self._acao("Ajustar à janela", "Ctrl+0", self.visor.ajustar, barra)
        barra.addSeparator()
        self.acao_modo_treino = self._acao("Modo de treino (Ctrl+T)", "Ctrl+T",
                                           self._modo_treino, barra)
        self.acao_modo_treino.setCheckable(True)
        self.acao_modo_treino.setToolTip("Arraste na página para marcar um glifo; "
                                         "Ctrl+clique junta boxes na seleção.")
        self.acao_padroes = self._acao("Padrões do livro…", "Ctrl+Shift+P",
                                       lambda: self.abas.setCurrentWidget(self.padroes))
        self.acao_opcoes = self._acao("Opções…", "Ctrl+,", self._opcoes)
        self.acao_diagramas = self._acao("Conferir diagramas…", "Ctrl+G",
                                         lambda: self.conferir_diagramas())
        self.acao_diagramas.setToolTip("A posição lida ao lado do diagrama impresso; "
                                       "também abre com um clique no diagrama.")
        self.acao_lote = self._acao("Reconhecer o livro…", "Ctrl+Shift+F5",
                                    self.reconhecer_livro)
        self.acao_cancelar_lote = self._acao("Cancelar o lote", None, self.cancelar_lote)
        self.acao_proximo_do_livro = self._acao("Próximo pendente do livro", "F6",
                                                self.proximo_pendente_do_livro)
        self.acao_exportar = self._acao("Exportar…", "Ctrl+E", self.exportar)
        self.acao_areas = self._acao("Editor de áreas (Ctrl+Shift+A)", "Ctrl+Shift+A",
                                     self._modo_areas, barra)
        self.acao_areas.setCheckable(True)
        self.acao_areas.setToolTip("Arraste para desenhar uma área; arraste dentro dela para "
                                   "mover e na borda para esticar. 1-4 trocam o tipo, Del apaga.")
        self.acao_areas_auto = self._acao("Refazer as áreas automáticas", None,
                                          self._areas_automaticas)
        self.acao_verificar = self._acao("Verificação de texto", "F7", self.verificar_texto)

        menu = self.menuBar().addMenu("&Projeto")
        for acao in (self.acao_novo, self.acao_abrir):
            menu.addAction(acao)
        menu.addSeparator()
        menu.addAction(self.acao_exportar)
        menu.addSeparator()
        menu.addAction(self._acao("Sair", "Ctrl+Q", self.close))
        menu_editar = self.menuBar().addMenu("&Editar")
        menu_editar.addAction(self.acao_desfazer)
        menu_editar.addAction(self.acao_refazer)
        menu_pagina = self.menuBar().addMenu("P&ágina")
        for acao in (self.acao_anterior, self.acao_seguinte, self.acao_reconhecer,
                     self.acao_reler, self.acao_ajustar):
            menu_pagina.addAction(acao)
        self.menu_ferramentas = self.menuBar().addMenu("&Ferramentas")
        for acao in (self.acao_modo_treino, self.acao_padroes, self.acao_diagramas):
            self.menu_ferramentas.addAction(acao)
        self.menu_ferramentas.addSeparator()
        for acao in (self.acao_areas, self.acao_areas_auto, self.acao_verificar):
            self.menu_ferramentas.addAction(acao)
        self.menu_ferramentas.addSeparator()
        for acao in (self.acao_lote, self.acao_cancelar_lote, self.acao_proximo_do_livro):
            self.menu_ferramentas.addAction(acao)
        self.menu_ferramentas.addSeparator()
        self.menu_ferramentas.addAction(self.acao_opcoes)

    def _atualizar_acoes(self) -> None:
        tem_projeto = self.projeto is not None and self.leitor is not None
        livre = not self.executor.ocupado
        total = self.fonte.total if self.fonte else 0
        self.acao_novo.setEnabled(livre)
        self.acao_abrir.setEnabled(livre)
        self.acao_reconhecer.setEnabled(tem_projeto and livre)
        self.acao_reler.setEnabled(tem_projeto and livre and bool(self.boxes))
        self.acao_anterior.setEnabled(tem_projeto and livre and self.indice_pagina > 0)
        self.acao_seguinte.setEnabled(tem_projeto and livre and self.indice_pagina < total - 1)
        self.seletor.setEnabled(tem_projeto and livre)
        self.acao_modo_treino.setEnabled(tem_projeto)
        self.acao_opcoes.setEnabled(tem_projeto and livre)
        self.acao_lote.setEnabled(tem_projeto and livre)
        self.acao_cancelar_lote.setEnabled(self._cancelar_lote is not None)
        self.acao_proximo_do_livro.setEnabled(tem_projeto and livre)
        self.acao_exportar.setEnabled(tem_projeto and livre)
        self.acao_areas.setEnabled(tem_projeto)
        self.acao_areas_auto.setEnabled(tem_projeto and livre and self.acao_areas.isChecked())
        self.acao_verificar.setEnabled(tem_projeto and livre and bool(self.boxes))
        self.acao_diagramas.setEnabled(tem_projeto and livre and bool(self.tabuleiros))
        historico = self.historicos.get(self.indice_pagina)
        desfazer = historico.proximo_a_desfazer if historico else None
        refazer = historico.proximo_a_refazer if historico else None
        self.acao_desfazer.setEnabled(tem_projeto and livre and desfazer is not None)
        self.acao_refazer.setEnabled(tem_projeto and livre and refazer is not None)
        self.acao_desfazer.setText(f"Desfazer: {desfazer}" if desfazer else "Desfazer")
        self.acao_refazer.setText(f"Refazer: {refazer}" if refazer else "Refazer")

    def _ocupado_mudou(self, ocupado: bool, titulo: str) -> None:
        self.progresso.setVisible(ocupado)
        self.progresso.setRange(0, 0)
        if ocupado:
            self.statusBar().showMessage(f"{titulo}…")
            self.treino.habilitar(False)
        elif self.atual is not None:
            self.treino.habilitar(True)
        self._atualizar_acoes()

    def _progredir(self, feito: int, total: int) -> None:
        self.progresso.setRange(0, max(total, 1))
        self.progresso.setValue(feito)

    def _falhou(self, titulo: str):
        def mostrar(mensagem: str):
            self.statusBar().showMessage(f"{titulo}: falhou.")
            QMessageBox.critical(self, titulo, mensagem)
        return mostrar

    # ------------------------------------------------------------------
    # Projeto
    # ------------------------------------------------------------------
    def novo_projeto(self) -> None:
        ultima = self.config.value("ultima_fonte", str(Path.home()))
        fonte, _ = QFileDialog.getOpenFileName(
            self, "Livro (PDF ou imagem)", ultima,
            "Livros (*.pdf *.png *.jpg *.jpeg *.tif *.tiff *.bmp)")
        if not fonte:
            return
        self.config.setValue("ultima_fonte", str(Path(fonte).parent))
        nome, ok = QInputDialog.getText(self, "Novo projeto", "Nome do livro:",
                                        text=Path(fonte).stem)
        if not ok:
            return
        padrao = self.config.value("pasta_dos_projetos", str(Path.home() / "AbbyChessCraft"))
        Path(padrao).mkdir(parents=True, exist_ok=True)
        pasta_mae = QFileDialog.getExistingDirectory(
            self, "Pasta onde guardar o projeto (sem acentos no caminho)", padrao)
        if not pasta_mae:
            return
        try:
            projeto = ProjetoDeLivro.criar(pasta_mae, nome, fonte)
        except ProjetoInvalido as erro:
            QMessageBox.warning(self, "Novo projeto", str(erro))
            return
        self.config.setValue("pasta_dos_projetos", pasta_mae)
        self._abrir(projeto)

    def abrir_projeto(self) -> None:
        padrao = self.config.value("pasta_dos_projetos", str(Path.home()))
        pasta = QFileDialog.getExistingDirectory(self, "Pasta do projeto", padrao)
        if not pasta:
            return
        try:
            projeto = ProjetoDeLivro.abrir(pasta)
        except ProjetoInvalido as erro:
            QMessageBox.warning(self, "Abrir projeto", str(erro))
            return
        self.config.setValue("pasta_dos_projetos", str(Path(pasta).parent))
        self._abrir(projeto)

    def abrir_caminho(self, pasta: str) -> None:
        """Abre um projeto pelo caminho, como o argumento da linha de comando."""
        try:
            self._abrir(ProjetoDeLivro.abrir(pasta))
        except ProjetoInvalido as erro:
            QMessageBox.warning(self, "Abrir projeto", str(erro))

    def _abrir(self, projeto: ProjetoDeLivro) -> None:
        self._salvar_pagina()
        if projeto.fonte_ausente and not self._localizar_fonte(projeto):
            projeto.fechar()
            return
        if projeto.somente_leitura:
            QMessageBox.information(
                self, "Abrir projeto",
                f"O projeto é da versão {projeto.dados.versao} do formato, mais nova que a "
                "deste programa. Ele abre só para leitura: dá para ver as páginas, mas nada "
                "do que for feito aqui é gravado.")
        if self.projeto is not None and self.projeto is not projeto:
            self.projeto.fechar()
        try:
            fonte = pg.fonte_do_projeto(projeto)
        except OSError as erro:
            QMessageBox.warning(self, "Abrir projeto", f"A fonte do livro não abriu:\n{erro}")
            return
        self.projeto, self.fonte, self.leitor = projeto, fonte, None
        self.boxes, self.atual, self.pulados, self.selecao = [], None, set(), set()
        self.lexico, self.ignoradas = None, set()
        so_leitura = " (só leitura)" if projeto.somente_leitura else ""
        self.setWindowTitle(f"{projeto.dados.nome}{so_leitura} — {TITULO}")
        self.seletor.blockSignals(True)
        self.seletor.setMaximum(fonte.total)
        self.seletor.blockSignals(False)
        self.total_de_paginas.setText(f" de {fonte.total} ")

        def carregar(_progresso):
            return LeitorDoLivro.com_modelos_globais(projeto.pasta_de_padroes,
                                                     limiares=projeto.dados.limiares)

        def pronto(leitor: LeitorDoLivro):
            self.leitor = leitor
            if leitor.rede is None:
                QMessageBox.warning(self, "Modelo", "A rede de glifos do PyBoxEditor não "
                                    "carregou. A leitura usa só os padrões e a base global.")
            lidas = projeto.paginas_lidas()
            self.ir_para_pagina(lidas[-1] if lidas else 0, salvar=False)
            self._atualizar_padroes()
            self.statusBar().showMessage(
                f"Projeto aberto. Base global com {leitor.base.total if leitor.base else 0} "
                f"referências; {leitor.arquivos_de_padrao()} padrões deste livro.", 8000)

        self.executor.rodar("Carregando os modelos", carregar, pronto,
                            self._falhou("Carregar os modelos"))

    # ------------------------------------------------------------------
    # Páginas
    # ------------------------------------------------------------------
    def ir_para_pagina(self, indice: int, salvar: bool = True) -> None:
        if self.fonte is None or self.executor.ocupado:
            return
        if not 0 <= indice < self.fonte.total:
            return
        if salvar:
            self._salvar_pagina()
        try:
            self.imagem = self.fonte.pagina(indice)
        except OSError as erro:
            QMessageBox.warning(self, "Página", str(erro))
            return
        self.indice_pagina = indice
        self.matriz = np.asarray(self.imagem.convert("L"))
        self.seletor.blockSignals(True)
        self.seletor.setValue(indice + 1)
        self.seletor.blockSignals(False)
        self.visor.mostrar_pagina(pixmap_da_pagina(self.imagem))
        self.boxes = self.projeto.carregar_pagina(indice) or []
        self.reconhecida = self.projeto.pagina_reconhecida(indice)
        self.tabuleiros = self.projeto.carregar_tabuleiros(indice)
        self.diagramas = self.projeto.carregar_diagramas(indice)
        self.atual, self.pulados, self.selecao = None, set(), set()
        self.zonas, self.zona_atual = self.projeto.carregar_zonas(indice), None
        self.desconhecidas, self.pos_verificacao = [], 0
        self.verificacao.limpar("Aperte F7 para verificar o texto da página.")
        self._atualizar_tudo()
        self._mostrar_zonas()
        if self.visor.modo_areas and not self.zonas:
            self._areas_automaticas()
        if self.boxes:
            self._ir_para_o_primeiro_pendente()
            if not self.reconhecida:
                self.statusBar().showMessage(
                    f"Página com {len(self.boxes)} glifo(s) marcados à mão e ainda não "
                    "reconhecida. O F5 reconhece o resto e mantém os quadros.", 10000)
        else:
            self.treino.limpar("Esta página ainda não foi reconhecida. Aperte F5.")
        self._atualizar_acoes()

    def _localizar_fonte(self, projeto: ProjetoDeLivro) -> bool:
        """A fonte sumiu e não foi achada pelo SHA-256: o usuário diz onde ela está."""
        QMessageBox.warning(self, "Abrir projeto",
                            f"A fonte do livro não está mais em\n{projeto.fonte}\n\nMostre "
                            "onde ela está agora; o programa confere que é o mesmo arquivo.")
        while True:
            caminho, _ = QFileDialog.getOpenFileName(
                self, "Onde está a fonte do livro?", str(projeto.pasta.parent),
                "PDF ou imagem (*.pdf *.png *.jpg *.jpeg *.tif *.tiff *.bmp)")
            if not caminho:
                return False
            try:
                projeto.relocalizar(caminho)
                return True
            except (ProjetoInvalido, OSError) as erro:
                QMessageBox.warning(self, "Abrir projeto", str(erro))

    def _pode_gravar(self) -> bool:
        """Falso, com o aviso na barra, quando o projeto está aberto só para leitura."""
        if self.projeto is not None and self.projeto.somente_leitura:
            self.statusBar().showMessage("Projeto aberto só para leitura: nada é gravado.", 6000)
            return False
        return self.projeto is not None

    def _salvar_pagina(self) -> None:
        if self.projeto is not None and self.boxes and not self.projeto.somente_leitura:
            self.diagramas = dg.para_caixas(self.tabuleiros, self.diagramas)
            self.projeto.salvar_pagina(self.indice_pagina, self.boxes, self.tabuleiros,
                                       self.diagramas, reconhecida=self.reconhecida)

    def reconhecer(self) -> None:
        if self.leitor is None or self.imagem is None:
            return
        marcados = [] if self.reconhecida else list(self.boxes)
        if self.reconhecida and self.boxes and QMessageBox.question(
                self, "Reconhecer página",
                "A página já foi reconhecida. Reconhecer de novo descarta os boxes e as "
                "correções só desta ocorrência. Os padrões ensinados ficam. Continuar?"
        ) != QMessageBox.StandardButton.Yes:
            return
        imagem, leitor, zonas = self.imagem, self.leitor, list(self.zonas)
        antes = self._instantaneo()

        def trabalho(progresso):
            segmentada = zn.segmentar(imagem, zonas, leitor)
            if marcados:
                segmentada.boxes = pg.manter_marcados(segmentada.boxes, marcados)
            pg.ler_boxes(imagem, segmentada.boxes, leitor, progresso=progresso)
            lidos = dg.ler_diagramas(imagem, segmentada.tabuleiros, escala=segmentada.escala,
                                     classificar=leitor.arbitro, boxes=segmentada.boxes)
            return segmentada, lidos

        def pronto(resultado):
            segmentada, lidos = resultado
            boxes = segmentada.boxes
            self.boxes, self.tabuleiros = boxes, segmentada.tabuleiros
            # A conferência de antes vale mais que a releitura do mesmo tabuleiro.
            self.diagramas = dg.mesclar(lidos, self.diagramas)
            self.atual, self.pulados, self.selecao = None, set(), set()
            self.reconhecida = True
            self._registrar("Reconhecer a página", antes)
            self._salvar_pagina()
            self._atualizar_tudo()
            self._ir_para_o_primeiro_pendente()
            resumo = pg.resumir(boxes, leitor)
            areas = f", pelas {len(zonas)} área(s) da página" if zonas else ""
            self.statusBar().showMessage(
                f"{resumo.boxes} boxes, {resumo.pendentes} a revisar, "
                f"{len(self.tabuleiros)} diagrama(s){areas}.", 8000)

        self.executor.rodar("Reconhecendo a página", trabalho, pronto,
                            self._falhou("Reconhecer página"), self._progredir)

    def reler_pendentes(self, tudo: bool = False) -> None:
        if self.leitor is None or not self.boxes:
            return
        imagem, boxes, leitor = self.imagem, self.boxes, self.leitor

        def trabalho(progresso):
            return pg.ler_boxes(imagem, boxes, leitor, so_pendentes=not tudo, progresso=progresso)

        def pronto(resumo):
            self._salvar_pagina()
            self._atualizar_tudo()
            self._ir_para_o_primeiro_pendente()
            self.statusBar().showMessage(f"Relida. {resumo.pendentes} a revisar.", 6000)

        self.executor.rodar("Relendo", trabalho, pronto, self._falhou("Reler"), self._progredir)

    # ------------------------------------------------------------------
    # A fila de revisão
    # ------------------------------------------------------------------
    def _fila(self) -> List[int]:
        """Pendentes, com os pulados no fim, na ordem em que foram pulados."""
        if self.leitor is None:
            return []
        fila = pg.fila_de_revisao(self.boxes, self.leitor)
        return [i for i in fila if i not in self.pulados] + [i for i in fila if i in self.pulados]

    def _ir_para_o_primeiro_pendente(self) -> None:
        fila = self._fila()
        if fila:
            self._mostrar_box(fila[0])
        else:
            self.atual = None
            self.visor.selecionar(None)
            self.treino.limpar("Nada a revisar nesta página. Clique num box para corrigi-lo, "
                               "ou vá para o próximo pendente do livro (F6).")

    def _andar_na_fila(self, passo: int) -> None:
        fila = self._fila()
        if not fila:
            self._ir_para_o_primeiro_pendente()
            return
        if passo > 0 and self.atual is not None and self.atual in fila:
            self.pulados.add(self.atual)
            fila = self._fila()
            self._mostrar_box(fila[0])
            return
        posicao = fila.index(self.atual) if self.atual in fila else 0
        self._mostrar_box(fila[(posicao + passo) % len(fila)])

    def _mostrar_box(self, indice: int) -> None:
        self.atual = indice
        fila = self._fila()
        posicao = (f"Pendente {fila.index(indice) + 1} de {len(fila)}" if indice in fila
                   else "Box fora da fila (já confirmado ou confiável)")
        self.treino.mostrar(self.matriz, self.boxes[indice], posicao)
        self.visor.selecionar(indice)

    def _box_clicado(self, indice: int) -> None:
        if not self.executor.ocupado:
            self._mostrar_box(indice)

    # ------------------------------------------------------------------
    # Decisões
    # ------------------------------------------------------------------
    def _alvos(self) -> List[int]:
        """O que a decisão vale: a seleção inteira, ou só o box em revisão."""
        if self.atual is None:
            return []
        return sorted(self.selecao | {self.atual})

    def _ensinar(self, char: str) -> None:
        if self.atual is None or self.leitor is None:
            return
        indices, imagem, boxes = self._alvos(), self.imagem, self.boxes
        leitor, projeto, pagina = self.leitor, self.projeto, self.indice_pagina
        antes = self._instantaneo()

        def trabalho(_progresso):
            return pg.ensinar_varios(imagem, boxes, indices, char, leitor, projeto, pagina)

        def pronto(resolvidos: int):
            self._registrar(f"Ensinar '{char}'", antes)
            self.pulados.difference_update(indices)
            self.selecao = set()
            self._salvar_pagina()
            self._atualizar_tudo()
            self._atualizar_padroes()
            self._ir_para_o_primeiro_pendente()
            amostras = f" com {len(indices)} amostras" if len(indices) > 1 else ""
            extra = f" e resolveu mais {resolvidos} na página" if resolvidos else ""
            self.statusBar().showMessage(f"Padrão '{char}' ensinado{amostras}{extra}.", 5000)

        self.executor.rodar("Ensinando", trabalho, pronto, self._falhou("Ensinar"))

    def _so_corrigir(self, char: str) -> None:
        if self.atual is None:
            return
        antes = self._instantaneo()
        for indice in self._alvos():
            pg.confirmar(self.boxes, indice, char)
        self._registrar(f"Corrigir para '{char}'", antes)
        for indice in self._alvos():
            self.pulados.discard(indice)
        self.selecao = set()
        self._salvar_pagina()
        self._atualizar_tudo()
        self._ir_para_o_primeiro_pendente()

    def _descartar(self) -> None:
        if self.atual is None:
            return
        removido = self.atual
        antes = self._instantaneo()
        pg.descartar(self.boxes, removido)
        self._registrar("Descartar box", antes)
        # Os índices depois do removido andam uma casa para trás.
        self.pulados = {i - (i > removido) for i in self.pulados if i != removido}
        self.atual, self.selecao = None, set()
        self._salvar_pagina()
        self._atualizar_tudo()
        self._ir_para_o_primeiro_pendente()

    # ------------------------------------------------------------------
    # Editar os boxes
    # ------------------------------------------------------------------
    def _pode_editar(self) -> bool:
        return self.leitor is not None and bool(self.boxes) and not self.executor.ocupado

    def _depois_de_editar(self, mostrar: int, mensagem: str) -> None:
        self.selecao = set()
        self._salvar_pagina()
        self._atualizar_tudo()
        self._mostrar_box(mostrar)
        self.statusBar().showMessage(mensagem, 5000)

    def _dividir(self, coluna: Optional[int]) -> None:
        if self.atual is not None:
            self._dividir_box(self.atual, coluna)

    def _dividir_box(self, indice: int, coluna: Optional[int]) -> None:
        """Divide o box e mostra a primeira parte, já relida, para ensinar."""
        if not self._pode_editar():
            return
        antes = self._instantaneo()
        try:
            esquerda, _ = pg.dividir(self.imagem, self.boxes, indice, self.leitor, x=coluna)
        except ValueError as erro:
            self.statusBar().showMessage(f"Não dividiu: {erro}", 6000)
            return
        self._registrar("Dividir box", antes)
        # Os índices depois do dividido andam uma casa para a frente.
        self.pulados = {i + (i > indice) for i in self.pulados if i != indice}
        self._depois_de_editar(esquerda, "Box dividido em dois; as partes foram relidas.")

    def _juntar(self, passo: int) -> None:
        if self.atual is not None:
            self._juntar_box(self.atual, passo)

    def _juntar_box(self, indice: int, passo: int) -> None:
        if not self._pode_editar():
            return
        outro = pg.vizinho(self.boxes, indice, passo)
        if outro is None:
            lado = "seguinte" if passo > 0 else "anterior"
            self.statusBar().showMessage(f"Não há box {lado} nesta linha para juntar.", 6000)
            return
        primeiro, segundo = sorted((indice, outro))
        antes = self._instantaneo()
        novo = pg.juntar(self.imagem, self.boxes, primeiro, segundo, self.leitor)
        self._registrar("Juntar boxes", antes)
        # O segundo sai; os índices depois dele andam uma casa para trás.
        self.pulados = {i - (i > segundo) for i in self.pulados if i not in (primeiro, segundo)}
        self._depois_de_editar(novo, "Boxes juntados; o box novo foi relido.")

    def _ajustar(self, esquerda: int, cima: int, direita: int, baixo: int) -> None:
        if self.atual is None or not self._pode_editar():
            return
        antes = self._instantaneo()
        try:
            pg.ajustar(self.imagem, self.boxes, self.atual, self.leitor, esquerda=esquerda,
                       cima=cima, direita=direita, baixo=baixo)
        except ValueError as erro:
            self.statusBar().showMessage(f"Não ajustou: {erro}", 6000)
            return
        # Os Alt+seta seguidos no mesmo box viram um passo só.
        self._registrar("Ajustar bordas", antes, juntar=("ajustar", self.atual))
        b = self.boxes[self.atual]
        self._depois_de_editar(self.atual, f"Box em ({b.x1}, {b.y1})–({b.x2}, {b.y2}).")

    # ------------------------------------------------------------------
    # Desfazer e refazer
    # ------------------------------------------------------------------
    def _instantaneo(self) -> hs.Instantaneo:
        """A página agora, com os padrões que o livro tem, para comparar depois."""
        estado = hs.instantaneo(self.boxes, self.diagramas)
        estado.reconhecida = self.reconhecida
        estado.padroes = (frozenset(c for v in self.leitor.padroes_por_caractere().values()
                                    for c in v) if self.leitor is not None else frozenset())
        return estado

    def _registrar(self, descricao: str, antes: hs.Instantaneo, *, juntar=None) -> None:
        """Guarda o passo que levou a página de `antes` até agora."""
        depois = self._instantaneo()
        criados = []
        if self.leitor is not None:
            for caminho in sorted(depois.padroes - antes.padroes):
                criados.append(self.leitor.padroes.guardar(caminho))
        historico = self.historicos.setdefault(self.indice_pagina, hs.Historico())
        historico.registrar(hs.Passo(descricao, antes, depois, criados, juntar=juntar))
        self._atualizar_acoes()

    def desfazer(self) -> None:
        historico = self.historicos.get(self.indice_pagina)
        if historico is None or self.executor.ocupado or self.leitor is None:
            return
        passo = historico.desfazer()
        if passo is None:
            return
        for amostra in passo.criados:
            if amostra.caminho.exists():
                self.leitor.esquecer(amostra.caminho)
        self._voltar_para(passo.antes, f"Desfeito: {passo.descricao}.")

    def refazer(self) -> None:
        historico = self.historicos.get(self.indice_pagina)
        if historico is None or self.executor.ocupado or self.leitor is None:
            return
        passo = historico.refazer()
        if passo is None:
            return
        for amostra in passo.criados:
            self.leitor.padroes.restaurar(amostra)
        self._voltar_para(passo.depois, f"Refeito: {passo.descricao}.")

    def _voltar_para(self, estado: hs.Instantaneo, mensagem: str) -> None:
        copia = hs.instantaneo(estado.boxes, estado.diagramas)
        self.boxes, self.diagramas = copia.boxes, copia.diagramas
        self.reconhecida = estado.reconhecida
        self.atual, self.pulados, self.selecao = None, set(), set()
        self._salvar_pagina()
        self._atualizar_tudo()
        self._atualizar_padroes()
        self._ir_para_o_primeiro_pendente()
        self._atualizar_acoes()
        self.statusBar().showMessage(mensagem, 6000)

    # ------------------------------------------------------------------
    # Modo de treino e ferramentas
    # ------------------------------------------------------------------
    def _modo_treino(self, sim: bool) -> None:
        if sim and self.acao_areas.isChecked():
            self.acao_areas.setChecked(False)
            self._modo_areas(False)
        self.visor.definir_modo_treino(sim)
        self.statusBar().showMessage(
            "Modo de treino: arraste em volta de um glifo para marcá-lo; Ctrl+clique junta "
            "boxes na seleção." if sim else "Modo de treino desligado.", 8000)

    def _criar_box(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """O quadro desenhado vira box, é lido e vai para o painel para ensinar."""
        if self.leitor is None or self.imagem is None or self.executor.ocupado:
            return
        antes = list(self.boxes)
        pagina_antes = self._instantaneo()
        try:
            indice = pg.criar_box(self.imagem, self.boxes, (x1, y1, x2, y2), self.leitor)
        except ValueError as erro:
            self.statusBar().showMessage(f"Não marcou: {erro}", 6000)
            return
        self._registrar("Marcar glifo", pagina_antes)
        # A ordem de leitura foi refeita: os pulados seguem o próprio box.
        novos = {id(b): i for i, b in enumerate(self.boxes)}
        self.pulados = {novos[id(antes[i])] for i in self.pulados if id(antes[i]) in novos}
        tirados = len(antes) + 1 - len(self.boxes)
        extra = f", no lugar de {tirados} box(es) de dentro" if tirados else ""
        self._depois_de_editar(indice, f"Glifo marcado{extra}. Digite o caractere e Enter.")

    def _alternar_na_selecao(self, indice: int) -> None:
        if self.executor.ocupado or not 0 <= indice < len(self.boxes):
            return
        if indice in self.selecao or (indice == self.atual and not self.selecao):
            self.selecao.discard(indice)
            if indice == self.atual and self.selecao:
                self._mostrar_box(min(self.selecao))
        else:
            if self.atual is not None:
                self.selecao.add(self.atual)
            self.selecao.add(indice)
            self._mostrar_box(indice)
        self._mostrar_selecao()

    def _limpar_selecao(self) -> None:
        self.selecao = set()
        self._mostrar_selecao()

    def _mostrar_selecao(self) -> None:
        self.visor.marcar_selecao(self.selecao)
        self.treino.mostrar_selecao(len(self._alvos()) if self.selecao else 0)

    def _opcoes(self) -> None:
        if self.projeto is None or self.leitor is None:
            return
        dialogo = DialogoDeOpcoes(self.projeto.dados.limiares, self)
        if dialogo.exec() != DialogoDeOpcoes.DialogCode.Accepted:
            return
        self.aplicar_limiares(dialogo.limiares())

    def aplicar_limiares(self, limiares) -> None:
        """Grava os limiares no projeto e refaz a fila com eles."""
        self.projeto.dados.limiares = limiares
        if self._pode_gravar():
            self.projeto.salvar()
        self.leitor.trocar_limiares(limiares)
        self._atualizar_tudo()
        if self.boxes:
            self._ir_para_o_primeiro_pendente()
        self.statusBar().showMessage("Limiares do livro gravados.", 5000)

    def _esquecer(self, caminhos: list) -> None:
        if self.leitor is None:
            return
        resposta = QMessageBox.question(
            self, "Esquecer padrões",
            f"Apagar {len(caminhos)} amostra(s) dos padrões deste livro? A página atual "
            "será relida sem elas.")
        if resposta != QMessageBox.StandardButton.Yes:
            return
        for caminho in caminhos:
            self.leitor.esquecer(caminho)
        self._atualizar_padroes()
        self.reler_pendentes(tudo=True)

    # ------------------------------------------------------------------
    # Editor de áreas
    # ------------------------------------------------------------------
    def _modo_areas(self, sim: bool) -> None:
        """Liga o editor de áreas, que desliga o modo de treino: os dois usam o arraste."""
        if sim and self.acao_modo_treino.isChecked():
            self.acao_modo_treino.setChecked(False)
            self.visor.definir_modo_treino(False)
        self.visor.definir_modo_areas(sim)
        self._mostrar_zonas()
        self._atualizar_acoes()
        if sim and not self.zonas and self.imagem is not None:
            self._areas_automaticas()
        elif sim:
            self.statusBar().showMessage(
                "Editor de áreas: arraste para desenhar, dentro para mover, na borda para "
                "esticar; 1 texto, 2 diagrama, 3 imagem, 4 ignorar; Del apaga. F5 reconhece "
                "pelas áreas.", 10000)
        else:
            self.statusBar().showMessage("Editor de áreas desligado.", 5000)

    def _areas_automaticas(self) -> None:
        """As áreas que a segmentação sugere: pelos boxes lidos, ou segmentando agora."""
        if self.imagem is None or self.executor.ocupado:
            return
        largura, altura = self.imagem.size
        if self.boxes:
            self._trocar_zonas(zn.automaticas(self.boxes, self.tabuleiros, largura, altura))
            return
        imagem, leitor = self.imagem, self.leitor
        indice = self.indice_pagina

        def trabalho(_progresso):
            bruta = pg.segmentar_pagina(imagem, leitor)
            return zn.automaticas(bruta.boxes, bruta.tabuleiros, largura, altura)

        def pronto(zonas):
            if self.indice_pagina == indice:
                self._trocar_zonas(zonas)

        self.executor.rodar("Achando as áreas", trabalho, pronto, self._falhou("Áreas"))

    def _trocar_zonas(self, zonas) -> None:
        self.zonas, self.zona_atual = list(zonas), None
        self._gravar_zonas()
        tipos = {}
        for z in self.zonas:
            tipos[zn.NOMES[z.tipo].lower()] = tipos.get(zn.NOMES[z.tipo].lower(), 0) + 1
        resumo = ", ".join(f"{n} {t}" for t, n in tipos.items()) or "nenhuma"
        self.statusBar().showMessage(f"Áreas automáticas: {resumo}. Corrija e aperte F5.", 10000)

    def _gravar_zonas(self) -> None:
        if self._pode_gravar():
            self.projeto.salvar_zonas(self.indice_pagina, self.zonas)
        self._mostrar_zonas()

    def _mostrar_zonas(self) -> None:
        self.visor.mostrar_zonas(self.zonas, self.zona_atual)

    def _zona_desenhada(self, x1: int, y1: int, x2: int, y2: int) -> None:
        if self.imagem is None:
            return
        largura, altura = self.imagem.size
        try:
            zona = zn.nova(zn.TEXTO, (x1, y1, x2, y2), largura, altura)
        except ValueError as erro:
            self.statusBar().showMessage(f"Não criou a área: {erro}", 6000)
            return
        self.zonas.append(zona)
        self.zona_atual = len(self.zonas) - 1
        self._gravar_zonas()
        self.statusBar().showMessage(
            f"Área {self.zona_atual + 1} de texto criada. 2 diagrama, 3 imagem, 4 ignorar.", 6000)

    def _zona_escolhida(self, indice: int) -> None:
        self.zona_atual = indice if 0 <= indice < len(self.zonas) else None
        self._mostrar_zonas()

    def _zona_arrastada(self, indice: int, bordas: str, dx: int, dy: int) -> None:
        if not 0 <= indice < len(self.zonas) or self.imagem is None:
            return
        largura, altura = self.imagem.size
        self.zonas[indice] = zn.arrastar(self.zonas[indice], bordas, dx, dy, largura, altura)
        self.zona_atual = indice
        self._gravar_zonas()

    def _zona_apagada(self, indice: int) -> None:
        if not 0 <= indice < len(self.zonas):
            return
        del self.zonas[indice]
        self.zona_atual = None
        self._gravar_zonas()
        aviso = "" if self.zonas else " Sem áreas, a página volta à segmentação automática."
        self.statusBar().showMessage(f"Área apagada.{aviso}", 6000)

    def _zona_tipo(self, indice: int, tipo: str) -> None:
        if not 0 <= indice < len(self.zonas):
            return
        zn.trocar_tipo(self.zonas, indice, tipo)
        self.zona_atual = indice
        self._gravar_zonas()
        self.statusBar().showMessage(f"Área {indice + 1}: {zn.NOMES[tipo].lower()}.", 5000)

    # ------------------------------------------------------------------
    # Verificação de texto
    # ------------------------------------------------------------------
    def verificar_texto(self) -> None:
        """Carrega o léxico do livro, se preciso, e mostra a primeira palavra desconhecida."""
        if self.projeto is None or not self.boxes or self.executor.ocupado:
            return
        if self.lexico is not None:
            self.pos_verificacao = 0
            if self.abas.currentWidget() is self.verificacao:
                self._recontar_desconhecidas(0)
            else:
                self.abas.setCurrentWidget(self.verificacao)  # `_aba_mudou` reconta
            return
        projeto = self.projeto
        extras = [projeto.fonte.with_name(projeto.fonte.stem + ".lexico.txt")]

        def trabalho(_progresso):
            return vf.carregar_lexico(projeto.dados.idioma, projeto.arquivo_do_lexico, extras)

        def pronto(lexico):
            self.lexico = lexico
            if not lexico.sinaliza:
                self.statusBar().showMessage(
                    f"Não há léxico para o idioma '{projeto.dados.idioma}' no PyBoxEditor.", 8000)
            self.verificar_texto()

        self.executor.rodar("Carregando o léxico", trabalho, pronto, self._falhou("Léxico"))

    def _recontar_desconhecidas(self, posicao: int) -> None:
        if self.lexico is None:
            return
        self.desconhecidas = vf.desconhecidas(self.boxes, self.lexico, self.ignoradas)
        self._mostrar_palavra(posicao)

    def _mostrar_palavra(self, posicao: int) -> None:
        if not self.desconhecidas:
            self.pos_verificacao = 0
            self.visor.marcar_palavra(None)
            self.verificacao.limpar("Nenhuma palavra desconhecida nesta página.")
            return
        self.pos_verificacao = posicao % len(self.desconhecidas)
        palavra = self.desconhecidas[self.pos_verificacao]
        self.verificacao.mostrar(self.matriz, self.boxes, palavra, self.pos_verificacao,
                                 len(self.desconhecidas))
        self.visor.marcar_palavra(vf.caixa_da_palavra(self.boxes, palavra.indices))

    def _palavra_atual(self) -> Optional[vf.Desconhecida]:
        if not self.desconhecidas:
            return None
        return self.desconhecidas[self.pos_verificacao % len(self.desconhecidas)]

    def _andar_na_verificacao(self, passo: int) -> None:
        if self.desconhecidas:
            self._mostrar_palavra(self.pos_verificacao + passo)

    def _corrigir_palavra(self, texto: str, ensinar: bool = False) -> None:
        """Grava o texto nos glifos da palavra; com `ensinar`, ensina os que mudaram."""
        palavra = self._palavra_atual()
        if palavra is None or self.executor.ocupado:
            return
        antes = self._instantaneo()
        try:
            mudados = vf.corrigir(self.boxes, palavra.indices, texto)
        except ValueError as erro:
            self.statusBar().showMessage(f"Não corrigiu: {erro}", 8000)
            return
        posicao = self.pos_verificacao

        def depois(mensagem: str) -> None:
            self._registrar(f"Corrigir '{texto}'", antes)
            self._salvar_pagina()
            self._atualizar_tudo()
            self._recontar_desconhecidas(posicao)
            atual = self._palavra_atual()
            if atual is not None and atual.indices == palavra.indices:
                self._mostrar_palavra(posicao + 1)  # continua desconhecida: segue adiante
            self.statusBar().showMessage(mensagem, 6000)

        if not ensinar or not mudados or self.leitor is None:
            depois(f"'{texto}': {len(mudados)} glifo(s) corrigido(s).")
            return
        por_char: dict = {}
        for indice, char in mudados:
            por_char.setdefault(char, []).append(indice)
        imagem, boxes, leitor = self.imagem, self.boxes, self.leitor
        projeto, pagina = self.projeto, self.indice_pagina

        def trabalho(_progresso):
            return sum(pg.ensinar_varios(imagem, boxes, indices, char, leitor, projeto, pagina)
                       for char, indices in por_char.items())

        def pronto(resolvidos: int):
            self._atualizar_padroes()
            extra = f"; os padrões resolveram mais {resolvidos} na página" if resolvidos else ""
            depois(f"'{texto}': {len(mudados)} glifo(s) corrigido(s) e ensinado(s){extra}.")

        self.executor.rodar("Ensinando", trabalho, pronto, self._falhou("Ensinar"))

    def _ignorar_todas(self) -> None:
        palavra = self._palavra_atual()
        if palavra is not None:
            self.ignoradas.add(palavra.palavra.lower())
            self._recontar_desconhecidas(self.pos_verificacao)

    def _adicionar_ao_lexico(self) -> None:
        palavra = self._palavra_atual()
        if palavra is None or self.lexico is None or self.projeto is None:
            return
        texto = self.verificacao.campo.text().strip() or palavra.palavra
        if not self._pode_gravar():
            return
        if not vf.adicionar(self.lexico, texto, self.projeto.arquivo_do_lexico):
            self.statusBar().showMessage(f"'{texto}' não entra no dicionário (já está, ou não "
                                         "é só de letras).", 6000)
            return
        self._recontar_desconhecidas(self.pos_verificacao)
        self.statusBar().showMessage(f"'{texto}' entrou no dicionário do livro.", 6000)

    def _glifo_da_palavra(self, indice: int) -> None:
        """O glifo clicado no recorte vai para o painel de treino, para editar."""
        if 0 <= indice < len(self.boxes) and not self.executor.ocupado:
            self.abas.setCurrentWidget(self.treino)
            self._mostrar_box(indice)

    def _aba_mudou(self, _indice: int) -> None:
        """Voltar à verificação refaz a lista: o treino pode ter dividido ou juntado glifos."""
        if self.abas.currentWidget() is self.verificacao and self.lexico is not None \
                and self.boxes:
            self._recontar_desconhecidas(self.pos_verificacao)
        elif self.abas.currentWidget() is not self.verificacao:
            self.visor.marcar_palavra(None)

    # ------------------------------------------------------------------
    # O livro inteiro: lote, revisão entre páginas e exportação
    # ------------------------------------------------------------------
    def reconhecer_livro(self) -> None:
        """Reconhece um intervalo de páginas em segundo plano, gravando cada uma."""
        if self.leitor is None or self.fonte is None or self.executor.ocupado:
            return
        total = self.fonte.total
        texto, ok = QInputDialog.getText(
            self, "Reconhecer o livro",
            f"Páginas a reconhecer (de 1 a {total}; por exemplo 26-27, 30):", text=f"1-{total}")
        if not ok:
            return
        try:
            indices = livro.interpretar_intervalo(texto, total)
        except ValueError as erro:
            QMessageBox.warning(self, "Reconhecer o livro", str(erro))
            return
        refazer = False
        lidas = livro.ja_lidas(self.projeto, indices)
        if lidas:
            botoes = QMessageBox.StandardButton
            resposta = QMessageBox.question(
                self, "Reconhecer o livro",
                f"{len(lidas)} das {len(indices)} páginas já foram reconhecidas. Reconhecer "
                "essas de novo?\n\nSim descarta os boxes delas e as correções só desta "
                "ocorrência (os padrões ficam). Não as pula e lê só as outras.",
                botoes.Yes | botoes.No | botoes.Cancel, botoes.No)
            if resposta == botoes.Cancel:
                return
            refazer = resposta == botoes.Yes
        self._salvar_pagina()
        projeto, fonte, leitor = self.projeto, self.fonte, self.leitor
        cancelar = self._cancelar_lote = threading.Event()

        def trabalho(progresso):
            return livro.reconhecer_paginas(projeto, fonte, leitor, indices, refazer=refazer,
                                            progresso=progresso, cancelado=cancelar.is_set)

        def progredir(feitas: int, total_do_lote: int) -> None:
            self._progredir(feitas, total_do_lote)
            if not cancelar.is_set():
                self.statusBar().showMessage(
                    f"Reconhecendo o livro: {feitas} de {total_do_lote} páginas…")

        def fim() -> None:
            self._cancelar_lote = None
            self._atualizar_acoes()

        def pronto(resultado: livro.ResultadoDoLote):
            fim()
            if self.indice_pagina in resultado.lidas:
                self.ir_para_pagina(self.indice_pagina, salvar=False)
            partes = [f"{len(resultado.lidas)} página(s) reconhecida(s)",
                      f"{resultado.total_de_pendentes} glifo(s) a revisar",
                      f"{sum(resultado.diagramas.values())} diagrama(s) lido(s) em FEN"]
            if resultado.puladas:
                partes.append(f"{len(resultado.puladas)} já lida(s) pulada(s)")
            if resultado.falhas:
                partes.append("falharam: " + ", ".join(str(i + 1) for i in resultado.falhas))
            inicio = "Lote cancelado: " if resultado.cancelado else "Lote concluído: "
            self.statusBar().showMessage(
                inicio + "; ".join(partes) + ". F6 vai ao próximo pendente do livro.", 15000)

        def falhou(mensagem: str):
            fim()
            self._falhou("Reconhecer o livro")(mensagem)

        self.executor.rodar("Reconhecendo o livro", trabalho, pronto, falhou, progredir)
        self._atualizar_acoes()

    def cancelar_lote(self) -> None:
        """Pede o fim do lote; a página em leitura não é gravada pela metade."""
        if self._cancelar_lote is not None:
            self._cancelar_lote.set()
            self.statusBar().showMessage("Cancelando o lote ao fim da leitura em curso…")

    def proximo_pendente_do_livro(self) -> None:
        """O pendente desta página ou, se ela acabou, a próxima página com pendentes."""
        if self.leitor is None or self.projeto is None or self.executor.ocupado:
            return
        if self._fila():
            self._ir_para_o_primeiro_pendente()
            return
        self._salvar_pagina()
        proxima = livro.proxima_com_pendentes(self.projeto, self.leitor.limiares,
                                              self.indice_pagina)
        if proxima is None or proxima == self.indice_pagina:
            self.statusBar().showMessage("Nada a revisar nas páginas reconhecidas do livro.",
                                         8000)
            return
        self.ir_para_pagina(proxima)
        self.statusBar().showMessage(f"Página {proxima + 1}: {len(self._fila())} a revisar.",
                                     6000)

    def exportar(self) -> None:
        """Escreve as páginas reconhecidas em PDF pesquisável, DOCX ou EPUB."""
        if self.projeto is None or self.executor.ocupado:
            return
        self._salvar_pagina()
        if not self.projeto.paginas_lidas():
            QMessageBox.information(self, "Exportar", "Nenhuma página foi reconhecida ainda.")
            return
        filtros = {"PDF pesquisável (*.pdf)": ".pdf", "Word (*.docx)": ".docx",
                   "EPUB (*.epub)": ".epub"}
        padrao = self.config.value("pasta_de_exportacao", str(self.projeto.pasta))
        caminho, filtro = QFileDialog.getSaveFileName(
            self, "Exportar o livro", str(Path(padrao) / self.projeto.pasta.name),
            ";;".join(filtros))
        if not caminho:
            return
        destino = Path(caminho)
        if destino.suffix.lower() not in filtros.values():
            destino = destino.with_suffix(filtros.get(filtro, ".pdf"))
        self.config.setValue("pasta_de_exportacao", str(destino.parent))
        projeto = self.projeto

        def trabalho(progresso):
            return ex.exportar(projeto, destino, progresso=progresso)

        def pronto(resumo: str):
            self.statusBar().showMessage(f"Exportado em {destino.name}: {resumo}", 15000)

        self.executor.rodar(f"Exportando {destino.suffix[1:].upper()}", trabalho, pronto,
                            self._falhou("Exportar"), self._progredir)

    # ------------------------------------------------------------------
    # Atualizar a tela
    # ------------------------------------------------------------------
    def _atualizar_tudo(self) -> None:
        pendentes = set(self._fila())
        self.diagramas = dg.para_caixas(self.tabuleiros, self.diagramas)
        self.visor.mostrar_boxes(self.boxes, pendentes, [d.caixa for d in self.diagramas],
                                 [cores.cor_do_diagrama(d) for d in self.diagramas])
        self._mostrar_selecao()
        self.texto.setPlainText(dg.texto_da_pagina(self.boxes, self.diagramas)
                                if self.boxes or self.diagramas else "")
        if self.leitor is not None:
            por_char = self.leitor.padroes_por_caractere()
            self.treino.mostrar_contagens(len(pendentes), len(self.boxes),
                                          sum(len(v) for v in por_char.values()), len(por_char))

    def _atualizar_padroes(self) -> None:
        if self.leitor is not None:
            self.padroes.atualizar(self.leitor.padroes_por_caractere())

    # ------------------------------------------------------------------
    # Os diagramas
    # ------------------------------------------------------------------
    def _diagrama_clicado(self, x: int, y: int) -> None:
        indice = dg.diagrama_em(self.diagramas, x, y)
        if indice is not None:
            self.conferir_diagramas(indice)

    def conferir_diagramas(self, indice: Optional[int] = None) -> None:
        """Abre a conferência no diagrama pedido, ou no primeiro ainda não conferido.

        Os que ainda não foram lidos (página gravada antes da leitura dos
        diagramas) são lidos antes, fora da thread da interface.
        """
        if self.leitor is None or self.imagem is None or self.executor.ocupado:
            return
        self.diagramas = dg.para_caixas(self.tabuleiros, self.diagramas)
        if not self.diagramas:
            self.statusBar().showMessage("Não há diagrama nesta página.", 5000)
            return
        if indice is None:
            indice = next((i for i, d in enumerate(self.diagramas) if not d.conferido), 0)
        por_ler = [i for i, d in enumerate(self.diagramas) if not d.lido and not d.erro]
        if not por_ler:
            self._abrir_conferencia(indice)
            return
        imagem, leitor, boxes = self.imagem, self.leitor, list(self.boxes)
        caixas = [self.diagramas[i].caixa for i in por_ler]

        def trabalho(_progresso):
            return dg.ler_diagramas(imagem, caixas, classificar=leitor.arbitro, boxes=boxes)

        def pronto(lidos):
            for i, lido in zip(por_ler, lidos):
                self.diagramas[i] = lido
            self._salvar_pagina()
            self._atualizar_tudo()
            self._abrir_conferencia(indice)

        self.executor.rodar("Lendo os diagramas", trabalho, pronto,
                            self._falhou("Ler os diagramas"))

    def _abrir_conferencia(self, indice: int) -> Optional[DialogoDeDiagrama]:
        d = self.diagramas[indice]
        if not d.lido:
            self.statusBar().showMessage(f"O diagrama não foi lido: {d.erro}", 8000)
            return None
        dialogo = DialogoDeDiagrama(self.matriz, self.diagramas, indice, self)
        dialogo.conferido.connect(self._aplicar_conferencia)
        self.dialogo_diagrama = dialogo
        dialogo.open()
        return dialogo

    def _aplicar_conferencia(self, indice: int, tabuleiro, tudo: bool) -> None:
        """Grava o diagrama conferido, refaz o texto e guarda as amostras no projeto."""
        antes = self._instantaneo()
        self.diagramas[indice] = self.diagramas[indice].conferir(tabuleiro)
        self._registrar(f"Conferir o diagrama {indice + 1}", antes)
        self._salvar_pagina()
        self._atualizar_tudo()
        mensagem = f"Diagrama {indice + 1} conferido: {self.diagramas[indice].fen}"
        if tudo or tabuleiro.corrigidas:
            origem = f"p{self.indice_pagina + 1:04d}"
            try:
                caminhos = dg.guardar_amostras(self.imagem, self.diagramas[indice], tabuleiro,
                                               self.projeto.pasta, origem, tudo=tudo)
            except Exception as erro:  # disco cheio, pasta sem permissão, modelo ausente
                log.exception("as amostras do diagrama não foram guardadas")
                mensagem += f". As amostras não foram guardadas: {erro}"
            else:
                mensagem += f"; {len(caminhos)} amostra(s) guardadas no projeto"
        self.statusBar().showMessage(mensagem, 8000)

    def closeEvent(self, evento):
        if self.executor.ocupado:
            self.cancelar_lote()
            self.statusBar().showMessage("Esperando a tarefa em andamento terminar…")
            self.executor.esperar()
        self._salvar_pagina()
        if self.projeto is not None:
            self.projeto.fechar()
        super().closeEvent(evento)
