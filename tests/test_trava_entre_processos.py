"""Dois processos no mesmo projeto (SPEC-qualidade Q-P5, decisão §13.3): o segundo abre só
para leitura, com o motivo, e não toca em nada da pasta (nem nos temporários do primeiro)."""
from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager

import pytest

from abbychess import gravacao as gv
from abbychess.projeto import ProjetoDeLivro

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


@contextmanager
def _outro_dono(pasta):
    """A trava do sistema na `projeto.lock`, por um descritor que não é o do projeto: o que
    outro processo do programa seguraria (o mesmo byte, sem esperar)."""
    fd = os.open(pasta / "projeto.lock", os.O_RDWR | os.O_CREAT, 0o644)
    try:
        if sys.platform == "win32":
            os.lseek(fd, gv.BYTE_DA_TRAVA, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
        if sys.platform == "win32":
            os.lseek(fd, gv.BYTE_DA_TRAVA, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    finally:
        os.close(fd)


def _fotografia(pasta):
    """Os arquivos e as pastas, com os bytes (a `projeto.lock` travada inclusive: um backup a
    copia)."""
    return {p.relative_to(pasta).as_posix(): (p.read_bytes() if p.is_file() else None)
            for p in sorted(pasta.rglob("*"))}


@pytest.fixture
def pasta_livre(projeto):
    """A pasta de um projeto criado e fechado: ninguém a segura."""
    pasta = projeto.pasta
    projeto.fechar()
    return pasta


def test_com_outro_dono_abre_so_para_leitura_e_nada_muda(pasta_livre):
    temporario = pasta_livre / "paginas" / "p0.json.tmp"      # a gravação em curso do outro
    temporario.write_text("{", encoding="utf-8")
    with _outro_dono(pasta_livre):
        antes = _fotografia(pasta_livre)
        aberto = ProjetoDeLivro.abrir(pasta_livre)
        try:
            assert aberto.somente_leitura
            assert "outra janela" in aberto.motivo_so_leitura
            with pytest.raises(gv.SomenteLeitura):
                aberto.salvar()
            assert _fotografia(pasta_livre) == antes
        finally:
            aberto.fechar()
    assert temporario.exists()


def test_sem_outro_dono_abre_para_gravar_e_solta_ao_fechar(pasta_livre):
    aberto = ProjetoDeLivro.abrir(pasta_livre)
    assert not aberto.somente_leitura
    aberto.fechar()
    with _outro_dono(pasta_livre):                # fechado, a trava é de quem quiser
        pass


def test_o_mesmo_processo_abre_duas_vezes_para_gravar(pasta_livre):
    um = ProjetoDeLivro.abrir(pasta_livre)
    dois = ProjetoDeLivro.abrir(pasta_livre)
    try:
        assert not um.somente_leitura and not dois.somente_leitura
    finally:
        dois.fechar()
        um.fechar()


_SEGURAR = """
import sys
from abbychess.projeto import ProjetoDeLivro
p = ProjetoDeLivro.abrir(sys.argv[1])
print("so_leitura" if p.somente_leitura else "dono", flush=True)
sys.stdin.readline()
p.fechar()
"""


@pytest.mark.processo
def test_o_segundo_processo_abre_so_para_leitura(pasta_livre):
    ambiente = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    primeiro = subprocess.Popen([sys.executable, "-c", _SEGURAR, str(pasta_livre)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                env=ambiente)
    try:
        assert primeiro.stdout.readline().strip() == "dono"
        aberto = ProjetoDeLivro.abrir(pasta_livre)
        try:
            assert aberto.somente_leitura and "outra janela" in aberto.motivo_so_leitura
        finally:
            aberto.fechar()
    finally:
        primeiro.communicate("\n", timeout=60)
    assert primeiro.returncode == 0
    depois = ProjetoDeLivro.abrir(pasta_livre)
    try:
        assert not depois.somente_leitura
    finally:
        depois.fechar()
