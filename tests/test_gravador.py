"""O gravador assíncrono (SPEC §4.3; CA-4.2 e CA-4.4, partes do 2a).

Coalescência, a falha que deixa a página suja, fechar que grava antes de voltar, o resumo
do livro que já vê o que está para gravar e o `livro.json` igual ao recalculado. Os
cenários com processo morto estão em `test_gravador_processo.py` (camada `processo`).
"""

from __future__ import annotations

import json
import random
import threading
import time

import pytest
from core.box_model import BoxEntry

from abbychess import edicao as ed
from abbychess import gravacao as gv
from abbychess.gravador import Gravador
from abbychess.modelo import Box, RECONHECIDA, gid_de
from abbychess.projeto import ARQUIVO_DO_LIVRO, PAGINAS_EM_MEMORIA, ProjetoDeLivro

from tests.test_treino_por_livro import _pagina_sintetica


class _Disco:
    """Um `gravar` falso que conta e pode falhar."""

    def __init__(self):
        self.gravados = []
        self.falhar = 0          # quantas vezes ainda falha (-1: sempre)
        self.trava = threading.Lock()

    def __call__(self, instantaneo):
        with self.trava:
            if self.falhar:
                self.falhar -= 1 if self.falhar > 0 else 0
                raise PermissionError("disco ocupado")
            self.gravados.append(instantaneo)


def test_cem_mudancas_em_400_ms_sao_uma_gravacao():
    disco = _Disco()
    gravador = Gravador(disco)
    try:
        inicio = time.monotonic()
        for k in range(100):                     # uma a cada 4 ms (o sleep do Windows é de
            while time.monotonic() < inicio + k * 0.004:   # ~15 ms: espera ativa)
                pass
            gravador.agendar(1, k)
        assert time.monotonic() - inicio < gravador.atraso   # tudo antes do prazo
        assert gravador.descarregar(5)
        assert disco.gravados == [99] and gravador.gravacoes == 1
    finally:
        gravador.fechar()


def test_paginas_diferentes_gravam_cada_uma_o_ultimo_instantaneo():
    disco = _Disco()
    gravador = Gravador(disco, atraso=0.05)
    try:
        for k in range(10):
            gravador.agendar(k % 3, (k % 3, k))
        assert gravador.descarregar(5)
        assert sorted(disco.gravados) == [(0, 9), (1, 7), (2, 8)]
        assert gravador.sujas == set()
    finally:
        gravador.fechar()


def test_sem_descarregar_grava_sozinho_depois_do_atraso():
    disco = _Disco()
    gravador = Gravador(disco, atraso=0.05)
    try:
        gravador.agendar(1, "a")
        fim = time.monotonic() + 3
        while not disco.gravados and time.monotonic() < fim:
            time.sleep(0.01)
        assert disco.gravados == ["a"]
    finally:
        gravador.fechar()


def test_falha_permanente_avisa_uma_vez_e_a_pagina_continua_suja():
    disco = _Disco()
    disco.falhar = -1
    avisos = []
    gravador = Gravador(disco, atraso=0.02, ao_falhar=lambda pid, erro: avisos.append((pid, erro)))
    try:
        gravador.agendar(7, "v1")
        assert not gravador.descarregar(5)
        time.sleep(0.2)                          # tenta de novo, com espera crescente
        assert gravador.sujas == {7} and gravador.falhando == {7}
        assert len(avisos) == 1 and isinstance(avisos[0][1], PermissionError)
        disco.falhar = 0                         # o disco voltou
        gravador.agendar(7, "v2")                # um instantâneo novo tenta na hora
        assert gravador.descarregar(5)
        assert disco.gravados == ["v2"] and gravador.sujas == set()
    finally:
        gravador.fechar()


def test_tres_falhas_e_depois_sucesso_grava_o_mesmo_instantaneo():
    disco = _Disco()
    disco.falhar = 3
    gravador = Gravador(disco, atraso=0.01)
    try:
        gravador.agendar(1, "unico")
        fim = time.monotonic() + 10
        while gravador.sujas and time.monotonic() < fim:
            gravador.descarregar(1)
        assert disco.gravados == ["unico"]
    finally:
        gravador.fechar()


def test_fechar_grava_antes_de_voltar_e_recusa_depois():
    disco = _Disco()
    gravador = Gravador(disco)                   # meio segundo de atraso
    gravador.agendar(1, "x")
    assert gravador.fechar()
    assert disco.gravados == ["x"]
    with pytest.raises(RuntimeError):
        gravador.agendar(1, "y")


