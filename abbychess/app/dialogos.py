"""Os diálogos da janela principal: criar e abrir projeto, a fonte sumida, o lote e a
exportação. Cada função pergunta o que precisa e chama os controladores com a resposta."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QInputDialog, QLineEdit, QMessageBox)

from abbychess import livro
from abbychess import nativo
from abbychess import pagina as pg
from abbychess.projeto import ProjetoDeLivro, ProjetoInvalido

FILTRO_DE_LIVROS = "Livros (*.pdf *.png *.jpg *.jpeg *.tif *.tiff *.bmp)"
FILTROS_DE_EXPORTACAO = {"PDF pesquisável (*.pdf)": ".pdf", "Word (*.docx)": ".docx",
                         "EPUB (*.epub)": ".epub"}

IDIOMAS = (("Português", "pt"), ("English", "en"), ("Español", "es"),
           ("Deutsch", "de"), ("Français", "fr"))


@dataclass(frozen=True)
class OpcoesDoNovoProjeto:
    nome: str
    idioma: str
    intervalo: tuple[int, int]


def intervalo_do_corpo(texto: str, total: int) -> tuple[int, int]:
    """Um intervalo contínuo visível ao usuário, convertido para índices de zero."""
    indices = livro.interpretar_intervalo(texto, total)
    if not indices:
        raise ValueError("Informe ao menos uma página do corpo do livro.")
    if indices != list(range(indices[0], indices[-1] + 1)):
        raise ValueError("O corpo do livro deve ser um intervalo contínuo, como 5-230.")
    return indices[0], indices[-1]


class DialogoDeNovoProjeto(QDialog):
    """Nome, idioma e corpo num formulário só, depois da escolha do arquivo (§9.1)."""

    def __init__(self, parent, nome: str, total: int):
        super().__init__(parent)
        self.setWindowTitle("Novo projeto")
        self.total = total
        self.nome = QLineEdit(nome)
        self.idioma = QComboBox()
        for rotulo, codigo in IDIOMAS:
            self.idioma.addItem(rotulo, codigo)
        self.intervalo = QLineEdit(f"1-{total}")
        self.intervalo.setToolTip("Páginas do conteúdo, sem capa e sumário; por exemplo, 5-230")
        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                  QDialogButtonBox.StandardButton.Cancel)
        botoes.accepted.connect(self._aceitar)
        botoes.rejected.connect(self.reject)
        formulario = QFormLayout(self)
        formulario.addRow("Nome do livro:", self.nome)
        formulario.addRow("Idioma:", self.idioma)
        formulario.addRow(f"Corpo (páginas 1-{total}):", self.intervalo)
        formulario.addRow(botoes)
        self.opcoes: Optional[OpcoesDoNovoProjeto] = None

    def _aceitar(self) -> None:
        try:
            intervalo = intervalo_do_corpo(self.intervalo.text(), self.total)
        except ValueError as erro:
            QMessageBox.warning(self, "Intervalo do corpo", str(erro))
            self.intervalo.setFocus()
            return
        self.opcoes = OpcoesDoNovoProjeto(
            self.nome.text().strip(), str(self.idioma.currentData()), intervalo)
        self.accept()

    @classmethod
    def obter(cls, parent, nome: str, total: int) -> Optional[OpcoesDoNovoProjeto]:
        dialogo = cls(parent, nome, total)
        return dialogo.opcoes if dialogo.exec() == QDialog.DialogCode.Accepted else None


def novo_projeto(janela) -> Optional[ProjetoDeLivro]:
    config = janela.config
    ultima = config.value("ultima_fonte", str(Path.home()))
    fonte, _ = QFileDialog.getOpenFileName(janela, "Livro (PDF ou imagem)", ultima,
                                           FILTRO_DE_LIVROS)
    if not fonte:
        return None
    config.setValue("ultima_fonte", str(Path(fonte).parent))
    try:
        total = pg.FonteDePaginas(fonte).total
    except OSError as erro:
        QMessageBox.warning(janela, "Novo projeto", f"A fonte do livro não abriu:\n{erro}")
        return None
    opcoes = DialogoDeNovoProjeto.obter(janela, Path(fonte).stem, total)
    if opcoes is None:
        return None
    padrao = config.value("pasta_dos_projetos", str(Path.home() / "AbbyChessCraft"))
    Path(padrao).mkdir(parents=True, exist_ok=True)
    pasta_mae = QFileDialog.getExistingDirectory(
        janela, "Pasta onde guardar o projeto (sem acentos no caminho)", padrao)
    if not pasta_mae:
        return None
    importadas = ()
    try:
        projeto = ProjetoDeLivro.criar(pasta_mae, opcoes.nome, fonte)
    except ProjetoInvalido as erro:
        QMessageBox.warning(janela, "Novo projeto", str(erro))
        return None
    projeto.dados.idioma = opcoes.idioma
    projeto.dados.extras["intervalo_do_corpo"] = list(opcoes.intervalo)
    projeto.salvar()
    try:
        camada = nativo.oferta(fonte)
        if camada.disponivel and QMessageBox.question(
                janela, "Texto nativo encontrado",
                (f"O PDF tem texto tipográfico confiável em {camada.aceitas} de "
                 f"{camada.amostradas} página(s) examinada(s). Usar esse texto sem OCR?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes) == QMessageBox.StandardButton.Yes:
            resultado = nativo.importar(projeto, idioma=opcoes.idioma)
            importadas = resultado.importadas
            janela.statusBar().showMessage(
                f"Texto nativo usado em {len(resultado.importadas)} página(s); "
                f"{len(resultado.recusadas)} ficaram para OCR.", 12000)
    except (OSError, ValueError) as erro:
        # A oferta é uma otimização segura: se a camada não abre ou não monta, o projeto
        # continua novo e o caminho de OCR de sempre permanece disponível.
        QMessageBox.warning(janela, "Texto nativo",
                            f"A camada de texto não pôde ser usada ({erro}). O OCR continua disponível.")
    inicio, fim = opcoes.intervalo
    candidatos = [i for i in range(inicio, fim + 1) if i not in set(importadas)]
    projeto.dados.extras["amostra_guiada_pendente"] = bool(candidatos)
    projeto.dados.extras[livro.CHAVE_DOS_CANDIDATOS_DA_AMOSTRA] = candidatos
    projeto.salvar()
    config.setValue("pasta_dos_projetos", pasta_mae)
    return projeto


def escolher_projeto(janela) -> Optional[ProjetoDeLivro]:
    padrao = janela.config.value("pasta_dos_projetos", str(Path.home()))
    pasta = QFileDialog.getExistingDirectory(janela, "Pasta do projeto", padrao)
    if not pasta:
        return None
    projeto = abrir_pasta(janela, pasta)
    if projeto is not None:
        janela.config.setValue("pasta_dos_projetos", str(Path(pasta).parent))
    return projeto


def abrir_pasta(janela, pasta: str) -> Optional[ProjetoDeLivro]:
    try:
        return ProjetoDeLivro.abrir(pasta)
    except ProjetoInvalido as erro:
        QMessageBox.warning(janela, "Abrir projeto", str(erro))
        return None


def preparar_abertura(janela, projeto: ProjetoDeLivro) -> Optional[pg.FonteDePaginas]:
    """A fonte do projeto, pedindo ao usuário se ela sumiu, e o aviso do só leitura.
    `None` (e o projeto fechado) se não deu: o projeto aberto antes continua."""
    if projeto.fonte_ausente and not localizar_fonte(janela, projeto):
        projeto.fechar()
        janela.statusBar().showMessage("O projeto não foi aberto: a fonte do livro não foi "
                                       "indicada.", 8000)
        return None
    try:
        fonte = pg.fonte_do_projeto(projeto)
    except OSError as erro:
        projeto.fechar()
        QMessageBox.warning(janela, "Abrir projeto", f"A fonte do livro não abriu:\n{erro}")
        return None
    if projeto.somente_leitura:
        QMessageBox.information(
            janela, "Abrir projeto",
            (projeto.motivo_so_leitura or
             f"O projeto é da versão {projeto.dados.versao} do formato, mais nova que a "
             "deste programa. Ele abre só para leitura.")
            + " Dá para ver as páginas, mas nada do que for feito aqui é gravado (nem o "
            "que você corrigir)." + ("" if projeto.motivo_so_leitura else
                                     " Para trabalhar nele, abra-o com a versão do "
                                     "programa que o gravou."))
    return fonte


def localizar_fonte(janela, projeto: ProjetoDeLivro) -> bool:
    """A fonte sumiu e não foi achada pelo SHA-256: o usuário diz onde ela está."""
    QMessageBox.warning(janela, "Abrir projeto",
                        f"A fonte do livro não está mais em\n{projeto.fonte}\n\nMostre "
                        "onde ela está agora; o programa confere que é o mesmo arquivo."
                        + ("\n\nComo o projeto é só para leitura, o lugar novo vale só "
                           "nesta sessão." if projeto.somente_leitura else ""))
    while True:
        caminho, _ = QFileDialog.getOpenFileName(
            janela, "Onde está a fonte do livro?", str(projeto.pasta.parent),
            "PDF ou imagem (*.pdf *.png *.jpg *.jpeg *.tif *.tiff *.bmp)")
        if not caminho:
            return False
        try:
            projeto.relocalizar(caminho)
            return True
        except (ProjetoInvalido, OSError) as erro:
            QMessageBox.warning(janela, "Abrir projeto", str(erro))


def avisos_da_abertura(janela, projeto: ProjetoDeLivro) -> None:
    """O que a abertura achou e o usuário precisa saber: migração, fonte movida."""
    if projeto.migrado:
        QMessageBox.information(
            janela, "Abrir projeto",
            "O projeto passou ao formato novo. Os programas de antes não o abrem mais "
            "para trabalhar (só para ver). A cópia das páginas, das áreas e do "
            f"projeto.json de antes está em\n{projeto.pasta / 'backup-v1'}")
    if projeto.fonte_relocalizada:
        QMessageBox.information(
            janela, "Abrir projeto", f"A fonte do livro não estava mais no lugar "
            f"gravado e foi achada (o mesmo arquivo, pelo conteúdo) em:\n{projeto.fonte}"
            + ("\n\nComo o projeto é só para leitura, isso vale nesta sessão, e a "
               "busca se repete a cada abertura." if projeto.somente_leitura else ""))


def avisos_dos_modelos(janela, estado: dict, padroes: int) -> None:
    """Os modelos globais carregaram (no servidor de leitura, §11, ou aqui): a rede ausente
    e o resumo na barra."""
    if not estado.get("rede"):
        QMessageBox.warning(janela, "Modelo", "A rede de glifos do PyBoxEditor não "
                            "carregou. A leitura usa só os padrões e a base global.")
    janela.statusBar().showMessage(
        f"Modelos prontos. Base global com {estado.get('base', 0)} referências; "
        f"{padroes} padrões deste livro.", 8000)


def intervalo_do_lote(janela, projeto, total: int) -> Optional[Tuple[List[int], bool]]:
    """As páginas do lote e se as já lidas são lidas de novo; `None` se cancelou."""
    texto, ok = QInputDialog.getText(
        janela, "Reconhecer o livro",
        f"Páginas a reconhecer (de 1 a {total}; por exemplo 26-27, 30):", text=f"1-{total}")
    if not ok:
        return None
    try:
        indices = livro.interpretar_intervalo(texto, total)
    except ValueError as erro:
        QMessageBox.warning(janela, "Reconhecer o livro", str(erro))
        return None
    refazer = False
    from abbychess.modelo import VERIFICADA

    lidas = livro.ja_lidas(projeto, indices)
    verificadas = [i for i in lidas if projeto.estado_da_pagina(i) == VERIFICADA]
    lidas = [i for i in lidas if i not in verificadas]      # essas o lote pula sempre
    if lidas:
        botoes = QMessageBox.StandardButton
        pulam = (f" ({len(verificadas)} verificada(s), que o lote pula sempre)"
                 if verificadas else "")
        resposta = QMessageBox.question(
            janela, "Reconhecer o livro",
            f"{len(lidas)} das {len(indices)} páginas já foram reconhecidas{pulam}. Ler "
            "essas de novo?\n\nSim as lê de novo mantendo as correções manuais e os glifos "
            "revisados; a página de antes fica em Página › Voltar ao estado antes do lote. "
            "Não as pula e lê só as outras.",
            botoes.Yes | botoes.No | botoes.Cancel, botoes.No)
        if resposta == botoes.Cancel:
            return None
        refazer = resposta == botoes.Yes
    return indices, refazer


def reler_depois(janela, paginas, *, faltou: bool) -> Optional[bool]:
    """Retomar o lote com páginas que ele não sobrescreveu: lê-las também? None é cancelar.
    Sem nada que tenha faltado do lote, a pergunta é só "ler essas?" (Sim ou Cancelar)."""
    botoes = QMessageBox.StandardButton
    lista = ", ".join(str(i + 1) for i in paginas)
    efeito = ("Sim as lê de novo, a aberta também: as correções manuais e os glifos revisados "
              "ficam, as outras mudanças delas saem, e o Ctrl+Z delas deixa de valer.")
    if faltou:
        texto = (f"O lote não sobrescreveu as páginas {lista}, porque você as mudou. Ler essas "
                 f"também?\n\n{efeito} Não lê só o que faltou do lote.")
        opcoes, padrao = botoes.Yes | botoes.No | botoes.Cancel, botoes.No
    else:
        texto = (f"O lote não sobrescreveu as páginas {lista}, porque você as mudou. Ler "
                 f"essas agora?\n\n{efeito}")
        opcoes, padrao = botoes.Yes | botoes.Cancel, botoes.Cancel
    resposta = QMessageBox.question(janela, "Retomar o lote", texto, opcoes, padrao)
    if resposta == botoes.Cancel:
        return None
    return resposta == botoes.Yes


def destino_da_exportacao(janela, projeto) -> Optional[Path]:
    if not projeto.paginas_lidas():
        QMessageBox.information(janela, "Exportar", "Nenhuma página foi reconhecida ainda.")
        return None
    padrao = janela.config.value("pasta_de_exportacao", str(projeto.pasta))
    caminho, filtro = QFileDialog.getSaveFileName(
        janela, "Exportar o livro", str(Path(padrao) / projeto.pasta.name),
        ";;".join(FILTROS_DE_EXPORTACAO))
    if not caminho:
        return None
    destino = Path(caminho)
    if destino.suffix.lower() not in FILTROS_DE_EXPORTACAO.values():
        destino = destino.with_suffix(FILTROS_DE_EXPORTACAO.get(filtro, ".pdf"))
    janela.config.setValue("pasta_de_exportacao", str(destino.parent))
    return destino


def confirmar(janela, titulo: str, pergunta: str) -> bool:
    return QMessageBox.question(janela, titulo, pergunta) == QMessageBox.StandardButton.Yes
