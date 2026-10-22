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
    j.acao_localizar = acao(j, "localizar", j.localizar, texto="Localizar…")
    j.acao_proxima_ocorrencia = acao(j, "proxima_ocorrencia", j.proxima_ocorrencia)
    j.acao_ocorrencia_anterior = acao(j, "ocorrencia_anterior", j.ocorrencia_anterior)
    j.acao_todas_em_resultados = acao(j, "todas_em_resultados", j.todas_em_resultados)
    j.acao_buscar_glifo = teclado.sem_atalho(j, "Buscar glifo…", j.buscar_glifo)
    j.acao_substituir = acao(j, "substituir", j.substituir, texto="Substituir…")
    j.acao_galeria = teclado.sem_atalho(j, "Galeria do caractere", lambda: j.abrir_galeria())
    j.acao_opcoes = acao(j, "opcoes", j.opcoes, texto="Opções…")
    j.acao_sair = acao(j, "sair", j.close, texto="Sair")
    j.acao_cancelar_lote = acao(j, "cancelar_lote", livro.cancelar, texto="Cancelar o lote")
    j.acao_retomar_lote = acao(j, "retomar_lote", j.retomar_lote, texto="Retomar o lote")
    j.acao_desfazer = acao(j, "desfazer", j.desfazer)
    j.acao_refazer = acao(j, "refazer", j.refazer)
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
    j.acao_verificada = acao(j, "pagina_verificada", j.verificar_pagina,
                             texto="Página verificada (abre a próxima)")
    j.acao_antes_do_lote = acao(j, "voltar_antes_do_lote", j.voltar_ao_antes_do_lote,
                                texto="Voltar ao estado antes do lote…")
    barra.addSeparator()

    # --- A fila ----------------------------------------------------------------
    j.acao_proximo_da_fila = acao(j, "proximo_da_fila", lambda: j.fila.andar(+1),
                                  texto="Próximo da fila")
    j.acao_anterior_da_fila = acao(j, "anterior_da_fila", lambda: j.fila.andar(-1),
                                   texto="Anterior da fila")
    j.acao_ciclar_fila = acao(j, "ciclar_modo_da_fila", j.fila.ciclar,
                              texto="Modo seguinte da fila")
    j.acao_escopo_da_fila = acao(j, "alternar_escopo_da_fila", j.fila.alternar_escopo,
                                 texto="Escopo da fila: página ou livro")
    j.acao_diagramas = acao(j, "proximo_diagrama", lambda: j.conferencia.proximo_do_livro(),
                            texto="Próximo diagrama por conferir")
    j.acao_diagramas.setToolTip("O próximo diagrama do livro ainda não conferido (o desta "
                                "página primeiro); também abre com um clique no diagrama.")
    # O editor Diagrama do Inspetor (§10): valem com o foco dentro dele.
    editor = [j.editor_diagrama]
    j.acao_conferir_diagrama = acao(j, "conferir_diagrama", j.editor_diagrama.confirmar,
                                    widgets=editor)
    j.acao_diagrama_anterior = acao(j, "diagrama_anterior", lambda: j.editor_diagrama.ir(-1),
                                    widgets=editor)
    j.acao_diagrama_seguinte = acao(j, "diagrama_seguinte", lambda: j.editor_diagrama.ir(+1),
                                    widgets=editor)
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
    j.caixa_de_zoom.valueChanged.connect(lambda valor: j.visor.definir_zoom(valor / 100))
    # O Enter na caixa devolve o foco ao visor (os atalhos voltam). Não pelo editingFinished,
    # que também vem quando a caixa perde o foco: roubaria o clique dado noutro campo.
    j.caixa_de_zoom.lineEdit().returnPressed.connect(lambda: j.visor.setFocus())
    j.acao_seguir = acao(j, "seguir", lambda: None, texto="Seguir o item atual", marcavel=True)
    j.acao_seguir.setChecked(True)
    imagem_e_glifo = [j.visor, j.treino]        # o zoom vale também com o foco no treino
    com_o_documento = [*imagem_e_glifo, j.texto]   # e, no Documento, muda o corpo
    j.acao_ajustar = acao(j, "zoom_pagina", j.zoom_padrao, texto="Página inteira",
                          widgets=com_o_documento, barra=barra)
    j.acao_ajustar.setToolTip("Página inteira na Imagem; no Documento, o corpo padrão (Ctrl+0)")
    j.acao_zoom_mais = acao(j, "zoom_mais", j.aproximar, texto="Aproximar",
                            widgets=com_o_documento)
    j.acao_zoom_menos = acao(j, "zoom_menos", j.afastar, texto="Afastar",
                             widgets=com_o_documento)
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
    j.acao_linha = acao(j, "mostrar_linha", j.alternar_linha, texto="Linha", marcavel=True)
    j.acao_linha.setChecked(True)
    j.acao_margens = acao(j, "ocultar_cabecalhos", j.texto.alternar_margens,
                          texto="Cabeçalhos e rodapés", widgets=[j.texto], marcavel=True)
    j.acao_margens.setChecked(True)
    j.acao_realce = teclado.sem_atalho(j, "Realce", j.texto.definir_realce)
    j.acao_realce.setCheckable(True)
    j.acao_realce.setChecked(True)
    j.acao_realce.setToolTip("Baixa confiança, fora do léxico, virtual e aguardando leitura")
    for q in (j.acao_realce, j.acao_margens):
        j.barra_do_documento.addAction(q)

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
    j.acao_reconhecer_zona = acao(j, "reconhecer_zona", j.areas.reconhecer_atual,
                                  widgets=[j.visor])
    j.acao_ordenar_areas = acao(j, "ordenar_areas", j.areas.iniciar_ordenacao,
                                widgets=[j.visor])
    j.acao_salvar_modelo_areas = acao(j, "salvar_modelo_areas", j.areas.salvar_modelo,
                                      widgets=[j.visor])
    j.acao_aplicar_modelo_areas = acao(j, "aplicar_modelo_areas", j.aplicar_modelo_de_areas,
                                       widgets=[j.visor])
    funcoes = (("funcao_texto", "texto"), ("funcao_titulo", "titulo"),
               ("funcao_cabecalho", "cabecalho"), ("funcao_rodape", "rodape"),
               ("funcao_numero", "numero_de_pagina"), ("funcao_nota", "nota"),
               ("funcao_legenda", "legenda"), ("funcao_diagrama", "diagrama"),
               ("funcao_ignorar", "ignorar"))
    j.acoes_das_funcoes = [acao(j, id_, lambda _=False, f=f: j.areas.trocar_funcao_atual(f),
                                widgets=[j.visor]) for id_, f in funcoes]

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
    j.acao_paleta = acao(j, "paleta", j.abrir_paleta, texto="Símbolos…", widgets=[t, j.texto])
    _documento(j)
    palavra = j.verificacao.campo
    j.acao_corrigir_palavra = acao(j, "corrigir_palavra", j.verificacao.pedir_corrigir,
                                   widgets=[j.verificacao])
    j.acao_ensinar_palavra = acao(j, "corrigir_e_ensinar_palavra", j.verificacao.pedir_ensinar,
                                  widgets=[j.verificacao])
    for q in (j.acao_corrigir_palavra, j.acao_ensinar_palavra):
        palavra.teclas.ligar(q)
    j.acao_ignorar = acao(j, "ignorar_palavra", j.verificacao.pedir_ignorar_todas,
                          widgets=[j.verificacao])
    j.acao_adicionar = acao(j, "adicionar_ao_lexico", j.verificacao.pedir_adicionar,
                            widgets=[j.verificacao])

    _menus(j)


