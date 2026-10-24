"""As operações de página (SPEC §12.4, passo L, rodada 2a): reordenar, apagar, restaurar e
inserir, pelo controlador e com o desfazer — CA-12.8, 12.9, 12.10, 12.15 e CA-4.6."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest
from core.box_model import BoxEntry
from PIL import Image

from abbychess import exportar as ex
from abbychess import pagina as pg
from abbychess import sequencia as sq
from abbychess.controlador import ControladorDePagina
from abbychess.leitor import LeitorDoLivro, nome_de_origem
from abbychess.modelo import pid_de
from abbychess.projeto import ProjetoDeLivro

from tests.test_visor import pdf_de_60_paginas  # noqa: F401


def _box(char, x=10):
    return BoxEntry(char=char, x1=x, y1=10, x2=x + 8, y2=22, source="manual", confidence=1.0)


def _ligar(projeto):
    controlador = ControladorDePagina()
    avisos = []
    controlador.eventos.ligar("aviso", lambda titulo, texto: avisos.append(texto))
    controlador.eventos.ligar("recusa", lambda _refazer, texto: avisos.append(texto))
    controlador.avisos = avisos
    controlador.ligar(projeto, pg.fonte_do_projeto(projeto),
                      LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    controlador.ir_para(0)
    return controlador


@pytest.fixture
def projeto(tmp_path, pdf_de_60_paginas):  # noqa: F811
    return ProjetoDeLivro.criar(tmp_path / "livros", "Operar", pdf_de_60_paginas)


@pytest.fixture
def ctl(projeto):
    return _ligar(projeto)


def _hashes(projeto):
    return {a.name: hashlib.sha256(a.read_bytes()).hexdigest()
            for a in (projeto.pasta / "paginas").glob("p*.json")}


def _texto(projeto):
    paginas = ex.paginas_do_projeto(projeto, None, camada="nunca",
                                    opcoes=ex.Opcoes(manter_margens=True))
    return ex.texto_do_livro(paginas)


# ----------------------------------------------------------------------
# CA-12.8: reordenar
# ----------------------------------------------------------------------

def test_ca_12_8_reordenar_so_reescreve_a_sequencia(projeto, ctl):
    for i in range(5):
        projeto.salvar_pagina(i, [_box("abcde"[i])])
    pids = projeto.sequencia.pids
    antes = _hashes(projeto)
    ctl.ir_para(2)                                   # a página 3 aberta
    assert ctl.mover_paginas([1, 2, 3], 9)           # as páginas 2-4 depois da 10
    esperado = [pids[0], *pids[4:10], pids[1], pids[2], pids[3], *pids[10:]]
    assert projeto.sequencia.pids == esperado
    assert _hashes(projeto) == antes                 # nenhum JSON de página mudou
    assert ctl.indice == esperado.index(pids[2])     # a aberta seguiu o pid
    assert ProjetoDeLivro.abrir(projeto.pasta).sequencia.pids == esperado     # gravada
    assert _texto(projeto).index("e") < _texto(projeto).index("b")            # na ordem nova


def test_ca_12_8_desfazer_devolve_a_ordem_e_o_seguinte_desfaz_a_edicao_de_antes(projeto, ctl):
    largura, altura = ctl.imagem.size
    ctl.marcar(0, 0, largura - 1, altura // 4)       # uma edição na página 1
    assert projeto.carregar_modelo(0).boxes
    pids = projeto.sequencia.pids
    ctl.mover_paginas([0], 4)
    assert projeto.sequencia.pids[4] == pids[0]
    ctl.desfazer()
    assert projeto.sequencia.pids == pids
    ctl.desfazer()                                   # a edição de antes da reordenação
    assert not projeto.carregar_modelo(0).boxes
    ctl.refazer()
    ctl.refazer()
    assert projeto.sequencia.pids[4] == pids[0] and projeto.carregar_modelo(4).boxes


def test_desfazer_a_reordenacao_e_recusado_se_a_ordem_mudou_por_fora(projeto, ctl):
    ctl.mover_paginas([0], 4)
    s = projeto.sequencia
    projeto.gravar_sequencia(s.mover([s.pid_em(10)], -1))    # outra mudança, sem o desfazer
    ctl.desfazer()
    assert any("mudou depois" in a for a in ctl.avisos)
    assert projeto.sequencia.pid_em(0) == s.pid_em(10)       # nada foi mudado


# ----------------------------------------------------------------------
# CA-12.9: inserir
# ----------------------------------------------------------------------

def _pdf(caminho, textos):
    import fitz

    with fitz.open() as doc:
        for texto in textos:
            doc.new_page(width=200, height=300).insert_text((20, 40), texto, fontsize=14)
        doc.save(str(caminho))
    return caminho


def _png(caminho):
    sorteio = np.random.default_rng(5)
    Image.fromarray(sorteio.integers(0, 255, (120, 80), dtype=np.uint8)).save(caminho)
    return caminho


def test_ca_12_9_inserir_copia_os_arquivos_e_as_paginas_renderizam_iguais(projeto, ctl,
                                                                          tmp_path):
    pdf = _pdf(tmp_path / "fora.pdf", ["Inserida A", "Inserida B"])
    png = _png(tmp_path / "fora.png")
    esperadas = [np.asarray(pg.FonteDePaginas(pdf).pagina(k).convert("L")) for k in (0, 1)]
    esperadas.append(np.asarray(Image.open(png).convert("L")))
    antes = set(projeto.sequencia.todos_os_pids)
    assert ctl.inserir_paginas([pdf, png], 5)        # depois da posição 5
    s = projeto.sequencia
    novas = [s.entrada_em(i) for i in (5, 6, 7)]
    assert len(s) == 63 and all(e.pid > max(antes) for e in novas)
    assert {e.fonte.split("/")[0] for e in novas} == {sq.PASTA_DAS_INSERIDAS}
    assert len(list((projeto.pasta / "inseridas").iterdir())) == 2
    pdf.unlink()
    png.unlink()                                     # o projeto não depende dos de fora
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    fonte = pg.fonte_do_projeto(reaberto)
    for posicao, esperada in zip((5, 6, 7), esperadas):          # antes de endireitar
        assert np.array_equal(np.asarray(fonte.original(posicao).convert("L")), esperada)


def test_ca_12_9_inserir_antes_da_primeira_e_ler_e_exportar_a_inserida(projeto, ctl, tmp_path):
    pdf = _pdf(tmp_path / "rosto.pdf", ["Rosto"])
    assert ctl.inserir_paginas([pdf], 0)
    assert projeto.sequencia.entrada_em(0).fonte.startswith("inseridas/")
    projeto.salvar_pagina(0, [_box("q"), _box("q", x=20)])     # lida (os boxes de um F5)
    assert projeto.carregar_modelo(0).pid == projeto.pid_da_pagina(0)
    assert _texto(projeto).startswith("qq")


def test_ca_12_9_pdf_cifrado_e_recusado_e_nada_muda(projeto, ctl, tmp_path):
    import fitz

    cifrado = tmp_path / "cifrado.pdf"
    with fitz.open() as doc:
        doc.new_page()
        doc.save(str(cifrado), encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="x", owner_pw="y")
    antes = (projeto.pasta / "projeto.json").read_bytes()
    assert not ctl.inserir_paginas([cifrado], 3)
    assert any("cifrado" in a for a in ctl.avisos)
    assert (projeto.pasta / "projeto.json").read_bytes() == antes
    assert not (projeto.pasta / "inseridas").exists()


# ----------------------------------------------------------------------
# CA-12.10: apagar e restaurar
# ----------------------------------------------------------------------

def test_ca_12_10_apagar_tira_do_livro_e_guarda_os_arquivos(projeto, ctl):
    for i, letra in ((2, "x"), (6, "y"), (8, "z")):
        projeto.salvar_pagina(i, [_box(letra), _box(letra, x=20)])
    pids = projeto.sequencia.pids
    antes = _hashes(projeto)
    assert ctl.apagar_paginas([2, 6])                # as páginas 3 e 7
    s = projeto.sequencia
    assert pids[2] not in s.pids and pids[6] not in s.pids and len(s) == 58
    # A posição conta as que ficaram: a 7 tinha 5 páginas do livro antes dela.
    assert {a.entrada.pid: a.posicao for a in s.apagadas} == {pids[2]: 2, pids[6]: 5}
    assert sorted(projeto.resumo_do_livro()) == [s.posicao_de(pids[8])]
    assert projeto.paginas_lidas() == [s.posicao_de(pids[8])]
    assert _texto(projeto).strip() == "zz"           # a exportação também
    assert _hashes(projeto) == antes                 # os arquivos continuam no disco
    ctl.desfazer()
    assert projeto.sequencia.pids == pids and sorted(projeto.resumo_do_livro()) == [2, 6, 8]


def test_ca_12_10_restaurar_depois_de_reabrir_devolve_ao_lugar(projeto, ctl):
    projeto.salvar_pagina(6, [_box("y")])
    pids = projeto.sequencia.pids
    ctl.apagar_paginas([2, 6])
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    assert {a.entrada.pid for a in reaberto.sequencia.apagadas} == {pids[2], pids[6]}
    outro = _ligar(reaberto)
    assert outro.restaurar_paginas([pids[6], pids[2]])
    assert reaberto.sequencia.pids == pids and not reaberto.sequencia.apagadas
    assert reaberto.carregar_pagina(6)[0].char == "y"


def test_a_pagina_aberta_que_e_apagada_da_lugar_a_vizinha(projeto, ctl):
    ctl.ir_para(59)
    pids = projeto.sequencia.pids
    ctl.apagar_paginas([59])
    assert ctl.indice == 58 and projeto.pid_da_pagina(ctl.indice) == pids[58]
    assert ctl.fonte.total == 59


def test_apagar_todas_e_recusado(projeto, ctl):
    assert not ctl.apagar_paginas(list(range(60)))
    assert len(projeto.sequencia) == 60


# ----------------------------------------------------------------------
# CA-12.15: a seleção e quando as operações ficam desligadas
# ----------------------------------------------------------------------

def test_ca_12_15_a_selecao_e_do_livro_e_a_operacao_e_uma_transacao(projeto, ctl):
    ctl.mover_paginas([30], -1)                      # reordenado: a 31 do PDF é a 1 do livro
    passos = ctl.historico.passos
    impares = sq.selecao("ímpares", len(projeto.sequencia))
    pids = sq.pids_da_selecao(projeto.sequencia, impares)
    assert pids[0] == projeto.sequencia.pid_em(0) == ctl.projeto.sequencia.pids[0]
    ctl.apagar_paginas(impares)
    assert ctl.historico.passos == passos + 1
    assert not set(pids) & set(projeto.sequencia.pids)


@pytest.mark.parametrize("como", ["lote", "so_leitura"])
def test_ca_12_15_com_o_lote_ou_so_para_leitura_nada_muda(projeto, ctl, como, tmp_path):
    if como == "lote":
        ctl.lote_rodando = True
    else:
        projeto.somente_leitura = True
    arquivos = {a: a.read_bytes() for a in projeto.pasta.rglob("*") if a.is_file()}
    assert ctl.motivo_para_nao_mudar_as_paginas() is not None
    assert not ctl.mover_paginas([1], 5)
    assert not ctl.apagar_paginas([1])
    assert not ctl.inserir_paginas([_png(tmp_path / "x.png")], 0)
    assert {a: a.read_bytes() for a in projeto.pasta.rglob("*") if a.is_file()} == arquivos


def test_com_uma_tarefa_em_curso_as_operacoes_e_o_desfazer_delas_esperam(projeto, ctl,
                                                                         monkeypatch):
    ctl.mover_paginas([0], 4)
    pids = projeto.sequencia.pids
    monkeypatch.setattr(ctl, "_agora", lambda: False)        # o F5 rodando, por exemplo
    assert not ctl.apagar_paginas([1])
    ctl.desfazer()
    assert projeto.sequencia.pids == pids and any("não pode voltar" in a for a in ctl.avisos)
    monkeypatch.undo()
    ctl.lote_rodando = True
    ctl.desfazer()
    assert projeto.sequencia.pids == pids                    # nem com o lote rodando


def test_a_operacao_que_nao_muda_nada_nao_vira_passo(projeto, ctl):
    passos = ctl.historico.passos
    assert not ctl.mover_paginas([3], 2)                     # a 4 já está depois da 3
    assert ctl.historico.passos == passos


def test_falha_ao_gravar_a_ordem_nao_muda_nada(projeto, ctl, monkeypatch):
    from abbychess import gravacao as gv

    pids = projeto.sequencia.pids

    def recusar(*_a, **_k):
        raise PermissionError("o projeto.json está aberto noutro programa")

    monkeypatch.setattr(gv, "gravar_json", recusar)
    assert not ctl.apagar_paginas([2])
    assert projeto.sequencia.pids == pids and ctl.historico.passos == 0
    assert any("não foi gravado" in a for a in ctl.avisos)


def test_desfazer_o_inserir_poe_as_inseridas_nas_apagadas(projeto, ctl, tmp_path):
    ctl.inserir_paginas([_png(tmp_path / "x.png")], 3)
    pid = projeto.pid_da_pagina(3)
    projeto.salvar_pagina(3, [_box("w")])                     # lida, fora do desfazer
    ctl.desfazer()
    assert pid not in projeto.sequencia.pids
    apagada = projeto.sequencia.apagada(pid)
    assert apagada is not None and apagada.entrada.fonte.startswith("inseridas/")
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)           # e não vira página do livro
    assert reaberto.sequencia.apagada(pid).entrada.fonte.startswith("inseridas/")
    ctl.refazer()
    assert projeto.sequencia.pid_em(3) == pid and not projeto.sequencia.apagadas


def test_as_visitas_seguem_as_paginas_pelo_pid(projeto, ctl):
    for i in (5, 9, 5):
        ctl.ir_para(i)                                       # visitas: 1, 6, 10, 6
    pids = projeto.sequencia.pids
    ctl.mover_paginas([5], 20)                               # a 6 vai para depois da 21
    assert ctl.visitas == [0, 20, 8, 20] and ctl._visita == 3
    ctl.voltar_visita()
    assert projeto.pid_da_pagina(ctl.indice) == pids[9]


def test_pdf_cifrado_diz_que_e_cifrado(projeto, tmp_path):
    import fitz

    from abbychess.projeto import ProjetoInvalido

    cifrado = tmp_path / "c.pdf"
    with fitz.open() as doc:
        doc.new_page()
        doc.save(str(cifrado), encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="x", owner_pw="y")
    with pytest.raises(ProjetoInvalido, match="é um PDF cifrado"):
        projeto.inserir_arquivo(cifrado)


# ----------------------------------------------------------------------
# CA-4.6: inserir antes da primeira e reordenar três páginas
# ----------------------------------------------------------------------

def test_ca_4_6_nenhum_gid_se_repete_e_a_amostra_acha_a_origem(projeto, ctl, tmp_path):
    for i in range(3):
        projeto.salvar_pagina(i, [_box("m"), _box("n", x=20)])
    gid = projeto.carregar_modelo(1).boxes[1].gid
    origem = nome_de_origem("livro", 1, 1, gid)
    ctl.inserir_paginas([_png(tmp_path / "antes.png")], 0)
    ctl.mover_paginas([1, 2, 3], 10)
    projeto.salvar_pagina(0, [_box("p"), _box("q", x=20)])      # a inserida, lida
    todos = []
    for arquivo in (projeto.pasta / "paginas").glob("p*.json"):
        todos += [b[0] for b in json.loads(arquivo.read_text(encoding="utf-8"))["boxes"]]
    assert len(todos) == len(set(todos)) == 8
    posicao, achado = projeto.origem_da_amostra(origem)
    assert achado == gid and projeto.pid_da_pagina(posicao) == pid_de(gid)
    assert gid in {b.gid for b in projeto.carregar_modelo(posicao).boxes}
