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
| A suíte rápida em paralelo (`-n auto`): ~32 s | §15.1 | `5612211` |
| A exportação lê a página pela `OrdemDeLeitura` do Documento | F, J | `8a991b2` |
| O teste do pool do índice (camada `processo`), quebrado desde o L | achado aqui | `13b3e91` |
| A pré-carga renderiza o PDF num processo à parte (a interface não para mais ~85 ms) | K | `be40bab`, `8388a7a` |
| Os processos do índice da busca morrem com o programa morto à força | achado aqui | `0c0918c` |
| Corrigir um caractere não refaz a ordem de leitura nem as linhas (validar, 13,6 → 2,8 ms) | H, pendência daqui | `ad255a8` |
| Manter as quebras na camada nativa devolve o hífen que o core tirou | J, pendência daqui | `12dd644` |
| O itálico no OCR, com uma régua do AbbyChessCraft | I | `ad808fa` |
| O EPUB conferido num leitor de verdade, o Calibre (`epub.calibre`) | J | `18af9f0` |

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
foi desfeito. Para chegar aos 60 s, o usuário deixou a escolha comigo: a suíte rápida roda em
paralelo, `pytest -q -n auto` (pytest-xdist 3.8.0, instalado no venv e declarado no
`pyproject.toml`): 32,3, 31,8 e 32,0 s em três rodadas, 12 núcleos, sem teste instável. Separar
os testes de janela tiraria da suíte rápida os que mais pegam regressão. As camadas de
desempenho e o portão continuam em série, porque medem tempo; o `-n auto` não entrou no
`addopts` por isso. Apagar as janelas mostrou um bug do programa: a troca de perfil de teclado caía no
ouvinte de uma janela já apagada ("Signal source has been deleted", que `teclado._apagado` não
reconhecia).

## A ordem de leitura da exportação

A exportação tinha a própria `_Leitura`, cópia da `layout.OrdemDeLeitura` do Documento menos no
mínimo de filas de texto por coluna (3 contra 6); o roadmap esperava a equivalência para
unificar. Em 160 páginas de 8 livros (20 espalhadas por livro, segmentadas sem OCR) as duas leem
igual em 157; nas 3 que divergem (Aagaard p. 242, Yusupov p. 150 e 202) o mínimo de 3 inventava
colunas que cortavam tabuleiros ou partiam uma página estreita de diagramas, e o de 6 as lê
como um trecho só. A exportação passou a usar a `OrdemDeLeitura` (`8a991b2`), sem mudança de
golden. O teste contou as peças dos tabuleiros como boxes; na exportação elas saem antes, o
que só reduz as divergências. Coluna curta de verdade (3 a 5 linhas) passa a ser lida como um
trecho só também na exportação, como já era no Documento.

## O render da pré-carga num processo

O fitz segura o GIL: cada página nunca vista que a pré-carga renderizava parava a interface
~85 ms. `abbychess/render.py` renderiza num processo à parte, pelo mesmo `PDFService` (os
mesmos pixels), e só a pré-carga o usa; a página pedida na hora renderiza aqui, que é mais
rápido. Pelo `CacheDePaginas`, 10 páginas nunca vistas do Xadrez Vitorioso, endireitadas, duas
rodadas: a maior parada da thread principal foi de 81–89 ms para 13–14 ms, e as paradas acima
de 20 ms de uma por página para nenhuma; cada pré-carga leva ~20–30 ms a mais (~500 ms com a
medida da inclinação). A revisão de código (`8388a7a`) pegou o que acontece quando o filho
trava: quem pede a página espera a pré-carga dele no máximo 1 s e renderiza aqui, o filho que
não responde é morto, o PDF trocado no mesmo lugar é lido de novo, e o filho fecha ocioso e
morre com o programa. Na suíte rápida ele fica desligado (`ABBY_RENDER_EM_PROCESSO=0`); nas
medidas, ligado, como no programa.

## Os processos órfãos do índice

Doze processos `spawn` parados desde a manhã, filhos de dois programas já mortos: os do
`PoolDoIndice`, seis por programa. No Windows, o `ProcessPoolExecutor` cujo pai morre sem o
`atexit` deixa os filhos vivos, e eles ainda prendem a saída de quem abriu o pai (dois perfis
em segundo plano não terminavam por isso). O vigia do pai do render (`render.vigiar_o_pai`)
virou o `initializer` do pool do índice (`0c0918c`); o teste da camada `processo` mata o
programa com `os._exit` e espera os filhos saírem.

## Corrigir um caractere

