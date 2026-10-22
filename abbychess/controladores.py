"""Os outros controladores da janela (SPEC §14.1): áreas, verificação, diagramas, livro e busca.

Cada um trabalha sobre a página aberta do `ControladorDePagina` e fala pelos mesmos
`Eventos`. Os que acrescentam:

- `ControladorDeLayout`: `layout_mudou`;
- `ControladorDeVerificacao`: `palavra_mudou` (a palavra desconhecida a mostrar, ou nenhuma);
- `ControladorDeDiagramas`: `conferir(indice)` (a janela abre a conferência);
- `ControladorDoLivro`: `projeto_aberto`, `lote_mudou`;
- `ControladorDaBusca`: `busca_terminou`, `busca_falhou`, `indice_mudou`.

Sem Qt. Os diálogos (que intervalo ler, onde exportar) são da janela; aqui chegam as
respostas.
"""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import CancelledError
from pathlib import Path
from typing import List, Optional, Sequence

from abbychess import diagramas as dg
from abbychess import edicao as ed
from abbychess import exportar as ex
from abbychess import historico as hs
from abbychess import lances as lc
from abbychess import livro
from abbychess import lote as lt
from abbychess import servidor_de_leitura as sl
from abbychess import verificacao as vf
from abbychess import zonas as zn
from abbychess.controlador import TEMPO_DO_PEDIDO, ControladorDePagina
from abbychess.leitor import LeitorDoLivro, congelar_para_a_coleta_de_lixo

log = logging.getLogger(__name__)

#: O que o último lote deixou para retomar, na pasta do projeto.
ARQUIVO_DO_LOTE = "lote.json"


# ----------------------------------------------------------------------
# As áreas da página (o editor de áreas)
# ----------------------------------------------------------------------

class ControladorDeLayout:
    """As áreas da página: desenhar, escolher, mover, apagar, trocar o tipo e as automáticas."""

    def __init__(self, pagina: ControladorDePagina):
        self.pagina = pagina
        self.eventos = pagina.eventos
        #: A área escolhida (posição na lista), ou None.
        self.atual: Optional[int] = None
        self._ordenacao: Optional[List[int]] = None
        self.modelo: Optional[zn.ModeloDeAreas] = None
        pagina.eventos.ligar("pagina_trocou", self._pagina_trocou)

    @property
    def zonas(self) -> list:
        return self.pagina.zonas

    def _pagina_trocou(self) -> None:
        self.atual = None
        self._ordenacao = None
        self.eventos.emitir("layout_mudou")

    def _trocar(self, zonas: Sequence[zn.Zona], atual: Optional[int], descricao: str,
                juntar=None) -> None:
        """As áreas novas da página, numa transação do desfazer (§14.2); mudar áreas não
        muda o estado da página."""
        p = self.pagina
        if not zonas and p.modelo is None:
            self.atual = None                    # nada a gravar numa página que não existe
        else:
            antes = p._instantaneo()
            modelo = p._pagina_para_editar()
            modelo.zonas = list(zonas)
            p._mudou(modelo, p.indice, descricao, antes, evento=None, juntar=juntar)
            self.atual = atual
        self.eventos.emitir("layout_mudou")

    def automaticas(self) -> None:
        """As áreas que a segmentação sugere: pelos boxes lidos, ou segmentando agora."""
        p = self.pagina
        if p.imagem is None:
            return
        largura, altura = p.imagem.size
        if p.boxes:
            self._automaticas_prontas(zn.automaticas(p.boxes, p.tabuleiros, largura, altura))
            return
        if p.servidor_parado():
            return
        indice = p.indice

        def preparar():
            if p.indice != indice or p.imagem is None:
                return None
            imagem, leitor = p.imagem, p.leitor
            servidor = p._servidor_para_pedir()

            def trabalho(_progresso):
                if servidor is None:
                    return sl.automaticas(imagem, leitor)
                try:                                  # o árbitro dos colados é o global
                    return servidor.chamar("automaticas", imagem, timeout=TEMPO_DO_PEDIDO)
                except sl.Cancelado:                  # o projeto fechou
                    return None

            def pronto(zonas):
                if zonas is not None and p.indice == indice:
                    self._automaticas_prontas(zonas)
            return trabalho, pronto

        p.tarefa("Achando as áreas", preparar, falhou=p._falhou("Áreas"))

    def _automaticas_prontas(self, zonas) -> None:
        zonas = self._aprender_margens(zonas)
        self._trocar(zonas, None, "Áreas automáticas")
        tipos: dict = {}
        for z in zonas:
            nome = zn.NOMES[z.tipo].lower()
            tipos[nome] = tipos.get(nome, 0) + 1
        resumo = ", ".join(f"{n} {t}" for t, n in tipos.items()) or "nenhuma"
        self.pagina._avisar(f"Áreas automáticas: {resumo}. Corrija e aperte F5.", 10000)

    def _aprender_margens(self, zonas):
        """Dá função às margens atuais pelas repetições das páginas reconhecidas."""
        p = self.pagina
        if p.projeto is None or p.imagem is None:
            return zonas
        paginas = {}
        for indice in p.projeto.paginas_lidas():
            modelo = p.modelo if indice == p.indice else p.projeto.carregar_modelo(indice)
            if modelo is None:
                continue
            lidos = [b.entry for b in modelo.boxes if b.entry.char]
            # Todas as páginas do livro são renderizadas no mesmo DPI. A altura aberta
            # evita renderizar as demais só para aprender a margem; pequenas variações de
            # mídia não atravessam as faixas conservadoras de 10% e 3%.
            paginas[indice] = (lidos, p.imagem.height)
        if p.indice not in paginas:
            lidos = [b.entry for b in (p.modelo.boxes if p.modelo else []) if b.entry.char]
            paginas[p.indice] = (lidos, p.imagem.height)
        funcoes = ex.funcoes_das_margens(paginas).get(p.indice, {})
        return zn.aplicar_funcoes_de_margem(zonas, paginas[p.indice][0], funcoes)

    def desenhar(self, x1: int, y1: int, x2: int, y2: int) -> None:
        p = self.pagina
        if p.imagem is None:
            return
        largura, altura = p.imagem.size
        try:
            zona = zn.nova(zn.TEXTO, (x1, y1, x2, y2), largura, altura)
        except ValueError as erro:
            p._avisar(f"Não criou a área: {erro}", 6000)
            return
        zonas = self.zonas + [zona]
        self._trocar(zonas, len(zonas) - 1, "Desenhar área")
        p._avisar(f"Área {len(zonas)} de texto criada. 2 diagrama, 3 imagem, 4 ignorar.", 6000)

    def escolher(self, indice: int) -> None:
        if self._ordenacao is not None and 0 <= indice < len(self.zonas):
            if indice not in self._ordenacao:
                self._ordenacao.append(indice)
            if len(self._ordenacao) == len(self.zonas):
                self._trocar(zn.ordenar(self.zonas, self._ordenacao), indice, "Ordenar áreas")
                self._ordenacao = None
            else:
                self.atual = indice
                self.eventos.emitir("layout_mudou")
                self.eventos.emitir("acoes_mudaram")
            return
        self.atual = indice if 0 <= indice < len(self.zonas) else None
        self.eventos.emitir("layout_mudou")
        self.eventos.emitir("acoes_mudaram")

    def arrastar(self, indice: int, bordas: str, dx: int, dy: int) -> None:
        p = self.pagina
        zonas = self.zonas
        if not 0 <= indice < len(zonas) or p.imagem is None:
            return
        largura, altura = p.imagem.size
        zonas[indice] = zn.arrastar(zonas[indice], bordas, dx, dy, largura, altura)
        # Os arrastes seguidos da mesma área são um passo só do desfazer.
        self._trocar(zonas, indice, "Mover área", juntar=("area", p.indice, indice))

    def apagar(self, indice: int) -> None:
        zonas = self.zonas
        if not 0 <= indice < len(zonas):
            return
        del zonas[indice]
        self._trocar(zonas, None, "Apagar área")
        aviso = "" if zonas else " Sem áreas, a página volta à segmentação automática."
        self.pagina._avisar(f"Área apagada.{aviso}", 6000)

    def trocar_tipo(self, indice: int, tipo: str) -> None:
        zonas = self.zonas
        if not 0 <= indice < len(zonas):
            return
        zn.trocar_tipo(zonas, indice, tipo)
        self._trocar(zonas, indice, "Trocar o tipo da área")
        self.pagina._avisar(f"Área {indice + 1}: {zn.NOMES[tipo].lower()}.", 5000)

    def trocar_funcao(self, indice: int, funcao: str) -> None:
        zonas = self.zonas
        if not 0 <= indice < len(zonas):
            return
        zn.trocar_funcao(zonas, indice, funcao)
        self._trocar(zonas, indice, "Trocar a função da área")
        self.pagina._avisar(f"Área {indice + 1}: {funcao.replace('_', ' ')}.", 5000)

    def trocar_funcao_atual(self, funcao: str) -> None:
        if self.atual is not None:
            self.trocar_funcao(self.atual, funcao)

    def iniciar_ordenacao(self) -> None:
        if not self.zonas:
            return
        self._ordenacao = []
        self.atual = None
        self.eventos.emitir("layout_mudou")
        self.pagina._avisar("Ordenar áreas: clique em cada uma na ordem de leitura; Esc cancela.",
                            8000)

    def cancelar_ordenacao(self) -> None:
        if self._ordenacao is not None:
            self._ordenacao = None
            self.atual = None
            self.eventos.emitir("layout_mudou")
            self.pagina._avisar("Ordenação cancelada.", 4000)

    def salvar_modelo(self) -> None:
        p = self.pagina
        if p.imagem is None or not self.zonas:
            return
        largura, altura = p.imagem.size
        self.modelo = zn.ModeloDeAreas(largura, altura, tuple(self.zonas))
        p._avisar(f"Modelo salvo com {len(self.zonas)} área(s).", 5000)

    def aplicar_modelo_aqui(self) -> None:
        p = self.pagina
        if self.modelo is None or p.imagem is None:
            return
        try:
            zonas = self.modelo.aplicar(*p.imagem.size)
        except ValueError as erro:
            p._avisar(f"Modelo não aplicado: {erro}", 7000)
            return
        self._trocar(zonas, None, "Aplicar modelo de áreas")

    def aplicar_modelo(self, indices: Sequence[int]) -> None:
        """Aplica o modelo a um intervalo já filtrado (todos, pares ou ímpares).

        Páginas de outra resolução são recusadas; todas as aceitas formam um único passo
        do desfazer do projeto.
        """
        p, modelo = self.pagina, self.modelo
        if modelo is None or p.projeto is None or p.fonte is None:
            return
        mudancas, recusadas = {}, []
        for indice in sorted(set(indices)):
            if not 0 <= indice < p.fonte.total:
                continue
            largura, altura = p.fonte.pagina(indice).size
            try:
                zonas = modelo.aplicar(largura, altura)
            except ValueError:
                recusadas.append(indice + 1)
                continue
            pagina = p.projeto.pagina_para_editar(indice)
            antes = pagina.instantaneo()
            pagina.zonas = zonas
            pagina.zonas = zn.vincular_legendas(zn.com_ids(pagina.zonas), pagina.diagramas)
            mudancas[pagina.pid] = hs.mudanca(antes, pagina.instantaneo())
            p.projeto.agendar(pagina)
        if mudancas:
            p.historico.registrar(hs.Transacao("Aplicar modelo de áreas", mudancas))
            p.eventos.emitir("acoes_mudaram")
            if p.modelo is not None and p.modelo.pid in mudancas:
                self.atual = None
                p.eventos.emitir("layout_mudou")
        complemento = f"; recusadas por resolução: {recusadas}" if recusadas else ""
        p._avisar(f"Modelo aplicado a {len(mudancas)} página(s){complemento}.", 8000)

    def reconhecer_atual(self) -> None:
        if self.atual is not None and 0 <= self.atual < len(self.zonas):
            self.pagina.reconhecer_zona(self.zonas[self.atual])


