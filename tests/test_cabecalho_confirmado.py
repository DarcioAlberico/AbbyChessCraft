"""O cabeçalho aprendido pelos confirmados (SPEC §5.1, etapa 5): a regra das margens corridas
"aprende por livro (o padrão dos títulos corridos confirmados, pares e ímpares)".

Confirmado é o título corrido que o usuário marcou: a área de cabeçalho ou de rodapé que ele
desenhou ou cuja função ele trocou (`automatica=False`). As letras dela valem nas páginas da
mesma paridade: como repetição (sem precisar de outra página que a repita) e, mais parecidas,
também para o título colado no texto, sem o vão que a regra pede.
"""

from __future__ import annotations

import fitz
from dataclasses import replace

from core.box_model import BoxEntry

from abbychess import exportar as ex
from abbychess import margens as mg
from abbychess import zonas as zn
from abbychess.leitor import FONTE_MANUAL
from abbychess.projeto import ProjetoDeLivro

LARGURA, ALTURA = 2480, 3500
FRASES = ("as brancas jogam e ganham", "um lance muito ruim", "o plano consiste em atacar",
          "e a Dama sob ataque", "trocar peças num momento bom", "evitar golpes baratos")


def _linha(texto: str, y: int, x: int = 300, altura: int = 50):
    return [BoxEntry(c, x + 30 * i, y, x + 30 * i + 25, y + altura, 1.0, FONTE_MANUAL)
            for i, c in enumerate(texto) if c != " "]


def _corpo(y: int, linhas: int = 6):
    return [b for k in range(linhas) for b in _linha(FRASES[k % len(FRASES)], y + 60 * k)]


def _colada(titulo: str = "XADREZ VITORIOSO"):
    """O título corrido a um passo da primeira linha do texto: sem o vão, a regra o deixa."""
    return _linha(titulo, 260) + _corpo(320)


def _tirados(boxes, indices):
    return "".join(boxes[k].char for k in sorted(indices))


def _zona_do_usuario(funcao: str, caixa=(250, 240, 1000, 315)):
    zona = zn.nova(zn.TEXTO, caixa, LARGURA, ALTURA)
    lista = [zona]
    zn.trocar_funcao(lista, 0, funcao)
    return lista[0]


CONFIRMADO_PAR = mg.Confirmado(paridade=0, lugar="cabecalho", letras="xadrezvitorioso")


def test_sem_confirmado_o_titulo_colado_fica_no_texto():
    paginas = {i: (_colada(), ALTURA) for i in (20, 22)}
    assert mg.margens_corridas(paginas) == {20: set(), 22: set()}


def test_o_confirmado_tira_o_titulo_colado_nas_paginas_da_mesma_paridade():
    paginas = {i: (_colada(), ALTURA) for i in (20, 21, 22)}
    funcoes = mg.funcoes_das_margens(paginas, [CONFIRMADO_PAR])
    for i in (20, 22):
        assert _tirados(paginas[i][0], funcoes[i]) == "XADREZVITORIOSO"
        assert set(funcoes[i].values()) == {"cabecalho"}
    assert funcoes[21] == {}                            # a ímpar tem o seu, que ninguém confirmou


def test_o_confirmado_vale_como_repeticao_numa_pagina_sozinha():
    """Com o vão, mas sem número e sem outra página que o repita: só o confirmado o tira."""
    boxes = _linha("XADREZ VITORIOSO", 180) + _corpo(360)
    assert mg.margens_corridas({22: (boxes, ALTURA)}) == {22: set()}
    tirar = mg.margens_corridas({22: (boxes, ALTURA)}, [CONFIRMADO_PAR])[22]
    assert _tirados(boxes, tirar) == "XADREZVITORIOSO"


def test_o_rodape_confirmado_nao_vale_em_cima():
    rodape = mg.Confirmado(paridade=0, lugar="rodape", letras="xadrezvitorioso")
    boxes = _linha("XADREZ VITORIOSO", 180) + _corpo(360)
    assert mg.margens_corridas({22: (boxes, ALTURA)}, [rodape]) == {22: set()}


def test_a_linha_colada_so_um_pouco_parecida_fica():
    """Colada no texto, a linha precisa se parecer mais com o confirmado do que pede a
    repetição: "XADREZ BRASILEIRO" divide letras com "xadrezvitorioso", mas é outra."""
    boxes = _colada("XADREZ BRASILEIRO")
    assert mg.margens_corridas({22: (boxes, ALTURA)}, [CONFIRMADO_PAR]) == {22: set()}


def test_o_lance_colado_no_texto_nunca_e_cabecalho():
    boxes = _linha("13.Cf3 Cf6", 260) + _corpo(320)
    lance = mg.Confirmado(paridade=0, lugar="cabecalho", letras="cfcf")
    assert mg.margens_corridas({22: (boxes, ALTURA)}, [lance]) == {22: set()}


def test_os_confirmados_saem_das_areas_do_usuario():
    boxes = _colada()
    automatica = replace(_zona_do_usuario("cabecalho"), automatica=True)
    numero = _zona_do_usuario("numero_de_pagina", (250, 240, 1000, 315))
    so_numero = _linha("22", 3350) + _corpo(320)
    confirmados = mg.confirmados_das_areas({
        20: (boxes, [_zona_do_usuario("cabecalho")]),
        21: (boxes, [automatica]),                       # a regra achou: ninguém confirmou
        22: (boxes, [numero]),                           # o número não é título corrido
        23: (so_numero, [_zona_do_usuario("rodape", (250, 3330, 1000, 3410))]),
        25: (_linha("YASSER SEIRAWAN", 3350) + _corpo(320),
             [_zona_do_usuario("rodape", (250, 3330, 1000, 3410))])})
    assert confirmados == [mg.Confirmado(0, "cabecalho", "xadrezvitorioso"),
                           mg.Confirmado(1, "rodape", "yasserseirawan")]


def _livro(tmp_path, paginas: int):
    """Um PDF de páginas em branco do tamanho de uma digitalização a 300 dpi."""
    doc = fitz.open()
    for _ in range(paginas):
        doc.new_page(width=LARGURA * 72 / 300, height=ALTURA * 72 / 300)
    caminho = tmp_path / "livro.pdf"
    doc.save(caminho)
    doc.close()
    return ProjetoDeLivro.criar(tmp_path / "livros", "Confirmado", caminho)


def test_a_exportacao_aprende_o_cabecalho_marcado_numa_pagina(tmp_path):
    projeto = _livro(tmp_path, 3)
    try:
        for i in range(3):
            projeto.salvar_pagina(i, _colada())
        projeto.salvar_zonas(0, [_zona_do_usuario("cabecalho")])
        paginas = ex.paginas_do_projeto(projeto, None)
        textos = {i: " ".join(b.texto for b in p.blocos) for i, p in enumerate(paginas)}
        assert "XADREZ" not in textos[0]                # a área marcada
        assert "XADREZ" not in textos[2]                # a par, que aprendeu com ela
        assert "XADREZ" in textos[1]                    # a ímpar, que ninguém confirmou
        assert all(t.startswith("as brancas jogam") for i, t in textos.items() if i != 1)
    finally:
        projeto.fechar()
