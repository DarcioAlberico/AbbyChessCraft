# AbbyChessCraft — spec de qualidade (análise ub-mode de 2026-10-30)

Versão 0.1, sobre o commit `4accb7f` (ramo `passo-i-treino`). Complementa a `docs/SPEC.md`
(v0.4): não pede função nova, pede que o que já existe não perca dado, não esconda erro e
caiba na cabeça de quem mexe. O plano de execução está em `plans/roadmap-qualidade.md`.

## 0. Como ler

- Cada problema tem um id (`Q-P1`, `Q-E2`…), a evidência (arquivo:linha no `4accb7f`), o
  risco e um **critério de aceitação** (`CA-Q…`) que vira teste antes da correção.
- **Confirmado** = li o código e o defeito está lá. **Suspeita** = o caminho existe no código,
  mas falta o teste que reproduz; o primeiro passo é esse teste, e se ele não falhar o item
  sai da spec.
- Severidade: **Alta** = perde ou corrompe dado do usuário, ou esconde o erro que perdeu;
  **Média** = uma decisão em vários lugares, uma corrida possível, uma fronteira aberta;
  **Baixa** = custo de manutenção.

## 1. Linha de base medida

| Medida | Valor no `4accb7f` | Como |
|---|---|---|
| Suíte rápida | 1839 passaram, 3 pularam, 0 falharam | `pytest -q -n 4 --cov=abbychess` |
| Tempo da suíte rápida com cobertura | 100 s (a meta da §15.1 é < 60 s sem cobertura) | idem |
| Cobertura de linhas (só a suíte rápida) | 90 % (22 110 linhas, 2 137 sem cobertura) | `coverage.json` |
| Funções | 2 089 | `ferramentas/crapper.py` |
| Funções com CRAP ≥ 10 | 301 (251 só pela complexidade, cc ≥ 10; 45 com cobertura < 50 %) | `docs/medidas/qualidade/crap-4accb7f.txt` |
| Pares de funções com forma ≥ 0,8 | 16 | `docs/medidas/qualidade/duplicacao-4accb7f.txt` |
| Portão `ruff --select E,F` | **reprova**: 3 F401 em `camada.py:23,28` (desde `a973d3b`) | contrato do roadmap |
| `ruff` com B, BLE, S110, SIM, PERF | 11 `except Exception` cegos, 2 `except: pass`, 7 propriedades lidas pelo efeito (B018) | — |
| Teste de mutação | não medido: nenhuma ferramenta instalada (§9) | — |

A tabela acima usa só a cobertura da suíte rápida. A **linha de base do Q0** soma a camada
`processo` (`ferramentas/qualidade.py`, no `3e2fc4d`, que só muda ferramentas, testes delas
e o `.gitignore` em relação ao `4accb7f`):

| Medida | Valor no `3e2fc4d` | Arquivo |
|---|---|---|
| Suíte rápida | 1844 passaram, 3 pularam, 93 s com cobertura | `docs/medidas/qualidade/2026-10-30-qualidade.json` |
| Camada `processo` | 35 passaram, 222 s com cobertura (o teto de 60 s sobe a 600 só na medida: a matança do gravador abre 50 filhos, todos medidos) | idem |
| Cobertura combinada | 91,7 % (22 109 linhas, 1 826 sem cobertura) | idem |
| Funções com CRAP ≥ 10 | 286 (251 só pela complexidade; 29 com cobertura < 50 %) | `docs/medidas/qualidade/crap-3e2fc4d.txt` |
| Pares com forma ≥ 0,8 | 16 | `docs/medidas/qualidade/duplicacao-3e2fc4d.txt` |
| Portão `ruff --select E,F` | passa | — |

Dos 45 casos de cobertura baixa da análise, 16 eram só a camada `processo` que não entrava na
conta (o servidor de leitura: `_caiu`, `fechar`, `_abrir`, `esperar`; o lote na janela;
`_renderizar_no_filho`; `PoolDoIndice._abrir`). `ServidorDeLeitura._ouvir` cai de 219 para
20,5 (71 % coberta) e `RenderEmProcesso.renderizar` de 102 para 10. Os 29 que sobram são falta
de teste de verdade, a começar por `epub.calibre` (567, 12 %: o Calibre só roda com
`ABBY_CALIBRE`), `ControladorDaFila._outra_pagina_das_palavras` (104, 8 %), `camada.palavras`
(49, 5 %) e `VisorDePagina._cursor_das_bordas` (47, 7 %). Daqui em diante, o CRAP de cada
passo é medido com `ferramentas/qualidade.py`.

Os módulos com menos cobertura na suíte rápida: `render.py` 36 %, `app/principal.py` 38 %,
`app/lote_na_janela.py` 44 %, `servidor_de_leitura.py` 55 %, `camada.py` 74 %,
`app/dialogos.py` 74 %.

## 2. Princípios desta spec

1. **Primeiro o teste que falha.** Cada `CA-Q` vira um teste que reprova no `4accb7f` pelo
   motivo esperado; só então a correção, a menor que o faz passar.
2. **Uma decisão mora num lugar só.** A duplicação de regra é tratada como defeito, não como
   estilo.
3. **Validar na entrada, confiar dentro.** O JSON do disco e as respostas do core são lidos e
   validados uma vez; o domínio recebe valores que já valem.
4. **Um escritor por arquivo, imposto pela estrutura**, não pela disciplina de quem chama.
5. **Nenhum erro some.** Toda exceção capturada vai ao log com o rastro e, se mudou o estado
   do usuário, aparece para ele.
6. **Tirar antes de pôr.** Código morto sai antes da refatoração que o tocaria.

## 3. Persistência e modelo

### Q-P1 (Alta, confirmado) — a página v1 é procurada pela posição, não pelo pid

- **Evidência:** `projeto.py:988-990` (`_tem_v1(indice)`) e `projeto.py:1009-1028`
  (`_ler_v1(indice)`) usam a posição no livro; na v1 o número do arquivo é a página do PDF,
  que é o pid. `carregar_modelo` (`projeto.py:646-672`) chama os dois pela posição. A v3
  deixa reordenar com páginas v1 ainda não migradas.
- **Risco:** depois de mover uma página, os glifos de outra são lidos, gravados e postos no
  cache com o pid errado.
- **CA-Q-P1:** num projeto v1 com duas páginas não migradas, trocar as duas de lugar e abrir
  cada uma mostra os glifos do seu próprio pid, antes e depois de fechar e reabrir.
- **Correção mínima:** `_tem_v1`/`_ler_v1` por pid; ou `migrar_tudo()` dentro de
  `_migrar_para_v3`, para que a v3 nunca conviva com v1 pendente (preferível: tira a v1 do
  caminho de leitura, §3 Q-P8).
- **Feito** no Q1 (`92f7a79` o teste, `7eedd90` a correção), pela decisão §13.1: a v1 migra
  inteira na abertura, pelo pid; só para leitura ela fica na memória, também por pid, e a
  leitura das páginas não conhece mais a v1.

### Q-P2 (Alta, confirmado) — um arquivo v1 que sobrou regrava a página vazia

