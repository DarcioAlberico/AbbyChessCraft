"""Os outros controladores da janela (SPEC §14.1): áreas, verificação, diagramas e livro.

Cada um trabalha sobre a página aberta do `ControladorDePagina` e fala pelos mesmos
`Eventos`. Os que acrescentam:

- `ControladorDeLayout`: `layout_mudou`;
- `ControladorDeVerificacao`: `palavra_mudou` (a palavra desconhecida a mostrar, ou nenhuma);
- `ControladorDeDiagramas`: `conferir(indice)` (a janela abre a conferência);
- `ControladorDoLivro`: `projeto_aberto`, `lote_mudou`.

Sem Qt. Os diálogos (que intervalo ler, onde exportar) são da janela; aqui chegam as
respostas.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import List, Optional, Sequence

from abbychess import diagramas as dg
from abbychess import edicao as ed
from abbychess import exportar as ex
from abbychess import livro
from abbychess import pagina as pg
from abbychess import verificacao as vf
from abbychess import zonas as zn
from abbychess.controlador import ControladorDePagina
from abbychess.leitor import LeitorDoLivro, congelar_para_a_coleta_de_lixo

log = logging.getLogger(__name__)


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
        pagina.eventos.ligar("pagina_trocou", self._pagina_trocou)

    @property
    def zonas(self) -> list:
        return self.pagina.zonas

    def _pagina_trocou(self) -> None:
        self.atual = None
        self.eventos.emitir("layout_mudou")

    def _trocar(self, zonas: Sequence[zn.Zona], atual: Optional[int]) -> None:
        if self.pagina.lote_rodando:
            self.pagina._recusar_no_lote()
            return
        p = self.pagina
        if not zonas and p.modelo is None:
            self.atual = None                    # nada a gravar numa página que não existe
        else:
            modelo = p._pagina_para_editar()
            modelo.zonas = list(zonas)
            p._gravar(modelo)
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
        indice = p.indice

        def preparar():
            if p.indice != indice or p.imagem is None:
                return None
            imagem, leitor = p.imagem, p.leitor

            def trabalho(_progresso):
                bruta = pg.segmentar_pagina(imagem, leitor)
                return zn.automaticas(bruta.boxes, bruta.tabuleiros, largura, altura)

            def pronto(zonas):
                if p.indice == indice:
                    self._automaticas_prontas(zonas)
            return trabalho, pronto

        p.tarefa("Achando as áreas", preparar, falhou=p._falhou("Áreas"))

    def _automaticas_prontas(self, zonas) -> None:
        self._trocar(zonas, None)
        tipos: dict = {}
        for z in zonas:
            nome = zn.NOMES[z.tipo].lower()
            tipos[nome] = tipos.get(nome, 0) + 1
        resumo = ", ".join(f"{n} {t}" for t, n in tipos.items()) or "nenhuma"
        self.pagina._avisar(f"Áreas automáticas: {resumo}. Corrija e aperte F5.", 10000)

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
        self._trocar(zonas, len(zonas) - 1)
        p._avisar(f"Área {len(zonas)} de texto criada. 2 diagrama, 3 imagem, 4 ignorar.", 6000)

    def escolher(self, indice: int) -> None:
        self.atual = indice if 0 <= indice < len(self.zonas) else None
        self.eventos.emitir("layout_mudou")

    def arrastar(self, indice: int, bordas: str, dx: int, dy: int) -> None:
        p = self.pagina
        zonas = self.zonas
        if not 0 <= indice < len(zonas) or p.imagem is None:
            return
        largura, altura = p.imagem.size
        zonas[indice] = zn.arrastar(zonas[indice], bordas, dx, dy, largura, altura)
        self._trocar(zonas, indice)

    def apagar(self, indice: int) -> None:
        zonas = self.zonas
        if not 0 <= indice < len(zonas):
            return
        del zonas[indice]
        self._trocar(zonas, None)
        aviso = "" if zonas else " Sem áreas, a página volta à segmentação automática."
        self.pagina._avisar(f"Área apagada.{aviso}", 6000)

    def trocar_tipo(self, indice: int, tipo: str) -> None:
        zonas = self.zonas
        if not 0 <= indice < len(zonas):
            return
        zn.trocar_tipo(zonas, indice, tipo)
        self._trocar(zonas, indice)
        self.pagina._avisar(f"Área {indice + 1}: {zn.NOMES[tipo].lower()}.", 5000)


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
        self.desconhecidas = vf.desconhecidas(p.boxes, self.lexico, self.ignoradas)
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
        try:
            mudados = vf.corrigir(entries, list(range(len(entries))), texto)
        except ValueError as erro:
            p._avisar(f"Não corrigiu: {erro}", 8000)
            return
        for k, _char in mudados:
            ed.trocar(p.modelo, gids[k], entries[k])
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

        if not ensinar or not mudados or p.leitor is None:
            depois(f"'{texto}': {len(mudados)} glifo(s) corrigido(s).")
            return
        por_char: dict = {}
        for k, char in mudados:
            por_char.setdefault(char, []).append(gids[k])

        def ensinou(resolvidos: int) -> None:
            extra = f"; os padrões resolveram mais {resolvidos} na página" if resolvidos else ""
            depois(f"'{texto}': {len(mudados)} glifo(s) corrigido(s) e ensinado(s){extra}.")

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
            p._avisar(f"'{texto}' não entra no dicionário (já está, ou não é só de letras).",
                      6000)
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
        pagina_indice = p.indice

        def preparar():
            pagina = p.modelo
            if p.indice != pagina_indice or pagina is None:
                return None
            atuais = dg.para_caixas(pagina.tabuleiros, pagina.diagramas)
            por_ler = [i for i, d in enumerate(atuais) if not d.lido and not d.erro]
            imagem, leitor, boxes = p.imagem, p.leitor, pagina.entries()
            caixas = [atuais[i].caixa for i in por_ler]

            def trabalho(_progresso):
                return dg.ler_diagramas(imagem, caixas, classificar=leitor.arbitro, boxes=boxes)

            def pronto(lidos):
                # Na página que pediu, mesmo que o usuário tenha ido a outra.
                novos = dg.para_caixas(pagina.tabuleiros, pagina.diagramas)
                for lido in lidos:
                    for i, d in enumerate(novos):
                        if d.caixa == lido.caixa and not d.lido:
                            novos[i] = lido
                pagina.diagramas = novos
                p._gravar(pagina)
                if pagina is p.modelo:
                    self.eventos.emitir("glifos_mudaram", None)
                    self._abrir(indice)
            return trabalho, pronto

        p.executar("Lendo os diagramas", preparar, falhou=p._falhou("Ler os diagramas"))

    def _abrir(self, indice: int) -> None:
        d = self.pagina.diagramas[indice]
        if not d.lido:
            self.pagina._avisar(f"O diagrama não foi lido: {d.erro}", 8000)
            return
        self.eventos.emitir("conferir", indice)

    def aplicar(self, indice: int, tabuleiro, tudo: bool) -> None:
        """Grava o diagrama conferido, refaz o texto e guarda as amostras no projeto."""
        p = self.pagina
        if p.modelo is None or p.lote_rodando:
            if p.lote_rodando:
                p._recusar_no_lote()
            return
        antes = p._instantaneo()
        diagramas = p.diagramas
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


# ----------------------------------------------------------------------
# O livro: abrir, o lote, a revisão entre páginas e a exportação
# ----------------------------------------------------------------------

class ControladorDoLivro:
    """O projeto aberto e o que vale para o livro inteiro."""

    def __init__(self, pagina: ControladorDePagina):
        self.pagina = pagina
        self.eventos = pagina.eventos
        #: O pedido de cancelar o lote em andamento, ou None sem lote.
        self._cancelar: Optional[threading.Event] = None

    @property
    def lote_rodando(self) -> bool:
        return self._cancelar is not None

    def abrir(self, projeto, fonte) -> None:
        """Liga o projeto (a fonte já aberta) e carrega os modelos fora da interface; ao fim,
        `projeto_aberto(leitor)` e a última página lida aparece."""
        p = self.pagina
        self._cancelar = None
        p.ligar(projeto, fonte, None)

        def preparar():
            def trabalho(_progresso):
                leitor = LeitorDoLivro.com_modelos_globais(projeto.pasta_de_padroes,
                                                           limiares=projeto.dados.limiares)
                log.info("congelados para a coleta de lixo: %d objetos",
                         congelar_para_a_coleta_de_lixo())
                return leitor

            def pronto(leitor):
                if p.projeto is not projeto:
                    return                          # outro projeto foi aberto antes
                self.usar(projeto, fonte, leitor)
                self.eventos.emitir("projeto_aberto", leitor)
            return trabalho, pronto

        p.tarefa("Carregando os modelos", preparar, falhou=p._falhou("Carregar os modelos"))

    def usar(self, projeto, fonte, leitor) -> None:
        """O projeto com o leitor pronto: abre a última página lida (ou a primeira)."""
        p = self.pagina
        self._cancelar = None
        p.ligar(projeto, fonte, leitor)
        lidas = projeto.paginas_lidas()
        p.ir_para(lidas[-1] if lidas else 0)

    def reconhecer(self, indices: Sequence[int], refazer: bool) -> None:
        """Lê as páginas `indices` em segundo plano, gravando cada uma (`livro.reconhecer_paginas`).
        Antes, o que a janela tem por gravar é gravado: o lote grava na thread dele."""
        p = self.pagina
        if not p.pronto:
            return
        cancelar = threading.Event()

        def preparar():
            if not p.pronto:
                return None
            # O lote grava na thread dele: o que o gravador tem não pode chegar depois e
            # passar por cima do que o lote leu.
            if not p.projeto.descarregar(10):
                p.eventos.emitir("aviso", "Reconhecer o livro", "O lote não começou: há "
                                 "páginas que não puderam ser gravadas (veja a barra de "
                                 "status). Libere o disco e tente de novo.")
                return None
            projeto, fonte, leitor = p.projeto, p.fonte, p.leitor
            self._cancelar = cancelar
            p.lote_rodando = True
            self.eventos.emitir("lote_mudou")

            def trabalho(progresso):
                return livro.reconhecer_paginas(projeto, fonte, leitor, indices, refazer=refazer,
                                                progresso=progresso, cancelado=cancelar.is_set)

            def pronto(resultado: livro.ResultadoDoLote):
                self._fim()
                if p.indice in resultado.lidas:
                    p.recarregar()
                partes = [f"{len(resultado.lidas)} página(s) reconhecida(s)",
                          f"{resultado.total_de_pendentes} glifo(s) a revisar",
                          f"{sum(resultado.diagramas.values())} diagrama(s) lido(s) em FEN"]
                if resultado.puladas:
                    partes.append(f"{len(resultado.puladas)} já lida(s) pulada(s)")
                if resultado.falhas:
                    partes.append("falharam: " + ", ".join(str(i + 1) for i in resultado.falhas))
                inicio = "Lote cancelado: " if resultado.cancelado else "Lote concluído: "
                p._avisar(inicio + "; ".join(partes) + ". F6 vai ao próximo pendente do livro.",
                          15000)
            return trabalho, pronto

        def progredir(feitas: int, total: int) -> None:
            if not cancelar.is_set():
                p._avisar(f"Reconhecendo o livro: {feitas} de {total} páginas…", 0)

        def falhou(mensagem: str) -> None:
            self._fim()
            p._falhou("Reconhecer o livro")(mensagem)

        p.tarefa("Reconhecendo o livro", preparar, falhou=falhou, progresso=progredir)

    def _fim(self) -> None:
        self._cancelar = None
        self.pagina.lote_rodando = False
        self.eventos.emitir("lote_mudou")
        self.eventos.emitir("acoes_mudaram")

    def cancelar(self) -> None:
        """Pede o fim do lote; a página em leitura não é gravada pela metade."""
        if self._cancelar is not None:
            self._cancelar.set()
            self.pagina._avisar("Cancelando o lote ao fim da leitura em curso…", 0)

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