# ----------------------------------------------------------------------
# A verificação de texto (F7)
# ----------------------------------------------------------------------

class ControladorDeVerificacao:
    """As palavras que o léxico não conhece, uma por vez, e a correção delas."""

    def __init__(self, pagina: ControladorDePagina):
        self.pagina = pagina
        self.eventos = pagina.eventos
        self.lexico = None
        self.ignoradas: set = set()
        self.desconhecidas: List[vf.Desconhecida] = []
        self.posicao = 0
        #: Os gids da página quando as palavras foram contadas (os índices delas são desta
        #: lista): uma edição depois disso não troca o glifo de uma correção.
        self._gids: List[int] = []
        pagina.eventos.ligar("pagina_trocou", self._pagina_trocou)

    def esquecer_projeto(self) -> None:
        self.lexico, self.ignoradas = None, set()

    def _pagina_trocou(self) -> None:
        self.desconhecidas, self.posicao, self._gids = [], 0, []

    def verificar(self) -> bool:
        """F7: carrega o léxico (fora da interface, na primeira vez) e conta as palavras.
        Devolve se o léxico já estava pronto (a janela mostra a aba agora)."""
        p = self.pagina
        if p.projeto is None or not p.boxes:
            return False
        if self.lexico is not None:
            self.posicao = 0
            return True
        projeto = p.projeto
        extras = [projeto.fonte.with_name(projeto.fonte.stem + ".lexico.txt")]

        def preparar():
            def trabalho(_progresso):
                return vf.carregar_lexico(projeto.dados.idioma, projeto.arquivo_do_lexico, extras)

            def pronto(lexico):
                self.lexico = lexico
                if not lexico.sinaliza:
                    p._avisar(f"Não há léxico para o idioma '{projeto.dados.idioma}' no "
                              "PyBoxEditor.", 8000)
                self.eventos.emitir("verificacao_pronta")
            return trabalho, pronto

        p.tarefa("Carregando o léxico", preparar, falhou=p._falhou("Léxico"))
        return False

    def recontar(self, posicao: Optional[int] = None) -> None:
        if self.lexico is None:
            return
        p = self.pagina
        self._gids = p.gids
        decididas = p.modelo.decisoes.quebras if p.modelo is not None else frozenset()
        quebras = [i for i, g in enumerate(self._gids) if g in decididas]
        self.desconhecidas = vf.desconhecidas(p.boxes, self.lexico, self.ignoradas, quebras)
        self.mostrar(self.posicao if posicao is None else posicao)

    def mostrar(self, posicao: int) -> None:
        if not self.desconhecidas:
            self.posicao = 0
        else:
            self.posicao = posicao % len(self.desconhecidas)
        self.eventos.emitir("palavra_mudou")

    def atual(self) -> Optional[vf.Desconhecida]:
        if not self.desconhecidas:
            return None
        return self.desconhecidas[self.posicao % len(self.desconhecidas)]

    def andar(self, passo: int) -> None:
        if self.desconhecidas:
            self.mostrar(self.posicao + passo)

    def gids_desconhecidos(self) -> set:
        """Os gids das palavras desconhecidas da última contagem (o ondulado do Documento)."""
        if self.lexico is None:
            return set()
        return {self._gids[i] for d in self.desconhecidas for i in d.indices
                if i < len(self._gids)}

    def gids_da_palavra(self, palavra: vf.Desconhecida) -> Optional[List[int]]:
        """Os gids da palavra, ou None se algum glifo dela saiu desde a contagem."""
        vivos = set(self.pagina.gids)
        gids = [self._gids[i] for i in palavra.indices if i < len(self._gids)]
        if len(gids) != len(palavra.indices) or not set(gids) <= vivos:
            return None
        return gids

    def corrigir(self, texto: str, ensinar: bool = False) -> None:
        """Grava o texto nos glifos da palavra; com `ensinar`, ensina os que mudaram. A
        palavra é a de agora; a correção, na vez dela na fila."""
        palavra = self.atual()
        if palavra is None:
            return
        gids = self.gids_da_palavra(palavra)
        posicao = self.posicao
        self.pagina._editar("Corrigindo a palavra",
                            lambda: self._corrigir(gids, posicao, texto, ensinar))

    def _corrigir(self, gids, posicao: int, texto: str, ensinar: bool) -> None:
        p = self.pagina
        if gids is None or p._vivos(gids) != gids:
            self.recontar()
            p._avisar("A página mudou desde a contagem; as palavras foram contadas de novo.",
                      6000)
            return
        antes = p._instantaneo()
        entries = [ed.copia(p.box(g)) for g in gids]
        indices = list(range(len(entries)))
        try:
            espacos = vf.quebras(entries, indices, texto)
            mudados = vf.corrigir(entries, indices, texto)
        except ValueError as erro:
            p._avisar(f"Não corrigiu: {erro}", 8000)
            return
        for k, _char in mudados:
            ed.trocar(p.modelo, gids[k], entries[k])
        espacos = [k for k in espacos if gids[k] not in p.modelo.decisoes.quebras]
        for k in espacos:                         # o espaço que a leitura não viu
            ed.quebrar(p.modelo, gids[k])
        descricao = f"Corrigir '{texto}'"
        # A correção e o ensino que vem dela são um passo só do desfazer.
        passo = ("palavra", object())             # uma chave só deste comando
        p._mudou(p.modelo, p.indice, descricao, antes, juntar=passo)

        def depois(mensagem: str) -> None:
            self.recontar(posicao)
            atual = self.atual()
            if atual is not None and self.gids_da_palavra(atual) == gids:
                self.mostrar(posicao + 1)         # continua desconhecida: segue adiante
            p._avisar(mensagem, 6000)

        separadas = f", {len(espacos)} palavra(s) separada(s)" if espacos else ""
        if not ensinar or not mudados or p.leitor is None:
            depois(f"'{texto}': {len(mudados)} glifo(s) corrigido(s){separadas}.")
            return
        por_char: dict = {}
        for k, char in mudados:
            por_char.setdefault(char, []).append(gids[k])

        def ensinou(resolvidos: int) -> None:
            extra = f"; os padrões resolveram mais {resolvidos} na página" if resolvidos else ""
            depois(f"'{texto}': {len(mudados)} glifo(s) corrigido(s) e ensinado(s)"
                   f"{separadas}{extra}.")

        p.ensinar_gids(por_char, descricao, ensinou, juntar=passo)

    def ignorar_todas(self) -> None:
        palavra = self.atual()
        if palavra is not None:
            self.ignoradas.add(palavra.palavra.lower())
            self.recontar()

    def adicionar(self, texto: str) -> None:
        """Põe a palavra (ou `texto`, se o usuário a corrigiu no campo) no dicionário do livro."""
        p = self.pagina
        palavra = self.atual()
        if palavra is None or self.lexico is None or p.projeto is None:
            return
        texto = texto.strip() or palavra.palavra
        if p.projeto.somente_leitura:
            p._avisar("Projeto aberto só para leitura: nada é gravado.", 6000)
            return
        if not vf.adicionar(self.lexico, texto, p.projeto.arquivo_do_lexico):
            p._avisar(f"'{texto}' não entra no dicionário (já está, ou não é palavra nem nome "
                      "como L.Shamkovich).", 6000)
            return
        self.recontar()
        p._avisar(f"'{texto}' entrou no dicionário do livro.", 6000)

    def gid_do_glifo(self, indice: int) -> Optional[int]:
        """O glifo clicado no recorte da palavra (índice da contagem), pelo gid."""
        if 0 <= indice < len(self._gids) and self._gids[indice] in set(self.pagina.gids):
            return self._gids[indice]
        return None


# ----------------------------------------------------------------------
# Os diagramas
# ----------------------------------------------------------------------

