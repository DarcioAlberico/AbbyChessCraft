# Passo Q2 — nenhum erro some (2026-10-30, ramo `qualidade-q2`)

Terceiro passo de `plans/roadmap-qualidade.md`, a partir do `0b447a2` (o Q1 mesclado), na
worktree irmã `C:\Python-Chess2\AbbyChessCraft-qualidade`.

## O que foi feito

Cada CA em dois commits: o teste, que reprova no commit de partida pelo motivo registrado, e
a correção.

| CA | Teste (reprovava assim) | Correção |
|---|---|---|
| Q-C1 | `e52ae33`: o `pronto` que levanta escapava para o laço do Qt, sem log nem `falhou`; o gancho do erro solto não existia | `4822e69`: `Executor._fim` leva o erro ao log com o rastro e ao `falhou` da tarefa; `registrar_os_erros_soltos` (o `sys.excepthook` e o `threading.excepthook`) no `main` |
| Q-C4, a regra | `21c6a83`: o teste de arquitetura achou nove `except` amplos que engoliam ou perdiam o rastro | `e42ba60`: os nove avisam com o rastro; o aviso do lote leva o rastro da leitura que falhou |
| Q-C4, a tabela | `d7b4bd2`: os metadados ilegíveis dos padrões viravam `{}` e eram regravados; um ouvinte que levanta calava os seguintes e subia para o comando | `b7461aa`: os metadados ilegíveis vão para `metadados.corrompido.json`; `Eventos.emitir` isola cada ouvinte; o fechamento com a tarefa presa vai ao log |
| Q-P7 | `b1f609f`: com um `p<pid>.json` truncado, o livro a dava por reconhecida, a busca e os Diagramas a pulavam e abri-la levantava `JSONDecodeError` | `c65476a`: `_gravada` isola o arquivo em `p<pid>.corrompido.json`, tira a página do livro e avisa uma vez; a página é não reconhecida para todos |
| Q-C2 | `76b88b5`: com o servidor, o lote gravava a página de um F5 em voo e a dava por lida; o `pronto` do F5 sobrescrevia a leitura do lote | `47aa314`: `lendo_no_f5` (do preparar ao pronto do F5) e o lote deixa a página para reler depois |
| — | a medida no `47aa314` achou dois pares novos de duplicação, deste passo | `069f995`: `_avisar_da_pagina` e `_reconhecer(zona)` |

## Verificação

- Suíte rápida com `-n 4`: 1858 passaram, 3 pularam.
- `ferramentas/qualidade.py` no `069f995` (árvore limpa,
  `docs/medidas/qualidade/2026-10-30-qualidade-212957.json`): a rápida e a `processo` (35)
  passam; cobertura combinada 91,8 % (igual ao Q1); 285 funções com CRAP ≥ 10 (285); 16 pares
  do dryer (16). Os últimos ~2 min coincidiram com a suíte de outro projeto da máquina; a
  medida é de correção e de cobertura, não de tempo.
- Portão `ABBY_PORTAO=1 pytest -m livro_real` no `069f995`, sozinho na máquina: 20 passaram,
  1 reprovou (`docs/medidas/2026-10-30-medida-falhou-214116.json`), o mesmo do Q1: o índice
  da busca pela janela (CA-7.1), 2824 ms de mediana para a meta de 2000 × 1,2. Rodado duas
  vezes em cada, alternando: a base `0b447a2` dá 2802 e 2894 ms, o Q2 3274 e 2554 ms. O
  ruído cobre a diferença; não há regressão que se veja.
- O ruff do portão passa; `janela.py` tem 499 linhas (CA-14.1).

## Registro

| Ação | Por quê |
|---|---|
| O `qtbot.waitUntil` no teste do executor | o pytest-qt já estava nas dependências; é o fim do laço com `sleep` (Q-T2) para os testes novos |
| A lista `LEVAM_O_ERRO` pelo nome da função, e não pela linha | a linha muda a cada edição; a função e o motivo, não |
| Um teste por linha da tabela só onde a falha perde mais que o log | as outras ganharam o rastro, que o teste de arquitetura já confere |
| No Q-P7, a página ilegível guardada e não reconhecida, em vez de um estado "ilegível" | o estado novo passaria pela máquina de estados e por três telas; assim nada nasce e é a regra dos metadados dos padrões; a spec registra a troca |
| O isolamento com a trava das páginas, e relendo o arquivo ali | o gravador pode tê-lo regravado no meio: o novo vale |
| `ligar_os_avisos_do_projeto` no `desenho` | os dois caminhos de abertura repetiam três linhas, e a janela passava das 500 |
| No Q-C2, vale o F5 | é o comando do usuário na página aberta; o lote já deixa para depois a página editada no meio |
| Um print temporário para ver o dano do Q-C2 na base | o primeiro assert reprovava antes de mostrar o que o usuário veria |
| A duplicação que o passo criou saiu antes de fechar | a medida a achou (18 pares); o passo não deixa o dryer pior |
| Esperar as suítes de outro projeto antes da medida e do portão | uma carga pesada por vez; o portão tem testes de tempo |
| Apagar as quatro medidas `medida-falhou-*` das comparações (duas na pasta principal) | eram minhas; fica a do portão |

## O que ficou

- O índice da busca pela janela (CA-7.1) passa da meta também na base.
- O executor síncrono dos testes (`ExecutorSincrono`) ainda não leva o erro do `pronto` ao
  `falhou` como o da janela (o M9 da revisão): os testes de controlador não exercitam esse
  caminho. Cabe no Q4.
- A tabela do Q-C4 tinha "a camada do PDF descarta o que já foi lido": a extração é uma
  chamada só, nada se descartava; o relatório da exportação sem a camada é do Q3.
