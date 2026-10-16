r"""Gabaritos de referência (SPEC §15.2): rascunho, faixas para transcrição, conferência.

Uso:

    .venv\Scripts\python.exe ferramentas\rotular.py rascunho --livro xv --pdf <PDF> --indices 20-26
    .venv\Scripts\python.exe ferramentas\rotular.py comparar <a.json> <b.json>
    .venv\Scripts\python.exe ferramentas\rotular.py cego-modelo --livro xv --pagina i020
    .venv\Scripts\python.exe ferramentas\rotular.py cego --livro xv --pagina i020 --por <nome> --txt <.txt>
    .venv\Scripts\python.exe ferramentas\rotular.py cego --livro xv --pagina i020 --por <nome>
        --diagrama d0 --fen <FEN>
    .venv\Scripts\python.exe ferramentas\rotular.py revisar --livro xv --pagina i020 --por <nome>
        --fen-verificado d0 --lado-verificado d0
    .venv\Scripts\python.exe ferramentas\rotular.py validar --livro xv --pdf <PDF>

O texto dos livros é do usuário: o assistente cuida só da estrutura (ver
`docs/protocolo-rotulagem.md`), e o texto de cada linha se corrige por
`texto-exportar` / `texto-importar`, num `.txt` por página.

O **rascunho** é a leitura atual do programa (modelos globais, padrões vazios), no
formato do gabarito: blocos com função, linhas de corpo com caixa e texto, diagramas
com FEN e legenda. Ele **não é verdade**: alguém corrige cada linha olhando as faixas
da página (`.rotulagem/<livro>/iNNN/faixa_KK.png`, fora do git), e outra pessoa revisa.
A caixa é relativa (0–1) à página **original**, antes de endireitar, para o gabarito
não depender do endireitamento.

O texto dos livros tem direito autoral: os gabaritos e as faixas ficam no computador
do usuário e fora de qualquer publicação.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

VERDADE = RAIZ / "tests" / "verdade"
FAIXAS = RAIZ / ".rotulagem"
#: Onde estão os PDFs dos livros de referência (os do PyBoxEditor, por padrão).
PASTA_DOS_PDFS = Path(os.environ.get("ABBY_PASTA_DOS_PDFS",
                                     "C:/Python-Chess2/PyBoxEditor_Tkinter/PDF"))
LINHAS_POR_FAIXA = 7
#: A concordância mínima da conferência cega do texto (SPEC §15.2).
CONCORDANCIA_MINIMA = 0.995

FUNCOES = {"texto", "titulo", "cabecalho", "rodape", "numero_de_pagina", "nota", "legenda",
           "diagrama", "figura", "tabela", "ignorar"}


def sha256_do_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _indices(texto: str):
    saida = []
    for parte in texto.split(","):
        a, _, b = parte.partition("-")
        saida.extend(range(int(a), int(b or a) + 1))
    return saida


# ----------------------------------------------------------------------
# Rascunho
# ----------------------------------------------------------------------

def _caixa_relativa(caixa, angulo, largura, altura):
    """A caixa da página endireitada levada à original, relativa a 0–1."""
    from abbychess import pagina as pg

    x1, y1, x2, y2 = caixa
    if angulo:
        cx, cy = pg.ponto_original((x1 + x2) / 2, (y1 + y2) / 2, angulo, largura, altura)
        dx, dy = cx - (x1 + x2) / 2, cy - (y1 + y2) / 2
        x1, y1, x2, y2 = x1 + dx, y1 + dy, x2 + dx, y2 + dy
    return [round(x1 / largura, 5), round(y1 / altura, 5), round(x2 / largura, 5),
            round(y2 / altura, 5)]


def trabalho_humano(gabarito: dict) -> bool:
    """Se o gabarito já tem trabalho de alguém, que um rascunho novo apagaria."""
    return bool(int(gabarito.get("verdade_versao", 0) or 0) > 0 or gabarito.get("estrutura_por")
                or gabarito.get("rotulado_por") or gabarito.get("revisado_por")
                or any(ln.get("texto_verificado") for ln in gabarito.get("linhas_corpo", [])))


def _recusar_sobrescrever(destino: Path, indices, forcar: bool) -> None:
    """Antes de ler qualquer página: recusa, ou guarda `.bak`, o gabarito com trabalho."""
    for indice in indices:
        arquivo = destino / f"i{indice:03d}.json"
        if not arquivo.is_file():
            continue
        if not trabalho_humano(json.loads(arquivo.read_text(encoding="utf-8"))):
            continue
        if not forcar:
            raise SystemExit(f"{arquivo.name} já tem trabalho (estrutura, texto ou revisão): "
                             "o rascunho o apagaria. Use --forcar para refazê-lo; o atual "
                             "fica em .bak")
        arquivo.with_name(arquivo.name + ".bak").write_bytes(arquivo.read_bytes())


def rascunho(livro: str, pdf: Path, indices, *, com_modelos: bool = True,
             forcar: bool = False) -> list:
    _recusar_sobrescrever(VERDADE / livro, indices, forcar)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporaria:
        return _rascunho(livro, pdf, indices, Path(temporaria) / "padroes", com_modelos)


def _rascunho(livro: str, pdf: Path, indices, pasta: Path, com_modelos: bool) -> list:
    import fitz
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    from abbychess import diagramas as dg
    from abbychess import exportar as ex
    from abbychess import pagina as pg
    from abbychess.leitor import LeitorDoLivro

    leitor = (LeitorDoLivro.com_modelos_globais(pasta) if com_modelos else LeitorDoLivro(pasta))
    fonte = pg.FonteDePaginas(pdf, endireitar=True)
    sha = sha256_do_arquivo(pdf)
    lidos = {}
    for indice in indices:
        imagem = fonte.pagina(indice)
        segmentada = pg.segmentar_pagina(imagem, leitor)
        pg.ler_boxes(imagem, segmentada.boxes, leitor)
        for b in segmentada.boxes:
            if not b.char:
                b.char = "?"            # sem leitura: entra na linha, para a linha existir
        lidos[indice] = (imagem, segmentada)
    alturas = {i: lidos[i][0].height for i in indices}
    margens = ex.margens_corridas({i: (lidos[i][1].boxes, alturas[i]) for i in indices})

    gravados = []
    destino = VERDADE / livro
    destino.mkdir(parents=True, exist_ok=True)
    for indice in indices:
        imagem, segmentada = lidos[indice]
        original = np.asarray(fonte.original(indice).convert("L"))
        altura, largura = original.shape
        angulo = fonte.inclinacao(indice)
        boxes = segmentada.boxes
        linhas = ex._linhas(boxes)
        de_margem = margens[indice]
        tabuleiros = dg.em_ordem(segmentada.tabuleiros)
        diagramas = dg.ler_diagramas(imagem, tabuleiros, escala=None,
                                     classificar=leitor.arbitro, boxes=boxes)

        blocos, linhas_corpo = [], []
        for k, linha in enumerate(linhas):
            caixa = (min(boxes[i].x1 for i in linha.indices), linha.topo,
                     max(boxes[i].x2 for i in linha.indices), linha.pe)
            funcao = "cabecalho" if set(linha.indices) & de_margem else "texto"
            legenda_de = next((d for d, t in enumerate(tabuleiros)
                               if 0 <= linha.topo - t[3] <= 3 * (linha.pe - linha.topo)
                               and caixa[0] < t[2] and caixa[2] > t[0]), None)
            if funcao == "texto" and legenda_de is not None:
                funcao = "legenda"
            rel = _caixa_relativa(caixa, angulo, largura, altura)
            blocos.append({"id": f"b{k:02d}", "funcao": funcao, "caixa_rel": rel, "ordem": k,
                           "coluna": 0, "texto_impresso": linha.texto,
                           **({"diagrama": f"d{legenda_de}"} if funcao == "legenda" else {})})
            if funcao in ("texto", "legenda"):
                linhas_corpo.append({"id": f"l{k:02d}", "bloco": f"b{k:02d}", "caixa_rel": rel,
                                     "texto": linha.texto, "texto_verificado": False,
                                     "negrito": False})
        for d, (caixa, lido) in enumerate(zip(tabuleiros, diagramas)):
            blocos.append({"id": f"d{d}", "funcao": "diagrama",
                           "caixa_rel": _caixa_relativa(caixa, angulo, largura, altura),
                           "ordem": None, "coluna": 0, "texto_impresso": ""})
        gabarito = {
            "livro": livro, "pdf": pdf.name, "pdf_sha256": sha, "indice_pdf": indice,
            "pagina_impressa": None, "dpi_de_leitura": 300,
            "render_sha256": hashlib.sha256(original.tobytes()).hexdigest(),
            "pymupdf": fitz.VersionBind, "inclinacao": angulo,
            "papel": int(np.median(original[original > 200])) if (original > 200).any() else 255,
            "verdade_versao": 0, "estrutura_por": "", "rotulado_por": "",
            "revisado_por": "", "blocos": blocos,
            "diagramas": [{"id": f"d{d}", "fen": lido.fen.split(" ")[0] if lido.fen else "",
                           "fen_lido": lido.fen.split(" ")[0] if lido.fen else "",
                           "lado": lido.lado or "?", "legenda": next(
                               (b["id"] for b in blocos if b.get("diagrama") == f"d{d}"), None),
                           "lances_seguintes": [], "fen_verificado": False,
                           "lado_verificado": False}
                          for d, lido in enumerate(diagramas)],
            "linhas_corpo": linhas_corpo,
        }
        arquivo = destino / f"i{indice:03d}.json"
        arquivo.write_text(json.dumps(gabarito, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8", newline="\n")
        gravados.append(arquivo)
        _faixas(livro, indice, original, blocos, Image, ImageDraw, ImageFont)
        _recortes_dos_diagramas(livro, indice, original, blocos, Image)
    return gravados


def _faixas(livro, indice, original, blocos, Image, ImageDraw, ImageFont):
    """A página em faixas de ~7 linhas, com o id da linha na margem, para transcrever."""
    pasta = FAIXAS / livro / f"i{indice:03d}"
    pasta.mkdir(parents=True, exist_ok=True)
    altura, largura = original.shape
    texto = [b for b in blocos if b["funcao"] != "diagrama"]
    try:
        fonte = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        fonte = ImageFont.load_default()
    for n, inicio in enumerate(range(0, len(texto), LINHAS_POR_FAIXA)):
        grupo = texto[inicio:inicio + LINHAS_POR_FAIXA]
        y1 = max(0, int(min(b["caixa_rel"][1] for b in grupo) * altura) - 12)
        y2 = min(altura, int(max(b["caixa_rel"][3] for b in grupo) * altura) + 12)
        faixa = Image.fromarray(original[y1:y2]).convert("RGB")
        margem = Image.new("RGB", (90 + faixa.width, faixa.height), "white")
        margem.paste(faixa, (90, 0))
        desenho = ImageDraw.Draw(margem)
        for b in grupo:
            y = int(b["caixa_rel"][1] * altura) - y1
            desenho.text((4, y), b["id"], fill=(200, 0, 0), font=fonte)
        margem.save(pasta / f"faixa_{n:02d}.png")


def _recortes_dos_diagramas(livro, indice, original, blocos, Image):
    """Cada tabuleiro com folga e a legenda de baixo, para ler o FEN e o lado a olho."""
    pasta = FAIXAS / livro / f"i{indice:03d}"
    altura, largura = original.shape
    for b in blocos:
        if b["funcao"] != "diagrama":
            continue
        x1, y1, x2, y2 = b["caixa_rel"]
        folga = 0.04 * (x2 - x1)
        caixa = (max(0, int((x1 - folga) * largura)), max(0, int((y1 - folga) * altura)),
                 min(largura, int((x2 + folga) * largura)),
                 min(altura, int((y2 + 3 * folga) * altura)))
        Image.fromarray(original).crop(caixa).save(pasta / f"diagrama_{b['id']}.png")


# ----------------------------------------------------------------------
# Conferência e validação
# ----------------------------------------------------------------------

def levenshtein(a: str, b: str) -> int:
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        atual = [i]
        for j, cb in enumerate(b, start=1):
            atual.append(min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + (ca != cb)))
        anterior = atual
    return anterior[-1]


def concordancia(a: dict, b: dict) -> float:
    """1 − (distância de edição / caracteres), sobre o texto do corpo em ordem."""
    texto_a = "\n".join(ln["texto"] for ln in a["linhas_corpo"])
    texto_b = "\n".join(ln["texto"] for ln in b["linhas_corpo"])
    total = max(len(texto_a), len(texto_b), 1)
    return 1.0 - levenshtein(texto_a, texto_b) / total


LADOS = {"w", "b", "?"}


def problemas_do_fen(fen: str) -> str:
    """Vazio se a parte das peças tem 8 fileiras de 8 casas; senão, o motivo."""
    fileiras = (fen or "").split("/")
    if len(fileiras) != 8:
        return f"{len(fileiras)} fileira(s) em vez de 8"
    for n, fileira in enumerate(fileiras):
        casas = 0
        for c in fileira:
            if c.isdigit():
                casas += int(c)
            elif c in "KQRBNPkqrbnp":
                casas += 1
            else:
                return f"caractere {c!r} na fileira {8 - n}"
        if casas != 8:
            return f"a fileira {8 - n} tem {casas} casas"
    return ""


def _caixa_valida(caixa) -> bool:
    if not isinstance(caixa, list) or len(caixa) != 4:
        return False
    x1, y1, x2, y2 = caixa
    return 0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1


def validar(gabarito: dict, pdf: Path | None = None) -> list:
    problemas = []
    for chave in ("livro", "pdf_sha256", "indice_pdf", "verdade_versao", "rotulado_por",
                  "revisado_por", "blocos", "diagramas", "linhas_corpo", "papel"):
        if chave not in gabarito:
            problemas.append(f"falta a chave {chave}")
    blocos = gabarito.get("blocos", [])
    por_id = {}
    for b in blocos:
        if b.get("id") in por_id:
            problemas.append(f"id repetido {b.get('id')}")
        por_id[b.get("id")] = b
        if b.get("funcao") not in FUNCOES:
            problemas.append(f"{b.get('id')}: função desconhecida {b.get('funcao')!r}")
        if not _caixa_valida(b.get("caixa_rel")):
            problemas.append(f"{b.get('id')}: caixa_rel não é [x1, y1, x2, y2] dentro de 0–1")
    ordens = [b["ordem"] for b in blocos if b.get("ordem") is not None]
    if len(ordens) != len(set(ordens)):
        problemas.append("ordem repetida entre os blocos")
    linhas = gabarito.get("linhas_corpo", [])
    if len({ln.get("id") for ln in linhas}) != len(linhas):
        problemas.append("id repetido entre as linhas de corpo")
    for ln in linhas:
        if ln.get("bloco") not in por_id:
            problemas.append(f"{ln.get('id')}: o bloco {ln.get('bloco')!r} não existe")
        if not _caixa_valida(ln.get("caixa_rel")):
            problemas.append(f"{ln.get('id')}: caixa_rel não é [x1, y1, x2, y2] dentro de 0–1")
    for d in gabarito.get("diagramas", []):
        motivo = problemas_do_fen(d.get("fen", ""))
        if motivo:
            problemas.append(f"{d.get('id')}: FEN inválido ({motivo})")
        if d.get("lado") not in LADOS:
            problemas.append(f"{d.get('id')}: lado {d.get('lado')!r} não é w, b ou ?")
        if d.get("id") not in por_id or por_id[d.get("id")].get("funcao") != "diagrama":
            problemas.append(f"{d.get('id')}: falta o bloco de função diagrama com esse id")
        legenda = d.get("legenda")
        if legenda is not None and por_id.get(legenda, {}).get("funcao") != "legenda":
            problemas.append(f"{d.get('id')}: a legenda {legenda!r} não é um bloco de legenda")
    if pdf is not None and gabarito.get("pdf_sha256") != sha256_do_arquivo(pdf):
        problemas.append("pdf_sha256 não confere com o arquivo")
    return problemas


def refazer_faixas(livro: str, pdf: Path) -> int:
    """As faixas e recortes de novo, a partir do JSON atual (depois de dividir ou acrescentar)."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    from abbychess import pagina as pg

    fonte = pg.FonteDePaginas(pdf)
    feitas = 0
    for arquivo in sorted((VERDADE / livro).glob("i*.json")):
        gabarito = json.loads(arquivo.read_text(encoding="utf-8"))
        original = np.asarray(fonte.original(gabarito["indice_pdf"]).convert("L"))
        pasta = FAIXAS / livro / arquivo.stem
        for velho in pasta.glob("*.png"):
            velho.unlink()
        blocos = [b for b in gabarito["blocos"] if b["funcao"] != "ignorar"]
        _faixas(livro, gabarito["indice_pdf"], original, blocos, Image, ImageDraw, ImageFont)
        _recortes_dos_diagramas(livro, gabarito["indice_pdf"], original, blocos, Image)
        feitas += 1
    return feitas


