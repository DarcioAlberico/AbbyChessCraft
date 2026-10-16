# Passo 1b — revisões de fechamento

2026-10-16. O modelo v2 (SPEC §4.1–§4.4): `Box` com gid por composição, `Diferenca` com
sucessores, decisões chaveadas por gid e reescritas pelos sucessores, `montar(pagina) ->
Documento` e o texto nos modos impresso e SAN, a procedência da leitura, `Zona` com função
e `DiagramaLido` com id, a máquina de estados de §4.4, o formato v2
(`paginas/p<pid>.json`) com a migração do v1 e `backup-v1/`, e o adaptador da janela.

## O que o passo decidiu, antes das revisões

| Decisão | Por quê |
|---|---|
| **A caracterização não mudou.** `pagina.texto` e `diagramas.texto_da_pagina` passam por `montar()` no modo SAN, e os golden de 2026-10-15 saem iguais | o roadmap pede justificar cada diferença; não houve nenhuma |
| `exportar.paragrafos` (a terceira montagem) continua como era | a paragrafação da exportação é do passo J; o documento já tem `paragrafo_antes` e `hifen_de_quebra` para ela usar |
| Migração **preguiçosa**, página a página, na primeira leitura | é o que §4.3 pede; `migrar_tudo()` existe para as ferramentas e os testes |
| Um arquivo v1 presente vence o v2 de mesmo pid | é o `backup-v1/` copiado de volta (CA-4.5) |
| A janela continua com listas de `BoxEntry` e índices; `modelo.reconciliar` acha os gids (pelo objeto, pela caixa, e sucessores por sobreposição) | o roadmap: "a janela ainda usa índices, por um adaptador que o 2a remove"; as edições por gid, com sucessores explícitos, estão em `abbychess/edicao.py` e são o que a máquina de estados exercita |
| A procedência vai por `abbychess/procedencia.py` (um registro por objeto, com referência fraca) | o `BoxEntry` é do core e não ganha campo (§4.1); some com o adaptador no 2a |
| `glifos_marcados` vem do "reconhecida=False" de hoje, e `reconhecer` não tira uma página de "em revisão" | §4.4; o lote e o F5 dizem `reconheceu=True` |
| A §4.6 (reconhecer de novo sem perder decisões) **não** entra no 1b | o roadmap a põe no passo E |

## O que a medida mostrou e o que mudou por ela

A primeira medida do 1b (3 rodadas completas) deu a releitura com p95 de 217–227 ms (o 1a
dava 141–165) e o Enter mais lento. O perfil com a janela e o livro real mostrou três causas,
todas corrigidas antes das revisões:

1. a reconciliação copiava os 1.450 glifos (`dataclasses.replace`) e chamava `as_state()`
   duas vezes em cada; o texto importava o core a cada caractere (gravação de ~26 para ~12 ms);
2. a foto dos estados eram milhares de tuplas de vida longa, que disparavam a coleta de lixo
   completa do Python a cada poucas edições (agora um dict de inteiros, que o coletor não
   rastreia);
3. cada coleta completa percorria ~230 mil objetos da rede e da base global; eles são
   congelados (`gc.freeze`) depois de carregados.

## Rodada 1

| Revisor | Notas | Veredito |
|---|---|---|
| Código e testes | Correção 6 · Simplicidade 7 · Testes 6 | volta |
| Produto e medição | Completude 8 · Fidelidade das medidas 6 · Clareza para o usuário 7 · Produtividade 8 | volta |

O que mudou depois dela:

