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

Ressalva sobre o CRAP: a cobertura é só a da suíte rápida. O servidor de leitura, o render em
processo e o lote ficam com CRAP alto porque a camada `processo` não entrou na conta. Por
isso o roadmap começa juntando as coberturas (Q0).

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

### Q-P2 (Alta, confirmado) — um arquivo v1 que sobrou regrava a página vazia

- **Evidência:** `_tem_v1` é verdadeiro com `paginas/NNNN.json` **ou** `zonas/NNNN.json`
  (`projeto.py:989-990`); `_migrar` (`projeto.py:1030-1040`) grava a v2 e apaga os dois com
  `gv.apagar`, que não tenta de novo em `PermissionError` (o `gravar_bytes` tenta). Se só o de
  zonas sobra, a próxima leitura remigra uma página sem boxes por cima de `p<pid>.json`.
- **CA-Q-P2:** com o apagar do arquivo de zonas falhando uma vez (injetado), a página
  migrada continua com todos os glifos depois de reabrir.
- **Correção mínima:** apagar primeiro o v1 de zonas e por último o de página (o de página
  marca "migrada"); `apagar` com as mesmas novas tentativas de `gravar_bytes`.

### Q-P3 (Alta, suspeita) — a página aberta pode sair do cache durante o lote

- **Evidência:** o LRU de 16 páginas (`projeto.py:747-755`) só poupa as sujas; `lote.py:381`
  e `421` comparam `pagina is p.modelo`.
- **Risco:** um lote de mais de 16 páginas despeja a aberta; o lote grava num objeto novo, a
  janela segue editando o velho e a próxima gravação apaga a leitura do lote.
- **CA-Q-P3:** com a página 0 aberta e limpa, um lote de 20 páginas sintéticas que inclui a 0
  termina com a leitura do lote visível na janela e no disco, e uma edição seguinte não a
  apaga.
- **Correção mínima:** `projeto.fixar(pid)` para a página aberta.

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

### Q-P5 (Média, confirmado) — nada impede dois processos no mesmo projeto

- **Evidência:** nenhuma trava entre processos; `limpar_temporarios`
  (`gravacao.py:151-157`) apaga o `.tmp` em curso do outro.
- **CA-Q-P5:** abrir o mesmo projeto num segundo processo o abre só para leitura, com aviso.
- **Correção mínima:** `projeto.lock` com `msvcrt.locking` (ou `O_EXCL` com o pid) em `abrir`.

### Q-P6 (Média, confirmado) — `projeto.json` validado pela metade

- **Evidência:** `"limiares": 5` levanta `AttributeError` em `_separar`; `proximo_pid: "12"`
  só estoura no meio de uma edição; o `ValueError` da sequência na migração escapa porque só
  `OSError` é tratado (`projeto.py:313-327`, `376`).
- **CA-Q-P6:** para cada campo de `projeto.json`, um valor do tipo errado ao abrir dá
  `ProjetoInvalido` com o nome do campo, e nada é gravado (teste parametrizado, ou hypothesis
  sobre o JSON).
- **Correção mínima:** uma função de entrada que valida os tipos de `Projeto` e `Limiares`.

### Q-P7 (Média, confirmado) — a página ilegível é tratada de três jeitos

- **Evidência:** `carregar_modelo` levanta (`projeto.py:670`); `ler_sem_guardar` e
  `ler_sem_migrar` devolvem `None` em `ValueError` (`603`, `943`), e a busca e a aba
  Diagramas pulam a página em silêncio; `_orfaos` e `recalcular_livro` capturam outro conjunto
  de exceções. O comentário de `projeto.py:1127` diz que um `inclinacoes.json` ilegível é
  ignorado, mas `pagina.py:139-141` levanta.
- **CA-Q-P7:** um `p<pid>.json` truncado aparece como "página ilegível" na busca, nos
  Diagramas e no relatório da exportação, nunca como "não reconhecida".
- **Correção mínima:** `ler_pagina(arquivo) -> Pagina | PaginaIlegivel`, um conjunto de
  exceções, log em `warning`.

### Q-P8 (Média) — leituras que gravam

- **Evidência:** a propriedade `sequencia` faz I/O, conserta e chama `salvar()`; ela é lida
  só pelo efeito em seis lugares (`projeto.py:299, 338, 386, 393, 1367, 1429`,
  `pagina.py:561`, ruff B018), com comentários do tipo "agora, antes de qualquer render".
