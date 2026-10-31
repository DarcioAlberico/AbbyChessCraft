"""A página como estava antes de o lote com "refazer" a reler (§4.6, CA-4.8), à parte do
`ProjetoDeLivro` (SPEC-qualidade Q-A1). O lote não entra no desfazer: antes de reler uma página
já lida, ele guarda a cópia dela em `paginas/.antes-do-lote/p<pid>.json` (`guardar`), e
"Voltar ao estado antes do lote" (`tem`, `data`, `voltar`) a põe de volta, com o JSON idêntico
ao copiado, e tira a cópia. A página, o cache, o gravador e o `livro.json` são do projeto
(`self._p`)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from abbychess import gravacao as gv
from abbychess.modelo import Pagina
from abbychess.pagina_em_json import pagina_para_json
from abbychess.pasta_do_projeto import PASTA_ANTES_DO_LOTE, PASTA_DE_PAGINAS


class AntesDoLote:
    def __init__(self, p) -> None:
        self._p = p

    def _arquivo(self, pid: int) -> Path:
        return self._p.pasta / PASTA_DE_PAGINAS / PASTA_ANTES_DO_LOTE / f"p{pid}.json"

    def guardar(self, pagina: Pagina) -> None:
        """A página como está agora, antes de o lote com "refazer" a reler: o lote não entra
        no desfazer, e "Voltar ao estado antes do lote" a restaura."""
        gv.gravar_json(self._arquivo(pagina.pid),
                       pagina_para_json(pagina.instantaneo(),
                                        self._p.ordem.pagina_da_fonte(pagina)))

    def tem(self, indice: int) -> bool:
        # O pid do modelo (em memória), e não o do `livro.json`: logo depois do lote, a
        # página ainda está com o gravador, e o livro não a tem.
        pagina = self._p.carregar_modelo(indice)
        return pagina is not None and self._arquivo(pagina.pid).is_file()

    def data(self, indice: int) -> Optional[datetime]:
        """Quando a cópia de antes do lote foi feita (a hora do arquivo), ou None."""
        pagina = self._p.carregar_modelo(indice)
        if pagina is None:
            return None
        arquivo = self._arquivo(pagina.pid)
        try:
            return datetime.fromtimestamp(arquivo.stat().st_mtime)
        except OSError:
            return None

    def voltar(self, indice: int) -> Pagina:
        """Põe de volta a página copiada antes do lote (o JSON idêntico ao copiado), e a
        cópia sai. O gravador grava antes o que tem pendente: senão, a gravação dele passaria
        por cima da página restaurada; se ele não grava, nada muda (`OSError`). No projeto
        só para leitura, também não."""
        if self._p.somente_leitura:
            raise OSError("o projeto está aberto só para leitura")
        if not self._p.paginas_em_memoria.descarregar(10):
            raise OSError("há páginas que não puderam ser gravadas (veja a barra de status); "
                          "nada foi mudado")
        pid = self._p.ordem.pid_em(indice)
        with self._p._trava_do_livro:
            copia = None if pid is None else self._arquivo(pid)
            if copia is None or not copia.is_file():
                raise OSError(f"a página {indice + 1} não tem cópia de antes do lote")
            dados = copia.read_bytes()
            gv.gravar_bytes(self._p._arquivo_v2(pid), dados)
            pagina = self._p._de_json(json.loads(dados.decode("utf-8")))
            self._p.paginas_em_memoria.guardar(pagina, foto_nova=True)
            self._p.resumo.atualizar(pid, self._p.resumo.do_modelo(pagina))
            gv.apagar(copia)
            return pagina
