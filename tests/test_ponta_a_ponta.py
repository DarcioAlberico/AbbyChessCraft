"""CA-C7 (SPEC-pagina-perfeita, C-7; T2): de ponta a ponta, com o filho de verdade.

PDF, lote, matar, reabrir, retomar, exportar, conferir. O caminho que um livro inteiro faz, e
que nenhum teste fazia junto: o lote lendo pelo servidor de leitura (o filho, com o leitor
falso), o filho morto no meio até o servidor desistir, o projeto fechado e aberto de novo numa
janela nova, o lote retomado de onde parou, e o livro exportado. O texto exportado tem cada
glifo lido uma vez só: nenhuma página perdida nem lida duas vezes.

Camada `processo` (abre o filho).
"""

from __future__ import annotations

import time

import pytest

from abbychess.app.janela import JanelaPrincipal
from abbychess.exportar import exportar
from abbychess.projeto import ProjetoDeLivro

from tests import leitor_falso
from tests.ajudantes import PAGINAS, _esperar, pdf_sintetico

pytestmark = pytest.mark.processo

#: Nove páginas sintéticas: o lote leva alguns segundos com o leitor falso.
LIVRO = PAGINAS * 3


def _ate(app, condicao, limite=60.0):
    fim = time.monotonic() + limite
    while not condicao() and time.monotonic() < fim:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    assert condicao(), "a condição não chegou no prazo"


def _abrir(app, pasta):
    janela = JanelaPrincipal()
    janela.fins = []
    janela.eventos.ligar("lote_terminou",
                         lambda _mensagem, resultado: janela.fins.append(resultado))
    janela.abrir_caminho(str(pasta))
    _esperar(app, janela)
    _ate(app, janela.pagina.servidor.pronto.is_set)
    return janela


def test_ca_c7_pdf_lote_matar_reabrir_retomar_exportar_conferir(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setenv("ABBY_SERVIDOR", "1")
    monkeypatch.setenv("ABBY_FABRICA_DE_LEITOR", "tests.leitor_falso:criar")
    monkeypatch.setenv("ABBY_FALSO_MS_POR_GLIFO", "40")        # ~0,6 s por página
    # "Reabrir o projeto?" depois de o servidor desistir: não; o teste reabre numa janela nova.
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    for nome in ("information", "warning"):
        monkeypatch.setattr(QMessageBox, nome, lambda *a, **k: None)

    # PDF
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Ponta", pdf_sintetico(tmp_path, LIVRO))
    pasta, total = projeto.pasta, len(LIVRO)
    projeto.fechar()

    # Lote
    j = _abrir(app, pasta)
    p = j.pagina
    j.livro.reconhecer(list(range(total)), refazer=False)
    _ate(app, lambda: len(p.projeto.resumo.paginas_lidas()) >= 2)

    # Matar: duas quedas seguidas, sem página concluída entre elas, e o servidor desiste.
    servidor = p.servidor
    monkeypatch.setenv("ABBY_FALSO_ATRASO_AO_ABRIR", "30")    # o reaberto ainda carregando
    servidor.processo.kill()
    _ate(app, lambda: servidor.reinicios == 1 and servidor.processo.is_alive()
         and not servidor.pronto.is_set())
    servidor.processo.kill()
    _ate(app, lambda: not j.livro.lote_rodando, 60)
    assert servidor.desistiu and j.fins[-1].servidor_parou
    lidas_antes = set(p.projeto.resumo.paginas_lidas())
    assert 2 <= len(lidas_antes) < total, "o lote parou no meio"
    monkeypatch.delenv("ABBY_FALSO_ATRASO_AO_ABRIR")
    j.close()

    # Reabrir: outra janela, outro filho; o que faltou do lote está no projeto (`lote.json`).
    j = _abrir(app, pasta)
    p = j.pagina
    assert set(p.projeto.resumo.paginas_lidas()) == lidas_antes
    assert j.livro.pode_retomar

    # Retomar: só o que faltou, sem ler de novo as lidas (CA-11.5).
    j.livro.retomar()
    _ate(app, lambda: not j.livro.lote_rodando, 120)
    resultado = j.fins[-1]
    assert not resultado.falhas and not resultado.servidor_parou
    assert set(resultado.lidas) == set(range(total)) - lidas_antes
    assert set(p.projeto.resumo.paginas_lidas()) == set(range(total))
    assert p.projeto.paginas_em_memoria.descarregar(10)

    # Exportar e conferir: cada glifo lido, uma vez, no texto exportado.
    glifos = 0
    for indice in range(total):
        modelo = p.projeto.carregar_modelo(indice)
        assert modelo is not None and modelo.boxes, f"a página {indice + 1} não foi lida"
        assert {b.entry.char for b in modelo.boxes} == {leitor_falso.LETRA}
        glifos += len(modelo.boxes)
    destino = tmp_path / "livro.txt"
    exportar(p.projeto, destino)
    texto = destino.read_text(encoding="utf-8")
    assert texto.count(leitor_falso.LETRA) == glifos
    j.close()
