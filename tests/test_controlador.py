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
from abbychess.leitor import LeitorDoLivro
from abbychess import pagina as pg
from abbychess.modelo import Box, Pagina, gid_de
from abbychess.projeto import ProjetoDeLivro

from tests.ajudantes import _pagina_sintetica  # noqa: E402,F401,F811
from tests.ajudantes import ExecutorManual, _controlador  # noqa: E402,F401,F811


@pytest.mark.erro_esperado
def test_um_ouvinte_que_falha_nao_cala_os_seguintes_nem_o_comando(caplog):
    """SPEC-qualidade Q-C4: `glifos_mudaram` tem três ouvintes ou mais; o que levanta vai ao
    log com o rastro, os outros ouvem, e a exceção não sobe para o comando que emitiu (ele
    já mudou a página e continua)."""
    import logging

    from abbychess.controlador import Eventos

    eventos, ouvidos = Eventos(), []

    def quebrado(*_args):
        raise ValueError("o painel quebrou")

    eventos.ligar("glifos_mudaram", quebrado)
    eventos.ligar("glifos_mudaram", lambda *args: ouvidos.append(args))
    with caplog.at_level(logging.ERROR, logger="abbychess.controlador"):
        eventos.emitir("glifos_mudaram", None)
    assert ouvidos == [(None,)]
    assert [r for r in caplog.records if r.exc_info and "glifos_mudaram" in r.getMessage()]


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


def test_resultado_de_tarefa_do_projeto_anterior_nao_entra_no_novo(dois_projetos):
    a, b = dois_projetos
    executor = ExecutorManual()
    ctl = _controlador(a, executor)
    ctl.leitura.reconhecer()
    fim = executor.comecar()                           # leu, mas o fim ainda não veio
    ctl.ligar(b, pg.FonteDePaginas(b.fonte),
              LeitorDoLivro(b.pasta_de_padroes, limiares=b.dados.limiares))
    ctl.ir_para(0)
    fim()
    assert ctl.boxes == [] and b.carregar_modelo(0) is None
    assert not b.paginas_em_memoria.sujas and b.resumo.paginas_lidas() == []


def test_tarefa_na_fila_do_projeto_anterior_nao_roda(dois_projetos):
    a, b = dois_projetos
    executor = ExecutorManual()
    ctl = _controlador(a, executor)
    ctl.leitura.reconhecer()
    fim = executor.comecar()                           # uma leitura em voo prende a fila
    ctl.marcar(0, 0, 300, 120)                         # na fila, ainda não rodou
    ctl.ligar(b, pg.FonteDePaginas(b.fonte),
              LeitorDoLivro(b.pasta_de_padroes, limiares=b.dados.limiares))
    ctl.ir_para(0)
    fim()
    executor.tudo()
    assert ctl.boxes == [] and b.carregar_modelo(0) is None


def test_reconhecer_entra_na_pagina_que_pediu_mesmo_depois_de_trocar(tmp_path):
    from tests.ajudantes import pdf_sintetico  # noqa: E402,F401,F811

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Duas", pdf_sintetico(tmp_path))
    try:
        executor = ExecutorManual()
        ctl = _controlador(projeto, executor)
        ctl.leitura.reconhecer()
        fim = executor.comecar()
        ctl.ir_para(1)                                 # o usuário foi adiante
        fim()
        assert ctl.indice == 1 and ctl.boxes == []    # a página aberta não mudou
        assert projeto.carregar_modelo(0).boxes        # a pedida ficou reconhecida
        assert projeto.resumo.paginas_lidas() == [0]
    finally:
        projeto.fechar()


