r"""A folha de conferência dos gabaritos: uma página HTML para revisar a estrutura e os FEN.

Uso:

    .venv\Scripts\python.exe ferramentas\folha_de_conferencia.py --livro xv
    .venv\Scripts\python.exe ferramentas\folha_de_conferencia.py --livro xv --paginas 20-26

Para cada gabarito (`tests/verdade/<livro>/iNNN.json`) a folha mostra a página original com
os blocos desenhados por cima (a cor é a função; o número, a ordem; a linha tracejada liga a
legenda ao diagrama dela), a tabela dos blocos em ordem com o que o `rotular.py validar`
acusa, e cada diagrama ao lado do tabuleiro desenhado pelo FEN do gabarito, com o lado e a
legenda. As caixas marcadas montam o comando `rotular.py revisar` da página.

A folha só lê: as correções continuam no JSON, e a assinatura pelo `revisar`. Ela é um arquivo
só, com as imagens dentro, em `.rotulagem/<livro>/conferencia/index.html` (fora do git, como as
faixas: o texto dos livros tem direito autoral), refeito do zero a cada vez.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))

from comum import PASTA_DOS_PDFS  # noqa: E402
from rotular import FAIXAS, VERDADE, _indices, validar  # noqa: E402

#: Largura da página na folha, em pixels (a original tem ~2.500 a 300 dpi).
LARGURA_DA_PAGINA = 1100

CORES = {
    "texto": "#4a6fa5", "titulo": "#8e44ad", "cabecalho": "#d35400", "rodape": "#a04000",
    "numero_de_pagina": "#795548", "nota": "#16a085", "legenda": "#2e8b57",
    "diagrama": "#1f5fd1", "figura": "#c2185b", "tabela": "#7d8b00", "ignorar": "#9e9e9e",
}
ABREVIADAS = {
    "texto": "txt", "titulo": "tít", "cabecalho": "cab", "rodape": "rod",
    "numero_de_pagina": "nº", "nota": "nota", "legenda": "leg", "diagrama": "diag",
    "figura": "fig", "tabela": "tab", "ignorar": "ign",
}


def _e(texto) -> str:
    return html.escape(str(texto), quote=True)


def avisos_do_diagrama(fen: str, lado: str) -> list:
    """O que salta aos olhos na posição: reis que faltam ou sobram, peão na 1ª ou 8ª, o lado
    que não joga em xeque. Não diz se o FEN é o do livro: isso só a imagem diz."""
    import chess

    try:
        tabuleiro = chess.BaseBoard(fen)
    except ValueError as erro:
        return [f"FEN que o python-chess recusa: {erro}"]
    avisos = []
    for cor, nome in ((chess.WHITE, "brancos"), (chess.BLACK, "pretos")):
        reis = len(tabuleiro.pieces(chess.KING, cor))
        if reis != 1:
            avisos.append(f"{reis} reis {nome}")
    if tabuleiro.pieces(chess.PAWN, chess.WHITE) & chess.BB_BACKRANKS or \
            tabuleiro.pieces(chess.PAWN, chess.BLACK) & chess.BB_BACKRANKS:
        avisos.append("peão na 1ª ou na 8ª fileira")
    if lado in ("w", "b") and not avisos:
        posicao = chess.Board(f"{fen} {lado} - - 0 1")
        if posicao.status() & chess.STATUS_OPPOSITE_CHECK:
            avisos.append("o lado que não joga está em xeque (o lado está errado?)")
    return avisos


def _tabuleiro_svg(fen: str) -> str:
    import chess
    import chess.svg

    try:
        return chess.svg.board(chess.BaseBoard(fen), size=300, coordinates=True)
    except ValueError:
        return '<div class="sem-tabuleiro">FEN inválido</div>'


def _diferenca_do_fen(fen: str, lido: str) -> str:
    """As casas em que o FEN do gabarito difere do lido pelo programa, em notação (a1…h8)."""
    import chess

    try:
        a, b = chess.BaseBoard(fen), chess.BaseBoard(lido)
    except ValueError:
        return ""
    casas = [chess.square_name(c) for c in chess.SQUARES if a.piece_at(c) != b.piece_at(c)]
    return ", ".join(casas)


def _sobreposicao(gabarito: dict, largura: int, altura: int) -> str:
    """O SVG dos blocos por cima da página, nas coordenadas relativas do gabarito."""
    proporcao = altura / largura
    w, h = 1000, 1000 * proporcao
    partes = [f'<svg class="sobre" viewBox="0 0 {w} {h:.1f}" preserveAspectRatio="none">']
    por_id = {b["id"]: b for b in gabarito["blocos"]}
    centros = []
    for b in sorted(gabarito["blocos"], key=lambda b: (b.get("ordem") is None, b.get("ordem") or 0)):
        x1, y1, x2, y2 = b["caixa_rel"]
        x1, x2, y1, y2 = x1 * w, x2 * w, y1 * h, y2 * h
        funcao = b.get("funcao", "?")
        cor = CORES.get(funcao, "#e53935")
        traco = ' stroke-dasharray="4 3"' if funcao == "ignorar" or b.get("caixa_estimada") else ""
        ordem = "" if b.get("ordem") is None else b["ordem"]
        dica = f'{b["id"]} · {funcao} · ordem {ordem}'
        if b.get("texto_impresso"):
            dica += f' — {b["texto_impresso"]}'
        partes.append(
            f'<g class="bloco f-{_e(funcao)}" data-id="{_e(b["id"])}"><title>{_e(dica)}</title>'
            f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{x2 - x1:.1f}" height="{y2 - y1:.1f}" '
            f'fill="{cor}" fill-opacity="0.10" stroke="{cor}" stroke-width="1.6"{traco}/>')
        rotulo = f'{ordem} {b["id"]} {ABREVIADAS.get(funcao, funcao)}'.strip()
        if x1 > 70:
            partes.append(f'<text class="rotulo" x="{x1 - 4:.1f}" y="{y1 + 9:.1f}" '
                          f'text-anchor="end" fill="{cor}">{_e(rotulo)}</text>')
        else:
            partes.append(f'<text class="rotulo" x="{x1 + 3:.1f}" y="{y1 + 9:.1f}" '
                          f'fill="{cor}">{_e(rotulo)}</text>')
        partes.append("</g>")
        if funcao != "ignorar" and b.get("ordem") is not None:
            centros.append(((x1 + x2) / 2, (y1 + y2) / 2))
    for b in gabarito["blocos"]:
        alvo = por_id.get(b.get("diagrama"))
        if b.get("funcao") == "legenda" and alvo:
            lx1, ly1, lx2, ly2 = b["caixa_rel"]
            dx1, dy1, dx2, dy2 = alvo["caixa_rel"]
            partes.append(
                f'<line class="ligacao" x1="{lx1 * w:.1f}" y1="{(ly1 + ly2) / 2 * h:.1f}" '
                f'x2="{(dx1 + dx2) / 2 * w:.1f}" y2="{(dy1 + dy2) / 2 * h:.1f}"/>')
    if len(centros) > 1:
        pontos = " ".join(f"{x:.1f},{y:.1f}" for x, y in centros)
        partes.append(f'<polyline class="ordem-de-leitura" points="{pontos}"/>')
    partes.append("</svg>")
    return "".join(partes)


def _tabela_dos_blocos(gabarito: dict) -> str:
    por_id = {b["id"]: b for b in gabarito["blocos"]}
    ordens = [b.get("ordem") for b in gabarito["blocos"] if b.get("ordem") is not None]
    repetidas = {o for o in ordens if ordens.count(o) > 1}
    linhas = []
    for b in sorted(gabarito["blocos"], key=lambda b: (b.get("ordem") is None, b.get("ordem") or 0)):
        funcao = b.get("funcao", "?")
        notas = []
        if b.get("ordem") in repetidas:
            notas.append("ordem repetida")
        if funcao == "legenda" and not b.get("diagrama"):
            notas.append("legenda sem diagrama")
        if b.get("diagrama") and por_id.get(b["diagrama"], {}).get("funcao") != "diagrama":
            notas.append(f'{b["diagrama"]} não é diagrama')
        if b.get("caixa_estimada"):
            notas.append("caixa estimada")
        ordem = "" if b.get("ordem") is None else b["ordem"]
        ligacao = f' → {_e(b["diagrama"])}' if b.get("diagrama") else ""
        linhas.append(
            f'<tr data-id="{_e(b["id"])}" class="f-{_e(funcao)}">'
            f'<td class="num">{_e(ordem)}</td><td class="id">{_e(b["id"])}</td>'
            f'<td><span class="ficha" style="--cor:{CORES.get(funcao, "#e53935")}">{_e(funcao)}'
            f'</span>{ligacao}</td><td class="num">{_e(b.get("coluna", ""))}</td>'
            f'<td class="texto">{_e(b.get("texto_impresso", ""))}</td>'
            f'<td class="nota">{_e("; ".join(notas))}</td></tr>')
    return ('<table class="blocos"><thead><tr><th>ordem</th><th>id</th><th>função</th>'
            '<th>col.</th><th>texto impresso</th><th>atenção</th></tr></thead><tbody>'
            + "".join(linhas) + "</tbody></table>")


def _cartao_do_diagrama(pagina: str, d: dict, gabarito: dict, recorte: str) -> str:
    por_id = {b["id"]: b for b in gabarito["blocos"]}
    legendas = [b.get("texto_impresso", "") for b in gabarito["blocos"]
                if b.get("funcao") == "legenda" and b.get("diagrama") == d["id"]]
    if not legendas and d.get("legenda") in por_id:
        legendas = [por_id[d["legenda"]].get("texto_impresso", "")]
    lado = {"w": "brancas jogam (w)", "b": "pretas jogam (b)"}.get(d.get("lado"), "não dito (?)")
    avisos = avisos_do_diagrama(d.get("fen", ""), d.get("lado", "?"))
    diferenca = ""
    if d.get("fen_lido") and d.get("fen_lido") != d.get("fen"):
        casas = _diferenca_do_fen(d["fen"], d["fen_lido"])
        diferenca = (f'<p class="aviso">O programa leu outro FEN: <code>{_e(d["fen_lido"])}</code>'
                     f'{f" (casas {_e(casas)})" if casas else ""}</p>')
    feito = []
    if d.get("fen_verificado"):
        feito.append("FEN já conferido")
    if d.get("lado_verificado"):
        feito.append("lado já conferido")
    lances = " ".join(d.get("lances_seguintes") or []) or "—"
    return f"""
