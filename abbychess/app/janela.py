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

A janela só compõe, liga sinais a comandos e desenha o que os eventos dizem (SPEC §14.1).
Os comandos e o estado estão nos controladores sem Qt (`abbychess.controlador`,
`abbychess.controladores`); as ações e os menus, em `app/acoes.py`; os diálogos, em
`app/dialogos.py`.
"""

from __future__ import annotations

import logging
from typing import Optional

from collections import OrderedDict

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QDockWidget, QInputDialog, QMainWindow, QPlainTextEdit,
                               QProgressBar, QTabWidget)

from abbychess.app import acoes, dialogos
from abbychess.app.desenho import DesenhoDaJanela
from abbychess.app.dialogo_diagrama import DialogoDeDiagrama
from abbychess.app.opcoes import DialogoDeOpcoes
from abbychess.app.painel_padroes import PainelDePadroes
from abbychess.app.painel_treino import FONTE_DE_SIMBOLOS, PainelDeTreino
from abbychess.app.painel_verificacao import PainelDeVerificacao
from abbychess.app.trabalho import Executor
from abbychess.app.visor import VisorDePagina
from abbychess.controlador import ControladorDePagina, Eventos
from abbychess.controladores import (ControladorDeDiagramas, ControladorDeLayout,
                                     ControladorDeVerificacao, ControladorDoLivro)

log = logging.getLogger(__name__)

TITULO = "AbbyChessCraft"


class JanelaPrincipal(DesenhoDaJanela, QMainWindow):
    #: Da thread do gravador: a página `indice` não gravou (o erro).
    falha_de_gravacao = Signal(object, object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(TITULO)
        self.resize(1500, 950)
        self.config = QSettings("AbbyChessCraft", "AbbyChessCraft")
        self.dialogo_diagrama: Optional[DialogoDeDiagrama] = None

        self.executor = Executor(self)
        self.eventos = Eventos()
        self.pagina = ControladorDePagina(self.eventos, self.executor)
        self.areas = ControladorDeLayout(self.pagina)
        self.verificador = ControladorDeVerificacao(self.pagina)
        self.conferencia = ControladorDeDiagramas(self.pagina)
        self.livro = ControladorDoLivro(self.pagina)
        self._montar_paineis()
        acoes.montar(self)
        self._ligar_eventos()
        self.progresso = QProgressBar()
        self.progresso.setMaximumWidth(260)
        self.progresso.hide()
        self.statusBar().addPermanentWidget(self.progresso)
        self.treino.limpar("Crie um projeto (Ctrl+N) ou abra um existente (Ctrl+O).")
        acoes.atualizar(self)

    # O projeto aberto, para quem lê de fora (os testes, os diálogos).
    projeto = property(lambda self: self.pagina.projeto)
    fonte = property(lambda self: self.pagina.fonte)
    leitor = property(lambda self: self.pagina.leitor)

    # ------------------------------------------------------------------
    # Montagem
    # ------------------------------------------------------------------
    def _montar_paineis(self) -> None:
        p, v = self.pagina, self.verificador
        self.visor = VisorDePagina()
        self.visor.box_clicado.connect(p.clicar)
        self.visor.dividir_em.connect(p.dividir_em)
        self.visor.juntar_com.connect(p.juntar_com)
        self.visor.area_desenhada.connect(p.marcar)
        self.visor.box_alternado.connect(p.alternar_na_selecao)
        self.visor.diagrama_clicado.connect(self.conferencia.clicado)
        self.visor.zona_desenhada.connect(self.areas.desenhar)
        self.visor.zona_escolhida.connect(self.areas.escolher)
        self.visor.zona_arrastada.connect(self.areas.arrastar)
        self.visor.zona_apagada.connect(self.areas.apagar)
        self.visor.zona_tipo.connect(self.areas.trocar_tipo)
        self.visor.zoom_mudou.connect(self._zoom_mudou)
        self.visor.pagina_vizinha.connect(self._pagina_vizinha)
        self._pixmaps = OrderedDict()
        self._pre_carga = QTimer(self)          # a seguinte, depois de pintar a atual
        self._pre_carga.setSingleShot(True)
        self._pre_carga.setInterval(150)
        self._pre_carga.timeout.connect(self.pagina.precarregar_seguinte)
        self._pre_pixmap = QTimer(self)
        self._pre_pixmap.setSingleShot(True)
        self._pre_pixmap.setInterval(400)
        self._pre_pixmap.timeout.connect(self._pre_converter)
        self.setCentralWidget(self.visor)

        self.treino = PainelDeTreino()
        self.treino.ensinar.connect(p.ensinar)
        self.treino.so_corrigir.connect(p.corrigir)
        self.treino.descartar.connect(p.descartar)
        self.treino.pular.connect(lambda: self.pagina.andar(+1))
        self.treino.anterior.connect(lambda: self.pagina.andar(-1))
        self.treino.dividir.connect(p.dividir)
        self.treino.juntar.connect(p.juntar)
        self.treino.ajustar.connect(p.ajustar)
        self.treino.corte_mudou.connect(self.visor.marcar_corte)
        self.treino.limpar_selecao.connect(p.limpar_selecao)

        self.padroes = PainelDePadroes()
        self.padroes.esquecer.connect(self.esquecer)

        self.verificacao = PainelDeVerificacao()
        self.verificacao.corrigir.connect(v.corrigir)
        self.verificacao.ensinar.connect(lambda t: self.verificador.corrigir(t, ensinar=True))
        self.verificacao.pular.connect(lambda: self.verificador.andar(+1))
        self.verificacao.anterior.connect(lambda: self.verificador.andar(-1))
        self.verificacao.ignorar_todas.connect(v.ignorar_todas)
        self.verificacao.adicionar.connect(self._adicionar_palavra)
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
        # O texto da página é refeito uma vez, um instante depois da última mudança: montar
        # o documento leva dezenas de ms, e um Enter muda a página duas vezes (o glifo e,
        # depois, a propagação).
        self.relogio_do_texto = QTimer(self)
        self.relogio_do_texto.setSingleShot(True)
        self.relogio_do_texto.setInterval(150)
        self.relogio_do_texto.timeout.connect(self.pintar_texto)
        self.texto.setFont(QFont(FONTE_DE_SIMBOLOS, 11))
        doca_texto = QDockWidget("Texto reconhecido", self)
        doca_texto.setObjectName("doca_texto")
        doca_texto.setWidget(self.texto)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, doca_texto)

    def _ligar_eventos(self) -> None:
        e = self.eventos
        for nome, funcao in (("pagina_trocou", self._pagina_trocou),
                             ("glifos_mudaram", self._glifos_mudaram),
                             ("atual_mudou", self._atual_mudou),
                             ("selecao_mudou", self._selecao_mudou),
                             ("padroes_mudaram", self._padroes_mudaram),
                             ("layout_mudou", self._layout_mudou),
                             ("palavra_mudou", self._palavra_mudou),
                             ("verificacao_pronta", self.verificar_texto),
                             ("conferir", self._abrir_conferencia),
                             ("atual_resolvido", self._atual_resolvido),
                             ("recusa", self._recusa),
                             ("projeto_aberto", self._projeto_aberto),
                             ("acoes_mudaram", self._acoes_mudaram),
                             ("lote_mudou", self._acoes_mudaram),
                             ("mensagem", self._mensagem),
                             ("falha", self._falha),
                             ("aviso", self._aviso)):
            e.ligar(nome, funcao)
        self.executor.ocupado_mudou.connect(self._ocupado_mudou)
        self.executor.fila_mudou.connect(self._fila_mudou)
        self.executor.progresso.connect(self._progredir)
        self.falha_de_gravacao.connect(self._gravacao_falhou)

    # ------------------------------------------------------------------
    # Projeto
    # ------------------------------------------------------------------
    def novo_projeto(self) -> None:
        projeto = dialogos.novo_projeto(self)
        if projeto is not None:
            self.abrir(projeto)

    def abrir_projeto(self) -> None:
        projeto = dialogos.escolher_projeto(self)
        if projeto is not None:
            self.abrir(projeto)

    def abrir_caminho(self, pasta: str) -> None:
        """Abre um projeto pelo caminho, como o argumento da linha de comando."""
        projeto = dialogos.abrir_pasta(self, pasta)
        if projeto is not None:
            self.abrir(projeto)

    def abrir(self, projeto) -> None:
        try:
            fonte = dialogos.preparar_abertura(self, projeto)
            if fonte is not None:
                self.trocar_projeto(projeto, fonte)
        except BaseException:
            if projeto is not self.projeto:
                projeto.fechar()                # a trava de só leitura não fica sem dono
            raise

    def trocar_projeto(self, projeto, fonte) -> None:
        """Fecha o projeto aberto (as tarefas e o gravador terminam antes) e abre `projeto`."""
        if self.projeto is not None and self.projeto is not projeto:
            if not self._fechar_projeto():
                projeto.fechar()                # o usuário ficou com o aberto
                return
        projeto.ao_falhar_gravacao = self.falha_de_gravacao.emit
        self._pixmaps.clear()                   # as páginas do projeto anterior saem
        self.verificador.esquecer_projeto()
        so_leitura = " (só leitura)" if projeto.somente_leitura else ""
        self.setWindowTitle(f"{projeto.dados.nome}{so_leitura} — {TITULO}")
        self.livro.abrir(projeto, fonte)

    def usar(self, projeto, fonte, leitor) -> None:
        """O projeto com o leitor já pronto (os testes; a abertura passa por `abrir`)."""
        projeto.ao_falhar_gravacao = self.falha_de_gravacao.emit
        self.livro.usar(projeto, fonte, leitor)

    def _projeto_aberto(self, leitor) -> None:
        self._padroes_mudaram()
        dialogos.avisos_da_abertura(self, self.projeto, leitor)

    def _parar_tarefas(self) -> None:
        """Cancela o lote, tira da fila o que não começou e espera a tarefa em andamento
        (o resultado dela ainda entra, antes de o projeto fechar)."""
        if self.executor.ocupado:
            self.livro.cancelar()
            self.executor.esvaziar()
            self.statusBar().showMessage("Esperando a tarefa em andamento terminar…")
            self.executor.esperar()
            QApplication.processEvents()        # o fim da tarefa chega antes de fechar

    def _fechar_projeto(self) -> bool:
        """Grava o que falta e fecha o projeto. Se alguma página não grava, pergunta antes
        de mexer nas tarefas: falso quando o usuário prefere não fechar (e perder as
        mudanças dela), e aí nada mudou."""
        projeto = self.projeto
        if not self._gravou_ou_perder(projeto):
            return False
        self._parar_tarefas()                   # o fim da tarefa em voo ainda entra
        if not self._gravou_ou_perder(projeto):   # e o que ele entregou também é gravado
            return False
        self.pagina.desligar()
        projeto.fechar(5)
        return True

    def _gravou_ou_perder(self, projeto) -> bool:
        """Verdadeiro se o gravador gravou tudo, ou se o usuário aceita perder o que falta."""
        if projeto.descarregar(10):
            return True
        paginas = ", ".join(str(i + 1) for i in projeto.paginas_sujas())
        return dialogos.confirmar(self, "Gravar", f"As mudanças da(s) página(s) {paginas} não "
                                  "puderam ser gravadas (veja a barra de status). Fechar mesmo "
                                  "assim e perder essas mudanças?")

    # ------------------------------------------------------------------
    # Comandos que perguntam antes
    # ------------------------------------------------------------------
    def ir_para_pagina(self, indice: int) -> None:
        self.pagina.ir_para(indice)

    def ir_para_a_pagina_pedida(self) -> None:
        """Ctrl+G: pergunta o número da página (o do PDF) e vai até ela."""
        p = self.pagina
        if p.fonte is None:
            return
        numero, ok = QInputDialog.getInt(self, "Ir para a página", f"Página (1 a {p.fonte.total}):",
                                         p.indice + 1, 1, p.fonte.total)
        if ok:
            p.ir_para(numero - 1)

    def _pagina_vizinha(self, passo: int) -> None:
        """PgDn no fim da página abre a seguinte no topo; PgUp no topo, a anterior no fim."""
        if self.pagina.vizinha(passo):
            if passo > 0:
                self.visor.ir_ao_topo()
            else:
                self.visor.ir_ao_fim()

    def reconhecer(self) -> None:
        p = self.pagina
        if p.reconhecida and p.boxes and not dialogos.confirmar(
                self, "Reconhecer página",
                "A página já foi reconhecida. Reconhecer de novo descarta os boxes e as "
                "correções só desta ocorrência. Os padrões ensinados ficam. Continuar?"):
            return
        p.reconhecer()

    def esquecer(self, caminhos: list) -> None:
        if self.leitor is not None and dialogos.confirmar(
                self, "Esquecer padrões", f"Apagar {len(caminhos)} amostra(s) dos padrões "
                "deste livro? A página atual será relida sem elas."):
            self.pagina.esquecer(caminhos)

    def opcoes(self) -> None:
        if not self.pagina.pronto:
            return
        dialogo = DialogoDeOpcoes(self.projeto.dados.limiares, self)
        if dialogo.exec() == DialogoDeOpcoes.DialogCode.Accepted:
            self.pagina.aplicar_limiares(dialogo.limiares())

    def reconhecer_livro(self) -> None:
        """Reconhece um intervalo de páginas em segundo plano, gravando cada uma."""
        if not self.pagina.pronto:
            return
        escolha = dialogos.intervalo_do_lote(self, self.projeto, self.fonte.total)
        if escolha is not None:
            self.livro.reconhecer(*escolha)

    def exportar(self) -> None:
        """Escreve as páginas reconhecidas em PDF pesquisável, DOCX ou EPUB."""
        if self.projeto is not None:
            destino = dialogos.destino_da_exportacao(self, self.projeto)
            if destino is not None:
                self.livro.exportar(destino)

    def modo_treino(self, sim: bool) -> None:
        if sim and self.acao_areas.isChecked():
            self.acao_areas.setChecked(False)
            self.modo_areas(False)
        self.visor.definir_modo_treino(sim)
        self.statusBar().showMessage(
            "Modo de treino: arraste em volta de um glifo para marcá-lo; Ctrl+clique junta "
            "boxes na seleção." if sim else "Modo de treino desligado.", 8000)

    def modo_areas(self, sim: bool) -> None:
        """Liga o editor de áreas, que desliga o modo de treino: os dois usam o arraste."""
        if sim and self.acao_modo_treino.isChecked():
            self.acao_modo_treino.setChecked(False)
            self.visor.definir_modo_treino(False)
        self.visor.definir_modo_areas(sim)
        self._layout_mudou()
        acoes.atualizar(self)
        if sim and not self.areas.zonas and self.pagina.imagem is not None:
            self.areas.automaticas()
        elif sim:
            self.statusBar().showMessage(
                "Editor de áreas: arraste para desenhar, dentro para mover, na borda para "
                "esticar; 1 texto, 2 diagrama, 3 imagem, 4 ignorar; Del apaga. F5 reconhece "
                "pelas áreas.", 10000)
        else:
            self.statusBar().showMessage("Editor de áreas desligado.", 5000)

    def verificar_texto(self) -> None:
        """F7: mostra a verificação, com a primeira palavra desconhecida."""
        if not self.verificador.verificar():
            return                              # o léxico carrega; `verificacao_pronta` volta
        if self.abas.currentWidget() is self.verificacao:
            self.verificador.recontar(0)
        else:
            self.abas.setCurrentWidget(self.verificacao)  # `_aba_mudou` reconta

    def _adicionar_palavra(self) -> None:
        self.verificador.adicionar(self.verificacao.campo.text())

    def _glifo_da_palavra(self, indice: int) -> None:
        """O glifo clicado no recorte vai para o painel de treino, para editar."""
        gid = self.verificador.gid_do_glifo(indice)
        if gid is not None:
            self.abas.setCurrentWidget(self.treino)
            self.pagina.escolher(gid)

    def _atual_resolvido(self) -> None:
        """A propagação resolveu o glifo mostrado: vai ao próximo pendente (ou, se o usuário
        o escolheu, mostra a leitura nova dele), a não ser que ele já esteja digitando nele
        (o que ele digitou não some)."""
        if self.treino.campo.isModified():
            return
        if self.pagina.escolhido and self.pagina.box_atual() is not None:
            self.pagina.escolher(self.pagina.atual)     # fica, com a leitura de agora
        else:
            self.pagina.ir_ao_primeiro_pendente()

    def _recusa(self, refazer: bool, texto: str) -> None:
        pilha = "refazer" if refazer else "desfazer"
        if dialogos.confirmar(self, "Desfazer", texto + f"\n\nTirar esta ação do {pilha} e "
                              "continuar com as outras?"):
            self.pagina.tirar_do_desfazer(refazer)

    def _aba_mudou(self, _indice: int) -> None:
        """Voltar à verificação reconta: o treino pode ter dividido ou juntado glifos."""
        if self.abas.currentWidget() is self.verificacao:
            if self.verificador.lexico is not None and self.pagina.boxes:
                self.verificador.recontar()
        else:
            self.visor.marcar_palavra(None)

    def _abrir_conferencia(self, indice: int) -> DialogoDeDiagrama:
        dialogo = DialogoDeDiagrama(self.pagina.matriz, self.pagina.diagramas, indice, self)
        dialogo.conferido.connect(self.conferencia.aplicar)
        self.dialogo_diagrama = dialogo
        dialogo.open()
        return dialogo

    def closeEvent(self, evento):
        if self.projeto is None:
            self._parar_tarefas()
        elif not self._fechar_projeto():
            evento.ignore()                     # ficou aberta: as mudanças estão na memória
            return
        super().closeEvent(evento)
