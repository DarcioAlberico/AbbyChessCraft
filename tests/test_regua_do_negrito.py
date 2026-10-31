"""O negrito na página escaneada e na página de partida (§9.2): a espessura do traço em tons
de cinza (`pagina.espessura_do_traco`) e a régua do livro (`abbychess.regua_do_negrito`),
gravada com cada página e mandada com o pedido de leitura."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image
from core.box_model import BoxEntry

from abbychess import livro
from abbychess import efeitos as ef
from abbychess import regua_do_negrito as rn



def _haste(largura: float, fase: float = 0.0) -> np.ndarray:
    """Uma haste de `largura` pixels em pé, desenhada a 8× e reduzida (a borda suave de um
    render de verdade), começando `fase` pixel depois da grade."""
    escala = 8
    grande = np.full((40 * escala, 30 * escala), 255, np.uint8)
    x0 = int(round((10 + fase) * escala))
    grande[5 * escala:35 * escala, x0:x0 + int(round(largura * escala))] = 0
    return np.asarray(Image.fromarray(grande).resize((30, 40), Image.Resampling.BOX))


# ----------------------------------------------------------------------
# A espessura do traço
# ----------------------------------------------------------------------

def test_a_espessura_segue_a_largura_do_traco_abaixo_do_pixel():
    """O traço do corpo de texto tem uns 2 px: meio pixel a mais é 25% de negrito. A medida
    em tons de cinza vê a diferença; a binária andava de pixel em pixel."""
    fino, grosso = ef.espessura_do_traco(_haste(2.0)), ef.espessura_do_traco(_haste(2.5))
    assert grosso / fino == pytest.approx(1.25, abs=0.06)


def test_a_espessura_nao_depende_da_fase_do_traco_na_grade():
    """O mesmo "t" redondo media 1,00 numa ocorrência e 1,18 na outra pela binária, conforme
    caía na grade: em tons de cinza, a fase não muda a medida."""
    medidas = [ef.espessura_do_traco(_haste(2.0, fase)) for fase in (0.0, 0.25, 0.5, 0.75)]
    assert max(medidas) / min(medidas) < 1.05


def test_o_recorte_sem_contraste_nao_tem_medida():
    assert ef.espessura_do_traco(np.full((20, 20), 200, np.uint8)) is None
    assert ef.espessura_do_traco(np.zeros((0, 0), np.uint8)) is None


# ----------------------------------------------------------------------
# A régua do livro
# ----------------------------------------------------------------------

def test_a_regua_da_pagina_tem_contagem_quantil_e_mediana_por_caractere():
    regua = rn.regua_da_pagina(["a", "a", "a", "a", "b", "", "b"],
                               [0.10, 0.12, 0.14, 0.16, 0.2, 0.5, None])
    assert regua == {"a": [4, pytest.approx(0.115), pytest.approx(0.13)], "b": [1, 0.2, 0.2]}


def test_juntar_pesa_cada_pagina_pela_contagem():
    livro_ = rn.juntar([{"a": [10, 0.10, 0.11]}, {"a": [1, 0.30, 0.31], "b": [5, 0.2, 0.2]},
                        {"a": [9, 0.10, 0.12]}, None, {"c": ["x", 1, 2]}])
    assert livro_ == {"a": [20, 0.10, pytest.approx(0.11)], "b": [5, 0.2, 0.2]}


def test_o_livro_curto_nao_tem_regua():
    pequeno = {"a": [rn.MINIMO_DO_LIVRO - 1, 0.1, 0.1]}
    assert rn.referencia_e_normal({}, pequeno) is None
    assert rn.referencia_e_normal({}, None) is None
    assert rn.referencia_e_normal({}, {"a": [rn.MINIMO_DO_LIVRO, 0.1, 0.11]}) is not None


def _pagina_de_partida():
    """Uma página em que todo lance é negrito ("12.d5"): os algarismos e as letras das casas
    só aparecem nele, e a página sozinha não tem o redondo deles."""
    boxes, palavras, medidas = [], [], []
    for k in range(30):
        palavra = []
        for j, char in enumerate("12.d5"):
            palavra.append(len(boxes))
            boxes.append(BoxEntry(char, 60 * k + 10 * j, 0, 60 * k + 10 * j + 8, 20))
            medidas.append(0.15)                # o negrito: 1,5 vez o redondo do livro
        palavras.append(palavra)
    return boxes, palavras, medidas


def test_a_pagina_de_partida_so_tem_negrito_com_a_regua_do_livro():
    boxes, palavras, medidas = _pagina_de_partida()
    da_pagina = rn.regua_da_pagina([b.char for b in boxes], medidas)
    assert set(ef.decidir_negritos(boxes, palavras, medidas, da_pagina)) == {False}
    # O livro mediu o redondo desses caracteres na prosa e nas variantes.
    do_livro = {char: [1000, 0.10, 0.104] for char in "12.d5aeost"}
    assert set(ef.decidir_negritos(boxes, palavras, medidas, da_pagina, do_livro)) == {True}


def test_com_a_regua_do_livro_a_prosa_redonda_continua_redonda():
    boxes = [BoxEntry(c, 10 * i, 0, 10 * i + 8, 20) for i, c in enumerate("the rest")]
    palavras = [[0, 1, 2], [4, 5, 6, 7]]
    medidas = [0.101, 0.099, 0.10, None, 0.102, 0.10, 0.098, 0.10]
    do_livro = {char: [1000, 0.10, 0.104] for char in "thers"}
    da_pagina = rn.regua_da_pagina([b.char for b in boxes], medidas)
    assert ef.decidir_negritos(boxes, palavras, medidas, da_pagina, do_livro) == [
        False, False, False, None, False, False, False, False]


# ----------------------------------------------------------------------
# A régua no projeto e no lote
# ----------------------------------------------------------------------

def test_a_regua_da_pagina_vai_ao_arquivo_e_ao_resumo_do_livro(projeto):  # noqa: F811
    from abbychess.projeto import ProjetoDeLivro

    pagina = projeto.pagina_para_editar(1)
    pagina.regua_do_negrito = {"a": [3, 0.1, 0.11]}
    projeto.salvar_modelo(pagina)
    projeto.paginas_em_memoria.descarregar(30)
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    assert reaberto.carregar_modelo(1).regua_do_negrito == {"a": [3, 0.1, 0.11]}
    assert reaberto.resumo.do_livro()[1]["regua_do_negrito"] == {"a": [3, 0.1, 0.11]}
    assert reaberto.resumo.regua_do_negrito() == {"a": [3, 0.1, 0.11]}
    assert reaberto.resumo.regua_do_negrito(sem_o_pid=reaberto.ordem.pid_em(1)) == {}


def test_o_lote_grava_a_regua_de_cada_pagina_e_manda_a_do_livro(projeto, fonte, leitor,  # noqa: F811
                                                                monkeypatch):
    pedidas = []
    original = ef.medir_efeitos

    def medir(imagem, boxes, regua_do_livro=None):
        pedidas.append(regua_do_livro)
        efeitos = original(imagem, boxes, regua_do_livro)
        return ef.Efeitos(efeitos.negritos, efeitos.italicos, {"a": [2000, 0.1, 0.11]})

    monkeypatch.setattr(ef, "medir_efeitos", medir)
    livro.reconhecer_paginas(projeto, fonte, leitor, range(3))
    assert pedidas[0] == {}
    assert pedidas[1] == {"a": [2000, 0.1, 0.11]}
    assert pedidas[2] == {"a": [4000, 0.1, 0.11]}
    assert projeto.carregar_modelo(2).regua_do_negrito == {"a": [2000, 0.1, 0.11]}
    assert projeto.resumo.regua_do_negrito()["a"][0] == 6000
    # A página apagada sai da régua do livro com o resumo dela.
    projeto.ordem.gravar(projeto.sequencia.apagar([projeto.ordem.pid_em(0)]))
    assert projeto.resumo.regua_do_negrito()["a"][0] == 4000
