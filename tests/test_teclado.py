"""O perfil de teclado e a troca de atalhos (SPEC §3.4, passo K): CA-3.3 e CA-3.7 também no
perfil FineReader, as trocas pelas mesmas regras do YAML, a troca valendo sem reiniciar e o
perfil lembrado no `QSettings` (o dos testes é um INI temporário, `tests/conftest.py`)."""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QAction, QKeySequence  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from abbychess import zonas as zn  # noqa: E402
from abbychess.app import teclado  # noqa: E402
from abbychess.app.janela import configuracao  # noqa: E402
from abbychess.projeto import ProjetoDeLivro  # noqa: E402

from tests.test_espaco import _abrir, _dentro, conferir_os_registrados  # noqa: E402
from tests.test_janela import _esperar  # noqa: E402
from tests.test_treino_por_livro import _pagina_sintetica  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def perfil_limpo():
    """Cada teste começa e termina no perfil padrão, sem trocas gravadas."""
    config = configuracao()
    # O INI temporário do conftest: apagar aqui nunca toca o registro de quem roda a suíte.
    assert config.format() == QSettings.Format.IniFormat
    config.remove("teclado")
    teclado.definir("padrao")
    yield config
    config.remove("teclado")
    teclado.definir("padrao")


@pytest.fixture
def sim(monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)


def _janela(app, tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Teste",
                                   _pagina_sintetica(tmp_path / "pagina.png"))
    return _abrir(projeto)


@pytest.fixture
def finereader(app, tmp_path, sim, perfil_limpo):
    """A janela aberta com o perfil FineReader gravado (como o usuário o deixou)."""
    teclado.definir("finereader")
    teclado.gravar(perfil_limpo)
    teclado.definir("padrao")                   # quem escolhe é o `carregar` da janela
    j = _janela(app, tmp_path)
    yield j
    j.close()


@pytest.fixture
def padrao(app, tmp_path, sim):
    j = _janela(app, tmp_path)
    yield j
    j.close()


# ----------------------------------------------------------------------
# As regras das trocas (as do YAML, §3.4)
# ----------------------------------------------------------------------

def test_os_dois_perfis_sem_troca_passam_nas_regras():
    assert teclado.problemas("padrao", {}) == []
    assert teclado.problemas("finereader", {}) == []


def test_troca_que_colide_no_mesmo_contexto_e_recusada():
    problemas = teclado.problemas("padrao", {"proximo_diagrama": ["F5"]})
    assert problemas and any("F5" in p for p in problemas)
    # A mesma tecla noutro perfil não colide (no FineReader o F5 é de Páginas, e o
    # reconhecer é Ctrl+F9): só o perfil da troca conta.
    assert teclado.problemas("padrao", {"proximo_diagrama": ["Ctrl+Shift+F12"]}) == []


@pytest.mark.parametrize("troca, trecho", [
    ({"localizar": ["Ctrl+Xyz"]}, "localizar"),                 # tecla que não se escreve
    ({"nao_existe": ["F12"]}, "ação desconhecida"),
    ({"localizar": ["Ctrl+Alt+F"]}, "Ctrl+Alt"),                # AltGr nos teclados ABNT
])
def test_troca_ruim_e_recusada_com_o_motivo(troca, trecho):
    problemas = teclado.problemas("padrao", troca)
    assert problemas and any(trecho in p for p in problemas), problemas


def test_perfil_desconhecido_e_recusado():
    assert teclado.problemas("emacs", {}) == ["perfil desconhecido: 'emacs'"]
    with pytest.raises(ValueError):
        teclado.definir("emacs")


def test_definir_com_tecla_ruim_nao_muda_nada():
    teclado.definir("padrao", {"proximo_diagrama": ["Ctrl+Shift+F12"]})
    with pytest.raises(ValueError):
        teclado.definir("finereader", {"localizar": ["Ctrl+Xyz"]})
    assert (teclado.PERFIL, teclado.trocas) == ("padrao", {"proximo_diagrama": ["Ctrl+Shift+F12"]})


def test_as_trocas_do_perfil_em_uso_nao_valem_no_outro():
    teclado.definir("finereader", {"localizar": ["Ctrl+Shift+F12"]})
    assert teclado.sequencias_do_perfil("localizar") == ["Ctrl+Shift+F12"]
    assert teclado.sequencias_do_perfil("localizar", "padrao") == ["Ctrl+F"]
    assert teclado.sequencias_do_perfil("localizar", "padrao", {"localizar": ["F12"]}) == ["F12"]


def test_tirar_a_tecla_e_uma_troca_valida():
    assert teclado.problemas("padrao", {"proximo_diagrama": []}) == []
    teclado.definir("padrao", {"proximo_diagrama": []})
    assert teclado.sequencias("proximo_diagrama") == []


