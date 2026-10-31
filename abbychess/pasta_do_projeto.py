"""Os nomes dos arquivos e das pastas de um projeto e a versão do formato dele (a forma da
pasta está no docstring de `abbychess.projeto`), à parte do `ProjetoDeLivro` (SPEC-qualidade
Q-A1): o projeto e a migração (`abbychess.migracoes`) os leem daqui, e `abbychess.projeto`
continua a reexportá-los para quem os importa de lá."""

ARQUIVO_DO_PROJETO = "projeto.json"
PASTA_DE_PADROES = "padroes"
PASTA_DE_PAGINAS = "paginas"
#: A página como estava antes de o lote com "refazer" a reler (§4.6), uma por pid.
PASTA_ANTES_DO_LOTE = ".antes-do-lote"
#: As páginas que só têm glifos marcados à mão no modo de treino, sem o F5.
ARQUIVO_DAS_MARCADAS = "marcadas.json"
PASTA_DE_ZONAS = "zonas"
ARQUIVO_DO_LEXICO = "lexico.txt"
ARQUIVO_DO_LIVRO = "livro.json"
#: 2: o modelo v2 (passo 1b): páginas em `paginas/p<pid>.json`, com gids e decisões.
#: 3: a sequência do livro em `projeto.json` (passo L, §12.4): toda página tem `pid` gravado,
#: e as listas de páginas, as inclinações, `janela.json` e `lote.json` são por `pid`.
VERSAO = 3
#: Onde a primeira abertura v2 guarda o projeto v1 de antes (§4.3).
PASTA_DO_BACKUP_V1 = "backup-v1"
#: Onde a primeira abertura v3 guarda os arquivos da v2 que ela muda (§12.4, CA-12.7).
PASTA_DO_BACKUP_V2 = "backup-v2"
#: Os arquivos do projeto que guardam páginas por posição até a v2 e por `pid` desde a v3.
ARQUIVO_DE_INCLINACOES = "inclinacoes.json"
ARQUIVO_DA_JANELA = "janela.json"
ARQUIVO_DO_LOTE = "lote.json"
#: As listas de posições do `projeto.json` (em `extras`) que passam a `pid` na v3: o corpo
#: (`app.dialogos`), a amostra guiada (`livro`) e a camada de texto nativa (`nativo`).
LISTAS_DE_PAGINAS = ("intervalo_do_corpo", "candidatos_da_amostra_guiada",
                     "paginas_da_amostra_guiada", "paginas_da_camada_nativa")
#: E os mapas posição -> número (os pendentes da amostra guiada ao terminar).
MAPAS_DE_PAGINAS = ("pendentes_iniciais_da_amostra",)
