"""`python -m abbychess [pasta-do-projeto]`.

A guarda é obrigatória (SPEC §11): o servidor de leitura nasce com `spawn`, e o filho importa
este módulo como `__mp_main__`; sem ela, o filho abriria outra janela em vez de ler.
"""

if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()            # o executável empacotado também abre o filho

    from abbychess.app.principal import main

    raise SystemExit(main())
