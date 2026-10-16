"""Passo 1a: gravação atômica, `extras`, só leitura, fonte relativa e relocalizada, `livro.json`.

CA-4.2 (parte do 1a): a falha injetada em cada etapa da gravação (escrever o temporário,
`fsync`, `os.replace`), com `PermissionError` 3 vezes e depois sucesso, ou para sempre,
deixa o arquivo antigo inteiro ou o novo inteiro, em cada arquivo do projeto que já existe.
CA-4.7: a fonte movida é achada pelo SHA-256, e os `*.tmp` sobrando somem ao abrir. E a
parte do `livro.json` do CA-4.4: depois de qualquer sequência de gravações ele é igual ao
recalculado das páginas.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import threading
from pathlib import Path

import pytest
from core.box_model import BoxEntry

from abbychess import gravacao as gv
from abbychess import pagina as pg
from abbychess import verificacao as vf
from abbychess.leitor import FONTE_LIVRO, FONTE_MANUAL, FONTE_NENHUMA, LeitorDoLivro
from abbychess.padroes import PadroesDoLivro
from abbychess.projeto import (ARQUIVO_DO_LIVRO, Limiares, ProjetoDeLivro, ProjetoInvalido,
                               pendentes_pelo_histograma, resumo_das_confiancas)
from abbychess.zonas import Zona

from tests.test_treino_por_livro import _pagina_sintetica


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    monkeypatch.setattr(gv, "ESPERA", 0.0)


@pytest.fixture
def projeto(tmp_path):
    fonte = _pagina_sintetica(tmp_path / "pagina.png")
    return ProjetoDeLivro.criar(tmp_path / "livros", "Persistência", fonte)


def _box(char="a", source="net", confianca=0.5, x=10):
    return BoxEntry(char=char, x1=x, y1=10, x2=x + 20, y2=40, source=source,
                    confidence=confianca)


# ----------------------------------------------------------------------
# A gravação atômica
# ----------------------------------------------------------------------

class _Sistema:
    """Troca uma chamada ao sistema de `gravacao` (`_write`, `_fsync`, `_replace`) por uma
    que falha com `PermissionError` `vezes` vezes (None = sempre); as etapas são as reais.

    Guarda os fds abertos, para conferir que nenhum vazou; com `parcial`, a escrita que
    falha grava antes uns bytes, como um disco que para no meio.
    """

    def __init__(self, monkeypatch, chamada: str, vezes, *, parcial: bool = False):
        self.fds, self.chamadas = [], 0
        abrir_original, original = gv._abrir_fd, getattr(gv, chamada)

        def abrir(*args):
            fd = abrir_original(*args)
            self.fds.append(fd)
            return fd

        def falhar(*args):
            self.chamadas += 1
            if vezes is None or self.chamadas <= vezes:
                if parcial:
                    original(args[0], bytes(args[1][:3]))
                raise PermissionError("injetada")
            return original(*args)

        monkeypatch.setattr(gv, "_abrir_fd", abrir)
        monkeypatch.setattr(gv, chamada, falhar)

    def fds_abertos(self) -> list:
        abertos = []
        for fd in self.fds:
            try:
                os.fstat(fd)
                abertos.append(fd)
            except OSError:
                pass
        return abertos


CHAMADAS = ["_write", "_fsync", "_replace"]


@pytest.mark.parametrize("chamada", CHAMADAS)
def test_tres_falhas_e_depois_sucesso_grava_o_novo(tmp_path, monkeypatch, chamada):
    arquivo = tmp_path / "a.json"
    arquivo.write_text("antigo", encoding="utf-8")
    sistema = _Sistema(monkeypatch, chamada, 3)
    gv.gravar_texto(arquivo, "novo")
    assert arquivo.read_text(encoding="utf-8") == "novo" and sistema.chamadas == 4
    assert not list(tmp_path.glob("*.tmp")) and sistema.fds_abertos() == []


@pytest.mark.parametrize("chamada", CHAMADAS)
def test_falha_permanente_deixa_o_antigo_sem_temporario_nem_fd(tmp_path, monkeypatch, chamada):
    arquivo = tmp_path / "a.json"
    arquivo.write_text("antigo", encoding="utf-8")
    sistema = _Sistema(monkeypatch, chamada, None, parcial=chamada == "_write")
    with pytest.raises(PermissionError):
        gv.gravar_texto(arquivo, "novo e bem mais comprido")
    assert arquivo.read_text(encoding="utf-8") == "antigo"
    assert sistema.chamadas == gv.TENTATIVAS
    assert not list(tmp_path.glob("*.tmp")) and sistema.fds_abertos() == []


def test_outro_erro_nao_tenta_de_novo_e_nao_deixa_temporario(tmp_path, monkeypatch):
    arquivo = tmp_path / "a.json"
    arquivo.write_text("antigo", encoding="utf-8")
    chamadas = []

    def disco_cheio(*_args):
        chamadas.append(1)
        raise OSError(28, "sem espaço")

    monkeypatch.setattr(gv, "_replace", disco_cheio)
    with pytest.raises(OSError, match="sem espaço"):
        gv.gravar_texto(arquivo, "novo")
    assert arquivo.read_text(encoding="utf-8") == "antigo" and chamadas == [1]
    assert not list(tmp_path.glob("*.tmp"))


def test_interrupcao_durante_a_espera_nao_deixa_temporario(tmp_path, monkeypatch):
    arquivo = tmp_path / "a.json"
    _Sistema(monkeypatch, "_replace", None)

    def interromper(_segundos):
        raise KeyboardInterrupt

    monkeypatch.setattr(gv.time, "sleep", interromper)
    with pytest.raises(KeyboardInterrupt):
        gv.gravar_texto(arquivo, "novo")
    assert not list(tmp_path.glob("*.tmp"))


def test_texto_sai_em_utf8_sem_bom_e_com_lf(tmp_path):
    arquivo = tmp_path / "a.txt"
    gv.gravar_texto(arquivo, "ação\nfim\n")
    assert arquivo.read_bytes() == "ação\nfim\n".encode("utf-8")


def _cada_arquivo_do_projeto(projeto: ProjetoDeLivro, tmp_path: Path):
    """(nome, caminho, gravar) de cada arquivo da lista de §4.3 que existe no passo 1a."""
    contador = iter(range(10_000))
    feitos: dict = {}           # cada objeto só é montado pelo arquivo que o usa (o léxico é lento)

    def um(nome, fazer):
        if nome not in feitos:
            feitos[nome] = fazer()
        return feitos[nome]

    def pagina():
        projeto.salvar_pagina(0, [_box(x=next(contador) % 500)])

    def marcadas():
        projeto.salvar_pagina(0, [_box()], reconhecida=next(contador) % 2 == 1)

    def projeto_json():
        projeto.dados.idioma = "pt" if next(contador) % 2 else "en"
        projeto.salvar()

    def inclinacoes():
        fonte = um("fonte", lambda: pg.FonteDePaginas(projeto.fonte, endireitar=True,
                                                     pasta=projeto.pasta))
        fonte._inclinacoes.clear()
        fonte.inclinacao(0)

    def lexico_txt():
        lexico = um("lexico", lambda: vf.carregar_lexico("pt", projeto.arquivo_do_lexico))
        vf.adicionar(lexico, "palavra" + "".join(chr(97 + int(d)) for d in str(next(contador))),
                     projeto.arquivo_do_lexico)

    def metadados():
        import numpy as np

        padroes = um("padroes", lambda: PadroesDoLivro(projeto.pasta_de_padroes))
        padroes.ensinar(np.full((20, 10), 255, np.uint8), "a", origem=f"o{next(contador)}")

    def zonas():
        projeto.salvar_zonas(0, [Zona("texto", 0, 0, 10 + next(contador) % 50, 10)])

    return [("pagina", projeto._arquivo_da_pagina(0), pagina),
            ("marcadas", projeto.pasta / "paginas" / "marcadas.json", marcadas),
            ("projeto.json", projeto.pasta / "projeto.json", projeto_json),
            ("livro.json", projeto.pasta / ARQUIVO_DO_LIVRO, pagina),
            ("inclinacoes.json", projeto.pasta / "inclinacoes.json", inclinacoes),
            ("lexico.txt", projeto.arquivo_do_lexico, lexico_txt),
            ("metadados", projeto.pasta_de_padroes / "metadados.json", metadados),
            ("zonas", projeto.pasta / "zonas" / "0001.json", zonas)]


ARQUIVOS = ["pagina", "marcadas", "projeto.json", "livro.json", "inclinacoes.json",
            "lexico.txt", "metadados", "zonas"]


@pytest.mark.parametrize("vezes", [3, None], ids=["3-falhas", "permanente"])
@pytest.mark.parametrize("chamada", CHAMADAS)
@pytest.mark.parametrize("nome", ARQUIVOS)
def test_cada_arquivo_do_projeto_fica_inteiro(projeto, tmp_path, monkeypatch, nome, chamada,
                                              vezes):
    """CA-4.2 (1a): o antigo inteiro (falha permanente) ou o novo inteiro (3 falhas e depois
    sucesso), em cada arquivo que o projeto já tem, sem temporário e sem fd sobrando."""
    alvo = {n: (c, g) for n, c, g in _cada_arquivo_do_projeto(projeto, tmp_path)}
    caminho, gravar = alvo[nome]
    gravar()
    gravar()                                # existe, e com conteúdo de uma gravação inteira
    antes = caminho.read_bytes()
    identidade = (caminho.stat().st_ino, caminho.stat().st_mtime_ns)
    sistema = _Sistema(monkeypatch, chamada, vezes)
    if vezes is None:
        with pytest.raises(PermissionError):
            gravar()
        assert caminho.read_bytes() == antes
        assert (caminho.stat().st_ino, caminho.stat().st_mtime_ns) == identidade
    else:
        gravar()                            # trocado por um arquivo novo (o conteúdo pode
        assert (caminho.stat().st_ino, caminho.stat().st_mtime_ns) != identidade  # ser igual)
    if caminho.suffix == ".json":
        json.loads(caminho.read_bytes().decode("utf-8"))
    assert not list(projeto.pasta.rglob("*.tmp")) and sistema.fds_abertos() == []


@pytest.mark.parametrize("nome", ARQUIVOS)
def test_cada_arquivo_do_projeto_passa_pela_gravacao_atomica(projeto, tmp_path, monkeypatch,
                                                             nome):
    alvo = {n: (c, g) for n, c, g in _cada_arquivo_do_projeto(projeto, tmp_path)}
    caminho, gravar = alvo[nome]
    gravados = []
    original = gv.gravar_bytes
    monkeypatch.setattr(gv, "gravar_bytes", lambda c, d: (gravados.append(Path(c)),
                                                          original(c, d))[1])
    gravar()
    assert caminho in gravados


def test_padrao_ensinado_esquecido_e_restaurado_passam_pela_gravacao(projeto, monkeypatch):
    import numpy as np

    gravados, apagados = [], []
    original_gravar, original_apagar = gv.gravar_bytes, gv.apagar
    monkeypatch.setattr(gv, "gravar_bytes", lambda c, d: (gravados.append(Path(c)),
                                                          original_gravar(c, d))[1])
    monkeypatch.setattr(gv, "apagar", lambda c: (apagados.append(Path(c)), original_apagar(c))[1])
    padroes = PadroesDoLivro(projeto.pasta_de_padroes)
    png = padroes.ensinar(np.full((20, 10), 255, np.uint8), "a", origem="x")
    assert png in gravados and png.suffix == ".png"
    amostra = padroes.guardar(png)
    padroes.esquecer(png)
    assert png.resolve() in [a.resolve() for a in apagados] and not png.exists()
    gravados.clear()
    padroes.restaurar(amostra)
    assert png.resolve() in [g.resolve() for g in gravados] and png.exists()


def test_temporarios_sobrando_sao_apagados_ao_abrir(projeto):
    sobras = [projeto.pasta / "projeto.json.tmp", projeto.pasta / "paginas" / "0001.json.tmp",
              projeto.pasta_de_padroes / "metadados.json.tmp"]
    for sobra in sobras:
        sobra.parent.mkdir(parents=True, exist_ok=True)
        sobra.write_text("{pela metade", encoding="utf-8")
    ProjetoDeLivro.abrir(projeto.pasta)
    assert not any(s.exists() for s in sobras)


# ----------------------------------------------------------------------
# projeto.json: extras e só leitura
# ----------------------------------------------------------------------

def _editar_projeto_json(projeto, **mudancas):
    arquivo = projeto.pasta / "projeto.json"
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    for chave, valor in mudancas.items():
        if chave == "limiares":
            dados["limiares"].update(valor)
        else:
            dados[chave] = valor
    arquivo.write_text(json.dumps(dados), encoding="utf-8")


def test_campo_desconhecido_vai_para_extras_e_volta_ao_arquivo(projeto):
    _editar_projeto_json(projeto, campo_do_futuro={"a": 1}, limiares={"novo_limiar": 0.7})
    aberto = ProjetoDeLivro.abrir(projeto.pasta)
    assert aberto.dados.extras == {"campo_do_futuro": {"a": 1}, "limiares": {"novo_limiar": 0.7}}
    assert aberto.dados.limiares == Limiares()
    gravado = json.loads((projeto.pasta / "projeto.json").read_text(encoding="utf-8"))
    assert gravado["extras"] == aberto.dados.extras and "campo_do_futuro" not in gravado
    assert ProjetoDeLivro.abrir(projeto.pasta).dados.extras == aberto.dados.extras


def _instantaneo(pasta: Path) -> dict:
    return {str(p.relative_to(pasta)): (p.stat().st_mtime_ns,
                                        hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(pasta.rglob("*")) if p.is_file()}


def test_versao_maior_abre_so_para_leitura_e_nada_muda(projeto, tmp_path):
    projeto.salvar_pagina(0, [_box()])
    (projeto.pasta / "paginas" / "0002.json.tmp").write_text("sobra", encoding="utf-8")
    _editar_projeto_json(projeto, versao=99, campo_do_futuro=1)
    antes = _instantaneo(projeto.pasta)
    aberto = ProjetoDeLivro.abrir(projeto.pasta)
    try:
        assert aberto.somente_leitura
        assert aberto.carregar_pagina(0) == [_box()]
        assert aberto.resumo_do_livro()[0]["boxes"] == 1
        with pytest.raises(gv.SomenteLeitura):
            aberto.salvar_pagina(0, [_box("b")])
        with pytest.raises(gv.SomenteLeitura):
            aberto.salvar()
        with pytest.raises(gv.SomenteLeitura):
            aberto.salvar_zonas(0, [])
        with pytest.raises(gv.SomenteLeitura):
            vf.adicionar(vf.carregar_lexico("pt", aberto.arquivo_do_lexico), "nova",
                         aberto.arquivo_do_lexico)
        import numpy as np

        with pytest.raises(gv.SomenteLeitura):
            LeitorDoLivro(aberto.pasta_de_padroes).ensinar(np.zeros((9, 9), np.uint8), "a")
        fonte = pg.fonte_do_projeto(aberto)
        fonte.inclinacao(0)                 # medida em memória, não gravada
        assert _instantaneo(projeto.pasta) == antes
    finally:
        aberto.fechar()
    assert not gv.protegida(projeto.pasta)


def test_livro_json_que_falta_em_projeto_so_leitura_nao_e_gravado(projeto):
    projeto.salvar_pagina(0, [_box()])
    (projeto.pasta / ARQUIVO_DO_LIVRO).unlink()
    _editar_projeto_json(projeto, versao=99)
    aberto = ProjetoDeLivro.abrir(projeto.pasta)
    try:
        assert aberto.resumo_do_livro()[0]["boxes"] == 1
        assert not (projeto.pasta / ARQUIVO_DO_LIVRO).exists()
    finally:
        aberto.fechar()


def test_projeto_json_ilegivel_continua_recusado(projeto):
    (projeto.pasta / "projeto.json").write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ProjetoInvalido, match="ilegível"):
        ProjetoDeLivro.abrir(projeto.pasta)
    (projeto.pasta / "projeto.json").write_text('{"nome": "x", "fonte": "y", "criado": "z", '
                                                '"versao": "dois"}', encoding="utf-8")
    with pytest.raises(ProjetoInvalido, match="ilegível"):
        ProjetoDeLivro.abrir(projeto.pasta)


# ----------------------------------------------------------------------
# A fonte: caminho relativo e relocalização pelo SHA-256 (CA-4.7)
# ----------------------------------------------------------------------

def test_fonte_dentro_do_projeto_fica_relativa_e_o_projeto_pode_mudar_de_pasta(tmp_path):
    pasta = tmp_path / "livros" / "dentro"
    pasta.mkdir(parents=True)
    fonte = _pagina_sintetica(pasta / "pagina.png")
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Dentro", fonte)
    assert projeto.pasta == pasta.resolve() and projeto.dados.fonte == "pagina.png"
    movida = tmp_path / "outro_lugar" / "dentro"
    shutil.move(str(pasta), str(movida))
    reaberto = ProjetoDeLivro.abrir(movida)
    assert reaberto.fonte == movida.resolve() / "pagina.png" and not reaberto.fonte_ausente


def test_fonte_renomeada_e_achada_pelo_sha(projeto):
    antiga = projeto.fonte
    nova = antiga.with_name("renomeada.png")
    antiga.rename(nova)
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    assert reaberto.fonte == nova.resolve() and not reaberto.fonte_ausente
    gravado = json.loads((projeto.pasta / "projeto.json").read_text(encoding="utf-8"))
    assert Path(gravado["fonte"]) == nova.resolve()


def test_fonte_sumida_sem_copia_fica_ausente_e_relocalizar_confere_o_conteudo(projeto, tmp_path):
    antiga = projeto.fonte
    guardada = tmp_path / "longe" / "guardada.png"
    guardada.parent.mkdir()
    antiga.rename(guardada)
    outra = _pagina_sintetica(tmp_path / "longe" / "outra.png", ("xyz",))
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    assert reaberto.fonte_ausente
    with pytest.raises(ProjetoInvalido, match="não é a fonte"):
        reaberto.relocalizar(outra)
    reaberto.relocalizar(guardada)
    assert reaberto.fonte == guardada.resolve() and not reaberto.fonte_ausente
    assert ProjetoDeLivro.abrir(projeto.pasta).fonte == guardada.resolve()


def test_projeto_antigo_ganha_o_sha_da_fonte_ao_abrir(projeto):
    _editar_projeto_json(projeto, fonte_sha256="")
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    esperado = hashlib.sha256(projeto.fonte.read_bytes()[:4 * 2**20]).hexdigest()
    assert reaberto.dados.fonte_sha256 == esperado


# ----------------------------------------------------------------------
# livro.json (CA-4.4, a parte do 1a)
# ----------------------------------------------------------------------

def _pagina_aleatoria(sorteio: random.Random):
    fontes = [FONTE_LIVRO, FONTE_MANUAL, FONTE_NENHUMA, "net", "base"]
    return [_box(char=sorteio.choice(["", "a", "b"]), source=sorteio.choice(fontes),
                 confianca=round(sorteio.random(), 4), x=10 * k) for k in range(sorteio.randint(0, 30))]


@pytest.mark.parametrize("semente", range(5))
def test_livro_json_e_igual_ao_recalculado_depois_de_qualquer_sequencia(projeto, semente):
    sorteio = random.Random(semente)
    for _ in range(25):
        indice = sorteio.randrange(6)
        boxes = _pagina_aleatoria(sorteio)
        tabuleiros = [(0, 0, 100, 100)] * sorteio.randint(0, 2)
        projeto.salvar_pagina(indice, boxes, tabuleiros, reconhecida=sorteio.random() > 0.3)
    gravado = json.loads((projeto.pasta / ARQUIVO_DO_LIVRO).read_text(encoding="utf-8"))
    assert gravado == projeto.recalcular_livro()
    assert ProjetoDeLivro.abrir(projeto.pasta).resumo_do_livro() == projeto.resumo_do_livro()


def test_livro_json_que_falta_e_refeito(projeto):
    projeto.salvar_pagina(2, [_box(), _box(source=FONTE_MANUAL)], reconhecida=False)
    (projeto.pasta / ARQUIVO_DO_LIVRO).unlink()
    resumo = ProjetoDeLivro.abrir(projeto.pasta).resumo_do_livro()
    assert resumo == {2: {"estado": "glifos_marcados", "boxes": 2, "pendentes": 1,
                          "confirmados": 1, "sem_leitura": 0, "histograma": {"50": 1},
                          "diagramas": 0, "diagramas_por_conferir": 0}}
    assert (projeto.pasta / ARQUIVO_DO_LIVRO).is_file()


def test_livro_json_estragado_e_refeito(projeto):
    projeto.salvar_pagina(0, [_box()])
    (projeto.pasta / ARQUIVO_DO_LIVRO).write_text("{nada", encoding="utf-8")
    assert ProjetoDeLivro.abrir(projeto.pasta).resumo_do_livro()[0]["boxes"] == 1


def test_histograma_da_os_pendentes_de_outro_limiar():
    sorteio = random.Random(7)
    boxes = _pagina_aleatoria(sorteio) + [_box(confianca=c)
                                          for c in (0.0, 0.29, 0.5, 0.899999, 0.9, 0.995, 1.0)]
    resumo = resumo_das_confiancas(boxes, Limiares())
    for centesimos in range(0, 101):            # de 0,00 a 1,00, a faixa das opções
        limiares = Limiares(revisao=centesimos / 100)
        assert (pendentes_pelo_histograma(resumo, limiares.revisao)
                == resumo_das_confiancas(boxes, limiares)["pendentes"]), centesimos


# ----------------------------------------------------------------------
# A trava de só leitura, a fonte em só leitura e a gravação concorrente
# ----------------------------------------------------------------------

def _versao_99(projeto):
    _editar_projeto_json(projeto, versao=99)


def test_duas_aberturas_so_leitura_da_mesma_pasta_precisam_de_dois_fechar(projeto):
    projeto.salvar_pagina(0, [_box()])
    _versao_99(projeto)
    a, b = ProjetoDeLivro.abrir(projeto.pasta), ProjetoDeLivro.abrir(projeto.pasta)
    a.fechar()
    a.fechar()                              # fechar duas vezes não solta a trava do outro
    with pytest.raises(gv.SomenteLeitura):
        b.salvar_pagina(0, [_box("b")])
    b.fechar()
    assert not gv.protegida(projeto.pasta)


def test_trava_de_uma_pasta_nao_afeta_o_projeto_ao_lado(projeto, tmp_path):
    vizinho = ProjetoDeLivro.criar(tmp_path / "livros", "Vizinho",
                                   _pagina_sintetica(tmp_path / "outra.png"))
    _versao_99(projeto)
    travado = ProjetoDeLivro.abrir(projeto.pasta)
    try:
        vizinho.salvar_pagina(0, [_box()])          # não levanta
        assert vizinho.carregar_pagina(0) == [_box()]
    finally:
        travado.fechar()


def test_so_leitura_sem_pasta_de_padroes_nao_cria_nada(projeto):
    import shutil as sh

    sh.rmtree(projeto.pasta_de_padroes)
    _versao_99(projeto)
    antes = _instantaneo(projeto.pasta)
    aberto = ProjetoDeLivro.abrir(projeto.pasta)
    try:
        leitor = LeitorDoLivro(aberto.pasta_de_padroes, limiares=aberto.dados.limiares)
        assert leitor.total_de_padroes == 0
        assert not aberto.pasta_de_padroes.exists() and _instantaneo(projeto.pasta) == antes
    finally:
        aberto.fechar()


def test_so_leitura_acha_a_fonte_renomeada_e_relocaliza_so_na_memoria(projeto, tmp_path):
    antiga = projeto.fonte
    nova = antiga.with_name("renomeada.png")
    antiga.rename(nova)
    _versao_99(projeto)
    antes = _instantaneo(projeto.pasta)
    aberto = ProjetoDeLivro.abrir(projeto.pasta)
    try:
        assert aberto.fonte == nova.resolve() and aberto.fonte_relocalizada
        longe = tmp_path / "longe"
        longe.mkdir()
        nova.rename(longe / "outra.png")
        aberto.relocalizar(longe / "outra.png")     # não levanta, não grava
        assert aberto.fonte == (longe / "outra.png").resolve()
        assert _instantaneo(projeto.pasta) == antes
    finally:
        aberto.fechar()


def test_relocalizar_que_falha_ao_gravar_nao_muda_a_memoria(projeto, tmp_path, monkeypatch):
    antes = (projeto.dados.fonte, projeto.dados.fonte_sha256)
    nova = projeto.fonte.with_name("copia.png")
    nova.write_bytes(projeto.fonte.read_bytes())

    def falhar(*_args):
        raise PermissionError("disco")

    monkeypatch.setattr(gv, "gravar_bytes", falhar)
    with pytest.raises(PermissionError):
        projeto.relocalizar(nova)
    assert (projeto.dados.fonte, projeto.dados.fonte_sha256) == antes


def test_fonte_de_mesmo_comeco_e_tamanho_diferente_nao_e_a_fonte(projeto, tmp_path):
    longe = tmp_path / "longe"
    longe.mkdir()
    conteudo = projeto.fonte.read_bytes()
    projeto.fonte.rename(longe / "guardada.png")
    (projeto.fonte.parent / "parecida.png").write_bytes(conteudo + b"anexo")
    reaberto = ProjetoDeLivro.abrir(projeto.pasta)
    assert reaberto.fonte_ausente                    # mesmo SHA dos 4 MB, outro tamanho
    with pytest.raises(ProjetoInvalido, match="não é a fonte"):
        reaberto.relocalizar(projeto.fonte.parent / "parecida.png")


def test_abrir_em_midia_so_de_leitura_abre_sem_gravar_o_ajuste(projeto, monkeypatch):
    _editar_projeto_json(projeto, fonte_sha256="", campo_novo=1)

    def recusar(*_args):
        raise PermissionError("mídia só de leitura")

    monkeypatch.setattr(gv, "gravar_bytes", recusar)
    aberto = ProjetoDeLivro.abrir(projeto.pasta)
    assert aberto.dados.fonte_sha256 and aberto.dados.extras == {"campo_novo": 1}


def test_livro_json_igual_ao_recalculado_depois_de_mudar_o_limiar(projeto):
    sorteio = random.Random(3)
    for indice in range(4):
        projeto.salvar_pagina(indice, _pagina_aleatoria(sorteio))
    projeto.dados.limiares = Limiares(revisao=0.55)
    projeto.salvar()
    projeto.reaplicar_limiar()
    gravado = json.loads((projeto.pasta / ARQUIVO_DO_LIVRO).read_text(encoding="utf-8"))
    assert gravado == projeto.recalcular_livro()


def test_gravacoes_de_duas_threads_deixam_o_livro_coerente(projeto):
    """O lote grava de outra thread enquanto a janela grava a página dela."""
    erros = []

    def gravar(primeira, semente):
        sorteio = random.Random(semente)
        try:
            for _ in range(15):
                projeto.salvar_pagina(sorteio.randrange(primeira, primeira + 3),
                                      _pagina_aleatoria(sorteio),
                                      reconhecida=sorteio.random() > 0.3)
        except Exception as erro:      # noqa: BLE001 (o teste quer qualquer falha)
            erros.append(erro)

    linhas = [threading.Thread(target=gravar, args=(k * 3, k)) for k in range(2)]
    for t in linhas:
        t.start()
    for t in linhas:
        t.join()
    assert erros == []
    gravado = json.loads((projeto.pasta / ARQUIVO_DO_LIVRO).read_text(encoding="utf-8"))
    assert gravado == projeto.recalcular_livro()


def test_resumo_do_livro_e_copia(projeto):
    projeto.salvar_pagina(0, [_box()])
    resumo = projeto.resumo_do_livro()
    resumo[0]["histograma"]["50"] = 999
    assert projeto.resumo_do_livro()[0]["histograma"] == {"50": 1}


def test_temporario_de_arquivo_do_usuario_nao_e_apagado(projeto):
    meu = projeto.pasta / "anotacoes.tmp"
    meu.write_text("meu", encoding="utf-8")
    ProjetoDeLivro.abrir(projeto.pasta)
    assert meu.exists()
