# Protocolo da medida da fatia (SPEC §15.4)

A fatia mede quanto trabalho custa levar as p. 21–27 do Xadrez Vitorioso (índices 20–26)
do estado reconhecido ao gabarito. Ela tem duas partes.

## CA-F.1: os gestos, pelo replay (reprova)

1. O ponto de partida é sempre o snapshot `tests/dados/fatia/xv-i020-026-inicial.zip`
   (projeto reconhecido com os modelos globais, padrões vazios), conferido pelo SHA-256 de
   `xv-i020-026-inicial.sha256`. Ele só é refeito por decisão registrada, e refazê-lo invalida
   a comparação com as medidas anteriores.
2. `ferramentas\replay_fatia.py rodar --livro xv --passo <passo>` simula as correções com os
   comandos de `ferramentas\replay\comandos.yaml` disponíveis no passo e grava
   `docs/medidas/AAAA-MM-DD-fatia-xv-passo-<passo>.json`.
3. Os custos do catálogo são conferidos contra a interface real por
   `tests\test_custo_dos_comandos.py` (QTest e um filtro de eventos); a convenção do que é um
   gesto está no próprio catálogo.
4. Só contam as linhas com `texto_verificado: true` e os diagramas do gabarito. Sem linha
   verificada, a medida é **pendente** (`"gestos": null`); os gestos dos diagramas saem à
   parte. Com gabarito por revisar (estrutura sem `revisado_por`, FEN sem `fen_verificado`),
   o `estado` diz **provisório** e o que falta.
5. **A linha de base é medida com o código do passo 0**, sempre: o replay chama o núcleo do
   programa (ensinar, propagar, dividir), e os passos 1b, 2b e outros mudam esse núcleo.
   Ela roda num worktree da tag `passo-0`, com os gabaritos copiados do checkout principal
   (os da medida nova):

   ```text
   git worktree add ..\AbbyChessCraft_passo0 passo-0
   robocopy tests\verdade ..\AbbyChessCraft_passo0\tests\verdade /E
   cd ..\AbbyChessCraft_passo0
   ..\AbbyChessCraft\.venv\Scripts\python.exe ferramentas\replay_fatia.py rodar --livro xv --passo 0
   ```

   O JSON gerado no worktree é copiado para `docs\medidas\` do checkout principal.
6. A comparação é `ferramentas\replay_fatia.py comparar <linha-de-base.json> <depois.json>`,
   que recusa medidas de snapshots diferentes, de versões diferentes do catálogo, de
   gabaritos diferentes (versão ou conteúdo de algum) ou de conjuntos de linhas diferentes.
7. **O critério** do roadmap vale sobre o total `gestos`, que inclui o custo fixo dos
   impossíveis: ≤ 85% da linha de base depois do passo A3, e ≤ 70% depois do D1. Um passo
   que torna possível uma correção antes impossível tem de baixar esse total. A navegação
   entre as páginas (`gestos_navegacao`) entra no total e sai também à parte.

## CA-F.2: o tempo de uma pessoa (informativo, não reprova)

1. O mesmo snapshot, aberto numa cópia, no programa do passo medido; a linha de base, no
   programa da tag `passo-0` (o worktree acima).
2. O tempo é o do registro de gestos da aplicação: com `ABBY_REGISTRO_DE_EVENTOS` apontando
   para um arquivo, o programa grava o instante de cada clique, tecla e atalho (sem o que foi
   digitado). `ferramentas\tempo_da_fatia.py` soma do primeiro ao último gesto, descontados
   os intervalos ociosos de mais de 60 s.
3. A linha de base é medida num bloco de páginas (índices 20–22) e o passo novo num bloco
   equivalente (23–25); numa segunda sessão, com pelo menos 7 dias de intervalo, os blocos
   se invertem, para descontar o aprendizado do texto.
4. O número de erros do bloco é o das diferenças do snapshot contra o gabarito nessas páginas
   (o replay as conta por página). O resultado é em segundos por erro e fica em
   `docs/medidas/AAAA-MM-DD-fatia-humana.json`, com o nome de quem mediu, o passo e o bloco.
