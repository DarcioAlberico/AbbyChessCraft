"""Um servidor de leitura no mesmo processo, para a suíte rápida (SPEC §11).

Tem a interface do `ServidorDeLeitura` que a janela usa (`pedir`, `esperar`, `chamar`,
`cancelar`, os deltas, `pronto`, `parado`) e responde de uma thread, com as mesmas funções de
leitura do filho e o leitor falso (o que os padrões não leem sai "x", fonte `neural`). O teste
segura a leitura das páginas (`segurar.clear()`) para editar no meio dela, e o que volta à
interface entra numa lista (`na_interface`), que o teste esvazia quando quer (`entregar`).
"""

from __future__ import annotations

import itertools
import threading
from typing import Callable, List

from abbychess import servidor_de_leitura as sl

from tests import leitor_falso


class ServidorFalso:
    def __init__(self, pasta_de_padroes, limiares):
        self.leitor = leitor_falso.criar(pasta_de_padroes, limiares)
        self.pronto = threading.Event()
        self.pronto.set()
        self.desistiu = False
        self.estado = {"rede": False, "base": 0}
        #: Limpo, a leitura de página espera (o teste edita enquanto o "servidor" lê).
        self.segurar = threading.Event()
        self.segurar.set()
        self.pedidos: List[sl.Pedido] = []
        self.cancelados: set = set()
        self._ids = itertools.count(1)
        self.fechado = False

    @property
    def parado(self) -> bool:
        return self.desistiu or self.fechado

    def derrubar(self) -> None:
        """A segunda queda: o servidor desiste, e a leitura em curso falha como no de
        verdade."""
        self.desistiu = True
        self.segurar.set()

    def pedir(self, operacao: str, argumentos=None, *, prioridade: int = sl.INTERATIVO,
              ao_terminar: Callable = None) -> sl.Pedido:
        pedido = sl.Pedido(next(self._ids), operacao, prioridade, ("pedido",), ao_terminar)
        self.pedidos.append(pedido)
        threading.Thread(target=self._responder, args=(pedido, argumentos), daemon=True).start()
        return pedido

    def _responder(self, pedido: sl.Pedido, argumentos) -> None:
        try:
            if pedido.operacao == "ler_pagina":
                self.segurar.wait(30)
                if pedido.id in self.cancelados:
                    raise sl.Cancelado
                if self.desistiu:
                    raise RuntimeError("o servidor de leitura caiu duas vezes")
                imagem, zonas, marcados = argumentos
                resultado = sl.ler_pagina(imagem, zonas, marcados, self.leitor)
            elif pedido.operacao == "reler_boxes":
                imagem, boxes, so_pendentes = argumentos
                resultado = sl.reler_boxes(imagem, boxes, self.leitor, so_pendentes=so_pendentes)
            elif pedido.operacao == "ler_recortes":
                resultado = sl.ler_recortes(argumentos, self.leitor)
            else:
                raise ValueError(f"operação desconhecida {pedido.operacao!r}")
        except sl.Cancelado:
            pedido.ok, pedido.resultado = False, sl.CANCELADO
        except Exception as erro:  # volta como resposta, como no filho
            pedido.ok, pedido.resultado = False, str(erro)
        else:
            pedido.ok, pedido.resultado = True, resultado
        pedido.feito.set()
        if pedido.ao_terminar is not None:
            pedido.ao_terminar(pedido)

    def esperar(self, pedido: sl.Pedido, timeout=None):
        if not pedido.feito.wait(timeout):
            raise TimeoutError(pedido.operacao)
        if not pedido.ok:
            if pedido.cancelado:
                raise sl.Cancelado
            raise sl.ErroDoServidor(str(pedido.resultado))
        return pedido.resultado

    def chamar(self, operacao: str, argumentos=None, *, prioridade: int = sl.INTERATIVO,
               timeout=None):
        return self.esperar(self.pedir(operacao, argumentos, prioridade=prioridade), timeout)

    def cancelar(self, pedido: sl.Pedido) -> None:
        self.cancelados.add(pedido.id)

    def enviar_padroes(self, criados, apagados) -> None:
        for caminho in apagados:
            self.leitor.padroes.excluir(caminho)
        for caminho, altura in criados:
            self.leitor.padroes.incluir(caminho, altura)

    def trocar_limiares(self, limiares) -> None:
        self.leitor.trocar_limiares(limiares)

    def abandonar_pendentes(self) -> None:
        pass

    def fechar(self, espera: float = 5.0) -> None:
        self.fechado = True
        self.segurar.set()


def ligar(controlador, servidor: ServidorFalso) -> list:
    """Põe o servidor falso no controlador (como `ligar(..., servidor)`) e devolve a lista
    do que volta à interface; `entregar(lista)` a esvazia."""
    controlador.servidor = servidor
    controlador._enviados = controlador.padroes()
    fila: list = []
    controlador.executar.na_interface = fila.append
    return fila


def entregar(fila: list, *, esperar_por: int = 0, limite: float = 10.0) -> int:
    """Roda o que voltou à interface; com `esperar_por`, espera chegarem tantos antes."""
    import time

    fim = time.monotonic() + limite
    while len(fila) < esperar_por and time.monotonic() < fim:
        time.sleep(0.005)
    feitos = 0
    while fila:
        fila.pop(0)()
        feitos += 1
    return feitos
