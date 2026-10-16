# AbbyChessCraft

OCR de livros de xadrez com treino de padrões por livro, no estilo do FineReader. O motor de
leitura é o `core` do PyBoxEditor, instalado como biblioteca. Este projeto acrescenta o que o
PyBoxEditor não tem: um conjunto de padrões próprio para cada livro, que vale na hora, não
contamina outros livros e é revisado numa interface em PySide6.

## Rodar

O aplicativo usa o Python 3.13 do sistema, onde estão o PyTorch, o PySide6 e o OpenCV. O
ambiente `.venv` enxerga esses pacotes e tem o PyBoxEditor e este projeto em modo editável.

```text
.venv\Scripts\python.exe -m abbychess
.venv\Scripts\python.exe -m abbychess C:\caminho\do\projeto
```

Para recriar o ambiente do zero:

```text
py -3.13 -m venv --system-site-packages .venv
.venv\Scripts\python.exe -m pip install -e C:\Python-Chess2\PyBoxEditor_Tkinter --no-deps
.venv\Scripts\python.exe -m pip install -e . --no-deps
.venv\Scripts\python.exe -m pip install hypothesis regex psutil pytest-timeout pytest-qt PyYAML
```

Os testes vêm em camadas (SPEC §15.1). A suíte rápida roda sempre e fica abaixo de 60 s; as
outras rodam com `-m`:

```text
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pytest -q -m livro_real
$env:ABBY_ROTULO_DA_MEDIDA = "linha-de-base"; .venv\Scripts\python.exe -m pytest -q -m desempenho tests\desempenho
```

`livro_real` usa os PDFs da pasta do PyBoxEditor e os modelos globais; com
`ABBY_PORTAO=1`, um teste desses que pularia por falta do livro **falha** (é o portão de
fechamento de cada passo do roadmap). O portão só vale com as camadas selecionadas, porque
o `addopts` as tira da suíte rápida:

```text
$env:ABBY_PORTAO = "1"; .venv\Scripts\python.exe -m pytest -q -m "livro_real or desempenho"
```

`desempenho` mede as metas de §2 da spec e grava o resultado em `docs/medidas/`.

O projeto está em git desde 2026-10-16. Os atalhos têm uma fonte só, `docs/atalhos.yaml`;
`docs/ATALHOS.md` é gerado dele por `ferramentas\atalhos.py`, e o teste reprova colisão,
letra solta em campo de texto, Ctrl+Alt e ligação nativa encoberta sem exceção declarada.

## O fluxo de treino

1. **Novo projeto** (Ctrl+N) liga um PDF ou uma imagem a uma pasta de projeto do livro.
2. **Reconhecer página** (F5) segmenta a página, separa os diagramas do texto, lê cada glifo
   e lê cada diagrama em FEN, que entra no texto reconhecido da página.
3. O painel de treino mostra o glifo menos confiável, ampliado e na linha em que está.
   - **Enter** ensina o padrão para este livro. As repetições do mesmo glifo saem da fila na hora.
   - **Shift+Enter** corrige só esta ocorrência, sem gravar padrão.
   - **Del** tira da página um box que não é caractere.
   - **Tab** pula para o próximo; Shift+Tab volta.
   - **Ctrl+D** divide um box que juntou dois glifos, como o "rp" da p. 27 do Darcy Lima:
     no ponto clicado no recorte ampliado ou, sem clique, no vão da tinta. As partes são
     aparadas à própria tinta, relidas, e a primeira aparece para ser ensinada.
   - **Ctrl+J** junta com o box seguinte da linha; **Ctrl+Shift+J**, com o anterior.
   - **Alt+seta** move a borda direita ou a de baixo; **Alt+Shift+seta**, a esquerda ou a de
     cima. O box é relido a cada passo.
   - O botão direito sobre um box, na página, também divide no ponto e junta.
   - A paleta insere figurinas e símbolos de avaliação.
   - **Ctrl+Z** desfaz e **Ctrl+Y** (ou Ctrl+Shift+Z) refaz, também com o foco no campo do
     caractere: ensinar, corrigir, descartar, dividir, juntar, ajustar as bordas, marcar um
     glifo, corrigir uma palavra na verificação, conferir um diagrama, o próprio F5, as
     áreas do editor de áreas, esquecer padrões e o Reler pendentes. **O desfazer é do
     projeto** (desde o passo
     2b): o Ctrl+Z desfaz a última ação do livro, mesmo que ela tenha sido noutra página, e
     abre essa página. Desfazer um ensinar apaga do livro as amostras que ele gravou, e as
     repetições que elas tinham resolvido voltam à fila; refazer as grava de novo; desfazer
     um esquecer devolve as amostras. Os Alt+seta seguidos no mesmo box, e os arrastes
     seguidos da mesma área, se desfazem de uma vez. O menu **Editar** diz o que vai ser
     desfeito. **Se algum glifo da ação mudou depois por um caminho que não passa pelo
     desfazer** (o reconhecimento em lote), o desfazer recusa e diz por quê, sem mudar nada,
     e pergunta se você quer tirar essa ação do desfazer para chegar às anteriores; uma
     mudança em outros glifos não impede.
   - **O Enter não espera a página toda** (desde o passo 2b). O glifo ensinado muda de cor
     na hora e o próximo pendente já aparece; a propagação do padrão pelos outros pendentes
     da página roda em seguida, fora da janela ("Propagando o padrão" na barra), e o que ela
     resolver muda de cor quando ela acaba. Dá para ensinar o glifo seguinte enquanto isso.
     Se a propagação resolver o glifo que o painel mostra, o painel passa ao próximo
     pendente, a não ser que você já tenha começado a digitar nele ou o tenha escolhido com
     um clique (aí ele fica, e o que você digitou não se perde). Um Ctrl+Z com a propagação
     ainda rodando desfaz o Enter e descarta o que ela ia resolver; o refazer refaz o glifo
     e roda a propagação de novo.
   - **Uma coisa por vez, na ordem** (desde o passo 2a). Reconhecer e reler rodam fora da
     janela, e enquanto isso o painel de treino fica desligado (a barra mostra o que está
     rodando); a propagação de um Enter não o desliga. O que você pedir nesse meio-tempo,
     como um F5, um Ctrl+Z ou um "Dividir aqui" no botão direito, não se perde: entra numa
     fila, que a barra mostra ("… Na fila: Desfazendo, Reconhecendo a página"), e roda
     quando chegar a vez. Uma edição pedida numa página e que só ganha a vez depois de você
     ir para outra é descartada, com aviso.
4. Na página seguinte, o livro já lê com os padrões ensinados.
5. A aba **Padrões do livro** mostra cada amostra por caractere e permite esquecer as erradas.
6. **Clicar num diagrama** abre a conferência (ver abaixo).

Cor dos boxes: roxo é o que você confirmou, verde vem de um padrão do livro, azul da rede ou
da base global, laranja vai para a revisão, vermelho ninguém leu e ciano está na seleção do
modo de treino. O tracejado do diagrama segue a mesma ideia: cinza ainda não lido, laranja
lido mas a conferir, azul lido com confiança, roxo conferido por você.

### Os diagramas

O F5 lê cada tabuleiro com o core do PyBoxEditor (`core.diagrama`: as redes de ocupação e de
peça sobre o resíduo de cada casa, com a legalidade como árbitro), e grava o FEN junto da
página. No texto reconhecido, o diagrama entra antes da primeira linha que começa na altura
dele, num fim de frase, como uma linha:

```text
[Diagrama 1: r2qkb1r/2p2pp1/ppn4p/8/3PN2n/PP3N2/bBB2PPP/3Q1RK1 w - - 0 1 — brancas a jogar (assumido: a página não diz); não revisado]
```

