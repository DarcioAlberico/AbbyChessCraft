# Passo 0 — revisões de fechamento

2026-10-16. O contrato do roadmap pede três revisões (código, produto/design, medição) com
nota ≥ 8 em cada eixo. O passo 0 não mexe na interface, então a revisão de design ficou
dentro da de produto e medição.

## Rodada 1

| Revisor | Notas | Veredito |
|---|---|---|
| Código e testes | Correção 6 · Simplicidade 7 · Testes 6 | volta |
| Produto e medição | Completude 6 · Fidelidade das medidas 5 · Clareza para o usuário 6 | volta |

O que mudou depois dela:

| Achado | Correção |
|---|---|
| `sem_atalho` sem efeito; tecla de vários caracteres não normalizada; só letras na regra 3 | `abbychess/atalhos.py`: `sem_atalho` tira a ação do perfil e reprova sequência junto; `F1`–`F24` e nomes canônicos, tecla desconhecida ou vazia é erro; qualquer caractere sem Ctrl/Alt reprova em escopo editável; F10 e Alt+F4 reprovam |
| Exceções obsoletas passam; ciclo em `dentro_de` | exceção sem sequência, fora do escopo ou do lado errado do nativo reprova; ciclo e pai inexistente reprovam |
| Cabeçalho medido contra a classe errada; blocos da mesma linha | `medir.py`: rodapé conta, a poeira não; blocos unidos por linha |
| Ordem pela posição na lista | pela `ordem` do bloco no gabarito; a métrica se chama `ordem_discordancia` |
| Medidas de estrutura como válidas | `estado: provisória` e `gabaritos_revisados` no resultado |
| `✝` como substituição falsa; palavras recontadas pelo texto | `replay_fatia.py`: `normalizar_saida` antes de comparar; palavra de cada box pelo `exportar.palavras` |
| Fatia com 0 gestos | sem linha verificada, `gestos: null` e `estado: pendente`; diagramas à parte; diagrama sem confiança é sempre conferido; lado a jogar errado custa `corrigir_lado` |
| Catálogo incompleto; impossíveis fora da soma | dividir, juntar, lado e trocar de página no catálogo (todos conferidos por QTest); impossíveis com custo fixo declarado; `convencao_de_gestos`; `comparar` recusa conjuntos de linhas diferentes |
| Premissa do contador de gestos | teste próprio: o evento que sobe para o pai não é espontâneo |
| `texto-importar` estragava blocos de várias linhas | junta as linhas do bloco; sobe `verdade_versao`; exige `--por`; o exportar não sobrescreve `.txt` mais novo |
| Portão e xfail; skip na preparação | xfail continua xfail; teste com `skipif` e fixture |
| Enter fora do método; memória do desfazer inflada; lote de 3 páginas | 5/30 repetições ensinando um caractere novo; memória pelo que o histórico prende (RSS) e pelo que volta ao esvaziá-lo; lote de 20 páginas; "fora do cache" declarado como não medido |
| README com números digitados e sem roteiro | tabelas geradas por `ferramentas/resumo_medidas.py`; "O que falta você fazer"; 13 diagramas e as páginas negativas nomeadas |
| Faltava `docs/medidas/protocolo-fatia.md`; conferência cega de diagrama | escrito; a conferência cega cobre 1 diagrama por livro (spec §15.2 e protocolo) |
| Menores | `\\a` na mensagem; parâmetros de teste sem ajuste de recuo; arredondamento do golden a 2 casas; temporários apagados; `StopIteration` virou mensagem; `arvore_suja` nas medidas; deps de dev anotadas por passo |

Ficou para depois, de propósito: o subcomando que traria o texto do corpus do PyBoxEditor
para o gabarito do Yusupov p. 33 (menor; a transcrição é do usuário e pode ser usada por ele).

## Rodada 2

| Revisor | Notas | Veredito |
|---|---|---|
| Código e testes | Correção 7 · Simplicidade 7 · Testes 6 | volta |
| Produto e medição | Completude 6 · Fidelidade das medidas 5 · Clareza para o usuário 6 | volta |

O que mudou depois dela:

| Achado | Correção |
|---|---|
| `rascunho` sobrescrevia gabarito com trabalho | recusa sem `--forcar`; com ele, guarda `.bak`; a recusa vem antes de ler qualquer página |
| `medir.py` sem teste | a comparação virou `comparar_pagina` e `resumir`, puras; `tests/test_medir.py` cobre IoU no corte, casamento, FEN malformado, linhas unidas, ordem, bloco sem ordem, margens com rodapé, linhas sem par e o resumo |
| Diagramas do replay sem teste; divisão e junção sem teste | testes diretos com objetos falsos: sem confiança é conferido, casas e lado custam, lado que a página não diz não custa, não achado é impossível; divisão, junção, `✝` e espaço |
| FEN medido contra a própria leitura | `fen_verificado` e `lado_verificado` no gabarito, marcados só por `rotular.py revisar` ou pela conferência cega igual; `medir` conta casas e lado só nos conferidos e dá o provisório à parte; o README mostra "pendente (provisório: …)" |
| Replay cobrava o ensino de novo em cada página | os padrões valem para a fatia toda; ao chegar a uma página depois de ensinar, o replay relê os pendentes (`reler_pendentes`, Ctrl+R, 1 gesto, conferido por QTest) |
| `test_pagina_seguinte` sem efeito | um PDF de verdade de 2 páginas; o teste confere a página nova |
| `atalhos.carregar` ignorava chave desconhecida e escopo vazio | problemas de forma (chave desconhecida, `id`/`descricao`/`desde_passo` faltando, escopo vazio) entram no `verificar`; tecla de edição sem Ctrl/Alt em escopo editável pede exceção (achou o Shift+Enter do campo, agora declarado) |
| Regras de exceção e escopo sem teste; `any` frouxo | casos de exceção fora do escopo, tipo inválido, id repetido, pai inexistente, chave errada, escopo vazio; cada caso exige que **todo** problema achado seja o da regra |
| README com estado digitado; fatia fixa; fim de linha | o estado vem do JSON; a fatia lista cada (livro, passo) pelo nome do arquivo; o README é lido e gravado com `newline=""` |
| `mkdtemp` vazando | `TemporaryDirectory` |
| Memória do desfazer contaminada; JSON parcial | as páginas são visitadas antes da base; a medida passou do RSS (que não caiu nada ao esvaziar o histórico: o alocador não devolve) para o tracemalloc ligado antes da base, contando o que é liberado ao esvaziar; sessão com falha grava `-falhou`; mesmo dia e rótulo só com `ABBY_SOBRESCREVER_MEDIDA=1` |
| Enter fora do método | `QTest.keyClick(Enter)` no campo, com o caractere lido do primeiro pendente (conferir a leitura) |
| JSON de desempenho gerado por código antigo | medido de novo depois do commit do passo 0, com a árvore limpa |
| Linha de base da fatia solta do código do passo 0 | a linha de base roda num worktree da tag `passo-0`; o JSON da fatia leva versão e SHA-256 de cada gabarito, e o `comparar` recusa catálogo ou gabaritos diferentes |
| §2 da spec com número errado e digitado | a §2 só tem os alvos e aponta para o JSON e a tabela gerada |
| Métricas da spec sem medida | negativas medidas (xv índices 0 e 7: diagramas falsos e linhas sem par); ligação da legenda, funções e lances declarados em `nao_medido`, com o passo |
| CA-F.2 impossível | `abbychess/app/registro_de_eventos.py` (ligado por `ABBY_REGISTRO_DE_EVENTOS`, só o instante de cada gesto) e `ferramentas/tempo_da_fatia.py`; protocolo e README dizem como medir a linha de base no programa da tag |
| Fatia sem estado provisório | `estado` diz o que falta revisar (estrutura, FEN) |
| Conferência cega sem ferramenta | `rotular.py cego-modelo`, `cego --txt`, `cego --diagrama --fen` gravam o resultado no gabarito; `revisar --por` assina |
| `validar` raso | FEN 8×8, lado, legenda que existe e é legenda, bloco de cada linha, caixas de 4 números, ordens e ids únicos |
| Lado do Darcy d1 contra o protocolo | o protocolo aceita o lance logo depois do diagrama (`1...`) como a página dizendo o lado |
| README sem dizer o que bloqueia | "O que falta você fazer" começa dizendo que as etapas não bloqueiam o roadmap (a linha de base se refaz na tag) e traz os comandos exatos por livro |
| Navegação cobrada só em página com correção | toda troca de página da fatia, em `gestos_navegacao`; linha não lida custa por caractere; o critério vale sobre `gestos` |
| CA-F.1 descrevia um replay dirigido por QTest | reescrita: simulação com custos conferidos por QTest |
| Nomes e números | Darcy: índices 25–26, p. 26–27 do PDF, impressas 27–28; "Margens corridas" no lugar de "Cabeçalho"; "—" explicado; `ordem` e `coluna` dos diagramas ficam no bloco |
| Menores | `split("\n")` e linha sem TAB recusada; exportar e importar conferem tudo antes de gravar; `--passo` desconhecido; a pasta dos PDFs numa constante (`ABBY_PASTA_DOS_PDFS`); PyYAML nas dependências; o teste-esqueleto saiu |

