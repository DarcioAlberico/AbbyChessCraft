"""O projeto de um livro: a fonte, os padrões treinados para ele e as páginas lidas.

Um projeto é uma pasta com esta forma::

    <pasta>/
        projeto.json      nome, caminho da fonte e o SHA-256 dela, idioma, limiares,
                          data de criação e, em `extras`, os campos que esta versão
                          não conhece
        livro.json        o resumo de cada página (estado, pendentes, histograma das
                          confianças, diagramas por conferir); cache, refeito se faltar
        padroes/          os padrões deste livro, uma pasta por caractere
        paginas/0001.json os boxes lidos e corrigidos de cada página, os tabuleiros
                          e, desde a leitura dos diagramas, o FEN de cada um
        diagramas/        as casas conferidas, guardadas como amostras deste livro
        zonas/0001.json   as áreas da página (texto, diagrama, imagem, ignorar)
        lexico.txt        as palavras que a verificação de texto aprendeu neste livro

As áreas ficam fora de `paginas/` de propósito: dá para desenhá-las antes do
primeiro reconhecimento, e uma página só com áreas não pode contar como lida.
Projetos sem `zonas/` nem `idioma` abrem como antes: sem áreas e em português.

Todo arquivo é gravado por `abbychess.gravacao` (temporário, `fsync`, troca). Um
projeto de versão mais nova abre só para leitura (`somente_leitura`): nada é
gravado nele. A fonte fica com caminho relativo quando está dentro da pasta do
projeto; se ela sumir, `abrir` procura o mesmo arquivo (pelo SHA-256 dos primeiros
4 MB e pelo tamanho) na pasta do caminho antigo, na do projeto e na pasta-mãe do
projeto, e senão `fonte_ausente` diz à janela que peça ao usuário (`relocalizar`).

`padroes/` usa o mesmo formato da base de treino do PyBoxEditor
(`core.learner.char_to_folder`) mais um `metadados.json` com a altura de cada
amostra (ver `abbychess.padroes`): uma amostra treinada aqui pode ser promovida
à base global sem conversão.

O nome da pasta do projeto é o nome do livro sem acentos nem símbolos. A pasta-mãe
pode ter acento: os padrões são lidos e gravados por `np.fromfile` e
`cv2.imdecode`, que aceitam esse caminho no Windows.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import threading
import unicodedata
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Tuple

from core.box_model import BoxEntry

from abbychess import gravacao as gv
from abbychess.zonas import Zona

if TYPE_CHECKING:
    from abbychess.diagramas import DiagramaLido

log = logging.getLogger(__name__)

ARQUIVO_DO_PROJETO = "projeto.json"
PASTA_DE_PADROES = "padroes"
PASTA_DE_PAGINAS = "paginas"
#: As páginas que só têm glifos marcados à mão no modo de treino, sem o F5.
ARQUIVO_DAS_MARCADAS = "marcadas.json"
PASTA_DE_ZONAS = "zonas"
ARQUIVO_DO_LEXICO = "lexico.txt"
ARQUIVO_DO_LIVRO = "livro.json"
VERSAO = 1
#: A versão do formato de `livro.json`; outra versão é refeita das páginas.
#: 2: a confiança 1,0 ganhou a faixa 100 do histograma (os caches v1 são refeitos).
VERSAO_DO_LIVRO = 2
#: Quanto da fonte entra no SHA-256 que a reconhece depois de movida.
BYTES_DO_SHA = 4 * 2**20
#: Quantos arquivos do tamanho certo, no máximo, `abrir` lê ao procurar a fonte sumida
#: (os de outro tamanho nem são lidos e não contam).
CANDIDATOS_DA_FONTE = 200

EXTENSOES_DE_IMAGEM = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


class ProjetoInvalido(ValueError):
    """O projeto não pode ser criado ou aberto, com o motivo para o usuário."""


@dataclass
class Limiares:
    """Quando cada elo da leitura é aceito, e quando o box vai para a revisão.

    As confianças seguem as escalas do PyBoxEditor. A do k-NN é `1 - d/2000`
    (`core.learner.DISTANCIA_MAXIMA`).
    A rede usa 0,80, o `NEURAL_THRESHOLD` da janela do PyBoxEditor, e a base
    global 0,30, o `LEARNER_THRESHOLD_NEURAL`.

    O do livro é 0,25, distância 1.500, e não os 0,50 da faixa da base global:
    num livro digitalizado as repetições da mesma letra ficam entre 900 e 1.400
    de distância umas das outras, e 0,50 deixava metade delas de fora. A tabela
    está em `abbychess.padroes`; a trava de altura de lá é o que impede o
    limiar mais largo de trocar `o` por `O`.
    """

    livro: float = 0.25
    rede: float = 0.80
    base: float = 0.30
    revisao: float = 0.90


@dataclass
class Projeto:
    nome: str
    fonte: str
    criado: str
    limiares: Limiares = field(default_factory=Limiares)
    #: O idioma da prosa, que escolhe o léxico da verificação de texto.
    idioma: str = "pt"
    versao: int = VERSAO
    #: O SHA-256 dos primeiros 4 MB da fonte e o tamanho dela, que a reconhecem se ela for
    #: movida (o tamanho separa dois arquivos de começo igual e evita ler os outros).
    fonte_sha256: str = ""
    fonte_tamanho: int = 0
    #: Os campos de `projeto.json` que esta versão não conhece. Não se perdem: ficam aqui
    #: e são regravados em `extras` (os de `limiares` em `extras["limiares"]`), onde uma
    #: versão futura que os entenda vai buscá-los.
    extras: Dict[str, object] = field(default_factory=dict)
    #: Endireitar cada página antes de ler (`pagina.medir_inclinacao`). Projeto
    #: novo nasce com isto; o que foi criado antes fica sem, porque os boxes
    #: gravados dele estão nas coordenadas da página torta.
    endireitar: bool = False


def sha_da_fonte(caminho: Path) -> str:
    """O SHA-256 dos primeiros `BYTES_DO_SHA` bytes do arquivo."""
    with open(caminho, "rb") as arquivo:
        return hashlib.sha256(arquivo.read(BYTES_DO_SHA)).hexdigest()


def _separar(bruto: dict, classe) -> Tuple[dict, dict]:
    """Os campos que `classe` conhece e os outros."""
    nomes = {f.name for f in fields(classe)}
    return ({k: v for k, v in bruto.items() if k in nomes},
            {k: v for k, v in bruto.items() if k not in nomes})


def nome_de_pasta(nome: str) -> str:
    """O nome do livro como nome de pasta só com ASCII, letras, dígitos e hífen."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    limpo = re.sub(r"[^A-Za-z0-9]+", "-", sem_acento).strip("-").lower()
    return limpo[:60] or "livro"


