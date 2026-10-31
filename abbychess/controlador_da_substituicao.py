"""Substituir (SPEC §7.2, passo D2): o `ControladorDaSubstituicao`.

Trabalha sobre a página aberta do `ControladorDePagina`, com o índice do `ControladorDaBusca`,
e fala pelos mesmos `Eventos`. Sem Qt.
"""

from __future__ import annotations

import logging
import threading
from typing import List, Optional

from abbychess.controlador import ControladorDePagina, depois_de_editar
from abbychess.controladores import ControladorDaBusca

log = logging.getLogger(__name__)


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

        return bs.paginas_do_escopo(self.pagina.projeto.resumo.paginas_lidas(), opcoes)

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
            versao = historico.versao(projeto.ordem.pid_em(i))
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
                    carimbo = (projeto.carimbo(i) if projeto.paginas_em_memoria.pagina(i) is None
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
                        depois_de_editar(copia, fontes[i], idioma)
                        feitas[i] = (copia, hs.mudanca(fontes[i], copia.instantaneo()),
                                     projeto.resumo.do_modelo(copia))
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
                depois_de_editar(viva, antes, self.pagina.projeto.dados.idioma)
                mudanca, resumo = hs.mudanca(antes, viva.instantaneo()), None
            transacao.paginas[viva.pid] = mudanca
            mudadas.append((viva, resumo))
        casos = sum(len(aceitos[p.indice]) for p, _r in mudadas)
        saidos = 0
        if mudadas:
            passos = pc.historico.passos
            pc.historico.registrar(transacao)
            saidos = max(0, passos + 1 - pc.historico.passos)
            gravou = all([projeto.paginas_em_memoria.agendar(p, resumo) for p, resumo in mudadas])
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
