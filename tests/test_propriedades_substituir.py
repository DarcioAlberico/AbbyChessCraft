"""Q-T6: substituir, e depois desfazer (§7.2, passo D2).

Duas propriedades, sobre texto de palavras de poucas letras (para os casamentos serem muitos)
e um padrão e um substituto de poucas letras (o substituto vazio tira glifos; o mais longo
divide):

- na página (`substituir.aplicar_na_pagina`, o que o controlador roda na cópia): o texto
  depois é o de antes com cada caso trocado pelo substituto dele, e nada mais; desfazer
  (`historico.mudanca`, para trás) volta à página de antes, os mesmos `Box`;
- no livro, pelo `ControladorDaSubstituicao` (a prévia numa thread, aplicar numa transação, o
  Ctrl+Z e o Ctrl+Y do projeto): desfazer volta ao texto de antes em todas as páginas, refazer
  ao substituído, e o projeto reaberto do disco tem o texto do último passo.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import fitz
from hypothesis import strategies as st

from abbychess import busca as bs
from abbychess import historico as hs
from abbychess import sessao as ss
from abbychess import substituir as sb
from abbychess.modelo import Box, gid_de
from abbychess.projeto import ProjetoDeLivro

from tests.ajudantes import ExecutorManual, _ate_valer, _controlador, _pagina
from tests.estrategias import propriedade

PALAVRA = st.text("abcd", min_size=1, max_size=4)
LINHA = st.lists(PALAVRA, min_size=1, max_size=3).map(" ".join)
PADRAO = st.text("abcd", min_size=1, max_size=2)
SUBSTITUTO = st.text("abx", max_size=2)


def _casos(pagina, padrao, modelo):
    expressao, _dica = bs.compilar(bs.Opcoes(padrao))
    texto, unidades = ss.texto_e_unidades(pagina)
    indexada = bs.indexar_pagina(pagina, "pt", margens=(), montada=(texto, unidades))
    return texto, sb.casos_da_pagina(indexada, unidades, expressao,
                                     sb.substituto(modelo, False), sb.PROSA)


def _com_os_casos(texto, casos):
    """O texto com cada caso trocado pelo substituto dele."""
    partes, posicao = [], 0
    for caso in sorted(casos, key=lambda c: c.inicio):
        partes += [texto[posicao:caso.inicio], caso.depois]
        posicao = caso.fim
    return "".join(partes + [texto[posicao:]])


def _palavras(texto):
    """As palavras de cada linha que tem alguma. Os espaços e as quebras são da geometria dos
    glifos: a palavra trocada por nada não deixa glifo para guardar o espaço dela, e a linha
    que ficou sem glifo sai."""
    return [ln.split() for ln in texto.split("\n") if ln.split()]


def lei_de_substituir_na_pagina(linhas, padrao, modelo):
    """O texto substituído é o de antes com os casos trocados; desfazer volta à página."""
    pagina = _pagina(*linhas)
    texto, casos = _casos(pagina, padrao, modelo)
    bons = [c for c in casos if c.aplicavel]
    if not bons:
        return
    antes = pagina.instantaneo()
    copia = pagina.instantaneo()
    try:
        sb.aplicar_na_pagina(copia, bons)
    except ss.Recusa:
        return                                  # sem tradução: nada aplicado
    agora, esperado = ss.texto_e_unidades(copia)[0], _com_os_casos(texto, bons)
    if {b.gid for b in antes.boxes} - copia.vivos:
        # Saiu um box (tirar ou juntar glifos): as linhas são do core, pela geometria, e a
        # página sintética de linhas curtas muda de colunas sem ele (como na máquina da
        # página, `test_modelo_estados`): os caracteres ficam os substituídos.
        assert sorted("".join(agora.split())) == sorted("".join(esperado.split()))
    else:
        assert _palavras(agora) == _palavras(esperado)
    m = hs.mudanca(antes, copia.instantaneo())
    hs.conferir(m, copia, para_tras=True)
    hs.aplicar(m, copia, para_tras=True)
    assert copia.boxes == list(antes.boxes) and copia.decisoes == antes.decisoes
    assert ss.texto_e_unidades(copia)[0] == texto


test_substituir_na_pagina_troca_os_casos_e_desfaz, \
    test_substituir_na_pagina_troca_os_casos_e_desfaz_noturna = propriedade(
        lei_de_substituir_na_pagina, rapida=40,
        linhas=st.lists(LINHA, min_size=1, max_size=2), padrao=PADRAO, modelo=SUBSTITUTO)


# ----------------------------------------------------------------------
# No livro: o controlador, a prévia, o Ctrl+Z e o Ctrl+Y, o disco
# ----------------------------------------------------------------------

def _livro(pasta: Path, textos) -> ProjetoDeLivro:
    pdf = pasta / "livro.pdf"
    with fitz.open() as doc:
        for _ in textos:
            doc.new_page(width=200, height=100)
        doc.save(str(pdf))
    projeto = ProjetoDeLivro.criar(pasta / "livros", "Substituir", pdf)
    for i, texto in enumerate(textos):
        pagina = projeto.pagina_para_editar(i)
        pagina.boxes = [Box(gid_de(pagina.pid, n), b.entry)
                        for n, b in enumerate(_pagina(texto).boxes)]
        pagina.proximo_n, pagina.estado = len(pagina.boxes), "reconhecida"
        projeto.salvar_modelo(pagina)
    return projeto


def _textos(projeto, n):
    return [ss.texto_e_unidades(projeto.carregar_modelo(i))[0] for i in range(n)]


def _letras_das(textos):
    """Os caracteres de cada página, sem os espaços (a ordem das linhas é a lei da página)."""
    return [sorted("".join(t.split())) for t in textos]


def lei_de_substituir_no_livro(tmp_path, textos, padrao, modelo):
    """Substituir no livro e desfazer volta ao texto de antes em todas as páginas; refazer, ao
    substituído; o projeto reaberto tem o do último passo."""
    from abbychess.controlador_da_substituicao import ControladorDaSubstituicao
    from abbychess.controladores import ControladorDaBusca

    pasta = Path(tempfile.mkdtemp(dir=tmp_path))
    projeto = _livro(pasta, textos)
    try:
        executor = ExecutorManual()
        ctl = _controlador(projeto, executor)
        busca = ControladorDaBusca(ctl, paralelo=False)
        busca.abrir()
        _ate_valer(busca.pronto.is_set)
        s = ControladorDaSubstituicao(ctl, busca)
        previas, feitas = [], []
        ctl.eventos.ligar("previa_pronta", lambda p, _fora: previas.append(p))
        ctl.eventos.ligar("substituicao_feita", lambda *a: feitas.append(a))
        antes = _textos(projeto, len(textos))
        assert s.previa(bs.Opcoes(padrao, escopo=bs.LIVRO), modelo, sb.PROSA)
        _ate_valer(lambda: previas)
        aceitos = {p.indice: [c for c in p.casos if c.aplicavel] for p in previas[-1]}
        esperado = list(antes)
        for p in previas[-1]:
            esperado[p.indice] = _com_os_casos(p.texto, aceitos[p.indice])
        s.aplicar(aceitos, "Substituir", {p.indice: p for p in previas[-1]})
        executor.tudo()
        if not any(aceitos.values()):
            assert _textos(projeto, len(textos)) == antes
            return
        _ate_valer(lambda: feitas)
        falhas = feitas[-1][2]
        for i in falhas:                         # a página sem tradução fica como estava
            esperado[i] = antes[i]
        substituidos = _textos(projeto, len(textos))
        assert _letras_das(substituidos) == _letras_das(esperado)
        ctl.desfazedor.desfazer()
        executor.tudo()
        assert _textos(projeto, len(textos)) == antes
        ctl.desfazedor.refazer()
        executor.tudo()
        assert _textos(projeto, len(textos)) == substituidos
        assert projeto.fechar(), "o gravador não gravou tudo"
        reaberto = ProjetoDeLivro.abrir(projeto.pasta)
        try:
            assert _textos(reaberto, len(textos)) == substituidos
        finally:
            reaberto.fechar()
    finally:
        projeto.fechar()


test_substituir_no_livro_desfaz_em_todas_as_paginas, \
    test_substituir_no_livro_desfaz_em_todas_as_paginas_noturna = propriedade(
        lei_de_substituir_no_livro, rapida=3, deadline=None,
        textos=st.lists(LINHA, min_size=2, max_size=3), padrao=PADRAO, modelo=SUBSTITUTO)
