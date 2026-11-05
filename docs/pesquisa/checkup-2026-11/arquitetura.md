# Check-up de arquitetura do AbbyChessCraft

Ramo `lacunas-da-spec`, commit `262d897`, 2026-11-05. Só leitura no repositório.

## 1. Veredito

**O design está bom onde há dados e regras puras, e ruim onde há coordenação.** O núcleo do domínio (`modelo`, `Zona`, `sessao`, gravação atômica, migrações) é melhor do que a média. Já a camada que junta tudo (controlador e janela) só mudou de arquivo: as catracas baixaram a complexidade local, mas o acoplamento dobrou.

- **Crítico:** nenhum. Não achei defeito que destrua dados hoje.
- **Alto:** cinco achados. O mais urgente é um risco real de dados, confirmado por experimento, e tem correção pequena: uma página que o programa só *não entende* é tratada como corrompida (A1).
- **As catracas:** a de complexidade valeu. As de linhas e de métodos por classe medem a coisa errada e já estão piorando a coesão (§4).

### Como ler

- **Fato** é o que conferi no código, com `arquivo:linha` em `abbychess/`, salvo indicação.
- **Opinião** vem marcada como tal.
- **Li por inteiro:** `modelo`, `pagina_em_json`, `dados_do_projeto`, `pasta_do_projeto`, `app/janela`, `controlador`, `arrumacao`, `antes_do_lote` e os testes de arquitetura.
- **Li em parte:** `projeto`, `pagina`, `ponte_de_leitura`, `migracoes`, `zonas`, `diagramas`, `montagem`, `sessao_do_documento`, `app/documento`, `app/espaco`, `app/desenho`, `app/dialogos`, `app/galeria_na_janela`, `app/paginas_na_janela`.
- **Só por métricas de AST, sem julgar o conteúdo:** `sessao` (li só o cabeçalho), `historico`, `texto`, `lances`, `epub`, `escritor_docx`, `servidor_de_leitura`, `busca` e os demais.
- **Não rodei** pytest nem ruff (o ruff não está no venv). O vulture não está instalado; os candidatos a código morto vêm de um script aproximado, por nome.

## 2. Os números

Medidos por AST, com o `crapper` do projeto para a complexidade.

| Medida | `4accb7f` (análise anterior) | `262d897` (hoje) | Leitura |
|---|---|---|---|
| Linhas de `abbychess/` | 35.197 | 41.713 | +18,5 %, com funções novas no meio |
| Módulos | 86 | 122 | |
| Funções | 2.089 | 2.977 | +42 % |
| Complexidade ciclomática total | 9.900 | 10.987 | **+11 %** |
| Funções com cc ≥ 10 | 251 | 5 | ganho real |
| Maior cc | 62 | 15 | ganho real |
| Funções com cc de 5 a 9 | 426 | 976 | o que era grande virou médio |
| Nomes privados de função com uma única referência | 302 | 921 | fragmentos |
| Acessos a `_privado` em objeto que não é `self` | 115 | **230** | **dobrou** |
| Família `ControladorDePagina` (8 classes) | 138 métodos, 2.483 linhas | 195 métodos, 2.704 linhas | a classe caiu de 138 para 61; a família cresceu |
| Família `ProjetoDeLivro` (7 classes) | 101 métodos, 1.635 linhas | 142 métodos, 1.782 linhas | idem |
| MRO da `JanelaPrincipal` (10 classes) | 214 métodos, 2.637 linhas | **237 métodos, 2.717 linhas, 70 atributos** | não encolheu |
| `app/janela.py` | 497 linhas | 498 | teto de 500 |

Ressalva: o crescimento inclui funções novas, então a comparação não isola o efeito da refatoração. Mesmo assim, nenhuma das três famílias encolheu.

## 3. Achados

### Alto

#### A1. O formato do disco embute o core sem versão, e "não entendo" vira "corrompido"

**Fato.**
- `Box.para_json` grava `list(entry.as_state())` e `de_json` faz `BoxEntry.from_state(tuple(estado))` (`modelo.py:105,111`). O `from_state` é `cls(*estado)` (`core/box_model.py:101`). Portanto, o formato de `p<pid>.json` é a ordem dos campos de uma classe de outro repositório.
- O core já cresceu esse estado várias vezes (`core/box_model.py:90-93`).
- `ERROS_DE_PAGINA_ILEGIVEL` inclui `ValueError` e `TypeError` (`projeto.py:118`). `_gravada` manda qualquer um deles para `_isolar_a_ilegivel` (`projeto.py:404-408`), que move o arquivo para `.corrompido.json` e tira a página do `livro.json` (`projeto.py:416-423`).
- A trava de versão mais nova olha só o `projeto.json` (`projeto.py:236`). `VERSAO_DA_PAGINA` e `VERSAO` são constantes independentes (`pagina_em_json.py:20`, `pasta_do_projeto.py:19`).

**Experimento** (pasta temporária, `quarentena.py`), com projeto de versão atual:

| Cenário | `somente_leitura` | `carregar_modelo` | Pasta `paginas/` depois |
|---|---|---|---|
| Página com `versao: 4` | False | None | só `p0.corrompido.json` |
| `BoxEntry` com 12 campos (core mais novo que o instalado) | False | None | só `p0.corrompido.json` |

