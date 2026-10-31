"""A revisão na janela (SPEC §8, passo C): a Galeria por caractere (CA-8.1), a aba Padrões e
o aviso de ensino no Glifo."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from tests.ajudantes import _ate, _pagina_lida  # noqa: E402,F401,F811


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
    assert all(i.char == "1" for i in g.modelo.itens)    # e a grade volta com ele
    jb.refazer()
    _ate(lambda: all(i.char == "l" for i in g.modelo.itens))


def test_a_celula_da_galeria_tem_o_tamanho_do_recorte_antes_de_ele_chegar(jb):  # noqa: F811
    """A grade mede a célula pelo primeiro item: sem o quadro do tamanho do recorte, as
    células saíam cortadas (uma tira de ~11×14 px) até um reset."""
    from abbychess.app.galeria import LADO

    _uns(jb, 3)
    jb.abrir_galeria("1", "pagina")
    g = jb.galeria
    g.vista.resize(400, 300)
    g.vista.doItemsLayout()
    retangulo = g.vista.visualRect(g.modelo.index(0))
    assert retangulo.width() >= LADO and retangulo.height() >= LADO


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
    assert "Altura relativa: 1,02" in item.toolTip() and "Efeito: não medido" in item.toolTip()
    idas, esquecidas = [], []
    painel.ir_para.connect(lambda pagina, gid: idas.append((pagina, gid)))
    painel.esquecer.connect(esquecidas.append)
    painel.amostras.itemActivated.emit(item)
    assert idas == [(20, 0x1a)]
    item.setSelected(True)
    QTest.keyClick(painel.amostras, Qt.Key.Key_Delete)
    assert esquecidas == [[str(arquivos[0])]]


def test_ca_8_2_shift_f7_alterna_o_escopo_da_fila(jb):  # noqa: F811
    _uns(jb, 3)
    assert jb.fila.escopo == "pagina"
    QTest.keyClick(jb.visor, Qt.Key.Key_F7, Qt.KeyboardModifier.ShiftModifier)
    assert jb.fila.escopo == "livro" and "livro" in jb.inspetor.seletor.text()
    assert "livro" in jb.inspetor.contador.text()
    QTest.keyClick(jb.visor, Qt.Key.Key_F7, Qt.KeyboardModifier.ShiftModifier)
    assert jb.fila.escopo == "pagina" and "livro" not in jb.inspetor.seletor.text()


def test_a_galeria_com_leituras_misturadas_e_um_passo_so(jb):  # noqa: F811
    _uns(jb, 3)
    from abbychess import busca as bs

    achados = [bs.GlifoAchado(jb.pagina.indice, b.gid, b.entry.char, "net", 0.9)
               for b in jb.pagina.modelo.boxes]                  # o "a" e os "1"
    jb.mostrar_glifos_na_galeria(achados, "Glifos de qualquer caractere")
    g = jb.galeria
    passos = jb.pagina.historico.passos
    g.vista.selectAll()
    QTest.keyClick(g.vista, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    _ate(lambda: all(b.entry.source == "manual" for b in jb.pagina.modelo.boxes))
    assert jb.pagina.historico.passos == passos + 1             # um passo do desfazer
    assert sorted(b.entry.char for b in jb.pagina.modelo.boxes) == ["1", "1", "1", "a"]


def test_trocar_de_pagina_fecha_a_pergunta_do_ctrl_t(jb, monkeypatch):  # noqa: F811
    _uns(jb, 3)
    marcadas = []
    monkeypatch.setattr(jb.pagina, "fila", lambda: [1, 2])      # com pendentes: a pergunta
    jb.pagina.verificar = lambda indice=None: marcadas.append(indice)
    jb.verificar_pagina()
    assert jb.confirmacao.aberta and "página 1" in jb.confirmacao.pergunta.text()
    jb.eventos.emitir("pagina_trocou")                   # foi a outra página antes de responder
    assert not jb.confirmacao.aberta
    del jb.pagina.verificar
    jb.verificar_pagina()                                # a pergunta leva o índice dela
    jb.pagina.indice += 1                                # a página mudou sem o evento
    jb.confirmacao._aceitar()
    jb.pagina.indice -= 1
    assert jb.pagina.modelo.estado != "verificada"       # a outra página não é marcada
    assert marcadas == []


def test_a_ordem_do_livro_que_muda_esvazia_a_galeria(jb):  # noqa: F811
    """Os glifos da Galeria citam posições de páginas: com a ordem do livro mudada, corrigi-los
    editaria outra página. A Galeria se esvazia e pede para abrir de novo."""
    _uns(jb, 3)
    jb.abrir_galeria("1", "pagina")
    assert jb.galeria.modelo.rowCount() == 3
    jb.pagina.eventos.emitir("sequencia_mudou")
    assert jb.galeria.modelo.rowCount() == 0
    assert "ordem do livro mudou" in jb.galeria.titulo.text()
