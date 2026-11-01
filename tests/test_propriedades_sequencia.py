"""Q-T6: a sequência do livro (§12.4): reordenar, apagar e restaurar preservam os pids.

Duas propriedades. A pura (`abbychess.sequencia`), com muitos exemplos: depois de qualquer
sequência de mover, apagar, restaurar e inserir,

- o conjunto dos pids (os do livro e os apagados) é o de antes mais os inseridos, sem
  repetição, e cada pid continua com a entrada dele (a mesma página da fonte, o mesmo quadro);
- mover leva as escolhidas, na ordem delas, para logo depois da página de referência, e as
  outras ficam na ordem delas;
- apagar tira as escolhidas e deixa as outras na ordem; restaurar logo depois, juntas ou uma
  de cada vez (em qualquer ordem), volta ao livro de antes;
- a sequência gravada (`para_json`) e relida é a mesma.

E a do projeto (`SequenciaDoLivro`, pelo `ControladorDaSequencia` e o Ctrl+Z), com poucos
exemplos e disco: cada pid continua apontando para a mesma página (o JSON dela), no livro e
nas apagadas, e o projeto reaberto tem a mesma ordem e as mesmas páginas.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import fitz
import pytest
from hypothesis import strategies as st

from abbychess import sequencia as sq
from abbychess.modelo import Box, gid_de
from abbychess.pagina_em_json import comparavel
from abbychess.projeto import ProjetoDeLivro

from tests.ajudantes import ExecutorManual, _controlador, _pagina
from tests.estrategias import propriedade

OPERACOES = ("mover", "apagar", "restaurar", "inserir")
PASSO = st.tuples(st.sampled_from(OPERACOES), st.integers(0, 2**12 - 1), st.integers(0, 10_000))


def _escolhidas(itens, mascara: int):
    """Os itens que a máscara de bits escolhe (na ordem deles)."""
    return [x for k, x in enumerate(itens) if mascara >> (k % 12) & 1]


def _entradas_iniciais(n: int):
    """`n` páginas da fonte, com pids fora de ordem e algumas com quadro e giro."""
    return [sq.Entrada(100 + (k + n // 2) % n, sq.FONTE_DO_LIVRO, k,
                       quadro=(0, 0, 50 + k, 80) if k % 3 == 1 else None, giro=(0, 90)[k % 2])
            for k in range(n)]


def _subsequencia(curta, longa) -> bool:
    it = iter(longa)
    return all(x in it for x in curta)


def _mover(s, mascara, j):
    pids = _escolhidas(s.pids, mascara)
    depois_da = j % (len(s) + 1) - 1
    if not pids or (depois_da >= 0 and s.pids[depois_da] in pids):
        with pytest.raises(ValueError):
            s.mover(pids, depois_da)
        return s
    nova = s.mover(pids, depois_da)
    ficam = [p for p in s.pids if p not in pids]
    assert [p for p in nova.pids if p not in pids] == ficam
    lugar = 0 if depois_da < 0 else ficam.index(s.pids[depois_da]) + 1
    assert nova.pids[lugar:lugar + len(pids)] == pids          # juntas, na ordem delas
    assert nova.apagadas == s.apagadas
    return nova


def _apagar(s, mascara, j):
    pids = _escolhidas(s.pids, mascara)
    if not pids or len(pids) >= len(s):
        with pytest.raises(ValueError):
            s.apagar(pids)
        return s
    nova = s.apagar(pids)
    assert nova.pids == [p for p in s.pids if p not in pids]
    assert [a.entrada.pid for a in nova.apagadas] == \
        [a.entrada.pid for a in s.apagadas] + [p for p in s.pids if p in pids]
    assert nova.restaurar(pids) == s                           # juntas
    uma_a_uma = nova
    ordem = sorted(pids, key=lambda p: (p * (j + 1)) % 9973)   # numa ordem qualquer
    for pid in ordem:
        uma_a_uma = uma_a_uma.restaurar([pid])
    assert uma_a_uma == s, f"restaurar uma de cada vez, na ordem {ordem}"
    return nova


def _restaurar(s, mascara, _j):
    pids = _escolhidas([a.entrada.pid for a in s.apagadas], mascara)
    if not pids:
        return s
    nova = s.restaurar(pids)
    assert _subsequencia(s.pids, nova.pids) and set(nova.pids) == set(s.pids) | set(pids)
    assert [a for a in nova.apagadas] == [a for a in s.apagadas if a.entrada.pid not in pids]
    return nova


def _inserir(s, mascara, j, proximo):
    novas = [sq.Entrada(proximo + k, f"{sq.PASTA_DAS_INSERIDAS}/x.pdf", k)
             for k in range(1 + mascara % 3)]
    na_posicao = j % (len(s) + 1)
    nova = s.inserir(novas, na_posicao)
    assert nova.pids == s.pids[:na_posicao] + [e.pid for e in novas] + s.pids[na_posicao:]
    return nova


def lei_da_sequencia(n, passos):
    """Mover, apagar, restaurar e inserir preservam os pids, e cada pid a página dele."""
    s = sq.Sequencia(tuple(_entradas_iniciais(n)))
    entrada_de = {e.pid: e for e in s.entradas}
    proximo = 1000
    for operacao, mascara, j in passos:
        if operacao == "inserir":
            s = _inserir(s, mascara, j, proximo)
            entrada_de.update({e.pid: e for e in s.entradas if e.pid >= proximo})
            proximo = max(entrada_de) + 1
        else:
            s = {"mover": _mover, "apagar": _apagar, "restaurar": _restaurar}[operacao](
                s, mascara, j)
        todos = s.todos_os_pids
        assert len(todos) == len(set(todos)) and set(todos) == set(entrada_de)
        assert all(e == entrada_de[e.pid] for e in s.entradas)
        assert all(a.entrada == entrada_de[a.entrada.pid] for a in s.apagadas)
        assert sq.Sequencia.de_json(s.para_json()) == s


test_a_sequencia_preserva_os_pids, test_a_sequencia_preserva_os_pids_noturna = propriedade(
    lei_da_sequencia, rapida=40, n=st.integers(1, 10), passos=st.lists(PASSO, max_size=10))


# ----------------------------------------------------------------------
# No projeto: o controlador da sequência, o Ctrl+Z, o disco
# ----------------------------------------------------------------------

PASSO_NO_PROJETO = st.one_of(
    st.tuples(st.sampled_from(("mover", "apagar", "restaurar")), st.integers(1, 2**6 - 1),
              st.integers(0, 100)),
    st.just(("desfazer", 0, 0)), st.just(("refazer", 0, 0)))


def _livro(pasta: Path, n: int) -> ProjetoDeLivro:
    """Um projeto de `n` páginas, cada uma com um texto só dela."""
    pdf = pasta / "livro.pdf"
    with fitz.open() as doc:
        for _ in range(n):
            doc.new_page(width=200, height=100)
        doc.save(str(pdf))
    projeto = ProjetoDeLivro.criar(pasta / "livros", "Sequencia", pdf)
    for i in range(n):
        pagina = projeto.pagina_para_editar(i)
        pagina.boxes = [Box(gid_de(pagina.pid, k), b.entry)
                        for k, b in enumerate(_pagina("abcdefgh"[:i + 1]).boxes)]
        pagina.proximo_n, pagina.estado = len(pagina.boxes), "reconhecida"
        projeto.salvar_modelo(pagina)
    return projeto


def _conferir_os_pids(projeto, conteudo) -> None:
    """Cada pid, no livro ou nas apagadas, com a página dele; nenhum pid a mais nem a menos."""
    s = projeto.sequencia
    assert sorted(s.todos_os_pids) == sorted(conteudo)
    for posicao, pid in enumerate(s.pids):
        pagina = projeto.carregar_modelo(posicao)
        assert pagina.pid == pid and comparavel(pagina) == conteudo[pid]
    for apagada in s.apagadas:
        assert comparavel(projeto.pagina_do_pid(apagada.entrada.pid)) == \
            conteudo[apagada.entrada.pid]


def _operar(ctl, operacao, mascara, j) -> None:
    s = ctl.projeto.sequencia
    if operacao == "mover":
        posicoes = _escolhidas(range(len(s)), mascara)
        ctl.operacoes.mover_paginas(posicoes, j % (len(s) + 1) - 1)
    elif operacao == "apagar":
        ctl.operacoes.apagar_paginas(_escolhidas(range(len(s)), mascara))
    elif operacao == "restaurar":
        pids = _escolhidas([a.entrada.pid for a in s.apagadas], mascara)
        if pids:
            ctl.operacoes.restaurar_paginas(pids)
    else:
        (ctl.desfazedor.refazer if operacao == "refazer" else ctl.desfazedor.desfazer)()


def lei_da_sequencia_no_projeto(tmp_path, n, passos):
    """Pelo controlador e pelo Ctrl+Z, cada pid continua com a página dele, na memória e no
    projeto reaberto, que tem a mesma ordem."""
    pasta = Path(tempfile.mkdtemp(dir=tmp_path))
    projeto = _livro(pasta, n)
    try:
        executor = ExecutorManual()
        ctl = _controlador(projeto, executor)
        conteudo = {projeto.ordem.pid_em(i): comparavel(projeto.carregar_modelo(i))
                    for i in range(n)}
        for passo in passos:
            _operar(ctl, *passo)
            executor.tudo()
            _conferir_os_pids(projeto, conteudo)
        sequencia = projeto.sequencia
        assert projeto.fechar(), "o gravador não gravou tudo"
        reaberto = ProjetoDeLivro.abrir(projeto.pasta)
        try:
            assert reaberto.sequencia == sequencia
            _conferir_os_pids(reaberto, conteudo)
        finally:
            reaberto.fechar()
    finally:
        projeto.fechar()


test_a_sequencia_no_projeto_preserva_os_pids, \
    test_a_sequencia_no_projeto_preserva_os_pids_noturna = propriedade(
        lei_da_sequencia_no_projeto, rapida=4, deadline=None,
        n=st.integers(2, 6), passos=st.lists(PASSO_NO_PROJETO, max_size=8))
