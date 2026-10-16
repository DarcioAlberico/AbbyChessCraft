"""As ações, a barra e os menus da janela principal, e quando cada ação vale.

Cada ação chama um comando de controlador (`abbychess.controlador`) ou um método da
janela que abre um diálogo antes. Os atalhos são os de `docs/atalhos.yaml`.
"""

from __future__ import annotations

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QLabel, QSpinBox, QToolBar


def _acao(janela, texto, atalho, funcao, barra=None) -> QAction:
    acao = QAction(texto, janela)
    if atalho:
        acao.setShortcut(QKeySequence(atalho))
    acao.triggered.connect(funcao)
    if barra is not None:
        barra.addAction(acao)
    return acao


def montar(janela) -> None:
    """Cria as ações (`janela.acao_*`), a barra principal e os menus."""
    j, p, livro = janela, janela.pagina, janela.livro
    barra = QToolBar("Principal")
    barra.setObjectName("barra_principal")
    barra.setMovable(False)
    j.addToolBar(barra)

    j.acao_novo = _acao(j, "Novo projeto…", "Ctrl+N", j.novo_projeto, barra)
    j.acao_abrir = _acao(j, "Abrir projeto…", "Ctrl+O", j.abrir_projeto, barra)
    barra.addSeparator()
    j.acao_anterior = _acao(j, "◀", "Ctrl+PgUp", lambda: j.ir_para_pagina(p.indice - 1), barra)
    j.seletor = QSpinBox()
    j.seletor.setMinimum(1)
    j.seletor.setKeyboardTracking(False)
    j.seletor.valueChanged.connect(lambda v: j.ir_para_pagina(v - 1))
    barra.addWidget(j.seletor)
    j.total_de_paginas = QLabel(" de 0 ")
    barra.addWidget(j.total_de_paginas)
    j.acao_seguinte = _acao(j, "▶", "Ctrl+PgDown", lambda: j.ir_para_pagina(p.indice + 1), barra)
    barra.addSeparator()
    j.acao_reconhecer = _acao(j, "Reconhecer página (F5)", "F5", j.reconhecer, barra)
    j.acao_reler = _acao(j, "Reler pendentes", "Ctrl+R", lambda: p.reler_pendentes(), barra)
    j.acao_desfazer = _acao(j, "Desfazer", "Ctrl+Z", p.desfazer)
    j.acao_refazer = _acao(j, "Refazer", "Ctrl+Y", p.refazer)
    j.acao_refazer.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
    barra.addSeparator()
    j.acao_ajustar = _acao(j, "Ajustar à janela", "Ctrl+0", j.visor.ajustar, barra)
    barra.addSeparator()
    j.acao_modo_treino = _acao(j, "Modo de treino (Ctrl+T)", "Ctrl+T", j.modo_treino, barra)
    j.acao_modo_treino.setCheckable(True)
    j.acao_modo_treino.setToolTip("Arraste na página para marcar um glifo; "
                                  "Ctrl+clique junta boxes na seleção.")
    j.acao_padroes = _acao(j, "Padrões do livro…", "Ctrl+Shift+P",
                           lambda: j.abas.setCurrentWidget(j.padroes))
    j.acao_opcoes = _acao(j, "Opções…", "Ctrl+,", j.opcoes)
    j.acao_diagramas = _acao(j, "Conferir diagramas…", "Ctrl+G",
                             lambda: j.conferencia.conferir())
    j.acao_diagramas.setToolTip("A posição lida ao lado do diagrama impresso; "
                                "também abre com um clique no diagrama.")
    j.acao_lote = _acao(j, "Reconhecer o livro…", "Ctrl+Shift+F5", j.reconhecer_livro)
    j.acao_cancelar_lote = _acao(j, "Cancelar o lote", None, livro.cancelar)
    j.acao_proximo_do_livro = _acao(j, "Próximo pendente do livro", "F6", livro.proximo_pendente)
    j.acao_exportar = _acao(j, "Exportar…", "Ctrl+E", j.exportar)
    j.acao_areas = _acao(j, "Editor de áreas (Ctrl+Shift+A)", "Ctrl+Shift+A", j.modo_areas, barra)
    j.acao_areas.setCheckable(True)
    j.acao_areas.setToolTip("Arraste para desenhar uma área; arraste dentro dela para "
                            "mover e na borda para esticar. 1-4 trocam o tipo, Del apaga.")
    j.acao_areas_auto = _acao(j, "Refazer as áreas automáticas", None, j.areas.automaticas)
    j.acao_verificar = _acao(j, "Verificação de texto", "F7", j.verificar_texto)

    menu = j.menuBar().addMenu("&Projeto")
    for acao in (j.acao_novo, j.acao_abrir):
        menu.addAction(acao)
    menu.addSeparator()
    menu.addAction(j.acao_exportar)
    menu.addSeparator()
    menu.addAction(_acao(j, "Sair", "Ctrl+Q", j.close))
    menu_editar = j.menuBar().addMenu("&Editar")
    menu_editar.addAction(j.acao_desfazer)
    menu_editar.addAction(j.acao_refazer)
    menu_pagina = j.menuBar().addMenu("P&ágina")
    for acao in (j.acao_anterior, j.acao_seguinte, j.acao_reconhecer, j.acao_reler,
                 j.acao_ajustar):
        menu_pagina.addAction(acao)
    j.menu_ferramentas = j.menuBar().addMenu("&Ferramentas")
    for grupo in ((j.acao_modo_treino, j.acao_padroes, j.acao_diagramas),
                  (j.acao_areas, j.acao_areas_auto, j.acao_verificar),
                  (j.acao_lote, j.acao_cancelar_lote, j.acao_proximo_do_livro),
                  (j.acao_opcoes,)):
        for acao in grupo:
            j.menu_ferramentas.addAction(acao)
        if grupo[0] is not j.acao_opcoes:
            j.menu_ferramentas.addSeparator()


