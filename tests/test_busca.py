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
from abbychess.modelo import Box

from tests.test_sessao import _pagina


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

    from abbychess.projeto import _pagina_para_json

    arquivos = {}
    for i in range(3):
        p = _pagina(f"pagina {i}")
        p.indice = i
        caminho = tmp_path / f"p{i}.json"
        caminho.write_text(json.dumps(_pagina_para_json(p)), encoding="utf-8")
        arquivos[i] = (str(caminho), 7)
    indice = bs.construir(arquivos, "pt", paralelo=False)
    assert sorted(indice) == [0, 1, 2] and indice[2].texto == "pagina 2" and indice[1].versao == 7


# ----------------------------------------------------------------------
# O controlador (o índice em segundo plano, a busca numa thread)
# ----------------------------------------------------------------------

def _esperar(condicao, limite=20.0):
    import time

    fim = time.monotonic() + limite
    while not condicao() and time.monotonic() < fim:
        time.sleep(0.01)
    assert condicao()


def test_o_controlador_monta_o_indice_busca_e_refaz_a_pagina_editada(tmp_path):
    from abbychess.controladores import ControladorDaBusca
    from abbychess.projeto import ProjetoDeLivro
    from tests.test_controlador import ExecutorManual, _controlador
    from tests.test_livro import pdf_sintetico

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Duas", pdf_sintetico(tmp_path))
    try:
        executor = ExecutorManual()
        ctl = _controlador(projeto, executor)
        ctl.reconhecer()
        executor.tudo()
        busca = ControladorDaBusca(ctl, paralelo=False)
        fins, falhas = [], []
        ctl.eventos.ligar("busca_terminou", fins.append)
        ctl.eventos.ligar("busca_falhou", falhas.append)
        busca.abrir()
        busca.buscar(bs.Opcoes("zzqq"))                  # pedida antes do índice: espera
        _esperar(lambda: busca.pronto.is_set() and fins)
        assert sorted(busca.indice) == projeto.paginas_lidas() and not fins[-1].ocorrencias
        texto, unidades = ss.texto_e_unidades(ctl.modelo)
        inicio, fim = ss.palavras_em(unidades, 0, 0)
        ctl.confirmar_sessao(unidades[inicio:fim], "zzqq" + texto[inicio:fim])   # uma edição
        executor.tudo()
        busca.buscar(bs.Opcoes("zzqq"))
        _esperar(lambda: len(fins) == 2)
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


@pytest.fixture
def livro_escrito(tmp_path):
    """Um projeto de 3 páginas com o texto escrito à mão (sem reconhecer), o controlador da
    página e o da busca (sem processos)."""
    from abbychess.controladores import ControladorDaBusca
    from abbychess.modelo import gid_de
    from abbychess.projeto import ProjetoDeLivro
    from tests.test_controlador import ExecutorManual, _controlador
    from tests.test_livro import pdf_sintetico

    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Três", pdf_sintetico(tmp_path))
    executor = ExecutorManual()
    ctl = _controlador(projeto, executor)

    def escrever(indice, texto):
        pagina = projeto.pagina_para_editar(indice)
        modelo = _pagina(texto)
        pagina.boxes = [Box(gid_de(pagina.pid, n), b.entry) for n, b in enumerate(modelo.boxes)]
        pagina.proximo_n = len(pagina.boxes)
        pagina.estado = "reconhecida"
        projeto.salvar_modelo(pagina)
        return pagina

    for i, texto in enumerate(("casa velha", "outra casa", "fim")):
        escrever(i, texto)
    busca = ControladorDaBusca(ctl, paralelo=False)
    eventos = {"fins": [], "falhas": [], "avisos": []}
    ctl.eventos.ligar("busca_terminou", eventos["fins"].append)
    ctl.eventos.ligar("busca_falhou", eventos["falhas"].append)
    ctl.eventos.ligar("aviso", lambda titulo, texto: eventos["avisos"].append(texto))
    busca.abrir()
    _esperar(busca.pronto.is_set)
    yield projeto, ctl, busca, escrever, eventos
    projeto.fechar()


def _buscar_e_esperar(busca, eventos, texto, **opcoes):
    antes = len(eventos["fins"]) + len(eventos["falhas"])
    busca.buscar(bs.Opcoes(texto, **opcoes))
    _esperar(lambda: len(eventos["fins"]) + len(eventos["falhas"]) > antes)
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
    monkeypatch.setattr(projeto, "modelo_em_memoria", lambda i: None)
    monkeypatch.setattr(projeto, "ler_sem_migrar", devagar)
    busca.buscar(bs.Opcoes("novo"))
    assert lido.wait(5)
    busca.cancelar()                                     # o Esc no meio
    soltar.set()
    _esperar(lambda: 2 in busca._velhas)
    monkeypatch.setattr(projeto, "ler_sem_migrar", original)
    [o] = _buscar_e_esperar(busca, eventos, "novo").ocorrencias
    assert o.pagina == 2


def test_a_pagina_que_deixou_de_ser_reconhecida_sai_do_indice(livro_escrito, monkeypatch):
    projeto, ctl, busca, escrever, eventos = livro_escrito
    assert len(_buscar_e_esperar(busca, eventos, "casa").ocorrencias) == 2
    monkeypatch.setattr(projeto, "paginas_lidas", lambda: [0, 2])
    assert [o.pagina for o in _buscar_e_esperar(busca, eventos, "casa").ocorrencias] == [0]
    assert 1 not in busca.indice and busca.nao_reconhecidas() >= 1


