r"""O CA-9.1: ensinar as legendas em negrito não estraga o corpo (p. 21–27 do Xadrez Vitorioso).

    .venv\Scripts\python.exe ferramentas\medir_legendas.py [--snapshot <zip da fatia>]

Parte do snapshot da fatia (projeto reconhecido, padrões vazios, SHA-256 conferido). Nas
linhas verificadas do gabarito que não são legenda, mede o CER por glifo (a distância de
edição entre os glifos lidos e os do gabarito, sem os espaços, sobre os glifos do gabarito) e
quais boxes estão certos. Depois ensina, página a página, cada glifo errado das legendas
verificadas com o caractere do gabarito e o estilo medido na página (`efeitos_da_pagina`, o
que o Enter da janela passa), propaga os padrões do livro em todas as páginas (o F5) e mede
de novo.

O critério: o CER do corpo depois ≤ o de antes, e nenhum box de corpo certo passa a errado.
A mesma rodada sem o estilo (o efeito desconhecido, que o k-NN compara com todas as
amostras) sai à parte, informativa: mostra o que o filtro do efeito evita.

A divisão entre legenda e corpo é a dos blocos do gabarito; enquanto a estrutura não for
revisada, a medida é **provisória**.

Grava `docs/medidas/AAAA-MM-DD-legendas-<livro>.json`.
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))

from comum import destino_da_medida, estado_do_git  # noqa: E402
from medir import casar  # noqa: E402
from replay_fatia import FATIA, MEDIDAS, SEM_LEITURA, _linhas_da_pagina  # noqa: E402
from rotular import VERDADE, levenshtein  # noqa: E402


def alinhar(boxes, indices, texto: str):
    """Os glifos lidos da linha (os boxes `indices`) contra o texto do gabarito.

    Devolve (erros, glifos do gabarito, {box certo: char}, [(box, char certo)] das trocas).
    """
    from core.notacao import normalizar_saida

    lidos = [normalizar_saida(boxes[i].char) or SEM_LEITURA for i in indices]
    certos = [c for c in texto if not c.isspace()]
    acertos, trocas = {}, []
    for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, lidos, certos,
                                                      autojunk=False).get_opcodes():
        if op == "equal":
            acertos.update({indices[a1 + t]: lidos[a1 + t] for t in range(a2 - a1)})
        elif op == "replace":
            trocas.extend((indices[a1 + t], certos[b1 + t]) for t in range(min(a2 - a1, b2 - b1)))
    return levenshtein(lidos, certos), len(certos), acertos, trocas


def _medir(paginas, gabaritos, fonte, legendas: bool) -> dict:
    """As linhas verificadas de legenda (ou as outras) de todas as páginas."""
    from abbychess import exportar as ex

    conta = {"erros": 0, "glifos": 0, "linhas": 0, "acertos": {}, "trocas": {}}
    for indice, (_, boxes) in paginas.items():
        gabarito = gabaritos[indice]
        funcao = {b["id"]: b["funcao"] for b in gabarito["blocos"]}
        escolhidas = [ln for ln in gabarito["linhas_corpo"] if ln.get("texto_verificado")
                      and (funcao.get(ln.get("bloco")) == "legenda") == legendas]
        linhas, caixas, _ = _linhas_da_pagina(boxes, fonte, indice, ex)
        par = {jv: ip for ip, jv in casar(caixas, [ln["caixa_rel"] for ln in escolhidas])}
        conta["trocas"][indice] = []
        for k, linha in enumerate(escolhidas):
            conta["linhas"] += 1
            if k not in par:
                n = sum(1 for c in linha["texto"] if not c.isspace())
                conta["erros"] += n
                conta["glifos"] += n
                continue
            erros, glifos, acertos, trocas = alinhar(boxes, list(linhas[par[k]].indices),
                                                     linha["texto"])
            conta["erros"] += erros
            conta["glifos"] += glifos
            conta["acertos"].update({(indice, i): c for i, c in acertos.items()})
            conta["trocas"][indice].extend(trocas)
    return conta


def _cer(conta: dict):
    return round(conta["erros"] / conta["glifos"], 4) if conta["glifos"] else None


def _estilos(imagem, boxes):
    """O estilo de cada box como a leitura o mede (`PaginaLida.estilos`); None sem medida."""
    from abbychess import pagina as pg
    from abbychess.modelo import Estilo

    negritos, italicos = pg.efeitos_da_pagina(imagem, boxes)
    return [Estilo(negrito=bool(n), italico=bool(i)) if n is not None or i else None
            for n, i in zip(negritos, italicos)]


def rodada(livro: str, snapshot: Path, com_estilo: bool, verdade: Path = VERDADE) -> dict:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
        return _rodada(livro, snapshot, com_estilo, verdade, Path(pasta).resolve())


def _rodada(livro, snapshot, com_estilo, verdade, pasta) -> dict:
    from abbychess import pagina as pg
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro

    with zipfile.ZipFile(snapshot) as z:
        z.extractall(pasta)
    projeto = ProjetoDeLivro.abrir(next(p.parent for p in pasta.rglob("projeto.json")))
    leitor = LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)
    fonte = pg.fonte_do_projeto(projeto)
    indices = projeto.paginas_lidas()
    gabaritos = {i: json.loads((verdade / livro / f"i{i:03d}.json").read_text(encoding="utf-8"))
                 for i in indices}
    paginas = {i: (fonte.pagina(i), projeto.carregar_pagina(i) or []) for i in indices}
    estilos = {i: _estilos(imagem, boxes) if com_estilo else None
               for i, (imagem, boxes) in paginas.items()}

    corpo_antes = _medir(paginas, gabaritos, fonte, legendas=False)
    legendas_antes = _medir(paginas, gabaritos, fonte, legendas=True)
    negritos = sum(1 for i in indices for k, _ in legendas_antes["trocas"][i]
                   if estilos[i] and estilos[i][k] and estilos[i][k].negrito)
    ensinados = 0
    for indice in indices:
        imagem, boxes = paginas[indice]
        for k, certo in legendas_antes["trocas"][indice]:
            pg.ensinar(imagem, boxes, k, certo, leitor, projeto, indice, propagar=False,
                       efeito=None if estilos[indice] is None else estilos[indice][k])
            ensinados += 1
    for indice in indices:
        imagem, boxes = paginas[indice]
        pg.propagar_padroes(imagem, boxes, leitor, efeitos=estilos[indice])
    corpo_depois = _medir(paginas, gabaritos, fonte, legendas=False)
    legendas_depois = _medir(paginas, gabaritos, fonte, legendas=True)

    estragados = [{"pagina": f"i{i:03d}", "box": k, "era": c,
                   "ficou": paginas[i][1][k].char}
                  for (i, k), c in sorted(corpo_antes["acertos"].items())
                  if (i, k) not in corpo_depois["acertos"]]
    corrigidos = sum(1 for chave in corpo_depois["acertos"] if chave not in corpo_antes["acertos"])
    return {
        "gabaritos": {f"i{i:03d}": {"verdade_versao": g.get("verdade_versao"),
                                    "revisada": bool(g.get("revisado_por"))}
                      for i, g in gabaritos.items()},
        "com_estilo": com_estilo,
        "glifos_de_legenda_ensinados": ensinados,
        "ensinados_medidos_em_negrito": negritos if com_estilo else None,
        "corpo": {"linhas": corpo_antes["linhas"], "glifos": corpo_antes["glifos"],
                  "erros_antes": corpo_antes["erros"], "erros_depois": corpo_depois["erros"],
                  "cer_antes": _cer(corpo_antes), "cer_depois": _cer(corpo_depois),
                  "corrigidos": corrigidos, "estragados": len(estragados)},
        "legendas": {"linhas": legendas_antes["linhas"], "glifos": legendas_antes["glifos"],
                     "cer_antes": _cer(legendas_antes), "cer_depois": _cer(legendas_depois)},
        "estragados": estragados,
        "aprovado": (corpo_depois["erros"] <= corpo_antes["erros"] and not estragados),
    }


def medir(livro: str, snapshot: Path, verdade: Path = VERDADE) -> dict:
    com = rodada(livro, snapshot, True, verdade)
    sem = rodada(livro, snapshot, False, verdade)
    gabaritos = com.pop("gabaritos")
    sem.pop("gabaritos")
    revisadas = sum(1 for g in gabaritos.values() if g["revisada"])
    return {
        "livro": livro, "snapshot": snapshot.name,
        "snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        "gabaritos": gabaritos,
        "criterio": "CER do corpo depois ≤ antes e nenhum glifo de corpo certo passa a errado "
                    "(rodada com o estilo)",
        "aprovado": com["aprovado"],
        "estado": ("definitivo" if revisadas == len(gabaritos) else
                   "provisório: a divisão entre legenda e corpo vem da estrutura do gabarito, "
                   f"revisada em {revisadas}/{len(gabaritos)} páginas"),
        "com_estilo": com,
        "sem_estilo_informativo": sem,
    }


def main(argv=None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--livro", default="xv")
    analisador.add_argument("--snapshot", type=Path)
    args = analisador.parse_args(argv)
    candidatos = sorted(FATIA.glob(f"{args.livro}-*-inicial.zip"))
    snapshot = args.snapshot or (candidatos[-1] if candidatos else None)
    if snapshot is None:
        raise SystemExit(f"não há snapshot de {args.livro} em {FATIA}")
    esperado = snapshot.with_suffix(".sha256").read_text(encoding="utf-8").strip()
    if hashlib.sha256(snapshot.read_bytes()).hexdigest() != esperado:
        raise SystemExit(f"{snapshot.name}: SHA-256 não confere com {snapshot.with_suffix('.sha256').name}")
    resultado = medir(args.livro, snapshot)
    resultado["data"] = datetime.date.today().isoformat()
    resultado.update(estado_do_git())
    MEDIDAS.mkdir(parents=True, exist_ok=True)
    destino = destino_da_medida(resultado["data"], f"legendas-{args.livro}")
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
    resumo = {"aprovado": resultado["aprovado"], "estado": resultado["estado"],
              **{nome: {**resultado[chave]["corpo"],
                        "legendas_cer": [resultado[chave]["legendas"]["cer_antes"],
                                         resultado[chave]["legendas"]["cer_depois"]]}
                 for nome, chave in (("com_estilo", "com_estilo"),
                                     ("sem_estilo", "sem_estilo_informativo"))}}
    print(json.dumps(resumo, ensure_ascii=False, indent=1))
    print(destino.relative_to(RAIZ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