class ProjetoDeLivro:
    """Acesso a um projeto aberto: metadados, padrões e páginas."""

    def __init__(self, pasta: Path, dados: Projeto, *, somente_leitura: bool = False):
        self.pasta = Path(pasta)
        self.dados = dados
        #: Versão mais nova que a do programa: nada é gravado (`gravacao.SomenteLeitura`).
        self.somente_leitura = somente_leitura
        self._livro: Optional[dict] = None
        #: Uma gravação de página por vez (o lote grava de outra thread): a página,
        #: `marcadas.json` e `livro.json` mudam juntos, e o `.tmp` de cada um é um só.
        self._trava_do_livro = threading.RLock()
        self._travado = somente_leitura         # este objeto segura uma trava de só leitura
        #: A abertura achou a fonte noutro lugar, pelo SHA-256 (a janela avisa).
        self.fonte_relocalizada = False

    # ------------------------------------------------------------------
    # Criar e abrir
    # ------------------------------------------------------------------
    @classmethod
    def criar(cls, pasta_mae: str | Path, nome: str, fonte: str | Path) -> "ProjetoDeLivro":
        fonte = Path(fonte).resolve()
        if not fonte.is_file():
            raise ProjetoInvalido(f"A fonte não existe: {fonte}")
        if fonte.suffix.lower() != ".pdf" and fonte.suffix.lower() not in EXTENSOES_DE_IMAGEM:
            raise ProjetoInvalido(f"Formato não suportado: {fonte.suffix}. Use PDF ou imagem.")
        nome = nome.strip() or fonte.stem
        pasta = Path(pasta_mae).resolve() / nome_de_pasta(nome)
        if (pasta / ARQUIVO_DO_PROJETO).exists():
            raise ProjetoInvalido(f"Já existe um projeto em {pasta}.")
        (pasta / PASTA_DE_PADROES).mkdir(parents=True, exist_ok=True)
        (pasta / PASTA_DE_PAGINAS).mkdir(parents=True, exist_ok=True)
        dados = Projeto(nome=nome, fonte=_caminho_gravado(fonte, pasta),
                        criado=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        endireitar=True, fonte_sha256=sha_da_fonte(fonte),
                        fonte_tamanho=fonte.stat().st_size)
        projeto = cls(pasta, dados)
        projeto.salvar()
        return projeto

    @classmethod
    def abrir(cls, pasta: str | Path) -> "ProjetoDeLivro":
        pasta = Path(pasta).resolve()
        arquivo = pasta / ARQUIVO_DO_PROJETO
        if not arquivo.is_file():
            raise ProjetoInvalido(f"Não há {ARQUIVO_DO_PROJETO} em {pasta}.")
        try:
            bruto = json.loads(arquivo.read_text(encoding="utf-8"))
            if not isinstance(bruto, dict):
                raise ValueError("não é um objeto JSON")
            conhecidos, desconhecidos = _separar(bruto, Projeto)
            extras = dict(conhecidos.pop("extras", None) or {})
            dos_limiares, outros_limiares = _separar(conhecidos.pop("limiares", None) or {},
                                                     Limiares)
            if outros_limiares:
                extras["limiares"] = {**dict(extras.get("limiares") or {}), **outros_limiares}
            extras.update(desconhecidos)
            dados = Projeto(limiares=Limiares(**dos_limiares), extras=extras, **conhecidos)
            if not isinstance(dados.versao, int):
                raise ValueError(f"versão {dados.versao!r}")
        except (ValueError, TypeError) as erro:
            raise ProjetoInvalido(f"{arquivo} está ilegível: {erro}") from erro
        if dados.versao > VERSAO:
            projeto = cls(pasta, dados, somente_leitura=False)
            if projeto.fonte_ausente:
                achada = projeto._procurar_fonte()
                if achada is not None:          # só na memória: nada é gravado
                    dados.fonte, projeto.fonte_relocalizada = str(achada), True
            # A trava por último: uma falha antes dela não deixa a pasta travada sem dono.
            projeto.somente_leitura = projeto._travado = True
            gv.proteger(pasta)
            return projeto
        (pasta / PASTA_DE_PADROES).mkdir(exist_ok=True)
        (pasta / PASTA_DE_PAGINAS).mkdir(exist_ok=True)
        gv.limpar_temporarios(pasta)
        projeto = cls(pasta, dados)
        mudou = bool(desconhecidos or outros_limiares)
        if projeto.fonte.is_file():
            if not dados.fonte_sha256 or not dados.fonte_tamanho:
                dados.fonte_sha256 = sha_da_fonte(projeto.fonte)
                dados.fonte_tamanho, mudou = projeto.fonte.stat().st_size, True
        else:
            achada = projeto._procurar_fonte()
            if achada is not None:
                dados.fonte, mudou = _caminho_gravado(achada, pasta), True
                dados.fonte_tamanho = achada.stat().st_size
                projeto.fonte_relocalizada = True
        if mudou:
            try:
                projeto.salvar()
            except OSError as erro:     # mídia só de leitura: abre igual, sem gravar o ajuste
                log.warning("não deu para gravar %s ao abrir: %s", ARQUIVO_DO_PROJETO, erro)
        return projeto

    def fechar(self) -> None:
        """Solta a trava de só leitura que este objeto segura (uma vez só)."""
        if self._travado:
            self._travado = False
            gv.liberar(self.pasta)

    def salvar(self) -> None:
        gv.gravar_json(self.pasta / ARQUIVO_DO_PROJETO, asdict(self.dados))

    # ------------------------------------------------------------------
    # A fonte do livro
    # ------------------------------------------------------------------
    @property
    def fonte_ausente(self) -> bool:
        return not self.fonte.is_file()

    def relocalizar(self, caminho: str | Path) -> None:
        """A fonte foi movida para `caminho`: confere que é o mesmo arquivo e grava.

        Projeto antigo, sem o SHA-256 gravado, aceita o arquivo e passa a ter o dele.
        """
        caminho = Path(caminho).resolve()
        if not caminho.is_file():
            raise ProjetoInvalido(f"A fonte não existe: {caminho}")
        sha, tamanho = sha_da_fonte(caminho), caminho.stat().st_size
        if self.dados.fonte_sha256 and (sha != self.dados.fonte_sha256 or (
                self.dados.fonte_tamanho and tamanho != self.dados.fonte_tamanho)):
            raise ProjetoInvalido(
                f"{caminho.name} não é a fonte deste projeto: o conteúdo é outro.")
        antes = (self.dados.fonte, self.dados.fonte_sha256, self.dados.fonte_tamanho)
        self.dados.fonte = _caminho_gravado(caminho, self.pasta)
        self.dados.fonte_sha256, self.dados.fonte_tamanho = sha, tamanho
        if self.somente_leitura:
            return              # vale nesta sessão; o arquivo do projeto não muda
        try:
            self.salvar()
        except BaseException:
            self.dados.fonte, self.dados.fonte_sha256, self.dados.fonte_tamanho = antes
            raise

    def _procurar_fonte(self) -> Optional[Path]:
        """O arquivo com o SHA-256 e o tamanho da fonte: na pasta do caminho antigo, na do
        projeto ou na pasta-mãe do projeto."""
        if not self.dados.fonte_sha256:
            return None
        antigo = self.fonte
        vistos, lidos = set(), 0
        for pasta in (antigo.parent, self.pasta, self.pasta.parent):
            if not pasta.is_dir():
                continue
            for candidato in sorted(pasta.glob("*" + antigo.suffix)):
                chave = candidato.resolve()
                if chave in vistos or not candidato.is_file():
                    continue
                vistos.add(chave)
                try:
                    tamanho = self.dados.fonte_tamanho
                    if tamanho and candidato.stat().st_size != tamanho:
                        continue        # tamanho diferente: nem é preciso ler
                    lidos += 1
                    if lidos > CANDIDATOS_DA_FONTE:
                        return None
                    if sha_da_fonte(candidato) == self.dados.fonte_sha256:
                        return chave
                except OSError:
                    continue
        return None

    # ------------------------------------------------------------------
    # Caminhos
    # ------------------------------------------------------------------
    @property
    def pasta_de_padroes(self) -> Path:
        return self.pasta / PASTA_DE_PADROES

    @property
    def fonte(self) -> Path:
        caminho = Path(self.dados.fonte)
        return caminho if caminho.is_absolute() else self.pasta / caminho

    @property
    def fonte_e_pdf(self) -> bool:
        return self.fonte.suffix.lower() == ".pdf"

    def _arquivo_da_pagina(self, indice: int) -> Path:
        return self.pasta / PASTA_DE_PAGINAS / f"{indice + 1:04d}.json"

    # ------------------------------------------------------------------
    # Páginas
    # ------------------------------------------------------------------
    def salvar_pagina(self, indice: int, boxes: List[BoxEntry],
                      tabuleiros: Sequence[Sequence[int]] = (),
                      diagramas: Optional[Sequence["DiagramaLido"]] = None, *,
                      reconhecida: bool = True) -> None:
        """Grava os boxes de uma página, com confiança, origem e geometria, e os tabuleiros.

        `reconhecida=False` é a página que só tem os glifos marcados à mão no modo
        de treino: ela é gravada, mas não conta como lida (`paginas_lidas`), e o
        lote e o F5 a reconhecem mantendo os quadros.

        `diagramas` é a leitura de cada tabuleiro (`abbychess.diagramas`). Fica
        numa chave própria, e `tabuleiros` continua sendo a lista das caixas:
        uma página gravada antes disso abre igual, só com os diagramas por ler.
        Sem `diagramas` (`None`), ficam os já gravados cujo tabuleiro continua na
        página: quem regrava só os boxes, como o reconhecimento em lote, não
        apaga uma conferência.
        """
        if diagramas is None:
            from abbychess.diagramas import para_caixas

            diagramas = para_caixas(tabuleiros, self.carregar_diagramas(indice))
        dados = {
            "pagina": indice + 1,
            "gravado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "boxes": [list(b.as_state()) for b in boxes],
            "tabuleiros": [list(map(int, t)) for t in tabuleiros],
        }
        lidos = [d.para_json() for d in diagramas if d.lido or d.erro]
        if lidos:
            dados["diagramas"] = lidos
        conferidos = sum(1 for d in diagramas if (d.lido or d.erro) and d.conferido)
        with self._trava_do_livro:
            gv.gravar_json(self._arquivo_da_pagina(indice), dados)
            self._marcar(indice, not reconhecida)
            self._atualizar_livro(indice, self._resumo_da_pagina(
                indice, boxes, len(tabuleiros), conferidos))

    def carregar_pagina(self, indice: int) -> Optional[List[BoxEntry]]:
        """Os boxes gravados da página, ou `None` se ela ainda não foi lida."""
        arquivo = self._arquivo_da_pagina(indice)
        if not arquivo.is_file():
            return None
        bruto = json.loads(arquivo.read_text(encoding="utf-8"))
        return [BoxEntry.from_state(tuple(estado)) for estado in bruto["boxes"]]

    def carregar_tabuleiros(self, indice: int) -> List[Tuple[int, int, int, int]]:
        """As caixas dos tabuleiros achados na página, ou lista vazia."""
        arquivo = self._arquivo_da_pagina(indice)
        if not arquivo.is_file():
            return []
        bruto = json.loads(arquivo.read_text(encoding="utf-8"))
        return [tuple(t) for t in bruto.get("tabuleiros", [])]

    # ------------------------------------------------------------------
    # Áreas e léxico
    # ------------------------------------------------------------------
    def _arquivo_das_zonas(self, indice: int) -> Path:
        return self.pasta / PASTA_DE_ZONAS / f"{indice + 1:04d}.json"

    def salvar_zonas(self, indice: int, zonas: Sequence[Zona]) -> None:
        """Grava as áreas da página. Sem áreas, apaga o arquivo: a página volta
        à segmentação inteira, em vez de não gerar box nenhum."""
        arquivo = self._arquivo_das_zonas(indice)
        if not zonas:
            gv.apagar(arquivo)
            return
        gv.gravar_json(arquivo, {"pagina": indice + 1, "zonas": [z.como_dict() for z in zonas]})

    def carregar_zonas(self, indice: int) -> List[Zona]:
        """As áreas gravadas da página, ou lista vazia."""
        arquivo = self._arquivo_das_zonas(indice)
        if not arquivo.is_file():
            return []
        bruto = json.loads(arquivo.read_text(encoding="utf-8"))
        return [Zona.de_dict(z) for z in bruto.get("zonas", [])]

    @property
    def arquivo_do_lexico(self) -> Path:
        return self.pasta / ARQUIVO_DO_LEXICO

    def carregar_diagramas(self, indice: int) -> List["DiagramaLido"]:
        """Os diagramas lidos da página, ou lista vazia se nenhum foi lido."""
        from abbychess.diagramas import DiagramaLido

        arquivo = self._arquivo_da_pagina(indice)
        if not arquivo.is_file():
            return []
        bruto = json.loads(arquivo.read_text(encoding="utf-8"))
        return [DiagramaLido.de_json(d) for d in bruto.get("diagramas", [])]

    def paginas_lidas(self) -> List[int]:
        """As páginas reconhecidas (F5 ou lote), sem as que só têm glifos marcados."""
        pasta = self.pasta / PASTA_DE_PAGINAS
        marcadas = self._marcadas()
        return sorted(int(p.stem) - 1 for p in pasta.glob("*.json")
                      if p.stem.isdigit() and int(p.stem) - 1 not in marcadas)

    def pagina_reconhecida(self, indice: int) -> bool:
        return self._arquivo_da_pagina(indice).is_file() and indice not in self._marcadas()

    def _marcadas(self) -> set:
        arquivo = self.pasta / PASTA_DE_PAGINAS / ARQUIVO_DAS_MARCADAS
        if not arquivo.is_file():
            return set()
        try:
            return {int(i) - 1 for i in json.loads(arquivo.read_text(encoding="utf-8"))}
        except (ValueError, TypeError):
            return set()

    def _marcar(self, indice: int, marcada: bool) -> None:
        marcadas = self._marcadas()
        if (indice in marcadas) == marcada:
            return
        marcadas = marcadas | {indice} if marcada else marcadas - {indice}
        gv.gravar_json(self.pasta / PASTA_DE_PAGINAS / ARQUIVO_DAS_MARCADAS,
                       sorted(i + 1 for i in marcadas))

    # ------------------------------------------------------------------
    # livro.json: o resumo de cada página, sem abrir as páginas
    # ------------------------------------------------------------------
    def resumo_do_livro(self) -> Dict[int, dict]:
        """Índice da página -> o resumo dela (`_resumo_da_pagina`), das páginas gravadas."""
        with self._trava_do_livro:
            return {int(k) - 1: json.loads(json.dumps(v))       # cópia funda: o cache não vaza
                    for k, v in self._carregar_livro()["paginas"].items()}

    def reaplicar_limiar(self) -> None:
        """Os `pendentes` de `livro.json` com o limiar de revisão de agora, pelo histograma
        (exato para os limiares de duas casas da janela de opções)."""
        if self.somente_leitura:
            return
        with self._trava_do_livro:
            livro = self._carregar_livro()
            revisao = self.dados.limiares.revisao
            novo = {"versao": livro["versao"],
                    "paginas": {k: {**v, "pendentes": pendentes_pelo_histograma(v, revisao)}
                                for k, v in livro["paginas"].items()}}
            gv.gravar_json(self.pasta / ARQUIVO_DO_LIVRO, novo)
            self._livro = novo                  # o cache só muda depois de gravado

    def recalcular_livro(self) -> dict:
        """O `livro.json` como ele deve ser, lendo todas as páginas gravadas."""
        paginas = {}
        for arquivo in sorted((self.pasta / PASTA_DE_PAGINAS).glob("*.json")):
            if not arquivo.stem.isdigit():
                continue
            indice = int(arquivo.stem) - 1
            try:
                boxes = self.carregar_pagina(indice) or []
                tabuleiros = self.carregar_tabuleiros(indice)
                conferidos = sum(1 for d in self.carregar_diagramas(indice) if d.conferido)
            except (OSError, ValueError, TypeError, KeyError):
                continue                # página ilegível: fica fora do resumo
            paginas[str(indice + 1)] = self._resumo_da_pagina(
                indice, boxes, len(tabuleiros), conferidos)
        return {"versao": VERSAO_DO_LIVRO, "paginas": paginas}

    def _carregar_livro(self) -> dict:
        if self._livro is None:
            arquivo = self.pasta / ARQUIVO_DO_LIVRO
            try:
                bruto = json.loads(arquivo.read_text(encoding="utf-8"))
                if bruto.get("versao") != VERSAO_DO_LIVRO or not isinstance(
                        bruto.get("paginas"), dict):
                    raise ValueError("versão ou forma inesperada")
            except (OSError, ValueError, AttributeError):
                bruto = self.recalcular_livro()
                if not self.somente_leitura:
                    gv.gravar_json(arquivo, bruto)
            self._livro = bruto
        return self._livro

    def _atualizar_livro(self, indice: int, resumo: dict) -> None:
        with self._trava_do_livro:
            livro = self._carregar_livro()
            livro["paginas"][str(indice + 1)] = resumo
            livro["paginas"] = dict(sorted(livro["paginas"].items(), key=lambda kv: int(kv[0])))
            gv.gravar_json(self.pasta / ARQUIVO_DO_LIVRO, livro)

    def _resumo_da_pagina(self, indice: int, boxes: Sequence[BoxEntry], tabuleiros: int,
                          conferidos: int) -> dict:
        return {"estado": "glifos_marcados" if indice in self._marcadas() else "reconhecida",
                **resumo_das_confiancas(boxes, self.dados.limiares),
                "diagramas": tabuleiros,
                "diagramas_por_conferir": max(0, tabuleiros - conferidos)}


