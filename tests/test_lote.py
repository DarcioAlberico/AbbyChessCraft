"""O lote pelo condutor (SPEC §11, §4.6), sem servidor: as regras de quem escreve.

O condutor lê cada página numa tarefa do executor (aqui, o `ExecutorManual`, que deixa o
teste escolher quando a leitura termina) e grava na thread de quem chama. Os casos:
a página aberta e suja não é sobrescrita (CA-11.4; a editada durante a leitura, com o
servidor, em `test_servidor_janela`); a verificada é pulada (CA-8.5);
cancelar e retomar não lê página duas vezes (CA-11.5); o "refazer" guarda a página de
antes e "Voltar ao estado antes do lote" a devolve idêntica (CA-4.8, a parte do lote); e
as edições não são recusadas durante o lote.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from abbychess import pagina as pg
from abbychess.controlador import ControladorDePagina, Eventos
from abbychess.controladores import ControladorDoLivro
from abbychess.leitor import FONTE_MANUAL, LeitorDoLivro
from abbychess.modelo import VERIFICADA
from abbychess.projeto import ProjetoDeLivro

from tests.test_controlador import ExecutorManual
from tests.test_livro import pdf_sintetico


@pytest.fixture
def projeto(tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Lote", pdf_sintetico(tmp_path))
    yield projeto
    projeto.fechar()


@pytest.fixture
def ctl(projeto):
    executor = ExecutorManual()
    pagina = ControladorDePagina(Eventos(), executar=executor)
    pagina.ligar(projeto, pg.FonteDePaginas(projeto.fonte),
                 LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    pagina.ir_para(0)
    livro = ControladorDoLivro(pagina)
    livro.executor = executor
    livro.fins = []
    pagina.eventos.ligar("lote_terminou", lambda mensagem, resultado: livro.fins.append(resultado))
    return livro


def _sem_hora(dados: bytes) -> dict:
    bruto = json.loads(dados)
    bruto.pop("gravado_em")
    return bruto


def _hash(projeto, indice) -> str:
    pid = projeto._pid_de(indice)
    return hashlib.sha256(projeto._arquivo_v2(pid).read_bytes()).hexdigest()


def test_o_lote_le_e_grava_as_paginas_e_a_aberta_aparece(ctl, projeto):
    ctl.reconhecer([0, 1, 2], refazer=False)
    assert ctl.lote_rodando
    ctl.executor.tudo()
    [resultado] = ctl.fins
    assert resultado.lidas == [0, 1, 2] and not ctl.lote_rodando
    assert projeto.paginas_lidas() == [0, 1, 2]
    assert ctl.pagina.boxes                               # a página aberta, já com os glifos


def test_ca_11_4_a_pagina_aberta_e_suja_nao_e_sobrescrita(ctl, projeto):
    p = ctl.pagina
    ctl.reconhecer([0], refazer=False)
    ctl.executor.tudo()
    projeto.descarregar(10)
    antes = _hash(projeto, 0)
    p.escolher(p.gids[0])
    p.corrigir("Z")                                       # a aberta, com um passo no desfazer
    projeto.descarregar(10)
    gravado = _hash(projeto, 0)
    assert gravado != antes
    ctl.reconhecer([0, 1], refazer=True)
    ctl.executor.tudo()
    resultado = ctl.fins[-1]
    assert resultado.reler_depois == [0] and resultado.lidas == [1]
    projeto.descarregar(10)
    assert _hash(projeto, 0) == gravado                   # o arquivo não mudou
    assert p.box(p.gids[0]).char == "Z"


def test_sem_servidor_a_edicao_espera_a_pagina_do_lote_e_vale_depois(ctl, projeto):
    """Sem servidor, a leitura do lote prende o leitor da interface: a edição pedida no meio
    entra na fila e roda depois da página (com o servidor, roda na hora, e a página vai
    para "reler depois": `tests/test_servidor_janela.py`)."""
    p = ctl.pagina
    ctl.reconhecer([0], refazer=False)
    ctl.executor.tudo()
    ctl.reconhecer([0], refazer=True)
    fim = ctl.executor.comecar()                          # o lote leu; a gravação não veio
    p.escolher(p.gids[0])
    p.corrigir("Q")                                       # não é recusada: espera a vez
    fim()
    ctl.executor.tudo()
    assert ctl.fins[-1].lidas == [0]
    assert p.box(p.gids[0]).char == "Q"


def test_ca_8_5_o_lote_pula_as_verificadas_mesmo_com_refazer(ctl, projeto):
    ctl.reconhecer([0, 1], refazer=False)
    ctl.executor.tudo()
    projeto.descarregar(10)                               # o gravador não passa por cima
    pagina = projeto.carregar_modelo(1)
    pagina.estado = VERIFICADA
    projeto.salvar_modelo(pagina)
    ctl.reconhecer([0, 1, 2], refazer=True)
    ctl.executor.tudo()
    resultado = ctl.fins[-1]
    assert resultado.verificadas == [1] and resultado.lidas == [0, 2]


def test_ca_11_5_cancelar_e_retomar_le_cada_pagina_uma_vez(ctl, projeto):
    lidas = []
    ctl.eventos.ligar("pagina_do_lote", lidas.append)
    ctl.reconhecer([0, 1, 2], refazer=True)
    fim = ctl.executor.comecar()
    fim()                                                 # a página 1 entrou
    fim = ctl.executor.comecar()                          # a 2 foi lida…
    ctl.cancelar()                                        # …e o cancelamento chega antes
    fim()                                                 # ela grava (a leitura acabou)
    ctl.executor.tudo()
    assert ctl.fins[-1].cancelado and ctl.pode_retomar
    assert ctl.restante == ([2], True)
    ctl.retomar()
    ctl.executor.tudo()
    assert lidas == [0, 1, 2] and not ctl.pode_retomar     # a união, sem repetir


def test_cancelar_no_meio_da_leitura_deixa_a_pagina_como_estava(ctl, projeto):
    ctl.reconhecer([0], refazer=False)
    ctl.executor.tudo()
    projeto.descarregar(10)
    antes = _hash(projeto, 0)
    ctl.reconhecer([0], refazer=True)
    ctl.cancelar()                                        # antes de a leitura começar
    ctl.executor.tudo()
    assert ctl.fins[-1].cancelado and ctl.fins[-1].lidas == []
    projeto.descarregar(10)
    assert _hash(projeto, 0) == antes and ctl.restante == ([0], True)


def test_ca_4_8_voltar_ao_estado_antes_do_lote_devolve_o_json_copiado(ctl, projeto):
    p = ctl.pagina
    ctl.reconhecer([0, 1], refazer=False)
    ctl.executor.tudo()
    p.ir_para(1)
    p.escolher(p.gids[0])
    p.corrigir("W")                                       # manual: o refazer o mantém (§4.6)
    projeto.descarregar(10)
    p.ir_para(0)                                          # a 1 não está aberta: o lote a relê
    copia_esperada = (projeto.pasta / "paginas" / f"p{projeto._pid_de(1)}.json").read_bytes()
    ctl.reconhecer([1], refazer=True)
    ctl.executor.tudo()
    assert ctl.fins[-1].lidas == [1]
    projeto.descarregar(10)
    pid = projeto._pid_de(1)
    copia = projeto.pasta / "paginas" / ".antes-do-lote" / f"p{pid}.json"
    assert copia.is_file()
    relida = projeto.carregar_modelo(1)
    assert any(b.entry.char == "W" and b.entry.source == FONTE_MANUAL for b in relida.boxes)
    guardado = copia.read_bytes()
    assert _sem_hora(guardado) == _sem_hora(copia_esperada)     # a página de antes do lote

    p.ir_para(1)
    assert projeto.tem_antes_do_lote(1)
    ctl.voltar_ao_antes_do_lote()
    projeto.descarregar(10)
    assert (projeto.pasta / "paginas" / f"p{pid}.json").read_bytes() == guardado
    assert not copia.exists() and not projeto.tem_antes_do_lote(1)
    assert any(b.char == "W" for b in p.boxes)
