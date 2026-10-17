"""O lote pelo condutor (SPEC §11, §4.6): as regras de quem escreve.

Sem servidor, o condutor lê cada página numa tarefa do executor (aqui, o `ExecutorManual`,
que deixa o teste escolher quando a leitura termina); com o servidor falso
(`tests/servidor_falso.py`), numa thread, e o teste segura a leitura para editar no meio.
Ele grava na thread de quem chama. Os casos:
a página aberta e suja não é sobrescrita (CA-11.4), nem a verificada ou mudada enquanto o
servidor a lia (aberta ou não); a verificada é pulada (CA-8.5);
cancelar e retomar não lê página duas vezes (CA-11.5); o "refazer" guarda a página de
antes e "Voltar ao estado antes do lote" a devolve idêntica (CA-4.8, a parte do lote); e
as edições não são recusadas durante o lote.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from abbychess import pagina as pg
from abbychess.controlador import ControladorDePagina, Eventos
from abbychess.controladores import ControladorDoLivro
from abbychess.leitor import FONTE_MANUAL, LeitorDoLivro
from abbychess.modelo import VERIFICADA
from abbychess.projeto import ProjetoDeLivro

from tests.test_controlador import ExecutorManual
from tests.test_livro import pdf_sintetico


@pytest.fixture
def projeto(tmp_path):
    projeto = ProjetoDeLivro.criar(tmp_path / "livros", "Lote", pdf_sintetico(tmp_path))
    yield projeto
    projeto.fechar()


@pytest.fixture
def ctl(projeto):
    executor = ExecutorManual()
    pagina = ControladorDePagina(Eventos(), executar=executor)
    pagina.ligar(projeto, pg.FonteDePaginas(projeto.fonte),
                 LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    pagina.ir_para(0)
    livro = ControladorDoLivro(pagina)
    livro.executor = executor
    livro.fins = []
    pagina.eventos.ligar("lote_terminou", lambda mensagem, resultado: livro.fins.append(resultado))
    return livro


def _sem_hora(dados: bytes) -> dict:
    bruto = json.loads(dados)
    bruto.pop("gravado_em")
    return bruto


def _hash(projeto, indice) -> str:
    pid = projeto._pid_de(indice)
    return hashlib.sha256(projeto._arquivo_v2(pid).read_bytes()).hexdigest()


def test_o_lote_le_e_grava_as_paginas_e_a_aberta_aparece(ctl, projeto):
    ctl.reconhecer([0, 1, 2], refazer=False)
    assert ctl.lote_rodando
    ctl.executor.tudo()
    [resultado] = ctl.fins
    assert resultado.lidas == [0, 1, 2] and not ctl.lote_rodando
    assert projeto.paginas_lidas() == [0, 1, 2]
    assert ctl.pagina.boxes                               # a página aberta, já com os glifos


def test_ca_11_4_a_pagina_aberta_e_suja_nao_e_sobrescrita(ctl, projeto):
    p = ctl.pagina
    ctl.reconhecer([0], refazer=False)
    ctl.executor.tudo()
    projeto.descarregar(10)
    antes = _hash(projeto, 0)
    p.escolher(p.gids[0])
    p.corrigir("Z")                                       # a aberta, com um passo no desfazer
    projeto.descarregar(10)
    gravado = _hash(projeto, 0)
    assert gravado != antes
    ctl.reconhecer([0, 1], refazer=True)
    ctl.executor.tudo()
    resultado = ctl.fins[-1]
    assert resultado.reler_depois == [0] and resultado.lidas == [1]
    projeto.descarregar(10)
    assert _hash(projeto, 0) == gravado                   # o arquivo não mudou
    assert p.box(p.gids[0]).char == "Z"


def test_sem_servidor_a_edicao_espera_a_pagina_do_lote_e_vale_depois(ctl, projeto):
    """Sem servidor, a leitura do lote prende o leitor da interface: a edição pedida no meio
    entra na fila e roda depois da página (com o servidor, roda na hora, e a página vai
    para "reler depois": `tests/test_servidor_janela.py`)."""
    p = ctl.pagina
    ctl.reconhecer([0], refazer=False)
    ctl.executor.tudo()
    ctl.reconhecer([0], refazer=True)
    fim = ctl.executor.comecar()                          # o lote leu; a gravação não veio
    p.escolher(p.gids[0])
    p.corrigir("Q")                                       # não é recusada: espera a vez
    fim()
    ctl.executor.tudo()
    assert ctl.fins[-1].lidas == [0]
    assert p.box(p.gids[0]).char == "Q"


def test_ca_8_5_o_lote_pula_as_verificadas_mesmo_com_refazer(ctl, projeto):
    ctl.reconhecer([0, 1], refazer=False)
    ctl.executor.tudo()
    projeto.descarregar(10)                               # o gravador não passa por cima
    pagina = projeto.carregar_modelo(1)
    pagina.estado = VERIFICADA
    projeto.salvar_modelo(pagina)
    ctl.reconhecer([0, 1, 2], refazer=True)
    ctl.executor.tudo()
    resultado = ctl.fins[-1]
    assert resultado.verificadas == [1] and resultado.lidas == [0, 2]


def test_ca_11_5_cancelar_e_retomar_le_cada_pagina_uma_vez(ctl, projeto):
    lidas = []
    ctl.eventos.ligar("pagina_do_lote", lidas.append)
    ctl.reconhecer([0, 1, 2], refazer=True)
    fim = ctl.executor.comecar()
    fim()                                                 # a página 1 entrou
    fim = ctl.executor.comecar()                          # a 2 foi lida…
    ctl.cancelar()                                        # …e o cancelamento chega antes
    fim()                                                 # ela grava (a leitura acabou)
    ctl.executor.tudo()
    assert ctl.fins[-1].cancelado and ctl.pode_retomar
    assert ctl.restante == ([2], True)
    ctl.retomar()
    ctl.executor.tudo()
    assert lidas == [0, 1, 2] and not ctl.pode_retomar     # a união, sem repetir


def test_cancelar_no_meio_da_leitura_deixa_a_pagina_como_estava(ctl, projeto):
    ctl.reconhecer([0], refazer=False)
    ctl.executor.tudo()
    projeto.descarregar(10)
    antes = _hash(projeto, 0)
    ctl.reconhecer([0], refazer=True)
    ctl.cancelar()                                        # antes de a leitura começar
    ctl.executor.tudo()
    assert ctl.fins[-1].cancelado and ctl.fins[-1].lidas == []
    projeto.descarregar(10)
    assert _hash(projeto, 0) == antes and ctl.restante == ([0], True)


def test_ca_4_8_voltar_ao_estado_antes_do_lote_devolve_o_json_copiado(ctl, projeto):
    p = ctl.pagina
    ctl.reconhecer([0, 1], refazer=False)
    ctl.executor.tudo()
    p.ir_para(1)
    p.escolher(p.gids[1])
    p.corrigir("W")                                       # manual: o refazer o mantém (§4.6)
    p.ir_para(0)                                          # a 1 não está aberta: o lote a relê
    p.escolher(p.gids[0])
    p.ensinar("a")                                        # o lote lê os "a" da 1 pelo padrão
    ctl.executor.tudo()
    projeto.descarregar(10)
    copia_esperada = (projeto.pasta / "paginas" / f"p{projeto._pid_de(1)}.json").read_bytes()
    assert not any(b.entry.source == "livro" for b in projeto.carregar_modelo(1).boxes)
    ctl.reconhecer([1], refazer=True)
    ctl.executor.tudo()
    assert ctl.fins[-1].lidas == [1]
    projeto.descarregar(10)
    pid = projeto._pid_de(1)
    copia = projeto.pasta / "paginas" / ".antes-do-lote" / f"p{pid}.json"
    relida = projeto.carregar_modelo(1)
    assert any(b.entry.char == "W" and b.entry.source == FONTE_MANUAL for b in relida.boxes)
    assert any(b.entry.source == "livro" for b in relida.boxes)      # a releitura mudou algo
    guardado = copia.read_bytes()
    assert _sem_hora(guardado) == _sem_hora(copia_esperada)     # a página de antes do lote

    p.ir_para(1)
    p.escolher(p.gids[2])
    p.corrigir("Z")                                       # editada depois do lote
    recusas = []
    p.eventos.ligar("recusa", lambda refazer, texto: recusas.append(texto))
    ctl.voltar_ao_antes_do_lote()
    projeto.descarregar(10)
    assert (projeto.pasta / "paginas" / f"p{pid}.json").read_bytes() == guardado
    assert not copia.exists() and not projeto.tem_antes_do_lote(1)
    assert not any(b.source == "livro" for b in p.boxes)       # a aberta mostra a de antes
    assert any(b.char == "W" for b in p.boxes) and not any(b.char == "Z" for b in p.boxes)
    p.desfazer()                                          # o "Z" não está mais lá: recusa
    assert recusas and "Corrigir para 'Z'" in recusas[0]


def test_voltar_ao_antes_do_lote_nao_grava_no_projeto_so_de_leitura(ctl, projeto):
    p = ctl.pagina
    ctl.reconhecer([0], refazer=False)
    ctl.executor.tudo()
    p.ir_para(1)
    ctl.reconhecer([0], refazer=True)
    ctl.executor.tudo()
    projeto.descarregar(10)
    p.ir_para(0)
    antes = _hash(projeto, 0)
    avisos = []
    p.eventos.ligar("aviso", lambda titulo, texto: avisos.append(texto))
    projeto.somente_leitura = True
    ctl.voltar_ao_antes_do_lote()
    assert avisos and "só para leitura" in avisos[0]
    assert _hash(projeto, 0) == antes and projeto.tem_antes_do_lote(0)


# ----------------------------------------------------------------------
# Com o servidor (o falso, no mesmo processo): a leitura numa thread, a gravação aqui
# ----------------------------------------------------------------------

@pytest.fixture
def com_servidor(ctl, projeto, monkeypatch):
    from tests import servidor_falso

    monkeypatch.setenv("ABBY_FALSO_MS_POR_GLIFO", "0")
    servidor = servidor_falso.ServidorFalso(projeto.pasta_de_padroes, projeto.dados.limiares)
    fila = servidor_falso.ligar(ctl.pagina, servidor)
    ctl.reconhecer([0, 1], refazer=False)                # as duas, lidas pelo servidor
    servidor_falso.entregar(fila, esperar_por=1)
    servidor_falso.entregar(fila, esperar_por=1)
    assert ctl.fins[-1].lidas == [0, 1]
    ctl.pagina.ir_para(0)
    return servidor, fila


def test_g2_a_pagina_verificada_durante_a_leitura_continua_verificada(ctl, projeto,
                                                                      com_servidor):
    from tests.servidor_falso import entregar

    servidor, fila = com_servidor
    p = ctl.pagina
    servidor.segurar.clear()
    ctl.reconhecer([0], refazer=True)
    p.verificar()                                         # Ctrl+T: verifica a 0 e abre a 1
    assert p.indice == 1 and projeto.estado_da_pagina(0) == VERIFICADA
    servidor.segurar.set()
    entregar(fila, esperar_por=1)
    assert ctl.fins[-1].verificadas == [0] and ctl.fins[-1].lidas == []
    assert projeto.estado_da_pagina(0) == VERIFICADA


def test_g2_a_correcao_feita_durante_a_leitura_numa_pagina_deixada_fica(ctl, projeto,
                                                                       com_servidor):
    from tests.servidor_falso import entregar

    servidor, fila = com_servidor
    p = ctl.pagina
    servidor.segurar.clear()
    ctl.reconhecer([0], refazer=True)
    gid = p.gids[3]
    p.escolher(gid)
    p.corrigir("Q")                                       # na hora: o lote está no servidor
    p.ir_para(1)                                          # e a página é deixada
    servidor.segurar.set()
    entregar(fila, esperar_por=1)
    assert ctl.fins[-1].reler_depois == [0] and ctl.fins[-1].lidas == []
    corrigido = projeto.carregar_modelo(0).box(gid).entry
    assert (corrigido.char, corrigido.source) == ("Q", FONTE_MANUAL)
    p.ir_para(0)
    p.desfazer()                                          # o Ctrl+Z dela continua valendo
    assert projeto.carregar_modelo(0).box(gid).entry.char != "Q"


def test_a_procedencia_volta_do_servidor_com_a_leitura(ctl, projeto, com_servidor):
    from tests.servidor_falso import entregar

    servidor, fila = com_servidor
    p = ctl.pagina
    p.escolher(p.gids[0])
    p.ensinar("a")                                        # o padrão vai ao servidor
    ctl.executor.tudo()
    ctl.reconhecer([1], refazer=True)
    entregar(fila, esperar_por=1)
    pela_amostra = [b for b in projeto.carregar_modelo(1).boxes if b.entry.source == "livro"]
    assert pela_amostra and all(b.amostra for b in pela_amostra)


def test_o_glifo_aguardando_que_volta_no_refazer_e_lido_e_o_desfazer_vale(ctl, projeto,
                                                                         com_servidor):
    from abbychess import pagina as pg
    from tests.servidor_falso import entregar

    servidor, fila = com_servidor
    p = ctl.pagina
    p.leitor.aguardar = True                              # a interface só com os padrões
    p.leitor.ocr = None
    b = p.box(p.gids[0])
    antes = len(p.gids)
    p.marcar(b.x1 - 1, b.y1 - 1, b.x2 + 1, b.y2 + 1)
    gid = p.atual
    assert pg.aguardando(p.box(gid))
    p.desfazer()                                          # antes de a leitura chegar
    p.refazer()
    assert pg.aguardando(p.box(gid))
    entregar(fila, esperar_por=1)                         # a leitura do primeiro pedido
    assert p.box(gid).char == "x"
    assert p.historico.proximo_a_desfazer == "Marcar glifo"
    recusas = []
    p.eventos.ligar("recusa", lambda refazer, texto: recusas.append(texto))
    p.desfazer()                                          # a leitura não impede o desfazer
    assert not recusas and gid not in p.gids and len(p.gids) == antes
    p.refazer()
    entregar(fila, esperar_por=1)
    assert p.box(gid).char == "x"


def test_abrir_a_pagina_com_aguardando_le_fora_do_desfazer(ctl, projeto, com_servidor):
    from dataclasses import replace

    from tests.servidor_falso import entregar

    servidor, fila = com_servidor
    p = ctl.pagina
    p.escolher(p.gids[0])
    p.corrigir("k")
    p.desfazer()                                          # algo para refazer
    pagina = projeto.carregar_modelo(1)
    pagina.boxes = [replace(b, entry=replace(b.entry, char="", source="", confidence=0.0))
                    if k == 0 else b for k, b in enumerate(pagina.boxes)]
    projeto.salvar_modelo(pagina)                         # um glifo da 1 ficou aguardando
    p.ir_para(1)
    entregar(fila, esperar_por=1)
    assert p.boxes[0].char == "x"
    assert p.historico.proximo_a_refazer == "Corrigir para 'k'"     # o refazer ficou


def test_com_o_servidor_parado_os_comandos_avisam_e_nao_leem(ctl, projeto, com_servidor):
    servidor, fila = com_servidor
    p = ctl.pagina
    mensagens = []
    p.eventos.ligar("mensagem", lambda texto, ms: mensagens.append(texto))
    servidor.desistiu = True
    pedidos = len(servidor.pedidos)
    p.reconhecer()
    p.reler_pendentes()
    assert len(servidor.pedidos) == pedidos and not ctl.executor.fila
    assert sum("Reabra o projeto" in m for m in mensagens) == 2


def test_o_lote_sincrono_de_centenas_de_paginas_nao_aninha_a_pilha(projeto, monkeypatch):
    """O executor síncrono (as ferramentas) termina cada página dentro da chamada que a
    pediu: o laço do condutor não pode se aninhar, ou um livro grande estouraria a pilha."""
    from abbychess import lote
    from abbychess import servidor_de_leitura as sl

    monkeypatch.setattr(lote.sl, "ler_pagina", lambda *a, **k: sl.PaginaLida([], [], [], None))
    monkeypatch.setattr(projeto, "guardar_antes_do_lote", lambda pagina: None)   # o disco, não
    pagina = ControladorDePagina(Eventos())
    pagina.ligar(projeto, pg.FonteDePaginas(projeto.fonte),
                 LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares))
    fins = []
    condutor = lote.CondutorDoLote(pagina, [0, 1, 2] * 84, refazer=True, ao_fim=fins.append)
    condutor.comecar()
    assert len(fins[0].lidas) == 252


def test_voltar_ao_antes_do_lote_durante_a_releitura_nao_e_sobrescrito(ctl, projeto,
                                                                       com_servidor):
    from tests.servidor_falso import entregar

    servidor, fila = com_servidor
    p = ctl.pagina
    ctl.reconhecer([0], refazer=True)                    # a cópia de antes
    entregar(fila, esperar_por=1)
    servidor.segurar.clear()
    ctl.reconhecer([0], refazer=True)                    # outro lote, relendo a 0
    ctl.voltar_ao_antes_do_lote()
    servidor.segurar.set()
    entregar(fila, esperar_por=1)
    assert ctl.fins[-1].reler_depois == [0] and p.historico.versao(p.modelo.pid) == 1


def test_o_que_falta_retomar_fica_no_projeto_e_volta_ao_reabrir(ctl, projeto):
    from abbychess.controladores import ARQUIVO_DO_LOTE

    ctl.reconhecer([0, 1, 2], refazer=True)
    fim = ctl.executor.comecar()
    fim()
    ctl.cancelar()
    ctl.executor.tudo()
    arquivo = projeto.pasta / ARQUIVO_DO_LOTE
    assert json.loads(arquivo.read_text(encoding="utf-8")) == {"paginas": [1, 2], "refazer": True}
    p = ctl.pagina                                        # reabre o projeto
    ctl.usar(projeto, p.fonte, p.leitor)
    assert ctl.restante == ([1, 2], True) and ctl.pode_retomar
    ctl.retomar()
    ctl.executor.tudo()
    assert ctl.fins[-1].lidas == [1, 2]
    assert not arquivo.exists() and ctl.restante is None


def test_o_servidor_que_desiste_para_o_lote_e_retomar_vale_ao_reabrir(ctl, projeto,
                                                                      com_servidor):
    from tests import servidor_falso

    servidor, fila = com_servidor
    servidor.segurar.clear()
    ctl.reconhecer([0, 1], refazer=True)
    servidor.derrubar()                                   # a segunda queda
    servidor_falso.entregar(fila, esperar_por=1)
    resultado = ctl.fins[-1]
    assert resultado.servidor_parou and not resultado.falhas and resultado.lidas == []
    assert ctl.restante == ([0, 1], True)
    assert not ctl.pode_retomar                           # "Não": o servidor está parado
    ctl.retomar()
    assert not ctl.lote_rodando
    novo = servidor_falso.ServidorFalso(projeto.pasta_de_padroes, projeto.dados.limiares)
    p = ctl.pagina                                        # "Sim": o projeto reabre
    ctl.usar(projeto, p.fonte, p.leitor)
    fila = servidor_falso.ligar(p, novo)
    assert ctl.pode_retomar
    ctl.retomar()
    servidor_falso.entregar(fila, esperar_por=1)
    servidor_falso.entregar(fila, esperar_por=1)
    assert ctl.fins[-1].lidas == [0, 1] and ctl.restante is None
