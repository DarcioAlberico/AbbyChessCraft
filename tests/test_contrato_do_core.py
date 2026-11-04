"""Os contratos com os privados do PyBoxEditor que o programa ainda usa (SPEC-qualidade Q-E7,
CA-Q-E7): cada teste fixa o comportamento de que o AbbyChessCraft depende, para uma mudança no
core reprovar aqui, e não em silêncio na leitura. Cada um tem o pedido de uma API pública em
`docs/pedidos-ao-pyboxeditor.md`; a lista dos acessos é a `EXCECOES` de
`tests/test_privados_do_core.py`."""

from __future__ import annotations

import gzip

import numpy as np
import pytest
from core.box_model import BoxEntry
from core.services.box_service import BoxService

from tests.ajudantes import _lido

P23 = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/R1BQKBNR"


def test_contrato_do_historico_do_tabuleiro():
    """`TabuleiroEdicao._historico`, `_indice` e `_estado`: o histórico zerado com o estado de
    agora faz dele o ponto de partida do desfazer (`DiagramaLido.edicao`); `_registrar` guarda
    um passo a mais, que o desfazer volta (`diagramas.afirmar_lado`)."""
    from abbychess import diagramas as dg

    tabuleiro = _lido(P23).edicao()
    assert not tabuleiro.pode_desfazer and not tabuleiro.desfazer()
    origem, informado = tabuleiro.lado_origem, tabuleiro.lado_informado
    assert dg.afirmar_lado(tabuleiro, tabuleiro.lado)          # o mesmo lado: só a procedência
    assert (tabuleiro.lado_origem, tabuleiro.lado_informado) == (dg.LADO_DO_USUARIO, True)
    assert tabuleiro.desfazer()
    assert (tabuleiro.lado_origem, tabuleiro.lado_informado) == (origem, informado)
    assert not tabuleiro.pode_desfazer
    assert tabuleiro.colocar(4, 4, "Q") and tabuleiro.desfazer()   # o passo do core também
    assert tabuleiro.casa(4, 4).simbolo is None


def _pagina(largura=40, altura=20, colunas=((5, 15), (25, 35)), fundo=255, tinta=0):
    matriz = np.full((altura, largura), fundo, dtype=np.uint8)
    for x1, x2 in colunas:
        matriz[4:16, x1:x2] = tinta
    return matriz


def test_contrato_da_tinta_do_box():
    """`BoxService._tinta_do_box(box, cinza)`: a máscara booleana da tinta dentro do box, na
    forma do recorte; None no box de menos de 3 pixels; a tarja preta (`negativo`) positivada."""
    mascara = BoxService._tinta_do_box(BoxEntry("", 0, 0, 40, 20), _pagina())
    assert mascara.shape == (20, 40) and mascara.dtype == bool
    assert mascara[10, 7] and mascara[10, 30] and not mascara[10, 20] and not mascara[1, 7]
    assert BoxService._tinta_do_box(BoxEntry("", 0, 0, 2, 20), _pagina()) is None
    negativa = BoxService._tinta_do_box(BoxEntry("", 0, 0, 40, 20, negativo=True),
                                        _pagina(fundo=0, tinta=255))
    assert negativa[10, 7] and not negativa[10, 20]


def test_contrato_do_vale_mais_fundo():
    """`BoxService._vale_mais_fundo(perfil, margem)`: (posição, fundura) do vale entre dois
    picos, a fundura contra o menor deles e acima de `MIN_FUNDURA_DO_VALE` num vão de verdade;
    None sem vale interno (curto, sem tinta, monotônico)."""
    perfil = [0, 9, 9, 9, 9, 1, 0, 1, 8, 8, 8, 8, 0]
    posicao, fundura = BoxService._vale_mais_fundo(perfil, BoxService.MARGEM_DO_CORTE)
    assert posicao == 6 and fundura >= BoxService.MIN_FUNDURA_DO_VALE
    margem = BoxService.MARGEM_DO_CORTE
    assert BoxService._vale_mais_fundo([5, 0], margem) is None              # curto
    assert BoxService._vale_mais_fundo([0] * 12, margem) is None            # sem tinta
    assert BoxService._vale_mais_fundo(list(range(12)), margem) is None     # monotônico


def test_contrato_da_lista_de_palavras(tmp_path):
    """`lexico._ler(caminho)`: as palavras do arquivo, uma por linha, em minúsculas, sem as
    linhas vazias; o `.gz` também; o byte torto não derruba a carga."""
    from core import lexico

    texto = tmp_path / "nomes.txt"
    texto.write_bytes("Casa\n\n  PEÃO \n".encode("utf-8") + b"tor\xffre\n")
    assert lexico._ler(str(texto)) == {"casa", "peão", "tor�re"}
    comprimido = tmp_path / "nomes.txt.gz"
    with gzip.open(comprimido, "wt", encoding="utf-8") as f:
        f.write("Rei\nDama\n")
    assert lexico._ler(str(comprimido)) == {"rei", "dama"}


def test_contrato_do_servico_de_aprendizado(tmp_path):
    """`LearningService._get_learner()`: a base k-NN da pasta de treino, a mesma a cada
    chamada; `_predictor`, depois de `load_predictor()` dar True: a rede, com `predict` e
    `predict_topk` (o leitor e o palpite as chamam)."""
    from core.learner import CharacterLearner
    from core.services.learning_service import LearningService

    from abbychess import leitor

    servico = LearningService(data_dir=str(tmp_path))
    base = servico._get_learner()
    assert isinstance(base, CharacterLearner) and servico._get_learner() is base
    global_ = LearningService(data_dir=str(leitor.base_global()))
    if not global_.load_predictor():
        pytest.skip("a rede global do PyBoxEditor não está nesta máquina")
    rede = global_._predictor
    assert callable(rede.predict) and callable(rede.predict_topk)
