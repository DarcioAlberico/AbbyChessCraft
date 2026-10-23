# Pendências dos passos (2026-10-23, ramo `pendencias`)

Depois do fechamento do L, o que os passos deixaram pendente e dava para fazer sem o usuário,
sem editar o core e sem gabarito novo. Ramo `pendencias`, a partir da tag `passo-l`.

## O que foi feito

| Pendência | De onde | Commit |
|---|---|---|
| O lote voltou de 17,2 para 8,5 s por página: o negrito converte a página para cinza uma vez | regressão do I (`2bbf0e7`), achada no fechamento do L | `a9fa43e` |
| Desmarcar todos os roques na conferência não volta ao inferido (`roque_informado`) | revisão do H | `cf151d1` |
| O clique no Documento e o Enter recortam da matriz do cache | regressão do C (`43a037f`) | `b949f2a` |
| Links para "Diagrama N" e "capítulo N" no EPUB e no DOCX | J | `150d5de` |
| Manter quebras de linha e hífens; realçar a baixa confiança no DOCX; o golden do CA-12.1 e o `opcoes.yaml` do CA-12.3 | J, §12.1 | `7e97083` |
| Aspas curvas (PD-07) e o PNG otimizado sem perda | J | `3d7d66c` |
| A suíte rápida de 314 para 119 s; a troca de perfil de teclado com uma janela já apagada | achado aqui | `9b365df` |
| As quatro observações da revisão de código | revisão | `0888053` |
| O aviso de uma thread depois que a janela fechou | achado no portão | `a925137` |
| A validação pelos lances guarda o texto depois dos diagramas (o Enter, 38,8 → ~25 ms) | custo do H, achado aqui | `9c98367` |
| Os ícones rasterizados uma vez por tema (abrir a janela, 78 → 36 ms; a suíte, ~118 → ~102 s) | achado aqui | `e671d7c` |

## A bissecção do lote

`ler_pagina` sem servidor, xv pp. 21–23, sempre com o core de hoje:

| Commit | s por página |
|---|---|
| D2 (`6a6564a`) | 9,43 |
| `6796117` (fim do C) | 9,32 |
| `edbb2e2`, `a728553`, `e02df42`, `7c9caed` | 8,97–8,99 |
| **`2bbf0e7`** (passo I, negrito no treino) | **21,01** |
| `a47d7a7` (F), `683c686` (G), K `2c938d5` | 20,26–21,36 |
| `passo-l` (`1d5d032`) | 20,73 |
| `a9fa43e` (a correção) | 9,78 |

No perfil do `2bbf0e7`, `efeitos_de_impressao` levava 9,8 dos 17,8 s de `ler_pagina`, 8,9 deles
em `recorte`, que convertia a página PIL inteira para cada um dos ~1.300 glifos; a medida do
negrito em si, 0,3 s. A Galeria recortava do mesmo jeito, numa thread.

## O clique e o Enter

O perfil na janela (offscreen, xv pp. 20–22, sob o cProfile) mostrou o mesmo padrão no aviso de
ensino do passo C (`aviso_de_ensino`): ~7 ms a cada glifo mostrado, para converter a página de
novo; o Enter pagava o mesmo em `pg.ensinar`. O que mais pesava no Enter, porém, era a
validação pelos lances do passo H, refeita em `_mudou`: ela montava o texto da página inteira
(~25 ms fora do perfil). Não dá para pular a validação olhando só os glifos que mudaram: o
lugar do diagrama no Documento depende de a linha anterior terminar a frase, e a divisão em
palavras depende dos caracteres. O que dá é guardar o texto depois dos diagramas pela chave do
que `texto.montar` usa (o caractere, a caixa e o ângulo de cada glifo, as áreas, as decisões e
os diagramas), sem a confiança e a fonte: o Enter que confirma a leitura, o mais comum, não
muda a chave (`9c98367`). Três rodadas de `test_enter_ensinar` no `9c98367`: 24,2, 26,5 e 24,9
ms na mediana, 39,7 a 42,5 no p95 (`2026-10-23-enter-pendencias-parcial*.json`; no D2, 32,2 no
p95).

## A suíte rápida

