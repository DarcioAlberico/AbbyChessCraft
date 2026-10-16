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

Com isso (rodadas completas, tabela "Rodadas repetidas" do README): o p95 da releitura do
1b ficou em 143–151 ms (1a: 141–165), o p95 do Enter em ~133 ms (1a: ~191; o congelamento
tirou a faixa alta) e a mediana da troca de página abaixo das do passo 0 e do 1a. O que o
modelo ainda custa é uns 10 ms na mediana da releitura (~123 contra ~111) e do Enter (~121
contra ~114). O congelamento também ajudaria o código de antes: a comparação com o 1a é
honesta sobre a mediana, não sobre o p95.
