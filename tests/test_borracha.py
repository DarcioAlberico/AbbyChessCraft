"""A borracha (SPEC §12.4, CA-12.17): a mancha do scanner marcada na página sai da imagem (fica
branca) na leitura, na exportação e no PDF pesquisável. A área apagada é guardada na entrada da
sequência, na página da fonte antes de endireitar: ela segue o corte, o giro e o ângulo, e o
Ctrl+Z a devolve."""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.box_model import BoxEntry  # noqa: E402
from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from abbychess import geometria as geo  # noqa: E402
from abbychess import geometria_do_modelo as gm  # noqa: E402
from abbychess import pagina as pg  # noqa: E402
from abbychess import sequencia as sq  # noqa: E402
from abbychess.controlador import ControladorDePagina  # noqa: E402
from abbychess.leitor import LeitorDoLivro  # noqa: E402
from abbychess.modelo import GLIFOS_MARCADOS, NAO_RECONHECIDA, Box, Decisoes, Pagina  # noqa: E402
from abbychess.projeto import ProjetoDeLivro  # noqa: E402

from tests.fixturas_paginas_na_janela import janela  # noqa: E402,F401,F811

#: A mancha do scanner, em pontos do PDF: um quadrado preto bem abaixo do texto.
MANCHA_PT = (100, 200, 110, 210)
#: Quanto a área marcada passa da mancha, em pixels.
FOLGA = 4


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def pdf_manchado(tmp_path):
    import fitz

    caminho = tmp_path / "manchado.pdf"
    with fitz.open() as doc:
        for k in range(3):
            pagina = doc.new_page(width=200, height=300)
            pagina.insert_text((20, 40), f"Pagina {k + 1}", fontsize=14)
            pagina.draw_rect(fitz.Rect(*MANCHA_PT), color=(0, 0, 0), fill=(0, 0, 0))
        doc.save(str(caminho))
    return caminho


@pytest.fixture
def sem_endireitar(monkeypatch):
    monkeypatch.setattr(pg, "medir_inclinacao", lambda *_a, **_k: 0.0)


@pytest.fixture
def projeto(tmp_path, pdf_manchado, sem_endireitar):
    return ProjetoDeLivro.criar(tmp_path / "livros", "Borracha", pdf_manchado)


