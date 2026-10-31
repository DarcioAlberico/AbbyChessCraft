"""As páginas visitadas e o sentido da pré-carga (§3.3, §14.1), à parte do `ControladorDePagina`
(SPEC-qualidade Q-A1). Abrir a página é do controlador (`ir_para`); aqui ficam o Alt+← e o
Alt+→, a primeira, a última, a vizinha, e a página que a pré-carga prepara."""

from __future__ import annotations

from typing import List, Optional


class Navegador:
    def __init__(self, p) -> None:
        self._p = p
        self.zerar()

    def zerar(self) -> None:
        """Outro projeto: nenhuma visita, e a pré-carga para a frente."""
        #: +1 ou -1: o sentido do último passo entre páginas, o da pré-carga.
        self._sentido = 1
        #: As páginas visitadas, para Alt+← e Alt+→ (§3.3), e onde se está nelas.
        self.visitas: List[int] = []
        self._visita = -1

    def chegou(self, de: int, para: int, *, visita: bool) -> None:
        """O `ir_para` abriu `para` (vindo de `de`); `visita=False` é o Alt+← e o Alt+→, que
        andam nas visitas sem mudá-las."""
        if para != de:
            self._sentido = 1 if para > de else -1
        if visita:
            self._registrar_visita(para)

    def precarregar_seguinte(self) -> None:
        """Renderiza a próxima página no sentido em que se anda (a seguinte, ou a anterior
        depois de um PgUp), a mais provável, noutra thread. A janela chama depois de pintar a
        atual: dentro do `ir_para`, a pré-carga disputava a CPU com a conversão e a pintura
        da página pedida, e a troca fora do cache ficava ~60 ms mais lenta."""
        if self._p.cache is not None and self._p.fonte is not None:
            self._p.cache.precarregar(self.proxima_provavel)

    @property
    def proxima_provavel(self) -> int:
        """A página que a pré-carga prepara: a vizinha no sentido do último passo; na ponta do
        livro (o Home deixa o sentido para trás na primeira), a do outro lado."""
        alvo = self._p.indice + self._sentido
        total = self._p.fonte.total if self._p.fonte is not None else 0
        return alvo if 0 <= alvo < total else self._p.indice - self._sentido

    def _registrar_visita(self, indice: int) -> None:
        if 0 <= self._visita < len(self.visitas) and self.visitas[self._visita] == indice:
            return
        del self.visitas[self._visita + 1:]
        self.visitas.append(indice)
        self._visita = len(self.visitas) - 1

    @property
    def pode_voltar(self) -> bool:
        return self._visita > 0

    @property
    def pode_avancar(self) -> bool:
        return self._visita < len(self.visitas) - 1

    def voltar_visita(self) -> bool:
        """Alt+←: a página visitada antes desta."""
        return self._andar_na_visita(-1)

    def avancar_visita(self) -> bool:
        """Alt+→: a página visitada depois (depois de um Alt+←)."""
        return self._andar_na_visita(+1)

    def _andar_na_visita(self, passo: int) -> bool:
        alvo = self._visita + passo
        if not 0 <= alvo < len(self.visitas):
            return False
        if not self._p.ir_para(self.visitas[alvo], visita=False):
            return False
        self._visita = alvo
        self._p.eventos.emitir("acoes_mudaram")    # Alt+←/→ ligam e desligam pelo lugar novo
        return True

    def pids_das_visitas(self, projeto) -> List[Optional[int]]:
        """As visitas pelo pid, antes de a ordem do livro mudar (`seguir_a_sequencia`)."""
        return [projeto.pid_da_pagina(i) for i in self.visitas]

    def seguir_a_sequencia(self, pids: List[Optional[int]], nova) -> None:
        """As visitas na ordem `nova`, pelos `pids` de antes: a de agora é a que sobra até ela
        (a mesma página pode estar duas vezes), e as vizinhas iguais que a saída de uma deixou
        se juntam."""
        novas, lugar = [], -1
        for k, pid in enumerate(pids):
            posicao = None if pid is None else nova.posicao_de(pid)
            if posicao is not None and (not novas or novas[-1] != posicao):
                novas.append(posicao)
            if k == self._visita:
                lugar = len(novas) - 1
        self.visitas, self._visita = novas, lugar if novas else -1

    def primeira(self) -> bool:
        return self._p.ir_para(0)

    def ultima(self) -> bool:
        return self._p.fonte is not None and self._p.ir_para(self._p.fonte.total - 1)

    def vizinha(self, passo: int) -> bool:
        """A página anterior (-1) ou a seguinte (+1), se houver."""
        return self._p.ir_para(self._p.indice + passo)
