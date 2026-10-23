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

1. **Novo projeto** (Ctrl+N) liga um PDF ou uma imagem a uma pasta de projeto do livro. Se a
   régua conservadora do `core.pdf_nativo` encontra texto tipográfico confiável no PDF, o
   programa oferece importá-lo: aceitando, cria essas páginas diretamente e não pede OCR ao
   servidor; as páginas recusadas pela régua continuam disponíveis para o F5 ou o lote.
2. **Reconhecer página** (F5) segmenta a página, separa os diagramas do texto, lê cada glifo
   e lê cada diagrama em FEN, que entra no texto reconhecido da página.
3. O **Inspetor**, à direita, mostra o glifo menos confiável, ampliado e na linha em que
   está (o editor Glifo; ver "O espaço de trabalho", abaixo).
   - **Enter** ensina o padrão para este livro. As repetições do mesmo glifo saem da fila na hora.
   - **Shift+Enter** corrige só esta ocorrência, sem gravar padrão.
   - **Del** tira da página um box que não é caractere.
   - **Alt+↓** pula para o próximo da fila; **Alt+↑** volta. Valem com o foco em qualquer
     painel e nunca mudam texto (desde o passo A2; antes eram Tab e Shift+Tab, e o Tab agora
     só anda pelo foco).
   - **Ctrl+D** divide um box que juntou dois glifos, como o "rp" da p. 27 do Darcy Lima:
     no ponto clicado no recorte ampliado ou, sem clique, no vão da tinta. As partes são
     aparadas à própria tinta, relidas, e a primeira aparece para ser ensinada.
   - **Ctrl+J** junta com o box seguinte da linha; **Ctrl+Shift+J**, com o anterior.
   - **Shift+seta** move a borda direita ou a de baixo; **Ctrl+Shift+seta**, a esquerda ou a
     de cima (desde o A2; antes, Alt+seta, que agora é das páginas visitadas). Valem no campo
     do caractere e com o foco na página. O box é relido a cada passo.
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
     um esquecer devolve as amostras. Os ajustes de borda seguidos no mesmo box, e os arrastes
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
     janela, e enquanto isso o Glifo do Inspetor fica desligado (a barra mostra o que está
     rodando); a propagação de um Enter não o desliga. O que você pedir nesse meio-tempo,
     como um F5, um Ctrl+Z ou um "Dividir aqui" no botão direito, não se perde: entra numa
     fila, que a barra mostra ("… Na fila: Desfazendo, Reconhecendo a página"), e roda
     quando chegar a vez. Uma edição pedida numa página e que só ganha a vez depois de você
     ir para outra é descartada, com aviso.
4. Na página seguinte, o livro já lê com os padrões ensinados.
5. A aba **Padrões** da vista direita mostra cada amostra por caractere e permite esquecer as
   erradas (Alt+3 cicla as abas; ver "A revisão (passo C)").
6. **Ctrl+T** marca a página como verificada e abre a próxima não verificada (desde o A2).
   Com glifos ainda a revisar, ele pergunta na barra, acima da faixa Linha: "Aceitar 12
   pendente(s)…? Enter aceita · Esc não marca" (o Esc fecha só a pergunta). Uma edição
   depois a devolve a "em revisão"; o Ctrl+Z desfaz a marca. (Até o A1, o Ctrl+T era o
   modo de treino, que agora é o Ctrl+M.)
7. **Clicar num diagrama** abre a conferência (ver abaixo).

Os boxes na página (desde o passo A1): **o que chama o olho é o que falta revisar.** Cada
estado tem cor e traço próprios, para não depender só da cor (a paleta Okabe-Ito, legível
para quem não distingue vermelho de verde):

- laranja tracejado, com fundo claro: vai para a revisão;
- vermelhão pontilhado, mais grosso, com fundo claro: ninguém leu;
- cinza traço-ponto: aguardando leitura (reconhecido só em parte);
- os aceitos ficam discretos, num cinza fino. **V** liga e desliga "mostrar a origem": roxo é
  o que você confirmou, verde-azulado um padrão do livro, azul a rede ou a base global.

O Glifo do Inspetor tem a legenda, desenhada com o traço de cada estado. Ciano é a seleção do
modo de treino. O tracejado do diagrama: cinza ainda não lido, laranja lido mas a conferir,
azul lido com confiança, roxo conferido por você.

### O espaço de trabalho

Desde o passo A2 a janela é a do FineReader:

- **Imagem e vista direita** dividem o meio, lado a lado (Ctrl+F7) ou empilhadas
  (Ctrl+Shift+F7); **Ctrl+F6** deixa só a Imagem e **Ctrl+F8** só a vista direita. A vista
  direita tem as abas **Documento** (ver abaixo) e
  **Padrões**. Até 1280 px de largura o padrão é o empilhado.
- O **Inspetor** é um editor só, o do item atual: **Glifo** (o treino) ou **Palavra** (a
  verificação de texto). No cabeçalho, a **fila**: o modo (confiança, ordem de leitura,
  por caractere, palavras desconhecidas, diagramas por conferir), o escopo (página ou livro)
  e a posição nela. **F7** passa ao modo seguinte, **Shift+F7** alterna o escopo, e o
  seletor escolhe os dois. O Alt+↓ leva o foco ao campo do Inspetor, de qualquer
  painel. No modo "diagramas por conferir", o Inspetor continua no Glifo (o editor de
  Diagrama é do passo H) e o Alt+↓, que só anda para a frente, abre a conferência do
  próximo. O editor só troca por um clique num item ou pelo modo da
  fila, nunca pelo foco. No campo do caractere, Enter, Shift+Enter, Del e as setas das bordas
  são do Glifo; **F2** abre a paleta de símbolos.
- A gaveta de **Páginas** (**F9**) lista o livro: o número, o estado (um símbolo: · não
  reconhecida, ✎ glifos marcados, ○ reconhecida, ◐ em revisão, ✓ verificada; o nome na dica),
  os glifos a revisar e os diagramas por conferir, em 150 px tirados da vista direita (a
  Imagem fica do tamanho que tinha). Ao fechar, o meio volta aos tamanhos de antes de ela
  abrir (um ajuste do divisor feito com ela aberta não fica). Enter ou duplo clique abre a página; o filtro mostra um estado; com várias
  selecionadas, o menu de contexto as reconhece em lote. Num projeto novo, numa janela de
  1600 px ou mais, ela abre sozinha.
- **Resultados / Avisos**, embaixo, guarda os avisos e os erros do projeto, com a hora, em
  `avisos.log` (nada some com a mensagem de 5 s da barra): as falhas de gravação e de tarefa,
  os avisos e as recusas do desfazer. O **⚠** da barra de status conta os novos e abre o
  painel.
- **Alt+1** a **Alt+5** levam o foco a Páginas, Imagem, vista direita (de novo: a aba
  seguinte), Inspetor e Resultados, abrindo o painel fechado. **Esc** esvazia a seleção e,
  depois, fecha Resultados (o foco volta ao painel de antes). **Shift+F10** e a tecla **Menu** abrem o menu de contexto do
  painel com o foco.
- A barra de status mostra a página e o estado dela, a fila, o zoom e, no lote, o andamento
  e o **✕** que o cancela.
- **O arranjo é do projeto**: ao fechar, ele vai para `janela.json` (gravado inteiro ou não
  gravado, como as páginas) e volta ao reabrir, com as docas, os tamanhos, o zoom, a aba e o
  editor ativos, o painel com o foco e a página aberta.
- **Ajuda › Atalhos do teclado** mostra a tabela de `docs/ATALHOS.md`, gerada de
  `docs/atalhos.yaml`, de onde o programa registra cada atalho.

**O que mudou de tecla no A2**: Tab → Alt+↓ (a fila); Ctrl+T (modo de treino) → **Ctrl+M**
(marcar glifo à mão), e o Ctrl+T passou a "página verificada"; Alt+seta (bordas) →
Shift+seta e Ctrl+Shift+seta; F7 (verificação) → F7 cicla o modo da fila, e a verificação é
o modo "palavras desconhecidas"; Ctrl+I (ignorar a palavra) → Ctrl+Shift+I; Ctrl+Shift+P
(Padrões) → Alt+3.

### O Documento e a Linha

Desde o passo A3 a aba **Documento** mostra a página reconhecida como texto formatado, e não
mais como texto puro:

- **Uma linha impressa por parágrafo**, com as figurinas como impressas (♘). O **cabeçalho e
  o rodapé corridos** (a linha curta na faixa de cima ou de baixo, separada do texto, com o
  número da página: a mesma regra que os tira da exportação) saem em cinza pequeno, e
  **Ctrl+Shift+H** (ou "Cabeçalhos e rodapés", na barra do Documento) os oculta. Os títulos
  em negrito e as notas em corpo menor dependem da função das áreas, que só o layout do
  passo F dá: até lá, o título sai como o corpo. Refluir as linhas em parágrafos também fica
  para o F: sem os parágrafos, o título e o corpo da mesma área se juntariam.
- **Os diagramas no lugar deles**, inteiros: o desenho da posição lida (o recorte da página,
  se ainda não lida), a linha do diagrama em monoespaçado, o estado (conferido, lido e não
  conferido, não lido; o "confiável pelos lances" de §6.1 vem com a validação pelos lances,
  passo H) e **Copiar FEN** (também pelo teclado: Tab até ele e Enter).
- **O realce** ("Realce", na barra do Documento): fundo laranja-claro no que vai para a
  revisão e no que ninguém leu (que aparece como □), ondulado vermelho no que o léxico não
  conhece (depois de a fila de palavras desconhecidas ter rodado na página), pontilhado no
  glifo virtual; o confirmado e o confiável sem realce.
- **Ctrl++ e Ctrl+−** com o foco no Documento mudam o corpo do texto (Ctrl+0 volta ao
  padrão: 10 numa janela de menos de 1600 px, para a linha caber na vista direita, e 11 de
  1600 em diante); com o foco na Imagem, o zoom dela.
- **Dá para editar**, desde o passo D1 (abaixo).

**A sincronia**: o clique numa palavra do Documento a contorna (tracejado azul) na Imagem e
leva o glifo clicado ao Inspetor; o cursor andando pelo Documento (as setas) contorna a
palavra na Imagem, que rola até ela só com Seguir; o clique na Imagem e o Alt+↓ da fila
levam o cursor do Documento ao glifo e o mostram, com o glifo atual da fila em fundo azul-claro (também sem o
foco no Documento). O contorno da palavra em verificação (cheio) é outro e fica. Uma edição
ou a propagação montam o Documento de novo sem perder o lugar: o cursor e a seleção voltam
aos mesmos glifos, e a rolagem fica; quando a fila anda (um Enter, o Alt+↓), o Documento
vai junto até o glifo seguinte. A página não reconhecida diz isso no Documento.

**A Linha** (**Ctrl+F5** a esconde e mostra), embaixo da Imagem e da vista direita: a linha
do glifo atual ampliada, a imagem em cima e o texto lido embaixo, cada caractere sob o glifo
dele, e o glifo atual contornado.

### Editar no Documento (passo D1)

O Documento se edita como um editor de texto, e cada edição vira o que ela é na página:

- **Digite por cima.** Começar a mudar uma palavra abre uma **sessão**, que cobre as palavras
  que você tocou (e cresce se a edição seguinte tocar as vizinhas). Nada muda na página
  enquanto a sessão está aberta. Ela **confirma** quando o cursor sai dela (as setas, um
  clique fora, outro painel), com **Enter** (e o cursor vai à próxima palavra duvidosa),
  **Shift+Enter** (fica ali) ou **Ctrl+Enter** (e ensina o glifo sob o cursor, como o Enter
  do Glifo, no mesmo passo do desfazer; o glifo virtual e a letra que você acabou de digitar
  não ensinam). Confirmar é **um passo** do desfazer, e os glifos da sessão que têm leitura
  ficam **revisados**: saem da fila e dos pendentes do livro (o □ e o aguardando ficam).
