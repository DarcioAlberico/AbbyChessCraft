"""A fixture `janela` que outros testes também usam (SPEC-qualidade Q-T5):
a janela de test_janela (uma página sintética, o leitor só do livro).

Cada `janela` mora num apoio seu: o nome se repete entre elas, e quem a usa a importa."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox
from abbychess import pagina as pg
from abbychess.app.janela import JanelaPrincipal
from abbychess.leitor import LeitorDoLivro
from abbychess.projeto import ProjetoDeLivro
from tests.ajudantes import _pagina_sintetica


@pytest.fixture
def janela(app, tmp_path, monkeypatch):
    # Toda pergunta é respondida com "sim", para o teste não esperar clique.
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    fonte = _pagina_sintetica(tmp_path / "pagina.png")
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Teste", fonte)
    j = JanelaPrincipal()
    j.usar(projeto, pg.FonteDePaginas(projeto.fonte),
          LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    yield j
    j.close()