- **Evidência:** `_tem_v1` é verdadeiro com `paginas/NNNN.json` **ou** `zonas/NNNN.json`
  (`projeto.py:989-990`); `_migrar` (`projeto.py:1030-1040`) grava a v2 e apaga os dois com
  `gv.apagar`, que não tenta de novo em `PermissionError` (o `gravar_bytes` tenta). Se só o de
  zonas sobra, a próxima leitura remigra uma página sem boxes por cima de `p<pid>.json`.
- **CA-Q-P2:** com o apagar do arquivo de zonas falhando uma vez (injetado), a página
  migrada continua com todos os glifos depois de reabrir.
- **Correção mínima:** apagar primeiro o v1 de zonas e por último o de página (o de página
  marca "migrada"); `apagar` com as mesmas novas tentativas de `gravar_bytes`.
- **Feito** no Q1 (`0c99af5`, `499aff4`), por outro caminho: nenhuma ordem de apagar é
  segura sozinha (sobrar o de página perde as áreas). Vale como página o arquivo v1 cujo pid
  ainda não tem o `p<pid>.json`, ou todos quando o `projeto.json` é o da v1 (CA-4.5); o resto
  é sobra e sai. A falha de apagar fica no log e não derruba a abertura para só leitura.
  Antes, fora do pytest, a cena perdia os 15 glifos da página 0.

### Q-P3 (Alta, confirmado no Q1) — a página aberta pode sair do cache durante o lote

- **Evidência:** o LRU de 16 páginas (`projeto.py:747-755`) só poupa as sujas; `lote.py:381`
  e `421` comparam `pagina is p.modelo`.
- **Risco:** um lote de mais de 16 páginas despeja a aberta; o lote grava num objeto novo, a
  janela segue editando o velho e a próxima gravação apaga a leitura do lote.
- **CA-Q-P3:** com a página 0 aberta e limpa, um lote de 20 páginas sintéticas que inclui a 0
  termina com a leitura do lote visível na janela e no disco, e uma edição seguinte não a
  apaga.
- **Correção mínima:** `projeto.fixar(pid)` para a página aberta.
- **Feito** no Q1 (`b1bd35d`, `b26f117`): o teste (o cache de 1 e o lote de 3) confirmou a
  suspeita; com o cache de sempre o mesmo teste passava. O `modelo` do controlador virou
  propriedade, e trocar a página aberta chama `projeto.prender(pid)`.

### Q-P4 (Média, confirmado) — o escritor único de `p<pid>.json` é convenção

- **Evidência:** o gravador grava sem `_trava_do_livro` (`projeto.py:456-462`);
  `salvar_modelo`, `gid_do_box` e `salvar_zonas` gravam o mesmo arquivo com ela
  (`712-718`, `794-803`, `954-963`); o `.tmp` tem nome fixo (`gravacao.py:84-87`). O comentário
  de `projeto.py:234` ("o lote grava de outra thread") contradiz `lote.py:13`.
- **CA-Q-P4:** duas gravações da mesma página disparadas ao mesmo tempo (gravador e
  `salvar_modelo`, com uma barreira) deixam no disco um JSON válido igual a uma das duas, em
  500 repetições.
- **Correção mínima:** `salvar_modelo` passa pelo gravador (`agendar` + `descarregar`);
  temporário com sufixo único.
- **Feito** no Q1 (`d9f2121`, `0cea755`), por outro caminho: passar pelo gravador tiraria o
  erro de quem grava em síncrono, e o sufixo único não resolve a ordem. Cada conteúdo ganha um
  bilhete quando é fotografado, toda gravação do arquivo passa por um lugar só, uma por vez,
  e o arquivo nunca recebe um bilhete mais velho que o último. O teste força a ordem ruim (o
  gravador preso com o instantâneo velho) em vez de 500 sorteios, e passou 10 vezes seguidas.

### Q-P5 (Média, confirmado) — nada impede dois processos no mesmo projeto

- **Evidência:** nenhuma trava entre processos; `limpar_temporarios`
  (`gravacao.py:151-157`) apaga o `.tmp` em curso do outro.
- **CA-Q-P5:** abrir o mesmo projeto num segundo processo o abre só para leitura, com aviso.
- **Feito** no Q6 (2026-10-31, `126e132`): `gravacao.tomar_a_pasta` trava a `projeto.lock` (msvcrt ou flock, um byte longe do conteúdo); sem ela, `abrir` abre só para leitura com o motivo, antes de criar pasta ou limpar temporário.
- **Correção mínima:** `projeto.lock` com `msvcrt.locking` (ou `O_EXCL` com o pid) em `abrir`.

### Q-P6 (Média, confirmado) — `projeto.json` validado pela metade

- **Evidência:** `"limiares": 5` levanta `AttributeError` em `_separar`; `proximo_pid: "12"`
  só estoura no meio de uma edição; o `ValueError` da sequência na migração escapa porque só
  `OSError` é tratado (`projeto.py:313-327`, `376`).
- **CA-Q-P6:** para cada campo de `projeto.json`, um valor do tipo errado ao abrir dá
  `ProjetoInvalido` com o nome do campo, e nada é gravado (teste parametrizado, ou hypothesis
  sobre o JSON).
- **Feito** no Q6 (`5eff49a`): `TIPOS_DO_PROJETO`, `TIPOS_DOS_LIMIARES` e `_conferir_tipos`; o erro diz o campo e nada é gravado (21 casos).
- **Correção mínima:** uma função de entrada que valida os tipos de `Projeto` e `Limiares`.

### Q-P7 (Média, confirmado) — a página ilegível é tratada de três jeitos

- **Evidência:** `carregar_modelo` levanta (`projeto.py:670`); `ler_sem_guardar` e
  `ler_sem_migrar` devolvem `None` em `ValueError` (`603`, `943`), e a busca e a aba
  Diagramas pulam a página em silêncio; `_orfaos` e `recalcular_livro` capturam outro conjunto
  de exceções. O comentário de `projeto.py:1127` diz que um `inclinacoes.json` ilegível é
  ignorado, mas `pagina.py:139-141` levanta.
- ~~**CA-Q-P7:** um `p<pid>.json` truncado aparece como "página ilegível" na busca, nos
  Diagramas e no relatório da exportação, nunca como "não reconhecida".~~
- **CA-Q-P7 (revisto no Q2):** um `p<pid>.json` truncado, na primeira leitura, vai inteiro
  para `p<pid>.corrompido.json` e sai do `livro.json`; a página é não reconhecida para todos
  (a busca, a aba Diagramas, a janela, a exportação), abrir a página não levanta, e o aviso
  diz qual e onde ficou o arquivo, uma vez. Um estado "ilegível" novo passaria por toda a
  máquina de estados e por três telas; assim nada nasce, o arquivo não se perde, e é a mesma
  regra dos metadados dos padrões.
- **Feito** no Q2 (`b1f609f` o teste, o commit seguinte a correção): `_gravada` lê a página
  por um caminho só, com um conjunto de exceções (`ERROS_DE_PAGINA_ILEGIVEL`); o resto
  (`inclinacoes.json`, `_orfaos`) fica como estava.