def test_edicao_pedida_numa_pagina_nao_roda_em_outra(tmp_path):
    from tests.ajudantes import pdf_sintetico  # noqa: E402,F401,F811

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Duas", pdf_sintetico(tmp_path))
    try:
        executor = ExecutorManual()
        ctl = _controlador(projeto, executor)
        ctl.ir_para(1)
        ctl.leitura.reconhecer()
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
    ctl.leitura.reconhecer()
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
    from abbychess.controlador_de_diagramas import ControladorDeDiagramas
    from tests.ajudantes import _lido, pdf_sintetico  # noqa: E402,F401,F811

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Duas", pdf_sintetico(tmp_path))
    try:
        modelo = projeto.pagina_para_editar(0)
        modelo.tabuleiros = [(10, 10, 210, 210)]
        projeto.paginas_em_memoria.agendar(modelo)
        executor = ExecutorManual()
        ctl = _controlador(projeto, executor)
        abertas = []
        ctl.eventos.ligar("conferir", abertas.append)
        conferencia = ControladorDeDiagramas(ctl)
        monkeypatch.setattr(dg, "ler_diagramas", lambda _img, caixas, **_k: [
            _lido(caixa=c) for c in caixas])
        conferencia.conferir(0)
        fim = executor.comecar()
        ctl.ir_para(1)                                  # o usuário foi adiante
        fim()
        assert projeto.carregar_modelo(0).diagramas[0].lido
        assert projeto.carregar_modelo(1) is None and abertas == []
    finally:
        projeto.fechar()


# ----------------------------------------------------------------------
# A conferência dos diagramas pelo livro
# ----------------------------------------------------------------------

#: As caixas dos tabuleiros de cada página do livro de três (a do meio não tem nenhum).
CAIXAS = {0: [(10, 10, 110, 110), (200, 10, 300, 110)], 2: [(10, 10, 110, 110)]}


@pytest.fixture
def livro_com_diagramas(tmp_path):
    """O livro de três páginas com os diagramas lidos nas pontas, aberto na primeira; as
    mensagens e as conferências abertas, `(página, diagrama)`, em `ouvidos`."""
    from abbychess.controlador_de_diagramas import ControladorDeDiagramas
    from tests.ajudantes import _lido, pdf_sintetico  # noqa: E402,F401,F811

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Tres", pdf_sintetico(tmp_path))
    for indice, caixas in CAIXAS.items():
        modelo = projeto.pagina_para_editar(indice)
        modelo.tabuleiros = caixas
        modelo.diagramas = [_lido(caixa=c) for c in caixas]
        projeto.paginas_em_memoria.agendar(modelo)
    ctl = _controlador(projeto, ExecutorManual())
    ouvidos = []
    ctl.eventos.ligar("conferir", lambda i: ouvidos.append((ctl.indice, i)))
    ctl.eventos.ligar("mensagem", lambda texto, _ms: ouvidos.append(texto))
    yield ctl, ControladorDeDiagramas(ctl), ouvidos
    projeto.fechar()


def test_pgdn_e_pgup_na_ponta_da_pagina_abrem_o_diagrama_vizinho_no_livro(livro_com_diagramas):
    ctl, conferencia, ouvidos = livro_com_diagramas
    conferencia.vizinho_do_livro(+1)                   # pula a do meio, sem diagrama
    conferencia.vizinho_do_livro(-1)                   # o último da anterior
    conferencia.vizinho_do_livro(-1)                   # não dá a volta no livro
    assert ouvidos == [(2, 0), (0, 1), "Não há diagrama antes deste no livro."]
    assert ctl.indice == 0


def test_a_pagina_vizinha_que_nao_abre_avisa_e_fica(livro_com_diagramas, monkeypatch):
    ctl, conferencia, ouvidos = livro_com_diagramas

    def pagina(entrada, *_a, **_k):
        raise OSError("A página 3 não renderizou.")

    monkeypatch.setattr(ctl.fonte, "pagina_da_entrada", pagina)
    conferencia.vizinho_do_livro(+1)
    assert ouvidos == ["A página 3 não abriu."] and ctl.indice == 0


def test_conferir_na_pagina_sem_diagrama_avisa(livro_com_diagramas):
    ctl, conferencia, ouvidos = livro_com_diagramas
    ctl.ir_para(1)
    conferencia.conferir()
    assert ouvidos == ["Não há diagrama nesta página."]