Log do segundo caso: `a página p0 está ilegível (BoxEntry.__init__() takes from 6 to 12 positional arguments but 13 were given)`.

**Custo.** Basta abrir um projeto gravado com um core mais novo usando um core mais antigo. Isso acontece, por exemplo, ao voltar o checkout do PyBoxEditor para bissectar. O programa abre o projeto *para gravar*, e cada página por onde passar (abrir, substituir, Galeria, exportar) vira "não reconhecida" e sai do `livro.json`.

Os bytes ficam guardados, mas o programa não tem como restaurá-los: a busca por `corrompido` só achou o código que grava. Um F5 começa a página do zero, e o `.corrompido.json` fica de lado.

O índice da busca não isola: ele ignora a página em silêncio (`busca.py:200-204`). `resumo_do_livro.py:115-119` e `sequencia_do_livro.py:254-258` também ignoram, e os três usam um conjunto de exceções sem `AttributeError`. Ou seja, o "um caminho só" do Q-P7 não vale para esses leitores.

Nenhum teste fixa `as_state`: `tests/test_contrato_do_core.py` só cobre os privados.

**Correção mínima** (cerca de 30 linhas, 2 testes).
1. Criar `PaginaDeOutraVersao`, levantada por `pagina_de_json` quando a versão é desconhecida e por `Box.de_json` quando `len(estado)` passa dos campos de `BoxEntry`.
2. `_gravada` não isola essa exceção: o projeto passa a só leitura, com o motivo. Quarentena só para JSON truncado ou forma inválida.
3. Um teste de contrato com um estado literal de 11 campos, conferido campo a campo.
4. Um teste que amarre `VERSAO_DA_PAGINA` a `VERSAO`, ou comentário e teste que digam por que são independentes.

#### A2. Os colaboradores do controlador vivem dele por `self._p`

**Fato.**
- `ControladorDePagina.__init__` cria sete colaboradores passando `self` (`controlador.py:147,161,169,174,176,181,183`).
- Acessos ao vizinho, medidos por AST (`coesao.txt`):

| Classe | Acessos a `self._p` | Deles a privados |
|---|---|---|
| `PonteDeLeitura` | 135 | 30 |
| `ControladorDaSessao` | 68 | 15 |
| `ControladorDaSequencia` | 63 | 13 |
| `ControladorDosPadroes` | 61 | 9 |
| `AplicadorDoHistorico` | 53 | 5 |
| `FilaDaPagina` | 43 | 0 |

- Dos 230 acessos cruzados a privados, 169 vão ao controlador ou ao projeto. Os mais usados: `_avisar` 75, `_falhou` 17, `_trava_do_livro` 13, `_gravar` 10, `_mudou` 8.
- Colaborador escreve estado do dono: `self._p.atual, self._p.pulados, self._p.selecao = None, set(), set()` (`ponte_de_leitura.py:126`).
- A dívida foi registrada e não foi paga: "ficam para o Q8" (`docs/revisoes/qualidade-Q7.md:92,100`). `qualidade-Q8.md` não trata do assunto (busquei `self._p`, `_p._` e `privados`), e o número subiu.

**Custo.** O `_` não informa mais nada, porque `_avisar` é a API mais usada do pacote. Nenhuma dessas classes se testa sem o controlador inteiro. `controlador.py` é o arquivo que mais muda (38 dos últimos 250 commits que tocaram `abbychess/`), e muda junto com `desenho` (8), `janela` (8) e `galeria_na_janela` (7).

**Correção mínima.**
1. Promover a nomes públicos, num commit mecânico, o que já é API de fato: `avisar`, `falhou`, `mudou`, `gravar`, `instantaneo`, `agora`, `editar`, `cinza`, `pode_ler`.
2. Criar uma catraca nova: o total de acessos cruzados a privados só desce, a partir de 230 menos os promovidos.
3. Criar um `PaginaAberta` com `indice, imagem, matriz, modelo, atual, pulados, selecao, escolhido`, com um `zerar()` no lugar dos resets repetidos (`controlador.py:345-346,370`, `ponte_de_leitura.py:126`).

**Opinião.** Não vale introduzir injeção de dependência por interface agora; os itens 1 e 3 pagam a maior parte.

#### A3. A `JanelaPrincipal` é uma classe de 237 métodos em 10 arquivos, sem interface declarada

