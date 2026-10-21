"""CA-3.5 [desempenho]: o item dos boxes com 2.000 boxes.

`paint()` do item numa `QImage` 1920×1080, em 10 zooms de 5% a 800%: p95 ≤ 33 ms; clicar
acha o box: p95 ≤ 2 ms em 1.000 cliques de semente fixa. Página sintética (não precisa do
livro), no tamanho de uma página a 300 dpi.
"""

from __future__ import annotations

import os
import random
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.desempenho.conftest import p95  # noqa: E402

pytestmark = [pytest.mark.desempenho]

LARGURA, ALTURA = 2480, 3508
ZOOMS = [0.05, 0.08, 0.12, 0.2, 0.33, 0.5, 1.0, 2.0, 4.0, 8.0]


def _boxes(n=2000):
    from core.box_model import BoxEntry

    sorteio = random.Random(7)
    boxes = []
    for k in range(n):
        linha, coluna = divmod(k, 50)
        x, y = 100 + coluna * 45, 100 + linha * 80
        boxes.append(BoxEntry("a", x, y, x + 30 + sorteio.randint(0, 8), y + 40,
                              sorteio.random(), sorteio.choice(["net", "livro", "manual"])))
    return boxes


def test_pintura_e_clique_do_item_dos_boxes(medidas):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter, QTransform
    from PySide6.QtWidgets import QApplication, QStyleOptionGraphicsItem

    from abbychess import grade as gd
    from abbychess.app.item_dos_boxes import ItemDosBoxes

    QApplication.instance() or QApplication([])
    boxes = _boxes()
    item = ItemDosBoxes(LARGURA, ALTURA)
    item.trocar(boxes, [gd.estado(b, i % 7 == 0) for i, b in enumerate(boxes)])
    imagem = QImage(1920, 1080, QImage.Format.Format_ARGB32)
    tempos = []
    for zoom in ZOOMS:
        # A parte da página que cabe na imagem, a esse zoom, a partir do meio dela.
        largura, altura = 1920 / zoom, 1080 / zoom
        exposto = QRectF(max(0, LARGURA / 2 - largura / 2), max(0, ALTURA / 2 - altura / 2),
                         min(LARGURA, largura), min(ALTURA, altura))
        opcao = QStyleOptionGraphicsItem()
        opcao.exposedRect = exposto
        for _ in range(6):
            pintor = QPainter(imagem)
            pintor.setTransform(QTransform.fromScale(zoom, zoom).translate(-exposto.left(),
                                                                           -exposto.top()))
            inicio = time.perf_counter_ns()
            item.paint(pintor, opcao)
            tempos.append((time.perf_counter_ns() - inicio) / 1e6)
            pintor.end()
    sorteio = random.Random(2026)
    cliques = []
    for _ in range(1000):
        # Metade dos cliques no meio de um box, metade num ponto qualquer da página.
        if sorteio.random() < 0.5:
            b = sorteio.choice(boxes)
            x, y = (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2
        else:
            x, y = sorteio.uniform(0, LARGURA), sorteio.uniform(0, ALTURA)
        inicio = time.perf_counter_ns()
        item.no_ponto(x, y)
        cliques.append((time.perf_counter_ns() - inicio) / 1e6)
    medidas["pintura_dos_boxes"] = {"p95_ms": round(p95(tempos), 2),
                                    "max_ms": round(max(tempos), 2), "n": len(tempos),
                                    "alvo_ms": 33, "boxes": len(boxes),
                                    "como": "paint() do item numa QImage 1920×1080, 10 zooms "
                                            "de 5% a 800% × 6"}
    medidas["clique_no_box"] = {"p95_ms": round(p95(cliques), 4), "n": len(cliques),
                                "alvo_ms": 2, "como": "ItemDosBoxes.no_ponto (o que o visor "
                                                      "chama no clique), 1.000 pontos de "
                                                      "semente fixa, metade no meio de um box"}
    assert p95(tempos) <= 33 and p95(cliques) <= 2      # os alvos do CA-3.5
