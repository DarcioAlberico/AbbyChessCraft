"""O resumo de cada página no `livro.json` (§4.3, §4.4, CA-4.4), à parte do `ProjetoDeLivro`
(SPEC-qualidade Q-A1). Por `pid`: o estado, os pendentes, o histograma das confianças (com ele,
`reaplicar_limiar` dá os pendentes de outro limiar sem reler as páginas), os diagramas por
conferir, as figurinas e a régua do negrito da página (§9.2, `regua_do_negrito`). É um cache
derivado: `carregar` o lê, ou o refaz das páginas gravadas (`recalcular`) se ele falta ou está
ilegível, e ler não grava (SPEC-qualidade Q-P8). Os caminhos que gravam a página (`_gravar`, o
gravador, `trocar_paginas`, a volta de antes do lote) o mudam por `atualizar` e
`atualizar_varias`; `do_livro` o dá pela posição de agora na sequência, já com as páginas
entregues ao gravador e ainda não gravadas. A trava do livro, a sequência e o cache das páginas
são do projeto (`self._p`)."""

from __future__ import annotations

import json
import logging
import math
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Tuple

from core.box_model import BoxEntry

from abbychess import gravacao as gv
from abbychess.modelo import FIGURINAS, LIDAS, NAO_RECONHECIDA, Pagina
from abbychess.pagina_em_json import pagina_de_json
from abbychess.pasta_do_projeto import ARQUIVO_DO_LIVRO, PASTA_DE_PAGINAS

if TYPE_CHECKING:
    from abbychess.projeto import Limiares

log = logging.getLogger(__name__)

#: A versão do formato de `livro.json`; outra versão é refeita das páginas.
#: 2: a confiança 1,0 ganhou a faixa 100 do histograma; 3: o `pid` de cada página e os
#: estados de §4.4; 4: chaveado por `pid` (passo L), com o índice da página no PDF em cada
#: resumo (os caches anteriores são refeitos).
VERSAO_DO_LIVRO = 4


