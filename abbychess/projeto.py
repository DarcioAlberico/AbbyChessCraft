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
primeira abertura, o v1 vai para `backup-v1/` e o projeto passa ao formato 2; cada página
v1 migra (pid = índice) e é gravada na primeira leitura dela. Copiar `backup-v1/` de volta
reabre o projeto como era (o arquivo v1 presente vence o v2 do mesmo pid).

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

import copy
import hashlib
import json
import logging
import math
import re
import threading
from collections import OrderedDict
import unicodedata
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Sequence, Tuple

from core.box_model import BoxEntry

from abbychess import gravacao as gv
from abbychess import procedencia
from abbychess import sequencia as sq
from abbychess.gravador import Gravador
from abbychess import zonas as zn
from abbychess.modelo import (FIGURINAS, GLIFOS_MARCADOS, LIDAS, NAO_RECONHECIDA, RECONHECIDA, VERIFICADA,
                              Box, Decisoes,
                              Pagina, foto, gid_de, proximo_estado, reconciliar, reenquadrar)
from abbychess.zonas import Zona

if TYPE_CHECKING:
    from abbychess.diagramas import DiagramaLido

log = logging.getLogger(__name__)

ARQUIVO_DO_PROJETO = "projeto.json"
PASTA_DE_PADROES = "padroes"
PASTA_DE_PAGINAS = "paginas"
#: A página como estava antes de o lote com "refazer" a reler (§4.6), uma por pid.
PASTA_ANTES_DO_LOTE = ".antes-do-lote"
#: As páginas que só têm glifos marcados à mão no modo de treino, sem o F5.
ARQUIVO_DAS_MARCADAS = "marcadas.json"
PASTA_DE_ZONAS = "zonas"
ARQUIVO_DO_LEXICO = "lexico.txt"
ARQUIVO_DO_LIVRO = "livro.json"
#: 2: o modelo v2 (passo 1b): páginas em `paginas/p<pid>.json`, com gids e decisões.
#: 3: a sequência do livro em `projeto.json` (passo L, §12.4): toda página tem `pid` gravado,
#: e as listas de páginas, as inclinações, `janela.json` e `lote.json` são por `pid`.
VERSAO = 3
#: A versão do formato de cada `paginas/p<pid>.json`. 3 (passo L): a geometria dos boxes,
#: o tamanho da fonte e os glifos fora do quadro; a 2 é lida como a geometria inteira.
VERSAO_DA_PAGINA = 3
VERSOES_DA_PAGINA = (2, 3)
#: Onde a primeira abertura v2 guarda o projeto v1 de antes (§4.3).
PASTA_DO_BACKUP_V1 = "backup-v1"
#: Onde a primeira abertura v3 guarda os arquivos da v2 que ela muda (§12.4, CA-12.7).
PASTA_DO_BACKUP_V2 = "backup-v2"
#: Os arquivos do projeto que guardam páginas por posição até a v2 e por `pid` desde a v3.
ARQUIVO_DE_INCLINACOES = "inclinacoes.json"
ARQUIVO_DA_JANELA = "janela.json"
ARQUIVO_DO_LOTE = "lote.json"
#: As listas de posições do `projeto.json` (em `extras`) que passam a `pid` na v3: o corpo
#: (`app.dialogos`), a amostra guiada (`livro`) e a camada de texto nativa (`nativo`).
LISTAS_DE_PAGINAS = ("intervalo_do_corpo", "candidatos_da_amostra_guiada",
                     "paginas_da_amostra_guiada", "paginas_da_camada_nativa")
