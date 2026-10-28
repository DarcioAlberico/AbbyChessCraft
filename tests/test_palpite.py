"""O palpite da rede no glifo que ninguém leu (SPEC §9.2, pendências do passo L).

O glifo que a cadeia toda leu sem reconhecer chega ao painel com o primeiro da rede abaixo do
limiar no campo, selecionado: o Enter o ensina, digitar o troca. Sem servidor, o controlador
pede o palpite só do glifo mostrado ao leitor da janela; com ele, um pedido leva os glifos sem
leitura da página toda, e o palpite entra no campo quando chega, se o campo ainda está vazio.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from abbychess.leitor import FONTE_MANUAL

from tests import leitor_falso, servidor_falso, test_janela
from tests.janela_util import boxes, fila, mostrar, trocar_entries
from tests.test_custo_dos_comandos import _pronta
from tests.test_janela import _esperar

app = test_janela.app
janela = test_janela.janela


def _com_rede(app, janela):
    _pronta(app, janela)
    janela.leitor.rede = leitor_falso.RedeFalsa()
    return janela.treino.campo


def test_o_glifo_lido_nao_tem_palpite(app, janela):
    campo = _com_rede(app, janela)
    caixa = (boxes(janela)[0].x1, boxes(janela)[0].y1)

    def ler_o_primeiro(e):
        if (e.x1, e.y1) == caixa:
            e.char, e.source, e.confidence = "a", "neural", 0.6
    trocar_entries(janela, janela.pagina.indice, ler_o_primeiro)
    _esperar(app, janela)
    mostrar(janela, 0)
    app.processEvents()
    assert campo.text() == "a" and "Palpite" not in janela.treino.leitura.text()
    assert janela.pagina.sugestao_do_atual() is None


def test_sem_rede_o_campo_fica_vazio(app, janela):
    _pronta(app, janela)
    mostrar(janela, fila(janela)[0])
    app.processEvents()
    assert janela.treino.campo.text() == "" and janela.pagina.sugestao_do_atual() is None


def test_digitar_troca_o_palpite(app, janela):
    campo = _com_rede(app, janela)
    primeiro = fila(janela)[0]
    mostrar(janela, primeiro)
    app.processEvents()
    assert campo.text() == leitor_falso.PALPITE
    QTest.keyClicks(campo, "a")                  # o palpite vem selecionado
    QTest.keyClick(campo, Qt.Key.Key_Return)
    _esperar(app, janela)
    assert (boxes(janela)[primeiro].char, boxes(janela)[primeiro].source) == ("a", FONTE_MANUAL)
    assert leitor_falso.PALPITE not in janela.leitor.padroes_por_caractere()


def test_o_palpite_que_chega_tarde_nao_apaga_o_que_se_digitou(app, janela):
    campo = _com_rede(app, janela)
    mostrar(janela, fila(janela)[0])
    app.processEvents()
    campo.setText("b")
    janela.treino.sugerir("z", 0.3)
    assert campo.text() == "b"


def test_o_palpite_vale_para_o_mesmo_glifo(app, janela):
    """O palpite guardado é do objeto do glifo: lido de novo, ou editado, ele é pedido outra
    vez, sem navegar."""
    _com_rede(app, janela)
    p = janela.pagina
    primeiro = fila(janela)[0]
    mostrar(janela, primeiro)
    velho = p._sugestoes[p.atual][0]
    assert velho is p.box_atual() and p.sugestao_do_atual() == (
        leitor_falso.PALPITE, leitor_falso.CONFIANCA_DO_PALPITE)
    trocar_entries(janela, p.indice, lambda e: None)    # cópias novas
    _esperar(app, janela)
    assert p.box_atual() is not velho and p._sugestoes[p.atual][0] is p.box_atual()


def test_o_glifo_aguardando_ganha_o_palpite_quando_a_leitura_chega(app, janela):
    """O glifo mostrado ainda aguardando o servidor não tem palpite; quando a leitura chega
    e ninguém o reconheceu, o palpite entra no campo sem navegar."""
    campo = _com_rede(app, janela)
    caixa = (boxes(janela)[0].x1, boxes(janela)[0].y1)

    def aguardar(e):
        if (e.x1, e.y1) == caixa:
            e.source = ""
    trocar_entries(janela, janela.pagina.indice, aguardar)
    _esperar(app, janela)
    mostrar(janela, 0)
    app.processEvents()
    assert campo.text() == "" and janela.pagina.sugestao_do_atual() is None

    def ninguem_leu(e):
        if (e.x1, e.y1) == caixa:
            e.source = "none"
    trocar_entries(janela, janela.pagina.indice, ninguem_leu)
    _esperar(app, janela)
    assert campo.text() == leitor_falso.PALPITE


def test_com_o_servidor_um_pedido_leva_a_pagina_e_o_palpite_chega_ao_campo(app, janela,
                                                                          tmp_path):
    _pronta(app, janela)
    servidor = servidor_falso.ServidorFalso(tmp_path / "padroes", janela.projeto.dados.limiares)
    na_interface = servidor_falso.ligar(janela.pagina, servidor)
    primeiro, segundo = fila(janela)[:2]
    mostrar(janela, primeiro)
    app.processEvents()
    assert janela.treino.campo.text() == ""      # o palpite ainda não chegou
    servidor_falso.entregar(na_interface, esperar_por=1)
    app.processEvents()
    assert janela.treino.campo.text() == leitor_falso.PALPITE
    assert [p.operacao for p in servidor.pedidos] == ["sugerir_recortes"]
    mostrar(janela, segundo)                       # já veio no mesmo pedido
    app.processEvents()
    assert janela.treino.campo.text() == leitor_falso.PALPITE
    assert len(servidor.pedidos) == 1
    servidor.fechar()


def test_a_rede_que_falha_nao_prende_o_painel(app, janela, caplog):
    campo = _com_rede(app, janela)

    class Quebrada:
        def predict(self, _recorte):
            raise RuntimeError("rede quebrada")
    janela.leitor.rede = Quebrada()
    mostrar(janela, fila(janela)[1])
    app.processEvents()
    assert janela.treino.campo.isEnabled() and campo.text() == ""
    assert janela.pagina.atual == janela.pagina.gid_em(fila(janela)[1])
    assert "rede quebrada" in caplog.text
