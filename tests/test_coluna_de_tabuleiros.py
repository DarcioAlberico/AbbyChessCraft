"""A coluna feita só de tabuleiros (CA-5.2): na p. 12 do Yusupov, os três diagramas enchem a
coluna da esquerda e o texto fica todo na da direita. Só pelos glifos a página tem uma coluna, e
os diagramas caíam pela altura no meio do comentário. Cada um entra logo antes do título dele
("Diagram 1-10"), onde começa o comentário; sem um título por tabuleiro, na altura dele."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from core.box_model import BoxEntry
from PIL import Image

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


def _comentarios(x0: int = 500, titulo: str = "Diagram 1-{}") -> list:
    """O resto da página anterior e três comentários, cada um com o título e cinco linhas,
    com o vão acima do título que abre parágrafo."""
    entries, y = _linha("fim.", 100, x0), 150
    for k in (1, 2, 3):
        y += 60
        entries += _linha(titulo.format(k), y, x0)
        for i in range(5):
            y += 50
            entries += _linha(f"a{k}{i}", y, x0)
        y += 50
    return entries


def _comentario(k: int, titulo: str = "Diagram 1-{}") -> str:
    return "\n".join([titulo.format(k)] + [f"a{k}{i}" for i in range(5)])


def test_cada_tabuleiro_da_esquerda_vem_antes_do_titulo_dele():
    assert _blocos(_comentarios()) == ["fim.", "d0", _comentario(1), "d1", _comentario(2),
                                       "d2", _comentario(3)]


def test_cada_tabuleiro_da_direita_vem_antes_do_titulo_dele():
    caixas = tuple((500, y1, 800, y2) for _, y1, _, y2 in PILHA)
    assert _blocos(_comentarios(x0=100), caixas) == ["fim.", "d0", _comentario(1), "d1",
                                                     _comentario(2), "d2", _comentario(3)]


@pytest.mark.parametrize("titulo", ["Di ram 1-{}", "Dia am 1–{}", "Diagrama {}", "Diagram {}0"])
def test_o_titulo_mal_lido_ou_de_outro_idioma_tambem_vale(titulo):
    assert _blocos(_comentarios(titulo=titulo)) == [
        "fim.", "d0", _comentario(1, titulo), "d1", _comentario(2, titulo),
        "d2", _comentario(3, titulo)]


def test_corrigir_o_titulo_poe_o_tabuleiro_antes_dele():
    """A correção de uma letra não refaz as linhas guardadas; o título é olhado a cada vez."""
    errado = _comentarios(titulo="Xiagram 1-{}")
    assert _blocos(errado)[:2] != ["fim.", "d0"]
    certo = [replace(e, char="D") if e.char == "X" else e for e in errado]
    assert _blocos(certo) == ["fim.", "d0", _comentario(1), "d1", _comentario(2),
                              "d2", _comentario(3)]


def test_sem_um_titulo_por_tabuleiro_vale_a_altura_depois_do_fim_de_frase():
    """As linhas ao lado do tabuleiro, cada uma terminada ou não em frase."""
    linhas = [e for k in range(20)
              for e in _linha(f"l{k}." if k == 8 else f"l{k}", 100 + 50 * k)]
    assert _blocos(linhas) == [
        "d0", "\n".join(f"l{k}" if k != 8 else "l8." for k in range(9)), "d1",
        "\n".join(f"l{k}" for k in range(9, 14)), "d2",
        "\n".join(f"l{k}" for k in range(14, 20))]


def test_o_titulo_de_mais_nao_pareia():
    """Quatro títulos e três tabuleiros: a conta não fecha, e nenhum vai ao título errado."""
    sobra = _linha("Diagram 1-4", 1300)
    blocos = _blocos(_comentarios() + sobra)
    assert blocos[0] == "d0" and "Diagram 1-1" in blocos[1]


def test_a_legenda_lida_vai_com_o_tabuleiro_e_nao_conta_como_titulo():
    legenda = _linha("Diagram 1-2", 410, x0=100)
    blocos = _blocos(legenda + _comentarios())
    assert blocos == ["fim.", "d0", _comentario(1) + "\nDiagram 1-2", "d1", _comentario(2),
                      "d2", _comentario(3)]


def test_o_titulo_de_largura_inteira_vem_antes_de_tudo():
    titulo = _linha("Um titulo que atravessa a calha", 40, x0=100)
    assert _blocos(titulo + _comentarios())[:3] == [
        "Um titulo que atravessa a calha\nfim.", "d0", _comentario(1)]


def test_a_exportacao_poe_o_tabuleiro_e_a_legenda_antes_do_titulo():
    legenda = _linha("Diagram 1-2", 410, x0=100)
    extraida = mo.pagina_extraida(0, legenda + _comentarios(), PILHA, Image.new("RGB", (1000, 1500)),
                                  desenhar_diagramas=False)
    ordem = [getattr(b, "texto", "figura").split(" ")[0] + " " + getattr(b, "texto", "").split(" ")[-1]
             if not isinstance(b, mo.Figura) else "figura" for b in extraida.blocos]
    figuras = [k for k, nome in enumerate(ordem) if nome == "figura"]
    assert len(figuras) == 3
    depois = [extraida.blocos[k + 1].texto for k in figuras]
    assert [d.split(" a")[0] for d in depois] == ["Diagram 1-1", "Diagram 1-2", "Diagram 1-3"]
    assert extraida.blocos[figuras[1] - 1].texto == "Diagram 1-2"


def test_a_pagina_tem_as_duas_colunas_e_sabe_qual_e_a_pilha():
    leitura = OrdemDeLeitura.da_pagina(_comentarios(), PILHA)
    assert len(leitura.colunas) == 2 and leitura.coluna_da_pilha == 0
    caixas = tuple((500, y1, 800, y2) for _, y1, _, y2 in PILHA)
    assert OrdemDeLeitura.da_pagina(_comentarios(x0=100), caixas).coluna_da_pilha == 1
    assert OrdemDeLeitura.da_pagina(_comentarios()).coluna_da_pilha is None


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
    diagrama logo antes da linha que o gabarito põe depois dele (a p. 12 tem os três na coluna
    da esquerda, e cada um vem antes do título do comentário dele, na da direita)."""
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
    linha_casada = {linhas[ip][0]: jv for ip, jv in casados}
    for did in diagramas:
        seguinte = min(k for k in linha_casada if k > itens.index(did))
        assert blocos[corpo[linha_casada[seguinte]]["bloco"]]["ordem"] == blocos[did]["ordem"] + 1, did
