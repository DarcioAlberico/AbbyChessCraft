"""O JSON de cada `paginas/p<pid>.json` (o modelo v2, §4.3; a versão 3 da página, com a
geometria, o tamanho e o que ficou fora do quadro, §12.4), à parte do `ProjetoDeLivro`
(SPEC-qualidade Q-A1). `pagina_para_json` e `pagina_de_json` levam a página ao JSON e o trazem
de volta (com as áreas fora do quadro e a geometria), `comparavel` e `vazia` dizem o que
`pagina_igual` compara, `com_ids_de_diagramas` dá os ids aos diagramas lidos, e `inteiro` lê o
número de página de uma lista gravada. Ler e gravar o arquivo, e a posição da página no livro
(a sequência), são do projeto."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from abbychess.modelo import RECONHECIDA, Box, Decisoes, Estado, Pagina
from abbychess.zonas import Zona

#: A versão do formato de cada `paginas/p<pid>.json`. 3 (passo L): a geometria dos boxes,
#: o tamanho da fonte e os glifos fora do quadro; a 2 é lida como a geometria inteira.
VERSAO_DA_PAGINA = 3
VERSOES_DA_PAGINA = (2, 3)


def inteiro(valor) -> Optional[int]:
    """O número de página de uma lista gravada, ou None (texto, `Infinity`, fração, `true`)."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, float):
        return int(valor) if valor.is_integer() else None
    try:
        return int(valor)
    except (TypeError, ValueError, OverflowError):
        return None


def pagina_para_json(pagina: Pagina, pagina_da_fonte: Optional[int] = None) -> dict:
    """O JSON da página. O `indice` gravado é o da página no PDF (`pagina_da_fonte`,
    §12.4), e não a posição no livro, que muda ao reordenar; sem ele, o da página."""
    quadro, giro = pagina.geometria
    return {
        "versao": VERSAO_DA_PAGINA, "pid": pagina.pid,
        "indice": pagina.indice if pagina_da_fonte is None else pagina_da_fonte,
        "geometria": [None if quadro is None else list(quadro), int(giro)],
        "tamanho": None if pagina.tamanho is None else list(pagina.tamanho),
        "fora": [[lugar, box.para_json()] for lugar, box in pagina.fora],
        "areas_fora": [[tipo, lugar, _area_para_json(tipo, objeto), aparada]
                       for tipo, lugar, objeto, aparada in pagina.areas_fora],
        "estado": pagina.estado, "proximo_n": pagina.proximo_n,
        "gravado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "boxes": [b.para_json() for b in pagina.boxes],
        "tabuleiros": [list(map(int, t)) for t in pagina.tabuleiros],
        "diagramas": [d.para_json() for d in pagina.diagramas],
        "zonas": [z.como_dict() for z in pagina.zonas],
        "decisoes": pagina.decisoes.para_json(),
        "regua_do_negrito": pagina.regua_do_negrito,
    }


def pagina_de_json(bruto: dict) -> Pagina:
    from abbychess.diagramas import DiagramaLido

    if bruto.get("versao") not in VERSOES_DA_PAGINA:
        raise ValueError(f"página de versão {bruto.get('versao')!r}")
    return Pagina(pid=int(bruto["pid"]), indice=int(bruto["indice"]),
                  boxes=[Box.de_json(b) for b in bruto.get("boxes", [])],
                  tabuleiros=[tuple(int(v) for v in t) for t in bruto.get("tabuleiros", [])],
                  diagramas=[DiagramaLido.de_json(d) for d in bruto.get("diagramas", [])],
                  zonas=[Zona.de_dict(z) for z in bruto.get("zonas", [])],
                  decisoes=Decisoes.de_json(bruto.get("decisoes")),
                  estado=Estado(bruto.get("estado", RECONHECIDA)),   # ValueError: ilegível
                  proximo_n=int(bruto.get("proximo_n", 0)),
                  geometria=_geometria_de(bruto.get("geometria")),
                  tamanho=None if bruto.get("tamanho") is None
                  else tuple(int(v) for v in bruto["tamanho"]),
                  fora=tuple((int(lugar), Box.de_json(b)) for lugar, b in bruto.get("fora", [])),
                  areas_fora=tuple((tipo, int(lugar), _area_de_json(tipo, objeto), bool(aparada))
                                   for tipo, lugar, objeto, aparada
                                   in bruto.get("areas_fora", [])),
                  regua_do_negrito=dict(bruto.get("regua_do_negrito") or {}))


def vazia(pagina: Pagina) -> bool:
    return not (pagina.boxes or pagina.zonas or pagina.tabuleiros or pagina.diagramas
                or pagina.fora or pagina.areas_fora or pagina.decisoes != Decisoes())


def comparavel(pagina: Pagina) -> str:
    """A página como o JSON dela, sem o que não é conteúdo (`pagina_igual`)."""
    bruto = pagina_para_json(pagina, 0)
    for chave in ("gravado_em", "indice", "proximo_n"):
        bruto.pop(chave, None)
    return json.dumps(bruto, sort_keys=True, ensure_ascii=False)


def _area_para_json(tipo: str, objeto):
    if tipo == "zona":
        return objeto.como_dict()
    if tipo == "diagrama":
        return objeto.para_json()
    return [int(v) for v in objeto]


def _area_de_json(tipo: str, bruto):
    from abbychess.diagramas import DiagramaLido

    if tipo == "zona":
        return Zona.de_dict(bruto)
    if tipo == "diagrama":
        return DiagramaLido.de_json(bruto)
    if tipo == "tabuleiro":
        return tuple(int(v) for v in bruto)
    raise ValueError(f"área guardada de tipo {tipo!r}")


def _geometria_de(bruto) -> tuple:
    from abbychess import geometria as geo

    return geo.normalizar(bruto)


def com_ids_de_diagramas(diagramas):
    from abbychess.diagramas import com_ids

    return com_ids(diagramas)
