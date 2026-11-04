"""Localizar, sem Qt (SPEC §7.1, §7.3, passo B): o índice, a busca, as classes de xadrez
(CA-7.4), figurina = letra (CA-7.6), o padrão inválido e o lento (CA-7.3), o escopo, o
"onde" e a busca por glifo."""

from __future__ import annotations

import re
import threading

import pytest
from core.box_model import BoxEntry

from abbychess import busca as bs
from abbychess import sessao as ss
from abbychess.modelo import Box, Pagina, gid_de

from tests.ajudantes import _pagina  # noqa: E402,F401,F811
from tests.ajudantes import _ate_valer  # noqa: E402,F401,F811
from tests.ajudantes import _lido  # noqa: E402,F401,F811


def _indice(*linhas, idioma="pt", indice=0):
    p = _pagina(*linhas)
    p.indice = indice
    return bs.indexar_pagina(p, idioma, margens=())


def _achados(paginas, texto, **opcoes):
    if isinstance(paginas, bs.PaginaIndexada):
        paginas = {paginas.indice: paginas}
    resultado = bs.buscar(paginas, bs.Opcoes(texto, **opcoes))
    return [paginas[o.pagina].texto[o.inicio:o.fim] for o in resultado.ocorrencias]


def test_o_indice_tem_o_texto_do_documento_e_o_gid_de_cada_caractere():
    p = _pagina("joga Cf3")
    indexada = bs.indexar_pagina(p, "pt", margens=())
    assert indexada.texto == ss.texto_e_unidades(p)[0] == "joga Cf3"
    assert indexada.gids[5] == p.boxes[4].gid and indexada.gids[4] is None
    assert indexada.etiqueta(0) == bs.PROSA and indexada.etiqueta(5) == bs.NOTACAO


def test_cada_resultado_leva_ao_gid_certo():
    indexada = _indice("vou conc1uir hoje")
    [o] = bs.buscar({0: indexada}, bs.Opcoes(r"(?<=\w)1(?=\w)", regex=True)).ocorrencias
    assert o.gids == (indexada.gids[8],) and o.linha == 1 and o.trecho[o.coluna] == "1"


@pytest.mark.parametrize("idioma, positivos, negativos", [
    ("pt", ["Cf3", "exd5", "O-O", "Te8=D+", "Dxe5#", "♘f3"], ["casa", "x9", "Zf3"]),
    ("en", ["Nf3", "exd5", "O-O-O", "Re8=Q+", "♘f3"], ["house", "Zf3"])])
def test_ca_7_4_a_classe_de_lance(idioma, positivos, negativos):
    for token in positivos:
        assert _achados(_indice(token, idioma=idioma), r"^\L$", regex=True, idioma=idioma), token
    for token in negativos:
        assert not _achados(_indice(token, idioma=idioma), r"^\L$", regex=True,
                            idioma=idioma), token


@pytest.mark.parametrize("classe, idioma, positivos, negativos", [
    (r"\P", "pt", ["C", "D", "♘", "♛"], ["N", "x", "a"]),
    (r"\P", "en", ["N", "Q", "♘"], ["C", "D", "x"]),
    (r"\C", "pt", ["e4", "h8", "a1"], ["i9", "e9", "z1"]),
    (r"\V", "pt", ["±", "∓", "⩲", "!?", "?!", "+-", "!", "∞"], ["a", "*"])])
def test_ca_7_4_as_classes_de_peca_casa_e_valoracao(classe, idioma, positivos, negativos):
    for token in positivos:
        assert _achados(_indice(token, idioma=idioma), rf"^{classe}$", regex=True,
                        maiusculas=True, idioma=idioma), (classe, token)
    for token in negativos:
        assert not _achados(_indice(token, idioma=idioma), rf"^{classe}$", regex=True,
                            maiusculas=True, idioma=idioma), (classe, token)


def test_a_classe_dentro_de_colchetes_e_a_dica():
    padrao, dica = bs.expandir_classes(r"[\P]x\C", "pt")
    assert re.fullmatch(padrao, "Cxe4") and re.fullmatch(padrao, "♘xe4")
    assert dica.startswith(r"\P = peça") and r"\C = casa" in dica
    with pytest.raises(bs.PadraoInvalido):
        bs.expandir_classes(r"[\L]", "pt")


