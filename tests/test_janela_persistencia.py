"""Passo 1a na janela: projeto só para leitura e fonte que sumiu.

A abertura passa por `JanelaPrincipal.abrir_caminho`, como pela linha de comando. O
leitor com os modelos globais é trocado por um só com os padrões do livro, para o teste
não carregar a rede.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox

from abbychess import gravacao as gv
from abbychess.app.janela import JanelaPrincipal
from abbychess.leitor import LeitorDoLivro
from abbychess.projeto import ProjetoDeLivro

from tests.test_janela import _esperar, app  # noqa: F401 (fixture)
from tests.test_treino_por_livro import _pagina_sintetica
from tests.janela_util import atual, boxes, fila, mostrar, pulados, selecao  # noqa: E402,F401


@pytest.fixture
def sem_dialogos(monkeypatch):
    """Registra os avisos em vez de abrir caixas de diálogo."""
    avisos = []
    for nome in ("information", "warning"):
        monkeypatch.setattr(QMessageBox, nome,
                            lambda _pai, titulo, texto, *a, **k: avisos.append(texto))
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(LeitorDoLivro, "com_modelos_globais",
                        classmethod(lambda cls, pasta, limiares=None: cls(pasta, limiares=limiares)))
    return avisos


@pytest.fixture
def projeto_lido(tmp_path, app):  # noqa: F811
    from abbychess import livro, pagina as pg

    fonte = _pagina_sintetica(tmp_path / "pagina.png")
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Janela", fonte)
    leitor = LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)
    livro.reconhecer_paginas(projeto, pg.fonte_do_projeto(projeto), leitor, [0])
    return projeto


def _instantaneo(pasta: Path) -> dict:
    return {str(p.relative_to(pasta)): (p.stat().st_mtime_ns,
                                        hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(pasta.rglob("*")) if p.is_file()}


def _abrir(app, pasta):  # noqa: F811
    janela = JanelaPrincipal()
    janela.abrir_caminho(str(pasta))
    _esperar(app, janela)
    return janela


def test_versao_mais_nova_abre_so_para_leitura_e_nada_e_gravado(app, projeto_lido,  # noqa: F811
                                                               sem_dialogos):
    arquivo = projeto_lido.pasta / "projeto.json"
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    dados["versao"] = 99
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    antes = _instantaneo(projeto_lido.pasta)

    janela = _abrir(app, projeto_lido.pasta)
    try:
        assert janela.projeto.somente_leitura and "só leitura" in janela.windowTitle()
        assert any("só para leitura" in a for a in sem_dialogos)
        assert boxes(janela)                              # a página aparece
        mostrar(janela, 0)
        janela.treino.campo.setText("z")
        janela.treino._so_corrigir()                     # muda na tela, não no disco
        janela.areas.desenhar(1, 1, 60, 60)              # nem a área nova
        from abbychess.projeto import Limiares

        janela.pagina.aplicar_limiares(Limiares(revisao=0.5))   # vale na sessão, não no disco
        assert "nesta sessão" in janela.statusBar().currentMessage()
        janela.ir_para_pagina(0)                         # a troca de página grava, se puder
        assert _instantaneo(projeto_lido.pasta) == antes
    finally:
        janela.close()
    assert _instantaneo(projeto_lido.pasta) == antes     # fechar também não grava
    assert not gv.protegida(projeto_lido.pasta)          # e solta a trava


def test_fonte_sumida_e_pedida_e_conferida(app, projeto_lido, sem_dialogos, tmp_path,  # noqa: F811
                                         monkeypatch):
    guardada = tmp_path / "longe" / "a-fonte.png"
    guardada.parent.mkdir()
    projeto_lido.fonte.rename(guardada)
    errada = _pagina_sintetica(tmp_path / "longe" / "outra.png", ("xyz",))
    respostas = iter([str(errada), str(guardada)])
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        lambda *a, **k: (next(respostas), ""))

    janela = _abrir(app, projeto_lido.pasta)
    try:
        assert janela.projeto is not None and janela.projeto.fonte == guardada.resolve()
        assert any("não é a fonte" in a for a in sem_dialogos)    # a primeira foi recusada
        assert boxes(janela)
    finally:
        janela.close()


def test_fonte_sumida_e_cancelada_nao_abre(app, projeto_lido, sem_dialogos, tmp_path,  # noqa: F811
                                          monkeypatch):
    # Fora das pastas onde a abertura procura pelo SHA-256: renomeada ao lado, seria achada.
    (tmp_path / "longe").mkdir()
    projeto_lido.fonte.rename(tmp_path / "longe" / "sumiu.png")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    janela = _abrir(app, projeto_lido.pasta)
    try:
        assert janela.projeto is None
    finally:
        janela.close()


def test_cancelar_a_fonte_de_outro_projeto_mantem_o_aberto(app, projeto_lido, sem_dialogos,  # noqa: F811
                                                         tmp_path, monkeypatch):
    janela = _abrir(app, projeto_lido.pasta)
    try:
        aberto = janela.projeto
        segundo = ProjetoDeLivro.criar(tmp_path / "outros", "Segundo",
                                       _pagina_sintetica(tmp_path / "segunda.png", ("xyz",)))
        (tmp_path / "longe").mkdir()
        segundo.fonte.rename(tmp_path / "longe" / "sumiu.png")
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
        janela.abrir_caminho(str(segundo.pasta))
        _esperar(app, janela)
        assert janela.projeto is aberto and boxes(janela)
        janela.ir_para_pagina(0)                        # e ainda grava normalmente
    finally:
        janela.close()


def test_fonte_achada_sozinha_e_avisada(app, projeto_lido, sem_dialogos):  # noqa: F811
    projeto_lido.fonte.rename(projeto_lido.fonte.with_name("renomeada.png"))
    janela = _abrir(app, projeto_lido.pasta)
    try:
        assert janela.projeto.fonte.name == "renomeada.png"
        assert any("foi achada" in a for a in sem_dialogos)
    finally:
        janela.close()


def test_so_leitura_com_fonte_sumida_acha_pela_memoria_e_nao_grava(app, projeto_lido,  # noqa: F811
                                                                  sem_dialogos):
    arquivo = projeto_lido.pasta / "projeto.json"
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    dados["versao"] = 99
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    projeto_lido.fonte.rename(projeto_lido.fonte.with_name("renomeada.png"))
    antes = _instantaneo(projeto_lido.pasta)
    janela = _abrir(app, projeto_lido.pasta)
    try:
        assert janela.projeto.somente_leitura and boxes(janela)
        assert janela.projeto.fonte.name == "renomeada.png"
    finally:
        janela.close()
    assert _instantaneo(projeto_lido.pasta) == antes


def test_falha_ao_abrir_nao_deixa_a_pasta_travada(app, projeto_lido, sem_dialogos,  # noqa: F811
                                                monkeypatch):
    arquivo = projeto_lido.pasta / "projeto.json"
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    dados["versao"] = 99
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    janela = JanelaPrincipal()

    def quebrar(*_a):
        raise RuntimeError("falha no meio da abertura")

    monkeypatch.setattr(janela, "trocar_projeto", quebrar)
    try:
        with pytest.raises(RuntimeError):
            janela.abrir(ProjetoDeLivro.abrir(projeto_lido.pasta))
        assert not gv.protegida(projeto_lido.pasta)
    finally:
        janela.close()


def test_limiares_que_nao_gravam_avisam_e_nao_dizem_gravados(app, projeto_lido,  # noqa: F811
                                                            sem_dialogos, monkeypatch):
    from abbychess.projeto import Limiares

    janela = _abrir(app, projeto_lido.pasta)
    try:
        def falhar(*_args):
            raise PermissionError("disco")

        monkeypatch.setattr(gv, "gravar_bytes", falhar)
        janela.pagina.aplicar_limiares(Limiares(revisao=0.5))
        assert any("não foram gravados" in a for a in sem_dialogos)
        assert janela.statusBar().currentMessage() == ("Limiares aplicados nesta sessão "
                                                       "(não foram gravados).")
    finally:
        monkeypatch.undo()
        janela.close()
