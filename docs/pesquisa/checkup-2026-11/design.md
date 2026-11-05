# Auditoria de design: AbbyChessCraft

Base: worktree `C:\Python-Chess2\AbbyChessCraft-coordenadas`, commit `262d897`. Caminhos relativos a ela.
Método: leitura de código e de `docs/`. O programa não foi aberto, nem os testes rodados. Só um script de contas fez as razões de contraste. O repositório não tem capturas de tela.

Marcas: **[F]** fato conferido na linha citada. **[O]** opinião de designer. **[T]** depende de render, a confirmar na tela.

## 1. Veredito

O programa tem uma base rara para uma ferramenta de um usuário só: desfazer nomeado, sessão de edição que não perde palavra, gravação atômica, teclas por perfil, estados vazios que dizem o que fazer. O miolo da fila de glifos é rápido, com 2 gestos por correção.

O problema está na fronteira do que esse miolo cobre. O erro de xadrez mais caro (o lance bem formado, errado e com confiança alta) não aparece em lugar nenhum. O caminho alternativo para corrigi-lo (o Documento) tem o foco no lugar errado. E o editor de diagramas perde o que foi corrigido, em silêncio, com a própria tecla de navegação dele.

Nada disso pede redesenho. Quase toda correção mínima abaixo é de poucas linhas.

| # | Classe | Achado | Custo principal |
|---|---|---|---|
| C1 | Crítico | Lance errado com confiança alta é invisível | Conferir cada lance a olho, por 300 páginas |
| C2 | Crítico | Foco invisível e fora do lugar; Enter tem 8 sentidos | Tecla no painel errado; pode ensinar padrão errado |
| C3 | Crítico | Edição do diagrama some ao mudar de página, sem aviso | Refazer casas; o usuário crê que gravou |
| A1 | Alto | Galeria não aplica figurina | A correção em massa de ♗/♘ não existe |
| A2 | Alto | Três modos de arraste sem indicação fixa e sem Esc | Apagar imagem ou criar áreas sem querer |
| A3 | Alto | Próximo passo e progresso do livro invisíveis | Não saber quando lançar o lote nem quanto falta |
| A4 | Alto | Geometria gravada e nunca lida; sem projeto recente | Refazer janela e procurar pasta em toda sessão |
| A5 | Alto | Conferência de diagramas: F8 preso, grade sem impresso, estado só por cor | Conferência lenta, um a um |
| A6 | Alto | Falha grave pesa o mesmo que aviso corriqueiro | Horas de trabalho com o disco falhando |
| M1–M6 | Médio | Copy falsa, recorte sem escala, paleta longa, contraste, palavra sem sugestão, teclas de função | §3 |

## 2. Críticos e altos

### C1. O lance bem formado e errado não aparece em lugar nenhum

**[F]** Um glifo só entra na fila por limiar de confiança ou por contradição com a palavra (`abbychess/fila_da_pagina.py:87-89`). As regras de contexto não valem em lance (`abbychess/contexto.py:17`). Elas só pegam o que é sintaxe, como a letra onde cabe algarismo ou a figurina larga demais (`contexto.py:23`, `:36`).

**[F]** A verificação de palavras exclui notação de propósito (`abbychess/verificacao.py:9`; o texto diz isso em `app/painel_verificacao.py:129`).

**[F]** O realce do Documento só conhece estado, léxico e virtual, e nada de lance (`app/documento.py:413-429`, `:928-937`).

**[F]** `lances.validar` só olha a primeira linha depois de um diagrama (`abbychess/lances.py:8-13`). O resultado vira estado **do diagrama** (`app/painel_diagramas.py:46-48`), escrito em cinza no Documento (`app/documento.py:379-381`) e como texto no editor (`app/editor_diagrama.py:656-664`).

**[F]** `Lance` e `Validacao` não guardam posição nem gid (`lances.py:110-120`, `:130-143`). Logo, nada leva ao lance culpado.

**Custo.** ♗ lido como ♘, e3 como c3, h3 como h8, com confiança alta: não vão à fila, não ganham realce e não chegam à verificação. Em partida sem diagrama, ou depois da primeira variante, nem a legalidade é testada. O revisor precisa ler cada lance a olho, no corpo 10–11 (`app/espaco.py:296`). Quando a validação acusa, a fila manda conferir o **diagrama**, mesmo quando o erro está no texto.

**Menor correção.**
1. `Validacao` guarda o índice do primeiro lance rejeitado, e o `Lance` guarda os gids dele.
2. O Documento pinta esse token com um realce próprio (traço, não só cor).
3. A fila ganha o modo "Lances" (ou esses glifos entram na fila atual, como `contexto.improvaveis` já faz).
4. **[O]** Passo seguinte: validar também a partida inteira a partir de `1.` sem diagrama. É o que nenhum concorrente faz, e é a promessa do §1 da SPEC.