#: E os mapas posição -> número (os pendentes da amostra guiada ao terminar).
MAPAS_DE_PAGINAS = ("pendentes_iniciais_da_amostra",)
#: Quantas páginas o projeto guarda em memória, no modelo (as outras relê do disco).
PAGINAS_EM_MEMORIA = 16
#: A versão do formato de `livro.json`; outra versão é refeita das páginas.
#: 2: a confiança 1,0 ganhou a faixa 100 do histograma; 3: o `pid` de cada página e os
#: estados de §4.4; 4: chaveado por `pid` (passo L), com o índice da página no PDF em cada
#: resumo (os caches anteriores são refeitos).
VERSAO_DO_LIVRO = 4
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
        #: `marcadas.json` e `livro.json` mudam juntos, e o `.tmp` de cada um é um só. A
        #: interface não espera por ela no caminho de uma edição (ver `_trava_do_cache`).
        self._trava_do_livro = threading.RLock()
        #: O cache das páginas (`_modelos`, `_estados`, `_a_gravar`): curta, sem disco. A
        #: ordem é sempre a do livro e depois a do cache, nunca o contrário.
        self._trava_do_cache = threading.RLock()
        self._travado = somente_leitura         # este objeto segura uma trava de só leitura
        #: As páginas lidas, no modelo (as mais recentes), por `pid`, e a foto
        #: (`modelo.foto`) de cada glifo na última gravação síncrona: quem grava listas de
        #: `BoxEntry` (o lote, as ferramentas) pode tê-los mudado no lugar, e só a foto diz o
        #: que mudou.
        self._modelos: "OrderedDict[int, Pagina]" = OrderedDict()
        self._estados: Dict[int, Dict[int, int]] = {}
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
        #: Avisado da thread do gravador quando uma página não grava: `(indice, erro)`.
        self.ao_falhar_gravacao = None
        #: As páginas (índices) que `fechar` não conseguiu gravar.
        self.nao_gravadas: List[int] = []

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
        projeto.sequencia               # agora, antes de qualquer render (o fitz e as threads)
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
            try:
                projeto.sequencia       # só na memória: nada é gravado
            except ProjetoInvalido:     # a sequência de um formato que esta versão não lê
                projeto._sequencia, projeto._proximo_pid = projeto._sequencia_da_v2()
            return projeto
        (pasta / PASTA_DE_PADROES).mkdir(exist_ok=True)
        (pasta / PASTA_DE_PAGINAS).mkdir(exist_ok=True)
        gv.limpar_temporarios(pasta)
        projeto = cls(pasta, dados)
        # A fonte antes da migração: a sequência da v3 tem uma entrada por página do PDF, e
        # sem o PDF o número de páginas não se sabe.
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
        versao_de_antes = dados.versao
        if dados.versao < VERSAO:
            try:
                # A cadeia (§12.4): a v1 passa à 2 (o `backup-v1/`), e a 2 à 3 (o `backup-v2/`).
                if dados.versao < 2:
                    projeto._preparar_migracao(bytes_do_projeto)
                    projeto.backups_da_migracao.append(pasta / PASTA_DO_BACKUP_V1)
                    projeto.migrado = True
                if projeto.fonte.is_file():
                    projeto._migrar_para_v3()
                    projeto.backups_da_migracao.append(pasta / PASTA_DO_BACKUP_V2)
                    projeto.migrado, mudou = True, False
                else:
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
                projeto.sequencia
                return projeto
        if mudou:
            try:
                projeto.salvar()
            except OSError as erro:     # mídia só de leitura: abre igual, sem gravar o ajuste
                log.warning("não deu para gravar %s ao abrir: %s", ARQUIVO_DO_PROJETO, erro)
        projeto.sequencia               # agora, antes de qualquer render (o fitz e as threads)
        if projeto.sequencia_gravada:
            projeto._completar_v3()     # o que uma queda no meio da migração deixou
        return projeto

    def fechar(self, limite: Optional[float] = 30.0) -> bool:
        """Espera o gravador gravar o que está pendente e solta a trava de só leitura que
        este objeto segura (uma vez só). Devolve se ficou tudo gravado."""
        gravou = True
        if self._gravador is not None:
            gravou = self._gravador.fechar(limite)
            self.nao_gravadas = [] if gravou else self.paginas_sujas()
            self._gravador = None
        if self._travado:
            self._travado = False
            gv.liberar(self.pasta)
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
        (devolve falso e nada é gravado). `resumo`: o de `resumo_do_modelo`, se quem chama
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
                                          else self._resumo_do_modelo(instantaneo))
            self.gravador.agendar(pagina.pid, instantaneo)
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

    def _gravar_instantaneo(self, pagina: Pagina) -> None:
        """A gravação do gravador. O arquivo da página é gravado sem a trava do livro: o
        instantâneo não muda, e só esta thread grava as páginas que a interface edita (o
        lote, que grava as dele, começa depois de `descarregar`). A trava vale só para o
        `livro.json`, que o lote também grava."""
        gv.gravar_json(self._arquivo_v2(pagina.pid),
                       _pagina_para_json(pagina, self._pagina_da_fonte(pagina)))
        with self._trava_do_livro:
            with self._trava_do_cache:
                # A foto é das gravações síncronas; esta página veio da interface, que não
                # muda nada no lugar, e a reconciliação a compara com o glifo mesmo.
                self._estados.pop(pagina.pid, None)
            self._atualizar_livro(pagina.pid, self._resumo_do_modelo(pagina))
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
        """O arquivo da página: o v2 (`paginas/p<pid>.json`) se existe, senão o v1 se ela
        ainda não migrou, senão onde o v2 vai ficar."""
        pid = self._pid_em(indice, criar=True)
        if self._arquivo_v2(pid).is_file():
            return self._arquivo_v2(pid)
        if self._arquivo_v1(indice).is_file():
            return self._arquivo_v1(indice)
        return self._arquivo_v2(pid)

    def _arquivo_v1(self, indice: int) -> Path:
        return self.pasta / PASTA_DE_PAGINAS / f"{indice + 1:04d}.json"

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
        """A página como está, sem passar pelo cache e sem migrar a v1 (o índice da busca,
        numa thread: §11, um escritor só): o instantâneo da que está na memória, a v1 lida
        como v2, ou o JSON v2 gravado; None se nada foi gravado dela."""
        modelo = self.modelo_em_memoria(indice)
        if modelo is not None:
            return modelo.instantaneo()
        if self._tem_v1(indice):
            with self._trava_do_livro:          # a interface pode migrá-la agora
                if self._tem_v1(indice):
                    return self._ler_v1(indice)
            modelo = self.modelo_em_memoria(indice)     # migrada: na memória, ou no v2
            if modelo is not None:
                return modelo.instantaneo()
        arquivo = self.arquivo_da_pagina(indice)
        if arquivo is None:
            return None
        try:
            return self._de_json(json.loads(arquivo.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return None

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
                    or self._tem_v1(pagina.indice) or self.carimbo(pagina.indice) != carimbo):
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
        """A página no modelo v2, ou `None` se nada foi gravado dela. Uma página v1 é
        migrada e gravada aqui, na primeira leitura (§4.3)."""
        pid = self._pid_em(indice)              # antes das travas (a do livro, se montar)
        if pid is None:
            return None                         # fora do livro: nada gravado
        v1 = not self.somente_leitura and self._tem_v1(indice)     # o stat, fora das travas
        with self._trava_do_cache:              # o caminho comum, sem esperar o disco
            em_cache = self._modelos.get(pid)
            if em_cache is not None and not v1:
                self._modelos.move_to_end(pid)
                return em_cache
        with self._trava_do_livro:
            em_cache = self._modelos.get(pid)
            # Um v1 que apareceu (o `backup-v1/` copiado de volta) vence a página em
            # memória; em só leitura nada migra, e a página em memória vale.
            v1 = (em_cache is None or not self.somente_leitura) and self._tem_v1(indice)
            if em_cache is not None and not v1:
                self._modelos.move_to_end(pid)
                return em_cache
            if v1:
                pagina = self._migrar(indice)
            else:
                arquivo = self._arquivo_v2_de(indice)
                if arquivo is None:
                    return None
                pagina = self._de_json(json.loads(arquivo.read_text(encoding="utf-8")))
            self._guardar_no_cache(pagina, foto_nova=True)
            return pagina

    def _de_json(self, bruto: dict) -> Pagina:
        """A página do JSON, com a posição dela no livro (a da sequência, e não o `indice`
        gravado no arquivo, que a sequência deixa de seguir no passo L)."""
        pagina = _pagina_de_json(bruto)
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

    def _gravar(self, pagina: Pagina) -> None:
        """A página e o resumo dela em `livro.json` (com a trava do livro)."""
        dados = _pagina_para_json(pagina, self._pagina_da_fonte(pagina))
        gv.gravar_json(self._arquivo_v2(pagina.pid), dados)
        with self._trava_do_cache:
            # A foto da gravação, do mesmo `as_state()` que foi para o JSON.
            self._estados[pagina.pid] = {b[0]: hash(tuple(b[1])) for b in dados["boxes"]}
        self._atualizar_livro(pagina.pid, self._resumo_do_modelo(pagina))

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
            if pid in sujas or saiu is pagina:
                continue                    # a página com gravação pendente fica
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
        treino: ela é gravada, mas não conta como lida (`paginas_lidas`). `reconheceu`
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

    # ------------------------------------------------------------------
    # Antes do lote (§4.6)
    # ------------------------------------------------------------------
    def _arquivo_antes_do_lote(self, pid: int) -> Path:
        return self.pasta / PASTA_DE_PAGINAS / PASTA_ANTES_DO_LOTE / f"p{pid}.json"

    def guardar_antes_do_lote(self, pagina: Pagina) -> None:
        """A página como está agora, antes de o lote com "refazer" a reler: o lote não entra
        no desfazer, e "Voltar ao estado antes do lote" a restaura."""
        gv.gravar_json(self._arquivo_antes_do_lote(pagina.pid),
                       _pagina_para_json(pagina.instantaneo(),
                                         self._pagina_da_fonte(pagina)))

    def tem_antes_do_lote(self, indice: int) -> bool:
        # O pid do modelo (em memória), e não o do `livro.json`: logo depois do lote, a
        # página ainda está com o gravador, e o livro não a tem.
        pagina = self.carregar_modelo(indice)
        return pagina is not None and self._arquivo_antes_do_lote(pagina.pid).is_file()

    def pid_da_pagina(self, indice: int) -> Optional[int]:
        """O pid da página na posição `indice`, sem ler o JSON dela (o da sequência), ou
        None fora do livro."""
        return self._pid_em(indice)

    def data_antes_do_lote(self, indice: int) -> Optional[datetime]:
        """Quando a cópia de antes do lote foi feita (a hora do arquivo), ou None."""
        pagina = self.carregar_modelo(indice)
        if pagina is None:
            return None
        arquivo = self._arquivo_antes_do_lote(pagina.pid)
        try:
            return datetime.fromtimestamp(arquivo.stat().st_mtime)
        except OSError:
            return None

    def voltar_ao_antes_do_lote(self, indice: int) -> Pagina:
        """Põe de volta a página copiada antes do lote (o JSON idêntico ao copiado), e a
        cópia sai. O gravador grava antes o que tem pendente: senão, a gravação dele passaria
        por cima da página restaurada; se ele não grava, nada muda (`OSError`). No projeto
        só para leitura, também não."""
        if self.somente_leitura:
            raise OSError("o projeto está aberto só para leitura")
        if not self.descarregar(10):
            raise OSError("há páginas que não puderam ser gravadas (veja a barra de status); "
                          "nada foi mudado")
        pid = self._pid_em(indice)
        with self._trava_do_livro:
            copia = None if pid is None else self._arquivo_antes_do_lote(pid)
            if copia is None or not copia.is_file():
                raise OSError(f"a página {indice + 1} não tem cópia de antes do lote")
            dados = copia.read_bytes()
            gv.gravar_bytes(self._arquivo_v2(pid), dados)
            pagina = self._de_json(json.loads(dados.decode("utf-8")))
            self._guardar_no_cache(pagina, foto_nova=True)
            self._atualizar_livro(pid, self._resumo_do_modelo(pagina))
            gv.apagar(copia)
            return pagina

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
        leitura do livro não despeja as páginas abertas). Uma página v1 não é migrada aqui:
        vai por `carregar_modelo`."""
        pid = self._pid_em(indice)
        if pid is None:
            return None
        with self._trava_do_cache:
            em_cache = self._modelos.get(pid)
        if em_cache is not None:
            return em_cache
        if self._tem_v1(indice):
            return self.carregar_modelo(indice)
        arquivo = self._arquivo_v2_de(indice)
        if arquivo is None:
            return None
        try:
            return self._de_json(json.loads(arquivo.read_text(encoding="utf-8")))
        except (OSError, ValueError):           # gravada agora mesmo pelo gravador: na próxima
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

    def paginas_lidas(self) -> List[int]:
        """As páginas reconhecidas (F5 ou lote), sem as que só têm glifos marcados."""
        return sorted(i for i, r in self.resumo_do_livro().items() if r["estado"] in LIDAS)

    def pagina_reconhecida(self, indice: int) -> bool:
        resumo = self.resumo_do_livro().get(indice)
        return resumo is not None and resumo["estado"] in LIDAS

    def estado_da_pagina(self, indice: int) -> str:
        resumo = self.resumo_do_livro().get(indice)
        return resumo["estado"] if resumo is not None else NAO_RECONHECIDA

    # ------------------------------------------------------------------
    # A migração do v1 (§4.3)
    # ------------------------------------------------------------------
    def _tem_v1(self, indice: int) -> bool:
        return (self._arquivo_v1(indice).is_file()
                or (self.pasta / PASTA_DE_ZONAS / f"{indice + 1:04d}.json").is_file())

    def _indices_v1(self) -> List[int]:
        indices = set()
        for pasta in (self.pasta / PASTA_DE_PAGINAS, self.pasta / PASTA_DE_ZONAS):
            if pasta.is_dir():
                indices |= {int(p.stem) - 1 for p in pasta.glob("*.json") if p.stem.isdigit()}
        return sorted(indices)

    def _marcadas_v1(self) -> set:
        arquivo = self.pasta / PASTA_DE_PAGINAS / ARQUIVO_DAS_MARCADAS
        if not arquivo.is_file():
            return set()
        try:
            return {int(i) - 1 for i in json.loads(arquivo.read_text(encoding="utf-8"))}
        except (ValueError, TypeError):
            return set()

    def _ler_v1(self, indice: int) -> Pagina:
        """A página v1 (página, áreas, marcadas) como modelo v2, sem gravar: pid = índice."""
        from abbychess.diagramas import DiagramaLido

        pagina = Pagina(pid=indice, indice=indice)
        arquivo = self._arquivo_v1(indice)
        if arquivo.is_file():
            bruto = json.loads(arquivo.read_text(encoding="utf-8"))
            pagina.boxes = [Box(gid_de(indice, n), BoxEntry.from_state(tuple(estado)))
                            for n, estado in enumerate(bruto.get("boxes", []))]
            pagina.proximo_n = len(pagina.boxes)
            pagina.tabuleiros = [tuple(int(v) for v in t) for t in bruto.get("tabuleiros", [])]
            pagina.diagramas = com_ids_de_diagramas(
                [DiagramaLido.de_json(d) for d in bruto.get("diagramas", [])])
            pagina.estado = GLIFOS_MARCADOS if indice in self._marcadas_v1() else RECONHECIDA
        zonas = self.pasta / PASTA_DE_ZONAS / f"{indice + 1:04d}.json"
        if zonas.is_file():
            bruto = json.loads(zonas.read_text(encoding="utf-8"))
            pagina.zonas = zn.com_ids([Zona.de_dict(z) for z in bruto.get("zonas", [])])
        return pagina

    def _migrar(self, indice: int) -> Pagina:
        """Grava a página v1 como v2 e tira os arquivos v1 dela (a cópia está em `backup-v1/`).
        Um arquivo v1 presente vence o v2 de mesmo pid: é o `backup-v1/` copiado de volta
        (CA-4.5)."""
        pagina = self._ler_v1(indice)
        if self.somente_leitura:
            return pagina
        self.salvar_modelo(pagina)
        gv.apagar(self._arquivo_v1(indice))
        gv.apagar(self.pasta / PASTA_DE_ZONAS / f"{indice + 1:04d}.json")
        return pagina

    def _preparar_migracao(self, bruto_do_projeto: bytes) -> None:
        """Na primeira abertura v2 de um projeto v1: `backup-v1/` com as páginas, as áreas e o
        `projeto.json` de antes, e o contador de pids depois de todo índice v1 e todo pid já
        gravado. As páginas migram depois, uma a uma, na primeira leitura."""
        backup = self.pasta / PASTA_DO_BACKUP_V1
        if not (backup / ARQUIVO_DO_PROJETO).is_file():
            for nome in (PASTA_DE_PAGINAS, PASTA_DE_ZONAS):
                origem = self.pasta / nome
                if origem.is_dir():
                    for arquivo in sorted(origem.glob("*.json")):
                        if arquivo.stem.isdigit() or arquivo.name == ARQUIVO_DAS_MARCADAS:
                            gv.gravar_bytes(backup / nome / arquivo.name, arquivo.read_bytes())
            gv.gravar_bytes(backup / ARQUIVO_DO_PROJETO, bruto_do_projeto)
        pids = [int(p.stem[1:]) for p in (self.pasta / PASTA_DE_PAGINAS).glob("p*.json")
                if p.stem[1:].isdigit()]
        self.dados.proximo_pid = max([self.dados.proximo_pid, *(i + 1 for i in self._indices_v1()),
                                      *(p + 1 for p in pids)])
        self.dados.versao = 2                       # a 3 vem logo depois (`_migrar_para_v3`)
        self.salvar()
        gv.apagar(self.pasta / ARQUIVO_DO_LIVRO)        # o cache é refeito com os pids

    def _migrar_para_v3(self) -> None:
        """Da v2 à v3 (§12.4, CA-12.7): `backup-v2/` com os arquivos que mudam, a sequência
        montada dos dados da v2 (toda página ganha `pid` gravado), as listas de páginas
        passadas a `pid`, e o `projeto.json` com a sequência e a `versao` 3 numa gravação só.
        Uma queda antes dela deixa o projeto na v2 (migra de novo na próxima abertura); depois
        dela, `inclinacoes.json`, `janela.json` e `lote.json` são passados a `pid`, e quem os lê
        aceita também a forma antiga (uma queda no meio não perde nada). Os JSON de página não
        mudam."""
        backup = self.pasta / PASTA_DO_BACKUP_V2
        if not (backup / ARQUIVO_DO_PROJETO).is_file():
            for nome in (ARQUIVO_DE_INCLINACOES, ARQUIVO_DA_JANELA, ARQUIVO_DO_LOTE,
                         ARQUIVO_DO_PROJETO):        # o projeto.json por último: ele marca o backup
                arquivo = self.pasta / nome
                if arquivo.is_file():
                    gv.gravar_bytes(backup / nome, arquivo.read_bytes())
        sequencia, proximo = self._sequencia_da_v2()
        self._listas_para_pids(sequencia)
        self.dados.sequencia = sequencia.para_json()
        self.dados.proximo_pid = max(self.dados.proximo_pid, proximo)
        self.dados.versao = VERSAO
        self.salvar()
        self._sequencia, self._proximo_pid = sequencia, max(self._proximo_pid, proximo)

    def _completar_v3(self) -> None:
        """Os arquivos que a migração passa a `pid` depois do `projeto.json` (as inclinações,
        `janela.json`, `lote.json`): a cada abertura da v3, só o que ainda está na forma da v2
        (uma queda no meio da migração). Uma falha de gravação só avisa no log: quem os lê
        aceita a forma da v2."""
        if self.somente_leitura:
            return
        try:
            self._inclinacoes_para_pids(self.sequencia)
            self._janela_e_lote_para_pids(self.sequencia)
        except OSError as erro:
            log.warning("os arquivos de %s não passaram todos a pid (%s); a próxima abertura "
                        "tenta de novo", self.pasta, erro)

    def _listas_para_pids(self, sequencia: sq.Sequencia) -> None:
        """As listas de posições do `projeto.json` (a v2 escreve o índice do PDF, que na
        migração é a posição) passam a `pid`; a posição fora do livro sai."""
        extras = self.dados.extras

        def pid(valor) -> Optional[int]:
            posicao = _inteiro(valor)
            if posicao is None:
                return None
            return sequencia.pid_em(posicao) if 0 <= posicao < len(sequencia) else None

        for chave in LISTAS_DE_PAGINAS:
            if isinstance(extras.get(chave), (list, tuple)):
                extras[chave] = [p for p in map(pid, extras[chave]) if p is not None]
        for chave in MAPAS_DE_PAGINAS:
            if isinstance(extras.get(chave), dict):
                extras[chave] = {str(p): n for k, n in extras[chave].items()
                                 if (p := pid(k)) is not None}

    def _inclinacoes_para_pids(self, sequencia: sq.Sequencia) -> None:
        """`inclinacoes.json` por `pid` (a chave da v3, `pagina._chave_da_inclinacao`)."""
        arquivo = self.pasta / ARQUIVO_DE_INCLINACOES
        if not arquivo.is_file():
            return
        try:
            bruto = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return                              # ilegível: a fonte o ignora e mede de novo
        if not any(chave.isdigit() for chave in bruto):
            return                              # já por pid
        do_pdf = {e.pagina: e.pid for e in sequencia.entradas if e.fonte == sq.FONTE_DO_LIVRO}
        novo = {}
        for chave, angulo in bruto.items():
            if chave.isdigit() and int(chave) in do_pdf:
                novo[f"p{do_pdf[int(chave)]}:inteira:0"] = angulo
            elif not chave.isdigit():
                novo[chave] = angulo
        gv.gravar_json(arquivo, dict(sorted(novo.items())))

    def _janela_e_lote_para_pids(self, sequencia: sq.Sequencia) -> None:
        """A página aberta em `janela.json` e as páginas de `lote.json` com o `pid` delas."""
        def pid(valor) -> Optional[int]:
            return (sequencia.pid_em(valor) if isinstance(valor, int)
                    and 0 <= valor < len(sequencia) else None)

        for nome in (ARQUIVO_DA_JANELA, ARQUIVO_DO_LOTE):
            arquivo = self.pasta / nome
            if not arquivo.is_file():
                continue
            try:
                bruto = json.loads(arquivo.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue                        # ilegível: quem o lê avisa, como antes
            if not isinstance(bruto, dict):
                continue
            if nome == ARQUIVO_DA_JANELA:
                if "pid" in bruto:
                    continue                    # já por pid
                bruto["pid"] = pid(bruto.get("pagina"))
            else:
                if bruto.get("pids"):
                    continue
                for chave in ("paginas", "reler_depois"):
                    bruto[chave] = [p for p in map(pid, bruto.get(chave) or []) if p is not None]
                bruto["pids"] = True
            gv.gravar_json(arquivo, bruto)

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
            valor = _inteiro(valor)
            if valor is None:
                continue
            posicao = self.posicao_do_pid(valor) if self.sequencia_gravada else valor
            if posicao is not None and 0 <= posicao < len(self.sequencia):
                saida.append(posicao)
        return saida

    def migrar_tudo(self) -> int:
        """Migra agora todas as páginas v1 que faltam (as ferramentas e os testes)."""
        feitas = 0
        for indice in self._indices_v1():
            if self.carregar_modelo(indice) is not None:
                feitas += 1
        return feitas

    # ------------------------------------------------------------------
    # livro.json: o resumo de cada página, sem abrir as páginas
    # ------------------------------------------------------------------
    def resumo_do_livro(self) -> Dict[int, dict]:
        """Posição da página no livro -> o resumo dela (`_resumo_do_modelo`), de toda página
        gravada que está na sequência."""
        sequencia = self.sequencia
        # Os pendentes antes do livro: uma página que o gravador termine entre as duas
        # leituras já está no livro lido, e não some por uma chamada.
        with self._trava_do_cache:
            pendentes = {pid: r for pid, (_, r) in self._a_gravar.items()}
        livro = self._livro                     # trocado inteiro a cada gravação
        if livro is None:
            with self._trava_do_livro:
                livro = self._carregar_livro()
        por_pid = {int(k): v for k, v in livro["paginas"].items()}
        por_pid.update(pendentes)
        resumo = {}
        for pid, r in por_pid.items():
            posicao = sequencia.posicao_de(pid)
            if posicao is not None:
                resumo[posicao] = r
        # Cópia funda: o cache não vaza.
        return {i: json.loads(json.dumps(resumo[i])) for i in sorted(resumo)}

    # ------------------------------------------------------------------
    # A sequência do livro (§12.4)
    # ------------------------------------------------------------------
    @property
    def sequencia(self) -> sq.Sequencia:
        """A ordem das páginas e o `pid` de cada uma (montada na primeira pergunta)."""
        sequencia = self._sequencia
        if sequencia is None:
            with self._trava_do_livro:
                if self._sequencia is None:
                    self._sequencia, self._proximo_pid = self._montar_sequencia()
                sequencia = self._sequencia
        return sequencia

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
            self.dados.sequencia = nova.para_json()
            self.dados.proximo_pid = max([self.dados.proximo_pid, self._proximo_pid,
                                          *(p + 1 for p in nova.todos_os_pids)])
            try:
                self.salvar()
            except BaseException:
                self.dados.sequencia, self.dados.proximo_pid = antes
                raise
            self._trocar_sequencia(nova)

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
            self.sequencia                      # o próximo pid vem dela
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
            return sequencia.posicao_de(pid_de(gid)), gid
        guardado = self._posicoes_do_pdf
        if guardado is None or guardado[0] is not sequencia:   # uma vez por sequência
            posicoes: Dict[int, int] = {}
            for posicao, entrada in enumerate(sequencia.entradas):
                if entrada.fonte == sq.FONTE_DO_LIVRO:
                    posicoes.setdefault(entrada.pagina, posicao)   # a primeira: a esquerda
            guardado = self._posicoes_do_pdf = (sequencia, posicoes)
        return guardado[1].get(pagina_do_nome), None

    def posicao_do_pid(self, pid: int) -> Optional[int]:
        """A posição no livro da página `pid`, ou None (fora da sequência)."""
        return self.sequencia.posicao_de(pid)

    def total_de_paginas(self) -> int:
        """Quantas páginas a fonte do livro tem (sem a fonte: 0)."""
        if not self.fonte.is_file():
            return 0
        if not self.fonte_e_pdf:
            return 1
        import fitz

        try:
            with fitz.open(str(self.fonte)) as documento:
                return documento.page_count
        except (RuntimeError, ValueError, OSError):
            return 0

    def _montar_sequencia(self) -> Tuple[sq.Sequencia, int]:
        """A sequência gravada (v3), ou a montada dos dados da v2. O projeto da v3 sem ela
        (o projeto novo, ou um `projeto.json` que a perdeu) a monta pela ordem do PDF e a grava
        já; o da v2 só para leitura a tem só na memória."""
        if self.dados.sequencia is not None:
            return self._sequencia_lida()
        sequencia, proximo = self._sequencia_da_v2()
        if self.dados.versao >= VERSAO and not self.somente_leitura and self.fonte.is_file():
            self.dados.sequencia = sequencia.para_json()
            self.dados.proximo_pid = max(self.dados.proximo_pid, proximo)
            self.salvar()
        return sequencia, proximo

    def _sequencia_lida(self) -> Tuple[sq.Sequencia, int]:
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
        livro = self._carregar_livro()
        for pid in em_disco:
            if pid in conhecidos and str(pid) not in livro["paginas"]:
                try:
                    pagina = _pagina_de_json(json.loads(
                        self._arquivo_v2(pid).read_text(encoding="utf-8")))
                except (OSError, ValueError, TypeError, KeyError):
                    continue
                resumo = self._resumo_do_modelo(pagina)
                if self.somente_leitura:
                    self._livro = livro = {**livro, "paginas": {**livro["paginas"],
                                                                str(pid): resumo}}
                else:
                    self._atualizar_livro(pid, resumo)
                    livro = self._carregar_livro()
        todas = list(sequencia.entradas) + [a.entrada for a in sequencia.apagadas]
        # Página do PDF -> o pid que a tem (as do livro, na sequência ou apagadas).
        do_pdf = {e.pagina: e.pid for e in todas if e.fonte == sq.FONTE_DO_LIVRO}
        orfaos = []
        for pid in em_disco:
            if pid in conhecidos:
                continue
            try:
                pagina = _pagina_de_json(json.loads(
                    self._arquivo_v2(pid).read_text(encoding="utf-8")))
            except (OSError, ValueError, TypeError, KeyError):
                continue
            dono = do_pdf.get(pagina.indice)
            if dono is not None and self._arquivo_v2(dono).is_file():
                continue                        # o perdedor de dois arquivos da mesma página
            orfaos.append(sq.Apagada(sq.Entrada(pid, sq.FONTE_DO_LIVRO, max(0, pagina.indice)),
                                     len(sequencia)))
        proximo = max([self.dados.proximo_pid, *(p + 1 for p in em_disco),
                       *(p + 1 for p in sequencia.todos_os_pids)])
        # As páginas do PDF que não estão em entrada nenhuma (uma sequência gravada curta, de
        # antes de a fonte voltar): no fim do livro, com pid novo.
        faltam = [k for k in range(self.total_de_paginas()) if k not in do_pdf]
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
            if not self.somente_leitura:
                self.dados.sequencia = sequencia.para_json()
                self.dados.proximo_pid = max(self.dados.proximo_pid, proximo)
                self.salvar()
        return sequencia, proximo

    def _sequencia_da_v2(self) -> Tuple[sq.Sequencia, int]:
        """A sequência de um projeto da v2 (`sequencia.da_v2`): a ordem do PDF, os `pid`
        das páginas gravadas pelo `livro.json`, e os `p<pid>.json` que ele não cita (uma
        queda entre a página e o livro: o mais recente de cada índice entra, e o livro é
        atualizado), a v1 não migrada com `pid` = índice. Um arquivo v1 presente vence a
        página v2 do mesmo índice (o `backup-v1/` copiado de volta, CA-4.5): os `gid` e as
        amostras dele usam o `pid` = índice. Todo `p<pid>.json` em disco fica abaixo do
        próximo `pid`, mesmo o que não entra na sequência."""
        livro = self._carregar_livro()
        gravados: Dict[int, int] = {}
        for chave, resumo in livro["paginas"].items():
            if isinstance(resumo.get("pagina_da_fonte"), int):
                gravados[resumo["pagina_da_fonte"]] = int(chave)
        orfaos = self._orfaos(livro, gravados)
        for indice, (pid, pagina) in orfaos.items():
            gravados[indice] = pid
        v1 = self._indices_v1()
        for indice in v1:
            gravados[indice] = indice
        em_disco = [int(a.stem[1:]) for a in (self.pasta / PASTA_DE_PAGINAS).glob("p*.json")
                    if a.stem[1:].isdigit()]
        piso = max([self.dados.proximo_pid, *(p + 1 for p in em_disco)])
        total = max([self.total_de_paginas(), *(i + 1 for i in gravados)], default=0)
        sequencia, proximo = sq.da_v2(total, gravados, (), piso)
        for indice, (pid, pagina) in orfaos.items():
            resumo = self._resumo_do_modelo(pagina)
            if self.somente_leitura:            # só na memória; troca, não muda no lugar
                livro = self._carregar_livro()
                self._livro = {**livro, "paginas": {**livro["paginas"], str(pid): resumo}}
            else:
                self._atualizar_livro(pid, resumo)
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
                pagina = _pagina_de_json(bruto)
            except (OSError, ValueError, TypeError, KeyError):
                continue
            indice = pagina.indice
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
        """O `livro.json` como ele deve ser, lendo todas as páginas gravadas (v2 e as v1 que
        ainda não migraram, sem migrá-las)."""
        por_indice: Dict[int, Tuple[tuple, Pagina]] = {}
        for arquivo in sorted((self.pasta / PASTA_DE_PAGINAS).glob("p*.json")):
            if not arquivo.stem[1:].isdigit():
                continue
            try:
                bruto = json.loads(arquivo.read_text(encoding="utf-8"))
                pagina = _pagina_de_json(bruto)
            except (OSError, ValueError, TypeError, KeyError):
                continue                # página ilegível: fica fora do resumo
            ordem = (bruto.get("gravado_em", ""), pagina.pid)
            if pagina.indice in por_indice:     # dois arquivos do mesmo índice: o mais recente
                log.warning("a página %d tem mais de um arquivo; vale o gravado por último",
                            pagina.indice + 1)
                if ordem < por_indice[pagina.indice][0]:
                    continue
            por_indice[pagina.indice] = (ordem, pagina)
        for indice in self._indices_v1():
            try:
                por_indice[indice] = ((), self._ler_v1(indice))
            except (OSError, ValueError, TypeError, KeyError):
                continue
        paginas = {str(p.pid): self._resumo_do_modelo(p) for _, p in por_indice.values()}
        return {"versao": VERSAO_DO_LIVRO,
                "paginas": dict(sorted(paginas.items(), key=lambda kv: int(kv[0])))}

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

    def _atualizar_livro(self, pid: int, resumo: dict) -> None:
        with self._trava_do_livro:
            livro = self._carregar_livro()
            paginas = {**livro["paginas"], str(pid): resumo}
            novo = {"versao": livro["versao"],
                    "paginas": dict(sorted(paginas.items(), key=lambda kv: int(kv[0])))}
            gv.gravar_json(self.pasta / ARQUIVO_DO_LIVRO, novo)
            self._livro = novo                  # o cache só muda depois de gravado

    def _pagina_da_fonte(self, pagina: Pagina) -> int:
        """O índice da página no PDF do livro (na v2, o que dá a ordem do livro, §12.4): o da
        entrada dela na sequência, e não a posição (`pagina.indice`), que muda ao reordenar.
        Antes de a sequência existir (montando-a, ou refazendo o livro), a página veio do JSON,
        e o `indice` dela é o gravado: o do PDF."""
        sequencia = self._sequencia         # sem montar: quem monta chama daqui
        entrada = sequencia.entrada_de(pagina.pid) if sequencia is not None else None
        if entrada is not None and entrada.fonte == sq.FONTE_DO_LIVRO:
            return entrada.pagina
        return pagina.indice

    def resumo_do_modelo(self, pagina: Pagina) -> dict:
        """O resumo da página no `livro.json` (sem mudar nada: vale numa thread)."""
        return self._resumo_do_modelo(pagina)

    def _resumo_do_modelo(self, pagina: Pagina) -> dict:
        tabuleiros = len(pagina.tabuleiros)
        conferidos = sum(1 for d in pagina.diagramas if d.conferido)
        return {"pid": pagina.pid, "pagina_da_fonte": self._pagina_da_fonte(pagina),
                "estado": pagina.estado,
                **resumo_das_confiancas(pagina.entries(), self.dados.limiares,
                                        [b.revisado for b in pagina.boxes]),
                "diagramas": tabuleiros,
                "diagramas_por_conferir": max(0, tabuleiros - conferidos),
                # Alguma figurina lida (o modo "livro" das peças, §6.4, sem abrir as páginas).
                "figurinas": any(b.entry.char in FIGURINAS for b in pagina.boxes)}


def _inteiro(valor) -> Optional[int]:
    """O número de página de uma lista gravada, ou None (texto, `Infinity`, fração, `true`)."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, float):
        return int(valor) if valor.is_integer() else None
    try:
        return int(valor)
    except (TypeError, ValueError, OverflowError):
        return None


