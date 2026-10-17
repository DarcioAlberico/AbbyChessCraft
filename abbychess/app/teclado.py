"""Os atalhos da janela, registrados a partir de `docs/atalhos.yaml` (SPEC §3.4, CA-3.7).

Cada ação do YAML vira uma `QAction` com o nome do id (`objectName`), as sequências do perfil
e o contexto do escopo: `global` vale na janela inteira (`WindowShortcut`); os demais valem
com o foco dentro dos widgets do escopo (`WidgetWithChildrenShortcut`), que quem registra
passa. Só as ações com `desde_passo` até `PASSO` são registradas com atalho; o teste da
janela confere que o conjunto é exatamente esse.

Nos widgets em que a ligação nativa vence (o campo de um caractere do Glifo: Enter, Delete,
Shift+seta, a exceção 6 de §3.4), a tecla não dispara o atalho: chega ao `keyPressEvent`
do widget, que dispara a mesma ação (`AcoesDaTecla`).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, Iterable, List, Optional

from PySide6.QtCore import QEvent, QKeyCombination, Qt
from PySide6.QtGui import QAction, QKeySequence

from abbychess import atalhos

#: O passo do roadmap do programa: as ações do YAML até ele têm atalho.
PASSO = "E"
#: O perfil de teclado (o FineReader e a escolha em Opções são do passo K).
PERFIL = "padrao"

#: Grafias do YAML que o `QKeySequence` escreve de outro jeito.
_PARA_QT = {"PgDn": "PgDown", "Enter": "Return", "Delete": "Del"}


@lru_cache(maxsize=1)
def tabela() -> atalhos.Tabela:
    return atalhos.carregar()


def para_qt(sequencia: str) -> QKeySequence:
    """`Ctrl+PgDn` (normalizada) → `QKeySequence("Ctrl+PgDown")`."""
    partes, tecla = atalhos._partir(sequencia)
    return QKeySequence("+".join(partes + [_PARA_QT.get(tecla, tecla)]))


def do_qt(sequencia: QKeySequence) -> str:
    """O inverso, para comparar com o YAML: `Ctrl+PgDown` → `Ctrl+PgDn`."""
    return atalhos.normalizar(sequencia.toString(QKeySequence.SequenceFormat.PortableText))


def ativa(id_: str) -> bool:
    """A ação já tem atalho neste passo."""
    acao = tabela().da_acao(id_)
    passos = tabela().passos
    return passos.index(acao.desde_passo) <= passos.index(PASSO)


def sequencias(id_: str) -> List[QKeySequence]:
    if not ativa(id_):
        return []
    return [para_qt(s) for s in tabela().da_acao(id_).sequencias.get(PERFIL, [])]


def acao(janela, id_: str, funcao, *, texto: Optional[str] = None,
         widgets: Iterable = (), barra=None, marcavel: bool = False) -> QAction:
    """A `QAction` do id, ligada a `funcao`. `widgets`: onde vale, se o escopo não é global."""
    yaml = tabela().da_acao(id_)
    q = QAction(texto or yaml.descricao, janela)
    q.setObjectName(id_)
    q.setShortcuts(sequencias(id_))
    q.setCheckable(marcavel)
    widgets = list(widgets)
    if yaml.escopo == ["global"]:
        q.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        janela.addAction(q)
    else:
        q.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        for w in widgets:
            w.addAction(q)
    q.triggered.connect(funcao)                 # não o toggled: um setChecked não comanda
    if barra is not None:
        barra.addAction(q)
    return q


def sem_atalho(janela, texto: str, funcao) -> QAction:
    """Uma ação só de menu, fora do YAML (sem tecla)."""
    q = QAction(texto, janela)
    q.triggered.connect(funcao)
    return q


class AcoesDaTecla:
    """As teclas que um widget de ligação nativa vencedora toma para si e passa às ações:
    o `event` dele aceita o `ShortcutOverride` dessas teclas e o `keyPressEvent` as dispara."""

    def __init__(self):
        self._acoes: Dict[str, QAction] = {}

    def ligar(self, q: QAction) -> None:
        for s in q.shortcuts():
            self._acoes[do_qt(s)] = q

    def _da(self, evento) -> Optional[QAction]:
        """A ação da tecla do evento. O teclado numérico conta como o principal: o Enter dele
        ensina como o Return, e as setas dele movem as bordas."""
        modificadores = evento.modifiers() & ~Qt.KeyboardModifier.KeypadModifier
        tecla = Qt.Key.Key_Return if evento.key() == Qt.Key.Key_Enter else Qt.Key(evento.key())
        try:
            nome = do_qt(QKeySequence(QKeyCombination(modificadores, tecla)))
        except ValueError:                      # uma tecla sem nome (um modificador sozinho)
            return None
        return self._acoes.get(nome)

    def sobrepor(self, evento) -> bool:
        """No `event`: o `ShortcutOverride` de uma tecla nossa fica com o widget."""
        if evento.type() == QEvent.Type.ShortcutOverride and self._da(evento) is not None:
            evento.accept()
            return True
        return False

    def disparar(self, evento) -> bool:
        """No `keyPressEvent`: a tecla nossa dispara a ação (se ligada) e não segue."""
        q = self._da(evento)
        if q is None:
            return False
        if q.isEnabled():
            q.trigger()
        return True
