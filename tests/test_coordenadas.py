"""Tirar as coordenadas dos diagramas (SPEC §10, CA-10.4): as letras e os números impressos em
volta do tabuleiro saem da imagem pela borracha; a legenda, a prosa e o tabuleiro ficam, e a
orientação que elas confirmaram sobrevive à releitura."""

from __future__ import annotations

import os

import numpy as np
import pytest
from core.box_model import BoxEntry
from core.tabuleiro_edicao import TabuleiroEdicao
from PIL import Image, ImageDraw, ImageFont

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from abbychess import coordenadas as co  # noqa: E402
from abbychess import diagramas as dg  # noqa: E402
from abbychess import modelo as md  # noqa: E402
from abbychess import pagina as pg  # noqa: E402
from abbychess.app import dialogo_paginas as dp  # noqa: E402
from abbychess.borracha import com_borrachas  # noqa: E402
from abbychess.controlador import ControladorDePagina  # noqa: E402
from abbychess.leitor import LeitorDoLivro  # noqa: E402
from abbychess.projeto import ProjetoDeLivro  # noqa: E402

from tests import ajudantes  # noqa: E402
from tests.ajudantes import FONTE_TTF, esperar, pagina_com_diagrama, sem_modelo  # noqa: E402
from tests.fixturas_paginas_na_janela import janela  # noqa: E402,F401,F811

FEN = "6k1/5ppp/8/8/8/8/5PPP/6K1"
TABULEIRO = (200, 150, 600, 550)
CASA = 50
LEGENDA = "Diagrama 6. Jogam as brancas e ganham a partida"
PROSA = ("O texto da coluna vizinha", "corre aqui ao lado do", "tabuleiro, linha por linha,",
         "sem ser coordenada nenhuma", "e continua nas linhas", "seguintes, com muitas letras",
         "em cada casa da altura", "do tabuleiro impresso", "até a linha de baixo",
         "que fecha o parágrafo")


def _fonte(tamanho):
    if not FONTE_TTF.exists():
        pytest.skip("a Arial não está nesta máquina")
    return ImageFont.truetype(str(FONTE_TTF), tamanho)


def _centrado(desenho, texto, cx, cy, fonte):
    a, b, c, d = desenho.textbbox((0, 0), texto, font=fonte)
    desenho.text((cx - (c - a) / 2 - a, cy - (d - b) / 2 - b), texto, fill=0, font=fonte)


def _pagina(*, letras=True, numeros=True, legenda=False, prosa=False, lado_das_letras="abaixo",
            vao_da_legenda=None):
    """Uma página branca com o tabuleiro (a grade e a moldura), e o que se pedir em volta. A
    legenda vem logo abaixo do que houver embaixo dele, ou a `vao_da_legenda` dele."""
    imagem = Image.new("L", (1200, 800), 255)
    d = ImageDraw.Draw(imagem)
    x1, y1, x2, y2 = TABULEIRO
    d.rectangle((x1, y1, x2 - 1, y2 - 1), outline=0, width=2)
    for k in range(8):
        for j in range(8):
            if (k + j) % 2:
                d.rectangle((x1 + j * CASA + 3, y1 + k * CASA + 3,
                             x1 + (j + 1) * CASA - 3, y1 + (k + 1) * CASA - 3), fill=120)
    fonte = _fonte(22)
    if letras:
        cy = y2 + 24 if lado_das_letras == "abaixo" else y1 - 24
        for j, letra in enumerate("abcdefgh"):
            _centrado(d, letra, x1 + (j + 0.5) * CASA, cy, fonte)
    if numeros:
        for k, numero in enumerate("87654321"):
            _centrado(d, numero, x1 - 22, y1 + (k + 0.5) * CASA, fonte)
    if legenda:
        vao = vao_da_legenda if vao_da_legenda is not None else (50 if letras else 8)
        d.text((x1, y2 + vao), LEGENDA, fill=0, font=fonte)
    if prosa:
        for k, linha in enumerate(PROSA):
            d.text((x2 + 12, y1 + k * 40), linha, fill=0, font=fonte)
    return imagem


def _so_muda_em(antes, depois, caixas):
    mascara = np.ones(np.asarray(antes).shape, dtype=bool)
    for x1, y1, x2, y2 in caixas:
        mascara[y1:y2, x1:x2] = False
    return np.array_equal(np.asarray(antes)[mascara], np.asarray(depois)[mascara])


def _tinta(imagem, caixa):
    x1, y1, x2, y2 = caixa
    return int((np.asarray(imagem)[y1:y2, x1:x2] < 128).sum())


# ----------------------------------------------------------------------
# Achar
# ----------------------------------------------------------------------