def _ler_gabarito(arquivo: Path) -> dict:
    return json.loads(arquivo.read_text(encoding="utf-8"))


def _gravar_gabarito(arquivo: Path, gabarito: dict) -> None:
    arquivo.write_text(json.dumps(gabarito, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")


def _gabarito(livro: str, pagina: str) -> Path:
    arquivo = VERDADE / livro / f"{pagina}.json"
    if not arquivo.is_file():
        raise SystemExit(f"não há gabarito {arquivo.relative_to(VERDADE)}")
    return arquivo


def texto_exportar(livro: str, *, forcar: bool = False) -> list:
    """Um `.txt` por página em `.rotulagem/<livro>/`, `lNN<TAB>texto`, para o usuário corrigir.

    Um `.txt` mais novo que o gabarito é trabalho do usuário ainda não importado: não é
    sobrescrito, salvo com `forcar`. A conferência é feita em todas as páginas antes de
    gravar a primeira.
    """
    pares = []
    for arquivo in sorted((VERDADE / livro).glob("i*.json")):
        destino = FAIXAS / livro / f"{arquivo.stem}.txt"
        if (not forcar and destino.is_file()
                and destino.stat().st_mtime > arquivo.stat().st_mtime):
            raise SystemExit(f"{destino.name} é mais novo que o gabarito: importe-o antes "
                             "(texto-importar) ou use --forcar para descartá-lo")
        pares.append((arquivo, destino))
    gravados = []
    for arquivo, destino in pares:
        gabarito = _ler_gabarito(arquivo)
        linhas = [f"# {arquivo.stem}: corrija o texto depois do TAB; '!' no início deixa a "
                  "linha não verificada"]
        linhas += [f"{'' if ln.get('texto_verificado') else '!'}{ln['id']}\t{ln['texto']}"
                   for ln in gabarito["linhas_corpo"]]
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text("\n".join(linhas) + "\n", encoding="utf-8", newline="\n")
        gravados.append(destino)
    return gravados


def ler_txt(txt: Path) -> list:
    """As linhas `[!]lNN<TAB>texto` do arquivo, como (id, texto, verificada).

    Só `\\n` separa linhas (um U+2028 dentro do texto fica no texto), o `\\r` do Windows
    sai, e uma linha sem TAB é recusada em vez de zerar o texto.
    """
    saida = []
    for numero, bruta in enumerate(txt.read_text(encoding="utf-8").split("\n"), start=1):
        bruta = bruta.rstrip("\r")
        if not bruta.strip() or bruta.startswith("#"):
            continue
        if "\t" not in bruta:
            raise SystemExit(f"{txt.name}, linha {numero}: falta o TAB entre o id e o texto")
        id_, _, texto = bruta.lstrip("!").partition("\t")
        saida.append((id_, texto, not bruta.startswith("!")))
    return saida


def texto_importar(livro: str, por: str) -> dict:
    """Grava no gabarito o texto corrigido pelo usuário; devolve {página: linhas verificadas}.

    O texto de um bloco de várias linhas é o das linhas dele, em ordem, unidas por quebra
    de linha. Mudar o texto sobe `verdade_versao` e assina `rotulado_por`. Todos os `.txt`
    são lidos e conferidos antes de gravar o primeiro gabarito.
    """
    if not por.strip():
        raise SystemExit("diga quem verificou o texto: --por <nome>")
    lidos = []
    for txt in sorted((FAIXAS / livro).glob("i*.txt")):
        arquivo = _gabarito(livro, txt.stem)
        gabarito = _ler_gabarito(arquivo)
        ids = {ln["id"] for ln in gabarito["linhas_corpo"]}
        linhas = ler_txt(txt)
        for id_, _, _ in linhas:
            if id_ not in ids:
                raise SystemExit(f"{txt.name}: id desconhecido {id_!r}")
        lidos.append((txt, arquivo, gabarito, linhas))
    resultado = {}
    for txt, arquivo, gabarito, linhas in lidos:
        antes = json.dumps(gabarito["linhas_corpo"], ensure_ascii=False, sort_keys=True)
        por_id = {ln["id"]: ln for ln in gabarito["linhas_corpo"]}
        for id_, texto, marcada in linhas:
            por_id[id_]["texto"] = texto
            por_id[id_]["texto_verificado"] = marcada
        for bloco in gabarito["blocos"]:
            suas = [ln["texto"] for ln in gabarito["linhas_corpo"] if ln.get("bloco") == bloco["id"]]
            if suas:
                bloco["texto_impresso"] = "\n".join(suas)
        if json.dumps(gabarito["linhas_corpo"], ensure_ascii=False, sort_keys=True) != antes:
            gabarito["verdade_versao"] = int(gabarito.get("verdade_versao", 0)) + 1
            gabarito["rotulado_por"] = por
        _gravar_gabarito(arquivo, gabarito)
        resultado[txt.stem] = sum(1 for _, _, marcada in linhas if marcada)
    return resultado


# ----------------------------------------------------------------------
# Conferência cega e revisão
# ----------------------------------------------------------------------

def cego_modelo(livro: str, pagina: str) -> Path:
    """O `.txt` da conferência cega: os ids das linhas, com o texto em branco."""
    gabarito = _ler_gabarito(_gabarito(livro, pagina))
    destino = FAIXAS / livro / f"{pagina}.cego.txt"
    if destino.is_file():
        raise SystemExit(f"{destino.name} já existe: é a transcrição de alguém")
    linhas = [f"# {pagina}, conferência cega: escreva o texto de cada linha depois do TAB, "
              "olhando só as faixas"]
    linhas += [f"{ln['id']}\t" for ln in gabarito["linhas_corpo"]]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8", newline="\n")
    return destino


def _hoje() -> str:
    from datetime import date

    return date.today().isoformat()


def cego_texto(livro: str, pagina: str, txt: Path, por: str) -> float:
    """Compara a transcrição cega com o gabarito e grava o resultado nele."""
    if not por.strip():
        raise SystemExit("diga quem transcreveu: --por <nome>")
    arquivo = _gabarito(livro, pagina)
    gabarito = _ler_gabarito(arquivo)
    ids = [ln["id"] for ln in gabarito["linhas_corpo"]]
    transcrito = {id_: texto for id_, texto, _ in ler_txt(txt)}
    if set(transcrito) != set(ids):
        raise SystemExit(f"{txt.name}: as linhas não são as do gabarito "
                         f"(faltam {sorted(set(ids) - set(transcrito))}, "
                         f"sobram {sorted(set(transcrito) - set(ids))})")
    copia = {"linhas_corpo": [{"texto": transcrito[i]} for i in ids]}
    valor = concordancia(gabarito, copia)
    gabarito.setdefault("conferencia_cega", {})["texto"] = {
        "concordancia": round(valor, 5), "aprovada": valor >= CONCORDANCIA_MINIMA,
        "por": por, "data": _hoje(), "verdade_versao": gabarito.get("verdade_versao")}
    _gravar_gabarito(arquivo, gabarito)
    return valor


def cego_fen(livro: str, pagina: str, diagrama: str, fen: str, por: str) -> bool:
    """Compara o FEN montado às cegas com o do gabarito e grava o resultado no diagrama."""
    if not por.strip():
        raise SystemExit("diga quem montou o FEN: --por <nome>")
    pecas = fen.split(" ")[0]
    motivo = problemas_do_fen(pecas)
    if motivo:
        raise SystemExit(f"FEN inválido: {motivo}")
    arquivo = _gabarito(livro, pagina)
    gabarito = _ler_gabarito(arquivo)
    alvo = next((d for d in gabarito["diagramas"] if d["id"] == diagrama), None)
    if alvo is None:
        raise SystemExit(f"{pagina} não tem o diagrama {diagrama}")
    igual = pecas == alvo["fen"]
    alvo["conferencia_cega"] = {"igual": igual, "por": por, "data": _hoje()}
    if igual:
        alvo["fen_verificado"] = True
    _gravar_gabarito(arquivo, gabarito)
    return igual


def revisar(livro: str, pagina: str, por: str, *, fen=(), lado=()) -> dict:
    """Assina `revisado_por` e marca os FEN e lados conferidos pelo revisor."""
    if not por.strip():
        raise SystemExit("diga quem revisou: --por <nome>")
    arquivo = _gabarito(livro, pagina)
    gabarito = _ler_gabarito(arquivo)
    ids = {d["id"] for d in gabarito["diagramas"]}
    desconhecidos = (set(fen) | set(lado)) - ids
    if desconhecidos:
        raise SystemExit(f"{pagina} não tem os diagramas {sorted(desconhecidos)}")
    for d in gabarito["diagramas"]:
        if d["id"] in fen:
            d["fen_verificado"] = True
        if d["id"] in lado:
            d["lado_verificado"] = True
    gabarito["revisado_por"] = por
    _gravar_gabarito(arquivo, gabarito)
    return gabarito





def _lista(texto: str) -> list:
    return [p.strip() for p in (texto or "").split(",") if p.strip()]


def main(argv=None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = analisador.add_subparsers(dest="comando", required=True)
    r = sub.add_parser("rascunho")
    r.add_argument("--livro", required=True)
    r.add_argument("--pdf", required=True, type=Path)
    r.add_argument("--indices", required=True)
    r.add_argument("--sem-modelos", action="store_true")
    r.add_argument("--forcar", action="store_true",
                   help="refaz também gabaritos com trabalho (o atual fica em .bak)")
    te = sub.add_parser("texto-exportar")
    te.add_argument("--livro", required=True)
    te.add_argument("--forcar", action="store_true")
    ti = sub.add_parser("texto-importar")
    ti.add_argument("--livro", required=True)
    ti.add_argument("--por", required=True, help="quem verificou o texto")
    f = sub.add_parser("faixas")
    f.add_argument("--livro", required=True)
    f.add_argument("--pdf", required=True, type=Path)
    c = sub.add_parser("comparar")
    c.add_argument("a", type=Path)
    c.add_argument("b", type=Path)
    cm = sub.add_parser("cego-modelo", help="o .txt em branco da conferência cega")
    cm.add_argument("--livro", required=True)
    cm.add_argument("--pagina", required=True, help="iNNN")
    cg = sub.add_parser("cego", help="grava a conferência cega do texto ou de um FEN")
    cg.add_argument("--livro", required=True)
    cg.add_argument("--pagina", required=True, help="iNNN")
    cg.add_argument("--por", required=True)
    cg.add_argument("--txt", type=Path, help="a transcrição cega (de cego-modelo)")
    cg.add_argument("--diagrama", help="dN, com --fen")
    cg.add_argument("--fen")
    rv = sub.add_parser("revisar", help="assina revisado_por e marca FEN e lados conferidos")
    rv.add_argument("--livro", required=True)
    rv.add_argument("--pagina", required=True, help="iNNN")
    rv.add_argument("--por", required=True)
    rv.add_argument("--fen-verificado", default="", help="d0,d1: FEN conferidos casa a casa")
    rv.add_argument("--lado-verificado", default="", help="d0: lados conferidos")
    v = sub.add_parser("validar")
    v.add_argument("--livro", required=True)
    v.add_argument("--pdf", type=Path)
    args = analisador.parse_args(argv)
    if args.comando == "rascunho":
        for arquivo in rascunho(args.livro, args.pdf, _indices(args.indices),
                                com_modelos=not args.sem_modelos, forcar=args.forcar):
            print(arquivo.relative_to(RAIZ))
        return 0
    if args.comando == "faixas":
        print(f"{refazer_faixas(args.livro, args.pdf)} página(s)")
        return 0
    if args.comando == "texto-exportar":
        for arquivo in texto_exportar(args.livro, forcar=args.forcar):
            print(arquivo.relative_to(RAIZ))
        return 0
    if args.comando == "texto-importar":
        for pagina, n in texto_importar(args.livro, args.por).items():
            print(f"{pagina}: {n} linha(s) verificada(s)")
        return 0
    if args.comando == "comparar":
        a, b = (json.loads(p.read_text(encoding="utf-8")) for p in (args.a, args.b))
        valor = concordancia(a, b)
        print(f"concordância {valor:.4%}")
        return 0 if valor >= CONCORDANCIA_MINIMA else 1
    if args.comando == "cego-modelo":
        print(cego_modelo(args.livro, args.pagina).relative_to(RAIZ))
        return 0
    if args.comando == "cego":
        if args.txt is not None:
            valor = cego_texto(args.livro, args.pagina, args.txt, args.por)
            print(f"concordância {valor:.4%}")
            return 0 if valor >= CONCORDANCIA_MINIMA else 1
        if args.diagrama and args.fen:
            igual = cego_fen(args.livro, args.pagina, args.diagrama, args.fen, args.por)
            print("igual ao gabarito" if igual else "DIFERENTE do gabarito: confira os dois")
            return 0 if igual else 1
        analisador.error("cego pede --txt, ou --diagrama e --fen")
    if args.comando == "revisar":
        revisar(args.livro, args.pagina, args.por, fen=_lista(args.fen_verificado),
                lado=_lista(args.lado_verificado))
        print(f"{args.pagina}: revisado por {args.por}")
        return 0
    erros = 0
    for arquivo in sorted((VERDADE / args.livro).glob("i*.json")):
        problemas = validar(_ler_gabarito(arquivo), args.pdf)
        for p in problemas:
            print(f"{arquivo.name}: {p}")
        erros += len(problemas)
    return 1 if erros else 0


if __name__ == "__main__":
    raise SystemExit(main())