### Q-P8 (Média) — leituras que gravam

- **Evidência:** a propriedade `sequencia` faz I/O, conserta e chama `salvar()`; ela é lida
  só pelo efeito em seis lugares (`projeto.py:299, 338, 386, 393, 1367, 1429`,
  `pagina.py:561`, ruff B018), com comentários do tipo "agora, antes de qualquer render".
- **CA-Q-P8:** ler `projeto.sequencia` não muda nenhum arquivo do projeto (teste por mtime e
  bytes); a montagem da sequência é um método explícito chamado em `abrir`/`criar`.
- **Feito** no Q6 (`72a3baf`): `montar_sequencia` grava os consertos ao criar e ao abrir; a propriedade e o `_carregar_livro` só leem.

### Q-P9 (Baixa) — strings mágicas e duas fontes da verdade

- Estado da página aceito sem validar em `_pagina_de_json` (`projeto.py:1908`), com padrões
  diferentes no JSON e na `Pagina`; `historico.py:178` repete `"nao_reconhecida"`; um
  `notacao` com erro de digitação cai em "letras" sem aviso → `StrEnum` validado na entrada.
- `dados.sequencia`/`_sequencia` e `dados.proximo_pid`/`_proximo_pid` sincronizados à mão
  em seis lugares → uma só, a tipada.
- `Box` é `frozen`, mas `entry` é um `BoxEntry` mutável e `carregar_pagina` entrega os objetos
  vivos do cache (`modelo.py:91-96`, `projeto.py:820-823`) → cópia na saída.
- **CA-Q-P9:** um estado ou uma notação desconhecidos em disco dão `ProjetoInvalido`.
- **Feito** no Q6 (`6cbbe2b`), em parte: `modelo.Estado` e `projeto.Notacao` (`StrEnum`); a notação desconhecida dá `ProjetoInvalido`, e o estado desconhecido faz a página ilegível (a regra do CA-Q-P7, não `ProjetoInvalido`: uma página não impede o livro). As duas fontes da verdade e a cópia do `Box` ficam para o Q7. **Feito** no Q7, corte 4: `carregar_pagina` entrega cópias (`37e97bf` o teste, `712cd9d`); a sequência e o próximo pid numa fonte só, a `SequenciaDoLivro` (`e657a72`, sem teste vermelho: nenhuma divergência visível achada).

## 4. Concorrência e falhas silenciosas

### Q-C1 (Alta, confirmado) — uma exceção no `pronto` some sem log

- **Evidência:** `app/trabalho.py:162-170` (`_fim`) chama o `pronto` só com `try/finally`; a
  exceção vai ao slot do Qt, não ao `log.exception` nem ao `falhou`; não há `sys.excepthook`.
  O `pronto` do F5 muda a página em vários passos (`controlador.py:1269-1295`).
- **Risco:** página pela metade, sem transação, sem gravação, sem aviso.
- **CA-Q-C1:** um `pronto` que levanta deixa um registro com o rastro no log, chama o
  `falhou` da tarefa (aviso na barra) e a fila segue.
- **Correção mínima:** `except Exception` em `_fim` com log e `falhou`; `excepthook` em
  `app/principal.py`.
- **Feito** no Q2 (`e52ae33`, `4822e69`), como a correção mínima; o gancho também pega o
  erro solto de uma thread (`threading.excepthook`).

### Q-C2 (Média, confirmado no Q2, com outro dano) — o lote e o F5 na mesma página

- **Evidência:** `lote._gravar` e o `chegou` dos aguardando entram por `na_interface`, fora do
  executor (`lote.py:378-425`, `controlador.py:1560-1587`); `_mudou_durante`
  (`lote.py:338-349`) não vê o F5 em voo, porque a versão só sobe no `pronto` dele.
- **CA-Q-C2:** F5 em voo + lote que termina a mesma página antes: o resultado final é um só
  dos dois, e o Ctrl+Z do F5 não desfaz a escrita do lote.
- **Correção mínima:** no `pronto`, comparar a versão do pid com a da hora do `preparar`.
- **Feito** no Q2 (`76b88b5`, `47aa314`). O teste mostrou outro dano: o Ctrl+Z do F5 voltava
  certo; o que se perdia era a leitura do lote, que o `pronto` do F5 sobrescrevia enquanto o
  relatório a dava por lida. A versão não serve (o F5 que começa antes do pedido do lote tem
  a mesma): o controlador guarda os pids com um F5 entre o preparar e o pronto
  (`lendo_no_f5`), e o lote deixa a página para reler depois.

### Q-C3 (Média, suspeita) — a rede do servidor usada por duas threads

- **Evidência:** só `leitor.ler` passa por `_ler_com_vez` (`servidor_de_leitura.py:243`);
  `sugerir_recortes` chama `rede.predict` sem a `_trava`.
- **CA-Q-C3:** todo método do leitor chamado no servidor passa pela mesma trava (teste com um
  leitor falso que registra sobreposição).
- **Feito** no Q6 (`1b5acf2`): `dar_a_vez` embrulha também `ler_pelo_livro` e `sugerir` (a trava reentrante); o `arbitro` já lê pelo `ler`.

### Q-C4 (Média, confirmado) — erros engolidos

| Onde | O que acontece |
|---|---|
| `app/trabalho.py:162` | Q-C1 |
| `controlador.py:93-95` (`Eventos.emitir`) | um ouvinte que levanta impede os seguintes |
| `servidor_de_leitura.py:577` | `except Exception: pass` |
| `busca.py:240` | o pool quebrado não deixa log; o índice fica ~4× mais lento |
| `exportar.py:1196-1201` | uma falha na camada do PDF devolve `{}` e descarta o que já foi lido |
| `padroes.py:181-185` | metadados corrompidos viram `{}` e são sobrescritos na gravação seguinte |
| `app/editor_diagrama.py:196`, `render.py:88` | `None`/`pass` sem log |
| `janela.py:318` | o retorno de `executor.esperar()` é ignorado ao fechar |

- **CA-Q-C4:** um teste de arquitetura reprova `except Exception` sem `log.exception` (ou
  re-raise) em `abbychess/`, com uma lista de exceções justificadas; cada linha da tabela tem
  um teste que injeta a falha e confere o log e o estado.
- **Feito** no Q2: o teste de arquitetura (`21c6a83`, `e42ba60`) aceita o que levanta, o que
  registra o rastro e as sete funções de `LEVAM_O_ERRO` (que levam o erro adiante como
  valor), e achou nove que engoliam; ganharam teste próprio as linhas que perdem mais que o
  log (`d7b4bd2`, `b7461aa`): os metadados dos padrões (agora guardados à parte, como a página
  ilegível do Q-P7) e o ouvinte que calava os outros. A camada do PDF não descartava nada:
  a extração é uma chamada só, e ela ganhou o rastro; o resto (o relatório) é do Q3. O
  fechamento com a tarefa presa só ganhou o log, sem teste: uma janela com uma tarefa presa
  30 s não cabe na suíte rápida.

### Q-C5 (Baixa) — corridas menores

