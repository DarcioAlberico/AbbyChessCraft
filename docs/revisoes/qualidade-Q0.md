# Passo Q0 — alavancas e portão (2026-10-30, ramo `qualidade-q0`)

Primeiro passo de `plans/roadmap-qualidade.md`, a partir do `980e2cb` (a spec e o roadmap),
na worktree irmã `C:\Python-Chess2\AbbyChessCraft-qualidade`.

## O que foi feito

| Commit | O quê | Como foi provado |
|---|---|---|
| `0d57f2f` | O portão `ruff --select E,F` volta a passar: `re`, `Dict` e `Optional` sem uso em `camada.py` (desde `a973d3b`) | o ruff do portão em `abbychess`, `tests` e `ferramentas`; os 33 testes que importam a camada |
| `18776fa` | Os testes do crapper e do dryer, chamados como na linha de comando, sobre um pacote de brinquedo com a complexidade contada à mão | os 4 passam; com os dois erros da análise recolocados um momento, 3 falham pelo motivo esperado |
| `4853f70` | `ferramentas/qualidade.py`: a rápida e a `processo` em série com a cobertura somada, o CRAP, a duplicação e o resumo JSON | o teste do resumo; a medida abaixo |
| `3e2fc4d` | `.coverage` e `.coverage.*` no `.gitignore` | a árvore limpa depois da medida (`arvore_suja: false`) |
| este | A linha de base combinada na §1 da spec, o comando no README e este registro | — |

## A medida (`3e2fc4d`)

`docs/medidas/qualidade/2026-10-30-qualidade.json`: a rápida 1844 passaram e 3 pularam (93 s
com cobertura), a `processo` 35 passaram (222 s), a cobertura 91,7 %, 286 funções com
CRAP ≥ 10 (eram 301 só com a rápida) e 16 pares do dryer. Dos 45 casos de cobertura baixa, 16
eram só a camada `processo`; os 29 que sobram estão na §1 da spec.

## Registro

| Ação | Por quê |
|---|---|
| Uma worktree irmã nova, e não a `AbbyChessCraft-roadmap` | a pasta principal é compartilhada; a do roadmap está no ramo `pendencias` |
| Tirar os imports antes de tudo | o portão vermelho esconde qualquer erro novo de E/F dos passos seguintes |
| Testar as ferramentas pela linha de comando, num pacote de brinquedo | é como elas são usadas; a complexidade contada à mão é o "uma unidade à mão" da alavanca |
| Recolocar os dois erros da análise por um momento | ver o teste falhar pelo motivo esperado (o método some; a filha casa com a mãe) |
| Rodar a `processo` com cobertura sozinha, primeiro | saber se o pytest-cov mede os filhos abertos por `spawn`: mede, mas a matança do gravador (36 s sem cobertura) passou dos 60 s e o pytest-timeout derrubou a camada |
| Subir o teto só na ferramenta (`--timeout=600`), sem mexer no teste | o custo é da cobertura em cada filho, não do código medido |
| Apagar os `.coverage.*` que a tentativa deixou e ignorá-los no git | eram meus, e sujariam o estado do git das medidas |
| Medir por último, sem editar durante a medida | regra do projeto: o pytest importa o código no início |

## O que ficou

- O CA-Q-X1 (o teste de arquitetura que reprova CRAP novo ≥ 10) fica para o Q8, como no
  roadmap; até lá, cada passo mede com `ferramentas/qualidade.py`.
- A rápida com cobertura leva 93 s; sem cobertura a meta continua < 60 s (Q4, decisão 13.5 da
  spec).
