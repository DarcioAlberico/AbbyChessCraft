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

| 2. Os módulos puros (`sequencia`, `lances`, `texto`, `historico`, `modelo`, `sessao`) | `9209b87` à mão (o molde: `Entrada.__post_init__`); `bd04683`, `09c9f36`, `631e9e6`, `27927ef` (os testes do `emendar`), `d140872`, `aad6d64`, `a97f6dd`, `3428a31`, `064f64f`, `6afeef8`, `4800a40` por um subagente, revisado aqui; `0e412bb` à mão | as 40 partidas, cada parte com cc ≤ 8; as grandes viraram uma classe com os passos (`_Reconciliacao`, `_Divisao`, `_Reescrita`, `_Linha`); os laços por glifo inteiros (a reconciliação de 3 000 glifos e o `alinhar` medidos antes e depois: iguais) | 255 → 215 |

| 3. A análise da página (`contexto`, `zonas`, `busca`, `ancoragem`, `layout`, `edicao`, `verificacao`) | `926949b`, `33f32e1`, `d5ac063`, `6257eb7`, `eef42f9`, `787bcf6`, `2cff6ba`, `3ddccc0`, `5bddec0`, `ef5bad5`, `3322106` por um subagente, revisado aqui; `475b380`, `13dde31` à mão | as 36 partidas, cada parte com cc ≤ 9; quatro commits só de testes antes de partir (a continuação da legenda e o ponto solto, a figurina digitada na busca, os virtuais ancorados no que se apaga, as listas extras do léxico: regras sem teste nenhum); os laços quentes medidos antes e depois (o `julgar` de 3 066 glifos, o `indexar_pagina`, as linhas das zonas: iguais); dois pares do dryer que o partir expôs, juntados (`texto.chars_dos_gids` para o contexto; `layout.partes_pelo_vao`, a mesma regra do vão no layout e nas zonas) | 215 → 179 |

Na rodada 3, também: `475b380` — o subagente achou e parou em `_linhas_que_atravessam`, que
recalculava o topo e o pé da fila a cada glifo da página: numa página de duas colunas de 3 410
glifos, 13,7 ms (quase metade da ordem de leitura); contados uma vez por fila, 1,9 ms, as
mesmas faixas. Sem teste vermelho (o custo é linear vezes o tamanho da fila: um teste de relógio
honesto não sai); a prova é a medida. Também anotado, não mudado: `_nada_no_meio`, no
`partir_depois_do_f`, percorre o trecho a cada partição (~20 ms em 154 partições da página
sintética; numa página real, bem menos).

Na rodada 2, também:
- `26af726`: partir levou o `modelo.py` de 966 para 1 154 linhas (a catraca do tamanho
  reprovou); a geometria (reenquadrar, dividir, endireitar) foi para `geometria_do_modelo.py`,
  sem import circular: o modelo só a citava em comentário. As duas `_caixa` iguais no topo do
  modelo (desde o passo L) ficaram uma em cada módulo.
- `21f8bea` (vermelho) e `09530eb`: o subagente achou um defeito de desempenho e parou nele.
  `_dividir_ligaduras_repetidas` contava cada glifo percorrendo todos os itens: no D2, cada
  confirmação do Documento numa página de 2 500 glifos levava ~0,5 s só nisso. O teste de
  desempenho (`tests/desempenho/test_sessao.py`) pede crescimento linear; com um `Counter`, o
  `planejar` dessa página foi de 534 para 11 ms. `0e412bb` partiu a função depois.
- `d8eac12`: a medida no `0e412bb` reprovou pelo dryer, com três pares novos, todos de
  partes tiradas de funções grandes (a repetição já estava dentro delas): juntados.

Também, achado na rodada 1: `8ff1c29` (vermelho) e `c25cbd0` (CA-Q-T5) — a regra dos imports
entre testes só via `from tests.test_x import`; seis arquivos ainda pegavam fixtures ou nomes de
outro teste por `from tests import test_x` ou `import tests.test_x`.

Verificação: a rápida inteira no `0179591`, 1987 passaram e 3 pularam em 83 s (-n 4; eram
75 s: os ~45 testes novos de widget). O teto é 90 s: as próximas rodadas partem funções e quase
não acrescentam testes, mas a folga é pequena.

Medida no `0e412bb` (`docs/medidas/qualidade/2026-10-31-qualidade-163049.json`): as duas
camadas passam (a rápida com cobertura em 127 s, a `processo` em 238 s); cobertura 93,4 %
(92,2 % no fim do Q7); 215 funções com CRAP ≥ 10, nenhuma fora da lista e nenhuma da lista
abaixo de 10; o dryer com 3 pares fora da lista, juntados no `d8eac12` (o dryer de novo: 1
par, o aceito). A rápida sem cobertura no `0e412bb`: 1990 passaram em 73–85 s.

## O que falta

As 176 de cc ≥ 10 que ainda dizem "a reduzir (Q8)" (eram 252) ("a reduzir (Q8)"): partir, com a suíte como pino (refatoração, sem mudar
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
| Rodada 2 nos módulos puros | são os que o Q9 vai mutar: partir antes de mutar |
| O defeito do `_dividir_ligaduras_repetidas` em três commits (o teste, a correção, o partir) | refatorar e mudar comportamento no mesmo commit é antipadrão; o teste com relógio fica na camada `desempenho`, fora da rápida (a regra do Q4) |
| A geometria num módulo novo, não outro corte do modelo | era a única seção que só dependia do resto e de que o resto não dependia |
| Os pares do dryer juntados, não aceitos | a repetição era de verdade (a mesma divisão, o mesmo índice); juntar seguiu o molde que o arquivo já tinha (`_levar`) |
| Daqui em diante, o subagente roda o dryer depois de partir | a medida só o roda no fim; os três pares apareceram nela |
| Rodada 3 com o dryer e a catraca do tamanho no protocolo | na rodada 3 ele pegou os dois pares na hora, e nenhum arquivo passou de 1 000 linhas |
| O `_linhas_que_atravessam` sem teste vermelho, com a medida | "se um teste honesto é impraticável, não escreva um ruim": o relógio não separa 13 de 2 ms do ruído sem um alvo, e a spec não tem alvo para a ordem de leitura |