- `PoolDoIndice` (`busca.py:220-224`): o pool é liberado fora da trava em que se leu `_usos`.
- `_refazer` lê `self.pagina.projeto` dentro da thread (`controladores.py:1537`); os recortes
  da Galeria não conferem a geração (`app/galeria_na_janela.py:167-186`).
- `_caiu` reenvia os pendentes ao filho novo sem os cancelamentos
  (`servidor_de_leitura.py:586-587`).
- `_voltar` aplica e grava antes de mover o histórico (`controlador.py:2263-2283`).
- **Feito** no Q6 (2026-10-31), um teste e uma correção para cada: o pool confere e se tira numa trava só (`7157ea1`); a busca, a busca por glifo e a procura das amostras leem o projeto do pedido (`31903a2`); os recortes da Galeria conferem a geração (`851e608`); o filho reaberto recebe o cancelar (`22a494a`); o histórico anda com as páginas, antes do disco (`919aa3b`).

## 5. Exportação

### Q-E1 (Alta, a confirmar por teste) — a exportação não lê o Documento

- **Evidência:** `exportar.py` refaz linhas e parágrafos dos boxes (`Estrutura.da_pagina`,
  `exportar.py:295-364`) e não cita `Decisoes.virtuais`, `Decisoes.quebras`,
  `_aplicar_decisoes` nem `partir_lances_colados`, que `texto.montar` aplica
  (`texto.py:169-222`). A área é escolhida pelo centro do glifo, o Documento pela maioria. A
  §12.1 diz "Lê o Documento (§4.2), não os boxes". Nenhum teste de exportação usa virtuais.
- **Risco:** a letra digitada à mão e as palavras partidas pelo usuário somem do DOCX, do EPUB
  e do TXT; o texto exportado diverge do texto que validou os lances.
- **CA-Q-E1:** numa página com uma letra virtual, uma quebra decidida e dois lances colados, o
  texto de cada formato é igual ao `texto.montar` da página (golden normalizado).
- **Correção mínima:** aplicar as decisões nas palavras da exportação; o fim é Q-E6.
- **Feito** no Q3 (`ba96dbb`, `ba28f64`, `1399a8c`, `6a9d483`), confirmado: a linha de
  teste saía "o cavlo … maisum ♘f62.c4", e o Documento "o cavalo … mais um ♘f6 2.c4". A
  `Estrutura` leva as palavras do texto do Documento (sem os não lidos, como `montar`), e
  cada linha exportada sai com elas. A medida da exportação achou uma regressão do primeiro
  passo (o glifo não lido juntava a palavra: "ca o" virava "cao"), que ganhou teste; depois
  da correção, o TXT da fatia do xv sai igual ao da base, byte a byte.

### Q-E2 (Alta, confirmado) — o PDF pesquisável ignora "só páginas verificadas"

- **Evidência:** o filtro está em `exportar.py:987` e `1926`, mas `exportar()` chama
  `exportar_pdf_pesquisavel` direto (`exportar.py:2047`), que usa todas as lidas
  (`1697-1699`).
- **CA-Q-E2:** com `so_verificadas` e uma página não verificada, o PDF não tem camada de texto
  nela e o relatório a cita, como nos outros formatos.
- **Correção mínima:** uma função `_alvo(projeto, indices, opcoes)` usada pelos três caminhos.
- **Feito** no Q3 (`7408d5b`, `03b6f03`), como a correção mínima.

### Q-E3 (Média, confirmado) — o EPUB troca o anterior antes de conferir

- **Evidência:** `_gravar_zip` faz `os.replace` (`epub.py:800`) e o `conferir` vem depois
  (`exportar.py:1329`); o DOCX confere o temporário antes (`escritor_docx.py:449-451`).
- **CA-Q-E3:** um EPUB que reprova no `conferir` não substitui o arquivo que já existia.
- **Feito** no Q3 (`b93bb89`, `586d81f`): o EPUB que não passa é recusado, como o DOCX, e o
  `problemas_do_arquivo` do relatório (sempre vazio agora) saiu.

### Q-E4 (Média, confirmado) — quatro gravações atômicas fora de `gravacao`

- **Evidência:** `exportar.py:1839`, `1858`, `epub.py:860`, `escritor_docx.py:434`; o
  `_gravar_pdf` usa `.tmp` de nome fixo e não o apaga se `doc.save` falhar.
- **CA-Q-E4:** com `PermissionError` na primeira troca (o Word com o DOCX aberto), cada
  formato tenta de novo como `gravacao.gravar_bytes`; uma falha não deixa `.tmp` para trás.
- **Correção mínima:** `gravacao.gravar_por(caminho, escrever_no_tmp, conferir=None)`.
- **Feito** no Q3 (`b93bb89`, `586d81f`), como a correção mínima, nos quatro escritores.

### Q-E5 (Média) — uma decisão em vários lugares na exportação

- O idioma: `exportar.py:1241-1258` e `idioma.py:74`, aberto duas vezes por exportação.
- O reconhecimento de lance em quatro regex: `lances.py:85`, `contexto.py:55`, `zonas.py:98`,
  `texto.py:141`; `PECAS` em `busca.py:48` e `sessao.py:628` (e `lances.py:168` importa de
  `sessao`).
- As marcas dos trechos e a ressalva do diagrama em `epub.py:214-244, 513-515` e
  `escritor_docx.py:142-183, 212-217`.
- O lado do PGN com o diagrama conferido (`lances.py:504`, suspeita).
- `Estrutura` chaveada por `id(BoxEntry)` (`exportar.py:304-363`): uma cópia perde o estilo.
- **CA-Q-E5:** um teste de arquitetura conta uma definição por regra (regex de lance, `PECAS`,
  idioma); os trechos marcados têm uma função comum ao EPUB, ao DOCX e à prévia.
- **Feito em parte** no Q7, corte 5 (`docs/revisoes/qualidade-Q7.md`): o idioma pedido uma vez
  por exportação (o `Pedido`, em TDD); o `PECAS` só em `modelo.py`, e as letras de lance do
  `contexto` e do `zonas` derivadas dele (em TDD: o lance alemão e o espanhol eram
  improváveis); `marcacao.trechos_marcados` e `ressalva_do_diagrama`, comuns ao EPUB e ao
  DOCX (a prévia usa a do EPUB); `tests/test_regras_unicas.py` é o teste de arquitetura. As
  quatro regex de lance ficam: cada uma é uma regra diferente (o SAN do PGN, a palavra que
  parece lance, a linha de lances sem espaços, o lance colado), e só as letras eram a mesma.
  Ficam: o lado do PGN (suspeita, não investigada); a `Estrutura` por `id()`, sem caminho de
  hoje que a quebre. Os dois detectores de idioma viraram um em 2026-11-04 (§13.7).

### Q-E6 (Melhoria) — um adaptador do Documento para a exportação

O que se construiria do zero: um `Pedido(projeto, opcoes)` resolvido uma vez (páginas,
idioma, metadados, números impressos) e a exportação consumindo `texto.montar`. `exportar.py`
(2 000+ linhas) se parte em montagem/margens (puras), PDF pesquisável, metadados e a porta
de entrada.

