# Passo Q7 — cortar os objetos-deus (em andamento, ramo `qualidade-q7`)

Oitavo passo de `plans/roadmap-qualidade.md`, a partir do `08a0080` (o Q6 mesclado no
`passo-i-treino`), na worktree irmã `C:\Python-Chess2\AbbyChessCraft-qualidade`. O roadmap
pede um corte por sessão; cada corte pina o comportamento, muda a estrutura e prova que nada
mudou com a mesma suíte.

## Cortes feitos

| Corte | Commits | O que mudou |
|---|---|---|
| 1. `aplicar_lida` (CA-Q-A2, parte 2) | `1c70d7f` o teste que pina o F5 e o lote na mesma página; `1015cb4` a função | `abbychess/arrumacao.py`: `arrumar(pagina, idioma)` (os ids, as legendas, os lances validados), usada por `_mudou` e `depois_de_editar`; `aplicar_lida(pagina, lida, idioma, tamanho=, zona=)`, usada pelo F5 e pelo lote. O pipeline "depois de ler" estava em quatro lugares |
| 2. `EstadoDaJanela` (CA-Q-A2, parte 1) | `6366d2f` o teste sem janela (vermelho); `2ce37e4` o módulo | `abbychess/estado_da_janela.py`: `calcular(p, livro, vista)` dá, por ação, None ou o motivo de não valer, as operações de página com a dica, e os textos do desfazer; `acoes.atualizar` só aplica; o alias `editar = tem` saiu |

Verificação de cada um: a rápida inteira com -n 4 (1917 e 1922 passaram, 3 pularam, 77–78 s);
ruff E,F limpo. A medida e o portão ficam para o fim do passo.

## O que falta

3. `ControladorDePagina` (`controlador.py`, 2 620 linhas): `Navegador`,
   `ControladorDaSequencia`, `PonteDeLeitura`, `AplicadorDoHistorico`, `ControladorDaSessao`, a
   fila para o `ControladorDaFila`.
4. `ProjetoDeLivro` (`projeto.py`, 2 215 linhas): `CacheDePaginas`, `ResumoDoLivro`,
   `Migracoes`, `Fonte`; e o resto do Q-P9 que o Q6 passou para cá (as duas fontes da verdade
   da sequência e do próximo pid, a cópia do `Box` na saída do cache).
5. A exportação (`exportar.py`, 2 130 linhas): `Pedido`, o adaptador do Documento (Q-E6), as
   regras únicas do Q-E5.

O CA-Q-A1 (nenhum arquivo acima de 1 000 linhas) pega também `controladores.py` (2 055),
`pagina.py` (1 446) e `epub.py` (1 154), que o roadmap não lista: o teste de arquitetura entra
com o teto descendo a cada corte.

## Registro

| Ação | Por quê |
|---|---|
| O teste do corte 1 pina os dois caminhos antes de juntá-los | o CA pede a comparação; ela passou no código de antes, e passou igual depois |
| A primeira versão dos dados do teste não cabia na página sintética (900 × 260) | o diagrama sumia (o `mesclar` só guarda o que a leitura traz); refeitos para caber |
| O F5 passa `evento=None` ao `_mudou` | o estado já vem de `aplicar_lida`; reconhecer duas vezes mudaria o estado em dobro |
| As leituras do `calcular` ficam atrás do `pronto` | o `and` do `atualizar` antigo cortava a leitura da visita sem página; a primeira rodada reprovou 332 testes por isso |