### C2. Foco invisível e fora do lugar; Enter e Ctrl+Enter mudam de sentido

**[F] Foco invisível.** A docstring da folha de estilo promete "o foco visível" (`app/estilo.py:300`), a SPEC o exige (`docs/SPEC.md:992`), e não há regra nenhuma de foco nas linhas seguintes (`estilo.py:301-309`). O Fusion pinta o campo; a Imagem e o Documento provavelmente não mudam **[T]**. O título das docas e a barra de status não dizem qual painel tem o foco.

**[F] Alt+3 não entra no Documento.** O foco vai ao contêiner (`app/espaco.py:753`, com `painel_do_documento` sendo um `QWidget` puro em `:130`). Não há `setFocusProxy` em `app/`. O teste só confere "dentro da vista" (`tests/test_espaco.py:124`); os testes que digitam chamam `j.texto.setFocus()` antes (`tests/test_documento.py:373`). Efeito esperado: seta, letra e Enter não fazem nada até um Tab **[T]**. O mesmo vale para as abas Galeria, Padrões e Diagramas: a Galeria tem `focar()` (`app/galeria.py:240`), que este caminho não usa.

**[F] Clicar numa palavra do Documento tira o foco dele.** O caminho é `documento.py:591-593` → `espaco.py:413-414` → `desenho.py:141` → `painel_treino.py:374`. O cursor não fica no texto; a próxima tecla substitui o caractere selecionado no campo do Glifo. Para escrever no Documento com o mouse, é preciso clicar no branco depois da linha.

**[F] O fim de qualquer tarefa também tira o foco do Documento.** `app/desenho.py:370-372` passa o foco de `self.texto` ao campo, de propósito. Sair do foco confirma a sessão aberta (`documento.py:884-887`). Com uma propagação em voo, a palavra meio digitada é confirmada, e o resto vai ao campo do Glifo **[T]**.

**[F] A mesma tecla, conforme o foco:**

| Foco | Enter | Ctrl+Enter |
|---|---|---|
| Campo do Glifo | ensina (`docs/ATALHOS.md:146`) | ensina e corrige em lote na página (`:145`) |
| Documento | confirma e avança (`:115`) | confirma e ensina um glifo (`:117`) |
| Palavra | corrige (`:153`) | corrige e ensina (`:154`) |
| Galeria | ensina a seleção (`app/galeria.py:164-168`) | nada |
| Diagrama | nada | conferido e próximo (`ATALHOS.md:161`) |
| Barra de confirmação | aceita (`app/confirmacao.py:74`) | |
| Busca / Substituir | próxima / substitui (`app/barra_de_busca.py:7`, `:13`) | todas (`barra_de_busca.py:105`) |
| Gaveta | abre a página (`app/painel_paginas.py:92`) | |

**Custo.** Sem ver o foco, Enter pode gravar uma amostra quando o usuário queria confirmar uma palavra. Só a Ctrl+Enter do Glifo corrige vários glifos de uma vez. Do Glifo ao Documento só por teclado são 5 gestos mais as setas, contra os 3 pretendidos (§5).

**Menor correção.**
1. `painel_do_documento.setFocusProxy(self.texto)`, e `_focar_a_vista` passa a chamar o `focar()` de cada aba.
2. `_documento_clicado` e `_devolver_o_painel` deixam de mover o foco quando ele está no Documento.
3. Regra de foco na folha: borda do painel em `destaque`, mais o nome do painel com foco na barra de status.

### C3. A edição do diagrama some ao mudar de página

**[F]** Trocar de página fecha o editor e apaga os tabuleiros editados (`app/desenho.py:49` → `app/diagramas_na_janela.py:55-60` → `app/editor_diagrama.py:278-281`). A docstring admite: "Sair sem conferir não leva edição nenhuma" (`editor_diagrama.py:19-20`). Nada avisa. PgDn, a tecla de navegação anunciada pelo próprio editor (`editor_diagrama.py:337-338`), faz isso ao passar da ponta da página (`editor_diagrama.py:496-498` → `abbychess/controlador_de_diagramas.py:44-58`). Ctrl+PgDn, F6, Ctrl+G, a gaveta e a aba Diagramas também. Só a sessão do Documento é salva antes de sair (`app/janela.py:180`).

**Custo.** Cada casa corrigida se perde sem sinal; o diagrama continua "por conferir". É contra o princípio 2 da SPEC (`docs/SPEC.md:36-38`). O "ir e voltar não perde edição" do comentário vale só dentro da página (`editor_diagrama.py:225`).

