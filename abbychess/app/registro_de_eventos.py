"""O registro dos gestos do usuário, para a medida humana da fatia (SPEC §15.4, CA-F.2).

Ligado só quando a variável `ABBY_REGISTRO_DE_EVENTOS` aponta para um arquivo: cada gesto
(clique, tecla que não é modificador, atalho disparado), pela mesma convenção do
catálogo de `ferramentas/replay/comandos.yaml`, vira uma linha JSON com o instante
monotônico em segundos, o tipo e o nome da classe do widget. Não grava o texto digitado
nem a tecla: só que houve um gesto, e quando. `ferramentas/tempo_da_fatia.py` soma o
tempo, descontando os intervalos ociosos de mais de 60 s.
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional

from PySide6.QtCore import QEvent, QObject, Qt

VARIAVEL = "ABBY_REGISTRO_DE_EVENTOS"

_MODIFICADORES = {Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta,
                  Qt.Key.Key_AltGr}


class RegistroDeEventos(QObject):
    def __init__(self, caminho: str):
        super().__init__()
        self._arquivo = open(caminho, "a", encoding="utf-8", newline="\n")
        self._escrever({"evento": "inicio", "relogio": time.time()})

    def _escrever(self, dados: dict) -> None:
        dados = {"t": round(time.monotonic(), 3), **dados}
        self._arquivo.write(json.dumps(dados, ensure_ascii=False) + "\n")
        self._arquivo.flush()

    def eventFilter(self, objeto, evento):
        tipo = evento.type()
        if tipo == QEvent.Type.Shortcut:
            self._escrever({"evento": "atalho", "widget": type(objeto).__name__})
        elif evento.spontaneous():
            if tipo == QEvent.Type.MouseButtonPress:
                self._escrever({"evento": "clique", "widget": type(objeto).__name__})
            elif tipo == QEvent.Type.KeyPress and evento.key() not in _MODIFICADORES:
                self._escrever({"evento": "tecla", "widget": type(objeto).__name__})
        return False

    def fechar(self) -> None:
        self._escrever({"evento": "fim", "relogio": time.time()})
        self._arquivo.close()


def instalar(app) -> Optional[RegistroDeEventos]:
    """Liga o registro na aplicação se a variável estiver definida; senão, nada."""
    caminho = os.environ.get(VARIAVEL)
    if not caminho:
        return None
    registro = RegistroDeEventos(caminho)
    app.installEventFilter(registro)
    app.aboutToQuit.connect(registro.fechar)
    return registro
