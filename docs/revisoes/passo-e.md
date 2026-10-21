# Passo E — Servidor de leitura (§11, §4.6)

Ramo `passo-e-servidor`, a partir da tag `passo-a3` (6388b28).

## O que o passo fez

- **O servidor de leitura** (`abbychess/servidor_de_leitura.py`): um processo filho com
  `spawn`, aberto com o projeto, guarda os modelos globais e atende toda leitura que não sai
  dos padrões do livro. Prioridade abaixo do normal e `torch.set_num_threads(núcleos − 2)`.
  Duas prioridades (interativo e lote) e a vez entre um glifo e outro do lote
  (`_ler_com_vez`): um F5 ou uma releitura passa na frente da próxima página do lote, e o
  cancelamento para a página no glifo seguinte. Os deltas dos padrões (`incluir`/`excluir`,
  sem gravar) valem a partir do pedido seguinte. Se o filho cai, é aberto de novo uma vez e
  os pedidos pendentes são reenviados; na segunda queda, desiste. `fechar`: `join(5)`, depois
  `terminate`. A fábrica de leitor é importável por caminho (o leitor falso dos testes).
- **A janela lê pelo servidor**: o F5, o Reler pendentes, os diagramas e as áreas
  automáticas. A interface fica só com os padrões do livro (`LeitorDoLivro(aguardar=True)`):
  o glifo que eles não leem fica "aguardando leitura" e vai ao servidor só como recorte; a
  resposta entra nos glifos que não mudaram e emenda a transação da edição. Antes de cada
  pedido, os padrões criados e apagados vão ao filho (`_sincronizar_padroes`).
- **A abertura** não espera os modelos: o projeto abre, a barra diz que eles estão
  carregando, e `modelos_prontos` chega quando o filho termina (o aviso da rede ausente vem
  dele). A primeira queda vai aos Avisos; na segunda a janela oferece reabrir o projeto.
- **O lote pelo servidor** (`abbychess/lote.py`, `CondutorDoLote`), com a interface como
  escritor único: decide (a verificada é pulada sempre; a já lida, sem "refazer"; a página
  aberta com passos no desfazer fica para "reler depois"), prepara o que fica (§4.6), lê (no
  servidor, numa thread; sem ele, numa tarefa do executor) e grava na thread da interface,
  conferindo o conflito de novo. O "refazer" guarda a página de antes em
  `paginas/.antes-do-lote/p<pid>.json`, e **Página › Voltar ao estado antes do lote** a
  devolve idêntica. Cancelar pelo ✕; **Retomar o lote** continua de onde parou. O progresso
  vai à gaveta e à barra, com o tempo estimado.
- **Nada é recusado durante o lote**: editar, o F5, o desfazer, esquecer padrões e as opções.
- **§4.6 no F5 e no lote**: reconhecer de novo mantém os glifos `manual` e `revisado`
  (`pagina.a_manter_na_releitura`); o caminho síncrono das ferramentas (`livro.py`) também.
- **A guarda do `__main__`**: o filho importa o módulo principal como `__mp_main__`, e sem a
  guarda abriria outra janela.

## Decisões

