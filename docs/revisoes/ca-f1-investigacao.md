# Por que a fatia custa quase o mesmo no passo 0 e no L (CA-F.1, 2026-10-23)

A medida do `c9e5751` deu 1.093 gestos no L contra 1.183 da linha de base do passo 0 (0,924; o
alvo é ≤ 0,70, ou seja, ≤ 828). Esta é a investigação de onde vão os gestos e do que os
baixaria. Os números vêm do replay instrumentado. Ele roda o mesmo `replay_fatia.replay`, num
projeto temporário, com `pagina.ensinar`, `dividir`, `juntar` e `descartar` embrulhados para
anotar cada correção. Não é uma medida do portão, e os scripts não estão no repositório.

## Onde vão os 1.093 gestos

| Comando | Vezes | Gestos | Igual no passo 0? |
|---|---|---|---|
| `ensinar_glifo` (3) | 205 | 615 | sim |
| `ensinar_da_fila` (2) | 12 | 24 | sim |
| `dividir_glifo` (2) | 48 | 96 | sim |
| `marcar_glifo` (4) | 15 | 60 | sim |
| `descartar_box` (2) | 15 | 30 | sim |
| `juntar_glifos` (2) | 11 | 22 | sim |
| `reler_pendentes` (1) | 6 | 6 | sim |
| Espaços | 15 | 30 | não: 120 no passo 0, impossíveis a 8 |
| Linhas não lidas (5 linhas, 170 caracteres) | | 190 | sim |
| Diagramas e navegação | | 20 | sim |

Duas razões fazem o L custar quase o mesmo que o passo 0:
- **O catálogo não tem comando mais barato.** Depois do passo 0, o único comando de texto novo é
  `corrigir_no_documento`, que custa 3, o mesmo que `ensinar_glifo`. A fila por caractere do
  passo I não está no catálogo.
- **A leitura e a propagação resolvem o mesmo número de glifos.** As 205 + 12 correções são
  iguais nos dois códigos.

## Os 217 glifos ensinados

- **47** são a primeira vez de cada caractere, e esses são inevitáveis.
- **122** são caracteres já ensinados, em boxes **pendentes**: a propagação passou por eles e o
  k-NN do livro não leu. 88 deles não tinham leitura nenhuma (`''→'r'` 14 vezes, `''→'s'` 11).
  Em 120 dos 122, a trava que barra é a **distância**: a amostra mais perto do mesmo caractere
  fica acima de 1.500. Em 36 também falha a altura ou a proporção. Nenhum dos 122 tinha uma
  amostra do caractere que passasse nas três travas. A menor distância fica entre 1.386 e
  5.501, com mediana ~2.080 e um quarto entre 1.500 e 1.700. Quando a propagação falhou, o
  caractere tinha de 1 a 8 amostras.
- **48** são caracteres já ensinados que **não estavam pendentes**: lidos com confiança ≥ 0,90
  pela rede ou pela base, ou lidos por um padrão do livro, que nunca volta à fila. Os pares mais
  comuns são `1→l` (7), `C→c` (5), `S→s` (3), `-→.` (3), `0→o` (2) e `1→i` (2).
  `precisa_revisao` não os manda à fila, e a propagação nunca olha para eles. Uns 23 são dígito no meio de palavra ou
  maiúscula no meio de minúsculas.

O recorte gravado ao ensinar e o que a propagação compara são o mesmo
(`vertical.recorte_de_pe`), então a distância é real. O descritor é o recorte em cinza
esticado para 32×32 e comparado pelo L2, e uma distância de 1.500 já é uma diferença média de
~47 níveis de cinza por pixel.

### Um descritor melhor

O teste usa os 9.959 glifos do corpo que estão certos no fim do replay (rotulados pelo
gabarito), pelo método da tabela de `abbychess/padroes.py`. As amostras são as K primeiras de
cada caractere nas páginas anteriores. Cada página de 21 a 26 é lida com as travas de proporção
e altura de hoje. O descritor de hoje usa o limiar de 1.500; os outros usam o limiar que dá o
mesmo número de erros.

| K | Hoje (cinza, 32×32) | `contraste_borrado` | `binario` (Otsu) |
|---|---|---|---|
| 1 | 39,9% (19 erros) | 47,0% | 51,0% |
| 3 | 66,7% (12 erros) | **79,0%** | 71,3% |
| 5 | 75,3% (13 erros) | **82,4%** | 71,3% |

