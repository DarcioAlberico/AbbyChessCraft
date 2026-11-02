"""As páginas do livro na memória (§4.3), à parte do `ProjetoDeLivro` (SPEC-qualidade Q-A1). Não
é o cache das imagens renderizadas (`pagina.CacheDePaginas`): aqui ficam as páginas lidas, no
modelo, as `PAGINAS_EM_MEMORIA` mais recentes por `pid` (`guardar`, `pagina`, `do_pid`, `usar`),
com a foto (`modelo.foto`) de cada glifo na última gravação síncrona (`fotografar`, `foto_de`);
a página aberta na janela, que o cache não despeja (`prender`, SPEC-qualidade Q-P3); e as
entregues ao gravador e ainda não gravadas (`agendar`, `sujas`, `paginas_sujas`,
`resumos_pendentes`), que também não saem da memória. O gravador (`abbychess.gravador`) é daqui:
uma thread só, criada na primeira entrega, com coalescência de meio segundo (`descarregar`,
`fechar`). A interface não espera o disco por esta trava (`_trava_do_cache`): ela é curta, e
vem sempre depois da trava do livro, nunca antes. Ler e gravar o arquivo da página é do projeto
(`self._p`): `carregar_modelo`, `_gravar` e `_gravar_instantaneo`, o que o gravador chama, com
o escritor único de cada `p<pid>.json` (SPEC-qualidade Q-P4)."""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Callable, Dict, Iterable, List, Optional

from abbychess import zonas as zn
from abbychess.gravador import Gravador
from abbychess.modelo import Pagina, foto
from abbychess.pagina_em_json import com_ids_de_diagramas

#: Quantas páginas o projeto guarda em memória, no modelo (as outras relê do disco).
PAGINAS_EM_MEMORIA = 16


