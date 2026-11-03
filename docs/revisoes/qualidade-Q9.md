# Passo Q9 — mutação (2026-11-01 a 2026-11-03, ramo `qualidade-q9`)

Décimo e último passo de `plans/roadmap-qualidade.md`, a partir do `962def4` (o Q8 mesclado no
`passo-i-treino`), na worktree irmã `C:\Python-Chess2\AbbyChessCraft-qualidade`. O CA-Q-M1 pede
≥ 85 % de mutantes mortos em cada módulo puro, com os sobreviventes virando teste ou código
apagado; o CA-Q-E7, os privados do PyBoxEditor numa lista que encolhe, cada um com pedido e
contrato.

## A alavanca: `ferramentas/mutador.py`

O `mutmut` 3 não roda no Windows, e o `cosmic-ray` não estava instalado (baixá-lo pedia
permissão). Como o crapper e o dryer, o mutador é da casa, pelo AST, testado num brinquedo
(`tests/test_mutador.py`: as partes puras na rápida, a medida inteira na camada `processo`).

- Os mutantes: comparação (também `is` e `in`), aritmético, atribuição, `and`/`or`, `not`
  tirado, condição do `if` e do `while` negada, a constante inteira mais um, `True`/`False`,
  `break`/`continue`; trocados no texto, nas posições do AST convertidas de bytes para
  caracteres.
- Os testes: os que importam o módulo; uma rodada sem mutante, com a cobertura por teste
  (`--cov-context=test`), diz quem passa por cada linha, e cada mutante roda só esses, com
  `-x`. Cada trabalhador numa cópia do projeto, sem bytecode, com o teto da rápida desligado.
- A medida grava o JSON a cada mutante e continua de onde parou (`--continuar`), em partes de
  menos de 10 minutos (`--ate-minutos`), reaproveitando a cobertura (`.contextos`).

Os defeitos da própria alavanca, cada um com o teste vermelho antes: o `U+2029` numa string do
`sessao` partia as linhas (`b6c50e2`, `6966e2f`); as linhas que rodam na importação (as
constantes, os valores padrão) têm o contexto vazio e valem para todos os testes do módulo
(`f1bde33`, `4de1be5`; também com outro teste nelas, `02142c2`, `7ca7117`); o mutante que
derruba o conftest é morto (`9ec1dc8`, `3b1168f`); `--marcas`, para os testes da camada
`processo` do pool do índice (`3ec6796`, `e03f4b0`); a cobertura guardada entre as partes
(`1427539`); o tempo estourado mata a árvore do pytest, e não só ele (`6e4eb83`: um neto
segurava a saída, e uma parte de 8,5 minutos levou 29).

## Os oito módulos puros

Medida oficial no `3265d20` (`docs/medidas/mutacao/<módulo>-3265d20.json`), com 2 trabalhadores:

| Módulo | Antes | Depois | Commits |
|---|---|---|---|
| `sequencia` | 87,2 % | **98,4 %** (246/250) | `50fc97f` à mão (o molde) |
| `historico` | 56,8 % | **94,8 %** (202/213) | `d8c5f8b` |
| `lances` | 79,2 % | **94,2 %** (195/207) | `77e5596` |
| `sessao` | 78,8 % | **93,1 %** (433/465) | `5c7f735`, `be1c10d` (código morto), `c2f9757` |
| `zonas` | 60,3 % | **92,5 %** (433/468) | `d93b4ba` |
| `modelo` | — | **90,8 %** (187/206) | `54f4da0` (código morto), `1ebe9b7` |
| `texto` | 62,7 % | **86,7 %** (144/166) | `769f856` |
| `busca` | 62,6 % | **86,0 %** (258/300) | `53265d6` (código morto), `4b40635`, `06a34d4` |

No total, 2 098 de 2 275 (92,2 %). Os testes novos chamam o código como o usuário dele chama e
conferem o que ele vê (a página, o texto, o PGN, a área, a mensagem); custam milissegundos, e o
do pool do índice, que abre processos, vai na camada `processo`. O código apagado tinha a
prova de que nenhuma entrada o alcança (o `Estilo.conhecido`; o casamento vazio e o `ocioso`
da busca; o "a palavra é nova?" do plano e o glifo repetido sem posição da sessão).

Os sobreviventes que ficam são, em quase todos, equivalentes: o `frozen` e o `repr` de um campo
que ninguém compara, os valores padrão que quem chama sempre passa, os limiares de desempenho
(o corte das 250 000 células do alinhamento, o mínimo de 8 tarefas para o pool), as caches, as
constantes que só mudam uma ordem igual. Os que não têm teste honesto dependem de um caso que a
página não produz, ou de um dos defeitos abaixo. A lista de cada módulo está no relatório do
`mutador` (o JSON), e os motivos nos commits dos testes.

