"""O registro de gestos da CA-F.2 e a soma do tempo ativo (`ferramentas/tempo_da_fatia.py`)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit

from abbychess.app import registro_de_eventos as re_

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import tempo_da_fatia  # noqa: E402


def test_sem_a_variavel_nada_e_instalado(monkeypatch):
    monkeypatch.delenv(re_.VARIAVEL, raising=False)
    assert re_.instalar(QApplication.instance() or QApplication([])) is None


def test_registra_gestos_sem_o_que_foi_digitado(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    destino = tmp_path / "sessao.jsonl"
    monkeypatch.setenv(re_.VARIAVEL, str(destino))
    registro = re_.instalar(app)
    campo = QLineEdit()
    campo.show()
    try:
        QTest.keyClicks(campo, "ab")
        QTest.keyClick(campo, Qt.Key.Key_A, Qt.KeyboardModifier.ShiftModifier)
        QTest.mouseClick(campo, Qt.MouseButton.LeftButton)
    finally:
        app.removeEventFilter(registro)
        registro.fechar()
        campo.close()
    linhas = [json.loads(ln) for ln in destino.read_text(encoding="utf-8").splitlines()]
    eventos = [ln["evento"] for ln in linhas]
    assert eventos[0] == "inicio" and eventos[-1] == "fim"
    assert eventos[1:-1] == ["tecla", "tecla", "tecla", "clique"]   # o Shift sozinho não conta
    assert "ab" not in destino.read_text(encoding="utf-8")


def test_tempo_ativo_desconta_as_pausas_longas():
    linhas = [json.dumps({"t": t, "evento": e}) for t, e in [
        (0.0, "inicio"), (1.0, "tecla"), (3.0, "clique"), (100.0, "tecla"), (101.5, "atalho"),
        (200.0, "fim")]]
    assert tempo_da_fatia.tempo_ativo(linhas) == {"gestos": 4, "segundos_ativos": 3.5,
                                                  "pausas_descontadas": 1}
