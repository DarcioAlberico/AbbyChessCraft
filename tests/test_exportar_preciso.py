"""A exportação precisa: o que a conversão do Odds & Ends (Quality Chess, 2012) mostrou.

Cada teste é um defeito do EPUB exportado das páginas 1, 6, 7 e 8:

- as duas colunas saíam misturadas linha a linha (`isfantastic:16...d3`), e o
  diagrama da coluna da esquerda caía entre os parágrafos da direita;
- o `o` ensinado como `O` lia o livro inteiro com `abOut` e `LOndOn`;
- as coordenadas do tabuleiro entravam no texto (`476542 a b c d e f g h`);
- a última linha da coluna, `13.♕b3 0–0–0`, saía como rodapé pelo `13`;
- o livro em inglês saía com `dc:language` `pt-BR`;
- e, no PDF nascido digital, nada disso precisava de OCR: a página sai da
  camada de texto, com o lado a jogar do diagrama pelo lance de antes dele.
"""

from __future__ import annotations

import zipfile

import pytest
from PIL import Image

from core.box_model import BoxEntry

from abbychess import exportar as ex
from abbychess import margens as mg
from abbychess import montagem as mo
from abbychess import texto as tx
from abbychess.leitor import FONTE_LIVRO, FONTE_MANUAL, FONTE_NATIVA
from abbychess.modelo import Box, Pagina
from abbychess.projeto import ProjetoDeLivro
from tests.ajudantes import _pdf_digital  # noqa: E402,F401,F811


def _linha(texto, y, x=300, altura=50, largura=30, alturas=None, fonte=FONTE_MANUAL):
    """Uma linha de boxes; `alturas` dá a altura de cada letra (senão, `altura`)."""
    saida = []
    for i, c in enumerate(texto):
        if c == " ":
            continue
        h = (alturas or {}).get(c, altura)
        saida.append(BoxEntry(c, x + largura * i, y + altura - h, x + largura * i + largura - 5,
                              y + altura, 1.0, fonte))
    return saida


def _texto(boxes):
    return " ".join(t for linha in mo.palavras(boxes) for t, _ in linha)


# ----------------------------------------------------------------------
# A caixa pela altura
# ----------------------------------------------------------------------

#: Altura-x 19, maiúscula 31: as medidas da p. 6 do Odds & Ends.
ALTURAS = {**{c: 19 for c in "aemnruocsvwxzOCSVWXZ"}, **{c: 31 for c in "bdfhklABDTL"}}


def test_o_maiusculo_da_altura_do_x_vira_minusculo():
    assert _texto(_linha("hOnestly abOut LOndOn", 100, alturas=ALTURAS, fonte=FONTE_LIVRO)) == \
        "honestly about London"


def test_a_maiuscula_de_verdade_fica():
    alturas = {**ALTURAS, "C": 31, "O": 31}
    assert _texto(_linha("Chess Open", 100, alturas=alturas, fonte=FONTE_LIVRO)) == "Chess Open"


def test_sem_regua_de_maiuscula_so_a_minuscula_se_prova():
    assert _texto(_linha("tO sOme", 100, alturas={**ALTURAS, "t": 21},
                         fonte=FONTE_LIVRO)) == "to some"


#: A caixa que engoliu tinta: o `v` e o `x` da altura das maiúsculas (Xadrez Vitorioso p. 26).
CAIXAS_ALTAS = {**ALTURAS, **{c: 31 for c in "cvwx"}}


def test_a_letra_alta_no_meio_da_palavra_nao_sobe():
    """`eVitar`, `ObViamente`, `próXimo`: 15 das 23 subidas medidas erram, todas no meio."""
    assert _texto(_linha("evitar existir bad", 100, alturas=CAIXAS_ALTAS, fonte=FONTE_LIVRO)) == \
        "evitar existir bad"


@pytest.mark.parametrize("lida, certa", [("white bad", "White bad"), ("(white bad", "(White bad")])
def test_a_primeira_letra_alta_sobe(lida, certa):
    assert _texto(_linha(lida, 100, alturas=CAIXAS_ALTAS, fonte=FONTE_LIVRO)) == certa


