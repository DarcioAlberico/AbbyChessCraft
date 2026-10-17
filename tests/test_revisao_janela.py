"""A revisão na janela (SPEC §8, passo C): a Galeria por caractere (CA-8.1), a aba Padrões e
o aviso de ensino no Glifo."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from tests.test_busca_janela import _ate, _pagina_lida, jb  # noqa: F401 (fixture)
from tests.test_documento import app  # noqa: F401 (fixture)
from tests.test_documento_edicao import _janela_do_modulo, j  # noqa: F401 (fixtures)


def _uns(jb, quantos):  # noqa: F811
    """A página com `quantos` glifos lidos como "1" (e um "a")."""
    linhas, resto = [], quantos
    while resto > 0:
        linhas.append(" ".join(["1"] * min(20, resto)))
        resto -= 20
    return _pagina_lida(jb, "a", *linhas)


def test_ca_8_1_digitar_na_galeria_corrige_40_num_passo(jb):  # noqa: F811
    _uns(jb, 40)
    jb.abrir_galeria("1", "pagina")
    g = jb.galeria
    assert g.modelo.rowCount() == 40 and not g.isHidden()
    padroes_antes = sum(len(v) for v in jb.leitor.padroes_por_caractere().values())
    g.vista.selectAll()
    QTest.keyClick(g.vista, Qt.Key.Key_L)                 # digitar "l"
    _ate(lambda: sum(b.entry.char == "l" for b in jb.pagina.modelo.boxes) == 40)
    assert all(b.entry.source == "manual" for b in jb.pagina.modelo.boxes if b.entry.char == "l")
    assert sum(len(v) for v in jb.leitor.padroes_por_caractere().values()) == padroes_antes
    assert all(i.char == "l" for i in g.modelo.itens)    # a grade mostra a leitura nova
    jb.desfazer()                                         # um passo do desfazer
    _ate(lambda: sum(b.entry.char == "1" for b in jb.pagina.modelo.boxes) == 40)


def test_shift_enter_so_corrige_e_enter_ensina_uma_amostra_por_glifo(jb):  # noqa: F811
    _uns(jb, 3)
    jb.abrir_galeria("1", "pagina")
    g = jb.galeria
    _ate(lambda: len(g.modelo.recortes) == 3)             # os recortes, numa thread
    total = lambda: sum(len(v) for v in jb.leitor.padroes_por_caractere().values())  # noqa: E731
    antes = total()
    g.vista.selectAll()
    QTest.keyClick(g.vista, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    _ate(lambda: all(b.entry.source == "manual" for b in jb.pagina.modelo.boxes
                     if b.entry.char == "1"))
    assert total() == antes                               # nenhum padrão novo
    jb.desfazer()
    _ate(lambda: not any(b.entry.source == "manual" for b in jb.pagina.modelo.boxes))
    g.vista.selectAll()
    QTest.keyClick(g.vista, Qt.Key.Key_Return)            # Enter ensina
    _ate(lambda: total() == antes + 3)
    jb.desfazer()                                         # e o desfazer apaga as amostras
    _ate(lambda: total() == antes)


def test_a_galeria_do_livro_e_a_busca_por_glifo(jb):  # noqa: F811
    _uns(jb, 5)
    jb.abrir_galeria("1", "livro")
    _ate(lambda: jb.galeria.modelo.rowCount() == 5 and "no livro" in jb.galeria.titulo.text())
    confiancas = [i.confianca for i in jb.galeria.modelo.itens]
    assert confiancas == sorted(confiancas)


def test_a_aba_padroes_filtra_vai_a_origem_e_esquece_com_delete(app, tmp_path):  # noqa: F811
    from PySide6.QtGui import QPixmap

    from abbychess.app.painel_padroes import PainelDePadroes

    arquivos = []
    for nome in ("um", "dois"):
        caminho = tmp_path / f"{nome}.png"
        QPixmap(8, 8).save(str(caminho))
        arquivos.append(caminho)
    painel = PainelDePadroes()
    painel.atualizar({"1": [arquivos[0]], "l": [arquivos[1]]},
                     {str(arquivos[0]): {"origem": (20, 0x1a), "altura": 1.02, "lidos": 14},
                      str(arquivos[1]): {"origem": None, "altura": None, "lidos": 0}})
    painel.busca.setText("1")
    assert painel.caracteres.currentItem().data(Qt.ItemDataRole.UserRole) == "1"
    item = painel.amostras.item(0)
    assert "p. 21" in item.text() and "leu 14" in item.text()
    assert "Altura relativa: 1.02" in item.toolTip()
    idas, esquecidas = [], []
    painel.ir_para.connect(lambda pagina, gid: idas.append((pagina, gid)))
    painel.esquecer.connect(esquecidas.append)
    painel.amostras.itemActivated.emit(item)
    assert idas == [(20, 0x1a)]
    item.setSelected(True)
    QTest.keyClick(painel.amostras, Qt.Key.Key_Delete)
    assert esquecidas == [[str(arquivos[0])]]
