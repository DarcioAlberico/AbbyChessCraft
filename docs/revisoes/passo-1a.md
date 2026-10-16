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
