"""O diálogo da exportação (SPEC §12.1): as opções e os metadados do livro, depois de escolher
o arquivo e antes de escrever, com a pré-visualização (§12.2) do que sairia.

As opções valem conforme o formato: o PDF pesquisável guarda a página inteira (nenhuma opção
de texto vale); o PGN só olha as páginas verificadas; as marcas de página são do TXT. Os
metadados (título, autores, editora, data, assuntos, direitos, identificador, edição
impressa e capa) são do EPUB e do DOCX e vão para `<projeto>/metadados.json`: o que se
preenche uma vez vale nas exportações seguintes. A capa escolhida fora do projeto é copiada
para a pasta dele.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QTextBrowser, QVBoxLayout, QWidget)

from abbychess import exportar as ex
from abbychess import links_de_analise as la

#: Os formatos com metadados (o PDF guarda o do arquivo original; TXT e PGN não têm).
COM_METADADOS = ("epub", "docx")


@dataclass(frozen=True)
class Escolha:
    """O que o diálogo devolve: as opções, os metadados do formulário (normalizados) e a
    capa escolhida fora do projeto (para copiar), ou `None`."""

    opcoes: ex.Opcoes
    metadados: dict
    capa: Optional[Path] = None


class DialogoDeExportacao(QDialog):
    def __init__(self, parent, formato: str, opcoes: ex.Opcoes, metadados: dict,
                 pasta_do_projeto: Path, titulo_padrao: str):
        super().__init__(parent)
        self.setWindowTitle(f"Exportar {formato.upper()}")
        self.formato = formato
        self.pasta = Path(pasta_do_projeto)
        self.capa_escolhida: Optional[Path] = None
        self.capa_atual = str(metadados.get("capa", "") or "")
        #: Quem faz a prévia: `(formato, opcoes, metadados)`; ela chega por `mostrar_previa`.
        self.ao_previsualizar = None
        self.janela_da_previa: Optional[JanelaDaPrevia] = None
        #: Falso depois de fechar: a prévia que chegar tarde não abre janela nenhuma.
        self.vivo = True

        self.manter_margens = QCheckBox("Manter cabeçalhos, rodapés e números de página")
        self.so_verificadas = QCheckBox("Só as páginas verificadas")
        self.desenhar = QCheckBox("Diagramas confiáveis redesenhados do FEN (senão, o recorte)")
        self.marcas = QCheckBox("Marcar o começo de cada página ([p. N])")
        self.manter_quebras = QCheckBox("Manter as quebras de linha e os hífens do impresso")
        self.manter_quebras.setToolTip("Cada linha impressa termina numa quebra dentro do "
                                       "parágrafo, e a palavra partida fica com o hífen")
        self.manter_quebras.setChecked(opcoes.manter_quebras)
        self.realcar = QCheckBox("Realçar os glifos de baixa confiança (DOCX)")
        self.realcar.setToolTip("Os glifos que a fila de revisão ainda pede saem com o "
                                "realce amarelo do Word")
        self.realcar.setChecked(opcoes.realcar_duvidosos)
        self.manter_margens.setChecked(opcoes.manter_margens)
        self.so_verificadas.setChecked(opcoes.so_verificadas)
        self.desenhar.setChecked(opcoes.desenhar_diagramas)
        self.marcas.setChecked(opcoes.marcas_de_pagina)
        self.analise = QComboBox()
        for site in la.SITES:
            self.analise.addItem(la.NOMES[site], site)
        self.analise.setCurrentIndex(la.SITES.index(opcoes.links_de_analise))
        self.analise.setAccessibleName("Link de análise dos diagramas")
        self.analise.setToolTip("Embaixo de cada diagrama lido (com FEN), o link que abre a "
                                "posição no tabuleiro de análise do site escolhido")
        rotulo_da_analise = QLabel("Link de análise dos diagramas:")
        rotulo_da_analise.setBuddy(self.analise)
        linha_da_analise = QWidget()
        analise_layout = QHBoxLayout(linha_da_analise)
        analise_layout.setContentsMargins(0, 0, 0, 0)
        analise_layout.addWidget(rotulo_da_analise)
        analise_layout.addWidget(self.analise)
        analise_layout.addStretch(1)
        caixa_opcoes = QGroupBox("Opções")
        coluna = QVBoxLayout(caixa_opcoes)
        for check in (self.manter_margens, self.manter_quebras, self.so_verificadas,
                      self.desenhar, self.marcas, self.realcar, linha_da_analise):
            coluna.addWidget(check)
        texto = formato in ("epub", "docx", "txt")
        self.manter_margens.setEnabled(texto)
        self.manter_quebras.setEnabled(texto)
        self.desenhar.setEnabled(formato in ("epub", "docx"))
        self.marcas.setEnabled(formato == "txt")
        self.realcar.setEnabled(formato == "docx")
        linha_da_analise.setEnabled(formato in ("epub", "docx"))
        self.so_verificadas.setEnabled(formato != "pdf")
        if formato == "pdf":
            coluna.addWidget(QLabel("O PDF pesquisável guarda as páginas inteiras: as opções de "
                                    "texto não se aplicam."))

        self.titulo = QLineEdit(str(metadados.get("titulo", "") or ""))
        self.titulo.setPlaceholderText(titulo_padrao)
        self.autores = QLineEdit("; ".join(_lista(metadados.get("autores")
                                                  or metadados.get("autor"))))
        self.autores.setPlaceholderText("Separe os nomes com ;")
        self.editora = QLineEdit(str(metadados.get("editora", "") or ""))
        self.data = QLineEdit(str(metadados.get("data", "") or ""))
        self.data.setPlaceholderText("AAAA, AAAA-MM ou AAAA-MM-DD")
        self.assuntos = QLineEdit("; ".join(_lista(metadados.get("assuntos"))))
        self.assuntos.setPlaceholderText("Xadrez; Finais")
        self.direitos = QLineEdit(str(metadados.get("direitos", "") or ""))
        self.identificador = QLineEdit(str(metadados.get("identificador", "") or ""))
        self.identificador.setPlaceholderText("vazio: um identificador estável pelo título e autores")
        self.fonte = QLineEdit(str(metadados.get("fonte", "") or ""))
        self.fonte.setPlaceholderText("a edição impressa; vazio: o título")
        self.capa = QLineEdit(self.capa_atual)
        self.capa.setReadOnly(True)
        self.capa.setPlaceholderText("sem capa")
        escolher = QPushButton("Escolher…")
        escolher.clicked.connect(self._escolher_capa)
        tirar = QPushButton("Tirar")
        tirar.clicked.connect(self._tirar_capa)
        linha_da_capa = QWidget()
        capa_layout = QHBoxLayout(linha_da_capa)
        capa_layout.setContentsMargins(0, 0, 0, 0)
        capa_layout.addWidget(self.capa, 1)
        capa_layout.addWidget(escolher)
        capa_layout.addWidget(tirar)

        self.caixa_metadados = QGroupBox("Metadados do livro")
        formulario = QFormLayout(self.caixa_metadados)
        for rotulo, campo in (("Título", self.titulo), ("Autores", self.autores),
                              ("Editora", self.editora), ("Data", self.data),
                              ("Assuntos", self.assuntos), ("Direitos", self.direitos),
                              ("Identificador", self.identificador),
                              ("Edição impressa", self.fonte), ("Capa", linha_da_capa)):
            formulario.addRow(rotulo, campo)
            if isinstance(campo, QLineEdit):
                campo.setAccessibleName(rotulo)
        self.caixa_metadados.setEnabled(formato in COM_METADADOS)
        if formato not in COM_METADADOS:
            self.caixa_metadados.setToolTip("Os metadados são do EPUB e do DOCX.")

        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                  QDialogButtonBox.StandardButton.Cancel)
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Exportar")
        self.btn_previa = botoes.addButton("Pré-visualizar…",
                                           QDialogButtonBox.ButtonRole.ActionRole)
        self.btn_previa.setToolTip("O que a exportação escreveria, com estas opções, e o "
                                   "relatório, sem gravar nada")
        self.btn_previa.setEnabled(formato != "pdf")
        self.btn_previa.clicked.connect(self.previsualizar)
        self.btn_exportar = botoes.button(QDialogButtonBox.StandardButton.Ok)
        botoes.accepted.connect(self._aceitar)
        botoes.rejected.connect(self.reject)
        corpo = QVBoxLayout(self)
        corpo.addWidget(caixa_opcoes)
        corpo.addWidget(self.caixa_metadados)
        corpo.addWidget(botoes)

    # ------------------------------------------------------------------
    def _escolher_capa(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "A capa do livro", str(self.pasta),
                                                 "Imagens (*.png *.jpg *.jpeg *.gif *.webp)")
        if caminho:
            self.capa_escolhida = Path(caminho)
            self.capa.setText(caminho)

    def _tirar_capa(self) -> None:
        self.capa_escolhida = None
        self.capa_atual = ""
        self.capa.clear()

    def opcoes(self) -> ex.Opcoes:
        return ex.Opcoes(manter_margens=self.manter_margens.isChecked(),
                         so_verificadas=self.so_verificadas.isChecked(),
                         desenhar_diagramas=self.desenhar.isChecked(),
                         marcas_de_pagina=self.marcas.isChecked(),
                         manter_quebras=self.manter_quebras.isChecked(),
                         realcar_duvidosos=self.realcar.isChecked(),
                         links_de_analise=self.analise.currentData())

    def metadados(self) -> dict:
        """O formulário como `metadados.json`. A capa é a de antes (também quando outra foi
        escolhida: quem grava a troca pela nova, e se não puder gravar, a de antes vale);
        sem capa no campo, nenhuma. Fora do EPUB e do DOCX, vazio."""
        if self.formato not in COM_METADADOS:
            return {}
        bruto = {"titulo": self.titulo.text(), "autores": self.autores.text(),
                 "editora": self.editora.text(), "data": self.data.text(),
                 "assuntos": self.assuntos.text(), "direitos": self.direitos.text(),
                 "identificador": self.identificador.text(), "fonte": self.fonte.text()}
        if self.capa.text() and self.capa_atual:
            bruto["capa"] = self.capa_atual
        return ex.normalizar_metadados(bruto)

    def escolha(self) -> Escolha:
        return Escolha(self.opcoes(), self.metadados(), self.capa_escolhida)

    def previsualizar(self) -> None:
        """Pede a prévia com o que está no diálogo agora; ela abre quando chegar."""
        try:
            metadados = self.metadados()
        except ValueError as erro:
            QMessageBox.warning(self, "Metadados", str(erro))
            return
        if self.ao_previsualizar is not None:
            # Exportar espera a prévia: as duas vão na mesma fila de tarefas.
            self.btn_previa.setEnabled(False)
            self.btn_exportar.setEnabled(False)
            self.btn_previa.setText("Pré-visualizando…")
            self.ao_previsualizar(self.formato, self.opcoes(),
                                  metadados if self.formato in COM_METADADOS else None)

    def previa_falhou(self, _mensagem: str = "") -> None:
        """A prévia não saiu (o aviso já foi): os botões voltam."""
        if not self.vivo:
            return
        self.btn_previa.setEnabled(True)
        self.btn_exportar.setEnabled(True)
        self.btn_previa.setText("Pré-visualizar…")

    def mostrar_previa(self, html: str) -> None:
        if not self.vivo:                       # chegou depois de fechar: fica de fora
            return
        self.previa_falhou()
        if self.janela_da_previa is None:
            self.janela_da_previa = JanelaDaPrevia(self)
        self.janela_da_previa.mostrar(html)

    def done(self, resultado: int) -> None:
        """Ao fechar (Exportar ou Cancelar), a prévia fecha junto e a que chegar tarde
        é ignorada."""
        self.vivo = False
        if self.janela_da_previa is not None:
            self.janela_da_previa.close()
        super().done(resultado)

    def _aceitar(self) -> None:
        try:
            self.metadados()
        except ValueError as erro:
            QMessageBox.warning(self, "Metadados", str(erro))
            self.data.setFocus()
            return
        self.accept()


class JanelaDaPrevia(QDialog):
    """A prévia em HTML (§12.2), ao lado do diálogo: não grava nada, e pode ficar aberta
    enquanto as opções mudam (Pré-visualizar de novo a refaz)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pré-visualização da exportação")
        self.resize(760, 820)
        self.navegador = QTextBrowser()
        self.navegador.setOpenLinks(False)
        self.navegador.anchorClicked.connect(_abrir_fora)
        self.navegador.setAccessibleName("Pré-visualização da exportação")
        fechar = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        fechar.rejected.connect(self.close)
        corpo = QVBoxLayout(self)
        corpo.addWidget(self.navegador, 1)
        corpo.addWidget(fechar)

    def mostrar(self, html: str) -> None:
        self.navegador.setHtml(html)
        self.show()
        self.raise_()


