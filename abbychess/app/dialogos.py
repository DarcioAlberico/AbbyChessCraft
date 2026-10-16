"""Os diálogos da janela principal: criar e abrir projeto, a fonte sumida, o lote e a
exportação. Cada função pergunta o que precisa e chama os controladores com a resposta."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from abbychess import livro
from abbychess import pagina as pg
from abbychess.projeto import ProjetoDeLivro, ProjetoInvalido

FILTRO_DE_LIVROS = "Livros (*.pdf *.png *.jpg *.jpeg *.tif *.tiff *.bmp)"
FILTROS_DE_EXPORTACAO = {"PDF pesquisável (*.pdf)": ".pdf", "Word (*.docx)": ".docx",
                         "EPUB (*.epub)": ".epub"}


def novo_projeto(janela) -> Optional[ProjetoDeLivro]:
    config = janela.config
    ultima = config.value("ultima_fonte", str(Path.home()))
    fonte, _ = QFileDialog.getOpenFileName(janela, "Livro (PDF ou imagem)", ultima,
                                           FILTRO_DE_LIVROS)
    if not fonte:
        return None
    config.setValue("ultima_fonte", str(Path(fonte).parent))
    nome, ok = QInputDialog.getText(janela, "Novo projeto", "Nome do livro:",
                                    text=Path(fonte).stem)
    if not ok:
        return None
    padrao = config.value("pasta_dos_projetos", str(Path.home() / "AbbyChessCraft"))
    Path(padrao).mkdir(parents=True, exist_ok=True)
    pasta_mae = QFileDialog.getExistingDirectory(
        janela, "Pasta onde guardar o projeto (sem acentos no caminho)", padrao)
    if not pasta_mae:
        return None
    try:
        projeto = ProjetoDeLivro.criar(pasta_mae, nome, fonte)
    except ProjetoInvalido as erro:
        QMessageBox.warning(janela, "Novo projeto", str(erro))
        return None
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


def avisos_da_abertura(janela, projeto: ProjetoDeLivro, leitor) -> None:
    """O que a abertura achou e o usuário precisa saber: rede ausente, migração, fonte movida."""
    if leitor.rede is None:
        QMessageBox.warning(janela, "Modelo", "A rede de glifos do PyBoxEditor não "
                            "carregou. A leitura usa só os padrões e a base global.")
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
    janela.statusBar().showMessage(
        f"Projeto aberto. Base global com {leitor.base.total if leitor.base else 0} "
        f"referências; {leitor.arquivos_de_padrao()} padrões deste livro.", 8000)


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
    lidas = livro.ja_lidas(projeto, indices)
    if lidas:
        botoes = QMessageBox.StandardButton
        resposta = QMessageBox.question(
            janela, "Reconhecer o livro",
            f"{len(lidas)} das {len(indices)} páginas já foram reconhecidas. Reconhecer "
            "essas de novo?\n\nSim descarta os boxes delas e as correções só desta "
            "ocorrência (os padrões ficam). Não as pula e lê só as outras.",
            botoes.Yes | botoes.No | botoes.Cancel, botoes.No)
        if resposta == botoes.Cancel:
            return None
        refazer = resposta == botoes.Yes
    return indices, refazer


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
