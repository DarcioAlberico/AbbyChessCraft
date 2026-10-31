"""O livro (SPEC §14.1): o `ControladorDoLivro`, com o projeto aberto, o lote, a revisão
entre páginas e a exportação.

Trabalha sobre a página aberta do `ControladorDePagina` e fala pelos mesmos `Eventos`;
acrescenta `projeto_aberto` e `lote_mudou`. Sem Qt: os diálogos (que intervalo ler, onde
exportar) são da janela; aqui chegam as respostas.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import List, Optional, Sequence

from abbychess import exportar as ex
from abbychess import metadados as mtd
from abbychess import livro
from abbychess import lote as lt
from abbychess import servidor_de_leitura as sl
from abbychess.controlador import AVISO_LONGO_MS, ControladorDePagina
from abbychess.leitor import LeitorDoLivro, congelar_para_a_coleta_de_lixo

log = logging.getLogger(__name__)

#: O que o último lote deixou para retomar, na pasta do projeto.
from abbychess.projeto import ARQUIVO_DO_LOTE  # noqa: E402  (o nome mora no projeto)


class _GravadorDoLote:
    """Grava `lote.json` numa thread (o mais novo vence); `esperar` antes de ler ou no fim."""

    def __init__(self):
        self._trava = threading.Lock()
        self._pendente = None
        self._thread: Optional[threading.Thread] = None

    def gravar(self, arquivo, dados) -> None:
        with self._trava:
            self._pendente = (arquivo, dados)
            if self._thread is None:
                self._thread = threading.Thread(target=self._rodar, name="lote-json", daemon=True)
                self._thread.start()

    def _rodar(self) -> None:
        from abbychess import gravacao as gv

        while True:
            with self._trava:
                pendente, self._pendente = self._pendente, None
                if pendente is None:
                    self._thread = None
                    return
            arquivo, dados = pendente
            try:
                if dados is None:
                    gv.apagar(arquivo)
                else:
                    gv.gravar_json(arquivo, dados)
            except OSError as erro:
                log.warning("o lote a retomar não foi gravado: %s", erro)

    def esperar(self, limite: float = 10.0) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(limite)


class ControladorDoLivro:
    """O projeto aberto e o que vale para o livro inteiro."""

    def __init__(self, pagina: ControladorDePagina):
        self.pagina = pagina
        self.eventos = pagina.eventos
        #: O lote em andamento (`lote.CondutorDoLote`), ou None.
        self._condutor = None
        #: O que faltou do lote cancelado, `(indices, refazer)`, para retomar.
        self.restante = None
        #: As páginas que o lote não sobrescreveu (mudadas pelo usuário): Retomar as lê só
        #: com a confirmação dele.
        self.reler_depois: List[int] = []
        self._reler_depois_antes: List[int] = []
        #: "Abrir sem o servidor" nesta sessão (os modelos não carregaram no filho).
        self.sem_servidor = False
        self._gravador_do_lote = _GravadorDoLote()
        self.eventos.ligar("pagina_reconhecida", self._saiu_de_reler_depois)
        self.eventos.ligar("pagina_verificada", self._saiu_de_reler_depois)
        # A ordem do livro mudou (§12.4): o lote a retomar volta do `lote.json`, que é por pid.
        self.eventos.ligar("sequencia_mudou", self._ler_restante)
        #: O servidor cujo `modelos_prontos` já foi emitido (uma vez por servidor).
        self._modelos_avisados = None
        #: As três páginas do primeiro treino enquanto o lote delas está rodando.
        self._amostra_guiada: Optional[tuple[int, ...]] = None

    @property
    def lote_rodando(self) -> bool:
        return self.pagina.lote_rodando

    def _trocar_condutor(self, condutor) -> None:
        """O condutor do lote e o `lote_rodando` da página mudam juntos, só aqui (Q-A3): a
        janela e as recusas da página leem o mesmo estado."""
        self._condutor = condutor
        self.pagina.lote_rodando = condutor is not None

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
        com_servidor = not self.sem_servidor and os.environ.get("ABBY_SERVIDOR", "1") != "0"

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
            self.pagina.leitura.ler_os_aguardando()  # o que a página aberta deixou esperando
        else:
            # O primeiro tombo só vai para os Avisos; no segundo o servidor desistiu, e a
            # janela oferece reabrir o projeto (§11).
            texto, desistiu = valor             # o `desistiu` da hora do aviso
            self.eventos.emitir(evento, texto, desistiu)
            self.eventos.emitir("acoes_mudaram")        # Retomar desliga com ele parado

    def usar(self, projeto, fonte, leitor, servidor=None) -> None:
        """O projeto com o leitor pronto: abre a última página lida (ou a primeira)."""
        p = self.pagina
        self._largar_lote()
        p.ligar(projeto, fonte, leitor, servidor)
        self._ler_restante()
        lidas = projeto.resumo.paginas_lidas()
        p.ir_para(lidas[-1] if lidas else 0)

    def reconhecer(self, indices: Sequence[int], refazer: bool,
                   forcar: Sequence[int] = ()) -> None:
        """Lê as páginas `indices` pelo condutor do lote (`lote.CondutorDoLote`): pelo
        servidor, com a janela livre (as edições não esperam), e gravando cada página aqui,
        na thread da interface (o escritor único, §11)."""
        p = self.pagina
        if not p.pronto:
            return
        if self._condutor is not None:
            p._avisar("O lote já está lendo o livro. Cancele-o (✕ na barra) antes de começar "
                      "outro.", AVISO_LONGO_MS)
            return
        self.restante = None
        self._reler_depois_antes = [i for i in self.reler_depois if i not in indices]
        condutor = lt.CondutorDoLote(
            p, indices, refazer, forcar=forcar, ao_progresso=self._progrediu,
            ao_gravar=lambda indice: self.eventos.emitir("pagina_do_lote", indice),
            ao_fim=lambda resultado: self._fim_do_lote(condutor, resultado))
        self._trocar_condutor(condutor)
        self._guardar(condutor.indices, refazer, self._reler_depois_antes)
        self.eventos.emitir("lote_mudou")
        self.eventos.emitir("acoes_mudaram")
        condutor.comecar()

    def iniciar_amostra_guiada(self) -> bool:
        """Começa uma vez as páginas 10/50/90% do corpo de um projeto novo."""
        from abbychess import livro as lv

        p = self.pagina
        if not p.pronto or not p.projeto.dados.extras.get("amostra_guiada_pendente"):
            return False
        extras = p.projeto.dados.extras
        candidatos = extras.get(lv.CHAVE_DOS_CANDIDATOS_DA_AMOSTRA)
        if candidatos is not None:               # gravados por pid (§12.4)
            candidatos = p.projeto.ordem.posicoes_das_gravadas(candidatos)
        else:                                    # projeto criado antes desta chave
            ponta = p.projeto.ordem.posicoes_das_gravadas(extras.get("intervalo_do_corpo") or ())
            inicio, fim = (ponta[0], ponta[-1]) if len(ponta) == 2 else (0, p.fonte.total - 1)
            candidatos = range(max(0, int(inicio)), min(p.fonte.total - 1, int(fim)) + 1)
        candidatos = [int(i) for i in candidatos if 0 <= int(i) < p.fonte.total]
        indices = tuple(lv.paginas_da_amostra(candidatos))
        if not indices:
            extras["amostra_guiada_pendente"] = False
            p.projeto.salvar()
            return False
        p.projeto.dados.extras["amostra_guiada_pendente"] = False
        p.projeto.dados.extras[lv.CHAVE_DA_AMOSTRA] = p.projeto.ordem.paginas_para_gravar(indices)
        p.projeto.salvar()
        self._amostra_guiada = indices
        self.reconhecer(indices, refazer=False)
        return True

    def _progrediu(self, feitas: int, total: int, estimativa: Optional[float]) -> None:
        condutor = self._condutor
        if condutor is not None and feitas:     # o ponto, a cada página (G1 da rodada 3)
            self._guardar(condutor.posicoes_restantes(), condutor.refazer,
                          self._reler_depois_de(condutor), agora=False)
        self.eventos.emitir("lote_progresso", feitas, total, estimativa)

    def _fim_do_lote(self, condutor, resultado) -> None:
        if self._condutor is not condutor:
            return                              # de um lote largado (outro projeto)
        era_amostra = self._amostra_guiada is not None
        paginas_da_amostra = self._amostra_guiada or ()
        self._amostra_guiada = None
        self._trocar_condutor(None)
        # O que faltou (cancelado, ou o servidor parou) e as páginas para reler depois ficam
        # para "Retomar o lote", guardadas no projeto (`lote.json`).
        faltam = condutor.posicoes_restantes() if resultado.cancelado else []
        self._guardar(faltam, condutor.refazer, self._reler_depois_de(condutor))
        mensagem = lt.resumo_do_fim(resultado)
        if resultado.servidor_parou and faltam:
            mensagem += " Reabra o projeto e use Projeto › Retomar o lote."
        elif self.pode_retomar:
            mensagem += " Projeto › Retomar o lote continua."
        self.eventos.emitir("lote_mudou")
        self.eventos.emitir("acoes_mudaram")
        self.eventos.emitir("lote_terminou", mensagem, resultado)
        if era_amostra:
            from abbychess import livro as lv

            completa = (not resultado.cancelado and not resultado.servidor_parou
                        and not resultado.falhas
                        and set(paginas_da_amostra) <= set(resultado.lidas + resultado.puladas))
            extras = self.pagina.projeto.dados.extras
            extras["amostra_guiada_pendente"] = not completa
            if completa:
                projeto = self.pagina.projeto
                resumo = projeto.resumo.do_livro()
                # Pelo valor gravado da página (o `pid`, §12.4), como a lista da amostra.
                extras[lv.CHAVE_DOS_PENDENTES_INICIAIS] = {
                    str(g): int(resumo.get(i, {}).get("pendentes", 0) or 0)
                    for i in paginas_da_amostra
                    for g in projeto.ordem.paginas_para_gravar([i])
                }
            self.pagina.projeto.salvar()
            if completa:
                # A mensagem da amostra é a que fica (antes, o resumo do lote a apagava).
                mensagem = (f"Amostra pronta nas páginas "
                            f"{', '.join(str(i + 1) for i in paginas_da_amostra)}: revise por "
                            "caractere e ensine com Enter. O cartão Saúde, na gaveta, mostra o "
                            "que falta para o livro inteiro.")
                self.eventos.emitir("amostra_terminou", paginas_da_amostra)
        detalhe = " Detalhes em Avisos (⚠)." if lt.tem_detalhe(resultado) else ""
        self.pagina._avisar(mensagem + detalhe, 20000)

    def _reler_depois_de(self, condutor) -> List[int]:
        """As páginas para reler depois: as de antes deste lote que ele não leu, e as dele."""
        antes = [i for i in self._reler_depois_antes if i not in condutor.resultado.lidas]
        return antes + [i for i in condutor.resultado.reler_depois if i not in antes]

    def _arquivo_do_lote(self):
        p = self.pagina
        return Path(p.projeto.pasta) / ARQUIVO_DO_LOTE if p.projeto is not None else None

    def _guardar(self, faltam: Sequence[int], refazer: bool, reler_depois: Sequence[int], *,
                 agora: bool = True) -> None:
        """O que o lote deixou para retomar, na memória e em `lote.json`. É gravado ao começar
        o lote, a cada página (numa thread, `agora=False`: o fsync não fica na janela) e no
        fim; fechar o projeto no meio do lote não perde o ponto, nem deixa valer o arquivo
        de um lote anterior."""
        self.restante = (list(faltam), bool(refazer)) if faltam else None
        self.reler_depois = list(reler_depois)
        arquivo, projeto = self._arquivo_do_lote(), self.pagina.projeto
        if arquivo is None or projeto.somente_leitura:
            return
        # Por `pid` (§12.4, `pids`): a página que mudar de lugar continua no lote a retomar.
        dados = None if not faltam and not reler_depois else {
            "paginas": projeto.ordem.paginas_para_gravar(faltam), "refazer": bool(refazer),
            "reler_depois": projeto.ordem.paginas_para_gravar(reler_depois),
            "pids": projeto.ordem.gravada}
        self._gravador_do_lote.gravar(arquivo, dados)
        if agora:
            self._gravador_do_lote.esperar()

    def _ler_restante(self) -> None:
        import json

        self._gravador_do_lote.esperar()
        self.restante, self.reler_depois = None, []
        arquivo = self._arquivo_do_lote()
        if arquivo is None or not arquivo.is_file():
            return
        try:
            bruto = json.loads(arquivo.read_text(encoding="utf-8"))
            projeto, total = self.pagina.projeto, self.pagina.fonte.total
            if bruto.get("pids"):               # v3: por pid
                paginas = projeto.ordem.posicoes_das_gravadas(bruto["paginas"])
                reler = projeto.ordem.posicoes_das_gravadas(bruto.get("reler_depois", []))
            else:                               # o da v2, por posição (a migração o passa)
                paginas = [int(i) for i in bruto["paginas"] if 0 <= int(i) < total]
                reler = [int(i) for i in bruto.get("reler_depois", []) if 0 <= int(i) < total]
            self.restante = (paginas, bool(bruto["refazer"])) if paginas else None
            self.reler_depois = reler
        except (OSError, ValueError, KeyError, TypeError) as erro:
            log.warning("o lote a retomar (%s) não abriu: %s", arquivo, erro)

    def _largar_lote(self) -> None:
        """Outro projeto: o lote deste não grava mais nada (o condutor confere a geração); o
        que faltava já está em `lote.json`, gravado a cada página."""
        if self._condutor is not None:
            self._condutor.cancelar()
        self._trocar_condutor(None)
        self.restante, self.reler_depois = None, []
        self.esperar_a_gravacao()

    def esperar_a_gravacao(self) -> None:
        """O `lote.json` que a thread ainda grava chega ao disco (fechar o projeto ou trocar de
        projeto não perde o ponto da última página)."""
        self._gravador_do_lote.esperar()

    def cancelar(self) -> None:
        """Pede o fim do lote: a página em leitura para no glifo seguinte e fica como estava;
        o que faltou fica para `retomar`."""
        if self._condutor is not None:
            self._condutor.cancelar()
            self.pagina._avisar("Cancelando o lote: a página em leitura para no glifo "
                                "seguinte…", 0)

    def retomar(self, com_reler_depois: bool = False) -> None:
        """Continua o lote cancelado de onde parou (sem ler de novo as já lidas, CA-11.5); com
        `com_reler_depois` (o usuário confirmou), lê também as que ficaram para reler depois,
        que ele tinha mudado (as correções manuais ficam, §4.6)."""
        if not self.pode_retomar:
            if self.restante is not None or self.reler_depois:
                self.pagina._avisar("O servidor de leitura parou: reabra o projeto para "
                                    "retomar o lote.", AVISO_LONGO_MS)
            return
        indices, refazer = self.restante if self.restante is not None else ([], False)
        forcar = list(self.reler_depois) if com_reler_depois else []
        indices = list(indices) + [i for i in forcar if i not in indices]
        if indices:                             # o "refazer" do lote vale para o que faltou
            self.reconhecer(indices, refazer, forcar=forcar)
        else:
            self.pagina._avisar("Nada faltou do lote.", 6000)

    def _saiu_de_reler_depois(self, indice: int) -> None:
        """O F5 releu a página, ou ela foi verificada: não fica mais para reler depois."""
        if indice in self.reler_depois and self._condutor is None:
            faltam, refazer = self.restante if self.restante is not None else ([], False)
            self._guardar(faltam, refazer, [i for i in self.reler_depois if i != indice])
            self.eventos.emitir("acoes_mudaram")

    @property
    def pode_retomar(self) -> bool:
        servidor = self.pagina.servidor
        return ((self.restante is not None or bool(self.reler_depois)) and self._condutor is None
                and not (servidor is not None and servidor.parado))

    def voltar_ao_antes_do_lote(self) -> None:
        """Página › Voltar ao estado antes do lote (§4.6): a página aberta volta a ser a que
        o lote com "refazer" copiou antes de relê-la."""
        p = self.pagina
        if not p.pronto or not p.projeto.antes_do_lote.tem(p.indice):
            p._avisar("Esta página não tem cópia de antes do lote.", 6000)
            return
        try:
            pagina = p.projeto.antes_do_lote.voltar(p.indice)
        except OSError as erro:
            p.eventos.emitir("aviso", "Voltar ao estado antes do lote", str(erro))
            return
        p.historico.tocar(pagina.pid)
        p.ir_para(p.indice, visita=False)
        self.eventos.emitir("acoes_mudaram")
        p._avisar(f"A página {p.indice + 1} voltou ao estado de antes do lote.", AVISO_LONGO_MS)

    def proximo_pendente(self) -> None:
        """F6: o pendente desta página ou, se ela acabou, a próxima página com pendentes."""
        p = self.pagina
        if not p.pronto:
            return
        if p.fila_da_pagina.fila():
            p.fila_da_pagina.ir_ao_primeiro_pendente()
            return
        proxima = livro.proxima_com_pendentes(p.projeto, p.leitor.limiares, p.indice)
        if proxima is None or proxima == p.indice:
            p._avisar("Nada a revisar nas páginas reconhecidas do livro.", AVISO_LONGO_MS)
            return
        p.ir_para(proxima)
        p._avisar(f"Página {proxima + 1}: {len(p.fila_da_pagina.fila())} a revisar.", 6000)

    def previa(self, formato: str, opcoes: Optional["ex.Opcoes"], metadados: Optional[dict],
               pronto, falhou=None) -> None:
        """A pré-visualização da exportação (§12.2), fora da interface: `pronto` recebe o
        HTML. Nada é gravado (nem os metadados do formulário)."""
        p = self.pagina
        projeto = p.projeto

        def preparar():
            def trabalho(progresso):
                return ex.previa(projeto, formato, opcoes=opcoes, metadados=metadados,
                                 progresso=progresso)[0]

            def chegou(html: str):
                if p.projeto is projeto:
                    pronto(html)
                elif falhou is not None:
                    falhou("o projeto mudou")
            return trabalho, chegou

        aviso = p._falhou("Pré-visualizar")

        def falha(mensagem: str) -> None:
            aviso(mensagem)
            if falhou is not None:
                falhou(mensagem)

        p.tarefa(f"Pré-visualizando {formato.upper()}", preparar, falhou=falha)

    def exportar(self, destino: Path, opcoes: Optional["ex.Opcoes"] = None,
                 metadados: Optional[dict] = None, capa: Optional[Path] = None) -> None:
        """Escreve as páginas reconhecidas em PDF pesquisável, DOCX, EPUB, TXT ou PGN (pelo
        sufixo), com as `opcoes` do diálogo. Os `metadados` do formulário vão antes para o
        `metadados.json` do projeto (com a `capa` copiada para a pasta); num projeto só de
        leitura, ou se a gravação falhar, valem só nesta exportação, sem a capa nova."""
        p, projeto = self.pagina, self.pagina.projeto
        if metadados is not None:
            try:
                metadados = mtd.gravar_metadados(projeto, metadados, capa)
            except (OSError, ValueError) as erro:   # SomenteLeitura é um OSError
                nova = " A capa nova ficou de fora; vale a de antes." if capa is not None else ""
                p._avisar(f"Os metadados não foram gravados no projeto ({erro}); valem só "
                          f"nesta exportação.{nova}", 10000)
                try:
                    metadados = mtd.normalizar_metadados(metadados)
                except ValueError:
                    metadados = None            # o arquivo, como estava

        def preparar():
            def trabalho(progresso):
                return ex.exportar_com_relatorio(projeto, destino, progresso=progresso,
                                                 opcoes=opcoes, metadados=metadados)

            def pronto(resultado):
                resumo, relatorio = resultado
                p._avisar(f"Exportado em {destino.name}: {resumo}", 15000)
                # O relatório vai a Resultados / Avisos (§12.2), sem diálogo: um aviso por
                # item, que o duplo clique leva à página dele.
                self.eventos.emitir("relatorio", f"Exportação: {destino.name}",
                                    relatorio.linhas())
            return trabalho, pronto

        p.tarefa(f"Exportando {destino.suffix[1:].upper()}", preparar,
                   falhou=p._falhou("Exportar"))
