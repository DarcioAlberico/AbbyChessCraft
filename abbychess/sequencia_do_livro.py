"""A sequência do livro no projeto (§12.4), à parte do `ProjetoDeLivro` (SPEC-qualidade Q-A1). A
estrutura é a de `abbychess.sequencia` (a ordem das páginas, a entrada de cada `pid`, as
apagadas); aqui fica a do projeto aberto: montá-la ao criar e ao abrir, dos dados da v3 ou da v2,
com os consertos do que uma queda deixou (`montar`, `da_v2`; ler não grava, SPEC-qualidade
Q-P8), o `pid` de cada posição e a posição de cada `pid` (`pid_em`, `posicao_de`), o contador de
`pid` que nunca volta (`novo_pid`, `inserir_arquivo`, §4.1), as listas gravadas por `pid` ou por
posição (`paginas_para_gravar`, `posicoes_das_gravadas`), a página do PDF de cada página
(`pagina_da_fonte`) e a origem das amostras antigas (`origem_da_amostra`). Trocá-la é das
operações de página (`gravar`, e `trocar_paginas` para dividir e o desfazer dela): o
`projeto.json` primeiro, e só depois a memória. As páginas, o cache delas, o resumo do livro, a
trava do livro e o `projeto.json` são do projeto (`self._p`)."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from abbychess import gravacao as gv
from abbychess import sequencia as sq
from abbychess.modelo import Pagina
from abbychess.pagina_em_json import inteiro, pagina_de_json, pagina_para_json
from abbychess.pasta_do_projeto import ARQUIVO_DO_PROJETO, PASTA_DE_PAGINAS, VERSAO

log = logging.getLogger(__name__)

#: O `indice` gravado da página que não é uma do PDF do livro (`pagina_da_fonte`).
FORA_DO_PDF = -1


class SequenciaDoLivro:
    def __init__(self, p) -> None:
        self._p = p
        #: A sequência do livro (§12.4): a posição de cada `pid`. Montada na primeira vez que
        #: alguém pergunta (`sequencia`), dos dados da v2; `_proximo_pid` é o primeiro `pid`
        #: acima dela, para as páginas que ela ainda não tem.
        self._sequencia: Optional[sq.Sequencia] = None
        self._proximo_pid = 0
        #: (sequência, página do PDF -> primeira posição dela): a origem das amostras antigas.
        self._posicoes_do_pdf: Optional[tuple] = None

    # ------------------------------------------------------------------
    # Montar (§12.4)
    # ------------------------------------------------------------------
    @property
    def sequencia(self) -> sq.Sequencia:
        """A ordem das páginas e o `pid` de cada uma. Ler não grava (SPEC-qualidade Q-P8):
        antes de `montar`, a pergunta a monta só na memória."""
        sequencia = self._sequencia
        if sequencia is None:
            with self._p._trava_do_livro:
                if self._sequencia is None:
                    self._sequencia, self._proximo_pid = self._montar(gravar=False)
                sequencia = self._sequencia
        return sequencia

    @property
    def ja_montada(self) -> Optional[sq.Sequencia]:
        """A sequência, sem montá-la: None antes da primeira montagem (quem monta lê páginas,
        e a leitura delas pergunta daqui)."""
        return self._sequencia

    def montar(self) -> sq.Sequencia:
        """Monta a sequência e grava o que a montagem conserta (o `livro.json` que falta, a
        página em disco que ele não cita, a sequência que o `projeto.json` da v3 não tem, as
        páginas fora dela): ao criar e ao abrir, na thread de quem abre e antes de qualquer
        render (o fitz que conta as páginas não roda junto com um render da pré-carga)."""
        with self._p._trava_do_livro:
            if not self._p.somente_leitura:
                self._p.resumo.esquecer()          # o do disco: o conserto da memória vai a ele
                self._p.resumo.carregar(gravar=True)
            self._sequencia, proximo = self._montar(gravar=True)
            self._proximo_pid = max(self._proximo_pid, proximo)
            return self._sequencia

    def adotar(self, sequencia: sq.Sequencia, proximo: int) -> None:
        """A sequência montada por fora (a migração à v3, a da v2 do projeto só para leitura
        cuja sequência gravada esta versão não lê), com o próximo `pid` acima dela."""
        self._sequencia, self._proximo_pid = sequencia, max(self._proximo_pid, proximo)

    def _montar(self, gravar: bool) -> Tuple[sq.Sequencia, int]:
        """A sequência gravada (v3), ou a montada dos dados da v2. O projeto da v3 sem ela
        (o projeto novo, ou um `projeto.json` que a perdeu) a monta pela ordem do PDF e, com
        `gravar`, a grava já; o da v2 só para leitura a tem só na memória."""
        if self._p.dados.sequencia is not None:
            return self._lida(gravar)
        sequencia, proximo = self.da_v2(gravar)
        if (gravar and self._p.dados.versao >= VERSAO and not self._p.somente_leitura
                and self._p.fonte.is_file()):
            self._p.dados.sequencia = sequencia.para_json()
            self._p.dados.proximo_pid = max(self._p.dados.proximo_pid, proximo)
            self._p.salvar()
        return sequencia, proximo

    def _lida(self, gravar: bool) -> Tuple[sq.Sequencia, int]:
        """A sequência do `projeto.json`. Um `p<pid>.json` que não está nela nem nas apagadas
        (uma queda entre gravações, §12.4) entra nas apagadas, no fim; todo arquivo em disco
        fica abaixo do próximo `pid`."""
        from abbychess.projeto import ProjetoInvalido

        try:
            sequencia = sq.Sequencia.de_json(self._p.dados.sequencia)
        except (KeyError, TypeError, ValueError) as erro:
            raise ProjetoInvalido(f"A sequência do livro em {ARQUIVO_DO_PROJETO} está "
                                  f"ilegível: {erro}") from erro
        conhecidos = set(sequencia.todos_os_pids)
        em_disco = sorted(int(a.stem[1:])
                          for a in (self._p.pasta / PASTA_DE_PAGINAS).glob("p*.json")
                          if a.stem[1:].isdigit())
        # A página da sequência que o `livro.json` não cita (uma queda entre a página e o
        # livro) entra nele agora: o resumo, a gaveta e a fila do livro a mostram.
        livro = self._p.resumo.carregar()
        for pid in em_disco:
            if pid in conhecidos and str(pid) not in livro["paginas"]:
                try:
                    pagina = pagina_de_json(json.loads(
                        self._p._arquivo_v2(pid).read_text(encoding="utf-8")))
                except (OSError, ValueError, TypeError, KeyError):
                    continue
                livro = self._p.resumo.citar(pid, self._p.resumo.do_modelo(pagina), gravar)
        todas = list(sequencia.entradas) + [a.entrada for a in sequencia.apagadas]
        # Página do PDF -> o pid que a tem (as do livro, na sequência ou apagadas).
        do_pdf = {e.pagina: e.pid for e in todas if e.fonte == sq.FONTE_DO_LIVRO}
        orfaos = []
        for pid in em_disco:
            if pid in conhecidos:
                continue
            try:
                pagina = pagina_de_json(json.loads(
                    self._p._arquivo_v2(pid).read_text(encoding="utf-8")))
            except (OSError, ValueError, TypeError, KeyError):
                continue
            dono = do_pdf.get(pagina.indice)
            if dono is not None and self._p._arquivo_v2(dono).is_file():
                # O perdedor de dois arquivos da mesma página (uma queda): o dono vale.
                log.warning("p%d.json repete a página %d do PDF, que é da p%d: fica fora do "
                            "livro", pid, pagina.indice + 1, dono)
                continue
            if pagina.indice < 0:
                # Uma inserida ou uma metade direita sem entrada: não se sabe a imagem dela, e
                # apontá-la para uma página do PDF mostraria os glifos noutra imagem.
                log.warning("p%d.json não é de uma página do PDF e saiu da sequência: fica "
                            "fora do livro, no disco", pid)
                continue
            orfaos.append(sq.Apagada(sq.Entrada(pid, sq.FONTE_DO_LIVRO, max(0, pagina.indice)),
                                     len(sequencia)))
        proximo = max([self._p.dados.proximo_pid, *(p + 1 for p in em_disco),
                       *(p + 1 for p in sequencia.todos_os_pids)])
        # As páginas do PDF que não estão em entrada nenhuma (uma sequência gravada curta, de
        # antes de a fonte voltar): no fim do livro, com pid novo.
        faltam = [k for k in range(self._p.origem.total_de_paginas()) if k not in do_pdf]
        novas = tuple(sq.Entrada(proximo + n, sq.FONTE_DO_LIVRO, k) for n, k in enumerate(faltam))
        proximo += len(novas)
        if orfaos or novas:
            if orfaos:
                log.warning("%d página(s) fora da sequência foram para as apagadas", len(orfaos))
            if novas:
                log.warning("%d página(s) do PDF fora da sequência entraram no fim do livro",
                            len(novas))
            sequencia = sq.Sequencia(sequencia.entradas + novas,
                                     sequencia.apagadas + tuple(orfaos))
            if gravar and not self._p.somente_leitura:
                self._p.dados.sequencia = sequencia.para_json()
                self._p.dados.proximo_pid = max(self._p.dados.proximo_pid, proximo)
                self._p.salvar()
        return sequencia, proximo

    def da_v2(self, gravar: bool = True) -> Tuple[sq.Sequencia, int]:
        """A sequência de um projeto da v2 (`sequencia.da_v2`): a ordem do PDF, os `pid`
        das páginas gravadas pelo `livro.json`, e os `p<pid>.json` que ele não cita (uma
        queda entre a página e o livro: o mais recente de cada índice entra, e o livro é
        atualizado), a v1 não migrada com `pid` = índice. Um arquivo v1 presente vence a
        página v2 do mesmo índice (o `backup-v1/` copiado de volta, CA-4.5): os `gid` e as
        amostras dele usam o `pid` = índice. Todo `p<pid>.json` em disco fica abaixo do
        próximo `pid`, mesmo o que não entra na sequência."""
        livro = self._p.resumo.carregar()
        gravados: Dict[int, int] = {}
        for chave, resumo in livro["paginas"].items():
            indice = resumo.get("pagina_da_fonte")
            if isinstance(indice, int) and indice >= 0:     # a inserida e a direita, não
                gravados[indice] = int(chave)
        orfaos = self._orfaos(livro, gravados)
        for indice, (pid, pagina) in orfaos.items():
            gravados[indice] = pid
        for indice in self._p._v1_so_leitura:      # aberto para gravar, a v1 já migrou
            gravados[indice] = indice
        em_disco = [int(a.stem[1:]) for a in (self._p.pasta / PASTA_DE_PAGINAS).glob("p*.json")
                    if a.stem[1:].isdigit()]
        piso = max([self._p.dados.proximo_pid, *(p + 1 for p in em_disco)])
        total = max([self._p.origem.total_de_paginas(), *(i + 1 for i in gravados)], default=0)
        sequencia, proximo = sq.da_v2(total, gravados, piso)
        for indice, (pid, pagina) in orfaos.items():
            self._p.resumo.citar(pid, self._p.resumo.do_modelo(pagina), gravar)
        return sequencia, proximo

    def _orfaos(self, livro: dict, gravados: Dict[int, int]) -> Dict[int, Tuple[int, Pagina]]:
        """índice -> (pid, página) dos `p<pid>.json` que o livro não cita, para os índices
        que ele não tem (ou cujo arquivo sumiu): o mais recente pelo `gravado_em` e, no
        empate, o `pid` maior."""
        citados = {int(k) for k in livro["paginas"]}
        achados: Dict[int, list] = {}
        for arquivo in (self._p.pasta / PASTA_DE_PAGINAS).glob("p*.json"):
            if not arquivo.stem[1:].isdigit() or int(arquivo.stem[1:]) in citados:
                continue
            try:
                bruto = json.loads(arquivo.read_text(encoding="utf-8"))
                pagina = pagina_de_json(bruto)
            except (OSError, ValueError, TypeError, KeyError):
                continue
            indice = pagina.indice
            if indice < 0:
                continue                    # não é uma página do PDF (a v2 não a conhece)
            if indice in gravados and self._p._arquivo_v2(gravados[indice]).is_file():
                continue                    # o livro já tem esta página, e o arquivo dela
            achados.setdefault(indice, []).append(
                (bruto.get("gravado_em", ""), pagina.pid, pagina))
        orfaos = {}
        for indice, lista in achados.items():
            _, pid, pagina = max(lista, key=lambda t: (t[0], t[1]))
            if len(lista) > 1:
                log.warning("a página %d tem %d arquivos sem o livro; vale o mais recente, p%d",
                            indice + 1, len(lista), pid)
            orfaos[indice] = (pid, pagina)
        return orfaos

    # ------------------------------------------------------------------
    # Posição e `pid`
    # ------------------------------------------------------------------
    def pid_em(self, indice: int, criar: bool = False) -> Optional[int]:
        """O `pid` da página na posição `indice` (o da sequência, sem ler o JSON dela), ou
        None fora do livro. Só `criar` (a página que nasce numa gravação: a fonte sumida não
        diz quantas páginas tem) estende a sequência com `pid` novos; uma pergunta não deixa
        entradas fantasmas."""
        sequencia = self.sequencia
        if 0 <= indice < len(sequencia):
            return sequencia.pid_em(indice)
        if indice < 0:
            raise IndexError(f"Página {indice + 1} fora do livro")
        if not criar:
            return None
        with self._p._trava_do_livro:
            sequencia = self._sequencia
            if indice >= len(sequencia):
                faltam = indice + 1 - len(sequencia)
                pids = list(range(self._proximo_pid, self._proximo_pid + faltam))
                self._proximo_pid += faltam
                novas = tuple(sq.Entrada(p, sq.FONTE_DO_LIVRO, len(sequencia) + k)
                              for k, p in enumerate(pids))
                self._sequencia = sequencia = sq.Sequencia(sequencia.entradas + novas,
                                                           sequencia.apagadas)
                if self.gravada and not self._p.somente_leitura:
                    self._p.dados.sequencia = sequencia.para_json()     # antes da página
                    self._p.dados.proximo_pid = max(self._p.dados.proximo_pid,
                                                    self._proximo_pid)
                    self._p.salvar()
            return sequencia.pid_em(indice)

    def posicao_de(self, pid: int) -> Optional[int]:
        """A posição no livro da página `pid`, ou None (fora da sequência)."""
        return self.sequencia.posicao_de(pid)

    def pagina_da_fonte(self, pagina: Pagina) -> int:
        """O índice da página no PDF do livro (na v2, o que dá a ordem do livro, §12.4): o da
        entrada dela na sequência, e não a posição (`pagina.indice`), que muda ao reordenar.
        A página que não é uma do PDF (a inserida) e a metade direita de uma divisão (a
        esquerda fica com o índice) gravam `FORA_DO_PDF`: o `backup-v2/` copiado de volta não
        as toma pela página do livro de mesmo número. Antes de a sequência existir (montando-a,
        ou refazendo o livro), a página veio do JSON, e o `indice` dela é o gravado."""
        sequencia = self._sequencia         # sem montar: quem monta chama daqui
        if sequencia is None:
            return pagina.indice
        entrada = sequencia.entrada_de(pagina.pid)
        if entrada is None:
            apagada = sequencia.apagada(pagina.pid)
            entrada = None if apagada is None else apagada.entrada
        if entrada is None:
            return pagina.indice
        if entrada.fonte == sq.FONTE_DO_LIVRO and entrada.metade != "direita":
            return entrada.pagina
        return FORA_DO_PDF

    # ------------------------------------------------------------------
    # As páginas nas listas gravadas (posição na interface, `pid` no disco)
    # ------------------------------------------------------------------
    @property
    def gravada(self) -> bool:
        """O projeto tem a sequência no disco (v3): as listas de páginas gravadas são de
        `pid`. Num projeto da v2 aberto só para leitura, de posições."""
        return self._p.dados.sequencia is not None

    def paginas_para_gravar(self, posicoes: Iterable[int]) -> List[int]:
        """As posições como o projeto as grava: os `pid` (v3), ou as próprias posições."""
        posicoes = [int(p) for p in posicoes]
        if not self.gravada:
            return posicoes
        return [p for p in map(self.pid_em, posicoes) if p is not None]

    def posicoes_das_gravadas(self, gravadas: Iterable) -> List[int]:
        """As posições de agora das páginas de uma lista gravada (`paginas_para_gravar`): a
        página que saiu do livro, ou o valor ilegível, sai."""
        saida = []
        for valor in gravadas or ():
            valor = inteiro(valor)
            if valor is None:
                continue
            posicao = self.posicao_de(valor) if self.gravada else valor
            if posicao is not None and 0 <= posicao < len(self.sequencia):
                saida.append(posicao)
        return saida

    # ------------------------------------------------------------------
    # Os `pid` novos (§4.1: estáveis, nunca reaproveitados)
    # ------------------------------------------------------------------
    def novo_pid(self) -> int:
        """Um `pid` que nenhuma página teve (a metade direita de uma divisão). Gravado com a
        sequência que o usa; perdido (nunca reaproveitado) se a operação não acontece."""
        with self._p._trava_do_livro:
            pid = self._proximo_pid
            self._proximo_pid += 1
            return pid

    def inserir_arquivo(self, caminho: str | Path) -> List[sq.Entrada]:
        """Copia o PDF ou a imagem para `inseridas/` (o nome pelo SHA-256: o mesmo arquivo
        inserido duas vezes é uma cópia só) e devolve uma entrada com `pid` novo para cada
        página dele, para `Sequencia.inserir`. O PDF cifrado ou que não abre levanta
        `ProjetoInvalido`, e nada é copiado. A imagem é uma página (de um TIFF de várias, a
        primeira)."""
        from abbychess.projeto import EXTENSOES_DE_IMAGEM, ProjetoInvalido

        caminho = Path(caminho)
        sufixo = caminho.suffix.lower()
        if sufixo != ".pdf" and sufixo not in EXTENSOES_DE_IMAGEM:
            raise ProjetoInvalido(f"Formato não suportado: {sufixo}. Use PDF ou imagem.")
        try:
            dados = caminho.read_bytes()
        except OSError as erro:
            raise ProjetoInvalido(f"{caminho.name} não abriu: {erro}") from erro
        paginas = 1
        if sufixo == ".pdf":
            import fitz

            try:
                with fitz.open(stream=dados, filetype="pdf") as documento:
                    cifrado = documento.needs_pass or documento.is_encrypted
                    paginas = documento.page_count
            except (RuntimeError, ValueError) as erro:
                raise ProjetoInvalido(f"{caminho.name} não é um PDF legível: {erro}") from erro
            if cifrado:
                raise ProjetoInvalido(f"{caminho.name} é um PDF cifrado: tire a senha antes de "
                                      "inserir.")
            if paginas == 0:
                raise ProjetoInvalido(f"{caminho.name} não tem páginas.")
        nome = f"{sq.PASTA_DAS_INSERIDAS}/{hashlib.sha256(dados).hexdigest()}{sufixo}"
        destino = self._p.pasta / nome
        if not destino.is_file():
            gv.gravar_bytes(destino, dados)
        with self._p._trava_do_livro:
            pids = list(range(self._proximo_pid, self._proximo_pid + paginas))
            self._proximo_pid += paginas
        return [sq.Entrada(pid, nome, k) for k, pid in enumerate(pids)]

    # ------------------------------------------------------------------
    # Trocar a sequência (as operações de página, §12.4)
    # ------------------------------------------------------------------
    def gravar(self, nova: sq.Sequencia) -> None:
        """A sequência nova (uma operação de página, §12.4): o `projeto.json` primeiro, e só
        depois a memória; uma falha de gravação (`OSError`) não muda nada. Recusa o projeto
        só para leitura e o da v2 (sem a sequência gravada: a fonte sumida)."""
        if self._p.somente_leitura:
            raise OSError("o projeto está aberto só para leitura")
        if not self.gravada:
            raise OSError("o projeto ainda está no formato antigo: abra-o com a fonte do livro "
                          "no lugar para passar ao novo")
        with self._p._trava_do_livro:
            antes = (self._p.dados.sequencia, self._p.dados.proximo_pid)
            velha = self.sequencia
            self._p.dados.sequencia = nova.para_json()
            self._p.dados.proximo_pid = max([self._p.dados.proximo_pid, self._proximo_pid,
                                             *(p + 1 for p in nova.todos_os_pids)])
            try:
                self._p.salvar()
            except BaseException:
                self._p.dados.sequencia, self._p.dados.proximo_pid = antes
                raise
            self.trocar(nova)
            self._regravar_as_reenquadradas(velha, nova)

    def _regravar_as_reenquadradas(self, velha: sq.Sequencia, nova: sq.Sequencia) -> None:
        """As páginas gravadas cujo quadro mudou (cortar, tirar o corte e o desfazer deles) vão
        ao gravador já levadas à geometria nova: o arquivo, o `livro.json` (as contagens sem
        os glifos guardados fora do quadro) e a busca (que lê a da memória) seguem a imagem.
        Girar não tira glifo nenhum: as contagens e o texto ficam, e a página é levada ao giro
        quando é lida (o livro inteiro girado não relê as 230 páginas). A sequência já está
        gravada antes: uma queda antes delas é a leitura preguiçosa que resolve
        (`_na_geometria_da_entrada`)."""
        memoria = self._p.paginas_em_memoria
        for posicao, entrada in enumerate(nova.entradas):
            antes = velha.entrada_de(entrada.pid)
            if antes is None or antes.quadro == entrada.quadro:
                continue
            if memoria.pagina(posicao) is None and self._p._arquivo_v2_de(posicao) is None:
                continue                            # nada gravado: nada a levar
            try:
                pagina = self._p.carregar_modelo(posicao)
            except (OSError, ValueError, KeyError, TypeError) as erro:
                log.warning("a página %d não foi levada à geometria nova: %s", posicao + 1,
                            erro)
                continue
            if pagina is not None:
                memoria.agendar(pagina)

    def trocar(self, nova: sq.Sequencia) -> None:
        """A sequência nova (as operações de página, rodada 2): as páginas da memória passam a
        ter a posição dela no `indice`. Não grava nada."""
        with self._p._trava_do_livro:
            self._sequencia = nova
            self._proximo_pid = max([self._proximo_pid, *(p + 1 for p in nova.todos_os_pids)])
            self._p.paginas_em_memoria.reposicionar(nova, self._p._na_geometria_da_entrada)

    def trocar_paginas(self, nova: sq.Sequencia, paginas: Dict[int, Optional[Pagina]],
                       gids_movidos: Dict[str, int]) -> None:
        """A sequência nova com páginas trocadas inteiras (dividir e o desfazer dela, §12.4):
        `paginas` é pid -> a página nova (None: o arquivo sai). A ordem das gravações: os
        arquivos das páginas que entram na sequência, o `projeto.json` (a sequência, o
        contador de `pid` e os `gids_movidos`), as outras páginas, e por último os arquivos que
        saem. `OSError` até o `projeto.json`: nada mudou (os arquivos que entraram saem).
        Depois dele a operação vale: a página que não grava fica com o gravador, que tenta de
        novo e avisa, e o arquivo que não sai é avisado no log. Uma queda depois do
        `projeto.json` e antes das páginas deixa a página de antes no disco, que a leitura leva
        à geometria nova: nada se perde (o que passou à página nova fica também guardado fora
        do quadro da outra)."""
        p, memoria = self._p, self._p.paginas_em_memoria
        if p.somente_leitura:
            raise OSError("o projeto está aberto só para leitura")
        if not self.gravada:
            raise OSError("o projeto ainda está no formato antigo")
        pendentes = set(paginas) & memoria.sujas
        if pendentes:
            raise OSError("há página com gravação pendente: tente de novo")
        with p._trava_do_livro:
            atual = self.sequencia
            entram = {pid for pid, pagina in paginas.items() if pagina is not None
                      and atual.entrada_de(pid) is None and atual.apagada(pid) is None}
            for pid, pagina in paginas.items():
                if pagina is not None and nova.posicao_de(pid) is not None:
                    pagina.indice = nova.posicao_de(pid)
            antes = (p.dados.sequencia, p.dados.proximo_pid, p.dados.gids_movidos)
            gravados = []
            try:
                for pid in entram:
                    entrada = nova.entrada_de(pid)
                    do_pdf = (entrada is not None and entrada.fonte == sq.FONTE_DO_LIVRO
                              and entrada.metade != "direita")
                    gv.gravar_json(p._arquivo_v2(pid), pagina_para_json(
                        paginas[pid], entrada.pagina if do_pdf else FORA_DO_PDF))
                    gravados.append(pid)
                p.dados.sequencia = nova.para_json()
                p.dados.proximo_pid = max([p.dados.proximo_pid, self._proximo_pid,
                                           *(pid + 1 for pid in nova.todos_os_pids)])
                p.dados.gids_movidos = dict(gids_movidos)
                p.salvar()
            except BaseException:
                p.dados.sequencia, p.dados.proximo_pid, p.dados.gids_movidos = antes
                for pid in gravados:
                    try:
                        p._arquivo_v2(pid).unlink(missing_ok=True)
                    except OSError:
                        log.warning("p%d.json ficou (vai para as apagadas)", pid,
                                    exc_info=True)
                raise
            memoria.tirar(paginas)              # a velha não é levada à geometria nova
            self.trocar(nova)
            resumos: Dict[int, Optional[dict]] = {}
            for pid, pagina in paginas.items():
                if pagina is None:
                    continue
                try:
                    p._gravar(pagina, livro=False)
                except OSError:
                    log.warning("a página p%d fica com o gravador", pid, exc_info=True)
                    memoria.agendar(pagina)
                else:
                    resumos[pid] = p.resumo.do_modelo(pagina)
                    p._trocadas[pid] = (p._carimbo_do_pid(pid), pagina.proximo_n)
                    memoria.guardar(pagina, foto_nova=True)
            for pid, pagina in paginas.items():
                if pagina is None:
                    try:
                        p._arquivo_v2(pid).unlink(missing_ok=True)
                        resumos[pid] = None
                    except OSError:
                        log.warning("p%d.json não saiu (vai para as apagadas)", pid,
                                    exc_info=True)
            try:
                p.resumo.atualizar_varias(resumos)
            except OSError:
                # As páginas estão gravadas; o livro.json se refaz delas ao abrir.
                log.warning("o livro.json não foi atualizado", exc_info=True)

    # ------------------------------------------------------------------
    # As amostras antigas
    # ------------------------------------------------------------------
    def origem_da_amostra(self, origem: str) -> Optional[Tuple[Optional[int], Optional[int]]]:
        """(posição de agora, gid) do glifo de onde a amostra veio, pelo nome de origem dela
        (`leitor.nome_de_origem`); None se o nome não diz. A posição vem do `gid` (`pid =
        gid >> 20`, §12.4), e não do número da página no nome, que é o de quando ela foi
        ensinada; None na posição: a página saiu do livro. A amostra antiga, sem o `gid` no
        nome, vai à primeira entrada da página do PDF do nome (a metade esquerda, se ela foi
        dividida)."""
        from abbychess.leitor import origem_de
        from abbychess.modelo import pid_de

        lido = origem_de(origem)
        if lido is None:
            return None
        pagina_do_nome, gid = lido
        sequencia = self.sequencia
        if gid is not None:
            gid = self._p.gid_de_agora(gid)
            return sequencia.posicao_de(pid_de(gid)), gid
        guardado = self._posicoes_do_pdf
        if guardado is None or guardado[0] is not sequencia:   # uma vez por sequência
            posicoes: Dict[int, int] = {}
            for direita in (False, True):       # a metade esquerda, onde quer que esteja
                for posicao, entrada in enumerate(sequencia.entradas):
                    if entrada.fonte == sq.FONTE_DO_LIVRO and \
                            (entrada.metade == "direita") == direita:
                        posicoes.setdefault(entrada.pagina, posicao)
            guardado = self._posicoes_do_pdf = (sequencia, posicoes)
        return guardado[1].get(pagina_do_nome), None