@pytest.mark.parametrize("lance", ["1.c4", "♖c4"])
def test_depois_do_numero_ou_da_figurina_nao_sobe(lance):
    assert _texto(_linha(f"{lance} bad", 100, alturas=CAIXAS_ALTAS, fonte=FONTE_LIVRO)) == \
        f"{lance} bad"


@pytest.mark.parametrize("fonte", [FONTE_MANUAL, FONTE_NATIVA])
def test_a_altura_nao_troca_a_letra_confirmada_nem_a_nativa(fonte):
    assert _texto(_linha("abOut bad", 100, alturas=ALTURAS, fonte=fonte)) == "abOut bad"


def test_a_altura_nao_troca_a_letra_revisada():
    """Visto e aceito no Documento: o `O` de `abOut` fica; o outro, que ninguém viu, desce."""
    boxes = _linha("abOut hOnest bad", 100, alturas=ALTURAS, fonte=FONTE_LIVRO)
    revisado = next(i for i, b in enumerate(boxes) if b.char == "O")
    pagina = Pagina(1, 0, boxes=[Box(i, e, revisado=i == revisado) for i, e in enumerate(boxes)],
                    proximo_n=len(boxes))
    entries, estrutura = mo.Estrutura.da_pagina(pagina)
    [paragrafo] = mo.pagina_extraida(0, entries, estrutura=estrutura).blocos
    assert paragrafo.texto == "abOut honest bad"


# ----------------------------------------------------------------------
# Coordenadas, rodapé e colunas
# ----------------------------------------------------------------------

#: Um tabuleiro de 400 px (casa de 50) em (1000, 1000).
TABULEIRO = (1000, 1000, 1400, 1400)


def test_as_coordenadas_do_tabuleiro_saem_do_texto():
    numeros = [BoxEntry(str(8 - k), 965, 1010 + 50 * k, 985, 1040, 1.0, FONTE_MANUAL)
               for k in range(8)]
    letras = [BoxEntry("abcdefgh"[k], 1015 + 50 * k, 1410, 1035, 1440, 1.0, FONTE_MANUAL)
              for k in range(8)]
    acima = _linha("9.e4 Qh5", 940, x=1000, altura=40)
    assert mo._sem_coordenadas(numeros + letras + acima, [TABULEIRO]) == acima
    # Sem coordenadas impressas, a legenda colada embaixo do tabuleiro, com
    # letras de `a` a `h` e números, fica inteira.
    legenda = _linha("1-40 Branco joga", 1405, x=1000, altura=30, largura=22)
    assert mo._sem_coordenadas(legenda, [TABULEIRO]) == legenda


def test_linha_de_lances_no_pe_da_pagina_nao_e_rodape():
    corpo = [b for k in range(6) for b in _linha(FRASES[k], 400 + 60 * k)]
    # A contraprova: no mesmo lugar, o rodapé com o número da página sai.
    rodape = _linha("22 YASSER SEIRAWAN", 3300)
    assert mg.margens_corridas({0: (corpo + rodape, 3500)})[0]
    lances = _linha("13.Qb3 0-0-0", 3300)
    assert not mg.margens_corridas({0: (corpo + lances, 3500)})[0]


#: Linhas de tamanhos diferentes: com o mesmo texto em todas, os espaços se
#: alinhariam e virariam calhas.
FRASES = ("as brancas jogam e ganham", "um lance muito ruim", "o plano consiste em atacar",
          "e a dama sob ataque", "trocar pecas num momento bom", "evitar golpes baratos")


def _duas_colunas(titulo=""):
    """Doze linhas em cada coluna, na mesma altura; a da direita em maiúsculas."""
    boxes = []
    if titulo:
        boxes += _linha(titulo, 120, x=900, altura=90, largura=70)
    for k in range(12):
        y = 300 + 60 * k
        boxes += _linha(f"{FRASES[k % 6]} {k:02d}", y, x=200, largura=25)
        boxes += _linha(f"{FRASES[(k + 3) % 6].upper()} {k:02d}", y, x=1300, largura=25)
    return boxes


