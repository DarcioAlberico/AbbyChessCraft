r"""O negrito e o itálico do OCR (`pagina.efeitos_da_pagina`) contra os da camada de texto de um
PDF, na página limpa e degradada como um livro escaneado.

    .venv\Scripts\python.exe ferramentas\medir_efeitos.py --pdf "<Odds & Ends.pdf>"
        [--ajuste 5-20,...] [--validacao 21-40,...] [--perfis limpo,escaneado,binario,ruim]
        [--folhas <pasta>] [--nome efeitos]

Cada glifo segmentado da página renderizada ganha o caractere e os rótulos do glifo da camada
que contém o centro dele: itálico e negrito pela bandeira da fonte ou pelo nome. No PDF
nascido digital (o Odds & Ends) os rótulos são exatos; na camada ClearScan de um livro
escaneado (o Karolyi), são o palpite do OCR do Acrobat, e a medida diz onde discordamos.

**Os perfis** degradam a página renderizada antes de segmentar, como o escâner a deixaria
(`degradar`): `limpo` não mexe; `escaneado` a passa por 220 dpi, borra, põe ruído, gira
0,3° e comprime em JPEG; `binario` é o escaneado em preto e branco (os scans de 1 bit);
`ruim` passa por 150 dpi, borra e gira mais. O rótulo segue o glifo pela transformação
inversa do giro.

**A conta é por palavra** (`core.notacao.palavras_da_pagina`), como a régua decide. Itálico:
as palavras de 3 letras ou mais com o rótulo igual em todas as letras. Negrito: as de 2 glifos
ou mais com o rótulo igual em todos (os lances em negrito contam). Com `--folhas`, uma imagem
por perfil com os falsos e os perdidos, para ver a olho.

Grava `docs/medidas/AAAA-MM-DD-<nome>.json`.
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))

from comum import destino_da_medida, estado_do_git  # noqa: E402
from medir_italico import AJUSTE, VALIDACAO, paginas  # noqa: E402

#: A regra do itálico pela fonte (`core.pdf_nativo._e_italico`, que é privado).
_ITALICO_NO_NOME = re.compile(r"(italic|oblique|kursiv|[-_,](bold|semibold|medium)?it(mt)?$)")
_NEGRITO_NO_NOME = re.compile(r"(bold|black|heavy|semibold|demibold|[-_,]bd$)")
_SUBCONJUNTO = re.compile(r"^[A-Z]{6}\+")


@dataclass(frozen=True)
class Perfil:
    """Como o escâner deixa a página: `dpi` de passagem (None: não reamostra), o borrão
    (sigma em pixels a 300 dpi), o ruído (desvio em tons de cinza), o giro em graus, a
    qualidade do JPEG (None: sem) e se ela vira preto e branco."""
    dpi: int | None = None
    borrao: float = 0.0
    ruido: float = 0.0
    giro: float = 0.0
    jpeg: int | None = None
    binaria: bool = False


PERFIS = {
    "limpo": Perfil(),
    "escaneado": Perfil(dpi=220, borrao=0.8, ruido=10, giro=0.3, jpeg=70),
    "binario": Perfil(dpi=220, borrao=0.8, ruido=10, giro=0.3, jpeg=None, binaria=True),
    "ruim": Perfil(dpi=150, borrao=1.2, ruido=18, giro=0.8, jpeg=50),
}

#: O DPI em que as páginas são renderizadas (o do projeto, `core.services.pdf_service`).
DPI_DA_PAGINA = 300


def degradar(imagem, perfil: Perfil, semente: int):
    """`(imagem degradada, matriz inversa)`: a matriz 2×3 leva um ponto da degradada à
    renderizada (o giro desfeito), para o rótulo da camada achar o glifo."""
    import cv2
    import numpy as np
    from PIL import Image

    tons = np.asarray(imagem.convert("L"), dtype=np.float32)
    altura, largura = tons.shape
    if perfil.dpi:
        fator = perfil.dpi / DPI_DA_PAGINA
        pequena = cv2.resize(tons, (max(1, round(largura * fator)), max(1, round(altura * fator))),
                             interpolation=cv2.INTER_AREA)
        tons = cv2.resize(pequena, (largura, altura), interpolation=cv2.INTER_LINEAR)
    if perfil.borrao:
        tons = cv2.GaussianBlur(tons, (0, 0), perfil.borrao)
    if perfil.ruido:
        tons = tons + np.random.default_rng(semente).normal(0, perfil.ruido, tons.shape)
    direta = cv2.getRotationMatrix2D((largura / 2, altura / 2), perfil.giro, 1.0)
    if perfil.giro:
        tons = cv2.warpAffine(tons, direta, (largura, altura), flags=cv2.INTER_LINEAR,
                              borderValue=255)
    tons = np.clip(tons, 0, 255).astype(np.uint8)
    if perfil.binaria:
        _, tons = cv2.threshold(tons, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    saida = Image.fromarray(tons)
    if perfil.jpeg:
        buffer = io.BytesIO()
        saida.save(buffer, "JPEG", quality=perfil.jpeg)
        saida = Image.open(io.BytesIO(buffer.getvalue())).convert("L")
    return saida, cv2.invertAffineTransform(direta)


#: O negrito falso: o mesmo glifo desenhado de novo a menos disto (em pontos) do primeiro. O
#: ChessBase imprime os lances da linha principal e o cabeçalho da partida assim, quatro
#: vezes com 0,24 pt de passo, numa fonte que se diz redonda (Odds & Ends, p. 75–86).
DESLOCAMENTO_DO_NEGRITO_FALSO = 1.0


def _glifos_da_camada(page) -> list:
    """`(x1, y1, x2, y2, char, italico, negrito)` dos glifos horizontais da camada, em pontos.
    O glifo repetido no mesmo lugar (`DESLOCAMENTO_DO_NEGRITO_FALSO`) é um negrito falso:
    conta uma vez, em negrito, com a caixa das cópias juntas."""
    brutos = []
    for bloco in page.get_text("rawdict")["blocks"]:
        for linha in bloco.get("lines", []):
            if tuple(linha["dir"]) != (1.0, 0.0):
                continue
            for span in linha["spans"]:
                nome = _SUBCONJUNTO.sub("", span["font"]).lower()
                italico = bool(span["flags"] & 2) or bool(_ITALICO_NO_NOME.search(nome))
                negrito = bool(span["flags"] & 16) or bool(_NEGRITO_NO_NOME.search(nome))
                for c in span["chars"]:
                    if c["c"].strip():
                        brutos.append((c["origin"], list(c["bbox"]), c["c"], italico, negrito))
    brutos.sort(key=lambda g: (g[2], round(g[0][1]), g[0][0]))
    saida, anterior = [], None
    for origem, caixa, char, italico, negrito in brutos:
        if anterior is not None and anterior[4] == char and \
                abs(origem[1] - anterior[7][1]) < DESLOCAMENTO_DO_NEGRITO_FALSO and \
                0 <= origem[0] - anterior[7][0] < DESLOCAMENTO_DO_NEGRITO_FALSO:
            anterior[0], anterior[1] = min(anterior[0], caixa[0]), min(anterior[1], caixa[1])
            anterior[2], anterior[3] = max(anterior[2], caixa[2]), max(anterior[3], caixa[3])
            anterior[6] = True
            anterior[7] = origem
            continue
        anterior = [*caixa, char, italico, negrito, origem]
        saida.append(anterior)
    return [tuple(g[:7]) for g in saida]


class _Conta:
    """A matriz de confusão de um efeito, com os exemplos dos erros (texto e caixa)."""

    def __init__(self):
        self.vp = self.fp = self.fn = self.vn = self.sem_medida = 0
        self.falsos, self.perdidos = [], []

    def somar(self, medido, certo, exemplo) -> None:
        if medido is None:
            self.sem_medida += 1
        elif medido and certo:
            self.vp += 1
        elif medido:
            self.fp += 1
            self.falsos.append(exemplo)
        elif certo:
            self.fn += 1
            self.perdidos.append(exemplo)
        else:
            self.vn += 1

    def resumo(self) -> dict:
        com, sem = self.vp + self.fn, self.fp + self.vn
        return {"com_o_efeito": com, "sem_o_efeito": sem, "verdadeiros": self.vp,
                "falsos": self.fp, "perdidos": self.fn, "sem_medida": self.sem_medida,
                "revocacao": round(self.vp / com, 4) if com else None,
                "precisao": round(self.vp / (self.vp + self.fp), 4) if self.vp + self.fp else None,
                "taxa_de_falsos": round(self.fp / sem, 5) if sem else None,
                "falsos_exemplos": [e[0] for e in self.falsos[:25]],
                "perdidos_exemplos": [e[0] for e in self.perdidos[:25]]}


def medir(pdf: Path, indices: list, perfil: Perfil) -> tuple:
    """`(resumo, contas)` do perfil nas páginas: o itálico e o negrito por palavra."""
    import fitz
    import numpy as np

    from abbychess import pagina as pg
    from core.notacao import palavras_da_pagina

    fonte = pg.FonteDePaginas(pdf)
    doc = fitz.open(pdf)
    italico, negrito = _Conta(), _Conta()
    tempos = []
    for indice in indices:
        renderizada = fonte.pagina(indice)
        imagem, inversa = degradar(renderizada, perfil, semente=indice)
        page = doc[indice]
        escala = renderizada.width / page.rect.width
        glifos = _glifos_da_camada(page)
        boxes = pg.segmentar(imagem)
        rotulos = []
        for b in boxes:
            cx, cy = inversa @ np.array([(b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2, 1.0])
            cx, cy = cx / escala, cy / escala
            achado = next((g for g in glifos if g[0] <= cx <= g[2] and g[1] <= cy <= g[3]), None)
            b.char = achado[4] if achado else ""
            rotulos.append(achado[5:] if achado else None)
        t0 = time.perf_counter()
        negritos, italicos = pg.efeitos_da_pagina(imagem, boxes)
        tempos.append((time.perf_counter() - t0) * 1000)
        cinza = np.asarray(imagem)
        for linha in palavras_da_pagina(boxes):
            for palavra in linha:
                todos = [s.indice for s in palavra.simbolos]
                if any(rotulos[i] is None for i in todos):
                    continue
                texto = "".join(boxes[i].char for i in todos)
                caixa = (min(boxes[i].x1 for i in todos), min(boxes[i].y1 for i in todos),
                         max(boxes[i].x2 for i in todos), max(boxes[i].y2 for i in todos))
                exemplo = (f"p{indice + 1} {texto}", (indice, caixa, cinza))
                letras = [i for i in todos if boxes[i].char.isalpha()]
                rotulo_i = {rotulos[i][0] for i in letras}
                if len(letras) >= 3 and len(rotulo_i) == 1:
                    italico.somar(italicos[letras[0]], rotulo_i.pop(), exemplo)
                rotulo_n = {rotulos[i][1] for i in todos}
                if len(todos) >= 2 and len(rotulo_n) == 1:
                    negrito.somar(negritos[todos[0]], rotulo_n.pop(), exemplo)
    tempos.sort()
    resumo = {"paginas": [i + 1 for i in indices], "italico": italico.resumo(),
              "negrito": negrito.resumo(),
              "ms_por_pagina_p50": round(tempos[len(tempos) // 2], 1) if tempos else None}
    return resumo, {"italico": italico, "negrito": negrito}


def folha(contas: dict, destino: Path, por_tipo: int = 40) -> None:
    """Uma imagem com os recortes dos falsos e dos perdidos de cada efeito, em faixas."""
    import numpy as np
    from PIL import Image, ImageDraw

    faixas = []
    for efeito, conta in contas.items():
        for nome, lista in (("falsos", conta.falsos), ("perdidos", conta.perdidos)):
            if not lista:
                continue
            faixas.append((f"{efeito} {nome} ({len(lista)})", None))
            for rotulo, (_indice, (x1, y1, x2, y2), cinza) in lista[:por_tipo]:
                recorte = cinza[max(0, y1 - 4):y2 + 4, max(0, x1 - 4):x2 + 4]
                faixas.append((rotulo, recorte))
    if not faixas:
        return
    largura = max([r.shape[1] for _, r in faixas if r is not None] + [200]) + 260
    altura = sum((r.shape[0] if r is not None else 24) + 6 for _, r in faixas)
    tela = Image.new("L", (largura, altura), 255)
    pincel = ImageDraw.Draw(tela)
    y = 0
    for rotulo, recorte in faixas:
        if recorte is None:
            pincel.text((4, y + 6), rotulo, fill=0)
            y += 30
            continue
        pincel.text((4, y + 2), rotulo[:36], fill=90)
        tela.paste(Image.fromarray(np.ascontiguousarray(recorte)), (256, y))
        y += recorte.shape[0] + 6
    tela.save(destino)


def main(argv=None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--pdf", type=Path, required=True)
    analisador.add_argument("--ajuste", default=AJUSTE)
    analisador.add_argument("--validacao", default=VALIDACAO)
    analisador.add_argument("--perfis", default="limpo,escaneado,binario,ruim")
    analisador.add_argument("--folhas", type=Path, help="a pasta das imagens dos erros")
    analisador.add_argument("--nome", default="efeitos", help="o nome-base do JSON")
    args = analisador.parse_args(argv)

    from abbychess import pagina as pg

    resultado = {
        "data": datetime.date.today().isoformat(), "git": estado_do_git(), "pdf": args.pdf.name,
        "regra": {"inclinacao_graus": pg.INCLINACAO_DO_ITALICO, "forca": pg.FORCA_DO_ITALICO,
                  "minimo_de_letras": pg.MINIMO_DE_LETRAS_DO_ITALICO,
                  "janela_graus": pg.JANELA_DO_ITALICO, "reta_ate_graus": pg.RETA_ATE},
        "perfis": {},
    }
    for nome in args.perfis.split(","):
        perfil = PERFIS[nome]
        resultado["perfis"][nome] = {"perfil": perfil.__dict__}
        for conjunto, texto in (("ajuste", args.ajuste), ("validacao", args.validacao)):
            if not texto:
                continue
            resumo, contas = medir(args.pdf, paginas(texto), perfil)
            resultado["perfis"][nome][conjunto] = resumo
            for efeito in ("italico", "negrito"):
                r = resumo[efeito]
                print(f"{nome:9s} {conjunto:9s} {efeito:7s}: {r['com_o_efeito']:5d} com, "
                      f"{r['sem_o_efeito']:6d} sem; revocação {r['revocacao']}, precisão "
                      f"{r['precisao']}, falsos {r['falsos']}, sem medida {r['sem_medida']}",
                      flush=True)
            if args.folhas:
                args.folhas.mkdir(parents=True, exist_ok=True)
                folha(contas, args.folhas / f"{args.nome}-{nome}-{conjunto}.png")
    destino = destino_da_medida(resultado["data"], args.nome)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
    print(destino)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