def test_o_diagrama_por_ler_nao_se_confere(livro_com_diagramas):
    from core.tabuleiro_edicao import TabuleiroEdicao
    from tests.ajudantes import FEN  # noqa: E402,F401,F811

    ctl, conferencia, ouvidos = livro_com_diagramas
    modelo = ctl.projeto.pagina_para_editar(0)
    modelo.diagramas = []                              # a página gravada antes da leitura
    ctl.projeto.paginas_em_memoria.agendar(modelo)
    ctl.ir_para(0)
    assert conferencia.aplicar(CAIXAS[0][1], TabuleiroEdicao.de_fen(FEN), False) is False
    assert ouvidos == ["O diagrama 2 não foi lido: não há posição a conferir."]
    assert not any(d.conferido for d in ctl.diagramas)


def test_o_projeto_so_para_leitura_nao_grava_a_conferencia(livro_com_diagramas):
    import json

    from core.tabuleiro_edicao import TabuleiroEdicao
    from tests.ajudantes import FEN  # noqa: E402,F401,F811

    ctl, _, _ = livro_com_diagramas
    pasta = ctl.projeto.pasta
    ctl.projeto.fechar()
    arquivo = pasta / "projeto.json"
    arquivo.write_text(json.dumps({**json.loads(arquivo.read_text(encoding="utf-8")),
                                   "versao": 99}), encoding="utf-8")
    so_leitura = ProjetoDeLivro.abrir(pasta)
    try:
        from abbychess.controlador_de_diagramas import ControladorDeDiagramas

        outro = _controlador(so_leitura, ExecutorManual())
        mensagens = []
        outro.eventos.ligar("mensagem", lambda texto, _ms: mensagens.append(texto))
        conferencia = ControladorDeDiagramas(outro)
        assert conferencia.aplicar(CAIXAS[0][0], TabuleiroEdicao.de_fen(FEN), True) is False
        assert mensagens == ["Projeto aberto só para leitura: a conferência não é gravada."]
        assert not outro.diagramas[0].conferido
        assert not (pasta / "diagramas").exists()      # nem as amostras
    finally:
        so_leitura.fechar()


@pytest.mark.erro_esperado
def test_as_amostras_que_nao_gravam_nao_desfazem_a_conferencia(livro_com_diagramas, monkeypatch):
    from abbychess import diagramas as dg
    from core.tabuleiro_edicao import TabuleiroEdicao
    from tests.ajudantes import FEN  # noqa: E402,F401,F811

    ctl, conferencia, ouvidos = livro_com_diagramas

    def guardar(*_a, **_k):
        raise OSError("disco cheio")

    monkeypatch.setattr(dg, "guardar_amostras", guardar)
    assert conferencia.aplicar(CAIXAS[0][0], TabuleiroEdicao.de_fen(FEN), True) is True
    fen = ctl.diagramas[0].fen
    assert ctl.diagramas[0].conferido
    assert ouvidos == [f"Diagrama 1 conferido: {fen}. As amostras não foram guardadas: "
                       "disco cheio"]


def _texto(ctl) -> str:
    """O texto da página como o Documento o mostra (□ no glifo que ninguém leu)."""
    from abbychess import sessao as ss

    return ss.texto_e_unidades(ctl.modelo)[0]


def _digitar(ctl, executor, n: int, novo: str) -> str:
    """O usuário digita `novo` no lugar da palavra `n` da página, no Documento (a sessão
    confirmada, na vez dela na fila); devolve o texto da página depois."""
    import re

    from abbychess import sessao as ss

    texto, unidades = ss.texto_e_unidades(ctl.modelo)
    comeco = list(re.finditer(r"\S+", texto))[n].start()
    inicio, fim = ss.palavras_em(unidades, comeco, comeco)
    ctl.sessoes.confirmar_sessao(unidades[inicio:fim], novo)
    executor.tudo()
    return _texto(ctl)


def _verificando_a_primeira_palavra(projeto):
    """A página reconhecida, a primeira palavra digitada "abc" no Documento, e a verificação
    (F7) contada com um léxico que não a conhece: ela é a palavra em revisão."""
    from core import lexico

    from abbychess.controladores import ControladorDeVerificacao

    executor = ExecutorManual()
    ctl = _controlador(projeto, executor)
    ctl.leitura.reconhecer()
    executor.tudo()
    assert _digitar(ctl, executor, 0, "abc").startswith("abc ")
    verificador = ControladorDeVerificacao(ctl)
    verificador.lexico = lexico.Lexico(palavras={"casa"})
    verificador.recontar()
    assert verificador.atual().palavra == "abc"
    return ctl, executor, verificador