| Decisão | Por quê |
|---|---|
| "Aberta e suja" é a página aberta com algum passo dela no desfazer ou no refazer | toda edição, F5 e desfazer passa por lá; sobrescrevê-la faria o Ctrl+Z dela ser recusado. A gravação pendente sozinha não conta: pode ser a do próprio lote |
| O lote não entra no desfazer; a página de antes vai para `.antes-do-lote/` | §4.6: seria grande demais para o histórico |
| A releitura de um glifo manda o recorte, não a página | a página (~9 MB) pela fila custaria mais que a leitura; o recorte e a altura de referência bastam |
| Os pedidos do F5 e do reler esperam o servidor dentro de uma tarefa do executor | a ordem das tarefas e o descarte por projeto (`geracao`) continuam os de sempre |
| Sem servidor (`ABBY_SERVIDOR=0`), o lote lê numa tarefa do executor por página | o leitor da interface é de uma thread por vez; a edição pedida no meio espera a página |
| O lote para quando o servidor desiste | as páginas seguintes falhariam todas; o que faltou fica para retomar depois de reabrir |
| O que não pôde seguir os glifos relidos (§4.6) vai aos Avisos, e não a uma lista própria em Resultados | Resultados e Avisos são o mesmo painel (A2); a lista que abre a página é do passo B, com a busca |
| Reconhecer o livro fica em Ferramentas e também no menu Projeto, com Cancelar e Retomar | a §11 pede Cancelar em Projeto; os três juntos ali, e o Reconhecer onde sempre esteve |
| `livro.reconhecer_paginas` roda o mesmo condutor, com um controlador sem janela | as regras do lote (verificada, §4.6, `.antes-do-lote`) não divergem entre a janela e as ferramentas; o laço não se aninha, para centenas de páginas no executor síncrono |
| O glifo "aguardando" lido sem a transação de origem entra fora do desfazer | não é decisão de ninguém; a pré-condição do desfazer aceita o aguardando lido depois (`historico.lido_depois`), e o refazer de outra página não se perde só por abrir uma página |

## Verificação

- Suíte rápida: 702 testes em 54 s; ruff limpo; camada `processo`: 24.
- `tests/test_laco.py` (rápido): o laço do filho numa thread com filas comuns: a vez entre
  glifos (o interativo começa e termina dentro da página do lote), os deltas, o cancelamento
  que sempre responde, a operação que falha, a guarda do `__main__`.
- `tests/test_lote.py` (rápido, sem servidor e com o servidor falso de
  `tests/servidor_falso.py`): CA-11.4, CA-8.5, CA-11.5, CA-4.8 (a parte do lote, com a
  página aberta mostrando a de antes e o Ctrl+Z recusado), a verificada e a corrigida
  durante a leitura, a procedência na volta, o aguardando no refazer e ao abrir, o servidor
  parado, o projeto só de leitura, 252 páginas no executor síncrono.
- `tests/test_servidor.py` e `tests/test_servidor_janela.py` (`processo`, o filho de
  verdade com o leitor falso): ler, deltas, CA-11.8, cancelar (também antes do pronto), a
  queda e a desistência, fechar sem órfão, o filho sem o Qt; na janela, a abertura, o F5,
  o aguardando, CA-11.1 e CA-11.2, CA-11.3, CA-11.4, o lote que para quando o servidor
  desiste, a procedência do padrão, CA-11.7 sem servidor pronto, o `livro.json` (CA-4.4).
- `tests/desempenho/test_servidor.py`: CA-11.1, CA-11.6 e CA-11.7 com o leitor real.

## Rodada 1 (código)

| Revisor | Notas | Veredito |
|---|---|---|
| Código e testes | Correção 5 · Simplicidade 7 · Testes 6 | volta |

| Achado | Correção |
|---|---|
| **G1** Cancelar um pedido do lote que ainda não começou o tirava da fila sem resposta: o lote ficava preso (o ✕ com os modelos carregando, ou durante um F5) | o pedido fica na fila e responde "cancelado" na vez dele; a thread do lote espera em voltas e desiste em 30 s; o teste que confirmava o defeito foi invertido, e há um com o filho de verdade |
| **G2** A regra de conflito só olhava a página aberta na hora de gravar: o Ctrl+T durante a leitura (que abre a seguinte) e a correção numa página deixada eram sobrescritos | uma versão de cada página no desfazer; o condutor a guarda ao pedir e reconfere ao gravar (a verificada é pulada, a mudada vai para "reler depois"); os dois cenários testados pelo caminho do servidor |
| 1 | Voltar ao estado antes do lote recusa o projeto só de leitura e o gravador que não descarrega |
| 2, 3 | o aguardando que volta por desfazer/refazer é lido; abrir a página com aguardando não cria transação (fora do desfazer, com a pré-condição tolerante) |
| 4, 5 | o servidor parado avisa nos comandos que leem; o Cancelado é silencioso; os pedidos da janela têm prazo; fechar abandona os pendentes antes de esperar a fila; os aguardando não passam mais pela fila de tarefas |
| 6–9 | o `desistiu` da hora do aviso; fechar e a queda na mesma trava; o "sair" para a página do lote; os cancelamentos não ficam guardados |
| 10 | o lote síncrono é o mesmo condutor; a procedência num lugar só; `CANCELADO` no lugar da string |
| 11 | os testes da vez entre glifos (pelo fim), da procedência, do CA-11.7 sem pronto e do CA-4.8 mais fortes |

