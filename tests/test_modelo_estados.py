"""CA-4.3 (parte do 1b): máquina de estados sobre os gids, as decisões e `montar()`.

Uma página sintética de 900×400 com 1 a 60 glifos (cada um, dois traços de tinta com um vão,
para o `dividir` ter onde cortar). As regras do 1b: dividir, juntar, marcar, quebrar,
juntar palavras e o glifo virtual. A cada passo, os invariantes de §4.5: gids únicos;
aposentados ∩ vivos = ∅; nenhuma decisão cita gid aposentado; `montar()` cobre cada glifo
lido e cada virtual uma vez.

Suíte rápida: `derandomize=True`, `max_examples=200`. A camada noturna roda 5.000.
"""

from __future__ import annotations

import os

import pytest
from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule
from PIL import Image, ImageDraw

from core.box_model import BoxEntry

from abbychess import edicao as ed
from abbychess import texto as tx
from abbychess.modelo import Box, Pagina, gid_de

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

    def _registrar(self, dif):
        novos = {b.gid for b in dif.novos}
        assert not novos & self.alocados, "gid reaproveitado"
        self.alocados |= novos

    @rule(i=st.integers(0, 10_000))
    def dividir(self, i):
        gid = self._escolher(i)
        if gid is None:
            return
        try:
            dif = ed.dividir(self.pagina, self.imagem, gid)
        except ValueError:
            return                                    # sem tinta dos dois lados: não divide
        assert dif.sucessores[gid] == [b.gid for b in dif.novos] and len(dif.novos) == 2
        self._registrar(dif)

    @rule(i=st.integers(0, 10_000))
    def juntar(self, i):
        if len(self.pagina.boxes) < 2:
            return
        k = i % (len(self.pagina.boxes) - 1)
        a, b = self.pagina.boxes[k].gid, self.pagina.boxes[k + 1].gid
        dif = ed.juntar(self.pagina, self.imagem, a, b)
        assert dif.sucessores == {a: [dif.novos[0].gid], b: [dif.novos[0].gid]}
        self._registrar(dif)

    @rule(i=st.integers(0, 10_000))
    def marcar(self, i):
        gid = self._escolher(i)
        if gid is None:
            return
        e = self.pagina.box(gid).entry
        try:
            dif = ed.marcar(self.pagina, self.imagem, (e.x1 - 2, e.y1 - 2, e.x2 + 2, e.y2 + 2))
        except ValueError:
            return
        self._registrar(dif)

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
            ed.descartar(self.pagina, gid)

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
    def montar_cobre_cada_glifo_uma_vez(self):
        doc = tx.montar(self.pagina)
        esperados = [b.gid for b in self.pagina.boxes if b.entry.char]
        esperados += [v.gid for v in self.pagina.decisoes.virtuais]
        assert sorted(doc.gids()) == sorted(esperados)


MaquinaDaPagina.TestCase.settings = settings(
    max_examples=EXEMPLOS, derandomize=True, stateful_step_count=25, deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
test_maquina_da_pagina = pytest.mark.timeout(600)(MaquinaDaPagina.TestCase)
