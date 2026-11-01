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

| 4. A exportação (`montagem`, `epub`, `exportar`, `margens`, `escritor_docx`, `pdf_pesquisavel`, `metadados`, `marcacao`, `previa`) | `e90887d` … `cfc12ea` (20 commits) por um subagente, revisado aqui; `ed33352` à mão | as 41 partidas, cada parte com cc ≤ 9; o golden da exportação (37 arquivos) igual a cada commit; os testes antes de partir: o que a conferência do EPUB recusa (17 casos) e a do DOCX (10), o PGN que sai e o que fica de fora, a palavra digitada sozinha; os tempos da camada do PDF, da `Estrutura.da_pagina` e da `pagina_extraida` iguais (7 páginas do golden, 10 308 glifos). Duas exceções com motivo: `_sem_coordenadas.fora` (roda por glifo e por tabuleiro) e `_no_calibre` (o validador externo, como o `ace`). Dois pares do dryer juntados | 179 → 140 |

| 5. Os controladores e a página (`controladores`, `pagina`, `ponte_de_leitura`, `controlador`, `fila_da_pagina`) | `deec535` … `ea1c83f` (18 commits) por um subagente, revisado aqui | as 34 partidas, nenhuma exceção, cada parte com cc ≤ 9; as partes do `ControladorDePagina` são funções do módulo (ele está preso em 61 métodos); cinco commits de testes antes de partir (PgDn e PgUp entre diagramas, a conferência que não grava, as palavras desconhecidas pelo livro — de 8 % a 83 % —, o lote a retomar da v2 e o ilegível, a prévia do Substituir que falha e a cancelada, os glifos aguardando a leitura); os laços quentes medidos (`_italicos`, `decidir_negritos`, `devolver_pingos`: iguais; a `fila` de 5 000, de 0,78 para 0,38 ms, as três listas num laço só) | 140 → 106 |

| 6. O resto do núcleo (25 módulos fora de `app/`) | `b469722` … `124966b` (31 commits) por um subagente, revisado aqui | 52 das 55 partidas, cada parte com cc ≤ 9, entre elas o `AplicadorDoHistorico._voltar` (cc 57, a pior do programa, para 7); o `atalhos._regras_da_tecla` partido pelas regras do docstring (não é despacho: uma tecla quebra várias regras), as teclas do Windows numa tabela; as partes do `ProjetoDeLivro` como funções do módulo (ele está preso em 43 métodos); seis commits de testes antes de partir (a sequência, a página ilegível, o servidor na camada `processo`, a sessão, as migrações); as 2 400 saídas com semente do `perturbar` iguais; ensinar e restaurar 300 amostras, 1,64 e 1,69 s antes e depois (o fsync domina). Três ficam com motivo: `PadroesDoLivro.ler` e `resumo_das_confiancas` (rodam por glifo), `_Laco._operar` (o despacho do protocolo com o filho) | 106 → 54 |

Na rodada 6, também: `b574ebc` — partir levava o `projeto.py` a 1 021 linhas; a notação, os
limiares, o `Projeto` e as conferências do `projeto.json` foram para `dados_do_projeto.py`
(mudança de lugar): 909 linhas. Fora de `app/`, a lista só tem exceções com motivo.

Na rodada 5, também: `deec535` e `22b025a` — os dois arquivos presos em `TETOS` não podiam
crescer. Do `controladores.py` saíram quatro controladores, cada um no seu módulo
(`controlador_de_layout`, `controlador_de_diagramas`, `controlador_do_livro`,
`controlador_da_substituicao`): de 2 055 para 813 linhas no fim. Do `pagina.py` saíram o
negrito e o itálico (`efeitos.py`) e a edição dos boxes (`editar_boxes.py`): de 1 446 para 998.
Os dois saem de `TETOS`: **nenhum arquivo de `abbychess/` passa de 1 000 linhas** (a parte dos
arquivos do CA-Q-A1; as cinco classes acima de 40 métodos continuam presas). Anotado, não
mudado: a anotação `hs.Instantaneo` em `ControladorDePagina._depois_de_editar` cita um nome que
o `historico` não tem (nunca avaliada, pelo `from __future__ import annotations`).

