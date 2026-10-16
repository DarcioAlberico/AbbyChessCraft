"""O processo filho dos testes `processo` do gravador: edita e grava até ser morto.

Fica num módulo próprio porque o `spawn` do Windows importa a função alvo pelo nome.
"""

from __future__ import annotations

import time

from core.box_model import BoxEntry

from abbychess import edicao as ed
from abbychess.modelo import RECONHECIDA, Box
from abbychess.projeto import ProjetoDeLivro


def editar_sem_parar(pasta: str, registro: str, intervalo: float, atraso: float) -> None:
    """Abre o projeto, e a cada `intervalo` segundos acrescenta à página 0 um glifo virtual
    `k` e agenda a gravação; grava `k carimbo` em `registro` (sem fsync: um processo morto
    não perde o que já escreveu no arquivo, só o que estava no buffer dele)."""
    projeto = ProjetoDeLivro.abrir(pasta)
    projeto.gravador.atraso = atraso
    pagina = projeto.pagina_para_editar(0)
    if not pagina.boxes:
        pagina.boxes = [Box(pagina.alocar(), BoxEntry("a", 10 * k, 0, 10 * k + 8, 9, 0.9, "rede"))
                        for k in range(300)]
        pagina.estado = RECONHECIDA
    with open(registro, "a", encoding="utf-8", buffering=1) as saida:
        k = 0
        while True:
            ed.virtual(pagina, str(k), pagina.boxes[0].gid)
            projeto.agendar(pagina)
            saida.write(f"{k} {time.monotonic():.6f}\n")
            k += 1
            time.sleep(intervalo)
