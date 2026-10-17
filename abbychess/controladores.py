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
import os
from pathlib import Path
from typing import List, Optional, Sequence

from abbychess import diagramas as dg
from abbychess import edicao as ed
from abbychess import exportar as ex
from abbychess import livro
from abbychess import lote as lt
from abbychess import servidor_de_leitura as sl
from abbychess import verificacao as vf
from abbychess import zonas as zn
from abbychess.controlador import TEMPO_DO_PEDIDO, ControladorDePagina
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
        self._trocar(zonas, None, "Áreas automáticas")
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
        self._trocar(zonas, len(zonas) - 1, "Desenhar área")
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
        if p.modelo is None:
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
        #: O lote em andamento (`lote.CondutorDoLote`), ou None.
        self._condutor = None
        #: O que faltou do lote cancelado, `(indices, refazer)`, para retomar.
        self.restante = None
        #: O servidor cujo `modelos_prontos` já foi emitido (uma vez por servidor).
        self._modelos_avisados = None

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
        com_servidor = os.environ.get("ABBY_SERVIDOR", "1") != "0"

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

    def usar(self, projeto, fonte, leitor, servidor=None) -> None:
        """O projeto com o leitor pronto: abre a última página lida (ou a primeira)."""
        p = self.pagina
        self._largar_lote()
        p.ligar(projeto, fonte, leitor, servidor)
        lidas = projeto.paginas_lidas()
        p.ir_para(lidas[-1] if lidas else 0)

    def reconhecer(self, indices: Sequence[int], refazer: bool) -> None:
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
        condutor = lt.CondutorDoLote(
            p, indices, refazer, ao_progresso=self._progrediu,
            ao_gravar=lambda indice: self.eventos.emitir("pagina_do_lote", indice),
            ao_fim=lambda resultado: self._fim_do_lote(condutor, resultado))
        self._condutor = condutor
        p.lote_rodando = True
        self.eventos.emitir("lote_mudou")
        self.eventos.emitir("acoes_mudaram")
        condutor.comecar()

    def _progrediu(self, feitas: int, total: int, estimativa: Optional[float]) -> None:
        self.eventos.emitir("lote_progresso", feitas, total, estimativa)

    def _fim_do_lote(self, condutor, resultado) -> None:
        if self._condutor is not condutor:
            return                              # de um lote largado (outro projeto)
        self._condutor = None
        self.pagina.lote_rodando = False
        if resultado.cancelado and condutor.restante:
            self.restante = (list(condutor.restante), condutor.refazer)
        mensagem = lt.resumo_do_fim(resultado)
        if self.restante is not None:
            mensagem += " Ferramentas › Retomar o lote continua de onde parou."
        self.eventos.emitir("lote_mudou")
        self.eventos.emitir("acoes_mudaram")
        self.eventos.emitir("lote_terminou", mensagem, resultado)
        self.pagina._avisar(mensagem + " F6 vai ao próximo pendente do livro.", 15000)

    def _largar_lote(self) -> None:
        """Outro projeto: o lote deste não grava mais nada (o condutor confere a geração)."""
        if self._condutor is not None:
            self._condutor.cancelar()
        self._condutor = None
        self.restante = None

    def cancelar(self) -> None:
        """Pede o fim do lote: a página em leitura para no glifo seguinte e fica como estava;
        o que faltou fica para `retomar`."""
        if self._condutor is not None:
            self._condutor.cancelar()
            self.pagina._avisar("Cancelando o lote: a página em leitura para no glifo "
                                "seguinte…", 0)

    def retomar(self) -> None:
        """Continua o lote cancelado de onde parou (sem ler de novo as já lidas, CA-11.5)."""
        if self.restante is None or self._condutor is not None:
            return
        indices, refazer = self.restante
        self.reconhecer(indices, refazer)

    @property
    def pode_retomar(self) -> bool:
        return self.restante is not None and self._condutor is None

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
    """A fila da revisão (§8.1): o modo, e o próximo e o anterior nele (Alt+↓ / Alt+↑, em
    qualquer painel). O escopo livro (Shift+F7) é do passo C; aqui, a página."""

    #: (modo, nome no seletor do Inspetor), na ordem do F7.
    MODOS = (("confianca", "Confiança"), ("leitura", "Ordem de leitura"),
             ("palavras", "Palavras desconhecidas"), ("diagramas", "Diagramas por conferir"))
    #: Os modos que andam pelos glifos (o Inspetor mostra o Glifo).
    DE_GLIFOS = ("confianca", "leitura")

    def __init__(self, pagina: ControladorDePagina, verificador: ControladorDeVerificacao,
                 conferencia: ControladorDeDiagramas):
        self.pagina, self.verificador, self.conferencia = pagina, verificador, conferencia
        self.eventos = pagina.eventos
        self.modo = "confianca"

    def nome(self, modo: Optional[str] = None) -> str:
        return dict(self.MODOS)[modo or self.modo]

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
        da fila, e não há "anterior" a que voltar."""
        if self.modo in self.DE_GLIFOS:
            self.pagina.andar(passo)
        elif self.modo == "palavras":
            self.verificador.andar(passo)
        else:
            self.conferencia.proximo_do_livro()

    def contador(self) -> str:
        """"12/204": a posição do item atual na fila do modo, e o tamanho dela."""
        p = self.pagina
        if self.modo in self.DE_GLIFOS:
            fila = p.fila()
            n = fila.index(p.atual) + 1 if p.atual in fila else 0
            return f"{n}/{len(fila)}"
        if self.modo == "palavras":
            total = len(self.verificador.desconhecidas)
            return f"{self.verificador.posicao + 1 if total else 0}/{total}"
        if p.projeto is None:
            return "0"
        resumo = p.projeto.resumo_do_livro()
        return str(sum(r.get("diagramas_por_conferir", 0) for r in resumo.values()))