<div class="diagrama">
 <figure><img src="{_e(recorte)}" alt="Recorte do diagrama {_e(d['id'])}">
  <figcaption>impresso</figcaption></figure>
 <figure>{_tabuleiro_svg(d.get('fen', ''))}<figcaption>pelo FEN do gabarito</figcaption></figure>
 <div class="dados">
  <h4>{_e(d['id'])}{' · ' + _e(', '.join(feito)) if feito else ''}</h4>
  <p><code class="fen">{_e(d.get('fen', ''))}</code></p>
  <p><b>Lado:</b> {_e(lado)}</p>
  <p><b>Legenda:</b> {_e(' / '.join(legendas) or '—')}</p>
  <p><b>Lances seguintes:</b> {_e(lances)}</p>
  {diferenca}
  {''.join(f'<p class="aviso">{_e(a)}</p>' for a in avisos)}
  <label><input type="checkbox" class="marca" data-pagina="{_e(pagina)}" data-tipo="fen"
   value="{_e(d['id'])}"{' checked' if d.get('fen_verificado') else ''}> FEN confere casa a casa</label>
  <label><input type="checkbox" class="marca" data-pagina="{_e(pagina)}" data-tipo="lado"
   value="{_e(d['id'])}"{' checked' if d.get('lado_verificado') else ''}> lado confere</label>
 </div>