# ----------------------------------------------------------------------
# O perfil lembrado
# ----------------------------------------------------------------------

def test_o_perfil_e_as_trocas_voltam_do_qsettings(tmp_path):
    config = QSettings(str(tmp_path / "c.ini"), QSettings.Format.IniFormat)
    trocas = {"proximo_diagrama": ["Ctrl+Shift+F12"], "localizar": ["Ctrl+F", "Ctrl+Shift+F11"],
              "substituir": []}
    teclado.definir("finereader", trocas)
    teclado.gravar(config)
    teclado.definir("padrao")
    fora = teclado.carregar(QSettings(str(tmp_path / "c.ini"), QSettings.Format.IniFormat))
    assert fora == [] and teclado.PERFIL == "finereader" and teclado.trocas == trocas
    assert teclado.sequencias_do_perfil("reconhecer_pagina") == ["Ctrl+F9"]


def test_cada_troca_gravada_vale_sozinha(tmp_path):
    """Uma ação que saiu do YAML, ou uma tecla que passou a colidir, não leva as outras."""
    config = QSettings(str(tmp_path / "c.ini"), QSettings.Format.IniFormat)
    config.setValue(teclado.CHAVE_DO_PERFIL, "padrao")
    config.setValue(teclado.CHAVE_DAS_TROCAS, json.dumps({
        "acao_que_saiu": ["F12"], "proximo_diagrama": ["F5"],          # colide com reconhecer
        "localizar": ["Ctrl+Shift+F11"]}))
    assert teclado.carregar(config) == ["acao_que_saiu", "proximo_diagrama"]
    assert teclado.trocas == {"localizar": ["Ctrl+Shift+F11"]}


@pytest.mark.parametrize("perfil, trocas, fica", [
    ("finereader", "{estragado", "finereader"),
    ("finereader", json.dumps({"proximo_diagrama": ["Ctrl+F9"]}), "finereader"),  # colide
    ("finereader", json.dumps({"proximo_diagrama": "F12"}), "finereader"),         # não é lista
    ("finereader", json.dumps({"proximo_diagrama": [12]}), "finereader"),
    ("emacs", "{}", "padrao"),
    ("padrao", json.dumps(["não", "é", "mapa"]), "padrao"),
])
def test_o_que_foi_gravado_estragado_fica_de_lado(tmp_path, perfil, trocas, fica):
    """O perfil conhecido fica; as trocas ruins não valem (e o programa abre do mesmo jeito)."""
    config = QSettings(str(tmp_path / "c.ini"), QSettings.Format.IniFormat)
    config.setValue(teclado.CHAVE_DO_PERFIL, perfil)
    config.setValue(teclado.CHAVE_DAS_TROCAS, trocas)
    teclado.carregar(config)
    assert (teclado.PERFIL, teclado.trocas) == (fica, {})


# ----------------------------------------------------------------------
# CA-3.3 e CA-3.7 no perfil FineReader
# ----------------------------------------------------------------------

def test_no_finereader_os_atalhos_registrados_sao_os_do_yaml(finereader):
    assert teclado.PERFIL == "finereader"
    conferir_os_registrados(finereader)
    assert finereader.acao_reconhecer.shortcut().toString() == "Ctrl+F9"
    assert "Ctrl+F9" in finereader.acao_reconhecer.toolTip()


def test_no_finereader_alt_n_poe_o_foco_no_painel_certo(app, finereader):
    j = finereader
    j.reconhecer()
    _esperar(app, j)
    paineis = {1: j.paginas, 2: j.visor, 3: j.vista, 4: j.linha, 5: j.inspetor, 6: j.resultados}
    for n, painel in paineis.items():
        QTest.keyClick(QApplication.focusWidget() or j, getattr(Qt.Key, f"Key_{n}"),
                       Qt.KeyboardModifier.AltModifier)
        app.processEvents()
        assert _dentro(painel), (n, QApplication.focusWidget())
    assert j.linha.isVisible()                  # Alt+4 mostra a Linha escondida


def test_no_finereader_ctrl_tab_anda_pelos_paineis(app, finereader):
    j = finereader
    j.focar(2)
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
    assert _dentro(j.vista)
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Backtab,
                   Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    assert _dentro(j.visor)


def test_no_finereader_ctrl_2_faz_da_zona_um_diagrama(app, finereader):
    j = finereader
    j.acao_areas.setChecked(True)
    j.modo_areas(True)
    _esperar(app, j)
    zona = j.areas.zonas[0]
    j.visor.apertar_no_editor_de_areas(QPointF((zona.x1 + zona.x2) / 2, (zona.y1 + zona.y2) / 2))
    j.visor.soltar_arraste(QPointF((zona.x1 + zona.x2) / 2, (zona.y1 + zona.y2) / 2))
    app.processEvents()
    assert j.areas.atual == 0 and all(q.isEnabled() for q in j.acoes_dos_tipos)
    assert j.areas.zonas[0].tipo != zn.DIAGRAMA              # a tecla é que muda
    j.visor.setFocus()
    QTest.keyClick(j.visor, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier)
    assert j.areas.zonas[0].tipo == zn.DIAGRAMA