def test_corrigir_e_ensinar_uma_palavra_e_um_passo_so_do_desfazer(dois_projetos):
    ctl, executor, verificador = _verificando_a_primeira_palavra(dois_projetos[0])
    antes = list(ctl.modelo.boxes)
    verificador.corrigir("xyz", ensinar=True)
    executor.tudo()                                     # a correção e, depois, o ensino
    assert _texto(ctl).startswith("xyz ")
    assert ctl.leitor.total_de_padroes == 3
    ctl.desfazedor.desfazer()
    executor.tudo()
    assert ctl.modelo.boxes == antes and _texto(ctl).startswith("abc ")   # um Ctrl+Z volta
    assert ctl.leitor.total_de_padroes == 0                               # as duas coisas
    assert ctl.historico.proximo_a_desfazer == "Editar 'abc'"


def test_espaco_na_correcao_separa_a_palavra_e_desfaz_junto(dois_projetos):
    ctl, executor, verificador = _verificando_a_primeira_palavra(dois_projetos[0])
    verificador.corrigir("x yz")
    executor.tudo()
    assert _texto(ctl).startswith("x yz ")
    ctl.desfazedor.desfazer()
    executor.tudo()
    assert _texto(ctl).startswith("abc ")               # a letra e o espaço, um Ctrl+Z


def test_trocar_de_projeto_solta_o_lote_preso(dois_projetos):
    a, b = dois_projetos
    executor = ExecutorManual()
    ctl = _controlador(a, executor)
    ctl.lote_rodando = True                             # o fim do lote foi descartado
    ctl.ligar(b, pg.FonteDePaginas(b.fonte),
              LeitorDoLivro(b.pasta_de_padroes, limiares=b.dados.limiares))
    assert not ctl.lote_rodando


def test_a_sessao_do_documento_na_fila_avisa_quando_entra(dois_projetos):
    """D1 (a revisão de código, achado 9): com a fila presa, a sessão confirmada espera a vez
    dela, e a janela só reposiciona o cursor (`depois`) quando a edição entrou."""
    from abbychess import sessao as ss

    a, _b = dois_projetos
    executor = ExecutorManual()
    ctl = _controlador(a, executor)
    ctl.leitura.reconhecer()
    executor.tudo()
    texto, unidades = ss.texto_e_unidades(ctl.modelo)
    inicio, fim = ss.palavras_em(unidades, 0, 0)
    executor.em_voo = False                            # uma leitura em voo prende a fila
    entrou = []
    ctl.sessoes.confirmar_sessao(unidades[inicio:fim], "x" + texto[inicio:fim],
                         depois=lambda: entrou.append(ss.texto_e_unidades(ctl.modelo)[0]))
    assert entrou == [] and executor.fila
    executor.em_voo = None
    executor.tudo()
    assert len(entrou) == 1 and entrou[0].startswith("x" + texto[inicio:fim])


def test_a_sessao_que_nao_pode_rodar_e_recusada(dois_projetos):
    """A revisão do D1 (rodada 2, achado 3): sem a imagem da página, a sessão não roda, e a
    janela ouve `sessao_recusada` para montar o Documento de novo do modelo."""
    from abbychess import sessao as ss

    a, _b = dois_projetos
    executor = ExecutorManual()
    ctl = _controlador(a, executor)
    ctl.leitura.reconhecer()
    executor.tudo()
    texto, unidades = ss.texto_e_unidades(ctl.modelo)
    inicio, fim = ss.palavras_em(unidades, 0, 0)
    recusas = []
    ctl.eventos.ligar("sessao_recusada", recusas.append)
    ctl.imagem = None
    ctl.sessoes.confirmar_sessao(unidades[inicio:fim], "x" + texto[inicio:fim])
    assert recusas and ss.texto_e_unidades(ctl.modelo)[0] == texto


