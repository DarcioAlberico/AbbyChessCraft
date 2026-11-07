"""CA-C2: erro solto e falha nativa deixam rastro em `app.log` e `leitura.log`, um por processo,
com a versão do programa, do core e do modelo."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

from abbychess import log_em_arquivo as la

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    monkeypatch.setenv(la.VARIAVEL, str(tmp_path))
    return tmp_path


def _rodar(pasta: Path, codigo: str) -> subprocess.CompletedProcess:
    ambiente = dict(os.environ, **{la.VARIAVEL: str(pasta)}, PYTHONPATH=str(RAIZ),
                    PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-c", codigo], env=ambiente, capture_output=True,
                          timeout=60)


def test_a_pasta_vem_da_variavel_e_senao_do_localappdata(monkeypatch, tmp_path):
    monkeypatch.setenv(la.VARIAVEL, str(tmp_path))
    assert la.pasta_de_dados() == tmp_path
    monkeypatch.delenv(la.VARIAVEL)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert la.pasta_de_dados() == tmp_path / "AbbyChessCraft"


def test_o_arquivo_grande_vira_ponto_um(tmp_path, monkeypatch):
    monkeypatch.setattr(la, "TAMANHO_MAXIMO", 10)
    arquivo = tmp_path / "app.log"
    arquivo.write_text("x" * 20, encoding="utf-8")
    la._rodar(arquivo)
    assert not arquivo.exists() and (tmp_path / "app.log.1").stat().st_size == 20


def test_sem_conseguir_escrever_o_programa_segue(tmp_path, monkeypatch, capsys):
    ocupado = tmp_path / "um-arquivo"
    ocupado.write_text("", encoding="utf-8")
    monkeypatch.setenv(la.VARIAVEL, str(ocupado))
    assert la.ligar("app") is None
    assert "não abriu" in capsys.readouterr().err


def test_as_versoes_dizem_o_programa_o_core_e_o_modelo():
    linha = la.versoes()
    assert "programa " in linha and "core " in linha and "modelo " in linha


@pytest.mark.processo
def test_o_erro_solto_vai_ao_app_log_com_as_versoes(tmp_path):
    saida = _rodar(tmp_path, "from abbychess.app import principal\n"
                             "from abbychess import log_em_arquivo\n"
                             "log_em_arquivo.ligar('app')\n"
                             "principal.registrar_os_erros_soltos()\n"
                             "raise RuntimeError('quebrou de propósito')\n")
    assert saida.returncode != 0
    texto = (tmp_path / "app.log").read_text(encoding="utf-8")
    assert "programa " in texto and "modelo " in texto
    assert "CRITICAL" in texto and "quebrou de propósito" in texto and "Traceback" in texto


@pytest.mark.processo
def test_a_falha_nativa_deixa_rastro_no_leitura_log(tmp_path):
    saida = _rodar(tmp_path, "import logging, faulthandler\n"
                             "from abbychess import log_em_arquivo\n"
                             "log_em_arquivo.ligar('leitura', logging.WARNING)\n"
                             "faulthandler._sigsegv()\n")
    assert saida.returncode != 0
    assert "Fatal Python error" in (tmp_path / "leitura.log").read_text(encoding="utf-8")


def test_um_erro_logado_vai_ao_arquivo(pasta):
    raiz = logging.getLogger()
    antes = list(raiz.handlers), raiz.level
    try:
        arquivo = la.ligar("app")
        logging.getLogger("abbychess.teste").warning("um aviso qualquer")
        for destino in raiz.handlers:
            destino.flush()
        assert "um aviso qualquer" in arquivo.read_text(encoding="utf-8")
    finally:
        import faulthandler

        faulthandler.disable()
        for destino in list(raiz.handlers):
            if destino not in antes[0]:
                raiz.removeHandler(destino)
                destino.close()
        raiz.setLevel(antes[1])
