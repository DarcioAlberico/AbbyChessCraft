"""Cada regra da exportação e da notação numa definição só (SPEC-qualidade Q-E5, CA-Q-E5): as
letras das peças por idioma, o idioma do livro pela camada do PDF e os trechos marcados que o
EPUB, o DOCX e a prévia escrevem. Uma segunda cópia passa num teste e diverge no outro."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ABBYCHESS = Path(__file__).resolve().parent.parent / "abbychess"


def _modulos():
    for arquivo in sorted(ABBYCHESS.rglob("*.py")):
        yield arquivo.relative_to(ABBYCHESS.parent).as_posix(), arquivo.read_text(encoding="utf-8")


def _atribuicoes(nome: str):
    for caminho, fonte in _modulos():
        for no in ast.walk(ast.parse(fonte)):
            if isinstance(no, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == nome for t in no.targets):
                yield caminho


def _textos():
    for caminho, fonte in _modulos():
        for no in ast.walk(ast.parse(fonte)):
            if isinstance(no, ast.Constant) and isinstance(no.value, str):
                yield caminho, no.value


def test_as_letras_das_pecas_por_idioma_sao_definidas_uma_vez():
    assert list(_atribuicoes("PECAS")) == ["abbychess/modelo.py"]


def test_nenhuma_regex_escreve_a_mao_as_letras_das_pecas_de_varios_idiomas():
    """A classe de letras de lance de mais de um idioma vem de `modelo.PECAS`. O `[KQRBN]` só
    do inglês (o SAN do PGN, `lances._LANCE`) é outra regra e fica."""
    misturadas = re.compile(r"\[[KQRBN]{5}[A-Z]")
    achadas = [(c, t) for c, t in _textos() if misturadas.search(t)]
    assert achadas == []


def test_o_idioma_do_livro_pela_camada_do_pdf_e_perguntado_num_lugar():
    chamadas = [c for c, fonte in _modulos() if "pdf_nativo.idioma_do_pdf(" in fonte]
    assert chamadas == ["abbychess/pedido.py"]


def test_os_trechos_marcados_sao_calculados_num_lugar():
    """O EPUB, o DOCX (e a prévia, pelo EPUB) pedem os pedaços a `marcacao.trechos_marcados`."""
    calculam = [c for c, fonte in _modulos() if "for c in texto]" in fonte and "marcas" in fonte]
    assert calculam == ["abbychess/marcacao.py"]
