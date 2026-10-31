"""A migração dos formatos antigos do projeto, na abertura (§4.3, §12.4, CA-12.7), à parte do
`ProjetoDeLivro` (SPEC-qualidade Q-A1). Da v1 (`paginas/0001.json`, `zonas/0001.json`,
`marcadas.json`) à 2: `preparar_migracao` guarda o `backup-v1/` e acerta o contador de pids, e
`migrar_a_v1` grava cada página v1 da pasta como `p<pid>.json` e tira os arquivos v1, a v1
inteira na abertura, antes de qualquer leitura (decisão §13.1; SPEC-qualidade Q-P1, Q-P2; o
`backup-v1/` copiado de volta vence, CA-4.5). Só para leitura nada migra:
`guardar_a_v1_na_memoria` deixa as páginas v1 no projeto, como o JSON v2 que a migração
gravaria. Da 2 à 3: `migrar_para_v3` guarda o `backup-v2/`, grava a sequência e passa as listas
de páginas a `pid`, e `completar_v3` passa as inclinações, `janela.json` e `lote.json`, também
o que uma queda no meio deixou na forma da v2. Abrir, e decidir o que migra, é do projeto
(`abrir`, `_abrir_para_gravar`, `_abrir_so_para_leitura`, `self._p`), e a sequência montada
dos dados da v2 também (`_sequencia_da_v2`): o projeto da v2 aberto só para leitura a usa sem
migrar."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from core.box_model import BoxEntry

from abbychess import gravacao as gv
from abbychess import sequencia as sq
from abbychess import zonas as zn
from abbychess.modelo import GLIFOS_MARCADOS, RECONHECIDA, Box, Pagina, gid_de
from abbychess.pagina_em_json import com_ids_de_diagramas, inteiro, pagina_para_json
from abbychess.pasta_do_projeto import (ARQUIVO_DA_JANELA, ARQUIVO_DAS_MARCADAS, ARQUIVO_DE_INCLINACOES,
                                        ARQUIVO_DO_LIVRO, ARQUIVO_DO_LOTE, ARQUIVO_DO_PROJETO,
                                        LISTAS_DE_PAGINAS, MAPAS_DE_PAGINAS, PASTA_DE_PAGINAS,
                                        PASTA_DE_ZONAS, PASTA_DO_BACKUP_V1, PASTA_DO_BACKUP_V2,
                                        VERSAO)
from abbychess.zonas import Zona

log = logging.getLogger(__name__)


class Migracoes:
    def __init__(self, p) -> None:
        self._p = p

    def _arquivo_v1(self, indice: int) -> Path:
        return self._p.pasta / PASTA_DE_PAGINAS / f"{indice + 1:04d}.json"

    def indices_v1(self) -> List[int]:
        indices = set()
        for pasta in (self._p.pasta / PASTA_DE_PAGINAS, self._p.pasta / PASTA_DE_ZONAS):
            if pasta.is_dir():
                indices |= {int(p.stem) - 1 for p in pasta.glob("*.json") if p.stem.isdigit()}
        return sorted(indices)

    def _marcadas_v1(self) -> set:
        arquivo = self._p.pasta / PASTA_DE_PAGINAS / ARQUIVO_DAS_MARCADAS
        if not arquivo.is_file():
            return set()
        try:
            return {int(i) - 1 for i in json.loads(arquivo.read_text(encoding="utf-8"))}
        except (ValueError, TypeError):
            return set()

    def _ler_v1(self, indice: int) -> Pagina:
        """A página v1 (página, áreas, marcadas) como modelo v2, sem gravar: pid = índice."""
        from abbychess.diagramas import DiagramaLido

        pagina = Pagina(pid=indice, indice=indice)
        arquivo = self._arquivo_v1(indice)
        if arquivo.is_file():
            bruto = json.loads(arquivo.read_text(encoding="utf-8"))
            pagina.boxes = [Box(gid_de(indice, n), BoxEntry.from_state(tuple(estado)))
                            for n, estado in enumerate(bruto.get("boxes", []))]
            pagina.proximo_n = len(pagina.boxes)
            pagina.tabuleiros = [tuple(int(v) for v in t) for t in bruto.get("tabuleiros", [])]
            pagina.diagramas = com_ids_de_diagramas(
                [DiagramaLido.de_json(d) for d in bruto.get("diagramas", [])])
            pagina.estado = GLIFOS_MARCADOS if indice in self._marcadas_v1() else RECONHECIDA
        zonas = self._p.pasta / PASTA_DE_ZONAS / f"{indice + 1:04d}.json"
        if zonas.is_file():
            bruto = json.loads(zonas.read_text(encoding="utf-8"))
            pagina.zonas = zn.com_ids([Zona.de_dict(z) for z in bruto.get("zonas", [])])
        return pagina

    def _pids_v1(self, v1_vence: bool) -> List[int]:
        """As páginas v1 da pasta que valem como página: todas quando o `projeto.json` é o
        da v1 (a primeira abertura, ou o `backup-v1/` copiado de volta, que vence o v2 de
        mesmo pid: CA-4.5); senão, só as que não têm o `p<pid>.json`. O arquivo v1 de uma
        página que já o tem é a sobra de uma migração que gravou a página e não conseguiu
        apagá-lo: migrá-lo de novo passaria a página por cima (SPEC-qualidade Q-P2)."""
        return [pid for pid in self.indices_v1()
                if v1_vence or not self._p._arquivo_v2(pid).is_file()]

    def migrar_a_v1(self, v1_vence: bool) -> None:
        """Na abertura, antes de qualquer leitura (SPEC-qualidade Q-P1): grava como v2 cada
        página v1 da pasta (`_pids_v1`) e tira os arquivos v1 (a cópia está em
        `backup-v1/`). O número do arquivo v1 é a página do PDF, que é o `pid` dela, e não a
        posição no livro, que reordenar muda. Um arquivo que não sai fica como sobra: a página
        já está gravada, e a próxima abertura o apaga."""
        migrar = set(self._pids_v1(v1_vence))
        for pid in self.indices_v1():
            if pid in migrar:
                self._p._gravar(self._ler_v1(pid))
            for arquivo in (self._arquivo_v1(pid),
                            self._p.pasta / PASTA_DE_ZONAS / f"{pid + 1:04d}.json"):
                try:
                    gv.apagar(arquivo)
                except OSError as erro:
                    log.warning("o arquivo v1 %s ficou (%s); a próxima abertura o apaga",
                                arquivo, erro)

    def guardar_a_v1_na_memoria(self, v1_vence: bool) -> None:
        """Só para leitura (nada migra): cada página v1 da pasta (`_pids_v1`), lida uma vez,
        como o JSON v2 que a migração gravaria (`_gravada` a lê daqui); a ilegível fica de
        fora."""
        self._p._v1_so_leitura = {}
        for pid in self._pids_v1(v1_vence):
            try:
                self._p._v1_so_leitura[pid] = pagina_para_json(self._ler_v1(pid), pid)
            except (OSError, ValueError, TypeError, KeyError) as erro:
                log.warning("a página v1 %d está ilegível (%s): fica de fora", pid + 1, erro)
        self._p._livro = None                   # o resumo do livro é refeito com elas

    def preparar_migracao(self, bruto_do_projeto: bytes) -> None:
        """Na primeira abertura v2 de um projeto v1: `backup-v1/` com as páginas, as áreas e o
        `projeto.json` de antes, e o contador de pids depois de todo índice v1 e todo pid já
        gravado. As páginas migram logo depois (`migrar_a_v1`)."""
        backup = self._p.pasta / PASTA_DO_BACKUP_V1
        if not (backup / ARQUIVO_DO_PROJETO).is_file():
            for nome in (PASTA_DE_PAGINAS, PASTA_DE_ZONAS):
                origem = self._p.pasta / nome
                if origem.is_dir():
                    for arquivo in sorted(origem.glob("*.json")):
                        if arquivo.stem.isdigit() or arquivo.name == ARQUIVO_DAS_MARCADAS:
                            gv.gravar_bytes(backup / nome / arquivo.name, arquivo.read_bytes())
            gv.gravar_bytes(backup / ARQUIVO_DO_PROJETO, bruto_do_projeto)
        pids = [int(p.stem[1:]) for p in (self._p.pasta / PASTA_DE_PAGINAS).glob("p*.json")
                if p.stem[1:].isdigit()]
        self._p.dados.proximo_pid = max([self._p.dados.proximo_pid, *(i + 1 for i in self.indices_v1()),
                                         *(p + 1 for p in pids)])
        self._p.dados.versao = 2                    # a 3 vem logo depois (`migrar_para_v3`)
        self._p.salvar()
        gv.apagar(self._p.pasta / ARQUIVO_DO_LIVRO)     # o cache é refeito com os pids

    def migrar_para_v3(self) -> None:
        """Da v2 à v3 (§12.4, CA-12.7): `backup-v2/` com os arquivos que mudam, a sequência
        montada dos dados da v2 (toda página ganha `pid` gravado), as listas de páginas
        passadas a `pid`, e o `projeto.json` com a sequência e a `versao` 3 numa gravação só.
        Uma queda antes dela deixa o projeto na v2 (migra de novo na próxima abertura); depois
        dela, `inclinacoes.json`, `janela.json` e `lote.json` são passados a `pid`, e quem os lê
        aceita também a forma antiga (uma queda no meio não perde nada). Os JSON de página não
        mudam."""
        backup = self._p.pasta / PASTA_DO_BACKUP_V2
        if not (backup / ARQUIVO_DO_PROJETO).is_file():
            for nome in (ARQUIVO_DE_INCLINACOES, ARQUIVO_DA_JANELA, ARQUIVO_DO_LOTE,
                         ARQUIVO_DO_PROJETO):        # o projeto.json por último: ele marca o backup
                arquivo = self._p.pasta / nome
                if arquivo.is_file():
                    gv.gravar_bytes(backup / nome, arquivo.read_bytes())
        sequencia, proximo = self._p._sequencia_da_v2()
        self._listas_para_pids(sequencia)
        self._p.dados.sequencia = sequencia.para_json()
        self._p.dados.proximo_pid = max(self._p.dados.proximo_pid, proximo)
        self._p.dados.versao = VERSAO
        self._p.salvar()
        self._p._sequencia, self._p._proximo_pid = sequencia, max(self._p._proximo_pid, proximo)

    def completar_v3(self) -> None:
        """Os arquivos que a migração passa a `pid` depois do `projeto.json` (as inclinações,
        `janela.json`, `lote.json`): a cada abertura da v3, só o que ainda está na forma da v2
        (uma queda no meio da migração). Uma falha de gravação só avisa no log: quem os lê
        aceita a forma da v2."""
        if self._p.somente_leitura:
            return
        try:
            self._inclinacoes_para_pids(self._p.sequencia)
            self._janela_e_lote_para_pids(self._p.sequencia)
        except OSError as erro:
            log.warning("os arquivos de %s não passaram todos a pid (%s); a próxima abertura "
                        "tenta de novo", self._p.pasta, erro)

    def _listas_para_pids(self, sequencia: sq.Sequencia) -> None:
        """As listas de posições do `projeto.json` (a v2 escreve o índice do PDF, que na
        migração é a posição) passam a `pid`; a posição fora do livro sai."""
        extras = self._p.dados.extras

        def pid(valor) -> Optional[int]:
            posicao = inteiro(valor)
            if posicao is None:
                return None
            return sequencia.pid_em(posicao) if 0 <= posicao < len(sequencia) else None

        for chave in LISTAS_DE_PAGINAS:
            if isinstance(extras.get(chave), (list, tuple)):
                extras[chave] = [p for p in map(pid, extras[chave]) if p is not None]
        for chave in MAPAS_DE_PAGINAS:
            if isinstance(extras.get(chave), dict):
                extras[chave] = {str(p): n for k, n in extras[chave].items()
                                 if (p := pid(k)) is not None}

    def _inclinacoes_para_pids(self, sequencia: sq.Sequencia) -> None:
        """`inclinacoes.json` por `pid` (a chave da v3, `pagina._chave_da_inclinacao`)."""
        arquivo = self._p.pasta / ARQUIVO_DE_INCLINACOES
        if not arquivo.is_file():
            return
        try:
            bruto = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return                              # ilegível: a fonte o ignora e mede de novo
        if not any(chave.isdigit() for chave in bruto):
            return                              # já por pid
        do_pdf = {e.pagina: e.pid for e in sequencia.entradas if e.fonte == sq.FONTE_DO_LIVRO}
        novo = {}
        for chave, angulo in bruto.items():
            if chave.isdigit() and int(chave) in do_pdf:
                novo[f"p{do_pdf[int(chave)]}:inteira:0"] = angulo
            elif not chave.isdigit():
                novo[chave] = angulo
        gv.gravar_json(arquivo, dict(sorted(novo.items())))

    def _janela_e_lote_para_pids(self, sequencia: sq.Sequencia) -> None:
        """A página aberta em `janela.json` e as páginas de `lote.json` com o `pid` delas."""
        def pid(valor) -> Optional[int]:
            return (sequencia.pid_em(valor) if isinstance(valor, int)
                    and 0 <= valor < len(sequencia) else None)

        for nome in (ARQUIVO_DA_JANELA, ARQUIVO_DO_LOTE):
            arquivo = self._p.pasta / nome
            if not arquivo.is_file():
                continue
            try:
                bruto = json.loads(arquivo.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue                        # ilegível: quem o lê avisa, como antes
            if not isinstance(bruto, dict):
                continue
            if nome == ARQUIVO_DA_JANELA:
                if "pid" in bruto:
                    continue                    # já por pid
                bruto["pid"] = pid(bruto.get("pagina"))
            else:
                if bruto.get("pids"):
                    continue
                for chave in ("paginas", "reler_depois"):
                    bruto[chave] = [p for p in map(pid, bruto.get(chave) or []) if p is not None]
                bruto["pids"] = True
            gv.gravar_json(arquivo, bruto)
