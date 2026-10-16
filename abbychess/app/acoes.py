"""As ações, a barra e os menus da janela principal, e quando cada ação vale.

Cada ação chama um comando de controlador (`abbychess.controlador`) ou um método da
janela que abre um diálogo antes. Os atalhos vêm de `docs/atalhos.yaml`, pelo id da ação
(`app/teclado.py`): só os de `desde_passo` até o passo do programa têm tecla.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QSpinBox, QToolBar

from abbychess.app import teclado


def montar(janela) -> None:
    """Cria as ações (`janela.acao_*`), a barra principal e os menus."""
    j, p, livro = janela, janela.pagina, janela.livro
    acao = teclado.acao
    barra = QToolBar("Principal")
    barra.setObjectName("barra_principal")
    barra.setMovable(False)
    j.addToolBar(barra)

    # --- Projeto e Editar ----------------------------------------------------------
    j.acao_novo = acao(j, "novo_projeto", j.novo_projeto, texto="Novo projeto…", barra=barra)
    j.acao_abrir = acao(j, "abrir_projeto", j.abrir_projeto, texto="Abrir projeto…", barra=barra)
    j.acao_exportar = acao(j, "exportar", j.exportar, texto="Exportar…")
    j.acao_opcoes = acao(j, "opcoes", j.opcoes, texto="Opções…")
    j.acao_sair = acao(j, "sair", j.close, texto="Sair")
    j.acao_cancelar_lote = acao(j, "cancelar_lote", livro.cancelar, texto="Cancelar o lote")
    j.acao_desfazer = acao(j, "desfazer", p.desfazer)
    j.acao_refazer = acao(j, "refazer", p.refazer)
    barra.addSeparator()

    # --- Página e livro ------------------------------------------------------------
    j.acao_anterior = acao(j, "pagina_anterior", lambda: p.vizinha(-1), texto="◀", barra=barra)
    j.seletor = QSpinBox()
    j.seletor.setMinimum(1)
    j.seletor.setKeyboardTracking(False)
    j.seletor.setAccessibleName("Página aberta")
    j.seletor.valueChanged.connect(lambda valor: j.ir_para_pagina(valor - 1))
    barra.addWidget(j.seletor)
    j.total_de_paginas = QLabel(" de 0 ")
    barra.addWidget(j.total_de_paginas)
    j.acao_seguinte = acao(j, "pagina_seguinte", lambda: p.vizinha(+1), texto="▶", barra=barra)
    j.acao_primeira = acao(j, "primeira_pagina", p.primeira, texto="Primeira página")
    j.acao_ultima = acao(j, "ultima_pagina", p.ultima, texto="Última página")
    j.acao_ir_para = acao(j, "ir_para_pagina", j.ir_para_a_pagina_pedida,
                          texto="Ir para a página…")
    j.acao_voltar_visita = acao(j, "voltar_visita", p.voltar_visita,
                                texto="Página visitada antes")
    j.acao_avancar_visita = acao(j, "avancar_visita", p.avancar_visita,
                                 texto="Página visitada depois")
    j.acao_rolar_acima = acao(j, "rolar_tela_acima", lambda: j.visor.rolar_tela(-1),
                              widgets=[j.visor])
    j.acao_rolar_abaixo = acao(j, "rolar_tela_abaixo", lambda: j.visor.rolar_tela(+1),
                               widgets=[j.visor])
    barra.addSeparator()
    j.acao_reconhecer = acao(j, "reconhecer_pagina", j.reconhecer,
                             texto="Reconhecer página (F5)", barra=barra)
    j.acao_reler = acao(j, "reler_pendentes", lambda: p.reler_pendentes(),
                        texto="Reler pendentes", barra=barra)
    j.acao_lote = acao(j, "reconhecer_livro", j.reconhecer_livro, texto="Reconhecer o livro…")
    j.acao_proximo_do_livro = acao(j, "proxima_pagina_pendente", livro.proximo_pendente,
                                   texto="Próxima página com pendentes")
    j.acao_verificada = acao(j, "pagina_verificada", p.verificar,
                             texto="Página verificada (abre a próxima)")
    barra.addSeparator()

    # --- A fila ----------------------------------------------------------------
    j.acao_proximo_da_fila = acao(j, "proximo_da_fila", lambda: j.fila.andar(+1),
                                  texto="Próximo da fila")
    j.acao_anterior_da_fila = acao(j, "anterior_da_fila", lambda: j.fila.andar(-1),
                                   texto="Anterior da fila")
    j.acao_ciclar_fila = acao(j, "ciclar_modo_da_fila", j.fila.ciclar,
                              texto="Modo seguinte da fila")
    j.acao_diagramas = acao(j, "proximo_diagrama", lambda: j.conferencia.proximo_do_livro(),
                            texto="Próximo diagrama por conferir")
    j.acao_diagramas.setToolTip("O próximo diagrama do livro ainda não conferido (o desta "
                                "página primeiro); também abre com um clique no diagrama.")
    j.acao_verificar = teclado.sem_atalho(j, "Verificação de texto (fila de palavras)",
                                          lambda: j.fila.definir("palavras"))

    # --- Exibir: arranjos, painéis, foco, zoom -------------------------------------------
    j.acao_so_imagem = acao(j, "arranjo_so_imagem", lambda: j.arranjar("so_imagem"),
                            texto="Só a Imagem")
    j.acao_lado_a_lado = acao(j, "arranjo_lado_a_lado", lambda: j.arranjar("lado_a_lado"),
                              texto="Lado a lado")
    j.acao_empilhado = acao(j, "arranjo_empilhado", lambda: j.arranjar("empilhado"),
                            texto="Empilhado")
    j.acao_so_vista = acao(j, "arranjo_so_vista", lambda: j.arranjar("so_vista"),
                           texto="Só a vista direita")
    j.acao_paginas = acao(j, "mostrar_paginas", j.alternar_paginas, texto="Páginas")
    j.acoes_de_foco = [acao(j, f"foco_{nome}", lambda _=False, n=n: j.focar(n), texto=texto)
                       for n, (nome, texto) in enumerate(
                           (("paginas", "Ir às Páginas"), ("imagem", "Ir à Imagem"),
                            ("vista", "Ir à vista direita (de novo: a aba seguinte)"),
                            ("inspetor", "Ir ao Inspetor"), ("resultados", "Ir a Resultados")),
                           start=1)]
    j.acao_seguir = acao(j, "seguir", lambda: None, texto="Seguir o item atual", marcavel=True)
    j.acao_seguir.setChecked(True)
    imagem_e_glifo = [j.visor, j.treino]        # o zoom vale também com o foco no treino
    j.acao_ajustar = acao(j, "zoom_pagina", j.visor.zoom_pagina,
                          texto="Página inteira", widgets=imagem_e_glifo, barra=barra)
    j.acao_zoom_mais = acao(j, "zoom_mais", j.visor.zoom_mais, texto="Aproximar",
                            widgets=imagem_e_glifo)
    j.acao_zoom_menos = acao(j, "zoom_menos", j.visor.zoom_menos, texto="Afastar",
                             widgets=imagem_e_glifo)
    j.acao_zoom_largura = acao(j, "zoom_largura", j.visor.zoom_largura,
                               texto="Largura da página", widgets=imagem_e_glifo)
    j.acao_zoom_100 = acao(j, "zoom_100", j.visor.zoom_100, texto="100%", widgets=imagem_e_glifo)
    j.acao_zoom_item = acao(j, "zoom_item", j.visor.zoom_item, texto="Zoom no item atual",
                            widgets=imagem_e_glifo)
    j.acao_origem = acao(j, "mostrar_origem", j.visor.definir_origem,
                         texto="Mostrar a origem das leituras", widgets=[j.visor],
                         marcavel=True)
    j.acao_padroes = teclado.sem_atalho(j, "Padrões do livro (Alt+3 cicla as abas)",
                                        lambda: j.vista.setCurrentWidget(j.padroes))
    j.acao_fechar = acao(j, "fechar_sobreposicao", j.fechar_sobreposicao,
                         texto="Fechar o que está por cima")

    # --- Ferramentas -------------------------------------------------------------
    j.acao_modo_treino = acao(j, "marcar_glifo", j.modo_treino,
                              texto="Marcar glifo à mão (Ctrl+M)", barra=barra, marcavel=True)
    j.acao_modo_treino.setToolTip("Arraste na página para marcar um glifo; "
                                  "Ctrl+clique junta boxes na seleção.")
    j.acao_areas = acao(j, "modo_areas", j.modo_areas, texto="Editor de áreas (Ctrl+Shift+A)",
                        barra=barra, marcavel=True)
    j.acao_areas.setToolTip("Arraste para desenhar uma área; arraste dentro dela para "
                            "mover e na borda para esticar. 1-4 trocam o tipo, Del apaga.")
    j.acao_areas_auto = acao(j, "areas_automaticas", j.areas.automaticas,
                             texto="Refazer as áreas automáticas")

    # --- O Glifo e a Palavra (escopos de painel) -----------------------------------------
    t, campo = j.treino, j.treino.campo
    j.acao_ensinar = acao(j, "ensinar", t.pedir_ensinar, texto="Ensinar padrão", widgets=[campo])
    j.acao_so_corrigir = acao(j, "so_corrigir", t.pedir_so_corrigir,
                              texto="Só esta ocorrência", widgets=[campo])
    j.acao_descartar = acao(j, "descartar_box", t.pedir_descartar, texto="Não é caractere",
                            widgets=[t])
    j.acao_dividir = acao(j, "dividir", t.pedir_dividir, texto="Dividir o box", widgets=[t])
    j.acao_juntar_seguinte = acao(j, "juntar_seguinte", lambda: j.treino.pedir_juntar(+1),
                                  widgets=[t])
    j.acao_juntar_anterior = acao(j, "juntar_anterior", lambda: j.treino.pedir_juntar(-1),
                                  widgets=[t])
    bordas = (("borda_direita_esq", (0, 0, -1, 0)), ("borda_direita_dir", (0, 0, 1, 0)),
              ("borda_baixo_cima", (0, 0, 0, -1)), ("borda_baixo_baixo", (0, 0, 0, 1)),
              ("borda_esquerda_esq", (-1, 0, 0, 0)), ("borda_esquerda_dir", (1, 0, 0, 0)),
              ("borda_topo_cima", (0, -1, 0, 0)), ("borda_topo_baixo", (0, 1, 0, 0)))
    j.acoes_das_bordas = [acao(j, id_, lambda _=False, d=d: j.treino.pedir_ajustar(*d),
                               widgets=[j.visor, campo]) for id_, d in bordas]
    for q in (j.acao_ensinar, j.acao_so_corrigir, j.acao_descartar, *j.acoes_das_bordas):
        campo.teclas.ligar(q)                   # no campo, a tecla é dele (exceção 6, §3.4)
    j.acao_paleta = acao(j, "paleta", t.abrir_paleta, texto="Símbolos…", widgets=[t])
    j.acao_ignorar = acao(j, "ignorar_palavra", j.verificacao.pedir_ignorar_todas,
                          widgets=[j.verificacao])
    j.acao_adicionar = acao(j, "adicionar_ao_lexico", j.verificacao.pedir_adicionar,
                            widgets=[j.verificacao])

    _menus(j)


def _menus(j) -> None:
    menu = j.menuBar().addMenu("&Projeto")
    for acao in (j.acao_novo, j.acao_abrir, None, j.acao_exportar, None, j.acao_sair):
        menu.addSeparator() if acao is None else menu.addAction(acao)
    menu = j.menuBar().addMenu("&Editar")
    menu.addAction(j.acao_desfazer)
    menu.addAction(j.acao_refazer)
    menu = j.menuBar().addMenu("P&ágina")
    for acao in (j.acao_anterior, j.acao_seguinte, j.acao_primeira, j.acao_ultima,
                 j.acao_ir_para, j.acao_voltar_visita, j.acao_avancar_visita, None,
                 j.acao_reconhecer, j.acao_reler, j.acao_verificada, None,
                 j.acao_proximo_da_fila, j.acao_anterior_da_fila, j.acao_ciclar_fila,
                 j.acao_proximo_do_livro, j.acao_diagramas):
        menu.addSeparator() if acao is None else menu.addAction(acao)
    menu = j.menuBar().addMenu("E&xibir")
    for acao in (j.acao_lado_a_lado, j.acao_empilhado, j.acao_so_imagem, j.acao_so_vista,
                 None, j.acao_paginas, j.doca_inspetor.toggleViewAction(),
                 j.doca_resultados.toggleViewAction(), j.acao_padroes, None, *j.acoes_de_foco,
                 None, j.acao_ajustar, j.acao_zoom_largura, j.acao_zoom_100, j.acao_zoom_item,
                 j.acao_zoom_mais, j.acao_zoom_menos, j.acao_origem, j.acao_seguir):
        menu.addSeparator() if acao is None else menu.addAction(acao)
    j.menu_ferramentas = j.menuBar().addMenu("&Ferramentas")
    for acao in (j.acao_modo_treino, j.acao_areas, j.acao_areas_auto, j.acao_verificar, None,
                 j.acao_lote, j.acao_cancelar_lote, None, j.acao_opcoes):
        j.menu_ferramentas.addSeparator() if acao is None else j.menu_ferramentas.addAction(acao)
    menu = j.menuBar().addMenu("Aj&uda")
    menu.addAction("Atalhos do teclado", j.mostrar_atalhos)
    menu.addAction("Sobre o AbbyChessCraft", j.sobre)


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
    j.acao_verificada.setEnabled(editar)
    j.acao_anterior.setEnabled(tem and p.indice > 0)
    j.acao_seguinte.setEnabled(tem and p.indice < total - 1)
    j.acao_primeira.setEnabled(tem and p.indice > 0)
    j.acao_ultima.setEnabled(tem and p.indice < total - 1)
    j.acao_ir_para.setEnabled(tem)
    j.acao_voltar_visita.setEnabled(tem and p.pode_voltar)
    j.acao_avancar_visita.setEnabled(tem and p.pode_avancar)
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
    j.acao_diagramas.setEnabled(tem)
    for q in (j.acao_proximo_da_fila, j.acao_anterior_da_fila, j.acao_ciclar_fila):
        q.setEnabled(tem)
    desfazer = p.historico.proximo_a_desfazer
    refazer = p.historico.proximo_a_refazer
    j.acao_desfazer.setEnabled(editar and desfazer is not None)
    j.acao_refazer.setEnabled(editar and refazer is not None)
    j.acao_desfazer.setText(f"Desfazer: {desfazer}" if desfazer else "Desfazer")
    j.acao_refazer.setText(f"Refazer: {refazer}" if refazer else "Refazer")