Na rodada 4, também:
- `e90887d` e `29be11c`: o `epub.py` estava em `TETOS` com 1 144 linhas e não podia crescer;
  a validação (a conferência interna, o Ace, o Calibre, o EPUBCheck) foi para
  `validacao_do_epub.py`, e as referências internas (página, diagrama, capítulo, que o DOCX
  também usa) para `links_internos.py`. O `epub.py` fica com 890 linhas e sai de `TETOS`
  (CA-Q-A1: sobram `controladores.py` e `pagina.py`).
- `508cb40` e `8239f2e` têm a lista um passo adiante do código (tiram o `trechos_marcados` e o
  `html_do_livro` um commit antes de parti-los): o `test_complexidade` reprova neles, passa do
  `3663751` em diante.
- `ed33352`: a medida no `cfc12ea` reprovou por uma função fora da lista,
  `_ComoDigitado._como_antes` (cc 8, 67 %, CRAP 10,4), da rodada 3: os dois ramos dela nunca
  tiveram teste. O teste de comportamento os cobre.
- A rápida no `cfc12ea` deu 104 s e 99 s (acima do teto de 90); alternando com a base
  `b8bd62c` numa worktree temporária: HEAD 83,6 e 81,8 s, base 93,0 e 83,2 s. Era a máquina;
  os testes novos da rodada custam ~2 s em série. O ruído chega a 10 s, perto do teto.

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

Medida no `cfc12ea` (`docs/medidas/qualidade/2026-10-31-qualidade-190615.json`): as duas
camadas passam; cobertura 93,9 %; 141 funções com CRAP ≥ 10, uma fora da lista (o
`_como_antes`, coberto no `ed33352`); o dryer com o par aceito só. Com o EPUBCheck, o Ace e o
Calibre configurados, os 87 testes que os usam passam no `ed33352`.

Medida no `ea1c83f` (`docs/medidas/qualidade/2026-10-31-qualidade-202733.json`): as duas
camadas passam; cobertura 94,1 %; 106 funções com CRAP ≥ 10, todas na lista; o dryer só com o
par aceito. O golden da exportação: 37 arquivos, 0 diferentes. A rápida sem cobertura: 91,3 s
e 85,3 s, com o AbbyChessCraft aberto na máquina (o usuário, desde as 17h32, com o servidor de
leitura): a folga do teto de 90 s é de poucos segundos.

Medida no `124966b` (`docs/medidas/qualidade/2026-10-31-qualidade-213958.json`): as duas
camadas passam; cobertura 94,5 %; 54 funções com CRAP ≥ 10, todas na lista (46 "a reduzir", 8
com motivo); o dryer só com o par aceito. O golden: 37 arquivos, 0 diferentes. A rápida sem
cobertura: 2055 passaram em 73,9 s.

## O que falta

As 46 de cc ≥ 10 que ainda dizem "a reduzir (Q8)" (eram 252), todas de `app/`: partir, com a
suíte como pino (refatoração, sem mudar
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
| Rodada 4 com o golden como pino a cada commit | a lição do Q3: a suíte não pega toda regressão da exportação |
| Os validadores do EPUB num módulo próprio antes de partir | o `epub.py` estava preso no teto de 1 144 linhas; partir dentro dele reprovaria a catraca |
| A rápida de 104 s comparada com a base antes de culpar a rodada | a regra da casa para tempo: conferir na base |
| O `_linhas_que_atravessam` sem teste vermelho, com a medida | "se um teste honesto é impraticável, não escreva um ruim": o relógio não separa 13 de 2 ms do ruído sem um alvo, e a spec não tem alvo para a ordem de leitura |
