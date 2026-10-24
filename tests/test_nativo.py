"""CA-9.5: aceitar a camada tipográfica cria páginas sem pedir OCR ao servidor."""

from abbychess import nativo
from abbychess import pagina as pg
from abbychess import texto as tx
from abbychess.controlador import ControladorDePagina
from abbychess.controladores import ControladorDoLivro
from abbychess.projeto import ProjetoDeLivro

from tests import leitor_falso, servidor_falso
from tests.test_controlador import ExecutorManual
from tests.test_exportar_preciso import _pdf_digital


def test_pdf_nativo_e_oferecido_e_cria_paginas_sem_ocr(tmp_path):
    pdf = _pdf_digital(tmp_path / "digital.pdf", paginas=2)
    oferta = nativo.oferta(pdf)
    assert oferta.disponivel and oferta.aceitas == oferta.amostradas == 2

    projeto = ProjetoDeLivro.criar(tmp_path / "projetos", "Digital", pdf)
    resultado = nativo.importar(projeto)
    assert resultado.importadas == (0, 1) and resultado.recusadas == ()
    assert projeto.paginas_lidas() == [0, 1]
    pagina = projeto.carregar_modelo(0)
    assert "The knight on d5 is strong" in tx.texto(tx.montar(pagina))
    assert all(b.entry.source == nativo.FONTE_NATIVA and b.revisado for b in pagina.boxes)

    # Abrir o projeto já importado com o servidor falso não agenda leitura: a camada criou
    # páginas confirmadas, e não boxes "aguardando leitura".
    executor = ExecutorManual()
    controlador = ControladorDePagina(executar=executor)
    livro = ControladorDoLivro(controlador)
    leitor = leitor_falso.criar(projeto.pasta_de_padroes, projeto.dados.limiares)
    servidor = servidor_falso.ServidorFalso(projeto.pasta_de_padroes, projeto.dados.limiares)
    livro.usar(projeto, pg.FonteDePaginas(projeto.fonte), leitor, servidor)
    assert servidor.pedidos == []


def test_imagem_nao_oferece_texto_nativo(tmp_path):
    imagem = tmp_path / "pagina.png"
    imagem.write_bytes(b"nao precisa ser uma imagem valida")
    assert not nativo.oferta(imagem).disponivel