def _lado_a_lado(esquerda, direita, vao_em_alturas, y=3300):
    """Duas frases na mesma altura, a da direita a `vao_em_alturas` alturas de letra (50)."""
    boxes = _linha(esquerda, y, x=200)
    fim = max(b.x2 for b in boxes)
    return boxes + _linha(direita, y, x=fim + int(vao_em_alturas * 50))


def test_as_legendas_lado_a_lado_sao_duas_linhas():
    """Xadrez Vitorioso p. 25: as legendas dos dois diagramas saíam numa frase só."""
    boxes = _lado_a_lado("Diagrama 6. Jogam as brancas.", "Diagrama 7. Jogam as brancas.", 10.5)
    assert [" ".join(t for t, _ in linha) for linha in mo.palavras(boxes)] == [
        "Diagrama 6. Jogam as brancas.", "Diagrama 7. Jogam as brancas."]

    pagina = Pagina(1, 0, boxes=[Box(i, e) for i, e in enumerate(boxes)], proximo_n=len(boxes))
    assert tx.texto(tx.montar(pagina)).splitlines() == [
        "Diagrama 6. Jogam as brancas.", "Diagrama 7. Jogam as brancas."]


@pytest.mark.parametrize("esquerda, direita, vao", [
    ("32. ... b2xa2 c3 d4", "Tb2xa2 Rg8 Th8", 6.3),       # a tabela de lances: vão menor
    ("Capitulo um", "Diagrama 7. Jogam as brancas.", 12),  # só duas palavras de um lado
])
def test_o_vao_que_nao_parte_a_linha(esquerda, direita, vao):
    assert len(mo.palavras(_lado_a_lado(esquerda, direita, vao))) == 1


def test_as_colunas_nao_se_misturam_na_linha():
    textos = [b.texto for b in mo.paragrafos(_duas_colunas())]
    juntos = " ".join(textos)
    assert not any(t != t.upper() and t != t.lower() for t in textos)
    assert juntos.index(f"{FRASES[5]} 11") < juntos.index(f"{FRASES[3].upper()} 00")


def test_o_titulo_que_atravessa_a_calha_vem_primeiro():
    textos = [b.texto for b in mo.paragrafos(_duas_colunas(titulo="Games"))]
    assert textos[0] == "Games"


def test_o_documento_tambem_le_uma_coluna_inteira_antes_da_seguinte():
    entries = _duas_colunas(titulo="Games")
    pagina = Pagina(1, 0, boxes=[Box(i, entry) for i, entry in enumerate(entries)],
                    proximo_n=len(entries))

    linhas = tx.texto(tx.montar(pagina)).splitlines()

    assert linhas[0] == "Games"
    assert not any(linha != linha.upper() and linha != linha.lower() for linha in linhas[1:])
    assert "as brancas jogam e ganham 00" in linhas[1]
    assert linhas.index(f"{FRASES[5]} 11") < linhas.index(f"{FRASES[3].upper()} 00")


def _contar_deteccoes(monkeypatch, refazer=False):
    """Conta as detecções de colunas do core; com `refazer`, a ordenação ignora a detecção
    que recebe (como antes de ela ser reaproveitada)."""
    from core.services.box_service import BoxService

    chamadas = []
    detectar = BoxService._colunas_e_transversais
    ordenar = BoxService.sort_boxes_reading_order

    def contando(*a, **k):
        chamadas.append(1)
        return detectar(*a, **k)

    monkeypatch.setattr(BoxService, "_colunas_e_transversais", staticmethod(contando))
    if refazer:
        monkeypatch.setattr(BoxService, "sort_boxes_reading_order",
                            staticmethod(lambda boxes, _deteccao=None: ordenar(boxes)))
    return chamadas