Ficou para o passo 2a, de propósito: mover as fixtures da janela para `tests/conftest.py`
(o docstring do conftest diz isso). Elas mudam de qualquer jeito quando a janela passa a
ser montada pelo controlador.

## Rodada 3

| Revisor | Notas | Veredito |
|---|---|---|
| Código e testes | Correção 7 · Simplicidade 8 · Testes 7 | volta |
| Produto e medição | Completude 8 · Fidelidade das medidas 7 · Clareza para o usuário 7 | volta |

O que mudou depois dela:

| Achado | Correção |
|---|---|
| O catálogo cobrava o clique no glifo que a janela já mostra | `ensinar_da_fila` (passo 0, 2 gestos: digitar e Enter, conferido por QTest); o replay corrige primeiro o glifo da cabeça da fila, como quem anda pelo Enter; catálogo versão 4 |
| Custos de passos futuros sem conferência | `conferir_no_passo` em cada um; conferido o custo, a versão sobe e a linha de base se refaz na tag; `corrigir_no_documento` passou a 3 (clique, Backspace, caractere) |
| "Não bloqueia" sem prazo; saída do roadmap pedia gabaritos revisados | o README e o roadmap (0.5) dizem: não bloqueia de 1a a A2; texto e FEN das p. 21–27 verificados antes do fechamento do A3; a saída do passo 0 foi reescrita |
| A tag `passo-0` não existia | criada no commit aprovado por esta rodada (abaixo), e as medidas refeitas nele |
| Estado do replay "medido" com o texto verificado em parte; conferência cega ignorada | o estado da fatia e o de `medir` contam as linhas verificadas, a conferência cega do texto aprovada **e na versão atual** do gabarito e a de FEN igual |
| `tempo_ativo` somava o salto do relógio entre sessões | uma sessão por `inicio`; só intervalos entre 0 e 60 s; linha cortada ignorada; parse uma vez |
| O README não lia a medida com hora no nome; gerador sem teste | `ferramentas/comum.py` (`ultima_medida`, `destino_da_medida`, `estado_do_git`, `PASTA_DOS_PDFS`, uma definição só); `tests/test_resumo_medidas.py` |
| Medidas sobrescritas no mesmo dia; JSON só de pulo | `medir` e o replay usam `destino_da_medida` (hora no nome, salvo `ABBY_SOBRESCREVER_MEDIDA=1`); o desempenho sem todas as metas grava `-parcial`, com falha `-falhou`, e registra a ordem fixa dos testes |
| `trabalho_humano` não via FEN, lado e conferência cega; `.bak` sobrescrito | vê; os backups se numeram |
| O registro quebrava depois de fechado; o atalho sem teste; o contador do teste duplicava a regra | `fechar` idempotente; teste do `Shortcut`; `tipo_do_gesto` é uma função só, usada pelo registro e pelo teste dos custos |
| A navegação perdia impossíveis | somados ao total |
| Exceção incompleta virava `KeyError`; `da_acao` com `StopIteration`; modificador repetido aceito | problema de forma; erro claro; recusado |
| "Linhas sem par" misturava a capa com o corpo; faltava a revocação de linhas | páginas `negativa` (xv i000 e i007) à parte; "perdidas" (linhas do gabarito não lidas) |
| O provisório do FEN parecia tautológico | `fen_rotulado_por` em cada diagrama; a coluna "FEN = leitura" diz quantos são iguais ao que o programa leu |
| A CA-F.2 sem de onde tirar o N | o replay grava `erros` (texto e diagramas) por página; o README e o protocolo dizem como somar |
| Menores | `robocopy` e o rótulo da medida no README; nomes dos JSON na §15.3; "estimado de 60 ações em 3 páginas"; caracteres novos do Enter no README; a legenda diz o que a ordem não vê; `percentil` único para p95 e p99; `medir.casas` usa a regra de FEN do `rotular`; o uso do `tempo_da_fatia` no docstring |
| O texto dos livros no git | decisão: o repositório é privado e local (README, "Limitações conhecidas", e o docstring do `rotular.py`) |
