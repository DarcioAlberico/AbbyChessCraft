"""As linhas de palavras guardadas por `texto.montar` (`_linhas_da_pagina`): corrigir um
caractere não refaz a ordem de leitura nem as linhas, e o documento sai igual ao montado do zero.

As páginas são as da fatia do Xadrez Vitorioso (p. 21–27, como lidas no passo 0)."""

from __future__ import annotations

import copy
import random
import zipfile
from pathlib import Path

import pytest

from abbychess import texto as tx
from abbychess.layout import OrdemDeLeitura

FATIA = Path(__file__).resolve().parent / "dados" / "fatia" / "xv-i020-026-inicial.zip"

#: As trocas: letra por letra (a mais comum), e as que mudam as palavras do core (algarismo,
#: ponto, o vazio) ou as linhas (o box que some do texto).
TROCAS = ["e", "a", "c", "♘", "fi", "1", "0", ".", "", ",", "-", "²"]


@pytest.fixture(scope="module")
def paginas(tmp_path_factory):
    from abbychess.projeto import ProjetoDeLivro

    pasta = tmp_path_factory.mktemp("fatia")
    with zipfile.ZipFile(FATIA) as z:
        z.extractall(pasta)
    projeto = ProjetoDeLivro.abrir(next(p.parent for p in pasta.rglob("projeto.json")))
    try:
        yield [projeto.carregar_modelo(i) for i in projeto.paginas_lidas()]
    finally:
        projeto.fechar()


def _do_zero(pagina) -> tx.Documento:
    with tx._TRAVA_DAS_LINHAS:
        tx._LINHAS_VISTAS.clear()
    return tx.montar(pagina)


def _corrigida(pagina, k: int, char: str):
    nova = copy.deepcopy(pagina)
    nova.boxes[k].entry.char = char
    return nova


def test_o_documento_com_as_linhas_guardadas_e_o_montado_do_zero(paginas):
    sorteio = random.Random(1234)
    for pagina in paginas:
        tx.montar(pagina)                               # guarda as linhas desta página
        for _ in range(12):
            k = sorteio.randrange(len(pagina.boxes))
            corrigida = _corrigida(pagina, k, sorteio.choice(TROCAS))
            guardado = tx.montar(corrigida)
            assert guardado == _do_zero(corrigida), (pagina.indice, k)
            tx.montar(pagina)
        for com_os_nao_lidos in (False, True):
            assert (tx.montar(pagina, com_os_nao_lidos=com_os_nao_lidos)
                    == tx.montar(copy.deepcopy(pagina), com_os_nao_lidos=com_os_nao_lidos))


@pytest.mark.parametrize("k, char", [(950, "x"), (951, "x"), (954, "1"), (969, "1"), (969, "."),
                                     (1036, "x")])
def test_os_numeros_que_o_core_remonta_mudam_a_chave(paginas, k, char):
    """Na p. 21, trocas que mudam as palavras do core (o "1." de um lance, a letra que vira
    algarismo): com a chave cega ao caractere, o documento saía com as palavras de antes."""
    pagina = paginas[0]
    assert pagina.indice == 20
    tx.montar(pagina)
    corrigida = _corrigida(pagina, k, char)
    assert tx.montar(corrigida) == _do_zero(corrigida)


def test_trocar_uma_letra_por_outra_nao_refaz_a_ordem_de_leitura(paginas, monkeypatch):
    pagina = paginas[1]
    tx.montar(pagina)
    chamadas = []
    original = OrdemDeLeitura.da_pagina
    monkeypatch.setattr(OrdemDeLeitura, "da_pagina",
                        classmethod(lambda cls, e: chamadas.append(1) or original(e)))
    letra = next(k for k, b in enumerate(pagina.boxes) if b.entry.char.isalpha())
    tx.montar(_corrigida(pagina, letra, "x"))
    assert chamadas == []
    numero = next(k for k, b in enumerate(pagina.boxes) if b.entry.char.isdigit())
    tx.montar(_corrigida(pagina, numero, "x"))          # o algarismo: as palavras mudam
    assert chamadas == [1]


def test_o_box_movido_refaz_as_linhas(paginas):
    pagina = copy.deepcopy(paginas[0])
    tx.montar(pagina)
    caixa = pagina.boxes[0].entry
    caixa.y1, caixa.y2 = caixa.y1 + 2000, caixa.y2 + 2000      # para o pé da página
    assert tx.montar(pagina) == _do_zero(pagina)
