"""O espaço de trabalho da janela (SPEC §3.1, §3.2): os painéis, os arranjos e o foco.

- A área central é um `QSplitter` com a **Imagem** (o visor) e a **vista direita** (abas:
  Documento, §6, e Padrões do livro), e embaixo dele a faixa **Linha** (Ctrl+F5).
- **Inspetor** (à direita), **Páginas** (a gaveta, à esquerda) e **Resultados / Avisos**
  (embaixo) são `QDockWidget`.
- A **barra de status** tem a página e o estado, a fila, a caixa de zoom, o lote com o ✕ que
  o cancela, o progresso e o ⚠N dos avisos novos.
- Os **arranjos** (Ctrl+F6, Ctrl+F7, Ctrl+Shift+F7, Ctrl+F8) e o foco (Alt+1 … Alt+5).
- O arranjo de cada projeto é gravado em `<projeto>/janela.json` (atômico), e volta ao
  reabrir: as docas, os tamanhos, o zoom, a aba e o editor ativos, o painel com o foco e a
  página aberta (CA-3.1).

É um mixin de `JanelaPrincipal`, como o desenho (`app/desenho.py`): a mesma regra do CA-14.1
vale aqui (as closures só chamam comandos).
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QByteArray, Qt, QTimer
from PySide6.QtWidgets import (QApplication, QDialog, QDockWidget, QLabel, QMessageBox,
                               QProgressBar, QSpinBox, QSplitter, QTabWidget, QTextBrowser,
                               QToolBar, QToolButton, QVBoxLayout, QWidget)

from abbychess import avisos as av
from abbychess import gravacao as gv
from abbychess import livro as lv
from abbychess import verificacao as vf
from abbychess.modelo import LIDAS
from abbychess.app import visor as vs
from abbychess.app.confirmacao import BarraDeConfirmacao
from abbychess.app.inspetor import PainelDoInspetor
from abbychess.app.linha import FaixaDaLinha
from abbychess.app.painel_paginas import NOMES_DOS_ESTADOS, PainelDePaginas
from abbychess.app.painel_resultados import PainelDeResultados
from abbychess.controladores import ControladorDaFila

log = logging.getLogger(__name__)

ARQUIVO_DO_ESPACO = "janela.json"
VERSAO_DO_ESPACO = 1
ARRANJOS = ("so_imagem", "lado_a_lado", "empilhado", "so_vista")
#: Até esta largura o arranjo padrão é o empilhado (§3.1: abaixo de 1280, e em 1280×720).
LARGURA_DO_EMPILHADO = 1280
#: A partir desta, a gaveta de Páginas abre num projeto novo (até o primeiro lote).
LARGURA_DA_GAVETA = 1600
#: As larguras padrão (§3.1, com as alças): (Páginas, Imagem, vista direita, Inspetor).
TAMANHOS = {1366: (0, 556, 500, 296), 1920: (150, 760, 680, 320)}
ATALHOS_MD = Path(__file__).resolve().parents[2] / "docs" / "ATALHOS.md"


def _b64(dados: QByteArray) -> str:
    return base64.b64encode(bytes(dados)).decode("ascii")


def _validar_espaco(dados) -> dict:
    """O `janela.json` com os tipos certos (ValueError, KeyError ou TypeError se não)."""
    if not isinstance(dados, dict) or dados.get("versao") != VERSAO_DO_ESPACO:
        raise ValueError("versão ou forma desconhecida")
    docas = dados.get("docas", {})
    if not isinstance(docas, dict):
        raise TypeError("docas não é um objeto")
    modo_zoom = dados.get("modo_zoom")
    if modo_zoom not in (None, "pagina", "largura"):
        raise ValueError(f"modo de zoom desconhecido: {modo_zoom!r}")
    editor, fila, arranjo = dados.get("editor", "glifo"), dados.get("fila", "confianca"), \
        dados.get("arranjo", "lado_a_lado")
    if editor not in ("glifo", "palavra") or fila not in dict(ControladorDaFila.MODOS) \
            or arranjo not in ARRANJOS:
        raise ValueError("editor, fila ou arranjo desconhecido")
    inteiros = {k: dados.get(k, d) for k, d in (("pagina", -1), ("aba", 0), ("foco", 0),
                                                 ("largura", 0))}
    if not all(type(v) is int for v in inteiros.values()):
        raise TypeError("página, aba ou foco não é um número inteiro")
    escala = dados.get("escala")
    if escala is not None and not isinstance(escala, (int, float)):
        raise TypeError("escala não é um número")
    return {"janela": QByteArray(base64.b64decode(dados["janela"], validate=True)),
            "divisor": QByteArray(base64.b64decode(dados["divisor"], validate=True)),
            "docas": {str(k): bool(v) for k, v in docas.items()}, "modo_zoom": modo_zoom,
            "escala": float(escala) if escala else None, "editor": editor, "fila": fila,
            "arranjo": arranjo, **inteiros}


def _doca(janela, titulo: str, nome: str, widget, area) -> QDockWidget:
    doca = QDockWidget(titulo, janela)
    doca.setObjectName(nome)
    doca.setWidget(widget)
    janela.addDockWidget(area, doca)
    return doca


class EspacoDeTrabalho:
    """Os painéis, os arranjos, o foco e o estado do espaço por projeto."""

    def _montar_espaco(self) -> None:
        self.avisos = av.RegistroDeAvisos()
        self.fila = ControladorDaFila(self.pagina, self.verificador, self.conferencia)

        self.painel_do_documento = QWidget()
        self.barra_do_documento = QToolBar("Documento")
        self.barra_do_documento.setIconSize(self.barra_do_documento.iconSize() * 0.75)
        caixa = QVBoxLayout(self.painel_do_documento)
        caixa.setContentsMargins(0, 0, 0, 0)
        caixa.setSpacing(0)
        caixa.addWidget(self.barra_do_documento)
        caixa.addWidget(self.texto, 1)
        self.vista = QTabWidget()
        self.vista.setObjectName("vista_direita")
        self.vista.setDocumentMode(True)
        self.vista.addTab(self.painel_do_documento, "Documento")
        self.vista.addTab(self.padroes, "Padrões")
        self.vista.addTab(self.painel_diagramas, "Diagramas")
        self.vista.currentChanged.connect(self._aba_mudou)
        self.divisor = QSplitter(Qt.Orientation.Horizontal)
        self.divisor.setObjectName("divisor")
        self.divisor.setChildrenCollapsible(False)
        self.divisor.setHandleWidth(4)
        self.divisor.addWidget(self.visor)
        self.divisor.addWidget(self.vista)
        self.linha = FaixaDaLinha()
        self.confirmacao = BarraDeConfirmacao()      # a pergunta do Ctrl+T (§8.4)
        centro = QWidget()
        caixa = QVBoxLayout(centro)
        caixa.setContentsMargins(0, 0, 0, 0)
        caixa.setSpacing(4)
        caixa.addWidget(self.divisor, 1)
        caixa.addWidget(self.confirmacao)
        caixa.addWidget(self.linha)
        self.setCentralWidget(centro)
        self.arranjo = "lado_a_lado"

        self.inspetor = PainelDoInspetor(ControladorDaFila.MODOS,
                                         {"glifo": self.treino, "palavra": self.verificacao,
                                          "diagrama": self.editor_diagrama},
                                         escopos=ControladorDaFila.ESCOPOS)
        self.inspetor.modo_escolhido.connect(self.fila.definir)
        self.inspetor.escopo_escolhido.connect(self.fila.definir_escopo)
        self.inspetor.setMinimumWidth(240)
        self.doca_inspetor = _doca(self, "Inspetor", "doca_inspetor", self.inspetor,
                                   Qt.DockWidgetArea.RightDockWidgetArea)
        self.paginas = PainelDePaginas()
        self.paginas.abrir.connect(self.ir_para_pagina)
        self.paginas.reconhecer.connect(lambda indices: self.livro.reconhecer(indices, False))
        self.paginas.reconhecer_livro.connect(self.reconhecer_livro)
        self.doca_paginas = _doca(self, "Páginas", "doca_paginas", self.paginas,
                                  Qt.DockWidgetArea.LeftDockWidgetArea)
        self.doca_paginas.hide()
        # Fechar a gaveta por qualquer caminho (F9, o X, o menu Exibir) devolve a largura.
        self.doca_paginas.visibilityChanged.connect(self._gaveta_mudou)
        self.resultados = PainelDeResultados()
        self.doca_resultados = _doca(self, "Resultados / Avisos", "doca_resultados",
                                     self.resultados, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.doca_resultados.hide()
        # Resultados embaixo da gaveta e do centro; o Inspetor vai até o pé da janela, para
        # Resultados abertos não esconderem os botões do Glifo em 768 de altura.
        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)
        self._foco_antes_dos_resultados = None
        self._divisor_antes_da_gaveta: list = []
        self._mensagem_da_tarefa: Optional[str] = None
        self.relogio_das_paginas = QTimer(self)     # a gaveta depois de uma rajada de edições
        self.relogio_das_paginas.setSingleShot(True)
        self.relogio_das_paginas.setInterval(500)
        self.relogio_das_paginas.timeout.connect(self.atualizar_paginas)
        self._montar_barra_de_status()

    def _montar_barra_de_status(self) -> None:
        barra = self.statusBar()
        self.rotulo_da_pagina = QLabel("")
        self.rotulo_da_fila = QLabel("")
        self.caixa_de_zoom = QSpinBox()
        self.caixa_de_zoom.setRange(int(vs.VisorDePagina.ESCALA_MINIMA * 100),
                                    int(vs.VisorDePagina.ESCALA_MAXIMA * 100))
        self.caixa_de_zoom.setSuffix("%")
        self.caixa_de_zoom.setKeyboardTracking(False)
        self.caixa_de_zoom.setFocusPolicy(Qt.FocusPolicy.ClickFocus)   # o Tab não para nela
        self.caixa_de_zoom.setToolTip("Zoom da página (Ctrl+roda, Ctrl++ e Ctrl+−)")
        self.caixa_de_zoom.setAccessibleName("Zoom da página")     # ligada em `acoes.montar`
        self.rotulo_do_lote = QLabel("")
        self.botao_cancelar = QToolButton()
        self.botao_cancelar.setText("✕")
        self.botao_cancelar.setToolTip("Cancelar o lote")
        self.botao_cancelar.setAccessibleName("Cancelar o lote")
        self.botao_cancelar.clicked.connect(self.livro.cancelar)
        self.botao_cancelar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.progresso = QProgressBar()
        self.progresso.setMaximumWidth(200)
        #: Os modelos carregando no servidor de leitura (§9.1): ocupado, sem número (o filho
        #: não diz em que etapa está), até `modelos_prontos`.
        self.carregando = QProgressBar()
        self.carregando.setRange(0, 0)
        self.carregando.setMaximumWidth(120)
        self.carregando.setFormat("Modelos…")
        self.carregando.setTextVisible(True)
        self.carregando.setAccessibleName("Carregando os modelos de leitura")
        self.carregando.setToolTip("O servidor de leitura está carregando os modelos; as "
                                   "páginas já abrem e o Enter já ensina.")
        self.botao_avisos = QToolButton()
        self.botao_avisos.setAccessibleName("Avisos e erros")
        self.botao_avisos.setToolTip("Os avisos e erros do projeto (Resultados / Avisos)")
        self.botao_avisos.clicked.connect(self.abrir_avisos)
        self.botao_avisos.setFocusPolicy(Qt.FocusPolicy.NoFocus)    # o Tab do campo não para aqui
        for widget in (self.rotulo_da_pagina, self.rotulo_da_fila, self.caixa_de_zoom,
                       self.rotulo_do_lote, self.botao_cancelar, self.progresso,
                       self.carregando,
                       self.botao_avisos):
            barra.addPermanentWidget(widget)
        for widget in (self.rotulo_do_lote, self.botao_cancelar, self.progresso,
                       self.carregando):
            widget.hide()
        self.atualizar_avisos()

    # ------------------------------------------------------------------
    # Arranjos e foco (§3.2)
    # ------------------------------------------------------------------
    def arranjar(self, nome: str) -> None:
        """Só a Imagem, lado a lado, empilhado ou só a vista direita (o Inspetor fica)."""
        if nome not in ARRANJOS:
            raise ValueError(f"arranjo desconhecido: {nome!r}")
        self.arranjo = nome
        self.visor.setVisible(nome != "so_vista")
        self.vista.setVisible(nome != "so_imagem")
        self.divisor.setOrientation(Qt.Orientation.Vertical if nome == "empilhado"
                                    else Qt.Orientation.Horizontal)

    def arranjo_padrao(self) -> None:
        """O arranjo e os tamanhos padrão para a largura da janela (§3.1). Os tamanhos vão
        depois do layout: uma doca que acabou de abrir ignora o `resizeDocks`."""
        largura = self.width()
        self.arranjar("lado_a_lado" if largura > LARGURA_DO_EMPILHADO else "empilhado")
        self._tamanhos_padrao()
        QTimer.singleShot(0, self._tamanhos_padrao)

    def alternar_linha(self, mostrar: Optional[bool] = None) -> None:
        """Ctrl+F5: mostra ou esconde a faixa Linha (`mostrar`, o estado da ação marcável)."""
        self.linha.setVisible((not self.linha.isVisible()) if mostrar is None else bool(mostrar))
        self._mostrar_a_linha()

    def _altura_da_linha(self) -> None:
        """80 px até 1080 de altura de tela útil, 96 acima (§3.1)."""
        self.linha.setFixedHeight(96 if self.height() >= 1000 else 80)

    def _tamanhos_padrao(self) -> None:
        """A tabela de §3.1: o Inspetor com 296 px até 1600 de largura e 320 a partir dela,
        a gaveta com 150, e o resto entre a Imagem e a vista direita, 53% e 47% (760 e 680
        em 1920; 558 e 500 em 1366)."""
        largura = self.width()
        self._altura_da_linha()
        self.texto.definir_corpo_padrao(10 if largura < LARGURA_DA_GAVETA else 11)
        inspetor = TAMANHOS[1920 if largura >= LARGURA_DA_GAVETA else 1366][3]
        paginas = TAMANHOS[1920][0] if self.doca_paginas.isVisible() else 0
        self.resizeDocks([self.doca_inspetor], [inspetor], Qt.Orientation.Horizontal)
        if paginas:
            self.resizeDocks([self.doca_paginas], [paginas], Qt.Orientation.Horizontal)
        if self.arranjo == "lado_a_lado":
            centro = self.divisor.width()
            # Abaixo de 1600 a gaveta aberta sai da vista direita, como no F9 (a Imagem de
            # 1366 é o limite da x-height do CA-3.2); de 1600 em diante a tabela já a conta.
            emprestado = paginas if largura < LARGURA_DA_GAVETA else 0
            imagem = round((centro + emprestado) * 760 / 1440)
            self.divisor.setSizes([imagem, centro - imagem])
        else:
            altura = self.divisor.height()
            self.divisor.setSizes([round(altura * 0.6), round(altura * 0.4)])
        if self.doca_resultados.isVisible():
            self._altura_dos_resultados()

    def alternar_paginas(self) -> None:
        """F9: abre ou fecha a gaveta de Páginas."""
        if self.doca_paginas.isVisible():
            self.doca_paginas.hide()                # `_gaveta_mudou` devolve os 150 px
        else:
            self.abrir_gaveta()

    def abrir_gaveta(self) -> None:
        """A gaveta com 150 px, tirados da vista direita: a Imagem fica do tamanho que tinha
        (em 1366, a x-height do CA-3.2 depende dela). A doca e o `resizeDocks` assentam no
        laço de eventos, um depois do outro; a largura da Imagem volta no fim."""
        if not self.doca_paginas.isVisible():
            self._divisor_antes_da_gaveta = self.divisor.sizes()
            self.doca_paginas.show()
            QTimer.singleShot(0, self._largura_da_gaveta)
        self.atualizar_paginas(seguir=True)

    def _largura_da_gaveta(self) -> None:
        self.resizeDocks([self.doca_paginas], [TAMANHOS[1920][0]], Qt.Orientation.Horizontal)
        QTimer.singleShot(0, self._repor_a_imagem)

    def _repor_a_imagem(self) -> None:
        antes, centro = self._divisor_antes_da_gaveta, sum(self.divisor.sizes())
        imagem = antes[0] if antes and self.visor.isVisible() else 0
        if imagem and self.arranjo == "lado_a_lado" and centro > imagem + 200:
            self.divisor.setSizes([imagem, centro - imagem])

    def _gaveta_mudou(self, visivel: bool) -> None:
        if not visivel and self._divisor_antes_da_gaveta:
            QTimer.singleShot(0, self._repor_o_divisor)

    def _repor_o_divisor(self) -> None:
        """A gaveta fechou: o divisor volta aos tamanhos de antes de ela abrir (sem isto, cada
        abrir e fechar deixaria a Imagem maior e a vista direita menor)."""
        antes, self._divisor_antes_da_gaveta = self._divisor_antes_da_gaveta, []
        if antes and len(antes) == len(self.divisor.sizes()):
            self.divisor.setSizes(antes)

    def focar(self, painel: int) -> None:
        """Alt+1 … Alt+5: Páginas, Imagem, vista direita (de novo: a aba seguinte), Inspetor,
        Resultados. Abre o painel fechado."""
        if painel == 1:
            self.abrir_gaveta()
            self.paginas.focar()
        elif painel == 2:
            if self.arranjo == "so_vista":
                self.arranjar("lado_a_lado")
            self.visor.setFocus(Qt.FocusReason.ShortcutFocusReason)
        elif painel == 3:
            if self.arranjo == "so_imagem":
                self.arranjar("lado_a_lado")
            dentro = self.vista.isAncestorOf(QApplication.focusWidget())
            if dentro:
                self.vista.setCurrentIndex((self.vista.currentIndex() + 1) % self.vista.count())
            self.vista.currentWidget().setFocus(Qt.FocusReason.ShortcutFocusReason)
        elif painel == 4:
            self.doca_inspetor.show()
            self.inspetor.focar()
        elif painel == 5:
            if not self.resultados.isAncestorOf(QApplication.focusWidget()):
                self._foco_antes_dos_resultados = QApplication.focusWidget()
            self.mostrar_resultados()
            self.resultados.focar()

    def _no_documento(self) -> bool:
        foco = QApplication.focusWidget()
        return foco is not None and (foco is self.texto or self.texto.isAncestorOf(foco))

    def aproximar(self) -> None:
        """Ctrl++: aumenta o corpo do Documento, com o foco nele; senão aproxima a Imagem."""
        if self._no_documento():
            self.texto.mudar_corpo(+1)
        else:
            self.visor.zoom_mais()

    def afastar(self) -> None:
        if self._no_documento():
            self.texto.mudar_corpo(-1)
        else:
            self.visor.zoom_menos()

    def zoom_padrao(self) -> None:
        """Ctrl+0: o corpo padrão no Documento; a página inteira na Imagem."""
        if self._no_documento():
            self.texto.mudar_corpo(0)
        else:
            self.visor.zoom_pagina()

    # ------------------------------------------------------------------
    # A sincronia (§6.2): o Documento, a Imagem, a Linha e a fila
    # ------------------------------------------------------------------
    def _indices(self, gids) -> list:
        indice = self._indice_por_gid()
        return [indice[g] for g in gids if g in indice]

    def _indice_por_gid(self) -> dict:
        """gid → posição na lista de boxes, montado uma vez por chamada (o `indice_de` do
        controlador procura na lista inteira, e a Linha pede um por glifo)."""
        return {g: i for i, g in enumerate(self.pagina.gids)}

    def _documento_clicado(self, gid: int, gids: list) -> None:
        """O clique numa palavra do Documento: os glifos dela destacados na Imagem (CA-6.1) e
        o glifo clicado no Glifo do Inspetor (ação explícita)."""
        if self.pagina.indice_de(gid) is not None:
            self.inspetor.mostrar("glifo")
            self.pagina.escolher(gid)            # a Linha e o cursor seguem pelo atual_mudou
        self._palavra_do_documento(gids, gid)   # depois: o atual_mudou apaga o contorno velho

    def _palavra_do_documento(self, gids: list, gid_da_linha=None) -> None:
        """O cursor do Documento numa palavra: ela destacada na Imagem e na Linha; com Seguir,
        a Imagem rola até ela."""
        indices = self._indices(gids)
        if not indices:
            return
        caixa = vf.caixa_da_palavra(self.pagina.boxes, indices)
        self.visor.marcar_palavra_do_documento(caixa)
        if self.acao_seguir.isChecked():        # só com Seguir a Imagem rola (§6.2)
            self.visor.mostrar_caixa(caixa)
        self._mostrar_a_linha(gids[0] if gid_da_linha is None else gid_da_linha)

    def _mostrar_a_linha(self, gid=None) -> None:
        """A faixa Linha com a linha do glifo (o atual, se nenhum é dado)."""
        p = self.pagina
        gid = p.atual if gid is None else gid
        if not self.linha.isVisible() or gid is None or p.matriz is None:
            self.linha.limpar()
            return
        indice = self._indice_por_gid()
        linha = [g for g in self.texto.linha_de(gid) if g in indice]
        if gid not in linha:
            linha = self._linha_pela_geometria(gid, indice)
        if not linha:
            self.linha.limpar()
            return
        boxes = p.boxes
        self.linha.mostrar(p.matriz, [boxes[indice[g]] for g in linha],
                           linha.index(gid) if gid in linha else None)

    def _linha_pela_geometria(self, gid, indice_por_gid: dict) -> list:
        """Os glifos da altura do glifo (o centro de cada um dentro da faixa dele), da
        esquerda para a direita: a linha quando o Documento ainda não a tem."""
        p = self.pagina
        indice = indice_por_gid.get(gid)
        if indice is None:
            return []
        boxes, alvo = p.boxes, p.boxes[indice]
        na_faixa = [i for i, b in enumerate(boxes) if alvo.y1 <= (b.y1 + b.y2) / 2 <= alvo.y2]
        return [p.gids[i] for i in sorted(na_faixa, key=lambda i: boxes[i].x1)]

    def painel_com_o_foco(self) -> int:
        """O número do Alt+N do painel com o foco (0: nenhum)."""
        foco = QApplication.focusWidget()
        for n, painel in ((1, self.paginas), (2, self.visor), (3, self.vista),
                          (4, self.inspetor), (5, self.resultados)):
            if foco is not None and (foco is painel or painel.isAncestorOf(foco)):
                return n
        return 0

    def fechar_sobreposicao(self) -> None:
        """Esc: fecha o que está por cima, na ordem da §3.4 (regra 4): a seleção do modo de
        marcar, depois Resultados (a busca e os menus, que vêm antes, fecham sozinhos com o
        Esc). Nunca cancela tarefa. Com uma sessão de edição aberta no Documento, o Esc a
        restaura (§6.3). A pergunta do Ctrl+T, se aberta, fecha antes de tudo (só ela)."""
        if self.confirmacao.aberta:
            self.confirmacao.recusar()
        elif self._barra_de_busca_com_o_foco():
            self.fechar_busca()
        elif self.texto.tem_sessao:
            self.texto.restaurar()
        elif self.pagina.selecao:
            self.pagina.limpar_selecao()
        elif self.doca_resultados.isVisible():
            foco = QApplication.focusWidget()       # antes do hide, que já move o foco
            estava = foco is not None and (foco is self.resultados
                                           or self.resultados.isAncestorOf(foco))
            self.doca_resultados.hide()
            self._devolver_o_foco(estava)

    def _devolver_o_foco(self, estava_em_resultados: bool) -> None:
        """Depois de fechar Resultados, o foco volta a quem o tinha antes do Alt+5 (ou à
        Imagem), e não ao botão ⚠ da barra."""
        antes, self._foco_antes_dos_resultados = self._foco_antes_dos_resultados, None
        if not estava_em_resultados:
            return                              # o foco estava noutro painel: fica onde está
        alvo = antes if antes is not None and antes.isVisible() else self.visor
        alvo.setFocus(Qt.FocusReason.OtherFocusReason)

    # ------------------------------------------------------------------
    # A fila, a gaveta, a barra e os avisos
    # ------------------------------------------------------------------
    def _modo_da_fila_mudou(self, modo: str) -> None:
        """O modo da fila escolhe o editor do Inspetor: Palavra nas palavras, Diagrama nos
        diagramas (aberto pelo F8 ou por um clique), Glifo no resto."""
        if modo == "palavras":
            self.verificar_texto()
        elif modo == "diagramas" and self.editor_diagrama.aberto:
            self.inspetor.mostrar("diagrama")
        else:
            self.inspetor.mostrar("glifo")
            self.visor.marcar_palavra(None)
            self.pagina.eventos.emitir("atual_mudou")
        self.atualizar_fila()

    def atualizar_fila(self) -> None:
        f = self.fila
        self.inspetor.mostrar_modo(f.modo, f.nome(), f.escopo, f.nome_do_escopo())
        contador = f.contador() if self.pagina.pronto else ""
        self.inspetor.mostrar_contador(contador)
        escopo = " (livro)" if f.escopo == "livro" else ""
        self.rotulo_da_fila.setText(f"fila: {f.nome().lower()}{escopo} {contador}".rstrip())

    def atualizar_paginas(self, seguir: bool = False) -> None:
        """A gaveta com o `livro.json` de agora; `seguir`: a página aberta mudou, e a gaveta
        a escolhe (as outras atualizações não mexem na seleção nem na rolagem)."""
        p = self.pagina
        if not self.doca_paginas.isVisible() or p.projeto is None or p.fonte is None:
            return
        self.paginas.mostrar(p.fonte.total, p.projeto.resumo_do_livro(),
                             p.indice if seguir else None)
        self.paginas.mostrar_saude(
            lv.saude(p.projeto, p.leitor.arquivos_de_padrao() if p.leitor else 0))

    def atualizar_barra(self) -> None:
        p = self.pagina
        if p.modelo is None or p.fonte is None:
            self.rotulo_da_pagina.setText("")
            return
        estado = NOMES_DOS_ESTADOS.get(p.modelo.estado, p.modelo.estado)
        self.rotulo_da_pagina.setText(f"p.{p.indice + 1}/{p.fonte.total} ● {estado}")

    def registrar_aviso(self, tipo: str, titulo: str, texto: str) -> None:
        """Um aviso ou erro no log persistente (Avisos), e o ⚠N da barra."""
        self.resultados.acrescentar(self.avisos.registrar(tipo, titulo, texto))
        self.atualizar_avisos()

    def atualizar_avisos(self) -> None:
        novos = self.avisos.novos
        self.botao_avisos.setText(f"⚠{novos}" if novos else "⚠")

    def mostrar_resultados(self) -> None:
        """Abre Resultados / Avisos com a altura padrão (200 px, §3.1)."""
        if not self.doca_resultados.isVisible():
            self.doca_resultados.show()
            QTimer.singleShot(0, self._altura_dos_resultados)   # depois do layout da doca

    def _altura_dos_resultados(self) -> None:
        """200 px (§3.1); numa janela de menos de 900 de altura, 130, para a página ficar."""
        altura = 200 if self.height() >= 900 else 130
        self.resizeDocks([self.doca_resultados], [altura], Qt.Orientation.Vertical)

    def abrir_avisos(self) -> None:
        self.mostrar_resultados()
        self.resultados.ir_aos_avisos()
        self.avisos.visto()
        self.atualizar_avisos()

    def _lote_na_barra(self) -> None:
        rodando = self.livro.lote_rodando
        self.rotulo_do_lote.setVisible(rodando)
        self.botao_cancelar.setVisible(rodando)
        self.relogio_das_paginas.start()        # o lote grava páginas em rajada

    # ------------------------------------------------------------------
    # O espaço por projeto (CA-3.1, CA-4.2)
    # ------------------------------------------------------------------
    def _caminho_do_espaco(self) -> Optional[Path]:
        projeto = self.projeto
        return None if projeto is None else Path(projeto.pasta) / ARQUIVO_DO_ESPACO

    def estado_do_espaco(self) -> dict:
        return {"versao": VERSAO_DO_ESPACO, "janela": _b64(self.saveState(VERSAO_DO_ESPACO)),
                "divisor": _b64(self.divisor.saveState()), "arranjo": self.arranjo,
                "docas": {d.objectName(): d.isVisible() for d in
                          (self.doca_inspetor, self.doca_paginas, self.doca_resultados)},
                "escala": self.visor.escala(), "modo_zoom": self.visor.modo_zoom,
                "aba": self.vista.currentIndex(), "editor": self.inspetor.atual(),
                "fila": self.fila.modo, "foco": self.painel_com_o_foco(),
                "pagina": self.pagina.indice, "largura": self.width()}

    def gravar_espaco(self) -> None:
        """Grava o espaço do projeto aberto (atômico, como as páginas)."""
        caminho = self._caminho_do_espaco()
        if caminho is None or self.projeto.somente_leitura:
            return
        try:
            gv.gravar_json(caminho, self.estado_do_espaco())
        except OSError as erro:
            self.registrar_aviso(av.ERRO, "Espaço de trabalho",
                                 f"O arranjo da janela não foi gravado ({erro}).")

    def restaurar_espaco(self) -> bool:
        """O espaço gravado do projeto, se houver e for legível; falso se não (projeto novo,
        ou um `janela.json` estragado, que vira aviso e não impede abrir)."""
        caminho = self._caminho_do_espaco()
        if caminho is None or not caminho.exists():
            return False
        try:
            dados = _validar_espaco(json.loads(caminho.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as erro:
            log.warning("Espaço de %s ilegível: %s", caminho, erro)
            self.registrar_aviso(av.AVISO, "Espaço de trabalho",
                                 f"O arranjo gravado da janela não pôde ser lido ({erro}); "
                                 "o padrão vale.")
            return False
        if not self.restoreState(dados["janela"], VERSAO_DO_ESPACO):
            log.warning("O estado das docas de %s não foi aceito pelo Qt", caminho)
        self.arranjar(dados["arranjo"])
        self.divisor.restoreState(dados["divisor"])
        if dados["largura"] and abs(dados["largura"] - self.width()) > 150:
            # Gravado noutra largura de janela: as docas e o arranjo voltam, os tamanhos são
            # os padrão desta (1920 numa tela de 1366 deixaria a Imagem com 464 px).
            QTimer.singleShot(0, self._tamanhos_padrao)
        for nome, visivel in dados["docas"].items():
            doca = self.findChild(QDockWidget, nome)
            if doca is not None:
                doca.setVisible(visivel)
        total = self.pagina.fonte.total if self.pagina.fonte else 0
        if 0 <= dados["pagina"] < total and dados["pagina"] != self.pagina.indice:
            self.pagina.ir_para(dados["pagina"])
        if dados["modo_zoom"] == "pagina":
            self.visor.zoom_pagina()
        elif dados["modo_zoom"] == "largura":
            self.visor.zoom_largura()
        elif dados["escala"]:
            self.visor.definir_zoom(dados["escala"])
        if 0 <= dados["aba"] < self.vista.count():
            self.vista.setCurrentIndex(dados["aba"])
        self.fila.definir(dados["fila"])
        self.inspetor.mostrar(dados["editor"])
        if dados["foco"]:
            self.focar(dados["foco"])
        return True

    def _espaco_padrao(self) -> None:
        """O espaço de um projeto sem `janela.json`: o arranjo da largura, a fila por
        confiança, o Glifo, o Documento e a página inteira (nada do projeto anterior fica)."""
        self.fila.definir("confianca")
        self.inspetor.mostrar("glifo")
        self.vista.setCurrentIndex(0)
        self.visor.zoom_pagina()
        self.arranjo_padrao()

    def abrir_avisos_do_projeto(self, projeto) -> None:
        """O log de avisos do projeto que abre (ou nenhum, `None`, ao fechar): um aviso entre
        fechar um projeto e abrir outro não vai para o arquivo do anterior."""
        if projeto is None:
            self.avisos.abrir(None)
        else:
            self.avisos.abrir(projeto.pasta, gravar=not projeto.somente_leitura)
        self.resultados.mostrar_avisos(self.avisos.itens)
        self.atualizar_avisos()

    def _espaco_do_projeto_aberto(self) -> None:
        """Ao abrir: o espaço gravado; num projeto sem ele, o padrão, com a gaveta aberta
        se a janela é larga e nada foi reconhecido ainda."""
        if not self.restaurar_espaco():
            novo = not any(r.get("estado") in LIDAS for r in self.projeto.resumo_do_livro().values())
            self.doca_paginas.setVisible(novo and self.width() >= LARGURA_DA_GAVETA)
            self._espaco_padrao()
        self.atualizar_paginas(seguir=True)
        self.atualizar_barra()
        self.atualizar_fila()

    # ------------------------------------------------------------------
    # Ajuda
    # ------------------------------------------------------------------
    def mostrar_atalhos(self) -> None:
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Atalhos do teclado")
        dialogo.resize(820, 640)
        texto = QTextBrowser()
        texto.setMarkdown(ATALHOS_MD.read_text(encoding="utf-8") if ATALHOS_MD.exists()
                          else "docs/ATALHOS.md não encontrado.")
        QVBoxLayout(dialogo).addWidget(texto)
        self.dialogo_de_atalhos = dialogo
        dialogo.open()

    def sobre(self) -> None:
        QMessageBox.about(self, "Sobre o AbbyChessCraft",
                          "AbbyChessCraft: o OCR de livros de xadrez com treino de padrões por "
                          "livro, sobre o core do PyBoxEditor.")
