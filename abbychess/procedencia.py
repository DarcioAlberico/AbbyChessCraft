"""De que amostra do livro veio a leitura de um `BoxEntry` (SPEC §4.1, a `amostra` do `Box`).

O `BoxEntry` é do core e não ganha campo novo. Enquanto a janela edita listas de
`BoxEntry` (até o passo 2a), quem lê um glifo registra aqui, para aquele objeto, o padrão
que deu a leitura, e o modelo recolhe o registro ao gravar (`modelo.reconciliar`). Um
registro vale só para o mesmo objeto, e some com ele: a chave é o `id` e o objeto é
conferido por uma referência fraca, porque um `id` pode ser reaproveitado depois que o
objeto morre.

`NENHUMA` registra que a leitura nova não veio de um padrão (e apaga a procedência velha).
"""

from __future__ import annotations

import threading
import weakref
from typing import Optional

from core.box_model import BoxEntry

#: A leitura veio da rede, da base global ou de ninguém: não há amostra do livro.
NENHUMA = ""

_registro: dict = {}
_trava = threading.Lock()


def registrar(entry: BoxEntry, amostra: Optional[str]) -> None:
    """Grava a procedência da leitura de `entry` (`None` ou `NENHUMA`: não veio do livro)."""
    chave = id(entry)

    def esquecer(_ref, chave=chave):
        with _trava:
            atual = _registro.get(chave)
            if atual is not None and atual[0]() is None:
                del _registro[chave]

    with _trava:
        _registro[chave] = (weakref.ref(entry, esquecer), amostra or NENHUMA)


def amostra_de(entry: BoxEntry) -> Optional[str]:
    """A procedência registrada: o caminho da amostra, `NENHUMA` (lida, mas não pelo livro)
    ou `None` (nada registrado para este objeto)."""
    with _trava:
        atual = _registro.get(id(entry))
    if atual is None or atual[0]() is not entry:
        return None
    return atual[1]
