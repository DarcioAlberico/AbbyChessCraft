"""O servidor de leitura e o lote vistos da janela (SPEC §11, passo E): os modelos prontos,
a queda do servidor, o progresso e o fim do lote, os resultados e "Voltar ao estado antes do
lote". Um mixin da `JanelaPrincipal`, como `EspacoDeTrabalho`.
"""

from __future__ import annotations

from abbychess import avisos as av
from abbychess import lote as lt
from abbychess.app import dialogos


class LoteNaJanela:
    def _modelos_prontos(self, estado: dict) -> None:
        self.carregando.hide()
        leitor = self.leitor
        dialogos.avisos_dos_modelos(self, estado, leitor.arquivos_de_padrao() if leitor else 0)

    def _servidor_caiu(self, texto: str, desistiu: bool) -> None:
        """§11: a primeira queda do servidor de leitura (reaberto sozinho) vai para os Avisos;
        na segunda ele desistiu, e a janela oferece reabrir o projeto."""
        self.registrar_aviso(av.ERRO if desistiu else av.AVISO, "Servidor de leitura", texto)
        if not desistiu or self.projeto is None:
            return
        self.carregando.hide()
        servidor = self.pagina.servidor
        if servidor is not None and servidor.estado is None:
            # Nunca carregou os modelos: reabrir cairia no mesmo erro (m13 do passo E).
            pergunta = (f"O servidor de leitura não conseguiu carregar os modelos: {texto}\n\n"
                        "Abrir o projeto sem o servidor? Os modelos carregam na própria "
                        "janela, que usa mais memória e pode engasgar durante o lote. O "
                        "rastro completo está no log do programa.")
            sem_servidor = True
        else:
            pergunta, sem_servidor = texto + "\n\nReabrir o projeto agora?", False
        if dialogos.confirmar(self, "Servidor de leitura", pergunta):
            if sem_servidor:
                self.livro.sem_servidor = True              # nesta sessão
            pasta = self.projeto.pasta
            if self._fechar_projeto():
                self.abrir_caminho(str(pasta))

    def voltar_ao_antes_do_lote(self) -> None:
        quando = self.projeto.data_antes_do_lote(self.pagina.indice) if self.projeto else None
        de = f" (a cópia de {quando:%d/%m/%Y às %H:%M})" if quando else ""
        if dialogos.confirmar(self, "Voltar ao estado antes do lote", "A página volta a ser a "
                              f"de antes do último lote com \u201crefazer\u201d{de}; tudo o que "
                              "mudou nela depois disso se perde (e não entra no desfazer). "
                              "Voltar?"):
            self.livro.voltar_ao_antes_do_lote()

    def _lote_progrediu(self, feitas: int, total: int, estimativa) -> None:
        texto = f"Lote: {feitas} de {total}"
        if estimativa:
            texto += f", cerca de {_duracao(estimativa)}"
        self.rotulo_do_lote.setText(texto)
        self.paginas.mostrar_lote(feitas, total, texto)

    def _pagina_do_lote(self, _indice: int) -> None:
        self.relogio_das_paginas.start()        # a gaveta, depois de uma rajada de páginas

    def _resultado(self, titulo: str, texto: str) -> None:
        """O que um comando deixou para conferir (Resultados / Avisos), sem diálogo."""
        self.registrar_aviso(av.AVISO, titulo, texto)

    def _lote_terminou(self, mensagem: str, resultado) -> None:
        self.paginas.esconder_lote()
        self.rotulo_do_lote.setText("")
        if lt.tem_detalhe(resultado):          # o lote limpo não é um aviso
            self.registrar_aviso(av.ERRO if resultado.servidor_parou else av.AVISO,
                                 "Reconhecer o livro", lt.detalhe_do_fim(resultado))
        if self.pagina.indice in resultado.lidas:
            self.pintar_texto()


    def retomar_lote(self) -> None:
        """Projeto › Retomar o lote: o que faltou e, se o usuário quiser, as páginas que o lote
        não sobrescreveu porque ele as tinha mudado."""
        livro = self.livro
        com_reler = False
        if livro.pode_retomar and livro.reler_depois:
            resposta = dialogos.reler_depois(self, livro.reler_depois,
                                             faltou=livro.restante is not None)
            if resposta is None:
                return
            com_reler = resposta
        livro.retomar(com_reler)


def _duracao(segundos: float) -> str:
    """O tempo estimado do lote, arredondado como se fala: "40 s", "3 min", "1 h 20 min"."""
    if segundos < 60:
        return f"{max(1, round(segundos / 10) * 10)} s"
    minutos = round(segundos / 60)
    if minutos < 60:
        return f"{minutos} min"
    return f"{minutos // 60} h {minutos % 60:02d} min"
