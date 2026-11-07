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
    boxes = _linha("13.Nf3 Nf6", 260) + _corpo(320)      # o `tem_lance` do core lê o inglês
    lance = mg.Confirmado(paridade=0, lugar="cabecalho", letras="nfnf")
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


def test_as_areas_automaticas_aprendem_com_o_cabecalho_marcado_noutra_pagina():
    """O modo Áreas (`_aprender_margens`): a área automática do título colado da página aberta
    vira cabeçalho porque o usuário marcou o mesmo título noutra página par."""
    from types import SimpleNamespace

    from abbychess.controlador_de_layout import ControladorDeLayout

    def modelo(zonas=()):
        return SimpleNamespace(boxes=[SimpleNamespace(entry=b) for b in _colada()],
                               zonas=list(zonas))

    modelos = {0: modelo([_zona_do_usuario("cabecalho")]), 1: modelo(), 2: modelo()}
    eventos = SimpleNamespace(ligar=lambda *_a: None)

    def aberta(indice):
        projeto = SimpleNamespace(resumo=SimpleNamespace(paginas_lidas=lambda: sorted(modelos)),
                                  carregar_modelo=modelos.get)
        return SimpleNamespace(eventos=eventos, projeto=projeto, indice=indice,
                               modelo=modelos[indice], imagem=SimpleNamespace(height=ALTURA))

    automatica = replace(_zona_do_usuario("texto"), automatica=True)
    [par] = ControladorDeLayout(aberta(2))._aprender_margens([automatica])
    [impar] = ControladorDeLayout(aberta(1))._aprender_margens([automatica])
    assert (par.funcao, impar.funcao) == ("cabecalho", "texto")


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
        textos = [" ".join(b.texto for b in p.blocos) for p in paginas]
        # O parágrafo que a paginação partiu volta a ser um: o texto da página 2 entra no da
        # 1. Por isso a conta é no livro: só o título da ímpar, que ninguém confirmou, fica;
        # sem o confirmado, o da par 2 também ficava.
        assert " ".join(textos).count("XADREZ") == 1
        assert textos[0].startswith("as brancas jogam")       # a área marcada
        assert textos[1].startswith("XADREZ VITORIOSO")       # a ímpar
    finally:
        projeto.fechar()
