"""A sequência no projeto (SPEC §12.4, passo L, rodada 1b): o cache, as gravações pendentes,
o `livro.json` e o desfazer chaveados por `pid`; a posição de uma página vem da sequência.

Ainda não há operação que reordene (rodada 2): aqui a sequência é trocada na memória, como a
operação vai trocar, para provar que tudo segue o `pid` e não o índice do PDF."""

from __future__ import annotations

import json

import pytest
from core.box_model import BoxEntry

from abbychess import sequencia as sq
from abbychess.projeto import ARQUIVO_DO_LIVRO, VERSAO_DO_LIVRO, ProjetoDeLivro

from tests.test_visor import pdf_de_60_paginas  # noqa: F401


def _box(x=10, char="a"):
    return BoxEntry(char=char, x1=x, y1=10, x2=x + 8, y2=22, source="livro",
                    confidence=0.95)


@pytest.fixture
def projeto(tmp_path, pdf_de_60_paginas):  # noqa: F811
    return ProjetoDeLivro.criar(tmp_path / "livros", "Sequencia", pdf_de_60_paginas)


def _reordenar(projeto, ordem):
    """Troca a sequência na memória (o que a operação de reordenar fará, na rodada 2)."""
    s = projeto.sequencia
    projeto._trocar_sequencia(sq.Sequencia(tuple(s.entradas[i] for i in ordem), s.apagadas))


def test_o_projeto_novo_tem_uma_entrada_por_pagina_do_pdf(projeto):
    s = projeto.sequencia
    assert len(s) == 60 and [e.pagina for e in s.entradas] == list(range(60))
    assert len(set(s.pids)) == 60
    assert projeto.pid_da_pagina(7) == s.pid_em(7)


def test_a_primeira_edicao_usa_o_pid_da_sequencia_e_o_contador_passa_dele(projeto):
    pid = projeto.pid_da_pagina(41)
    projeto.salvar_pagina(41, [_box()])
    assert projeto.carregar_modelo(41).pid == pid
    assert projeto.dados.proximo_pid > pid
    gravado = json.loads(ProjetoDeLivro.abrir(projeto.pasta).pasta.joinpath(
        "projeto.json").read_text(encoding="utf-8"))
    assert gravado["proximo_pid"] > pid            # no disco antes do arquivo da página


def test_livro_json_e_chaveado_por_pid_com_o_indice(projeto):
    projeto.salvar_pagina(3, [_box()])
    livro = json.loads((projeto.pasta / ARQUIVO_DO_LIVRO).read_text(encoding="utf-8"))
    pid = projeto.pid_da_pagina(3)
    assert livro["versao"] == VERSAO_DO_LIVRO and list(livro["paginas"]) == [str(pid)]
    assert livro["paginas"][str(pid)]["pagina_da_fonte"] == 3


def test_reabrir_monta_a_mesma_posicao_para_cada_pagina_gravada(projeto):
    for i in (0, 5, 59):
        projeto.salvar_pagina(i, [_box()])
    pids = {i: projeto.pid_da_pagina(i) for i in (0, 5, 59)}
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    assert {i: reaberto.pid_da_pagina(i) for i in (0, 5, 59)} == pids
    assert sorted(reaberto.resumo_do_livro()) == [0, 5, 59]


def test_o_livro_json_antigo_por_indice_e_refeito(projeto):
    projeto.salvar_pagina(2, [_box()])
    pid = projeto.pid_da_pagina(2)
    arquivo = projeto.pasta / ARQUIVO_DO_LIVRO
    velho = json.loads(arquivo.read_text(encoding="utf-8"))
    resumo = velho["paginas"][str(pid)]
    resumo.pop("pagina_da_fonte")
    arquivo.write_text(json.dumps({"versao": 3, "paginas": {"3": resumo}}), encoding="utf-8")
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    assert reaberto.pid_da_pagina(2) == pid and list(reaberto.resumo_do_livro()) == [2]
    assert json.loads(arquivo.read_text(encoding="utf-8"))["versao"] == VERSAO_DO_LIVRO


def test_arquivo_que_o_livro_nao_cita_entra_na_sequencia(projeto):
    projeto.salvar_pagina(8, [_box()])
    pid = projeto.pid_da_pagina(8)
    arquivo = projeto.pasta / ARQUIVO_DO_LIVRO
    livro = json.loads(arquivo.read_text(encoding="utf-8"))
    del livro["paginas"][str(pid)]                 # a queda entre a página e o livro
    arquivo.write_text(json.dumps(livro), encoding="utf-8")
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    assert reaberto.pid_da_pagina(8) == pid
    assert reaberto.carregar_pagina(8) is not None and 8 in reaberto.resumo_do_livro()
    assert str(pid) in json.loads(arquivo.read_text(encoding="utf-8"))["paginas"]


# ----------------------------------------------------------------------
# A posição segue a sequência (o que a rodada 2 vai usar)
# ----------------------------------------------------------------------