# ----------------------------------------------------------------------
# A troca vale sem reiniciar
# ----------------------------------------------------------------------

def test_trocar_o_perfil_reaplica_as_teclas_e_as_dicas(app, padrao):
    j = padrao
    j.acao_diagramas.setToolTip("dica escrita à mão")
    assert j.acao_reconhecer.shortcut().toString() == "F5"
    ids = {a.id for a in teclado.tabela().acoes}
    esperado = sum(1 for q in j.findChildren(QAction) if q.objectName() in ids
                   and teclado.sequencias_do_perfil(q.objectName(), "padrao", {})
                   != teclado.sequencias_do_perfil(q.objectName(), "finereader", {}))
    teclado.definir("finereader")
    assert teclado.reaplicar(j) == esperado > 0
    conferir_os_registrados(j)
    assert "Ctrl+F9" in j.acao_reconhecer.toolTip()
    assert j.acao_diagramas.toolTip() == "dica escrita à mão"    # a dica própria fica
    teclado.definir("padrao", {"reconhecer_pagina": ["Ctrl+Shift+F12"]})
    teclado.reaplicar(j)
    assert [s.toString() for s in j.acao_reconhecer.shortcuts()] == ["Ctrl+Shift+F12"]
    from abbychess.app import vazios

    assert "Ctrl+Shift+F12 reconhece" in vazios.pagina_nao_reconhecida()


def test_o_mapa_dos_widgets_de_ligacao_nativa_segue_a_troca(app):
    q = QAction("teste")
    q.setShortcut(QKeySequence("Return"))
    teclas = teclado.AcoesDaTecla()
    teclas.ligar(q)
    assert set(teclas._acoes) == {"Enter"}
    q.setShortcut(QKeySequence("Ctrl+Return"))
    teclas.religar()
    assert set(teclas._acoes) == {"Ctrl+Enter"}


def test_o_menu_teclado_grava_e_reaplica(app, padrao, perfil_limpo, monkeypatch):
    from abbychess.app import dialogo_teclado

    monkeypatch.setattr(dialogo_teclado, "perguntar", lambda _j: ("finereader", {}))
    padrao.acao_teclado.trigger()
    assert teclado.PERFIL == "finereader"
    assert padrao.acao_reconhecer.shortcut().toString() == "Ctrl+F9"
    assert configuracao().value(teclado.CHAVE_DO_PERFIL) \
        == "finereader"
    assert padrao.acao_teclado in padrao.menu_ferramentas.actions()


#: Teclas novas para ações que os painéis citam (nenhuma é usada no perfil padrão).
TROCAS_VISIVEIS = {"reconhecer_pagina": ["Ctrl+Shift+F12"], "paleta": ["Ctrl+Shift+F11"],
                   "proxima_ocorrencia": ["Ctrl+Shift+F9"], "dividir": ["Ctrl+Shift+F6"],
                   "proximo_da_fila": ["Ctrl+Shift+F4"]}


def _textos_da_janela(j):
    """Todo texto que a janela mostra ou dá ao leitor de tela, com o widget de cada um."""
    from PySide6.QtWidgets import QAbstractButton, QGroupBox, QLabel, QWidget

    textos = []
    for w in [j, *j.findChildren(QWidget)]:
        textos += [(w, w.toolTip()), (w, w.accessibleName())]
        if isinstance(w, (QAbstractButton, QLabel)):
            textos.append((w, w.text()))
        if isinstance(w, QGroupBox):
            textos.append((w, w.title()))
    textos += [(q, q.toolTip()) for q in j.findChildren(QAction)]
    textos.append((j.visor, j.visor.mensagem_vazia))
    return textos


def test_trocar_a_tecla_muda_todo_texto_que_a_cita_com_a_janela_aberta(app, padrao):
    """O que cita tecla (dicas, nomes acessíveis, rótulos, o estado vazio) segue a troca sem
    reiniciar: nenhum texto fica com a tecla velha nem com um `{id}` sem trocar."""
    import re

    assert teclado.problemas("padrao", TROCAS_VISIVEIS) == []
    antes = " ".join(t for _w, t in _textos_da_janela(padrao))
    assert re.search(r"(?<![\w+])F5\b", antes) and re.search(r"(?<![\w+])F2\b", antes)
    teclado.definir("padrao", TROCAS_VISIVEIS)
    teclado.reaplicar(padrao)
    textos = _textos_da_janela(padrao)
    velhas = re.compile(r"(?<![\w+])(F5|F2|F3)\b|(?<![\w+])Ctrl\+D\b|Alt\+(Down|↓)")
    sobrou = [(type(w).__name__, t) for w, t in textos if velhas.search(t)]
    assert sobrou == []
    assert [t for _w, t in textos if teclado.MARCA_DE_TECLA.search(t)] == []
    juntos = " ".join(t for _w, t in textos)
    for (tecla,) in TROCAS_VISIVEIS.values():
        assert tecla in juntos, tecla
    # O estado vazio também: a página aberta e não reconhecida, no Glifo.
    assert "Ctrl+Shift+F12 reconhece" in padrao.treino.leitura.text()


