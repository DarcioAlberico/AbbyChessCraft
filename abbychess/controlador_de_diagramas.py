"""Os diagramas (SPEC §14.1): o `ControladorDeDiagramas`, a conferência.

Trabalha sobre a página aberta do `ControladorDePagina` e fala pelos mesmos `Eventos`;
acrescenta `conferir(indice)` (a janela abre a conferência). Sem Qt.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from abbychess import diagramas as dg
from abbychess import lances as lc
from abbychess import servidor_de_leitura as sl
from abbychess.controlador import AVISO_LONGO_MS, ControladorDePagina

log = logging.getLogger(__name__)


class ControladorDeDiagramas:
    """A conferência dos diagramas: lê os que faltam e grava o que foi conferido."""

    def __init__(self, pagina: ControladorDePagina):
        self.pagina = pagina
        self.eventos = pagina.eventos

    def por_conferir_na_pagina(self) -> int:
        """Quantos diagramas da página aberta ainda estão por conferir: o que falhou na leitura
        não tem posição, e não conta (U-5a). A pergunta do Ctrl+T os cita (CA-U5b)."""
        return sum(1 for d in self.pagina.diagramas if _por_conferir(d))

    def proximo_do_livro(self) -> None:
        """F8: o primeiro diagrama ainda não conferido desta página, ou a próxima página do
        livro que tem um (dando a volta no livro), aberta já na conferência."""
        p = self.pagina
        if not p.pronto:
            return
        if _tem_por_conferir(p.diagramas):
            self.conferir()
            return
        com = _paginas_com(p.projeto.resumo.do_livro(), "diagramas_por_conferir")
        for proxima in _em_volta(com, p.indice):
            if not p.ir_para(proxima):
                return
            # O `livro.json` de antes conta o que falhou na leitura: esta só se vê aberta.
            if _tem_por_conferir(p.diagramas):
                self.conferir()
                return
        p._avisar("Não há diagrama por conferir no livro.", 6000)

    def vizinho_do_livro(self, passo: int) -> None:
        """PgDn (+1) na ponta da página: o primeiro diagrama da próxima página que tem algum;
        PgUp (−1): o último da anterior. Não dá a volta no livro."""
        p = self.pagina
        if not p.pronto:
            return
        alvo = _vizinha(_paginas_com(p.projeto.resumo.do_livro(), "diagramas"), p.indice, passo)
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
            com = _paginas_com(projeto.resumo.do_livro(), "diagramas")

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
            indice = _primeiro_por_conferir(diagramas)
        if not _por_ler(diagramas):
            self._abrir(indice)
            return
        if p.leitura.servidor_parado():
            return
        pagina_indice = p.indice

        def preparar():
            pagina = p.modelo
            if p.indice != pagina_indice or pagina is None:
                return None
            atuais = dg.para_caixas(pagina.tabuleiros, pagina.diagramas)
            por_ler = _por_ler(atuais)
            imagem, leitor, boxes = p.imagem, p.leitor, pagina.entries()
            caixas = [atuais[i].caixa for i in por_ler]

            servidor = p.leitura.servidor_para_pedir()

            def trabalho(_progresso):
                if servidor is None:
                    return sl.ler_diagramas(imagem, caixas, boxes, leitor)
                try:
                    return servidor.chamar("ler_diagramas", (imagem, caixas, boxes),
                                           timeout=sl.TEMPO_DO_PEDIDO)
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
                pagina.diagramas = lc.validar_pagina(pagina, p.projeto.dados.chave_das_pecas)
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
            self.pagina._avisar(f"O diagrama não foi lido: {d.erro}", AVISO_LONGO_MS)
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
        indice = _indice_da_caixa(diagramas, caixa)
        if indice is None:
            p._avisar("O diagrama mudou na página ({reconhecer_pagina}, desfazer ou áreas): reabra a "
                      "conferência.", AVISO_LONGO_MS)
            return False
        if not diagramas[indice].lido:
            p._avisar(f"O diagrama {indice + 1} não foi lido: não há posição a conferir.", 6000)
            return False
        antes = p._instantaneo()
        diagramas[indice] = diagramas[indice].conferir(tabuleiro)
        p.modelo.diagramas = diagramas
        p._mudou(p.modelo, p.indice, f"Conferir o diagrama {indice + 1}", antes)
        mensagem = f"Diagrama {indice + 1} conferido: {diagramas[indice].fen}"
        mensagem += _guardar_as_amostras(p, diagramas[indice], tabuleiro, tudo)
        p._avisar(mensagem, AVISO_LONGO_MS)
        return True


def _paginas_com(resumo: dict, chave: str) -> List[int]:
    """As páginas do resumo do livro com algum `chave` ("diagramas", "diagramas_por_conferir"),
    em ordem."""
    return sorted(i for i, r in resumo.items() if r.get(chave, 0) > 0)


def _em_volta(paginas: List[int], indice: int) -> List[int]:
    """As `paginas` depois de `indice` e, dando a volta no livro, as de antes, sem ela."""
    return [i for i in paginas if i > indice] + [i for i in paginas if i < indice]


def _tem_por_conferir(diagramas) -> bool:
    """Há algo a conferir: o que falhou na leitura não tem posição, e não prende o F8 (U-5a)."""
    return any(_por_conferir(d) for d in diagramas)


def _por_conferir(d) -> bool:
    return not d.conferido and not d.erro


def _vizinha(paginas: List[int], indice: int, passo: int) -> Optional[int]:
    """A primeira de `paginas` depois de `indice` (`passo` > 0) ou a última antes dela; None na
    ponta do livro."""
    if passo > 0:
        return next((i for i in paginas if i > indice), None)
    return next((i for i in reversed(paginas) if i < indice), None)


def _primeiro_por_conferir(diagramas) -> int:
    """O primeiro diagrama lido e ainda não conferido, ou o primeiro de todos."""
    return next((i for i, d in enumerate(diagramas) if d.lido and not d.conferido), 0)


def _por_ler(diagramas) -> List[int]:
    """Os diagramas ainda não lidos (a página gravada antes da leitura), fora os que falharam."""
    return [i for i, d in enumerate(diagramas) if not d.lido and not d.erro]


def _indice_da_caixa(diagramas, caixa) -> Optional[int]:
    """O diagrama da página que está na `caixa`, ou None se ele sumiu."""
    return next((i for i, d in enumerate(diagramas) if tuple(d.caixa) == tuple(caixa)), None)


def _guardar_as_amostras(p: ControladorDePagina, diagrama, tabuleiro, tudo: bool) -> str:
    """Guarda no projeto as casas do diagrama conferido como amostras (todas com `tudo`; senão,
    as corrigidas, se houver) e devolve o que a mensagem da conferência diz delas."""
    if not (tudo or tabuleiro.corrigidas):
        return ""
    origem = f"p{p.indice + 1:04d}"
    try:
        caminhos = dg.guardar_amostras(p.imagem, diagrama, tabuleiro, p.projeto.pasta, origem,
                                       tudo=tudo)
    except Exception as erro:  # disco cheio, pasta sem permissão, modelo ausente
        log.exception("as amostras do diagrama não foram guardadas")
        return f". As amostras não foram guardadas: {erro}"
    return f"; {len(caminhos)} amostra(s) guardadas no projeto"
