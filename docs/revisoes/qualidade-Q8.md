# Passo Q8 — CRAP abaixo de 10 (em andamento, ramo `qualidade-q8`)

Nono passo de `plans/roadmap-qualidade.md`, a partir do `9c1f644` (o Q7 mesclado no
`passo-i-treino`), na worktree irmã `C:\Python-Chess2\AbbyChessCraft-qualidade`. Na medida do
`9bb04dd`, 281 funções passavam de CRAP 10: 252 com cc ≥ 10 (só partindo) e 29 com cc < 10 e
pouca cobertura (só testando).

## A alavanca (CA-Q-X1)

| Commit | O que mudou |
|---|---|
| `8bc0def` o teste (vermelho); `70871f8` o crapper | `ferramentas/crapper.py --aceitos`, no molde do dryer: sai 1 com função ≥ 10 fora da lista ("novo") e com função da lista que não passa mais de 10 ("sumiu"); `qualidade.py` o chama com `ferramentas/crap_aceitos.txt` e falha com qualquer uma das duas listas fora do lugar. A lista começou com as 281, todas "a reduzir (Q8)" |
| `038b4ae` | `tests/test_complexidade.py`, na rápida: toda função com cc ≥ 10 (pelo AST, sem cobertura) está na lista, a lista não cita função que não existe, cada linha tem motivo, e o `TETO` só desce |

O passo fecha quando nenhuma linha diz "a reduzir (Q8)".

## Rodadas

| Rodada | Commits | O que mudou | Lista |
|---|---|---|---|
| 1. As de cc < 10 (testar) | `a3a96bd` à mão (o molde); `a970061`, `601e16c`, `5d675bb`, `388766f`, `c55c7e4`, `da7f6e0`, `0179591` por um subagente, revisado aqui | testes de comportamento para 26 das 29 (o mouse, o botão direito, as teclas, os diálogos de verdade; o PDF com texto da camada; o lote retomado; o palpite com o veto de proporção): todas abaixo de 10 com os testes do arquivo. Três ficam com motivo: `estilo.tema_do_sistema` (o offscreen da suíte sempre responde `Unknown`), `principal.main` (o ponto de entrada fica no `app.exec()`), `epub.ace` (o validador externo só roda no portão) | 281 → 255 |

Também, achado na rodada 1: `8ff1c29` (vermelho) e `c25cbd0` (CA-Q-T5) — a regra dos imports
entre testes só via `from tests.test_x import`; seis arquivos ainda pegavam fixtures ou nomes de
outro teste por `from tests import test_x` ou `import tests.test_x`.

Verificação: a rápida inteira no `0179591`, 1987 passaram e 3 pularam em 83 s (-n 4; eram
75 s: os ~45 testes novos de widget). O teto é 90 s: as próximas rodadas partem funções e quase
não acrescentam testes, mas a folga é pequena.

## O que falta

As 252 de cc ≥ 10 ("a reduzir (Q8)"): partir, com a suíte como pino (refatoração, sem mudar
comportamento no mesmo commit); as de cobertura < 50 % primeiro ganham o teste. Os `match` e as
cadeias de `if` de despacho só se partem se a tabela ficar mais clara (§8); senão ficam com
motivo. Também Q-T3 (os testes que montam estado privado) e Q-T6 (as propriedades que faltam).

## Registro

| Ação | Por quê |
|---|---|
| A lista de aceitos antes de reduzir qualquer função | o CA-Q-X1 pede a lista e a catraca; sem ela, nada impede uma função nova acima de 10 enquanto o passo anda |
| A parte de cc ≥ 10 na rápida, a de cobertura só na medida | cc ≥ 10 passa de 10 mesmo toda coberta, e o AST basta; a cobertura combinada leva ~6 min |
| A lista nomeia `arquivo Classe.funcao`, sem a linha | a linha muda a cada corte; o nome qualificado não |
| Uma função à mão (`camada.palavras`, `da_pagina`) antes do subagente | o molde do teste de comportamento (PDF de verdade, projeto de verdade) e da saída da lista |
| `tirar_da_lista.py` no scratchpad | tira as linhas e baixa o `TETO` de uma vez; sem ela, cada redução eram duas edições à mão |
| As três exceções da rodada 1 conferidas aqui | o subagente confirmou no PySide6 6.11.1 que o offscreen ignora o `setColorScheme`; o `main` e o Ace não têm teste honesto na rápida |
| O `app` dos quatro arquivos passou a ser o do conftest | é a mesma `QApplication` que o do `test_janela` devolvia (uma por processo) |
