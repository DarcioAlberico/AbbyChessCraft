# Protocolo de rotulagem dos gabaritos (SPEC §15.2)

Os gabaritos `tests/verdade/<livro>/iNNN.json` são a verdade contra a qual o layout, o
texto e os diagramas são medidos. Um gabarito errado faz o programa "acertar" o erro, então
a regra é registrar **o que está impresso**, não o que a leitura deu.

## Duas partes, dois responsáveis

Os livros têm direito autoral. Por isso o gabarito tem duas partes:

| Parte | O que é | Quem faz |
|---|---|---|
| **Estrutura** | função de cada bloco, ordem de leitura, coluna, negrito, caixas, diagramas (FEN, lado a jogar, legenda, primeiros lances) | o assistente (Claude), olhando as faixas; revisada pelo usuário |
| **Texto** | o texto de cada linha (`linhas_corpo[].texto`, `blocos[].texto_impresso`) | **o usuário**, dono do livro |

O assistente **não transcreve** o texto dos livros: o `texto` de cada linha começa como a
leitura do programa, com `texto_verificado: false`, e só o usuário o corrige e o marca. As
medidas que dependem do texto (CER do corpo, CA-9.1, a fatia CA-F.1) só valem sobre linhas
com `texto_verificado: true`; o resto do gabarito (layout, cabeçalhos, legendas, diagramas)
vale assim que a estrutura estiver revisada.

## Etapas

1. **Rascunho**: `ferramentas\rotular.py rascunho` grava o JSON com a leitura atual
   (`verdade_versao: 0`) e, fora do git, em `.rotulagem/<livro>/iNNN/`, as faixas da página
   (`faixa_KK.png`, com o id de cada linha na margem em vermelho) e o recorte de cada
   diagrama (`diagrama_dN.png`).
2. **Estrutura** (assistente): corrige funções, ordem, coluna, negrito, divide linhas que
   juntam duas, acrescenta linhas que a leitura perdeu (com o texto vazio e
   `caixa_estimada: true`), e preenche os diagramas. `estrutura_por` e `verdade_versao: 1`.
3. **Texto** (usuário): `ferramentas\rotular.py texto-exportar --livro xv` gera
   `.rotulagem/<livro>/iNNN.txt`, uma linha por `linhas_corpo`, no formato `lNN<TAB>texto`.
   O usuário corrige o texto olhando as faixas, salva, e roda `ferramentas\rotular.py
   texto-importar --livro xv`, que grava o texto e marca `texto_verificado: true` nas
   linhas mudadas ou confirmadas (uma linha começada por `!` fica não verificada).
4. **Conferência cega** (usuário ou outra pessoa): em 1 página por livro,
   `ferramentas\rotular.py cego-modelo --livro xv --pagina iNNN` gera
   `.rotulagem/<livro>/iNNN.cego.txt` com os ids das linhas e o texto em branco; quem
   confere transcreve do zero, só pelas faixas, e `ferramentas\rotular.py cego --livro xv
   --pagina iNNN --por <nome> --txt <arquivo>` compara com o gabarito e grava o resultado nele
   (`conferencia_cega.texto`: concordância, aprovada se ≥ 99,5% dos caracteres, quem e
   quando). O mesmo com 1 diagrama por livro: montar o FEN só pela imagem, sem ver o do
   gabarito (nem o `fen_lido`), e `rotular.py cego ... --diagrama dN --fen <FEN>`; o
   resultado fica no diagrama (`conferencia_cega`), e o FEN igual passa a `fen_verificado`.
5. **Revisão**: o usuário confere a estrutura, o FEN e o lado de cada diagrama, e assina com
   `ferramentas\rotular.py revisar --livro xv --pagina iNNN --por <nome> --fen-verificado
   d0,d1 --lado-verificado d0`, que grava `revisado_por` e marca os diagramas conferidos.
6. **Rascunho de novo**: `rascunho` recusa refazer um gabarito que já tem trabalho
   (estrutura, texto verificado ou revisão); com `--forcar`, refaz e guarda o anterior em
   `iNNN.json.bak` (os seguintes, em `.bak1`, `.bak2`…).

## Regras da estrutura

- **Função de cada bloco** (`blocos[].funcao`): `texto`, `titulo` (título de seção ou
  capítulo), `cabecalho` (título corrido no alto), `rodape`, `numero_de_pagina`, `nota`,
  `legenda` (de diagrama, com `"diagrama": "dN"`), `diagrama`, `figura`, `tabela`, `ignorar`
  (sujeira, poeira de digitalização, textura de foto).
- **Linhas de corpo** (`linhas_corpo`): toda linha que é texto do livro (texto, título,
  legenda, nota). Cabeçalho, número de página, rodapé e ignorar **não** entram.
- **Linha que junta duas** (duas legendas lado a lado, as duas colunas numa linha só):
  dividir em dois itens, com caixas estimadas (`caixa_estimada: true`) e o texto do
  rascunho repartido onde der (sem transcrever; o usuário corrige depois).
- **Ordem** (`blocos[].ordem`): a ordem de leitura humana; em duas colunas, coluna a coluna,
  com `coluna` 0 (esquerda) ou 1. Diagramas também: a `ordem` e a `coluna` deles ficam no
  bloco de função `diagrama` (o item de `diagramas[]` tem o mesmo id e não as repete).
- **Negrito**: `negrito: true` na linha impressa inteira em negrito.
- **Diagramas** (`diagramas[]`): `fen` = a parte das peças (8 fileiras, da 8ª à 1ª, brancas
  embaixo salvo indicação do livro), conferida casa a casa e com a contagem de peças;
  `fen_lido` fica como veio do rascunho. `lado`: `w` ou `b` só se a página disser: a
  legenda, o ▲▼ do Yusupov, ou o lance logo depois do diagrama (`1...` diz que jogam as
  pretas, `1.` sem reticências, as brancas); senão `?`. `fen_verificado` e
  `lado_verificado` começam `false` e só o revisor os marca (`rotular.py revisar`), ou a
  conferência cega que deu igual (`rotular.py cego`). `legenda`: o id do bloco da legenda.
  `lances_seguintes`: até 6 meios-lances do texto logo depois do diagrama, em SAN com letras
  inglesas (K Q R B N), ou vazio.
- **Cabeçalho do JSON**: `pagina_impressa` (o número impresso, ou `null`),
  `verdade_versao: 1`, `estrutura_por`, `rotulado_por` (quem verificou o texto, ou `""`),
  `revisado_por: ""`.
- Ao fim, `ferramentas\rotular.py validar --livro <livro> --pdf <PDF>` sem problemas.