def test_ca_7_6_figurina_igual_a_letra():
    indexada = _indice("joga Cf3 ou ♘f3 ou Nf3 Casa")
    assert _achados(indexada, "Cf3", maiusculas=True, figurina_letra=True) == ["Cf3", "♘f3", "Nf3"]
    assert _achados(indexada, "Cf3", maiusculas=True) == ["Cf3"]
    assert _achados(indexada, "Casa", maiusculas=True, figurina_letra=True) == ["Casa"]


def test_ca_7_3_regex_invalida_e_padrao_lento():
    with pytest.raises(bs.PadraoInvalido):
        bs.buscar({0: _indice("casa")}, bs.Opcoes("(casa", regex=True))
    longo = _indice("a" * 400 + "!")
    with pytest.raises(bs.PadraoLento, match="lento"):
        bs.buscar({0: longo}, bs.Opcoes(r"(\w+)+$", regex=True), tempo_limite=0.02)


def test_maiusculas_palavra_inteira_e_o_escopo():
    paginas = {i: _indice(f"Casa casa casamento {i}", indice=i) for i in range(4)}
    assert len(_achados(paginas, "casa")) == 12
    assert len(_achados(paginas, "casa", maiusculas=True)) == 8
    assert len(_achados(paginas, "casa", palavra_inteira=True)) == 8
    assert len(_achados(paginas, "casa", escopo=bs.PAGINA, pagina_atual=2)) == 3
    assert len(_achados(paginas, "casa", escopo=bs.INTERVALO, intervalo=(1, 2))) == 6
    g = paginas[3].gids                                   # "casa", a segunda palavra
    assert _achados(paginas, "casa", escopo=bs.SELECAO, selecao=(3, g[5], g[8])) == ["casa"]


def test_onde_separa_prosa_notacao_e_fen():
    p = _pagina("joga Cf3 casa")
    p.diagramas = [type("D", (), {"lido": True, "fen": "8/8/8/8/8/5N2/8/8 w",
                                "caixa": (0, 500, 100, 600), "id": "d0"})()]
    indexada = bs.indexar_pagina(p, "pt", margens=())
    assert indexada.texto.endswith("\n8/8/8/8/8/5N2/8/8 w")
    assert _achados(indexada, "a", onde=frozenset({bs.PROSA})) == ["a", "a", "a"]
    assert _achados(indexada, "f3", onde=frozenset({bs.NOTACAO})) == ["f3"]
    assert _achados(indexada, "5N2", onde=frozenset({bs.FEN})) == ["5N2"]
    assert not _achados(indexada, "5N2", onde=frozenset({bs.PROSA, bs.NOTACAO}))


def test_a_busca_cancelada_para_entre_as_paginas():
    paginas = {i: _indice("casa", indice=i) for i in range(5)}
    vistas = []
    resultado = bs.buscar(paginas, bs.Opcoes("casa"),
                          cancelado=lambda: (vistas.append(1), len(vistas) > 2)[1])
    assert resultado.cancelada and resultado.paginas_buscadas == 2


def test_a_busca_por_glifo():
    p = _pagina("casa")
    p.boxes[1] = Box(p.boxes[1].gid, BoxEntry("a", 42, 20, 60, 50, 0.3, "manual"))
    indexada = bs.indexar_pagina(p, "pt", margens=())
    assert [g.gid for g in bs.buscar_glifos({0: indexada}, "a")] == [p.boxes[1].gid, p.boxes[3].gid]
    assert [g.gid for g in bs.buscar_glifos({0: indexada}, "a", fontes=["manual"])] == [p.boxes[1].gid]
    assert [g.gid for g in bs.buscar_glifos({0: indexada}, "", confianca_maxima=0.5)] == [p.boxes[1].gid]


def test_construir_sem_processos_pelos_arquivos(tmp_path):
    import json

    from abbychess.pagina_em_json import pagina_para_json

    arquivos = {}
    for i in range(3):
        p = _pagina(f"pagina {i}")
        p.indice = i
        caminho = tmp_path / f"p{i}.json"
        caminho.write_text(json.dumps(pagina_para_json(p)), encoding="utf-8")
        arquivos[i] = (str(caminho), 7)
    indice = bs.construir(arquivos, "pt", paralelo=False)
    assert sorted(indice) == [0, 1, 2] and indice[2].texto == "pagina 2" and indice[1].versao == 7


# ----------------------------------------------------------------------
# O controlador (o índice em segundo plano, a busca numa thread)
# ----------------------------------------------------------------------