**Fato.**
- MRO em `app/janela.py:72-74`. O teste mede só as linhas de um arquivo (`tests/test_arquitetura.py:61-63`) e os métodos de cada classe isolada (`tests/test_tamanho_dos_modulos.py:33`).
- O motivo do mixin está escrito: "separada para a janela ficar com a montagem [...] (CA-14.1: `janela.py` < 500 linhas)" (`app/desenho.py:3-4`).
- Desde o `4accb7f`, `janela.py` foi de 497 a 498 linhas, `desenho.py` de 341 a 421 e `espaco.py` de 745 a 820.
- Dependência implícita, em nomes `self.X` que a classe usa e não define: `DesenhoDaJanela` 43, `EspacoDeTrabalho` 36, `JanelaPrincipal` 75.
- Estado compartilhado entre mixins: `_posicao` em `BuscaNaJanela` e `SubstituirNaJanela` (`app/substituir_na_janela.py:87`), `_ultima_troca` (`app/janela.py:142`, `app/desenho.py:46`), `_mensagem_da_tarefa`.
- Ordem de montagem contornada por sondagem: `hasattr(self, "busca")` (`app/desenho.py:198`), `getattr(self, "_espaco_ja_de", None)` (`app/janela.py:293`).
- A mesma coisa em dois lugares por causa do teto: `modo_treino` e `modo_areas` em `app/janela.py:425,433`, `modo_borracha` e `_so_um_modo` em `app/paginas_na_janela.py:69,79`.
- O CA-14.1 não vale onde `qualidade-Q8.md:205` diz que vale: o teste olha só `janela`, `desenho` e `espaco` (`tests/test_arquitetura.py:66-73`). Aplicando a mesma função aos outros sete: `PaginasNaJanela` 27 violações, `GaleriaNaJanela` 15, `EdicaoNoDocumento` 4, `BuscaNaJanela` 3.

**Custo.** Para mexer na janela é preciso ter 2.700 linhas na cabeça. Sem verificador de tipos, renomear um método de mixin só falha quando o caminho roda. Reverter isso também é caro: os testes usam 201 nomes distintos de `janela.`/`j.`, em 1.981 usos.

**Correção mínima.**
1. Trocar a régua: teto no total da MRO (237 métodos, 70 atributos), que só desce, no lugar das 500 linhas.
2. Estender o teste do CA-14.1 aos dez, com uma lista de exceções que só encolhe.
3. Juntar os três modos do arraste num lugar.

**Opinião.** Não reescreva. Quando uma função tocar a Galeria, converta esse mixin em objeto composto, mantendo `janela.abrir_galeria` como delegação. Ela é a candidata natural: 19 métodos, 5 atributos, só 9 nomes externos.

#### A4. Ciclo de 16 módulos, escondido por importações tardias

**Fato** (`grafo.py`, `grafo.txt`).
- Pelos imports de topo, não há ciclo nenhum. Contando os imports dentro de funções, há um componente de **16 módulos**: `antes_do_lote, cache_do_projeto, contexto, diagramas, fonte_do_livro, geometria_do_modelo, lances, leitor, migracoes, pagina, pagina_em_json, projeto, resumo_do_livro, sequencia_do_livro, texto, zonas`.
- Há mais três pares: `edicao`↔`editar_boxes`, `epub`↔`marcacao`, `app.documento`↔`app.painel_treino`.
- São **185 imports internos tardios**, mais 76 do core. Não achei em `tests/` nenhum teste de camada nem de ciclo de imports; o que vigia import de `abbychess/` é o de Qt (`tests/test_arquitetura.py:88`).
- Camadas invertidas: `zonas` importa `pagina` (`zonas.py:360,809,823`), `livro` importa `controlador` (`livro.py:168`), `leitor` importa `projeto` (`leitor.py:30`).
- Parte dos tardios não tem motivo aparente: `geometria_do_modelo` importa `geometria` tarde dez vezes, e `geometria` não depende de ninguém.
- Fan-in inflado: `FONTE_*` e `precisa_revisao` moram em `leitor.py:32-38` (22 importações de `leitor`), e 8 módulos de `app/` importam `AVISO_LONGO_MS` de `controlador` (`app/janela.py:56` e outros), embora ele more em `avisos.py:31`.

**Simulação** (`cortes.py`, cortes cumulativos, sem contar arestas de módulos novos):

| Cortes | Componente |
|---|---|
| Hoje | 16 |
| `leitor→projeto` (`Limiares` já mora em `dados_do_projeto`; `nome_de_pasta` desce) | 15 |
| `sequencia_do_livro→projeto` (mover `ProjetoInvalido` para baixo) | 15 |
| `fonte_do_livro→projeto` (idem) | 14 |
| `zonas→pagina` (tirar `segmentar*` de `zonas` e `MARGEM_DO_TABULEIRO` de `pagina`) | **4**: `diagramas, lances, texto, zonas` |
| Também `texto→diagramas`, `lances→diagramas`, `zonas→diagramas` | **0** |

**Custo.** O `ImportError` vira erro em tempo de execução, em caminho raro. Não dá para raciocinar em camadas, nem extrair uma delas. E um corte como o do Q7 acrescenta ciclo sem ninguém ver.

**Correção mínima.** As quatro arestas num passo. Depois, um teste de AST com as camadas permitidas, o tamanho máximo de componente e o número de imports tardios como catracas.

#### A5. Dois caminhos para o mesmo texto: o Documento e a exportação

