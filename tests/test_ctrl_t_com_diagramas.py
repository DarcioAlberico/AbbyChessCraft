"""CA-U5b (SPEC-pagina-perfeita, U-5b; T1, bloco 4): a pergunta do Ctrl+T conta os diagramas
por conferir da página.

Antes, ela contava só os glifos e os lances: a página ficava ✓ com um diagrama por conferir.
O diagrama que falhou na leitura não tem posição a conferir e não conta, como no F8 (U-5a).
"""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from abbychess.controlador_de_diagramas import ControladorDeDiagramas  # noqa: E402

from tests.ajudantes import _lido  # noqa: E402
from tests.fixturas_espaco import janela  # noqa: E402,F401,F811


def _conferencia(diagramas):
    pagina = SimpleNamespace(eventos=SimpleNamespace(ligar=lambda *_a: None), diagramas=diagramas)
    return ControladorDeDiagramas(pagina)


def test_conta_os_por_conferir_sem_o_que_falhou_nem_o_conferido():
    diagramas = [_lido(), _lido(conferido=True), _lido(erro="a leitura falhou"), _lido()]
    assert _conferencia(diagramas).por_conferir_na_pagina() == 2
    assert _conferencia([]).por_conferir_na_pagina() == 0


def test_o_ctrl_t_so_com_diagrama_pergunta(app, janela, monkeypatch):  # noqa: F811
    j = janela
    monkeypatch.setattr(j.pagina.fila_da_pagina, "fila", lambda: [])
    monkeypatch.setattr(j.fila.lances, "resumo_da_pagina", lambda: {"nao_conferidos": 0})
    monkeypatch.setattr(j.conferencia, "por_conferir_na_pagina", lambda: 1)
    j.verificar_pagina()
    assert j.confirmacao.aberta
    assert j.confirmacao.pergunta.text() == ("Marcar verificada? 1 diagrama por conferir. "
                                             "Enter aceita · Esc não marca")
    j.confirmacao._fechar()
    assert j.pagina.modelo is None or j.pagina.modelo.estado != "verificada"


def test_o_ctrl_t_cita_os_lances_e_os_diagramas(app, janela, monkeypatch):  # noqa: F811
    """As dúvidas dos glifos na mesma frase já são de `test_fila_lances.py` (CA-F4.9)."""
    j = janela
    monkeypatch.setattr(j.fila.lances, "resumo_da_pagina", lambda: {"nao_conferidos": 2})
    monkeypatch.setattr(j.conferencia, "por_conferir_na_pagina", lambda: 2)
    j.verificar_pagina()
    assert j.confirmacao.pergunta.text() == ("Marcar verificada? 2 lances não conferidos. "
                                             "2 diagramas por conferir. Enter aceita · Esc não marca")
    j.confirmacao._fechar()
