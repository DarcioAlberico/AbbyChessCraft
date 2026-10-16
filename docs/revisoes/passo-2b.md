# Passo 2b — Desfazer e propagação (§14.2)

Ramo `passo-2b-desfazer`, a partir de `diagramas-lado-e-pdf` (27bcfab): a tag `passo-2a`
mais o trabalho de duas sessões irmãs sobre os diagramas (o lado tirado de novo da legenda
depois de uma edição, e a marca do lado no PDF), commitado ali para não se perder.

## O que o passo fez

- **`HistoricoDoProjeto`** (`abbychess/historico.py`): o desfazer do projeto inteiro, de
  `Transacao`es. Cada uma diz, por página, só o que mudou: o `Box` de antes e o de depois de
  cada gid tocado, os vizinhos para recolocar um glifo que volta no lugar dele, a ordem
  inteira quando a ação reordena a página (marcar um quadro), e os campos da página que
  mudaram (decisões, áreas, tabuleiros, diagramas, estado); mais as amostras de padrão
  criadas e apagadas. Limite de 50 MB (estimado, com total incremental), as mais antigas
  saem.
- **Pré-condição por gid**: desfazer só aplica se cada gid da transação está igual ao que
  ela deixou (`igual`: o mesmo objeto ou o mesmo valor, como o de uma página relida do
  disco); senão recusa, inteira, com aviso. Mudança por fora em outros gids não impede.
- **O Enter em duas partes** (§14.2): a parte síncrona (o glifo manual, a amostra gravada,
  a cor nova) roda na hora; a propagação vai para a fila como tarefa *leve*, com uma cópia
  dos padrões que já tem a amostra nova (`PadroesDoLivro.instantaneo`,
  `LeitorDoLivro.para_propagar`), e emenda o `depois` da transação do Enter. Desfazer com a
  propagação rodando a invalida (`Transacao.invalidada`), e o resultado é descartado. Com só
  tarefas leves rodando, as edições e o Enter seguinte rodam na hora (`_agora`), e o painel
  de treino continua valendo.
- **O desfazer cobre** o esquecer padrão (as amostras apagadas voltam, e a releitura que ele
  pede emenda a transação) e as áreas (os arrastes seguidos da mesma área viram uma).
- **Ctrl+Z abre a página da transação** quando ela é outra.
- **Eventos finos** (§14.1): uma transação que só muda leituras avisa os gids, e a janela
  repinta só esses boxes (`VisorDePagina.repintar_boxes`); o painel de texto é refeito uma
  vez, 150 ms depois da última mudança. Sem isso, o Enter montava o documento inteiro duas
  vezes (a parte síncrona e a propagação), uns 45 ms cada.

## Decisões

| Decisão | Por quê |
|---|---|
| A pré-condição compara por valor, não só por identidade | a §14.2 pede "igual ao `depois`"; a página que sai das 16 em memória volta do disco com objetos novos, e a identidade recusaria o desfazer sem motivo |
| A ordem inteira só quando a ação reordena os que ficaram | a ordem de 2.000 gids custa ~70 KB por transação; quase toda ação só muda leituras ou põe e tira glifos (os vizinhos bastam) |
| O refazer não repropaga a propagação descartada | refaz o que a transação guardou; a §14.2 não pede mais; o Ctrl+R relê os pendentes (o README diz) |
| Os campos da página voltam só se ainda estão como a ação os deixou | a pré-condição é por gid (§14.2); um campo mudado depois por outra ação fica, e as decisões que citarem um glifo que saiu caem |
| O texto da página com 150 ms de atraso | o documento leva dezenas de ms para montar e é derivado (§4.2); a cor do glifo, que é o que o usuário espera ver, muda na hora |

## Verificação

- Suíte rápida, ruff, camada `processo` (4 passaram).
- CA-14.2: `tests/test_desfazer.py` (unidades da pré-condição; na janela, mudança por fora no
  gid recusa com aviso e sem mudar nada, em outro gid não impede; igual por valor desfaz).
- CA-14.3: ensinar, a propagação terminar e desfazer volta a página toda; desfazer com a
  propagação presa não aplica o resultado dela; um Enter durante uma propagação presa não
  perde nem duplica leitura (e dois Ctrl+Z voltam a página inteira); [desempenho]
  `enter_com_propagacao_lenta`.
- CA-4.3 (2b): a `MaquinaDoControlador` ganhou `desfazer_tudo` (volta à página inicial, os
  mesmos `Box`, as decisões e o estado, quando nada mudou por fora) e `editar_e_desfazer`;
  conferida contra dois mutantes (recolocar no fim; a propagação que ignora a invalidação).
- Mais: desfazer e refazer uma área (com os ids), desfazer depois de a página sair da
  memória, o Enter que não grava a amostra não deixa nada, a ordem de quem marca, o Alt+seta
  redesenha a caixa no visor.

## Rodada 1 (código)

| Revisor | Notas | Veredito |
|---|---|---|
| Código e testes | Correção 6 · Simplicidade 8 · Testes 6 | volta |

| Achado | Correção |
|---|---|
| **B1** Os ids que a gravação dá às áreas e aos diagramas faziam o desfazer largar esses campos (o "Desenhar área" desfeito deixava a área) | `_mudou` dá os ids antes de medir; teste de desfazer e refazer uma área |
| **M1** A pré-condição por identidade recusava o desfazer de uma página relida do disco | `historico.igual` por valor; teste com a página tirada da memória |
| **M2** O Enter síncrono sem tratamento de falha deixava amostras órfãs | falha inteira: as amostras gravadas saem, aviso, nenhuma transação; teste |
| m1–m6 | os vizinhos de um glifo mexido e depois removido no `emendar`; o comentário e a ordem do `invalidada`; a estimativa com vizinhos e itens, total incremental; código morto; o teste do Enter durante a propagação confere a página inteira |
| Achado pela máquina, nesta rodada | marcar um quadro reordena a página inteira e a transação não guardava a ordem: `MudancaDaPagina.ordem`, teste explícito |
| Desempenho, achado no ensaio | o Enter até o fim da propagação passou de 82 para 120 ms na mediana (o documento montado duas vezes); eventos finos e o texto refeito depois da última mudança |