**Fato.**
- A SPEC diz "Lê o Documento (§4.2), não os boxes" (`docs/SPEC.md:768`).
- O código diz o contrário: "A montagem das linhas e dos parágrafos continua a desta exportação" (`montagem.py:62`). O `Estrutura.da_pagina` é um adaptador com mais de dez campos chaveados por `id()` e uma lista `vivos` só para manter os ids válidos (`montagem.py:68-97`).
- As palavras saem do Documento quando dá, e da geometria quando não dá (`montagem.py:276-280`).
- Medido pelo projeto: 95,0 % das palavras em comum, em 81 trechos diferentes (`docs/SPEC-qualidade.md:352-358`).
- A decisão §13.9 aprofundou a bifurcação: a caixa pela altura tem uma regra inteira na exportação e outra parcial na leitura (`montagem.py:270`, `arrumacao.py:41`).
- O CER oficial lê as linhas da exportação, não o Documento (`SPEC-qualidade.md:365`).

**Custo.** Toda regra de texto se decide duas vezes. O usuário corrige e vê um texto, e o livro exportado pode sair com outro. Este é o único caso da lista que muda o que o usuário recebe, e o projeto já sabe dele (Q-E6). Eu o elevo porque a §13.9 mostra que a distância está sendo administrada, não reduzida.

**Correção mínima.** Sem refazer nada agora: pôr a porcentagem de palavras iguais entre Documento e exportação em `ferramentas/qualidade.py`, como catraca que só sobe. O fim é a correção da caixa e a junção do hífen virarem uma função sobre o Documento, que a exportação consome. Isso pede decisão do usuário, porque muda o texto exportado.

### Médio

#### M1. Tipos primitivos para o que já deu defeito, e nenhum verificador de tipos

**Fato.**
- `grep` por `NewType|Protocol|TypedDict|Literal[` em `abbychess/` não acha nada. Os únicos enums são `Estado` e `Notacao`. Não há mypy nem pyright em `pyproject.toml`, `ferramentas/`, `tests/`, `docs/` ou `plans/`.
- `indice` é a posição no livro em `modelo.Pagina` (`projeto.py:482-487`) e a página do PDF no JSON (`pagina_em_json.py:37-38`). O Q-P1, de severidade alta, foi exatamente a troca entre posição e pid.
- Anotações que mentem sem ninguém acusar:
  - `hs.Instantaneo` não existe (`controlador.py:759`); foi "anotado, não mudado" no Q8.
  - `boxes: List[Box]` recebe tupla (`modelo.py:364,418`).
  - `estado: str` é um `Estado` (`modelo.py:369`).
- O executor é um protocolo implícito, sondado por `getattr` (`controlador.py:531-532`, `controladores.py:488`, `lote.py:268`).

**Correção mínima.** `Pid = NewType(...)` e `Posicao = NewType(...)`, mais pyright em modo básico só em `modelo`, `sequencia`, `historico`, `arrumacao`, `pagina_em_json`, ampliando aos poucos. Um `Protocol` para o executor.

#### M2. A função da área e a fonte da leitura são strings soltas

**Fato.**
- Literais fora de uma definição: `'legenda'` 23 vezes em 9 arquivos, `'titulo'` 23 em 11, `'cabecalho'` 15 em 10, `'numero_de_pagina'` 14 em 9, `'rodape'` 13 em 9.
- "O que é margem" tem definições separadas: `app/documento.py:59`, `montagem.py:54`, `lances.py:62` (superconjunto), `zonas.py:690`.
- Este ramo acrescentou uma cópia de `zonas.FUNCOES` em `app/editor_de_area.py:16`. `tests/test_regras_unicas.py` diz cobrir as letras das peças, o idioma e os trechos marcados, não isto.
- A fonte da leitura se classifica por substring: `"learner" in fonte`, `fonte.startswith("base")` (`busca.py:712-718`). `FONTE_AGUARDANDO = ""` (`leitor.py:38`) dá um sentido novo ao `source == ""` do core, que lá quer dizer "não avaliado" (`core/box_model.py:30-32`).

**Custo.** Uma comparação com erro de digitação dá `False` em silêncio. O `Zona.__post_init__` valida a construção, não as comparações.

**Correção mínima.** `Funcao(StrEnum)`, a mesma receita do `Estado`, com os conjuntos `MARGENS` e `FORA_DA_EXPORTACAO` definidos uma vez em `zonas`. Estender `test_regras_unicas`.

#### M3. O resumo da página é um dict cru, e `extras` guarda campos conhecidos

**Fato: o resumo.** `do_livro()` devolve `Dict[int, dict]` (`resumo_do_livro.py:57,194-207`), lido em cerca de 14 lugares só por `estado` e `pendentes`, às vezes com `int(... or 0)` (`controlador.py:471`, `app/espaco.py:702`, `app/lote_na_janela.py:31`, `exportar.py:256,345`, `livro.py:93,214`, `pedido.py:116`, `app/painel_paginas.py:308-310`).

**Fato: `extras`.** O comentário diz "os campos que esta versão não conhece" (`dados_do_projeto.py:73-75`). Na prática guarda sete chaves que o programa conhece: `intervalo_do_corpo`, `amostra_guiada_pendente`, `candidatos_da_amostra_guiada`, `paginas_da_amostra_guiada`, `pendentes_iniciais_da_amostra`, `limiar_de_pendentes_da_amostra`, `paginas_da_camada_nativa`. São escritas até do `app/` (`app/dialogos.py:204,253-255`). O tipo interno não é validado: `TIPOS_DO_PROJETO` só confere que `extras` é dict (`dados_do_projeto.py:92`), e `livro.py:78` faz `int(extras.get(...))` em tempo de execução. **O CA-Q-P6 ("para cada campo") fica furado aí.**

