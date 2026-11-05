"""A coluna feita só de tabuleiros (CA-5.2): na p. 12 do Yusupov, os três diagramas enchem a
coluna da esquerda e o texto fica todo na da direita. Só pelos glifos a página tem uma coluna,
e os diagramas caíam pela altura no meio do comentário."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from core.box_model import BoxEntry

from abbychess import montagem as mo
from abbychess import texto as tx
from abbychess.layout import OrdemDeLeitura, _coluna_dos_tabuleiros
from tests.ajudantes import _lido
from tests.livros import PASTA_DOS_PDFS

PILHA = ((100, 100, 400, 400), (100, 450, 400, 750), (100, 800, 400, 1100))
VERDADE = Path(__file__).resolve().parent / "verdade" / "yusupov"


def _linha(texto: str, y: int, x0: int = 500) -> list:
    return [BoxEntry(c, x0 + 22 * k, y, x0 + 22 * k + 20, y + 30, 0.9, "net")
            for k, c in enumerate(texto) if c != " "]


def _coluna_de_texto(x0: int = 500, n: int = 20, topo: int = 100) -> list:
    """`n` linhas, "l0" a "l19", uma frase só para nenhum fim de frase decidir nada."""
    return [e for k in range(n) for e in _linha(f"l{k}", topo + 50 * k, x0)]


def _blocos(entries, caixas=PILHA) -> list:
    pagina = tx.pagina_avulsa(entries, [_lido(caixa=c) for c in caixas])
    doc = tx.montar(pagina)
    return [b.diagrama_id or tx.texto_do_bloco(doc, b) for b in doc.blocos]


def _texto_inteiro(n: int = 20) -> str:
    return "\n".join(f"l{k}" for k in range(n))


def test_a_pilha_de_tabuleiros_a_esquerda_vem_antes_do_texto_da_direita():
    assert _blocos(_coluna_de_texto()) == ["d0", "d1", "d2", _texto_inteiro()]


def test_a_pilha_de_tabuleiros_a_direita_vem_depois_do_texto_da_esquerda():
    caixas = tuple((500, y1, 800, y2) for _, y1, _, y2 in PILHA)
    assert _blocos(_coluna_de_texto(x0=100), caixas) == [_texto_inteiro(), "d0", "d1", "d2"]


def test_a_legenda_lida_fica_na_coluna_do_tabuleiro():
    legenda = _linha("Diagrama", 410, x0=100)
    assert _blocos(legenda + _coluna_de_texto()) == [
        "d0", "Diagrama", "d1", "d2", _texto_inteiro()]


def test_o_titulo_de_largura_inteira_vem_antes_da_pilha():
    titulo = _linha("Um titulo que atravessa a calha", 40, x0=100)
    assert _blocos(titulo + _coluna_de_texto()) == [
        "Um titulo que atravessa a calha", "d0", "d1", "d2", _texto_inteiro()]


def test_a_exportacao_le_a_pilha_como_o_documento():
    leitura = OrdemDeLeitura.da_pagina(_coluna_de_texto(), PILHA)
    assert len(leitura.colunas) == 2
    extraida = mo.pagina_extraida(0, _coluna_de_texto(), PILHA)
    assert [p.texto for p in extraida.blocos] == [_texto_inteiro().replace("\n", " ")]
    assert (leitura.chave(250, 450), 450) < (leitura.chave(510, 100), 100)


def test_um_tabuleiro_so_nao_faz_coluna():
    """É o tabuleiro que o parágrafo contorna, e a regra é a do fim de frase (`texto`)."""
    assert OrdemDeLeitura.da_pagina(_coluna_de_texto(), PILHA[:1]).colunas == ()


def test_tabuleiros_lado_a_lado_nao_sao_pilha():
    lado_a_lado = ((100, 100, 250, 400), (260, 100, 400, 400))
    assert OrdemDeLeitura.da_pagina(_coluna_de_texto(), lado_a_lado).colunas == ()


def test_a_linha_que_atravessa_na_altura_da_pilha_desfaz_a_coluna():
    """O texto que passa por baixo de um tabuleiro é o de uma coluna só que o contorna."""
    atravessa = _linha("texto longo que corre por baixo", 420, x0=100)
    assert OrdemDeLeitura.da_pagina(_coluna_de_texto() + atravessa, PILHA).colunas == ()


def test_texto_dos_dois_lados_da_pilha_nao_e_coluna_dos_tabuleiros():
    """Com texto dos dois lados, quem diz as colunas são os glifos."""
    esquerda = [e for e in _coluna_de_texto(x0=0) if e.x2 <= 90]
    assert _coluna_dos_tabuleiros(esquerda + _coluna_de_texto(), PILHA, 30) == ()


def test_poucas_linhas_ao_lado_nao_fazem_coluna():
    assert OrdemDeLeitura.da_pagina(_coluna_de_texto(n=5), PILHA).colunas == ()


def test_poucas_linhas_entre_dois_tabuleiros_centrados_nao_sao_coluna():
    """Odds & Ends, i177: uma coluna só, e as linhas entre os tabuleiros ficam à esquerda deles.
    Têm filas bastantes, mas não acompanham a altura da pilha."""
    centrados = ((500, 100, 800, 700), (500, 720, 800, 1320))
    entre = [e for k in range(7) for e in _linha(f"l{k}", 600 + 40 * k, x0=100)]
    assert _coluna_dos_tabuleiros(entre, centrados, 30) == ()


def test_mover_o_tabuleiro_nao_reaproveita_a_ordem_guardada():
    """As linhas guardadas pela chave dependem também das caixas dos tabuleiros."""
    entries = _coluna_de_texto()
    sem_pilha = tx.pagina_avulsa(entries, [_lido(caixa=PILHA[0])])
    assert [b.diagrama_id for b in tx.montar(sem_pilha).blocos if b.diagrama_id] == ["d0"]
    assert _blocos(entries) == ["d0", "d1", "d2", _texto_inteiro()]


# ----------------------------------------------------------------------
# CA-5.2: o livro real
# ----------------------------------------------------------------------

def _caixa_da_linha(linha, por_gid):
    glifos = [por_gid[g] for p in linha.palavras for g in p.gids if g in por_gid]
    return (min(e.x1 for e in glifos), min(e.y1 for e in glifos),
            max(e.x2 for e in glifos), max(e.y2 for e in glifos)) if glifos else None


def _ler_as_paginas(pasta, indices):
    from abbychess import livro as lv
    from abbychess import pagina as pg
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro

    pdf = next(Path(PASTA_DOS_PDFS).rglob("Artur Yusupov - Chess Evolution 1*editable.pdf"))
    projeto = ProjetoDeLivro.criar(pasta, "ca-5-2", pdf)
    leitor = LeitorDoLivro.com_modelos_globais(projeto.pasta_de_padroes,
                                               limiares=projeto.dados.limiares)
    fonte = pg.fonte_do_projeto(projeto)
    lv.reconhecer_paginas(projeto, fonte, leitor, indices)
    return projeto, fonte


def _o_que_o_documento_le(projeto, fonte, indice: int) -> list:
    """Na ordem do Documento: o id de cada diagrama e a caixa relativa de cada linha."""
    from rotular import _caixa_relativa

    pagina = projeto.carregar_modelo(indice)
    doc = tx.montar(pagina)
    lidos, entries = tx._lidos(pagina, False)
    por_gid = {b.gid: e for b, e in zip(lidos, entries)}
    imagem, angulo = fonte.pagina(indice), fonte.inclinacao(indice)
    itens = []
    for bloco in doc.blocos:
        if bloco.diagrama_id:
            itens.append(bloco.diagrama_id)
        caixas = [_caixa_da_linha(ln, por_gid) for ln in bloco.linhas]
        itens += [_caixa_relativa(c, angulo, imagem.width, imagem.height) for c in caixas if c]
    return itens


@pytest.mark.livro_real
@pytest.mark.parametrize("indice", [12, 33])
def test_ca_5_2_a_ordem_das_paginas_de_duas_colunas_do_yusupov(tmp_path, indice):
    """Lida só como imagem: Kendall 0 nas linhas de corpo casadas com o gabarito, e cada
    diagrama antes de toda linha de uma coluna depois da dele (a p. 12 tem os três na da
    esquerda, e o comentário todo na da direita)."""
    from medir import casar, discordancia

    gabarito = json.loads((VERDADE / f"i{indice:03d}.json").read_text(encoding="utf-8"))
    projeto, fonte = _ler_as_paginas(tmp_path, [indice])
    try:
        itens = _o_que_o_documento_le(projeto, fonte, indice)
    finally:
        projeto.fechar()
    linhas = [(k, item) for k, item in enumerate(itens) if not isinstance(item, str)]
    corpo = gabarito["linhas_corpo"]
    casados = casar([caixa for _, caixa in linhas], [ln["caixa_rel"] for ln in corpo])
    # Na p. 12, um cisco do ornamento lido "=" cola em "met by...", e a caixa dela não casa.
    assert len(casados) >= 0.85 * len(corpo)
    blocos = {b["id"]: b for b in gabarito["blocos"]}
    lida = [jv for _, jv in sorted(casados)]
    certa = sorted(lida, key=lambda jv: (blocos[corpo[jv]["bloco"]]["ordem"], jv))
    assert discordancia(lida, certa) == 0.0
    diagramas = [item for item in itens if isinstance(item, str)]
    assert diagramas == [d["id"] for d in gabarito["diagramas"]]
    for did in diagramas:
        depois = {linhas[ip][0] for ip, jv in casados
                  if blocos[corpo[jv]["bloco"]]["coluna"] > blocos[did]["coluna"]}
        assert all(itens.index(did) < k for k in depois), did