- **Esc** (ou Ctrl+Z com a sessão aberta) devolve a palavra ao que era, e **Ctrl+Y** a
  confirma de novo, enquanto o cursor não sai dela. Fora de uma sessão, Ctrl+Z e Ctrl+Y são o
  desfazer do projeto.
- **Enter numa palavra sem mudança** a aceita (como o *Skip* do FineReader): os glifos com
  leitura ficam revisados, sem trocar a fonte da leitura.
- O que cada edição faz: **trocar uma letra** corrige o glifo (fica manual, como o
  Shift+Enter do Glifo); **apagar uma letra** tira o glifo da página (o Ctrl+Z o devolve);
  **digitar uma letra que faltou** cria um **glifo virtual** (sem caixa, pontilhado azul; se
  houver tinta sem box no lugar, a Linha oferece o **Ctrl+M** para marcar o quadro); **um
  espaço** parte a palavra, e **apagar um espaço** junta as duas (na mesma linha impressa),
  também junto de um glifo virtual. O texto da página depois de confirmar é o que você
  digitou: o glifo virtual fica onde você o pôs, mesmo se a letra ao lado dele sair depois.
  Colar (só o texto; o tab vira espaço), arrastar e o IME dão o mesmo resultado que digitar.
  Numa palavra com letras repetidas, sai o glifo da letra que você apagou ("cassa": o
  Backspace no segundo "s" tira o segundo). As edições que mudam a estrutura (glifo tirado,
  glifo virtual) avisam na Linha e na barra de status ("casxa → casa: 1 glifo tirado · Ctrl+Z
  desfaz").
- **Ainda não** (passo G): trocar duas letras por uma ("rn" → "m", que é juntar os glifos) ou
  uma por duas ("m" → "rn", dividir, e também uma letra no meio de uma ligadura como "fi").
  A sessão é recusada, a palavra volta ao que era, e a Linha diz "este tipo de edição chega
  numa próxima versão". Negrito, itálico e sublinhado e o parágrafo novo também são do G.
- **As figurinas** (§6.4): num lance que você digitou, a letra da peça vira figurina ao
  confirmar, quando o livro é de figurinas ("Cf3" → "♘f3" em português; "Nf3" → "♘f3" em
  inglês; "(Cf3)," → "(♘f3),"). O lance que ficou igual e no mesmo lugar não muda. **Opções ›
  Peças nos lances** escolhe figurinas, letras ou, o padrão, **como o livro**: figurinas se o
  livro tem figurinas lidas (em qualquer página lida), letras se não tem (uma figurina lida
  por engano num livro de letras liga o modo: escolha "Letras" nas Opções).
  **Ctrl+Shift+K/Q/R/B/N/P** inserem ♔♕♖♗♘♙ no cursor (o mesmo atalho de novo alterna para a
  preta, ♚♛♜♝♞♟), e **F2** abre a paleta de símbolos no cursor.
- **O diagrama não se apaga**: uma seleção que o cruza apaga o texto e o diagrama fica.

### Localizar (passo B)

**Ctrl+F** abre a barra no topo da vista direita (na aba Documento; a seleção do Documento
vira o texto, e uma seleção longa ou de várias linhas vira o escopo Seleção) e busca enquanto
você digita:

- **Aa** separa maiúsculas e minúsculas; **ab|** acha só a palavra inteira; **.\*** liga a
  expressão regular, com as classes de xadrez **`\L`** (lance: Cf3, exd5, O-O, e8=D+),
  **`\P`** (peça: as figurinas e as letras do idioma do livro), **`\C`** (casa: a1 a h8) e
  **`\V`** (valoração: ± ∓ ⩲ ⩱ +- -+ += =+ = ∞ ! ? !! ?? !? ?! □); a expansão delas aparece na
  dica do campo. As classes valem com qualquer **Aa** (B, o bispo, não é b, a coluna), e
  `^` e `$` valem em cada linha impressa. **♘=C** (figurina = letra) faz "Cf3" achar também
  "♘f3" e "Nf3" (a letra conta como peça quando vem seguida de uma casa).
- **O escopo**: o livro, a página aberta, a seleção do Documento ou um intervalo de páginas
  ("3-10"; um intervalo que não se lê aparece como erro na barra). A seleção fica a de quando
  você escolheu Seleção, mesmo que o cursor ande, e o escopo diz de que página ela é
  ("Seleção (p. 3)"); ela cai ao fechar a barra ou trocar de página, e o Ctrl+F sem seleção
  volta ao escopo de antes. **Onde**: prosa, notação, FEN (o do diagrama lido), legendas (a
  partir do passo H) e cabeçalhos e rodapés.
- **F3** e **Shift+F3** (ou Enter e Shift+Enter na barra) vão à próxima e à anterior, dando a
  volta no livro; a ocorrência atual fica em laranja no Documento e contornada na Imagem, as
  outras da página em amarelo. **Alt+Enter** manda todas para **Resultados** (página, linha e
  o trecho, com o casamento em negrito; Enter ou duplo clique leva até ela), e a gaveta das
  páginas ganha a coluna **Ach.** com a contagem de cada página. F3 com a barra fechada a
  abre e vai à primeira; Enter ou F3 logo depois de digitar esperam a busca nova. Editar a
  página com a barra aberta refaz a contagem (a ocorrência atual continua). **Esc**, com o
  foco na barra, a fecha.
- A regex inválida aparece na barra ("erro", com a mensagem na dica); um padrão lento demais
  (como `(\w+)+$` num texto longo) aborta a busca inteira quando um casamento passa de meio
  segundo, com o aviso. A janela continua respondendo durante a busca (o atraso de um evento
  fica em ~2 ms). Buscar uma regex num livro de 230 páginas leva ~13 ms.
- **Editar › Buscar glifo…**: caractere, fonte (rede, base global, livro, manual, sem
  leitura) e faixa de confiança; os glifos achados abrem na **Galeria** (desde o passo C).
  Ela roda em segundo plano, como a busca.
- **O índice** é montado ao abrir o projeto, em segundo plano, nos processos que o programa
  abre ao começar (6 processos, ~290 MB, fechados quando o índice fica pronto, ou depois de
  5 minutos se nenhum projeto for aberto); não vai para o disco. 230 páginas levam 1,4–1,5 s
  com os processos já abertos (o alvo é 2 s), e 1,7–2,4 s pela janela com o servidor de
  leitura subindo junto. Com os processos por abrir (o projeto aberto logo ao abrir o
  programa, ou o segundo projeto da sessão), 2,0–2,9 s. O que você edita, o F5 e o lote
  refazem as páginas deles antes da busca seguinte, e o livro v1 é lido sem migrar. As
  páginas não reconhecidas ficam fora (a barra de status diz quantas, no escopo do livro).
  O índice de 230 páginas ocupa ~70 MB na memória. Na tabela das medidas, a memória com o
  lote do B (~2.450 MB) inclui o que os testes do índice, que rodam antes no mesmo
  processo, deixaram na interface; o CA-11.1 sozinho dá ~1.680 MB.
- **Os Avisos** que citam uma página (como as decisões que não seguiram os glifos relidos,
  desde o passo E) abrem a página com Enter ou duplo clique, e o glifo do ponto citado.

### Substituir (passo D2)

**Ctrl+H** abre a barra de Localizar com a linha de substituir (Ctrl+F a esconde de novo):

- **Substituir por**: com a regex ligada, `\1` e `\g<nome>` trazem os grupos (um grupo que
  a regex não tem é erro na barra); sem ela, o texto vai como está. **Prosa | Notação |
  Ambos** (o padrão é Prosa, que inclui as legendas e os cabeçalhos): a Prosa nunca toca uma
  palavra de notação, e a Notação nunca toca a prosa; o FEN é pesquisável, mas nunca
  substituído. O filtro **Onde** da busca também vale. Quando nada fica para trocar porque
  as ocorrências estão no outro "onde" ("Cf3" → "Nf3" com Prosa), a barra diz quantas ficaram
  fora e qual escolher.
- **Substituir** (ou Enter no campo) troca a ocorrência atual, se ela está na página aberta,
  e vai à próxima; se ela está noutra página, vai até ela primeiro; as que já estão como o
  substituto ("casa" → "Casa" sem o Aa) são puladas, e no fim a barra diz "Nada mais a
  substituir". **Todas** (ou Ctrl+Enter no campo), no escopo Página ou Seleção, troca direto.
  No Livro ou num intervalo, monta sempre a **prévia** em Resultados, com **todos** os casos:
  um por linha (página, linha, prosa ou notação, as palavras antes → depois), cada um com a
  caixa marcada. Espaço marca ou desmarca os selecionados (Shift e Ctrl+A selecionam vários),
  **Aplicar N** (ou Enter na lista) aplica os marcados, e Shift+Enter ou o duplo clique leva
  ao caso. Uma prévia que fica velha (outra substituição mudou as páginas) sai da tela.
- Cada caso é a menor sequência de palavras que um ou mais casamentos tocam. A troca segue a
  tabela da edição no Documento (§6.3): uma letra trocada fica `manual`, uma letra que sobra
  tira o glifo dela, uma que falta vira glifo virtual; as correções de leitura comuns têm
  tradução ("cassa" → "casa", "ivro" → "livro", "conc1uir" → "concluir", "casas" → "casa").
  Só o que é do passo G fica de fora: duas letras virando uma, ou uma virando duas, no mesmo
  trecho ("rn" → "m", "m" → "rn", e também "casa" → "lar", onde "sa" vira "r"). Esse caso
  aparece na prévia desmarcado e desabilitado, com o trecho e o motivo na dica, e na página
  aberta fica de fora, com o aviso. Substituir não ensina nem marca nada como revisado.
- Tudo o que uma vez Substituir ou Todas trocou, mesmo no livro inteiro, é **um passo** do
  desfazer: um Ctrl+Z volta todas as páginas. Uma página editada entre a prévia e o Aplicar
  recebe a troca na versão de agora, se as palavras de cada caso ainda são as mesmas; senão
  fica de fora, com o motivo nos Avisos.
- A prévia lê só as páginas em que o índice da busca acha o padrão (~40 ms cada). Num livro
  de 230 páginas, trocar "e" por "E" (28.693 casos, todas as páginas) leva ~9 s de prévia, em
  segundo plano, com o progresso na barra de status, mais ~9 s para editar as cópias das
  páginas (também em segundo plano, com o progresso; a fila de comandos espera), e prende a
  janela por ~0,4 s ao trocá-las; o Ctrl+Z leva ~0,5 s. Essa transação ocupa ~43 MB dos 50 MB
  do desfazer: os passos mais antigos que não cabem saem, e a barra de status diz quantos.

### A revisão (passo C)

- **A fila** (o seletor no cabeçalho do Inspetor): os modos confiança, ordem de leitura,
  **por caractere** (os pendentes agrupados pela leitura e, em cada grupo, do menos
  confiável ao mais), palavras desconhecidas e diagramas por conferir. **Shift+F7** passa do
  escopo da página ao do **livro**: o Alt+↓ no último pendente da página abre a próxima
  página com pendentes (e o Alt+↑ no primeiro, a anterior), pelo resumo do `livro.json`, sem
  abrir as páginas; nas palavras, a página seguinte; o contador diz "3/12 · livro 410". A
  fila julga de novo só os glifos que mudaram. O **F6** também conta pelo resumo.
- **A Galeria** (a terceira aba da vista direita; Editar › Galeria do caractere, ou a busca
  por glifo): a grade dos recortes dos glifos lidos como o caractere do glifo atual, da
  página ou do livro, do menos confiável ao mais, com a página e a confiança na dica. As
  setas, Shift e Ctrl+A selecionam; **digitar um caractere** o aplica à seleção, em quantas
  páginas forem, num passo do desfazer (sem ensinar); **Enter** ensina a seleção, uma amostra
  por glifo, com a leitura de cada um; **Shift+Enter** só corrige (a leitura fica, `manual`,
  sem padrão novo). O duplo clique leva ao glifo. Os recortes chegam em segundo plano.
- **A aba Padrões**: o campo acha o caractere; cada amostra diz a página de onde veio,
  quantos glifos do livro ela leu, a altura relativa e o efeito (negrito e itálico, desde o
  passo I); o duplo clique (ou Ir à origem) abre a página no glifo de origem. **Esquecer**
  (o botão, ou Delete) não pergunta: as amostras saem, e os glifos que elas leram, no livro
  inteiro, voltam à fila (a leitura fica, sem a fonte que a dava), pelo índice da busca e em
  segundo plano; uma página verificada atingida volta a "em revisão", com aviso nos Avisos. O
  Ctrl+Z desfaz tudo num passo: as amostras voltam e os glifos saem da fila de novo.
- **Ao ensinar**, embaixo do campo do Glifo: o efeito ("Enter ensina 'l' · 23 iguais nesta
  página", os glifos da página com a mesma leitura dele; no escopo livro, também quantos no
  livro) e, em laranja, o **conflito** quando o glifo está perto de amostras de outro
  caractere ("⚠ este glifo está a 0,04 de 14 amostra(s) de '1'"). A margem fica nas Opções do
  livro ("Avisar conflito a menos de", 0,10 por padrão, na escala da distância do k-NN / 2000).
- **Ctrl+T** com pendentes pergunta na barra, sem diálogo (ver o treino, acima).

### A página: zoom e navegação

Desde o passo A1 o visor desenha os boxes num item só, e só o pedaço da tela que mudou: a
página de 2.000 boxes pinta em ~12 ms em qualquer zoom (o alvo é 33).

- **Zoom** de 5% a 800%: Ctrl+roda ou Ctrl++ e Ctrl+− (no limite, a barra diz "zoom máximo"
  ou "zoom mínimo"); **Ctrl+0** página inteira, **Ctrl+9** largura da página, **Ctrl+8**
  100%, **Ctrl+7** o glifo atual. Valem com o foco na página ou no Glifo do Inspetor; o **V**,
  só com o foco na página (clique na margem dela), porque no campo do caractere ele é uma
  letra. A caixa de zoom da barra aceita o número; o Enter devolve
  o teclado à página. Página inteira e largura continuam valendo ao redimensionar a janela.
- **Rolar**: a roda rola, Shift+roda rola na horizontal; **espaço + arrastar** ou o **botão do
  meio** arrastam a página, sem marcar nada, também no modo de treino.
- **PgDn e PgUp** rolam uma tela; no fim da página, o PgDn abre a seguinte no topo, e no topo
  o PgUp abre a anterior no fim.
- **Alt+Home** e **Alt+End**: primeira e última página. **Ctrl+G**: ir para a página pedida.
  **Alt+←** e **Alt+→** voltam e avançam pelas páginas visitadas, como num navegador.
- **Seguir** (Ctrl+Shift+L, ligado): a página rola para manter o glifo do Inspetor à
  vista, longe da borda. Desligado, a vista fica onde você a deixou. Religá-lo não leva a
  vista ao glifo na hora, só no próximo, e ele volta ligado quando o programa abre.
- **F8**: o próximo diagrama do livro ainda por conferir (na própria página, se houver).
- As páginas vizinhas já ficam prontas: a seguinte é renderizada em segundo plano, e as 5
  últimas vistas ficam na memória, então ir e voltar é imediato.

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

**Clicar no diagrama** (ou **Ferramentas › Próximo diagrama por conferir**, F8, que abre o
próximo por conferir do livro) abre o **editor Diagrama no Inspetor** (passo H; antes era um
diálogo). A Imagem dá zoom no diagrama impresso e continua navegável: zoom, rolagem e o resto
da janela valem enquanto se confere. No Inspetor fica a posição lida, desenhada pela fonte de
diagrama do PyBoxEditor:

- clique seleciona a casa; a letra da peça a põe (maiúscula branca, minúscula preta); Delete,
  Backspace ou espaço a esvaziam; as setas andam pelas casas; o botão direito esvazia;
- com uma peça escolhida na paleta, o clique pinta, e clicar de novo alterna com vazia;
- verde é casa corrigida por você, vermelho trocada pela legalidade, laranja leitura duvidosa;
- o lado a jogar começa sem escolha quando a página não diz; o roque só oferece o que a
  posição comporta; com o foco no editor, Ctrl+Z e Ctrl+Y desfazem e refazem as casas;
- **o roque inferido** (rei e torre nas casas iniciais) aparece com o botão "Usar o
  inferido"; ele não vai ao FEN, nem à exportação, sem você marcar;
- os avisos dizem o que o leitor desconfia (o porteiro do PyBoxEditor), o que a posição tem de
  impossível, que, sem coordenadas impressas, a orientação é suposta, e o que os lances do
  texto dizem (abaixo), refeito a cada casa corrigida;
- **Conferido** (Ctrl+Enter) grava o FEN e passa ao próximo por conferir (o F8). PgUp e PgDn
  andam pelos diagramas do livro: no fim da página, o primeiro da próxima página com
  diagrama. Sair sem conferir não leva nada. Os botões FEN e PGN copiam a posição e o PGN.

**A validação pelos lances** (`abbychess.lances`, passo H). A primeira linha de lances do
texto depois de cada diagrama (até o próximo diagrama ou título, sem legenda nem margens; as
letras do idioma do livro, `Cf3` em português, e as figurinas) é jogada na posição lida. O
lance ilegal ou ambíguo, o `x` que não captura e o `+`/`#` que não dá xeque/mate dão o aviso
("3.Cf3 do texto não é legal aqui") e tiram a confiança da leitura; todos legais dão
**confiável pelos lances**, que não anula a dúvida do porteiro. Quando ninguém disse o lado,
o número do primeiro lance (`10...`) o diz. O PGN por diagrama parte do FEN (`SetUp`) e leva
os lances que passaram.

**A aba Diagramas** (vista direita) mostra os diagramas do livro numa grade: o recorte (das
páginas já abertas), a posição desenhada e o estado, com os filtros por conferir, lidos sem
confiança, confiáveis pelos lances e conferidos. Enter ou duplo clique abre o diagrama no
editor.

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

- **Marcar glifo à mão** (Ctrl+M, desde o A2; antes Ctrl+T): o arraste na página desenha o quadro de um glifo, em vez de
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
- **Padrões do livro** (no menu Exibir; Alt+3 cicla as abas da vista direita) abre a aba das
  amostras.
- **Próximo diagrama por conferir** (F8, desde o passo A1; antes era o Ctrl+G, que agora vai para uma
  página) abre a conferência no próximo diagrama do livro ainda não conferido, a começar
  pela página aberta.
- **Reconhecer o livro** (Ctrl+Shift+F5) lê um intervalo de páginas ("26-27, 30"; vazio é o
  livro inteiro) com os padrões do livro, lê os diagramas em FEN como o F5 e grava cada
  página assim que ela termina. O diagrama já conferido não é relido. **Desde o passo E a
  janela inteira continua valendo durante o lote**: ele lê no servidor de leitura (abaixo) e
  a janela só grava cada página que volta, entre um comando seu e outro. Dá para ensinar,
  corrigir, dividir, desfazer, mudar as opções e apertar F5 noutra página; o F5 passa na
  frente da próxima página do lote, e o padrão ensinado no meio vale nas páginas que o lote
  começar depois. A gaveta de Páginas mostra a barra do andamento, e a barra de status as
  páginas feitas e o tempo estimado. As páginas **verificadas** são sempre puladas. Se o
  intervalo tem páginas já lidas, ele pergunta: Sim as lê de novo, **mantendo as correções
  manuais e os glifos revisados** (como o F5, §4.6), Não as pula. A **página aberta em que
  você mexeu nesta sessão** (algum passo dela no desfazer) não é sobrescrita, nem a que você
  mudar (aberta ou não) enquanto o lote a lê: ficam para "reler depois", e a mensagem do fim
  e os Avisos dizem quais; **Projeto › Retomar o lote** pergunta se as lê também (as
  correções manuais e os revisados ficam; as outras mudanças delas saem). A que você verificar
  (Ctrl+T) enquanto o lote a lê continua verificada. Antes de reler uma página já lida, o lote guarda
  como ela estava em `paginas/.antes-do-lote/`, e **Página › Voltar ao estado antes do lote**
  a devolve (a confirmação diz de quando é a cópia; o que mudou na página depois disso se
  perde e não entra no desfazer). **Cancelar o lote** (o ✕ da barra ou Projeto › Cancelar
  o lote) para a página em leitura no glifo seguinte; ela fica como estava, as já gravadas
  ficam, e **Projeto › Retomar o lote** continua de onde parou, sem ler nenhuma página duas
  vezes. O que falta fica guardado no projeto (`lote.json`, gravado a cada página):
  fechar o programa no meio do lote, ou o servidor parar, não perde o ponto. No fim, a barra
  diz o resumo curto (lidas, a revisar, para reler depois, falhas), e os **Avisos** (⚠)
  guardam o detalhe, página por página.
- **Próxima página com pendentes** (F6, no menu Página) é a fila de revisão do livro todo: mostra o pendente
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
- **Verificação de texto** (a fila "palavras desconhecidas", F7): anda pelas palavras da página que o léxico do core não
  conhece (`core.lexico`), no editor **Palavra** do Inspetor, com o recorte da palavra e os glifos dela
  contornados. O léxico só aponta, nunca troca nada, e não vê notação: `Bxf6` e `exd5` não
  aparecem. **Enter** grava o texto do campo nos glifos, uma letra por glifo, e só os que
  mudaram viram manuais; **Ctrl+Enter** também os ensina como padrões do livro. **Alt+↓** pula,
  **Alt+↑** volta, **Ctrl+Shift+I** ignora a palavra nesta sessão e **Ctrl+Shift+D** a põe no
  dicionário do livro (`lexico.txt` do projeto). Se a palavra tem glifos de mais ou de menos,
  o clique no glifo do recorte o abre no Glifo, para dividir ou juntar. O léxico é
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

### O servidor de leitura (passo E)

**Reconhecer de novo sem perder decisões** (§4.6, também do passo E): o F5 numa página já
lida e o lote com "refazer" mantêm os glifos corrigidos à mão e os revisados; o glifo que a
segmentação devolve com a caixa um pouco diferente (interseção sobre união de ao menos 0,6
com a de antes) continua o mesmo, com as decisões dele (quebras, junções, glifos
virtuais). O que não pôde seguir os glifos relidos vai para os Avisos, com o caractere e
a posição do glifo (em pixels da página; os itens que abrem a página são do passo B).

Os modelos globais do PyBoxEditor (a rede e a base, ~1 GB na memória) ficam num **processo
filho**, aberto com o projeto, e não mais na janela. Ele faz toda leitura que não sai dos
padrões do livro: o F5, o Reler pendentes, o lote, os diagramas, as áreas automáticas e a
leitura de um glifo depois de dividir, juntar, ajustar ou marcar. O que muda para você:

- **O projeto abre na hora.** A barra diz "Carregando os modelos no servidor de leitura…",
  com uma barra ocupada ("Modelos…") até eles ficarem prontos; as páginas já abrem e o Enter
  já ensina. O F5 pedido antes disso espera por eles.
- **Aguardando leitura.** A janela só tem os padrões do livro. O glifo que eles não leem
  (depois de dividir, por exemplo) aparece em cinza, com traço e ponto, "aguardando leitura", e
  recebe a leitura do servidor em seguida, num passo só do desfazer com a edição.
- **Os padrões vão junto.** O que você ensina ou esquece é mandado ao servidor antes do
  pedido seguinte; uma página do lote em andamento passa a usá-lo a partir do glifo
  seguinte.
- **Se o servidor cair**, ele é aberto de novo sozinho e os pedidos em curso são refeitos;
  isso fica nos Avisos (⚠ na barra). Se cair de novo, a janela avisa e oferece reabrir o
  projeto; o lote para, e Retomar o lote continua depois de reabrir. Se ele nunca conseguir
  carregar os modelos (um modelo que falta, o torch quebrado), a janela diz a causa e
  oferece abrir o projeto sem o servidor, com os modelos na própria janela.
- **A memória** é a dos dois processos somados (a medida "Memória com o lote" soma os dois).

`ABBY_SERVIDOR=0` faz a janela ler sem o servidor, com os modelos nela mesma (é o que a
suíte rápida usa); `ABBY_FABRICA_DE_LEITOR=modulo:funcao` troca o leitor do filho (os testes
usam um leitor falso, sem torch).

### A aparência

O programa segue o tema claro ou escuro do sistema e troca na hora quando ele muda. A página,
a faixa Linha e o Documento continuam papel nos dois temas: o livro não inverte. Os estados
dos boxes têm cor e traço próprios, com contraste de pelo menos 3:1 contra o papel; abaixo de
40% de zoom os pendentes aparecem só com o contorno, e o glifo selecionado tem contorno duplo.
Todas as cores estão em `abbychess/app/estilo.py`. As capturas de revisão saem nos dois temas:

```powershell
.venv\Scripts\python.exe ferramentas\capturas.py --livro xv --indice 25 --tema escuro
```

Os ícones da barra e dos menus são do [Lucide](https://lucide.dev) 0.460.0 (licença ISC, em
`abbychess/app/icones/LICENSE`): só os usados moram no pacote, pintados com a cor do texto do
tema e refeitos quando ele muda. Reconhecer e Reler mostram o nome ao lado do ícone; os
outros, o nome e a tecla na dica.

Painel vazio diz o que fazer, com a tecla do perfil em uso: sem livro, a Imagem e o Glifo
dizem como criar ou abrir um projeto; a página não reconhecida diz como reconhecer e como
marcar glifos à mão; os Padrões sem nenhum, como ensinar. Todo botão só com símbolo (◀, ▶,
as peças da paleta, os botões internos das docas) tem nome para o leitor de tela e dica.

### O teclado: perfil e trocas

**Ferramentas › Teclado…** escolhe o perfil e troca as teclas, sem reiniciar:

- **Padrão**, o do AbbyChessCraft (as teclas deste README);
- **FineReader**, as teclas do ABBYY FineReader para quem vem dele: Ctrl+F9 reconhece a
  página, F5 mostra Páginas, F6/F7/Shift+F7/F8 escolhem o arranjo, Alt+4 vai à Linha (e o
  Inspetor e Resultados passam a Alt+5 e Alt+6), Ctrl+Tab e Ctrl+Shift+Tab andam pelos
  painéis, Ctrl+F7 escolhe a fila de palavras, Ctrl+1 a Ctrl+5 dão o tipo da área
  selecionada no editor de áreas (texto, diagrama, tabela, imagem, ignorar).

Na tabela, as teclas de cada ação se editam como texto (`Ctrl+Y; Ctrl+Shift+Z`, separadas
por ponto e vírgula; vazio tira a tecla). Ao aceitar, as trocas passam pelas mesmas regras de `docs/atalhos.yaml`: tecla
repetida no mesmo contexto, letra sem modificador onde se digita, Ctrl+Alt (o AltGr dos
teclados ABNT) e tecla que encobre uma ligação do campo são recusadas, com o motivo. O perfil
e as trocas ficam lembrados; trocar de perfil desfaz as trocas. As dicas e os avisos que
citam uma tecla citam a do perfil em uso.

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
**Desde o passo J a exportação lê a estrutura do Documento** (`exportar.Estrutura`): a área
de título sai como título de capítulo (`<h1>` no EPUB, Heading 1 no DOCX, e entra no
sumário); as áreas de cabeçalho, rodapé e número de página saem (a regra acima continua
valendo, mas não tira o que você marcou como área de texto) e a de ignorar sai sempre; o negrito e o itálico do glifo,
o parágrafo pedido (Ctrl+Shift+Enter) e o hífen de quebra decidido no Documento valem no
arquivo. **Projeto › Exportar** também escreve:

- **TXT**: um parágrafo por bloco, com linha em branco entre eles, e cada diagrama numa linha
  com o FEN e o lado a jogar (ou o motivo do recorte);
- **PGN**: uma partida por diagrama conferido ou confiável pelos lances, partindo da posição
  (`SetUp`/`FEN`) com os lances do texto que passaram na validação, os NAGs e as etiquetas
  `Page` e `Diagram`. Os diagramas que ficaram de fora vão ao relatório, com o motivo.

**O EPUB tem escritor próprio** (`abbychess/epub.py`, passo J): um arquivo por capítulo
(não por página), com a página impressa como âncora; o sumário pelos títulos, em dois
níveis; a lista de páginas e os marcos (capa, sumário, começo do texto); as mensagens no
idioma do livro ("Contents" num livro inglês); a acessibilidade declarada pelo que o
arquivo de fato tem; e imagens repetidas guardadas uma vez só.

**Depois de escolher o arquivo, o diálogo da exportação** pergunta as opções (manter
cabeçalhos e rodapés, só as páginas verificadas, diagramas redesenhados ou recortados, as
marcas de página do TXT; cada uma só vale no formato que a usa, e a escolha é lembrada) e,
no EPUB e no DOCX, os metadados do livro: título, autores e assuntos (separados por `;`),
editora, data (AAAA, AAAA-MM ou AAAA-MM-DD), direitos, identificador, edição impressa e a
capa, que é copiada para a pasta do projeto. O formulário fica em `metadados.json` na pasta
do projeto e volta preenchido na próxima exportação; num projeto só de leitura ele vale só
naquela exportação. **Pré-visualizar…** mostra, sem gravar nada, o que a exportação
escreveria com as opções do diálogo: o relatório inteiro e as primeiras 30 páginas, com o
mesmo texto por parágrafo do arquivo e os diagramas com o texto alternativo (o PGN aparece
como texto; o PDF não tem prévia). O arquivo também pode ser escrito à mão:

```json
{"autores": ["Jacob Aagaard"], "editora": "Quality Chess", "data": "2012",
 "assuntos": ["Xadrez", "Finais"], "direitos": "© 2012", "capa": "capa.jpg"}
```

O **número impresso** de cada página é tirado das margens (o deslocamento entre o número
do cabeçalho ou rodapé e a posição no PDF, quando ao menos duas páginas concordam): no EPUB
ele é o rótulo da lista de páginas e o alvo dos links ("ver a página 23", "on page 23"
viram link quando a página está no livro exportado); no **PDF pesquisável** ele vira o rótulo
de cada página, e os títulos do Documento viram os **marcadores** (o sumário e os rótulos que o
PDF original já trazia ficam).

Depois de gravar, o arquivo é relido e conferido (pacote, manifesto, XML e cada link); com
`ABBY_EPUBCHECK` apontando o `epubcheck.jar`, `epub.epubcheck` roda o EPUBCheck também. O EPUBCheck 5.4.0
aprova o EPUB da fatia do Xadrez Vitorioso sem erro nem advertência; para rodá-lo nos testes:

```powershell
$env:ABBY_EPUBCHECK = "C:\tools\epubcheck-5.4.0\epubcheck.jar"
$env:ABBY_ACE = "C:\tools\ace-1.4.6\node_modules\.bin\ace.cmd"
.venv\Scripts\python.exe -m pytest -q tests/test_epub.py
```

A **acessibilidade** é conferida pelo Ace by DAISY 1.4.6 (`epub.ace`, com `ABBY_ACE`): o EPUB
da fatia e os sintéticos passam sem violação. O OPF declara o idioma também no `<package>` e a
edição impressa de onde vêm as páginas (`dc:source` refinado como `source-of pagination`).
Os campos de certificação (`a11y:certifiedBy`, `dcterms:conformsTo`) ficam de fora de
propósito: ninguém certificou o livro.

Depois de cada exportação, o **relatório** vai a Resultados / Avisos: páginas, títulos,
margens tiradas, diagramas recortados e o motivo, páginas não verificadas, glifos pendentes
e os diagramas fora do PGN, cada item com a página.

- **DOCX**: desde o passo J pelo escritor próprio (`abbychess/escritor_docx.py`): títulos nos
  estilos de título do Word, negrito e itálico, os diagramas com o FEN no texto alternativo,
  um marcador por página impressa e hiperlink nas referências `página N`, os metadados nas
  propriedades e os mesmos bytes com o mesmo `SOURCE_DATE_EPOCH`. (Até o passo J, DOCX e EPUB
  saíam pelos escritores do PyBoxEditor, `core.exportar`, com a fonte dos
  símbolos embutida. Os parágrafos saem do vão entre as linhas, a hifenização no fim de linha
  é desfeita e as figurinas saem como impressas.) O idioma do arquivo é o do texto do livro
  (o que a camada do PDF diz, ou o do projeto).

**O PDF nascido digital sai da própria camada de texto.** No DOCX e no EPUB, a página cuja
camada a régua do `core.pdf_nativo` aceita (texto tipográfico, não OCR de fábrica nem figurina
em imagem) sai dela, e não dos boxes: as letras e figurinas que o autor escreveu (inclusive a
codificação "SP" do ChessBase das edições da Quality Chess), o negrito da linha principal, as
colunas na ordem, o cabeçalho corrente fora e o FEN exato dos diagramas compostos em fonte. O
lado a jogar que a revisão conferiu num diagrama do projeto passa para o diagrama da camada. As
outras páginas saem dos boxes, como antes. Nas pp. 1 e 6–8 do *Odds & Ends* (Quality Chess,
2012), as quatro páginas vieram da camada, sem um erro de letra, contra uns 90 `O` no lugar de
`o`, colunas embaralhadas e o `13.♕b3 0–0–0` cortado como rodapé na exportação pelos boxes.

**Pelos boxes**, a exportação também:

- monta as linhas **coluna a coluna** (`exportar._Leitura`): o que atravessa a calha (o título
  centrado) é uma faixa sozinha, e as figuras entram no trecho da coluna delas;
- acerta a **caixa** das letras que só mudam de tamanho (`o O`, `c C`, `s S`, `v V`, `w W`,
  `x X`, `z Z`) pela altura na linha, e o `X` de captura (`♖Xf2` → `♖xf2`);
- tira do texto as **coordenadas** do tabuleiro (o número sozinho à esquerda, a letra sozinha
  embaixo), e só elas: a legenda colada embaixo fica;
- não trata como rodapé a linha que tem **lances**.

Nos dois caminhos, o diagrama sem lado lido ganha o do **último lance antes dele**, quando a peça
que o fez está na casa de chegada e o texto depois do diagrama continua a numeração
(`10.♘xc4` → `10...`); e o parágrafo que a paginação partiu volta a ser um.

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

### As páginas do livro: mover, apagar, inserir, girar, cortar, dividir (passo L)

O menu **Página** tem **Mover páginas…**, **Apagar páginas…**, **Inserir páginas…**,
**Páginas apagadas…**, **Girar à direita** e **Girar à esquerda** (um gesto, sem diálogo),
**Girar páginas…**, **Cortar páginas…**, **Tirar o corte…**, **Dividir páginas…** e
**Endireitar páginas…**. O menu de contexto da gaveta de Páginas faz o mesmo com as linhas
selecionadas, e o menu Página vale para elas quando há mais de uma escolhida (senão, para a
página aberta). Nos diálogos, as páginas se escolhem como texto, com o número de agora no
livro: `3-7, 12`, `ímpares`, `pares`, `todas` ou uma paridade num intervalo (`ímpares
15-200`, `pares de 3 a 9`); o diálogo diz quantas o texto escolhe, ou o que está errado nele.

- **Mover** tira as páginas de onde estão e as põe, na mesma ordem, depois da página
  escolhida (0: o começo do livro).
- **Apagar** tira as páginas do livro, da busca, da fila e das exportações, mas o projeto as
  guarda com os glifos, as correções e os padrões ensinados nelas: **Páginas apagadas…** as
  devolve ao lugar de onde saíram (todas juntas, ou da apagada mais recente para a mais
  antiga, voltam à ordem exata).
- **Inserir** põe no livro as páginas de um PDF ou de imagens, copiadas para a pasta
  `inseridas/` do projeto (o arquivo de fora pode sumir depois). PDF com senha é recusado.
  As inseridas são lidas, ensinadas e exportadas como as outras; no PDF pesquisável, a
  página inserida, cortada ou girada sai com a imagem que se vê no programa.
- **Girar** gira de 90 em 90 graus; **cortar** tira margens (em porcentagem do que se vê:
  confira na página depois, o corte ainda é por números). Os glifos, as áreas e os diagramas
  lidos vão junto, nos mesmos pixels; o que o corte deixa de fora fica guardado e volta com o
  Ctrl+Z ou com **Tirar o corte…**. A página lida girada mantém a leitura da posição de antes
  (a barra avisa): o F5 lê de novo.
- **Endireitar** gira a página por um ângulo à mão (até 20°, positivo no sentido
  anti-horário), no lugar do medido. O diálogo começa no ângulo medido de cada página (dar
  OK sem mexer não muda nada) e diz quantas das escolhidas perdem a leitura: ficam os glifos
  de leitura digitada ou aceitos na revisão, girados com a página, e as áreas desenhadas; o
  F5 lê o resto de novo.
- **Dividir** separa a página espelhada (duas páginas do livro numa imagem) em duas: a
  metade esquerda fica no lugar, a direita entra logo depois, cada uma com os glifos dela.
  As amostras ensinadas antes continuam achando o glifo de origem. Uma metade não se divide
  de novo (na seleção, ela é pulada, e a barra avisa); o Ctrl+Z junta as duas. Divida o
  livro espelhado antes de ler: é instantâneo (nada a gravar). O livro já lido leva uns
  segundos, com o cursor de espera, porque as duas metades de cada página são gravadas
  (os números estão em "As medidas do roadmap", linhas "Dividir o livro").

Cada operação é um passo do **Ctrl+Z**. Elas ficam desligadas, com o motivo na dica, no
projeto só para leitura, com o lote rodando, com uma tarefa em curso ou com o servidor lendo
glifos da página. A página de cada
glifo tem um número que não muda (o `pid`): a página aberta, a busca, o lote a retomar e a
origem das amostras seguem a página para onde ela for. O `projeto.json` guarda a ordem do
livro desde o formato 3 (§12.4): o projeto antigo passa a ele na primeira abertura com o PDF
no lugar, e os arquivos de antes ficam em `backup-v2/`.

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
  novo. Fechar com o lote rodando cancela o lote: a página em leitura para no glifo
  seguinte e fica como estava, e o servidor de leitura fecha em até 5 s.

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
- **O texto da página** (o Documento, a busca e as exportações de hoje) sai de um
  documento montado das páginas (`abbychess.texto.montar`), com as decisões que você toma
  editando no Documento desde o passo D1 (espaço a mais ou a menos, o caractere que falta;
  o parágrafo é do passo G). Sem edições, ele sai igual ao de antes, conferido pelos testes
  de caracterização.

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

| Meta | linha de base | 1a (`2026-10-16-passo-1a.json`) | 1b (`2026-10-16-passo-1b.json`) | 2a (`2026-10-16-passo-2a.json`) | 2b (`2026-10-16-passo-2b.json`) | a1 (`2026-10-16-passo-a1.json`) | a2 (`2026-10-16-passo-a2.json`) | a3 (`2026-10-17-passo-a3.json`) | e (`2026-10-17-passo-e.json`) | d1 (`2026-10-17-passo-d1-094555.json`) | b (`2026-10-17-passo-b.json`) | d2 (`2026-10-17-passo-d2.json`) | l (`2026-10-23-passo-l.json`) | pendencias (`2026-10-23-passo-pendencias.json`) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Troca de página, p95 | 194,22 | 190,06 | 186,8 | 190,79 | 161,89 | 15,21 | 16,04 | 14,5 | 16,74 | 17,44 | 18,97 | 18,6 | 18,82 | 19,7 |
| Troca fora do cache, p95 | — | — | — | — | — | 147,1 | 144,68 | 145,27 | 146,97 | 147,86 | 150,02 | 153,78 | 135,34 | 138,58 |
| Enter, p95 | 110,88 | 119,73 | 138,17 | 89,43 | 23,68 | 26,63 | 26,8 | 22,41 | 26,12 | 29,66 | 27,35 | 32,23 | 54,04 | 41,97 |
| Releitura, p95 | 145,73 | 122,08 | 166,34 | 85,98 | 16,92 | 20,23 | 20,88 | 20,15 | 44,48 | 45,03 | 46,99 | 51,44 | 57,97 | 55,01 |
| Desfazer (MB) | 4182,9 | 4182,9 | 4120,9 | 164 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8,6 | 8,6 |
| Atraso no lote, p99 | 8,5 | 8,6 | 15,1 | 13,1 | 12,9 | 22 | 12 | 9,5 | 2,2 | 2,3 | 2,4 | 2,5 | 2,2 | 2,2 |
| Memória com o lote (MB) | 1620 | 1661 | 1676 | 1653 | 1654 | 1793 | 1799 | 1823 | 2050 | 2053 | 2459 | 2468 | 2752 | 1994 |
| Releitura com o lote, p95 | — | — | — | — | — | — | — | — | 124,11 | 113,34 | 92,99 | 111,17 | 169,14 | 206,09 |
| Atraso no lote falso (51 p.), p99 | — | — | — | — | — | — | — | — | 14,1 | 2,8 | 4,1 | 4,6 | 2,1 | 2,5 |
| Gravar uma página do lote, p95 | — | — | — | — | — | — | — | — | 17,6 | 19,2 | 19,7 | 22 | 32 | 36,7 |
| Lote com servidor (s/p.) | — | — | — | — | — | — | — | — | 8,33 | 8,34 | 8,5 | 8,71 | 17,2 | 8,5 |
| Lote sem servidor (s/p.) | — | — | — | — | — | — | — | — | 8,26 | 8,52 | 8,48 | 8,71 | 17,4 | 8,52 |
| Pintura de 2.000 boxes, p95 | — | — | — | — | — | 11,5 | 13,14 | 13,2 | 13,12 | 13,27 | 13,2 | 13,46 | 12 | 10,03 |
| Montar o Documento, p95 | — | — | — | — | 25,61 | 22,72 | 25,97 | 31,78 | 39,82 | 34,81 | 35,42 | 34,88 | 41,17 | 45,92 |
| Clique no Documento, p95 | — | — | — | — | — | — | — | 2,84 | 3,25 | 3,46 | 3,26 | 3,43 | 11,33 | 4,4 |
| Clique acha o box, p95 | — | — | — | — | — | 0,0016 | 0,0016 | 0,0016 | 0,0017 | 0,0017 | 0,0017 | 0,0017 | 0,0016 | 0,002 |
| Montar o índice da busca (230 p.), p95 | — | — | — | — | — | — | — | — | — | — | 1395,66 | 1430,76 | 1422,75 | 1502,46 |
| Buscar regex no livro (230 p.), p95 | — | — | — | — | — | — | — | — | — | — | 17,25 | 15,07 | 13,51 | 13,47 |
| Atraso durante a busca, p99 | — | — | — | — | — | — | — | — | — | — | 2 | 1,8 | 1,6 | 2,3 |
| Atraso durante o aborto, p99 | — | — | — | — | — | — | — | — | — | — | 2 | 1,2 | 1,5 | 1,5 |
| Índice pela janela (230 p.), máx. | — | — | — | — | — | — | — | — | — | — | 2217 | 2257 | 2379 | 2504 |
| Substituir no livro: a janela presa (230 p.) | — | — | — | — | — | — | — | — | — | — | — | 371 | 355 | 360 |
| Substituir no livro: o Ctrl+Z (230 p.) | — | — | — | — | — | — | — | — | — | — | — | 563 | 527 | 526 |
| Substituir no livro: o desfazer (MB) | — | — | — | — | — | — | — | — | — | — | — | 43,4 | 44 | 44 |
| Abrir ao painel de Páginas (230 p.), p95 | — | — | — | — | — | — | — | — | — | — | — | — | 54,8 | 56,1 |
| Dividir o livro lido (230 p.) | — | — | — | — | — | — | — | — | — | — | — | — | 7741 | 7840 |
| Dividir o livro: o Ctrl+Z (230 p.) | — | — | — | — | — | — | — | — | — | — | — | — | 2347 | 2615 |
| Dividir o livro antes de ler (231 p.) | — | — | — | — | — | — | — | — | — | — | — | — | 129 | 130 |
| Girar o livro lido (230 p.) | — | — | — | — | — | — | — | — | — | — | — | — | 342 | 662 |
| Girar uma página, p95 | — | — | — | — | — | — | — | — | — | — | — | — | 16,43 | 15,26 |

Rodadas repetidas, em ms (cada valor é uma rodada, na ordem em que rodou). Sem o congelamento dos modelos para a coleta de lixo (até o 1a, e no 1b com `ABBY_SEM_CONGELAR=1`), o p95 do Enter do passo 0 ao 1b tem duas faixas no mesmo código (perto de 110–130 e de 180–235; no 2a, uma só, perto de 90); o atraso no lote tem duas faixas sempre (perto de 8–10 e de 21). Desde o 2b o congelamento é desligado (`ABBY_CONGELAR=1` liga): as duas linhas do 2b rodam o mesmo programa (o rótulo `sem_congelar` é do roteiro de medida), e a coluna do Enter mede até a cor mudar (até o 2a, até o fim da propagação). Desde o A1 a troca é no cache de páginas (a vizinha já pré-carregada); a de fora do cache tem coluna própria. Compare pela mediana (p50), que varia bem menos (mas uma rodada solta pode sair alta):

| Código | Commit | Rodada | Troca, p50 | Troca, p95 | Fora do cache, p50 | Enter, p50 | Enter, p95 | Releitura, p50 | Releitura, p95 | Atraso no lote, p99 | Releitura com o lote, p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| passo 0 | 25e81b1 | completa | 169,76; 174,14; 171,68 | 192,19; 190,98; 192,11 | — | 104,33; 104,61; 104,66 | 177,63; 179,72; 179,81 | 107,34; 107,54; 105,85 | 124,76; 129,43; 142,69 | 21,4; 8,7; 8,3 | — |
| passo 0 | 25e81b1 | só do lote, sem os padrões | — | — | — | — | — | — | — | 19,9; 7,7; 7,1 | — |
| passo 1a | 315db35 | completa | 180,73; 183,85; 180,22 | 195,04; 198,16; 196,84 | — | 149,4; 114,34; 113,81 | 191,17; 190,97; 190,82 | 133,34; 111,81; 111,19 | 165,4; 150,71; 141,33 | 20,8; 21,3; 8,7 | — |
| passo 1a | 3bf1ad3 | só do lote, sem os padrões | — | — | — | — | — | — | — | 7,5; 20,5; 7,7 | — |
| passo 1b | 1519d8f | completa | 170,01; 166,11; 167,1 | 184,66; 192,26; 182,72 | — | 125,37; 140,8; 125,31 | 149,77; 149,56; 139,9 | 131,89; 139,62; 131,52 | 154,31; 159,37; 158,59 | 17,7; 15; 16,6 | — |
| passo 2a | d19c858 | completa | 162,65; 167,54; 171,97 | 180,58; 191,56; 190,65 | — | 91,38; 82,94; 83,67 | 95,14; 115,58; 90,57 | 74,82; 74,92; 74,59 | 85,61; 90,63; 106,11 | 10,2; 10,1; 21,6 | — |
| passo 2b | 6f863c3 | completa | 157,59; 153,58; 153,66 | 189,56; 171,05; 174,1 | — | 20,85; 21,1; 20,62 | 25,5; 26,13; 25,7 | 13,33; 13,59; 15,26 | 15,65; 16,1; 19,15 | 20,2; 22; 21,8 | — |
| passo a1 | 538adae | completa | 14,06; 14,02; 14,12 | 14,65; 14,28; 14,52 | 132,15; 130,39; 132,9 | 20,63; 20,62; 20,82 | 25,86; 22,97; 25,86 | 14,63; 14,5; 14,76 | 21,54; 17,03; 19,82 | 10,4; 22; 22 | — |
| passo a2 | 93c94a7 | completa | 14,17; 14,23; 14,32 | 15,4; 14,95; 14,81 | 129,93; 135,18; 133,2 | 21,26; 20,83; 21,43 | 27,75; 26,56; 24,42 | 14,93; 14,74; 15,49 | 19,82; 20,77; 19,94 | 9,5; 9,5; 22,2 | — |
| passo a3 | 271d582 | completa | 14,27; 14,12; 14,09 | 14,63; 15,36; 14,46 | 128,43; 129,36; 128,24 | 29,97; 21,33; 21,24 | 37,04; 22,94; 22,86 | 14,09; 14,6; 14,42 | 17,25; 19,34; 19,16 | 21; 9,4; 9,7 | — |
| passo e | 9c759e2 | completa | 14,51; 14,42; 14,56 | 19,08; 17,73; 19,45 | 134,01; 134,1; 133,4 | 23,93; 23,92; 23,99 | 25,85; 28,95; 29,18 | 38,97; 38,73; 38,97 | 43,78; 42,3; 45,41 | 2,2; 2,2; 2,2 | 105,28; 64,42; 65,99 |
| passo d1 | c955dff | completa | 15,21; 14,99; 14,91 | 19,92; 19,05; 17,88 | 133,54; 133,05; 134,86 | 24,63; 33,33; 24,89 | 30,22; 36,06; 27,03 | 35,51; 38,84; 38,67 | 41,52; 44,55; 43,99 | 2,2; 2,2; 2,2 | 117,22; 66,18; 73,22 |
| passo b | c96247f | completa | 15,45; 14,97; 15,41 | 17,5; 16,58; 19,28 | 135,29; 135,04; 140,82 | 24,38; 23,83; 24,2 | 26,23; 30,84; 32,35 | 40,98; 39,41; 42,02 | 46,51; 46,05; 73,56 | 3,1; 2,5; 2,5 | 81,96; 73,53; 92,71 |
| passo d2 | 6a6564a | completa | 15,57; 15,15; 15,66 | 17,16; 18,68; 16,91 | 140,63; 138,89; 146,39 | 35,22; 45,13; 46,88 | 42,51; 67,24; 61,19 | 42,17; 42,59; 46,02 | 50,27; 48,95; 54,52 | 2,6; 2,6; 2,6 | 83,66; 70,76; 82,4 |
| passo l | 071b8e5 | completa | 15,05; 15,38; 15,41 | 17,11; 17,59; 19,09 | 120,43; 122,55; 122,53 | 44,9; 44,96; 45,28 | 55,17; 50,53; 54,75 | 47,24; 52,97; 53,77 | 59,72; 61,82; 65,63 | 2,2; 2,2; 2,2 | 105,91; 162,73; 162,06 |
| passo 1b sem congelar | 1519d8f | completa | 169,84; 175,66; 170,16 | 192,25; 202,72; 196,29 | — | 123,14; 126,27; 144,94 | 199,91; 203,93; 234,95 | 124,11; 123,85; 140,89 | 142,6; 150,72; 233,54 | 14,4; 15,5; 16,3 | — |
| passo 2a sem congelar | d19c858 | completa | 174,66; 175,73; 178,05 | 188,01; 188,63; 188,4 | — | 82,23; 82,43; 82,52 | 91,7; 89,92; 92,03 | 73,15; 70,64; 75,29 | 88,33; 91,91; 92,78 | 11,7; 20,8; 21,5 | — |
| passo 2b sem congelar | 6f863c3 | completa | 153,56; 153,19; 157,37 | 173,65; 165,46; 168,14 | — | 20,55; 20,57; 21,47 | 24,01; 27,01; 27,08 | 14,4; 13,82; 14,5 | 16,9; 16,99; 18,83 | 22,3; 9,1; 9,8 | — |

Qualidade contra os gabaritos (`ferramentas\medir.py`). **Margens corridas**: cabeçalho, número de página e rodapé tirados do texto. **Sem par**: linhas lidas que não casam com nenhuma linha do gabarito (inventadas); as das páginas negativas (capa, sumário) vão à parte. **Perdidas**: linhas do gabarito que a leitura não achou. **Casas** e **lado** só contam nos diagramas que você conferiu; o provisório, entre parênteses, é contra o FEN rotulado pelo assistente (casa a casa, contra o recorte), ainda não conferido por você, e a coluna **FEN = leitura** diz em quantos ele é igual ao que o programa leu. **Ordem**: pares de linhas casadas fora da ordem de leitura do gabarito (não vê onde o diagrama cai no texto). "—" é nada a medir.

| Livro | Commit | Páginas | Margens corridas P / R | Diagramas achados (falsos) | Sem par | Sem par nas negativas | Perdidas | FEN = leitura | Casas erradas por diagrama | Lado certo | Ordem | CER do corpo | Estado |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| xv | 0888053 | 9 | 0,5 / 1 | 7/7 (1) | 6 | 938 (2 pág.) | 3 (+9 nas negativas) | 7/7 | pendente (provisório: 0) | pendente (provisório: 2/5) | 0 | pendente | provisória: estrutura revisada em 0/9 páginas; FEN conferido em 0/7 diagramas; texto verificado em 0/241 linhas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual |
| yusupov | 071b8e5 | 3 | 1 / 0,75 | 3/3 (0) | 8 | — | 5 | 3/3 | pendente (provisório: 0) | pendente (provisório: 1/3) | 0 | pendente | provisória: estrutura revisada em 0/3 páginas; FEN conferido em 0/3 diagramas; texto verificado em 0/157 linhas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual |
| darcy | 071b8e5 | 2 | — / 0 | 3/3 (0) | 1 | — | 0 | 2/3 | pendente (provisório: 3) | pendente (provisório: 0/1) | 0 | pendente | provisória: estrutura revisada em 0/2 páginas; FEN conferido em 0/3 diagramas; texto verificado em 0/97 linhas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual |

Ainda não medido: a ligação da legenda ao diagrama, no passo H (a leitura de hoje não liga legenda a diagrama); precisão e revocação por função de bloco, no passo F (a leitura de hoje não classifica blocos).

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
| xv | 4e974a5 | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 445,5 s |
| xv | 1da748e | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 452,6 s |
| xv | 93c94a7 | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 454,6 s |
| xv | f058c02 | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 444,2 s |
| xv | 34001f8 | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 435,3 s |
| xv | 271d582 | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 434,3 s |
| xv | 5ba8ba0 | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 433,6 s |
| xv | 9c759e2 | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 434,5 s |
| xv | dd38d99 | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 440,9 s |
| xv | c955dff | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 446,5 s |
| xv | c96247f | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 447,8 s |
| xv | 6a6564a | 0,875 / 1 | 7/7 (1) | 6 | 3 | 0 | 1/5 | 458,1 s |
| xv | 071b8e5 | 0,5 / 1 | 7/7 (1) | 6 | 3 | 0 | 2/5 | 508,9 s |
| xv | 0888053 | 0,5 / 1 | 7/7 (1) | 6 | 3 | 0 | 2/5 | 440,5 s |
| yusupov | bb0b7e5 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23 s |
| yusupov | 0ebbf9c | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23,1 s |
| yusupov | 3bf1ad3 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23,4 s |
| yusupov | bab6a1a | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23,4 s |
| yusupov | 5f969c7 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23,3 s |
| yusupov | d19c858 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 24,4 s |
| yusupov | b5c5142 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23,8 s |
| yusupov | 6f863c3 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 25,8 s |
| yusupov | 4e974a5 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 24,1 s |
| yusupov | 1da748e | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23,9 s |
| yusupov | 93c94a7 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 24,3 s |
| yusupov | f058c02 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23,7 s |
| yusupov | 34001f8 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23,2 s |
| yusupov | 271d582 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23,4 s |
| yusupov | 5ba8ba0 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23 s |
| yusupov | 9c759e2 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23,1 s |
| yusupov | dd38d99 | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 22,9 s |
| yusupov | c955dff | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 22,9 s |
| yusupov | c96247f | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 23,8 s |
| yusupov | 6a6564a | 1 / 0,75 | 3/3 (0) | 8 | 13 | 0 | 0/3 | 24,6 s |
| yusupov | 071b8e5 | 1 / 0,75 | 3/3 (0) | 8 | 5 | 0 | 1/3 | 35,8 s |
| darcy | bb0b7e5 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 23,5 s |
| darcy | 0ebbf9c | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 23,7 s |
| darcy | 3bf1ad3 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 23,8 s |
| darcy | bab6a1a | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 23,8 s |
| darcy | 5f969c7 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 23,7 s |
| darcy | d19c858 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 25,5 s |
| darcy | b5c5142 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 24,3 s |
| darcy | 6f863c3 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 25,4 s |
| darcy | 4e974a5 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 24,2 s |
| darcy | 1da748e | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 25 s |
| darcy | 93c94a7 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 25,9 s |
| darcy | f058c02 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 24,2 s |
| darcy | 34001f8 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 23,8 s |
| darcy | 271d582 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 23,9 s |
| darcy | 5ba8ba0 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 23,6 s |
| darcy | 9c759e2 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 24 s |
| darcy | dd38d99 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 24,5 s |
| darcy | c955dff | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 24,4 s |
| darcy | c96247f | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 24,5 s |
| darcy | 6a6564a | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 25,5 s |
| darcy | 071b8e5 | — / 0 | 3/3 (0) | 1 | 0 | 3 | 0/1 | 49,4 s |

Fatia (`ferramentas\replay_fatia.py`; **erros** são as diferenças do snapshot contra o gabarito, o N da medida humana):

| Livro | Passo | Páginas | Total | Gestos dos diagramas | Navegação | Erros | Estado | JSON |
|---|---|---|---|---|---|---|---|---|
| xv | 0 | i020, i021, i022, i023, i024, i025, i026 | gestos pendentes | 14 | 6 | 4 (diagramas; texto pendente) | pendente: nenhuma linha com texto verificado; estrutura revisada em 0/7 páginas; FEN conferido em 0/7 diagramas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual | `2026-10-17-fatia-xv-passo-0.json` |
| xv | 1a | i020, i021, i022, i023, i024, i025, i026 | gestos pendentes | 14 | 6 | 4 (diagramas; texto pendente) | pendente: nenhuma linha com texto verificado; estrutura revisada em 0/7 páginas; FEN conferido em 0/7 diagramas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual | `2026-10-16-fatia-xv-passo-1a.json` |
| xv | 1b | i020, i021, i022, i023, i024, i025, i026 | gestos pendentes | 14 | 6 | 4 (diagramas; texto pendente) | pendente: nenhuma linha com texto verificado; estrutura revisada em 0/7 páginas; FEN conferido em 0/7 diagramas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual | `2026-10-16-fatia-xv-passo-1b.json` |
| xv | 2a | i020, i021, i022, i023, i024, i025, i026 | gestos pendentes | 14 | 6 | 4 (diagramas; texto pendente) | pendente: nenhuma linha com texto verificado; estrutura revisada em 0/7 páginas; FEN conferido em 0/7 diagramas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual | `2026-10-16-fatia-xv-passo-2a.json` |
| xv | 2b | i020, i021, i022, i023, i024, i025, i026 | gestos pendentes | 14 | 6 | 4 (diagramas; texto pendente) | pendente: nenhuma linha com texto verificado; estrutura revisada em 0/7 páginas; FEN conferido em 0/7 diagramas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual | `2026-10-16-fatia-xv-passo-2b.json` |
| xv | A1 | i020, i021, i022, i023, i024, i025, i026 | gestos pendentes | 14 | 6 | 4 (diagramas; texto pendente) | pendente: nenhuma linha com texto verificado; estrutura revisada em 0/7 páginas; FEN conferido em 0/7 diagramas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual | `2026-10-16-fatia-xv-passo-A1.json` |
| xv | A2 | i020, i021, i022, i023, i024, i025, i026 | gestos pendentes | 14 | 6 | 4 (diagramas; texto pendente) | pendente: nenhuma linha com texto verificado; estrutura revisada em 0/7 páginas; FEN conferido em 0/7 diagramas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual | `2026-10-16-fatia-xv-passo-A2-204155.json` |
| xv | A3 | i020, i021, i022, i023, i024, i025, i026 | gestos pendentes | 14 | 6 | 4 (diagramas; texto pendente) | pendente: nenhuma linha com texto verificado; estrutura revisada em 0/7 páginas; FEN conferido em 0/7 diagramas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual | `2026-10-17-fatia-xv-passo-A3.json` |
| xv | E | i020, i021, i022, i023, i024, i025, i026 | gestos pendentes | 14 | 6 | 4 (diagramas; texto pendente) | pendente: nenhuma linha com texto verificado; estrutura revisada em 0/7 páginas; FEN conferido em 0/7 diagramas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual | `2026-10-17-fatia-xv-passo-E.json` |
| xv | D1 | i020, i021, i022, i023, i024, i025, i026 | gestos pendentes | 14 | 6 | 4 (diagramas; texto pendente) | pendente: nenhuma linha com texto verificado; estrutura revisada em 0/7 páginas; FEN conferido em 0/7 diagramas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual | `2026-10-17-fatia-xv-passo-D1-101106.json` |
| xv | B | i020, i021, i022, i023, i024, i025, i026 | gestos pendentes | 14 | 6 | 4 (diagramas; texto pendente) | pendente: nenhuma linha com texto verificado; estrutura revisada em 0/7 páginas; FEN conferido em 0/7 diagramas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual | `2026-10-17-fatia-xv-passo-B.json` |
| xv | D2 | i020, i021, i022, i023, i024, i025, i026 | gestos pendentes | 14 | 6 | 4 (diagramas; texto pendente) | pendente: nenhuma linha com texto verificado; estrutura revisada em 0/7 páginas; FEN conferido em 0/7 diagramas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual | `2026-10-17-fatia-xv-passo-D2.json` |
| xv | L | i020, i021, i022, i023, i024, i025, i026 | gestos pendentes | 14 | 6 | 4 (diagramas; texto pendente) | pendente: nenhuma linha com texto verificado; estrutura revisada em 0/7 páginas; FEN conferido em 0/7 diagramas; sem conferência cega do texto aprovada e em dia; sem conferência cega de FEN igual | `2026-10-23-fatia-xv-passo-L.json` |
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
verificados antes do fechamento do D1**, o primeiro passo julgado pelos gestos da fatia
(sem eles, o número não existe; até a versão 0.7 do roadmap o prazo era o A3). Enquanto isso, as medidas de texto ficam "pendentes" e as
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
| `abbychess/controladores.py` | Os controladores das áreas, da verificação, dos diagramas, do livro (abrir, lote, F6, exportar), da fila (os modos e o escopo), da busca e da substituição |
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
| `abbychess/livro.py` | O lote síncrono das ferramentas e dos testes, e a fila de revisão do livro todo |
| `abbychess/servidor_de_leitura.py` | O servidor de leitura (§11): o processo filho com os modelos globais, a vez entre glifos, os deltas dos padrões, a queda e o fechamento |
| `abbychess/sessao.py` | A sessão de edição do Documento sem Qt (§6.3): alinhar, planejar (ou recusar o que é do passo G), aplicar; as figurinas (§6.4) |
| `abbychess/busca.py` | Localizar sem Qt (§7.1, §7.3): o índice das páginas (montado em processos), a busca com o `regex` e o tempo-limite, as classes `\L` `\P` `\C` `\V`, figurina = letra, a busca por glifo |
| `abbychess/substituir.py` | Substituir sem Qt (§7.2): os casos (Prosa, Notação, Ambos; o FEN nunca), `\1` e `\g<nome>`, o que ainda não tem tradução, e aplicar numa página como uma sessão de edição |
| `abbychess/ancoragem.py` | Onde os glifos virtuais da sessão ficam (a âncora de cada um, como o usuário os digitou) e as palavras que a montagem do core parte ou junta quando um box sai |
| `abbychess/lote.py` | O lote da janela (`CondutorDoLote`): decide, lê pelo servidor e grava na thread da interface; cancelar, retomar, `.antes-do-lote/` |
| `abbychess/exportar.py` | PDF pesquisável, DOCX e EPUB a partir das páginas gravadas, pelo core do PyBoxEditor, sem o cabeçalho e o rodapé corridos |
| `abbychess/historico.py` | O desfazer do projeto: transações por gid (o que cada ação mudou, por página), a pré-condição, o limite de 50 MB, a propagação que emenda o Enter |
| `abbychess/app/` | A interface PySide6 (a edição no Documento: `documento.py` e `edicao_na_janela.py`; Localizar: `barra_de_busca.py` e `busca_na_janela.py`; Substituir: `substituir_na_janela.py`; a Galeria: `galeria.py` e `galeria_na_janela.py`; a pergunta do Ctrl+T: `confirmacao.py`): a janela (só liga sinais aos controladores e desenha), `acoes.py` (menus e atalhos), `dialogos.py`, o executor com fila (`trabalho.py`), visor da página, painéis de treino, padrões e verificação, opções, conferência de diagramas |
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
  em ~37 ms. A troca de página, que no 2b ficou em 153–158 ms, é do passo A1 (abaixo). O alvo de §2
  vale "com o lote rodando", o que só o passo E permite medir.
- **O visor e a troca de página, desde o passo A1** (3 rodadas do commit `538adae`, pasta
  limpa). Trocar para uma página no cache, como a seguinte, já pré-carregada, leva 14 ms na
  mediana e 15 no p95 (alvo de 150). Uma página **já visitada** que saiu do cache leva
  130–133 ms na mediana e 143–149 no p95 (alvo de 600): é o mesmo método da troca do 2b
  (alternar as páginas 20 e 21, a inclinação já medida, no mesmo processo), que deu
  153–158. A **primeira** visita a uma página, num projeto que endireita as páginas, mede a
  inclinação e leva ~500 ms, como no 2b (medida da revisão de produto, fora da tabela); o
  processo novo de §15.3 não está medido. A pré-carga da seguinte roda 150 ms depois de a
  página pedida ser pintada: dentro da troca, ela disputava a CPU com a conversão e a
  pintura, e a troca fora do cache ficava em 213–215 ms (as 3 rodadas do `4e974a5`, em
  `docs/medidas/2026-10-16-pre-carga-no-ir-para-a1*.json`). A pintura dos boxes de uma
  página com 2.000 deles fica em 10–13 ms no p95 em zooms de 5% a 800% (alvo de 33), e o
  clique acha o box em ~0,002 ms. **A memória com o lote subiu** de ~1654 MB para 1773–1793
  MB (as 5 páginas e os 5 pixmaps que o cache guarda; alvo de 2560). O Enter até a cor
  mudar, a releitura e o Enter com uma propagação lenta em curso ficaram iguais aos do 2b
  (21, 15 e 19–21 ms na mediana). A qualidade dos três livros e a fatia, medidas no
  `4e974a5`, não mudaram (o passo não mexe na leitura; a correção depois dele só muda quando
  a pré-carga roda e os atalhos de zoom).
- **A edição no Documento, desde o passo D1** (3 rodadas e o portão do commit `c955dff`,
  pasta limpa; a primeira bateria, do `dd38d99`, antes das revisões, está em
  `docs/medidas/2026-10-17-primeira-rodada-d1*.json`). A troca, a releitura, o lote (8,1–8,5
  s por página, com e sem o servidor) e a memória (2029–2053 MB) ficaram iguais às do E.
  **O Enter até a cor mudar** ficou com a mesma mediana (24–25 ms em 2 das 3 rodadas), mas o
  p95 subiu ~3 ms em 3 das 4 medidas (27–36, contra 26–29 no E; alvo de 100), e uma rodada
  saiu alta por igual (33 na mediana), como a "rodada alta" já vista no A1 e no A3; até o fim
  da propagação, 88–95 na mediana (84 no E). É um custo pequeno e real, não investigado.
  **Montar o Documento** ficou em 32 ms na mediana (31 no E), mas o p95 subiu para 40–42 nas
  rodadas (32–33 no E), com máximos de 69–70: a vista guarda a unidade de cada caractere a
  cada montagem (`_guardar_as_unidades`, um laço em Python), para a sessão comparar.
  **O pico durante o lote** caiu de 132–137 ms para 92–105: a volta de cada página do lote
  saiu da janela (o `lote.json` numa thread e a página seguinte num passo à parte do laço de
  eventos), como o E deixou para o D1; o p99 segue em 2,2, e com o leitor falso caiu de
  7,6–14,1 para 2,8–4,5. **A edição em si** (informativo,
  medido pela revisão de produto na janela, fora da bateria, numa página de 1.890 glifos):
  uma tecla na sessão custa ~0,5 ms; confirmar uma palavra, 40–47 ms (a montagem do
  Documento é quase tudo); colar a página inteira por cima com 20 letras trocadas e
  confirmar, ~135 ms, e com toda palavra mudada, ~350 ms. **A suíte rápida** ficou em 56–60 s
  (o limite da §15.1 é 60): o passo seguinte que acrescentar testes de janela tem de medir.
  O **CA-F.1** não foi julgado: o texto e os FEN das p. 21–27 do Xadrez Vitorioso ainda não
  foram verificados (a fatia segue "gestos pendentes"; ver "O que falta você fazer").
- **O servidor de leitura, desde o passo E** (3 rodadas e o portão do commit `9c759e2`,
  pasta limpa). **Desde o E as medidas rodam como o programa abre o projeto**: a janela só
  com os padrões do livro e os modelos no servidor; até o A3, os modelos ficavam na própria
  janela. **O atraso da interface durante o lote** caiu para p99 de 2,2 ms nas 3 rodadas e
  no portão (alvo de 50; até o A3, as duas faixas de ~9 e ~21 ms), agora com todas as ações
  valendo. O máximo ficou em 132–137 ms (no A3, 96–106), e começa junto com a volta de
  uma página: o atraso é igual à distância até a gravação mais perto (o tique só dispara no
  fim do engasgo). Gravar a página custa 18–22 ms no p95; o resto vem do que a mesma volta
  faz na janela (o `lote.json` e preparar a página seguinte: carregar o modelo dela e o que o
  §4.6 mantém). Na prática, a cada página do lote (~8 s) um comando pode passar de 100 ms;
  tirar isso da thread da janela ficou para o D1, que edita durante o lote (e o fez: ver o
  item do D1). Com o leitor falso, 51 páginas
  sintéticas, uma a cada ~200 ms: p99 de 7,6–14 ms. **A releitura de um glifo com o lote
  rodando** (CA-11.7, do Alt+seta ao glifo lido pelo servidor) ficou em 40–46 ms na mediana
  e 64–124 no p95 (124 no portão; alvo de 150), com máximos de até 364 ms. Na primeira
  versão do passo, a segmentação da página do lote (~0,45 s, sem glifos no meio) não dava a
  vez, e uma das 4 medidas passou do alvo (205 ms no p95): a página do lote foi para uma
  thread do filho. **A releitura sem o lote** passou de 14–15 ms (A3) a 37–39 na mediana e
  42–45 no p95, porque agora vai ao servidor (nas 30 repetições o glifo não estava nos padrões
  do livro); o alvo é 150. **A memória somada** (a janela e o servidor) ficou em 1959–2050
  MB (alvo de 2560): o servidor com ~1010, e a janela com 720–820. A explicação provável é
  que o processo de teste guarda o que os módulos anteriores carregaram (as páginas e o
  histórico da linha de base): com o módulo do servidor sozinho, numa versão anterior do
  passo e numa rodada só, a soma foi de 1616 (janela ~450). Não foi repetido em 3 rodadas. **O lote de 20 páginas levou 161–163 s** (A3: 88), e não pelo servidor: o projeto
  da medida não tem padrões (no A3, o lote lia com os padrões que os testes do Enter tinham
  ensinado, e a leitura pelo padrão pula a cadeia global); no mesmo projeto, com os mesmos
  padrões, as mesmas 5 páginas levam 8,2 s cada com o servidor e sem ele
  (`lote_com_e_sem_servidor`). O Enter até a cor ficou em 24 ms na mediana e 26–29 no p95
  (A3: 21 e 23); a troca no cache em 14 (p95 17–19), fora do cache em 133–135 (A3: 128); montar
  o Documento em 32–40 no p95; o clique no Documento em 3,3. A qualidade dos três livros e a
  fatia, no `9c759e2`, ficaram iguais às do A3, e um teste `livro_real` confere que a página
  e os recortes lidos pelo servidor dão os mesmos boxes e leituras que lidos no processo, que
  é como `medir.py` e a fatia leem. As medidas da primeira versão do passo, com a linha de
  base ainda sem o servidor, estão em `docs/medidas/2026-10-17-primeira-rodada-e*.json`.
- **A suíte rápida está em 58–59 s**, no limite de 60 (§15.1): os testes do servidor
  falso e do laço do filho somaram ~5 s. Um passo que acrescente testes rápidos vai precisar
  tirar tempo de algum lugar.
- **O Documento, desde o passo A3** (3 rodadas do commit `271d582`, pasta limpa). O clique
  numa palavra do Documento (um clique de verdade, com o contorno na Imagem, o glifo no
  Inspetor, o cursor e a Linha seguindo) leva 2,5 ms na mediana e 2,8 no p95 (alvo de 50,
  CA-6.1; na primeira medida, 10 ms: a Linha procurava cada glifo dela na página inteira). Montar o Documento, que roda 150 ms depois da última mudança da página e fora do
  Enter, passou de ~22 ms (o texto puro, até o A2) a 31 na mediana e 32–33 no p95, pelos
  formatos do realce, os desenhos dos diagramas e as margens corridas (em cache). **Duas
  medidas subiram em relação ao A2**: o Enter até o fim da propagação, de 72–73 ms na
  mediana a 81 (89 numa rodada), pelo que a página faz a mais quando o glifo atual muda (o
  Documento e a Linha seguem a fila); e a memória com o lote, de ~1782 MB a ~1806 (os
  documentos e as imagens dos diagramas). Não foram investigadas além disso. A troca no
  cache (14 ms), fora do cache (128–129) e a releitura (14–15) ficaram como no A2. O Enter
  até a cor ficou em 21 ms na mediana e 23 no p95 em 2 das 3 rodadas e no portão; **a
  primeira rodada depois do portão** teve 30 na mediana e 37 no p95, um deslocamento por
  igual (o máximo, 39). Uma rodada assim apareceu também no A1 (a segunda do `4e974a5`, p95
  de 33) e na primeira medida do A3 (a segunda do `f058c02`); a do A2 (`1da748e`) foi outra
  coisa, uma cauda (p95 de 67, pico de 286). Não foi investigado. As medidas anteriores do
  A3, antes das correções da revisão de produto, estão em
  `docs/medidas/2026-10-16-primeira-rodada-a3*.json` e `…-segunda-rodada-a3*.json`.
  **Refluir as linhas em parágrafos** fica para o passo F, com os parágrafos do layout;
  **editar** no Documento veio no D1. O **CA-F.1** (os gestos para levar a fatia ao
  gabarito) segue pendente: o replay conta contra as linhas de texto verificadas do gabarito,
  e nenhuma está verificada ainda (`ferramentas\rotular.py`, ver "O que falta você fazer").
  Pela versão 0.8 do roadmap, o alvo de ≤ 85% depois do A3 saiu (o A3 é só leitura e não
  traz comando mais barato ao replay: o número seria o do A2), e o prazo da verificação
  passou ao fechamento do D1.
- **O espaço de trabalho, desde o passo A2** (3 rodadas do commit `93c94a7`, pasta limpa).
  As medidas do A1 ficaram iguais: a troca no cache em 14 ms na mediana, fora do cache
  130–135; a pintura dos boxes, 12–13 no p95; a releitura, 15 na mediana; o Enter até a cor
  mudar, 21 na mediana e 24–28 no p95 nas 3 rodadas e no portão. **Na primeira medida do
  passo** (commit `1da748e`, antes da revisão de produto), uma rodada teve o Enter com 30 ms
  na mediana, 67 no p95 e um pico de 286 ms, e o Enter com uma propagação lenta com p95 de
  42; não era a rodada alta do A1 (lá, p95 de 33 e máximo de 35, um deslocamento por igual),
  e sim uma cauda. As 3 rodadas finais, depois das correções da revisão (que não tocaram o
  caminho do Enter), não a repetiram; não foi investigado. Essas rodadas estão em
  `docs/medidas/2026-10-16-primeira-rodada-a2*.json`. A **Linha** (a linha atual ampliada)
  e a cláusula dela no CA-3.2 (a x-height ≥ 12 px nela) são do passo A3; a da Imagem (≥ 6
  px no zoom largura, no índice
  25 do livro de referência) passa em 1366×768 e em 1280×720. O Shift+F10 e a tecla Menu
  vêm do Windows como pedido de menu de contexto; o teste confere que cada painel abre o
  menu nesse pedido, não a tecla em si. A gaveta de Páginas é refeita do `livro.json` a cada
  troca de página e meio segundo depois de uma rajada de edições; com 230 páginas, ela fica
  pronta ~0,1 s depois de abrir o projeto (CA-8.3, desde o passo C). Com ela aberta (o padrão de um projeto novo numa janela de
  1600 px ou mais), a troca no cache passa de ~11 para ~16 ms na mediana (medida da revisão
  de produto, fora do protocolo); as medidas oficiais rodam com ela fechada.
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
- **O atraso da interface durante o lote, até o A3,** tinha duas faixas no p99 (perto de 9 e
  de 22 ms), abaixo do alvo de 50 ms (desde o E, ver o item do servidor de leitura). O máximo ficou em 128–154 ms nas 6
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
  guarda). Desligar essas ações na janela ficou para depois (o A2 não o fez; o passo K,
  com os estados vazios e os tokens, é o lugar).
