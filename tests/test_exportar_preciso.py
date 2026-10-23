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

import fitz
import pytest
from PIL import Image

from core.box_model import BoxEntry

from abbychess import exportar as ex
from abbychess import texto as tx
from abbychess.leitor import FONTE_MANUAL
from abbychess.modelo import Box, Pagina
from abbychess.projeto import ProjetoDeLivro


def _linha(texto, y, x=300, altura=50, largura=30, alturas=None):
    """Uma linha de boxes; `alturas` dá a altura de cada letra (senão, `altura`)."""
    saida = []
    for i, c in enumerate(texto):
        if c == " ":
            continue
        h = (alturas or {}).get(c, altura)
        saida.append(BoxEntry(c, x + largura * i, y + altura - h, x + largura * i + largura - 5,
                              y + altura, 1.0, FONTE_MANUAL))
    return saida


def _texto(boxes):
    return " ".join(t for linha in ex.palavras(boxes) for t, _ in linha)


# ----------------------------------------------------------------------
# A caixa pela altura
# ----------------------------------------------------------------------

#: Altura-x 19, maiúscula 31: as medidas da p. 6 do Odds & Ends.
ALTURAS = {**{c: 19 for c in "aemnruocsvwxzOCSVWXZ"}, **{c: 31 for c in "bdfhklABDTL"}}


def test_o_maiusculo_da_altura_do_x_vira_minusculo():
    assert _texto(_linha("hOnestly abOut LOndOn", 100, alturas=ALTURAS)) == \
        "honestly about London"


def test_a_maiuscula_de_verdade_fica():
    alturas = {**ALTURAS, "C": 31, "O": 31}
    assert _texto(_linha("Chess Open", 100, alturas=alturas)) == "Chess Open"


def test_sem_regua_de_maiuscula_so_a_minuscula_se_prova():
    assert _texto(_linha("tO sOme", 100, alturas={**ALTURAS, "t": 21})) == "to some"


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
    assert ex._sem_coordenadas(numeros + letras + acima, [TABULEIRO]) == acima
    # Sem coordenadas impressas, a legenda colada embaixo do tabuleiro, com
    # letras de `a` a `h` e números, fica inteira.
    legenda = _linha("1-40 Branco joga", 1405, x=1000, altura=30, largura=22)
    assert ex._sem_coordenadas(legenda, [TABULEIRO]) == legenda


def test_linha_de_lances_no_pe_da_pagina_nao_e_rodape():
    corpo = [b for k in range(6) for b in _linha(FRASES[k], 400 + 60 * k)]
    # A contraprova: no mesmo lugar, o rodapé com o número da página sai.
    rodape = _linha("22 YASSER SEIRAWAN", 3300)
    assert ex.margens_corridas({0: (corpo + rodape, 3500)})[0]
    lances = _linha("13.Qb3 0-0-0", 3300)
    assert not ex.margens_corridas({0: (corpo + lances, 3500)})[0]


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


def test_as_colunas_nao_se_misturam_na_linha():
    textos = [b.texto for b in ex.paragrafos(_duas_colunas())]
    juntos = " ".join(textos)
    assert not any(t != t.upper() and t != t.lower() for t in textos)
    assert juntos.index(f"{FRASES[5]} 11") < juntos.index(f"{FRASES[3].upper()} 00")


def test_o_titulo_que_atravessa_a_calha_vem_primeiro():
    textos = [b.texto for b in ex.paragrafos(_duas_colunas(titulo="Games"))]
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
            return tx.texto(tx.montar(tx.pagina_avulsa(entries)))
        return [p.texto for p in ex.paragrafos(entries)]

    with monkeypatch.context() as m:
        refeitas = _contar_deteccoes(m, refazer=True)
        antes = montar()
    chamadas = _contar_deteccoes(monkeypatch)
    assert montar() == antes
    assert (len(refeitas), len(chamadas)) == (2, 1)


# ----------------------------------------------------------------------
# A camada de texto do PDF nascido digital
# ----------------------------------------------------------------------

PROSA = ("The knight on d5 is strong and the bishop has no square. It is not easy for "
         "Black to defend the king, and White has a clear plan after the exchange of the "
         "queens on the long diagonal of the board.")


def _pdf_digital(caminho, paginas=2):
    doc = fitz.open()
    for numero in range(paginas):
        p = doc.new_page(width=480, height=680)
        p.insert_text((40, 60), f"Chapter {numero + 1}", fontname="hebo", fontsize=18)
        palavras = (PROSA + " " + PROSA).split()
        for k in range(0, len(palavras), 8):
            p.insert_text((40, 100 + 14 * (k // 8)), " ".join(palavras[k:k + 8]),
                          fontname="helv", fontsize=11)
    doc.save(caminho)
    doc.close()
    return caminho


def _projeto_digital(tmp_path):
    pdf = _pdf_digital(tmp_path / "livro.pdf")
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Digital", pdf)
    # Os boxes que o OCR gravou dizem outra coisa: é a camada que tem de sair.
    projeto.salvar_pagina(0, _linha("lixo do ocr", 300))
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


def test_o_idioma_do_arquivo():
    assert ex.idioma_do_arquivo("pt") == "pt-BR"
    assert ex.idioma_do_arquivo("en") == "en"


def test_a_captura_sai_em_minuscula():
    assert ex._captura_minuscula("♖Xf2!") == "♖xf2!"
    assert ex._captura_minuscula("eXd5") == "exd5"
    assert ex._captura_minuscula("XIIIIIY") == "XIIIIIY"