| Achado | Correção |
|---|---|
| Dois virtuais depois do mesmo glifo saíam ao contrário | entram na ordem em que foram digitados (o segundo depois do primeiro), também no começo da linha; teste |
| `quebrar` depois de `juntar_palavras` na mesma fronteira não fazia nada | `quebrar` desfaz a junção que termina no glifo; invariante na máquina de estados: quebra e junção nunca na mesma fronteira |
| `livro.json` sem a página (queda entre página e livro) a escondia e a duplicava | a página é achada pelos arquivos que o livro não cita; de dois arquivos do mesmo índice vale o gravado por último (no recálculo também); testes |
| `gid_do_box` dava gid só na memória, e o gid vai para o nome do padrão | grava a página quando dá gid novo (e o estado vai a "em revisão"); teste depois de reabrir |
| `paragrafo_antes` só valia no primeiro glifo da linha | vale em qualquer glifo da linha (o documento é feito de linhas inteiras); teste |
| O cache guardava a foto velha quando a página era relida | a foto é refeita sempre que a página vem do disco; teste de LRU com a página expulsa e relida |
| Em só leitura, as páginas v1 eram relidas a cada acesso | a página em memória vale |
| `_arquivo_da_pagina` com docstring falsa | corrigida e o código também |
| `gc.freeze` escondido na fábrica do leitor | função nomeada, `congelar_para_a_coleta_de_lixo`, chamada pela janela ao abrir o projeto (e pelo teste de desempenho, como a janela), com `ABBY_SEM_CONGELAR=1` para o A/B; a docstring diz que congela tudo o que está vivo |
| A máquina de estados não via perda de decisão nem o caminho da janela | invariante de preservação (nenhuma edição perde decisão cujo glifo não tocou) e regras pela lista de `BoxEntry` + `reconciliar` (dividir, juntar, descartar, corrigir); dois mutantes conferidos (o `quebrar` antigo e uma reescrita que perde tudo) |
| CA-4.5 sem página nova antes da volta | teste: uma página v2 nova (pid ≥ 3) antes de copiar o backup; nenhum gid se repete e o contador cobre todos os arquivos |
| **O custo do modelo misturado com o congelamento** | A/B no commit final: 3 rodadas com e 3 sem o congelamento (`repeticao-1b` e `repeticao-1b_sem_congelar`). Pela mediana, o 1b sem congelar contra o 1a: Enter uns 7 ms e releitura uns 10 ms mais lentos (o custo da reconciliação); a troca uns 12 ms mais rápida (a página em memória). O congelamento não muda medianas; tira a faixa alta do p95 do Enter (~200 → ~135 ms). O p95 da releitura do 1b (152–158 ms) ficou pior que o do passo 0 e passou do alvo; o README o diz |
| O critério do 2a perdeu o sentido | refeito: medianas do Enter e da releitura de volta à faixa do passo 0 (o congelamento não muda medianas, então a comparação vale) e o p95 da releitura ≤ 150 ms |
| "Os p95 do 1b ficaram iguais ou melhores" era falso na releitura | corrigido no README |
| A volta pelo `backup-v1/` prometia demais | o README diz o que volta (páginas, áreas, `projeto.json`) e o que não (correções depois da migração, padrões, léxico, amostras de diagrama, inclinações), e recomenda copiar a pasta antes da primeira abertura |
| Menores | a migração avisa na barra de status; v1 em mídia só de leitura abre só para leitura; a janela ainda não mostra o estado (dito); a §4.4 da spec ganhou "reconhecida → verificada" e "marcar é edição"; a tabela das rodadas tem a mediana da releitura e explica o congelamento; `a.prof` saiu do git; as rodadas de antes das otimizações estão no commit `6d192c6` |

A qualidade e a fatia foram medidas de novo no commit final (`5f969c7`): iguais às do passo 0
nos três livros.

## Rodada 2

| Revisor | Notas | Veredito |
|---|---|---|
| Código e testes | Correção 7 · Simplicidade 7 · Testes 7 | volta |
| Produto e medição | Completude 9 · Fidelidade das medidas 7 · Clareza para o usuário 8 · Produtividade 8 | volta |

O que mudou depois dela:

| Achado | Correção |
|---|---|
| A reescrita pelos sucessores levava uma quebra e uma junção à mesma fronteira (glifos fundidos); a camada noturna (5.000 exemplos) derrubava a invariante | `reescrever` resolve o conflito: fica a junção, a quebra cai e vai para `caidas`; teste explícito da sequência; a camada noturna passa |
| `gid_do_box` gravava uma página de glifos marcados como "não reconhecida" | passa a "glifos marcados" |
| A busca pelos arquivos que o livro não cita rodava a cada acesso a página nova | uma varredura por sessão |
| **O congelamento piorava a releitura, e o texto dizia que não mudava medianas** | o teste congelava antes de criar a janela; o programa congela depois (com a janela e o projeto vivos), e o teste passou a fazer igual. O A/B foi refeito assim no commit desta rodada (`1df8980`, 3 rodadas com e 3 sem): as medianas não mudam; o p95 do Enter cai de ~200 para ~133 ms e o da releitura de 145–166 para 136–144 ms, dentro do alvo. O README diz isso e que o A/B anterior, na outra condição, dava o contrário na releitura |
| O critério do 2a se apoiava na premissa falsa | refeito: o 2a mede com e sem o congelamento; as medianas, pelas sem, contra o passo 0 (que não congelava); o p95 da releitura, pelas com, ≤ 150 ms, e o do Enter fora da faixa de ~200 |
| Menores | os JSON de desempenho registram quantos objetos estavam congelados; o teste de desempenho congela depois de criar a janela, como o programa; o aviso da migração é um diálogo (aparece uma vez, na abertura que migra), e o projeto v1 em mídia só de leitura diz por quê; a tabela "Desempenho por passo" diz que é a rodada do portão e remete às repetidas |

A qualidade e a fatia ficaram as do commit `5f969c7`: as correções desta rodada não
tocam o caminho da leitura nem o do texto sem decisões (os testes de caracterização e a
máquina de estados conferem).

## Rodada 3

| Revisor | Notas | Veredito |
|---|---|---|
| Código e testes | Correção 8 · Simplicidade 8 · Testes 8 | **aceita** |
| Produto e medição | Completude 9 · Fidelidade das medidas 7 · Clareza para o usuário 8 · Produtividade 8 | volta |

O bloqueio de produto: o teste congelava depois de ler três páginas, e o programa congela
antes de abrir qualquer uma (logo depois de carregar os modelos). O teste passou a congelar
no ponto do programa, a janela registra no log quantos objetos congelou, e o A/B foi refeito
no commit `1519d8f` (3 rodadas com e 3 sem). O resultado volta ao da rodada 2: o
congelamento tira a faixa alta do p95 do Enter (200–235 → 140–150 ms) e piora a releitura
(p95 154–159 ms com, 143–151 sem; a mediana uns 7 ms). O README declara a troca e por que
o congelamento ficou ligado; o A/B anterior, com as páginas congeladas, fica citado pelo
commit (`8277fa0`). O critério do 2a voltou a "o p95 da releitura não pior que o do 1b",
com o alvo de 150 ms no 2b. O custo do modelo, pelas rodadas sem congelamento contra o 1a,
é de uns 10 a 15 ms na mediana do Enter e da releitura; a troca, uns 10 ms mais rápida.

Os três testes que o revisor de código pediu como menores entraram: o estado
`glifos_marcados` gravado por `gid_do_box`, o motivo do só leitura em mídia sem gravação, e
o lote gravando enquanto a janela pede gids (duas threads).

## Rodada 4 (confirmação de produto)

Completude 9 · Fidelidade das medidas 8 · Clareza para o usuário 8 · Produtividade 8 —
**aceita**. Os menores dela entraram: a tabela "Desempenho por passo" diz por que a rodada do
portão não é a condição das repetições (congelou 270.070 objetos, contra 247.901, porque
roda depois dos testes `livro_real`); a legenda das rodadas tem as faixas de hoje; o alvo
de 150 ms da releitura está na verificação do 2b no roadmap. Fica registrado, sem medida:
o número de objetos que a janela congela (agora no log) não foi anotado ao lado dos do teste;
a equivalência vem do lugar da chamada.

**Fechamento.** As duas revisões aceitaram (código na rodada 3, produto na 4). A tag
`passo-1b` fica no commit que grava este registro. O desempenho final é do `1519d8f`; a
qualidade e a fatia, do `5f969c7` (o caminho da leitura não mudou depois, e os testes de
caracterização e a máquina de estados conferem).