**Correção mínima.** Uma dataclass `ResumoDaPagina` e um `AmostraGuiada` como campos de verdade, passando pela mesma conferência da entrada.

#### M4. Estados ilegais no modelo da página

**Fato.**
- Três representações do mesmo tabuleiro: `tabuleiros` e `diagramas` em listas paralelas (`modelo.py:365-366`, juntadas por `para_caixas` em `controlador.py:241`), mais a `Zona` de tipo diagrama.
- `areas_fora` são 4-tuplas com a string do tipo (`modelo.py:380-384`, `pagina_em_json.py:96-102,117-126`).
- `instantaneo` lista os campos à mão (`modelo.py:418-423`). `pagina_para_json`, `pagina_de_json` e `vazia` fazem o mesmo. Um campo novo esquecido no instantâneo some do desfazer em silêncio.
- `lado_origem` é string, definida em módulos diferentes (`diagramas.py:57-58`, `lances.LADO_DOS_LANCES`, e `"convencao"` no core).
- `ControladorDePagina.cache` só nasce em `ligar` (`controlador.py:340`), e `app/paginas_na_janela.py:38` captura `AttributeError` ali perto.

**Correção mínima.** `dataclasses.replace(self, boxes=tuple(self.boxes), ...)` em `instantaneo`, só para os campos que são listas. O resto, só quando o código for tocado.

**Opinião.** Unir `tabuleiros` e `diagramas` paga, mas é migração de formato: fica para quando houver outra razão de subir a versão.

#### M5. Uma API de gravação inteira só para os testes

**Fato.**
- `salvar_pagina` tem 0 chamadas em `abbychess/` e `ferramentas/`, e 95 em `tests/`.
- Os comentários dizem que ela é "para o lote, as ferramentas e os testes" (`projeto.py:36-38`) e "(o lote, as ferramentas)" (`modelo.py:453-454`). O lote usa `aplicar_lida` (`lote.py:387`).
- `salvar_zonas` só nos testes. `gid_do_box` só no ramo `gid is None` de `pagina.ensinar` (`pagina.py:920-921`), e a produção passa o gid (`ponte_de_leitura.py:316-317`).
- As fotos existem para esse caminho (`cache_do_projeto.py:4,201-210`, `projeto.py:333,534,568`; "A foto é das gravações síncronas", `projeto.py:331`).

**Custo.** Os testes montam estado por um escritor que a produção não usa. O parâmetro `estados` de `reconciliar` (só `projeto.py:567` o passa; `arrumacao.py:44` não) e as fotos do cache ficam presos a isso.

**Correção mínima.** Mover `salvar_pagina`, `gid_do_box`, `salvar_zonas` e `_reconciliar` para `tests/ajudantes.py`, com a ferramenta `mover_definicoes` do projeto; `pagina.ensinar` passa a exigir o `gid`. `ProjetoDeLivro` iria de 43 para 39 métodos e **sairia de `TETOS`** sem empurrar nada. O Q-Z1 aceitou essa porta de teste; minha opinião é que já custa mais do que vale.

#### M6. Sobras de lógica no `app/` (Q-A2)

O CA-Q-A2 foi cumprido: `EstadoDaJanela` não tem Qt, e `aplicar_lida` é usada pelo F5 e pelo lote (conferi). O resto da evidência do próprio Q-A2 continua lá, sem registro de "feito":

- Criar projeto grava estado de domínio no diálogo (`app/dialogos.py:194-206,249-256`).
- A ordem de fechar está na janela (`app/janela.py:324-344`).
- Uma thread própria, fora do executor, lê páginas (`app/galeria_na_janela.py:156-181`).
- O controlador chama de volta a janela para confirmar a sessão (`controlador.py:164,357,444`, `app/janela.py:180`).
- O `app` chama privados do controlador (`app/substituir_na_janela.py:72,84`).
- `DesenhoDaJanela` diz "nenhum decide nada" (`app/desenho.py:5`), mas decide (`app/desenho.py:52-55`).

**Correção mínima.** `ControladorDoLivro.criar_projeto(opcoes)` e `.fechar()`, com os diálogos só perguntando; os recortes da Galeria como `tarefa`.

#### M7. Core sem pino e sem fronteira

**Fato.**
- O core nem é dependência declarada (`pyproject.toml:11-12,16-17`). É instalação editável de um checkout, hoje com 4 arquivos não versionados e sem mudança em arquivo versionado.
- 43 módulos importam `core`; 28 importam `BoxEntry`. Os acessos a `.x1 .y1 .x2 .y2 .char` são 724, contados por nome (inclui `Zona`, que tem as mesmas coordenadas).
- A medida grava o commit do projeto, não o do core (`ferramentas/comum.py:25-37`, `docs/medidas/2026-11-05-medida.json`). A SPEC só pede o "commit" (`docs/SPEC.md:1116`).
- Regras repetidas à mão: `DPI_DA_LEITURA = 300` (`montagem.py:26`) contra `DPI_PADRAO` (`core/services/pdf_service.py:54`), que `camada.py:81` importa; `SALTO_DE_PARAGRAFO = 1.6` (`montagem.py:31`) contra `0.6` no core (`core/pagina.py:36`).