Levava 314 s (limite de 60, §15.1). Os testes do tema levavam ~15 s cada na chamada e na
desmontagem, e 3 s sozinhos: as janelas fechadas dos módulos anteriores continuavam vivas no
Qt, e cada troca da folha de estilo refazia o estilo de todas. Uma fixture do conftest as apaga
no fim de cada módulo: 119 s. Depois, abrir uma janela caiu de 78 para 36 ms com os ícones
rasterizados uma vez por tema (`e671d7c`): ~102 s. Ainda passa do limite, e o que sobra está
espalhado por 1.555 testes (36 s de preparação, 50 de chamada, 10 de desmontagem; o mais lento,
3 s; as esperas com `sleep`, as travas do gravador, os `fsync`). No D1 eram 56–60 s com bem
menos testes. Baixar o passo da espera mais usada (`_esperar`, de 10 para 2 ms) ganhou 1,5 s e
foi desfeito. Chegar aos 60 s pede uma decisão: separar os testes de janela num marcador
próprio, ou rodar em paralelo (`pytest-xdist`, uma dependência nova). Apagar as janelas mostrou um bug do programa: a troca de perfil de teclado caía no
ouvinte de uma janela já apagada ("Signal source has been deleted", que `teclado._apagado` não
reconhecia).

## A revisão de código

Uma rodada, de um revisor independente sobre os seis primeiros commits: nada grave. As quatro
observações, corrigidas em `0888053`: manter as quebras na camada nativa não as devolvia
depois do hífen que o core guarda colado; "Diagrama 6.1" virava link para o 6, e o romano do
capítulo valia em minúsculas; `png_otimizado` podia tirar a gestão de cor; o teste da matriz
do cache não cobria o Enter nem a propagação.

## As medidas

O portão (`ABBY_PORTAO=1 -m "livro_real or desempenho"`, rótulo `passo-pendencias`) no
`0888053` aprovou: 27 testes, nenhuma falha, `docs/medidas/2026-10-23-passo-pendencias.json`.
Contra o portão do L (`071b8e5`):

| Medida | L | Pendências |
|---|---|---|
| Lote com servidor, s por página | 17,2 | 8,5 |
| Lote sem servidor, s por página | 17,4 | 8,52 |
| Memória com o lote, pico (MB) | 2752 | 1994 |
| Enter até a cor mudar, p50 / p95 | 45,8 / 54,0 | 38,8 / 42,0 |
| Clique no Documento, p50 / p95 | 10,6 / 11,3 | 3,7 / 4,4 |
| Releitura com o lote, p95 (alvo 150) | 169,1 | 206,1 |
| Índice pela janela, mediana | 2042 | 2056 |

O lote volta ao D2 (8,71) e o clique quase volta (3,43). A releitura com o lote saiu alta no
portão, com um máximo de 594 ms. Três repetições isoladas da mesma medida, no mesmo commit
(`2026-10-23-releitura-pendencias-parcial*.json`), deram 152,7, 100,8 e 107,6 ms no p95; no L,
o portão e as repetições deram de 106 a 169. É a mesma faixa, com uma rodada alta; com o lote
duas vezes mais rápido, o servidor lê mais páginas por segundo e a releitura disputa mais.
Passa do alvo de 150 numa parte das rodadas, como já passava no L.

A qualidade do Xadrez Vitorioso (`medir.py --indices 0,7,20-26`,
`2026-10-23-qualidade-xv-100252.json`) é idêntica à do L em tudo, menos o tempo do lote da
medida (509 → 440 s).

## Verificação

- Suíte rápida: 1553 passed, 2 skipped, em ~2 min no `2cbbdf6`; 1555 passed no `e671d7c`, em
  ~100 s.
- `ruff check --select E,F --line-length 110 abbychess tests`: limpo.
- EPUBCheck 5.4.0 e Ace 1.4.6 (`ABBY_EPUBCHECK`, `ABBY_ACE`): aprovam o livro com os links novos
  e as quatro combinações do golden.

## O que continua pendente

Precisa do usuário:
- **CA-10.1** (passo H): a redação do critério (a precisão "nas perturbadas" só é atingível
  lida sobre as afetadas).
- **O itálico no OCR** (passo I): espera uma régua pública do core, e o contrato não deixa
  editar o core.
- **CA-9.1 e CA-F.1**: o texto e os FEN das p. 21–27 do Xadrez Vitorioso verificados.
- **Os testes em leitores de verdade** (Calibre, Thorium, móvel) do EPUB (passo J).

Trabalho grande, para um passo próprio:
- **O render do fitz fora da interface** (passo K): segura o GIL ~80 ms por página nunca vista;
  pede um processo, como o servidor de leitura.
- **Unificar a montagem das linhas da exportação com a `OrdemDeLeitura`** do Documento (passos F
  e J), quando a caracterização mostrar a equivalência.
- **A suíte rápida abaixo de 60 s**: ~102 s hoje, sem um culpado só; pede separar os testes de
  janela ou rodar em paralelo.
- **Corrigir um caractere ainda monta o texto da página** para a validação pelos lances
  (~25 ms); só confirmar a leitura deixou de montar.

Decididos como estão: a medida da inclinação do grosso ao fino (K, espera gabarito); as metades
do dividir herdando o estado da página e o diagrama aparado (L).
