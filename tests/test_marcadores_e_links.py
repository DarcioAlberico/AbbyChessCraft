"""Os marcadores do PDF, o número impresso das páginas e os links internos do EPUB (passo J)."""

from __future__ import annotations

import zipfile

import fitz

from core.box_model import BoxEntry
from core.pagina import PaginaExtraida, Paragrafo

from abbychess import epub
from abbychess import exportar as ex
from abbychess import texto as tx
from abbychess.leitor import FONTE_MANUAL
from abbychess.zonas import Zona

from tests.test_livro import _ensinar_e_ler, fonte, leitor, projeto  # noqa: F401 (fixtures)


def _linha(texto: str, y: int, x: int = 40):
    boxes, cursor = [], x
    for char in texto:
        if char != " ":
            boxes.append(BoxEntry(char, cursor, y, cursor + 10, y + 20, 1.0, FONTE_MANUAL))
        cursor += 14
    return boxes


def _pagina_com_rodape(numero_impresso: str):
    entries = _linha("Texto da pagina corrida.", 100) + _linha(numero_impresso, 3000)
    pagina = tx.pagina_avulsa(entries, zonas=[Zona("texto", 0, 2990, 2000, 3040,
                                                   funcao="numero_de_pagina")])
    return ex.Estrutura.da_pagina(pagina)


# ----------------------------------------------------------------------
# O número impresso
# ----------------------------------------------------------------------

def test_o_deslocamento_mais_votado_vale_para_o_livro_todo():
    paginas = {20: _pagina_com_rodape("21"), 21: _pagina_com_rodape("22"),
               22: _pagina_com_rodape("2l"),                  # o OCR errou: não vota
               23: _pagina_com_rodape("99")}                  # um número qualquer: perde
    numeros = ex.numeros_impressos(paginas, {}, todas=range(20, 26))
    assert numeros == {i: i + 1 for i in range(20, 26)}


def test_sem_acordo_nao_ha_numero():
    paginas = {0: _pagina_com_rodape("7"), 1: _pagina_com_rodape("40")}
    assert ex.numeros_impressos(paginas, {}) == {}


# ----------------------------------------------------------------------
# Os marcadores e os rótulos do PDF
# ----------------------------------------------------------------------

def test_o_pdf_ganha_os_marcadores_pelos_titulos(projeto, fonte, leitor, tmp_path):  # noqa: F811
    _ensinar_e_ler(projeto, fonte, leitor)
    boxes = projeto.carregar_pagina(1)
    topo = min(b.y1 for b in boxes)
    primeira = [b for b in boxes if b.y1 < topo + 20]
    zona = Zona("texto", 0, topo - 5, 5000, max(b.y2 for b in primeira) + 5, funcao="titulo")
    projeto.salvar_zonas(1, [zona])
    titulos = ex.titulos_das_paginas(projeto, projeto.paginas_lidas())
    assert [i for i, _t in titulos] == [1]
    destino = tmp_path / "saida.pdf"                  # o livro.pdf é a fonte da fixture
    resumo = ex.exportar_pdf_pesquisavel(projeto, destino)
    assert resumo.marcadores == 1
    with fitz.open(destino) as doc:
        assert doc.get_toc() == [[1, titulos[0][1], 2]]


def test_o_sumario_do_pdf_original_fica(tmp_path):
    doc = fitz.open()
    for _ in range(2):
        doc.new_page()
    doc.set_toc([[1, "Do editor", 2]])
    resumo = ex.ResumoDoPdf()

    class _Projeto:
        def carregar_modelo(self, _i):
            return None

    ex._marcar_o_pdf(doc, _Projeto(), [0, 1], resumo)
    assert doc.get_toc() == [[1, "Do editor", 2]]
    assert resumo.marcadores_do_original == 1 and resumo.marcadores == 0


# ----------------------------------------------------------------------
# Os links internos do EPUB
# ----------------------------------------------------------------------

