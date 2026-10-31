"""As regras da própria suíte (SPEC §15.1, SPEC-qualidade Q-T1): o que a suíte rápida não
carrega, e o que as camadas lentas continuam tendo."""

from __future__ import annotations

import pytest

from abbychess.leitor import LeitorDoLivro


def test_a_suite_rapida_nao_carrega_os_modelos_globais(tmp_path):
    """CA-Q-T1: a rede e a base global do PyBoxEditor levam segundos e gigabytes por worker;
    na suíte rápida, quem as pede (a janela que abre um projeto) recebe o leitor só com os
    padrões do livro, e o teste da janela não estoura o prazo com -n 4."""
    leitor = LeitorDoLivro.com_modelos_globais(tmp_path / "padroes")
    assert leitor.rede is None and leitor.base is None and leitor.ocr is None


@pytest.mark.livro_real
def test_a_camada_do_livro_real_carrega_os_modelos_globais(tmp_path):
    leitor = LeitorDoLivro.com_modelos_globais(tmp_path / "padroes")
    assert leitor.base is not None and leitor.ocr is not None