def test_acha_as_letras_embaixo_e_os_numeros_a_esquerda():
    x1, y1, x2, y2 = TABULEIRO
    esquerda, abaixo = co.caixas_das_coordenadas(_pagina(), TABULEIRO)
    assert esquerda[2] <= x1 and y1 <= esquerda[1] and esquerda[3] <= y2
    assert abaixo[1] >= y2 and x1 <= abaixo[0] and abaixo[2] <= x2
    # Toda a tinta de fora do tabuleiro está nelas.
    sem = np.asarray(_pagina()).copy()
    for a, b, c, d in (esquerda, abaixo):
        sem[b:d, a:c] = 255
    assert np.array_equal(sem, np.asarray(_pagina(letras=False, numeros=False)))


def test_acha_as_letras_em_cima_tambem():
    caixas = co.caixas_das_coordenadas(_pagina(lado_das_letras="acima"), TABULEIRO)
    assert len(caixas) == 2 and any(c[3] <= TABULEIRO[1] for c in caixas)


def test_a_casa_sem_marca_nao_impede_e_duas_impedem():
    imagem = _pagina(numeros=False)
    x1, _y1, _x2, y2 = TABULEIRO
    d = ImageDraw.Draw(imagem)
    d.rectangle((x1, y2 + 2, x1 + CASA - 1, y2 + 60), fill=255)         # o "a" apagado
    assert len(co.caixas_das_coordenadas(imagem, TABULEIRO)) == 1
    d.rectangle((x1 + CASA, y2 + 2, x1 + 2 * CASA - 1, y2 + 60), fill=255)
    assert co.caixas_das_coordenadas(imagem, TABULEIRO) == []


def test_tabuleiro_sem_coordenadas_nao_tem_nada_a_tirar():
    assert co.caixas_das_coordenadas(_pagina(letras=False, numeros=False), TABULEIRO) == []


@pytest.mark.parametrize("campos", [{"legenda": True}, {"prosa": True},
                                    {"legenda": True, "prosa": True}])
def test_legenda_e_prosa_coladas_nao_sao_coordenadas(campos):
    imagem = _pagina(letras=False, numeros=False, **campos)
    assert co.caixas_das_coordenadas(imagem, TABULEIRO) == []


def test_com_legenda_e_prosa_so_as_coordenadas_saem():
    imagem = _pagina(legenda=True, prosa=True)
    caixas = co.caixas_das_coordenadas(imagem, TABULEIRO)
    assert len(caixas) == 2
    sem = np.asarray(imagem).copy()
    for a, b, c, d in caixas:
        sem[b:d, a:c] = 255
    assert np.array_equal(sem, np.asarray(_pagina(letras=False, numeros=False, legenda=True,
                                                  prosa=True, vao_da_legenda=50)))


def test_a_letra_partida_pelo_limiar_sai_inteira():
    imagem = _pagina(numeros=False)
    x1, _y1, _x2, y2 = TABULEIRO
    d = ImageDraw.Draw(imagem)
    d.rectangle((x1 + 5.5 * CASA + 8, y2 + 18, x1 + 5.5 * CASA + 10, y2 + 20), fill=0)   # o pedaço
    [caixa] = co.caixas_das_coordenadas(imagem, TABULEIRO)
    a, b, c, e = caixa
    sem = np.asarray(imagem).copy()
    sem[b:e, a:c] = 255
    assert _tinta(sem, (x1, y2, TABULEIRO[2], y2 + 60)) == 0


def test_a_moldura_de_fora_nao_entra_e_nao_engana():
    imagem = _pagina()
    x1, y1, x2, y2 = TABULEIRO
    ImageDraw.Draw(imagem).rectangle((x1 - 4, y1 - 4, x2 + 3, y2 + 3), outline=0, width=1)
    assert len(co.caixas_das_coordenadas(imagem, TABULEIRO)) == 2


def test_na_beira_da_imagem_nao_estoura():
    imagem = _pagina().crop((150, 100, 620, 575))              # sem margem depois do "a b c"
    caixa = (50, 50, 450, 450)
    assert len(co.caixas_das_coordenadas(imagem, caixa)) == 2


# ----------------------------------------------------------------------
# A orientação na releitura
# ----------------------------------------------------------------------

def _lido(fen=FEN, **campos):
    return ajudantes._lido(fen, **{"caixa": TABULEIRO, **campos})


