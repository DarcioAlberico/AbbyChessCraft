"""O espaço de trabalho da janela (SPEC §3.1, §3.2): os painéis, os arranjos e o foco.

- A área central é um `QSplitter` com a **Imagem** (o visor) e a **vista direita** (abas:
  Documento, que até o A3 é o texto reconhecido de hoje, e Padrões do livro).
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
                               QToolButton, QVBoxLayout)

from abbychess import avisos as av
from abbychess import gravacao as gv
from abbychess.modelo import LIDAS
from abbychess.app import visor as vs
from abbychess.app.inspetor import PainelDoInspetor
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

        self.vista = QTabWidget()
        self.vista.setObjectName("vista_direita")
        self.vista.setDocumentMode(True)
        self.vista.addTab(self.texto, "Documento")
        self.vista.addTab(self.padroes, "Padrões")
        self.divisor = QSplitter(Qt.Orientation.Horizontal)
        self.divisor.setObjectName("divisor")
        self.divisor.setChildrenCollapsible(False)
        self.divisor.setHandleWidth(4)
        self.divisor.addWidget(self.visor)
        self.divisor.addWidget(self.vista)
        self.setCentralWidget(self.divisor)
        self.arranjo = "lado_a_lado"

        self.inspetor = PainelDoInspetor(ControladorDaFila.MODOS,
                                         {"glifo": self.treino, "palavra": self.verificacao})
        self.inspetor.modo_escolhido.connect(self.fila.definir)
        self.inspetor.setMinimumWidth(240)
        self.doca_inspetor = _doca(self, "Inspetor", "doca_inspetor", self.inspetor,
                                   Qt.DockWidgetArea.RightDockWidgetArea)
        self.paginas = PainelDePaginas()
        self.paginas.abrir.connect(self.ir_para_pagina)
        self.paginas.reconhecer.connect(lambda indices: self.livro.reconhecer(indices, False))
        self.doca_paginas = _doca(self, "Páginas", "doca_paginas", self.paginas,
                                  Qt.DockWidgetArea.LeftDockWidgetArea)
        self.doca_paginas.hide()
        self.resultados = PainelDeResultados()
        self.doca_resultados = _doca(self, "Resultados / Avisos", "doca_resultados",
                                     self.resultados, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.doca_resultados.hide()
        for canto in (Qt.Corner.BottomLeftCorner, Qt.Corner.BottomRightCorner):
            self.setCorner(canto, Qt.DockWidgetArea.BottomDockWidgetArea)
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
        self.progresso = QProgressBar()
        self.progresso.setMaximumWidth(200)
        self.botao_avisos = QToolButton()
        self.botao_avisos.setAccessibleName("Avisos e erros")
        self.botao_avisos.setToolTip("Os avisos e erros do projeto (Resultados / Avisos)")
        self.botao_avisos.clicked.connect(self.abrir_avisos)
        for widget in (self.rotulo_da_pagina, self.rotulo_da_fila, self.caixa_de_zoom,
                       self.rotulo_do_lote, self.botao_cancelar, self.progresso,
                       self.botao_avisos):
            barra.addPermanentWidget(widget)
        for widget in (self.rotulo_do_lote, self.botao_cancelar, self.progresso):
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
        """O arranjo e os tamanhos padrão para a largura da janela (§3.1)."""
        largura = self.width()
        self.arranjar("lado_a_lado" if largura > LARGURA_DO_EMPILHADO else "empilhado")
        paginas, imagem, vista, inspetor = TAMANHOS[1920 if largura >= 1700 else 1366]
        escala = largura / (1920 if largura >= 1700 else 1366)
        self.resizeDocks([self.doca_inspetor], [round(inspetor * escala)],
                         Qt.Orientation.Horizontal)
        if self.doca_paginas.isVisible():
            self.resizeDocks([self.doca_paginas], [round(max(paginas, 150) * escala)],
                             Qt.Orientation.Horizontal)
        if self.arranjo == "lado_a_lado":
            self.divisor.setSizes([round(imagem * escala), round(vista * escala)])
        else:
            altura = self.divisor.height()
            self.divisor.setSizes([round(altura * 0.6), round(altura * 0.4)])

    def alternar_paginas(self) -> None:
        """F9: abre ou fecha a gaveta de Páginas."""
        self.doca_paginas.setVisible(not self.doca_paginas.isVisible())
        if self.doca_paginas.isVisible():
            self.atualizar_paginas()

    def focar(self, painel: int) -> None:
        """Alt+1 … Alt+5: Páginas, Imagem, vista direita (de novo: a aba seguinte), Inspetor,
        Resultados. Abre o painel fechado."""
        if painel == 1:
            self.doca_paginas.show()
            self.atualizar_paginas()
            self.paginas.focar()
        elif painel == 2:
            if self.arranjo == "so_vista":
                self.visor.setVisible(True)
            self.visor.setFocus(Qt.FocusReason.ShortcutFocusReason)
        elif painel == 3:
            if self.arranjo == "so_imagem":
                self.vista.setVisible(True)
            dentro = self.vista.isAncestorOf(QApplication.focusWidget())
            if dentro:
                self.vista.setCurrentIndex((self.vista.currentIndex() + 1) % self.vista.count())
            self.vista.currentWidget().setFocus(Qt.FocusReason.ShortcutFocusReason)
        elif painel == 4:
            self.doca_inspetor.show()
            self.inspetor.focar()
        elif painel == 5:
            self.doca_resultados.show()
            self.resultados.focar()

    def painel_com_o_foco(self) -> int:
        """O número do Alt+N do painel com o foco (0: nenhum)."""
        foco = QApplication.focusWidget()
        for n, painel in ((1, self.paginas), (2, self.visor), (3, self.vista),
                          (4, self.inspetor), (5, self.resultados)):
            if foco is not None and (foco is painel or painel.isAncestorOf(foco)):
                return n
        return 0

    def fechar_sobreposicao(self) -> None:
        """Esc: fecha o que está por cima, nesta ordem: Resultados, a seleção do modo de
        marcar (§3.4, regra 4). Nunca cancela tarefa."""
        if self.doca_resultados.isVisible():
            self.doca_resultados.hide()
        elif self.pagina.selecao:
            self.pagina.limpar_selecao()

    # ------------------------------------------------------------------
    # A fila, a gaveta, a barra e os avisos
    # ------------------------------------------------------------------
    def _modo_da_fila_mudou(self, modo: str) -> None:
        """O modo da fila escolhe o editor do Inspetor: Palavra nas palavras, Glifo no resto."""
        if modo == "palavras":
            self.verificar_texto()
        else:
            self.inspetor.mostrar("glifo")
            self.visor.marcar_palavra(None)
            self.pagina.eventos.emitir("atual_mudou")
        self.atualizar_fila()

    def atualizar_fila(self) -> None:
        self.inspetor.mostrar_modo(self.fila.modo, self.fila.nome())
        contador = self.fila.contador() if self.pagina.pronto else ""
        self.inspetor.mostrar_contador(contador)
        self.rotulo_da_fila.setText(f"fila: {self.fila.nome().lower()} {contador}".rstrip())

    def atualizar_paginas(self) -> None:
        p = self.pagina
        if not self.doca_paginas.isVisible() or p.projeto is None or p.fonte is None:
            return
        self.paginas.mostrar(p.fonte.total, p.projeto.resumo_do_livro(), p.indice)

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

    def abrir_avisos(self) -> None:
        self.doca_resultados.show()
        self.resultados.ir_aos_avisos()
        self.avisos.visto()
        self.atualizar_avisos()

    def _lote_na_barra(self) -> None:
        rodando = self.livro.lote_rodando
        self.rotulo_do_lote.setVisible(rodando)
        self.botao_cancelar.setVisible(rodando)
        self.atualizar_paginas()

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
                "pagina": self.pagina.indice}

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
        """O espaço gravado do projeto, se houver; falso se não há (projeto novo)."""
        caminho = self._caminho_do_espaco()
        if caminho is None or not caminho.exists():
            return False
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            if dados.get("versao") != VERSAO_DO_ESPACO:
                return False
            self.restoreState(QByteArray(base64.b64decode(dados["janela"])), VERSAO_DO_ESPACO)
            self.arranjar(dados.get("arranjo", "lado_a_lado"))
            self.divisor.restoreState(QByteArray(base64.b64decode(dados["divisor"])))
            for nome, visivel in dados.get("docas", {}).items():
                doca = self.findChild(QDockWidget, nome)
                if doca is not None:
                    doca.setVisible(visivel)
        except (OSError, ValueError, KeyError, TypeError) as erro:
            log.warning("Espaço de %s ilegível: %s", caminho, erro)
            return False
        total = self.pagina.fonte.total if self.pagina.fonte else 0
        if 0 <= dados.get("pagina", -1) < total and dados["pagina"] != self.pagina.indice:
            self.pagina.ir_para(dados["pagina"])
        if dados.get("modo_zoom") == "pagina":
            self.visor.zoom_pagina()
        elif dados.get("modo_zoom") == "largura":
            self.visor.zoom_largura()
        elif dados.get("escala"):
            self.visor.definir_zoom(float(dados["escala"]))
        if 0 <= dados.get("aba", -1) < self.vista.count():
            self.vista.setCurrentIndex(dados["aba"])
        if dados.get("fila") in dict(ControladorDaFila.MODOS):
            self.fila.definir(dados["fila"])
        if dados.get("editor") in self.inspetor.editores:
            self.inspetor.mostrar(dados["editor"])
        if dados.get("foco"):
            self.focar(int(dados["foco"]))
        return True

    def _espaco_do_projeto_aberto(self) -> None:
        """Ao abrir: o espaço gravado; num projeto sem ele, o padrão, com a gaveta aberta
        até o primeiro lote se a janela é larga e nada foi reconhecido ainda."""
        self.avisos.abrir(self.projeto.pasta, gravar=not self.projeto.somente_leitura)
        self.resultados.mostrar_avisos(self.avisos.itens)
        self.atualizar_avisos()
        if not self.restaurar_espaco():
            novo = not any(r.get("estado") in LIDAS for r in self.projeto.resumo_do_livro().values())
            self.doca_paginas.setVisible(novo and self.width() >= LARGURA_DA_GAVETA)
            self.arranjo_padrao()
        self.atualizar_paginas()
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
