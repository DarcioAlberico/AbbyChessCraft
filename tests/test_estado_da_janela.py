"""Que ação vale agora, sem janela (SPEC-qualidade Q-A2, CA-Q-A2 parte 1): o estado é
calculado do controlador e do que só a vista sabe; `acoes.atualizar` só o aplica."""
from __future__ import annotations

from types import SimpleNamespace as Ns

from abbychess import estado_da_janela as ej


def _pagina(**mudar):
    projeto = Ns(sequencia=Ns(apagadas=()), somente_leitura=False,
                 tem_antes_do_lote=lambda indice: False)
    base = dict(pronto=True, lote_rodando=False, projeto=projeto, fonte=Ns(total=5), boxes=[1],
                indice=2, navegador=Ns(pode_voltar=False, pode_avancar=False),
                historico=Ns(proximo_a_desfazer=None, proximo_a_refazer=None),
                operacoes=Ns(motivo_para_nao_mudar_as_paginas=lambda: None))
    base.update(mudar)
    return Ns(**base)


LIVRO = Ns(lote_rodando=False, pode_retomar=False)
VISTA = ej.Vista()


def test_sem_projeto_so_novo_e_abrir_valem():
    estado = ej.calcular(_pagina(pronto=False, projeto=None, fonte=None, boxes=[]), LIVRO, VISTA)
    ligadas = {nome for nome, motivo in estado.habilitadas.items() if motivo is None}
    assert ligadas == {"acao_novo", "acao_abrir"}
    assert estado.habilitadas["acao_reconhecer"] == ej.SEM_PAGINA


def test_com_o_lote_rodando_abrir_espera_e_cancelar_vale():
    livro = Ns(lote_rodando=True, pode_retomar=False)
    estado = ej.calcular(_pagina(lote_rodando=True), livro, VISTA)
    assert estado.habilitadas["acao_abrir"] == ej.LOTE_RODANDO
    assert estado.habilitadas["acao_lote"] == ej.LOTE_RODANDO
    assert estado.habilitadas["acao_cancelar_lote"] is None
    assert estado.habilitadas["acao_reconhecer"] is None       # o lote não prende a janela


def test_as_operacoes_de_pagina_levam_o_motivo_na_dica():
    motivo = "O projeto está aberto só para leitura."
    estado = ej.calcular(_pagina(operacoes=Ns(motivo_para_nao_mudar_as_paginas=lambda: motivo)), LIVRO, VISTA)
    assert all(m == motivo and dica.endswith(motivo) for m, dica in estado.paginas)
    assert not estado.paginas_mudam
    livre = ej.calcular(_pagina(), LIVRO, VISTA)
    restaurar = livre.paginas[3]                    # devolver as apagadas: não há nenhuma
    assert restaurar[0] == ej.SEM_APAGADAS and livre.paginas_mudam
    assert all(m is None for k, (m, _d) in enumerate(livre.paginas) if k != 3)


def test_o_desfazer_da_sessao_do_documento_e_da_palavra():
    pagina = _pagina(historico=Ns(proximo_a_desfazer="Ensinar 'a'", proximo_a_refazer=None))
    assert ej.calcular(pagina, LIVRO, VISTA).texto_do_desfazer == "Desfazer: Ensinar 'a'"
    na_sessao = ej.calcular(pagina, LIVRO, ej.Vista(sessao=True))
    assert na_sessao.texto_do_desfazer == "Desfazer: a palavra"
    estado = ej.calcular(_pagina(), LIVRO, VISTA)
    assert estado.texto_do_refazer == "Refazer" and estado.habilitadas["acao_refazer"] is not None
    no_diagrama = ej.calcular(_pagina(), LIVRO, ej.Vista(no_diagrama=True))
    assert no_diagrama.habilitadas["acao_desfazer"] is None


def test_as_acoes_das_areas_seguem_a_vista():
    sem_areas = ej.calcular(_pagina(), LIVRO, VISTA)
    assert sem_areas.habilitadas["acao_areas_auto"] == ej.AREAS_DESLIGADAS
    com_area = ej.calcular(_pagina(), LIVRO, ej.Vista(areas_ligadas=True, area_atual=True,
                                                      tem_zonas=True))
    for nome in ("acao_areas_auto", "acao_reconhecer_zona", "acao_ordenar_areas",
                 "acao_salvar_modelo_areas", "acoes_das_funcoes", "acoes_dos_tipos"):
        assert com_area.habilitadas[nome] is None, nome
    assert com_area.habilitadas["acao_aplicar_modelo_areas"] == ej.SEM_MODELO