## Rodada 2 (código)

Correção 7 · Simplicidade 8 · Testes 8 — volta. **N1**: o repintar parcial não movia a caixa
(o Alt+seta para a direita ou para baixo deixava o quadro antigo). `repintar_boxes` põe a
caixa de agora; teste do visor, conferido contra a versão sem a correção.

## Rodada 3 (código)

Correção 9 · Simplicidade 8 · Testes 9 — **aceita**.

## Medidas (commit `b5c5142`)

- Portão (`ABBY_PORTAO=1 -m "livro_real or desempenho"`): 9 passaram;
  `docs/medidas/2026-10-16-passo-2b.json`.
- Rodadas repetidas: 3 com o congelamento (`repeticao-2b`) e 3 sem
  (`repeticao-2b_sem_congelar`). O critério do roadmap, nas 3 com o congelamento:
  - o Enter até a cor mudar fica ≤ 100 ms no p95 nas 3 (31,8; 54,8; 47,6);
  - as medianas não sobem mais de 5 ms acima das do 2a: o Enter até o fim da propagação deu
    75,7; 88,4; 78,2 (2a: 91,4; 82,9; 83,7), e a releitura 15,1; 15,6; 20,0 (2a: 74,8;
    74,9; 74,6);
  - a memória do desfazer estimada fica ≤ 50 MB: 8,1 MB.
- **A memória do desfazer sem o congelamento saiu negativa** nas 3 rodadas (−16,4 MB): com
  60 ações, o histórico prendia ~85 KB, menos que o que o coletor de lixo solta por conta
  própria entre as duas leituras. A medida passou a ter 300 ações e a trazer também a
  estimativa do histórico (commit `1f1ea5c`, que só muda o teste); rodada de novo, com e sem
  o congelamento (`memoria-2b-com`, `memoria-2b-sem`): 8,1 MB nas duas, e 7,3 MB pela
  estimativa. Essas duas foram medidas com a árvore suja (o README e este registro, só
  texto).
- **O congelamento saiu**: com e sem ele, os números ficaram iguais ou melhores sem (o Enter
  até a cor: 24,8; 35,2; 24,8 com, 21,5; 23,3; 32,8 sem; a troca: 153,9; 150,1; 170,2 com,
  153,6; 148,5; 147,7 sem). `congelar_para_a_coleta_de_lixo` só congela com `ABBY_CONGELAR=1`.
- Um pico de 935 ms no atraso máximo durante o lote, numa rodada com o congelamento; as
  outras 5 deram 124–154 ms. Não se repetiu nem foi investigado (o README diz).
- Qualidade (`medir.py`, os três livros) e fatia (`replay_fatia.py --passo 2b`): iguais às
  do 2a; só o tempo do lote (xv 460 → 447 s) e a marca de árvore suja (o README e este
  registro, sem código) diferem.

## Revisão de produto, rodada 1

| Revisor | Notas | Veredito |
|---|---|---|
| Produto e medição | Completude 8 · Fidelidade das medidas 7 · Clareza para o usuário 7 · Produtividade 7 | volta |

O revisor rodou a janela com cenários próprios (offscreen, a propagação presa) e achou:

| Achado | Correção |
|---|---|
| **M1** Quando a propagação resolvia o glifo mostrado, o painel pulava e apagava o que o usuário tinha digitado | o painel só avança sozinho se o glifo foi posto pela fila (não escolhido por clique ou Tab) e o campo não foi editado (`atual_resolvido`); três testes (avança, digitando fica, escolhido fica) |
| **M2** "Desfazer um ensinar devolve as repetições à fila" falhava depois de um Ctrl+R (fora do desfazer) | o Reler pendentes entra no desfazer; o refazer de um Enter desfeito com a propagação descartada roda a propagação de novo; testes |
| **M3** Uma recusa travava o desfazer inteiro | a recusa pergunta se tira a ação do desfazer, para chegar às anteriores; teste |
| **M4** A árvore suja de todas as medidas não estava declarada | os JSON passam a listar os arquivos sujos (`arquivos_sujos`); as medidas foram refeitas com a pasta limpa (abaixo) |
| **M5** A comparação 2a → 2b da releitura não mede o mesmo (o texto da página saiu do tempo medido) | o teste mede o painel de texto à parte (`texto_da_pagina`) e o README diz a mudança de método |
| m1–m8 | os textos do congelamento, da tabela e da memória (README); a propagação não cobre mais a mensagem do Enter na barra; o refazer propaga de novo; a recusa é uma pergunta, uma vez por Ctrl+Z |

A janela passou de 500 linhas com isso; o desenho foi para um mixin (`app/desenho.py`,
`DesenhoDaJanela`), com a mesma regra do CA-14.1 (teste ampliado).

## Rodada 4 (código, sobre as correções do produto)

Correção 8 · Simplicidade 8 · Testes 8 — **aceita**. Os dois furos que ela deixou entraram
junto: o refazer que repropaga decide depois de abrir a página da transação (teste de refazer
de outra página), e `mostrar` direto zera o "escolhido" (só `escolher` o liga).
