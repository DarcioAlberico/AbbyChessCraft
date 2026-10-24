# Passo L — Editor de imagem e páginas (§12.4)

O passo foi feito no ramo `passo-i-treino`, na pasta principal, depois do K (a partir de
`2c938d5`). O fechamento mediu na worktree irmã, no ramo `passo-l-fechamento`: a primeira
bateria em `976ee76` e a segunda em `071b8e5`.

## O que o passo fez

- **A sequência do livro** (`abbychess/sequencia.py`, sem Qt): a ordem das páginas em
  `projeto.json` (formato 3), com `pid` estável; cada entrada é a receita da imagem (a fonte,
  a página dela, o quadro, o giro, a metade, o ângulo à mão, o tamanho da fonte). Todo dado
  de página é chaveado por `pid`; a posição no livro é derivada. A migração da v2 (com
  `backup-v2/`) foi validada em cópias de dois projetos reais.
- **Mover, apagar, restaurar e inserir** (rodada 2): as apagadas ficam guardadas e voltam
  no lugar (pela âncora); as inseridas são copiadas para `inseridas/` (SHA-256).
- **Girar e cortar** (rodada 3a): a imagem é a fonte endireitada, depois o quadro, depois o
  giro, e os glifos seguem com conta inteira (`abbychess/geometria.py`); o JSON de página v3
  grava a geometria dos boxes, e a página é levada à da entrada na leitura; o que o corte
  deixa de fora fica guardado (`fora`, `areas_fora`) e volta.
- **Dividir** (rodada 3b): a direita ganha um `pid` novo e os glifos dela gids novos
  (`gids_movidos`, para as amostras acharem a origem); as páginas são trocadas inteiras com
  a sequência (`trocar_paginas`), e o Ctrl+Z junta e aposenta o `pid`.
- **Endireitar à mão** e **o PDF pesquisável das páginas transformadas** (rodada 4).
- **A janela**: o menu Página e a gaveta com todas as operações, girar à direita e à
  esquerda num gesto, os diálogos com a seleção (`3-7, 12`, `ímpares 15-200`…), o Ctrl+Z
  de cada operação.

## Decisões

| Decisão | Por quê |
|---|---|
| Endireitar antes do quadro e do giro | endireitar gira em volta do centro, que muda com o quadro; antes dele, cortar e girar são contas inteiras e o glifo passa de uma geometria a outra sem arredondar |
| Girar e cortar gravam a sequência primeiro; a página é levada na leitura | uma queda no meio não deixa boxes no quadro errado; o Ctrl+Z é a sequência de antes |
| Girar não regrava as páginas; cortar, sim (pelo gravador) | girar não tira glifo nenhum (as contagens e o texto ficam); o corte guarda glifos fora, e o `livro.json` e a busca precisam saber |
| Dividir e endireitar trocam as páginas inteiras | uma divisão preguiçosa poria os glifos da direita no `fora` da esquerda; o desfazer confere as páginas (pelo carimbo do arquivo que a operação gravou, e relendo só a que mudou) |
| Marcado à mão = leitura digitada ou aceita na revisão | o box não diz quem o desenhou; são esses que o usuário decidiu |
| Nada é medido nas operações (só o ângulo guardado) | medir é um render por página, na thread da interface: dividir o livro levava 104 s |
| Cortar e dividir por números (dívida declarada na §12.4) | marcar o retângulo e a linha sobre a imagem, com prévia, fica para depois |
| Girar sem tecla padrão, atribuível no perfil | Ctrl+Shift+< e > dependem do teclado (ABNT2) |

## Revisões

| Rodada | Revisor | Notas | Veredito |
|---|---|---|---|
| Código 1 | código e testes | Correção 7 · Simplicidade 7 · Testes 8 | volta |
| Produto 1 | produto, design e medição | Completude 7 · Fidelidade 6 · Clareza 7 · Produtividade 5 · Design 7 | volta |
| Código 2 | código e testes | 9 · 8 · 9 | aceita |
| Produto 2 | produto, design e medição | 8 · 8 · 7 · 8 · 8 | volta |
| Produto 3 | produto, design e medição | 8 · 8 · 8 · 8 · 8 | aceita |
| Código 3 (as mudanças de desempenho) | código e testes | 8 · 8 · 8 | aceita |