class ResumoDoLivro:
    def __init__(self, p) -> None:
        self._p = p
        #: O `livro.json` lido (ou refeito), trocado inteiro a cada gravação; None: a próxima
        #: leitura é a do disco (`carregar`).
        self._livro: Optional[dict] = None

    def paginas_lidas(self) -> List[int]:
        """As páginas reconhecidas (F5 ou lote), sem as que só têm glifos marcados."""
        return sorted(i for i, r in self.do_livro().items() if r["estado"] in LIDAS)

    def pagina_reconhecida(self, indice: int) -> bool:
        resumo = self.do_livro().get(indice)
        return resumo is not None and resumo["estado"] in LIDAS

    def estado_da_pagina(self, indice: int) -> str:
        resumo = self.do_livro().get(indice)
        return resumo["estado"] if resumo is not None else NAO_RECONHECIDA

    def do_livro(self) -> Dict[int, dict]:
        """Posição da página no livro -> o resumo dela (`do_modelo`), de toda página
        gravada que está na sequência."""
        sequencia = self._p.sequencia
        # Os pendentes antes do livro: uma página que o gravador termine entre as duas
        # leituras já está no livro lido, e não some por uma chamada.
        pendentes = self._p.paginas_em_memoria.resumos_pendentes()
        livro = self._livro                     # trocado inteiro a cada gravação
        if livro is None:
            with self._p._trava_do_livro:
                livro = self.carregar()
        por_pid = {int(k): v for k, v in livro["paginas"].items()}
        por_pid.update(pendentes)
        resumo = {}
        for pid, r in por_pid.items():
            posicao = sequencia.posicao_de(pid)
            if posicao is not None:
                resumo[posicao] = r
        # Cópia funda: o cache não vaza.
        return {i: json.loads(json.dumps(resumo[i])) for i in sorted(resumo)}

    def regua_do_negrito(self, sem_o_pid: Optional[int] = None) -> dict:
        """A régua do negrito do livro (`regua_do_negrito.juntar`): a das páginas gravadas
        que estão na sequência, sem a `sem_o_pid` (a que se vai ler, que traz a dela)."""
        from abbychess import regua_do_negrito as rn

        sequencia = self._p.sequencia
        pendentes = self._p.paginas_em_memoria.resumos_pendentes()
        livro = self._livro                     # trocado inteiro a cada gravação
        if livro is None:
            with self._p._trava_do_livro:
                livro = self.carregar()
        por_pid = {int(k): v for k, v in livro["paginas"].items()}
        por_pid.update(pendentes)
        return rn.juntar(r.get("regua_do_negrito") for pid, r in por_pid.items()
                         if pid != sem_o_pid and sequencia.posicao_de(pid) is not None)

    def reaplicar_limiar(self) -> None:
        """Os `pendentes` de `livro.json` com o limiar de revisão de agora, pelo histograma
        (exato para os limiares de duas casas da janela de opções)."""
        if self._p.somente_leitura:
            return
        with self._p._trava_do_livro:
            livro = self.carregar()
            revisao = self._p.dados.limiares.revisao
            novo = {"versao": livro["versao"],
                    "paginas": {k: {**v, "pendentes": pendentes_pelo_histograma(v, revisao)}
                                for k, v in livro["paginas"].items()}}
            gv.gravar_json(self._p.pasta / ARQUIVO_DO_LIVRO, novo)
            self._livro = novo                  # o cache só muda depois de gravado

    def recalcular(self) -> dict:
        """O `livro.json` como ele deve ser, lendo todas as páginas gravadas (as v2, e as v1
        da memória num projeto v1 aberto só para leitura)."""
        por_indice: Dict[int, Tuple[tuple, Pagina]] = {}
        for arquivo in sorted((self._p.pasta / PASTA_DE_PAGINAS).glob("p*.json")):
            if not arquivo.stem[1:].isdigit():
                continue
            try:
                bruto = json.loads(arquivo.read_text(encoding="utf-8"))
                pagina = pagina_de_json(bruto)
            except (OSError, ValueError, TypeError, KeyError):
                continue                # página ilegível: fica fora do resumo
            ordem = (bruto.get("gravado_em", ""), pagina.pid)
            if pagina.indice in por_indice:     # dois arquivos do mesmo índice: o mais recente
                log.warning("a página %d tem mais de um arquivo; vale o gravado por último",
                            pagina.indice + 1)
                if ordem < por_indice[pagina.indice][0]:
                    continue
            por_indice[pagina.indice] = (ordem, pagina)
        for indice, bruto in self._p._v1_so_leitura.items():
            por_indice[indice] = ((), pagina_de_json(bruto))
        paginas = {str(p.pid): self.do_modelo(p) for _, p in por_indice.values()}
        return {"versao": VERSAO_DO_LIVRO,
                "paginas": dict(sorted(paginas.items(), key=lambda kv: int(kv[0])))}

    def carregar(self, gravar: bool = False) -> dict:
        """O `livro.json`, ou o recalculado das páginas se ele falta ou está ilegível. Só
        `gravar` (a montagem da abertura, `ordem.montar`) grava o recalculado; ler não
        grava (SPEC-qualidade Q-P8), e a gravação seguinte do livro o leva ao disco."""
        if self._livro is None:
            arquivo = self._p.pasta / ARQUIVO_DO_LIVRO
            try:
                bruto = json.loads(arquivo.read_text(encoding="utf-8"))
                if bruto.get("versao") != VERSAO_DO_LIVRO or not isinstance(
                        bruto.get("paginas"), dict):
                    raise ValueError("versão ou forma inesperada")
            except (OSError, ValueError, AttributeError):
                bruto = self.recalcular()
                if gravar and not self._p.somente_leitura:
                    gv.gravar_json(arquivo, bruto)
            self._livro = bruto
        return self._livro

    def citar(self, pid: int, resumo: dict, gravar: bool) -> dict:
        """A página em disco que o `livro.json` não cita entra nele: gravada (`gravar`, a
        montagem da abertura) ou só na memória (a leitura, o projeto só para leitura), por
        troca e não no lugar. Devolve o livro de agora."""
        if gravar and not self._p.somente_leitura:
            self.atualizar(pid, resumo)
        else:
            livro = self.carregar()
            self._livro = {**livro, "paginas": {**livro["paginas"], str(pid): resumo}}
        return self.carregar()

    def tirar_da_memoria(self, pid: int) -> None:
        """A página sai só do resumo da memória (a ilegível no projeto só para leitura), por
        troca e não no lugar; o `livro.json` não muda."""
        livro = self.carregar()
        self._livro = {**livro, "paginas": {k: v for k, v in livro["paginas"].items()
                                            if k != str(pid)}}

    def esquecer(self) -> None:
        """O resumo da memória sai: a próxima leitura é a do disco (a montagem da abertura) ou a
        refeita das páginas (a v1 deixada na memória)."""
        self._livro = None

    def atualizar(self, pid: int, resumo: Optional[dict]) -> None:
        """O resumo da página no `livro.json` (None: ela sai dele)."""
        self.atualizar_varias({pid: resumo})

    def atualizar_varias(self, resumos: Dict[int, Optional[dict]]) -> None:
        """Os resumos de várias páginas no `livro.json`, numa gravação só (None: a página sai
        dele)."""
        if not resumos:
            return
        with self._p._trava_do_livro:
            livro = self.carregar()
            paginas = {**livro["paginas"], **{str(pid): r for pid, r in resumos.items()}}
            for pid, resumo in resumos.items():
                if resumo is None:
                    del paginas[str(pid)]
            novo = {"versao": livro["versao"],
                    "paginas": dict(sorted(paginas.items(), key=lambda kv: int(kv[0])))}
            gv.gravar_json(self._p.pasta / ARQUIVO_DO_LIVRO, novo)
            self._livro = novo                  # o cache só muda depois de gravado

    def do_modelo(self, pagina: Pagina) -> dict:
        """O resumo da página no `livro.json` (sem mudar nada: vale numa thread)."""
        tabuleiros = len(pagina.tabuleiros)
        # O que falhou na leitura não tem posição a conferir, e o contador chega a zero (U-5a).
        conferidos = sum(1 for d in pagina.diagramas if d.conferido or d.erro)
        # A régua do negrito dela, para a do livro (`regua_do_negrito`), quando foi medida.
        regua = {"regua_do_negrito": pagina.regua_do_negrito} if pagina.regua_do_negrito else {}
        return {"pid": pagina.pid, "pagina_da_fonte": self._p.ordem.pagina_da_fonte(pagina),
                "estado": pagina.estado,
                **resumo_das_confiancas(pagina.entries(), self._p.dados.limiares,
                                        [b.revisado for b in pagina.boxes]),
                "diagramas": tabuleiros,
                "diagramas_por_conferir": max(0, tabuleiros - conferidos),
                # Alguma figurina lida (o modo "livro" das peças, §6.4, sem abrir as páginas).
                "figurinas": any(b.entry.char in FIGURINAS for b in pagina.boxes),
                **self._dos_lances(pagina), **_da_imagem(pagina), **regua}

    def _dos_lances(self, pagina: Pagina) -> dict:
        """`lances_por_conferir` e `fortes`, as contagens da fila Lances (F-4) e da marca forte."""
        from abbychess import decodificador_de_lances as dl
        from abbychess import evidencia as ev
        from abbychess import texto as tx

        if not pagina.boxes:
            return {"lances_por_conferir": 0, "fortes": 0}
        chave = self._p.dados.chave_das_pecas
        documento = tx.montar(pagina, com_os_nao_lidos=True)
        return {"lances_por_conferir": dl.lances_por_conferir(documento, ev.conferidos(pagina), chave),
                "fortes": len(ev.da_pagina(pagina, documento, pagina.diagramas, chave).fortes)}


