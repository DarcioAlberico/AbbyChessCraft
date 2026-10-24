"""A pré-visualização da exportação (SPEC §12.2, passo J): um HTML só, antes de gravar.

Sai do mesmo caminho da exportação (`exportar.paginas_do_projeto`, com as mesmas opções), e
não de uma montagem à parte: o texto de cada parágrafo é o mesmo do DOCX e do EPUB
(CA-12.4), com a marcação do EPUB (`epub.xhtml_do_texto`), e o relatório é o mesmo que a
exportação levaria a Resultados (CA-12.5). As imagens dos diagramas vão dentro do HTML
(`data:`), para a janela da prévia não depender de arquivo nenhum.

Num livro grande a prévia mostra as primeiras `LIMITE` páginas e diz quantas faltam; o
relatório cobre todas.
"""

from __future__ import annotations

import base64
import html
from typing import Sequence

from core.pagina import Figura, PaginaExtraida, Paragrafo

from abbychess import epub

#: Quantas páginas a prévia mostra (o relatório cobre todas).
LIMITE = 30

CSS = """
body { font-family: Georgia, serif; margin: 12px 16px; }
h1.previa { font-family: 'Segoe UI', sans-serif; font-size: 13pt; color: #555; }
div.relatorio { font-family: 'Segoe UI', sans-serif; font-size: 9pt; color: #333;
                background: #f4f4f4; padding: 6px 10px; }
div.pagina { font-family: 'Segoe UI', sans-serif; font-size: 8pt; color: #888;
             border-top: 1px solid #ccc; margin-top: 14px; padding-top: 2px; }
p.alt { font-family: 'Segoe UI', sans-serif; font-size: 8pt; color: #666; }
p.resto { font-style: italic; color: #888; }
"""


def _cabeca(titulo: str, idioma: str) -> str:
    return (f'<!DOCTYPE html><html lang="{html.escape(idioma, quote=True)}"><head>'
            f'<meta charset="utf-8"><title>{html.escape(titulo)}</title>'
            f"<style>{CSS}</style></head><body>"
            f'<h1 class="previa">Pré-visualização: {html.escape(titulo)}</h1>')


def _relatorio(linhas: Sequence[str]) -> str:
    itens = "".join(f"<li>{html.escape(linha)}</li>" for linha in linhas[1:])
    resumo = html.escape(linhas[0]) if linhas else ""
    return (f'<div class="relatorio"><p><b>Relatório:</b> {resumo}</p>'
            + (f"<ul>{itens}</ul>" if itens else "") + "</div>")


def html_do_livro(paginas: Sequence[PaginaExtraida], linhas_do_relatorio: Sequence[str],
                  titulo: str, idioma: str = "pt-BR", limite: int = LIMITE,
                  quebras: bool = False, realce: bool = False) -> str:
    """O HTML da prévia: o relatório, e as páginas com os títulos, os parágrafos (negrito e
    itálico como no EPUB) e os diagramas com o texto alternativo do EPUB embaixo."""
    msg = epub.mensagens(idioma)
    partes = [_cabeca(titulo, idioma), _relatorio(linhas_do_relatorio)]
    for pagina in paginas[:limite]:
        partes.append(f'<div class="pagina">{html.escape(msg["pagina"])} '
                      f"{pagina.numero + 1}</div>")
        for bloco in pagina.blocos:
            if isinstance(bloco, Figura):
                tipo, _ = epub.tipo_da_imagem(bloco.png)
                dados = base64.b64encode(bloco.png).decode("ascii")
                alt = epub.alternativo(bloco, msg, idioma)
                partes.append(f'<p><img src="data:{tipo};base64,{dados}" width="220" '
                              f'alt="{html.escape(alt, quote=True)}"></p>'
                              f'<p class="alt">{html.escape(alt)}</p>')
            elif isinstance(bloco, Paragrafo) and bloco.texto.strip():
                corpo = epub.xhtml_do_texto(bloco, "", quebras=quebras, realce=realce)
                if bloco.titulo:
                    nivel = 1 if bloco.nivel == 1 else 2
                    partes.append(f"<h{nivel + 1}>{corpo}</h{nivel + 1}>")
                else:
                    partes.append(f"<p>{corpo}</p>")
    if len(paginas) > limite:
        partes.append(f'<p class="resto">… e mais {len(paginas) - limite} página(s), que a '
                      "exportação inclui.</p>")
    partes.append("</body></html>")
    return "".join(partes)


def html_do_texto(texto: str, linhas_do_relatorio: Sequence[str], titulo: str,
                  idioma: str = "pt-BR") -> str:
    """A prévia de um arquivo de texto puro (o PGN): o relatório e o texto como sairá."""
    return (_cabeca(titulo, idioma) + _relatorio(linhas_do_relatorio)
            + f"<pre>{html.escape(texto)}</pre></body></html>")
