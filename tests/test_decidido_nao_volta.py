"""D-5, CA-D5: glifo `neural` revisado, confiança 0,5, padrão que o lê diferente: Enter, Ctrl+R e
a propagação não o trocam (Princípio 5: decidido não volta). Com os dois caminhos do Ctrl+R: no
processo e pelo servidor."""

from __future__ import annotations

import pytest
from core.box_model import BoxEntry
from PIL import Image

from abbychess import contexto
from abbychess import pagina as pg
from abbychess.leitor import FONTE_MANUAL
from abbychess.modelo import Box, Pagina, gid_de
from abbychess.projeto import ProjetoDeLivro
from tests.ajudantes import ExecutorManual, _controlador, _pagina_sintetica
from tests.servidor_falso import ServidorFalso


class _LeitorQueLeOutraCoisa:
    """Lê todo recorte como `x`, pelo livro, com confiança alta."""

    def __init__(self, limiares):
        self.limiares = limiares

    def ler_pelo_livro(self, *_a, **_k):
        from abbychess.leitor import Leitura

        return Leitura("x", "livro", 0.99)

    def para_propagar(self):
        return self


def _o_revisado(ctl) -> Box:
    return next(b for b in ctl.modelo.boxes if b.revisado)


@pytest.fixture
def projeto(tmp_path):
    p = ProjetoDeLivro.criar(tmp_path, "Livro", _pagina_sintetica(tmp_path / "p.png"))
    yield p
    p.fechar()


def _pagina_com_um_revisado(projeto) -> Pagina:
    """Dois glifos `neural` a 0,5: o primeiro revisado, o segundo não."""
    pagina = Pagina(pid=0, indice=0, boxes=[
        Box(gid_de(0, 0), BoxEntry("a", 10, 10, 30, 30, 0.5, "neural"), revisado=True),
        Box(gid_de(0, 1), BoxEntry("b", 40, 10, 60, 30, 0.5, "neural"))], proximo_n=2)
    projeto.salvar_modelo(pagina)
    return pagina


def _estado(box: Box) -> tuple:
    return box.entry.char, box.entry.source, box.entry.confidence


def test_o_pendente_da_pagina_nao_conta_o_revisado(projeto):
    pagina = _pagina_com_um_revisado(projeto)
    assert contexto.pendentes_da_pagina(pagina, projeto.dados.limiares) == [False, True]


def test_a_leitura_com_nao_ler_nao_toca_nele():
    class Leitor:
        limiares = None

        @staticmethod
        def ler(*_a, **_k):
            raise AssertionError("não devia ler")

    boxes = [BoxEntry("a", 1, 1, 9, 9, 0.5, "neural")]
    assert pg._alvos_da_leitura(boxes, False, None, nao_ler=[0]) == []
    assert pg._alvos_da_leitura(boxes, False, None) == boxes


def test_ca_d5_o_ctrl_r_nao_troca_o_revisado(projeto):
    _pagina_com_um_revisado(projeto)
    executor = ExecutorManual()
    ctl = _controlador(projeto, executor)
    executor.tudo()
    ctl.leitor.ler = lambda *a, **k: _uma_leitura("x")
    antes = _estado(_o_revisado(ctl))
    ctl.leitura.reler_pendentes()
    executor.tudo()
    assert _estado(_o_revisado(ctl)) == antes
    assert next(b for b in ctl.modelo.boxes if not b.revisado).entry.char == "x"


def _uma_leitura(char):
    from abbychess.leitor import Leitura

    return Leitura(char, "livro", 0.99)


def test_ca_d5_o_ctrl_r_pelo_servidor_nao_troca_o_revisado(projeto, monkeypatch):
    _pagina_com_um_revisado(projeto)
    executor = ExecutorManual()
    ctl = _controlador(projeto, executor)
    executor.tudo()
    servidor = ServidorFalso(projeto.pasta_de_padroes, projeto.dados.limiares)
    servidor.leitor.ler = lambda *a, **k: _uma_leitura("x")
    monkeypatch.setattr(ctl.leitura, "servidor_para_pedir", lambda: servidor)
    monkeypatch.setattr(ctl.leitura, "servidor_parado", lambda: False)
    antes = _estado(_o_revisado(ctl))
    ctl.leitura.reler_pendentes()
    executor.tudo()
    assert _estado(_o_revisado(ctl)) == antes
    assert next(b for b in ctl.modelo.boxes if not b.revisado).entry.char == "x"


def test_ca_d5_a_propagacao_nao_troca_o_revisado(projeto):
    from abbychess import historico as hs

    pagina = _pagina_com_um_revisado(projeto)
    executor = ExecutorManual()
    ctl = _controlador(projeto, executor)
    executor.tudo()
    ctl.leitor.para_propagar = lambda: _LeitorQueLeOutraCoisa(ctl.leitor.limiares)
    modelo = ctl.modelo
    antes = _estado(_o_revisado(ctl))
    transacao = hs.Transacao("Ensinar", {pagina.pid: hs.mudanca(modelo.instantaneo(),
                                                                modelo.instantaneo())})
    ctl.leitura.propagar(modelo, 0, transacao, None)
    executor.tudo()
    assert _estado(_o_revisado(ctl)) == antes
    assert next(b for b in ctl.modelo.boxes if not b.revisado).entry.char == "x"


def test_o_manual_continua_sem_ser_relido():
    boxes = [BoxEntry("a", 1, 1, 9, 9, 1.0, FONTE_MANUAL)]
    assert pg._alvos_da_leitura(boxes, False, None) == []


def test_propagar_no_lugar_sem_pendentes_continua_igual():
    """O caminho das ferramentas (`replay_fatia`): sem a página, os pendentes de sempre."""
    boxes = [BoxEntry("a", 1, 1, 9, 9, 0.5, "neural")]
    leitor = _LeitorQueLeOutraCoisa(None)
    from abbychess.dados_do_projeto import Limiares

    leitor.limiares = Limiares()
    assert pg.propagar_padroes(Image.new("L", (20, 20), 255), boxes, leitor) == 1
    assert boxes[0].char == "x"