def _pagina_para_json(pagina: Pagina, pagina_da_fonte: Optional[int] = None) -> dict:
    """O JSON da página. O `indice` gravado é o da página no PDF (`pagina_da_fonte`,
    §12.4), e não a posição no livro, que muda ao reordenar; sem ele, o da página."""
    quadro, giro = pagina.geometria
    return {
        "versao": VERSAO_DA_PAGINA, "pid": pagina.pid,
        "indice": pagina.indice if pagina_da_fonte is None else pagina_da_fonte,
        "geometria": [None if quadro is None else list(quadro), int(giro)],
        "tamanho": None if pagina.tamanho is None else list(pagina.tamanho),
        "fora": [[lugar, box.para_json()] for lugar, box in pagina.fora],
        "areas_fora": [[tipo, lugar, _area_para_json(tipo, objeto), aparada]
                       for tipo, lugar, objeto, aparada in pagina.areas_fora],
        "estado": pagina.estado, "proximo_n": pagina.proximo_n,
        "gravado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "boxes": [b.para_json() for b in pagina.boxes],
        "tabuleiros": [list(map(int, t)) for t in pagina.tabuleiros],
        "diagramas": [d.para_json() for d in pagina.diagramas],
        "zonas": [z.como_dict() for z in pagina.zonas],
        "decisoes": pagina.decisoes.para_json(),
    }