`texto.montar` leva 10–21 ms nas páginas da fatia, ~85% na ordem de leitura e nas linhas, que só
leem a geometria (conferido pela árvore das funções do core); das palavras, o core só lê o
caractere quando ele some na normalização (o box vazio ocupa espaço, mas não é símbolo) e nos
números que ele remonta. `_linhas_da_pagina` guarda as linhas das últimas 16 páginas pela caixa,
o ângulo e a moldura de cada glifo e só por esses caracteres (`ad255a8`). Validar a página pelos
lances depois de corrigir uma letra, 105 correções na fatia: 2,8 ms na mediana (13,6 sem as
linhas guardadas). O teste das trocas sorteadas não pegava a chave cega ao caractere (o
"mutante" passava); seis trocas da p. 21 que mudam as palavras do core a pegam.

## As quebras da camada nativa

O core tira o hífen da palavra partida quando o dicionário diz que era quebra (o `lex` de
`pdf_nativo.extrair`) e o hífen brando; ali a quebra não tinha onde voltar. Sem espaço nem hífen
no começo da linha, e com letra dos dois lados, ela volta com o hífen, como impressa
(`12dd644`). A exportação de hoje não passa o dicionário ao core, e o fitz entrega o hífen brando
como "-": o caso é raro, mas o teste o roda pela camada de verdade.

## O itálico

O passo I deixou o itálico esperando uma régua pública do core, que não existe e que o contrato
não deixa escrever lá. `pagina._italicos` mede aqui (`ad808fa`): por palavra, a inclinação mais
comum das bordas quase verticais das letras (Sobel, janela de ±25°) contra a das palavras retas
da página. Só as letras de pé contam, com 3 ou mais; itálico a 7° da referência, com o pico 2×
o da vertical.

O gabarito é o Odds & Ends, nascido digital: cada glifo segmentado da página renderizada ganha o
rótulo do glifo da camada que contém o centro dele (itálico pela bandeira ou pelo nome da fonte,
a regra do core). O primeiro desenho (o cisalhamento que concentra a tinta) marcava 6% das
palavras retas ("½–½", "¥g7", "you", "were"); a borda com a janela de ±35°, "Wijk aan Zee" (a
diagonal do Z). `ferramentas/medir_italico.py`, com a implementação final:

| Páginas | Retas | Falsos itálicos | Itálicas | Achadas |
|---|---|---|---|---|
| Do ajuste (36) | 6.294 | 0 | 394 | 95,9% |
| Fora do ajuste (60) | 11.647 | 0 | 433 | 95,8% |

Na fatia do Xadrez Vitorioso, que não tem itálico, 0 das 1.436 palavras medidas. ~105 ms por
página no lote (8,6 s). As perdidas são palavras sem haste ("over", "see") e a página quase toda
em itálico com poucas retas. Não há livro escaneado com itálico e gabarito: a revocação no
escaneado não foi medida. O falso itálico é o erro caro (o k-NN não compara amostras de efeitos
diferentes), e por isso os limiares ficaram do lado da precisão.

## O EPUB no Calibre

