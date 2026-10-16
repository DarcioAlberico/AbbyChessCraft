"""CA-4.3 (parte do 1b): máquina de estados sobre os gids, as decisões e `montar()`.

Uma página sintética de 900×400 com 1 a 60 glifos (cada um, dois traços de tinta com um vão,
para o `dividir` ter onde cortar). As regras do 1b: dividir, juntar, marcar, quebrar,
juntar palavras e o glifo virtual, pelas edições por gid (`abbychess.edicao`) e também pelo
caminho da janela de hoje (a lista de `BoxEntry` editada por `abbychess.pagina` e
reconciliada, `modelo.reconciliar`). A cada passo, os invariantes de §4.5: gids únicos;
aposentados ∩ vivos = ∅; nenhuma decisão cita gid aposentado; `montar()` cobre cada glifo
lido e cada virtual uma vez. E dois do modelo: nenhuma edição perde uma decisão cujo glifo
ela não tocou, e uma quebra e uma junção nunca valem na mesma fronteira.

Suíte rápida: `derandomize=True`, `max_examples=200`. A camada noturna roda 5.000.
"""

from __future__ import annotations

import os

import pytest
from hypothesis import HealthCheck, Phase, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule
from PIL import Image, ImageDraw

from core.box_model import BoxEntry

from abbychess import edicao as ed
from abbychess import pagina as pg
from abbychess import texto as tx
from abbychess.modelo import Box, Pagina, foto, gid_de, reconciliar

LARGURA, ALTURA = 900, 400
EXEMPLOS = 5000 if os.environ.get("ABBY_NOTURNO") == "1" else 200


def _pagina_sintetica(n: int):
    """`n` glifos em linhas de 12, cada um com dois traços verticais separados por um vão."""
    imagem = Image.new("L", (LARGURA, ALTURA), 255)
    desenho = ImageDraw.Draw(imagem)
    boxes = []
    for k in range(n):
        linha, coluna = divmod(k, 12)
        x, y = 20 + coluna * 72, 20 + linha * 70
        desenho.rectangle((x, y, x + 8, y + 30), fill=0)
        desenho.rectangle((x + 20, y, x + 28, y + 30), fill=0)
        boxes.append(BoxEntry("a", x, y, x + 29, y + 31, 0.95, "net"))
    pagina = Pagina(pid=7, indice=3, boxes=[Box(gid_de(7, i), b) for i, b in enumerate(boxes)],
                    estado="reconhecida", proximo_n=n)
    return imagem, pagina


