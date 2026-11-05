"""PP1b. D-3, CA-D3: numa página nativa com diagrama, colunas e tabela, trocar uma palavra e apagar
outra faz o EPUB diferir do sem edição só nelas. C-1, CA-C1: matar a interface à força encerra o
filho em até 5 s."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import psutil
import pytest
from core.box_model import BoxEntry
from core.pagina import Figura, PaginaExtraida, Paragrafo, Tabela

from abbychess import exportar as ex
from abbychess import nativo
from abbychess.leitor import FONTE_MANUAL, FONTE_NATIVA
from abbychess.modelo import Box, Decisoes, Pagina
from abbychess.projeto import ProjetoDeLivro
from tests.ajudantes import _pdf_digital

RAIZ = Path(__file__).resolve().parent.parent


def _extraida() -> PaginaExtraida:
    figura = Figura(b"png", 10, 10, origem="render")
    return PaginaExtraida(0, [Paragrafo("uma frase de teste", inicios=[0, 4]), figura,
                              Paragrafo("outra coluna aqui", negrito=[(6, 12)]),
                              Tabela([["a b", "c"], ["d", "e f"]])])


def _pagina(*palavras) -> Pagina:
    boxes = [Box(k, BoxEntry(p, 10 * k, 0, 10 * k + 8, 8, 1.0, FONTE_NATIVA), revisado=True)
             for k, p in enumerate(palavras)]
    return Pagina(1, 0, boxes=boxes, proximo_n=len(boxes))


TODAS = "uma frase de teste outra coluna aqui a b c d e f".split()


def _textos(extraida):
    return [b.texto if isinstance(b, Paragrafo) else "figura" if isinstance(b, Figura) else b.linhas
            for b in extraida.blocos]


def test_sem_edicao_nada_muda():
    extraida = _extraida()
    antes = _textos(extraida)
    assert nativo.remendar(extraida, _pagina(*TODAS)) == []
    assert _textos(extraida) == antes


def test_trocar_uma_palavra_so_muda_ela():
    extraida = _extraida()
    palavras = list(TODAS)
    palavras[1] = "linha"
    assert nativo.remendar(extraida, _pagina(*palavras)) == []
    assert _textos(extraida)[0] == "uma linha de teste"
    assert _textos(extraida)[1] == "figura" and _textos(extraida)[2] == "outra coluna aqui"
    assert extraida.blocos[0].inicios == [0, 4]


def test_apagar_uma_palavra_sai_com_um_espaco():
    extraida = _extraida()
    palavras = [p for p in TODAS if p != "de"]
    assert nativo.remendar(extraida, _pagina(*palavras)) == []
    assert _textos(extraida)[0] == "uma frase teste"


def test_a_ultima_palavra_do_paragrafo_sai_com_o_espaco_de_antes():
    extraida = _extraida()
    palavras = [p for p in TODAS if p != "teste"]
    nativo.remendar(extraida, _pagina(*palavras))
    assert _textos(extraida)[0] == "uma frase de"


def test_na_tabela_a_troca_fica_na_celula():
    extraida = _extraida()
    palavras = list(TODAS)
    palavras[TODAS.index("f")] = "g"
    nativo.remendar(extraida, _pagina(*palavras))
    assert extraida.blocos[3].linhas == [["a b", "c"], ["d", "e g"]]


def test_inserir_vai_depois_da_palavra_anterior():
    extraida = _extraida()
    palavras = list(TODAS)
    palavras.insert(2, "nova")
    nativo.remendar(extraida, _pagina(*palavras))
    assert _textos(extraida)[0] == "uma frase nova de teste"


def test_os_trechos_de_estilo_seguem_o_texto():
    extraida = _extraida()
    palavras = list(TODAS)
    palavras[TODAS.index("outra")] = "uma-outra"
    nativo.remendar(extraida, _pagina(*palavras))
    assert _textos(extraida)[2] == "uma-outra coluna aqui"
    assert extraida.blocos[2].negrito == [(10, 16)]


def test_a_decisao_de_quebra_nao_se_aplica_e_o_relatorio_diz():
    pagina = _pagina(*TODAS)
    pagina.decisoes = Decisoes(quebras=frozenset({1}))
    avisos = nativo.remendar(_extraida(), pagina)
    assert len(avisos) == 1 and "quebra" in avisos[0]


def test_abaixo_da_similaridade_nada_se_aplica():
    extraida = _extraida()
    antes = _textos(extraida)
    avisos = nativo.remendar(extraida, _pagina("nada", "a", "ver"))
    assert _textos(extraida) == antes and "mudou demais" in avisos[0]


@pytest.fixture
def importado(tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path / "x", "Livro", _pdf_digital(tmp_path / "d.pdf", paginas=2))
    nativo.importar(projeto, [0, 1])
    yield projeto
    projeto.fechar()


def _texto_do_pdf(projeto, relatorio=None):
    relatorio = relatorio if relatorio is not None else ex.Relatorio()
    paginas = ex.paginas_do_projeto(projeto, None, relatorio=relatorio)
    return " ".join(b.texto for p in paginas for b in p.blocos if isinstance(b, Paragrafo)), relatorio


def test_ca_d3_a_exportacao_difere_so_na_palavra_trocada_e_na_apagada(importado):
    antes, _r = _texto_do_pdf(importado)
    pagina = importado.pagina_para_editar(0)
    alvo, apagar = pagina.boxes[3], pagina.boxes[5]
    pagina.boxes = [replace(b, entry=replace(b.entry, char="TROCADA", source=FONTE_MANUAL))
                    if b is alvo else b for b in pagina.boxes if b is not apagar]
    importado.salvar_modelo(pagina)
    depois, relatorio = _texto_do_pdf(importado)
    assert relatorio.da_camada == [0, 1]                  # continua saindo da camada
    assert "TROCADA" in depois and relatorio.nao_aplicadas == []
    a, b = antes.split(), depois.split()
    assert len(b) == len(a) - 1
    assert sum(x not in a for x in b) == 1


def test_a_pagina_nativa_lida_por_ocr_com_glifo_decidido_sai_dos_boxes(tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path / "x", "Livro", _pdf_digital(tmp_path / "d.pdf", paginas=1))
    try:
        pagina = projeto.pagina_para_editar(0)
        pagina.boxes = [Box(0, BoxEntry("a", 1, 1, 9, 9, 1.0, FONTE_MANUAL))]
        pagina.proximo_n = 1
        pagina.estado = "reconhecida"
        projeto.salvar_modelo(pagina)
        _, relatorio = _texto_do_pdf(projeto)
        assert relatorio.da_camada == []
    finally:
        projeto.fechar()


@pytest.mark.processo
@pytest.mark.timeout(120)
def test_ca_c1_matar_a_interface_encerra_o_filho(tmp_path):
    codigo = (
        "import sys, time\n"
        "from abbychess import servidor_de_leitura as sl\n"
        "from abbychess.dados_do_projeto import Limiares\n"
        "if __name__ == '__main__':\n"
        f"    s = sl.ServidorDeLeitura(r'{tmp_path}', Limiares(), fabrica='tests.leitor_falso:criar')\n"
        "    s.pronto.wait(60)\n"
        "    print(s.processo.pid, flush=True)\n"
        "    time.sleep(60)\n")
    ambiente = dict(os.environ, PYTHONPATH=str(RAIZ))
    arquivo = tmp_path / "interface.py"
    arquivo.write_text(codigo, encoding="utf-8")
    pai = subprocess.Popen([sys.executable, str(arquivo)], stdout=subprocess.PIPE, env=ambiente, text=True)
    filho = psutil.Process(int(pai.stdout.readline()))
    assert filho.is_running()
    pai.kill()
    pai.wait()
    inicio = time.monotonic()
    while filho.is_running() and filho.status() != psutil.STATUS_ZOMBIE and time.monotonic() - inicio < 5:
        time.sleep(0.05)
    assert not filho.is_running(), "o filho ficou órfão"