`contraste_borrado` estica o contraste entre os percentis 2 e 98, reduz por área para 32×32 e
borra com σ 0,8. Com o mesmo número de erros, ele lê de 7 a 12 pontos a mais da página
seguinte. Os limiares foram escolhidos nesta mesma fatia, então o ganho é otimista. Antes de
adotar, ele tem de ser validado no Darcy Lima e no Yusupov, com a tabela do `padroes.py` medida
de novo. Pôr o glifo num quadrado mantendo a proporção piora muito, porque a trava da proporção
já faz esse papel.

## As 48 divisões

No snapshot há 53 divisões de 1 box para 2 caracteres, e **29 já têm o texto certo** num box só
(`ri`, `an`, `tr`, `rt`…). A exportação já sai certa nesses casos, mas `replay_fatia.diferencas`
compara o box com os caracteres um a um e cobra a divisão. São cerca de 58 gestos que não
correspondem a nenhum erro do texto. Eles pesam igual na linha de base e no L, então não mudam
a razão, mas inflam os dois números. As outras divisões são boxes sem leitura (15) ou com
leitura errada.

## As 5 linhas não lidas (190 gestos)

- **Duas linhas são erro do gabarito, não da leitura:** "Diagrama 5. Jogam as pretas." (i024 l03)
  e "Diagrama 8. Jogam as pretas." (i026 l28). A leitura as acha inteiras. Quem não casa é a
  caixa da linha no gabarito, que vai de 25% a 41% da altura da página e engole o diagrama. A
  revisão da estrutura (`revisado_por`) as corrige.
- **"Diagrama 6…" e "Diagrama 7…" (i025 l22 e l24):** as legendas de dois diagramas lado a lado
  saem como uma linha só.
- **i026 l06:** a linha sai partida, e só a metade da direita casa.

## O que baixaria o custo

O alvo pede ≤ 828 gestos, 265 a menos que hoje. Os efeitos abaixo são estimativas, cada uma
pelo número de casos acima vezes o custo do comando. Nenhuma foi medida no replay.

1. **Mandar à fila a leitura confiante improvável.** Um dígito no meio de uma palavra de
   letras, ou uma maiúscula no meio de minúsculas, vai para a revisão mesmo com confiança alta.
   Assim ele entra na propagação e na fila, a 2 gestos em vez de 3. São ~23 dos 48 confiantes,
   ou −25 a −70 gestos. A mudança é pequena e local (`precisa_revisao` com o contexto da
   palavra) e serve a qualquer livro escaneado.
2. **O descritor `contraste_borrado` no k-NN do livro**, depois de validado nos outros dois
   livros. Se ele recuperar de 30% a 40% dos 122 pendentes que hoje não casam, são −110 a −150
   gestos. Os padrões já gravados continuam valendo, porque o descritor é calculado na leitura
   a partir do PNG.
3. **Corrigir em lote uma confusão do livro.** Seria um comando novo, conferido pelo
   `test_custo_dos_comandos.py`: todas as leituras `0` dentro de palavras viram `o` com um
   Enter. Os pares que se repetem (`0→o` 11, `1→l` 12, `S→s` 6, `C→c` 6, `—→-` 8, `1→i` 5,
   `9→g` 4, `D→p` 4) somam ~56 correções, ou −80 a −110 gestos. Vale conferir antes se a fila
   por caractere do passo I já oferece esse caminho; se oferecer, falta só pô-la no catálogo.
4. **Dividir a linha** que junta duas legendas lado a lado (o que é do passo G) e a linha
   partida da i026: ~2 linhas, −60 a −70 gestos.

Somadas, as propostas 1 a 4 dão de −275 a −400 gestos, ou de 0,61 a 0,69 da linha de base. A
faixa passa do alvo, mas só se as estimativas se confirmarem.

Duas correções do lado da medida mudam os números sem mudar a razão:
- **O replay não cobra a divisão de um box cujo texto já está certo.** A linha de base é medida
  de novo com a mesma regra.
- **A revisão da estrutura corrige as caixas das duas legendas.** Ela é do usuário.

Nenhuma das propostas mexe no core do PyBoxEditor.

## O que foi feito (2026-10-23, com o sim do usuário para a 1 e a validação da 2)

