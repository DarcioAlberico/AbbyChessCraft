"""Os estados vazios (SPEC §13): o que cada painel diz quando não tem o que mostrar.

Um painel vazio sem palavra nenhuma parece quebrado; com a instrução, ele diz o próximo
passo e a tecla dele. As frases ficam aqui para os painéis dizerem a mesma coisa. As teclas
saem do perfil de agora (`teclado`): no FineReader o F5 mostra Páginas e o Ctrl+F9 reconhece.
"""

from abbychess.app import teclado


_tecla = teclado.tecla


def sem_projeto() -> str:
    return (f"Nenhum livro aberto.\n{_tecla('novo_projeto', 'Projeto › Novo')} cria um projeto "
            f"a partir de um PDF ou de uma imagem; {_tecla('abrir_projeto', 'Projeto › Abrir')} "
            "abre um projeto.")


def pagina_nao_reconhecida() -> str:
    return (f"Página não reconhecida. {_tecla('reconhecer_pagina', 'Página › Reconhecer')} "
            f"reconhece; {_tecla('marcar_glifo', 'o menu da Imagem')} marca glifos à mão.")


def nada_reconhecido() -> str:
    return (f"Nada reconhecido nesta página. {_tecla('marcar_glifo', 'O menu da Imagem')} marca "
            f"glifos à mão; {_tecla('reconhecer_pagina', 'Página › Reconhecer')} lê de novo.")


def escolha_a_fila_de_palavras() -> str:
    """A Verificação sem fila de palavras: no FineReader, Ctrl+F7 a escolhe; no padrão, o
    F7 cicla o modo da fila até ela."""
    direta = teclado.tecla("fila_em_palavras")
    como = (direta if direta else
            f"{_tecla('ciclar_modo_da_fila', 'o modo da fila no Inspetor')} cicla até ela")
    return f"Escolha a fila de palavras desconhecidas ({como}) para verificar o texto."


SEM_PADROES = ("Nenhum padrão ensinado ainda. No Glifo, digite o caractere do box e aperte "
               "Enter: ele vira padrão deste livro.")