- **Um projeto aberto por este programa não abre mais no programa da tag `passo-0`.** A
  primeira abertura grava em `projeto.json` campos novos (`fonte_sha256`, `fonte_tamanho`,
  `extras`), que o programa do passo 0 recusa como "ilegível". Para voltar ao passo 0 com um
  livro em andamento, use a cópia de segurança de antes do passo.

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
- **A revisão, desde o passo C**: no escopo livro, a fila das palavras desconhecidas passa
  à página seguinte, uma a uma (o léxico não tem resumo no `livro.json`); o "iguais nesta
  página" do aviso de ensino conta os glifos com a mesma leitura, e não os de forma
  parecida; a Galeria do livro tira os recortes de cada página da fonte (a primeira vez,
  ~0,15 s por página, em segundo plano); desde o passo I, o negrito medido por palavra fica
  no glifo, é guardado na amostra ensinada e separa os vizinhos do k-NN (a medição do
  itálico ainda está pendente); o glifo devolvido à fila por um esquecer fica com a leitura e sem a fonte (a
  busca por glifo o mostra em "sem leitura").
- **Localizar, desde o passo B**: figurina = letra vale no texto literal (com a regex ligada,
  use `\P`); o cabeçalho e o rodapé do índice saem de uma regra simples das linhas da página
  (a primeira e a última, curtas, com número, separadas do texto), e não da regra completa
  da exportação; a legenda ganha a etiqueta dela no passo H; buscar antes de o índice ficar
  pronto espera
  por ele (a barra de status mostra o progresso). O índice de 230 páginas cumpre os 2 s só
  com os processos já abertos (o primeiro projeto, aberto um pouco depois do programa); o
  projeto aberto junto com o programa, e o segundo da sessão, levam 2,0–2,9 s, e pela janela
  o índice chega a 2,4 s (CA-7.1, uma limitação conhecida).
