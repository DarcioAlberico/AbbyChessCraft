# Passo A2 — Espaço de trabalho (§3.1, §3.2, §3.4)

Ramo `passo-a2-espaco`, a partir da tag `passo-a1` (6e3464d).

## O que o passo fez

- **Os atalhos vêm do YAML** (`abbychess/app/teclado.py`, CA-3.7): cada ação de
  `docs/atalhos.yaml` vira uma `QAction` com o id (`objectName`), as sequências do perfil
  padrão e o contexto do escopo (`global` na janela; os de painel com
  `WidgetWithChildrenShortcut` nos widgets do escopo). Só as de `desde_passo` até o A2 têm
  tecla; os `QShortcut` soltos dos painéis saíram. No campo do caractere, onde a ligação
  nativa vence, Enter, Shift+Enter, Delete e as setas das bordas ficam com o campo e
  disparam a mesma ação (`AcoesDaTecla`; a exceção 6 de §3.4).
- **As teclas novas**: Alt+↓/↑ (a fila, em qualquer painel), F7 (o modo da fila), Ctrl+T
  (página verificada), Ctrl+M (marcar glifo), Shift+seta e Ctrl+Shift+seta (as bordas),
  Ctrl+Shift+I, F2 (a paleta), os arranjos (Ctrl+F6, Ctrl+F7, Ctrl+Shift+F7, Ctrl+F8), F9,
  Alt+1…5, Esc. O PgUp/PgDn do visor passou a ação.
- **O espaço** (`app/espaco.py`, um mixin como o desenho): o `QSplitter` da Imagem com a
  vista direita (Documento, Padrões); o Inspetor (`app/inspetor.py`: Glifo e Palavra, o
  seletor da fila num `QToolButton` e o contador); a gaveta de Páginas
  (`app/painel_paginas.py`, de `livro.json`); Resultados/Avisos
  (`app/painel_resultados.py`) com o log persistente (`abbychess/avisos.py`,
  `avisos.log`); a barra de status (página e estado, fila, zoom, lote com ✕, ⚠N); os
  arranjos e o foco; o espaço por projeto em `janela.json` (atômico); os menus Exibir e Ajuda.
- **A fila** (`ControladorDaFila`, §8.1): os modos confiança, ordem de leitura, palavras
  desconhecidas e diagramas por conferir; o escopo livro (Shift+F7) é do passo C.
- **Ctrl+T** (`ControladorDePagina.verificar`, §4.4): entra no desfazer e abre a próxima
  página não verificada.
- **Os menus de contexto pelo teclado**: o visor (o do box em revisão, ou o da vista) e
  Resultados/Avisos ganharam o menu que faltava; o Windows manda o Shift+F10 e a tecla Menu
  como `QContextMenuEvent` de teclado.
- `ferramentas/capturas.py`: as capturas para a revisão de design (offscreen, com as fontes
  do Windows).

## Decisões

| Decisão | Por quê |
|---|---|
| O espaço é um mixin da janela, não funções | as ações chamam `j.arranjar(...)`/`j.focar(...)` sem violar a regra das lambdas, e a regra do CA-14.1 vale nele |
| O campo do caractere aceita o `ShortcutOverride` das teclas do Glifo e as dispara | o `QLineEdit` venceria Enter, Delete e Shift+seta, e o atalho nunca chegaria; aceitar o override deixa um caminho só, sem disparo duplo |
| O Ctrl+T entra no desfazer | é uma mudança da página (o estado), e o Ctrl+Z dela não pode ficar sem efeito |
| A verificação de texto é um modo da fila | §8.1 lista "palavras desconhecidas" entre os modos; o F7 de antes (abrir a verificação) virou o F7 de ciclar o modo |
| O Inspetor não encolhe abaixo de 296 px | a tabela de §3.1; o Glifo foi apertado (margens, rótulos com a tecla na dica) para caber |
| A Linha (Ctrl+F5) e a cláusula dela no CA-3.2 ficam para o A3 | o YAML a põe no A3, com o Documento |

## Verificação

