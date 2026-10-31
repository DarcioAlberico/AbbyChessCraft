"""A janela com o livro inteiro: lote em segundo plano, F6 entre páginas e exportação.

Como em `test_janela`, o leitor roda sem a rede global, e o resto é o código
real, com as tarefas no `Executor`. As perguntas e os diálogos de arquivo são
trocados por respostas fixas.
"""

from __future__ import annotations

import os
import json
import zipfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (QApplication, QFileDialog, QInputDialog, QMenu,  # noqa: E402
                               QMessageBox)

from abbychess import livro as lv  # noqa: E402
from abbychess import pagina as pg  # noqa: E402
from abbychess.app.janela import JanelaPrincipal  # noqa: E402
from abbychess.leitor import FONTE_MANUAL, LeitorDoLivro  # noqa: E402
from abbychess.projeto import ProjetoDeLivro  # noqa: E402

from tests.ajudantes import _esperar  # noqa: E402,F401,F811
from tests.ajudantes import pdf_sintetico  # noqa: E402,F401,F811
from tests.janela_util import trocar_entries  # noqa: E402
from tests.janela_util import atual, boxes, fila, mostrar, pulados, selecao  # noqa: E402,F401

SIM = QMessageBox.StandardButton.Yes
NAO = QMessageBox.StandardButton.No


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def respostas(monkeypatch):
    """O que os diálogos respondem; o teste muda antes de agir."""
    estado = {"intervalo": "1-3", "pergunta": SIM, "perguntas": 0, "arquivo": ""}

    def pergunta(*a, **_k):
        estado["perguntas"] += 1
        estado["texto"] = a[2] if len(a) > 2 else ""
        return estado["pergunta"]

    monkeypatch.setattr(QMessageBox, "question", pergunta)
    monkeypatch.setattr(QInputDialog, "getText",
                        lambda *a, **k: (estado["intervalo"], True))
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (estado["arquivo"], "EPUB (*.epub)"))

    # O diálogo da exportação: `estado["exportacao"]` preenche o formulário, e ele aceita.
    from PySide6.QtWidgets import QDialog

    from abbychess.app.dialogo_exportacao import DialogoDeExportacao

    def exec_(dialogo):
        estado["dialogo"] = dialogo
        preencher = estado.get("exportacao")
        if preencher is not None:
            preencher(dialogo)
        dialogo.done(QDialog.DialogCode.Accepted)        # como o exec de verdade termina
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DialogoDeExportacao, "exec", exec_)
    return estado


