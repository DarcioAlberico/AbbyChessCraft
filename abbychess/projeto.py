"""O projeto de um livro: a fonte, os padrões treinados para ele e as páginas lidas.

Um projeto é uma pasta com esta forma (formato 2, desde o passo 1b)::

    <pasta>/
        projeto.json      nome, caminho da fonte e o SHA-256 dela, idioma, limiares,
                          data de criação, o próximo `pid` de página e, em `extras`, os
                          campos que esta versão não conhece
        livro.json        o resumo de cada página (índice → pid, estado, pendentes,
                          histograma das confianças, diagramas por conferir); cache,
                          refeito se faltar
        padroes/          os padrões deste livro, uma pasta por caractere
        paginas/p<pid>.json  a página no modelo v2 (`abbychess.modelo`): os glifos com
                          gid, procedência, estilo e revisão; as decisões do usuário; as
                          áreas; os tabuleiros e os diagramas lidos; o estado (§4.4)
        diagramas/        as casas conferidas, guardadas como amostras deste livro
        lexico.txt        as palavras que a verificação de texto aprendeu neste livro
        backup-v1/        o projeto v1 de antes da migração (páginas, áreas, projeto.json)

**O `pid`** é da página, não da posição dela no PDF: reordenar ou inserir páginas (passo
L) não o muda, e os gids dos glifos (`pid << 20 | n`) continuam únicos no projeto. A página
grava o próprio índice, e `livro.json` mapeia índice → pid.

**Migração do v1** (`paginas/0001.json`, `zonas/0001.json`, `paginas/marcadas.json`): na
primeira abertura, o v1 vai para `backup-v1/` e o projeto passa ao formato 2; todas as
páginas v1 migram (pid = o número do arquivo, a página do PDF) e são gravadas ali mesmo, na
abertura. Copiar `backup-v1/` de volta reabre o projeto como era (o arquivo v1 presente vence
o v2 do mesmo pid). Só para leitura, nada migra: as páginas v1 ficam na memória. A migração,
da v1 e da v2 à v3, é da `Migracoes` (`abbychess.migracoes`, `self.migracoes`).

**A janela edita o modelo** (`abbychess.controlador`, desde o passo 2a) e não grava: ela
entrega a página a `agendar`, que guarda um instantâneo imutável para o gravador
(`abbychess.gravador`), uma thread só, com coalescência de meio segundo. `fechar` espera o
gravador. As funções de listas de `BoxEntry` (`carregar_pagina`, `salvar_pagina`) ficam
para o lote, as ferramentas e os testes: a gravação delas é síncrona e reconcilia a lista
com o modelo (`modelo.reconciliar`), mantendo os gids. As páginas lidas ficam em memória,
no modelo, as `PAGINAS_EM_MEMORIA` mais recentes, e uma página com gravação pendente não
sai da memória.

Todo arquivo é gravado por `abbychess.gravacao` (temporário, `fsync`, troca). Um
projeto de versão mais nova abre só para leitura (`somente_leitura`): nada é
gravado nele. A fonte fica com caminho relativo quando está dentro da pasta do
projeto; se ela sumir, `abrir` procura o mesmo arquivo (pelo SHA-256 dos primeiros
4 MB e pelo tamanho) na pasta do caminho antigo, na do projeto e na pasta-mãe do
projeto, e senão `origem.ausente` diz à janela que peça ao usuário
(`origem.relocalizar`). A fonte é da `FonteDoLivro` (`abbychess.fonte_do_livro`,
`self.origem`).

`padroes/` usa o mesmo formato da base de treino do PyBoxEditor
(`core.learner.char_to_folder`) mais um `metadados.json` com a altura de cada
amostra (ver `abbychess.padroes`): uma amostra treinada aqui pode ser promovida
à base global sem conversão.

O nome da pasta do projeto é o nome do livro sem acentos nem símbolos. A pasta-mãe
pode ter acento: os padrões são lidos e gravados por `np.fromfile` e
`cv2.imdecode`, que aceitam esse caminho no Windows.
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import logging
import re
import threading
from collections import OrderedDict
import unicodedata
from dataclasses import asdict, dataclass, field, fields
from enum import StrEnum
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Sequence, Tuple

from core.box_model import BoxEntry

from abbychess import gravacao as gv
from abbychess import procedencia
from abbychess.antes_do_lote import AntesDoLote
from abbychess.fonte_do_livro import FonteDoLivro, caminho_gravado, sha_da_fonte
from abbychess import sequencia as sq
from abbychess.gravador import Gravador
from abbychess.migracoes import Migracoes
from abbychess.resumo_do_livro import ResumoDoLivro
from abbychess import zonas as zn
from abbychess.modelo import (GLIFOS_MARCADOS, NAO_RECONHECIDA, RECONHECIDA, VERIFICADA,
                              Pagina, foto, proximo_estado, reconciliar, reenquadrar)
from abbychess.pagina_em_json import (com_ids_de_diagramas, comparavel, inteiro, pagina_de_json,
                                      pagina_para_json, vazia)
from abbychess.pasta_do_projeto import (ARQUIVO_DO_LEXICO, ARQUIVO_DO_PROJETO, PASTA_DE_PADROES,
                                        PASTA_DE_PAGINAS, PASTA_DO_BACKUP_V1, PASTA_DO_BACKUP_V2,
                                        VERSAO)
# Reexportados: o espaço, a fonte, o lote e os testes da migração e do livro.json os importam daqui.
from abbychess.pasta_do_projeto import (ARQUIVO_DA_JANELA, ARQUIVO_DE_INCLINACOES,  # noqa: F401
                                        ARQUIVO_DO_LIVRO, ARQUIVO_DO_LOTE,  # noqa: F401
                                        LISTAS_DE_PAGINAS, MAPAS_DE_PAGINAS)  # noqa: F401
# Reexportados: o livro e os testes do resumo os importam daqui.
from abbychess.resumo_do_livro import (VERSAO_DO_LIVRO, pendentes_pelo_histograma,  # noqa: F401
                                       resumo_das_confiancas)  # noqa: F401
from abbychess.zonas import Zona

if TYPE_CHECKING:
    from abbychess.diagramas import DiagramaLido

log = logging.getLogger(__name__)

#: O `indice` gravado da página que não é uma do PDF do livro (`_pagina_da_fonte`).
FORA_DO_PDF = -1

#: Quantas páginas o projeto guarda em memória, no modelo (as outras relê do disco).
PAGINAS_EM_MEMORIA = 16
#: Os erros de um JSON de página que não se lê, no texto ou na forma (SPEC-qualidade Q-P7).
ERROS_DE_PAGINA_ILEGIVEL = (ValueError, TypeError, KeyError, AttributeError)

EXTENSOES_DE_IMAGEM = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


class ProjetoInvalido(ValueError):
    """O projeto não pode ser criado ou aberto, com o motivo para o usuário."""


class Notacao(StrEnum):
    """Como o livro escreve as peças nos lances (`Projeto.notacao`, §6.4); a entrada do
    `projeto.json` recusa o resto (SPEC-qualidade Q-P9)."""

    LIVRO = "livro"
    FIGURINAS = "figurinas"
    LETRAS = "letras"


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
    #: A margem do aviso de conflito ao ensinar (§8.3), na escala das distâncias do k-NN
    #: do livro (`distância / 2000`): o glifo mais perto que isto de amostras de outro
    #: caractere é avisado.
    conflito: float = 0.10


@dataclass
class Projeto:
    nome: str
    fonte: str
    criado: str
    limiares: Limiares = field(default_factory=Limiares)
    #: O idioma da prosa, que escolhe o léxico da verificação de texto e as letras das
    #: peças nos lances (pt: R D T B C; en: K Q R B N).
    idioma: str = "pt"
    #: Como o livro escreve as peças nos lances: "figurinas" (♘f3), "letras" (Cf3) ou
    #: "livro" (como o livro: figurinas se ele tem figurinas lidas). No modo figurinas, a
    #: letra digitada num lance vira figurina ao confirmar (§6.4).
    notacao: str = "livro"
    versao: int = VERSAO
    #: O SHA-256 dos primeiros 4 MB da fonte e o tamanho dela, que a reconhecem se ela for
    #: movida (o tamanho separa dois arquivos de começo igual e evita ler os outros).
    fonte_sha256: str = ""
    fonte_tamanho: int = 0
    #: O próximo `pid` de página (§4.1): estável, nunca reaproveitado.
    proximo_pid: int = 0
    #: Os campos de `projeto.json` que esta versão não conhece. Não se perdem: ficam aqui
    #: e são regravados em `extras` (os de `limiares` em `extras["limiares"]`), onde uma
    #: versão futura que os entenda vai buscá-los.
    extras: Dict[str, object] = field(default_factory=dict)
    #: Endireitar cada página antes de ler (`pagina.medir_inclinacao`). Projeto
    #: novo nasce com isto; o que foi criado antes fica sem, porque os boxes
    #: gravados dele estão nas coordenadas da página torta.
    endireitar: bool = False
    #: A sequência do livro (`sequencia.Sequencia.para_json`, §12.4), desde a v3. Nula num
    #: projeto da v2 aberto só para leitura (ela é montada na memória).
    sequencia: Optional[dict] = None
    #: Os glifos que mudaram de página ao dividi-la (§12.4): gid velho -> gid novo (as chaves
    #: em texto, como no JSON). A amostra ensinada antes acha o glifo de origem por aqui.
    gids_movidos: Dict[str, int] = field(default_factory=dict)


_NADA = type(None)
#: O tipo de cada campo conhecido do `projeto.json` e dos limiares (SPEC-qualidade Q-P6): a
#: entrada confere todos antes de montar o `Projeto` e antes de gravar qualquer coisa.
TIPOS_DO_PROJETO = {
    "nome": str, "fonte": str, "criado": str, "limiares": (dict, _NADA), "idioma": str,
    "notacao": str, "versao": int, "fonte_sha256": str, "fonte_tamanho": int,
    "proximo_pid": int, "extras": (dict, _NADA), "endireitar": bool, "sequencia": (dict, _NADA),
    "gids_movidos": dict,
}
TIPOS_DOS_LIMIARES = {f.name: (int, float) for f in fields(Limiares)}
#: Os campos de texto que só aceitam alguns valores.
VALORES_DO_PROJETO = {"notacao": tuple(Notacao)}
_NOMES_DOS_TIPOS = {str: "texto", int: "inteiro", float: "número", bool: "sim ou não",
                    dict: "objeto"}


def _conferir_tipos(valores: dict, tipos: dict, prefixo: str = "") -> None:
    """`ValueError` com o nome do primeiro campo de `valores` que não é do tipo de `tipos`
    (os que `tipos` não conhece passam: vão para `extras`). Um booleano não vale por número."""
    for nome, valor in valores.items():
        tipo = tipos.get(nome)
        if tipo is None:
            continue
        aceitos = tipo if isinstance(tipo, tuple) else (tipo,)
        if not isinstance(valor, aceitos) or (isinstance(valor, bool) and bool not in aceitos):
            esperado = " ou ".join(_NOMES_DOS_TIPOS[t] for t in aceitos if t is not _NADA)
            raise ValueError(f"o campo {prefixo}{nome} devia ser {esperado}, e é {valor!r}")


def _conferir_valores(valores: dict) -> None:
    """`ValueError` com o nome do campo de texto que só aceita alguns valores e tem outro."""
    for nome, aceitos in VALORES_DO_PROJETO.items():
        if nome in valores and valores[nome] not in set(aceitos):
            raise ValueError(f"o campo {nome} devia ser {', '.join(aceitos)}, e é "
                             f"{valores[nome]!r}")


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
        #: As gravações síncronas e a do `livro.json` (o gravador, numa thread, também o
        #: grava): a página, `marcadas.json` e `livro.json` mudam juntos, e o `.tmp` de cada um
        #: é um só. O arquivo da página tem a trava dele (`_trava_das_paginas`). A interface
        #: não espera por ela no caminho de uma edição (ver `_trava_do_cache`).
        self._trava_do_livro = threading.RLock()
        #: O cache das páginas (`_modelos`, `_estados`, `_a_gravar`): curta, sem disco. A
        #: ordem é sempre a do livro e depois a do cache, nunca o contrário.
        self._trava_do_cache = threading.RLock()
        self._travado = somente_leitura         # este objeto segura uma trava de só leitura
        #: Este objeto segura a pasta contra outro processo (`gravacao.tomar_a_pasta`).
        self._dono_da_pasta = False
        #: As páginas lidas, no modelo (as mais recentes), por `pid`, e a foto
        #: (`modelo.foto`) de cada glifo na última gravação síncrona: quem grava listas de
        #: `BoxEntry` (o lote, as ferramentas) pode tê-los mudado no lugar, e só a foto diz o
        #: que mudou.
        self._modelos: "OrderedDict[int, Pagina]" = OrderedDict()
        self._estados: Dict[int, Dict[int, int]] = {}
        #: O pid da página aberta na janela (`prender`), que o cache não despeja.
        self._presa: Optional[int] = None
        #: pid -> (o carimbo do arquivo, o contador de gids) da última página que
        #: `trocar_paginas` gravou: o desfazer de uma divisão confere pelo carimbo, sem reler
        #: as 460 páginas de um livro dividido (o arquivo que mudou depois é relido).
        self._trocadas: Dict[int, Tuple[Optional[tuple], int]] = {}
        #: Só num projeto v1 aberto só para leitura (que não migra): pid -> o JSON v2 que a
        #: migração gravaria de cada página v1, lido uma vez na abertura. Aberto para gravar,
        #: a v1 migra inteira na abertura, e a leitura das páginas não a conhece.
        self._v1_so_leitura: Dict[int, dict] = {}
        #: A sequência do livro (§12.4): a posição de cada `pid`. Montada na primeira vez que
        #: alguém pergunta (`sequencia`), dos dados da v2; `_proximo_pid` é o primeiro `pid`
        #: acima dela, para as páginas que ela ainda não tem.
        self._sequencia: Optional[sq.Sequencia] = None
        self._proximo_pid = 0
        #: (sequência, página do PDF -> primeira posição dela): a origem das amostras antigas.
        self._posicoes_do_pdf: Optional[tuple] = None
        #: A abertura achou a fonte noutro lugar, pelo SHA-256 (a janela avisa).
        self.fonte_relocalizada = False
        #: Esta abertura passou o projeto a um formato novo (a janela avisa onde ficou a cópia).
        self.migrado = False
        #: As pastas com as cópias de antes de cada migração desta abertura.
        self.backups_da_migracao: List[Path] = []
        #: Por que um projeto que não é de versão mais nova abriu só para leitura.
        self.motivo_so_leitura = ""
        #: O gravador das páginas que a janela edita, criado na primeira entrega.
        self._gravador: Optional[Gravador] = None
        #: pid -> (instantâneo, resumo) das páginas entregues e ainda não gravadas: o
        #: resumo do livro as mostra como estão, e não como o disco ainda está.
        self._a_gravar: Dict[int, tuple] = {}
        #: O escritor único de cada `p<pid>.json` (SPEC-qualidade Q-P4): o conteúdo ganha um
        #: bilhete quando é fotografado (`agendar`, `_gravar`), toda gravação do arquivo passa
        #: por `_gravar_arquivo_da_pagina`, uma por vez, e o arquivo nunca recebe um bilhete
        #: mais velho que o último gravado nele (o instantâneo que o gravador tirou da fila
        #: antes de uma gravação síncrona mais nova não volta por cima dela).
        self._trava_das_paginas = threading.Lock()
        self._bilhetes = itertools.count(1)
        self._ultimo_bilhete: Dict[int, int] = {}
        #: Avisado da thread do gravador quando uma página não grava: `(indice, erro)`.
        self.ao_falhar_gravacao = None
        #: Avisado (de qualquer thread) quando um `p<pid>.json` ilegível é isolado:
        #: `(posição, nome do arquivo guardado, ou None)`, uma vez por página.
        self.ao_achar_ilegivel = None
        self._ilegiveis_avisadas: set = set()
        #: As páginas (índices) que `fechar` não conseguiu gravar.
        self.nao_gravadas: List[int] = []
        #: A migração dos formatos antigos, que a abertura chama (`abrir`).
        self.migracoes = Migracoes(self)
        #: A cópia de cada página de antes de o lote a reler (§4.6).
        self.antes_do_lote = AntesDoLote(self)
        #: O resumo de cada página no `livro.json` (§4.3), sem abrir as páginas.
        self.resumo = ResumoDoLivro(self)
        #: A fonte do livro (§4.3): onde ela está, e achá-la se ela sumiu.
        self.origem = FonteDoLivro(self)

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
        if not gv.tomar_a_pasta(pasta):
            raise ProjetoInvalido(f"Outra janela do AbbyChessCraft está criando {pasta}.")
        try:
            dados = Projeto(nome=nome, fonte=caminho_gravado(fonte, pasta),
                            criado=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                            endireitar=True, fonte_sha256=sha_da_fonte(fonte),
                            fonte_tamanho=fonte.stat().st_size)
            projeto = cls(pasta, dados)
            projeto._dono_da_pasta = True
            projeto.salvar()
            projeto.montar_sequencia()
        except BaseException:
            gv.soltar_a_pasta(pasta)
            raise
        return projeto

    @classmethod
    def abrir(cls, pasta: str | Path) -> "ProjetoDeLivro":
        pasta = Path(pasta).resolve()
        arquivo = pasta / ARQUIVO_DO_PROJETO
        if not arquivo.is_file():
            raise ProjetoInvalido(f"Não há {ARQUIVO_DO_PROJETO} em {pasta}.")
        try:
            bytes_do_projeto = arquivo.read_bytes()
            bruto = json.loads(bytes_do_projeto.decode("utf-8"))
            if not isinstance(bruto, dict):
                raise ValueError("não é um objeto JSON")
            _conferir_tipos(bruto, TIPOS_DO_PROJETO)
            _conferir_tipos(bruto.get("limiares") or {}, TIPOS_DOS_LIMIARES, "limiares.")
            _conferir_valores(bruto)
            conhecidos, desconhecidos = _separar(bruto, Projeto)
            extras = dict(conhecidos.pop("extras", None) or {})
            dos_limiares, outros_limiares = _separar(conhecidos.pop("limiares", None) or {},
                                                     Limiares)
            if outros_limiares:
                extras["limiares"] = {**dict(extras.get("limiares") or {}), **outros_limiares}
            extras.update(desconhecidos)
            dados = Projeto(limiares=Limiares(**dos_limiares), extras=extras, **conhecidos)
        except (ValueError, TypeError) as erro:
            raise ProjetoInvalido(f"{arquivo} está ilegível: {erro}") from erro
        if dados.versao > VERSAO:
            return cls._abrir_so_para_leitura(pasta, dados, v1_vence=False)
        if not gv.tomar_a_pasta(pasta):
            # Outro processo o tem aberto (Q-P5, decisão §13.3): nada aqui grava, nem limpa
            # os temporários das gravações dele.
            return cls._abrir_so_para_leitura(
                pasta, dados, v1_vence=dados.versao < 2,
                motivo="O projeto já está aberto em outra janela do AbbyChessCraft: este abre "
                       "só para leitura, e o que você mudar aqui não é gravado.")
        try:
            projeto = cls._abrir_para_gravar(pasta, dados, bytes_do_projeto,
                                             bool(desconhecidos or outros_limiares))
        except BaseException:
            gv.soltar_a_pasta(pasta)
            raise
        projeto._dono_da_pasta = True
        return projeto

    @classmethod
    def _abrir_so_para_leitura(cls, pasta: Path, dados: Projeto, *, v1_vence: bool,
                               motivo: str = "") -> "ProjetoDeLivro":
        """O projeto que esta abertura não grava (o de versão mais nova, o que outro processo
        tem aberto): a fonte achada pelo SHA-256, a v1 e a sequência só na memória."""
        projeto = cls(pasta, dados, somente_leitura=False)
        projeto.motivo_so_leitura = motivo
        if projeto.origem.ausente:
            achada = projeto.origem.procurar()
            if achada is not None:              # só na memória: nada é gravado
                dados.fonte, projeto.fonte_relocalizada = str(achada), True
        # A trava por último: uma falha antes dela não deixa a pasta travada sem dono.
        projeto.somente_leitura = projeto._travado = True
        gv.proteger(pasta)
        projeto.migracoes.guardar_a_v1_na_memoria(v1_vence=v1_vence)
        try:
            projeto.montar_sequencia()          # só leitura: nada é gravado
        except ProjetoInvalido:         # a sequência de um formato que esta versão não lê
            projeto._sequencia, projeto._proximo_pid = projeto._sequencia_da_v2(gravar=False)
        return projeto

    @classmethod
    def _abrir_para_gravar(cls, pasta: Path, dados: Projeto, bytes_do_projeto: bytes,
                           mudou: bool) -> "ProjetoDeLivro":
        """O projeto que este processo tem para gravar (`tomar_a_pasta`): os temporários
        limpos, a fonte achada, a cadeia de migração e os consertos da sequência gravados.
        `mudou`: o `projeto.json` tinha campos que esta versão regrava em `extras`."""
        (pasta / PASTA_DE_PADROES).mkdir(exist_ok=True)
        (pasta / PASTA_DE_PAGINAS).mkdir(exist_ok=True)
        gv.limpar_temporarios(pasta)
        projeto = cls(pasta, dados)
        # A fonte antes da migração: a sequência da v3 tem uma entrada por página do PDF, e
        # sem o PDF o número de páginas não se sabe.
        if projeto.fonte.is_file():
            if not dados.fonte_sha256 or not dados.fonte_tamanho:
                dados.fonte_sha256 = sha_da_fonte(projeto.fonte)
                dados.fonte_tamanho, mudou = projeto.fonte.stat().st_size, True
        else:
            achada = projeto.origem.procurar()
            if achada is not None:
                dados.fonte, mudou = caminho_gravado(achada, pasta), True
                dados.fonte_tamanho = achada.stat().st_size
                projeto.fonte_relocalizada = True
        versao_de_antes = dados.versao
        if dados.versao < VERSAO or projeto.migracoes.indices_v1():
            try:
                # A cadeia (§12.4): a v1 passa à 2 (o `backup-v1/`), e a 2 à 3 (o `backup-v2/`).
                if dados.versao < 2:
                    projeto.migracoes.preparar_migracao(bytes_do_projeto)
                    projeto.backups_da_migracao.append(pasta / PASTA_DO_BACKUP_V1)
                    projeto.migrado = True
                # As páginas v1 migram todas aqui, antes de qualquer leitura (SPEC-qualidade
                # Q-P1): a queda no meio da cadeia, ou um arquivo v1 copiado de volta, também.
                projeto.migracoes.migrar_a_v1(v1_vence=versao_de_antes < 2)
                if dados.versao < VERSAO and projeto.fonte.is_file():
                    projeto.migracoes.migrar_para_v3()
                    projeto.backups_da_migracao.append(pasta / PASTA_DO_BACKUP_V2)
                    projeto.migrado, mudou = True, False
                elif dados.versao < VERSAO:
                    # Sem a fonte, a v3 espera: o projeto segue na v2 (que grava as listas
                    # por posição e a sequência só na memória) até abrir com o PDF.
                    log.warning("a fonte de %s não foi achada; a passagem à v3 fica para "
                                "quando ela estiver no lugar", pasta)
            except OSError as erro:
                # Mídia só de leitura (ou sem espaço): sem o backup não se migra nada; o projeto
                # abre só para leitura, como abria antes, com a sequência só na memória.
                log.warning("o projeto v%d não pôde migrar (%s); abre só para leitura",
                            versao_de_antes, erro)
                projeto.motivo_so_leitura = (
                    "O projeto é do formato antigo e precisa passar ao novo, mas não deu para "
                    f"gravar na pasta dele ({erro}). Ele abre só para leitura.")
                projeto.somente_leitura = projeto._travado = True
                gv.proteger(pasta)
                projeto.migracoes.guardar_a_v1_na_memoria(v1_vence=versao_de_antes < 2)
                projeto.montar_sequencia()
                return projeto
        if mudou:
            try:
                projeto.salvar()
            except OSError as erro:     # mídia só de leitura: abre igual, sem gravar o ajuste
                log.warning("não deu para gravar %s ao abrir: %s", ARQUIVO_DO_PROJETO, erro)
        projeto.montar_sequencia()
        if projeto.sequencia_gravada:
            projeto.migracoes.completar_v3()    # o que uma queda no meio da migração deixou
        return projeto

    def fechar(self, limite: Optional[float] = 30.0) -> bool:
        """Espera o gravador gravar o que está pendente e solta as travas que este objeto
        segura (a de só leitura e a entre processos, uma vez só). Devolve se ficou tudo
        gravado."""
        gravou = True
        if self._gravador is not None:
            gravou = self._gravador.fechar(limite)
            self.nao_gravadas = [] if gravou else self.paginas_sujas()
            self._gravador = None
        if self._travado:
            self._travado = False
            gv.liberar(self.pasta)
        if self._dono_da_pasta:
            self._dono_da_pasta = False
            gv.soltar_a_pasta(self.pasta)
        return gravou

    # ------------------------------------------------------------------
    # O gravador (§4.3): a janela entrega, a thread dele grava
    # ------------------------------------------------------------------
    @property
    def gravador(self) -> Gravador:
        if self._gravador is None:
            self._gravador = Gravador(self._gravar_instantaneo, ao_falhar=self._falhou)
        return self._gravador

    def agendar(self, pagina: Pagina, resumo: Optional[dict] = None) -> bool:
        """A página mudou: o gravador a grava em até meio segundo. Em só leitura, recusa
        (devolve falso e nada é gravado). `resumo`: o de `resumo.do_modelo`, se quem chama
        já o calculou fora da interface (substituir no livro inteiro)."""
        if self.somente_leitura:
            return False
        with self._trava_do_cache:              # sem a trava do livro: não espera o disco
            # Os ids das áreas e dos diagramas nascem aqui, na página viva, e não só no
            # instantâneo: o que for gravado é o que a página tem.
            pagina.diagramas = com_ids_de_diagramas(pagina.diagramas)
            pagina.zonas = zn.com_ids(pagina.zonas)
            self._guardar_no_cache(pagina, foto=False)
            instantaneo = pagina.instantaneo()
            # O resumo vale já para quem pergunta (F6, o lote, "lidas"), antes da gravação.
            self._a_gravar[pagina.pid] = (instantaneo, resumo if resumo is not None
                                          else self.resumo.do_modelo(instantaneo))
            self.gravador.agendar(pagina.pid, (next(self._bilhetes), instantaneo))
        return True

    def descarregar(self, limite: Optional[float] = None) -> bool:
        """Grava agora o que o gravador tem pendente e espera (antes do lote, que grava na
        thread dele, por exemplo). Não chame segurando a trava do livro."""
        return self._gravador.descarregar(limite) if self._gravador is not None else True

    @property
    def sujas(self) -> set:
        """Os pids com mudança ainda não gravada."""
        return self._gravador.sujas if self._gravador is not None else set()

    def paginas_sujas(self) -> List[int]:
        """As posições das páginas entregues ao gravador e ainda não gravadas."""
        sequencia = self.sequencia
        with self._trava_do_cache:
            pids = list(self._a_gravar)
        return sorted(p for p in map(sequencia.posicao_de, pids) if p is not None)

    def _gravar_instantaneo(self, entregue: Tuple[int, Pagina]) -> None:
        """A gravação do gravador: `(bilhete, instantâneo)`. O arquivo da página é gravado
        sem a trava do livro (a interface não espera o disco), na vez dele entre as gravações
        do mesmo arquivo; o resumo vai ao `livro.json` só se nenhuma gravação mais nova da
        página veio antes."""
        bilhete, pagina = entregue
        self._gravar_arquivo_da_pagina(pagina.pid, bilhete,
                                       pagina_para_json(pagina, self._pagina_da_fonte(pagina)))
        with self._trava_do_livro:
            with self._trava_das_paginas:
                vale = self._ultimo_bilhete.get(pagina.pid) == bilhete
            if vale:
                with self._trava_do_cache:
                    # A foto é das gravações síncronas; esta página veio da interface, que
                    # não muda nada no lugar, e a reconciliação a compara com o glifo mesmo.
                    self._estados.pop(pagina.pid, None)
                self.resumo.atualizar(pagina.pid, self.resumo.do_modelo(pagina))
        with self._trava_do_cache:
            pendente = self._a_gravar.get(pagina.pid)
            if pendente is not None and pendente[0] is pagina:
                del self._a_gravar[pagina.pid]

    def _falhou(self, pid: int, erro: BaseException) -> None:
        if self.ao_falhar_gravacao is not None:
            self.ao_falhar_gravacao(self.sequencia.posicao_de(pid), erro)

    def salvar(self) -> None:
        # Na trava do livro: a interface e o gravador (a sequência que cresce) gravam o mesmo
        # `projeto.json`, e o temporário dele é um só.
        with self._trava_do_livro:
            gv.gravar_json(self.pasta / ARQUIVO_DO_PROJETO, asdict(self.dados))

    # ------------------------------------------------------------------
    # Caminhos
    # ------------------------------------------------------------------
    @property
    def pasta_de_padroes(self) -> Path:
        return self.pasta / PASTA_DE_PADROES

    @property
    def fonte(self) -> Path:
        """O caminho da fonte do livro (`origem.caminho`)."""
        return self.origem.caminho

    def _arquivo_v2(self, pid: int) -> Path:
        return self.pasta / PASTA_DE_PAGINAS / f"p{pid}.json"

    # ------------------------------------------------------------------
    # Páginas (modelo v2, §4.3)
    # ------------------------------------------------------------------
    def arquivo_da_pagina(self, indice: int) -> Optional[Path]:
        """O JSON v2 gravado da página (None se ela não foi gravada, ou é v1): o índice da
        busca o lê fora do cache (§7.3)."""
        with self._trava_do_livro:
            return self._arquivo_v2_de(indice)

    def ler_sem_migrar(self, indice: int) -> Optional[Pagina]:
        """A página como está, sem passar pelo cache (o índice da busca, numa thread: §11, um
        escritor só): o instantâneo da que está na memória, ou a gravada; None se nada foi
        gravado dela."""
        modelo = self.modelo_em_memoria(indice)
        if modelo is not None:
            return modelo.instantaneo()
        try:
            return self._gravada(indice)
        except OSError:                         # o arquivo trocado agora mesmo: na próxima
            return None

    def _gravada(self, indice: int) -> Optional[Pagina]:
        """A página da posição `indice` como está gravada, lida de novo (fora do cache): o
        `p<pid>.json`, ou a v1 de um projeto só para leitura; None se nada foi gravado dela,
        ou se o arquivo é ilegível (`_isolar_a_ilegivel`). O `OSError` sobe: quem lê decide."""
        pid = self._pid_em(indice)
        if pid is None:
            return None
        bruto = self._v1_so_leitura.get(pid)
        if bruto is not None:
            return self._de_json(bruto)
        arquivo = self._arquivo_v2(pid)
        if not arquivo.is_file():
            return None
        dados = arquivo.read_bytes()
        try:
            return self._de_json(json.loads(dados.decode("utf-8")))
        except ERROS_DE_PAGINA_ILEGIVEL as erro:
            self._isolar_a_ilegivel(pid, arquivo, erro)
            return None

    def _isolar_a_ilegivel(self, pid: int, arquivo: Path, erro: Exception) -> None:
        """O `p<pid>.json` que não se lê (SPEC-qualidade Q-P7) vai inteiro para
        `p<pid>.corrompido[-N].json` e sai do `livro.json`: a página passa a não reconhecida
        para todos (a busca, a aba Diagramas, a janela, a exportação), e quem a edita começa
        de novo sem apagar o arquivo. Só para leitura, só o resumo da memória muda. O aviso
        (`ao_achar_ilegivel(posição, guardado)`) sai uma vez por página."""
        guardado = None
        with self._trava_do_livro:
            with self._trava_das_paginas:       # o gravador não troca o arquivo no meio
                try:
                    dados = arquivo.read_bytes()
                    pagina_de_json(json.loads(dados.decode("utf-8")))
                    return                      # regravado agora mesmo: vale o novo
                except FileNotFoundError:
                    return                      # outra leitura já o isolou
                except ERROS_DE_PAGINA_ILEGIVEL:
                    pass
                if not self.somente_leitura:
                    guardado, n = arquivo.with_name(f"p{pid}.corrompido.json"), 1
                    while guardado.exists():
                        n += 1
                        guardado = arquivo.with_name(f"p{pid}.corrompido-{n}.json")
                    try:
                        gv.gravar_bytes(guardado, dados)
                        gv.apagar(arquivo)
                    except OSError:
                        log.warning("a página p%d está ilegível e não foi guardada à parte",
                                    pid, exc_info=True)
                        guardado = None
            livro = self.resumo.carregar()
            if str(pid) in livro["paginas"] and (guardado is not None or self.somente_leitura):
                if self.somente_leitura:        # só na memória; troca, não muda no lugar
                    self.resumo.tirar_da_memoria(pid)
                else:
                    self.resumo.atualizar(pid, None)
        log.warning("a página p%d está ilegível (%s); %s", pid, erro,
                    f"guardada em {guardado.name}" if guardado is not None else "fica como está")
        if pid in self._ilegiveis_avisadas:
            return
        self._ilegiveis_avisadas.add(pid)
        if self.ao_achar_ilegivel is not None:
            self.ao_achar_ilegivel(self.sequencia.posicao_de(pid),
                                   guardado.name if guardado is not None else None)

    def carimbo(self, indice: int) -> Optional[tuple]:
        """O (arquivo, tamanho, mtime) do JSON v2 da página, tomado antes de `ler_sem_migrar`:
        `adotar` sabe por ele se o arquivo mudou desde a leitura."""
        arquivo = self.arquivo_da_pagina(indice)
        if arquivo is None:
            return None
        try:
            estado = arquivo.stat()
        except OSError:
            return None
        return (str(arquivo), estado.st_size, estado.st_mtime_ns)

    def adotar(self, pagina: Pagina, carimbo: Optional[tuple]) -> Optional[Pagina]:
        """A página lida fora do cache (`ler_sem_migrar` do JSON, numa thread) entra nele
        como a viva, se nada a mudou desde a leitura: nenhuma outra entrou no cache e o
        arquivo tem o mesmo `carimbo`. Devolve a do cache (a adotada, ou a que já estava lá),
        ou None (leia com `pagina_para_editar`). Só a interface adota."""
        with self._trava_do_livro:
            em_cache = self.modelo_em_memoria(pagina.indice)
            if em_cache is not None:
                return em_cache
            if (carimbo is None or self._pid_em(pagina.indice) != pagina.pid
                    or self.carimbo(pagina.indice) != carimbo):
                return None
            # Girar e cortar não gravam a página (o carimbo é o mesmo): a lida na geometria
            # de antes é levada à de agora.
            self._na_geometria_da_entrada(pagina)
            self._guardar_no_cache(pagina, foto_nova=True)
            return pagina

    def modelo_em_memoria(self, indice: int) -> Optional[Pagina]:
        """A página do cache, sem ler o disco (None se ela não está na memória)."""
        pid = self._pid_em(indice)
        if pid is None:
            return None
        with self._trava_do_cache:
            return self._modelos.get(pid)

    def carregar_modelo(self, indice: int) -> Optional[Pagina]:
        """A página no modelo v2, ou `None` se nada foi gravado dela."""
        pid = self._pid_em(indice)              # antes das travas (a do livro, se montar)
        if pid is None:
            return None                         # fora do livro: nada gravado
        with self._trava_do_cache:              # o caminho comum, sem esperar o disco
            em_cache = self._modelos.get(pid)
            if em_cache is not None:
                self._modelos.move_to_end(pid)
                return em_cache
        with self._trava_do_livro:
            em_cache = self._modelos.get(pid)
            if em_cache is not None:
                self._modelos.move_to_end(pid)
                return em_cache
            pagina = self._gravada(indice)
            if pagina is None:
                return None
            self._guardar_no_cache(pagina, foto_nova=True)
            return pagina

    def _de_json(self, bruto: dict) -> Pagina:
        """A página do JSON, com a posição dela no livro (a da sequência, e não o `indice`
        gravado no arquivo, que a sequência deixa de seguir no passo L)."""
        pagina = pagina_de_json(bruto)
        posicao = self.sequencia.posicao_de(pagina.pid)
        if posicao is not None:
            pagina.indice = posicao
        self._na_geometria_da_entrada(pagina)
        return pagina

    def _na_geometria_da_entrada(self, pagina: Pagina) -> None:
        """Os boxes na geometria da entrada de agora (§12.4): a página gravada noutra (uma
        operação de página que só gravou a sequência, ou uma queda antes do arquivo da
        página) é levada na leitura."""
        sequencia = self._sequencia
        if sequencia is None:
            return
        entrada = sequencia.entrada_de(pagina.pid)
        if entrada is None:
            apagada = sequencia.apagada(pagina.pid)
            entrada = None if apagada is None else apagada.entrada
        if entrada is not None:
            try:
                reenquadrar(pagina, entrada.geometria, entrada.tamanho)
            except ValueError as erro:          # um projeto.json sem o tamanho (estragado)
                log.warning("a página p%d não foi levada à geometria da entrada: %s",
                            pagina.pid, erro)

    def _arquivo_v2_de(self, indice: int) -> Optional[Path]:
        """O `p<pid>.json` da página na posição `indice`, ou None se nada foi gravado dela.
        Os arquivos que o `livro.json` não cita (uma queda entre a página e o livro) entram
        na sequência quando ela é montada (`_montar_sequencia`)."""
        pid = self._pid_em(indice)
        if pid is None:
            return None
        arquivo = self._arquivo_v2(pid)
        return arquivo if arquivo.is_file() else None

    def salvar_modelo(self, pagina: Pagina) -> None:
        """Grava a página v2 e o resumo dela em `livro.json`."""
        with self._trava_do_livro:
            pagina.diagramas = com_ids_de_diagramas(pagina.diagramas)
            pagina.zonas = zn.com_ids(pagina.zonas)
            self._gravar(pagina)
            self._guardar_no_cache(pagina)

    def _gravar(self, pagina: Pagina, *, livro: bool = True) -> None:
        """A página e o resumo dela em `livro.json` (com a trava do livro); `livro=False`
        deixa o resumo para quem grava várias de uma vez (`trocar_paginas`)."""
        bilhete = next(self._bilhetes)
        dados = pagina_para_json(pagina, self._pagina_da_fonte(pagina))
        self._gravar_arquivo_da_pagina(pagina.pid, bilhete, dados)
        with self._trava_do_cache:
            # A foto da gravação, do mesmo `as_state()` que foi para o JSON.
            self._estados[pagina.pid] = {b[0]: hash(tuple(b[1])) for b in dados["boxes"]}
        if livro:
            self.resumo.atualizar(pagina.pid, self.resumo.do_modelo(pagina))

    def _gravar_arquivo_da_pagina(self, pid: int, bilhete: int, dados: dict) -> bool:
        """O único lugar que grava `p<pid>.json` (Q-P4), uma gravação por vez: a de bilhete
        mais velho que o último gravado não vai ao disco (devolve falso)."""
        with self._trava_das_paginas:
            if bilhete < self._ultimo_bilhete.get(pid, 0):
                return False
            gv.gravar_json(self._arquivo_v2(pid), dados)
            self._ultimo_bilhete[pid] = bilhete
            return True

    def prender(self, pid: Optional[int]) -> None:
        """A página aberta na janela (None: nenhuma): o cache não a despeja, por mais páginas
        que um lote leia, e quem a pede de novo (o lote, a busca) recebe o mesmo objeto que a
        janela edita, e não outro lido do disco (SPEC-qualidade Q-P3)."""
        with self._trava_do_cache:
            self._presa = pid

    def _guardar_no_cache(self, pagina: Pagina, *, foto_nova: bool = False,
                          foto: bool = True) -> None:
        """Põe a página no cache; `foto_nova` (a página veio do disco) refaz a foto dos
        estados, que de outro modo seria a de outra versão da mesma página. `foto=False` é a
        página que a interface entrega ao gravador: ela não muda nada no lugar, e a foto
        (um hash por glifo) não é calculada a cada edição."""
        with self._trava_do_cache:
            self._no_cache(pagina, foto_nova, foto)

    def _no_cache(self, pagina: Pagina, foto_nova: bool, com_foto: bool) -> None:
        self._modelos[pagina.pid] = pagina
        self._modelos.move_to_end(pagina.pid)
        if not com_foto:
            self._estados.pop(pagina.pid, None)
        elif foto_nova or pagina.pid not in self._estados:
            self._estados[pagina.pid] = {b.gid: foto(b.entry) for b in pagina.boxes}
        sujas = self.sujas
        for pid in list(self._modelos):
            if len(self._modelos) <= PAGINAS_EM_MEMORIA:
                break
            saiu = self._modelos[pid]
            if pid in sujas or saiu is pagina or pid == self._presa:
                continue                    # a página com gravação pendente fica, e a aberta
            del self._modelos[pid]
            self._estados.pop(pid, None)

    def pagina_para_editar(self, indice: int) -> Pagina:
        """A página no modelo, criada (com pid novo) se nada foi gravado dela: é a que a
        janela edita na primeira mudança."""
        with self._trava_do_livro:
            return self._modelo_ou_novo(indice)

    def _modelo_ou_novo(self, indice: int) -> Pagina:
        pagina = self.carregar_modelo(indice)
        if pagina is None:
            pid = self._pid_em(indice, criar=True)
            if pid >= self.dados.proximo_pid:
                # O contador gravado passa do pid da página que nasce, antes do arquivo dela.
                # Ele não é o teto dos pids em disco (uma página de pid menor nasce sem
                # gravá-lo): ao montar a sequência, os `p<pid>.json` em disco também contam.
                self.dados.proximo_pid = pid + 1
                if not self.somente_leitura:
                    self.salvar()
            entrada = self.sequencia.entrada_de(pid)
            pagina = Pagina(pid=pid, indice=indice)
            if entrada is not None:
                pagina.geometria, pagina.tamanho = entrada.geometria, entrada.tamanho
            self._guardar_no_cache(pagina)
        return pagina

    def _reconciliar(self, pagina: Pagina, boxes: Sequence[BoxEntry]):
        novos, dif = reconciliar(pagina.boxes, boxes, pagina.alocar, procedencia.amostra_de,
                                 self._estados.get(pagina.pid))
        pagina.aplicar(dif, novos)
        return dif

    def gid_do_box(self, indice: int, boxes: Sequence[BoxEntry], posicao: int) -> int:
        """O gid do box `posicao` de uma lista de `BoxEntry` da página (para quem trabalha
        com listas: as ferramentas e os testes; a janela, desde o 2a, já tem os gids).

        Se a reconciliação deu gids novos, a página é gravada antes de o gid sair daqui:
        quem o pede o grava em disco (o nome do padrão ensinado), e um gid só na memória
        voltaria a ser alocado depois de uma queda."""
        with self._trava_do_livro:
            pagina = self._modelo_ou_novo(indice)
            dif = self._reconciliar(pagina, boxes)
            if dif.novos and not self.somente_leitura:
                if pagina.estado in (RECONHECIDA, VERIFICADA):
                    pagina.estado = proximo_estado(pagina.estado, "editar")
                elif pagina.estado == NAO_RECONHECIDA and pagina.boxes:
                    pagina.estado = proximo_estado(pagina.estado, "marcar")
                self.salvar_modelo(pagina)
            return pagina.boxes[posicao].gid

    def salvar_pagina(self, indice: int, boxes: List[BoxEntry],
                      tabuleiros: Sequence[Sequence[int]] = (),
                      diagramas: Optional[Sequence["DiagramaLido"]] = None, *,
                      reconhecida: bool = True, reconheceu: bool = False) -> None:
        """Grava os boxes de uma página, com confiança, origem e geometria, e os tabuleiros.

        É o adaptador do passo 1b: a lista de `BoxEntry` é reconciliada com o modelo
        (`modelo.reconciliar`), e cada glifo guarda o gid; os que nasceram de uma edição
        ganham gid novo, e as decisões vão aos sucessores.

        `reconhecida=False` é a página que só tem os glifos marcados à mão no modo de
        treino: ela é gravada, mas não conta como lida (`resumo.paginas_lidas`). `reconheceu`
        diz que a gravação é a de um reconhecimento (F5 ou lote), e não de uma edição:
        o estado vai por `proximo_estado` (§4.4).

        A mudança feita **no lugar** num `BoxEntry` (a ferramenta que muda o que
        `carregar_pagina` devolveu) só é vista se a página tem foto (veio do disco ou de outra
        gravação por aqui); a página que a janela entregou ao gravador não tem, e a mudança
        no lugar não entra em `mudados`. Quem trabalha por listas, passe objetos novos.

        `diagramas` é a leitura de cada tabuleiro (`abbychess.diagramas`). Sem
        `diagramas` (`None`), ficam os já gravados cujo tabuleiro continua na página:
        quem regrava só os boxes, como o reconhecimento em lote, não apaga uma conferência.
        """
        from abbychess.diagramas import para_caixas

        with self._trava_do_livro:
            # Uma cópia rasa: a interface pode estar mostrando a página do cache (o lote lê
            # a página aberta), e ela não muda debaixo dela; a cópia entra no cache.
            pagina = copy.copy(self._modelo_ou_novo(indice))
            if diagramas is None:
                diagramas = para_caixas(tabuleiros, pagina.diagramas)
            lidos = com_ids_de_diagramas([d for d in diagramas if d.lido or d.erro])
            dif = self._reconciliar(pagina, boxes)
            mudou = (not dif.vazia or [list(t) for t in tabuleiros] != [list(t) for t in pagina.tabuleiros]
                     or [d.para_json() for d in lidos] != [d.para_json() for d in pagina.diagramas])
            pagina.tabuleiros = [tuple(int(v) for v in t) for t in tabuleiros]
            pagina.diagramas = list(lidos)
            if not reconhecida:
                # A página ainda não passou pelo F5 (ou o desfazer voltou a antes dele): é
                # o "só glifos marcados" do v1, qualquer que fosse o estado gravado.
                pagina.estado = GLIFOS_MARCADOS if pagina.boxes else NAO_RECONHECIDA
            elif reconheceu or pagina.estado in (NAO_RECONHECIDA, GLIFOS_MARCADOS):
                pagina.estado = proximo_estado(pagina.estado, "reconhecer")
            elif mudou:
                pagina.estado = proximo_estado(pagina.estado, "editar")
            self.salvar_modelo(pagina)

    def pid_da_pagina(self, indice: int) -> Optional[int]:
        """O pid da página na posição `indice`, sem ler o JSON dela (o da sequência), ou
        None fora do livro."""
        return self._pid_em(indice)

    def carregar_pagina(self, indice: int) -> Optional[List[BoxEntry]]:
        """Os boxes gravados da página, ou `None` se ela ainda não foi lida nem marcada.
        Os objetos são os do modelo: a janela os edita, e a gravação os reconcilia."""
        pagina = self.carregar_modelo(indice)
        if pagina is None or (not pagina.boxes and pagina.estado == NAO_RECONHECIDA):
            return None
        return pagina.entries()

    def carregar_tabuleiros(self, indice: int) -> List[Tuple[int, int, int, int]]:
        """As caixas dos tabuleiros achados na página, ou lista vazia."""
        pagina = self.carregar_modelo(indice)
        return [tuple(t) for t in pagina.tabuleiros] if pagina is not None else []

    def ler_sem_guardar(self, indice: int) -> Optional[Pagina]:
        """A página para só ler (a aba Diagramas percorre o livro): a do cache, se estiver
        lá (pode ter o que ainda não foi gravado), ou a do JSON, **sem entrar no cache** (a
        leitura do livro não despeja as páginas abertas)."""
        pid = self._pid_em(indice)
        if pid is None:
            return None
        with self._trava_do_cache:
            em_cache = self._modelos.get(pid)
        if em_cache is not None:
            return em_cache
        try:
            return self._gravada(indice)
        except OSError:                         # gravada agora mesmo pelo gravador: na próxima
            return None

    def carregar_diagramas(self, indice: int) -> List["DiagramaLido"]:
        """Os diagramas lidos da página, ou lista vazia se nenhum foi lido."""
        pagina = self.carregar_modelo(indice)
        return list(pagina.diagramas) if pagina is not None else []

    # ------------------------------------------------------------------
    # Áreas e léxico
    # ------------------------------------------------------------------
    def salvar_zonas(self, indice: int, zonas: Sequence[Zona]) -> None:
        """Grava as áreas da página (no arquivo dela, desde o v2). Sem áreas, a página volta
        à segmentação inteira, em vez de não gerar box nenhum. Uma página sem nada gravado
        nasce aqui, como não reconhecida: dá para desenhar as áreas antes do F5."""
        with self._trava_do_livro:
            if not zonas and self.carregar_modelo(indice) is None:
                return
            pagina = self._modelo_ou_novo(indice)
            pagina.zonas = list(zonas)
            self.salvar_modelo(pagina)

    def carregar_zonas(self, indice: int) -> List[Zona]:
        """As áreas gravadas da página, ou lista vazia."""
        pagina = self.carregar_modelo(indice)
        return list(pagina.zonas) if pagina is not None else []

    @property
    def arquivo_do_lexico(self) -> Path:
        return self.pasta / ARQUIVO_DO_LEXICO

    # ------------------------------------------------------------------
    # As páginas nas listas gravadas (posição na interface, `pid` no disco)
    # ------------------------------------------------------------------
    @property
    def sequencia_gravada(self) -> bool:
        """O projeto tem a sequência no disco (v3): as listas de páginas gravadas são de
        `pid`. Num projeto da v2 aberto só para leitura, de posições."""
        return self.dados.sequencia is not None

    def paginas_para_gravar(self, posicoes: Iterable[int]) -> List[int]:
        """As posições como o projeto as grava: os `pid` (v3), ou as próprias posições."""
        posicoes = [int(p) for p in posicoes]
        if not self.sequencia_gravada:
            return posicoes
        return [p for p in map(self._pid_em, posicoes) if p is not None]

    def posicoes_das_gravadas(self, gravadas: Iterable) -> List[int]:
        """As posições de agora das páginas de uma lista gravada (`paginas_para_gravar`): a
        página que saiu do livro, ou o valor ilegível, sai."""
        saida = []
        for valor in gravadas or ():
            valor = inteiro(valor)
            if valor is None:
                continue
            posicao = self.posicao_do_pid(valor) if self.sequencia_gravada else valor
            if posicao is not None and 0 <= posicao < len(self.sequencia):
                saida.append(posicao)
        return saida

    # ------------------------------------------------------------------
    # A sequência do livro (§12.4)
    # ------------------------------------------------------------------
    @property
    def sequencia(self) -> sq.Sequencia:
        """A ordem das páginas e o `pid` de cada uma. Ler não grava (SPEC-qualidade Q-P8):
        antes de `montar_sequencia`, a pergunta a monta só na memória."""
        sequencia = self._sequencia
        if sequencia is None:
            with self._trava_do_livro:
                if self._sequencia is None:
                    self._sequencia, self._proximo_pid = self._montar_sequencia(gravar=False)
                sequencia = self._sequencia
        return sequencia

    def montar_sequencia(self) -> sq.Sequencia:
        """Monta a sequência e grava o que a montagem conserta (o `livro.json` que falta, a
        página em disco que ele não cita, a sequência que o `projeto.json` da v3 não tem, as
        páginas fora dela): ao criar e ao abrir, na thread de quem abre e antes de qualquer
        render (o fitz que conta as páginas não roda junto com um render da pré-carga)."""
        with self._trava_do_livro:
            if not self.somente_leitura:
                self.resumo.esquecer()          # o do disco: o conserto da memória vai a ele
                self.resumo.carregar(gravar=True)
            self._sequencia, proximo = self._montar_sequencia(gravar=True)
            self._proximo_pid = max(self._proximo_pid, proximo)
            return self._sequencia

    def _pid_em(self, indice: int, criar: bool = False) -> Optional[int]:
        """O `pid` da página na posição `indice`, ou None fora do livro. Só `criar` (a
        página que nasce numa gravação: a fonte sumida não diz quantas páginas tem) estende a
        sequência com `pid` novos; uma pergunta não deixa entradas fantasmas."""
        sequencia = self.sequencia
        if 0 <= indice < len(sequencia):
            return sequencia.pid_em(indice)
        if indice < 0:
            raise IndexError(f"Página {indice + 1} fora do livro")
        if not criar:
            return None
        with self._trava_do_livro:
            sequencia = self._sequencia
            if indice >= len(sequencia):
                faltam = indice + 1 - len(sequencia)
                pids = list(range(self._proximo_pid, self._proximo_pid + faltam))
                self._proximo_pid += faltam
                novas = tuple(sq.Entrada(p, sq.FONTE_DO_LIVRO, len(sequencia) + k)
                              for k, p in enumerate(pids))
                self._sequencia = sequencia = sq.Sequencia(sequencia.entradas + novas,
                                                           sequencia.apagadas)
                if self.sequencia_gravada and not self.somente_leitura:
                    self.dados.sequencia = sequencia.para_json()     # antes da página
                    self.dados.proximo_pid = max(self.dados.proximo_pid, self._proximo_pid)
                    self.salvar()
            return sequencia.pid_em(indice)

    def gravar_sequencia(self, nova: sq.Sequencia) -> None:
        """A sequência nova (uma operação de página, §12.4): o `projeto.json` primeiro, e só
        depois a memória; uma falha de gravação (`OSError`) não muda nada. Recusa o projeto
        só para leitura e o da v2 (sem a sequência gravada: a fonte sumida)."""
        if self.somente_leitura:
            raise OSError("o projeto está aberto só para leitura")
        if not self.sequencia_gravada:
            raise OSError("o projeto ainda está no formato antigo: abra-o com a fonte do livro "
                          "no lugar para passar ao novo")
        with self._trava_do_livro:
            antes = (self.dados.sequencia, self.dados.proximo_pid)
            velha = self.sequencia
            self.dados.sequencia = nova.para_json()
            self.dados.proximo_pid = max([self.dados.proximo_pid, self._proximo_pid,
                                          *(p + 1 for p in nova.todos_os_pids)])
            try:
                self.salvar()
            except BaseException:
                self.dados.sequencia, self.dados.proximo_pid = antes
                raise
            self._trocar_sequencia(nova)
            self._regravar_as_reenquadradas(velha, nova)

    def _regravar_as_reenquadradas(self, velha: sq.Sequencia, nova: sq.Sequencia) -> None:
        """As páginas gravadas cujo quadro mudou (cortar, tirar o corte e o desfazer deles) vão
        ao gravador já levadas à geometria nova: o arquivo, o `livro.json` (as contagens sem
        os glifos guardados fora do quadro) e a busca (que lê a da memória) seguem a imagem.
        Girar não tira glifo nenhum: as contagens e o texto ficam, e a página é levada ao giro
        quando é lida (o livro inteiro girado não relê as 230 páginas). A sequência já está
        gravada antes: uma queda antes delas é a leitura preguiçosa que resolve
        (`_na_geometria_da_entrada`)."""
        for posicao, entrada in enumerate(nova.entradas):
            antes = velha.entrada_de(entrada.pid)
            if antes is None or antes.quadro == entrada.quadro:
                continue
            if self.modelo_em_memoria(posicao) is None and self._arquivo_v2_de(posicao) is None:
                continue                            # nada gravado: nada a levar
            try:
                pagina = self.carregar_modelo(posicao)
            except (OSError, ValueError, KeyError, TypeError) as erro:
                log.warning("a página %d não foi levada à geometria nova: %s", posicao + 1,
                            erro)
                continue
            if pagina is not None:
                self.agendar(pagina)

    def inserir_arquivo(self, caminho: str | Path) -> List[sq.Entrada]:
        """Copia o PDF ou a imagem para `inseridas/` (o nome pelo SHA-256: o mesmo arquivo
        inserido duas vezes é uma cópia só) e devolve uma entrada com `pid` novo para cada
        página dele, para `Sequencia.inserir`. O PDF cifrado ou que não abre levanta
        `ProjetoInvalido`, e nada é copiado. A imagem é uma página (de um TIFF de várias, a
        primeira)."""
        caminho = Path(caminho)
        sufixo = caminho.suffix.lower()
        if sufixo != ".pdf" and sufixo not in EXTENSOES_DE_IMAGEM:
            raise ProjetoInvalido(f"Formato não suportado: {sufixo}. Use PDF ou imagem.")
        try:
            dados = caminho.read_bytes()
        except OSError as erro:
            raise ProjetoInvalido(f"{caminho.name} não abriu: {erro}") from erro
        paginas = 1
        if sufixo == ".pdf":
            import fitz

            try:
                with fitz.open(stream=dados, filetype="pdf") as documento:
                    cifrado = documento.needs_pass or documento.is_encrypted
                    paginas = documento.page_count
            except (RuntimeError, ValueError) as erro:
                raise ProjetoInvalido(f"{caminho.name} não é um PDF legível: {erro}") from erro
            if cifrado:
                raise ProjetoInvalido(f"{caminho.name} é um PDF cifrado: tire a senha antes de "
                                      "inserir.")
            if paginas == 0:
                raise ProjetoInvalido(f"{caminho.name} não tem páginas.")
        nome = f"{sq.PASTA_DAS_INSERIDAS}/{hashlib.sha256(dados).hexdigest()}{sufixo}"
        destino = self.pasta / nome
        if not destino.is_file():
            gv.gravar_bytes(destino, dados)
        with self._trava_do_livro:
            pids = list(range(self._proximo_pid, self._proximo_pid + paginas))
            self._proximo_pid += paginas
        return [sq.Entrada(pid, nome, k) for k, pid in enumerate(pids)]

    def _trocar_sequencia(self, nova: sq.Sequencia) -> None:
        """A sequência nova (as operações de página, rodada 2): as páginas da memória passam a
        ter a posição dela no `indice`. Não grava nada."""
        with self._trava_do_livro:
            self._sequencia = nova
            self._proximo_pid = max([self._proximo_pid, *(p + 1 for p in nova.todos_os_pids)])
            with self._trava_do_cache:
                for pid, pagina in self._modelos.items():
                    posicao = nova.posicao_de(pid)
                    if posicao is not None:
                        pagina.indice = posicao
                        self._na_geometria_da_entrada(pagina)

    def origem_da_amostra(self, origem: str) -> Optional[Tuple[Optional[int], Optional[int]]]:
        """(posição de agora, gid) do glifo de onde a amostra veio, pelo nome de origem dela
        (`leitor.nome_de_origem`); None se o nome não diz. A posição vem do `gid` (`pid =
        gid >> 20`, §12.4), e não do número da página no nome, que é o de quando ela foi
        ensinada; None na posição: a página saiu do livro. A amostra antiga, sem o `gid` no
        nome, vai à primeira entrada da página do PDF do nome (a metade esquerda, se ela foi
        dividida)."""
        from abbychess.leitor import origem_de
        from abbychess.modelo import pid_de

        lido = origem_de(origem)
        if lido is None:
            return None
        pagina_do_nome, gid = lido
        sequencia = self.sequencia
        if gid is not None:
            gid = self.gid_de_agora(gid)
            return sequencia.posicao_de(pid_de(gid)), gid
        guardado = self._posicoes_do_pdf
        if guardado is None or guardado[0] is not sequencia:   # uma vez por sequência
            posicoes: Dict[int, int] = {}
            for direita in (False, True):       # a metade esquerda, onde quer que esteja
                for posicao, entrada in enumerate(sequencia.entradas):
                    if entrada.fonte == sq.FONTE_DO_LIVRO and \
                            (entrada.metade == "direita") == direita:
                        posicoes.setdefault(entrada.pagina, posicao)
            guardado = self._posicoes_do_pdf = (sequencia, posicoes)
        return guardado[1].get(pagina_do_nome), None

    def gid_de_agora(self, gid: int) -> int:
        """O gid de hoje do glifo `gid` (o mesmo, ou o que ele ganhou ao mudar de página numa
        divisão, pelos `gids_movidos`)."""
        movidos = self.dados.gids_movidos
        for _ in range(len(movidos) + 1):       # uma cadeia não volta, mas o arquivo é de fora
            novo = inteiro(movidos.get(str(gid)))
            if novo is None or novo == gid:
                break
            gid = novo
        return gid

    def novo_pid(self) -> int:
        """Um `pid` que nenhuma página teve (a metade direita de uma divisão). Gravado com a
        sequência que o usa; perdido (nunca reaproveitado) se a operação não acontece."""
        with self._trava_do_livro:
            pid = self._proximo_pid
            self._proximo_pid += 1
            return pid

    def pagina_do_pid(self, pid: int) -> Optional[Pagina]:
        """A página `pid` como está (a do cache, ou a do arquivo, sem pô-la no cache); None
        se nada foi gravado dela. Também a de fora da sequência."""
        with self._trava_do_livro:
            with self._trava_do_cache:
                em_cache = self._modelos.get(pid)
            if em_cache is not None:
                return em_cache
            arquivo = self._arquivo_v2(pid)
            if not arquivo.is_file():
                return None
            return self._de_json(json.loads(arquivo.read_text(encoding="utf-8")))

    def _carimbo_do_pid(self, pid: int) -> Optional[tuple]:
        try:
            estado = self._arquivo_v2(pid).stat()
        except OSError:
            return None
        return (estado.st_size, estado.st_mtime_ns)

    def _intocada(self, pid: int) -> Optional[int]:
        """O contador de gids da página que `trocar_paginas` gravou por último, se o arquivo
        está como ela o deixou e a página não está na memória (que pode ter mudado sem
        gravar); senão None."""
        registro = self._trocadas.get(pid)
        if registro is None:
            return None
        with self._trava_do_cache:
            if pid in self._modelos:
                return None
        carimbo = self._carimbo_do_pid(pid)
        return registro[1] if carimbo is not None and carimbo == registro[0] else None

    def proximo_n_de(self, pid: int) -> Optional[int]:
        """O contador de gids da página `pid` como está (None: sem arquivo), sem relê-la se
        `trocar_paginas` a gravou e nada a mudou depois."""
        intocada = self._intocada(pid)
        if intocada is not None:
            return intocada
        pagina = self.pagina_do_pid(pid)
        return None if pagina is None else pagina.proximo_n

    def pagina_igual(self, pid: int, esperada: Optional[Pagina]) -> bool:
        """A página `pid` está como `esperada` (None: sem arquivo)? Compara o que vai para o
        JSON, sem a data, a posição e o contador de gids (o que se relê do disco é igual ao
        que foi gravado, com os números arredondados do mesmo jeito). A página que
        `trocar_paginas` gravou e ninguém mudou depois (o mesmo carimbo, fora da memória) é a
        que o desfazer espera: o histórico é linear, e toda outra gravação muda o carimbo."""
        if esperada is not None and self._intocada(pid) is not None:
            return True
        atual = self.pagina_do_pid(pid)
        if esperada is None:
            # A página vazia que a interface criou na memória (um box desenhado e tirado) e
            # nunca gravou vale a de antes.
            return atual is None or (vazia(atual) and not self._arquivo_v2(pid).is_file())
        if atual is None:
            return False
        return comparavel(atual) == comparavel(esperada)

    def trocar_paginas(self, nova: sq.Sequencia, paginas: Dict[int, Optional[Pagina]],
                       gids_movidos: Dict[str, int]) -> None:
        """A sequência nova com páginas trocadas inteiras (dividir e o desfazer dela, §12.4):
        `paginas` é pid -> a página nova (None: o arquivo sai). A ordem das gravações: os
        arquivos das páginas que entram na sequência, o `projeto.json` (a sequência, o
        contador de `pid` e os `gids_movidos`), as outras páginas, e por último os arquivos que
        saem. `OSError` até o `projeto.json`: nada mudou (os arquivos que entraram saem).
        Depois dele a operação vale: a página que não grava fica com o gravador, que tenta de
        novo e avisa, e o arquivo que não sai é avisado no log. Uma queda depois do
        `projeto.json` e antes das páginas deixa a página de antes no disco, que a leitura leva
        à geometria nova: nada se perde (o que passou à página nova fica também guardado fora
        do quadro da outra)."""
        if self.somente_leitura:
            raise OSError("o projeto está aberto só para leitura")
        if not self.sequencia_gravada:
            raise OSError("o projeto ainda está no formato antigo")
        pendentes = set(paginas) & self.sujas
        if pendentes:
            raise OSError("há página com gravação pendente: tente de novo")
        with self._trava_do_livro:
            atual = self.sequencia
            entram = {pid for pid, pagina in paginas.items() if pagina is not None
                      and atual.entrada_de(pid) is None and atual.apagada(pid) is None}
            for pid, pagina in paginas.items():
                if pagina is not None and nova.posicao_de(pid) is not None:
                    pagina.indice = nova.posicao_de(pid)
            antes = (self.dados.sequencia, self.dados.proximo_pid, self.dados.gids_movidos)
            gravados = []
            try:
                for pid in entram:
                    entrada = nova.entrada_de(pid)
                    do_pdf = (entrada is not None and entrada.fonte == sq.FONTE_DO_LIVRO
                              and entrada.metade != "direita")
                    gv.gravar_json(self._arquivo_v2(pid), pagina_para_json(
                        paginas[pid], entrada.pagina if do_pdf else FORA_DO_PDF))
                    gravados.append(pid)
                self.dados.sequencia = nova.para_json()
                self.dados.proximo_pid = max([self.dados.proximo_pid, self._proximo_pid,
                                              *(p + 1 for p in nova.todos_os_pids)])
                self.dados.gids_movidos = dict(gids_movidos)
                self.salvar()
            except BaseException:
                self.dados.sequencia, self.dados.proximo_pid, self.dados.gids_movidos = antes
                for pid in gravados:
                    try:
                        self._arquivo_v2(pid).unlink(missing_ok=True)
                    except OSError:
                        log.warning("p%d.json ficou (vai para as apagadas)", pid,
                                    exc_info=True)
                raise
            with self._trava_do_cache:
                for pid in paginas:             # a velha não é levada à geometria nova
                    self._modelos.pop(pid, None)
                    self._estados.pop(pid, None)
            self._trocar_sequencia(nova)
            resumos: Dict[int, Optional[dict]] = {}
            for pid, pagina in paginas.items():
                if pagina is None:
                    continue
                try:
                    self._gravar(pagina, livro=False)
                except OSError:
                    log.warning("a página p%d fica com o gravador", pid, exc_info=True)
                    self.agendar(pagina)
                else:
                    resumos[pid] = self.resumo.do_modelo(pagina)
                    self._trocadas[pid] = (self._carimbo_do_pid(pid), pagina.proximo_n)
                    self._guardar_no_cache(pagina, foto_nova=True)
            for pid, pagina in paginas.items():
                if pagina is None:
                    try:
                        self._arquivo_v2(pid).unlink(missing_ok=True)
                        resumos[pid] = None
                    except OSError:
                        log.warning("p%d.json não saiu (vai para as apagadas)", pid,
                                    exc_info=True)
            try:
                self.resumo.atualizar_varias(resumos)
            except OSError:
                # As páginas estão gravadas; o livro.json se refaz delas ao abrir.
                log.warning("o livro.json não foi atualizado", exc_info=True)

    def posicao_do_pid(self, pid: int) -> Optional[int]:
        """A posição no livro da página `pid`, ou None (fora da sequência)."""
        return self.sequencia.posicao_de(pid)

    def _montar_sequencia(self, gravar: bool) -> Tuple[sq.Sequencia, int]:
        """A sequência gravada (v3), ou a montada dos dados da v2. O projeto da v3 sem ela
        (o projeto novo, ou um `projeto.json` que a perdeu) a monta pela ordem do PDF e, com
        `gravar`, a grava já; o da v2 só para leitura a tem só na memória."""
        if self.dados.sequencia is not None:
            return self._sequencia_lida(gravar)
        sequencia, proximo = self._sequencia_da_v2(gravar)
        if (gravar and self.dados.versao >= VERSAO and not self.somente_leitura
                and self.fonte.is_file()):
            self.dados.sequencia = sequencia.para_json()
            self.dados.proximo_pid = max(self.dados.proximo_pid, proximo)
            self.salvar()
        return sequencia, proximo

    def _sequencia_lida(self, gravar: bool) -> Tuple[sq.Sequencia, int]:
        """A sequência do `projeto.json`. Um `p<pid>.json` que não está nela nem nas apagadas
        (uma queda entre gravações, §12.4) entra nas apagadas, no fim; todo arquivo em disco
        fica abaixo do próximo `pid`."""
        try:
            sequencia = sq.Sequencia.de_json(self.dados.sequencia)
        except (KeyError, TypeError, ValueError) as erro:
            raise ProjetoInvalido(f"A sequência do livro em {ARQUIVO_DO_PROJETO} está "
                                  f"ilegível: {erro}") from erro
        conhecidos = set(sequencia.todos_os_pids)
        em_disco = sorted(int(a.stem[1:]) for a in (self.pasta / PASTA_DE_PAGINAS).glob("p*.json")
                          if a.stem[1:].isdigit())
        # A página da sequência que o `livro.json` não cita (uma queda entre a página e o
        # livro) entra nele agora: o resumo, a gaveta e a fila do livro a mostram.
        livro = self.resumo.carregar()
        for pid in em_disco:
            if pid in conhecidos and str(pid) not in livro["paginas"]:
                try:
                    pagina = pagina_de_json(json.loads(
                        self._arquivo_v2(pid).read_text(encoding="utf-8")))
                except (OSError, ValueError, TypeError, KeyError):
                    continue
                livro = self.resumo.citar(pid, self.resumo.do_modelo(pagina), gravar)
        todas = list(sequencia.entradas) + [a.entrada for a in sequencia.apagadas]
        # Página do PDF -> o pid que a tem (as do livro, na sequência ou apagadas).
        do_pdf = {e.pagina: e.pid for e in todas if e.fonte == sq.FONTE_DO_LIVRO}
        orfaos = []
        for pid in em_disco:
            if pid in conhecidos:
                continue
            try:
                pagina = pagina_de_json(json.loads(
                    self._arquivo_v2(pid).read_text(encoding="utf-8")))
            except (OSError, ValueError, TypeError, KeyError):
                continue
            dono = do_pdf.get(pagina.indice)
            if dono is not None and self._arquivo_v2(dono).is_file():
                # O perdedor de dois arquivos da mesma página (uma queda): o dono vale.
                log.warning("p%d.json repete a página %d do PDF, que é da p%d: fica fora do "
                            "livro", pid, pagina.indice + 1, dono)
                continue
            if pagina.indice < 0:
                # Uma inserida ou uma metade direita sem entrada: não se sabe a imagem dela, e
                # apontá-la para uma página do PDF mostraria os glifos noutra imagem.
                log.warning("p%d.json não é de uma página do PDF e saiu da sequência: fica "
                            "fora do livro, no disco", pid)
                continue
            orfaos.append(sq.Apagada(sq.Entrada(pid, sq.FONTE_DO_LIVRO, max(0, pagina.indice)),
                                     len(sequencia)))
        proximo = max([self.dados.proximo_pid, *(p + 1 for p in em_disco),
                       *(p + 1 for p in sequencia.todos_os_pids)])
        # As páginas do PDF que não estão em entrada nenhuma (uma sequência gravada curta, de
        # antes de a fonte voltar): no fim do livro, com pid novo.
        faltam = [k for k in range(self.origem.total_de_paginas()) if k not in do_pdf]
        novas = tuple(sq.Entrada(proximo + n, sq.FONTE_DO_LIVRO, k) for n, k in enumerate(faltam))
        proximo += len(novas)
        if orfaos or novas:
            if orfaos:
                log.warning("%d página(s) fora da sequência foram para as apagadas", len(orfaos))
            if novas:
                log.warning("%d página(s) do PDF fora da sequência entraram no fim do livro",
                            len(novas))
            sequencia = sq.Sequencia(sequencia.entradas + novas,
                                     sequencia.apagadas + tuple(orfaos))
            if gravar and not self.somente_leitura:
                self.dados.sequencia = sequencia.para_json()
                self.dados.proximo_pid = max(self.dados.proximo_pid, proximo)
                self.salvar()
        return sequencia, proximo

    def _sequencia_da_v2(self, gravar: bool = True) -> Tuple[sq.Sequencia, int]:
        """A sequência de um projeto da v2 (`sequencia.da_v2`): a ordem do PDF, os `pid`
        das páginas gravadas pelo `livro.json`, e os `p<pid>.json` que ele não cita (uma
        queda entre a página e o livro: o mais recente de cada índice entra, e o livro é
        atualizado), a v1 não migrada com `pid` = índice. Um arquivo v1 presente vence a
        página v2 do mesmo índice (o `backup-v1/` copiado de volta, CA-4.5): os `gid` e as
        amostras dele usam o `pid` = índice. Todo `p<pid>.json` em disco fica abaixo do
        próximo `pid`, mesmo o que não entra na sequência."""
        livro = self.resumo.carregar()
        gravados: Dict[int, int] = {}
        for chave, resumo in livro["paginas"].items():
            indice = resumo.get("pagina_da_fonte")
            if isinstance(indice, int) and indice >= 0:     # a inserida e a direita, não
                gravados[indice] = int(chave)
        orfaos = self._orfaos(livro, gravados)
        for indice, (pid, pagina) in orfaos.items():
            gravados[indice] = pid
        for indice in self._v1_so_leitura:      # aberto para gravar, a v1 já migrou
            gravados[indice] = indice
        em_disco = [int(a.stem[1:]) for a in (self.pasta / PASTA_DE_PAGINAS).glob("p*.json")
                    if a.stem[1:].isdigit()]
        piso = max([self.dados.proximo_pid, *(p + 1 for p in em_disco)])
        total = max([self.origem.total_de_paginas(), *(i + 1 for i in gravados)], default=0)
        sequencia, proximo = sq.da_v2(total, gravados, piso)
        for indice, (pid, pagina) in orfaos.items():
            self.resumo.citar(pid, self.resumo.do_modelo(pagina), gravar)
        return sequencia, proximo

    def _orfaos(self, livro: dict, gravados: Dict[int, int]) -> Dict[int, Tuple[int, Pagina]]:
        """índice -> (pid, página) dos `p<pid>.json` que o livro não cita, para os índices
        que ele não tem (ou cujo arquivo sumiu): o mais recente pelo `gravado_em` e, no
        empate, o `pid` maior."""
        citados = {int(k) for k in livro["paginas"]}
        achados: Dict[int, list] = {}
        for arquivo in (self.pasta / PASTA_DE_PAGINAS).glob("p*.json"):
            if not arquivo.stem[1:].isdigit() or int(arquivo.stem[1:]) in citados:
                continue
            try:
                bruto = json.loads(arquivo.read_text(encoding="utf-8"))
                pagina = pagina_de_json(bruto)
            except (OSError, ValueError, TypeError, KeyError):
                continue
            indice = pagina.indice
            if indice < 0:
                continue                    # não é uma página do PDF (a v2 não a conhece)
            if indice in gravados and self._arquivo_v2(gravados[indice]).is_file():
                continue                    # o livro já tem esta página, e o arquivo dela
            achados.setdefault(indice, []).append(
                (bruto.get("gravado_em", ""), pagina.pid, pagina))
        orfaos = {}
        for indice, lista in achados.items():
            _, pid, pagina = max(lista, key=lambda t: (t[0], t[1]))
            if len(lista) > 1:
                log.warning("a página %d tem %d arquivos sem o livro; vale o mais recente, p%d",
                            indice + 1, len(lista), pid)
            orfaos[indice] = (pid, pagina)
        return orfaos

    def _pagina_da_fonte(self, pagina: Pagina) -> int:
        """O índice da página no PDF do livro (na v2, o que dá a ordem do livro, §12.4): o da
        entrada dela na sequência, e não a posição (`pagina.indice`), que muda ao reordenar.
        A página que não é uma do PDF (a inserida) e a metade direita de uma divisão (a
        esquerda fica com o índice) gravam `FORA_DO_PDF`: o `backup-v2/` copiado de volta não
        as toma pela página do livro de mesmo número. Antes de a sequência existir (montando-a,
        ou refazendo o livro), a página veio do JSON, e o `indice` dela é o gravado."""
        sequencia = self._sequencia         # sem montar: quem monta chama daqui
        if sequencia is None:
            return pagina.indice
        entrada = sequencia.entrada_de(pagina.pid)
        if entrada is None:
            apagada = sequencia.apagada(pagina.pid)
            entrada = None if apagada is None else apagada.entrada
        if entrada is None:
            return pagina.indice
        if entrada.fonte == sq.FONTE_DO_LIVRO and entrada.metade != "direita":
            return entrada.pagina
        return FORA_DO_PDF
