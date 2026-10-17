"""CA-4.3: máquina de estados sobre os gids, as decisões e `montar()` (D1: editar_palavra).

Uma página sintética de 900×400 com 1 a 60 glifos (cada um, dois traços de tinta com um vão,
para o `dividir` ter onde cortar). As regras do 1b: dividir, juntar, marcar, quebrar,
juntar palavras e o glifo virtual, pelas edições por gid (`abbychess.edicao`) e também pelo
caminho da janela de hoje (a lista de `BoxEntry` editada por `abbychess.pagina` e
reconciliada, `modelo.reconciliar`). A cada passo, os invariantes de §4.5: gids únicos;
aposentados ∩ vivos = ∅; nenhuma decisão cita gid aposentado; `montar()` cobre cada glifo
lido e cada virtual uma vez. E dois do modelo: nenhuma edição perde uma decisão cujo glifo
ela não tocou, e uma quebra e uma junção nunca valem na mesma fronteira. Do D1: a sessão
confirmada (sem recusa) deixa na página o texto digitado, e a âncora de todo virtual é um box
vivo ou outro virtual.

Suíte rápida: `derandomize=True`, `max_examples=120`. A camada noturna roda 5.000.
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
from abbychess import sessao as ss
from abbychess import texto as tx
from abbychess.modelo import Box, Pagina, foto, gid_de, reconciliar

LARGURA, ALTURA = 900, 400
EXEMPLOS = 5000 if os.environ.get("ABBY_NOTURNO") == "1" else 120


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


ACOES = ["trocar", "apagar", "inserir", "inserir_antes", "comeco", "espaco", "palavra",
         "trocar_e_partir", "juntar", "nada"]


def _trecho(pagina, i, acao, c):
    """O texto da página, a sessão [a, b) de uma edição numa palavra e o texto novo dela
    (ou None)."""
    texto, unidades = ss.texto_e_unidades(pagina)
    glifos = [k for k, u in enumerate(unidades) if u.glifo]
    if not glifos:
        return None
    k = glifos[i % len(glifos)]
    a, b = ss.palavras_em(unidades, k, k + 1)
    if acao == "juntar":
        if b >= len(unidades) or unidades[b].tipo != ss.ESPACO:
            return None
        b = ss.palavras_em(unidades, b + 1, b + 1)[1]
    trecho, onde = texto[a:b], k - a
    if acao in ("espaco", "trocar_e_partir") and (onde + 1 >= len(trecho) or trecho[onde + 1] == " "):
        return None                             # um espaço na borda não parte nada
    novo = {"trocar": trecho[:onde] + c + trecho[onde + 1:],
            "apagar": trecho[:onde] + trecho[onde + 1:],
            "inserir": trecho[:onde + 1] + c + trecho[onde + 1:],
            "inserir_antes": trecho[:onde] + c + trecho[onde:],
            "comeco": c + trecho,
            "espaco": trecho[:onde + 1] + " " + trecho[onde + 1:],
            "palavra": trecho + " " + c,
            "trocar_e_partir": trecho[:onde] + c + " " + trecho[onde + 1:],
            "juntar": trecho.replace(" ", "", 1),
            "nada": trecho}[acao]
    if not novo.strip():
        return None
    return texto, unidades, a, b, novo


def sessao_de_uma_palavra(pagina, i, acao, c):
    """As unidades e o texto novo de uma edição numa palavra da página (ou None)."""
    trecho = _trecho(pagina, i, acao, c)
    if trecho is None:
        return None
    _texto, unidades, a, b, novo = trecho
    return unidades[a:b], novo


def editar_uma_palavra(pagina, i, acao, c):
    """A edição pela sessão; sem recusa, a página fica com o texto digitado."""
    trecho = _trecho(pagina, i, acao, c)
    if trecho is None:
        return
    texto, unidades, a, b, novo = trecho
    try:
        plano = ss.editar(pagina, unidades[a:b], novo)
    except ss.Recusa:
        return
    if acao != "apagar":                         # um box só sai se a letra dele foi apagada
        assert not plano.sair
    esperado = texto[:a] + novo + texto[b:]
    agora, unidades_agora = ss.texto_e_unidades(pagina)
    ficaram = pagina.vivos
    antes = [tuple(g for g in linha if g in ficaram) for linha in _linhas_dos_boxes(unidades)]
    if not ficaram or [linha for linha in antes if linha] != _linhas_dos_boxes(unidades_agora):
        # Tirar um box mudou como o core agrupa as linhas da página (as linhas são dela), ou
        # a página ficou sem box nenhum (sem linhas; os virtuais sem âncora vão ao começo):
        # os caracteres ficam os digitados.
        assert sorted(agora.replace(" ", "").replace("\n", "")) == \
            sorted(esperado.replace(" ", "").replace("\n", ""))
    elif not all(antes):
        # Uma linha ficou sem box (e uma linha só existe com boxes): o virtual que sobrou nela
        # vai para a vizinha, e as palavras ficam as digitadas, na ordem.
        assert agora.split() == esperado.split()
    else:
        assert agora == esperado


def _linhas_dos_boxes(unidades):
    """Os boxes de cada linha impressa da página, em ordem."""
    linhas, atual = [], []
    for u in list(unidades) + [ss.Unidade("\n", None, ss.LINHA)]:
        if u.tipo == ss.LINHA:
            linhas.append(tuple(atual))
            atual = []
        elif u.tipo == ss.GLIFO and (not atual or atual[-1] != u.gid):
            atual.append(u.gid)
    return [linha for linha in linhas if linha]


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

    @rule(i=st.integers(0, 10_000), acao=st.sampled_from(ACOES), c=st.sampled_from("xz1"))
    def editar_palavra(self, i, acao, c):
        """D1: uma sessão do Documento numa palavra (§6.3), pela sessão sem Qt."""
        editar_uma_palavra(self.pagina, i, acao, c)

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
    def a_ancora_de_todo_virtual_esta_na_pagina(self):
        d = self.pagina.decisoes
        validos = self.pagina.vivos | {v.gid for v in d.virtuais}
        for v in d.virtuais:
            assert v.depois_de is None or v.depois_de in validos
            assert v.antes_de is None or v.antes_de in validos
        ancora = {v.gid: v.depois_de if v.depois_de is not None else v.antes_de
                  for v in d.virtuais}
        for gid in ancora:                                # e nenhuma cadeia fecha um ciclo
            vistos = set()
            while gid in ancora:
                assert gid not in vistos
                vistos.add(gid)
                gid = ancora[gid]

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
        idioma = "pt"
        notacao = "letras"

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

    def para_propagar(self):
        return self


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
        self.inicial = (list(pagina.boxes), pagina.decisoes, pagina.estado)
        #: O reler muda glifos sem passar pelo desfazer (§14.2): depois dele, desfazer tudo
        #: não precisa voltar à página inicial.
        self.mudou_por_fora = False

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
        antes = list(self.ctl.modelo.boxes)
        self.ctl.reler_pendentes(tudo)
        self.mudou_por_fora |= self.ctl.modelo.boxes != antes

    @rule()
    def desfazer_tudo(self):
        """CA-4.3 (2b): desfazer tudo volta à página inicial (os mesmos `Box`, as decisões e
        o estado), se nada a mudou por fora do desfazer."""
        historico = self.ctl.historico
        while historico.proxima_a_desfazer() is not None:
            antes = historico.proxima_a_desfazer()
            self.ctl.desfazer()
            if historico.proxima_a_desfazer() is antes:
                assert self.mudou_por_fora, "desfazer recusado sem mudança por fora"
                return
        if not self.mudou_por_fora:
            boxes, decisoes, estado = self.inicial
            assert self.ctl.modelo.boxes == boxes
            assert self.ctl.modelo.decisoes == decisoes and self.ctl.modelo.estado == estado

    @rule(i=st.integers(0, 10_000), acao=st.sampled_from(ACOES), c=st.sampled_from("xz1"))
    def editar_palavra(self, i, acao, c):
        """D1: a sessão do Documento pelo controlador (um passo do desfazer)."""
        sessao = sessao_de_uma_palavra(self.ctl.modelo, i, acao, c)
        if sessao is not None:
            self.ctl.confirmar_sessao(*sessao)

    @rule()
    def desfazer(self):
        self.ctl.desfazer()

    @rule()
    def refazer(self):
        self.ctl.refazer()

    @rule(c=st.sampled_from("ab"), qual=st.sampled_from(["corrigir", "descartar", "juntar"]))
    def editar_e_desfazer(self, c, qual):
        """Desfazer logo depois de uma edição volta a página (os mesmos `Box`) e o estado."""
        if self.ctl.atual is None or len(self.ctl.gids) < 2:
            return
        antes, estado = list(self.ctl.modelo.boxes), self.ctl.modelo.estado
        decisoes = self.ctl.modelo.decisoes
        {"corrigir": lambda: self.ctl.corrigir(c), "descartar": self.ctl.descartar,
         "juntar": lambda: self.ctl.juntar(+1)}[qual]()
        if self.ctl.modelo.boxes == antes:
            return                                   # a edição não se aplicou (sem vizinho)
        self.ctl.desfazer()
        assert self.ctl.modelo.boxes == antes and self.ctl.modelo.estado == estado
        assert self.ctl.modelo.decisoes == decisoes

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
