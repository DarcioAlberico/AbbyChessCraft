"""O log persistente de avisos e erros (SPEC §3.1, Resultados / Avisos; CA-4.2 no A2).

Nada que o usuário precise saber some com uma mensagem de 5 s na barra: os avisos, as falhas
de tarefa, as falhas de gravação e as recusas do desfazer entram aqui, com a hora, e ficam
em `<projeto>/avisos.log` (uma linha JSON por aviso, os últimos `LIMITE`). Sem projeto, ou
num projeto só de leitura, ficam só na memória.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

from abbychess import gravacao as gv

log = logging.getLogger(__name__)

ARQUIVO = "avisos.log"
#: Quantos avisos o arquivo guarda; os mais antigos saem quando ele passa do dobro.
LIMITE = 500

#: Os tipos, do mais grave ao menos.
ERRO, AVISO = "erro", "aviso"


@dataclass(frozen=True)
class Aviso:
    quando: str          # "2026-10-16 18:40:12"
    tipo: str            # ERRO ou AVISO
    titulo: str
    texto: str

    def linha(self) -> str:
        return f"{self.quando}  {self.titulo}: {self.texto}"


class RegistroDeAvisos:
    def __init__(self):
        self.itens: List[Aviso] = []
        self._arquivo: Optional[Path] = None
        #: Quantos chegaram desde que o usuário olhou (o ⚠N da barra de status).
        self.novos = 0

    def abrir(self, pasta: Optional[Path], *, gravar: bool = True) -> None:
        """Os avisos do projeto em `pasta` (os que o arquivo tem); `gravar` falso no projeto
        só de leitura."""
        self.itens, self.novos = [], 0
        self._arquivo = Path(pasta) / ARQUIVO if pasta is not None and gravar else None
        caminho = Path(pasta) / ARQUIVO if pasta is not None else None
        if caminho is None or not caminho.exists():
            return
        for linha in caminho.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                self.itens.append(Aviso(**json.loads(linha)))
            except (ValueError, TypeError):
                continue                        # uma linha cortada por uma queda
        self.itens = self.itens[-LIMITE:]

    def registrar(self, tipo: str, titulo: str, texto: str) -> Aviso:
        aviso = Aviso(time.strftime("%Y-%m-%d %H:%M:%S"), tipo, titulo, texto)
        self.itens.append(aviso)
        self.novos += 1
        if self._arquivo is not None:
            try:
                self._gravar(aviso)
            except OSError as erro:             # o aviso fica na memória
                log.warning("Não gravou o aviso em %s: %s", self._arquivo, erro)
        return aviso

    def _gravar(self, aviso: Aviso) -> None:
        with open(self._arquivo, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(asdict(aviso), ensure_ascii=False) + "\n")
        if len(self.itens) > 2 * LIMITE:
            self.itens = self.itens[-LIMITE:]
            gv.gravar_texto(self._arquivo, "".join(json.dumps(asdict(a), ensure_ascii=False)
                                                  + "\n" for a in self.itens))

    def visto(self) -> None:
        self.novos = 0