def _da_imagem(pagina: Pagina) -> dict:
    """`imagem`, só na página tratada como imagem (L-9): a gaveta filtra por ela."""
    from abbychess import tipo_de_pagina as tp

    return {"imagem": True} if tp.tratada_como_imagem(pagina) else {}


def resumo_das_confiancas(boxes: Sequence[BoxEntry], limiares: Limiares,
                          revisados: Optional[Sequence[bool]] = None) -> dict:
    """Os boxes da página em `confirmados`, `sem_leitura` e o histograma do resto.

    O histograma tem faixas de 0,01 (a chave é o centésimo de baixo; 100 é a confiança
    1,0) e conta só os boxes lidos e não confirmados, os únicos que um limiar de revisão
    diferente mudaria de lado: com ele, `pendentes_pelo_histograma` dá os pendentes de
    outro limiar (de duas casas) sem abrir a página. O glifo que a palavra desmente
    (`contexto`) é pendente com qualquer limiar: conta em `improvaveis`, fora do resto.
    """
    from abbychess import contexto
    from abbychess.leitor import FONTE_NENHUMA, FONTES_CONFIRMADAS, precisa_revisao

    confirmados = sem_leitura = pendentes = improvaveis = 0
    histograma: Dict[int, int] = {}
    revisados = revisados or [False] * len(boxes)
    for b, revisado, improvavel in zip(boxes, revisados, contexto.improvaveis_da_lista(boxes)):
        if improvavel and not revisado:
            improvaveis += 1
            pendentes += 1
            continue
        if not revisado and precisa_revisao(b.char, b.source, b.confidence, limiares):
            pendentes += 1
        if b.source in FONTES_CONFIRMADAS or revisado:      # o revisado é aceito (§6.3)
            confirmados += 1
        elif not b.char or b.source == FONTE_NENHUMA:
            sem_leitura += 1
        else:
            faixa = _faixa(b.confidence)
            histograma[faixa] = histograma.get(faixa, 0) + 1
    return {"boxes": len(boxes), "pendentes": pendentes, "confirmados": confirmados,
            "sem_leitura": sem_leitura, "improvaveis": improvaveis,
            "histograma": {str(k): histograma[k] for k in sorted(histograma)}}


def pendentes_pelo_histograma(resumo: dict, revisao: float) -> int:
    """Os pendentes da página com o limiar `revisao` (de duas casas, de 0,00 a 1,00), pelo
    histograma."""
    corte = math.floor(round(float(revisao) * 100, 6))
    return (resumo["sem_leitura"] + int(resumo.get("improvaveis", 0) or 0)
            + sum(n for k, n in resumo["histograma"].items() if int(k) < corte))


def _faixa(confianca: float) -> int:
    # Arredondar a 6 casas antes do piso põe 0,29 na faixa 29, e não na 28 que
    # `0.29 * 100 == 28.999…` daria. Confiança 1,0 tem a faixa 100 só dela, para o limiar
    # 1,00 (o máximo das opções) não a contar como pendente.
    return min(100, max(0, math.floor(round(float(confianca) * 100, 6))))