**Feito em parte** no Q7, corte 5: o `exportar.py` partido como acima (674 linhas), e o
`Pedido` (as opções, os índices cortados pelo intervalo, o alvo e o idioma, resolvidos uma
vez). Os metadados continuam montados pela porta de entrada, e os números impressos pelas
margens, no caminho das páginas: o `Pedido` os levaria sem mudar nada que se veja. A
exportação consumindo `texto.montar` inteira fica: muda o texto exportado (não é estrutura) e
pede o seu passo, com o golden de cada formato.

**Medido em 2026-11-04, e não feito:** na fatia do Xadrez Vitorioso (snapshot inicial, sete
páginas, com as margens, sem a camada), `texto.montar` e a exportação têm 95,0 % das palavras em
comum (2 053 de 2 160), em 81 trechos diferentes. Nos 40 que li, a exportação sai melhor: corrige
a caixa pela altura (`eSse` → `esse`, `CC6` → `Cc6`) e junta o hífen de quebra (`van- tagem` →
`vantagem`). Ler `montar` inteira perderia isso no livro exportado. Antes do Q-E6, é preciso
decidir se a correção da caixa vai para o Documento, e o hífen pede a junção na exportação de
qualquer jeito.

**A caixa no Documento, medida em 2026-11-04 (só leitura; a decisão continua em aberto).** A
regra atual (`montagem._caixa_pela_altura`) levada ao Documento, na fatia: troca 62 de 10 204
glifos, e as 62 já estão na fila de revisão, 61 com a mesma sugestão (`contexto`). Os improváveis
vão de 209 a 149, os pendentes de 1 965 a 1 954, as desconhecidas de 244 a 216. A validação dos
diagramas fica igual nos 14 medidos (a fatia, Yusupov, Darcy e as pp. i000 e i007 do Vitorioso).
O CER oficial não muda, porque `medir.py` já lê as linhas da exportação: 385 erros sem a regra,
338 com ela, 334 só descendo, em 12 008 caracteres.

Contra o gabarito (a fatia) e a camada do PDF (Yusupov, Aagaard, Nunn, Dvoretsky, Odds & Ends):

| Direção | Certas | Erradas | Sem como comparar |
|---|---|---|---|
| Desce para minúscula | 102 | 0 | 9 |
| Sobe para maiúscula | 8 | 15 | 6 |

As 15 erradas sobem no meio da palavra (`eVitar`, `eXistirá`, `anyWhere`), numa caixa mais alta
que a letra; 7 são capturas que `_captura_minuscula` conserta na saída, e as outras 8 saem no
arquivo. As 8 certas sobem na primeira letra (`white` → `White`). A amostra é pequena e veio
depois da regra, sem conferência à parte. **A regra também desfaz o glifo confirmado:** ela não
olha a fonte do glifo, e o `v` de "evitar" marcado como manual continua saindo `eVitar`, sem que
o usuário possa corrigi-lo.

**Corrigido na exportação em 2026-11-04** (`de06353`, `1c12c16`): a letra só sobe na primeira
posição da palavra, e a altura não troca o glifo manual, o nativo nem o revisado. Medida de novo
nas mesmas páginas, pelo caminho real da exportação: 110 trocas certas (102 descendo, 8 subindo) e
nenhuma errada, com 10 sem como comparar; na fatia, 333 erros em 12 008 caracteres (2,77 %). A
regra foi desenhada olhando estas páginas, então a medida não é independente. Levar a correção ao
Documento continua em aberto, e o impacto da tabela acima não foi refeito com a regra nova.

### Q-E7 (Média) — privados do core

`leitor.py:75,128,130` (`_predictor`, `_get_learner`), `verificacao.py:93,96`
(`lexico._ler`), `diagramas.py:231-232,330` (`TabuleiroEdicao._historico`, `_estado`,
`_indice`, `_registrar`); e regras copiadas do core (`exportar.py:703-720`, `1618-1639`,
`layout.py:298`). Contra o contrato do roadmap e a §18.2.
- **CA-Q-E7:** um teste de arquitetura reprova `._x` de módulos do PyBoxEditor fora de uma
  lista de exceções que encolhe; cada exceção tem um pedido em
  `docs/pedidos-ao-pyboxeditor.md` e um teste de contrato que fixa o comportamento usado.
- **Feito** no Q9 (`docs/revisoes/qualidade-Q9.md`): `tests/test_privados_do_core.py` e
  `tests/test_contrato_do_core.py`; nove acessos em quatro pedidos. As regras copiadas do core
  ficam fora do CA.

## 6. Arquitetura

### Q-A1 (Média) — objetos-deus

| Classe | Tamanho | Corte proposto |
|---|---|---|
| `ControladorDePagina` (`controlador.py:138`) | 138 métodos, ~2 400 linhas; 9 das 15 funções mais complexas | `Navegador` (480-602), `ControladorDaSequencia` (§12.4, 604-1006), fila e margens para o `ControladorDaFila` que já existe, `PonteDeLeitura` (1533-1710), `AplicadorDoHistorico` (2177-2320), `ControladorDaSessao`. **Feito no Q7, corte 3** (`docs/revisoes/qualidade-Q7.md`): esses e o `ControladorDosPadroes`; a fila virou `FilaDaPagina` (o `ControladorDaFila` é da janela); 888 linhas e 61 métodos |
| `ProjetoDeLivro` (`projeto.py`) | ~1 640 linhas | `CacheDePaginas` (com páginas presas, Q-P3), `ResumoDoLivro`, `Migracoes`, `Fonte`. **Feito no Q7, corte 4** (`docs/revisoes/qualidade-Q7.md`): `CacheDoProjeto`, `ResumoDoLivro`, `Migracoes`, `FonteDoLivro`, e também `AntesDoLote`, `SequenciaDoLivro` e a página em JSON; 950 linhas e 43 métodos |
| `JanelaPrincipal` (`app/janela.py:72`) | 447 linhas, mas 9 mixins somam ~3 000 na MRO | composição: um objeto por painel, com só os controladores de que precisa |
| `exportar.py` | ~2 000 linhas | Q-E6. **Feito no Q7, corte 5** (`docs/revisoes/qualidade-Q7.md`): `montagem`, `margens`, `metadados`, `pedido`, `pdf_pesquisavel`; 674 linhas |

- **CA-Q-A1:** nenhum arquivo de `abbychess/` com mais de 1 000 linhas, nenhuma classe com
  mais de 40 métodos (teste de arquitetura, com o teto descendo a cada passo). **No fim do
  Q7** (decisão §13.6): `controladores.py` (2 055), `pagina.py` (1 446), `epub.py` (1 144) e
  cinco classes (`ControladorDePagina` 61, `VistaDoDocumento` 58, `VisorDePagina` 55,
  `EspacoDeTrabalho` 53, `ProjetoDeLivro` 43) ficam presos em `TETOS` de
  `tests/test_tamanho_dos_modulos.py`. **No Q8** (`docs/revisoes/qualidade-Q8.md`, rodadas 4
  e 5), partir as funções obrigou a tirar seções dos três arquivos: nenhum arquivo passa mais de
  1 000 linhas; as cinco classes continuam presas.