def _ligar(projeto):
    controlador = ControladorDePagina()
    controlador.mensagens = []
    controlador.eventos.ligar("mensagem", lambda texto, _ms: controlador.mensagens.append(texto))
    controlador.ligar(projeto, pg.fonte_do_projeto(projeto),
                      LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    controlador.ir_para(0)
    return controlador


@pytest.fixture
def ctl(projeto):
    return _ligar(projeto)


def _imagem(ctl, posicao=0):
    return np.asarray(ctl.fonte.pagina(posicao).convert("L"))


def _mancha(imagem, folga=FOLGA):
    """A caixa da tinta abaixo do texto (a mancha), com a folga."""
    altura = imagem.shape[0]
    ys, xs = np.nonzero(imagem[altura // 3:] < 128)
    assert len(xs), "a mancha não está na página"
    y0 = altura // 3
    return (int(xs.min()) - folga, int(ys.min()) + y0 - folga,
            int(xs.max()) + 1 + folga, int(ys.max()) + y0 + 1 + folga)


def _fora(imagem, caixa):
    x1, y1, x2, y2 = caixa
    mascara = np.ones(imagem.shape, dtype=bool)
    mascara[y1:y2, x1:x2] = False
    return mascara


def _branca(imagem, caixa, minimo=255):
    x1, y1, x2, y2 = caixa
    return bool((imagem[y1:y2, x1:x2] >= minimo).all())


# ----------------------------------------------------------------------
# CA-12.17: a borracha
# ----------------------------------------------------------------------

def test_ca_12_17_a_mancha_apagada_sai_da_imagem_e_o_resto_fica(projeto, ctl):
    antes = _imagem(ctl)
    caixa = _mancha(antes)
    assert ctl.operacoes.apagar_manchas(0, [caixa])
    depois = _imagem(ctl)
    assert _branca(depois, caixa)
    fora = _fora(depois, caixa)
    assert np.array_equal(depois[fora], antes[fora])          # o texto e o resto, intactos
    assert np.array_equal(np.asarray(ctl.imagem.convert("L")), depois)   # a aberta também
    assert np.array_equal(_imagem(ctl, 1), _imagem(_ligar(projeto), 1))  # as outras, não
    assert ctl.mensagens[-1].startswith("Feito: Borracha na página 1")


def test_ca_12_17_a_borracha_e_gravada_e_o_ctrl_z_a_devolve(projeto, ctl):
    antes = _imagem(ctl)
    caixa = _mancha(antes)
    ctl.operacoes.apagar_manchas(0, [caixa])
    apagada = _imagem(ctl)
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)           # só leitura: o lock é do ctl
    assert reaberto.sequencia.entrada_em(0).borrachas == projeto.sequencia.entrada_em(0).borrachas
    assert np.array_equal(np.asarray(pg.fonte_do_projeto(reaberto).pagina(0).convert("L")),
                          apagada)
    reaberto.fechar()
    ctl.desfazedor.desfazer()
    assert projeto.sequencia.entrada_em(0).borrachas == ()
    assert np.array_equal(_imagem(ctl), antes)
    ctl.desfazedor.refazer()
    assert np.array_equal(_imagem(ctl), apagada)


def test_duas_borrachas_somam_e_tirar_as_devolve(projeto, ctl):
    antes = _imagem(ctl)
    caixa = _mancha(antes)
    x1, y1, x2, y2 = caixa
    meio = (x1 + x2) // 2
    ctl.operacoes.apagar_manchas(0, [(x1, y1, meio, y2)])
    ctl.operacoes.apagar_manchas(0, [(meio, y1, x2, y2)])
    assert len(projeto.sequencia.entrada_em(0).borrachas) == 2
    assert _branca(_imagem(ctl), caixa)
    assert ctl.operacoes.tirar_as_borrachas([0])
    assert np.array_equal(_imagem(ctl), antes)
    assert not ctl.operacoes.tirar_as_borrachas([0])          # sem borracha: nada muda


def test_a_borracha_na_pagina_cortada_e_girada_apaga_o_que_se_ve(projeto, ctl):
    ctl.operacoes.cortar_paginas([0], (0.1, 0.1, 0.1, 0.1))
    ctl.operacoes.girar_paginas([0], 90)
    vista = _imagem(ctl)
    caixa = _mancha(np.rot90(vista, k=1))                     # de pé, para achar a mancha
    altura_de_pe = vista.shape[1]
    x1, y1, x2, y2 = caixa
    na_vista = (altura_de_pe - y2, x1, altura_de_pe - y1, x2)  # a caixa de pé, girada 90°
    assert ctl.operacoes.apagar_manchas(0, [na_vista])
    depois = _imagem(ctl)
    assert _branca(depois, na_vista)
    fora = _fora(depois, na_vista)
    assert np.array_equal(depois[fora], vista[fora])
    ctl.operacoes.tirar_o_corte([0])                          # a borracha é da fonte: fica
    ctl.operacoes.girar_paginas([0], 270)
    inteira = _imagem(ctl)
    assert (inteira[inteira.shape[0] // 3:] >= 128).all()     # nada da mancha sobrou


def test_a_borracha_segue_o_angulo_da_pagina(projeto, ctl):
    ctl.operacoes.endireitar_paginas([0], 2.0)
    torta = _imagem(ctl)
    assert ctl.operacoes.apagar_manchas(0, [_mancha(torta)])
    x1, y1, x2, y2 = _mancha(torta)
    assert _branca(_imagem(ctl), (x1 + 2, y1 + 2, x2 - 2, y2 - 2), minimo=250)
    ctl.operacoes.endireitar_paginas([0], None)               # de volta ao medido (0°)
    reta = _imagem(ctl)
    assert (reta[reta.shape[0] // 3:] >= 128).all()           # a área girou com a página


def test_a_borracha_vai_ao_pdf_pesquisavel(projeto, ctl, tmp_path):
    import fitz

    from abbychess.pdf_pesquisavel import exportar_pdf_pesquisavel

    caixa = _mancha(_imagem(ctl))
    ctl.operacoes.apagar_manchas(0, [caixa])
    projeto.salvar_pagina(0, [BoxEntry(char="P", x1=80, y1=120, x2=100, y2=170,
                                       source="manual", confidence=1.0)])
    destino = tmp_path / "saida.pdf"
    exportar_pdf_pesquisavel(projeto, destino, [0])
    with fitz.open(destino) as doc:
        pix = doc[0].get_pixmap(dpi=300, colorspace=fitz.csGRAY)
        exportada = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    assert (exportada[exportada.shape[0] // 3:] >= 128).all()


def _glifo(char, x1, y1, x2, y2):
    return BoxEntry(char=char, x1=x1, y1=y1, x2=x2, y2=y2, source="manual", confidence=1.0)


def _chars(projeto, posicao=0):
    pagina = projeto.carregar_modelo(posicao)
    return [] if pagina is None else [b.entry.char for b in pagina.boxes]


def test_ca_12_17_o_glifo_lido_na_mancha_sai_com_ela(projeto, ctl):
    caixa = _mancha(_imagem(ctl))
    x1, y1, x2, y2 = caixa
    projeto.salvar_pagina(0, [_glifo("P", 80, 120, 100, 170),
                              _glifo(".", x1 + FOLGA, y1 + FOLGA, x2 - FOLGA, y2 - FOLGA)])
    ctl.ir_para(0)
    gids = [b.gid for b in projeto.carregar_modelo(0).boxes]
    assert ctl.operacoes.apagar_manchas(0, [caixa])
    assert _chars(projeto) == ["P"]
    assert "1 glifo lido saiu" in ctl.mensagens[-1]
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)           # só leitura: o lock é do ctl
    assert [b.entry.char for b in reaberto.carregar_modelo(0).boxes] == ["P"]
    reaberto.fechar()
    ctl.desfazedor.desfazer()                                # o mesmo Ctrl+Z da área devolve
    assert projeto.sequencia.entrada_em(0).borrachas == ()
    assert [b.gid for b in projeto.carregar_modelo(0).boxes] == gids
    ctl.desfazedor.refazer()
    assert _chars(projeto) == ["P"]


def test_o_glifo_so_tocado_pela_area_fica_e_o_aviso_diz(projeto, ctl):
    """O centro fora da área: é a letra vizinha que a borracha pegou de raspão, e o texto dela
    não sai sem o usuário pedir."""
    caixa = _mancha(_imagem(ctl))
    x1, y1, x2, y2 = caixa
    projeto.salvar_pagina(0, [_glifo("r", x2 - 2, y1, x2 + 40, y2)])
    ctl.ir_para(0)
    assert ctl.operacoes.apagar_manchas(0, [caixa])
    assert _chars(projeto) == ["r"]
    assert "1 glifo tocado fica" in ctl.mensagens[-1]


def test_a_area_sem_glifo_lido_nao_troca_a_pagina(projeto, ctl):
    caixa = _mancha(_imagem(ctl))
    projeto.salvar_pagina(0, [_glifo("P", 80, 120, 100, 170)])
    ctl.ir_para(0)
    antes = projeto.carregar_modelo(0).boxes[0].gid
    assert ctl.operacoes.apagar_manchas(0, [caixa])
    assert projeto.carregar_modelo(0).boxes[0].gid == antes
    assert "glifo" not in ctl.mensagens[-1]


def test_sem_os_glifos_tira_as_decisoes_deles_e_a_leitura_vazia():
    a, b = Box(1, BoxEntry(char="a", x1=0, y1=0, x2=10, y2=10)), \
        Box(2, BoxEntry(char="b", x1=50, y1=0, x2=60, y2=10))
    pagina = Pagina(pid=0, indice=0, boxes=[a, b], estado=GLIFOS_MARCADOS,
                    decisoes=Decisoes(quebras=frozenset({1, 2}), juncoes=frozenset({(1, 2)})))
    nova = gm.sem_os_glifos(pagina, [(45, 0, 70, 20)])
    assert [x.gid for x in nova.boxes] == [1]
    assert nova.decisoes.quebras == {1} and not nova.decisoes.juncoes
    assert nova.estado == GLIFOS_MARCADOS
    assert [x.gid for x in pagina.boxes] == [1, 2]            # a de entrada não muda
    assert gm.sem_os_glifos(pagina, [(200, 200, 210, 210)]) is pagina
    vazia = gm.sem_os_glifos(pagina, [(0, 0, 70, 20)])
    assert vazia.boxes == [] and vazia.estado == NAO_RECONHECIDA


def test_a_caixa_vazia_ou_fora_da_pagina_e_recusada(projeto, ctl):
    largura, altura = ctl.imagem.size
    assert not ctl.operacoes.apagar_manchas(0, [(10, 10, 10, 30)])
    assert not ctl.operacoes.apagar_manchas(0, [(largura + 5, 0, largura + 50, 40)])
    assert projeto.sequencia.entrada_em(0).borrachas == ()
    assert ctl.operacoes.apagar_manchas(0, [(-20, -20, 30, 30)])    # aparada na página
    assert _branca(_imagem(ctl), (0, 0, 30, 30))


def test_a_entrada_guarda_a_borracha_no_json():
    quadrilatero = (1.5, 2.0, 10.0, 2.0, 10.0, 8.25, 1.5, 8.25)
    entrada = sq.Entrada(7, borrachas=(quadrilatero,))
    assert sq.Entrada.de_json(entrada.para_json()) == entrada
    assert "borrachas" not in sq.Entrada(7).para_json()
    with pytest.raises(ValueError):
        sq.Entrada(7, borrachas=((1.0, 2.0, 3.0),))


@pytest.mark.parametrize("angulo", [0.0, 1.5, -2.25])
def test_a_caixa_da_vista_vai_a_fonte_antes_de_endireitar(angulo):
    tamanho = (800, 1200)
    geometria = ((40, 60, 760, 1100), 90)
    caixa = (100, 200, 180, 260)
    quadrilatero = geo.borracha_na_fonte(caixa, geometria, tamanho, angulo)
    a, b, c, d = geo.para_a_fonte(caixa, geometria, tamanho)
    cantos = [(a, b), (c, b), (c, d), (a, d)]
    esperados = [v for x, y in cantos for v in pg.ponto_original(x, y, angulo, *tamanho)]
    assert list(quadrilatero) == pytest.approx(esperados, abs=0.01)


# ----------------------------------------------------------------------
# A borracha na janela
# ----------------------------------------------------------------------

def _arrastar(j, de, ate):
    porta = j.visor.viewport()
    inicio = j.visor.mapFromScene(QPointF(*de))
    fim = j.visor.mapFromScene(QPointF(*ate))
    QTest.mousePress(porta, Qt.MouseButton.LeftButton, pos=inicio)
    QTest.mouseMove(porta, fim)
    QTest.mouseRelease(porta, Qt.MouseButton.LeftButton, pos=fim)


def test_a_borracha_na_janela_apaga_o_arraste_e_o_ctrl_z_volta(app, janela):  # noqa: F811
    j = janela
    j.show()
    app.processEvents()
    antes = np.asarray(j.pagina.imagem.convert("L")).copy()
    j.acao_borracha.trigger()
    assert j.acao_borracha.isChecked() and j.visor.modo_borracha
    texto = (40, 90, 420, 220)                               # "Pagina 1"
    _arrastar(j, texto[:2], texto[2:])
    depois = np.asarray(j.pagina.imagem.convert("L"))
    x1, y1, x2, y2 = texto
    assert (depois[y1 + 3:y2 - 3, x1 + 3:x2 - 3] == 255).all()
    assert (antes[y1:y2, x1:x2] < 128).any()                 # havia texto ali
    assert j.acao_desfazer.text().startswith("Desfazer: Borracha na página 1")
    j.acao_desfazer.trigger()
    assert np.array_equal(np.asarray(j.pagina.imagem.convert("L")), antes)


def test_com_zoom_a_vista_fica_onde_estava_depois_de_apagar(app, janela):  # noqa: F811
    j = janela
    j.show()
    app.processEvents()
    j.visor.definir_zoom(4.0)
    barra = j.visor.verticalScrollBar()
    barra.setValue(barra.maximum() // 2)
    antes = barra.value()
    assert antes > 0
    j.acao_borracha.trigger()
    centro = j.visor.mapToScene(j.visor.viewport().rect().center())
    _arrastar(j, (centro.x() - 20, centro.y() - 20), (centro.x() + 20, centro.y() + 20))
    assert j.pagina.projeto.sequencia.entrada_em(0).borrachas
    assert barra.value() == antes


def test_a_borracha_e_os_outros_modos_do_arraste_se_excluem(app, janela):  # noqa: F811
    j = janela
    j.acao_borracha.trigger()
    j.acao_modo_treino.trigger()
    assert j.acao_modo_treino.isChecked() and not j.acao_borracha.isChecked()
    assert not j.visor.modo_borracha
    j.acao_borracha.trigger()
    assert not j.acao_modo_treino.isChecked() and not j.visor.modo_treino
    j.acao_areas.trigger()
    assert not j.acao_borracha.isChecked() and not j.visor.modo_borracha
