# Passo Q1 — persistência sem perda (2026-10-30, ramo `qualidade-q1`)

Segundo passo de `plans/roadmap-qualidade.md`, a partir do `bc4c6c5` (o Q0 mesclado), na
worktree irmã `C:\Python-Chess2\AbbyChessCraft-qualidade`. A decisão §13.1 da spec foi do
usuário: migrar toda a v1 na abertura.

## O que foi feito

Cada CA em dois commits: o teste, que reprova no commit de partida pelo motivo registrado, e
a correção.

| CA | Teste (reprovava assim) | Correção |
|---|---|---|
| Q-P1 | `92f7a79`: depois de mover a 1ª página, a posição 0 (pid 1) mostrava os glifos da página do PDF 0; a abertura deixava os arquivos v1 na pasta | `7eedd90`: a v1 migra inteira na abertura, pelo pid; só para leitura, ela fica na memória por pid; um caminho só lê a página gravada (`_gravada`); saem `_tem_v1`, `_migrar`, `migrar_tudo` e `_arquivo_da_pagina` |
| Q-P2 | `0c99af5`: a falha de apagar `zonas/0001.json` derrubava a abertura para só leitura; o apagar não tentava de novo. Fora do pytest, a abertura seguinte regravava a página 0 com 0 dos 15 glifos | `499aff4`: o arquivo v1 de um pid que já tem o `p<pid>.json` é sobra e sai, salvo quando o `projeto.json` é o da v1 (CA-4.5); a falha de apagar vai ao log; `gravacao.apagar` tenta de novo |
| Q-P3 | `b1bd35d`: com o cache de 1 e o lote de 3, a janela mostrava `''` e não o "W" que o lote releu; com o cache de sempre o mesmo teste passava | `b26f117`: o `modelo` do controlador é propriedade, e trocar a página aberta a prende no cache (`projeto.prender`) |
| Q-P4 | `d9f2121`: com o gravador preso no instantâneo do "y", a gravação síncrona do "z" perdia para ele: a página reaberta tinha "y" | `0cea755`: bilhete por conteúdo fotografado, toda gravação do `p<pid>.json` por `_gravar_arquivo_da_pagina`, uma por vez, nunca um bilhete mais velho; o comentário da trava do livro corrigido |

## Verificação

- Suíte rápida com `-n 4`: 1850 passaram, 3 pularam.
- `ferramentas/qualidade.py` no `0cea755` (árvore limpa,
  `docs/medidas/qualidade/2026-10-30-qualidade-193149.json`): a rápida e a camada `processo`
  (35) passam; cobertura combinada 91,8 % (91,7 % no Q0); 285 funções com CRAP ≥ 10 (286); 16
  pares do dryer (16).
- Portão `ABBY_PORTAO=1 pytest -m livro_real` no `0cea755`: 20 passaram, 1 reprovou
  (`docs/medidas/2026-10-30-medida-falhou.json`). O que reprova é
  `tests/desempenho/test_busca.py::test_ca_7_1_o_indice_pela_janela_com_o_servidor`: o índice
  pronto em 2559 ms de mediana para a meta de 2000 ms × 1,2. Rodado duas vezes em cada, um
  depois do outro: a base `bc4c6c5` dá 2601 e 2548 ms, o Q1 dá 2457 e 2610 ms. A falha é
  anterior ao Q1.
- O ruff do portão passa.

## Registro

| Ação | Por quê |
|---|---|
| Ramo `qualidade-q1` na mesma worktree do Q0 | o Q0 já estava mesclado; a pasta principal fica intocada |
| Ler toda a migração (abrir, a cadeia, a leitura, a sequência da v2) antes do teste | a migração preguiçosa estava em seis métodos; a decisão do usuário tira todos |
| No Q-P1, o projeto só para leitura lê a v1 uma vez, como o JSON v2 que a migração gravaria | assim a leitura das páginas tem um caminho só, também sem gravar nada |
| Dois testes que punham um v1 num projeto aberto passaram a reabri-lo | o que eles protegem (a página antiga abre com os diagramas por ler) não muda; o momento da migração, sim, pela decisão |
| No Q-P2, rejeitar a correção da spec (a ordem de apagar) | sobrar o arquivo de página perde as áreas; a regra pelo `p<pid>.json` é idempotente nas duas sobras |
| Mostrar a perda do Q-P2 fora do pytest, num script no scratchpad | o primeiro assert do teste (só leitura) reprova antes do que perde dado |
| No Q-P3, um print temporário e uma rodada de controle com o cache de sempre | o primeiro teste passou na base; o print mostrou o despejo, e a releitura igual à anterior escondia a perda: o teste passou a injetar uma letra diferente |
| No Q-P4, rejeitar `salvar_modelo` pelo gravador | o erro de quem grava em síncrono deixaria de subir (os testes de `test_persistencia` dependem disso) |
| Um teste que força a ordem ruim, em vez de 500 sorteios | o sorteio raramente cai na janela; a ordem forçada reprova sempre na base |
| Apagar as quatro medidas `medida-falhou-*` das comparações de tempo (duas na pasta principal) | eram minhas; fica a do portão, no commit do passo |
| Medir por último, sem editar durante as medidas | regra do projeto |

## O que ficou

- O índice da busca pela janela (CA-7.1) passa da meta, também na base: é desempenho, fora
  deste roadmap; fica para quem cuida da busca.
- `ler_sem_migrar` e `ler_sem_guardar` fazem quase o mesmo (uma devolve o instantâneo, a outra
  o objeto vivo), e o nome da primeira não diz mais nada: Q5.