class ControladorDeDiagramas:
    """A conferência dos diagramas: lê os que faltam e grava o que foi conferido."""

    def __init__(self, pagina: ControladorDePagina):
        self.pagina = pagina
        self.eventos = pagina.eventos

    def proximo_do_livro(self) -> None:
        """F8: o primeiro diagrama ainda não conferido desta página, ou a próxima página do
        livro que tem um (dando a volta no livro), aberta já na conferência."""
        p = self.pagina
        if not p.pronto:
            return
        if any(not d.conferido for d in p.diagramas):
            self.conferir()
            return
        resumo = p.projeto.resumo_do_livro()
        com = sorted(i for i, r in resumo.items() if r.get("diagramas_por_conferir", 0) > 0)
        proxima = next((i for i in com if i > p.indice), com[0] if com else None)
        if proxima is None or proxima == p.indice:
            p._avisar("Não há diagrama por conferir no livro.", 6000)
            return
        if p.ir_para(proxima):
            self.conferir()

    def vizinho_do_livro(self, passo: int) -> None:
        """PgDn (+1) na ponta da página: o primeiro diagrama da próxima página que tem algum;
        PgUp (−1): o último da anterior. Não dá a volta no livro."""
        p = self.pagina
        if not p.pronto:
            return
        resumo = p.projeto.resumo_do_livro()
        com = sorted(i for i, r in resumo.items() if r.get("diagramas", 0) > 0)
        if passo > 0:
            alvo = next((i for i in com if i > p.indice), None)
        else:
            alvo = next((i for i in reversed(com) if i < p.indice), None)
        if alvo is None:
            p._avisar(f"Não há diagrama {'depois' if passo > 0 else 'antes'} deste no livro.",
                      5000)
            return
        if not p.ir_para(alvo):
            p._avisar(f"A página {alvo + 1} não abriu.", 5000)
            return
        self.conferir(0 if passo > 0 else max(0, len(p.diagramas) - 1))

    def do_livro(self, pronto) -> None:
        """Os diagramas de todas as páginas que têm algum, fora da interface: `pronto` recebe
        [(índice da página, [DiagramaLido])] (a aba Diagramas), um por tabuleiro, os por ler
        também (`para_caixas`, a mesma lista de `ControladorDePagina.diagramas`: o índice do
        item é o da conferência). Lê sem passar pelo cache de páginas (`ler_sem_guardar`)."""
        p = self.pagina
        if p.projeto is None:
            return
        projeto = p.projeto

        def preparar():
            com = sorted(i for i, r in projeto.resumo_do_livro().items()
                         if r.get("diagramas", 0) > 0)

            def trabalho(_progresso):
                saida = []
                for i in com:
                    pagina = projeto.ler_sem_guardar(i)
                    if pagina is not None:
                        saida.append((i, dg.para_caixas(pagina.tabuleiros, pagina.diagramas)))
                return saida

            def chegou(paginas):
                if p.projeto is projeto:
                    pronto(paginas)
            return trabalho, chegou

        p.tarefa("Lendo os diagramas do livro", preparar,
                 falhou=p._falhou("Diagramas do livro"))

    def clicado(self, x: int, y: int) -> None:
        indice = dg.diagrama_em(self.pagina.diagramas, x, y)
        if indice is not None:
            self.conferir(indice)

    def conferir(self, indice: Optional[int] = None) -> None:
        """Abre a conferência no diagrama pedido, ou no primeiro ainda não conferido. Os que
        ainda não foram lidos (página gravada antes da leitura dos diagramas) são lidos
        antes, fora da interface."""
        p = self.pagina
        if not p.pronto or p.imagem is None:
            return
        diagramas = p.diagramas
        if not diagramas:
            p._avisar("Não há diagrama nesta página.", 5000)
            return
        if indice is None:
            indice = next((i for i, d in enumerate(diagramas) if not d.conferido), 0)
        if not any(not d.lido and not d.erro for d in diagramas):
            self._abrir(indice)
            return
        if p.servidor_parado():
            return
        pagina_indice = p.indice

        def preparar():
            pagina = p.modelo
            if p.indice != pagina_indice or pagina is None:
                return None
            atuais = dg.para_caixas(pagina.tabuleiros, pagina.diagramas)
            por_ler = [i for i, d in enumerate(atuais) if not d.lido and not d.erro]
            imagem, leitor, boxes = p.imagem, p.leitor, pagina.entries()
            caixas = [atuais[i].caixa for i in por_ler]

            servidor = p._servidor_para_pedir()

            def trabalho(_progresso):
                if servidor is None:
                    return sl.ler_diagramas(imagem, caixas, boxes, leitor)
                try:
                    return servidor.chamar("ler_diagramas", (imagem, caixas, boxes),
                                           timeout=TEMPO_DO_PEDIDO)
                except sl.Cancelado:                  # o projeto fechou
                    return None

            def pronto(lidos):
                if lidos is None:
                    return
                # Na página que pediu, mesmo que o usuário tenha ido a outra.
                novos = dg.para_caixas(pagina.tabuleiros, pagina.diagramas)
                for lido in lidos:
                    for i, d in enumerate(novos):
                        if d.caixa == lido.caixa and not d.lido:
                            novos[i] = lido
                pagina.diagramas = dg.com_ids(novos)
                pagina.diagramas = lc.validar_pagina(pagina, p.projeto.dados.idioma)
                p._gravar(pagina)
                if pagina is p.modelo:
                    self.eventos.emitir("glifos_mudaram", None)
                    self._abrir(indice)
            return trabalho, pronto

        p.executar("Lendo os diagramas", preparar, falhou=p._falhou("Ler os diagramas"))

    def _abrir(self, indice: int) -> None:
        diagramas = self.pagina.diagramas
        if not 0 <= indice < len(diagramas):
            self.pagina._avisar("O diagrama pedido não está mais na página.", 6000)
            return
        d = diagramas[indice]
        if not d.lido:
            self.pagina._avisar(f"O diagrama não foi lido: {d.erro}", 8000)
            return
        self.eventos.emitir("conferir", indice)

    def aplicar(self, caixa, tabuleiro, tudo: bool) -> bool:
        """Grava o diagrama conferido, refaz o texto e guarda as amostras no projeto.

        O diagrama é achado pela `caixa`, não pelo índice: entre abrir a conferência e
        conferir, um F5, um desfazer ou a edição de áreas podem ter mudado a lista. Devolve
        se gravou (falso: sem página, projeto só leitura, ou o diagrama sumiu)."""
        p = self.pagina
        if p.modelo is None:
            return False
        if p.projeto.somente_leitura:
            p._avisar("Projeto aberto só para leitura: a conferência não é gravada.", 6000)
            return False
        diagramas = p.diagramas
        indice = next((i for i, d in enumerate(diagramas)
                       if tuple(d.caixa) == tuple(caixa)), None)
        if indice is None:
            p._avisar("O diagrama mudou na página (F5, desfazer ou áreas): reabra a "
                      "conferência.", 8000)
            return False
        antes = p._instantaneo()
        diagramas[indice] = diagramas[indice].conferir(tabuleiro)
        p.modelo.diagramas = diagramas
        p._mudou(p.modelo, p.indice, f"Conferir o diagrama {indice + 1}", antes)
        mensagem = f"Diagrama {indice + 1} conferido: {diagramas[indice].fen}"
        if tudo or tabuleiro.corrigidas:
            origem = f"p{p.indice + 1:04d}"
            try:
                caminhos = dg.guardar_amostras(p.imagem, diagramas[indice], tabuleiro,
                                               p.projeto.pasta, origem, tudo=tudo)
            except Exception as erro:  # disco cheio, pasta sem permissão, modelo ausente
                log.exception("as amostras do diagrama não foram guardadas")
                mensagem += f". As amostras não foram guardadas: {erro}"
            else:
                mensagem += f"; {len(caminhos)} amostra(s) guardadas no projeto"
        p._avisar(mensagem, 8000)
        return True


# ----------------------------------------------------------------------
# O livro: abrir, o lote, a revisão entre páginas e a exportação
# ----------------------------------------------------------------------

class _GravadorDoLote:
    """Grava `lote.json` numa thread (o mais novo vence); `esperar` antes de ler ou no fim."""

    def __init__(self):
        self._trava = threading.Lock()
        self._pendente = None
        self._thread: Optional[threading.Thread] = None

    def gravar(self, arquivo, dados) -> None:
        with self._trava:
            self._pendente = (arquivo, dados)
            if self._thread is None:
                self._thread = threading.Thread(target=self._rodar, name="lote-json", daemon=True)
                self._thread.start()

    def _rodar(self) -> None:
        from abbychess import gravacao as gv

        while True:
            with self._trava:
                pendente, self._pendente = self._pendente, None
                if pendente is None:
                    self._thread = None
                    return
            arquivo, dados = pendente
            try:
                if dados is None:
                    gv.apagar(arquivo)
                else:
                    gv.gravar_json(arquivo, dados)
            except OSError as erro:
                log.warning("o lote a retomar não foi gravado: %s", erro)

    def esperar(self, limite: float = 10.0) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(limite)


