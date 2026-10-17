r"""Substituir no livro inteiro (SPEC §7.2, passo D2), sobre um livro sintético de 230 páginas
com o texto da fatia do Xadrez Vitorioso.

    .venv\Scripts\python.exe -m pytest -q -m desempenho tests\desempenho\test_substituir.py

- CA-7.2: Substituir todas nas 230 páginas e um Ctrl+Z volta todas (e o Ctrl+Y as refaz).
  Medidos, sem alvo na SPEC: a prévia (numa thread), editar as cópias (na thread do
  executor), trocar as páginas e registrar a transação (na thread da interface: o tempo em
  que a janela fica presa) e o desfazer.
"""

from __future__ import annotations

import time
import zipfile
from dataclasses import replace

import pytest

from abbychess import busca as bs
from abbychess import historico as hs
from abbychess import substituir as sb

from tests.desempenho.test_busca import PAGINAS, SNAPSHOT

pytestmark = [pytest.mark.desempenho, pytest.mark.timeout(900)]


def _livro_de_230(pasta):
    """Um projeto com um PDF sintético de 231 páginas e 230 delas com os glifos das 7 da
    fatia (cada cópia com pid e gids próprios)."""
    from abbychess.modelo import Box, Decisoes, gid_de
    from abbychess.projeto import ProjetoDeLivro
    from tests.test_livro import PAGINAS as LINHAS, pdf_sintetico

    with zipfile.ZipFile(SNAPSHOT) as z:
        z.extractall(pasta / "fatia")
    fatia = ProjetoDeLivro.abrir(next(p.parent for p in (pasta / "fatia").rglob("projeto.json")))
    try:
        modelos = [fatia.carregar_modelo(i) for i in fatia.paginas_lidas()]
    finally:
        fatia.fechar()
    projeto = ProjetoDeLivro.criar(pasta / "livros", "Sintético",
                                   pdf_sintetico(pasta, LINHAS * 77))
    for k in range(PAGINAS):
        molde = modelos[k % len(modelos)]
        pagina = projeto.pagina_para_editar(k)
        pagina.boxes = [Box(gid_de(pagina.pid, n), b.entry, b.amostra, b.estilo, b.revisado)
                        for n, b in enumerate(molde.boxes)]
        pagina.proximo_n = len(pagina.boxes)
        pagina.decisoes = Decisoes()
        pagina.diagramas = [replace(d) for d in molde.diagramas]
        pagina.estado = molde.estado
        projeto.salvar_modelo(pagina)
    assert projeto.descarregar(60)
    return projeto


def _esperar(condicao, limite=120.0):
    fim = time.monotonic() + limite
    while not condicao() and time.monotonic() < fim:
        time.sleep(0.01)
    assert condicao()


def test_ca_7_2_substituir_todas_no_livro_e_um_ctrl_z(tmp_path, medidas):
    from abbychess.controladores import ControladorDaBusca, ControladorDaSubstituicao
    from tests.test_controlador import ExecutorManual, _controlador

    projeto = _livro_de_230(tmp_path)
    try:
        executor = ExecutorManual()
        ctl = _controlador(projeto, executor)
        busca = ControladorDaBusca(ctl, paralelo=False)
        sub = ControladorDaSubstituicao(ctl, busca)
        previas, feitas = [], []
        ctl.eventos.ligar("previa_pronta", previas.append)
        ctl.eventos.ligar("substituicao_feita", lambda *a: feitas.append(a))
        originais = {i: projeto.carregar_modelo(i).instantaneo() for i in range(PAGINAS)}

        inicio = time.perf_counter()
        assert sub.previa(bs.Opcoes("e", maiusculas=True), "E", sb.PROSA)
        _esperar(lambda: previas)
        t_previa = time.perf_counter() - inicio
        aceitos = {p.indice: [c for c in p.casos if c.aplicavel] for p in previas[0]}
        casos = sum(len(c) for c in aceitos.values())
        assert len(aceitos) == PAGINAS and casos > 10 * PAGINAS

        sub.aplicar(aceitos, "Substituir")
        inicio = time.perf_counter()
        fim = executor.comecar()                         # as cópias, na thread do executor
        t_copias = time.perf_counter() - inicio
        inicio = time.perf_counter()
        fim()                                            # trocar e registrar, na interface
        t_trocar = time.perf_counter() - inicio
        assert feitas[-1][:2] == (casos, PAGINAS) and not feitas[-1][2]
        transacao = ctl.historico.proxima_a_desfazer()
        assert len(transacao.paginas) == PAGINAS          # uma transação só

        inicio = time.perf_counter()
        ctl.desfazer()                                    # um Ctrl+Z
        executor.tudo()
        t_desfazer = time.perf_counter() - inicio
        for i in range(PAGINAS):                          # todas voltaram
            agora = projeto.carregar_modelo(i)
            assert all(hs.igual(a, b) for a, b in zip(agora.boxes, originais[i].boxes))
            assert len(agora.boxes) == len(originais[i].boxes)
        ctl.refazer()
        executor.tudo()
        assert sum(1 for i in range(PAGINAS)
                   if any(b.entry.char == "E" for b in projeto.carregar_modelo(i).boxes)) == PAGINAS
    finally:
        projeto.fechar()
    medidas["substituir_no_livro"] = {
        "paginas": PAGINAS, "casos": casos, "previa_s": round(t_previa, 2),
        "copias_s": round(t_copias, 2), "trocar_na_interface_ms": round(t_trocar * 1000),
        "desfazer_ms": round(t_desfazer * 1000),
        "como": "'e' -> 'E' (Aa ligado, Prosa) nas 230 páginas: a prévia numa thread, as cópias "
                "na thread do executor, trocar as páginas e registrar a transação na interface, "
                "e um Ctrl+Z (sem alvo na SPEC; o CA-7.2 é que um Ctrl+Z volta todas)"}
