"""CA-12.7: a migração da v2 à v3 (SPEC §12.4, passo L, rodada 1e). A sequência do livro vai
para o `projeto.json`, toda página ganha `pid` gravado, e as inclinações, `janela.json`,
`lote.json` e as listas de páginas do projeto passam a `pid`.

O projeto v2 é montado à mão, como a v2 o gravava: sem a sequência, uma página com `pid`
diferente do índice, uma página v1 ainda não migrada, e tudo o mais por índice do PDF."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from abbychess import gravacao as gv
from abbychess import livro
from abbychess import pagina as pg
from abbychess.modelo import gid_de
from abbychess.projeto import ProjetoDeLivro

from tests.test_visor import pdf_de_60_paginas  # noqa: F401

ESTADO = ["a", 1, 1, 5, 5, 1.0, "manual", 0, False, -1.0, False]


def _json(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


def _gravar(caminho, dados):
    caminho.write_text(json.dumps(dados), encoding="utf-8")


@pytest.fixture
def projeto_v2(tmp_path, pdf_de_60_paginas):  # noqa: F811
    from core.box_model import BoxEntry

    novo = ProjetoDeLivro.criar(tmp_path / "livros", "Migrar", pdf_de_60_paginas)
    for indice in (0, 1, 2):
        novo.salvar_pagina(indice, [BoxEntry.from_state(tuple(ESTADO))])
    assert novo.fechar(10)
    pasta, paginas = novo.pasta, novo.pasta / "paginas"
    # A página 2 com o pid 40 (a v2 dava o pid na ordem da primeira edição).
    bruto = _json(paginas / "p1.json")
    bruto.update(pid=40, boxes=[[gid_de(40, 0), ESTADO, None, [0, 0, 0], 0]])
    _gravar(paginas / "p40.json", bruto)
    (paginas / "p1.json").unlink()
    (paginas / "p2.json").unlink()
    # A página 8 ainda na v1 (a migração da v1 dá a ela o pid 7).
    _gravar(paginas / "0008.json", {"boxes": [["b", 1, 1, 5, 5, 1.0, "manual", 0, False,
                                               -1.0, False]]})
    _gravar(pasta / "inclinacoes.json", {"0": 0.3, "5": -0.2})
    _gravar(pasta / "janela.json", {"pagina": 5})
    _gravar(pasta / "lote.json", {"paginas": [3, 4], "refazer": False, "reler_depois": [1]})
    dados = _json(pasta / "projeto.json")
    dados.pop("sequencia")
    dados.update(versao=2, proximo_pid=41)
    dados["extras"] = {"intervalo_do_corpo": [2, 50], "candidatos_da_amostra_guiada": [3, 4, 5],
                       "paginas_da_amostra_guiada": [10, 20],
                       "pendentes_iniciais_da_amostra": {"10": 4},
                       "paginas_da_camada_nativa": [0]}
    _gravar(pasta / "projeto.json", dados)
    (pasta / "livro.json").unlink()
    return pasta


def test_ca_12_7_a_v2_vira_v3_com_toda_pagina_com_pid(projeto_v2):
    antes = {n: (projeto_v2 / n).read_bytes()
             for n in ("projeto.json", "inclinacoes.json", "janela.json", "lote.json")}
    projeto = ProjetoDeLivro.abrir(projeto_v2)
    assert projeto.migrado and projeto.dados.versao == 3
    assert projeto.backups_da_migracao == [projeto_v2 / "backup-v2"]
    for nome, dados in antes.items():                           # os arquivos de antes
        assert (projeto_v2 / "backup-v2" / nome).read_bytes() == dados
    gravado = _json(projeto_v2 / "projeto.json")
    assert gravado["versao"] == 3 and len(gravado["sequencia"]["entradas"]) == 60
    s = projeto.sequencia
    assert [e.pagina for e in s.entradas] == list(range(60))
    assert s.pid_em(0) == 0 and s.pid_em(1) == 40 and s.pid_em(7) == 7
    novos = [p for i, p in enumerate(s.pids) if i not in (0, 1, 7)]
    assert len(set(s.pids)) == 60 and min(novos) > 40


def test_ca_12_7_os_gids_e_os_dados_ficam(projeto_v2):
    projeto = ProjetoDeLivro.abrir(projeto_v2)
    assert projeto.carregar_modelo(1).boxes[0].gid == gid_de(40, 0)
    assert projeto.carregar_modelo(0).boxes[0].gid == gid_de(0, 0)
    v1 = projeto.carregar_modelo(7)
    assert v1.pid == 7 and v1.boxes[0].entry.char == "b" and v1.boxes[0].gid == gid_de(7, 0)
    assert sorted(projeto.resumo_do_livro()) == [0, 1, 7]


def test_ca_12_7_inclinacoes_por_pid_sem_medir_de_novo(projeto_v2, monkeypatch):
    projeto = ProjetoDeLivro.abrir(projeto_v2)
    assert _json(projeto_v2 / "inclinacoes.json") == {
        f"p{projeto.pid_da_pagina(0)}:inteira:0": 0.3,
        f"p{projeto.pid_da_pagina(5)}:inteira:0": -0.2}
    monkeypatch.setattr(pg, "medir_inclinacao", lambda *_a, **_k: pytest.fail("mediu"))
    fonte = pg.fonte_do_projeto(projeto)
    assert fonte.inclinacao(0) == 0.3 and fonte.inclinacao(5) == -0.2


def test_ca_12_7_janela_lote_e_listas_por_pid(projeto_v2):
    projeto = ProjetoDeLivro.abrir(projeto_v2)
    pid = projeto.pid_da_pagina
    assert _json(projeto_v2 / "janela.json")["pid"] == pid(5)
    lote = _json(projeto_v2 / "lote.json")
    assert lote["pids"] and lote["paginas"] == [pid(3), pid(4)] and lote["reler_depois"] == [40]
    assert projeto.posicoes_das_gravadas(lote["paginas"]) == [3, 4]
    extras = projeto.dados.extras
    assert projeto.posicoes_das_gravadas(extras["intervalo_do_corpo"]) == [2, 50]
    assert projeto.posicoes_das_gravadas(extras["candidatos_da_amostra_guiada"]) == [3, 4, 5]
    assert projeto.posicoes_das_gravadas(extras["paginas_da_camada_nativa"]) == [0]
    assert extras["pendentes_iniciais_da_amostra"] == {str(pid(10)): 4}
    saude = livro.saude(projeto)
    assert saude.paginas == (10, 20) and saude.pendentes_antes == 4


def test_ca_12_7_reabrir_nao_migra_de_novo(projeto_v2):
    primeira = ProjetoDeLivro.abrir(projeto_v2)
    pids = primeira.sequencia.pids
    primeira.fechar()
    segunda = ProjetoDeLivro.abrir(projeto_v2)
    assert not segunda.migrado and segunda.sequencia.pids == pids


def test_ca_12_7_copiar_o_backup_de_volta_reabre_igual(projeto_v2):
    projeto = ProjetoDeLivro.abrir(projeto_v2)
    pids = {i: projeto.pid_da_pagina(i) for i in (0, 1, 7)}
    projeto.fechar()
    for arquivo in (projeto_v2 / "backup-v2").iterdir():
        shutil.copy2(arquivo, projeto_v2 / arquivo.name)
    reaberto = ProjetoDeLivro.abrir(projeto_v2)
    assert reaberto.migrado and {i: reaberto.pid_da_pagina(i) for i in (0, 1, 7)} == pids
    assert reaberto.carregar_modelo(1).boxes[0].gid == gid_de(40, 0)
    # As listas, o lote e as inclinações também voltam a pid, pelas mesmas páginas.
    assert reaberto.posicoes_das_gravadas(
        reaberto.dados.extras["paginas_da_amostra_guiada"]) == [10, 20]
    assert reaberto.posicoes_das_gravadas(_json(projeto_v2 / "lote.json")["paginas"]) == [3, 4]
    assert _json(projeto_v2 / "inclinacoes.json")[f"p{reaberto.pid_da_pagina(0)}:inteira:0"] \
        == 0.3


def test_ca_12_7_a_queda_depois_do_projeto_json_nao_perde_as_inclinacoes(projeto_v2,
                                                                          monkeypatch):
    """O `projeto.json` v3 foi gravado e a conversão das inclinações não: a medida da v2
    (pelo índice do PDF) ainda vale, e nada é medido de novo."""
    class Queda(Exception):
        pass

    def cair(*_a, **_k):
        raise Queda

    monkeypatch.setattr(ProjetoDeLivro, "_inclinacoes_para_pids", cair)
    with pytest.raises(Queda):
        ProjetoDeLivro.abrir(projeto_v2)
    monkeypatch.undo()
    assert _json(projeto_v2 / "projeto.json")["versao"] == 3
    reaberto = ProjetoDeLivro.abrir(projeto_v2)
    monkeypatch.setattr(pg, "medir_inclinacao", lambda *_a, **_k: pytest.fail("mediu"))
    assert pg.fonte_do_projeto(reaberto).inclinacao(0) == 0.3


def test_ca_12_7_sem_gravar_na_pasta_abre_so_para_leitura_com_a_sequencia_na_memoria(
        projeto_v2, monkeypatch):
    antes = (projeto_v2 / "projeto.json").read_bytes()

    def recusar(*_a, **_k):
        raise PermissionError("mídia só de leitura")

    monkeypatch.setattr(gv, "gravar_bytes", recusar)
    projeto = ProjetoDeLivro.abrir(projeto_v2)
    assert projeto.somente_leitura and not projeto.sequencia_gravada
    assert projeto.pid_da_pagina(1) == 40 and len(projeto.sequencia) == 60
    assert (projeto_v2 / "projeto.json").read_bytes() == antes
    projeto.fechar()


def test_ca_12_7_o_projeto_v1_vai_direto_a_v3(tmp_path):
    from tests.test_migracao_v1 import FIXTURE

    pasta = tmp_path / "v1"
    shutil.copytree(FIXTURE, pasta)
    projeto = ProjetoDeLivro.abrir(pasta)
    assert projeto.migrado and projeto.dados.versao == 3
    assert projeto.backups_da_migracao == [pasta / "backup-v1", pasta / "backup-v2"]
    assert _json(pasta / "backup-v2" / "projeto.json")["versao"] == 2   # o meio da cadeia
    assert projeto.pid_da_pagina(0) == 0 and projeto.pid_da_pagina(2) == 2   # v1: pid = índice
    assert _json(pasta / "projeto.json")["sequencia"]["entradas"][1]["pid"] == 1


def test_ca_12_7_sem_a_fonte_a_v3_espera_e_vem_quando_ela_volta(projeto_v2):
    """Sem o PDF não se sabe quantas páginas o livro tem: o projeto segue na v2 (gravável,
    como até a rodada 1d) e não grava uma sequência curta; com o PDF de volta, migra inteiro."""
    dados = _json(projeto_v2 / "projeto.json")
    fonte = projeto_v2 / dados["fonte"] if not Path(dados["fonte"]).is_absolute() \
        else Path(dados["fonte"])
    escondida = fonte.with_name("escondida.bin")
    fonte.rename(escondida)
    sem = ProjetoDeLivro.abrir(projeto_v2)
    assert not sem.migrado and not sem.sequencia_gravada and not sem.somente_leitura
    assert _json(projeto_v2 / "projeto.json")["versao"] == 2
    assert sem.pid_da_pagina(1) == 40
    sem.fechar()
    escondida.rename(fonte)
    com = ProjetoDeLivro.abrir(projeto_v2)
    assert com.migrado and len(_json(projeto_v2 / "projeto.json")["sequencia"]["entradas"]) == 60


def test_a_sequencia_gravada_curta_ganha_as_paginas_que_faltam_do_pdf(projeto_v2):
    projeto = ProjetoDeLivro.abrir(projeto_v2)
    dados = _json(projeto_v2 / "projeto.json")
    dados["sequencia"]["entradas"] = dados["sequencia"]["entradas"][:3]    # uma sequência curta
    projeto.fechar()
    _gravar(projeto_v2 / "projeto.json", dados)
    reaberto = ProjetoDeLivro.abrir(projeto_v2)
    s = reaberto.sequencia
    assert len(s) == 60 and [e.pagina for e in s.entradas] == list(range(60))
    assert s.pid_em(1) == 40 and len(set(s.pids)) == 60


@pytest.mark.parametrize("valor", [float("inf"), "x", [1], True, 2.5, -1, 999])
def test_valor_estragado_numa_lista_nao_impede_a_migracao(projeto_v2, valor):
    dados = _json(projeto_v2 / "projeto.json")
    dados["extras"]["paginas_da_amostra_guiada"] = [10, valor]
    (projeto_v2 / "projeto.json").write_text(json.dumps(dados), encoding="utf-8")
    projeto = ProjetoDeLivro.abrir(projeto_v2)
    assert projeto.posicoes_das_gravadas(projeto.dados.extras["paginas_da_amostra_guiada"]) \
        == [10]


def test_falha_de_gravacao_depois_do_projeto_json_migra_e_completa_na_proxima(projeto_v2,
                                                                              monkeypatch):
    real = gv.gravar_json

    def sem_janela(caminho, dados, *a, **k):
        if Path(caminho).name in ("janela.json", "lote.json", "inclinacoes.json"):
            raise PermissionError("o arquivo está aberto noutro programa")
        return real(caminho, dados, *a, **k)

    monkeypatch.setattr(gv, "gravar_json", sem_janela)
    projeto = ProjetoDeLivro.abrir(projeto_v2)
    assert projeto.migrado and not projeto.somente_leitura and projeto.dados.versao == 3
    assert "pid" not in _json(projeto_v2 / "janela.json")
    projeto.fechar()
    monkeypatch.undo()
    reaberto = ProjetoDeLivro.abrir(projeto_v2)              # completa o que faltou
    assert _json(projeto_v2 / "janela.json")["pid"] == reaberto.pid_da_pagina(5)
    assert _json(projeto_v2 / "lote.json")["pids"]
    assert not any(k.isdigit() for k in _json(projeto_v2 / "inclinacoes.json"))


def test_o_projeto_de_versao_mais_nova_com_sequencia_estranha_abre_so_para_leitura(projeto_v2):
    dados = _json(projeto_v2 / "projeto.json")
    dados.update(versao=9, sequencia={"formato": "outro"})
    _gravar(projeto_v2 / "projeto.json", dados)
    projeto = ProjetoDeLivro.abrir(projeto_v2)
    assert projeto.somente_leitura and len(projeto.sequencia) == 60
    assert projeto.pid_da_pagina(1) == 40
    projeto.fechar()


def test_o_janela_json_da_v2_sem_pid_vale_e_o_pid_ruim_nao():
    from abbychess.app.espaco import VERSAO_DO_ESPACO, _validar_espaco

    base = {"versao": VERSAO_DO_ESPACO, "janela": "", "divisor": "", "pagina": 5}
    assert _validar_espaco(base)["pid"] is None                 # o da v2: abre na posição
    assert _validar_espaco({**base, "pid": 12})["pid"] == 12
    with pytest.raises(TypeError):
        _validar_espaco({**base, "pid": "12"})


def test_as_chaves_das_listas_sao_as_que_a_migracao_converte():
    from abbychess import nativo
    from abbychess import projeto as pj

    assert {livro.CHAVE_DA_AMOSTRA, livro.CHAVE_DOS_CANDIDATOS_DA_AMOSTRA,
            nativo.CHAVE_DAS_PAGINAS, "intervalo_do_corpo"} == set(pj.LISTAS_DE_PAGINAS)
    assert (livro.CHAVE_DOS_PENDENTES_INICIAIS,) == pj.MAPAS_DE_PAGINAS


def test_o_projeto_novo_ja_nasce_na_v3(tmp_path, pdf_de_60_paginas):  # noqa: F811
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Novo", pdf_de_60_paginas)
    gravado = _json(projeto.pasta / "projeto.json")
    assert gravado["versao"] == 3 and len(gravado["sequencia"]["entradas"]) == 60
    assert not ProjetoDeLivro.abrir(projeto.pasta).migrado
