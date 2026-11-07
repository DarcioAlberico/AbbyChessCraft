"""O desenho da janela principal: o que cada evento dos controladores muda na tela.

É uma parte da `JanelaPrincipal` (`app/janela.py`), separada para a janela ficar com a
montagem e os comandos que perguntam antes (CA-14.1: `janela.py` < 500 linhas). Cada método
lê o estado dos controladores e desenha; nenhum decide nada.
"""

from __future__ import annotations

import functools
import time
from pathlib import Path

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox

from abbychess import avisos as av
from abbychess import grade as gd
from abbychess import livro as lv
from abbychess import tipo_de_pagina
from abbychess import verificacao as vf
from abbychess.app import acoes
from abbychess.app.imagens import pixmap_da_pagina
from abbychess.app import estilo
from abbychess.app import registro_de_eventos, teclado, vazios
from abbychess.controlador import AVISO_LONGO_MS


class DesenhoDaJanela:
    """Os métodos de desenho da `JanelaPrincipal` (um mixin: não é usado sozinho)."""

    def _pagina_trocou(self) -> None:
        p = self.pagina
        if self.confirmacao.aberta:             # a pergunta do Ctrl+T era da outra página
            self.confirmacao.recusar()
        self.seletor.blockSignals(True)
        self.seletor.setMaximum(max(1, p.fonte.total))
        self.seletor.setValue(p.indice + 1)
        self.seletor.blockSignals(False)
        self.total_de_paginas.setText(f" de {p.fonte.total} ")
        self.visor.mostrar_pagina(self._pixmap(p.indice, p.imagem))
        # A seguinte, depois desta pintada. Folheando (outra troca há menos de 1 s: ninguém
        # lê uma página nesse tempo), já: a página nunca vista leva ~470 ms para renderizar e
        # medir, e o pedido seguinte chegava antes de uma pré-carga adiada acabar.
        agora = time.monotonic()
        self._pre_carga.setInterval(20 if agora - self._ultima_troca < 1.0 else 150)
        self._ultima_troca = agora
        self._pre_carga.start()
        self._pre_pixmap.start()                # e o pixmap dela, quando a pré-carga a tiver
        self._fechar_conferencia()              # os diagramas em edição eram da outra
        registro_de_eventos.anotar_pagina(p.modelo.pid if p.modelo is not None else None,
                                          self.fila.modo)
        self.verificacao.limpar(vazios.escolha_a_fila_de_palavras())
        self._layout_mudou()
        if self.visor.modo_areas and not p.zonas:
            self.areas.automaticas()
        if self.fila.modo == "palavras":        # a página nova também é verificada
            self.verificar_texto()
        elif self.fila.modo == "lances":
            self.fila.lances.recontar(0)
        self.atualizar_barra()
        self.atualizar_paginas(seguir=True)

    def _sequencia_mudou(self) -> None:
        """A ordem do livro mudou (§12.4): o que a janela guarda por posição sai (os pixmaps
        convertidos), e a gaveta e a aba Diagramas mostram a ordem nova."""
        self._pixmaps.clear()
        self.atualizar_paginas(seguir=True)
        self._diagramas_mudaram()
        total = self.pagina.fonte.total if self.pagina.fonte is not None else 0
        self.seletor.blockSignals(True)
        self.seletor.setMaximum(max(1, total))
        self.seletor.setValue(self.pagina.indice + 1)
        self.seletor.blockSignals(False)
        self.total_de_paginas.setText(f" de {total} ")
        # As ocorrências da busca e a prévia do substituir citam posições de antes.
        if self.resultados.na_previa:
            self.resultados.limpar_previa("A ordem do livro mudou: peça a prévia de novo.")
        else:
            self.resultados.mostrar_ocorrencias([], "A ordem do livro mudou: busque de novo.")

    def _pixmap(self, indice: int, imagem):
        """O QPixmap da página, das últimas 5 convertidas (a conversão leva dezenas de ms)."""
        guardado = self._pixmaps.get(indice)
        if guardado is not None and guardado[0] is imagem:
            self._pixmaps.move_to_end(indice)
            return guardado[1]
        cache = self.pagina.cache
        preparada = cache.preparada(indice, imagem) if cache is not None else None
        # A QImage feita na thread que renderizou: aqui só a cópia para o QPixmap.
        pixmap = (QPixmap.fromImage(preparada.qimage) if preparada is not None
                  else pixmap_da_pagina(imagem))
        self._pixmaps[indice] = (imagem, pixmap)
        while len(self._pixmaps) > 5:
            self._pixmaps.popitem(last=False)
        return pixmap

    def _pre_converter(self) -> None:
        """Converte a próxima provável, se a pré-carga já a renderizou (fora do clique)."""
        p = self.pagina
        if p.cache is not None and p.cache.tem(p.navegador.proxima_provavel):
            self._pixmap(p.navegador.proxima_provavel, p.cache.pagina(p.navegador.proxima_provavel)[0])

    def zoom_de_pagina(self, zoom) -> None:
        """Ctrl+7/8/9: `zoom()` na Imagem e no Glifo; no Documento, o corpo é do Ctrl++ e Ctrl+−, e
        a barra diz onde vale (§3.3)."""
        if self._no_documento():
            self.statusBar().showMessage(
                teclado.com_teclas("Zoom de página: foco na Imagem ({foco_imagem})"), 6000)
        else:
            zoom()

    def _zoom_mudou(self, escala: float, limite: str) -> None:
        self.caixa_de_zoom.blockSignals(True)
        self.caixa_de_zoom.setValue(round(escala * 100))
        self.caixa_de_zoom.blockSignals(False)
        if limite:
            self.statusBar().showMessage(f"zoom {limite}", 3000)

    def _glifos_mudaram(self, gids=None) -> None:
        """`gids`: só esses mudaram (a leitura, não a caixa nem a lista); None: tudo."""
        p = self.pagina
        na_fila = set(p.fila_da_pagina.fila())
        todos = p.gids
        pendentes = {i for i, g in enumerate(todos) if g in na_fila}
        mudados = None if gids is None else [i for i, g in enumerate(todos) if g in gids]
        _pintar_os_boxes(self.visor, p, pendentes, mudados)
        self._selecao_mudou()
        self.relogio_do_texto.start()
        self.relogio_das_paginas.start()        # o estado e os pendentes, na gaveta
        self.atualizar_barra()
        if p.leitor is not None:
            _mostrar_as_contagens(self.treino, p.leitor, len(pendentes), len(p.boxes))

    def _atual_mudou(self) -> None:
        p = self.pagina
        self.atualizar_fila()
        if p.box_atual() is None:
            self.visor.selecionar(None)
            self.treino.limpar(vazios.pagina_nao_reconhecida()
                               if not p.boxes else
                               _sem_pendentes(self.fila.lances.resumo_da_pagina(),
                                              _faltam_ler(p)))
            return
        self.treino.mostrar(p.matriz, p.box_atual(), p.fila_da_pagina.posicao_do_atual(),
                            tomar_o_foco=QApplication.focusWidget() is not self.texto)
        if (sugestao := p.leitura.sugestao_do_atual()) is not None:    # §9.2: o palpite da rede
            self.treino.sugerir(*sugestao)
        elif (troca := p.leitura.sugestao_do_contexto()) is not None:  # a palavra ou a linha desmente
            self.treino.sugerir_pelo_contexto(*troca)
        # A fila e a Imagem levam o Documento e a Linha ao glifo (§6.2).
        self.texto.ir_ao_gid(p.atual, rolar=True)   # §6.2: o Documento rola até o glifo
        self.texto.marcar_atual(p.atual)            # e o marca, também sem o foco nele
        self.visor.marcar_palavra_do_documento(None)    # o contorno do cursor ficaria velho
        self._mostrar_a_linha()
        # Seguir (Ctrl+Shift+L): o item atual fica visível, a 120 px da borda (§3.3).
        self.visor.selecionar(p.indice_de(p.atual), centralizar=self.acao_seguir.isChecked())
        if not self.executor.so_leves():        # a propagação de um Enter não prende o painel
            self.treino.habilitar(False)

    def pintar_texto(self) -> None:
        """O Documento da página, com o realce de cada glifo (§6.1), sem perder o lugar."""
        self.relogio_do_texto.stop()
        p, v = self.pagina, self.verificador
        na_fila = set(p.fila_da_pagina.fila())
        da_fila = p.fila_da_pagina.margens_da_fila()  # a conta que a fila usou, talvez de antes
        estados = _estados_dos_glifos(p.modelo, na_fila)
        estados.update(dict.fromkeys(p.evidencia.agora().fortes, gd.FORTE))
        aviso = _aviso_do_documento(p)
        # A palavra fora do léxico que o usuário aceitou (Enter: revisada) não é mais duvidosa.
        revisados = {b.gid for b in p.modelo.boxes if b.revisado} if p.modelo is not None else set()
        margens = p.fila_da_pagina.gids_de_margem()
        self.texto.montar(p.documento(), p.diagramas, estados, v.gids_desconhecidos() - revisados,
                          p.gids_virtuais(), p.matriz, margens, aviso)
        self._mostrar_a_linha()
        if margens != da_fila:                  # a ordem da fila mudou com a conta nova
            self.atualizar_fila()

    def _selecao_mudou(self) -> None:
        p = self.pagina
        self.visor.marcar_selecao({p.indice_de(g) for g in p.selecao} - {None})
        self.treino.mostrar_selecao(len(p.alvos()) if p.selecao else 0)

    def _aviso_de_ensino(self, *_):
        """O efeito e o conflito de ensinar o caractere do campo (§8.3); no escopo livro da
        fila, também quantos glifos do livro têm a mesma leitura (pelo índice da busca)."""
        p = self.pagina
        efeito, conflito = p.padroes_do_livro.aviso_de_ensino(self.treino.campo.text())
        livro = ""
        if efeito and self.fila.escopo == "livro" and p.atual is not None:
            i = p.indice_de(p.atual)
            lida = p.modelo.boxes[i].entry.char if i is not None else ""
            n = self.busca.contar_leitura(lida) if lida else 0
            livro = f" · {n} no livro" if n else ""
        self.treino.mostrar_aviso_de_ensino(efeito, conflito, livro)

    def _padroes_mudaram(self) -> None:
        """A aba Padrões: as amostras, com a origem, a altura, o efeito e quantos glifos do
        livro cada uma leu (pelo índice da busca, §8.3)."""
        if self.leitor is None or self.projeto is None:
            return
        padroes = self.leitor.padroes
        pasta = Path(padroes.pasta)               # os arquivos são dela (sem resolver cada um)
        lidos = self.busca.lidos_por_amostra() if hasattr(self, "busca") else {}
        detalhes = {}
        for arquivos in self.leitor.padroes_por_caractere().values():
            for arquivo in arquivos:
                meta = padroes.meta_de(arquivo)
                try:
                    nome = Path(arquivo).relative_to(pasta).as_posix()
                except ValueError:
                    nome = ""
                # (posição de agora, gid): pelo gid da amostra, que segue a página (§12.4).
                origem = self.projeto.ordem.origem_da_amostra(meta.get("origem", ""))
                detalhes[str(arquivo)] = {"origem": origem,
                                          "altura": meta.get("altura"),
                                          "efeito": meta.get("efeito"),
                                          "lidos": lidos.get(nome, 0)}
        self.padroes.atualizar(self.leitor.padroes_por_caractere(), detalhes)

    def ir_a_origem(self, pagina: int, gid) -> None:
        """A página e o glifo de onde a amostra veio (a aba Padrões, "ir para"); `pagina` é a
        posição de agora (`projeto.ordem.origem_da_amostra`), ou None se ela saiu do livro."""
        if self.fonte is None or pagina is None or not 0 <= pagina < self.fonte.total:
            if pagina is None:
                self._origem_fora_do_livro(gid)
            return
        if pagina != self.pagina.indice:
            self.ir_para_pagina(pagina)
            self.pintar_texto()
        if gid is not None:
            self._ir_ao_glifo_de_origem(gid)

    def _ir_ao_glifo_de_origem(self, gid) -> None:
        """O glifo na página aberta; o que o corte deixou de fora fica no aviso."""
        if gid in set(self.pagina.gids):
            self.pagina.escolher(gid)
        elif self.pagina.modelo is not None and gid in {
                b.gid for _lugar, b in self.pagina.modelo.fora}:
            self.statusBar().showMessage("O glifo de origem desta amostra saiu da página (o "
                                         "corte o deixou de fora; tirar o corte o devolve).",
                                         AVISO_LONGO_MS)

    def _origem_fora_do_livro(self, gid) -> None:
        """A origem numa página apagada (§12.4): a pergunta na barra para restaurá-la, e o
        Enter a devolve ao lugar e vai ao glifo. A amostra antiga, sem `gid`, não diz qual das
        apagadas era: fica o aviso, e Página › Páginas apagadas… a devolve."""
        from abbychess.modelo import pid_de

        projeto = self.projeto
        apagada = (projeto.sequencia.apagada(pid_de(gid))
                   if projeto is not None and gid is not None else None)
        if apagada is None:
            self.statusBar().showMessage("A página de origem desta amostra saiu do livro.",
                                         6000)
            return
        lugar = (f"depois da página {apagada.posicao}" if apagada.posicao
                 else "no começo do livro")
        self.confirmacao.perguntar(
            f"A página de origem desta amostra foi apagada (estava {lugar}). Restaurá-la e ir "
            "ao glifo? Enter restaura · Esc não",
            functools.partial(self._restaurar_a_origem, apagada.entrada.pid, gid))

    def _restaurar_a_origem(self, pid: int, gid: int) -> None:
        if self.pagina.operacoes.restaurar_paginas([pid]):
            self.ir_a_origem(self.projeto.sequencia.posicao_de(pid), gid)

    def _layout_mudou(self) -> None:
        numeros = self.areas.numeros()
        self.visor.mostrar_zonas(self.areas.zonas, self.areas.atual, self.areas.ordem_clicada,
                                 numeros)
        self._editor_de_area_em_dia(numeros)

    def _editor_de_area_em_dia(self, numeros: dict) -> None:
        """O editor Área com a área escolhida; fora do editor de áreas, ele volta ao Glifo."""
        if not self.visor.modo_areas and self.inspetor.atual() == "area":
            self.inspetor.mostrar("glifo")
        a = self.areas
        if a.atual is None or not 0 <= a.atual < len(a.zonas):
            self.editor_de_area.mostrar(None, 0, "")
            return
        zona = a.zonas[a.atual]
        self.editor_de_area.mostrar(numeros.get(zona.id, a.atual + 1), len(a.zonas), zona.funcao)

    def _area_escolhida(self, _indice: int) -> None:
        """O clique numa área abre o editor dela; no Ordenar, o clique diz a ordem (§3.1)."""
        if not self.areas.ordenando and self.areas.atual is not None:
            self.inspetor.mostrar("area")

    def _palavra_mudou(self) -> None:
        v, p = self.verificador, self.pagina
        palavra = v.atual()
        if palavra is None:
            self.visor.marcar_palavra(None)
            self.verificacao.limpar("Nenhuma palavra desconhecida nesta página.")
            return
        self.verificacao.mostrar(p.matriz, p.boxes, palavra, v.posicao, len(v.desconhecidas))
        self.visor.marcar_palavra(vf.caixa_da_palavra(p.boxes, palavra.indices))

    def _linha_de_lance_mudou(self) -> None:
        """A fila Lances (F-4): a linha no editor Palavra, na Imagem, na Linha e no Documento."""
        if self.fila.modo != "lances":
            return
        p, lances = self.pagina, self.fila.lances
        linha = lances.atual()
        self.atualizar_fila()
        if linha is None:
            self.visor.marcar_palavra(None)
            self.verificacao.limpar(lances.mensagem_vazia())
            return
        palavra = lances.como_palavra(linha)
        self.verificacao.mostrar(p.matriz, p.boxes, palavra, lances.posicao, len(lances.linhas))
        self.visor.marcar_palavra(vf.caixa_da_palavra(p.boxes, palavra.indices))
        self.visor.mostrar_caixa(vf.caixa_da_palavra(p.boxes, palavra.indices))
        self.texto.ir_ao_gid(linha.gids[0])
        de_lance = set(linha.linha.gids_de_lance)
        self.linha.mostrar(p.matriz, [p.box(g) for g in linha.gids], None,
                           sublinhados={k for k, g in enumerate(linha.gids) if g in de_lance},
                           fortes={k for k, g in enumerate(linha.gids) if g in linha.ilegais})

    def _acoes_mudaram(self) -> None:
        acoes.atualizar(self)

    def _mensagem(self, texto: str, ms: int) -> None:
        # Os controladores não têm Qt nem perfil: citam a tecla por `{id}`, trocada aqui.
        texto = teclado.com_teclas(texto, so_conhecidas=True)
        if ms == 0 and self.executor.na_fila:   # o progresso não apaga a fila da barra
            texto += f" Na fila: {', '.join(self.executor.na_fila)}."
        self.statusBar().showMessage(texto, ms)

    def _falha(self, titulo: str, texto: str) -> None:
        self.statusBar().showMessage(f"{titulo}: falhou.")
        self.registrar_aviso(av.ERRO, titulo, texto)
        QMessageBox.critical(self, titulo, texto)

    def _aviso(self, titulo: str, texto: str) -> None:
        self.registrar_aviso(av.AVISO, titulo, texto)
        QMessageBox.warning(self, titulo, texto)

    def _relatorio(self, titulo: str, linhas) -> None:
        """Um relatório (o da exportação, §12.2): vai a Resultados / Avisos, sem diálogo, um
        aviso por linha (o duplo clique no item abre a página que ele cita)."""
        for linha in linhas:
            self.registrar_aviso(av.AVISO, titulo, linha)

    def _gravacao_falhou(self, indice, erro) -> None:
        """CA-4.2 (A2): a falha de gravação vai para Avisos, além da barra; e a faixa fica à
        vista até a página gravar (CA-U6)."""
        self._avisar_da_pagina("Gravação", indice, (
            f"não foi gravada ({erro}). Ela continua com as mudanças em memória e o programa "
            "tenta de novo; não feche antes de liberar o disco."))
        self.faixa_de_gravacao.mostrar(indice, erro, lambda: (
            self.projeto is not None and self.projeto.paginas_em_memoria.falhando))

    def _avisar_da_pagina(self, titulo: str, indice, resto: str) -> None:
        """O aviso de uma página na barra e em Avisos: "A página N " + `resto`."""
        pagina = f"A página {indice + 1}" if indice is not None else "Uma página"
        texto = f"{pagina} {resto}"
        self.statusBar().showMessage(texto)
        self.registrar_aviso(av.ERRO, titulo, texto)

    def ligar_os_avisos_do_projeto(self, projeto) -> None:
        """Os avisos do projeto que abre: a falha de gravação e a página ilegível (que chegam
        de qualquer thread, pelos sinais), e o registro de Avisos dele."""
        projeto.ao_falhar_gravacao = self.falha_de_gravacao.emit
        projeto.ao_achar_ilegivel = self.pagina_ilegivel.emit
        self.abrir_avisos_do_projeto(projeto)

    def _pagina_ilegivel(self, indice, guardado) -> None:
        """SPEC-qualidade Q-P7: a página cujo arquivo não se lê passa a não reconhecida; o
        aviso diz qual e onde ficou o arquivo de antes."""
        onde = (f" O arquivo dela foi guardado em paginas/{guardado}." if guardado else "")
        self._avisar_da_pagina("Página ilegível", indice, (
            f"estava com o arquivo ilegível e ficou como não reconhecida.{onde} "
            + teclado.com_teclas("Reconheça-a de novo ({reconhecer_pagina}).")))

    def _ocupado_mudou(self, ocupado: bool, titulo: str) -> None:
        self.progresso.setVisible(ocupado)
        self.progresso.setRange(0, 0)
        if ocupado and not self.executor.so_leves():
            self._mensagem_da_tarefa = f"{titulo}…"
            self.statusBar().showMessage(self._mensagem_da_tarefa)
            self.treino.habilitar(False)
        elif ocupado:
            pass                                # a propagação: o painel vale, e a mensagem
                                                # do Enter fica na barra
        else:
            self._limpar_a_mensagem_da_tarefa()
        if not ocupado and self.pagina.box_atual() is not None:
            self._devolver_o_painel()
        acoes.atualizar(self)

    def _devolver_o_painel(self) -> None:
        """A tarefa acabou com um glifo atual: o painel de treino volta, e o campo pega o foco
        de ninguém. Quem o tem por escolha fica com ele, o Documento também (U-1)."""
        self.treino.habilitar(True)
        foco = QApplication.focusWidget()
        if (self.inspetor.atual() == "glifo" and self.isActiveWindow()
                and (foco is None or self.treino.isAncestorOf(foco))):
            self.treino.campo.setFocus()

    def _limpar_a_mensagem_da_tarefa(self) -> None:
        """A tarefa acabou: o "Carregando o léxico…" dela sai da barra (uma mensagem que
        veio depois, como o resultado, fica)."""
        mensagem = self._mensagem_da_tarefa
        if mensagem and self.statusBar().currentMessage().startswith(mensagem):
            self.statusBar().clearMessage()
        self._mensagem_da_tarefa = None

    def _fila_mudou(self, titulos: list) -> None:
        if self.executor.titulo:
            self._mensagem_da_tarefa = f"{self.executor.titulo}…"      # a tarefa que roda agora
            fila = f" Na fila: {', '.join(titulos)}." if titulos else ""
            self.statusBar().showMessage(f"{self.executor.titulo}…{fila}")

    def _progredir(self, feito: int, total: int) -> None:
        self.progresso.setRange(0, max(total, 1))
        self.progresso.setValue(feito)              # o rótulo do lote é de `_lote_progrediu`