class MaquinaDaPagina(RuleBasedStateMachine):
    @initialize(n=st.integers(1, 60))
    def montar_pagina(self, n):
        self.imagem, self.pagina = _pagina_sintetica(n)
        self.alocados = set(self.pagina.vivos)

    def _escolher(self, data_i):
        vivos = [b.gid for b in self.pagina.boxes]
        return vivos[data_i % len(vivos)] if vivos else None

    def _registrar(self, dif, antes=None):
        novos = {b.gid for b in dif.novos}
        assert not novos & self.alocados, "gid reaproveitado"
        self.alocados |= novos
        if antes is not None:
            self._preservou(antes, dif.removidos)

    def _preservou(self, antes, removidos):
        """Toda decisão de antes cujo glifo a edição não tocou continua igual."""
        depois = self.pagina.decisoes
        assert {g for g in antes.quebras if g not in removidos} <= depois.quebras
        assert {g for g in antes.paragrafo_antes if g not in removidos} <= depois.paragrafo_antes
        assert {j for j in antes.juncoes if not (set(j) & removidos)} <= depois.juncoes
        intactos = {v.gid for v in antes.virtuais if v.depois_de not in removidos}
        assert intactos <= {v.gid for v in depois.virtuais}

    def _pela_janela(self, editar):
        """A edição como a janela de hoje a faz: na lista de `BoxEntry`, depois reconciliada."""
        antes = self.pagina.decisoes
        foto_de_antes = {b.gid: foto(b.entry) for b in self.pagina.boxes}
        entries = self.pagina.entries()
        try:
            editar(entries)
        except ValueError:
            return
        novos, dif = reconciliar(self.pagina.boxes, entries, self.pagina.alocar,
                                 estados=foto_de_antes)
        self.pagina.aplicar(dif, novos)
        self._registrar(dif, antes)

    @rule(i=st.integers(0, 10_000))
    def dividir(self, i):
        gid = self._escolher(i)
        if gid is None:
            return
        antes = self.pagina.decisoes
        try:
            dif = ed.dividir(self.pagina, self.imagem, gid)
        except ValueError:
            return                                    # sem tinta dos dois lados: não divide
        assert dif.sucessores[gid] == [b.gid for b in dif.novos] and len(dif.novos) == 2
        self._registrar(dif, antes)

    @rule(i=st.integers(0, 10_000))
    def juntar(self, i):
        if len(self.pagina.boxes) < 2:
            return
        k = i % (len(self.pagina.boxes) - 1)
        a, b = self.pagina.boxes[k].gid, self.pagina.boxes[k + 1].gid
        antes = self.pagina.decisoes
        dif = ed.juntar(self.pagina, self.imagem, a, b)
        assert dif.sucessores == {a: [dif.novos[0].gid], b: [dif.novos[0].gid]}
        self._registrar(dif, antes)

    @rule(i=st.integers(0, 10_000))
    def marcar(self, i):
        gid = self._escolher(i)
        if gid is None:
            return
        e = self.pagina.box(gid).entry
        antes = self.pagina.decisoes
        try:
            dif = ed.marcar(self.pagina, self.imagem, (e.x1 - 2, e.y1 - 2, e.x2 + 2, e.y2 + 2))
        except ValueError:
            return
        self._registrar(dif, antes)

    @rule(i=st.integers(0, 10_000))
    def quebrar(self, i):
        gid = self._escolher(i)
        if gid is not None:
            ed.quebrar(self.pagina, gid)

    @rule(i=st.integers(0, 10_000))
    def juntar_palavras(self, i):
        if len(self.pagina.boxes) < 2:
            return
        k = i % (len(self.pagina.boxes) - 1)
        ed.juntar_palavras(self.pagina, self.pagina.boxes[k].gid, self.pagina.boxes[k + 1].gid)

    @rule(i=st.integers(0, 10_000), nova=st.booleans())
    def virtual(self, i, nova):
        gid = self._escolher(i)
        _, novo = ed.virtual(self.pagina, "x", gid, palavra_nova=nova)
        assert novo not in self.alocados
        self.alocados.add(novo)

    @rule(i=st.integers(0, 10_000))
    def descartar(self, i):
        gid = self._escolher(i)
        if gid is not None and len(self.pagina.boxes) > 1:
            antes = self.pagina.decisoes
            dif = ed.descartar(self.pagina, gid)
            self._preservou(antes, dif.removidos)

    @rule(i=st.integers(0, 10_000))
    def dividir_pela_janela(self, i):
        if self.pagina.boxes:
            k = i % len(self.pagina.boxes)
            self._pela_janela(lambda entries: pg.dividir(self.imagem, entries, k))

    @rule(i=st.integers(0, 10_000))
    def juntar_pela_janela(self, i):
        if len(self.pagina.boxes) >= 2:
            k = i % (len(self.pagina.boxes) - 1)
            self._pela_janela(lambda entries: pg.juntar(self.imagem, entries, k, k + 1))

    @rule(i=st.integers(0, 10_000))
    def descartar_pela_janela(self, i):
        if len(self.pagina.boxes) >= 2:
            k = i % len(self.pagina.boxes)
            self._pela_janela(lambda entries: pg.descartar(entries, k))

    @rule(i=st.integers(0, 10_000))
    def corrigir_pela_janela(self, i):
        if self.pagina.boxes:
            k = i % len(self.pagina.boxes)
            self._pela_janela(lambda entries: pg.confirmar(entries, k, "z"))

    # ------------------------------------------------------------------
    @invariant()
    def gids_unicos(self):
        vivos = [b.gid for b in self.pagina.boxes]
        assert len(vivos) == len(set(vivos))

    @invariant()
    def aposentados_e_vivos_nao_se_cruzam(self):
        vivos = self.pagina.vivos
        assert not (self.pagina.aposentados & vivos)
        assert all(g >> 20 == self.pagina.pid for g in vivos)
        assert all((g & ((1 << 20) - 1)) < self.pagina.proximo_n for g in vivos)

    @invariant()
    def nenhuma_decisao_cita_gid_aposentado(self):
        assert self.pagina.decisoes.gids() <= self.pagina.vivos

    @invariant()
    def quebra_e_juncao_nunca_na_mesma_fronteira(self):
        d = self.pagina.decisoes
        assert not (d.quebras & {b for _, b in d.juncoes})

    @invariant()
    def montar_cobre_cada_glifo_uma_vez(self):
        doc = tx.montar(self.pagina)
        esperados = [b.gid for b in self.pagina.boxes if b.entry.char]
        esperados += [v.gid for v in self.pagina.decisoes.virtuais]
        assert sorted(doc.gids()) == sorted(esperados)


MaquinaDaPagina.TestCase.settings = settings(
    max_examples=EXEMPLOS, derandomize=True, stateful_step_count=25, deadline=None,
    # Sem a fase "explain": ela roda com rastreio linha a linha e leva minutos.
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target, Phase.shrink],
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
test_maquina_da_pagina = pytest.mark.timeout(600)(MaquinaDaPagina.TestCase)


# ----------------------------------------------------------------------
# CA-4.3 (parte do 2a): o controlador, com pular e selecionar
# ----------------------------------------------------------------------

class _ProjetoNaMemoria:
    """O que o controlador pede ao projeto, sem disco."""

    somente_leitura = False

    class dados:
        nome = "Maquina"

    def __init__(self, pagina):
        self.pagina = pagina
        self.agendadas = 0

    def carregar_modelo(self, indice):
        return self.pagina

    def pagina_para_editar(self, indice):
        return self.pagina

    def agendar(self, pagina):
        self.agendadas += 1
        return True


