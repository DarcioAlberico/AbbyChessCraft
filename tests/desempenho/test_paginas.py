r"""As operações de página no livro inteiro (SPEC §12.4, passo L), sobre o livro sintético de
230 páginas com o texto da fatia do Xadrez Vitorioso, todas lidas, num PDF com páginas do
tamanho das da fatia (os glifos caem dentro delas):

    .venv\Scripts\python.exe -m pytest -q -m desempenho tests\desempenho\test_paginas.py

Medidos, sem alvo na SPEC (o §1 pede a interface que não trava): dividir as 230 páginas e o
Ctrl+Z (gravam as páginas inteiras com a sequência), girar as 230 e o Ctrl+Z (só a sequência
e o gravador), e girar uma página (o gesto de um clique), tudo na thread da interface.
"""

from __future__ import annotations

import time

import pytest

from tests.desempenho.conftest import cronometrar
from tests.desempenho.test_busca import PAGINAS
from tests.desempenho.test_substituir import _livro_de_230

pytestmark = [pytest.mark.desempenho, pytest.mark.timeout(900)]


def _segundos(funcao) -> float:
    inicio = time.perf_counter()
    assert funcao() is not False
    return time.perf_counter() - inicio


def test_dividir_e_girar_o_livro_inteiro(tmp_path, medidas):
    from abbychess import pagina as pg
    from abbychess.controlador import ControladorDePagina
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro
    from tests.test_controlador import ExecutorManual

    projeto = _livro_de_230(tmp_path, pdf_do_tamanho_da_fatia=True)
    try:
        ctl = ControladorDePagina(executar=ExecutorManual())
        ctl.ligar(projeto, pg.fonte_do_projeto(projeto),     # a fonte como o programa a abre
                  LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
        ctl.ir_para(0)
        todas, total = list(range(PAGINAS)), len(projeto.sequencia)   # o PDF tem uma a mais
        dividir = _segundos(lambda: ctl.dividir_paginas(todas))
        assert len(projeto.sequencia) == total + PAGINAS
        desfazer_dividir = _segundos(ctl.desfazer)
        assert len(projeto.sequencia) == total
        girar = _segundos(lambda: ctl.girar_paginas(todas, 90))
        desfazer_girar = _segundos(ctl.desfazer)
        assert projeto.sequencia.entrada_em(0).giro == 0
        assert projeto.descarregar(120)

        def um_giro(i):
            ctl.girar_paginas([3], 90 if i % 2 == 0 else 270)

        uma = cronometrar(um_giro)
    finally:
        projeto.fechar()
    # O caso comum: o livro escaneado espelhado é dividido antes de ler (nada a gravar).
    novo = ProjetoDeLivro.criar(tmp_path / "antes", "Sem leitura", projeto.fonte)
    try:
        ctl = ControladorDePagina(executar=ExecutorManual())
        ctl.ligar(novo, pg.fonte_do_projeto(novo),
                  LeitorDoLivro(novo.pasta_de_padroes, limiares=novo.dados.limiares))
        ctl.ir_para(0)
        sem_leitura = _segundos(lambda: ctl.dividir_paginas(list(range(len(novo.sequencia)))))
    finally:
        novo.fechar()
    medidas["paginas_no_livro"] = {
        "paginas": PAGINAS, "dividir_ms": round(dividir * 1000),
        "desfazer_dividir_ms": round(desfazer_dividir * 1000),
        "dividir_sem_leitura_ms": round(sem_leitura * 1000),
        "girar_ms": round(girar * 1000), "desfazer_girar_ms": round(desfazer_girar * 1000),
        "girar_uma_p95_ms": uma["p95_ms"], "girar_uma_p50_ms": uma["p50_ms"]}