class ControladorDoLivro:
    """O projeto aberto e o que vale para o livro inteiro."""

    def __init__(self, pagina: ControladorDePagina):
        self.pagina = pagina
        self.eventos = pagina.eventos
        #: O lote em andamento (`lote.CondutorDoLote`), ou None.
        self._condutor = None
        #: O que faltou do lote cancelado, `(indices, refazer)`, para retomar.
        self.restante = None
        #: As páginas que o lote não sobrescreveu (mudadas pelo usuário): Retomar as lê só
        #: com a confirmação dele.
        self.reler_depois: List[int] = []
        self._reler_depois_antes: List[int] = []
        #: "Abrir sem o servidor" nesta sessão (os modelos não carregaram no filho).
        self.sem_servidor = False
        self._gravador_do_lote = _GravadorDoLote()
        self.eventos.ligar("pagina_reconhecida", self._saiu_de_reler_depois)
        self.eventos.ligar("pagina_verificada", self._saiu_de_reler_depois)
        #: O servidor cujo `modelos_prontos` já foi emitido (uma vez por servidor).
        self._modelos_avisados = None
        #: As três páginas do primeiro treino enquanto o lote delas está rodando.
        self._amostra_guiada: Optional[tuple[int, ...]] = None

    @property
    def lote_rodando(self) -> bool:
        return self._condutor is not None

    def abrir(self, projeto, fonte) -> None:
        """Liga o projeto (a fonte já aberta) e prepara a leitura fora da interface; ao fim,
        `projeto_aberto(leitor)` e a última página lida aparece.

        Com o servidor de leitura (§11, o padrão; `ABBY_SERVIDOR=0` o desliga), a interface
        fica só com os padrões do livro e o filho carrega os modelos: a navegação já vale, e
        `modelos_prontos(estado)` vem quando ele termina. Sem servidor, os modelos carregam
        aqui (numa thread) e `modelos_prontos` vem logo depois de `projeto_aberto`."""
        p = self.pagina
        self._largar_lote()
        p.ligar(projeto, fonte, None)
        com_servidor = not self.sem_servidor and os.environ.get("ABBY_SERVIDOR", "1") != "0"

        def preparar():
            def trabalho(_progresso):
                pasta, limiares = projeto.pasta_de_padroes, projeto.dados.limiares
                if com_servidor:
                    leitor = LeitorDoLivro(pasta, limiares=limiares, aguardar=True)
                    servidor = sl.ServidorDeLeitura(
                        pasta, limiares,
                        ao_avisar=lambda titulo, texto, desistiu: self._do_servidor(
                            servidor, "servidor_caiu", (texto, desistiu)),
                        ao_ficar_pronto=lambda estado: self._do_servidor(
                            servidor, "modelos_prontos", estado))
                    return leitor, servidor
                leitor = LeitorDoLivro.com_modelos_globais(pasta, limiares=limiares)
                log.info("congelados para a coleta de lixo: %d objetos",
                         congelar_para_a_coleta_de_lixo())
                return leitor, None

            def pronto(resultado):
                leitor, servidor = resultado
                if p.projeto is not projeto:
                    if servidor is not None:
                        servidor.fechar()
                    return                          # outro projeto foi aberto antes
                self.usar(projeto, fonte, leitor, servidor)
                self.eventos.emitir("projeto_aberto", leitor)
                if servidor is None:
                    self.eventos.emitir("modelos_prontos", sl.estado_do_leitor(leitor))
                elif servidor.estado is not None:   # ficou pronto antes de chegar aqui
                    self._servidor_disse(servidor, "modelos_prontos", servidor.estado)
            return trabalho, pronto

        p.tarefa("Carregando os modelos", preparar, falhou=p._falhou("Carregar os modelos"))

    def _do_servidor(self, servidor, evento: str, valor) -> None:
        """Da thread ouvinte do servidor: o evento vai à thread da interface."""
        self.pagina.executar.na_interface(lambda: self._servidor_disse(servidor, evento, valor))

    def _servidor_disse(self, servidor, evento: str, valor) -> None:
        if self.pagina.servidor is not servidor:
            return                              # de um servidor que já não é o do projeto
        if evento == "modelos_prontos":
            if self._modelos_avisados is servidor:
                return
            self._modelos_avisados = servidor
            self.eventos.emitir("modelos_prontos", valor)
            self.pagina.ler_os_aguardando()     # o que a página aberta deixou esperando
        else:
            # O primeiro tombo só vai para os Avisos; no segundo o servidor desistiu, e a
            # janela oferece reabrir o projeto (§11).
            texto, desistiu = valor             # o `desistiu` da hora do aviso
            self.eventos.emitir(evento, texto, desistiu)
            self.eventos.emitir("acoes_mudaram")        # Retomar desliga com ele parado

    def usar(self, projeto, fonte, leitor, servidor=None) -> None:
        """O projeto com o leitor pronto: abre a última página lida (ou a primeira)."""
        p = self.pagina
        self._largar_lote()
        p.ligar(projeto, fonte, leitor, servidor)
        self._ler_restante()
        lidas = projeto.paginas_lidas()
        p.ir_para(lidas[-1] if lidas else 0)

    def reconhecer(self, indices: Sequence[int], refazer: bool,
                   forcar: Sequence[int] = ()) -> None:
        """Lê as páginas `indices` pelo condutor do lote (`lote.CondutorDoLote`): pelo
        servidor, com a janela livre (as edições não esperam), e gravando cada página aqui,
        na thread da interface (o escritor único, §11)."""
        p = self.pagina
        if not p.pronto:
            return
        if self._condutor is not None:
            p._avisar("O lote já está lendo o livro. Cancele-o (✕ na barra) antes de começar "
                      "outro.", 8000)
            return
        self.restante = None
        self._reler_depois_antes = [i for i in self.reler_depois if i not in indices]
        condutor = lt.CondutorDoLote(
            p, indices, refazer, forcar=forcar, ao_progresso=self._progrediu,
            ao_gravar=lambda indice: self.eventos.emitir("pagina_do_lote", indice),
            ao_fim=lambda resultado: self._fim_do_lote(condutor, resultado))
        self._condutor = condutor
        self._guardar(condutor.indices, refazer, self._reler_depois_antes)
        p.lote_rodando = True
        self.eventos.emitir("lote_mudou")
        self.eventos.emitir("acoes_mudaram")
        condutor.comecar()

    def iniciar_amostra_guiada(self) -> bool:
        """Começa uma vez as páginas 10/50/90% do corpo de um projeto novo."""
        from abbychess import livro as lv

        p = self.pagina
        if not p.pronto or not p.projeto.dados.extras.get("amostra_guiada_pendente"):
            return False
        extras = p.projeto.dados.extras
        candidatos = extras.get(lv.CHAVE_DOS_CANDIDATOS_DA_AMOSTRA)
        if candidatos is None:                  # projeto criado antes desta chave
            inicio, fim = extras.get("intervalo_do_corpo", (0, p.fonte.total - 1))
            candidatos = range(max(0, int(inicio)), min(p.fonte.total - 1, int(fim)) + 1)
        candidatos = [int(i) for i in candidatos if 0 <= int(i) < p.fonte.total]
        indices = tuple(lv.paginas_da_amostra(candidatos))
        if not indices:
            extras["amostra_guiada_pendente"] = False
            p.projeto.salvar()
            return False
        p.projeto.dados.extras["amostra_guiada_pendente"] = False
        p.projeto.dados.extras[lv.CHAVE_DA_AMOSTRA] = list(indices)
        p.projeto.salvar()
        self._amostra_guiada = indices
        self.reconhecer(indices, refazer=False)
        return True

    def _progrediu(self, feitas: int, total: int, estimativa: Optional[float]) -> None:
        condutor = self._condutor
        if condutor is not None and feitas:     # o ponto, a cada página (G1 da rodada 3)
            self._guardar(list(condutor.restante), condutor.refazer,
                          self._reler_depois_de(condutor), agora=False)
        self.eventos.emitir("lote_progresso", feitas, total, estimativa)

    def _fim_do_lote(self, condutor, resultado) -> None:
        if self._condutor is not condutor:
            return                              # de um lote largado (outro projeto)
        era_amostra = self._amostra_guiada is not None
        paginas_da_amostra = self._amostra_guiada or ()
        self._amostra_guiada = None
        self._condutor = None
        self.pagina.lote_rodando = False
        # O que faltou (cancelado, ou o servidor parou) e as páginas para reler depois ficam
        # para "Retomar o lote", guardadas no projeto (`lote.json`).
        faltam = list(condutor.restante) if resultado.cancelado else []
        self._guardar(faltam, condutor.refazer, self._reler_depois_de(condutor))
        mensagem = lt.resumo_do_fim(resultado)
        if resultado.servidor_parou and faltam:
            mensagem += " Reabra o projeto e use Projeto › Retomar o lote."
        elif self.pode_retomar:
            mensagem += " Projeto › Retomar o lote continua."
        self.eventos.emitir("lote_mudou")
        self.eventos.emitir("acoes_mudaram")
        self.eventos.emitir("lote_terminou", mensagem, resultado)
        if era_amostra:
            from abbychess import livro as lv

            completa = (not resultado.cancelado and not resultado.servidor_parou
                        and not resultado.falhas
                        and set(paginas_da_amostra) <= set(resultado.lidas + resultado.puladas))
            extras = self.pagina.projeto.dados.extras
            extras["amostra_guiada_pendente"] = not completa
            if completa:
                resumo = self.pagina.projeto.resumo_do_livro()
                extras[lv.CHAVE_DOS_PENDENTES_INICIAIS] = {
                    str(i): int(resumo.get(i, {}).get("pendentes", 0) or 0)
                    for i in paginas_da_amostra
                }
            self.pagina.projeto.salvar()
            if completa:
                self.eventos.emitir("amostra_terminou", paginas_da_amostra)
        detalhe = " Detalhes em Avisos (⚠)." if lt.tem_detalhe(resultado) else ""
        self.pagina._avisar(mensagem + detalhe, 15000)

    def _reler_depois_de(self, condutor) -> List[int]:
        """As páginas para reler depois: as de antes deste lote que ele não leu, e as dele."""
        antes = [i for i in self._reler_depois_antes if i not in condutor.resultado.lidas]
        return antes + [i for i in condutor.resultado.reler_depois if i not in antes]

    def _arquivo_do_lote(self):
        p = self.pagina
        return Path(p.projeto.pasta) / ARQUIVO_DO_LOTE if p.projeto is not None else None

    def _guardar(self, faltam: Sequence[int], refazer: bool, reler_depois: Sequence[int], *,
                 agora: bool = True) -> None:
        """O que o lote deixou para retomar, na memória e em `lote.json`. É gravado ao começar
        o lote, a cada página (numa thread, `agora=False`: o fsync não fica na janela) e no
        fim; fechar o projeto no meio do lote não perde o ponto, nem deixa valer o arquivo
        de um lote anterior."""
        self.restante = (list(faltam), bool(refazer)) if faltam else None
        self.reler_depois = list(reler_depois)
        arquivo, projeto = self._arquivo_do_lote(), self.pagina.projeto
        if arquivo is None or projeto.somente_leitura:
            return
        dados = None if not faltam and not reler_depois else {
            "paginas": [int(i) for i in faltam], "refazer": bool(refazer),
            "reler_depois": [int(i) for i in reler_depois]}
        self._gravador_do_lote.gravar(arquivo, dados)
        if agora:
            self._gravador_do_lote.esperar()

    def _ler_restante(self) -> None:
        import json

        self._gravador_do_lote.esperar()
        self.restante, self.reler_depois = None, []
        arquivo = self._arquivo_do_lote()
        if arquivo is None or not arquivo.is_file():
            return
        try:
            bruto = json.loads(arquivo.read_text(encoding="utf-8"))
            total = self.pagina.fonte.total
            paginas = [int(i) for i in bruto["paginas"] if 0 <= int(i) < total]
            self.restante = (paginas, bool(bruto["refazer"])) if paginas else None
            self.reler_depois = [int(i) for i in bruto.get("reler_depois", [])
                                 if 0 <= int(i) < total]
        except (OSError, ValueError, KeyError, TypeError) as erro:
            log.warning("o lote a retomar (%s) não abriu: %s", arquivo, erro)

    def _largar_lote(self) -> None:
        """Outro projeto: o lote deste não grava mais nada (o condutor confere a geração); o
        que faltava já está em `lote.json`, gravado a cada página."""
        if self._condutor is not None:
            self._condutor.cancelar()
        self._condutor = None
        self.restante, self.reler_depois = None, []
        self.esperar_a_gravacao()

    def esperar_a_gravacao(self) -> None:
        """O `lote.json` que a thread ainda grava chega ao disco (fechar o projeto ou trocar de
        projeto não perde o ponto da última página)."""
        self._gravador_do_lote.esperar()

    def cancelar(self) -> None:
        """Pede o fim do lote: a página em leitura para no glifo seguinte e fica como estava;
        o que faltou fica para `retomar`."""
        if self._condutor is not None:
            self._condutor.cancelar()
            self.pagina._avisar("Cancelando o lote: a página em leitura para no glifo "
                                "seguinte…", 0)

    def retomar(self, com_reler_depois: bool = False) -> None:
        """Continua o lote cancelado de onde parou (sem ler de novo as já lidas, CA-11.5); com
        `com_reler_depois` (o usuário confirmou), lê também as que ficaram para reler depois,
        que ele tinha mudado (as correções manuais ficam, §4.6)."""
        if not self.pode_retomar:
            if self.restante is not None or self.reler_depois:
                self.pagina._avisar("O servidor de leitura parou: reabra o projeto para "
                                    "retomar o lote.", 8000)
            return
        indices, refazer = self.restante if self.restante is not None else ([], False)
        forcar = list(self.reler_depois) if com_reler_depois else []
        indices = list(indices) + [i for i in forcar if i not in indices]
        if indices:                             # o "refazer" do lote vale para o que faltou
            self.reconhecer(indices, refazer, forcar=forcar)
        else:
            self.pagina._avisar("Nada faltou do lote.", 6000)

    def _saiu_de_reler_depois(self, indice: int) -> None:
        """O F5 releu a página, ou ela foi verificada: não fica mais para reler depois."""
        if indice in self.reler_depois and self._condutor is None:
            faltam, refazer = self.restante if self.restante is not None else ([], False)
            self._guardar(faltam, refazer, [i for i in self.reler_depois if i != indice])
            self.eventos.emitir("acoes_mudaram")

    @property
    def pode_retomar(self) -> bool:
        servidor = self.pagina.servidor
        return ((self.restante is not None or bool(self.reler_depois)) and self._condutor is None
                and not (servidor is not None and servidor.parado))

    def voltar_ao_antes_do_lote(self) -> None:
        """Página › Voltar ao estado antes do lote (§4.6): a página aberta volta a ser a que
        o lote com "refazer" copiou antes de relê-la."""
        p = self.pagina
        if not p.pronto or not p.projeto.tem_antes_do_lote(p.indice):
            p._avisar("Esta página não tem cópia de antes do lote.", 6000)
            return
        try:
            pagina = p.projeto.voltar_ao_antes_do_lote(p.indice)
        except OSError as erro:
            p.eventos.emitir("aviso", "Voltar ao estado antes do lote", str(erro))
            return
        p.historico.tocar(pagina.pid)
        p.ir_para(p.indice, visita=False)
        self.eventos.emitir("acoes_mudaram")
        p._avisar(f"A página {p.indice + 1} voltou ao estado de antes do lote.", 8000)

    def proximo_pendente(self) -> None:
        """F6: o pendente desta página ou, se ela acabou, a próxima página com pendentes."""
        p = self.pagina
        if not p.pronto:
            return
        if p.fila():
            p.ir_ao_primeiro_pendente()
            return
        proxima = livro.proxima_com_pendentes(p.projeto, p.leitor.limiares, p.indice)
        if proxima is None or proxima == p.indice:
            p._avisar("Nada a revisar nas páginas reconhecidas do livro.", 8000)
            return
        p.ir_para(proxima)
        p._avisar(f"Página {proxima + 1}: {len(p.fila())} a revisar.", 6000)

    def exportar(self, destino: Path) -> None:
        """Escreve as páginas reconhecidas em PDF pesquisável, DOCX ou EPUB (pelo sufixo)."""
        p = self.pagina
        projeto = p.projeto

        def preparar():
            def trabalho(progresso):
                return ex.exportar(projeto, destino, progresso=progresso)

            def pronto(resumo: str):
                p._avisar(f"Exportado em {destino.name}: {resumo}", 15000)
            return trabalho, pronto

        p.tarefa(f"Exportando {destino.suffix[1:].upper()}", preparar,
                   falhou=p._falhou("Exportar"))