### Q-A2 (Média) — o app decide regra de negócio (CA-14.1)

- O estado da sessão do Documento mora no `QTextEdit` (`app/documento.py:197, 777-800`) e o
  controlador chama a janela para confirmá-la (`controlador.py:176`, `janela.py:178`).
- A política de ações ligadas/desligadas está em `acoes.atualizar` (`app/acoes.py:353-440`,
  cc 42), com uma tupla casada por posição.
- O fluxo de criar projeto está em `app/dialogos.py:140-208`; a ordem de fechar em
  `janela.py:321-341`; uma thread com lógica de domínio em `app/galeria_na_janela.py:156-188`.
- O pipeline "depois de ler" (reconciliar, mesclar, `depois_de_ler`, legendas, validar,
  estado) está em quatro lugares: `controlador.py:1253-1298`, `lote.py:378-425`,
  `controlador.py:125-135`, `controlador.py:2587-2601`.
- **CA-Q-A2:** um `EstadoDaJanela` sem Qt (`habilitadas: dict[str, motivo | None]`) calculado
  no controlador e testado sem janela; `acoes.atualizar` só aplica. Uma função pura
  `aplicar_lida(pagina, lida, ...)` usada pelo F5 e pelo lote, com um teste que compara os
  dois caminhos na mesma página.

### Q-A3 (Baixa) — uma decisão em dois lugares no controlador

O lote rodando com dois flags (`controlador.py:217`, `controladores.py:806`); o modo da fila
em dois lugares espelhados à mão (`controlador.py:193`, `controladores.py:1212, 1236`); a
duração 8000 ms em ~30 lugares; "centro dentro da zona" três vezes
(`controlador.py:1237, 1266, 1281`); `TEMPO_DO_PEDIDO` no controlador, importado pelo lote.

**Feito** no Q5 (2026-10-31): `_trocar_condutor` muda o condutor e o flag juntos;
`AVISO_LONGO_MS`; `TEMPO_DO_PEDIDO` no `servidor_de_leitura`; `Zona.contem_o_centro` (eram
seis contas, três em `zonas.py`). O modo da fila fica: `ordem_da_fila` guarda o último modo de
glifos enquanto a fila mostra palavras ou diagramas, e só `ControladorDaFila.definir` a escreve.

## 7. Duplicação (dryer, rank ≥ 0,8)

`ferramentas/dryer.py` compara a forma do AST de cada par de funções com ≥ 60 nós. Os 16
pares de `docs/medidas/qualidade/duplicacao-4accb7f.txt`, com o destino:

| Rank | Par | Destino |
|---|---|---|
| 1,00 | `diagramas.com_ids` ↔ `zonas.com_ids` | `com_ids(itens, prefixo)` genérico |
| 0,98 | `controladores.trocar_tipo` ↔ `trocar_funcao` | um `_trocar(campo, valor)` |
| 0,91 | `sessao._linha_original` ↔ `_palavras_originais` | uma derivando da outra |
| 0,87 | `lote._paginas` ↔ `app/dialogo_paginas.texto_da_selecao` | **uma regra** de faixas de páginas (hoje uma usa "–" e a outra "-": decidir se é de propósito) |
| 0,87 | `visor.marcar_palavra` ↔ `marcar_palavra_do_documento` | um parâmetro |
| 0,86 | `painel_treino.abrir_paleta` ↔ `documento.abrir_paleta` | um ajudante comum do app |
| 0,86 / 0,85 / 0,82 | `paginas_na_janela`: `apagar_paginas`, `mover_paginas`, `tirar_o_corte`, `girar_paginas` | um `_operar_nas_paginas(operacao)` |
| 0,86 | `controlador.documento` ↔ `texto` | um derivando do outro |
| 0,84 | `barra_de_busca._botao` ↔ `_acao_simples` | um só |
| 0,84 | `controlador.voltar_visita` ↔ `avancar_visita` | `_andar_na_visita(passo)` |
| 0,82 | `edicao.corrigir` ↔ `ajustar` | rever: podem ser duas operações de mesma forma |
| 0,82 | `busca._paginas_do_escopo` ↔ `controladores._paginas` | **uma regra** de escopo (a do controlador só troca o conjunto de páginas) |
| 0,81 | `padroes.esquecer` ↔ `restaurar` | rever: inversos de mesma forma são esperados |
| 0,81 | `diagramas.para_caixas` ↔ `mesclar` | rever |

- **CA-Q-D1:** `dryer.py abbychess 0.8` lista só os pares marcados "rever" que forem
  aceitos, registrados numa lista de exceções com o motivo; o teste de arquitetura reprova
  par novo. **Feito** no Q5 (2026-10-31): 1 par, aceito em `ferramentas/pares_aceitos.txt`;
  quem reprova o par novo é a medida (`dryer.py --aceitos`, chamado por `qualidade.py`), não
  a rápida: o dryer leva 18 s. A rápida testa o mecanismo num pacote de brinquedo.

## 8. Complexidade (crapper, CRAP < 10)

CRAP = cc² × (1 − cobertura)³ + cc. Com cc ≥ 10 a função passa de 10 mesmo 100 % coberta: dos
301 casos, 251 só se resolvem partindo; os 45 com cobertura < 50 % se resolvem testando
primeiro (e partindo, se ainda passarem).

As piores pela complexidade (cc): `ControladorDePagina._voltar` 55, `epub.conferir` 62,
`app/acoes.atualizar` 42, `modelo.reconciliar` 41, `zonas.classificar_funcoes` 39,
`escritor_docx.escrever` 39, `sessao.planejar` 39, `ancoragem.como_digitado` 37,
`contexto._pela_linha` 35, `sessao.aplicar` 34, `epub._capitulos` 34.

As piores pela cobertura: `epub.calibre` (CRAP 567, 12 %), `ServidorDeLeitura._ouvir` (219,
3 %), `ControladorDaFila._outra_pagina_das_palavras` (104, 8 %), `RenderEmProcesso.renderizar`
(102, 3 %), `LoteNaJanela._servidor_caiu` (76, 6 %), `camada.palavras` (49, 5 %).

- **CA-Q-X1:** `crapper.py` com a cobertura combinada (rápida + `processo`) não lista função
  ≥ 10 fora de uma lista de exceções com motivo (por exemplo, um `match` de despacho que
  ficaria pior partido); o teto da lista desce a cada passo.
- Os `case`/cadeias de `if` de despacho (`acoes.atualizar`, `atalhos._regras_da_tecla`) só
  são partidos se a tabela de dados ficar mais clara que o código.
- **Feito** no Q8 (`docs/revisoes/qualidade-Q8.md`): a lista é `ferramentas/crap_aceitos.txt`
  (o `crapper --aceitos` na medida, `tests/test_complexidade.py` na rápida, o `TETO` que só
  desce); das 281 do começo sobram 9, cada uma com o motivo (três por glifo, três despachos ou o
  ponto de entrada, três que só o portão ou a tela de verdade alcançam). O
  `atalhos._regras_da_tecla` não era despacho (uma tecla quebra várias regras): foi partido.