def _pagina_de_json(bruto: dict) -> Pagina:
    from abbychess.diagramas import DiagramaLido

    if bruto.get("versao") not in VERSOES_DA_PAGINA:
        raise ValueError(f"página de versão {bruto.get('versao')!r}")
    return Pagina(pid=int(bruto["pid"]), indice=int(bruto["indice"]),
                  boxes=[Box.de_json(b) for b in bruto.get("boxes", [])],
                  tabuleiros=[tuple(int(v) for v in t) for t in bruto.get("tabuleiros", [])],
                  diagramas=[DiagramaLido.de_json(d) for d in bruto.get("diagramas", [])],
                  zonas=[Zona.de_dict(z) for z in bruto.get("zonas", [])],
                  decisoes=Decisoes.de_json(bruto.get("decisoes")),
                  estado=bruto.get("estado", RECONHECIDA),
                  proximo_n=int(bruto.get("proximo_n", 0)),
                  geometria=_geometria_de(bruto.get("geometria")),
                  tamanho=None if bruto.get("tamanho") is None
                  else tuple(int(v) for v in bruto["tamanho"]),
                  fora=tuple((int(lugar), Box.de_json(b)) for lugar, b in bruto.get("fora", [])),
                  areas_fora=tuple((tipo, int(lugar), _area_de_json(tipo, objeto), bool(aparada))
                                   for tipo, lugar, objeto, aparada
                                   in bruto.get("areas_fora", [])))


