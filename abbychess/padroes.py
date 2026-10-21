"""Os padrões de um livro: vizinho mais próximo com a altura do glifo junto.

**Por que não o `CharacterLearner` do PyBoxEditor.** Ele compara recortes
esticados para 32×32, e o esticão apaga o tamanho: `o` e `O`, `c` e `C`, `l` e
`1` viram o mesmo desenho. Na base global isso é compensado depois, pela
geometria da linha. Aqui a correção tem de estar no próprio padrão, porque um
`o` ensinado não pode passar a ler todo `O` do livro. Medido no Darcy Lima
(p. 26 a 28), a altura do glifo dividida pela altura de referência da página
separa a família inteira:

    o 0,98   O 1,33   0 1,31   c 0,98   C 1,32   l 1,31   1 1,29

Então cada padrão guarda a sua altura relativa, e a leitura só aceita o vizinho
cuja altura esteja a até `TOLERANCIA_DE_ALTURA` da do glifo lido.

**O limiar de distância é outro que o da base global**, e também foi medido.
Num livro digitalizado as repetições da mesma letra variam com o papel e a
tinta. Com padrões da p. 26 lendo a p. 27 (1.712 glifos de referência), com a
trava de altura:

    distância   1 amostra/letra   3 amostras   5 amostras
    < 1.000           1 certo         26           33
    < 1.300         216 certos       326          397
    < 1.500         552 / 2 err      818 / 1      859 / 0
    < 1.700         853 / 5 err    1.041 / 1    1.064 / 0

1.500, que é confiança 0,25 na escala `1 - d/2000` do PyBoxEditor, cobre metade
da página seguinte com três amostras por letra e quase nenhum erro. O "erro" da
tabela é contra a leitura confiante da rede, que também erra, então é um teto.

**A proporção também vai na comparação.** O esticão para 32×32 apaga a
largura tanto quanto a altura: o hífen (12×4 px no Xadrez Vitorioso) e o
ponto (6×6) viram o mesmo quadrado preto, e com o hífen ensinado na p. 26 três
pontos das páginas seguintes saíram hífen; o travessão (27×5) lia o hífen do
`0-0`. A largura sobre a altura do glifo e a do padrão podem diferir até
`PROPORCAO_MAXIMA` vezes. Não precisa de metadado: o recorte é gravado no
tamanho original. Entre amostras do mesmo caractere ensinadas na p. 26 a
proporção varia até 1,6 vez (o "a" com e sem acento colado); entre o ponto e o
hífen, 1,7 a 3 vezes.

**Formato em disco.** Uma pasta por caractere (`core.learner.char_to_folder`),
o recorte no tamanho original e `metadados.json` com a altura relativa de cada
arquivo. É o formato da base global mais um arquivo, então uma amostra daqui
pode ser promovida para lá. A leitura e a gravação usam `np.fromfile` e
`cv2.imdecode`, que aceitam caminho com acento no Windows, ao contrário de
`cv2.imread`.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from core.learner import char_to_folder, folder_to_char

from abbychess import gravacao as gv

LADO = 32
METADADOS = "metadados.json"

#: Distância L2 entre recortes de 32×32 em 0..255 abaixo da qual o padrão
#: responde. Ver a tabela no docstring do módulo.
DISTANCIA_MAXIMA = 1500.0

#: Divisor da confiança, o mesmo `DISTANCIA_MAXIMA` da base global, para as duas
#: confianças falarem a mesma escala na fila de revisão.
ESCALA_DA_CONFIANCA = 2000.0

#: Diferença relativa de altura aceita entre o glifo e o padrão.
TOLERANCIA_DE_ALTURA = 0.20

#: Quantas vezes a proporção (largura / altura) do glifo e a do padrão podem
#: diferir. Ver o docstring do módulo.
PROPORCAO_MAXIMA = 1.6


def _efeito(valor) -> Optional[Tuple[bool, bool]]:
    """Normaliza o efeito conhecido para ``(negrito, italico)``.

    ``None`` significa que o efeito ainda não foi medido. Aceitar tanto o ``Estilo`` do
    modelo quanto uma sequência curta mantém este módulo independente do modelo da página.
    Sublinhado é uma decisão editorial, não um efeito de impressão reconhecido.
    """
    if valor is None:
        return None
    if hasattr(valor, "negrito"):
        return bool(valor.negrito), bool(valor.italico)
    itens = list(valor)
    return bool(itens[0]) if itens else False, bool(itens[1]) if len(itens) > 1 else False


@dataclass(frozen=True)
class Amostra:
    """Um padrão guardado inteiro, para o desfazer apagá-lo e o refazer devolvê-lo."""

    caminho: Path
    png: bytes
    meta: dict


@dataclass
class Resposta:
    char: str
    confianca: float
    distancia: float
    caminho: Optional[Path]


def _vetor(recorte: np.ndarray) -> np.ndarray:
    cinza = recorte if recorte.ndim == 2 else cv2.cvtColor(recorte, cv2.COLOR_RGB2GRAY)
    return cv2.resize(cinza, (LADO, LADO)).astype(np.float32).reshape(-1)


def _proporcao(imagem: np.ndarray) -> float:
    return imagem.shape[1] / max(1, imagem.shape[0])


def _ler_png(caminho: Path) -> Optional[np.ndarray]:
    dados = np.fromfile(str(caminho), dtype=np.uint8)
    return cv2.imdecode(dados, cv2.IMREAD_GRAYSCALE) if dados.size else None


def _nome_limpo(origem: str) -> str:
    limpo = "".join(c for c in origem if c.isascii() and (c.isalnum() or c in "-_"))
    return f"{limpo[:70]}_{uuid.uuid4().hex[:8]}" if limpo else uuid.uuid4().hex


def conflito_nas_distancias(distancias, chars, cabe, char: str, margem: float
                            ) -> Optional[Tuple[str, int, float]]:
    """O caractere diferente de `char` com mais amostras a menos de `margem` (no empate,
    a mais perto), quantas são e a maior distância delas; None se nenhuma."""
    perto: Dict[str, List[float]] = {}
    for d, c, ok in zip(distancias, chars, cabe):
        if ok and c != char and d <= margem:
            perto.setdefault(c, []).append(float(d))
    if not perto:
        return None
    outro = min(perto, key=lambda c: (-len(perto[c]), min(perto[c])))
    return outro, len(perto[outro]), max(perto[outro])


class PadroesDoLivro:
    """Os padrões ensinados para um livro, consultáveis assim que gravados."""

    def __init__(self, pasta: str | Path, *, distancia_maxima: float = DISTANCIA_MAXIMA,
                 tolerancia_de_altura: float = TOLERANCIA_DE_ALTURA):
        self.pasta = Path(pasta)        # a pasta nasce com o primeiro padrão (`gravacao`)
        self.distancia_maxima = distancia_maxima
        self.tolerancia_de_altura = tolerancia_de_altura
        self._carregar()

    # ------------------------------------------------------------------
    def _carregar(self) -> None:
        arquivo = self.pasta / METADADOS
        try:
            self._meta: Dict[str, dict] = (json.loads(arquivo.read_text(encoding="utf-8"))
                                           if arquivo.is_file() else {})
        except ValueError:
            self._meta = {}
        vetores, chars, alturas, proporcoes, efeitos, caminhos = [], [], [], [], [], []
        subpastas = self.pasta.iterdir() if self.pasta.is_dir() else ()
        for pasta in sorted(p for p in subpastas if p.is_dir()):
            char = folder_to_char(pasta.name)
            for png in sorted(pasta.glob("*.png")):
                imagem = _ler_png(png)
                if imagem is None:
                    continue
                vetores.append(_vetor(imagem))
                chars.append(char)
                proporcoes.append(_proporcao(imagem))
                meta = self._meta.get(self._chave(png), {})
                alturas.append(meta.get("altura", np.nan))
                efeitos.append(_efeito(meta.get("efeito")))
                caminhos.append(png)
        self._X = (np.stack(vetores) if vetores else np.zeros((0, LADO * LADO), np.float32))
        self._normas = (self._X * self._X).sum(axis=1)
        self._chars, self._caminhos = chars, caminhos
        self._alturas = np.array(alturas, dtype=np.float32)
        self._proporcoes = np.array(proporcoes, dtype=np.float32)
        self._efeitos = efeitos

    def _chave(self, caminho: Path) -> str:
        return caminho.relative_to(self.pasta).as_posix()

    def relativo(self, caminho) -> Optional[str]:
        """O caminho da amostra relativo à pasta dos padrões (a procedência gravada no `Box`)."""
        if caminho is None:
            return None
        try:
            return Path(caminho).resolve().relative_to(self.pasta.resolve()).as_posix()
        except ValueError:
            return Path(caminho).name

    def _gravar_meta(self) -> None:
        gv.gravar_json(self.pasta / METADADOS, self._meta)

    # ------------------------------------------------------------------
    @property
    def total(self) -> int:
        return len(self._chars)

    def ler(self, recorte: np.ndarray, altura_relativa: Optional[float] = None,
            efeito=None) -> Resposta:
        """O padrão mais próximo cuja altura combina, se estiver perto o bastante.

        Sem altura relativa (página sem referência) a trava de altura não roda.
        Padrão sem altura gravada também passa por ela sem ser barrado. A trava
        da proporção roda sempre.
        """
        if not self.total or recorte is None or recorte.size == 0:
            return Resposta("", 0.0, float("inf"), None)
        v = _vetor(recorte)
        d2 = self._normas + float(v @ v) - 2.0 * (self._X @ v)
        distancias = np.sqrt(np.maximum(d2, 0.0))
        candidatos = np.flatnonzero(distancias < self.distancia_maxima)
        if candidatos.size:
            razao = self._proporcoes[candidatos] / _proporcao(recorte)
            candidatos = candidatos[(razao <= PROPORCAO_MAXIMA) & (razao * PROPORCAO_MAXIMA >= 1.0)]
        if altura_relativa is not None and candidatos.size:
            alturas = self._alturas[candidatos]
            maior = np.maximum(alturas, altura_relativa)
            cabe = np.isnan(alturas) | (np.abs(alturas - altura_relativa)
                                        <= self.tolerancia_de_altura * maior)
            candidatos = candidatos[cabe]
        efeito = _efeito(efeito)
        if efeito is not None and candidatos.size:
            # Padrões antigos, sem efeito, continuam utilizáveis. Quando ambos os lados
            # são conhecidos, porém, pesos diferentes nunca chegam a ser vizinhos.
            candidatos = np.array([i for i in candidatos
                                   if self._efeitos[int(i)] in (None, efeito)], dtype=int)
        if not candidatos.size:
            return Resposta("", 0.0, float(distancias.min()), None)
        i = int(candidatos[np.argmin(distancias[candidatos])])
        d = float(distancias[i])
        return Resposta(self._chars[i], max(0.0, 1.0 - d / ESCALA_DA_CONFIANCA), d,
                        self._caminhos[i])

    def conflito(self, recorte: np.ndarray, char: str, altura_relativa: Optional[float],
                 margem: float) -> Optional[Tuple[str, int, float]]:
        """§8.3: o outro caractere de que o glifo está perto ao ser ensinado como `char`:
        (caractere, quantas amostras dele a menos de `margem`, a maior dessas distâncias),
        na escala `distância / ESCALA_DA_CONFIANCA`, com as travas de proporção e altura de
        `ler`; None sem conflito."""
        if not self.total or recorte is None or recorte.size == 0:
            return None
        v = _vetor(recorte)
        d2 = self._normas + float(v @ v) - 2.0 * (self._X @ v)
        distancias = np.sqrt(np.maximum(d2, 0.0)) / ESCALA_DA_CONFIANCA
        razao = self._proporcoes / _proporcao(recorte)
        cabe = (razao <= PROPORCAO_MAXIMA) & (razao * PROPORCAO_MAXIMA >= 1.0)
        if altura_relativa is not None:
            maior = np.maximum(self._alturas, altura_relativa)
            cabe &= np.isnan(self._alturas) | (np.abs(self._alturas - altura_relativa)
                                               <= self.tolerancia_de_altura * maior)
        return conflito_nas_distancias(distancias, self._chars, cabe, char, margem)

    def instantaneo(self) -> "PadroesDoLivro":
        """Os padrões de agora, para ler fora da thread da interface enquanto ela ensina
        (passo 2b): as matrizes são as mesmas (ensinar e esquecer as trocam, não as mudam no
        lugar) e as listas, cópias. Só para `ler`: não ensine nem esqueça nele."""
        foto = object.__new__(PadroesDoLivro)
        foto.pasta, foto._meta = self.pasta, self._meta
        foto.distancia_maxima, foto.tolerancia_de_altura = (self.distancia_maxima,
                                                            self.tolerancia_de_altura)
        foto._X, foto._normas = self._X, self._normas
        foto._chars, foto._caminhos = list(self._chars), list(self._caminhos)
        foto._alturas, foto._proporcoes = self._alturas, self._proporcoes
        foto._efeitos = list(self._efeitos)
        return foto

    def ensinar(self, recorte: np.ndarray, char: str, altura_relativa: Optional[float] = None,
                origem: str = "", efeito=None) -> Path:
        """Grava o recorte no tamanho original e o torna consultável na hora."""
        if not char:
            raise ValueError("O caractere ensinado não pode ser vazio.")
        cinza = recorte if recorte.ndim == 2 else cv2.cvtColor(recorte, cv2.COLOR_RGB2GRAY)
        pasta = self.pasta / char_to_folder(char)
        caminho = pasta / f"{_nome_limpo(origem)}.png"
        ok, png = cv2.imencode(".png", cinza)
        if not ok:
            raise OSError(f"O recorte de '{char}' não pôde ser codificado em PNG.")
        gv.gravar_bytes(caminho, png.tobytes())
        efeito = _efeito(efeito)
        self._meta[self._chave(caminho)] = {
            "altura": None if altura_relativa is None else round(float(altura_relativa), 4),
            "origem": origem,
            **({"efeito": [int(v) for v in efeito]} if efeito is not None else {}),
        }
        self._gravar_meta()
        v = _vetor(cinza)
        # Listas novas, e não `append`: um instantâneo (a propagação lendo noutra thread)
        # nunca vê a matriz de um tamanho e as listas de outro.
        self._X = np.vstack([self._X, v[None, :]])
        self._normas = np.append(self._normas, float(v @ v))
        self._chars = self._chars + [char]
        self._caminhos = self._caminhos + [caminho]
        self._proporcoes = np.append(self._proporcoes, np.float32(_proporcao(cinza)))
        self._alturas = np.append(self._alturas, np.float32(
            np.nan if altura_relativa is None else altura_relativa))
        self._efeitos = self._efeitos + [efeito]
        return caminho

    def esquecer(self, caminho: str | Path) -> None:
        caminho = Path(caminho).resolve()
        if self.pasta.resolve() not in caminho.parents:
            raise ValueError(f"{caminho} não é um padrão deste livro.")
        gv.apagar(caminho)
        self._meta.pop(caminho.relative_to(self.pasta.resolve()).as_posix(), None)
        self._gravar_meta()
        self._carregar()

    # ------------------------------------------------------------------
    # Os deltas do servidor de leitura (§11): a interface grava e esquece; o servidor só
    # passa a ler (ou a não ler) com a amostra, sem tocar no disco.
    # ------------------------------------------------------------------
    def incluir(self, caminho: str | Path, altura_relativa: Optional[float] = None,
                efeito=None) -> bool:
        """Passa a ler com a amostra já gravada em `caminho` (falso se o arquivo não abre)."""
        caminho = Path(caminho)
        if caminho in self._caminhos:
            return True
        imagem = _ler_png(caminho)
        if imagem is None:
            return False
        v = _vetor(imagem)
        self._X = np.vstack([self._X, v[None, :]])
        self._normas = np.append(self._normas, float(v @ v))
        self._chars = self._chars + [folder_to_char(caminho.parent.name)]
        self._caminhos = self._caminhos + [caminho]
        self._proporcoes = np.append(self._proporcoes, np.float32(_proporcao(imagem)))
        self._alturas = np.append(self._alturas, np.float32(
            np.nan if altura_relativa is None else altura_relativa))
        self._efeitos = self._efeitos + [_efeito(efeito)]
        return True

    def excluir(self, caminho: str | Path) -> None:
        """Deixa de ler com a amostra (o arquivo, quem apaga é a interface)."""
        caminho = Path(caminho)
        manter = [i for i, c in enumerate(self._caminhos) if Path(c) != caminho]
        if len(manter) == len(self._caminhos):
            return
        self._X = self._X[manter] if manter else np.zeros((0, LADO * LADO), np.float32)
        self._normas = self._normas[manter]
        self._chars = [self._chars[i] for i in manter]
        self._caminhos = [self._caminhos[i] for i in manter]
        self._proporcoes = self._proporcoes[manter]
        self._alturas = self._alturas[manter]
        self._efeitos = [self._efeitos[i] for i in manter]

    def altura_de(self, caminho: str | Path) -> Optional[float]:
        """A altura relativa gravada da amostra (para o delta que vai ao servidor)."""
        caminho = Path(caminho)
        try:
            altura = self._meta.get(self._chave(caminho), {}).get("altura")
        except ValueError:
            return None
        return None if altura is None else float(altura)

    def efeito_de(self, caminho: str | Path) -> Optional[Tuple[bool, bool]]:
        """O efeito de impressão gravado da amostra, para o delta do servidor."""
        try:
            return _efeito(self._meta.get(self._chave(Path(caminho)), {}).get("efeito"))
        except ValueError:
            return None

    def guardar(self, caminho: str | Path) -> Amostra:
        """O arquivo do padrão e os metadados dele, para voltar com `restaurar`."""
        caminho = Path(caminho).resolve()
        chave = caminho.relative_to(self.pasta.resolve()).as_posix()
        return Amostra(caminho, caminho.read_bytes(), dict(self._meta.get(chave, {})))

    def restaurar(self, amostra: Amostra) -> None:
        """Devolve um padrão apagado, com a altura gravada, e o torna consultável."""
        caminho = Path(amostra.caminho).resolve()
        if self.pasta.resolve() not in caminho.parents:
            raise ValueError(f"{caminho} não é um padrão deste livro.")
        gv.gravar_bytes(caminho, amostra.png)
        self._meta[caminho.relative_to(self.pasta.resolve()).as_posix()] = dict(amostra.meta)
        self._gravar_meta()
        self._carregar()

    def meta_de(self, caminho: str | Path) -> dict:
        """Os metadados gravados da amostra (a altura relativa, a origem; o efeito, desde o
        passo I), ou {}."""
        try:
            return dict(self._meta.get(self._chave(Path(caminho)), {}))
        except ValueError:
            return {}

    def por_caractere(self) -> Dict[str, List[Path]]:
        resultado: Dict[str, List[Path]] = {}
        for char, caminho in zip(self._chars, self._caminhos):
            resultado.setdefault(char, []).append(caminho)
        return resultado

    def amostras_de(self, char: str) -> List[Tuple[Path, Optional[float]]]:
        return [(c, None if np.isnan(a) else float(a))
                for ch, c, a in zip(self._chars, self._caminhos, self._alturas) if ch == char]
