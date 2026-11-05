"""O log em arquivo e a falha nativa (C-2): sem ele, o programa aberto pelo atalho não deixa
rastro nenhum de uma queda, nem na interface nem no servidor de leitura.

Um arquivo por processo, em `%LOCALAPPDATA%\\AbbyChessCraft\\`: `app.log` e `leitura.log`. Não há
rotação entre processos: duas janelas no mesmo projeto escrevem no mesmo arquivo, e o Windows
não deixa renomear o que outro abriu. Só ao abrir, se ele passou do tamanho, vira `.1`. Vai para
lá o log do Python e, por `faulthandler`, a falha nativa. A primeira linha diz a versão do
programa, a do core e a do modelo, sem ler o modelo: a abertura não paga por isso.
"""

from __future__ import annotations

import faulthandler
import logging
import os
import sys
from importlib import metadata
from pathlib import Path
from typing import Optional

#: O teste e quem quiser os logs noutro lugar.
VARIAVEL = "ABBY_PASTA_DE_LOG"
TAMANHO_MAXIMO = 5 * 1024 * 1024
FORMATO = "%(asctime)s %(process)d %(name)s %(levelname)s %(message)s"

log = logging.getLogger(__name__)


def pasta_de_dados() -> Path:
    """Onde o programa guarda o que é da máquina (`%LOCALAPPDATA%\\AbbyChessCraft`)."""
    escolhida = os.environ.get(VARIAVEL)
    if escolhida:
        return Path(escolhida)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / "AbbyChessCraft"


def _rodar(arquivo: Path) -> None:
    """O arquivo grande vira `.1`; com outro processo nele, continua crescendo até a próxima."""
    try:
        if arquivo.stat().st_size > TAMANHO_MAXIMO:
            os.replace(arquivo, arquivo.with_name(arquivo.name + ".1"))
    except OSError:
        pass


def _versao_do_programa() -> str:
    try:
        return metadata.version("abbychesscraft")
    except metadata.PackageNotFoundError:
        return "sem instalar"


def _commit_do_core(raiz: Path) -> str:
    """O commit do checkout do core, lido do `.git`, sem abrir processo."""
    try:
        cabeca = (raiz / ".git" / "HEAD").read_text(encoding="ascii").strip()
        if cabeca.startswith("ref: "):
            cabeca = (raiz / ".git" / cabeca[5:]).read_text(encoding="ascii").strip()
    except OSError:
        return "sem git"
    return cabeca[:10]


def versoes() -> str:
    """A linha das versões: o programa, o core e o modelo (tamanho e data, sem ler o arquivo)."""
    try:
        import core

        raiz = Path(core.__file__).resolve().parent.parent
    except ImportError:
        return f"programa {_versao_do_programa()}, sem o core"
    try:
        dados = (raiz / "custom_model.pth").stat()
        modelo = f"{dados.st_size} bytes, {int(dados.st_mtime)}"
    except OSError:
        modelo = "ausente"
    return f"programa {_versao_do_programa()}, core {_commit_do_core(raiz)}, modelo {modelo}"


def ligar(nome: str, nivel: int = logging.INFO) -> Optional[Path]:
    """O `<nome>.log` deste processo e a falha nativa nele. Sem conseguir escrever, o programa
    segue sem log em arquivo: None, e o aviso vai ao stderr. Chamar uma vez por processo."""
    pasta = pasta_de_dados()
    arquivo = pasta / f"{nome}.log"
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        _rodar(arquivo)
        destino = logging.FileHandler(arquivo, encoding="utf-8")
    except OSError as erro:
        print(f"o log em arquivo não abriu: {erro}", file=sys.stderr)
        return None
    destino.setFormatter(logging.Formatter(FORMATO))
    destino.setLevel(nivel)
    raiz = logging.getLogger()
    raiz.addHandler(destino)
    raiz.setLevel(min(raiz.level, nivel) if raiz.level else nivel)
    faulthandler.enable(file=destino.stream, all_threads=True)
    log.info("%s", versoes())
    return arquivo
