# Passo 1a — revisões de fechamento

2026-10-16. Persistência ainda no formato v1: gravação atômica, `extras` e só leitura em
`projeto.json`, fonte relativa e relocalizada pelo SHA-256, `livro.json`. O passo não mexe
no desenho da janela (só nos avisos da abertura), então a revisão de design ficou dentro da
de produto e medição.

## Rodada 1

| Revisor | Notas | Veredito |
|---|---|---|
| Código e testes | Correção 6 · Simplicidade 8 · Testes 6 | volta |
| Produto e medição | Completude 6,5 · Fidelidade das medidas 7 · Clareza para o usuário 7 · Produtividade 8 | volta |

O que mudou depois dela:

| Achado | Correção |
|---|---|
| A trava de só leitura se perdia ao reabrir a mesma pasta (um `set` global sem contagem) | contagem de referências em `gravacao`; cada objeto solta só a trava que segura, uma vez; o `abrir` normal não solta mais nada; testes de duas aberturas e do projeto vizinho |
| Os testes de falha trocavam a etapa inteira, e o código real de fechar o fd nunca rodava | as chamadas ao sistema (`_abrir_fd`, `_write`, `_fsync`, `_replace`) são nomes do módulo; os testes falham nelas com as etapas reais, conferem que nenhum fd ficou aberto e que não sobrou `.tmp`, inclusive com a escrita parada no meio |
| "3 falhas e depois sucesso" só no arquivo genérico | os dois cenários (3 falhas e permanente) nas 3 chamadas e nos 8 arquivos do projeto; PNG de padrão, esquecer e restaurar também passam pela gravação |
| Só leitura com a fonte sumida: laço sem saída e memória trocada | em só leitura, a abertura procura a fonte e a relocalização vale só na memória, sem gravar; uma relocalização que falha ao gravar desfaz a troca na memória |
| `PadroesDoLivro` criava `padroes/` num projeto só leitura | a pasta nasce com o primeiro padrão; teste sem `padroes/` |
| `livro.json` diferente do recalculado depois de mudar os limiares | `reaplicar_limiar` refaz os pendentes pelo histograma (exato com os limiares de duas casas das opções) e a janela o chama; teste de igualdade depois da troca |
| `marcadas.json` e `livro.json` gravados de duas threads sem trava | uma gravação de página por vez (`RLock`): página, marcadas e livro mudam juntos; teste com duas threads |
| Abrir em mídia só de leitura falhava no ajuste do `projeto.json` | o ajuste fica só na memória e a abertura segue, com aviso no log |
| Busca da fonte cara e com falso positivo de começo igual | o tamanho entra junto do SHA-256 (`fonte_tamanho`): candidato de outro tamanho nem é lido, e arquivo de mesmo começo e tamanho diferente é recusado |
| Interrupção na espera deixava `.tmp` | a limpeza do temporário está num `finally` |
| `limpar_temporarios` apagava qualquer `*.tmp` | só `*.json.tmp`, `*.txt.tmp` e `*.png.tmp` |
| `resumo_do_livro` devolvia o histograma do cache | cópia funda |
| Erro ao abrir a fonte depois de fechar o projeto anterior | a fonte do novo é aberta antes; se falhar, o novo é fechado e o anterior continua |
| Relocalização automática silenciosa | a janela avisa onde achou a fonte |
| Mensagens em só leitura | o aviso diz como trabalhar no projeto; os limiares avisam que valem só na sessão |
| README sem as medidas do passo; só o xv medido; "iguais à linha de base" sem dizer do desempenho | tabela "Desempenho por passo" gerada no README, com a variação entre rodadas declarada; os três livros medidos; coluna de commit na tabela de qualidade |
| A volta ao programa do passo 0 quebra sem aviso | nas Limitações: o `projeto.json` gravado pelo 1a não abre no passo 0; volta só pela cópia de segurança |
| Limitações incompletas em só leitura; "tenta de novo 5 vezes"; onde a fonte é procurada | o README lista as ações que falham; "até 5 tentativas ao todo"; a pasta-mãe; a spec §4.3 descreve a busca automática |

Ficou como está, de propósito: o `extras` regrava os limiares desconhecidos em
`extras["limiares"]`, e não em `limiares` (é o que a spec §4.3 diz: "vai para `extras`");
o docstring foi corrigido. Projeto antigo sem SHA gravado aceita o arquivo indicado na
relocalização (a abertura com a fonte presente já grava o SHA, então o caso é raro).
Dois commits por passo (código e medidas), como no passo 0, para as medidas registrarem o
commit do código que mediram.

## Rodada 2

