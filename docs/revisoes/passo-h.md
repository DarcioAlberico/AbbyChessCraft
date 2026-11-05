# Passo H — Diagramas (§10)

O passo foi feito em `passo-i-treino` (`8d65660`, `85dfac5`; nas pendências, `cf151d1`, o roque
desmarcado na conferência, e o CA-10.1 com a redação nova aprovada pelo usuário). O fechamento
foi feito em 2026-10-28, no ramo `fechamento-c` (worktree
`C:\Python-Chess2\AbbyChessCraft-fechamento`), sobre o código de hoje e no escopo do passo H,
revisado num worktree parado (`C:\Python-Chess2\AbbyChessCraft-revisao`).

## O que o passo fez

- **A validação pelos lances** (`abbychess/lances.py`): a primeira linha de lances depois de
  cada diagrama, nas letras do idioma e nas figurinas, jogada no FEN lido com python-chess;
  "confiável pelos lances", o aviso do lance ilegal e o lado a jogar pelo número do lance.
- **O roque inferido** só para validar, com o "Usar" na conferência (CA-10.3), e o **PGN por
  diagrama**.
- **O editor Diagrama no Inspetor**: a Imagem enquadra o impresso, Ctrl+Enter confere e vai ao
  próximo, PgUp/PgDn pelos diagramas do livro, F8, Ctrl+Z nas casas.
- **A aba Diagramas**: a grade com o recorte, a posição desenhada e o estado, e os filtros.
- **O CA-10.1** em `ferramentas/medir.py`, com as perturbações em `abbychess/perturbacoes.py`.

## Revisões do fechamento

| Rodada | Revisor | Notas | Veredito |
|---|---|---|---|
| Código 1 | código e testes | Correção 6 · Simplicidade 7 · Testes 7 | volta |
| Produto 1 | produto, design e medição | Completude 6 · Fidelidade 7 · Clareza 5 · Produtividade 6 · Design 4 | volta |
| Código 2 | código e testes | 8 · 7 · 8 | volta (simplicidade) |
| Produto 2 | produto, design e medição | 8 · 7 · 8 · 8 · 8 | volta (fidelidade) |
| Código 3 | código e testes | 8 · 8 · 8 | aceita |
| Produto 3 | produto, design e medição | 8 · 8 · 8 · 8 · 8 | aceita |

**Código 1**: conferir sem tocar no lado apagava o lado que só o número do lance dava (o FEN
ficava "w" assumido e discordava do PGN); o roque marcado e depois invalidado por uma casa
corrigida ia ao FEN (inválido, o diagrama caía do PGN); o Ctrl+Enter chegava a um diagrama não
lido e o deixava conferir um tabuleiro vazio.
**Produto 1**: o mesmo lado apagado, visto na p. 25 (um dos dois lados certos do 2/5); o editor
não cabia no Inspetor (338 px contra 296, a coluna h e os botões cortados); a casa de 30 px
(o §3.2 pede 32); o lado a jogar abaixo da dobra e o lado assumido invisível na aba.
**Código 2**: `lances.py` misturava a medida (as perturbações) com o que o programa usa; o
aviso de "brancas assumidas" do core com o lado dos lances; PgUp/PgDn no não lido; o filtro
sem o conferido sem lado.
**Produto 2**: o roadmap ainda dava o CA-10.1 como pendente; o "lado certo" não dizia que os
errados eram lado não dito; o que o CA-10.1 mede (os lances do gabarito, não o extrator).
**Produto 3** (aceita): o editor ainda cortava ~8 px com a Segoe UI 9 (o teste media com a
fonte de reserva) e os botões ↶ ↷ eram pequenos demais; corrigidos junto com este registro.

Os commits: `55e5e65`, `1221a77`, `28760a1` e o deste registro.

## Decisões

| Decisão | Por quê |
|---|---|
| O lado dos lances vale também no conferido, quando ninguém disse o lado | conferir sem tocar no lado não é dizer "brancas" |
| O roque conferido é filtrado pelo que rei e torre ainda permitem | uma casa corrigida depois de marcar o roque o torna impossível |
| A medida do CA-10.1 joga os lances rotulados no gabarito | mede a validação; o extrator da linha do OCR tem a sua própria fraqueza (a linha hipotética da prosa) |
| As perturbações num módulo à parte | o que só a medida usa não pesa no que o programa carrega |

## Verificação

- Suíte rápida no commit deste registro: 1752 testes aprovados e 3 pulados; ruff limpo.
- CA-10.1 (`validacao_pelos_lances`: 23 de 23 afetadas detectadas no Xadrez Vitorioso, 16 de 17
  no Yusupov, 9 de 9 no Darcy Lima), CA-10.2 e CA-10.3 em `tests/test_lances.py`,
  `tests/test_janela_diagramas.py`; o CA-3.2 (a casa de 32 px e o editor ≤ 270 px com a Segoe
  UI 9) em `test_janela_diagramas.py`.

## Limitações conhecidas

- ~~O extrator da linha perde o lance com sinal colado (`±`, `+-`, `†`) ou o roque com traço en.~~
  Corrigido em 2026-11-05. A linha hipotética da prosa ainda pode virar a principal: ignorar o que
  vem entre parênteses antes da linha foi medido e piorou (o ")" que o OCR perde esconde a linha
  toda; 45 lances confiáveis sumiram numa página do Aagaard).
- ~~O `e.p.` como primeiro lance é recusado.~~ Corrigido em 2026-11-05.
- O editor mostra a validação com as linhas de quando abriu (corrigir o texto com ele aberto
  não atualiza o aviso até reabrir).
- A aba Diagramas não se atualiza com edições da página (o botão Atualizar a refaz) e guarda a
  posição da página, não o `pid`.
- O aviso do lance ilegal aparece em texto corrido, entre os outros; no tema escuro, os rádios
  desmarcados do lado quase não se veem.
