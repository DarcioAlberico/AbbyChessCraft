"""A fila de glifos da página aberta (§8.1), à parte do `ControladorDePagina` (SPEC-qualidade
Q-A1): que glifos vão à revisão (julgando de novo só os que mudaram) e em que ordem
(`ordem_da_fila`: a confiança, a ordem da página ou o caractere), com o que a exportação tira
(o cabeçalho e o rodapé corridos, as áreas de margem: `gids_fora_do_texto`) depois do resto;
e o andar nela: o primeiro pendente depois de uma decisão, o pular e o voltar (`andar`).

Não é o `ControladorDaFila` de `controladores.py`: aquele é da janela (o modo da revisão, dos
glifos às palavras e aos diagramas, e o escopo, a página ou o livro) e anda nesta quando o modo
é de glifos; esta é da página aberta, vive com o controlador e vale sem janela (o lote, os
testes, as ferramentas)."""

from __future__ import annotations

from typing import List, Optional

from abbychess import contexto
from abbychess.leitor import precisa_revisao

#: Quantas páginas guardam a conta das margens corridas (`gids_de_margem`): as do cache de
#: páginas (§14.1) e folga.
MARGENS_GUARDADAS = 8


class FilaDaPagina:
    def __init__(self, p) -> None:
        self._p = p
        #: A ordem da fila de glifos (§8.1): "confianca" (o menos confiável primeiro, os
        #: pulados no fim) ou "leitura" (a ordem da página).
        self.ordem_da_fila = "confianca"
        #: gid -> (o que decide, se ele vai para a fila): a fila julga de novo só os glifos
        #: que mudaram (a leitura, a fonte, a confiança ou o revisado), e todos quando o
        #: limiar muda.
        self._pendencia: dict = {}
        self._limiar_da_pendencia = None
        #: Na ordem de leitura: (página, posição na ordem da página) do último glifo mostrado,
        #: para a decisão seguir em frente mesmo quando o glifo sai (descartar, juntar).
        self._lugar_de_leitura = (-1, 0)
        #: pid -> (chave, gids) da última conta das margens corridas de cada página
        #: (`gids_de_margem`), das `MARGENS_GUARDADAS` páginas vistas por último.
        self._margens: dict = {}
        #: A fila usa a última conta das margens da página (`margens_da_fila`), mesmo de antes
        #: da última mudança, e quem liga isto a refaz (`gids_de_margem`) depois: a janela,
        #: com o texto da página, 150 ms depois da última mudança. Desligado, a fila refaz a
        #: conta a cada mudança (~25 ms numa página cheia; uma releitura muda a página 2 vezes).
        self.margens_com_o_texto = False

    def zerar(self) -> None:
        """Outro projeto (o `ligar`): as margens guardadas saem, porque os pid se repetem de
        um projeto a outro. A ordem, a pendência e o lugar na ordem de leitura ficam."""
        self._margens = {}

    def fila(self) -> List[int]:
        """Os gids a revisar (§8.1): do menos confiável ao mais, com os pulados no fim; na
        ordem de leitura (`ordem_da_fila`), na ordem da página; por caractere, agrupados pela
        leitura (os sem leitura no fim) e, em cada grupo, do menos confiável ao mais. O glifo
        `revisado` (visto e aceito no Documento, §6.3) não volta.

        Por confiança e por caractere, o que a exportação tira (`gids_fora_do_texto`: o
        cabeçalho e o rodapé corridos, as áreas de margem) vem depois do resto e antes dos
        pulados: no Xadrez Vitorioso o □ do título corrido abria a fila de toda página. Na
        ordem de leitura, não: `andar` e o fim da página contam com a fila na ordem dela. As
        margens corridas são as de `margens_da_fila` (na janela, a última conta da página)."""
        if self._p.leitor is None or self._p.modelo is None:
            return []
        boxes = self._p.modelo.boxes
        fila = [boxes[i].gid for i in _na_ordem(boxes, self._pendentes(), self.ordem_da_fila)]
        if self.ordem_da_fila == "leitura":
            return fila
        fora = self.gids_fora_do_texto(self.margens_da_fila()) if fila else frozenset()
        return _fora_e_pulados_no_fim(fila, fora, self._p.pulados)

    def _pendentes(self) -> List[int]:
        """Os índices dos glifos que vão para a fila, na ordem da página. Só os glifos que
        mudaram são julgados de novo (§8.1: a fila recalculada só para os gids tocados)."""
        limiares = self._p.leitor.limiares
        chave = limiares.revisao                 # o único limiar que decide a fila
        anterior = self._pendencia if chave == self._limiar_da_pendencia else {}
        contra = contexto.improvaveis(self._p.modelo)    # a palavra desmente a leitura
        nova, indices = {}, []
        for i, box in enumerate(self._p.modelo.boxes):
            e = box.entry
            estado = (e.char, e.source, e.confidence, box.revisado, box.gid in contra)
            visto = anterior.get(box.gid)
            if visto is not None and visto[0] == estado:
                pendente = visto[1]
            else:
                pendente = not box.revisado and (
                    precisa_revisao(e.char, e.source, e.confidence, limiares)
                    or (box.gid in contra and contexto.volta_pelo_contexto(e.source)))
            nova[box.gid] = (estado, pendente)
            if pendente:
                indices.append(i)
        self._pendencia, self._limiar_da_pendencia = nova, chave
        return indices

    def posicao_do_atual(self) -> str:
        """O que o Glifo diz da posição: nada, se o glifo está na fila (o contador do Inspetor
        a mostra); "fora da fila", se não."""
        if self._p.atual in self.fila():
            return ""
        return "Glifo fora da fila (já confirmado ou confiável)"

    def gids_de_margem(self) -> frozenset:
        """Os glifos do cabeçalho e do rodapé corridos da página, pela regra da exportação
        (`margens.margens_corridas`: a faixa, o vão e o número da página), até o layout do
        passo F dar a função às áreas. O glifo sem leitura conta (`margens.margens_da_pagina`):
        o □ do título corrido é título corrido."""
        if self._p.modelo is None or self._p.imagem is None:
            return frozenset()
        boxes = self._p.modelo.boxes
        # A regra olha as linhas inteiras da página (~25 ms numa página cheia): o resultado
        # fica, por página, enquanto o que ela lê não muda (o texto, a posição de cada glifo e
        # a altura da página); montar a chave custa uma fração de milissegundo. Guardar só a
        # última página refazia a conta em toda troca entre duas páginas.
        chave = (self._p.imagem.height,
                 tuple((b.gid, b.entry.char, b.entry.x1, b.entry.y1, b.entry.x2, b.entry.y2)
                       for b in boxes))
        guardada = self._margens.pop(self._p.modelo.pid, None)
        if guardada is None or guardada[0] != chave:
            guardada = (chave, _margens_corridas(boxes, self._p.imagem.height))
        _guardar_por_ultimo(self._margens, self._p.modelo.pid, guardada)
        return guardada[1]

    def margens_da_fila(self) -> frozenset:
        """As margens corridas que a fila usa: as de `gids_de_margem` ou, com
        `margens_com_o_texto`, a última conta desta página, se há uma."""
        if self.margens_com_o_texto and self._p.modelo is not None:
            guardada = self._margens.get(self._p.modelo.pid)
            if guardada is not None:
                return guardada[1]
        return self.gids_de_margem()

    def gids_fora_do_texto(self, margens: Optional[frozenset] = None) -> frozenset:
        """Os glifos que a exportação tira: os de `gids_de_margem` (ou `margens`) e os das
        áreas de cabeçalho, rodapé, número de página e ignorar (`exportar.FORA_DA_EXPORTACAO`)."""
        if self._p.modelo is None:
            return frozenset()
        from abbychess import montagem as mo

        areas = [z for z in self._p.modelo.zonas if z.funcao in mo.FORA_DA_EXPORTACAO]
        nas_areas = {b.gid for b in self._p.modelo.boxes
                     if any(z.contem_o_centro(b.entry) for z in areas)} if areas else set()
        return (self.gids_de_margem() if margens is None else margens) | nas_areas

    def guardar_lugar(self) -> None:
        """Na ordem de leitura, onde está o glifo mostrado (o `mostrar` o põe)."""
        if self._p.atual is not None and self.ordem_da_fila == "leitura":
            gids = self._p.gids
            if self._p.atual in gids:
                self._lugar_de_leitura = (self._p.indice, gids.index(self._p.atual))

    def ir_ao_primeiro_pendente(self) -> None:
        """O próximo a revisar depois de uma decisão: o primeiro da fila; na ordem de
        leitura, o primeiro pendente a partir do lugar do glifo decidido (e, no fim da
        página, o primeiro dela)."""
        fila = self.fila()
        if self.ordem_da_fila == "leitura" and fila:
            ordem = {g: n for n, g in enumerate(self._p.gids)}
            pagina, lugar = self._lugar_de_leitura
            lugar = ordem.get(self._p.atual, lugar if pagina == self._p.indice else 0)
            adiante = [g for g in fila if ordem[g] >= lugar]
            self._p.atual = adiante[0] if adiante else fila[0]
        else:
            self._p.atual = fila[0] if fila else None
        self.guardar_lugar()
        self._p.escolhido = False
        self._p.eventos.emitir("atual_mudou")

    def andar(self, passo: int) -> None:
        """Pula (passo > 0: o atual vai para o fim da fila) ou volta na fila. Na ordem de
        leitura, anda para o pendente seguinte (ou anterior) na página, sem pular."""
        fila = self.fila()
        if not fila:
            self.ir_ao_primeiro_pendente()
            return
        if self.ordem_da_fila == "leitura":
            self._p.escolher(_vizinho_na_leitura(fila, self._p.gids, self._p.atual, passo))
            return
        if passo > 0 and self._p.atual in fila:
            self._p.pulados.add(self._p.atual)
            self._p.escolher(self.fila()[0])
            return
        if self._p.atual not in fila:            # fora da fila: o primeiro (ou o último) dela
            self._p.escolher(fila[0] if passo > 0 else fila[-1])
            return
        self._p.escolher(fila[(fila.index(self._p.atual) + passo) % len(fila)])


