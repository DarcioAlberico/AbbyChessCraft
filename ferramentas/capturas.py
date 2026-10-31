"""Capturas da janela para a revisão de design (roadmap, passo A2 em diante).

Abre a janela num projeto e grava PNGs de cada arranjo nas resoluções de §3.1 (1366×768 e
1920×1080; 1280×720 para o empilhado padrão), com a página reconhecida, e o arranjo padrão
também com a página ainda sem leitura:

    .venv\\Scripts\\python.exe ferramentas\\capturas.py --livro xv --indice 25 --saida capturas

A CA-13.2 pede os 8 PNG (claro e escuro × 1366 e 1920 × com e sem leitura) na plataforma do
Windows, com a janela visível: `--visivel`, uma vez com `--tema claro` e outra com
`--tema escuro`. Sem ele, offscreen (o estilo é o mesmo Fusion, que o tema põe).

`--livro` acha o PDF pelo gabarito (`tests/verdade/<livro>/i<índice>.json`); `--pdf` aponta
um PDF direto. O projeto é criado numa pasta temporária, que sai no fim, e as escolhas
lembradas (`QSettings`) vão a um INI nela: nada é gravado no projeto de ninguém, no registro
do programa nem na base global do PyBoxEditor (a leitura usa os modelos globais só para ler).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

if "--visivel" not in sys.argv:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# O offscreen não acha as fontes do sistema sozinho: sem isto, o texto sai em quadradinhos.
if os.name == "nt":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"),
                                                         "Fonts"))
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))

from comum import PASTA_DOS_PDFS  # noqa: E402

CENARIOS = [
    # (nome, largura, altura, arranjo ou None para o padrão, docas a abrir)
    ("1366-padrao", 1366, 768, None, ()),
    ("1366-paginas-e-avisos", 1366, 768, None, ("doca_paginas", "doca_resultados")),
    ("1920-padrao", 1920, 1080, None, ("doca_paginas",)),
    ("1920-so-imagem", 1920, 1080, "so_imagem", ()),
    ("1920-so-vista", 1920, 1080, "so_vista", ()),
    ("1280-empilhado", 1280, 720, None, ()),
]
#: Com a página ainda sem leitura (a CA-13.2): o arranjo padrão nas duas resoluções.
SEM_LEITURA = [("1366-padrao-sem-leitura", 1366, 768, None, ()),
               ("1920-padrao-sem-leitura", 1920, 1080, None, ())]


def _pdf(args) -> Path:
    if args.pdf:
        return Path(args.pdf)
    verdade = json.loads((RAIZ / "tests" / "verdade" / args.livro / f"i{args.indice:03d}.json")
                         .read_text(encoding="utf-8"))
    pdf = next(PASTA_DOS_PDFS.rglob(verdade["pdf"]), None)
    if pdf is None:
        raise SystemExit(f"PDF não encontrado em {PASTA_DOS_PDFS}: {verdade['pdf']}")
    return pdf


def _esperar(app, janela, limite=120.0) -> None:
    fim = time.monotonic() + limite
    while janela.executor.ocupado and time.monotonic() < fim:
        app.processEvents()
        time.sleep(0.02)
    app.processEvents()


def main() -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--livro", default="xv")
    analisador.add_argument("--indice", type=int, default=25)
    analisador.add_argument("--pdf")
    analisador.add_argument("--saida", default=str(RAIZ / "capturas"))
    analisador.add_argument("--tema", choices=("claro", "escuro"), default="claro",
                            help="o tema da interface (§13); a página e o Documento não invertem")
    analisador.add_argument("--visivel", action="store_true",
                            help="a janela de verdade, na plataforma do Windows (CA-13.2)")
    args = analisador.parse_args()

    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from abbychess import pagina as pg
    from abbychess.app.janela import JanelaPrincipal
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro

    app = QApplication.instance() or QApplication([])
    from abbychess.app import estilo

    estilo.aplicar(app, args.tema)
    from PySide6.QtGui import QFont
    app.setFont(QFont("Segoe UI", 9))           # a fonte do Windows, não a de reserva
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    pdf = _pdf(args)
    with tempfile.TemporaryDirectory(prefix="abby-capturas-", ignore_cleanup_errors=True) as pasta:
        # As escolhas lembradas num INI da pasta temporária, não no registro do programa (a
        # janela grava a geometria ao fechar).
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, pasta)
        projeto = ProjetoDeLivro.criar(Path(pasta) / "livros", "Capturas", pdf)
        leitor = LeitorDoLivro.com_modelos_globais(projeto.pasta_de_padroes,
                                                   limiares=projeto.dados.limiares)
        janela = JanelaPrincipal()
        janela.resize(1366, 768)
        janela.show()
        janela.usar(projeto, pg.fonte_do_projeto(projeto), leitor)   # endireitada, como abre
        janela.ir_para_pagina(args.indice)
        _esperar(app, janela)
        for nome, largura, altura, arranjo, docas in SEM_LEITURA:
            _capturar(app, janela, saida / f"{nome}-{args.tema}.png", largura, altura,
                      arranjo, docas)
        janela.pagina.leitura.reconhecer()
        _esperar(app, janela)
        for nome, largura, altura, arranjo, docas in CENARIOS:
            _capturar(app, janela, saida / f"{nome}-{args.tema}.png", largura, altura,
                      arranjo, docas)
        janela.pagina.projeto.descarregar(10)
        janela.close()
    return 0


def _capturar(app, janela, caminho: Path, largura: int, altura: int, arranjo, docas) -> None:
    janela.resize(largura, altura)
    app.processEvents()
    janela.doca_paginas.hide()
    janela.doca_resultados.hide()
    janela.arranjo_padrao()
    app.processEvents()
    # As docas abrem pelo caminho do usuário (F9, o ⚠), não pelo arranjo padrão.
    if "doca_paginas" in docas:
        janela.alternar_paginas()
        app.processEvents()
    if "doca_resultados" in docas:
        janela.abrir_avisos()
        app.processEvents()
    if arranjo is not None:
        janela.arranjar(arranjo)
    janela.visor.zoom_largura()
    janela.atualizar_paginas()
    janela.pintar_texto()
    app.processEvents()
    janela.grab().save(str(caminho))
    print(caminho)


if __name__ == "__main__":
    raise SystemExit(main())