def test_os_erros_nas_threads_nao_penduram_a_busca(livro_escrito, monkeypatch):
    projeto, ctl, busca, escrever, eventos = livro_escrito
    monkeypatch.setattr(bs, "buscar", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disco")))
    busca.buscar(bs.Opcoes("casa"))
    _esperar(lambda: eventos["falhas"])
    assert "A busca falhou" in eventos["falhas"][-1]
    monkeypatch.setattr(bs, "construir", lambda *a, **k: (_ for _ in ()).throw(OSError("quebrou")))
    busca.abrir()
    _esperar(busca.pronto.is_set)                        # pronto, com o índice parcial
    assert eventos["avisos"] and "ficaram fora" in eventos["avisos"][-1]


def test_trocar_de_projeto_durante_a_montagem_fica_com_o_novo(livro_escrito, monkeypatch):
    projeto, ctl, busca, escrever, eventos = livro_escrito
    soltar = threading.Event()
    original = bs.construir

    def devagar(*a, **k):
        soltar.wait(5)
        return original(*a, **k)
    monkeypatch.setattr(bs, "construir", devagar)
    busca.abrir()                                        # a montagem velha, presa
    geracao = busca._geracao
    monkeypatch.setattr(bs, "construir", original)
    busca.abrir()                                        # a nova
    _esperar(busca.pronto.is_set)
    soltar.set()
    assert busca._geracao == geracao + 1 and sorted(busca.indice) == [0, 1, 2]


def test_uma_busca_velha_nao_desfaz_a_pagina_relida_por_uma_mais_nova(livro_escrito):
    """A busca 1 termina depois da 2, que releu a página: o texto da 2 fica."""
    projeto, ctl, busca, escrever, eventos = livro_escrito
    busca.buscar(bs.Opcoes("casa"))
    _esperar(lambda: eventos["fins"])
    escrever(1, "relida")
    busca.marcar_velha(1)
    leitura_velha, refazer, carregar, _v = busca._paginas_a_refazer()   # a busca 1 a lê antes
    velha = busca._refazer(refazer, carregar, lambda: True)
    assert velha[1].texto == "relida"
    escrever(1, "outra")
    busca.marcar_velha(1)
    busca.buscar(bs.Opcoes("outra"))                     # a busca 2, mais nova, termina antes
    _esperar(lambda: len(eventos["fins"]) == 2)
    busca._guardar(leitura_velha, velha)                 # o fim atrasado da busca 1
    busca.buscar(bs.Opcoes("outra"))
    _esperar(lambda: len(eventos["fins"]) == 3)
    assert len(eventos["fins"][-1].ocorrencias) == 1


def test_a_busca_por_glifo_roda_fora_da_interface(livro_escrito):
    projeto, ctl, busca, escrever, eventos = livro_escrito
    busca.abrir()
    _esperar(busca.pronto.is_set)
    fila, achados = [], []
    ctl.executar.na_interface = fila.append
    escrever(2, "aaa")
    busca.marcar_velha(2)
    busca.glifos("a", ao_terminar=achados.append)
    assert not achados                                   # volta na hora, sem ler a página
    _esperar(lambda: fila)
    fila.pop(0)()
    assert sum(g.pagina == 2 for g in achados[0]) == 3 and busca.indice[2].texto == "aaa"


def test_os_resultados_voltam_pela_fila_da_interface(livro_escrito):
    projeto, ctl, busca, escrever, eventos = livro_escrito
    fila = []
    ctl.executar.na_interface = fila.append              # como o executor da janela
    busca.buscar(bs.Opcoes("casa"))
    _esperar(lambda: fila)
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
    from abbychess.projeto import _pagina_para_json

    def projeto(nome):
        pasta = tmp_path / nome
        pasta.mkdir()
        for i in range(120):
            p = _pagina(f"{nome} pagina {i} com Cf3 e casa")
            p.indice = i
            (pasta / f"p{i}.json").write_text(json.dumps(_pagina_para_json(p)), encoding="utf-8")
        return SimpleNamespace(dados=SimpleNamespace(idioma="pt"), paginas_lidas=lambda: range(120),
                               pid_da_pagina=lambda i: i, modelo_em_memoria=lambda i: None,
                               arquivo_da_pagina=lambda i: pasta / f"p{i}.json")
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
        _esperar(busca.pronto.is_set, 60)
        assert len(busca.indice) == 120 and not avisos
        assert busca.indice[0].texto.startswith("b pagina")
    finally:
        busca.pool.liberar()


@pytest.mark.processo
def test_o_indice_no_pool_de_processos_e_o_mesmo_que_em_serie(tmp_path):
    """O índice montado nos processos (o padrão do programa) é igual ao montado na thread."""
    import json

    from abbychess.projeto import _pagina_para_json

    fontes = {}
    for i in range(10):
        p = _pagina(f"pagina {i} com Cf3 e casa")
        p.indice = i
        caminho = tmp_path / f"p{i}.json"
        caminho.write_text(json.dumps(_pagina_para_json(p)), encoding="utf-8")
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
