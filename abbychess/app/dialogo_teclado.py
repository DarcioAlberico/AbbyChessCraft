"""Opções › Teclado (SPEC §3.4, passo K): o perfil (padrão ou FineReader) e a troca de atalhos.

A tabela mostra cada ação com tecla neste passo, o escopo e as teclas no perfil escolhido;
as teclas se editam como texto ("Ctrl+Shift+F; F3"). Ao aceitar, as trocas passam pelas
mesmas regras do `docs/atalhos.yaml` (`teclado.problemas`); com problema, o diálogo diz qual
e não fecha. As trocas valem para o perfil escolhido: trocar de perfil as desfaz.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from abbychess import atalhos
from abbychess.app import estilo, teclado

PERFIS = (("padrao", "Padrão"), ("finereader", "FineReader"))
#: As colunas da tabela.
ACAO, ESCOPO, TECLAS = 0, 1, 2


def partir(texto: str) -> List[str]:
    """ "Ctrl+Y; Ctrl+Shift+Z" -> as sequências normalizadas (vazio: sem tecla). Só o ";"
    separa: a vírgula é tecla (Ctrl+, abre as Opções), e o ";" logo depois de um "+" também
    ("Ctrl+;")."""
    sequencias, pedacos = [], texto.split(";")
    for i, pedaco in enumerate(pedacos):
        if pedaco.rstrip().endswith("+") and i + 1 < len(pedacos):
            pedaco = pedaco.rstrip() + ";"     # "Ctrl+" ";" ...: a tecla é o próprio ";"
        if pedaco.strip():
            sequencias.append(atalhos.normalizar(pedaco.strip()))
    return sequencias


def com_nomes(problema: str) -> str:
    """O problema das regras com o nome de cada ação no lugar do id ("proximo_diagrama" ->
    "“Próximo diagrama por conferir do livro”"), para quem lê o aviso."""
    descricoes = {a.id: a.descricao for a in teclado.tabela().acoes}
    return re.sub(r"\b[a-z][a-z0-9_]*\b",
                  lambda m: f"“{descricoes[m.group(0)]}”" if m.group(0) in descricoes
                  else m.group(0), problema)


class DialogoDoTeclado(QDialog):
    def __init__(self, parent=None, perfil: str = "padrao",
                 trocas: Optional[Dict[str, List[str]]] = None):
        super().__init__(parent)
        self.setWindowTitle("Teclado")
        self.resize(720, 560)
        self.perfil = QComboBox()
        for valor, rotulo in PERFIS:
            self.perfil.addItem(rotulo, valor)
        self.perfil.setCurrentIndex(max(0, self.perfil.findData(perfil)))
        self.perfil.setAccessibleName("Perfil de teclado")
        self.perfil.setToolTip("Padrão: as teclas do AbbyChessCraft. FineReader: as do "
                               "ABBYY FineReader, para quem vem dele.")
        self.perfil.currentIndexChanged.connect(lambda _i: self._preencher({}))
        restaurar = QPushButton("Restaurar o perfil")
        restaurar.setToolTip("Desfaz as trocas: volta às teclas do perfil")
        restaurar.clicked.connect(lambda: self._preencher({}))
        nota = QLabel("Edite as teclas como texto (\"Ctrl+Shift+F; F3\"); vazio tira a tecla. "
                      "As trocas valem para o perfil escolhido; trocar de perfil as desfaz.")
        nota.setWordWrap(True)
        estilo.papel(nota, "dica")

        self.tabela = QTableWidget(0, 3)
        self.tabela.setHorizontalHeaderLabels(["Ação", "Onde", "Teclas"])
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.horizontalHeader().setSectionResizeMode(ACAO, QHeaderView.ResizeMode.Stretch)
        self.tabela.setAccessibleName("Atalhos do perfil")
        self._ids: List[str] = []

        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                  QDialogButtonBox.StandardButton.Cancel)
        botoes.accepted.connect(self._aceitar)
        botoes.rejected.connect(self.reject)
        topo = QFormLayout()
        topo.addRow("Perfil", self.perfil)
        corpo = QVBoxLayout(self)
        corpo.addLayout(topo)
        corpo.addWidget(nota)
        corpo.addWidget(self.tabela, 1)
        corpo.addWidget(restaurar, 0, Qt.AlignmentFlag.AlignLeft)
        corpo.addWidget(botoes)
        self._preencher(dict(trocas or {}))

    # ------------------------------------------------------------------
    def perfil_escolhido(self) -> str:
        return self.perfil.currentData()

    def _preencher(self, trocas: Dict[str, List[str]]) -> None:
        perfil = self.perfil_escolhido()
        acoes = [a for a in teclado.tabela().acoes if teclado.ativa(a.id)]
        self._ids = [a.id for a in acoes]
        self.tabela.setRowCount(len(acoes))
        for linha, a in enumerate(acoes):
            descricao = QTableWidgetItem(a.descricao)
            descricao.setFlags(descricao.flags() & ~Qt.ItemFlag.ItemIsEditable)
            descricao.setData(Qt.ItemDataRole.UserRole, a.id)
            escopo = QTableWidgetItem(", ".join(a.escopo))
            escopo.setFlags(escopo.flags() & ~Qt.ItemFlag.ItemIsEditable)
            teclas = QTableWidgetItem("; ".join(teclado.sequencias_do_perfil(a.id, perfil, trocas)))
            self.tabela.setItem(linha, ACAO, descricao)
            self.tabela.setItem(linha, ESCOPO, escopo)
            self.tabela.setItem(linha, TECLAS, teclas)

    def trocas(self) -> Dict[str, List[str]]:
        """As teclas que diferem das do perfil (levanta `ValueError` com a tecla ruim)."""
        perfil = self.perfil_escolhido()
        saida = {}
        for linha, id_ in enumerate(self._ids):
            texto = self.tabela.item(linha, TECLAS).text()
            try:
                novas = partir(texto)
            except ValueError as erro:
                raise ValueError(f"{self.tabela.item(linha, ACAO).text()}: {erro}") from erro
            if novas != teclado.sequencias_do_perfil(id_, perfil, {}):
                saida[id_] = novas
        return saida

    def escolha(self) -> Tuple[str, Dict[str, List[str]]]:
        return self.perfil_escolhido(), self.trocas()

    def _aceitar(self) -> None:
        try:
            perfil, trocas = self.escolha()
        except ValueError as erro:
            QMessageBox.warning(self, "Teclado", str(erro))
            return
        problemas = teclado.problemas(perfil, trocas)
        if problemas:
            QMessageBox.warning(self, "Teclado", "Estas teclas não podem valer:\n\n"
                                + "\n".join(com_nomes(p) for p in problemas[:12]))
            return
        self.accept()


def perguntar(janela) -> Optional[Tuple[str, Dict[str, List[str]]]]:
    dialogo = DialogoDoTeclado(janela, teclado.PERFIL, teclado.trocas)
    try:
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialogo.escolha()
    finally:
        dialogo.deleteLater()