**Proposta 1, implementada** (`abbychess/contexto.py`, `ca011ae` e revisão `29572c1`). A fatia
no `29572c1` (`2026-10-23-fatia-xv-passo-L-223221.json`) dá **1.066 gestos**, razão **0,901**
contra a linha de base de 1.183 (era 0,924). O CA-F.1 continua reprovado. A regra marca os
glifos confiantes que a palavra desmente, mas só 9 deixam de ser ensinados à mão (205 → 196
`ensinar_glifo`). Os outros entram na fila e na propagação, e lá o k-NN do livro esbarra na
mesma trava de distância dos 122 pendentes. A estimativa era de −25 a −70 gestos, e o
resultado foi −27.

**Proposta 2, reprovada na validação** (`ferramentas/medir_descritor.py`,
`2026-10-23-descritor.json`, no `ca011ae`). O limiar do `contraste_borrado` foi escolhido na
fatia: 1.278, que com K = 3 dá os mesmos erros do descritor de hoje a 1.500. Depois foi aplicado
sem mudança a 7 páginas do Darcy Lima e a 7 do Yusupov. Os rótulos são os glifos em que a
leitura confiante do programa e a camada de OCR do PDF concordam.

| Livro (glifos lidos) | K | Hoje: certos / errados | `contraste_borrado`: certos / errados |
|---|---|---|---|
| Xadrez Vitorioso (8.339), ajuste | 1 / 3 / 5 | 2.708 / 7, 4.711 / 4, 5.284 / 5 | 3.300 / 8, 5.221 / 4, 5.662 / 4 |
| Darcy Lima (9.104) | 1 / 3 / 5 | 5.990 / 1, 7.192 / 0, 7.407 / 0 | 5.886 / 2, 6.843 / 0, 7.091 / 0 |
| Yusupov (2.997) | 1 / 3 / 5 | 20 / 9, 223 / 11, 296 / 11 | 22 / 10, 220 / 11, 242 / 11 |

No Darcy Lima, também escaneado e em português, ele lê de 1 a 4 pontos **menos**. No Yusupov,
os dois empatam. O ganho da fatia era do Xadrez Vitorioso, não do descritor, e ele não foi
adotado. No Yusupov, os dois descritores leem menos de 10% da página seguinte com o limiar de
1.500. É um livro em que o k-NN do livro quase não propaga, e isso merece uma investigação
própria.

Para chegar a ≤ 0,70, faltam 238 gestos. O que ainda pode dar isso:
- a correção em lote de uma confusão (proposta 3);
- dividir a linha das legendas lado a lado (proposta 4);
- um k-NN que propague mais sem errar mais. Isso pede outra abordagem, que não seja só trocar o
  descritor: por exemplo, mais amostras por caractere ou uma métrica aprendida no próprio livro.

## A proposta 3, o ensinar em lote (2026-10-24, com o sim do usuário)

**O comando** (`02fc26a`). No campo do Glifo, o Ctrl+Enter ensina o glifo como o Enter. No
mesmo passo do desfazer, ele também corrige, sem ensinar, os outros glifos da página que têm a
mesma leitura e que a palavra desmente (`contexto.lote`). A troca só vale onde deixa a palavra
provável: o "0" de "C0L0CA" não vira "o", e nada muda num lance como "ca6".

Nenhum comando anterior fazia isso. A fila por caractere (o modo "Por caractere" do F7) só
põe juntos os glifos da mesma leitura, e cada um continua custando o seu gesto. A Galeria do
passo C corrige muitos
glifos de uma vez, mas mostra todos os glifos lidos como o caractere, inclusive os "0" certos
de "10" e de "1.e4". Escolher à mão os que estão dentro de palavras custa um gesto por glifo.

**No catálogo e no teste.** O catálogo vai à versão 6. O custo de cada comando é o do ensinar
que ele substitui:
- `ensinar_em_lote_da_fila`, 2 gestos: digitar e Ctrl+Enter;
- `ensinar_em_lote`, 3 gestos: clique, digitar e Ctrl+Enter.

`test_custo_dos_comandos.py` confere os dois na janela, com QTest. A linha de base do passo 0
medida de novo com o catálogo 6 (`2026-10-24-fatia-xv-passo-0.json`) continua em 1.183 gestos.

**No replay.** O lote substitui o ensinar quando deixa certos mais glifos do que o Enter
simples deixaria, contando a propagação que vem depois do Enter. A comparação roda numa cópia,
porque a propagação também acerta parte desses glifos de graça.

**A medida** (`2026-10-24-fatia-xv-passo-L.json`, no `02fc26a`, árvore limpa) dá **1.057
gestos**, razão **0,894** (era 0,901). O CA-F.1 continua reprovado, e faltam 229 gestos.
- **Os lotes.** Foram usados 8 vezes, sobre 23 glifos: `0→o` três vezes (7, 1 e 1 glifos),
  `1→l` três vezes (4, 3 e 1), `S→s` uma (4) e `I→l` uma (2).