**Menor correção.** Guardar `tabuleiros` por caixa e pid até fechar o projeto, em vez de limpar. Indicar "alterado, não gravado" no cabeçalho (`editor_diagrama.py:553`). Ao sair com alteração, usar a `BarraDeConfirmacao` que já existe.

### A1. A Galeria não aplica figurina

**[F]** O YAML e a SPEC dão às figurinas e à paleta o escopo Galeria (`docs/atalhos.yaml:301`, `:343-348`; `docs/SPEC.md:229-230`). O código só as registra em Documento e Glifo (`app/acoes.py:265`, `:298-302`). A Galeria ignora Ctrl (`app/galeria.py:170-174`). Sem foco no campo, `inserir_figurina` escreve no Documento (`app/edicao_na_janela.py:101-106`), mesmo com a aba escondida se vier do menu **[T]**. A Galeria também não tem tecla própria (`acoes.py:36`).

**Custo.** A Galeria de ♘ é a melhor tela para achar o ♗ intruso, e "digitar aplica" não serve porque ♗ não está no teclado. Sobra o duplo clique, um glifo por vez.

**Menor correção.** Pôr `j.galeria` nos `widgets` de figurinas e paleta. Em `inserir_figurina`, com o foco na Galeria, chamar `_galeria_aplicar`. Dar uma tecla a "Galeria do caractere".

### A2. Modos sem indicação fixa

**[F]** Marcar glifo, Áreas e Borracha mudam o que o arraste faz. O cursor é o mesmo nos três (`app/visor.py:378-383`). O aviso some em segundos (`app/janela.py:429-431`, `:443-449`; `app/paginas_na_janela.py:84-86`). Sobra o ícone marcado na barra. Esc não sai de modo nenhum (`app/espaco.py:465-485`).

**[F]** Com Áreas ligado, folhear escreve áreas automáticas em cada página sem áreas (`app/desenho.py:52-53` → `abbychess/controlador_de_layout.py:61-74`, `:109-111`), e numa página não lida dispara tarefa (`controlador_de_layout.py:107`).

**[F]** Há teclas fora do YAML e de `ATALHOS.md`: 1–4 mudam o tipo e Backspace apaga a área (`visor.py:807`, `:829-834`).

**Custo.** Arraste apaga a imagem numa página posterior sem que o usuário lembre do modo ligado. Tudo se desfaz, mas o erro aparece tarde.

**Menor correção.** Rótulo fixo na barra de status ("BORRACHA · Esc sai"), com cursor próprio para cada modo. Esc sai do modo. A automática só com pedido. Registrar 1–4 e Backspace no YAML, ou tirá-las.

### A3. Próximo passo e progresso do livro invisíveis

**[F]** A janela nasce com 1500 px (`app/janela.py:82`), e a gaveta só abre em projeto novo a partir de 1600 (`app/espaco.py:56`, `:703`). Logo, o cartão Saúde e o botão "Reconhecer o livro" não aparecem por padrão. No Documento, o cartão só aparece em página **não** reconhecida (`app/desenho.py:416-420`). A mensagem que o cita dura 20 s e não diz F9 (`abbychess/controlador_do_livro.py:259`, `:285-288`). Quando a fila acaba, o Glifo sugere F6, nunca o lote (`desenho.py:137-139`; `controlador_do_livro.py:417`). "Reconhecer o livro" e "Exportar" não estão na barra, ao contrário de Novo e Abrir (`app/acoes.py:75`, `:29`, `:27-28`).

**[F]** Não há total do livro. A barra mostra a página e a fila (`espaco.py:589`, `:561`); a gaveta tem filtro e cartão só da amostra (`app/painel_paginas.py:163-192`). O fim do lote limpo deixa uma mensagem de 20 s e nada mais (`app/lote_na_janela.py:88-95`).

**Custo.** Depois de ensinar a amostra, o passo central fica escondido. Num livro de 300 páginas, "quanto falta" exige filtrar a gaveta e contar.

**Menor correção.** Uma etiqueta fixa na barra de status: `verificadas 123/300 · diagramas por conferir 14`. Tela de fim de fila: "Amostra pronta: Ctrl+Shift+F5 reconhece o livro". "Reconhecer o livro" e "Exportar" na barra.

### A4. A janela e o projeto não voltam

**[F]** `closeEvent` grava a geometria (`app/janela.py:492`), e nada a lê: não há `restoreGeometry` em `abbychess/`. A janela sempre nasce com 1500×950. Em seguida, `_restaurar_as_docas` vê mais de 150 px de diferença contra a largura gravada e **volta aos tamanhos padrão** (`app/espaco.py:790-793`). Quem trabalha maximizado perde o divisor que acertou. Em tela de 768 px, ou de 1080 a 150%, a janela nasce maior que a tela **[T]**.

