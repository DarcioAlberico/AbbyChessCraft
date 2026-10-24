"""As correções das revisões do fechamento do passo L (docs/revisoes/passo-l.md): o ângulo
guardado no Ctrl+Z do giro, dividir sem medir as páginas sem leitura, o `indice` da página que
não é do PDF, a seleção com paridade e intervalo, e a janela (girar num gesto, a gaveta, os
diálogos)."""

from __future__ import annotations

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.box_model import BoxEntry  # noqa: E402
from PIL import Image  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialogButtonBox  # noqa: E402

from abbychess import pagina as pg  # noqa: E402
from abbychess import sequencia as sq  # noqa: E402
from abbychess.app import dialogo_paginas as dp  # noqa: E402
from abbychess.controlador import ControladorDePagina  # noqa: E402
from abbychess.leitor import LeitorDoLivro  # noqa: E402
from abbychess.projeto import FORA_DO_PDF, ProjetoDeLivro  # noqa: E402

from tests.test_espaco import sim  # noqa: E402,F401
from tests.test_visor import pdf_de_60_paginas  # noqa: E402,F401


class _Medidas:
    """A medida da inclinação: 0,6° na página deitada (mais larga que alta), 0 na de pé; conta
    as chamadas."""

    def __init__(self):
        self.chamadas = 0

    def __call__(self, cinza, *_a, **_k):
        self.chamadas += 1
        altura, largura = cinza.shape[:2]
        return 0.6 if largura > altura else 0.0


@pytest.fixture
def medidas(monkeypatch):
    medir = _Medidas()
    monkeypatch.setattr(pg, "medir_inclinacao", medir)
    return medir


@pytest.fixture
def projeto(tmp_path, pdf_de_60_paginas, medidas):  # noqa: F811
    return ProjetoDeLivro.criar(tmp_path / "livros", "Fechamento", pdf_de_60_paginas)


