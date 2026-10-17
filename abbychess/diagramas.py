"""Os diagramas da página: ler a posição, conferir e levar o FEN para o texto.

Sem Qt. A leitura é a do PyBoxEditor (`core.diagrama`): as duas redes, a de
ocupação e a das peças, sobre o resíduo de cada casa, com a legalidade como
árbitro; os rótulos `a`–`h` dizem a orientação quando o livro os imprime, e a
legenda em volta diz de quem é a vez quando diz (`core.lado_a_jogar`).

**O lado a jogar nunca é brancas em silêncio.** O FEN exige o campo e sai com
`w` quando ninguém disse, mas `lado` fica `None` e a linha do texto diz
"assumido: a página não diz". Só a legenda da página (`legenda`) ou quem
conferiu (`usuario`) afirmam um lado.

## O que a conferência vira

A correção casa a casa grava o FEN conferido na página, e ele não é relido:
reconhecer a página de novo mantém o diagrama conferido que ocupa o mesmo lugar
(`mesclar`). É a memória do livro para os diagramas.

**A correção não vira padrão de leitura do livro, e foi medido.** Um vizinho
mais próximo sobre o resíduo das casas, como o dos glifos, treinado nos
diagramas conferidos da p. 26 do Darcy Lima e testado no que ficou de fora:

| diagrama de teste | treino | casas certas | erradas |
|---|---|---:|---:|
| o das setas | 1 diagrama | 47 | 17 |
| o de cima | 2 diagramas | 58 | 6 |
| o do meio | 1 diagrama | 59 | 5 |

As distâncias das leituras erradas (a menor, 51,9) caem dentro das certas (até
83,2): não há limiar que separe. As redes do PyBoxEditor leram certos os dois
diagramas sem setas; trocar a leitura delas pelo vizinho do livro pioraria.
Por isso a conferência só **guarda** as amostras, e só na pasta do projeto
(`<projeto>/diagramas/`, no formato de `core.treino_diagrama`), para uma
promoção futura à base de diagramas. A base global não é tocada.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np

from core import diagrama_modelo as modelo
from core import lado_a_jogar
from core.box_model import BoxEntry
from core.tabuleiro_edicao import TabuleiroEdicao

Caixa = Tuple[int, int, int, int]

#: Procedências do lado a jogar. Vazio quer dizer que ninguém disse.
LADO_DA_LEGENDA = "legenda"
LADO_DO_USUARIO = "usuario"

#: A faixa em que uma linha de boxes encostada no tabuleiro conta como legenda
#: (`legendas_dos_boxes`), em alturas de referência da página
#: (`core.proporcao.altura_de_referencia`, a dos padrões do livro). Não é a
#: escala da segmentação, que no Xadrez Vitorioso vai de 28 a 38 px de uma
#: página para outra, com a mesma fonte; a altura de referência dá 27 nas cinco
#: páginas com diagrama. Ali, de 21 a 27, a legenda começa de 1,2 a 2,7 alturas
#: abaixo do tabuleiro, e a prosa mais perto fica a 4,6 ou mais, menos a do
#: Teste 1, a 2,7 acima ("Jogam as pretas. O que fazer?"), que diz o lado
#: daquele diagrama.
FAIXA_DA_LEGENDA = 3.5

#: Box mais alto que isto, em alturas de referência, não é letra de legenda.
ALTURA_MAXIMA_DA_LEGENDA = 2.5

#: Quanto duas caixas precisam se sobrepor para serem o mesmo diagrama.
SOBREPOSICAO_DO_MESMO = 0.5

#: As pastas das amostras colhidas na conferência, dentro do projeto.
PASTA_DE_DIAGRAMAS = "diagramas"

_FIM_DE_FRASE = re.compile(r"[.:!?…»”\"]\s*$")


@dataclass
class DiagramaLido:
    """Um diagrama da página: onde está, o que se leu e o que se conferiu."""

    caixa: Caixa
    #: As 64 casas, de a8 a h1. Vazia quando o diagrama não foi lido.
    casas: List[modelo.Casa] = field(default_factory=list)
    #: "w" ou "b" quando a legenda ou quem conferiu disse; `None` quando não.
    lado: Optional[str] = None
    lado_origem: str = ""
    #: O trecho da legenda que disse o lado, para quem confere poder julgar.
    lado_trecho: str = ""
    roque: str = ""
    #: Como o diagrama está impresso; as casas já vêm giradas para a posição.
    orientacao: str = "branca"
    #: Os rótulos impressos decidiram a orientação. Sem eles, é suposição.
    orientacao_confirmada: bool = False
    titulo: str = ""
    #: O título que o core releu em volta do tabuleiro; o lado sai dele quando a linha
    #: de boxes da legenda não diz (`rederivar_lado`).
    titulo_do_core: str = ""
    #: Os lados (`acima`, `abaixo`) em que o core achou os rótulos `a`–`h`: não são legenda.
    lados_de_rotulo: Tuple[str, ...] = ()
    conferido: bool = False
    #: Por que o porteiro do PyBoxEditor não confia na leitura; vazio se confia.
    motivo: str = ""
    #: Por que não deu para ler (modelo ausente, recorte ruim).
    erro: str = ""
    #: Estável na página (`d0`, `d1`…): é o que o documento cita (§4.2). Vazio até gravar.
    id: str = ""

    # ------------------------------------------------------------------
    @property
    def lido(self) -> bool:
        return len(self.casas) == 64

    @property
    def confiavel(self) -> bool:
        return self.lido and (self.conferido or not self.motivo)

    @property
    def fen(self) -> str:
        """O FEN da posição. Sem lado dito, o campo é `w` por exigência do formato."""
        if not self.lido:
            return ""
        return f"{self.leitura().tabuleiro().board_fen()} {self.lado or 'w'} {self.roque or '-'} - 0 1"

    def marca_do_lado(self) -> str:
        """`brancas a jogar (assumido: a página não diz)` e as outras procedências."""
        return lado_a_jogar.marca(self.lado, self.lado_origem if self.lado else "")

    def linha_de_texto(self, numero: int, *, com_ressalva: bool = True) -> str:
        """A linha do diagrama no texto reconhecido da página. `com_ressalva` falso tira o
        "não revisado" (o Documento mostra o estado à parte, §6.1)."""
        if not self.lido:
            motivo = self.erro or "ainda não lido"
            return f"[Diagrama {numero}: {motivo}]"
        ressalva = "" if self.conferido or not com_ressalva else f"; {lado_a_jogar.NAO_REVISADO}"
        return (f"[Diagrama {numero}: {self.fen}{lado_a_jogar.SEPARADOR_DO_ALT}"
                f"{self.marca_do_lado()}{ressalva}]")

    # ------------------------------------------------------------------
    def leitura(self) -> modelo.Leitura:
        """A `Leitura` do core, para o porteiro e o editor de posição."""
        casas = [replace(c) for c in self.casas]
        return modelo.Leitura(caixa=tuple(self.caixa), casas=casas, orientacao=self.orientacao,
                              lado_a_jogar=self.lado if self.lado_origem == LADO_DA_LEGENDA else None)

    def edicao(self) -> TabuleiroEdicao:
        """O tabuleiro editável do core, com o que já foi conferido."""
        tabuleiro = TabuleiroEdicao(self.leitura())
        for casa, gravada in zip(tabuleiro.casas, self.casas):
            casa.corrigida = gravada.corrigida
            casa.confianca_ocupacao = gravada.confianca_ocupacao
        if self.lado_origem == LADO_DO_USUARIO and self.lado in lado_a_jogar.LADOS:
            tabuleiro.lado, tabuleiro.lado_origem, tabuleiro.lado_informado = (
                self.lado, LADO_DO_USUARIO, True)
        if self.roque:
            tabuleiro.roque, tabuleiro.roque_informado = self.roque, True
        # O que veio gravado é o ponto de partida: não há o que desfazer antes dele.
        tabuleiro._historico = [tabuleiro._estado()]
        tabuleiro._indice = 0
        return tabuleiro

    def conferir(self, tabuleiro: TabuleiroEdicao, *, conferido: bool = True) -> "DiagramaLido":
        """Este diagrama com a posição, o lado e o roque do tabuleiro conferido."""
        casas = [modelo.Casa(c.linha, c.coluna, c.simbolo, c.confianca, c.arbitrada,
                             c.corrigida, getattr(c, "confianca_ocupacao", 0.0) or 0.0)
                 for c in tabuleiro.casas]
        dito = tabuleiro.lado_origem in (LADO_DA_LEGENDA, LADO_DO_USUARIO)
        return replace(self, casas=casas,
                       lado=tabuleiro.lado if dito else None,
                       lado_origem=tabuleiro.lado_origem if dito else "",
                       lado_trecho=self.lado_trecho if tabuleiro.lado_origem == LADO_DA_LEGENDA else "",
                       roque=tabuleiro.roque, conferido=conferido)

    # ------------------------------------------------------------------
    def para_json(self) -> dict:
        return {
            "id": self.id,
            "caixa": [int(v) for v in self.caixa],
            "fen": self.fen,
            "casas": [[c.simbolo or "", round(float(c.confianca), 4), bool(c.arbitrada),
                       bool(c.corrigida), round(float(c.confianca_ocupacao), 4)]
                      for c in self.casas],
            "lado": self.lado or "",
            "lado_origem": self.lado_origem,
            "lado_trecho": self.lado_trecho,
            "roque": self.roque,
            "orientacao": self.orientacao,
            "orientacao_confirmada": self.orientacao_confirmada,
            "titulo": self.titulo,
            "titulo_do_core": self.titulo_do_core,
            "lados_de_rotulo": list(self.lados_de_rotulo),
            "conferido": self.conferido,
            "motivo": self.motivo,
            "erro": self.erro,
        }

    @classmethod
    def de_json(cls, bruto: dict) -> "DiagramaLido":
        casas = []
        for i, (simbolo, confianca, arbitrada, corrigida, ocupacao) in enumerate(bruto.get("casas", [])):
            casas.append(modelo.Casa(i // 8, i % 8, simbolo or None, float(confianca),
                                     bool(arbitrada), bool(corrigida), float(ocupacao)))
        lado = bruto.get("lado") or None
        return cls(caixa=tuple(int(v) for v in bruto["caixa"]), casas=casas,
                   lado=lado if lado in lado_a_jogar.LADOS else None,
                   lado_origem=bruto.get("lado_origem", "") if lado else "",
                   lado_trecho=bruto.get("lado_trecho", ""),
                   roque=bruto.get("roque", ""),
                   orientacao=bruto.get("orientacao", "branca"),
                   orientacao_confirmada=bool(bruto.get("orientacao_confirmada", False)),
                   titulo=bruto.get("titulo", ""),
                   # Gravado antes do campo, o título é o que se tem do core.
                   titulo_do_core=bruto.get("titulo_do_core", bruto.get("titulo", "")),
                   lados_de_rotulo=tuple(bruto.get("lados_de_rotulo", ())),
                   conferido=bool(bruto.get("conferido", False)),
                   motivo=bruto.get("motivo", ""), erro=bruto.get("erro", ""),
                   id=str(bruto.get("id") or ""))


def com_ids(diagramas: Sequence[DiagramaLido]) -> List[DiagramaLido]:
    """Os diagramas com `id` cada um: os que não têm ganham o próximo `dN` livre."""
    usados = {d.id for d in diagramas if d.id}
    proximo, saida = 0, []
    for d in diagramas:
        if not d.id:
            while f"d{proximo}" in usados:
                proximo += 1
            d = replace(d, id=f"d{proximo}")
            usados.add(d.id)
        saida.append(d)
    return saida


def afirmar_lado(tabuleiro: TabuleiroEdicao, lado: str) -> bool:
    """Quem confere diz de quem é a vez, mesmo que seja o `w` que já estava lá.

    `TabuleiroEdicao.definir_lado` não faz nada quando o lado não muda, e o `w`
    da convenção continuaria convenção. Aqui ele vira informado por quem
    conferiu, com um passo no desfazer. Devolve se algo mudou.
    """
    if lado not in lado_a_jogar.LADOS:
        return False
    if tabuleiro.definir_lado(lado, LADO_DO_USUARIO):
        return True
    if tabuleiro.lado_origem == LADO_DO_USUARIO:
        return False
    tabuleiro.lado_origem, tabuleiro.lado_informado = LADO_DO_USUARIO, True
    tabuleiro._registrar()
    return True


# ----------------------------------------------------------------------
# Ler
# ----------------------------------------------------------------------

def ler_diagrama(imagem, caixa: Caixa, *, escala: Optional[float] = None, classificar=None,
                 boxes: Optional[Sequence[BoxEntry]] = None) -> DiagramaLido:
    """Lê um tabuleiro da página em FEN, com a orientação e o lado que a página disser.

    `classificar` é `(recorte) -> (char, confiança)`, o `LeitorDoLivro.arbitro`:
    lê os rótulos `a`–`h` e a legenda. Sem ele a orientação fica suposta e o
    lado, por dizer.
    """
    from core import diagrama

    arr = _cinza(imagem)
    caixa = tuple(int(v) for v in caixa)
    escala = escala or None
    try:
        rotulos = diagrama.ler_rotulos(arr, caixa, escala, classificar)
        leitura = diagrama.ler(arr, caixa, orientacao=rotulos.orientacao or "branca")
        titulo = diagrama.ler_titulo(arr, caixa, escala, classificar, boxes=boxes, rotulos=rotulos)
    except diagrama.ModeloAusente as erro:
        return DiagramaLido(caixa, erro=f"o modelo de diagramas não carregou ({erro})")
    if len(leitura.casas) != 64:
        motivo = next((a for a in leitura.avisos if a != diagrama.AVISO_CONVENCAO), "")
        return DiagramaLido(caixa, erro=motivo or "não deu para ler o tabuleiro")
    ok, motivo = diagrama.confiavel(leitura)
    lido = DiagramaLido(caixa, casas=leitura.casas, orientacao=leitura.orientacao,
                        orientacao_confirmada=rotulos.orientacao is not None,
                        titulo_do_core=titulo.texto, lados_de_rotulo=tuple(rotulos.lados),
                        motivo="" if ok else motivo)
    return _com_lado(lido, legendas_dos_boxes(boxes, caixa, rotulos.lados) if boxes else [])


def _com_lado(d: DiagramaLido, legendas: Sequence[str]) -> DiagramaLido:
    """O diagrama com o lado, a procedência, o trecho e o título que a página diz.

    As linhas da página valem mais que a releitura do core: trazem os padrões do
    livro e as correções do usuário (ver `legendas_dos_boxes`). Sem lado nelas,
    vale o título do core.
    """
    dito, titulo = lado_a_jogar.ler(d.titulo_do_core), d.titulo_do_core
    da_pagina = lado_a_jogar.ler_varios(*legendas) if legendas else None
    if da_pagina and da_pagina.lado:
        dito, titulo = da_pagina, " / ".join(legendas)
    dito = dito if dito and dito.lado else None
    return replace(d, lado=dito.lado if dito else None,
                   lado_origem=LADO_DA_LEGENDA if dito else "",
                   lado_trecho=dito.trecho if dito else "", titulo=titulo)


def rederivar_lados(diagramas: Sequence[DiagramaLido], antes: Sequence[BoxEntry],
                    depois: Sequence[BoxEntry]) -> List[DiagramaLido]:
    """Os diagramas com o lado dito de novo pela legenda, quando a linha dela mudou.

    Ensinar, corrigir, dividir ou juntar um box da legenda muda o que ela diz,
    e o lado não espera o F5 seguinte: sai das linhas de boxes de `depois`, sem
    reler o tabuleiro (só `lado`, `lado_origem`, `lado_trecho` e `titulo`). Só
    muda o diagrama cuja legenda mudou entre `antes` e `depois`; o conferido e o
    de lado informado por quem conferiu ficam como estão.
    """
    saida = []
    for d in diagramas:
        if d.lido and not d.conferido and d.lado_origem != LADO_DO_USUARIO:
            agora = legendas_dos_boxes(depois, d.caixa, d.lados_de_rotulo)
            if agora != legendas_dos_boxes(antes, d.caixa, d.lados_de_rotulo):
                d = _com_lado(d, agora)
        saida.append(d)
    return saida


def legendas_dos_boxes(boxes: Sequence[BoxEntry], caixa: Caixa,
                       lados_de_rotulo: Sequence[str] = (),
                       referencia: Optional[float] = None) -> List[str]:
    """O texto da linha de boxes encostada no tabuleiro, acima e abaixo.

    **Por que não basta o `core.diagrama.ler_titulo`.** Ele acha as marcas pela
    borda voltada para o tabuleiro, numa faixa de `FAIXA_EM_CARACTERES` vezes
    a escala da página, e relê cada recorte. No Xadrez Vitorioso a legenda
    ("Diagrama 6. Jogam as brancas.") começa logo abaixo da faixa: só o alto
    das maiúsculas entrava, e o título saía "Di7Jb"; a da p. 25 nem entrava.
    E a releitura do recorte cru não usa a altura do glifo nem o que o usuário
    ensinou ou corrigiu naqueles boxes.

    Aqui a faixa é a `FAIXA_DA_LEGENDA`, e ela só acha a linha: o box mais
    perto do tabuleiro com a borda na faixa a escolhe, e entram os boxes da
    linha dele, com os caracteres que já têm. Só contam os boxes com o centro
    dentro da largura do tabuleiro, para a legenda do diagrama vizinho, na
    mesma linha, ficar de fora. Os lados em que o core achou os rótulos `a`–`h`
    não são legenda. Devolve um texto por lado, acima primeiro.
    """
    from core import proporcao
    from core.notacao import texto_da_pagina as texto_dos_boxes

    x1, y1, x2, y2 = caixa
    referencia = (referencia or proporcao.altura_de_referencia(list(boxes))
                  or (y2 - y1) / 16.0)
    faixa = referencia * FAIXA_DA_LEGENDA
    na_largura = [b for b in boxes if b.char and x1 <= (b.x1 + b.x2) / 2 <= x2
                  and b.y2 - b.y1 <= referencia * ALTURA_MAXIMA_DA_LEGENDA]
    textos = []
    for lado in ("acima", "abaixo"):
        if lado in lados_de_rotulo:
            continue
        if lado == "acima":
            perto = [(y1 - b.y2, b) for b in na_largura if y1 - faixa <= b.y2 <= y1]
        else:
            perto = [(b.y1 - y2, b) for b in na_largura if y2 <= b.y1 <= y2 + faixa]
        if not perto:
            continue
        semente = min(perto, key=lambda par: par[0])[1]
        linha = [b for b in na_largura if semente.y1 <= (b.y1 + b.y2) / 2 <= semente.y2]
        texto = texto_dos_boxes(linha).strip()
        if texto:
            textos.append(texto)
    return textos


def ler_diagramas(imagem, tabuleiros: Sequence[Caixa], *, escala: Optional[float] = None,
                  classificar=None, boxes: Optional[Sequence[BoxEntry]] = None
                  ) -> List[DiagramaLido]:
    """Todos os tabuleiros da página, de cima para baixo (`em_ordem`)."""
    arr = _cinza(imagem)
    return [ler_diagrama(arr, caixa, escala=escala, classificar=classificar, boxes=boxes)
            for caixa in em_ordem(tabuleiros)]


def em_ordem(caixas: Sequence[Caixa]) -> List[Caixa]:
    """As caixas de cima para baixo e, na mesma altura, da esquerda para a direita.

    É a numeração do texto ("Diagrama 1") e a da conferência. A ordem em que o
    `core.diagrama.localizar` os acha não é a de leitura: na p. 26 do Darcy
    Lima ele dá primeiro o diagrama de baixo.
    """
    return sorted((tuple(int(v) for v in c) for c in caixas), key=lambda c: (c[1], c[0]))


def mesclar(novos: Sequence[DiagramaLido], antigos: Sequence[DiagramaLido]) -> List[DiagramaLido]:
    """Os diagramas relidos, com o conferido de antes onde ele ocupa o mesmo lugar.

    Reconhecer a página de novo não pode desfazer uma conferência: o FEN
    corrigido à mão vale mais que a releitura do mesmo tabuleiro.
    """
    saida = []
    for novo in novos:
        igual = next((a for a in antigos if a.conferido
                      and _sobreposicao(a.caixa, novo.caixa) >= SOBREPOSICAO_DO_MESMO), None)
        saida.append(replace(igual, caixa=novo.caixa) if igual is not None else novo)
    return saida


def diagrama_em(diagramas: Sequence[DiagramaLido], x: float, y: float) -> Optional[int]:
    """O índice do diagrama que contém o ponto da página, ou `None`."""
    for i, d in enumerate(diagramas):
        x1, y1, x2, y2 = d.caixa
        if x1 <= x <= x2 and y1 <= y <= y2:
            return i
    return None


def para_caixas(tabuleiros: Sequence[Caixa], diagramas: Sequence[DiagramaLido]
                ) -> List[DiagramaLido]:
    """Um diagrama por tabuleiro: os lidos onde há, e os por ler onde não há.

    Uma página gravada antes da leitura dos diagramas só tem as caixas; elas
    entram aqui como diagramas por ler, e a leitura vem no primeiro clique.
    """
    saida = []
    for caixa in em_ordem(tabuleiros):
        lido = next((d for d in diagramas
                     if _sobreposicao(d.caixa, caixa) >= SOBREPOSICAO_DO_MESMO), None)
        saida.append(replace(lido, caixa=caixa) if lido is not None else DiagramaLido(caixa))
    return saida


# ----------------------------------------------------------------------
# Amostras do livro
# ----------------------------------------------------------------------

def pasta_de_amostras(pasta_do_projeto: str | Path) -> Tuple[Path, Path]:
    """(peças, ocupação): onde a conferência guarda as amostras deste livro."""
    raiz = Path(pasta_do_projeto) / PASTA_DE_DIAGRAMAS
    return raiz / "pecas", raiz / "ocupacao"


def guardar_amostras(imagem, diagrama_lido: DiagramaLido, tabuleiro: TabuleiroEdicao,
                     pasta_do_projeto: str | Path, origem: str, *, tudo: bool = False) -> List[str]:
    """Guarda no projeto as casas conferidas, como amostras de peça e de ocupação.

    `tudo=False` guarda só as casas corrigidas à mão; `tudo=True`, as 64, que é
    o "conferi o diagrama inteiro". As pastas são sempre as do projeto: o
    `core.treino_diagrama.colher` gravaria na base global se elas faltassem.
    """
    from core import treino_diagrama

    pecas, ocupacao = pasta_de_amostras(pasta_do_projeto)
    caminhos = treino_diagrama.colher(_cinza(imagem), diagrama_lido.leitura(), tabuleiro,
                                      origem, tudo, pasta=str(pecas), pasta_ocupacao=str(ocupacao))
    return list(caminhos)


def amostras_guardadas(pasta_do_projeto: str | Path) -> int:
    pecas, ocupacao = pasta_de_amostras(pasta_do_projeto)
    return sum(1 for pasta in (pecas, ocupacao) if pasta.is_dir() for _ in pasta.rglob("*.png"))


# ----------------------------------------------------------------------
# O texto da página
# ----------------------------------------------------------------------

def texto_da_pagina(boxes: Sequence[BoxEntry], diagramas: Sequence[DiagramaLido]) -> str:
    """O texto da página com uma linha por diagrama, no lugar em que ele está.

    O diagrama entra antes da primeira linha que começa na altura dele ou
    abaixo, mas só num fim de frase: a linha anterior termina em ponto, dois
    pontos, exclamação ou interrogação. Assim o parágrafo que contorna o
    tabuleiro não é partido no meio, e "Veja a posição ao lado:" fica antes
    da posição. Sem fim de frase depois dele, o diagrama vai para o fim.

    A regra mora em `abbychess.texto.montar`; aqui é o modo `san`, como sempre foi.
    """
    from abbychess import texto as tx

    pagina = tx.pagina_avulsa(boxes, diagramas)
    return tx.texto(tx.montar(pagina), pagina.diagramas, modo=tx.SAN)


# ----------------------------------------------------------------------

def _cinza(imagem) -> np.ndarray:
    if hasattr(imagem, "convert"):
        return np.asarray(imagem.convert("L"))
    arr = np.asarray(imagem)
    return arr if arr.ndim == 2 else arr.mean(axis=2).astype(np.uint8)


def _sobreposicao(a: Sequence[int], b: Sequence[int]) -> float:
    """Interseção sobre a menor das duas áreas."""
    largura = min(a[2], b[2]) - max(a[0], b[0])
    altura = min(a[3], b[3]) - max(a[1], b[1])
    if largura <= 0 or altura <= 0:
        return 0.0
    menor = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return largura * altura / menor if menor > 0 else 0.0
