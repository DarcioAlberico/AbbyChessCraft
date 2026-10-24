"""Os tokens da aparência (§13, passo K): CA-13.2 (contraste e traços) e CA-13.3 (o tema
troca sem reiniciar; nenhuma cor literal em `app/` fora de `estilo.py`)."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter, QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication, QGraphicsScene, QLabel  # noqa: E402

from core.box_model import BoxEntry  # noqa: E402

from abbychess import grade as gd  # noqa: E402
from abbychess.app import estilo  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
APP = RAIZ / "abbychess" / "app"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tema_claro_no_fim(app):
    """O teste aplica temas no app único: no fim, a paleta e a folha de antes voltam."""
    paleta, folha = app.palette(), app.styleSheet()
    yield
    estilo.aplicar(app, "claro")
    app.setPalette(paleta)
    app.setStyleSheet(folha)


def _papel_de_referencia() -> QColor:
    """O fundo do índice 25 do livro de referência, gravado no gabarito (CA-13.2)."""
    g = json.loads((RAIZ / "tests" / "verdade" / "xv" / "i025.json").read_text(encoding="utf-8"))
    return QColor(g["papel"], g["papel"], g["papel"])


# ----------------------------------------------------------------------
# CA-13.2
# ----------------------------------------------------------------------

#: Os estados que chamam o olho e os traços da origem (com V): os aceitos discretos ficam
#: de fora de propósito (§3.3).
ESTADOS = [estilo.TRACOS[gd.PENDENTE], estilo.TRACOS[gd.SEM_LEITURA],
           estilo.TRACOS[gd.AGUARDANDO], *estilo.TRACOS_DA_ORIGEM.values()]


@pytest.mark.parametrize("papel", ["referencia", "escuro"])
def test_ca_13_2_contraste_dos_estados_contra_o_papel(papel):
    fundo = _papel_de_referencia() if papel == "referencia" else estilo.PAPEL_ESCURO
    tokens = [t.cor for t in ESTADOS] + [
        estilo.DIAGRAMA_POR_LER, estilo.DIAGRAMA_A_CONFERIR, estilo.DIAGRAMA_CONFIAVEL,
        estilo.DIAGRAMA_CONFERIDO, estilo.CONTORNO_DA_SELECAO, estilo.MARCADO, estilo.PALAVRA]
    baixos = [(c.name(), round(estilo.contraste(c, fundo), 2)) for c in tokens
              if estilo.contraste(c, fundo) < 3.0]
    assert baixos == []


def test_ca_13_2_cada_estado_com_traco_distinto():
    estilos = [t.estilo for t in ESTADOS]
    assert len(set(estilos)) == len(estilos)
    assert all(t.largura >= 1.5 for t in ESTADOS)
    personalizados = [t for t in ESTADOS if t.estilo == Qt.PenStyle.CustomDashLine]
    assert all(t.padrao for t in personalizados)


def test_o_contraste_wcag_confere_com_valores_conhecidos():
    assert round(estilo.contraste(QColor(0, 0, 0), QColor(255, 255, 255)), 1) == 21.0
    assert round(estilo.contraste(QColor(119, 119, 119), QColor(255, 255, 255)), 2) == 4.48


# ----------------------------------------------------------------------
# CA-13.3
# ----------------------------------------------------------------------

def _cores_literais(arquivo: Path):
    """As cores escritas à mão no arquivo: `QColor(<constantes>)`, `Qt.GlobalColor.x` e
    `#rrggbb` ou `color:` dentro de texto."""
    import re

    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    achadas = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call) and getattr(no.func, "id", getattr(no.func, "attr", "")) == "QColor":
            if no.args and all(isinstance(a, ast.Constant) for a in no.args):
                achadas.append((no.lineno, ast.unparse(no)))
        elif isinstance(no, ast.Attribute) and isinstance(no.value, ast.Attribute) \
                and no.value.attr == "GlobalColor":
            achadas.append((no.lineno, ast.unparse(no)))
        elif isinstance(no, ast.Constant) and isinstance(no.value, str) and (
                re.search(r"#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?\b", no.value)
                or re.search(r"(?:color|background|border)[^;:]*:[^;{]*\b(?:white|black|gr[ae]y|red|"
                             r"blue|green|yellow|orange)\b", no.value)
                or re.search(r"\bcolor\s*:\s*[#a-z]", no.value)):
            achadas.append((no.lineno, no.value[:60]))
    return achadas


def test_ca_13_3_nenhuma_cor_literal_fora_de_estilo():
    achadas = {a.name: _cores_literais(a) for a in sorted(APP.glob("*.py")) if a.name != "estilo.py"}
    assert {nome: lista for nome, lista in achadas.items() if lista} == {}


def test_a_varredura_acha_uma_cor_literal(tmp_path):
    exemplo = tmp_path / "x.py"
    exemplo.write_text('a = QColor(1, 2, 3)\nb = Qt.GlobalColor.black\nc = "color: #123456;"\n'
                       "d = QColor(outra)\n"
                       'e = "background: white; border: 1px solid #999;"\n'
                       'f = f"background: {x}; border: 1px solid {y};"\n', encoding="utf-8")
    assert [linha for linha, _ in _cores_literais(exemplo)] == [1, 2, 3, 5]


def test_ca_13_3_trocar_o_tema_troca_a_paleta_sem_reiniciar(app, monkeypatch, tema_claro_no_fim):
    from abbychess.app.documento import VistaDoDocumento

    documento = VistaDoDocumento()
    rotulo = QLabel("dica")
    estilo.papel(rotulo, "dica")
    monkeypatch.setattr(estilo, "tema_do_sistema", lambda: "escuro")
    estilo.aplicar(app)                         # o que o colorSchemeChanged dispara
    assert estilo.tema() is estilo.ESCURO
    assert app.palette().color(QPalette.ColorRole.Window) == estilo.ESCURO.janela
    assert estilo.ESCURO.texto_secundario.name() in app.styleSheet()
    # O livro não inverte: o Documento continua papel.
    assert documento.palette().color(QPalette.ColorRole.Base) == estilo.PAPEL
    assert documento.palette().color(QPalette.ColorRole.Text) == estilo.TINTA
    monkeypatch.setattr(estilo, "tema_do_sistema", lambda: "claro")
    estilo.aplicar(app)
    assert app.palette().color(QPalette.ColorRole.Window) == estilo.CLARO.janela
    assert rotulo.property("papel") == "dica"


def test_papel_desconhecido_e_recusado(app):
    with pytest.raises(ValueError):
        estilo.papel(QLabel(), "roxo")


def test_os_temas_tem_texto_legivel():
    for t in (estilo.CLARO, estilo.ESCURO):
        assert estilo.contraste(t.texto, t.base) >= 7.0
        assert estilo.contraste(t.texto_secundario, t.base) >= 4.5
        for campo in ("erro", "aviso", "acerto", "link"):
            assert estilo.contraste(getattr(t, campo), t.janela) >= 4.5, (t.nome, campo)


# ----------------------------------------------------------------------
# As pendências do A1
# ----------------------------------------------------------------------

def _pintar(escala: float) -> QImage:
    from abbychess.app.item_dos_boxes import ItemDosBoxes

    item = ItemDosBoxes(200, 200)
    item.trocar([BoxEntry("a", 50, 50, 150, 150, 0.1, "manual")], [gd.PENDENTE])
    cena = QGraphicsScene(0, 0, 200, 200)
    cena.addItem(item)
    lado = round(200 * escala)
    imagem = QImage(lado, lado, QImage.Format.Format_RGB32)
    imagem.fill(estilo.PAPEL)
    pintor = QPainter(imagem)
    cena.render(pintor, QRectF(0, 0, lado, lado), QRectF(0, 0, 200, 200))
    pintor.end()
    return imagem


def test_em_zoom_baixo_o_box_pendente_e_so_contorno(app):
    perto, longe = _pintar(1.0), _pintar(0.3)
    assert perto.pixelColor(100, 100) != estilo.PAPEL          # preenchido a 100%
    assert longe.pixelColor(30, 30) == estilo.PAPEL            # o meio limpo a 30%


def test_a_selecao_tem_contorno_duplo(app):
    from abbychess.app.visor import VisorDePagina

    visor = VisorDePagina()
    visor.mostrar_boxes([BoxEntry("a", 10, 10, 30, 30, 1.0, "manual")], set())
    visor.selecionar(0)
    fora = visor._destaque
    [dentro] = fora.childItems()
    assert fora.pen().color() == estilo.CONTORNO_DA_SELECAO
    assert dentro.pen().color() == estilo.SELECIONADO
    assert fora.pen().widthF() > dentro.pen().widthF()
    visor.selecionar(None)
    assert visor._destaque is None


# ----------------------------------------------------------------------
# A revisão de código (rodada 1)
# ----------------------------------------------------------------------

def test_cores_de_estado_na_interface_escura_ficam_legiveis(app, tema_claro_no_fim):
    estados = [estilo.CINZA, estilo.ROXO_AVERMELHADO, estilo.LARANJA, estilo.VERMELHAO,
               estilo.VERDE_AZULADO]
    assert [estilo.na_interface(c) for c in estados] == estados       # no claro, as mesmas
    estilo.aplicar(app, "escuro")
    for c in estados:
        assert estilo.contraste(estilo.na_interface(c), estilo.ESCURO.base) >= 4.5, c.name()


def test_o_tema_novo_e_avisado(app, tema_claro_no_fim):
    recebidos = []
    estilo.avisos().tema_mudou.connect(recebidos.append)
    try:
        estilo.aplicar(app, "escuro")
        estilo.aplicar(app, "claro")
    finally:
        estilo.avisos().tema_mudou.disconnect(recebidos.append)
    assert recebidos == ["escuro", "claro"]

