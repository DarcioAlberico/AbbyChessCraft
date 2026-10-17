# Passo A3 — Documento e sincronia (§6.1, §6.2)

Ramo `passo-a3-documento`, a partir da tag `passo-a2` (965b0fe).

## O que o passo fez

- **O Documento** (`abbychess/app/documento.py`, `VistaDoDocumento`): a página montada num
  `QTextDocument` a partir do documento derivado (`texto.montar`, agora com
  `com_os_nao_lidos` para a vista mostrar como □ os glifos que ninguém leu), no modo
  `impresso`. Uma linha impressa por parágrafo; título, margens (cabeçalho, rodapé, número de
  página, em cinza pequeno; Ctrl+Shift+H os oculta) e notas com formato próprio.
- **O mapa posição → gid** no `QTextBlockUserData` de cada parágrafo (o gid de cada
  caractere), não num formato por glifo. O documento anterior sai a cada montagem.
- **Os diagramas** no lugar deles: o desenho da posição lida (ou o recorte, se não lida), a
  linha do diagrama em monoespaçado, o estado e "Copiar FEN" (mouse e teclado).
- **O realce** (liga e desliga na barra do Documento): fundo laranja-claro no que vai para a
  revisão e no não lido, ondulado no desconhecido do léxico, pontilhado no virtual.
- **O corpo**: Ctrl++/−/0 com o foco no Documento mudam o corpo; na Imagem, o zoom.
- **Só leitura** até o D1.
- **A faixa Linha** (`abbychess/app/linha.py`, Ctrl+F5): a linha do glifo atual ampliada,
  a imagem em cima e o texto embaixo, glifo a glifo; 80 px, 96 em janelas altas.
- **A sincronia** (`app/espaco.py`): o clique numa palavra do Documento a contorna na Imagem
  (um item próprio, tracejado, que não apaga o da verificação) e leva o glifo ao Inspetor; o
  cursor andando contorna a palavra e mostra a Linha, e a Imagem rola só com Seguir; o clique
  na Imagem e a fila levam o cursor do Documento ao glifo e o mostram.
- **Sem perder o lugar** (CA-6.5): montar de novo devolve o cursor e a seleção aos mesmos
  glifos (gid e deslocamento) e a rolagem ao valor de antes.

## Decisões

| Decisão | Por quê |
|---|---|
| Uma linha impressa por parágrafo, sem refluir | refluir pede os parágrafos do layout (passo F); sem eles, o título e o corpo da mesma área se juntavam num parágrafo só (visto na captura) |
| Os glifos não lidos entram na vista como □ | o realce "aguardando leitura" e "sem leitura" de §6.1 é deles, e a Linha e o clique precisam deles; o texto e a exportação continuam só com os lidos |
| O contorno do cursor do Documento é outro item do visor | o da palavra em verificação continua o mesmo; os dois aparecem juntos |
| O estado "confiável pelos lances" fica para o H | depende da validação pelos lances, que é do passo H |
| A paleta (F2) não vale no Documento até o D1 | ela insere símbolos, e o Documento é só leitura; o teste do registro a declara |
| O CA-F.1 (gestos da fatia) continua pendente | o replay conta gestos contra as linhas com `texto_verificado`, e nenhuma está verificada ainda (é do usuário, `ferramentas/rotular.py`) |
| A x-height da Linha (CA-3.2, pendência do A2) | ≥ 12 px em 1366×768 e 1280×720, no índice 25 do livro de referência ([livro_real]) |

## Verificação

- Suíte rápida (671, 53 s depois de tirar o dicionário português dos testes do
  `lexico.txt`, onde ele não era o assunto), ruff limpo.
- `tests/test_documento.py`: o mapa (ida e volta, o caractere à direita do cursor, o espaço),
  montar de novo não deixa documentos vivos, as margens, o realce, o ondulado e o pontilhado,
  o corpo, só leitura, o diagrama com a linha, o estado e Copiar FEN; na janela, CA-6.1 (o
  contorno é o da palavra clicada), a Imagem e a fila levam o cursor, CA-6.5 (o cursor e a
  rolagem; a seleção), o cursor contorna a palavra certa e a Linha é a dela, o contorno da
  verificação fica, sem Seguir a Imagem não rola (com zoom de 4×), o clique no branco não
  escolhe, o último glifo de uma linha visual quebrada se acha, a Linha pela geometria,
  Ctrl+F5, o zoom do corpo, Ctrl+Shift+H; [livro_real] a x-height na Linha.
- [desempenho] o clique numa palavra do Documento (CA-6.1, `QTest.mouseClick`).

## Rodada 1 (código)

| Revisor | Notas | Veredito |
|---|---|---|
| Código e testes | Correção 6 · Simplicidade 8 · Testes 7 | volta |

| Achado | Correção |
|---|---|
| **1** Cada montagem deixava vivo o `QTextDocument` anterior, com as imagens dos diagramas | `deleteLater` do anterior, decidido antes do `setDocument` (que apaga o padrão do Qt) |
| **2** O teste dos formatos não via o vazamento | conta os `QTextDocument` vivos depois de 20 montagens; falha com a versão antiga |
| **3** O cursor do Documento apagava o contorno da palavra em verificação | um item próprio no visor; teste |
| **4** Sem Seguir, a Imagem rolava mesmo assim | o contorno não rola; só o Seguir; teste com zoom de 4× |
| 5–11 | o clique avisa uma vez e o desempenho mede o clique de verdade; o Documento mostra o glifo da Imagem e da fila sempre; a Linha pela geometria sem o mapa; o clique no branco; a seleção mantida; Copiar FEN pelo teclado; pequenas fragilidades |

## Rodada 2 (código)

Correção 9 · Simplicidade 8 · Testes 9 — **aceita**. O defeito menor que ela achou (o último
glifo de uma linha visual quebrada não se achava pelo clique) entrou junto (`b4fd450`), com
teste.

## Medidas (commit `f058c02`, pasta limpa)

- Portão: 16 passaram; `docs/medidas/2026-10-16-passo-a3.json`.
- 3 rodadas (`repeticao-a3`): o clique no Documento, mediana 10,1–10,5 ms e p95 20,3–23,0
  (alvo de 50); montar o Documento (`texto_da_pagina`), mediana 30,8–31,4 e p95 33,4–35,8
  (A2: ~22, o texto puro); troca no cache, mediana 14,2–14,4; fora do cache, 129,7–131,7;
  Enter até a cor, mediana 30,4; 21,1; 21,2 e p95 38,8; 27,1; 27,7 (a primeira rodada
  deslocada por igual, como no A1); com uma propagação lenta, p95 37,9; 28,6; 22,2;
  releitura, mediana 14,3–15,3; memória com o lote, 1805–1806 MB; atraso no lote, p99
  9,9–21,2.
- Qualidade (`medir.py`, os três livros, no `f058c02`) e fatia (`--passo A3`, no `63cce57`):
  iguais às do A2. O CA-F.1 continua "gestos pendentes": o texto do gabarito não está
  verificado.