## Rodada 2 (código)

Correção 8 · Simplicidade 8 · Testes 8 — **aceita**. Os menores que ela achou entraram
(`5ba8ba0`): o aguardando é pedido também com o servidor reabrindo; o fechamento desistido
devolve os aguardando abandonados; voltar ao antes do lote sobe a versão da página (e acha a
cópia logo depois do lote); o lote sem cancelamento tem o prazo dos pedidos; o teste do
laço síncrono (que falha com a versão recursiva).

## A primeira bateria (commit `5ba8ba0`)

Portão e 3 rodadas com a linha de base ainda **sem** o servidor (os modelos na janela do
teste), renomeadas para `docs/medidas/2026-10-17-primeira-rodada-e*.json`: o atraso no lote
já em p99 de 2,2 ms, a releitura com o lote em p95 de 78–103, a memória somada em 2173–2177
(inflada pelos modelos que a linha de base carregava no processo de teste), o lote em 163 s
(o projeto sem padrões; sem servidor, as mesmas páginas levaram os mesmos 8,1 s, numa medida
à parte que a revisão de produto pediu em JSON). Uma segunda bateria, sobre o `ea6a19d`, foi
parada no meio pela rodada 3 de código (descartada), e uma terceira, sobre o `567c6e8`, achou
a releitura com o lote em p95 de 205 ms numa das 4 medidas (a segmentação da página do lote
não dava a vez) e foi descartada depois da correção.

## Revisão de produto, rodada 1

| Revisor | Notas | Veredito |
|---|---|---|
| Produto, design e medição | Completude 6 · Fidelidade das medidas 5 · Clareza 6 · Produtividade 7 · Design 7 | volta |

| Achado | Correção |
|---|---|
| **M1** Retomar não funcionava depois de o servidor desistir (o "Sim" de reabrir zerava o restante; o "Não" falhava em laço) | o que falta fica em `lote.json` e volta ao reabrir; Retomar desligado com o servidor parado; a queda não conta como falha (`servidor_parou`) |
| **M2** A pergunta do lote dizia que "Sim" descarta as correções | o texto do §4.6 e as verificadas contadas à parte |
| **M3** A §4.6 pela metade: sem a transferência por IoU ≥ 0,6 nem a lista em Resultados | `reconciliar(iou_minimo=0,6)` no F5 e no lote; o que caiu vai aos Avisos; teste com o glifo que muda 2 px |
| **M4** A linha de base media sem o servidor | ela abre o projeto com o servidor, como o programa; o JSON diz a configuração |
| **M5** Números sem JSON: o lote com e sem servidor, o pico na gravação, a qualidade pelo filho | `lote_com_e_sem_servidor`, `maior_atraso` com a gravação mais perto, `gravar_pagina_do_lote`, e um teste `livro_real` de que o filho lê como o processo |
| m1–m14 | a memória sem os modelos do módulo anterior; as rodadas na condição real; as faixas do README; os campos velhos dos JSON; o lote com o leitor falso; o traço-ponto; o rótulo do lote com um dono só; Cancelar e Retomar no menu Projeto; a data da cópia de antes do lote; Retomar e reler depois guardados no projeto; o tempo de gravar medido; a barra de carregamento dos modelos; abrir sem servidor quando os modelos não carregam; a mensagem do fim curta, com o detalhe nos Avisos |

## Rodadas 3 a 5 (código, sobre as correções do produto)

