"""Capturas do editor de páginas para a revisão de design (roadmap, passo L, §12.4).

Abre a janela offscreen num projeto temporário do livro e grava PNGs do menu Página, de cada
diálogo das operações de página e da janela depois de girar, cortar, dividir e endireitar a
página reconhecida (cada uma desfeita antes da seguinte):

    .venv\\Scripts\\python.exe ferramentas\\capturas_paginas.py --livro xv --indice 25 --saida capturas-l

Como `capturas.py`: o projeto é criado numa pasta temporária, que sai no fim, e a leitura
usa os modelos globais só para ler.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"),
                                                         "Fonts"))
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))

from capturas import _esperar, _pdf  # noqa: E402


def main() -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--livro", default="xv")
    analisador.add_argument("--indice", type=int, default=25)
    analisador.add_argument("--pdf")
    analisador.add_argument("--saida", default=str(RAIZ / "capturas-l"))
    analisador.add_argument("--tema", choices=("claro", "escuro"), default="claro")
    args = analisador.parse_args()

    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication, QDialog, QMenu

    from abbychess import pagina as pg
    from abbychess.app import dialogo_paginas as dp
    from abbychess.app import estilo
    from abbychess.app.janela import JanelaPrincipal
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro

    app = QApplication.instance() or QApplication([])
    estilo.aplicar(app, args.tema)
    app.setFont(QFont("Segoe UI", 9))
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)

    def gravar(widget, nome: str) -> None:
        app.processEvents()
        caminho = saida / f"{nome}-{args.tema}.png"
        widget.grab().save(str(caminho))
        print(caminho)

    def capturar(dialogo: QDialog, nome: str) -> None:
        dialogo.show()
        dialogo.adjustSize()
        gravar(dialogo, nome)
        dialogo.reject()
        dialogo.deleteLater()

    # Os diálogos são mostrados e capturados, e não executados (a resposta é "cancelar").
    nomes = iter(["dialogo-mover", "dialogo-apagar", "dialogo-girar", "dialogo-cortar",
                  "dialogo-tirar-o-corte", "dialogo-dividir", "dialogo-endireitar"])

    def perguntar_paginas(janela, titulo, total, **opcoes):
        capturar(dp.DialogoDasPaginas(janela, titulo, total, **opcoes), next(nomes))
        return None

    def perguntar_com(janela, titulo, total, linhas, _ler, **opcoes):
        capturar(dp.DialogoDasPaginas(janela, titulo, total, linhas=linhas, **opcoes),
                 next(nomes))
        return None

    dp.perguntar_paginas, dp.perguntar_com = perguntar_paginas, perguntar_com
    pdf = _pdf(args)
    with tempfile.TemporaryDirectory(prefix="abby-capturas-l-") as pasta:
        projeto = ProjetoDeLivro.criar(Path(pasta) / "livros", "Capturas", pdf)
        leitor = LeitorDoLivro.com_modelos_globais(projeto.pasta_de_padroes,
                                                   limiares=projeto.dados.limiares)
        janela = JanelaPrincipal()
        janela.resize(1366, 768)
        janela.show()
        janela.usar(projeto, pg.fonte_do_projeto(projeto), leitor)
        janela.ir_para_pagina(args.indice)
        janela.pagina.reconhecer()
        _esperar(app, janela)
        janela.visor.zoom_largura()
        gravar(janela, "0-pagina-lida")

        menu = next(m for m in janela.menuBar().findChildren(QMenu) if m.title() == "P&ágina")
        menu.adjustSize()
        menu.show()
        gravar(menu, "menu-pagina")
        menu.hide()
        for acao in (janela.acao_mover_paginas, janela.acao_apagar_paginas,
                     janela.acao_girar_paginas, janela.acao_cortar_paginas,
                     janela.acao_tirar_o_corte, janela.acao_dividir_paginas,
                     janela.acao_endireitar_paginas):
            acao.trigger()
        capturar(dp.DialogoDasApagadas(janela, projeto.sequencia.apagar(
            [args.indice + 1]).apagadas), "dialogo-paginas-apagadas")

        p, i = janela.pagina, args.indice
        for nome, fazer in (("1-girada-90", lambda: p.girar_paginas([i], 90)),
                            ("2-cortada", lambda: p.cortar_paginas([i], (0.08, 0.06, 0.08, 0.1))),
                            ("3-dividida-esquerda", lambda: p.dividir_paginas([i], 0.5)),
                            ("5-endireitada-3-graus", lambda: p.endireitar_paginas([i], 3.0))):
            fazer()
            _esperar(app, janela)
            janela.ir_para_pagina(i)
            janela.visor.zoom_largura()
            gravar(janela, nome)
            if nome.startswith("3-"):
                janela.ir_para_pagina(i + 1)
                janela.visor.zoom_largura()
                gravar(janela, "4-dividida-direita")
            p.desfazer()
            _esperar(app, janela)
        janela.pagina.projeto.descarregar(10)
        janela.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