class ControladorDaFila:
    """A fila da revisão (§8.1): o modo, o escopo, e o próximo e o anterior nele (Alt+↓ /
    Alt+↑, em qualquer painel). No escopo livro (Shift+F7), o fim da fila da página leva à
    próxima página com pendentes (e o começo, à anterior), pelo resumo do `livro.json`; nas
    palavras, à página seguinte; os diagramas são sempre os do livro."""

    #: (modo, nome no seletor do Inspetor), na ordem do F7.
    MODOS = (("confianca", "Confiança"), ("leitura", "Ordem de leitura"),
             ("caractere", "Por caractere"), ("palavras", "Palavras desconhecidas"),
             ("diagramas", "Diagramas por conferir"))
    #: Os modos que andam pelos glifos (o Inspetor mostra o Glifo).
    DE_GLIFOS = ("confianca", "leitura", "caractere")
    #: (escopo, nome), na ordem do Shift+F7.
    ESCOPOS = (("pagina", "página"), ("livro", "livro"))

    def __init__(self, pagina: ControladorDePagina, verificador: ControladorDeVerificacao,
                 conferencia: ControladorDeDiagramas):
        self.pagina, self.verificador, self.conferencia = pagina, verificador, conferencia
        self.eventos = pagina.eventos
        self.modo = "confianca"
        self.escopo = "pagina"

    def nome(self, modo: Optional[str] = None) -> str:
        return dict(self.MODOS)[modo or self.modo]

    def nome_do_escopo(self) -> str:
        return dict(self.ESCOPOS)[self.escopo]

    def definir_escopo(self, escopo: str) -> None:
        if escopo not in dict(self.ESCOPOS):
            raise ValueError(f"escopo da fila desconhecido: {escopo!r}")
        self.escopo = escopo
        self.eventos.emitir("modo_da_fila_mudou", self.modo)

    def alternar_escopo(self) -> None:
        """Shift+F7: a página ou o livro."""
        self.definir_escopo("livro" if self.escopo == "pagina" else "pagina")

    def definir(self, modo: str) -> None:
        if modo not in dict(self.MODOS):
            raise ValueError(f"modo da fila desconhecido: {modo!r}")
        self.modo = modo
        if modo in self.DE_GLIFOS:
            self.pagina.ordem_da_fila = modo
            self.pagina.pulados = set()
        self.eventos.emitir("modo_da_fila_mudou", modo)

    def ciclar(self) -> None:
        """F7: o modo seguinte."""
        modos = [m for m, _ in self.MODOS]
        self.definir(modos[(modos.index(self.modo) + 1) % len(modos)])

    def andar(self, passo: int) -> None:
        """Alt+↓ (passo +1) e Alt+↑ (−1): o item seguinte ou o anterior no modo de agora.
        Nunca muda texto. Nos diagramas, os dois vão ao próximo por conferir: o conferido sai
        da fila, e não há "anterior" a que voltar. No escopo livro, passar do fim (ou do
        começo) da página leva à próxima (ou à anterior) com o que revisar."""
        if self.modo in self.DE_GLIFOS:
            if self.escopo == "livro" and self._na_ponta(passo):
                self._outra_pagina(passo)
            else:
                self.pagina.andar(passo)
        elif self.modo == "palavras":
            v = self.verificador
            total = len(v.desconhecidas)
            na_ponta = not total or (v.posicao == total - 1 if passo > 0 else v.posicao == 0)
            if self.escopo == "livro" and na_ponta:
                self._outra_pagina_das_palavras(passo)
            else:
                v.andar(passo)
        else:
            self.conferencia.proximo_do_livro()

    def _na_ponta(self, passo: int) -> bool:
        """O atual é o último da fila da página (Alt+↓) ou o primeiro (Alt+↑), ou ela está
        vazia: a próxima ida sai da página."""
        p = self.pagina
        fila = p.fila()
        if not fila:
            return True
        if p.atual not in fila:
            return False
        if passo > 0:
            if p.ordem_da_fila == "confianca":   # o Alt+↓ põe o atual no fim (os pulados)
                return all(g in p.pulados or g == p.atual for g in fila)
            return fila.index(p.atual) == len(fila) - 1
        return fila.index(p.atual) == 0

    def _outra_pagina(self, passo: int) -> None:
        from abbychess import livro as lv

        p = self.pagina
        if p.projeto is None or p.leitor is None:
            return
        ir = lv.proxima_com_pendentes if passo > 0 else lv.anterior_com_pendentes
        alvo = ir(p.projeto, p.leitor.limiares, p.indice)
        if alvo is None or alvo == p.indice:
            p.pulados = set()
            p.ir_ao_primeiro_pendente()
            p._avisar("Não há mais o que revisar no livro.", 5000)
            return
        p.ir_para(alvo)
        fila = p.fila()
        if fila:
            p.escolher(fila[0] if passo > 0 else fila[-1])

    def _outra_pagina_das_palavras(self, passo: int) -> None:
        p = self.pagina
        if p.projeto is None or p.fonte is None:
            return
        lidas = sorted(p.projeto.paginas_lidas())
        if not lidas:
            return
        depois = [i for i in lidas if (i > p.indice if passo > 0 else i < p.indice)]
        alvo = (depois[0] if passo > 0 else depois[-1]) if depois else \
            (lidas[0] if passo > 0 else lidas[-1])
        if alvo != p.indice:
            p.ir_para(alvo)
        self.verificador.verificar()

    def contador(self) -> str:
        """"12/204": a posição do item atual na fila do modo, e o tamanho dela."""
        p = self.pagina
        if self.modo in self.DE_GLIFOS:
            fila = p.fila()
            n = fila.index(p.atual) + 1 if p.atual in fila else 0
            if self.escopo == "livro" and p.projeto is not None and p.leitor is not None:
                from abbychess import livro as lv

                outras = lv.pendentes_por_pagina(p.projeto, p.leitor.limiares)
                total = sum(v for i, v in outras.items() if i != p.indice) + len(fila)
                return f"{n}/{len(fila)} · livro {total}"
            return f"{n}/{len(fila)}"
        if self.modo == "palavras":
            total = len(self.verificador.desconhecidas)
            return f"{self.verificador.posicao + 1 if total else 0}/{total}"
        if p.projeto is None:
            return "0"
        resumo = p.projeto.resumo_do_livro()
        return str(sum(r.get("diagramas_por_conferir", 0) for r in resumo.values()))


# ----------------------------------------------------------------------
# Localizar (§7.1, §7.3, passo B)
# ----------------------------------------------------------------------

