# Passo 2a — Controlador e gravador (§14.1, §4.3)

Ramo `passo-2a-controlador`, a partir da tag `passo-1b`.

## O que o passo fez

- **Controladores sem Qt.** `abbychess/controlador.py` (`ControladorDePagina`: a página
  aberta, a fila, os pulados, a seleção, o glifo em revisão e o desfazer, tudo por gid) e
  `abbychess/controladores.py` (áreas, verificação, diagramas e livro). A janela
  (`app/janela.py`, 446 linhas) só liga sinais a comandos e desenha o que os eventos dizem;
  as ações e menus foram para `app/acoes.py` e os diálogos para `app/dialogos.py`.
- **O adaptador de índices saiu da janela.** A janela não reconcilia mais uma lista de
  `BoxEntry` com o modelo: os comandos editam o modelo (`abbychess.edicao`). A
  reconciliação ficou só onde a página é relida inteira (F5 e lote), onde ela é a
  transferência dos gids (e das decisões) para os glifos do mesmo lugar.
- **Nada muda no lugar.** Uma edição troca o objeto `Box` (e o `BoxEntry`) e a lista; a
  leitura fora da interface trabalha sobre cópias (`edicao.copias_para_ler`) e o resultado
  entra só nos glifos que não mudaram enquanto ela rodava (`edicao.aplicar_leituras`).
- **Gravador assíncrono** (`abbychess/gravador.py`): uma thread, instantâneos imutáveis
  (`Pagina.instantaneo`, uma tupla por lista), coalescência de 500 ms a partir da primeira
  mudança, falha que deixa a página suja e tenta de novo com espera crescente, `fechar`
  que descarrega. O projeto é o dono dele (`ProjetoDeLivro.agendar`, `descarregar`,
  `fechar`); uma página com gravação pendente não sai do cache, e o resumo do livro mostra
  as páginas entregues e ainda não gravadas.
- **Ocupado visível.** O executor do Qt enfileira as tarefas (nunca ignora), a barra de
  status mostra a que roda e as que esperam. Cada tarefa tira o instantâneo do que precisa
  quando chega a vez dela (`preparar`), mas o que o usuário pediu (gids, caractere) é
  guardado na hora do comando. Durante o lote, editar a página é recusado com aviso.
- **O desfazer guarda o instantâneo do modelo**, sem cópia funda (a medida da memória do
  desfazer cai por isso; o desfazer do projeto com pré-condição por gid é do 2b).

## Decisões

| Decisão | Por quê |
|---|---|
| O lote continua gravando síncrono, na thread dele | o servidor de leitura (passo E) é quem tira o lote do processo da interface; até lá, o lote descarrega o gravador antes de começar e a edição da página é recusada enquanto ele roda, para não haver dois escritores da mesma página |
| A coalescência conta da primeira mudança, não da última | "100 mudanças em 400 ms geram 1 gravação" e a perda máxima numa queda fica limitada a 500 ms + t_fsync, como o CA-4.4 pede; um atraso que reinicia a cada mudança poderia nunca gravar numa sessão de digitação contínua |
| O painel de treino fica desligado enquanto uma tarefa roda | o Enter seguinte, antes do fim do anterior, ensinaria o mesmo glifo; o 2b separa a parte síncrona do Enter da propagação (§14.2) |
| `procedencia` com trava reentrante | a máquina de estados do controlador, com o rastreio do hypothesis, achou um travamento: o callback da referência fraca pega a trava, e a coleta de lixo pode chamá-lo dentro de `registrar`, na mesma thread |

## Verificação

- Suíte rápida, ruff, e a camada `processo` (`tests/test_gravador_processo.py`, as
  primeiras deste projeto): matar o gravador em 50 pontos (semente 2026) não deixa JSON
  inválido; com uma edição a cada 20 ms, ao reabrir estão todas as com carimbo ≤ T − 500 ms
  − t_fsync − 50 ms (a folga da volta da thread), em 3 tempos de vida; t_fsync medido
  (5,7 ms na máquina cadastrada).
