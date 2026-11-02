"""O fluxo compacto de criação do livro (§9.1)."""

from types import SimpleNamespace

import pytest

from abbychess.app import dialogos
from abbychess.projeto import ProjetoDeLivro
from tests.ajudantes import pdf_sintetico  # noqa: E402,F401,F811


@pytest.mark.parametrize(("texto", "total", "esperado"), [
    ("", 12, (0, 11)),
    ("5-10", 20, (4, 9)),
    ("7", 20, (6, 6)),
])
def test_intervalo_do_corpo(texto, total, esperado):
    assert dialogos.intervalo_do_corpo(texto, total) == esperado


def test_intervalo_do_corpo_recusa_paginas_descontinuas():
    with pytest.raises(ValueError, match="contínuo"):
        dialogos.intervalo_do_corpo("2-4, 8", 10)


@pytest.mark.parametrize(("paridade", "esperado"), [
    ("Todas", [1, 2, 3, 4, 5]),
    ("Páginas ímpares", [2, 4]),
    ("Páginas pares", [1, 3, 5]),
])
def test_modelo_de_areas_filtra_intervalo_por_numero_visivel(monkeypatch, paridade, esperado):
    monkeypatch.setattr(dialogos.QInputDialog, "getText",
                        lambda *_a, **_k: ("2-6", True))
    monkeypatch.setattr(dialogos.QInputDialog, "getItem",
                        lambda *_a, **_k: (paridade, True))

    assert dialogos.paginas_do_modelo_de_areas(None, 10) == esperado


def test_cancelar_ou_errar_o_intervalo_nao_da_paginas_ao_lote_nem_ao_modelo(projeto, monkeypatch):
    avisos = []
    monkeypatch.setattr(dialogos.QMessageBox, "warning", lambda _j, _t, texto: avisos.append(texto))
    monkeypatch.setattr(dialogos.QInputDialog, "getText", lambda *_a, **_k: ("1-3", False))
    assert dialogos.intervalo_do_lote(None, projeto, 3) is None          # Cancelar
    assert dialogos.paginas_do_modelo_de_areas(None, 3) is None
    monkeypatch.setattr(dialogos.QInputDialog, "getText", lambda *_a, **_k: ("1-x", True))
    assert dialogos.intervalo_do_lote(None, projeto, 3) is None          # o aviso diz o quê
    assert dialogos.paginas_do_modelo_de_areas(None, 3) is None
    assert avisos == ["Não entendi '1-x'. Use, por exemplo, 26-27, 30."] * 2


def test_o_lote_pergunta_pelas_ja_lidas_e_conta_as_verificadas(projeto, monkeypatch):
    from core.box_model import BoxEntry

    from abbychess.modelo import VERIFICADA

    caixa = [BoxEntry(char="a", x1=10, y1=10, x2=20, y2=30, source="manual", confidence=1.0)]
    projeto.salvar_pagina(0, caixa)
    projeto.salvar_pagina(1, caixa)
    verificada = projeto.pagina_para_editar(1)
    verificada.estado = VERIFICADA
    projeto.salvar_modelo(verificada)
    botoes = dialogos.QMessageBox.StandardButton
    perguntas, respostas = [], iter([botoes.Cancel, botoes.Yes])

    def responder(_janela, _titulo, texto, *_a):
        perguntas.append(texto)
        return next(respostas)
    monkeypatch.setattr(dialogos.QMessageBox, "question", responder)
    monkeypatch.setattr(dialogos.QInputDialog, "getText", lambda *_a, **_k: ("1-3", True))
    assert dialogos.intervalo_do_lote(None, projeto, 3) is None          # Cancelar
    assert dialogos.intervalo_do_lote(None, projeto, 3) == ([0, 1, 2], True)   # Sim: de novo
    assert perguntas[0].startswith("1 das 3 páginas já foram reconhecidas (1 verificada(s), "
                                   "que o lote pula sempre). Ler essas de novo?")