**O lado a jogar nunca é brancas em silêncio.** O FEN exige o campo e sai com `w` quando a
página não diz, mas a linha diz que é suposição. A legenda impressa em volta ("pretas
jogam", o `▼` do Yusupov) é lida e vira "da legenda"; a escolha na conferência vira
"informado na revisão". A legenda vale primeiro como está nos boxes da página, a linha
encostada no tabuleiro com o que os padrões do livro leram e o que você corrigiu; só sem
ela vale a releitura do core. Ensinar, corrigir, dividir ou juntar um box da legenda diz o
lado na hora, sem F5: os diagramas não conferidos da página tiram o lado de novo da linha de
boxes, sem reler o tabuleiro, e o Ctrl+Z da edição o desfaz junto. O conferido e o de lado
informado na revisão não mudam.

**Clicar no diagrama** (ou **Ferramentas › Conferir diagramas**, Ctrl+G, que abre o primeiro
por conferir) mostra o recorte impresso e a posição lida lado a lado, na mesma escala, a
posição desenhada pela fonte de diagrama do PyBoxEditor:

- clique seleciona a casa; a letra da peça a põe (maiúscula branca, minúscula preta); Delete,
  Backspace ou espaço a esvaziam; as setas andam pelas casas; o botão direito esvazia;
- com uma peça escolhida na paleta, o clique pinta, e clicar de novo alterna com vazia;
- verde é casa corrigida por você, vermelho trocada pela legalidade, laranja leitura duvidosa;
- o lado a jogar começa sem escolha quando a página não diz; o roque só oferece o que a
  posição comporta; Ctrl+Z e Ctrl+Y desfazem e refazem;
- os avisos dizem o que o leitor desconfia (o porteiro do PyBoxEditor), o que a posição tem de
  impossível e que, sem coordenadas impressas, a orientação é suposta;
- **Conferido** (Ctrl+Enter) grava o FEN, passa ao próximo por conferir e, no último, fecha.
  PgUp e PgDown andam entre os diagramas da página. Fechar sem conferir não leva nada.

O diagrama conferido não é relido: reconhecer a página de novo, pelo F5 ou pelo lote, mantém
a conferência do tabuleiro que está no mesmo lugar. Uma página gravada antes desta leitura
abre com os diagramas por ler, e o primeiro clique os lê.

**A correção não vira padrão de leitura, e foi medido.** Um vizinho mais próximo do livro
sobre o resíduo das casas, treinado nos diagramas conferidos da p. 26 e testado no que ficou
de fora, errou de 5 a 17 casas por tabuleiro, com as distâncias dos erros no meio das dos
acertos; as redes do PyBoxEditor leram certos os dois diagramas sem setas. As casas
corrigidas (e as 64, com "Conferi as 64 casas") são **guardadas** como amostras na pasta
`diagramas/` do projeto, no formato de `core.treino_diagrama`, para uma promoção futura. A
base global de diagramas do PyBoxEditor não é tocada: o `treino_diagrama.colher` é chamado
sempre com as pastas do projeto.

### O menu Ferramentas

- **Modo de treino** (Ctrl+T): o arraste na página desenha o quadro de um glifo, em vez de
  mover a página. O quadro é aparado à tinta, substitui os boxes que ficam dentro dele, é lido
  e vai para o painel, onde Enter o ensina. Funciona também numa página ainda não reconhecida:
  dá para marcar e ensinar os glifos difíceis primeiro e só então apertar F5. Na p. 27 do
  Darcy Lima, um "r" marcado assim antes do F5 fez a leitura tirar 27 "r" do padrão. A
  página só com glifos marcados não conta como lida (`paginas/marcadas.json`): a exportação
  a pula, o lote a reconhece, e o F5 nela não pergunta nada e mantém os quadros no lugar dos
  boxes da segmentação que caem sobre eles.
- **Ctrl+clique** num box, em qualquer modo, põe o box na seleção (ou o tira dela). Enter
  ensina a seleção inteira com o mesmo caractere, uma amostra por box; Shift+Enter corrige
  todos sem gravar padrão; Esc esvazia a seleção.
- **Padrões do livro** (Ctrl+Shift+P) abre a aba das amostras.
- **Conferir diagramas** (Ctrl+G) abre a conferência no primeiro diagrama da página ainda não
  conferido.
- **Reconhecer o livro** (Ctrl+Shift+F5) lê um intervalo de páginas ("26-27, 30"; vazio é o
  livro inteiro) em segundo plano, com os padrões do livro, lê os diagramas em FEN como o F5
  e grava cada página no projeto assim que ela termina. O diagrama já conferido não é relido. A barra mostra a página em que o lote está. Enquanto ele roda, o painel de treino e as ações de reconhecer e reler ficam desligadas, e editar a página (dividir, juntar ou marcar pelo visor, desfazer, esquecer padrões, as opções) é recusado na hora, com aviso na barra: cancele o lote ou espere ele acabar. Ver as páginas continua valendo. Se o intervalo tem
  páginas já lidas, ele pergunta: Sim as lê de novo (os boxes e as correções só desta
  ocorrência saem, os padrões ficam), Não as pula. **Cancelar o lote** para ao fim da leitura
  em curso; a página interrompida fica como estava e as já gravadas ficam.
- **Próximo pendente do livro** (F6) é a fila de revisão do livro todo: mostra o pendente
  desta página e, quando ela acaba, abre a próxima página gravada que ainda tem glifo a
  revisar, dando a volta no livro.
- **Editor de áreas** (Ctrl+Shift+A): as áreas da página, como as do FineReader. Ao ligar,
  a página ganha as áreas automáticas que a segmentação sugere: um bloco de texto por grupo de
  linhas sem vão grande e um diagrama por tabuleiro, com a margem das coordenadas. O arraste
  fora das áreas desenha uma área de texto; dentro de uma área, a escolhe e move; na borda da
  escolhida, a estica. As teclas **1** a **4** trocam o tipo (texto, diagrama, imagem,
  ignorar), **Del** apaga, e o botão direito faz as duas coisas. O F5 e o lote passam a
  reconhecer pelas áreas: só o que está numa área de texto vira box, cada diagrama vira
  tabuleiro (o achado dentro dele, ou a própria área) e imagem e ignorar não geram nada. Onde
  áreas se sobrepõem vence a mais restritiva: ignorar e imagem, depois diagrama, depois texto.
  É um modo à parte do de treino, que também usa o arraste: ligar um desliga o outro.
  **Refazer as áreas automáticas** descarta as da página e sugere de novo. Apagar todas volta
  a página à segmentação automática inteira.
- **Verificação de texto** (F7): anda pelas palavras da página que o léxico do core não
  conhece (`core.lexico`), na aba **Verificação**, com o recorte da palavra e os glifos dela
  contornados. O léxico só aponta, nunca troca nada, e não vê notação: `Bxf6` e `exd5` não
  aparecem. **Enter** grava o texto do campo nos glifos, uma letra por glifo, e só os que
  mudaram viram manuais; **Ctrl+Enter** também os ensina como padrões do livro. **Tab** pula,
  **Shift+Tab** volta, **Ctrl+I** ignora a palavra nesta sessão e **Ctrl+Shift+D** a põe no
  dicionário do livro (`lexico.txt` do projeto). Se a palavra tem glifos de mais ou de menos,
  o clique no glifo do recorte o abre no painel de treino, para dividir ou juntar. O léxico é
  o do idioma do projeto (`idioma` no `projeto.json`, português por padrão: o pacote Hunspell
  do core com os nomes próprios), mais o `.lexico.txt` que o PyBoxEditor guarda ao lado do
  PDF, só para leitura.
- **Opções** (Ctrl+,) muda os limiares deste livro: quando a leitura vai para a revisão e
  quando o padrão do livro, a rede e a base global são aceitos. Ficam no `projeto.json` e valem
  na hora, sem reconhecer de novo.

Na p. 27 do Darcy Lima, as áreas automáticas são três: as duas partidas e o número da
página. Com o número em "ignorar", o F5 pelas áreas deu 2.111 boxes, os 2.113 da segmentação
inteira menos o "28". A verificação achou 40 palavras em 0,7 s, com o léxico já carregado
(0,6 s na primeira vez), entre elas "Cava1o", "desenvover", "maIoria" e "ganhartempos";
corrigir "Cava1o" para "Cavalo" trocou só o glifo do "1".

### Exportar

**Projeto › Exportar** (Ctrl+E) escreve as páginas já reconhecidas, com as correções, no
formato da extensão escolhida. No DOCX e no EPUB, o cabeçalho e o rodapé corridos e a poeira
da borda da página ficam fora do texto (`exportar.margens_corridas`). Conta como título
corrido a primeira (ou a última) linha que está na faixa de 10% da borda, separada do texto
por um vão de mais de 1,5 passo de linha, curta, e que tem o número da página ou se repete,
só nas letras, no mesmo lugar de outra página exportada. O título de capítulo, sem número e
sem repetição, fica. No Xadrez Vitorioso, p. 21 a 27, saem os sete cabeçalhos ("22 YASSER
SEIRAWAN & JEREMY SILMAN" nas pares, "XADREZ VITORIOSO: ESTRATÉGIAS 23" nas ímpares) e
nenhuma linha do texto. O PDF pesquisável mantém tudo na camada, para a busca achar o
cabeçalho também.

- **PDF pesquisável**: as páginas do PDF original, sem rasterizar, com a leitura do projeto
  como texto invisível, uma palavra por vez. A camada de OCR invisível que o PDF já trazia
  (a do Darcy Lima lê "hb7" onde está "♗b7") é apagada antes; página com texto visível
  próprio fica sem a nossa camada, para a busca não achar tudo duas vezes. Com fonte em
  imagem, cada página vira uma página de PDF a 300 dpi.
- **DOCX** e **EPUB**: pelos escritores do PyBoxEditor (`core.exportar`), com a fonte dos
  símbolos embutida. Os parágrafos saem do vão entre as linhas, a hifenização no fim de linha
  é desfeita e as figurinas saem como impressas.

**Os diagramas na exportação.** O diagrama conferido, ou que o porteiro do PyBoxEditor
(`core.diagrama.confiavel`) aprovou, sai redesenhado do FEN pela fonte de diagrama
(`core.render_diagrama`), com o FEN e o lado a jogar no texto alternativo e "não revisado"
quando ninguém o conferiu. No PDF pesquisável, o FEN entra invisível sobre o tabuleiro, e a
busca o acha; logo abaixo dele, também invisível, vai a mesma marca do lado do texto
alternativo ("brancas a jogar (assumido: a página não diz); não revisado"), para o `w` que a
página não disse não passar por leitura na camada de texto. O resto (por ler, ou lido sem confiança) sai como recorte da página, com o
motivo no aviso e sem FEN, para um FEN duvidoso não passar por leitura. Na p. 26 do Darcy
Lima o porteiro recusa os três diagramas, e eles saem como recorte até serem conferidos;
conferido o primeiro, ele saiu desenhado nos três formatos e o FEN dele foi achado no PDF.

Nas páginas 26 e 27 do Darcy Lima, o lote levou 24 s depois de 13 s carregando os modelos, e
os três arquivos saíram em 1,5 s (PDF), 0,8 s (DOCX) e 0,5 s (EPUB).

### O projeto no disco

Desde o passo 1a, todo arquivo do projeto (as páginas, que desde o 1b trazem as áreas e a
marca de "só glifos marcados", `projeto.json`, `livro.json`, `inclinacoes.json`,
`lexico.txt` e os padrões com os metadados deles) é gravado do mesmo jeito: num `.tmp` ao lado, com `fsync`, e trocado pelo antigo de
uma vez. Uma queda no meio deixa o arquivo antigo inteiro ou o novo inteiro, nunca um JSON
pela metade; se o Windows segurar o arquivo um instante (antivírus, indexador), a gravação
tenta de novo (até 5 tentativas ao todo, a cada 50 ms). Os `.tmp` que uma queda deixar são apagados na próxima abertura.

- **A fonte pode mudar de lugar.** Se o PDF estiver dentro da pasta do projeto, o caminho
  fica relativo, e a pasta inteira pode ser movida. Se a fonte sumir, a abertura procura o
  mesmo arquivo (pelo SHA-256 dos primeiros 4 MB e pelo tamanho) na pasta onde ela estava,
  na pasta do projeto e na pasta-mãe do projeto, e o acha mesmo renomeado (a janela avisa
  onde); se não achar, pede para você mostrar onde ele está, e recusa um arquivo de
  conteúdo diferente. Num projeto só para leitura, o lugar novo vale só na sessão: a busca
  (ou a pergunta) se repete a cada abertura.
- **Projeto de versão mais nova abre só para leitura.** Dá para ver as páginas, mas nada é
  gravado (o título da janela diz "só leitura"). Um campo de `projeto.json` que esta versão
  não conhece não se perde: vai para `extras` e volta igual ao arquivo.
- **`livro.json`** é o resumo de cada página gravada (o `pid` dela, o estado, pendentes, o
  histograma das confianças e os diagramas por conferir), atualizado a cada gravação de
  página. É um cache: se faltar ou estragar, é refeito das páginas na abertura.
- **A gravação não trava a janela (passo 2a).** Uma correção não grava na hora: ela vai
  para um gravador numa thread própria, que junta as mudanças da mesma página e grava meio
  segundo depois da primeira (cem correções seguidas são uma gravação). Se o disco recusar
  (cheio, sem permissão, antivírus segurando o arquivo), a barra de status diz qual página
  não foi gravada; ela continua com as mudanças na memória e o gravador tenta de novo,
  esperando mais a cada vez. **Fechar a janela grava o que falta antes de fechar.** Se
  alguma página não grava, ele pergunta se fecha mesmo assim e perde as mudanças dela;
  "Não" deixa a janela aberta, com tudo na memória, para você liberar o disco e fechar de
  novo. Fechar com o lote rodando cancela o lote e espera a página em leitura terminar (ela
  é gravada; pode levar alguns segundos).

**O modelo v2 (passo 1b).** Cada glifo tem agora uma identidade que não muda (`gid`): a
página tem um número próprio (`pid`), que reordenar ou inserir páginas não muda, e cada
glifo um gid dela. Dividir um glifo aposenta o gid dele e dá gids novos às partes, e o
programa sabe quem veio de quem. O que muda para você:

- **As páginas ficam em `paginas/p<pid>.json`**, com os glifos, as áreas (antes em
  `zonas/`), os diagramas, a marca de "só glifos marcados" (antes em `marcadas.json`) e o
  estado da página: não reconhecida, glifos marcados, reconhecida, em revisão (depois da
  primeira correção) ou verificada (a marcação de verificada chega no passo C).
- **Um projeto antigo migra sozinho.** Na primeira abertura, as páginas, as áreas e o
  `projeto.json` como eram vão para `backup-v1/` (a barra de status avisa), e cada página
  passa ao formato novo quando é aberta pela primeira vez. Num disco onde não dá para
  gravar a cópia, o projeto abre só para leitura, sem migrar.
- **Cada leitura sabe de que padrão veio.** O glifo lido por um padrão do livro guarda qual
  amostra o leu (é o que a revisão do passo C vai mostrar), e o padrão ensinado leva no
  nome o gid do glifo de onde saiu.
- **O estado de cada página** é gravado desde já, mas a janela ainda não o mostra (a
  galeria de páginas é do passo C).
- **O texto da página** (o painel de texto, a busca e as exportações de hoje) sai de um
  documento montado das páginas (`abbychess.texto.montar`), com as decisões que você tomar
  a partir do passo D1 (espaço a mais ou a menos, o caractere que falta, parágrafo). Hoje
  ele sai igual ao de antes, conferido pelos testes de caracterização.

### A página torta

Projeto novo endireita cada página antes de ler. A inclinação é medida pelo perfil de
projeção (`pagina.medir_inclinacao`: gira a tinta de -3° a 3°, de 0,05 em 0,05, e fica com as
linhas mais nítidas) e gravada em `inclinacoes.json`, no projeto, para a imagem sair a mesma
toda vez: os boxes gravados estão nas coordenadas da página endireitada. No PDF pesquisável a
camada de texto volta ao lugar da página original, que não é girada.

Sem isso, a vírgula e o ponto do fim da linha, que ficam baixos, caíam na linha de baixo
("uma Dama" / ", mas agora"). O `core.preprocess.deskew` do PyBoxEditor não serve aqui: ele
mede pelo retângulo mínimo de toda a tinta, e numa página com diagramas mede o diagrama (2,19°
na p. 26 do Xadrez Vitorioso, onde as linhas descem 0,55°). Projeto criado antes disso fica
sem endireitar (`"endireitar": false` no `projeto.json`), porque os boxes dele estão nas
coordenadas da página torta.

## Como a leitura decide

1. **Padrões do livro** (`abbychess/padroes.py`): vizinho mais próximo só entre as amostras
   deste livro, com a altura e a proporção do glifo na comparação. O recorte de 32×32 apaga o
   tamanho e a forma da caixa: sem a altura um `o` ensinado leria todo `O`, e sem a proporção
   o hífen leria o ponto (os dois viram um quadrado preto).
2. **Cadeia global do PyBoxEditor**: a rede de glifos e a base global de cerca de 170 mil
   amostras, com os limiares e vetos medidos lá. O EasyOCR fica desligado.

O que o usuário confirmou e o que saiu de um padrão do livro não volta à fila. O resto volta
abaixo de 0,90 de confiança.

Os diagramas são lidos só pelas redes de diagrama do PyBoxEditor; os padrões do livro não
entram (ver **Os diagramas**).

## O que foi medido

### Xadrez Vitorioso – Estratégias (Seirawan e Silman)

O livro de referência agora é este: digitalizado a cerca de 250 dpi, só imagem, em português.
O Darcy Lima, a 100 dpi e com a camada de OCR de fábrica, ficou para os testes que já o usam.
Páginas 21 a 27, projeto novo, sem nenhum padrão ensinado, com os modelos reais:

| Medida | Página torta | Página endireitada |
|---|---|---|
| Lote das 7 páginas (10 mil glifos) | 68 s | 71 s |
| Linhas que começam com vírgula ou ponto | 12 | 2 |
| Glifos na fila | 1.966 (19%) | 1.914 (19%) |
| Diagramas confiáveis, de 7 | 2 | 3 |
| Diagramas exportados desenhados do FEN | 2 | 3 |

Na p. 26, endireitada, a primeira linha sai "TESTE 1. As pretas têm a vantagem de uma Dama,
mas agora ela está sob ataque." inteira, e o Diagrama 7, que lia uma torre em a2, lê o peão.
O que sobra para o treino do livro é o que ele faz bem: `1` por `l` e `0` por `o` na prosa
("conc1uir", "s0rte") e a fonte em negrito dos títulos e das legendas, que a cadeia global
quase não lê ("Dia rama 6. Jo am a hran as").

**O treino da p. 26.** Num projeto novo (endireitado), a p. 26 foi reconhecida com os modelos
globais e ensinada como na janela: o glifo da cabeça da fila, Enter com o caractere impresso,
a propagação pela página, até a fila acabar. O impresso veio de um gabarito escrito a olho,
linha a linha, sobre os recortes da página, e não da leitura do modelo. Depois, os erros que a
leitura dava com confiança (fora da fila, os que a verificação de texto mostra) foram
ensinados também. As outras páginas foram relidas pelo lote com os padrões, e cada leitura
vinda deles que discordava da cadeia global foi conferida no recorte.

| Medida | Valor |
|---|---|
| Fila da p. 26 ao reconhecer | 204 glifos, de 1.047 |
| Erros de leitura da p. 26 | 38, 4 deles com confiança, fora da fila ("8" por "&", "v" por "V" e "l" por "I" nos títulos, "0u" por "ou") |
| Para zerar a fila | 68 Enter, 1 Ctrl+D (o "Al" colado de "Alguns") e 2 Del (sujeira na borda) |
| Padrões gravados | 72: os 68 e os 4 erros confiantes; mais ensinados: s 11, o 9, S 5, l 4 |
| Ensinar e propagar, sem contar o reconhecimento | 1,6 s no total |
| Leituras da p. 26 vindas dos padrões | 135, todas certas pelo gabarito |
| Fila da p. 26 depois de ensinar | 0 glifos, e nenhum erro fora da fila |
| Fila das p. 21–25 e 27 sem padrões | 1.710 glifos (287, 303, 230, 342, 228 e 320) |
| Fila das mesmas páginas com os 72 padrões | 397 glifos (87, 48, 65, 74, 57 e 66) |
| Lote dessas seis páginas com os padrões | 32 s; o das sete, sem padrões, levou 69 s (a leitura que sai do padrão não passa pela cadeia global) |
| Leituras das outras páginas vindas dos padrões | 1.779: 1.640 iguais à cadeia global, 139 diferentes |
| As 139 diferentes, conferidas no recorte | 137 certas (47 "l" no lugar de "1", 25 "o" de "0", 25 "s" de "S", 13 "v" de "V"); 2 erradas |

As duas erradas são os zeros do roque em negrito, "5.0-0!", que o padrão do "O" de
"VITORIOSO" leu como letra. A primeira rodada teve mais seis: três pontos lidos como hífen, o
hífen do "5...0-0" lido como travessão e dois "1" de lance ("14.Bx", "1.Db8") lidos como "l".
Esticados para 32×32, o hífen (12×4 px) e o ponto (6×6) viram o mesmo quadrado preto. Daí a
trava de proporção do padrão (`padroes.PROPORCAO_MAXIMA`), que tirou essas seis e não mudou
mais nenhuma leitura.

**O lado a jogar pela legenda.** Das sete posições, cinco têm o lado impresso perto: o Teste 1
("Jogam as pretas. O que fazer?", na linha de cima) e as legendas dos Diagramas 5 a 8; as dos
Diagramas 3 e 4 só dão o nome da partida. A leitura do core (`ler_titulo`) não deu nenhuma,
nem depois do treino: ela olha uma faixa de 1,4 vez a escala da página, e as minúsculas da
legenda começam abaixo dela (o título saía "Di7Jb"). Agora a legenda sai das linhas de boxes
da página, com o que o livro ensinou (`diagramas.legendas_dos_boxes`):

| Lado dito pela página, de 7 | Valor |
|---|---|
| Sem padrões | 1 (o Teste 1, cuja linha é prosa em fonte comum) |
| Com os padrões da p. 26 | 4: Teste 1 e Diagramas 6 e 7 ("brancas") e 8 ("pretas") |
| Com mais um Enter, no "g" em negrito da p. 25 (lido "9") | 5: o Diagrama 5 ("pretas") |
| Lado errado | nenhum; os Diagramas 3 e 4 continuam "assumido" |

### Darcy Lima e Júlio Lapertosa

No livro do Darcy Lima e Júlio Lapertosa, páginas 26 e 27, com os modelos reais:

| Medida | Valor |
|---|---|
| Reconhecer uma página de 1.700 glifos | cerca de 13 s |
| Ensinar um padrão e propagar pela página | 0,45 s |
| Fila da p. 26 ao reconhecer | 373 glifos |
| Fila da p. 26 depois de ensinar 13 padrões | 46 glifos |
| Fila da p. 27 sem padrões do livro | 313 glifos |
| Fila da p. 27 com os 13 padrões da p. 26 | 189 glifos |
| Leituras da p. 27 vindas dos padrões | 259, todas conferidas certas |

Na simulação, cada padrão foi ensinado com a leitura que o modelo já dava, conferida depois
contra a cadeia global e, nas quatro discordâncias, a olho. O limiar e a trava de altura têm
a tabela de calibração no docstring de `abbychess/padroes.py`.

Os três diagramas da p. 26, sem moldura e sem coordenadas, saem lidos em 0,2 s no total
(o F5 da página inteira passou a 15 s):

| Diagrama | Leitura | Porteiro |
|---|---|---|
| 1, no alto à direita | certa, com 1 casa trocada pela legalidade | desconfia: casa mais fraca em 15% |
| 2, no meio à direita | certa | desconfia: casa mais fraca em 69% |
| 3, o esquema com setas | errada: as setas viram peças, 33 peças | posição impossível |

Os três abrem na conferência; o terceiro se corrige casa a casa até a posição do segundo,
que é a mesma. O lado a jogar sai "assumido" nos três: a página não diz.

### As medidas do roadmap

A primeira tabela é a linha de base, medida em 2026-10-16 com o código do passo 0 (a tag
`passo-0`); as seguintes trazem cada passo ao lado dela. A qualidade e a fatia mostram a
medida mais nova, com o commit, e o histórico da qualidade mostra todas. As tabelas são
geradas dos JSON de `docs/medidas/` por `ferramentas\resumo_medidas.py`; não as edite à mão.

<!-- medidas:inicio -->
Desempenho, de `docs/medidas/2026-10-16-linha-de-base.json` (commit 76ba432; máquina cadastrada: sim; p95 de 30 repetições):

| Meta (spec §2) | Hoje | Alvo |
|---|---|---|
| Trocar de página (não há cache) | p95 194 ms | 150 ms no cache; fora do cache ainda não medido pelo método |
| Enter até a cor do box mudar | p95 111 ms (0 → 35 padrões no livro; 7 das 30 repetições ensinaram caractere novo) | 100 ms |
| Releitura de um glifo | p95 146 ms; impossível com o lote | 150 ms com o lote |
| Memória do desfazer, 300 páginas × 20 ações | ~4182,9 MB (estimado de 60 ações em 3 páginas, extrapolado) | 50 MB |
| Atraso da interface durante o lote (20 páginas) | p99 8,5 ms, com as ações desabilitadas | 50 ms, com as ações |
| Memória com o lote | 1620 MB num processo | 2560 MB |
| Buscar regex no livro | não existe | 1000 ms |
| Montar o índice da busca | não existe | 2000 ms |

Desempenho por passo, em ms ou MB (uma rodada cada, a do portão, que roda no mesmo processo depois dos testes `livro_real` e por isso não é a condição das rodadas repetidas; quanto o mesmo código varia, e o que se conclui, está nelas, abaixo):

| Meta | linha de base | 1a (`2026-10-16-passo-1a.json`) | 1b (`2026-10-16-passo-1b.json`) | 2a (`2026-10-16-passo-2a.json`) | 2b (`2026-10-16-passo-2b.json`) |
|---|---|---|---|---|---|
| Troca de página, p95 | 194,22 | 190,06 | 186,8 | 190,79 | 161,89 |
| Enter, p95 | 110,88 | 119,73 | 138,17 | 89,43 | 23,68 |
| Releitura, p95 | 145,73 | 122,08 | 166,34 | 85,98 | 16,92 |
| Desfazer (MB) | 4182,9 | 4182,9 | 4120,9 | 164 | 8 |
| Atraso no lote, p99 | 8,5 | 8,6 | 15,1 | 13,1 | 12,9 |
| Memória com o lote (MB) | 1620 | 1661 | 1676 | 1653 | 1654 |

Rodadas repetidas, em ms (cada valor é uma rodada, na ordem em que rodou). Sem o congelamento dos modelos para a coleta de lixo (até o 1a, e no 1b com `ABBY_SEM_CONGELAR=1`), o p95 do Enter do passo 0 ao 1b tem duas faixas no mesmo código (perto de 110–130 e de 180–235; no 2a, uma só, perto de 90); o atraso no lote tem duas faixas sempre (perto de 8–10 e de 21). Desde o 2b o congelamento é desligado (`ABBY_CONGELAR=1` liga): as duas linhas do 2b rodam o mesmo programa (o rótulo `sem_congelar` é do roteiro de medida), e a coluna do Enter mede até a cor mudar (até o 2a, até o fim da propagação). Compare pela mediana (p50), que varia bem menos (mas uma rodada solta pode sair alta):

| Código | Commit | Rodada | Troca, p50 | Troca, p95 | Enter, p50 | Enter, p95 | Releitura, p50 | Releitura, p95 | Atraso no lote, p99 |
|---|---|---|---|---|---|---|---|---|---|
| passo 0 | 25e81b1 | completa | 169,76; 174,14; 171,68 | 192,19; 190,98; 192,11 | 104,33; 104,61; 104,66 | 177,63; 179,72; 179,81 | 107,34; 107,54; 105,85 | 124,76; 129,43; 142,69 | 21,4; 8,7; 8,3 |
| passo 0 | 25e81b1 | só do lote, sem os padrões | — | — | — | — | — | — | 19,9; 7,7; 7,1 |
| passo 1a | 315db35 | completa | 180,73; 183,85; 180,22 | 195,04; 198,16; 196,84 | 149,4; 114,34; 113,81 | 191,17; 190,97; 190,82 | 133,34; 111,81; 111,19 | 165,4; 150,71; 141,33 | 20,8; 21,3; 8,7 |
| passo 1a | 3bf1ad3 | só do lote, sem os padrões | — | — | — | — | — | — | 7,5; 20,5; 7,7 |
| passo 1b | 1519d8f | completa | 170,01; 166,11; 167,1 | 184,66; 192,26; 182,72 | 125,37; 140,8; 125,31 | 149,77; 149,56; 139,9 | 131,89; 139,62; 131,52 | 154,31; 159,37; 158,59 | 17,7; 15; 16,6 |
| passo 1b sem congelar | 1519d8f | completa | 169,84; 175,66; 170,16 | 192,25; 202,72; 196,29 | 123,14; 126,27; 144,94 | 199,91; 203,93; 234,95 | 124,11; 123,85; 140,89 | 142,6; 150,72; 233,54 | 14,4; 15,5; 16,3 |
| passo 2a | d19c858 | completa | 162,65; 167,54; 171,97 | 180,58; 191,56; 190,65 | 91,38; 82,94; 83,67 | 95,14; 115,58; 90,57 | 74,82; 74,92; 74,59 | 85,61; 90,63; 106,11 | 10,2; 10,1; 21,6 |
| passo 2a sem congelar | d19c858 | completa | 174,66; 175,73; 178,05 | 188,01; 188,63; 188,4 | 82,23; 82,43; 82,52 | 91,7; 89,92; 92,03 | 73,15; 70,64; 75,29 | 88,33; 91,91; 92,78 | 11,7; 20,8; 21,5 |
| passo 2b | 6f863c3 | completa | 157,59; 153,58; 153,66 | 189,56; 171,05; 174,1 | 20,85; 21,1; 20,62 | 25,5; 26,13; 25,7 | 13,33; 13,59; 15,26 | 15,65; 16,1; 19,15 | 20,2; 22; 21,8 |
| passo 2b sem congelar | 6f863c3 | completa | 153,56; 153,19; 157,37 | 173,65; 165,46; 168,14 | 20,55; 20,57; 21,47 | 24,01; 27,01; 27,08 | 14,4; 13,82; 14,5 | 16,9; 16,99; 18,83 | 22,3; 9,1; 9,8 |

Qualidade contra os gabaritos (`ferramentas\medir.py`). **Margens corridas**: cabeçalho, número de página e rodapé tirados do texto. **Sem par**: linhas lidas que não casam com nenhuma linha do gabarito (inventadas); as das páginas negativas (capa, sumário) vão à parte. **Perdidas**: linhas do gabarito que a leitura não achou. **Casas** e **lado** só contam nos diagramas que você conferiu; o provisório, entre parênteses, é contra o FEN rotulado pelo assistente (casa a casa, contra o recorte), ainda não conferido por você, e a coluna **FEN = leitura** diz em quantos ele é igual ao que o programa leu. **Ordem**: pares de linhas casadas fora da ordem de leitura do gabarito (não vê onde o diagrama cai no texto). "—" é nada a medir.

| Livro | Commit | Páginas | Margens corridas P / R | Diagramas achados (falsos) | Sem par | Sem par nas negativas | Perdidas | FEN = leitura | Casas erradas por diagrama | Lado certo | Ordem | CER do corpo | Estado |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| xv | 6f863c3 | 9 | 0,875 / 1 | 7/7 (1) | 6 | 833 (2 pág.) | 3 (+10 nas negativas) | 7/7 | pendente (provisório: 0) | pendente (provisório: 1/5) | 0 | pendente | provisória: estrutura revisada em 0/9 páginas; FEN conferido em 0/7 diagramas; texto verificado em 0/241 linhas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual |
| yusupov | 6f863c3 | 3 | 1 / 0,75 | 3/3 (0) | 8 | — | 13 | 3/3 | pendente (provisório: 0) | pendente (provisório: 0/3) | 0 | pendente | provisória: estrutura revisada em 0/3 páginas; FEN conferido em 0/3 diagramas; texto verificado em 0/157 linhas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual |
| darcy | 6f863c3 | 2 | — / 0 | 3/3 (0) | 1 | — | 0 | 2/3 | pendente (provisório: 3) | pendente (provisório: 0/1) | 0 | pendente | provisória: estrutura revisada em 0/2 páginas; FEN conferido em 0/3 diagramas; texto verificado em 0/97 linhas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual |

Ainda não medido: a ligação da legenda ao diagrama, no passo H (a leitura de hoje não liga legenda a diagrama); precisão e revocação por função de bloco, no passo F (a leitura de hoje não classifica blocos); a validação do FEN pelos lances, no passo H.

Histórico da qualidade (todas as medidas; casas e lado provisórios):

| Livro | Commit | Margens P / R | Diagramas (falsos) | Sem par | Perdidas | Casas | Lado | Lote |
|---|---|---|---|---|---|---|---|---|
| xv | bb0b7e5 | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 430,6 s |
| xv | 0ebbf9c | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 433,3 s |
| xv | 3bf1ad3 | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 433,6 s |
| xv | 315db35 | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 432,2 s |
| xv | bab6a1a | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 434,2 s |
| xv | 5f969c7 | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 434,5 s |
| xv | d19c858 | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 459,6 s |
| xv | b5c5142 | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 447,3 s |
| xv | 6f863c3 | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 446,6 s |
| yusupov | bb0b7e5 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23 s |
| yusupov | 0ebbf9c | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23,1 s |
| yusupov | 3bf1ad3 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23,4 s |
| yusupov | bab6a1a | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23,4 s |
| yusupov | 5f969c7 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23,3 s |
| yusupov | d19c858 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 24,4 s |
| yusupov | b5c5142 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23,8 s |
| yusupov | 6f863c3 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 25,8 s |
| darcy | bb0b7e5 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 23,5 s |
| darcy | 0ebbf9c | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 23,7 s |
| darcy | 3bf1ad3 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 23,8 s |
| darcy | bab6a1a | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 23,8 s |
| darcy | 5f969c7 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 23,7 s |
| darcy | d19c858 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 25,5 s |
| darcy | b5c5142 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 24,3 s |
| darcy | 6f863c3 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 25,4 s |

Fatia (`ferramentas\replay_fatia.py`; **erros** são as diferenças do snapshot contra o gabarito, o N da medida humana):

| Livro | Passo | Páginas | Total | Gestos dos diagramas | Navegação | Erros | Estado | JSON |
|---|---|---|---|---|---|---|---|---|
| xv | 0 | i020, i021, i022, i023, i024, i025, i026 | gestos pendentes | 14 | 6 | 4 (diagramas; texto pendente) | pendente: nenhuma linha com texto verificado; estrutura revisada em 0/7 páginas; FEN conferido em 0/7 diagramas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual | `2026-10-16-fatia-xv-passo-0.json` |
| xv | 1a | i020, i021, i022, i023, i024, i025, i026 | gestos pendentes | 14 | 6 | 4 (diagramas; texto pendente) | pendente: nenhuma linha com texto verificado; estrutura revisada em 0/7 páginas; FEN conferido em 0/7 diagramas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual | `2026-10-16-fatia-xv-passo-1a.json` |
| xv | 1b | i020, i021, i022, i023, i024, i025, i026 | gestos pendentes | 14 | 6 | 4 (diagramas; texto pendente) | pendente: nenhuma linha com texto verificado; estrutura revisada em 0/7 páginas; FEN conferido em 0/7 diagramas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual | `2026-10-16-fatia-xv-passo-1b.json` |
| xv | 2a | i020, i021, i022, i023, i024, i025, i026 | gestos pendentes | 14 | 6 | 4 (diagramas; texto pendente) | pendente: nenhuma linha com texto verificado; estrutura revisada em 0/7 páginas; FEN conferido em 0/7 diagramas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual | `2026-10-16-fatia-xv-passo-2a.json` |
| xv | 2b | i020, i021, i022, i023, i024, i025, i026 | gestos pendentes | 14 | 6 | 4 (diagramas; texto pendente) | pendente: nenhuma linha com texto verificado; estrutura revisada em 0/7 páginas; FEN conferido em 0/7 diagramas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual | `2026-10-16-fatia-xv-passo-2b.json` |
<!-- medidas:fim -->

O replay da fatia (os gestos para levar as p. 21–27 ao gabarito) é
`ferramentas\replay_fatia.py rodar --livro xv --passo 0`; o texto dele fica **pendente**
até você verificar o texto dos gabaritos, e os gestos dos diagramas ficam **provisórios**
até os FEN serem conferidos.

**A linha de base fica presa à tag `passo-0`.** O replay e as medidas chamam o núcleo do
programa, que os passos seguintes mudam. Por isso a linha de base é sempre medida com o
código do passo 0, num worktree da tag, mesmo depois que o roadmap andar:

```text
git worktree add ..\AbbyChessCraft_passo0 passo-0
cd ..\AbbyChessCraft_passo0
..\AbbyChessCraft\.venv\Scripts\python.exe ferramentas\replay_fatia.py rodar --livro xv --passo 0
```

Os gabaritos e o catálogo de comandos do worktree têm de ser os da medida nova (o
`comparar` recusa medidas com gabaritos ou catálogos de versões diferentes); copie-os antes
de rodar, e traga o JSON de volta:

```text
robocopy tests\verdade ..\AbbyChessCraft_passo0\tests\verdade /E
copy ferramentas\replay\comandos.yaml ..\AbbyChessCraft_passo0\ferramentas\replay\
copy ..\AbbyChessCraft_passo0\docs\medidas\*-fatia-xv-passo-0*.json docs\medidas\
```

### Os gabaritos

`tests/verdade/` tem o gabarito de 14 páginas:

| Livro | Páginas (índice do PDF) | Para medir |
|---|---|---|
| Xadrez Vitorioso | 20–26 (impressas 21–27) | o corpo, os cabeçalhos, as legendas e 7 diagramas |
| Xadrez Vitorioso | 0 (capa), 7 (sumário) | páginas negativas: nada de corpo nem diagrama inventado; a 21 (impressa 22) é a terceira negativa, sem diagrama |
| Yusupov | 6 (uma coluna), 12 (duas colunas com 3 diagramas), 33 (duas colunas, soluções) | colunas e ordem de leitura |
| Darcy Lima | 25 e 26 (impressas 27 e 28) | a digitalização ruim e 3 diagramas sem moldura |

São 13 diagramas ao todo. O protocolo está em `docs/protocolo-rotulagem.md`. A
**estrutura** (função de cada bloco, ordem, colunas, negrito, os diagramas com FEN, lado a
jogar, legenda e primeiros lances) foi rotulada pelo assistente olhando as faixas da
página. O **texto** de cada linha é seu: o assistente não transcreve o texto dos livros,
que têm direito autoral.

#### O que falta você fazer

O passo 0 está fechado como código: as ferramentas, os gabaritos com a estrutura e as
medidas de hoje. As etapas abaixo são suas. Elas **não bloqueiam os passos 1a a A2**,
porque a linha de base pode ser medida de novo a qualquer momento no worktree da tag
`passo-0` (acima). Mas o **texto e os FEN das p. 21–27 do Xadrez Vitorioso têm de estar
verificados antes do fechamento do A3**, o primeiro passo julgado pelos gestos da fatia
(sem eles, o número não existe). Enquanto isso, as medidas de texto ficam "pendentes" e as
de diagrama e estrutura, "provisórias", e o README diz isso em cada tabela.

**A ordem importa para a conferência cega.** Se você faz tudo sozinho, comece por ela: gere
o modelo e transcreva a página às cegas (etapa 3), e monte às cegas o FEN de um diagrama por
livro, **antes** de abrir o gabarito ou o `.txt`. Depois revise a estrutura e o texto (etapas
1 e 2). O `cego --txt` que grava o resultado roda **por último**, depois do `texto-importar`:
ele compara com o texto verificado e fica preso à versão do gabarito, que o importar sobe.

1. **Revisar a estrutura** de cada gabarito (`tests\verdade\<livro>\iNNN.json`) olhando as
   faixas em `.rotulagem\<livro>\iNNN\`. Corrija no JSON o que estiver errado (função,
   ordem, coluna, caixas). Para cada diagrama, confira o FEN casa a casa contra
   `.rotulagem\<livro>\iNNN\diagrama_dN.png` e o lado a jogar; depois assine, dizendo
   quais FEN e lados você conferiu:

   ```text
   .venv\Scripts\python.exe ferramentas\rotular.py revisar --livro xv --pagina i020 --por "Seu nome" --fen-verificado d0 --lado-verificado d0
   ```

2. **Verificar o texto**, um livro por vez:

   ```text
   .venv\Scripts\python.exe ferramentas\rotular.py texto-exportar --livro xv
   ```

   Abra `.rotulagem\xv\iNNN.txt` (uma linha por linha impressa, `lNN<TAB>texto`) ao lado
   de `.rotulagem\xv\iNNN\faixa_KK.png` (o id vermelho na margem é o da linha), corrija o
   texto e apague o `!` do começo **só** das linhas que você conferiu: apagar os `!` em
   massa marcaria como verdade a leitura do próprio programa. Depois:

   ```text
   .venv\Scripts\python.exe ferramentas\rotular.py texto-importar --livro xv --por "Seu nome"
   ```

3. **Conferência cega** (outra pessoa, ou você antes das etapas 1 e 2), numa página por
   livro. O modelo traz os ids das linhas, com o texto em branco:

   ```text
   .venv\Scripts\python.exe ferramentas\rotular.py cego-modelo --livro xv --pagina i022
   ```

   Transcreva cada linha em `.rotulagem\xv\i022.cego.txt` olhando só as faixas, e grave
   o resultado no gabarito (aprova com concordância ≥ 99,5%):

   ```text
   .venv\Scripts\python.exe ferramentas\rotular.py cego --livro xv --pagina i022 --por "Nome" --txt .rotulagem\xv\i022.cego.txt
   ```

   O mesmo com um diagrama por livro: monte o FEN só pela imagem do diagrama, sem ver o do
   gabarito, e rode `rotular.py cego --livro xv --pagina i020 --por "Nome" --diagrama d0
   --fen "<FEN>"`; igual ao gabarito, o FEN fica conferido.
4. **Validar**, em cada livro: `ferramentas\rotular.py validar --livro <livro>` sem
   problemas (FEN de 8×8, lado, legenda que existe, ordens únicas).
5. **Medir de novo** (comandos exatos) e gerar as tabelas:

   ```text
   .venv\Scripts\python.exe ferramentas\medir.py --livro xv --indices 0,7,20-26
   .venv\Scripts\python.exe ferramentas\medir.py --livro yusupov --indices 6,12,33
   .venv\Scripts\python.exe ferramentas\medir.py --livro darcy --indices 25,26
   .venv\Scripts\python.exe ferramentas\resumo_medidas.py
   ```

   e o replay da linha de base no worktree da tag `passo-0` (acima).
6. **A medida humana da fatia (CA-F.2)**, informativa: no programa da tag `passo-0`, abra
   uma cópia do snapshot da fatia com o registro de gestos ligado, corrija as páginas
   índices 20–22 e some o tempo; o protocolo completo (os blocos e a segunda sessão depois
   de 7 dias) está em `docs\medidas\protocolo-fatia.md`.

   No worktree da tag, e depois no checkout principal (o registro vai para um caminho
   absoluto, e a variável é desligada depois da sessão):

   ```text
   $env:ABBY_REGISTRO_DE_EVENTOS = "C:\Python-Chess2\sessao-base.jsonl"; ..\AbbyChessCraft\.venv\Scripts\python.exe -m abbychess <cópia do projeto>; Remove-Item Env:ABBY_REGISTRO_DE_EVENTOS
   .venv\Scripts\python.exe ferramentas\tempo_da_fatia.py C:\Python-Chess2\sessao-base.jsonl --erros <N> --por "Seu nome" --passo 0 --bloco i020-i022
   ```

   O N é a soma dos erros das páginas do bloco (`paginas.iNNN.erros` no JSON da fatia
   medido com o texto verificado).

`.rotulagem` fica fora do git. "p. N" nas seções mais acima é o número da página no
programa (a do PDF, índice N − 1); os gabaritos dizem também a página impressa.

## Onde está o quê

| Arquivo | O que faz |
|---|---|
| `abbychess/projeto.py` | A pasta do projeto: fonte (relativa, relocalizada pelo SHA-256), idioma, limiares, `extras`, só leitura, as páginas no formato v2 (`p<pid>.json`), a migração do v1, `livro.json` |
| `abbychess/modelo.py` | O modelo da página: `Box` com gid, decisões, `Diferenca`, `Pagina` (e o instantâneo dela), o estado da página e a reconciliação da página relida (F5, lote) |
| `abbychess/edicao.py` | As edições por gid (dividir, juntar, marcar, ajustar, corrigir, descartar, quebrar e juntar palavras, glifo virtual), cada uma com os sucessores, sem mudar nada no lugar |
| `abbychess/controlador.py` | O `ControladorDePagina`: a página aberta, a fila, a seleção, o desfazer e os comandos da janela, por gid e sem Qt |
| `abbychess/controladores.py` | Os controladores das áreas, da verificação, dos diagramas e do livro (abrir, lote, F6, exportar) |
| `abbychess/gravador.py` | O gravador das páginas: uma thread, instantâneos imutáveis, coalescência de meio segundo |
| `abbychess/texto.py` | O documento derivado da página (`montar`) e o texto dele, nos modos impresso e SAN |
| `abbychess/procedencia.py` | De que amostra do livro veio cada leitura |
| `abbychess/gravacao.py` | A gravação atômica de todo arquivo do projeto e a trava de só leitura |
| `abbychess/zonas.py` | As áreas da página: geometria, áreas automáticas, reconhecer pelas áreas |
| `abbychess/verificacao.py` | O léxico do livro, as palavras desconhecidas e a correção por glifo |
| `abbychess/padroes.py` | Os padrões do livro, com altura, proporção e leitura segura para acento |
| `abbychess/leitor.py` | A ordem da leitura: padrões do livro, depois a cadeia global |
| `abbychess/pagina.py` | Segmentar, separar diagramas, ler, ensinar, propagar, dividir e juntar boxes, montar o texto |
| `abbychess/diagramas.py` | Ler cada tabuleiro em FEN, o lado a jogar (pela legenda nos boxes), a conferência, as amostras no projeto e o FEN no texto |
| `abbychess/livro.py` | O lote de páginas, com cancelamento, e a fila de revisão do livro todo |
| `abbychess/exportar.py` | PDF pesquisável, DOCX e EPUB a partir das páginas gravadas, pelo core do PyBoxEditor, sem o cabeçalho e o rodapé corridos |
| `abbychess/historico.py` | O desfazer do projeto: transações por gid (o que cada ação mudou, por página), a pré-condição, o limite de 50 MB, a propagação que emenda o Enter |
| `abbychess/app/` | A interface PySide6: a janela (só liga sinais aos controladores e desenha), `acoes.py` (menus e atalhos), `dialogos.py`, o executor com fila (`trabalho.py`), visor da página, painéis de treino, padrões e verificação, opções, conferência de diagramas |
| `tests/` | O núcleo e a janela, sem depender do modelo global |
| `docs/ANALISE_PYBOXEDITOR.md` | O que o PyBoxEditor oferece a este projeto |
| `docs/SPEC.md` | A especificação da aplicação completa (v0.4, aprovada nas revisões) |
| `plans/abbychesscraft-roadmap.md` | O roadmap em passos, com a ordem serial e o contrato de cada passo |
| `docs/pesquisa/`, `docs/revisoes/` | A pesquisa do FineReader e a auditoria do programa; o registro das rodadas de revisão |
| `docs/atalhos.yaml`, `docs/ATALHOS.md` | Os atalhos (a fonte única) e a tabela gerada |
| `docs/medidas/` | A máquina cadastrada e cada medida, em JSON |
| `abbychess/atalhos.py` | Ler e conferir a tabela de atalhos, sem Qt |
| `ferramentas/` | `rotular.py` (gabaritos, conferência cega, revisão), `medir.py` (qualidade), `replay_fatia.py` e `replay/comandos.yaml` (a fatia), `tempo_da_fatia.py` (CA-F.2), `atalhos.py`, `resumo_medidas.py` (as tabelas do README) |
| `abbychess/app/registro_de_eventos.py` | O registro de gestos da CA-F.2, ligado por `ABBY_REGISTRO_DE_EVENTOS` |
| `tests/verdade/`, `tests/dados/fatia/` | Os gabaritos e o snapshot da fatia (conteúdo de livros: não publicar) |
| `tests/golden/caracterizacao/` | O comportamento de hoje, fixado antes da refatoração do roadmap |

## Limitações conhecidas

- **Voltar a um programa de antes do 1b** pede a cópia: o programa do 1a abre o projeto
  migrado só para leitura (o formato é o 2) e mostra as páginas migradas como não lidas.
  Copiar `backup-v1/` por cima do projeto devolve as páginas, as áreas e o `projeto.json`
  de antes da migração; **não volta** o que foi feito depois dela: correções nas páginas
  (inclusive as lidas pela primeira vez depois, que ficam só em `paginas/p<pid>.json`),
  padrões ensinados (`padroes/`), palavras do léxico, amostras de diagrama e inclinações.
  Antes de abrir um projeto importante pela primeira vez no 1b, vale copiar a pasta inteira.
- **O Enter e a releitura, desde o passo 2b** (tabela "Rodadas repetidas": 6 rodadas do
  commit `6f863c3`, com a pasta limpa e sem o congelamento, que saiu no 2b; sem o lote
  rodando). O Enter até a cor mudar ficou em 21 ms na mediana e 24–27 ms no p95 (alvo de
  100); até o fim da propagação, que é o que o 2a media como Enter, em 71–74 ms na mediana
  (2a: 82–91). Com uma propagação lenta em curso (1 s injetado), o segundo Enter muda de
  cor em 19–30 ms (p95). O ajuste de borda (a releitura de um glifo) ficou em 13–15 ms na
  mediana e 16–19 no p95 (alvo de 150; 2a: 71–75 na mediana). **A medida mudou junto**:
  desde o 2b o painel de texto da página é refeito 150 ms depois da última mudança, fora do
  tempo do Enter e da releitura, e custa 22 ms (p95 22–29) na thread da interface, à parte
  (`texto_da_pagina`); no 2a ele entrava nas duas medidas. Mesmo somando, a releitura fica
  em ~37 ms. A troca de página ficou em 153–158 ms (alvo de 150, no passo A1). O alvo de §2
  vale "com o lote rodando", o que só o passo E permite medir.
- **A memória do desfazer está no alvo** para correções de um glifo (é o que a medida faz:
  300 correções reais em 3 páginas): 8,0–8,1 MB para 300 páginas × 20 ações pelo
  `tracemalloc` (o portão e uma rodada só da memória no commit `badede5`, outra no `b291e91`,
  que só mexe na verificação), e a estimativa do
  próprio histórico, a que o limite de 50 MB usa, 6,9–7,3 MB, uns 10% abaixo. Nas 6 rodadas
  repetidas a medida ainda tinha o gravador gravando entre as duas leituras, e uma deu −9,6
  (o portão do 6f863c3, que está no commit `84b3ce6`, deu 0,2); o teste passou a esperar o
  gravador antes de cada leitura. O F5 é a ação mais cara (a página inteira); 50 MB cabem
  umas 50 páginas reconhecidas de novo, e as ações mais antigas saem antes.
- **O congelamento dos modelos para a coleta de lixo (`gc.freeze`) saiu no 2b.** Nas 6
  rodadas do commit `b5c5142` (3 com e 3 sem, `docs/medidas/2026-10-16-congelamento-2b-*`)
  ele não ajudou: sem ele, as medianas do Enter,
  da releitura e da troca ficaram iguais ou um pouco melhores; no atraso durante o lote, 2
  das 3 sem ele caíram na faixa de ~21 ms (com ele, 1 de 3), o que é a variação de sempre
  dessa medida, e uma das rodadas com ele estava perturbada (um pico de 935 ms no lote).
  `ABBY_CONGELAR=1` o religa, para medir de novo.
- **O atraso da interface durante o lote** tem duas faixas no p99 (perto de 9 e de 22 ms),
  como em todos os passos, abaixo do alvo de 50 ms. O máximo ficou em 128–154 ms nas 6
  rodadas (até o 1b, 85–105; desde o 2a o lote do teste passa pelo controlador do livro, que
  grava o pendente antes de começar e recarrega a página aberta no fim). No 2a, uma rodada
  com o instante de cada atraso (`docs/medidas/2026-10-16-pico-do-lote-2a-parcial.json`,
  árvore suja, máquina ocupada) achou o maior no recarregar da página, 0,17 s depois do fim
  do lote, e outros de até 125 ms no meio dele. A origem dos picos fica para o passo E, que
  tira o lote do processo da interface.
- **O tempo do lote** de 20 páginas das rodadas de desempenho ficou em 86–93 s no 2b (2a:
  105,5–108,1 s; 1b: 102,4–113,4 s). No `medir.py` (uma rodada por livro), o xv levou 447 s
  (2a: 460; 1b: 431–435).
- **Uma queda pode perder o último meio segundo.** O gravador grava meio segundo depois da
  primeira mudança: o que foi feito nesse intervalo, mais o tempo da gravação, se perde
  numa queda de energia ou se o programa for morto (medido pelos testes de processo: tudo o
  que tinha mais de 500 ms + t_fsync estava gravado). **Com o disco recusando**, a perda numa
  queda é tudo o que mudou desde a primeira falha (a barra de status avisa na hora). Fechar a
  janela normalmente grava tudo.
- **A busca automática da fonte lê no máximo 200 arquivos do tamanho certo** por pasta
  procurada; numa pasta com mais que isso, ela desiste e pede para você mostrar a fonte.
- **No projeto só para leitura, as ações que gravam falham com aviso** em vez de ficarem
  desabilitadas: ensinar e esquecer padrões, guardar as casas de um diagrama conferido e o
  reconhecimento em lote (que avisa só depois de ler a primeira página). A correção feita na
  tela fica só na memória: some ao fechar (ou quando a página sai das 16 que o programa
  guarda). A janela passa a desligar essas ações no passo A2.
- **Um projeto aberto por este programa não abre mais no programa da tag `passo-0`.** A
  primeira abertura grava em `projeto.json` campos novos (`fonte_sha256`, `fonte_tamanho`,
  `extras`), que o programa do passo 0 recusa como "ilegível". Para voltar ao passo 0 com um
  livro em andamento, use a cópia de segurança de antes do passo.

- **O Del do treino não descarta o box com o foco no campo do caractere.** O campo fica com a
  tecla, mesmo vazio (achado da tabela de atalhos no passo 0). Por enquanto, use o botão
  "Não é caractere"; o passo A2 corrige pela regra 6 de §3.4 da spec.
- **O repositório tem conteúdo de livros** (`tests/verdade/`, `tests/dados/fatia/`): ele é
  privado e fica local, por decisão do passo 0 (o texto dos gabaritos é a referência das
  medidas e precisa estar versionado com elas). Não publique o repositório; para publicar,
  tire essas pastas do histórico antes.

- **Dividir corta numa coluna só.** O corte escolhido à mão é sempre vertical e reto; dois
  glifos empilhados ou encaixados em diagonal só se dividem pelo corte automático, que
  escolhe o eixo pela tinta, ou se dividem e depois se ajustam as bordas.
- **O FineReader ainda não foi clonado inteiro.** Do menu Ferramentas existem o modo de
  treino, os padrões, as opções, o reconhecimento do livro em lote e a fila do livro; no
  Projeto, a exportação; o editor de áreas, a verificação de texto e a leitura e
  conferência dos diagramas.
- **O lote não aprende sozinho.** Ele lê com os padrões que existem quando começa; ensinar
  durante o lote não é possível (a edição é recusada com aviso enquanto ele roda), e o que
  se ensina depois só vale para as páginas lidas de novo ou com Ctrl+R. O lote grava as
  páginas na thread dele, e não pelo gravador; o servidor de leitura do passo E muda isso.
- **Os parágrafos exportados saem do vão entre linhas.** Recuo de primeira linha, títulos,
  cabeçalho e rodapé de página não são reconhecidos: o cabeçalho corrido entra como
  parágrafo, e uma página de duas colunas sai na ordem de leitura, mas sem marcar a coluna.
- **A camada do PDF pesquisável supõe página sem rotação.** Página com `/Rotate` no PDF
  recebe o texto nas coordenadas da página renderizada, que não batem com as da página
  girada.
- **O cabeçalho corrido é achado por regra, não por layout.** A linha de cabeçalho colada no
  texto (sem o vão), ou o cabeçalho que não tem número e aparece numa página só da
  exportação, entra no texto como parágrafo.
- **As áreas valem no próximo reconhecimento.** Mudar uma área não tira nem acrescenta boxes
  na hora: é preciso o F5, que troca os boxes da página pelos das áreas.
- **A verificação de texto não junta nem separa palavras.** "ganhartempos" aparece como uma
  palavra desconhecida, mas o espaço que falta não é um glifo; a palavra fica sinalizada até
  ir para o dicionário ou ser ignorada. Pedaços de lance que o core não reconhece como
  notação ("xd", "O...Qf") também aparecem.
- **O desfazer é da sessão.** Fechar o projeto o esquece, e ele guarda até 50 MB pela
  estimativa dele (as ações mais antigas saem). Ficam fora dele o reconhecimento em lote
  (que ganha "voltar ao estado antes do lote" no passo E) e as amostras de diagrama
  guardadas na conferência (a conferência em si se desfaz). Depois de um lote que releu
  uma página, o Ctrl+Z das ações de antes nela é recusado (os glifos mudaram), e a pergunta
  da recusa deixa tirá-las do caminho.
- **Endireitar só corrige a inclinação.** Página curva perto da lombada, ou girada mais
  de 3°, não se endireita; projeto antigo não endireita (ver **A página torta**).
- **A legenda só diz o lado depois de ensinada.** No Xadrez Vitorioso a cadeia global lê mal
  a fonte em negrito das legendas ("Jo am a hran as"), e o lado sai assumido até ela ser
  ensinada (ver **O que foi medido**). Ensinada ou corrigida na página, o lado muda na hora;
  mas o padrão novo só chega às legendas das outras páginas quando elas são lidas de novo
  (F5 ou lote). **Reler pendentes** (Ctrl+R) não muda o lado.
- **A linha encostada no diagrama é tomada por legenda.** Até 3,5 alturas de referência acima
  ou abaixo do tabuleiro, a linha que diz "jogam as pretas" vale como legenda, mesmo que seja
  prosa. No Teste 1 do Xadrez Vitorioso a prosa é o enunciado e acerta; num livro em que o
  texto contorna o diagrama, pode dizer o lado de outra posição.
- **O "O" e o "0" em negrito se confundem.** O padrão do "O" de um título leu os zeros do roque
  "0-0" como letra; a altura e a proporção não os separam, e o glifo não volta à fila.
- **O diagrama só é desenhado do FEN com confiança.** Sem conferir, o porteiro do
  PyBoxEditor recusa boa parte dos diagramas de um livro digitalizado (os três da p. 26 do
  Darcy Lima), e eles saem como recorte. Conferir é o que os leva desenhados ao arquivo.
- **A posição do diagrama no texto é por altura.** Numa página de duas colunas com o
  diagrama na da direita, a linha do FEN pode cair no meio da coluna da esquerda.
- **Roque e en passant não estão no diagrama.** O roque sai `-` até alguém marcá-lo na
  conferência; en passant sai sempre `-`.
- **Promover padrões para a base global** do PyBoxEditor é um passo que ainda não existe.
