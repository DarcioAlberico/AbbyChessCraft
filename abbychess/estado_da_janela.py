"""Que ação vale agora, e por que não (SPEC-qualidade Q-A2): a regra que ligava e desligava as
ações da janela, sem Qt. `calcular` lê o controlador da página, o do livro e a `Vista` (o que
só a janela sabe: as áreas ligadas, a sessão do Documento, o editor de diagrama aberto);
`app.acoes.atualizar` só aplica o `EstadoDaJanela` nos `QAction`.

Uma tarefa rodando não desliga quase nada: o comando pedido entra na fila do executor, que a
barra de status mostra. O lote também não: ele grava entre um comando e outro; só abrir outro
projeto e começar outro lote esperam o fim dele."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

SEM_PAGINA = "Nenhuma página aberta."
LOTE_RODANDO = "O lote está lendo o livro: espere-o terminar, ou cancele-o."
SEM_LOTE = "Nenhum lote rodando."
NADA_A_RETOMAR = "Não há lote a retomar."
SEM_ANTES = "A página não tem o estado de antes do lote."
SEM_BOXES = "A página ainda não tem glifos."
NA_PRIMEIRA = "Já é a primeira página."
NA_ULTIMA = "Já é a última página."
SEM_VISITA = "Não há página visitada para esse lado."
AREAS_DESLIGADAS = "As áreas não estão à vista."
SEM_AREA_ATUAL = "Escolha uma área."
SEM_AREAS = "A página não tem áreas."
SEM_MODELO = "Não há modelo de áreas guardado."
SEM_APAGADAS = "Não há páginas apagadas."
NADA_A_DESFAZER = "Nada a desfazer."
NADA_A_REFAZER = "Nada a refazer."

#: As dicas das operações de página, na ordem de `JanelaPrincipal.acoes_de_paginas`.
DICAS_DAS_PAGINAS = (
    "Muda páginas de lugar (as escolhidas, depois de outra)",
    "Tira páginas do livro; elas ficam guardadas no projeto",
    "Põe páginas de um PDF ou de imagens no livro",
    "Devolve ao livro as páginas apagadas",
    "Gira 90° no sentido horário a página aberta (ou as escolhidas na gaveta)",
    "Gira 90° no sentido anti-horário a página aberta (ou as escolhidas na gaveta)",
    "Gira as páginas de 90 em 90 graus, com os glifos",
    "Corta as margens das páginas; os glifos de fora ficam guardados",
    "Devolve as páginas cortadas inteiras",
    "Divide a página espelhada em duas",
    "Endireita as páginas por um ângulo à mão; a leitura delas se desfaz",
)
#: A posição de "Restaurar páginas apagadas" em `DICAS_DAS_PAGINAS`.
RESTAURAR = 3


@dataclass(frozen=True)
class Vista:
    """O que só a janela sabe."""

    areas_ligadas: bool = False         # Exibir › Áreas
    area_atual: bool = False            # uma área escolhida no visor
    tem_zonas: bool = False             # o painel de áreas tem áreas
    tem_modelo: bool = False            # há modelo de áreas guardado
    sessao: bool = False                # a sessão do Documento: o Ctrl+Z é dela (§6.3)
    pode_reaplicar: bool = False        # depois do Esc, o Ctrl+Y reaplica a palavra
    no_diagrama: bool = False           # o editor Diagrama aberto: o Ctrl+Z é o do tabuleiro


@dataclass(frozen=True)
class EstadoDaJanela:
    #: O nome do atributo da janela (a ação, ou a lista de ações) -> None se vale, ou o
    #: motivo de não valer.
    habilitadas: Dict[str, Optional[str]] = field(default_factory=dict)
    #: (motivo ou None, dica) de cada operação de página, na ordem de `DICAS_DAS_PAGINAS`.
    paginas: Tuple[Tuple[Optional[str], str], ...] = ()
    #: As páginas podem mudar (a gaveta deixa arrastar).
    paginas_mudam: bool = True
    texto_do_desfazer: str = "Desfazer"
    texto_do_refazer: str = "Refazer"


def _primeiro(*condicoes: Tuple[bool, str]) -> Optional[str]:
    """O motivo da primeira condição que falha, ou None se todas valem."""
    return next((motivo for vale, motivo in condicoes if not vale), None)


def _das_paginas(p) -> Tuple[Tuple[Tuple[Optional[str], str], ...], bool]:
    motivo = p.operacoes.motivo_para_nao_mudar_as_paginas()
    apagadas = bool(p.projeto.sequencia.apagadas) if p.projeto is not None else False
    paginas = []
    for k, dica in enumerate(DICAS_DAS_PAGINAS):
        proprio = SEM_APAGADAS if k == RESTAURAR and not apagadas else None
        paginas.append((motivo or proprio, dica if motivo is None else f"{dica}. {motivo}"))
    return tuple(paginas), motivo is None


def calcular(p, livro, vista: Vista) -> EstadoDaJanela:
    """O estado das ações: `p` é o `ControladorDePagina`, `livro` o `ControladorDoLivro`."""
    # O que só existe com a página aberta é lido só com ela (sem página, não há visita).
    pronto = p.pronto
    tem = (pronto, SEM_PAGINA)
    sem_lote = (not p.lote_rodando, LOTE_RODANDO)
    boxes = (pronto and bool(p.boxes), SEM_BOXES)
    total = p.fonte.total if p.fonte else 0
    antes = (pronto and not p.projeto.somente_leitura and p.projeto.antes_do_lote.tem(p.indice),
             SEM_ANTES)
    primeira = (pronto and p.indice > 0, NA_PRIMEIRA)
    ultima = (pronto and p.indice < total - 1, NA_ULTIMA)
    voltar = (pronto and p.navegador.pode_voltar, SEM_VISITA)
    avancar = (pronto and p.navegador.pode_avancar, SEM_VISITA)
    areas = (vista.areas_ligadas, AREAS_DESLIGADAS)
    area_atual = _primeiro(tem, areas, (vista.area_atual, SEM_AREA_ATUAL))
    desfazer, refazer = p.historico.proximo_a_desfazer, p.historico.proximo_a_refazer
    if vista.sessao:
        desfazer = "a palavra"
    if vista.pode_reaplicar:
        refazer = "a palavra"
    habilitadas = {
        "acao_novo": _primeiro(sem_lote),
        "acao_abrir": _primeiro(sem_lote),
        "acao_reconhecer": _primeiro(tem),
        "acao_reler": _primeiro(tem, boxes),
        "acao_verificada": _primeiro(tem),
        "acao_anterior": _primeiro(tem, primeira),
        "acao_primeira": _primeiro(tem, primeira),
        "acao_seguinte": _primeiro(tem, ultima),
        "acao_ultima": _primeiro(tem, ultima),
        "acao_ir_para": _primeiro(tem),
        "acao_voltar_visita": _primeiro(tem, voltar),
        "acao_avancar_visita": _primeiro(tem, avancar),
        "seletor": _primeiro(tem),
        "acao_modo_treino": _primeiro(tem),
        "acao_opcoes": _primeiro(tem),
        "acao_lote": _primeiro(tem, sem_lote),
        "acao_cancelar_lote": _primeiro((livro.lote_rodando, SEM_LOTE)),
        "acao_retomar_lote": _primeiro(tem, (livro.pode_retomar, NADA_A_RETOMAR)),
        "acao_antes_do_lote": _primeiro(tem, antes),
        "acao_proximo_do_livro": _primeiro(tem),
        "acao_exportar": _primeiro(tem),
        "acao_localizar": _primeiro(tem),
        "acao_proxima_ocorrencia": _primeiro(tem),
        "acao_ocorrencia_anterior": _primeiro(tem),
        "acao_todas_em_resultados": _primeiro(tem),
        "acao_buscar_glifo": _primeiro(tem),
        "acao_substituir": _primeiro(tem),
        "acao_galeria": _primeiro(tem, boxes),
        "acao_areas": _primeiro(tem),
        "acao_areas_auto": _primeiro(tem, areas),
        "acao_reconhecer_zona": area_atual,
        "acoes_das_funcoes": area_atual,
        "acoes_dos_tipos": area_atual,
        "acao_ordenar_areas": _primeiro(tem, areas, (vista.tem_zonas, SEM_AREAS)),
        "acao_salvar_modelo_areas": _primeiro(tem, areas, (vista.tem_zonas, SEM_AREAS)),
        "acao_aplicar_modelo_areas": _primeiro(tem, areas, (vista.tem_modelo, SEM_MODELO)),
        "acao_verificar": _primeiro(tem, boxes),
        "acao_diagramas": _primeiro(tem),
        "acao_proximo_da_fila": _primeiro(tem),
        "acao_anterior_da_fila": _primeiro(tem),
        "acao_ciclar_fila": _primeiro(tem),
        "acao_escopo_da_fila": _primeiro(tem),
        "acao_realce": _primeiro(tem, boxes),       # sem página reconhecida, nada a realçar
        "acao_margens": _primeiro(tem, boxes),
        "acao_desfazer": _primeiro(tem, (desfazer is not None or vista.no_diagrama,
                                         NADA_A_DESFAZER)),
        "acao_refazer": _primeiro(tem, (refazer is not None or vista.no_diagrama,
                                        NADA_A_REFAZER)),
    }
    paginas, paginas_mudam = _das_paginas(p)
    return EstadoDaJanela(habilitadas, paginas, paginas_mudam,
                          f"Desfazer: {desfazer}" if desfazer else "Desfazer",
                          f"Refazer: {refazer}" if refazer else "Refazer")
