"""O servidor lê como a janela lia (SPEC §11): a mesma página, pelo filho e no processo.

Com o leitor real (a rede e a base global), a página 21 do Xadrez Vitorioso lida pelo servidor
dá os mesmos boxes (caractere, origem, confiança e caixa) que lida no próprio processo, e os
recortes que a janela manda (a releitura de um glifo, com a altura de referência da página)
dão as mesmas leituras que o glifo lido na página. É o que sustenta comparar a qualidade e a
fatia, medidas no processo (`medir.py`, `replay_fatia.py`), com o programa, que lê pelo filho.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tests.livros import PASTA_DOS_PDFS

pytestmark = [pytest.mark.livro_real, pytest.mark.processo, pytest.mark.timeout(900)]

_PDF = sorted(PASTA_DOS_PDFS.glob("Xadrez Vitorioso*/*.pdf"))


def _como(boxes):
    return [(b.char, b.source, round(float(b.confidence), 4), b.x1, b.y1, b.x2, b.y2)
            for b in boxes]


def test_a_pagina_e_os_recortes_lidos_pelo_filho_sao_os_lidos_no_processo():
    if not _PDF:
        pytest.skip("o PDF do Xadrez Vitorioso não está nesta máquina")
    from abbychess import pagina as pg
    from abbychess import servidor_de_leitura as sl
    from abbychess.projeto import ProjetoDeLivro

    projeto = ProjetoDeLivro.criar(Path(tempfile.mkdtemp()), "Equivalência", _PDF[0])
    servidor = sl.ServidorDeLeitura(projeto.pasta_de_padroes, projeto.dados.limiares,
                                    fabrica=sl.FABRICA_PADRAO)
    try:
        assert servidor.pronto.wait(300), "o servidor não carregou os modelos"
        imagem = pg.fonte_do_projeto(projeto).pagina(20)
        leitor = sl.leitor_global(projeto.pasta_de_padroes, projeto.dados.limiares)
        aqui = sl.ler_pagina(imagem, [], [], leitor)
        pelo_filho = servidor.chamar("ler_pagina", (imagem, [], []), timeout=600)
        assert len(aqui.boxes) > 500
        assert _como(pelo_filho.boxes) == _como(aqui.boxes)
        assert pelo_filho.tabuleiros == aqui.tabuleiros
        assert [d.fen for d in pelo_filho.diagramas] == [d.fen for d in aqui.diagramas]

        indices = list(range(0, len(aqui.boxes), max(1, len(aqui.boxes) // 40)))
        recortes = pg.recortes_para_ler(imagem, aqui.boxes, indices)
        leituras = servidor.chamar("ler_recortes", recortes, timeout=600)
        assert [(r.char, r.fonte, round(r.confianca, 4)) for r in leituras] == \
            [(aqui.boxes[i].char, aqui.boxes[i].source, round(float(aqui.boxes[i].confidence), 4))
             for i in indices]
    finally:
        servidor.fechar()
        projeto.fechar()