- **O saldo.** O `ensinar_glifo` caiu de 196 para 185 (−33 gestos), e os 8 lotes custam 24.
  Sobram −9 gestos.

A estimativa da proposta era de −80 a −110 gestos e errou. Ela contava as confusões do
snapshot, antes da fila do contexto. Desde a proposta 1, essas leituras já vão para a fila,
e a propagação do padrão ensinado resolve a maior parte delas: dos 55 `1→l` improváveis do
snapshot, só 7 ainda são ensinados à mão.

**O que ainda se ensina à mão.** São 205 glifos, e 122 deles **não tinham leitura nenhuma**
(`''→r` 15, `''→s` 11, `''→p` 8, `''→i` 7…). As confusões que sobram são poucas por página:
`—→-` 8, `0→o` 7, `1→l` 7, `C→c` 6. Nenhum lote resolve os glifos sem leitura: eles são o
maior bloco que sobra (cerca de 366 gestos), seguido das linhas não lidas (190) e das divisões
(96). Para chegar a ≤ 0,70, o caminho passa por eles:
- uma leitura melhor dos glifos que hoje saem vazios, que é o k-NN do livro de antes;
- dividir as linhas das legendas lado a lado (proposta 4).

## O palpite da rede no glifo sem leitura (2026-10-24, com o sim do usuário)

**De onde veio.** Dos 61 glifos sem leitura do snapshot que pedem uma substituição, o primeiro
da rede global, abaixo do limiar dela (0,80), é o certo em 36. Uma faixa de confiança mínima
não ajudaria: os 36 certos têm todos confiança ≥ 0,4, e só 3 dos errados ficam abaixo disso.

**O comando** (`92ce6b9`). O glifo que ninguém leu chega ao Glifo com esse palpite no campo,
selecionado (SPEC §9.2). O Enter o ensina, e digitar o troca. A leitura diz que é palpite, e
o glifo continua sem leitura na fila até alguém decidir. O palpite vem do servidor de leitura,
num pedido com os glifos sem leitura da página toda.

O risco é o Enter por reflexo num palpite errado, que grava um padrão errado. Ele é o mesmo
de aceitar a leitura de um glifo lido com confiança baixa, que o Enter já ensina hoje.

**No catálogo e no teste.** O catálogo vai à versão 7, e cada comando custa um gesto a menos
que o ensinar que substitui:
- `aceitar_palpite_da_fila`, 1 gesto: o Enter;
- `aceitar_palpite`, 2 gestos: o clique e o Enter.

`test_custo_dos_comandos.py` confere os dois na janela. A linha de base com o catálogo 7
(`2026-10-24-fatia-xv-passo-0-082756.json`) continua em 1.183.

**A medida** (`2026-10-24-fatia-xv-passo-L-082803.json`, no `92ce6b9`, árvore limpa) dá **983
gestos**, razão **0,831** (era 0,894). O palpite foi aceito 74 vezes: 67 fora da vez da fila e
7 na vez dela. A estimativa era de −40 a −60, e a medida deu −74. A estimativa contava só os
61 glifos sem leitura do snapshot; o replay acha outros no caminho, como as partes de um box
dividido que os padrões do livro não leem.

## O alvo revisto (2026-10-24, com o sim do usuário)

Com o palpite, o que sobra na fatia é:
- 190 gestos de custo fixo do que nenhum comando corrige (5 linhas que a leitura não acha, a
  4 gestos cada, e os 170 caracteres delas, a 1);
- 118 `ensinar_glifo` e 5 `ensinar_da_fila`, sobretudo glifos que a rede erra;
- 48 divisões, 15 descartes, 15 marcações e 11 junções.

As alavancas que restam, somadas, ficam perto de 0,80: dividir as legendas lado a lado (cerca
de −25), não cobrar a divisão de um box cujo texto já está certo (a razão vai de 0,83 a cerca
de 0,82, porque o ajuste vale nos dois lados) e um k-NN do livro que propague mais sem errar
mais, que pede outra abordagem. Nenhuma combinação delas chega a 0,70.

O alvo passou a ser **≤ 85% da linha de base no fim do roadmap** (SPEC §15.4), no lugar de
≤ 70% depois do D1. Com ele, o CA-F.1 aprova (0,831), provisório até a estrutura e os FEN das
p. 21–27 serem revisados.
