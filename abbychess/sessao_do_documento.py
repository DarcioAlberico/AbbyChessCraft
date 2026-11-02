"""A sessão do Documento confirmada (§6.3), à parte do `ControladorDePagina` (SPEC-qualidade
Q-A1): as unidades e o texto de agora viram as operações da tabela num passo do desfazer, na
hora ou na vez dela na fila de tarefas (`na_fila`, que o Ctrl+T e o fechar do projeto
consultam); o Ctrl+Enter ensina o glifo sob o cursor no mesmo passo; o novo parágrafo e os
estilos (Ctrl+Shift+Enter, Ctrl+B/I/U). Aqui também o modo das peças nos lances (§6.4), que
lembra, por projeto, se o livro tem figurinas. A edição em si (`_editar`, `_mudou`) e a letra
virtual que faltava continuam do controlador."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import List, Optional, Sequence

from abbychess import edicao as ed
from abbychess import sessao as ss
from abbychess.historico import Antes
from abbychess.modelo import Pagina

log = logging.getLogger(__name__)


class ControladorDaSessao:
    def __init__(self, p) -> None:
        self._p = p
        #: Conta as sessões do Documento confirmadas: a chave do passo do desfazer de cada
        #: uma, que o ensinar do Ctrl+Enter emenda.
        self._numero_da_sessao = 0
        self.zerar()

    def zerar(self) -> None:
        """Outro projeto: a fila dele foi esvaziada, e o modo das peças é consultado de novo."""
        #: O livro tem figurinas lidas (o modo "livro" das peças, §6.4): o "sim" fica guardado
        #: até outro projeto; sem ele (None), o resumo das páginas é consultado de novo.
        self._livro_tem_figurinas: Optional[bool] = None
        #: As sessões do Documento confirmadas que esperam a vez na fila, como [corpo, já
        #: rodou?] (o Ctrl+T espera; fechar o projeto as aplica na hora).
        self.na_fila: List[list] = []

    def confirmar_sessao(self, unidades, novo: str, *, ensinar_gid: Optional[int] = None,
                         original: Optional[str] = None, fixos=(), depois=None,
                         agora: bool = False) -> None:
        """§6.3: a sessão do Documento confirmada (Enter, Shift+Enter, Ctrl+Enter, sair dela):
        as unidades originais dela e o texto de agora viram as operações da tabela, num passo
        do desfazer, e os glifos dela com leitura ficam `revisado`. Sem mudança, é aceitar a
        palavra. O que é do passo G recusa tudo (`sessao_recusada`, com a mensagem); o que
        muda a estrutura avisa (`estrutural`). `ensinar_gid` (Ctrl+Enter) ensina o glifo sob o
        cursor no mesmo passo do desfazer (`ss.LETRA_NOVA`: uma letra digitada agora, que não
        ensina). `fixos`: os pares que nenhuma edição tocou (`sessao.alinhar`). `depois()`
        roda quando a edição entrou na página (na hora, ou na vez dela na fila).
        `agora`: aplica já,
        sem a fila (fechar o projeto, que esvazia a fila)."""
        unidades = list(unidades)
        original = original if original is not None else "".join(u.texto for u in unidades)
        dados = self._p.projeto.dados if self._p.projeto is not None else None
        indice, pagina = self._p.indice, self._p.modelo
        if dados is not None:
            novo = ss.com_figurinas(novo, original, dados.idioma,
                                    self._modo_das_pecas(dados.notacao, pagina))

        def corpo():
            # A página da sessão, mesmo que o usuário já tenha ido a outra (a sessão confirma
            # ao sair da página, e a edição pode esperar a vez dela na fila).
            aberta = pagina is self._p.modelo
            feito = self._aplicar_na_pagina(pagina, indice, unidades, novo, fixos, aberta)
            if feito is not None:
                self._registrar(pagina, indice, feito, (novo, original), aberta,
                                ensinar_gid, depois)
        # A edição que não rodou (a página sem imagem, ou outra na vez dela): o Documento
        # volta ao modelo.
        if pagina is None:
            self._p.eventos.emitir("sessao_recusada", "a página não pode ser editada agora")
            return
        if agora:                               # fechar o projeto: a fila vai ser esvaziada
            corpo()
            return
        if self._p._agora():
            self._p._editar("Editando o texto", corpo, so_nesta_pagina=False,
                            nao_rodou=lambda: self._p.eventos.emitir(
                                "sessao_recusada", "a página não pode ser editada agora"))
            return
        espera = [corpo, False]
        self.na_fila.append(espera)

        def rodar(funcao):
            def rodando():
                if espera[1]:                   # já aplicada (fechar o projeto)
                    return
                espera[1] = True
                self.na_fila.remove(espera)
                funcao()
            return rodando
        self._p._editar("Editando o texto", rodar(corpo), so_nesta_pagina=False,
                        nao_rodou=rodar(lambda: self._p.eventos.emitir(
                            "sessao_recusada", "a página não pode ser editada agora")))

    def _aplicar_na_pagina(self, pagina: Pagina, indice: int, unidades, novo: str, fixos,
                           aberta: bool) -> Optional[tuple]:
        """A sessão aplicada na página: (plano, antes, os gids que saíram), ou None com a
        recusa avisada (a página mudou, ou a edição falhou e foi desfeita)."""
        if self._pagina_mudou(pagina, indice, unidades, aberta):
            self._p.eventos.emitir("sessao_recusada", "a página mudou antes da confirmação")
            return None
        try:
            plano = ss.planejar(unidades, novo, fixos)
        except ss.Recusa as recusa:
            self._p.eventos.emitir("sessao_recusada", str(recusa))
            return None
        antes = Antes(pagina.instantaneo(), self._p.padroes())
        vivos_antes = set(pagina.vivos)
        try:
            ss.aplicar(pagina, plano, self._p.imagem if aberta else None, self._p.leitor)
        except Exception:
            # Nada da sessão fica pela metade: a página volta ao instantâneo (os gids já
            # alocados não voltam: um gid nunca se repete).
            pagina.boxes, pagina.decisoes = list(antes.pagina.boxes), antes.pagina.decisoes
            log.exception("a sessão do Documento falhou ao aplicar")
            self._p.eventos.emitir("sessao_recusada", "a edição falhou e foi desfeita")
            return None
        return plano, antes, vivos_antes - pagina.vivos

    def _pagina_mudou(self, pagina: Pagina, indice: int, unidades, aberta: bool) -> bool:
        virtuais = {v.gid for v in pagina.decisoes.virtuais}
        if not aberta and self._p.projeto.paginas_em_memoria.pagina(indice) is not pagina:
            # A página saiu da memória e foi lida de novo (o lote, por exemplo): a
            # edição no objeto velho seria gravada por cima da nova.
            return True
        return any(u.glifo and u.gid not in pagina.vivos | virtuais for u in unidades)

    def _registrar(self, pagina: Pagina, indice: int, feito: tuple, textos: tuple,
                   aberta: bool, ensinar_gid: Optional[int], depois) -> None:
        """A sessão aplicada no desfazer (o passo que o Ctrl+Enter emenda), com o aviso
        estrutural, o ensinar e o `depois` na página aberta."""
        plano, antes, saiu = feito
        novo, original = textos
        if aberta:
            self._tirar_da_escolha(saiu)
        palavra = " ".join(novo.split())
        descricao = (f"Editar '{palavra[:40]}'" if plano.muda
                     else f"Aceitar '{' '.join(original.split())[:40]}'")
        self._numero_da_sessao += 1
        chave = ("sessao", self._numero_da_sessao)   # o Ctrl+Enter emenda nesta
        self._p._mudou(pagina, indice, descricao, antes, juntar=chave)
        self._avisar_o_estrutural(pagina, plano, aberta)
        if aberta:
            self._depois_na_aberta(ensinar_gid, depois, chave)

    def _tirar_da_escolha(self, saiu: set) -> None:
        self._p.pulados -= saiu
        self._p.selecao -= saiu
        if self._p.atual in saiu:
            self._p.atual = None

    def _avisar_o_estrutural(self, pagina: Pagina, plano, aberta: bool) -> None:
        tinta = aberta and bool(plano.virtuais) and self._tinta_sem_box(pagina, plano)
        aviso = plano.estrutural(*(["há tinta sem box aqui: Ctrl+M marca o quadro"]
                                   if tinta else []))
        if aviso:
            self._p.eventos.emitir("estrutural", aviso)

    def _depois_na_aberta(self, ensinar_gid: Optional[int], depois, chave) -> None:
        if ensinar_gid is not None:
            self._ensinar_do_documento(ensinar_gid, chave)
        if depois is not None:
            depois()

    def novo_paragrafo(self, gid: Optional[int]) -> None:
        """Ctrl+Shift+Enter: começa um parágrafo na linha do glifo indicado, num passo do
        desfazer; de novo na mesma linha, tira o parágrafo. O parágrafo começa sempre no
        começo da linha: o Documento e a exportação partem por linha, e uma linha não se
        divide em dois parágrafos (antes, a palavra do meio da linha abria o bloco num e não
        no outro)."""
        if self._p.modelo is None:
            return
        if gid is None:
            self._p._avisar("Ponha o cursor numa palavra para começar o parágrafo nela.", 5000)
            return
        linha = _linha_do_glifo(self._p.documento(), gid)
        # O primeiro glifo da linha com leitura (não um virtual, nem um box ainda não lido:
        # a exportação lê o parágrafo pelo primeiro glifo lido da linha).
        lidos = {b.gid for b in self._p.modelo.boxes if b.entry.char}
        inicio = _primeiro_lido(linha, gid, lidos)
        if inicio is None:
            self._p._avisar("A linha não tem glifo lido onde começar o parágrafo.", 6000)
            return
        tirar = inicio in self._p.modelo.decisoes.paragrafo_antes

        def corpo():
            antes = Antes(self._p.modelo.instantaneo(), self._p.padroes())
            if tirar:
                d = self._p.modelo.decisoes
                self._p.modelo.decisoes = replace(d, paragrafo_antes=d.paragrafo_antes - {inicio})
            else:
                ed.paragrafo(self._p.modelo, inicio)
            self._p._mudou(self._p.modelo, self._p.indice,
                           "Tirar o parágrafo" if tirar else "Novo parágrafo", antes)
            if tirar:
                self._p._avisar("Parágrafo tirado: a linha volta ao parágrafo de antes · Ctrl+Z "
                                "desfaz.", 6000)
            elif inicio != gid:
                self._p._avisar("Parágrafo novo no começo da linha (uma linha não se divide em "
                                "dois parágrafos) · Ctrl+Z desfaz.", 7000)
            else:
                self._p._avisar("Parágrafo novo · de novo na mesma linha, tira · Ctrl+Z desfaz.",
                                6000)
        self._p._editar("Criando parágrafo", corpo)

    def alternar_estilo(self, gids: Sequence[int], campo: str) -> None:
        """Alterna negrito, itálico ou sublinhado na seleção do Documento."""
        gids = [g for g in dict.fromkeys(gids)
                if self._p.modelo is not None and g in self._p.modelo.vivos]
        if not gids or self._p.modelo is None:
            return

        def corpo():
            antes = Antes(self._p.modelo.instantaneo(), self._p.padroes())
            ed.estilizar(self._p.modelo, gids, campo)
            nome = {"negrito": "negrito", "italico": "itálico", "sublinhado": "sublinhado"}[campo]
            self._p._mudou(self._p.modelo, self._p.indice, f"Alternar {nome}", antes)
        self._p._editar("Aplicando o estilo", corpo)

    def aplicar_as_sessoes_na_fila(self) -> None:
        """Fechar o projeto (a fila vai ser esvaziada): as sessões do Documento que esperavam
        a vez entram agora, em vez de se perder."""
        for espera in list(self.na_fila):
            if not espera[1]:
                espera[1] = True
                self.na_fila.remove(espera)
                espera[0]()

    def _modo_das_pecas(self, notacao: str, pagina: Optional[Pagina]) -> str:
        """O modo das peças nos lances (§6.4). "livro": figurinas se o livro tem figurinas
        lidas (a página aberta ou, uma vez por projeto, as outras páginas lidas), senão
        letras; uma página de prosa num livro de figurinas segue o livro."""
        if notacao != "livro":
            return notacao
        if not self._livro_tem_figurinas and pagina is not None:
            if ss.modo_da_pagina("livro", (b.entry.char for b in pagina.boxes)) == "figurinas":
                self._livro_tem_figurinas = True
        if not self._livro_tem_figurinas:       # o "não" não fica guardado: o lote lê mais
            self._livro_tem_figurinas = self._figurinas_nas_paginas_lidas() or None
        return "figurinas" if self._livro_tem_figurinas else "letras"

    def _figurinas_nas_paginas_lidas(self) -> bool:
        """Pelo resumo das páginas no `livro.json` (sem abrir nenhuma; uma página gravada
        antes do D1 não tem o campo e conta quando for gravada de novo)."""
        if self._p.projeto is None:
            return False
        return any(r.get("figurinas") for r in self._p.projeto.resumo.do_livro().values())

    def _tinta_sem_box(self, pagina: Pagina, plano) -> bool:
        """Há tinta sem box onde uma letra que faltou entrou (a letra que a segmentação não
        viu): a faixa ao lado do glifo âncora, do tamanho das letras, até o vizinho da linha."""
        if self._p.matriz is None:
            return False
        caixas = {b.gid: b.entry for b in pagina.boxes}
        for letras, (lado, ancora) in plano.virtuais:
            e = caixas.get(ancora)
            if e is None:
                continue
            largura = max(4, (e.x2 - e.x1)) * len(letras)
            x1, x2 = _faixa_ao_lado(e, lado, largura, _na_mesma_linha(caixas, e))
            recorte = self._p.matriz[max(0, e.y1):e.y2, max(0, x1):max(0, x2)]
            if recorte.size and int((recorte < 128).sum()) >= 12:
                return True
        return False

    def _ensinar_do_documento(self, gid: int, chave) -> None:
        """Ctrl+Enter: o glifo sob o cursor, ensinado com o caractere dele, no passo do
        desfazer da edição (`chave`)."""
        virtuais = {v.gid for v in self._p.modelo.decisoes.virtuais} if self._p.modelo else set()
        if gid == ss.LETRA_NOVA or gid in virtuais:
            self._p._avisar("Glifo sem tinta não ensina.", 6000)
            return
        if self._p.modelo is None or gid not in self._p.modelo.vivos or not self._p._pode_ler():
            return
        char = self._p.box(gid).char
        if not char:
            return
        self._p.escolher(gid)
        self._p.limpar_selecao()
        self._p.leitura.ensinar_gids({char: [gid]}, f"Ensinar '{char}'",
                                     self._p.leitura.depois_de_ensinar(char, [gid]), juntar=chave)



def _linha_do_glifo(documento, gid: int):
    """A linha do Documento que tem o glifo, ou None."""
    return next((ln for b in documento.blocos for ln in b.linhas
                 if any(gid in p.gids for p in ln.palavras)), None)


def _primeiro_lido(linha, gid: int, lidos: set) -> Optional[int]:
    """O primeiro glifo lido da linha (sem a linha, o próprio `gid`, se lido); None se não há."""
    proprio = gid if gid in lidos else None
    if not linha:
        return proprio
    return next((g for p in linha.palavras for g in p.gids if g in lidos), proprio)


def _na_mesma_linha(caixas: dict, e) -> list:
    """As caixas que cruzam a faixa vertical de `e` (sem ela)."""
    return [b for b in caixas.values() if b is not e and b.y1 < e.y2 and b.y2 > e.y1]


def _faixa_ao_lado(e, lado: str, largura: int, mesma_linha: list) -> tuple:
    """(x1, x2) da faixa de `largura` ao lado de `e` ("depois" ou antes), até o vizinho da
    linha."""
    if lado == "depois":
        x1 = e.x2 + 1
        return x1, min([x1 + largura] + [b.x1 for b in mesma_linha if b.x1 >= e.x2])
    x2 = e.x1 - 1
    return max([x2 - largura] + [b.x2 for b in mesma_linha if b.x2 <= e.x1]), x2
