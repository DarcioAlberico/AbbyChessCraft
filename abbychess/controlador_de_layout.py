"""As áreas da página (o editor de áreas, SPEC §14.1): o `ControladorDeLayout`.

Trabalha sobre a página aberta do `ControladorDePagina` e fala pelos mesmos `Eventos`;
acrescenta `layout_mudou`. Sem Qt.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from abbychess import historico as hs
from abbychess import margens as mg
from abbychess import servidor_de_leitura as sl
from abbychess import texto as tx
from abbychess import zonas as zn
from abbychess.controlador import AVISO_LONGO_MS, ControladorDePagina


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

    @property
    def ordem_clicada(self) -> Optional[List[int]]:
        """As áreas já clicadas no Ordenar, na ordem (None fora dele)."""
        return None if self._ordenacao is None else list(self._ordenacao)

    @property
    def ordenando(self) -> bool:
        """Se o Ordenar está em curso (o Esc o cancela antes de qualquer outra coisa)."""
        return self._ordenacao is not None

    def numeros(self) -> dict:
        """O número de cada área, pelo id: o da ordem de leitura (§5.2)."""
        modelo = self.pagina.modelo
        return tx.numeros_das_areas(modelo) if modelo is not None else {}

    def _parar_a_ordenacao(self) -> None:
        """Uma área que nasce, sai ou muda no meio do Ordenar invalida os cliques dados."""
        if self._ordenacao is not None:
            self._ordenacao = None
            self.pagina._avisar("Ordenação cancelada: as áreas mudaram.", 4000)

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
        if p.leitura.servidor_parado():
            return
        indice = p.indice

        def preparar():
            if p.indice != indice or p.imagem is None:
                return None
            imagem, leitor = p.imagem, p.leitor
            servidor = p.leitura.servidor_para_pedir()

            def trabalho(_progresso):
                if servidor is None:
                    return sl.automaticas(imagem, leitor)
                try:                                  # o árbitro dos colados é o global
                    return servidor.chamar("automaticas", imagem, timeout=sl.TEMPO_DO_PEDIDO)
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
        for z in zonas:                          # pela função, que é o que se corrige
            nome = zn.NOMES_DAS_FUNCOES[z.funcao].lower()
            tipos[nome] = tipos.get(nome, 0) + 1
        resumo = ", ".join(f"{n} {t}" for t, n in tipos.items()) or "nenhuma"
        self.pagina._avisar(f"Áreas automáticas: {resumo}. Corrija e aperte "
                            "{reconhecer_pagina}.", 10000)

    def _aprender_margens(self, zonas):
        """Dá função às margens atuais pelas repetições das páginas reconhecidas e pelos
        títulos corridos que o usuário marcou nelas (§5.1)."""
        p = self.pagina
        if p.projeto is None or p.imagem is None:
            return zonas
        paginas, areas = _lidas_e_a_aberta(p)
        confirmados = mg.confirmados_das_areas(
            {i: (paginas[i][0], areas.get(i, ())) for i in paginas})
        funcoes = mg.funcoes_das_margens(paginas, confirmados).get(p.indice, {})
        return zn.aplicar_funcoes_de_margem(zonas, paginas[p.indice][0], funcoes)

    def desenhar(self, x1: int, y1: int, x2: int, y2: int) -> None:
        p = self.pagina
        self._parar_a_ordenacao()
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
        p._avisar(f"Área {len(zonas)} de texto criada: a letra da função a troca (T texto, "
                  "H título, C cabeçalho, R rodapé, P nº de página, N nota, L legenda, "
                  "D diagrama, I imagem, X ignorar).", AVISO_LONGO_MS)

    def escolher(self, indice: int) -> None:
        if self._ordenacao is not None and 0 <= indice < len(self.zonas):
            if indice not in self._ordenacao:
                self._ordenacao.append(indice)
            if len(self._ordenacao) == len(self.zonas):
                self._ordenacao, ordem = None, self._ordenacao
                self._trocar(zn.ordenar(self.zonas, ordem), indice, "Ordenar áreas")
                self.pagina._avisar(f"Áreas ordenadas ({len(ordem)}) · Ctrl+Z desfaz.", 6000)
            else:
                self.atual = indice
                self.eventos.emitir("layout_mudou")
                self.eventos.emitir("acoes_mudaram")
                self.pagina._avisar(f"Ordenar: {len(self._ordenacao)} de {len(self.zonas)} · "
                                    "clique na próxima · Esc cancela.", 0)
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
        self._parar_a_ordenacao()
        zonas = self.zonas
        if not 0 <= indice < len(zonas):
            return
        del zonas[indice]
        self._trocar(zonas, None, "Apagar área")
        aviso = "" if zonas else " Sem áreas, a página volta à segmentação automática."
        self.pagina._avisar(f"Área apagada.{aviso}", 6000)

    def trocar_tipo(self, indice: int, tipo: str) -> None:
        self._trocar_na_area(indice, zn.trocar_tipo, tipo, "Trocar o tipo da área", zn.NOMES)

    def trocar_funcao(self, indice: int, funcao: str) -> None:
        self._trocar_na_area(indice, zn.trocar_funcao, funcao, "Trocar a função da área",
                             zn.NOMES_DAS_FUNCOES)

    def _trocar_na_area(self, indice: int, trocar, valor: str, descricao: str, nomes) -> None:
        """O tipo ou a função da área `indice` (`trocar` é o de `zonas`), com o aviso."""
        self._parar_a_ordenacao()
        zonas = self.zonas
        if not 0 <= indice < len(zonas):
            return
        trocar(zonas, indice, valor)
        self._trocar(zonas, indice, descricao)
        self.pagina._avisar(f"Área {indice + 1}: {nomes[valor].lower()}.", 5000)

    def trocar_funcao_atual(self, funcao: str) -> None:
        if self.atual is not None:
            self.trocar_funcao(self.atual, funcao)

    def levar_a_atual_ao_numero(self, numero: int) -> None:
        """A área escolhida passa a ter o `numero` na ordem de leitura; as outras andam, e a
        ordem de todas fica gravada, como no Ordenar. Um passo do desfazer."""
        zonas, atual = self.zonas, self.atual
        if atual is None or not 0 <= atual < len(zonas):
            return
        numeros = self.numeros()
        ordem = sorted(range(len(zonas)), key=lambda i: numeros.get(zonas[i].id, i + 1))
        if ordem.index(atual) == numero - 1:
            return
        ordem.remove(atual)
        ordem.insert(numero - 1, atual)
        self._parar_a_ordenacao()
        self._trocar(zn.ordenar(zonas, ordem), atual, "Mudar a ordem da área")

    def iniciar_ordenacao(self) -> None:
        if not self.zonas:
            return
        self._ordenacao = []
        self.atual = None
        self.eventos.emitir("layout_mudou")
        self.pagina._avisar("Ordenar áreas: clique em cada uma na ordem de leitura; Esc cancela.",
                            AVISO_LONGO_MS)

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
        p.eventos.emitir("acoes_mudaram")        # "Aplicar o modelo" liga já
        p._avisar(f"Modelo salvo com {len(self.zonas)} área(s): Aplicar o modelo de áreas o "
                  "leva a um intervalo de páginas.", 6000)

    def aplicar_modelo(self, indices: Sequence[int]) -> None:
        """Aplica o modelo a um intervalo já filtrado (todos, pares ou ímpares).

        Páginas de outra resolução são recusadas; todas as aceitas formam um único passo
        do desfazer do projeto.
        """
        p, modelo = self.pagina, self.modelo
        if modelo is None or p.projeto is None or p.fonte is None:
            return
        mudancas, recusadas = _aplicar_nas_paginas(p, modelo, indices)
        if mudancas:
            self._registrar_o_modelo(mudancas)
        complemento = f"; recusadas por resolução: {recusadas}" if recusadas else ""
        p._avisar(f"Modelo aplicado a {len(mudancas)} página(s){complemento}.", AVISO_LONGO_MS)

    def _registrar_o_modelo(self, mudancas: dict) -> None:
        """O modelo aplicado num passo só do desfazer; a página aberta, se mudou, mostra as
        áreas novas já."""
        p = self.pagina
        p.historico.registrar(hs.Transacao("Aplicar modelo de áreas", mudancas))
        p.eventos.emitir("acoes_mudaram")
        aberta = p.projeto.ordem.pid_em(p.indice) if p.indice is not None else None
        if aberta in mudancas:
            # A página aberta (lida ou não) mostra as zonas novas já.
            self.atual = None
            p.recarregar()
            p.eventos.emitir("layout_mudou")

    def reconhecer_atual(self) -> None:
        if self.atual is not None and 0 <= self.atual < len(self.zonas):
            self.pagina.leitura.reconhecer_zona(self.zonas[self.atual])


def _lidos(modelo) -> list:
    """Os glifos lidos (com caractere) da página do modelo; nenhum sem página."""
    return [b.entry for b in (modelo.boxes if modelo else []) if b.entry.char]


def _lidas_e_a_aberta(p: ControladorDePagina) -> Tuple[dict, dict]:
    """({índice: (glifos lidos, altura)}, {índice: áreas}) das páginas reconhecidas e da
    aberta, para aprender as margens (`margens.funcoes_das_margens`) e os títulos corridos
    confirmados (`margens.confirmados_das_areas`)."""
    paginas, areas = {}, {}
    for indice in p.projeto.resumo.paginas_lidas():
        modelo = p.modelo if indice == p.indice else p.projeto.carregar_modelo(indice)
        if modelo is None:
            continue
        areas[indice] = list(modelo.zonas)
        # Todas as páginas do livro são renderizadas no mesmo DPI. A altura aberta
        # evita renderizar as demais só para aprender a margem; pequenas variações de
        # mídia não atravessam as faixas conservadoras de 10% e 3%.
        paginas[indice] = (_lidos(modelo), p.imagem.height)
    paginas.setdefault(p.indice, (_lidos(p.modelo), p.imagem.height))
    areas.setdefault(p.indice, list(p.modelo.zonas) if p.modelo is not None else [])
    return paginas, areas


def _aplicar_nas_paginas(p: ControladorDePagina, modelo: zn.ModeloDeAreas,
                         indices: Sequence[int]):
    """`(mudanças, recusadas)`: as áreas do modelo em cada página de `indices` (pid ->
    mudança do desfazer), e as páginas (de 1) de outra resolução, que ficam como estavam."""
    from abbychess import geometria as geo

    mudancas, recusadas = {}, []
    for indice in sorted(set(indices)):
        if not 0 <= indice < p.fonte.total:
            continue
        # O tamanho da imagem da entrada sem renderizar (renderizar cada página, com a
        # medida da inclinação, prendia a janela ~0,4 s por página nunca vista).
        entrada = p.fonte.entrada(indice)
        largura, altura = geo.tamanho_da_imagem((entrada.quadro, entrada.giro),
                                                p.fonte.tamanho_da_fonte(entrada))
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
        p.projeto.paginas_em_memoria.agendar(pagina)
    return mudancas, recusadas