- Suíte rápida (624, 51–55 s), ruff limpo, camada `processo` (4).
- `tests/test_espaco.py`: CA-3.7 (os registrados são exatamente o YAML até o A2, sem
  `QShortcut`; atalho citado no README ou na SPEC existe no YAML), CA-3.3 (cada arranjo; o
  Alt+N põe o foco no painel certo; Alt+3 de novo cicla as abas), CA-3.2 (os tamanhos em
  1366; o empilhado em 1280; [livro_real] a x-height do gabarito na Imagem no zoom largura,
  ≥ 6 px em 1366×768 e 1280×720), CA-3.1 (reabrir restaura a página, o arranjo, o divisor
  ±2 px, as docas, o zoom, a aba e o painel com o foco), CA-4.2 (a falha de gravação em
  Avisos, no `avisos.log`; o espaço gravado é atômico: a troca que falha deixa o antigo
  inteiro), CA-8.2 (o Alt+↓ com o foco em cada painel anda e nunca muda texto; F7 cicla o
  modo e o editor), §4.4 (Ctrl+T, o desfazer dele, a edição devolve a em revisão), a
  exceção 6 (Delete e Shift+→ no campo), F2, Esc, Shift+F10/Menu em todo painel, a gaveta.

## Rodada 1 (código)

| Revisor | Notas | Veredito |
|---|---|---|
| Código e testes | Correção 6 · Simplicidade 7 · Testes 6 | volta |

| Achado | Correção |
|---|---|
| **M1** O Enter do teclado numérico deixou de ensinar no campo (o `KeypadModifier` virava "Num+Enter", que a tabela recusava) | `AcoesDaTecla` tira o modificador e trata o Enter como o Return; teste do Return, do Enter numérico e do Shift+Enter pelo teclado |
| **M2** Na ordem de leitura, decidir voltava ao primeiro pendente da página | o lugar do glifo decidido, por página; a fila segue dali; teste de corrigir e descartar |
| **M3** O Esc fechava Resultados antes da seleção, contra a §3.4 | a seleção primeiro; teste |
| **M4** Em 1920 a gaveta ficava com 226 px (o filtro a alargava) e o `resizeDocks` de uma doca recém-aberta era ignorado; o teste só olhava as constantes | o filtro pelo começo do texto; os tamanhos depois do layout, pela tabela de §3.1; testes com as larguras de verdade em 1366 e 1920 |
| m1–m8 | `janela.json` estragado vira aviso e não impede abrir; o projeto sem ele começa do padrão; o log de avisos troca de projeto ao abrir e fecha ao fechar; a gaveta atualiza no lugar; o sinal morto do treino; o menu da vista; o modo dos diagramas; o foco que mostra um painel muda o arranjo |
| Os testes | o registro contra o YAML lido à parte, com o contexto e os widgets do escopo (pega o mutante das ações sem widget); a citação no README só do que já vale, e a grafia ruim reprova; Alt+↓ em mais widgets e no modo das palavras |
| Achado nesta rodada | o Enter e o Ctrl+Enter da Palavra eram teclas fora do YAML: `corrigir_palavra` e `corrigir_e_ensinar_palavra`, desde o A2 |

## Rodada 2 (código)

Correção 9 · Simplicidade 8 · Testes 9 — **aceita**. A observação dela (o tipo
`redireciona` das exceções do Enter, que a legenda descrevia só como "o widget cede a
tecla") virou a legenda do YAML (`1da748e`).

## Medidas (commit `1da748e`, pasta limpa)

- Portão: 13 passaram; `docs/medidas/2026-10-16-passo-a2.json`.
- 3 rodadas (`repeticao-a2`): troca no cache, mediana 12,0–12,1 ms; fora do cache,
  130,1–133,6 (p95 144–146); Enter até a cor, mediana 21,1; 30,4; 21,3 e p95 24,2; 66,7;
  25,6 (uma rodada solta, com um pico de 286 ms; o portão, 21,5 e 25,9); com uma propagação
  lenta, p95 24,1; 42,4; 26,2; releitura, mediana 14,3–15,2; pintura, p95 11,8–13,3; memória
  com o lote, 1776–1780 MB (portão 1793); desfazer, 8,0 MB; atraso no lote, p99 9,1–22,1.
- Qualidade (`medir.py`, os três livros) e fatia (`--passo A2`, commit `cec156f`, que só
  acrescenta os JSON): iguais às do A1; o lote do xv, 452,6 s (A1: 445,5).