def _sessao_na_primeira_palavra(projeto):
    from abbychess import sessao as ss

    executor = ExecutorManual()
    ctl = _controlador(projeto, executor)
    ctl.leitura.reconhecer()
    executor.tudo()
    texto, unidades = ss.texto_e_unidades(ctl.modelo)
    inicio, fim = ss.palavras_em(unidades, 0, 0)
    recusas = []
    ctl.eventos.ligar("sessao_recusada", recusas.append)
    return ctl, executor, unidades[inicio:fim], recusas


def test_apagar_a_palavra_do_glifo_escolhido_tira_a_escolha(dois_projetos):
    from abbychess import sessao as ss

    ctl, executor, palavra, recusas = _sessao_na_primeira_palavra(dois_projetos[0])
    palavras = len(ss.texto_e_unidades(ctl.modelo)[0].split())
    gids = {u.gid for u in palavra if u.glifo}
    ctl.escolher(next(iter(gids)))
    ctl.sessoes.confirmar_sessao(palavra, "")
    executor.tudo()
    assert ctl.atual is None and not gids & ctl.modelo.vivos and recusas == []
    assert len(ss.texto_e_unidades(ctl.modelo)[0].split()) == palavras - 1


def test_a_sessao_de_glifos_que_sairam_da_pagina_e_recusada(dois_projetos):
    from abbychess import sessao as ss

    ctl, executor, palavra, recusas = _sessao_na_primeira_palavra(dois_projetos[0])
    ctl.sessoes.confirmar_sessao(palavra, "")
    executor.tudo()
    depois = ss.texto_e_unidades(ctl.modelo)[0]
    ctl.sessoes.confirmar_sessao(palavra, "y")              # a sessão velha, da mesma palavra
    executor.tudo()
    assert recusas == ["a página mudou antes da confirmação"]
    assert ss.texto_e_unidades(ctl.modelo)[0] == depois


@pytest.mark.erro_esperado
def test_a_sessao_que_falha_ao_aplicar_volta_a_pagina(dois_projetos, monkeypatch):
    from abbychess import sessao as ss

    ctl, executor, palavra, recusas = _sessao_na_primeira_palavra(dois_projetos[0])
    antes = ss.texto_e_unidades(ctl.modelo)[0]
    desfazer = len(ctl.historico._desfazer)

    def falhar(*_a, **_k):
        raise RuntimeError("a edição quebrou no meio")

    monkeypatch.setattr(ss, "aplicar", falhar)
    ctl.sessoes.confirmar_sessao(palavra, "")
    executor.tudo()
    assert recusas == ["a edição falhou e foi desfeita"]
    assert ss.texto_e_unidades(ctl.modelo)[0] == antes
    assert len(ctl.historico._desfazer) == desfazer


def test_a_recusa_do_aplicar_chega_a_janela_com_o_motivo(dois_projetos, monkeypatch):
    """A `Recusa` do `aplicar` (o espaço num glifo que a tinta não corta) chega à janela com o
    motivo dela, não como falha, e a página e o desfazer ficam como estavam."""
    from abbychess import sessao as ss

    ctl, executor, palavra, recusas = _sessao_na_primeira_palavra(dois_projetos[0])
    antes = ss.texto_e_unidades(ctl.modelo)[0]
    desfazer = len(ctl.historico._desfazer)

    def recusar(*_a, **_k):
        raise ss.Recusa("não dá para pôr um espaço dentro do glifo “fi”")

    monkeypatch.setattr(ss, "aplicar", recusar)
    ctl.sessoes.confirmar_sessao(palavra, "")
    executor.tudo()
    assert recusas == ["não dá para pôr um espaço dentro do glifo “fi”"]
    assert ss.texto_e_unidades(ctl.modelo)[0] == antes
    assert len(ctl.historico._desfazer) == desfazer