**Código 1**: desfazer o giro de uma página lida depois dele desalinhava os boxes (o ângulo
medido de novo); dividir media cada página na thread da interface; voltar o `backup-v2/`
depois de inserir mostrava a página errada (a inserida gravava um `indice` de página do PDF).
**Produto 1**: dividir o livro prendia a janela 108 s; o endireitar começava num ângulo fixo
que valeria para todas as páginas escolhidas; girar sem gesto único nem gaveta; a seleção
sem paridade num intervalo; os textos ("(s)", "Cancel", o infinitivo); as capturas
mostravam o Documento antes de ele se redesenhar.
**Produto 2**: o endireitar anunciava "desfazer a leitura" num OK que não fazia nada.
**Código 3**: girar sem regravar deixava o índice da busca ler a página fora da memória na
geometria de antes (e, depois de reordenar, pela página do PDF, e não pela posição): o
índice passou a levar a página à geometria e à posição de agora.
A prova de desempenho nova (`tests/desempenho/test_paginas.py`) corrigiu um número que a
revisão de produto tinha aceitado: os "~3 s" de dividir o livro eram de uma sonda com 60
glifos por página; com os ~1.500 da fatia, 11,6 s, e depois das correções 7,7 s (antes de
ler, 0,13 s). A revisão de produto confirmou o veredito com o número certo.

## Verificação

- Suíte rápida: 1521 testes aprovados e 2 pulados; suíte do core: 3586; ruff limpo nos dois; `ferramentas/capturas_paginas.py` (o menu, os
  diálogos e a janela depois de cada operação, nos dois temas).
- CA-12.7 a 12.16 e CA-4.6 em `tests/test_sequencia*.py`, `test_migracao_v3.py`,
  `test_operacoes_de_pagina.py`, `test_girar_e_cortar.py`, `test_dividir.py`,
  `test_endireitar_a_mao.py`, `test_exportar_pela_sequencia.py`, `test_paginas_na_janela.py`
  e `test_fechamento_l.py`.

## O que o portão pegou

A primeira bateria (commit `976ee76`) reprovou num só teste, o CA-7.1 pela janela (do abrir
o projeto ao índice da busca pronto, com o servidor): mediana de 2.434 ms, contra 2.400 ms
(o alvo de 2 s × 1,2). Nas três repetições deu 2.483, 2.386 e 2.408 ms. No passo D2 dava
1.812 ms. Os portões do F ao K não rodaram esse teste, então ele não apareceu antes.

A causa não é do passo L. Medido no mesmo arquivo de 230 páginas, num pool de 6 processos:

| Código | Montar o índice (mediana) |
|---|---|
| D2 (`6a6564a`) | 1,30 s |
| K (`2c938d5`), antes do L | 1,74 s |
| L (`976ee76`) | 1,78 s |
| L com o core de antes de 17/10 | 1,74 s |
| L com a correção | 1,35 s |

A regressão veio do passo F (`a47d7a7`, "ordenar colunas no Documento"). `texto.montar`
passou a detectar as colunas da página (`OrdemDeLeitura`), e depois o core detectava as
mesmas colunas de novo, ao ordenar o trecho. Numa página de uma coluna só, o trecho é a
página inteira e as duas detecções dão o mesmo resultado. A detecção é a parte mais cara de
montar o texto (~22 ms numa página de 1.500 glifos), e o índice monta o texto de todas as
páginas.

A correção:
- O core (PyBoxEditor `master`) ganhou `BoxService.detectar_colunas_e_transversais` e um
  `deteccao=` opcional em `sort_boxes_reading_order` e `palavras_da_pagina`. Sem esse
  parâmetro, tudo funciona como antes.
- O `OrdemDeLeitura` e o `exportar._Leitura` guardam a detecção e a repassam ao core quando
  o trecho é a página inteira.
- O teste novo (`test_a_pagina_de_uma_coluna_detecta_as_colunas_uma_vez`) confere uma
  detecção por página, e que o texto sai igual ao da detecção refeita, no Documento e na
  exportação.

Os JSON da primeira bateria estão em `d35ac37`. Os `-falhou` continuam na árvore; os que a
segunda bateria substituiu saíram em `071b8e5`.

## As medidas (commit `071b8e5`, worktree limpa)

O portão (`ABBY_PORTAO=1`, `livro_real or desempenho`) teve 27 testes aprovados. As três
repetições (`repeticao-l`) também aprovaram. Arquivos: `2026-10-23-passo-l.json`,
`2026-10-23-repeticao-l*.json`, a qualidade dos três livros e a fatia
`2026-10-23-fatia-xv-passo-L.json`. As tabelas do README foram regeneradas pelo
`ferramentas/resumo_medidas.py`.

