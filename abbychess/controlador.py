"""O controlador da página aberta (SPEC §14.1): os comandos da janela, sem Qt.

A janela só liga sinais a comandos e desenha o que os eventos dizem. Quem guarda a página
aberta, a fila de revisão, a seleção, o desfazer e decide o que cada comando faz é o
`ControladorDePagina`, com os colaboradores dele, cada um à parte (SPEC-qualidade Q-A1): a
fila de glifos e o andar nela (`fila_da_pagina`, a `FilaDaPagina`), as visitas
(`navegador`), as operações de página (`operacoes`), o Ctrl+Z e o Ctrl+Y (`desfazedor`), a
sessão do Documento (`sessoes`), os padrões do livro (`padroes_do_livro`) e o que vai ao
leitor e ao servidor de leitura (`leitura`, a `PonteDeLeitura`).

Tudo é **por gid** (§4.1): a fila, os pulados, a seleção e o glifo em revisão sobrevivem a
dividir, juntar e marcar sem remapear índices, e a edição muda o modelo (`abbychess.edicao`),
que o gravador grava (`CacheDoProjeto.agendar`).

**Eventos** (`Eventos`): `pagina_trocou`, `glifos_mudaram(gids)`, `atual_mudou`,
`selecao_mudou`, `padroes_mudaram`, `acoes_mudaram`, `mensagem(texto, ms)`,
`falha(titulo, texto)` e `aviso(titulo, texto)`; os outros controladores acrescentam os
deles.

**Todo comando que muda a página ou usa o leitor é uma tarefa** (`tarefa`), e as tarefas
rodam uma por vez, na ordem: a janela passa o executor do Qt, que as enfileira; os testes
passam o `ExecutorSincrono`. `preparar()` roda na thread da interface quando chega a vez
da tarefa: as edições (dividir, juntar, corrigir…) se fazem ali mesmo, e as leituras (ler,
ensinar, reconhecer) tiram o instantâneo do que precisam e devolvem `(trabalho, pronto)`;
`trabalho(progresso)` roda fora da interface sobre cópias, e `pronto(resultado)` põe o
resultado na página que a tarefa guardou. Assim o leitor nunca é usado por duas threads, e
nenhuma edição acontece no meio de uma leitura. O que o usuário pediu (os gids, o
caractere) é guardado na hora do comando: uma tarefa na fila não ensina outro glifo; e a
tarefa de outro projeto (aberto antes do atual) é descartada, pela `geracao`.

O lote (`lote.CondutorDoLote`, `lote_rodando`) não prende a janela: lê pelo servidor e
grava cada página aqui, na thread da interface, entre um comando e outro; as edições, o F5 e
o desfazer valem durante ele.

**O servidor de leitura** (§11, `servidor`): com ele, a interface não tem os modelos globais;
o leitor dela só tem os padrões do livro (a propagação, a fila), e o que eles não leem fica
"aguardando leitura". O F5, o reler, os diagramas e os glifos aguardando vão ao servidor (pela
`PonteDeLeitura`), e a resposta entra como a da propagação: nos glifos que não mudaram,
emendando a transação da edição. Antes de cada pedido, os padrões criados e apagados desde o
último vão ao servidor (`leitura.sincronizar_padroes`). Sem servidor (os testes, as
ferramentas), lê-se aqui mesmo.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from core.box_model import BoxEntry

from abbychess import ancoragem as ag
from abbychess.aplicador_do_historico import AplicadorDoHistorico
from abbychess import arrumacao
from abbychess.avisos import AVISO_LONGO_MS
from abbychess import diagramas as dg
from abbychess import edicao as ed
from abbychess import historico as hs
from abbychess.historico import Antes
from abbychess import lances as lc
from abbychess import pagina as pg
from abbychess import editar_boxes as eb
from abbychess.fila_da_pagina import FilaDaPagina
from abbychess.padroes_do_livro import ControladorDosPadroes
from abbychess.ponte_de_leitura import PonteDeLeitura
from abbychess import servidor_de_leitura as sl
from abbychess.fila_de_lances import EvidenciaNaPagina
from abbychess.sessao_do_documento import ControladorDaSessao
from abbychess import texto as tx
from abbychess.modelo import (LIDAS, NAO_RECONHECIDA, PaginaDeOutraVersao, RECONHECIDA, VERIFICADA,
                              Diferenca, Pagina, proximo_estado)
from abbychess.navegador import Navegador
from abbychess.operacoes_de_pagina import ControladorDaSequencia

log = logging.getLogger(__name__)


class Eventos:
    """Os avisos dos controladores para quem desenha. Sem Qt: quem ouve é chamado na hora,
    na thread que emitiu (a da interface, para os comandos)."""

    def __init__(self):
        self._ouvintes: Dict[str, List[Callable]] = defaultdict(list)

    def ligar(self, nome: str, funcao: Callable) -> None:
        self._ouvintes[nome].append(funcao)

    def emitir(self, nome: str, *args) -> None:
        """Chama cada ouvinte; o que levanta vai ao log com o rastro, e os outros ouvem do
        mesmo jeito: o comando que emitiu já mudou o modelo e segue (SPEC-qualidade Q-C4)."""
        for funcao in list(self._ouvintes.get(nome, ())):
            try:
                funcao(*args)
            except Exception:
                log.exception("um ouvinte de %r falhou", nome)


class ExecutorSincrono:
    """O executor dos testes e das ferramentas: roda cada tarefa na hora, na mesma thread."""

    ocupado = False

    def so_leves(self) -> bool:
        return True                         # nada fica rodando: tudo pode na hora

    def na_interface(self, funcao) -> None:
        funcao()                            # não há outra thread de interface

    def __call__(self, titulo: str, preparar, falhou=None, progresso=None, leve=False) -> None:
        par = preparar()
        if par is None:
            return
        trabalho, pronto = par
        try:
            resultado = trabalho(progresso or (lambda *_: None))
        except Exception as erro:
            log.exception("a tarefa %r falhou", titulo)
            if falhou is None:
                raise
            falhou(str(erro))
            return
        pronto(resultado)


def depois_de_editar(pagina, antes, idioma: str = "pt") -> None:
    """O que toda edição faz depois (como `ControladorDePagina._mudou`): o estado (§4.4), o
    lado dos diagramas pela legenda, os ids das áreas e dos diagramas."""
    pagina.estado = proximo_estado(pagina.estado, "editar")
    if pagina.diagramas:
        pagina.diagramas = dg.rederivar_lados(list(pagina.diagramas), antes.entries(),
                                              pagina.entries())
    arrumacao.arrumar(pagina, idioma)


class ControladorDePagina:
    """A página aberta: o modelo dela, a fila, a seleção, o desfazer e os comandos."""

    def __init__(self, eventos: Optional[Eventos] = None, executar=None):
        self.eventos = eventos or Eventos()
        self.executar = executar or ExecutorSincrono()
        self.projeto = None
        self.fonte = None
        self.leitor = None
        #: O servidor de leitura do projeto (§11), ou None: lê-se na interface.
        self.servidor: Optional[sl.ServidorDeLeitura] = None
        #: O F5, o reler, o Enter, os glifos aguardando, o palpite da rede e o servidor (§11).
        self.leitura = PonteDeLeitura(self)
        self.eventos.ligar("atual_mudou", self.leitura.sugerir_ao_atual)
        # O glifo mostrado aguardando o servidor só fica sem leitura quando a leitura chega.
        self.eventos.ligar("glifos_mudaram", lambda *_: self.leitura.sugerir_ao_atual())
        self.indice = 0
        self.imagem = None
        self.matriz: Optional[np.ndarray] = None
        #: A imagem de que a `matriz` é o cinza (quem troca `imagem` à mão não a leva junto).
        self._matriz_da_imagem = None
        self._modelo: Optional[Pagina] = None
        #: O glifo em revisão, os pulados e a seleção do modo de treino, por gid.
        self.atual: Optional[int] = None
        self.pulados: set = set()
        #: A sessão do Documento confirmada (§6.3), o parágrafo, os estilos e o modo das peças.
        self.sessoes = ControladorDaSessao(self)
        #: A evidência da página aberta (F-1, F-3, X-1), calculada quando o texto é pintado.
        self.evidencia = EvidenciaNaPagina(self)
        #: Chamado antes de sair da página aberta (outra página, o Ctrl+T): a janela confirma
        #: ali a sessão aberta do Documento (§6.3), que não pode ficar para depois.
        self.antes_de_sair_da_pagina: Optional[Callable[[], None]] = None
        #: Feito com a matriz da página na thread que a renderiza (a da pré-carga, quase
        #: sempre): a janela põe aqui a `QImage` dela, e a conversão sai da interface.
        self.preparar_imagem: Optional[Callable[[np.ndarray], object]] = None
        #: As visitas (Alt+←, Alt+→), a primeira, a última e o sentido da pré-carga.
        self.navegador = Navegador(self)
        #: (box, virtual, letra): o box marcado ao lado da letra virtual. Se o usuário o
        #: confirma com essa letra (Enter ou Shift+Enter), o virtual sai no mesmo passo.
        self._letra_que_faltava: Optional[Tuple[int, int, str]] = None
        #: A fila de glifos (§8.1): a ordem, as margens corridas, o primeiro pendente e o andar.
        self.fila_da_pagina = FilaDaPagina(self)
        #: Mover, apagar, girar, cortar, dividir… as páginas (§12.4).
        self.operacoes = ControladorDaSequencia(self)
        self.selecao: set = set()
        #: O desfazer do projeto (§14.2), da sessão.
        self.historico = hs.HistoricoDoProjeto()
        #: O Ctrl+Z e o Ctrl+Y: aplica as transações do `historico`.
        self.desfazedor = AplicadorDoHistorico(self)
        #: Esquecer amostras (§8.3), o aviso de ensino e os limiares, a notação e o idioma.
        self.padroes_do_livro = ControladorDosPadroes(self)
        #: O lote está lendo o livro (a janela mostra o progresso e o ✕; nada é recusado).
        self.lote_rodando = False
        #: Muda a cada `ligar`: a tarefa pedida para outro projeto não roda nem aplica.
        self.geracao = 0
        #: O glifo em revisão foi escolhido pelo usuário (e não posto pela fila).
        self.escolhido = False
        self.eventos.ligar("padroes_mudaram", self.leitura.sincronizar_padroes)

    # ------------------------------------------------------------------
    # O que a janela lê
    # ------------------------------------------------------------------
    @property
    def boxes(self) -> List[BoxEntry]:
        """Os glifos da página em ordem de leitura (os `BoxEntry`, para desenhar)."""
        return self.modelo.entries() if self.modelo is not None else []

    @property
    def gids(self) -> List[int]:
        return [b.gid for b in self.modelo.boxes] if self.modelo is not None else []

    def _cinza(self):
        """A página aberta para recortar glifos: a matriz do cache quando é a desta imagem
        (converter de novo custava ~7 ms em cada clique e em cada Enter), senão a imagem."""
        if self.matriz is not None and self._matriz_da_imagem is self.imagem:
            return self.matriz
        return self.imagem

    def indice_de(self, gid: Optional[int]) -> Optional[int]:
        if gid is None or self.modelo is None:
            return None
        return next((i for i, b in enumerate(self.modelo.boxes) if b.gid == gid), None)

    def gid_em(self, indice: int) -> Optional[int]:
        if self.modelo is None or not 0 <= indice < len(self.modelo.boxes):
            return None
        return self.modelo.boxes[indice].gid

    def box(self, gid: int) -> BoxEntry:
        return self.modelo.box(gid).entry

    @property
    def reconhecida(self) -> bool:
        return self.modelo is not None and self.modelo.estado in LIDAS

    @property
    def estado(self) -> str:
        return self.modelo.estado if self.modelo is not None else NAO_RECONHECIDA

    @property
    def tabuleiros(self) -> list:
        return list(self.modelo.tabuleiros) if self.modelo is not None else []

    @property
    def diagramas(self) -> List[dg.DiagramaLido]:
        """Um diagrama por tabuleiro (os por ler também), em ordem."""
        if self.modelo is None:
            return []
        return dg.para_caixas(self.modelo.tabuleiros, self.modelo.diagramas)

    @property
    def zonas(self) -> list:
        return list(self.modelo.zonas) if self.modelo is not None else []

    @property
    def pronto(self) -> bool:
        """Há projeto, fonte e leitor: os comandos valem."""
        return self.projeto is not None and self.leitor is not None and self.fonte is not None

    def alvos(self) -> List[int]:
        """O que a decisão vale: a seleção inteira, ou só o glifo em revisão (por gid, na
        ordem de leitura)."""
        if self.atual is None:
            return []
        escolhidos = self.selecao | {self.atual}
        return [g for g in self.gids if g in escolhidos]

    def texto(self) -> str:
        """O texto da página (com as decisões e os diagramas), como no painel de baixo."""
        pagina = self._pagina_do_documento()
        return "" if pagina is None else tx.texto(tx.montar(pagina), pagina.diagramas,
                                                   modo=tx.SAN)

    def diagramas_com_ids(self) -> list:
        return dg.com_ids(self.diagramas)

    def documento(self):
        """O documento derivado da página (§4.2), para o painel Documento, com os glifos que
        ninguém leu (o realce os mostra); None sem página reconhecida."""
        pagina = self._pagina_do_documento()
        return None if pagina is None else tx.montar(pagina, com_os_nao_lidos=True)

    def _pagina_do_documento(self):
        """O instantâneo da página com os diagramas de agora; None sem nada reconhecido."""
        if self.modelo is None or not (self.modelo.boxes or self.modelo.tabuleiros):
            return None
        pagina = self.modelo.instantaneo()
        pagina.diagramas = self.diagramas
        return pagina

    def linhas_dos_diagramas(self) -> List[List[lc.Lance]]:
        """A primeira linha de lances do texto que segue cada diagrama (§10), na ordem de
        `diagramas`, para a conferência validar a posição enquanto ela é corrigida."""
        if self.modelo is None or not self.modelo.tabuleiros:
            return []
        pagina = self.modelo.instantaneo()
        pagina.diagramas = dg.com_ids(self.diagramas)
        idioma = self.projeto.dados.chave_das_pecas if self.projeto is not None else "pt"
        textos = lc.textos_depois(tx.montar(pagina))
        return [lc.primeira_linha(textos.get(d.id, ""), idioma) for d in pagina.diagramas]

    def gids_virtuais(self) -> frozenset:
        """Os gids dos glifos virtuais (sem caixa) da página."""
        if self.modelo is None:
            return frozenset()
        return frozenset(v.gid for v in self.modelo.decisoes.virtuais)

    def padroes(self) -> frozenset:
        return self.padroes_de(self.leitor)

    @staticmethod
    def padroes_de(leitor) -> frozenset:
        if leitor is None:
            return frozenset()
        return frozenset(c for v in leitor.padroes_por_caractere().values() for c in v)

    # ------------------------------------------------------------------
    # Projeto e páginas
    # ------------------------------------------------------------------
    @property
    def modelo(self) -> Optional[Pagina]:
        """A página no modelo; `None` enquanto nada dela foi gravado (nasce na 1ª mudança)."""
        return self._modelo

    @modelo.setter
    def modelo(self, pagina: Optional[Pagina]) -> None:
        # O projeto a prende no cache (SPEC-qualidade Q-P3): o lote e a busca leem o mesmo
        # objeto que a janela edita, por maior que seja o lote.
        self._modelo = pagina
        if self.projeto is not None:
            self.projeto.paginas_em_memoria.prender(None if pagina is None else pagina.pid)

    def ligar(self, projeto, fonte, leitor, servidor: Optional[sl.ServidorDeLeitura] = None
              ) -> None:
        """O projeto aberto, a fonte das páginas e o leitor (os modelos já carregados; ou,
        com o `servidor`, só os padrões do livro). O servidor do projeto anterior fecha."""
        self.sessoes.zerar()                    # a fila do projeto anterior foi esvaziada
        self._letra_que_faltava = None
        if self.servidor is not None and self.servidor is not servidor:
            self.servidor.fechar()
        self.servidor = servidor
        self.leitura.zerar(leitor, servidor)
        self.fila_da_pagina.zerar()             # os pid se repetem de um projeto a outro
        self.geracao += 1
        self.lote_rodando = False               # o lote do projeto anterior não vale aqui
        self.projeto, self.fonte, self.leitor = projeto, fonte, leitor
        #: As páginas renderizadas mais recentes e a pré-carga da seguinte (§14.1), que
        #: renderiza o PDF num processo à parte (`render.do_programa`).
        from abbychess import render

        self.cache = (pg.CacheDePaginas(fonte, preparar=self.preparar_imagem,
                                        renderizador=render.do_programa())
                      if fonte is not None else None)
        self.navegador.zerar()
        self.historico = hs.HistoricoDoProjeto()
        self.modelo, self.atual, self.pulados, self.selecao = None, None, set(), set()
        self.imagem = self.matriz = None

    def desligar(self) -> None:
        self.ligar(None, None, None)

    def ir_para(self, indice: int, *, visita: bool = True) -> bool:
        """Abre a página `indice` (0 = a primeira). Falso se não deu (fora do livro, ou a
        fonte não renderizou; o motivo vai em `aviso`). `visita=False` é o Alt+← e o Alt+→,
        que andam no histórico de visitas sem mudá-lo."""
        if self.fonte is None or not 0 <= indice < self.fonte.total:
            return False
        if indice != self.indice and self.antes_de_sair_da_pagina is not None:
            self.antes_de_sair_da_pagina()
        try:
            imagem, matriz = self.cache.pagina(indice)
        except OSError as erro:
            self.eventos.emitir("aviso", "Página", str(erro))
            return False
        try:
            modelo = self.projeto.carregar_modelo(indice)
        except PaginaDeOutraVersao as erro:     # D-1: nada mudou aqui, e o arquivo fica como está
            self.eventos.emitir("aviso", "Página", f"A página {indice + 1} foi gravada por uma "
                                f"versão mais nova do programa: atualize-o para abri-la ({erro}).")
            return False
        de = self.indice
        self.indice, self.imagem, self.matriz = indice, imagem, matriz
        self._matriz_da_imagem = imagem
        self._letra_que_faltava = None
        self.navegador.chegou(de, indice, visita=visita)
        self.modelo = modelo
        self.atual, self.pulados, self.selecao = None, set(), set()
        self.eventos.emitir("pagina_trocou")
        self.eventos.emitir("glifos_mudaram", None)
        if self.boxes:
            self.fila_da_pagina.ir_ao_primeiro_pendente()
            self.leitura.ler_os_aguardando_de(self.modelo, indice, None)
            if not self.reconhecida:
                self._avisar(f"Página com {len(self.boxes)} glifo(s) marcados à mão e ainda não "
                             "reconhecida. O {reconhecer_pagina} reconhece o resto e mantém "
                             "os quadros.", 10000)
            else:
                self._avisar_os_padroes_novos(indice)
        else:
            self.eventos.emitir("atual_mudou")
        self.eventos.emitir("acoes_mudaram")
        return True

    def padroes_novos_da_pagina(self, indice: int) -> int:
        """Quantos padrões do livro foram ensinados depois da última gravação da página lida e
        ainda não revisada (`RECONHECIDA`); 0 nas outras, ou sem leitor."""
        modelo = self.modelo if indice == self.indice else None
        padroes = getattr(self.leitor, "padroes", None)
        if modelo is None or modelo.estado != RECONHECIDA or padroes is None:
            return 0
        arquivo = self.projeto.arquivo_da_pagina(indice)
        try:
            instante = arquivo.stat().st_mtime if arquivo is not None else None
        except OSError:
            instante = None
        return padroes.ensinados_depois(instante) if instante is not None else 0

    def _avisar_os_padroes_novos(self, indice: int) -> None:
        """A página lida antes do treino: o aviso do Reler (Ctrl+R), que a lê com os padrões."""
        novos = self.padroes_novos_da_pagina(indice)
        if novos:
            self._avisar(f"Esta página foi lida antes de {novos} padrão(ões) do livro ensinado(s) "
                         "depois. O {reler_pendentes} relê os pendentes com eles.", 12000)


    #: O maior ângulo de endireitar à mão, em graus (para mais, girar de 90 em 90).
    ENDIREITAR_NO_MAXIMO = 20.0


    def recarregar(self) -> None:
        """Mostra de novo a página aberta (o lote acabou de gravá-la)."""
        self.ir_para(self.indice)

    # ------------------------------------------------------------------
    # A fila de revisão
    # ------------------------------------------------------------------
    def mostrar(self, gid: Optional[int]) -> None:
        """Põe o glifo em revisão no painel de treino."""
        if gid is not None and self.indice_de(gid) is None:
            return
        self.atual = gid
        self.fila_da_pagina.guardar_lugar()
        self.escolhido = False                  # `escolher` o liga depois, se foi o usuário
        self.eventos.emitir("atual_mudou")

    def clicar(self, indice: int) -> None:
        """O box clicado no visor (pela posição na lista)."""
        self.escolher(self.gid_em(indice))

    def escolher(self, gid: Optional[int]) -> None:
        """O glifo que o usuário escolheu (clique, Tab): a propagação não o troca sozinha."""
        self.mostrar(gid)
        self.escolhido = self.atual is not None

    def verificar(self, indice: Optional[int] = None) -> None:
        """Ctrl+T: a página está verificada (§4.4), e a próxima página não verificada abre.
        Entra no desfazer; uma edição depois a devolve a `em_revisao`. Com `indice` (a
        página de que a pergunta da barra falava), nada acontece se a aberta é outra."""
        if indice is not None and indice != self.indice:
            return
        if self.antes_de_sair_da_pagina is not None:   # a sessão aberta entra antes
            self.antes_de_sair_da_pagina()
        if self.modelo is None or self.modelo.estado not in LIDAS:
            self._avisar("Reconheça a página antes de marcá-la como verificada "
                         "({reconhecer_pagina}).", 6000)
            return

        def corpo():
            antes = self._instantaneo()
            self._mudou(self.modelo, self.indice, "Página verificada", antes, evento="verificar")
            self.eventos.emitir("pagina_verificada", self.indice)
            self.eventos.emitir("acoes_mudaram")
            proxima = self._proxima_nao_verificada()
            if proxima is None:
                self._avisar("Página verificada. As seguintes já estão todas verificadas.", 6000)
                return
            verificada = self.indice + 1
            self.ir_para(proxima)
            self._avisar(f"Página {verificada} verificada; abrindo a {proxima + 1}.", 6000)
        # Na fila, depois da sessão que já espera lá: a edição não a devolve a em revisão.
        self._editar("Verificando a página", corpo, precisa_de_glifos=False)

    def _proxima_nao_verificada(self) -> Optional[int]:
        """A primeira página depois da aberta que não está verificada (a não reconhecida
        conta: está por revisar)."""
        resumo = self.projeto.resumo.do_livro()
        for i in range(self.indice + 1, self.fonte.total):
            if resumo.get(i, {}).get("estado") != VERIFICADA:
                return i
        return None

    def alternar_na_selecao(self, indice: int) -> None:
        """O Ctrl+clique do modo de treino: põe ou tira o glifo da seleção."""
        gid = self.gid_em(indice)
        if gid is None:
            return
        if _escolhido(self, gid):
            self.selecao.discard(gid)
            if gid == self.atual and self.selecao:
                self.mostrar(_primeiro_da_selecao(self))
        else:
            if self.atual is not None:
                self.selecao.add(self.atual)
            self.selecao.add(gid)
            self.mostrar(gid)
        self.eventos.emitir("selecao_mudou")

    def limpar_selecao(self) -> None:
        self.selecao = set()
        self.eventos.emitir("selecao_mudou")

    # ------------------------------------------------------------------
    # As tarefas
    # ------------------------------------------------------------------
    def tarefa(self, titulo: str, preparar, falhou=None, progresso=None, *,
               leve: bool = False) -> None:
        """Põe `preparar` na fila do executor, presa ao projeto de agora: se outro projeto
        for aberto antes da vez dela (ou antes do fim do trabalho), ela não roda (ou o
        resultado não entra). `leve` é a propagação de um Enter, que lê com uma cópia dos
        padrões: com ela rodando, as edições não esperam (`_agora`)."""
        geracao = self.geracao

        def guardado():
            if self.geracao != geracao:
                return None
            par = preparar()
            if par is None:
                return None
            trabalho, pronto = par

            def pronto_guardado(resultado):
                if self.geracao != geracao:
                    log.info("o resultado de %r foi descartado: o projeto mudou", titulo)
                    return
                pronto(resultado)
            return trabalho, pronto_guardado

        def falhou_guardado(mensagem: str) -> None:
            if self.geracao == geracao and falhou is not None:
                falhou(mensagem)

        self.executar(titulo, guardado, falhou=falhou_guardado if falhou else None,
                      progresso=progresso, leve=leve)

    def _agora(self) -> bool:
        """Uma edição pode rodar na hora: nada roda, ou só a propagação de um Enter (que lê
        com uma cópia dos padrões e só entra nos glifos que não mudaram, §14.2)."""
        so_leves = getattr(self.executar, "so_leves", None)
        return so_leves() if so_leves is not None else not getattr(self.executar, "ocupado", False)

    def _editar(self, titulo: str, corpo, *, precisa_de_glifos: bool = True,
                nao_rodou=None, so_nesta_pagina: bool = True) -> None:
        """Uma edição: na hora, se nada prende o leitor (`_agora`); senão na fila, e `corpo()`
        roda na vez dela, se a página ainda é a mesma (se não é, avisa que a edição foi
        descartada; com `so_nesta_pagina=False`, roda assim mesmo: o corpo sabe a página
        dele). `nao_rodou()`, se o corpo não rodou."""
        if self._agora():
            if self._pode_editar(precisa_de_glifos):
                corpo()
            elif nao_rodou is not None:
                nao_rodou()
            return
        indice = self.indice

        def preparar():
            if self.indice != indice and not so_nesta_pagina:
                if self.pronto:
                    corpo()
                    return None
            elif self.indice != indice:
                self._avisar(f"{titulo}: descartado, porque a página mudou (era a {indice + 1}) "
                             "antes da vez dele na fila.", AVISO_LONGO_MS)
            elif self._pode_editar(precisa_de_glifos):
                corpo()
                return None
            if nao_rodou is not None:
                nao_rodou()
            return None
        self.tarefa(titulo, preparar, falhou=self._falhou(titulo))

    # ------------------------------------------------------------------
    # Os comandos que editam (na vez deles na fila: na hora, se nada está rodando)
    # ------------------------------------------------------------------
    def _vivos(self, gids) -> List[int]:
        vivos = set(self.gids)
        return [g for g in gids if g in vivos]

    def corrigir(self, char: str) -> None:
        """Shift+Enter: aceita `char` no glifo em revisão (ou na seleção) sem ensinar."""
        if self.atual is None:
            return
        pedidos = self.alvos()

        def corpo():
            alvos = self._vivos(pedidos)
            if not alvos:
                self._avisar("O glifo a corrigir saiu da página antes da vez dele.", 6000)
                return
            antes = self._instantaneo()
            for gid in alvos:
                ed.corrigir(self.modelo, gid, char)
            self._tirar_a_letra_que_faltava(self.modelo, alvos, char)
            self.pulados.difference_update(alvos)
            self.selecao = set()
            self._mudou(self.modelo, self.indice, f"Corrigir para '{char}'", antes)
            self.eventos.emitir("selecao_mudou")
            self.fila_da_pagina.ir_ao_primeiro_pendente()
        self._editar("Corrigindo", corpo)

    def corrigir_no_livro(self, alvos, char, recortes=None) -> None:
        """A Galeria (§8.2): a leitura nos glifos `alvos` (página -> gids), em quantas páginas
        forem, num passo do desfazer e sem ensinar (digitar, Shift+Enter). `char` é um
        caractere para todos, ou {(página, gid): caractere} (cada glifo com o dele). Com
        `recortes` ((página, gid) -> o recorte do glifo), cada um também é ensinado: uma
        amostra por glifo (Enter), gravadas de uma vez. Os glifos ficam `manual`; a página
        editada sai de verificada."""
        alvos = {int(i): list(g) for i, g in alvos.items() if g}
        char_de = (char.get if isinstance(char, dict) else (lambda _chave: char))
        if not alvos or not char:
            return

        def corpo():
            transacao = hs.Transacao(_descricao_da_galeria(alvos, char_de, recortes))
            aberta, feitos, mudadas, pedidos = _corrigir_nas_paginas(self, alvos, char_de,
                                                                     recortes)
            if not mudadas:
                self._avisar("Os glifos escolhidos na Galeria saíram das páginas.", 6000)
                return
            _registrar_a_galeria(self, transacao, mudadas, pedidos)
            if transacao.amostras_criadas:
                self.eventos.emitir("padroes_mudaram")
            if aberta:
                self.selecao = set()
                self.eventos.emitir("glifos_mudaram", None)
                self.eventos.emitir("selecao_mudou")
            self.eventos.emitir("acoes_mudaram")
            # As leituras aplicadas vão no evento: a Galeria troca a grade por elas (uma ação
            # ainda na fila não confunde a grade da anterior).
            self.eventos.emitir("galeria_aplicada", feitos, len(transacao.paginas),
                                bool(transacao.amostras_criadas), _aplicadas(alvos, char_de))
        self._editar("Galeria", corpo, so_nesta_pagina=False, precisa_de_glifos=False)

    def descartar(self) -> None:
        """Del: tira o glifo da página (não é caractere)."""
        gid = self.atual
        if gid is None:
            return

        def corpo():
            if not self._vivos([gid]):
                return
            antes = self._instantaneo()
            dif = ed.descartar(self.modelo, gid)
            self._seguir(dif)
            self.selecao = set()
            self._mudou(self.modelo, self.indice, "Descartar box", antes)
            self.eventos.emitir("selecao_mudou")
            self.fila_da_pagina.ir_ao_primeiro_pendente()
        self._editar("Descartando", corpo)

    def dividir(self, coluna: Optional[int] = None, gid: Optional[int] = None) -> None:
        """Ctrl+D: divide o glifo em dois (no ponto `coluna`, ou pela tinta) e mostra a
        primeira parte, já relida."""
        gid = self.atual if gid is None else gid
        if gid is None:
            return

        def corpo():
            if not self._vivos([gid]):
                return
            antes = self._instantaneo()
            try:
                dif = ed.dividir(self.modelo, self.imagem, gid, self.leitor, x=coluna)
            except ValueError as erro:
                self._avisar(f"Não dividiu: {erro}", 6000)
                return
            self._seguir(dif)
            self._depois_de_editar(dif.novos[0].gid, "Dividir box", antes,
                                   "Box dividido em dois; as partes foram relidas.")
        self._editar("Dividindo", corpo)

    def juntar(self, passo: int, gid: Optional[int] = None) -> None:
        """Ctrl+J: junta o glifo com o vizinho da mesma linha (passo +1 ou -1)."""
        gid = self.atual if gid is None else gid
        if gid is None:
            return

        def corpo():
            i = self.indice_de(gid)
            outro = eb.vizinho(self.boxes, i, passo) if i is not None else None
            if outro is None:
                lado = "seguinte" if passo > 0 else "anterior"
                self._avisar(f"Não há box {lado} nesta linha para juntar.", 6000)
                return
            antes = self._instantaneo()
            dif = ed.juntar(self.modelo, self.imagem, gid, self.gid_em(outro), self.leitor)
            self._seguir(dif)
            self._depois_de_editar(dif.novos[0].gid, "Juntar boxes", antes,
                                   "Boxes juntados; o box novo foi relido.")
        self._editar("Juntando", corpo)

    def dividir_em(self, indice: int, coluna: int) -> None:
        """O "Dividir aqui" do menu do visor (o box pela posição na lista)."""
        gid = self.gid_em(indice)
        if gid is not None:
            self.dividir(coluna, gid)

    def juntar_com(self, indice: int, passo: int) -> None:
        gid = self.gid_em(indice)
        if gid is not None:
            self.juntar(passo, gid)

    def ajustar(self, esquerda: int, cima: int, direita: int, baixo: int) -> None:
        """Alt+seta: move as bordas do glifo em revisão, em pixels da página."""
        gid = self.atual
        if gid is None:
            return

        def corpo():
            if not self._vivos([gid]):
                return
            antes = self._instantaneo()
            try:
                ed.ajustar(self.modelo, self.imagem, gid, self.leitor, esquerda=esquerda,
                           cima=cima, direita=direita, baixo=baixo)
            except ValueError as erro:
                self._avisar(f"Não ajustou: {erro}", 6000)
                return
            b = self.box(gid)
            # Os Alt+seta seguidos no mesmo box viram um passo só.
            self._depois_de_editar(gid, "Ajustar bordas", antes,
                                   f"Box em ({b.x1}, {b.y1})–({b.x2}, {b.y2}).",
                                   juntar=("ajustar", gid))
        self._editar("Ajustando", corpo)

    def marcar(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """O quadro desenhado no modo de treino vira glifo, lido, no lugar dos de dentro."""
        if self.imagem is None:
            return

        def corpo():
            antes = self._instantaneo()
            pagina = self._pagina_para_editar()
            try:
                dif = ed.marcar(pagina, self.imagem, (x1, y1, x2, y2), self.leitor)
            except ValueError as erro:
                self._avisar(f"Não marcou: {erro}", 6000)
                return
            self._seguir(dif)
            tirados = len(dif.removidos)
            extra = f", no lugar de {tirados} box(es) de dentro" if tirados else ""
            novo = dif.novos[0].gid
            vizinho = ag.virtual_vizinho(pagina, novo)
            self._letra_que_faltava = None if vizinho is None else (novo, *vizinho)
            if vizinho is not None:             # a letra que faltava, digitada no Documento
                mensagem = (f"Glifo marcado{extra}. Se é o '{vizinho[1]}' que faltava ali, Enter "
                            "o confirma, e a letra virtual sai.")
            else:
                mensagem = f"Glifo marcado{extra}. Digite o caractere e Enter."
            self._depois_de_editar(novo, "Marcar glifo", antes, mensagem, evento="marcar")
            if vizinho is not None:
                self.eventos.emitir("caractere_sugerido", vizinho[1])
        self._editar("Marcando", corpo, precisa_de_glifos=False)

    def _tirar_a_letra_que_faltava(self, pagina: Pagina, gids, char: str) -> None:
        """O box marcado ao lado da letra virtual foi confirmado com a letra dela: ele é a
        letra que faltava, e o virtual sai (no passo do desfazer da confirmação)."""
        pendente, self._letra_que_faltava = self._letra_que_faltava, None
        if pendente is None:
            return
        box, virtual, letra = pendente
        if (box in gids and char == letra and pagina is self.modelo
                and virtual in {v.gid for v in pagina.decisoes.virtuais}):
            ed.apagar_virtual(pagina, virtual)

    def _depois_de_editar(self, mostrar: int, descricao: str, antes: hs.Instantaneo,
                          mensagem: str, *, juntar=None, evento: str = "editar") -> None:
        self.selecao = set()
        self._mudou(self.modelo, self.indice, descricao, antes, juntar=juntar, evento=evento)
        self.eventos.emitir("selecao_mudou")
        self.mostrar(mostrar)
        self._avisar(mensagem, 5000)

    # ------------------------------------------------------------------
    # Por dentro
    # ------------------------------------------------------------------
    def _avisar(self, texto: str, ms: int = 6000) -> None:
        self.eventos.emitir("mensagem", texto, ms)

    def _falhou(self, titulo: str):
        def falhou(mensagem: str) -> None:
            self.eventos.emitir("falha", titulo, mensagem)
        return falhou

    def _pode_ler(self) -> bool:
        return self.pronto and self.imagem is not None

    def _pode_editar(self, precisa_de_glifos: bool = True) -> bool:
        if not self._pode_ler():
            return False
        return not precisa_de_glifos or bool(self.boxes)

    def box_atual(self) -> Optional[BoxEntry]:
        """O glifo em revisão, ou None se ele não está mais na página (o lote a releu)."""
        i = self.indice_de(self.atual)
        return self.modelo.boxes[i].entry if i is not None else None

    def _pagina_para_editar(self) -> Pagina:
        if self.modelo is None:
            self.modelo = self.projeto.pagina_para_editar(self.indice)
        return self.modelo

    def _instantaneo(self) -> Antes:
        """A página agora, com os padrões que o livro tem, para o desfazer."""
        pagina = self.modelo.instantaneo() if self.modelo is not None else None
        return Antes(pagina, self.padroes())

    def _seguir(self, dif: Diferenca) -> None:
        """O atual passa ao primeiro sucessor; pulados e seleção ficam só com os vivos."""
        if self.atual in dif.removidos:
            sucessores = dif.sucessores.get(self.atual) or []
            self.atual = sucessores[0] if sucessores else None
        self.pulados -= dif.removidos
        self.selecao -= dif.removidos
        if dif.caidas:
            self._avisar("Decisões que não puderam seguir os glifos: " + "; ".join(dif.caidas),
                         10000)

    def _mudou(self, pagina: Pagina, indice: int, descricao: str, antes: Antes, *,
               juntar=None, evento: Optional[str] = "editar") -> hs.Transacao:
        """Depois de uma edição: o estado (§4.4), o lado dos diagramas, o passo do desfazer,
        a gravação e o aviso.

        Ensinar, corrigir, dividir ou juntar um box da legenda muda o que ela diz: o lado
        dos diagramas não conferidos sai de novo dela aqui, sem reler os tabuleiros, e
        entra no mesmo passo do desfazer (`diagramas.rederivar_lados`). O F5 já leu tudo."""
        _com_o_estado_e_os_lados(pagina, antes, evento)
        criados = _amostras_novas(self, antes)
        arrumacao.arrumar(pagina, self.projeto.dados.chave_das_pecas)
        transacao = self.historico.registrar(hs.Transacao(
            descricao, {pagina.pid: hs.mudanca(antes.pagina, pagina.instantaneo())},
            amostras_criadas=criados, juntar=juntar))
        self._gravar(pagina)
        self.leitura.ler_os_aguardando_de(pagina, indice, transacao)
        if pagina is self.modelo:
            m = transacao.paginas.get(pagina.pid)
            self.eventos.emitir("glifos_mudaram", set(m.antes) if _so_a_leitura(m) else None)
        self.eventos.emitir("acoes_mudaram")
        return transacao

    def _gravar(self, pagina: Pagina) -> None:
        if not self.projeto.paginas_em_memoria.agendar(pagina):
            self._avisar("Projeto aberto só para leitura: nada é gravado.", 6000)


# ----------------------------------------------------------------------
# As partes da seleção, do `_mudou` e da Galeria
# ----------------------------------------------------------------------

def _escolhido(p: ControladorDePagina, gid: int) -> bool:
    """O glifo já está escolhido: na seleção, ou é o atual de uma seleção vazia."""
    return gid in p.selecao or (gid == p.atual and not p.selecao)


def _primeiro_da_selecao(p: ControladorDePagina) -> int:
    """O primeiro glifo da seleção na ordem da página."""
    return next(g for g in p.gids if g in p.selecao)


def _com_o_estado_e_os_lados(pagina: Pagina, antes: Antes, evento: Optional[str]) -> None:
    """O estado da página depois do `evento` (§4.4) e o lado dos diagramas pela legenda que a
    edição mudou (não no reconhecer, que já leu tudo)."""
    if evento is not None:              # mudar só as áreas não é editar a página (§4.4)
        pagina.estado = proximo_estado(pagina.estado, evento)
    if evento not in (None, "reconhecer") and pagina.diagramas and antes.pagina is not None:
        pagina.diagramas = dg.rederivar_lados(pagina.diagramas, antes.pagina.entries(),
                                              pagina.entries())


def _amostras_novas(p: ControladorDePagina, antes: Antes) -> list:
    """As amostras que a edição criou no livro, guardadas para o desfazer."""
    criados = []
    if p.leitor is not None:
        for caminho in sorted(p.padroes() - antes.padroes):
            criados.append(p.leitor.padroes.guardar(caminho))
    return criados


def _so_a_leitura(m) -> bool:
    """Só a leitura de alguns glifos mudou (a lista e as caixas, não): a janela repinta só
    eles; senão, tudo."""
    return (m is not None and m.ordem is None and not m.campos.keys() - {"estado"}
            and all(a is not None and d is not None for a, d in
                    zip(m.antes.values(), m.depois.values())))


def _descricao_da_galeria(alvos: dict, char_de, recortes) -> str:
    """O nome do passo da Galeria no desfazer ("Corrigir para 'e' (12 glifo(s), Galeria)")."""
    n = sum(len(g) for g in alvos.values())
    chars = {char_de((i, g)) for i, gids in alvos.items() for g in gids} - {None, ""}
    nome = f"'{next(iter(chars))}'" if len(chars) == 1 else "as leituras"
    acao = "Ensinar" if recortes else "Corrigir para"
    return f"{acao} {nome} ({n} glifo(s), Galeria)"


def _corrigir_nas_paginas(p: ControladorDePagina, alvos: dict, char_de, recortes):
    """`(a aberta foi tocada, glifos corrigidos, [(página, antes)], pedidos de ensino)`: a
    leitura da Galeria nos glifos que ainda estão em cada página."""
    aberta, feitos, mudadas, pedidos = False, 0, [], []
    for indice, gids in sorted(alvos.items()):
        pagina, desta = _pagina_da_galeria(p, indice)
        aberta = aberta or desta
        vivos = set(pagina.vivos)
        gids = [g for g in gids if g in vivos and char_de((indice, g))]
        if not gids:
            continue
        antes = pagina.instantaneo()
        feitos += _corrigir_os_glifos(p, pagina, indice, gids, char_de, recortes, pedidos)
        # Como toda edição: o estado, o lado dos diagramas pela legenda corrigida e a
        # validação pelos lances (um lance do texto pode ter mudado).
        depois_de_editar(pagina, antes, p.projeto.dados.chave_das_pecas)
        mudadas.append((pagina, antes))
    return aberta, feitos, mudadas, pedidos


def _pagina_da_galeria(p: ControladorDePagina, indice: int):
    """`(a página a editar, se é a aberta)`."""
    if p.modelo is not None and indice == p.indice:
        return p.modelo, True
    return p.projeto.pagina_para_editar(indice), False


def _corrigir_os_glifos(p: ControladorDePagina, pagina: Pagina, indice: int, gids, char_de,
                        recortes, pedidos: list) -> int:
    """A leitura nos glifos da página; os que têm recorte vão a `pedidos`, para ensinar de uma
    vez. Devolve quantos."""
    from core import proporcao

    from abbychess.leitor import nome_de_origem

    referencia = proporcao.altura_de_referencia(pagina.entries()) if recortes else None
    for gid in gids:
        letra = char_de((indice, gid))
        recorte = (recortes or {}).get((indice, gid))
        if recorte is not None and p.leitor is not None:
            pedidos.append((recorte, letra, referencia, nome_de_origem(
                p.projeto.dados.nome, indice, pagina.indice_de(gid), gid)))
        ed.corrigir(pagina, gid, letra)
    return len(gids)


def _registrar_a_galeria(p: ControladorDePagina, transacao: hs.Transacao, mudadas, pedidos
                         ) -> None:
    """As amostras ensinadas de uma vez e as páginas mudadas na `transacao`, gravadas; ela vai
    ao desfazer."""
    for caminho in (p.leitor.ensinar_varios(pedidos) if pedidos else []):
        transacao.amostras_criadas.append(p.leitor.padroes.guardar(caminho))
    for pagina, antes in mudadas:
        transacao.paginas[pagina.pid] = hs.mudanca(antes, pagina.instantaneo())
        p._gravar(pagina)
    p.historico.registrar(transacao)


def _aplicadas(alvos: dict, char_de) -> dict:
    """(página, gid) -> a leitura aplicada, para a Galeria trocar a grade."""
    return {(i, g): char_de((i, g)) for i, gids in alvos.items() for g in gids
            if char_de((i, g))}