**[F]** Não há lista de recentes nem reabertura do último projeto (nenhuma ocorrência em `app/`). `Ctrl+O` pede a pasta (`app/dialogos.py:259-267`).

**[F]** O escopo da fila e os estados de Realce, Seguir, Margens e Origem não entram no espaço gravado (`espaco.py:630-639`).

**Custo.** Toda sessão de um trabalho de semanas começa com pasta, maximizar e refazer divisor.

**Menor correção.** `restoreGeometry` no `__init__`, antes de abrir o projeto. Lembrar o último projeto (Ctrl+O já na pasta dele; item "Recentes" no menu). Gravar `escopo`.

### A5. A conferência de diagramas é lenta e tem um beco

- **[F] F8 preso.** `proximo_do_livro` não sai da página enquanto houver diagrama não conferido, incluindo o que falhou na leitura, que não pode ser conferido (`abbychess/controlador_de_diagramas.py:33-35`, `:182-184`, `:215-222`). O contador nunca zera (`abbychess/resumo_do_livro.py:205`; `abbychess/controladores.py:402-405`). Saída: virar a página à mão **[T]**.
- **[F] Grade sem impresso.** A aba Diagramas só tem recorte das 5 páginas em memória (`app/diagramas_na_janela.py:81-88`, `app/desenho.py:89`); as outras mostram "recorte na Imagem" (`app/painel_diagramas.py:169-170`). A Galeria já resolve isso numa thread (`app/galeria_na_janela.py:156-181`).
- **[F] Estado só por cor.** Os quatro estados do tabuleiro na Imagem usam o mesmo traço (`app/visor.py:754-766`, `app/estilo.py:131-134`), contra a regra do próprio arquivo (`estilo.py:18-20`). A legenda tem uma linha só, em cinza (`app/painel_treino.py:308-309`).
- **[F] Lado sem tecla.** É o erro mais comum, segundo o código (`painel_diagramas.py:62-63`), e pede Tab até os rádios (`editor_diagrama.py:406-418`; ordem de tabulação **[T]**). As peças usam letras do FEN inglês (`editor_diagrama.py:182-183`), enquanto o livro em português digita R D T B C (`docs/SPEC.md:503-505`).
- **[F] Ctrl+T ignora diagramas.** A pergunta conta só os glifos (`app/galeria_na_janela.py:87-93`). A página fica ✓ com diagrama por conferir.
- **[F] F7 engana.** Em "Diagramas por conferir", sem editor aberto, o Inspetor mostra o Glifo (`app/espaco.py:547-550`).
- **[O]** O impresso (Imagem) e a leitura (Inspetor) ficam separados pelo Documento em toda a largura. Comparar casa a casa é um salto de olho de ~500 px (`app/espaco.py:59`). Um atalho de arranjo automático na conferência (Só a Imagem, Ctrl+F6) resolve sem código novo de desenho.

**Menor correção.** F8 pula quem não tem `lido`. Reutilizar a thread de recortes na grade. Traço distinto por estado, com legenda de 4 linhas. Teclas para o lado (Ctrl+W e Ctrl+B não colidem no editor; conferir no YAML). Incluir diagramas na pergunta do Ctrl+T.

### A6. A falha grave pesa o mesmo que o aviso corriqueiro

**[F]** A falha de gravação vai à barra e a Avisos (`app/desenho.py:319-330`), e a barra troca de texto na próxima mensagem (`desenho.py:297-302`). Sobra `⚠N`, igual para erro e para linha de relatório (`app/espaco.py:596-598`). O texto pede "não feche antes de liberar o disco", e nada insiste nisso até fechar (`app/janela.py:346-353`).

**[F]** O relatório da exportação não abre o painel (`desenho.py:313-317`), embora a SPEC diga que abre (`docs/SPEC.md:88`). Alt+5 não vai à aba Avisos nem zera o contador, ao contrário do ⚠ (`espaco.py:756-761` contra `:611-615`).

**[F]** A SPEC diz "nada some com um `showMessage` de 5 s" (`docs/SPEC.md:112`), mas há 41 `showMessage` em `app/` e 96 chamadas de `_avisar` nos controladores que não chegam ao log, como "A conferência fechou: os diagramas da página mudaram" (`app/diagramas_na_janela.py:50`).

**Custo.** Com o disco falhando, o revisor segue corrigindo com o trabalho só em memória.

**Menor correção.** Faixa fixa (a `BarraDeConfirmacao`, ou irmã) enquanto `paginas_sujas()` não gravar. ⚠ em `erro` quando há erro novo. Relatório abre Avisos.

## 3. Médios

