r"""O descritor do k-NN do livro: o de hoje (`padroes.py`) contra o `contraste_borrado`.

    .venv\Scripts\python.exe ferramentas\medir_descritor.py
        [--darcy 25-31] [--yusupov 30-36]

A pergunta é se outro descritor deixa os padrões do livro lerem mais da página seguinte com
os mesmos erros (`docs/revisoes/ca-f1-investigacao.md`). O método é o da tabela de
`abbychess/padroes.py`. As amostras são as K primeiras de cada caractere nas páginas antes da
lida. Cada página seguinte é lida pelo vizinho mais perto que passa nas travas de proporção
(1,6) e de altura (0,20). O glifo é aceito abaixo do limiar.

- **Ajuste**, a fatia do Xadrez Vitorioso (o snapshot, índices 20–26). São rotulados os glifos
  das linhas verificadas que a leitura do snapshot já acerta, pelo alinhamento com o gabarito.
  O limiar do descritor novo é o que dá, com K = 3, os mesmos erros que o de hoje dá a 1.500.
- **Validação**, Darcy Lima e Yusupov, que nenhum limiar viu. As páginas são reconhecidas num
  projeto temporário, como o `medir.py` faz. Um glifo é rotulado quando a leitura confiante
  do programa (rede ou base, ≥ 0,90) e a camada de OCR do PDF (outro motor) dizem o mesmo
  caractere. O conjunto tende aos glifos fáceis, e os dois descritores são medidos nos mesmos
  glifos. Os dois descritores usam os limiares fixos (1.500 e o do ajuste).

Grava `docs/medidas/AAAA-MM-DD-descritor.json`.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))

from comum import destino_da_medida, estado_do_git  # noqa: E402
from medir import casar  # noqa: E402
from medir_italico import paginas as _indices_de  # noqa: E402
from replay_fatia import FATIA, MEDIDAS, _linhas_da_pagina  # noqa: E402
from rotular import PASTA_DOS_PDFS, VERDADE  # noqa: E402

LADO = 32
LIMIAR_DE_HOJE = 1500.0
PROPORCAO_MAXIMA = 1.6
TOLERANCIA_DE_ALTURA = 0.20
CONFIANCA_DO_ROTULO = 0.90
KS = (1, 3, 5)


def cinza(rec: np.ndarray) -> np.ndarray:
    """O descritor até aqui: o recorte em cinza esticado para 32×32."""
    return cv2.resize(rec, (LADO, LADO)).astype(np.float32).reshape(-1)


def contraste_borrado(rec: np.ndarray) -> np.ndarray:
    """O contraste esticado entre os percentis 2 e 98, a redução por área e um borrão leve."""
    baixo, alto = np.percentile(rec, 2), np.percentile(rec, 98)
    esticado = np.clip((rec.astype(np.float32) - baixo) * 255.0 / max(alto - baixo, 1.0), 0, 255)
    v = cv2.resize(esticado, (LADO, LADO), interpolation=cv2.INTER_AREA)
    return cv2.GaussianBlur(v, (3, 3), 0.8).reshape(-1)


DESCRITORES = {"cinza": cinza, "contraste_borrado": contraste_borrado}


# ----------------------------------------------------------------------
# Os glifos rotulados
# ----------------------------------------------------------------------

def _glifo(cz, boxes, i, referencia, pagina, char) -> dict:
    from abbychess.leitor import altura_relativa
    from core import vertical

    rec = vertical.recorte_de_pe(cz, boxes[i])
    return {"pagina": pagina, "char": char, "rec": rec,
            "alt": altura_relativa(rec, referencia)}


def rotulados_da_fatia(snapshot: Path) -> list:
    """Os glifos do snapshot que a leitura já acerta, pelo gabarito verificado."""
    import medir_legendas as ml

    from abbychess import exportar as ex
    from abbychess import pagina as pg
    from abbychess.projeto import ProjetoDeLivro
    from core import proporcao

    saida = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
        pasta = Path(pasta)
        with zipfile.ZipFile(snapshot) as z:
            z.extractall(pasta)
        projeto = ProjetoDeLivro.abrir(next(p.parent for p in pasta.rglob("projeto.json")))
        fonte = pg.fonte_do_projeto(projeto)
        for indice in projeto.paginas_lidas():
            g = json.loads((VERDADE / "xv" / f"i{indice:03d}.json").read_text(encoding="utf-8"))
            verificadas = [ln for ln in g["linhas_corpo"] if ln.get("texto_verificado")]
            boxes = projeto.carregar_pagina(indice) or []
            linhas, caixas, _ = _linhas_da_pagina(boxes, fonte, indice, ex)
            cz = pg.cinza(fonte.pagina(indice))
            referencia = proporcao.altura_de_referencia(boxes)
            for ip, jv in casar(caixas, [ln["caixa_rel"] for ln in verificadas]):
                _, _, acertos, _ = ml.alinhar(boxes, list(linhas[ip].indices),
                                              verificadas[jv]["texto"])
                saida += [_glifo(cz, boxes, i, referencia, indice, c) for i, c in acertos.items()]
    return saida


def rotulados_pela_camada(pdf: Path, indices: list) -> tuple:
    """Os glifos em que a leitura confiante do programa e a camada de OCR do PDF concordam;
    e quantos glifos lidos com confiança havia (para a taxa de acordo)."""
    import fitz

    from abbychess import livro as lv
    from abbychess import pagina as pg
    from abbychess.leitor import FONTES_CONFIRMADAS, LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro
    from core import proporcao
    from medir_italico import _glifos_da_camada

    saida, confiantes = [], 0
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
        projeto = ProjetoDeLivro.criar(Path(pasta), "descritor", pdf)
        leitor = LeitorDoLivro.com_modelos_globais(projeto.pasta_de_padroes,
                                                   limiares=projeto.dados.limiares)
        fonte = pg.fonte_do_projeto(projeto)
        lv.reconhecer_paginas(projeto, fonte, leitor, indices)
        doc = fitz.open(pdf)
        for indice in indices:
            imagem = fonte.pagina(indice)
            escala = imagem.width / doc[indice].rect.width
            camada = _glifos_da_camada(doc[indice])
            boxes = projeto.carregar_pagina(indice) or []
            cz = pg.cinza(imagem)
            referencia = proporcao.altura_de_referencia(boxes)
            for i, b in enumerate(boxes):
                if (not b.char or b.source in FONTES_CONFIRMADAS or b.source == "none"
                        or b.confidence < CONFIANCA_DO_ROTULO):
                    continue
                confiantes += 1
                cx, cy = (b.x1 + b.x2) / 2 / escala, (b.y1 + b.y2) / 2 / escala
                achado = next((c for c in camada if c[0] <= cx <= c[2] and c[1] <= cy <= c[3]),
                              None)
                if achado is not None and achado[4] == b.char:
                    saida.append(_glifo(cz, boxes, i, referencia, indice, b.char))
    return saida, confiantes


# ----------------------------------------------------------------------
# A leitura da página seguinte
# ----------------------------------------------------------------------

def vizinhos(dados: list, descritor, k: int):
    """Para cada glifo das páginas depois da primeira: a distância do vizinho mais perto que
    passa nas travas (inf se nenhum) e se o caractere dele é o certo."""
    X = np.stack([descritor(d["rec"]) for d in dados])
    prop = np.array([d["rec"].shape[1] / max(1, d["rec"].shape[0]) for d in dados], np.float32)
    alt = np.array([np.nan if d["alt"] is None else d["alt"] for d in dados], np.float32)
    chars = np.array([d["char"] for d in dados], object)
    pag = np.array([d["pagina"] for d in dados])
    distancias, certos = [], []
    for p in sorted(set(pag.tolist()))[1:]:
        refs, conta = [], defaultdict(int)
        for i in np.flatnonzero(pag < p):
            if conta[chars[i]] < k:
                refs.append(i)
                conta[chars[i]] += 1
        refs, q = np.array(refs), np.flatnonzero(pag == p)
        R, Q = X[refs], X[q]
        d = np.sqrt(np.maximum((Q * Q).sum(1)[:, None] + (R * R).sum(1)[None, :] - 2 * Q @ R.T, 0))
        razao = prop[refs][None, :] / prop[q][:, None]
        ok = (razao <= PROPORCAO_MAXIMA) & (razao * PROPORCAO_MAXIMA >= 1.0)
        ar, aq = alt[refs][None, :], alt[q][:, None]
        ok &= np.isnan(ar) | np.isnan(aq) | (np.abs(ar - aq) <= TOLERANCIA_DE_ALTURA * np.maximum(ar, aq))
        d = np.where(ok, d, np.inf)
        j = d.argmin(1)
        distancias.append(d[np.arange(len(q)), j])
        certos.append(chars[refs[j]] == chars[q])
    return np.concatenate(distancias), np.concatenate(certos)


def ler(distancias, certos, limiar: float) -> dict:
    aceitos = distancias < limiar
    n = len(distancias)
    return {"glifos": n, "certos": int((aceitos & certos).sum()),
            "errados": int((aceitos & ~certos).sum()),
            "cobertura": round(float((aceitos & certos).sum()) / n, 4) if n else None}


def limiar_com_os_erros(distancias, certos, erros: int) -> float:
    """O maior limiar que aceita no máximo `erros` glifos errados."""
    ordem = np.argsort(distancias)
    errados = np.cumsum(~certos[ordem])
    corte = int(np.searchsorted(errados, erros, side="right"))
    corte = min(corte, int(np.isfinite(distancias).sum()))
    if corte == 0:
        return 0.0
    if corte < len(ordem) and np.isfinite(distancias[ordem[corte]]):
        return float((distancias[ordem[corte - 1]] + distancias[ordem[corte]]) / 2)
    return float(distancias[ordem[corte - 1]]) + 1.0


def medir(darcy: list, yusupov: list) -> dict:
    snapshot = sorted(FATIA.glob("xv-*-inicial.zip"))[-1]
    xv = rotulados_da_fatia(snapshot)
    d0, c0 = vizinhos(xv, cinza, 3)
    d1, c1 = vizinhos(xv, contraste_borrado, 3)
    limiar = limiar_com_os_erros(d1, c1, ler(d0, c0, LIMIAR_DE_HOJE)["errados"])
    livros = {"xv": {"rotulados": len(xv), "rotulo": "gabarito verificado", "dados": xv}}
    for nome, prefixo, indices in (("darcy", "Darcy Lima", darcy),
                                   ("yusupov", "Artur Yusupov - Chess Evolution 1", yusupov)):
        pdf = next(p for p in Path(PASTA_DOS_PDFS).rglob("*.pdf") if p.name.startswith(prefixo))
        dados, confiantes = rotulados_pela_camada(pdf, indices)
        livros[nome] = {"rotulados": len(dados), "confiantes": confiantes,
                        "rotulo": "rede ou base ≥ 0,90 igual à camada de OCR do PDF",
                        "indices": indices, "dados": dados}
    resultado = {"limiar_contraste_borrado": round(limiar, 1), "limiar_cinza": LIMIAR_DE_HOJE,
                 "livros": {}}
    for nome, livro in livros.items():
        por_k = {}
        for k in KS:
            base = vizinhos(livro["dados"], cinza, k)
            novo = vizinhos(livro["dados"], contraste_borrado, k)
            por_k[str(k)] = {"cinza": ler(*base, LIMIAR_DE_HOJE),
                             "contraste_borrado": ler(*novo, limiar)}
        resultado["livros"][nome] = {**{c: v for c, v in livro.items() if c != "dados"},
                                     "por_k": por_k}
    validacao = [resultado["livros"][n]["por_k"][str(k)] for n in ("darcy", "yusupov") for k in KS]
    resultado["aprovado"] = all(v["contraste_borrado"]["certos"] > v["cinza"]["certos"]
                                and v["contraste_borrado"]["errados"] <= v["cinza"]["errados"]
                                for v in validacao)
    resultado["criterio"] = ("na validação (Darcy e Yusupov, K = 1, 3, 5), com os limiares fixos: "
                             "mais glifos certos e não mais errados que o descritor de hoje")
    return resultado


def main(argv=None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--darcy", default="25-31", help="índices do PDF")
    analisador.add_argument("--yusupov", default="30-36", help="índices do PDF")
    args = analisador.parse_args(argv)
    resultado = medir(_indices_de(args.darcy), _indices_de(args.yusupov))
    resultado["data"] = datetime.date.today().isoformat()
    resultado.update(estado_do_git())
    MEDIDAS.mkdir(parents=True, exist_ok=True)
    destino = destino_da_medida(resultado["data"], "descritor")
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
    print(json.dumps(resultado, ensure_ascii=False, indent=1))
    print(destino.relative_to(RAIZ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