@pytest.mark.parametrize("na_fila", [False, True])
def test_sair_da_pagina_confirma_a_sessao_na_pagina_dela(tmp_path, na_fila):
    """A revisão de produto do D1 (M3): trocar de página com a sessão aberta a confirma
    antes, na página dela, também quando a edição espera a vez na fila."""
    from abbychess import sessao as ss
    from tests.ajudantes import pdf_sintetico  # noqa: E402,F401,F811

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Duas", pdf_sintetico(tmp_path))
    try:
        executor = ExecutorManual()
        ctl = _controlador(projeto, executor)
        ctl.leitura.reconhecer()
        executor.tudo()
        pagina = ctl.modelo
        texto, unidades = ss.texto_e_unidades(pagina)
        inicio, fim = ss.palavras_em(unidades, 0, 0)
        novo = "x" + texto[inicio:fim]
        ctl.antes_de_sair_da_pagina = lambda: ctl.sessoes.confirmar_sessao(unidades[inicio:fim], novo)
        if na_fila:
            executor.em_voo = False                    # uma leitura em voo prende a fila
        assert ctl.ir_para(1) and ctl.indice == 1
        executor.em_voo = None
        executor.tudo()
        assert ss.texto_e_unidades(pagina)[0].startswith(novo)
        assert pagina.pid in {p for t in ctl.historico._desfazer for p in t.paginas}
    finally:
        projeto.fechar()


@pytest.mark.parametrize("letra, sai", [("x", True), (",", False)])
def test_o_box_marcado_confirmado_com_a_letra_que_faltava_tira_o_virtual(dois_projetos, letra, sai):
    """A revisão do D1: o virtual sai só quando o usuário confirma o box marcado ao lado
    dele com a letra dele (a vírgula marcada ali fica vírgula, e o virtual fica)."""
    a, _b = dois_projetos
    executor = ExecutorManual()
    ctl = _controlador(a, executor)
    sugeridas = []
    ctl.eventos.ligar("caractere_sugerido", sugeridas.append)
    ctl.leitura.reconhecer()
    executor.tudo()
    assert _digitar(ctl, executor, 0, "□□□x").startswith("□□□x ")   # o "x" que faltava
    terceiro = ctl.boxes[2]                             # o glifo ao lado do virtual
    ctl.marcar(terceiro.x1, terceiro.y1, terceiro.x2, terceiro.y2)   # Ctrl+M sobre a tinta
    executor.tudo()
    box = ctl.atual
    assert sugeridas == ["x"]                           # o Documento sugere a letra virtual
    ctl.corrigir(letra)                                 # Enter
    executor.tudo()
    assert _texto(ctl).startswith("□□x " if sai else f"□□{letra}x ")
    assert ctl.box(box).char == letra


def test_o_ctrl_t_espera_a_sessao_na_fila_e_fechar_aplica_na_hora(dois_projetos):
    """A revisão do D1: com a edição do texto na fila, o Ctrl+T espera (senão a edição a
    devolveria a em revisão); `agora` (fechar o projeto) aplica sem a fila."""
    from abbychess import sessao as ss

    a, _b = dois_projetos
    executor = ExecutorManual()
    ctl = _controlador(a, executor)
    ctl.leitura.reconhecer()
    executor.tudo()
    texto, unidades = ss.texto_e_unidades(ctl.modelo)
    inicio, fim = ss.palavras_em(unidades, 0, 0)
    executor.em_voo = False                            # uma leitura em voo prende a fila
    ctl.sessoes.confirmar_sessao(unidades[inicio:fim], "x" + texto[inicio:fim])
    ctl.verificar()
    assert ctl.modelo.estado != "verificada" and len(ctl.sessoes.na_fila) == 1
    executor.em_voo = None
    executor.tudo()
    assert not ctl.sessoes.na_fila
    assert a.resumo.estado_da_pagina(0) == "verificada"     # na vez dele, depois da edição
    assert a.carregar_modelo(0) is not None and ss.texto_e_unidades(a.carregar_modelo(0))[0].startswith("x")
    ctl.ir_para(0)
    executor.tudo()
    executor.em_voo = False
    texto, unidades = ss.texto_e_unidades(ctl.modelo)
    ctl.sessoes.confirmar_sessao(unidades[inicio:fim + 1], "y" + texto[inicio:fim + 1], agora=True)
    assert ss.texto_e_unidades(ctl.modelo)[0].startswith("y")


