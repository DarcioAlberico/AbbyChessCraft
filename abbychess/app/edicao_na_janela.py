"""A edição no Documento vista da janela (SPEC §6.3 e §6.4): a sessão confirmada,
a recusa, o desfazer e o refazer que olham a sessão aberta, a paleta e as figurinas. Um
mixin da `JanelaPrincipal`, como `EspacoDeTrabalho`.
"""

from __future__ import annotations

from typing import Optional

from abbychess.app import teclado

class EdicaoNoDocumento:
    def _sessao_do_documento(self, unidades, novo, avancar, ensinar_gid, ultimo, fixos,
                             fim_de_linha=False, agora=False) -> None:
        """A sessão confirmada: o controlador aplica; quando a edição entra na página (na
        hora, ou na vez dela na fila), o Documento é montado de novo do modelo e o cursor fica
        onde estava ao confirmar (o texto montado é o digitado: sair da sessão para outra
        palavra fica nela; Shift+Enter fica ali), ou, com Enter, vai à próxima duvidosa."""
        marca = self.texto.marca_ao_confirmar

        def entrou() -> None:
            self.pintar_texto()
            if avancar:
                depois = self.texto.posicao_do_gid(ultimo) if ultimo is not None else None
                self.texto.ir_a_proxima_duvidosa(depois if depois is not None else 0)
            else:
                self.texto.ir_a_marca(marca)
        self.pagina.confirmar_sessao(unidades, novo, ensinar_gid=ensinar_gid, fixos=fixos,
                                     depois=entrou, fim_de_linha=fim_de_linha,
                                     agora=agora)

    def confirmar_a_sessao_aberta(self, agora: bool = False) -> None:
        """Antes de sair da página (outra página, o Ctrl+T, fechar o projeto): a sessão aberta
        do Documento confirma agora, na página dela (§6.3), em vez de se perder. `agora`:
        sem a fila (ao fechar o projeto, que a esvazia)."""
        if self.texto.tem_sessao:
            self.texto.confirmar(avancar=False, agora=agora)

    def _sessao_recusada(self, motivo: str) -> None:
        self._aviso_estrutural(f"Edição recusada: {motivo}")
        self.pintar_texto()                     # a palavra volta ao que era

    def _caractere_sugerido(self, letra: str, confianca: Optional[float] = None) -> None:
        """O box marcado ao lado de uma letra virtual: a letra dela no campo do Glifo,
        selecionada (Enter a confirma; digitar troca). Com a `confianca`, é o palpite da rede
        para o glifo que ninguém leu (§9.2), que só entra no campo ainda vazio."""
        if confianca is not None:
            self.treino.sugerir(letra, confianca)
            return
        self.treino.campo.setText(letra)
        self.treino.campo.selectAll()

    def _sem_duvidosas(self) -> None:
        self._aviso_estrutural(teclado.com_teclas(
            "Nenhuma palavra duvidosa depois desta na página · {proxima_pagina_pendente} vai à "
            "próxima página com pendentes"))

    def _aviso_estrutural(self, texto: str) -> None:
        """Na Linha e também na barra de status (a Linha pode estar escondida, Ctrl+F5)."""
        self.linha.avisar(texto)
        self.statusBar().showMessage(texto, 8000)

    def _no_editor_de_diagrama(self) -> bool:
        """O foco está no editor Diagrama do Inspetor (o desfazer é o do tabuleiro, §10)."""
        foco = self.focusWidget()
        editor = self.editor_diagrama
        return foco is not None and (foco is editor or editor.isAncestorOf(foco))

    def desfazer(self) -> None:
        """Ctrl+Z: com o foco no editor Diagrama, a última casa editada (sem casa a desfazer,
        vale o da página, como desfazer a conferência); com uma sessão
        aberta no Documento, ela volta ao que era (Ctrl+Y a reaplica); senão, o desfazer do
        projeto."""
        if self._no_editor_de_diagrama() and self.editor_diagrama.pode_desfazer:
            self.editor_diagrama.desfazer()
        elif self.texto.tem_sessao:
            self.texto.restaurar()
        else:
            self.texto.esquecer_a_restaurada()
            self.pagina.desfazer()

    def refazer(self) -> None:
        if self._no_editor_de_diagrama() and self.editor_diagrama.pode_refazer:
            self.editor_diagrama.refazer()
        elif self.texto.pode_reaplicar:
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
        """Ctrl+Shift+K/Q/R/B/N/P: no Documento ou no campo do Glifo, onde estiver o foco."""
        if self.treino.campo.hasFocus():
            self.treino.inserir_figurina(figurina)
        else:
            self.texto.inserir_figurina(figurina)

    def novo_paragrafo(self) -> None:
        gid = self.texto.primeiro_gid_da_palavra()
        self.confirmar_a_sessao_aberta()
        self.pagina.novo_paragrafo(gid)

    def alternar_estilo(self, campo: str) -> None:
        gids = self.texto.gids_selecionados()
        self.confirmar_a_sessao_aberta()
        self.pagina.alternar_estilo(gids, campo)
