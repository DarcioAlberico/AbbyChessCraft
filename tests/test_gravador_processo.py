"""O gravador com o processo morto no meio (camada `processo`; CA-4.2 e CA-4.4 do 2a).

Um filho (`tests/filho_do_gravador.py`) edita a página 0 sem parar e o gravador dele grava;
o teste o mata.

- CA-4.2: morto em 50 pontos sorteados (semente fixa), nenhum JSON do projeto fica
  inválido, e o projeto reabre.
- CA-4.4: com uma edição a cada 20 ms, ao reabrir estão todas as edições com carimbo
  ≤ T − 500 ms − t_fsync (T, a morte; t_fsync, a gravação da página medida aqui), com
  50 ms de folga para a volta da thread do gravador.

`time.monotonic` é do sistema no Windows (o mesmo relógio nos dois processos).
"""

from __future__ import annotations

import json
import multiprocessing
import random
import statistics
import time
from pathlib import Path

import pytest

from abbychess import gravacao as gv
from abbychess.projeto import ProjetoDeLivro

from tests.filho_do_gravador import editar_sem_parar
from tests.test_treino_por_livro import _pagina_sintetica

pytestmark = pytest.mark.processo

FOLGA_DA_THREAD = 0.05


@pytest.fixture
def pasta(tmp_path) -> Path:
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Morto",
                                   _pagina_sintetica(tmp_path / "pagina.png"))
    projeto.fechar()
    return projeto.pasta


def _iniciar(pasta: Path, registro: Path, intervalo: float, atraso: float):
    contexto = multiprocessing.get_context("spawn")
    filho = contexto.Process(target=editar_sem_parar,
                             args=(str(pasta), str(registro), intervalo, atraso), daemon=True)
    filho.start()
    fim = time.monotonic() + 60
    while (not registro.exists() or not registro.read_text(encoding="utf-8").strip()) \
            and time.monotonic() < fim:
        time.sleep(0.02)                     # o filho importou e começou a editar
    assert filho.is_alive(), "o filho morreu sozinho"
    return filho


def _matar(filho) -> float:
    morte = time.monotonic()
    filho.kill()
    filho.join(10)
    return morte


def _json_validos(pasta: Path) -> None:
    for arquivo in sorted(pasta.rglob("*.json")):
        json.loads(arquivo.read_text(encoding="utf-8"))      # falha se estiver pela metade


def test_matar_o_gravador_em_50_pontos_nao_deixa_json_invalido(pasta, tmp_path):
    sorteio = random.Random(2026)
    filho = None
    try:
        for rodada in range(50):
            # Um registro por rodada: o filho só é morto depois de editar de verdade.
            filho = _iniciar(pasta, tmp_path / f"registro{rodada}.txt", intervalo=0.002,
                             atraso=0.0)
            time.sleep(sorteio.uniform(0.0, 0.08))
            _matar(filho)
            _json_validos(pasta)
            filho = None
    finally:
        if filho is not None and filho.is_alive():
            filho.kill()
    projeto = ProjetoDeLivro.abrir(pasta)            # e o projeto abre
    try:
        assert projeto.carregar_modelo(0) is not None
    finally:
        projeto.fechar()


def _t_fsync(pasta: Path) -> float:
    """O tempo de gravar a página 0 como ela está (mediana de 10)."""
    arquivo = next((pasta / "paginas").glob("p*.json"))
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    tempos = []
    for _ in range(10):
        inicio = time.perf_counter()
        gv.gravar_json(pasta / "medida-do-fsync.json", dados)
        tempos.append(time.perf_counter() - inicio)
    (pasta / "medida-do-fsync.json").unlink()
    return statistics.median(tempos)


@pytest.mark.parametrize("vida", [1.5, 2.3, 3.1])
def test_edicoes_mais_velhas_que_o_atraso_sobrevivem_a_morte(pasta, tmp_path, vida, record_property):
    registro = tmp_path / "registro.txt"
    filho = _iniciar(pasta, registro, intervalo=0.02, atraso=0.5)
    try:
        time.sleep(vida)
    finally:
        morte = _matar(filho)
    carimbos = {}
    for linha in registro.read_text(encoding="utf-8").splitlines():
        k, t = linha.split()
        carimbos[k] = float(t)
    t_fsync = _t_fsync(pasta)
    record_property("t_fsync_ms", round(t_fsync * 1000, 2))
    limite = morte - 0.5 - t_fsync - FOLGA_DA_THREAD
    projeto = ProjetoDeLivro.abrir(pasta)
    try:
        gravados = {v.char for v in projeto.carregar_modelo(0).decisoes.virtuais}
    finally:
        projeto.fechar()
    devidos = {k for k, t in carimbos.items() if t <= limite}
    assert devidos, "o filho não viveu o bastante para o teste dizer algo"
    assert devidos <= gravados, sorted(devidos - gravados, key=int)[:5]
    print(f"t_fsync = {t_fsync * 1000:.1f} ms; {len(devidos)} edições devidas, "
          f"{len(gravados)} gravadas de {len(carimbos)}")
