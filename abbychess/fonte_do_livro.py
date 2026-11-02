"""A fonte do livro, o PDF ou a imagem de onde vêm as páginas (§4.3, CA-4.7), à parte do
`ProjetoDeLivro` (SPEC-qualidade Q-A1). Não é a fonte das páginas renderizadas
(`pagina.FonteDePaginas`): aqui fica onde o arquivo está (`caminho`, relativo à pasta do projeto
quando está dentro dela, `caminho_gravado`), se ele é um PDF (`e_pdf`) e quantas páginas tem
(`total_de_paginas`, o que a sequência do livro precisa, §12.4). Se ele sumir, a abertura procura
o mesmo arquivo pelo SHA-256 dos primeiros 4 MB e pelo tamanho (`procurar`, `sha_da_fonte`) ao
lado do caminho antigo, na pasta do projeto e na pasta-mãe dele, e senão `ausente` diz à janela
que peça ao usuário (`relocalizar`, que confere o conteúdo). Em só leitura, a fonte achada ou
indicada vale só na sessão. Abrir e decidir o que fazer com a fonte achada é do projeto (`abrir`,
`_abrir_para_gravar`, `_abrir_so_para_leitura`), e o `projeto.json` também (`self._p`); as
páginas inseridas, copiadas para `inseridas/`, também (`inserir_arquivo`): o que ele devolve são
entradas da sequência, com `pid` novos."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

#: Quanto da fonte entra no SHA-256 que a reconhece depois de movida.
BYTES_DO_SHA = 4 * 2**20
#: Quantos arquivos do tamanho certo, no máximo, `abrir` lê ao procurar a fonte sumida
#: (os de outro tamanho nem são lidos e não contam).
CANDIDATOS_DA_FONTE = 200


def sha_da_fonte(caminho: Path) -> str:
    """O SHA-256 dos primeiros `BYTES_DO_SHA` bytes do arquivo."""
    with open(caminho, "rb") as arquivo:
        return hashlib.sha256(arquivo.read(BYTES_DO_SHA)).hexdigest()


def caminho_gravado(fonte: Path, pasta: Path) -> str:
    """Relativo (com /) quando a fonte está dentro da pasta do projeto; senão absoluto."""
    fonte, pasta = Path(fonte).resolve(), Path(pasta).resolve()
    try:
        return fonte.relative_to(pasta).as_posix()
    except ValueError:
        return str(fonte)


class FonteDoLivro:
    def __init__(self, p) -> None:
        self._p = p

    @property
    def caminho(self) -> Path:
        caminho = Path(self._p.dados.fonte)
        return caminho if caminho.is_absolute() else self._p.pasta / caminho

    @property
    def e_pdf(self) -> bool:
        return self.caminho.suffix.lower() == ".pdf"

    @property
    def ausente(self) -> bool:
        return not self.caminho.is_file()

    def relocalizar(self, caminho: str | Path) -> None:
        """A fonte foi movida para `caminho`: confere que é o mesmo arquivo e grava.

        Projeto antigo, sem o SHA-256 gravado, aceita o arquivo e passa a ter o dele.
        """
        from abbychess.projeto import ProjetoInvalido       # o projeto importa este módulo

        caminho = Path(caminho).resolve()
        if not caminho.is_file():
            raise ProjetoInvalido(f"A fonte não existe: {caminho}")
        sha, tamanho = sha_da_fonte(caminho), caminho.stat().st_size
        if self._p.dados.fonte_sha256 and (sha != self._p.dados.fonte_sha256 or (
                self._p.dados.fonte_tamanho and tamanho != self._p.dados.fonte_tamanho)):
            raise ProjetoInvalido(
                f"{caminho.name} não é a fonte deste projeto: o conteúdo é outro.")
        antes = (self._p.dados.fonte, self._p.dados.fonte_sha256, self._p.dados.fonte_tamanho)
        self._p.dados.fonte = caminho_gravado(caminho, self._p.pasta)
        self._p.dados.fonte_sha256, self._p.dados.fonte_tamanho = sha, tamanho
        if self._p.somente_leitura:
            return              # vale nesta sessão; o arquivo do projeto não muda
        try:
            self._p.salvar()
        except BaseException:
            self._p.dados.fonte, self._p.dados.fonte_sha256, self._p.dados.fonte_tamanho = antes
            raise

    def procurar(self) -> Optional[Path]:
        """O arquivo com o SHA-256 e o tamanho da fonte: na pasta do caminho antigo, na do
        projeto ou na pasta-mãe do projeto."""
        if not self._p.dados.fonte_sha256:
            return None
        lidos = 0
        for chave, candidato in self._candidatos():
            try:
                if not self._do_tamanho(candidato):
                    continue            # tamanho diferente: nem é preciso ler
                lidos += 1
                if lidos > CANDIDATOS_DA_FONTE:
                    return None
                if sha_da_fonte(candidato) == self._p.dados.fonte_sha256:
                    return chave
            except OSError:
                continue
        return None

    def _candidatos(self):
        """(caminho resolvido, caminho) de cada arquivo com a extensão da fonte, uma vez só,
        na pasta do caminho antigo, na do projeto e na pasta-mãe dele."""
        antigo = self.caminho
        vistos = set()
        for pasta in (antigo.parent, self._p.pasta, self._p.pasta.parent):
            if not pasta.is_dir():
                continue
            for candidato in sorted(pasta.glob("*" + antigo.suffix)):
                chave = candidato.resolve()
                if chave in vistos or not candidato.is_file():
                    continue
                vistos.add(chave)
                yield chave, candidato

    def _do_tamanho(self, candidato: Path) -> bool:
        """O candidato tem o tamanho da fonte (ou o tamanho dela não foi guardado)."""
        tamanho = self._p.dados.fonte_tamanho
        return not tamanho or candidato.stat().st_size == tamanho

    def total_de_paginas(self) -> int:
        """Quantas páginas a fonte do livro tem (sem a fonte: 0)."""
        if not self.caminho.is_file():
            return 0
        if not self.e_pdf:
            return 1
        import fitz

        try:
            with fitz.open(str(self.caminho)) as documento:
                return documento.page_count
        except (RuntimeError, ValueError, OSError):
            return 0
