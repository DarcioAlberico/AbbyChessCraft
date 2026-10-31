"""A fixture `janela` que outros testes também usam (SPEC-qualidade Q-T5):
a janela de test_espaco (aberta como o programa a abre, pelo espaço de trabalho).

Cada `janela` mora num apoio seu: o nome se repete entre elas, e quem a usa a importa."""

from __future__ import annotations

import pytest
from abbychess.projeto import ProjetoDeLivro
from tests.ajudantes import _abrir
from tests.ajudantes import _pagina_sintetica


@pytest.fixture
def janela(app, tmp_path, sim):
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Teste",
                                   _pagina_sintetica(tmp_path / "pagina.png"))
    j = _abrir(projeto)
    yield j
    j.close()