| Mudança no core | Como o projeto sobrevive hoje |
|---|---|
| Renomear um dos 9 privados usados | Bem: o teste de contrato reprova |
| Crescer `as_state` | Lendo projeto antigo, bem. Na direção contrária, A1 |
| Mudar a ordem de `as_state` | Mal: leitura errada em silêncio, se a quantidade bater |
| Renomear campo de `BoxEntry` | 28 módulos |
| Mudar o comportamento de `palavras_da_pagina` ou `sort_boxes_reading_order` | Só golden e medidas pegam; sem o commit do core na medida, a diferença aparece atribuída ao código do projeto |

**Correção mínima.** Gravar o commit e o estado sujo do core em `ambiente`, e o portão reprovar se ele mudou desde a medida de referência. Declarar o `pyboxeditor` no `pyproject`. Estender os testes de contrato a umas dez funções públicas.

**Opinião.** Não faça uma fachada geral: `BoxEntry` é um núcleo compartilhado de fato, e o `modelo` já o compõe bem. Um adaptador custaria centenas de trocas para proteger de um risco pequeno.

### Baixo

**Comentários que mentem** (além dos já citados):
- `projeto.py:539` diz "O único lugar que grava `p<pid>.json`", mas `antes_do_lote.py:68` e `sequencia_do_livro.py:620` também gravam. Não achei corrida (o primeiro descarrega o gravador antes, o segundo é pid novo). Só a afirmação é falsa, e o princípio 4 da SPEC-qualidade pedia a regra imposta pela estrutura.
- `modelo.py:449,469` ("a janela de hoje edita por índice", "a janela muda o `BoxEntry` no lugar") contradiz `modelo.py:454-455` e `modelo.py:415-417`.
- `projeto.py:3` diz "formato 2", e `VERSAO` é 3.
- `app/janela.py:22-23` cita 2 módulos de controladores, e hoje são seis, fora os colaboradores.
- `tests/test_tamanho_dos_modulos.py:15` ainda fala do Q7 em andamento.
- `docs/SPEC.md:1009-1011` descreve 3 controladores.
- `pyproject.toml:13-15` diz que o YAML vira dado do pacote no passo A2. Ele não virou (`atalhos.py:31` lê `docs/`, e o `package-data` só tem ícones): uma instalação fora do checkout não acha os atalhos.

**Código morto** (script por nome, aproximado):
- `FonteDePaginas.fixar_inclinacao` (`pagina.py:227`) não tem nenhuma chamada.
- Só com teste ou ferramenta: `pg.descartar` (`pagina.py:987`), `pg.texto` (`pagina.py:992`), `modelo.n_de`, `padroes.amostras_de`.

**Parâmetros e funções longas:**
- `DialogoDasPaginas.__init__` com 14 parâmetros (`app/dialogo_paginas.py:51`), `epub._capitulos` 11 (`epub.py:313`), `exportar._escrever_formatado` e `epub._opf` 10.
- `exportar_docx` tem 10 parâmetros mesmo com `Pedido` existindo (`exportar.py:457`).
- `acoes.montar` tem 264 linhas (`app/acoes.py:16`), mas é tabela de ligação: não mexeria.
- 96,7 % das funções têm até 30 linhas.

**Nomes:**
- `pagina` significa a matriz (`pagina.py:822`), o número (`pagina.py:904`), o modelo (`ponte_de_leitura.py:90`) e o controlador (`app/janela.py:88`).
- `fonte` é o `FonteDePaginas`, o caminho, a origem da leitura e o campo de metadados.
- `self._p` é o controlador em algumas classes e o projeto em outras.

**Eventos:** são 41 nomes em string, sem registro. Hoje meu cruzamento por AST não achou nenhum órfão, mas ninguém o faz: `servidor_caiu` sai por variável (`controlador_do_livro.py:127`). Um teste de AST de 20 linhas resolve.

**python-docx:** `paragrafo._p` e `run._r` (`escritor_docx.py:121,163`) também são privados de terceiro, fora da catraca de privados do core.

## 4. As catracas: reduzem ou empurram?