def _na_ordem(boxes, indices: List[int], ordem: str) -> List[int]:
    """Os índices dos pendentes na ordem da fila: por caractere (os sem leitura no fim) e, em
    cada um, do menos confiável ao mais; na ordem da página; ou do menos confiável ao mais."""
    if ordem == "caractere":
        return sorted(indices, key=lambda i: (boxes[i].entry.char or "￿",
                                              round(boxes[i].entry.confidence, 2), i))
    if ordem != "leitura":
        return sorted(indices, key=lambda i: (round(boxes[i].entry.confidence, 2), i))
    return indices


def _fora_e_pulados_no_fim(fila: List[int], fora, pulados) -> List[int]:
    """A fila com o que a exportação tira depois do resto, e os pulados no fim de tudo; cada
    parte na ordem em que estava."""
    resto, de_fora, no_fim = [], [], []
    for g in fila:
        if g in pulados:
            no_fim.append(g)
        elif g in fora:
            de_fora.append(g)
        else:
            resto.append(g)
    return resto + de_fora + no_fim


def _vizinho_na_leitura(fila: List[int], gids: List[int], atual, passo: int) -> int:
    """Na ordem de leitura: o pendente seguinte ao atual (`passo` > 0) ou o anterior, na
    página; na ponta, o primeiro (ou o último) da fila."""
    ordem = {g: n for n, g in enumerate(gids)}
    aqui = ordem.get(atual, -1)
    if passo > 0:
        return next((g for g in fila if ordem[g] > aqui), fila[0])
    return next((g for g in reversed(fila) if ordem[g] < aqui), fila[-1])


def _margens_corridas(boxes, altura: int) -> frozenset:
    """Os gids do cabeçalho e do rodapé corridos (`margens.margens_da_pagina`)."""
    from abbychess import margens as mg

    indices = mg.margens_da_pagina([b.entry for b in boxes], altura)
    return frozenset(boxes[i].gid for i in indices if i < len(boxes))


def _guardar_por_ultimo(margens: dict, pid: int, guardada) -> None:
    """Guarda a conta da página como a vista por último, com só as `MARGENS_GUARDADAS`
    últimas."""
    margens[pid] = guardada
    while len(margens) > MARGENS_GUARDADAS:
        del margens[next(iter(margens))]
