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
