r"""As metas de Localizar (SPEC §7.1, §7.3, passo B), sobre a fatia do Xadrez Vitorioso.

    .venv\Scripts\python.exe -m pytest -q -m desempenho tests\desempenho\test_busca.py

- CA-7.1 [desempenho]: 230 páginas (as 7 da fatia repetidas, sem OCR): montar o índice
  (p95 ≤ 2 s, em processos, como ao abrir o projeto) e `(?<=\w)1(?=\w)` no livro (p95 ≤ 1 s),
  com o mesmo que o `re` acha no texto concatenado e cada resultado no gid certo;
- CA-7.3 [desempenho]: o atraso de um `QTimer` de 16 ms durante uma busca longa (p99 < 100 ms).

O portão (`alvo × 1,2`) só reprova na máquina de `docs/medidas/maquina.json`.
"""

from __future__ import annotations

import json
import re
import tempfile
import threading
import time
import zipfile
from pathlib import Path

import pytest

from abbychess import busca as bs

from tests.desempenho.conftest import cronometrar, na_maquina_cadastrada, percentil

pytestmark = [pytest.mark.desempenho, pytest.mark.timeout(900)]

RAIZ = Path(__file__).resolve().parent.parent.parent
SNAPSHOT = RAIZ / "tests" / "dados" / "fatia" / "xv-i020-026-inicial.zip"
PAGINAS = 230
PADRAO = r"(?<=\w)1(?=\w)"


@pytest.fixture(scope="module")
def livro_de_230():
    """Os JSON v2 das 7 páginas da fatia, copiados até 230 (cada cópia com o índice dela)."""
    from abbychess.projeto import ProjetoDeLivro

    pasta = Path(tempfile.mkdtemp())
    with zipfile.ZipFile(SNAPSHOT) as z:
        z.extractall(pasta / "fatia")
    projeto = ProjetoDeLivro.abrir(next(p.parent for p in (pasta / "fatia").rglob("projeto.json")))
    try:
        lidas = projeto.paginas_lidas()
        for i in lidas:
            projeto.carregar_modelo(i)                # a migração para o v2
        assert projeto.descarregar(30)
        originais = [json.loads(projeto.arquivo_da_pagina(i).read_text(encoding="utf-8"))
                     for i in lidas]
    finally:
        projeto.fechar()
    arquivos = {}
    for k in range(PAGINAS):
        bruto = dict(originais[k % len(originais)], indice=k)
        caminho = pasta / "livro" / f"p{k:04d}.json"
        caminho.parent.mkdir(exist_ok=True)
        caminho.write_text(json.dumps(bruto), encoding="utf-8")
        arquivos[k] = (str(caminho), 0)
    return arquivos


def _portao(valor: float, alvo: float) -> None:
    if na_maquina_cadastrada():
        assert valor <= alvo * 1.2, f"{valor} > {alvo} × 1,2"


def test_ca_7_1_montar_o_indice(livro_de_230, medidas):
    resultado = cronometrar(lambda _i: bs.construir(livro_de_230, "pt", paralelo=True),
                            aquecimentos=1, repeticoes=5)
    medidas["montar_indice_da_busca"] = {
        **resultado, "paginas": PAGINAS, "processos": bs.processos_para_indexar(),
        "alvo_p95_ms": 2000,
        "como": "as 7 páginas da fatia (JSON v2) copiadas até 230, montadas por "
                "`busca.construir` num pool de processos aberto a cada vez (o programa o "
                "abre ao abrir o projeto); inclui abrir os processos"}
    _portao(resultado["p95_ms"], 2000)


def test_ca_7_1_buscar_no_livro(livro_de_230, medidas):
    indice = bs.construir(livro_de_230, "pt", paralelo=True)
    assert len(indice) == PAGINAS
    opcoes = bs.Opcoes(PADRAO, regex=True, maiusculas=True)
    resultado = cronometrar(lambda _i: bs.buscar(indice, opcoes))
    achadas = bs.buscar(indice, opcoes).ocorrencias
    # O mesmo que o `re` acha no texto concatenado (as páginas separadas por "\n").
    deslocamento, esperado = {}, []
    concatenado = ""
    for k in sorted(indice):
        deslocamento[k] = len(concatenado)
        concatenado += indice[k].texto + "\n"
    esperado = [m.start() for m in re.finditer(PADRAO, concatenado)]
    assert [deslocamento[o.pagina] + o.inicio for o in achadas] == esperado
    for o in achadas:                                   # cada resultado leva ao gid certo
        if o.etiqueta != bs.FEN:                        # (o FEN do diagrama não tem gid)
            assert o.gids == (indice[o.pagina].gids[o.inicio],)
    medidas["buscar_regex_no_livro"] = {
        **resultado, "paginas": PAGINAS, "ocorrencias": len(achadas), "alvo_p95_ms": 1000,
        "como": f"`busca.buscar` de {PADRAO!r} no índice de {PAGINAS} páginas, na thread do "
                "teste; o resultado igual ao do `re` no texto concatenado"}
    _portao(resultado["p95_ms"], 1000)


def test_ca_7_3_a_janela_responde_durante_a_busca(livro_de_230, medidas):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    indice = bs.construir(livro_de_230, "pt", paralelo=True)
    # Uma busca longa (sem estourar o tempo-limite): palavras de 3 letras ou mais seguidas.
    opcoes = bs.Opcoes(r"(?:\w{3,}\s+){2,}\w+", regex=True)
    atrasos, ultimo = [], [time.perf_counter()]

    def tique():
        agora = time.perf_counter()
        atrasos.append((agora - ultimo[0]) * 1000 - 16)
        ultimo[0] = agora

    relogio = QTimer()
    relogio.setInterval(16)
    relogio.timeout.connect(tique)
    feito = threading.Event()
    voltas = []

    def buscar():
        inicio = time.perf_counter()
        for _ in range(40):
            bs.buscar(indice, opcoes)
        voltas.append(time.perf_counter() - inicio)
        feito.set()

    relogio.start()
    ultimo[0] = time.perf_counter()
    threading.Thread(target=buscar, daemon=True).start()
    while not feito.is_set():
        app.processEvents()
        time.sleep(0.001)
    relogio.stop()
    p99 = round(percentil(atrasos, 0.99), 1)
    medidas["atraso_durante_a_busca"] = {
        "p99_ms": p99, "max_ms": round(max(atrasos), 1), "disparos": len(atrasos),
        "duracao_s": round(voltas[0], 2), "alvo_p99_ms": 100,
        "como": "um QTimer de 16 ms na thread da interface enquanto outra thread busca "
                f"{opcoes.texto!r} 40 vezes seguidas no índice de {PAGINAS} páginas"}
    _portao(p99, 100)
