"""O modo do arraste à vista (SPEC-pagina-perfeita U-2, CA-U2): enquanto marcar glifo, o editor
de áreas ou a borracha estão ligados, a barra de status mostra um rótulo fixo ("Borracha · Esc
sai"), e o Esc sai do modo (pela ordem de `fechar_sobreposicao`, §3.4 regra 4).

O aviso que cada modo dá ao ligar passa em alguns segundos; o rótulo fica enquanto o modo
estiver ligado. O cursor de cada modo é do visor (`VisorDePagina._cursor_do_modo`). Um objeto
à parte, e não um mixin da janela (roadmap da página perfeita, T4).
"""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QLabel
from shiboken6 import isValid

from abbychess.app import estilo, teclado


class ModoDoArraste(QObject):
    """O rótulo do modo ligado e a saída pelo Esc, para as três ações de modo da janela."""

    def __init__(self, janela):
        super().__init__(janela)
        self.janela = janela
        self.rotulo = QLabel("")
        self.rotulo.setAccessibleName("O modo do arraste ligado na Imagem")
        estilo.papel(self.rotulo, "aviso")
        janela.statusBar().addPermanentWidget(self.rotulo)
        self.rotulo.hide()
        for _nome, acao in self._modos():
            acao.toggled.connect(self._mudou)
        teclado.quando_mudar(self.atualizar)

    def _modos(self):
        j = self.janela
        return (("Marcar glifo", j.acao_modo_treino), ("Editor de áreas", j.acao_areas),
                ("Borracha", j.acao_borracha))

    def ligado(self) -> Optional[Tuple[str, object]]:
        """(nome, ação) do modo ligado, ou None."""
        return next(((nome, acao) for nome, acao in self._modos() if acao.isChecked()), None)

    def sair(self) -> bool:
        """O Esc: desliga o modo ligado (pela ação, como o clique no botão). Falso sem modo."""
        modo = self.ligado()
        if modo is None:
            return False
        modo[1].trigger()
        return True

    def _mudou(self, *_args) -> None:
        if isValid(self) and isValid(self.rotulo):
            self.atualizar()

    def atualizar(self) -> None:
        modo = self.ligado()
        if modo is None:
            self.rotulo.hide()
            return
        self.rotulo.setText(f"{modo[0]} · {teclado.tecla('fechar_sobreposicao', 'Esc')} sai")
        self.rotulo.show()