def atualizar(janela) -> None:
    """Liga e desliga as ações pelo estado: projeto aberto, lote rodando, o que a página tem.

    Uma tarefa rodando não desliga quase nada: o comando pedido entra na fila do
    executor, que a barra de status mostra. O lote desliga o que edita a página."""
    j, p = janela, janela.pagina
    tem = p.pronto
    sem_lote = not p.lote_rodando
    total = p.fonte.total if p.fonte else 0
    editar = tem and sem_lote
    j.acao_novo.setEnabled(sem_lote)
    j.acao_abrir.setEnabled(sem_lote)
    j.acao_reconhecer.setEnabled(editar)
    j.acao_reler.setEnabled(editar and bool(p.boxes))
    j.acao_anterior.setEnabled(tem and p.indice > 0)
    j.acao_seguinte.setEnabled(tem and p.indice < total - 1)
    j.seletor.setEnabled(tem)
    j.acao_modo_treino.setEnabled(tem)
    j.acao_opcoes.setEnabled(editar)
    j.acao_lote.setEnabled(editar)
    j.acao_cancelar_lote.setEnabled(j.livro.lote_rodando)
    j.acao_proximo_do_livro.setEnabled(tem)
    j.acao_exportar.setEnabled(tem)
    j.acao_areas.setEnabled(tem)
    j.acao_areas_auto.setEnabled(editar and j.acao_areas.isChecked())
    j.acao_verificar.setEnabled(tem and bool(p.boxes))
    j.acao_diagramas.setEnabled(tem and bool(p.tabuleiros))
    historico = p.historico
    desfazer = historico.proximo_a_desfazer if historico else None
    refazer = historico.proximo_a_refazer if historico else None
    j.acao_desfazer.setEnabled(editar and desfazer is not None)
    j.acao_refazer.setEnabled(editar and refazer is not None)
    j.acao_desfazer.setText(f"Desfazer: {desfazer}" if desfazer else "Desfazer")
    j.acao_refazer.setText(f"Refazer: {refazer}" if refazer else "Refazer")
