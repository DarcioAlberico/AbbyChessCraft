"""Os padrões do livro e as opções dele, à parte do `ControladorDePagina` (SPEC-qualidade Q-A1).
Esquecer amostras num passo do desfazer e devolver à fila os glifos que elas leram, na página
aberta na hora e nas outras pelo índice da busca (§8.3, a procedência: `procurar_no_livro`,
que o refazer de um esquecer também chama); o aviso de ensino, o efeito e o conflito (§8.3);
e as opções do livro: os limiares, com a fila refeita por eles (§8.1, CA-8.3), a notação das
peças (§6.4) e o idioma da prosa. Os padrões em si são do leitor (`p.leitor.padroes`)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Sequence, Tuple

from abbychess import contexto
from abbychess import edicao as ed
from abbychess import historico as hs
from abbychess import pagina as pg
from abbychess import procedencia
from abbychess.avisos import AVISO_LONGO_MS
from abbychess.leitor import FONTE_NENHUMA
from abbychess.modelo import Pagina, proximo_estado


class ControladorDosPadroes:
    #: Quem acha, no livro, os glifos lidos por umas amostras (o índice da busca):
    #: `lidos_pelas_amostras(nomes, ao_terminar)`, com `ao_terminar({página: [gids]})`.
    lidos_pelas_amostras = None

    def __init__(self, p) -> None:
        self._p = p

    def esquecer(self, caminhos: Sequence) -> None:
        """Apaga amostras dos padrões do livro (§8.3), num passo do desfazer, e devolve à
        fila os glifos que elas leram: na página aberta, na hora; nas outras, pelo índice da
        busca, em segundo plano (`lidos_pelas_amostras`), emendando a mesma transação. O
        glifo devolvido fica com a leitura e perde a fonte (o padrão que a dava sumiu: ele
        volta à fila); a página verificada atingida volta a `em_revisao`, com aviso. Desfazer
        o esquecer devolve as amostras e tira os glifos da fila de novo. Na fila de
        tarefas: o leitor não muda no meio de uma leitura."""
        if self._p.leitor is None:
            return
        caminhos = list(caminhos)

        def preparar():
            if self._p.leitor is None:
                return None
            nomes = {self._nome_da_amostra(c) for c in caminhos}
            apagadas = [self._p.leitor.padroes.guardar(c) for c in caminhos]
            self._p.leitor.esquecer_varios(caminhos)      # recarrega os padrões uma vez só
            self._p.eventos.emitir("padroes_mudaram")
            transacao = hs.Transacao(f"Esquecer {len(caminhos)} amostra(s)",
                                     amostras_apagadas=apagadas, esquecidas=frozenset(nomes))
            self._p.historico.registrar(transacao)
            self.procurar_no_livro(transacao)
            return None
        self._p.tarefa("Esquecendo padrões", preparar, falhou=self._p._falhou("Esquecer padrões"))

    def procurar_no_livro(self, transacao) -> None:
        """Os glifos lidos pelas amostras que a `transacao` esqueceu voltam à fila: os da
        página aberta na hora; os das outras quando a procura no livro volta, emendando a
        transação. Também no refazer de um esquecer desfeito antes de ela voltar."""
        nomes, quantas = set(transacao.esquecidas), len(transacao.amostras_apagadas)
        devolvidos = {}
        if self._p.modelo is not None:
            n = self._devolver_a_fila(self._p.modelo, nomes, None, transacao)
            if n:
                devolvidos[self._p.indice] = n
        self._p.eventos.emitir("acoes_mudaram")
        procurar = self.lidos_pelas_amostras
        if procurar is None:
            self._avisar_os_devolvidos(quantas, devolvidos, completo=True)
            return
        self._p._avisar(f"Esquecida(s) {quantas} amostra(s); procurando no livro os glifos que "
                        "ela(s) leram…", 0)
        # (Se a ordem do livro muda no meio, a busca procura de novo pela ordem nova.)
        procurar(nomes, lambda achados: self._devolver_no_livro(
            nomes, achados, transacao, devolvidos, quantas))

    def aviso_de_ensino(self, char: str) -> Tuple[str, str]:
        """§8.3, ao digitar o caractere do glifo atual: o efeito ("Enter ensina 'l' · 23
        iguais nesta página": os glifos da página com a mesma leitura dele; e, se alguns a
        palavra desmente, quantos o Ctrl+Enter corrige em lote) e o conflito
        ("este glifo está a 0,08 de 14 amostras de '1'", ou "")."""
        if not char or self._p.modelo is None or self._p.atual is None or self._p.leitor is None:
            return "", ""
        i = self._p.indice_de(self._p.atual)
        if i is None:
            return "", ""
        entradas = self._p.modelo.entries()
        lida = entradas[i].char
        iguais = sum(1 for k, e in enumerate(entradas) if k != i and lida and e.char == lida)
        efeito = f"Enter ensina '{char}'" + (f" · {iguais} iguais nesta página" if iguais else "")
        alvos = self._p.alvos()                     # o que o Ctrl+Enter usaria (`ensinar`)
        lidas = {self._p.box(g).char for g in alvos} - {char, ""}
        em_lote = len(contexto.lote(self._p.modelo, lidas, char, alvos)) if lidas else 0
        if em_lote:
            efeito += (f" · Ctrl+Enter corrige também {em_lote} "
                       f"{'/'.join(repr(c) for c in sorted(lidas))} que a palavra desmente")
        conflito = ""
        if self._p.imagem is not None:
            from core import proporcao
            from abbychess.leitor import altura_relativa

            recorte = pg.recorte(self._p._cinza(), entradas[i])
            referencia = proporcao.altura_de_referencia(entradas)
            achado = self._p.leitor.padroes.conflito(recorte, char,
                                                     altura_relativa(recorte, referencia),
                                                     self._p.leitor.limiares.conflito)
            if achado is not None:
                outro, n, distancia = achado
                conflito = (f"este glifo está a {distancia:.2f} de {n} amostra(s) de "
                            f"'{outro}'".replace(".", ","))
        return efeito, conflito

    def _nome_da_amostra(self, caminho) -> str:
        """O nome da amostra como o `Box.amostra` o guarda (relativo à pasta dos padrões)."""
        caminho = Path(caminho)
        try:
            return caminho.resolve().relative_to(
                Path(self._p.projeto.pasta_de_padroes).resolve()).as_posix()
        except ValueError:
            return caminho.name

    def _devolver_a_fila(self, pagina: Pagina, nomes: set, gids, transacao) -> int:
        """Os glifos da página lidos pelas amostras `nomes` (só os de `gids`, se vier)
        voltam à fila; a verificada volta a `em_revisao`. Emenda a `transacao` e grava.
        Devolve quantos voltaram."""
        alvo = None if gids is None else set(gids)
        antes = pagina.instantaneo()
        boxes, n = list(pagina.boxes), 0
        for k, box in enumerate(boxes):
            if box.amostra in nomes and (alvo is None or box.gid in alvo):
                entry = ed.copia(box.entry)
                entry.source = FONTE_NENHUMA
                procedencia.registrar(entry, procedencia.NENHUMA)
                boxes[k] = replace(box, entry=entry, amostra=None, revisado=False)
                n += 1
        if not n:
            return 0
        pagina.boxes = boxes
        estado = proximo_estado(pagina.estado, "esquecer_padrao")
        if estado != pagina.estado:
            pagina.estado = estado
            self._p.eventos.emitir("aviso", "Esquecer padrões",
                                   f"Página {pagina.indice + 1}: estava verificada e voltou à "
                                   "revisão (o padrão esquecido lia glifos dela).")
        self._p.leitura.emendar(transacao, antes, pagina)
        self._p._gravar(pagina)
        if pagina is self._p.modelo:
            if self._p.atual is None:
                self._p.fila_da_pagina.ir_ao_primeiro_pendente()
            self._p.eventos.emitir("glifos_mudaram", None)
        return n

    def _devolver_no_livro(self, nomes, achados, transacao, devolvidos, quantas) -> None:
        """O resultado da procura no livro: as outras páginas, na mesma transação (se ela
        não foi desfeita no meio)."""
        if transacao.invalidada or self._p.projeto is None:
            if transacao.invalidada:             # a mensagem "procurando…" não fica na barra
                self._p._avisar("Esquecer desfeito antes de a procura no livro voltar.", 6000)
            return
        for indice, gids in sorted(achados.items()):
            if self._p.modelo is not None and indice == self._p.indice:
                pagina = self._p.modelo
            else:
                pagina = self._p.projeto.pagina_para_editar(indice)
            n = self._devolver_a_fila(pagina, nomes, gids, transacao)
            if n:
                devolvidos[indice] = devolvidos.get(indice, 0) + n
        self._p.eventos.emitir("acoes_mudaram")
        self._avisar_os_devolvidos(quantas, devolvidos, completo=True)

    def _avisar_os_devolvidos(self, quantas: int, devolvidos: dict, completo: bool) -> None:
        total = sum(devolvidos.values())
        if total:
            self._p._avisar(f"Esquecida(s) {quantas} amostra(s): {total} glifo(s) voltaram à fila "
                            f"em {len(devolvidos)} página(s) · {{desfazer}} desfaz.", 10000)
        else:
            self._p._avisar(f"Esquecida(s) {quantas} amostra(s); nenhum glifo lido por ela(s) · "
                            "Ctrl+Z desfaz.", AVISO_LONGO_MS)

    def aplicar_limiares(self, limiares) -> None:
        """Os limiares do livro, gravados no projeto, e a fila refeita com eles (na fila: a
        fila de revisão não muda no meio de uma leitura). A mensagem vai para a barra; um
        problema ao gravar vai em `aviso`."""

        def preparar():
            if self._p.projeto is not None:
                self._aplicar_limiares(limiares)
            return None
        self._p.tarefa("Aplicando os limiares", preparar, falhou=self._p._falhou("Opções"))

    def definir_notacao(self, notacao: str) -> None:
        """Como o livro escreve as peças nos lances (§6.4), no projeto (gravado junto com os
        limiares, que vêm logo depois)."""
        if self._p.projeto is not None:
            self._p.projeto.dados.notacao = notacao

    def definir_idioma(self, idioma: str) -> bool:
        """O idioma da prosa do livro (o léxico da verificação, as letras das peças), no
        projeto, gravado junto com os limiares; devolve se mudou."""
        if self._p.projeto is None or self._p.projeto.dados.idioma == idioma:
            return False
        self._p.projeto.dados.idioma = idioma
        return True

    def _aplicar_limiares(self, limiares) -> None:
        projeto = self._p.projeto
        projeto.dados.limiares = limiares
        gravou = False
        if not projeto.somente_leitura:
            try:
                projeto.salvar()
            except OSError as erro:
                self._p.eventos.emitir("aviso", "Opções", "Os limiares valem nesta sessão, mas "
                                       f"não foram gravados no projeto:\n{erro}")
            else:
                gravou = True
                try:
                    projeto.resumo.reaplicar_limiar()
                except OSError as erro:
                    self._p.eventos.emitir("aviso", "Opções", "Os limiares foram gravados, mas o "
                                           "resumo do livro (livro.json) não; ele é refeito na "
                                           f"próxima gravação de página:\n{erro}")
        self._p.leitor.trocar_limiares(limiares)
        if self._p.servidor is not None:
            self._p.servidor.trocar_limiares(limiares)
        self._p.eventos.emitir("glifos_mudaram", None)
        if self._p.boxes:
            self._p.fila_da_pagina.ir_ao_primeiro_pendente()
        if gravou:
            mensagem = "Limiares do livro gravados."
        elif projeto.somente_leitura:
            mensagem = "Limiares aplicados nesta sessão (o projeto é só para leitura)."
        else:
            mensagem = "Limiares aplicados nesta sessão (não foram gravados)."
        self._p._avisar(mensagem, 5000)