@pytest.fixture
def janela(app, tmp_path, respostas):
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Livro", pdf_sintetico(tmp_path))
    j = JanelaPrincipal()
    j.usar(projeto, pg.FonteDePaginas(projeto.fonte),
          LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    yield j
    j.close()


def test_menu_ferramentas_tem_o_lote_e_o_projeto_a_exportacao(janela):
    ferramentas = [a.text() for a in janela.menu_ferramentas.actions()]
    pagina = next(m for m in janela.menuBar().findChildren(QMenu) if m.title() == "P&ágina")
    assert "Reconhecer o livro…" in ferramentas
    assert "Próxima página com pendentes" in [a.text() for a in pagina.actions()]
    projeto = next(m for m in janela.menuBar().findChildren(QMenu) if m.title() == "&Projeto")
    assert "Exportar…" in [a.text() for a in projeto.actions()]
    assert janela.acao_lote.isEnabled() and not janela.acao_cancelar_lote.isEnabled()


def test_cartao_de_saude_mostra_a_evolucao_e_oferece_o_lote(janela):
    chamadas = []
    janela.paginas.reconhecer_livro.disconnect()
    janela.paginas.reconhecer_livro.connect(lambda: chamadas.append(True))

    abertas = []
    janela.paginas.abrir.disconnect()
    janela.paginas.abrir.connect(abertas.append)
    janela.paginas.mostrar_saude(lv.SaudeDoLivro((0, 1, 2), 40, 3, 12, 4,
                                                 ((0, 10, 1), (1, 20, 2), (2, 10, 0))))

    assert janela.paginas.saude.isHidden() is False
    assert janela.paginas.amostra_da_saude.text() == "Amostra (3 páginas), pendentes antes → agora:"
    texto = janela.paginas.pendentes_da_saude.text()
    assert ">p. 2</a>: 20 → 2" in texto and "Total: 40 → 3" in texto   # por página (§9.1)
    janela.paginas.pendentes_da_saude.linkActivated.emit("1")          # o link abre a página
    assert abertas == [1]
    assert janela.paginas.padroes_da_saude.text() == "12 amostras ensinadas"
    assert janela.paginas.limiar_da_saude.value() == 4
    assert janela.paginas.botao_reconhecer_livro.isDefault()
    assert janela.paginas.botao_reconhecer_livro.property("pronto") is True
    janela.paginas.botao_reconhecer_livro.click()
    assert chamadas == [True]


def test_o_limiar_da_saude_e_escolhido_na_gaveta(janela):
    """O limiar do cartão vem do usuário (§9.1) e fica no projeto."""
    janela.paginas.limiar_da_saude.setValue(7)
    assert janela.projeto.dados.extras[lv.CHAVE_DO_LIMIAR_DA_SAUDE] == 7


def test_lote_reconhece_o_intervalo_e_mostra_a_pagina_atual(app, janela, respostas):
    respostas["intervalo"] = "1-2"
    janela.reconhecer_livro()
    assert janela.acao_cancelar_lote.isEnabled()
    _esperar(app, janela)
    assert janela.projeto.resumo.paginas_lidas() == [0, 1]
    assert boxes(janela), "a página aberta foi lida no lote e recarregada"
    assert "Lote concluído" in janela.statusBar().currentMessage()
    assert not janela.acao_cancelar_lote.isEnabled()
    assert respostas["perguntas"] == 0  # nada lido antes: nada a perguntar


def test_lote_pergunta_e_pula_as_ja_lidas(app, janela, respostas):
    janela.reconhecer()
    _esperar(app, janela)
    mostrar(janela, 0)
    janela.treino.campo.setText("a")
    janela.treino.pedir_so_corrigir()

    respostas["pergunta"] = NAO
    janela.reconhecer_livro()
    _esperar(app, janela)
    assert respostas["perguntas"] == 1
    assert janela.projeto.resumo.paginas_lidas() == [0, 1, 2]
    assert janela.projeto.carregar_pagina(0)[0].source == FONTE_MANUAL


def test_cancelar_o_lote_guarda_o_que_ja_foi_lido(app, janela, respostas):
    janela.reconhecer_livro()
    janela.livro.cancelar()
    _esperar(app, janela)
    assert "Lote cancelado" in janela.statusBar().currentMessage()
    assert len(janela.projeto.resumo.paginas_lidas()) < 3


def test_f6_vai_para_a_proxima_pagina_com_pendentes(app, janela):
    janela.reconhecer_livro()
    _esperar(app, janela)
    # Resolve a página 1 inteira; a 2 também, e o F6 tem de achar a 3.
    def resolver(e):
        e.char, e.source, e.confidence = "a", FONTE_MANUAL, 1.0

    trocar_entries(janela, 0, resolver)
    trocar_entries(janela, 1, resolver)

    janela.livro.proximo_pendente()
    assert janela.pagina.indice == 2
    assert atual(janela) == fila(janela)[0]

    # Com pendentes na página aberta, F6 fica nela.
    janela.livro.proximo_pendente()
    assert janela.pagina.indice == 2


def test_exportar_epub_pela_janela(app, janela, respostas, tmp_path):
    janela.reconhecer_livro()
    _esperar(app, janela)
    respostas["arquivo"] = str(tmp_path / "saida")  # sem extensão: vale o filtro

    def preencher(dialogo):
        dialogo.autores.setText("Yasser Seirawan; Jeremy Silman")
        dialogo.data.setText("2012-05")
    respostas["exportacao"] = preencher
    janela.exportar()
    _esperar(app, janela)
    destino = tmp_path / "saida.epub"
    assert destino.is_file()
    with zipfile.ZipFile(destino) as z:
        assert z.namelist()[0] == "mimetype"
        opf = z.read("OEBPS/content.opf").decode("utf-8")
    assert "<dc:creator>Jeremy Silman</dc:creator>" in opf and "<dc:date>2012-05</dc:date>" in opf
    assert "Exportado em saida.epub" in janela.statusBar().currentMessage()
    # O formulário ficou no projeto: a próxima exportação já o traz preenchido.
    gravado = json.loads((janela.projeto.pasta / "metadados.json").read_text(encoding="utf-8"))
    assert gravado == {"autores": ["Yasser Seirawan", "Jeremy Silman"], "data": "2012-05"}
    respostas["exportacao"] = None
    janela.exportar()
    _esperar(app, janela)
    assert respostas["dialogo"].autores.text() == "Yasser Seirawan; Jeremy Silman"
    assert respostas["dialogo"].marcas.isEnabled() is False      # é do TXT


def test_a_pergunta_do_lote_diz_que_as_correcoes_ficam_e_conta_as_verificadas_a_parte(
        app, janela, respostas):
    from abbychess.modelo import VERIFICADA

    respostas["intervalo"] = "1-3"
    janela.reconhecer_livro()
    _esperar(app, janela)
    janela.projeto.paginas_em_memoria.descarregar(10)
    pagina = janela.projeto.carregar_modelo(2)
    pagina.estado = VERIFICADA
    janela.projeto.salvar_modelo(pagina)
    respostas["perguntas"], respostas["pergunta"] = 0, NAO
    janela.reconhecer_livro()
    _esperar(app, janela)
    texto = respostas["texto"]
    assert "2 das 3" in texto and "1 verificada" in texto
    assert "mantendo as correções manuais" in texto and "Voltar ao estado antes do lote" in texto


def test_a_previa_que_chega_depois_de_fechar_o_dialogo_nao_abre_janela(app, janela, respostas,
                                                                       tmp_path):
    janela.reconhecer_livro()
    _esperar(app, janela)
    respostas["arquivo"] = str(tmp_path / "saida.epub")
    respostas["exportacao"] = lambda dialogo: dialogo.previsualizar()
    janela.exportar()                       # pede a prévia e fecha com Exportar
    _esperar(app, janela)                   # a prévia chega, depois a exportação
    dialogo = respostas["dialogo"]
    assert dialogo.vivo is False and dialogo.janela_da_previa is None
    assert (tmp_path / "saida.epub").is_file()


def test_previa_pelo_controlador_chega_ao_dialogo(app, janela, tmp_path):
    from abbychess import exportar as ex
    from abbychess.app.dialogo_exportacao import DialogoDeExportacao

    janela.reconhecer_livro()
    _esperar(app, janela)
    dialogo = DialogoDeExportacao(janela, "epub", ex.Opcoes(), {}, tmp_path, "Livro")
    dialogo.ao_previsualizar = lambda f, o, m: janela.livro.previa(
        f, o, m, dialogo.mostrar_previa, dialogo.previa_falhou)
    dialogo.previsualizar()
    assert not dialogo.btn_exportar.isEnabled()   # Exportar espera a prévia
    _esperar(app, janela)
    texto = dialogo.janela_da_previa.navegador.toPlainText()
    # As páginas desta fixture não têm caracteres ensinados: a prévia mostra as marcas delas.
    assert "Pré-visualização" in texto and "Relatório" in texto and "Página 3" in texto
    assert dialogo.btn_exportar.isEnabled()
    dialogo.reject()
    assert not dialogo.janela_da_previa.isVisible()   # fechar o diálogo fecha a prévia


# ----------------------------------------------------------------------
# As opções do livro e o modelo de áreas, pelos menus
# ----------------------------------------------------------------------

def _no_dialogo(preencher, aceitar=True):
    """O diálogo modal, quando abrir: `preencher(dialogo)` e o OK (ou o Cancelar)."""
    from PySide6.QtCore import QTimer

    def agir():
        dialogo = QApplication.activeModalWidget()
        preencher(dialogo)
        dialogo.accept() if aceitar else dialogo.reject()
    QTimer.singleShot(0, agir)


def test_as_opcoes_do_livro_mudam_os_limiares_a_notacao_e_o_idioma(app, janela):
    import json

    def mudar(dialogo):
        dialogo.campos["revisao"].setValue(0.35)
        dialogo.campo_notacao.setCurrentIndex(dialogo.campo_notacao.findData("letras"))
        dialogo.campo_idioma.setCurrentIndex(dialogo.campo_idioma.findData("en"))
    dados = janela.projeto.dados
    antes = (dados.limiares.revisao, dados.notacao, dados.idioma)
    assert all(a != b for a, b in zip(antes, (0.35, "letras", "en")))
    _no_dialogo(mudar, aceitar=False)                    # Cancelar: nada muda
    janela.acao_opcoes.trigger()
    assert (dados.limiares.revisao, dados.notacao, dados.idioma) == antes

    _no_dialogo(mudar)
    janela.acao_opcoes.trigger()
    assert (dados.limiares.revisao, dados.notacao, dados.idioma) == (0.35, "letras", "en")
    gravado = json.loads((janela.projeto.pasta / "projeto.json").read_text(encoding="utf-8"))
    assert gravado["notacao"] == "letras" and gravado["idioma"] == "en"


def test_as_opcoes_sem_livro_aberto_nao_abrem(app, respostas):
    janela = JanelaPrincipal()
    try:
        janela.opcoes()                                   # sem projeto: nenhum diálogo modal
        assert QApplication.activeModalWidget() is None
    finally:
        janela.close()


def test_o_modelo_de_areas_vai_as_paginas_impares_do_intervalo(app, janela, respostas,
                                                               monkeypatch):
    escolhas = []

    def paridade(*_a, **_k):
        return escolhas.pop(0)
    monkeypatch.setattr(QInputDialog, "getItem", paridade)
    janela.acao_aplicar_modelo_areas.trigger()           # sem modelo salvo: nada a aplicar
    assert not any(janela.projeto.carregar_zonas(i) for i in range(3))

    janela.acao_areas.setChecked(True)
    janela.modo_areas(True)
    _esperar(app, janela)
    zonas = list(janela.areas.zonas)
    assert zonas
    janela.acao_salvar_modelo_areas.trigger()
    janela.pagina.ir_para(1)
    _esperar(app, janela)
    for _ in list(janela.areas.zonas):                   # a 2ª sem áreas, para ver o modelo
        janela.areas.apagar(0)

    escolhas.append(("Páginas ímpares", False))          # Cancelar na paridade
    janela.acao_aplicar_modelo_areas.trigger()
    assert not janela.projeto.carregar_zonas(2)

    respostas["intervalo"] = "2-3"
    escolhas.append(("Páginas ímpares", True))
    janela.acao_aplicar_modelo_areas.trigger()
    assert [z.caixa for z in janela.projeto.carregar_zonas(2)] == [z.caixa for z in zonas]
    assert not janela.projeto.carregar_zonas(1)          # a 2ª é par: fica sem


# ----------------------------------------------------------------------
# Retomar o lote, voltar ao antes dele e o cartão Saúde no Documento
# ----------------------------------------------------------------------

CANCELAR = QMessageBox.StandardButton.Cancel


def _livro_sem_janela(tmp_path):
    """O projeto de 3 páginas com o controlador do livro sem janela (as tarefas quando o
    teste quiser), para deixar o projeto como uma sessão de antes o deixou."""
    from abbychess.controladores import ControladorDoLivro
    from tests.ajudantes import ExecutorManual, _controlador

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Livro", pdf_sintetico(tmp_path))
    executor = ExecutorManual()
    pagina = _controlador(projeto, executor)
    livro = ControladorDoLivro(pagina)
    livro.executor = executor
    return projeto, pagina, livro, executor


def _reaberto(projeto):
    """O projeto fechado e aberto de novo numa janela, como no dia seguinte."""
    projeto.paginas_em_memoria.descarregar(10)
    pasta = projeto.pasta
    projeto.fechar()
    reaberto = ProjetoDeLivro.abrir(pasta)
    j = JanelaPrincipal()
    j.usar(reaberto, pg.FonteDePaginas(reaberto.fonte),
           LeitorDoLivro(reaberto.pasta_de_padroes, limiares=reaberto.dados.limiares))
    return j


@pytest.fixture
def lote_parado(app, tmp_path, respostas):
    """A janela de um projeto fechado com o lote no meio: a 1ª página, aberta e corrigida à
    mão (um "R"), ficou para reler depois; a 2ª foi relida, a 3ª falta."""
    projeto, pagina, livro, executor = _livro_sem_janela(tmp_path)
    livro.reconhecer([0, 1, 2], refazer=False)
    executor.tudo()
    pagina.escolher(pagina.gids[0])
    pagina.corrigir("R")
    livro.reconhecer([0, 1, 2], refazer=True)            # a 1ª, aberta e mudada, fica
    executor.comecar()()                                 # a 2ª é lida
    livro.cancelar()
    executor.tudo()
    assert livro.reler_depois == [0] and livro.restante == ([2], True)
    j = _reaberto(projeto)
    yield j
    j.close()


def _o_r_manual(projeto) -> bool:
    return any((b.entry.char, b.entry.source) == ("R", FONTE_MANUAL)
               for b in projeto.carregar_modelo(0).boxes)


def test_retomar_o_lote_pergunta_se_le_tambem_as_paginas_mudadas(app, lote_parado, respostas):
    j = lote_parado
    assert j.livro.pode_retomar and j.livro.restante == ([2], True)
    respostas["pergunta"] = CANCELAR
    j.retomar_lote()
    _esperar(app, j)
    texto = respostas["texto"]
    assert "O lote não sobrescreveu as páginas 1, porque você as mudou" in texto
    assert "Não lê só o que faltou do lote" in texto
    assert j.livro.restante == ([2], True) and j.livro.reler_depois == [0]      # nada

    respostas["pergunta"] = NAO                          # só o que faltou
    j.retomar_lote()
    _esperar(app, j)
    assert j.livro.restante is None and j.livro.reler_depois == [0] and j.livro.pode_retomar

    respostas["pergunta"] = SIM                          # sem o que faltou: "ler essas agora?"
    j.retomar_lote()
    _esperar(app, j)
    assert "Ler essas agora?" in respostas["texto"] and "Não lê" not in respostas["texto"]
    assert j.livro.reler_depois == [] and not j.livro.pode_retomar
    assert _o_r_manual(j.projeto)                        # a correção à mão ficou (§4.6)
    assert j.projeto.antes_do_lote.tem(0)                # e a página de antes, guardada


def test_voltar_ao_antes_do_lote_pergunta_com_a_data_da_copia_e_desfaz_o_que_veio_depois(
        app, lote_parado, respostas):
    j = lote_parado
    respostas["pergunta"] = SIM                          # retoma lendo também a 1ª
    j.retomar_lote()
    _esperar(app, j)
    assert not j.livro.pode_retomar and j.projeto.antes_do_lote.tem(0)
    j.ir_para_pagina(0)
    p = j.pagina
    gid = next(b.gid for b in p.modelo.boxes if b.entry.char != "R")
    p.escolher(gid)
    p.corrigir("Z")                                      # mudada depois do lote

    respostas["pergunta"] = NAO
    j.voltar_ao_antes_do_lote()
    copia = j.projeto.antes_do_lote.data(0)
    assert f"(a cópia de {copia:%d/%m/%Y às %H:%M})" in respostas["texto"]
    assert p.box(gid).char == "Z" and j.projeto.antes_do_lote.tem(0)

    respostas["pergunta"] = SIM
    j.voltar_ao_antes_do_lote()
    assert p.box(gid).char != "Z" and not j.projeto.antes_do_lote.tem(0)
    assert _o_r_manual(j.projeto)                        # a de antes do lote tinha o "R"


def test_a_pagina_nao_lida_mostra_a_saude_da_amostra_no_documento(app, tmp_path, respostas):
    """§9.1: com a amostra guiada lida, a página ainda não reconhecida mostra no Documento os
    pendentes de cada página da amostra, antes e agora, e o que fazer; com o limiar
    escolhido na gaveta acima dos pendentes, a amostra está pronta."""
    projeto, pagina, livro, executor = _livro_sem_janela(tmp_path)
    projeto.dados.extras.update(amostra_guiada_pendente=True, intervalo_do_corpo=[0, 2],
                                candidatos_da_amostra_guiada=[0, 1])
    projeto.salvar()
    assert livro.iniciar_amostra_guiada()
    executor.tudo()
    saude = lv.saude(projeto)
    assert saude.paginas == (0, 1) and saude.pendentes_agora > saude.limiar
    j = _reaberto(projeto)
    try:
        j.ir_para_pagina(2)
        j.pintar_texto()
        texto = j.texto.toPlainText()
        (_p0, antes0, agora0), (_p1, antes1, agora1) = saude.por_pagina
        assert texto.startswith("Saúde do livro: a amostra, pendentes antes → agora\n"
                                f"  p. 1: {antes0} → {agora0}\n  p. 2: {antes1} → {agora1}\n"
                                f"  total: {saude.pendentes_antes} → {saude.pendentes_agora} · "
                                "0 amostras ensinadas\n"
                                f"Revise a amostra até restarem {saude.limiar} pendentes ou menos")
        assert "Página não reconhecida" in texto
        j.paginas.limiar_da_saude.setValue(saude.pendentes_agora)      # na gaveta
        j.pintar_texto()
        assert "A amostra está pronta:" in j.texto.toPlainText()
        assert "reconhece o livro inteiro" in j.texto.toPlainText()
    finally:
        j.close()