@pytest.mark.parametrize("saida", ["documento", "exportacao"])
def test_a_pagina_de_uma_coluna_detecta_as_colunas_uma_vez(monkeypatch, saida):
    """O índice da busca monta o texto de todas as páginas: a detecção das colunas é a parte
    mais cara, e a página de um trecho só a fazia duas vezes (a ordem de leitura e o core),
    o que pôs o índice pela janela em 2,4 s no portão do passo L."""
    entries = [b for k in range(12) for b in _linha(f"{FRASES[k % 6]} {k:02d}", 300 + 60 * k)]

    def montar():
        if saida == "documento":
            tx._LINHAS_VISTAS.clear()              # as linhas guardadas pulariam a detecção
            return tx.texto(tx.montar(tx.pagina_avulsa(entries)))
        return [p.texto for p in mo.paragrafos(entries)]

    with monkeypatch.context() as m:
        refeitas = _contar_deteccoes(m, refazer=True)
        antes = montar()
    chamadas = _contar_deteccoes(monkeypatch)
    assert montar() == antes
    assert (len(refeitas), len(chamadas)) == (2, 1)


# ----------------------------------------------------------------------
# A camada de texto do PDF nascido digital
# ----------------------------------------------------------------------


def _projeto_digital(tmp_path):
    pdf = _pdf_digital(tmp_path / "livro.pdf")
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Digital", pdf)
    # Os boxes que o OCR gravou dizem outra coisa: é a camada que tem de sair.
    projeto.salvar_pagina(0, _linha("lixo do ocr", 300, fonte=FONTE_LIVRO))
    return projeto


def test_a_pagina_digital_sai_da_camada_de_texto(tmp_path):
    projeto = _projeto_digital(tmp_path)
    [pagina] = ex.paginas_do_projeto(projeto, None)
    texto = " ".join(b.texto for b in pagina.blocos if isinstance(b, ex.Paragrafo))
    assert getattr(pagina, "leitura", "") == "camada"
    assert "The knight on d5 is strong" in texto and "lixo" not in texto


def test_sem_a_camada_a_pagina_sai_dos_boxes(tmp_path):
    projeto = _projeto_digital(tmp_path)
    [pagina] = ex.paginas_do_projeto(projeto, None, camada="nunca")
    texto = " ".join(b.texto for b in pagina.blocos if isinstance(b, ex.Paragrafo))
    assert "lixo" in texto


def test_a_pagina_digitalizada_continua_nos_boxes(tmp_path):
    imagem = tmp_path / "pagina.png"
    Image.new("L", (2480, 3500), 255).save(imagem)
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Imagem", imagem)
    projeto.salvar_pagina(0, _linha("texto lido", 300))
    [pagina] = ex.paginas_do_projeto(projeto, None)
    assert "texto lido" in pagina.blocos[0].texto


def test_o_epub_leva_o_idioma_do_livro(tmp_path):
    projeto = _projeto_digital(tmp_path)
    assert projeto.dados.idioma == "pt"
    destino = tmp_path / "livro.epub"
    resumo = ex.exportar(projeto, destino)
    with zipfile.ZipFile(destino) as z:
        opf = z.read("OEBPS/content.opf").decode("utf-8")
    assert "<dc:language>en</dc:language>" in opf
    assert "1 página(s) lida(s) da camada de texto do PDF" in resumo
    assert "as margens que o core tira delas não são listadas" in resumo


#: Prosa nos idiomas que o projeto oferece fora do português e do inglês (SPEC-qualidade §13.7).
PROSA = {
    "es": "El rey de las blancas se mueve y las negras no tienen jugada, pero el peón que está "
          "en la columna del alfil es más fuerte y lo que importa es la casilla de al lado",
    "de": "Der König und der Turm stehen auf dem Feld, aber Schwarz ist nicht am Zug und auch "
          "die Dame wird nach dem Tausch mit einer Figur von der Grundreihe nicht besser",
    "fr": "Le roi et les pions des blancs sont dans une position qui est forte, mais les noirs "
          "ont pour eux le coup du cavalier avec une menace sur la case et pas plus",
}


