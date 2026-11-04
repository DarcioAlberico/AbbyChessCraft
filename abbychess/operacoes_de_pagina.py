"""As operações de página (§12.4): mover, apagar, restaurar, inserir, girar, cortar, dividir,
endireitar e a borracha (CA-12.17), à parte do `ControladorDePagina` (SPEC-qualidade Q-A1).
Cada uma grava a sequência nova, registra a transação do desfazer e leva a janela junto
(`aplicar_sequencia`, que o desfazer também usa)."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Optional, Sequence

from abbychess import historico as hs
from abbychess import sequencia as sq
from abbychess.avisos import AVISO_LONGO_MS

log = logging.getLogger(__name__)


class ControladorDaSequencia:
    def __init__(self, p) -> None:
        self._p = p
        #: Quantas vezes a ordem do livro mudou (§12.4): quem guarda posições de páginas
        #: numa espera (a Galeria do livro) confere por ele.
        self.mudancas_da_sequencia = 0

    # ------------------------------------------------------------------
    # As operações de página (§12.4, passo L): reordenar, apagar, restaurar, inserir
    # ------------------------------------------------------------------
    def motivo_para_nao_mudar_as_paginas(self) -> Optional[str]:
        """Por que as operações de página estão desligadas agora, ou None (§12.4: só para
        leitura, o lote rodando, o projeto ainda na v2)."""
        if self._p.projeto is None or self._p.fonte is None:
            return "Nenhum projeto aberto."
        if self._p.projeto.somente_leitura:
            return "O projeto está aberto só para leitura."
        if not self._p.projeto.ordem.gravada:
            return ("O projeto ainda está no formato antigo: abra-o com a fonte do livro no "
                    "lugar para passar ao novo.")
        if self._p.lote_rodando:
            return "O lote está lendo o livro: espere-o terminar, ou cancele-o."
        if self._p.leitura.lendo:
            # A leitura que chega grava a página de quando foi pedida.
            return "O servidor está lendo glifos da página: espere a leitura chegar."
        if not self._p._agora():
            # Uma tarefa (o F5, uma gravação da sessão) usa a posição de agora: mudar a
            # ordem no meio dela a faria gravar noutra página.
            return "Espere a tarefa em curso terminar."
        return None

    def mover_paginas(self, posicoes: Sequence[int], depois_da: int) -> bool:
        """As páginas das `posicoes` vão para depois da posição `depois_da` (-1: o começo)."""
        return self._mudar_sequencia(
            lambda s: s.mover(sq.pids_da_selecao(s, posicoes), depois_da),
            f"Mover {sq.quantas_paginas(len(set(posicoes)))}")

    def apagar_paginas(self, posicoes: Sequence[int]) -> bool:
        """As páginas saem do livro para as apagadas (os JSON e as amostras ficam)."""
        return self._mudar_sequencia(lambda s: s.apagar(sq.pids_da_selecao(s, posicoes)),
                                     f"Apagar {sq.quantas_paginas(len(set(posicoes)))}")

    def restaurar_paginas(self, pids: Sequence[int]) -> bool:
        """As páginas apagadas voltam ao lugar de onde saíram, com o mesmo `pid`."""
        return self._mudar_sequencia(lambda s: s.restaurar(pids),
                                     f"Restaurar {sq.quantas_paginas(len(set(pids)))}")

    def inserir_paginas(self, caminhos: Sequence, na_posicao: int) -> bool:
        """As páginas dos arquivos (PDF ou imagem, copiados para `inseridas/`) entram a partir
        da posição `na_posicao` (0: antes da primeira)."""
        from abbychess.projeto import ProjetoInvalido

        motivo = self.motivo_para_nao_mudar_as_paginas()
        if motivo is not None:
            self._p._avisar(motivo, AVISO_LONGO_MS)
            return False
        if not 0 <= na_posicao <= len(self._p.projeto.sequencia) or not caminhos:
            self._p._avisar("Inserir páginas: diga os arquivos e onde inseri-los.", AVISO_LONGO_MS)
            return False
        novas = []
        try:
            for caminho in caminhos:
                novas += self._p.projeto.ordem.inserir_arquivo(caminho)
        except (ProjetoInvalido, OSError) as erro:
            self._p.eventos.emitir("aviso", "Inserir páginas", f"{erro} Nada foi inserido.")
            return False

        def desfeita(antes: "sq.Sequencia") -> "sq.Sequencia":
            # Desfazer põe as inseridas nas apagadas (e não as esquece): lidas pelo F5 ou pelo
            # lote, que não entram no desfazer, elas voltam por Páginas apagadas, com a fonte
            # certa (um JSON de página órfão viraria página do livro).
            return sq.Sequencia(antes.entradas, antes.apagadas + tuple(
                sq.Apagada(e, na_posicao + k) for k, e in enumerate(novas)))

        return self._mudar_sequencia(lambda s: s.inserir(novas, na_posicao),
                                     f"Inserir {sq.quantas_paginas(len(novas))}",
                                     desfeita=desfeita)

    def girar_paginas(self, posicoes: Sequence[int], graus: int) -> bool:
        """Gira as páginas `graus` (90, 180 ou 270) no sentido horário (§12.4). Os boxes vão
        juntos, com conta exata (`geometria_do_modelo.reenquadrar`); a página com boxes guarda o ângulo de
        endireitar em que foi lida (`aplicar_sequencia`, também no Ctrl+Z)."""
        graus %= 360
        if graus not in (90, 180, 270):
            self._p._avisar("Girar páginas: só 90°, 180° ou 270°.", 6000)
            return False

        nota = []

        def fazer(s):
            nova = s
            pids = sq.pids_da_selecao(s, posicoes)
            for pid in pids:
                e = nova.entrada_de(pid)
                nova = nova.com_entrada(replace(e, giro=(e.giro + graus) % 360,
                                                tamanho=e.tamanho or self._tamanho(e)))
            lidas = {self._p.projeto.ordem.pid_em(i) for i in self._p.projeto.resumo.paginas_lidas()}
            if lidas.intersection(pids):
                # Os glifos vão junto, mas a leitura (a ordem das linhas, o texto deitado) é a
                # da posição de antes.
                nota.append("a leitura é da posição de antes; F5 lê de novo")
            return nova

        sentido = {90: "à direita", 180: "de cabeça para baixo", 270: "à esquerda"}[graus]
        return self._mudar_sequencia(
            fazer, f"Girar {sq.quantas_paginas(len(set(posicoes)))} {sentido}", nota=nota)

    def cortar_paginas(self, posicoes: Sequence[int], margens: Sequence[float]) -> bool:
        """Corta as páginas pelas margens `(esquerda, cima, direita, baixo)`, frações da imagem
        que se vê (uma página já cortada é cortada dentro do que se vê). O glifo que sai do
        quadro fica guardado na página (`Pagina.fora`): o Ctrl+Z, ou tirar o corte, o
        devolvem com o mesmo gid."""
        from abbychess import geometria as geo

        esquerda, cima, direita, baixo = (float(m) for m in margens)
        if min(esquerda, cima, direita, baixo) < 0 or esquerda + direita >= 1 \
                or cima + baixo >= 1:
            self._p._avisar("Cortar páginas: as margens somadas deixam a página vazia.", 6000)
            return False

        def fazer(s):
            nova = s
            for pid in sq.pids_da_selecao(s, posicoes):
                e = nova.entrada_de(pid)
                tamanho = e.tamanho or self._tamanho(e)
                largura, altura = geo.tamanho_da_imagem(e.geometria, tamanho)
                vista = (round(esquerda * largura), round(cima * altura),
                         largura - round(direita * largura), altura - round(baixo * altura))
                if vista[2] <= vista[0] or vista[3] <= vista[1]:
                    raise ValueError(f"a página {s.posicao_de(pid) + 1} ficaria vazia")
                nova = nova.com_entrada(replace(
                    e, quadro=geo.quadro_da_vista(vista, e.geometria, tamanho), tamanho=tamanho))
            return nova

        return self._mudar_sequencia(fazer, f"Cortar {sq.quantas_paginas(len(set(posicoes)))}")

    def tirar_o_corte(self, posicoes: Sequence[int]) -> bool:
        """A página inteira de volta (o giro fica); os glifos guardados voltam. A metade de
        uma divisão não: o quadro dela é a divisão (o Ctrl+Z junta as metades)."""
        def fazer(s):
            nova = s
            for pid in sq.pids_da_selecao(s, posicoes):
                e = nova.entrada_de(pid)
                if e.metade is not None:
                    raise ValueError(f"a página {s.posicao_de(pid) + 1} é a metade de uma "
                                     "divisão; o Ctrl+Z da divisão junta as metades")
                nova = nova.com_entrada(replace(e, quadro=None))
            return nova

        return self._mudar_sequencia(
            fazer, f"Tirar o corte de {sq.quantas_paginas(len(set(posicoes)))}")

    def apagar_manchas(self, posicao: int, caixas: Sequence[Sequence[int]]) -> bool:
        """A borracha (CA-12.17): as `caixas` `(x1, y1, x2, y2)`, marcadas na imagem que se vê
        da página na `posicao` (aparadas nela), ficam brancas. Elas vão à entrada da sequência,
        na página da fonte antes de endireitar (`geometria.borracha_na_fonte`), e seguem o
        corte, o giro e o ângulo; a leitura não muda (o glifo lido na área fica até o F5 ou o
        Del, e o aviso diz quantos são)."""
        from abbychess import geometria as geo

        nota = []

        def fazer(s):
            e = s.entrada_em(posicao)
            tamanho = e.tamanho or self._tamanho(e)
            largura, altura = geo.tamanho_da_imagem(e.geometria, tamanho)
            vistas = [c for c in (_aparada(c, largura, altura) for c in caixas) if c]
            if not vistas:
                raise ValueError("a área marcada fica fora da página")
            angulo = self._p.fonte.inclinacao_da_entrada(e)
            novas = tuple(geo.borracha_na_fonte(c, e.geometria, tamanho, angulo) for c in vistas)
            lidos = self._glifos_nas_caixas(posicao, vistas)
            if lidos:
                nota.append(f"{lidos} glifo{' lido fica' if lidos == 1 else 's lidos ficam'} "
                            "na área; F5 lê de novo, ou Del o apaga")
            return s.com_entrada(replace(e, tamanho=tamanho, borrachas=e.borrachas + novas))

        return self._mudar_sequencia(fazer, f"Borracha na página {posicao + 1}", nota=nota)

    def tirar_as_borrachas(self, posicoes: Sequence[int]) -> bool:
        """As áreas apagadas das páginas voltam como eram na fonte."""
        def fazer(s):
            nova = s
            for pid in sq.pids_da_selecao(s, posicoes):
                nova = nova.com_entrada(replace(nova.entrada_de(pid), borrachas=()))
            return nova

        return self._mudar_sequencia(
            fazer, f"Tirar a borracha de {sq.quantas_paginas(len(set(posicoes)))}")

    def _glifos_nas_caixas(self, posicao: int, caixas) -> int:
        """Quantos glifos lidos da página tocam as caixas (na imagem que se vê)."""
        pagina = self._p.projeto.carregar_modelo(posicao)
        if pagina is None:
            return 0
        return sum(any(b.entry.x1 < x2 and x1 < b.entry.x2 and b.entry.y1 < y2
                       and y1 < b.entry.y2 for x1, y1, x2, y2 in caixas)
                   for b in pagina.boxes)

    def dividir_paginas(self, posicoes: Sequence[int], fracao: float = 0.5) -> bool:
        """Divide as páginas espelhadas (§12.4) na `fracao` da largura do que se vê: a metade
        esquerda fica com o `pid`, a direita entra logo depois com um `pid` novo, e os glifos
        dela ganham gids novos (`gids_movidos`, para as amostras acharem a origem). As páginas
        são gravadas inteiras com a sequência; o Ctrl+Z as junta de novo e aposenta o `pid`
        novo. A metade de uma divisão não se divide de novo: na seleção, ela é pulada (com
        aviso). Nada é medido aqui (seria um render por página, na thread da interface): a
        direita recebe o ângulo guardado da página, e sem ele mede o mesmo, da mesma página
        inteira, quando abrir."""
        fracao = float(fracao)
        if not 0 < fracao < 1:
            self._p._avisar("Dividir páginas: a divisão fica dentro da página.", 6000)
            return False
        angulos, troca, nota = [], {}, []

        def fazer(s):
            projeto = self._p.projeto
            projeto.paginas_em_memoria.descarregar()               # nada do gravador chega depois da divisão
            movidos = dict(projeto.dados.gids_movidos)
            nova, paginas, metades = s, {}, 0
            for pid in sq.pids_da_selecao(s, posicoes):
                e = nova.entrada_de(pid)
                if e.metade is not None:
                    metades += 1
                    continue
                esquerda, direita, divididas = self._dividir_a_pagina(s, e, fracao)
                nova = nova.com_entrada(esquerda)
                nova = nova.inserir([direita], nova.posicao_de(pid) + 1)
                self._guardar_as_divididas(e, direita, divididas, paginas, movidos, angulos)
            if metades and nova == s:
                raise ValueError("as páginas escolhidas já são metades de uma divisão")
            if metades:
                nota.append(_nota_das_metades(metades))
            troca.update(paginas=paginas, movidos=(dict(projeto.dados.gids_movidos), movidos))
            return nova

        sequencia = self._p.projeto.sequencia if self._p.projeto is not None else None
        ja_metades = {p for p in set(posicoes) if sequencia is not None
                      and 0 <= p < len(sequencia) and sequencia.entrada_em(p).metade}
        a_dividir = len(set(posicoes)) - len(ja_metades) or len(set(posicoes))
        return self._mudar_sequencia(fazer, f"Dividir {sq.quantas_paginas(a_dividir)}",
                                     troca=troca, nota=nota,
                                     depois_de_gravar=lambda: self._guardar_os_angulos(angulos))

    def endireitar_paginas(self, posicoes: Sequence[int], angulo: Optional[float]) -> bool:
        """Endireita as páginas à mão (§12.4, CA-12.14): o `angulo` (graus, anti-horário, como
        `pagina.girar`) vence o medido; None volta ao medido. A leitura da página com glifos
        se desfaz: ficam os marcados à mão (a leitura digitada, ou o glifo aceito na revisão),
        girados em volta do centro, e as áreas do usuário; o resto sai, e a página vai a
        `glifos_marcados` (`geometria_do_modelo.endireitar`). O Ctrl+Z devolve o ângulo e a página."""
        from abbychess import geometria_do_modelo as gm
        from abbychess.leitor import FONTE_MANUAL

        if angulo is not None:
            angulo = round(float(angulo), 2)
            if abs(angulo) > self._p.ENDIREITAR_NO_MAXIMO:
                self._p._avisar(f"Endireitar páginas: no máximo {self._p.ENDIREITAR_NO_MAXIMO:g}° "
                                "(para mais, gire a página).", 6000)
                return False

        def manter(box) -> bool:
            return box.entry.source == FONTE_MANUAL or box.revisado

        troca = {}

        def fazer(s):
            projeto = self._p.projeto
            projeto.paginas_em_memoria.descarregar()
            nova, paginas = s, {}
            for pid in sq.pids_da_selecao(s, posicoes):
                e = nova.entrada_de(pid)
                if e.angulo == angulo:
                    continue
                tamanho = e.tamanho or self._tamanho(e)
                outra = replace(e, angulo=angulo, tamanho=tamanho)
                nova = nova.com_entrada(outra)
                pagina = projeto.carregar_modelo(s.posicao_de(pid))
                if pagina is None:
                    continue                    # sem leitura: nada a medir nem a girar
                delta = self._p.fonte.inclinacao_da_entrada(outra) - \
                    self._p.fonte.inclinacao_da_entrada(e)
                if delta:
                    paginas[pid] = (pagina.instantaneo(),
                                    gm.endireitar(pagina, delta, tamanho, manter))
            if paginas:
                movidos = dict(projeto.dados.gids_movidos)
                troca.update(paginas=paginas, movidos=(movidos, movidos))
            return nova

        como = "pelo ângulo medido" if angulo is None else f"em {angulo:g}°"
        return self._mudar_sequencia(
            fazer, f"Endireitar {sq.quantas_paginas(len(set(posicoes)))} {como}", troca=troca)

    def _tamanho(self, entrada) -> tuple:
        return tuple(self._p.fonte.tamanho_da_fonte(entrada))

    def _angulos_a_guardar(self, antes, nova) -> list:
        """(entrada nova, ângulo) de cada página com boxes que muda de giro: ela fica no
        ângulo de endireitar em que foi lida (§12.4: um ângulo medido de novo, na página
        girada, os tiraria do lugar). Vale na operação e no Ctrl+Z e Ctrl+Y dela: a página
        lida depois do giro desfeito guarda o ângulo do giro. Só lê; `_guardar_os_angulos`
        grava."""
        mudam = [e for e in nova.entradas
                 if antes.entrada_de(e.pid) is not None
                 and antes.entrada_de(e.pid).giro != e.giro]
        if not mudam:
            return []
        # O guardado, sem medir (um render por página, na thread da interface): a página lida
        # foi aberta e medida; a que ganhou boxes sem abrir não tem ângulo a guardar.
        com_dados = {self._p.projeto.ordem.pid_em(i) for i in self._p.projeto.resumo.do_livro()}
        angulos = []
        for e in mudam:
            if e.pid in com_dados:
                guardado = self._p.fonte.inclinacao_guardada(antes.entrada_de(e.pid))
                if guardado is not None:
                    angulos.append((e, guardado))
        return angulos

    def _guardar_os_angulos(self, angulos) -> None:
        """Grava os ângulos (a sequência nova já está gravada, e a página girada ainda não foi
        mostrada) e tira do cache a imagem endireitada por outro ângulo."""
        if not angulos:
            return
        try:
            self._p.fonte.fixar_inclinacoes(angulos)
        except OSError:
            # O ângulo vale na memória; numa outra sessão a página é medida de novo, e os
            # boxes podem andar uns pixels.
            log.warning("os ângulos de %d página(s) não foram gravados", len(angulos),
                        exc_info=True)
        if self._p.cache is not None:
            for entrada, _angulo in angulos:
                self._p.cache.esquecer(entrada)

    def _dividir_a_pagina(self, s: sq.Sequencia, e, fracao: float) -> tuple:
        """As entradas das duas metades da página `e` cortada em `fracao` da largura do que se
        vê (a direita com um `pid` novo) e (a página, gm.dividir dela), ou None sem nada
        gravado; `ValueError` se a página é estreita demais."""
        from abbychess import geometria as geo
        from abbychess import geometria_do_modelo as gm

        projeto = self._p.projeto
        tamanho = e.tamanho or self._tamanho(e)
        largura, altura = geo.tamanho_da_imagem(e.geometria, tamanho)
        corte = round(fracao * largura)
        if not 0 < corte < largura:
            raise ValueError(f"a página {s.posicao_de(e.pid) + 1} é estreita demais")
        pid_novo = projeto.ordem.novo_pid()
        esquerda = replace(e, metade="esquerda", tamanho=tamanho,
                           quadro=geo.quadro_da_vista((0, 0, corte, altura),
                                                      e.geometria, tamanho))
        direita = replace(e, pid=pid_novo, metade="direita", tamanho=tamanho,
                          quadro=geo.quadro_da_vista((corte, 0, largura, altura),
                                                     e.geometria, tamanho))
        pagina = projeto.carregar_modelo(s.posicao_de(e.pid))
        divididas = None if pagina is None else (
            pagina, gm.dividir(pagina, corte, esquerda.geometria, direita.geometria, tamanho,
                               pid_novo))
        return esquerda, direita, divididas

    def _guardar_as_divididas(self, e, direita, divididas, paginas: dict, movidos: dict,
                              angulos: list) -> None:
        """As páginas de antes e de depois, os gids que mudaram de página e o ângulo da
        direita, para a transação."""
        if divididas is None:
            paginas[e.pid] = paginas[direita.pid] = (None, None)
            return
        pagina, (pagina_e, pagina_d, m) = divididas
        paginas[e.pid] = (pagina.instantaneo(), pagina_e)
        paginas[direita.pid] = (None, pagina_d)
        movidos.update({str(velho): novo for velho, novo in m.items()})
        # Os boxes da direita estão no ângulo em que a página foi lida (o
        # guardado; sem ele, a direita mede o mesmo, da mesma página inteira).
        guardado = self._p.fonte.inclinacao_guardada(e)
        if guardado is not None:
            angulos.append((direita, guardado))

    def _mudar_sequencia(self, fazer, descricao: str, *, desfeita=None,
                         depois_de_gravar=None, troca: Optional[dict] = None,
                         nota: Sequence[str] = ()) -> bool:
        """Uma operação de página: a sequência nova gravada, uma transação do desfazer com a
        de antes e a de depois (§14.2), e a janela seguindo a página aberta. `desfeita(antes)`
        é a sequência que o desfazer põe, quando não é a de antes (a do inserir);
        `depois_de_gravar()` roda com a sequência nova gravada, antes de mostrar a página.
        `troca`, que `fazer` preenche, traz as páginas trocadas inteiras (dividir):
        `paginas` (pid -> (instantâneo antes, a página nova)) e `movidos` (os `gids_movidos`
        antes e depois). `nota`, que `fazer` também preenche, vai no aviso de feito."""
        motivo = self.motivo_para_nao_mudar_as_paginas()
        if motivo is not None:
            self._p._avisar(motivo, AVISO_LONGO_MS)
            return False
        if self._p.antes_de_sair_da_pagina is not None:
            # A sessão do Documento aberta entra antes: `fazer` olha quais páginas têm boxes.
            self._p.antes_de_sair_da_pagina()
        antes = self._p.projeto.sequencia
        nova = self._nova_sequencia(fazer, antes, descricao)
        if nova is None:
            return False
        if nova == antes:
            self._p._avisar(f"{descricao}: nada muda.", 6000)
            return False
        if desfeita is not None:
            antes = desfeita(antes)
        transacao = hs.Transacao(descricao, sequencia=(antes, nova))
        gravar = self._com_as_inteiras(transacao, troca)
        try:
            self.aplicar_sequencia(nova, depois_de_gravar, gravar)
        except OSError as erro:
            self._p.eventos.emitir("aviso", "Páginas", f"{descricao} não foi gravado ({erro}); "
                                   "nada mudou.")
            return False
        self._p.historico.registrar(transacao)
        self._p.eventos.emitir("acoes_mudaram")
        extra = "".join(f" ({n})" for n in nota)
        self._p._avisar(f"Feito: {descricao}{extra}. Ctrl+Z desfaz.", 6000)
        return True

    def _nova_sequencia(self, fazer, antes: sq.Sequencia, descricao: str):
        """A sequência que `fazer` monta, ou None com o aviso do que a impediu."""
        try:
            return fazer(antes)
        except (ValueError, IndexError) as erro:
            self._p._avisar(f"{descricao}: {erro}.", AVISO_LONGO_MS)
        except (OSError, RuntimeError) as erro:   # a fonte ilegível (o tamanho, o ângulo)
            self._p.eventos.emitir("aviso", "Páginas", f"{descricao}: a fonte não foi lida "
                                   f"({erro}); nada mudou.")
        return None

    def _com_as_inteiras(self, transacao, troca: Optional[dict]):
        """As páginas trocadas inteiras (dividir) na transação, e o `gravar` que as grava com
        a sequência; None sem elas."""
        if not troca:
            return None
        novas = {pid: depois for pid, (_antes, depois) in troca["paginas"].items()}
        transacao.inteiras = {
            pid: (velha, None if depois is None else depois.instantaneo())
            for pid, (velha, depois) in troca["paginas"].items()}
        transacao.movidos = troca["movidos"]

        def gravar(s):
            self._p.projeto.ordem.trocar_paginas(s, novas, troca["movidos"][1])
        return gravar

    def aplicar_sequencia(self, nova: "sq.Sequencia", depois_de_gravar=None,
                          gravar=None) -> None:
        """Grava a sequência (com `gravar(nova)`, se dado: a das páginas trocadas inteiras) e
        leva a janela junto: as visitas e a página aberta pelo `pid` (a apagada dá lugar à
        vizinha), e `sequencia_mudou` para quem guarda posições."""
        projeto = self._p.projeto
        aberta = projeto.sequencia.entrada_em(self._p.indice) if self._p.imagem is not None else None
        visitas = self._p.navegador.pids_das_visitas(projeto)
        angulos = self._angulos_a_guardar(projeto.sequencia, nova)
        (gravar or projeto.ordem.gravar)(nova)      # OSError: nada mudou
        self._guardar_os_angulos(angulos)
        if depois_de_gravar is not None:
            depois_de_gravar()
        self._p.navegador.seguir_a_sequencia(visitas, nova)
        if aberta is not None:
            alvo = nova.posicao_de(aberta.pid)
            if alvo is None:
                alvo = min(self._p.indice, len(nova) - 1)
            if alvo != self._p.indice or nova.entrada_em(alvo) != aberta:
                self._p.ir_para(alvo, visita=False)    # a página aberta mudou de lugar ou saiu
        self.mudancas_da_sequencia += 1
        self._p.eventos.emitir("sequencia_mudou")


def _aparada(caixa, largura: int, altura: int):
    """A caixa `(x1, y1, x2, y2)` aparada na imagem `largura` × `altura`, ou None se nada
    dela fica dentro (ou ela é vazia)."""
    x1, y1, x2, y2 = (int(v) for v in caixa)
    x1, y1, x2, y2 = max(x1, 0), max(y1, 0), min(x2, largura), min(y2, altura)
    return (x1, y1, x2, y2) if x2 > x1 and y2 > y1 else None


def _nota_das_metades(metades: int) -> str:
    """A nota do aviso de feito: quantas das escolhidas já eram metades e ficaram."""
    return (f"{sq.quantas_paginas(metades)} já "
            f"{'era metade' if metades == 1 else 'eram metades'}, e "
            f"{'ficou' if metades == 1 else 'ficaram'} como "
            f"{'estava' if metades == 1 else 'estavam'}")
