"""Os metadados do livro exportado (§12.1): o `metadados.json` do projeto, a capa copiada para
a pasta dele, e os `epub.Metadados` que o EPUB e o DOCX levam. À parte de `exportar.py`
(SPEC-qualidade Q-E6, CA-Q-A1)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional, Tuple

from abbychess import gravacao as gv
from abbychess.projeto import ProjetoDeLivro

log = logging.getLogger(__name__)


#: O arquivo, na pasta do projeto, com os metadados do livro exportado (§12.1).
ARQUIVO_DE_METADADOS = "metadados.json"


#: Os campos de `metadados.json`, na ordem do formulário (§12.1).
CAMPOS_DE_METADADOS = ("titulo", "autores", "editora", "data", "assuntos", "direitos",
                       "identificador", "fonte", "capa")
#: Os campos que são listas.
LISTAS_DE_METADADOS = ("autores", "assuntos")
#: A data que o EPUB aceita (`dc:date`).
DATA_DOS_METADADOS = re.compile(r"\d{4}(-\d{2}(-\d{2})?)?")
#: O nome da capa copiada para a pasta do projeto (a extensão é a da origem).
NOME_DA_CAPA = "capa"


def ler_metadados(projeto: ProjetoDeLivro) -> dict:
    """O `metadados.json` do projeto como está, ou `{}` (sem arquivo, ou ilegível: aviso no
    log, e a exportação segue só com o título)."""
    import json

    arquivo = Path(projeto.pasta) / ARQUIVO_DE_METADADOS
    if not arquivo.is_file():
        return {}
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        log.warning("%s ilegível (%s): o EPUB sai só com o título.", arquivo, erro)
        return {}
    return dados if isinstance(dados, dict) else {}


def normalizar_metadados(dados: dict) -> dict:
    """Os campos conhecidos, sem espaços nas pontas, as listas como listas (um texto com
    `;` vira lista) e sem os vazios. Levanta `ValueError` com a data fora de AAAA-MM-DD."""
    saida: dict = {}
    for campo in CAMPOS_DE_METADADOS:
        valor = _normalizado(campo, dados.get(campo))
        if valor:
            saida[campo] = valor
    if "data" in saida and not DATA_DOS_METADADOS.fullmatch(saida["data"]):
        raise ValueError(f"A data {saida['data']!r} deve ser AAAA, AAAA-MM ou AAAA-MM-DD.")
    return saida


def _normalizado(campo: str, valor):
    """O valor do campo sem espaços nas pontas (a lista, item a item); vazio se não sobra
    nada."""
    if valor is None:
        return None
    if campo in LISTAS_DE_METADADOS:
        return _itens(valor)
    return str(valor).strip()


def _itens(valor) -> list:
    if isinstance(valor, str):
        itens = valor.split(";")
    elif isinstance(valor, (list, tuple)):
        itens = list(valor)
    else:                                       # um número, um objeto: vira um item
        itens = [valor]
    return [str(v).strip() for v in itens if v is not None and str(v).strip()]


def gravar_metadados(projeto: ProjetoDeLivro, dados: dict,
                     capa: Optional[Path] = None) -> dict:
    """Grava o `metadados.json` (atômico, como todo arquivo do projeto) e devolve o que foi
    gravado. `capa` é uma imagem escolhida fora do projeto: é copiada para a pasta dele
    (`capa.<ext>`) e o campo passa a apontá-la. Recusa (`SomenteLeitura`) em projeto só
    de leitura."""
    novos = normalizar_metadados(dados)
    pasta = Path(projeto.pasta)
    # As chaves que o formulário não conhece (escritas à mão) ficam; as dele valem o que ele
    # disse, e a vazia sai. O `autor` singular de antes dá lugar a `autores`.
    gravado = {k: v for k, v in ler_metadados(projeto).items()
               if k not in CAMPOS_DE_METADADOS and k != "autor"}
    gravado.update(novos)
    if capa is not None:
        extensao = _copiar_a_capa(Path(capa), pasta)
        gravado["capa"] = f"{NOME_DA_CAPA}{extensao}"
    gv.gravar_json(pasta / ARQUIVO_DE_METADADOS, gravado)
    if capa is not None:
        _apagar_as_outras_capas(pasta, extensao)
    return gravado


def _copiar_a_capa(capa: Path, pasta: Path) -> str:
    """A capa conferida e copiada para a pasta do projeto (`capa.<ext>`); devolve a extensão."""
    conteudo = capa.read_bytes()
    _conferir_capa(conteudo)
    extensao = capa.suffix.lower() if capa.suffix.lower() in EXTENSOES_DA_CAPA else ".png"
    destino = pasta / f"{NOME_DA_CAPA}{extensao}"
    if not destino.exists() or destino.resolve() != capa.resolve():
        gv.gravar_bytes(destino, conteudo)
    return extensao


def _apagar_as_outras_capas(pasta: Path, extensao: str) -> None:
    """A capa de outra extensão não fica órfã; sai só depois do JSON, que se falhar deixa
    valendo a de antes."""
    for velha in EXTENSOES_DA_CAPA:
        if velha != extensao and (pasta / f"{NOME_DA_CAPA}{velha}").is_file():
            gv.apagar(pasta / f"{NOME_DA_CAPA}{velha}")


#: As extensões de capa que o EPUB leva, e o tamanho máximo (a cópia é na hora de exportar).
EXTENSOES_DA_CAPA = (".png", ".jpg", ".jpeg", ".gif", ".webp")
TAMANHO_MAXIMO_DA_CAPA = 20 * 1024 * 1024


def _conferir_capa(conteudo: bytes) -> None:
    """Levanta `ValueError` se a capa não for PNG, JPEG, GIF ou WebP, ou passar do limite."""
    if len(conteudo) > TAMANHO_MAXIMO_DA_CAPA:
        raise ValueError(f"A capa tem {len(conteudo) // (1024 * 1024)} MB; o limite é "
                         f"{TAMANHO_MAXIMO_DA_CAPA // (1024 * 1024)} MB.")
    assinaturas = (conteudo[:8] == b"\x89PNG\r\n\x1a\n", conteudo[:3] == b"\xff\xd8\xff",
                   conteudo[:6] in (b"GIF87a", b"GIF89a"),
                   conteudo[:4] == b"RIFF" and conteudo[8:12] == b"WEBP")
    if not any(assinaturas):
        raise ValueError("A capa não é uma imagem PNG, JPEG, GIF ou WebP.")


def metadados_do_projeto(projeto: ProjetoDeLivro, idioma: str, dados: Optional[dict] = None):
    """Os metadados do EPUB: o título e o idioma do projeto e o que `metadados.json` disser
    (`titulo`, `autores`, `editora`, `data`, `assuntos`, `direitos`, `identificador`,
    `fonte` e `capa`, o caminho de uma imagem relativo à pasta do projeto). `dados` troca o
    arquivo (o formulário de um projeto só de leitura). Sem nada, só o título e o idioma."""
    from abbychess import epub

    dados = ler_metadados(projeto) if dados is None else dados
    if not isinstance(dados, dict):
        dados = {}

    def texto(chave: str) -> str:
        valor = dados.get(chave)
        return str(valor).strip() if valor is not None else ""

    def lista(valor) -> Tuple[str, ...]:
        if isinstance(valor, str):
            return (valor.strip(),) if valor.strip() else ()
        if not isinstance(valor, (list, tuple)):
            return ()
        return tuple(str(v).strip() for v in valor if v is not None and str(v).strip())

    capa = None
    if texto("capa"):
        pasta = Path(projeto.pasta).resolve()
        arquivo_da_capa = (pasta / texto("capa")).resolve()
        if pasta != arquivo_da_capa and pasta not in arquivo_da_capa.parents:
            log.warning("A capa %s está fora da pasta do projeto: fica de fora.", texto("capa"))
        else:
            try:
                capa = arquivo_da_capa.read_bytes()
            except OSError as erro:
                log.warning("A capa %s não foi lida (%s).", texto("capa"), erro)
    return epub.Metadados(
        titulo=texto("titulo") or projeto.dados.nome, idioma=idioma,
        autores=lista(dados.get("autores") or dados.get("autor")),
        editora=texto("editora"), data=texto("data"), assuntos=lista(dados.get("assuntos")),
        direitos=texto("direitos"), identificador=texto("identificador"),
        fonte=texto("fonte"), capa=capa)