| # | Fato | Custo | Menor correção |
|---|---|---|---|
| M1 | **[F]** O diálogo do F5 diz que "descarta os boxes e as correções só desta ocorrência" (`app/janela.py:381-384`), mas o código mantém manuais e revisados (`abbychess/editar_boxes.py:200-209`; o do lote diz certo, `app/dialogos.py:390`). "Linha vermelha do recorte" (`app/painel_treino.py:252`) é amarela (`:438`). "(F5)" fixo no aviso (`app/desenho.py:345`), que no perfil FineReader mostra Páginas. "Amostra" tem dois sentidos no mesmo cartão (`app/painel_paginas.py:169`, `:178`). | Medo infundado de F5; termos ambíguos | Texto novo, ou tirar a pergunta, já que F5 se desfaz (`docs/SPEC.md:378`). Chamar as páginas de "páginas de teste" |
| M2 | **[F]** O recorte é sempre esticado a 140 px de altura (`app/painel_treino.py:433`, `:176`; `app/imagens.py:55-59`). Vírgula e apóstrofo, `o` e `O` perdem o tamanho e a linha de base. Na Linha, a letra é fixa em 12 pt, com caixa ±8 px além do glifo (`app/linha.py:103`, `:115`): pode sobrepor **[T]**. O atual ali é contorno único amarelo, 1,66:1 sobre o papel (`linha.py:109-113`). | O glifo isolado engana justamente nos pares que o contexto não resolve | Escala comum por linha e traço da linha de base no recorte. Contorno duplo na Linha, como no visor (`visor.py:332-339`) |
| M3 | **[F]** F2 é um menu de 58 itens numa coluna, sem mnemônico nem busca (`painel_treino.py:47-58`, `:91-101`). A grade é só de mouse (`:292`) e fica abaixo da dobra em 768 px (comentário em `:336`). | NAG (±, ⩲) custa dezenas de setas ou o mouse, contra `docs/SPEC.md:33-35` | Filtro por nome ao digitar, e atalho numérico para os 10 mais usados do livro |
| M4 | Contraste: §6 | Ver tabela | Ver tabela |
| M5 | **[F]** A Palavra não oferece sugestão (só a da camada do PDF, `app/painel_verificacao.py:198-203`), e o campo vem todo selecionado (`:204`). No perfil padrão, chegar às palavras exige F7 três vezes (`docs/ATALHOS.md:18`; ordem em `abbychess/controladores.py:283-285`). | Prosa custa mais do que no FineReader | Lista numerada de sugestões do Hunspell (Alt+1…3), sem nunca aplicar sozinha; tecla direta para a fila de palavras |
| M6 | **[F]** F5–F8 misturam famílias: F7 é fila e Ctrl+F7 é arranjo; F6 é página pendente e Ctrl+F6 é arranjo (`docs/ATALHOS.md:13`, `:28`, `:43`, `:59`). Menu Página com 30 itens planos (`app/acoes.py:332-338`). | Tecla errada muda o layout em vez de andar | **[O]** Mover arranjos para um grupo só; submenu "Operações de página" |

## 4. Fluxo principal

| Etapa | Gestos | Onde fica cego | Perde trabalho? |
|---|---|---|---|
| Novo projeto | Ctrl+N, arquivo, formulário, pasta, [texto nativo?] (`app/dialogos.py:141-160`): 5–7 | Pasta "sem acentos" só no título do diálogo (`:191`) | Não |
| Áreas | Ctrl+Shift+A, letra; modelo só pelo menu (`docs/ATALHOS.md:91`, `:104`) | A amostra lê antes de oferecer revisar as áreas; modos invisíveis (A2) | Não; desfaz |
| Reconhecer | Automático na amostra; F5 na página | Resumo só na barra, 8 s (`abbychess/ponte_de_leitura.py:145-146`) | F5 mantém o decidido |
| Treinar | Letra + Enter | Fim da amostra (A3) | Não |
| Lote | Ctrl+Shift+F5, intervalo, [ler de novo?] | Fim do lote some em 20 s (A3); ✕ sem confirmação, mas com retomada (`app/espaco.py:228`) | Não; cópia antes do lote |
| Revisar | Fila; Ctrl+T | Erro fora da fila (C1); foco (C2); total do livro (A3) | Sessão segura |
| Diagramas | F8, casas, Ctrl+Enter | Beco do F8; só por cor (A5) | **Sim (C3)** |
| Exportar | Ctrl+E, salvar, opções, OK; formato escolhido no filtro do arquivo (`dialogos.py:458-465`) | Relatório não abre (A6) | Não |

## 5. Carga e revisão