## Os defeitos que a mutação achou

Cada um com o teste vermelho antes da correção:

- `49bfb73`, `f9deb3f`: o PGN perdia o aviso do primeiro lance ilegal quando nenhum lance
  passava e o diagrama não estava conferido (o comentário da posição o sobrescrevia).
- `9c7c957`, `88e415e`: `texto.montar` levantava `IndexError` na página sem glifo lido, com um
  virtual e um diagrama (a linha só de virtuais não tem lugar na página).
- `d3786fd`, `522bb04`, `9c85d29` (A): apagar a letra antes (ou depois) do hífen de fim de linha
  junto com o hífen não juntava a palavra ("exe plo"): a junção apontava a letra que também saía.
- `6f425b9`, `0786121` (C): a palavra nova digitada no começo da segunda linha ia para a
  primeira: o alinhamento via a quebra impressa e a digitada como espaço.

**Fica, à espera de uma decisão (§13.8 da spec): B, o espaço digitado dentro de uma ligadura**
("afib" → "af ib", com o box "fi", deixa a página "a fib"). A correção mexe em cinco ou seis
lugares do plano da sessão, e o caso sem tinta para cortar pede escolher entre recusar a edição
e guardar a caixa perdendo o espaço. O rascunho do teste está pronto.

Também anotados, sem mudança: na rodada do `zonas`, a vírgula com o centro abaixo da linha de
base ganha uma área automática só dela numa linha sem letra de perna (a função e o texto não
mudam; é uma área a mais no editor).

## Q-E7: os privados do core

`tests/test_privados_do_core.py` (`888dbe5` vermelho, `3265d20`): o acesso a um `_nome` do
PyBoxEditor, achado pelo AST sem saber os tipos (pelo nome importado do core, ou por uma
variável da função criada por uma classe do core ou anotada com ela), tem de estar em
`EXCECOES`, com o pedido em `docs/pedidos-ao-pyboxeditor.md` e o teste de contrato em
`tests/test_contrato_do_core.py`; a lista não aceita nome velho. São nove acessos em quatro
pedidos: o ponto de partida e o passo do desfazer do tabuleiro (`TabuleiroEdicao._historico`,
`_indice`, `_estado`, `_registrar`), a tinta do box e o vale mais fundo (`BoxService.
_tinta_do_box`, `_vale_mais_fundo`), a rede e a base do serviço de aprendizado
(`LearningService._predictor`, `_get_learner`) e a leitura de uma lista de palavras
(`lexico._ler`). As regras copiadas do core (Q-E7, parte 2) não entraram: o CA é dos privados.

## Verificação final (no `3265d20`)

- `ferramentas/qualidade.py` (`docs/medidas/qualidade/2026-11-03-qualidade.json`): as duas
  camadas passam (a rápida com cobertura em 97 s, a `processo` em 260 s); cobertura 94,9 %
  (94,7 % no fim do Q8); 9 funções com CRAP ≥ 10, todas na lista com motivo; o dryer só com o
  par aceito.
- A rápida sem cobertura: 2241 passaram e 3 pularam em 55 s (-n 4).
- Portão `ABBY_PORTAO=1 pytest -m livro_real`, com o EPUBCheck, o Ace e o Calibre: **22 de 22
  passaram** (`docs/medidas/2026-11-03-medida.json`). O CA-7.1, que reprova desde a base, deu
  mediana 2271 ms, abaixo dos 2 400 do portão: não é correção; ele oscila em torno do limite
  (2412 no fim do Q8; a base, 2486–2692).

## Registro

| Ação | Por quê |
|---|---|
| Um mutador da casa, não o `cosmic-ray` | instalar um pacote é baixar, e pedia a permissão do usuário; e o mutador da casa roda por mutante só os testes da linha |
| Um módulo à mão (o `sequencia`) antes dos subagentes | o molde: os tipos de sobrevivente (a regra sem teste, a mensagem que ninguém conferia, o equivalente) |
| Os subagentes um de cada vez | uma carga pesada por vez; a mutação é a mais pesada da casa |
| Mutação com 2 trabalhadores, não 4 | a máquina travou duas vezes durante a mutação (01 e 02/11) |
| O defeito achado não era corrigido pelo subagente | ele parava e relatava; a correção veio em TDD, com o teste vermelho num commit à parte |
| A medida oficial dos oito no commit final | vários mudaram depois da própria medida (o PGN, o `montar`, a sessão) |
| O B esperando a decisão | a correção mexe no plano inteiro e o caso sem tinta é escolha de produto |
| Os `.contextos` fora do git | ~12 MB de cache, que a medida refaz |
