"""A edição no Documento vista da janela (SPEC §6.3, §6.4, passo D1): a sessão confirmada,
a recusa, o desfazer e o refazer que olham a sessão aberta, a paleta e as figurinas. Um
mixin da `JanelaPrincipal`, como `EspacoDeTrabalho`.
"""

from __future__ import annotations


class EdicaoNoDocumento:
    def _sessao_do_documento(self, unidades, novo, avancar, ensinar_gid, ultimo, fixos) -> None:
        """A sessão confirmada: o controlador aplica; quando a edição entra na página (na
        hora, ou na vez dela na fila), o Documento é montado de novo do modelo e o cursor vai
        ao fim da palavra (ou, com Enter, à próxima duvidosa)."""
        def entrou() -> None:
            self.pintar_texto()
            if avancar:
                depois = self.texto.posicao_do_gid(ultimo) if ultimo is not None else None
                self.texto.ir_a_proxima_duvidosa(depois if depois is not None else 0)
            else:
                self.texto.ir_ao_fim_do_gid(ultimo)
        self.pagina.confirmar_sessao(unidades, novo, ensinar_gid=ensinar_gid, fixos=fixos,
                                     depois=entrou)

    def _sessao_recusada(self, motivo: str) -> None:
        self.linha.avisar(f"Edição recusada: {motivo}")
        self.pintar_texto()                     # a palavra volta ao que era

    def desfazer(self) -> None:
        """Ctrl+Z: com uma sessão aberta no Documento, ela volta ao que era (Ctrl+Y a
        reaplica); senão, o desfazer do projeto."""
        if self.texto.tem_sessao:
            self.texto.restaurar()
        else:
            self.texto.esquecer_a_restaurada()
            self.pagina.desfazer()

    def refazer(self) -> None:
        if self.texto.pode_reaplicar:
            self.texto.reaplicar()
        else:
            self.pagina.refazer()

    def abrir_paleta(self) -> None:
        """F2: a paleta no Documento (o cursor de texto) ou no campo do Glifo."""
        if self.texto.hasFocus():
            self.texto.abrir_paleta()
        else:
            self.treino.abrir_paleta()

    def confirmar_no_documento(self, avancar: bool = False, ensinar: bool = False) -> None:
        """Enter (`avancar`), Shift+Enter e Ctrl+Enter (`ensinar`) no Documento."""
        self.texto.confirmar(avancar=avancar, ensinar=ensinar)

    def inserir_figurina(self, figurina: str) -> None:
        self.texto.inserir_figurina(figurina)
