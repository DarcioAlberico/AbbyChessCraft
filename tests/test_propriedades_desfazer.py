"""Q-T6: o desfazer entre páginas, com o gravador: gravar, reabrir e comparar.

Um livro de três páginas em disco (`ProjetoDeLivro`), cada uma com glifos escritos à mão, e o
`ControladorDePagina` de verdade (sem Qt): edições em qualquer página (corrigir, descartar,
juntar, verificar), misturadas com Ctrl+Z e Ctrl+Y. O oráculo é a pilha do desfazer como o
usuário a vê: cada edição que entra no histórico empilha (a página, como estava, como ficou);
desfazer volta a página da última à de antes, e refazer, à de depois. As leis:

- depois de cada passo, cada página do projeto é a do oráculo (o JSON dela, sem a data);
- desfazer e refazer nunca recusam (nada mudou por fora) e abrem a página da transação;
- fechar o projeto grava tudo (o gravador descarrega), e o projeto reaberto do disco tem as
  mesmas páginas.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import fitz
from hypothesis import strategies as st

from abbychess.modelo import Box, gid_de
from abbychess.pagina_em_json import comparavel
from abbychess.projeto import ProjetoDeLivro

from tests.ajudantes import ExecutorManual, _controlador, _pagina
from tests.estrategias import propriedade

TEXTOS = ("abc de", "fgh", "ij kl")
EDICOES = ("corrigir", "descartar", "juntar", "verificar")

PASSO = st.one_of(
    st.tuples(st.just("editar"), st.integers(0, len(TEXTOS) - 1), st.sampled_from(EDICOES),
              st.integers(0, 1000), st.sampled_from("xyz")),
    st.just(("desfazer",)), st.just(("refazer",)))


def _livro(pasta: Path) -> ProjetoDeLivro:
    """O projeto de três páginas, cada uma com os glifos de `TEXTOS` (sem reconhecer)."""
    pdf = pasta / "livro.pdf"
    with fitz.open() as doc:
        for _ in TEXTOS:
            doc.new_page(width=200, height=100)
        doc.save(str(pdf))
    projeto = ProjetoDeLivro.criar(pasta / "livros", "Propriedade", pdf)
    for i, texto in enumerate(TEXTOS):
        pagina = projeto.pagina_para_editar(i)
        pagina.boxes = [Box(gid_de(pagina.pid, n), b.entry)
                        for n, b in enumerate(_pagina(texto).boxes)]
        pagina.proximo_n = len(pagina.boxes)
        pagina.estado = "reconhecida"
        projeto.salvar_modelo(pagina)
    return projeto


def _paginas(projeto) -> dict:
    """pid -> a página como o JSON dela, sem a data, a posição e o contador."""
    return {projeto.ordem.pid_em(i): comparavel(projeto.carregar_modelo(i))
            for i in range(len(TEXTOS))}


def _editar(ctl, executor, indice, edicao, i, c) -> None:
    ctl.ir_para(indice)
    if not ctl.gids:
        return
    ctl.mostrar(ctl.gids[i % len(ctl.gids)])
    {"corrigir": lambda: ctl.corrigir(c), "descartar": ctl.descartar,
     "juntar": lambda: ctl.juntar(+1 if i % 2 else -1), "verificar": ctl.verificar}[edicao]()
    executor.tudo()


def _voltar(ctl, executor, refazer: bool) -> None:
    """Ctrl+Z (ou Ctrl+Y): a transação sai da pilha dela, sem recusa."""
    historico = ctl.historico
    transacao = historico.proxima_a_refazer() if refazer else historico.proxima_a_desfazer()
    (ctl.desfazedor.refazer if refazer else ctl.desfazedor.desfazer)()
    executor.tudo()
    agora = historico.proxima_a_refazer() if refazer else historico.proxima_a_desfazer()
    assert agora is not transacao, "desfazer recusado sem mudança por fora"
    [pid] = transacao.paginas
    assert ctl.indice == ctl.projeto.ordem.posicao_de(pid)      # a página dela, aberta


def lei_do_desfazer_entre_paginas(tmp_path, passos):
    """Desfazer e refazer entre as páginas seguem a pilha do usuário, na memória e no disco
    (gravar, reabrir e comparar)."""
    pasta = Path(tempfile.mkdtemp(dir=tmp_path))
    projeto = _livro(pasta)
    try:
        executor = ExecutorManual()
        ctl = _controlador(projeto, executor)
        oraculo = _paginas(projeto)
        pilha, feitas = [], 0                  # (pid, antes, depois); quantas valem
        for passo in passos:
            if passo[0] == "editar":
                ultima = ctl.historico.proxima_a_desfazer()
                _editar(ctl, executor, *passo[1:])
                if ctl.historico.proxima_a_desfazer() is not ultima:   # entrou no histórico
                    pid = ctl.projeto.ordem.pid_em(passo[1])
                    agora = _paginas(projeto)[pid]
                    pilha[feitas:] = [(pid, oraculo[pid], agora)]
                    feitas += 1
                    oraculo[pid] = agora
            elif passo[0] == "desfazer" and feitas:
                _voltar(ctl, executor, refazer=False)
                feitas -= 1
                pid, antes, _depois = pilha[feitas]
                oraculo[pid] = antes
            elif passo[0] == "refazer" and feitas < len(pilha):
                _voltar(ctl, executor, refazer=True)
                pid, _antes, depois = pilha[feitas]
                feitas += 1
                oraculo[pid] = depois
            assert _paginas(projeto) == oraculo
        assert projeto.fechar(), "o gravador não gravou tudo"
        reaberto = ProjetoDeLivro.abrir(projeto.pasta)
        try:
            assert _paginas(reaberto) == oraculo
        finally:
            reaberto.fechar()
    finally:
        projeto.fechar()


test_o_desfazer_entre_paginas_grava_e_reabre_igual, \
    test_o_desfazer_entre_paginas_grava_e_reabre_igual_noturna = propriedade(
        lei_do_desfazer_entre_paginas, rapida=4, deadline=None,
        passos=st.lists(PASSO, max_size=10))
