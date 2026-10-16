"""A leitura de um glifo com os padrões do livro na frente da cadeia global.

A ordem é a do treino de padrões do FineReader: o que o usuário ensinou para este
livro vale antes de tudo, e o resto vem do conhecimento geral.

1. **Padrões do livro** (`abbychess.padroes.PadroesDoLivro`): vizinho mais
   próximo só com as amostras ensinadas neste projeto, com a altura do glifo
   na comparação. Ensinar grava a amostra e ela já responde na leitura
   seguinte, sem treino.
2. **Cadeia global do PyBoxEditor** (`OCRService.fallback_chain_detalhado`): a
   rede de glifos e o k-NN da base global, com os vetos de proporção e de
   alfabeto e os limiares medidos lá. O EasyOCR, último elo dessa cadeia, fica
   desligado por padrão: é lento, e o box que nenhum dos outros leu é
   justamente o que deve ir para a revisão.

Os padrões de um livro não tocam a base global. Promover uma amostra para lá é
outra decisão, explícita.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from abbychess.padroes import ESCALA_DA_CONFIANCA, PadroesDoLivro
from abbychess.projeto import Limiares, nome_de_pasta

FONTE_LIVRO = "livro"
FONTE_LIVRO_FRACO = "livro?"
FONTE_MANUAL = "manual"
FONTE_NENHUMA = "none"

#: Fontes que o usuário decidiu ou confirmou, e que a revisão não volta a mostrar.
FONTES_CONFIRMADAS = {FONTE_LIVRO, FONTE_MANUAL}


@dataclass
class Leitura:
    char: str
    fonte: str
    confianca: float
    #: O padrão do livro que deu a leitura (caminho relativo à pasta dos padrões, com /),
    #: ou `None` quando ela não veio do livro (procedência, §4.1).
    amostra: Optional[str] = None


class _SemEasyOCR:
    """Leitor vazio no lugar do EasyOCR: a cadeia termina em "não li"."""

    def recognize(self, *_args, **_kwargs):
        return []


def base_global() -> Path:
    """A base de treino global do PyBoxEditor, uma pasta por caractere."""
    from config.paths import projeto_dir

    return projeto_dir() / "training_data"


def altura_relativa(recorte: np.ndarray, altura_de_referencia: Optional[float]) -> Optional[float]:
    """A altura do glifo em pé dividida pela altura de referência da página."""
    if not altura_de_referencia or recorte is None or recorte.size == 0:
        return None
    return recorte.shape[0] / float(altura_de_referencia)


class LeitorDoLivro:
    """Lê glifos com os padrões do livro e, na falta deles, com a cadeia global.

    `ocr`, `rede` e `base` são o `OCRService`, o `NeuralPredictor` e o
    `CharacterLearner` global do PyBoxEditor. Ficam injetáveis para os testes
    rodarem sem o modelo de 2,8 MB; `LeitorDoLivro.com_modelos_globais` monta os
    três de verdade.
    """

    def __init__(self, pasta_de_padroes: str | Path, *, limiares: Optional[Limiares] = None,
                 ocr=None, rede=None, base=None, easyocr: bool = False):
        self.pasta_de_padroes = Path(pasta_de_padroes)
        self.limiares = limiares or Limiares()
        # O limiar do livro é uma confiança na escala 1 - d/2000; o padrão o
        # quer em distância.
        self.padroes = PadroesDoLivro(
            self.pasta_de_padroes,
            distancia_maxima=(1.0 - self.limiares.livro) * ESCALA_DA_CONFIANCA)
        self.ocr = ocr
        self.rede = rede
        self.base = base
        self._leitor_easyocr = None if easyocr else _SemEasyOCR()

    @classmethod
    def com_modelos_globais(cls, pasta_de_padroes: str | Path, *,
                            limiares: Optional[Limiares] = None,
                            easyocr: bool = False) -> "LeitorDoLivro":
        """O leitor com a rede e a base global do PyBoxEditor carregadas.

        Carregar a base global custa alguns segundos e a rede menos de um, então
        isto deve rodar fora da thread da interface.
        """
        from core.services.learning_service import LearningService
        from core.services.ocr_service import OCRService

        # Caminho absoluto, e não o padrão "training_data": o LearningService o
        # resolve no diretório atual, e aberto daqui ele criaria uma base vazia
        # na pasta do AbbyChessCraft em vez de ler a do PyBoxEditor.
        servico = LearningService(data_dir=str(base_global()))
        rede = servico._predictor if servico.load_predictor() else None
        return cls(pasta_de_padroes, limiares=limiares, ocr=OCRService(),
                   rede=rede, base=servico._get_learner(), easyocr=easyocr)

    def trocar_limiares(self, limiares: Limiares) -> None:
        """Passa a ler com outros limiares, sem recarregar os modelos."""
        self.limiares = limiares
        self.padroes.distancia_maxima = (1.0 - limiares.livro) * ESCALA_DA_CONFIANCA

    # ------------------------------------------------------------------
    # Ler
    # ------------------------------------------------------------------
    def ler_pelo_livro(self, recorte: np.ndarray, altura_de_referencia: Optional[float] = None
                       ) -> Leitura:
        """Só os padrões do livro. É o que basta para propagar um padrão novo."""
        resposta = self.padroes.ler(recorte, altura_relativa(recorte, altura_de_referencia))
        if resposta.char:
            return Leitura(resposta.char, FONTE_LIVRO, resposta.confianca,
                           self.padroes.relativo(resposta.caminho))
        return Leitura("", FONTE_NENHUMA, 0.0)

    def ler(self, recorte: np.ndarray, *, altura_de_referencia: Optional[float] = None
            ) -> Leitura:
        """A leitura do recorte de um glifo, em pé e escuro sobre claro."""
        if recorte is None or recorte.size == 0:
            return Leitura("", FONTE_NENHUMA, 0.0)
        pelo_livro = self.ler_pelo_livro(recorte, altura_de_referencia)
        if pelo_livro.char:
            return pelo_livro
        return self._ler_global(recorte, altura_de_referencia)

    def _ler_global(self, recorte, altura_de_referencia) -> Leitura:
        if self.ocr is None:
            return Leitura("", FONTE_NENHUMA, 0.0)
        leitura = self.ocr.fallback_chain_detalhado(
            recorte, predictor=self.rede, learner=self.base, reader=self._leitor_easyocr,
            neural_threshold=self.limiares.rede, learner_threshold=self.limiares.base,
            altura_de_referencia=altura_de_referencia)
        return Leitura(leitura.char, leitura.fonte, float(leitura.confianca))

    def arbitro(self, recorte: np.ndarray):
        """`(char, confiança)` no formato que o separador de glifos colados pede."""
        leitura = self.ler(recorte)
        return leitura.char, leitura.confianca

    # ------------------------------------------------------------------
    # Ensinar e esquecer
    # ------------------------------------------------------------------
    def ensinar(self, recorte: np.ndarray, char: str, *,
                altura_de_referencia: Optional[float] = None, origem: str = "") -> Path:
        """Grava o recorte como padrão de `char` neste livro. Vale na hora."""
        return self.padroes.ensinar(recorte, char,
                                    altura_relativa(recorte, altura_de_referencia), origem)

    def esquecer(self, caminho: str | Path) -> None:
        """Apaga um padrão do livro; a leitura seguinte já não o usa."""
        self.padroes.esquecer(caminho)

    def padroes_por_caractere(self) -> Dict[str, List[Path]]:
        """Os arquivos de padrão deste livro, agrupados pelo caractere."""
        return self.padroes.por_caractere()

    @property
    def total_de_padroes(self) -> int:
        return self.padroes.total

    def arquivos_de_padrao(self) -> int:
        return self.padroes.total


def precisa_revisao(char: str, fonte: str, confianca: float, limiares: Limiares) -> bool:
    """Se o box vai para a fila de revisão.

    O que o usuário confirmou e o que saiu de um padrão do livro não voltam: o
    padrão é uma decisão dele aplicada às repetições. O resto volta quando
    ninguém leu ou a confiança fica abaixo do limiar de revisão.
    """
    if fonte in FONTES_CONFIRMADAS:
        return False
    if not char or fonte == FONTE_NENHUMA:
        return True
    return confianca < limiares.revisao


def congelar_para_a_coleta_de_lixo() -> int:
    """Tira da coleta de lixo do Python tudo o que está vivo agora; devolve quantos objetos.

    É para chamar logo depois de carregar os modelos globais (a janela, ao abrir o
    projeto): a rede e a base são centenas de milhares de objetos que não mudam na sessão,
    e cada coleta completa os percorria, ~90 ms na thread da interface (os picos do p95 da
    releitura medidos no passo 1b). Congela **tudo** o que está vivo, não só os modelos.
    `ABBY_SEM_CONGELAR=1` desliga, para medir sem. O congelamento de antes é desfeito primeiro, e o que
    morreu desde então (os modelos do projeto anterior) é recolhido antes de congelar.
    O que estiver vivo no momento (a janela, o projeto) também fica congelado até a
    próxima chamada: a memória dele não volta antes disso.
    """
    import gc
    import os

    if os.environ.get("ABBY_SEM_CONGELAR") == "1":     # o A/B da medida (docs/revisoes/passo-1b.md)
        return 0
    gc.unfreeze()
    gc.collect()
    gc.freeze()
    return gc.get_freeze_count()


def nome_de_origem(projeto_nome: str, pagina: int, indice_box: int,
                   gid: Optional[int] = None) -> str:
    """Nome do arquivo de padrão que diz de onde a amostra veio: o glifo de origem pelo gid
    (estável, §4.1), e a página e a posição só para quem lê o nome."""
    base = f"{nome_de_pasta(projeto_nome)}_p{pagina + 1:04d}_b{indice_box:05d}"
    return base if gid is None else f"{base}_g{gid:x}"
