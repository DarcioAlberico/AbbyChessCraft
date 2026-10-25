"""O cabeçalho e o rodapé corridos no fim da fila de revisão (§8.1, pendências do passo L).

No Xadrez Vitorioso, o □ do título corrido ("XADREZ VITORIOSO: ESTRATÉGIA 21") tinha
confiança 0 e abria a fila de toda página: a exportação o tira, e o usuário tinha de pulá-lo
antes de chegar ao texto. Agora o que a exportação tira vem depois do resto da fila e antes
dos pulados, em todas as ordens.
"""

from __future__ import annotations

from types import SimpleNamespace

from PIL import Image

from core.box_model import BoxEntry

from abbychess import exportar as ex
from abbychess import pagina as pg
from abbychess.controlador import ControladorDePagina, Eventos, ExecutorSincrono
from abbychess.leitor import FONTE_NENHUMA
from abbychess.modelo import Box, Pagina
from abbychess.projeto import Limiares
from abbychess.zonas import TEXTO, Zona

ALTURA = 2800


def _entries():
    """O título corrido "12 TITULO" no alto, com o "U" sem leitura, e 30 linhas de corpo
    lidas com confiança baixa (todas na fila)."""
    cabecalho = [BoxEntry(c, 100 + n * 25, 60, 120 + n * 25, 90, 0.95, "neural")
                 for n, c in enumerate("12 TITULO") if c != " "]
    cabecalho[5] = BoxEntry("", cabecalho[5].x1, 60, cabecalho[5].x2, 90, 0.0, FONTE_NENHUMA)
    corpo = [BoxEntry(c, 100 + n * 25, 400 + k * 40, 120 + n * 25, 430 + k * 40, 0.5, "neural")
             for k in range(30) for n, c in enumerate("texto")]
    return cabecalho, corpo


def test_as_margens_da_pagina_contam_o_glifo_sem_leitura():
    cabecalho, corpo = _entries()
    boxes = cabecalho + corpo
    assert ex.margens_da_pagina(boxes, ALTURA) == set(range(len(cabecalho)))
    # Um cisco sem leitura logo abaixo do título não fecha o vão que a regra pede: ela roda
    # nos lidos, como na exportação, e o cisco, fora da altura do título, não entra.
    cisco = BoxEntry("", 400, 100, 410, 112, 0.0, FONTE_NENHUMA)
    assert ex.margens_da_pagina(cabecalho + [cisco] + corpo, ALTURA) == set(range(len(cabecalho)))


def test_o_cisco_sem_leitura_na_borda_da_pagina_e_margem():
    """O cisco da borda da digitalização (no Xadrez Vitorioso, 3×20 px a 34 px do pé da
    página) travava a cabeça da fila; o do meio da página continua na vez dele."""
    cabecalho, corpo = _entries()
    no_pe = BoxEntry("", 168, ALTURA - 34, 171, ALTURA - 14, 0.0, FONTE_NENHUMA)
    no_meio = BoxEntry("", 1500, 1400, 1508, 1406, 0.0, FONTE_NENHUMA)
    boxes = cabecalho + corpo + [no_pe, no_meio]
    margens = ex.margens_da_pagina(boxes, ALTURA)
    assert len(boxes) - 2 in margens and len(boxes) - 1 not in margens


def test_a_fila_da_lista_manda_as_margens_para_o_fim():
    cabecalho, corpo = _entries()
    boxes = cabecalho + corpo
    leitor = SimpleNamespace(limiares=Limiares())
    assert pg.fila_de_revisao(boxes, leitor)[0] == 5                # confiança 0 na frente
    fila = pg.fila_de_revisao(boxes, leitor, ex.margens_da_pagina(boxes, ALTURA))
    assert fila[0] == len(cabecalho) and fila[-1] == 5
    assert sorted(fila) == sorted(pg.fila_de_revisao(boxes, leitor))  # a mesma fila, na ordem


def _controlador(zonas=()):
    cabecalho, corpo = _entries()
    p = ControladorDePagina(Eventos(), ExecutorSincrono())
    p.imagem = Image.new("L", (2000, ALTURA), 255)
    p.leitor = SimpleNamespace(limiares=Limiares())
    p.modelo = Pagina(pid=0, indice=0, boxes=[Box(1000 + k, e) for k, e in
                                               enumerate(cabecalho + corpo)])
    p.modelo.zonas = list(zonas)
    return p, len(cabecalho)


def test_a_fila_da_janela_poe_as_margens_depois_do_texto_e_antes_dos_pulados():
    p, n = _controlador()
    gids = [b.gid for b in p.modelo.boxes]
    assert gids[5] in p.gids_de_margem()
    for ordem in ("confianca", "caractere"):
        p.ordem_da_fila = ordem
        fila = p.fila()
        # Do título corrido só o "U" está na fila (os outros têm confiança alta), e no fim.
        assert [g for g in fila if g in gids[:n]] == [gids[5]], ordem
        assert fila[-1] == gids[5] and len(fila) == 1 + len(gids) - n, ordem
    # Na ordem de leitura a fila fica na ordem da página: andar e o fim da página contam com ela.
    p.ordem_da_fila = "leitura"
    assert p.fila() == sorted(p.fila(), key=gids.index) and p.fila()[0] == gids[5]
    p.escolher(gids[n + 10])
    p.andar(-1)
    assert p.atual == gids[n + 9]
    p.ordem_da_fila = "confianca"
    p.pulados.add(gids[n])
    assert p.fila()[-2:] == [gids[5], gids[n]]


def test_o_glifo_numa_area_de_margem_tambem_vai_para_o_fim():
    """Uma linha do corpo dentro de uma área de rodapé desenhada pelo usuário."""
    zona = Zona(TEXTO, 90, 390, 300, 440, funcao="rodape")
    p, n = _controlador([zona])
    gids = [b.gid for b in p.modelo.boxes]
    primeira_linha = set(gids[n:n + 5])
    assert primeira_linha <= p.gids_fora_do_texto()
    assert set(p.fila()[-6:]) == {gids[5]} | primeira_linha