**Carga [F].** 6 áreas e 10 vistas: Páginas, Imagem, Linha, Resultados (2 abas), vista direita (4 abas: `espaco.py:141-143` e `galeria_na_janela.py:28`), Inspetor (4 editores, `espaco.py:168-170`). Modos: 3 de arraste; 5 de fila × 2 escopos; 4 arranjos; mais V, Seguir, Realce e Margens. 107 ações criadas (`app/acoes.py`), 98 itens de menu por contagem em `_menus`, cerca de 110 linhas de atalho em `docs/ATALHOS.md`. Nada disso disputa atenção na imagem, porque os aceitos são discretos, o que é bom. **[O]** A carga real é de memória: os mesmos gestos mudam por foco e modo sem sinal (C2, A2). O Glifo empilha tudo numa coluna, com a paleta de 10 linhas antes da legenda (`painel_treino.py:322-340`).

**Gestos por correção (a partir do código).**

| Caso | Caminho | Gestos |
|---|---|---|
| Na fila, leitura certa | Enter (ensina) ou Shift+Enter | 1 |
| Na fila, letra errada | letra, Enter (avança sozinho) | 2 |
| Na fila, figurina errada | Ctrl+Shift+N, Enter (preta: mais um) | 2–3 (4–7 teclas) |
| Na fila, NAG sem tecla | F2, setas, Enter, Enter | 3 + até 50 setas, ou mouse |
| Dois glifos colados | Ctrl+D, letra, Enter, letra, Enter | 5 |
| **Fora da fila, com mouse** | clique, letra, Enter | 3, mão fora do teclado |
| **Fora da fila, só teclado** | Alt+3, Tab, setas, Del, letra, Enter | 5 + setas (C2) |
| Palavra desconhecida | F7×3 (uma vez), setas, letra, Enter | 3 + setas |
| Diagrama sem erro | F8, Ctrl+Enter | 2 |
| Diagrama, uma peça | F8, setas (≤14) ou clique, letra, Ctrl+Enter | 3 + setas |
| Lado a jogar | ~5 Tab, Espaço **[T]** | 6, sem atalho |

**Como a tela ajuda a achar o erro de xadrez.**
- Bom **[F]**: fundo laranja, ondulado e □ no Documento; traço e cor por estado na Imagem; Linha imagem-sobre-texto; `contexto` pega l/1 e figurina larga; "Pelo contexto" e "Palpite" dizem que são palpites (`painel_treino.py:376-401`); conflito ao ensinar (`:345-354`).
- Falta **[F]**: nada marca lance (C1); nada mostra a próxima ambiguidade ♗/♘; a Galeria, que é o melhor recurso, tem acesso fraco (A1).
- **[O]** A fila por confiança salta pela página e tira o contexto de leitura. Para o revisor depois da fase de treino, a "Ordem de leitura" seria o padrão melhor; hoje o espaço padrão reabre em confiança (`espaco.py:682`).
- **[O]** Enter = ensinar é ótimo na amostra. Na página 200, aceitar não deveria criar amostra. Vale testar com o usuário se o padrão muda quando a amostra acaba; não mudaria sem medir, pelo CA-F.1.

## 6. Contraste WCAG (calculado dos tokens de `app/estilo.py`)

Interface (`estilo.py:240-253`), texto normal pede 4,5:1:

| Token | Claro /janela | Claro /base | Escuro /janela | Escuro /botão |
|---|---|---|---|---|
| texto | 16,17 | 18,42 | 12,27 | 9,51 |
| texto_secundario | 6,54 | 7,46 | 6,59 | 5,11 |
| erro | 5,82 | 6,63 | 5,95 | 4,61 |
| aviso | 4,86 | 5,53 | 7,99 | 6,19 |
| acerto | 5,55 | 6,33 | 8,26 | 6,40 |
| link | 6,20 | 7,07 | 7,13 | 5,52 |
| texto_do_destaque/destaque | 5,19 | | 7,12 | |
| **borda** (controle, pede 3:1) | **1,63** | **1,86** | **1,91** | **2,08** (/base) |
| **MARCADO** como texto (`painel_treino.py:420`) | **4,13** | | **3,26** | |

Texto da interface passa AA. Duas falhas: a borda de campos e botões (1.4.11; em Fusion o preenchimento ajuda, **[T]**) e o rótulo da seleção em ciano. Desabilitado usa `texto_secundario`, que dá só 2,47 (claro) e 1,86 (escuro) contra o habilitado: pouco para distinguir botão morto de botão vivo.

Papel (`estilo.py:45-50`, `:119-122`), 3:1 contra 255 e contra 230:

| Token | /255 | /230 | Nota |
|---|---|---|---|
| LARANJA, VERMELHAO, AZUL, VERDE_AZULADO, ROXO, CINZA | 4,65–6,53 | 3,72–5,23 | Passam (bom) |
| MARCADO, PALAVRA | 4,70; 5,87 | 3,77; 4,71 | Passam |
| **SELECIONADO** | **1,66** | **1,33** | No visor é salvo pelo contorno preto; **sozinho na Linha e no corte** (`linha.py:109`, `painel_treino.py:438`, `visor.py:433`) |
| Aceito (preto a 25%) | 1,84 | 1,82 | Discreto de propósito: ok |
| COR_DA_ZONA diagrama, ignorar | 2,87; 3,48 | 2,30; 2,79 | Só fallback (`visor.py:782`); baixa prioridade |

Fundos de realce do Documento (`estilo.py:153-158`):

| Fundo | /papel | /FUNDO_DE_BAIXA_CONFIANCA |
|---|---|---|
| Baixa confiança | **1,25** | |
| Busca | 1,23 | **1,02** |
| Sessão | **1,09** | 1,15 |
| Atual | 1,75 | 1,40 |

A tinta sobre todos passa de 11:1. **Baixa confiança e busca são quase a mesma cor**, e a sessão é quase invisível. Para o trabalho que mais importa, é fraco, ainda mais em 10–11 pt: o realce é um fundo de 1,25:1 **[T]**. Correção: baixa confiança com fundo mais saturado **e** sublinhado; busca noutra matiz (azul claro).

Casas do editor Diagrama (`estilo.py:173-175`), contra a casa de baixo: corrigida 1,32/1,04, arbitrada 1,60/1,25, duvidosa 1,29/1,02 (clara/escura). Corrigida e duvidosa têm luminância igual entre si (1,00 sobre branco): só o matiz separa verde de laranja, justamente o par que o daltônico confunde. O desenho do tabuleiro (`editor_diagrama.py:197-198`) muda o fundo real **[T]**. Correção: um canto ou traço por estado, em vez de só o preenchimento.

## 7. Acessibilidade, teclado e DPI

- **Bom [F]:** 55 `setAccessibleName`; `nomear_os_controles_do_qt` cobre botões internos (`app/acessibilidade.py:25-42`); dicas seguem o perfil; Shift+F10 no visor (`visor.py:690-718`).
- **[F]** A Imagem não tem nome acessível (`visor.py`, sem `setAccessibleName`), e a Linha desenha o texto com `drawText` (`linha.py:115`), invisível ao leitor de tela. O tabuleiro tem nome, sem o valor da casa (`editor_diagrama.py:78`). "Copiar FEN" só responde ao mouse, apesar da flag de teclado (`documento.py:134-137`, `:585-588`).
- **[F] Alvo.** O teste do mínimo de 24 px vale só para a barra principal (`tests/test_icones.py:104`). ✕ e ⚠ da barra de status não têm tamanho mínimo (`espaco.py:224-229`, `:242-246`); colunas de 22–26 px na gaveta, com cabeçalhos "Est.", "Diag." (`painel_paginas.py:86`, `:101`) **[T]**.
- **[F] Tipografia.** `CORPO_DA_INTERFACE` e `FONTE_DA_INTERFACE` são só declarados (`estilo.py:193-194`): não há `app.setFont`. O corpo é o padrão do Windows, sem opção de aumentar para jornadas longas. **[O]** Um corpo da interface em Opções ajuda a vista.
- **[F] DPI.** Qt6 escala as medidas lógicas. Bitmaps de tamanho fixo perdem nitidez acima de 100%: legenda (`painel_treino.py:116`), tabuleiro (`editor_diagrama.py:197-198`), recortes da Galeria (`galeria.py:85-86`) **[T]**. Em 1080p a 150% a tela tem 1280 lógicos. O arranjo se decide pela largura da janela, não da tela (`espaco.py:276-277`), e ela nasce com 1500: lado a lado numa janela maior que a tela, a menos que o Windows a limite (A4) **[T]**.

## 8. Consistência

- **[F]** Cor e ícones são bem contidos: os tokens valem em todo `app/`, com Lucide monocromático na cor do tema (`app/icones.py:24-36`). Bom.
- **[F]** Espaços não seguem os tokens: margens de 0, 2, 4 e 6 escritas à mão (`espaco.py:134`; `painel_paginas.py:111`, `:148`; `confirmacao.py:33`); `ESPACOS` só aparece na folha de estilo (`estilo.py:304`, `:308`). `RAIO` não é usado.
- **[F]** Ações parecidas com formas diferentes: "◀ Anterior" em botão de texto Unicode (`painel_treino.py:243`), ◀ ▶ ↶ ↷ em `QToolButton` (`editor_diagrama.py:330-348`), Lucide na barra.
- **[F]** Texto fixo que não segue o perfil: "Shift+seta" (`app/inspetor.py:23`, `painel_treino.py:272-273`), `app/galeria.py:33`, "Enter ensina" (`painel_treino.py:420`).
- **[O] Copy.** O português é claro e honesto, acima da média do ramo. Pontos a limar: "box" (`desenho.py:137`, `abbychess/fila_da_pagina.py:101`) contra "glifo"; "vista direita" (`acoes.py:144`, `:149`), que é termo de spec e não de tela; "pendente", "a revisar" e "duvidosa" para a mesma ideia.