def _documento(j) -> None:
    """As teclas da edição no Documento (§6.3, §6.4, passo D1). Enter, Shift+Enter, Ctrl+Z e
    Ctrl+Y são do `QTextEdit`: a vista as entrega às ações (a exceção "redireciona")."""
    acao, d = teclado.acao, j.texto
    j.acao_confirmar = acao(j, "confirmar_e_avancar",
                            lambda: j.confirmar_no_documento(avancar=True), widgets=[d])
    j.acao_confirmar_sem_avancar = acao(j, "confirmar_sem_avancar", j.confirmar_no_documento,
                                        widgets=[d])
    j.acao_ensinar_no_documento = acao(j, "ensinar_no_documento",
                                       lambda: j.confirmar_no_documento(ensinar=True),
                                       widgets=[d])
    j.acao_novo_paragrafo = acao(j, "novo_paragrafo", j.novo_paragrafo, widgets=[d])
    j.acao_negrito = acao(j, "negrito", lambda: j.alternar_estilo("negrito"), widgets=[d])
    j.acao_italico = acao(j, "italico", lambda: j.alternar_estilo("italico"), widgets=[d])
    j.acao_sublinhado = acao(j, "sublinhado", lambda: j.alternar_estilo("sublinhado"),
                             widgets=[d])
    j.acoes_das_figurinas = [acao(j, id_, lambda _=False, f=f: j.inserir_figurina(f),
                                  widgets=[d, j.treino])
                             for id_, f in (("figurina_rei", "♔"), ("figurina_dama", "♕"),
                                            ("figurina_torre", "♖"), ("figurina_bispo", "♗"),
                                            ("figurina_cavalo", "♘"), ("figurina_peao", "♙"))]
    for q in (j.acao_confirmar, j.acao_confirmar_sem_avancar, j.acao_novo_paragrafo,
              j.acao_negrito, j.acao_italico, j.acao_sublinhado,
              j.acao_desfazer, j.acao_refazer):
        d.teclas.ligar(q)