- **CA-Q-P8:** ler `projeto.sequencia` não muda nenhum arquivo do projeto (teste por mtime e
  bytes); a montagem da sequência é um método explícito chamado em `abrir`/`criar`.

### Q-P9 (Baixa) — strings mágicas e duas fontes da verdade

- Estado da página aceito sem validar em `_pagina_de_json` (`projeto.py:1908`), com padrões
  diferentes no JSON e na `Pagina`; `historico.py:178` repete `"nao_reconhecida"`; um
  `notacao` com erro de digitação cai em "letras" sem aviso → `StrEnum` validado na entrada.
- `dados.sequencia`/`_sequencia` e `dados.proximo_pid`/`_proximo_pid` sincronizados à mão
  em seis lugares → uma só, a tipada.
- `Box` é `frozen`, mas `entry` é um `BoxEntry` mutável e `carregar_pagina` entrega os objetos
  vivos do cache (`modelo.py:91-96`, `projeto.py:820-823`) → cópia na saída.
- **CA-Q-P9:** um estado ou uma notação desconhecidos em disco dão `ProjetoInvalido`.

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

### Q-C2 (Média, suspeita) — o lote e o F5 na mesma página

- **Evidência:** `lote._gravar` e o `chegou` dos aguardando entram por `na_interface`, fora do
  executor (`lote.py:378-425`, `controlador.py:1560-1587`); `_mudou_durante`
  (`lote.py:338-349`) não vê o F5 em voo, porque a versão só sobe no `pronto` dele.
- **CA-Q-C2:** F5 em voo + lote que termina a mesma página antes: o resultado final é um só
  dos dois, e o Ctrl+Z do F5 não desfaz a escrita do lote.
- **Correção mínima:** no `pronto`, comparar a versão do pid com a da hora do `preparar`.

### Q-C3 (Média, suspeita) — a rede do servidor usada por duas threads

- **Evidência:** só `leitor.ler` passa por `_ler_com_vez` (`servidor_de_leitura.py:243`);
  `sugerir_recortes` chama `rede.predict` sem a `_trava`.
- **CA-Q-C3:** todo método do leitor chamado no servidor passa pela mesma trava (teste com um
  leitor falso que registra sobreposição).

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

### Q-C5 (Baixa) — corridas menores

- `PoolDoIndice` (`busca.py:220-224`): o pool é liberado fora da trava em que se leu `_usos`.
- `_refazer` lê `self.pagina.projeto` dentro da thread (`controladores.py:1537`); os recortes
  da Galeria não conferem a geração (`app/galeria_na_janela.py:167-186`).
- `_caiu` reenvia os pendentes ao filho novo sem os cancelamentos
  (`servidor_de_leitura.py:586-587`).
- `_voltar` aplica e grava antes de mover o histórico (`controlador.py:2263-2283`).

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

### Q-E2 (Alta, confirmado) — o PDF pesquisável ignora "só páginas verificadas"

- **Evidência:** o filtro está em `exportar.py:987` e `1926`, mas `exportar()` chama
  `exportar_pdf_pesquisavel` direto (`exportar.py:2047`), que usa todas as lidas
  (`1697-1699`).
- **CA-Q-E2:** com `so_verificadas` e uma página não verificada, o PDF não tem camada de texto
  nela e o relatório a cita, como nos outros formatos.
- **Correção mínima:** uma função `_alvo(projeto, indices, opcoes)` usada pelos três caminhos.

### Q-E3 (Média, confirmado) — o EPUB troca o anterior antes de conferir

- **Evidência:** `_gravar_zip` faz `os.replace` (`epub.py:800`) e o `conferir` vem depois
  (`exportar.py:1329`); o DOCX confere o temporário antes (`escritor_docx.py:449-451`).
- **CA-Q-E3:** um EPUB que reprova no `conferir` não substitui o arquivo que já existia.

### Q-E4 (Média, confirmado) — quatro gravações atômicas fora de `gravacao`

- **Evidência:** `exportar.py:1839`, `1858`, `epub.py:860`, `escritor_docx.py:434`; o
  `_gravar_pdf` usa `.tmp` de nome fixo e não o apaga se `doc.save` falhar.
- **CA-Q-E4:** com `PermissionError` na primeira troca (o Word com o DOCX aberto), cada
  formato tenta de novo como `gravacao.gravar_bytes`; uma falha não deixa `.tmp` para trás.
