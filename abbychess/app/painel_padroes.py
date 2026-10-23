"""Os padrões ensinados para este livro (SPEC §8.3), por caractere, com a opção de esquecer.

Ensinar errado acontece: um `l` ensinado como `1` passa a ler errado todas as
repetições dele. Aqui se vê cada amostra de cada caractere e se apaga a ruim. O campo de
busca acha o caractere; cada amostra diz a página de onde veio, a altura relativa, o efeito
(negrito, itálico: desde o passo I) e quantos glifos do livro ela leu; o duplo clique (ou
"Ir à origem") abre a página no glifo de origem. Esquecer (o botão, ou Delete) não
pergunta: o Ctrl+Z desfaz, e os glifos que a amostra leu voltam à fila.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QSplitter, QVBoxLayout, QWidget)

from abbychess.app.painel_treino import FONTE_DE_SIMBOLOS
from abbychess.app import vazios


class _GradeDeAmostras(QListWidget):
    """A grade das amostras: Delete esquece as selecionadas."""

    def __init__(self, painel: "PainelDePadroes"):
        super().__init__()
        self._painel = painel

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key.Key_Delete:
            self._painel._esquecer()
            return
        super().keyPressEvent(evento)


class PainelDePadroes(QWidget):
    esquecer = Signal(list)
    #: A origem da amostra escolhida: (índice da página, gid ou None).
    ir_para = Signal(int, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._padroes: Dict[str, List[Path]] = {}
        self._detalhes: Dict[str, dict] = {}

        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Caractere")
        self.busca.setAccessibleName("Buscar o caractere nos padrões")
        self.busca.setClearButtonEnabled(True)
        self.busca.textChanged.connect(self._filtrar)

        self.caracteres = QListWidget()
        self.caracteres.setFont(QFont(FONTE_DE_SIMBOLOS, 12))
        self.caracteres.currentTextChanged.connect(self._mostrar_amostras)

        self.amostras = _GradeDeAmostras(self)
        self.amostras.setViewMode(QListWidget.ViewMode.IconMode)
        self.amostras.setIconSize(QSize(48, 48))
        self.amostras.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.amostras.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.amostras.setWordWrap(True)
        self.amostras.itemActivated.connect(self._ir_a_origem)
        self.amostras.itemSelectionChanged.connect(self._mostrar_detalhe)

        self.detalhe = QLabel("")
        self.detalhe.setWordWrap(True)
        self.botao_ir = QPushButton("Ir à origem")
        self.botao_ir.clicked.connect(lambda: self._ir_a_origem(self.amostras.currentItem()))
        self.botao_esquecer = QPushButton("Esquecer (Delete)")
        self.botao_esquecer.setToolTip("Apaga as amostras selecionadas; os glifos que elas "
                                       "leram voltam à fila. Ctrl+Z desfaz.")
        self.botao_esquecer.clicked.connect(self._esquecer)
        self.resumo = QLabel("")

        esquerda = QWidget()
        caixa_esquerda = QVBoxLayout(esquerda)
        caixa_esquerda.setContentsMargins(0, 0, 0, 0)
        caixa_esquerda.addWidget(self.busca)
        caixa_esquerda.addWidget(self.caracteres)

        direita = QWidget()
        caixa_direita = QVBoxLayout(direita)
        caixa_direita.setContentsMargins(0, 0, 0, 0)
        caixa_direita.addWidget(self.amostras)
        caixa_direita.addWidget(self.detalhe)
        botoes = QHBoxLayout()
        botoes.addWidget(self.resumo, 1)
        botoes.addWidget(self.botao_ir)
        botoes.addWidget(self.botao_esquecer)
        caixa_direita.addLayout(botoes)

        divisor = QSplitter(Qt.Orientation.Horizontal)
        divisor.addWidget(esquerda)
        divisor.addWidget(direita)
        divisor.setSizes([140, 400])

        caixa = QVBoxLayout(self)
        caixa.addWidget(divisor)

    def atualizar(self, padroes: Dict[str, List[Path]],
                  detalhes: Optional[Dict[str, dict]] = None) -> None:
        """`detalhes`: caminho -> {"origem": (página, gid) ou None, "altura", "efeito",
        "lidos"}."""
        atual = self.caracteres.currentItem()
        escolhido = atual.data(Qt.ItemDataRole.UserRole) if atual else None
        self._padroes, self._detalhes = padroes, detalhes or {}
        self.caracteres.blockSignals(True)
        self.caracteres.clear()
        for char, arquivos in sorted(padroes.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            item = QListWidgetItem(f"{char}    {len(arquivos)}")
            item.setData(Qt.ItemDataRole.UserRole, char)
            self.caracteres.addItem(item)
            if char == escolhido:
                self.caracteres.setCurrentItem(item)
        self.caracteres.blockSignals(False)
        total = sum(len(v) for v in padroes.values())
        self.resumo.setText(f"{total} amostras em {len(padroes)} caracteres" if total
                            else vazios.SEM_PADROES)
        self.resumo.setWordWrap(True)
        self._filtrar(self.busca.text())
        self._mostrar_amostras()

    def _filtrar(self, texto: str) -> None:
        """O campo de busca: só os caracteres que contêm o texto, e o primeiro escolhido."""
        primeiro = None
        for n in range(self.caracteres.count()):
            item = self.caracteres.item(n)
            mostra = not texto or texto in item.data(Qt.ItemDataRole.UserRole)
            item.setHidden(not mostra)
            if mostra and primeiro is None:
                primeiro = item
        atual = self.caracteres.currentItem()
        if texto and primeiro is not None and (atual is None or atual.isHidden()):
            self.caracteres.setCurrentItem(primeiro)

    def _texto_da_amostra(self, arquivo) -> str:
        d = self._detalhes.get(str(arquivo), {})
        origem = d.get("origem")
        partes = [f"p. {origem[0] + 1}" if origem else "origem ?"]
        if d.get("lidos"):
            partes.append(f"leu {d['lidos']}")
        return " · ".join(partes)

    def _dica_da_amostra(self, arquivo) -> str:
        d = self._detalhes.get(str(arquivo), {})
        origem = d.get("origem")
        linhas = [Path(arquivo).stem,
                  f"Origem: página {origem[0] + 1}" if origem else "Origem: não diz",
                  f"Altura relativa: {d['altura']:.2f}" if d.get("altura") is not None
                  else "Altura relativa: —",
                  f"Efeito: {d['efeito']}" if d.get("efeito") else "Efeito: — (passo I)",
                  f"Glifos do livro lidos por ela: {d.get('lidos', 0)}"]
        return "\n".join(linhas)

    def _mostrar_amostras(self, *_args) -> None:
        self.amostras.clear()
        atual = self.caracteres.currentItem()
        if atual is None:
            self.detalhe.setText("")
            return
        for arquivo in self._padroes.get(atual.data(Qt.ItemDataRole.UserRole), []):
            item = QListWidgetItem(QIcon(QPixmap(str(arquivo))), self._texto_da_amostra(arquivo))
            item.setData(Qt.ItemDataRole.UserRole, str(arquivo))
            item.setToolTip(self._dica_da_amostra(arquivo))
            self.amostras.addItem(item)
        self._mostrar_detalhe()

    def _mostrar_detalhe(self) -> None:
        itens = self.amostras.selectedItems()
        if len(itens) == 1:
            self.detalhe.setText(self._dica_da_amostra(itens[0].data(Qt.ItemDataRole.UserRole))
                                 .replace("\n", " · "))
        else:
            self.detalhe.setText(f"{len(itens)} selecionadas" if itens else
                                 "Duplo clique: ir à origem · Delete: esquecer")
        tem_origem = len(itens) == 1 and bool(
            self._detalhes.get(itens[0].data(Qt.ItemDataRole.UserRole), {}).get("origem"))
        self.botao_ir.setEnabled(tem_origem)

    def _ir_a_origem(self, item) -> None:
        if item is None:
            return
        origem = self._detalhes.get(item.data(Qt.ItemDataRole.UserRole), {}).get("origem")
        if origem:
            self.ir_para.emit(origem[0], origem[1])

    def _esquecer(self) -> None:
        caminhos = [i.data(Qt.ItemDataRole.UserRole) for i in self.amostras.selectedItems()]
        if caminhos:
            self.esquecer.emit(caminhos)
