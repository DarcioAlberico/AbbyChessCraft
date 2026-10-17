"""Localizar vista da janela (SPEC §7.1, passo B): a barra, F3 e Shift+F3, Alt+Enter, os
Resultados, a contagem na gaveta, o destaque no Documento e a busca por glifo. Um mixin da
`JanelaPrincipal`, como `EdicaoNoDocumento`; quem busca é o `ControladorDaBusca`.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFormLayout, QHBoxLayout, QLineEdit, QWidget)

from abbychess import busca as bs
from abbychess.app.barra_de_busca import BarraDeBusca
from abbychess.controladores import ControladorDaBusca

#: As fontes da busca por glifo (§7.1: rede, base, livro, manual).
FONTES_DO_GLIFO = ((bs.REDE, "Rede"), (bs.BASE, "Base global"), (bs.LIVRO_, "Livro"),
                   (bs.MANUAL, "Manual"), (bs.SEM_LEITURA, "Sem leitura"))


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
        self.resultados.escolhido.connect(self._resultado_escolhido)
        self._ocorrencias: List[bs.Ocorrencia] = []
        self._posicao: Optional[int] = None
        self._mandar_para_resultados = False
        e = self.eventos
        e.ligar("busca_terminou", self._busca_terminou)
        e.ligar("busca_falhou", self._busca_falhou)
        e.ligar("indice_mudou", self._indice_mudou)
        e.ligar("pagina_trocou", self._destacar_na_pagina)

    # ------------------------------------------------------------------
    def localizar(self) -> None:
        """Ctrl+F: a barra no topo da vista direita, com a seleção do Documento como texto."""
        if self.projeto is None:
            return
        selecionado = self.texto.textCursor().selectedText()
        texto = selecionado if selecionado and " " not in selecionado else None
        self.barra_de_busca.abrir(texto)
        if self.barra_de_busca.campo.text():
            self._buscar()

    def fechar_busca(self) -> None:
        self.barra_de_busca.hide()
        self.busca.cancelar()
        self._ocorrencias, self._posicao = [], None
        self.texto.destacar_busca([])
        self.paginas.mostrar_ocorrencias(None)
        self.texto.setFocus(Qt.FocusReason.OtherFocusReason)

    def _opcoes(self) -> bs.Opcoes:
        return self.barra_de_busca.opcoes(pagina_atual=self.pagina.indice,
                                          selecao=self._selecao_no_indice(),
                                          idioma=self.busca.idioma)

    def _selecao_no_indice(self):
        """A seleção do Documento como (página, início, fim) no texto do índice (que não
        tem os diagramas), pelos gids das pontas."""
        cursor = self.texto.textCursor()
        if not cursor.hasSelection():
            return None
        indexada = self.busca.indice.get(self.pagina.indice)
        if indexada is None:
            return None
        a = self.texto.gid_na_posicao(cursor.selectionStart())
        b = self.texto.gid_na_posicao(max(cursor.selectionStart(), cursor.selectionEnd() - 1))
        if a is None or b is None or a not in indexada.gids or b not in indexada.gids:
            return None
        inicio = indexada.gids.index(a)
        fim = len(indexada.gids) - indexada.gids[::-1].index(b)
        return (self.pagina.indice, inicio, fim)

    def _buscar(self) -> None:
        if not self.barra_de_busca.campo.text():
            self.busca.cancelar()
            self._ocorrencias, self._posicao = [], None
            self.barra_de_busca.mostrar_contagem(None, 0)
            self.texto.destacar_busca([])
            self.paginas.mostrar_ocorrencias(None)
            return
        opcoes = self._opcoes()
        try:
            _expressao, dica = bs.compilar(opcoes)
            self.barra_de_busca.mostrar_dica(dica or "Enter: próxima · Shift+Enter: anterior · "
                                             "Alt+Enter: todas em Resultados")
        except bs.PadraoInvalido:
            pass                                # o controlador avisa
        if not self.busca.pronto.is_set():
            self.statusBar().showMessage("Montando o índice da busca…", 0)
        self.busca.buscar(opcoes)

    def _indice_mudou(self, feitas: int, total: int) -> None:
        if feitas < total:
            self.statusBar().showMessage(f"Montando o índice da busca: {feitas} de {total} "
                                         "páginas…", 0)

    def _busca_falhou(self, mensagem: str) -> None:
        self._ocorrencias, self._posicao = [], None
        self.barra_de_busca.mostrar_erro(mensagem)
        self.texto.destacar_busca([])
        self.statusBar().showMessage(mensagem, 8000)

    def _busca_terminou(self, resultado: bs.Resultado) -> None:
        self._ocorrencias = list(resultado.ocorrencias)
        self._posicao = None
        total = len(self._ocorrencias)
        self.barra_de_busca.mostrar_contagem(None, total)
        self.paginas.mostrar_ocorrencias(resultado.por_pagina() if total else {})
        fora = self.busca.nao_reconhecidas()
        if not total:
            self.statusBar().showMessage("Nada encontrado." + (
                f" {fora} página(s) não reconhecida(s) ficaram fora." if fora else ""), 8000)
        else:
            paginas = len(resultado.por_pagina())
            self.statusBar().showMessage(
                f"{total} ocorrência(s) em {paginas} página(s)." + (
                    f" {fora} página(s) não reconhecida(s) ficaram fora." if fora else ""), 8000)
        self._destacar_na_pagina()
        if self._mandar_para_resultados:
            self._mandar_para_resultados = False
            self._mostrar_em_resultados()

    def _destacar_na_pagina(self) -> None:
        """As ocorrências da página aberta, no Documento (a atual em laranja)."""
        if not self.barra_de_busca.isVisible():
            return
        aqui = [n for n, o in enumerate(self._ocorrencias) if o.pagina == self.pagina.indice]
        atual = aqui.index(self._posicao) if self._posicao in aqui else None
        self.texto.destacar_busca([self._ocorrencias[n].gids for n in aqui], atual)

    # ------------------------------------------------------------------
    def proxima_ocorrencia(self) -> None:
        """F3: a próxima ocorrência (dá a volta no livro); sem busca, abre a barra."""
        self._andar(+1)

    def ocorrencia_anterior(self) -> None:
        self._andar(-1)

    def _andar(self, passo: int) -> None:
        if not self.barra_de_busca.isVisible() or not self.barra_de_busca.campo.text():
            self.localizar()
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

    def _ir_a_ocorrencia(self, n: int) -> None:
        o = self._ocorrencias[n]
        self._posicao = n
        if o.pagina != self.pagina.indice:
            self.ir_para_pagina(o.pagina)
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
        """Alt+Enter: todas as ocorrências em Resultados."""
        if not self.barra_de_busca.campo.text():
            self.localizar()
            return
        if self.busca.ultimo_resultado is None or self.barra_de_busca.relogio.isActive():
            self._mandar_para_resultados = True
            self.barra_de_busca.relogio.stop()
            self._buscar()
            return
        self._mostrar_em_resultados()

    def _mostrar_em_resultados(self) -> None:
        total = len(self._ocorrencias)
        fora = self.busca.nao_reconhecidas()
        cabecalho = (f"Localizar “{self.barra_de_busca.campo.text()}”: {total} "
                     f"ocorrência(s)" + (f"; {fora} página(s) não reconhecida(s) ficaram fora"
                                        if fora else ""))
        self.resultados.mostrar_ocorrencias(self._ocorrencias, cabecalho)
        self.mostrar_resultados()

    def _resultado_escolhido(self, alvo) -> None:
        if isinstance(alvo, bs.Ocorrencia):
            if alvo in self._ocorrencias:
                self._ir_a_ocorrencia(self._ocorrencias.index(alvo))
        elif isinstance(alvo, bs.GlifoAchado):
            if alvo.pagina != self.pagina.indice:
                self.ir_para_pagina(alvo.pagina)
            if alvo.gid in set(self.pagina.gids):
                self.pagina.escolher(alvo.gid)

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
                                          else " (o índice ainda está sendo montado)"))
        self.mostrar_resultados()

    def _barra_de_busca_com_o_foco(self) -> bool:
        foco = QApplication.focusWidget()
        return (self.barra_de_busca.isVisible() and foco is not None
                and (foco is self.barra_de_busca or self.barra_de_busca.isAncestorOf(foco)))


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
