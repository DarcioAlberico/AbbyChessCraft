"""Os outros controladores da janela (SPEC §14.1): verificação, fila e busca.

Cada um trabalha sobre a página aberta do `ControladorDePagina` e fala pelos mesmos
`Eventos`. Os que acrescentam:

- `ControladorDeVerificacao`: `palavra_mudou` (a palavra desconhecida a mostrar, ou nenhuma);
- `ControladorDaBusca`: `busca_terminou`, `busca_falhou`, `indice_mudou`.

As áreas, os diagramas, o livro e a substituição têm o seu módulo: `controlador_de_layout`,
`controlador_de_diagramas`, `controlador_do_livro` e `controlador_da_substituicao`.

Sem Qt.
"""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import CancelledError
from typing import List, Optional

from abbychess import edicao as ed
from abbychess import verificacao as vf
from abbychess.controlador import AVISO_LONGO_MS, ControladorDePagina
from abbychess.controlador_de_diagramas import ControladorDeDiagramas
from abbychess.fila_de_lances import FilaDeLances

log = logging.getLogger(__name__)


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
        #: As páginas em que o aviso do idioma já saiu nesta sessão (`_conferir_o_idioma`).
        self._idioma_avisado: set = set()
        self.desconhecidas: List[vf.Desconhecida] = []
        self.posicao = 0
        #: Os gids da página quando as palavras foram contadas (os índices delas são desta
        #: lista): uma edição depois disso não troca o glifo de uma correção.
        self._gids: List[int] = []
        pagina.eventos.ligar("pagina_trocou", self._pagina_trocou)

    def esquecer_projeto(self) -> None:
        self.lexico, self.ignoradas, self._idioma_avisado = None, set(), set()

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
                              "PyBoxEditor.", AVISO_LONGO_MS)
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
        self._com_a_camada()
        self._conferir_o_idioma()
        self.mostrar(self.posicao if posicao is None else posicao)

    def _com_a_camada(self) -> None:
        """A segunda opinião da camada de texto do PDF (`camada.opinioes`): a sugestão nas
        palavras marcadas e as que só ela desmente. Uma falha dela não para a verificação."""
        from abbychess import camada

        p = self.pagina
        try:
            palavras = camada.da_pagina(p.projeto, getattr(p, "fonte", None), p.indice)
            if palavras:
                fora = {d.lower() for d in self.ignoradas}
                self.desconhecidas = [d for d in camada.opinioes(self.desconhecidas, p.boxes,
                                                                 palavras, self.lexico)
                                      if d.palavra.lower() not in fora]
        except Exception:
            log.exception("a camada de texto do PDF não opinou")

    def _conferir_o_idioma(self) -> None:
        """O texto da página noutro idioma que o do projeto: as palavras que o léxico marca
        são quase todas certas, e as erradas se perdem entre elas (Mirkovic, p. 19: 178 com o
        português, 32 com o inglês). Avisa uma vez por página aberta."""
        from abbychess import idioma as idm
        from abbychess import texto as tx

        p = self.pagina
        if p.modelo is None or p.projeto is None or p.indice in self._idioma_avisado:
            return
        self._idioma_avisado.add(p.indice)
        dito = idm.provavel(tx.texto(tx.montar(p.modelo)))
        do_projeto = p.projeto.dados.idioma
        if dito is None or dito == (do_projeto or "").split("-")[0]:
            return
        p._avisar(f"O texto desta página parece em {idm.NOMES.get(dito, dito)}, e o idioma do "
                  f"livro é {idm.NOMES.get(do_projeto, do_projeto)}: a verificação usa o "
                  "dicionário errado. Troque em Projeto › Opções ({opcoes}).", 15000)

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
        if self._mudou_desde_a_contagem(gids):
            return
        antes = p._instantaneo()
        entries = [ed.copia(p.box(g)) for g in gids]
        indices = list(range(len(entries)))
        try:
            espacos = vf.quebras(entries, indices, texto)
            mudados = vf.corrigir(entries, indices, texto)
        except ValueError as erro:
            p._avisar(f"Não corrigiu: {erro}", AVISO_LONGO_MS)
            return
        espacos = _gravar_a_correcao(p.modelo, gids, entries, mudados, espacos)
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

        def ensinou(resolvidos: int) -> None:
            extra = f"; os padrões resolveram mais {resolvidos} na página" if resolvidos else ""
            depois(f"'{texto}': {len(mudados)} glifo(s) corrigido(s) e ensinado(s)"
                   f"{separadas}{extra}.")

        p.leitura.ensinar_gids(_gids_por_caractere(mudados, gids), descricao, ensinou,
                               juntar=passo)

    def _mudou_desde_a_contagem(self, gids) -> bool:
        """Algum glifo da palavra saiu ou mudou desde a contagem: conta as palavras de novo e
        avisa (a correção não entra)."""
        p = self.pagina
        if gids is not None and p._vivos(gids) == gids:
            return False
        self.recontar()
        p._avisar("A página mudou desde a contagem; as palavras foram contadas de novo.", 6000)
        return True

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