- **Correção mínima:** `gravacao.gravar_por(caminho, escrever_no_tmp, conferir=None)`.

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

### Q-E6 (Melhoria) — um adaptador do Documento para a exportação

O que se construiria do zero: um `Pedido(projeto, opcoes)` resolvido uma vez (páginas,
idioma, metadados, números impressos) e a exportação consumindo `texto.montar`. `exportar.py`
(2 000+ linhas) se parte em montagem/margens (puras), PDF pesquisável, metadados e a porta
de entrada.

### Q-E7 (Média) — privados do core

`leitor.py:75,128,130` (`_predictor`, `_get_learner`), `verificacao.py:93,96`
(`lexico._ler`), `diagramas.py:231-232,330` (`TabuleiroEdicao._historico`, `_estado`,
`_indice`, `_registrar`); e regras copiadas do core (`exportar.py:703-720`, `1618-1639`,
`layout.py:298`). Contra o contrato do roadmap e a §18.2.
- **CA-Q-E7:** um teste de arquitetura reprova `._x` de módulos do PyBoxEditor fora de uma
  lista de exceções que encolhe; cada exceção tem um pedido em
  `docs/pedidos-ao-pyboxeditor.md` e um teste de contrato que fixa o comportamento usado.

## 6. Arquitetura

### Q-A1 (Média) — objetos-deus

| Classe | Tamanho | Corte proposto |
|---|---|---|
| `ControladorDePagina` (`controlador.py:138`) | 138 métodos, ~2 400 linhas; 9 das 15 funções mais complexas | `Navegador` (480-602), `ControladorDaSequencia` (§12.4, 604-1006), fila e margens para o `ControladorDaFila` que já existe, `PonteDeLeitura` (1533-1710), `AplicadorDoHistorico` (2177-2320), `ControladorDaSessao` |
| `ProjetoDeLivro` (`projeto.py`) | ~1 640 linhas | `CacheDePaginas` (com páginas presas, Q-P3), `ResumoDoLivro`, `Migracoes`, `Fonte` |
| `JanelaPrincipal` (`app/janela.py:72`) | 447 linhas, mas 9 mixins somam ~3 000 na MRO | composição: um objeto por painel, com só os controladores de que precisa |
| `exportar.py` | ~2 000 linhas | Q-E6 |

- **CA-Q-A1:** nenhum arquivo de `abbychess/` com mais de 1 000 linhas, nenhuma classe com
  mais de 40 métodos (teste de arquitetura, com o teto descendo a cada passo).

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
  par novo.

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

## 9. Mutação

Não medido: o `mutmut` 3 não roda no Windows sem `fork`; o `cosmic-ray` roda. A mutação de
31 mil linhas não cabe numa sessão, nem na regra de uma carga pesada por vez.
- **CA-Q-M1:** os módulos puros (`modelo`, `texto`, `lances`, `sequencia`, `historico`,
  `sessao`, `zonas`, `busca`) com ≥ 85 % de mutantes mortos, um módulo por sessão, só os
  testes que importam o módulo, `-n` ≤ 4; os sobreviventes viram teste ou código apagado.

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

### Q-T2 (Alta) — tempo de relógio e `sleep` como sincronização

- Asserções de tempo: `test_laco.py:134`, `test_gravador.py:43-52, 278`, `test_render.py:70`.
- `sleep` fixo como "o outro já chegou": `test_laco.py:57,84,129,146,151`,
  `test_servidor.py:80,90`, `test_render.py:67`, `test_busca.py:456`,
  `test_gravador_processo.py:53`.
- 14 laços `while … sleep` em 6 variantes de `_esperar`; o `qtbot` nunca é usado.
- **CA-Q-T2:** um teste de arquitetura reprova `time.sleep` e `perf_counter` em asserção na
  suíte rápida; a espera é uma só (`qtbot.waitUntil` ou um `esperar(cond)` do conftest), e os
  falsos sinalizam com `threading.Event`.

### Q-T3 (Média) — testes de implementação

- ~270 acessos a `_x` do código; os piores montam estado interno
  (`test_controlador.py:258,286,396,446`, `test_busca.py:369-391`,
  `test_documento.py:200-334`, `test_fechamento_l.py:308-313`, `test_janela.py:85`).
