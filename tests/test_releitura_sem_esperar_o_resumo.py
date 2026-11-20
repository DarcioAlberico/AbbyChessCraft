"""A releitura de um glifo com o lote rodando (CA-11.7, alvo 150 ms; medido em 19/11 a 262 ms):
o que a interface fazia antes de pedir e depois de receber.

O perfil (`docs/revisoes/releitura-com-o-lote.md`) mostrou a leitura no filho em ~1 ms e quase
todo o tempo na interface: a cada gravação, `agendar` calculava o resumo da página (o
`resumo_das_confiancas`, com o julgamento do contexto da página inteira) na thread da
interface, e o pedido ao servidor só saía depois dele. Agora:

- o resumo de quem espera gravação é calculado quando alguém o pede, uma vez;
- o recorte vai ao servidor antes da gravação, e o filho lê enquanto a interface grava.
"""

from __future__ import annotations

from core.box_model import BoxEntry

from abbychess import pagina as pg
from abbychess.controlador import ControladorDePagina
from abbychess.leitor import LeitorDoLivro
from abbychess.projeto import ProjetoDeLivro

from tests.ajudantes import _pagina_sintetica


def _projeto(tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Resumo",
                                   _pagina_sintetica(tmp_path / "pagina.png"))
    projeto.salvar_pagina(0, [BoxEntry(c, 40 + 40 * k, 40, 70 + 40 * k, 100, 0.99, "neural")
                              for k, c in enumerate("abc")])
    return projeto


def _contar(monkeypatch, projeto):
    chamadas = []
    original = projeto.resumo.do_modelo

    def do_modelo(pagina, *a, **k):
        chamadas.append(k.get("leve", False))
        return original(pagina, *a, **k)
    monkeypatch.setattr(projeto.resumo, "do_modelo", do_modelo)
    return chamadas


def test_agendar_nao_calcula_o_resumo_e_quem_pede_o_tem_uma_vez(tmp_path, monkeypatch):
    projeto = _projeto(tmp_path)
    try:
        pagina = projeto.carregar_modelo(0)
        esperado = projeto.resumo.do_modelo(pagina.instantaneo(), leve=True)
        cache = projeto.paginas_em_memoria
        cache.gravador.atraso = 60                      # nada é gravado durante o teste
        chamadas = _contar(monkeypatch, projeto)
        assert cache.agendar(pagina)
        assert chamadas == []                           # a gravação não espera o resumo
        assert cache.resumos_pendentes() == {pagina.pid: esperado}
        assert cache.resumos_pendentes() == {pagina.pid: esperado}
        assert chamadas == [True]                       # uma vez, leve, e guardado
        pagina.boxes[0].entry.char = "z"
        assert cache.agendar(pagina)                    # outra versão: outro resumo
        assert cache.resumos_pendentes()[pagina.pid] != esperado
        assert chamadas == [True, True]
        assert projeto.resumo.do_livro()[0]["pid"] == pagina.pid
    finally:
        projeto.fechar()


def test_o_resumo_dado_por_quem_chama_vale(tmp_path, monkeypatch):
    projeto = _projeto(tmp_path)
    try:
        pagina = projeto.carregar_modelo(0)
        cache = projeto.paginas_em_memoria
        cache.gravador.atraso = 60
        chamadas = _contar(monkeypatch, projeto)
        assert cache.agendar(pagina, {"pid": pagina.pid, "estado": "teste"})
        assert cache.resumos_pendentes()[pagina.pid]["estado"] == "teste" and chamadas == []
    finally:
        projeto.fechar()


def test_o_recorte_vai_ao_servidor_antes_da_gravacao(tmp_path, monkeypatch):
    projeto = _projeto(tmp_path)
    try:
        ctl = ControladorDePagina()
        ctl.ligar(projeto, pg.FonteDePaginas(projeto.fonte),
                  LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares,
                                aguardar=True))
        ctl.ir_para(0)
        ctl.escolher(ctl.gids[0])
        ordem = []
        pedir = ctl.leitura.ler_os_aguardando_de
        agendar = projeto.paginas_em_memoria.agendar
        monkeypatch.setattr(ctl.leitura, "ler_os_aguardando_de",
                            lambda *a, **k: (ordem.append("pedido"), pedir(*a, **k))[1])
        monkeypatch.setattr(projeto.paginas_em_memoria, "agendar",
                            lambda *a, **k: (ordem.append("gravar"), agendar(*a, **k))[1])
        ctl.ajustar(0, 0, 1, 0)
        assert ordem == ["pedido", "gravar"]
    finally:
        projeto.fechar()
