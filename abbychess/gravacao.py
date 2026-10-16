"""Gravação atômica dos arquivos do projeto (SPEC §4.3).

Todo arquivo do projeto é gravado do mesmo jeito: o conteúdo vai para
`<nome>.tmp` ao lado, passa por `fsync` e troca de lugar com o antigo por
`os.replace`. Quem lê depois acha o antigo inteiro ou o novo inteiro, nunca um
JSON pela metade.

No Windows, um antivírus ou o indexador que abriu o arquivo um instante faz o
`os.replace` falhar com `PermissionError`. A gravação tenta de novo
`TENTATIVAS` vezes, com `ESPERA` segundos entre elas; se não der, apaga o
temporário e deixa o erro subir, com o arquivo antigo intacto. Qualquer outra
falha (disco cheio, interrupção) também apaga o temporário e sobe na hora. Os
temporários que sobrarem de uma queda do processo são apagados ao abrir o
projeto (`limpar_temporarios`).

Um projeto de versão mais nova que a do programa abre só para leitura: a pasta
dele fica `protegida`, e qualquer gravação ou remoção dentro dela recusa com
`SomenteLeitura`. A trava fica aqui, e não em cada chamador, para que nenhum
caminho de gravação escape dela. Ela conta referências: duas aberturas da mesma
pasta só para leitura precisam de dois `liberar` para soltá-la.

As chamadas ao sistema (`_abrir_fd`, `_write`, `_fsync`, `_replace`) são nomes
deste módulo para os testes injetarem falha nelas sem trocar as etapas.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import Counter
from pathlib import Path
from typing import List, Union

TENTATIVAS = 5
ESPERA = 0.05
SUFIXO_TEMPORARIO = ".tmp"
#: Os temporários que `limpar_temporarios` apaga: só os que esta gravação cria.
EXTENSOES_GRAVADAS = (".json", ".txt", ".png")

Caminho = Union[str, Path]

_abrir_fd = os.open
_write = os.write
_fsync = os.fsync
_replace = os.replace

_protegidas: Counter = Counter()
_trava = threading.Lock()


class SomenteLeitura(PermissionError):
    """Gravar num projeto aberto só para leitura."""


def protegida(caminho: Caminho) -> bool:
    """Se o caminho está dentro de uma pasta aberta só para leitura."""
    alvo = Path(caminho).resolve()
    with _trava:
        return any(alvo == p or p in alvo.parents for p, n in _protegidas.items() if n > 0)


def proteger(pasta: Caminho) -> None:
    with _trava:
        _protegidas[Path(pasta).resolve()] += 1


def liberar(pasta: Caminho) -> None:
    chave = Path(pasta).resolve()
    with _trava:
        if _protegidas[chave] > 1:
            _protegidas[chave] -= 1
        else:
            _protegidas.pop(chave, None)


def _recusar_se_protegida(caminho: Path) -> None:
    if protegida(caminho):
        raise SomenteLeitura(
            f"O projeto está aberto só para leitura; {caminho.name} não foi gravado.")


def temporario_de(caminho: Caminho) -> Path:
    caminho = Path(caminho)
    return caminho.with_name(caminho.name + SUFIXO_TEMPORARIO)


def _escrever(temporario: Path, dados: bytes) -> int:
    fd = _abrir_fd(temporario, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0))
    try:
        vista = memoryview(dados)
        while vista:
            vista = vista[_write(fd, vista):]
    except BaseException:
        os.close(fd)
        raise
    return fd


def _sincronizar(fd: int) -> None:
    try:
        _fsync(fd)
    finally:
        os.close(fd)


def _trocar(temporario: Path, caminho: Path) -> None:
    _replace(temporario, caminho)


def gravar_bytes(caminho: Caminho, dados: bytes) -> None:
    """Grava `dados` em `caminho` de forma atômica, com novas tentativas."""
    caminho = Path(caminho)
    _recusar_se_protegida(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = temporario_de(caminho)
    gravado = False
    try:
        for tentativa in range(TENTATIVAS):
            try:
                _sincronizar(_escrever(temporario, dados))
                _trocar(temporario, caminho)
                gravado = True
                return
            except PermissionError:
                if tentativa == TENTATIVAS - 1:
                    raise
                time.sleep(ESPERA)
    finally:
        if not gravado:
            temporario.unlink(missing_ok=True)


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
    """Apaga os temporários (`*.json.tmp`, `*.txt.tmp`, `*.png.tmp`) que uma gravação
    interrompida deixou na pasta. Devolve quais.

    Um segundo processo com o mesmo projeto aberto perderia um temporário em andamento:
    o programa não foi feito para isso (§4.3, escritor único).
    """
    pasta = Path(pasta)
    if protegida(pasta):
        return []
    apagados = []
    for extensao in EXTENSOES_GRAVADAS:
        for sobra in pasta.rglob(f"*{extensao}{SUFIXO_TEMPORARIO}"):
            if not sobra.is_file():
                continue
            try:
                sobra.unlink()
                apagados.append(sobra)
            except OSError:
                pass                # outro processo ainda está com ele; fica para a próxima
    return apagados