def test_todo_modelo_de_texto_cita_acao_do_yaml():
    """Os `{id}` escritos no código (dicas, avisos dos controladores) são ações do YAML: um
    erro de digitação viraria `KeyError` na hora de mostrar."""
    import ast
    from pathlib import Path

    import abbychess

    raiz = Path(abbychess.__file__).parent
    ids = {a.id for a in teclado.tabela().acoes}
    arquivos = [*raiz.joinpath("app").glob("*.py"), raiz / "controlador.py",
                raiz / "controladores.py"]
    citados = {}
    for arquivo in arquivos:
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        documentacao = {id(no.body[0].value) for no in ast.walk(arvore)
                        if isinstance(no, (ast.Module, ast.FunctionDef, ast.ClassDef))
                        and no.body and isinstance(no.body[0], ast.Expr)}
        for no in ast.walk(arvore):
            if (isinstance(no, ast.Constant) and isinstance(no.value, str)
                    and id(no) not in documentacao):
                for nome in teclado.MARCA_DE_TECLA.findall(no.value):
                    citados.setdefault(nome, arquivo.name)
    assert citados and {n: a for n, a in citados.items() if n not in ids} == {}


@pytest.mark.parametrize("texto, sequencias", [
    ("Ctrl+Y; Ctrl+Shift+Z", ["Ctrl+Y", "Ctrl+Shift+Z"]),
    ("Ctrl+,", ["Ctrl+,"]),                       # a vírgula é tecla, não separa
    ("Ctrl+;", ["Ctrl+;"]),                       # nem o ";" logo depois do "+"
    ("Ctrl+; F3", ["Ctrl+;", "F3"]),
    (" ; ", []),                                  # vazio: sem tecla
])
def test_o_dialogo_le_as_teclas_escritas(texto, sequencias):
    from abbychess.app.dialogo_teclado import partir

    assert partir(texto) == sequencias


def test_o_aviso_do_dialogo_diz_o_nome_das_acoes():
    from abbychess.app.dialogo_teclado import com_nomes

    problema = teclado.problemas("padrao", {"proximo_diagrama": ["F5"]})[0]
    legivel = com_nomes(problema)
    assert "proximo_diagrama" in problema and "proximo_diagrama" not in legivel
    assert "Próximo diagrama por conferir" in legivel and "F5" in legivel


# ----------------------------------------------------------------------
# O diálogo
# ----------------------------------------------------------------------

def _linha_de(dialogo, id_):
    return dialogo._ids.index(id_)


def test_o_dialogo_devolve_so_o_que_difere_do_perfil(app):
    from abbychess.app.dialogo_teclado import ACAO, TECLAS, DialogoDoTeclado

    d = DialogoDoTeclado(None, "finereader")
    assert d.trocas() == {}
    linha = _linha_de(d, "proximo_diagrama")
    assert d.tabela.item(linha, TECLAS).text() == "Ctrl+F8"
    assert d.tabela.item(linha, ACAO).flags() & Qt.ItemFlag.ItemIsEditable == Qt.ItemFlag(0)
    d.tabela.item(linha, TECLAS).setText("ctrl+shift+f12 ; ")
    assert d.escolha() == ("finereader", {"proximo_diagrama": ["Ctrl+Shift+F12"]})
    d.perfil.setCurrentIndex(d.perfil.findData("padrao"))           # trocar de perfil desfaz
    assert d.trocas() == {}
    d.deleteLater()


def test_o_dialogo_recusa_a_colisao_e_nao_fecha(app, monkeypatch):
    from abbychess.app.dialogo_teclado import TECLAS, DialogoDoTeclado

    avisos = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _p, _t, texto: avisos.append(texto))
    d = DialogoDoTeclado(None, "padrao")
    d.tabela.item(_linha_de(d, "proximo_diagrama"), TECLAS).setText("F5")
    d._aceitar()
    assert avisos and "F5" in avisos[0] and d.result() != d.DialogCode.Accepted
    d.tabela.item(_linha_de(d, "proximo_diagrama"), TECLAS).setText("Ctrl+Xyz")
    d._aceitar()
    assert len(avisos) == 2 and "Próximo diagrama" in avisos[1]
    d.deleteLater()