# ----------------------------------------------------------------------
# Com o projeto
# ----------------------------------------------------------------------

@pytest.fixture
def projeto(tmp_path):
    fonte = _pagina_sintetica(tmp_path / "pagina.png")
    p = ProjetoDeLivro.criar(tmp_path / "livros", "Gravador", fonte)
    yield p
    p.fechar()


def _pagina(projeto, indice, n=5):
    pagina = projeto.pagina_para_editar(indice)
    pagina.boxes = [Box(pagina.alocar(), BoxEntry("a", 10 * k, 0, 10 * k + 8, 9, 0.9, "rede"))
                    for k in range(n)]
    pagina.estado = RECONHECIDA
    return pagina


def test_agendar_nao_grava_na_hora_e_o_resumo_ja_ve(projeto):
    pagina = _pagina(projeto, 0)
    assert projeto.agendar(pagina)
    assert not (projeto.pasta / "paginas" / f"p{pagina.pid}.json").exists()
    assert projeto.paginas_lidas() == [0]        # o resumo não espera o disco
    assert projeto.descarregar(5)
    gravado = json.loads((projeto.pasta / "paginas" / f"p{pagina.pid}.json").read_text("utf-8"))
    assert len(gravado["boxes"]) == 5
    assert projeto.paginas_lidas() == [0]


def test_fechar_com_a_pagina_suja_grava_antes_de_voltar(projeto):
    pagina = _pagina(projeto, 0)
    projeto.agendar(pagina)
    ed.corrigir(pagina, pagina.boxes[0].gid, "z")
    projeto.agendar(pagina)
    assert projeto.fechar()
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    try:
        assert reaberto.carregar_pagina(0)[0].char == "z"
    finally:
        reaberto.fechar()


def test_falha_de_gravacao_avisa_pelo_projeto_e_a_pagina_fica_suja(projeto, monkeypatch):
    avisos = []
    projeto.ao_falhar_gravacao = lambda indice, erro: avisos.append((indice, str(erro)))
    pagina = _pagina(projeto, 3)

    def falhar(*_a, **_k):
        raise PermissionError("antivírus")

    monkeypatch.setattr(gv, "gravar_json", falhar)
    projeto.agendar(pagina)
    assert not projeto.descarregar(5)
    assert avisos == [(3, "antivírus")] and pagina.pid in projeto.sujas
    monkeypatch.undo()
    projeto.agendar(pagina)
    assert projeto.descarregar(5) and not projeto.sujas


def test_so_leitura_recusa_e_nada_e_gravado(projeto, tmp_path):
    pagina = _pagina(projeto, 0)
    projeto.agendar(pagina)
    projeto.fechar()
    arquivo = projeto.pasta / "projeto.json"
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    dados["versao"] = 99
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    so_leitura = ProjetoDeLivro.abrir(projeto.pasta)
    try:
        modelo = so_leitura.carregar_modelo(0)
        antes = (projeto.pasta / "paginas" / f"p{modelo.pid}.json").read_bytes()
        ed.corrigir(modelo, modelo.boxes[0].gid, "z")
        assert not so_leitura.agendar(modelo)
        assert so_leitura.descarregar(1)
        assert (projeto.pasta / "paginas" / f"p{modelo.pid}.json").read_bytes() == antes
    finally:
        so_leitura.fechar()


def test_pagina_com_gravacao_pendente_nao_sai_da_memoria(projeto, monkeypatch):
    bloqueio = threading.Event()
    original = projeto._gravar_instantaneo
    monkeypatch.setattr(projeto.gravador, "_gravar",
                        lambda inst: (bloqueio.wait(10), original(inst)))
    suja = _pagina(projeto, 0)
    projeto.agendar(suja)
    for k in range(1, PAGINAS_EM_MEMORIA + 4):   # enche o cache com outras
        _pagina(projeto, k)
    assert projeto.carregar_modelo(0) is suja
    bloqueio.set()
    assert projeto.descarregar(10)


