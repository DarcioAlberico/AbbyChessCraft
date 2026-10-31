"""A fixture `janela` que outros testes também usam (SPEC-qualidade Q-T5):
a janela de test_paginas_na_janela (o PDF de 60 páginas, 1366 × 768).

Cada `janela` mora num apoio seu: o nome se repete entre elas, e quem a usa a importa."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication
from abbychess.projeto import ProjetoDeLivro


@pytest.fixture
def janela(app, tmp_path, pdf_de_60_paginas, sim):  # noqa: F811
    """A janela como o programa a abre: a fonte pela sequência do projeto."""
    from abbychess import pagina as pg
    from abbychess.app.janela import JanelaPrincipal
    from abbychess.leitor import LeitorDoLivro

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Janela", pdf_de_60_paginas)
    j = JanelaPrincipal()
    j.resize(1366, 768)
    j.show()
    j.usar(projeto, pg.fonte_do_projeto(projeto),
           LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    QApplication.processEvents()
    yield j
    j.close()