def resumo_das_confiancas(boxes: Sequence[BoxEntry], limiares: Limiares) -> dict:
    """Os boxes da página em `confirmados`, `sem_leitura` e o histograma do resto.

    O histograma tem faixas de 0,01 (a chave é o centésimo de baixo; 100 é a confiança
    1,0) e conta só os
    boxes lidos e não confirmados, os únicos que um limiar de revisão diferente
    mudaria de lado: com ele, `pendentes_pelo_histograma` dá os pendentes de outro
    limiar (de duas casas) sem abrir a página.
    """
    from abbychess.leitor import FONTE_NENHUMA, FONTES_CONFIRMADAS, precisa_revisao

    confirmados = sem_leitura = 0
    histograma: Dict[int, int] = {}
    for b in boxes:
        if b.source in FONTES_CONFIRMADAS:
            confirmados += 1
        elif not b.char or b.source == FONTE_NENHUMA:
            sem_leitura += 1
        else:
            faixa = _faixa(b.confidence)
            histograma[faixa] = histograma.get(faixa, 0) + 1
    pendentes = sum(1 for b in boxes if precisa_revisao(b.char, b.source, b.confidence, limiares))
    return {"boxes": len(boxes), "pendentes": pendentes, "confirmados": confirmados,
            "sem_leitura": sem_leitura,
            "histograma": {str(k): histograma[k] for k in sorted(histograma)}}


def pendentes_pelo_histograma(resumo: dict, revisao: float) -> int:
    """Os pendentes da página com o limiar `revisao` (de duas casas, até 0,99), pelo histograma."""
    corte = math.floor(round(float(revisao) * 100, 6))
    return resumo["sem_leitura"] + sum(n for k, n in resumo["histograma"].items()
                                       if int(k) < corte)


def _faixa(confianca: float) -> int:
    # Arredondar a 6 casas antes do piso põe 0,29 na faixa 29, e não na 28 que
    # `0.29 * 100 == 28.999…` daria. Confiança 1,0 tem a faixa 100 só dela, para o limiar
    # 1,00 (o máximo das opções) não a contar como pendente.
    return min(100, max(0, math.floor(round(float(confianca) * 100, 6))))


def _caminho_gravado(fonte: Path, pasta: Path) -> str:
    """Relativo (com /) quando a fonte está dentro da pasta do projeto; senão absoluto."""
    fonte, pasta = Path(fonte).resolve(), Path(pasta).resolve()
    try:
        return fonte.relative_to(pasta).as_posix()
    except ValueError:
        return str(fonte)