- CA-4.2 (2a), CA-4.4 (sem o servidor): `tests/test_gravador.py`, `tests/test_janela.py`.
- CA-4.3 (2a): `MaquinaDoControlador` em `tests/test_modelo_estados.py` (mostrar, pular,
  selecionar, dividir, juntar, descartar, corrigir, marcar), com os invariantes de pulados,
  seleção e atual ⊂ vivos e o atual passando ao primeiro sucessor; conferida contra um
  mutante (o `_seguir` que não tira os aposentados dos pulados), pego em 4 s.
- CA-14.1: `tests/test_arquitetura.py` (menos de 500 linhas; closures da janela só chamam
  comandos de controlador, por AST, com o teste da própria regra; a lógica não importa Qt).

## Rodada 1

| Revisor | Notas | Veredito |
|---|---|---|
| Código e testes | Correção 5 · Simplicidade 7 · Testes 5 | volta |

O que mudou depois dela:

| Achado | Correção |
|---|---|
| **B1** A tarefa em voo (ou na fila) aplicava o resultado no projeto aberto depois, ou num projeto fechado | cada `ligar` muda a `geracao` do controlador; `tarefa()` não roda nem aplica o que é de outra geração; trocar de projeto e fechar a janela param as tarefas antes (`_parar_tarefas`); testes com um executor manual (resultado e fila do projeto anterior) e os dois mutantes conferidos |
| **M1** Edições usavam o leitor na thread da interface com uma tarefa usando o mesmo leitor | **toda** edição e todo comando que usa o leitor (esquecer, limiares, desfazer) é uma tarefa da fila; com o executor livre, roda na hora. Nenhuma edição acontece no meio de uma leitura |
| **M2** O `fsync` da página com a trava do livro fazia a interface esperar o disco | o arquivo da página é gravado sem trava (só o gravador grava o que a interface edita); a trava do livro vale só para o `livro.json`; uma trava curta separada (`_trava_do_cache`) protege o cache, e `agendar`, `carregar_modelo` (no cache) e `resumo_do_livro` não pegam mais a trava do livro |
| **M3** A leitura dos diagramas aplicava na página aberta, não na que pediu | `preparar` guarda a página, e o `pronto` aplica nela; a conferência só abre se ela ainda é a aberta |
| **M4** A correção de palavra com ensinar mudava o modelo antes da vez e podia não gravar | a correção é uma tarefa: na vez dela troca os glifos, registra o passo e grava; o ensino que vem dela é a tarefa seguinte, emendada no mesmo passo do desfazer (chave única do comando) |
| **M5** O aviso de falha ao fechar mostrava `[]` e fechava mesmo assim | `ProjetoDeLivro.paginas_sujas()` (os índices) e `nao_gravadas`; fechar a janela (ou trocar de projeto) com página que não grava pergunta, e "Não" deixa a janela aberta; teste |
| m1 O lote começava sem o gravador descarregado | não começa, com aviso |
| m2 Um aviso que falhasse matava a thread do gravador | os avisos são protegidos |
| m3 Editar durante o F5 | não acontece mais (M1) |
| m4 O lote mudava no lugar a página que a interface mostra | `salvar_pagina` trabalha numa cópia rasa, que entra no cache; a janela confere se o glifo em revisão ainda existe (`box_atual`) |
| m5 Restos do adaptador | a foto (`_estados`) não é mais calculada para as páginas do gravador; a docstring de `reconciliar` diz onde ela vale agora (F5, lote, listas); `gid_do_box` fica para as ferramentas (o `replay_fatia` ensina por listas) |
| m6 Uma tentativa por edição com a página falhando | piso de `atraso` depois da última falha |
| m7 O CA-14.1 só olhava a janela e só as chamadas | também as lambdas de `app/acoes.py`, e as closures da janela não podem ter atribuição nem controle de fluxo |
| m8 Testes dependentes de tempo e um `print` | o de 100 mudanças espera ativamente (o `sleep` do Windows dorme ~15 ms); o que confere "ainda não gravou" usa atraso de 30 s; o `print` saiu |
| Falta de teste de `aplicar_leituras` e de tarefa em voo | `tests/test_controlador.py`; a máquina do controlador ganhou ensinar, reler, desfazer e refazer |