def _menus(j) -> None:
    menu = j.menuBar().addMenu("&Projeto")
    for acao in (j.acao_novo, j.acao_abrir, None, j.acao_exportar, None, j.acao_lote,
                 j.acao_cancelar_lote, j.acao_retomar_lote, None, j.acao_sair):
        menu.addSeparator() if acao is None else menu.addAction(acao)
    menu = j.menuBar().addMenu("&Editar")
    menu.addAction(j.acao_desfazer)
    menu.addAction(j.acao_refazer)
    menu.addSeparator()                         # localizar (§7.1)
    for acao in (j.acao_localizar, j.acao_substituir, j.acao_proxima_ocorrencia,
                 j.acao_ocorrencia_anterior, j.acao_todas_em_resultados, j.acao_buscar_glifo,
                 j.acao_galeria):
        menu.addAction(acao)
    menu.addSeparator()                         # a sessão do Documento (§6.3)
    for acao in (j.acao_confirmar, j.acao_confirmar_sem_avancar, j.acao_ensinar_no_documento,
                 j.acao_novo_paragrafo, j.acao_negrito, j.acao_italico,
                 j.acao_sublinhado):
        menu.addAction(acao)
    menu.addSeparator()
    menu.addAction(j.acao_paleta)
    figurinas = menu.addMenu("Figurinas")
    for acao in j.acoes_das_figurinas:
        figurinas.addAction(acao)
    menu = j.menuBar().addMenu("P&ágina")
    for acao in (j.acao_anterior, j.acao_seguinte, j.acao_primeira, j.acao_ultima,
                 j.acao_ir_para, j.acao_voltar_visita, j.acao_avancar_visita, None,
                 j.acao_reconhecer, j.acao_reler, j.acao_verificada, j.acao_antes_do_lote,
                 None,
                 j.acao_proximo_da_fila, j.acao_anterior_da_fila, j.acao_ciclar_fila,
                 j.acao_escopo_da_fila, j.acao_proximo_do_livro, j.acao_diagramas):
        menu.addSeparator() if acao is None else menu.addAction(acao)
    menu = j.menuBar().addMenu("E&xibir")
    for acao in (j.acao_lado_a_lado, j.acao_empilhado, j.acao_so_imagem, j.acao_so_vista,
                 None, j.acao_paginas, j.doca_inspetor.toggleViewAction(),
                 j.doca_resultados.toggleViewAction(), j.acao_linha, j.acao_padroes, None,
                 j.acao_realce, j.acao_margens, None, *j.acoes_de_foco,
                 None, j.acao_ajustar, j.acao_zoom_largura, j.acao_zoom_100, j.acao_zoom_item,
                 j.acao_zoom_mais, j.acao_zoom_menos, j.acao_origem, j.acao_seguir):
        menu.addSeparator() if acao is None else menu.addAction(acao)
    j.menu_ferramentas = j.menuBar().addMenu("&Ferramentas")
    for acao in (j.acao_modo_treino, j.acao_areas, j.acao_areas_auto,
                 j.acao_reconhecer_zona, j.acao_ordenar_areas,
                 j.acao_salvar_modelo_areas, j.acao_aplicar_modelo_areas,
                 j.acao_verificar, None,
                 j.acao_lote, None,
                 j.acao_opcoes):
        j.menu_ferramentas.addSeparator() if acao is None else j.menu_ferramentas.addAction(acao)
    menu = j.menuBar().addMenu("Aj&uda")
    menu.addAction("Atalhos do teclado", j.mostrar_atalhos)
    menu.addAction("Sobre o AbbyChessCraft", j.sobre)