- **Substituir, desde o passo D2**: o que é do passo G fica de fora (desabilitado na
  prévia): o caso comum é "rn" → "m" (e "m" → "rn"), que espera o juntar e o dividir glifos;
  uma troca editorial em que duas letras viram uma ("casa" → "lar") também. As figurinas não
  entram sozinhas no texto substituído (o §6.4 é da digitação). Uma troca no livro inteiro
  pode ocupar quase todo o desfazer (~43 MB em 230 páginas e 28 mil casos; a partir de ~270
  páginas com uma troca tão comum, passa dos 50 MB e fica sozinha no desfazer: os passos de
  antes saem, e a barra de status diz quantos).
- **A edição no Documento, desde o D1**: o que é do passo G (k letras por 1, 1 por k, o
  parágrafo, os estilos) é recusado com aviso; o Ctrl+T com uma edição do texto ainda na fila
  pede para tentar de novo depois que ela entrar; num projeto com páginas lidas antes do D1,
  o modo das peças "como o livro" só vê as figurinas delas quando forem gravadas de novo
  (escolha "Figurinas" nas Opções); apagar a quebra de linha impressa entre duas
  palavras não as junta, e uma linha que perde todos os boxes some, com o glifo virtual que
  sobrou indo para a linha vizinha (as linhas são da página; a Linha avisa). A posição que a Linha e os
  Avisos dão de um glifo é em pixels da página.