</div>"""


def _embutida(imagem, formato: str) -> str:
    """A imagem dentro do HTML (`data:`): a folha é um arquivo só, que abre em qualquer lugar."""
    import base64
    import io

    dados = io.BytesIO()
    imagem.save(dados, formato, **({"quality": 85} if formato == "JPEG" else {}))
    tipo = "jpeg" if formato == "JPEG" else "png"
    return f"data:image/{tipo};base64,{base64.b64encode(dados.getvalue()).decode('ascii')}"


def _secao(arquivo: Path, gabarito: dict, fonte) -> str:
    import numpy as np

    pagina = arquivo.stem
    original = fonte.original(gabarito["indice_pdf"]).convert("L")
    render = hashlib.sha256(np.asarray(original).tobytes()).hexdigest()
    largura, altura = original.size
    reduzida = original.resize((LARGURA_DA_PAGINA, round(altura * LARGURA_DA_PAGINA / largura)))
    imagem_da_pagina = _embutida(reduzida, "JPEG")

    cartoes = []
    for d in gabarito.get("diagramas", []):
        bloco = next((b for b in gabarito["blocos"] if b["id"] == d["id"]), None)
        if bloco is None:
            continue
        x1, y1, x2, y2 = bloco["caixa_rel"]
        folga = 0.03 * (x2 - x1)
        caixa = (max(0, int((x1 - folga) * largura)), max(0, int((y1 - folga) * altura)),
                 min(largura, int((x2 + folga) * largura)), min(altura, int((y2 + folga) * altura)))
        recorte = _embutida(original.crop(caixa), "PNG")
        cartoes.append(_cartao_do_diagrama(pagina, d, gabarito, recorte))

    problemas = validar(gabarito)
    if render != gabarito.get("render_sha256"):
        problemas.insert(0, "a página renderizada hoje não é a do gabarito (render_sha256): "
                            "as caixas podem estar fora do lugar")
    impressa = gabarito.get("pagina_impressa")
    titulo = f"p. {impressa} ({pagina})" if impressa else pagina
    estado = []
    estado.append(f'revisado por {_e(gabarito["revisado_por"])}' if gabarito.get("revisado_por")
                  else "sem revisão")
    if gabarito.get("negativa"):
        estado.append("página negativa (sem corpo)")
    estado.append(f'verdade v{_e(gabarito.get("verdade_versao", 0))}')
    lista = ("".join(f"<li>{_e(p)}</li>" for p in problemas) if problemas
             else "<li class='ok'>o validar não acusa nada</li>")
    diagramas = (f'<h3>Diagramas</h3>{"".join(cartoes)}' if cartoes else "")
    return f"""