## 9. Mutação

Não medido: o `mutmut` 3 não roda no Windows sem `fork`; o `cosmic-ray` roda. A mutação de
31 mil linhas não cabe numa sessão, nem na regra de uma carga pesada por vez.
- **CA-Q-M1:** os módulos puros (`modelo`, `texto`, `lances`, `sequencia`, `historico`,
  `sessao`, `zonas`, `busca`) com ≥ 85 % de mutantes mortos, um módulo por sessão, só os
  testes que importam o módulo, `-n` ≤ 4; os sobreviventes viram teste ou código apagado.
- **Feito** no Q9 (`docs/revisoes/qualidade-Q9.md`): `ferramentas/mutador.py` (da casa, pelo
  AST, cada mutante só com os testes da linha dele); os oito módulos de 86,0 % (`busca`) a
  98,4 % (`sequencia`), 92,2 % ao todo, medidos no `3265d20` com 2 trabalhadores.

## 10. A suíte de testes

### Q-T1 (Alta, confirmado) — o teste instável da janela carrega os modelos globais

- **Evidência:** `tests/test_janela.py:470`
  (`test_trocar_de_projeto_com_tarefa_em_voo_termina_no_projeto_dela`) chega a
  `LeitorDoLivro.com_modelos_globais` (`leitor.py:113`) por `janela.trocar_projeto` →
  `livro.abrir`; o `_esperar` (`test_janela.py:47`, 20 s) espera a fila inteira. Só
  `tests/test_janela_persistencia.py:36` faz o stub.
- **CA-Q-T1:** uma fixture autouse na suíte rápida bloqueia `com_modelos_globais` (liberada
  só em `livro_real`); o teste passa 20 vezes seguidas com `-n 4` e espera a condição dele
  (o projeto certo e a página gravada), não a fila ociosa.
- **Feito** no Q4 (`5989fde`, `617fb3b`): sem os modelos, o aviso modal "a rede não carregou"
  parava o teste até o timeout; a suíte ganhou também uma fixture que não deixa aviso modal
  nenhum abrir. O teste passou 20 vezes seguidas, em 0,39 s (10,6 s sozinho antes).

### Q-T2 (Alta) — tempo de relógio e `sleep` como sincronização

- Asserções de tempo: `test_laco.py:134`, `test_gravador.py:43-52, 278`, `test_render.py:70`.
- `sleep` fixo como "o outro já chegou": `test_laco.py:57,84,129,146,151`,
  `test_servidor.py:80,90`, `test_render.py:67`, `test_busca.py:456`,
  `test_gravador_processo.py:53`.
- 14 laços `while … sleep` em 6 variantes de `_esperar`; o `qtbot` nunca é usado.
- **CA-Q-T2:** um teste de arquitetura reprova `time.sleep` e `perf_counter` em asserção na
  suíte rápida; a espera é uma só (`qtbot.waitUntil` ou um `esperar(cond)` do conftest), e os
  falsos sinalizam com `threading.Event`.
- **Feito** no Q4 (`c500f8c`, `072408f`): 23 casos em 8 arquivos (os de `test_servidor` e
  `test_gravador_processo` são da camada `processo` e ficam). A espera única é
  `tests/ajudantes.esperar`; as afirmações de tempo viraram fatos causais (a chamada voltou
  com o falso ainda preso) ou o relógio falso do `Gravador`.

### Q-T3 (Média) — testes de implementação

- ~270 acessos a `_x` do código; os piores montam estado interno
  (`test_controlador.py:258,286,396,446`, `test_busca.py:369-391`,
  `test_documento.py:200-334`, `test_fechamento_l.py:308-313`, `test_janela.py:85`).
- Espiões que contam chamadas sem conferir o resultado
  (`test_texto_linhas_guardadas.py:81-107`, `test_gravador.py:338`, `test_visor.py:507,531`).
- **CA-Q-T3:** cada teste desses confere o resultado que o usuário veria; o estado é montado
  por API pública (ganchos de teste pequenos e nomeados, como `projeto.esvaziar_cache()`).
- **Feito** no Q8: os testes listados montam o estado pelo que o usuário faz e conferem o que
  ele vê; cada versão nova reprovou com o código quebrado por um instante. Um gancho, só de
  leitura (`FaixaDaLinha.glifos`); um espião fica, com o motivo (a ordem de leitura não
  refeita não se vê sem relógio). Os dois restos do Q-T4 também.

### Q-T4 (Média) — a pirâmide da §15.1 não é imposta

- O marcador `noturno` não é aplicado a teste nenhum; as máquinas de estado rodam na rápida com
  `timeout(600)` (`test_modelo_estados.py:327, 563`).
- Nenhum hook reprova a suíte rápida acima de 60 s; ela leva 100 s com cobertura.
- `test_fen_no_livro.py:67` pula quando a segmentação falha (uma regressão vira skip);
  `test_sessao.py:313` usa `times.ttf` sem guarda; ~40 % da suíte pula sem a Arial, sem aviso
  agregado.
- **CA-Q-T4:** `-m noturno` seleciona as máquinas com 5 000 exemplos e a rápida roda 100; um
  `pytest_sessionfinish` reprova a rápida acima de ~~60 s~~ 90 s (§13.5); o resumo da sessão
  conta os pulos por motivo.
- **Feito** no Q4 (`a1e4f76`, `4fd272b`). O `test_fen_no_livro` e o `times.ttf` sem guarda
  ficam para o Q8 (Q-T3).

### Q-T5 (Baixa) — o conftest central não existe de fato

32 `QApplication.instance() or QApplication([])` em 26 arquivos, ~180 imports
`from tests.test_X import …`, fixtures reimportadas com `# noqa: F811`, PDFs sintéticos
refeitos a cada teste, 25 testes de `test_janela.py` reconhecendo a mesma página.
- **CA-Q-T5:** nenhum `from tests.test_` nos testes; ~~as fixtures de sessão (PDF, PNG,
  projeto já reconhecido copiado por `copytree`) baixam a suíte rápida para < 60 s com
  `-n 4`~~ (o teto passou a 90 s, §13.5, e a suíte já cabe nele: 77–82 s).
- **Feito** no Q4 (`a96bea7`, `282a389`), por uma ferramenta que move cada nome com as
  definições de que ele depende: as 128 importações de 48 nomes vão para
  `tests/ajudantes.py`, `tests/fixturas.py` (que o conftest dá a todos) e três
  `tests/fixturas_<origem>.py` (as `janela` de nome repetido); a `app` é do conftest, de
  sessão. As fixtures de sessão para o tempo não foram feitas: o teto de 90 s não as pede.

### Q-T6 (Melhoria) — onde falta propriedade