def atualizar(janela) -> None:
    """Liga e desliga as ações pelo estado: projeto aberto, lote rodando, o que a página tem.

    Uma tarefa rodando não desliga quase nada: o comando pedido entra na fila do
    executor, que a barra de status mostra. O lote (passo E) também não: ele grava entre um
    comando e outro; só abrir outro projeto e começar outro lote esperam o fim dele."""
    j, p = janela, janela.pagina
    tem = p.pronto
    sem_lote = not p.lote_rodando
    total = p.fonte.total if p.fonte else 0
    editar = tem
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
    j.acao_lote.setEnabled(tem and sem_lote)
    j.acao_cancelar_lote.setEnabled(j.livro.lote_rodando)
    j.acao_retomar_lote.setEnabled(tem and j.livro.pode_retomar)
    j.acao_antes_do_lote.setEnabled(tem and not p.projeto.somente_leitura
                                    and p.projeto.tem_antes_do_lote(p.indice))
    j.acao_proximo_do_livro.setEnabled(tem)
    j.acao_exportar.setEnabled(tem)
    for q in (j.acao_localizar, j.acao_proxima_ocorrencia, j.acao_ocorrencia_anterior,
              j.acao_todas_em_resultados, j.acao_buscar_glifo):
        q.setEnabled(tem)
    j.acao_substituir.setEnabled(editar)
    j.acao_galeria.setEnabled(tem and bool(p.boxes))
    j.acao_areas.setEnabled(tem)
    j.acao_areas_auto.setEnabled(editar and j.acao_areas.isChecked())
    area_atual = editar and j.acao_areas.isChecked() and j.areas.atual is not None
    j.acao_reconhecer_zona.setEnabled(area_atual)
    j.acao_ordenar_areas.setEnabled(editar and j.acao_areas.isChecked() and bool(j.areas.zonas))
    j.acao_salvar_modelo_areas.setEnabled(editar and j.acao_areas.isChecked()
                                          and bool(j.areas.zonas))
    j.acao_aplicar_modelo_areas.setEnabled(editar and j.acao_areas.isChecked()
                                           and j.areas.modelo is not None)
    for q in j.acoes_das_funcoes:
        q.setEnabled(area_atual)
    j.acao_verificar.setEnabled(tem and bool(p.boxes))
    j.acao_diagramas.setEnabled(tem)
    for q in (j.acao_proximo_da_fila, j.acao_anterior_da_fila, j.acao_ciclar_fila,
              j.acao_escopo_da_fila):
        q.setEnabled(tem)
    for q in (j.acao_realce, j.acao_margens):     # sem página reconhecida, nada a realçar
        q.setEnabled(tem and bool(p.boxes))
    desfazer = p.historico.proximo_a_desfazer
    refazer = p.historico.proximo_a_refazer
    if j.texto.tem_sessao:                      # na sessão, o Ctrl+Z é dela (§6.3)
        desfazer = "a palavra"
    if j.texto.pode_reaplicar:                  # depois do Esc, o Ctrl+Y a reaplica
        refazer = "a palavra"
    # Com o editor Diagrama aberto, o Ctrl+Z dele (o do tabuleiro) vale sem histórico.
    no_diagrama = j.editor_diagrama.aberto and j.editor_diagrama.isVisible()
    j.acao_desfazer.setEnabled(editar and (desfazer is not None or no_diagrama))
    j.acao_refazer.setEnabled(editar and (refazer is not None or no_diagrama))
    j.acao_desfazer.setText(f"Desfazer: {desfazer}" if desfazer else "Desfazer")
    j.acao_refazer.setText(f"Refazer: {refazer}" if refazer else "Refazer")