def _area_para_json(tipo: str, objeto):
    if tipo == "zona":
        return objeto.como_dict()
    if tipo == "diagrama":
        return objeto.para_json()
    return [int(v) for v in objeto]


def _area_de_json(tipo: str, bruto):
    from abbychess.diagramas import DiagramaLido

    if tipo == "zona":
        return Zona.de_dict(bruto)
    if tipo == "diagrama":
        return DiagramaLido.de_json(bruto)
    if tipo == "tabuleiro":
        return tuple(int(v) for v in bruto)
    raise ValueError(f"área guardada de tipo {tipo!r}")


def _geometria_de(bruto) -> tuple:
    from abbychess import geometria as geo

    return geo.normalizar(bruto)


def com_ids_de_diagramas(diagramas):
    from abbychess.diagramas import com_ids

    return com_ids(diagramas)


def resumo_das_confiancas(boxes: Sequence[BoxEntry], limiares: Limiares,
                          revisados: Optional[Sequence[bool]] = None) -> dict:
    """Os boxes da página em `confirmados`, `sem_leitura` e o histograma do resto.

    O histograma tem faixas de 0,01 (a chave é o centésimo de baixo; 100 é a confiança
    1,0) e conta só os boxes lidos e não confirmados, os únicos que um limiar de revisão
    diferente mudaria de lado: com ele, `pendentes_pelo_histograma` dá os pendentes de
    outro limiar (de duas casas) sem abrir a página.
    """
    from abbychess.leitor import FONTE_NENHUMA, FONTES_CONFIRMADAS, precisa_revisao

    confirmados = sem_leitura = pendentes = 0
    histograma: Dict[int, int] = {}
    revisados = revisados or [False] * len(boxes)
    for b, revisado in zip(boxes, revisados):
        if not revisado and precisa_revisao(b.char, b.source, b.confidence, limiares):
            pendentes += 1
        if b.source in FONTES_CONFIRMADAS or revisado:      # o revisado é aceito (§6.3)
            confirmados += 1
        elif not b.char or b.source == FONTE_NENHUMA:
            sem_leitura += 1
        else:
            faixa = _faixa(b.confidence)
            histograma[faixa] = histograma.get(faixa, 0) + 1
    return {"boxes": len(boxes), "pendentes": pendentes, "confirmados": confirmados,
            "sem_leitura": sem_leitura,
            "histograma": {str(k): histograma[k] for k in sorted(histograma)}}


def pendentes_pelo_histograma(resumo: dict, revisao: float) -> int:
    """Os pendentes da página com o limiar `revisao` (de duas casas, de 0,00 a 1,00), pelo
    histograma."""
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