def test_novo_projeto_guarda_idioma_e_intervalo_no_mesmo_fluxo(app, tmp_path, monkeypatch):  # noqa: F811
    fonte = pdf_sintetico(tmp_path)
    destino = tmp_path / "projetos"
    valores = {}

    class Config:
        def value(self, chave, padrao):
            return padrao

        def setValue(self, chave, valor):
            valores[chave] = valor

    janela = SimpleNamespace(config=Config(), statusBar=lambda: SimpleNamespace(showMessage=lambda *_: None))
    monkeypatch.setattr(dialogos.QFileDialog, "getOpenFileName",
                        lambda *_a, **_k: (str(fonte), ""))
    monkeypatch.setattr(dialogos.QFileDialog, "getExistingDirectory",
                        lambda *_a, **_k: str(destino))
    monkeypatch.setattr(dialogos.DialogoDeNovoProjeto, "obter",
                        lambda *_a, **_k: dialogos.OpcoesDoNovoProjeto("Meu livro", "en", (1, 2)))
    monkeypatch.setattr(dialogos.nativo, "oferta", lambda *_a, **_k: dialogos.nativo.Oferta(0, 0))

    projeto = dialogos.novo_projeto(janela)
    try:
        assert projeto.dados.idioma == "en"
        assert projeto.dados.extras["intervalo_do_corpo"] == [1, 2]
        assert projeto.dados.extras["amostra_guiada_pendente"] is True
        assert projeto.dados.extras[dialogos.livro.CHAVE_DOS_CANDIDATOS_DA_AMOSTRA] == [1, 2]
        reaberto = ProjetoDeLivro.abrir(projeto.pasta)
        try:
            assert reaberto.dados.idioma == "en"
            assert reaberto.dados.extras["intervalo_do_corpo"] == [1, 2]
        finally:
            reaberto.fechar()
    finally:
        projeto.fechar()
    assert valores["ultima_fonte"] == str(fonte.parent)


def test_texto_nativo_parcial_deixa_so_as_recusadas_para_a_amostra(app, tmp_path, monkeypatch):  # noqa: F811
    fonte = pdf_sintetico(tmp_path)
    janela = SimpleNamespace(
        config=SimpleNamespace(value=lambda _chave, padrao: padrao, setValue=lambda *_: None),
        statusBar=lambda: SimpleNamespace(showMessage=lambda *_: None))
    monkeypatch.setattr(dialogos.QFileDialog, "getOpenFileName",
                        lambda *_a, **_k: (str(fonte), ""))
    monkeypatch.setattr(dialogos.QFileDialog, "getExistingDirectory",
                        lambda *_a, **_k: str(tmp_path / "projetos"))
    monkeypatch.setattr(dialogos.DialogoDeNovoProjeto, "obter",
                        lambda *_a, **_k: dialogos.OpcoesDoNovoProjeto("Parcial", "pt", (0, 2)))
    monkeypatch.setattr(dialogos.nativo, "oferta", lambda *_a, **_k: dialogos.nativo.Oferta(2, 3))
    monkeypatch.setattr(dialogos.QMessageBox, "question",
                        lambda *_a, **_k: dialogos.QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(dialogos.nativo, "importar",
                        lambda *_a, **_k: dialogos.nativo.Resultado((0, 2), (1,)))

    projeto = dialogos.novo_projeto(janela)
    try:
        assert projeto.dados.extras["amostra_guiada_pendente"] is True
        assert projeto.dados.extras[dialogos.livro.CHAVE_DOS_CANDIDATOS_DA_AMOSTRA] == [1]
    finally:
        projeto.fechar()



def test_o_idioma_sugerido_pela_camada_do_pdf_vem_escolhido(app, tmp_path, monkeypatch):  # noqa: F811
    """O novo projeto pergunta o idioma já com o que a camada de texto do PDF diz (Mirkovic:
    o projeto em inglês nasceu em português, o primeiro da lista)."""
    from abbychess.app.opcoes import DialogoDeOpcoes
    from abbychess.projeto import Limiares

    fonte = pdf_sintetico(tmp_path)
    vistos = {}

    def obter(_parent, nome, total, idioma=None):
        vistos["idioma"] = idioma
        return None
    monkeypatch.setattr(dialogos.idm, "da_camada_do_pdf", lambda caminho: "en")
    monkeypatch.setattr(dialogos.DialogoDeNovoProjeto, "obter", obter)
    monkeypatch.setattr(dialogos.QFileDialog, "getOpenFileName",
                        lambda *_a, **_k: (str(fonte), ""))
    janela = SimpleNamespace(config=SimpleNamespace(value=lambda _c, p: p, setValue=lambda *_: None))
    assert dialogos.novo_projeto(janela) is None and vistos["idioma"] == "en"

    dialogo = dialogos.DialogoDeNovoProjeto(None, "Livro", 10, "en")
    assert dialogo.idioma.currentData() == "en"
    assert dialogos.DialogoDeNovoProjeto(None, "Livro", 10).idioma.currentData() == "pt"
    opcoes = DialogoDeOpcoes(Limiares(), None, idioma="en")
    assert opcoes.idioma() == "en"
