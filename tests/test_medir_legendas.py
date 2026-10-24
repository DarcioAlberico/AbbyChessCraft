"""O alinhamento do CA-9.1 (`ferramentas/medir_legendas.py`), sem PDF."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import medir_legendas as ml  # noqa: E402


def _boxes(texto):
    return [SimpleNamespace(char=c) for c in texto]


def test_linha_certa_tem_todos_os_boxes_certos_e_nenhuma_troca():
    boxes = _boxes("Diagrama3.")
    erros, glifos, acertos, trocas = ml.alinhar(boxes, list(range(10)), "Diagrama 3.")
    assert (erros, glifos, trocas) == (0, 10, [])
    assert sorted(acertos) == list(range(10))


def test_troca_aponta_o_box_e_o_char_certo():
    boxes = _boxes("Dia9rama")
    erros, glifos, acertos, trocas = ml.alinhar(boxes, list(range(8)), "Diagrama")
    assert (erros, glifos) == (1, 8)
    assert trocas == [(3, "g")]
    assert 3 not in acertos and len(acertos) == 7


def test_box_sem_leitura_e_sobra_contam_como_erro_e_nao_como_troca():
    boxes = _boxes("Lo" + "\x00" + "ndres.")
    boxes[2].char = ""                             # sem leitura: o □ do replay
    erros, glifos, acertos, trocas = ml.alinhar(boxes, [0, 1, 3, 4, 5, 6, 7, 8], "Londres")
    assert glifos == 7 and erros == 1              # o "." sobra
    assert trocas == []
    erros, _, _, trocas = ml.alinhar(boxes, list(range(9)), "Londres.")
    assert erros == 1 and trocas == []             # o box vazio sobra