def _abrir_fora(url: QUrl) -> None:
    """O link de análise da prévia abre no navegador; o resto da prévia não navega."""
    if url.scheme() == "https":
        QDesktopServices.openUrl(url)


def _lista(valor) -> list:
    """Os itens de uma lista do arquivo, tolerando o que foi escrito à mão (texto, número)."""
    if valor is None:
        return []
    if isinstance(valor, str):
        return [valor] if valor.strip() else []
    if not isinstance(valor, (list, tuple)):
        return [str(valor)]
    return [str(v) for v in valor if v is not None and str(v).strip()]


# ----------------------------------------------------------------------
# As opções lembradas entre exportações
# ----------------------------------------------------------------------

CHAVE = "exportacao/opcoes"


def opcoes_lembradas(config) -> ex.Opcoes:
    """As opções da última exportação (`QSettings`), ou as padrão. As de ligar e desligar
    vão pelo nome; as de escolher, como `campo=valor` (o valor que não vale mais fica no
    padrão)."""
    bruto = config.value(CHAVE, "")
    padrao = ex.Opcoes()
    if isinstance(bruto, (list, tuple)):        # o INI devolve a lista que as vírgulas fazem
        bruto = ",".join(str(b) for b in bruto)
    if not isinstance(bruto, str) or not bruto:
        return padrao
    marcadas = set(bruto.split(","))
    escolhas = dict(m.split("=", 1) for m in marcadas if "=" in m)
    campos = {}
    for campo, valor in vars(padrao).items():
        if isinstance(valor, bool):
            campos[campo] = campo in marcadas
        elif campo == "links_de_analise" and escolhas.get(campo) in la.SITES:
            campos[campo] = escolhas[campo]
    return ex.Opcoes(**campos)


def lembrar_opcoes(config, opcoes: ex.Opcoes) -> None:
    config.setValue(CHAVE, ",".join(c if v is True else f"{c}={v}"
                                    for c, v in vars(opcoes).items()
                                    if v is True or not isinstance(v, bool)) or "nenhuma")


def perguntar(janela, projeto, destino: Path) -> Optional[Escolha]:
    """O diálogo para o `destino`; `None` se o usuário cancelar."""
    formato = ex.formato_do_caminho(destino)
    dialogo = DialogoDeExportacao(janela, formato, opcoes_lembradas(janela.config),
                                  ex.ler_metadados(projeto), projeto.pasta, projeto.dados.nome)

    def previsualizar(formato_, opcoes, metadados):
        janela.livro.previa(formato_, opcoes, metadados, dialogo.mostrar_previa,
                            dialogo.previa_falhou)
    dialogo.ao_previsualizar = previsualizar
    try:
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return None
        escolha = dialogo.escolha()
    finally:
        dialogo.ao_previsualizar = None         # sem ciclo, e a memória da prévia sai
        dialogo.deleteLater()
    lembrar_opcoes(janela.config, escolha.opcoes)
    return escolha