class ControladorDaBusca:
    """O índice das páginas e a busca, fora da thread da interface.

    O índice é montado em segundo plano ao abrir o projeto (`abrir`), nos processos que o
    programa abre ao começar (`aquecer`; `busca.PoolDoIndice`) e fecha depois de cada índice.
    Antes de cada busca, são refeitas a página que o usuário editou (a versão dela no
    histórico mudou), a que o F5 ou o lote leu (`pagina_reconhecida`, `pagina_do_lote`) e a
    reconhecida depois; a que deixou de ser reconhecida sai. A busca roda numa thread
    (`concurrent=True` no `regex`: a janela continua respondendo); uma busca nova cancela a
    anterior entre as páginas, e o que ela já tinha refeito fica. As páginas são lidas sem o
    cache do projeto e sem migrar a v1 (`projeto.ler_sem_migrar`). Os resultados voltam pela
    fila da interface (`executar.na_interface`) e saem nos eventos:

    - `busca_terminou(resultado)` (um `busca.Resultado`);
    - `busca_falhou(mensagem)` (a regex inválida, o padrão lento demais, um erro);
    - `indice_mudou(feitas, total)` enquanto o índice é montado (e `total, total` no fim).
    """

    def __init__(self, pagina: ControladorDePagina, paralelo: Optional[bool] = None):
        from abbychess import busca as bs

        self.pagina = pagina
        self.eventos = pagina.eventos
        self.paralelo = (os.environ.get("ABBY_INDICE_PARALELO", "1") != "0"
                         if paralelo is None else paralelo)
        self.pool = bs.PoolDoIndice()
        self.indice: dict = {}
        self.pronto = threading.Event()
        self._geracao = 0
        self._busca = 0
        self._velhas: set = set()
        self._leitura = 0                       # conta as leituras das páginas a refazer
        self._lida_em: dict = {}                # página -> a leitura que a pôs no índice
        #: leitura em voo -> as páginas que ela leva para refazer (fora de dia até o fim).
        self._em_refazer: dict = {}
        self._pendente = None                   # a busca pedida antes de o índice ficar pronto
        self.ultimo_resultado = None
        self.eventos.ligar("pagina_reconhecida", self.marcar_velha)
        self.eventos.ligar("pagina_do_lote", self.marcar_velha)

    @property
    def idioma(self) -> str:
        projeto = self.pagina.projeto
        return projeto.dados.idioma if projeto is not None else "pt"

    def _na_interface(self, funcao) -> None:
        chamar = getattr(self.pagina.executar, "na_interface", None)
        if chamar is None:
            funcao()
        else:
            chamar(funcao)

    def aquecer(self) -> None:
        """Abre os processos do índice já com o programa (o próximo projeto aberto os usa)."""
        if self.paralelo:
            self.pool.aquecer()

    # ------------------------------------------------------------------
    def abrir(self) -> None:
        """O projeto aberto: o índice antigo sai e o novo começa a ser montado."""
        from abbychess import busca as bs

        self._geracao += 1
        self._busca += 1
        geracao = self._geracao
        self.indice, self._velhas, self._pendente, self._lida_em = {}, set(), None, {}
        self._em_refazer = {}
        self.ultimo_resultado = None
        self.pronto.clear()
        projeto = self.pagina.projeto
        if projeto is None:
            return
        historico, idioma = self.pagina.historico, self.idioma
        fontes, a_ler = {}, {}
        for indice in projeto.paginas_lidas():
            versao = historico.versao(projeto.pid_da_pagina(indice))
            modelo = projeto.modelo_em_memoria(indice)
            caminho = None if modelo is not None else projeto.arquivo_da_pagina(indice)
            if modelo is not None:              # na memória (talvez sem gravar): o instantâneo
                fontes[indice] = (modelo.instantaneo(), versao)
            elif caminho is not None:
                fontes[indice] = (str(caminho), versao)
            else:                               # v1: lida na thread, sem migrar
                a_ler[indice] = versao
        total = len(fontes) + len(a_ler)
        paralelo, pool = self.paralelo, self.pool

        def montar():
            feitas = [0]
            indice: dict = {}

            def contar(_indexada):
                feitas[0] += 1
                if feitas[0] % 10 == 0:
                    self._na_interface(lambda n=feitas[0]: self._progresso(geracao, n, total))
            vale = lambda: geracao == self._geracao      # noqa: E731
            try:
                for i, versao in a_ler.items():
                    pagina = projeto.ler_sem_migrar(i)
                    if pagina is not None:
                        fontes[i] = (pagina, versao)
                indice = bs.construir(fontes, idioma, paralelo=paralelo, pool=pool,
                                      cancelado=lambda: not vale(), ao_indexar=contar)
            except Exception as erro:       # o índice parcial vale; o erro vai aos Avisos
                if vale() and not isinstance(erro, CancelledError):
                    log.exception("o índice da busca não foi montado inteiro")
                    self._na_interface(lambda e=erro: self.eventos.emitir(
                        "aviso", "Índice da busca",
                        f"Algumas páginas ficaram fora da busca: {str(e) or repr(e)}"))
            self._na_interface(lambda: self._indice_pronto(geracao, indice))

        threading.Thread(target=montar, name="indice-da-busca", daemon=True).start()

    def _progresso(self, geracao: int, feitas: int, total: int) -> None:
        if geracao == self._geracao and not self.pronto.is_set():
            self.eventos.emitir("indice_mudou", feitas, total)

    def _indice_pronto(self, geracao: int, indice: dict) -> None:
        if geracao != self._geracao:
            return
        self.indice = indice
        self.pronto.set()
        self.eventos.emitir("indice_mudou", len(indice), len(indice))
        if self._pendente is not None:
            opcoes, self._pendente = self._pendente, None
            self.buscar(opcoes)

    def marcar_velha(self, indice: int) -> None:
        """A página foi lida de novo (F5 ou lote): refeita antes da próxima busca."""
        self._velhas.add(int(indice))

    def cancelar(self) -> None:
        self._busca += 1
        self._pendente = None

    @property
    def buscando(self) -> bool:
        """Uma busca foi pedida e ainda não terminou (nem foi cancelada)."""
        return self._pendente is not None or self._em_voo == self._busca

    _em_voo = -1

    # ------------------------------------------------------------------
    def buscar(self, opcoes) -> Optional[str]:
        """Busca em segundo plano; o fim vem em `busca_terminou` ou `busca_falhou`. Antes de
        o índice ficar pronto, a busca espera por ele. Devolve a dica (a expansão das
        classes), ou None se a regex não compila (e `busca_falhou` já saiu)."""
        from abbychess import busca as bs

        self._busca += 1
        try:
            expressao, dica = bs.compilar(opcoes)       # o erro da regex, na hora, sem thread
        except bs.PadraoInvalido as erro:
            self.eventos.emitir("busca_falhou", f"Regex inválida: {erro}")
            return None
        if not self.pronto.is_set():
            self._pendente = opcoes
            return dica
        numero, geracao = self._busca, self._geracao
        self._em_voo = numero
        leitura, refazer, carregar, velhas = self._paginas_a_refazer()
        indice = dict(self.indice)

        def rodar():
            vale = lambda: numero == self._busca and geracao == self._geracao   # noqa: E731
            resultado, erro, refeitas = None, None, {}
            try:
                refeitas = self._refazer(refazer, carregar, vale)
                indice.update(refeitas)
                if vale():
                    resultado = bs.buscar(indice, opcoes, cancelado=lambda: not vale(),
                                          tempo_limite=bs.TEMPO_LIMITE, expressao=expressao)
            except bs.PadraoLento as lento:
                erro = f"Busca abortada: {lento}."
            except Exception as falha:          # o erro vai para a barra, e a busca termina
                log.exception("a busca falhou")
                erro = f"A busca falhou: {falha}"
            self._na_interface(lambda: self._fim(numero, geracao, leitura, refeitas, velhas,
                                                 resultado, erro))

        threading.Thread(target=rodar, name="busca", daemon=True).start()
        return dica

    def _refazer(self, refazer: dict, carregar: dict, vale) -> dict:
        """Indexa as páginas a refazer (fora da thread da interface); devolve só elas."""
        from abbychess import busca as bs

        projeto, idioma, refeitas = self.pagina.projeto, self.idioma, {}
        for i, (pagina, versao) in refazer.items():
            refeitas[i] = bs.indexar_pagina(pagina, idioma, versao=versao)
        for i, versao in carregar.items():
            if not vale():
                break
            pagina = projeto.ler_sem_migrar(i)
            if pagina is not None:
                refeitas[i] = bs.indexar_pagina(pagina, idioma, versao=versao)
        return refeitas

    def _paginas_a_refazer(self):
        """As páginas do índice que mudaram: as editadas (a versão no histórico) e as na
        memória, como instantâneo (a interface pode mudá-las durante a busca); as relidas e
        as que entraram no livro depois, para ler na thread. Devolve também o número desta
        leitura (a mais nova vence no índice) e as velhas que este pedido leva (voltam a
        velhas se ele não terminar)."""
        projeto, historico = self.pagina.projeto, self.pagina.historico
        refazer, carregar = {}, {}
        lidas = set(projeto.paginas_lidas())
        for i in sorted(lidas):
            versao = historico.versao(projeto.pid_da_pagina(i))
            indexada = self.indice.get(i)
            if indexada is not None and indexada.versao == versao and i not in self._velhas:
                continue
            modelo = projeto.modelo_em_memoria(i)
            if modelo is not None:
                refazer[i] = (modelo.instantaneo(), versao)
            else:
                carregar[i] = versao
        for i in [i for i in self.indice if i not in lidas]:
            self.indice.pop(i, None)            # deixou de ser reconhecida (o desfazer do F5)
        velhas, self._velhas = self._velhas & set(refazer) | self._velhas & set(carregar), set()
        self._leitura += 1
        self._em_refazer[self._leitura] = set(refazer) | set(carregar)
        return self._leitura, refazer, carregar, velhas

    def fora_de_dia(self) -> set:
        """As páginas que o índice ainda não tem como estão: as relidas e as que uma busca
        em voo leva para refazer."""
        fora = set(self._velhas)
        for paginas in self._em_refazer.values():
            fora |= paginas
        return fora

    def _guardar(self, leitura: int, refeitas: dict) -> None:
        """As páginas refeitas entram no índice, se ainda são lidas e se nenhuma leitura mais
        nova (que viu o disco depois) já as pôs lá."""
        lidas = set(self.pagina.projeto.paginas_lidas()) if self.pagina.projeto else set()
        for i, indexada in refeitas.items():
            atual = self.indice.get(i)
            if (i in lidas and self._lida_em.get(i, 0) < leitura
                    and (atual is None or indexada.versao >= atual.versao)):
                self.indice[i] = indexada
                self._lida_em[i] = leitura

    def _fim(self, numero: int, geracao: int, leitura: int, refeitas: dict, velhas: set,
             resultado, erro) -> None:
        self._em_refazer.pop(leitura, None)
        if numero == self._em_voo:
            self._em_voo = -1
        if geracao != self._geracao:
            return
        self._guardar(leitura, refeitas)        # o que foi refeito fica, se ainda vale
        if resultado is None and erro is None:  # abandonada: as relidas voltam a velhas
            self._velhas |= velhas
        if numero != self._busca:               # uma busca mais nova já foi pedida
            return
        if erro is not None:
            self.eventos.emitir("busca_falhou", erro)
            return
        if resultado is not None:
            self.ultimo_resultado = resultado
            self.eventos.emitir("busca_terminou", resultado)

    def nao_reconhecidas(self) -> int:
        """Quantas páginas do livro ficaram fora da busca (não reconhecidas)."""
        p = self.pagina
        total = p.fonte.total if p.fonte is not None else 0
        return max(0, total - len(self.indice))

    def contar_leitura(self, char: str) -> int:
        """Quantos glifos do livro têm a leitura `char`, pelo índice de agora."""
        return sum(1 for indexada in self.indice.values() for g in indexada.glifos
                   if g[1] == char)

    def lidos_por_amostra(self) -> dict:
        """Amostra (o nome) -> quantos glifos do livro ela leu, pelo índice de agora (sem
        refazer as páginas: a aba Padrões o mostra como está)."""
        contagem: dict = {}
        for indexada in self.indice.values():
            for _gid, amostra in indexada.amostras:
                contagem[amostra] = contagem.get(amostra, 0) + 1
        return contagem

    def lidos_por(self, amostras, ao_terminar) -> None:
        """Os glifos do livro lidos pelas `amostras` (os nomes, relativos à pasta dos
        padrões), numa thread, pelo índice com as páginas que mudaram já refeitas (§8.3):
        `ao_terminar({página: [gids]})` na interface (não é chamado se outro projeto abriu).
        Antes de o índice ficar pronto, todas as páginas lidas são lidas na thread."""
        amostras = set(amostras)
        projeto = self.pagina.projeto
        if projeto is None:
            return
        geracao = self._geracao
        if self.pronto.is_set():
            leitura, refazer, carregar, _velhas = self._paginas_a_refazer()
            indice = dict(self.indice)
        else:
            historico = self.pagina.historico
            leitura, refazer, indice = 0, {}, {}
            carregar = {i: historico.versao(projeto.pid_da_pagina(i))
                        for i in projeto.paginas_lidas()}

        def rodar():
            refeitas = {}
            try:
                refeitas = self._refazer(refazer, carregar, lambda: geracao == self._geracao)
            except Exception:
                log.exception("a procura dos glifos lidos pelas amostras falhou")
            indice.update(refeitas)
            achados = {}
            for i, indexada in indice.items():
                gids = [g for g, a in indexada.amostras if a in amostras]
                if gids:
                    achados[i] = gids

            def fim():
                self._em_refazer.pop(leitura, None)
                if geracao != self._geracao:
                    return
                if leitura:
                    self._guardar(leitura, refeitas)
                ao_terminar(achados)
            self._na_interface(fim)

        threading.Thread(target=rodar, name="lidos-pelas-amostras", daemon=True).start()

    def glifos(self, char: str, fontes=None, minima: float = 0.0, maxima: float = 1.0,
               ao_terminar=None) -> None:
        """A busca por glifo (§7.1), numa thread, no índice com as páginas que mudaram já
        refeitas (depois de um lote, elas são muitas); `ao_terminar(achados)` é chamado na
        interface (não é chamado se outro projeto foi aberto no meio)."""
        from abbychess import busca as bs

        geracao, indice = self._geracao, dict(self.indice)
        leitura, refazer, carregar, velhas = (
            self._paginas_a_refazer() if self.pagina.projeto is not None and self.pronto.is_set()
            else (0, {}, {}, set()))

        def rodar():
            refeitas, achados = {}, []
            try:
                refeitas = self._refazer(refazer, carregar, lambda: geracao == self._geracao)
                indice.update(refeitas)
                achados = bs.buscar_glifos(indice, char, fontes, minima, maxima)
            except Exception:
                log.exception("a busca por glifo falhou")
                refeitas = None

            def fim():
                self._em_refazer.pop(leitura, None)
                if geracao != self._geracao:
                    return
                if refeitas is None:            # falhou: as relidas voltam a velhas
                    self._velhas |= velhas
                else:
                    self._guardar(leitura, refeitas)
                if ao_terminar is not None:
                    ao_terminar(achados)
            self._na_interface(fim)

        threading.Thread(target=rodar, name="busca-por-glifo", daemon=True).start()


