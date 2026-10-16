"""O projeto de um livro: a fonte, os padrões treinados para ele e as páginas lidas.

Um projeto é uma pasta com esta forma::

    <pasta>/
        projeto.json      nome, caminho da fonte, idioma, limiares e data de criação
        padroes/          os padrões deste livro, uma pasta por caractere
        paginas/0001.json os boxes lidos e corrigidos de cada página, os tabuleiros
                          e, desde a leitura dos diagramas, o FEN de cada um
        diagramas/        as casas conferidas, guardadas como amostras deste livro
        zonas/0001.json   as áreas da página (texto, diagrama, imagem, ignorar)
        lexico.txt        as palavras que a verificação de texto aprendeu neste livro

As áreas ficam fora de `paginas/` de propósito: dá para desenhá-las antes do
primeiro reconhecimento, e uma página só com áreas não pode contar como lida.
Projetos sem `zonas/` nem `idioma` abrem como antes: sem áreas e em português.

`padroes/` usa o mesmo formato da base de treino do PyBoxEditor
(`core.learner.char_to_folder`) mais um `metadados.json` com a altura de cada
amostra (ver `abbychess.padroes`): uma amostra treinada aqui pode ser promovida
à base global sem conversão.

O nome da pasta do projeto é o nome do livro sem acentos nem símbolos. A pasta-mãe
pode ter acento: os padrões são lidos e gravados por `np.fromfile` e
`cv2.imdecode`, que aceitam esse caminho no Windows.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple

from core.box_model import BoxEntry

if TYPE_CHECKING:
    from abbychess.diagramas import DiagramaLido

from abbychess.zonas import Zona

ARQUIVO_DO_PROJETO = "projeto.json"
PASTA_DE_PADROES = "padroes"
PASTA_DE_PAGINAS = "paginas"
#: As páginas que só têm glifos marcados à mão no modo de treino, sem o F5.
ARQUIVO_DAS_MARCADAS = "marcadas.json"
PASTA_DE_ZONAS = "zonas"
ARQUIVO_DO_LEXICO = "lexico.txt"
VERSAO = 1

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
    #: Endireitar cada página antes de ler (`pagina.medir_inclinacao`). Projeto
    #: novo nasce com isto; o que foi criado antes fica sem, porque os boxes
    #: gravados dele estão nas coordenadas da página torta.
    endireitar: bool = False


def nome_de_pasta(nome: str) -> str:
    """O nome do livro como nome de pasta só com ASCII, letras, dígitos e hífen."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    limpo = re.sub(r"[^A-Za-z0-9]+", "-", sem_acento).strip("-").lower()
    return limpo[:60] or "livro"


class ProjetoDeLivro:
    """Acesso a um projeto aberto: metadados, padrões e páginas."""

    def __init__(self, pasta: Path, dados: Projeto):
        self.pasta = Path(pasta)
        self.dados = dados

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
        dados = Projeto(nome=nome, fonte=str(fonte),
                        criado=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        endireitar=True)
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
            limiares = Limiares(**bruto.pop("limiares", {}))
            dados = Projeto(limiares=limiares, **bruto)
        except (ValueError, TypeError) as erro:
            raise ProjetoInvalido(f"{arquivo} está ilegível: {erro}") from erro
        if dados.versao > VERSAO:
            raise ProjetoInvalido(
                f"O projeto é da versão {dados.versao}; este programa lê até a {VERSAO}.")
        (pasta / PASTA_DE_PADROES).mkdir(exist_ok=True)
        (pasta / PASTA_DE_PAGINAS).mkdir(exist_ok=True)
        return cls(pasta, dados)

    def salvar(self) -> None:
        _gravar_json(self.pasta / ARQUIVO_DO_PROJETO, asdict(self.dados))

    # ------------------------------------------------------------------
    # Caminhos
    # ------------------------------------------------------------------
    @property
    def pasta_de_padroes(self) -> Path:
        return self.pasta / PASTA_DE_PADROES

    @property
    def fonte(self) -> Path:
        return Path(self.dados.fonte)

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
        _gravar_json(self._arquivo_da_pagina(indice), dados)
        self._marcar(indice, not reconhecida)

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
            arquivo.unlink(missing_ok=True)
            return
        arquivo.parent.mkdir(exist_ok=True)
        _gravar_json(arquivo, {"pagina": indice + 1, "zonas": [z.como_dict() for z in zonas]})

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
        _gravar_json(self.pasta / PASTA_DE_PAGINAS / ARQUIVO_DAS_MARCADAS,
                     sorted(i + 1 for i in marcadas))


def _gravar_json(caminho: Path, dados) -> None:
    """Grava por arquivo temporário e troca, para não deixar JSON pela metade."""
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                          encoding="utf-8", newline="\n")
    temporario.replace(caminho)