@pytest.mark.parametrize("codigo", PROSA)
def test_o_epub_leva_o_idioma_do_livro_fora_do_portugues_e_do_ingles(tmp_path, codigo):
    """O detector do core só conhece pt e en: sem resposta dele, valia o "pt" com que o projeto
    nasce, e o livro saía `pt-BR` (SPEC-qualidade §13.7)."""
    import fitz

    doc = fitz.open()
    pagina = doc.new_page(width=600, height=800)
    for k in range(6):
        pagina.insert_textbox((40, 40 + 100 * k, 560, 130 + 100 * k), PROSA[codigo],
                              fontname="helv", fontsize=10)
    doc.save(tmp_path / "livro.pdf")
    doc.close()
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Digital", tmp_path / "livro.pdf")
    projeto.salvar_pagina(0, _linha("lixo do ocr", 300))
    destino = tmp_path / "livro.epub"
    ex.exportar(projeto, destino)
    with zipfile.ZipFile(destino) as z:
        opf = z.read("OEBPS/content.opf").decode("utf-8")
    assert f"<dc:language>{codigo}</dc:language>" in opf


#: O diagrama 1-7 do Dvoretsky, e onde ele fica na página do PDF (em pontos).
FEN_DO_DIAGRAMA = "8/1k6/1p6/1K6/P1P5/8/8/8"
X_DO_DIAGRAMA, Y_DO_DIAGRAMA, CASA = 220, 200, 20


def _pdf_com_diagrama(caminho):
    """Uma página nascida digital: prosa em Helvetica e o diagrama composto na ChessMerida do
    PyBoxEditor, uma casa por glifo (como o `core.pdf_nativo` o lê)."""
    import fitz

    from core import render_diagrama

    fonte = render_diagrama.carregar("ChessMerida-Diagram")
    doc = fitz.open()
    p = doc.new_page(width=600, height=800)
    p.insert_text((200, 60), "Chapter 1 Pawn Endgames", fontname="hebo", fontsize=16)
    for k, linha in enumerate(["White has the opposition, but it is not enough",
                               "to win, and the whole ending turns on that."]):
        p.insert_text((60, 100 + 12 * k), linha, fontname="helv", fontsize=10)
    for k, linha in enumerate(render_diagrama.linhas(FEN_DO_DIAGRAMA, fonte, "branca")):
        p.insert_text((X_DO_DIAGRAMA, Y_DO_DIAGRAMA + (k + 1) * CASA), linha,
                      fontfile=fonte.arquivo, fontname="merida", fontsize=CASA)
    for k, linha in enumerate(["Since 2.c5 would be useless, the king starts an",
                               "outflanking maneuver."]):
        p.insert_text((60, 500 + 12 * k), linha, fontname="helv", fontsize=10)
    doc.save(caminho)
    doc.close()
    return caminho


@pytest.mark.parametrize("conferido, lado, esperado", [
    (True, "b", "b"),                    # o lado conferido na revisão vale sobre o da camada
    (False, "b", "w"),                   # o lido e não conferido, não
    (True, None, "w"),                   # conferido sem lado escolhido: fica o da camada
])
def test_o_lado_conferido_na_revisao_vai_ao_diagrama_da_camada(tmp_path, conferido, lado,
                                                               esperado):
    from tests.ajudantes import _lido

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Digital",
                                   _pdf_com_diagrama(tmp_path / "livro.pdf"))
    escala = 300 / 72                                     # a página lida, a 300 dpi
    caixa = tuple(round(v * escala) for v in (X_DO_DIAGRAMA, Y_DO_DIAGRAMA,
                                              X_DO_DIAGRAMA + 8 * CASA, Y_DO_DIAGRAMA + 8 * CASA))
    pagina = projeto.pagina_para_editar(0)
    pagina.diagramas = [_lido(FEN_DO_DIAGRAMA, caixa=caixa, conferido=conferido, lado=lado)]
    projeto.salvar_modelo(pagina)
    [figura] = [b for b in ex.paginas_da_camada(projeto, [0])[0].blocos
                if isinstance(b, ex.Figura)]
    assert figura.fen.split()[:2] == [FEN_DO_DIAGRAMA, esperado]


