"""A leitura improvável pela palavra (`abbychess.contexto`): a regra e onde ela vale."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from core.box_model import BoxEntry

from abbychess import contexto
from abbychess import pagina as pg
from abbychess.leitor import FONTE_LIVRO, FONTE_MANUAL, FONTE_NATIVA
from abbychess.projeto import Limiares, pendentes_pelo_histograma, resumo_das_confiancas


def _marcados(palavra: str) -> str:
    return "".join(c if m else "." for c, m in zip(palavra, contexto.improvaveis_na_palavra(
        list(palavra))))


@pytest.mark.parametrize("palavra, marcados", [
    ("c0l0ca", ".0.0.."),               # algarismo entre letras
    ("dific11ltar", ".....11...."),     # a série inteira
    ("1ibera", "1....."),               # no começo, antes de duas letras
    ("muit0", "....0"),                 # no fim, depois de duas letras
    ("anteS", "....S"),                 # maiúscula depois de minúscula
    ("CavaIo", "....I."),
    ("VITORlOSO", ".....l..."),         # minúscula entre maiúsculas
])
def test_o_que_a_palavra_desmente(palavra, marcados):
    assert _marcados(palavra) == marcados


@pytest.mark.parametrize("palavra", [
    "Tae1+", "Cxh2", "12.h3+", "1.e4", "2...Cf6", "4.Bc4?", "0-0", "Bxd6++", "(1.Dc3",
    "e4-e5", "Bispo-c8)", "1º", "2ª", "1890", "Inicialmente", "Diagrama", "PEÇAS", "f7",
])
def test_lance_numero_e_palavra_comum_passam(palavra):
    assert _marcados(palavra) == "." * len(palavra)


def _linha(texto: str, *, fonte="neural", confianca=0.99, fontes=None):
    """Uma linha de boxes de 10×20 px, 1 px entre letras e 12 px entre palavras."""
    boxes, x = [], 40
    for c in texto:
        if c == " ":
            x += 12
            continue
        f = (fontes or {}).get(len(boxes), fonte)
        boxes.append(BoxEntry(c, x, 100, x + 10, 120, confianca, f))
        x += 11
    return boxes


def test_o_improvavel_confiante_vai_para_a_fila_e_o_manual_nao():
    boxes = _linha("a c0l0ca e e4", fontes={2: FONTE_MANUAL})
    pendentes = contexto.pendentes(boxes, Limiares())
    assert [b.char for b, p in zip(boxes, pendentes) if p] == ["0"]       # o 1º é manual
    assert pg.fila_de_revisao(boxes, SimpleNamespace(limiares=Limiares())) == [4]


def test_o_padrao_do_livro_volta_e_o_texto_nativo_nao():
    assert contexto.volta_pelo_contexto(FONTE_LIVRO)
    assert not contexto.volta_pelo_contexto(FONTE_NATIVA)
    assert not contexto.volta_pelo_contexto(FONTE_MANUAL)
    boxes = _linha("p0r", fonte=FONTE_LIVRO, confianca=0.4)
    assert contexto.pendentes(boxes, Limiares()) == [False, True, False]


def test_a_propagacao_rele_o_improvavel():
    boxes = _linha("p0r")
    lidos = []

    class Leitor:
        limiares = Limiares()

        def ler_pelo_livro(self, recorte, referencia, efeito):
            lidos.append(recorte.shape)
            return SimpleNamespace(char="o", fonte=FONTE_LIVRO, confianca=0.5, amostra=None)

    from PIL import Image

    resolvidos = pg.propagar_padroes(Image.new("L", (200, 200), 255), boxes, Leitor())
    assert resolvidos == 1 and len(lidos) == 1
    assert "".join(b.char for b in boxes) == "por"


def test_o_resumo_conta_o_improvavel_com_qualquer_limiar():
    boxes = _linha("c0l0ca anteS")
    resumo = resumo_das_confiancas(boxes, Limiares())
    assert resumo["improvaveis"] == 3 and resumo["pendentes"] == 3
    assert sum(resumo["histograma"].values()) == len(boxes) - 3
    for revisao in (0.10, 0.90, 1.00):
        assert pendentes_pelo_histograma(resumo, revisao) >= 3
    assert pendentes_pelo_histograma(resumo, 0.90) == 3
    revisados = [b.char == "S" for b in boxes]
    assert resumo_das_confiancas(boxes, Limiares(), revisados)["improvaveis"] == 2