@pytest.mark.parametrize("semente", range(4))
def test_livro_json_igual_ao_recalculado_depois_de_gravacoes_assincronas(projeto, semente):
    sorteio = random.Random(semente)
    paginas = [_pagina(projeto, k, n=sorteio.randint(1, 8)) for k in range(5)]
    for _ in range(40):
        pagina = sorteio.choice(paginas)
        acao = sorteio.random()
        if acao < 0.5 and pagina.boxes:
            ed.corrigir(pagina, sorteio.choice(pagina.boxes).gid, sorteio.choice("ab"))
        elif acao < 0.8 and len(pagina.boxes) > 1:
            ed.descartar(pagina, sorteio.choice(pagina.boxes).gid)
        else:
            pagina.boxes = pagina.boxes + [Box(pagina.alocar(), BoxEntry("", 1, 50, 9, 59))]
        projeto.agendar(pagina)
        if sorteio.random() < 0.2:
            projeto.descarregar(5)
    assert projeto.descarregar(5)
    gravado = json.loads((projeto.pasta / ARQUIVO_DO_LIVRO).read_text(encoding="utf-8"))
    assert gravado == projeto.recalcular_livro()


def test_instantaneo_e_imutavel_frente_as_edicoes(projeto):
    pagina = _pagina(projeto, 0)
    foto = pagina.instantaneo()
    ed.descartar(pagina, pagina.boxes[0].gid)
    ed.corrigir(pagina, pagina.boxes[0].gid, "q")
    assert len(foto.boxes) == 5 and foto.boxes[1].entry.char == "a"
    assert gid_de(pagina.pid, 0) == foto.boxes[0].gid


def test_a_interface_nao_espera_o_disco_do_gravador(projeto, monkeypatch):
    """Com o gravador preso dentro do `fsync` do livro.json (segurando a trava do livro), as
    chamadas da interface (entregar, ler a página do cache, o resumo) voltam na hora."""
    original = gv.gravar_json
    preso, solto = threading.Event(), threading.Event()

    def gravar(caminho, dados):
        if caminho.name == ARQUIVO_DO_LIVRO and threading.current_thread().name == "gravador":
            preso.set()
            solto.wait(10)
        original(caminho, dados)

    pagina = _pagina(projeto, 0)
    outra = _pagina(projeto, 1)
    projeto.descarregar(5)
    monkeypatch.setattr(gv, "gravar_json", gravar)
    projeto.agendar(pagina)
    projeto.gravador.descarregar(0)              # começa já
    assert preso.wait(5)
    try:
        inicio = time.monotonic()
        ed.corrigir(outra, outra.boxes[0].gid, "z")
        projeto.agendar(outra)
        assert projeto.carregar_modelo(1) is outra
        assert 1 in projeto.resumo_do_livro()
        assert time.monotonic() - inicio < 0.5
    finally:
        solto.set()
    assert projeto.descarregar(5)


def test_aviso_que_falha_nao_para_o_gravador():
    disco = _Disco()
    gravador = Gravador(disco, atraso=0.01, ao_gravar=lambda pid: 1 / 0)
    try:
        gravador.agendar(1, "a")
        assert gravador.descarregar(5)
        gravador.agendar(1, "b")                 # a thread continua viva
        assert gravador.descarregar(5)
        assert disco.gravados == ["a", "b"]
    finally:
        gravador.fechar()


def test_pagina_falhando_nao_tenta_a_cada_edicao():
    disco = _Disco()
    disco.falhar = -1
    tentativas = []
    original = disco.__call__

    def contar(instantaneo):
        tentativas.append(instantaneo)
        original(instantaneo)

    gravador = Gravador(contar, atraso=0.1)
    try:
        gravador.agendar(1, 0)
        gravador.descarregar(2)
        inicio = time.monotonic()
        k = 0
        while time.monotonic() - inicio < 0.3:   # muitas edições seguidas
            k += 1
            gravador.agendar(1, k)
        assert k > 100 and len(tentativas) <= 5  # uma tentativa por `atraso`, não por edição
    finally:
        disco.falhar = 0
        gravador.fechar(5)


def test_salvar_pagina_nao_muda_a_pagina_que_a_interface_mostra(projeto):
    from tests.test_treino_por_livro import _pagina_sintetica  # noqa: F401 (a fonte já existe)

    mostrada = _pagina(projeto, 0)
    projeto.agendar(mostrada)
    projeto.descarregar(5)
    antes = list(mostrada.boxes)
    projeto.salvar_pagina(0, [BoxEntry("q", 0, 0, 5, 5, 1.0, "manual")], reconheceu=True)
    assert mostrada.boxes == antes                     # a da interface não mudou
    nova = projeto.carregar_modelo(0)
    assert nova is not mostrada and [b.entry.char for b in nova.boxes] == ["q"]