O Calibre 9.14 está na máquina. `epub.calibre` (`ABBY_CALIBRE`, o `ebook-convert`) converte o
EPUB em PDF pelo motor do leitor e acusa a conversão que falha, o aviso do Calibre e o link
interno do texto que não sai como link no PDF (`18af9f0`). Sem problema nenhum nos EPUB da
fatia (com e sem as quebras), das p. 1–12 do Odds & Ends (pela camada), dos golden do CA-12.1 e
do CA-12.3 e do teste dos links. Visto nas páginas: os diagramas, as figurinas e os símbolos
(⩲ ⩱ ∓ ⯹ ∞ ⇄), o negrito, e "Diagrama 1" e "capítulo 1" levando ao lugar certo. No Odds & Ends,
três coisas da camada do core, não do leitor: as três linhas grandes da capa ("July 2011
Newsletter", "By", "The QC Team") saem como três títulos; duas entradas do sumário saem num
parágrafo só; a tabela de símbolos sai com o símbolo depois da descrição. Thorium e leitor de
celular continuam por abrir.

## A revisão de código

Uma rodada, de um revisor independente sobre os seis primeiros commits: nada grave. As quatro
observações, corrigidas em `0888053`: manter as quebras na camada nativa não as devolvia
depois do hífen que o core guarda colado; "Diagrama 6.1" virava link para o 6, e o romano do
capítulo valia em minúsculas; `png_otimizado` podia tirar a gestão de cor; o teste da matriz
do cache não cobria o Enter nem a propagação.

A segunda rodada, de outro revisor independente sobre `0c0918c..18af9f0`: nada grave (conferiu
a chave das linhas contra o core, a conta dos índices do "-\n", os recortes do itálico e o pickle
da `PaginaLida` sem os itálicos). Das quatro observações menores, três corrigidas no
`epub.calibre`: o link sem texto, ou partido por `<br/>`, acusava em falso; "Diagrama 1" podia
gastar o link "Diagrama 12" (agora casa primeiro o de texto igual); o tempo estourado deixava os
filhos do `ebook-convert` vivos. A quarta fica: o `Estilo` tem duas pontas e não diz
"desconhecido", e o itálico medido com o negrito por medir grava `negrito=False`; é raro (o
itálico pede 3 letras, o negrito 2 glifos) e o k-NN só perde as amostras em negrito-itálico.

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

O segundo portão, no `8388a7a` (com a cache do texto, a ordem de leitura unificada e o render
em processo; `2026-10-23-passo-pendencias-151932.json`), também aprovou (27 testes): o Enter em
25,6 ms na mediana (41,4 no p95), o Enter com uma propagação lenta em 28,2 (35,2), a releitura
com o lote em 102,7 no p95 (dentro do alvo de 150), o lote em 8,6 s por página e o pico de
memória em 1998 MB. Abrir o projeto até o painel de Páginas teve uma rodada de 151 ms (as outras
nove, 28–55, como antes; alvo de 300), o p95 de 10 rodadas é a maior.

A qualidade do Xadrez Vitorioso (`medir.py --indices 0,7,20-26`,
`2026-10-23-qualidade-xv-100252.json`) é idêntica à do L em tudo, menos o tempo do lote da
medida (509 → 440 s).

O terceiro portão, no `a6555df` (esta rodada; `2026-10-23-passo-pendencias-181911.json`),
aprovou (27 testes). Contra o segundo:

| Medida | 2º portão | 3º portão |
|---|---|---|
| Texto da página, p50 / p95 | 36,9 / 42,1 | 17,5 / 22,5 |
| Releitura com o lote, p95 (alvo 150) | 102,7 | 72,6 |
| Montar o índice da busca, p50 | 1413 | 895 |
| Enter até a cor mudar, p50 / p95 | 25,6 / 41,4 | 28,6 / 58,0 |
| Lote com servidor, s por página | 8,6 | 9,0 |
| Troca de página, p50 | 15,4 | 17,2 |
| Clique no Documento, p50 | 3,8 | 4,6 |

O texto da página é o efeito das linhas guardadas. O índice da busca também, mas só no teste:
as 230 páginas dele são cópias das 7 da fatia, e a cache de cada processo acerta; num livro de
verdade ela não acerta ali. O resto subiu 5–15% junto, inclusive o que esta rodada não tocou (a
troca de página, o clique, o Enter que confirma a leitura, que não muda a chave das linhas): a
máquina estava mais lenta nesta rodada. O itálico custa ~0,1 s dos 9,0 s do lote. A qualidade do
Xadrez Vitorioso (`2026-10-23-qualidade-xv-180804.json`) é idêntica à de antes, menos o tempo
do lote da medida (440 → 455 s). O itálico, `2026-10-23-italico.json`, repete os números de
cima no `a6555df`.

## O texto verificado das p. 21–27

O usuário corrigiu e conferiu as 213 linhas de corpo de i020–i026 contra as faixas
(`7a824ec`, `rotulado_por: DarcioAlberico`; 149 diferiam da leitura). A estrutura (legenda,
corpo, título) e os FEN continuam sem revisão, e por isso as três medidas abaixo são
provisórias. Todas no `c9e5751`.

**CA-9.1, aprovado** (`ferramentas/medir_legendas.py`, nova, e `2026-10-23-legendas-xv.json`).
A ferramenta parte do snapshot da fatia e ensina os 17 glifos errados das legendas com o estilo
medido na página, como o Enter faz. Depois propaga os padrões nas sete páginas, como o F5 faz.

| | CER do corpo (9.870 glifos) | Glifos de corpo certos que erram | Errados que acertam | CER das legendas |
|---|---|---|---|---|
| Com o estilo (o critério) | 4,22% → 4,22% | 0 | 0 | 26,3% → 20,1% |
| Sem o estilo (informativo) | 4,22% → 4,14% | 0 | 8 | 26,3% → 20,4% |

Só 8 dos 17 glifos ensinados saíram medidos em negrito. Com o estilo, o padrão negrito não
alcança o corpo, que é reto. Nesta fatia, então, o filtro do efeito não evitou estrago nenhum,
porque sem ele também não houve estrago. Ele só barrou 8 acertos no corpo. O critério passa,
mas a medida não mostra o benefício que o filtro promete.

**CA-F.1, reprovado.** As duas medidas usam o mesmo snapshot, o catálogo versão 5 e os mesmos
gabaritos:
- a linha de base no código da tag `passo-0`, num worktree com os gabaritos e o catálogo
  copiados, como manda o protocolo: `2026-10-23-fatia-xv-passo-0.json`, 1.183 gestos;
- hoje, no `--passo L`: `2026-10-23-fatia-xv-passo-L-213554.json`, 1.093 gestos.

`replay_fatia.py comparar` dá razão 0,924, e o alvo era ≤ 0,70 depois do D1. A diferença
inteira são os 15 espaços: impossíveis no passo 0, hoje se corrigem no Documento
(`espaco_no_documento`), e o custo dos impossíveis cai de 310 para 190. O resto é igual nos
dois códigos:
- 205 `ensinar_glifo` e 12 `ensinar_da_fila`;
- 48 divisões, 11 junções, 15 descartes e 15 marcações;
- 5 linhas que a leitura não acha, que custam 170 caracteres.

Nenhum passo até o L barateou o comando de ensinar nem aumentou o que a propagação resolve
na fatia. O replay ensina cada caractere só uma vez, e por isso uma propagação melhor
apareceria no número de glifos ensinados.

A qualidade do Xadrez Vitorioso com o texto verificado (`2026-10-23-qualidade-xv-214359.json`)
dá CER do corpo de 3,23%, nas 213 linhas e com espaços (o `medir.py` conta por caractere). O
resto é igual ao de antes.

## Verificação

- Suíte rápida: 1553 passed, 2 skipped, em ~2 min no `2cbbdf6`; 1555 passed no `d29d399`, em
  ~102 s em série e ~32 s com `-n auto`; 1559 passed no `8388a7a`, ~39 s com `-n auto`;
  1581 passed, 3 skipped no `a6555df`, ~40 s.
- Camada `processo`: 32 passed no `8388a7a` (uma falhava desde o L, `13b3e91`); as de
  `tests/test_render.py`, com a dos órfãos do índice, no `0c0918c`.
- Calibre 9.14 (`ABBY_CALIBRE`): os testes dos links e os EPUB da fatia e do Odds & Ends, sem
  problema, no `a6555df`.
- `ruff check --select E,F --line-length 110 abbychess tests`: limpo.
- EPUBCheck 5.4.0 e Ace 1.4.6 (`ABBY_EPUBCHECK`, `ABBY_ACE`): aprovam o livro com os links novos
  e as quatro combinações do golden.

## O que continua pendente

Resolvido com o usuário:
- **CA-10.1** (passo H): a redação. "A precisão de 'confiável pelos lances' é 1,0 nos dois
  conjuntos" não passa nas perturbadas: a perturbação que nenhum lance do texto toca não muda
  nenhum lance, e nenhuma validação pelos lances a vê (no Xadrez Vitorioso, 73 de 100 saem
  confiáveis assim; das 23 afetadas, nenhuma). O `medir.py` já conta as duas: as confiáveis
  afetadas (erro da validação) e as não afetadas (fora do alcance dela). Com o sim do usuário, o
  SPEC passou a pedir a precisão 1,0 nos FEN do gabarito e, nas perturbadas, a detecção ≥ 60% das
  afetadas, com as não afetadas fora da conta. Pela medida de hoje, passa no Xadrez Vitorioso
  (23 de 23) e no Yusupov (16 de 17).

Medido com o texto verificado (seção acima):
- **CA-9.1** aprova, provisório até a estrutura ser revisada.
- **CA-F.1** reprova: 92,4% da linha de base, o alvo é ≤ 70%. Baixar o custo de ensinar e
  divisões e linhas não lidas é trabalho de leitura e de propagação. O que fazer com o alvo,
  ou com o passo que o fecharia, é do usuário.

Precisa do usuário:
- **Os FEN e a estrutura das p. 21–27** (os diagramas e as legendas revisados), para as
  medidas deixarem de ser provisórias.
- **Os leitores que não estão na máquina** (Thorium, celular); o Calibre já confere.

Decididos como estão:
- **A página pedida na hora renderiza na thread da interface** (~85 ms, mais a medida da
  inclinação na primeira visita). Pelo processo à parte ela sairia ~25 ms mais tarde, e a
  interface a espera de qualquer jeito; girar o laço de eventos nesse meio deixaria entrar
  tecla, clique e a resposta do lote no meio do `ir_para`. O alvo (trocar para página fora do
  cache, ≤ 600 ms) passa com folga.
- A medida da inclinação do grosso ao fino (K, espera gabarito); as metades do dividir herdando
  o estado da página e o diagrama aparado (L).
- O que a camada do core faz no Odds & Ends (os títulos da capa, o sumário, a tabela de
  símbolos): é do core, que o contrato não deixa editar.