As operações de página, num livro de 230 páginas com ~1.500 glifos cada, no portão e nas três
repetições:

| Operação | Medido | Antes do fechamento |
|---|---|---|
| Dividir o livro lido | 7,6 s a 7,7 s | 11,6 s |
| O Ctrl+Z da divisão | 2,3 s a 2,7 s | 13,9 s |
| Dividir antes de ler (231 p.) | 0,13 s | — |
| Girar o livro lido | 0,33 s a 0,34 s | 5,5 s |
| Girar uma página, p95 | 14 ms a 16 ms | — |
| Abrir ao painel de Páginas, p95 | 55 ms (alvo 300) | — |

O índice da busca pela janela, em mediana, foi de 2.042 ms no portão e de 1.970, 1.951 e
2.013 ms nas repetições (limite de 2.400 ms). Montar o índice no pool deu p95 de 1.423 ms (alvo
de 2.000 ms).

A qualidade (`medir.py`) nos três livros saiu igual nas duas baterias, e a fatia também.
Comparada com a do D2:

- **xv:** 7/7 FEN iguais à leitura. O lado a jogar provisório subiu de 1/5 para 2/5, e as
  perdidas caíram de 3 (+10 nas negativas) para 3 (+9). A precisão das margens corridas caiu de
  0,875 para 0,5, e os glifos sem par nas negativas subiram de 833 para 938. Essas diferenças
  vêm de antes do L: medido agora no K (`2c938d5`), o xv dá os mesmos números, e só o tempo do
  lote muda (538 s no K, 509 s no L). A correção das colunas também não os mudou: as duas
  baterias dão os mesmos números.
- **yusupov:** 3/3 FEN; as perdidas caíram de 13 para 5.
- **darcy:** 2/3 FEN, como antes.

**O que piorou desde o D2, e de onde vem.** Do E ao K, nenhum passo rodou o portão. O README
compara, portanto, o L com o D2:

| Medida | D2 | L |
|---|---|---|
| Lote, por página | 8,7 s | 17,2 s |
| Enter, p95 | 32 ms | 54 ms |
| Clique no Documento, p95 | 3,4 ms | 11,3 ms |
| Gravar uma página do lote, p95 | 22 ms | 32 ms |
| Releitura com o lote, p95 | 111 ms | 169 ms |
| Memória com o lote | 2.468 MB | 2.752 MB |

Para separar o L do resto, medi os mesmos módulos no K (`2c938d5`) e no L (`d78db62`), na mesma
hora:

| Medida | K | L |
|---|---|---|
| Lote com servidor, por página | 17,08 s | 17,02 s |
| Lote sem servidor, por página | 17,13 s | 17,17 s |
| Gravar uma página do lote, p95 | 43 ms | 31 ms |
| Releitura com o lote, p95 | 133 ms | 151 ms |
| Memória com o lote, pico | 1.657 MB | 1.689 MB |
| Enter (ensinar), p95 | 56 ms | 53 ms |
| Clique no Documento, p95 | 16,6 ms | 14,9 ms |
| Texto da página, p95 | 50 ms | 39 ms |

As pioras vêm de antes do L. A releitura com o lote varia de uma rodada para outra: 133 ms a
169 ms nas mesmas condições. Achar o passo que dobrou o lote (do E ao K) fica como pendência
fora deste passo.

## Limitações conhecidas

- Cortar e dividir são por números (sem marcar sobre a imagem).
- Dividir o livro já lido roda na thread da interface (uns segundos, com o cursor de espera e
  a janela desligada); dividir antes de ler é instantâneo.
- `ProjetoDeLivro` passou de 1.900 linhas: a migração e a recuperação da sequência caberiam
  num módulo próprio.
- As duas metades herdam o estado da página; o diagrama que passa da divisão vai aparado com
  a leitura de antes.
- Se uma página do PDF exportado vira imagem, o sumário e os rótulos do original não vêm.
- A origem numa página apagada só avisa (restaurar é por Páginas apagadas…).
- Num livro de duas colunas, cada coluna ainda passa pela detecção do core outra vez. Só a
  página de uma coluna reaproveita a detecção.
- O lote leva 17 s por página, o dobro do D2, e o Enter e o clique no Documento também ficaram
  mais lentos. Essas pioras são de algum passo entre o E e o K.