@pytest.fixture
def ctl(projeto):
    controlador = ControladorDePagina()
    controlador.ligar(projeto, pg.fonte_do_projeto(projeto),
                      LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    controlador.ir_para(0)
    return controlador


def _ler(projeto, posicao):
    projeto.salvar_pagina(posicao, [BoxEntry(char="a", x1=30, y1=40, x2=52, y2=70,
                                             source="manual", confidence=1.0)])


def test_o_ctrl_z_do_giro_guarda_o_angulo_em_que_a_pagina_foi_lida(projeto, ctl):
    """A página sem leitura girada, lida deitada (0,6°) e o giro desfeito: a imagem de pé fica
    endireitada pelos 0,6° em que os boxes foram lidos, e não pelos 0° medidos agora."""
    ctl.girar_paginas([2], 90)
    assert ctl.fonte.inclinacao(2) == 0.6
    _ler(projeto, 2)
    ctl.desfazer()
    assert projeto.sequencia.entrada_em(2).giro == 0
    assert ctl.fonte.inclinacao(2) == 0.6
    ctl.refazer()
    assert ctl.fonte.inclinacao(2) == 0.6


def test_dividir_nao_mede_a_pagina_sem_leitura(projeto, ctl, medidas):
    antes = medidas.chamadas
    assert ctl.dividir_paginas([3, 4, 5, 6, 7])
    assert medidas.chamadas == antes


def test_dividir_pula_as_metades_e_avisa(projeto, ctl):
    avisos = []
    ctl.eventos.ligar("mensagem", lambda texto, *_: avisos.append(texto))
    ctl.dividir_paginas([1])
    assert ctl.dividir_paginas([1, 2, 3])                     # 1 e 2 já são metades
    assert len(projeto.sequencia) == 62
    assert "2 páginas já eram metades" in avisos[-1]
    assert not ctl.dividir_paginas([1, 2])                    # só metades: nada muda


def test_a_inserida_e_a_metade_direita_nao_gravam_o_indice_do_pdf(projeto, ctl, tmp_path):
    imagem = tmp_path / "solta.png"
    Image.fromarray(np.full((300, 200), 255, np.uint8)).save(imagem)
    projeto.gravar_sequencia(projeto.sequencia.inserir(projeto.inserir_arquivo(imagem), 5))
    _ler(projeto, 5)
    _ler(projeto, 8)
    ctl.dividir_paginas([8])
    projeto.descarregar()
    livro = json.loads((projeto.pasta / "livro.json").read_text(encoding="utf-8"))
    por_pid = {int(k): v["pagina_da_fonte"] for k, v in livro["paginas"].items()}
    assert por_pid[projeto.pid_da_pagina(5)] == FORA_DO_PDF          # a inserida
    assert por_pid[projeto.pid_da_pagina(8)] == 7                    # a esquerda: a p. 8
    assert por_pid[projeto.pid_da_pagina(9)] == FORA_DO_PDF          # a direita
    bruto = json.loads((projeto.pasta / "paginas" / f"p{projeto.pid_da_pagina(5)}.json")
                       .read_text(encoding="utf-8"))
    assert bruto["indice"] == FORA_DO_PDF


@pytest.mark.parametrize("texto, posicoes", [
    ("ímpares 1-10", [0, 2, 4, 6, 8]), ("pares de 3 a 9", [3, 5, 7]),
    ("impares: 15-20", [14, 16, 18]), ("pares 2", [1])])
def test_a_selecao_com_paridade_e_intervalo(texto, posicoes):
    assert sq.selecao(texto, 20) == posicoes


def test_a_selecao_com_paridade_fora_do_livro_diz_o_motivo():
    with pytest.raises(ValueError, match="fora"):
        sq.selecao("ímpares 1-30", 20)


# ----------------------------------------------------------------------
# A janela
# ----------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app, tmp_path, pdf_de_60_paginas, sim, medidas):  # noqa: F811
    from abbychess.app.janela import JanelaPrincipal

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Janela", pdf_de_60_paginas)
    j = JanelaPrincipal()
    j.resize(1366, 768)
    j.show()
    j.usar(projeto, pg.fonte_do_projeto(projeto),
           LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    QApplication.processEvents()
    yield j
    j.close()


def test_girar_a_direita_e_a_esquerda_num_gesto(app, janela):
    janela.ir_para_pagina(4)
    janela.acao_girar_a_direita.trigger()
    assert janela.projeto.sequencia.entrada_em(4).giro == 90
    assert janela.statusBar().currentMessage().startswith("Feito: Girar 1 página à direita")
    janela.acao_girar_a_esquerda.trigger()
    assert janela.projeto.sequencia.entrada_em(4).giro == 0


def test_a_gaveta_tem_todas_as_operacoes_com_a_selecao(app, janela, monkeypatch):
    menu = janela.paginas.menu_de_contexto()
    textos = [a.text() for a in menu.actions()]
    for texto in ("Girar à direita", "Cortar…", "Dividir…", "Endireitar…"):
        assert texto in textos
    janela.paginas.operacao.emit("girar_a_direita", [1, 2])
    assert [janela.projeto.sequencia.entrada_em(i).giro for i in (1, 2, 3)] == [90, 90, 0]


def test_o_dialogo_de_mover_recusa_a_referencia_que_se_move(app):
    from abbychess.app.paginas_na_janela import _mover_vale

    d = dp.DialogoDasPaginas(None, "Mover", 20, selecao="3-5", lugar="Depois da página",
                             lugar_padrao=4, validar=_mover_vale,
                             efeito=dp.efeito("1 página muda de lugar: {PAGINAS}.",
                                              "{N} páginas mudam de lugar: {PAGINAS}."))
    ok = d.botoes.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok.isEnabled() and "referência" in d.previa.text()
    d.lugar.setValue(10)
    assert ok.isEnabled() and d.previa.text() == "3 páginas mudam de lugar: 3-5."
    d.campo.setText("7")
    assert d.previa.text() == "1 página muda de lugar: 7."
    assert d.minimumWidth() >= 400
    d.deleteLater()


def test_o_endireitar_diz_o_que_o_ok_faz_conforme_a_caixa(app, janela, monkeypatch):
    """No medido (o padrão), o OK só volta as páginas de ângulo à mão, e fica desligado sem
    elas; com um ângulo, ele diz que a leitura se desfaz. A prévia segue a caixa."""
    vistos = {}

    def perguntar_com(janela_, titulo, total, linhas, ler, **opcoes):
        d = dp.DialogoDasPaginas(janela_, titulo, total, linhas=linhas, **opcoes)
        ok = d.botoes.button(QDialogButtonBox.StandardButton.Ok)
        caixa = linhas[2][1]
        vistos["medido"] = (ok.isEnabled(), ok.text(), d.previa.text(), ler())
        caixa.setChecked(False)
        vistos["a_mao"] = (ok.isEnabled(), ok.text(), d.previa.text())
        d.deleteLater()
        return None

    monkeypatch.setattr(dp, "perguntar_com", perguntar_com)
    _ler(janela.projeto, 1)
    janela.endireitar_paginas([0, 1, 2])
    habilitado, _rotulo, previa, valor = vistos["medido"]
    assert not habilitado and "nada muda" in previa and valor is None
    habilitado, rotulo, previa = vistos["a_mao"]
    assert habilitado and rotulo == "Endireitar e desfazer a leitura"
    assert "A leitura de 1 página se desfaz" in previa
    janela.pagina.endireitar_paginas([2], 1.5)                # uma com ângulo à mão
    janela.endireitar_paginas([0, 1, 2])
    habilitado, rotulo, previa, _valor = vistos["medido"]
    assert habilitado and rotulo == "Voltar ao ângulo medido"
    assert previa.startswith("1 página volta ao ângulo medido")


def test_mover_para_onde_ja_estao_e_recusado_no_dialogo():
    from abbychess.app.paginas_na_janela import _mover_vale

    assert "já estão aí" in _mover_vale([25], 24)
    assert "já estão aí" in _mover_vale([3, 4, 5], 2)
    assert _mover_vale([3, 4, 5], 9) is None


def test_o_aviso_de_dividir_conta_as_divididas(projeto, ctl):
    avisos = []
    ctl.eventos.ligar("mensagem", lambda texto, *_: avisos.append(texto))
    ctl.dividir_paginas([1])
    ctl.dividir_paginas([1, 2, 3, 4])                         # 1 e 2 são metades
    assert avisos[-1].startswith("Feito: Dividir 2 páginas (2 páginas já eram metades")


def test_os_botoes_do_qt_em_portugues(app):
    from abbychess.app.principal import traduzir_o_qt

    traduzir_o_qt(app)
    caixa = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
    assert caixa.button(QDialogButtonBox.StandardButton.Cancel).text() == "Cancelar"
    caixa.deleteLater()


def test_ir_a_origem_diz_que_o_glifo_saiu_da_pagina_ou_do_livro(app, janela):
    projeto = janela.projeto
    _ler(projeto, 3)
    janela.ir_para_pagina(3)
    gid = projeto.carregar_modelo(3).boxes[0].gid
    janela.pagina.cortar_paginas([3], (0.5, 0, 0, 0))          # o glifo fica de fora
    janela.ir_a_origem(3, gid)
    assert "saiu da página" in janela.statusBar().currentMessage()
    janela.ir_a_origem(None, gid)
    assert "saiu do livro" in janela.statusBar().currentMessage()


def test_a_busca_le_a_pagina_girada_fora_da_memoria_na_geometria_da_entrada(projeto, ctl):
    """Girar não regrava a página: o índice, que lê o arquivo, a leva ao giro (e à posição de
    agora), e acha o mesmo texto que acharia com ela na memória."""
    from abbychess import busca as bs

    caixas = [BoxEntry(char=c, x1=40 + 14 * k, y1=60, x2=52 + 14 * k, y2=80, source="manual",
                       confidence=1.0) for k, c in enumerate("ola")]
    caixas += [BoxEntry(char=c, x1=40 + 14 * k, y1=400, x2=52 + 14 * k, y2=420,
                        source="manual", confidence=1.0) for k, c in enumerate("mundo")]
    projeto.salvar_pagina(3, caixas)
    ctl.girar_paginas([3], 90)
    ctl.mover_paginas([3], 9)                                  # e muda de lugar
    posicao = projeto.posicao_do_pid(projeto.sequencia.entradas[9].pid)
    na_memoria = bs._indexar_tarefa((projeto.carregar_modelo(posicao).instantaneo(), "pt", 0))
    entrada = projeto.sequencia.entrada_em(posicao)
    do_arquivo = bs._indexar_tarefa(((str(projeto.arquivo_da_pagina(posicao)), posicao,
                                      entrada.geometria, entrada.tamanho), "pt", 0))
    assert do_arquivo.texto == na_memoria.texto and do_arquivo.indice == posicao == 9


def test_o_ctrl_z_da_divisao_pelo_carimbo_com_o_cache_vazio(projeto, ctl):
    """O caminho rápido do desfazer (o arquivo como `trocar_paginas` o deixou): aceita a página
    intocada e recusa a que mudou por fora."""
    _ler(projeto, 2)
    ctl.dividir_paginas([2])
    with projeto._trava_do_cache:
        projeto._modelos.clear()
    assert ctl.desfazer() is None and len(projeto.sequencia) == 60   # intocada: desfaz
    ctl.refazer()
    with projeto._trava_do_cache:
        projeto._modelos.clear()
    arquivo = projeto.pasta / "paginas" / f"p{projeto.pid_da_pagina(3)}.json"
    bruto = json.loads(arquivo.read_text(encoding="utf-8"))
    bruto["estado"] = "verificada"                                  # mudou por fora
    arquivo.write_text(json.dumps(bruto), encoding="utf-8")
    ctl.desfazer()
    assert len(projeto.sequencia) == 61                             # recusado