- Espiões que contam chamadas sem conferir o resultado
  (`test_texto_linhas_guardadas.py:81-107`, `test_gravador.py:338`, `test_visor.py:507,531`).
- **CA-Q-T3:** cada teste desses confere o resultado que o usuário veria; o estado é montado
  por API pública (ganchos de teste pequenos e nomeados, como `projeto.esvaziar_cache()`).

### Q-T4 (Média) — a pirâmide da §15.1 não é imposta

- O marcador `noturno` não é aplicado a teste nenhum; as máquinas de estado rodam na rápida com
  `timeout(600)` (`test_modelo_estados.py:327, 563`).
- Nenhum hook reprova a suíte rápida acima de 60 s; ela leva 100 s com cobertura.
- `test_fen_no_livro.py:67` pula quando a segmentação falha (uma regressão vira skip);
  `test_sessao.py:313` usa `times.ttf` sem guarda; ~40 % da suíte pula sem a Arial, sem aviso
  agregado.
- **CA-Q-T4:** `-m noturno` seleciona as máquinas com 5 000 exemplos e a rápida roda 100; um
  `pytest_sessionfinish` reprova a rápida acima de 60 s; o resumo da sessão conta os pulos por
  motivo.

### Q-T5 (Baixa) — o conftest central não existe de fato

32 `QApplication.instance() or QApplication([])` em 26 arquivos, ~180 imports
`from tests.test_X import …`, fixtures reimportadas com `# noqa: F811`, PDFs sintéticos
refeitos a cada teste, 25 testes de `test_janela.py` reconhecendo a mesma página.
- **CA-Q-T5:** nenhum `from tests.test_` nos testes; as fixtures de sessão (PDF, PNG, projeto
  já reconhecido copiado por `copytree`) baixam a suíte rápida para < 60 s com `-n 4`.

### Q-T6 (Melhoria) — onde falta propriedade

Hypothesis só em `test_modelo_estados.py`. Faltam: as edições fora das máquinas
(`dividir_em`, `estilizar`, `paragrafo`, virtuais, `juntar_varios`, `ajustar`, `revisar`); o
desfazer entre páginas com o gravador ("gravar, reabrir e comparar"); a sequência (reordenar,
apagar e restaurar preservam os pids); substituir e desfazer; o ida-e-volta de lances e FEN.

## 11. Código morto (sai antes de refatorar)

`projeto._arquivo_da_pagina`, `salvar_zonas`, `modelo.n_de`, `pagina.efeitos_de_impressao`,
o parâmetro `indices_v1` de `sq.da_v2` (sempre `()`), `app/documento.ir_ao_fim_do_gid`,
`app/painel_resultados.mostrar_glifos`, o `avisar` de `controlador._pode_ler`, o alias
`editar = tem` (`acoes.py:383`), `leitor.FONTE_LIVRO_FRACO`, `historico.descartar_desfazer`,
`descartar_refazer`, `emendou`. Os usados só por testes (`exportar.exportar`, `paragrafos`,
`migrar_tudo`, `grade.ACEITOS`, `diagramas.amostras_guardadas`) ficam se forem a porta que o
teste usa como o usuário; senão saem. Os 3 F401 de `camada.py` saem já (o portão).
- **CA-Q-Z1:** cada item é confirmado sem chamador por `git grep` (e pelo mutador, quando
  houver) e apagado num commit próprio; a suíte passa igual.

## 12. Fora do escopo

- Função nova da `docs/SPEC.md`.
- Editar o PyBoxEditor: o que precisar dele vira pedido em `docs/pedidos-ao-pyboxeditor.md`.
- Trocar de biblioteca (pydantic, msgspec): a validação de entrada é escrita à mão, com
  dataclasses, até um passo provar que não dá.

## 13. Decisões em aberto

1. **Q-P1:** migrar toda a v1 na abertura (some a migração preguiçosa) ou só passar a busca a
   pid? A primeira tira código; a segunda é menor.
2. **Faixas de páginas:** o "–" do lote e o "-" do diálogo são de propósito (mostrar contra
   digitar)?
3. **Q-P5:** o segundo processo abre só para leitura ou recusa?
4. **Q-E1:** a exportação passa a usar `texto.montar` inteira (Q-E6) já no primeiro passo, ou
   primeiro só as decisões?
5. **Teto da suíte rápida:** 60 s sem cobertura (como hoje na §15.1) e a medida com cobertura
   à parte?

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
