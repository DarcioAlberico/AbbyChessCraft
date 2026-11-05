# Passo F — Layout (§5)

O passo foi feito em `passo-i-treino` (`a47d7a7`, `5270041`, `83269af`, `136610e`, `b6e2218`;
nas pendências, a exportação lendo pela `OrdemDeLeitura` do Documento e a correção das colunas
detectadas duas vezes). O fechamento foi feito em 2026-10-28, no ramo `fechamento-c` (worktree
`C:\Python-Chess2\AbbyChessCraft-fechamento`), sobre o código de hoje e no escopo do passo F,
revisado num worktree parado (`C:\Python-Chess2\AbbyChessCraft-revisao`).

## O que o passo fez

- **As zonas automáticas com função** (§5.1): título, legenda (ligada ao diagrama), nota,
  número de página, e o cabeçalho e o rodapé aprendidos pelas páginas lidas do livro; a
  ordem de leitura em colunas no Documento.
- **O modo Áreas**: a cor e o nome da função de cada área, as letras T/H/C/R/P/N/L/D/I/X e o
  menu de contexto, o Ordenar por cliques (Esc cancela), o modelo de áreas aplicado a um
  intervalo, às pares ou às ímpares, e Ctrl+Shift+R relendo só a área.
- **O CA-5.1 medido** (desde o fechamento): `ferramentas/medir.py` dá a precisão e a revocação
  por função e a ligação da legenda, e a tabela de qualidade do README as mostra.

## Revisões do fechamento

| Rodada | Revisor | Notas | Veredito |
|---|---|---|---|
| Código 1 | código e testes | Correção 5 · Simplicidade 7 · Testes 5 | volta |
| Produto 1 | produto, design e medição | Completude 5 · Fidelidade 4 · Clareza 4 · Produtividade 5 · Design 5 | volta |
| Código 2 | código e testes | 8 · 8 · 8 | aceita |
| Produto 2 | produto, design e medição | 6 · 7 · 7 · 5 · 7 | volta |
| Produto 3 | produto, design e medição | 8 · 8 · 8 · 8 · 8 | aceita |

**Código 1**: o Esc não cancelava o Ordenar na janela real (a ação global do Esc o levava);
duas legendas lado a lado viravam uma zona só ligada a um diagrama só; a regra da legenda
pegava prosa e lances; a zona mexida pelo usuário continuava "automática" (a exportação e a
aprendizagem a reclassificavam); o modelo de áreas renderizava cada página na thread da
interface e não aparecia na página aberta; um privado do core; apagar no meio do Ordenar
levantava ValueError; faltavam testes do CA-5.4, do CA-5.5 com 4 zonas e do Esc real.
**Produto 1**: no livro de referência, a função automática errava as legendas (0 de 17 certas
e ligadas) e punha 30 linhas do corpo como título; nenhuma medida do layout (o `medir.py`
dizia "não classifica blocos"); o Ordenar cego e frágil; os textos ensinavam as teclas 1–4;
as cores das funções abaixo de 3:1 e os rótulos ilegíveis sobre o impresso.
**Produto 2**: as áreas feitas antes de reconhecer (o fluxo do FineReader) saíam quase todas
"título" e continuavam depois do F5; as colunas do CA-5.1 não chegavam ao README.
**Produto 3** (aceita): depois do F5 os rótulos não se redesenhavam, e o lote não
reclassificava; corrigidos junto com este registro.

Os commits: `560b915`, `aa9dd1b`, `ae93f22`, `d38d59c`, `830c5b1`, a parte do F em `e3242a0`,
e o deste registro.

## O CA-5.1 no livro de referência

Medido nas p. 21–27 do Xadrez Vitorioso (reconhecidas, e de novo pela revisão de produto,
independente): legenda 17/17, todas ligadas ao diagrama certo (eram 0); cabeçalho 7/7; texto
193 acertos, 0 falsos, 2 faltaram; título 1 acerto e 1 falso (uma linha de lances com o número
mal lido; eram 30 falsos). O JSON oficial sai no portão do fechamento dos passos.

## Decisões

| Decisão | Por quê |
|---|---|
| O título pela altura das maiúsculas (percentil 90), e nunca numa linha com lance numerado | a linha de lances, cheia de maiúsculas e algarismos, tinha a mediana alta sem ser de letra maior |
| A legenda tolera o OCR só em "Diagrama"; pode ficar ao lado do diagrama; as linhas curtas logo embaixo dela a continuam | o OCR lê "Dia9rama"; o "Teste 1" fica à direita do tabuleiro; "Teste" com 2 erros pegava "These squares" |
| Uma regra só para a área que vale (a do usuário, a menor) e a linha pela zona da maioria dos glifos | três regras diferentes davam funções diferentes no Documento, na exportação e na medida |
| Sem leitura, nenhuma regra de tamanho; o F5 e o lote reclassificam as automáticas | as áreas feitas antes de ler não têm texto para decidir |

## Verificação

- Suíte rápida no commit deste registro: 1752 testes aprovados e 3 pulados; ruff limpo.
- CA-5.4 (o modelo só nas ímpares, a página aberta), CA-5.5 (4 zonas na ordem inversa, o Esc
  real), as legendas lado a lado, a regra da legenda, a zona do usuário, as áreas antes de ler
  em `tests/test_zonas.py` e `tests/test_janela_areas_e_verificacao.py`; as cores (CA-13.2)
  em `tests/test_estilo.py`.

## Limitações conhecidas

- Não há o editor "Área" no Inspetor (a função se troca pela letra ou pelo botão direito), e
  o vínculo da legenda não se edita à mão.
- Os diagramas não seguem o Ordenar no Documento (ficam onde a leitura os pôs), e a
  exportação não usa a ordem das áreas.
- ~~O FEN do diagrama de uma página de duas colunas (o Yusupov) cai pela altura, entre as linhas
  da outra coluna.~~ Era o CA-5.2 reprovando; corrigido em 2026-11-04 (roadmap, "A coluna só de
  tabuleiros").
- Fora do Ordenar, o número da área é a posição na lista, não a ordem de leitura.
- Na página densa (o Yusupov), o ornamento vira áreas minúsculas e os rótulos se sobrepõem.
- `_aprender_margens` varre as páginas lidas na thread da interface ao ligar o modo Áreas numa
  página sem zonas (~26 ms por página); o cabeçalho corrido não é aprendido de novo no F5 das
  áreas feitas antes de ler (o Documento ainda o mostra em cinza pela regra das margens).
- "Refazer as áreas automáticas" troca todas, sem confirmar (há Ctrl+Z); o diálogo do modelo
  vem com o livro inteiro como intervalo.
