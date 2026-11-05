"""M3, PPT: CA-U13, CA-U14, CA-F2.1, CA-F2.2, CA-F4.6, CA-U3, CA-U10."""

from __future__ import annotations

import pytest
from core.box_model import BoxEntry
from PySide6.QtGui import QFont, QFontMetricsF
from PySide6.QtTest import QTest

from abbychess import grade as gd
from abbychess import livro as lv
from abbychess import pagina as pg
from abbychess.app import documento as dc
from abbychess.app import estilo
from abbychess.app import painel_treino as pt
from abbychess.app.desenho import _sem_pendentes
from abbychess.app.imagens import FONTE
from abbychess.app.janela import JanelaPrincipal
from abbychess.leitor import LeitorDoLivro
from abbychess.projeto import ProjetoDeLivro
from tests.ajudantes import _escrever, _pagina_sintetica


@pytest.fixture
def janela(app, tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path, "Livro", _pagina_sintetica(tmp_path / "p.png"))
    j = JanelaPrincipal()
    j.usar(projeto, pg.FonteDePaginas(projeto.fonte),
           LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    j.resize(1366, 768)
    j.show()
    j.activateWindow()
    app.processEvents()
    yield j
    j.close()


def _contraste(a, b) -> float:
    def luminancia(cor):
        def canal(c):
            c = c / 255
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * canal(cor.red()) + 0.7152 * canal(cor.green()) + 0.0722 * canal(cor.blue())
    claro, escuro = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (claro + 0.05) / (escuro + 0.05)


# ------------------------------------------------------------------
# U-13
# ------------------------------------------------------------------
def _linhas_visuais(vista) -> list:
    saida = []
    bloco = vista.document().begin()
    while bloco.isValid():
        saida.append(bloco.layout().lineCount())
        bloco = bloco.next()
    return saida


def test_ca_u13_a_linha_impressa_nao_quebra_e_o_corpo_diminui(app, janela):
    longa = "palavra " * 16
    _escrever(janela, longa.strip(), "curta")
    janela.vista.setCurrentIndex(0)
    janela.divisor.setSizes([900, 450])
    app.processEvents()
    janela.pintar_texto()
    app.processEvents()
    assert all(n == 1 for n in _linhas_visuais(janela.texto))
    assert janela.texto._corpo_montado < janela.texto.corpo
    assert janela.texto._corpo_montado >= dc.CORPO_DO_ENCAIXE


def test_ca_u13_abaixo_do_minimo_ha_rolagem_e_nao_quebra(app, janela):
    _escrever(janela, " ".join(["palavra"] * 60))
    janela.divisor.setSizes([1000, 300])
    app.processEvents()
    janela.pintar_texto()
    app.processEvents()
    assert janela.texto._corpo_montado == dc.CORPO_DO_ENCAIXE
    assert all(n == 1 for n in _linhas_visuais(janela.texto))
    assert janela.texto.horizontalScrollBar().maximum() > 0


def test_a_linha_que_cabe_fica_no_corpo_do_usuario(app, janela):
    _escrever(janela, "curta")
    assert janela.texto._corpo_montado == janela.texto.corpo


def test_fora_da_tela_o_corpo_nao_muda(app):
    vista = dc.VistaDoDocumento()
    assert vista._corpo_que_cabe(object()) == vista.corpo
    vista.deleteLater()


def test_o_formato_do_titulo_segue_o_corpo_montado(app):
    vista = dc.VistaDoDocumento()
    vista._corpo_montado = 10
    assert vista._formato_do_caractere("titulo").fontPointSize() == 13
    assert vista._formato_do_bloco("texto").nonBreakableLines()
    vista.deleteLater()


def test_as_metricas_usam_a_fonte_do_documento(app):
    assert QFontMetricsF(QFont(FONTE, 11)).horizontalAdvance("abc") > 0


# ------------------------------------------------------------------
# U-14
# ------------------------------------------------------------------
def test_ca_u14_a_largura_usa_a_mancha_e_nao_a_folha(app, janela):
    _escrever(janela, *["palavra de texto corrido aqui"] * 4)
    visor = janela.visor
    visor.zoom_pagina()
    app.processEvents()
    da_folha = visor.escala()
    visor.zoom_largura()
    app.processEvents()
    assert visor.escala() >= da_folha * 1.15


def test_a_mancha_sem_a_poeira(app, janela):
    visor = janela.visor
    boxes = [BoxEntry("a", 100 + k, 10, 110 + k, 20) for k in range(200)]
    visor._boxes = boxes + [BoxEntry(".", 0, 0, 1, 1)]
    x1, x2 = visor._mancha()
    assert 90 < x1 <= 100 and x2 >= 300


def test_sem_glifos_nao_ha_mancha(janela):
    janela.visor._boxes = []
    assert janela.visor._mancha() is None


def test_o_espaco_padrao_abre_na_largura(janela):
    janela._espaco_padrao()
    assert janela.visor.modo_zoom == "largura"


# ------------------------------------------------------------------
# F-2
# ------------------------------------------------------------------
def test_ca_f2_1_o_fundo_forte_passa_de_3_para_1():
    assert _contraste(estilo.FUNDO_FORTE, estilo.PAPEL) > 3
    assert _contraste(estilo.FUNDO_FORTE, estilo.FUNDO_DA_BUSCA) > 3


def test_ca_f2_2_o_estado_tem_traco(app):
    from PySide6.QtGui import QTextCharFormat

    from abbychess.app.formatos_do_documento import formato_novo

    forte = formato_novo(QTextCharFormat(), gd.FORTE, False, False, None)
    pendente = formato_novo(QTextCharFormat(), gd.PENDENTE, False, False, None)
    assert forte.underlineStyle() == QTextCharFormat.UnderlineStyle.SingleUnderline
    assert pendente.underlineStyle() != QTextCharFormat.UnderlineStyle.SingleUnderline


def _fundo_em(janela, gid):
    cursor = janela.texto.textCursor()
    cursor.setPosition(janela.texto.posicao_do_gid(gid) + 1)
    return cursor.charFormat().background().color()


def test_ca_f4_6_o_vazio_e_a_palavra_desmentida_ficam_destacados(app, janela):
    from dataclasses import replace

    pagina = _escrever(janela, "s0rte de palavra")
    p = janela.pagina
    sem_leitura = pagina.boxes[-1]
    p.modelo.boxes = [replace(b, entry=replace(b.entry, char="", source="none"))
                      if b is sem_leitura else b for b in p.modelo.boxes]
    janela.pintar_texto()
    evidencia = p.evidencia.agora()
    assert evidencia.motivos[sem_leitura.gid][0] == "Ninguém leu"
    zero = next(b for b in p.modelo.boxes if b.entry.char == "0")
    assert evidencia.motivos[zero.gid][0] == "A palavra desmente"
    assert _fundo_em(janela, zero.gid) == estilo.FUNDO_FORTE


def test_ca_f4_6_o_realce_de_hoje_continua_por_baixo(app, janela):
    pagina = _escrever(janela, "abc")
    p = janela.pagina
    p.leitor.limiares.revisao = 1.0
    p.fila_da_pagina._limiar_da_pendencia = None
    janela.pintar_texto()
    assert _fundo_em(janela, pagina.boxes[0].gid) == estilo.FUNDO_DE_BAIXA_CONFIANCA


def test_o_glifo_aguardando_nao_e_forte(app, janela):
    from dataclasses import replace

    pagina = _escrever(janela, "abc")
    p = janela.pagina
    p.modelo.boxes = [replace(b, entry=replace(b.entry, char="", source=""))
                      if b is pagina.boxes[0] else b for b in p.modelo.boxes]
    assert pagina.boxes[0].gid not in p.evidencia.agora().fortes


# ------------------------------------------------------------------
# U-3
# ------------------------------------------------------------------
def test_ca_u3_a_etiqueta_conta_o_livro():
    resumo = {0: {"estado": "verificada", "lances_por_conferir": 3, "diagramas_por_conferir": 1},
              1: {"estado": "reconhecida", "lances_por_conferir": 7},
              2: {"estado": "nao_reconhecida"}}
    assert lv.progresso(resumo, 300) == "verificadas 1/300 · lances por conferir 10 · diagramas 1"


def test_ca_u3_a_etiqueta_acompanha_na_janela(app, janela):
    pagina = _escrever(janela, "1.e4 e5")
    janela.projeto.salvar_modelo(pagina)
    janela.atualizar_paginas()
    assert "lances por conferir 2" in janela.rotulo_do_progresso.text()
    assert janela.rotulo_do_progresso.text().startswith("verificadas 0/")


def test_ca_u3_a_fila_vazia_oferece_o_lote():
    assert "Faltam ler 12" in _sem_pendentes({"nao_conferidos": 0}, 12)
    assert "Faltam ler" not in _sem_pendentes({"nao_conferidos": 0}, 0)


# ------------------------------------------------------------------
# U-10
# ------------------------------------------------------------------
@pytest.fixture(autouse=True)
def uso_limpo():
    pt._USO_DA_PALETA.clear()
    yield
    pt._USO_DA_PALETA.clear()


def test_ca_u10_mais_ou_menos_em_tres_teclas(app):
    escolhidos = []
    menu = pt.menu_da_paleta(None, escolhidos.append)     # a tecla 1: F2
    QTest.keyClicks(menu, "+=")                           # as teclas 2 e 3
    assert escolhidos == ["±"]


def test_o_filtro_pelo_nome(app):
    menu = pt.menu_da_paleta(None, [].append)
    QTest.keyClicks(menu, "ata")
    assert menu.acoes_dos_simbolos["→"].isVisible()
    assert not menu.acoes_dos_simbolos["♔"].isVisible()


def test_o_filtro_com_um_resultado_ja_escolhe(app):
    escolhidos = []
    menu = pt.menu_da_paleta(None, escolhidos.append)
    QTest.keyClicks(menu, "zugz")
    assert escolhidos == ["⨀"]


def test_os_mais_usados_vem_nas_teclas_de_numero(app):
    pt._USO_DA_PALETA.update({"⩲": 5, "!": 2})
    escolhidos = []
    menu = pt.menu_da_paleta(None, escolhidos.append)
    assert menu.actions()[0].text().startswith("1  ⩲")
    QTest.keyClicks(menu, "2")
    assert escolhidos == ["!"]


def test_escolher_conta_o_uso(app):
    menu = pt.menu_da_paleta(None, [].append)
    menu.escolher("∞")
    assert pt._USO_DA_PALETA["∞"] == 1


def test_a_grade_sai_abaixo_de_900(app, janela):
    janela.inspetor.mostrar("glifo")
    janela.resize(1366, 768)
    app.processEvents()
    janela.treino.ajustar_a_paleta()
    assert janela.treino.grade_da_paleta.isHidden()
    janela.resize(1366, 1000)
    app.processEvents()
    janela.treino.ajustar_a_paleta()
    if janela.height() >= pt.ALTURA_DA_GRADE_DA_PALETA:   # o offscreen pode limitar a altura
        assert not janela.treino.grade_da_paleta.isHidden()
