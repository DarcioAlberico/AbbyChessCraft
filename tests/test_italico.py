"""O itálico medido no OCR (pendência do passo I): a inclinação das bordas das letras de cada
palavra contra a das palavras retas da página (`pagina._italicos`)."""

from __future__ import annotations

import fitz
import numpy as np
import pytest
from PIL import Image

from abbychess import pagina as pg
from abbychess import servidor_de_leitura as sl
from abbychess.modelo import Estilo
from core.box_model import BoxEntry

FRASE = "The quick brown fox jumps over the lazy dog and runs home"


def _pdf(caminho, linhas):
    """Um PDF de uma página com `(texto, fonte)` por linha (as fontes base do PDF)."""
    doc = fitz.open()
    pagina = doc.new_page(width=420, height=60 + 22 * len(linhas))
    for k, (texto, fonte) in enumerate(linhas):
        pagina.insert_text((24, 40 + 22 * k), texto, fontname=fonte, fontsize=13)
    doc.save(caminho)
    doc.close()
    return caminho


def _efeitos_por_linha(caminho, n_linhas):
    imagem = pg.FonteDePaginas(caminho).pagina(0)
    boxes = pg.segmentar(imagem)
    for b in boxes:
        b.char = "a"                     # as palavras e a medida só pedem que seja letra
    _negritos, italicos = pg.efeitos_da_pagina(imagem, boxes)
    altura = imagem.height / (60 + 22 * n_linhas)
    linhas = [[] for _ in range(n_linhas)]
    for b, italico in zip(boxes, italicos):
        k = round(((b.y1 + b.y2) / 2 / altura - 40 + 6) / 22)
        if 0 <= k < n_linhas:
            linhas[k].append(italico)
    return linhas


def _fracao_italica(linha) -> float:
    conhecidos = [m for m in linha if m is not None]
    assert len(conhecidos) >= 0.8 * len(linha)
    return sum(conhecidos) / len(conhecidos)


def test_a_linha_em_italico_sai_italica_e_as_retas_nao(tmp_path):
    """Nenhuma palavra reta sai itálica (o falso itálico separa o glifo das amostras retas no
    k-NN); das itálicas, quase todas: "over", sem haste, sai reta em Times-Italic."""
    linhas = [(FRASE, "tiro"), (FRASE, "tiit"), (FRASE, "tiro"), (FRASE, "tiro")]
    medidas = _efeitos_por_linha(_pdf(tmp_path / "t.pdf", linhas), len(linhas))
    assert all(medidas)
    for k, (_texto, fonte) in enumerate(linhas):
        fracao = _fracao_italica(medidas[k])
        assert fracao >= 0.8 if fonte == "tiit" else fracao == 0.0, (k, medidas[k])


def test_a_pagina_quase_toda_em_italico_nao_puxa_a_referencia(tmp_path):
    """A referência é a das palavras retas: com uma linha reta só, as itálicas continuam
    itálicas (no Odds & Ends, a p. 643 é quase toda em itálico)."""
    linhas = [(FRASE, "tiit"), (FRASE, "tiit"), (FRASE, "tiro"), (FRASE, "tiit")]
    medidas = _efeitos_por_linha(_pdf(tmp_path / "t.pdf", linhas), len(linhas))
    assert [_fracao_italica(linha) >= 0.8 for linha in medidas] == [True, True, False, True]
    assert _fracao_italica(medidas[2]) == 0.0


@pytest.mark.parametrize("cisalhamento, esperado", [(0.0, 0), (0.2, 11), (0.3, 17), (-0.2, -11)])
def test_a_inclinacao_das_bordas_de_hastes_cisalhadas(cisalhamento, esperado):
    """Hastes verticais cisalhadas: o pico fica no ângulo do cisalhamento (atan 0,2 ≈ 11°).
    Desenhadas a 4× e reduzidas, com a borda suave de um render de verdade (a escada de um
    pixel tem as bordas todas verticais)."""
    grande = np.full((240, 480), 255, np.uint8)
    for x0 in range(80, 400, 64):
        for y in range(40, 200):
            x = int(round(x0 + cisalhamento * (120 - y)))
            grande[y, x:x + 16] = 0
    recorte = np.asarray(Image.fromarray(grande).resize((120, 60), Image.Resampling.BOX))
    medida = pg._inclinacao_das_bordas(recorte, np.ones_like(recorte, bool))
    assert medida is not None and abs(medida[0] - esperado) <= 2 and medida[1] >= 1.0


def test_algarismos_e_palavras_curtas_nao_tem_italico_medido():
    pagina = np.full((40, 200), 255, np.uint8)
    boxes = [BoxEntry(c, 10 + 12 * k, 10, 20 + 12 * k, 30) for k, c in enumerate("1234")]
    boxes += [BoxEntry(c, 120 + 12 * k, 10, 130 + 12 * k, 30) for k, c in enumerate("ab")]
    assert pg._italicos(pagina, boxes, [[0, 1, 2, 3], [4, 5]]) == [None] * 6