Rodada 3: Correção 7 · Simplicidade 8 · Testes 7 — volta: fechar com o lote ativo não
atualizava o `lote.json` (e o de um lote anterior voltaria). Agora ele é gravado ao começar
o lote e a cada página; as páginas para reler depois ficam numa lista à parte, e Retomar só
as lê com a confirmação; "abrir sem servidor" é uma opção da sessão; o motivo vazio; Retomar
desliga com o servidor parado; as decisões que caem dizem o glifo, e não o gid (`aae64c8`).

Rodada 4: Correção 8 · Simplicidade 8 · Testes 8 — **aceita**, com menores que entraram
(`567c6e8`): Retomar força as páginas confirmadas uma a uma, sem mudar o "refazer" do que
faltou; só os números que são glifos viram descrição; o diálogo sem nada que tenha faltado;
o F5 e o Ctrl+T tiram a página da lista.

Rodada 5 (sobre a página do lote numa thread do filho, `6c61ed7`): Correção 8 · Simplicidade
8 · Testes 8 — **aceita**; os menores entraram (`9c759e2`): o acordar perdido (o laço olha o
`no_lote`, e não o `is_alive()`), o cancelar tardio, o que não é recebido durante um F5 na
docstring, e o teste do cancelar e do sair no meio da segmentação.

## As medidas finais (commit `9c759e2`, pasta limpa)

- Portão: 20 passaram; `docs/medidas/2026-10-17-passo-e.json`.
- 3 rodadas (`repeticao-e`), na ordem, e o portão por último entre colchetes:
  - atraso no lote: p99 2,2; 2,2; 2,2 [2,2] ms, máximo 136,8; 134,4; 137,1 [132,3], a
    ~0,13 s de uma gravação de página;
  - atraso no lote com o leitor falso (51 páginas): p99 7,6; 12,8; 9,0 [14,1];
  - gravar uma página do lote na janela: p95 21,9; 22,1; 19,5 [17,6];
  - releitura com o lote: mediana 41,7; 40,4; 41,0 [46,1] e p95 105,3; 64,4; 66,0 [124,1]
    (alvo 150);
  - releitura sem o lote (pelo servidor): mediana 39,0; 38,7; 39,0 [37,0];
  - memória somada com o lote: 2028; 1959; 2027 [2050] MB (servidor ~1010);
  - lote de 20 páginas: 162,4; 162,7; 163,3 [161,3] s; com e sem servidor, as mesmas 5
    páginas: 8,17/8,23; 8,21/8,24; 8,16/8,21 [8,33/8,26] s por página;
  - Enter até a cor: mediana 23,9; 23,9; 24,0 [23,9]; troca no cache 14,5; 14,4; 14,6;
    fora do cache 134,0; 134,1; 133,4; montar o Documento p95 31,8; 33,5; 32,4 [39,8];
    clique no Documento p95 3,4; 3,3; 3,3.
- Qualidade (`medir.py`, os três livros) e fatia (`--passo E`): iguais às do A3.

## Revisão de produto, rodada 2

Completude 8 · Fidelidade das medidas 8 · Clareza para o usuário 8 · Produtividade 8 ·
Design 8 — **aceita**. Dos menores, entraram depois das medidas (só textos e os Avisos do
fim do lote, fora do caminho medido): a frase do fim depois da queda, os Avisos só com o que
há a conferir e as páginas em faixas, Reconhecer o livro também no menu Projeto; no README,
a leitura do pico do atraso (ele começa na volta de cada página), a memória dita como
explicação provável e o tempo da suíte (58–59 s). Ficam pendentes: tirar da thread da janela
o que a volta de cada página faz além de gravar (~115 ms; para o D1, que edita durante o
lote); a memória com o módulo do servidor sozinho em 3 rodadas; a posição das caídas que
abre o glifo (passo B); o resumo do lote interrompido nos Avisos quando o usuário reabre o
projeto na hora (o `lote.json` fica certo).

**Fechamento.** As duas revisões aceitaram: código na rodada 5 (a 4 aceitou o resto), produto
na 2. A tag `passo-e` fica no commit que grava este registro. As medidas de desempenho são as
3 rodadas e o portão do `9c759e2`; a qualidade e a fatia, do mesmo commit.