Hypothesis só em `test_modelo_estados.py`. Faltam: as edições fora das máquinas
(`dividir_em`, `estilizar`, `paragrafo`, virtuais, `juntar_varios`, `ajustar`, `revisar`); o
desfazer entre páginas com o gravador ("gravar, reabrir e comparar"); a sequência (reordenar,
apagar e restaurar preservam os pids); substituir e desfazer; o ida-e-volta de lances e FEN.
- **Feito** no Q8: uma propriedade por grupo (`tests/test_propriedades_*.py`, com
  `tests/estrategias.py`), poucos exemplos na rápida (~1,9 s em série) e 2 000 no `noturno`.
  Elas acharam dois defeitos, corrigidos com o exemplo mínimo como teste: as letras digitadas
  na edição 1 → k cortadas uma em cima da outra, e o virtual tirado que trocava a ordem dos
  outros.

## 11. Código morto (sai antes de refatorar)

`projeto._arquivo_da_pagina`, `salvar_zonas`, `modelo.n_de`, `pagina.efeitos_de_impressao`,
o parâmetro `indices_v1` de `sq.da_v2` (sempre `()`), `app/documento.ir_ao_fim_do_gid`,
`app/painel_resultados.mostrar_glifos`, o `avisar` de `controlador._pode_ler`, o alias
`editar = tem` (`acoes.py:383`), `leitor.FONTE_LIVRO_FRACO`, `historico.descartar_desfazer`,
`descartar_refazer`, `emendou`. Os usados só por testes (`exportar.exportar`, `paragrafos`,
`migrar_tudo`, `grade.ACEITOS`, `diagramas.amostras_guardadas`) ficam se forem a porta que o
teste usa como o usuário; senão saem. Os 3 F401 de `camada.py` saem já (o portão).
- **CA-Q-Z1:** cada item é confirmado sem chamador por `git grep` (e pelo mutador, quando
  houver) e apagado num commit próprio; a suíte passa igual. **Feito** no Q5 (2026-10-31):
  saíram `FONTE_LIVRO_FRACO`, `ir_ao_fim_do_gid`, `mostrar_glifos`, `efeitos_de_impressao`,
  o `indices_v1` e o `avisar` de `_pode_ler`; `_arquivo_da_pagina`, `n_de`,
  `descartar_desfazer`/`descartar_refazer` e `emendou` têm chamador e ficam; `salvar_zonas`,
  `exportar`, `paragrafos`, `grade.ACEITOS` e `amostras_guardadas` ficam como a porta do
  teste; o alias `editar = tem` sai no Q-A2.

## 12. Fora do escopo

- Função nova da `docs/SPEC.md`.
- Editar o PyBoxEditor: o que precisar dele vira pedido em `docs/pedidos-ao-pyboxeditor.md`.
- Trocar de biblioteca (pydantic, msgspec): a validação de entrada é escrita à mão, com
  dataclasses, até um passo provar que não dá.

## 13. Decisões em aberto

1. ~~**Q-P1:** migrar toda a v1 na abertura ou só passar a busca a pid?~~ **Decidido**
   (2026-10-30): migrar toda a v1 na abertura.
2. ~~**Faixas de páginas:** o "–" do lote e o "-" do diálogo são de propósito (mostrar contra
   digitar)?~~ **Decidido** (2026-10-31): sim; uma função só, `sequencia.faixas_de_paginas`,
   com o separador por parâmetro.
3. ~~**Q-P5:** o segundo processo abre só para leitura ou recusa?~~ **Decidido** (2026-10-31): só para leitura, com o motivo.
4. ~~**Q-E1:** a exportação passa a usar `texto.montar` inteira (Q-E6) já no primeiro passo, ou
   primeiro só as decisões?~~ **Decidido** (2026-10-30): só as decisões no Q3; o Q-E6 no Q7.
5. ~~**Teto da suíte rápida:** 60 s sem cobertura (como hoje na §15.1) e a medida com
   cobertura à parte?~~ **Decidido** (2026-10-30): 90 s com -n 4 e sem cobertura; a medida
   com cobertura, à parte.
6. ~~**CA-Q-A1 no fim do Q7:** fechar com o que sobra preso na catraca ou seguir cortando?~~
   **Decidido** (2026-10-31): fechar; os tetos de `tests/test_tamanho_dos_modulos.py` só
   descem.
7. ~~**Idioma do livro:** a exportação usa o detector do core (pt e en) e o projeto novo o de
   `idioma.py` (cinco idiomas); escolher um só muda o `dc:language` do EPUB. Qual vale?~~
   **Escolhido** (2026-11-04, pela sessão, quando o usuário mandou continuar; a conferir): o de
   `idioma.py`. Nos 14 PDFs de `PyBoxEditor_Tkinter\PDF` os dois dão a mesma resposta (10 en, 1
   pt, 3 sem resposta), e o `dc:language` deles não muda; o do core deixava sair `pt-BR` o livro
   em espanhol, alemão ou francês. A camada continua valendo sobre o idioma do projeto.
8. ~~**O espaço digitado dentro de uma ligadura** (achado no Q9, defeito B): "afib" → "af ib",
   com o box "fi", deixa a página "a fib". Corrigir mexe no plano da sessão (um item por pedaço
   da divisão), e, sem tinta para cortar (a imagem indisponível ou as letras coladas), a sessão
   pode recusar a edição ou guardar a caixa e perder o espaço. Qual?~~ **Decidido**
   (2026-11-03): recusar, com o motivo ("divida-o antes (Ctrl+D)"). **Feito** no ramo
   `ligadura-com-espaco` (`1bb99f5` vermelho, `bc4611c`): a ligadura com espaço dentro se
   divide pela tinta e a palavra parte entre os pedaços; a página sem imagem, ou a tinta que
   não dá duas partes, recusa (o core corta até as letras coladas, no meio da largura).

## Apêndice — registro da análise

| Ação | Por quê |
|---|---|
| Li a `docs/SPEC.md` (§14, §15) e o contrato do `plans/abbychesscraft-roadmap.md` | para não repetir o que já está planejado e seguir o contrato dos passos |
| Rodei a suíte rápida com cobertura (`-n 4`, sozinha) | a cobertura por linha é a entrada do CRAP; uma carga pesada por vez |
| Escrevi `ferramentas/crapper.py` (AST + `coverage.json`) e comparei a complexidade com a contagem independente dos revisores (`_voltar` 55 × 53, `acoes.atualizar` 42 × 42, `epub.conferir` 62 × 61) | a skill pede o crapper e ele não estava instalado; a primeira versão pulava os métodos de classe (faltava `yield from`), corrigido |
| Escrevi `ferramentas/dryer.py` (forma do AST + difflib) | idem para o dryer; a primeira versão comparava a função aninhada com a mãe (2 falsos pares), corrigido |
| Rodei o `ruff` do portão e um conjunto maior de regras | achou o portão quebrado (F401) e os `except` cegos |
| Quatro revisores de leitura, em paralelo, um por área (modelo e persistência, controladores e app, exportação, testes) | 31 mil linhas não cabem na leitura direta; cada um com escopo disjunto |
| Conferi no código os achados de severidade alta (Q-P1, Q-C1, Q-E1, Q-E2, Q-T1) | o relato de um revisor não é prova |
| Não rodei mutação | não há ferramenta instalada e não cabe numa carga só (§9) |
