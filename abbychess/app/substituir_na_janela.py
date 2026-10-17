"""Substituir vista da janela (SPEC §7.2, passo D2): Ctrl+H, a linha de substituir da barra,
Substituir e Todas, a prévia em Resultados e o aviso do que foi feito. Um mixin da
`JanelaPrincipal`, como `BuscaNaJanela`; quem substitui é o `ControladorDaSubstituicao`.

Substituir troca a ocorrência atual, se ela está na página aberta (senão vai até ela), e
segue para a próxima (as que já estão como o substituto são puladas); Todas, no escopo
Página ou Seleção, aplica direto; no Livro ou num intervalo, sempre monta a prévia em
Resultados, e só "Aplicar N" (Enter) aplica.
"""

from __future__ import annotations

from dataclasses import replace

from abbychess import busca as bs
from abbychess import substituir as sb
from abbychess.controladores import ControladorDaSubstituicao, _descricao


class SubstituirNaJanela:
    def _montar_substituir(self) -> None:
        self.substituicao = ControladorDaSubstituicao(self.pagina, self.busca)
        b = self.barra_de_busca
        b.substituir.connect(self.substituir_atual)
        b.substituir_todas.connect(self.substituir_todas)
        self.resultados.aplicar_previa.connect(self._aplicar_previa)
        #: Depois de Substituir: (página, posição) de onde a próxima ocorrência é buscada.
        self._ida_apos = None
        self._ida_apos_pendente = None
        #: As prévias na tela (página -> `Previa`): o Aplicar edita as páginas como elas
        #: as leram.
        self._previas: dict = {}
        e = self.eventos
        e.ligar("previa_pronta", self._previa_pronta)
        e.ligar("previa_progresso", self._previa_progresso)
        e.ligar("substituicao_falhou", self._substituicao_falhou)
        e.ligar("substituicao_feita", self._substituicao_feita)

    # ------------------------------------------------------------------
    def substituir(self) -> None:
        """Ctrl+H: a barra de Localizar com a linha de substituir."""
        if self.projeto is None:
            return
        self.localizar()
        self.barra_de_busca.abrir_substituir()

    def _limpar_previa(self) -> None:
        """Outro projeto: a prévia do anterior não vale mais."""
        self.substituicao.cancelar()
        self._previas = {}
        self.resultados.limpar_previa()

    def _alvo_e_substituto(self):
        b = self.barra_de_busca
        return b.substituto.text(), b.alvo.currentData()

    def substituir_atual(self) -> None:
        """Substituir: a ocorrência atual, se ela está na página aberta; senão vai até ela
        (ou à primeira); depois segue para a próxima."""
        b = self.barra_de_busca
        if not b.campo.text():
            b.campo.setFocus()
            return
        if b.relogio.isActive() or self.busca.buscando or self._posicao is None:
            self._andar(+1)
            return
        escopo = b.escopo.currentData()
        opcoes = replace(self._opcoes(), escopo=escopo if escopo in (bs.PAGINA, bs.SELECAO)
                         else bs.PAGINA)
        modelo, alvo = self._alvo_e_substituto()
        for _vez in range(len(self._ocorrencias)):
            o = self._ocorrencias[self._posicao]
            if o.pagina != self.pagina.indice:
                self._ir_a_ocorrencia(self._posicao)
                return
            feitos = self.substituicao.na_pagina(opcoes, modelo, alvo, posicao=o.inicio)
            if feitos is None:                  # o aviso já saiu
                return
            if feitos:
                caso = feitos[0]
                self._ida_apos_pendente = (caso.pagina, caso.inicio + len(caso.depois))
                return
            # Já está como o substituto ("casa" -> "Casa" sem o Aa): a próxima.
            self._posicao = (self._posicao + 1) % len(self._ocorrencias)
        self.statusBar().showMessage("Nada mais a substituir.", 8000)

    def substituir_todas(self) -> None:
        """Todas: direto na página (ou na seleção); no livro ou num intervalo, a prévia."""
        b = self.barra_de_busca
        if not b.campo.text():
            b.campo.setFocus()
            return
        escopo = b.escopo.currentData()
        modelo, alvo = self._alvo_e_substituto()
        if escopo == bs.SELECAO and self._selecao_congelada is None:
            b.mostrar_erro("Sem seleção: selecione o trecho no Documento e escolha Seleção.")
            return
        if escopo == bs.INTERVALO and b.intervalo_de_paginas() is None:
            b.mostrar_erro("Intervalo inválido: escreva as páginas como 3-10 (ou só 7).")
            return
        if escopo in (bs.PAGINA, bs.SELECAO):
            self.substituicao.na_pagina(self._opcoes(), modelo, alvo)
            return
        if self.substituicao.previa(self._opcoes(), modelo, alvo):
            self.statusBar().showMessage("Montando a prévia da substituição…", 0)

    # ------------------------------------------------------------------
    def _previa_progresso(self, feitas: int, total: int) -> None:
        self.statusBar().showMessage(f"Montando a prévia da substituição: {feitas} de {total} "
                                     "páginas…", 0)

    def _fora_do_onde(self, fora: int) -> str:
        """" 3 ocorrência(s) em notação ficaram fora (escolha Notação ou Ambos)."."""
        if not fora:
            return ""
        alvo = self.barra_de_busca.alvo.currentData()
        outro, escolha = (("notação", "Notação ou Ambos") if alvo == sb.PROSA
                          else ("prosa", "Prosa ou Ambos"))
        return f" {fora} ocorrência(s) em {outro} ficaram fora (escolha {escolha})."

    def _previa_pronta(self, previas, fora: int = 0) -> None:
        total = sum(len(p.casos) for p in previas)
        sem = sum(1 for p in previas for c in p.casos if not c.aplicavel)
        if not total:
            self.statusBar().showMessage("Nada a substituir." + self._fora_do_onde(fora), 10000)
            return
        b = self.barra_de_busca
        cabecalho = (f"Substituir “{b.campo.text()}” por “{b.substituto.text()}”: {total} "
                     f"caso(s) em {len(previas)} página(s)"
                     + (f", {sem} sem tradução ainda (desabilitados)" if sem else "") + "."
                     + self._fora_do_onde(fora)
                     + " Espaço desmarca · Enter aplica os marcados · Shift+Enter ou duplo "
                       "clique vai ao caso.")
        self._previas = {p.indice: p for p in previas}
        self.statusBar().clearMessage()
        self.resultados.mostrar_previa(previas, cabecalho)
        self.mostrar_resultados()
        self.resultados.focar()

    def _aplicar_previa(self, marcados) -> None:
        casos = [c for lista in marcados.values() for c in lista]
        previas, self._previas = self._previas, {}
        self.statusBar().showMessage(f"Substituindo {len(casos)} caso(s)…", 0)
        self.substituicao.aplicar(marcados, _descricao(casos), previas)

    def _substituicao_falhou(self, mensagem: str) -> None:
        self._ida_apos_pendente = None
        self.barra_de_busca.mostrar_erro(mensagem)
        self.statusBar().showMessage(mensagem, 8000)

    def _substituicao_feita(self, casos: int, paginas: int, falhas, sem_traducao: int,
                            saidos: int = 0) -> None:
        partes = [f"Substituída(s) {casos} ocorrência(s) em {paginas} página(s)"]
        if sem_traducao:
            partes.append(f"{sem_traducao} sem tradução ainda ficaram")
        if falhas:
            partes.append(f"{len(falhas)} página(s) ficaram de fora (veja os Avisos)")
            for indice, motivo in sorted(falhas.items()):
                self.eventos.emitir("aviso", "Substituir",
                                    f"Página {indice + 1} ficou fora da substituição: {motivo}.")
        if saidos:
            partes.append(f"{saidos} passo(s) mais antigo(s) do desfazer saíram para esta caber")
        if casos:
            partes.append("Ctrl+Z desfaz")
        self.statusBar().showMessage(" · ".join(partes) + ".", 10000)
        if casos and self.resultados.na_previa:  # uma prévia de antes desta troca: velha
            self._previas = {}
            self.resultados.limpar_previa("A prévia saiu: outra substituição mudou as páginas. "
                                          "Refaça Todas para ver os casos de agora.")
        self._ida_apos, self._ida_apos_pendente = self._ida_apos_pendente, None
        b = self.barra_de_busca
        if not b.isHidden() and b.campo.text():  # a contagem nova (e a próxima, se foi uma)
            b.relogio.stop()
            self._buscar()

    def _ir_depois_de_substituir(self) -> bool:
        """Na busca refeita depois de Substituir: vai à próxima ocorrência depois do que
        foi trocado. True se foi."""
        apos, self._ida_apos = self._ida_apos, None
        if apos is None or not self._ocorrencias:
            return False
        n = next((k for k, o in enumerate(self._ocorrencias) if (o.pagina, o.inicio) >= apos), 0)
        self._ida_pendente = None
        self._ir_a_ocorrencia(n)
        return True