def _paginas_com_lances(resumo: dict) -> List[int]:
    """As páginas lidas com lance por conferir; sem a chave no resumo, conta como desconhecida."""
    return sorted(i for i, r in resumo.items()
                  if r.get("lances_por_conferir", 1) and r.get("estado") != "nao_reconhecida")


def _vizinha_com_lances(p, passo: int) -> Optional[int]:
    """A página seguinte (ou a anterior) com lance por conferir; None na ponta, ou sem projeto."""
    if p.projeto is None:
        return None
    com = _paginas_com_lances(p.projeto.resumo.do_livro())
    if passo > 0:
        return next((i for i in com if i > p.indice), None)
    return next((i for i in reversed(com) if i < p.indice), None)


def _gravar_a_correcao(modelo, gids: List[int], entries, mudados, espacos) -> List[int]:
    """Troca na página os glifos que a correção mudou e quebra a palavra nos espaços que a
    leitura não viu; devolve esses espaços, sem os que já eram quebra decidida."""
    for k, _char in mudados:
        ed.trocar(modelo, gids[k], entries[k])
    espacos = [k for k in espacos if gids[k] not in modelo.decisoes.quebras]
    for k in espacos:                         # o espaço que a leitura não viu
        ed.quebrar(modelo, gids[k])
    return espacos


def _gids_por_caractere(mudados, gids: List[int]) -> dict:
    """Os gids corrigidos de cada caractere novo, para ensinar (`ensinar_gids`)."""
    por_char: dict = {}
    for k, char in mudados:
        por_char.setdefault(char, []).append(gids[k])
    return por_char


# ----------------------------------------------------------------------
# A fila da revisão
# ----------------------------------------------------------------------

