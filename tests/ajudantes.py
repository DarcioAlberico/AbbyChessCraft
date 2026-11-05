"""O que os testes dividem e não é fixture (SPEC-qualidade Q-T2, Q-T5).

`esperar` é a espera única da suíte rápida: ela espera uma condição, e não um tempo; o
`time.sleep` dos testes rápidos é só o dela (o teste de `tests/test_suite.py` confere).
"""

from __future__ import annotations
import fitz
import io
import pytest
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QShortcut
from PySide6.QtWidgets import QApplication
from abbychess import atalhos, diagramas as dg, livro, pagina as pg, sessao as ss
from abbychess.app import teclado
from abbychess.app.janela import JanelaPrincipal
from abbychess.controlador import ControladorDePagina
from abbychess.leitor import FONTE_MANUAL, LeitorDoLivro
from abbychess.modelo import Box, Pagina, gid_de
from core import diagrama
from core.box_model import BoxEntry
from pathlib import Path
from tests.janela_util import boxes

import time
from typing import Callable, Optional


def esperar(condicao: Callable[[], object], limite: float = 20.0, *,
            a_cada: Optional[Callable[[], None]] = None) -> bool:
    """Espera `condicao()` valer, até `limite` segundos; devolve se valeu (o teste afirma).
    A cada volta, os eventos do Qt (se há uma aplicação) e `a_cada` (a fila da interface de
    um controlador sem janela, por exemplo)."""
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
    except ImportError:                                  # sem o Qt: só a condição
        app = None
    fim = time.monotonic() + limite
    while True:
        if a_cada is not None:
            a_cada()
        if app is not None:
            app.processEvents()
        if condicao():
            return True
        if time.monotonic() >= fim:
            return False
        time.sleep(0.005)


def _ate_valer(condicao, limite=20.0):
    assert esperar(condicao, limite)


def _ate(condicao, limite=10.0):
    assert esperar(condicao, limite)


def _pagina_lida(jb, *linhas):
    """A página escrita, gravada e no índice da busca."""
    pagina = _escrever(jb, *linhas)
    jb.projeto.salvar_modelo(pagina)
    jb.busca.abrir()
    _ate(jb.busca.pronto.is_set)
    return pagina


def _buscar(jb, texto, **marcas):
    b = jb.barra_de_busca
    jb.localizar()
    for nome, valor in marcas.items():
        getattr(b, nome).setChecked(valor)
    b.campo.setText(texto)
    b.contador.setText("")
    antes = jb.busca.ultimo_resultado
    b.relogio.stop()
    jb._buscar()
    _ate(lambda: jb.busca.ultimo_resultado is not antes or "erro" in b.contador.text())


class ExecutorManual:
    """Guarda as tarefas; `comecar()` roda o preparar e o trabalho da primeira e devolve o
    pronto com o resultado, para o teste chamar quando quiser."""

    def __init__(self):
        self.fila = []
        #: A tarefa começada cujo fim o teste ainda não chamou (e se ela é leve).
        self.em_voo = None

    def __call__(self, titulo, preparar, falhou=None, progresso=None, leve=False):
        self.fila.append((titulo, preparar, leve))

    def so_leves(self):
        return (self.em_voo is None or self.em_voo) and all(t[2] for t in self.fila)

    def comecar(self):
        titulo, preparar, leve = self.fila.pop(0)
        par = preparar()
        if par is None:
            return None
        trabalho, pronto = par
        resultado = trabalho(lambda *_: None)
        self.em_voo = leve

        def fim():
            self.em_voo = None
            pronto(resultado)
        return fim

    def tudo(self):
        while self.fila:
            fim = self.comecar()
            if fim is not None:
                fim()