def test_o_estilo_da_pagina_lida_leva_o_italico():
    entradas = [BoxEntry("a", 0, 0, 5, 5) for _ in range(4)]
    lida = sl.PaginaLida(entradas, [None] * 4, [], None, [], negritos=[True, False, None, None],
                         italicos=[False, True, True, None])
    estilos = lida.estilos()
    assert [estilos.get(id(e)) for e in entradas] == [
        Estilo(True, False), Estilo(False, True), Estilo(None, True), None]
    # O servidor que não mede o itálico (o falso dos testes): o itálico fica não medido, e
    # o reto medido no negrito é reto (False), não desconhecido.
    so_negrito = sl.PaginaLida(entradas, [None] * 4, [], None, [], negritos=[True, None, False, None])
    assert [so_negrito.estilos().get(id(e)) for e in entradas] == [
        Estilo(negrito=True), None, Estilo(negrito=False), None]


def test_o_estilo_nao_medido_nao_vira_reto():
    """O box sem medida tem o efeito desconhecido (None), que o JSON guarda e devolve; o reto
    medido (False) também volta como reto, e o JSON de antes ([0, 0, 0]) é "não medido"."""
    from abbychess.modelo import SEM_ESTILO

    assert SEM_ESTILO.negrito is None and SEM_ESTILO.italico is None
    for estilo in (Estilo(), Estilo(False, None), Estilo(None, False), Estilo(False, False),
                   Estilo(True, None), Estilo(True, False, True), Estilo(sublinhado=True)):
        assert Estilo.de_json(estilo.para_json()) == estilo, estilo
    assert Estilo.de_json([0, 0, 0]) is SEM_ESTILO


def test_o_glifo_sem_medida_acha_a_amostra_em_negrito(tmp_path):
    """O box sem medida (SEM_ESTILO, o padrão) compara com todas as amostras: a amostra em
    negrito continua vizinha dele; o reto medido, não."""
    import numpy as np

    from abbychess.leitor import LeitorDoLivro
    from abbychess.modelo import SEM_ESTILO

    recorte = np.full((40, 30), 255, dtype=np.uint8)
    recorte[5:35, 10:20] = 0
    leitor = LeitorDoLivro(tmp_path / "padroes")
    leitor.ensinar(recorte, "l", altura_de_referencia=40, efeito=Estilo(True, False))
    assert leitor.ler(recorte, altura_de_referencia=40, efeito=SEM_ESTILO).char == "l"
    assert leitor.ler(recorte, altura_de_referencia=40, efeito=Estilo(None, False)).char == "l"
    assert leitor.ler(recorte, altura_de_referencia=40, efeito=Estilo(False, False)).char == ""


def test_o_lote_rele_o_glifo_lido_por_amostra_de_outro_efeito(tmp_path):
    """CA-9.3 no caminho do lote e do F5: lido antes de o efeito ser medido, o glifo que uma
    amostra em negrito leu é lido de novo quando a página o mede reto."""
    from core import vertical

    from abbychess import procedencia
    from abbychess.leitor import LeitorDoLivro

    imagem = Image.new("L", (100, 60), 255)
    imagem.paste(0, (40, 10, 50, 40))
    box = BoxEntry("", 35, 5, 55, 45)
    recorte = vertical.recorte_de_pe(np.asarray(imagem), box)
    leitor = LeitorDoLivro(tmp_path / "padroes")
    negrito = leitor.ensinar(recorte, "n", altura_de_referencia=40, efeito=Estilo(True, False))
    leitor.ensinar(recorte, "r", altura_de_referencia=40, efeito=Estilo(False, False))
    box.char, box.source, box.confidence = "n", "livro", 1.0
    procedencia.registrar(box, str(negrito))
    assert pg.reler_pelo_efeito(imagem, [box], leitor, [False], [None]) == 1
    assert box.char == "r"
    # Medido em negrito (ou sem medida), a leitura fica.
    box.char = "n"
    procedencia.registrar(box, str(negrito))
    assert pg.reler_pelo_efeito(imagem, [box], leitor, [True], [None]) == 0
    assert pg.reler_pelo_efeito(imagem, [box], leitor, [None], [None]) == 0
    assert box.char == "n"


def test_reler_mantem_o_sublinhado_do_usuario():
    """A medida nova diz o negrito e o itálico; o sublinhado (Ctrl+U) é do usuário e fica."""
    from abbychess.modelo import Box, reconciliar

    antes = [Box(0, BoxEntry("a", 0, 0, 5, 5), estilo=Estilo(False, False, True))]
    nova = BoxEntry("a", 0, 0, 5, 5)
    boxes, _dif = reconciliar(antes, [nova], alocar=lambda: 1,
                              estilo_de=lambda e: Estilo(True, False))
    assert boxes[0].estilo == Estilo(True, False, True)


def test_efeitos_de_impressao_continua_so_o_negrito():
    assert pg.efeitos_de_impressao(Image.new("L", (10, 10)), []) == []
    assert pg.efeitos_da_pagina(Image.new("L", (10, 10)), []) == ([], [])