def test_o_controlador_monta_o_indice_busca_e_refaz_a_pagina_editada(tmp_path):
    from abbychess.controladores import ControladorDaBusca
    from abbychess.projeto import ProjetoDeLivro
    from tests.ajudantes import ExecutorManual, _controlador  # noqa: E402,F401,F811
    from tests.ajudantes import pdf_sintetico  # noqa: E402,F401,F811

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Duas", pdf_sintetico(tmp_path))
    try:
        executor = ExecutorManual()
        ctl = _controlador(projeto, executor)
        ctl.leitura.reconhecer()
        executor.tudo()
        busca = ControladorDaBusca(ctl, paralelo=False)
        fins, falhas = [], []
        ctl.eventos.ligar("busca_terminou", fins.append)
        ctl.eventos.ligar("busca_falhou", falhas.append)
        busca.abrir()
        busca.buscar(bs.Opcoes("zzqq"))                  # pedida antes do índice: espera
        _ate_valer(lambda: busca.pronto.is_set() and fins)
        assert sorted(busca.indice) == projeto.resumo.paginas_lidas() and not fins[-1].ocorrencias
        texto, unidades = ss.texto_e_unidades(ctl.modelo)
        inicio, fim = ss.palavras_em(unidades, 0, 0)
        ctl.sessoes.confirmar_sessao(unidades[inicio:fim], "zzqq" + texto[inicio:fim])   # uma edição
        executor.tudo()
        busca.buscar(bs.Opcoes("zzqq"))
        _ate_valer(lambda: len(fins) == 2)
        [o] = fins[-1].ocorrencias
        assert o.pagina == ctl.indice and len(o.gids) == 4
        busca.buscar(bs.Opcoes("(zz", regex=True))
        assert falhas and "inválida" in falhas[-1]
    finally:
        projeto.fechar()


# ----------------------------------------------------------------------
# Os casos de borda das revisões do passo B
# ----------------------------------------------------------------------

@pytest.mark.parametrize("padrao, texto, esperado", [
    (r"\P", "abc dor", []),                               # com o Aa desligado (o padrão)
    (r"\C", "Seção B3", []),
    (r"\Px\C", "Bxc5 bxc5", ["Bxc5"]),
    (r"\C", "the5 a43 e4", ["e4"]),
    (r"\L", "the5 a43 exd5", ["exd5"]),
    (r"\V", "+= =+ e8=D", ["+=", "=+"]),
    (r"[^]\C]", "]", []),
    (r"^casa", "nada\ncasa", ["casa"]),                   # ^ em cada linha impressa
])
def test_as_classes_e_a_expansao_nos_casos_de_borda(padrao, texto, esperado):
    p = _pagina(*texto.split("\n"))
    indexada = bs.indexar_pagina(p, "pt", margens=())
    assert _achados(indexada, padrao, regex=True) == esperado


def test_a_propriedade_unicode_do_regex_fica_como_esta():
    assert bs.expandir_classes(r"\P{Lu}x\p{Ll}", "pt")[0] == r"\P{Lu}x\p{Ll}"


@pytest.mark.parametrize("classe, positivos, negativos", [
    (r"\C", ["e4", "h8"], ["E4", "i9"]), (r"\V", ["±", "!?", "+-"], ["a"])])
def test_ca_7_4_casa_e_valoracao_em_ingles(classe, positivos, negativos):
    for token in positivos:
        assert _achados(_indice(token, idioma="en"), rf"^{classe}$", regex=True, idioma="en")
    for token in negativos:
        assert not _achados(_indice(token, idioma="en"), rf"^{classe}$", regex=True, idioma="en")


def test_a_casa_depois_da_desambiguacao():
    indexada = _indice("Nbd7 Rae1 Cbd2 Tfe1 R1e2 exd5 the5 a43 i9")
    assert _achados(indexada, r"\C", regex=True) == ["d7", "e1", "d2", "e1", "e2", "d5"]


def test_figurina_igual_a_letra_so_na_peca_de_um_lance():
    indexada = _indice("Cada nada C1e2 ♘1e2 Rd1 Td1")
    assert _achados(indexada, "Cada", figurina_letra=True) == ["Cada"]
    assert _achados(indexada, "C1e2", figurina_letra=True) == ["C1e2", "♘1e2"]
    assert _achados(indexada, "Td1", figurina_letra=True) == ["Td1"]   # o R do pt é o rei