# ----------------------------------------------------------------------
# Substituir (§7.2, passo D2)
# ----------------------------------------------------------------------

class ControladorDaSubstituicao:
    """Substituir: os casos (`substituir.casos_da_pagina`) e a aplicação numa transação do
    desfazer, mesmo no livro inteiro.

    Na página aberta, `na_pagina` aplica direto (um caso, ou todos). Fora dela, `previa`
    monta os casos numa thread: o índice da busca diz que páginas podem ter casamento, e só
    elas são lidas (sem o cache e sem migrar, `projeto.ler_sem_migrar`) e montadas; cada
    `substituir.Previa` leva a página como foi lida. A janela as mostra em Resultados, e
    `aplicar` aplica os aceitos: as cópias das páginas lidas são editadas na thread do
    executor (a fila: nada mais edita enquanto isso) e trocadas na interface, que confere
    que a página não mudou desde a leitura (se mudou, aplica na de agora, se as palavras de
    cada caso ainda são as mesmas; senão a página fica de fora, com o motivo). Os eventos:

    - `previa_pronta(previas, fora)` (uma `Previa` por página com casos; `fora`, os
      casamentos que tocam palavras de outro "onde");
    - `previa_progresso(feitas, total)`;
    - `substituicao_falhou(mensagem)` (o substituto inválido, o padrão lento, um erro);
    - `substituicao_feita(casos, paginas, falhas, sem_traducao, saidos)` (`falhas`:
      página -> motivo; `sem_traducao`: os casos da página aberta que ficaram de fora;
      `saidos`: os passos mais antigos do desfazer que saíram para a transação caber).
    """

    def __init__(self, pagina: ControladorDePagina, busca: ControladorDaBusca):
        self.pagina = pagina
        self.busca = busca
        self.eventos = pagina.eventos
        self._numero = 0

    # ------------------------------------------------------------------
    def _preparar(self, opcoes, modelo: str):
        from abbychess import busca as bs
        from abbychess import substituir as sb

        expressao, _dica = bs.compilar(opcoes)
        sb.validar(modelo, expressao, opcoes.regex)
        return expressao, sb.substituto(modelo, opcoes.regex)

    def _paginas(self, opcoes) -> List[int]:
        from abbychess import busca as bs

        lidas = sorted(self.pagina.projeto.paginas_lidas())
        if opcoes.escopo in (bs.PAGINA, bs.SELECAO):
            alvo = (opcoes.selecao[0] if opcoes.escopo == bs.SELECAO and opcoes.selecao
                    else opcoes.pagina_atual)
            return [alvo] if alvo in lidas else []
        if opcoes.escopo == bs.INTERVALO and opcoes.intervalo is not None:
            a, b = sorted(opcoes.intervalo)
            return [i for i in lidas if a <= i <= b]
        return lidas

    def _casos(self, pagina, opcoes, expressao, trocar, alvo: str):
        from abbychess import busca as bs
        from abbychess import sessao as ss
        from abbychess import substituir as sb

        montada = ss.texto_e_unidades(pagina)
        indexada = bs.indexar_pagina(pagina, self.busca.idioma, montada=montada)
        trecho = None
        if opcoes.escopo == bs.SELECAO:
            trecho = bs._trecho_da_selecao(indexada, opcoes.selecao)
            if trecho is None:
                return sb.Previa(pagina.indice, montada[0], [], lida=pagina)
        fora = [0]
        casos = sb.casos_da_pagina(indexada, montada[1], expressao, trocar, alvo, opcoes.onde,
                                   trecho, bs.TEMPO_LIMITE, fora)
        return sb.Previa(pagina.indice, montada[0], casos, lida=pagina, fora=fora[0])

    def _na_interface(self, funcao) -> None:
        self.busca._na_interface(funcao)

    def _candidatas(self, indices: List[int]) -> dict:
        """Índice -> a página no índice da busca, se ela está em dia (a versão no histórico,
        e não relida desde então); as outras (None) são lidas de qualquer jeito."""
        projeto, historico, busca = self.pagina.projeto, self.pagina.historico, self.busca
        fora, em_dia = busca.fora_de_dia(), {}
        for i in indices:
            indexada = busca.indice.get(i)
            versao = historico.versao(projeto.pid_da_pagina(i))
            em_dia[i] = (indexada if indexada is not None and indexada.versao == versao
                         and i not in fora else None)
        return em_dia

    # ------------------------------------------------------------------
    def previa(self, opcoes, modelo: str, alvo: str) -> bool:
        """Os casos fora da página aberta, numa thread (o fim em `previa_pronta` ou
        `substituicao_falhou`). False se o padrão ou o substituto não compilam."""
        from abbychess import busca as bs

        try:
            expressao, trocar = self._preparar(opcoes, modelo)
        except bs.PadraoInvalido as erro:
            self.eventos.emitir("substituicao_falhou", f"Regex inválida: {erro}")
            return False
        self._numero += 1
        numero, geracao = self._numero, self.pagina.geracao
        projeto, indices = self.pagina.projeto, self._paginas(opcoes)
        em_dia = self._candidatas(indices)

        def rodar():
            previas, fora, erro = [], 0, None
            try:
                for n, i in enumerate(indices):
                    if numero != self._numero:
                        return
                    if n % 10 == 9:
                        self._na_interface(lambda f=n + 1: self._progresso(numero, f,
                                                                           len(indices)))
                    indexada = em_dia[i]
                    if indexada is not None and expressao.search(
                            indexada.texto, concurrent=True, timeout=bs.TEMPO_LIMITE) is None:
                        continue                # o índice em dia: sem casamento, sem ler
                    # O carimbo antes de ler: se o arquivo mudar depois, aplicar o vê.
                    carimbo = (projeto.carimbo(i) if projeto.modelo_em_memoria(i) is None
                               else None)
                    pagina = projeto.ler_sem_migrar(i)
                    if pagina is None:
                        continue
                    previa = self._casos(pagina, opcoes, expressao, trocar, alvo)
                    fora += previa.fora
                    if previa.casos:
                        previa.carimbo, previa.geracao = carimbo, geracao
                        previas.append(previa)
            except (bs.PadraoLento, TimeoutError) as lento:
                erro = f"Substituição abortada: {lento or 'padrão lento demais'}."
            except Exception as falha:          # o erro vai para a barra
                log.exception("a prévia da substituição falhou")
                erro = f"A prévia falhou: {falha}"
            self._na_interface(lambda: self._previa_pronta(numero, geracao, previas, fora,
                                                           erro))

        threading.Thread(target=rodar, name="previa-da-substituicao", daemon=True).start()
        return True

    def _progresso(self, numero: int, feitas: int, total: int) -> None:
        if numero == self._numero:
            self.eventos.emitir("previa_progresso", feitas, total)

    def _previa_pronta(self, numero, geracao, previas, fora, erro) -> None:
        if numero != self._numero or geracao != self.pagina.geracao:
            return
        if erro is not None:
            self.eventos.emitir("substituicao_falhou", erro)
            return
        self.eventos.emitir("previa_pronta", previas, fora)

    def cancelar(self) -> None:
        self._numero += 1

    # ------------------------------------------------------------------
    def na_pagina(self, opcoes, modelo: str, alvo: str, posicao: Optional[int] = None):
        """Na página aberta, direto (§7.2): o caso que contém `posicao` (o casamento atual
        da busca), ou todos (`posicao` None). O que ainda não tem tradução fica de fora, com
        o aviso. Devolve os casos pedidos (aplicados na vez deles na fila); [] se em
        `posicao` não há o que trocar (o casamento já está como o substituto: quem chama
        segue para o próximo); None se nada foi feito (o aviso já saiu)."""
        from abbychess import busca as bs

        pc = self.pagina
        if pc.modelo is None or pc.projeto is None:
            self.eventos.emitir("substituicao_falhou", "Nada a substituir nesta página.")
            return None
        try:
            expressao, trocar = self._preparar(opcoes, modelo)
            previa = self._casos(pc.modelo.instantaneo(), opcoes, expressao, trocar, alvo)
        except (bs.PadraoInvalido, bs.PadraoLento) as erro:
            self.eventos.emitir("substituicao_falhou", str(erro))
            return None
        casos = previa.casos
        if posicao is not None:
            casos = [c for c in casos if c.inicio <= posicao < c.fim][:1]
            if not casos and self._ja_trocado(previa.texto, expressao, trocar, posicao):
                return []
            if not casos:
                self.eventos.emitir("substituicao_falhou", "Não substituído: "
                                    + self._por_que_fora(previa, alvo) + ".")
                return None
        bons = [c for c in casos if c.aplicavel]
        if not bons:
            motivo = casos[0].motivo if casos else self._por_que_fora(previa, alvo)
            self.eventos.emitir("substituicao_falhou", f"Não substituído: {motivo}.")
            return None
        previa.geracao = pc.geracao
        self.aplicar({pc.indice: bons}, _descricao(bons), {pc.indice: previa},
                     sem_traducao=len(casos) - len(bons))
        return bons

    @staticmethod
    def _ja_trocado(texto: str, expressao, trocar, posicao: int) -> bool:
        """O casamento que começa em `posicao` já está como o substituto."""
        casado = expressao.search(texto, posicao)
        return casado is not None and casado.start() == posicao and trocar(casado) == casado.group()

    @staticmethod
    def _por_que_fora(previa, alvo: str) -> str:
        from abbychess import substituir as sb

        if not previa.fora:
            return "nada a substituir aqui"
        escolha = "Notação ou Ambos" if alvo == sb.PROSA else "Prosa ou Ambos"
        return (f"{previa.fora} ocorrência(s) em {_outro_onde(alvo)} ficaram fora "
                f"(escolha {escolha})")

    def aplicar(self, aceitos, descricao: str, previas, sem_traducao: int = 0) -> None:
        """Os casos aceitos (página -> casos), das `previas` (página -> `Previa`, com a
        página como foi lida), numa transação do desfazer (ver o docstring da classe). O
        fim em `substituicao_feita`."""
        from abbychess import historico as hs
        from abbychess import sessao as ss
        from abbychess import substituir as sb

        aceitos = {i: list(c) for i, c in aceitos.items() if c}
        pc = self.pagina
        if not aceitos or pc.projeto is None:
            return
        if any(previas[i].geracao != pc.geracao for i in aceitos):
            self.eventos.emitir("substituicao_falhou", "A prévia é de outro projeto: refaça.")
            return
        fontes = {i: previas[i].lida for i in aceitos}
        carimbos = {i: previas[i].carimbo for i in aceitos}

        idioma = pc.projeto.dados.idioma

        def preparar():
            projeto = pc.projeto
            for i in aceitos:
                if fontes[i] is None:           # sem a leitura (não deveria): a de agora
                    fontes[i] = projeto.pagina_para_editar(i).instantaneo()

            def trabalho(progresso):
                # Fora da interface: a cópia editada, o estado, os lados dos diagramas, a
                # mudança para o desfazer e o resumo do livro (a interface só troca).
                feitas, falhas = {}, {}
                for n, (i, casos) in enumerate(sorted(aceitos.items())):
                    progresso(n, len(aceitos))
                    copia = fontes[i].instantaneo()
                    try:
                        sb.aplicar_na_pagina(copia, casos)
                        _depois_de_editar(copia, fontes[i], idioma)
                        feitas[i] = (copia, hs.mudanca(fontes[i], copia.instantaneo()),
                                     projeto.resumo_do_modelo(copia))
                    except ss.Recusa as recusa:
                        falhas[i] = str(recusa)
                    except Exception as erro:   # a página fica de fora; o resto vale
                        log.exception("substituir na página %d falhou", i + 1)
                        falhas[i] = f"a substituição falhou: {erro}"
                return feitas, falhas

            def pronto(resultado):
                self._trocar(aceitos, fontes, carimbos, *resultado, descricao, sem_traducao)
            return trabalho, pronto
        pc.tarefa(f"Substituindo em {len(aceitos)} página(s)", preparar,
                  falhou=pc._falhou("Substituir"))

    def _trocar(self, aceitos, fontes, carimbos, feitas, falhas, descricao,
                sem_traducao) -> None:
        """Na interface: as cópias editadas entram nas páginas, numa transação. A página que
        a prévia leu do disco, e que ninguém abriu desde então, é adotada como a viva
        (`projeto.adotar`: sem ler o JSON de novo)."""
        from abbychess import historico as hs
        from abbychess import sessao as ss
        from abbychess import substituir as sb

        pc = self.pagina
        projeto = pc.projeto
        transacao = hs.Transacao(descricao)
        mudadas = []
        for i, (copia, mudanca, resumo) in sorted(feitas.items()):
            fonte = fontes[i]
            if pc.modelo is not None and pc.modelo.indice == i:
                viva = pc.modelo
            else:
                viva = projeto.adotar(fonte, carimbos.get(i)) or projeto.pagina_para_editar(i)
            if viva is fonte or _mesma_pagina(viva, fonte):
                viva.boxes, viva.decisoes = list(copia.boxes), copia.decisoes
                viva.proximo_n = max(viva.proximo_n, copia.proximo_n)
                viva.estado = copia.estado
                viva.diagramas, viva.zonas = list(copia.diagramas), list(copia.zonas)
            else:                               # mudou desde a leitura: na de agora
                antes = viva.instantaneo()
                try:
                    sb.aplicar_na_pagina(viva, aceitos[i])
                except Exception as erro:
                    viva.boxes, viva.decisoes = list(antes.boxes), antes.decisoes
                    falhas[i] = (str(erro) if isinstance(erro, ss.Recusa)
                                 else f"a substituição falhou: {erro}")
                    continue
                _depois_de_editar(viva, antes, self.pagina.projeto.dados.idioma)
                mudanca, resumo = hs.mudanca(antes, viva.instantaneo()), None
            transacao.paginas[viva.pid] = mudanca
            mudadas.append((viva, resumo))
        casos = sum(len(aceitos[p.indice]) for p, _r in mudadas)
        saidos = 0
        if mudadas:
            passos = pc.historico.passos
            pc.historico.registrar(transacao)
            saidos = max(0, passos + 1 - pc.historico.passos)
            gravou = all([projeto.agendar(p, resumo) for p, resumo in mudadas])
            if not gravou:
                pc._avisar("Projeto aberto só para leitura: nada é gravado.", 6000)
            if any(p is pc.modelo for p, _r in mudadas):
                vivos = pc.modelo.vivos
                pc.pulados &= vivos
                pc.selecao &= vivos
                if pc.atual not in vivos:
                    pc.atual = None
                self.eventos.emitir("glifos_mudaram", None)
            self.eventos.emitir("acoes_mudaram")
        self.eventos.emitir("substituicao_feita", casos, len(mudadas), dict(falhas),
                            sem_traducao, saidos)