| Catraca | Veredito | Evidência |
|---|---|---|
| Complexidade (`test_complexidade.py`, cc < 10) | **Reduziu de verdade, localmente.** A total subiu 11 % | cc ≥ 10 de 251 para 5; máximo de 62 para 15. O preço: cc 5 a 9 dobrou, e privados de referência única triplicaram |
| Privados do core (`test_privados_do_core.py`) | **Boa, mantém** | Minha varredura independente não achou nada fora dos 9 da lista |
| Linhas por arquivo (1.000) | **Mista.** Forçou bons cortes e também cortes por aritmética | Bons: `validacao_do_epub`, `links_internos`, `dados_do_projeto`, `pedido`. Mecânicos: "partir levava o `projeto.py` a 1 021 linhas" (`qualidade-Q8.md:103`); "o arquivo passou de 1 000 linhas ao partir" (`geometria_do_modelo.py:6`); "perdeu uma linha [...] um `p, projeto` numa linha" (`qualidade-Q7.md:106`) |
| Métodos por classe (40) | **Empurra** | "funções: a classe não cresce", escrito três vezes (`app/documento.py:891`, `app/espaco.py:736`, `app/visor.py:752`). Essas funções são métodos com outro nome: `_escrever_as_linhas(vista, ...)` tem 10 parâmetros e lê `vista._linha_do_gid` (`app/documento.py:893-914`); `janela._foco_antes_dos_resultados` (`app/espaco.py:759`) |
| 500 linhas em `janela.py` | **Empurra, sem ganho** | A MRO cresceu 23 métodos com o arquivo parado. A memória do projeto já diz: "método novo de janela vai para `DesenhoDaJanela` ou um `*_na_janela`" |

**Pressão de agora:** `pagina.py` 1.000 linhas (exatamente no limite), `sessao.py` 992, `app/documento.py` 992, `controlador.py` 950, `montagem.py` 942. A próxima função em qualquer um deles vai forçar um corte mecânico.

**Objetos-deus, um a um:**

| Objeto | Juízo |
|---|---|
| `controlador.py` | **Segue central.** A classe caiu pela metade, mas é ela que os colaboradores chamam, e é o arquivo que mais muda (A2) |
| `projeto.py` | **Melhor que o controlador.** Os pedaços são coerentes (`Migracoes`, `ResumoDoLivro`, `pagina_em_json`), mas alcançam privados (`_trava_do_livro` 13 vezes). 4 métodos só para teste (M5) |
| `janela.py` e `espaco.py` | **Continuam deus**, em dez arquivos (A3) |
| `pagina.py` | **Balaio sem estado**, baixo risco: fonte de imagens e cache (`:109-565`), segmentação (`:593-798`), leitura e ensino (`:812-1000`). Partir nesses três paga também o corte `zonas→pagina` |
| `sessao.py` | **Não é deus** pelo que vi: o cabeçalho descreve um pipeline sem Qt (realinhar, planejar, aplicar). Não li o corpo; só a pressão do teto é problema |
| `montagem.py` | **Coeso em torno da exportação.** O defeito é existir em paralelo ao Documento (A5) |

**Proposta (opinião).** Manter a de complexidade e a de privados do core. Trocar a de 500 linhas e a de métodos por classe por réguas de acoplamento: total da MRO, acessos cruzados a privados, tamanho do maior ciclo, imports tardios. Manter as 1.000 linhas só como alarme.

## 5. A análise anterior: o que segue de pé

| Item | Declarado | Hoje |
|---|---|---|
| Q-P1, Q-P2 (v1 por pid, sobra) | Feito | Segue (`migracoes.py:83-108`) |
| Q-P4 (escritor único) | Feito | **Em parte:** o caminho comum sim, mas o comentário "único" é falso (Baixo) |
| Q-P6 (`projeto.json` validado) | Feito | **Em parte:** `extras` por dentro não (M3) |
| Q-P7 (ilegível por um caminho só) | Feito | **Em parte:** outros três leitores têm política própria; e a regra confunde corrompido com desconhecido (A1) |
| Q-P8 (ler não grava) | Feito | Segue (`sequencia_do_livro.py:57-66`) |
| Q-P9 (`Estado`, `Notacao`, fonte única) | Feito | Segue. Literais de estado fora do `modelo`: só o rótulo em `app/painel_paginas.py:35-37` e uma constante de outro sentido em `lote.py:46` |
| Q-C4 (erros engolidos) | Feito | Teste presente (`tests/test_arquitetura.py:160`) e `Eventos.emitir` correto (`controlador.py:88-95`) |
| Q-E5 (`PECAS` única) | Em parte | Segue; a regra das funções de área não está coberta (M2) |
| Q-E6 (exportação pelo Documento) | Medido, não feito | Aberto (A5) |
| Q-E7 (privados do core) | Feito | **Confirmado de forma independente** |
| Q-A1 (objetos-deus) | Fechado com tetos | A regra passa, o objetivo não: §4 |
| Q-A2 (app decide regra) | Feito o CA | CA ok; a evidência restante continua (M6) |
| Q-A3 (decisões duplicadas) | Feito | Segue: `8000` só em `avisos.py:31` |
| Q-Z1 (código morto) | Feito | Surgiu `fixar_inclinacao`; a API de teste é maior do que parecia (M5) |

## 6. O que está BOM e não deve ser mexido

