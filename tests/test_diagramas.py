"""A leitura dos diagramas: FEN, lado a jogar, conferência, gravação e texto.

O diagrama de teste é desenhado pela fonte de diagrama do PyBoxEditor
(`core.render_diagrama`) numa página sintética e lido pelas redes de diagrama de
verdade, que são pequenas e carregam em menos de um segundo. A rede de glifos
fica de fora, como nos outros testes.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from core import diagrama
from core.box_model import BoxEntry

from abbychess import diagramas as dg
from abbychess import pagina as pg
from abbychess.leitor import FONTE_MANUAL
from abbychess.projeto import ProjetoDeLivro

from tests.livros import PASTA_DOS_PDFS

FONTE_TTF = Path("C:/Windows/Fonts/arial.ttf")

#: Uma posição com roque possível dos dois lados.
FEN = "r3k2r/pp3ppp/2n5/3q4/3P4/2N2N2/PP3PPP/R3K2R"

sem_modelo = pytest.mark.skipif(not Path(diagrama.CAMINHO_MODELO).is_file()
                                or not Path(diagrama.CAMINHO_OCUPACAO).is_file(),
                                reason="os modelos de diagrama do PyBoxEditor não estão aqui")


def pagina_com_diagrama(caminho: Path, fen: str = FEN, legenda: str = "") -> Path:
    """Uma página com uma linha de texto, um tabuleiro de 400 px e outra linha."""
    from core import render_diagrama

    png, _l, _a = render_diagrama.desenhar(fen, lado_px=400, moldura="simples", tons=0)
    tabuleiro = Image.open(io.BytesIO(png)).convert("L")
    pagina = Image.new("L", (1000, 760), 255)
    desenho = ImageDraw.Draw(pagina)
    if not FONTE_TTF.exists():
        pytest.skip("a Arial não está nesta máquina")
    fonte = ImageFont.truetype(str(FONTE_TTF), 40)
    desenho.text((40, 30), "abc abc:", fill=0, font=fonte)
    pagina.paste(tabuleiro, (300, 110))
    if legenda:
        desenho.text((300, 110 + tabuleiro.size[1] + 30), legenda, fill=0, font=fonte)
    desenho.text((40, 680), "cab bca.", fill=0, font=fonte)
    pagina.save(caminho)
    return caminho


def _lido(fen: str = FEN, **campos) -> dg.DiagramaLido:
    from core.tabuleiro_edicao import TabuleiroEdicao

    casas = [diagrama.Casa(c.linha, c.coluna, c.simbolo, 0.99 if c.simbolo else 0.0,
                           confianca_ocupacao=0.999)
             for c in TabuleiroEdicao.de_fen(fen).casas]
    return dg.DiagramaLido(campos.pop("caixa", (300, 110, 704, 514)), casas=casas, **campos)


# ----------------------------------------------------------------------
# Ler
# ----------------------------------------------------------------------

@sem_modelo
def test_le_o_tabuleiro_da_pagina_em_fen(tmp_path):
    imagem = Image.open(pagina_com_diagrama(tmp_path / "p.png"))
    segmentada = pg.segmentar_pagina(imagem)
    assert len(segmentada.tabuleiros) == 1
    assert segmentada.escala > 0

    lidos = dg.ler_diagramas(imagem, segmentada.tabuleiros, escala=segmentada.escala)

    assert len(lidos) == 1
    d = lidos[0]
    assert d.lido and not d.erro
    assert d.fen == FEN + " w - - 0 1"
    assert d.confiavel
    # A página não diz quem joga: o FEN tem 'w' porque o formato exige, mas o
    # lado fica por dizer e o texto diz que é suposição.
    assert d.lado is None and d.lado_origem == ""
    assert "assumido" in d.linha_de_texto(1)
    assert not d.orientacao_confirmada


@sem_modelo
def test_legenda_diz_o_lado_a_jogar(tmp_path):
    imagem = Image.open(pagina_com_diagrama(tmp_path / "p.png", legenda="pretas jogam"))
    segmentada = pg.segmentar_pagina(imagem)
    # A legenda impressa é lida pelo classificador; aqui, um que lê só ela.
    texto = iter("pretasjogam")

    def classificar(_recorte):
        return next(texto, "?"), 1.0

    d = dg.ler_diagramas(imagem, segmentada.tabuleiros, escala=segmentada.escala,
                         classificar=classificar, boxes=segmentada.boxes)[0]
    assert d.titulo == "pretas jogam"
    assert (d.lado, d.lado_origem) == ("b", dg.LADO_DA_LEGENDA)
    assert d.fen.split()[1] == "b"
    assert "pretas a jogar (da legenda)" in d.linha_de_texto(1)


def test_modelo_ausente_vira_erro_e_nao_derruba_a_pagina(monkeypatch):
    def sem_rede(*_a, **_k):
        raise diagrama.ModeloAusente("sem o arquivo")

    monkeypatch.setattr(diagrama, "ler", sem_rede)
    d = dg.ler_diagrama(Image.new("L", (500, 500), 255), (10, 10, 410, 410))
    assert not d.lido and "modelo" in d.erro
    assert d.linha_de_texto(2).startswith("[Diagrama 2: o modelo")


# ----------------------------------------------------------------------
# Conferir
# ----------------------------------------------------------------------

def test_conferir_grava_correcao_lado_e_roque():
    d = _lido()
    tabuleiro = d.edicao()
    assert not tabuleiro.pode_desfazer
    tabuleiro.colocar(0, 0, None)            # tira a torre de a8
    tabuleiro.colocar(4, 4, "Q")             # dama branca em e4
    tabuleiro.definir_lado("b")
    tabuleiro.definir_roque("Kk")

    conferido = d.conferir(tabuleiro)

    assert conferido.conferido
    assert conferido.fen == "4k2r/pp3ppp/2n5/3q4/3PQ3/2N2N2/PP3PPP/R3K2R b Kk - 0 1"
    assert (conferido.lado, conferido.lado_origem) == ("b", dg.LADO_DO_USUARIO)
    linha = conferido.linha_de_texto(1)
    assert "pretas a jogar (informado na revisão)" in linha
    assert "não revisado" not in linha
    assert {c.nome for c in conferido.casas if c.corrigida} == {"a8", "e4"}
    # O original não muda: fechar sem conferir não leva edição nenhuma.
    assert not d.conferido and d.fen.startswith("r3k2r")


def test_conferir_sem_escolher_o_lado_continua_assumido():
    conferido = _lido().conferir(_lido().edicao())
    assert conferido.lado is None
    assert "brancas a jogar (assumido: a página não diz)" in conferido.linha_de_texto(1)


def test_edicao_volta_com_o_que_foi_conferido():
    tabuleiro = _lido().edicao()
    tabuleiro.colocar(7, 7, None)
    assert dg.afirmar_lado(tabuleiro, "w")      # o mesmo 'w', agora dito por alguém
    assert not dg.afirmar_lado(tabuleiro, "w")
    conferido = _lido().conferir(tabuleiro)

    de_novo = conferido.edicao()
    assert de_novo.casa(7, 7).simbolo is None and de_novo.casa(7, 7).corrigida
    assert (de_novo.lado, de_novo.lado_origem) == ("w", dg.LADO_DO_USUARIO)
    assert not de_novo.pode_desfazer


def test_json_vai_e_volta():
    d = _lido(lado="b", lado_origem=dg.LADO_DA_LEGENDA, lado_trecho="pretas jogam",
              titulo="Diagrama 4", motivo="a peça na casa mais fraca ficou em 60%")
    bruto = json.loads(json.dumps(d.para_json()))
    volta = dg.DiagramaLido.de_json(bruto)
    assert volta.para_json() == d.para_json()
    assert volta.fen == d.fen and not volta.confiavel


def test_releitura_mantem_o_diagrama_conferido():
    conferido = _lido(caixa=(100, 100, 500, 500)).conferir(_lido().edicao())
    relido = _lido("8/8/8/8/8/8/8/K6k", caixa=(102, 98, 503, 499))
    outro = _lido("8/8/8/8/8/8/8/k6K", caixa=(100, 900, 500, 1300))

    mesclados = dg.mesclar([relido, outro], [conferido])

    assert mesclados[0].conferido and mesclados[0].fen == conferido.fen
    assert mesclados[0].caixa == (102, 98, 503, 499)
    assert mesclados[1] is outro


def test_diagramas_saem_de_cima_para_baixo():
    caixas = [(80, 2769, 900, 3535), (1533, 302, 2365, 1072), (1548, 1691, 2377, 2465)]
    assert dg.em_ordem(caixas)[0] == (1533, 302, 2365, 1072)
    por_ler = dg.para_caixas(caixas, [])
    assert [d.caixa[1] for d in por_ler] == [302, 1691, 2769]
    assert not any(d.lido for d in por_ler)
    assert dg.diagrama_em(por_ler, 1600, 400) == 0
    assert dg.diagrama_em(por_ler, 10, 10) is None


# ----------------------------------------------------------------------
# Gravar no projeto
# ----------------------------------------------------------------------

@pytest.fixture
def projeto(tmp_path):
    fonte = Image.new("L", (100, 100), 255)
    fonte.save(tmp_path / "f.png")
    return ProjetoDeLivro.criar(tmp_path / "livros", "Diagramas", tmp_path / "f.png")


def test_fen_gravado_volta_com_a_pagina(projeto):
    boxes = [BoxEntry("a", 0, 0, 5, 5, 1.0, FONTE_MANUAL)]
    caixa = (300, 110, 704, 514)
    d = _lido(caixa=caixa).conferir(_lido().edicao())
    projeto.salvar_pagina(0, boxes, [caixa], [d])

    bruto = json.loads((projeto.pasta / "paginas" / "0001.json").read_text(encoding="utf-8"))
    assert bruto["tabuleiros"] == [list(caixa)]
    assert bruto["diagramas"][0]["fen"] == d.fen

    volta = projeto.carregar_diagramas(0)
    assert [x.fen for x in volta] == [d.fen] and volta[0].conferido
    assert projeto.carregar_pagina(0) == boxes


def test_pagina_gravada_antes_da_leitura_abre_com_diagramas_por_ler(projeto):
    """O formato antigo, sem a chave "diagramas", continua valendo."""
    arquivo = projeto.pasta / "paginas" / "0001.json"
    arquivo.write_text(json.dumps({"pagina": 1, "boxes": [], "tabuleiros": [[1, 2, 401, 402]]}),
                       encoding="utf-8")
    assert projeto.carregar_diagramas(0) == []
    assert projeto.carregar_tabuleiros(0) == [(1, 2, 401, 402)]
    por_ler = dg.para_caixas(projeto.carregar_tabuleiros(0), projeto.carregar_diagramas(0))
    assert len(por_ler) == 1 and not por_ler[0].lido


def test_regravar_so_os_boxes_nao_apaga_a_conferencia(projeto):
    """O lote regrava a página sem diagramas; a conferência fica."""
    caixa = (300, 110, 704, 514)
    d = _lido(caixa=caixa).conferir(_lido().edicao())
    projeto.salvar_pagina(0, [], [caixa], [d])
    projeto.salvar_pagina(0, [], [(301, 111, 704, 514)])
    assert [x.fen for x in projeto.carregar_diagramas(0)] == [d.fen]
    projeto.salvar_pagina(0, [], [])
    assert projeto.carregar_diagramas(0) == []


@sem_modelo
def test_amostras_ficam_no_projeto_e_nunca_na_base_global(tmp_path, projeto, monkeypatch):
    from core import treino_diagrama

    global_pecas, global_ocupacao = tmp_path / "global_pecas", tmp_path / "global_ocupacao"
    monkeypatch.setattr(treino_diagrama, "PASTA_PADRAO", str(global_pecas))
    monkeypatch.setattr(treino_diagrama, "PASTA_OCUPACAO", str(global_ocupacao))
    imagem = Image.open(pagina_com_diagrama(tmp_path / "p.png"))
    d = dg.ler_diagrama(imagem, pg.segmentar_pagina(imagem).tabuleiros[0])
    tabuleiro = d.edicao()
    tabuleiro.colocar(3, 3, "Q")               # d5: a dama vira branca

    so_a_corrigida = dg.guardar_amostras(imagem, d, tabuleiro, projeto.pasta, "p0001")
    tudo = dg.guardar_amostras(imagem, d, tabuleiro, projeto.pasta, "p0001", tudo=True)

    pecas, ocupacao = dg.pasta_de_amostras(projeto.pasta)
    assert len(so_a_corrigida) == 2           # a peça e a ocupação de d5
    assert (pecas / "branca" / "Q").is_dir()
    assert len(tudo) == 64 + len(tabuleiro.ocupadas)
    assert all(Path(c).is_relative_to(projeto.pasta) for c in tudo)
    assert dg.amostras_guardadas(projeto.pasta) == 64 + len(tabuleiro.ocupadas)
    assert not global_pecas.exists() and not global_ocupacao.exists()
    assert ocupacao.is_dir()


# ----------------------------------------------------------------------
# O texto da página
# ----------------------------------------------------------------------

def _linha(texto: str, y: int, x: int = 0):
    boxes, cursor = [], x
    for char in texto:
        if char != " ":
            boxes.append(BoxEntry(char, cursor, y, cursor + 10, y + 20, 1.0, FONTE_MANUAL))
        cursor += 14
    return boxes


def test_fen_entra_no_texto_num_fim_de_frase():
    # Linhas de largura parecida: a ordem de leitura do core acha colunas no vão.
    boxes = (_linha("Veja a posição:", 0) + _linha("o texto segue", 40)
             + _linha("e acaba aqui.", 80) + _linha("Depois vem isto", 600))
    # O diagrama começa na altura da segunda linha, que contorna o tabuleiro.
    d = _lido(caixa=(500, 40, 900, 440))

    texto = dg.texto_da_pagina(boxes, [d]).split("\n")

    assert texto[0] == "Veja a posição:"
    assert texto[1].startswith("[Diagrama 1: " + FEN + " w - - 0 1 — brancas a jogar")
    assert texto[1].endswith("; não revisado]")
    assert texto[2:] == ["o texto segue", "e acaba aqui.", "Depois vem isto"]


def test_sem_fim_de_frase_o_diagrama_vai_para_o_fim():
    boxes = _linha("sem ponto", 0) + _linha("nenhum", 40)
    texto = dg.texto_da_pagina(boxes, [_lido(caixa=(500, 30, 900, 430))]).split("\n")
    assert texto[:2] == ["sem ponto", "nenhum"] and texto[2].startswith("[Diagrama 1:")
    assert dg.texto_da_pagina([], [_lido()]).startswith("[Diagrama 1:")


_DARCY = sorted(PASTA_DOS_PDFS.glob("Darcy*/Darcy*.pdf"))


@sem_modelo
@pytest.mark.livro_real
@pytest.mark.skipif(not _DARCY, reason="o PDF do Darcy Lima não está nesta máquina")
def test_darcy_p26_tres_diagramas_lidos_e_conferiveis():
    """Os dois sem setas saem certos; o das setas sai errado e o porteiro avisa."""
    imagem = pg.FonteDePaginas(_DARCY[0]).pagina(25)
    segmentada = pg.segmentar_pagina(imagem)
    lidos = dg.ler_diagramas(imagem, segmentada.tabuleiros, escala=segmentada.escala)

    assert [d.caixa[1] for d in lidos] == sorted(d.caixa[1] for d in lidos)
    assert all(d.lido and d.lado is None for d in lidos)
    meio = "r2qkb1r/2p2pp1/ppn4p/8/3PN2n/PP3N2/bBB2PPP/3Q1RK1"
    assert lidos[0].fen.split()[0] == "rnbk1bnr/pp1p4/2p4p/4q3/2B2pQP/2N5/PPPP2P1/R1BKR3"
    assert lidos[1].fen.split()[0] == meio
    # O esquema com setas é a mesma posição do meio; as setas viram peças.
    assert lidos[2].fen.split()[0] != meio and not lidos[2].confiavel
    # Conferir casa a casa leva o das setas à posição certa.
    from core.tabuleiro_edicao import TabuleiroEdicao

    certo = TabuleiroEdicao.de_fen(meio + " w - - 0 1")
    tabuleiro = lidos[2].edicao()
    for casa in certo.casas:
        tabuleiro.colocar(casa.linha, casa.coluna, casa.simbolo)
    assert lidos[2].conferir(tabuleiro).fen.split()[0] == meio


# ----------------------------------------------------------------------
# A legenda pelas linhas da página
# ----------------------------------------------------------------------

def _legenda(texto: str, x: int, topo: int, char: int = 10):
    """Uma linha de legenda: a maiúscula sobe acima das minúsculas, que têm 7 px."""
    boxes, cursor = [], x
    for c in texto:
        if c != " ":
            alto = c.isupper() or c.isdigit()
            boxes.append(BoxEntry(c, cursor, topo if alto else topo + char // 2 + 8,
                                  cursor + 10, topo + 2 * char, 1.0, FONTE_MANUAL))
        cursor += 14
    return boxes


def test_legenda_sai_da_linha_inteira_dos_boxes():
    # Altura de referência 10: a faixa (3,5) acaba 35 px abaixo do tabuleiro.
    # A legenda começa a 30 px, mas só as maiúsculas: as minúsculas começam a
    # 43, como na p. 26 do Xadrez Vitorioso, onde só o alto das maiúsculas
    # entrava na faixa do core.
    caixa = (100, 100, 500, 500)
    boxes = (_linha("Jogam as brancas.", 0, x=100)            # prosa longe, acima
             + _legenda("Diagrama 6. Jogam as pretas.", 110, 530)
             + _legenda("Potter-Amador", 110, 556)             # a linha de baixo
             + _legenda("Diagrama 7. Jogam as brancas.", 560, 530))  # a do vizinho

    assert dg.legendas_dos_boxes(boxes, caixa, referencia=10) == ["Diagrama 6. Jogam as pretas."]
    # Os lados com rótulos de casa não são legenda.
    assert dg.legendas_dos_boxes(boxes, caixa, ["abaixo"], referencia=10) == []
    # Longe demais (4 alturas) não é legenda.
    longe = _legenda("Jogam as pretas.", 110, 540)
    assert dg.legendas_dos_boxes(longe, caixa, referencia=10) == []


@sem_modelo
def test_legenda_ensinada_nos_boxes_diz_o_lado(tmp_path):
    # O core relê os recortes; sem classificador ele não lê nada. Os boxes da
    # legenda, com os caracteres que o treino do livro lhes deu, dizem o lado.
    imagem = Image.open(pagina_com_diagrama(tmp_path / "p.png", legenda="pretas jogam"))
    segmentada = pg.segmentar_pagina(imagem)
    caixa = segmentada.tabuleiros[0]
    legenda = sorted((b for b in segmentada.boxes if caixa[3] < b.y1 < caixa[3] + 120),
                     key=lambda b: b.x1)
    assert len(legenda) == len("pretasjogam")
    for b, c in zip(legenda, "pretasjogam"):
        b.char, b.source, b.confidence = c, FONTE_MANUAL, 1.0

    d = dg.ler_diagramas(imagem, segmentada.tabuleiros, escala=segmentada.escala,
                         boxes=segmentada.boxes)[0]

    assert (d.lado, d.lado_origem) == ("b", dg.LADO_DA_LEGENDA)
    assert d.titulo == "pretas jogam"
    assert d.fen.split()[1] == "b"


@sem_modelo
def test_legenda_sem_leitura_nos_boxes_continua_assumida(tmp_path):
    imagem = Image.open(pagina_com_diagrama(tmp_path / "p.png", legenda="pretas jogam"))
    segmentada = pg.segmentar_pagina(imagem)
    d = dg.ler_diagramas(imagem, segmentada.tabuleiros, escala=segmentada.escala,
                         boxes=segmentada.boxes)[0]
    assert d.lado is None and d.lado_origem == ""