def _outro_onde(alvo: str) -> str:
    from abbychess import substituir as sb

    return "notação" if alvo == sb.PROSA else "prosa"


def _depois_de_editar(pagina, antes, idioma: str = "pt") -> None:
    """O que toda edição faz depois (como `ControladorDePagina._mudou`): o estado (§4.4), o
    lado dos diagramas pela legenda, os ids das áreas e dos diagramas."""
    from abbychess.modelo import proximo_estado

    pagina.estado = proximo_estado(pagina.estado, "editar")
    if pagina.diagramas:
        pagina.diagramas = dg.rederivar_lados(list(pagina.diagramas), antes.entries(),
                                              pagina.entries())
    pagina.zonas = zn.com_ids(list(pagina.zonas))
    pagina.diagramas = dg.com_ids(list(pagina.diagramas))
    pagina.zonas = zn.vincular_legendas(pagina.zonas, pagina.diagramas)
    pagina.diagramas = lc.validar_pagina(pagina, idioma)


def _mesma_pagina(viva, lida) -> bool:
    """A página de agora é a que foi lida: os mesmos glifos, decisões, áreas, diagramas e
    estado (a cópia editada leva tudo isso da lida)."""
    from abbychess import historico as hs

    if (viva.pid != lida.pid or viva.decisoes != lida.decisoes or viva.estado != lida.estado
            or len(viva.boxes) != len(lida.boxes)
            or list(viva.zonas) != list(lida.zonas)
            or list(viva.diagramas) != list(lida.diagramas)
            or list(viva.tabuleiros) != list(lida.tabuleiros)):
        return False
    return all(a is b or hs.igual(a, b) for a, b in zip(viva.boxes, lida.boxes))


def _descricao(casos) -> str:
    """O nome da transação no menu Editar ("Substituir 'casa' por 'lar'", ou "Substituir 12
    ocorrências")."""
    if len(casos) == 1:
        return f"Substituir '{casos[0].antes[:30]}' por '{casos[0].depois[:30]}'"
    return f"Substituir {len(casos)} ocorrências"