class _FonteNaMemoria:
    total = 1

    def __init__(self, imagem):
        self.imagem = imagem

    def pagina(self, indice):
        return self.imagem


class _LeitorSemPadroes:
    """A fila sai das confianças; ler não acha nada (como um livro sem padrões)."""

    def __init__(self):
        from abbychess.projeto import Limiares

        self.limiares = Limiares()

    def ler(self, *_a, **_k):
        from abbychess.leitor import Leitura

        return Leitura("", "nenhuma", 0.0)

    ler_pelo_livro = ler

    def ensinar(self, *_a, **_k):
        return None                              # não guarda padrão: a máquina olha a página

    def padroes_por_caractere(self):
        return {}


class MaquinaDoControlador(RuleBasedStateMachine):
    @initialize(n=st.integers(1, 40), baixas=st.lists(st.integers(0, 39), max_size=20))
    def montar(self, n, baixas):
        from dataclasses import replace as trocar

        from abbychess.controlador import ControladorDePagina

        self.imagem, pagina = _pagina_sintetica(n)
        # Algumas confianças baixas: elas fazem a fila.
        pagina.boxes = [trocar(b, entry=trocar(b.entry, confidence=0.2)) if i in baixas else b
                        for i, b in enumerate(pagina.boxes)]
        self.ctl = ControladorDePagina()
        self.ctl.ligar(_ProjetoNaMemoria(pagina), _FonteNaMemoria(self.imagem),
                       _LeitorSemPadroes())
        self.ctl.ir_para(0)

    def _gid(self, i):
        gids = self.ctl.gids
        return gids[i % len(gids)] if gids else None

    @rule(i=st.integers(0, 10_000))
    def mostrar(self, i):
        self.ctl.mostrar(self._gid(i))

    @rule(passo=st.sampled_from([+1, -1]))
    def pular(self, passo):
        self.ctl.andar(passo)

    @rule(i=st.integers(0, 10_000))
    def selecionar(self, i):
        if self.ctl.gids:
            self.ctl.alternar_na_selecao(i % len(self.ctl.gids))

    @rule()
    def limpar_selecao(self):
        self.ctl.limpar_selecao()

    @rule(x=st.integers(0, 40))
    def dividir(self, x):
        atual = self.ctl.atual
        if atual is None:
            return
        caixa = self.ctl.box(atual)
        antes = set(self.ctl.gids)
        self.ctl.dividir(caixa.x1 + x if caixa.x1 + x < caixa.x2 and x > 0 else None)
        if atual not in self.ctl.gids:           # dividiu: o atual é a primeira parte
            novos = [g for g in self.ctl.gids if g not in antes]
            assert self.ctl.atual == novos[0] and len(novos) == 2

    @rule(passo=st.sampled_from([+1, -1]))
    def juntar(self, passo):
        self.ctl.juntar(passo)

    @rule()
    def descartar(self):
        if len(self.ctl.gids) > 1:
            self.ctl.descartar()

    @rule(c=st.sampled_from("abz"))
    def corrigir(self, c):
        self.ctl.corrigir(c)

    @rule(i=st.integers(0, 10_000))
    def marcar(self, i):
        gid = self._gid(i)
        if gid is not None:
            e = self.ctl.box(gid)
            self.ctl.marcar(e.x1 - 2, e.y1 - 2, e.x2 + 2, e.y2 + 2)

    @rule(c=st.sampled_from("ab"))
    def ensinar(self, c):
        atual = self.ctl.atual
        self.ctl.ensinar(c)
        if atual is not None:
            assert self.ctl.box(atual).char == c and self.ctl.box(atual).source == "manual"

    @rule(tudo=st.booleans())
    def reler(self, tudo):
        self.ctl.reler_pendentes(tudo)

    @rule()
    def desfazer(self):
        self.ctl.desfazer()

    @rule()
    def refazer(self):
        self.ctl.refazer()

    # ------------------------------------------------------------------
    @invariant()
    def pulados_selecao_e_atual_sao_vivos(self):
        vivos = set(self.ctl.gids)
        assert self.ctl.pulados <= vivos
        assert self.ctl.selecao <= vivos
        assert self.ctl.atual is None or self.ctl.atual in vivos

    @invariant()
    def fila_e_uma_permutacao_dos_pendentes(self):
        fila = self.ctl.fila()
        assert len(fila) == len(set(fila)) and set(fila) <= set(self.ctl.gids)

    @invariant()
    def gids_unicos_e_decisoes_vivas(self):
        modelo = self.ctl.modelo
        gids = [b.gid for b in modelo.boxes]
        assert len(gids) == len(set(gids))
        assert modelo.decisoes.gids() <= modelo.vivos


MaquinaDoControlador.TestCase.settings = settings(
    max_examples=EXEMPLOS, derandomize=True, stateful_step_count=25, deadline=None,
    # Sem a fase "explain": ela roda com rastreio linha a linha e leva minutos.
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target, Phase.shrink],
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
test_maquina_do_controlador = pytest.mark.timeout(600)(MaquinaDoControlador.TestCase)