class CacheDoProjeto:
    def __init__(self, p) -> None:
        self._p = p
        #: O cache das páginas (`_modelos`, `_estados`, `_a_gravar`): curta, sem disco. A
        #: ordem é sempre a do livro e depois a do cache, nunca o contrário.
        self._trava_do_cache = threading.RLock()
        #: As páginas lidas, no modelo (as mais recentes), por `pid`, e a foto
        #: (`modelo.foto`) de cada glifo na última gravação síncrona: quem grava listas de
        #: `BoxEntry` (o lote, as ferramentas) pode tê-los mudado no lugar, e só a foto diz o
        #: que mudou.
        self._modelos: "OrderedDict[int, Pagina]" = OrderedDict()
        self._estados: Dict[int, Dict[int, int]] = {}
        #: O pid da página aberta na janela (`prender`), que o cache não despeja.
        self._presa: Optional[int] = None
        #: O gravador das páginas que a janela edita, criado na primeira entrega.
        self._gravador: Optional[Gravador] = None
        #: pid -> (instantâneo, resumo) das páginas entregues e ainda não gravadas: o
        #: resumo do livro as mostra como estão, e não como o disco ainda está.
        self._a_gravar: Dict[int, tuple] = {}

    # ------------------------------------------------------------------
    # O gravador (§4.3): a janela entrega, a thread dele grava
    # ------------------------------------------------------------------
    @property
    def gravador(self) -> Gravador:
        if self._gravador is None:
            self._gravador = Gravador(self._p._gravar_instantaneo, ao_falhar=self._falhou)
        return self._gravador

    def agendar(self, pagina: Pagina, resumo: Optional[dict] = None) -> bool:
        """A página mudou: o gravador a grava em até meio segundo. Em só leitura, recusa
        (devolve falso e nada é gravado). `resumo`: o de `resumo.do_modelo`, se quem chama
        já o calculou fora da interface (substituir no livro inteiro)."""
        if self._p.somente_leitura:
            return False
        with self._trava_do_cache:              # sem a trava do livro: não espera o disco
            # Os ids das áreas e dos diagramas nascem aqui, na página viva, e não só no
            # instantâneo: o que for gravado é o que a página tem.
            pagina.diagramas = com_ids_de_diagramas(pagina.diagramas)
            pagina.zonas = zn.com_ids(pagina.zonas)
            self.guardar(pagina, foto=False)
            instantaneo = pagina.instantaneo()
            # O resumo vale já para quem pergunta (F6, o lote, "lidas"), antes da gravação.
            self._a_gravar[pagina.pid] = (instantaneo, resumo if resumo is not None
                                          else self._p.resumo.do_modelo(instantaneo))
            self.gravador.agendar(pagina.pid, (next(self._p._bilhetes), instantaneo))
        return True

    def descarregar(self, limite: Optional[float] = None) -> bool:
        """Grava agora o que o gravador tem pendente e espera (antes do lote, que grava na
        thread dele, por exemplo). Não chame segurando a trava do livro."""
        return self._gravador.descarregar(limite) if self._gravador is not None else True

    def fechar(self, limite: Optional[float]) -> bool:
        """Espera o gravador gravar o que está pendente e o solta. Devolve se ficou tudo
        gravado; as posições que não gravaram vão a `nao_gravadas` do projeto."""
        if self._gravador is None:
            return True
        gravou = self._gravador.fechar(limite)
        self._p.nao_gravadas = [] if gravou else self.paginas_sujas()
        self._gravador = None
        return gravou

    @property
    def sujas(self) -> set:
        """Os pids com mudança ainda não gravada."""
        return self._gravador.sujas if self._gravador is not None else set()

    def paginas_sujas(self) -> List[int]:
        """As posições das páginas entregues ao gravador e ainda não gravadas."""
        sequencia = self._p.sequencia
        with self._trava_do_cache:
            pids = list(self._a_gravar)
        return sorted(p for p in map(sequencia.posicao_de, pids) if p is not None)

    def resumos_pendentes(self) -> Dict[int, dict]:
        """pid -> o resumo de cada página entregue e ainda não gravada (`agendar`)."""
        with self._trava_do_cache:
            return {pid: r for pid, (_, r) in self._a_gravar.items()}

    def gravada(self, pagina: Pagina) -> None:
        """O gravador gravou o instantâneo `pagina`: ela deixa de estar pendente, se nenhum
        outro mais novo da mesma página foi entregue depois."""
        with self._trava_do_cache:
            pendente = self._a_gravar.get(pagina.pid)
            if pendente is not None and pendente[0] is pagina:
                del self._a_gravar[pagina.pid]

    def _falhou(self, pid: int, erro: BaseException) -> None:
        if self._p.ao_falhar_gravacao is not None:
            self._p.ao_falhar_gravacao(self._p.sequencia.posicao_de(pid), erro)

    # ------------------------------------------------------------------
    # As páginas lidas (o modelo v2, §4.3)
    # ------------------------------------------------------------------
    def pagina(self, indice: int) -> Optional[Pagina]:
        """A página do cache, sem ler o disco (None se ela não está na memória)."""
        pid = self._p.ordem.pid_em(indice)
        if pid is None:
            return None
        with self._trava_do_cache:
            return self._modelos.get(pid)

    def do_pid(self, pid: int) -> Optional[Pagina]:
        """A página `pid` do cache, sem mudar a ordem dele (None se ela não está lá)."""
        with self._trava_do_cache:
            return self._modelos.get(pid)

    def usar(self, pid: int) -> Optional[Pagina]:
        """A página `pid` do cache, que passa a ser a mais recente dele (None se ela não está
        lá)."""
        with self._trava_do_cache:
            em_cache = self._modelos.get(pid)
            if em_cache is not None:
                self._modelos.move_to_end(pid)
            return em_cache

    def prender(self, pid: Optional[int]) -> None:
        """A página aberta na janela (None: nenhuma): o cache não a despeja, por mais páginas
        que um lote leia, e quem a pede de novo (o lote, a busca) recebe o mesmo objeto que a
        janela edita, e não outro lido do disco (SPEC-qualidade Q-P3)."""
        with self._trava_do_cache:
            self._presa = pid

    def guardar(self, pagina: Pagina, *, foto_nova: bool = False,
                foto: bool = True) -> None:
        """Põe a página no cache; `foto_nova` (a página veio do disco) refaz a foto dos
        estados, que de outro modo seria a de outra versão da mesma página. `foto=False` é a
        página que a interface entrega ao gravador: ela não muda nada no lugar, e a foto
        (um hash por glifo) não é calculada a cada edição."""
        with self._trava_do_cache:
            self._no_cache(pagina, foto_nova, foto)

    def _no_cache(self, pagina: Pagina, foto_nova: bool, com_foto: bool) -> None:
        self._modelos[pagina.pid] = pagina
        self._modelos.move_to_end(pagina.pid)
        if not com_foto:
            self._estados.pop(pagina.pid, None)
        elif foto_nova or pagina.pid not in self._estados:
            self._estados[pagina.pid] = {b.gid: foto(b.entry) for b in pagina.boxes}
        self._tirar_as_mais_velhas(pagina)

    def _tirar_as_mais_velhas(self, pagina: Pagina) -> None:
        """Até `PAGINAS_EM_MEMORIA`, saem as lidas há mais tempo: a com gravação pendente
        fica, e a aberta, e `pagina`, a que acabou de entrar."""
        sujas = self.sujas
        for pid in list(self._modelos):
            if len(self._modelos) <= PAGINAS_EM_MEMORIA:
                break
            saiu = self._modelos[pid]
            if pid in sujas or saiu is pagina or pid == self._presa:
                continue                    # a página com gravação pendente fica, e a aberta
            del self._modelos[pid]
            self._estados.pop(pid, None)

    def tirar(self, pids: Iterable[int]) -> None:
        """As páginas `pids` saem do cache, com a foto delas."""
        with self._trava_do_cache:
            for pid in pids:
                self._modelos.pop(pid, None)
                self._estados.pop(pid, None)

    def reposicionar(self, nova, levar: Callable[[Pagina], None]) -> None:
        """As páginas do cache passam a ter no `indice` a posição delas na sequência `nova`, e
        `levar` as leva à geometria da entrada. Não grava nada."""
        with self._trava_do_cache:
            for pid, pagina in self._modelos.items():
                posicao = nova.posicao_de(pid)
                if posicao is not None:
                    pagina.indice = posicao
                    levar(pagina)

    def foto_de(self, pid: int) -> Optional[Dict[int, int]]:
        """A foto da página `pid` na última gravação síncrona (None: sem foto)."""
        return self._estados.get(pid)

    def fotografar(self, pid: int, estados: Dict[int, int]) -> None:
        """A foto da gravação síncrona da página `pid`: gid -> `modelo.foto` do glifo."""
        with self._trava_do_cache:
            self._estados[pid] = estados

    def esquecer_a_foto(self, pid: int) -> None:
        """A página `pid` gravada pelo gravador, que veio da interface (que não muda nada no
        lugar): a reconciliação a compara com o glifo mesmo."""
        with self._trava_do_cache:
            self._estados.pop(pid, None)
