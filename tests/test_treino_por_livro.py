"""O treino por livro: projeto, padrões que valem na hora e propagação na página.

Rodam sem a rede global do PyBoxEditor (`ocr=None`), para o resultado depender só
dos padrões do livro e o teste não precisar do modelo de 2,8 MB.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from abbychess import pagina as pg
from abbychess.leitor import FONTE_LIVRO, FONTE_MANUAL, LeitorDoLivro
from abbychess.projeto import ProjetoDeLivro, ProjetoInvalido, nome_de_pasta

FONTE_TTF = Path("C:/Windows/Fonts/arial.ttf")


def _pagina_sintetica(caminho: Path, linhas=("abc abc abc", "cab bca")) -> Path:
    imagem = Image.new("L", (900, 80 + 90 * len(linhas)), 255)
    desenho = ImageDraw.Draw(imagem)
    fonte = (ImageFont.truetype(str(FONTE_TTF), 56) if FONTE_TTF.exists()
             else ImageFont.load_default(size=56))
    for i, linha in enumerate(linhas):
        desenho.text((40, 40 + 90 * i), linha, fill=0, font=fonte)
    imagem.save(caminho)
    return caminho


@pytest.fixture
def projeto(tmp_path):
    fonte = _pagina_sintetica(tmp_path / "pagina.png")
    return ProjetoDeLivro.criar(tmp_path / "livros", "Estratégia no Xadrez", fonte)


@pytest.fixture
def leitor(projeto):
    return LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)


def test_nome_de_pasta_tira_acento_e_simbolo():
    assert nome_de_pasta("Darcy Lima & Júlio — A Estratégia") == "darcy-lima-julio-a-estrategia"
    assert nome_de_pasta("???") == "livro"


def test_projeto_criado_reabre_com_os_mesmos_dados(projeto):
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    assert reaberto.dados == projeto.dados
    assert reaberto.pasta.name == "estrategia-no-xadrez"
    assert reaberto.pasta_de_padroes.is_dir()


def test_pasta_mae_com_acento_guarda_e_le_os_padroes(tmp_path):
    """O OpenCV do Windows perde arquivos em caminho com acento; os padrões não."""
    fonte = _pagina_sintetica(tmp_path / "p.png")
    projeto = ProjetoDeLivro.criar(tmp_path / "Livros de Ação", "X", fonte)
    imagem = pg.FonteDePaginas(projeto.fonte).pagina(0)
    boxes = pg.segmentar(imagem)
    leitor = LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)
    pg.ensinar(imagem, boxes, 0, "a", leitor, projeto, pagina=0, propagar=False)

    novo = LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)
    assert novo.total_de_padroes == 1
    assert novo.ler(pg.recorte(imagem, boxes[3])).char == "a"


def test_projeto_repetido_e_recusado(projeto, tmp_path):
    with pytest.raises(ProjetoInvalido, match="Já existe"):
        ProjetoDeLivro.criar(tmp_path / "livros", "Estratégia no Xadrez", projeto.fonte)


def test_pagina_gravada_volta_igual(projeto):
    fonte = pg.FonteDePaginas(projeto.fonte)
    boxes = pg.segmentar(fonte.pagina(0))
    boxes[0].char, boxes[0].source, boxes[0].confidence = "a", FONTE_MANUAL, 1.0
    projeto.salvar_pagina(0, boxes)
    assert projeto.carregar_pagina(0) == boxes
    assert projeto.carregar_pagina(1) is None
    assert projeto.paginas_lidas() == [0]


def test_sem_padroes_nem_rede_tudo_vai_para_a_revisao(projeto, leitor):
    imagem = pg.FonteDePaginas(projeto.fonte).pagina(0)
    boxes = pg.segmentar(imagem)
    resumo = pg.ler_boxes(imagem, boxes, leitor)
    assert resumo.boxes == len(boxes) >= 15
    assert resumo.pendentes == len(boxes)


def test_ensinar_uma_letra_resolve_as_repeticoes_dela(projeto, leitor):
    imagem = pg.FonteDePaginas(projeto.fonte).pagina(0)
    boxes = pg.segmentar(imagem)
    pg.ler_boxes(imagem, boxes, leitor)

    # Os boxes vêm em ordem de leitura e espaço não é box: a, b, c, a, b, c...
    resolvidos = pg.ensinar(imagem, boxes, 0, "a", leitor, projeto, pagina=0)

    assert boxes[0].source == FONTE_MANUAL
    lidos_como_a = [b for b in boxes if b.char == "a" and b.source == FONTE_LIVRO]
    # Há cinco "a" na página; um foi ensinado e os outros quatro saem do padrão.
    assert len(lidos_como_a) == 4
    assert resolvidos == 4


def test_o_padrao_ensinado_vale_em_outra_sessao(projeto, leitor):
    imagem = pg.FonteDePaginas(projeto.fonte).pagina(0)
    boxes = pg.segmentar(imagem)
    pg.ensinar(imagem, boxes, 1, "b", leitor, projeto, pagina=0, propagar=False)

    novo = LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)
    leitura = novo.ler(pg.recorte(imagem, boxes[4]))  # o "b" do segundo "abc"
    assert (leitura.char, leitura.fonte) == ("b", FONTE_LIVRO)


def test_esquecer_tira_o_padrao_da_leitura(projeto, leitor):
    imagem = pg.FonteDePaginas(projeto.fonte).pagina(0)
    boxes = pg.segmentar(imagem)
    pg.ensinar(imagem, boxes, 2, "c", leitor, projeto, pagina=0, propagar=False)
    [arquivo] = leitor.padroes_por_caractere()["c"]

    leitor.esquecer(arquivo)

    assert "c" not in leitor.padroes_por_caractere()
    assert leitor.ler(pg.recorte(imagem, boxes[5])).fonte != FONTE_LIVRO  # o "c" do segundo "abc"


def test_esquecer_recusa_arquivo_de_fora(leitor, tmp_path):
    intruso = tmp_path / "x.png"
    intruso.write_bytes(b"")
    with pytest.raises(ValueError):
        leitor.esquecer(intruso)


def test_padroes_de_um_livro_nao_valem_em_outro(projeto, leitor, tmp_path):
    imagem = pg.FonteDePaginas(projeto.fonte).pagina(0)
    boxes = pg.segmentar(imagem)
    pg.ensinar(imagem, boxes, 0, "a", leitor, projeto, pagina=0, propagar=False)

    outro = ProjetoDeLivro.criar(tmp_path / "livros", "Outro livro", projeto.fonte)
    leitor_do_outro = LeitorDoLivro(outro.pasta_de_padroes)
    assert leitor_do_outro.total_de_padroes == 0
    assert leitor_do_outro.ler(pg.recorte(imagem, boxes[3])).fonte != FONTE_LIVRO  # outro "a"


def test_fila_poe_o_menos_confiavel_primeiro(leitor):
    from core.box_model import BoxEntry

    boxes = [BoxEntry("a", 0, 0, 5, 5, 0.85, "neural"),
             BoxEntry("", 10, 0, 15, 5, 0.0, "none"),
             BoxEntry("b", 20, 0, 25, 5, 0.95, "neural"),
             BoxEntry("c", 30, 0, 35, 5, 1.0, FONTE_MANUAL)]
    assert pg.fila_de_revisao(boxes, leitor) == [1, 0]


def test_box_manual_nao_e_relido(projeto, leitor):
    imagem = pg.FonteDePaginas(projeto.fonte).pagina(0)
    boxes = pg.segmentar(imagem)
    pg.confirmar(boxes, 0, "Z")
    pg.ler_boxes(imagem, boxes, leitor)
    assert (boxes[0].char, boxes[0].source) == ("Z", FONTE_MANUAL)


def test_tabuleiros_gravados_voltam_com_a_pagina(projeto):
    from core.box_model import BoxEntry

    boxes = [BoxEntry("a", 0, 0, 5, 5, 1.0, FONTE_MANUAL)]
    projeto.salvar_pagina(0, boxes, [(10, 20, 410, 420)])
    assert projeto.carregar_tabuleiros(0) == [(10, 20, 410, 420)]
    assert projeto.carregar_tabuleiros(1) == []


_DARCY = sorted(Path("C:/Python-Chess2/PyBoxEditor_Tkinter/PDF").glob("Darcy*/Darcy*.pdf"))


@pytest.mark.skipif(not _DARCY, reason="o PDF do Darcy Lima não está nesta máquina")
def test_diagrama_sem_moldura_sai_do_texto():
    """A p. 26 do Darcy Lima tem três diagramas sem moldura fechada."""
    imagem = pg.FonteDePaginas(_DARCY[0]).pagina(25)
    segmentada = pg.segmentar_pagina(imagem)
    assert len(segmentada.tabuleiros) == 3
    for x1, y1, x2, y2 in segmentada.tabuleiros:
        assert not [b for b in segmentada.boxes
                    if x1 <= (b.x1 + b.x2) / 2 <= x2 and y1 <= (b.y1 + b.y2) / 2 <= y2]


def test_ensinar_o_minusculo_nao_le_o_maiusculo(tmp_path):
    """O recorte de 32x32 apaga o tamanho; a altura gravada no padrão o devolve."""
    fonte = _pagina_sintetica(tmp_path / "p.png", linhas=("oo OO oo OO",))
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Caixa", fonte)
    leitor = LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)
    imagem = pg.FonteDePaginas(projeto.fonte).pagina(0)
    boxes = pg.segmentar(imagem)
    pg.ler_boxes(imagem, boxes, leitor)

    pg.ensinar(imagem, boxes, 0, "o", leitor, projeto, pagina=0)

    assert [b.char for b in boxes] == ["o", "o", "", "", "o", "o", "", ""]
    assert all(b.source == FONTE_LIVRO for b in boxes[1:2] + boxes[4:6])


def test_propagar_usa_so_os_padroes_do_livro(projeto, leitor):
    """A propagação não chama a cadeia global: um padrão novo só muda o livro."""
    imagem = pg.FonteDePaginas(projeto.fonte).pagina(0)
    boxes = pg.segmentar(imagem)

    class CadeiaQueNaoPodeSerChamada:
        def fallback_chain_detalhado(self, *a, **k):
            raise AssertionError("a propagação chamou a cadeia global")

    leitor.ocr = CadeiaQueNaoPodeSerChamada()
    resolvidos = pg.ensinar(imagem, boxes, 0, "a", leitor, projeto, pagina=0)
    assert resolvidos == 4


def test_o_hifen_ensinado_nao_le_o_ponto(tmp_path):
    """Esticados para 32x32, o hífen e o ponto viram o mesmo quadrado preto.

    A proporção do recorte, que o arquivo do padrão guarda, os separa. É o que
    o Xadrez Vitorioso mostrou: o hífen ensinado na p. 26 lia os pontos das
    páginas seguintes.
    """
    import numpy as np

    from abbychess.padroes import PadroesDoLivro

    def mancha(largura, altura):
        recorte = np.full((altura + 4, largura + 4), 255, np.uint8)
        recorte[2:-2, 2:-2] = 0
        return recorte

    padroes = PadroesDoLivro(tmp_path / "padroes")
    padroes.ensinar(mancha(12, 4), "-")
    assert padroes.ler(mancha(13, 5)).char == "-"
    assert padroes.ler(mancha(6, 6)).char == ""
    assert padroes.ler(mancha(27, 5)).char == ""

    padroes.ensinar(mancha(7, 7), ".")
    # Numa sessão nova, a proporção sai do PNG gravado.
    relido = PadroesDoLivro(tmp_path / "padroes")
    assert relido.ler(mancha(6, 6)).char == "."
    assert relido.ler(mancha(11, 4)).char == "-"
