"""Uma amostra de ligadura continua sendo um glifo e sai como letras no texto."""

import numpy as np

from core.box_model import BoxEntry

from abbychess import texto as tx
from abbychess.leitor import LeitorDoLivro
from abbychess.modelo import Estilo


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


def test_efeitos_diferentes_nunca_sao_vizinhos_quando_conhecidos(tmp_path):
    recorte = np.full((40, 30), 255, dtype=np.uint8)
    recorte[5:35, 6:25] = 0
    leitor = LeitorDoLivro(tmp_path / "padroes")
    caminho = leitor.ensinar(recorte, "n", altura_de_referencia=40,
                             efeito=Estilo(negrito=True))
    leitor.ensinar(recorte, "r", altura_de_referencia=40, efeito=Estilo(False, False))

    assert leitor.ler(recorte, altura_de_referencia=40,
                      efeito=Estilo(negrito=True)).char == "n"
    assert leitor.ler(recorte, altura_de_referencia=40, efeito=Estilo(False, False)).char == "r"
    # Sem medida (o efeito desconhecido), as duas amostras valem: nenhuma é excluída.
    assert leitor.ler(recorte, altura_de_referencia=40, efeito=Estilo()).char in ("n", "r")
    assert leitor.ler(recorte, altura_de_referencia=40, efeito=None).char in ("n", "r")
    assert leitor.padroes.efeito_de(caminho) == (True, None)   # o itálico não foi medido

    reaberto = LeitorDoLivro(tmp_path / "padroes")
    assert reaberto.ler(recorte, altura_de_referencia=40,
                        efeito=Estilo(negrito=True)).char == "n"


def test_a_ligadura_sai_como_as_letras_dela_na_exportacao():
    """O mesmo texto do Documento: a ligadura de um box sai "fi" no TXT, no DOCX e no EPUB
    (que leem `mo.palavras`), e a busca por "fim" acha."""
    from abbychess import montagem as mo

    boxes = [BoxEntry("ﬁ", 0, 0, 20, 30), BoxEntry("m", 22, 0, 40, 30)]
    linhas = mo.palavras(boxes)
    assert [texto for linha in linhas for texto, _indices in linha] == ["fim"]
