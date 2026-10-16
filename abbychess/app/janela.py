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

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QDockWidget, QMainWindow, QMessageBox, QPlainTextEdit,
                               QProgressBar, QTabWidget)

from abbychess import verificacao as vf
from abbychess.app import acoes, cores, dialogos
from abbychess.app.dialogo_diagrama import DialogoDeDiagrama
from abbychess.app.imagens import pixmap_da_pagina
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


class JanelaPrincipal(QMainWindow):
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
            self.pagina.mostrar(gid)

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

    # ------------------------------------------------------------------
    # Desenhar o que os eventos dizem
    # ------------------------------------------------------------------
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

    def _glifos_mudaram(self, _gids=None) -> None:
        p = self.pagina
        na_fila = set(p.fila())
        pendentes = {i for i, g in enumerate(p.gids) if g in na_fila}
        diagramas = p.diagramas
        self.visor.mostrar_boxes(p.boxes, pendentes, [d.caixa for d in diagramas],
                                 [cores.cor_do_diagrama(d) for d in diagramas])
        self._selecao_mudou()
        self.texto.setPlainText(p.texto())
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
        if self.executor.ocupado:
            self.treino.habilitar(False)

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
        if ocupado:
            self.statusBar().showMessage(f"{titulo}…")
            self.treino.habilitar(False)
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

    def closeEvent(self, evento):
        if self.projeto is None:
            self._parar_tarefas()
        elif not self._fechar_projeto():
            evento.ignore()                     # ficou aberta: as mudanças estão na memória
            return
        super().closeEvent(evento)
