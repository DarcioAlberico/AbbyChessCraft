"""O registro dos gestos do usuário, para a medida humana da fatia (SPEC §15.4, CA-F.2).

Ligado só quando a variável `ABBY_REGISTRO_DE_EVENTOS` aponta para um arquivo: cada gesto
vira uma linha JSON com o instante monotônico em segundos, o tipo e o nome da classe do
widget. Não grava o texto digitado nem a tecla: só que houve um gesto, e quando.
`ferramentas/tempo_da_fatia.py` soma o tempo, descontando os intervalos ociosos de mais de
60 s.

O que é um gesto (`tipo_do_gesto`) é a convenção do catálogo de
`ferramentas/replay/comandos.yaml`, e é a mesma função que o teste dos custos do catálogo
usa: a regra que confere o custo é a regra que mede a pessoa.
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


def tipo_do_gesto(evento) -> Optional[str]:
    """'atalho', 'clique', 'tecla' ou `None` (não é gesto).

    A tecla de um atalho chega como `Shortcut`, não como `KeyPress`; o evento que sobe do
    widget filho para o pai não é espontâneo e não conta de novo; a tecla modificadora
    sozinha não conta, porque um acorde é um gesto só.
    """
    tipo = evento.type()
    if tipo == QEvent.Type.Shortcut:
        return "atalho"
    if not evento.spontaneous():
        return None
    if tipo == QEvent.Type.MouseButtonPress:
        return "clique"
    if tipo == QEvent.Type.KeyPress and evento.key() not in _MODIFICADORES:
        return "tecla"
    return None


class RegistroDeEventos(QObject):
    def __init__(self, caminho: str):
        super().__init__()
        self._arquivo = open(caminho, "a", encoding="utf-8", newline="\n")
        self._escrever({"evento": "inicio", "relogio": time.time()})

    def _escrever(self, dados: dict) -> None:
        if self._arquivo is None:           # fechado: um evento atrasado não derruba nada
            return
        dados = {"t": round(time.monotonic(), 3), **dados}
        self._arquivo.write(json.dumps(dados, ensure_ascii=False) + "\n")
        self._arquivo.flush()

    def eventFilter(self, objeto, evento):
        gesto = tipo_do_gesto(evento)
        if gesto is not None:
            self._escrever({"evento": gesto, "widget": type(objeto).__name__})
        return False

    def fechar(self) -> None:
        if self._arquivo is None:
            return
        self._escrever({"evento": "fim", "relogio": time.time()})
        self._arquivo.close()
        self._arquivo = None


def instalar(app) -> Optional[RegistroDeEventos]:
    """Liga o registro na aplicação se a variável estiver definida; senão, nada."""
    caminho = os.environ.get(VARIAVEL)
    if not caminho:
        return None
    registro = RegistroDeEventos(caminho)
    app.installEventFilter(registro)
    app.aboutToQuit.connect(registro.fechar)
    return registro