def test_depois_de_reordenar_a_pagina_e_achada_na_posicao_nova(projeto):
    projeto.salvar_pagina(0, [_box(char="x")])
    projeto.salvar_pagina(1, [_box(char="y")])
    pid0 = projeto.pid_da_pagina(0)
    _reordenar(projeto, [1, 2, 0, *range(3, 60)])  # a página 1 vai à posição 3
    assert projeto.pid_da_pagina(2) == pid0
    assert projeto.carregar_pagina(2)[0].char == "x"
    assert projeto.carregar_pagina(0)[0].char == "y"
    assert projeto.carregar_modelo(2).indice == 2  # a posição de agora, não a gravada
    resumo = projeto.resumo_do_livro()
    assert sorted(resumo) == [0, 2] and resumo[2]["pid"] == pid0


def test_gravar_depois_de_reordenar_guarda_a_pagina_do_pdf_e_nao_a_posicao(projeto):
    """Até a v3 gravar a sequência (rodada 1e), o PDF dá a ordem: a página movida e gravada
    tem de voltar à página dela no PDF, e não ir para a posição em que estava ao gravar."""
    projeto.salvar_pagina(0, [_box(char="x")])
    pid = projeto.pid_da_pagina(0)
    _reordenar(projeto, [1, 2, 0, *range(3, 60)])
    projeto.salvar_pagina(2, [_box(char="z")])         # a mesma página, na posição 3
    assert projeto.fechar(10)
    livro = json.loads((projeto.pasta / ARQUIVO_DO_LIVRO).read_text(encoding="utf-8"))
    assert livro["paginas"][str(pid)]["pagina_da_fonte"] == 0
    bruto = json.loads((projeto.pasta / "paginas" / f"p{pid}.json").read_text(encoding="utf-8"))
    assert bruto["indice"] == 0
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    assert reaberto.pid_da_pagina(0) == pid and reaberto.carregar_pagina(0)[0].char == "z"


def test_perguntar_fora_do_livro_nao_cria_paginas(projeto):
    assert projeto.pid_da_pagina(500) is None
    assert projeto.carregar_modelo(500) is None and projeto.modelo_em_memoria(500) is None
    assert projeto.estado_da_pagina(500) == "nao_reconhecida"
    assert len(projeto.sequencia) == 60


def test_arquivo_em_disco_fora_do_livro_reserva_o_pid(projeto):
    """Um `p<pid>.json` que não entra na sequência (o perdedor de dois arquivos do mesmo
    índice) não tem o pid dele dado a outra página."""
    projeto.salvar_pagina(0, [_box()])
    bruto = json.loads((projeto.pasta / "paginas" / f"p{projeto.pid_da_pagina(0)}.json")
                       .read_text(encoding="utf-8"))
    bruto.update(pid=500, gravado_em="2000-01-01T00:00:00+00:00")
    (projeto.pasta / "paginas" / "p500.json").write_text(json.dumps(bruto), encoding="utf-8")
    (projeto.pasta / ARQUIVO_DO_LIVRO).unlink()
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    assert reaberto.pid_da_pagina(0) == projeto.pid_da_pagina(0)
    assert 500 not in reaberto.sequencia.pids
    assert min(p for p in reaberto.sequencia.pids if p != reaberto.pid_da_pagina(0)) > 500


def test_sem_a_fonte_a_pagina_gravada_continua_no_lugar(projeto):
    projeto.salvar_pagina(7, [_box()])
    pid = projeto.pid_da_pagina(7)
    projeto.fonte.rename(projeto.fonte.with_suffix(".sumido"))
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    assert reaberto.pid_da_pagina(7) == pid and reaberto.carregar_pagina(7) is not None


def test_pagina_pendente_no_gravador_segue_a_posicao(projeto):
    pagina = projeto.pagina_para_editar(4)
    _reordenar(projeto, [4, *range(4), *range(5, 60)])
    assert projeto.agendar(pagina)
    assert projeto.paginas_sujas() == [0]
    assert 0 in projeto.resumo_do_livro()
    assert projeto.fechar(10) and projeto.paginas_sujas() == []


def test_o_desfazer_acha_a_pagina_pelo_pid_depois_de_reordenar(tmp_path, pdf_de_60_paginas):  # noqa: F811
    from abbychess import pagina as pg
    from abbychess.controlador import ControladorDePagina
    from abbychess.leitor import LeitorDoLivro

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Desfazer", pdf_de_60_paginas)
    controlador = ControladorDePagina()
    controlador.ligar(projeto, pg.fonte_do_projeto(projeto),
                      LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    controlador.ir_para(6)
    largura, altura = controlador.imagem.size
    controlador.marcar(0, 0, largura - 1, altura // 4)  # o "Pagina 7" vira um glifo
    pid = projeto.pid_da_pagina(6)
    assert projeto.carregar_modelo(6).boxes
    controlador.ir_para(0)
    _reordenar(projeto, [6, *range(6), *range(7, 60)])
    controlador.desfazer()
    assert controlador.indice == 0 and controlador.modelo.pid == pid
    assert not controlador.modelo.boxes
