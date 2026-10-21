"""Um processo como o do programa (o Qt já carregado) que abre o servidor de leitura e
pergunta ao filho o que ele importou: `python -m tests.app_falso <pasta>` imprime a lista.

Rodado por `tests/test_servidor.py` (camada `processo`): o filho do `spawn` importa este
módulo como `__mp_main__`, e a guarda o deixa sem o Qt, como a de `abbychess/__main__.py`.
"""

if __name__ == "__main__":
    import sys

    import PySide6.QtCore  # noqa: F401 (o pai tem o Qt, como a janela)

    from abbychess import servidor_de_leitura as sl
    from abbychess.projeto import Limiares

    servidor = sl.ServidorDeLeitura(sys.argv[1], Limiares(), fabrica="tests.leitor_falso:criar")
    try:
        print(servidor.chamar("modulos", timeout=60))
    finally:
        servidor.fechar()