def test_referencia_a_pagina_impressa_vira_link_e_o_rotulo_e_o_impresso(tmp_path):
    paginas = [PaginaExtraida(numero=0, blocos=[Paragrafo("Capítulo", titulo=True, nivel=1),
                                                Paragrafo("A solução está na página 12; "
                                                          "a página 99 não existe.",
                                                          negrito=[(20, 30)])]),
               PaginaExtraida(numero=1, blocos=[Paragrafo("Outro", titulo=True, nivel=1),
                                                Paragrafo("Meio.")]),
               PaginaExtraida(numero=2, blocos=[Paragrafo("Solução.")])]
    destino = tmp_path / "a.epub"
    escrito = epub.escrever(paginas, destino, epub.Metadados("L"),
                            numeros={0: 10, 1: 11, 2: 12})
    assert escrito.links == 1
    assert epub.conferir(destino) == []
    with zipfile.ZipFile(destino) as z:
        primeiro = z.read("OEBPS/texto/capitulo-001.xhtml").decode("utf-8")
        nav = z.read("OEBPS/nav.xhtml").decode("utf-8")
    # O link atravessa o negrito sem quebrar a marcação, e aponta outro capítulo.
    assert 'href="capitulo-002.xhtml#pg3"' in primeiro
    assert "página 99 não existe" in primeiro and "#pg99" not in primeiro
    assert 'aria-label="10"' in primeiro
    assert '<a href="texto/capitulo-002.xhtml#pg3">12</a>' in nav


def test_sem_numero_impresso_nao_ha_link():
    alvos = {}
    assert epub.referencias("ver a página 12", "pt", alvos) == []
    assert epub.referencias("see page 12 and p. 13", "en", {12: "x#a", 13: "x#b"}) == [
        (4, 11, "x#a"), (16, 21, "x#b")]
    assert epub.referencias("siehe Seite 5", "de", {5: "y#c"}) == [(6, 13, "y#c")]


def test_exportar_sobre_a_propria_fonte_e_recusado(projeto, fonte, leitor):  # noqa: F811
    import pytest

    _ensinar_e_ler(projeto, fonte, leitor)
    antes = projeto.fonte.read_bytes()
    with pytest.raises(ValueError, match="próprio arquivo de origem"):
        ex.exportar(projeto, projeto.fonte)
    assert projeto.fonte.read_bytes() == antes

# ----------------------------------------------------------------------
# A revisão de código (rodada 1)
# ----------------------------------------------------------------------

def test_o_encarte_sem_numero_muda_o_deslocamento_dali_em_diante():
    # 10 e 11 são as páginas 11 e 12; depois de um encarte de 4 páginas, 16 e 17 são 13 e 14.
    paginas = {10: _pagina_com_rodape("11"), 11: _pagina_com_rodape("12"),
               16: _pagina_com_rodape("13"), 17: _pagina_com_rodape("14")}
    numeros = ex.numeros_impressos(paginas, {}, todas=[10, 11, 16, 17, 18])
    assert numeros == {10: 11, 11: 12, 16: 13, 17: 14, 18: 15}


def test_paginas_de_rosto_ganham_romanos_e_o_rotulo_do_pdf_fica_valido(tmp_path, monkeypatch):
    doc = fitz.open()
    for _ in range(4):
        doc.new_page()
    estruturas = {i: _pagina_com_rodape(str(i - 1)) if i >= 2 else ex.Estrutura.da_pagina(None)
                  for i in range(4)}

    class _Projeto:
        def carregar_modelo(self, _i):
            return None

    # As estruturas entram pelo `Estrutura.da_pagina` do projeto falso.
    fila = iter(estruturas[i] for i in range(4))
    monkeypatch.setattr(ex.Estrutura, "da_pagina", classmethod(lambda cls, _p: next(fila)))
    resumo = ex.ResumoDoPdf()
    ex._marcar_o_pdf(doc, _Projeto(), [0, 1, 2, 3], resumo)
    assert resumo.rotulos
    assert [p.get_label() for p in doc] == ["i", "ii", "1", "2"]


def test_citacao_de_outra_obra_nao_vira_link():
    alvos = {3: "c#a", 12: "c#b"}
    assert epub.referencias("(Informator 45, p. 12)", "en", alvos) == []
    assert epub.referencias("Fine, p. 3", "en", alvos) == []
    assert epub.referencias("Ver a solução, p. 12", "pt", alvos) == [(15, 20, "c#b")]


def test_pagina_sem_numero_impresso_nao_colide_com_um_impresso(tmp_path):
    paginas = [PaginaExtraida(numero=i, blocos=[Paragrafo(f"Texto {i}.")]) for i in range(4)]
    destino = tmp_path / "a.epub"
    epub.escrever(paginas, destino, epub.Metadados("L"), numeros={2: 1, 3: 2})
    with zipfile.ZipFile(destino) as z:
        nav = z.read("OEBPS/nav.xhtml").decode("utf-8")
    assert ">[1]</a>" in nav and ">[2]</a>" in nav and ">1</a>" in nav and ">2</a>" in nav
    assert epub.conferir(destino) == []