def _pintar_os_boxes(visor, p, pendentes: set, mudados) -> None:
    """Só os boxes `mudados`, se o visor consegue; senão todos, com os diagramas."""
    if mudados is None or not visor.repintar_boxes(p.boxes, pendentes, mudados):
        diagramas = p.diagramas
        visor.mostrar_boxes(p.boxes, pendentes, [d.caixa for d in diagramas],
                            [estilo.cor_do_diagrama(d) for d in diagramas])


def _mostrar_as_contagens(treino, leitor, pendentes: int, glifos: int) -> None:
    """Os pendentes, os glifos e as amostras do livro, no painel de treino."""
    por_char = leitor.padroes_por_caractere()
    treino.mostrar_contagens(pendentes, glifos, sum(len(v) for v in por_char.values()),
                             len(por_char))


def _faltam_ler(p) -> int:
    """Quantas páginas do livro ainda não foram lidas."""
    if p.projeto is None or p.fonte is None:
        return 0
    return max(0, p.fonte.total - len(p.projeto.resumo.paginas_lidas()))


def _sem_pendentes(resumo: dict, faltam_ler: int = 0) -> str:
    """A tela da fila de glifos vazia: com lance por conferir, nunca "nada a revisar" (F-4); com
    página por ler, a tecla do lote (U-3)."""
    resto = teclado.com_teclas("Clique num glifo para corrigi-lo, ou vá para o próximo pendente do "
                               "livro ({proxima_pagina_pendente}).")
    if faltam_ler:
        resto += teclado.com_teclas(f" Faltam ler {faltam_ler} página(s): {{reconhecer_livro}}.")
    if resumo["nao_conferidos"]:
        return teclado.com_teclas(f"Sem glifos na fila. {resumo['nao_conferidos']} lances não "
                                  "conferidos: {fila_lances} confere. ") + resto
    return f"Nada a revisar nesta página. {resto}"


def _estados_dos_glifos(modelo, na_fila: set) -> dict:
    """gid → o estado do realce no Documento (§6.1); vazio sem modelo."""
    return {b.gid: gd.estado(b.entry, b.gid in na_fila) for b in modelo.boxes} \
        if modelo is not None else {}


def _aviso_do_documento(p) -> str:
    """O texto do Documento vazio: na página não reconhecida, com a saúde do livro."""
    if p.modelo is not None and tipo_de_pagina.tratada_como_imagem(p.modelo):
        return vazios.tratada_como_imagem()
    aviso = vazios.nada_reconhecido() if p.reconhecida else vazios.pagina_nao_reconhecida()
    if not p.reconhecida and p.projeto is not None:
        saude = lv.saude(p.projeto, p.leitor.arquivos_de_padrao() if p.leitor else 0)
        if saude.paginas:
            aviso = f"{vazios.saude_do_livro(saude)}\n\n{aviso}"
    return aviso