def test_figurina_igual_a_letra_pela_figurina_e_pela_letra_do_ingles():
    """A figurina digitada, branca ou preta, e a letra do inglês num livro em português
    acham as quatro formas da peça, e só dela (o B é o bispo)."""
    indexada = _indice("Cf3 ♘f3 Nf3 ♞f3 Bf3")
    for texto in ("♘f3", "♞f3", "Nf3"):
        assert _achados(indexada, texto, maiusculas=True, figurina_letra=True) == [
            "Cf3", "♘f3", "Nf3", "♞f3"], texto


def test_o_tempo_limite_conta_cada_casamento(monkeypatch):
    """Muitos casamentos rápidos numa página não estouram o tempo-limite (só o casamento
    lento conta), nem com outra thread disputando o GIL (o laço em Python entre os
    casamentos não entra na conta)."""
    indexada = _indice(" ".join(["a"] * 100))
    parar = threading.Event()

    def ocupar():
        while not parar.is_set():
            sum(range(2000))
    vizinha = threading.Thread(target=ocupar, daemon=True)
    vizinha.start()
    try:
        achadas = bs.buscar({0: indexada}, bs.Opcoes("a"), tempo_limite=0.05).ocorrencias
    finally:
        parar.set()
        vizinha.join()
    assert len(achadas) == 100


def _buscar_e_esperar(busca, eventos, texto, **opcoes):
    antes = len(eventos["fins"]) + len(eventos["falhas"])
    busca.buscar(bs.Opcoes(texto, **opcoes))
    _ate_valer(lambda: len(eventos["fins"]) + len(eventos["falhas"]) > antes)
    return eventos["fins"][-1] if eventos["fins"] else None


def test_a_pagina_relida_pelo_lote_entra_na_busca(livro_escrito):
    projeto, ctl, busca, escrever, eventos = livro_escrito
    assert not _buscar_e_esperar(busca, eventos, "novo").ocorrencias
    escrever(1, "texto novo")                            # como o lote grava a página
    busca.marcar_velha(1)                                # o evento pagina_do_lote
    [o] = _buscar_e_esperar(busca, eventos, "novo").ocorrencias
    assert o.pagina == 1


def test_a_busca_abandonada_devolve_as_relidas(livro_escrito, monkeypatch):
    projeto, ctl, busca, escrever, eventos = livro_escrito
    escrever(2, "fim novo")
    busca.marcar_velha(2)
    lido = threading.Event()
    soltar = threading.Event()
    original = projeto.ler_sem_migrar

    def devagar(i):                                      # a thread presa no meio da leitura
        lido.set()
        soltar.wait(5)
        return original(i)
    monkeypatch.setattr(projeto.paginas_em_memoria, "pagina", lambda i: None)
    monkeypatch.setattr(projeto, "ler_sem_migrar", devagar)
    busca.buscar(bs.Opcoes("novo"))
    assert lido.wait(5)
    busca.cancelar()                                     # o Esc no meio
    soltar.set()
    _ate_valer(lambda: 2 in busca._velhas)
    monkeypatch.setattr(projeto, "ler_sem_migrar", original)
    [o] = _buscar_e_esperar(busca, eventos, "novo").ocorrencias
    assert o.pagina == 2


def test_a_pagina_que_deixou_de_ser_reconhecida_sai_do_indice(livro_escrito, monkeypatch):
    projeto, ctl, busca, escrever, eventos = livro_escrito
    assert len(_buscar_e_esperar(busca, eventos, "casa").ocorrencias) == 2
    monkeypatch.setattr(projeto.resumo, "paginas_lidas", lambda: [0, 2])
    assert [o.pagina for o in _buscar_e_esperar(busca, eventos, "casa").ocorrencias] == [0]
    assert 1 not in busca.indice and busca.nao_reconhecidas() >= 1