- **O lote não volta às páginas que já leu.** O padrão ensinado durante o lote vale nas
  páginas que ele começar depois (desde o passo E); as que ele já leu só mudam lidas de novo
  (F5, Ctrl+R ou outro lote).
- **As páginas para reler depois não abrem pelos Avisos.** O detalhe do fim do lote as lista
  em texto; Retomar o lote as lê, mas clicar nelas nos Avisos ainda não abre a página (o
  painel de Resultados ganha itens que abrem a página no passo B, com a busca).
- **Voltar ao estado antes do lote não se desfaz**, e vale para a última releitura de cada
  página pelo lote com "refazer" (a cópia de uma releitura substitui a da anterior).
- **Os parágrafos exportados pelos boxes saem do vão entre linhas.** Recuo de primeira
  linha, títulos e negrito não são reconhecidos (pela camada do PDF, são); a frase que passa
  de uma coluna para a outra sai em dois parágrafos.
- **Pela camada do PDF, a correção feita nos boxes não entra.** O texto vem do PDF, que já é
  o do autor; só o lado a jogar conferido na revisão passa. As páginas que o ChessBase imprime
  com a prosa em imagem (pp. 94 em diante do *Odds & Ends*) a régua manda aos boxes.
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
  (que tem **Página › Voltar ao estado antes do lote** desde o passo E) e as amostras de diagrama
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
- **Depois das pendências de 2026-10-23** (portão do `0888053`, coluna "pendencias" das
  tabelas; o registro em `docs/revisoes/pendencias.md`). O lote voltou a 8,5 s por página e o
  clique no Documento a 3,7 ms. **A releitura de um glifo com o lote** passa do alvo de 150 ms
  no p95 numa parte das rodadas (206 no portão, 101–153 em três repetições; no L, 106–169):
  com o lote duas vezes mais rápido, ela disputa o servidor com mais páginas. **O Enter**
  (38,8 ms na mediana) ainda paga ~25 ms da validação pelos lances, que monta o texto da página
  a cada edição. **A suíte rápida** leva ~2 min, acima dos 60 s da §15.1. Manter as quebras
  numa página da camada nativa não devolve a quebra onde a camada tirou o hífen da palavra
  partida.
