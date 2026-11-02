# Passo Q6 — fronteira e tipos (2026-10-31, ramo `qualidade-q6`)

Sétimo passo de `plans/roadmap-qualidade.md`, empilhado no `qualidade-q5` (`fa22e1e`, não
mesclado), na worktree irmã `C:\Python-Chess2\AbbyChessCraft-qualidade`. A decisão §13.3 da
spec foi do usuário: o segundo processo abre o projeto só para leitura.

## O que foi feito

| CA | Teste (reprovava assim) | Correção |
|---|---|---|
| Q-P6 | `25de369`: 21 campos do `projeto.json` e dos limiares com o tipo errado; quase todos abriam (o `"limiares": 5` estourava no meio), e o erro da versão não dizia o campo | `5eff49a`: `TIPOS_DO_PROJETO`, `TIPOS_DOS_LIMIARES` e `_conferir_tipos`, antes de montar o `Projeto` e de gravar qualquer coisa; o erro diz o campo; o `gids_movidos` errado deixa de virar `{}` calado |
| Q-P8 | `016fa93`: ler `projeto.sequencia` gravava o `projeto.json` e o `livro.json` | `72a3baf`: `montar_sequencia`, chamada ao criar e em cada saída de `abrir`, grava os consertos; a propriedade e o `_carregar_livro` só leem; o conserto do livro na memória é um só (`_citar_no_livro`); as leituras pelo efeito saem |
| Q-P5 | `a2b16f3`: com a `projeto.lock` de outro dono, o projeto abria para gravar | `126e132`: `gravacao.tomar_a_pasta`/`soltar_a_pasta` (msvcrt ou flock, reentrante no processo); `abrir` a toma depois de ler o JSON e antes de criar pasta ou limpar temporário, e sem ela abre só para leitura com o motivo (`_abrir_so_para_leitura`, o mesmo caminho da versão mais nova); `criar` também a toma; `fechar` a solta |
| Q-P9 | `3720e01`: a notação `"figurina"` abria (cairia em letras) e o estado `"reconhecido"` entrava na página | `6cbbe2b`: `modelo.Estado` e `projeto.Notacao` (`StrEnum`); a notação errada dá `ProjetoInvalido` com o campo; o estado errado faz a página ilegível |
| Q-C3 | `6bf4c5c` (depois de `7f49d3a`, o embrulho num método): `ler_pelo_livro` e `sugerir` rodavam junto com o glifo do lote | `1b5acf2`: `dar_a_vez` embrulha os dois na trava, agora reentrante |
| Q-C5 | `302b771`: o pool fechado debaixo de um `obter` | `7157ea1`: `PoolDoIndice._fechar(se)` confere e tira numa trava só (eram três cópias) |
| Q-C5 | `220183c`: a busca lia as páginas do projeto trocado | `31903a2`: `_refazer` recebe o projeto do pedido; a busca por glifo e a procura das amostras tinham a mesma leitura |
| Q-C5 | `40ba931`: os recortes da Galeria do projeto velho entravam | `851e608`: a geração conferida na thread e na chegada |
| Q-C5 | `8b78888`: o filho reaberto rodava o pedido cancelado | `22a494a`: o cancelar vai de novo, logo depois do pedido |
| Q-C5 | `f3e2a76`: o desfazer que falhava nos padrões deixava a transação aplicada na pilha | `919aa3b`: o histórico anda com as páginas, antes do disco; a falha dos padrões vira aviso |

## Desvios da spec

- **CA-Q-P9, a página:** o estado desconhecido num `p<pid>.json` não dá `ProjetoInvalido`;
  a página cai na regra da página ilegível que o Q2 decidiu (CA-Q-P7 revisto): uma página
  estragada não impede o livro de abrir.
- **Q-P9, o resto:** as duas fontes da verdade (`dados.sequencia`/`_sequencia`,
  `dados.proximo_pid`/`_proximo_pid`) e a cópia do `Box` na saída do cache ficam para o Q7,
  com a divisão do `ProjetoDeLivro`: o CA só pede o estado e a notação.
- **Q-C3:** o `arbitro` não ganhou embrulho: ele lê pelo `ler`, que já passa pela vez
  inteira, e embrulhá-lo de novo poria o lote a esperar a vez segurando a trava.

## Verificação

- A rápida inteira no `6cbbe2b`, depois do último CA que mexe em tudo: 1907 passaram e 3
  pularam em 75 s (-n 4, máquina livre). Cada CA seguinte rodou os testes da área dele
  (servidor, busca, Galeria, desfazer: de 47 a 855 testes) e a camada `processo` do
  servidor.
- `ferramentas/qualidade.py` no `919aa3b` (árvore limpa,
  `docs/medidas/qualidade/2026-10-31-qualidade-020243.json`): a rápida com cobertura (110 s)
  e a `processo` (211 s) passam; cobertura 92,0 %; 282 funções com CRAP ≥ 10 (281 no Q5: o
  `abrir` virou dois, 13 e 15, onde era um só); 1 par do dryer, 0 fora da lista.
- Portão `ABBY_PORTAO=1 pytest -m livro_real` no `919aa3b`, com os validadores, sozinho na
  máquina: 21 passaram, 1 reprovou (`docs/medidas/2026-10-31-medida-falhou-021148.json`): o
  mesmo índice da busca pela janela (CA-7.1) que reprova na base, mediana 2541 ms e máximo
  2955 ms (no Q5, 2416 e 2931; a base deu 2548–2894 ms).
- O ruff do portão passa.

## Registro

| Ação | Por quê |
|---|---|
| Perguntei a §13.3 antes do CA-Q-P5 | só leitura ou recusa é escolha do usuário |
| A trava no byte 2³⁰, não no 0 | a primeira rodada da rápida reprovou 30 testes: o byte travado não se lê por outro descritor, e fotografar ou copiar a pasta (um backup, o Explorer) esbarrava nele |
| Fechei o projeto antes de mover a pasta no teste de mudar de pasta | no Windows, a pasta com um arquivo aberto não se move; o teste quer o projeto fechado que muda de lugar |
| Corrigi a expectativa do segundo teste do Q-P8 antes do commit vermelho | a sequência remontada ganha pids novos, como já era; o teste pinava outra coisa |
| Extraí `dar_a_vez` num commit à parte antes do teste do Q-C3 | o vermelho devia reprovar pela sobreposição, não por um nome que faltava |
| Troquei o `arbitro` do leitor falso | o de verdade lê pelo `ler`; o falso fingia um caminho que não existe |
| Os testes das corridas encenam a intercalação (a thread adiada, a trava que dá a vez no meio) | sem `sleep` na rápida (a regra do Q4), e determinísticos |
| Medi e rodei o portão com a worktree parada | a regra da casa |
