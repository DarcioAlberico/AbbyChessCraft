# Passo G — Edição completa (§6.3, linhas G)

O passo foi feito em `passo-i-treino` (`683c686`). O fechamento foi feito em 2026-10-28,
no ramo `fechamento-c` (worktree `C:\Python-Chess2\AbbyChessCraft-fechamento`), sobre o código
de hoje e no escopo do passo G, revisado num worktree parado
(`C:\Python-Chess2\AbbyChessCraft-revisao`).

## O que o passo fez

- **k → 1 e 1 → k** na sessão do Documento (§6.3): duas letras viram uma ("rn" → "m" junta os
  boxes) e uma vira duas ("m" → "rn" divide o box pela tinta, ou faz uma caixa de duas letras
  quando a tinta não tem vão), no mesmo passo do desfazer; desde o fechamento, também junto
  com uma quebra ou junção de palavras na mesma edição ("rn b" → "mb").
- **O hífen de quebra**: apagar o hífen de fim de linha junta a palavra (o Documento mostra as
  linhas como impressas; a exportação sai "exemplo").
- **Ctrl+Shift+Enter** começa um parágrafo no começo da linha do cursor (de novo, tira), e
  **Ctrl+B/I/U** alternam negrito, itálico e sublinhado na seleção.
- **A prévia do Ctrl+H** habilita e aplica os casos estruturais.

## Revisões do fechamento

| Rodada | Revisor | Notas | Veredito |
|---|---|---|---|
| Código 1 | código e testes | Correção 4 · Simplicidade 6 · Testes 4 | volta |
| Produto 1 | produto, design e medição | Completude 4 · Fidelidade 5 · Clareza 5 · Produtividade 6 · Design 7 | volta |
| Código 2 | código e testes | 8 · 7 · 8 | volta (simplicidade) |
| Produto 2 | produto, design e medição | 8 · 8 · 8 · 8 · 8 | aceita |
| Código 3 | código e testes | 8 · 8 · 8 | aceita |

**Código 1**: o Ctrl+H estrutural falhava em toda página (a cópia da página guarda os boxes
numa tupla, e juntar ou dividir somava uma lista: TypeError, a página ficava de fora); o hífen
apagado não juntava a palavra e a exportação saía pior ("exem plo"); juntar ou dividir boxes e
mexer nas palavras na mesma edição abortava (a quebra e a junção usavam os gids aposentados);
o Ctrl+Shift+Enter no meio da linha abria o bloco no Documento e não na exportação.
**Produto 1**: os mesmos M1 e M2 vistos na janela (a caixa modal em inglês e termos de
Python); o README dizia que tudo isso era recusado; o parágrafo sem retorno e sem como tirar.
**Código 2**: o travessão solto no fim da linha virava junção; o parágrafo num virtual no
começo da linha dava ValueError; o parâmetro `fim_de_linha` e o ramo da recusa, mortos.

Os commits: `cfdfdd2` e `849ccde`.

## Decisões

| Decisão | Por quê |
|---|---|
| O parágrafo começa sempre no começo da linha | o Documento e a exportação partem por linha; uma linha não se divide em dois parágrafos |
| O hífen apagado vira uma junção entre as linhas, lida pela exportação | o Documento mostra as linhas do livro como impressas; juntar linhas no Documento é outra coisa |
| Na substituição, "m" → "rn" faz uma caixa de duas letras | a substituição não tem a imagem da página para dividir pela tinta |

## Verificação

- Suíte rápida no `1221a77`: 1750 testes aprovados e 3 pulados; ruff limpo. Dois testes de
  tempo (`test_lote.py::test_g1_…`, `test_janela.py::test_trocar_de_projeto_…`) falham às
  vezes na suíte em paralelo e passam sozinhos: instabilidade de tempo sob carga, fora do G.
- CA-6.4 nas linhas G e CA-6.6 ("cama" → "carna" com tinta, dois boxes e nenhum virtual) em
  `tests/test_sessao.py`, `test_editar_boxes.py`, `test_documento_edicao.py`,
  `test_substituir.py`; o hífen na exportação em `test_sessao.py`.

## Limitações conhecidas

- A substituição não divide pela tinta (caixa de duas letras).
- A divisão em que o core corta no eixo y não é recusada.
- A edição combinada com um espaço movido pode descartar o box e criar virtuais.
- Nada impede ensinar uma caixa de várias letras.
- A releitura (F5) troca o negrito e o itálico decididos pelo usuário pelos medidos (o
  sublinhado fica).
- O sublinhado fica só no Documento (a exportação leva negrito e itálico).
- O parágrafo novo aparece no Documento como um espaço um pouco maior entre as linhas.