- **Qt isolado:** nenhum import de Qt fora de `app/` (conferido por AST), com teste (`tests/test_arquitetura.py:88`).
- **`modelo.py`:** fan-in 32, fan-out 0 (só depende do `BoxEntry`). `Decisoes` imutável com `reescrever`. Máquina de estados em tabela (`modelo.py:322-351`). Compõe o `BoxEntry` em vez de herdar.
- **`Zona`:** valida a coerência entre tipo e função na construção (`zonas.py:149-157`). É o molde certo.
- **Gravação:** `gravacao` atômica, bilhetes por conteúdo (`projeto.py:538-546`), trava entre processos, projeto de versão nova só para leitura (`projeto.py:236`), `extras` preservando o desconhecido, backups de migração.
- **O pipeline de leitura:** `arrumacao.aplicar_lida` única para F5 e lote (`lote.py:387`, `ponte_de_leitura.py:119`).
- **`estado_da_janela`:** a política das ações sem Qt.
- **`ExecutorSincrono`** (`controlador.py:98-122`): a costura que faz os controladores testáveis sem janela.
- **O padrão dos testes de arquitetura:** cada regra tem um teste que prova que ela pega a violação (`tests/test_arquitetura.py:76`, `test_tamanho_dos_modulos.py:54`, `test_privados_do_core.py:108`). Isso é raro e deve ser copiado nas réguas novas.
- **Os cortes por assunto da exportação:** `pedido`, `metadados`, `margens`, `pdf_pesquisavel`, `validacao_do_epub`, `links_internos`.
- **Disciplina de commit:** média de 2,6 arquivos de `abbychess/` por commit, nos últimos 250.

**Decisões a manter (opinião):** não adotar pydantic, não criar fachada sobre `BoxEntry`, não reescrever a janela de uma vez.

## 7. Evolução

### O que hoje torna caro mudar

1. **Uma regra de texto:** decide-se no Documento e na exportação (A5).
2. **Um comando novo de janela:** "Editor Área" tocou 5 arquivos (`e1c742f`), "Borracha" tocou 10 (`7af3eb3`), e o lugar do método é decidido pelo teto, não pelo assunto.
3. **Qualquer serviço do controlador:** muda a chamada em até sete colaboradores (A2).
4. **O core:** sem pino, e com o formato de disco preso a ele (A1, M7).
5. **Um campo novo na página:** `Pagina`, `instantaneo`, `pagina_para_json`, `pagina_de_json`, `vazia` e às vezes o resumo, sem nada que acuse o esquecimento.
6. **Posição contra pid:** sem tipo, só a atenção de quem escreve impede o erro.

### As 5 refatorações que mais pagam

Em ordem de retorno por custo. As estimativas de custo são opinião.

| # | Refatoração | Achados | Custo | Retorno |
|---|---|---|---|---|
| 1 | **Fronteira de dados e core:** `PaginaDeOutraVersao`, contrato de `as_state`, commit do core na medida | A1, M7 | Pequeno: cerca de 30 linhas e 3 testes | Fecha o único risco real de dados; as medidas ficam atribuíveis |
| 2 | **Cortar o ciclo:** as 4 arestas, depois as 3, partir `pagina.py` em três; teste de camadas e catraca de tardios | A4 | Pequeno a médio: 1 ou 2 sessões, mecânico | Componente de 16 para 0; alivia o teto de `pagina.py`; dá o mapa de camadas que falta |
| 3 | **Serviços públicos do controlador e `PaginaAberta`:** renome mecânico, nova catraca | A2 | Médio: cerca de 170 trocas com ferramenta | O acoplamento fica visível e mensurável; os colaboradores passam a poder ser testados e encolhidos |
| 4 | **Tipos nas fronteiras:** `Funcao`, `Pid`, `Posicao`, `ResumoDaPagina`, `AmostraGuiada`, pyright parcial; `instantaneo` por `replace`; a API de teste para `tests/` | M1 a M5 | Médio, fatiável, um tipo por commit | Tira as classes de erro que já custaram defeito de severidade alta; `ProjetoDeLivro` sai do teto |
| 5 | **Um texto só:** catraca da divergência já; depois a caixa e o hífen como função sobre o Documento | A5 | Grande, com golden de cada formato e decisão do usuário | Fim da decisão dupla; a §12.1 passa a ser verdade |

**Fora dos cinco, de propósito:** a composição da janela (A3). Ela é a dívida mais visível, mas é a mais cara e a que menos perde dado. Agora, faça só o barato: trocar a régua, estender o CA-14.1 e juntar os modos do arraste. A conversão pode seguir mixin por mixin, começando pela Galeria, quando uma função tocar o mixin.

**Ordem e cuidado.** O 1 vem antes de tudo, e o 2 antes do 3 (o mapa de camadas orienta os cortes). Cada passo usa o golden da exportação como pino, com uma carga pesada por vez e sem editar a worktree durante as medidas.

## 8. Anexos

Todos no scratchpad desta sessão:

- `grafo.py`, `grafo.txt`, `grafo.json`: grafo de imports, ciclos, fan-in e fan-out.
- `metricas.py`, `metricas.txt`: classes, funções, parâmetros e literais.
- `coesao.py`, `coesao.txt`: MRO, retro-referências e privados cruzados.
- `extra.py`, `extra.txt`: privados do core, arestas do ciclo e eventos.
- `comparar.py`: `4accb7f` contra `HEAD`.
- `closures.py`: a regra do CA-14.1 nos outros mixins.
- `cortes.py`: a simulação dos cortes.
- `quarentena.py`: o experimento do A1.
- `mortos.py`, `mortos.txt`: candidatos a código morto.