def _girado(fen):
    """O FEN lido de um tabuleiro impresso com as pretas embaixo, supondo as brancas."""
    casas = TabuleiroEdicao.de_fen(fen).casas
    simbolos = [c.simbolo for c in reversed(casas)]
    linhas = []
    for k in range(8):
        linha, vazias = "", 0
        for s in simbolos[k * 8:k * 8 + 8]:
            if s is None:
                vazias += 1
            else:
                linha += (str(vazias) if vazias else "") + s
                vazias = 0
        linhas.append(linha + (str(vazias) if vazias else ""))
    return "/".join(linhas)


def test_a_releitura_sem_rotulos_guarda_a_orientacao_confirmada():
    antes = _lido(orientacao="preta", orientacao_confirmada=True)
    relido = _lido(_girado(FEN), caixa=(202, 151, 601, 549))     # supôs as brancas embaixo
    [mesclado] = dg.mesclar([relido], [antes])
    assert mesclado.orientacao == "preta" and mesclado.orientacao_confirmada
    assert mesclado.fen.split()[0] == FEN
    assert [(c.linha, c.coluna) for c in mesclado.casas] == [(k // 8, k % 8) for k in range(64)]
    assert mesclado.caixa == (202, 151, 601, 549)


def test_a_releitura_das_brancas_so_confirma():
    [mesclado] = dg.mesclar([_lido()], [_lido(orientacao_confirmada=True)])
    assert mesclado.orientacao == "branca" and mesclado.orientacao_confirmada
    assert mesclado.fen.split()[0] == FEN


def test_o_que_a_releitura_confirmou_vale_mais():
    novo = _lido(orientacao="branca", orientacao_confirmada=True)
    [mesclado] = dg.mesclar([novo], [_lido(orientacao="preta", orientacao_confirmada=True)])
    assert mesclado is novo


def test_sem_confirmacao_antes_a_releitura_fica_como_veio():
    novo = _lido()
    assert dg.mesclar([novo], [_lido(orientacao="preta")])[0] is novo
    assert dg.mesclar([novo], [])[0] is novo


@sem_modelo
def test_ca_10_4_o_tabuleiro_com_as_pretas_embaixo_sai_igual_depois_de_tirar_e_reler(tmp_path):
    """Com as redes de verdade e as coordenadas impressas ao contrário: a leitura sem elas supõe
    as brancas embaixo, e a orientação que elas confirmaram desfaz o erro."""
    imagem = Image.open(pagina_com_diagrama(tmp_path / "p.png")).convert("L")
    segmentada = pg.segmentar_pagina(imagem)
    [caixa] = segmentada.tabuleiros
    x1, y1, x2, y2 = caixa
    casa = (x2 - x1) / 8
    d = ImageDraw.Draw(imagem)
    fonte = _fonte(int(casa * 0.4))
    for k in range(8):
        _centrado(d, "hgfedcba"[k], x1 + (k + 0.5) * casa, y2 + casa * 0.4, fonte)
        _centrado(d, "12345678"[k], x1 - casa * 0.4, y1 + (k + 0.5) * casa, fonte)
    rotulos = iter("hgfedcba12345678")

    def classificar(_recorte):
        return next(rotulos, "?"), 1.0

    antes = dg.ler_diagramas(imagem, [caixa], escala=segmentada.escala,
                             classificar=classificar)[0]
    assert antes.orientacao == "preta" and antes.orientacao_confirmada

    caixas = co.caixas_das_coordenadas(imagem, caixa)
    assert len(caixas) == 2
    limpa = com_borrachas(imagem, [(a, b, c, b, c, e, a, e) for a, b, c, e in caixas])
    relido = dg.ler_diagramas(limpa, [caixa], escala=segmentada.escala,
                              classificar=lambda _r: ("?", 0.0))[0]
    assert not relido.orientacao_confirmada and relido.fen != antes.fen   # o erro que se evita

    [mesclado] = dg.mesclar([relido], [antes])
    assert mesclado.fen == antes.fen
    assert mesclado.orientacao == "preta" and mesclado.orientacao_confirmada


# ----------------------------------------------------------------------
# A operação de página
# ----------------------------------------------------------------------

@pytest.fixture
def sem_endireitar(monkeypatch):
    monkeypatch.setattr(pg, "medir_inclinacao", lambda *_a, **_k: 0.0)


@pytest.fixture
def pdf(tmp_path):
    """Três páginas: com coordenadas; sem coordenadas; e com, para a seleção de várias."""
    import fitz

    caminho = tmp_path / "livro.pdf"
    paginas = [_pagina(legenda=True, prosa=True), _pagina(letras=False, numeros=False),
               _pagina(legenda=True)]
    primeira, *resto = [p.convert("RGB") for p in paginas]
    primeira.save(caminho, "PDF", resolution=300, save_all=True, append_images=resto)
    with fitz.open(caminho) as doc:
        assert len(doc) == 3
    return caminho


@pytest.fixture
def ctl(tmp_path, pdf, sem_endireitar):
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Coordenadas", pdf)
    controlador = ControladorDePagina()
    controlador.mensagens = []
    controlador.eventos.ligar("mensagem", lambda texto, _ms: controlador.mensagens.append(texto))
    controlador.ligar(projeto, pg.fonte_do_projeto(projeto),
                      LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    controlador.ir_para(0)
    return controlador


def _imagem(ctl, posicao=0):
    return np.asarray(ctl.fonte.pagina(posicao).convert("L"))


def _com_diagrama(ctl, posicao, *boxes, lido=True):
    """A página gravada com o diagrama no tabuleiro: lido, ou só a caixa."""
    projeto = ctl.projeto
    projeto.salvar_pagina(posicao, list(boxes) or [_glifo("P", 900, 700, 920, 730)])
    pagina = projeto.carregar_modelo(posicao)
    pagina.tabuleiros = [TABULEIRO]
    pagina.diagramas = dg.com_ids([_lido() if lido else dg.DiagramaLido(TABULEIRO)])
    pagina.estado = md.RECONHECIDA
    projeto.paginas_em_memoria.guardar(pagina)
    projeto.paginas_em_memoria.agendar(pagina)
    projeto.paginas_em_memoria.descarregar()
    ctl.ir_para(ctl.indice)


def _glifo(char, x1, y1, x2, y2):
    return BoxEntry(char=char, x1=x1, y1=y1, x2=x2, y2=y2, source="manual", confidence=1.0)


def test_ca_10_4_as_coordenadas_saem_e_o_resto_nao_muda(ctl):
    _com_diagrama(ctl, 0)
    antes = _imagem(ctl)
    ctl.operacoes.tirar_as_coordenadas([0])
    depois = _imagem(ctl)
    x1, y1, x2, y2 = TABULEIRO
    assert _tinta(depois, (x1 - 45, y1, x1, y2)) == 0                    # os números
    assert _tinta(depois, (x1, y2, x2, y2 + 45)) == 0                    # as letras
    assert np.array_equal(depois[y1:y2, x1:x2], antes[y1:y2, x1:x2])     # o tabuleiro
    assert np.array_equal(depois[y1:y2, x2:], antes[y1:y2, x2:])         # a prosa
    assert np.array_equal(depois[y2 + 45:], antes[y2 + 45:])             # a legenda
    assert ctl.mensagens[-1].startswith("Feito: Tirar as coordenadas de 1 página")


def test_ca_10_4_e_um_passo_so_do_ctrl_z_com_varias_paginas(ctl):
    _com_diagrama(ctl, 0)
    _com_diagrama(ctl, 2)
    antes = [_imagem(ctl, 0), _imagem(ctl, 2)]
    ctl.operacoes.tirar_as_coordenadas([0, 1, 2])
    assert len(ctl.projeto.sequencia.entrada_em(0).borrachas) == 2
    assert len(ctl.projeto.sequencia.entrada_em(2).borrachas) == 2
    assert ctl.projeto.sequencia.entrada_em(1).borrachas == ()
    ctl.desfazedor.desfazer()
    assert np.array_equal(_imagem(ctl, 0), antes[0]) and np.array_equal(_imagem(ctl, 2), antes[1])
    ctl.desfazedor.refazer()
    assert not np.array_equal(_imagem(ctl, 0), antes[0])


def test_ca_10_4_tirar_a_borracha_as_devolve(ctl):
    _com_diagrama(ctl, 0)
    antes = _imagem(ctl)
    ctl.operacoes.tirar_as_coordenadas([0])
    assert ctl.operacoes.tirar_as_borrachas([0])
    assert np.array_equal(_imagem(ctl), antes)


def test_ca_10_4_os_glifos_lidos_nelas_saem_e_voltam_com_o_ctrl_z(ctl):
    x1, _y1, _x2, y2 = TABULEIRO
    _com_diagrama(ctl, 0, _glifo("P", 900, 700, 920, 730),
                  _glifo("a", x1 + 15, y2 + 12, x1 + 35, y2 + 36))
    ctl.operacoes.tirar_as_coordenadas([0])
    assert [b.entry.char for b in ctl.projeto.carregar_modelo(0).boxes] == ["P"]
    assert "1 glifo lido saiu" in ctl.mensagens[-1]
    ctl.desfazedor.desfazer()
    assert [b.entry.char for b in ctl.projeto.carregar_modelo(0).boxes] == ["P", "a"]


def test_ca_10_4_o_diagrama_por_ler_fica_com_as_dele(ctl):
    _com_diagrama(ctl, 0, lido=False)
    antes = ctl.projeto.sequencia
    ctl.operacoes.tirar_as_coordenadas([0])
    assert ctl.projeto.sequencia == antes
    assert "nenhum diagrama lido" in ctl.mensagens[-1]


def test_ca_10_4_sem_nada_a_tirar_o_aviso_diz_e_a_sequencia_fica(ctl):
    _com_diagrama(ctl, 1)
    antes = ctl.projeto.sequencia
    ctl.operacoes.tirar_as_coordenadas([1])
    assert ctl.projeto.sequencia == antes
    assert "nenhuma coordenada" in ctl.mensagens[-1]


def test_ca_10_4_de_novo_nao_acha_nada(ctl):
    _com_diagrama(ctl, 0)
    ctl.operacoes.tirar_as_coordenadas([0])
    borrachas = ctl.projeto.sequencia.entrada_em(0).borrachas
    ctl.operacoes.tirar_as_coordenadas([0])
    assert ctl.projeto.sequencia.entrada_em(0).borrachas == borrachas


def test_ca_10_4_a_area_segue_a_pagina_girada(ctl):
    _com_diagrama(ctl, 0)
    ctl.operacoes.tirar_as_coordenadas([0])
    em_pe = _imagem(ctl)
    ctl.operacoes.girar_paginas([0], 90)
    assert np.array_equal(_imagem(ctl), np.rot90(em_pe, k=-1))


def test_ca_10_4_o_pdf_pesquisavel_sai_sem_elas(ctl, tmp_path):
    import fitz

    from abbychess.pdf_pesquisavel import exportar_pdf_pesquisavel

    _com_diagrama(ctl, 0)
    ctl.operacoes.tirar_as_coordenadas([0])
    destino = tmp_path / "saida.pdf"
    exportar_pdf_pesquisavel(ctl.projeto, destino, [0])
    with fitz.open(destino) as doc:
        pix = doc[0].get_pixmap(dpi=300, colorspace=fitz.csGRAY)
        saida = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    x1, y1, x2, y2 = TABULEIRO
    assert _tinta(saida, (x1 - 45, y1, x1, y2)) == 0
    assert _tinta(saida, (x1, y2, x2, y2 + 45)) == 0


# ----------------------------------------------------------------------
# Na janela
# ----------------------------------------------------------------------

def _diagrama_na_aberta(j):
    p = j.pagina
    pagina = p._pagina_para_editar()
    pagina.tabuleiros = [(100, 100, 300, 300)]
    pagina.diagramas = dg.com_ids([_lido(caixa=(100, 100, 300, 300))])
    p._gravar(pagina)


def _fingir_as_coordenadas(monkeypatch):
    monkeypatch.setattr(co, "caixas_das_coordenadas", lambda _i, _t: [(50, 100, 95, 300)])


def test_o_menu_pergunta_as_paginas_e_a_tarefa_tira_num_passo_do_desfazer(app, janela, monkeypatch):  # noqa: F811
    j = janela
    _diagrama_na_aberta(j)
    _fingir_as_coordenadas(monkeypatch)
    monkeypatch.setattr(dp, "perguntar_paginas", lambda *_a, **_k: ([0], -1))
    assert j.acao_tirar_as_coordenadas in j.acoes_de_paginas
    assert j.acao_tirar_as_coordenadas.isEnabled()
    j.acao_tirar_as_coordenadas.trigger()
    sequencia = j.pagina.projeto.sequencia
    assert esperar(lambda: j.pagina.projeto.sequencia.entrada_em(0).borrachas)
    assert sequencia.entrada_em(0).borrachas == ()
    assert j.acao_desfazer.text().startswith("Desfazer: Tirar as coordenadas de 1 página")
    j.acao_desfazer.trigger()
    assert j.pagina.projeto.sequencia.entrada_em(0).borrachas == ()


def test_a_gaveta_oferece_a_operacao(app, janela, monkeypatch):  # noqa: F811
    from abbychess.app.painel_paginas import OPERACOES_DA_GAVETA

    j = janela
    assert ("Tirar as coordenadas…", "tirar_as_coordenadas") in OPERACOES_DA_GAVETA
    _diagrama_na_aberta(j)
    _fingir_as_coordenadas(monkeypatch)
    monkeypatch.setattr(dp, "perguntar_paginas", lambda *_a, **_k: ([0], -1))
    j.operacao_da_gaveta("tirar_as_coordenadas", [0])
    assert esperar(lambda: j.pagina.projeto.sequencia.entrada_em(0).borrachas)
