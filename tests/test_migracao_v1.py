"""CA-4.1 e CA-4.5: o projeto v1 de `tests/dados/projeto_v1` abre pela versão 2 sem perder nada.

A fixture foi gravada pelo programa da tag `passo-1a` (o formato v1 de verdade): três
páginas (a 1 sem a chave `tabuleiros`, a 2 com um diagrama, a 3 só com glifos marcados à
mão, em `marcadas.json`), as áreas da 1 em `zonas/`, `inclinacoes.json`, um padrão ensinado e
um campo de `projeto.json` que o programa não conhece.

A verdade é lida direto dos arquivos v1, sem o código do programa, e comparada campo a
campo com o que a versão 2 devolve depois de migrar, de gravar e de reabrir.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from abbychess import gravacao as gv
from abbychess.modelo import gid_de
from abbychess.projeto import PASTA_DO_BACKUP_V1, VERSAO, ProjetoDeLivro

FIXTURE = Path(__file__).parent / "dados" / "projeto_v1"


@pytest.fixture
def projeto_v1(tmp_path) -> Path:
    destino = tmp_path / "fixture-v1"
    shutil.copytree(FIXTURE, destino)
    return destino


def _verdade_v1(pasta: Path) -> dict:
    """O conteúdo do projeto v1, lido dos arquivos."""
    paginas = {}
    for arquivo in sorted((pasta / "paginas").glob("[0-9]*.json")):
        bruto = json.loads(arquivo.read_text(encoding="utf-8"))
        paginas[int(arquivo.stem) - 1] = {
            "boxes": [list(b) for b in bruto["boxes"]],
            "tabuleiros": [list(t) for t in bruto.get("tabuleiros", [])],
            "diagramas": bruto.get("diagramas", [])}
    zonas = {}
    for arquivo in sorted((pasta / "zonas").glob("*.json")):
        bruto = json.loads(arquivo.read_text(encoding="utf-8"))
        zonas[int(arquivo.stem) - 1] = [(z["tipo"], z["caixa"]) for z in bruto["zonas"]]
    return {"paginas": paginas, "zonas": zonas,
            "marcadas": {int(i) - 1 for i in json.loads(
                (pasta / "paginas" / "marcadas.json").read_text(encoding="utf-8"))},
            "inclinacoes": (pasta / "inclinacoes.json").read_bytes(),
            "padroes": {p.relative_to(pasta).as_posix(): p.read_bytes()
                        for p in (pasta / "padroes").rglob("*") if p.is_file()},
            "projeto": json.loads((pasta / "projeto.json").read_text(encoding="utf-8"))}


def _conferir(projeto: ProjetoDeLivro, verdade: dict) -> None:
    """Campo a campo: boxes, tabuleiros, diagramas, áreas, marcadas, inclinação e padrões."""
    for indice, pagina in verdade["paginas"].items():
        boxes = projeto.carregar_pagina(indice)
        assert [list(b.as_state()) for b in boxes] == pagina["boxes"], indice
        assert [list(t) for t in projeto.carregar_tabuleiros(indice)] == pagina["tabuleiros"]
        # Os campos que o v1 não tinha (`titulo_do_core`, `lados_de_rotulo`) nascem do padrão.
        gravados = [{k: v for k, v in d.para_json().items() if k in esperado}
                    for d, esperado in zip(projeto.carregar_diagramas(indice),
                                           pagina["diagramas"])]
        assert len(gravados) == len(pagina["diagramas"]), indice
        assert gravados == pagina["diagramas"], indice
        assert projeto.pagina_reconhecida(indice) == (indice not in verdade["marcadas"])
        zonas = [(z.tipo, list(z.caixa)) for z in projeto.carregar_zonas(indice)]
        assert zonas == verdade["zonas"].get(indice, []), indice
    assert (projeto.pasta / "inclinacoes.json").read_bytes() == verdade["inclinacoes"]
    padroes = {p.relative_to(projeto.pasta).as_posix(): p.read_bytes()
               for p in (projeto.pasta / "padroes").rglob("*") if p.is_file()}
    assert padroes == verdade["padroes"]
    assert projeto.dados.extras["campo_do_futuro"] == verdade["projeto"]["campo_do_futuro"]


def test_a_fixture_e_mesmo_v1():
    verdade = _verdade_v1(FIXTURE)
    assert verdade["projeto"]["versao"] == 1
    assert "tabuleiros" not in json.loads((FIXTURE / "paginas" / "0001.json").read_text("utf-8"))
    assert verdade["marcadas"] and verdade["zonas"] and verdade["padroes"]
    assert any(p["diagramas"] for p in verdade["paginas"].values())


def test_abre_migra_grava_e_reabre_sem_perder_nada(projeto_v1):
    verdade = _verdade_v1(projeto_v1)
    original = (projeto_v1 / "projeto.json").read_bytes()
    projeto = ProjetoDeLivro.abrir(projeto_v1)
    assert projeto.dados.versao == VERSAO
    assert (projeto_v1 / PASTA_DO_BACKUP_V1 / "projeto.json").read_bytes() == original
    for nome in ("paginas/0001.json", "paginas/0002.json", "paginas/0003.json",
                 "paginas/marcadas.json", "zonas/0001.json"):
        assert (projeto_v1 / PASTA_DO_BACKUP_V1 / nome).read_bytes() == (FIXTURE / nome).read_bytes()
    _conferir(projeto, verdade)

    # Cada página migrada foi gravada (v2) e o v1 dela saiu de `paginas/` e `zonas/`.
    assert sorted(p.name for p in (projeto_v1 / "paginas").glob("*.json")) == [
        "marcadas.json", "p0.json", "p1.json", "p2.json"]
    assert not list((projeto_v1 / "zonas").glob("*.json"))
    assert [b.gid for b in projeto.carregar_modelo(0).boxes][:3] == [gid_de(0, n) for n in range(3)]
    assert projeto.estado_da_pagina(2) == "glifos_marcados"

    for indice in verdade["paginas"]:              # gravar sem mudar nada
        projeto.salvar_pagina(indice, projeto.carregar_pagina(indice),
                              projeto.carregar_tabuleiros(indice),
                              reconhecida=projeto.pagina_reconhecida(indice))
    _conferir(ProjetoDeLivro.abrir(projeto_v1), verdade)


def _instantaneo(pasta: Path) -> dict:
    return {str(p.relative_to(pasta)): (p.stat().st_mtime_ns,
                                        hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(pasta.rglob("*")) if p.is_file()}


def test_versao_99_abre_so_para_leitura_e_nenhum_arquivo_muda(projeto_v1):
    arquivo = projeto_v1 / "projeto.json"
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    dados["versao"] = 99
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    antes = _instantaneo(projeto_v1)
    projeto = ProjetoDeLivro.abrir(projeto_v1)
    try:
        assert projeto.somente_leitura
        for indice in range(3):                    # ler as páginas v1 não migra nada
            projeto.carregar_pagina(indice)
            projeto.carregar_zonas(indice)
        assert projeto.paginas_lidas() == [0, 1]
        assert _instantaneo(projeto_v1) == antes
        assert not (projeto_v1 / PASTA_DO_BACKUP_V1).exists()
    finally:
        projeto.fechar()
    assert not gv.protegida(projeto_v1)


def test_copiar_o_backup_v1_de_volta_reabre_pela_versao_de_hoje(projeto_v1):
    """CA-4.5: o backup copiado por cima do projeto migrado volta a ser o projeto."""
    verdade = _verdade_v1(projeto_v1)
    projeto = ProjetoDeLivro.abrir(projeto_v1)
    projeto.migrar_tudo()
    projeto.salvar_pagina(0, projeto.carregar_pagina(0)[:2], reconhecida=True)   # muda a 0
    backup = projeto_v1 / PASTA_DO_BACKUP_V1
    for arquivo in backup.rglob("*"):
        if arquivo.is_file():
            destino = projeto_v1 / arquivo.relative_to(backup)
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(arquivo, destino)
    _conferir(ProjetoDeLivro.abrir(projeto_v1), verdade)


def test_volta_do_backup_com_pagina_nova_nao_repete_gid(projeto_v1):
    projeto = ProjetoDeLivro.abrir(projeto_v1)
    projeto.migrar_tudo()
    from core.box_model import BoxEntry

    projeto.salvar_pagina(5, [BoxEntry("a", 0, 0, 10, 10)])         # uma página nova: pid 3
    nova = projeto.carregar_modelo(5)
    assert nova.pid >= 3
    backup = projeto_v1 / PASTA_DO_BACKUP_V1
    for arquivo in backup.rglob("*"):
        if arquivo.is_file():
            destino = projeto_v1 / arquivo.relative_to(backup)
            shutil.copyfile(arquivo, destino)
    reaberto = ProjetoDeLivro.abrir(projeto_v1)
    reaberto.migrar_tudo()
    pids = [reaberto.carregar_modelo(i).pid for i in (0, 1, 2, 5)]
    assert len(set(pids)) == 4 and reaberto.dados.proximo_pid > max(pids)
    gids = [b.gid for i in (0, 1, 2, 5) for b in reaberto.carregar_modelo(i).boxes]
    assert len(gids) == len(set(gids))


def test_v1_em_midia_so_de_leitura_abre_so_para_leitura(projeto_v1, monkeypatch):
    def recusar(*_args):
        raise PermissionError("mídia só de leitura")

    monkeypatch.setattr(gv, "gravar_bytes", recusar)
    projeto = ProjetoDeLivro.abrir(projeto_v1)
    try:
        assert projeto.somente_leitura and not projeto.migrado
        assert "não deu para gravar" in projeto.motivo_so_leitura
        assert projeto.carregar_pagina(0) is not None          # as páginas v1 aparecem
    finally:
        projeto.fechar()


def test_a_abertura_que_migra_avisa(projeto_v1):
    assert ProjetoDeLivro.abrir(projeto_v1).migrado
    assert not ProjetoDeLivro.abrir(projeto_v1).migrado          # só da primeira vez