## 9. Comparação honesta com o FineReader

| O que importa | FineReader (`docs/pesquisa/finereader.md`) | AbbyChessCraft | Vence |
|---|---|---|---|
| Verificar sequência | Alt+↓/↑, Ctrl+T (§2) | Igual, com 5 modos e escopo | Abby |
| Sugestão na palavra | Replace pela sugestão (§2) | Só a camada do PDF (M5) | FineReader |
| Treino | Diálogo modal; padrão de até 1.000 caracteres (§5) | Fila, Galeria, Procedência, conflito, por livro | Abby, de longe |
| Figurinas, FEN, lances | Nada | Tudo, com falhas em C1 e A1 | Abby |
| Localizar | Sem regex documentada (§6) | Regex no livro | Abby |
| Áreas e modelos | Tipos, Order Areas, templates (§3) | Paridade, com função e editor Área | Empate |
| Miniaturas e início | Miniaturas ou lista (§1); projetos recentes [não pesquisado] | Só lista (`painel_paginas.py`, embora a SPEC peça, `docs/SPEC.md:94-95`), sem recentes | FineReader |
| Polimento e foco | Produto maduro | C2, A4, M6 | FineReader |
| Desfazer e não perder | Não documentado na pesquisa | Desfazer nomeado por transação; só C3 foge | Abby, se corrigir C3 |

**[O]** O usuário não ganha nada imitando mais o FineReader. A vantagem real é saber xadrez, e o ganho maior está em levar essa inteligência à tela de revisão (C1, A1).

## 10. O que está bom e não deve mudar

- **A fila com campo já selecionado e avanço sozinho** (`painel_treino.py:361-374`): 2 gestos por correção é o coração do programa.
- **A sessão do Documento**: Esc restaura, Ctrl+Y reaplica, sair confirma (`app/documento.py:17-31`; `app/edicao_na_janela.py:32-37`).
- **Hierarquia da página**: aceitos a 25%, pendentes em traço e cor, Okabe-Ito escurecida medida contra 255 e 230 (`app/estilo.py:18-22`, `:75-89`). A página nunca inverte.
- **Desfazer com nome** ("Desfazer: X") e resposta na barra (`abbychess/estado_da_janela.py:158`; `abbychess/aplicador_do_historico.py:64`).
- **Gravação sem botão Salvar**, atômica (`docs/SPEC.md:315-322`).
- **Estados vazios com a tecla do perfil de agora** (`app/vazios.py`).
- **A pergunta inline** em vez de modal no Ctrl+T (`app/confirmacao.py`).
- **Lote que não prende a tela**, com tempo estimado, cancelar, retomar e voltar (`app/lote_na_janela.py`; `abbychess/estado_da_janela.py:6-8`).
- **Linguagem honesta sobre incerteza**: "Palpite da rede… confira antes do Enter", "A página não diz. Escolha", "Orientação não confirmada" (`painel_treino.py:382-384`; `editor_diagrama.py:596`, `:648-650`).
- **Galeria e aba Diagramas como conceito**, ambas com o que falta em A1 e A5, e **dois perfis de teclado** com regras conferidas (`app/teclado.py:13-18`).

## 11. Ordem sugerida

1. **Uma tarde:** C3 (guardar tabuleiros), A1, A4, F8 preso, M1, foco de Alt+3 e do clique (C2).
2. **Dois dias:** indicador de foco e de modo (C2, A2), etiqueta do progresso (A3), faixa de falha (A6), realce mais forte (§6).
3. **O que muda o produto:** C1, com medida de quantos erros de lance o gabarito pega.

## 12. Limites desta auditoria

- Nada foi visto em tela: toda a medida de espaço, sobreposição, corte e aparência precisa das 8 capturas do CA-13.2.
- Li por inteiro os módulos centrais da revisão. De `barra_de_busca`, `busca_na_janela`, `substituir_na_janela`, `painel_padroes`, `dialogo_paginas`, `previa_da_pagina`, `opcoes` e `dialogo_teclado`, só trechos ou nada: busca, substituição e operações de página não foram auditadas.
- As contagens de gestos saem do código, sem medir tempo; podem divergir do replay do CA-F.1.
- A comparação com o FineReader se apoia em `docs/pesquisa/finereader.md`, não em uso do produto.
