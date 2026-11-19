"""CA-C3 e CA-C4 (SPEC-pagina-perfeita, C-3 e C-4; T2): o vigia do servidor de leitura.

- **CA-C3.** O filho manda `("vivo", id)` a cada 50 glifos. Um filho travado, mas vivo, ficava
  600 s por página; agora, sem sinal no prazo com um pedido em curso, ele é morto, e o pedido
  segue a regra da queda. Um leitor falso que dorme para sempre no glifo 10 é morto em até 70 s.
- **CA-C4.** O filho manda `("comecou", id)`. Duas quedas no mesmo pedido: ele vira falha, e o
  resto segue (o lote não prende). `reinicios` zera a cada pedido concluído. O pedido que não
  estava em curso na queda não acumula queda.

Com o leitor falso (`tests/leitor_falso.py`) e um filho de verdade: camada `processo`.
"""

from __future__ import annotations

import pytest
from PIL import Image

from abbychess import servidor_de_leitura as sl
from abbychess.projeto import Limiares

from tests.ajudantes import _pagina_sintetica, esperar

FABRICA = "tests.leitor_falso:criar"

pytestmark = pytest.mark.processo


def _servidor(tmp_path, **k):
    avisos = []
    s = sl.ServidorDeLeitura(tmp_path / "padroes", Limiares(), fabrica=FABRICA,
                             ao_avisar=lambda _titulo, texto, desistiu: avisos.append(texto), **k)
    s.avisos = avisos
    assert s.pronto.wait(60), "o filho não ficou pronto"
    return s


def _imagem(tmp_path, linhas=("abc abc abc", "cab bca")):
    return Image.open(_pagina_sintetica(tmp_path / "pagina.png", linhas)).convert("L")


def _pedir_a_pagina(servidor, imagem, prioridade=sl.LOTE):
    return servidor.pedir("ler_pagina", (imagem, [], []), prioridade=prioridade)


def test_ca_c3_o_prazo_sem_sinal_cabe_nos_70_s():
    assert sl.PRAZO_SEM_SINAL + 2 * sl.VOLTA_DO_VIGIA <= 70
    assert sl.SINAL_A_CADA == 50


@pytest.mark.erro_esperado                 # o vigia loga o filho travado
def test_ca_c3_o_filho_travado_e_morto_e_o_pedido_segue_a_regra_da_queda(tmp_path, monkeypatch):
    monkeypatch.setenv("ABBY_FALSO_DORME_NO_GLIFO", "10")
    s = _servidor(tmp_path, prazo_sem_sinal=3)
    try:
        primeiro = s.pid
        pedido = _pedir_a_pagina(s, _imagem(tmp_path))
        assert pedido.feito.wait(60), "o vigia não matou o filho travado"
        # Reaberto, o filho dorme de novo na mesma página: duas quedas no pedido, e ele falha.
        assert not pedido.ok and "duas vezes" in pedido.resultado
        assert s.pid != primeiro and not s.desistiu
        assert any("sinal" in aviso for aviso in s.avisos)
        assert s.chamar("pid", timeout=60) == s.pid                # e o servidor segue lendo
    finally:
        s.fechar()


def test_ca_c3_a_leitura_longa_que_da_sinal_nao_e_morta(tmp_path, monkeypatch):
    """~130 glifos a 20 ms: 2,6 s de página, com o prazo de 1,5 s; o "vivo" a cada 50 glifos
    (1 s) a mantém."""
    monkeypatch.setenv("ABBY_FALSO_MS_POR_GLIFO", "20")
    s = _servidor(tmp_path, prazo_sem_sinal=1.5)
    try:
        linhas = ("abc abc abc abc abc abc abc",) * 6
        lida = s.esperar(_pedir_a_pagina(s, _imagem(tmp_path, linhas)), 60)
        assert len(lida.boxes) > 100
        assert s.reinicios == 0 and not s.avisos
    finally:
        s.fechar()


def test_ca_c4_a_pagina_que_derruba_o_filho_duas_vezes_falha_e_o_resto_segue(tmp_path,
                                                                              monkeypatch):
    monkeypatch.setenv("ABBY_FALSO_CAI_NO_GLIFO", "5")
    s = _servidor(tmp_path)
    try:
        pedido = _pedir_a_pagina(s, _imagem(tmp_path))
        assert pedido.feito.wait(60)
        assert not pedido.ok and "duas vezes" in pedido.resultado and pedido.quedas == 2
        assert not s.desistiu and not s.parado
        assert s.chamar("pid", timeout=60) == s.pid                # o resto segue
        assert s.reinicios == 0                                    # zerou no pedido concluído
    finally:
        s.fechar()


def test_ca_c4_reinicios_zera_a_cada_pedido_concluido(tmp_path):
    s = _servidor(tmp_path)
    try:
        s.processo.kill()
        assert s.chamar("pid", timeout=60) == s.pid               # reaberto, e o pedido volta
        assert s.reinicios == 0
        s.processo.kill()                                          # uma queda, não a segunda
        assert s.chamar("pid", timeout=60) == s.pid
        assert not s.desistiu and len(s.avisos) == 2
    finally:
        s.fechar()


def test_ca_c4_o_pedido_que_nao_estava_em_curso_nao_acumula_queda(tmp_path, monkeypatch):
    """O filho cai duas vezes ainda carregando os modelos: o pedido esperava na fila, e não
    leva a culpa; sem nada concluído entre as duas quedas, o servidor desiste, como antes."""
    s = _servidor(tmp_path)
    try:
        monkeypatch.setenv("ABBY_FALSO_ATRASO_AO_ABRIR", "30")     # o filho reaberto demora
        s.processo.kill()
        assert esperar(lambda: s.reinicios == 1 and s.processo.is_alive(), 30)
        pedido = s.pedir("pid")
        s.processo.kill()
        assert pedido.feito.wait(60)
        assert pedido.quedas == 0 and s.desistiu
        assert "caiu duas vezes" in pedido.resultado
    finally:
        s.fechar()
