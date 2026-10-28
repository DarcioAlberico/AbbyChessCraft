# Passo C — Revisão (§8)

O passo foi feito no ramo `passo-c-revisao` (de `76f370a` a `6796117`, mesclados em
`passo-i-treino`), com uma rodada de revisão de código (`936498d`) que **nunca entrou** em
`passo-i-treino`: a revisão de código do fechamento achou isso. O fechamento foi feito em
2026-10-28, depois do passo L, no ramo `fechamento-c` (worktree
`C:\Python-Chess2\AbbyChessCraft-fechamento`), sobre o código de hoje e no escopo do passo C.

## O que o passo fez

- **Os modos e o escopo da fila** (F7, Shift+F7): por confiança, por leitura, por caractere e
  palavras; a página ou o livro, com o Alt+↓ atravessando as páginas.
- **A Galeria por caractere** (CA-8.1): a grade dos recortes dos glifos lidos como um
  caractere, da página ou do livro; digitar aplica à seleção, Enter ensina, Shift+Enter só
  corrige, num passo só do desfazer em quantas páginas forem.
- **A aba Padrões**: as amostras por caractere com a origem, a altura, o efeito e quantos
  glifos cada uma leu; ir à origem; esquecer pelo Delete, que se desfaz.
- **Procedência** (CA-8.4): esquecer uma amostra devolve à fila, no livro inteiro, os glifos
  que ela leu, e a página verificada atingida volta a `em_revisao`.
- **O aviso de conflito ao ensinar** (CA-8.6) e o **Ctrl+T com a confirmação na barra**
  (CA-8.5, com as transições do §4.4 testadas).

## Revisões do fechamento

| Rodada | Revisor | Notas | Veredito |
|---|---|---|---|
| Código 1 | código e testes | Correção 5 · Simplicidade 8 · Testes 6 | volta |
| Produto 1 | produto, design e medição | Completude 6 · Fidelidade 6 · Clareza 6 · Produtividade 5 · Design 6 | volta |
| Código 2 | código e testes | 7 · 8 · 7 | volta |
| Produto 2 | produto, design e medição | 8 · 7 · 8 · 8 · 8 | volta |
| Código 3 | código e testes | 8 · 8 · 8 | aceita |
| Produto 3 | produto, design e medição | 8 · 8 · 8 · 8 · 8 | aceita |

**Código 1**: a rodada 1 (`936498d`) não estava mesclada, e com ela faltavam a pergunta do
Ctrl+T com a página dela (aceitar depois de trocar de página marcava a outra), o esquecer em
lote (40 amostras congelavam a janela ~24 s, cada uma relendo a base), a Galeria com
leituras misturadas num passo só e o refazer de um esquecer desfeito antes da procura. Além
disso: a Galeria e o esquecer endereçavam por posição de página, que muda quando a ordem do
livro muda (passo L); o Alt+↓ com o glifo atual fora da fila pulava o primeiro; a Galeria do
livro aceitava resposta velha; o CA-8.5 comparava a tabela do §4.4 com ela mesma.
**Produto 1**: o Ctrl+T marcava a página errada (o mesmo da rodada 1); as células da Galeria
saíam cortadas numa tira de ~11×14 px (a grade media a célula antes de o recorte chegar); a
grade ficava com a correção desfeita depois do Ctrl+Z; a Galeria vazia não dizia como
abri-la; a aba Padrões mostrava "Efeito: [1, 0]", nomes internos e a altura com ponto; o
README citava "~0,1 s" e "~0,15 s por página" sem JSON, e o CA-8.3 não media pelo método da
§15.3.
**Código 2**: o desfazer do esquecer ainda relia a base inteira (`restaurar_varios` com
`_carregar`); a correção pela Galeria não fazia o pós-edição das outras edições (o lado do
diagrama pela legenda, a validação pelos lances); o `_galeria_pendente` como estado solto.
**Produto 2**: o CA-8.3 aquecia uma vez só, e o README dizia 5; "Galeria de os glifos sem
leitura"; a Galeria não dizia quantos glifos estavam selecionados.

Os commits: `4d73292` (a rodada 1 trazida, com os conflitos resolvidos pelo código de hoje e
o `ensinar_varios`/`esquecer_varios` com o efeito do passo I), `c01cf97`, `cb1f928`,
`95c80a8` e `56a8a6b`.

## Decisões

| Decisão | Por quê |
|---|---|
| A Galeria se esvazia quando a ordem do livro muda | os glifos dela citam posições de páginas; corrigi-los editaria a página que passou a estar ali |
| A procura do esquecer refeita pela busca quando o índice é montado de novo | o índice é chaveado pela posição e refeito em `sequencia_mudou`; a resposta de antes era descartada em silêncio, e os glifos das outras páginas nunca voltavam à fila |
| `depois_de_editar` no controlador, para a Galeria, o substituir e o `_mudou` | uma edição só de uma vez em várias páginas não pode pular o lado dos diagramas nem a validação pelos lances |
| A aba Galeria aberta vazia mostra o caractere do glifo atual | o estado vazio pedia um caminho de menu que ninguém achava |

## Verificação

- Suíte rápida no `9ebe441`: 1726 testes aprovados e 3 pulados; ruff limpo.
- CA-8.1 a CA-8.6 em `tests/test_revisao.py`, `tests/test_revisao_janela.py` e
  `tests/test_espaco.py`; CA-8.3 [desempenho] em `tests/desempenho/test_revisao.py` (5
  aquecimentos e 30 rodadas, do `ProjetoDeLivro.abrir`), com o JSON no portão do fechamento.

## Limitações conhecidas

- Com o índice da busca ainda montando, a Galeria do livro avisa e mostra só o que já está
  indexado, em vez de esperar.
- "N iguais nesta página", no aviso de ensino, conta os glifos com a mesma leitura.
- A ordem das abas (Documento, Padrões, Diagramas, Galeria) não é a da §3.1.
- O custo de uma correção pela Galeria em dezenas de páginas (o JSON de cada uma lido na
  thread da interface) não está medido.