class ControladorDaFila:
    """A fila da revisão (§8.1): o modo, o escopo, e o próximo e o anterior nele (Alt+↓ /
    Alt+↑, em qualquer painel). No escopo livro (Shift+F7), o fim da fila da página leva à
    próxima página com pendentes (e o começo, à anterior), pelo resumo do `livro.json`; nas
    palavras, à página seguinte; os diagramas são sempre os do livro."""

    #: (modo, nome no seletor do Inspetor), na ordem do F7.
    MODOS = (("lances", "Lances"), ("confianca", "Confiança"), ("leitura", "Ordem de leitura"),
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
        #: A fila Lances (F-4): a linha, e não o glifo.
        self.lances = FilaDeLances(pagina)

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
            self.pagina.fila_da_pagina.ordem_da_fila = modo
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
            self._andar_nos_glifos(passo)
        else:
            {"palavras": self._andar_nas_palavras, "lances": self._andar_nos_lances,
             "diagramas": lambda _passo: self.conferencia.proximo_do_livro()}[self.modo](passo)

    def _andar_nos_glifos(self, passo: int) -> None:
        if self.escopo == "livro" and self._na_ponta(passo):
            self._outra_pagina(passo)
        else:
            self.pagina.fila_da_pagina.andar(passo)

    def _andar_nas_palavras(self, passo: int) -> None:
        v = self.verificador
        total = len(v.desconhecidas)
        na_ponta = not total or (v.posicao == total - 1 if passo > 0 else v.posicao == 0)
        if self.escopo == "livro" and na_ponta:
            self._outra_pagina_das_palavras(passo)
        else:
            v.andar(passo)

    def _andar_nos_lances(self, passo: int) -> None:
        if self.escopo == "livro" and self.lances.na_ponta(passo):
            self._outra_pagina_dos_lances(passo)
        else:
            self.lances.andar(passo)

    def _outra_pagina_dos_lances(self, passo: int) -> None:
        """A próxima página (ou a anterior) com lance por conferir, pelo resumo do livro. Página
        sem a chave no resumo conta como desconhecida: abre e conta."""
        p = self.pagina
        alvo = _vizinha_com_lances(p, passo)
        if alvo is None:
            p._avisar("Não há mais lance por conferir no livro.", 5000)
            return
        p.ir_para(alvo)
        self.lances.recontar(0 if passo > 0 else -1)

    def ir_aos_lances(self) -> None:
        """F4: a fila Lances, fixa até fechar o projeto ou escolher outra."""
        self.definir("lances")

    def andar_no_painel(self, passo: int) -> None:
        """Os botões Pular e Anterior do editor Palavra, com o sentido da fila ativa."""
        if self.modo == "lances":
            self._andar_nos_lances(passo)
        else:
            self.verificador.andar(passo)

    def corrigir_no_painel(self, texto: str, ensinar: bool = False) -> None:
        """Enter e Ctrl+Enter do editor Palavra, com o sentido da fila ativa."""
        if self.modo == "lances":
            self.lances.confirmar(texto, ensinar)
        else:
            self.verificador.corrigir(texto, ensinar=ensinar)

    def _na_ponta(self, passo: int) -> bool:
        """O atual é o último da fila da página (Alt+↓) ou o primeiro (Alt+↑), ou ela está
        vazia: a próxima ida sai da página."""
        p = self.pagina
        fila = p.fila_da_pagina.fila()
        if not fila:
            return True
        if p.atual not in fila:
            return False
        if passo > 0:
            if p.fila_da_pagina.ordem_da_fila == "confianca":  # o Alt+↓ põe o atual no fim (os pulados)
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
            p.fila_da_pagina.ir_ao_primeiro_pendente()
            p._avisar("Não há mais o que revisar no livro.", 5000)
            return
        p.ir_para(alvo)
        fila = p.fila_da_pagina.fila()
        if fila:
            p.escolher(fila[0] if passo > 0 else fila[-1])

    def _outra_pagina_das_palavras(self, passo: int) -> None:
        p = self.pagina
        if p.projeto is None or p.fonte is None:
            return
        lidas = sorted(p.projeto.resumo.paginas_lidas())
        if not lidas:
            return
        alvo = _lida_vizinha(lidas, p.indice, passo)
        if alvo != p.indice:
            p.ir_para(alvo)
        self.verificador.verificar()

    def contador(self) -> str:
        """"12/204": a posição do item atual na fila do modo, e o tamanho dela."""
        p = self.pagina
        if self.modo in self.DE_GLIFOS:
            return self._contador_dos_glifos()
        if self.modo == "lances":
            total = len(self.lances.linhas)
            return f"{self.lances.posicao + 1 if total else 0}/{total}"
        if self.modo == "palavras":
            total = len(self.verificador.desconhecidas)
            return f"{self.verificador.posicao + 1 if total else 0}/{total}"
        if p.projeto is None:
            return "0"
        resumo = p.projeto.resumo.do_livro()
        return str(sum(r.get("diagramas_por_conferir", 0) for r in resumo.values()))

    def _contador_dos_glifos(self) -> str:
        """O contador dos modos de glifos: a posição na fila da página e o tamanho dela; no
        escopo livro, também os pendentes do livro todo (os das outras páginas pelo resumo)."""
        p = self.pagina
        fila = p.fila_da_pagina.fila()
        n = fila.index(p.atual) + 1 if p.atual in fila else 0
        if self.escopo == "livro" and p.projeto is not None and p.leitor is not None:
            from abbychess import livro as lv

            outras = lv.pendentes_por_pagina(p.projeto, p.leitor.limiares)
            total = sum(v for i, v in outras.items() if i != p.indice) + len(fila)
            return f"{n}/{len(fila)} · livro {total}"
        return f"{n}/{len(fila)}"


def _lida_vizinha(lidas: List[int], indice: int, passo: int) -> int:
    """A página lida depois de `indice` (`passo` > 0) ou a antes dela; na ponta, dá a volta no
    livro (a primeira, ou a última, das `lidas`)."""
    depois = [i for i in lidas if (i > indice if passo > 0 else i < indice)]
    if not depois:
        return lidas[0] if passo > 0 else lidas[-1]
    return depois[0] if passo > 0 else depois[-1]


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
        # A ordem do livro mudou (§12.4): o índice, chaveado pela posição e com threads em voo,
        # é montado de novo (em segundo plano, como ao abrir o projeto).
        self.eventos.ligar("sequencia_mudou", self._sequencia_mudou)

    def _sequencia_mudou(self) -> None:
        if self.pagina.projeto is not None:
            self.abrir()

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
        for indice in projeto.resumo.paginas_lidas():
            versao = historico.versao(projeto.ordem.pid_em(indice))
            modelo = projeto.paginas_em_memoria.pagina(indice)
            caminho = None if modelo is not None else projeto.arquivo_da_pagina(indice)
            if modelo is not None:              # na memória (talvez sem gravar): o instantâneo
                fontes[indice] = (modelo.instantaneo(), versao)
            elif caminho is not None:
                # A posição e a geometria da entrada: o arquivo pode estar na de antes de um
                # giro (que não regrava a página, §12.4).
                entrada = projeto.sequencia.entrada_em(indice)
                fontes[indice] = ((str(caminho), indice, entrada.geometria, entrada.tamanho),
                                  versao)
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
        indice, projeto = dict(self.indice), self.pagina.projeto   # o de agora, não o da thread

        def rodar():
            vale = lambda: numero == self._busca and geracao == self._geracao   # noqa: E731
            resultado, erro, refeitas = None, None, {}
            try:
                refeitas = self._refazer(projeto, refazer, carregar, vale)
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

    def _refazer(self, projeto, refazer: dict, carregar: dict, vale) -> dict:
        """Indexa as páginas a refazer (fora da thread da interface), lidas do `projeto` de
        quando a busca foi pedida; devolve só elas."""
        from abbychess import busca as bs

        idioma, refeitas = self.idioma, {}
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
        lidas = set(projeto.resumo.paginas_lidas())
        for i in sorted(lidas):
            versao = historico.versao(projeto.ordem.pid_em(i))
            indexada = self.indice.get(i)
            if indexada is not None and indexada.versao == versao and i not in self._velhas:
                continue
            modelo = projeto.paginas_em_memoria.pagina(i)
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
        lidas = set(self.pagina.projeto.resumo.paginas_lidas()) if self.pagina.projeto else set()
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
            carregar = {i: historico.versao(projeto.ordem.pid_em(i))
                        for i in projeto.resumo.paginas_lidas()}

        def rodar():
            refeitas = {}
            try:
                refeitas = self._refazer(projeto, refazer, carregar,
                                         lambda: geracao == self._geracao)
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
                    # O índice foi montado de novo no meio. Pela ordem nova do mesmo projeto
                    # (§12.4), as posições achadas são as de antes: procura de novo. Outro
                    # projeto aberto: a procura se perde.
                    if self.pagina.projeto is projeto:
                        self.lidos_por(amostras, ao_terminar)
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

        geracao, indice, projeto = self._geracao, dict(self.indice), self.pagina.projeto
        leitura, refazer, carregar, velhas = (
            self._paginas_a_refazer() if projeto is not None and self.pronto.is_set()
            else (0, {}, {}, set()))

        def rodar():
            refeitas, achados = {}, []
            try:
                refeitas = self._refazer(projeto, refazer, carregar,
                                         lambda: geracao == self._geracao)
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
