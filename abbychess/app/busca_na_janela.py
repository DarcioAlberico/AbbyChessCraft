"""Localizar vista da janela (SPEC §7.1, passo B): a barra, F3 e Shift+F3, Alt+Enter, os
Resultados, a contagem na gaveta, o destaque no Documento e a busca por glifo. Um mixin da
`JanelaPrincipal`, como `EdicaoNoDocumento`; quem busca é o `ControladorDaBusca`.
"""

from __future__ import annotations

import re
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFormLayout, QHBoxLayout, QLineEdit, QWidget)

from abbychess import busca as bs
from abbychess.app.barra_de_busca import BarraDeBusca
from abbychess.controladores import ControladorDaBusca

#: As fontes da busca por glifo (§7.1: rede, base, livro, manual), e o nome de cada uma.
FONTES_DO_GLIFO = ((bs.REDE, "Rede"), (bs.BASE, "Base global"), (bs.LIVRO_, "Livro"),
                   (bs.MANUAL, "Manual"), (bs.SEM_LEITURA, "Sem leitura"))
NOMES_DAS_FONTES = dict(FONTES_DO_GLIFO)
#: A seleção do Documento com mais que isto (ou de várias linhas) vira o escopo Seleção.
SELECAO_LONGA = 40


class BuscaNaJanela:
    def _montar_busca(self) -> None:
        self.busca = ControladorDaBusca(self.pagina)
        self.barra_de_busca = BarraDeBusca()
        self.painel_do_documento.layout().insertWidget(0, self.barra_de_busca)
        b = self.barra_de_busca
        b.mudou.connect(self._buscar)
        b.proxima.connect(self.proxima_ocorrencia)
        b.anterior.connect(self.ocorrencia_anterior)
        b.todas.connect(self.todas_em_resultados)
        b.fechar.connect(self.fechar_busca)
        b.escopo.currentIndexChanged.connect(self._escopo_mudou)
        self.resultados.escolhido.connect(self._resultado_escolhido)
        self.resultados.aviso_escolhido.connect(self._aviso_escolhido)
        self._ocorrencias: List[bs.Ocorrencia] = []
        self._posicao: Optional[int] = None
        self._mandar_para_resultados = False
        #: A ida pedida (F3, Enter) antes de a busca terminar: +1, -1 ou None.
        self._ida_pendente: Optional[int] = None
        #: A seleção do Documento quando o escopo Seleção foi escolhido (o cursor anda).
        self._selecao_congelada = None
        #: (página, versão no histórico) da página aberta na última busca: a edição dela
        #: (a versão muda) refaz a busca; trocar de página, não.
        self._versao_buscada = None
        self._atual_antes = None
        e = self.eventos
        e.ligar("busca_terminou", self._busca_terminou)
        e.ligar("busca_falhou", self._busca_falhou)
        e.ligar("indice_mudou", self._indice_mudou)
        e.ligar("pagina_trocou", self._destacar_na_pagina)
        e.ligar("glifos_mudaram", self._pagina_editada)
        self.busca.aquecer()                    # os processos do índice, já com o programa

    # ------------------------------------------------------------------
    def localizar(self) -> None:
        """Ctrl+F: a barra no topo da vista direita (na aba Documento), com a seleção do
        Documento como texto; a seleção longa, ou de várias linhas, vira o escopo Seleção."""
        if self.projeto is None:
            return
        self.vista.setCurrentWidget(self.painel_do_documento)
        cursor = self.texto.textCursor()
        selecionado = cursor.selectedText()
        texto = None
        if selecionado and (" " in selecionado or len(selecionado) > SELECAO_LONGA):
            self._selecao_congelada = self._selecao_atual()
            self.barra_de_busca.escolher_escopo(bs.SELECAO)
        elif selecionado:
            texto = selecionado
        self.barra_de_busca.abrir(texto)
        if self.barra_de_busca.campo.text():
            self.barra_de_busca.relogio.stop()
            self._buscar()

    def fechar_busca(self) -> None:
        self.barra_de_busca.hide()
        self.busca.cancelar()
        self._ocorrencias, self._posicao, self._ida_pendente = [], None, None
        self._mandar_para_resultados = False
        self.texto.destacar_busca([])
        self.paginas.mostrar_ocorrencias(None)
        self.texto.setFocus(Qt.FocusReason.OtherFocusReason)

    def _escopo_mudou(self, *_):
        if self.barra_de_busca.escopo.currentData() == bs.SELECAO:
            self._selecao_congelada = self._selecao_atual() or self._selecao_congelada

    def _selecao_atual(self):
        """A seleção do Documento como (página, gid do primeiro glifo, gid do último)."""
        cursor = self.texto.textCursor()
        if not cursor.hasSelection():
            return None
        inicio, fim = cursor.selectionStart(), cursor.selectionEnd()
        gids = [g for k in range(inicio, fim) if (g := self.texto.gid_na_posicao(k)) is not None]
        return (self.pagina.indice, gids[0], gids[-1]) if gids else None

    def _opcoes(self) -> bs.Opcoes:
        return self.barra_de_busca.opcoes(pagina_atual=self.pagina.indice,
                                          selecao=self._selecao_congelada,
                                          idioma=self.busca.idioma)

    def _buscar(self) -> None:
        b = self.barra_de_busca
        if self._posicao is not None and self._ocorrencias:      # para ficar nela depois
            atual = self._ocorrencias[self._posicao]
            self._atual_antes = (atual.pagina, atual.gids[:1], b.campo.text())
        self._ocorrencias, self._posicao = [], None
        self._versao_buscada = self._versao_da_aberta()
        if not b.campo.text():
            self.busca.cancelar()
            self._ida_pendente = None
            b.mostrar_contagem(None, 0)
            self.texto.destacar_busca([])
            self.paginas.mostrar_ocorrencias(None)
            return
        if b.escopo.currentData() == bs.INTERVALO and b.intervalo_de_paginas() is None:
            self.busca.cancelar()
            b.mostrar_erro("Intervalo inválido: escreva as páginas como 3-10 (ou só 7).")
            return
        if b.escopo.currentData() == bs.SELECAO and self._selecao_congelada is None:
            self.busca.cancelar()
            b.mostrar_erro("Sem seleção: selecione o trecho no Documento e escolha Seleção.")
            return
        if not self.busca.pronto.is_set():
            self.statusBar().showMessage("Montando o índice da busca…", 0)
        dica = self.busca.buscar(self._opcoes())
        if dica is not None:
            b.mostrar_dica(dica or "Enter: próxima · Shift+Enter: anterior · Alt+Enter: "
                                   "todas em Resultados · Esc (com o foco na barra): fechar")

    def _indice_mudou(self, feitas: int, total: int) -> None:
        if feitas < total:
            self.statusBar().showMessage(f"Montando o índice da busca: {feitas} de {total} "
                                         "páginas…", 0)
        elif self.statusBar().currentMessage().startswith("Montando o índice da busca"):
            self.statusBar().clearMessage()

    def _versao_da_aberta(self):
        p = self.pagina
        pid = p.modelo.pid if p.modelo is not None else None
        return (p.indice, p.historico.versao(pid))

    def _pagina_editada(self, *_):
        """Com a barra aberta, a busca refaz a contagem depois de uma edição da página aberta
        (a versão dela no histórico mudou; trocar de página, que também avisa
        `glifos_mudaram`, não refaz)."""
        if self.barra_de_busca.isHidden() or not self.barra_de_busca.campo.text():
            return
        agora = self._versao_da_aberta()
        buscada = self._versao_buscada
        if buscada is not None and agora[0] == buscada[0] and agora != buscada:
            self.barra_de_busca.relogio.start()

    def _busca_falhou(self, mensagem: str) -> None:
        self._ocorrencias, self._posicao = [], None
        self._mandar_para_resultados, self._ida_pendente = False, None
        self.barra_de_busca.mostrar_erro(mensagem)
        self.texto.destacar_busca([])
        self.statusBar().showMessage(mensagem, 8000)

    def _busca_terminou(self, resultado: bs.Resultado) -> None:
        self._ocorrencias = list(resultado.ocorrencias)
        self._posicao = None
        antes, self._atual_antes = getattr(self, "_atual_antes", None), None
        if antes is not None and antes[2] == self.barra_de_busca.campo.text():
            # A mesma busca refeita (depois de uma edição): a ocorrência atual continua.
            self._posicao = next((n for n, o in enumerate(self._ocorrencias)
                                  if (o.pagina, o.gids[:1]) == antes[:2]), None)
        total = len(self._ocorrencias)
        self.barra_de_busca.mostrar_contagem(self._posicao, total)
        self.paginas.mostrar_ocorrencias(resultado.por_pagina() if total else {})
        fora = self._fora_da_busca()
        if not total:
            self.statusBar().showMessage("Nada encontrado." + fora, 8000)
        else:
            self.statusBar().showMessage(f"{total} ocorrência(s) em "
                                         f"{len(resultado.por_pagina())} página(s)." + fora, 8000)
        self._destacar_na_pagina()
        if self._mandar_para_resultados:
            self._mandar_para_resultados = False
            self._mostrar_em_resultados()
        if self._ida_pendente is not None:
            passo, self._ida_pendente = self._ida_pendente, None
            self._andar(passo)

    def _fora_da_busca(self) -> str:
        """" N página(s) não reconhecida(s) ficaram fora." (só no escopo do livro)."""
        if self.barra_de_busca.escopo.currentData() != bs.LIVRO:
            return ""
        fora = self.busca.nao_reconhecidas()
        return f" {fora} página(s) não reconhecida(s) ficaram fora." if fora else ""

    def _destacar_na_pagina(self) -> None:
        """As ocorrências da página aberta, no Documento (a atual em laranja)."""
        if self.barra_de_busca.isHidden():
            return
        aqui = [n for n, o in enumerate(self._ocorrencias) if o.pagina == self.pagina.indice]
        atual = aqui.index(self._posicao) if self._posicao in aqui else None
        self.texto.destacar_busca([self._ocorrencias[n].gids for n in aqui], atual)

    # ------------------------------------------------------------------
    def proxima_ocorrencia(self) -> None:
        """F3: a próxima ocorrência (dá a volta no livro); sem busca, abre a barra e vai à
        primeira quando ela terminar."""
        self._andar(+1)

    def ocorrencia_anterior(self) -> None:
        self._andar(-1)

    def _andar(self, passo: int) -> None:
        b = self.barra_de_busca
        if b.isHidden() or not b.campo.text():
            self._ida_pendente = passo if b.campo.text() else None
            self.localizar()
            return
        if b.relogio.isActive() or self.busca.buscando:
            # Digitou e já pediu a próxima: a ida espera esta busca (não a anterior).
            self._ida_pendente = passo
            if b.relogio.isActive():
                b.relogio.stop()
                self._buscar()
            return
        if not self._ocorrencias:
            return
        n = len(self._ocorrencias)
        if self._posicao is None:               # a primeira a partir da página aberta
            aqui = self.pagina.indice
            ordem = range(n) if passo > 0 else range(n - 1, -1, -1)
            self._posicao = next((k for k in ordem
                                  if (self._ocorrencias[k].pagina >= aqui if passo > 0
                                      else self._ocorrencias[k].pagina <= aqui)),
                                 0 if passo > 0 else n - 1)
        else:
            self._posicao = (self._posicao + passo) % n
        self._ir_a_ocorrencia(self._posicao)

    def _ir_a_pagina_ja_montada(self, indice: int) -> None:
        """Outra página, com o Documento já montado (o relógio do texto montaria depois, e o
        cursor iria para o lugar errado)."""
        if indice != self.pagina.indice:
            self.ir_para_pagina(indice)
            self.pintar_texto()

    def _ir_a_ocorrencia(self, n: int) -> None:
        o = self._ocorrencias[n]
        self._posicao = n
        self._ir_a_pagina_ja_montada(o.pagina)
        self.barra_de_busca.mostrar_contagem(n, len(self._ocorrencias))
        self._destacar_na_pagina()
        if o.gids:
            self.texto.ir_ao_gid(o.gids[0])
            self.visor.marcar_palavra(self._caixa_dos_gids(o.gids))

    def _caixa_dos_gids(self, gids):
        modelo = self.pagina.modelo
        caixas = [b.entry for b in modelo.boxes if b.gid in set(gids)] if modelo is not None else []
        if not caixas:
            return None
        return (min(e.x1 for e in caixas), min(e.y1 for e in caixas),
                max(e.x2 for e in caixas), max(e.y2 for e in caixas))

    def todas_em_resultados(self) -> None:
        """Alt+Enter: todas as ocorrências em Resultados (as desta busca: espera ela)."""
        b = self.barra_de_busca
        if not b.campo.text():
            self.localizar()
            return
        if self.busca.ultimo_resultado is None or b.relogio.isActive() or self.busca.buscando:
            self._mandar_para_resultados = True
            if b.relogio.isActive() or self.busca.ultimo_resultado is None:
                b.relogio.stop()
                self._buscar()
            return
        self._mostrar_em_resultados()

    def _mostrar_em_resultados(self) -> None:
        total = len(self._ocorrencias)
        cabecalho = (f"Localizar “{self.barra_de_busca.campo.text()}”: {total} "
                     f"ocorrência(s)." + self._fora_da_busca())
        self.resultados.mostrar_ocorrencias(self._ocorrencias, cabecalho)
        self.mostrar_resultados()

    def _resultado_escolhido(self, alvo) -> None:
        if isinstance(alvo, bs.Ocorrencia):
            if alvo in self._ocorrencias:
                self._ir_a_ocorrencia(self._ocorrencias.index(alvo))
        elif isinstance(alvo, bs.GlifoAchado):
            self._ir_a_pagina_ja_montada(alvo.pagina)
            if alvo.gid in set(self.pagina.gids):
                self.pagina.escolher(alvo.gid)

    def _aviso_escolhido(self, pagina: int, x: Optional[int], y: Optional[int]) -> None:
        """Um aviso que cita "Página N" (e "em (x, y)", o glifo de uma decisão que caiu): a
        página abre, e o glifo daquele ponto fica escolhido."""
        if self.pagina.fonte is None or not 0 <= pagina < self.pagina.fonte.total:
            return
        self._ir_a_pagina_ja_montada(pagina)
        modelo = self.pagina.modelo
        if x is None or modelo is None:
            return
        alvo = next((b.gid for b in modelo.boxes
                     if b.entry.x1 <= x <= b.entry.x2 and b.entry.y1 <= y <= b.entry.y2), None)
        if alvo is not None:
            self.pagina.escolher(alvo)

    # ------------------------------------------------------------------
    def buscar_glifo(self) -> None:
        """A busca por glifo (§7.1): caractere, fonte e faixa de confiança; a lista vai para
        Resultados (a Galeria é do passo C)."""
        if self.projeto is None:
            return
        dialogo = DialogoDaBuscaPorGlifo(self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        char, fontes, minima, maxima = dialogo.pedido()
        achados = self.busca.glifos(char, fontes, minima, maxima)
        descricao = f"'{char}'" if char else "qualquer caractere"
        self.resultados.mostrar_glifos(
            achados, f"Glifos {descricao}, confiança de {minima:.2f} a {maxima:.2f}: "
                     f"{len(achados)}" + ("" if self.busca.pronto.is_set()
                                          else " (o índice ainda está sendo montado)"),
            NOMES_DAS_FONTES)
        self.mostrar_resultados()

    def _barra_de_busca_com_o_foco(self) -> bool:
        foco = QApplication.focusWidget()
        return (self.barra_de_busca.isVisible() and foco is not None
                and (foco is self.barra_de_busca or self.barra_de_busca.isAncestorOf(foco)))


#: "Página 12" e "em (340, 1180)" num aviso (as decisões que caíram na releitura, §4.6).
_PAGINA_DO_AVISO = re.compile(r"[Pp]ágina (\d+)")
_PONTO_DO_AVISO = re.compile(r"em \((\d+), (\d+)\)")


def lugar_do_aviso(texto: str):
    """(página, x, y) que o aviso cita (x e y None sem o ponto), ou None."""
    pagina = _PAGINA_DO_AVISO.search(texto)
    if pagina is None:
        return None
    ponto = _PONTO_DO_AVISO.search(texto, pagina.end())
    return (int(pagina.group(1)) - 1, int(ponto.group(1)) if ponto else None,
            int(ponto.group(2)) if ponto else None)


class DialogoDaBuscaPorGlifo(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Buscar glifo")
        self.caractere = QLineEdit()
        self.caractere.setMaxLength(4)
        self.caractere.setPlaceholderText("qualquer")
        self.fontes = {}
        linha = QWidget()
        caixa = QHBoxLayout(linha)
        caixa.setContentsMargins(0, 0, 0, 0)
        for valor, rotulo in FONTES_DO_GLIFO:
            marca = QCheckBox(rotulo)
            marca.setChecked(True)
            self.fontes[valor] = marca
            caixa.addWidget(marca)
        self.minima, self.maxima = QDoubleSpinBox(), QDoubleSpinBox()
        for campo, valor in ((self.minima, 0.0), (self.maxima, 1.0)):
            campo.setRange(0.0, 1.0)
            campo.setSingleStep(0.05)
            campo.setDecimals(2)
            campo.setValue(valor)
        formulario = QFormLayout(self)
        formulario.addRow("Caractere", self.caractere)
        formulario.addRow("Fonte", linha)
        formulario.addRow("Confiança de", self.minima)
        formulario.addRow("até", self.maxima)
        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                  | QDialogButtonBox.StandardButton.Cancel)
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        formulario.addRow(botoes)

    def pedido(self):
        fontes = [v for v, marca in self.fontes.items() if marca.isChecked()]
        todas = len(fontes) == len(self.fontes)
        return (self.caractere.text(), None if todas else fontes,
                min(self.minima.value(), self.maxima.value()),
                max(self.minima.value(), self.maxima.value()))
