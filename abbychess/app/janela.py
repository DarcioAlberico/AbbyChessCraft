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
   diagrama, imagem e o que ignorar, antes do F5. A **verificação de texto** (a fila de
   palavras desconhecidas, F7) anda pelas palavras que o léxico do core não conhece.

A janela só compõe, liga sinais a comandos e desenha o que os eventos dizem (SPEC §14.1).
Os comandos e o estado estão nos controladores sem Qt (`abbychess.controlador`,
`abbychess.controladores`); as ações e os menus, em `app/acoes.py` (os atalhos, de
`docs/atalhos.yaml` por `app/teclado.py`); os painéis, os arranjos e o espaço por projeto,
em `app/espaco.py`; os diálogos, em `app/dialogos.py`.
"""

from __future__ import annotations

import logging

from collections import OrderedDict

from PySide6.QtCore import QSettings, QTimer, Signal
from PySide6.QtWidgets import QApplication, QInputDialog, QMainWindow

from abbychess import avisos as av
from abbychess.app import acoes, dialogos
from abbychess.app.busca_na_janela import BuscaNaJanela
from abbychess.app.galeria_na_janela import GaleriaNaJanela
from abbychess.app.substituir_na_janela import SubstituirNaJanela
from abbychess.app.desenho import DesenhoDaJanela
from abbychess.app.diagramas_na_janela import DiagramasNaJanela
from abbychess.app.edicao_na_janela import EdicaoNoDocumento
from abbychess.app.espaco import EspacoDeTrabalho
from abbychess.app.lote_na_janela import LoteNaJanela
from abbychess.app.documento import VistaDoDocumento
from abbychess.app.opcoes import DialogoDeOpcoes
from abbychess.app.painel_padroes import PainelDePadroes
from abbychess.app.painel_treino import PainelDeTreino
from abbychess.app.painel_verificacao import PainelDeVerificacao
from abbychess.app.trabalho import Executor
from abbychess.app.visor import VisorDePagina
from abbychess.controlador import ControladorDePagina, Eventos
from abbychess.controladores import (ControladorDeDiagramas, ControladorDeLayout,
                                     ControladorDeVerificacao, ControladorDoLivro)

log = logging.getLogger(__name__)

TITULO = "AbbyChessCraft"


class JanelaPrincipal(DesenhoDaJanela, EspacoDeTrabalho, DiagramasNaJanela, LoteNaJanela,
                      EdicaoNoDocumento, BuscaNaJanela, SubstituirNaJanela, GaleriaNaJanela, QMainWindow):
    #: Da thread do gravador: a página `indice` não gravou (o erro).
    falha_de_gravacao = Signal(object, object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(TITULO)
        self.resize(1500, 950)
        self.config = QSettings("AbbyChessCraft", "AbbyChessCraft")

        self.executor = Executor(self)
        self.eventos = Eventos()
        self.pagina = ControladorDePagina(self.eventos, self.executor)
        self.areas = ControladorDeLayout(self.pagina)
        self.verificador = ControladorDeVerificacao(self.pagina)
        self.conferencia = ControladorDeDiagramas(self.pagina)
        self.livro = ControladorDoLivro(self.pagina)
        self._montar_paineis()
        self._montar_espaco()
        self._montar_busca()
        self._montar_substituir()
        self._montar_galeria()
        acoes.montar(self)
        self._ligar_eventos()
        self.treino.limpar("Crie um projeto (Ctrl+N) ou abra um existente (Ctrl+O).")
        acoes.atualizar(self)
        self.arranjo_padrao()
        self.atualizar_fila()

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
        self.visor.box_clicado.connect(self._box_clicado)
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
        self.visor.zona_funcao.connect(self.areas.trocar_funcao)
        self.visor.ordenacao_cancelada.connect(self.areas.cancelar_ordenacao)
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
        self._montar_diagramas()                # o editor Diagrama e a aba (§10)

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

        self.padroes = PainelDePadroes()
        self.padroes.esquecer.connect(self.esquecer)
        self.padroes.ir_para.connect(self.ir_a_origem)
        self.treino.campo.textChanged.connect(self._aviso_de_ensino)

        self.verificacao = PainelDeVerificacao()
        self.verificacao.corrigir.connect(v.corrigir)
        self.verificacao.ensinar.connect(lambda t: self.verificador.corrigir(t, ensinar=True))
        self.verificacao.pular.connect(lambda: self.verificador.andar(+1))
        self.verificacao.anterior.connect(lambda: self.verificador.andar(-1))
        self.verificacao.ignorar_todas.connect(v.ignorar_todas)
        self.verificacao.adicionar.connect(self._adicionar_palavra)
        self.verificacao.glifo_escolhido.connect(self._glifo_da_palavra)

        self.texto = VistaDoDocumento()         # o Documento (§6.1), só leitura até o D1
        self.texto.glifo_clicado.connect(self._documento_clicado)
        self.texto.sessao_confirmada.connect(self._sessao_do_documento)
        self.texto.sessao_mudou.connect(self._acoes_mudaram)
        self.texto.sem_duvidosas.connect(self._sem_duvidosas)
        self.pagina.antes_de_sair_da_pagina = self.confirmar_a_sessao_aberta
        self.texto.cursor_na_palavra.connect(self._palavra_do_documento)
        # O texto da página é refeito uma vez, um instante depois da última mudança: montar
        # o documento leva dezenas de ms, e um Enter muda a página duas vezes (o glifo e,
        # depois, a propagação).
        self.relogio_do_texto = QTimer(self)
        self.relogio_do_texto.setSingleShot(True)
        self.relogio_do_texto.setInterval(150)
        self.relogio_do_texto.timeout.connect(self.pintar_texto)

    def _ligar_eventos(self) -> None:
        e = self.eventos
        for nome, funcao in (("pagina_trocou", self._pagina_trocou),
                             ("glifos_mudaram", self._glifos_mudaram),
                             ("glifos_mudaram", self._sincronizar_conferencia),
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
                             ("modelos_prontos", self._modelos_prontos),
                             ("amostra_terminou", self._amostra_terminou),
                             ("servidor_caiu", self._servidor_caiu),
                             ("lote_progresso", self._lote_progrediu),
                             ("lote_terminou", self._lote_terminou),
                             ("resultado", self._resultado),
                             ("sessao_recusada", self._sessao_recusada),
                             ("estrutural", self._aviso_estrutural),
                             ("caractere_sugerido", self._caractere_sugerido),
                             ("pagina_do_lote", self._pagina_do_lote),
                             ("acoes_mudaram", self._acoes_mudaram),
                             ("lote_mudou", self._acoes_mudaram),
                             ("lote_mudou", self._lote_na_barra),
                             ("modo_da_fila_mudou", self._modo_da_fila_mudou),
                             ("palavra_mudou", self.atualizar_fila),
                             ("mensagem", self._mensagem),
                             ("falha", self._falha),
                             ("aviso", self._aviso),
                             ("relatorio", self._relatorio)):
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
        self.abrir_avisos_do_projeto(projeto)
        self.verificador.esquecer_projeto()
        so_leitura = " (só leitura)" if projeto.somente_leitura else ""
        self.setWindowTitle(f"{projeto.dados.nome}{so_leitura} — {TITULO}")
        self.livro.abrir(projeto, fonte)
        # O espaço e a gaveta já, pelo livro.json, sem esperar o leitor (§8.1, CA-8.3: o
        # painel de Páginas com o livro todo logo ao abrir); `_projeto_aberto` os refaz.
        self._espaco_do_projeto_aberto()

    def usar(self, projeto, fonte, leitor, servidor=None) -> None:
        """O projeto com o leitor já pronto (os testes e as medidas; a abertura passa por
        `abrir`). Com o `servidor`, o leitor é o da interface (só os padrões do livro)."""
        projeto.ao_falhar_gravacao = self.falha_de_gravacao.emit
        self.abrir_avisos_do_projeto(projeto)
        self.livro.usar(projeto, fonte, leitor, servidor)
        self._espaco_do_projeto_aberto()

    def _projeto_aberto(self, leitor) -> None:
        self.fechar_busca()
        self._limpar_previa()
        self.busca.abrir()                      # o índice da busca, em segundo plano (§7.3)
        self._padroes_mudaram()
        self._espaco_do_projeto_aberto()
        dialogos.avisos_da_abertura(self, self.projeto)
        servidor = self.pagina.servidor
        if servidor is not None and not servidor.pronto.is_set():
            # §9.1: a navegação já vale; o que for lido antes fica "aguardando leitura".
            self.carregando.show()
            self.statusBar().showMessage("Carregando os modelos no servidor de leitura… As "
                                         "páginas já abrem; a leitura começa quando ele "
                                         "terminar.")

    def _parar_tarefas(self) -> None:
        """Cancela o lote, tira da fila o que não começou e espera a tarefa em andamento
        (o resultado dela ainda entra, antes de o projeto fechar)."""
        self.livro.cancelar()
        if self.pagina.servidor is not None:
            # A tarefa em curso que espera o servidor termina já ("cancelado"), sem a janela
            # ficar congelada esperando uma leitura que não vai entrar.
            self.pagina.servidor.abandonar_pendentes()
        if self.executor.ocupado:
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
        # A sessão aberta do Documento entra agora, depois da tarefa em voo (um F5 dela que
        # entrasse depois passaria por cima) e sem a fila, que acabou de ser esvaziada.
        self.pagina.aplicar_as_sessoes_na_fila()
        self.confirmar_a_sessao_aberta(agora=True)
        self.livro.esperar_a_gravacao()
        if not self._gravou_ou_perder(projeto):   # e o que ele entregou também é gravado
            self.pagina.ler_os_aguardando()     # ficou aberto: o que foi abandonado volta
            return False
        self.gravar_espaco()
        self.abrir_avisos_do_projeto(None)
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

    def verificar_pagina(self) -> None:
        """Ctrl+T: com glifos a revisar, pergunta na barra (§8.4: Enter aceita, Esc não
        marca e fecha só a pergunta) antes de marcar a página como verificada."""
        pendentes = len(self.pagina.fila()) if self.pagina.modelo is not None else 0
        if pendentes:
            self.confirmacao.perguntar(
                f"Aceitar {pendentes} pendente(s) como estão e marcar a página como "
                "verificada? Enter aceita · Esc não marca", self.pagina.verificar)
            return
        self.pagina.verificar()

    def reconhecer(self) -> None:
        p = self.pagina
        if p.reconhecida and p.boxes and not dialogos.confirmar(
                self, "Reconhecer página",
                "A página já foi reconhecida. Reconhecer de novo descarta os boxes e as "
                "correções só desta ocorrência. Os padrões ensinados ficam. Continuar?"):
            return
        p.reconhecer()

    def esquecer(self, caminhos: list) -> None:
        if self.leitor is not None:              # sem pergunta: o Ctrl+Z desfaz (§8.3)
            self.pagina.esquecer(caminhos)

    def opcoes(self) -> None:
        if not self.pagina.pronto:
            return
        dialogo = DialogoDeOpcoes(self.projeto.dados.limiares, self,
                                  notacao=self.projeto.dados.notacao)
        if dialogo.exec() == DialogoDeOpcoes.DialogCode.Accepted:
            self.pagina.definir_notacao(dialogo.notacao())
            self.pagina.aplicar_limiares(dialogo.limiares())

    def reconhecer_livro(self) -> None:
        """Reconhece um intervalo de páginas em segundo plano, gravando cada uma."""
        if not self.pagina.pronto:
            return
        escolha = dialogos.intervalo_do_lote(self, self.projeto, self.fonte.total)
        if escolha is not None:
            self.livro.reconhecer(*escolha)

    def aplicar_modelo_de_areas(self) -> None:
        """Aplica o modelo salvo a um intervalo, opcionalmente só nas pares ou ímpares."""
        if self.fonte is None or self.areas.modelo is None:
            return
        indices = dialogos.paginas_do_modelo_de_areas(self, self.fonte.total)
        if indices is not None:
            self.areas.aplicar_modelo(indices)

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
            "Marcar glifo à mão: arraste em volta de um glifo para marcá-lo; Ctrl+clique junta "
            "boxes na seleção." if sim else "Marcar glifo à mão: desligado.", 8000)

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
        """A fila de palavras desconhecidas: a Palavra no Inspetor, com a primeira delas
        (recontada: o treino pode ter dividido ou juntado glifos)."""
        self.inspetor.mostrar("palavra")
        if self.verificador.verificar():        # senão o léxico carrega, e
            self.verificador.recontar(0)        # `verificacao_pronta` volta aqui

    def _adicionar_palavra(self) -> None:
        self.verificador.adicionar(self.verificacao.campo.text())

    def _glifo_da_palavra(self, indice: int) -> None:
        """O glifo clicado no recorte vai para o painel de treino, para editar."""
        gid = self.verificador.gid_do_glifo(indice)
        if gid is not None:
            self.inspetor.mostrar("glifo")
            self.pagina.escolher(gid)

    def _box_clicado(self, indice: int) -> None:
        """O clique num box é ação explícita: o Inspetor mostra o Glifo dele."""
        self.inspetor.mostrar("glifo")
        self.pagina.clicar(indice)

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
        self.registrar_aviso(av.AVISO, "Desfazer" if not refazer else "Refazer", texto)
        if dialogos.confirmar(self, "Desfazer", texto + f"\n\nTirar esta ação do {pilha} e "
                              "continuar com as outras?"):
            self.pagina.tirar_do_desfazer(refazer)

    def closeEvent(self, evento):
        self.config.setValue("geometria", self.saveGeometry())
        if self.projeto is None:
            self._parar_tarefas()
        elif not self._fechar_projeto():
            evento.ignore()                     # ficou aberta: as mudanças estão na memória
            return
        super().closeEvent(evento)
