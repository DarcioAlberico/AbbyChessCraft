"""O diálogo da exportação (SPEC §12.1): as opções e os metadados do livro, depois de escolher
o arquivo e antes de escrever.

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

from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from abbychess import exportar as ex

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

        self.manter_margens = QCheckBox("Manter cabeçalhos, rodapés e números de página")
        self.so_verificadas = QCheckBox("Só as páginas verificadas")
        self.desenhar = QCheckBox("Diagramas confiáveis redesenhados do FEN (senão, o recorte)")
        self.marcas = QCheckBox("Marcar o começo de cada página ([p. N])")
        self.manter_margens.setChecked(opcoes.manter_margens)
        self.so_verificadas.setChecked(opcoes.so_verificadas)
        self.desenhar.setChecked(opcoes.desenhar_diagramas)
        self.marcas.setChecked(opcoes.marcas_de_pagina)
        caixa_opcoes = QGroupBox("Opções")
        coluna = QVBoxLayout(caixa_opcoes)
        for check in (self.manter_margens, self.so_verificadas, self.desenhar, self.marcas):
            coluna.addWidget(check)
        texto = formato in ("epub", "docx", "txt")
        self.manter_margens.setEnabled(texto)
        self.desenhar.setEnabled(formato in ("epub", "docx"))
        self.marcas.setEnabled(formato == "txt")
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
                         marcas_de_pagina=self.marcas.isChecked())

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

    def _aceitar(self) -> None:
        try:
            self.metadados()
        except ValueError as erro:
            QMessageBox.warning(self, "Metadados", str(erro))
            self.data.setFocus()
            return
        self.accept()


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
    """As opções da última exportação (`QSettings`), ou as padrão."""
    bruto = config.value(CHAVE, "")
    padrao = ex.Opcoes()
    if isinstance(bruto, (list, tuple)):        # o INI devolve a lista que as vírgulas fazem
        bruto = ",".join(str(b) for b in bruto)
    if not isinstance(bruto, str) or not bruto:
        return padrao
    marcadas = set(bruto.split(","))
    return ex.Opcoes(**{campo: campo in marcadas for campo in vars(padrao)})


def lembrar_opcoes(config, opcoes: ex.Opcoes) -> None:
    config.setValue(CHAVE, ",".join(c for c, v in vars(opcoes).items() if v) or "nenhuma")


def perguntar(janela, projeto, destino: Path) -> Optional[Escolha]:
    """O diálogo para o `destino`; `None` se o usuário cancelar."""
    formato = ex.formato_do_caminho(destino)
    dialogo = DialogoDeExportacao(janela, formato, opcoes_lembradas(janela.config),
                                  ex.ler_metadados(projeto), projeto.pasta, projeto.dados.nome)
    if dialogo.exec() != QDialog.DialogCode.Accepted:
        return None
    escolha = dialogo.escolha()
    lembrar_opcoes(janela.config, escolha.opcoes)
    return escolha