def test_o_idioma_do_livro_e_lido_uma_vez_por_exportacao(tmp_path, monkeypatch):
    """O idioma pela camada do PDF abre o livro: a exportação e a prévia o pedem uma vez, e a
    camada de texto e os metadados levam o mesmo (SPEC-qualidade Q-E5, Q-E6)."""
    from abbychess import idioma as idm

    projeto = _projeto_digital(tmp_path)
    pedidos = []
    original = idm.da_camada_do_pdf
    monkeypatch.setattr(idm, "da_camada_do_pdf",
                        lambda *a, **k: pedidos.append(1) or original(*a, **k))
    ex.exportar(projeto, tmp_path / "livro.epub")
    assert len(pedidos) == 1
    pedidos.clear()
    ex.previa(projeto, "docx")
    assert len(pedidos) == 1


def test_o_idioma_do_arquivo():
    from abbychess import pedido

    assert pedido.idioma_do_arquivo("pt") == "pt-BR"
    assert pedido.idioma_do_arquivo("en") == "en"


def test_a_captura_sai_em_minuscula():
    assert mo._captura_minuscula("♖Xf2!") == "♖xf2!"
    assert mo._captura_minuscula("eXd5") == "exd5"
    assert mo._captura_minuscula("XIIIIIY") == "XIIIIIY"


def _com_lacunas(*partes, y=3300):
    """Uma linha de boxes de largura 16, como a p. 15 do Aagaard: cada parte é `(texto,
    lacuna antes)`, e dentro da parte as letras ficam a 2 px umas das outras."""
    boxes, x = [], 200
    for texto, antes in partes:
        x += antes
        for c in texto:
            boxes.append(BoxEntry(c, x, y, x + 16, y + 25, 1.0, FONTE_MANUAL))
            x += 18
        x -= 2
    return boxes


#: Três "f" dentro da palavra, com o gancho sobre a letra seguinte (-3): o mínimo para o
#: gancho valer (`layout.AMOSTRAS_DO_GANCHO`).
_COM_GANCHO = (("af", 20), ("ter", -3), ("f", 20), ("or", -3), ("f", 20), ("ar", -3))


def test_o_espaco_depois_do_f_com_gancho():
    """O gancho do "f" passa da haste, e a lacuna até a palavra seguinte cai a 5–8 px,
    abaixo do limiar do core (8): "Depth ofthe analysis". Dentro da palavra, o gancho
    cobre a letra seguinte ("after", -3)."""
    boxes = _com_lacunas(("Depth", 0), ("of", 20), ("the", 6), *_COM_GANCHO,
                         ("of", 20), ("exercises", 5))
    assert _texto(boxes) == "Depth of the after for far of exercises"

    pagina = Pagina(1, 0, boxes=[Box(i, e) for i, e in enumerate(boxes)], proximo_n=len(boxes))
    assert tx.texto(tx.montar(pagina)) == "Depth of the after for far of exercises"


def test_o_f_sem_gancho_continua_na_palavra():
    """Numa fonte sem gancho, o "f" fica à lacuna comum da palavra (2 px)."""
    assert _texto(_com_lacunas(("af", 0), ("ter", 2), ("of", 20), ("fer", 2))) == "after offer"


def test_o_gancho_de_uma_amostra_so_nao_vale():
    """Na p. 1045 do Yusupov uma amostra só (-4) dava um gancho de 7 px."""
    boxes = _com_lacunas(("Depth", 0), ("of", 20), ("the", 6), ("af", 20), ("ter", -3))
    assert _texto(boxes) == "Depth ofthe after"


def test_o_box_sem_leitura_depois_do_f_nao_parte_a_palavra():
    """"fo|llowed" com o "o" sem leitura: o core não o faz símbolo, mas mede a lacuna por
    ele, e a palavra fica como ele a fez."""
    from dataclasses import replace

    boxes = _com_lacunas(*_COM_GANCHO, ("of", 20), ("the", 6), ("fo", 20), ("llowed", 2))
    o = max(i for i, b in enumerate(boxes) if b.char == "o" and boxes[i - 1].char == "f")
    boxes[o] = replace(boxes[o], char="")
    assert _texto(boxes) == "after for far of the fllowed"
