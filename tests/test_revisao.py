"""A revisão (SPEC §8, passo C), sem a janela: os modos e o escopo da fila (F7, Shift+F7,
Alt+↓ no livro), a fila recalculada só para os glifos tocados e o F6 pelo resumo do livro."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from core.box_model import BoxEntry

from abbychess import livro as lv
from abbychess.modelo import Box, gid_de


def _escrever(projeto, indice, texto, confiancas):
    """A página `indice` com uma letra por box (as confianças na ordem das letras)."""
    pagina = projeto.pagina_para_editar(indice)
    boxes, x, n = [], 20, 0
    for palavra in texto.split(" "):
        for letra in palavra:
            boxes.append(Box(gid_de(pagina.pid, n),
                             BoxEntry(letra, x, 20, x + 18, 50, confiancas[n], "net")))
            n, x = n + 1, x + 22
        x += 30
    pagina.boxes, pagina.proximo_n, pagina.estado = boxes, n, "reconhecida"
    projeto.salvar_modelo(pagina)
    return pagina


@pytest.fixture
def livro(tmp_path):
    """Três páginas: a 1 e a 3 com glifos a revisar (confiança abaixo de 0,90), a 2 sem."""
    from abbychess.controladores import ControladorDaFila
    from abbychess.projeto import ProjetoDeLivro
    from tests.test_controlador import ExecutorManual, _controlador
    from tests.test_livro import pdf_sintetico

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Três", pdf_sintetico(tmp_path))
    _escrever(projeto, 0, "cab bca", [0.5, 0.2, 0.95, 0.3, 0.6, 0.4])
    _escrever(projeto, 1, "abc", [0.99, 0.99, 0.99])
    _escrever(projeto, 2, "ba ab", [0.7, 0.1, 0.95, 0.8])
    ctl = _controlador(projeto, ExecutorManual())
    verificador = SimpleNamespace(desconhecidas=[], posicao=0, andar=lambda p: None,
                                  verificar=lambda: True)
    fila = ControladorDaFila(ctl, verificador, SimpleNamespace(proximo_do_livro=lambda: None))
    yield projeto, ctl, fila
    projeto.fechar()


def _letras(ctl, gids):
    return "".join(ctl.modelo.box(g).entry.char for g in gids)


def test_os_modos_ordenam_a_fila(livro):
    projeto, ctl, fila = livro
    fila.definir("confianca")
    assert _letras(ctl, ctl.fila()) == "abacc"            # 0,2 0,3 0,4 0,5 0,6
    fila.definir("leitura")
    assert _letras(ctl, ctl.fila()) == "cabca"            # a ordem da página, sem o 0,95
    fila.definir("caractere")
    assert _letras(ctl, ctl.fila()) == "aabcc"            # pela leitura; em cada uma, a confiança
    fila.ciclar()
    assert fila.modo == "palavras"


def test_no_escopo_livro_o_fim_da_pagina_leva_a_proxima_com_pendentes(livro):
    projeto, ctl, fila = livro
    fila.definir("leitura")
    fila.definir_escopo("livro")
    ctl.escolher(ctl.fila()[-1])
    fila.andar(+1)                                        # a página 2 não tem pendentes
    assert ctl.indice == 2 and ctl.atual == ctl.fila()[0]
    fila.andar(-1)                                        # o começo da 3 volta ao fim da 1
    assert ctl.indice == 0 and ctl.atual == ctl.fila()[-1]
    assert fila.contador() == "5/5 · livro 8"
    fila.alternar_escopo()                                # Shift+F7: só a página
    fila.andar(+1)
    assert ctl.indice == 0 and ctl.atual == ctl.fila()[0]


def test_na_confianca_o_livro_segue_depois_de_pular_todos(livro):
    projeto, ctl, fila = livro
    fila.definir("confianca")
    fila.definir_escopo("livro")
    ctl.ir_ao_primeiro_pendente()
    for _ in range(4):                                    # os 4 primeiros vão para o fim
        fila.andar(+1)
    assert ctl.indice == 0
    fila.andar(+1)                                        # o quinto: todos pulados
    assert ctl.indice == 2


def test_a_fila_julga_de_novo_so_os_glifos_tocados(livro, monkeypatch):
    from abbychess import controlador as cp
    from abbychess import edicao as ed

    projeto, ctl, fila = livro
    ctl.fila()
    julgados = []
    original = cp.precisa_revisao
    monkeypatch.setattr(cp, "precisa_revisao", lambda *a: (julgados.append(a), original(*a))[1])
    ctl.fila()
    assert julgados == []                                 # nada mudou
    ed.corrigir(ctl.modelo, ctl.modelo.boxes[0].gid, "x")
    ctl.fila()
    assert len(julgados) == 1                             # só o corrigido


def test_o_f6_conta_pelo_resumo_sem_abrir_as_paginas(livro, monkeypatch):
    projeto, ctl, fila = livro
    assert projeto.descarregar(10)
    monkeypatch.setattr(projeto, "carregar_modelo", lambda i: (_ for _ in ()).throw(
        AssertionError("abriu a página")))
    limiares = ctl.leitor.limiares
    assert lv.pendentes_por_pagina(projeto, limiares) == {0: 5, 2: 3}
    assert lv.proxima_com_pendentes(projeto, limiares, 0) == 2
    assert lv.anterior_com_pendentes(projeto, limiares, 0) == 2
    mais_baixo = type(limiares)(**{**vars(limiares), "revisao": 0.35})
    assert lv.pendentes_por_pagina(projeto, mais_baixo) == {0: 2, 2: 1}   # outro limiar


def test_ca_8_4_esquecer_devolve_a_fila_os_lidos_no_livro_e_desfazer_os_tira(livro):
    """Uma amostra que leu 30 glifos em 3 páginas (uma verificada): esquecê-la devolve os 30
    à fila (a verificada volta a em_revisao); desfazer os tira de novo."""
    import time

    import numpy as np

    from abbychess.controladores import ControladorDaBusca
    from abbychess.modelo import EM_REVISAO, VERIFICADA

    projeto, ctl, fila = livro
    caminho = ctl.leitor.ensinar(np.full((30, 18), 255, np.uint8), "e", origem="teste")
    nome = Path(caminho).resolve().relative_to(Path(projeto.pasta_de_padroes).resolve()).as_posix()
    for indice in range(3):
        pagina = projeto.pagina_para_editar(indice)
        pagina.boxes = [Box(gid_de(pagina.pid, 100 + n),
                            BoxEntry("e", 20 + 22 * n, 100, 38 + 22 * n, 130, 0.97, "livro"),
                            amostra=nome) for n in range(10)] + list(pagina.boxes)
        pagina.estado = VERIFICADA if indice == 1 else pagina.estado
        projeto.salvar_modelo(pagina)
    ctl.ir_para(0)
    fila_da_interface = []
    ctl.executar.na_interface = fila_da_interface.append
    busca = ControladorDaBusca(ctl, paralelo=False)
    ctl.lidos_pelas_amostras = busca.lidos_por
    busca.abrir()

    def esperar(condicao):
        fim = time.monotonic() + 20
        while not condicao() and time.monotonic() < fim:
            while fila_da_interface:
                fila_da_interface.pop(0)()
            time.sleep(0.01)
        assert condicao()
    esperar(busca.pronto.is_set)

    def da_amostra():
        return sum(1 for i in range(3) for b in projeto.carregar_modelo(i).boxes
                   if b.entry.source == "livro" and b.amostra == nome)

    def na_fila():
        return sum(1 for i in range(3) for b in projeto.carregar_modelo(i).boxes
                   if b.gid % 1000 >= 100 and b.entry.source == "none" and b.entry.char == "e")
    assert da_amostra() == 30 and na_fila() == 0
    ctl.esquecer([caminho])
    ctl.executar.tudo()
    esperar(lambda: na_fila() == 30)
    assert da_amostra() == 0 and projeto.carregar_modelo(1).estado == EM_REVISAO
    assert len(ctl.historico.proxima_a_desfazer().paginas) == 3      # uma transação só
    ctl.desfazer()
    ctl.executar.tudo()
    assert na_fila() == 0 and da_amostra() == 30
    assert projeto.carregar_modelo(1).estado == VERIFICADA
    assert Path(caminho).exists()                        # a amostra voltou


# ----------------------------------------------------------------------
# O aviso de conflito e o efeito ao ensinar (§8.3, CA-8.6)
# ----------------------------------------------------------------------

def test_ca_8_6_o_conflito_numa_matriz_montada_a_mao():
    import numpy as np

    from abbychess.padroes import conflito_nas_distancias

    distancias = np.array([0.05, 0.08, 0.30, 0.02, 0.09])
    chars = ["1", "1", "1", "l", "I"]
    cabe = [True, True, True, True, True]
    assert conflito_nas_distancias(distancias, chars, cabe, "l", 0.10) == ("1", 2, 0.08)
    assert conflito_nas_distancias(distancias, chars, cabe, "l", 0.04) is None
    assert conflito_nas_distancias(distancias, chars, [False] * 5, "l", 0.10) is None
    assert conflito_nas_distancias(distancias, chars, cabe, "1", 0.10) == ("l", 1, 0.02)


def test_ca_8_6_o_conflito_nos_padroes_do_livro(tmp_path):
    import numpy as np

    from abbychess.padroes import PadroesDoLivro

    padroes = PadroesDoLivro(tmp_path / "padroes")
    barra = np.full((30, 12), 255, np.uint8)
    barra[:, 5:7] = 0
    for k in range(3):
        padroes.ensinar(barra, "1", None, f"o{k}")
    quadrado = np.zeros((30, 12), np.uint8)
    assert padroes.conflito(barra, "l", None, 0.10)[:2] == ("1", 3)
    assert padroes.conflito(barra, "1", None, 0.10) is None      # o mesmo caractere
    assert padroes.conflito(quadrado, "l", None, 0.01) is None   # longe


def test_o_aviso_de_ensino_diz_o_efeito_e_o_conflito(livro):
    from abbychess import pagina as pg

    projeto, ctl, fila = livro
    fila.definir("leitura")
    ctl.escolher(ctl.modelo.boxes[0].gid)                 # o primeiro "c" (há outro)
    efeito, conflito = ctl.aviso_de_ensino("e")
    assert efeito == "Enter ensina 'e' · 1 iguais nesta página" and conflito == ""
    recorte = pg.recorte(ctl.imagem, ctl.modelo.boxes[0].entry)
    ctl.leitor.ensinar(recorte, "o", origem="teste")
    efeito, conflito = ctl.aviso_de_ensino("e")
    assert "amostra(s) de 'o'" in conflito


def test_ca_8_5_todas_as_transicoes_do_4_4():
    """Cada par (estado, evento) da tabela, e todo par fora dela deixa o estado como está."""
    from abbychess import modelo as md

    eventos = {e for _s, e in md._TRANSICOES}
    for estado in md.ESTADOS:
        for evento in eventos:
            esperado = md._TRANSICOES.get((estado, evento), estado)
            assert md.proximo_estado(estado, evento) == esperado, (estado, evento)
    assert md.proximo_estado(md.VERIFICADA, "esquecer_padrao") == md.EM_REVISAO
    assert md.proximo_estado(md.RECONHECIDA, "verificar") == md.VERIFICADA
