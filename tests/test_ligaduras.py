"""Uma amostra de ligadura continua sendo um glifo e sai como letras no texto."""

import numpy as np

from core.box_model import BoxEntry

from abbychess import texto as tx
from abbychess.leitor import LeitorDoLivro


def test_ligadura_ensinada_le_um_box_e_dois_caracteres(tmp_path):
    recorte = np.full((40, 30), 255, dtype=np.uint8)
    recorte[5:35, 6:25] = 0
    leitor = LeitorDoLivro(tmp_path / "padroes")
    leitor.ensinar(recorte, "ﬁ", altura_de_referencia=40)

    lida = leitor.ler(recorte, altura_de_referencia=40)
    assert lida.char == "ﬁ"
    pagina = tx.pagina_avulsa([BoxEntry(lida.char, 10, 10, 40, 50, 1.0, lida.fonte)])
    documento = tx.montar(pagina)
    assert len(documento.gids()) == 1
    assert tx.texto(documento, modo=tx.IMPRESSO) == "fi"
    assert tx.texto(documento, modo=tx.SAN) == "fi"
