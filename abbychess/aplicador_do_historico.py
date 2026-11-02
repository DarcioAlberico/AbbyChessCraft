"""O Ctrl+Z e o Ctrl+Y do projeto (§14.2), à parte do `ControladorDePagina` (SPEC-qualidade
Q-A1). A transação é conferida contra as páginas e contra a ordem do livro antes de aplicar;
aplicada, o histórico anda com as páginas, antes do disco (SPEC-qualidade Q-C5). O histórico
(`HistoricoDoProjeto`) continua do controlador, que o lê em muitos lugares."""

from __future__ import annotations

import logging

from abbychess import historico as hs

log = logging.getLogger(__name__)


class AplicadorDoHistorico:
    def __init__(self, p) -> None:
        self._p = p

    def desfazer(self) -> None:
        """Ctrl+Z: desfaz a última transação do projeto (§14.2), na página dela; com só a
        propagação de um Enter rodando, na hora (e a propagação é descartada)."""
        self._desfazer_ou_refazer(refazer=False)

    def refazer(self) -> None:
        self._desfazer_ou_refazer(refazer=True)

    def _desfazer_ou_refazer(self, *, refazer: bool) -> None:
        transacao = self._proxima(refazer)
        if transacao is not None and transacao.sequencia is not None:
            motivo = self._p.operacoes.motivo_para_nao_mudar_as_paginas()
            if motivo is not None:              # a ordem não muda com o lote ou uma tarefa
                self._p.eventos.emitir("recusa", refazer, f"\u201c{transacao.descricao}\u201d "
                                       f"não pode voltar agora: {motivo}")
                return
        if self._p._agora():
            self._voltar(refazer)
        else:
            self._p.tarefa("Refazendo" if refazer else "Desfazendo",
                           lambda: (self._voltar(refazer), None)[1],
                           falhou=self._p._falhou("Desfazer"))

    def _proxima(self, refazer: bool):
        h = self._p.historico
        return h.proxima_a_refazer() if refazer else h.proxima_a_desfazer()

    def _voltar(self, refazer: bool) -> None:
        transacao = self._proxima(refazer)
        if transacao is None or self._p.leitor is None or self._p.projeto is None:
            return
        paginas = self._conferidas(transacao, refazer)
        if paginas is None or not self._aplicar_a_ordem(transacao, refazer):
            return
        self._aplicar_nas_paginas(transacao, paginas, refazer)
        self._voltar_os_padroes(transacao, refazer)
        self._reabrir(transacao)
        self._procurar_de_novo(transacao, refazer)
        self._propagar_de_novo(transacao, refazer)
        self._p.eventos.emitir("padroes_mudaram")
        self._p.eventos.emitir("acoes_mudaram")
        # Quem mostra leituras de outras páginas (a Galeria) as relê das páginas tocadas.
        self._p.eventos.emitir("historico_aplicado", set(transacao.paginas))
        self._p.leitura.ler_os_aguardando()        # o que voltou ainda sem leitura
        acao = "Refeito" if refazer else "Desfeito"
        self._p._avisar(f"{acao}: {transacao.descricao}.", 6000)

    def _conferidas(self, transacao, refazer: bool) -> dict | None:
        """As páginas da transação pelo pid, conferidas contra a ordem do livro e contra a
        transação; None (com a recusa avisada) se alguma mudou depois."""
        try:
            if transacao.sequencia is not None:
                self._conferir_a_ordem(transacao, refazer)
            return self._paginas_conferidas(transacao, refazer)
        except hs.Recusa as recusa:
            acao = "refazer" if refazer else "desfazer"
            self._p.eventos.emitir("recusa", refazer, f"Não dá para {acao} "
                                   f"“{transacao.descricao}”: {recusa}. Nada foi mudado.")
            return None

    def _conferir_a_ordem(self, transacao, refazer: bool) -> None:
        # A operação de página (§12.4): só se a ordem do livro é a que ela deixou.
        antes, depois = transacao.sequencia
        esperada = antes if refazer else depois
        if self._p.projeto.sequencia != esperada:
            raise hs.Recusa("a ordem do livro mudou depois (por outra ação)")
        if transacao.inteiras:
            self._p.projeto.paginas_em_memoria.descarregar()
        for pid, (velha, nova) in transacao.inteiras.items():
            self._conferir_a_inteira(pid, velha, nova, refazer)

    def _conferir_a_inteira(self, pid, velha, nova, refazer: bool) -> None:
        contador = self._p.projeto.proximo_n_de(pid)
        for guardada in (velha, nova):
            if contador is not None and guardada is not None:
                # Um gid nunca volta: a página que sai (a direita, no desfazer)
                # leva o contador dela para quando voltar.
                guardada.proximo_n = max(guardada.proximo_n, contador)
        if not self._p.projeto.pagina_igual(pid, velha if refazer else nova):
            posicao = self._p.projeto.ordem.posicao_de(pid)
            onde = "" if posicao is None else f" {posicao + 1}"
            raise hs.Recusa(f"a página{onde} mudou depois (por outra ação)")

    def _paginas_conferidas(self, transacao, refazer: bool) -> dict:
        paginas = {}
        for pid, m in transacao.paginas.items():
            # Pelo pid (§12.4): a página pode ter mudado de posição desde a transação.
            posicao = self._p.projeto.ordem.posicao_de(pid)
            if posicao is None:
                raise hs.Recusa(f"a página {m.indice + 1} saiu do livro")
            pagina = (self._p.modelo if self._p.modelo is not None and self._p.modelo.pid == pid
                      else self._p.projeto.carregar_modelo(posicao))
            if pagina is None or pagina.pid != pid:
                raise hs.Recusa(f"a página {posicao + 1} não é mais a da transação")
            hs.conferir(m, pagina, para_tras=not refazer)
            paginas[pid] = pagina
        return paginas

    def _aplicar_a_ordem(self, transacao, refazer: bool) -> bool:
        """A ordem do livro de antes (ou de depois) de uma operação de página; False (com a
        recusa avisada) se ela não foi gravada."""
        if transacao.sequencia is None:
            return True
        antes, depois = transacao.sequencia
        gravar = None
        if transacao.inteiras:
            gravar = self._gravar_as_inteiras(transacao, refazer)
        try:
            self._p.operacoes.aplicar_sequencia(depois if refazer else antes, gravar=gravar)
        except OSError as erro:
            self._p.eventos.emitir("recusa", refazer, "A ordem do livro não foi gravada "
                                   f"({erro}); nada foi mudado.")
            return False
        return True

    def _gravar_as_inteiras(self, transacao, refazer: bool):
        from abbychess.geometria_do_modelo import viva

        lado = 1 if refazer else 0
        alvo = {pid: None if par[lado] is None else viva(par[lado])
                for pid, par in transacao.inteiras.items()}

        def gravar(s):
            self._p.projeto.ordem.trocar_paginas(s, alvo, transacao.movidos[lado])
        return gravar

    def _aplicar_nas_paginas(self, transacao, paginas: dict, refazer: bool) -> None:
        for pid, m in transacao.paginas.items():
            hs.aplicar(m, paginas[pid], para_tras=not refazer)
        if not refazer:
            # A propagação dela, se ainda roda, não entra; e o refazer não a roda de novo
            # (refaz o que a transação guardou: o Ctrl+R relê os pendentes).
            transacao.invalidada = True
        # O histórico anda com as páginas, antes do disco (SPEC-qualidade Q-C5): o que falhar
        # depois não deixa a transação, já aplicada, na pilha de onde saiu.
        if refazer:
            self._p.historico.refeita()
        else:
            self._p.historico.desfeita()
        for pagina in paginas.values():
            self._p._gravar(pagina)

    def _voltar_os_padroes(self, transacao, refazer: bool) -> None:
        # Cada lista de uma vez (os padrões relidos uma vez só, e não por amostra: desfazer o
        # esquecer de 40 amostras levava ~0,6 s por amostra).
        voltam, saem = _voltam_e_saem(transacao, refazer)
        try:
            if voltam:
                self._p.leitor.padroes.restaurar_varios(voltam)
            existentes = [a.caminho for a in saem if a.caminho.exists()]
            if existentes:
                self._p.leitor.esquecer_varios(existentes)
        except OSError as erro:
            log.exception("os padrões de %r não voltaram", transacao.descricao)
            self._p.eventos.emitir("aviso", "Refazer" if refazer else "Desfazer",
                                   f"“{transacao.descricao}” voltou nas páginas, mas os "
                                   f"padrões do livro não ({erro}).")

    def _reabrir(self, transacao) -> None:
        aberta = self._p.modelo is not None and self._p.modelo.pid in transacao.paginas
        posicoes = sorted(p for p in map(self._p.projeto.ordem.posicao_de, transacao.paginas)
                          if p is not None)
        if aberta or not posicoes or not self._p.ir_para(posicoes[0]):
            # A página aberta mudou (ou a da transação não abre): o glifo em revisão, os
            # pulados e a seleção podem citar glifos que saíram.
            self._p.atual, self._p.pulados, self._p.selecao = None, set(), set()
            self._p.eventos.emitir("glifos_mudaram", None)
            self._p.eventos.emitir("selecao_mudou")
            self._p.fila_da_pagina.ir_ao_primeiro_pendente()

    def _procurar_de_novo(self, transacao, refazer: bool) -> None:
        if refazer and transacao.invalidada and transacao.esquecidas:
            # Um esquecer desfeito antes de a procura no livro voltar: o refazer só trouxe o
            # que a transação guardou (a página aberta); a procura roda de novo.
            transacao.invalidada = False
            self._p.padroes_do_livro.procurar_no_livro(transacao)

    def _propagar_de_novo(self, transacao, refazer: bool) -> None:
        repropagar = refazer and transacao.invalidada and transacao.amostras_criadas
        if repropagar and self._p.modelo is not None and self._p.modelo.pid in transacao.paginas:
            # Um Enter cuja propagação foi descartada quando ele foi desfeito: ela roda de
            # novo (na página dele, já aberta), com os padrões de agora, e emenda a transação.
            transacao.invalidada = False
            self._p.leitura.propagar(self._p.modelo, self._p.indice, transacao, None)

    def tirar_do_desfazer(self, refazer: bool = False) -> None:
        """Tira a próxima ação do desfazer (ou do refazer) sem aplicá-la: depois de uma
        recusa, para chegar às anteriores."""
        if refazer:
            self._p.historico.descartar_refazer()
        else:
            self._p.historico.descartar_desfazer()
        self._p.eventos.emitir("acoes_mudaram")
        self._p._avisar("A ação saiu do desfazer; o Ctrl+Z segue com as anteriores.", 6000)


def _voltam_e_saem(transacao, refazer: bool) -> tuple[list, list]:
    """As amostras que voltam aos padrões do livro e as que saem deles."""
    if refazer:
        return transacao.amostras_criadas, transacao.amostras_apagadas
    return transacao.amostras_apagadas, transacao.amostras_criadas