Um achado novo, das próprias correções: uma tarefa pedida de dentro de outra (esquecer →
reler; corrigir → ensinar) entrava de novo no laço do executor e apagava a referência da
tarefa que já rodava; o executor agora só enfileira enquanto está no laço ou num `pronto`
(teste). Sobre conferir um diagrama numa página verificada: ela volta a "em revisão", como
qualquer edição (§4.4); as áreas e o "reler" continuam fora do desfazer (o desfazer do
projeto é do 2b).

## Rodada 2

| Revisor | Notas | Veredito |
|---|---|---|
| Código e testes | Correção 8 · Simplicidade 7 · Testes 7 | volta |

Confirmou B1 e M1–M5 resolvidos e a ordem das travas sem ciclo. O que mudou depois dela:

| Achado | Correção |
|---|---|
| **M6** A foto (um hash por glifo) voltava a ser calculada na thread da interface na primeira edição depois de cada gravação | a página entregue por `agendar` entra no cache sem foto (`foto=False`), e a foto que houver é descartada; só as gravações síncronas (lote, ferramentas) a mantêm |
| m9 `lote_rodando` podia ficar preso depois de trocar de projeto | `ligar` o zera, e o controlador do livro zera o pedido de cancelar |
| m10 O resumo podia mostrar a versão velha de uma página entre duas leituras | lê os pendentes antes do livro |
| m11 Fechar parava as tarefas antes de perguntar | pergunta antes; parar as tarefas vem depois do "sim" (e o fim da tarefa em voo ainda entra) |
| m12 Um `stat` dentro da trava do cache | fora das travas |
| m13 Um `rodar` pedido por quem ouve "livre" ficava parado | o laço do executor confere a fila depois de avisar |
| Testes que faltavam | a interface não espera o `fsync` do livro (gravador preso); aviso do gravador que falha; o piso das tentativas; `salvar_pagina` não muda a página mostrada; diagramas lidos entram na página que pediu; corrigir e ensinar uma palavra é um passo só do desfazer; o lote não começa sem descarregar; trocar de projeto solta o lote; trocar de projeto pela janela com F5 em voo termina no projeto dele; na máquina do controlador, desfazer logo depois de corrigir, descartar ou juntar volta os mesmos `Box`, o estado e as decisões |

Ficam, de propósito: `gid_do_box` e o `gid=None` de `pagina.ensinar` (o `replay_fatia`
ensina por listas de `BoxEntry`), e `Instantaneo.boxes` (o que os testes do desfazer leem).

## Rodada 3

| Revisor | Notas | Veredito |
|---|---|---|
| Código e testes | Correção 8 · Simplicidade 8 · Testes 8 | **aceita** |

Os menores dela entraram antes das medidas: fechar pergunta de novo depois de parar as
tarefas, pelo que a tarefa em voo entregou (m14, teste); a docstring de `salvar_pagina` diz
que a mudança no lugar não é vista numa página sem foto (m15); testes de que `agendar` não
calcula a foto e de que uma tarefa pedida por quem ouve "livre" roda (m16). Os resíduos
(m17) ficam como registrado na rodada 2.

## Medidas (commit `d19c858`)

- Portão (`ABBY_PORTAO=1 -m "livro_real or desempenho"`): 8 passaram;
  `docs/medidas/2026-10-16-passo-2a.json`.
- Rodadas repetidas: 3 com o congelamento (`repeticao-2a`) e 3 sem
  (`repeticao-2a_sem_congelar`). O critério do roadmap passa nas 3 de cada lado: sem
  congelar, a mediana do Enter (82 ms) e a da releitura (71–75 ms) ficaram abaixo da faixa do
  passo 0 (104–105 e 106–108); com o congelamento, o p95 da releitura (86–106 ms) ficou
  abaixo do do 1b (154–159) e o do Enter (90–116) longe da faixa de ~200. O alvo de 150 ms
  do p95 da releitura, que era do 2b, já foi alcançado.
- A memória do desfazer estimada (300 × 20) caiu de 4.121 MB para 164 MB.
- Qualidade (`medir.py`, os três livros) e fatia (`replay_fatia.py --passo 2a`): iguais às
  do 1b; só o tempo do lote difere (xv 435 → 460 s, yusupov 23,3 → 24,4, darcy 23,7 → 25,5),
  uma rodada de cada, sem repetição.