| Revisor | Notas | Veredito |
|---|---|---|
| Código e testes | Correção 7 · Simplicidade 8 · Testes 7 | volta |
| Produto e medição | Completude 8 · Fidelidade das medidas 6,5 · Clareza para o usuário 8 · Produtividade 8 | volta |

O que mudou depois dela:

| Achado | Correção |
|---|---|
| Com o limiar de revisão 1,00, o histograma contava a confiança 1,0 como pendente | a confiança 1,0 tem a faixa 100 só dela; `VERSAO_DO_LIVRO` 2 refaz os caches antigos; o teste varre de 0,00 a 1,00 com confianças 0 e 1 |
| A chamada da janela a `reaplicar_limiar` sem teste | teste da janela: `livro.json` igual ao recalculado depois de cada troca de limiar (inclusive 1,00 e 0,00); em só leitura, nada muda e a mensagem diz "nesta sessão" |
| `reaplicar_limiar` mudava o cache antes de gravar | o cache só muda depois de gravado |
| A trava de só leitura podia ficar sem dono numa falha da abertura | a trava é posta por último em `abrir`; `_abrir` fecha o projeto novo se algo falhar; teste |
| A relocalização automática não gravava o tamanho | grava |
| **O atraso no lote "piorou 2,4 vezes" sem declaração** | primeiro A/B com 3 rodadas em cada código, mas **só do lote** (`-k atraso`): o p99 tem duas faixas, perto de 7–8 ms e perto de 20 ms, nos dois códigos (passo 0: 19,9; 7,7; 7,1 — 1a: 7,5; 20,5; 7,7). A rodada 3 apontou que essa carga é outra (o lote lê sem os padrões do Enter) e que a conclusão ia além dos dados; o A/B na condição completa está na rodada 3 |
| A seção das medidas dizia "passo 0" e a qualidade do passo 0 sumia da tabela | "As medidas do roadmap"; "Histórico da qualidade" com todas as medidas de cada livro, que mostra a qualidade do 1a igual à do passo 0 |
| A árvore suja com correções do código medido | commit das correções e todas as medidas de novo nele |
| Menores | "o projeto não foi aberto" ao cancelar a fonte; os avisos de só leitura dizem que a fonte achada ou indicada vale na sessão; onde a busca procura (o README, o docstring e a spec iguais); o limite de 200 conta só arquivos do tamanho certo, e está nas Limitações; erro ao gravar os limiares vira aviso; o roadmap descreve os commits do passo; as Limitações falam do `fsync` sem coalescência em disco lento ou com antivírus |

## Rodada 3

| Revisor | Notas | Veredito |
|---|---|---|
| Código e testes | Correção 8 · Simplicidade 8 · Testes 7 | volta |
| Produto e medição | Completude 8,5 · Fidelidade das medidas 6,5 · Clareza para o usuário 8 · Produtividade 8 | volta |

O que mudou depois dela:

| Achado | Correção |
|---|---|
| A migração do cache v1, o limite de candidatos da fonte e o tamanho na relocalização automática sem teste | testes: o `livro.json` v1 com a confiança 1,0 em "99" é refeito com "100" e versão 2; com o limite em 2, três arquivos do tamanho certo antes da fonte fazem a busca desistir, e trinta de outro tamanho não contam; o tamanho regravado |
| `_atualizar_livro` mudava o cache antes de gravar | o cache só muda depois de gravado; teste |
| Mensagens dos limiares contraditórias quando a gravação falha | "gravados" só quando gravou; se só o `livro.json` falha, o aviso diz isso; teste |
| **O A/B do atraso foi só do lote, outra carga; a conclusão ia além dos dados** | A/B **completo** (o módulo inteiro de desempenho, 3 rodadas na tag `passo-0` e 3 no 1a `315db35`, na mesma máquina, tabela "Rodadas repetidas" gerada no README). Resultado: **o 1a custa tempo.** O Enter (p95) ficou acima do passo 0 nas três rodadas, e a troca de página também; o atraso no lote cai mais vezes na faixa alta (contando todas as rodadas completas, 4 de 6 no 1a contra 1 de 5 no passo 0), abaixo do alvo de 50 ms. A causa provável são os `fsync` síncronos novos (página, `livro.json`, padrão e metadados). O README declara isso nas Limitações; o gravador assíncrono do passo 2a, com coalescência, tira essas gravações da thread da interface e do lote, e a medida do 2a tem de mostrar a volta |
| Número digitado à mão na legenda do desempenho por passo | saiu; a variação está nas rodadas repetidas, geradas dos JSON |
| A tabela das rodadas não dizia a condição | coluna "Rodada": completa ou só do lote, sem os padrões |
