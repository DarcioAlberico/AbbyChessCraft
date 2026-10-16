"""Gravação atômica dos arquivos do projeto (SPEC §4.3).

Todo arquivo do projeto é gravado do mesmo jeito: o conteúdo vai para
`<nome>.tmp` ao lado, passa por `fsync` e troca de lugar com o antigo por
`os.replace`. Quem lê depois acha o antigo inteiro ou o novo inteiro, nunca um
JSON pela metade.

No Windows, um antivírus ou o indexador que abriu o arquivo um instante faz o
`os.replace` falhar com `PermissionError`. A gravação tenta de novo
`TENTATIVAS` vezes, com `ESPERA` segundos entre elas; se não der, apaga o
temporário e deixa o erro subir, com o arquivo antigo intacto. Os `*.tmp` que
sobrarem de uma queda são apagados ao abrir o projeto (`limpar_temporarios`).

Um projeto de versão mais nova que a do programa abre só para leitura: a pasta
dele fica `protegida`, e qualquer gravação ou remoção dentro dela recusa com
`SomenteLeitura`. A trava fica aqui, e não em cada chamador, para que nenhum
caminho de gravação escape dela.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Iterable, List, Union

TENTATIVAS = 5
ESPERA = 0.05
SUFIXO_TEMPORARIO = ".tmp"

Caminho = Union[str, Path]

_protegidas: set = set()
_trava = threading.Lock()


class SomenteLeitura(PermissionError):
    """Gravar num projeto aberto só para leitura."""


def protegida(caminho: Caminho) -> bool:
    """Se o caminho está dentro de uma pasta aberta só para leitura."""
    alvo = Path(caminho).resolve()
    with _trava:
        return any(alvo == p or p in alvo.parents for p in _protegidas)


def proteger(pasta: Caminho) -> None:
    with _trava:
        _protegidas.add(Path(pasta).resolve())


def liberar(pasta: Caminho) -> None:
    with _trava:
        _protegidas.discard(Path(pasta).resolve())


def _recusar_se_protegida(caminho: Path) -> None:
    if protegida(caminho):
        raise SomenteLeitura(
            f"O projeto está aberto só para leitura; {caminho.name} não foi gravado.")


def temporario_de(caminho: Caminho) -> Path:
    caminho = Path(caminho)
    return caminho.with_name(caminho.name + SUFIXO_TEMPORARIO)


# As três etapas ficam em funções próprias para os testes injetarem falha em cada uma.
def _escrever(temporario: Path, dados: bytes) -> int:
    fd = os.open(temporario, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0))
    try:
        vista = memoryview(dados)
        while vista:
            vista = vista[os.write(fd, vista):]
    except BaseException:
        os.close(fd)
        raise
    return fd


def _sincronizar(fd: int) -> None:
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _trocar(temporario: Path, caminho: Path) -> None:
    os.replace(temporario, caminho)


def gravar_bytes(caminho: Caminho, dados: bytes) -> None:
    """Grava `dados` em `caminho` de forma atômica, com novas tentativas."""
    caminho = Path(caminho)
    _recusar_se_protegida(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = temporario_de(caminho)
    for tentativa in range(TENTATIVAS):
        try:
            _sincronizar(_escrever(temporario, dados))
            _trocar(temporario, caminho)
            return
        except PermissionError:
            if tentativa == TENTATIVAS - 1:
                temporario.unlink(missing_ok=True)
                raise
            time.sleep(ESPERA)
        except BaseException:
            temporario.unlink(missing_ok=True)
            raise


def gravar_texto(caminho: Caminho, texto: str) -> None:
    """Texto em UTF-8 sem BOM e com LF."""
    gravar_bytes(caminho, texto.encode("utf-8"))


def gravar_json(caminho: Caminho, dados) -> None:
    gravar_texto(caminho, json.dumps(dados, ensure_ascii=False, indent=1))


def apagar(caminho: Caminho) -> None:
    """Remove um arquivo do projeto, se existir; recusa em projeto só para leitura."""
    caminho = Path(caminho)
    _recusar_se_protegida(caminho)
    caminho.unlink(missing_ok=True)


def limpar_temporarios(pasta: Caminho) -> List[Path]:
    """Apaga os `*.tmp` que uma gravação interrompida deixou na pasta. Devolve quais."""
    pasta = Path(pasta)
    if protegida(pasta):
        return []
    apagados = []
    for sobra in _temporarios(pasta):
        try:
            sobra.unlink()
            apagados.append(sobra)
        except OSError:
            pass                    # outro processo ainda está com ele; fica para a próxima
    return apagados


def _temporarios(pasta: Path) -> Iterable[Path]:
    return [p for p in pasta.rglob("*" + SUFIXO_TEMPORARIO) if p.is_file()]
