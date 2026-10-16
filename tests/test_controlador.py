"""O controlador da página com as tarefas em voo (passo 2a): o que entra e o que não entra.

Um executor manual roda o `preparar` e o `trabalho` de cada tarefa quando o teste manda e
guarda o `pronto`, para o teste trocar de página ou de projeto no meio. E as leituras feitas
sobre cópias: só entram nos glifos que não mudaram (`edicao.aplicar_leituras`).
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from core.box_model import BoxEntry

from abbychess import edicao as ed
from abbychess import procedencia
from abbychess.controlador import ControladorDePagina
from abbychess.leitor import LeitorDoLivro
from abbychess import pagina as pg
from abbychess.modelo import Box, Pagina, gid_de
from abbychess.projeto import ProjetoDeLivro

from tests.test_treino_por_livro import _pagina_sintetica


class ExecutorManual:
    """Guarda as tarefas; `comecar()` roda o preparar e o trabalho da primeira e devolve o
    pronto com o resultado, para o teste chamar quando quiser."""

    def __init__(self):
        self.fila = []
        #: A tarefa começada cujo fim o teste ainda não chamou (e se ela é leve).
        self.em_voo = None

    def __call__(self, titulo, preparar, falhou=None, progresso=None, leve=False):
        self.fila.append((titulo, preparar, leve))

    def so_leves(self):
        return (self.em_voo is None or self.em_voo) and all(t[2] for t in self.fila)

    def comecar(self):
        titulo, preparar, leve = self.fila.pop(0)
        par = preparar()
        if par is None:
            return None
        trabalho, pronto = par
        resultado = trabalho(lambda *_: None)
        self.em_voo = leve

        def fim():
            self.em_voo = None
            pronto(resultado)
        return fim

    def tudo(self):
        while self.fila:
            fim = self.comecar()
            if fim is not None:
                fim()


# ----------------------------------------------------------------------
# aplicar_leituras
# ----------------------------------------------------------------------

def _pagina(n=4):
    boxes = [Box(gid_de(1, k), BoxEntry("", 10 * k, 0, 10 * k + 8, 9, 0.1, "nenhuma"))
             for k in range(n)]
    return Pagina(pid=1, indice=0, boxes=boxes, proximo_n=n)


def _ler_tudo(lidos, char="x"):
    for e in lidos:
        e.char, e.source, e.confidence = char, "rede", 0.9
        procedencia.registrar(e, None)


def test_aplicar_leituras_poe_a_leitura_e_nao_muda_o_objeto_velho():
    pagina = _pagina()
    antes = tuple(pagina.boxes)
    lidos = ed.copias_para_ler(antes, lambda e: True)
    _ler_tudo(lidos)
    dif = ed.aplicar_leituras(pagina, antes, lidos)
    assert dif.mudados == {b.gid for b in antes}
    assert all(b.entry.char == "x" for b in pagina.boxes)
    assert all(b.entry.char == "" for b in antes)       # o instantâneo não mudou


def test_edicao_feita_durante_a_leitura_vence_a_leitura():
    pagina = _pagina()
    antes = tuple(pagina.boxes)
    lidos = ed.copias_para_ler(antes, lambda e: True)
    ed.corrigir(pagina, antes[1].gid, "Z")             # o usuário corrigiu enquanto lia
    ed.descartar(pagina, antes[2].gid)                 # e tirou outro
    _ler_tudo(lidos)
    dif = ed.aplicar_leituras(pagina, antes, lidos)
    assert dif.mudados == {antes[0].gid, antes[3].gid}
    assert pagina.box(antes[1].gid).entry.char == "Z"
    assert antes[2].gid not in pagina.vivos


def test_leitura_que_nao_mudou_nada_nao_e_mudanca():
    pagina = _pagina()
    antes = tuple(pagina.boxes)
    lidos = ed.copias_para_ler(antes, lambda e: e.x1 == 0)   # só o primeiro é copiado
    assert lidos[1] is antes[1].entry
    assert ed.aplicar_leituras(pagina, antes, lidos).vazia
    assert pagina.boxes == list(antes)


# ----------------------------------------------------------------------
# Tarefas em voo
# ----------------------------------------------------------------------

@pytest.fixture
def dois_projetos(tmp_path):
    projetos = []
    for nome in ("Primeiro", "Segundo"):
        fonte = _pagina_sintetica(tmp_path / f"{nome}.png")
        projetos.append(ProjetoDeLivro.criar(tmp_path / "livros", nome, fonte))
    yield projetos
    for p in projetos:
        p.fechar()


def _controlador(projeto, executor):
    ctl = ControladorDePagina(executar=executor)
    ctl.ligar(projeto, pg.FonteDePaginas(projeto.fonte),
              LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    ctl.ir_para(0)
    return ctl


def test_resultado_de_tarefa_do_projeto_anterior_nao_entra_no_novo(dois_projetos):
    a, b = dois_projetos
    executor = ExecutorManual()
    ctl = _controlador(a, executor)
    ctl.reconhecer()
    fim = executor.comecar()                           # leu, mas o fim ainda não veio
    ctl.ligar(b, pg.FonteDePaginas(b.fonte),
              LeitorDoLivro(b.pasta_de_padroes, limiares=b.dados.limiares))
    ctl.ir_para(0)
    fim()
    assert ctl.boxes == [] and b.carregar_modelo(0) is None
    assert not b.sujas and b.paginas_lidas() == []


def test_tarefa_na_fila_do_projeto_anterior_nao_roda(dois_projetos):
    a, b = dois_projetos
    executor = ExecutorManual()
    ctl = _controlador(a, executor)
    ctl.reconhecer()
    fim = executor.comecar()                           # uma leitura em voo prende a fila
    ctl.marcar(0, 0, 300, 120)                         # na fila, ainda não rodou
    ctl.ligar(b, pg.FonteDePaginas(b.fonte),
              LeitorDoLivro(b.pasta_de_padroes, limiares=b.dados.limiares))
    ctl.ir_para(0)
    fim()
    executor.tudo()
    assert ctl.boxes == [] and b.carregar_modelo(0) is None


def test_reconhecer_entra_na_pagina_que_pediu_mesmo_depois_de_trocar(tmp_path):
    from tests.test_livro import pdf_sintetico

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Duas", pdf_sintetico(tmp_path))
    try:
        executor = ExecutorManual()
        ctl = _controlador(projeto, executor)
        ctl.reconhecer()
        fim = executor.comecar()
        ctl.ir_para(1)                                 # o usuário foi adiante
        fim()
        assert ctl.indice == 1 and ctl.boxes == []    # a página aberta não mudou
        assert projeto.carregar_modelo(0).boxes        # a pedida ficou reconhecida
        assert projeto.paginas_lidas() == [0]
    finally:
        projeto.fechar()


def test_edicao_pedida_numa_pagina_nao_roda_em_outra(tmp_path):
    from tests.test_livro import pdf_sintetico

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Duas", pdf_sintetico(tmp_path))
    try:
        executor = ExecutorManual()
        ctl = _controlador(projeto, executor)
        ctl.ir_para(1)
        ctl.reconhecer()
        fim = executor.comecar()                       # uma leitura em voo prende a fila
        ctl.ir_para(0)
        ctl.marcar(0, 0, 300, 120)                     # pedida na página 0, na fila
        ctl.ir_para(1)
        fim()
        executor.tudo()
        assert projeto.carregar_modelo(0) is None      # não rodou: a página tinha mudado
    finally:
        projeto.fechar()


def test_comando_guarda_o_glifo_da_hora_em_que_foi_pedido(dois_projetos):
    a, _ = dois_projetos
    executor = ExecutorManual()
    ctl = _controlador(a, executor)
    ctl.reconhecer()
    executor.tudo()
    primeiro, segundo = ctl.gids[0], ctl.gids[1]
    ctl.mostrar(primeiro)
    ctl.corrigir("Q")                                  # pedido para o primeiro
    ctl.mostrar(segundo)                               # o painel mudou antes da vez dele
    executor.tudo()
    assert ctl.box(primeiro).char == "Q" and ctl.box(segundo).char != "Q"
    assert replace(ctl.box(primeiro)).source == "manual"


def test_diagramas_lidos_entram_na_pagina_que_pediu(tmp_path, monkeypatch):
    from abbychess import diagramas as dg
    from abbychess.controladores import ControladorDeDiagramas
    from tests.test_livro import pdf_sintetico

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Duas", pdf_sintetico(tmp_path))
    try:
        modelo = projeto.pagina_para_editar(0)
        modelo.tabuleiros = [(10, 10, 210, 210)]
        projeto.agendar(modelo)
        executor = ExecutorManual()
        ctl = _controlador(projeto, executor)
        abertas = []
        ctl.eventos.ligar("conferir", abertas.append)
        conferencia = ControladorDeDiagramas(ctl)
        monkeypatch.setattr(dg, "ler_diagramas", lambda _img, caixas, **_k: [
            dg.DiagramaLido(c, casas=[None] * 64) for c in caixas])
        conferencia.conferir(0)
        fim = executor.comecar()
        ctl.ir_para(1)                                  # o usuário foi adiante
        fim()
        assert projeto.carregar_modelo(0).diagramas[0].lido
        assert projeto.carregar_modelo(1) is None and abertas == []
    finally:
        projeto.fechar()


def test_corrigir_e_ensinar_uma_palavra_e_um_passo_so_do_desfazer(dois_projetos):
    from abbychess import verificacao as vf
    from abbychess.controladores import ControladorDeVerificacao

    a, _ = dois_projetos
    executor = ExecutorManual()
    ctl = _controlador(a, executor)
    ctl.reconhecer()
    executor.tudo()
    verificador = ControladorDeVerificacao(ctl)
    antes = [b for b in ctl.modelo.boxes]
    class _SemLexico:                                   # não sinaliza nada ao recontar
        sinaliza = False

    verificador.lexico = _SemLexico()
    verificador._gids = ctl.gids
    verificador.desconhecidas = [vf.Desconhecida("ab", [0, 1])]
    verificador.corrigir("xy", ensinar=True)
    executor.tudo()                                     # a correção e, depois, o ensino
    assert [ctl.box(g).char for g in ctl.gids[:2]] == ["x", "y"]
    assert ctl.leitor.total_de_padroes == 2
    ctl.desfazer()
    executor.tudo()
    assert ctl.modelo.boxes == antes                    # um Ctrl+Z volta as duas coisas
    assert ctl.leitor.total_de_padroes == 0
    assert ctl.historico.proximo_a_desfazer == "Reconhecer a página"


def test_lote_nao_comeca_se_o_gravador_nao_descarrega(dois_projetos, monkeypatch):
    from abbychess.controladores import ControladorDoLivro

    a, _ = dois_projetos
    executor = ExecutorManual()
    ctl = _controlador(a, executor)
    avisos = []
    ctl.eventos.ligar("aviso", lambda titulo, texto: avisos.append(texto))
    monkeypatch.setattr(a, "descarregar", lambda limite=None: False)
    ControladorDoLivro(ctl).reconhecer([0], refazer=False)
    executor.tudo()
    assert avisos and "não começou" in avisos[0]
    assert not ctl.lote_rodando and a.paginas_lidas() == []


def test_trocar_de_projeto_solta_o_lote_preso(dois_projetos):
    a, b = dois_projetos
    executor = ExecutorManual()
    ctl = _controlador(a, executor)
    ctl.lote_rodando = True                             # o fim do lote foi descartado
    ctl.ligar(b, pg.FonteDePaginas(b.fonte),
              LeitorDoLivro(b.pasta_de_padroes, limiares=b.dados.limiares))
    assert not ctl.lote_rodando