<section id="{_e(pagina)}" data-pagina="{_e(pagina)}">
 <h2>{_e(titulo)} <span class="estado">{' · '.join(estado)}</span></h2>
 <ul class="problemas">{lista}</ul>
 <div class="lado-a-lado">
  <div class="pagina"><img src="{imagem_da_pagina}" alt="Página {_e(pagina)}">
   {_sobreposicao(gabarito, largura, altura)}</div>
  <div class="tabela">{_tabela_dos_blocos(gabarito)}</div>
 </div>
 {diagramas}
 <div class="comando">
  <label><input type="checkbox" class="estrutura" data-pagina="{_e(pagina)}"> estrutura conferida</label>
  <pre><code data-comando="{_e(pagina)}"></code></pre>
  <button type="button" data-copiar="{_e(pagina)}">Copiar o comando</button>
 </div>
</section>"""


ESTILO = """
:root { --fundo:#f6f5f2; --papel:#fff; --tinta:#1d1d1f; --suave:#6b6b70; --linha:#dcdad5;
  --aviso:#b3261e; --ok:#2e7d32; }
* { box-sizing:border-box; }
body { margin:0; background:var(--fundo); color:var(--tinta);
  font:14px/1.45 "Segoe UI", system-ui, sans-serif; }
header { position:sticky; top:0; z-index:5; background:var(--papel); border-bottom:1px solid var(--linha);
  padding:10px 16px; display:flex; flex-wrap:wrap; gap:8px 18px; align-items:center; }
header h1 { font-size:16px; margin:0 12px 0 0; }
header nav a { margin-right:8px; color:var(--tinta); }
header label { color:var(--suave); }
header input[type=text] { font:inherit; padding:2px 6px; width:14em; }
.legenda-cores { display:flex; flex-wrap:wrap; gap:4px 10px; font-size:12px; }
main { padding:0 16px 48px; max-width:1900px; margin:0 auto; }
section { background:var(--papel); border:1px solid var(--linha); border-radius:8px; margin:18px 0;
  padding:12px 16px 16px; scroll-margin-top:110px; }
h2 { font-size:18px; margin:4px 0 6px; }
h2 .estado { font-size:13px; font-weight:400; color:var(--suave); }
h3 { font-size:15px; margin:18px 0 8px; }
h4 { margin:0 0 6px; font-size:14px; }
.problemas { margin:0 0 10px; padding-left:18px; color:var(--aviso); }
.problemas .ok { color:var(--ok); list-style:"✓ "; }
.lado-a-lado { display:grid; grid-template-columns:minmax(0, 3fr) minmax(420px, 2fr); gap:16px;
  align-items:start; }
@media (max-width:1100px) { .lado-a-lado { grid-template-columns:1fr; } }
.pagina { position:relative; border:1px solid var(--linha); }
.pagina img { display:block; width:100%; height:auto; }
.sobre { position:absolute; inset:0; width:100%; height:100%; }
.rotulo { font:600 8.5px "Segoe UI", sans-serif; paint-order:stroke; stroke:#fff; stroke-width:2.5px; }
body.sem-rotulos .rotulo, body.sem-ignorar .f-ignorar { display:none; }
.ligacao { stroke:#2e8b57; stroke-width:1.4; stroke-dasharray:3 3; }
.ordem-de-leitura { fill:none; stroke:#e53935; stroke-width:1; opacity:.7; display:none; }
body.com-ordem .ordem-de-leitura { display:inline; }
.bloco.realce rect { fill-opacity:.35; stroke-width:3; }
.tabela { max-height:1500px; overflow:auto; }
table.blocos { border-collapse:collapse; width:100%; font-size:13px; }
.blocos th { position:sticky; top:0; background:var(--papel); text-align:left;
  border-bottom:1px solid var(--linha); }
.blocos td, .blocos th { padding:3px 6px; vertical-align:top; }
.blocos tr:nth-child(even) td { background:#faf9f7; }
.blocos tr.realce td { background:#fff3c4; }
.blocos .num { text-align:right; font-variant-numeric:tabular-nums; }
.blocos .id { font-family:Consolas, monospace; }
.blocos .nota { color:var(--aviso); }
.blocos tr.f-ignorar td { color:var(--suave); }
.ficha { border-left:4px solid var(--cor); padding-left:5px; }
.diagrama { display:flex; flex-wrap:wrap; gap:16px; align-items:flex-start; padding:10px 0;
  border-top:1px solid var(--linha); }
.diagrama figure { margin:0; text-align:center; }
.diagrama figure img, .diagrama figure svg { width:300px; height:auto; display:block; }
.diagrama figcaption { color:var(--suave); font-size:12px; }
.dados { flex:1 1 320px; }
.dados p { margin:4px 0; }
.dados label { display:block; margin-top:6px; }
.fen { font-family:Consolas, monospace; font-size:13px; word-break:break-all; }
.aviso { color:var(--aviso); }
.comando { margin-top:14px; padding-top:10px; border-top:1px solid var(--linha); }
.comando pre { background:#1d1d1f; color:#f2f2f2; padding:8px 10px; border-radius:6px;
  white-space:pre-wrap; word-break:break-all; margin:6px 0; }
button { font:inherit; padding:4px 12px; cursor:pointer; }
"""

SCRIPT = r"""
const livro = document.body.dataset.livro;
const nome = document.getElementById('nome');
try { nome.value = localStorage.getItem('conferencia.nome') || ''; } catch (e) {}
function comando(pagina) {
  const marcadas = tipo => [...document.querySelectorAll(
    `.marca[data-pagina="${pagina}"][data-tipo="${tipo}"]:checked`)].map(c => c.value);
  const fen = marcadas('fen'), lado = marcadas('lado');
  const por = nome.value.trim() || 'Seu nome';
  let c = `.venv\\Scripts\\python.exe ferramentas\\rotular.py revisar --livro ${livro}`
    + ` --pagina ${pagina} --por "${por}"`;
  if (fen.length) c += ` --fen-verificado ${fen.join(',')}`;
  if (lado.length) c += ` --lado-verificado ${lado.join(',')}`;
  return c;
}
function atualizar() {
  document.querySelectorAll('[data-comando]').forEach(el => {
    const pagina = el.dataset.comando;
    const estrutura = document.querySelector(`.estrutura[data-pagina="${pagina}"]`).checked;
    el.textContent = estrutura ? comando(pagina)
      : '(marque "estrutura conferida" quando a estrutura da página estiver certa)';
  });
}
nome.addEventListener('input', () => {
  try { localStorage.setItem('conferencia.nome', nome.value); } catch (e) {}
  atualizar();
});
document.addEventListener('change', e => {
  if (e.target.matches('.marca, .estrutura')) atualizar();
  if (e.target.dataset.classe) document.body.classList.toggle(e.target.dataset.classe, e.target.checked);
});
document.addEventListener('click', e => {
  const pagina = e.target.dataset.copiar;
  if (!pagina) return;
  const texto = document.querySelector(`[data-comando="${pagina}"]`).textContent;
  navigator.clipboard.writeText(texto).then(() => {
    e.target.textContent = 'Copiado'; setTimeout(() => e.target.textContent = 'Copiar o comando', 1200);
  });
});
function realcar(secao, id, ligado) {
  secao.querySelectorAll(`[data-id="${id}"]`).forEach(el => el.classList.toggle('realce', ligado));
}
document.addEventListener('mouseover', e => {
  const alvo = e.target.closest('[data-id]');
  if (alvo) realcar(alvo.closest('section'), alvo.dataset.id, true);
});
document.addEventListener('mouseout', e => {
  const alvo = e.target.closest('[data-id]');
  if (alvo) realcar(alvo.closest('section'), alvo.dataset.id, false);
});
atualizar();
"""


def montar(livro: str, paginas=None, pdf: Path | None = None) -> Path:
    from abbychess import pagina as pg

    arquivos = sorted((VERDADE / livro).glob("i*.json"))
    if paginas is not None:
        arquivos = [a for a in arquivos if int(a.stem[1:]) in set(paginas)]
    if not arquivos:
        raise SystemExit(f"nenhum gabarito em {VERDADE / livro}")
    gabaritos = [(a, json.loads(a.read_text(encoding="utf-8"))) for a in arquivos]
    nome_do_pdf = gabaritos[0][1]["pdf"]
    pdf = pdf or next(PASTA_DOS_PDFS.rglob(nome_do_pdf), None)
    if pdf is None or not pdf.is_file():
        raise SystemExit(f"{nome_do_pdf} não está em {PASTA_DOS_PDFS}; passe --pdf ou defina "
                         "ABBY_PASTA_DOS_PDFS")
    pasta = FAIXAS / livro / "conferencia"
    pasta.mkdir(parents=True, exist_ok=True)
    for velho in pasta.glob("*"):
        if velho.suffix in (".jpg", ".png", ".html"):
            velho.unlink()
    fonte = pg.FonteDePaginas(pdf)
    secoes = [_secao(a, g, fonte) for a, g in gabaritos]
    indice = " ".join(
        f'<a href="#{_e(a.stem)}">{_e(g.get("pagina_impressa") or a.stem)}</a>' for a, g in gabaritos)
    cores = "".join(f'<span class="ficha" style="--cor:{c}">{_e(f)}</span>' for f, c in CORES.items())
    documento = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Conferência {_e(livro)}</title><style>{ESTILO}</style></head>
<body data-livro="{_e(livro)}">
<header>
 <h1>Conferência — {_e(livro)}</h1>
 <nav>{indice}</nav>
 <label>Seu nome <input type="text" id="nome" placeholder="para o --por"></label>
 <label><input type="checkbox" data-classe="sem-rotulos"> esconder rótulos</label>
 <label><input type="checkbox" data-classe="sem-ignorar"> esconder "ignorar"</label>
 <label><input type="checkbox" data-classe="com-ordem"> linha da ordem de leitura</label>
 <div class="legenda-cores">{cores}</div>
</header>
<main>{"".join(secoes)}
<section><h2>Depois de assinar todas</h2>
<pre><code>.venv\\Scripts\\python.exe ferramentas\\rotular.py validar --livro {_e(livro)}</code></pre>
<p>A folha não grava nada: corrija o JSON em <code>tests\\verdade\\{_e(livro)}\\</code>, rode
<code>folha_de_conferencia.py</code> de novo para ver a correção e assine pelo comando.</p></section>
</main><script>{SCRIPT}</script></body></html>
"""
    destino = pasta / "index.html"
    destino.write_text(documento, encoding="utf-8", newline="\n")
    return destino


def main(argv=None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    analisador.add_argument("--livro", required=True)
    analisador.add_argument("--paginas", help="índices do PDF, como 20-26 ou 0,7,20-26")
    analisador.add_argument("--pdf", type=Path, help="o PDF do livro, se não estiver na pasta dos PDFs")
    args = analisador.parse_args(argv)
    destino = montar(args.livro, _indices(args.paginas) if args.paginas else None, args.pdf)
    print(destino)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