def _controlador(projeto, executor):
    ctl = ControladorDePagina(executar=executor)
    ctl.ligar(projeto, pg.FonteDePaginas(projeto.fonte),
              LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    ctl.ir_para(0)
    return ctl


def _pronta(app, janela):
    janela.reconhecer()
    _esperar(app, janela)
    janela.show()
    janela.activateWindow()
    janela.visor.resetTransform()
    app.processEvents()
    return janela


FONTE_TTF = Path("C:/Windows/Fonts/arial.ttf")


#: Uma posição com roque possível dos dois lados.
FEN = "r3k2r/pp3ppp/2n5/3q4/3P4/2N2N2/PP3PPP/R3K2R"


sem_modelo = pytest.mark.skipif(not Path(diagrama.CAMINHO_MODELO).is_file()
                                or not Path(diagrama.CAMINHO_OCUPACAO).is_file(),
                                reason="os modelos de diagrama do PyBoxEditor não estão aqui")


def pagina_com_diagrama(caminho: Path, fen: str = FEN, legenda: str = "") -> Path:
    """Uma página com uma linha de texto, um tabuleiro de 400 px e outra linha."""
    from core import render_diagrama

    png, _l, _a = render_diagrama.desenhar(fen, lado_px=400, moldura="simples", tons=0)
    tabuleiro = Image.open(io.BytesIO(png)).convert("L")
    pagina = Image.new("L", (1000, 760), 255)
    desenho = ImageDraw.Draw(pagina)
    if not FONTE_TTF.exists():
        pytest.skip("a Arial não está nesta máquina")
    fonte = ImageFont.truetype(str(FONTE_TTF), 40)
    desenho.text((40, 30), "abc abc:", fill=0, font=fonte)
    pagina.paste(tabuleiro, (300, 110))
    if legenda:
        desenho.text((300, 110 + tabuleiro.size[1] + 30), legenda, fill=0, font=fonte)
    desenho.text((40, 680), "cab bca.", fill=0, font=fonte)
    pagina.save(caminho)
    return caminho


def _lido(fen: str = FEN, **campos) -> dg.DiagramaLido:
    from core.tabuleiro_edicao import TabuleiroEdicao

    casas = [diagrama.Casa(c.linha, c.coluna, c.simbolo, 0.99 if c.simbolo else 0.0,
                           confianca_ocupacao=0.999)
             for c in TabuleiroEdicao.de_fen(fen).casas]
    return dg.DiagramaLido(campos.pop("caixa", (300, 110, 704, 514)), casas=casas, **campos)


def _legenda(texto: str, x: int, topo: int, char: int = 10):
    """Uma linha de legenda: a maiúscula sobe acima das minúsculas, que têm 7 px."""
    boxes, cursor = [], x
    for c in texto:
        if c != " ":
            alto = c.isupper() or c.isdigit()
            boxes.append(BoxEntry(c, cursor, topo if alto else topo + char // 2 + 8,
                                  cursor + 10, topo + 2 * char, 1.0, FONTE_MANUAL))
        cursor += 14
    return boxes


_CAIXA = (100, 100, 500, 500)


def _escrever(j, *linhas, estados=None):
    """A página aberta com estas linhas, cada letra um box (0,9 de confiança, "net")."""
    p = j.pagina
    pagina = p._pagina_para_editar()
    boxes = []
    for k, linha in enumerate(linhas):
        x, y = 20, 20 + 60 * k
        for palavra in linha.split(" "):
            for letra in palavra:
                boxes.append(Box(pagina.alocar(), BoxEntry(letra, x, y, x + 18, y + 30, 0.9, "net")))
                x += 22
            x += 30
    pagina.boxes = boxes
    pagina.decisoes = type(pagina.decisoes)()
    pagina.tabuleiros, pagina.diagramas = [], []
    pagina.estado = "reconhecida"
    p.ir_para(0)
    j.pintar_texto()
    j.texto.setFocus()
    QApplication.processEvents()
    return pagina


RAIZ = Path(__file__).resolve().parent.parent


def _abrir(projeto, largura=1366, altura=768):
    j = JanelaPrincipal()
    j.resize(largura, altura)
    j.show()
    j.activateWindow()
    QApplication.processEvents()
    j.usar(projeto, pg.FonteDePaginas(projeto.fonte),
           LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    QApplication.processEvents()
    return j


def _esperado_do_yaml():
    """As ações com tecla até o passo, lidas do YAML sem passar por `abbychess.atalhos`."""
    import yaml

    bruto = yaml.safe_load((RAIZ / "docs" / "atalhos.yaml").read_text(encoding="utf-8"))
    passos = [str(x) for x in bruto["passos"]]
    limite = passos.index(teclado.PASSO)
    esperado = {}
    for item in bruto["acoes"]:
        sem = item.get("sem_atalho") or []
        sequencias = item.get(teclado.PERFIL) or item.get(bruto["perfis"][0])   # herda o padrão
        if (passos.index(str(item["desde_passo"])) <= limite and sequencias
                and teclado.PERFIL not in sem):
            lista = sequencias if isinstance(sequencias, list) else [sequencias]
            esperado[item["id"]] = ({atalhos.normalizar(str(x)) for x in lista}, item["escopo"])
    return esperado


def _widgets_do_escopo(janela):
    return {"imagem": {janela.visor}, "imagem_areas": {janela.visor}, "glifo": {janela.treino},
            "campo_glifo": {janela.treino.campo}, "palavra": {janela.verificacao},
            "documento": {janela.texto}, "galeria": {janela.galeria}, "diagrama": {janela.editor_diagrama}}


#: (ação, escopo) que só passam a valer depois (nenhum, desde que o Documento ficou editável
#: no D1).
_SO_DEPOIS_DA_EDICAO: set = set()


def conferir_os_registrados(janela):
    """As teclas da janela são as do YAML no perfil de agora (`teclado.PERFIL`); o perfil
    FineReader usa o mesmo em `tests/test_teclado.py`."""
    esperado = _esperado_do_yaml()
    por_escopo = _widgets_do_escopo(janela)
    registrados = {}
    for q in janela.findChildren(QAction):
        if not q.shortcuts():
            continue
        assert q.objectName() not in registrados, q.objectName()   # uma ação por id
        registrados[q.objectName()] = {teclado.do_qt(x) for x in q.shortcuts()}
        sequencias, escopo = esperado.get(q.objectName(), (None, None))
        assert escopo is not None, f"{q.objectName()} tem tecla e não está no YAML até o passo"
        if escopo == ["global"]:
            assert q.shortcutContext() == Qt.ShortcutContext.WindowShortcut, q.objectName()
        else:
            assert q.shortcutContext() == Qt.ShortcutContext.WidgetWithChildrenShortcut
            onde = set().union(*(por_escopo[e] for e in escopo
                                 if (q.objectName(), e) not in _SO_DEPOIS_DA_EDICAO))
            assert onde and onde <= set(q.associatedObjects()), (q.objectName(), escopo)
        assert q.receivers("2triggered(bool)") > 0, q.objectName()       # ligada a um comando
    assert registrados == {k: v for k, (v, _) in esperado.items()}
    assert janela.findChildren(QShortcut) == []           # nada fora do YAML


def _dentro(painel):
    foco = QApplication.focusWidget()
    return foco is not None and (foco is painel or painel.isAncestorOf(foco))


def _x_height_do_gabarito(matriz, verdade) -> float:
    """A x-height mediana das linhas do corpo do gabarito, em pixels da página: em cada
    linha, a faixa de linhas de pixels com mais da metade da tinta da mais cheia."""
    import statistics

    h, w = matriz.shape
    alturas = []
    for linha in verdade["linhas_corpo"]:
        x1, y1, x2, y2 = linha["caixa_rel"]
        perfil = (matriz[int(y1 * h):int(y2 * h), int(x1 * w):int(x2 * w)] < 128).sum(axis=1)
        if perfil.max():
            alturas.append(int((perfil > perfil.max() / 2).sum()))
    return statistics.median(alturas)


PROSA = ("The knight on d5 is strong and the bishop has no square. It is not easy for "
         "Black to defend the king, and White has a clear plan after the exchange of the "
         "queens on the long diagonal of the board.")


def _pdf_digital(caminho, paginas=2):
    doc = fitz.open()
    for numero in range(paginas):
        p = doc.new_page(width=480, height=680)
        p.insert_text((40, 60), f"Chapter {numero + 1}", fontname="hebo", fontsize=18)
        palavras = (PROSA + " " + PROSA).split()
        for k in range(0, len(palavras), 8):
            p.insert_text((40, 100 + 14 * (k // 8)), " ".join(palavras[k:k + 8]),
                          fontname="helv", fontsize=11)
    doc.save(caminho)
    doc.close()
    return caminho


def _esperar(app, janela, limite=20.0):
    assert esperar(lambda: not janela.executor.ocupado, limite), "a tarefa não terminou no prazo"
    app.processEvents()
    if janela.relogio_do_texto.isActive():          # o texto da página, sem esperar o relógio
        janela.pintar_texto()


def _ler_a_mao(app, janela):  # noqa: F811
    """Reconhece e dá aos glifos a leitura certa, como se a rede tivesse lido."""
    letras = list("abcabcabc" + "cabbca")
    janela.reconhecer()
    _esperar(app, janela)
    assert len(boxes(janela)) == len(letras)
    for b, c in zip(boxes(janela), letras):
        b.char, b.source, b.confidence = c, "neural", 0.99
    janela._glifos_mudaram()


P25 = "rnbqk2r/ppp3pp/3p1n2/8/2Bb1B2/5Q2/PPP3PP/4RR1K"


TEXTO_P25 = ("10...Rf8 11.Dd5??\nAs brancas ameaçam o mate e esperam que as pretas se\n"
             "entusiasmem por 11...Cxd5 12.Bxd6+ + Rg8 13.Bxd5+ Be6 14.Bxe6 xeque-mate.\n"
             "11...Dd7 12.Dxd4 Cc6")


PAGINAS = (("abc abc abc", "cab bca"), ("bca cab", "abc"), ("cba cba", "bac abc"))


def pdf_sintetico(pasta: Path, paginas=PAGINAS, *, camada_antiga: bool = False) -> Path:
    """Um PDF de imagens, uma página por grupo de linhas, como um livro digitalizado."""
    doc = fitz.open()
    for i, linhas in enumerate(paginas):
        caminho = _pagina_sintetica(pasta / f"p{i}.png", linhas)
        with Image.open(caminho) as imagem:
            largura, altura = imagem.size
        page = doc.new_page(width=largura * 72 / 300, height=altura * 72 / 300)
        page.insert_image(page.rect, filename=str(caminho))
        if camada_antiga:
            page.insert_text((5, 15), "hb7 lixo", fontsize=8, render_mode=3)
    destino = pasta / "livro.pdf"
    doc.save(destino)
    doc.close()
    return destino


def _ensinar_e_ler(projeto, fonte, leitor):
    imagem = fonte.pagina(0)
    boxes = pg.segmentar(imagem)
    for indice, char in enumerate("abc"):
        pg.ensinar(imagem, boxes, indice, char, leitor, projeto, pagina=0, propagar=False)
    livro.reconhecer_paginas(projeto, fonte, leitor, range(3), refazer=True)


FIXTURE = Path(__file__).parent / "dados" / "projeto_v1"


def _pagina(*linhas: str) -> Pagina:
    """Cada letra um box de 18 px (passo de 22 na palavra, 30 a mais entre palavras)."""
    boxes, n = [], 0
    for k, linha in enumerate(linhas):
        x, y = 20, 20 + 60 * k
        for palavra in linha.split(" "):
            for letra in palavra:
                boxes.append(Box(gid_de(1, n), BoxEntry(letra, x, y, x + 18, y + 30, 0.9, "net")))
                n += 1
                x += 22
            x += 30
    return Pagina(pid=1, indice=0, boxes=boxes, estado="reconhecida", proximo_n=n)


def _editar(pagina, de: str, para: str) -> ss.Plano:
    """Troca a primeira ocorrência de `de` (palavras inteiras) por `para`, como a vista faz:
    a sessão é a menor sequência de palavras que cobre o trecho."""
    texto, unidades = ss.texto_e_unidades(pagina)
    inicio = texto.index(de)
    a, b = ss.palavras_em(unidades, inicio, inicio + len(de))
    novo = texto[a:inicio] + para + texto[inicio + len(de):b]
    return ss.editar(pagina, unidades[a:b], novo)


def _pagina_sintetica(caminho: Path, linhas=("abc abc abc", "cab bca")) -> Path:
    imagem = Image.new("L", (900, 80 + 90 * len(linhas)), 255)
    desenho = ImageDraw.Draw(imagem)
    if not FONTE_TTF.exists():
        # Outra fonte daria outros glifos e outros números: o teste pula, não muda.
        pytest.skip("a Arial não está nesta máquina")
    fonte = ImageFont.truetype(str(FONTE_TTF), 56)
    for i, linha in enumerate(linhas):
        desenho.text((40, 40 + 90 * i), linha, fill=0, font=fonte)
    imagem.save(caminho)
    return caminho
