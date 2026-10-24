"""A leitura improvável pela palavra (`abbychess.contexto`): a regra e onde ela vale."""

from __future__ import annotations

from dataclasses import replace
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
    "NxN", "QxQ+", "DxD", "TxT", "♘gf3", "1.♘gf3", "♕xf7+", "exd6e.p.", "a8=D", "0-0-0",
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


class _Leitor:
    """O k-NN do livro de mentira: lê todo glifo pendente como `char`."""

    limiares = Limiares()

    def __init__(self, char):
        self.char, self.lidos = char, 0

    def ler_pelo_livro(self, recorte, referencia, efeito):
        self.lidos += 1
        return SimpleNamespace(char=self.char, fonte=FONTE_LIVRO, confianca=0.5, amostra=None)


def test_a_propagacao_rele_o_improvavel():
    from PIL import Image

    boxes = _linha("p0r")
    leitor = _Leitor("o")
    assert pg.propagar_padroes(Image.new("L", (200, 200), 255), boxes, leitor) == 1
    assert leitor.lidos == 1 and "".join(b.char for b in boxes) == "por"


def test_o_improvavel_lido_igual_nao_conta_como_resolvido():
    from PIL import Image

    boxes = _linha("p0r")
    leitor = _Leitor("0")                       # o padrão do livro também diz 0
    assert pg.propagar_padroes(Image.new("L", (200, 200), 255), boxes, leitor) == 0
    assert leitor.lidos == 1
    assert contexto.pendentes(boxes, Limiares()) == [False, True, False]   # e segue na fila


def test_a_quebra_de_palavra_do_usuario_vale_e_a_mudanca_renova_o_julgamento():
    from abbychess import texto as tx

    pagina = tx.pagina_avulsa(_linha("c0l0ca"))
    zero = pagina.boxes[1].gid
    assert zero in contexto.improvaveis(pagina)
    pagina.boxes[1].entry.char = "o"                               # corrigido no lugar
    assert zero not in contexto.improvaveis(pagina)
    pagina.boxes[1].entry.char = "0"
    l_ = pagina.boxes[2].gid
    pagina.decisoes = type(pagina.decisoes)(quebras=frozenset({l_}))   # "c0" | "l0ca"
    assert zero not in contexto.improvaveis(pagina)                 # "c0": 1 letra antes
    assert pagina.boxes[3].gid in contexto.improvaveis(pagina)      # "l0ca" segue


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


# ----------------------------------------------------------------------
# O lote (Ctrl+Enter no Glifo)
# ----------------------------------------------------------------------

def test_o_lote_e_a_mesma_leitura_que_a_palavra_desmente():
    boxes = _linha("c0l0ca n0 10 1.e4 b0l0s", fontes={15: FONTE_MANUAL})
    # O outro 0 de "c0l0ca" e o último de "b0l0s"; não o de "n0" (uma letra só), nem o de
    # "10" e o de "1.e4" (número e lance), nem o 0 manual (o primeiro de "b0l0s").
    assert contexto.lote_da_lista(boxes, {"0"}, "o", fora={1}) == [3, 17]
    assert contexto.lote_da_lista(boxes, {"0", "1"}, "o", fora={1}) == [3, 17]


def test_o_lote_so_troca_onde_a_troca_deixa_a_palavra_provavel():
    boxes = _linha("c0l0ca C0L0CA")
    assert contexto.lote_da_lista(boxes, {"0"}, "o") == [1, 3]          # não o de "CoLoCA"
    assert contexto.lote_da_lista(boxes, {"0"}, "O") == [7, 9]          # não o de "cOlOca"


def test_o_lote_deixa_de_fora_o_revisado_e_vale_pelos_gids():
    from abbychess import texto as tx

    pagina = tx.pagina_avulsa(_linha("c0l0ca b0l0s"))
    gids = [b.gid for b in pagina.boxes]
    assert contexto.lote(pagina, {"0"}, "o", {gids[1]}) == [gids[3], gids[7], gids[9]]
    boxes = list(pagina.boxes)
    boxes[7] = replace(boxes[7], revisado=True)
    pagina.boxes = boxes
    assert contexto.lote(pagina, {"0"}, "o", {gids[1]}) == [gids[3], gids[9]]
    assert contexto.lote(pagina, {"1"}, "l") == []
