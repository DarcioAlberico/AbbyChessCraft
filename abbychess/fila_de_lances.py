"""A fila Lances (F-4, SPEC da página perfeita §5.4): a revisão por linha, em ordem de leitura. Sem Qt.

A linha aparece como imagem sobre texto; **Enter sem editar confere**: número, lance, xeque e sinal
da linha ficam `revisado`, sem ensinar, num passo do desfazer, e a fila vai à próxima linha. A prosa
da linha não muda de estado. **Editar e Enter** corrige pela sessão do Documento, só nas palavras
que mudaram, e confere. **Ctrl+Enter** faz o mesmo e ensina os glifos que mudaram. **Alt+↓** pula.
O relatório diz "conferidos", nunca "certos": conferir é o olho do revisor, e pode errar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set

from abbychess import decodificador_de_lances as dl
from abbychess import edicao as ed
from abbychess import evidencia as ev
from abbychess import sessao as ss
from abbychess import texto as tx
from abbychess import verificacao as vf
from abbychess import tokens as tk

MENSAGEM_SEM_LANCE = "Nenhuma forma de lance lida nesta página"


@dataclass(frozen=True)
class LinhaNaFila:
    linha: dl.LinhaDeLance
    #: Os glifos da linha que têm caixa na página (o virtual não tem).
    gids: List[int]
    #: Os gids do lance ilegal na linha, e o motivo dele; vazio sem ilegal.
    ilegais: frozenset = frozenset()
    motivo: str = ""


class FilaDeLances:
    def __init__(self, pagina):
        self._p = pagina
        self.eventos = pagina.eventos
        self.linhas: List[LinhaNaFila] = []
        self.posicao = 0
        #: As linhas sem lance (as que estão entre duas) já vistas, por gid inicial e página.
        self._vistas: Set[tuple] = set()

    def _chave(self) -> str:
        projeto = self._p.projeto
        return projeto.dados.chave_das_pecas if projeto is not None else "pt"

    def _documento(self):
        return self._p.documento()

    def recontar(self, posicao: Optional[int] = None) -> None:
        """As linhas por conferir da página aberta; a fila fica na `posicao` (a de agora)."""
        self.linhas = self._linhas_por_conferir()
        total = len(self.linhas)
        alvo = self.posicao if posicao is None else posicao
        self.posicao = alvo % total if total else 0
        self.eventos.emitir("linha_de_lance_mudou")

    def _linhas_por_conferir(self) -> List[LinhaNaFila]:
        p = self._p
        documento = self._documento() if p.modelo is not None else None
        if documento is None:
            return []
        feitos = ev.conferidos(p.modelo)
        vivos = set(p.gids)
        saida = []
        for ln in dl.linhas_da_fila(documento, self._chave()):
            gids = [g for g in ln.gids if g in vivos]
            if gids and not self._ja_conferida(ln, gids, feitos):
                saida.append(self._na_fila(ln, gids))
        return saida

    def _na_fila(self, ln: dl.LinhaDeLance, gids: List[int]) -> LinhaNaFila:
        evidencia = self._p.evidencia.agora()
        ilegais = frozenset(g for g in ln.gids_de_lance if g in evidencia.ilegais)
        motivo = next((evidencia.motivos[g][0] for g in ilegais), "")
        return LinhaNaFila(ln, gids, ilegais, motivo)

    def _ja_conferida(self, ln: dl.LinhaDeLance, gids: Sequence[int], feitos) -> bool:
        if ln.tem_lance:
            return all(g in feitos for g in ln.gids_de_lance if g in set(gids))
        return (self._p.indice, gids[0]) in self._vistas

    def atual(self) -> Optional[LinhaNaFila]:
        return self.linhas[self.posicao % len(self.linhas)] if self.linhas else None

    def andar(self, passo: int) -> None:
        if self.linhas:
            self.posicao = (self.posicao + passo) % len(self.linhas)
        self.eventos.emitir("linha_de_lance_mudou")

    def na_ponta(self, passo: int) -> bool:
        total = len(self.linhas)
        return not total or (self.posicao == total - 1 if passo > 0 else self.posicao == 0)

    def como_palavra(self, linha: LinhaNaFila) -> vf.Desconhecida:
        """A linha como a Palavra do Inspetor a mostra: o recorte, e o texto no campo."""
        indices = [self._p.indice_de(g) for g in linha.gids]
        return vf.Desconhecida(linha.linha.texto, [i for i in indices if i is not None], "lance",
                               sugestao=linha.linha.texto, aviso=linha.motivo)

    def confirmar(self, texto: str, ensinar: bool = False) -> None:
        """Enter e Ctrl+Enter da fila: sem mudança, confere; com mudança, corrige e confere."""
        linha = self.atual()
        if linha is None:
            return
        if " ".join(texto.split()) == " ".join(linha.linha.texto.split()):
            self._p._editar("Conferindo a linha", lambda: self._conferir(linha, None))
            return
        self._corrigir(linha, texto, ensinar)

    def _conferir(self, linha: LinhaNaFila, juntar) -> None:
        p = self._p
        vivos = set(p.gids)
        gids = [g for g in linha.linha.gids_de_lance if g in vivos]
        antes = p._instantaneo()
        mudou = not ed.revisar(p.modelo, gids).vazia
        if mudou:
            p._mudou(p.modelo, p.indice, "Conferir a linha", antes, juntar=juntar)
        if not linha.linha.tem_lance and linha.gids:
            self._vistas.add((p.indice, linha.gids[0]))
        self.recontar()

    def _unidades(self, linha: LinhaNaFila) -> List[ss.Unidade]:
        """As unidades da linha, como o Documento as vê: glifo a glifo, com os espaços."""
        documento = self._documento()
        normal = tx.normalizador(tx.IMPRESSO)
        virtuais = set(self._p.gids_virtuais())
        unidades: List[ss.Unidade] = []
        for k, palavra in enumerate(_palavras_da_linha(documento, linha.linha.gids)):
            if k:
                unidades.append(ss.Unidade(" ", None, ss.ESPACO))
            for g in palavra.gids:
                char = documento.chars.get(g, "")
                for letra in (tx.NAO_LIDO if char == tx.NAO_LIDO else (normal(char) or tx.NAO_LIDO)):
                    unidades.append(ss.Unidade(letra, g, ss.VIRTUAL if g in virtuais else ss.GLIFO))
        return unidades

    def _corrigir(self, linha: LinhaNaFila, texto: str, ensinar: bool) -> None:
        """A sessão só nas palavras que mudaram, e os lances da linha conferidos no mesmo passo."""
        p = self._p
        unidades = self._unidades(linha)
        original = "".join(u.texto for u in unidades)
        novo = " ".join(texto.split())
        inicio, fim = tk.trecho_mudado(novo, original)
        a, b = ss.palavras_em(unidades, inicio, len(original) - fim)
        trecho = novo[a:b + len(novo) - len(original)]
        chars_antes = {g: p.box(g).char for g in linha.gids if p.indice_de(g) is not None}

        def depois():
            chave = ("sessao", p.sessoes._numero_da_sessao)
            self._conferir(linha, chave)
            if ensinar:
                self._ensinar_os_que_mudaram(chars_antes, chave)

        p.sessoes.confirmar_sessao(unidades[a:b], trecho, depois=depois)

    def _ensinar_os_que_mudaram(self, chars_antes: Dict[int, str], chave) -> None:
        p = self._p
        por_char: Dict[str, List[int]] = {}
        vivos = set(p.gids)
        for g, antes in chars_antes.items():
            if g in vivos and p.box(g).char and p.box(g).char != antes:
                por_char.setdefault(p.box(g).char, []).append(g)
        if por_char and p.leitor is not None:
            p.leitura.ensinar_gids(por_char, "Ensinar da linha", lambda _n: None, juntar=chave)

    def resumo_da_pagina(self) -> Dict[str, int]:
        """As contagens da página aberta para as telas vazias e o Ctrl+T."""
        p = self._p
        documento = self._documento() if p.modelo is not None else None
        if documento is None:
            return {"ilegais": 0, "aceitos": 0, "sem_posicao": 0, "nao_conferidos": 0, "lances": 0}
        contagens = ev.contagens_dos_lances(p.modelo, documento, p.diagramas_com_ids(), self._chave())
        contagens["lances"] = sum(pl.token.classe == tk.LANCE
                                  for _b, _l, palavras in dl.palavras_de_texto(documento, self._chave())
                                  for pl in palavras)
        return contagens

    def mensagem_vazia(self) -> str:
        """As telas de Lances vazia (F-4): nunca dizem "nada a revisar"."""
        r = self.resumo_da_pagina()
        if not r["lances"]:
            return MENSAGEM_SEM_LANCE
        return (f"Lances conferidos: {r['lances'] - r['nao_conferidos']}, sendo {r['aceitos']} "
                "como impressos")


def _palavras_da_linha(documento, gids: Sequence[int]):
    alvo = tuple(gids)
    for bloco in documento.blocos:
        for linha in bloco.linhas:
            if tuple(g for p in linha.palavras for g in p.gids) == alvo:
                return linha.palavras
    return ()


class EvidenciaNaPagina:
    """A evidência da página aberta, em memória, calculada de novo quando o texto muda: nunca
    em `arrumar`, que roda a cada edição. A janela a pede 500 ms depois da última edição."""

    def __init__(self, pagina):
        self._p = pagina
        self._chave_atual = None
        self._evidencia = ev.EvidenciaDaPagina()

    def agora(self) -> ev.EvidenciaDaPagina:
        p = self._p
        if p.modelo is None or p.projeto is None:
            return ev.EvidenciaDaPagina()
        chave = (p.modelo.pid, tuple(id(b) for b in p.modelo.boxes),
                 tuple(id(d) for d in p.modelo.diagramas), p.projeto.dados.chave_das_pecas)
        if chave != self._chave_atual:
            documento = p.documento()
            self._evidencia = (ev.da_pagina(p.modelo, documento, p.diagramas_com_ids(), chave[-1])
                               if documento is not None else ev.EvidenciaDaPagina())
            self._chave_atual = chave
        return self._evidencia