def test_o_modo_como_o_livro_olha_o_resumo_das_paginas_lidas(tmp_path):
    """A revisão de produto do D1: uma página sem figurinas num livro de figurinas segue o
    livro, pelo resumo do `livro.json` (sem abrir as páginas). O modo se vê no lance
    digitado no Documento: "Cf3" vira "♘f3" no livro de figurinas e fica como foi digitado
    no de letras."""
    from tests.ajudantes import pdf_sintetico  # noqa: E402,F401,F811

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Duas", pdf_sintetico(tmp_path))
    try:
        executor = ExecutorManual()
        ctl = _controlador(projeto, executor)
        assert projeto.dados.notacao == "livro"
        ctl.leitura.reconhecer()
        executor.tudo()
        assert _digitar(ctl, executor, 0, "Cf3").startswith("Cf3 ")   # sem figurinas: letras
        assert _digitar(ctl, executor, 1, "♘□□").startswith("Cf3 ♘□□ ")
        ctl.ir_para(1)
        ctl.leitura.reconhecer()
        executor.tudo()
        ctl.sessoes.zerar()                            # como ao abrir o projeto
        assert _digitar(ctl, executor, 0, "Cf3").startswith("♘f3 ")   # segue o livro
        ctl.padroes_do_livro.definir_notacao("letras")
        assert _digitar(ctl, executor, 1, "Cf3").startswith("♘f3 Cf3\n")
    finally:
        projeto.fechar()


def test_fechar_aplica_as_sessoes_que_esperavam_na_fila(dois_projetos):
    """A revisão do D1: a sessão confirmada que esperava a vez na fila entra ao fechar o
    projeto (a fila vai ser esvaziada), e só uma vez."""
    from abbychess import sessao as ss

    a, _b = dois_projetos
    executor = ExecutorManual()
    ctl = _controlador(a, executor)
    ctl.leitura.reconhecer()
    executor.tudo()
    texto, unidades = ss.texto_e_unidades(ctl.modelo)
    inicio, fim = ss.palavras_em(unidades, 0, 0)
    executor.em_voo = False
    ctl.sessoes.confirmar_sessao(unidades[inicio:fim], "x" + texto[inicio:fim])
    ctl.sessoes.aplicar_as_sessoes_na_fila()
    assert ss.texto_e_unidades(ctl.modelo)[0].startswith("x" + texto[inicio:fim])
    executor.em_voo = None
    executor.tudo()                                    # a tarefa da fila não aplica de novo
    assert ss.texto_e_unidades(ctl.modelo)[0].startswith("x" + texto[inicio:fim])
    assert not ss.texto_e_unidades(ctl.modelo)[0].startswith("xx")


def test_a_pagina_lida_antes_do_treino_avisa_o_reler(dois_projetos):
    """Mirkovic: as pp. 10 e 89, lidas na criação do projeto, ficaram com o O lido como 0
    depois do treino nas outras; abri-las avisa quantos padrões vieram depois e o Ctrl+R."""
    import os

    import numpy as np

    from abbychess.modelo import RECONHECIDA

    a, _b = dois_projetos
    executor = ExecutorManual()
    ctl = _controlador(a, executor)
    ctl.leitura.reconhecer()
    executor.tudo()
    ctl.modelo.estado = RECONHECIDA
    a.salvar_modelo(ctl.modelo)
    arquivo = a.arquivo_da_pagina(0)
    assert arquivo is not None and arquivo.is_file()
    os.utime(arquivo, (1_000_000_000, 1_000_000_000))       # lida há muito tempo
    avisos = []
    ctl.eventos.ligar("mensagem", lambda texto, *_: avisos.append(texto))
    ctl.ir_para(0)
    assert ctl.padroes_novos_da_pagina(0) == 0 and not any("antes de" in t for t in avisos)

    ctl.leitor.ensinar(np.full((20, 10), 0, np.uint8), "x")
    ctl.ir_para(0)
    assert ctl.padroes_novos_da_pagina(0) == 1
    assert any("lida antes de 1 padrão" in t and "{reler_pendentes}" in t for t in avisos)
