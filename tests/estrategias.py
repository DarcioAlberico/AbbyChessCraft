"""O que as propriedades dividem (SPEC-qualidade Q-T6): a página sintética, as invariantes da
página e as duas camadas de cada propriedade.

`pagina_sintetica` é a página das máquinas de estado (`test_modelo_estados`): cada glifo, dois
traços de tinta com um vão, para o `dividir` ter onde cortar. `conferir_a_pagina` são as
invariantes do modelo (§4.5) que toda edição mantém: gids únicos; aposentados ∩ vivos = ∅;
nenhuma decisão cita gid aposentado; uma quebra e uma junção nunca na mesma fronteira; a âncora
de todo virtual é um box vivo ou outro virtual, sem ciclo; `montar()` cobre cada glifo lido e
cada virtual uma vez.

`propriedade` dá a lei nas duas camadas (§15.1), como `_casos` dá as máquinas: a da suíte
rápida, com poucos exemplos, e a noturna (`-m noturno`), com milhares.
"""

from __future__ import annotations

import inspect

import pytest
from hypothesis import HealthCheck, Phase, given, settings
from PIL import Image, ImageDraw

from core.box_model import BoxEntry

from abbychess import texto as tx
from abbychess.modelo import Box, Pagina, gid_de

LARGURA, ALTURA = 900, 400
#: Os glifos de cada linha da página sintética.
POR_LINHA = 12
#: Os exemplos da camada noturna de cada propriedade, se ela não diz outro número.
EXEMPLOS_DA_NOITE = 2000


def pagina_sintetica(n: int, pid: int = 7):
    """`n` glifos em linhas de 12, cada um com dois traços verticais separados por um vão."""
    imagem = Image.new("L", (LARGURA, ALTURA), 255)
    desenho = ImageDraw.Draw(imagem)
    boxes = []
    for k in range(n):
        linha, coluna = divmod(k, POR_LINHA)
        x, y = 20 + coluna * 72, 20 + linha * 70
        desenho.rectangle((x, y, x + 8, y + 30), fill=0)
        desenho.rectangle((x + 20, y, x + 28, y + 30), fill=0)
        boxes.append(BoxEntry("a", x, y, x + 29, y + 31, 0.95, "net"))
    pagina = Pagina(pid=pid, indice=3, boxes=[Box(gid_de(pid, i), b) for i, b in enumerate(boxes)],
                    estado="reconhecida", proximo_n=n)
    return imagem, pagina


# ----------------------------------------------------------------------
# As invariantes da página (§4.5)
# ----------------------------------------------------------------------

def gids_unicos(pagina) -> None:
    vivos = [b.gid for b in pagina.boxes]
    assert len(vivos) == len(set(vivos))


def aposentados_e_vivos_nao_se_cruzam(pagina) -> None:
    vivos = pagina.vivos
    assert not (pagina.aposentados & vivos)
    assert all(g >> 20 == pagina.pid for g in vivos)
    assert all((g & ((1 << 20) - 1)) < pagina.proximo_n for g in vivos)


def nenhuma_decisao_cita_gid_aposentado(pagina) -> None:
    assert pagina.decisoes.gids() <= pagina.vivos


def quebra_e_juncao_nunca_na_mesma_fronteira(pagina) -> None:
    d = pagina.decisoes
    assert not (d.quebras & {b for _, b in d.juncoes})


def a_ancora_de_todo_virtual_esta_na_pagina(pagina) -> None:
    d = pagina.decisoes
    validos = pagina.vivos | {v.gid for v in d.virtuais}
    for v in d.virtuais:
        assert v.depois_de is None or v.depois_de in validos
        assert v.antes_de is None or v.antes_de in validos
    ancora = {v.gid: v.depois_de if v.depois_de is not None else v.antes_de for v in d.virtuais}
    for gid in ancora:                                    # e nenhuma cadeia fecha um ciclo
        vistos = set()
        while gid in ancora:
            assert gid not in vistos
            vistos.add(gid)
            gid = ancora[gid]


def montar_cobre_cada_glifo_uma_vez(pagina) -> None:
    doc = tx.montar(pagina)
    esperados = [b.gid for b in pagina.boxes if b.entry.char]
    esperados += [v.gid for v in pagina.decisoes.virtuais]
    assert sorted(doc.gids()) == sorted(esperados)


def conferir_a_pagina(pagina) -> None:
    """Todas as invariantes da página (as das máquinas de estado)."""
    gids_unicos(pagina)
    aposentados_e_vivos_nao_se_cruzam(pagina)
    nenhuma_decisao_cita_gid_aposentado(pagina)
    quebra_e_juncao_nunca_na_mesma_fronteira(pagina)
    a_ancora_de_todo_virtual_esta_na_pagina(pagina)
    montar_cobre_cada_glifo_uma_vez(pagina)


# ----------------------------------------------------------------------
# As duas camadas (§15.1)
# ----------------------------------------------------------------------

def ajustes(exemplos: int, deadline=200) -> settings:
    """Os ajustes de uma propriedade: os exemplos sempre os mesmos (`derandomize`), sem a fase
    "explain" (ela roda com rastreio linha a linha e leva minutos)."""
    return settings(
        max_examples=exemplos, derandomize=True, deadline=deadline,
        phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target, Phase.shrink],
        # O `tmp_path` é um só por teste: cada exemplo abre a pasta dele dentro.
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large,
                               HealthCheck.function_scoped_fixture])


def propriedade(lei, *, rapida: int, noturna: int = EXEMPLOS_DA_NOITE, deadline=200,
                **estrategias):
    """A lei nas duas camadas: (o teste da suíte rápida, com `rapida` exemplos, e o noturno,
    marcado, com `noturna`). Os parâmetros da lei que não são estratégias são fixtures
    (`tmp_path`). `deadline=None` só onde o disco ou o Qt fazem o tempo variar."""
    def variante(exemplos: int):
        def teste(*args, **kwargs):
            return lei(*args, **kwargs)
        teste.__signature__ = inspect.signature(lei)
        teste.__name__, teste.__qualname__ = lei.__name__, lei.__qualname__
        teste.__doc__, teste.__module__ = lei.__doc__, lei.__module__
        return ajustes(exemplos, deadline)(given(**estrategias)(teste))

    return variante(rapida), pytest.mark.noturno(pytest.mark.timeout(1800)(variante(noturna)))
