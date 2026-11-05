"""F-3 (o lance ilegal na tela), F-4 (a fila Lances), X-3 (lado não dito) e o registro por página."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from abbychess import decodificador_de_lances as dl
from abbychess import evidencia as ev
from abbychess import exportar as ex
from abbychess import lances as lc
from abbychess import pagina as pg
from abbychess import texto as tx
from abbychess.app import documento as dc
from abbychess.app import estilo
from abbychess.app import registro_de_eventos as re
from abbychess.app.janela import JanelaPrincipal
from abbychess.leitor import LeitorDoLivro
from abbychess.projeto import ProjetoDeLivro
from tests.ajudantes import _escrever, _lido, _pagina_sintetica

INICIAL = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"


@pytest.fixture
def janela(app, tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path, "Livro", _pagina_sintetica(tmp_path / "p.png"))
    projeto.dados.letras_das_pecas = "KQRBN"
    j = JanelaPrincipal()
    j.usar(projeto, pg.FonteDePaginas(projeto.fonte),
           LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    j.resize(1366, 768)
    j.show()
    j.activateWindow()
    app.processEvents()
    yield j
    j.close()


def _com_diagrama(j, *linhas):
    """A página com um diagrama da posição inicial antes das `linhas`."""
    pagina = _escrever(j, *linhas)
    diagrama = _lido(INICIAL, caixa=(0, 0, 8, 8))
    pagina.tabuleiros = [tuple(diagrama.caixa)]
    pagina.diagramas = [diagrama]
    j.pagina._mudou(pagina, 0, "x", j.pagina._instantaneo())
    return j.pagina.modelo


def _texto_da_linha(j, linha) -> str:
    return linha.linha.texto


# ------------------------------------------------------------------
# F-3
# ------------------------------------------------------------------
def test_ca_f3_1_o_lance_ilegal_fica_com_marca_e_entra_na_evidencia(app, janela):
    _com_diagrama(janela, "1.e4 e5 2.Bf3 Nc6")
    evidencia = janela.pagina.evidencia.agora()
    assert evidencia.ilegais
    assert "".join(janela.pagina.box(g).char for g in sorted(evidencia.ilegais)) == "Bf3"
    janela.pintar_texto()
    gid = sorted(evidencia.ilegais)[0]
    cursor = janela.texto.textCursor()
    cursor.setPosition(janela.texto.posicao_do_gid(gid) + 1)
    assert cursor.charFormat().background().color() == estilo.FUNDO_FORTE


def test_ca_f3_2_o_texto_diz_os_dois_lados_da_duvida(app, janela):
    _com_diagrama(janela, "1.e4 e5 2.Bf3")
    motivos = {m for m, _s in janela.pagina.evidencia.agora().motivos.values()}
    assert any("Bf3" in m and "leitura" in m and "impressão" in m and "diagrama" in m for m in motivos)


def test_gids_do_rejeitado_sem_o_numero(app, janela):
    _com_diagrama(janela, "1.e4 e5 2.Bf3")
    p = janela.pagina
    [d] = [d for d in p.diagramas_com_ids() if d.validacao is not None]
    assert d.validacao.legais == 2
    gids = lc.gids_do_rejeitado(p.documento(), d, "KQRBN")
    assert "".join(p.box(g).char for g in gids) == "Bf3"


def test_a_linha_legal_nao_tem_marca(app, janela):
    _com_diagrama(janela, "1.e4 e5 2.Nf3")
    assert not janela.pagina.evidencia.agora().ilegais


def test_o_lance_ilegal_nao_troca_nada(app, janela):
    modelo = _com_diagrama(janela, "1.e4 e5 2.Bf3")
    antes = [b.entry.char for b in modelo.boxes]
    janela.pagina.evidencia.agora()
    assert [b.entry.char for b in janela.pagina.modelo.boxes] == antes


# ------------------------------------------------------------------
# F-4
# ------------------------------------------------------------------
def test_f7_cicla_comecando_em_lances(janela):
    assert [m for m, _n in janela.fila.MODOS][:2] == ["lances", "confianca"]
    janela.fila.definir("diagramas")
    janela.fila.ciclar()
    assert janela.fila.modo == "lances"


def test_lances_nao_e_modo_de_glifos(janela):
    assert "lances" not in janela.fila.DE_GLIFOS


def test_f4_abre_a_fila_no_editor_palavra(app, janela):
    _escrever(janela, "prosa só", "1.e4 e5", "2.Nf3")
    janela.acao_fila_lances.trigger()
    app.processEvents()
    assert janela.fila.modo == "lances" and janela.inspetor.atual() == "palavra"
    assert janela.verificacao.campo.text() == "prosa só"        # a vizinha do primeiro lance
    assert janela.fila.contador() == "1/3"


def test_ca_f4_1_enter_confere_so_numero_lance_e_sinal_e_um_ctrl_z_volta(app, janela, monkeypatch):
    monkeypatch.setattr(dl, "COM_AS_VIZINHAS", False)
    _escrever(janela, "depois de 1.e4 ±", "antes de 2.Nf3 e fim")
    janela.acao_fila_lances.trigger()
    app.processEvents()
    p = janela.pagina
    amostras_antes = p.leitor.arquivos_de_padrao() if p.leitor else 0
    janela.verificacao.pedir_corrigir()
    janela.executor.esperar()
    app.processEvents()
    revisados = "".join(b.entry.char for b in p.modelo.boxes if b.revisado)
    assert revisados == "1.e4±"
    assert p.leitor.arquivos_de_padrao() == amostras_antes
    assert janela.fila.lances.atual().linha.texto == "antes de 2.Nf3 e fim"
    janela.acao_desfazer.trigger()
    janela.executor.esperar()
    assert not any(b.revisado for b in p.modelo.boxes)


def test_conferir_nao_troca_a_fonte_nem_o_caractere(app, janela):
    _escrever(janela, "1.e4 e5")
    p = janela.pagina
    antes = [(b.gid, b.entry.char, b.entry.source, b.entry.confidence) for b in p.modelo.boxes]
    janela.fila.ir_aos_lances()
    janela.verificacao.pedir_corrigir()
    janela.executor.esperar()
    assert [(b.gid, b.entry.char, b.entry.source, b.entry.confidence) for b in p.modelo.boxes] == antes
    assert all(b.revisado for b in p.modelo.boxes)


def test_a_linha_nao_entra_selecionada_e_a_palavra_entra(app, janela):
    from abbychess.app.painel_verificacao import CORPO_DA_LINHA, CORPO_DA_PALAVRA
    from abbychess.verificacao import Desconhecida

    _escrever(janela, "1.e4 e5")
    janela.fila.ir_aos_lances()
    campo = janela.verificacao.campo
    assert not campo.hasSelectedText() and campo.cursorPosition() == 0
    assert campo.font().pointSize() == CORPO_DA_LINHA
    p = janela.pagina
    janela.verificacao.mostrar(p.matriz, p.boxes, Desconhecida("1.e4", [0, 1, 2, 3]), 0, 1)
    assert campo.hasSelectedText() and campo.font().pointSize() == CORPO_DA_PALAVRA


def test_a_etiqueta_conta_a_pagina_aberta_antes_da_gravacao(app, janela):
    _escrever(janela, "1.e4 e5")
    janela.atualizar_paginas()
    assert "lances por conferir 2" in janela.rotulo_do_progresso.text()
    janela.fila.ir_aos_lances()
    janela.verificacao.pedir_corrigir()
    janela.executor.esperar()
    janela.atualizar_paginas()
    assert "lances por conferir 0" in janela.rotulo_do_progresso.text()


def test_alt_baixo_pula_sem_conferir(app, janela):
    _escrever(janela, "1.e4", "2.Nf3")
    janela.fila.ir_aos_lances()
    janela.acao_proximo_da_fila.trigger()
    assert janela.fila.lances.atual().linha.texto == "2.Nf3"
    assert not any(b.revisado for b in janela.pagina.modelo.boxes)


def test_editar_e_enter_corrige_e_confere(app, janela):
    _escrever(janela, "1.e4 e6")
    janela.fila.ir_aos_lances()
    janela.verificacao.campo.setText("1.e4 e5")
    janela.verificacao.pedir_corrigir()
    janela.executor.esperar()
    app.processEvents()
    p = janela.pagina
    assert "".join(b.entry.char for b in p.modelo.boxes) == "1.e4e5"
    assert all(b.revisado for b in p.modelo.boxes)
    janela.acao_desfazer.trigger()
    janela.executor.esperar()
    assert "".join(b.entry.char for b in p.modelo.boxes) == "1.e4e6"
    assert not any(b.revisado for b in p.modelo.boxes)


def test_ca_f4_2_o_ilegal_aceito_sem_editar_fica_sem_marca_e_o_relatorio_conta(app, janela):
    _com_diagrama(janela, "1.e4 e5 2.Bf3")
    p = janela.pagina
    assert p.evidencia.agora().ilegais
    janela.fila.ir_aos_lances()
    assert "Bf3" in janela.verificacao.lido.text()
    janela.verificacao.pedir_corrigir()
    janela.executor.esperar()
    assert not p.evidencia.agora().ilegais
    documento = p.documento()
    contagens = ev.contagens_dos_lances(p.modelo, documento, p.diagramas_com_ids(), "KQRBN")
    assert contagens["aceitos"] == 1 and contagens["ilegais"] == 0
    # Depois de reabrir: calculado de novo, sem nada gravado de novo.
    p.projeto.salvar_modelo(p.modelo)
    relida = p.projeto.carregar_modelo(0)
    assert not ev.da_pagina(relida, tx.montar(relida, com_os_nao_lidos=True), relida.diagramas,
                            "KQRBN").ilegais


def test_ca_f4_7a_as_telas_vazias(app, janela):
    _escrever(janela, "prosa só")
    janela.fila.ir_aos_lances()
    assert "Nenhuma forma de lance" in janela.verificacao.posicao.text()
    _escrever(janela, "1.e4")
    janela.fila.ir_aos_lances()
    janela.verificacao.pedir_corrigir()
    janela.executor.esperar()
    assert "Lances conferidos: 1, sendo 0 como impressos" in janela.verificacao.posicao.text()


def test_ca_f4_7a_confianca_vazia_com_lance_nao_diz_nada_a_revisar(app, janela):
    from abbychess.app.desenho import _sem_pendentes

    com = _sem_pendentes({"nao_conferidos": 40})
    assert "40 lances não conferidos" in com and "Nada a revisar" not in com
    assert "Nada a revisar" in _sem_pendentes({"nao_conferidos": 0})


def test_ca_f4_9_o_ctrl_t_pergunta_com_os_dois_numeros_e_esc_nao_marca(app, janela, monkeypatch):
    _escrever(janela, "1.e4 e5")
    p = janela.pagina
    monkeypatch.setattr(p.fila_da_pagina, "fila", lambda: [1, 2, 3])
    janela.verificar_pagina()
    texto = janela.confirmacao.pergunta.text()
    assert "Aceitar 3 dúvidas" in texto and "2 lances não conferidos" in texto
    janela.confirmacao._fechar()
    assert p.modelo.estado != "verificada"


def test_o_ctrl_t_so_com_lances_tambem_pergunta(app, janela):
    _escrever(janela, "1.e4")
    janela.pagina.leitor.limiares.revisao = 0.0
    janela.pagina.fila_da_pagina._limiar_da_pendencia = None
    janela.verificar_pagina()
    assert "1 lances não conferidos" in janela.confirmacao.pergunta.text()


def test_o_resumo_conta_os_lances_por_conferir(app, janela):
    _escrever(janela, "1.e4 e5")
    p = janela.pagina
    assert p.projeto.resumo.do_modelo(p.modelo)["lances_por_conferir"] == 2
    janela.fila.ir_aos_lances()
    janela.verificacao.pedir_corrigir()
    janela.executor.esperar()
    assert p.projeto.resumo.do_modelo(p.modelo)["lances_por_conferir"] == 0


def test_a_chave_a_mais_no_resumo_nao_muda_a_versao(tmp_path):
    from abbychess.resumo_do_livro import VERSAO_DO_LIVRO

    assert VERSAO_DO_LIVRO == 4


def test_o_relatorio_de_lances_lista_e_enter_vai_ao_lance(app, janela):
    _com_diagrama(janela, "1.e4 e5 2.Bf3")
    p = janela.pagina
    p.projeto.salvar_modelo(p.modelo)
    janela.relatorio_de_lances()
    janela.executor.esperar()
    app.processEvents()
    lista = janela.resultados.resultados
    textos = [lista.item(k).text() for k in range(lista.count())]
    assert textos[0].startswith("Relatório de lances:")
    assert any("ilegal" in t and "Bf3" in t for t in textos)


def test_a_exportacao_traz_as_quatro_contagens(app, janela, tmp_path):
    _com_diagrama(janela, "1.e4 e5 2.Bf3")
    p = janela.pagina
    p.projeto.salvar_modelo(p.modelo)
    relatorio = ex.Relatorio()
    ex._lances_no_relatorio(relatorio, p.projeto, 0)
    assert relatorio.lances["ilegais"] == 1
    assert "lances: 1 ilegal(is)" in relatorio.resumo()
    assert "não conferido(s)" in relatorio.resumo()


def test_a_tecla_f4_tem_excecao_no_combobox():
    from abbychess.atalhos import carregar

    acao = carregar().da_acao("fila_lances")
    assert any(e.widget == "combobox" and e.tecla == "F4" for e in acao.excecoes)


def test_a_linha_mostra_sublinhado_e_forte(app, janela):
    _com_diagrama(janela, "1.e4 e5 2.Bf3")
    janela.fila.ir_aos_lances()
    assert janela.linha._sublinhados and janela.linha._fortes
    assert janela.linha._fortes <= janela.linha._sublinhados | janela.linha._fortes


def test_a_linha_longa_diminui_a_letra(app):
    from abbychess.app.linha import CORPO_MAXIMO, CORPO_MINIMO, FaixaDaLinha
    from core.box_model import BoxEntry

    faixa = FaixaDaLinha()
    faixa._boxes = [BoxEntry("a", k, 0, k + 1, 1) for k in range(70)]
    faixa.escala = 2.0
    assert faixa.corpo_do_texto() == CORPO_MINIMO
    faixa.escala = 40.0
    assert faixa.corpo_do_texto() == CORPO_MAXIMO


def test_ctrl_enter_ensina_so_os_que_mudaram(app, janela, monkeypatch):
    _escrever(janela, "1.e4 e6")
    p = janela.pagina
    pedidos = []
    monkeypatch.setattr(p.leitura, "ensinar_gids", lambda por_char, *a, **k: pedidos.append(por_char))
    janela.fila.ir_aos_lances()
    janela.verificacao.campo.setText("1.e4 e5")
    janela.verificacao.pedir_ensinar()
    janela.executor.esperar()
    app.processEvents()
    assert list(pedidos[0]) == ["5"] and len(pedidos[0]["5"]) == 1


def test_ctrl_enter_sem_mudanca_nao_ensina(app, janela, monkeypatch):
    _escrever(janela, "1.e4")
    p = janela.pagina
    monkeypatch.setattr(p.leitura, "ensinar_gids", lambda *a, **k: pytest.fail("ensinou"))
    janela.fila.ir_aos_lances()
    janela.verificacao.pedir_ensinar()
    janela.executor.esperar()
    assert all(b.revisado for b in p.modelo.boxes)


class _Pagina:
    def __init__(self, indice, resumo):
        self.indice = indice
        self.projeto = type("P", (), {"resumo": type("R", (), {"do_livro": lambda s: resumo})()})


def test_a_vizinha_no_escopo_livro():
    from abbychess.controladores import _vizinha_com_lances

    resumo = {0: {"lances_por_conferir": 2}, 1: {"lances_por_conferir": 0}, 2: {},
              3: {"lances_por_conferir": 1, "estado": "nao_reconhecida"}, 4: {"lances_por_conferir": 1}}
    assert _vizinha_com_lances(_Pagina(0, resumo), +1) == 2       # sem a chave: desconhecida, abre
    assert _vizinha_com_lances(_Pagina(2, resumo), +1) == 4
    assert _vizinha_com_lances(_Pagina(4, resumo), +1) is None
    assert _vizinha_com_lances(_Pagina(2, resumo), -1) == 0
    assert _vizinha_com_lances(_Pagina(0, resumo), -1) is None
    sem_projeto = _Pagina(0, resumo)
    sem_projeto.projeto = None
    assert _vizinha_com_lances(sem_projeto, +1) is None


def test_os_itens_do_relatorio_por_tipo(app, janela):
    _com_diagrama(janela, "1.e4 e5 2.Bf3")
    p = janela.pagina
    itens = ev.itens_da_pagina(0, p.modelo, p.documento(), p.diagramas_com_ids(), "KQRBN")
    assert {i.tipo for i in itens} == {"ilegal", "não conferido"}
    ilegal = next(i for i in itens if i.tipo == "ilegal")
    assert ilegal.pagina == 0 and "p. 1: ilegal" in ilegal.texto


def test_o_item_sem_posicao_e_o_aceito(app, janela):
    _escrever(janela, "14.Qh8")
    p = janela.pagina
    itens = ev.itens_da_pagina(0, p.modelo, p.documento(), [], "KQRBN")
    assert [i.tipo for i in itens] == ["sem posição"]
    _com_diagrama(janela, "1.e4 e5 2.Bf3")
    janela.fila.ir_aos_lances()
    janela.verificacao.pedir_corrigir()
    janela.executor.esperar()
    itens = ev.itens_da_pagina(0, p.modelo, p.documento(), p.diagramas_com_ids(), "KQRBN")
    assert [i.tipo for i in itens] == ["aceito como impresso"]


def test_o_relatorio_sem_x1_nao_lista_os_nao_conferidos(app, janela, monkeypatch):
    monkeypatch.setattr(ev, "X1_LIGADO", False)
    _escrever(janela, "1.e4")
    p = janela.pagina
    assert ev.itens_da_pagina(0, p.modelo, p.documento(), [], "KQRBN") == []


# ------------------------------------------------------------------
# X-3
# ------------------------------------------------------------------
def test_ca_x3_1_sem_lado_dito_nao_sai_como_confiavel():
    d = _lido()
    assert not d.lado
    assert dc.estado_do_diagrama(d) == "lado não dito"


def test_o_lado_pelos_lances_e_dito():
    from dataclasses import replace

    validacao = lc.Validacao(lc.CONFIAVEL, 1, 1, vez="w")
    d = replace(_lido(), lado="w", lado_origem=lc.LADO_DOS_LANCES, validacao=validacao)
    assert dc.estado_do_diagrama(d) == "confiável pelos lances"


def test_ca_x3_2_ctrl_w_e_ctrl_b_definem_o_lado(app, janela):
    editor = janela.editor_diagrama
    editor.abrir([_lido()], pid=0)
    assert "lado não dito" in editor.cabecalho.text()
    assert janela.acao_lado_pretas.shortcuts()[0].toString() == "Ctrl+B"
    assert janela.acao_lado_brancas.shortcuts()[0].toString() == "Ctrl+W"
    janela.acao_lado_pretas.trigger()
    assert editor.tabuleiro().lado == "b" and "lado não dito" not in editor.cabecalho.text()
    janela.acao_lado_brancas.trigger()
    assert editor.tabuleiro().lado == "w"


def test_o_relatorio_lista_o_lado_presumido(app, janela):
    _com_diagrama(janela, "prosa")
    p = janela.pagina
    p.projeto.salvar_modelo(p.modelo)
    relatorio = ex.Relatorio()
    ex._lances_no_relatorio(relatorio, p.projeto, 0)
    assert relatorio.lado_presumido == {0: 1}
    assert "1 diagrama(s) com o lado presumido" in relatorio.resumo()


# ------------------------------------------------------------------
# As letras das peças
# ------------------------------------------------------------------
def test_as_letras_do_projeto_mudam_a_validacao(app, janela):
    assert janela.projeto.dados.chave_das_pecas == "KQRBN"
    janela.projeto.dados.letras_das_pecas = ""
    assert janela.projeto.dados.chave_das_pecas == janela.projeto.dados.idioma


def test_o_campo_das_letras_nas_opcoes(app):
    from abbychess.app.opcoes import DialogoDeOpcoes
    from abbychess.dados_do_projeto import Limiares

    dialogo = DialogoDeOpcoes(Limiares(), letras="KQRBN")
    assert dialogo.letras() == "KQRBN"
    dialogo.campo_letras.setText("kqrbn")
    assert dialogo.letras() == "KQRBN"
    dialogo.campo_letras.setText("KK")
    assert dialogo.letras() == ""


# ------------------------------------------------------------------
# O registro por página
# ------------------------------------------------------------------
def test_o_registro_escreve_a_pagina_sem_texto(app, tmp_path):
    caminho = tmp_path / "e.jsonl"
    registro = re.RegistroDeEventos(str(caminho))
    registro.pagina(7, "lances")
    registro.fechar()
    linhas = [json.loads(ln) for ln in caminho.read_text(encoding="utf-8").splitlines()]
    assert {"pid": 7, "fila": "lances", "evento": "pagina"}.items() <= linhas[1].items()


def test_o_tempo_por_pagina(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
    import tempo_da_fatia as tf

    eventos = [{"evento": "inicio", "t": 0}, {"evento": "pagina", "pid": 1, "fila": "lances", "t": 0},
               {"evento": "tecla", "t": 1}, {"evento": "tecla", "t": 11},
               {"evento": "pagina", "pid": 2, "fila": "confianca", "t": 12},
               {"evento": "tecla", "t": 13}, {"evento": "tecla", "t": 200}]
    linhas = [json.dumps(e) for e in eventos]
    saida = tf.por_pagina(linhas)
    assert saida["por_pagina"] == {"1": 10.0, "2": 2.0}
    assert tf.por_pagina(linhas, "lances")["por_pagina"] == {"1": 10.0}


def test_o_registro_ligado_por_padrao_e_a_opcao_desliga(app):
    from abbychess.app import opcoes
    from abbychess.app.janela import configuracao

    config = configuracao()
    config.remove(opcoes.CHAVE_DO_REGISTRO)
    assert opcoes.registro_ligado(config)
    config.setValue(opcoes.CHAVE_DO_REGISTRO, "nao")
    assert not opcoes.registro_ligado(config)
    config.remove(opcoes.CHAVE_DO_REGISTRO)


def test_instalar_com_o_padrao(app, tmp_path, monkeypatch):
    monkeypatch.delenv(re.VARIAVEL, raising=False)
    assert re.instalar(app) is None
    registro = re.instalar(app, str(tmp_path / "e.jsonl"))
    assert registro is re.atual
    app.removeEventFilter(registro)
    registro.fechar()
    re.atual = None