def test_os_erros_nas_threads_nao_penduram_a_busca(livro_escrito, monkeypatch):
    projeto, ctl, busca, escrever, eventos = livro_escrito
    monkeypatch.setattr(bs, "buscar", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disco")))
    busca.buscar(bs.Opcoes("casa"))
    _ate_valer(lambda: eventos["falhas"])
    assert "A busca falhou" in eventos["falhas"][-1]
    monkeypatch.setattr(bs, "construir", lambda *a, **k: (_ for _ in ()).throw(OSError("quebrou")))
    busca.abrir()
    _ate_valer(busca.pronto.is_set)                        # pronto, com o índice parcial
    assert eventos["avisos"] and "ficaram fora" in eventos["avisos"][-1]


def test_trocar_de_projeto_durante_a_montagem_fica_com_o_novo(livro_escrito, monkeypatch):
    """A montagem do índice do projeto de antes termina depois da do novo: o índice que fica
    é o do novo, inteiro (nenhuma página fora da busca, e o "n" que só ele tem contado)."""
    projeto, ctl, busca, escrever, eventos = livro_escrito
    soltar, velhas = threading.Event(), []
    original = bs.construir

    def devagar(*a, **k):
        velhas.append(threading.current_thread())
        soltar.wait(5)
        return original(*a, **k)
    monkeypatch.setattr(bs, "construir", devagar)
    busca.abrir()                                        # a montagem velha, presa
    monkeypatch.setattr(bs, "construir", original)
    escrever(2, "nova")                                  # o projeto de agora é outro
    busca.abrir()                                        # a nova
    _ate_valer(busca.pronto.is_set)
    soltar.set()
    velhas[0].join(5)                                    # a velha termina, atrasada
    assert not velhas[0].is_alive()
    assert busca.nao_reconhecidas() == 0 and busca.contar_leitura("n") == 1


def test_uma_busca_velha_nao_desfaz_a_pagina_relida_por_uma_mais_nova(livro_escrito, monkeypatch):
    """A busca 1 termina depois da 2, que releu a página: o texto da 2 fica."""
    projeto, ctl, busca, escrever, eventos = livro_escrito
    busca.buscar(bs.Opcoes("casa"))
    _ate_valer(lambda: eventos["fins"])
    presa, soltar = [], threading.Event()
    original = bs.indexar_pagina

    def devagar(pagina, *a, **k):
        indexada = original(pagina, *a, **k)
        if indexada.texto == "relida":                   # a busca 1 leu a página relida
            presa.append(threading.current_thread())
            soltar.wait(5)
        return indexada
    monkeypatch.setattr(bs, "indexar_pagina", devagar)
    escrever(1, "relida")
    busca.marcar_velha(1)
    busca.buscar(bs.Opcoes("relida"))                    # a busca 1, presa depois de ler
    _ate_valer(lambda: presa)
    escrever(1, "outra")
    busca.marcar_velha(1)
    busca.buscar(bs.Opcoes("outra"))                     # a busca 2, mais nova, termina antes
    _ate_valer(lambda: len(eventos["fins"]) == 2)
    soltar.set()
    presa[0].join(5)                                     # o fim atrasado da busca 1
    assert not presa[0].is_alive()
    assert [o.pagina for o in eventos["fins"][-1].ocorrencias] == [1]
    assert busca.contar_leitura("u") == 1                # o índice de agora: "outra", e não
                                                         # o "relida" da busca 1


def test_a_busca_por_glifo_roda_fora_da_interface(livro_escrito):
    projeto, ctl, busca, escrever, eventos = livro_escrito
    busca.abrir()
    _ate_valer(busca.pronto.is_set)
    fila, achados = [], []
    ctl.executar.na_interface = fila.append
    escrever(2, "aaa")
    busca.marcar_velha(2)
    busca.glifos("a", ao_terminar=achados.append)
    assert not achados                                   # volta na hora, sem ler a página
    _ate_valer(lambda: fila)
    fila.pop(0)()
    assert sum(g.pagina == 2 for g in achados[0]) == 3 and busca.indice[2].texto == "aaa"


def test_os_resultados_voltam_pela_fila_da_interface(livro_escrito):
    projeto, ctl, busca, escrever, eventos = livro_escrito
    fila = []
    ctl.executar.na_interface = fila.append              # como o executor da janela
    busca.buscar(bs.Opcoes("casa"))
    _ate_valer(lambda: fila)
    assert not eventos["fins"]                           # nada chega fora da interface
    fila.pop(0)()
    assert len(eventos["fins"][-1].ocorrencias) == 2


@pytest.mark.processo
def test_trocar_de_projeto_com_o_pool_nao_esvazia_o_indice_novo(tmp_path):
    """A montagem velha, cancelada, não fecha os processos que a nova está usando."""
    import json
    import time
    from types import SimpleNamespace

    from abbychess.controlador import Eventos
    from abbychess.controladores import ControladorDaBusca
    from abbychess.pagina_em_json import pagina_para_json

    def projeto(nome):
        pasta = tmp_path / nome
        pasta.mkdir()
        for i in range(120):
            p = _pagina(f"{nome} pagina {i} com Cf3 e casa")
            p.indice = i
            (pasta / f"p{i}.json").write_text(json.dumps(pagina_para_json(p)), encoding="utf-8")
        # A sequência, desde o passo L: o índice lê dela a geometria de cada página.
        from abbychess.sequencia import Sequencia

        return SimpleNamespace(dados=SimpleNamespace(idioma="pt"),
                               resumo=SimpleNamespace(paginas_lidas=lambda: range(120)),
                               ordem=SimpleNamespace(pid_em=lambda i: i),
                               paginas_em_memoria=SimpleNamespace(pagina=lambda i: None),
                               arquivo_da_pagina=lambda i: pasta / f"p{i}.json",
                               sequencia=Sequencia.do_livro(range(120)))
    ctl = SimpleNamespace(projeto=projeto("a"), eventos=Eventos(), executar=SimpleNamespace(),
                          historico=SimpleNamespace(versao=lambda pid: 0))
    busca = ControladorDaBusca(ctl, paralelo=True)
    avisos = []
    ctl.eventos.ligar("aviso", lambda *a: avisos.append(a))
    busca.pool.obter()                                  # aquecido, como no programa
    busca.pool.devolver()
    busca.abrir()
    time.sleep(0.3)
    ctl.projeto = projeto("b")
    busca.abrir()
    try:
        _ate_valer(busca.pronto.is_set, 60)
        assert len(busca.indice) == 120 and not avisos
        assert busca.indice[0].texto.startswith("b pagina")
    finally:
        busca.pool.liberar()


@pytest.mark.processo
def test_o_indice_no_pool_de_processos_e_o_mesmo_que_em_serie(tmp_path):
    """O índice montado nos processos (o padrão do programa) é igual ao montado na thread."""
    import json

    from abbychess.pagina_em_json import pagina_para_json

    fontes = {}
    for i in range(10):
        p = _pagina(f"pagina {i} com Cf3 e casa")
        p.indice = i
        caminho = tmp_path / f"p{i}.json"
        caminho.write_text(json.dumps(pagina_para_json(p)), encoding="utf-8")
        fontes[i] = (str(caminho), i)
    na_memoria = _pagina("na memória")                  # a página como objeto, também
    na_memoria.indice = 10
    fontes[10] = (na_memoria, 3)
    pool = bs.PoolDoIndice()
    try:
        paralelo = bs.construir(fontes, "pt", paralelo=True, pool=pool)
    finally:
        pool.liberar()
    serie = bs.construir(fontes, "pt", paralelo=False)
    assert paralelo == serie and len(serie) == 11


# ----------------------------------------------------------------------
# As regras que a mutação achou sem teste (Q9, CA-Q-M1)
# ----------------------------------------------------------------------

def test_os_fens_da_pagina_sem_texto_ficam_um_por_linha():
    """A página só de diagramas: o primeiro FEN abre o texto, sem quebra antes dele."""
    p = Pagina(pid=1, indice=0, estado="reconhecida")
    p.diagramas = [_lido(caixa=(0, 0, 400, 400)), _lido(caixa=(0, 500, 400, 900))]
    indexada = bs.indexar_pagina(p, "pt", margens=())
    fen = p.diagramas[0].fen
    assert indexada.texto == f"{fen}\n{fen}"


def _nas_alturas(*linhas) -> Pagina:
    """Uma linha de glifos de 30 px de altura em cada topo, (texto, topo), com 14 px a mais
    entre as palavras (com os 30 px do `_pagina`, o core parte as linhas em colunas)."""
    boxes = []
    for texto, topo in linhas:
        x = 20
        for palavra in texto.split(" "):
            for letra in palavra:
                boxes.append(Box(gid_de(1, len(boxes)),
                                 BoxEntry(letra, x, topo, x + 18, topo + 30, 0.9, "net")))
                x += 22
            x += 14
    return Pagina(pid=1, indice=0, boxes=boxes, estado="reconhecida", proximo_n=len(boxes))


def _das_margens(*linhas) -> list:
    """As palavras que o índice, sem as margens de quem chama, etiqueta como cabeçalho."""
    indexada = bs.indexar_pagina(_nas_alturas(*linhas), "pt")
    return [t.group(0) for t in re.finditer(r"\S+", indexada.texto)
            if indexada.etiqueta(t.start()) == bs.CABECALHO]


#: Quatro linhas de texto, a 10 px umas das outras.
_CORPO = (("o texto da página", 80), ("segue aqui", 120), ("e mais", 160), ("acaba", 200))


def test_o_cabecalho_e_o_rodape_pelas_linhas_montadas():
    """A primeira e a última linha, curtas, com um número e a 30 px do texto (o vão mediano é
    10), são as margens; o número da página sozinho, de um algarismo, também."""
    assert _das_margens(("12 Capítulo", 20), *_CORPO, ("7", 260)) == ["12", "Capítulo", "7"]


def test_o_lance_da_primeira_e_da_ultima_linha_colado_ao_texto_nao_e_margem():
    assert _das_margens(("1.e4 e5", 40), *_CORPO, ("2.Cf3 Cc6", 240)) == []


def test_a_margem_e_curta_tem_numero_e_passa_de_1_5_vez_o_vao_mediano():
    longa = "12 " + "x" * 57                                    # 60 caracteres
    assert _das_margens((longa, 20), *_CORPO) == longa.split()
    assert _das_margens((longa + "x", 20), *_CORPO) == []        # 61
    assert _das_margens(("Capítulo", 20), *_CORPO) == []         # sem número
    assert _das_margens(("12 Capítulo", 35), *_CORPO) == []      # 15 px: 1,5 vez, não mais
    # O vão mediano é o do meio: entre os de 10 e os de 30 px, 30 (e 40 px não bastam).
    assert _das_margens(("12 Capítulo", 20), ("um", 90), ("dois", 130), ("tres", 170),
                        ("quatro", 230), ("cinco", 290), ("seis", 330)) == []
    # As linhas coladas (o vão mediano 0): 2 px já separam o cabeçalho.
    assert _das_margens(("12 Capítulo", 20), ("um", 52), ("dois", 82), ("tres", 112),
                        ("quatro", 142)) == ["12", "Capítulo"]


@pytest.mark.parametrize("nucleos, processos", [(None, 1), (2, 1), (4, 2), (8, 6), (16, 6)])
def test_o_indice_usa_os_nucleos_menos_dois_de_1_a_6_processos(monkeypatch, nucleos, processos):
    monkeypatch.setattr(bs.os, "cpu_count", lambda: nucleos)
    assert bs.processos_para_indexar() == processos


def test_a_barra_no_fim_do_padrao_e_invalida():
    with pytest.raises(bs.PadraoInvalido):
        bs.buscar({0: _indice("casa")}, bs.Opcoes("casa\\", regex=True))


def test_os_colchetes_da_regex():
    """A classe de xadrez depois de outra letra nos colchetes, o "[" depois do "^" e o "]"
    logo depois do "[" (os dois literais)."""
    assert _achados(_indice("x C a"), r"[x\P]", regex=True, maiusculas=True) == ["x", "C"]
    assert _achados(_indice("a[b"), "[^a]", regex=True) == ["[", "b"]
    assert _achados(_indice("a]"), "[]a]", regex=True) == ["a", "]"]


def test_o_escopo_vale_so_o_que_e_dele():
    """A barra guarda a seleção e o intervalo de antes quando o escopo muda."""
    from dataclasses import replace

    lidas = [0, 1, 2, 3]
    selecao = bs.Opcoes("x", escopo=bs.SELECAO, selecao=(3, 7, 9), pagina_atual=1,
                        intervalo=(1, 2))
    assert bs.paginas_do_escopo(lidas, selecao) == [3]
    assert bs.paginas_do_escopo(lidas, replace(selecao, escopo=bs.PAGINA)) == [1]
    assert bs.paginas_do_escopo(lidas, replace(selecao, escopo=bs.LIVRO)) == lidas


def test_o_padrao_lento_diz_a_pagina_que_o_usuario_ve():
    longo = _indice("a" * 400 + "!", indice=2)
    with pytest.raises(bs.PadraoLento, match=r"\(página 3\)"):
        bs.buscar({2: longo}, bs.Opcoes(r"(\w+)+$", regex=True), tempo_limite=0.02)


def test_o_casamento_vazio_anda_uma_posicao_e_nao_conta():
    assert _achados(_indice("axxb"), "x*", regex=True) == ["xx"]


def test_a_selecao_cujo_ultimo_glifo_saiu_da_pagina_nao_acha_nada():
    indexada = _indice("casa velha")
    selecao = (0, indexada.gids[0], gid_de(1, 999))
    assert _achados(indexada, "casa", escopo=bs.SELECAO, selecao=selecao) == []


def test_a_ocorrencia_na_segunda_linha_e_entre_palavras():
    """A ocorrência que começa no espaço tem a etiqueta da palavra, os gids só dos glifos, e
    a coluna e a linha da segunda linha."""
    indexada = _indice("joga Cf3")
    [o] = bs.buscar({0: indexada}, bs.Opcoes(" Cf3", onde=frozenset({bs.NOTACAO}))).ocorrencias
    assert o.etiqueta == bs.NOTACAO
    [o] = bs.buscar({0: indexada}, bs.Opcoes("a C")).ocorrencias
    assert o.gids == (indexada.gids[3], indexada.gids[5])
    indexada = bs.indexar_pagina(_nas_alturas(("uma casa", 20), ("mais nova", 60)), "pt",
                                 margens=())
    assert indexada.texto == "uma casa\nmais nova"
    [o] = bs.buscar({0: indexada}, bs.Opcoes("nova")).ocorrencias
    assert (o.linha, o.trecho, o.trecho[o.coluna:o.coluna + 4]) == (2, "mais nova", "nova")


def test_a_busca_que_terminou_nao_foi_cancelada():
    assert not bs.buscar({0: _indice("casa")}, bs.Opcoes("casa")).cancelada
    assert not bs.buscar({0: _indice("casa")}, bs.Opcoes("")).cancelada


def test_a_busca_por_glifo_pelo_grupo_da_fonte_e_nas_pontas_da_confianca():
    fontes = ("manual", "livro", "", "none", "learner", "base", "net")
    assert [bs.grupo_da_fonte(f) for f in fontes] == [bs.MANUAL, bs.LIVRO_, bs.SEM_LEITURA,
                                                     bs.SEM_LEITURA, bs.BASE, bs.BASE, bs.REDE]
    p = _pagina("casa")
    p.boxes[1] = Box(p.boxes[1].gid, BoxEntry("a", 42, 20, 60, 50, 0.3, "manual"))
    indexada = bs.indexar_pagina(p, "pt", margens=())
    da_rede = bs.buscar_glifos({0: indexada}, "", fontes=[bs.REDE])
    assert [g.gid for g in da_rede] == [p.boxes[k].gid for k in (0, 2, 3)]
    assert [g.gid for g in bs.buscar_glifos({0: indexada}, "", confianca_minima=0.3,
                                            confianca_maxima=0.3)] == [p.boxes[1].gid]


@pytest.mark.parametrize("nucleos, processos", [(12, 6), (8, 6), (4, 2), (3, 1), (None, 1)])
def test_o_indice_usa_os_nucleos_menos_dois_de_1_a_6(monkeypatch, nucleos, processos):
    """A janela e o servidor de leitura ficam com dois núcleos; mais de 6 processos não ganha."""
    monkeypatch.setattr(bs.os, "cpu_count", lambda: nucleos)
    assert bs.processos_para_indexar() == processos


@pytest.mark.processo
def test_o_pool_do_indice_fica_aberto_enquanto_ha_uso_e_fecha_com_o_ultimo():
    """`obter` e `devolver` contam os usos: os processos são os mesmos enquanto há um uso, o
    último fecha (o próximo `obter` abre outros), devolver a mais não deixa a conta negativa, e
    `liberar` fecha na hora, com uso ou sem."""
    pool = bs.PoolDoIndice()
    try:
        primeiro = pool.obter()
        assert primeiro is not None and pool.obter() is primeiro     # dois usos, um pool
        pool.devolver()
        assert pool.obter() is primeiro                               # ainda há uso: o mesmo
        pool.devolver()
        pool.devolver()                                               # o último fecha
        segundo = pool.obter()
        assert segundo is not None and segundo is not primeiro
        pool.liberar()                                                # fecha com o uso aberto
        terceiro = pool.obter()
        assert terceiro is not segundo
        for _ in range(4):                                            # devolver a mais: zero
            pool.devolver()
        quarto = pool.obter()
        assert quarto is not terceiro
        pool.devolver()                                               # um uso, devolvido: fecha
        assert pool.obter() is not quarto
    finally:
        pool.liberar()
