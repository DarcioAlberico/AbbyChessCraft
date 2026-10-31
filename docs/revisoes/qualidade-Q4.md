# Passo Q4 — suíte confiável (2026-10-30/31, ramo `qualidade-q4`)

Quinto passo de `plans/roadmap-qualidade.md`, a partir do `7f04e91` (o Q3 mesclado), na
worktree irmã `C:\Python-Chess2\AbbyChessCraft-qualidade`. A decisão §13.5 da spec foi do
usuário: o teto da suíte rápida é 90 s com -n 4, sem cobertura.

## O que foi feito

| CA | Teste (reprovava assim) | Correção |
|---|---|---|
| Q-T1 | `5989fde`: na rápida, `com_modelos_globais` carregava a rede (4,9 s) | `617fb3b`: as fixtures autouse `sem_os_modelos_globais` (fora de `livro_real` e `desempenho`) e `avisos_que_nao_param` (o aviso modal da rede ausente parava o teste da tarefa em voo); o teste confere a condição dele quando a troca volta |
| Q-T2 | `c500f8c`: 23 `sleep` e asserções de relógio em 8 arquivos da rápida | `072408f`: `tests/ajudantes.esperar`, a espera única; os falsos com `Event`; o relógio falso do `Gravador`; as afirmações de tempo como fatos causais |
| Q-T5 | `a96bea7`: 128 importações de 48 nomes entre testes | `282a389`: os nomes em `tests/ajudantes.py`, `tests/fixturas.py` (pelo conftest a todos) e `tests/fixturas_<origem>.py` (as três `janela`); a `app` no conftest |
| Q-T4 | `a1e4f76`: sem teto, sem o resumo dos pulos, sem a camada noturna | `4fd272b`: o teto de 90 s no `pytest_sessionfinish`, os pulos por motivo no fim, as máquinas de estado nas duas camadas |
| — | — | `27ff9a4`: a §15.1 da SPEC e o contrato do roadmap com os 90 s |

## Verificação

- A suíte rápida 10 vezes seguidas com -n 4, cada uma com a máquina livre: 1877 passaram e 3
  pularam em todas, de 77 a 82 s (abaixo do teto); o fim de cada uma conta os três pulos (os
  validadores do EPUB sem a variável). O teste da tarefa em voo, 20 vezes seguidas.
- `ferramentas/qualidade.py` no `27ff9a4` (árvore limpa,
  `docs/medidas/qualidade/2026-10-30-qualidade-234047.json`): a rápida (110 s com cobertura,
  sem o teto, como deve) e a `processo` (35) passam; cobertura 91,9 %; 285 funções com
  CRAP ≥ 10; 16 pares do dryer.
- Portão `ABBY_PORTAO=1 pytest -m livro_real` no `27ff9a4`, com os validadores, sozinho na
  máquina: 21 passaram (o teste novo de que a camada `livro_real` carrega os modelos de
  verdade inclusive), 1 reprovou
  (`docs/medidas/2026-10-31-medida-falhou.json`): o mesmo índice da busca pela janela
  (CA-7.1), 2692 ms, dentro do que a base deu (2548–2894 ms).
- As camadas lentas coletam sem erro depois da mudança dos módulos de apoio.
- O ruff do portão passa.
- A camada noturna inteira (2 × 5000 exemplos, até 30 min) não rodou; o teste confere que
  `-m noturno` as seleciona com 5000.

## Registro

| Ação | Por quê |
|---|---|
| Perguntar a §13.5 antes do gancho | a rápida leva ~76 s com -n 4: o teto de 60 s reprovaria toda rodada |
| A fixture dos avisos modais junto com a dos modelos | sem os modelos, o aviso da rede ausente travava o teste até o timeout (achado rodando-o) |
| O teste da tarefa em voo sem a espera da fila | a troca de projeto já espera a tarefa; a fila inclui a abertura do segundo, que não é a condição do teste |
| As afirmações de tempo como fatos causais | "levou menos de 0,5 s" quebra numa pausa do sistema; "voltou com o falso preso" não, e reprova o mesmo defeito |
| Uma ferramenta para mover os 48 nomes (`mover_apoio.py`, no scratchpad) | à mão seriam 128 importações e o fecho de cada definição; três versões erradas foram desfeitas antes da que ficou (os parâmetros contados como dependência, as importações copiadas inteiras, o `*` que não traz o `_`) |
| As fixtures pelo conftest, e não importadas | importadas, cada teste que as recebe precisava do `# noqa: F811` |
| As três `janela` em apoios separados | o nome se repete com definições diferentes |
| As fixtures de sessão para o tempo, não | eram para os 60 s; com 90 s a suíte já cabe |
| Esperar as outras suítes da máquina antes de cada rodada | uma carga pesada por vez |

## O que ficou

- Os `# noqa: F811` antigos dos testes que recebiam as fixtures agora do conftest ficaram,
  sem efeito; uma limpeza à parte.
- O `test_fen_no_livro` que pula quando a segmentação falha e o `times.ttf` sem guarda (Q-T4)
  vão com os testes de implementação, no Q8 (Q-T3).
- O executor síncrono dos testes ainda não leva o erro do `pronto` ao `falhou` (do Q2).
- O índice da busca pela janela (CA-7.1) passa da meta também na base.
